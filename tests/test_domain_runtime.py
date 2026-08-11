"""v0.88.0-b: Multi-Domain 集成 Runtime + LCA 测试.

对应 12-kernel-mapping §3.1 Multi-Domain 集成:
    - BeliefState.domain_extension + set/get/has_domain_extension
    - Runtime.plan_domain_aware API
    - ExperimentDesigner domain-aware 候选池
    - Evaluator.domain_reward_adjustment

向后兼容:
    - 防御性自检 [8] 仍 hard block (set_domain_extension 是 allowlisted mutation)
    - Runtime.plan / plan_goal_aware / plan_motivation_aware 行为不变
"""

from __future__ import annotations

import pytest

from ecos.cta.belief_state import BeliefState
from ecos.domain import CareerDomain, EducationDomain, ScienceDomain
from ecos.lca.cta_input import CTAInput
from ecos.lca.evaluator import Evaluator
from ecos.lca.experiment_designer import ExperimentDesigner
from ecos.lca.intervention import InterventionType
from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig
from ecos.lca.planner import Planner, PlannerConfig
from ecos.lca.policy_learner import PolicyLearnerConfig
from ecos.runtime.api import plan_domain_aware, plan_motivation_aware, plan


# ============================================================================
# v0.88.0-b 1/14: BeliefState.domain_extension 字段
# ============================================================================

def test_belief_state_has_domain_extension_field():
    """BeliefState 必含 domain_extension 字段 (default factory)."""
    state = BeliefState(student_id="test_001")
    assert hasattr(state, "domain_extension")
    assert state.domain_extension == {}, "domain_extension 默认空 dict"


def test_belief_state_domain_extension_default_factory_per_instance():
    """domain_extension 是 default_factory dict (per instance 独立)."""
    s1 = BeliefState(student_id="test_001")
    s2 = BeliefState(student_id="test_002")
    s1.domain_extension["injected"] = "v1"
    assert "injected" not in s2.domain_extension, (
        "domain_extension 必须是 default_factory, 不能跨实例共享"
    )


def test_belief_state_set_domain_extension_allowlisted_mutation():
    """set_domain_extension 是 allowlisted mutation (防御性自检 [8] 通过)."""
    state = BeliefState(student_id="test_001")
    state.set_domain_extension("active_domain", "science")
    assert state.domain_extension["active_domain"] == "science"


def test_belief_state_set_domain_extension_invalid_key():
    """set_domain_extension: key 非字符串 _log.warning + skip (防御性自检 [1])."""
    state = BeliefState(student_id="test_001")
    state.set_domain_extension(123, "value")  # type: ignore[arg-type]
    assert 123 not in state.domain_extension, (
        "非字符串 key 应被 skip, 不写入 domain_extension"
    )


def test_belief_state_get_domain_extension_returns_value():
    """get_domain_extension(key) 返对应 value."""
    state = BeliefState(student_id="test_001")
    state.set_domain_extension("active_domain", "career")
    assert state.get_domain_extension("active_domain") == "career"


def test_belief_state_get_domain_extension_missing_returns_default():
    """get_domain_extension(missing_key, default) 返 default (防御性自检 [1])."""
    state = BeliefState(student_id="test_001")
    assert state.get_domain_extension("nonexistent") is None
    assert state.get_domain_extension("nonexistent", default="fallback") == "fallback"


def test_belief_state_has_domain_extension_true_false():
    """has_domain_extension 正确判定."""
    state = BeliefState(student_id="test_001")
    state.set_domain_extension("active_domain", "education")
    assert state.has_domain_extension("active_domain") is True
    assert state.has_domain_extension("nonexistent") is False


# ============================================================================
# v0.88.0-b 2/14: BeliefState 序列化 domain_extension
# ============================================================================

def test_belief_state_to_dict_includes_domain_extension():
    """to_dict 含 domain_extension 字段 (跟 motivation 模式一致)."""
    state = BeliefState(student_id="test_001")
    state.set_domain_extension("active_domain", "science")
    d = state.to_dict()
    assert "domain_extension" in d
    assert d["domain_extension"]["active_domain"] == "science"


def test_belief_state_from_dict_restores_domain_extension():
    """from_dict 恢复 domain_extension (跟 motivation 模式一致)."""
    state = BeliefState(student_id="test_001")
    state.set_domain_extension("active_domain", "career")
    state.set_domain_extension("extra_field", [1, 2, 3])
    d = state.to_dict()
    restored = BeliefState.from_dict(d)
    assert restored.get_domain_extension("active_domain") == "career"
    assert restored.get_domain_extension("extra_field") == [1, 2, 3]


def test_belief_state_from_dict_missing_domain_extension_empty():
    """from_dict 缺 domain_extension 字段 → 兜底空 dict (向后兼容)."""
    state = BeliefState(student_id="test_001")
    d = state.to_dict()
    # 模拟老 snapshot (没有 domain_extension 字段)
    d.pop("domain_extension", None)
    restored = BeliefState.from_dict(d)
    assert restored.domain_extension == {}


def test_belief_state_apply_snapshot_restores_domain_extension():
    """apply_snapshot 恢复 domain_extension (跟 motivation / current_goals 模式一致)."""
    state = BeliefState(student_id="test_001")
    state.set_domain_extension("active_domain", "education")
    snapshot = {
        "domain_extension": {"active_domain": "education", "k": "v"},
    }
    state.apply_snapshot(snapshot)
    assert state.get_domain_extension("active_domain") == "education"
    assert state.get_domain_extension("k") == "v"


# ============================================================================
# v0.88.0-b 3/14: ExperimentDesigner domain-aware 候选池
# ============================================================================

def test_experiment_designer_domain_aware_science_prefers_inquiry():
    """ExperimentDesigner: domain='science' 偏好 INQUIRY."""
    designer = ExperimentDesigner()
    planner = Planner(PlannerConfig())
    cta_input = CTAInput(student_id="test_001", belief_state=BeliefState(student_id="test_001"))
    plan = planner.plan(cta_input)
    candidates = designer.design(
        plan, cta_input, n_candidates=10, domain_name="science"
    )
    # n_candidates=10, i % 3 == 1 的 candidates (idx 1, 4, 7) 应是 INQUIRY
    types = [c.intervention_type for c in candidates]
    inquiry_indices = [i for i, t in enumerate(types) if t == InterventionType.INQUIRY]
    assert len(inquiry_indices) >= 3, (
        f"science Domain 应有 ≥3 个 INQUIRY candidate, got {types}"
    )


def test_experiment_designer_domain_aware_career_prefers_practice():
    """ExperimentDesigner: domain='career' 偏好 PRACTICE."""
    designer = ExperimentDesigner()
    planner = Planner(PlannerConfig())
    cta_input = CTAInput(student_id="test_001", belief_state=BeliefState(student_id="test_001"))
    plan = planner.plan(cta_input)
    candidates = designer.design(
        plan, cta_input, n_candidates=10, domain_name="career"
    )
    types = [c.intervention_type for c in candidates]
    practice_indices = [i for i, t in enumerate(types) if t == InterventionType.PRACTICE]
    assert len(practice_indices) >= 3, (
        f"career Domain 应有 ≥3 个 PRACTICE candidate, got {types}"
    )


def test_experiment_designer_domain_none_no_override():
    """ExperimentDesigner: domain_name=None 不做 override (向后兼容)."""
    designer = ExperimentDesigner()
    planner = Planner(PlannerConfig())
    cta_input = CTAInput(student_id="test_001", belief_state=BeliefState(student_id="test_001"))
    plan = planner.plan(cta_input)
    candidates_none = designer.design(
        plan, cta_input, n_candidates=10, domain_name=None
    )
    # 跟 v0.81 默认行为一致 (DEFAULT_CANDIDATE_TYPES 主导)
    types_none = [c.intervention_type for c in candidates_none]
    # 不强制断言 exact pattern, 但应能正常生成 10 candidates
    assert len(candidates_none) == 10


def test_experiment_designer_unknown_domain_no_override():
    """ExperimentDesigner: 未知 domain_name → 不 override (兜底)."""
    designer = ExperimentDesigner()
    planner = Planner(PlannerConfig())
    cta_input = CTAInput(student_id="test_001", belief_state=BeliefState(student_id="test_001"))
    plan = planner.plan(cta_input)
    # 不应 raise, 走默认 types
    candidates = designer.design(
        plan, cta_input, n_candidates=10, domain_name="unknown_domain"
    )
    assert len(candidates) == 10


# ============================================================================
# v0.88.0-b 4/14: Evaluator.domain_reward_adjustment
# ============================================================================

def test_evaluator_domain_reward_adjustment_education_factor_1_0():
    """Evaluator.domain_reward_adjustment: education → 1.0 (中性)."""
    evaluator = Evaluator()
    state = BeliefState(student_id="test_001")
    factor = evaluator.domain_reward_adjustment(state, domain_name="education")
    assert factor == 1.0


def test_evaluator_domain_reward_adjustment_science_factor_1_1():
    """Evaluator.domain_reward_adjustment: science → 1.1 (boost)."""
    evaluator = Evaluator()
    state = BeliefState(student_id="test_001")
    factor = evaluator.domain_reward_adjustment(state, domain_name="science")
    assert factor == 1.1


def test_evaluator_domain_reward_adjustment_career_factor_1_2():
    """Evaluator.domain_reward_adjustment: career → 1.2 (boost)."""
    evaluator = Evaluator()
    state = BeliefState(student_id="test_001")
    factor = evaluator.domain_reward_adjustment(state, domain_name="career")
    assert factor == 1.2


def test_evaluator_domain_reward_adjustment_unknown_returns_1_0():
    """Evaluator.domain_reward_adjustment: 未知 domain → 1.0 (兜底中性)."""
    evaluator = Evaluator()
    state = BeliefState(student_id="test_001")
    factor = evaluator.domain_reward_adjustment(state, domain_name="unknown")
    assert factor == 1.0


def test_evaluator_domain_reward_adjustment_fallback_to_state_extension():
    """Evaluator.domain_reward_adjustment: domain_name=None → 读 state.domain_extension['active_domain']."""
    evaluator = Evaluator()
    state = BeliefState(student_id="test_001")
    state.set_domain_extension("active_domain", "career")
    factor = evaluator.domain_reward_adjustment(state, domain_name=None)
    assert factor == 1.2, (
        "domain_name=None 时应 fallback to state.domain_extension['active_domain']"
    )


def test_evaluator_domain_reward_adjustment_no_domain_returns_1_0():
    """Evaluator.domain_reward_adjustment: 无 domain → 1.0 (兜底中性)."""
    evaluator = Evaluator()
    state = BeliefState(student_id="test_001")
    # 都不传
    factor = evaluator.domain_reward_adjustment(state)
    assert factor == 1.0


# ============================================================================
# v0.88.0-b 5/14: Runtime.plan_domain_aware 集成
# ============================================================================

def test_runtime_plan_domain_aware_sets_active_domain():
    """Runtime.plan_domain_aware 自动设 active_domain 到 state (allowlisted mutation)."""
    state = BeliefState(student_id="test_001")
    cta_input = CTAInput(student_id="test_001", belief_state=state)
    lca_engine = LCAEngine(LCAEngineConfig(policy_learner_config=PolicyLearnerConfig()))
    try:
        plan_domain_aware(
            "test_001",
            domain_name="science",
            lca_engine=lca_engine,
            cta_input=cta_input,
        )
        assert state.get_domain_extension("active_domain") == "science", (
            "plan_domain_aware 应自动 set domain_extension['active_domain']"
        )
    finally:
        pass  # cleanup


def test_runtime_plan_domain_aware_returns_lca_result():
    """Runtime.plan_domain_aware 返 LCAResult (跟 plan 同类型)."""
    state = BeliefState(student_id="test_001")
    cta_input = CTAInput(student_id="test_001", belief_state=state)
    lca_engine = LCAEngine(LCAEngineConfig(policy_learner_config=PolicyLearnerConfig()))
    result = plan_domain_aware(
        "test_001",
        domain_name="career",
        lca_engine=lca_engine,
        cta_input=cta_input,
    )
    # LCAResult 含 intervention + rationale + expected_gain
    assert hasattr(result, "intervention")
    assert hasattr(result, "expected_gain")


def test_runtime_plan_domain_aware_falls_back_to_state_extension():
    """Runtime.plan_domain_aware 不传 domain_name → fallback 到 state.domain_extension."""
    state = BeliefState(student_id="test_001")
    state.set_domain_extension("active_domain", "science")
    cta_input = CTAInput(student_id="test_001", belief_state=state)
    lca_engine = LCAEngine(LCAEngineConfig(policy_learner_config=PolicyLearnerConfig()))
    # 不传 domain_name kwarg, 应 fallback
    result = plan_domain_aware(
        "test_001",
        lca_engine=lca_engine,
        cta_input=cta_input,
    )
    # active_domain 应保持原值 (science)
    assert state.get_domain_extension("active_domain") == "science"


def test_runtime_plan_domain_aware_does_not_break_plan():
    """Runtime.plan 不受 plan_domain_aware 影响 (向后兼容)."""
    state = BeliefState(student_id="test_001")
    cta_input = CTAInput(student_id="test_001", belief_state=state)
    lca_engine = LCAEngine(LCAEngineConfig(policy_learner_config=PolicyLearnerConfig()))
    result = plan(
        "test_001",
        lca_engine=lca_engine,
        cta_input=cta_input,
    )
    # plan 行为不变, 应 work
    assert hasattr(result, "intervention")


def test_runtime_plan_domain_aware_does_not_break_motivation_aware():
    """Runtime.plan_motivation_aware 不受 plan_domain_aware 影响 (向后兼容)."""
    state = BeliefState(student_id="test_001")
    cta_input = CTAInput(student_id="test_001", belief_state=state)
    lca_engine = LCAEngine(LCAEngineConfig(policy_learner_config=PolicyLearnerConfig()))
    result = plan_motivation_aware(
        "test_001",
        lca_engine=lca_engine,
        cta_input=cta_input,
    )
    # plan_motivation_aware 行为不变
    assert hasattr(result, "intervention")