"""ECOS First-party Plugin Library 3 Use Case 示例 (v0.94.0-c).

对应设计: docs/plugin_library.md §五 + §八.

Use Case:
  1. register_three_first_party: 注册 3 first-party plugin 到 default registry + 列出
  2. enable_disable_lifecycle: HintFatiguePlugin enable/disable 计数清零 lifecycle 演示
  3. hot_reload_from_db: 持久化到 DB + 从 DB 重建 (PluginRegistryStore + load_from_db)

Plugin 原则 (per docs/plugin_library.md §一):
  - Plugin 不调 LCAEngine / Runtime write API
  - Plugin 只订阅 EventBus topic + 读 event.payload
  - Plugin 不 mutate BeliefState (defensive check [8] hard block)
  - Plugin 走 SDK Plugin ABC + PluginRegistry.register

不变量:
  - First-party plugin 全程 read-only + log warning, 不写 state
  - Lifecycle: instantiate → register → enable → on_event → disable → unregister
  - Persistence schema_version "0.94.0" 独立 schema (跟 POMDPPolicy 0.93.0 / CognitiveTwinAgent 0.92.0 隔离)

本文件不直接执行, 仅作为 First-party Plugin Library 使用模板. 真集成请在 web/api/ 子模块中订阅.
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Any, Dict

from ecos.cta.event_log import LearningEvent
from ecos.event.bus import EventBus
from ecos.persistence.plugin_registry_store import PluginRegistryStore
from ecos.plugins.first_party import (
    HintFatiguePlugin,
    ParentEngagementPlugin,
    TeacherProgressPlugin,
)
from ecos.plugins.registry import (
    PluginRegistry,
    get_default_registry,
    reset_default_registry,
)

_log = logging.getLogger(__name__)


# ── Use Case 1: register_three_first_party ──────────────────────────────


def use_case_register_three_first_party() -> Dict[str, Any]:
    """Use Case 1: 注册 3 first-party plugin 到 default registry.

    Returns:
        dict 含 3 字段:
          - registered: List[str] 注册的 plugin name (sorted)
          - topics: Dict[str, List[str]] 各 plugin 订阅的 topic
          - metadata: Dict[str, Dict] 各 plugin metadata.to_dict() (version/description/subscribed_topics)
    """
    registry = get_default_registry()

    # 幂等: 已注册 skip (避免重复 register raise)
    if not registry.has("hint_fatigue"):
        registry.register(HintFatiguePlugin())
    if not registry.has("parent_engagement"):
        registry.register(ParentEngagementPlugin())
    if not registry.has("teacher_progress"):
        registry.register(TeacherProgressPlugin())

    return {
        "registered": registry.list_names(),
        "topics": {
            name: list(registry.get(name).get_subscribed_topics())
            for name in registry.list_names()
        },
        "metadata": {
            name: registry.get(name).metadata.to_dict()
            for name in registry.list_names()
        },
    }


# ── Use Case 2: enable_disable_lifecycle ────────────────────────────────


def use_case_enable_disable_lifecycle(student_id: str = "lbc001") -> Dict[str, Any]:
    """Use Case 2: HintFatiguePlugin enable/disable lifecycle 演示.

    流程:
      1. 注册 + enable HintFatiguePlugin
      2. emit 3 次 hint_requested → 计数 + 触发 threshold_exceeded (threshold=2)
      3. disable → 计数清零 (lifecycle 完整)

    Returns:
        dict 含 3 字段:
          - before_count: enable 后初始计数 (0)
          - after_count: 3 次 emit 后计数 (3)
          - disabled_count: disable 后计数 (0)
    """
    # 1) 准备 plugin + bus (隔离)
    plugin = HintFatiguePlugin(threshold=2)
    bus = EventBus()

    registry = PluginRegistry()
    registry.register(plugin)
    registry.subscribe_all(bus)

    plugin.enable()
    before_count = plugin.get_hint_count(student_id)

    # 2) emit 3 次 hint_requested (模拟学生答 3 题各请求 1 次 hint)
    for i in range(3):
        event = LearningEvent.from_hint_requested(
            student_id=student_id, problem_id=f"PB-Q{i:03d}",
        )
        result = plugin.on_event(event)
        _log.info(
            "HintFatiguePlugin lifecycle: hint #%d, result=%s",
            i + 1, result,
        )
    after_count = plugin.get_hint_count(student_id)

    # 3) disable → 计数清零
    registry.unsubscribe_all(bus)
    plugin.disable()
    disabled_count = plugin.get_hint_count(student_id)

    return {
        "before_count": before_count,
        "after_count": after_count,
        "disabled_count": disabled_count,
    }


# ── Use Case 3: hot_reload_from_db ──────────────────────────────────────


def use_case_hot_reload_from_db(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Use Case 3: 持久化到 DB + 从 DB 重建 (PluginRegistryStore + load_from_db).

    流程:
      1. 注册 3 first-party plugin 到 registry
      2. save_to_db(plugin_registry_store) → 持久化 metadata
      3. reset_default_registry() → 强制重建 singleton
      4. load_from_db(plugin_registry_store) → 从 DB 重建 registry
      5. 验证: 3 plugin 全部 recovered, metadata 跟 save 一致

    Args:
        db_path: 可选 DB path (默认用 temp file, 测试隔离).

    Returns:
        dict 含 4 字段:
          - saved_names: 持久化时的 plugin name list
          - loaded_names: 从 DB 重建后的 plugin name list
          - db_path: 实际 DB path
          - metadata_match: bool — save/load metadata 一致性校验
    """
    cleanup_needed = False
    if db_path is None:
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        cleanup_needed = True

    try:
        # 1) 注册 3 plugin (default registry)
        registry1 = get_default_registry()
        registry1.register(HintFatiguePlugin())
        registry1.register(ParentEngagementPlugin())
        registry1.register(TeacherProgressPlugin())
        saved_names = registry1.list_names()

        # 2) save_to_db
        store = PluginRegistryStore(db_path=db_path)
        registry1.save_to_db(store)
        store.close()

        # 3) reset singleton + 新 registry
        reset_default_registry()
        registry2 = get_default_registry()

        # 4) load_from_db
        store2 = PluginRegistryStore(db_path=db_path)
        loaded_names = registry2.load_from_db(store2)
        store2.close()

        # 5) metadata 一致性校验
        metadata_match = all(
            registry2.get(name).metadata.to_dict()
            == registry1.get(name).metadata.to_dict()
            for name in saved_names
        ) if set(saved_names) == set(loaded_names) else False

        return {
            "saved_names": saved_names,
            "loaded_names": loaded_names,
            "db_path": db_path,
            "metadata_match": metadata_match,
        }
    finally:
        if cleanup_needed and os.path.exists(db_path):
            os.unlink(db_path)


# ── Plugin Library Entry Point ──────────────────────────────────────────


def run_all_use_cases(db_path: Optional[str] = None) -> Dict[str, Any]:
    """运行 3 use case, 返汇总 dict (test/CLI entry)."""
    return {
        "register_three_first_party": use_case_register_three_first_party(),
        "enable_disable_lifecycle": use_case_enable_disable_lifecycle(),
        "hot_reload_from_db": use_case_hot_reload_from_db(db_path=db_path),
    }


# ── Module self-test (smoke test) ───────────────────────────────────────


def _self_test_imports() -> bool:
    """Verify all imports work (smoke test for docs/plugin_library.md §七 linkage).

    Returns:
        True if all imports succeed.
    """
    try:
        from ecos.plugins.first_party import (  # noqa: F401
            HintFatiguePlugin,
            ParentEngagementPlugin,
            TeacherProgressPlugin,
        )
        from ecos.plugins.registry import PluginRegistry, get_default_registry  # noqa: F401
        from ecos.persistence.plugin_registry_store import PluginRegistryStore  # noqa: F401
        from ecos.cta.event_log import LearningEvent  # noqa: F401
        from ecos.event.bus import EventBus  # noqa: F401
        return True
    except ImportError as e:
        _log.error("Plugin Library self-test failed: %s", e)
        return False


if __name__ == "__main__":
    import sys
    success = _self_test_imports()
    print(f"Plugin Library self-test: {'PASS' if success else 'FAIL'}")
    sys.exit(0 if success else 1)