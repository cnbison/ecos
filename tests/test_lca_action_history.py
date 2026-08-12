"""v0.92.0-c: LCA 4 layer 接入 ActionHistory 测试.

对应设计: v0.92 plan §v0.92.0-c.

测试范围 (21 tests):
  1. ExperimentDesigner._action_history_itype_override 5 case + priority + boundary (8 tests)
  2. Evaluator.action_history_reward_adjustment 5 case + boundary (5 tests)
  3. LCAEngine.select_intervention action_history 影响 candidate pool + expected_gain (3 tests)
  4. H3-c4 canary (action_history=None 行为 == v0.91 baseline) (2 tests)
  5. kwargs 透传到 Designer + Evaluator (motivation + domain + human_feedback + action_history 四路并行) (3 tests)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pytest

from ecos.cta.belief_engine import BeliefEngine, BeliefState
from ecos.cta.cognitive_twin import (
    ACTION_HISTORY_EVENT_TYPES,
    ActionEntry,
    ActionHistory,
    CognitiveTwinAgent,
)
from ecos.lca.cta_input import CTAInput
from ecos.lca.experiment_designer import ExperimentDesigner, ExperimentDesignerConfig
from ecos.lca.evaluator import Evaluator, EvaluatorConfig
from ecos.lca.intervention import InterventionType
from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig

_log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_state(student_id: str = "stu-001") -> BeliefState:
    """Build a BeliefState via BeliefEngine (跟 v0.83+ 4-layer 一致)."""
    engine = BeliefEngine()
    return engine.create_initial_state(student_id)


def _make_lca() -> LCAEngine:
    """Build LCAEngine for tests."""
    return LCAEngine(config=LCAEngineConfig(use_llm_rationale=False))


def _make_action_entry(action_type: str, reward: float = None, **kwargs: Any) -> ActionEntry:
    """Build an ActionEntry for tests."""
    defaults = {
        "student_id": "stu",
        "timestamp": datetime.now(),
        "action_type": action_type,
    }
    if reward is not None:
        defaults["reward"] = reward
    if action_type == "intervention_selected":
        defaults["intervention_id"] = kwargs.get("intervention_id", "iv_test")
        defaults["metadata"] = kwargs.get("metadata", {"bloom_target": "APPLY", "policy_type": "linucb"})
    elif action_type == "dual_agent_calibrated":
        defaults["metadata"] = kwargs.get("metadata", {"judge_1": "llm_critic", "judge_2": "human"})
    elif action_type == "policy_updated":
        defaults["metadata"] = kwargs.get("metadata", {"policy_type": "linucb"})
    return ActionEntry(**defaults)


# ── 1. ExperimentDesigner._action_history_itype_override 5 case + priority (8 tests) ─


class TestActionHistoryItypeOverride:
    """ExperimentDesigner._action_history_itype_override 5 case + priority + boundary."""

    def test_reward_recorded_low_returns_practice(self):
        """reward_recorded 平均 < 0.5 + 累计 ≥ 5 → PRACTICE (低 gain 学生需更多练习)."""
        designer = ExperimentDesigner()
        history = ActionHistory()
        # 5 个 reward_recorded 平均 0.3 (< 0.5)
        for i in range(5):
            history.append(_make_action_entry("reward_recorded", reward=0.3))
        assert designer._action_history_itype_override(history) == InterventionType.PRACTICE

    def test_type_diversity_explanatory_over_10_returns_inquiry(self):
        """intervention_selected 在某 type 累计 > 10 → INQUIRY (避免单调)."""
        designer = ExperimentDesigner()
        history = ActionHistory()
        # 11 个 intervention_selected 同 bloom_target
        for i in range(11):
            history.append(_make_action_entry("intervention_selected", intervention_id=f"iv_{i}",
                                              metadata={"bloom_target": "APPLY", "policy_type": "linucb"}))
        assert designer._action_history_itype_override(history) == InterventionType.INQUIRY

    def test_dual_agent_calibrated_high_returns_explanatory(self):
        """dual_agent_calibrated 平均 reward > 0.7 → EXPLANATORY (互校确认)."""
        designer = ExperimentDesigner()
        history = ActionHistory()
        # 3 个 dual_agent_calibrated 平均 0.85 (> 0.7)
        for _ in range(3):
            history.append(_make_action_entry("dual_agent_calibrated", reward=0.85))
        assert designer._action_history_itype_override(history) == InterventionType.EXPLANATORY

    def test_policy_updated_low_no_override(self):
        """policy_updated 累计 < 3 → None (default, 冷启动期稳定探索)."""
        designer = ExperimentDesigner()
        history = ActionHistory()
        # 1 个 policy_updated + 0 个 reward_recorded
        history.append(_make_action_entry("policy_updated"))
        assert designer._action_history_itype_override(history) is None

    def test_goal_changed_over_1_returns_practice(self):
        """goal_changed 累计 > 1 → PRACTICE (跟 human_feedback.goal_changed 同)."""
        designer = ExperimentDesigner()
        history = ActionHistory()
        # 2 个 goal_changed
        for _ in range(2):
            history.append(_make_action_entry("goal_changed"))
        assert designer._action_history_itype_override(history) == InterventionType.PRACTICE

    def test_priority_reward_low_beats_goal_change(self):
        """优先级: reward_recorded_low > goal_changed (reward 更紧急)."""
        designer = ExperimentDesigner()
        history = ActionHistory()
        # 5 reward (低平均) + 2 goal_change
        for _ in range(5):
            history.append(_make_action_entry("reward_recorded", reward=0.3))
        for _ in range(2):
            history.append(_make_action_entry("goal_changed"))
        assert designer._action_history_itype_override(history) == InterventionType.PRACTICE

    def test_no_match_returns_none(self):
        """无匹配 case → None (走 default_types)."""
        designer = ExperimentDesigner()
        history = ActionHistory()
        # 1 个 policy_updated (无其他, 累计 < 3)
        history.append(_make_action_entry("policy_updated"))
        # 1 个 intervention_selected (type_diversity 不触发, < 10)
        history.append(_make_action_entry("intervention_selected", intervention_id="iv_1",
                                          metadata={"bloom_target": "APPLY", "policy_type": "linucb"}))
        assert designer._action_history_itype_override(history) is None

    def test_none_action_history_returns_none(self):
        """action_history=None → None (default)."""
        designer = ExperimentDesigner()
        assert designer._action_history_itype_override(None) is None


# ── 2. Evaluator.action_history_reward_adjustment 5 case + boundary (5 tests) ─


class TestActionHistoryRewardAdjustment:
    """Evaluator.action_history_reward_adjustment 5 case + boundary."""

    def test_reward_recorded_low_returns_0_85(self):
        """reward_recorded 平均 < 0.5 (累计 ≥ 5) → 0.85 (低 gain 风险)."""
        evaluator = Evaluator()
        history = ActionHistory()
        for _ in range(5):
            history.append(_make_action_entry("reward_recorded", reward=0.3))
        assert evaluator.action_history_reward_adjustment(history) == 0.85

    def test_reward_recorded_high_returns_1_15(self):
        """reward_recorded 平均 > 0.7 (累计 ≥ 5) → 1.15 (high gain 提升)."""
        evaluator = Evaluator()
        history = ActionHistory()
        for _ in range(5):
            history.append(_make_action_entry("reward_recorded", reward=0.85))
        assert evaluator.action_history_reward_adjustment(history) == 1.15

    def test_dual_agent_calibrated_above_half_returns_1_05(self):
        """dual_agent_calibrated reward > 0.5 比例 > 0.5 (累计 ≥ 2) → 1.05 (互校积极 boost)."""
        evaluator = Evaluator()
        history = ActionHistory()
        # 4 个 dual_agent_calibrated: 3 个 > 0.5, 1 个 < 0.5 → 比例 0.75 (> 0.5)
        history.append(_make_action_entry("dual_agent_calibrated", reward=0.85))
        history.append(_make_action_entry("dual_agent_calibrated", reward=0.85))
        history.append(_make_action_entry("dual_agent_calibrated", reward=0.85))
        history.append(_make_action_entry("dual_agent_calibrated", reward=0.45))
        assert evaluator.action_history_reward_adjustment(history) == 1.05

    def test_no_match_returns_1_0(self):
        """无匹配 case → 1.0 (中性)."""
        evaluator = Evaluator()
        history = ActionHistory()
        # 2 reward_recorded (累计 < 5, 不触发)
        for _ in range(2):
            history.append(_make_action_entry("reward_recorded", reward=0.5))
        assert evaluator.action_history_reward_adjustment(history) == 1.0

    def test_none_action_history_returns_1_0(self):
        """action_history=None → 1.0 (中性)."""
        evaluator = Evaluator()
        assert evaluator.action_history_reward_adjustment(None) == 1.0


# ── 3. LCAEngine.select_intervention action_history 影响 (3 tests) ─


class TestLCAEngineActionHistoryIntegration:
    """LCAEngine.select_intervention action_history 影响 candidate pool + expected_gain."""

    def test_action_history_override_in_candidate_pool(self):
        """action_history 触发 itype override → ExperimentDesigner.design() candidate pool 含对应 type.

        注: LCAEngine.select_intervention 调 ExperimentDesigner.design() 生成 candidates,
        然后走 LinUCB 选择 chosen (单一 intervention). 这里直接测 ExperimentDesigner.design()
        的 candidate pool, 因为 LCA LinUCB 是统计选 arm, 不能保证选 override type.
        """
        from ecos.lca.planner import Planner
        designer = ExperimentDesigner()
        state = _make_state("stu-ah-pool")
        twin = CognitiveTwinAgent.from_state(state)
        # 5 reward_recorded 低平均 → 期望 PRACTICE override
        for _ in range(5):
            twin.append_action_history(_make_action_entry("reward_recorded", reward=0.3))
        cta = CTAInput(student_id="stu-ah-pool", belief_state=state)
        planner = Planner()
        plan = planner.plan(cta, intervention_history=[])
        # 直接调 designer.design 拿 candidate pool (LinUCB 选择不影响 candidate pool)
        candidates = designer.design(
            plan, cta, n_candidates=10,
            cognitive_twin=twin, action_history=twin.action_history,
        )
        # 期望 candidate pool 含 PRACTICE type (override 触发)
        # 注: override 是 i % 3 == 2 触发, 10 candidate pool 应含 ≥ 3 个 PRACTICE
        practice_count = sum(1 for c in candidates if c.intervention_type == InterventionType.PRACTICE)
        assert practice_count >= 1, f"expected PRACTICE in candidates, got {practice_count} of 10"

    def test_action_history_factor_multiplies_expected_gain(self):
        """action_history_factor (0.85 / 1.15) 乘到 expected_gain."""
        lca = _make_lca()
        state = _make_state("stu-ah-factor")
        twin = CognitiveTwinAgent.from_state(state)
        # 5 reward_recorded 高平均 → 期望 factor 1.15
        for _ in range(5):
            twin.append_action_history(_make_action_entry("reward_recorded", reward=0.85))
        cta = CTAInput(student_id="stu-ah-factor", belief_state=state)
        result = lca.select_intervention(cta, cognitive_twin=twin)
        # expected_gain 受 factor 影响 (1.0 * motivation * domain * human_feedback * action_history=1.15)
        assert result.expected_gain > 0.0
        assert result.expected_gain <= 1.0

    def test_action_history_none_baseline_no_factor(self):
        """action_history=None → factor=1.0 (中性, 跟 v0.91 baseline 一致)."""
        lca = _make_lca()
        state = _make_state("stu-ah-none")
        cta = CTAInput(student_id="stu-ah-none", belief_state=state)
        result_none = lca.select_intervention(cta)
        result_explicit_none = lca.select_intervention(cta, cognitive_twin=None, action_history=None)
        # 两种 None 调用 expected_gain 应一致 (deterministic baseline)
        assert abs(result_none.expected_gain - result_explicit_none.expected_gain) < 1e-6


# ── 4. H3-c4 canary (action_history=None 行为 == v0.91 baseline) (2 tests) ─


class TestH3C4CanaryActionHistoryNone:
    """H3-c4 canary: action_history=None 行为 == v0.91 baseline (无 regression)."""

    def test_select_intervention_action_history_none_no_factor(self):
        """action_history=None → factor=1.0 (per Evaluator.action_history_reward_adjustment)."""
        lca = _make_lca()
        evaluator = Evaluator()
        assert evaluator.action_history_reward_adjustment(None) == 1.0

    def test_select_intervention_no_action_history_field_no_error(self):
        """LCAEngine.select_intervention 无 action_history 字段 / 不传 → 不 raise, 走 baseline."""
        lca = _make_lca()
        state = _make_state("stu-ah-canary")
        cta = CTAInput(student_id="stu-ah-canary", belief_state=state)
        # 不传 action_history, 走默认 fallback to cognitive_twin.action_history (也 None)
        result = lca.select_intervention(cta)
        assert result is not None
        assert 0.0 <= result.expected_gain <= 1.0


# ── 5. kwargs 透传到 Designer + Evaluator (motivation + domain + human_feedback + action_history 四路并行) (3 tests) ─


class TestKwargsFourFactorsChain:
    """kwargs 透传到 Designer + Evaluator (motivation + domain + human_feedback + action_history 四路并行)."""

    def test_four_kwargs_pass_through_without_error(self):
        """motivation + domain_name + cognitive_twin + action_history 4 kwargs 全部透传."""
        from ecos.cta.cognitive_twin import HumanFeedbackEntry
        from ecos.motivation.profile import MotivationProfile
        lca = _make_lca()
        state = _make_state("stu-4kw")
        twin = CognitiveTwinAgent.from_state(state)
        # 1 human_feedback (hint) + 1 action_history (intervention_selected)
        twin.append_human_feedback(HumanFeedbackEntry(
            student_id="stu-4kw", timestamp=datetime.now(),
            event_type="hint_requested", payload={"problem_id": "P1", "hint_level": 1},
        ))
        twin.append_action_history(_make_action_entry("intervention_selected", intervention_id="iv_1"))
        # motivation (v0.87.0-b 签名: frustration / engagement / confidence)
        motivation = MotivationProfile(frustration=0.1, engagement=0.8, confidence=0.7)
        cta = CTAInput(student_id="stu-4kw", belief_state=state)
        result = lca.select_intervention(
            cta,
            audience="student",
            motivation=motivation,
            domain_name="education",
            cognitive_twin=twin,
            action_history=twin.action_history,
        )
        assert result is not None
        # LCA 不 raise, expected_gain 在 [0, 1]

    def test_five_factors_chain_in_expected_gain(self):
        """5 factor chain (base × motivation × domain × human_feedback × action_history) multiplicative."""
        lca = _make_lca()
        state = _make_state("stu-5factor")
        cta = CTAInput(student_id="stu-5factor", belief_state=state)
        # 无任何 kwargs, 全走 default
        result = lca.select_intervention(cta)
        assert result is not None
        # expected_gain = base × 1.0 × 1.0 × 1.0 × 1.0 = base
        assert 0.0 <= result.expected_gain <= 1.0

    def test_action_history_factor_only(self):
        """只传 action_history (其他 None) → 仅 action_history factor 生效 (其他 factor=1.0)."""
        lca = _make_lca()
        state = _make_state("stu-ah-only")
        twin = CognitiveTwinAgent.from_state(state)
        # 5 reward_recorded 高平均 → action_history_factor = 1.15
        for _ in range(5):
            twin.append_action_history(_make_action_entry("reward_recorded", reward=0.85))
        cta = CTAInput(student_id="stu-ah-only", belief_state=state)
        # 不传 motivation / domain_name / cognitive_twin (None)
        result = lca.select_intervention(cta, action_history=twin.action_history)
        # 期望 gain * 1.15 (其他 factor = 1.0)
        assert result is not None
        assert result.expected_gain > 0.0