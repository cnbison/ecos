"""v0.86.0-b: Twin Consistency Check 测试套件.

对应 12-kernel-mapping §2.1 Twin 一致性保证.

测试覆盖:
- TwinConsistencyResult (2): basic / to_dict
- 5 规则检查 (5): rule_k_bloom / rule_tc_k / rule_goal_completed / rule_bloom_confidence / rule_goals_evidence
- 综合场景 (3): all_consistent / with_goal_param / recommendation_human_review
- Singleton (2): get_default_checker / reset
- Runtime.plan 集成 (2): consistent 不阻断 / inconsistent log warning + emit event

向后兼容:
- goal=None 走 state-only 检查 (v0.85 plan 调用)
- 防御性自检 [8] 仍 hard block (Checker 不 mutate state)
"""

from __future__ import annotations

import logging
from datetime import datetime

import numpy as np
import pytest

from ecos.cta.belief_state import BeliefState, ConfidenceDimensionState, TCState
from ecos.cta.event_log import EventLog, LearningEvent
from ecos.goal import Goal
from ecos.twin import (
    TwinConsistencyChecker,
    TwinConsistencyResult,
    get_default_checker,
    reset_default_checker,
)


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────


def _make_state(
    k_mastery: float = 0.5,
    bloom_apply: float = 0.5,
    bloom_analyze: float = 0.5,
    bloom_evaluate: float = 0.5,
    bloom_create: float = 0.5,
    c_confidence: float = 0.5,
    overall_confidence: float = 0.5,
    student_id: str = "lbc_test",
) -> BeliefState:
    """构造一个可控的 BeliefState (5D + Bloom + TC)."""
    state = BeliefState(student_id=student_id)
    state.K.mastery_prob = k_mastery
    state.bloom_profile.apply = bloom_apply
    state.bloom_profile.analyze = bloom_analyze
    state.bloom_profile.evaluate = bloom_evaluate
    state.bloom_profile.create = bloom_create
    state.C.confidence = c_confidence
    state.overall_confidence = overall_confidence
    return state


# ────────────────────────────────────────────────────────────────────
# TwinConsistencyResult (2 tests)
# ────────────────────────────────────────────────────────────────────


def test_result_basic_creation():
    """TwinConsistencyResult 默认值."""
    result = TwinConsistencyResult(consistent=True)
    assert result.consistent is True
    assert result.violations == []
    assert result.recommendation == "continue"
    assert result.goal_id is None


def test_result_to_dict():
    """TwinConsistencyResult.to_dict() 含全部字段."""
    result = TwinConsistencyResult(
        consistent=False,
        violations=["K.mastery=0.8 >= 0.7 但 Bloom.L3+_avg=0.4 < 0.5"],
        recommendation="fallback_intervention",
        goal_id="g1",
    )
    data = result.to_dict()
    assert data["consistent"] is False
    assert len(data["violations"]) == 1
    assert data["recommendation"] == "fallback_intervention"
    assert data["goal_id"] == "g1"


# ────────────────────────────────────────────────────────────────────
# 5 规则测试 (5 tests)
# ────────────────────────────────────────────────────────────────────


def test_rule_k_bloom_violation():
    """Rule 1: K.mastery >= 0.7 但 Bloom L3+ < 0.5 → violation."""
    state = _make_state(k_mastery=0.8, bloom_apply=0.3, bloom_analyze=0.3, bloom_evaluate=0.3, bloom_create=0.3)
    checker = TwinConsistencyChecker()
    result = checker.check(state)
    assert result.consistent is False
    assert any("K.mastery" in v and "Bloom.L3+" in v for v in result.violations)


def test_rule_tc_k_violation():
    """Rule 2: TC post_liminal 但 K.mastery < 0.6 → violation."""
    state = _make_state(k_mastery=0.4)
    state.C.tc_states["python_variables"] = TCState(
        tc_id="python_variables", status="post_liminal", progress=1.0
    )
    checker = TwinConsistencyChecker()
    result = checker.check(state)
    assert result.consistent is False
    assert any("TC.python_variables" in v and "K.mastery" in v for v in result.violations)


def test_rule_goal_completed_violation():
    """Rule 3: Goal.status="completed" 但 overall_confidence < 0.7 → violation."""
    state = _make_state(overall_confidence=0.5)
    state.current_goals.append(Goal(
        goal_id="g1", capability="vars", objective="apply", status="completed",
    ))
    checker = TwinConsistencyChecker()
    result = checker.check(state)
    assert result.consistent is False
    assert any("g1" in v and "overall_confidence" in v for v in result.violations)


def test_rule_bloom_confidence_violation():
    """Rule 4: Bloom L6+ (L5+L6) >= 0.5 但 C.confidence < 0.3 → violation."""
    state = _make_state(
        bloom_evaluate=0.6, bloom_create=0.6,  # L6+ avg = 0.6
        c_confidence=0.2,  # < 0.3
    )
    checker = TwinConsistencyChecker()
    result = checker.check(state)
    assert result.consistent is False
    assert any("Bloom.L6+" in v and "C.confidence" in v for v in result.violations)


def test_rule_goals_evidence_violation():
    """Rule 5: current_goals 非空但都无 evidence → violation."""
    state = _make_state()
    state.current_goals.append(Goal(goal_id="g1", capability="vars", objective="apply"))
    state.current_goals.append(Goal(goal_id="g2", capability="loops", objective="use"))
    # 都没 evidence
    checker = TwinConsistencyChecker()
    result = checker.check(state)
    assert result.consistent is False
    assert any("current_goals" in v and "evidence" in v for v in result.violations)


# ────────────────────────────────────────────────────────────────────
# 综合场景 (3 tests)
# ────────────────────────────────────────────────────────────────────


def test_all_rules_consistent():
    """全部 5 规则一致 → consistent=True, recommendation=continue."""
    state = _make_state(
        k_mastery=0.5,  # Rule 1 不触发 (K < 0.7)
        bloom_evaluate=0.4,  # Rule 4 L6+ avg < 0.5 不触发
        c_confidence=0.5,
        overall_confidence=0.5,
    )
    # 没 TC post_liminal (Rule 2 不触发)
    # 没 completed goal (Rule 3 不触发)
    # current_goals 空 (Rule 5 不触发)
    g_evidence = Goal(goal_id="g1", capability="vars", objective="apply", evidence_ids=[101])
    state.current_goals.append(g_evidence)

    checker = TwinConsistencyChecker()
    result = checker.check(state)
    assert result.consistent is True
    assert result.violations == []
    assert result.recommendation == "continue"


def test_with_goal_param_stricter_rule_5():
    """goal 传入时, Rule 5 严格: 该 Goal 必须有 evidence."""
    state = _make_state()
    g_no_evidence = Goal(goal_id="g_strict", capability="vars", objective="apply")
    checker = TwinConsistencyChecker()
    result = checker.check(state, goal=g_no_evidence)
    assert result.consistent is False
    assert any("g_strict" in v and "evidence" in v for v in result.violations)
    assert result.goal_id == "g_strict"


def test_recommendation_human_review_on_evidence_violation():
    """Rule 5 violation → recommendation=human_review."""
    state = _make_state()
    g_no_evidence = Goal(goal_id="g1", capability="vars", objective="apply")
    state.current_goals.append(g_no_evidence)
    checker = TwinConsistencyChecker()
    result = checker.check(state, goal=g_no_evidence)
    assert result.consistent is False
    assert result.recommendation == "human_review"


# ────────────────────────────────────────────────────────────────────
# Singleton (2 tests)
# ────────────────────────────────────────────────────────────────────


def test_module_singleton_get_default():
    """get_default_checker() 返 singleton."""
    reset_default_checker()
    c1 = get_default_checker()
    c2 = get_default_checker()
    assert c1 is c2
    reset_default_checker()


def test_module_reset_clears_singleton():
    """reset_default_checker() 重建."""
    reset_default_checker()
    c1 = get_default_checker()
    reset_default_checker()
    c2 = get_default_checker()
    assert c1 is not c2
    reset_default_checker()


# ────────────────────────────────────────────────────────────────────
# Runtime.plan 集成 (2 tests)
# ────────────────────────────────────────────────────────────────────


def test_runtime_plan_consistent_state_runs_lca(caplog):
    """Consistent state → Runtime.plan 正常调 lca.select_intervention, 不 log warning."""
    from ecos.lca.cta_input import CTAInput
    from ecos.runtime.api import plan

    # 构造 consistent state (低 K master 避免 Rule 1, 空 current_goals 避免 Rule 5)
    state = _make_state(
        k_mastery=0.5,  # < 0.7, Rule 1 不触发
        bloom_evaluate=0.4, bloom_create=0.4,  # L6+ avg = 0.4 < 0.5, Rule 4 不触发
    )

    # 显式传 cta_input (避免 Runtime.plan 走 estimate() 创建 fresh state)
    cta_input = CTAInput(student_id="lbc_test", belief_state=state)

    # custom LCA engine (mock)
    class MockLCAEngine:
        def select_intervention(self, cta_input, audience="student"):
            return {"intervention_type": "test", "audience": audience}

    with caplog.at_level(logging.WARNING):
        result = plan(
            student_id="lbc_test",
            cta_input=cta_input,
            lca_engine=MockLCAEngine(),
        )

    # mock LCA 返 result
    assert result["intervention_type"] == "test"
    # 不应有 Twin inconsistent warning
    assert not any("Twin inconsistent" in r.message for r in caplog.records)


def test_runtime_plan_inconsistent_emits_event(caplog):
    """Inconsistent state → Runtime.plan log warning + emit goal_changed event."""
    from ecos.lca.cta_input import CTAInput
    from ecos.runtime.api import plan

    # 构造 inconsistent state (K master >= 0.7 但 Bloom L3+ < 0.5)
    state = _make_state(
        k_mastery=0.8,
        bloom_apply=0.3, bloom_analyze=0.3, bloom_evaluate=0.3, bloom_create=0.3,
    )

    cta_input = CTAInput(student_id="lbc_test", belief_state=state)

    # Mock LCA engine
    class MockLCAEngine:
        def select_intervention(self, cta_input, audience="student"):
            return {"intervention_type": "fallback"}

    # Mock event_log (in-memory)
    event_log = EventLog.in_memory()

    with caplog.at_level(logging.WARNING):
        result = plan(
            student_id="lbc_test",
            cta_input=cta_input,
            lca_engine=MockLCAEngine(),
            event_log=event_log,
        )

    # plan 仍返 result (不阻断)
    assert result["intervention_type"] == "fallback"
    # log warning
    assert any("Twin inconsistent" in r.message for r in caplog.records)
    # emit goal_changed event (load_events 需要 student_id)
    events = event_log.load_events("lbc_test")
    assert any(e.event_type == "goal_changed" for e in events)
    assert any(e.source == "twin_consistency_check" for e in events)
