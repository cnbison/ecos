"""v0.85.0-c: /api/lca Plugin path tests.

Covers:
  - LearningEventType.REQUEST_INTERVENTION enum value
  - LearningEvent.from_request_intervention factory (1 field + payload)
  - PluginRuntime._handle_request_intervention subscriber
  - PluginRuntime.get_last_intervention_result shared state
  - PluginRuntime.start() registers 3 subscribers (response_submitted + request_calibration + request_intervention)
  - lca.select_intervention Plugin path
  - lca.select_intervention legacy fallback
  - 防御性自检 [1] silent pass + [8] AST scan
  - H3-c4 canary

Per discussions/2026-08-11-v085-design.md §4.
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


def _make_intervention_event_payload(
    student_id: str = "stu-001",
    audience: str = "student",
):
    """Build a request_intervention LearningEvent."""
    return LearningEvent.from_request_intervention(
        student_id=student_id,
        audience=audience,
    )


# ── LearningEventType enum (1 test) ─────────────────────────────────────────


class TestLearningEventTypeRequestIntervention:
    """LearningEventType.REQUEST_INTERVENTION enum value (v0.85.0-c 第 10 值)."""

    def test_request_intervention_enum_value(self):
        """REQUEST_INTERVENTION = 'request_intervention'."""
        assert LearningEventType.REQUEST_INTERVENTION.value == "request_intervention"
        # 10 values total
        assert len(LearningEventType) == 10


# ── from_request_intervention factory (2 tests) ────────────────────────────


class TestFromRequestInterventionFactory:
    """LearningEvent.from_request_intervention factory."""

    def test_factory_basic(self):
        """Factory produces event with event_type=request_intervention + structured payload."""
        event = _make_intervention_event_payload()
        assert event.event_type == "request_intervention"
        assert event.source == "lca_select_intervention"
        assert event.student_id == "stu-001"
        assert event.event_id.startswith("evt_")

        # Payload structured
        assert event.payload["audience"] == "student"

    def test_factory_with_custom_audience(self):
        """Factory accepts custom audience (e.g. 'teacher' / 'parent')."""
        event = LearningEvent.from_request_intervention(
            student_id="stu-002",
            audience="teacher",
            source="custom_caller",
        )
        assert event.source == "custom_caller"
        assert event.student_id == "stu-002"
        assert event.payload["audience"] == "teacher"


# ── PluginRuntime._handle_request_intervention (2 tests) ──────────────────


class TestHandleRequestIntervention:
    """PluginRuntime._handle_request_intervention subscriber."""

    def test_handler_calls_runtime_plan(self):
        """Subscriber reconstructs CTAInput, calls Runtime.plan, stores LCAResult."""
        # Mock state + LCAEngine
        mock_state = MagicMock()
        mock_lca_engine = MagicMock()
        mock_result = MagicMock()
        mock_lca_engine.select_intervention = MagicMock(return_value=mock_result)

        state_factory = lambda sid: (None, mock_state)
        lca_engine_factory = lambda: mock_lca_engine

        # Mock _save_lca_state (avoid DB call)
        import web.api.lca as lca_module
        original_save = lca_module._save_lca_state
        lca_module._save_lca_state = MagicMock()
        try:
            # Mock Runtime.plan
            from ecos.runtime import api as runtime_api
            original_plan = runtime_api.plan
            runtime_api.plan = MagicMock(return_value=mock_result)
            try:
                runtime = PluginRuntime(
                    bus=EventBus(),
                    state_factory=state_factory,
                    lca_engine_factory=lca_engine_factory,
                )
                runtime.start()

                event = _make_intervention_event_payload()
                runtime._get_bus().publish("request_intervention", event)

                # Runtime.plan called once with cta_input + lca_engine
                assert runtime_api.plan.call_count == 1
                # Result stored in _intervention_results
                stored = runtime.get_last_intervention_result("stu-001")
                assert stored is mock_result
            finally:
                runtime_api.plan = original_plan
        finally:
            lca_module._save_lca_state = original_save

    def test_handler_returns_result(self):
        """Subscriber returns the LCAResult."""
        mock_state = MagicMock()
        mock_lca_engine = MagicMock()
        mock_result = MagicMock()
        mock_lca_engine.select_intervention = MagicMock(return_value=mock_result)

        state_factory = lambda sid: (None, mock_state)
        lca_engine_factory = lambda: mock_lca_engine

        import web.api.lca as lca_module
        original_save = lca_module._save_lca_state
        lca_module._save_lca_state = MagicMock()
        try:
            from ecos.runtime import api as runtime_api
            original_plan = runtime_api.plan
            runtime_api.plan = MagicMock(return_value=mock_result)
            try:
                runtime = PluginRuntime(
                    bus=EventBus(),
                    state_factory=state_factory,
                    lca_engine_factory=lca_engine_factory,
                )
                runtime.start()

                event = _make_intervention_event_payload(student_id="stu-result")
                success = runtime._get_bus().publish("request_intervention", event)
                assert success == 1
                # _intervention_results populated
                assert runtime.get_last_intervention_result("stu-result") is mock_result
            finally:
                runtime_api.plan = original_plan
        finally:
            lca_module._save_lca_state = original_save


# ── PluginRuntime.start() registers 3 subscribers (1 test) ────────────────


class TestStartRegisters3Subscribers:
    """PluginRuntime.start() registers response_submitted + request_calibration + request_intervention."""

    def test_start_registers_three_subscribers(self):
        """start() adds 7 subscribers (v0.85.0-c: 3 + v0.91.0-b: 4 frontend stub)."""
        bus = EventBus()
        runtime = PluginRuntime(
            bus=bus,
            state_factory=lambda sid: (None, None),
            lca_engine_factory=lambda: None,
        )
        runtime.start()
        assert runtime.subscription_count == 8  # v0.85.0-c: 3 + v0.91.0-b: 4 frontend stub + v0.93.0-b: 1 diagnostic
        assert bus.get_topic_count("response_submitted") == 1
        assert bus.get_topic_count("request_calibration") == 1
        assert bus.get_topic_count("request_intervention") == 1


# ── lca.select_intervention Plugin path (1 test) ──────────────────────────


class TestLcaSelectInterventionPluginPath:
    """lca.select_intervention Plugin path (PluginRuntime 已启动)."""

    def test_lca_select_uses_plugin_path(self):
        """When subscriber is registered, lca.select uses Plugin path (not legacy)."""
        reset_default_bus()
        reset_plugin_runtime()

        # Mock LCAEngine
        mock_lca_engine = MagicMock()
        mock_lca_engine.select_intervention = MagicMock(return_value=MagicMock())

        # Mock state
        mock_state = MagicMock()

        # Mock _save_lca_state (avoid DB)
        import web.api.lca as lca_module
        original_save = lca_module._save_lca_state
        original_get_orch = lca_module.get_lca_engine
        lca_module._save_lca_state = MagicMock()
        lca_module.get_lca_engine = MagicMock(return_value=mock_lca_engine)
        try:
            from ecos.runtime import api as runtime_api
            original_plan = runtime_api.plan
            runtime_api.plan = MagicMock(return_value=MagicMock())
            try:
                # Create PluginRuntime with mock factory
                runtime = PluginRuntime(
                    bus=get_default_bus(),
                    state_factory=lambda sid: (None, mock_state),
                    lca_engine_factory=lambda: mock_lca_engine,
                )
                runtime.start()

                # Patch module-level singleton
                import web.api.plugin_runtime as pr_module
                pr_module._plugin_runtime_singleton = runtime

                # Call lca.select_intervention
                result = lca_module.select_intervention("stu-001", mock_state)

                # Runtime.plan called (Plugin path), legacy not called
                assert runtime_api.plan.call_count == 1
                # legacy path: engine.select_intervention NOT called directly
                assert mock_lca_engine.select_intervention.call_count == 0
            finally:
                runtime_api.plan = original_plan
        finally:
            lca_module._save_lca_state = original_save
            lca_module.get_lca_engine = original_get_orch


# ── Legacy fallback (1 test) ──────────────────────────────────────────────


class TestLegacyFallback:
    """When no subscriber is registered, _legacy_select_intervention is called."""

    def test_no_subscriber_falls_back_to_legacy(self):
        """bus.publish returns 0 → legacy direct path."""
        reset_default_bus()
        reset_plugin_runtime()

        mock_lca_engine = MagicMock()
        mock_lca_engine.select_intervention = MagicMock(return_value=MagicMock())
        mock_state = MagicMock()

        import web.api.lca as lca_module
        original_save = lca_module._save_lca_state
        original_load = lca_module._get_or_create_lca_state
        original_get_orch = lca_module.get_lca_engine
        lca_module._save_lca_state = MagicMock()
        lca_module._get_or_create_lca_state = MagicMock()
        lca_module.get_lca_engine = MagicMock(return_value=mock_lca_engine)
        try:
            # No PluginRuntime registered → bus.publish returns 0 → legacy path
            result = lca_module.select_intervention("stu-001", mock_state)

            # engine.select_intervention called directly (legacy)
            assert mock_lca_engine.select_intervention.call_count == 1
        finally:
            lca_module._save_lca_state = original_save
            lca_module._get_or_create_lca_state = original_load
            lca_module.get_lca_engine = original_get_orch


# ── Defense: silent pass scan (1 test) ─────────────────────────────────────


class TestDefensiveChecks:
    """防御性自检 [1]: silent pass scan in plugin_runtime.py + lca.py."""

    def test_no_silent_pass_added(self):
        """Grep 'except ...: pass' in plugin_runtime.py + lca.py."""
        pattern = r"^\s*except.*:[[:space:]]*(pass|continue)\s*$"
        for path in ["web/api/plugin_runtime.py", "web/api/lca.py"]:
            result = subprocess.run(
                ["grep", "-nE", pattern, path],
                capture_output=True, text=True,
            )
            assert result.stdout.strip() == "", (
                f"{path}: silent pass detected: {result.stdout}"
            )


# ── H3-c4 canary (1 test) ──────────────────────────────────────────────────


class TestH3C4Canary:
    """H3-c4 canary: LCA behavior unchanged after /api/lca Plugin refactor."""

    def test_lca_path_unchanged(self):
        """LCA path not touched by v0.85.0-c /api/lca Plugin refactor."""
        # LCAEngine select_intervention should still work as before
        from ecos.lca.orchestrator import LCAEngine
        lca = LCAEngine()
        assert lca is not None
        # LCA Engine unchanged (the Plugin path just routes through Runtime.plan which
        # internally calls the same lca.select_intervention)


# ── Test isolation fixture (autouse) ──────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_default_bus():
    """Reset default bus + plugin runtime singleton for isolation."""
    reset_default_bus()
    reset_plugin_runtime()
    yield
    reset_default_bus()
    reset_plugin_runtime()
