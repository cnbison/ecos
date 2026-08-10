"""Twin 变化归因 —— v0.83.0-c Evaluation Engine 第 1 个 evaluator.

对应 kernel-mapping §1.5: "Twin 变化归因 (基于 Event 流 + State Diff)".

设计:
  - 输入: before_state / after_state (2 个 BeliefState) + 关联 evidence_ids
  - 输出: TwinAttributionResult (含 state_diff + dominant_factor)
  - 主导因子: 按 |state_diff| 排序, 选 delta 最大的字段

v0.83.0-c 简化:
  - 仅看 5D mastery_prob + bloom_profile 6 层 + overall_confidence
  - 主导因子 = max |state_diff| 对应的字段 + delta
  - evidence_attribution 列出 after_state.evidence_summary 概览
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..cta.belief_state import BeliefState, BloomLevel

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TwinAttributionResult 数据类
# ---------------------------------------------------------------------------

@dataclass
class TwinAttributionResult:
    """Twin 变化归因结果.

    Attributes:
        student_id:            学生 ID
        since:                 起始时间 (optional, 决策辅助)
        state_diff:            Dict[str, Dict[str, float]] 字段 -> {old, new, delta}
        evidence_attribution:  List[Dict[str, Any]] evidence 关联概览
        dominant_factor:       str  (e.g. "K.mastery_prob: 0.5 -> 0.7 (+0.2)")
    """

    student_id: str
    since: Optional[datetime]
    state_diff: Dict[str, Dict[str, float]]
    evidence_attribution: List[Dict[str, Any]]
    dominant_factor: str

    def to_dict(self) -> dict:
        return {
            "student_id": self.student_id,
            "since": self.since.isoformat() if self.since else None,
            "state_diff": self.state_diff,
            "evidence_attribution": self.evidence_attribution,
            "dominant_factor": self.dominant_factor,
        }


# ---------------------------------------------------------------------------
# TwinAttribution 类
# ---------------------------------------------------------------------------

class TwinAttribution:
    """Twin 变化归因 (v0.83.0-c).

    用法:
        attributor = TwinAttribution(evidence_engine=engine)
        result = attributor.attribute("student_001", before_state, after_state, since=...)
        # -> TwinAttributionResult(
        #        state_diff={"K.mastery_prob": {"old": 0.5, "new": 0.7, "delta": 0.2}, ...},
        #        dominant_factor="K.mastery_prob: 0.5 -> 0.7 (+0.2)")

    字段覆盖 (v0.83.0-c):
      - 5D mastery_prob (K/P/S/C/X)
      - Bloom 6 层 (remember/understand/apply/analyze/evaluate/create)
      - overall_confidence
      - evidence_summary (count of evidence_ids per dim)
    """

    # 跟踪的字段路径 (跟 TwinAttributionResult.state_diff keys 对应)
    TRACKED_DIMS = ["K", "P", "S", "C", "X"]
    TRACKED_BLOOM = ["remember", "understand", "apply", "analyze", "evaluate", "create"]

    def __init__(self, evidence_engine: Optional[Any] = None):
        # evidence_engine optional (v0.83.0-b 引入), 不传则 evidence_attribution 仅用 state 概览
        self.evidence_engine = evidence_engine

    def attribute(
        self,
        student_id: str,
        before: BeliefState,
        after: BeliefState,
        since: Optional[datetime] = None,
    ) -> TwinAttributionResult:
        """计算 before -> after 的 State diff, 找出主导变化因子.

        Args:
            student_id: 学生 ID
            before:     变化前 BeliefState
            after:      变化后 BeliefState
            since:      起始时间 (optional, 标注到结果)

        Returns:
            TwinAttributionResult
        """
        state_diff: Dict[str, Dict[str, float]] = {}

        # 1) 5D mastery_prob
        for dim in self.TRACKED_DIMS:
            dim_before = float(getattr(before, dim).mastery_prob)
            dim_after = float(getattr(after, dim).mastery_prob)
            delta = dim_after - dim_before
            if abs(delta) > 1e-6:  # 只记录有变化的
                state_diff[f"{dim}.mastery_prob"] = {
                    "old": dim_before, "new": dim_after, "delta": delta,
                }

        # 2) Bloom 6 层
        for layer in self.TRACKED_BLOOM:
            bloom_before = float(getattr(before.bloom_profile, layer))
            bloom_after = float(getattr(after.bloom_profile, layer))
            delta = bloom_after - bloom_before
            if abs(delta) > 1e-6:
                state_diff[f"bloom.{layer}"] = {
                    "old": bloom_before, "new": bloom_after, "delta": delta,
                }

        # 3) overall_confidence
        overall_before = float(before.overall_confidence)
        overall_after = float(after.overall_confidence)
        delta = overall_after - overall_before
        if abs(delta) > 1e-6:
            state_diff["overall_confidence"] = {
                "old": overall_before, "new": overall_after, "delta": delta,
            }

        # 4) evidence_attribution (after_state.evidence_summary 概览)
        evidence_attribution = self._build_evidence_attribution(after, since)

        # 5) 主导因子 = max |delta| 字段
        dominant_factor = self._find_dominant_factor(state_diff)

        return TwinAttributionResult(
            student_id=student_id,
            since=since,
            state_diff=state_diff,
            evidence_attribution=evidence_attribution,
            dominant_factor=dominant_factor,
        )

    def _build_evidence_attribution(
        self,
        after: BeliefState,
        since: Optional[datetime],
    ) -> List[Dict[str, Any]]:
        """构造 evidence_attribution 列表 (含每个维度的 evidence 数量)."""
        summary = after.evidence_summary()
        result = []
        for dim, count in summary.items():
            if count > 0:
                entry = {"dim": dim, "evidence_count": count}
                # 如果 evidence_engine 注入, 进一步查 evidence 来源分布
                if self.evidence_engine is not None:
                    try:
                        evidences = self.evidence_engine.query_by_student(
                            after.student_id, since=since, limit=count * 2,
                        )
                        # 统计 source 分布
                        source_dist: Dict[str, int] = {}
                        for ev in evidences:
                            source_dist[ev.source.value] = source_dist.get(
                                ev.source.value, 0,
                            ) + 1
                        entry["source_dist"] = source_dist
                    except Exception:
                        _log.warning("evidence 来源分布查询失败, 跳过", exc_info=True)
                result.append(entry)
        return result

    @staticmethod
    def _find_dominant_factor(state_diff: Dict[str, Dict[str, float]]) -> str:
        """找 |delta| 最大的字段, 格式化为 "field: old -> new (+delta)"."""
        if not state_diff:
            return "(无变化)"

        # 按 |delta| 降序
        sorted_fields = sorted(
            state_diff.items(),
            key=lambda kv: abs(kv[1]["delta"]),
            reverse=True,
        )
        top_field, top_diff = sorted_fields[0]
        return (
            f"{top_field}: {top_diff['old']:.3f} -> {top_diff['new']:.3f} "
            f"({top_diff['delta']:+.3f})"
        )


__all__ = [
    "TwinAttribution",
    "TwinAttributionResult",
]
