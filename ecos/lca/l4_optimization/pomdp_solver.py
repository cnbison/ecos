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
        """PBVI 单步 backup (v0.89.0-b, 经典 PBVI / Sondik 1971 简化).

        算法 (对每个 action a, 输出 α-vector in state space):
          α_a[s] = R(s, a) + γ * Σ_o P(o|δ_s, a) * max_{α'} α'(b'_a,o)
          其中:
            δ_s = one-hot belief (state s)
            b'_a,o(s') = O[o|s'] * Σ_s' T[s'|s, a] * δ_s(s) / P(o|δ_s, a)
                      = O[o|s'] * T[s'|s, a] / P(o|δ_s, a)
            P(o|δ_s, a) = Σ_s' O[o|s'] * T[s'|s, a]

        纯函数 (不修改 self.alpha_vectors, 新 α-vector 作为返回值).
        belief_points 在 backup_step 中**不直接使用** (留 v0.89.0-c/d 阶段
        用于 coverage / reachable check). PBVI class 持有 belief_points
        作为 init anchor, 但 backup 是 state-space PBVI 简化.

        Args:
            transition:        shape (n_states, n_states, n_arms)
            observation_model: shape (n_observations, n_states)
            reward:            shape (n_states, n_arms)

        Returns:
            List[AlphaVector]: 每个 action 一个 α (action, values[n_states])

        防御性自检 [1]:
          - 输入 shape 不匹配 → ValueError
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

        new_alphas: List[AlphaVector] = []

        for a in range(n_arms):
            # α_a values shape (n_states,) — α_a[s] = V_a(δ_s)
            values = np.zeros(n_states)
            T_a = transition[:, :, a]  # shape (n_states, n_states)

            for s in range(n_states):
                # immediate reward 在 state s 选 action a
                immediate = float(reward[s, a])

                # future expected value
                future = 0.0
                for o in range(n_observations):
                    # b'_a,o(s') = O[o|s'] * T[s'|s, a]  (one-hot δ_s)
                    b_next_unnorm = observation_model[o] * T_a[:, s]
                    p_obs = b_next_unnorm.sum()
                    if p_obs > 0:
                        b_next = b_next_unnorm / p_obs
                        future += p_obs * self._alpha_value_at(b_next)

                values[s] = immediate + self.gamma * future

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

    def update_alpha_vectors(self, new_alphas: List[AlphaVector]) -> bool:
        """更新 α-vector + 收敛检测 (v0.89.0-b).

        算法:
          - 对每个 new_alpha (按 action 匹配), 算 values 跟旧 α 的 max abs diff
          - 收集 max_diff
          - 替换 self.alpha_vectors 为 new_alphas
          - max_diff < epsilon → 收敛 (返 True)

        Args:
            new_alphas: 新 α-vector 集合 (List[AlphaVector])

        Returns:
            bool: 是否收敛 (max_diff < epsilon)

        防御性自检 [1]:
          - new_alphas 为空 → False (退化, 不更新)
        """
        if not new_alphas:
            return False

        # 算 max_diff (按 action 匹配)
        max_diff = 0.0
        old_by_action = {α.action: α for α in self.alpha_vectors}
        for new_α in new_alphas:
            old_α = old_by_action.get(new_α.action)
            if old_α is not None and old_α.values.shape == new_α.values.shape:
                diff = float(np.max(np.abs(new_α.values - old_α.values)))
                if diff > max_diff:
                    max_diff = diff

        # 替换 (PBVI 简化: 直接替换)
        self.alpha_vectors = list(new_alphas)
        return max_diff < self.epsilon

    def solve(
        self,
        transition: np.ndarray,
        observation_model: np.ndarray,
        reward: np.ndarray,
    ) -> int:
        """PBVI 主算法: iterative backup + 收敛 (v0.89.0-b).

        算法:
          for i in 1..n_iters:
            new_alphas = backup_step(transition, O, reward)
            converged = update_alpha_vectors(new_alphas)
            if converged: 返 i
          返 n_iters (未收敛)

        Args:
            transition:        shape (n_states, n_states, n_arms)
            observation_model: shape (n_observations, n_states)
            reward:            shape (n_states, n_arms)

        Returns:
            int: 实际迭代次数 (1..n_iters)

        防御性自检 [1]:
          - 输入 shape 由 backup_step 校验 (传透)
        """
        for i in range(self.n_iters):
            new_alphas = self.backup_step(transition, observation_model, reward)
            converged = self.update_alpha_vectors(new_alphas)
            if converged:
                return i + 1
        return self.n_iters


__all__ = [
    "AlphaVector",
    "PBVI",
    "reachable_belief_points",
    "uniform_belief_points",
]


def reachable_belief_points(
    transition: np.ndarray,
    observation_model: np.ndarray,
    initial_belief: np.ndarray,
    n_steps: int = 5,
    n_samples_per_step: int = 4,
    seed: Optional[int] = None,
) -> List[np.ndarray]:
    """reachable belief point sampling (v0.89.0-b).

    简化算法:
      - 从 initial_belief 出发
      - 随机采样 (action, observation) 对, 算 next belief (跟 POMDP.bayes_update 同公式)
      - 收集 n_steps * n_samples_per_step 个 belief points
      - 加入 initial_belief 作为 anchor (确保起点覆盖)

    Args:
        transition:        shape (n_states, n_states, n_arms)
        observation_model: shape (n_observations, n_states)
        initial_belief:    shape (n_states,) 起点 belief
        n_steps:           采样步数 (默认 5)
        n_samples_per_step: 每步采样数 (默认 4)
        seed:              PRNG seed (None = 系统 entropy, 测试用固定 seed)

    Returns:
        List[np.ndarray]: belief points (每个 shape (n_states,))

    跟 POMDP.bayes_update 一致:
        b'(s') = O[o|s'] * Σ_s T[s'|s, a] * b(s) / P(o|b, a)
        P(o|b, a) = Σ_s' b'(s')

    防御性自检 [1]:
      - n_states 维度不匹配 → ValueError
      - n_steps / n_samples_per_step <= 0 → ValueError
    """
    if transition.ndim != 3:
        raise ValueError(
            f"reachable_belief_points: transition 必须是 3D, got shape={transition.shape}"
        )
    if observation_model.ndim != 2:
        raise ValueError(
            f"reachable_belief_points: observation_model 必须是 2D, got shape={observation_model.shape}"
        )
    if n_steps <= 0:
        raise ValueError(f"reachable_belief_points: n_steps={n_steps} 必须 > 0")
    if n_samples_per_step <= 0:
        raise ValueError(
            f"reachable_belief_points: n_samples_per_step={n_samples_per_step} 必须 > 0"
        )

    n_states = transition.shape[0]
    n_arms = transition.shape[2]
    n_observations = observation_model.shape[0]

    if observation_model.shape[1] != n_states:
        raise ValueError(
            f"reachable_belief_points: observation_model shape={observation_model.shape} "
            f"第二维跟 n_states={n_states} 不匹配"
        )
    if initial_belief.shape != (n_states,):
        raise ValueError(
            f"reachable_belief_points: initial_belief shape={initial_belief.shape} "
            f"跟 n_states={n_states} 不匹配"
        )

    rng = np.random.default_rng(seed)
    belief_points: List[np.ndarray] = [initial_belief.copy()]
    current = initial_belief.copy()

    for _ in range(n_steps):
        for _ in range(n_samples_per_step):
            a = int(rng.integers(0, n_arms))
            o = int(rng.integers(0, n_observations))
            # b'(s') = O[o|s'] * T[:, :, a].T @ b / P(o|b, a)
            b_next_unnorm = observation_model[o] * (transition[:, :, a].T @ current)
            p_obs = b_next_unnorm.sum()
            if p_obs > 0:
                current = b_next_unnorm / p_obs
                belief_points.append(current.copy())
    return belief_points


def uniform_belief_points(
    n_states: int = 4,
    n_samples: int = 10,
    seed: Optional[int] = None,
) -> List[np.ndarray]:
    """uniform simplex sampling (v0.89.0-b).

    用 Dirichlet(1, 1, ..., 1) = uniform on (n_states-1)-simplex.

    Args:
        n_states: 状态数量 (默认 4)
        n_samples: 采样数 (默认 10)
        seed:     PRNG seed (None = 系统 entropy, 测试用固定 seed)

    Returns:
        List[np.ndarray]: belief points (每个 shape (n_states,))

    防御性自检 [1]:
      - n_states / n_samples <= 0 → ValueError
    """
    if n_states <= 0:
        raise ValueError(f"uniform_belief_points: n_states={n_states} 必须 > 0")
    if n_samples <= 0:
        raise ValueError(f"uniform_belief_points: n_samples={n_samples} 必须 > 0")

    rng = np.random.default_rng(seed)
    return [
        rng.dirichlet(np.ones(n_states))
        for _ in range(n_samples)
    ]