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
if TYPE_CHECKING:
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
    ) -> List[Intervention]:
        """生成候选干预池.

        Args:
            plan:        Planner.plan() 输出 (含 bloom_target/clt_level/ca_stage/bjork_triggers)
            cta_input:   CTA 输入 (用于 skill_filter)
            n_candidates: 候选池大小 (默认 self.config.n_candidates, 通常 = bandit.n_arms)
            motivation:  v0.87.0-b: 可选 MotivationProfile, 调整 itype 权重
                          (frustration > 0.7 优先 EXPLANATORY, engagement < 0.3 优先 INQUIRY,
                           confidence+engagement 高 优先 PRACTICE)

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
        """
        if n_candidates is None:
            n_candidates = self.config.n_candidates

        bloom_target = plan.bloom_target
        clt_level = plan.clt_level
        ca_stage = plan.ca_stage
        bjork_triggers = plan.bjork_triggers

        # v0.87.0-b: motivation-aware itype preference
        motivation_override = self._motivation_itype_override(motivation)

        candidates: List[Intervention] = []
        target_skills = cta_input.skill_filter or []
        # 取 bloom 标签作为 target_tcs 占位 (Phase 4+ 接 Q-Matrix)
        target_tcs = [bloom_target.name.lower()]

        for i in range(n_candidates):
            # v0.87.0-b: motivation override 优先于 default types
            if motivation_override is not None and i % 3 == 0:
                itype = motivation_override
            else:
                itype = self.config.default_types[i % len(self.config.default_types)]
            difficulty = self.config.default_difficulties[
                i % len(self.config.default_difficulties)
            ]

            # Step 1: CA 阶段调整干预类型
            itype = self._adjust_for_ca_stage(itype, ca_stage, i)

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
