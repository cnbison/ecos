"""Domain 抽象层 —— v0.88.0-a (Phase 7+ 抽象推演 #1).

对应 12-kernel-mapping §3 Multi-Domain 抽象:
    - Domain-agnostic Kernel 1 套 (LinUCB / Thompson / POMDP / Evidence / Runtime)
    - Domain-specific Extension N 套 (Education / Science / Career)

3 个内置 Domain:
    - EducationDomain: K12 学科教育 (默认)
    - ScienceDomain:   科研方法
    - CareerDomain:    职业技能

设计原则:
    - Domain 是 Kernel-agnostic (不持有 LinUCB state / 等)
    - Capability 是 Domain 入口 (capability_ontology 暴露 Domain 能力)
    - Domain-specific 扩展通过 profile_extensions 注入 BeliefState (v0.88.0-b)
    - DomainRegistry singleton (per 12-kernel-mapping §3 Domain-agnostic Kernel 模式)

向后兼容:
    - 复用 v0.86.0-d DEFAULT_CAPABILITIES_LIST (Capability frozen dataclass)
    - 不修改 Goal Ontology 接口
    - 不修改 BeliefState schema (v0.88.0-b 才加 domain_extension 字段)
    - 防御性自检 [8] 仍 hard block (Domain 不 mutate state)
"""

from __future__ import annotations

import logging

from .base import Domain, DomainRegistry, get_default_registry
from .career import CareerDomain
from .education import EducationDomain
from .science import ScienceDomain

_log = logging.getLogger(__name__)


def register_default_domains(registry: DomainRegistry | None = None) -> int:
    """注册 3 个默认 Domain (Education / Science / Career) 到 registry.

    Args:
        registry: 目标 registry (None = 默认 singleton)

    Returns:
        注册数量 (默认 3)

    防御性: 重复注册同名 domain 走覆盖式, 不 raise
    """
    if registry is None:
        registry = get_default_registry()
    registry.register(EducationDomain())
    registry.register(ScienceDomain())
    registry.register(CareerDomain())
    _log.info(
        "register_default_domains: 注册 3 个默认 Domain (education / science / career)"
    )
    return 3


__all__ = [
    "Domain",
    "DomainRegistry",
    "get_default_registry",
    "EducationDomain",
    "ScienceDomain",
    "CareerDomain",
    "register_default_domains",
]