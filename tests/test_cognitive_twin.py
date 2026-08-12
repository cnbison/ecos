"""v0.91.0-a (3-tuple) → v0.92.0-a (4-tuple): Twin → Human Twin 抽象 — CognitiveTwinAgent 数据结构测试.

对应设计: discussions/2026-08-12-v091-design.md §2.

测试范围:
  1. HumanFeedbackEntry 创建 / frozen / to_dict / from_dict round-trip (3 tests)
  2. HumanFeedbackTrajectory append + cap 500 + last_n + count_by_type (3 tests)
  3. CognitiveTwinAgent.from_state + 4-tuple access + action_history ActionHistory (3 tests)
  4. 防御性 (schema_version 校验 + 越界 raise + frozen raise on assignment) (3 tests)
"""

from __future__ import annotations

import logging
from datetime import datetime

import pytest

from ecos.cta.belief_state import BeliefState
from ecos.cta.cognitive_twin import (
    HUMAN_FEEDBACK_EVENT_TYPES,
    SCHEMA_VERSION,
    ActionHistory,
    CognitiveTwinAgent,
    HumanFeedbackEntry,
    HumanFeedbackTrajectory,
)

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. HumanFeedbackEntry 创建 / frozen / to_dict / from_dict round-trip (3 tests)
# ---------------------------------------------------------------------------


def test_human_feedback_entry_create_basic():
    """HumanFeedbackEntry 基本创建: 4 字段 (student_id / timestamp / event_type / payload)."""
    now = datetime(2026, 8, 12, 10, 0, 0)
    entry = HumanFeedbackEntry(
        student_id="lbc001",
        timestamp=now,
        event_type="hint_requested",
        payload={"problem_id": "PB-Q18", "hint_level": 1},
    )
    assert entry.student_id == "lbc001"
    assert entry.timestamp == now
    assert entry.event_type == "hint_requested"
    assert entry.payload == {"problem_id": "PB-Q18", "hint_level": 1}
    assert entry.source == "plugin"  # default
    assert entry.schema_version == "0.92.0"  # default (CognitiveTwinAgent SCHEMA_VERSION 升级 v0.92.0-a)


def test_human_feedback_entry_frozen_immutable():
    """HumanFeedbackEntry frozen (跟 AlphaVector v0.89.0-a 同模式): 外部 mutation raise."""
    entry = HumanFeedbackEntry(
        student_id="lbc001",
        timestamp=datetime.now(),
        event_type="idle_detected",
        payload={"idle_seconds": 30.0},
    )
    # frozen dataclass: 直接赋值 raise FrozenInstanceError (dataclasses.FrozenInstanceError)
    with pytest.raises((AttributeError, Exception)) as exc_info:
        entry.event_type = "goal_changed"  # type: ignore[misc]
    assert "frozen" in str(exc_info.value).lower() or "cannot assign" in str(exc_info.value).lower()


def test_human_feedback_entry_round_trip():
    """to_dict → from_dict round-trip: 字段一一对应, schema_version 校验通过."""
    original = HumanFeedbackEntry(
        student_id="lbc002",
        timestamp=datetime(2026, 8, 12, 14, 30, 0),
        event_type="reflection_completed",
        payload={"reflection_text": "今天学了 variables", "problem_id": "PB-Q20"},
        source="frontend_reflection",
    )
    state = original.to_dict()
    restored = HumanFeedbackEntry.from_dict(state)
    assert restored.student_id == original.student_id
    assert restored.timestamp == original.timestamp
    assert restored.event_type == original.event_type
    assert restored.payload == original.payload
    assert restored.source == original.source
    assert restored.schema_version == "0.92.0"


# ---------------------------------------------------------------------------
# 2. HumanFeedbackTrajectory append + cap 500 + last_n + count_by_type (3 tests)
# ---------------------------------------------------------------------------


def test_human_feedback_trajectory_append_basic():
    """append 增量 + entries 按时间升序."""
    traj = HumanFeedbackTrajectory()
    assert len(traj.entries) == 0
    e1 = HumanFeedbackEntry(
        student_id="lbc001", timestamp=datetime(2026, 8, 12, 10, 0, 0),
        event_type="hint_requested", payload={"problem_id": "PB-Q1", "hint_level": 1},
    )
    e2 = HumanFeedbackEntry(
        student_id="lbc001", timestamp=datetime(2026, 8, 12, 10, 5, 0),
        event_type="idle_detected", payload={"idle_seconds": 15.0},
    )
    traj.append(e1)
    traj.append(e2)
    assert len(traj.entries) == 2
    assert traj.entries[0] == e1
    assert traj.entries[1] == e2


def test_human_feedback_trajectory_cap_500():
    """append 501 → 截断到最近 500 (跟 TrajectoryState maxlen 500 同 pattern, per belief_engine.py:167)."""
    traj = HumanFeedbackTrajectory(maxlen=500)
    # 构造 501 个 entry
    base_time = datetime(2026, 8, 12, 10, 0, 0)
    for i in range(501):
        entry = HumanFeedbackEntry(
            student_id="lbc001",
            timestamp=datetime(2026, 8, 12, 10, 0, i % 60),  # 简化时间
            event_type="hint_requested",
            payload={"problem_id": f"PB-Q{i}", "hint_level": 1},
        )
        traj.append(entry)
    assert len(traj.entries) == 500, f"cap 500 应截断到 500, got {len(traj.entries)}"
    # 验证保留的是最近 500 (即 entries[-1] 是第 500 个)
    last_entry = traj.entries[-1]
    assert last_entry.payload["problem_id"] == "PB-Q500"


def test_human_feedback_trajectory_count_by_type():
    """count_by_type 统计各 event_type 出现次数 (c 阶段 ExperimentDesigner 用)."""
    traj = HumanFeedbackTrajectory()
    # 6 hint + 4 idle + 2 reflection + 1 goal_change
    for i in range(6):
        traj.append(HumanFeedbackEntry(
            student_id="lbc001", timestamp=datetime.now(),
            event_type="hint_requested", payload={"problem_id": f"P{i}", "hint_level": 1},
        ))
    for i in range(4):
        traj.append(HumanFeedbackEntry(
            student_id="lbc001", timestamp=datetime.now(),
            event_type="idle_detected", payload={"idle_seconds": 10.0 + i},
        ))
    for i in range(2):
        traj.append(HumanFeedbackEntry(
            student_id="lbc001", timestamp=datetime.now(),
            event_type="reflection_completed", payload={"reflection_text": f"r{i}", "problem_id": "P1"},
        ))
    traj.append(HumanFeedbackEntry(
        student_id="lbc001", timestamp=datetime.now(),
        event_type="goal_changed", payload={"old_goal_id": "G1", "new_goal_id": "G2"},
    ))
    assert traj.count_by_type("hint_requested") == 6
    assert traj.count_by_type("idle_detected") == 4
    assert traj.count_by_type("reflection_completed") == 2
    assert traj.count_by_type("goal_changed") == 1
    assert traj.count_by_type("hint_requested") + traj.count_by_type("idle_detected") \
        + traj.count_by_type("reflection_completed") + traj.count_by_type("goal_changed") \
        == len(traj.entries)


# ---------------------------------------------------------------------------
# 3. CognitiveTwinAgent.from_state + 4-tuple access + action_history ActionHistory (3 tests)
# ---------------------------------------------------------------------------


def test_cognitive_twin_agent_from_state_basic():
    """from_state 静态方法: 从 BeliefState 派生 4-tuple (单一入口, v0.92.0-a 升级)."""
    state = BeliefState(student_id="lbc001")
    agent = CognitiveTwinAgent.from_state(state)
    assert agent.belief_state is state  # 同引用, 不复制
    assert agent.trajectory is state.trajectory  # 同一 TrajectoryState
    assert isinstance(agent.human_feedback, HumanFeedbackTrajectory)
    assert len(agent.human_feedback.entries) == 0  # 初始空
    assert isinstance(agent.action_history, ActionHistory)  # v0.92.0-a: 升级为 ActionHistory 实例
    assert len(agent.action_history.entries) == 0  # 初始空
    assert agent.schema_version == "0.92.0"


def test_cognitive_twin_agent_4tuple_access():
    """4-tuple 字段访问: belief_state / trajectory / human_feedback / action_history."""
    state = BeliefState(student_id="lbc001")
    agent = CognitiveTwinAgent.from_state(state)
    # belief_state 访问
    assert agent.belief_state.student_id == "lbc001"
    # trajectory 訪問 (BeliefState 已內嵌)
    assert isinstance(agent.trajectory.snapshots, list)
    # human_feedback 訪問 (entries list 初始空)
    assert len(agent.human_feedback.entries) == 0
    # action_history 訪問 (entries list 初始空)
    assert len(agent.action_history.entries) == 0
    # append_human_feedback 走 allowlisted mutation (FUNC_ALLOWLIST += "append_human_feedback")
    entry = HumanFeedbackEntry(
        student_id="lbc001", timestamp=datetime.now(),
        event_type="hint_requested", payload={"problem_id": "P1", "hint_level": 1},
    )
    agent.append_human_feedback(entry)
    assert len(agent.human_feedback.entries) == 1
    assert agent.human_feedback.entries[0] == entry


def test_cognitive_twin_agent_append_action_history():
    """v0.92.0-a: append_action_history 走 allowlisted mutation (FUNC_ALLOWLIST += "append_action_history").

    跟 append_human_feedback 完全同模式, 但 entry 是 ActionEntry (5 action_type).
    """
    from ecos.cta.cognitive_twin import ActionEntry
    state = BeliefState(student_id="lbc001")
    agent = CognitiveTwinAgent.from_state(state)
    # 初始 ActionHistory 空
    assert len(agent.action_history.entries) == 0
    # append_action_history 走 allowlisted mutation
    action_entry = ActionEntry(
        student_id="lbc001",
        timestamp=datetime.now(),
        action_type="intervention_selected",
        intervention_id="iv_abc123",
        reward=0.75,
        metadata={"expected_gain": 0.3, "policy_type": "linucb"},
    )
    agent.append_action_history(action_entry)
    assert len(agent.action_history.entries) == 1
    assert agent.action_history.entries[0] == action_entry
    # count_by_type 验证
    assert agent.action_history.count_by_type("intervention_selected") == 1
    assert agent.action_history.count_by_type("reward_recorded") == 0


# ---------------------------------------------------------------------------
# 4. 防御性 (schema_version 校验 + 越界 raise + frozen raise on assignment) (3 tests)
# ---------------------------------------------------------------------------


def test_human_feedback_entry_invalid_event_type_raises():
    """event_type 不是 4 HUMAN_FEEDBACK_EVENT_TYPES 之一 → raise ValueError (per 防御性自检 [1])."""
    with pytest.raises(ValueError, match="必须是 HUMAN_FEEDBACK_EVENT_TYPES 之一"):
        HumanFeedbackEntry(
            student_id="lbc001",
            timestamp=datetime.now(),
            event_type="invalid_type",  # 不是 4 值之一
            payload={},
        )


def test_human_feedback_trajectory_invalid_count_by_type_raises():
    """count_by_type 传入非法 event_type → raise ValueError (per 防御性自检 [1])."""
    traj = HumanFeedbackTrajectory()
    with pytest.raises(ValueError, match="必须是 HUMAN_FEEDBACK_EVENT_TYPES 之一"):
        traj.count_by_type("invalid_type")


def test_cognitive_twin_agent_invalid_schema_version_raises():
    """CognitiveTwinAgent.schema_version != "0.92.0" → raise ValueError (per 防御性自检 [5])."""
    state = BeliefState(student_id="lbc001")
    with pytest.raises(ValueError, match="schema_version 必须是"):
        CognitiveTwinAgent(
            belief_state=state,
            trajectory=state.trajectory,
            schema_version="0.91.0",  # 老 v0.91.0 snapshot, 应 raise
        )