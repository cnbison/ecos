"""抗幻觉机制 1：CTA 信念分布检查（spec §4.1）.

确保信念是**分布**而非**事实**——CTA 不下"已掌握"或"未掌握"的硬结论，
而是维护 (theta_mean, theta_cov) + confidence + evidence_ids。

Phase 4 MVP 检查项：
  1. 每个维度都有 confidence 字段（schema 合规）
  2. 低 confidence（< 0.6）必须有足够 evidence_ids（≥ 3）支撑
  3. 任何维度 confidence ≥ 0.99 视为过度自信（不健康）
"""

from __future__ import annotations

from typing import List, Tuple

from ...cta.belief_state import BeliefState


class BeliefDistributionCheck:
    """信念分布合理性检查器."""

    LOW_CONFIDENCE_THRESHOLD = 0.6
    OVERCONFIDENT_THRESHOLD = 0.99
    MIN_EVIDENCE_FOR_LOW_CONF = 3
    DIMENSIONS = ("K", "P", "S", "C", "X")

    @classmethod
    def is_well_formed(cls, belief_state: BeliefState) -> Tuple[bool, List[str]]:
        """检查 BeliefState 是否健康.

        Returns:
            (is_ok, issues)：
              - is_ok: True 表示全部通过；False 表示至少一项不合规
              - issues: 不合规项描述列表（空列表 = 通过）
        """
        issues: List[str] = []

        # 检查 1：5D schema 合规
        for dim_name in cls.DIMENSIONS:
            dim = getattr(belief_state, dim_name, None)
            if dim is None:
                issues.append(f"{dim_name} 维度缺失")
                continue
            if not hasattr(dim, "confidence"):
                issues.append(f"{dim_name} 缺少 confidence 字段")
            if not hasattr(dim, "evidence_ids"):
                issues.append(f"{dim_name} 缺少 evidence_ids 字段")

        # 检查 2：低 confidence 必须有足够 evidence
        for dim_name in cls.DIMENSIONS:
            dim = getattr(belief_state, dim_name, None)
            if dim is None:
                continue
            if (
                hasattr(dim, "confidence")
                and dim.confidence < cls.LOW_CONFIDENCE_THRESHOLD
            ):
                evidence_count = len(getattr(dim, "evidence_ids", []))
                if evidence_count < cls.MIN_EVIDENCE_FOR_LOW_CONF:
                    issues.append(
                        f"{dim_name} 维度置信度 {dim.confidence:.2f} 偏低，"
                        f"但 evidence_ids 仅 {evidence_count} 个（< {cls.MIN_EVIDENCE_FOR_LOW_CONF}）"
                    )

        # 检查 3：避免过度自信
        for dim_name in cls.DIMENSIONS:
            dim = getattr(belief_state, dim_name, None)
            if dim is None:
                continue
            if (
                hasattr(dim, "confidence")
                and dim.confidence >= cls.OVERCONFIDENT_THRESHOLD
            ):
                issues.append(
                    f"{dim_name} 维度过度自信 (confidence={dim.confidence:.2f})——"
                    f"应当保留不确定性"
                )

        return len(issues) == 0, issues


__all__ = ["BeliefDistributionCheck"]