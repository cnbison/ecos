"""POMDP Policy — 部分可观测 MDP 雏形 (v0.87.0-c).

对应 12-kernel-mapping §1.3 Policy Engine:
    "POMDP Policy (部分可观测 MDP, Phase 6+)".

v0.87.0-c 范围 (Phase 6+ 第 2 个 sub-version):
  - 4 状态 POMDP (Engaged / Frustrated / Bored / Confused)
  - 简化 transition + observation model (固定矩阵, 不学习)
  - Bayesian belief update (b'(s') ∝ O[o|s'] * Σ_s T[s'|s] * b(s))
  - select_action: argmax_a Σ_s b(s) * R(s, a)
  - 接口同构 LinUCB / Thompson (select_arm / update / dump_state / load_state)
  - PRNG seed (测试用)

POMDP 雏形限制 (Phase 6+ 初始版本, 后续 v0.88+ 扩展):
  - Simplified transition (不依赖 action, 简化矩阵)
  - Simplified observation model (固定 4x4)
  - 不实现 partial observability 的"模型学习" (transition / observation 固定)
  - 不实现完整 POMDP solver (point-based / SARSOP 等)

向后兼容:
  - 接口同构 LinUCB/Thompson (select_arm / update / dump_state / load_state)
  - 防御性自检 [8] 仍 hard block (POMDPPolicy 不 mutate state)
  - H3-c4 canary 必 PASS (POMDP 只改 select_intervention / update, classroom 行为不变)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, ClassVar, Dict, List, Optional

import numpy as np

_log = logging.getLogger(__name__)


@dataclass
class POMDPConfig:
    """POMDP 配置.

    Attributes:
        n_arms:       arm 数量 (跟 LinUCB.config.n_arms 一致)
        n_states:     latent state 数量 (默认 4: Engaged/Frustrated/Bored/Confused)
        n_observations: observation 数量 (默认 4, 跟 state 一一对应)
        seed:         PRNG seed (None = 系统 entropy, 测试用固定 seed)
    """

    n_arms: int = 10
    n_states: int = 4
    n_observations: int = 4
    seed: Optional[int] = None


class POMDPPolicy:
    """小 POMDP solver (v0.87.0-c 雏形).

    4 状态:
      - 0: Engaged   (投入)
      - 1: Frustrated (挫败)
      - 2: Bored     (无聊)
      - 3: Confused  (困惑)

    Belief state: b = P(state) (4-dim 概率向量, 和 = 1)
    Transition:    T[s'|s] (4x4, 简化: 不依赖 action)
    Observation:   O[o|s] (4 obs per state, 4x4 矩阵)
    Reward:        R(s, a) (per state + action, 4 x n_arms)

    算法:
      - select_arm: argmax_a Σ_s b(s) * R(s, a)
      - bayes_update(observation): b'(s') ∝ O[o|s'] * Σ_s T[s'|s] * b(s)
      - update(arm, context, reward): 仅更新 arm_pull_counts (简化, 不学 transition)

    适用:
      - reward ∈ [0, 1] (any float)
      - 4 状态 (Engaged/Frustrated/Bored/Confused)
      - 固定 transition / observation model (Phase 6+ 简化)

    防御性自检 [1]:
      - bayes_update 越界 observation _log.warning 跳过
      - select_arm n_arms=0 返 0 (degenerate)
    """

    STATE_NAMES: ClassVar[tuple] = ("Engaged", "Frustrated", "Bored", "Confused")

    def __init__(
        self,
        n_arms: int = 10,
        n_states: int = 4,
        n_observations: int = 4,
        seed: Optional[int] = None,
    ):
        if n_states <= 0:
            raise ValueError(f"POMDPPolicy: n_states={n_states} 必须 > 0")
        self.n_arms = int(n_arms)
        self.n_states = int(n_states)
        self.n_observations = int(n_observations)
        self._rng = np.random.default_rng(seed)

        # Belief state: 概率向量 (和 = 1, uniform prior)
        self.belief_state: np.ndarray = np.ones(self.n_states) / self.n_states

        # Transition: T[s'|s] (n_states x n_states, 简化: 不依赖 action)
        # 强 self-loop (0.7) + 弱跨状态 (0.1) → row sums = 0.7 + (n_states-1)*0.1
        # 当 n_states=4: row sum = 0.7 + 3*0.1 = 1.0
        self.transition: np.ndarray = (
            np.eye(self.n_states) * 0.7
            + np.ones((self.n_states, self.n_states)) * 0.1
        )
        # 归一化 row sum = 1 (防御性: 不依赖 n_states 整除)
        self.transition = self.transition / self.transition.sum(axis=1, keepdims=True)

        # Observation model: O[o|s] (n_observations x n_states)
        # 强对角 (0.6) + 弱跨 (auto: (1-0.6)/(n_states-1)) → row sum 精确 = 1.0
        # 例: n_states=4 → off-diagonal = 0.4/3 ≈ 0.1333
        obs_off = (1.0 - 0.6) / max(1, self.n_states - 1)
        self.observation_model: np.ndarray = np.full(
            (self.n_observations, self.n_states), obs_off
        )
        for s in range(self.n_states):
            self.observation_model[s, s] = 0.6
        # row sum 精确 = 1.0 (无需归一化, 但防御性: normalize 防浮点误差)
        self.observation_model = self.observation_model / self.observation_model.sum(axis=1, keepdims=True)

        # Reward: R(s, a) (n_states x n_arms), random init
        self.reward: np.ndarray = self._rng.uniform(0, 1, (self.n_states, self.n_arms))

        # Stats
        self.arm_pull_counts: np.ndarray = np.zeros(self.n_arms, dtype=int)
        self.total_observations: int = 0

    def select_arm(self, context: Optional[np.ndarray] = None) -> int:
        """argmax_a Σ_s b(s) * R(s, a).

        Args:
            context: 上下文向量 (LinUCB 接口同构, POMDP 不依赖 context, 忽略)

        Returns:
            arm 索引 [0, n_arms)

        防御性: n_arms=0 返 0 (degenerate)
        """
        if self.n_arms <= 0:
            _log.warning("POMDPPolicy.select_arm: n_arms=%s, 返 0 (degenerate)", self.n_arms)
            return 0
        # Expected reward per action: b^T @ R (n_arms,)
        expected_reward = self.belief_state @ self.reward
        return int(np.argmax(expected_reward))

    def update(self, arm: int, context: Optional[np.ndarray] = None, reward: float = 0.0) -> None:
        """Update arm_pull_counts (简化, 不学 transition / observation model).

        v0.87.0-c 简化: 仅追踪 arm 拉取次数. POMDP 完整 update 需要
        observation 反馈 (下一 commit bayes_update 处理), 跟 update 分开.
        当前 commit 仅满足接口同构 (跟 LinUCB/Thompson 一致).

        Args:
            arm: 选中的 arm 索引
            context: 上下文向量 (忽略)
            reward: 奖励 ∈ [0, 1] (LinUCB/Thompson 接口同构, POMDP 简化不直接用)

        防御性自检 [1]:
          - arm 越界 _log.warning + return
          - reward 截断到 [0, 1]
        """
        if arm < 0 or arm >= self.n_arms:
            _log.warning(
                "POMDPPolicy.update: arm 越界 (arm=%s, n_arms=%s), 跳过",
                arm, self.n_arms,
            )
            return
        # 截断 reward 到 [0, 1] (跟 LinUCB.update 一致)
        clamped = max(0.0, min(1.0, float(reward)))
        self.arm_pull_counts[arm] += 1

    def bayes_update(self, observation: int) -> None:
        """Bayesian belief update (POMDP 核心).

        b'(s') ∝ O[o|s'] * Σ_s T[s'|s] * b(s)

        Args:
            observation: int [0, n_observations), 答题 reaction 量化

        防御性自检 [1]: 越界 observation _log.warning 跳过 (不 raise)
        """
        if not (0 <= int(observation) < self.n_observations):
            _log.warning(
                "POMDPPolicy.bayes_update: observation 越界 (obs=%s, n_obs=%s), 跳过",
                observation, self.n_observations,
            )
            return
        # Predict: b_pred[s'] = Σ_s T[s'|s] * b(s)
        b_pred = self.transition.T @ self.belief_state
        # Update: b_post[s'] ∝ O[obs|s'] * b_pred[s']
        b_post = self.observation_model[observation] * b_pred
        # Normalize
        norm = b_post.sum()
        if norm > 0:
            self.belief_state = b_post / norm
        else:
            # 防御性: norm=0 时 fallback uniform (避免 NaN)
            self.belief_state = np.ones(self.n_states) / self.n_states
        self.total_observations += 1

    def get_arm_stats(self) -> Dict[str, Any]:
        """获取 arm + state 统计信息 (跟 LinUCB.get_arm_stats 接口同构).

        Returns:
            dict 含:
              - n_arms (int)
              - n_states (int)
              - n_observations (int)
              - state_names (List[str])
              - belief_state (List[float])
              - arm_pull_counts (List[int])
              - total_pulls (int)
              - total_observations (int)
              - expected_reward (List[float])  b @ R
        """
        expected_reward = (self.belief_state @ self.reward).tolist()
        return {
            "n_arms": self.n_arms,
            "n_states": self.n_states,
            "n_observations": self.n_observations,
            "state_names": list(self.STATE_NAMES[:self.n_states]),
            "belief_state": self.belief_state.tolist(),
            "arm_pull_counts": self.arm_pull_counts.tolist(),
            "total_pulls": int(self.arm_pull_counts.sum()),
            "total_observations": self.total_observations,
            "expected_reward": expected_reward,
        }

    def dump_state(self) -> Dict[str, Any]:
        """导出状态 (跟 LinUCB 持久化 schema 兼容).

        Returns:
            dict 含:
              - n_arms / n_states / n_observations
              - belief_state (List[float])
              - transition (List[List[float]])  n_states x n_states
              - observation_model (List[List[float]])  n_obs x n_states
              - reward (List[List[float]])  n_states x n_arms
              - arm_pull_counts (List[int])
              - total_observations (int)
        """
        return {
            "n_arms": self.n_arms,
            "n_states": self.n_states,
            "n_observations": self.n_observations,
            "belief_state": self.belief_state.tolist(),
            "transition": self.transition.tolist(),
            "observation_model": self.observation_model.tolist(),
            "reward": self.reward.tolist(),
            "arm_pull_counts": self.arm_pull_counts.tolist(),
            "total_observations": self.total_observations,
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        """加载状态 (含维度校验, 防御性自检 [5]).

        Args:
            state: dump_state() 导出的 dict

        防御性自检 [5]: n_arms / n_states / n_observations 必须匹配, 缺一不可
        """
        n_arms = int(state.get("n_arms", self.n_arms))
        n_states = int(state.get("n_states", self.n_states))
        n_observations = int(state.get("n_observations", self.n_observations))

        if n_arms != self.n_arms or n_states != self.n_states or n_observations != self.n_observations:
            raise ValueError(
                f"POMDPPolicy state 维度不匹配: "
                f"expected n_arms={self.n_arms}, n_states={self.n_states}, n_observations={self.n_observations}, "
                f"got n_arms={n_arms}, n_states={n_states}, n_observations={n_observations}"
            )

        belief = state.get("belief_state") or []
        if len(belief) != self.n_states:
            raise ValueError(
                f"POMDPPolicy state belief_state 长度不匹配 (expected={self.n_states}, got={len(belief)})"
            )

        self.belief_state = np.array(belief, dtype=float)

        # transition / observation_model / reward 长度校验 (per 防御性自检 [5])
        transition = state.get("transition") or []
        if len(transition) != self.n_states:
            raise ValueError(
                f"POMDPPolicy state transition 长度不匹配 (expected={self.n_states}, got={len(transition)})"
            )
        self.transition = np.array(transition, dtype=float)

        observation = state.get("observation_model") or []
        if len(observation) != self.n_observations:
            raise ValueError(
                f"POMDPPolicy state observation_model 长度不匹配 (expected={self.n_observations}, got={len(observation)})"
            )
        self.observation_model = np.array(observation, dtype=float)

        reward = state.get("reward") or []
        if len(reward) != self.n_states:
            raise ValueError(
                f"POMDPPolicy state reward 长度不匹配 (expected={self.n_states}, got={len(reward)})"
            )
        self.reward = np.array(reward, dtype=float)

        arm_pull_counts = state.get("arm_pull_counts") or []
        self.arm_pull_counts = (
            np.array(arm_pull_counts, dtype=int)
            if arm_pull_counts else np.zeros(self.n_arms, dtype=int)
        )
        self.total_observations = int(state.get("total_observations", 0))


__all__ = [
    "POMDPPolicy",
    "POMDPConfig",
]
