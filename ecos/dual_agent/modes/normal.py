"""常态循环模式（spec §3.1）——新事件/新证据时执行 6 步互校.

Step 1: CTA 更新信念
Step 2: 状态机转移 → CTA_HYPOTHESIS
Step 3: LCA 设计干预
Step 4: 状态机转移 → LCA_EXPERIMENT
Step 5: 等待 observation
Step 6: 状态机转移 → OBSERVATION_PENDING
Step 7: 包装为 CalibratedLCAResult 返回给 App 层
"""

from __future__ import annotations

from typing import Optional

from ...cta.belief_engine import BeliefEngine
from ...cta.belief_state import BeliefState
from ...lca.orchestrator import CTAInput, LCAEngine, LCAResult
from ..protocol.messages import (
    CalibratedLCAResult,
    CTAOutput,
    MessageType,
)
from ..protocol.state_machine import CalibrationState, CalibrationStateMachine


class NormalCycle:
    """常态互校循环."""

    def __init__(
        self,
        cta_engine: BeliefEngine,
        lca_engine: LCAEngine,
        state_machine: CalibrationStateMachine,
    ):
        self.cta = cta_engine
        self.lca = lca_engine
        self.state_machine = state_machine

    def run(
        self,
        state: BeliefState,
        observation,
        previous_lca_result: Optional[CalibratedLCAResult] = None,
        challenge_history: Optional[list] = None,
        intervention_hints: Optional[list] = None,
    ) -> tuple:
        """执行一轮常态互校.

        Args:
            state: 当前学生 BeliefState（由 orchestrator 持有）
            observation: 本次 Observation
            previous_lca_result: 上一轮 CalibratedLCAResult（用于因果归因）
            challenge_history: 历史质疑记录（从 CTAOutput 传入）
            intervention_hints: CTA 给 LCA 的提示

        Returns:
            (new_state, cta_output, calibrated_lca_result) 三元组
        """
        student_id = state.student_id

        # Step 1: CTA 更新信念（带上一轮 LCA 结果的因果信号）
        # M2 W4 简化：CTA 端占位 LCAResult（intervention_type + actual_outcome）
        cta_lca_placeholder = None
        if previous_lca_result is not None and previous_lca_result.actual_outcome is not None:
            from ...cta.belief_engine import LCAResult as CTALCAResult
            cta_lca_placeholder = CTALCAResult(
                intervention_type=previous_lca_result.intervention.intervention_type.value,
                expected_gain=previous_lca_result.expected_gain,
                actual_outcome=previous_lca_result.actual_outcome,
            )
        new_state: BeliefState = self.cta.update(state, observation, lca_result=cta_lca_placeholder)

        # Step 2: 状态机转移 → CTA_HYPOTHESIS
        self.state_machine.transition(student_id, MessageType.CTA_OUTPUT)
        calibration_round = self._next_round(student_id)

        # Step 3: 构造 CTAOutput
        cta_output = CTAOutput.from_belief_state(
            belief_state=new_state,
            calibration_round=calibration_round,
            challenge_history=challenge_history,
            intervention_hints=intervention_hints,
        )

        # Step 4: LCA 设计干预
        cta_input = CTAInput(
            student_id=student_id,
            belief_state=new_state,
            skill_filter=observation.skill_id and [observation.skill_id],
        )
        lca_result: LCAResult = self.lca.select_intervention(cta_input)

        # Step 5: 状态机转移 → LCA_EXPERIMENT
        self.state_machine.transition(student_id, MessageType.LCA_INTERVENTION)

        # Step 6: 包装 CalibratedLCAResult
        calibrated = CalibratedLCAResult.from_lca_result(
            lca_result,
            calibration_round=calibration_round,
        )

        # Step 7: 状态机转移 → OBSERVATION_PENDING（等待下一轮 observation）
        self.state_machine.transition(student_id, MessageType.OBSERVATION)

        return new_state, cta_output, calibrated

    @staticmethod
    def _next_round(student_id: str) -> int:
        """获取下一轮互校序号（M2 W4 占位：基于 state_machine 历史计数）."""
        # M2 W4 简化：orchestrator 维护 round 计数；这里仅返回 0 作为占位
        return 0


__all__ = ["NormalCycle"]