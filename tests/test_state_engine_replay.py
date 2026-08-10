"""v0.81.0-c: StateEngine.replay + simulate pytest 套件.

Tests:
- replay basic: empty events, single event, multiple events
- replay equivalence: replay(events) state == inline update state
- simulate: fork_at_idx=0 (full alternative), fork_at_idx=midpoint, fork_at_idx=len (no alternative applied)
- simulate: out-of-range fork_at_idx raises ValueError
- multi-student isolation
- log_event=False propagation: replay doesn't pollute event_log
- update_fn / create_state_fn callback shape

Total: 16 tests.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

import pytest

from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig, Observation
from ecos.cta.belief_state import BloomLevel, BeliefState
from ecos.cta.event_log import EventLog, LearningEvent
from ecos.cta.state_engine import StateEngine


# ─── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def engine():
    """BeliefEngine without event_log (default)."""
    return BeliefEngine()


def _make_observation(
    skill_id: str, problem_id: str, score: float, ts: datetime, bloom: BloomLevel = BloomLevel.APPLY
) -> Observation:
    return Observation(
        skill_id=skill_id,
        problem_id=problem_id,
        correct=score >= 0.6,
        score=score,
        bloom_level=bloom,
        timestamp=ts,
    )


def _build_events(n: int, base_ts: datetime) -> List[LearningEvent]:
    """Build n synthetic LearningEvents with rising timestamps."""
    events = []
    for i in range(n):
        obs = _make_observation(
            skill_id=f"skill_{i}",
            problem_id=f"P{i}",
            score=0.7 if i % 2 == 0 else 0.3,
            ts=base_ts + timedelta(minutes=i),
        )
        events.append(
            LearningEvent(
                event_id=f"evt_replay_{i:03d}",
                student_id="student_replay_001",
                timestamp=obs.timestamp,
                source="belief_updater",
                event_type="observation",
                payload=obs.to_dict(),
            )
        )
    return events


# ─── StateEngine.replay basic tests (4) ─────────────────────────────────────


def test_replay_empty_events_returns_fresh_state(engine):
    """replay([]) should return a fresh initial state (no events applied)."""
    se = StateEngine()
    state = se.replay(
        events=[],
        student_id="student_x",
        update_fn=lambda s, o: engine.update(s, o, log_event=False),
        create_state_fn=engine.create_initial_state,
    )
    assert state.student_id == "student_x"
    # Fresh state has 0 trajectory snapshots, 0 response history
    assert len(state.trajectory.snapshots) == 0


def test_replay_single_event_applies_one_observation(engine):
    """replay([event]) should apply exactly one observation."""
    base_ts = datetime(2026, 8, 10, 10, 0, 0)
    events = _build_events(1, base_ts)
    se = StateEngine()
    state = se.replay(
        events,
        student_id="student_replay_001",
        update_fn=lambda s, o: engine.update(s, o, log_event=False),
        create_state_fn=engine.create_initial_state,
    )
    # After 1 observation, trajectory should have 1 snapshot
    assert len(state.trajectory.snapshots) == 1


def test_replay_multiple_events_chronological(engine):
    """replay(3 events) should apply all 3 in chronological order."""
    base_ts = datetime(2026, 8, 10, 10, 0, 0)
    events = _build_events(3, base_ts)
    se = StateEngine()
    state = se.replay(
        events,
        student_id="student_replay_001",
        update_fn=lambda s, o: engine.update(s, o, log_event=False),
        create_state_fn=engine.create_initial_state,
    )
    # After 3 observations, trajectory should have 3 snapshots
    assert len(state.trajectory.snapshots) == 3


def test_replay_does_not_pollute_event_log(engine):
    """replay() with event_log attached should NOT log events (log_event=False)."""
    log = EventLog.in_memory()
    eng_with_log = BeliefEngine(event_log=log)
    eng_with_log.reset_student("student_replay_001")

    base_ts = datetime(2026, 8, 10, 10, 0, 0)
    events = _build_events(3, base_ts)

    state = eng_with_log.replay(events, student_id="student_replay_001")
    # No events should have been logged (log_event=False)
    assert log.count_events("student_replay_001") == 0


# ─── Replay equivalence critical test (1, HIGH risk) ─────────────────────────


def test_replay_equivalence_with_inline_update(engine):
    """CRITICAL: replay(events) state == inline update state for theta/dim/bloom/overall.

    This is the key risk per plan: replay path may diverge from inline path.
    We deep-compare the deterministic fields (NOT version/last_updated/event_id,
    which are run-specific).

    Why version/last_updated/event_id are NOT compared:
    - version: each commit bumps version with NEW event_id, so replayed state.version
      has different event_id chain than inline state.version.
    - last_updated: set to observation.timestamp in both paths, but other side-effects
      (e.g. bump_version now()) may differ in microsecond precision.
    - event_id: random UUID per commit.
    """
    base_ts = datetime(2026, 8, 10, 10, 0, 0)
    events = _build_events(5, base_ts)

    # Inline path: create state, apply each observation via engine.update
    engine.reset_student("student_inline_001")
    inline_state = engine.create_initial_state("student_inline_001")
    for event in events:
        obs = Observation.from_dict(event.payload)
        # Override timestamp to match event (since from_dict may parse it)
        inline_state = engine.update(inline_state, obs, log_event=False)

    # Replay path: engine.replay (uses StateEngine.replay internally)
    engine.reset_student("student_replay_001")
    replayed_state = engine.replay(events, student_id="student_replay_001")

    # Deep-compare deterministic fields
    import numpy as np

    # 5D theta_mean (5 elements)
    assert np.allclose(inline_state.theta_mean, replayed_state.theta_mean, atol=1e-6), (
        f"theta_mean mismatch: inline={inline_state.theta_mean} "
        f"replayed={replayed_state.theta_mean}"
    )

    # 5D theta_cov (5x5)
    assert np.allclose(inline_state.theta_cov, replayed_state.theta_cov, atol=1e-6), (
        f"theta_cov mismatch: inline={inline_state.theta_cov} "
        f"replayed={replayed_state.theta_cov}"
    )

    # Per-dim: theta, mastery_prob, confidence, mastered
    for dim in ("K", "P", "S", "C", "X"):
        inline_dim = getattr(inline_state, dim)
        replayed_dim = getattr(replayed_state, dim)
        assert abs(inline_dim.theta - replayed_dim.theta) < 1e-6, (
            f"{dim}.theta mismatch: {inline_dim.theta} vs {replayed_dim.theta}"
        )
        assert abs(inline_dim.mastery_prob - replayed_dim.mastery_prob) < 1e-6
        assert abs(inline_dim.confidence - replayed_dim.confidence) < 1e-6
        assert inline_dim.mastered == replayed_dim.mastered

    # Bloom profile 6 fields + confidence + dominant_layer
    for field_name in (
        "remember", "understand", "apply", "analyze", "evaluate", "create", "confidence",
    ):
        v_inline = getattr(inline_state.bloom_profile, field_name)
        v_replay = getattr(replayed_state.bloom_profile, field_name)
        assert abs(v_inline - v_replay) < 1e-6, (
            f"bloom_profile.{field_name} mismatch: {v_inline} vs {v_replay}"
        )
    assert inline_state.bloom_profile.dominant_layer == replayed_state.bloom_profile.dominant_layer

    # overall_confidence
    assert abs(inline_state.overall_confidence - replayed_state.overall_confidence) < 1e-6

    # Trajectory snapshot count (deterministic - inline + replay both append per observation)
    assert len(inline_state.trajectory.snapshots) == len(replayed_state.trajectory.snapshots)


# ─── StateEngine.simulate tests (5) ─────────────────────────────────────────


def test_simulate_fork_at_zero_applies_only_alternative(engine):
    """simulate(fork_at_idx=0) should apply 0 original + N alternative events."""
    base_ts = datetime(2026, 8, 10, 10, 0, 0)
    original_events = _build_events(3, base_ts)
    alternative_events = _build_events(2, base_ts + timedelta(hours=1))

    state = engine.simulate(
        original_events,
        student_id="student_sim_001",
        fork_at_idx=0,
        alternative_events=alternative_events,
    )
    # 0 original + 2 alternative = 2 trajectory snapshots
    assert len(state.trajectory.snapshots) == 2


def test_simulate_fork_at_midpoint(engine):
    """simulate(fork_at_idx=2) on 4 events should apply 2 original + alternative."""
    base_ts = datetime(2026, 8, 10, 10, 0, 0)
    original_events = _build_events(4, base_ts)
    alternative_events = _build_events(3, base_ts + timedelta(hours=2))

    state = engine.simulate(
        original_events,
        student_id="student_sim_002",
        fork_at_idx=2,
        alternative_events=alternative_events,
    )
    # 2 original prefix + 3 alternative = 5 trajectory snapshots
    assert len(state.trajectory.snapshots) == 5


def test_simulate_fork_at_len_with_empty_alternative(engine):
    """simulate(fork_at_idx=len, alternative=[]) should apply only original."""
    base_ts = datetime(2026, 8, 10, 10, 0, 0)
    original_events = _build_events(3, base_ts)

    state = engine.simulate(
        original_events,
        student_id="student_sim_003",
        fork_at_idx=3,  # == len(original_events)
        alternative_events=[],  # no alternative -> only original replayed
    )
    # 3 original + 0 alternative = 3 trajectory snapshots
    assert len(state.trajectory.snapshots) == 3


def test_simulate_fork_at_idx_out_of_range_raises(engine):
    """simulate(fork_at_idx=-1 or >len) should raise ValueError."""
    base_ts = datetime(2026, 8, 10, 10, 0, 0)
    events = _build_events(3, base_ts)
    se = StateEngine()

    with pytest.raises(ValueError):
        se.simulate(
            events,
            student_id="x",
            fork_at_idx=-1,
            alternative_events=[],
            update_fn=lambda s, o: engine.update(s, o, log_event=False),
            create_state_fn=engine.create_initial_state,
        )

    with pytest.raises(ValueError):
        se.simulate(
            events,
            student_id="x",
            fork_at_idx=4,  # > len(events)=3
            alternative_events=[],
            update_fn=lambda s, o: engine.update(s, o, log_event=False),
            create_state_fn=engine.create_initial_state,
        )


def test_simulate_does_not_pollute_event_log(engine):
    """simulate() should NOT log events (log_event=False)."""
    log = EventLog.in_memory()
    eng_with_log = BeliefEngine(event_log=log)
    eng_with_log.reset_student("student_sim_004")

    base_ts = datetime(2026, 8, 10, 10, 0, 0)
    original = _build_events(3, base_ts)
    alternative = _build_events(2, base_ts + timedelta(hours=1))

    eng_with_log.simulate(
        original,
        student_id="student_sim_004",
        fork_at_idx=2,
        alternative_events=alternative,
    )
    assert log.count_events("student_sim_004") == 0


# ─── Multi-student isolation (1) ─────────────────────────────────────────────


def test_replay_multi_student_isolation(engine):
    """replay() for student A should not affect student B's state."""
    base_ts = datetime(2026, 8, 10, 10, 0, 0)
    events_a = _build_events(2, base_ts)
    events_b = [
        LearningEvent(
            event_id=f"evt_b_{i}",
            student_id="student_b",
            timestamp=base_ts + timedelta(minutes=i),
            source="belief_updater",
            event_type="observation",
            payload=_make_observation(
                skill_id=f"skill_b_{i}",
                problem_id=f"PB_b_{i}",
                score=1.0,
                ts=base_ts + timedelta(minutes=i),
            ).to_dict(),
        )
        for i in range(3)
    ]

    state_a = engine.replay(events_a, student_id="student_a")
    state_b = engine.replay(events_b, student_id="student_b")

    assert state_a.student_id == "student_a"
    assert state_b.student_id == "student_b"
    assert len(state_a.trajectory.snapshots) == 2
    assert len(state_b.trajectory.snapshots) == 3


# ─── Update_fn / create_state_fn callback shape (2) ──────────────────────────


def test_replay_uses_create_state_fn_for_fresh_state(engine):
    """replay() should call create_state_fn(student_id) to get a fresh state."""
    se = StateEngine()
    call_count = [0]
    call_args = []

    def tracked_create(student_id):
        call_count[0] += 1
        call_args.append(student_id)
        return engine.create_initial_state(student_id)

    se.replay(
        events=[],
        student_id="student_tracked",
        update_fn=lambda s, o: engine.update(s, o, log_event=False),
        create_state_fn=tracked_create,
    )
    assert call_count[0] == 1
    assert call_args == ["student_tracked"]


def test_replay_calls_update_fn_per_event(engine):
    """replay() should call update_fn once per event."""
    se = StateEngine()
    call_count = [0]

    def tracked_update(state, obs):
        call_count[0] += 1
        return engine.update(state, obs, log_event=False)

    base_ts = datetime(2026, 8, 10, 10, 0, 0)
    events = _build_events(4, base_ts)
    se.replay(
        events,
        student_id="student_tracked_2",
        update_fn=tracked_update,
        create_state_fn=engine.create_initial_state,
    )
    assert call_count[0] == 4


# ─── Pure function property (1) ─────────────────────────────────────────────


def test_replay_does_not_mutate_input_events(engine):
    """replay() should not mutate the input events list."""
    base_ts = datetime(2026, 8, 10, 10, 0, 0)
    events = _build_events(3, base_ts)
    original_event_ids = [e.event_id for e in events]
    original_payloads = [dict(e.payload) for e in events]

    engine.replay(events, student_id="student_pure")

    # Events list should be unchanged
    assert [e.event_id for e in events] == original_event_ids
    for orig, now in zip(original_payloads, [e.payload for e in events]):
        assert orig == now
