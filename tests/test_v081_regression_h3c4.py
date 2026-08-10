"""v0.81.0-c: v0.78 H3-c4 regression canary for replay path.

Critical invariant: replay(events) state == inline update state for theta/dim/bloom/overall.
This guards against silent regression in:
- BeliefUpdator.apply (sole mutation site)
- StateEngine.replay (event iteration + Observation.from_dict)
- BeliefEngine.update(log_event=False) (event log suppression)

3 tests:
- multi-event replay equivalence (10 events, deep-compare 5D + Bloom + overall)
- replay determinism (calling replay twice produces identical state)
- simulate fork produces divergent state (counterfactual works)
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import List

import numpy as np
import pytest

from ecos.cta.belief_engine import BeliefEngine, Observation
from ecos.cta.belief_state import BloomLevel
from ecos.cta.event_log import EventLog, LearningEvent


def _build_mixed_observation(idx: int, base_ts: datetime) -> Observation:
    """Build a mixed observation simulating lbc001-style H3-c4 trajectory."""
    # Cycle through different skills/bloom levels/scores
    skills = ["variables", "loops", "conditionals", "functions", "lists"]
    blooms = [BloomLevel.REMEMBER, BloomLevel.UNDERSTAND, BloomLevel.APPLY, BloomLevel.ANALYZE]
    return Observation(
        skill_id=skills[idx % len(skills)],
        problem_id=f"PB-Q{idx:03d}",
        correct=(idx % 3 != 0),  # 2/3 correct
        score=1.0 if idx % 3 != 0 else 0.2,
        bloom_level=blooms[idx % len(blooms)],
        explanation_text=f"answer_{idx}",
        timestamp=base_ts + timedelta(minutes=idx),
    )


def _build_event_list(n: int, base_ts: datetime, student_id: str) -> List[LearningEvent]:
    """Build n LearningEvents mirroring a real H3-c4 trajectory."""
    events = []
    for i in range(n):
        obs = _build_mixed_observation(i, base_ts)
        events.append(
            LearningEvent(
                event_id=f"evt_h3c4_{i:03d}",
                student_id=student_id,
                timestamp=obs.timestamp,
                source="belief_updater",
                event_type="observation",
                payload=obs.to_dict(),
            )
        )
    return events


# ─── Tests (3) ─────────────────────────────────────────────────────────────


@pytest.fixture
def engine():
    return BeliefEngine()


def test_replay_equivalence_multi_event(engine):
    """CRITICAL: replay(10 events) state == inline update state for theta/dim/bloom/overall.

    This is the H3-c4 regression canary: if BeliefEngine.update silently changes
    behavior, replayed state diverges from inline state. We deep-compare all
    deterministic fields (NOT version/event_id - those are run-specific).
    """
    n_events = 10
    base_ts = datetime(2026, 8, 10, 9, 0, 0)
    events = _build_event_list(n_events, base_ts, "student_h3c4_replay")

    # Inline path
    engine.reset_student("student_h3c4_inline")
    inline_state = engine.create_initial_state("student_h3c4_inline")
    for event in events:
        obs = Observation.from_dict(event.payload)
        inline_state = engine.update(inline_state, obs, log_event=False)

    # Replay path
    engine.reset_student("student_h3c4_replay")
    replayed_state = engine.replay(events, student_id="student_h3c4_replay")

    # Deep-compare deterministic fields
    # 1. 5D theta_mean (5 elements)
    assert np.allclose(inline_state.theta_mean, replayed_state.theta_mean, atol=1e-6), (
        f"theta_mean diverged: inline={inline_state.theta_mean} "
        f"replayed={replayed_state.theta_mean}"
    )

    # 2. 5D theta_cov (5x5)
    assert np.allclose(inline_state.theta_cov, replayed_state.theta_cov, atol=1e-6), (
        f"theta_cov diverged: inline={inline_state.theta_cov.tolist()} "
        f"replayed={replayed_state.theta_cov.tolist()}"
    )

    # 3. Per-dim: theta, mastery_prob, confidence, mastered
    for dim in ("K", "P", "S", "C", "X"):
        inline_dim = getattr(inline_state, dim)
        replayed_dim = getattr(replayed_state, dim)
        assert abs(inline_dim.theta - replayed_dim.theta) < 1e-6, (
            f"{dim}.theta diverged: {inline_dim.theta} vs {replayed_dim.theta}"
        )
        assert abs(inline_dim.mastery_prob - replayed_dim.mastery_prob) < 1e-6
        assert abs(inline_dim.confidence - replayed_dim.confidence) < 1e-6
        assert inline_dim.mastered == replayed_dim.mastered

    # 4. Bloom profile 6 fields + confidence + dominant_layer
    for field_name in (
        "remember", "understand", "apply", "analyze", "evaluate", "create", "confidence",
    ):
        v_inline = getattr(inline_state.bloom_profile, field_name)
        v_replay = getattr(replayed_state.bloom_profile, field_name)
        assert abs(v_inline - v_replay) < 1e-6, (
            f"bloom_profile.{field_name} diverged: {v_inline} vs {v_replay}"
        )
    assert (
        inline_state.bloom_profile.dominant_layer
        == replayed_state.bloom_profile.dominant_layer
    )

    # 5. overall_confidence
    assert abs(
        inline_state.overall_confidence - replayed_state.overall_confidence
    ) < 1e-6, (
        f"overall_confidence diverged: "
        f"{inline_state.overall_confidence} vs {replayed_state.overall_confidence}"
    )

    # 6. Trajectory snapshot count (deterministic)
    assert (
        len(inline_state.trajectory.snapshots) == len(replayed_state.trajectory.snapshots)
    ), (
        f"trajectory snapshot count diverged: "
        f"inline={len(inline_state.trajectory.snapshots)} "
        f"replayed={len(replayed_state.trajectory.snapshots)}"
    )


def test_replay_is_deterministic(engine):
    """Calling replay() twice on same events produces identical state (no random drift).

    Critical for H3-c4 regression canary: if replay is non-deterministic, the
    canary itself becomes flaky and we lose the ability to detect real regressions.
    """
    n_events = 5
    base_ts = datetime(2026, 8, 10, 14, 0, 0)
    events = _build_event_list(n_events, base_ts, "student_h3c4_deterministic")

    engine.reset_student("student_h3c4_deterministic")
    state1 = engine.replay(events, student_id="student_h3c4_deterministic")

    engine.reset_student("student_h3c4_deterministic")
    state2 = engine.replay(events, student_id="student_h3c4_deterministic")

    # Compare all deterministic fields (theta/dim/bloom/overall)
    assert np.allclose(state1.theta_mean, state2.theta_mean, atol=1e-9)
    assert np.allclose(state1.theta_cov, state2.theta_cov, atol=1e-9)
    for dim in ("K", "P", "S", "C", "X"):
        d1 = getattr(state1, dim)
        d2 = getattr(state2, dim)
        assert abs(d1.theta - d2.theta) < 1e-9
        assert abs(d1.mastery_prob - d2.mastery_prob) < 1e-9
    for field_name in (
        "remember", "understand", "apply", "analyze", "evaluate", "create", "confidence",
    ):
        v1 = getattr(state1.bloom_profile, field_name)
        v2 = getattr(state2.bloom_profile, field_name)
        assert abs(v1 - v2) < 1e-9
    assert abs(state1.overall_confidence - state2.overall_confidence) < 1e-9


def test_simulate_fork_produces_divergent_state(engine):
    """simulate(fork_at_idx=5, alternative=[different events]) should diverge from inline.

    This verifies that simulate() actually applies alternative events (counterfactual)
    rather than just copying original state.
    """
    n_events = 10
    base_ts = datetime(2026, 8, 10, 16, 0, 0)
    events = _build_event_list(n_events, base_ts, "student_h3c4_sim")

    # Build alternative events with HIGHER scores (should produce higher theta)
    alternative_events = []
    for i in range(5):
        obs = Observation(
            skill_id=f"alt_skill_{i}",
            problem_id=f"ALT-{i}",
            correct=True,
            score=1.0,  # All correct
            bloom_level=BloomLevel.APPLY,
            timestamp=base_ts + timedelta(minutes=n_events + i),
        )
        alternative_events.append(
            LearningEvent(
                event_id=f"evt_alt_{i:03d}",
                student_id="student_h3c4_sim",
                timestamp=obs.timestamp,
                source="belief_updater",
                event_type="observation",
                payload=obs.to_dict(),
            )
        )

    # Inline path: apply all 10 events
    engine.reset_student("student_h3c4_sim_inline")
    inline_state = engine.create_initial_state("student_h3c4_sim_inline")
    for event in events:
        obs = Observation.from_dict(event.payload)
        inline_state = engine.update(inline_state, obs, log_event=False)

    # Simulate path: apply events[0:5] + alternative_events (5 high-score)
    engine.reset_student("student_h3c4_sim")
    simulated_state = engine.simulate(
        events,
        student_id="student_h3c4_sim",
        fork_at_idx=5,
        alternative_events=alternative_events,
    )

    # Simulated state should DIVERGE from inline state
    # (alternative events all score=1.0 vs original mix of 1.0/0.2)
    assert not np.allclose(
        inline_state.theta_mean, simulated_state.theta_mean, atol=1e-6
    ), (
        f"simulate failed to diverge: inline={inline_state.theta_mean} "
        f"simulated={simulated_state.theta_mean}"
    )

    # Trajectory: inline has 10 snapshots, simulated has 5 original + 5 alternative = 10
    assert len(simulated_state.trajectory.snapshots) == 10
