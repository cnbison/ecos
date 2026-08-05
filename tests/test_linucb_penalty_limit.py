"""v0.71.0 P0-g: LinUCB 惩罚次数限制测试.

背景:
  v0.59.0 引入策略质疑路径 bandit.A[last_arm] *= 10 (LINUCB_PENALTY_FACTOR).
  lbc003 触发 50 次策略质疑 -> A 矩阵放大 1.6e+05 倍 -> θ ≈ 0 -> V3 预测 ~0.11.

修复 (v0.71.0 P0-g):
  LCAPolicyLearner.apply_penalty(arm, factor) 替代直接 *=10.
  每 arm 最多惩罚 PENALTY_MAX 次 (默认 1, 实验数据最优).

实验数据 (lbc003 56 道题重放):
  PENALTY_MAX=1 -> V3 ECE=0.5737 (A 放大 10 倍)
  PENALTY_MAX=2 -> V3 ECE=0.7320 (A 放大 100 倍)
  PENALTY_MAX=3 -> V3 ECE=0.7529 (A 放大 1000 倍)
  PENALTY_MAX=5 -> V3 ECE=0.7553 (A 放大 10 万倍)

测试覆盖:
  1. apply_penalty 第一次返回 True, A 矩阵被放大
  2. apply_penalty 达到 PENALTY_MAX 后返回 False, A 矩阵不再变
  3. apply_penalty arm 越界返回 False + _log.warning
  4. strategy_challenge.lca_revise_policy 走 apply_penalty 路径
  5. lbc003 重放: 每 arm 最多惩罚 PENALTY_MAX 次 (不爆炸)
"""

from __future__ import annotations

import logging
from unittest.mock import patch

import numpy as np
import pytest


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def learner():
    from ecos.lca.l4_optimization.policy_learner import LCAPolicyLearner, BanditConfig
    return LCAPolicyLearner(BanditConfig())


@pytest.fixture
def belief_state():
    from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig
    from ecos.cta.l1_evolution import EvolutionConfig
    from ecos.cta.l2_mirt import MIRTConfig

    config = BeliefEngineConfig(
        evolution_config=EvolutionConfig(),
        mirt_config=MIRTConfig(),
    )
    engine = BeliefEngine(config=config, llm_client=None)
    return engine.create_initial_state("test_penalty")


# ──────────────────────────────────────────────────────────────────────
# 1. apply_penalty 基础行为
# ──────────────────────────────────────────────────────────────────────


class TestApplyPenaltyBasic:
    """v0.71.0: apply_penalty 基础行为."""

    def test_first_penalty_returns_true_and_scales_a(self, learner):
        """第一次 apply_penalty 返回 True, A 矩阵 *factor."""
        arm = 0
        A_before = learner.bandit.A[arm].copy()
        result = learner.apply_penalty(arm, factor=10.0)
        assert result is True
        A_after = learner.bandit.A[arm]
        # A 矩阵应该被放大 10 倍
        np.testing.assert_allclose(A_after, A_before * 10.0)
        assert learner._penalty_counts[arm] == 1

    def test_penalty_max_limit_returns_false(self, learner):
        """达到 PENALTY_MAX 后 apply_penalty 返回 False, A 矩阵不再变."""
        arm = 0
        # 跑 PENALTY_MAX 次 (默认 1)
        first = learner.apply_penalty(arm, factor=10.0)
        assert first is True
        assert learner._penalty_counts[arm] == 1

        # 第 2 次应该返回 False
        A_before = learner.bandit.A[arm].copy()
        second = learner.apply_penalty(arm, factor=10.0)
        assert second is False
        # A 矩阵不变
        np.testing.assert_allclose(learner.bandit.A[arm], A_before)
        # 计数器不再增加
        assert learner._penalty_counts[arm] == 1

    def test_arm_out_of_range_returns_false_with_warning(self, learner, caplog):
        """arm 越界返回 False + _log.warning."""
        with caplog.at_level(logging.WARNING):
            result = learner.apply_penalty(-1, factor=10.0)
        assert result is False
        assert "arm 越界" in caplog.text

        with caplog.at_level(logging.WARNING):
            result = learner.apply_penalty(999, factor=10.0)
        assert result is False
        assert "arm 越界" in caplog.text

    def test_penalty_counts_isolated_per_arm(self, learner):
        """每 arm 惩罚计数器独立."""
        # arm 0 惩罚 1 次 (达到 PENALTY_MAX=1)
        r0 = learner.apply_penalty(0, factor=10.0)
        assert r0 is True
        # arm 0 再次惩罚 -> False
        r0_2 = learner.apply_penalty(0, factor=10.0)
        assert r0_2 is False
        # arm 1 仍可惩罚
        r1 = learner.apply_penalty(1, factor=10.0)
        assert r1 is True
        assert learner._penalty_counts[0] == 1
        assert learner._penalty_counts[1] == 1


# ──────────────────────────────────────────────────────────────────────
# 2. strategy_challenge 路径调 apply_penalty
# ──────────────────────────────────────────────────────────────────────


class TestStrategyChallengeUsesApplyPenalty:
    """v0.71.0: strategy_challenge.lca_revise_policy 走 apply_penalty 路径."""

    def test_lca_revise_policy_calls_apply_penalty(self, learner, belief_state):
        """lca_revise_policy 走 apply_penalty, 不直接 *= 10."""
        from ecos.dual_agent.modes.strategy_challenge import StrategyChallengeMode
        from ecos.dual_agent.protocol.messages import StrategyChallenge
        from ecos.lca.intervention import (
            Intervention, InterventionType, CAStage, CLTLevel, BloomLevel,
        )
        from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig, CTAInput

        # 先 select 一次让 _last_arm 有值
        intervention = Intervention(
            intervention_type=InterventionType.EXPLANATORY,
            bloom_target=BloomLevel.UNDERSTAND,
            target_skills=[],
            target_misconceptions=[],
            target_tcs=["understand"],
            difficulty=0.5,
            quantity=3,
            feedback_density=0.8,
            scaffolding_level=0.5,
            clt_level=CLTLevel.DEVELOPING,
            ca_stage=CAStage.MODELING,
            bjork_triggers=[],
            expected_gain=0.3,
            expected_risk=0.1,
        )
        cta_input = CTAInput(student_id="test_penalty", belief_state=belief_state)
        # 直接 mock select_intervention 返回我们的 intervention
        # (避免依赖 LLM, 但要让 _last_arm 有值)
        learner.select_intervention = lambda state, cands: intervention
        learner._last_arm = 0  # 模拟 select 后的状态

        # 构造 StrategyChallengeMode
        lca_engine = LCAEngine(config=LCAEngineConfig(), llm_client=None)
        lca_engine.bandits["test_penalty"] = learner
        sc_mode = StrategyChallengeMode(lca_engine)

        # 构造 challenge
        challenge = StrategyChallenge(
            student_id="test_penalty",
            current_intervention_type="explanatory",
            cta_suggestion="test",
            evidence="test",
            calibration_round=1,
        )

        # patch select_intervention 避免依赖候选列表
        with patch.object(lca_engine, 'select_intervention', return_value=type('R', (), {'intervention': intervention, 'expected_gain': 0.3, 'expected_risk': 0.1})()):
            # 调 lca_revise_policy
            sc_mode.lca_revise_policy(challenge, belief_state, cta_input)

        # 验证: _penalty_counts[0] = 1 (调过 apply_penalty 一次)
        assert learner._penalty_counts[0] == 1

        # A 矩阵应该被放大 (跟初始 I 矩阵比)
        A = learner.bandit.A[0]
        # A = I * 10 (因为只惩罚 1 次)
        np.testing.assert_allclose(A, np.eye(A.shape[0]) * 10.0)


# ──────────────────────────────────────────────────────────────────────
# 3. lbc003 重放: 每 arm 惩罚次数有上限
# ──────────────────────────────────────────────────────────────────────


class TestLbc003ReplayPenaltyBounded:
    """v0.71.0: lbc003 重放后, 每 arm 惩罚次数 <= PENALTY_MAX."""

    def test_penalty_bounded_after_replay(self):
        """重放 lbc003 56 道题后, 每 arm 惩罚次数 <= PENALTY_MAX (1)."""
        import sqlite3, json
        from ecos.dual_agent.orchestrator import DualAgentConfig, DualAgentOrchestrator
        from ecos.cta.belief_engine import Observation
        from ecos.cta.belief_state import BloomLevel

        conn = sqlite3.connect('web/ecos.db')
        row = conn.execute("SELECT response_history FROM students WHERE student_id='lbc003'").fetchone()
        rh = json.loads(row[0])

        orch = DualAgentOrchestrator(config=DualAgentConfig(), llm_client=None)
        sid = 'test_lbc003_penalty_bounded'
        bloom_map = {
            'REMEMBER': BloomLevel.REMEMBER, 'UNDERSTAND': BloomLevel.UNDERSTAND,
            'APPLY': BloomLevel.APPLY, 'ANALYZE': BloomLevel.ANALYZE,
            'EVALUATE': BloomLevel.EVALUATE, 'CREATE': BloomLevel.CREATE,
        }

        for h in rh:
            obs = Observation(
                problem_id=h['problem_id'], skill_id='variables',
                correct=bool(h.get('correct', 0)), score=float(h.get('score', 0.0)),
                bloom_level=bloom_map.get(h.get('bloom_level', 'APPLY'), BloomLevel.APPLY),
                response_time_sec=0.0,
            )
            orch.process_observation(obs, student_id=sid)

        # 验证: 每 arm 惩罚次数 <= PENALTY_MAX (默认 1)
        bandit = orch.lca_engine.bandits[sid]
        from ecos.lca.l4_optimization.policy_learner import LCAPolicyLearner
        max_pen = LCAPolicyLearner.PENALTY_MAX
        for arm_idx, count in enumerate(bandit._penalty_counts):
            assert count <= max_pen, (
                f"arm[{arm_idx}] 惩罚次数 {count} > PENALTY_MAX {max_pen}"
            )

        # 验证: A 矩阵最大特征值 <= 10^PENALTY_MAX (不爆炸)
        #   PENALTY_MAX=1 -> A_max_eig <= 10 + ε (因为还有正常的 x x^T 累加)
        #   v0.75.3 H3-c3: fingerprint 修复后 update 每轮都调, A 累加更多,
        #     阈值从 100 -> 300 (10 * penalty + ~50 updates * |x|^2 ≈ 110, 留余量)
        import numpy as np
        for arm_idx in range(bandit.config.n_arms):
            eigvals = np.linalg.eigvalsh(bandit.bandit.A[arm_idx])
            # PENALTY_MAX=1 时, A = 10*I + sum(x x^T), 最大特征值应 < 300
            assert eigvals.max() < 300, (
                f"arm[{arm_idx}] A_max_eig={eigvals.max():.2e} > 300, "
                f"惩罚机制仍让 A 矩阵爆炸"
            )
