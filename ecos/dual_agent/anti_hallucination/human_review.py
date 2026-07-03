"""抗幻觉机制 4：人工审核触发（spec §4.4）.

触发条件：
  1. 整体置信度 < 阈值（默认 0.6）
  2. 信念分布合理性检查失败
  3. 连续 N 次干预无效

Phase 4 MVP：
  - 触发器实现
  - 暂不实现 review queue（Phase 5+ 接入持久化 + 教师后台接口）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from ..protocol.messages import CTAOutput, HumanReviewRequest
from .belief_check import BeliefDistributionCheck


@dataclass
class HumanReviewConfig:
    """人工审核配置."""

    confidence_threshold: float = 0.6
    consecutive_ineffective_threshold: int = 3
    enabled: bool = True


class HumanReviewTrigger:
    """人工审核触发器.

    用法：
        trigger = HumanReviewTrigger(HumanReviewConfig())
        should, req = trigger.should_request_human_review(cta_output, consecutive_ineffective=4)
        if should:
            queue_review(req)
    """

    def __init__(self, config: Optional[HumanReviewConfig] = None):
        self.config = config or HumanReviewConfig()
        self._review_queue: List[HumanReviewRequest] = []

    def should_request_human_review(
        self,
        cta_output: CTAOutput,
        consecutive_ineffective: int = 0,
    ) -> Tuple[bool, Optional[HumanReviewRequest]]:
        """判断是否应请求人工审核.

        Args:
            cta_output: 互校层 CTA 输出
            consecutive_ineffective: 最近连续无效干预次数

        Returns:
            (should_review, request)：
              - should_review: True 表示需触发
              - request: HumanReviewRequest 对象（None 表示未触发）
        """
        if not self.config.enabled:
            return False, None

        # 条件 1：整体置信度过低
        if cta_output.overall_confidence < self.config.confidence_threshold:
            return True, HumanReviewRequest(
                student_id=cta_output.student_id,
                reason=f"CTA 整体置信度 {cta_output.overall_confidence:.2f} < 阈值 {self.config.confidence_threshold}",
                priority="high",
                belief_state_snapshot=cta_output.belief_state,
                calibration_round=cta_output.calibration_round,
            )

        # 条件 2：信念分布不合理
        is_well, issues = BeliefDistributionCheck.is_well_formed(cta_output.belief_state)
        if not is_well:
            return True, HumanReviewRequest(
                student_id=cta_output.student_id,
                reason=f"信念分布不合理: {'; '.join(issues[:3])}",
                priority="critical",
                belief_state_snapshot=cta_output.belief_state,
                calibration_round=cta_output.calibration_round,
            )

        # 条件 3：连续 N 次干预无效
        if consecutive_ineffective >= self.config.consecutive_ineffective_threshold:
            return True, HumanReviewRequest(
                student_id=cta_output.student_id,
                reason=f"连续 {consecutive_ineffective} 次干预无显著效果",
                priority="high",
                belief_state_snapshot=cta_output.belief_state,
                calibration_round=cta_output.calibration_round,
            )

        return False, None

    def queue_review(self, request: HumanReviewRequest) -> None:
        """将请求入队（Phase 5+ 接入持久化层）."""
        self._review_queue.append(request)

    def get_pending_reviews(self) -> List[HumanReviewRequest]:
        """获取待审核请求（Phase 5+ 教师后台接口使用）."""
        return list(self._review_queue)

    def clear(self) -> None:
        """清空队列（测试用）."""
        self._review_queue.clear()


__all__ = ["HumanReviewTrigger", "HumanReviewConfig"]