"""ECOS Plugin Registry singleton —— v0.94.0-b.

对应 12-kernel-mapping §6 Plugin SDK (Phase 7+ 抽象推演 #7):
    - Plugin Registry singleton (跟 DomainRegistry v0.88.0-a 100% parallel API)
    - Plugin lifecycle 管理 (instantiate → register → enable → on_event → disable → unregister)
    - EventBus 集成 (subscribe_all / unsubscribe_all)

v0.94.0-b 设计:
    - PluginRegistry singleton (跟 DomainRegistry 完全 parallel pattern)
    - register(plugin) / get(name) / has(name) / list_names() / list_plugins() / clear() / reset()
    - subscribe_all(bus) / unsubscribe_all(bus) — Plugin lifecycle 跟 EventBus 联动
    - is_enabled(name) — query enabled state
    - dependencies 校验 (register 时)

向后兼容:
    - 不引用 BeliefState / LCAEngine / Runtime
    - PluginRegistry 跟 PluginRuntime 8 subscriber (v0.93.0-b) 解耦 — PluginRuntime built-in 8 subscriber 优先
    - Plugin 通过 PluginRegistry.register + PluginRuntime.start() 联合调用挂载
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from ecos.plugins.base import Plugin

_log = logging.getLogger(__name__)


class PluginRegistry:
    """ECOS Plugin Registry singleton (v0.94.0-b).

    跟 DomainRegistry v0.88.0-a 完全 parallel API surface.
    Plugin lifecycle: instantiate → register → enable → on_event (多次) → disable → unregister.

    设计:
        - 模块级 singleton (单进程 1 份, 跟 DomainRegistry 同)
        - register: 注册 Plugin 实例 (按 name 索引, 重复 register raise ValueError)
        - get: 按 name 反查 Plugin 实例 (None = 不存在)
        - has: 判定 Plugin 是否已注册
        - list_names: 列出所有已注册 Plugin name (sorted)
        - list_plugins: 列出所有已注册 Plugin 实例 (sorted by name)
        - is_enabled: query Plugin 是否 enabled
        - clear / reset: 测试隔离用 (跟 DomainRegistry.reset() 同 pattern)

    Plugin lifecycle:
        1. instantiate (Plugin(metadata=...))
        2. register (registry.register(plugin)) — 检查 dependencies
        3. enable (在 subscribe_all 时统一调, 或外部手动调)
        4. on_event (多次, EventBus 触发)
        5. disable (在 unsubscribe_all 时统一调, 或外部手动调)
        6. unregister (PluginRegistry.reset() 或 PluginRegistry.clear() 清空)
    """

    _instance: Optional["PluginRegistry"] = None

    def __new__(cls) -> "PluginRegistry":
        """Singleton pattern (跟 DomainRegistry v0.88.0-a 完全 parallel)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._plugins: Dict[str, Plugin] = {}
            cls._instance._subscription_ids: Dict[str, List[str]] = {}
            cls._instance._enabled: Dict[str, bool] = {}
        return cls._instance

    # ── API: register / get / has / list ─────────────────────────────────────

    def register(self, plugin: Plugin) -> None:
        """注册 Plugin 实例 (按 metadata.name 索引).

        Args:
            plugin: Plugin 实例 (Plugin ABC subclass).

        Raises:
            ValueError: 重复 name / 依赖未注册 / metadata 非法.

        防御性自检 [1]: 重复 name raise ValueError (跟 DomainRegistry.register
        idempotent 覆盖相反 — Plugin 不能覆盖, 否则可能引入 version mismatch).
        """
        if not isinstance(plugin, Plugin):
            raise TypeError(
                f"PluginRegistry.register: 非 Plugin 实例 (type={type(plugin).__name__})"
            )
        name = plugin.metadata.name
        if name in self._plugins:
            raise ValueError(
                f"PluginRegistry.register: plugin {name!r} already registered "
                f"(existing type={type(self._plugins[name]).__name__})"
            )
        # dependencies 校验: 每个 dep 必须已 register (软依赖 — 仅 register 时检查)
        for dep in plugin.metadata.dependencies:
            if dep not in self._plugins:
                raise ValueError(
                    f"PluginRegistry.register: plugin {name!r} requires "
                    f"dependency {dep!r} not registered"
                )
        self._plugins[name] = plugin
        self._enabled[name] = False
        _log.debug(
            "PluginRegistry.register: registered plugin=%s v%s",
            name, plugin.metadata.version,
        )

    def get(self, name: str) -> Optional[Plugin]:
        """按 name 反查 Plugin 实例.

        Args:
            name: Plugin name (跟 metadata.name 一致).

        Returns:
            Plugin 实例 或 None (防御性自检 [1]: 不存在返 None, 不 raise).

        跟 DomainRegistry.get() 完全 parallel API.
        """
        return self._plugins.get(name)

    def has(self, name: str) -> bool:
        """判定 Plugin 是否已注册.

        Args:
            name: Plugin name.

        Returns:
            bool (跟 DomainRegistry.has() 完全 parallel API).
        """
        return name in self._plugins

    def list_names(self) -> List[str]:
        """列出所有已注册 Plugin name (sorted).

        Returns:
            List[str] 按字母序 sorted (跟 DomainRegistry.list_names() 略有不同,
            DomainRegistry 是按注册顺序, PluginRegistry 是 sorted — 便于跨进程稳定输出).
        """
        return sorted(self._plugins.keys())

    def list_plugins(self) -> List[Plugin]:
        """列出所有已注册 Plugin 实例 (sorted by name)."""
        return [self._plugins[name] for name in self.list_names()]

    # ── API: enable / disable / is_enabled ───────────────────────────────────

    def is_enabled(self, name: str) -> bool:
        """Query Plugin 是否已 enable (subscribe 到 bus).

        Args:
            name: Plugin name.

        Returns:
            bool (False if not registered or not enabled).

        跟 Plugin lifecycle 跟踪 — Plugin metadata 仅声明 subscribed_topics,
        实际 subscribe 到 bus 由 subscribe_all() 统一管理, 这里追踪 enable 状态.
        """
        return self._enabled.get(name, False)

    def enable(self, name: str) -> None:
        """手动 enable 一个 plugin (调 plugin.enable()).

        跟 subscribe_all() 区别: subscribe_all 会调 enable + bus.subscribe;
        enable() 仅调 plugin.enable(), 不动 bus. 适用于 "Plugin 已 subscribe,
        想从 disabled 状态恢复" 场景.

        Args:
            name: Plugin name.

        Raises:
            KeyError: Plugin 未注册.
        """
        if name not in self._plugins:
            raise KeyError(f"PluginRegistry.enable: plugin {name!r} not registered")
        if self._enabled.get(name, False):
            return  # 幂等: 已 enabled 不重复调
        self._plugins[name].enable()
        self._enabled[name] = True

    def disable(self, name: str) -> None:
        """手动 disable 一个 plugin (调 plugin.disable()).

        跟 unsubscribe_all() 区别: unsubscribe_all 会调 bus.unsubscribe + plugin.disable;
        disable() 仅调 plugin.disable(), 不动 bus.

        Args:
            name: Plugin name.

        Raises:
            KeyError: Plugin 未注册.
        """
        if name not in self._plugins:
            raise KeyError(f"PluginRegistry.disable: plugin {name!r} not registered")
        if not self._enabled.get(name, False):
            return  # 幂等
        self._plugins[name].disable()
        self._enabled[name] = False

    # ── API: subscribe_all / unsubscribe_all (EventBus 联动) ─────────────────

    def subscribe_all(self, bus: Any) -> Dict[str, List[str]]:
        """遍历所有 plugin, 调 enable() + bus.subscribe() 挂载到 bus.

        Args:
            bus: EventBus 实例 (避免硬依赖, Any 类型 — 接受 EventBus / Mock).

        Returns:
            Dict[plugin_name, List[subscription_id]] — 每个 plugin 的 sub_id 列表.

        防御性:
            - 重复 subscribe_all 是幂等的 (plugin 已 enabled 则跳过 enable)
            - EventBus.subscribe 返回的 sub_id 存到 self._subscription_ids 供 unsubscribe_all 用
        """
        result: Dict[str, List[str]] = {}
        for plugin in self.list_plugins():
            name = plugin.metadata.name
            if not self._enabled.get(name, False):
                plugin.enable()
                self._enabled[name] = True
            sub_ids: List[str] = []
            for topic in plugin.get_subscribed_topics():
                try:
                    sub_id = bus.subscribe(topic, plugin.on_event)
                    sub_ids.append(sub_id)
                except Exception:
                    _log.warning(
                        "PluginRegistry.subscribe_all: bus.subscribe failed "
                        "for plugin=%s topic=%s",
                        name, topic, exc_info=True,
                    )
            self._subscription_ids[name] = sub_ids
            result[name] = list(sub_ids)
        return result

    def unsubscribe_all(self, bus: Any) -> None:
        """遍历所有 enabled plugin, 调 bus.unsubscribe() + plugin.disable().

        Args:
            bus: EventBus 实例.

        防御性:
            - 重复 unsubscribe_all 是幂等的 (subscription_ids 清空后跳过)
            - plugin.disable() 失败不阻断其他 plugin (catch + _log.warning + continue)
        """
        for plugin_name, sub_ids in list(self._subscription_ids.items()):
            for sub_id in sub_ids:
                try:
                    bus.unsubscribe(sub_id)
                except Exception:
                    _log.warning(
                        "PluginRegistry.unsubscribe_all: bus.unsubscribe failed "
                        "for plugin=%s sub_id=%s",
                        plugin_name, sub_id, exc_info=True,
                    )
            plugin = self._plugins.get(plugin_name)
            if plugin is not None and self._enabled.get(plugin_name, False):
                try:
                    plugin.disable()
                except Exception:
                    _log.warning(
                        "PluginRegistry.unsubscribe_all: plugin.disable failed "
                        "for plugin=%s",
                        plugin_name, exc_info=True,
                    )
                self._enabled[plugin_name] = False
        self._subscription_ids.clear()

    # ── API: clear / reset (测试隔离) ────────────────────────────────────────

    def clear(self) -> None:
        """清空 registry (测试隔离用, 不推荐 production 使用).

        跟 DomainRegistry.clear() 完全 parallel API — 清空 dict 但不重置 singleton.
        """
        self._plugins.clear()
        self._subscription_ids.clear()
        self._enabled.clear()

    def reset(self) -> None:
        """重置 singleton (测试隔离用, 跟 DomainRegistry.reset() 同 pattern).

        跟 DomainRegistry 一致: 仅清空 in-memory state, 不破坏 singleton 实例.
        生产代码不应调 reset().
        """
        self.clear()


def get_default_registry() -> PluginRegistry:
    """获取默认 PluginRegistry singleton (懒加载, 跟 DomainRegistry.get_default_registry() 同 pattern)."""
    return PluginRegistry()


def reset_default_registry() -> None:
    """Reset module-level singleton (测试隔离用, 跟 DomainRegistry 完全 parallel).

    跟 PluginRegistry.reset() 区别: 这个会强制重建 singleton (清空 _instance),
    PluginRegistry.reset() 仅清空 in-memory state.
    """
    PluginRegistry._instance = None


__all__ = [
    "PluginRegistry",
    "get_default_registry",
    "reset_default_registry",
]