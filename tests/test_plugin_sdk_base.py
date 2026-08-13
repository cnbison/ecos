"""Tests for ecos/plugins/base.py — Plugin ABC + PluginMetadata frozen dataclass (v0.94.0-a).

对应 12-kernel-mapping §6 Plugin SDK + Phase 7+ 抽象推演 #7.

12 tests covering:
    - PluginMetadata __post_init__ validation (4 tests)
    - PluginMetadata serialization round-trip (2 tests)
    - PluginMetadata frozen invariant (1 test)
    - Plugin ABC instantiation guard (2 tests)
    - Concrete Plugin subclass lifecycle (3 tests)
"""

from __future__ import annotations

import pytest

from ecos.cta.event_log import LearningEvent, LearningEventType
from ecos.plugins.base import (
    SCHEMA_VERSION,
    Plugin,
    PluginMetadata,
)


# ──────────────────────────────────────────────────────────────────────
# PluginMetadata __post_init__ validation (4 tests)
# ──────────────────────────────────────────────────────────────────────


def test_plugin_metadata_valid_creation():
    """PluginMetadata 合法构造 (name / version / subscribed_topics 全合法)."""
    meta = PluginMetadata(
        name="hint_fatigue",
        version="1.0.0",
        description="Detect hint overuse",
        subscribed_topics=("hint_requested",),
    )
    assert meta.name == "hint_fatigue"
    assert meta.version == "1.0.0"
    assert meta.description == "Detect hint overuse"
    assert meta.subscribed_topics == ("hint_requested",)
    assert meta.dependencies == ()
    assert meta.schema_version == "0.94.0"


def test_plugin_metadata_invalid_name_raises():
    """PluginMetadata.name 非法 (含大写 / 数字开头 / 特殊字符) raise ValueError."""
    with pytest.raises(ValueError, match="name must match"):
        PluginMetadata(name="HintFatigue", version="1.0.0")
    with pytest.raises(ValueError, match="name must match"):
        PluginMetadata(name="123_hint", version="1.0.0")  # 数字开头
    with pytest.raises(ValueError, match="name must match"):
        PluginMetadata(name="hint-fatigue", version="1.0.0")  # 短横线
    with pytest.raises(ValueError, match="name must match"):
        PluginMetadata(name="", version="1.0.0")  # 空字符串


def test_plugin_metadata_invalid_version_raises():
    """PluginMetadata.version 非法 (非 semver 3 段数字) raise ValueError."""
    with pytest.raises(ValueError, match="version must be semver"):
        PluginMetadata(name="hint_fatigue", version="1.0")  # 2 段
    with pytest.raises(ValueError, match="version must be semver"):
        PluginMetadata(name="hint_fatigue", version="v1.0.0")  # 含 v
    with pytest.raises(ValueError, match="version must be semver"):
        PluginMetadata(name="hint_fatigue", version="1.0.0-beta")  # 含 pre-release


def test_plugin_metadata_invalid_subscribed_topics_raises():
    """PluginMetadata.subscribed_topics 含非法 topic raise ValueError."""
    with pytest.raises(ValueError, match="invalid topics"):
        PluginMetadata(
            name="bad_plugin",
            version="1.0.0",
            subscribed_topics=("not_a_real_topic",),
        )


# ──────────────────────────────────────────────────────────────────────
# PluginMetadata serialization round-trip (2 tests)
# ──────────────────────────────────────────────────────────────────────


def test_plugin_metadata_to_dict():
    """PluginMetadata.to_dict() 返 6 字段 dict (含 schema_version)."""
    meta = PluginMetadata(
        name="hint_fatigue",
        version="1.0.0",
        description="Detect hint overuse",
        dependencies=("dummy",),
        subscribed_topics=("hint_requested",),
    )
    d = meta.to_dict()
    assert d == {
        "name": "hint_fatigue",
        "version": "1.0.0",
        "description": "Detect hint overuse",
        "dependencies": ["dummy"],
        "subscribed_topics": ["hint_requested"],
        "schema_version": "0.94.0",
    }


def test_plugin_metadata_from_dict_round_trip():
    """PluginMetadata.from_dict() + to_dict() round-trip 等价."""
    original = PluginMetadata(
        name="parent_engagement",
        version="2.1.3",
        description="Parent dashboard",
        dependencies=("hint_fatigue", "teacher_progress"),
        subscribed_topics=("pomdp_diagnostic_updated",),
    )
    d = original.to_dict()
    restored = PluginMetadata.from_dict(d)
    assert restored == original


# ──────────────────────────────────────────────────────────────────────
# PluginMetadata frozen invariant (1 test)
# ──────────────────────────────────────────────────────────────────────


def test_plugin_metadata_frozen():
    """PluginMetadata frozen: 创建后不能改 name (防御性)."""
    meta = PluginMetadata(name="hint_fatigue", version="1.0.0")
    with pytest.raises(Exception):  # FrozenInstanceError 是 dataclasses 内部
        meta.name = "other_plugin"  # type: ignore[misc]


# ──────────────────────────────────────────────────────────────────────
# Plugin ABC instantiation guard (2 tests)
# ──────────────────────────────────────────────────────────────────────


def test_plugin_abc_cannot_instantiate():
    """Plugin(ABC) 不能直接 instantiate (TypeError due to abstract methods)."""
    with pytest.raises(TypeError, match="abstract"):
        Plugin()  # type: ignore[abstract]


def test_plugin_subclass_missing_method_raises():
    """Plugin subclass 缺 4 abstract method 之一 raise TypeError."""
    # 缺 on_event
    with pytest.raises(TypeError, match="abstract"):
        class IncompletePlugin1(Plugin):
            metadata = PluginMetadata(name="incomplete1", version="1.0.0")

            def get_subscribed_topics(self):
                return set()

            def enable(self):
                pass

            def disable(self):
                pass

        IncompletePlugin1()  # type: ignore[abstract]


# ──────────────────────────────────────────────────────────────────────
# Concrete Plugin subclass lifecycle (3 tests)
# ──────────────────────────────────────────────────────────────────────


def _make_concrete_plugin() -> Plugin:
    """构造一个最小合法 Plugin (用于 lifecycle 测试)."""

    class ConcretePlugin(Plugin):
        metadata = PluginMetadata(
            name="concrete_test",
            version="1.0.0",
            subscribed_topics=("hint_requested",),
        )

        def __init__(self) -> None:
            self.event_count = 0
            self.enabled = False

        def on_event(self, event: LearningEvent):
            self.event_count += 1
            return {"student_id": event.student_id, "count": self.event_count}

        def get_subscribed_topics(self):
            return set(self.metadata.subscribed_topics)

        def enable(self):
            self.enabled = True
            self.event_count = 0

        def disable(self):
            self.enabled = False

    return ConcretePlugin()


def test_plugin_subclass_lifecycle_on_event_returns_result():
    """Plugin.on_event 返 result dict (跟 PluginRuntime._handle_* 一致)."""
    plugin = _make_concrete_plugin()
    event = LearningEvent.from_hint_requested(
        student_id="lbc001", problem_id="PB-Q01", hint_level=1
    )
    result = plugin.on_event(event)
    assert result == {"student_id": "lbc001", "count": 1}


def test_plugin_subclass_lifecycle_enable_disable():
    """Plugin.enable / disable 切换 enabled 状态 + 清零 counter."""
    plugin = _make_concrete_plugin()
    assert not plugin.enabled
    plugin.enable()
    assert plugin.enabled
    assert plugin.event_count == 0
    event = LearningEvent.from_hint_requested(
        student_id="lbc001", problem_id="PB-Q01"
    )
    plugin.on_event(event)
    assert plugin.event_count == 1
    plugin.disable()
    assert not plugin.enabled


def test_plugin_get_subscribed_topics_returns_set():
    """Plugin.get_subscribed_topics() 返 set (跟 PluginRegistry.subscribe_all 用)."""
    plugin = _make_concrete_plugin()
    topics = plugin.get_subscribed_topics()
    assert isinstance(topics, set)
    assert "hint_requested" in topics


# ──────────────────────────────────────────────────────────────────────
# Bonus: SCHEMA_VERSION + Plugin-internal topics (1 test)
# ──────────────────────────────────────────────────────────────────────


def test_schema_version_is_0_94_0():
    """SCHEMA_VERSION = '0.94.0' (跟 POMDPPolicy 0.93.0 / CognitiveTwinAgent 0.92.0 隔离)."""
    assert SCHEMA_VERSION == "0.94.0"
    # 独立 schema isolation: PluginMetadata 默认 schema_version 不等于 POMDPPolicy / CognitiveTwinAgent
    assert SCHEMA_VERSION != "0.93.0"
    assert SCHEMA_VERSION != "0.92.0"


def test_plugin_metadata_accepts_pomdp_diagnostic_updated_topic():
    """PluginMetadata 允许 'pomdp_diagnostic_updated' topic (PluginRuntime 内部 topic, 不在 LearningEventType enum).

    对应 v0.93.0-b PluginRuntime._handle_pomdp_diagnostic_updated 用 bus.publish("pomdp_diagnostic_updated", ...)
    不走 LearningEvent factory, 是 Plugin-internal topic. Plugin SDK 必须支持这个 topic.
    """
    meta = PluginMetadata(
        name="parent_engagement",
        version="1.0.0",
        subscribed_topics=("pomdp_diagnostic_updated",),
    )
    assert "pomdp_diagnostic_updated" in meta.subscribed_topics


def test_plugin_self_dependency_raises():
    """PluginMetadata 不能依赖自己 (defensive validation)."""
    # 直接构造: dependencies 含 self.name — 但 PluginMetadata 不依赖 name 在 dependencies 中
    # 实际上 PluginMetadata.__post_init__ 校验 self.name in self.dependencies
    # 但 dependencies 字段是构造时传入, name 在元组中才能 trigger
    with pytest.raises(ValueError, match="cannot depend on itself"):
        PluginMetadata(
            name="self_dep",
            version="1.0.0",
            dependencies=("self_dep",),  # 含 self.name
        )