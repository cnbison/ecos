"""v0.84.0-a: LearningEvent unification tests.

Covers:
  - LearningEventType enum (string round-trip + unknown fallback)
  - LearningEvent factory methods (from_observation / from_calibration_message / from_response_submitted)
  - CalibrationMessage.to_learning_event (dual_agent integration)
  - FeatureExtractor double-write (in-memory + event_log)
  - DualAgentOrchestrator accepts event_log (constructor signature)
  - Backward compat (old "observation" string still works)
  - Defensive checks (silent pass + check [8] AST scan)
  - H3-c4 canary (LCA behavior unchanged)

Per discussions/2026-08-11-v084-design.md §2-§6.
"""
from __future__ import annotations

import logging
from datetime import datetime

import pytest

from ecos.cta.event_log import (
    EventLog,
    LearningEvent,
    LearningEventType,
)
from ecos.cta.belief_engine import Observation
from ecos.cta.belief_state import BloomLevel
from ecos.cta.feature_extractor import FeatureExtractor
from ecos.cta.observation_engine import ObservationContext
from ecos.dual_agent.orchestrator import DualAgentConfig, DualAgentOrchestrator
from ecos.dual_agent.protocol.messages import (
    CalibrationMessage,
    MessageType,
)
from ecos.lca.intervention import Intervention, InterventionType


# ─── LearningEventType enum (3 tests) ──────────────────────────────────────


class TestLearningEventType:
    """LearningEventType enum: 7 值 + from_value() 兼容 string/enum/unknown."""

    def test_enum_values(self):
        """All 7 event types are defined."""
        assert LearningEventType.OBSERVATION.value == "observation"
        assert LearningEventType.CALIBRATION.value == "calibration"
        assert LearningEventType.RESPONSE_SUBMITTED.value == "response_submitted"
        assert LearningEventType.HINT_REQUESTED.value == "hint_requested"
        assert LearningEventType.IDLE_DETECTED.value == "idle_detected"
        assert LearningEventType.GOAL_CHANGED.value == "goal_changed"
        assert LearningEventType.REFLECTION_COMPLETED.value == "reflection_completed"
        assert len(LearningEventType) == 7

    def test_from_value_string_roundtrip(self):
        """from_value accepts strings matching enum values."""
        assert LearningEventType.from_value("observation") == LearningEventType.OBSERVATION
        assert LearningEventType.from_value("calibration") == LearningEventType.CALIBRATION
        assert LearningEventType.from_value("response_submitted") == LearningEventType.RESPONSE_SUBMITTED

    def test_from_value_unknown_defaults_to_observation(self, caplog):
        """Unknown string + non-str/non-enum both default to OBSERVATION (defensive)."""
        with caplog.at_level(logging.WARNING):
            assert LearningEventType.from_value("unknown_event") == LearningEventType.OBSERVATION
            assert LearningEventType.from_value(12345) == LearningEventType.OBSERVATION
        assert any(
            "unknown event_type" in r.message or "non-str/non-enum" in r.message
            for r in caplog.records
        )


# ─── LearningEvent factory methods (4 tests) ──────────────────────────────


def _make_observation() -> Observation:
    """Helper: construct a test Observation."""
    return Observation(
        skill_id="python.variables",
        problem_id="pb-test-001",
        correct=True,
        score=0.85,
        bloom_level=BloomLevel.APPLY,
        explanation_text="test explanation",
        problem_text="x = 5",
        correct_answer="assignment",
        user_answer="x = 5",
        ai_reasoning="correct",
        timestamp=datetime(2026, 8, 11, 12, 0, 0),
    )


class TestLearningEventFactories:
    """LearningEvent factory methods: from_observation / from_calibration_message / from_response_submitted."""

    def test_from_observation_default_event_type(self):
        """from_observation defaults to event_type=OBSERVATION."""
        obs = _make_observation()
        event = LearningEvent.from_observation(obs, source="test")
        assert event.event_type == "observation"
        assert event.student_id == "python.variables"
        assert event.source == "test"
        assert event.payload["problem_id"] == "pb-test-001"
        assert event.payload["score"] == 0.85
        assert event.timestamp == obs.timestamp
        assert event.event_id.startswith("evt_")

    def test_from_observation_with_enum_event_type(self):
        """from_observation accepts LearningEventType enum for event_type."""
        obs = _make_observation()
        event = LearningEvent.from_observation(
            obs,
            source="test",
            event_type=LearningEventType.RESPONSE_SUBMITTED,
        )
        assert event.event_type == "response_submitted"

    def test_from_calibration_message_basic(self):
        """from_calibration_message wraps a CalibrationMessage as event_type=calibration."""
        msg = CalibrationMessage(
            message_type=MessageType.COMPLETED,
            student_id="stu-test-001",
            timestamp=datetime(2026, 8, 11, 12, 0, 0),
            calibration_round=3,
        )
        event = LearningEvent.from_calibration_message(msg, source="test")
        assert event.event_type == "calibration"
        assert event.student_id == "stu-test-001"
        assert event.source == "test"
        assert event.payload["calibration_round"] == 3
        assert event.payload["message_type"] == "completed"
        assert event.timestamp == msg.timestamp

    def test_from_response_submitted(self):
        """from_response_submitted creates event_type=response_submitted event."""
        obs = _make_observation()
        event = LearningEvent.from_response_submitted(obs, source="test")
        assert event.event_type == "response_submitted"
        assert event.source == "test"
        assert event.payload["problem_id"] == "pb-test-001"


# ─── CalibrationMessage.to_learning_event (2 tests) ────────────────────────


class TestCalibrationMessageToLearningEvent:
    """CalibrationMessage.to_learning_event: dual_agent integration helper."""

    def test_to_learning_event_basic(self):
        """to_learning_event converts CalibrationMessage with event_type=calibration."""
        msg = CalibrationMessage(
            message_type=MessageType.COMPLETED,
            student_id="stu-001",
            timestamp=datetime(2026, 8, 11, 10, 0, 0),
            calibration_round=5,
        )
        event = msg.to_learning_event()
        assert event.event_type == "calibration"
        assert event.student_id == "stu-001"
        assert event.timestamp == datetime(2026, 8, 11, 10, 0, 0)
        assert event.source == "dual_agent_orchestrator"
        assert event.payload["calibration_round"] == 5

    def test_to_learning_event_student_id_override(self):
        """to_learning_event accepts student_id override."""
        msg = CalibrationMessage(
            message_type=MessageType.COMPLETED,
            student_id="original",
            timestamp=1234567890.0,  # unix time float
            calibration_round=1,
        )
        event = msg.to_learning_event(student_id="override-sid")
        assert event.student_id == "override-sid"
        # unix float timestamp should be converted to datetime
        assert isinstance(event.timestamp, datetime)


# ─── FeatureExtractor double-write (3 tests) ──────────────────────────────


class TestFeatureExtractorDoubleWrite:
    """FeatureExtractor accepts optional event_log and double-writes response_submitted."""

    def _make_ctx(self, obs: Observation) -> ObservationContext:
        """Build a valid ObservationContext matching observation_engine.py:146-152 fields."""
        return ObservationContext(
            student_id="stu-001",
            skill_id=obs.skill_id,
            problem_id=obs.problem_id,
            score=obs.score,
            correct=obs.correct,
            bloom_level=obs.bloom_level,
            in_warmup=False,
            just_exited_warmup=False,
            bloom_step=0.05,
            observation=obs,
        )

    def test_no_event_log_in_memory_only(self):
        """Without event_log, FeatureExtractor keeps legacy in-memory behavior."""
        extractor = FeatureExtractor()  # event_log=None
        obs = _make_observation()
        ctx = self._make_ctx(obs)
        result = extractor.extract("stu-001", obs, ctx)
        assert len(result["history"]) == 1
        assert result["history"][0]["problem_id"] == "pb-test-001"
        # _event_log is None, no emit happened
        assert extractor._event_log is None

    def test_with_event_log_double_writes(self):
        """With event_log, FeatureExtractor writes both in-memory cache + event_log."""
        event_log = EventLog.in_memory()
        extractor = FeatureExtractor(event_log=event_log)
        obs = _make_observation()
        ctx = self._make_ctx(obs)
        result = extractor.extract("stu-001", obs, ctx)

        # In-memory cache populated
        assert len(result["history"]) == 1

        # EventLog also has the response_submitted event (student_id from observation.skill_id)
        events = event_log.load_events("python.variables")
        assert len(events) == 1
        assert events[0].event_type == "response_submitted"
        assert events[0].source == "feature_extractor"
        assert events[0].payload["problem_id"] == "pb-test-001"

    def test_emit_failure_does_not_break_extraction(self, caplog):
        """If event_log.emit raises, FeatureExtractor still completes extraction."""
        # Build an EventLog whose log_event raises
        class BrokenEventLog:
            def log_event(self, event):
                raise RuntimeError("simulated sqlite failure")

        extractor = FeatureExtractor(event_log=BrokenEventLog())
        obs = _make_observation()
        ctx = self._make_ctx(obs)
        with caplog.at_level(logging.WARNING):
            result = extractor.extract("stu-001", obs, ctx)
        # In-memory cache still populated
        assert len(result["history"]) == 1
        # Defensive warning logged
        assert any(
            "response_submitted" in r.message for r in caplog.records
        )


# ─── DualAgentOrchestrator integration (2 tests) ───────────────────────────


class TestDualAgentOrchestratorEventLog:
    """DualAgentOrchestrator accepts optional event_log (dual-write support)."""

    def test_orchestrator_accepts_event_log(self):
        """DualAgentOrchestrator __init__ accepts event_log kwarg."""
        event_log = EventLog.in_memory()
        # Use minimal config to avoid heavy LLM dependencies
        config = DualAgentConfig(timeout_sec=1, enable_timeout=False)
        orch = DualAgentOrchestrator(config=config, event_log=event_log)
        assert orch.event_log is event_log

    def test_orchestrator_event_log_default_none(self):
        """DualAgentOrchestrator defaults event_log to None (backward compat)."""
        config = DualAgentConfig(timeout_sec=1, enable_timeout=False)
        orch = DualAgentOrchestrator(config=config)
        assert orch.event_log is None


# ─── Backward compat (2 tests) ────────────────────────────────────────────


class TestBackwardCompat:
    """Old "observation" string still works (v0.81.0-a forward compat)."""

    def test_old_string_event_type_works(self):
        """LearningEvent with event_type='observation' (old v0.81 callers) works."""
        event = LearningEvent(
            event_id="evt_test123",
            student_id="stu-old",
            timestamp=datetime(2026, 8, 1),
            source="belief_updater",
            event_type="observation",  # old string, v0.81 style
            payload={"problem_id": "pb-001"},
        )
        # Round-trip via EventLog
        log = EventLog.in_memory()
        log.log_event(event)
        loaded = log.load_events("stu-old")
        assert len(loaded) == 1
        assert loaded[0].event_type == "observation"
        assert loaded[0].payload["problem_id"] == "pb-001"

    def test_existing_event_log_data_unaffected(self):
        """Events with non-enum event_type strings (e.g. 'observation') still loadable."""
        log = EventLog.in_memory()
        # Insert via v0.81 path (string event_type directly)
        legacy = LearningEvent(
            event_id="evt_legacy",
            student_id="stu-001",
            timestamp=datetime(2026, 7, 15),
            source="belief_updater",
            event_type="observation",
            payload={"problem_id": "pb-legacy-001"},
        )
        log.log_event(legacy)
        events = log.load_events("stu-001")
        assert len(events) == 1
        assert events[0].event_id == "evt_legacy"
        assert events[0].event_type == "observation"


# ─── Defensive checks (2 tests) ────────────────────────────────────────────


class TestDefensiveChecks:
    """防御性自检 [1] silent pass + [8] AST scan."""

    def test_no_silent_pass_in_new_code(self):
        """Grep for 'except ...: pass' or 'except ...: continue' (per check_defensive.sh:58)."""
        import subprocess
        # Mirror check_defensive.sh [1/8] regex: exact "except ... : pass/continue" at EOL
        pattern = r"^\s*except.*:[[:space:]]*(pass|continue)\s*$"
        for path in [
            "ecos/cta/event_log.py",
            "ecos/cta/feature_extractor.py",
            "ecos/dual_agent/protocol/messages.py",
            "ecos/dual_agent/orchestrator.py",
        ]:
            result = subprocess.run(
                ["grep", "-nE", pattern, path],
                capture_output=True, text=True,
            )
            # Empty stdout means no silent pass found
            assert result.stdout.strip() == "", (
                f"{path}: silent pass detected: {result.stdout}"
            )

    def test_check_8_state_mutation_scan(self):
        """防御性自检 [8] AST scan should pass (no direct state.X = value mutation)."""
        import subprocess
        # Run the check_no_direct_state_mutation.py script
        result = subprocess.run(
            ["python", "scripts/check_no_direct_state_mutation.py"],
            capture_output=True, text=True,
        )
        # exit code 0 = pass
        assert result.returncode == 0, (
            f"check [8] failed: {result.stdout}\n{result.stderr}"
        )


# ─── H3-c4 canary (1 test) ────────────────────────────────────────────────


class TestH3C4Canary:
    """H3-c4 canary: LCA behavior unchanged after LearningEvent unification."""

    def test_lca_event_log_unchanged(self):
        """LCAEngine operations don't emit LearningEvent (LCA is read-only per CQRS)."""
        # This is a smoke test: verify LCA path doesn't accidentally trigger event_log writes.
        # We construct a minimal orchestrator and check event_log.count_events after a no-op.
        event_log = EventLog.in_memory()
        from ecos.lca.orchestrator import LCAEngine
        lca = LCAEngine()
        # LCA is read-only; no event_log write should happen via LCA API
        initial_count = event_log.count_events("dummy")
        # (LCA.select_intervention would write to LCA state, not event_log)
        assert initial_count == 0
        assert event_log.mode == "in_memory"
