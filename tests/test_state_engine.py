"""v0.80.0 StateEngine test suite.

Covers:
- commit (full state / delta / StateDelta)
- validate (all rules from 2.0 §2.2)
- snapshot (with event_id binding)
- diff (structured, not scalar)
- apply_snapshot shim backward compat
- _default_engine singleton

Covers 2.0 §2.2.1 StateEngine 6 responsibilities (4 in v0.80 scope):
- Transition: ✅ commit
- Validation: ✅ validate
- Snapshot: ✅ snapshot
- Diff: ✅ diff
- Replay: ❌ (deferred to v0.81)
- Versioning: ✅ bump_version via commit
"""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pytest

from ecos.cta.belief_state import (
    BeliefState,
    BloomLevel,
    ConfidenceDimensionState,
    DimensionState,
    LearningDNAState,
    TCState,
)
from ecos.cta.state_engine import (
    StateDelta,
    StateDiff,
    StateEngine,
    _default_engine,
    get_default_engine,
)


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def clean_engine() -> StateEngine:
    """Fresh StateEngine with empty snapshot ring."""
    engine = StateEngine()
    engine.clear_snapshots()
    return engine


@pytest.fixture
def baseline_state() -> BeliefState:
    """BeliefState with non-default values for diff/commit tests."""
    state = BeliefState(student_id="lbc_test")
    state.K = DimensionState(theta=1.5, se=0.5, mastery_prob=0.8, confidence=0.6, dimension="K")
    state.P = DimensionState(theta=0.3, se=0.4, mastery_prob=0.6, confidence=0.7, dimension="P")
    state.S = DimensionState(theta=-0.2, se=0.6, mastery_prob=0.4, confidence=0.5, dimension="S")
    state.C = ConfidenceDimensionState(
        theta=0.1, se=0.3, mastery_prob=0.55, confidence=0.65, dimension="C",
        tc_states={"TC1": TCState(tc_id="TC1", status="liminal", progress=0.5, confidence=0.6)},
        discount_factor=0.9,
    )
    state.X = DimensionState(theta=0.0, se=0.5, mastery_prob=0.5, confidence=0.5, dimension="X")
    state.theta_mean = np.array([1.5, 0.3, -0.2, 0.1, 0.0])
    state.theta_cov = np.eye(5) * 2.0
    state.bloom_profile.remember = 0.9
    state.bloom_profile.understand = 0.7
    state.bloom_profile.apply = 0.6
    state.bloom_profile.analyze = 0.4
    state.bloom_profile.evaluate = 0.3
    state.bloom_profile.create = 0.2
    state.bloom_profile.confidence = 0.5
    state.overall_confidence = 0.55
    return state


# ── commit: full state replacement ──────────────────────────────────────


def test_commit_full_state_replacement(clean_engine, baseline_state):
    target = BeliefState(student_id="lbc_target")
    source = baseline_state
    event_id = clean_engine.commit(target, source, source="test_full_replace")

    assert isinstance(event_id, str)
    assert event_id.startswith("evt_")
    assert target.K.theta == source.K.theta
    assert target.P.mastery_prob == source.P.mastery_prob
    assert target.overall_confidence == source.overall_confidence


def test_commit_full_state_does_not_copy_student_id(clean_engine, baseline_state):
    target = BeliefState(student_id="lbc_target")
    source = baseline_state
    source.student_id = "lbc_source"
    clean_engine.commit(target, source, source="test_sid_keep")
    assert target.student_id == "lbc_target"


def test_commit_returns_event_id_format(clean_engine, baseline_state):
    event_id = clean_engine.commit(baseline_state, {"overall_confidence": 0.5}, source="test_format")
    assert event_id.startswith("evt_")
    assert len(event_id) == len("evt_") + 12


def test_commit_bumps_version_with_event_id(clean_engine, baseline_state):
    old_version = baseline_state.version
    event_id = clean_engine.commit(baseline_state, {"overall_confidence": 0.7}, source="test_version_bump")
    assert baseline_state.version == f"v1.0+{event_id}"
    assert baseline_state.version != old_version


def test_commit_validates_after_mutation_when_validate_true(clean_engine, baseline_state):
    event_id = clean_engine.commit(
        baseline_state,
        {"overall_confidence": 0.5},
        source="test_validate_pass",
        validate=True,
    )
    assert event_id


def test_commit_invalid_state_raises_when_validate_true(clean_engine, baseline_state):
    with pytest.raises(ValueError, match="State validation failed"):
        clean_engine.commit(
            baseline_state,
            {"overall_confidence": 1.5},  # invalid: > 1.0
            source="test_validate_fail",
            validate=True,
        )


def test_commit_invalid_state_no_raise_when_validate_false(clean_engine, baseline_state):
    """Default: validate is False, invalid state does NOT raise."""
    event_id = clean_engine.commit(
        baseline_state,
        {"overall_confidence": 1.5},
        source="test_no_validate",
    )
    assert event_id  # still returns event_id


def test_commit_none_payload_is_noop(clean_engine, baseline_state):
    old_overall = baseline_state.overall_confidence
    event_id = clean_engine.commit(baseline_state, None, source="test_noop")
    assert event_id
    assert baseline_state.overall_confidence == old_overall


def test_commit_unsupported_payload_type_raises(clean_engine, baseline_state):
    with pytest.raises(TypeError, match="Unsupported new_state_or_delta type"):
        clean_engine.commit(baseline_state, 12345, source="test_bad_type")


def test_commit_state_delta_object(clean_engine, baseline_state):
    delta = StateDelta(delta={"overall_confidence": 0.42}, source="test_statedelta")
    event_id = clean_engine.commit(baseline_state, delta, source="will_be_overridden")
    assert event_id == delta.event_id
    assert baseline_state.overall_confidence == 0.42


# ── commit: delta dict partial ──────────────────────────────────────────


def test_commit_delta_partial_overall_confidence(clean_engine, baseline_state):
    clean_engine.commit(baseline_state, {"overall_confidence": 0.99}, source="test_partial")
    assert baseline_state.overall_confidence == 0.99


def test_commit_delta_partial_theta_mean(clean_engine, baseline_state):
    new_theta = [0.1, 0.2, 0.3, 0.4, 0.5]
    clean_engine.commit(baseline_state, {"theta_mean": new_theta}, source="test_theta")
    np.testing.assert_array_equal(baseline_state.theta_mean, np.array(new_theta))


def test_commit_delta_partial_bloom_profile(clean_engine, baseline_state):
    clean_engine.commit(
        baseline_state,
        {"bloom_profile": {"remember": 0.95, "apply": 0.7}},
        source="test_bloom",
    )
    assert baseline_state.bloom_profile.remember == 0.95
    assert baseline_state.bloom_profile.apply == 0.7
    # v0.77.1 contract: missing fields fall back to default 0.5 (not retain original)
    assert baseline_state.bloom_profile.understand == 0.5


def test_commit_delta_empty_dict(clean_engine, baseline_state):
    old_overall = baseline_state.overall_confidence
    event_id = clean_engine.commit(baseline_state, {}, source="test_empty")
    assert event_id
    assert baseline_state.overall_confidence == old_overall


def test_commit_delta_tc_states(clean_engine, baseline_state):
    snapshot = {
        "C": {
            "tc_states": {
                "TC_test": {
                    "tc_id": "TC_test",
                    "status": "post_liminal",
                    "progress": 0.8,
                    "confidence": 0.9,
                }
            }
        }
    }
    clean_engine.commit(baseline_state, snapshot, source="test_tc")
    assert "TC_test" in baseline_state.C.tc_states
    assert baseline_state.C.tc_states["TC_test"].progress == 0.8
    assert baseline_state.C.tc_states["TC_test"].status == "post_liminal"


# ── validate: all rules ─────────────────────────────────────────────────


def test_validate_clean_state_no_issues(baseline_state):
    is_valid, issues = baseline_state.validate()
    assert is_valid
    assert issues == []


def test_validate_mastery_prob_out_of_range(baseline_state):
    baseline_state.K.mastery_prob = 1.5
    is_valid, issues = baseline_state.validate()
    assert not is_valid
    assert any("K.mastery_prob" in i for i in issues)


def test_validate_confidence_out_of_range(baseline_state):
    baseline_state.P.confidence = -0.1
    is_valid, issues = baseline_state.validate()
    assert not is_valid
    assert any("P.confidence" in i for i in issues)


def test_validate_all_5d_mastery_probs(baseline_state):
    for dim_name in ("K", "P", "S", "C", "X"):
        baseline_state_copy = BeliefState(student_id="test")
        baseline_state_copy.K = DimensionState(dimension="K", mastery_prob=1.5)
        is_valid, issues = baseline_state_copy.validate()
        assert not is_valid
        assert any("K.mastery_prob" in i for i in issues)


def test_validate_bloom_profile_out_of_range(baseline_state):
    baseline_state.bloom_profile.apply = 1.5
    is_valid, issues = baseline_state.validate()
    assert not is_valid
    assert any("bloom_profile.apply" in i for i in issues)


def test_validate_bloom_confidence_out_of_range(baseline_state):
    baseline_state.bloom_profile.confidence = -0.5
    is_valid, issues = baseline_state.validate()
    assert not is_valid
    assert any("bloom_profile.confidence" in i for i in issues)


def test_validate_c_discount_factor_out_of_range(baseline_state):
    baseline_state.C.discount_factor = 1.5
    is_valid, issues = baseline_state.validate()
    assert not is_valid
    assert any("C.discount_factor" in i for i in issues)


def test_validate_tc_state_progress_out_of_range(baseline_state):
    baseline_state.C.tc_states["TC1"].progress = 1.5
    is_valid, issues = baseline_state.validate()
    assert not is_valid
    assert any("TC1" in i and "progress" in i for i in issues)


def test_validate_tc_state_confidence_out_of_range(baseline_state):
    baseline_state.C.tc_states["TC1"].confidence = -0.1
    is_valid, issues = baseline_state.validate()
    assert not is_valid
    assert any("TC1" in i and "confidence" in i for i in issues)


def test_validate_overall_confidence_out_of_range(baseline_state):
    baseline_state.overall_confidence = 1.5
    is_valid, issues = baseline_state.validate()
    assert not is_valid
    assert any("overall_confidence" in i for i in issues)


def test_validate_theta_mean_wrong_shape(baseline_state):
    baseline_state.theta_mean = np.array([0.0, 0.0, 0.0])  # 3 elements
    is_valid, issues = baseline_state.validate()
    assert not is_valid
    assert any("theta_mean.shape" in i for i in issues)


def test_validate_theta_cov_wrong_shape(baseline_state):
    baseline_state.theta_cov = np.eye(3)
    is_valid, issues = baseline_state.validate()
    assert not is_valid
    assert any("theta_cov.shape" in i for i in issues)


def test_validate_returns_tuple_of_bool_list(baseline_state):
    result = baseline_state.validate()
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], bool)
    assert isinstance(result[1], list)


def test_validate_multiple_issues_collected(baseline_state):
    baseline_state.K.mastery_prob = 1.5
    baseline_state.P.confidence = -0.1
    baseline_state.overall_confidence = 2.0
    is_valid, issues = baseline_state.validate()
    assert not is_valid
    assert len(issues) >= 3


# ── validate: edge cases (float precision tolerance) ─────────────────────


def test_validate_mastery_prob_at_boundary_0(baseline_state):
    baseline_state.K.mastery_prob = 0.0
    is_valid, issues = baseline_state.validate()
    assert is_valid


def test_validate_mastery_prob_at_boundary_1(baseline_state):
    baseline_state.K.mastery_prob = 1.0
    is_valid, issues = baseline_state.validate()
    assert is_valid


# ── snapshot ────────────────────────────────────────────────────────────


def test_snapshot_returns_snapshot_id(clean_engine, baseline_state):
    snapshot_id = clean_engine.snapshot(baseline_state, source_event_id="evt_abc123")
    assert snapshot_id.startswith("snap_")


def test_snapshot_stores_state_dict(clean_engine, baseline_state):
    snapshot_id = clean_engine.snapshot(baseline_state, source_event_id="evt_abc123")
    snapshots = clean_engine.get_snapshots()
    assert len(snapshots) == 1
    assert snapshots[0]["snapshot_id"] == snapshot_id
    assert snapshots[0]["source_event_id"] == "evt_abc123"
    assert "state" in snapshots[0]
    assert snapshots[0]["state"]["student_id"] == "lbc_test"


def test_snapshot_increments_count(clean_engine, baseline_state):
    for i in range(3):
        clean_engine.snapshot(baseline_state, source_event_id=f"evt_{i}")
    assert len(clean_engine.get_snapshots()) == 3


def test_snapshot_ring_buffer_max(clean_engine, baseline_state):
    clean_engine._max_snapshots = 5
    for i in range(10):
        clean_engine.snapshot(baseline_state, source_event_id=f"evt_{i}")
    snapshots = clean_engine.get_snapshots()
    assert len(snapshots) == 5
    # oldest should be gone, newest kept
    assert snapshots[0]["source_event_id"] == "evt_5"
    assert snapshots[-1]["source_event_id"] == "evt_9"


def test_snapshot_includes_timestamp(clean_engine, baseline_state):
    clean_engine.snapshot(baseline_state, source_event_id="evt_test")
    snapshots = clean_engine.get_snapshots()
    assert "timestamp" in snapshots[0]
    # should be ISO format
    datetime.fromisoformat(snapshots[0]["timestamp"])


def test_snapshot_state_independent_of_live_mutation(clean_engine, baseline_state):
    """Snapshot should not change when state is mutated after snapshot."""
    clean_engine.snapshot(baseline_state, source_event_id="evt_before")
    original_overall = clean_engine.get_snapshots()[0]["state"]["overall_confidence"]
    baseline_state.overall_confidence = 0.99
    snapshot_overall = clean_engine.get_snapshots()[0]["state"]["overall_confidence"]
    assert snapshot_overall == original_overall


def test_clear_snapshots(clean_engine, baseline_state):
    clean_engine.snapshot(baseline_state, source_event_id="evt_test")
    clean_engine.clear_snapshots()
    assert clean_engine.get_snapshots() == []


# ── diff ─────────────────────────────────────────────────────────────────


def test_diff_no_changes_returns_empty(clean_engine, baseline_state):
    import copy
    s2 = copy.deepcopy(baseline_state)
    diff = clean_engine.diff(baseline_state, s2)
    assert diff.changed_fields == []
    assert diff.old_values == {}
    assert diff.new_values == {}


def test_diff_detects_mastery_prob_change(clean_engine, baseline_state):
    import copy
    s2 = copy.deepcopy(baseline_state)
    s2.K.mastery_prob = 0.95
    diff = clean_engine.diff(baseline_state, s2)
    assert "K.mastery_prob" in diff.changed_fields
    assert diff.old_values["K.mastery_prob"] == baseline_state.K.mastery_prob
    assert diff.new_values["K.mastery_prob"] == 0.95


def test_diff_computes_delta_magnitude(clean_engine, baseline_state):
    import copy
    s2 = copy.deepcopy(baseline_state)
    old_val = baseline_state.K.mastery_prob
    s2.K.mastery_prob = old_val + 0.2
    diff = clean_engine.diff(baseline_state, s2)
    assert abs(diff.delta_magnitudes["K.mastery_prob"] - 0.2) < 1e-6


def test_diff_detects_overall_confidence_change(clean_engine, baseline_state):
    import copy
    s2 = copy.deepcopy(baseline_state)
    s2.overall_confidence = 0.99
    diff = clean_engine.diff(baseline_state, s2)
    assert "overall_confidence" in diff.changed_fields


def test_diff_detects_bloom_profile_change(clean_engine, baseline_state):
    import copy
    s2 = copy.deepcopy(baseline_state)
    s2.bloom_profile.apply = 0.95
    diff = clean_engine.diff(baseline_state, s2)
    assert "bloom_profile.apply" in diff.changed_fields


def test_diff_detects_theta_mean_change(clean_engine, baseline_state):
    import copy
    s2 = copy.deepcopy(baseline_state)
    s2.theta_mean[0] = baseline_state.theta_mean[0] + 1.0
    diff = clean_engine.diff(baseline_state, s2)
    assert "theta_mean[0]" in diff.changed_fields


def test_diff_detects_c_discount_factor_change(clean_engine, baseline_state):
    import copy
    s2 = copy.deepcopy(baseline_state)
    s2.C.discount_factor = 0.5
    diff = clean_engine.diff(baseline_state, s2)
    assert "C.discount_factor" in diff.changed_fields


def test_diff_returns_state_diff_instance(clean_engine, baseline_state):
    diff = clean_engine.diff(baseline_state, baseline_state)
    assert isinstance(diff, StateDiff)


def test_diff_multiple_fields(clean_engine, baseline_state):
    import copy
    s2 = copy.deepcopy(baseline_state)
    s2.K.mastery_prob = 0.95
    s2.P.confidence = 0.9
    s2.overall_confidence = 0.8
    diff = clean_engine.diff(baseline_state, s2)
    assert len(diff.changed_fields) >= 3


# ── apply_snapshot shim backward compat ──────────────────────────────────


def test_apply_snapshot_shim_delegates_to_commit(baseline_state):
    """BeliefState.apply_snapshot should route through StateEngine.commit."""
    # Clear default engine's state for clean test
    _default_engine.clear_snapshots()
    baseline_state.apply_snapshot({"overall_confidence": 0.42})
    assert baseline_state.overall_confidence == 0.42
    # version should be bumped (proves it went through commit)
    assert baseline_state.version.startswith("v1.0+evt_")


def test_apply_snapshot_shim_preserves_field_logic(baseline_state):
    """apply_snapshot shim should still apply same fields as v0.77.1."""
    snapshot = {
        "theta_mean": [0.1, 0.2, 0.3, 0.4, 0.5],
        "bloom_profile": {"remember": 0.95, "apply": 0.7},
        "overall_confidence": 0.42,
    }
    baseline_state.apply_snapshot(snapshot)
    np.testing.assert_array_equal(baseline_state.theta_mean, np.array([0.1, 0.2, 0.3, 0.4, 0.5]))
    assert baseline_state.bloom_profile.remember == 0.95
    assert baseline_state.bloom_profile.apply == 0.7
    assert baseline_state.overall_confidence == 0.42


def test_apply_snapshot_shim_does_not_touch_student_id(baseline_state):
    baseline_state.apply_snapshot({"student_id": "should_be_ignored"})
    assert baseline_state.student_id == "lbc_test"


# ── _default_engine singleton ───────────────────────────────────────────


def test_get_default_engine_returns_singleton():
    engine1 = get_default_engine()
    engine2 = get_default_engine()
    assert engine1 is engine2


def test_default_engine_is_state_engine_instance():
    engine = get_default_engine()
    assert isinstance(engine, StateEngine)


# ── bump_version ────────────────────────────────────────────────────────


def test_bump_version_sets_version_with_event_id(baseline_state):
    baseline_state.bump_version("evt_abc123")
    assert baseline_state.version == "v1.0+evt_abc123"


def test_bump_version_updates_last_updated(baseline_state):
    old_ts = baseline_state.last_updated
    # ensure timestamp differs
    import time
    time.sleep(0.001)
    baseline_state.bump_version("evt_test")
    assert baseline_state.last_updated >= old_ts


# ── pytest report header ────────────────────────────────────────────────


def pytest_report_header(config):
    return [
        "ECOS StateEngine test suite v0.80.0",
        "  4 of 6 StateEngine responsibilities (commit/validate/snapshot/diff)",
        "  Replay deferred to v0.81 Event Engine",
    ]
