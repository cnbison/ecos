"""v0.84.0-c: EventLog retention policy tests.

Covers:
  - EventLogConfig defaults
  - prune() respects max_per_student (in_memory + sqlite)
  - prune() per-student vs all
  - auto_prune_on_log triggers prune after log
  - purge_before() time-based (in_memory + sqlite)
  - unlimited config (max=0) skips prune
  - defensive: prune failure doesn't break log_event
  - 防御性自检 [1] silent pass scan

Per discussions/2026-08-11-v084-design.md §4.
"""
from __future__ import annotations

import logging
import os
import tempfile
from datetime import datetime, timedelta

import pytest

from ecos.cta.event_log import (
    EventLog,
    EventLogConfig,
    LearningEvent,
)


def _make_event(student_id: str, idx: int, base_ts: datetime) -> LearningEvent:
    """Build a test LearningEvent with deterministic event_id + timestamp."""
    return LearningEvent(
        event_id=f"evt_{student_id}_{idx:04d}",
        student_id=student_id,
        timestamp=base_ts + timedelta(seconds=idx),
        source="test",
        event_type="observation",
        payload={"problem_id": f"pb-{idx}"},
    )


# ── EventLogConfig defaults (1 test) ───────────────────────────────────────


class TestEventLogConfig:
    """EventLogConfig: 3 fields + defaults."""

    def test_config_defaults(self):
        """Default config: max_per_student=10000, retention_days=0, auto_prune_on_log=False."""
        config = EventLogConfig()
        assert config.max_per_student == 10000
        assert config.retention_days == 0
        assert config.auto_prune_on_log is False


# ── prune() in_memory mode (3 tests) ────────────────────────────────────────


class TestPruneInMemory:
    """prune() in in_memory mode respects max_per_student."""

    def test_prune_caps_to_max_per_student(self):
        """Exceeding max_per_student triggers deletion of oldest events."""
        config = EventLogConfig(max_per_student=3)
        log = EventLog.in_memory(config=config)
        base_ts = datetime(2026, 8, 11, 12, 0, 0)
        # Add 5 events for stu-001
        for i in range(5):
            log.log_event(_make_event("stu-001", i, base_ts))
        assert log.count_events("stu-001") == 5

        deleted = log.prune(student_id="stu-001")
        assert deleted == 2  # 5 - 3 cap
        assert log.count_events("stu-001") == 3

        # Verify the 3 remaining are the most recent (idx 2, 3, 4)
        events = log.load_events("stu-001")
        idx_values = sorted(
            int(e.event_id.rsplit("_", 1)[1]) for e in events
        )
        assert idx_values == [2, 3, 4]

    def test_prune_no_op_when_under_cap(self):
        """If count <= max_per_student, prune returns 0 and doesn't delete."""
        config = EventLogConfig(max_per_student=10)
        log = EventLog.in_memory(config=config)
        base_ts = datetime(2026, 8, 11, 12, 0, 0)
        for i in range(3):
            log.log_event(_make_event("stu-001", i, base_ts))

        deleted = log.prune(student_id="stu-001")
        assert deleted == 0
        assert log.count_events("stu-001") == 3

    def test_prune_all_students(self):
        """prune(student_id=None) prunes all students."""
        config = EventLogConfig(max_per_student=2)
        log = EventLog.in_memory(config=config)
        base_ts = datetime(2026, 8, 11, 12, 0, 0)
        # Add 4 events to each of 2 students
        for sid in ("stu-001", "stu-002"):
            for i in range(4):
                log.log_event(_make_event(sid, i, base_ts))

        deleted = log.prune()  # all students
        assert deleted == 4  # 2 students × 2 events over cap
        assert log.count_events("stu-001") == 2
        assert log.count_events("stu-002") == 2


# ── prune() sqlite mode (1 test) ────────────────────────────────────────────


class TestPruneSqlite:
    """prune() in sqlite mode uses DELETE with timestamp ASC LIMIT."""

    def test_prune_sqlite_caps_to_max(self):
        """Sqlite mode: DELETE oldest events beyond max_per_student cap."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            config = EventLogConfig(max_per_student=3)
            log = EventLog.from_sqlite(db_path, config=config)
            base_ts = datetime(2026, 8, 11, 12, 0, 0)
            for i in range(5):
                log.log_event(_make_event("stu-001", i, base_ts))

            deleted = log.prune(student_id="stu-001")
            assert deleted == 2
            assert log.count_events("stu-001") == 3
            log.close()
        finally:
            os.unlink(db_path)


# ── auto_prune_on_log (1 test) ─────────────────────────────────────────────


class TestAutoPruneOnLog:
    """auto_prune_on_log triggers prune() after log_event()."""

    def test_auto_prune_after_log(self):
        """Logging beyond cap with auto_prune_on_log=True prunes automatically."""
        config = EventLogConfig(max_per_student=2, auto_prune_on_log=True)
        log = EventLog.in_memory(config=config)
        base_ts = datetime(2026, 8, 11, 12, 0, 0)
        # Add 5 events; each log_event() that exceeds cap triggers prune
        for i in range(5):
            log.log_event(_make_event("stu-001", i, base_ts))

        # Final state: 2 most recent events remain
        assert log.count_events("stu-001") == 2
        events = log.load_events("stu-001")
        idx_values = sorted(int(e.event_id.rsplit("_", 1)[1]) for e in events)
        assert idx_values == [3, 4]


# ── purge_before() (2 tests) ───────────────────────────────────────────────


class TestPurgeBefore:
    """purge_before() deletes events with timestamp < cutoff."""

    def test_purge_before_in_memory(self):
        """In-memory: events strictly before cutoff are deleted."""
        log = EventLog.in_memory()
        base_ts = datetime(2026, 8, 11, 12, 0, 0)
        for i in range(5):
            log.log_event(_make_event("stu-001", i, base_ts))
        assert log.count_events("stu-001") == 5

        # Cutoff: delete events with idx < 2 (timestamps < base_ts + 2s)
        cutoff = base_ts + timedelta(seconds=2)
        deleted = log.purge_before(cutoff)
        assert deleted == 2  # idx 0 and idx 1
        assert log.count_events("stu-001") == 3

    def test_purge_before_sqlite(self):
        """Sqlite: DELETE events with timestamp < cutoff."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            log = EventLog.from_sqlite(db_path)
            base_ts = datetime(2026, 8, 11, 12, 0, 0)
            for i in range(5):
                log.log_event(_make_event("stu-001", i, base_ts))

            cutoff = base_ts + timedelta(seconds=3)
            deleted = log.purge_before(cutoff)
            assert deleted == 3  # idx 0, 1, 2
            assert log.count_events("stu-001") == 2  # idx 3, 4
            log.close()
        finally:
            os.unlink(db_path)


# ── Unlimited config (1 test) ──────────────────────────────────────────────


class TestUnlimitedConfig:
    """max_per_student=0 means unlimited; prune() returns 0."""

    def test_unlimited_config_skips_prune(self):
        """max_per_student=0 disables pruning; events accumulate forever."""
        config = EventLogConfig(max_per_student=0)
        log = EventLog.in_memory(config=config)
        base_ts = datetime(2026, 8, 11, 12, 0, 0)
        for i in range(50):
            log.log_event(_make_event("stu-001", i, base_ts))

        deleted = log.prune(student_id="stu-001")
        assert deleted == 0
        assert log.count_events("stu-001") == 50


# ── Defensive checks (1 test) ──────────────────────────────────────────────


class TestDefensiveChecks:
    """防御性自检 [1]: prune failure doesn't break log_event."""

    def test_prune_failure_does_not_break_log_event(self, caplog):
        """If prune raises internally, log_event still succeeds + warning logged."""
        # Build a broken EventLog where prune raises
        config = EventLogConfig(max_per_student=2, auto_prune_on_log=True)
        log = EventLog.in_memory(config=config)

        # Monkey-patch prune to raise
        original_prune = log.prune
        def broken_prune(student_id=None):
            raise RuntimeError("simulated prune failure")
        log.prune = broken_prune

        # log_event should still work (defensive: catch + warning)
        with caplog.at_level(logging.WARNING):
            log.log_event(_make_event("stu-001", 0, datetime.now()))

        # Event was still added
        assert log.count_events("stu-001") == 1
        # Warning was logged
        assert any(
            "auto_prune" in r.message.lower() for r in caplog.records
        )

        # Restore prune
        log.prune = original_prune


# ── Silent pass scan (1 test) ──────────────────────────────────────────────


class TestSilentPassScan:
    """防御性自检 [1]: silent pass scan in event_log.py after v0.84.0-c additions."""

    def test_no_silent_pass_added_in_event_log(self):
        """Grep for 'except ...: pass' in ecos/cta/event_log.py."""
        import subprocess
        pattern = r"^\s*except.*:[[:space:]]*(pass|continue)\s*$"
        result = subprocess.run(
            ["grep", "-nE", pattern, "ecos/cta/event_log.py"],
            capture_output=True, text=True,
        )
        assert result.stdout.strip() == "", (
            f"silent pass detected: {result.stdout}"
        )
