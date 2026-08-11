"""Domain abstract base class —— v0.88.0-a.

对应 12-kernel-mapping §3 Multi-Domain 抽象 (Phase 7+ 抽象推演 #1):
    - Domain-agnostic Kernel 1 套 (LinUCB / Thompson / POMDP / Evidence / Runtime)
    - Domain-specific Extension N 套 (Education / Science / Career)

v0.88.0-a 设计:
    - Domain ABC: name / description / capability_ontology / profile_extensions
    - 4 个 abstract property (强制子类实现)
    - DomainRegistry singleton (per 12-kernel-mapping §3 Domain-agnostic Kernel 模式)
    - Capability 是 Domain 入口 (capability_ontology 暴露 Domain 能力)
    - Domain 不 mutate state (defensive check [8] 仍 hard block)

向后兼容:
    - 不引用 BeliefState, 不修改 Goal Ontology 接口
    - Kernel (LinUCB / Thompson / POMDP / Evidence / Runtime) 完全 Domain-agnostic
    - v0.88.0-b 在 BeliefState 加 domain_extension 字段, 走 DomainExtension 渐进迁移
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

_log = logging.getLogger(__name__)


class Domain(ABC):
    """Domain abstract base class (v0.88.0-a).

    4 个 abstract property:
        - name:                Domain 标识 (e.g. 'education' / 'science' / 'career')
        - description:         Domain 描述
        - capability_ontology: Dict[capability_name -> Capability] (Domain 能力字典)
        - profile_extensions:  Dict[extension_name -> Any] (Domain-specific 扩展)

    设计原则:
        - Domain 是 Kernel-agnostic: 不持有 LinUCB / Thompson / POMDP state
        - Domain 入口是 capability_ontology (通过 Capability 暴露 Domain 能力)
        - Domain-specific 扩展通过 profile_extensions 注入 BeliefState
        - Domain 不 mutate state (defensive check [8] 仍 hard block)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Domain 标识 (e.g. 'education' / 'science' / 'career')."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Domain 描述."""
        pass

    @property
    @abstractmethod
    def capability_ontology(self) -> Dict[str, Any]:
        """Domain 能力字典 (capability_name -> Capability).

        Returns:
            Dict[str, Capability] (e.g. {"python_variables": Capability(...)})
        """
        pass

    @property
    @abstractmethod
    def profile_extensions(self) -> Dict[str, Any]:
        """Domain-specific profile 扩展.

        Returns:
            Dict[str, Any] (e.g. {"research_methods": [...]} for science)
                          (e.g. {"vocational_tracks": [...]} for career)
        """
        pass

    def get_capability(self, name: str) -> Optional[Any]:
        """通过 capability name 反查 Capability (None = 不存在).

        Args:
            name: capability name (e.g. "python_variables")

        Returns:
            Capability 实例 或 None

        防御性自检 [1]: name 不存在返 None, 不 raise
        """
        try:
            return self.capability_ontology.get(name)
        except Exception:
            _log.warning(
                "Domain.get_capability: capability=%s 查找失败, 返 None",
                name, exc_info=True,
            )
            return None

    def has_capability(self, name: str) -> bool:
        """判定 capability 是否存在 Domain 中.

        Args:
            name: capability name

        Returns:
            bool
        """
        return name in self.capability_ontology

    def list_capabilities(self) -> List[str]:
        """返回所有 capability name 列表 (用于调试 + 文档生成)."""
        return list(self.capability_ontology.keys())

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 dict (持久化 + logging 用).

        Returns:
            dict 含:
                - name (str)
                - description (str)
                - capability_ontology (Dict[str, Capability.to_dict()])
                - profile_extensions (Dict[str, Any])
        """
        return {
            "name": self.name,
            "description": self.description,
            "capability_ontology": {
                k: v.to_dict() if hasattr(v, "to_dict") else v
                for k, v in self.capability_ontology.items()
            },
            "profile_extensions": dict(self.profile_extensions),
        }


class DomainRegistry:
    """Domain registry singleton (v0.88.0-a).

    负责管理多个 Domain 实例, 提供 register / get / list 入口.

    设计:
        - 模块级 singleton (单进程 1 份)
        - register: 注册 Domain 实例 (按 name)
        - get: 按 name 反查 Domain
        - list_names: 列出所有已注册 Domain name

    向后兼容:
        - 默认 registry 在 import 时自动构造
        - 提供 reset() 用于测试隔离
        - register idempotent (同名覆盖)
    """

    _instance: Optional["DomainRegistry"] = None

    def __new__(cls) -> "DomainRegistry":
        """Singleton pattern (per 12-kernel-mapping §3 Domain-agnostic Kernel 模式)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._domains = {}
        return cls._instance

    def register(self, domain: Domain) -> None:
        """注册 Domain 实例 (按 name 索引).

        Args:
            domain: Domain 实例

        防御性自检 [1]: 重复 name _log.warning + 覆盖 (idempotent)
        """
        if not isinstance(domain, Domain):
            _log.warning(
                "DomainRegistry.register: 非 Domain 实例 (type=%s), skip",
                type(domain).__name__,
            )
            return
        name = domain.name
        if name in self._domains:
            _log.warning(
                "DomainRegistry.register: 覆盖已注册 domain=%s",
                name,
            )
        self._domains[name] = domain

    def get(self, name: str) -> Optional[Domain]:
        """按 name 反查 Domain 实例.

        Args:
            name: Domain 标识 (e.g. "education")

        Returns:
            Domain 实例 或 None

        防御性自检 [1]: name 不存在返 None, 不 raise
        """
        return self._domains.get(name)

    def list_names(self) -> List[str]:
        """列出所有已注册 Domain name.

        Returns:
            List[str] (按注册顺序)
        """
        return list(self._domains.keys())

    def has(self, name: str) -> bool:
        """判定 Domain 是否已注册.

        Args:
            name: Domain 标识

        Returns:
            bool
        """
        return name in self._domains

    def clear(self) -> None:
        """清空 registry (测试隔离用, 不推荐 production 使用)."""
        self._domains.clear()

    def reset(self) -> None:
        """重置 singleton (测试隔离用)."""
        self._domains.clear()


def get_default_registry() -> DomainRegistry:
    """获取默认 DomainRegistry singleton (懒加载)."""
    return DomainRegistry()


__all__ = [
    "Domain",
    "DomainRegistry",
    "get_default_registry",
]