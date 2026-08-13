"""ECOS Plugin SDK base class —— v0.94.0-a.

对应 12-kernel-mapping §6 Plugin SDK (Phase 7+ 抽象推演 #7):
    - 第一方 plugin 库 (Kernel-only SDK) — 给 Plugin 开发者 SDK-level 基类
    - Plugin 不调用 Twin, Plugin 只能产生 Event + 读 Kernel state (跟 v0.85.0 原则一致)
    - Plugin ABC + PluginMetadata frozen dataclass (跟 Domain ABC v0.88.0-a + Capability v0.86.0-a 完全 parallel pattern)

v0.94.0-a 设计:
    - Plugin(ABC): 4 abstract method (on_event / get_subscribed_topics / enable / disable)
    - PluginMetadata(frozen=True): name / version / description / dependencies / subscribed_topics / schema_version
    - __post_init__ 防御性校验: name lowercase alphanumeric+underscore / version semver / subscribed_topics 合法 / 不能依赖自己
    - Plugin 是 process_event pattern, 不 mutate Kernel state (defensive check [8] 仍 hard block)

向后兼容:
    - 不引用 BeliefState, 不修改 LearningEvent / EventBus / PluginRuntime 接口
    - 现有 PluginRuntime 8 subscriber (v0.93.0-b) 维持 — Plugin ABC 是 SDK 开发者面, 不是替换 PluginRuntime
    - v0.94.0-b PluginRegistry 在 base.py 之上注册管理
    - v0.94.0-c first-party plugin 继承 Plugin ABC

Plugin lifecycle (跟 DomainRegistry / LCAEngine dump/load 模式一致):
    instantiate → register → enable → on_event (多次) → disable → unregister
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, Set, Tuple

from ecos.cta.event_log import LearningEvent, LearningEventType

_log = logging.getLogger(__name__)

# Schema version (跟 POMDPPolicy 0.93.0 / CognitiveTwinAgent 0.92.0 隔离)
SCHEMA_VERSION = "0.94.0"

# Plugin-internal topics (不在 LearningEventType enum 内的 topic 字符串, 用于 PluginRuntime subscriber 内部 routing)
# 跟 v0.93.0-b PluginRuntime._handle_pomdp_diagnostic_updated 一致 (line 372-404 用 bus.publish("pomdp_diagnostic_updated", ...)
# 不走 LearningEvent factory, 是 PluginRuntime 内部 topic)
_PLUGIN_INTERNAL_TOPICS: Tuple[str, ...] = ("pomdp_diagnostic_updated",)

# name 合法性校验: lowercase alphanumeric + underscore (跟 Domain.name / Capability.name 一致风格)
_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

# semver: MAJOR.MINOR.PATCH (3 段全数字)
_SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def _get_valid_topics() -> Set[str]:
    """返 union(LearningEventType values, Plugin-internal topics) 用于 __post_init__ 校验.

    跟 Domain / POMDPPolicy / CognitiveTwinAgent 的 frozen dataclass 校验一致.
    """
    return {e.value for e in LearningEventType} | set(_PLUGIN_INTERNAL_TOPICS)


@dataclass(frozen=True)
class PluginMetadata:
    """Plugin metadata (v0.94.0-a).

    Frozen dataclass 跟 v0.91 HumanFeedbackEntry / v0.92 ActionEntry / v0.93 POMDPDiagnostic 同模式.
    Plugin 创建后 metadata 不可变, 防止外部 mutation 干扰 registry / persistence.

    字段:
        - name: str                       — 唯一 plugin 标识 (lowercase alphanumeric+underscore, e.g. "hint_fatigue")
        - version: str                    — semver (e.g. "1.0.0")
        - description: str = ""           — plugin 描述
        - dependencies: Tuple[str, ...]   — 软依赖的其他 plugin name (空 = 无依赖)
        - subscribed_topics: Tuple[str, ...] — 订阅的 event topic (必须是合法 LearningEventType 或 Plugin-internal)
        - schema_version: str = "0.94.0"  — 独立 schema version (跟 POMDPPolicy 0.93.0 / CognitiveTwinAgent 0.92.0 隔离)

    防御性自检:
        - __post_init__ 校验 name / version / subscribed_topics / dependencies 合法性
        - 非法 raise ValueError (跟 Capability v0.86.0-a / POMDPDiagnostic v0.93.0-a 一致)
    """

    name: str
    version: str
    description: str = ""
    dependencies: Tuple[str, ...] = ()
    subscribed_topics: Tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        # name 校验: lowercase + alphanumeric + underscore
        if not _NAME_PATTERN.match(self.name):
            raise ValueError(
                f"PluginMetadata.name must match {_NAME_PATTERN.pattern!r} "
                f"(lowercase alphanumeric+underscore starting with letter): "
                f"name={self.name!r}"
            )
        # version 校验: semver
        if not _SEMVER_PATTERN.match(self.version):
            raise ValueError(
                f"PluginMetadata.version must be semver (e.g. '1.0.0'): "
                f"version={self.version!r}"
            )
        # subscribed_topics 校验: 必须在合法 topic 集合内
        valid = _get_valid_topics()
        invalid = set(self.subscribed_topics) - valid
        if invalid:
            raise ValueError(
                f"PluginMetadata.subscribed_topics contain invalid topics: "
                f"invalid={sorted(invalid)}, valid={sorted(valid)}"
            )
        # dependencies 不能包含 self.name (不能依赖自己)
        if self.name in self.dependencies:
            raise ValueError(
                f"PluginMetadata: plugin {self.name!r} cannot depend on itself"
            )
        # dependencies name 也要合法 (防御性)
        for dep in self.dependencies:
            if not _NAME_PATTERN.match(dep):
                raise ValueError(
                    f"PluginMetadata.dependencies contain invalid name: "
                    f"dep={dep!r}"
                )

    def to_dict(self) -> dict:
        """序列化为 dict (用于 plugin_registry DB 持久化 / logging).

        Returns:
            dict 含 6 字段 (跟 SCHEMA_VERSION 同步).
        """
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "dependencies": list(self.dependencies),
            "subscribed_topics": list(self.subscribed_topics),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PluginMetadata":
        """从 dict 反序列化 (PluginRegistryStore.load 路径).

        Args:
            data: dict 含 PluginMetadata 字段 (兼容老 DB schema_version 缺失, 默认 "0.94.0").

        Returns:
            PluginMetadata 实例.

        Raises:
            ValueError: 字段合法性校验失败 (跟 __post_init__ 一致).
        """
        return cls(
            name=str(data["name"]),
            version=str(data["version"]),
            description=str(data.get("description", "")),
            dependencies=tuple(data.get("dependencies", ())),
            subscribed_topics=tuple(data.get("subscribed_topics", ())),
            schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
        )


class Plugin(ABC):
    """ECOS Plugin SDK base class (v0.94.0-a).

    Plugin 不调用 Twin, Plugin 只能产生 Event + 读 Kernel state.
    跟 v0.85.0 Plugin Runtime 100% production 模式 + v0.91 HumanFeedbackEntry / v0.92 ActionEntry
    frozen dataclass + v0.93 POMDPDiagnostic 模式对齐.

    4 abstract method (跟 Domain ABC v0.88.0-a 4 abstract property 同风格):
        1. on_event(event)         — 处理 event, 返 result (跟 PluginRuntime._handle_* 一致)
        2. get_subscribed_topics() — 返订阅的 LearningEventType 值集合
        3. enable()                — 生命周期: 启用 plugin (subscribe to topics)
        4. disable()               — 生命周期: 禁用 plugin (unsubscribe from topics)

    设计原则:
        - Plugin 是 Kernel-agnostic: 不持有 BeliefState / LCAEngine / Runtime reference
        - Plugin 通过 LearningEvent payload 读 student_id (e.g. event.student_id), 然后调 Runtime API 拉 Kernel state
        - Plugin 不 mutate state (defensive check [8] 仍 hard block)
        - Plugin lifecycle: instantiate → register → enable → on_event (多次) → disable → unregister

    用法示例 (c 阶段 first-party plugin):
        >>> from ecos.plugins.base import Plugin, PluginMetadata
        >>> class MyPlugin(Plugin):
        ...     metadata = PluginMetadata(name="my_plugin", version="1.0.0",
        ...                                subscribed_topics=("hint_requested",))
        ...     def on_event(self, event):
        ...         return {"student_id": event.student_id}
        ...     def get_subscribed_topics(self):
        ...         return set(self.metadata.subscribed_topics)
        ...     def enable(self): pass
        ...     def disable(self): pass
    """

    metadata: PluginMetadata  # subclass 必须定义 class-level metadata

    @abstractmethod
    def on_event(self, event: LearningEvent) -> Optional[Any]:
        """处理一个 event, 返 result (跟 PluginRuntime._handle_* 完全 parallel).

        Args:
            event: LearningEvent 实例 (from_hint_requested / from_idle_detected /
                  from_goal_changed / from_reflection_completed /
                  from_pomdp_diagnostic_updated 等 factory 构造)

        Returns:
            Optional[Any] — Plugin 自定义 result (e.g. {"student_id": ..., "count": ...}).
            返 None 也合法 (plugin 仅 emit log/warning 不产出 result).

        设计:
            - Plugin 不应 mutate Kernel state (e.g. 不应调 LCAEngine.append_human_feedback 直接写)
            - Plugin 应 read-only + emit log/warning
            - 如果需要写 Kernel state, 应通过 Runtime API (e.g. Runtime.diagnose_pomdp) 走 Kernel 路径
        """
        ...

    @abstractmethod
    def get_subscribed_topics(self) -> Set[str]:
        """返订阅的 LearningEventType 值集合 (PluginRegistry.subscribe_all 用).

        Returns:
            Set[str] — e.g. {"hint_requested"} 或 {"pomdp_diagnostic_updated"}.
            元素必须是 PluginMetadata.subscribed_topics 子集.
        """
        ...

    @abstractmethod
    def enable(self) -> None:
        """Lifecycle: 启用 plugin (PluginRegistry.subscribe_all 调用).

        实现约定:
            - 清理 plugin state (e.g. 清零 counter)
            - 不调 bus.subscribe (PluginRegistry.subscribe_all 统一管理)
            - enable 后 plugin 才会被 on_event 调用
        """
        ...

    @abstractmethod
    def disable(self) -> None:
        """Lifecycle: 禁用 plugin (PluginRegistry.unsubscribe_all 调用).

        实现约定:
            - 清理 plugin state (跟 enable 对称)
            - 不调 bus.unsubscribe (PluginRegistry.unsubscribe_all 统一管理)
            - disable 后 plugin 不再被 on_event 调用
        """
        ...

    def __repr__(self) -> str:
        return (
            f"<{type(self).__name__} "
            f"name={self.metadata.name!r} v{self.metadata.version}>"
        )


__all__ = [
    "SCHEMA_VERSION",
    "PluginMetadata",
    "Plugin",
]