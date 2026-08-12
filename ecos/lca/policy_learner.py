"""LCA 策略学习层 (PolicyLearner) —— v0.82 LCA 4-layer split 第 4 层.

对应:
  - research/00-overview/11-ecos-2.0-architecture-proposal.md §2.2.1 LCA 4-layer
  - research/00-overview/12-kernel-mapping-current-vs-2.0.md §4 LCA Policy Learner
  - 旧 LCAEngine._get_bandit + self.bandits + dump_state/load_state LinUCB 部分
    + _is_linucb_cold_start (orchestrator.py v0.81.0)

职责:
  - LinUCB 包装 (per-student LCAPolicyLearner lazy init)
  - select(student_id, state, candidates) -> Intervention
  - update(student_id, intervention, new_state, reward) -> None
  - is_cold_start(student_id) -> bool (v0.69.0 引入, dual_agent_confidence 来源切换)
  - dump(student_id) -> dict (4 字段 + 2 内部)
  - load(student_id, snapshot) -> None (维度校验, 防御性自检 [5])

设计原则:
  - PolicyLearner 是 2.0 §2.2.1 策略学习层, 不持有 rationale / evaluation 状态
  - 持有 per-student LCAPolicyLearner 实例 (v0.57.0 per-student 隔离原则)
  - 冷启动阈值: arm_pull_counts.sum() < cold_start_threshold 走 fallback
  - v0.83+ 扩展: Thompson Sampling / POMDP 同接口实现, LCAEngine 不变
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

from ..cta.belief_state import BeliefState
from .intervention import Intervention
from .l4_optimization import BanditConfig, LCAPolicyLearner

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Policy Learner Config
# ---------------------------------------------------------------------------

@dataclass
class PolicyLearnerConfig:
    """PolicyLearner 配置.

    Attributes:
        bandit_config:         LinUCB 配置 (n_arms / context_dim / alpha 等)
        cold_start_threshold:  总 arm_pull 阈值 (< threshold 视为冷启动, 走 fallback)
                              默认 10, 跟 v0.69.0 LCAEngine._is_linucb_cold_start 一致
        policy_type:           v0.86.0-c: "linucb" (默认) / "thompson"
                              v0.87.0-d: 扩展到 "pomdp"
        thompson_seed:         v0.86.0-c: Thompson Sampling PRNG seed (testing 用)
        pomdp_seed:            v0.87.0-d: POMDP Policy PRNG seed (testing 用)
    """

    bandit_config: BanditConfig = field(default_factory=BanditConfig)
    cold_start_threshold: int = 10
    policy_type: str = "linucb"
    thompson_seed: Optional[int] = None
    pomdp_seed: Optional[int] = None
    # v0.89.0-d: POMDP 是否走 PBVI (None → POMDPPolicy 默认 True)
    pomdp_use_pbvi: Optional[bool] = None
    # v0.90.0-d: POMDP T/R 后验学习开关 (None → POMDPPolicy 默认 True)
    pomdp_use_learned_t_r: Optional[bool] = None


# ---------------------------------------------------------------------------
# Policy Learner 类
# ---------------------------------------------------------------------------

class PolicyLearner:
    """LCA 策略学习层 (v0.82 LCA 4-layer split 第 4 层).

    用法:
        learner = PolicyLearner(PolicyLearnerConfig())
        # 1) select 阶段
        chosen = learner.select(student_id, belief_state, candidates)
        # 2) update 阶段
        learner.update(student_id, chosen, new_state, reward=0.7)
        # 3) 冷启动判定 (dual_agent_confidence 来源)
        if learner.is_cold_start(student_id):
            ...  # 走 _estimate_gain fallback
        # 4) 持久化
        snapshot = learner.dump(student_id)
        learner.load(student_id, snapshot)

    旧代码 (LCAEngine v0.81.0):
        bandit = self._get_bandit(student_id)
        chosen = bandit.select_intervention(belief_state, candidates)
        # update
        bandit.update(intervention=chosen, belief_state=new_state, reward=reward)
        # 冷启动
        if self._is_linucb_cold_start(student_id): ...
        # 持久化
        self.bandits[student_id]  # 内部 dict

    v0.82.0-d: 上述逻辑抽到 PolicyLearner, LCAEngine 仅委托.
    """

    def __init__(self, config: Optional[PolicyLearnerConfig] = None):
        self.config = config or PolicyLearnerConfig()
        # v0.57.0: per-student bandit 改造 (修复 v0.56.0 单 bandit 多学生数据冲突 BUG)
        #   之前 self.bandit 是单 bandit 全局共享, lbc001 + lbc002 答题会互相污染 LinUCB 状态
        #   现在 self._learners[student_id] 隔离 per-student
        self._learners: Dict[str, LCAPolicyLearner] = {}

    # ---------------------------------------------------------------
    # Per-student LCAPolicyLearner 访问
    # ---------------------------------------------------------------

    def _get_learner(self, student_id: str) -> LCAPolicyLearner:
        """获取 per-student LCAPolicyLearner (lazy init).

        v0.57.0: 修复 v0.56.0 单 bandit 多学生数据冲突 BUG.
                  每个学生独立 LCAPolicyLearner 实例, LinUCB A/b 矩阵隔离.
        v0.86.0-c: 透传 policy_type + thompson_seed 到 LCAPolicyLearner
        v0.87.0-d: 透传 pomdp_seed
        v0.89.0-d: 透传 pomdp_use_pbvi
        v0.90.0-d: 透传 pomdp_use_learned_t_r
        """
        if student_id not in self._learners:
            self._learners[student_id] = LCAPolicyLearner(
                self.config.bandit_config,
                policy_type=self.config.policy_type,
                thompson_seed=self.config.thompson_seed,
                pomdp_seed=self.config.pomdp_seed,
                pomdp_use_pbvi=self.config.pomdp_use_pbvi,
                pomdp_use_learned_t_r=self.config.pomdp_use_learned_t_r,
            )
        return self._learners[student_id]

    # ---------------------------------------------------------------
    # 主入口: select / update
    # ---------------------------------------------------------------

    def select(
        self,
        student_id: str,
        belief_state: BeliefState,
        candidates: list,
    ) -> Intervention:
        """基于 LinUCB 选择最佳干预 (委托 LCAPolicyLearner.select_intervention).

        Args:
            student_id:   学生 ID
            belief_state: CTA 状态 (构建上下文)
            candidates:   候选干预列表 (来自 ExperimentDesigner)

        Returns:
            选中的 Intervention
        """
        learner = self._get_learner(student_id)
        return learner.select_intervention(belief_state, candidates)

    def update(
        self,
        student_id: str,
        intervention: Intervention,
        new_state: BeliefState,
        reward: float,
        observation: Optional[int] = None,
    ) -> None:
        """基于干预效果更新 LinUCB (委托 LCAPolicyLearner.update).

        Args:
            student_id:    学生 ID
            intervention:  之前选中的干预
            new_state:     干预后的 CTA 状态
            reward:        状态增量 (state_delta), 已被调用方归一化到 [0, 1]
            observation:   v0.90.0-d 新增. POMDP observation ∈ [0, n_observations);
                           None (LinUCB/Thompson) 走老路径; int (POMDP) 触发 _update_t_r.
        """
        learner = self._get_learner(student_id)
        learner.update(
            intervention=intervention,
            belief_state=new_state,
            reward=reward,
            observation=observation,
        )

    # ---------------------------------------------------------------
    # v0.69.0: LinUCB 冷启动判定 (dual_agent_confidence 来源切换)
    # ---------------------------------------------------------------

    def is_cold_start(self, student_id: str) -> bool:
        """判定 LinUCB 是否处于冷启动期.

        v0.69.0: 用于决定 dual_agent_confidence 来源
          - 冷启动期: 走 _estimate_gain 简化估算 (source="estimate_gain_fallback")
          - 非冷启动期: 走 LinUCB θ@x 预测 (source="linucb")

        判定规则: arm_pull_counts.sum() < cold_start_threshold (默认 10)

        Args:
            student_id: 学生 ID

        Returns:
            True 如果 LinUCB 处于冷启动期 (应该走 fallback)
            False 如果 LinUCB 已积累足够数据, θ@x 预测可信

        防御性自检 [1]: 失败兜底返回 True (保守, 走简化估算)
        """
        try:
            learner = self._learners.get(student_id)
            if learner is None:
                # bandit 未初始化 -> 冷启动
                return True
            total_pulls = int(learner.bandit.arm_pull_counts.sum())
            threshold = self.config.cold_start_threshold
            return total_pulls < threshold
        except Exception:
            _log.warning(
                "LinUCB 冷启动判定失败 (student=%s), 兜底返回 True (走 fallback)",
                student_id,
                exc_info=True,
            )
            return True

    # ---------------------------------------------------------------
    # 持久化: dump / load (防御性自检 [5])
    # ---------------------------------------------------------------

    def dump(self, student_id: str) -> dict:
        """导出 per-student LinUCB 状态 (4 字段 + 2 内部辅助).

        Returns:
            dict 含 4 关键字段:
              1. bandit_a              (List[List[List[float]]])  n_arms × d × d
              2. bandit_b              (List[List[float]])        n_arms × d
              3. arm_pull_counts       (List[int])
              4. arm_fingerprints      (Dict[str, str])  arm_idx → intervention_id
            + 内部辅助:
              - last_arm               (int)
        """
        learner = self._get_learner(student_id)
        linucb = learner.bandit  # LinUCB 实例
        return {
            "bandit_a": [a.tolist() for a in linucb.A],
            "bandit_b": [b.tolist() for b in linucb.b],
            "arm_pull_counts": linucb.arm_pull_counts.tolist(),
            "arm_fingerprints": {str(k): v for k, v in learner._arm_fingerprints.items()},
            "last_arm": learner._last_arm,
        }

    def load(self, student_id: str, snapshot: dict) -> None:
        """加载 per-student LinUCB 状态 (含维度校验, 防御性自检 [5]).

        Args:
            student_id: 学生 ID
            snapshot:   dump() 导出的 dict (4 字段 + 2 内部辅助)

        防御性自检 [5]: 4 关键字段必须全恢复, 缺一不可 (否则 LinUCB 学错位).
        """
        import numpy as np

        learner = self._get_learner(student_id)
        linucb = learner.bandit

        bandit_a = snapshot.get("bandit_a", []) or []
        bandit_b = snapshot.get("bandit_b", []) or []
        arm_pull_counts = snapshot.get("arm_pull_counts", []) or []

        # 防御性: 维度校验 (防止 schema 漂移, 错位数据会污染 LinUCB)
        if bandit_a:
            expected_n_arms = linucb.n_arms
            expected_d = linucb.context_dim
            actual_n_arms = len(bandit_a)
            actual_d = len(bandit_a[0][0]) if bandit_a[0] and bandit_a[0][0] else 0

            if actual_n_arms != expected_n_arms or actual_d != expected_d:
                # 维度不匹配, 拒绝加载 (不污染 LinUCB)
                raise ValueError(
                    f"LinUCB state 维度不匹配 (student={student_id}): "
                    f"expected n_arms={expected_n_arms}, d={expected_d}, "
                    f"got n_arms={actual_n_arms}, d={actual_d}. "
                    f"可能 schema 漂移, 需手动清理 student_lca_state 行."
                )

            linucb.A = [np.array(a, dtype=float) for a in bandit_a]
            linucb.b = [np.array(b, dtype=float) for b in bandit_b]
            linucb.arm_pull_counts = np.array(arm_pull_counts, dtype=int)
        # 如果 snapshot 是空 (新学生), 保持默认 A=I, b=0 (LinUCB 冷启动)

        # 内部辅助 (arm → intervention_id 映射, LinUCB select arm 需要)
        af_dict = snapshot.get("arm_fingerprints", {}) or {}
        learner._arm_fingerprints = {int(k): v for k, v in af_dict.items()}
        learner._last_arm = int(snapshot.get("last_arm", -1))


__all__ = [
    "PolicyLearner",
    "PolicyLearnerConfig",
]
