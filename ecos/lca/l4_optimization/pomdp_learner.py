"""POMDP T/R 在线学习数据结构 (v0.90.0-a).

对应 12-kernel-mapping §1.3 Policy Engine POMDP 参数学习:
    "POMDP 完整 (依赖型 T+R, v0.88.0-c)" → "POMDP T/R 在线学习 (v0.90.0-d)".

v0.90.0-a 范围 (Phase 7+ 第 3 个 sub-version, POMDP T/R 学习数据通路):
  - **TransitionPosterior** (Dirichlet 多项式共轭 posterior):
    - shape (n_states, n_states, n_arms), 跟 POMDPPolicy.transition 对齐
    - count[s_next, s, a] (跟 POMDPPolicy.transition[s', s, a] 一致)
    - alpha0 = 1.0 (uniform prior, 跟 Thompson Sampling 一致)
    - update(s, a, s_next) 增量: count[s_next, s, a] += 1
    - mean() 派生 posterior MAP: T[s', s, a] = (count + alpha0) / Σ_s' (count + alpha0)
  - **RewardPosterior** (Beta 共轭 posterior):
    - alpha (n_states, n_arms), beta (n_states, n_arms), 跟 POMDPPolicy.reward 对齐
    - alpha0 = 1.0 (uniform prior, Beta(1, 1))
    - update(s, a, reward) 增量: alpha += reward, beta += (1 - reward)
    - mean() 派生 posterior MAP: alpha / (alpha + beta) (Bayes estimator)
  - **输入校验**: s / a / s_next 越界 raise ValueError; reward ∉ [0, 1] raise
  - **Posterior 数据结构独立**: 不持有 POMDPPolicy / BeliefState 引用, 走单独路径.

v0.90.0-b (持久化 + 注入 POMDPPolicy) + v0.90.0-c (PBVI 消费) 后续实施.
不引入 POMDPPolicy 接口变更 (接口同构 LinUCB/Thompson/POMDP 维持).

约定 (跟 POMDPPolicy.transition 一致):
    count[s_next, s, a] = # 次观察到 (state=s, action=a) → s_next
    posterior mean T[s_next, s, a] = (count[s_next, s, a] + alpha0) / Σ_s' count[s_next, s, a] + alpha0

防御性自检 [1]:
  - update 越界 raise (强制)
  - mean() 永远返 valid 矩阵 (count 全 0 → 均匀分布)
  - alpha / beta shape 不一致 → raise
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict

import numpy as np

_log = logging.getLogger(__name__)


@dataclass
class TransitionPosterior:
    """T(s'|s, a) Dirichlet 多项式共轭 posterior (v0.90.0-a).

    每 (s, a) 对一个 Dirichlet (n_states 项), update (s, a, s') increment.
    posterior mean (MAP point estimate, v0.90 决策):
        T_mean[s_next, s, a] = (count[s_next, s, a] + alpha0) /
                               Σ_s_next (count[s_next, s, a] + alpha0)

    Attributes:
        count:   shape (n_states, n_states, n_arms), 每 (s_next, s, a) 计数
        alpha0:  Dirichlet prior 强度 (默认 1.0, uniform prior)
    """

    count: np.ndarray
    alpha0: float = 1.0
    n_states: int = field(init=False)
    n_arms: int = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.count, np.ndarray):
            self.count = np.asarray(self.count, dtype=int)
        if self.count.ndim != 3:
            raise ValueError(
                f"TransitionPosterior.count 必须是 3D (n_states x n_states x n_arms), "
                f"got shape={self.count.shape}"
            )
        if (self.count < 0).any():
            raise ValueError(
                f"TransitionPosterior.count 不能为负 (got min={self.count.min()})"
            )
        if self.alpha0 <= 0:
            raise ValueError(
                f"TransitionPosterior.alpha0 必须 > 0 (got={self.alpha0})"
            )
        n_states_dim1, n_states_dim2, n_arms = self.count.shape
        if n_states_dim1 != n_states_dim2:
            raise ValueError(
                f"TransitionPosterior.count shape[0]={n_states_dim1} != shape[1]={n_states_dim2} "
                f"(约定 dim 0 = s_next, dim 1 = s, 必须都是 n_states)"
            )
        object.__setattr__(self, "n_states", int(n_states_dim1))
        object.__setattr__(self, "n_arms", int(n_arms))

    def update(self, s: int, a: int, s_next: int) -> None:
        """增量更新 count[s_next, s, a] += 1 (跟 Thompson Sampling 一致).

        Args:
            s:      当前状态 [0, n_states)
            a:      action/arm  [0, n_arms)
            s_next: 下一状态    [0, n_states)

        Raises:
            ValueError: s / a / s_next 越界 (强制 raise, 跟 POMDPPolicy.update 风格一致)
        """
        if not (0 <= s < self.n_states):
            raise ValueError(
                f"TransitionPosterior.update: s={s} 越界 [0, {self.n_states})"
            )
        if not (0 <= a < self.n_arms):
            raise ValueError(
                f"TransitionPosterior.update: a={a} 越界 [0, {self.n_arms})"
            )
        if not (0 <= s_next < self.n_states):
            raise ValueError(
                f"TransitionPosterior.update: s_next={s_next} 越界 [0, {self.n_states})"
            )
        self.count[s_next, s, a] += 1

    def mean(self) -> np.ndarray:
        """派生 posterior MAP (归一化 count + alpha0, 跨 s_next 求和).

        Returns:
            np.ndarray shape (n_states, n_states, n_arms):
                T_mean[s_next, s, a] = (count[s_next, s, a] + alpha0) /
                                       Σ_s_next (count[s_next, s, a] + alpha0)
                每 (s, a) 固定后, T[:, s, a] sum = 1 (valid stochastic vector)
                count 全 0 → 均匀分布 (1/n_states, alpha0 平滑)
        """
        posterior = self.count.astype(float) + self.alpha0
        return posterior / posterior.sum(axis=0, keepdims=True)

    def total_evidence(self) -> int:
        """总证据数 (sum count), 用于冷启动阈值判断 (v0.90.0-d min_samples)."""
        return int(self.count.sum())


@dataclass
class RewardPosterior:
    """R(s, a) Beta 共轭 posterior (v0.90.0-a).

    每 (s, a) 存 (alpha, beta), update 后 alpha += reward, beta += (1 - reward).
    posterior mean (MAP point estimate, v0.90 决策):
        R_mean[s, a] = alpha[s, a] / (alpha[s, a] + beta[s, a])  (Bayes estimator)

    Attributes:
        alpha:  shape (n_states, n_arms), Beta α 参数 (跟 POMDPPolicy.reward 对齐)
        beta:   shape (n_states, n_arms), Beta β 参数
        alpha0: Beta prior 初值 (默认 1.0, uniform prior Beta(1, 1))
    """

    alpha: np.ndarray
    beta: np.ndarray
    alpha0: float = 1.0
    n_states: int = field(init=False)
    n_arms: int = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.alpha, np.ndarray):
            self.alpha = np.asarray(self.alpha, dtype=float)
        if not isinstance(self.beta, np.ndarray):
            self.beta = np.asarray(self.beta, dtype=float)
        if self.alpha.ndim != 2:
            raise ValueError(
                f"RewardPosterior.alpha 必须是 2D (n_states x n_arms), "
                f"got shape={self.alpha.shape}"
            )
        if self.beta.shape != self.alpha.shape:
            raise ValueError(
                f"RewardPosterior.beta shape 必须跟 alpha 一致 "
                f"(alpha={self.alpha.shape}, beta={self.beta.shape})"
            )
        if (self.alpha <= 0).any() or (self.beta <= 0).any():
            raise ValueError(
                f"RewardPosterior.alpha/beta 必须 > 0 "
                f"(alpha min={self.alpha.min()}, beta min={self.beta.min()})"
            )
        if self.alpha0 <= 0:
            raise ValueError(
                f"RewardPosterior.alpha0 必须 > 0 (got={self.alpha0})"
            )
        object.__setattr__(self, "n_states", int(self.alpha.shape[0]))
        object.__setattr__(self, "n_arms", int(self.alpha.shape[1]))

    def update(self, s: int, a: int, reward: float) -> None:
        """Beta 共轭 update: alpha[s, a] += reward, beta[s, a] += (1 - reward).

        Args:
            s:      状态   [0, n_states)
            a:      arm    [0, n_arms)
            reward: 奖励 ∈ [0, 1] (Beta prior assumption)

        Raises:
            ValueError: s / a 越界 或 reward ∉ [0, 1]
        """
        if not (0 <= s < self.n_states):
            raise ValueError(
                f"RewardPosterior.update: s={s} 越界 [0, {self.n_states})"
            )
        if not (0 <= a < self.n_arms):
            raise ValueError(
                f"RewardPosterior.update: a={a} 越界 [0, {self.n_arms})"
            )
        if not (0.0 <= reward <= 1.0):
            raise ValueError(
                f"RewardPosterior.update: reward={reward} 必须在 [0, 1]"
            )
        self.alpha[s, a] += reward
        self.beta[s, a] += 1.0 - reward

    def mean(self) -> np.ndarray:
        """派生 posterior MAP: alpha / (alpha + beta).

        Returns:
            np.ndarray shape (n_states, n_arms): R_mean[s, a]
                alpha=beta=1 (prior) → 0.5 (uniform)
        """
        return self.alpha / (self.alpha + self.beta)

    def total_evidence(self) -> int:
        """总证据数 (sum (alpha + beta) - alpha0 * n_states * n_arms), 用于冷启动阈值."""
        return int(
            (self.alpha.sum() + self.beta.sum()) - self.alpha0 * self.n_states * self.n_arms
        )

    def get_arm_stats(self) -> Dict[str, Any]:
        """获取 per-(s, a) posterior 统计 (跟 ThompsonSampling.get_arm_stats 接口同构).

        Returns:
            dict 含:
              - alpha (List[List[float]])  shape (n_states, n_arms)
              - beta  (List[List[float]])  shape (n_states, n_arms)
              - expected_reward (List[List[float]])  alpha / (alpha + beta)
              - n_states (int)
              - n_arms (int)
              - total_evidence (int)
        """
        return {
            "alpha": self.alpha.tolist(),
            "beta": self.beta.tolist(),
            "expected_reward": (self.alpha / (self.alpha + self.beta)).tolist(),
            "n_states": self.n_states,
            "n_arms": self.n_arms,
            "total_evidence": self.total_evidence(),
        }


__all__ = [
    "TransitionPosterior",
    "RewardPosterior",
]