"""L4 Cognitive Apprenticeship 6 阶段状态机.

对应：
  - research/10-engineering/02-lca-policy-engine.md §4.1 CAStateMachine
  - research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md §3.2

阶段转移规则（M2 W2 MVP 实现 Stage 1-3）：
  MODELING → COACHING    学生开始尝试（has_tried_independently）
  COACHING → SCAFFOLDING 学生需要支持（needs_scaffolding）
  COACHING ↔ SCAFFOLDING 支持减少时回退到 Coaching
  ARTICULATION/REFLECTION/EXPLORATION：Phase 5+（保留骨架 + 简单转移）

LCA 在后台判断当前阶段（不暴露给 UI）。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from ...cta.belief_state import BeliefState
from ..intervention import CAStage, Intervention


class CAStateMachine:
    """Cognitive Apprenticeship 6 阶段状态机.

    用法：
        sm = CAStateMachine()
        stage = sm.current_stage("student_001")  # 默认 MODELING
        new_stage = sm.transition("student_001", belief_state, history)
    """

    def __init__(self):
        self.state: Dict[str, CAStage] = {}  # student_id → CAStage

    def current_stage(self, student_id: str) -> CAStage:
        """获取学生当前 CA 阶段（默认 MODELING）."""
        return self.state.get(student_id, CAStage.MODELING)

    def transition(
        self,
        student_id: str,
        belief_state: BeliefState,
        intervention_history: Optional[List[Intervention]] = None,
    ) -> CAStage:
        """根据状态转移 CA 阶段.

        Args:
            student_id: 学生 ID
            belief_state: CTA 输出
            intervention_history: 历史干预列表（M2 W2 可选）

        Returns:
            转移后的 CAStage
        """
        current = self.current_stage(student_id)
        history = intervention_history or []

        if current == CAStage.MODELING:
            # Modeling → Coaching：学生开始尝试
            if self._has_tried_independently(belief_state, history):
                self.state[student_id] = CAStage.COACHING
                return CAStage.COACHING

        elif current == CAStage.COACHING:
            # Coaching → Scaffolding：需要支持
            if self._needs_scaffolding(belief_state):
                self.state[student_id] = CAStage.SCAFFOLDING
                return CAStage.SCAFFOLDING
            # Coaching → Articulation：学生讲出思路（M2 W2 占位，Phase 5+）
            if self._can_articulate(history):
                # M2 W2 不实现 ARTICULATION（Phase 5+），保留占位
                pass

        elif current == CAStage.SCAFFOLDING:
            # Scaffolding → Coaching：支持减少（mastery 上升）
            if self._scaffolding_reduced(belief_state):
                self.state[student_id] = CAStage.COACHING
                return CAStage.COACHING

        # Phase 5+ 占位（不动状态）
        # ARTICULATION → REFLECTION → EXPLORATION 留给 Phase 5+
        return current

    # ---------------------------------------------------------------
    # 内部转移条件
    # ---------------------------------------------------------------

    @staticmethod
    def _has_tried_independently(
        belief_state: BeliefState,
        history: Optional[List[Intervention]] = None,
    ) -> bool:
        """判断学生是否已尝试独立做题（→ Coaching）.

        规则（独立检查，分别触发）：
          (a) trajectory 快照数 ≥ 3（学生已有独立尝试痕迹）
          (b) 历史干预中至少 1 条 PRACTICE 类型干预
        任一满足 → COACHING。
        """
        # 条件 (a)：trajectory 充足
        if len(belief_state.trajectory.snapshots) >= 3:
            return True
        # 条件 (b)：历史干预中有 PRACTICE
        if history:
            return any(it.intervention_type.value == "practice" for it in history)
        return False

    @staticmethod
    def _needs_scaffolding(belief_state: BeliefState) -> bool:
        """判断学生是否需要支持（→ Scaffolding）."""
        # 规则：K 维度 mastery_prob < 0.4 或 C 维度 confidence 低
        if belief_state.K.mastery_prob < 0.4:
            return True
        # TC 容器：Phase 5+ 接入。当前用 C 维度 confidence 作隐含信号
        if belief_state.C.confidence < 0.4:
            return True
        return False

    @staticmethod
    def _can_articulate(history: List[Intervention]) -> bool:
        """判断学生是否讲出思路（→ Articulation，Phase 5+）.

        M2 W2 占位：永远返回 False，让状态停留在 Coaching。
        """
        return False

    @staticmethod
    def _scaffolding_reduced(belief_state: BeliefState) -> bool:
        """判断支持是否可减少（Scaffolding → Coaching）."""
        # K mastery 提升到 0.6 以上 + C confidence 充足
        if belief_state.K.mastery_prob > 0.6 and belief_state.C.confidence > 0.5:
            return True
        return False


__all__ = ["CAStateMachine"]
