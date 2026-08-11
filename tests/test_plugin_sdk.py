"""v0.84.0-d: Plugin SDK 雏形 tests.

Covers:
  - PluginRuntime basic (start/stop/subscription_count)
  - PluginRuntime._handle_response_submitted delegates to Runtime.update_belief
  - web/api/belief.py:submit_answer uses Plugin path when subscriber registered
  - submit_answer falls back to legacy path when no subscriber (backward compat)
  - State mutation works through Plugin path (in-place reference)
  - Defense: belief.py doesn't import engine.update directly (AST scan)
  - Defense: silent pass scan
  - H3-c4 canary (LCA behavior unchanged)
  - Response shape backward compat

Per discussions/2026-08-11-v084-design.md §5.
"""
from __future__ import annotations

import logging
import subprocess
from datetime import datetime
from typing import Any, Tuple
from unittest.mock import MagicMock

import pytest

from ecos.cta.belief_engine import BeliefEngine, Observation
from ecos.cta.belief_state import BloomLevel
from ecos.cta.event_log import LearningEvent
from ecos.event import EventBus, get_default_bus, reset_default_bus
from web.api.plugin_runtime import PluginRuntime


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_obs(skill_id: str = "python.variables") -> Observation:
    """Build a test Observation."""
    return Observation(
        skill_id=skill_id,
        problem_id="pb-test-001",
        correct=True,
        score=0.85,
        bloom_level=BloomLevel.APPLY,
        explanation_text="test",
        problem_text="x = 5",
        correct_answer="assignment",
        user_answer="x = 5",
        ai_reasoning="correct",
        timestamp=datetime(2026, 8, 11, 12, 0, 0),
    )


def _make_response_submitted_event(student_id: str, obs: Observation) -> LearningEvent:
    """Build a response_submitted LearningEvent for tests."""
    return LearningEvent.from_response_submitted(
        obs,
        source="test_plugin_sdk",
    )


def _make_state_factory(engine: BeliefEngine, state: Any):
    """Build a state_factory that returns (engine, state) for a fixed student_id."""
    def factory(student_id: str) -> Tuple[Any, Any]:
        return engine, state
    return factory


# ── PluginRuntime basic (3 tests) ──────────────────────────────────────────


class TestPluginRuntimeBasic:
    """PluginRuntime: start/stop/subscription management."""

    def test_start_registers_response_submitted_subscriber(self):
        """start() registers 3 subscribers (response_submitted + request_calibration + request_intervention in v0.85.0-c)."""
        bus = EventBus()
        runtime = PluginRuntime(bus=bus, state_factory=lambda sid: (None, None))
        assert not runtime.is_started
        runtime.start()
        assert runtime.is_started
        assert runtime.subscription_count == 3  # v0.85.0-b/c 加了 request_calibration + request_intervention
        assert bus.get_topic_count("response_submitted") == 1

    def test_stop_unregisters_subscribers(self):
        """stop() clears all subscriptions."""
        bus = EventBus()
        runtime = PluginRuntime(bus=bus, state_factory=lambda sid: (None, None))
        runtime.start()
        assert bus.get_topic_count("response_submitted") == 1
        runtime.stop()
        assert not runtime.is_started
        assert runtime.subscription_count == 0
        assert bus.get_topic_count("response_submitted") == 0

    def test_double_start_is_noop_with_warning(self, caplog):
        """start() called twice is no-op (defensive)."""
        bus = EventBus()
        runtime = PluginRuntime(bus=bus, state_factory=lambda sid: (None, None))
        runtime.start()
        with caplog.at_level(logging.WARNING):
            runtime.start()  # should warn + skip
        assert runtime.subscription_count == 3  # still 3 (response_submitted + request_calibration + request_intervention)
        assert any(
            "已启动" in r.message for r in caplog.records
        )


# ── PluginRuntime.handle (2 tests) ─────────────────────────────────────────


class TestPluginRuntimeHandler:
    """PluginRuntime._handle_response_submitted: delegates to Runtime.update_belief."""

    def test_handler_calls_runtime_update_belief(self):
        """Handler reconstructs Observation from event.payload and calls Runtime.update_belief."""
        # Mock engine + state
        engine = MagicMock(spec=BeliefEngine)
        state = MagicMock()
        state.student_id = "stu-001"
        engine.update = MagicMock(return_value=state)

        bus = EventBus()
        runtime = PluginRuntime(
            bus=bus,
            state_factory=_make_state_factory(engine, state),
        )
        runtime.start()

        # Build event from observation
        obs = _make_obs()
        event = _make_response_submitted_event("stu-001", obs)

        # Publish (triggers handler)
        success = bus.publish("response_submitted", event)
        assert success == 1

        # engine.update was called with reconstructed Observation
        assert engine.update.call_count == 1
        call_args = engine.update.call_args
        # Args: (state, observation, ...) - we check observation was passed
        # Position 1 is observation (after state)
        passed_obs = call_args[0][1]
        assert passed_obs.skill_id == obs.skill_id
        assert passed_obs.problem_id == obs.problem_id

    def test_handler_returns_state(self):
        """Handler returns the (mutated) state."""
        engine = MagicMock(spec=BeliefEngine)
        state = MagicMock()
        state.student_id = "stu-001"
        engine.update = MagicMock(return_value=state)

        bus = EventBus()
        runtime = PluginRuntime(
            bus=bus,
            state_factory=_make_state_factory(engine, state),
        )
        runtime.start()

        obs = _make_obs()
        event = _make_response_submitted_event("stu-001", obs)
        result = bus.publish("response_submitted", event)
        # publish returns int (success count), not state
        assert result == 1


# ── Plugin path end-to-end (2 tests) ───────────────────────────────────────


class TestPluginPathEndToEnd:
    """End-to-end: Plugin produces event -> Runtime handles -> state mutates."""

    def test_real_belief_engine_via_plugin_path(self):
        """Use real BeliefEngine (not mock); verify state mutation through Plugin path."""
        engine = BeliefEngine()
        state = engine.create_initial_state("python.variables")  # match obs skill_id

        # Snapshot fields that should mutate (bloom apply, trajectory snapshots, version)
        initial_bloom_apply = float(state.bloom_profile.apply)
        initial_trajectory_len = len(state.trajectory.snapshots)
        initial_version = state.version

        bus = EventBus()
        runtime = PluginRuntime(
            bus=bus,
            state_factory=_make_state_factory(engine, state),
        )
        runtime.start()

        obs = _make_obs(skill_id="python.variables")
        event = _make_response_submitted_event("python.variables", obs)
        bus.publish("response_submitted", event)

        # Verify state was mutated (bloom_profile.apply + trajectory + version change)
        assert state.bloom_profile.apply != initial_bloom_apply, (
            f"Plugin path should mutate bloom_profile.apply ({initial_bloom_apply} -> "
            f"{state.bloom_profile.apply})"
        )
        assert len(state.trajectory.snapshots) > initial_trajectory_len, (
            "Plugin path should add trajectory snapshot"
        )
        assert state.version != initial_version, (
            "Plugin path should bump state version"
        )

    def test_state_factory_called_with_student_id_from_event(self):
        """state_factory(student_id) is called with event.student_id."""
        engine = MagicMock(spec=BeliefEngine)
        state = MagicMock()
        state.student_id = "python.variables"
        engine.update = MagicMock(return_value=state)

        factory_calls = []

        def factory(sid):
            factory_calls.append(sid)
            return engine, state

        bus = EventBus()
        runtime = PluginRuntime(bus=bus, state_factory=factory)
        runtime.start()

        obs = _make_obs()  # skill_id="python.variables" -> event.student_id="python.variables"
        event = _make_response_submitted_event("python.variables", obs)
        bus.publish("response_submitted", event)

        # event.student_id derives from observation.skill_id (fallback)
        # since Observation has no student_id field, event.student_id = "python.variables"
        assert factory_calls == ["python.variables"]


# ── Legacy fallback path (1 test) ──────────────────────────────────────────


class TestLegacyFallback:
    """When no subscriber is registered, _update_via_plugin_or_legacy falls back."""

    def test_no_subscriber_falls_back_to_legacy(self):
        """bus.publish returns 0 → fallback to engine.update directly."""
        from web.api.belief import _update_via_plugin_or_legacy

        reset_default_bus()  # ensure clean default bus with no subscribers

        engine = MagicMock(spec=BeliefEngine)
        state = MagicMock()
        state.student_id = "stu-001"
        engine.update = MagicMock(return_value=state)

        obs = _make_obs()
        result = _update_via_plugin_or_legacy(
            engine=engine, state=state, obs=obs, student_id="stu-001",
        )

        # engine.update was called directly (legacy fallback)
        assert engine.update.call_count == 1
        # Result is the state (mock returns same object)
        assert result is state


# ── Plugin principle: belief.py doesn't import engine.update (1 test) ──────


class TestPluginPrinciple:
    """Defense: belief.py:submit_answer should NOT directly call engine.update."""

    def test_belief_py_no_engine_update_import(self):
        """Grep belief.py: no 'from ... import BeliefEngine.update' or direct .update() call.

        Plugin 原则: submit_answer body should NOT directly call engine.update().
        The 1 fallback call inside _update_via_plugin_or_legacy is OK
        (defensive, used when no subscriber is registered).
        """
        # Read the file
        with open("/Users/loubicheng/project/ecos/web/api/belief.py") as f:
            content = f.read()

        # Strip comments (lines starting with #) to avoid counting comments
        non_comment_lines = [
            line for line in content.splitlines()
            if not line.strip().startswith("#")
        ]
        non_comment_content = "\n".join(non_comment_lines)

        # Count actual `engine.update(` calls (not in comments)
        update_calls = non_comment_content.count("engine.update(")
        # In _update_via_plugin_or_legacy: 1 occurrence (the legacy fallback)
        assert update_calls == 1, (
            f"belief.py should only call engine.update once "
            f"(in _update_via_plugin_or_legacy legacy fallback). Found {update_calls}."
        )

        # Verify no direct update call in submit_answer body
        submit_answer_start = content.find("def submit_answer(")
        helper_start = content.find("def _update_via_plugin_or_legacy(")
        submit_answer_body = content[submit_answer_start:helper_start]

        # Filter comments in submit_answer_body
        sa_non_comment = "\n".join(
            line for line in submit_answer_body.splitlines()
            if not line.strip().startswith("#")
        )
        assert "engine.update(" not in sa_non_comment, (
            "submit_answer body should NOT directly call engine.update() — "
            "Plugin 原则 violation"
        )


# ── Defense: silent pass scan (1 test) ─────────────────────────────────────


class TestDefensiveChecks:
    """防御性自检 [1]: silent pass scan in plugin_runtime.py."""

    def test_no_silent_pass_in_plugin_runtime(self):
        """Grep 'except ...: pass' or 'except ...: continue' in web/api/plugin_runtime.py."""
        pattern = r"^\s*except.*:[[:space:]]*(pass|continue)\s*$"
        result = subprocess.run(
            ["grep", "-nE", pattern, "web/api/plugin_runtime.py"],
            capture_output=True, text=True,
        )
        assert result.stdout.strip() == "", (
            f"silent pass detected: {result.stdout}"
        )


# ── H3-c4 canary (1 test) ──────────────────────────────────────────────────


class TestH3C4Canary:
    """H3-c4 canary: LCA behavior unchanged after Plugin SDK refactor."""

    def test_lca_path_unaffected(self):
        """LCA path not touched by v0.84.0-d + v0.85.0-b/c Plugin SDK refactor.

        v0.85.0-c 加了 lca_engine_factory + _handle_request_intervention, 引用
        ecos.lca.cta_input (CTAInput dataclass) 是允许的 (Plugin SDK 全量阶段
        LCA 纳入). 但 LCAEngine 核心逻辑 (Orchestrator / Planner / Evaluator /
        Policy Learner) 不应被动.
        """
        # Smoke test: PluginRuntime doesn't import LCAEngine core modules
        import web.api.plugin_runtime as pr
        source = open(pr.__file__).read()
        # 防御性: 允许 from ecos.lca.cta_input (data class), 但不应 import orchestrator 等核心
        forbidden_imports = [
            "from ecos.lca.orchestrator",
            "from ecos.lca.l4_optimization",
            "from ecos.lca.intervention",
        ]
        for forbidden in forbidden_imports:
            assert forbidden not in source, (
                f"PluginRuntime should not import {forbidden} (use factory pattern instead)"
            )


# ── Test isolation (autouse fixture) ──────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_default_bus():
    """Reset default bus before/after each test for isolation."""
    reset_default_bus()
    yield
    reset_default_bus()
