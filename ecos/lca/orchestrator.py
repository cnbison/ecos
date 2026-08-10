"""LCA 主流程编排——L3-L4 教学法栈 + Contextual Bandits.

对应：
  - research/10-engineering/02-lca-policy-engine.md §6 LCAOrchestrator
  - research/00-overview/02-architecture.md §6 双 Agent 互校接口

主入口：
    LCAEngine(config=LCAEngineConfig()).select_intervention(cta_input)
    LCAEngine(config=LCAEngineConfig()).update(student_id, intervention, new_state, reward)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..cta.belief_state import BeliefState, BloomLevel, LearningDNAState
from ..llm_client import ECOSLLMClient
from .cta_input import CTAInput
from .intervention import (
    CAStage,
    CLTLevel,
    Intervention,
)
from .l3_selection import (
    CAConfig,
    CLTConfig,
)
from .l4_optimization import (
    BanditConfig,
    CTA_L4_Backend,
    LCAAttribution,
    LCAPolicyLearner,
)
from .experiment_designer import (
    ExperimentDesigner,
    ExperimentDesignerConfig,
)
from .planner import PlanDecision, Planner, PlannerConfig
from .rationale import RationaleGenerator

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LCA Input / Output 数据结构
# ---------------------------------------------------------------------------

# v0.82.0-b: CTAInput 迁到独立文件 cta_input.py (打破 orchestrator <-> experiment_designer 循环 import)
# 旧位置: ecos.lca.orchestrator.CTAInput
# 新位置: ecos.lca.cta_input.CTAInput
# __init__.py 仍导出 CTAInput (向后兼容)


@dataclass
class LCAResult:
    """LCA 输出（完整版——与 CTA belief_engine.py 占位 LCAResult 区分）.

    这个 LCAResult 是 LCA → App 层的契约。

    Attributes:
        student_id:    学生 ID
        intervention:  选中的干预
        rationale:     自然语言理由（LLM 生成或 fallback）
        expected_gain: 期望状态增量（用于 App 层 + 教师后台接口）
        expected_risk: 期望风险（Frustration 概率）
        bloom_target:  选中的目标 Bloom 层
        clt_level:     CLT 呈现级别
        ca_stage:      CA 阶段
        timestamp:     时间戳
    """

    student_id: str
    intervention: Intervention
    rationale: str
    expected_gain: float
    expected_risk: float
    bloom_target: BloomLevel
    clt_level: CLTLevel
    ca_stage: CAStage
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """序列化为 dict（持久化 + 教师后台接口使用）."""
        return {
            "student_id": self.student_id,
            "intervention": self.intervention.to_dict(),
            "rationale": self.rationale,
            "expected_gain": self.expected_gain,
            "expected_risk": self.expected_risk,
            "bloom_target": self.bloom_target.name,
            "clt_level": self.clt_level.name,
            "ca_stage": self.ca_stage.name,
            "timestamp": self.timestamp.isoformat(),
        }


# ---------------------------------------------------------------------------
# 候选干预生成已迁移到 ecos.lca.experiment_designer (v0.82.0-b)
# ---------------------------------------------------------------------------

# v0.82.0-b: 旧 _generate_candidates + DEFAULT_CANDIDATE_* 模块级常量
#   全部迁到 ExperimentDesigner (LCA 4-layer 第 2 层)
#   LCAEngine.select_intervention step 5 委托 self.experiment_designer.design(plan, cta_input, n_candidates)
#   行为完全保持一致 (跟 v0.81 LCAEngine._generate_candidates 算法一致)

# ---------------------------------------------------------------------------
# LCA Engine 主类
# ---------------------------------------------------------------------------

@dataclass
class LCAEngineConfig:
    """LCA Engine 配置."""

    clt_config: CLTConfig = field(default_factory=CLTConfig)
    ca_config: CAConfig = field(default_factory=CAConfig)
    bandit_config: BanditConfig = field(default_factory=BanditConfig)
    # v0.82.0-a: Planner 子 config (LCA 4-layer 第 1 层)
    planner_config: PlannerConfig = field(default_factory=PlannerConfig)
    # v0.82.0-b: Experiment Designer 子 config (LCA 4-layer 第 2 层)
    experiment_designer_config: ExperimentDesignerConfig = field(
        default_factory=ExperimentDesignerConfig
    )
    use_llm_rationale: bool = True
    rationale_audience: str = "student"  # 默认 student
    expected_gain_scale: float = 0.3    # expected_gain = scale × (1 - mastery)


class LCAEngine:
    """LCA 主引擎——L3-L4 教学法栈 + Contextual Bandits + Rationale.

    用法：
        engine = LCAEngine(config=LCAEngineConfig(), llm_client=client)
        result = engine.select_intervention(cta_input)
        # 观测到 reward 后
        engine.update(student_id, result.intervention, new_state, reward)
    """

    def __init__(
        self,
        config: Optional[LCAEngineConfig] = None,
        llm_client: Optional[ECOSLLMClient] = None,
    ):
        self.config = config or LCAEngineConfig()

        # v0.82.0-a: Planner 决策层 (LCA 4-layer split 第 1 层)
        #   内部组合 L3 组件 (CLT/Bjork/CA scaffolding) + CAStateMachine
        #   LCAEngine 通过 __getattr__ 转发访问 self.clt / self.bjork_testing 等
        self.planner = Planner(self.config.planner_config)

        # v0.82.0-b: Experiment Designer 实验设计层 (LCA 4-layer split 第 2 层)
        #   消费 Planner.plan() 输出 PlanDecision, 生成候选干预池
        self.experiment_designer = ExperimentDesigner(
            self.config.experiment_designer_config
        )

        # L4 组件 (v0.82.0-d 抽到 PolicyLearner, 当前 LCAEngine 直接持有)
        # v0.57.0: per-student bandit 改造 (修复 v0.56.0 单 bandit 多学生数据冲突 BUG)
        #   之前 self.bandit 是单 bandit 全局共享, lbc001 + lbc002 答题会互相污染 LinUCB 状态
        #   现在 self.bandits[student_id] 隔离 per-student
        self.bandits: Dict[str, "LCAPolicyLearner"] = {}
        self.attribution = LCAAttribution(CTA_L4_Backend())

        # Rationale（按 config 决定是否接 LLM）
        rationale_client = llm_client if self.config.use_llm_rationale else None
        self.rationale_gen = RationaleGenerator(rationale_client)

        # 当前干预历史（M2 W2 用内存；Phase 5+ 接入 persistence）
        self.intervention_history: Dict[str, List[Intervention]] = {}

        # v0.57.0: per-student select_count / update_count (持久化)
        self._select_count: Dict[str, int] = {}
        self._update_count: Dict[str, int] = {}
        # v0.57.0: per-student last_intervention (持久化)
        self._last_intervention: Dict[str, Intervention] = {}

    # v0.82.0-a: __getattr__ forwarding for Planner 子组件 (向后兼容)
    #   旧代码 / 测试可能访问 engine.clt / engine.bjork_testing 等
    #   转发到 self.planner.clt / self.planner.bjork_testing 等
    #   跟 v0.80 CTA BeliefEngine.__getattr__ 同模式
    _FORWARDED_PLANNER_ATTRS = {
        "clt", "bjork_testing", "bjork_spacing",
        "ca_scaffolding", "ca_state_machine",
    }

    def __getattr__(self, name: str) -> Any:
        """Forward Planner sub-component access to self.planner.

        Triggered only when normal attribute lookup fails. Used for
        self.clt / self.bjork_testing / etc. that were direct attributes
        in v0.81 LCAEngine. v0.82.0-a moved them to Planner.
        """
        if name in LCAEngine._FORWARDED_PLANNER_ATTRS:
            planner = self.__dict__.get("planner")
            if planner is not None and hasattr(planner, name):
                return getattr(planner, name)
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    # ---------------------------------------------------------------
    # 主入口
    # ---------------------------------------------------------------

    def select_intervention(
        self,
        cta_input: CTAInput,
        audience: Optional[str] = None,
    ) -> LCAResult:
        """LCA 主选择流程.

        Steps（02-lca §6）：
          1-4. Planner 决策层 (v0.82.0-a: 委托 self.planner.plan())
          5.   生成候选 + LinUCB 选择
          6.   生成 rationale
          7.   记录干预 + 归因
          8.   输出 LCAResult

        Args:
            cta_input: CTA 输入（含 BeliefState）
            audience: rationale 受众（student / teacher / parent）

        Returns:
            LCAResult（含 Intervention + rationale + expected_gain/risk）
        """
        belief_state = cta_input.belief_state
        student_id = cta_input.student_id
        audience = audience or self.config.rationale_audience

        # v0.82.0-a: Step 1-4 委托 Planner (决策层 4 步合一)
        history = self.intervention_history.get(student_id, [])
        plan: PlanDecision = self.planner.plan(cta_input, intervention_history=history)
        bloom_target = plan.bloom_target
        ca_stage = plan.ca_stage
        clt_level = plan.clt_level
        bjork_triggers = plan.bjork_triggers

        # Step 5: 生成候选 + LinUCB 选择
        # v0.82.0-b: 候选生成委托 ExperimentDesigner (LCA 4-layer 第 2 层)
        candidates = self.experiment_designer.design(
            plan,
            cta_input,
            n_candidates=self.config.bandit_config.n_arms,
        )
        # v0.57.0: per-student bandit (修复 v0.56.0 多学生数据冲突)
        bandit = self._get_bandit(student_id)
        chosen = bandit.select_intervention(belief_state, candidates)
        # 触发标签回填
        chosen.bjork_triggers = bjork_triggers

        # Step 6: rationale
        rationale = self.rationale_gen.generate(chosen, belief_state, audience=audience)
        chosen.rationale = rationale

        # 估算 expected_gain / risk
        expected_gain = self._estimate_gain(chosen, belief_state)
        expected_risk = self._estimate_risk(chosen, belief_state)
        chosen.expected_gain = expected_gain
        chosen.expected_risk = expected_risk

        # Step 7: 记录干预
        self.intervention_history.setdefault(student_id, []).append(chosen)
        self.attribution.record_intervention(chosen, student_id)
        # v0.57.0: per-student 计数 + last_intervention 跟踪 (持久化用)
        self._last_intervention[student_id] = chosen
        self._select_count[student_id] = self._select_count.get(student_id, 0) + 1

        # Step 8: 输出
        return LCAResult(
            student_id=student_id,
            intervention=chosen,
            rationale=rationale,
            expected_gain=expected_gain,
            expected_risk=expected_risk,
            bloom_target=bloom_target,
            clt_level=clt_level,
            ca_stage=ca_stage,
        )

    def update(
        self,
        student_id: str,
        intervention: Intervention,
        new_state: BeliefState,
        state_delta: float,
        reward: Optional[float] = None,
    ) -> None:
        """基于干预效果更新策略（LinUCB + 因果归因）.

        Args:
            student_id: 学生 ID
            intervention: 选中的干预
            new_state: 干预后 CTA 状态
            state_delta: 状态增量（new_theta - old_theta，归一化到 [0, 1]）
                - 仍用于因果归因 (attribution)
                - 当 reward=None 时, 也作为 LinUCB reward fallback (向后兼容)
            reward: v0.69.0 新增. LinUCB reward 直接来源.
                - dual_agent 路径: 传 actual_outcome (partial credit 0-1, 答对概率直接度量)
                - 教学 LCA 路径: 不传 (默认 None), 用 state_delta 兜底 (跟 v0.68.0 一致)
                - 设计理由: dual_agent 内部 LCAEngine 是 v0.62.0-A 独立实例, 改 reward 不污染教学 LCA
        """
        # v0.69.0: reward 来源优先级: 显式传 reward > state_delta fallback
        #   dual_agent 路径: reward = actual_outcome (答对概率)
        #   教学 LCA 路径: reward = state_delta (mastery 增长, 跟之前一致)
        if reward is None:
            linucb_reward = max(0.0, min(1.0, state_delta))
        else:
            linucb_reward = max(0.0, min(1.0, reward))

        # 因果归因 (仍用 state_delta, 不用 reward, 因为 attribution 测的是状态变化)
        self.attribution.attribute_effect(
            intervention,
            student_id,
            state_delta=state_delta,
        )

        # v0.57.0: per-student bandit (修复 v0.56.0 多学生数据冲突)
        bandit = self._get_bandit(student_id)
        bandit.update(
            intervention=intervention,
            belief_state=new_state,
            reward=linucb_reward,
        )
        # v0.57.0: per-student update 计数
        self._update_count[student_id] = self._update_count.get(student_id, 0) + 1

    # ---------------------------------------------------------------
    # v0.69.0: LinUCB 冷启动判定 (B4 前置)
    # ---------------------------------------------------------------

    def _is_linucb_cold_start(self, student_id: str) -> bool:
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
            bandit = self.bandits.get(student_id)
            if bandit is None:
                # bandit 未初始化 -> 冷启动
                return True
            total_pulls = int(bandit.bandit.arm_pull_counts.sum())
            threshold = self.config.bandit_config.cold_start_threshold
            return total_pulls < threshold
        except Exception:
            _log.warning(
                "LinUCB 冷启动判定失败 (student=%s), 兜底返回 True (走 fallback)",
                student_id,
                exc_info=True,
            )
            return True

    # ---------------------------------------------------------------
    # v0.57.0: per-student bandit 隔离 + 持久化接口
    # ---------------------------------------------------------------

    def _get_bandit(self, student_id: str) -> "LCAPolicyLearner":
        """获取 per-student bandit (lazy init).

        v0.57.0: 修复 v0.56.0 单 bandit 多学生数据冲突 BUG.
                  每个学生独立 LCAPolicyLearner 实例, LinUCB A/b 矩阵隔离.
        """
        if student_id not in self.bandits:
            self.bandits[student_id] = LCAPolicyLearner(self.config.bandit_config)
        return self.bandits[student_id]

    def dump_state(self, student_id: str) -> dict:
        """导出 per-student LCA 状态 (7 字段 + 内部辅助字段).

        Returns:
            dict 含 7 关键字段 (CLAUDE.md [5]):
              1. intervention_history  (List[Intervention.to_dict()])
              2. bandit_a              (List[List[List[float]]])
              3. bandit_b              (List[List[float]])
              4. arm_pull_counts       (List[int])
              5. last_intervention     (Intervention.to_dict() | None)
              6. update_count          (int)
              7. select_count          (int)
            + 内部字段:
              - arm_fingerprints       (Dict[str, str])  arm_idx → intervention_id
              - last_arm               (int)
        """
        import numpy as np

        bandit = self._get_bandit(student_id)
        linucb = bandit.bandit  # LinUCB 实例

        last_iv = self._last_intervention.get(student_id)
        return {
            # 7 关键字段
            "intervention_history": [iv.to_dict() for iv in self.intervention_history.get(student_id, [])],
            "bandit_a": [a.tolist() for a in linucb.A],
            "bandit_b": [b.tolist() for b in linucb.b],
            "arm_pull_counts": linucb.arm_pull_counts.tolist(),
            "last_intervention": last_iv.to_dict() if last_iv else None,
            "update_count": self._update_count.get(student_id, 0),
            "select_count": self._select_count.get(student_id, 0),
            # 内部辅助 (LinUCB select arm 需要)
            "arm_fingerprints": {str(k): v for k, v in bandit._arm_fingerprints.items()},
            "last_arm": bandit._last_arm,
        }

    def load_state(self, student_id: str, snapshot: dict) -> None:
        """加载 per-student LCA 状态 (7 字段全恢复).

        Args:
            student_id: 学生 ID
            snapshot: dump_state() 导出的 dict

        防御性自检 [5]: 7 关键字段必须全恢复, 缺一不可 (否则 LinUCB 学错位).

        注: context_dim 永远是 LCAPolicyLearner.CONTEXT_DIM=16 (常量),
             不从 snapshot 推断 (避免 schema 漂移导致 LinUCB 维度错位).
        """
        import numpy as np
        from .intervention import Intervention as _IV

        # 7 关键字段恢复
        # 1. intervention_history
        history = snapshot.get("intervention_history", []) or []
        self.intervention_history[student_id] = [_IV.from_dict(d) for d in history]

        # 2-4. LinUCB A/b 矩阵 + arm_pull_counts
        bandit = self._get_bandit(student_id)
        linucb = bandit.bandit

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

        # 5. last_intervention
        last_iv_dict = snapshot.get("last_intervention")
        if last_iv_dict:
            self._last_intervention[student_id] = _IV.from_dict(last_iv_dict)
        else:
            self._last_intervention.pop(student_id, None)

        # 6-7. 计数
        self._update_count[student_id] = int(snapshot.get("update_count", 0))
        self._select_count[student_id] = int(snapshot.get("select_count", 0))

        # 内部辅助 (arm → intervention_id 映射, LinUCB select arm 需要)
        af_dict = snapshot.get("arm_fingerprints", {}) or {}
        bandit._arm_fingerprints = {int(k): v for k, v in af_dict.items()}
        bandit._last_arm = int(snapshot.get("last_arm", -1))

    # ---------------------------------------------------------------
    # 内部工具
    # ---------------------------------------------------------------

    # v0.82.0-a: _should_review_spaced 迁移到 Planner._should_review_spaced
    # 旧逻辑保留在 PlannerConfig.mastery_threshold / trajectory_min_len 配置中

    def _estimate_gain(
        self,
        intervention: Intervention,
        belief_state: BeliefState,
    ) -> float:
        """估算 expected_gain = scale × (1 - K_mastery).

        gain_potential × scaffolding 比例。
        """
        bp_mastery = {
            BloomLevel.REMEMBER: belief_state.bloom_profile.remember,
            BloomLevel.UNDERSTAND: belief_state.bloom_profile.understand,
            BloomLevel.APPLY: belief_state.bloom_profile.apply,
            BloomLevel.ANALYZE: belief_state.bloom_profile.analyze,
            BloomLevel.EVALUATE: belief_state.bloom_profile.evaluate,
            BloomLevel.CREATE: belief_state.bloom_profile.create,
        }[intervention.bloom_target]
        gain = self.config.expected_gain_scale * (1.0 - bp_mastery)
        # scaffolding 提升 gain
        gain *= (0.5 + 0.5 * intervention.scaffolding_level)
        return max(0.0, min(1.0, gain))

    def _estimate_risk(
        self,
        intervention: Intervention,
        belief_state: BeliefState,
    ) -> float:
        """估算 expected_risk——Frustration / Cheating 概率.

        规则：
        - 高难度 + 低 K mastery → 高 frustration 风险
        - 低 scaffolding + 错误率历史 → 中风险
        """
        # 难度 - K mastery gap
        k_gap = intervention.difficulty - belief_state.K.mastery_prob
        risk = max(0.0, k_gap) * 0.5
        # scaffolding 缓解
        risk *= (1.0 - intervention.scaffolding_level)
        return max(0.0, min(1.0, risk))


__all__ = ["LCAEngine", "LCAEngineConfig", "LCAResult", "CTAInput"]
