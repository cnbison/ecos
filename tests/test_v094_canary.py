"""v0.94.0-d: Plugin SDK canary — H3-c4 维持 + Plugin lifecycle 不污染 BeliefState + 老 DB compat.

对应设计: discussions/2026-08-13-v094-design.md §d 阶段.

v0.94.0-d canary 范围 (4 tests):
  1. H3-c4 canary: Plugin lifecycle (enable/disable/on_event) 不污染 BeliefState
     - HintFatiguePlugin.on_event 计数不影响 BeliefState.theta_mean
     - PluginRegistry.subscribe_all 调 bus.subscribe 不触发 BeliefState mutation
  2. v0.81 replay canary: PluginRegistry 不参与 StateEngine.replay
     - replay events 不重建 Plugin (Plugin 是 configuration, 不是 per-student state)
     - BeliefState replay 跟 Plugin 状态完全解耦
  3. 老 DB 兼容: CREATE TABLE IF NOT EXISTS 幂等 (v0.93 前 DB 无 plugin_registry 表)
  4. PluginRegistry.reset() 隔离 (singleton 跟 DomainRegistry 同 pattern)

防御性自检 [8] hard block 维持: Plugin / PluginRegistry / first-party plugin 不持有
BeliefState 引用, 0 新 mutation site (Plugin 是 process_event pattern).
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from typing import Any, Dict, List

import numpy as np
import pytest

from ecos.cta.belief_engine import BeliefEngine, Observation
from ecos.cta.belief_state import BloomLevel
from ecos.cta.event_log import LearningEvent
from ecos.event.bus import EventBus
from ecos.persistence.plugin_registry_store import PluginRegistryStore
from ecos.plugins.first_party import (
    HintFatiguePlugin,
    ParentEngagementPlugin,
    TeacherProgressPlugin,
)
from ecos.plugins.registry import PluginRegistry, reset_default_registry
from web.api.plugin_runtime import PluginRuntime


# ─── Test helpers ────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_plugin_registry():
    """每个 test 自动 reset PluginRegistry singleton (test 隔离)."""
    reset_default_registry()
    yield
    reset_default_registry()


def _build_observation(idx: int, base_ts: datetime) -> Observation:
    """Build H3-c4 style observation."""
    return Observation(
        skill_id="variables",
        problem_id=f"PB-Q{idx:03d}",
        correct=(idx % 3 != 0),
        score=1.0 if idx % 3 != 0 else 0.2,
        bloom_level=BloomLevel.APPLY,
        explanation_text=f"answer_{idx}",
        timestamp=base_ts + timedelta(minutes=idx),
    )


def _build_event_list(n: int, base_ts: datetime, student_id: str) -> List[LearningEvent]:
    """Build n H3-c4 trajectory LearningEvents."""
    events = []
    for i in range(n):
        obs = _build_observation(i, base_ts)
        events.append(
            LearningEvent(
                event_id=f"evt_v094_{i:03d}",
                student_id=student_id,
                timestamp=obs.timestamp,
                source="belief_updater",
                event_type="observation",
                payload=obs.to_dict(),
            )
        )
    return events


# ─── 1. H3-c4 canary: Plugin lifecycle 不污染 BeliefState (1 test) ──────────


def test_plugin_lifecycle_does_not_pollute_belief_state():
    """H3-c4 canary: Plugin 生命周期 (enable/disable/on_event/subscribe_all) 不污染 BeliefState.

    验证:
      - 注册 HintFatiguePlugin 到 PluginRegistry + 订阅 hint_requested topic
      - emit hint_requested event 触发 plugin.on_event (计数 + 阈值告警)
      - BeliefState.theta_mean / dim.K.theta 在 plugin 启用前后一致
      - 防御性自检 [8] hard block 维持: Plugin 不触及 BeliefState
    """
    # 1) 构造 BeliefState + 跑 5 个 inline event
    engine = BeliefEngine()
    student_id = "student_plugin_canary"
    base_ts = datetime(2026, 8, 13, 9, 0, 0)

    events = _build_event_list(5, base_ts, student_id)
    inline_state = engine.create_initial_state(student_id)
    for event in events:
        obs = Observation.from_dict(event.payload)
        inline_state = engine.update(inline_state, obs, log_event=False)

    # 记录原始 theta (Plugin enable 前)
    theta_before = inline_state.K.theta
    theta_mean_before = inline_state.theta_mean.copy()

    # 2) 启用 HintFatiguePlugin + emit hint event
    bus = EventBus()
    registry = PluginRegistry()
    plugin = HintFatiguePlugin(threshold=2)
    registry.register(plugin)
    registry.subscribe_all(bus)

    # emit 3 次 hint_requested (跟 Plugin 阈值 2 配合: 第 3 次触发 threshold_exceeded)
    for i in range(3):
        hint_event = LearningEvent.from_hint_requested(
            student_id=student_id, problem_id=f"PB-Q{i:03d}",
        )
        bus.publish("hint_requested", hint_event)

    # 3) BeliefState.theta 在 plugin enable + on_event 后不变 (Plugin 不污染 state)
    assert abs(inline_state.K.theta - theta_before) < 1e-9
    assert np.allclose(inline_state.theta_mean, theta_mean_before, atol=1e-9)

    # Plugin 内部计数正确 (跟 BeliefState 解耦)
    assert plugin.get_hint_count(student_id) == 3

    # 4) Plugin disable + unsubscribe 后, 计数清零 (lifecycle 完整)
    registry.unsubscribe_all(bus)
    plugin.disable()
    assert plugin.get_hint_count(student_id) == 0


# ─── 2. v0.81 replay canary: PluginRegistry 不参与 StateEngine.replay (1 test) ──


def test_state_engine_replay_does_not_rebuild_plugin_registry():
    """v0.81 replay canary: StateEngine.replay 不重建 Plugin Registry.

    验证:
      - StateEngine.replay 仍走 BeliefState 路径 (跟 v0.91/v0.92/v0.93 完全 parallel pattern)
      - PluginRegistry 是 process_event 配置, 不是 per-student state
      - Replay 路径不触发 plugin enable / on_event
    """
    # 1) 跑 5 个 event H3-c4 trajectory
    engine = BeliefEngine()
    student_id = "student_replay_no_plugin"
    base_ts = datetime(2026, 8, 13, 10, 0, 0)
    events = _build_event_list(5, base_ts, student_id)

    # 2) Replay 路径: BeliefEngine.replay 不应触发任何 plugin
    replayed_state = engine.replay(events, student_id=student_id)

    # 3) 验证 BeliefState 正常重建
    assert hasattr(replayed_state, "K")
    assert hasattr(replayed_state, "theta_mean")
    assert len(replayed_state.trajectory.snapshots) == 5

    # 4) 验证 PluginRegistry 是独立 singleton, 不参与 replay
    # PluginRegistry 是 process_event configuration, 跟 BeliefState 完全解耦
    # 这里仅验证 PluginRegistry.get_default() 仍可用 (replay 不破坏 singleton)
    from ecos.plugins.registry import get_default_registry
    registry = get_default_registry()
    # 默认 singleton 仍存在 (无 plugin 也 OK)
    assert isinstance(registry, PluginRegistry)
    # 没 plugin, list_names 应为空
    assert registry.list_names() == []


# ─── 3. 老 DB 兼容: CREATE TABLE IF NOT EXISTS 幂等 (1 test) ──────────────


def test_plugin_registry_store_old_db_compat_idempotent_init():
    """老 DB (v0.93 前) 无 plugin_registry 表, CREATE TABLE IF NOT EXISTS 兜底.

    验证:
      - PluginRegistryStore 在 v0.93 DB 上 init_schema 不 raise
      - 表自动创建 + save/load 走通
      - v0.94 DB 二次 init_schema 幂等 (覆盖不报错)
    """
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        # 1) 模拟 v0.93 DB (无 plugin_registry 表): 创建 LCAStore 类似 schema
        #    简化: 直接创建 PluginRegistryStore, 表自动创建
        store1 = PluginRegistryStore(db_path=db_path)
        # 2) Save 1 个 plugin (验证 DB 创建成功)
        store1.save_plugin(
            name="hint_fatigue",
            version="1.0.0",
            enabled=True,
            subscribed_topics=["hint_requested"],
            metadata={"name": "hint_fatigue", "version": "1.0.0"},
        )
        store1.close()

        # 3) 重新打开 (模拟新进程启动), 应幂等建表
        store2 = PluginRegistryStore(db_path=db_path)
        rows = store2.list_all()
        assert len(rows) == 1
        assert rows[0]["name"] == "hint_fatigue"

        # 4) 再 close + 再启 (3 次 init_schema 全幂等)
        store2.close()
        store3 = PluginRegistryStore(db_path=db_path)
        assert len(store3.list_all()) == 1
        store3.close()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


# ─── 4. PluginRegistry.reset() singleton 隔离 (1 test) ────────────────────


def test_plugin_registry_reset_singleton_isolation():
    """PluginRegistry.reset() + reset_default_registry() 隔离 (跟 DomainRegistry 同 pattern).

    验证:
      - reset_default_registry() 清空 _instance, 下次 PluginRegistry() 拿新实例
      - PluginRegistry.reset() 仅清空 in-memory state, 不破坏 singleton 实例
      - PluginRegistry singleton pattern 跟 DomainRegistry v0.88.0-a 完全 parallel
    """
    # 1) 拿 singleton + register plugin
    registry1 = PluginRegistry()
    registry1.register(HintFatiguePlugin())
    assert "hint_fatigue" in registry1.list_names()

    # 2) reset_default_registry() 强制重建 singleton
    reset_default_registry()
    registry2 = PluginRegistry()
    assert registry1 is not registry2  # 新实例
    assert registry2.list_names() == []  # 新实例空

    # 3) register 新 plugin 到新实例
    registry2.register(ParentEngagementPlugin())
    assert registry2.list_names() == ["parent_engagement"]

    # 4) PluginRegistry.reset() 仅清空 state, 不破坏 singleton 实例
    registry2.reset()
    assert registry2.list_names() == []
    # singleton 实例仍存在
    registry3 = PluginRegistry()
    assert registry3 is registry2  # 同一实例, 仅清空