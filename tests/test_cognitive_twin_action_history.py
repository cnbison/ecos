"""v0.92.0-a: Twin → Human Twin 第 4 维度 — ActionEntry + ActionHistory 数据结构测试.

对应设计: v0.92 design §v0.92.0-a.

测试范围 (12 tests):
  1. ActionEntry 创建 / frozen / to_dict / from_dict round-trip (3 tests)
  2. ActionHistory append + cap 500 + last_n + count_by_type + 5 action_type 校验 (3 tests)
  3. CognitiveTwinAgent 4-tuple access + append_action_history allowlisted (3 tests)
  4. 防御性 (schema_version 校验 + 越界 raise + reward range raise + frozen) (3 tests)
"""

from __future__ import annotations

import logging
from datetime import datetime

import pytest

from ecos.cta.belief_state import BeliefState
from ecos.cta.cognitive_twin import (
    ACTION_HISTORY_EVENT_TYPES,
    SCHEMA_VERSION,
    ActionEntry,
    ActionHistory,
    CognitiveTwinAgent,
    HumanFeedbackTrajectory,
)

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. ActionEntry 创建 / frozen / to_dict / from_dict round-trip (3 tests)
# ---------------------------------------------------------------------------


def test_action_entry_create_basic():
    """ActionEntry 基本创建: 5 字段 (student_id / timestamp / action_type + 3 可选)."""
    now = datetime(2026, 8, 12, 10, 0, 0)
    entry = ActionEntry(
        student_id="lbc001",
        timestamp=now,
        action_type="intervention_selected",
        intervention_id="iv_abc123",
        reward=0.75,
        metadata={"expected_gain": 0.3, "expected_risk": 0.1, "audience": "student", "policy_type": "linucb"},
    )
    assert entry.student_id == "lbc001"
    assert entry.timestamp == now
    assert entry.action_type == "intervention_selected"
    assert entry.intervention_id == "iv_abc123"
    assert entry.reward == 0.75
    assert entry.metadata["expected_gain"] == 0.3
    assert entry.source == "lca"  # default
    assert entry.schema_version == "0.92.0"  # default (CognitiveTwinAgent SCHEMA_VERSION 升级)


def test_action_entry_frozen_immutable():
    """ActionEntry frozen (跟 HumanFeedbackEntry v0.91.0-a + AlphaVector v0.89.0-a 同模式)."""
    entry = ActionEntry(
        student_id="lbc001",
        timestamp=datetime.now(),
        action_type="reward_recorded",
        reward=0.85,
    )
    # frozen dataclass: 直接赋值 raise FrozenInstanceError
    with pytest.raises((AttributeError, Exception)) as exc_info:
        entry.action_type = "policy_updated"  # type: ignore[misc]
    assert "frozen" in str(exc_info.value).lower() or "cannot assign" in str(exc_info.value).lower()


def test_action_entry_round_trip():
    """to_dict → from_dict round-trip: 字段一一对应, schema_version 校验通过."""
    original = ActionEntry(
        student_id="lbc002",
        timestamp=datetime(2026, 8, 12, 14, 30, 0),
        action_type="dual_agent_calibrated",
        intervention_id=None,  # dual_agent 无单一 intervention_id
        reward=0.92,
        metadata={"judge_1": "llm_critic", "judge_2": "human", "agreement": 0.92},
        source="dual_agent",
    )
    state = original.to_dict()
    restored = ActionEntry.from_dict(state)
    assert restored.student_id == original.student_id
    assert restored.timestamp == original.timestamp
    assert restored.action_type == original.action_type
    assert restored.intervention_id == original.intervention_id
    assert restored.reward == original.reward
    assert restored.metadata == original.metadata
    assert restored.source == original.source
    assert restored.schema_version == "0.92.0"


# ---------------------------------------------------------------------------
# 2. ActionHistory append + cap 500 + last_n + count_by_type + 5 action_type 校验 (3 tests)
# ---------------------------------------------------------------------------


def test_action_history_append_basic():
    """append 增量 + entries 按时间升序 + 5 action_type 全部可插入."""
    hist = ActionHistory()
    assert len(hist.entries) == 0
    e1 = ActionEntry(
        student_id="lbc001", timestamp=datetime(2026, 8, 12, 10, 0, 0),
        action_type="intervention_selected", intervention_id="iv_1",
    )
    e2 = ActionEntry(
        student_id="lbc001", timestamp=datetime(2026, 8, 12, 10, 5, 0),
        action_type="reward_recorded", intervention_id="iv_1", reward=0.85,
    )
    e3 = ActionEntry(
        student_id="lbc001", timestamp=datetime(2026, 8, 12, 10, 6, 0),
        action_type="dual_agent_calibrated", reward=0.92,
    )
    e4 = ActionEntry(
        student_id="lbc001", timestamp=datetime(2026, 8, 12, 10, 7, 0),
        action_type="policy_updated", metadata={"policy_type": "pomdp"},
    )
    e5 = ActionEntry(
        student_id="lbc001", timestamp=datetime(2026, 8, 12, 10, 8, 0),
        action_type="goal_changed", metadata={"old_goal_id": "G1", "new_goal_id": "G2"},
    )
    hist.append(e1)
    hist.append(e2)
    hist.append(e3)
    hist.append(e4)
    hist.append(e5)
    assert len(hist.entries) == 5
    assert hist.entries[0] == e1
    assert hist.entries[-1] == e5


def test_action_history_cap_500():
    """append 501 → 截断到最近 500 (跟 HumanFeedbackTrajectory maxlen 500 同 pattern)."""
    hist = ActionHistory(maxlen=500)
    base_time = datetime(2026, 8, 12, 10, 0, 0)
    for i in range(501):
        entry = ActionEntry(
            student_id="lbc001",
            timestamp=datetime(2026, 8, 12, 10, 0, i % 60),
            action_type="intervention_selected",
            intervention_id=f"iv_{i}",
        )
        hist.append(entry)
    assert len(hist.entries) == 500, f"cap 500 应截断到 500, got {len(hist.entries)}"
    # 验证保留的是最近 500 (即 entries[-1] 是第 500 个)
    last_entry = hist.entries[-1]
    assert last_entry.intervention_id == "iv_500"


def test_action_history_count_by_type_and_last_n():
    """count_by_type 统计各 action_type 出现次数 + last_n 返回最近 n 条."""
    hist = ActionHistory()
    # 10 intervention_selected + 5 reward_recorded + 3 dual_agent + 2 policy_updated + 1 goal_changed = 21
    for i in range(10):
        hist.append(ActionEntry(
            student_id="lbc001", timestamp=datetime.now(),
            action_type="intervention_selected", intervention_id=f"iv_{i}",
        ))
    for i in range(5):
        hist.append(ActionEntry(
            student_id="lbc001", timestamp=datetime.now(),
            action_type="reward_recorded", reward=0.5 + i * 0.1,
        ))
    for i in range(3):
        hist.append(ActionEntry(
            student_id="lbc001", timestamp=datetime.now(),
            action_type="dual_agent_calibrated", reward=0.8,
        ))
    for i in range(2):
        hist.append(ActionEntry(
            student_id="lbc001", timestamp=datetime.now(),
            action_type="policy_updated", metadata={"policy_type": "linucb"},
        ))
    hist.append(ActionEntry(
        student_id="lbc001", timestamp=datetime.now(),
        action_type="goal_changed", metadata={"old_goal_id": "G1", "new_goal_id": "G2"},
    ))
    assert hist.count_by_type("intervention_selected") == 10
    assert hist.count_by_type("reward_recorded") == 5
    assert hist.count_by_type("dual_agent_calibrated") == 3
    assert hist.count_by_type("policy_updated") == 2
    assert hist.count_by_type("goal_changed") == 1
    # last_n(3) 返回最近 3 条
    last3 = hist.last_n(3)
    assert len(last3) == 3
    # 顺序保持 (按 append 顺序, 最后 3 条)


# ---------------------------------------------------------------------------
# 3. CognitiveTwinAgent 4-tuple access + append_action_history allowlisted (3 tests)
# ---------------------------------------------------------------------------


def test_cognitive_twin_4tuple_default_empty():
    """CognitiveTwinAgent.from_state 默认 4-tuple 全空 (action_history 不再是 None 占位)."""
    state = BeliefState(student_id="lbc001")
    agent = CognitiveTwinAgent.from_state(state)
    assert agent.belief_state is state
    assert isinstance(agent.human_feedback, HumanFeedbackTrajectory)
    assert len(agent.human_feedback.entries) == 0
    # v0.92.0-a: action_history 是 ActionHistory 实例 (不再是 Optional[Dict]=None)
    assert isinstance(agent.action_history, ActionHistory)
    assert len(agent.action_history.entries) == 0
    assert agent.schema_version == "0.92.0"


def test_cognitive_twin_append_action_history_allowlisted():
    """CognitiveTwinAgent.append_action_history 走 allowlisted mutation (FUNC_ALLOWLIST).

    跟 append_human_feedback 完全同模式, 但 entry 是 ActionEntry (5 action_type).
    """
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
    # 多 action_type 混合
    agent.append_action_history(ActionEntry(
        student_id="lbc001", timestamp=datetime.now(),
        action_type="reward_recorded", intervention_id="iv_abc123", reward=0.85,
    ))
    assert agent.action_history.count_by_type("intervention_selected") == 1
    assert agent.action_history.count_by_type("reward_recorded") == 1


def test_cognitive_twin_dump_state_round_trip_with_action_history():
    """CognitiveTwinAgent.dump_state + load_state round-trip 含 action_history 4-tuple.

    v0.92.0-a 兑现占位: dump_state["action_history"] 从 None → ActionHistory.to_dict().
    """
    state = BeliefState(student_id="lbc001")
    agent_orig = CognitiveTwinAgent.from_state(state)
    # 添加 1 个 human_feedback + 2 个 action_history
    from ecos.cta.cognitive_twin import HumanFeedbackEntry
    agent_orig.append_human_feedback(HumanFeedbackEntry(
        student_id="lbc001", timestamp=datetime.now(),
        event_type="hint_requested", payload={"problem_id": "P1", "hint_level": 1},
    ))
    agent_orig.append_action_history(ActionEntry(
        student_id="lbc001", timestamp=datetime.now(),
        action_type="intervention_selected", intervention_id="iv_1",
    ))
    agent_orig.append_action_history(ActionEntry(
        student_id="lbc001", timestamp=datetime.now(),
        action_type="reward_recorded", intervention_id="iv_1", reward=0.85,
    ))
    # dump + load (新 state 模拟重启)
    state_restored = BeliefState(student_id="lbc001")
    agent_restored = CognitiveTwinAgent.load_state(
        agent_orig.dump_state(), state_restored,
    )
    assert len(agent_restored.human_feedback.entries) == 1
    assert len(agent_restored.action_history.entries) == 2
    assert agent_restored.action_history.count_by_type("intervention_selected") == 1
    assert agent_restored.action_history.count_by_type("reward_recorded") == 1
    assert agent_restored.schema_version == "0.92.0"


# ---------------------------------------------------------------------------
# 4. 防御性 (schema_version 校验 + 越界 raise + reward range raise + frozen) (3 tests)
# ---------------------------------------------------------------------------


def test_action_entry_invalid_action_type_raises():
    """action_type 不是 5 ACTION_HISTORY_EVENT_TYPES 之一 → raise ValueError (per 防御性自检 [1])."""
    with pytest.raises(ValueError, match="必须是 ACTION_HISTORY_EVENT_TYPES 之一"):
        ActionEntry(
            student_id="lbc001",
            timestamp=datetime.now(),
            action_type="invalid_action_type",  # 不是 5 值之一
        )


def test_action_entry_invalid_reward_range_raises():
    """reward 不在 [0, 1] → raise ValueError (per 防御性自检 [1])."""
    with pytest.raises(ValueError, match=r"reward 必须在 \[0, 1\]"):
        ActionEntry(
            student_id="lbc001",
            timestamp=datetime.now(),
            action_type="reward_recorded",
            reward=1.5,  # 超出 [0, 1]
        )
    with pytest.raises(ValueError, match=r"reward 必须在 \[0, 1\]"):
        ActionEntry(
            student_id="lbc001",
            timestamp=datetime.now(),
            action_type="reward_recorded",
            reward=-0.1,  # 负值
        )


def test_action_history_old_schema_version_raises():
    """ActionHistory.from_dict 老 schema_version → raise ValueError (per 防御性自检 [5]).

    同时覆盖 ActionEntry.from_dict 老 schema_version raise.
    """
    # 老 snapshot (含老 schema_version)
    old_state = {
        "entries": [],
        "maxlen": 500,
        "schema_version": "0.91.0",  # 老 v0.91.0 schema
    }
    with pytest.raises(ValueError, match=r"不支持的 schema_version"):
        ActionHistory.from_dict(old_state)
    # 老 v0.90.0 schema 也 raise
    old_state_90 = {
        "entries": [],
        "maxlen": 500,
        "schema_version": "0.90.0",
    }
    with pytest.raises(ValueError, match=r"不支持的 schema_version"):
        ActionHistory.from_dict(old_state_90)
    # None schema_version 也 raise
    with pytest.raises(ValueError, match=r"不支持的 schema_version"):
        ActionHistory.from_dict({})
    # ActionEntry.from_dict 也 raise
    old_entry = {
        "student_id": "lbc001",
        "timestamp": "2026-08-12T10:00:00",
        "action_type": "intervention_selected",
        "schema_version": "0.91.0",  # 老
    }
    with pytest.raises(ValueError, match=r"不支持的 schema_version"):
        ActionEntry.from_dict(old_entry)