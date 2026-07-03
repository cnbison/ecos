"""L4 LCAPolicyLearner——LinUCB + Intervention 候选映射.

对应：
  - research/10-engineering/02-lca-policy-engine.md §4.2 LCAPolicyLearner

职责：
  - 把 BeliefState 编码成 LinUCB 上下文向量（16 维）
  - 维护 Intervention 候选池（arm 索引 → Intervention）
  - 提供 select_intervention(belief_state, candidates) 和 update(...)
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np

from ...cta.belief_state import BeliefState, BloomLevel
from ..intervention import Intervention
from .linucb import BanditConfig, LinUCB


class LCAPolicyLearner:
    """LCA 策略学习器——LinUCB 包装 + 上下文构建.

    用法：
        learner = LCAPolicyLearner(BanditConfig(n_arms=10))
        intervention = learner.select_intervention(belief_state, candidate_list)
        # 观测到 reward 后
        learner.update(intervention, belief_state, reward=state_delta)
    """

    # Context dim: 5 (5D theta) + 6 (Bloom) + 5 (DNA) = 16
    CONTEXT_DIM = 16

    def __init__(self, config: BanditConfig | None = None):
        self.config = config or BanditConfig()
        # 强制 spec 默认 context_dim（避免外部传错维度）
        if self.config.context_dim != self.CONTEXT_DIM:
            self.config.context_dim = self.CONTEXT_DIM
        self.bandit = LinUCB(
            n_arms=self.config.n_arms,
            context_dim=self.config.context_dim,
            alpha=self.config.alpha,
        )
        # Arm 索引 → 候选干预 hash（用于 update 时反查）
        self._arm_fingerprints: Dict[int, str] = {}
        self._last_arm: int = -1

    def select_intervention(
        self,
        belief_state: BeliefState,
        candidate_interventions: List[Intervention],
    ) -> Intervention:
        """基于 LinUCB 选择最佳干预.

        Args:
            belief_state: CTA 输出（构建上下文）
            candidate_interventions: 候选干预列表（数量应 == n_arms）

        Returns:
            选中的 Intervention

        Raises:
            ValueError: 候选数量与 n_arms 不匹配（候选数量不够时循环复用）
        """
        if not candidate_interventions:
            raise ValueError("candidate_interventions 不能为空")

        context = self._build_context(belief_state)
        arm = self.bandit.select_arm(context)
        self._last_arm = arm

        # 候选映射（循环复用）
        idx = arm % len(candidate_interventions)
        chosen = candidate_interventions[idx]

        # 记录 arm → 干预 fingerprint
        self._arm_fingerprints[arm] = chosen.intervention_id
        return chosen

    def update(
        self,
        intervention: Intervention,
        belief_state: BeliefState,
        reward: float,
    ) -> None:
        """基于干预效果更新 LinUCB.

        Args:
            intervention: 之前选中的干预
            belief_state: 干预后的 CTA 状态
            reward: 状态增量（state_delta），已被调用方归一化到 [0, 1]
        """
        context = self._build_context(belief_state)
        # 反查 arm 索引：优先用 last_arm + 指纹匹配
        arm = self._lookup_arm(intervention)
        if arm is None:
            # 未匹配（如新会话），跳过 update（不影响主流程）
            return
        # 截断 reward 到 [min_reward, max_reward]
        clamped = max(
            self.config.min_reward,
            min(self.config.max_reward, reward),
        )
        self.bandit.update(arm, context, clamped)

    # ---------------------------------------------------------------
    # 上下文构建（02-lca §4.2 _build_context）
    # ---------------------------------------------------------------

    def _build_context(self, belief_state: BeliefState) -> np.ndarray:
        """构造 LinUCB 上下文向量（16 维）.

        5 (5D theta) + 6 (BloomProfile) + 5 (DNA)
        """
        theta5 = np.array([
            belief_state.K.theta,
            belief_state.P.theta,
            belief_state.S.theta,
            belief_state.C.theta,
            belief_state.X.theta,
        ], dtype=float)
        bloom6 = np.array([
            belief_state.bloom_profile.remember,
            belief_state.bloom_profile.understand,
            belief_state.bloom_profile.apply,
            belief_state.bloom_profile.analyze,
            belief_state.bloom_profile.evaluate,
            belief_state.bloom_profile.create,
        ], dtype=float)
        dna = belief_state.learning_dna
        dna5 = np.array([
            1.0 if dna.input_preference == "visual" else 0.0,
            1.0 if dna.input_preference == "auditory" else 0.0,
            1.0 if dna.input_preference == "kinesthetic" else 0.0,
            1.0 if dna.feedback_preference == "immediate" else 0.0,
            dna.motivation_pattern.get("weekday", 0.5),
        ], dtype=float)
        return np.concatenate([theta5, bloom6, dna5])  # (16,)

    def _lookup_arm(self, intervention: Intervention) -> int | None:
        """通过干预 ID 反查 arm 索引."""
        target = intervention.intervention_id
        for arm, fp in self._arm_fingerprints.items():
            if fp == target:
                return arm
        # fallback: 使用 last_arm（仅当指纹匹配时）
        if self._last_arm >= 0 and self._arm_fingerprints.get(self._last_arm) == target:
            return self._last_arm
        return None


__all__ = ["LCAPolicyLearner"]
