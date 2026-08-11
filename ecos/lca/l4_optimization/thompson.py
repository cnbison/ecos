"""Thompson Sampling — 贝叶斯 Bandit (v0.86.0-c).

对应 12-kernel-mapping §1.3 Policy Engine:
    "v0.76.0: 引入 Thompson Sampling (Policy Engine 第二个 Policy)".

算法 (Beta-Bernoulli conjugate):
    - 每 arm 维护 (α, β) 标量
    - select_arm: sample θ_a ~ Beta(α_a, β_a), return argmax
    - update(arm, reward): α += reward, β += (1 - reward)

接口同构 (跟 LinUCB 一致):
    - select_arm(context) -> int (context 忽略, non-contextual Beta)
    - update(arm, context, reward) -> None (context 忽略)
    - dump_state() -> dict
    - load_state(state) -> None
    - get_arm_stats() -> dict

冷启动: 全部 arm 初始化 (α=1, β=1) uniform prior
PRNG: numpy.random 默认 (production 走系统 entropy); 测试用 np.random.seed 固定

向后兼容:
    - LinUCB 主路径不变 (默认 policy_type="linucb", v0.82.0-d 兼容)
    - dtype / shape 跟 LinUCB 兼容 (n_arms scalar α/β arrays)
    - 防御性自检 [8] 仍 hard block (ThompsonSampling 不 mutate state)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np

_log = logging.getLogger(__name__)


@dataclass
class ThompsonConfig:
    """Thompson Sampling 配置.

    Attributes:
        n_arms:     arm 数量 (跟 LinUCB.config.n_arms 一致)
        alpha_prior: Beta prior α 初值 (default 1.0 = uniform prior)
        beta_prior:  Beta prior β 初值 (default 1.0 = uniform prior)
        seed:       PRNG seed (None = 系统 entropy, 测试用固定 seed)
    """

    n_arms: int = 10
    alpha_prior: float = 1.0
    beta_prior: float = 1.0
    seed: Optional[int] = None


class ThompsonSampling:
    """Beta-Bernoulli Thompson Sampling.

    用法:
        bandit = ThompsonSampling(n_arms=10, seed=42)
        # 注: context 对 Thompson 是非必需的 (Beta prior 不依赖 context)
        #     但签名跟 LinUCB 对齐, 接受 context 参数 (忽略)
        arm_idx = bandit.select_arm(context=None)
        bandit.update(arm_idx, context=None, reward=0.7)

    适用条件:
        - reward ∈ [0, 1] (Beta prior 假设)
        - non-contextual (observation 不依赖 context)
        - n_arms 固定 (不支持动态 arm)

    持久化:
        - dump_state(): dict 含 alpha / beta / arm_pull_counts
        - load_state(state): 恢复 alpha / beta / arm_pull_counts

    防御性自检 [1]:
        - update 越界 _log.warning, 不 raise
        - select_arm 时 n_arms=0 返 0 (fallback)
    """

    def __init__(
        self,
        n_arms: int = 10,
        alpha_prior: float = 1.0,
        beta_prior: float = 1.0,
        seed: Optional[int] = None,
    ):
        self.n_arms = int(n_arms)
        self.alpha_prior = float(alpha_prior)
        self.beta_prior = float(beta_prior)
        # v0.86.0-c: PRNG (跟 LinUCB 不同, LinUCB 是 deterministic)
        self._rng = np.random.default_rng(seed)
        # v0.86.0-c: per-arm Beta parameters
        self.alpha: np.ndarray = np.full(self.n_arms, self.alpha_prior, dtype=float)
        self.beta: np.ndarray = np.full(self.n_arms, self.beta_prior, dtype=float)
        # v0.86.0-c: 每 arm 拉取次数 (跟 LinUCB.arm_pull_counts 兼容, 用于冷启动判定)
        self.arm_pull_counts: np.ndarray = np.zeros(self.n_arms, dtype=int)

    def select_arm(self, context: Optional[np.ndarray] = None) -> int:
        """Beta(α, β) 采样选 argmax.

        Args:
            context: 16 维上下文向量 (LinUCB 接口同构, Beta prior 不依赖 context, 忽略)

        Returns:
            arm 索引 [0, n_arms)

        防御性: n_arms=0 返 0 (degenerate)
        """
        if self.n_arms <= 0:
            _log.warning("ThompsonSampling.select_arm: n_arms=%s, 返 0 (degenerate)", self.n_arms)
            return 0
        # Beta(α, β) 采样 (跟 LinUCB select_arm 接口同构但内容不同)
        samples = self._rng.beta(self.alpha, self.beta)
        return int(np.argmax(samples))

    def update(self, arm: int, context: Optional[np.ndarray] = None, reward: float = 0.0) -> None:
        """Beta conjugate update: α += reward, β += (1 - reward).

        Args:
            arm:     选中的 arm 索引
            context: 上下文向量 (忽略)
            reward:  奖励 ∈ [0, 1] (Beta prior assumption)

        防御性自检 [1]:
            - arm 越界 _log.warning + return
            - reward 截断到 [0, 1] (允许小幅越界, 不 raise)
        """
        if arm < 0 or arm >= self.n_arms:
            _log.warning(
                "ThompsonSampling.update: arm 越界 (arm=%s, n_arms=%s), 跳过",
                arm, self.n_arms,
            )
            return
        # 截断 reward 到 [0, 1] (跟 LinUCB.update 一致)
        clamped = max(0.0, min(1.0, float(reward)))
        self.alpha[arm] += clamped
        self.beta[arm] += (1.0 - clamped)
        self.arm_pull_counts[arm] += 1

    def get_arm_stats(self) -> Dict[str, Any]:
        """获取每个 arm 的统计信息 (跟 LinUCB.get_arm_stats 接口同构).

        Returns:
            dict 含:
              - n_arms (int)
              - alpha_prior / beta_prior (float)
              - alpha / beta (List[float])    per-arm Beta params
              - arm_pull_counts (List[int])
              - total_pulls (int)
              - expected_reward (List[float])  alpha / (alpha + beta) 后验均值
        """
        expected_reward = (self.alpha / (self.alpha + self.beta)).tolist()
        return {
            "n_arms": self.n_arms,
            "alpha_prior": self.alpha_prior,
            "beta_prior": self.beta_prior,
            "alpha": self.alpha.tolist(),
            "beta": self.beta.tolist(),
            "arm_pull_counts": self.arm_pull_counts.tolist(),
            "total_pulls": int(self.arm_pull_counts.sum()),
            "expected_reward": expected_reward,
        }

    def dump_state(self) -> Dict[str, Any]:
        """导出状态 (跟 LinUCB 持久化 schema 兼容 4 字段).

        Returns:
            dict 含:
              - alpha (List[float])       per-arm α
              - beta (List[float])        per-arm β
              - arm_pull_counts (List[int])
              - alpha_prior (float)
              - beta_prior (float)
              - n_arms (int)
        """
        return {
            "alpha": self.alpha.tolist(),
            "beta": self.beta.tolist(),
            "arm_pull_counts": self.arm_pull_counts.tolist(),
            "alpha_prior": self.alpha_prior,
            "beta_prior": self.beta_prior,
            "n_arms": self.n_arms,
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        """加载状态 (含维度校验, 防御性自检 [5]).

        Args:
            state: dump_state() 导出的 dict

        防御性自检 [5]: n_arms / alpha / beta 长度必须匹配, 缺一不可
        """
        n_arms = state.get("n_arms", self.n_arms)
        if int(n_arms) != self.n_arms:
            raise ValueError(
                f"ThompsonSampling state n_arms 不匹配 (expected={self.n_arms}, got={n_arms})"
            )

        alpha = state.get("alpha") or []
        beta = state.get("beta") or []
        arm_pull_counts = state.get("arm_pull_counts") or []

        if len(alpha) != self.n_arms or len(beta) != self.n_arms:
            raise ValueError(
                f"ThompsonSampling state 长度不匹配 (alpha={len(alpha)}, beta={len(beta)}, "
                f"expected={self.n_arms})"
            )

        self.alpha = np.array(alpha, dtype=float)
        self.beta = np.array(beta, dtype=float)
        self.arm_pull_counts = np.array(arm_pull_counts, dtype=int) if arm_pull_counts else np.zeros(self.n_arms, dtype=int)


__all__ = [
    "ThompsonSampling",
    "ThompsonConfig",
]
