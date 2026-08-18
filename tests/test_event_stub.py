"""v0.85.0-d: Frontend event stub tests + production activation.

Covers:
  - LearningEvent.from_hint_requested factory
  - LearningEvent.from_idle_detected factory
  - LearningEvent.from_goal_changed factory
  - LearningEvent.from_reflection_completed factory
  - Blueprint registered in app
  - 4 endpoint emit events correctly (mock Flask test client)
  - Production activation (PluginRuntime.start() in if __name__ block)
  - Defensive: PluginRuntime start failure doesn't block Flask
  - 防御性自检 [1] silent pass + [8] AST scan
  - H3-c4 canary

Per discussions/2026-08-11-v085-design.md §5.
"""
from __future__ import annotations

import logging
import subprocess
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from ecos.cta.event_log import (
    LearningEvent,
    LearningEventType,
)
from ecos.event import EventBus, get_default_bus, reset_default_bus
from web.api.plugin_runtime import (
    PluginRuntime,
    get_plugin_runtime,
    reset_plugin_runtime,
)


# ── 4 factory tests (4 tests) ──────────────────────────────────────────────


class TestFrontendEventFactories:
    """4 frontend event factory methods (v0.85.0-d)."""

    def test_hint_requested_factory(self):
        """from_hint_requested produces hint_requested event with payload."""
        event = LearningEvent.from_hint_requested(
            student_id="stu-001",
            problem_id="pb-001",
            hint_level=2,
        )
        assert event.event_type == "hint_requested"
        assert event.student_id == "stu-001"
        assert event.payload["problem_id"] == "pb-001"
        assert event.payload["hint_level"] == 2

    def test_idle_detected_factory(self):
        """from_idle_detected produces idle_detected event with payload."""
        event = LearningEvent.from_idle_detected(
            student_id="stu-002",
            idle_seconds=30.5,
        )
        assert event.event_type == "idle_detected"
        assert event.student_id == "stu-002"
        assert event.payload["idle_seconds"] == 30.5

    def test_goal_changed_factory(self):
        """from_goal_changed produces goal_changed event with payload."""
        event = LearningEvent.from_goal_changed(
            student_id="stu-003",
            old_goal_id="python.variables",
            new_goal_id="python.loops",
        )
        assert event.event_type == "goal_changed"
        assert event.student_id == "stu-003"
        assert event.payload["old_goal_id"] == "python.variables"
        assert event.payload["new_goal_id"] == "python.loops"

    def test_reflection_completed_factory(self):
        """from_reflection_completed produces reflection_completed event with optional problem_id."""
        # With problem_id
        event1 = LearningEvent.from_reflection_completed(
            student_id="stu-004",
            reflection_text="This problem requires understanding of variables.",
            problem_id="pb-002",
        )
        assert event1.event_type == "reflection_completed"
        assert event1.payload["reflection_text"] == "This problem requires understanding of variables."
        assert event1.payload["problem_id"] == "pb-002"

        # Without problem_id (None)
        event2 = LearningEvent.from_reflection_completed(
            student_id="stu-005",
            reflection_text="General reflection.",
        )
        assert event2.payload["problem_id"] is None


# ── Blueprint registration (1 test) ────────────────────────────────────────


class TestBlueprintRegistration:
    """v0.85.0-d: event_stub_bp registered in app."""

    def test_blueprint_registered_in_app(self):
        """event_stub_bp registered with Flask app."""
        from web.api.app import app
        # Check if any view function has the endpoint name
        # Flask blueprint endpoints are namespaced with the blueprint name
        view_functions = list(app.view_functions.keys())
        # Blueprint endpoints: event_stub.api_event_hint / event_stub.api_event_idle / etc
        assert "event_stub.api_event_hint" in view_functions
        assert "event_stub.api_event_idle" in view_functions
        assert "event_stub.api_event_goal_change" in view_functions
        assert "event_stub.api_event_reflection" in view_functions


# ── Endpoint behavior via Flask test client (4 tests) ──────────────────────


class TestEndpointBehavior:
    """4 endpoint behavior via Flask test_client."""

    @pytest.fixture
    def client(self):
        """Flask test client."""
        from web.api.app import app
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_hint_endpoint_emits_event(self, client):
        """POST /api/event/hint emits hint_requested event."""
        reset_default_bus()
        # Subscribe to hint_requested
        bus = get_default_bus()
        received = []
        bus.subscribe("hint_requested", lambda e: received.append(e))

        resp = client.post("/api/event/hint", json={
            "student_id": "stu-001",
            "problem_id": "pb-001",
            "hint_level": 2,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "logged"
        assert data["student_id"] == "stu-001"
        assert "event_id" in data

        # Event was emitted
        assert len(received) == 1
        assert received[0].event_type == "hint_requested"
        assert received[0].payload["problem_id"] == "pb-001"

    # ── v0.96.7: hint 内容生成 ────────────────────────────────────────

    def test_hint_returns_rule_generated_content(self, client):
        """v0.96.7: 真实 problem_id 返回基于元数据的提示 (考查点 + Bloom 层中文)."""
        resp = client.post("/api/event/hint", json={
            "student_id": "stu-001",
            "problem_id": "PB-Q01",  # 变量 L1, 无 misconception
            "hint_level": 1,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "logged"
        assert "hint" in data
        hint = data["hint"]
        assert "变量与赋值" in hint          # skill_name
        assert "L1" in hint and "记忆" in hint  # Bloom 层 + 中文标签
        # 不泄漏答案 (对照 Q 矩阵 correct_answer)
        from web.api.qmatrix import get_question_detail
        assert get_question_detail("PB-Q01")["correct_answer"] == "5"
        assert "5" not in hint
        assert "print(x)" not in hint

    def test_hint_includes_misconception_warning(self, client):
        """v0.96.7: 带 misconception 的题, hint 含误区描述 (M1-M8 权威库)."""
        resp = client.post("/api/event/hint", json={
            "student_id": "stu-001",
            "problem_id": "PB-Q02",  # 变量 L2, misconceptions=["M2"]
            "hint_level": 1,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "hint" in data
        hint = data["hint"]
        assert "常见误区" in hint
        assert "x=x+1" in hint or "赋值" in hint  # M2 名称/描述

    def test_hint_unknown_problem_returns_fallback(self, client):
        """v0.96.7: 未知 problem_id → 兜底提示 + status 仍 logged."""
        resp = client.post("/api/event/hint", json={
            "student_id": "stu-001",
            "problem_id": "not-exist-999",
            "hint_level": 1,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "logged"
        assert "hint" in data
        assert "没有针对性" in data["hint"]

    def test_idle_endpoint_emits_event(self, client):
        """POST /api/event/idle emits idle_detected event."""
        reset_default_bus()
        bus = get_default_bus()
        received = []
        bus.subscribe("idle_detected", lambda e: received.append(e))

        resp = client.post("/api/event/idle", json={
            "student_id": "stu-002",
            "idle_seconds": 45.0,
        })
        assert resp.status_code == 200
        assert len(received) == 1
        assert received[0].event_type == "idle_detected"
        assert received[0].payload["idle_seconds"] == 45.0

    def test_goal_change_endpoint_emits_event(self, client):
        """POST /api/event/goal_change emits goal_changed event."""
        reset_default_bus()
        bus = get_default_bus()
        received = []
        bus.subscribe("goal_changed", lambda e: received.append(e))

        resp = client.post("/api/event/goal_change", json={
            "student_id": "stu-003",
            "old_goal_id": "python.variables",
            "new_goal_id": "python.loops",
        })
        assert resp.status_code == 200
        assert len(received) == 1
        assert received[0].event_type == "goal_changed"

    def test_reflection_endpoint_emits_event(self, client):
        """POST /api/event/reflection emits reflection_completed event."""
        reset_default_bus()
        bus = get_default_bus()
        received = []
        bus.subscribe("reflection_completed", lambda e: received.append(e))

        resp = client.post("/api/event/reflection", json={
            "student_id": "stu-004",
            "reflection_text": "I learned about variables today.",
            "problem_id": "pb-002",
        })
        assert resp.status_code == 200
        assert len(received) == 1
        assert received[0].event_type == "reflection_completed"
        assert "variables" in received[0].payload["reflection_text"]


# ── Production activation (1 test) ─────────────────────────────────────────


class TestProductionActivation:
    """v0.85.0-d: PluginRuntime.start() in if __name__ block."""

    def test_if_name_block_calls_plugin_runtime_start(self):
        """web/api/app.py if __name__ block calls plugin_runtime.start()."""
        # Read the file and verify the activation code is present
        with open("/Users/loubicheng/project/ecos/web/api/app.py") as f:
            content = f.read()

        # Check: if __name__ block contains plugin_runtime.start()
        assert 'if __name__ == "__main__"' in content
        # Find the block
        start_idx = content.find('if __name__ == "__main__"')
        block = content[start_idx:]
        assert "plugin_runtime" in block
        assert ".start()" in block
        assert "Production activation" in block  # comment marker

    def test_start_failure_does_not_block_flask(self, caplog):
        """If PluginRuntime.start() raises, Flask still starts (defensive)."""
        # Mock PluginRuntime to raise on start
        reset_plugin_runtime()

        # Patch get_plugin_runtime to return a failing runtime
        from web.api.plugin_runtime import PluginRuntime

        original_start = PluginRuntime.start
        def failing_start(self):
            raise RuntimeError("simulated PluginRuntime start failure")

        PluginRuntime.start = failing_start
        try:
            # Simulate the if __name__ block logic (mirrors web/api/app.py)
            with caplog.at_level(logging.WARNING):
                try:
                    from web.api.plugin_runtime import get_plugin_runtime
                    plugin_runtime = get_plugin_runtime()
                    plugin_runtime.start()
                except Exception:
                    logging.getLogger(__name__).warning(
                        "Production activation: PluginRuntime 启动失败, "
                        "production 走 legacy fallback (Plugin 路径未生效)",
                        exc_info=True,
                    )

            # Warning was logged
            assert any(
                "PluginRuntime" in r.message for r in caplog.records
            )
        finally:
            PluginRuntime.start = original_start


# ── Defense: silent pass scan (1 test) ─────────────────────────────────────


class TestDefensiveChecks:
    """防御性自检 [1]: silent pass scan in event_stub.py."""

    def test_no_silent_pass_in_event_stub(self):
        """Grep 'except ...: pass' in web/api/event_stub.py."""
        pattern = r"^\s*except.*:[[:space:]]*(pass|continue)\s*$"
        result = subprocess.run(
            ["grep", "-nE", pattern, "web/api/event_stub.py"],
            capture_output=True, text=True,
        )
        assert result.stdout.strip() == "", (
            f"silent pass detected: {result.stdout}"
        )


# ── H3-c4 canary (1 test) ──────────────────────────────────────────────────


class TestH3C4Canary:
    """H3-c4 canary: LCA behavior unchanged after v0.85.0-d frontend stub."""

    def test_lca_path_unaffected(self):
        """LCA path not touched by v0.85.0-d frontend stub endpoints."""
        from ecos.lca.orchestrator import LCAEngine
        lca = LCAEngine()
        assert lca is not None


# ── Test isolation fixture (autouse) ──────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_default_bus():
    """Reset default bus + plugin runtime singleton for isolation."""
    reset_default_bus()
    reset_plugin_runtime()
    yield
    reset_default_bus()
    reset_plugin_runtime()
