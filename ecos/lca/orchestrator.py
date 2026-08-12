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
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ..cta.belief_state import BeliefState, BloomLevel, LearningDNAState
from ..llm_client import ECOSLLMClient
from .cta_input import CTAInput

# v0.87.0-b: MotivationProfile TYPE_CHECKING 避免循环 import
# v0.91.0-b: CognitiveTwinAgent + HumanFeedbackEntry TYPE_CHECKING 避免循环 import
#   CognitiveTwinAgent 引用 BeliefState + TrajectoryState (top-level import OK),
#   HumanFeedbackEntry 引用 LearningEvent (TYPE_CHECKING 避免循环)
if TYPE_CHECKING:
    from ..cta.cognitive_twin import ActionEntry, ActionHistory, CognitiveTwinAgent, HumanFeedbackEntry
    from ..lca.l4_optimization.pomdp_diagnostic import POMDPDiagnostic
    from ..motivation.profile import MotivationProfile
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
    LCAPolicyLearner,
)
from .experiment_designer import (
    ExperimentDesigner,
    ExperimentDesignerConfig,
)
from .evaluator import Evaluator, EvaluatorConfig
from .planner import PlanDecision, Planner, PlannerConfig
from .policy_learner import PolicyLearner, PolicyLearnerConfig
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
    # v0.82.0-c: Evaluator 子 config (LCA 4-layer 第 3 层)
    evaluator_config: EvaluatorConfig = field(default_factory=EvaluatorConfig)
    # v0.82.0-d: PolicyLearner 子 config (LCA 4-layer 第 4 层)
    #   None = LCAEngine.__init__ 从 self.bandit_config 派生 (cold_start_threshold 透传)
    policy_learner_config: Optional[PolicyLearnerConfig] = None
    use_llm_rationale: bool = True
    rationale_audience: str = "student"  # 默认 student
    # v0.82.0-c: expected_gain_scale 迁到 EvaluatorConfig.gain_scale (从 LCAEngineConfig 移除)


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

        # v0.82.0-c: Evaluator 评估层 (LCA 4-layer split 第 3 层)
        #   估算 expected_gain/risk + 因果归因 (wrap LCAAttribution)
        self.evaluator = Evaluator(self.config.evaluator_config)
        # 向后兼容: tests/test_lca_update_reward_actual_outcome.py:196 monkey-patch
        #   `lca_engine.attribution.attribute_effect`, 必须保持 self.attribution 可访问
        #   这里把 evaluator.attribution 引用暴露为 self.attribution (共享同一对象)
        self.attribution = self.evaluator.attribution

        # v0.82.0-d: PolicyLearner 策略学习层 (LCA 4-layer split 第 4 层)
        #   LinUCB 包装 (per-student lazy init) + 冷启动判定 + dump/load
        #   如果 self.config.policy_learner_config 是 None, 从 self.config.bandit_config 派生
        #   (保持 cold_start_threshold 跟 BanditConfig.cold_start_threshold 同步)
        pl_config = self.config.policy_learner_config
        if pl_config is None:
            pl_config = PolicyLearnerConfig(
                bandit_config=self.config.bandit_config,
                cold_start_threshold=self.config.bandit_config.cold_start_threshold,
            )
        self.policy_learner = PolicyLearner(pl_config)
        # 向后兼容: dual_agent/orchestrator.py:569 / tests/test_lca_*.py 大量访问
        #   `lca_engine.bandits[student_id]` / `lca_engine.bandits.get(sid)` /
        #   `lca_engine._get_bandit(student_id)`.
        #   这里把 policy_learner._learners 引用暴露为 self.bandits (共享同一 dict)
        self.bandits: Dict[str, "LCAPolicyLearner"] = self.policy_learner._learners

        # v0.82.0-d: self.bandits 引用 = self.policy_learner._learners (共享同一 dict)
        #   任何 self.bandits[student_id] = X 都会同步到 self.policy_learner._learners
        #   任何 self.policy_learner._get_learner(student_id) 也会从同一 dict 拿
        #   v0.82.0-d: self.attribution 移到 self.evaluator.attribution (上面 __init__)
        #   保持 self.attribution 引用 = self.evaluator.attribution (向后兼容 tests/test_lca_update_reward_actual_outcome.py monkey-patch)

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
        # v0.88.0-d: per-student last POMDP observation (下次 select 消费 bayes_update)
        self._last_observation: Dict[str, int] = {}
        # v0.91.0-b: per-student CognitiveTwinAgent (Twin → Human Twin 抽象)
        #   dict 模式跟 _last_intervention / _last_observation 同 (per-student state)
        #   维护在 LCAEngine, 不污染 BeliefState (8 字段已饱和)
        #   c 阶段 select_intervention 消费 (Designer + Evaluator 透传)
        #   d 阶段 dump_state/load_state 加 cognitive_twin 字段
        self._cognitive_twin: Dict[str, "CognitiveTwinAgent"] = {}
        # v0.91.0-d: cognitive_twin dump 暂存 (load_state 后 bind_cognitive_twin 重建)
        self._cognitive_twin_pending: Dict[str, dict] = {}
        # v0.93.0-b: per-student POMDP diagnostic (Twin 第 5 维度 — POMDP T/R 后验可视化)
        #   跟 _cognitive_twin / _last_intervention / _last_observation 同 per-student dict 模式
        #   LCA select_intervention pomdp path auto-collect, Runtime.diagnose_pomdp 读缓存
        #   不污染 BeliefState (Plugin SDK 第 8 subscriber pomdp_diagnostic_updated 也走此 dict)
        self._pomdp_diagnostic: Dict[str, "POMDPDiagnostic"] = {}

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
        motivation: Optional["MotivationProfile"] = None,
        domain_name: Optional[str] = None,
        cognitive_twin: Optional["CognitiveTwinAgent"] = None,
        action_history: Optional["ActionHistory"] = None,
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
            motivation: v0.87.0-b: 可选 MotivationProfile, 调整候选池 itype 权重
                        (frustration/engagement/confidence 考虑)
            domain_name: v0.88.0-b: 可选 Domain name (e.g. "education"/"science"/"career"),
                          调整候选池 itype 权重 + reward factor
                          (None = 读 state.domain_extension["active_domain"] 兜底)
            cognitive_twin: v0.91.0-b: 可选 CognitiveTwinAgent, Twin → Human Twin 抽象.
                            存 self._cognitive_twin[student_id] 供 c 阶段消费 (Designer + Evaluator).
                            None 时 fallback to self._cognitive_twin.get(student_id) (per-student dict 兜底).
            action_history: v0.92.0-b: 可选 ActionHistory (Twin 第 4 维度, LCA 内部自动记录).
                            透传到 ExperimentDesigner._action_history_itype_override +
                            Evaluator.action_history_reward_adjustment (c 阶段消费).
                            None 时 fallback to self._cognitive_twin[student_id].action_history 派生.

        Returns:
            LCAResult（含 Intervention + rationale + expected_gain/risk）
        """
        belief_state = cta_input.belief_state
        student_id = cta_input.student_id
        audience = audience or self.config.rationale_audience

        # v0.87.0-b: motivation fallback to belief_state.motivation
        if motivation is None:
            motivation = getattr(belief_state, "motivation", None)

        # v0.88.0-b: domain_name fallback to belief_state.domain_extension["active_domain"]
        if domain_name is None:
            domain_name = getattr(belief_state, "domain_extension", {}).get(
                "active_domain"
            )

        # v0.91.0-b: cognitive_twin fallback to per-student dict
        #   存储 cognitive_twin 到 self._cognitive_twin[student_id] 供 c 阶段消费
        #   (ExperimentDesigner._human_feedback_itype_override + Evaluator.human_feedback_reward_adjustment)
        if cognitive_twin is None:
            cognitive_twin = self._cognitive_twin.get(student_id)
        if cognitive_twin is not None:
            self._cognitive_twin[student_id] = cognitive_twin

        # v0.92.0-b: action_history fallback to cognitive_twin.action_history
        #   (per-student dict 兜底: LCAEngine 内部 LCA 视角跟踪的 LCA 自动行为轨迹)
        #   透传到 ExperimentDesigner._action_history_itype_override +
        #   Evaluator.action_history_reward_adjustment (c 阶段消费)
        if action_history is None and cognitive_twin is not None:
            action_history = cognitive_twin.action_history

        # v0.82.0-a: Step 1-4 委托 Planner (决策层 4 步合一)
        history = self.intervention_history.get(student_id, [])
        plan: PlanDecision = self.planner.plan(cta_input, intervention_history=history)
        bloom_target = plan.bloom_target
        ca_stage = plan.ca_stage
        clt_level = plan.clt_level
        bjork_triggers = plan.bjork_triggers

        # Step 5: 生成候选 + LinUCB 选择
        # v0.82.0-b: 候选生成委托 ExperimentDesigner (LCA 4-layer 第 2 层)
        # v0.87.0-b: motivation 透传到 ExperimentDesigner.design()
        # v0.88.0-b: domain_name 透传到 ExperimentDesigner.design()
        # v0.91.0-c: cognitive_twin 透传到 ExperimentDesigner.design() (itype 权重调整)
        # v0.92.0-c: action_history 透传到 ExperimentDesigner.design() (itype 权重调整)
        candidates = self.experiment_designer.design(
            plan,
            cta_input,
            n_candidates=self.config.bandit_config.n_arms,
            motivation=motivation,
            domain_name=domain_name,
            cognitive_twin=cognitive_twin,
            action_history=action_history,
        )
        # v0.82.0-d: LinUCB 选择委托 PolicyLearner.select (LCA 4-layer 第 4 层)
        #   内部 lazy init per-student LCAPolicyLearner (v0.57.0 per-student 隔离)
        chosen = self.policy_learner.select(student_id, belief_state, candidates)
        # 触发标签回填
        chosen.bjork_triggers = bjork_triggers

        # Step 6: rationale
        rationale = self.rationale_gen.generate(chosen, belief_state, audience=audience)
        chosen.rationale = rationale

        # 估算 expected_gain / risk (v0.82.0-c 委托 Evaluator)
        expected_gain = self.evaluator.estimate_gain(chosen, belief_state)
        expected_risk = self.evaluator.estimate_risk(chosen, belief_state)

        # v0.87.0-b: motivation reward 调整 (multiplicative factor)
        motivation_factor = self.evaluator.motivation_reward_adjustment(belief_state)
        expected_gain *= motivation_factor

        # v0.88.0-b: domain reward 调整 (multiplicative factor, 跟 motivation 同 range)
        domain_factor = self.evaluator.domain_reward_adjustment(
            belief_state, domain_name=domain_name
        )
        expected_gain *= domain_factor

        # v0.91.0-c: human_feedback reward 调整 (multiplicative factor, 跟 motivation / domain 同 range)
        human_feedback_factor = self.evaluator.human_feedback_reward_adjustment(
            cognitive_twin
        )
        expected_gain *= human_feedback_factor

        # v0.92.0-c: action_history reward 调整 (multiplicative factor, 跟 human_feedback 同 range)
        #   多 factor chain: base × motivation × domain × human_feedback × action_history (5 因素)
        action_history_factor = self.evaluator.action_history_reward_adjustment(
            action_history
        )
        expected_gain *= action_history_factor

        chosen.expected_gain = max(0.0, min(1.0, expected_gain))
        chosen.expected_risk = expected_risk

        # v0.88.0-d: POMDP 路径 - 在 select 前消化上次 observation
        #   LCAEngine 维护 _last_observation[student_id] (上次 update 产出),
        #   select 前 set 到 LCAPolicyLearner, 内部 select 调 bayes_update
        # v0.89.0-d: 同时显式 solve_pbvi (双层防御: dual_agent 路径直接走 LCAEngine
        #   时也确保 PBVI 在 select 前收敛; 内部幂等)
        if self.policy_learner.config.policy_type == "pomdp":
            obs = self._last_observation.get(student_id)
            learner = self.policy_learner._get_learner(student_id)
            if obs is not None:
                # 从 per-student LCAPolicyLearner 调 set_observation
                learner.set_observation(obs)
            if learner.pomdp is not None:
                try:
                    learner.pomdp.solve_pbvi()
                except Exception as e:  # noqa: BLE001
                    _log.warning(
                        "LCAEngine.select_intervention: solve_pbvi 失败 (%s), 退化到 select_arm 内 fallback",
                        e,
                    )

        # Step 7: 记录干预
        self.intervention_history.setdefault(student_id, []).append(chosen)
        # v0.82.0-c: 委托 Evaluator.record_intervention (wrap self.attribution)
        self.evaluator.record_intervention(chosen, student_id)
        # v0.57.0: per-student 计数 + last_intervention 跟踪 (持久化用)
        self._last_intervention[student_id] = chosen
        self._select_count[student_id] = self._select_count.get(student_id, 0) + 1

        # v0.92.0-b: 自动记录 intervention_selected ActionEntry (LCA 视角, Twin 第 4 维度)
        #   跟前 3 维度 human_feedback 主动注入 pattern 不同 — action_history 是 LCA 内部自动记录,
        #   Plugin SDK 不加新 subscriber. metadata 含 expected_gain / expected_risk / audience /
        #   bloom_target / policy_type 5 字段, 供 c 阶段 ExperimentDesigner + Evaluator 消费.
        from ..cta.cognitive_twin import ActionEntry
        try:
            action_entry = ActionEntry(
                student_id=student_id,
                timestamp=datetime.now(),
                action_type="intervention_selected",
                intervention_id=chosen.intervention_id,
                reward=None,  # 干预选择时无 reward (reward 在 update 时记录)
                metadata={
                    "expected_gain": float(chosen.expected_gain),
                    "expected_risk": float(chosen.expected_risk),
                    "audience": audience,
                    "bloom_target": bloom_target.name,
                    "policy_type": self.policy_learner.config.policy_type,
                },
                source="lca",
            )
            self.append_action_history(student_id, action_entry, state=belief_state)
        except Exception:  # noqa: BLE001
            # 防御性: action_history 记录失败不阻断 select (per 防御性自检 [1])
            _log.warning(
                "LCAEngine.select_intervention: append_action_history 失败 (sid=%s), 继续",
                student_id, exc_info=True,
            )

        # Step 8: 输出
        result = LCAResult(
            student_id=student_id,
            intervention=chosen,
            rationale=rationale,
            expected_gain=expected_gain,
            expected_risk=expected_risk,
            bloom_target=bloom_target,
            clt_level=clt_level,
            ca_stage=ca_stage,
        )

        # v0.93.0-b: POMDP path auto-collect diagnostic (跟 v0.92.0-b action_history auto-record parallel)
        #   选完 intervention 后触发 LCAEngine._pomdp_diagnostic[student_id] 缓存
        #   Runtime.diagnose_pomdp() 读缓存, miss 时调 learner.pomdp.get_diagnostic() lazy collect
        if self.policy_learner.config.policy_type == "pomdp":
            self._collect_pomdp_diagnostic(student_id)

        return result

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

        # 因果归因 (v0.82.0-c 委托 Evaluator.attribute_effect, wrap self.attribution)
        #   仍用 state_delta, 不用 reward, 因为 attribution 测的是状态变化
        self.evaluator.attribute_effect(
            intervention,
            student_id,
            state_delta=state_delta,
        )

        # v0.82.0-d: LinUCB update 委托 PolicyLearner.update (LCA 4-layer 第 4 层)
        # v0.90.0-d: POMDP 路径透传 observation (触发 _update_t_r 学 T/R)
        pomdp_observation = None
        if self.policy_learner.config.policy_type == "pomdp":
            # v0.88.0-d: linucb_reward ∈ [0, 1] → discretize 到 [0, n_observations)
            pomdp_observation = int(
                min(3, int(linucb_reward * 4))  # 跟 LCAPolicyLearner._reward_to_observation 一致
            )
        self.policy_learner.update(
            student_id,
            intervention,
            new_state,
            reward=linucb_reward,
            observation=pomdp_observation,
        )
        # v0.57.0: per-student update 计数
        self._update_count[student_id] = self._update_count.get(student_id, 0) + 1

        # v0.88.0-d: POMDP observation 记录 (下次 select 消费 bayes_update)
        #   v0.90.0-d: pomdp_observation 已在上面算, 这里只保留 dict (backward compat)
        if pomdp_observation is not None:
            self._last_observation[student_id] = pomdp_observation

        # v0.92.0-b: 自动记录 reward_recorded ActionEntry (LCA 视角, Twin 第 4 维度)
        #   跟前 3 维度 human_feedback 主动注入 pattern 不同 — action_history 是 LCA 内部自动记录,
        #   Plugin SDK 不加新 subscriber. metadata 含 policy_type / pomdp_observation (None for 非 POMDP).
        #   供 c 阶段 ExperimentDesigner._action_history_itype_override +
        #   Evaluator.action_history_reward_adjustment 消费.
        from ..cta.cognitive_twin import ActionEntry
        try:
            reward_entry = ActionEntry(
                student_id=student_id,
                timestamp=datetime.now(),
                action_type="reward_recorded",
                intervention_id=intervention.intervention_id if hasattr(intervention, "intervention_id") else None,
                reward=float(linucb_reward),
                metadata={
                    "policy_type": self.policy_learner.config.policy_type,
                    "pomdp_observation": pomdp_observation,  # None for LinUCB / Thompson
                },
                source="lca",
            )
            self.append_action_history(student_id, reward_entry, state=new_state)
        except Exception:  # noqa: BLE001
            # 防御性: action_history 记录失败不阻断 update (per 防御性自检 [1])
            _log.warning(
                "LCAEngine.update: append_action_history 失败 (sid=%s), 继续",
                student_id, exc_info=True,
            )

    # ---------------------------------------------------------------
    # v0.91.0-b: Human Twin 抽象 — append_human_feedback (Plugin SDK 4 endpoint 接线)
    # ---------------------------------------------------------------

    def append_human_feedback(
        self,
        student_id: str,
        entry: "HumanFeedbackEntry",
        state: Optional[BeliefState] = None,
    ) -> None:
        """v0.91.0-b: 追加 HumanFeedbackEntry 到 per-student CognitiveTwinAgent.

        Plugin SDK 4 endpoint subscriber (hint_requested / idle_detected / goal_changed
        / reflection_completed) 调此方法把 Human-in-loop 信号注入 LCA 状态.

        Args:
            student_id: 学生 ID
            entry: HumanFeedbackEntry 实例 (4 event_type 校验已通过, frozen)
            state: Optional[BeliefState] for lazy init CognitiveTwinAgent.
                   None 时若 student_id 不在 _cognitive_twin dict, skip (下次 select
                   时 select_intervention 走 from_state 兜底).

        防御性自检 [8]: CognitiveTwinAgent.append_human_feedback 是 allowlisted mutation
        (FUNC_ALLOWLIST += "append_human_feedback", 跟 append_trajectory_snapshot /
        add_evidence / set_domain_extension / add_motivation_observation 同模式).

        c 阶段: select_intervention 消费 self._cognitive_twin[student_id]
                (Designer._human_feedback_itype_override + Evaluator.human_feedback_reward_adjustment)
        """
        # v0.91.0-b: lazy init CognitiveTwinAgent from state (跟 _last_intervention
        # 模式一致, state 不在时 skip 不报错)
        if student_id not in self._cognitive_twin:
            if state is None:
                # No state to init from, skip silently (下次 select 时 select_intervention
                # 会从 cta_input.belief_state 兜底 from_state)
                _log.debug(
                    "LCAEngine.append_human_feedback: student_id=%s 没 state, "
                    "skip lazy init (下次 select 会兜底)",
                    student_id,
                )
                return
            from ..cta.cognitive_twin import CognitiveTwinAgent
            self._cognitive_twin[student_id] = CognitiveTwinAgent.from_state(state)

        # append_human_feedback 走 allowlisted mutation (FUNC_ALLOWLIST)
        self._cognitive_twin[student_id].append_human_feedback(entry)

    # ---------------------------------------------------------------
    # v0.92.0-b: Twin 第 4 维度 — append_action_history (LCA 内部自动记录, Plugin SDK 不加新 subscriber)
    # ---------------------------------------------------------------

    def append_action_history(
        self,
        student_id: str,
        entry: "ActionEntry",
        state: Optional[BeliefState] = None,
    ) -> None:
        """v0.92.0-b: 追加 ActionEntry 到 per-student CognitiveTwinAgent.action_history.

        LCAEngine.select_intervention Step 7 (自动记录 intervention_selected) +
        update (自动记录 reward_recorded) 调此方法. Plugin SDK 不加新 subscriber — action_recorded
        由 LCA 内部自动记录, 跟前 3 维度 human_feedback 主动注入 pattern 不同.

        Args:
            student_id: 学生 ID
            entry: ActionEntry 实例 (5 action_type 校验已通过, frozen)
            state: Optional[BeliefState] for lazy init CognitiveTwinAgent.
                   None 时若 student_id 不在 _cognitive_twin dict, skip (下次 select
                   时 select_intervention 走 from_state 兜底).

        防御性自检 [8]: CognitiveTwinAgent.append_action_history 是 allowlisted mutation
        (FUNC_ALLOWLIST += "append_action_history", 跟 append_human_feedback 完全同模式).

        c 阶段: select_intervention 消费 cognitive_twin.action_history
                (Designer._action_history_itype_override + Evaluator.action_history_reward_adjustment)
        """
        # v0.92.0-b: lazy init CognitiveTwinAgent from state (跟 append_human_feedback 完全 parallel)
        if student_id not in self._cognitive_twin:
            if state is None:
                _log.debug(
                    "LCAEngine.append_action_history: student_id=%s 没 state, "
                    "skip lazy init (下次 select 会兜底)",
                    student_id,
                )
                return
            from ..cta.cognitive_twin import CognitiveTwinAgent
            self._cognitive_twin[student_id] = CognitiveTwinAgent.from_state(state)

        # append_action_history 走 allowlisted mutation (FUNC_ALLOWLIST)
        self._cognitive_twin[student_id].append_action_history(entry)

    def bind_cognitive_twin(
        self,
        student_id: str,
        belief_state: BeliefState,
    ) -> Optional["CognitiveTwinAgent"]:
        """v0.91.0-d: Materialize CognitiveTwinAgent from pending dict + restored belief_state.

        在 LCAEngine.load_state 之后调用 (web/api/belief.py apply_snapshot 路径),
        把暂存的 cognitive_twin dict 重建为完整 CognitiveTwinAgent 实例.

        Args:
            student_id: 学生 ID
            belief_state: 已 restore 的 BeliefState 实例 (含 trajectory 引用)

        Returns:
            CognitiveTwinAgent 实例 (或 None — 老 snapshot 无 cognitive_twin 字段时)

        防御性自检 [5]: cognitive_twin schema_version 不匹配 raise ValueError
                          (per HumanFeedbackTrajectory.from_dict / CognitiveTwinAgent.load_state)
        """
        cognitive_twin_dict = self._cognitive_twin_pending.pop(student_id, None)
        if cognitive_twin_dict is None:
            # 老 snapshot 无 cognitive_twin 字段, 或 student 不在 pending
            return None
        from ..cta.cognitive_twin import CognitiveTwinAgent
        twin = CognitiveTwinAgent.load_state(cognitive_twin_dict, belief_state)
        self._cognitive_twin[student_id] = twin
        return twin

    # ---------------------------------------------------------------
    # v0.93.0-b: POMDP T/R 后验可视化 — get_pomdp_diagnostic + _collect_pomdp_diagnostic
    # ---------------------------------------------------------------

    def get_pomdp_diagnostic(
        self,
        student_id: str,
    ) -> Optional["POMDPDiagnostic"]:
        """v0.93.0-b: 拿 per-student POMDP diagnostic (Twin 第 5 维度 — T/R 后验可视化).

        Args:
            student_id: 学生 ID

        Returns:
            POMDPDiagnostic (frozen dataclass, 含 T/R/belief/coverage/most_likely_state/
            last_updated/schema_version) 或 None:
              - 缓存命中 (上次 select/update 调过 _collect_pomdp_diagnostic): 返缓存值
              - 缓存 miss + policy_type=="pomdp" + learner.pomdp not None: lazy collect
              - 缓存 miss + 非 POMDP policy: 返 None + _log.warning (per 防御性自检 [1])

        防御性自检 [1]:
          - 派生异常 → _log.warning + 返 None (silent pass 防御)
          - 非 POMDP policy → _log.warning + 返 None (per 防御性自检 [1])
        """
        # 缓存命中
        cached = self._pomdp_diagnostic.get(student_id)
        if cached is not None:
            return cached

        # 缓存 miss → 检查 POMDP policy 是否存在
        if self.policy_learner.config.policy_type != "pomdp":
            _log.warning(
                "LCAEngine.get_pomdp_diagnostic: student_id=%s policy_type=%s 不是 POMDP, 返 None",
                student_id, self.policy_learner.config.policy_type,
            )
            return None

        learner = self.policy_learner._learners.get(student_id)
        if learner is None or learner.pomdp is None:
            _log.warning(
                "LCAEngine.get_pomdp_diagnostic: student_id=%s POMDP learner 不存在, 返 None",
                student_id,
            )
            return None

        # lazy collect
        return self._collect_pomdp_diagnostic(student_id)

    def _collect_pomdp_diagnostic(
        self,
        student_id: str,
    ) -> Optional["POMDPDiagnostic"]:
        """v0.93.0-b: 内部 helper, 派生 + 缓存 per-student POMDPDiagnostic.

        select_intervention pomdp path 自动调, Runtime.diagnose_pomdp 缓存 miss 时也调.
        POMDPPolicy.get_diagnostic() 内部已有 lazy init + silent pass 防御, 这里加 try/except
        兜底 (双层防御).

        Args:
            student_id: 学生 ID

        Returns:
            POMDPDiagnostic (写入 self._pomdp_diagnostic[student_id]) 或 None:
              - learner 不存在 / pomdp 为 None → 返 None
              - POMDPPolicy.get_diagnostic() 异常 → _log.warning + 返 None

        防御性自检 [8]: _pomdp_diagnostic dict mutation 走 self mutation (LCAEngine self
                       mutation 不触及 BeliefState).
        """
        learner = self.policy_learner._learners.get(student_id)
        if learner is None or learner.pomdp is None:
            return None
        try:
            diagnostic = learner.pomdp.get_diagnostic()
            self._pomdp_diagnostic[student_id] = diagnostic
            return diagnostic
        except Exception as e:  # noqa: BLE001
            _log.warning(
                "LCAEngine._collect_pomdp_diagnostic: POMDPPolicy.get_diagnostic 失败 "
                "(sid=%s, err=%s), skip",
                student_id, e, exc_info=True,
            )
            return None

    # ---------------------------------------------------------------
    # v0.69.0: LinUCB 冷启动判定 (B4 前置)
    # ---------------------------------------------------------------

    def _is_linucb_cold_start(self, student_id: str) -> bool:
        """判定 LinUCB 是否处于冷启动期 (v0.82.0-d 委托 PolicyLearner.is_cold_start).

        v0.69.0: 用于决定 dual_agent_confidence 来源
          - 冷启动期: 走 _estimate_gain 简化估算 (source="estimate_gain_fallback")
          - 非冷启动期: 走 LinUCB θ@x 预测 (source="linucb")

        旧逻辑 (v0.81) 直接读 self.bandits.get(student_id) + arm_pull_counts.sum(),
        v0.82.0-d 抽到 PolicyLearner.is_cold_start (LCA 4-layer 第 4 层).
        backward compat: 保留方法, 因为 dual_agent/orchestrator.py:575 调.
        """
        return self.policy_learner.is_cold_start(student_id)

    # ---------------------------------------------------------------
    # v0.57.0: per-student bandit 隔离 (保留为 backward-compat shim)
    # v0.82.0-d: 委托 PolicyLearner._get_learner
    # ---------------------------------------------------------------

    def _get_bandit(self, student_id: str) -> "LCAPolicyLearner":
        """获取 per-student bandit (lazy init, v0.82.0-d 委托 PolicyLearner).

        v0.57.0: 修复 v0.56.0 单 bandit 多学生数据冲突 BUG.
                  每个学生独立 LCAPolicyLearner 实例, LinUCB A/b 矩阵隔离.

        v0.82.0-d: 实现迁到 PolicyLearner._get_learner, 这里只做委托.
        backward compat: 保留方法, 因为 web/api/lca.py:300 / tests/test_lca_*.py 大量访问.
        """
        return self.policy_learner._get_learner(student_id)

    def dump_state(self, student_id: str) -> dict:
        """导出 per-student LCA 状态 (9 字段 + 内部辅助字段).

        v0.82.0-d: 拆 LCAEngine 跟 PolicyLearner 边界
          - LCAEngine 维护: intervention_history, last_intervention, update_count, select_count
          - PolicyLearner 维护: bandit_a, bandit_b, arm_pull_counts, arm_fingerprints, last_arm
        v0.91.0-d: 加 cognitive_twin 字段 (Twin → Human Twin 抽象)
        v0.93.0-c: 加 pomdp_diagnostic 字段 (Twin 第 5 维度 — POMDP T/R 后验可视化 + 演化追踪)

        Returns:
            dict 含 9 关键字段 (CLAUDE.md [5]):
              1. intervention_history  (List[Intervention.to_dict()])
              2. bandit_a              (List[List[List[float]]])  <- 来自 PolicyLearner.dump
              3. bandit_b              (List[List[float]])        <- 来自 PolicyLearner.dump
              4. arm_pull_counts       (List[int])                <- 来自 PolicyLearner.dump
              5. last_intervention     (Intervention.to_dict() | None)
              6. update_count          (int)
              7. select_count          (int)
              8. cognitive_twin        (Dict | None)              <- v0.91.0-d 新增
              9. pomdp_diagnostic      (Dict | None)              <- v0.93.0-c 新增
            + 内部字段:
              - arm_fingerprints       (Dict[str, str])  arm_idx → intervention_id  <- PolicyLearner.dump
              - last_arm               (int)                                        <- PolicyLearner.dump
        """
        # v0.82.0-d: LinUCB 部分委托 PolicyLearner.dump
        policy_state = self.policy_learner.dump(student_id)

        last_iv = self._last_intervention.get(student_id)
        # v0.91.0-d: cognitive_twin dump (None 时不存字段, 保持 backward compat)
        cognitive_twin = self._cognitive_twin.get(student_id)
        cognitive_twin_dict = (
            cognitive_twin.dump_state() if cognitive_twin is not None else None
        )
        # v0.93.0-c: pomdp_diagnostic dump (None 时不存字段, 老 snapshot backward compat)
        #   POMDP policy 不在用 / 派生失败 → None 兜底, load_state graceful skip
        pomdp_diagnostic = self._pomdp_diagnostic.get(student_id)
        pomdp_diagnostic_dict = (
            pomdp_diagnostic.to_dict() if pomdp_diagnostic is not None else None
        )
        return {
            # 1. intervention_history (LCAEngine 维护)
            "intervention_history": [iv.to_dict() for iv in self.intervention_history.get(student_id, [])],
            # 2-4. LinUCB 核心 (PolicyLearner 维护)
            "bandit_a": policy_state["bandit_a"],
            "bandit_b": policy_state["bandit_b"],
            "arm_pull_counts": policy_state["arm_pull_counts"],
            # 5. last_intervention (LCAEngine 维护)
            "last_intervention": last_iv.to_dict() if last_iv else None,
            # 6-7. 计数 (LCAEngine 维护)
            "update_count": self._update_count.get(student_id, 0),
            "select_count": self._select_count.get(student_id, 0),
            # 8. cognitive_twin (v0.91.0-d 新增, Twin → Human Twin 抽象)
            "cognitive_twin": cognitive_twin_dict,
            # 9. pomdp_diagnostic (v0.93.0-c 新增, Twin 第 5 维度 — POMDP T/R 后验可视化)
            "pomdp_diagnostic": pomdp_diagnostic_dict,
            # 内部辅助 (LinUCB select arm 需要, PolicyLearner 维护)
            "arm_fingerprints": policy_state["arm_fingerprints"],
            "last_arm": policy_state["last_arm"],
        }

    def load_state(self, student_id: str, snapshot: dict) -> None:
        """加载 per-student LCA 状态 (8 字段全恢复).

        Args:
            student_id: 学生 ID
            snapshot: dump_state() 导出的 dict

        防御性自检 [5]: 8 关键字段必须全恢复, 缺一不可 (否则 LinUCB 学错位).
        v0.82.0-d: LinUCB 部分委托 PolicyLearner.load (含维度校验).
        v0.91.0-d: cognitive_twin 字段恢复 (None 时跳过 — backward compat 老 snapshot).
        """
        from .intervention import Intervention as _IV

        # 1. intervention_history (LCAEngine 维护)
        history = snapshot.get("intervention_history", []) or []
        self.intervention_history[student_id] = [_IV.from_dict(d) for d in history]

        # 2-4. LinUCB 核心 + 内部辅助 (PolicyLearner 维护, 含维度校验)
        self.policy_learner.load(student_id, snapshot)

        # 5. last_intervention (LCAEngine 维护)
        last_iv_dict = snapshot.get("last_intervention")
        if last_iv_dict:
            self._last_intervention[student_id] = _IV.from_dict(last_iv_dict)
        else:
            self._last_intervention.pop(student_id, None)

        # 6-7. 计数 (LCAEngine 维护)
        self._update_count[student_id] = int(snapshot.get("update_count", 0))
        self._select_count[student_id] = int(snapshot.get("select_count", 0))

        # 8. cognitive_twin (v0.91.0-d 新增, v0.92.0-a 升级为 4-tuple)
        #   None 或 schema_version 校验失败 → 跳过 (老 snapshot 不抛, 避免 v0.91 升级 break)
        #   schema_version != "0.92.0" → _log.warning + 跳过
        cognitive_twin_dict = snapshot.get("cognitive_twin")
        if cognitive_twin_dict is not None:
            try:
                # 注: 这里不直接调 CognitiveTwinAgent.load_state (需要 belief_state 引用,
                #   belief_state 是外部传入, 由 web/api/belief.py apply_snapshot 路径提供).
                #   LCAEngine.load_state 仅恢复 _cognitive_twin dict 的 stub, 具体 belief_state
                #   ref 由 apply_snapshot 后置绑定.
                from ..cta.cognitive_twin import CognitiveTwinAgent, SCHEMA_VERSION
                if cognitive_twin_dict.get("schema_version") != SCHEMA_VERSION:
                    _log.warning(
                        "LCAEngine.load_state: cognitive_twin schema_version=%s 不匹配 %s, skip",
                        cognitive_twin_dict.get("schema_version"), SCHEMA_VERSION,
                    )
                else:
                    # 暂存 dict, belief_state 由 caller 负责构造 CognitiveTwinAgent.from_state
                    # 后调用 lca.append_human_feedback 重建 (caller side 绑定)
                    self._cognitive_twin_pending[student_id] = cognitive_twin_dict
            except Exception:
                _log.warning(
                    "LCAEngine.load_state: cognitive_twin 恢复失败 (sid=%s), skip",
                    student_id, exc_info=True,
                )

        # 9. pomdp_diagnostic (v0.93.0-c 新增, Twin 第 5 维度 — POMDP T/R 后验可视化)
        #   老 v0.92 snapshot 没此字段 → graceful skip + _log.warning (避免 v0.92 升级 break)
        #   schema_version 不匹配 → _log.warning + skip
        pomdp_diagnostic_dict = snapshot.get("pomdp_diagnostic")
        if pomdp_diagnostic_dict is not None:
            try:
                from ..lca.l4_optimization.pomdp_diagnostic import (
                    POMDPDiagnostic, SCHEMA_VERSION as POMDP_DIAG_SV,
                )
                if pomdp_diagnostic_dict.get("schema_version") != POMDP_DIAG_SV:
                    _log.warning(
                        "LCAEngine.load_state: pomdp_diagnostic schema_version=%s 不匹配 %s, skip",
                        pomdp_diagnostic_dict.get("schema_version"), POMDP_DIAG_SV,
                    )
                else:
                    diag = POMDPDiagnostic.from_dict(pomdp_diagnostic_dict)
                    self._pomdp_diagnostic[student_id] = diag
            except Exception:
                _log.warning(
                    "LCAEngine.load_state: pomdp_diagnostic 恢复失败 (sid=%s), skip",
                    student_id, exc_info=True,
                )

    # ---------------------------------------------------------------
    # 内部工具
    # ---------------------------------------------------------------

    # v0.82.0-a: _should_review_spaced 迁移到 Planner._should_review_spaced
    # 旧逻辑保留在 PlannerConfig.mastery_threshold / trajectory_min_len 配置中

    # v0.82.0-c: _estimate_gain / _estimate_risk 实现迁到 Evaluator (LCA 4-layer 第 3 层)
    # 这里只保留 _estimate_gain 作为 backward-compat shim (dual_agent/orchestrator.py:579
    # 仍调 `self.lca_engine._estimate_gain(intervention, belief_state)`, 必须保持签名)
    def _estimate_gain(
        self,
        intervention: Intervention,
        belief_state: BeliefState,
    ) -> float:
        """估算 expected_gain (v0.82.0-c 委托 Evaluator).

        跟 v0.81 LCAEngine._estimate_gain 行为完全一致, 但实际逻辑在 self.evaluator.
        保留方法是因为 dual_agent/orchestrator.py:579 调 `self.lca_engine._estimate_gain(...)`.
        """
        return self.evaluator.estimate_gain(intervention, belief_state)


# v0.82.0-c: _estimate_risk 实现迁到 Evaluator.estimate_risk (LCA 4-layer 第 3 层)
#   LCAEngine.select_intervention 内部调 self.evaluator.estimate_risk
#   旧方法已删除 (没外部代码依赖, 跟 _estimate_gain 不同)

__all__ = ["LCAEngine", "LCAEngineConfig", "LCAResult", "CTAInput"]
