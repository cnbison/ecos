"""v0.92.0-b: Runtime + LCAEngine append_action_history 接入测试.

对应设计: v0.92 plan §v0.92.0-b.

测试范围 (15 tests):
  1. LCAEngine select_intervention 自动记录 intervention_selected action (4 tests)
  2. LCAEngine update 自动记录 reward_recorded action (3 tests)
  3. Runtime.plan_action_aware kwargs 透传 + 第 7 plan API (3 tests)
  4. LCAEngine.append_action_history lazy init CognitiveTwinAgent from state (3 tests)
  5. POMDPPolicy 老 v0.91.0 / v0.92.0-a 之前 snapshot raise (防御性自检 [5]) (2 tests)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pytest

from ecos.cta.belief_engine import BeliefEngine, BeliefState
from ecos.cta.cognitive_twin import (
    ACTION_HISTORY_EVENT_TYPES,
    ActionEntry,
    CognitiveTwinAgent,
)
from ecos.lca.cta_input import CTAInput
from ecos.lca.l4_optimization.pomdp import POMDPPolicy, SCHEMA_VERSION
from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig

_log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_state(student_id: str = "stu-001") -> BeliefState:
    """Build a BeliefState via BeliefEngine (跟 v0.83+ 4-layer 一致)."""
    engine = BeliefEngine()
    state = engine.create_initial_state(student_id)
    return state


def _make_lca_engine() -> LCAEngine:
    """Build LCAEngine for tests (无 LLM rationale)."""
    return LCAEngine(config=LCAEngineConfig(use_llm_rationale=False))


def _make_lca_engine_with_state(student_id: str = "stu-001"):
    """Build LCAEngine + pre-allocated BeliefState for tests."""
    lca = _make_lca_engine()
    state = _make_state(student_id)
    return lca, state


# ── 1. LCAEngine select_intervention 自动记录 intervention_selected action (4 tests) ─


class TestSelectInterventionAutoRecord:
    """LCAEngine.select_intervention 自动记录 intervention_selected ActionEntry (v0.92.0-b)."""

    def test_select_intervention_records_intervention_selected(self):
        """select_intervention Step 7 自动构造 ActionEntry(intervention_selected) 并 append."""
        lca, state = _make_lca_engine_with_state()
        cta = CTAInput(student_id="stu-sel-1", belief_state=state)
        result = lca.select_intervention(cta)

        # _cognitive_twin 已 lazy init (append_action_history 触发)
        assert "stu-sel-1" in lca._cognitive_twin
        twin = lca._cognitive_twin["stu-sel-1"]

        # action_history 已记录 1 条 intervention_selected
        assert twin.action_history.count_by_type("intervention_selected") == 1
        entries = twin.action_history.entries
        assert len(entries) == 1
        entry = entries[0]
        assert entry.action_type == "intervention_selected"
        assert entry.intervention_id == result.intervention.intervention_id
        assert entry.source == "lca"
        assert entry.schema_version == "0.92.0"  # ActionEntry 是 CognitiveTwinAgent 子组件, 仍 v0.92.0 schema (独立于 POMDPPolicy SCHEMA_VERSION="0.93.0")

    def test_select_intervention_metadata_complete(self):
        """intervention_selected ActionEntry.metadata 含 5 字段 (expected_gain/risk/audience/bloom_target/policy_type)."""
        lca, state = _make_lca_engine_with_state()
        cta = CTAInput(student_id="stu-sel-meta", belief_state=state)
        lca.select_intervention(cta, audience="teacher")

        entry = lca._cognitive_twin["stu-sel-meta"].action_history.entries[0]
        assert "expected_gain" in entry.metadata
        assert "expected_risk" in entry.metadata
        assert entry.metadata["audience"] == "teacher"
        assert "bloom_target" in entry.metadata
        assert "policy_type" in entry.metadata

    def test_select_intervention_multiple_calls_accumulate(self):
        """多次 select_intervention 累积 intervention_selected entries (cap 500)."""
        lca, state = _make_lca_engine_with_state()
        cta = CTAInput(student_id="stu-sel-multi", belief_state=state)
        for _ in range(3):
            lca.select_intervention(cta)
        assert lca._cognitive_twin["stu-sel-multi"].action_history.count_by_type("intervention_selected") == 3

    def test_select_intervention_action_history_cap_500(self):
        """select_intervention 累积 > 500 → 截断到最近 500 (跟 HumanFeedbackTrajectory 同 pattern)."""
        lca, state = _make_lca_engine_with_state()
        cta = CTAInput(student_id="stu-sel-cap", belief_state=state)
        # 多次 select 触发 cap 500
        for _ in range(501):
            lca.select_intervention(cta)
        # cap 截断到 500
        assert len(lca._cognitive_twin["stu-sel-cap"].action_history.entries) == 500


# ── 2. LCAEngine update 自动记录 reward_recorded action (3 tests) ─


class TestUpdateAutoRecordReward:
    """LCAEngine.update 自动记录 reward_recorded ActionEntry (v0.92.0-b)."""

    def test_update_records_reward_recorded(self):
        """update 自动构造 ActionEntry(reward_recorded) 并 append (reward=[0,1])."""
        from ecos.lca.intervention import Intervention, InterventionType, CLTLevel, CAStage
        lca, state = _make_lca_engine_with_state()
        cta = CTAInput(student_id="stu-upd", belief_state=state)
        result = lca.select_intervention(cta)

        # 构造 Intervention (从 result.intervention)
        intervention = result.intervention

        # update (reward=0.85)
        lca.update("stu-upd", intervention, state, state_delta=0.1, reward=0.85)

        # action_history 累积 reward_recorded
        twin = lca._cognitive_twin["stu-upd"]
        assert twin.action_history.count_by_type("reward_recorded") == 1
        entry = twin.action_history.last_n(1)[0]
        assert entry.action_type == "reward_recorded"
        assert entry.reward == 0.85
        assert entry.intervention_id == intervention.intervention_id

    def test_update_reward_pomdp_observation_recorded(self):
        """POMDP 路径 update 记录 reward_recorded 含 pomdp_observation in metadata."""
        from ecos.lca.policy_learner import PolicyLearnerConfig
        from ecos.lca.l4_optimization import BanditConfig
        # 用 POMDP policy
        pl_config = PolicyLearnerConfig(
            bandit_config=BanditConfig(n_arms=10, context_dim=16, cold_start_threshold=10),
            policy_type="pomdp",
        )
        lca = LCAEngine(config=LCAEngineConfig(
            use_llm_rationale=False,
            policy_learner_config=pl_config,
        ))
        state = _make_state("stu-pomdp")
        cta = CTAInput(student_id="stu-pomdp", belief_state=state)
        result = lca.select_intervention(cta)
        lca.update("stu-pomdp", result.intervention, state, state_delta=0.1, reward=0.7)

        entry = lca._cognitive_twin["stu-pomdp"].action_history.last_n(1)[0]
        assert entry.action_type == "reward_recorded"
        assert entry.metadata["policy_type"] == "pomdp"
        # pomdp_observation 应是 int (离散化到 [0, 4))
        assert "pomdp_observation" in entry.metadata
        assert entry.metadata["pomdp_observation"] is not None

    def test_update_select_intervention_full_sequence(self):
        """完整 select + update 序列累积 intervention_selected + reward_recorded."""
        lca, state = _make_lca_engine_with_state()
        cta = CTAInput(student_id="stu-full", belief_state=state)
        result = lca.select_intervention(cta)
        lca.update("stu-full", result.intervention, state, state_delta=0.1, reward=0.9)

        twin = lca._cognitive_twin["stu-full"]
        # 1 intervention_selected + 1 reward_recorded = 2 entries
        assert twin.action_history.count_by_type("intervention_selected") == 1
        assert twin.action_history.count_by_type("reward_recorded") == 1
        assert len(twin.action_history.entries) == 2


# ── 3. Runtime.plan_action_aware kwargs 透传 (3 tests) ─


class TestPlanActionAware:
    """Runtime.plan_action_aware (7 plan API) kwargs 透传 + action_entry fallback."""

    def test_plan_action_aware_basic(self):
        """plan_action_aware 基本调用: action_entry=None 不 raise, 走 LCA select_intervention."""
        from ecos.runtime import api as runtime_api
        lca, state = _make_lca_engine_with_state()
        result = runtime_api.plan_action_aware(
            student_id="stu-pa-1",
            audience="student",
            cta_input=CTAInput(student_id="stu-pa-1", belief_state=state),
            lca_engine=lca,
        )
        assert result is not None
        # action_history 自动记录 (来自 select_intervention Step 7)
        assert lca._cognitive_twin["stu-pa-1"].action_history.count_by_type("intervention_selected") == 1

    def test_plan_action_aware_action_entry_injection(self):
        """plan_action_aware 接受 action_entry kwarg, 触发 LCAEngine.append_action_history."""
        from ecos.runtime import api as runtime_api
        lca, state = _make_lca_engine_with_state()
        # 构造 1 个 reward_recorded ActionEntry (手动注入, 测试 API)
        action_entry = ActionEntry(
            student_id="stu-pa-inj",
            timestamp=datetime.now(),
            action_type="reward_recorded",
            intervention_id="iv_manual",
            reward=0.95,
            metadata={"policy_type": "linucb", "pomdp_observation": None},
            source="manual",
        )
        runtime_api.plan_action_aware(
            student_id="stu-pa-inj",
            audience="student",
            cta_input=CTAInput(student_id="stu-pa-inj", belief_state=state),
            lca_engine=lca,
            action_entry=action_entry,
        )
        twin = lca._cognitive_twin["stu-pa-inj"]
        # 1 manual reward_recorded + 1 auto intervention_selected (from select_intervention)
        assert twin.action_history.count_by_type("reward_recorded") == 1
        assert twin.action_history.count_by_type("intervention_selected") == 1

    def test_plan_action_aware_delegation_chain(self):
        """plan → plan_goal_aware → plan_human_feedback_aware → plan_action_aware 委托链.

        plan() 委托 plan_goal_aware (老), 但 Runtime 通过 _cognitive_twin dict 共享 CognitiveTwinAgent.
        """
        from ecos.runtime import api as runtime_api
        lca, state = _make_lca_engine_with_state()
        # 先 plan_action_aware (懒加载 CognitiveTwinAgent, action_history 已含 1 条)
        runtime_api.plan_action_aware(
            student_id="stu-chain",
            audience="student",
            cta_input=CTAInput(student_id="stu-chain", belief_state=state),
            lca_engine=lca,
        )
        # 再 plan_human_feedback_aware (委托 plan_action_aware, 共享 _cognitive_twin dict)
        from ecos.cta.cognitive_twin import HumanFeedbackEntry
        from ecos.cta.event_log import LearningEvent
        event = LearningEvent.from_hint_requested(
            student_id="stu-chain", problem_id="pb-1", hint_level=1,
        )
        runtime_api.plan_human_feedback_aware(
            student_id="stu-chain",
            audience="student",
            cta_input=CTAInput(student_id="stu-chain", belief_state=state),
            lca_engine=lca,
            human_feedback_entry=HumanFeedbackEntry.from_event(event),
        )
        twin = lca._cognitive_twin["stu-chain"]
        # intervention_selected 累计 2 次 (2 plan 调用, 都调 select_intervention)
        assert twin.action_history.count_by_type("intervention_selected") == 2
        # human_feedback 含 1 条
        assert twin.human_feedback.count_by_type("hint_requested") == 1


# ── 4. LCAEngine.append_action_history lazy init (3 tests) ─


class TestAppendActionHistoryLazyInit:
    """LCAEngine.append_action_history lazy init CognitiveTwinAgent from state (跟 append_human_feedback 完全 parallel)."""

    def test_append_action_history_lazy_init_from_state(self):
        """append_action_history + state → CognitiveTwinAgent.from_state 兜底 lazy init."""
        lca, state = _make_lca_engine_with_state()
        assert "stu-action-auto" not in lca._cognitive_twin
        entry = ActionEntry(
            student_id="stu-action-auto",
            timestamp=datetime.now(),
            action_type="policy_updated",
            metadata={"policy_type": "linucb"},
        )
        lca.append_action_history("stu-action-auto", entry, state=state)
        assert "stu-action-auto" in lca._cognitive_twin
        twin = lca._cognitive_twin["stu-action-auto"]
        assert isinstance(twin, CognitiveTwinAgent)
        assert twin.belief_state is state
        assert twin.action_history.count_by_type("policy_updated") == 1

    def test_append_action_history_skip_when_no_state(self):
        """append_action_history 无 state 且 dict 无 entry → skip (debug log, 不 raise)."""
        lca, _ = _make_lca_engine_with_state()
        # _cognitive_twin dict 空, state=None
        entry = ActionEntry(
            student_id="stu-no-state",
            timestamp=datetime.now(),
            action_type="dual_agent_calibrated",
            reward=0.92,
        )
        # 应 skip 不 raise (per append_human_feedback 同模式)
        lca.append_action_history("stu-no-state", entry, state=None)
        assert "stu-no-state" not in lca._cognitive_twin

    def test_append_action_history_dict_persists_across_appends(self):
        """_cognitive_twin dict 跨多次 append_action_history 持久 (per-student state)."""
        lca, state = _make_lca_engine_with_state()
        # 1st append → lazy init
        entry1 = ActionEntry(
            student_id="stu-persist", timestamp=datetime.now(),
            action_type="intervention_selected", intervention_id="iv_1",
        )
        lca.append_action_history("stu-persist", entry1, state=state)
        twin_after_first = lca._cognitive_twin["stu-persist"]
        # 2nd append → dict 不重建
        entry2 = ActionEntry(
            student_id="stu-persist", timestamp=datetime.now(),
            action_type="reward_recorded", intervention_id="iv_1", reward=0.7,
        )
        lca.append_action_history("stu-persist", entry2, state=state)
        twin_after_second = lca._cognitive_twin["stu-persist"]
        assert twin_after_first is twin_after_second, "dict 应保持引用稳定"
        # 2 entries 都在
        assert twin_after_second.action_history.count_by_type("intervention_selected") == 1
        assert twin_after_second.action_history.count_by_type("reward_recorded") == 1


# ── 5. POMDPPolicy 老 v0.91.0 snapshot raise (防御性自检 [5]) (2 tests) ─


class TestPomdpOldSchemaRaiseV092:
    """POMDPPolicy 老 v0.91.0 snapshot schema_version raise (v0.92.0-b SCHEMA_VERSION 升级).

    v0.91.0 是 v0.92.0-b 之前的当前 schema, 升级后老 snapshot raise ValueError.
    """

    def test_old_v091_snapshot_raises(self):
        """老 v0.91.0 snapshot raise ValueError (新加的 case, v0.92.0-b 升级前 OK)."""
        p = POMDPPolicy(seed=42)
        old_state = {
            "schema_version": "0.91.0",  # v0.92.0-b 之前的 schema
            "n_arms": 10,
            "n_states": 4,
            "n_observations": 4,
            "belief_state": [0.25, 0.25, 0.25, 0.25],
            "transition": [[[0.25] * 10] * 4] * 4,
            "observation_model": [[0.25] * 4] * 4,
            "reward": [[0.5] * 10] * 4,
        }
        with pytest.raises(ValueError, match=r"schema_version 不匹配"):
            p.load_state(old_state)

    def test_current_schema_dump_load(self):
        """v0.93.0 schema_version="0.93.0" dump + load round-trip 不 raise (v0.93.0-c 升级)."""
        p1 = POMDPPolicy(seed=42)
        state = p1.dump_state()
        assert state["schema_version"] == "0.93.0"
        p2 = POMDPPolicy(seed=42)
        p2.load_state(state)
        # 不 raise = round-trip OK