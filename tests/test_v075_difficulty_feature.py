"""v0.75 P0-m: LinUCB difficulty feature (17 维 context) 测试.

背景:
  v0.74 ECE 0.24 仍未过 H3 阈值 0.10, 真正瓶颈是 Platt/Isotonic 阶段
  bin [0.9, 1.0] gap +0.10 (26/49 样本, 占全局 ECE 0.06).

  根因: LinUCB context 16 维只看学生状态, 看不到干预难度. 所以
  同一 raw_V3 (e.g. 0.40) 对应"易干预"和"难干预"都给同样预测,
  Platt 校准后高 conf bin 出现 +0.10 系统误差.

方案:
  LinUCB context 16 -> 17 维 (末尾加 intervention.difficulty).
  启用 use_arm_features=True 时, 每个候选评估独立 context,
  LinUCB 能学到"这个学生 + 这个难度 -> 期望答对概率".

测试覆盖:
  - TestLinUCBScoreArm: 4 个 bandit 单测
    1. score_arm 返回合理 UCB 分数
    2. score_arm 越界返回 0.0 + warning
    3. score_arm context dim 错误返回 0.0 + warning
    4. score_arm 跟 select_arm 一致 (重构不破坏行为)
  - TestPolicyLearnerDifficulty: 3 个 policy learner 单测
    1. use_arm_features=False 时, context 仍 16 维
    2. use_arm_features=True 时, context 17 维 (含 difficulty)
    3. use_arm_features=True 时, select_intervention 评估每个候选
  - TestV075Lbc003DifficultyImprovement: 1 个 lbc003 重放集成
    - 验证 use_arm_features=True 跟 False 跑出不同的 V3 分布
    - 预期: bin [0.9, 1.0] gap 改善

设计:
  - use_arm_features 默认 False (向后兼容)
  - 显式 use_arm_features=True 时激活 17 维路径
  - 旧测试不依赖 use_arm_features, 维持 16 维默认行为
"""

from __future__ import annotations

import json
import logging
import sqlite3

import numpy as np
import pytest

from ecos.cta.belief_engine import Observation
from ecos.cta.belief_state import (
    BloomLevel, BeliefState, DimensionState, ConfidenceDimensionState,
    BloomProfileState, LearningDNAState, TrajectoryState,
)
from ecos.lca.intervention import Intervention, InterventionType
from ecos.lca.l4_optimization.linucb import LinUCB, BanditConfig
from ecos.lca.l4_optimization.policy_learner import LCAPolicyLearner


# ──────────────────────────────────────────────────────────────────────
# 1. LinUCB.score_arm 单测
# ──────────────────────────────────────────────────────────────────────


class TestLinUCBScoreArm:
    """v0.75 P0-m: LinUCB 新增 score_arm 方法."""

    def test_score_arm_returns_ucb(self):
        """score_arm 返回 θ@x + α*sqrt(x'A^{-1}x) UCB 分数."""
        bandit = LinUCB(n_arms=3, context_dim=4, alpha=1.0)
        # 训一下, 让 θ 有意义
        bandit.update(0, np.array([0.5, 0.5, 0.5, 0.5]), reward=1.0)
        bandit.update(1, np.array([0.1, 0.1, 0.1, 0.1]), reward=0.0)
        bandit.update(2, np.array([0.9, 0.9, 0.9, 0.9]), reward=0.5)

        score = bandit.score_arm(0, np.array([0.5, 0.5, 0.5, 0.5]))
        assert isinstance(score, float)
        # UCB >= expected_reward (因为有 confidence_bound 项)
        assert score > 0.0

    def test_score_arm_out_of_range_returns_zero(self, caplog):
        """score_arm arm 越界返回 0.0 + log warning."""
        bandit = LinUCB(n_arms=3, context_dim=4, alpha=1.0)
        with caplog.at_level(logging.WARNING, logger="ecos.lca.l4_optimization.linucb"):
            score = bandit.score_arm(99, np.array([0.5, 0.5, 0.5, 0.5]))
        assert score == 0.0
        warning_logs = [r for r in caplog.records if "arm 越界" in r.message]
        assert len(warning_logs) >= 1

    def test_score_arm_wrong_context_dim_returns_zero(self, caplog):
        """score_arm context dim 不匹配返回 0.0 + log warning."""
        bandit = LinUCB(n_arms=3, context_dim=4, alpha=1.0)
        with caplog.at_level(logging.WARNING, logger="ecos.lca.l4_optimization.linucb"):
            score = bandit.score_arm(0, np.array([0.5, 0.5, 0.5]))  # 3 维, 期望 4
        assert score == 0.0
        warning_logs = [r for r in caplog.records if "context dim 错误" in r.message]
        assert len(warning_logs) >= 1

    def test_select_arm_uses_score_arm_internally(self):
        """select_arm 跟 score_arm 给出同样的 argmax 结果 (重构一致性)."""
        bandit = LinUCB(n_arms=3, context_dim=4, alpha=0.5)
        bandit.update(0, np.array([0.5, 0.5, 0.5, 0.5]), reward=1.0)
        bandit.update(1, np.array([0.1, 0.1, 0.1, 0.1]), reward=0.0)
        bandit.update(2, np.array([0.9, 0.9, 0.9, 0.9]), reward=0.5)

        context = np.array([0.5, 0.5, 0.5, 0.5])
        arm_from_select = bandit.select_arm(context)

        # 手动算每个 arm 的 score, 跟 select_arm 一致
        scores = [bandit.score_arm(i, context) for i in range(3)]
        arm_from_scores = int(np.argmax(scores))

        assert arm_from_select == arm_from_scores


# ──────────────────────────────────────────────────────────────────────
# 2. LCAPolicyLearner difficulty feature 测试
# ──────────────────────────────────────────────────────────────────────


def _make_belief_state() -> BeliefState:
    """构造测试 BeliefState (5D mastery 0.5, 默认)."""
    return BeliefState(student_id="test_student")


def _make_candidate_interventions(n: int = 10) -> list:
    """构造 n 个候选 Intervention (难度依次 [0.3, 0.5, 0.4, 0.6, 0.5, 0.4, 0.5, 0.7, 0.7, 0.7])."""
    difficulties = [0.3, 0.5, 0.4, 0.6, 0.5, 0.4, 0.5, 0.7, 0.7, 0.7]
    candidates = []
    for i in range(n):
        cand = Intervention(
            intervention_type=InterventionType.PRACTICE,
            bloom_target=BloomLevel.APPLY,
            difficulty=difficulties[i % len(difficulties)],
        )
        candidates.append(cand)
    return candidates


class TestPolicyLearnerDifficulty:
    """v0.75 P0-m: LCAPolicyLearner 支持 17 维 context (含 intervention.difficulty)."""

    def test_context_default_16_dim(self):
        """默认 (use_arm_features=False) context 16 维."""
        learner = LCAPolicyLearner()
        state = _make_belief_state()
        context = learner._build_context(state)
        assert context.shape == (16,), f"default 应该是 16 维, got {context.shape}"
        assert learner.bandit.context_dim == 16

    def test_context_with_difficulty_17_dim(self):
        """use_arm_features=True + 提供 intervention 时 context 17 维."""
        config = BanditConfig(use_arm_features=True)
        learner = LCAPolicyLearner(config=config)
        state = _make_belief_state()
        cand = _make_candidate_interventions(1)[0]
        context = learner._build_context(state, intervention=cand)
        assert context.shape == (17,), f"use_arm_features 应该是 17 维, got {context.shape}"
        assert learner.bandit.context_dim == 17
        # 最后 1 维 = intervention.difficulty
        assert context[-1] == cand.difficulty

    def test_context_without_intervention_16_dim_even_with_arm_features(self):
        """use_arm_features=True 但不传 intervention 时 context 仍 16 维 (兼容 update 路径)."""
        config = BanditConfig(use_arm_features=True)
        learner = LCAPolicyLearner(config=config)
        state = _make_belief_state()
        # 不传 intervention
        context = learner._build_context(state)
        assert context.shape == (16,), (
            f"不传 intervention 应该保持 16 维, got {context.shape}"
        )

    def test_select_intervention_with_arm_features(self):
        """use_arm_features=True 时, select_intervention 评估每个候选 (17 维)."""
        config = BanditConfig(use_arm_features=True, n_arms=10, alpha=1.0)
        learner = LCAPolicyLearner(config=config)
        state = _make_belief_state()
        candidates = _make_candidate_interventions(10)

        chosen = learner.select_intervention(state, candidates)
        assert chosen in candidates
        # 验证 _last_arm 跟 chosen.intervention_id 匹配
        assert learner._arm_fingerprints[learner._last_arm] == chosen.intervention_id

    def test_arm_features_does_not_break_existing_tests(self):
        """use_arm_features=False 默认行为不变 (跟 v0.74 兼容)."""
        learner = LCAPolicyLearner()
        state = _make_belief_state()
        candidates = _make_candidate_interventions(10)

        chosen = learner.select_intervention(state, candidates)
        assert chosen in candidates
        # 16 维 context 训练一次, 验证 update 不报错
        learner.update(chosen, state, reward=1.0)
        assert learner.bandit.arm_pull_counts.sum() == 1


# ──────────────────────────────────────────────────────────────────────
# 3. v0.75 P0-m lbc003 重放验证
# ──────────────────────────────────────────────────────────────────────


class TestV075Lbc003DifficultyImprovement:
    """v0.75 P0-m: lbc003 重放, use_arm_features=True 跟 False 对比.

    预期:
      - use_arm_features=False (v0.74 行为): calibrated V3 ECE 0.24
      - use_arm_features=True (v0.75 P0-m):
        - bin [0.9, 1.0] gap 改善 (raw V3 现在区分难易干预)
        - 全局 ECE 改善 (期望接近 single agent baseline 0.17)
        - source 分布变化: isotonic_regression 样本数可能减少 (因为 raw V3 更分散)
    """

    def test_arm_features_changes_v3_distribution(self):
        """lbc003 重放, use_arm_features=True 跟 False 跑出不同 V3 分布."""
        from ecos.dual_agent.orchestrator import DualAgentConfig, DualAgentOrchestrator
        from ecos.lca.orchestrator import LCAEngineConfig
        from ecos.lca.l4_optimization.linucb import BanditConfig

        # 加载 lbc003 数据
        conn = sqlite3.connect("web/ecos.db")
        row = conn.execute(
            "SELECT response_history FROM students WHERE student_id='lbc003'"
        ).fetchone()
        rh = json.loads(row[0])

        bloom_map = {
            "REMEMBER": BloomLevel.REMEMBER, "UNDERSTAND": BloomLevel.UNDERSTAND,
            "APPLY": BloomLevel.APPLY, "ANALYZE": BloomLevel.ANALYZE,
            "EVALUATE": BloomLevel.EVALUATE, "CREATE": BloomLevel.CREATE,
        }

        # 跑两次: use_arm_features=False vs True
        results = {}
        for use_arm in (False, True):
            bandit_cfg = BanditConfig(use_arm_features=use_arm)
            lca_cfg = LCAEngineConfig(bandit_config=bandit_cfg)
            dual_cfg = DualAgentConfig(lca_config=lca_cfg)
            orch = DualAgentOrchestrator(config=dual_cfg, llm_client=None)
            sid = f"test_v075_arm_{use_arm}"

            for h in rh:
                obs = Observation(
                    problem_id=h["problem_id"], skill_id="variables",
                    correct=bool(h.get("correct", 0)),
                    score=float(h.get("score", 0.0)),
                    bloom_level=bloom_map.get(h.get("bloom_level", "APPLY"), BloomLevel.APPLY),
                    response_time_sec=0.0,
                )
                orch.process_observation(obs, student_id=sid)

            # 提取 raw V3 跟 actual_outcome
            raw_v3s = []
            actuals = []
            for h in orch.intervention_history[sid]:
                raw = h.metadata.get("dual_agent_confidence")
                actual = h.actual_outcome
                if raw is not None and actual is not None:
                    raw_v3s.append(float(raw))
                    actuals.append(float(actual))

            results[use_arm] = {
                "raw_v3s": np.array(raw_v3s),
                "actuals": np.array(actuals),
            }

        raw_v3s_off = results[False]["raw_v3s"]
        raw_v3s_on = results[True]["raw_v3s"]
        actuals = results[False]["actuals"]  # same for both

        print(f"\nuse_arm_features=False raw_V3 范围: [{raw_v3s_off.min():.3f}, {raw_v3s_off.max():.3f}], mean={raw_v3s_off.mean():.3f}, std={raw_v3s_off.std():.3f}")
        print(f"use_arm_features=True  raw_V3 范围: [{raw_v3s_on.min():.3f}, {raw_v3s_on.max():.3f}], mean={raw_v3s_on.mean():.3f}, std={raw_v3s_on.std():.3f}")

        # 预期: use_arm_features=True 时, raw V3 std 显著增加 (因为有 difficulty 信号)
        # 这样 Platt/Isotonic 有更多区分度
        assert raw_v3s_on.std() > raw_v3s_off.std(), (
            f"use_arm_features=True raw V3 std ({raw_v3s_on.std():.3f}) 应 > "
            f"False ({raw_v3s_off.std():.3f}), 因为 difficulty 让 raw V3 区分度更高"
        )
