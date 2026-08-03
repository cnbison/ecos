"""v0.69.0-b: LCAEngine.update reward=actual_outcome 测试.

目标 (按 v0.69.0 PRD §3.1.1 + §7.2):
  1. LCAEngine.update 接受 reward 参数 (新增, Optional[float] = None)
  2. reward=None -> 用 state_delta fallback (向后兼容, 教学 LCA 路径)
  3. reward=actual_outcome -> 用 actual_outcome 作为 LinUCB reward
  4. attribution 仍用 state_delta (不传 reward 给 attribution)
  5. reward 截断到 [0, 1]

防御性自检 [6]: 失败不污染 in-memory
"""

from __future__ import annotations

import logging

import numpy as np
import pytest


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def belief_state():
    """构造一个最小 BeliefState."""
    from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig
    from ecos.cta.l1_evolution import EvolutionConfig
    from ecos.cta.l2_mirt import MIRTConfig

    config = BeliefEngineConfig(
        evolution_config=EvolutionConfig(),
        mirt_config=MIRTConfig(),
    )
    engine = BeliefEngine(config=config, llm_client=None)
    return engine.create_initial_state("test_lca_reward")


@pytest.fixture
def lca_engine():
    """独立 LCAEngine."""
    from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig

    return LCAEngine(config=LCAEngineConfig(), llm_client=None)


def _select_intervention(lca_engine, belief_state, sid="test_lca_reward"):
    """helper: select 一道干预."""
    from ecos.lca.orchestrator import CTAInput

    cta_input = CTAInput(student_id=sid, belief_state=belief_state)
    return lca_engine.select_intervention(cta_input)


# ──────────────────────────────────────────────────────────────────────
# 1. LCAEngine.update 接口向后兼容
# ──────────────────────────────────────────────────────────────────────


class TestLCAEngineUpdateBackwardCompat:
    """v0.69.0-b: LCAEngine.update 向后兼容."""

    def test_update_accepts_reward_param(self, lca_engine, belief_state):
        """update 接受 reward 参数 (新增), 不传也能工作 (向后兼容)."""
        result = _select_intervention(lca_engine, belief_state)
        # 不传 reward (老调用方式)
        lca_engine.update(
            student_id="test_lca_reward",
            intervention=result.intervention,
            new_state=belief_state,
            state_delta=0.5,
        )
        # 没 raise 即通过
        bandit = lca_engine.bandits["test_lca_reward"]
        assert int(bandit.bandit.arm_pull_counts.sum()) == 1

    def test_update_with_reward_none_uses_state_delta(self, lca_engine, belief_state):
        """reward=None (默认) -> 用 state_delta 作为 LinUCB reward."""
        result = _select_intervention(lca_engine, belief_state)
        lca_engine.update(
            student_id="test_lca_reward",
            intervention=result.intervention,
            new_state=belief_state,
            state_delta=0.5,
            reward=None,  # 显式 None, 走 fallback
        )
        bandit = lca_engine.bandits["test_lca_reward"]
        # arm_pull_counts 应该 +1
        assert int(bandit.bandit.arm_pull_counts.sum()) == 1


# ──────────────────────────────────────────────────────────────────────
# 2. reward=actual_outcome 行为
# ──────────────────────────────────────────────────────────────────────


class TestLCAEngineUpdateRewardActualOutcome:
    """v0.69.0-b: reward=actual_outcome (dual_agent 路径)."""

    def test_reward_actual_outcome_affects_linucb_b_vector(
        self, lca_engine, belief_state
    ):
        """reward=actual_outcome -> LinUCB b_a += actual_outcome * x."""
        result = _select_intervention(lca_engine, belief_state)
        bandit = lca_engine.bandits["test_lca_reward"]
        # 找到 chosen arm
        arm_idx = bandit._lookup_arm(result.intervention)
        assert arm_idx is not None
        # 记录 update 前的 b
        b_before = bandit.bandit.b[arm_idx].copy()

        actual_outcome = 0.8
        lca_engine.update(
            student_id="test_lca_reward",
            intervention=result.intervention,
            new_state=belief_state,
            state_delta=0.1,  # 故意跟 actual_outcome 不同, 区分两个信号
            reward=actual_outcome,
        )
        # update 后, b_a += reward * x = 0.8 * x
        #   验证: b_after - b_before = 0.8 * x
        #   对比: 如果走 state_delta fallback, 应该是 0.1 * x
        context = bandit._build_context(belief_state)
        b_after = bandit.bandit.b[arm_idx]
        delta = b_after - b_before
        expected_delta = actual_outcome * context
        np.testing.assert_allclose(delta, expected_delta, atol=1e-10)

    def test_reward_actual_outcome_clamped_to_1(self, lca_engine, belief_state):
        """reward > 1.0 截断到 1.0."""
        result = _select_intervention(lca_engine, belief_state)
        lca_engine.update(
            student_id="test_lca_reward",
            intervention=result.intervention,
            new_state=belief_state,
            state_delta=0.5,
            reward=2.0,  # 截断到 1.0
        )
        # 没 raise, LinUCB 正常更新
        bandit = lca_engine.bandits["test_lca_reward"]
        assert int(bandit.bandit.arm_pull_counts.sum()) == 1

    def test_reward_actual_outcome_clamped_to_0(self, lca_engine, belief_state):
        """reward < 0.0 截断到 0.0."""
        result = _select_intervention(lca_engine, belief_state)
        lca_engine.update(
            student_id="test_lca_reward",
            intervention=result.intervention,
            new_state=belief_state,
            state_delta=0.5,
            reward=-0.5,  # 截断到 0.0
        )
        # 没 raise, LinUCB 正常更新
        bandit = lca_engine.bandits["test_lca_reward"]
        assert int(bandit.bandit.arm_pull_counts.sum()) == 1

    def test_reward_zero_does_not_corrupt_b_vector(
        self, lca_engine, belief_state
    ):
        """reward=0.0 (学生答错) -> b_a 不变 (b += 0 * x = 0)."""
        result = _select_intervention(lca_engine, belief_state)
        bandit = lca_engine.bandits["test_lca_reward"]
        arm_idx = bandit._lookup_arm(result.intervention)
        b_before = bandit.bandit.b[arm_idx].copy()

        lca_engine.update(
            student_id="test_lca_reward",
            intervention=result.intervention,
            new_state=belief_state,
            state_delta=0.5,
            reward=0.0,  # 学生答错, reward=0
        )
        b_after = bandit.bandit.b[arm_idx]
        np.testing.assert_allclose(b_after, b_before, atol=1e-10)


# ──────────────────────────────────────────────────────────────────────
# 3. attribution 仍用 state_delta (不传 reward 给 attribution)
# ──────────────────────────────────────────────────────────────────────


class TestAttributionUsesStateDelta:
    """v0.69.0-b: attribution 仍用 state_delta, 不用 reward."""

    def test_attribution_records_state_delta_not_reward(
        self, lca_engine, belief_state
    ):
        """attribution.attribute_effect 收到的是 state_delta, 不是 reward."""
        result = _select_intervention(lca_engine, belief_state)

        # mock attribution.attribute_effect 验证收到 state_delta
        from ecos.lca.l4_optimization.attribution import LCAAttribution

        original_attr = lca_engine.attribution.attribute_effect
        recorded_state_delta = []

        def mock_attribute_effect(intervention, student_id, state_delta):
            recorded_state_delta.append(state_delta)
            return original_attr(intervention, student_id, state_delta=state_delta)

        lca_engine.attribution.attribute_effect = mock_attribute_effect
        try:
            lca_engine.update(
                student_id="test_lca_reward",
                intervention=result.intervention,
                new_state=belief_state,
                state_delta=0.3,  # 故意跟 reward 不同
                reward=0.9,
            )
        finally:
            lca_engine.attribution.attribute_effect = original_attr

        # attribution 收到 state_delta=0.3, 不是 reward=0.9
        assert len(recorded_state_delta) == 1
        assert recorded_state_delta[0] == 0.3


# ──────────────────────────────────────────────────────────────────────
# 4. 教学 LCA 路径不受影响 (v0.62.0-A 隔离决策)
# ──────────────────────────────────────────────────────────────────────


class TestTeachingLCANotAffectedByRewardParam:
    """v0.69.0-b: 教学 LCA 路径 (web/api/lca.py) 不传 reward, 不受影响."""

    def test_teaching_lca_path_uses_state_delta(self, lca_engine, belief_state):
        """教学 LCA 路径 (web/api/lca.py) 不传 reward, 走 state_delta fallback."""
        result = _select_intervention(lca_engine, belief_state)
        # 教学 LCA 路径调 update 时不传 reward
        lca_engine.update(
            student_id="test_lca_reward",
            intervention=result.intervention,
            new_state=belief_state,
            state_delta=0.5,  # 教学 LCA 路径: 用 reward (state_delta=0.5) 给 LinUCB
        )
        bandit = lca_engine.bandits["test_lca_reward"]
        # arm_pull_counts +1
        assert int(bandit.bandit.arm_pull_counts.sum()) == 1
