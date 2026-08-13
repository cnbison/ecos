"""Tests for ecos/plugins/registry.py — PluginRegistry singleton (v0.94.0-b).

对应 12-kernel-mapping §6 Plugin SDK + Phase 7+ 抽象推演 #7.

8 tests covering:
    - PluginRegistry singleton pattern (2 tests)
    - PluginRegistry register API (3 tests)
    - PluginRegistry lifecycle + EventBus integration (2 tests)
    - PluginRegistry dependencies validation (1 test)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

import pytest

from ecos.cta.event_log import LearningEvent
from ecos.event.bus import EventBus
from ecos.plugins.base import Plugin, PluginMetadata
from ecos.plugins.registry import (
    PluginRegistry,
    get_default_registry,
    reset_default_registry,
)


# ── Test helpers ──────────────────────────────────────────────────────


def _make_test_plugin(
    name: str = "test_plugin",
    topics: tuple = ("hint_requested",),
    dependencies: tuple = (),
) -> Plugin:
    """构造一个 minimal Plugin subclass for testing."""

    class _TestPlugin(Plugin):
        metadata = PluginMetadata(
            name=name,
            version="1.0.0",
            subscribed_topics=topics,
            dependencies=dependencies,
        )

        def __init__(self) -> None:
            self.event_log: List[LearningEvent] = []
            self.enabled = False

        def on_event(self, event: LearningEvent):
            self.event_log.append(event)
            return {"student_id": event.student_id}

        def get_subscribed_topics(self) -> Set[str]:
            return set(self.metadata.subscribed_topics)

        def enable(self) -> None:
            self.enabled = True

        def disable(self) -> None:
            self.enabled = False

    return _TestPlugin()


# ──────────────────────────────────────────────────────────────────────
# PluginRegistry singleton pattern (2 tests)
# ──────────────────────────────────────────────────────────────────────


def test_plugin_registry_is_singleton():
    """PluginRegistry 是 singleton (跟 DomainRegistry v0.88.0-a 完全 parallel pattern)."""
    reset_default_registry()  # 测试隔离
    r1 = PluginRegistry()
    r2 = PluginRegistry()
    assert r1 is r2


def test_get_default_registry_returns_singleton():
    """get_default_registry() 返同一个 PluginRegistry 实例."""
    reset_default_registry()
    r1 = get_default_registry()
    r2 = get_default_registry()
    assert r1 is r2


# ──────────────────────────────────────────────────────────────────────
# PluginRegistry register API (3 tests)
# ──────────────────────────────────────────────────────────────────────


def test_plugin_registry_register_and_get():
    """register(plugin) 后 get(name) 返 Plugin 实例 (跟 DomainRegistry 完全 parallel)."""
    reset_default_registry()
    registry = PluginRegistry()
    plugin = _make_test_plugin(name="hint_fatigue")
    registry.register(plugin)
    assert registry.has("hint_fatigue")
    assert registry.get("hint_fatigue") is plugin
    assert registry.get("not_registered") is None


def test_plugin_registry_duplicate_register_raises():
    """重复 register 同 name raise ValueError (防御性: 防止 version mismatch)."""
    reset_default_registry()
    registry = PluginRegistry()
    plugin1 = _make_test_plugin(name="hint_fatigue")
    registry.register(plugin1)
    plugin2 = _make_test_plugin(name="hint_fatigue")
    with pytest.raises(ValueError, match="already registered"):
        registry.register(plugin2)


def test_plugin_registry_register_non_plugin_raises():
    """register 非 Plugin 实例 raise TypeError (防御性)."""
    reset_default_registry()
    registry = PluginRegistry()
    with pytest.raises(TypeError, match="非 Plugin 实例"):
        registry.register("not_a_plugin")  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────
# PluginRegistry lifecycle + EventBus integration (2 tests)
# ──────────────────────────────────────────────────────────────────────


def test_plugin_registry_subscribe_all_mounts_to_bus():
    """subscribe_all(bus) 遍历 plugin 调 enable + bus.subscribe, 返 sub_id dict."""
    reset_default_registry()
    registry = PluginRegistry()
    bus = EventBus()
    plugin = _make_test_plugin(name="hint_fatigue", topics=("hint_requested",))
    registry.register(plugin)

    result = registry.subscribe_all(bus)

    assert "hint_fatigue" in result
    assert len(result["hint_fatigue"]) == 1
    assert plugin.enabled
    assert registry.is_enabled("hint_fatigue")


def test_plugin_registry_unsubscribe_all_disables():
    """unsubscribe_all(bus) 调 bus.unsubscribe + plugin.disable, 清理 subscription_ids."""
    reset_default_registry()
    registry = PluginRegistry()
    bus = EventBus()
    plugin = _make_test_plugin(name="hint_fatigue", topics=("hint_requested",))
    registry.register(plugin)
    registry.subscribe_all(bus)
    assert plugin.enabled

    registry.unsubscribe_all(bus)

    assert not plugin.enabled
    assert not registry.is_enabled("hint_fatigue")


# ──────────────────────────────────────────────────────────────────────
# PluginRegistry dependencies validation (1 test)
# ──────────────────────────────────────────────────────────────────────


def test_plugin_registry_dependency_check():
    """register 时校验 dependencies: 未注册的 dep raise ValueError (软依赖)."""
    reset_default_registry()
    registry = PluginRegistry()
    # 先注册一个 plugin without dep
    base_plugin = _make_test_plugin(name="base_plugin")
    registry.register(base_plugin)

    # 注册 dep plugin (引用 base_plugin)
    dep_plugin = _make_test_plugin(name="dep_plugin", dependencies=("base_plugin",))
    registry.register(dep_plugin)  # 不 raise (base_plugin 已 register)

    # 注册 missing dep plugin
    missing_dep_plugin = _make_test_plugin(
        name="missing_dep_plugin", dependencies=("not_registered",)
    )
    with pytest.raises(ValueError, match="requires dependency .* not registered"):
        registry.register(missing_dep_plugin)


# ──────────────────────────────────────────────────────────────────────
# Bonus: list_names / list_plugins / clear / reset (additional coverage)
# ──────────────────────────────────────────────────────────────────────


def test_plugin_registry_list_names_sorted():
    """list_names() 按字母序 sorted (跨进程稳定输出)."""
    reset_default_registry()
    registry = PluginRegistry()
    registry.register(_make_test_plugin(name="z_plugin"))
    registry.register(_make_test_plugin(name="a_plugin"))
    registry.register(_make_test_plugin(name="m_plugin"))
    assert registry.list_names() == ["a_plugin", "m_plugin", "z_plugin"]


def test_plugin_registry_clear_and_reset():
    """clear() / reset() 清空 registry (测试隔离用)."""
    reset_default_registry()
    registry = PluginRegistry()
    registry.register(_make_test_plugin(name="hint_fatigue"))
    assert registry.has("hint_fatigue")

    registry.clear()
    assert not registry.has("hint_fatigue")
    assert registry.list_names() == []

    # 重新注册应 work (singleton 实例仍然在, 仅清空 state)
    registry.register(_make_test_plugin(name="other_plugin"))
    assert registry.has("other_plugin")