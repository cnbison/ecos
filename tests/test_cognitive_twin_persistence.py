"""v0.91.0-d: 冷启动 + 持久化 + canary 测试.

对应设计: discussions/2026-08-12-v091-design.md §3.

测试范围 (8 tests):
  1. dump_state + load_state round-trip + schema_version 校验 (3 tests)
  2. LCAEngine dump_state + load_state 含 cognitive_twin 字段 (2 tests)
  3. 老 v0.90 LCAEngine snapshot raise (per 防御性自检 [5]) (2 tests)
  4. v0.81 replay canary (cognitive_twin 走 LCA 路径, StateEngine.replay 不重建) (1 test)
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from typing import Any

import pytest

from ecos.cta.belief_engine import BeliefEngine
from ecos.cta.cognitive_twin import (
    SCHEMA_VERSION,
    CognitiveTwinAgent,
    HumanFeedbackEntry,
    HumanFeedbackTrajectory,
)
from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig
from ecos.persistence.db import Database, DatabaseConfig


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_entry(event_type: str, student_id: str = "stu-d", payload: dict = None) -> HumanFeedbackEntry:
    """Build a HumanFeedbackEntry for tests."""
    return HumanFeedbackEntry(
        student_id=student_id,
        timestamp=datetime(2026, 8, 12, 12, 0, 0),
        event_type=event_type,
        payload=payload or {"dummy": "x"},
        source="test_persistence",
    )


def _make_twin_with_feedback(counts: dict, student_id: str = "stu-d") -> CognitiveTwinAgent:
    """Build a CognitiveTwinAgent with N entries of each event_type."""
    engine = BeliefEngine()
    state = engine.create_initial_state(student_id)
    twin = CognitiveTwinAgent.from_state(state)
    for event_type, count in counts.items():
        for i in range(count):
            twin.append_human_feedback(_make_entry(event_type, student_id))
    return twin


# ── 1. CognitiveTwinAgent dump_state + load_state round-trip + schema_version 校验 (3 tests) ─


class TestCognitiveTwinDumpLoad:
    """CognitiveTwinAgent.dump_state + load_state round-trip + schema_version 校验."""

    def test_dump_load_round_trip_preserves_entries(self):
        """dump_state + load_state round-trip 保留 entries."""
        engine = BeliefEngine()
        state = engine.create_initial_state("stu-rt")
        twin_orig = CognitiveTwinAgent.from_state(state)
        # 5 entries (mixed)
        for event_type, count in [
            ("hint_requested", 3),
            ("idle_detected", 2),
        ]:
            for _ in range(count):
                twin_orig.append_human_feedback(_make_entry(event_type, "stu-rt"))

        # dump + load (load 需传入 belief_state)
        state_restored = engine.create_initial_state("stu-rt")  # 新 state 模拟重启
        twin_restored = CognitiveTwinAgent.load_state(
            twin_orig.dump_state(), state_restored,
        )
        assert len(twin_restored.human_feedback.entries) == 5
        assert twin_restored.human_feedback.count_by_type("hint_requested") == 3
        assert twin_restored.human_feedback.count_by_type("idle_detected") == 2
        assert twin_restored.schema_version == SCHEMA_VERSION

    def test_load_state_raises_on_old_schema_version(self):
        """load_state 老 schema_version raise ValueError (per 防御性自检 [5])."""
        engine = BeliefEngine()
        state = engine.create_initial_state("stu-old")
        old_state = {
            "human_feedback": {"entries": [], "maxlen": 500, "schema_version": "0.90.0"},
            "action_history": None,
            "schema_version": "0.90.0",
            "belief_state_ref": "stu-old",
        }
        with pytest.raises(ValueError, match=r"不支持的 schema_version"):
            CognitiveTwinAgent.load_state(old_state, state)

    def test_dump_state_includes_schema_version_field(self):
        """dump_state 含 schema_version 字段 (LCAEngine.load_state 校验依赖)."""
        engine = BeliefEngine()
        state = engine.create_initial_state("stu-sv")
        twin = CognitiveTwinAgent.from_state(state)
        dump = twin.dump_state()
        assert dump["schema_version"] == "0.91.0"
        assert dump["belief_state_ref"] == "stu-sv"
        assert dump["human_feedback"]["schema_version"] == "0.91.0"
        assert dump["action_history"] is None  # v0.92+ 占位


# ── 2. LCAEngine dump_state + load_state 含 cognitive_twin 字段 (2 tests) ─


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


class TestLCAEngineDumpLoadCognitiveTwin:
    """LCAEngine.dump_state + load_state 含 cognitive_twin 字段 + bind_cognitive_twin."""

    def test_dump_state_includes_cognitive_twin_field(self):
        """dump_state 含 cognitive_twin 字段 (Twin → Human Twin 抽象)."""
        lca = LCAEngine(config=LCAEngineConfig(use_llm_rationale=False))
        engine = BeliefEngine()
        state = engine.create_initial_state("stu-lca-dump")
        twin = _make_twin_with_feedback({"hint_requested": 6, "idle_detected": 4}, student_id="stu-lca-dump")
        # 先 append 1 个 entry 让 dict 初始化 (然后重新覆盖)
        lca.append_human_feedback("stu-lca-dump", _make_entry("hint_requested"), state=state)
        # 直接覆盖 _cognitive_twin 为我们构造的 (含 10 entries)
        lca._cognitive_twin["stu-lca-dump"] = twin

        snapshot = lca.dump_state("stu-lca-dump")
        assert "cognitive_twin" in snapshot
        assert snapshot["cognitive_twin"] is not None
        assert snapshot["cognitive_twin"]["schema_version"] == "0.91.0"
        assert snapshot["cognitive_twin"]["belief_state_ref"] == "stu-lca-dump"

    def test_load_state_restores_cognitive_twin_via_bind(self):
        """load_state + bind_cognitive_twin 完整恢复 CognitiveTwinAgent."""
        lca = LCAEngine(config=LCAEngineConfig(use_llm_rationale=False))
        engine = BeliefEngine()
        state = engine.create_initial_state("stu-lca-rt")
        twin = _make_twin_with_feedback({"hint_requested": 6})
        # 写入 _cognitive_twin
        lca._cognitive_twin["stu-lca-rt"] = twin
        snapshot = lca.dump_state("stu-lca-rt")
        # 清空 + 模拟重启
        lca._cognitive_twin.clear()
        lca._cognitive_twin_pending.clear()
        assert "stu-lca-rt" not in lca._cognitive_twin
        # load (存 pending)
        lca.load_state("stu-lca-rt", snapshot)
        # bind (需要 belief_state — 用同一个 engine 重建 state)
        state_restored = engine.create_initial_state("stu-lca-rt")
        twin_restored = lca.bind_cognitive_twin("stu-lca-rt", state_restored)
        # 验证
        assert twin_restored is not None
        assert isinstance(twin_restored, CognitiveTwinAgent)
        assert twin_restored.human_feedback.count_by_type("hint_requested") == 6
        assert lca._cognitive_twin["stu-lca-rt"] is twin_restored


# ── 3. 老 v0.90 LCAEngine snapshot raise per 防御性自检 [5] (2 tests) ────


class TestLCAEngineOldSnapshotCompat:
    """老 v0.90 LCAEngine snapshot (无 cognitive_twin 字段) backward compat."""

    def test_load_state_no_cognitive_twin_field_no_error(self):
        """老 v0.90 snapshot (无 cognitive_twin 字段) load 不 raise, skip 字段."""
        lca = LCAEngine(config=LCAEngineConfig(use_llm_rationale=False))
        # 构造 v0.90 snapshot (无 cognitive_twin 字段)
        old_snapshot = _make_minimal_lca_snapshot()
        # load 不应 raise (缺字段 graceful skip)
        lca.load_state("stu-old", old_snapshot)
        # _cognitive_twin dict 仍空 (无字段)
        assert "stu-old" not in lca._cognitive_twin

    def test_load_state_cognitive_twin_old_schema_version_skip(self):
        """cognitive_twin schema_version 不匹配 → skip + warning (不 raise)."""
        lca = LCAEngine(config=LCAEngineConfig(use_llm_rationale=False))
        snapshot = _make_minimal_lca_snapshot()
        snapshot["cognitive_twin"] = {
            "human_feedback": {"entries": [], "maxlen": 500, "schema_version": "0.90.0"},
            "action_history": None,
            "schema_version": "0.90.0",  # 老 schema
            "belief_state_ref": "stu",
        }
        # load 不 raise (LCAEngine.load_state 老 schema_version 仅 warning + skip)
        lca.load_state("stu-old2", snapshot)
        # pending 仍空 (老 schema 被跳过)
        assert "stu-old2" not in lca._cognitive_twin_pending


# ── 4. v0.81 replay canary (1 test) ───────────────────────────────────────


class TestReplayCanaryCognitiveTwin:
    """v0.81 replay canary: StateEngine.replay 不重建 CognitiveTwinAgent (cognitive_twin 走 LCA 路径)."""

    def test_state_engine_replay_does_not_rebuild_cognitive_twin(self):
        """StateEngine.replay 仍走 BeliefState 路径, 不动 CognitiveTwinAgent."""
        from ecos.cta.event_log import LearningEvent

        # Build events
        events = [
            LearningEvent(
                event_id="evt-1",
                student_id="stu-replay",
                timestamp=datetime(2026, 8, 12, 12, 0, 0),
                source="test",
                event_type="response_submitted",
                payload={"skill_id": "python.variables", "problem_id": "pb-1",
                         "correct": True, "score": 0.85, "bloom_level": "L3"},
            ),
        ]

        # v0.81 StateEngine.replay path
        engine = BeliefEngine()
        state_orig = engine.create_initial_state("stu-replay")
        state_replayed = engine.replay(events, student_id="stu-replay")

        # CognitiveTwinAgent 不通过 replay 路径重建
        # (CognitiveTwinAgent.from_state() 是 LCAEngine.append_human_feedback 入口,
        #  不是 StateEngine.replay 的责任)
        twin_from_replayed = CognitiveTwinAgent.from_state(state_replayed)
        assert twin_from_replayed.belief_state is state_replayed
        # trajectory 引用一致 (from_state 不复制)
        assert twin_from_replayed.trajectory is state_replayed.trajectory
        # human_feedback 初始空 (replay 不重建, 不写)
        assert len(twin_from_replayed.human_feedback.entries) == 0


# ── Test isolation fixture (autouse) ──────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset module-level singletons for isolation."""
    yield