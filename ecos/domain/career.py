"""Career Domain —— 职业技能 (v0.88.0-a).

对应 12-kernel-mapping §3 Multi-Domain 抽象:
    - 第三类 Domain (职业)
    - 3 capability (skill / portfolio / certification)
    - vocational_tracks extension

设计:
    - CareerDomain(name="career", description="职业技能")
    - capability_ontology: 3 capability (skill/portfolio/certification)
    - profile_extensions:
        - vocational_tracks: engineering / design / research / management
        - certification_levels: entry / mid / senior / expert

向后兼容:
    - Capability 使用 frozen dataclass (跟 v0.86.0-a 一致)
    - 不修改 Goal Ontology 接口
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict

from ..goal import Capability
from .base import Domain

_log = logging.getLogger(__name__)


@dataclass
class CareerDomain(Domain):
    """职业 Domain (v0.88.0-a, 职业技能).

    3 capability:
      1. skill         - 专业技能
      2. portfolio     - 作品集
      3. certification - 职业认证

    profile_extensions:
      - vocational_tracks: [engineering / design / research / management]
      - certification_levels: [entry / mid / senior / expert]
    """

    NAME: ClassVar[str] = "career"

    _description: str = field(default="职业技能 (skill / portfolio / certification)", init=False)
    _capability_ontology: Dict[str, Capability] = field(
        default_factory=lambda: {
            "skill": Capability(
                name="skill",
                description="专业技能 (硬技能 / 软技能)",
                domain="career",
            ),
            "portfolio": Capability(
                name="portfolio",
                description="作品集 (项目 / 案例 / 成就)",
                domain="career",
            ),
            "certification": Capability(
                name="certification",
                description="职业认证 (学历 / 行业认证 / 执业资格)",
                domain="career",
            ),
        },
        init=False,
    )
    _profile_extensions: Dict[str, Any] = field(
        default_factory=lambda: {
            "vocational_tracks": ["engineering", "design", "research", "management", "communication"],
            "certification_levels": ["entry", "mid", "senior", "expert"],
        },
        init=False,
    )

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def description(self) -> str:
        return self._description

    @property
    def capability_ontology(self) -> Dict[str, Capability]:
        return dict(self._capability_ontology)

    @property
    def profile_extensions(self) -> Dict[str, Any]:
        return dict(self._profile_extensions)


__all__ = ["CareerDomain"]