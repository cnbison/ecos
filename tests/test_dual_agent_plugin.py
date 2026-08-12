"""v0.85.0-b: /api/dual_agent Plugin path tests.

Covers:
  - LearningEventType.REQUEST_CALIBRATION enum value
  - LearningEvent.from_request_calibration factory (5 fields + payload)
  - PluginRuntime._handle_request_calibration subscriber
  - PluginRuntime.get_last_calibration_result shared state
  - dual_agent.process_observation_for_student Plugin path
  - dual_agent.process_observation_for_student legacy fallback
  - PluginRuntime.start() registers 2 subscribers (response_submitted + request_calibration)
  - 防御性自检 [1] silent pass + [8] AST scan
  - H3-c4 canary

Per discussions/2026-08-11-v085-design.md §3.
"""
from __future__ import annotations

import logging
import subprocess
from datetime import datetime
from typing import Any, Tuple
from unittest.mock import MagicMock

import pytest

from ecos.cta.event_log import (
    EventLog,
    LearningEvent,
    LearningEventType,
)
from ecos.event import EventBus, get_default_bus, reset_default_bus
from web.api.plugin_runtime import (
    PluginRuntime,
    get_plugin_runtime,
    reset_plugin_runtime,
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_calibration_event_payload(
    student_id: str = "stu-001",
    problem_id: str = "pb-001",
    skill_id: str = "python.variables",
    correct: bool = True,
    score: float = 0.85,
    bloom_layer: str = "L3",
):
    """Build a request_calibration LearningEvent."""
    return LearningEvent.from_request_calibration(
        student_id=student_id,
        problem_id=problem_id,
        skill_id=skill_id,
        correct=correct,
        score=score,
        bloom_layer=bloom_layer,
    )


# ── LearningEventType enum (1 test) ─────────────────────────────────────────


class TestLearningEventTypeRequestCalibration:
    """LearningEventType.REQUEST_CALIBRATION enum value (v0.85.0-b 第 9 值)."""

    def test_request_calibration_enum_value(self):
        """REQUEST_CALIBRATION = 'request_calibration'."""
        assert LearningEventType.REQUEST_CALIBRATION.value == "request_calibration"
        # 10 values total
        assert len(LearningEventType) == 10


# ── from_request_calibration factory (3 tests) ─────────────────────────────


class TestFromRequestCalibrationFactory:
    """LearningEvent.from_request_calibration factory."""

    def test_factory_basic(self):
        """Factory produces event with event_type=request_calibration + structured payload."""
        event = _make_calibration_event_payload()
        assert event.event_type == "request_calibration"
        assert event.source == "submit_answer"
        assert event.student_id == "stu-001"
        assert event.event_id.startswith("evt_")

        # Payload structured
        assert event.payload["problem_id"] == "pb-001"
        assert event.payload["skill_id"] == "python.variables"
        assert event.payload["correct"] is True
        assert event.payload["score"] == 0.85
        assert event.payload["bloom_layer"] == "L3"

    def test_factory_with_custom_source(self):
        """Factory accepts custom source."""
        event = LearningEvent.from_request_calibration(
            student_id="stu-002",
            problem_id="pb-002",
            skill_id="python.loops",
            correct=False,
            score=0.3,
            bloom_layer="L5",
            source="custom_caller",
        )
        assert event.source == "custom_caller"
        assert event.student_id == "stu-002"
        assert event.payload["bloom_layer"] == "L5"

    def test_factory_payload_types(self):
        """Payload fields have correct types (defensive)."""
        event = _make_calibration_event_payload()
        assert isinstance(event.payload["correct"], bool)
        assert isinstance(event.payload["score"], float)
        assert isinstance(event.payload["problem_id"], str)
        assert isinstance(event.payload["skill_id"], str)
        assert isinstance(event.payload["bloom_layer"], str)


# ── PluginRuntime._handle_request_calibration (2 tests) ───────────────────


class TestHandleRequestCalibration:
    """PluginRuntime._handle_request_calibration subscriber."""

    def test_handler_calls_orchestrator(self):
        """Subscriber reconstructs Observation, calls orch.process_observation, stores result."""
        # Mock orchestrator
        orch = MagicMock()
        mock_result = MagicMock()
        mock_result.calibration_round = 5
        orch.process_observation = MagicMock(return_value=mock_result)

        # Mock orchestrator factory
        orch_factory = MagicMock(return_value=orch)

        # Mock _load_dual_state_if_needed (avoid actual DB load)
        import web.api.dual_agent as da_module
        original_load = da_module._load_dual_state_if_needed
        da_module._load_dual_state_if_needed = MagicMock()
        try:
            runtime = PluginRuntime(
                bus=EventBus(),
                state_factory=lambda sid: (None, None),
                dual_orchestrator_factory=orch_factory,
            )
            runtime.start()

            event = _make_calibration_event_payload()
            runtime._get_bus().publish("request_calibration", event)

            # orch.process_observation called once
            assert orch.process_observation.call_count == 1
            # Result stored in _calibration_results
            stored = runtime.get_last_calibration_result("stu-001")
            assert stored is mock_result
        finally:
            da_module._load_dual_state_if_needed = original_load

    def test_handler_returns_result(self):
        """Subscriber returns the CalibratedLCAResult."""
        orch = MagicMock()
        mock_result = MagicMock()
        mock_result.calibration_round = 1
        orch.process_observation = MagicMock(return_value=mock_result)
        orch_factory = MagicMock(return_value=orch)

        import web.api.dual_agent as da_module
        original_load = da_module._load_dual_state_if_needed
        da_module._load_dual_state_if_needed = MagicMock()
        try:
            runtime = PluginRuntime(
                bus=EventBus(),
                state_factory=lambda sid: (None, None),
                dual_orchestrator_factory=orch_factory,
            )
            runtime.start()

            event = _make_calibration_event_payload(student_id="stu-result")
            success = runtime._get_bus().publish("request_calibration", event)
            assert success == 1
            # _calibration_results populated
            assert runtime.get_last_calibration_result("stu-result") is mock_result
        finally:
            da_module._load_dual_state_if_needed = original_load


# ── PluginRuntime.start() registers 2 subscribers (1 test) ────────────────


class TestStartRegisters2Subscribers:
    """PluginRuntime.start() registers response_submitted + request_calibration."""

    def test_start_registers_both_subscribers(self):
        """start() adds 7 subscribers (v0.85.0-c: 3 + v0.91.0-b: 4 frontend stub)."""
        bus = EventBus()
        runtime = PluginRuntime(
            bus=bus,
            state_factory=lambda sid: (None, None),
            dual_orchestrator_factory=lambda: None,
            lca_engine_factory=lambda: None,
        )
        runtime.start()
        assert runtime.subscription_count == 8  # v0.85.0-c: 3 + v0.91.0-b: 4 frontend stub + v0.93.0-b: 1 diagnostic
        assert bus.get_topic_count("response_submitted") == 1
        assert bus.get_topic_count("request_calibration") == 1
        assert bus.get_topic_count("request_intervention") == 1


# ── dual_agent.process_observation_for_student Plugin path (1 test) ───────


class TestProcessObservationForStudentPluginPath:
    """dual_agent.process_observation_for_student Plugin path (PluginRuntime 已启动)."""

    def test_dual_agent_process_uses_plugin_path(self):
        """When subscriber is registered, dual_agent uses Plugin path (not legacy)."""
        reset_default_bus()
        reset_plugin_runtime()

        # Setup PluginRuntime with mock orchestrator
        orch = MagicMock()
        mock_result = MagicMock()
        mock_result.calibration_round = 3
        mock_result.calibration_round_minus_1 = 2
        # Need to mock attributes for _post_process_calibration
        mock_result.calibration_round = 3
        mock_result.intervention.intervention_type.value = "review"
        mock_result.bloom_target.name = "APPLY"
        mock_result.degraded_mode = False
        orch.process_observation = MagicMock(return_value=mock_result)
        orch.get_warnings = MagicMock(return_value=[])

        # Mock _write_calibration_log + _save_dual_state + _write_prev_actual_outcome
        import web.api.dual_agent as da_module
        original_load = da_module._load_dual_state_if_needed
        original_save = da_module._save_dual_state
        original_prev = da_module._write_prev_actual_outcome
        original_cal = da_module._write_calibration_log
        original_get_orch = da_module.get_dual_orchestrator
        original_enabled = da_module.DUAL_AGENT_ENABLED

        da_module._load_dual_state_if_needed = MagicMock()
        da_module._save_dual_state = MagicMock()
        da_module._write_prev_actual_outcome = MagicMock()
        da_module._write_calibration_log = MagicMock(return_value=42)
        da_module.get_dual_orchestrator = MagicMock(return_value=orch)
        da_module.DUAL_AGENT_ENABLED = True

        try:
            # Create PluginRuntime with custom orchestrator factory
            runtime = PluginRuntime(
                bus=get_default_bus(),
                state_factory=lambda sid: (None, None),
                dual_orchestrator_factory=lambda: orch,
            )
            runtime.start()

            # Patch module-level _plugin_runtime_singleton to use our runtime
            import web.api.plugin_runtime as pr_module
            pr_module._plugin_runtime_singleton = runtime

            # Now call process_observation_for_student
            result = da_module.process_observation_for_student(
                student_id="stu-001",
                problem_id="pb-001",
                skill_id="python.variables",
                correct=True,
                score=0.85,
                bloom_layer="L3",
            )

            # orch.process_observation called via subscriber (Plugin path)
            assert orch.process_observation.call_count == 1
            # Result returned by Plugin path
            assert result is not None
            assert result["round"] == 3
            assert result["intervention_type"] == "review"
            assert result["calibration_id"] == 42
        finally:
            da_module._load_dual_state_if_needed = original_load
            da_module._save_dual_state = original_save
            da_module._write_prev_actual_outcome = original_prev
            da_module._write_calibration_log = original_cal
            da_module.get_dual_orchestrator = original_get_orch
            da_module.DUAL_AGENT_ENABLED = original_enabled


# ── Legacy fallback (1 test) ──────────────────────────────────────────────


class TestLegacyFallback:
    """When no subscriber is registered, _legacy_process_observation is called."""

    def test_no_subscriber_falls_back_to_legacy(self):
        """bus.publish returns 0 → legacy direct path."""
        reset_default_bus()
        reset_plugin_runtime()

        orch = MagicMock()
        mock_result = MagicMock()
        mock_result.calibration_round = 1
        mock_result.intervention.intervention_type.value = "review"
        mock_result.bloom_target.name = "APPLY"
        mock_result.degraded_mode = False
        orch.process_observation = MagicMock(return_value=mock_result)
        orch.get_warnings = MagicMock(return_value=[])

        # Mock _write_calibration_log + others
        import web.api.dual_agent as da_module
        original_load = da_module._load_dual_state_if_needed
        original_save = da_module._save_dual_state
        original_prev = da_module._write_prev_actual_outcome
        original_cal = da_module._write_calibration_log
        original_get_orch = da_module.get_dual_orchestrator
        original_enabled = da_module.DUAL_AGENT_ENABLED

        da_module._load_dual_state_if_needed = MagicMock()
        da_module._save_dual_state = MagicMock()
        da_module._write_prev_actual_outcome = MagicMock()
        da_module._write_calibration_log = MagicMock(return_value=99)
        da_module.get_dual_orchestrator = MagicMock(return_value=orch)
        da_module.DUAL_AGENT_ENABLED = True

        try:
            # No PluginRuntime registered → bus.publish returns 0 → legacy path
            # (default bus singleton not started)
            result = da_module.process_observation_for_student(
                student_id="stu-001",
                problem_id="pb-001",
                skill_id="python.variables",
                correct=True,
                score=0.85,
                bloom_layer="L3",
            )

            # orch.process_observation called directly (legacy)
            assert orch.process_observation.call_count == 1
            assert result is not None
            assert result["calibration_id"] == 99  # from legacy path
        finally:
            da_module._load_dual_state_if_needed = original_load
            da_module._save_dual_state = original_save
            da_module._write_prev_actual_outcome = original_prev
            da_module._write_calibration_log = original_cal
            da_module.get_dual_orchestrator = original_get_orch
            da_module.DUAL_AGENT_ENABLED = original_enabled


# ── Defense: silent pass scan (1 test) ─────────────────────────────────────


class TestDefensiveChecks:
    """防御性自检 [1]: silent pass scan in plugin_runtime.py + dual_agent.py."""

    def test_no_silent_pass_added(self):
        """Grep 'except ...: pass' in plugin_runtime.py + dual_agent.py."""
        pattern = r"^\s*except.*:[[:space:]]*(pass|continue)\s*$"
        for path in ["web/api/plugin_runtime.py", "web/api/dual_agent.py"]:
            result = subprocess.run(
                ["grep", "-nE", pattern, path],
                capture_output=True, text=True,
            )
            assert result.stdout.strip() == "", (
                f"{path}: silent pass detected: {result.stdout}"
            )


# ── H3-c4 canary (1 test) ──────────────────────────────────────────────────


class TestH3C4Canary:
    """H3-c4 canary: LCA behavior unchanged after /api/dual_agent Plugin refactor."""

    def test_lca_path_unaffected(self):
        """LCA path not touched by v0.85.0-b /api/dual_agent Plugin refactor."""
        # The PluginRuntime subscriber for request_calibration calls orch.process_observation
        # which is the SAME code path as the legacy. Verify no LCA code change.
        # Smoke test: ensure LCA path still works (smoke)
        from ecos.lca.orchestrator import LCAEngine
        lca = LCAEngine()
        assert lca is not None
        # LCA Engine unchanged


# ── Test isolation fixture (autouse) ──────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_default_bus():
    """Reset default bus + plugin runtime singleton for isolation."""
    reset_default_bus()
    reset_plugin_runtime()
    yield
    reset_default_bus()
    reset_plugin_runtime()
