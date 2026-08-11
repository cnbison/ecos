"""POMDP point-based solver — PBVI 雏形 (v0.89.0-a, α-vector + 单步 backup).

对应 12-kernel-mapping §1.3 Policy Engine:
    "POMDP Policy (部分可观测 MDP)" → "POMDP PBVI 雏形 (point-based solver, v0.89.0-a)".

v0.89.0-a 范围 (Phase 7+ POMDP 完整化 #2, 算法本体):
  - AlphaVector frozen dataclass: (action, values[n_states]) 不可变值函数向量
  - PBVI class: belief_points (List[np.ndarray]) + alpha_vectors (List[AlphaVector])
    + gamma / epsilon / n_iters 配置
  - PBVI.backup_step(transition, observation_model, reward) -> List[AlphaVector]
    单步 backup 算法:
      对每个 action a, 对每个 belief point b:
        V_a(b) = Σ_s b(s) * R(s, a) + γ * Σ_o P(o|b, a) * max_{α'} α'(b')
      P(o|b, a) = Σ_s' O[o|s'] * Σ_s T[s'|s, a] * b(s)
  - PBVI.alpha_value(belief): 在给定 belief 上算 max α(b) (雏形)
  - PBVI.best_action(belief): argmax_a α_a(b) (跟 POMDPPolicy.select_arm 同构)

v0.89.0-b 范围 (留待):
  - PBVI.update_alpha_vectors (收敛检测)
  - PBVI.solve 主算法 (iterative backup)
  - reachable_belief_points / uniform_belief_points sampling

v0.89.0-c 范围 (留待):
  - POMDPPolicy 集成 PBVI select_arm (替换 v0.88.0-c QMDP argmax_a b @ R[:, a])

v0.89.0-d 范围 (留待):
  - Runtime + PolicyABTest 集成

向后兼容:
  - PBVI 是 POMDPPolicy 子组件 (c 阶段集成), 现有 POMDPPolicy 不变
  - PBVI 纯函数 (backup_step / alpha_value / best_action) 不修改 self.alpha_vectors
  - 防御性自检 [8] 仍 hard block (PBVI solver 不 mutate BeliefState)
  - H3-c4 canary 必 PASS (PBVI 是 POMDP solver 子模块, LCA 行为不变)

设计文档: discussions/2026-08-11-v089-design.md §2
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AlphaVector:
    """PBVI α-vector (v0.89.0-a).

    每个 α 对应一个 action: α = (action, values[n_states])
    values[s] = 在状态 s 上该 action 的值 (V(s) = Σ_b α(b) for action a)

    不可变 (frozen) 防止 solver 内部 mutation 干扰外部.
    跟 POMDPPolicy.select_arm 接口同构 (a=action, values 是值函数).
    """

    action: int
    values: np.ndarray  # shape (n_states,)

    def __repr__(self) -> str:
        return f"AlphaVector(action={self.action}, values={self.values.tolist()})"


class PBVI:
    """Point-Based Value Iteration 雏形 (v0.89.0-a, 算法本体).

    核心思想:
      - 在一组 belief points B = {b_1, ..., b_K} 上做 value iteration
      - 每个 α-vector 对应一个 action, values[n_states] 表示在每个状态上的值
      - backup: 对每个 b ∈ B, 对每个 action a, 算 V_a(b)
        V_a(b) = Σ_s b(s) * R(s, a) + γ * Σ_o P(o|b, a) * max_{α'} α'(b')
      - select_arm(b): argmax_a α_a(b) = argmax_a Σ_s α_a(s) * b(s)

    Attributes:
        belief_points:  评估的 belief 点集合 (List[np.ndarray], shape (n_states,))
        alpha_vectors:  当前迭代的 α-vector 集合 (List[AlphaVector], 初始空)
        gamma:          折扣因子 (默认 0.95)
        epsilon:        收敛阈值 (留 v0.89.0-b, 雏形不强制)
        n_iters:        最大迭代次数 (留 v0.89.0-b, 雏形不强制)
    """

    def __init__(
        self,
        belief_points: List[np.ndarray],
        gamma: float = 0.95,
        epsilon: float = 1e-4,
        n_iters: int = 50,
    ):
        if not belief_points:
            raise ValueError("PBVI: belief_points 不能为空")
        if not (0.0 < gamma <= 1.0):
            raise ValueError(f"PBVI: gamma={gamma} 必须 ∈ (0, 1]")
        if epsilon <= 0:
            raise ValueError(f"PBVI: epsilon={epsilon} 必须 > 0")
        if n_iters <= 0:
            raise ValueError(f"PBVI: n_iters={n_iters} 必须 > 0")

        self.belief_points = belief_points
        self.alpha_vectors: List[AlphaVector] = []
        self.gamma = float(gamma)
        self.epsilon = float(epsilon)
        self.n_iters = int(n_iters)

    def backup_step(
        self,
        transition: np.ndarray,
        observation_model: np.ndarray,
        reward: np.ndarray,
    ) -> List[AlphaVector]:
        """PBVI 单步 backup (v0.89.0-a).

        算法:
          对每个 action a (n_arms):
            对每个 belief point b (K):
              V_a(b) = Σ_s b(s) * R(s, a) + γ * Σ_o P(o|b, a) * max_{α'} α'(b')

        P(o|b, a) 计算 (per Sondik 1971):
          P(o|b, a) = Σ_s' O[o|s'] * Σ_s T[s'|s, a] * b(s)
          b'_a(s') = O[o|s'] * Σ_s T[s'|s, a] * b(s) / P(o|b, a)

        纯函数 (不修改 self.alpha_vectors, 新 α-vector 作为返回值).

        Args:
            transition:        shape (n_states, n_states, n_arms) — POMDPPolicy.transition
            observation_model: shape (n_observations, n_states)   — POMDPPolicy.observation_model
            reward:            shape (n_states, n_arms)            — POMDPPolicy.reward

        Returns:
            List[AlphaVector]: 每个 action 一个 α (action, values[K])

        防御性自检 [1]:
          - 输入 shape 不匹配 → ValueError
          - belief_points 维度不匹配 → ValueError
        """
        # 维度校验
        if transition.ndim != 3:
            raise ValueError(
                f"PBVI.backup_step: transition 必须是 3D (n_states, n_states, n_arms), "
                f"got shape={transition.shape}"
            )
        if observation_model.ndim != 2:
            raise ValueError(
                f"PBVI.backup_step: observation_model 必须是 2D (n_observations, n_states), "
                f"got shape={observation_model.shape}"
            )
        if reward.ndim != 2:
            raise ValueError(
                f"PBVI.backup_step: reward 必须是 2D (n_states, n_arms), "
                f"got shape={reward.shape}"
            )

        n_states = transition.shape[0]
        n_arms = transition.shape[2]
        n_observations = observation_model.shape[0]

        if reward.shape != (n_states, n_arms):
            raise ValueError(
                f"PBVI.backup_step: reward shape={reward.shape} 跟 transition 不匹配 "
                f"(expected ({n_states}, {n_arms}))"
            )
        if observation_model.shape[1] != n_states:
            raise ValueError(
                f"PBVI.backup_step: observation_model shape={observation_model.shape} "
                f"第二维={observation_model.shape[1]} 跟 n_states={n_states} 不匹配"
            )

        # belief_points 维度校验
        for b_idx, b in enumerate(self.belief_points):
            if b.shape != (n_states,):
                raise ValueError(
                    f"PBVI.backup_step: belief_points[{b_idx}] shape={b.shape} "
                    f"跟 n_states={n_states} 不匹配"
                )

        new_alphas: List[AlphaVector] = []

        for a in range(n_arms):
            values = np.zeros(len(self.belief_points))
            for b_idx, b in enumerate(self.belief_points):
                # 即时 reward: Σ_s b(s) * R(s, a)
                immediate = float(b @ reward[:, a])
                # 未来 expected value: γ * Σ_o P(o|b, a) * max_{α'} α'(b')
                future = 0.0
                for o in range(n_observations):
                    # b'(s') = O[o|s'] * T[:, :, a].T @ b
                    T_a = transition[:, :, a]
                    b_next_unnorm = observation_model[o] * (T_a.T @ b)
                    p_obs = b_next_unnorm.sum()
                    if p_obs > 0:
                        b_next = b_next_unnorm / p_obs
                        future += p_obs * self._alpha_value_at(b_next)
                values[b_idx] = immediate + self.gamma * future
            new_alphas.append(AlphaVector(action=a, values=values))

        return new_alphas

    def _alpha_value_at(self, belief: np.ndarray) -> float:
        """在给定 belief 上算 max α(b) (内部用).

        雏形 (a 阶段): 仅跟当前 alpha_vectors 比较 (无 α 时返 0.0).
        """
        if not self.alpha_vectors:
            return 0.0
        return max(float(α.values @ belief) for α in self.alpha_vectors)

    def alpha_value(self, belief: np.ndarray) -> float:
        """对外 API: 在给定 belief 上算 max α(b).

        Args:
            belief: shape (n_states,)

        Returns:
            float: max_a Σ_s α_a(s) * b(s) (无 α-vector 时返 0.0)
        """
        return self._alpha_value_at(belief)

    def best_action(self, belief: np.ndarray) -> int:
        """对外 API: argmax_a α_a(b).

        雏形: 返回 belief 上 α 值最大的 action.
        跟 POMDPPolicy.select_arm(context) 接口同构.

        Args:
            belief: shape (n_states,)

        Returns:
            int: arm 索引 [0, n_arms)
                 雏形退化: 无 alpha_vectors 时返 0
        """
        if not self.alpha_vectors:
            _log.warning(
                "PBVI.best_action: 无 alpha_vectors, 返 0 (退化, 调用方应先 solve)"
            )
            return 0
        best_a = self.alpha_vectors[0].action
        best_v = float(self.alpha_vectors[0].values @ belief)
        for α in self.alpha_vectors[1:]:
            v = float(α.values @ belief)
            if v > best_v:
                best_v = v
                best_a = α.action
        return int(best_a)

    def get_alpha_stats(self) -> dict:
        """获取 α-vector 统计 (调试用).

        Returns:
            dict 含:
              - n_alpha_vectors (int)
              - n_belief_points (int)
              - gamma / epsilon / n_iters
              - actions (List[int])  当前所有 α 的 action 列表
        """
        return {
            "n_alpha_vectors": len(self.alpha_vectors),
            "n_belief_points": len(self.belief_points),
            "gamma": self.gamma,
            "epsilon": self.epsilon,
            "n_iters": self.n_iters,
            "actions": [α.action for α in self.alpha_vectors],
        }


__all__ = [
    "AlphaVector",
    "PBVI",
]