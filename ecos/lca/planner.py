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
from typing import Any, Dict, List, Optional

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
        bloom_target:       目标 Bloom 层 (1-6)
        ca_stage:           CA 阶段 (MODELING/COACHING/SCAFFOLDING/...)
        clt_level:          CLT 呈现级别 (NOVICE/DEVELOPING/PROFICIENT/EXPERT)
        bjork_triggers:     Bjork 触发标签列表 (test/space/...)
        review_schedule:    v0.97.1 skill → 复习时间表 ( BjorkSpacingEffect 输出,
                            datetime 已转 isoformat 字符串, 供 designer 写入
                            Intervention.metadata["review_schedule"])。空 dict =
                            未触发 / 未提供 skill_mastery_view
        scaffolding_adjust: v0.97.1 scaffolding 有界增量 [-0.2, +0.2] (CA
                            streaks fade/restore, designer 叠加在 CLT 映射上)。
                            None = 未提供 skill_mastery_view / streaks 未达阈值
    """

    bloom_target: BloomLevel
    ca_stage: CAStage
    clt_level: CLTLevel
    bjork_triggers: List[str] = field(default_factory=list)
    review_schedule: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    scaffolding_adjust: Optional[float] = None


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
        #   v0.97.1: 提供 skill_mastery_view 时, spacing 走 per-skill 数据驱动
        #   (bjork_spacing.get_review_schedule 消费 decayed/last_ts), scaffolding
        #   走 CA streaks 有界增量; None → legacy 规则 (向后兼容, 黄金回归基线不变)
        view = cta_input.skill_mastery_view
        bjork_triggers: List[str] = []
        review_schedule: Dict[str, Dict[str, Any]] = {}
        scaffolding_adjust: Optional[float] = None
        if self.bjork_testing.should_insert_test(belief_state):
            bjork_triggers.append("test")
        if view:
            spacing_skills = self._spacing_candidates_from_view(view)
            for sid in spacing_skills:
                bjork_triggers.append("space")
                info = view[sid]
                schedule = self.bjork_spacing.get_review_schedule(
                    skill_id=sid,
                    current_mastery=info["decayed"],
                    last_review_date=info["last_ts"],
                    now=cta_input.timestamp,
                )
                # datetime → isoformat (Intervention.metadata 需可 JSON 持久化)
                review_schedule[sid] = {
                    "skill_id": sid,
                    "mastery": schedule["mastery"],
                    "peak": info["peak"],
                    "decayed": info["decayed"],
                    "next_short_review": schedule["next_short_review"].isoformat(),
                    "next_long_review": schedule["next_long_review"].isoformat(),
                }
            scaffolding_adjust = self._scaffolding_adjust_from_view(view)
        elif self._should_review_spaced(belief_state):
            bjork_triggers.append("space")

        return PlanDecision(
            bloom_target=bloom_target,
            ca_stage=ca_stage,
            clt_level=clt_level,
            bjork_triggers=bjork_triggers,
            review_schedule=review_schedule,
            scaffolding_adjust=scaffolding_adjust,
        )

    # ---------------------------------------------------------------
    # 内部工具
    # ---------------------------------------------------------------

    def _should_review_spaced(self, belief_state: BeliefState) -> bool:
        """判断是否应触发间隔复习 (迁移自 v0.81 LCAEngine._should_review_spaced).

        规则: K mastery_prob > threshold + trajectory 长度 ≥ trajectory_min_len

        v0.97.1: 仅在未提供 skill_mastery_view 时使用 (legacy 回退路径);
        提供 view 时走 _spacing_candidates_from_view (per-skill 数据驱动)。
        """
        if belief_state.K.mastery_prob > self.config.mastery_threshold:
            if len(belief_state.trajectory.snapshots) >= self.config.trajectory_min_len:
                return True
        return False

    # ---------------------------------------------------------------
    # v0.97.1: skill_mastery_view 数据驱动接线 (bjork_spacing / ca_scaffolding)
    # ---------------------------------------------------------------

    # spacing 触发阈值 (承接 CogMirror P3 先验, v0.98 试点数据回来后校准)
    SPACING_PEAK_MIN = 0.7        # 曾掌握到位才谈遗忘
    SPACING_DECAYED_MAX = 0.55    # 衰减后低于此值 → 需要复习
    SPACING_DROP_MIN = 0.15       # 或掉幅足够大 → 需要复习

    def _spacing_candidates_from_view(
        self, view: Dict[str, Dict[str, Any]]
    ) -> List[str]:
        """从 skill_mastery_view 筛选需间隔复习的 skill.

        规则: peak ≥ SPACING_PEAK_MIN 且 (decayed < SPACING_DECAYED_MAX
        或 peak - decayed ≥ SPACING_DROP_MIN)。从未答过的 skill 不在 view,
        天然不触发; 无时间证据的条目 decayed==peak, 掉幅为 0, 不误触发。

        Returns:
            skill_id 列表 (view 迭代序, 稳定)
        """
        return [
            sid
            for sid, info in view.items()
            if info["peak"] >= self.SPACING_PEAK_MIN
            and (
                info["decayed"] < self.SPACING_DECAYED_MAX
                or info["peak"] - info["decayed"] >= self.SPACING_DROP_MIN
            )
        ]

    # scaffolding 有界增量范围 (fade 是调制不是接管, CLT 主导不变)
    SCAFFOLDING_ADJUST_LIMIT = 0.2
    # fade/restore 的名义基准 (update_scaffolding_level 需要一个 current_level,
    # 取 0.5 中性值, 差值即增量; 真实基准由 designer 的 CLT 映射提供)
    _SCAFFOLDING_NOMINAL_BASE = 0.5

    def _scaffolding_adjust_from_view(
        self, view: Dict[str, Dict[str, Any]]
    ) -> Optional[float]:
        """从 skill_mastery_view 的 streaks 算 scaffolding 有界增量.

        规则: 跨 skill 取 max(streak_fail) 与 max(streak_success),
        失败优先 (frustration 保护 > 撤走支持) —— 任一 skill 达
        restore_threshold 即 restore, 不与 fade 叠加。增量 = (调整后值 -
        名义基准 0.5), clamp ±SCAFFOLDING_ADJUST_LIMIT。

        Returns:
            [-0.2, +0.2] 增量; streaks 未达任何阈值 → None (不调整)
        """
        if not view:
            return None
        max_fail = max(info["streak_fail"] for info in view.values())
        max_succ = max(info["streak_success"] for info in view.values())

        ca = self.config.ca_config
        base = self._SCAFFOLDING_NOMINAL_BASE
        if max_fail >= ca.restore_threshold:
            new_level = self.ca_scaffolding.update_scaffolding_level(
                base, consecutive_successes=0, consecutive_failures=max_fail,
            )
        elif max_succ >= ca.fade_threshold:
            new_level = self.ca_scaffolding.update_scaffolding_level(
                base, consecutive_successes=max_succ, consecutive_failures=0,
            )
        else:
            return None

        adjust = new_level - base
        return max(
            -self.SCAFFOLDING_ADJUST_LIMIT,
            min(self.SCAFFOLDING_ADJUST_LIMIT, adjust),
        )


__all__ = ["Planner", "PlannerConfig", "PlanDecision"]
