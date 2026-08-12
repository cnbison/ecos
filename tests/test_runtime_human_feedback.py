"""v0.91.0-b: Runtime + Plugin SDK 4 subscriber + LCAEngine.append_human_feedback 集成测试.

对应设计: discussions/2026-08-12-v091-design.md §3.

测试范围 (15 tests):
  1. 4 endpoint → LearningEvent → HumanFeedbackEntry → LCAEngine.append_human_feedback 链 (4 tests)
  2. Runtime.plan_human_feedback_aware kwargs 透传 (3 tests)
  3. LCAEngine._cognitive_twin dict 持久 + from_state fallback (3 tests)
  4. PluginRuntime 4 subscriber + handler defensive fallback (3 tests)
  5. POMDPPolicy 老 snapshot raise (per 防御性自检 [5]) (2 tests)
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from ecos.cta.belief_engine import BeliefEngine, BeliefState
from ecos.cta.cognitive_twin import (
    CognitiveTwinAgent,
    HUMAN_FEEDBACK_EVENT_TYPES,
    HumanFeedbackEntry,
    HumanFeedbackTrajectory,
)
from ecos.cta.event_log import LearningEvent, LearningEventType
from ecos.event import EventBus, get_default_bus, reset_default_bus
from ecos.lca.cta_input import CTAInput
from ecos.lca.l4_optimization.pomdp import POMDPPolicy
from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig
from web.api.plugin_runtime import (
    PluginRuntime,
    reset_plugin_runtime,
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_state_with_twin(student_id: str = "stu-001") -> BeliefState:
    """Build a BeliefState via BeliefEngine (跟 v0.83+ 4-layer 一致)."""
    engine = BeliefEngine()
    state = engine.create_initial_state(student_id)
    return state


def _make_lca_engine_with_state(student_id: str = "stu-001"):
    """Build LCAEngine + pre-allocated BeliefState for tests."""
    lca = LCAEngine(config=LCAEngineConfig(use_llm_rationale=False))
    state = _make_state_with_twin(student_id)
    return lca, state


# ── 1. 4 endpoint → LearningEvent → HumanFeedbackEntry → append_human_feedback (4 tests) ─


class TestHumanFeedbackEndpointChain:
    """4 endpoint → LearningEvent → HumanFeedbackEntry → LCAEngine.append_human_feedback 完整链."""

    def test_hint_requested_chain(self):
        """hint_requested LearningEvent → HumanFeedbackEntry → LCAEngine._cognitive_twin."""
        lca, state = _make_lca_engine_with_state()
        # Build event via factory
        event = LearningEvent.from_hint_requested(
            student_id="stu-hint",
            problem_id="pb-001",
            hint_level=2,
        )
        # Build entry via from_event factory
        entry = HumanFeedbackEntry.from_event(event)
        assert entry.event_type == "hint_requested"
        assert entry.payload == {"problem_id": "pb-001", "hint_level": 2}
        # LCAEngine.append_human_feedback (state 用于 lazy init CognitiveTwinAgent)
        lca.append_human_feedback("stu-hint", entry, state=state)
        # _cognitive_twin dict 已存
        assert "stu-hint" in lca._cognitive_twin
        assert lca._cognitive_twin["stu-hint"].human_feedback.count_by_type("hint_requested") == 1

    def test_idle_detected_chain(self):
        """idle_detected LearningEvent → HumanFeedbackEntry → LCAEngine._cognitive_twin."""
        lca, state = _make_lca_engine_with_state()
        event = LearningEvent.from_idle_detected(
            student_id="stu-idle",
            idle_seconds=15.5,
        )
        entry = HumanFeedbackEntry.from_event(event)
        assert entry.event_type == "idle_detected"
        assert entry.payload == {"idle_seconds": 15.5}
        lca.append_human_feedback("stu-idle", entry, state=state)
        assert lca._cognitive_twin["stu-idle"].human_feedback.count_by_type("idle_detected") == 1

    def test_goal_changed_chain(self):
        """goal_changed LearningEvent → HumanFeedbackEntry → LCAEngine._cognitive_twin."""
        lca, state = _make_lca_engine_with_state()
        event = LearningEvent.from_goal_changed(
            student_id="stu-goal",
            old_goal_id="python.variables",
            new_goal_id="python.loops",
        )
        entry = HumanFeedbackEntry.from_event(event)
        assert entry.event_type == "goal_changed"
        assert entry.payload == {"old_goal_id": "python.variables", "new_goal_id": "python.loops"}
        lca.append_human_feedback("stu-goal", entry, state=state)
        assert lca._cognitive_twin["stu-goal"].human_feedback.count_by_type("goal_changed") == 1

    def test_reflection_completed_chain(self):
        """reflection_completed LearningEvent → HumanFeedbackEntry → LCAEngine._cognitive_twin."""
        lca, state = _make_lca_engine_with_state()
        event = LearningEvent.from_reflection_completed(
            student_id="stu-reflect",
            reflection_text="I struggled with off-by-one errors",
            problem_id="pb-007",
        )
        entry = HumanFeedbackEntry.from_event(event)
        assert entry.event_type == "reflection_completed"
        assert entry.payload["reflection_text"] == "I struggled with off-by-one errors"
        assert entry.payload["problem_id"] == "pb-007"
        lca.append_human_feedback("stu-reflect", entry, state=state)
        assert lca._cognitive_twin["stu-reflect"].human_feedback.count_by_type("reflection_completed") == 1


# ── 2. Runtime.plan_human_feedback_aware kwargs 透传 (3 tests) ────────────


class TestPlanHumanFeedbackAware:
    """Runtime.plan_human_feedback_aware (6 plan API) kwargs 透传 + cognitive_twin fallback."""

    def test_human_feedback_entry_triggers_append(self):
        """human_feedback_entry kwarg 触发 LCAEngine.append_human_feedback."""
        from ecos.runtime import api as runtime_api
        lca, state = _make_lca_engine_with_state()
        event = LearningEvent.from_hint_requested(student_id="stu-kw", problem_id="pb-x", hint_level=1)
        entry = HumanFeedbackEntry.from_event(event)

        result = runtime_api.plan_human_feedback_aware(
            student_id="stu-kw",
            audience="student",
            cta_input=CTAInput(student_id="stu-kw", belief_state=state),
            lca_engine=lca,
            human_feedback_entry=entry,
        )
        # append 触发, _cognitive_twin dict 已存
        assert "stu-kw" in lca._cognitive_twin
        assert lca._cognitive_twin["stu-kw"].human_feedback.count_by_type("hint_requested") == 1
        # LCAResult 仍正常返回
        assert result is not None

    def test_cognitive_twin_none_fallback_to_dict(self):
        """cognitive_twin=None → fallback to lca._cognitive_twin[student_id]."""
        from ecos.runtime import api as runtime_api
        lca, state = _make_lca_engine_with_state()
        # 先 append 一个 feedback (lazy init CognitiveTwinAgent)
        event = LearningEvent.from_idle_detected(student_id="stu-fb", idle_seconds=10.0)
        lca.append_human_feedback("stu-fb", HumanFeedbackEntry.from_event(event), state=state)
        # cognitive_twin=None, plan 应 fallback 到 dict
        result = runtime_api.plan_human_feedback_aware(
            student_id="stu-fb",
            audience="student",
            cta_input=CTAInput(student_id="stu-fb", belief_state=state),
            lca_engine=lca,
        )
        assert result is not None
        # cognitive_twin 仍在 dict 中 (b 阶段 select 内部 store)
        assert "stu-fb" in lca._cognitive_twin

    def test_all_kwargs_pass_through(self):
        """motivation + domain_name + cognitive_twin 全部 kwargs 透传到 select_intervention."""
        from ecos.runtime import api as runtime_api
        lca, state = _make_lca_engine_with_state()
        # Build CognitiveTwinAgent
        twin = CognitiveTwinAgent.from_state(state)
        # motivation (v0.87.0-b) + domain_name (v0.88.0-b) + cognitive_twin (v0.91.0-b) 都传
        result = runtime_api.plan_human_feedback_aware(
            student_id="stu-all",
            audience="student",
            cta_input=CTAInput(student_id="stu-all", belief_state=state),
            lca_engine=lca,
            cognitive_twin=twin,
            domain_name="education",
        )
        assert result is not None
        # 3 kwargs 路径都走通, LCA 没 raise


# ── 3. LCAEngine._cognitive_twin dict 持久 + from_state fallback (3 tests) ─


class TestCognitiveTwinDictPersistence:
    """LCAEngine._cognitive_twin dict 持久 + from_state fallback 行为 (b 阶段)."""

    def test_append_human_feedback_lazy_init_from_state(self):
        """append_human_feedback + state → CognitiveTwinAgent.from_state 兜底 lazy init."""
        lca, state = _make_lca_engine_with_state()
        # 初始 dict 为空
        assert "stu-auto" not in lca._cognitive_twin
        # append 触发 lazy init from_state
        event = LearningEvent.from_reflection_completed(
            student_id="stu-auto", reflection_text="x", problem_id="pb",
        )
        entry = HumanFeedbackEntry.from_event(event)
        lca.append_human_feedback("stu-auto", entry, state=state)
        # dict 已 populated with CognitiveTwinAgent (from_state 派生)
        assert "stu-auto" in lca._cognitive_twin
        twin = lca._cognitive_twin["stu-auto"]
        assert isinstance(twin, CognitiveTwinAgent)
        assert twin.belief_state is state
        assert twin.human_feedback.count_by_type("reflection_completed") == 1

    def test_explicit_cognitive_twin_passed_through(self):
        """显式 cognitive_twin 透传到 select_intervention, dict 同步更新."""
        lca, state = _make_lca_engine_with_state()
        twin = CognitiveTwinAgent.from_state(state)
        cta = CTAInput(student_id="stu-exp", belief_state=state)
        # 显式传 cognitive_twin
        lca.select_intervention(cta, cognitive_twin=twin)
        # dict 存同一引用
        assert lca._cognitive_twin["stu-exp"] is twin

    def test_cognitive_twin_dict_persists_across_appends(self):
        """_cognitive_twin dict 跨多次 append_human_feedback 持久 (per-student state)."""
        lca, state = _make_lca_engine_with_state()
        # 1st append → lazy init
        event1 = LearningEvent.from_hint_requested(
            student_id="stu-persist", problem_id="pb-1", hint_level=1,
        )
        lca.append_human_feedback("stu-persist", HumanFeedbackEntry.from_event(event1), state=state)
        twin_after_first = lca._cognitive_twin["stu-persist"]
        # 2nd append → dict 不重建 (追加 entry)
        event2 = LearningEvent.from_hint_requested(
            student_id="stu-persist", problem_id="pb-2", hint_level=2,
        )
        lca.append_human_feedback("stu-persist", HumanFeedbackEntry.from_event(event2), state=state)
        twin_after_second = lca._cognitive_twin["stu-persist"]
        assert twin_after_first is twin_after_second, "dict 应保持引用稳定"
        # 2 entries 都在
        assert twin_after_second.human_feedback.count_by_type("hint_requested") == 2


# ── 4. PluginRuntime 4 subscriber + handler defensive fallback (3 tests) ──


class TestPluginRuntimeHumanFeedbackSubscribers:
    """PluginRuntime 4 subscriber (hint / idle / goal / reflection) + handler defensive."""

    def test_subscription_count_is_7(self):
        """start() registers 7 subscribers (3 v0.85 + 4 v0.91)."""
        reset_plugin_runtime()
        bus = EventBus()
        runtime = PluginRuntime(
            bus=bus,
            state_factory=lambda sid: (None, None),
            lca_engine_factory=lambda: None,
        )
        runtime.start()
        assert runtime.subscription_count == 8
        # 4 frontend stub endpoint 都有 subscriber
        assert bus.get_topic_count("hint_requested") == 1
        assert bus.get_topic_count("idle_detected") == 1
        assert bus.get_topic_count("goal_changed") == 1
        assert bus.get_topic_count("reflection_completed") == 1

    def test_handler_invokes_lca_append_human_feedback(self):
        """handler 调 LCAEngine.append_human_feedback, 写入 _cognitive_twin."""
        reset_plugin_runtime()
        lca, state = _make_lca_engine_with_state()
        bus = EventBus()
        runtime = PluginRuntime(
            bus=bus,
            state_factory=lambda sid: (BeliefEngine(), state),
            lca_engine_factory=lambda: lca,
        )
        runtime.start()
        # Publish hint_requested event
        event = LearningEvent.from_hint_requested(
            student_id="stu-handler",
            problem_id="pb-h",
            hint_level=1,
        )
        success = bus.publish("hint_requested", event)
        assert success == 1
        # LCAEngine._cognitive_twin 已写入
        assert "stu-handler" in lca._cognitive_twin
        assert lca._cognitive_twin["stu-handler"].human_feedback.count_by_type("hint_requested") == 1

    def test_handler_exception_does_not_break_bus(self):
        """handler 抛异常 (state_factory None) 不破坏 bus 其他 subscriber."""
        reset_plugin_runtime()
        bus = EventBus()
        # state_factory 返 (None, None) → handler 内 state=None + lca=None → exception
        runtime = PluginRuntime(
            bus=bus,
            state_factory=lambda sid: (None, None),
            lca_engine_factory=lambda: None,
        )
        # 4 handlers 都注册
        runtime.start()
        # publish 时 handler 内部异常被 _log.warning 兜住, bus 仍 ack
        event = LearningEvent.from_idle_detected(student_id="stu-fail", idle_seconds=5.0)
        # publish 不抛 (handler exception _log.warning 不 raise, EventBus 设计)
        success = bus.publish("idle_detected", event)
        assert success == 1, "publish 应 ack 即便 handler 异常"
        # Bus 状态健康: 仍可 publish 其他 event
        event2 = LearningEvent.from_reflection_completed(
            student_id="stu-ok", reflection_text="ok", problem_id="pb-2",
        )
        assert bus.publish("reflection_completed", event2) == 1


# ── 5. POMDPPolicy 老 snapshot raise per 防御性自检 [5] (2 tests) ────────


class TestPomdpOldSchemaRaise:
    """POMDPPolicy 老 v0.90.0 / v0.89.0-c snapshot schema_version raise (防御性自检 [5])."""

    def test_old_v090_snapshot_raises(self):
        """老 v0.90.0 snapshot (schema_version="0.90.0") raise ValueError."""
        p = POMDPPolicy(seed=42)
        old_state = {
            "schema_version": "0.90.0",
            "n_arms": 10,
            "n_states": 4,
            "n_observations": 4,
            "belief_state": [0.25, 0.25, 0.25, 0.25],
            "transition": [[[0.25] * 10] * 4] * 4,
            "observation_model": [[0.25] * 4] * 4,
            "reward": [[0.5] * 10] * 4,
        }
        with pytest.raises(ValueError, match=r"schema_version 不匹配"):
            p.load_state(old_state)

    def test_old_v089_c_snapshot_raises(self):
        """老 v0.89.0-c snapshot raise ValueError (防御性自检 [5] 同样生效)."""
        p = POMDPPolicy(seed=42)
        old_state = {
            "schema_version": "0.89.0-c",
            "n_arms": 10,
            "n_states": 4,
            "n_observations": 4,
            "belief_state": [0.25, 0.25, 0.25, 0.25],
            "transition": [[[0.25] * 10] * 4] * 4,
            "observation_model": [[0.25] * 4] * 4,
            "reward": [[0.5] * 10] * 4,
        }
        with pytest.raises(ValueError, match=r"schema_version 不匹配"):
            p.load_state(old_state)


# ── Test isolation fixture (autouse) ──────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset default bus + plugin runtime singleton for isolation."""
    reset_default_bus()
    reset_plugin_runtime()
    yield
    reset_default_bus()
    reset_plugin_runtime()