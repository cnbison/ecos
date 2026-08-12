"""L4 LCAPolicyLearner——LinUCB + Thompson Sampling + POMDP + Intervention 候选映射.

对应：
  - research/10-engineering/02-lca-policy-engine.md §4.2 LCAPolicyLearner
  - v0.86.0-c: Thompson Sampling 扩展 (Policy Engine 第二个 Policy)
  - v0.87.0-c/d: POMDP Policy 扩展 (Policy Engine 第三个 Policy)
  - v0.88.0-c: POMDP 依赖型 T+R (T 真正 action-dependent)
  - v0.88.0-d: POMDP action observation feedback 集成 Runtime

职责：
  - 把 BeliefState 编码成 LinUCB 上下文向量（16 维）
  - 维护 Intervention 候选池（arm 索引 → Intervention）
  - 提供 select_intervention(belief_state, candidates) 和 update(...)
  - v0.86.0-c: 根据 policy_type ("linucb" / "thompson") 委托不同 bandit
  - v0.87.0-d: 根据 policy_type ("pomdp") 委托 POMDPPolicy
  - v0.88.0-d: POMDP 路径接受 observation feedback (bayes_update(action, obs))
"""

from __future__ import annotations

import logging
from typing import Dict, List, Literal, Optional

import numpy as np

from ...cta.belief_state import BeliefState, BloomLevel
from ..intervention import Intervention
from .linucb import BanditConfig, LinUCB
from .pomdp import POMDPPolicy
from .thompson import ThompsonSampling

_log = logging.getLogger(__name__)


# v0.86.0-c: policy_type 合法值 (v0.87.0-d 扩展到 3 值)
PolicyType = Literal["linucb", "thompson", "pomdp"]


class LCAPolicyLearner:
    """LCA 策略学习器——LinUCB / Thompson / POMDP 包装 + 上下文构建.

    v0.86.0-c 起支持 2 种 policy, v0.87.0-d 扩展到 3 种 (通过 policy_type 切换):
      - "linucb" (默认): 上下文 Bandit, 16 维 context, UCB 算法
      - "thompson" (v0.86.0-c): 贝叶斯 Bandit, Beta(α, β) 每 arm, Thompson Sampling
      - "pomdp" (v0.87.0-d): 部分可观测 MDP, 4 状态 (Engaged/Frustrated/Bored/Confused),
                              Bayesian belief inference (4 状态 Bayesian)

    用法：
        # 默认 LinUCB
        learner = LCAPolicyLearner(BanditConfig(n_arms=10))
        # 或 Thompson Sampling
        learner = LCAPolicyLearner(BanditConfig(n_arms=10), policy_type="thompson",
                                    thompson_seed=42)
        # 或 POMDP
        learner = LCAPolicyLearner(BanditConfig(n_arms=10), policy_type="pomdp",
                                    pomdp_seed=42)
        intervention = learner.select_intervention(belief_state, candidate_list)
        # 观测到 reward 后
        learner.update(intervention, belief_state, reward=state_delta)
    """

    # Context dim: 5 (5D theta) + 6 (Bloom) + 5 (DNA) = 16
    CONTEXT_DIM = 16
    # v0.75 P0-m: 启用 arm features 时追加的维度 (intervention.difficulty)
    ARM_FEATURE_DIM = 1

    def __init__(
        self,
        config: BanditConfig | None = None,
        policy_type: str = "linucb",
        thompson_seed: Optional[int] = None,
        pomdp_seed: Optional[int] = None,
        pomdp_use_pbvi: Optional[bool] = None,
        pomdp_use_learned_t_r: Optional[bool] = None,
    ):
        # v0.87.0-d: 校验 policy_type (3 值)
        if policy_type not in ("linucb", "thompson", "pomdp"):
            raise ValueError(
                f"LCAPolicyLearner: 未知 policy_type={policy_type!r}, 应为 'linucb' / 'thompson' / 'pomdp'"
            )
        self.policy_type: str = policy_type
        self.config = config or BanditConfig()
        # v0.75 P0-m: 启用 arm features 时 context_dim 从 16 -> 17
        if self.config.use_arm_features:
            self.config.context_dim = self.CONTEXT_DIM + self.ARM_FEATURE_DIM
        elif self.config.context_dim != self.CONTEXT_DIM:
            # 旧路径: 强制 spec 默认 16 维
            self.config.context_dim = self.CONTEXT_DIM
        self.bandit = LinUCB(
            n_arms=self.config.n_arms,
            context_dim=self.config.context_dim,
            alpha=self.config.alpha,
            decay_factor=self.config.decay_factor,  # v0.75.3 H3-c3
        )
        # v0.86.0-c: Thompson Sampling 实例 (仅 policy_type=="thompson" 时创建)
        self.thompson: Optional[ThompsonSampling] = None
        if policy_type == "thompson":
            self.thompson = ThompsonSampling(
                n_arms=self.config.n_arms,
                seed=thompson_seed,
            )
        # v0.87.0-d: POMDP Policy 实例 (仅 policy_type=="pomdp" 时创建)
        # v0.89.0-d: 显式传 use_pbvi (默认 None → 走 POMDPPolicy 默认 True)
        # v0.90.0-d: 显式传 use_learned_t_r (默认 None → 走 POMDPPolicy 默认 True)
        self.pomdp: Optional[POMDPPolicy] = None
        if policy_type == "pomdp":
            self.pomdp = POMDPPolicy(
                n_arms=self.config.n_arms,
                seed=pomdp_seed,
                use_pbvi=True if pomdp_use_pbvi is None else bool(pomdp_use_pbvi),
                use_learned_t_r=True if pomdp_use_learned_t_r is None else bool(pomdp_use_learned_t_r),
            )
        # Arm 索引 → 候选干预 hash（用于 update 时反查）
        self._arm_fingerprints: Dict[int, str] = {}
        self._last_arm: int = -1
        # v0.75.3 H3-c3: intervention_id -> arm 映射 (只追加, 不覆盖)
        #   背景: _arm_fingerprints[arm] 在同 arm 连续被选时被覆盖, 上一轮 intervention_id 丢失,
        #         _lookup_arm 返回 None, LinUCB.update 被跳过.
        #         lbc003 round 15+ arm 0 连续被选 47 次, 但只有 1 次 update 成功.
        #   修复: 维护 _intervention_to_arm dict, select_intervention 时追加, _lookup_arm 优先用它.
        self._intervention_to_arm: Dict[str, int] = {}
        # v0.71.0: 每 arm 惩罚计数器 (策略质疑路径用, 防止 A 矩阵反复 *10 爆炸)
        #   背景: lbc003 触发 50 次策略质疑 -> A 矩阵放大 1.6e+05 倍 -> θ ≈ 0 -> V3 预测永远 ~0.11
        #   修复: 限制每 arm 最多惩罚 penalty_max 次 (默认 3), 超过不再 *=10
        self._penalty_counts: List[int] = [0] * self.config.n_arms
        # v0.88.0-d: POMDP observation feedback (from last update)
        #   None = 首次 select 无 observation, 不调 bayes_update
        #   int = 上次 update 产出的 observation, 下次 select 之前调 bayes_update(_last_arm, obs)
        self._last_observation: Optional[int] = None

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

        v0.75 P0-m: 启用 use_arm_features 时, 每个候选评估 (16 + difficulty) = 17 维
                    context, 选 UCB 最高的 (per-arm context 模式)
        """
        if not candidate_interventions:
            raise ValueError("candidate_interventions 不能为空")

        # v0.86.0-c: Thompson Sampling 路径 (non-contextual, 忽略 context)
        if self.policy_type == "thompson" and self.thompson is not None:
            arm = self.thompson.select_arm(context=None)
            self._last_arm = arm
            idx = arm % len(candidate_interventions)
            chosen = candidate_interventions[idx]
            self._arm_fingerprints[arm] = chosen.intervention_id
            self._intervention_to_arm[chosen.intervention_id] = arm
            return chosen

        # v0.87.0-d: POMDP 路径 (non-contextual, 走 belief_state)
        # v0.88.0-d: POMDP 路径接受 action observation feedback (T(s'|s,a) 依赖 action)
        # v0.89.0-d: POMDP 路径默认走 PBVI (v0.89.0-c 集成); 显式 solve_pbvi 触发收敛
        if self.policy_type == "pomdp" and self.pomdp is not None:
            # v0.88.0-d: 在 select 前消化上次 observation (bayes_update 考虑 action)
            # 这是 v0.88.0-c 依赖型 T+R 的关键集成点: action 影响 transition, observation 影响 posterior
            if self._last_observation is not None and self._last_arm >= 0:
                self.pomdp.bayes_update(self._last_arm, self._last_observation)
                self._last_observation = None  # 消费后清空 (避免重复消费)
            # v0.89.0-d: 显式 solve_pbvi (首次 select 走 PBVI 前必须收敛; PBVI 内部 α-vector 缓存保证幂等)
            try:
                self.pomdp.solve_pbvi()
            except Exception as e:  # noqa: BLE001
                _log.warning(
                    "LCAPolicyLearner.select_intervention: solve_pbvi 失败 (%s), 退化到 select_arm 内 fallback",
                    e,
                )
            arm = self.pomdp.select_arm(context=None)
            self._last_arm = arm
            idx = arm % len(candidate_interventions)
            chosen = candidate_interventions[idx]
            self._arm_fingerprints[arm] = chosen.intervention_id
            self._intervention_to_arm[chosen.intervention_id] = arm
            return chosen

        # LinUCB 路径 (现有)
        if not self.config.use_arm_features:
            # 旧路径: 16 维 shared context, 所有 arm 共享
            context = self._build_context(belief_state)
            arm = self.bandit.select_arm(context)
            self._last_arm = arm
            idx = arm % len(candidate_interventions)
            chosen = candidate_interventions[idx]
            self._arm_fingerprints[arm] = chosen.intervention_id
            self._intervention_to_arm[chosen.intervention_id] = arm  # v0.75.3 H3-c3
            return chosen

        # v0.75 P0-m 新路径: per-candidate context, 每个候选独立评估
        base = self._build_context(belief_state)
        best_arm, best_score = -1, -float("inf")
        for i, cand in enumerate(candidate_interventions):
            arm_idx = i % self.config.n_arms
            ctx = self._build_context(belief_state, intervention=cand)
            score = self.bandit.score_arm(arm_idx, ctx)
            if score > best_score:
                best_arm, best_score = arm_idx, score
        self._last_arm = best_arm
        idx = best_arm % len(candidate_interventions)
        chosen = candidate_interventions[idx]
        self._arm_fingerprints[best_arm] = chosen.intervention_id
        self._intervention_to_arm[chosen.intervention_id] = best_arm  # v0.75.3 H3-c3
        return chosen

    def update(
        self,
        intervention: Intervention,
        belief_state: BeliefState,
        reward: float,
        observation: Optional[int] = None,
    ) -> None:
        """基于干预效果更新 LinUCB.

        Args:
            intervention: 之前选中的干预
            belief_state: 干预后的 CTA 状态
            reward: 状态增量（state_delta），已被调用方归一化到 [0, 1]
            observation: v0.90.0-d 新增. POMDP observation ∈ [0, n_observations);
                         None (LinUCB/Thompson) 走老路径; int (POMDP) 触发 _update_t_r.

        v0.75 P0-m: 启用 use_arm_features 时, context 重建时附 intervention.difficulty
        v0.88.0-d: POMDP update 同时存储 observation (下次 select 消费)
        v0.90.0-d: POMDP observation 参数透传到 POMDPPolicy.update (触发 _update_t_r 学 T/R)
        """
        # v0.86.0-c: Thompson Sampling 路径 (non-contextual)
        if self.policy_type == "thompson" and self.thompson is not None:
            arm = self._lookup_arm(intervention)
            if arm is None:
                return
            clamped = max(
                self.config.min_reward,
                min(self.config.max_reward, reward),
            )
            self.thompson.update(arm, context=None, reward=clamped)
            return

        # v0.87.0-d: POMDP 路径 (non-contextual, 简化 update)
        # v0.88.0-d: POMDP update 同时存储 observation (下次 select 消费)
        # v0.90.0-d: POMDP observation 参数透传到 POMDPPolicy.update (触发 _update_t_r)
        if self.policy_type == "pomdp" and self.pomdp is not None:
            arm = self._lookup_arm(intervention)
            if arm is None:
                return
            clamped = max(
                self.config.min_reward,
                min(self.config.max_reward, reward),
            )
            # v0.90.0-d: observation 透传到 POMDPPolicy.update (None → 不学, int → _update_t_r)
            self.pomdp.update(arm, context=None, reward=clamped, observation=observation)
            # v0.88.0-d: reward → observation (discretize) → 下次 select 消费 bayes_update
            #            (兜底, 让 LCAEngine 不传 obs 时也能维持原 v0.88.0-d 行为)
            self._last_observation = self._reward_to_observation(clamped)
            return

        # LinUCB 路径 (现有)
        # v0.75 P0-m: 重建跟 select 时一样的 context (含 intervention.difficulty)
        if self.config.use_arm_features:
            context = self._build_context(belief_state, intervention=intervention)
        else:
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
    # v0.71.0: LinUCB 惩罚机制 (策略质疑路径用, 防止 A 矩阵爆炸)
    # ---------------------------------------------------------------

    # v0.71.0: 默认每 arm 最多惩罚 1 次.
    #   实验数据 (lbc003 56 道题重放):
    #     PENALTY_MAX=1 -> V3 ECE=0.5737 (A 放大 10 倍, θ 范数仍可读)
    #     PENALTY_MAX=2 -> V3 ECE=0.7320 (A 放大 100 倍)
    #     PENALTY_MAX=3 -> V3 ECE=0.7529 (A 放大 1000 倍)
    #     PENALTY_MAX=5 -> V3 ECE=0.7553 (A 放大 10 万倍)
    #   结论: 1 次惩罚已够让 LinUCB 知道 arm 不好, 多次惩罚反而毁模型.
    #   注: V3 ECE 仍 0.57 远超 0.10 阈值, 但这是 LinUCB θ@x 预测能力本身的问题,
    #       不是惩罚机制问题. 后续 v0.72+ 评估是否换 confidence 指标.
    PENALTY_MAX: int = 1

    def apply_penalty(self, arm: int, factor: float = 10.0) -> bool:
        """v0.71.0: 对指定 arm 应用 LinUCB A 矩阵惩罚 (有次数上限).

        策略质疑路径调用: 当某 arm 表现无效 (actual_outcome 低) 时,
        放大其 A 矩阵降低 UCB, 让 LinUCB 倾向其他 arm.

        v0.71.0 修复 (lbc003 V3=0.11 根因):
          之前 strategy_challenge.py 直接 bandit.A[last_arm] *= 10 反复执行,
          lbc003 触发 50 次后 A 矩阵放大 1.6e+05 倍, θ 趋近 0, V3 预测永远 ~0.11.
          修复: 限制每 arm 最多惩罚 PENALTY_MAX 次 (默认 3), 超过不再惩罚.

        Args:
            arm: 要惩罚的 arm 索引
            factor: 惩罚因子 (默认 10.0, 跟 LINUCB_PENALTY_FACTOR 一致)

        Returns:
            True = 惩罚已应用; False = 已达上限, 跳过惩罚

        防御性自检 [1]: arm 越界 / Thompson / POMDP 路径 _log.warning, 不 raise
        """
        if self.policy_type == "thompson":
            _log.warning(
                "apply_penalty: policy_type='thompson' 不支持 LinUCB A 矩阵惩罚, 跳过",
            )
            return False
        if self.policy_type == "pomdp":
            _log.warning(
                "apply_penalty: policy_type='pomdp' 不支持 LinUCB A 矩阵惩罚, 跳过",
            )
            return False
        if arm < 0 or arm >= self.config.n_arms:
            _log.warning(
                "apply_penalty: arm 越界 (arm=%s, n_arms=%s), 跳过",
                arm, self.config.n_arms,
            )
            return False
        if self._penalty_counts[arm] >= self.PENALTY_MAX:
            return False
        self.bandit.A[arm] = self.bandit.A[arm] * factor
        self._penalty_counts[arm] += 1
        return True

    def get_penalty_counts(self) -> List[int]:
        """v0.71.0: 暴露每 arm 惩罚次数 (调试 + 测试用)."""
        return list(self._penalty_counts)

    # ---------------------------------------------------------------
    # v0.88.0-d: POMDP observation feedback 接口 (LCAEngine 集成用)
    # ---------------------------------------------------------------

    def set_observation(self, observation: int) -> None:
        """v0.88.0-d: 外部设 observation (LCAEngine 计算 reward 后调用).

        POMDP path: 下次 select_intervention() 时, 在 select_arm 之前
        调 pomdp.bayes_update(_last_arm, observation) 消化该 observation.
        其他 policy_type: 忽略 (LinUCB/Thompson 不需要).

        Args:
            observation: int [0, n_observations), POMDP observation

        防御性: pomdp is None (非 POMDP 路径) 时静默忽略
        """
        if self.policy_type != "pomdp" or self.pomdp is None:
            return
        if not isinstance(observation, int) or not (0 <= observation < self.pomdp.n_observations):
            _log.warning(
                "LCAPolicyLearner.set_observation: obs 越界或非 int (obs=%s, n_obs=%s), 跳过",
                observation, self.pomdp.n_observations if self.pomdp else "N/A",
            )
            return
        self._last_observation = int(observation)

    @staticmethod
    def _reward_to_observation(reward: float) -> int:
        """v0.88.0-d: reward ∈ [0, 1] → observation ∈ [0, 4) 离散化.

        4 observation (跟 POMDP 4 状态一致):
          - 0.0    → 0 (对应 Bored, 低反应)
          - 0.25   → 1
          - 0.5    → 2
          - 0.75   → 3 (高反应)
          - 1.0    → 3 (clip 到 n_obs - 1)

        默认 n_observations = 4 (跟 POMDPPolicy 默认一致).
        """
        clamped = max(0.0, min(1.0, float(reward)))
        n_obs = 4  # 跟 POMDPPolicy 默认 n_observations=4
        return min(n_obs - 1, int(clamped * n_obs))

    # ---------------------------------------------------------------
    # 上下文构建（02-lca §4.2 _build_context）
    # ---------------------------------------------------------------

    def _build_context(
        self,
        belief_state: BeliefState,
        intervention: Optional[Intervention] = None,
    ) -> np.ndarray:
        """构造 LinUCB 上下文向量.

        基础 16 维: 5 (5D theta) + 6 (BloomProfile) + 5 (DNA)

        v0.75 P0-m: 启用 use_arm_features 且提供 intervention 时,
                    追加 1 维 intervention.difficulty (总 17 维).
                    用于 per-candidate context 模式, 让 LinUCB 区分
                    不同难度的干预.
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
        base = np.concatenate([theta5, bloom6, dna5])  # (16,)

        # v0.75 P0-m: 追加 intervention.difficulty (1 维) -> 17 维
        if self.config.use_arm_features and intervention is not None:
            difficulty = float(np.clip(intervention.difficulty, 0.0, 1.0))
            return np.concatenate([base, [difficulty]])  # (17,)
        return base

    def _lookup_arm(self, intervention: Intervention) -> int | None:
        """通过干预 ID 反查 arm 索引.

        v0.75.3 H3-c3: 优先用 _intervention_to_arm (只追加, 不覆盖)
          背景: _arm_fingerprints[arm] 在同 arm 连续被选时被覆盖, 上一轮 intervention_id 丢失,
                _lookup_arm 返回 None, LinUCB.update 被跳过.
                lbc003 round 15+ arm 0 连续被选 47 次, 但只有 1 次 update 成功.
          修复: _intervention_to_arm dict 在 select_intervention 时追加 (不覆盖),
                _lookup_arm 优先用它, O(1) 查找.
        """
        target = intervention.intervention_id
        # v0.75.3 H3-c3: 优先用 _intervention_to_arm (never overwrite)
        if target in self._intervention_to_arm:
            return self._intervention_to_arm[target]
        # fallback: _arm_fingerprints (legacy, 可能被覆盖)
        for arm, fp in self._arm_fingerprints.items():
            if fp == target:
                return arm
        return None


__all__ = ["LCAPolicyLearner", "PolicyType"]
