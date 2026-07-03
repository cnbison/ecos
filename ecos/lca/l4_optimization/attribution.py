"""L4 因果归因——与 CTA L4 协作.

对应：
  - research/10-engineering/02-lca-policy-engine.md §4.4 LCAAttribution
  - research/10-engineering/01-cta-belief-engine.md §7 L4 因果归因层

Phase 4 MVP 简化：
  - 因果归因的真实 ATE 计算由 CTA L4 完成
  - LCA 端只负责把干预记录推给 CTA（提供 recording API）
  - 实际 attribute_effect 调用 CTA 端 ABTestAttributor
  - M2 W2 实现接口骨架 + Mock 后端（避免硬依赖）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ...cta.belief_state import BeliefState
from ..intervention import Intervention


@dataclass
class CausalEffect:
    """因果效应估计结果."""

    intervention_type: str
    student_id: str
    state_delta: float          # 观测到的状态变化
    estimated_ate: float        # 估计 ATE
    confidence: float           # 置信度 [0, 1]
    is_control: bool = False    # 是否为对照组
    n_samples: int = 1          # 用于估计的样本数


class CTA_L4_Backend:
    """CTA L4 后端的占位接口（M2 W2 由 LCA 直接使用 BeliefEngine 推断 ATE）.

    实际实现将在 M2 W4 互校模块完成后接入 ABTestAttributor。
    """

    def __init__(self):
        # student_id → list of (intervention_type, state_delta)
        self._records: Dict[str, List[tuple]] = {}

    def record_intervention(self, intervention: Intervention, student_id: str) -> None:
        """记录干预（推到 CTA L4，CTA 端做 ATE 计算）."""
        self._records.setdefault(student_id, []).append(
            (intervention.intervention_type.value, None)
        )

    def record_outcome(
        self,
        intervention: Intervention,
        student_id: str,
        state_delta: float,
    ) -> None:
        """记录干预结果（state_delta = new_theta - old_theta）. """
        records = self._records.setdefault(student_id, [])
        # 找到对应记录并填充 state_delta（pop 直到找到匹配项）
        for i, (itype, sd) in enumerate(records):
            if sd is None and itype == intervention.intervention_type.value:
                records[i] = (itype, state_delta)
                return
        # 未找到匹配项时追加
        records.append((intervention.intervention_type.value, state_delta))

    def attribute(
        self,
        intervention_type: str,
        student_id: str,
        state_delta: float,
        is_control: bool = False,
    ) -> CausalEffect:
        """估计 ATE（简化版：单样本均值 + 置信度衰减）.

        实际版本将由 ABTestAttributor 实现 OLS / IPW / Doubly Robust。
        M2 W2 占位实现：直接返回 state_delta 作为 ATE 估计（无偏但粗糙）。
        """
        records = self._records.get(student_id, [])
        outcomes = [sd for _, sd in records if sd is not None]
        n = len(outcomes)
        # ATE 估计（MVP 简化：最近 N 次平均）
        if n == 0:
            estimated_ate = state_delta
        else:
            recent = outcomes[-10:]  # 最近 10 次
            estimated_ate = sum(recent) / len(recent)
        # 置信度随样本量增加
        confidence = min(1.0, n / 30.0)
        return CausalEffect(
            intervention_type=intervention_type,
            student_id=student_id,
            state_delta=state_delta,
            estimated_ate=estimated_ate,
            confidence=confidence,
            is_control=is_control,
            n_samples=n,
        )


class LCAAttribution:
    """LCA 端因果归因适配器.

    用法：
        attribution = LCAAttribution(CTA_L4_Backend())
        attribution.record_intervention(intervention, "student_001")
        # 学生响应后：
        effect = attribution.attribute_effect(intervention, "student_001", state_delta=0.3)
    """

    def __init__(self, backend: Optional[CTA_L4_Backend] = None):
        self.backend = backend or CTA_L4_Backend()

    def record_intervention(self, intervention: Intervention, student_id: str) -> None:
        self.backend.record_intervention(intervention, student_id)

    def attribute_effect(
        self,
        intervention: Intervention,
        student_id: str,
        state_delta: float,
        is_control: bool = False,
    ) -> CausalEffect:
        # 先把 outcome 推给 backend
        self.backend.record_outcome(intervention, student_id, state_delta)
        return self.backend.attribute(
            intervention_type=intervention.intervention_type.value,
            student_id=student_id,
            state_delta=state_delta,
            is_control=is_control,
        )


__all__ = ["LCAAttribution", "CausalEffect", "CTA_L4_Backend"]
