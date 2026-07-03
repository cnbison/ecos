"""降级到单 Agent（spec §5.3）.

当双 Agent 互校不可行时（超时 / 异常 / 错误次数过多），降级为直接 CTA → LCA，
不经过互校循环，标记 `degraded_mode=True` 便于人工审核。
"""

from __future__ import annotations

import time
from typing import Optional

from ...cta.belief_engine import BeliefEngine
from ...cta.belief_state import BeliefState
from ...lca.orchestrator import LCAEngine, LCAResult, CTAInput
from ..protocol.messages import CalibratedLCAResult, CTAOutput


class SingleAgentFallback:
    """降级模式——单 Agent 直通，不经过互校.

    用法：
        fallback = SingleAgentFallback(cta_engine, lca_engine)
        result = fallback.run_degraded(state, student_id, ...)
    """

    ERROR_THRESHOLD = 3
    TIME_THRESHOLD_SEC = 60.0

    def __init__(self, cta_engine: BeliefEngine, lca_engine: LCAEngine):
        self.cta = cta_engine
        self.lca = lca_engine

    def run_degraded(
        self,
        state: BeliefState,
        observation,
        previous_lca_result: Optional[CalibratedLCAResult] = None,
        fallback_reason: str = "互校循环超时或失败",
    ) -> CalibratedLCAResult:
        """降级模式主入口.

        Args:
            state: 当前学生 BeliefState
            observation: 本次 Observation
            previous_lca_result: 上一轮 CalibratedLCAResult（用于因果归因）
            fallback_reason: 降级原因

        Returns:
            CalibratedLCAResult（degraded_mode=True）
        """
        student_id = state.student_id

        # Step 1: CTA 直接更新
        # M2 W4 简化：CTA 端占位 LCAResult 用 None 走非 L4 路径
        new_state = self.cta.update(state, observation, lca_result=None)

        # Step 2: 构造 CTAOutput + LCA 选择
        cta_output = CTAOutput.from_belief_state(new_state)
        cta_input = CTAInput(student_id=student_id, belief_state=new_state)
        lca_result: LCAResult = self.lca.select_intervention(cta_input)

        # Step 3: 包装为 CalibratedLCAResult + 标记降级
        calibrated = CalibratedLCAResult.from_lca_result(lca_result)
        calibrated.degraded_mode = True
        calibrated.metadata["fallback_reason"] = fallback_reason
        calibrated.metadata["degraded_at"] = time.time()
        return calibrated

    def should_fallback(
        self,
        error_count: int,
        time_elapsed_sec: float,
    ) -> bool:
        """判断是否应降级.

        Args:
            error_count: 连续错误次数
            time_elapsed_sec: 单次互校耗时

        Returns:
            True = 应降级
        """
        if error_count >= self.ERROR_THRESHOLD:
            return True
        if time_elapsed_sec > self.TIME_THRESHOLD_SEC:
            return True
        return False


__all__ = ["SingleAgentFallback"]