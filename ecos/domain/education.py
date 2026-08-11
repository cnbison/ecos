"""Education Domain —— K12 学科教育 (v0.88.0-a).

对应 12-kernel-mapping §3 Multi-Domain 抽象:
    - 第一类 Domain (默认 / K12 教育)
    - 5 Python 默认 capability (跟 v0.86.0-d DEFAULT_CAPABILITIES_LIST 复用)
    - K12 + Bloom + TC 教学法

设计:
    - EducationDomain(name="education", description="K12 学科教育")
    - capability_ontology: 5 Python capability (variables/loops/functions/conditionals/strings)
    - profile_extensions:
        - grade_levels: [K-12 阶段]
        - learning_standards: [教学标准 (CCSS / 课标)]

向后兼容:
    - 复用 v0.86.0-d DEFAULT_CAPABILITIES_LIST (Capability frozen dataclass)
    - 不修改 Goal Ontology 接口
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List

from ..goal import DEFAULT_CAPABILITIES_LIST, Capability
from .base import Domain

_log = logging.getLogger(__name__)


@dataclass
class EducationDomain(Domain):
    """教育 Domain (v0.88.0-a, K12 默认).

    5 Python 默认 capability (跟 v0.86.0-d DEFAULT_CAPABILITIES_LIST 一致):
      1. python_variables
      2. python_loops
      3. python_functions
      4. python_conditionals
      5. python_strings

    profile_extensions:
      - grade_levels: K12 阶段 (elementary / middle / high)
      - learning_standards: 教学标准 (CCSS / 课标 placeholder)
    """

    NAME: ClassVar[str] = "education"

    _description: str = field(default="K12 学科教育 (默认 Domain)", init=False)
    _capability_ontology: Dict[str, Capability] = field(
        default_factory=lambda: {c.name: c for c in DEFAULT_CAPABILITIES_LIST},
        init=False,
    )
    _profile_extensions: Dict[str, Any] = field(
        default_factory=lambda: {
            "grade_levels": ["elementary", "middle", "high"],
            "learning_standards": ["CCSS", "课标"],
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


__all__ = ["EducationDomain"]