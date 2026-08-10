"""v0.80.0-c FeatureExtractor test suite.

Covers:
- extract() appends to response_history
- extract() returns {history, history_entry}
- response_history maxlen=100 (trims when exceeded)
- history_entry is last appended dict
- get_history / set_history / reset_student
"""
from __future__ import annotations

from datetime import datetime

import pytest

from ecos.cta.belief_engine import Observation
from ecos.cta.belief_state import BloomLevel
from ecos.cta.feature_extractor import FeatureExtractor
from ecos.cta.inference_engine import ObservationContext


@pytest.fixture
def extractor() -> FeatureExtractor:
    return FeatureExtractor()


def _make_observation(score: float = 1.0, problem_id: str = "P001") -> Observation:
    return Observation(
        skill_id="addition",
        problem_id=problem_id,
        correct=score >= 0.6,
        score=score,
        bloom_level=BloomLevel.APPLY,
        user_answer="42",
        correct_answer="42",
        ai_reasoning="correct",
        timestamp=datetime(2026, 8, 10, 12, 0, 0),
    )


def _make_ctx(score: float = 1.0, bloom: BloomLevel = BloomLevel.APPLY) -> ObservationContext:
    return ObservationContext(
        student_id="lbc_test",
        skill_id="addition",
        problem_id="P001",
        score=score,
        correct=score >= 0.6,
        bloom_level=bloom,
        in_warmup=False,
        just_exited_warmup=False,
        bloom_step=0.05,
        observation=_make_observation(score=score),
    )


# ── extract() basic ────────────────────────────────────────────────────


def test_extract_returns_dict_with_history_and_entry(extractor):
    obs = _make_observation()
    ctx = _make_ctx()
    result = extractor.extract("lbc", obs, ctx)
    assert "history" in result
    assert "history_entry" in result
    assert isinstance(result["history"], list)


def test_extract_appends_to_history(extractor):
    obs = _make_observation()
    ctx = _make_ctx()
    result = extractor.extract("lbc", obs, ctx)
    assert len(result["history"]) == 1


def test_extract_history_entry_is_last(extractor):
    obs = _make_observation()
    ctx = _make_ctx()
    result = extractor.extract("lbc", obs, ctx)
    assert result["history_entry"] is result["history"][-1]


def test_extract_accumulates_across_calls(extractor):
    for i in range(3):
        obs = _make_observation(problem_id=f"P{i:03d}")
        ctx = _make_ctx()
        extractor.extract("lbc", obs, ctx)
    assert len(extractor.get_history("lbc")) == 3


# ── extract() field correctness ────────────────────────────────────────


def test_extract_history_entry_has_required_fields(extractor):
    obs = _make_observation()
    ctx = _make_ctx()
    result = extractor.extract("lbc", obs, ctx)
    entry = result["history_entry"]
    assert entry["problem_id"] == "P001"
    assert entry["correct"] == 1  # int(correct)
    assert entry["score"] == 1.0
    assert entry["bloom_level"] == "APPLY"
    assert entry["user_answer"] == "42"
    assert entry["correct_answer"] == "42"
    assert entry["ai_reasoning"] == "correct"
    assert entry["timestamp"] == "2026-08-10T12:00:00"


def test_extract_records_partial_credit_score(extractor):
    """partial credit score is stored as float."""
    obs = _make_observation(score=0.7)
    ctx = _make_ctx(score=0.7)
    result = extractor.extract("lbc", obs, ctx)
    assert result["history_entry"]["score"] == 0.7
    assert result["history_entry"]["correct"] == 1  # 0.7 >= 0.6


def test_extract_records_wrong_answer(extractor):
    obs = _make_observation(score=0.0)
    ctx = _make_ctx(score=0.0)
    result = extractor.extract("lbc", obs, ctx)
    assert result["history_entry"]["score"] == 0.0
    assert result["history_entry"]["correct"] == 0  # 0.0 < 0.6


# ── maxlen=100 ─────────────────────────────────────────────────────────


def test_extract_trims_history_at_100(extractor):
    """response_history trims to last 100 entries when exceeded."""
    for i in range(105):
        obs = _make_observation(problem_id=f"P{i:03d}")
        ctx = _make_ctx()
        extractor.extract("lbc", obs, ctx)
    history = extractor.get_history("lbc")
    assert len(history) == 100
    # Should keep last 100 (P005 - P104)
    assert history[0]["problem_id"] == "P005"
    assert history[-1]["problem_id"] == "P104"


def test_extract_returns_history_after_trim(extractor):
    """When trim kicks in, returned history reflects trimmed list."""
    for i in range(105):
        obs = _make_observation(problem_id=f"P{i:03d}")
        ctx = _make_ctx()
        result = extractor.extract("lbc", obs, ctx)
    # After 105 calls, the last call's history should have 100 entries
    assert len(result["history"]) == 100


# ── multiple students isolated ─────────────────────────────────────────


def test_extract_isolates_students(extractor):
    """Each student has its own history list."""
    for sid in ["lbc1", "lbc2"]:
        obs = _make_observation()
        ctx = _make_ctx()
        ctx.student_id = sid
        extractor.extract(sid, obs, ctx)
    assert len(extractor.get_history("lbc1")) == 1
    assert len(extractor.get_history("lbc2")) == 1


# ── get_history / set_history / reset_student ──────────────────────────


def test_get_history_empty_for_unknown_student(extractor):
    assert extractor.get_history("unknown") == []


def test_set_history_replaces(extractor):
    """set_history replaces the entire list (DB restore path)."""
    history = [{"problem_id": "P001", "correct": 1, "score": 1.0, "bloom_level": "APPLY"}]
    extractor.set_history("lbc", history)
    assert extractor.get_history("lbc") is history


def test_reset_student_clears_history(extractor):
    obs = _make_observation()
    ctx = _make_ctx()
    extractor.extract("lbc", obs, ctx)
    assert len(extractor.get_history("lbc")) == 1
    extractor.reset_student("lbc")
    assert extractor.get_history("lbc") == []


def test_reset_student_idempotent(extractor):
    extractor.reset_student("unknown")  # no exception
