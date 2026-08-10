"""LCA Input 数据结构 —— v0.82.0-b 抽出 (打破 orchestrator 循环 import).

对应:
  - research/10-engineering/02-lca-policy-engine.md §6 LCAOrchestrator
  - 旧位置: ecos.lca.orchestrator.CTAInput (v0.81.0 之前)
  - v0.82.0-b: 抽到独立文件, 让 Planner + ExperimentDesigner + LCAEngine 都能引用
    而不触发循环 import

设计:
  - 不可变字段 (student_id / belief_state / bloom_target_candidates / skill_filter)
  - timestamp 工厂方法 (每次构造自动设 now)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from ..cta.belief_state import BeliefState, BloomLevel


@dataclass
class CTAInput:
    """LCA 接收的 CTA 输出 (M2 W2 简化版).

    Attributes:
        student_id:              学生 ID
        belief_state:            CTA 估计的 BeliefState
        bloom_target_candidates: 候选 Bloom 层 (默认全 6 层)
        skill_filter:            可选——只针对特定技能列表
        timestamp:               时间戳
    """

    student_id: str
    belief_state: BeliefState
    bloom_target_candidates: Optional[List[BloomLevel]] = None
    skill_filter: Optional[List[str]] = None
    timestamp: datetime = field(default_factory=datetime.now)


__all__ = ["CTAInput"]
