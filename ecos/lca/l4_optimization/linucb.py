"""L4 Contextual Bandits (LinUCB 算法) — MVP 策略学习.

对应：
  - research/10-engineering/02-lca-policy-engine.md §4.2 Contextual Bandits (LinUCB)
  - research/10-engineering/02-lca-policy-engine.md §6 LCAOrchestrator 第 5-8 步
  - research/00-overview/02-architecture.md §6.3 双 Agent 互校

LinUCB 算法（Li et al., 2010）：
  - 每个 arm a 维护参数 θ_a
  - 选择 arm：argmax_a (θ_a^T x + α √(x^T A_a^{-1} x))
  - 探索-利用平衡：α 控制（exploration bonus）
  - 更新：A_a += x x^T, b_a += r x

Context（CTA 状态）：5D + 6 Bloom + 5 DNA = 16 维（与 02-lca §4.2 一致）
Arm（干预候选）：每个候选 Intervention 编码为整数索引（M2 W2 默认 10 个候选）

Phase 4 MVP：
  - 使用 numpy 实现 LinUCB（无 vowpalwabbit 依赖）
  - 候选 arm 数量通过 BanditConfig.n_arms 配置（默认 10，覆盖 5 类型 × 2 难度）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from ...cta.belief_state import BeliefState

_log = logging.getLogger(__name__)


@dataclass
class BanditConfig:
    """Bandit 配置."""

    n_arms: int = 10        # 候选干预数量（默认 10）
    context_dim: int = 16   # 上下文维度：5 + 6 + 5
    alpha: float = 1.0      # 探索系数（LinUCB 探索-利用平衡）
    min_reward: float = 0.0
    max_reward: float = 1.0
    # v0.69.0: LinUCB 冷启动阈值 (arm_pull_counts.sum() < threshold -> 冷启动期)
    # 冷启动期 expected_gain 走 _estimate_gain 简化估算, 非冷启动走 LinUCB θ@x 预测
    # 默认 10: 10 个 arm 各拉 1 次, 或同 arm 拉 10 次, 之后 LinUCB 预测生效
    cold_start_threshold: int = 10
    # v0.75 P0-m: 是否启用 arm features (intervention.difficulty)
    #   False (默认): 16 维 student context, 所有 arm 共享 (v0.71-v0.74 行为)
    #   True: 17 维 context (16 student + 1 intervention.difficulty), 每个候选独立评估
    use_arm_features: bool = False


class LinUCB:
    """LinUCB 算法实现——对应论文 Li et al., 2010 'A Contextual-Bandit Approach to
    Personalized News Article Recommendation'.

    用法：
        bandit = LinUCB(n_arms=10, context_dim=16, alpha=1.0)
        arm_idx = bandit.select_arm(context_vector)
        bandit.update(arm_idx, context_vector, reward=0.3)
    """

    def __init__(self, n_arms: int = 10, context_dim: int = 16, alpha: float = 1.0):
        self.n_arms = n_arms
        self.context_dim = context_dim
        self.alpha = alpha
        # 每个 arm 的协方差矩阵 + 线性参数
        self.A: List[np.ndarray] = [np.eye(context_dim) for _ in range(n_arms)]
        self.b: List[np.ndarray] = [np.zeros(context_dim) for _ in range(n_arms)]
        # 统计信息
        self.arm_pull_counts: np.ndarray = np.zeros(n_arms, dtype=int)

    def select_arm(self, context: np.ndarray) -> int:
        """根据 UCB 选择 arm.

        Args:
            context: 上下文向量（dim = context_dim）

        Returns:
            arm 索引 [0, n_arms)
        """
        x = np.asarray(context, dtype=float).flatten()
        assert x.shape[0] == self.context_dim, (
            f"context dim mismatch: expected {self.context_dim}, got {x.shape[0]}"
        )

        ucb_values = np.zeros(self.n_arms)
        for arm in range(self.n_arms):
            ucb_values[arm] = self.score_arm(arm, x)

        return int(np.argmax(ucb_values))

    def score_arm(self, arm: int, context: np.ndarray) -> float:
        """v0.75 P0-m: 计算指定 arm 在给定 context 下的 UCB 分数.

        用于 arm features 模式 (use_arm_features=True), 每个候选 arm 评估时
        context 不同 (候选特有的 difficulty), 需要逐个调用 score_arm.

        Args:
            arm: arm 索引 [0, n_arms)
            context: 上下文向量 (dim = context_dim)

        Returns:
            UCB 分数 (expected_reward + alpha * confidence_bound)
            异常时返回 0.0, 不污染 bandit 状态

        防御性自检 [1]: 任何异常 _log.warning, 不 raise, 不 silent pass
        防御性自检 [6]: 失败不污染 in-memory bandit 状态
        """
        x = np.asarray(context, dtype=float).flatten()
        if arm < 0 or arm >= self.n_arms:
            _log.warning(
                "score_arm: arm 越界 (arm=%s, n_arms=%s), 返回 0.0",
                arm, self.n_arms,
            )
            return 0.0
        if x.shape[0] != self.context_dim:
            _log.warning(
                "score_arm: context dim 错误 (expected=%s, got=%s), 返回 0.0",
                self.context_dim, x.shape[0],
            )
            return 0.0
        try:
            A_inv = np.linalg.inv(self.A[arm])
        except np.linalg.LinAlgError:
            A_inv = np.eye(self.context_dim)
        theta = A_inv @ self.b[arm]
        expected_reward = float(theta @ x)
        confidence_bound = self.alpha * float(np.sqrt(x @ A_inv @ x))
        return expected_reward + confidence_bound

    def update(self, arm: int, context: np.ndarray, reward: float) -> None:
        """更新选中的 arm（在线岭回归）.

        A_a ← A_a + x x^T
        b_a ← b_a + r x

        Args:
            arm: 选中的 arm 索引
            context: 上下文向量
            reward: 观测到的奖励（state_delta，归一化到 [0, 1]）
        """
        x = np.asarray(context, dtype=float).flatten()
        self.A[arm] = self.A[arm] + np.outer(x, x)
        self.b[arm] = self.b[arm] + reward * x
        self.arm_pull_counts[arm] += 1

    def get_arm_stats(self) -> dict:
        """获取每个 arm 的统计信息（调试 + 教师后台接口）."""
        return {
            "n_arms": self.n_arms,
            "context_dim": self.context_dim,
            "alpha": self.alpha,
            "arm_pull_counts": self.arm_pull_counts.tolist(),
            "total_pulls": int(self.arm_pull_counts.sum()),
        }


__all__ = ["LinUCB", "BanditConfig"]
