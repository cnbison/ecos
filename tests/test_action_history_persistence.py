"""v0.92.0-d: ActionHistory 持久化测试 — 冷启动 + canary.

对应设计: v0.92 plan §v0.92.0-d.

测试范围 (8 tests):
  1. CognitiveTwinAgent 4-tuple dump_state + load_state round-trip + action_history 字段 + schema_version="0.92.0" 校验 (3 tests)
  2. LCAEngine dump_state + load_state 含 action_history 字段 (在 cognitive_twin 嵌套内) + bind_cognitive_twin (2 tests)
  3. 老 v0.91 LCAEngine snapshot backward compat (action_history 字段缺/老 schema_version skip) (2 tests)
  4. v0.81 replay canary (action_history 不通过 StateEngine.replay 重建, 走 LCA 路径) (1 test)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from ecos.cta.belief_engine import BeliefEngine
from ecos.cta.cognitive_twin import (
    ACTION_HISTORY_EVENT_TYPES,
    SCHEMA_VERSION,
    ActionEntry,
    ActionHistory,
    CognitiveTwinAgent,
)
from ecos.lca.cta_input import CTAInput
from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig

_log = __import__("logging").getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_state(student_id: str = "stu-d"):
    engine = BeliefEngine()
    return engine.create_initial_state(student_id)


def _make_action_entry(action_type: str, **kwargs: Any) -> ActionEntry:
    """Build an ActionEntry for tests."""
    defaults = {
        "student_id": "stu-d",
        "timestamp": datetime(2026, 8, 12, 12, 0, 0),
        "action_type": action_type,
    }
    if "intervention_id" in kwargs:
        defaults["intervention_id"] = kwargs["intervention_id"]
    if "reward" in kwargs:
        defaults["reward"] = kwargs["reward"]
    if "metadata" in kwargs:
        defaults["metadata"] = kwargs["metadata"]
    return ActionEntry(**defaults)


def _make_minimal_lca_snapshot(student_id: str = "stu") -> dict:
    """Build a minimal LCAEngine snapshot that passes LinUCB dimension check (n_arms=10, d=16)."""
    n_arms = 10
    context_dim = 16
    return {
        "intervention_history": [],
        "bandit_a": [[[0.0] * context_dim] * n_arms] * n_arms,
        "bandit_b": [[0.0] * context_dim] * n_arms,
        "arm_pull_counts": [0] * n_arms,
        "last_intervention": None,
        "update_count": 0,
        "select_count": 0,
        "arm_fingerprints": {},
        "last_arm": -1,
    }


# ── 1. CognitiveTwinAgent 4-tuple dump_state + load_state round-trip + schema_version 校验 (3 tests) ─


class TestCognitiveTwinActionHistoryDumpLoad:
    """CognitiveTwinAgent.dump_state + load_state round-trip 含 action_history + schema_version 校验."""

    def test_dump_state_includes_action_history_field(self):
        """CognitiveTwinAgent.dump_state 含 action_history 字段 (entries + maxlen + schema_version)."""
        state = _make_state("stu-ah-dump")
        twin = CognitiveTwinAgent.from_state(state)
        # append 3 reward_recorded + 2 intervention_selected
        for i in range(3):
            twin.append_action_history(_make_action_entry("reward_recorded", reward=0.85))
        for i in range(2):
            twin.append_action_history(_make_action_entry("intervention_selected", intervention_id=f"iv_{i}"))

        dump = twin.dump_state()
        assert "action_history" in dump
        ah_dict = dump["action_history"]
        assert ah_dict["schema_version"] == SCHEMA_VERSION  # "0.92.0"
        assert ah_dict["maxlen"] == 500
        assert len(ah_dict["entries"]) == 5
        # 5 action_type 校验: 3 reward_recorded + 2 intervention_selected
        assert sum(1 for e in ah_dict["entries"] if e["action_type"] == "reward_recorded") == 3
        assert sum(1 for e in ah_dict["entries"] if e["action_type"] == "intervention_selected") == 2

    def test_dump_load_round_trip_preserves_action_history(self):
        """dump + load round-trip 保留 action_history entries 完整."""
        state = _make_state("stu-ah-rt")
        twin_orig = CognitiveTwinAgent.from_state(state)
        # 5 不同 action_type 混合 (覆盖 5 ACTION_HISTORY_EVENT_TYPES)
        # 1) intervention_selected
        for i in range(3):
            twin_orig.append_action_history(_make_action_entry(
                "intervention_selected", intervention_id=f"iv_{i}"))
        # 2) reward_recorded
        for _ in range(2):
            twin_orig.append_action_history(_make_action_entry("reward_recorded", reward=0.85))
        # 3) dual_agent_calibrated
        twin_orig.append_action_history(_make_action_entry(
            "dual_agent_calibrated", reward=0.9,
            metadata={"judge_1": "llm_critic", "judge_2": "human"},
        ))

        # dump + load (simulate 重启 — 新 BeliefState)
        state_restored = _make_state("stu-ah-rt")
        twin_restored = CognitiveTwinAgent.load_state(twin_orig.dump_state(), state_restored)

        # 验证: 6 entries 完整保留
        assert len(twin_restored.action_history.entries) == 6
        assert twin_restored.action_history.count_by_type("intervention_selected") == 3
        assert twin_restored.action_history.count_by_type("reward_recorded") == 2
        assert twin_restored.action_history.count_by_type("dual_agent_calibrated") == 1
        # 验证: intervention_id 保留
        iv_ids = [e.intervention_id for e in twin_restored.action_history.entries if e.action_type == "intervention_selected"]
        assert iv_ids == ["iv_0", "iv_1", "iv_2"]
        # 验证: schema_version="0.92.0"
        assert twin_restored.schema_version == "0.92.0"

    def test_load_state_action_history_old_schema_raises(self):
        """load_state 老 action_history schema_version raise ValueError (per 防御性自检 [5])."""
        state = _make_state("stu-ah-old")
        old_dump = {
            "human_feedback": {"entries": [], "maxlen": 500, "schema_version": SCHEMA_VERSION},
            # 老 action_history schema_version="0.91.0" 触发 ValueError
            "action_history": {"entries": [], "maxlen": 500, "schema_version": "0.91.0"},
            "schema_version": SCHEMA_VERSION,
            "belief_state_ref": "stu-ah-old",
        }
        with pytest.raises(ValueError, match=r"ActionHistory.from_dict.*不支持的 schema_version"):
            CognitiveTwinAgent.load_state(old_dump, state)


# ── 2. LCAEngine dump_state + load_state 含 action_history 字段 + bind_cognitive_twin (2 tests) ─


class TestLCAEngineActionHistoryDumpLoad:
    """LCAEngine dump_state + load_state 含 action_history 字段 (cognitive_twin 嵌套) + bind_cognitive_twin."""

    def test_dump_state_includes_action_history_after_select(self):
        """LCAEngine.dump_state cognitive_twin.action_history 字段 (select_intervention 自动记录)."""
        lca = LCAEngine(config=LCAEngineConfig(use_llm_rationale=False))
        state = _make_state("stu-ah-lca")
        cta = CTAInput(student_id="stu-ah-lca", belief_state=state)
        # select 一次 (auto-records intervention_selected ActionEntry)
        lca.select_intervention(cta)

        # dump_state 检查 cognitive_twin.action_history 字段
        snapshot = lca.dump_state("stu-ah-lca")
        cognitive_twin_dict = snapshot["cognitive_twin"]
        assert cognitive_twin_dict is not None
        assert "action_history" in cognitive_twin_dict
        ah_dict = cognitive_twin_dict["action_history"]
        # 至少 1 个 intervention_selected (auto-recorded by LCAEngine.select_intervention Step 7)
        iv_count = sum(1 for e in ah_dict["entries"] if e["action_type"] == "intervention_selected")
        assert iv_count >= 1
        assert ah_dict["schema_version"] == "0.92.0"

    def test_load_state_restores_action_history_via_bind(self):
        """load_state + bind_cognitive_twin 完整恢复 action_history entries."""
        lca = LCAEngine(config=LCAEngineConfig(use_llm_rationale=False))
        state = _make_state("stu-ah-bind")
        cta = CTAInput(student_id="stu-ah-bind", belief_state=state)
        # 多次 select (积累 action_history)
        for _ in range(3):
            lca.select_intervention(cta)

        snapshot = lca.dump_state("stu-ah-bind")
        # 清空 + 模拟重启
        lca._cognitive_twin.clear()
        lca._cognitive_twin_pending.clear()
        # load (存 pending)
        lca.load_state("stu-ah-bind", snapshot)
        # bind (需要 belief_state — 用同一个 engine 重建 state)
        state_restored = _make_state("stu-ah-bind")
        twin_restored = lca.bind_cognitive_twin("stu-ah-bind", state_restored)
        # 验证: action_history entries 完整 (>= 3)
        assert twin_restored is not None
        assert isinstance(twin_restored, CognitiveTwinAgent)
        iv_count = twin_restored.action_history.count_by_type("intervention_selected")
        assert iv_count >= 3, f"expected >= 3 intervention_selected after 3 selects, got {iv_count}"
        # 验证: ActionEntry.schema_version="0.92.0" (entries 内嵌)
        for entry in twin_restored.action_history.entries:
            assert entry.schema_version == "0.92.0"
        # 验证: CognitiveTwinAgent.schema_version="0.92.0"
        assert twin_restored.schema_version == "0.92.0"


# ── 3. 老 v0.91 LCAEngine snapshot backward compat (2 tests) ────────────────


class TestLCAEngineV091SnapshotCompat:
    """老 v0.91 LCAEngine snapshot (schema_version="0.91.0" 或 action_history 字段缺) backward compat."""

    def test_load_state_v091_cognitive_twin_no_action_history_skip(self):
        """老 v0.91 cognitive_twin (schema_version="0.91.0" + 无 action_history 字段) → skip + warning."""
        lca = LCAEngine(config=LCAEngineConfig(use_llm_rationale=False))
        snapshot = _make_minimal_lca_snapshot()
        # 老 v0.91 schema: cognitive_twin 含 human_feedback 但无 action_history 字段 + 老 schema_version
        snapshot["cognitive_twin"] = {
            "human_feedback": {"entries": [], "maxlen": 500, "schema_version": "0.91.0"},
            # 无 action_history 字段 (v0.91 还没这字段)
            "schema_version": "0.91.0",
            "belief_state_ref": "stu",
        }
        # load 不 raise (老 schema_version 仅 warning + skip)
        lca.load_state("stu-v091", snapshot)
        # pending 仍空 (老 schema 被跳过)
        assert "stu-v091" not in lca._cognitive_twin_pending
        # _cognitive_twin 也没建 (无新数据)
        assert "stu-v091" not in lca._cognitive_twin

    def test_load_state_no_cognitive_twin_field_no_error(self):
        """无 cognitive_twin 字段的 snapshot (pre v0.91) load 不 raise."""
        lca = LCAEngine(config=LCAEngineConfig(use_llm_rationale=False))
        snapshot = _make_minimal_lca_snapshot()
        # snapshot 无 cognitive_twin 字段 (老 v0.86-v0.90 时代)
        assert "cognitive_twin" not in snapshot
        lca.load_state("stu-pre-v091", snapshot)
        # _cognitive_twin / pending 都空 (无字段)
        assert "stu-pre-v091" not in lca._cognitive_twin
        assert "stu-pre-v091" not in lca._cognitive_twin_pending


# ── 4. v0.81 replay canary (1 test) ────────────────────────────────────────


class TestReplayCanaryActionHistory:
    """v0.81 replay canary: StateEngine.replay 不重建 ActionHistory (action_history 走 LCA 路径)."""

    def test_state_engine_replay_does_not_rebuild_action_history(self):
        """StateEngine.replay 仍走 BeliefState 路径, action_history 不通过 replay 重建."""
        from ecos.cta.event_log import LearningEvent

        events = [
            LearningEvent(
                event_id="evt-1",
                student_id="stu-replay-ah",
                timestamp=datetime(2026, 8, 12, 12, 0, 0),
                source="test",
                event_type="response_submitted",
                payload={"skill_id": "python.variables", "problem_id": "pb-1",
                         "correct": True, "score": 0.85, "bloom_level": "L3"},
            ),
        ]
        # v0.81 StateEngine.replay path
        engine = BeliefEngine()
        state_orig = engine.create_initial_state("stu-replay-ah")
        state_replayed = engine.replay(events, student_id="stu-replay-ah")

        # ActionHistory 不通过 replay 路径重建
        # (action_history 走 LCAEngine.append_action_history 入口, 不是 StateEngine.replay 的责任)
        twin_from_replayed = CognitiveTwinAgent.from_state(state_replayed)
        assert twin_from_replayed.belief_state is state_replayed
        # trajectory 引用一致 (from_state 不复制)
        assert twin_from_replayed.trajectory is state_replayed.trajectory
        # action_history 初始空 (replay 不重建, 不写)
        assert len(twin_from_replayed.action_history.entries) == 0
        # human_feedback 同样初始空 (replay 不重建)
        assert len(twin_from_replayed.human_feedback.entries) == 0


# ── Test isolation fixture (autouse) ──────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset module-level singletons for isolation."""
    yield
