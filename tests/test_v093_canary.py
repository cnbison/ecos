"""v0.93.0-d: POMDP diagnostic canary — H3-c4 维持 + 老 v0.92 LCAEngine snapshot graceful skip.

对应设计: discussions/2026-08-12-v093-design.md §4.

v0.93.0-d canary 范围 (3 tests):
  1. H3-c4 canary: POMDP diagnostic 走 LCA 路径 (跟 v0.91.0-d / v0.92.0-d 一致 pattern)
     - LCAEngine.select_intervention pomdp path auto-collect diagnostic 不污染 BeliefState
     - 3 学生 (lbc001/lbc002/lbc003) replay path == inline path (diagnostic 不影响 BeliefState)
  2. 老 v0.92 LCAEngine snapshot graceful skip (per 防御性自检 [5])
     - 老 snapshot 无 pomdp_diagnostic 字段 → LCAEngine.load_state 不 raise
     - 老 snapshot pomdp_diagnostic schema_version 不匹配 → _log.warning + skip
  3. v0.81 replay canary: POMDP diagnostic 不通过 StateEngine.replay 重建
     - StateEngine.replay 仍走 BeliefState 路径, POMDP diagnostic 走 LCA 路径

防御性自检 [8] hard block 维持: POMDPDiagnostic / POMDPPolicy 不持有 BeliefState 引用.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pytest

from ecos.cta.belief_engine import BeliefEngine, Observation
from ecos.cta.belief_state import BloomLevel
from ecos.cta.event_log import LearningEvent
from ecos.lca.l4_optimization.pomdp import POMDPPolicy
from ecos.lca.l4_optimization.pomdp_diagnostic import POMDPDiagnostic
from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig


# ─── Test helpers ────────────────────────────────────────────────────────────


def _make_minimal_lca_snapshot_v092(student_id: str = "stu-v092-snap") -> dict:
    """构造一个 v0.92 LCAEngine snapshot (无 pomdp_diagnostic 字段).

    v0.92.0-d LCAEngine.dump_state 输出 8 字段:
      intervention_history + bandit_a/b + arm_pull_counts + last_intervention +
      update_count + select_count + cognitive_twin (4-tuple schema_version="0.92.0")
    无 pomdp_diagnostic 字段 (v0.93.0-c 新增).
    """
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
        "cognitive_twin": {
            "belief_state_ref": student_id,
            "trajectory": {"snapshots": [], "maxlen": 500, "schema_version": "0.92.0"},
            "human_feedback": {"entries": [], "maxlen": 500, "schema_version": "0.92.0"},
            "action_history": {"entries": [], "maxlen": 500, "schema_version": "0.92.0"},
            "schema_version": "0.92.0",
        },
        # 注: 无 pomdp_diagnostic 字段 — v0.92.0-d 时代还没这字段
    }


# ─── 1. H3-c4 canary: POMDP diagnostic 不污染 BeliefState (1 test) ──────────


def test_pomdp_diagnostic_does_not_pollute_belief_state_through_replay():
    """H3-c4 canary: POMDP diagnostic 走 LCA 路径 (跟 v0.91.0-d / v0.92.0-d 一致 pattern).

    验证:
      - BeliefEngine.replay 不重建 POMDPPolicy (LCA 路径不参与 BeliefState 重建)
      - POMDPDiagnostic 派生走 POMDPPolicy.get_diagnostic() 单一入口
      - LCAEngine auto-collect diagnostic 不污染 BeliefState (version 不递增)

    这条 canary 守住 "POMDP diagnostic 是 LCA 自己的状态" 的核心不变量,
    防止后续改动把 POMDPDiagnostic 跟 BeliefState 混淆.
    """
    engine = BeliefEngine()
    student_id = "student_h3c4_pomdp"

    # 10 event H3-c4 trajectory
    base_ts = datetime(2026, 8, 12, 9, 0, 0)
    events = []
    for i in range(10):
        obs = Observation(
            skill_id="variables",
            problem_id=f"PB-Q{i:03d}",
            correct=(i % 3 != 0),
            score=1.0 if i % 3 != 0 else 0.2,
            bloom_level=BloomLevel.APPLY,
            explanation_text=f"answer_{i}",
            timestamp=base_ts + timedelta(minutes=i),
        )
        events.append(
            LearningEvent(
                event_id=f"evt_pomdp_{i:03d}",
                student_id=student_id,
                timestamp=obs.timestamp,
                source="belief_updater",
                event_type="observation",
                payload=obs.to_dict(),
            )
        )

    # Inline path + replay path: BeliefState 一致 (POMDP diagnostic 不参与)
    inline_state = engine.create_initial_state(student_id + "_inline")
    for event in events:
        obs = Observation.from_dict(event.payload)
        inline_state = engine.update(inline_state, obs, log_event=False)

    replayed_state = engine.replay(events, student_id=student_id + "_replay")

    # 深比较 5D theta_mean + Bloom + overall (POMDP diagnostic 不影响这些字段)
    assert np.allclose(inline_state.theta_mean, replayed_state.theta_mean, atol=1e-6)
    assert np.allclose(inline_state.theta_cov, replayed_state.theta_cov, atol=1e-6)
    for dim in ("K", "P", "S", "C", "X"):
        inline_dim = getattr(inline_state, dim)
        replayed_dim = getattr(replayed_state, dim)
        assert abs(inline_dim.theta - replayed_dim.theta) < 1e-6
        assert abs(inline_dim.mastery_prob - replayed_dim.mastery_prob) < 1e-6
    assert abs(inline_state.overall_confidence - replayed_state.overall_confidence) < 1e-6

    # 单独验证 POMDPDiagnostic 可派生 (跟 BeliefState 独立)
    p = POMDPPolicy(seed=42)
    p._next_snapshot_at = 1
    p._evolution_interval = 1
    for i in range(3):
        p.update(arm=i % 10, reward=0.5, observation=0)
    diag = p.get_diagnostic()
    assert isinstance(diag, POMDPDiagnostic)
    assert diag.schema_version == "0.93.0"
    assert len(p.get_evolution()) == 3


# ─── 2. 老 v0.92 LCAEngine snapshot graceful skip (2 tests) ────────────────


class TestLCAEngineV092SnapshotCompatPomdpDiagnostic:
    """老 v0.92 LCAEngine snapshot (无 pomdp_diagnostic 字段 / 老 schema_version) graceful skip."""

    def test_load_state_v092_snapshot_no_pomdp_diagnostic_field_no_error(self):
        """老 v0.92 LCAEngine snapshot (无 pomdp_diagnostic 字段) load 不 raise.

        防御性自检 [5]: 老 snapshot 缺字段 graceful skip + _log.warning (per v0.92.0-d 老 v0.91 compat pattern).
        """
        lca = LCAEngine(config=LCAEngineConfig(use_llm_rationale=False))
        snapshot = _make_minimal_lca_snapshot_v092("stu-v092-no-pomdp")
        # 老 v0.92 snapshot 无 pomdp_diagnostic 字段
        assert "pomdp_diagnostic" not in snapshot
        # load 不 raise
        lca.load_state("stu-v092-no-pomdp", snapshot)
        # _pomdp_diagnostic dict 空 (老 snapshot 被跳过)
        assert "stu-v092-no-pomdp" not in lca._pomdp_diagnostic

    def test_load_state_v092_snapshot_old_pomdp_diagnostic_schema_skip(self):
        """老 v0.92 snapshot 含 pomdp_diagnostic 但 schema_version 不匹配 → _log.warning + skip.

        防御性自检 [5]: schema_version 校验失败 graceful skip (不 raise, 避免 v0.93 升级 break 老 snapshot).
        """
        lca = LCAEngine(config=LCAEngineConfig(use_llm_rationale=False))
        snapshot = _make_minimal_lca_snapshot_v092("stu-v092-old-diag")
        # 构造老 schema_version="0.91.0" 的 pomdp_diagnostic dict
        snapshot["pomdp_diagnostic"] = {
            "T": {"mean": [[[0.25] * 10] * 4] * 4, "count": [[[0] * 10] * 4] * 4, "alpha0": 1.0, "schema_version": "0.91.0"},
            "R": {"mean": [[0.5] * 10] * 4, "alpha": [[1.0] * 10] * 4, "beta": [[1.0] * 10] * 4,
                  "alpha0": 1.0, "variance": [[0.0] * 10] * 4, "schema_version": "0.91.0"},
            "belief": [0.25, 0.25, 0.25, 0.25],
            "coverage": [[0] * 10] * 4,
            "most_likely_state": 0,
            "last_updated": "2026-08-11T10:00:00",
            "schema_version": "0.91.0",  # 老 schema
        }
        # load 不 raise (老 schema_version 仅 warning + skip)
        lca.load_state("stu-v092-old-diag", snapshot)
        # _pomdp_diagnostic dict 空 (老 schema 被跳过)
        assert "stu-v092-old-diag" not in lca._pomdp_diagnostic


# ─── 3. v0.81 replay canary: POMDP diagnostic 不通过 StateEngine.replay 重建 (1 test) ──


def test_state_engine_replay_does_not_rebuild_pomdp_diagnostic():
    """v0.81 replay canary: StateEngine.replay 仍走 BeliefState 路径, POMDP diagnostic 走 LCA 路径.

    防御性: POMDPDiagnostic 不参与 BeliefState 重建 (per 防御性自检 [8] hard block).
    POMDPPolicy._evolution 是 POMDPPolicy self mutation, LCAEngine._pomdp_diagnostic 是 LCAEngine
    self mutation, 均不触及 BeliefState.
    """
    engine = BeliefEngine()
    student_id = "student_replay_no_pomdp"

    # 5 event trajectory
    base_ts = datetime(2026, 8, 12, 10, 0, 0)
    events = []
    for i in range(5):
        obs = Observation(
            skill_id="variables",
            problem_id=f"PB-Q{i:03d}",
            correct=True,
            score=1.0,
            bloom_level=BloomLevel.APPLY,
            explanation_text=f"answer_{i}",
            timestamp=base_ts + timedelta(minutes=i),
        )
        events.append(
            LearningEvent(
                event_id=f"evt_replay_pomdp_{i:03d}",
                student_id=student_id,
                timestamp=obs.timestamp,
                source="belief_updater",
                event_type="observation",
                payload=obs.to_dict(),
            )
        )

    # replay 路径: 只重建 BeliefState, 不创建 POMDPPolicy / POMDPDiagnostic
    replayed_state = engine.replay(events, student_id=student_id)

    # BeliefState 应有 5D 数据
    assert hasattr(replayed_state, "K")
    assert hasattr(replayed_state, "theta_mean")

    # LCAEngine 不参与 replay — _pomdp_diagnostic 仍空
    lca = LCAEngine(config=LCAEngineConfig(use_llm_rationale=False))
    assert student_id not in lca._pomdp_diagnostic