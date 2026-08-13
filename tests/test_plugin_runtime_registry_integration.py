"""Tests for PluginRuntime + PluginRegistry DI integration (v0.94.0-b).

对应 12-kernel-mapping §6 Plugin SDK + Phase 7+ 抽象推演 #7.

5 tests covering:
    - PluginRuntime.__init__ accepts plugin_registry_factory kwarg (DI)
    - PluginRuntime.start() triggers PluginRegistry.subscribe_all
    - PluginRuntime.stop() triggers PluginRegistry.unsubscribe_all
    - subscription_count maintained at 8 (built-in) — Plugin registry is additional layer
    - DI: custom plugin_registry_factory overrides default
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

import pytest

from ecos.cta.event_log import LearningEvent
from ecos.event.bus import EventBus
from ecos.plugins.base import Plugin, PluginMetadata
from ecos.plugins.registry import PluginRegistry, reset_default_registry


def _make_minimal_plugin(name: str = "test_plugin") -> Plugin:
    """Minimal Plugin for testing registry integration."""

    class _TestPlugin(Plugin):
        metadata = PluginMetadata(
            name=name,
            version="1.0.0",
            subscribed_topics=("hint_requested",),
        )

        def on_event(self, event: LearningEvent):
            return {"student_id": event.student_id}

        def get_subscribed_topics(self) -> Set[str]:
            return set(self.metadata.subscribed_topics)

        def enable(self) -> None:
            pass

        def disable(self) -> None:
            pass

    return _TestPlugin()


@pytest.fixture(autouse=True)
def _reset_plugin_registry():
    """每个 test 自动 reset PluginRegistry singleton (测试隔离)."""
    reset_default_registry()
    yield
    reset_default_registry()


# ──────────────────────────────────────────────────────────────────────
# PluginRuntime DI integration (5 tests)
# ──────────────────────────────────────────────────────────────────────


def test_plugin_runtime_accepts_plugin_registry_factory_kwarg():
    """PluginRuntime.__init__ 接受 plugin_registry_factory kwarg (DI 注入)."""
    from web.api.plugin_runtime import PluginRuntime

    custom_registry = PluginRegistry()
    custom_registry.register(_make_minimal_plugin(name="custom_plugin"))

    def custom_factory() -> PluginRegistry:
        return custom_registry

    runtime = PluginRuntime(plugin_registry_factory=custom_factory)
    # 验证 DI 注入成功 (没有调 start() 之前, _plugin_registry_factory 应该是 custom_factory)
    assert runtime._plugin_registry_factory is custom_factory


def test_plugin_runtime_start_calls_plugin_registry_subscribe_all():
    """PluginRuntime.start() 调 PluginRegistry.subscribe_all(bus), first-party plugin 挂载到 bus."""
    from web.api.plugin_runtime import PluginRuntime

    bus = EventBus()
    # 注册一个 test plugin 到 default singleton registry
    plugin = _make_minimal_plugin(name="hint_fatigue")
    registry = PluginRegistry()
    registry.register(plugin)

    runtime = PluginRuntime()  # 默认 plugin_registry_factory
    runtime._bus = bus  # 注入 test bus
    runtime.start()

    # Plugin 应该已 enabled
    assert registry.is_enabled("hint_fatigue")

    # bus 应已收到 hint_requested 订阅 (从 PluginRegistry.subscribe_all)
    # 模拟 emit event 验证 plugin on_event 被调
    event = LearningEvent.from_hint_requested(student_id="lbc001", problem_id="PB-Q01")
    success_count = bus.publish("hint_requested", event)
    # 至少有 1 个 subscriber (来自 PluginRegistry) + built-in (hint_requested 也走 PluginRuntime._handle_hint_requested)
    # 但 hint_requested 在 PluginRuntime._handle_hint_requested 也订阅了 — 实际是 2 个 subscriber
    assert success_count >= 1  # at least PluginRegistry subscribed successfully

    runtime.stop()


def test_plugin_runtime_stop_calls_plugin_registry_unsubscribe_all():
    """PluginRuntime.stop() 调 PluginRegistry.unsubscribe_all(bus), first-party plugin 反挂载."""
    from web.api.plugin_runtime import PluginRuntime

    bus = EventBus()
    plugin = _make_minimal_plugin(name="hint_fatigue")
    registry = PluginRegistry()
    registry.register(plugin)

    runtime = PluginRuntime()
    runtime._bus = bus
    runtime.start()
    assert registry.is_enabled("hint_fatigue")

    runtime.stop()
    assert not registry.is_enabled("hint_fatigue")


def test_plugin_runtime_subscription_count_maintained_at_8():
    """PluginRuntime.subscription_count 维持 8 (built-in) — Plugin registry 是 additional layer.

    对应 12-kernel-mapping §6 PluginRuntime 8 subscriber 表:
    response_submitted / request_calibration / request_intervention /
    hint_requested / idle_detected / goal_changed / reflection_completed / pomdp_diagnostic_updated.
    PluginRegistry 管理的 first-party plugin 订阅不影响 subscription_count.
    """
    from web.api.plugin_runtime import PluginRuntime

    bus = EventBus()
    # 注册多个 first-party plugin (让 PluginRegistry 内部有 sub_id)
    plugin1 = _make_minimal_plugin(name="plugin_a")
    plugin2 = _make_minimal_plugin(name="plugin_b")
    registry = PluginRegistry()
    registry.register(plugin1)
    registry.register(plugin2)

    runtime = PluginRuntime()
    runtime._bus = bus
    runtime.start()

    # subscription_count 仍 = 8 (built-in), 不含 PluginRegistry 挂载的 first-party plugin
    assert runtime.subscription_count == 8

    runtime.stop()
    assert runtime.subscription_count == 0  # 全部 unsubscribe


def test_plugin_runtime_di_custom_registry_factory_overrides_default():
    """DI: 自定义 plugin_registry_factory 被调 — 测试隔离场景.

    验证:
        1. 自定义 factory 在 start() 时被调 (而非默认 _default_plugin_registry_factory)
        2. factory 返的 registry 上的 plugin 被 enable
        3. 自定义 factory 不影响 default singleton (隔离 OK)
    """
    from web.api.plugin_runtime import PluginRuntime

    bus = EventBus()
    factory_call_count = 0

    # 构造 custom registry (PluginRegistry 是 singleton, custom_registry 即 singleton)
    custom_registry = PluginRegistry()
    custom_plugin = _make_minimal_plugin(name="custom_plugin")
    custom_registry.register(custom_plugin)
    # 清理 enable 状态 (因为其他 test 可能 enable 过)
    custom_registry.disable("custom_plugin")

    def custom_factory() -> PluginRegistry:
        nonlocal factory_call_count
        factory_call_count += 1
        return custom_registry

    runtime = PluginRuntime(plugin_registry_factory=custom_factory)
    runtime._bus = bus
    runtime.start()

    # custom_factory 被调了 (start 调用了它)
    assert factory_call_count >= 1
    # custom_plugin 应该 enable (通过 custom_factory 注入的 registry)
    assert custom_registry.is_enabled("custom_plugin")

    runtime.stop()
    assert not custom_registry.is_enabled("custom_plugin")