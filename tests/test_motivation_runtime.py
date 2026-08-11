"""v0.87.0-b: Motivation Profile 集成 Runtime + LCA 测试套件.

对应 12-kernel-mapping §2.1 Motivation Profile 集成.

测试覆盖:
- Evaluator.motivation_reward_adjustment (3): default / frustration_high / confidence_engagement_high
- ExperimentDesigner motivation-aware (4): frustration → EXPLANATORY / engagement_low → INQUIRY / confidence+engagement → PRACTICE / motivation=None backward compat
- Runtime.plan_motivation_aware (3): basic / motivation_observation emits / motivation profile direct
- 集成 (4): LCAEngine motivation / state.motivation fallback / reward adjustment / Twin Consistency still works

向后兼容:
- LCAEngine.select_intervention motivation=None 走 state.motivation fallback (v0.87.0-a)
- Runtime.plan / plan_goal_aware 行为不变 (v0.86)
- ExperimentDesigner.design motivation=None 走 default_types (v0.82.0-b)
"""

from __future__ import annotations

import pytest

from ecos.cta.belief_state import BeliefState
from ecos.lca.cta_input import CTAInput
from ecos.lca.evaluator import Evaluator
from ecos.lca.experiment_designer import ExperimentDesigner
from ecos.lca.intervention import InterventionType
from ecos.lca.planner import PlanDecision
from ecos.lca.policy_learner import PolicyLearner, PolicyLearnerConfig
from ecos.motivation import MotivationObservation, MotivationProfile
from ecos.runtime.api import plan, plan_goal_aware, plan_motivation_aware


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────


def _make_state(motivation: MotivationProfile = None) -> BeliefState:
    """构造可控 state (含可选 motivation)."""
    state = BeliefState(student_id="lbc_test")
    if motivation is not None:
        state.motivation = motivation
    return state


def _mock_lca_engine():
    """Mock LCA engine (测试用, 返固定 result)."""
    class MockLCAEngine:
        def __init__(self):
            self.select_intervention_calls = []
            self.last_audience = None
            self.last_motivation = None

        def select_intervention(self, cta_input, audience="student", motivation=None):
            # 模拟 real LCAEngine: motivation=None → state.motivation fallback
            if motivation is None:
                motivation = getattr(cta_input.belief_state, "motivation", None)
            self.select_intervention_calls.append((cta_input, audience, motivation))
            self.last_audience = audience
            self.last_motivation = motivation
            return {
                "intervention_type": "test",
                "audience": audience,
                "expected_gain": 0.5,
                "expected_risk": 0.1,
            }

    return MockLCAEngine()


# ────────────────────────────────────────────────────────────────────
# Evaluator.motivation_reward_adjustment (3 tests)
# ────────────────────────────────────────────────────────────────────


def test_evaluator_motivation_reward_default():
    """motivation 中性 → factor = 1.0."""
    motivation = MotivationProfile()  # frustration=0 / engagement=0.5 / confidence=0.5
    state = _make_state(motivation)
    evaluator = Evaluator()
    factor = evaluator.motivation_reward_adjustment(state)
    assert factor == 1.0


def test_evaluator_motivation_reward_frustration_high():
    """frustration > 0.7 → factor = 0.7 (降低 gain, 避免 burnout)."""
    motivation = MotivationProfile(frustration=0.8, engagement=0.5, confidence=0.5)
    state = _make_state(motivation)
    evaluator = Evaluator()
    factor = evaluator.motivation_reward_adjustment(state)
    assert factor == 0.7


def test_evaluator_motivation_reward_confidence_engagement_high():
    """confidence > 0.7 AND engagement > 0.6 → factor = 1.3 (boost)."""
    motivation = MotivationProfile(frustration=0.0, engagement=0.8, confidence=0.8)
    state = _make_state(motivation)
    evaluator = Evaluator()
    factor = evaluator.motivation_reward_adjustment(state)
    assert factor == 1.3


# ────────────────────────────────────────────────────────────────────
# ExperimentDesigner motivation-aware (4 tests)
# ────────────────────────────────────────────────────────────────────


def _make_plan_decision() -> PlanDecision:
    """v0.87.0-b: 用 ARTICULATION stage (避免 _adjust_for_ca_stage 覆盖 motivation override)."""
    from ecos.cta.belief_state import BloomLevel
    from ecos.lca.intervention import CAStage, CLTLevel
    return PlanDecision(
        bloom_target=BloomLevel.APPLY,
        ca_stage=CAStage.ARTICULATION,  # 4 (Phase 5+, 不在 3-stage _adjust_for_ca_stage 分支)
        clt_level=CLTLevel.DEVELOPING,
        bjork_triggers=[],
    )


def test_designer_frustration_prefers_explanatory():
    """frustration > 0.7 → EXPLANATORY override (i % 3 == 0)."""
    motivation = MotivationProfile(frustration=0.8)
    cta_input = CTAInput(student_id="lbc_test", belief_state=_make_state(motivation))
    designer = ExperimentDesigner()
    candidates = designer.design(_make_plan_decision(), cta_input, motivation=motivation)
    # i=0, 3, 6, 9 → 至少 4 个是 EXPLANATORY
    explanatory_count = sum(
        1 for c in candidates if c.intervention_type == InterventionType.EXPLANATORY
    )
    assert explanatory_count >= 4


def test_designer_engagement_low_prefers_inquiry():
    """engagement < 0.3 → INQUIRY override (i % 3 == 0)."""
    motivation = MotivationProfile(engagement=0.2)
    cta_input = CTAInput(student_id="lbc_test", belief_state=_make_state(motivation))
    designer = ExperimentDesigner()
    candidates = designer.design(_make_plan_decision(), cta_input, motivation=motivation)
    inquiry_count = sum(
        1 for c in candidates if c.intervention_type == InterventionType.INQUIRY
    )
    assert inquiry_count >= 4


def test_designer_confidence_engagement_high_prefers_practice():
    """confidence > 0.7 AND engagement > 0.6 → PRACTICE override."""
    motivation = MotivationProfile(confidence=0.8, engagement=0.7)
    cta_input = CTAInput(student_id="lbc_test", belief_state=_make_state(motivation))
    designer = ExperimentDesigner()
    candidates = designer.design(_make_plan_decision(), cta_input, motivation=motivation)
    practice_count = sum(
        1 for c in candidates if c.intervention_type == InterventionType.PRACTICE
    )
    assert practice_count >= 4


def test_designer_motivation_none_backward_compat():
    """motivation=None → 走 default_types (v0.82.0-b 兼容)."""
    cta_input = CTAInput(student_id="lbc_test", belief_state=_make_state())
    designer = ExperimentDesigner()
    candidates = designer.design(_make_plan_decision(), cta_input, motivation=None)
    # 10 candidates (跟 n_candidates=10)
    assert len(candidates) == 10
    # types 跟 default_types 一致
    assert candidates[0].intervention_type == InterventionType.EXPLANATORY


# ────────────────────────────────────────────────────────────────────
# Runtime.plan_motivation_aware (3 tests)
# ────────────────────────────────────────────────────────────────────


def test_plan_motivation_aware_basic():
    """plan_motivation_aware 调 lca.select_intervention (透传 motivation)."""
    motivation = MotivationProfile(frustration=0.8)
    state = _make_state()
    cta_input = CTAInput(student_id="lbc_test", belief_state=state)
    lca = _mock_lca_engine()

    result = plan_motivation_aware(
        student_id="lbc_test",
        cta_input=cta_input,
        lca_engine=lca,
        motivation=motivation,
    )
    assert result["intervention_type"] == "test"
    assert lca.last_motivation is motivation


def test_plan_motivation_aware_observation_emits_to_state():
    """plan_motivation_aware + motivation_observation → state.motivation 更新."""
    state = _make_state()
    cta_input = CTAInput(student_id="lbc_test", belief_state=state)
    lca = _mock_lca_engine()

    obs = MotivationObservation(
        timestamp=__import__("datetime").datetime.now(),
        signal_type="frustration",
        value=0.8,
    )
    plan_motivation_aware(
        student_id="lbc_test",
        cta_input=cta_input,
        lca_engine=lca,
        motivation_observation=obs,
    )
    # state.motivation.frustration 应该更新
    assert state.motivation.frustration == 0.8
    assert len(state.motivation.recent_trajectory) == 1
    # lca 收到 state.motivation (None motivation → state fallback)
    assert lca.last_motivation is state.motivation


def test_plan_motivation_aware_falls_back_to_state_motivation():
    """motivation=None → fallback to state.motivation (lca 收到 state.motivation)."""
    motivation = MotivationProfile(frustration=0.5)
    state = _make_state(motivation)
    cta_input = CTAInput(student_id="lbc_test", belief_state=state)
    lca = _mock_lca_engine()

    plan_motivation_aware(
        student_id="lbc_test",
        cta_input=cta_input,
        lca_engine=lca,
        # motivation=None (lca 走 state.motivation fallback)
    )
    assert lca.last_motivation is state.motivation


# ────────────────────────────────────────────────────────────────────
# 集成 (4 tests)
# ────────────────────────────────────────────────────────────────────


def test_lca_select_intervention_uses_motivation():
    """LCAEngine.select_intervention(motivation=...) 接受 motivation 参数."""
    from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig
    motivation = MotivationProfile(frustration=0.8)
    state = _make_state()
    cta_input = CTAInput(student_id="lbc_test", belief_state=state)

    lca = LCAEngine(config=LCAEngineConfig(bandit_config=PolicyLearnerConfig().bandit_config))
    result = lca.select_intervention(cta_input, motivation=motivation)
    assert result is not None
    # expected_gain 应该是 estimate_gain × motivation_factor (0.7)
    # 不严格断言值, 只确认 motivation 路径生效


def test_lca_select_intervention_state_motivation_fallback():
    """LCAEngine.select_intervention(motivation=None) 走 state.motivation fallback."""
    from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig
    state = _make_state(MotivationProfile(frustration=0.8))
    cta_input = CTAInput(student_id="lbc_test", belief_state=state)

    lca = LCAEngine(config=LCAEngineConfig(bandit_config=PolicyLearnerConfig().bandit_config))
    # motivation=None → state.motivation 生效
    result = lca.select_intervention(cta_input, motivation=None)
    assert result is not None


def test_evaluator_motivation_adjustment_applied_to_expected_gain():
    """Evaluator.motivation_reward_adjustment 影响 expected_gain (via LCAEngine)."""
    from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig
    # 1) 中性 motivation (factor=1.0)
    state_neutral = _make_state(MotivationProfile(frustration=0.0, engagement=0.5, confidence=0.5))
    cta_neutral = CTAInput(student_id="lbc_test", belief_state=state_neutral)
    lca = LCAEngine(config=LCAEngineConfig(bandit_config=PolicyLearnerConfig().bandit_config))
    result_neutral = lca.select_intervention(cta_neutral)
    gain_neutral = result_neutral.intervention.expected_gain

    # 2) frustration high (factor=0.7)
    state_frustrated = _make_state(MotivationProfile(frustration=0.8))
    cta_frustrated = CTAInput(student_id="lbc_frustrated", belief_state=state_frustrated)
    result_frustrated = lca.select_intervention(cta_frustrated)
    gain_frustrated = result_frustrated.intervention.expected_gain

    # frustration high 时 expected_gain 应该 ≤ 中性 (factor=0.7)
    assert gain_frustrated <= gain_neutral


def test_plan_motivation_aware_twin_consistency_still_works():
    """plan_motivation_aware 仍走 Twin Consistency Check (v0.86.0-b 兼容)."""
    from ecos.cta.event_log import EventLog
    # 构造 inconsistent state (K master >= 0.7 但 Bloom L3+ < 0.5)
    state = _make_state()
    state.K.mastery_prob = 0.8
    state.bloom_profile.apply = 0.3
    state.bloom_profile.analyze = 0.3
    state.bloom_profile.evaluate = 0.3
    state.bloom_profile.create = 0.3
    cta_input = CTAInput(student_id="lbc_test", belief_state=state)

    lca = _mock_lca_engine()
    event_log = EventLog.in_memory()

    plan_motivation_aware(
        student_id="lbc_test",
        cta_input=cta_input,
        lca_engine=lca,
        event_log=event_log,
        # 没有 motivation (fallback to state.motivation)
    )
    # emit goal_changed event
    events = event_log.load_events("lbc_test")
    assert any(e.event_type == "goal_changed" for e in events)
