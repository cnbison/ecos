"""POMDP Policy — 部分可观测 MDP 完整 (v0.88.0-c, 依赖型 T+R).

对应 12-kernel-mapping §1.3 Policy Engine:
    "POMDP Policy (部分可观测 MDP, Phase 6+)" → "POMDP 完整 (依赖型 T+R, v0.88.0-c)".

v0.88.0-c 范围 (Phase 7+ 第 1 个 sub-version, POMDP 雏形升级):
  - 4 状态 POMDP (Engaged / Frustrated / Bored / Confused)
  - **依赖型 T(s'|s, a)**: shape (n_states, n_states, n_arms) — 替换 v0.87.0-c 4x4 简化矩阵
    每个 action 有自己的 transition 矩阵 (选该 action 时, +0.1 跨状态概率)
  - **R(s, a) 固定 init**: 替换 v0.87.0-c random init (state s 偏好 arm 区间 [s*n_arms/n_states, (s+1)*n_arms/n_states))
  - **bayes_update(action, observation)**: Bayes update 考虑 action
    b'(s') ∝ O[o|s'] * Σ_s T[s'|s, a] * b(s)
  - select_arm: argmax_a Σ_s b(s) * R(s, a) (跟 v0.87.0-c 同, R shape 不变)
  - update(arm, context, reward): 仍仅追踪 arm_pull_counts (接口同构 LinUCB/Thompson)
  - dump_state / load_state: 7+ 字段, transition 加 action 维
    **老 snapshot 不兼容** (维度变化, per design doc §4.3)

v0.87.0-c 雏形限制 (已升级部分):
  - ~~Simplified transition (不依赖 action)~~ → v0.88.0-c: T(s'|s, a) 依赖 action ✅
  - ~~R(s, a) random init~~ → v0.88.0-c: 固定 init (per design doc §4.2) ✅
  - **仍限制** (推迟 v0.89+):
    - T(s'|s, a) 固定, 不学
    - R(s, a) 固定 init, 不学
    - 不实现 point-based solver (α-vector, PBVI, Perseus)
    - 不实现完整 POMDP solver (SARSOP, etc.)

向后兼容:
  - 接口同构 LinUCB/Thompson (select_arm / update / dump_state / load_state 名称不变)
  - **bayes_update signature 变化**: v0.87.0-c `bayes_update(observation)` → v0.88.0-c `bayes_update(action, observation)`
  - 防御性自检 [8] 仍 hard block (POMDPPolicy 不 mutate state)
  - H3-c4 canary 必 PASS (POMDP 只改 select_intervention / update, classroom 行为不变)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional

import numpy as np

if TYPE_CHECKING:
    from ecos.lca.l4_optimization.pomdp_solver import PBVI

_log = logging.getLogger(__name__)

# v0.89.0-c: schema version for dump_state / load_state 老 snapshot 检测
# v0.88.0-c 老 snapshot raise ValueError (per design doc §7.5 + 防御性自检 [5])
SCHEMA_VERSION = "0.89.0-c"


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
    """POMDP solver (v0.88.0-c, 依赖型 T+R).

    4 状态:
      - 0: Engaged   (投入)
      - 1: Frustrated (挫败)
      - 2: Bored     (无聊)
      - 3: Confused  (困惑)

    Belief state: b = P(state) (4-dim 概率向量, 和 = 1)
    Transition:    **T[s'|s, a]** (n_states x n_states x n_arms, **依赖 action**)
                   - base T[s'|s]: 强 self-loop (0.7) + 弱跨 (0.1) (跟 v0.87.0-c 同)
                   - perturbation[a]: 选该 action 时 +0.1 跨状态概率 (off-diagonal)
    Observation:   O[o|s] (n_obs per state, 跟 v0.87.0-c 同, 不依赖 action)
    Reward:        **R(s, a) 固定 init** (n_states x n_arms, 替换 v0.87.0-c random)
                   - state s 偏好 arm 区间 [s*n_arms/n_states, (s+1)*n_arms/n_states) (高 reward)
                   - 其他 arm 区间 (低 reward)
                   - PRNG seed 可重现

    算法:
      - select_arm: argmax_a Σ_s b(s) * R(s, a) (跟 v0.87.0-c 同)
      - **bayes_update(action, observation)**: b'(s') ∝ O[o|s'] * Σ_s T[s'|s, a] * b(s)
        (v0.88.0-c 升级: 考虑 action)
      - update(arm, context, reward): 仅更新 arm_pull_counts (v0.87.0-c 接口同构)

    适用:
      - reward ∈ [0, 1] (any float)
      - 4 状态 (Engaged/Frustrated/Bored/Confused)
      - **依赖 action 的 T**: 不同 action 导致不同 belief update (v0.88.0-c 关键升级)
      - **固定 R init**: 测试可重现 (PRNG seed)

    防御性自检 [1]:
      - bayes_update 越界 action / observation _log.warning 跳过
      - select_arm n_arms=0 返 0 (degenerate)
      - dump_state schema_version 不匹配 _log.warning + raise
    """

    STATE_NAMES: ClassVar[tuple] = ("Engaged", "Frustrated", "Bored", "Confused")

    def __init__(
        self,
        n_arms: int = 10,
        n_states: int = 4,
        n_observations: int = 4,
        seed: Optional[int] = None,
        use_pbvi: bool = True,
        pbvi_gamma: float = 0.95,
        pbvi_epsilon: float = 1e-4,
        pbvi_n_iters: int = 50,
        pbvi_n_belief_points: int = 16,
        pbvi_seed: Optional[int] = None,
    ):
        if n_states <= 0:
            raise ValueError(f"POMDPPolicy: n_states={n_states} 必须 > 0")
        self.n_arms = int(n_arms)
        self.n_states = int(n_states)
        self.n_observations = int(n_observations)
        self._rng = np.random.default_rng(seed)

        # Belief state: 概率向量 (和 = 1, uniform prior)
        self.belief_state: np.ndarray = np.ones(self.n_states) / self.n_states

        # v0.88.0-c: T[s'|s, a] 依赖 action (n_states x n_states x n_arms)
        # base T[s'|s]: 强 self-loop (0.7) + 弱跨 (0.1)
        # perturbation[a]: 选该 action 时 +0.1 跨状态概率 (off-diagonal only)
        self.transition: np.ndarray = self._init_transition_matrix()

        # Observation model: O[o|s] (n_observations x n_states, 跟 v0.87.0-c 同, 不依赖 action)
        obs_off = (1.0 - 0.6) / max(1, self.n_states - 1)
        self.observation_model: np.ndarray = np.full(
            (self.n_observations, self.n_states), obs_off
        )
        for s in range(self.n_states):
            self.observation_model[s, s] = 0.6
        self.observation_model = self.observation_model / self.observation_model.sum(axis=1, keepdims=True)

        # v0.88.0-c: R(s, a) 固定 init (替换 v0.87.0-c random uniform init)
        self.reward: np.ndarray = self._init_reward_matrix(seed)

        # Stats
        self.arm_pull_counts: np.ndarray = np.zeros(self.n_arms, dtype=int)
        self.total_observations: int = 0

        # v0.89.0-c: PBVI solver (point-based value iteration)
        # use_pbvi=True 默认开 (PBVI 是更精确求解), False 退化到 QMDP (v0.88.0-c)
        self.use_pbvi = bool(use_pbvi)
        self.pbvi_gamma = float(pbvi_gamma)
        self.pbvi_epsilon = float(pbvi_epsilon)
        self.pbvi_n_iters = int(pbvi_n_iters)
        self.pbvi_n_belief_points = int(pbvi_n_belief_points)
        self.pbvi_seed = pbvi_seed
        # solver 懒加载 (首次 select_arm / solve_pbvi 才创建)
        self.solver: Optional["PBVI"] = None

    def _init_transition_matrix(self) -> np.ndarray:
        """v0.88.0-c: 初始化 T[s'|s, a] (n_states x n_states x n_arms), 依赖 action.

        算法 (per design doc §4.2 intent):
          - base T[s'|s]: 强 self-loop (0.7) + 弱跨 (0.1) (跟 v0.87.0-c 同)
          - perturbation[a]: 选该 action 时跨状态概率偏移, 强度依赖 action
            → a=0: +0.05 (最小), a=n_arms-1: +0.15 (最大)
            → 不同 action 导致不同 transition 矩阵 (T 真正 action-dependent)
          - 归一化: T[a] 每行 sum = 1 (valid stochastic matrix)
        """
        transition = np.zeros((self.n_states, self.n_states, self.n_arms))
        for a in range(self.n_arms):
            base = np.eye(self.n_states) * 0.7 + np.ones((self.n_states, self.n_states)) * 0.1
            # v0.88.0-c: perturbation 强度依赖 action (per design doc §4.2 intent)
            # 设计意图: 不同 action 导致不同跨状态概率 (a 越大, cross-state 越强)
            perturbation_strength = 0.05 + 0.10 * (a / max(1, self.n_arms - 1))
            perturbation = np.ones((self.n_states, self.n_states)) * perturbation_strength
            np.fill_diagonal(perturbation, 0.0)  # off-diagonal only
            T_a = base + perturbation
            # 归一化 row sum = 1
            transition[:, :, a] = T_a / T_a.sum(axis=1, keepdims=True)
        return transition

    def _init_reward_matrix(self, seed: Optional[int]) -> np.ndarray:
        """v0.88.0-c: 固定 R(s, a) init (替换 v0.87.0-c random uniform).

        规则 (per design doc §4.2):
          - state s 偏好 arm 区间 [s*n_arms/n_states, (s+1)*n_arms/n_states)
            → 该区间 R[s, a] ∈ U(0.5, 1.0) (高 reward)
          - 其他 arm 区间 R[s, a] ∈ U(0.0, 0.5) (低 reward)
        """
        rng = np.random.default_rng(seed)
        R = np.zeros((self.n_states, self.n_arms))
        for s in range(self.n_states):
            start = (s * self.n_arms // self.n_states)
            end = ((s + 1) * self.n_arms // self.n_states)
            R[s, start:end] = rng.uniform(0.5, 1.0, end - start)
            if start > 0:
                R[s, :start] = rng.uniform(0.0, 0.5, start)
            if end < self.n_arms:
                R[s, end:] = rng.uniform(0.0, 0.5, self.n_arms - end)
        return R

    def select_arm(self, context: Optional[np.ndarray] = None) -> int:
        """argmax_a: PBVI 路径 (v0.89.0-c) 或 QMDP fallback (v0.88.0-c).

        PBVI 路径 (use_pbvi=True, 默认):
          - 懒加载 PBVI solver (reachable_belief_points 从 belief_state 出发)
          - solver.solve() 直到收敛 (首次 select_arm 时)
          - argmax_a α_a(belief_state) = argmax_a Σ_s α_a(s) * b(s)

        QMDP fallback (use_pbvi=False):
          - argmax_a Σ_s b(s) * R(s, a) (v0.88.0-c 行为, 跟 v0.87.0-c 同)

        Args:
            context: 上下文向量 (LinUCB 接口同构, POMDP 不依赖 context, 忽略)

        Returns:
            arm 索引 [0, n_arms)

        防御性:
          - n_arms=0 返 0 (degenerate)
          - PBVI 路径 solver 初始化失败 → fallback QMDP + _log.warning
        """
        if self.n_arms <= 0:
            _log.warning("POMDPPolicy.select_arm: n_arms=%s, 返 0 (degenerate)", self.n_arms)
            return 0

        if self.use_pbvi:
            try:
                solver = self._init_pbvi_solver()
                if not solver.alpha_vectors:
                    # 首次: 触发 solve (PBVI iterative backup 直到收敛)
                    solver.solve(self.transition, self.observation_model, self.reward)
                return solver.best_action(self.belief_state)
            except Exception as e:
                # 防御性: PBVI 失败 → fallback QMDP (避免 NaN / 崩溃)
                _log.warning(
                    "POMDPPolicy.select_arm: PBVI 路径失败 (%s), fallback 到 QMDP",
                    e,
                )

        # QMDP fallback (v0.88.0-c 行为)
        expected_reward = self.belief_state @ self.reward
        return int(np.argmax(expected_reward))

    def _init_pbvi_solver(self) -> "PBVI":
        """懒加载 PBVI solver (v0.89.0-c).

        首次调用时构造 PBVI:
          - belief_points = reachable_belief_points(self.transition, O, self.belief_state, ...)
            起点 = 当前 belief_state
          - 内部随机 sample (action, observation) → next belief (跟 bayes_update 同公式)
        后续调用直接返 cached solver (self.solver).

        Returns:
            PBVI: solver 实例 (cached after first call)

        防御性: lazy import 避免循环依赖 (pomdp_solver 引用 pomdp reward 公式)
        """
        if self.solver is None:
            from ecos.lca.l4_optimization.pomdp_solver import (
                PBVI,
                reachable_belief_points,
            )
            belief_points = reachable_belief_points(
                self.transition,
                self.observation_model,
                self.belief_state,
                n_steps=3,
                n_samples_per_step=max(1, self.pbvi_n_belief_points // 3 - 1),
                seed=self.pbvi_seed,
            )
            self.solver = PBVI(
                belief_points=belief_points,
                gamma=self.pbvi_gamma,
                epsilon=self.pbvi_epsilon,
                n_iters=self.pbvi_n_iters,
            )
        return self.solver

    def solve_pbvi(self) -> int:
        """显式触发 PBVI solve (v0.89.0-c, 幂等: v0.89.0-d).

        懒加载 solver + 触发 iterative backup 直到收敛. 返实际迭代次数.
        Production 由 Runtime plan / LCAEngine.select_intervention 显式触发 (v0.89.0-d).

        幂等 (v0.89.0-d): 同一 POMDPPolicy 实例上, 当 solver.alpha_vectors 已
        非空 (上次解的 α 缓存) → 直接返 0, 跳过重复 backup. 仍要重新 solve
        时, 调用方应 reset (重新 _init_pbvi_solver / 显式清空 solver.alpha_vectors).

        Returns:
            int: 实际迭代次数 (1..pbvi_n_iters); 0 = 已是上次解, 跳过
        """
        solver = self._init_pbvi_solver()
        if solver.alpha_vectors:
            return 0
        return solver.solve(self.transition, self.observation_model, self.reward)

    def update(self, arm: int, context: Optional[np.ndarray] = None, reward: float = 0.0) -> None:
        """Update arm_pull_counts (简化, 不学 transition / observation model).

        跟 v0.87.0-c 接口同构 (LinUCB/Thompson 一致), 不接受 action feedback.
        POMDP 完整 update 需要 observation feedback (bayes_update 处理), 跟 update 分开.

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
        clamped = max(0.0, min(1.0, float(reward)))
        self.arm_pull_counts[arm] += 1

    def bayes_update(self, action: int, observation: int) -> None:
        """v0.88.0-c: Bayesian belief update (考虑 action, T(s'|s, a) 依赖 action).

        b'(s') ∝ O[o|s'] * Σ_s T[s'|s, a] * b(s)

        Args:
            action:      int [0, n_arms), 上次 select 的 arm (POMDP 依赖 action)
            observation: int [0, n_observations), 答题 reaction 量化

        v0.88.0-c 关键升级: bayes_update 现在考虑 action (跟 v0.87.0-c 区分):
          - v0.87.0-c: bayes_update(observation) — T 不依赖 action, action 无意义
          - v0.88.0-c: bayes_update(action, observation) — T 依赖 action, 不同 action → 不同 posterior

        防御性自检 [1]: 越界 action / observation _log.warning 跳过 (不 raise)
        """
        action_int = int(action)
        observation_int = int(observation)
        if not (0 <= action_int < self.n_arms):
            _log.warning(
                "POMDPPolicy.bayes_update: action 越界 (action=%s, n_arms=%s), 跳过",
                action, self.n_arms,
            )
            return
        if not (0 <= observation_int < self.n_observations):
            _log.warning(
                "POMDPPolicy.bayes_update: observation 越界 (obs=%s, n_obs=%s), 跳过",
                observation, self.n_observations,
            )
            return
        # Predict: b_pred[s'] = Σ_s T[s'|s, a] * b(s)
        b_pred = self.transition[:, :, action_int].T @ self.belief_state
        # Update: b_post[s'] ∝ O[obs|s'] * b_pred[s']
        b_post = self.observation_model[observation_int] * b_pred
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
        """导出状态 (v0.89.0-c schema, v0.88.0-c / v0.87.0-c 老 snapshot 不兼容).

        Returns:
            dict 含:
              - schema_version (str)  "0.89.0-c" (老 snapshot raise per 防御性自检 [5])
              - n_arms / n_states / n_observations
              - belief_state (List[float])
              - transition (List[List[List[float]]])  n_states x n_states x n_arms (3D, v0.88.0-c 升级)
              - observation_model (List[List[float]])  n_obs x n_states
              - reward (List[List[float]])  n_states x n_arms (固定 init, v0.88.0-c 升级)
              - arm_pull_counts (List[int])
              - total_observations (int)
              - use_pbvi (bool)  v0.89.0-c PBVI 开关
              - pbvi_config (Dict)  PBVI 配置 (gamma / epsilon / n_iters / n_belief_points)
              - solver_state (Dict)  PBVI solver 状态 (alpha_vectors + belief_points, lazy 兜底 None)
        """
        pbvi_config = {
            "gamma": self.pbvi_gamma,
            "epsilon": self.pbvi_epsilon,
            "n_iters": self.pbvi_n_iters,
            "n_belief_points": self.pbvi_n_belief_points,
        }
        # solver_state 懒加载兜底: 未初始化时存 None (load_state 时重建)
        if self.solver is None:
            solver_state = None
        else:
            solver_state = {
                "alpha_vectors": [
                    {"action": α.action, "values": α.values.tolist()}
                    for α in self.solver.alpha_vectors
                ],
                "belief_points": [b.tolist() for b in self.solver.belief_points],
            }
        return {
            "schema_version": SCHEMA_VERSION,
            "n_arms": self.n_arms,
            "n_states": self.n_states,
            "n_observations": self.n_observations,
            "belief_state": self.belief_state.tolist(),
            "transition": self.transition.tolist(),
            "observation_model": self.observation_model.tolist(),
            "reward": self.reward.tolist(),
            "arm_pull_counts": self.arm_pull_counts.tolist(),
            "total_observations": self.total_observations,
            "use_pbvi": self.use_pbvi,
            "pbvi_config": pbvi_config,
            "solver_state": solver_state,
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        """加载状态 (v0.89.0-c schema 校验, 防御性自检 [5]).

        v0.89.0-c snapshot 包含 PBVI 开关、配置和可选 solver 状态；老
        v0.88.0-c / v0.87.0-c snapshot 不兼容，必须迁移或丢弃。

        Args:
            state: dump_state() 导出的 dict

        防御性自检 [5]:
          - schema_version 不匹配 → raise (老 snapshot 不兼容)
          - n_arms / n_states / n_observations 必须匹配
          - transition 形状必须是 3D (n_states x n_states x n_arms)
          - reward 长度必须是 n_states
        """
        schema_version = state.get("schema_version")
        if schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"POMDPPolicy schema_version 不匹配: "
                f"expected={SCHEMA_VERSION!r}, got={schema_version!r}. "
                f"老 snapshot 不兼容, 需要迁移或丢弃."
            )

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

        # v0.88.0-c: transition 必须是 3D (n_states x n_states x n_arms)
        transition = state.get("transition") or []
        if len(transition) != self.n_states:
            raise ValueError(
                f"POMDPPolicy state transition 第一维不匹配 (expected={self.n_states}, got={len(transition)})"
            )
        # 第二维 + 第三维校验 (防御性: 防止 (n_states, n_states, 1) 等退化 shape)
        for a_idx, T_a in enumerate(transition):
            if len(T_a) != self.n_states:
                raise ValueError(
                    f"POMDPPolicy state transition 第二维不匹配 (action={a_idx}, expected={self.n_states}, got={len(T_a)})"
                )
            if not isinstance(T_a[0], list):
                raise ValueError(
                    f"POMDPPolicy state transition 第三维必须是 list "
                    f"(action={a_idx}, got type={type(T_a[0]).__name__}, 期望 3D array)"
                )
            if len(T_a[0]) != self.n_arms:
                raise ValueError(
                    f"POMDPPolicy state transition 第三维不匹配 (action={a_idx}, expected={self.n_arms}, got={len(T_a[0])})"
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

        self.use_pbvi = bool(state.get("use_pbvi", self.use_pbvi))
        pbvi_config = state.get("pbvi_config") or {}
        self.pbvi_gamma = float(pbvi_config.get("gamma", self.pbvi_gamma))
        self.pbvi_epsilon = float(pbvi_config.get("epsilon", self.pbvi_epsilon))
        self.pbvi_n_iters = int(pbvi_config.get("n_iters", self.pbvi_n_iters))
        self.pbvi_n_belief_points = int(
            pbvi_config.get("n_belief_points", self.pbvi_n_belief_points)
        )

        solver_state = state.get("solver_state")
        self.solver = None
        if solver_state is not None:
            belief_points = solver_state.get("belief_points") or []
            alpha_vectors = solver_state.get("alpha_vectors") or []
            if not belief_points:
                raise ValueError("POMDPPolicy solver_state belief_points 不能为空")
            solver = self._init_pbvi_solver()
            solver.belief_points = [np.asarray(b, dtype=float) for b in belief_points]
            restored_alphas = []
            from ecos.lca.l4_optimization.pomdp_solver import AlphaVector
            for item in alpha_vectors:
                values = np.asarray(item["values"], dtype=float)
                if values.shape != (self.n_states,):
                    raise ValueError(
                        "POMDPPolicy solver_state alpha_vector values 长度不匹配 "
                        f"(expected={self.n_states}, got={values.shape})"
                    )
                restored_alphas.append(AlphaVector(action=int(item["action"]), values=values))
            solver.alpha_vectors = restored_alphas

__all__ = [
    "POMDPPolicy",
    "POMDPConfig",
    "SCHEMA_VERSION",
]