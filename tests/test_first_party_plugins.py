"""Tests for ecos/plugins/first_party/ — 3 first-party plugin reference implementations (v0.94.0-c).

对应 12-kernel-mapping §6 Plugin SDK + Phase 7+ 抽象推演 #7.

10 tests covering:
    - HintFatiguePlugin: 计数 / 阈值告警 / lifecycle (3 tests)
    - ParentEngagementPlugin: evolution 解析 / state 变化 / lifecycle (3 tests)
    - TeacherProgressPlugin: coverage 冷启动 / current state / lifecycle (3 tests)
    - PluginRegistry.register 3 plugin + list_names sorted (1 test)
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Set

import numpy as np
import pytest

from ecos.cta.event_log import LearningEvent
from ecos.lca.l4_optimization.pomdp_diagnostic import (
    POMDPDiagnostic,
    RewardPosteriorSnapshot,
    SCHEMA_VERSION as POMDP_DIAG_SCHEMA,
    TransitionPosteriorSnapshot,
)
from ecos.plugins.base import Plugin, PluginMetadata
from ecos.plugins.first_party import (
    HINT_FATIGUE_THRESHOLD,
    COLD_START_COVERAGE_THRESHOLD,
    HintFatiguePlugin,
    ParentEngagementPlugin,
    TeacherProgressPlugin,
)
from ecos.plugins.registry import PluginRegistry, reset_default_registry


# ── Test helpers ──────────────────────────────────────────────────────


def _make_diagnostic(
    coverage_value: int = 10,
    most_likely_state: int = 0,
    evolution: Optional[list] = None,
) -> POMDPDiagnostic:
    """Construct a minimal POMDPDiagnostic for testing plugin handlers.

    Args:
        coverage_value: 填充 coverage 矩阵的统一值 (default 10 = 已冷启动完成).
        most_likely_state: belief argmax 索引 (0=Engaged, 1=Frustrated, 2=Bored, 3=Confused).
        evolution: optional evolution list (timed snapshots).
    """
    n_states, n_arms = 4, 3
    # T snapshot: shape (4, 4, 3) + count (4, 4, 3)
    mean_T = np.full((n_states, n_states, n_arms), 1.0 / n_states)
    count_T = np.full((n_states, n_states, n_arms), coverage_value, dtype=int)
    T_snapshot = TransitionPosteriorSnapshot(
        mean=mean_T, count=count_T, alpha0=1.0, schema_version=POMDP_DIAG_SCHEMA,
    )
    # R snapshot: shape (4, 3) + alpha/beta/variance
    alpha_R = np.full((n_states, n_arms), 5.0)
    beta_R = np.full((n_states, n_arms), 5.0)
    mean_R = alpha_R / (alpha_R + beta_R)
    variance_R = np.full((n_states, n_arms), 0.05)
    R_snapshot = RewardPosteriorSnapshot(
        mean=mean_R, alpha=alpha_R, beta=beta_R, alpha0=1.0,
        variance=variance_R, schema_version=POMDP_DIAG_SCHEMA,
    )
    # belief: argmax = most_likely_state
    belief = np.zeros(n_states)
    belief[most_likely_state] = 0.7
    for i in range(n_states):
        if i != most_likely_state:
            belief[i] = 0.1
    # coverage
    coverage = np.full((n_states, n_arms), coverage_value, dtype=int)
    # 构造 diagnostic, evolution 不在 POMDPDiagnostic 字段里, 在 dict 序列化时手动加
    diag = POMDPDiagnostic(
        T=T_snapshot, R=R_snapshot,
        belief=belief, coverage=coverage,
        most_likely_state=most_likely_state,
        last_updated=__import__("datetime").datetime.now(),
        schema_version=POMDP_DIAG_SCHEMA,
    )
    # 注入 evolution 到 to_dict 输出 (POMDPDiagnostic 是 frozen dataclass, evolution
    # 不在字段里, 而是在 LCAEngine dump_state 时附加到 diagnostic_dict['evolution'])
    # 这里直接通过 payload 注入, 不改 POMDPDiagnostic 本身
    return diag


@pytest.fixture(autouse=True)
def _reset_plugin_registry():
    """每个 test 自动 reset PluginRegistry singleton."""
    reset_default_registry()
    yield
    reset_default_registry()


# ──────────────────────────────────────────────────────────────────────
# HintFatiguePlugin (3 tests)
# ──────────────────────────────────────────────────────────────────────


def test_hint_fatigue_counts_and_triggers_warning_at_threshold():
    """HintFatiguePlugin 计数 hint_requested, 计数 > 阈值时 result 含 threshold_exceeded=True."""
    plugin = HintFatiguePlugin(threshold=2)
    plugin.enable()

    # 第 1 次: count=1, 未超阈值
    e1 = LearningEvent.from_hint_requested(student_id="lbc001", problem_id="PB-Q01")
    r1 = plugin.on_event(e1)
    assert r1["hint_count"] == 1
    assert r1["threshold_exceeded"] is False

    # 第 2 次: count=2, 未超阈值 (> 阈值才是 exceeded)
    e2 = LearningEvent.from_hint_requested(student_id="lbc001", problem_id="PB-Q01")
    r2 = plugin.on_event(e2)
    assert r2["hint_count"] == 2
    assert r2["threshold_exceeded"] is False

    # 第 3 次: count=3, 超阈值
    e3 = LearningEvent.from_hint_requested(student_id="lbc001", problem_id="PB-Q01")
    r3 = plugin.on_event(e3)
    assert r3["hint_count"] == 3
    assert r3["threshold_exceeded"] is True

    plugin.disable()


def test_hint_fatigue_per_student_isolation():
    """HintFatiguePlugin per-student 计数隔离: lbc001 计数不影响 lbc002."""
    plugin = HintFatiguePlugin(threshold=5)
    plugin.enable()

    # lbc001 计数 3 次
    for i in range(3):
        plugin.on_event(
            LearningEvent.from_hint_requested(student_id="lbc001", problem_id="PB-Q01")
        )
    # lbc002 计数 1 次
    plugin.on_event(
        LearningEvent.from_hint_requested(student_id="lbc002", problem_id="PB-Q01")
    )

    assert plugin.get_hint_count("lbc001") == 3
    assert plugin.get_hint_count("lbc002") == 1
    assert plugin.get_hint_count("not_seen") == 0  # 未出现返 0

    plugin.disable()


def test_hint_fatigue_enable_disable_clears_counts():
    """HintFatiguePlugin enable/disable 清零计数 (跟 enable 对称)."""
    plugin = HintFatiguePlugin(threshold=5)
    plugin.enable()
    plugin.on_event(LearningEvent.from_hint_requested(student_id="lbc001", problem_id="PB-Q01"))
    assert plugin.get_hint_count("lbc001") == 1

    plugin.disable()
    # disable 清零计数
    assert plugin.get_hint_count("lbc001") == 0

    plugin.enable()
    # re-enable 后计数仍 0
    assert plugin.get_hint_count("lbc001") == 0
    plugin.disable()


# ──────────────────────────────────────────────────────────────────────
# ParentEngagementPlugin (3 tests)
# ──────────────────────────────────────────────────────────────────────


def test_parent_engagement_reads_diagnostic_current_state():
    """ParentEngagementPlugin 读 POMDPDiagnostic 当前状态 (most_likely_state → 名字)."""
    plugin = ParentEngagementPlugin()
    plugin.enable()

    diagnostic = _make_diagnostic(most_likely_state=1)  # Frustrated
    diag_dict = diagnostic.to_dict()
    diag_dict["evolution"] = []  # evolution 是 PluginRuntime 注入的

    event = LearningEvent.from_pomdp_diagnostic_updated("lbc001", diag_dict)
    result = plugin.on_event(event)

    assert result is not None
    assert result["student_id"] == "lbc001"
    assert result["current_state"] == "Frustrated"
    assert result["current_state_index"] == 1
    assert result["evolution_count"] == 0

    plugin.disable()


def test_parent_engagement_reads_evolution_timed_snapshots():
    """ParentEngagementPlugin 读 POMDPDiagnostic.evolution (timed snapshots K=10)."""
    plugin = ParentEngagementPlugin()
    plugin.enable()

    diagnostic = _make_diagnostic(most_likely_state=0)  # Engaged
    diag_dict = diagnostic.to_dict()
    # evolution: 3 snapshot 状态序列 (0=Engaged, 2=Bored, 1=Frustrated)
    diag_dict["evolution"] = [
        {"most_likely_state": 0},
        {"most_likely_state": 2},
        {"most_likely_state": 1},
    ]

    event = LearningEvent.from_pomdp_diagnostic_updated("lbc001", diag_dict)
    result = plugin.on_event(event)

    assert result["recent_states"] == ["Engaged", "Bored", "Frustrated"]
    assert result["evolution_count"] == 3

    plugin.disable()


def test_parent_engagement_state_change_detection():
    """ParentEngagementPlugin 检测状态变化 (跟上一 snapshot 比)."""
    plugin = ParentEngagementPlugin()
    plugin.enable()

    # 第一次 emit: 状态 0 (Engaged), state_changed = False (无 prev)
    diag1 = _make_diagnostic(most_likely_state=0)
    diag1_dict = diag1.to_dict()
    diag1_dict["evolution"] = []
    e1 = LearningEvent.from_pomdp_diagnostic_updated("lbc001", diag1_dict)
    r1 = plugin.on_event(e1)
    assert r1["state_changed"] is False

    # 第二次 emit: 状态 1 (Frustrated), state_changed = True
    diag2 = _make_diagnostic(most_likely_state=1)
    diag2_dict = diag2.to_dict()
    diag2_dict["evolution"] = []
    e2 = LearningEvent.from_pomdp_diagnostic_updated("lbc001", diag2_dict)
    r2 = plugin.on_event(e2)
    assert r2["state_changed"] is True
    assert r2["current_state"] == "Frustrated"

    # 第三次 emit: 状态 1 (Frustrated), state_changed = False (跟上次同)
    diag3 = _make_diagnostic(most_likely_state=1)
    diag3_dict = diag3.to_dict()
    diag3_dict["evolution"] = []
    e3 = LearningEvent.from_pomdp_diagnostic_updated("lbc001", diag3_dict)
    r3 = plugin.on_event(e3)
    assert r3["state_changed"] is False

    plugin.disable()


# ──────────────────────────────────────────────────────────────────────
# TeacherProgressPlugin (3 tests)
# ──────────────────────────────────────────────────────────────────────


def test_teacher_progress_cold_start_detection_when_coverage_low():
    """TeacherProgressPlugin 冷启动判断: min(coverage) < 5 → cold_start=True."""
    plugin = TeacherProgressPlugin()
    plugin.enable()

    diagnostic = _make_diagnostic(coverage_value=3)  # 冷启动期
    diag_dict = diagnostic.to_dict()
    diag_dict["evolution"] = []

    event = LearningEvent.from_pomdp_diagnostic_updated("lbc001", diag_dict)
    result = plugin.on_event(event)

    assert result is not None
    assert result["min_coverage"] == 3
    assert result["cold_start"] is True
    assert "冷启动期" in result["advice"]

    plugin.disable()


def test_teacher_progress_warmed_up_when_coverage_above_threshold():
    """TeacherProgressPlugin min(coverage) >= 5 → cold_start=False, 已冷启动完成."""
    plugin = TeacherProgressPlugin()
    plugin.enable()

    diagnostic = _make_diagnostic(coverage_value=10)  # 已冷启动完成
    diag_dict = diagnostic.to_dict()
    diag_dict["evolution"] = []

    event = LearningEvent.from_pomdp_diagnostic_updated("lbc001", diag_dict)
    result = plugin.on_event(event)

    assert result["min_coverage"] == 10
    assert result["cold_start"] is False
    assert "已冷启动完成" in result["advice"]

    plugin.disable()


def test_teacher_progress_reads_most_likely_state_and_belief():
    """TeacherProgressPlugin 读 most_likely_state + belief 分布."""
    plugin = TeacherProgressPlugin()
    plugin.enable()

    diagnostic = _make_diagnostic(coverage_value=10, most_likely_state=2)  # Bored
    diag_dict = diagnostic.to_dict()
    diag_dict["evolution"] = []

    event = LearningEvent.from_pomdp_diagnostic_updated("lbc001", diag_dict)
    result = plugin.on_event(event)

    assert result["most_likely_state"] == "Bored"
    assert result["most_likely_state_index"] == 2
    # belief 是 list of floats (sum=1.0)
    assert abs(sum(result["belief"]) - 1.0) < 1e-6
    assert result["belief"][2] == pytest.approx(0.7)  # Bored 是 most_likely

    plugin.disable()


# ──────────────────────────────────────────────────────────────────────
# PluginRegistry.register 3 plugin + list_names sorted (1 test)
# ──────────────────────────────────────────────────────────────────────


def test_plugin_registry_register_all_three_first_party():
    """PluginRegistry.register 3 first-party plugin 后 list_names() 返 sorted 列表."""
    registry = PluginRegistry()
    registry.register(HintFatiguePlugin())
    registry.register(ParentEngagementPlugin())
    registry.register(TeacherProgressPlugin())

    names = registry.list_names()
    assert names == ["hint_fatigue", "parent_engagement", "teacher_progress"]

    # 验证 metadata 跟 schemas 一致
    assert registry.get("hint_fatigue").metadata.version == "1.0.0"
    assert registry.get("parent_engagement").metadata.subscribed_topics == ("pomdp_diagnostic_updated",)
    assert registry.get("teacher_progress").metadata.subscribed_topics == ("pomdp_diagnostic_updated",)

    # 验证 PluginRegistry.subscribe_all 调 enable + 返 sub_id dict
    from ecos.event.bus import EventBus
    bus = EventBus()
    sub_ids = registry.subscribe_all(bus)
    # 3 plugin × 各订阅 topic 数 (hint_fatigue=1, parent_engagement=1, teacher_progress=1)
    assert "hint_fatigue" in sub_ids
    assert len(sub_ids["hint_fatigue"]) == 1
    assert len(sub_ids["parent_engagement"]) == 1
    assert len(sub_ids["teacher_progress"]) == 1

    registry.unsubscribe_all(bus)