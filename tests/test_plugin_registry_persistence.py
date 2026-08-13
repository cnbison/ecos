"""Tests for ecos/persistence/plugin_registry_store.py — PluginRegistryStore (v0.94.0-d).

对应 12-kernel-mapping §6 Plugin SDK + Phase 7+ 抽象推演 #7.

4 tests covering:
    - save_plugin + load_plugin round-trip (含 schema_version 校验)
    - save_to_db (3 first-party plugin) + list_all 返 sorted list
    - load_from_db instantiate 3 first-party plugin + register (singleton 隔离)
    - 老 DB 兼容: CREATE TABLE IF NOT EXISTS 幂等 (二次 init_schema 不 raise)
"""

from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, List, Optional

import pytest

from ecos.persistence.plugin_registry_store import PluginRegistryStore
from ecos.plugins.first_party import (
    HintFatiguePlugin,
    ParentEngagementPlugin,
    TeacherProgressPlugin,
)
from ecos.plugins.registry import PluginRegistry, reset_default_registry


@pytest.fixture
def temp_db_path():
    """临时 DB path fixture (test isolation)."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture(autouse=True)
def _reset_plugin_registry():
    """每个 test 自动 reset PluginRegistry singleton."""
    reset_default_registry()
    yield
    reset_default_registry()


# ──────────────────────────────────────────────────────────────────────
# PluginRegistryStore save/load round-trip (1 test)
# ──────────────────────────────────────────────────────────────────────


def test_plugin_registry_store_save_load_roundtrip(temp_db_path):
    """save_plugin + load_plugin round-trip: 6 字段对齐 + schema_version 默认 "0.94.0"."""
    store = PluginRegistryStore(db_path=temp_db_path)

    metadata = {
        "name": "hint_fatigue",
        "version": "1.0.0",
        "description": "Hint fatigue detector",
        "dependencies": [],
        "subscribed_topics": ["hint_requested"],
        "schema_version": "0.94.0",
    }
    store.save_plugin(
        name="hint_fatigue",
        version="1.0.0",
        enabled=True,
        subscribed_topics=["hint_requested"],
        metadata=metadata,
    )

    row = store.load_plugin("hint_fatigue")
    assert row is not None
    assert row["name"] == "hint_fatigue"
    assert row["version"] == "1.0.0"
    assert row["enabled"] is True
    assert row["subscribed_topics"] == ["hint_requested"]
    assert row["metadata"] == metadata
    assert row["schema_version"] == "0.94.0"
    # registered_at 是 ISO timestamp
    assert row["registered_at"] is not None

    # 不存在的 plugin 返 None
    assert store.load_plugin("not_registered") is None

    store.close()


# ──────────────────────────────────────────────────────────────────────
# PluginRegistry.save_to_db + PluginRegistryStore.list_all (1 test)
# ──────────────────────────────────────────────────────────────────────


def test_plugin_registry_save_to_db_persists_3_first_party(temp_db_path):
    """PluginRegistry.save_to_db 持久化 3 first-party plugin, list_all 返 sorted list."""
    store = PluginRegistryStore(db_path=temp_db_path)
    registry = PluginRegistry()
    registry.register(HintFatiguePlugin())
    registry.register(ParentEngagementPlugin())
    registry.register(TeacherProgressPlugin())

    # Save
    registry.save_to_db(store)

    # List all (sorted by name)
    rows = store.list_all()
    assert len(rows) == 3
    assert [r["name"] for r in rows] == [
        "hint_fatigue", "parent_engagement", "teacher_progress",
    ]

    # 验证每个 row 字段
    hint_row = next(r for r in rows if r["name"] == "hint_fatigue")
    assert hint_row["subscribed_topics"] == ["hint_requested"]
    assert hint_row["metadata"]["schema_version"] == "0.94.0"

    parent_row = next(r for r in rows if r["name"] == "parent_engagement")
    assert parent_row["subscribed_topics"] == ["pomdp_diagnostic_updated"]

    teacher_row = next(r for r in rows if r["name"] == "teacher_progress")
    assert teacher_row["subscribed_topics"] == ["pomdp_diagnostic_updated"]

    store.close()


# ──────────────────────────────────────────────────────────────────────
# PluginRegistry.load_from_db instantiate + register (1 test)
# ──────────────────────────────────────────────────────────────────────


def test_plugin_registry_load_from_db_rebuilds_registry(temp_db_path):
    """PluginRegistry.load_from_db 从 DB 重建 registry, instantiate + register 3 first-party."""
    store = PluginRegistryStore(db_path=temp_db_path)

    # 1) 先 save (模拟 v0.94.0-d 之前 startup 写入)
    reg1 = PluginRegistry()
    reg1.register(HintFatiguePlugin())
    reg1.register(ParentEngagementPlugin())
    reg1.register(TeacherProgressPlugin())
    reg1.save_to_db(store)

    # 2) Reset singleton + 重新 load (模拟新进程启动)
    reset_default_registry()
    reg2 = PluginRegistry()

    # 3) load_from_db instantiate 3 plugin + register
    registered = reg2.load_from_db(store)
    assert registered == ["hint_fatigue", "parent_engagement", "teacher_progress"]
    assert reg2.list_names() == ["hint_fatigue", "parent_engagement", "teacher_progress"]

    # 验证 metadata 跟 DB 一致 (PluginMetadata.from_dict 路径)
    assert reg2.get("hint_fatigue").metadata.version == "1.0.0"
    assert reg2.get("parent_engagement").metadata.subscribed_topics == ("pomdp_diagnostic_updated",)

    store.close()


# ──────────────────────────────────────────────────────────────────────
# 老 DB 兼容: CREATE TABLE IF NOT EXISTS 幂等 (1 test)
# ──────────────────────────────────────────────────────────────────────


def test_plugin_registry_store_init_schema_is_idempotent(temp_db_path):
    """PluginRegistryStore._init_schema 幂等: 二次调用 + 老 DB 重建不 raise.

    老 DB (v0.93 前) 无 plugin_registry 表, CREATE TABLE IF NOT EXISTS 兜底.
    v0.94+ 二次 init_schema 应幂等 (覆盖现有表 schema 不变).
    """
    store1 = PluginRegistryStore(db_path=temp_db_path)
    # 写一行
    store1.save_plugin(
        name="hint_fatigue",
        version="1.0.0",
        enabled=True,
        subscribed_topics=["hint_requested"],
        metadata={"name": "hint_fatigue", "version": "1.0.0"},
    )
    store1.close()

    # 重启 (新连接), 应幂等建表 (数据不丢)
    store2 = PluginRegistryStore(db_path=temp_db_path)
    rows = store2.list_all()
    assert len(rows) == 1
    assert rows[0]["name"] == "hint_fatigue"

    # 再 close + 再启 (3 次 init_schema 全幂等)
    store2.close()
    store3 = PluginRegistryStore(db_path=temp_db_path)
    rows3 = store3.list_all()
    assert len(rows3) == 1
    store3.close()