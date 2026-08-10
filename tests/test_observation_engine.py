"""v0.80.0-c ObservationEngine test suite.

Covers:
- run() builds ObservationContext (no state mutation on BeliefState)
- warmup state machine (count, in_warmup, just_exited_warmup)
- probe state machine (probe_due_in, should_probe_now, consume_probe)
- score/correct derivation from observation
- bloom_step switching (warmup vs normal)
- reset_student clears state
"""
from __future__ import annotations

from datetime import datetime

import pytest

from ecos.cta.belief_engine import BeliefEngineConfig, Observation
from ecos.cta.belief_state import BloomLevel
from ecos.cta.observation_engine import ObservationEngine


@pytest.fixture
def config() -> BeliefEngineConfig:
    return BeliefEngineConfig(
        warmup_questions=5,
        warmup_step=0.1,
        bloom_update_step=0.05,
        probe_interval=8,
        probe_first_after_warmup=True,
    )


@pytest.fixture
def engine() -> ObservationEngine:
    return ObservationEngine()


def _make_observation(score: float = 1.0, bloom: BloomLevel = BloomLevel.APPLY) -> Observation:
    return Observation(
        skill_id="addition",
        problem_id="P001",
        correct=score >= 0.6,
        score=score,
        bloom_level=bloom,
        timestamp=datetime(2026, 8, 10, 12, 0, 0),
    )


# ── run(): returns ObservationContext ──────────────────────────────────


def test_run_returns_observation_context(engine, config):
    obs = _make_observation()
    ctx = engine.run("lbc_test", obs, config)
    assert ctx.student_id == "lbc_test"
    assert ctx.skill_id == "addition"
    assert ctx.problem_id == "P001"
    assert ctx.observation is obs


def test_run_derives_score_from_observation_score(engine, config):
    obs = _make_observation(score=0.7)
    ctx = engine.run("lbc_test", obs, config)
    assert ctx.score == 0.7
    assert ctx.correct is True  # 0.7 >= 0.6


def test_run_derives_correct_false_below_threshold(engine, config):
    obs = _make_observation(score=0.3)
    ctx = engine.run("lbc_test", obs, config)
    assert ctx.score == 0.3
    assert ctx.correct is False  # 0.3 < 0.6


def test_run_falls_back_to_correct_when_score_zero(engine, config):
    """When score=0 and correct=True, falls back to score=1.0 (老调用兼容)."""
    obs = Observation(
        skill_id="addition", problem_id="P001",
        correct=True, score=0.0,  # 老调用
        bloom_level=BloomLevel.APPLY,
        timestamp=datetime(2026, 8, 10),
    )
    ctx = engine.run("lbc_test", obs, config)
    assert ctx.score == 1.0
    assert ctx.correct is True


def test_run_in_warmup_true_for_first_n(engine, config):
    """First 4 questions are in warmup (count incremented BEFORE is_warmup check;
    warmup_questions=5 means count < 5, so questions 1-4 are warmup, 5th exits)."""
    for i in range(4):
        obs = _make_observation()
        ctx = engine.run("lbc", obs, config)
        assert ctx.in_warmup is True, f"question {i+1} should be in warmup"


def test_run_in_warmup_false_after_n(engine, config):
    """5th question exits warmup (count=5, 5 < 5 is False)."""
    for _ in range(4):
        engine.run("lbc", _make_observation(), config)
    ctx = engine.run("lbc", _make_observation(), config)
    assert ctx.in_warmup is False


def test_run_just_exited_warmup_on_first_post_warmup(engine, config):
    """just_exited_warmup is True on the 5th question (first post-warmup)."""
    for _ in range(4):
        engine.run("lbc", _make_observation(), config)
    ctx = engine.run("lbc", _make_observation(), config)
    assert ctx.just_exited_warmup is True


def test_run_just_exited_warmup_false_on_subsequent(engine, config):
    """just_exited_warmup is False on 6th+ question."""
    for _ in range(5):
        engine.run("lbc", _make_observation(), config)
    ctx = engine.run("lbc", _make_observation(), config)
    assert ctx.just_exited_warmup is False


def test_run_bloom_step_uses_warmup_step_during_warmup(engine, config):
    """bloom_step = warmup_step (0.1) during warmup."""
    obs = _make_observation()
    ctx = engine.run("lbc", obs, config)
    assert ctx.bloom_step == 0.1


def test_run_bloom_step_uses_normal_step_after_warmup(engine, config):
    """bloom_step = bloom_update_step (0.05) after warmup (5th question)."""
    for _ in range(4):
        engine.run("lbc", _make_observation(), config)
    ctx = engine.run("lbc", _make_observation(), config)
    assert ctx.bloom_step == 0.05


def test_run_does_not_mutate_belief_state(engine, config):
    """ObservationEngine.run() does NOT touch BeliefState (no state arg)."""
    obs = _make_observation()
    # No state argument - structurally cannot mutate BeliefState
    ctx = engine.run("lbc", obs, config)
    assert ctx is not None


# ── warmup state machine ────────────────────────────────────────────────


def test_is_warmup_true_initially(engine, config):
    assert engine.is_warmup("lbc", config) is True


def test_is_warmup_false_after_n(engine, config):
    for _ in range(5):
        engine.run("lbc", _make_observation(), config)
    assert engine.is_warmup("lbc", config) is False


def test_warmup_remaining(engine, config):
    assert engine.warmup_remaining("lbc", config) == 5
    engine.run("lbc", _make_observation(), config)
    assert engine.warmup_remaining("lbc", config) == 4


def test_warmup_progress_shape(engine, config):
    progress = engine.warmup_progress("lbc", config)
    assert set(progress.keys()) == {"is_warmup", "warmup_remaining", "warmup_total", "warmup_count"}


# ── probe state machine ─────────────────────────────────────────────────


def test_should_probe_now_false_during_warmup(engine, config):
    """Probe is disabled during warmup."""
    engine.run("lbc", _make_observation(), config)
    assert engine.should_probe_now("lbc", config) is False


def test_should_probe_now_true_after_interval(engine, config):
    """After warmup + probe_interval questions, should_probe_now=True.

    Warmup: 4 questions (5th exits).
    Then probe_due_in initialized to 8 (probe_interval) on 5th question.
    Each subsequent question decrements probe_due_in by 1.
    After 8 more questions (5th through 12th), probe_due_in reaches 0.
    """
    # warmup (4 questions, 5th exits)
    for _ in range(4):
        engine.run("lbc", _make_observation(), config)
    # 5th question: just_exited_warmup, probe_due_in = 8 (init), then decrement to 7
    # 6th: 7->6, 7th: 6->5, ... 12th: 1->0
    for _ in range(8):
        if engine.should_probe_now("lbc", config):
            break
        engine.run("lbc", _make_observation(), config)
    assert engine.should_probe_now("lbc", config) is True


def test_consume_probe_resets_due_in(engine, config):
    """consume_probe resets _probe_due_in to probe_interval."""
    for _ in range(4):
        engine.run("lbc", _make_observation(), config)
    # Get to probe time (8 questions after warmup exit)
    for _ in range(8):
        if engine.should_probe_now("lbc", config):
            break
        engine.run("lbc", _make_observation(), config)
    assert engine.should_probe_now("lbc", config) is True
    engine.consume_probe("lbc", config)
    assert engine.should_probe_now("lbc", config) is False
    assert engine._probe_count["lbc"] == 1


# ── reset_student ──────────────────────────────────────────────────────


def test_reset_student_clears_warmup_count(engine, config):
    engine.run("lbc", _make_observation(), config)
    assert engine._warmup_count.get("lbc") == 1
    engine.reset_student("lbc")
    assert "lbc" not in engine._warmup_count


def test_reset_student_clears_probe_state(engine, config):
    for _ in range(5):
        engine.run("lbc", _make_observation(), config)
    engine.reset_student("lbc")
    assert "lbc" not in engine._probe_due_in
    assert "lbc" not in engine._probe_count


def test_reset_student_idempotent(engine):
    """reset_student on unknown student is a no-op."""
    engine.reset_student("unknown")
    # No exception
