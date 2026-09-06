"""per-misconception 证据闭环测试 (v0.97.3, P2 A2 reconcile) — CogMirror A2 移植回归."""
from __future__ import annotations

import inspect
import os
import tempfile
from datetime import datetime

import pytest

from ecos.cta.misconception_reconcile import (
    QUARANTINE_MIN_EVIDENCE,
    MisconceptionEvidenceRow,
    MisconceptionEvidenceTracker,
    load_tracker_for_student,
    reconcile_for_student,
)
from ecos.persistence.db import Database, DatabaseConfig


def _row(skill_id, misc_id, score, correct=None, ts="2026-09-05T10:00:00"):
    r = {"skill_id": skill_id, "misc_id": misc_id, "score": score, "timestamp": ts}
    if correct is not None:
        r["correct"] = correct
    return r


@pytest.fixture
def tmp_db():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "ev.db")
        db = Database(DatabaseConfig(db_path=path))
        try:
            db.init_schema()  # fixture 调 init_schema (与 get_db() 同模式)
            db.upsert_student("stu_001", grade_level=5, subject="math")
            yield db
        finally:
            db.close()


def test_confidence_laplace_math():
    t = MisconceptionEvidenceTracker()
    assert t.confidence_for("M1") == 0.5
    t.record_success("M1")
    assert t.confidence_for("M1") == pytest.approx(2 / 3)
    t.record_failure("M1")
    assert t.confidence_for("M1") == 0.5


def test_confidence_direction_persistent_over_0_6():
    t = MisconceptionEvidenceTracker()
    for _ in range(3):
        t.record_success("M8")
    assert t.confidence_for("M8") > 0.6
    assert t.confidence_for("M8") == pytest.approx(4 / 5)


def test_confidence_direction_overcome_falls_below_0_6():
    t = MisconceptionEvidenceTracker()
    for _ in range(5):
        t.record_failure("M4")
    assert t.confidence_for("M4") < 0.6


def test_reconcile_overcome_records_failure():
    t = MisconceptionEvidenceTracker()
    t.reconcile([_row("math.frac", "M8", 0.0), _row("math.frac", None, 1.0)])
    e = t.evidence_for("M8")
    assert e.failure_count == 1 and e.success_count == 0


def test_reconcile_persistent_records_success():
    t = MisconceptionEvidenceTracker()
    t.reconcile([_row("math.frac", "M8", 0.0), _row("math.frac", None, 0.0)])
    e = t.evidence_for("M8")
    assert e.success_count == 1 and e.failure_count == 0


def test_reconcile_retrigger_records_success_even_when_correct():
    t = MisconceptionEvidenceTracker()
    t.reconcile([_row("math.frac", "M8", 0.0), _row("math.frac", "M8", 1.0)])
    e = t.evidence_for("M8")
    assert e.success_count == 1 and e.failure_count == 0


def test_reconcile_uses_correct_field_when_present():
    t = MisconceptionEvidenceTracker()
    t.reconcile([_row("math.frac", "M1", 1.0), _row("math.frac", None, 0.9, correct=False)])
    e = t.evidence_for("M1")
    assert e.success_count == 1


def test_reconcile_skips_other_skills():
    t = MisconceptionEvidenceTracker()
    t.reconcile([_row("math.frac", "M8", 0.0), _row("math.alg", None, 1.0)])
    assert t.evidence_for("M8") is None


def test_reconcile_skips_when_no_next_in_skill():
    t = MisconceptionEvidenceTracker()
    t.reconcile([_row("math.frac", "M8", 0.0)])
    assert t.evidence_for("M8") is None


def test_reconcile_skips_unmatched_rows():
    t = MisconceptionEvidenceTracker()
    updated = t.reconcile([_row("math.frac", None, 0.0), _row("math.frac", "", 1.0)])
    assert updated == 0
    assert t.evidence_for("M1") is None


def test_reconcile_multiple_hits_each_joined_to_next():
    t = MisconceptionEvidenceTracker()
    t.reconcile([
        _row("math.frac", "M8", 0.0),
        _row("math.frac", "M8", 0.0),
        _row("math.frac", None, 1.0),
    ])
    e = t.evidence_for("M8")
    assert e.success_count == 1 and e.failure_count == 1


def test_reconcile_returns_count_of_updates():
    t = MisconceptionEvidenceTracker()
    updated = t.reconcile([
        _row("math.frac", "M1", 0.0),
        _row("math.frac", None, 0.0),
        _row("math.alg", "M3", 0.0),
        _row("math.alg", None, 1.0),
    ])
    assert updated == 2


def test_quarantine_thresholds():
    t = MisconceptionEvidenceTracker()
    assert not t.quarantined("M1")
    for _ in range(QUARANTINE_MIN_EVIDENCE):
        t.record_failure("M1")
    assert t.quarantined("M1")


def test_quarantine_requires_min_evidence():
    t = MisconceptionEvidenceTracker()
    t.record_failure("M2")
    t.record_failure("M2")
    assert not t.quarantined("M2")


def test_quarantine_persistent_not_quarantined():
    t = MisconceptionEvidenceTracker()
    for _ in range(5):
        t.record_success("M5")
    assert not t.quarantined("M5")


def test_evidence_for_unknown_returns_none():
    t = MisconceptionEvidenceTracker()
    assert t.evidence_for("unknown") is None


def test_all_evidence_sorted_by_misc_id():
    t = MisconceptionEvidenceTracker()
    t.record_success("M3")
    t.record_failure("M1")
    t.record_success("M2")
    rows = t.all_evidence()
    assert [r.misc_id for r in rows] == ["M1", "M2", "M3"]


def test_evidence_row_total_and_laplace():
    r = MisconceptionEvidenceRow(
        misc_id="M1", success_count=2, failure_count=1, last_updated="2026-09-05",
    )
    assert r.total == 3
    assert r.laplace_confidence() == pytest.approx((2 + 1) / (3 + 2))


def test_load_accumulates_existing_evidence():
    t = MisconceptionEvidenceTracker()
    t.load([{"misc_id": "M1", "success_count": 1, "failure_count": 0,
             "last_updated": "2026-09-01T00:00:00"}])
    t.load([{"misc_id": "M1", "success_count": 0, "failure_count": 1,
             "last_updated": "2026-09-02T00:00:00"}])
    e = t.evidence_for("M1")
    assert e.success_count == 1
    assert e.failure_count == 1
    assert e.last_updated == "2026-09-02T00:00:00"


def test_clear_resets_state():
    t = MisconceptionEvidenceTracker()
    t.record_success("M1")
    t.clear()
    assert t.evidence_for("M1") is None


def test_dump_preserves_round_trip():
    t = MisconceptionEvidenceTracker()
    t.record_success("M1")
    t.record_failure("M2")
    t.record_success("M2")
    dumped = t.dump()
    t2 = MisconceptionEvidenceTracker()
    t2.load(dumped)
    assert t2.confidence_for("M1") == t.confidence_for("M1")
    assert t2.confidence_for("M2") == t.confidence_for("M2")


def test_save_and_load_roundtrip(tmp_db):
    t = MisconceptionEvidenceTracker()
    t.record_success("M8")
    t.record_failure("M8")
    t.record_success("M3")
    tmp_db.save_misconception_evidence("stu_001", t.dump())

    loaded = load_tracker_for_student(tmp_db, "stu_001")
    assert loaded.confidence_for("M8") == pytest.approx(t.confidence_for("M8"))
    assert loaded.confidence_for("M3") == pytest.approx(t.confidence_for("M3"))


def test_save_upsert_idempotent(tmp_db):
    rows = [{"misc_id": "M8", "success_count": 1, "failure_count": 0,
             "last_updated": datetime.now().isoformat()}]
    tmp_db.save_misconception_evidence("stu_001", rows)
    tmp_db.save_misconception_evidence("stu_001", rows)
    loaded = tmp_db.load_misconception_evidence("stu_001")
    assert len(loaded) == 1
    assert loaded[0]["success_count"] == 1


def test_save_upsert_updates_counters(tmp_db):
    tmp_db.save_misconception_evidence("stu_001", [
        {"misc_id": "M1", "success_count": 1, "failure_count": 0, "last_updated": "2026-09-01"},
    ])
    tmp_db.save_misconception_evidence("stu_001", [
        {"misc_id": "M1", "success_count": 3, "failure_count": 1, "last_updated": "2026-09-05"},
    ])
    loaded = tmp_db.load_misconception_evidence("stu_001", "M1")
    assert loaded[0]["success_count"] == 3
    assert loaded[0]["failure_count"] == 1


def test_load_filters_by_student(tmp_db):
    tmp_db.upsert_student("stu_002", grade_level=5, subject="math")
    tmp_db.save_misconception_evidence("stu_001", [
        {"misc_id": "M1", "success_count": 1, "failure_count": 0, "last_updated": "2026-09-05"},
    ])
    tmp_db.save_misconception_evidence("stu_002", [
        {"misc_id": "M3", "success_count": 0, "failure_count": 1, "last_updated": "2026-09-05"},
    ])
    rows1 = tmp_db.load_misconception_evidence("stu_001")
    rows2 = tmp_db.load_misconception_evidence("stu_002")
    assert [r["misc_id"] for r in rows1] == ["M1"]
    assert [r["misc_id"] for r in rows2] == ["M3"]


def test_load_specific_misc_id(tmp_db):
    tmp_db.save_misconception_evidence("stu_001", [
        {"misc_id": "M1", "success_count": 1, "failure_count": 0, "last_updated": ""},
        {"misc_id": "M3", "success_count": 0, "failure_count": 1, "last_updated": ""},
    ])
    rows = tmp_db.load_misconception_evidence("stu_001", "M1")
    assert len(rows) == 1
    assert rows[0]["misc_id"] == "M1"


def test_delete_purges_student_evidence(tmp_db):
    tmp_db.save_misconception_evidence("stu_001", [
        {"misc_id": "M1", "success_count": 1, "failure_count": 0, "last_updated": ""},
    ])
    assert len(tmp_db.load_misconception_evidence("stu_001")) == 1
    deleted = tmp_db.delete_misconception_evidence("stu_001")
    assert deleted == 1
    assert tmp_db.load_misconception_evidence("stu_001") == []


def test_save_empty_rows_is_noop(tmp_db):
    assert tmp_db.save_misconception_evidence("stu_001", []) == 0


def test_save_skips_rows_without_misc_id(tmp_db):
    written = tmp_db.save_misconception_evidence("stu_001", [
        {"misc_id": "", "success_count": 1, "failure_count": 0, "last_updated": ""},
        {"misc_id": None, "success_count": 1, "failure_count": 0, "last_updated": ""},
    ])
    assert written == 0


def test_load_tracker_for_student_empty_db(tmp_db):
    t = load_tracker_for_student(tmp_db, "stu_001")
    assert t.confidence_for("M1") == 0.5
    assert t.evidence_for("M1") is None


def test_reconcile_for_student_round_trip(tmp_db):
    rows = [_row("math.frac", "M8", 0.0), _row("math.frac", None, 1.0)]
    updated = reconcile_for_student(tmp_db, "stu_001", rows)
    assert updated == 1
    loaded = tmp_db.load_misconception_evidence("stu_001")
    assert len(loaded) == 1
    assert loaded[0]["misc_id"] == "M8"
    assert loaded[0]["failure_count"] == 1


def test_reconcile_for_student_no_updates_doesnt_write(tmp_db):
    updated = reconcile_for_student(tmp_db, "stu_001", [])
    assert updated == 0
    assert tmp_db.load_misconception_evidence("stu_001") == []


def test_reconcile_for_student_db_failure_returns_neg1(tmp_db, monkeypatch):
    def _boom_load(*_a, **_kw):
        raise RuntimeError("db 挂了")
    monkeypatch.setattr(tmp_db, "load_misconception_evidence", _boom_load)
    updated = reconcile_for_student(tmp_db, "stu_001", [_row("s", "M1", 0.0)])
    assert updated == -1


def test_no_silent_pass_in_misconception_reconcile():
    import ecos.cta.misconception_reconcile as mod
    src = inspect.getsource(mod)
    lines = [ln for ln in src.splitlines() if "pass" in ln and "except" in ln]
    assert not lines, f"发现 except: pass 静默吞错, 防御性自检 [1] 违规: {lines}"
