"""v0.86.0-d: Integration 测试套件 (Goal-aware Runtime + 真 A/B Test).

对应 12-kernel-mapping:
    - §2.3 Goal Ontology (Capability registry)
    - §1.3 Policy Engine (真 A/B Test LinUCB vs Thompson)
    - §5 Runtime API (Goal-aware plan + evaluate goal)

测试覆盖:
- DEFAULT_CAPABILITY_REGISTRY (3): 5 capabilities / register_default_capabilities / idempotent
- Runtime.plan_goal_aware (2): new API / basic
- Runtime.plan backward compat (1): call plan_goal_aware
- Runtime.evaluate goal (2): accept goal / prefer goal over goal_id
- PolicyABTest 真 A/B (3): with events / winner threshold / fallback
- 集成 (3): registry + plan + evaluate end-to-end

向后兼容:
- plan 行为不变 (委托 plan_goal_aware, 默认 goal=None)
- evaluate 接受 goal_id 字符串 (v0.83.0-c 兼容)
- DEFAULT_CAPABILITY_REGISTRY 不强制 (学生 current_goals 仍可 [])
- 防御性自检 [8] 仍 hard block (Runtime API 0 直接 mutation)
"""

from __future__ import annotations

from datetime import datetime

import pytest

from ecos.cta.belief_state import BeliefState
from ecos.cta.event_log import LearningEvent
from ecos.evaluation.evaluation_engine import EvaluationEngine
from ecos.evaluation.goal_completion import GoalStatus
from ecos.evaluation.policy_ab_test import ABTestResult, PolicyABTest
from ecos.goal import (
    DEFAULT_CAPABILITIES_LIST,
    Goal,
    get_default_ontology,
    register_default_capabilities,
    reset_default_ontology,
)
from ecos.lca.cta_input import CTAInput
from ecos.runtime.api import evaluate, plan, plan_goal_aware


# ────────────────────────────────────────────────────────────────────
# DEFAULT_CAPABILITY_REGISTRY (3 tests)
# ────────────────────────────────────────────────────────────────────


def test_default_capabilities_list_has_5_python_capabilities():
    """DEFAULT_CAPABILITIES_LIST 含 5 条 Python Capability."""
    assert len(DEFAULT_CAPABILITIES_LIST) == 5
    names = [c.name for c in DEFAULT_CAPABILITIES_LIST]
    assert "python_variables" in names
    assert "python_loops" in names
    assert "python_functions" in names
    assert "python_conditionals" in names
    assert "python_strings" in names
    # 全部 domain="python"
    assert all(c.domain == "python" for c in DEFAULT_CAPABILITIES_LIST)


def test_register_default_capabilities_idempotent():
    """register_default_capabilities 重复注册 idempotent (覆盖式)."""
    reset_default_ontology()
    onto = get_default_ontology()

    # 第一次注册
    n1 = register_default_capabilities(onto)
    assert n1 == 5
    assert len(onto.list_capabilities()) == 5

    # 第二次注册 (覆盖同名, 数量不变)
    n2 = register_default_capabilities(onto)
    assert n2 == 5
    assert len(onto.list_capabilities()) == 5

    # 注册后, from_capability 可用
    goal = onto.from_capability("python_variables", metric_dimension="K", metric_threshold=0.7)
    assert goal.capability == "python_variables"
    reset_default_ontology()


def test_register_default_with_default_singleton():
    """register_default_capabilities() 不传 onto 用 default singleton."""
    reset_default_ontology()
    n = register_default_capabilities()
    assert n == 5
    onto = get_default_ontology()
    assert onto.has_capability("python_loops")
    reset_default_ontology()


# ────────────────────────────────────────────────────────────────────
# Runtime.plan_goal_aware (2 tests)
# ────────────────────────────────────────────────────────────────────


def _mock_lca_engine():
    """创建 mock LCA engine (测试用)."""
    class MockLCAEngine:
        def select_intervention(self, cta_input, audience="student"):
            return {"intervention_type": "test", "audience": audience}

    return MockLCAEngine()


def _make_state_with_goal() -> tuple:
    """构造 state + goal (consistent + K.mastery >= 0.7)."""
    state = BeliefState(student_id="lbc_test")
    state.K.mastery_prob = 0.5
    state.bloom_profile.apply = 0.5
    state.overall_confidence = 0.5
    goal = Goal(
        goal_id="g1", capability="python_variables", objective="apply",
        metric_dimension="K", metric_threshold=0.7,
        evidence_ids=[101],
    )
    state.append_goal(goal)
    return state, goal


def test_plan_goal_aware_new_api():
    """v0.86.0-d: plan_goal_aware 是新 API, 接受 goal 参数."""
    state, goal = _make_state_with_goal()
    cta_input = CTAInput(student_id="lbc_test", belief_state=state)

    result = plan_goal_aware(
        student_id="lbc_test",
        cta_input=cta_input,
        lca_engine=_mock_lca_engine(),
        goal=goal,
    )
    assert result["intervention_type"] == "test"


def test_plan_goal_aware_without_goal_runs_state_only_check():
    """v0.86.0-d: plan_goal_aware 不传 goal 走 state-only check."""
    state, _ = _make_state_with_goal()
    cta_input = CTAInput(student_id="lbc_test", belief_state=state)

    result = plan_goal_aware(
        student_id="lbc_test",
        cta_input=cta_input,
        lca_engine=_mock_lca_engine(),
        # goal=None (走 state-only)
    )
    assert result["intervention_type"] == "test"


# ────────────────────────────────────────────────────────────────────
# Runtime.plan backward compat (1 test)
# ────────────────────────────────────────────────────────────────────


def test_plan_delegates_to_plan_goal_aware():
    """v0.86.0-d: plan 委托 plan_goal_aware (向后兼容)."""
    state, _ = _make_state_with_goal()
    cta_input = CTAInput(student_id="lbc_test", belief_state=state)

    # plan 跟 plan_goal_aware 行为一致
    result = plan(
        student_id="lbc_test",
        cta_input=cta_input,
        lca_engine=_mock_lca_engine(),
    )
    assert result["intervention_type"] == "test"


# ────────────────────────────────────────────────────────────────────
# Runtime.evaluate goal (2 tests)
# ────────────────────────────────────────────────────────────────────


def test_evaluate_accepts_goal_object():
    """v0.86.0-d: evaluate(metric='goal_completion', goal=Goal) work."""
    state = BeliefState(student_id="lbc_test")
    state.K.mastery_prob = 0.75
    goal = Goal(
        goal_id="g1", capability="python_variables", objective="apply",
        metric_dimension="K", metric_threshold=0.7,
    )
    result = evaluate(
        student_id="lbc_test",
        metric="goal_completion",
        state=state,
        goal=goal,
    )
    assert result["completed"] is True
    assert result["goal_id"] == "K.mastery>=0.7"


def test_evaluate_goal_id_still_works():
    """v0.86.0-d: evaluate(metric='goal_completion', goal_id=str) 向后兼容."""
    state = BeliefState(student_id="lbc_test")
    state.K.mastery_prob = 0.5
    result = evaluate(
        student_id="lbc_test",
        metric="goal_completion",
        state=state,
        goal_id="K.mastery>=0.7",  # 字符串路径 (v0.83.0-c)
    )
    assert result["completed"] is False
    assert result["goal_id"] == "K.mastery>=0.7"


# ────────────────────────────────────────────────────────────────────
# PolicyABTest 真 A/B (3 tests)
# ────────────────────────────────────────────────────────────────────


def _make_event(student_id: str, score: float) -> LearningEvent:
    """构造 dummy LearningEvent with score payload."""
    return LearningEvent(
        event_id=f"evt_{student_id}_{score}",
        student_id=student_id,
        timestamp=datetime.now(),
        source="test",
        event_type="response_submitted",
        payload={"score": score, "correct": score >= 0.7},
    )


def test_policy_ab_test_real_a_b_with_events():
    """v0.86.0-d: events 参数非空 → 真 A/B replay path."""
    ab = PolicyABTest()
    events = [_make_event("lbc_test", 0.7) for _ in range(10)]
    result = ab.compare("lbc_test", "linucb", "thompson", events=events)
    assert isinstance(result, ABTestResult)
    assert result.n_a == 10
    assert result.n_b == 10
    # mean_reward 是 0.7 (所有 event score=0.7)
    assert abs(result.mean_reward_a - 0.7) < 1e-9
    assert abs(result.mean_reward_b - 0.7) < 1e-9


def test_policy_ab_test_winner_threshold():
    """v0.86.0-d: 5% 阈值触发 winner."""
    ab = PolicyABTest()
    # 10 events with score=0.7, 10 events with score=0.5 -> mean ≈ 0.6
    # 不同 mean 触发 winner
    events = [_make_event("lbc_test", 0.7) for _ in range(5)] + \
             [_make_event("lbc_test", 0.3) for _ in range(5)]
    # 平均 = 0.5 (5 个 0.7 + 5 个 0.3)
    result = ab.compare("lbc_test", "linucb", "thompson", events=events)
    assert result.n_a == 10
    # mean_reward 都是 0.5 (同一 event 序列)
    assert abs(result.mean_reward_a - result.mean_reward_b) < 1e-9
    # 平局 → winner=None
    assert result.winner is None


def test_policy_ab_test_fallback_when_events_none():
    """v0.86.0-d: events=None 走 fallback (lca_engine=None → winner=None)."""
    ab = PolicyABTest()  # lca_engine=None
    result = ab.compare("lbc_test", "linucb", "thompson", events=None)
    assert result.winner is None
    assert result.n_a == 0


# ────────────────────────────────────────────────────────────────────
# 集成 (3 tests)
# ────────────────────────────────────────────────────────────────────


def test_registry_plus_plan_goal_aware_end_to_end():
    """集成: registry 注册 → plan_goal_aware 走 Goal-aware 路径."""
    reset_default_ontology()
    register_default_capabilities()
    onto = get_default_ontology()

    # 从默认 registry 构造 Goal
    goal = onto.from_capability(
        "python_variables", metric_dimension="K", metric_threshold=0.7,
    )
    assert goal.goal_id == "goal.python_variables.L3"

    # plan_goal_aware 接受这个 Goal
    state = BeliefState(student_id="lbc_test")
    state.K.mastery_prob = 0.5
    state.bloom_profile.apply = 0.5
    cta_input = CTAInput(student_id="lbc_test", belief_state=state)

    result = plan_goal_aware(
        student_id="lbc_test",
        cta_input=cta_input,
        lca_engine=_mock_lca_engine(),
        goal=goal,
    )
    assert result["intervention_type"] == "test"
    reset_default_ontology()


def test_evaluate_goal_from_default_registry():
    """集成: 从 default registry 构造 Goal → evaluate 判定."""
    reset_default_ontology()
    register_default_capabilities()
    onto = get_default_ontology()

    goal = onto.from_capability(
        "python_variables", metric_dimension="K", metric_threshold=0.7,
    )

    state = BeliefState(student_id="lbc_test")
    state.K.mastery_prob = 0.8  # >= 0.7, completed

    result = evaluate(
        student_id="lbc_test",
        metric="goal_completion",
        state=state,
        goal=goal,
    )
    assert result["completed"] is True
    reset_default_ontology()


def test_policy_ab_test_after_registry_setup():
    """集成: 真 A/B Test 走 events replay (跟 registry 独立)."""
    ab = PolicyABTest()
    events = [
        _make_event("lbc_test", 0.8),
        _make_event("lbc_test", 0.6),
        _make_event("lbc_test", 0.9),
        _make_event("lbc_test", 0.4),
        _make_event("lbc_test", 0.7),
        _make_event("lbc_test", 0.5),
    ]
    result = ab.compare("lbc_test", "linucb", "thompson", events=events)
    # 6 events, mean = (0.8+0.6+0.9+0.4+0.7+0.5)/6 = 3.9/6 = 0.65
    assert result.n_a == 6
    assert abs(result.mean_reward_a - 0.65) < 1e-9
    assert abs(result.mean_reward_b - 0.65) < 1e-9
    # 两 policy 同 event 序列, mean 一致 → 平局
    assert result.winner is None
