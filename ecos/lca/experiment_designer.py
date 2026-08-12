"""LCA 实验设计层 (Experiment Designer) —— v0.82 LCA 4-layer split 第 2 层.

对应:
  - research/00-overview/11-ecos-2.0-architecture-proposal.md §2.2.1 LCA 4-layer
  - research/00-overview/12-kernel-mapping-current-vs-2.0.md §4 LCA Experiment Designer
  - 旧 LCAEngine._generate_candidates (orchestrator.py:129-212 v0.81.0)

职责:
  - 根据 PlanDecision (bloom_target / clt_level / ca_stage / bjork_triggers)
    + CTAInput (skill_filter) 生成候选干预池 (n_candidates arms)
  - 参数化 (difficulty / quantity / feedback_density / scaffolding_level)
  - 调整规则:
    - CA 阶段 (MODELING → EXPLANATORY 主导, COACHING → PRACTICE 主导, SCAFFOLDING → EXPLANATORY + 高 scaffolding)
    - Bjork 触发 (test → INQUIRY 强化, space → 更低 difficulty)
    - CLT 级别 (NOVICE 0.9 / DEVELOPING 0.6 / PROFICIENT 0.3 / EXPERT 0.1 scaffolding)
  - v0.87.0-b: motivation-aware itype override (frustration/engagement/confidence)
  - v0.88.0-b: domain-aware itype override (education/science/career)

设计原则:
  - ExperimentDesigner 是 2.0 §2.2.1 实验设计层, 不持有 bandit state
  - 消费 Planner.plan() 输出 (PlanDecision), 产出 List[Intervention]
  - 纯函数: 输入相同 → 输出相同 (无副作用, 便于测试)
  - 默认 10 candidate pool (DEFAULT_CANDIDATE_TYPES / DEFAULT_CANDIDATE_DIFFICULTIES)
    来自 v0.81 LCAEngine, 可通过 ExperimentDesignerConfig 自定义
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional

from .cta_input import CTAInput
from .intervention import (
    CAStage,
    CLTLevel,
    Intervention,
    InterventionType,
)
from .planner import PlanDecision

# v0.87.0-b: TYPE_CHECKING 避免循环 import (MotivationProfile 不引用 LCA, 顶层 import 也可)
# v0.91.0-c: CognitiveTwinAgent TYPE_CHECKING 避免循环 import
# v0.92.0-c: ActionHistory TYPE_CHECKING 避免循环 import
if TYPE_CHECKING:
    from ..cta.cognitive_twin import ActionHistory, CognitiveTwinAgent
    from ..motivation.profile import MotivationProfile

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 默认候选池 (v0.81 LCAEngine 同源, 跟 bandit_config.n_arms=10 对齐)
# ---------------------------------------------------------------------------

DEFAULT_CANDIDATE_TYPES: List[InterventionType] = [
    InterventionType.EXPLANATORY,
    InterventionType.EXPLANATORY,
    InterventionType.PRACTICE,
    InterventionType.PRACTICE,
    InterventionType.INQUIRY,
    InterventionType.FEEDBACK,
    InterventionType.METACOGNITIVE,
    InterventionType.EXPLANATORY,
    InterventionType.PRACTICE,
    InterventionType.INQUIRY,
]
DEFAULT_CANDIDATE_DIFFICULTIES: List[float] = [
    0.3, 0.5, 0.4, 0.6, 0.5, 0.4, 0.5, 0.7, 0.7, 0.7,
]


# ---------------------------------------------------------------------------
# Experiment Designer Config
# ---------------------------------------------------------------------------

@dataclass
class ExperimentDesignerConfig:
    """Experiment Designer 配置.

    Attributes:
        n_candidates:           默认候选池大小 (跟 bandit n_arms 对齐)
        default_types:          默认候选类型序列 (i % len(types) 取值)
        default_difficulties:   默认候选难度序列
        quantity_by_type:       各 InterventionType 的 quantity 映射
        scaffolding_by_clt:     CLT 4 级 → scaffolding_level 映射
        feedback_density_default: 默认 feedback_density (非 EXPERT)
        feedback_density_expert: EXPERT 级别 feedback_density
        domain_aware_types:     v0.88.0-b: 各 Domain 默认 itype 映射 (per design doc §3.2)
                                  - education: None (走 K12 logic, 已有)
                                  - science:   INQUIRY (苏格拉底式)
                                  - career:    PRACTICE (实战)
    """

    n_candidates: int = 10
    default_types: List[InterventionType] = field(
        default_factory=lambda: list(DEFAULT_CANDIDATE_TYPES)
    )
    default_difficulties: List[float] = field(
        default_factory=lambda: list(DEFAULT_CANDIDATE_DIFFICULTIES)
    )
    quantity_by_type: dict = field(default_factory=lambda: {
        InterventionType.EXPLANATORY: 3,
        InterventionType.PRACTICE: 8,
        InterventionType.INQUIRY: 5,
        InterventionType.FEEDBACK: 4,
        InterventionType.METACOGNITIVE: 3,
    })
    scaffolding_by_clt: dict = field(default_factory=lambda: {
        CLTLevel.NOVICE: 0.9,
        CLTLevel.DEVELOPING: 0.6,
        CLTLevel.PROFICIENT: 0.3,
        CLTLevel.EXPERT: 0.1,
    })
    feedback_density_default: float = 0.8
    feedback_density_expert: float = 0.4
    # v0.88.0-b: domain-aware itype preference (per design doc §3.2)
    # None = 走 default K12 logic (education Domain 不强制 override)
    domain_aware_types: dict = field(default_factory=lambda: {
        "education": None,  # 已有 K12 logic
        "science": InterventionType.INQUIRY,   # 科研: 苏格拉底式
        "career": InterventionType.PRACTICE,   # 职业: 实战主导
    })


# ---------------------------------------------------------------------------
# Experiment Designer 类
# ---------------------------------------------------------------------------

class ExperimentDesigner:
    """LCA 实验设计层 (v0.82 LCA 4-layer split 第 2 层).

    用法:
        designer = ExperimentDesigner(ExperimentDesignerConfig())
        candidates = designer.design(plan, cta_input, n_candidates=10)
        # -> List[Intervention] (默认 10 个, 喂给 PolicyLearner.select())

    旧代码 (LCAEngine._generate_candidates v0.81.0):
        candidates = _generate_candidates(
            bloom_target=bloom_target,
            clt_level=clt_level,
            ca_stage=ca_stage,
            bjork_triggers=bjork_triggers,
            cta_input=cta_input,
            skill_filter=cta_input.skill_filter,
            n_candidates=self.config.bandit_config.n_arms,
        )

    v0.82.0-b: 上述逻辑抽到 ExperimentDesigner.design(), LCAEngine 仅委托.
    """

    def __init__(self, config: Optional[ExperimentDesignerConfig] = None):
        self.config = config or ExperimentDesignerConfig()

    # ---------------------------------------------------------------
    # 主入口
    # ---------------------------------------------------------------

    def design(
        self,
        plan: PlanDecision,
        cta_input: CTAInput,
        n_candidates: Optional[int] = None,
        motivation: Optional["MotivationProfile"] = None,
        domain_name: Optional[str] = None,
        cognitive_twin: Optional["CognitiveTwinAgent"] = None,
        action_history: Optional["ActionHistory"] = None,
    ) -> List[Intervention]:
        """生成候选干预池.

        Args:
            plan:        Planner.plan() 输出 (含 bloom_target/clt_level/ca_stage/bjork_triggers)
            cta_input:   CTA 输入 (用于 skill_filter)
            n_candidates: 候选池大小 (默认 self.config.n_candidates, 通常 = bandit.n_arms)
            motivation:  v0.87.0-b: 可选 MotivationProfile, 调整 itype 权重
                          (frustration > 0.7 优先 EXPLANATORY, engagement < 0.3 优先 INQUIRY,
                           confidence+engagement 高 优先 PRACTICE)
            domain_name: v0.88.0-b: 可可 Domain name (e.g. "education"/"science"/"career"),
                          调整 itype 权重 (science → INQUIRY, career → PRACTICE).
                          None = 不做 domain override (走 K12 default)
            cognitive_twin: v0.91.0-c: 可选 CognitiveTwinAgent, 调整 itype 权重
                          (hint_requested > 5 → EXPLANATORY, idle_detected > 3 → INQUIRY,
                           reflection_completed > 3 → PRACTICE, goal_changed > 1 → PRACTICE).
                          None = 不做 human_feedback override (走 default).
            action_history: v0.92.0-c: 可选 ActionHistory (Twin 第 4 维度, LCA 内部自动记录),
                          调整 itype 权重 (reward_recorded 平均 < 0.5 → PRACTICE, dual_agent_calibrated
                          平均 reward > 0.7 → EXPLANATORY, type_diversity → INQUIRY 切换,
                          policy_updated < 3 → default, goal_changed > 1 → PRACTICE).
                          None = 不做 action_history override (走 default).

        Returns:
            List[Intervention] 长度 = n_candidates

        调整规则 (跟 v0.81 LCAEngine._generate_candidates 行为一致):
          1. CA 阶段 (MODELING/COACHING/SCAFFOLDING) → 调整 itype
          2. Bjork trigger "test" + INQUIRY → 加 "retrieval" 标签
          3. Bjork trigger "space" → difficulty ≤ 0.5
          4. CLT level → scaffolding_level (0.9/0.6/0.3/0.1)
          5. InterventionType → quantity (3/8/5/4/3)
          6. CLT != EXPERT → feedback_density 0.8, EXPERT → 0.4
          7. v0.87.0-b: motivation 调整 itype 权重 (frustration/engagement/confidence)
          8. v0.88.0-b: domain 调整 itype 权重 (science=INQUIRY / career=PRACTICE)
          9. v0.91.0-c: human_feedback 调整 itype 权重 (hint/idle/reflection/goal)
                          (优先级: motivation > human_feedback > domain > default)
          10. v0.92.0-c: action_history 调整 itype 权重 (reward/dual_agent/type_diversity/policy/goal)
                          (优先级: motivation > human_feedback > action_history > domain > default)
        """
        if n_candidates is None:
            n_candidates = self.config.n_candidates

        bloom_target = plan.bloom_target
        clt_level = plan.clt_level
        ca_stage = plan.ca_stage
        bjork_triggers = plan.bjork_triggers

        # v0.87.0-b: motivation-aware itype preference
        motivation_override = self._motivation_itype_override(motivation)
        # v0.88.0-b: domain-aware itype preference
        domain_override = self._domain_itype_override(domain_name)
        # v0.91.0-c: human_feedback-aware itype preference (优先级: motivation > human_feedback > domain)
        human_feedback_override = self._human_feedback_itype_override(cognitive_twin)
        # v0.92.0-c: action_history-aware itype preference (优先级: motivation > human_feedback > action_history > domain)
        action_history_override = self._action_history_itype_override(action_history)

        candidates: List[Intervention] = []
        target_skills = cta_input.skill_filter or []
        # 取 bloom 标签作为 target_tcs 占位 (Phase 4+ 接 Q-Matrix)
        target_tcs = [bloom_target.name.lower()]

        for i in range(n_candidates):
            # v0.87.0-b: motivation override 优先于 default types
            # v0.88.0-b: domain override (优先级: motivation > domain > default)
            # v0.91.0-c: human_feedback override (优先级: motivation > human_feedback > domain > default)
            # v0.92.0-c: action_history override (优先级: motivation > human_feedback > action_history > domain > default)
            if motivation_override is not None and i % 3 == 0:
                itype = motivation_override
            elif human_feedback_override is not None and i % 3 == 1:
                itype = human_feedback_override
            elif action_history_override is not None and i % 3 == 2:
                itype = action_history_override
            elif domain_override is not None and i % 3 == 2:
                itype = domain_override
            else:
                itype = self.config.default_types[i % len(self.config.default_types)]
            difficulty = self.config.default_difficulties[
                i % len(self.config.default_difficulties)
            ]

            # Step 1: CA 阶段调整干预类型
            itype = self._adjust_for_ca_stage(itype, ca_stage, i)

            # v0.88.0-b: domain override 在 CAStage 调整之后 (domain 有最终决定权, per design doc §3.2)
            if domain_override is not None and i % 3 == 2:
                itype = domain_override

            # Step 2: Bjork 触发调整
            bjork = list(bjork_triggers)
            if "test" in bjork and itype == InterventionType.INQUIRY:
                # 强化测试效应
                bjork.append("retrieval")
            if "space" in bjork:
                # 间隔模式: 更低难度
                difficulty = min(difficulty, 0.5)

            # v0.87.0-b: frustration > 0.7 → 降难度, 提 scaffolding
            if motivation is not None and motivation.frustration > 0.7:
                difficulty = min(difficulty, 0.4)
                # 提升 scaffolding_factor 间接通过 _adjust_for_ca_stage
                # (NOVICE/DEVELOPING 已经有高 scaffolding, 这里不重复)

            # Step 3: scaffolding_level 与 CLTLevel 对齐
            scaffolding = self.config.scaffolding_by_clt[clt_level]

            # Step 4: quantity 调整 (按 InterventionType)
            quantity = self.config.quantity_by_type[itype]

            # Step 5: feedback_density (EXPERT 走 0.4, 其他走 0.8)
            feedback_density = (
                self.config.feedback_density_expert
                if clt_level == CLTLevel.EXPERT
                else self.config.feedback_density_default
            )

            intervention = Intervention(
                intervention_type=itype,
                bloom_target=bloom_target,
                target_skills=target_skills[:3],
                # Phase 5+ 接 TC 容器: 当前用空 list (M2 W2 不阻塞)
                target_misconceptions=[],
                target_tcs=target_tcs,
                difficulty=difficulty,
                quantity=quantity,
                feedback_density=feedback_density,
                scaffolding_level=scaffolding,
                clt_level=clt_level,
                ca_stage=ca_stage,
                bjork_triggers=bjork,
                expected_gain=0.0,  # 由 LCAEngine 在 select 阶段补全 (Evaluator 估算)
                expected_risk=0.0,
            )
            candidates.append(intervention)
        return candidates

    @staticmethod
    def _motivation_itype_override(
        motivation: Optional["MotivationProfile"],
    ) -> Optional[InterventionType]:
        """v0.87.0-b: motivation-aware itype preference.

        规则 (per design doc §3.2):
          - frustration > 0.7: 返 EXPLANATORY (放松, 减少压力)
          - engagement < 0.3: 返 INQUIRY (激活兴趣)
          - confidence > 0.7 AND engagement > 0.6: 返 PRACTICE (巩固)
          - 其他: 返 None (走 default_types)
        """
        if motivation is None:
            return None
        try:
            if motivation.frustration > 0.7:
                return InterventionType.EXPLANATORY
            if motivation.engagement < 0.3:
                return InterventionType.INQUIRY
            if motivation.confidence > 0.7 and motivation.engagement > 0.6:
                return InterventionType.PRACTICE
        except Exception:
            _log.warning(
                "ExperimentDesigner._motivation_itype_override 异常, 返 None",
                exc_info=True,
            )
        return None

    def _domain_itype_override(
        self,
        domain_name: Optional[str],
    ) -> Optional[InterventionType]:
        """v0.88.0-b: domain-aware itype preference.

        规则 (per design doc §3.2):
          - education: 返 None (走 K12 default logic, 已有)
          - science:   返 INQUIRY (苏格拉底式, 探索驱动)
          - career:    返 PRACTICE (实战主导)
          - 其他 (含 None): 返 None (走 default_types)

        Args:
            domain_name: Domain name (e.g. "education"/"science"/"career")

        Returns:
            Optional[InterventionType] (None = 不 override)
        """
        if domain_name is None:
            return None
        try:
            override = self.config.domain_aware_types.get(domain_name)
            return override
        except Exception:
            _log.warning(
                "ExperimentDesigner._domain_itype_override 异常, 返 None",
                exc_info=True,
            )
            return None

    @staticmethod
    def _human_feedback_itype_override(
        cognitive_twin: Optional["CognitiveTwinAgent"],
    ) -> Optional[InterventionType]:
        """v0.91.0-c: human feedback-aware itype preference (Twin → Human Twin).

        规则 (per design doc §3.3):
          - hint_requested > 5:    返 EXPLANATORY (学生主动求助 → 详细讲解)
          - idle_detected > 3:     返 INQUIRY     (走神 → 提问激活兴趣)
          - reflection_completed > 3: 返 PRACTICE  (深度反思 → 巩固练习)
          - goal_changed > 1:      返 PRACTICE    (目标调整后 → 巩固新方向)

        条件互斥 (优先级: hint > idle > reflection > goal_change):
          hint_requested > 5 EXPLANATORY 优先 (说明学生在卡题, 帮学生)
          else idle_detected > 3 INQUIRY (走神, 提问拉回)
          else reflection_completed > 3 PRACTICE (深度反思后巩固)
          else goal_changed > 1 PRACTICE (目标调整后巩固)

        不满足 → 返 None (走 default_types).

        Args:
            cognitive_twin: Optional[CognitiveTwinAgent] (v0.91.0-a 数据结构).
                            None 时返 None (无 human_feedback 数据).

        Returns:
            Optional[InterventionType] (None = 不 override)

        防御性自检 [1]: cognitive_twin.human_feedback 缺失/异常 _log.warning + 返 None
        """
        if cognitive_twin is None:
            return None
        try:
            hf = cognitive_twin.human_feedback
            if hf is None:
                return None
            # 优先级: hint > idle > reflection > goal_change
            if hf.count_by_type("hint_requested") > 5:
                return InterventionType.EXPLANATORY
            if hf.count_by_type("idle_detected") > 3:
                return InterventionType.INQUIRY
            if hf.count_by_type("reflection_completed") > 3:
                return InterventionType.PRACTICE
            if hf.count_by_type("goal_changed") > 1:
                return InterventionType.PRACTICE
        except Exception:
            _log.warning(
                "ExperimentDesigner._human_feedback_itype_override 异常, 返 None",
                exc_info=True,
            )
        return None

    @staticmethod
    def _action_history_itype_override(
        action_history: Optional["ActionHistory"],
    ) -> Optional[InterventionType]:
        """v0.92.0-c: action_history-aware itype preference (Twin 第 4 维度).

        规则 (per v0.92 plan §v0.92.0-c, 5 case 优先级: reward_low > type_diversity >
              dual_agent > policy_cold > goal_changed):
          1. reward_recorded 平均 < 0.5 + 累计 ≥ 5 → PRACTICE   (低 gain 学生需更多练习)
          2. intervention_selected 在某 type (e.g. EXPLANATORY) 累计 > 10 →
             切换该 type → INQUIRY                              (避免单调, 改 INQUIRY)
          3. dual_agent_calibrated 平均 reward > 0.7 → EXPLANATORY (互校确认学生掌握)
          4. policy_updated 累计 < 3 → None (default)            (冷启动期稳定探索)
          5. goal_changed 累计 > 1 → PRACTICE                   (跟 human_feedback.goal_changed 同)

        优先级: reward_low > type_diversity > dual_agent > policy_cold > goal_changed
        不满足 → 返 None (走 default_types).

        Args:
            action_history: Optional[ActionHistory] (v0.92.0-a 数据结构, Twin 第 4 维度).
                            None 时返 None (无 action_history 数据).

        Returns:
            Optional[InterventionType] (None = 不 override)

        防御性自检 [1]: action_history 缺失/异常 _log.warning + 返 None
        """
        if action_history is None:
            return None
        try:
            ah = action_history
            if ah is None:
                return None
            # 1. reward_recorded 平均 < 0.5 + 累计 ≥ 5 → PRACTICE
            reward_count = ah.count_by_type("reward_recorded")
            if reward_count >= 5:
                rewards = [e.reward for e in ah.entries if e.action_type == "reward_recorded" and e.reward is not None]
                if rewards and sum(rewards) / len(rewards) < 0.5:
                    return InterventionType.PRACTICE
            # 2. type_diversity (intervention_selected 在某 type > 10 → INQUIRY)
            #   从 metadata["bloom_target"] 聚合 (LCA 自动记录的 action_history 字段)
            type_counter: dict = {}
            for e in ah.entries:
                if e.action_type == "intervention_selected" and "bloom_target" in e.metadata:
                    type_counter[e.metadata["bloom_target"]] = type_counter.get(e.metadata["bloom_target"], 0) + 1
            if any(v > 10 for v in type_counter.values()):
                return InterventionType.INQUIRY
            # 3. dual_agent_calibrated 平均 reward > 0.7 → EXPLANATORY
            dual_count = ah.count_by_type("dual_agent_calibrated")
            if dual_count >= 1:
                dual_rewards = [e.reward for e in ah.entries if e.action_type == "dual_agent_calibrated" and e.reward is not None]
                if dual_rewards and sum(dual_rewards) / len(dual_rewards) > 0.7:
                    return InterventionType.EXPLANATORY
            # 4. policy_updated 累计 < 3 → None (冷启动期稳定探索, 不 override)
            #   (policy_updated < 3 = 冷启动期, 不 override 让 designer 自由选)
            # 5. goal_changed 累计 > 1 → PRACTICE (跟 human_feedback.goal_changed 同)
            if ah.count_by_type("goal_changed") > 1:
                return InterventionType.PRACTICE
        except Exception:
            _log.warning(
                "ExperimentDesigner._action_history_itype_override 异常, 返 None",
                exc_info=True,
            )
        return None

    # ---------------------------------------------------------------
    # 内部工具
    # ---------------------------------------------------------------

    @staticmethod
    def _adjust_for_ca_stage(
        itype: InterventionType,
        ca_stage: CAStage,
        idx: int,
    ) -> InterventionType:
        """CA 阶段调整干预类型 (跟 v0.81 _generate_candidates 行为一致).

        - MODELING: 第 0/3/6/9... (i % 3 == 0) 保留, 其他 → EXPLANATORY
        - COACHING: PRACTICE / FEEDBACK 保留, 其他 → PRACTICE
        - SCAFFOLDING: EXPLANATORY / METACOGNITIVE 保留, 其他 → EXPLANATORY
        """
        if ca_stage == CAStage.MODELING:
            if idx % 3 != 0:
                return InterventionType.EXPLANATORY
        elif ca_stage == CAStage.COACHING:
            if itype not in (InterventionType.PRACTICE, InterventionType.FEEDBACK):
                return InterventionType.PRACTICE
        elif ca_stage == CAStage.SCAFFOLDING:
            if itype not in (InterventionType.EXPLANATORY, InterventionType.METACOGNITIVE):
                return InterventionType.EXPLANATORY
        return itype


__all__ = [
    "ExperimentDesigner",
    "ExperimentDesignerConfig",
    "DEFAULT_CANDIDATE_TYPES",
    "DEFAULT_CANDIDATE_DIFFICULTIES",
]
