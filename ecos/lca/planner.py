"""LCA 决策层 (Planner) —— v0.82 LCA 4-layer split 第 1 层.

对应:
  - research/00-overview/11-ecos-2.0-architecture-proposal.md §2.2.1 LCA 4-layer
  - research/00-overview/12-kernel-mapping-current-vs-2.0.md §4 LCA Planner
  - 旧 LCAEngine.select_intervention step 1-4 (orchestrator.py:313-332 v0.81.0)

职责:
  - Step 1: Bloom 目标层选择 (select_bloom_target)
  - Step 2: CA 阶段判定 (CAStateMachine.transition)
  - Step 3: CLT 4 级呈现 (AdaptiveCLTPresender.determine_level)
  - Step 4: Bjork 触发判定 (BjorkTestingEffect + BjorkSpacingEffect)

设计原则 (沿用 v0.80 CTA 4-layer):
  - Planner 是 2.0 §2.2.1 决策层, 不持有 reward/attribution/linucb 状态
  - 持有 L3 组件 (CLT/Bjork/CA scaffolding) + CAStateMachine (per-student 阶段状态)
  - 输出 PlanDecision 不可变值对象, 给 ExperimentDesigner / PolicyLearner 后置消费
  - rationale / risk / gain 后续由 Evaluator 补全, 避免 Planner 循环依赖
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from ..cta.belief_state import BeliefState, BloomLevel
from .intervention import (
    CAStage,
    CLTLevel,
    Intervention,
    select_bloom_target,
)
from .l3_selection import (
    AdaptiveCLTPresender,
    BjorkSpacingEffect,
    BjorkTestingEffect,
    CAConfig,
    CAScaffoldingDecay,
    CLTConfig,
)
from .l4_optimization import CAStateMachine

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Planner Config
# ---------------------------------------------------------------------------

@dataclass
class PlannerConfig:
    """Planner 配置 (LCAEngineConfig.planner_config 注入).

    Attributes:
        clt_config:       CLT 4 级自适应配置
        ca_config:        CA scaffolding 衰减配置
        mastery_threshold: 间隔复习触发阈值 (K mastery_prob > threshold + trajectory 长度)
        trajectory_min_len: 间隔复习所需 trajectory 最小长度
    """

    clt_config: CLTConfig = field(default_factory=CLTConfig)
    ca_config: CAConfig = field(default_factory=CAConfig)
    # v0.81 旧 LCAEngine._should_review_spaced 阈值, 显式配置化
    #   旧逻辑: belief_state.K.mastery_prob > 0.5 AND len(trajectory) >= 5
    mastery_threshold: float = 0.5
    trajectory_min_len: int = 5


# ---------------------------------------------------------------------------
# Planner Output (不可变值对象)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PlanDecision:
    """Planner 输出 (含 L3 全部教学法决策).

    v0.82 4-layer: ExperimentDesigner 消费 bloom_target + ca_stage + clt_level,
                   PolicyLearner 消费 bjork_triggers 调 LinUCB 上下文,
                   Evaluator 消费全部字段算 expected_gain/risk.

    Attributes:
        bloom_target:   目标 Bloom 层 (1-6)
        ca_stage:       CA 阶段 (MODELING/COACHING/SCAFFOLDING/...)
        clt_level:      CLT 呈现级别 (NOVICE/DEVELOPING/PROFICIENT/EXPERT)
        bjork_triggers: Bjork 触发标签列表 (test/space/...)
    """

    bloom_target: BloomLevel
    ca_stage: CAStage
    clt_level: CLTLevel
    bjork_triggers: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Planner 类
# ---------------------------------------------------------------------------

class Planner:
    """LCA 决策层 (v0.82 LCA 4-layer split 第 1 层).

    用法:
        planner = Planner(PlannerConfig())
        plan = planner.plan(cta_input)
        # -> PlanDecision(bloom_target, ca_stage, clt_level, bjork_triggers)

    旧代码 (LCAEngine.select_intervention step 1-4, v0.81.0):
        # Step 1: Bloom 目标层
        bloom_target = select_bloom_target(belief_state, candidates_bloom, belief_state.learning_dna)
        # Step 2: CA 阶段
        ca_stage = self.ca_state_machine.transition(student_id, belief_state, history)
        # Step 3: CLT 4 级
        clt_level = self.clt.determine_level(student_id, belief_state)
        # Step 4: Bjork 触发
        bjork_triggers = []
        if self.bjork_testing.should_insert_test(belief_state):
            bjork_triggers.append("test")
        if self._should_review_spaced(belief_state):
            bjork_triggers.append("space")

    v0.82.0-a: 上述 4 步抽到 Planner.plan(), LCAEngine 仅委托.
    """

    def __init__(self, config: Optional[PlannerConfig] = None):
        self.config = config or PlannerConfig()

        # L3 教学法组件 (复用, 不动 l3_selection/)
        self.clt = AdaptiveCLTPresender(self.config.clt_config)
        self.bjork_testing = BjorkTestingEffect()
        self.bjork_spacing = BjorkSpacingEffect()
        self.ca_scaffolding = CAScaffoldingDecay(self.config.ca_config)

        # CA 状态机 (per-student 阶段状态, 来自 l4_optimization/)
        #   CA 状态机是"决策辅助", 不是"策略学习", 放 Planner 更合适
        self.ca_state_machine = CAStateMachine()

    # ---------------------------------------------------------------
    # 主入口
    # ---------------------------------------------------------------

    def plan(
        self,
        cta_input,
        intervention_history: Optional[List[Intervention]] = None,
    ) -> PlanDecision:
        """LCA 决策入口 (4 步合一).

        Args:
            cta_input: CTA 输入 (含 student_id + BeliefState + bloom candidates)
            intervention_history: 历史干预列表 (LCAEngine 注入, 用于 CA 阶段判定
                的 _can_articulate / _has_tried_independently PRACTICE 检查).
                默认 None → 使用 [] (跟 v0.81 LCAEngine 冷启动行为一致).

        Returns:
            PlanDecision (不可变)
        """
        belief_state = cta_input.belief_state
        student_id = cta_input.student_id
        candidates_bloom = cta_input.bloom_target_candidates or list(BloomLevel)
        history = intervention_history or []

        # Step 1: Bloom 目标层
        bloom_target = select_bloom_target(
            belief_state,
            candidates_bloom,
            belief_state.learning_dna,
        )

        # Step 2: CA 阶段 (per-student 状态, 由 ca_state_machine 持有)
        #   history 由 LCAEngine 注入 (LCAEngine.intervention_history per-student)
        ca_stage = self.ca_state_machine.transition(student_id, belief_state, history)

        # Step 3: CLT 4 级
        clt_level = self.clt.determine_level(student_id, belief_state)

        # Step 4: Bjork 触发
        bjork_triggers: List[str] = []
        if self.bjork_testing.should_insert_test(belief_state):
            bjork_triggers.append("test")
        if self._should_review_spaced(belief_state):
            bjork_triggers.append("space")

        return PlanDecision(
            bloom_target=bloom_target,
            ca_stage=ca_stage,
            clt_level=clt_level,
            bjork_triggers=bjork_triggers,
        )

    # ---------------------------------------------------------------
    # 内部工具
    # ---------------------------------------------------------------

    def _should_review_spaced(self, belief_state: BeliefState) -> bool:
        """判断是否应触发间隔复习 (迁移自 v0.81 LCAEngine._should_review_spaced).

        规则: K mastery_prob > threshold + trajectory 长度 ≥ trajectory_min_len
        """
        if belief_state.K.mastery_prob > self.config.mastery_threshold:
            if len(belief_state.trajectory.snapshots) >= self.config.trajectory_min_len:
                return True
        return False


__all__ = ["Planner", "PlannerConfig", "PlanDecision"]
