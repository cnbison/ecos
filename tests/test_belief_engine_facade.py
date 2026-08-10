"""v0.80.0-c BeliefEngine facade test suite.

Critical invariant: BeliefEngine is a facade over 4 layers
(ObservationEngine + FeatureExtractor + InferenceEngine + BeliefUpdator).
All 14 production callers + ~230 tests should pass unchanged.

Covers:
- __getattr__ forwarding for web/api/belief.py:189-191 compat (engine._warmup_count etc)
- warmup/probe methods delegate to ObservationEngine
- reset_student delegates to both ObservationEngine + FeatureExtractor
- update() orchestrates 4 layers
- create_initial_state still produces valid BeliefState
"""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pytest

from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig, Observation
from ecos.cta.belief_state import BloomLevel


@pytest.fixture
def engine() -> BeliefEngine:
    return BeliefEngine(llm_client=None)


# ── __getattr__ forwarding (critical: web/api/belief.py:189-191 compat) ───


def test_getattr_forwards_warmup_count(engine):
    """engine._warmup_count forwards to ObservationEngine._warmup_count."""
    assert engine._warmup_count is engine._observation_engine._warmup_count


def test_getattr_forwards_probe_due_in(engine):
    assert engine._probe_due_in is engine._observation_engine._probe_due_in


def test_getattr_forwards_probe_count(engine):
    assert engine._probe_count is engine._observation_engine._probe_count


def test_getattr_forwards_warmup_pool_cursor(engine):
    assert engine._warmup_pool_cursor is engine._observation_engine._warmup_pool_cursor


def test_getattr_forwards_response_history(engine):
    """engine._response_history forwards to FeatureExtractor._response_history."""
    assert engine._response_history is engine._feature_extractor._response_history


def test_getattr_writes_propagate_to_observation_engine(engine):
    """web/api/belief.py:189 pattern: engine._warmup_count[sid] = X.

    Must mutate ObservationEngine's dict (same object).
    """
    engine._warmup_count["lbc_test"] = 42
    assert engine._observation_engine._warmup_count["lbc_test"] == 42


def test_getattr_writes_propagate_to_feature_extractor(engine):
    """web/api/belief.py:224 pattern: engine._response_history[sid] = history.

    Must mutate FeatureExtractor's dict (same object).
    """
    history = [{"problem_id": "P001", "correct": 1, "score": 1.0}]
    engine._response_history["lbc_test"] = history
    assert engine._feature_extractor._response_history["lbc_test"] is history


def test_getattr_raises_for_unknown_attr(engine):
    """Unknown attributes raise AttributeError (not silently return None)."""
    with pytest.raises(AttributeError):
        _ = engine.totally_unknown_attr


def test_getattr_does_not_shadow_methods(engine):
    """Methods (is_warmup, update, etc) are NOT forwarded (found via normal lookup)."""
    assert callable(engine.is_warmup)
    assert callable(engine.update)
    assert callable(engine.create_initial_state)


# ── warmup/probe methods delegate to ObservationEngine ─────────────────


def test_is_warmup_delegates(engine):
    assert engine.is_warmup("lbc") is True  # fresh student
    assert engine._observation_engine._warmup_count.get("lbc", 0) == 0


def test_warmup_progress_delegates(engine):
    progress = engine.warmup_progress("lbc")
    assert progress["is_warmup"] is True
    assert progress["warmup_count"] == 0


def test_should_probe_now_delegates(engine):
    """During warmup, should_probe_now=False."""
    assert engine.should_probe_now("lbc") is False


def test_consume_probe_delegates(engine):
    """consume_probe updates ObservationEngine._probe_count."""
    engine.consume_probe("lbc")
    assert engine._observation_engine._probe_count.get("lbc") == 1


def test_probe_progress_delegates(engine):
    progress = engine.probe_progress("lbc")
    assert "should_probe" in progress
    assert "probe_due_in" in progress
    assert "probe_count" in progress


# ── reset_student delegates to both layers ─────────────────────────────


def test_reset_student_clears_feature_extractor(engine):
    """reset_student clears _feature_extractor._response_history."""
    obs = Observation(
        skill_id="addition", problem_id="P001", correct=True, score=1.0,
        bloom_level=BloomLevel.APPLY, timestamp=datetime(2026, 8, 10),
    )
    state = engine.create_initial_state("lbc")
    engine.update(state, obs)
    assert len(engine._feature_extractor.get_history("lbc")) == 1
    engine.reset_student("lbc")
    assert engine._feature_extractor.get_history("lbc") == []


def test_reset_student_clears_observation_engine(engine):
    """reset_student clears _observation_engine._warmup_count."""
    obs = Observation(
        skill_id="addition", problem_id="P001", correct=True, score=1.0,
        bloom_level=BloomLevel.APPLY, timestamp=datetime(2026, 8, 10),
    )
    state = engine.create_initial_state("lbc")
    engine.update(state, obs)
    assert engine._observation_engine._warmup_count.get("lbc") == 1
    engine.reset_student("lbc")
    assert "lbc" not in engine._observation_engine._warmup_count


# ── update() orchestrates 4 layers ─────────────────────────────────────


def test_update_runs_all_4_layers(engine):
    """update() calls ObservationEngine.run + FeatureExtractor.extract + InferenceEngine.run + BeliefUpdator.apply."""
    state = engine.create_initial_state("lbc")
    obs = Observation(
        skill_id="addition", problem_id="P001", correct=True, score=1.0,
        bloom_level=BloomLevel.APPLY, timestamp=datetime(2026, 8, 10, 12, 0, 0),
    )

    # Pre-update: state at version v1.0
    pre_version = state.version
    pre_warmup = engine._observation_engine._warmup_count.get("lbc", 0)
    pre_history_len = len(engine._feature_extractor.get_history("lbc"))

    engine.update(state, obs)

    # Post-update: all 4 layers executed
    # Layer 1 (ObservationEngine): _warmup_count incremented
    assert engine._observation_engine._warmup_count["lbc"] == pre_warmup + 1
    # Layer 2 (FeatureExtractor): history appended
    assert len(engine._feature_extractor.get_history("lbc")) == pre_history_len + 1
    # Layer 3 (InferenceEngine): InferenceResult computed (state version bumped)
    assert state.version != pre_version
    # Layer 4 (BeliefUpdator): mutations applied
    assert state.bloom_profile.apply > 0  # default 0.5 + delta


def test_update_does_not_own_internal_state(engine):
    """BeliefEngine does NOT own _warmup_count / _response_history (moved to layers)."""
    assert "_warmup_count" not in engine.__dict__
    assert "_response_history" not in engine.__dict__
    assert "_probe_due_in" not in engine.__dict__
    assert "_probe_count" not in engine.__dict__
    assert "_warmup_pool_cursor" not in engine.__dict__


# ── create_initial_state ───────────────────────────────────────────────


def test_create_initial_state_returns_valid_state(engine):
    state = engine.create_initial_state("lbc_new")
    assert state.student_id == "lbc_new"
    assert state.theta_mean.shape == (5,)
    assert state.theta_cov.shape == (5, 5)
    assert state.bloom_profile is not None
    assert state.trajectory is not None


def test_create_initial_state_C_is_confidence_dim(engine):
    """C dimension must be ConfidenceDimensionState (含 misconception_hits)."""
    from ecos.cta.belief_state import ConfidenceDimensionState
    state = engine.create_initial_state("lbc_new")
    assert isinstance(state.C, ConfidenceDimensionState)


# ── perception_critic / misc_detector delegation ────────────────────────


def test_perception_critic_delegates_to_inference_engine(engine):
    """perception_critic property delegates to InferenceEngine (which lazy-inits PerceptionCritic)."""
    critic = engine.perception_critic
    assert critic is engine._inference_engine.perception_critic


def test_misc_detector_delegates_to_inference_engine(engine):
    critic = engine.misc_detector
    assert critic is engine._inference_engine.misc_detector


# ── get_bkt_mastery / get_theta / select_next_problem ─────────────────


def test_get_bkt_mastery(engine):
    """Default BKT p_init=0.1 for new skill."""
    assert engine.get_bkt_mastery("addition") == 0.1  # BKT default p_init


def test_get_theta(engine):
    state = engine.create_initial_state("lbc")
    theta = engine.get_theta(state)
    assert theta.shape == (5,)


def test_select_next_problem_returns_none(engine):
    """L3 CD-CAT is M2 W1 占位, returns None."""
    state = engine.create_initial_state("lbc")
    assert engine.select_next_problem(state) is None
