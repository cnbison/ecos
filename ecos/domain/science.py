"""Science Domain —— 科研方法 (v0.88.0-a).

对应 12-kernel-mapping §3 Multi-Domain 抽象:
    - 第二类 Domain (科研)
    - 3 capability (hypothesis / experiment / analysis)
    - research_methods extension

设计:
    - ScienceDomain(name="science", description="科研方法")
    - capability_ontology: 3 capability (hypothesis/experiment/analysis)
    - profile_extensions:
        - research_methods: empirical / theoretical / computational
        - domain_categories: physics / chemistry / biology / ...

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
class ScienceDomain(Domain):
    """科研 Domain (v0.88.0-a, 科研方法).

    3 capability:
      1. hypothesis  - 假设生成
      2. experiment  - 实验设计
      3. analysis    - 数据分析

    profile_extensions:
      - research_methods: [empirical / theoretical / computational]
      - domain_categories: [physics / chemistry / biology / ...]
    """

    NAME: ClassVar[str] = "science"

    _description: str = field(default="科研方法 (hypothesis / experiment / analysis)", init=False)
    _capability_ontology: Dict[str, Capability] = field(
        default_factory=lambda: {
            "hypothesis": Capability(
                name="hypothesis",
                description="假设生成与可检验性",
                domain="science",
            ),
            "experiment": Capability(
                name="experiment",
                description="实验设计 (控制变量 / 重复性 / 因果)",
                domain="science",
            ),
            "analysis": Capability(
                name="analysis",
                description="数据分析 (统计 / 模型 / 解释)",
                domain="science",
            ),
        },
        init=False,
    )
    _profile_extensions: Dict[str, Any] = field(
        default_factory=lambda: {
            "research_methods": ["empirical", "theoretical", "computational"],
            "domain_categories": ["physics", "chemistry", "biology", "earth_science", "astronomy"],
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


__all__ = ["ScienceDomain"]