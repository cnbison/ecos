"""v0.81.0-b: BeliefUpdator + BeliefEngine EventLog wiring tests.

Tests:
- event_log=None (default): no events logged, all callers unchanged
- event_log attached: apply() persists LearningEvent
- log_event=False suppresses logging (replay path)
- payload shape: event_id matches, student_id, timestamp, source, event_type
- BeliefEngine.update propagates log_event to BeliefUpdator
- End-to-end: BeliefEngine.update with event_log -> EventLog has event

Total: 12 tests.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

import pytest

from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig, Observation
from ecos.cta.belief_updater import BeliefUpdator
from ecos.cta.event_log import EventLog, LearningEvent
from ecos.cta.inference_engine import InferenceResult
from ecos.cta.state_engine import StateEngine
from ecos.cta.belief_state import (
    BeliefState,
    BloomLevel,
    BloomProfileState,
    ConfidenceDimensionState,
    LearningDNAState,
    TrajectoryState,
)


@pytest.fixture
def clean_state():
    """Fresh BeliefState for testing."""
    import numpy as np
    state = BeliefState(student_id="student_test_001")
    state.theta_mean = np.zeros(5)
    state.theta_cov = np.eye(5)
    state.bloom_profile = BloomProfileState()
    state.bloom_profile.update_dominant()
    state.learning_dna = LearningDNAState()
    state.trajectory = TrajectoryState()
    state.overall_confidence = 0.0
    state.last_updated = datetime.now()
    if not isinstance(state.C, ConfidenceDimensionState):
        state.C = ConfidenceDimensionState(dimension="C")
    return state


@pytest.fixture
def sample_observation():
    """Sample Observation for tests."""
    return Observation(
        skill_id="variables",
        problem_id="PB-Q1",
        correct=True,
        score=1.0,
        bloom_level=BloomLevel.APPLY,
        explanation_text="x = 5",
        timestamp=datetime(2026, 8, 10, 14, 30, 0),
    )


@pytest.fixture
def sample_inference_result():
    """Minimal InferenceResult for BeliefUpdator.apply (most fields None)."""
    return InferenceResult(
        theta_mean=None,
        theta_cov=None,
        dim_updates={},
        bloom_field_updates={},
        bloom_dominant_recompute=False,
        bloom_confidence=None,
        bloom_evidence_id=None,
        llm_perception_bloom_target=None,
        llm_perception_dominant_recompute=False,
        llm_perception_c_confidence=None,
        llm_misc_hit=None,
        llm_misc_illusory_flag=False,
        llm_misc_c_discount_factor=None,
        llm_misc_c_mastery_prob=None,
        llm_misc_c_mastered=None,
        llm_misc_c_evidence_id=None,
        tc_skill_id=None,
        tc_state=None,
        overall_confidence=None,
        trajectory_maxlen=None,
        last_updated=datetime(2026, 8, 10, 14, 30, 0),
    )


# ─── BeliefUpdator direct tests (6) ─────────────────────────────────────────


def test_belief_updator_init_default_no_event_log():
    """BeliefUpdator with no event_log should have event_log=None."""
    se = StateEngine()
    updator = BeliefUpdator(se)
    assert updator.event_log is None


def test_belief_updator_init_accepts_event_log():
    """BeliefUpdator with event_log should store it."""
    se = StateEngine()
    log = EventLog.in_memory()
    updator = BeliefUpdator(se, event_log=log)
    assert updator.event_log is log


def test_apply_with_no_event_log_works(clean_state, sample_observation, sample_inference_result):
    """Without event_log, apply() should still work (no logging, just mutation)."""
    se = StateEngine()
    updator = BeliefUpdator(se)  # no event_log
    event_id = updator.apply(
        clean_state, sample_inference_result, sample_observation, history_entry={}
    )
    assert event_id.startswith("evt_")
    # No event was logged (we can't verify directly without event_log, but apply didn't crash)


def test_apply_with_event_log_logs_event(
    clean_state, sample_observation, sample_inference_result
):
    """With event_log, apply() should persist a LearningEvent."""
    se = StateEngine()
    log = EventLog.in_memory()
    updator = BeliefUpdator(se, event_log=log)
    event_id = updator.apply(
        clean_state, sample_inference_result, sample_observation, history_entry={}
    )
    events = log.load_events("student_test_001")
    assert len(events) == 1
    assert events[0].event_id == event_id
    assert events[0].student_id == "student_test_001"
    assert events[0].source == "belief_updater"
    assert events[0].event_type == "observation"


def test_apply_with_log_event_false_suppresses(
    clean_state, sample_observation, sample_inference_result
):
    """log_event=False should suppress event logging (replay path)."""
    se = StateEngine()
    log = EventLog.in_memory()
    updator = BeliefUpdator(se, event_log=log)
    updator.apply(
        clean_state,
        sample_inference_result,
        sample_observation,
        history_entry={},
        log_event=False,
    )
    events = log.load_events("student_test_001")
    assert len(events) == 0  # suppressed


def test_apply_event_payload_contains_observation(
    clean_state, sample_observation, sample_inference_result
):
    """Event payload should be the serialized Observation (via to_dict)."""
    se = StateEngine()
    log = EventLog.in_memory()
    updator = BeliefUpdator(se, event_log=log)
    updator.apply(clean_state, sample_inference_result, sample_observation, history_entry={})
    events = log.load_events("student_test_001")
    payload = events[0].payload
    assert payload["skill_id"] == "variables"
    assert payload["problem_id"] == "PB-Q1"
    assert payload["correct"] is True
    assert payload["score"] == 1.0
    assert payload["bloom_level"] == "APPLY"


# ─── BeliefEngine facade tests (4) ──────────────────────────────────────────


def test_belief_engine_init_default_no_event_log():
    """BeliefEngine without event_log should not log."""
    engine = BeliefEngine()
    assert engine._event_log is None
    assert engine._belief_updater.event_log is None


def test_belief_engine_init_accepts_event_log():
    """BeliefEngine with event_log should propagate to BeliefUpdator."""
    log = EventLog.in_memory()
    engine = BeliefEngine(event_log=log)
    assert engine._event_log is log
    assert engine._belief_updater.event_log is log


def test_belief_engine_update_logs_event_via_event_log(
    clean_state, sample_observation
):
    """BeliefEngine.update with event_log should persist LearningEvent."""
    log = EventLog.in_memory()
    engine = BeliefEngine(event_log=log)
    # Need to reset warmup state since BeliefEngine has internal state across tests
    engine.reset_student("student_test_001")
    engine.update(clean_state, sample_observation)
    events = log.load_events("student_test_001")
    assert len(events) >= 1
    assert events[-1].source == "belief_updater"
    assert events[-1].event_type == "observation"


def test_belief_engine_update_log_event_false_suppresses(
    clean_state, sample_observation
):
    """BeliefEngine.update(log_event=False) should suppress event logging."""
    log = EventLog.in_memory()
    engine = BeliefEngine(event_log=log)
    engine.reset_student("student_test_001")
    engine.update(clean_state, sample_observation, log_event=False)
    events = log.load_events("student_test_001")
    assert len(events) == 0


# ─── Observation to_dict / from_dict round-trip tests (2) ───────────────────


def test_observation_to_dict_serializes_all_fields(sample_observation):
    """Observation.to_dict should serialize all fields (BloomLevel -> name, datetime -> ISO)."""
    d = sample_observation.to_dict()
    assert d["skill_id"] == "variables"
    assert d["problem_id"] == "PB-Q1"
    assert d["correct"] is True
    assert d["score"] == 1.0
    assert d["bloom_level"] == "APPLY"
    assert d["explanation_text"] == "x = 5"
    assert d["timestamp"] == "2026-08-10T14:30:00"


def test_observation_from_dict_round_trips(sample_observation):
    """Observation.from_dict(to_dict()) should preserve all fields."""
    d = sample_observation.to_dict()
    restored = Observation.from_dict(d)
    assert restored.skill_id == sample_observation.skill_id
    assert restored.problem_id == sample_observation.problem_id
    assert restored.correct == sample_observation.correct
    assert restored.score == sample_observation.score
    assert restored.bloom_level == sample_observation.bloom_level
    assert restored.timestamp == sample_observation.timestamp


def test_observation_from_dict_invalid_bloom_level_falls_back():
    """Observation.from_dict with invalid bloom_level name should fall back to APPLY."""
    obs = Observation.from_dict({"skill_id": "x", "problem_id": "p", "bloom_level": "NONEXISTENT"})
    assert obs.bloom_level == BloomLevel.APPLY
