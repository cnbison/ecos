"""v0.81.0-a: EventLog + LearningEvent pytest 套件.

Tests:
- in_memory mode: log/load/count/close, multi-student isolation, dedup
- sqlite mode: schema, log/load round-trip, multi-student isolation, time range filter, limit
- LearningEvent dataclass: field defaults, payload dict shape
- Edge cases: empty load, non-existent student, closed log

Total: 30 tests.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from ecos.cta.event_log import EventLog, LearningEvent


# ─── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def sample_event():
    """Sample LearningEvent for tests."""
    return LearningEvent(
        event_id="evt_test001",
        student_id="student_001",
        timestamp=datetime(2026, 8, 10, 14, 30, 0),
        source="belief_updater",
        event_type="observation",
        payload={
            "skill_id": "variables",
            "problem_id": "PB-Q1",
            "score": 0.7,
            "correct": True,
        },
    )


@pytest.fixture
def second_event():
    """Second event (later timestamp, same student)."""
    return LearningEvent(
        event_id="evt_test002",
        student_id="student_001",
        timestamp=datetime(2026, 8, 10, 14, 31, 0),
        source="belief_updater",
        event_type="observation",
        payload={
            "skill_id": "loops",
            "problem_id": "PB-Q2",
            "score": 0.4,
            "correct": False,
        },
    )


@pytest.fixture
def other_student_event():
    """Event for different student (isolation test)."""
    return LearningEvent(
        event_id="evt_test003",
        student_id="student_002",
        timestamp=datetime(2026, 8, 10, 14, 30, 0),
        source="belief_updater",
        event_type="observation",
        payload={"skill_id": "variables", "problem_id": "PB-Q1", "score": 1.0, "correct": True},
    )


@pytest.fixture
def sqlite_db(tmp_path):
    """Fresh sqlite db path."""
    return str(tmp_path / "test_event_log.db")


# ─── LearningEvent dataclass tests (4) ──────────────────────────────────────


def test_learning_event_default_event_type():
    """Default event_type should be 'observation' (v0.81 only type)."""
    e = LearningEvent(
        event_id="evt_x",
        student_id="s1",
        timestamp=datetime(2026, 8, 10),
        source="belief_updater",
    )
    assert e.event_type == "observation"
    assert e.payload == {}


def test_learning_event_payload_dict_default():
    """payload should default to empty dict (not None)."""
    e = LearningEvent(
        event_id="evt_x",
        student_id="s1",
        timestamp=datetime(2026, 8, 10),
        source="belief_updater",
    )
    assert e.payload == {}
    # Mutating payload should not affect other instances (default_factory)
    e.payload["foo"] = "bar"
    e2 = LearningEvent(
        event_id="evt_y", student_id="s2", timestamp=datetime(2026, 8, 10), source="x"
    )
    assert e2.payload == {}


def test_learning_event_explicit_fields():
    """Explicit fields should be stored as-is."""
    e = LearningEvent(
        event_id="evt_abc",
        student_id="student_001",
        timestamp=datetime(2026, 8, 10, 14, 30, 0),
        source="belief_updater",
        event_type="observation",
        payload={"skill_id": "loops", "score": 0.8},
    )
    assert e.event_id == "evt_abc"
    assert e.student_id == "student_001"
    assert e.source == "belief_updater"
    assert e.event_type == "observation"
    assert e.payload["skill_id"] == "loops"


def test_learning_event_forward_compat_calibration_type():
    """v0.82+ may use event_type='calibration' without dataclass change."""
    e = LearningEvent(
        event_id="evt_calib_001",
        student_id="student_001",
        timestamp=datetime(2026, 8, 10),
        source="calibration_engine",
        event_type="calibration",
        payload={"trigger_reason": "low_confidence"},
    )
    assert e.event_type == "calibration"


# ─── in_memory mode tests (10) ──────────────────────────────────────────────


def test_in_memory_factory_returns_event_log():
    """in_memory() classmethod should return EventLog instance."""
    log = EventLog.in_memory()
    assert isinstance(log, EventLog)
    assert log.mode == "in_memory"


def test_in_memory_log_event_stores_event(sample_event):
    """log_event should add event to in-memory list."""
    log = EventLog.in_memory()
    log.log_event(sample_event)
    events = log.load_events("student_001")
    assert len(events) == 1
    assert events[0].event_id == "evt_test001"


def test_in_memory_log_event_dedup_by_event_id(sample_event):
    """Re-logging same event_id should be a no-op (mirrors sqlite PRIMARY KEY)."""
    log = EventLog.in_memory()
    log.log_event(sample_event)
    log.log_event(sample_event)  # same event_id
    events = log.load_events("student_001")
    assert len(events) == 1


def test_in_memory_load_returns_chronological_order(sample_event, second_event):
    """load_events should return events sorted by timestamp (oldest first)."""
    log = EventLog.in_memory()
    # Insert out of order
    log.log_event(second_event)
    log.log_event(sample_event)
    events = log.load_events("student_001")
    assert len(events) == 2
    assert events[0].event_id == "evt_test001"  # earlier timestamp
    assert events[1].event_id == "evt_test002"  # later timestamp


def test_in_memory_multi_student_isolation(sample_event, other_student_event):
    """load_events should only return events for the queried student."""
    log = EventLog.in_memory()
    log.log_event(sample_event)
    log.log_event(other_student_event)
    s1_events = log.load_events("student_001")
    s2_events = log.load_events("student_002")
    assert len(s1_events) == 1
    assert len(s2_events) == 1
    assert s1_events[0].event_id == "evt_test001"
    assert s2_events[0].event_id == "evt_test003"


def test_in_memory_load_empty_returns_empty_list():
    """load_events for non-existent student should return empty list."""
    log = EventLog.in_memory()
    events = log.load_events("nonexistent_student")
    assert events == []


def test_in_memory_load_with_since_filter(sample_event, second_event):
    """load_events since filter should exclude earlier events."""
    log = EventLog.in_memory()
    log.log_event(sample_event)
    log.log_event(second_event)
    events = log.load_events(
        "student_001", since=datetime(2026, 8, 10, 14, 30, 30)
    )
    assert len(events) == 1
    assert events[0].event_id == "evt_test002"


def test_in_memory_load_with_until_filter(sample_event, second_event):
    """load_events until filter should exclude later events."""
    log = EventLog.in_memory()
    log.log_event(sample_event)
    log.log_event(second_event)
    events = log.load_events(
        "student_001", until=datetime(2026, 8, 10, 14, 30, 30)
    )
    assert len(events) == 1
    assert events[0].event_id == "evt_test001"


def test_in_memory_load_with_limit(sample_event, second_event):
    """load_events limit should cap results."""
    log = EventLog.in_memory()
    log.log_event(sample_event)
    log.log_event(second_event)
    events = log.load_events("student_001", limit=1)
    assert len(events) == 1


def test_in_memory_count_events(sample_event, other_student_event):
    """count_events should return per-student count."""
    log = EventLog.in_memory()
    log.log_event(sample_event)
    log.log_event(other_student_event)
    assert log.count_events("student_001") == 1
    assert log.count_events("student_002") == 1
    assert log.count_events("student_xxx") == 0


def test_in_memory_close_is_safe():
    """close() on in_memory mode should be a no-op (no error)."""
    log = EventLog.in_memory()
    log.close()
    assert log.mode == "closed"


# ─── sqlite mode tests (12) ─────────────────────────────────────────────────


def test_from_sqlite_factory_creates_log(sqlite_db):
    """from_sqlite() should return EventLog with sqlite mode."""
    log = EventLog.from_sqlite(sqlite_db)
    assert isinstance(log, EventLog)
    assert log.mode == "sqlite"
    log.close()


def test_from_sqlite_creates_table_idempotent(sqlite_db):
    """from_sqlite() should create event_log table; calling again should be safe."""
    log1 = EventLog.from_sqlite(sqlite_db)
    log1.close()
    log2 = EventLog.from_sqlite(sqlite_db)  # should not error
    log2.close()


def test_sqlite_log_event_persists(sample_event, sqlite_db):
    """log_event should write to sqlite."""
    log = EventLog.from_sqlite(sqlite_db)
    log.log_event(sample_event)
    log.close()

    # Reopen and verify
    log2 = EventLog.from_sqlite(sqlite_db)
    events = log2.load_events("student_001")
    assert len(events) == 1
    assert events[0].event_id == "evt_test001"
    assert events[0].student_id == "student_001"
    log2.close()


def test_sqlite_log_event_round_trip_payload(sample_event, sqlite_db):
    """payload dict should round-trip through sqlite (JSON serialize/deserialize)."""
    log = EventLog.from_sqlite(sqlite_db)
    log.log_event(sample_event)
    log.close()

    log2 = EventLog.from_sqlite(sqlite_db)
    events = log2.load_events("student_001")
    assert events[0].payload["skill_id"] == "variables"
    assert events[0].payload["problem_id"] == "PB-Q1"
    assert events[0].payload["score"] == 0.7
    assert events[0].payload["correct"] is True
    log2.close()


def test_sqlite_log_event_dedup_by_event_id(sample_event, sqlite_db):
    """INSERT OR IGNORE should dedup by event_id PRIMARY KEY."""
    log = EventLog.from_sqlite(sqlite_db)
    log.log_event(sample_event)
    log.log_event(sample_event)  # duplicate event_id
    events = log.load_events("student_001")
    assert len(events) == 1
    log.close()


def test_sqlite_load_chronological_order(sample_event, second_event, sqlite_db):
    """sqlite load should return events sorted by timestamp ASC."""
    log = EventLog.from_sqlite(sqlite_db)
    log.log_event(second_event)
    log.log_event(sample_event)
    events = log.load_events("student_001")
    assert events[0].event_id == "evt_test001"
    assert events[1].event_id == "evt_test002"
    log.close()


def test_sqlite_multi_student_isolation(sample_event, other_student_event, sqlite_db):
    """sqlite should isolate events by student_id."""
    log = EventLog.from_sqlite(sqlite_db)
    log.log_event(sample_event)
    log.log_event(other_student_event)
    s1 = log.load_events("student_001")
    s2 = log.load_events("student_002")
    assert len(s1) == 1
    assert len(s2) == 1
    log.close()


def test_sqlite_load_with_since_until_filter(sample_event, second_event, sqlite_db):
    """sqlite since/until filters should narrow results."""
    log = EventLog.from_sqlite(sqlite_db)
    log.log_event(sample_event)
    log.log_event(second_event)
    events = log.load_events(
        "student_001",
        since=datetime(2026, 8, 10, 14, 30, 30),
        until=datetime(2026, 8, 10, 14, 31, 30),
    )
    assert len(events) == 1
    assert events[0].event_id == "evt_test002"
    log.close()


def test_sqlite_load_with_limit(sample_event, second_event, sqlite_db):
    """sqlite limit should cap results."""
    log = EventLog.from_sqlite(sqlite_db)
    log.log_event(sample_event)
    log.log_event(second_event)
    events = log.load_events("student_001", limit=1)
    assert len(events) == 1
    log.close()


def test_sqlite_count_events(sample_event, second_event, sqlite_db):
    """count_events on sqlite."""
    log = EventLog.from_sqlite(sqlite_db)
    log.log_event(sample_event)
    log.log_event(second_event)
    assert log.count_events("student_001") == 2
    assert log.count_events("student_002") == 0
    log.close()


def test_sqlite_load_nonexistent_student_empty(sqlite_db):
    """load_events for non-existent student should return empty list."""
    log = EventLog.from_sqlite(sqlite_db)
    events = log.load_events("nonexistent")
    assert events == []
    log.close()


def test_sqlite_close_releases_connection(sqlite_db):
    """close() should release sqlite connection."""
    log = EventLog.from_sqlite(sqlite_db)
    log.close()
    assert log.mode == "closed"
    # Subsequent operations should raise (or we can verify _conn is None)
    assert log._conn is None


def test_sqlite_payload_with_numpy_array(sqlite_db):
    """payload with numpy array (via tolist) should serialize OK."""
    import numpy as np

    arr = np.array([0.1, 0.2, 0.3])
    event = LearningEvent(
        event_id="evt_np",
        student_id="student_np",
        timestamp=datetime(2026, 8, 10),
        source="belief_updater",
        payload={"theta": arr.tolist()},  # caller converts numpy -> list
    )
    log = EventLog.from_sqlite(sqlite_db)
    log.log_event(event)
    events = log.load_events("student_np")
    assert events[0].payload["theta"] == [0.1, 0.2, 0.3]
    log.close()


# ─── Database class integration tests (4) ──────────────────────────────────


def test_database_init_schema_creates_event_log_table(tmp_path):
    """Database.init_schema() should create event_log table."""
    from ecos.persistence.db import Database, DatabaseConfig

    db = Database(DatabaseConfig(db_path=str(tmp_path / "test.db")))
    db.init_schema()
    # Verify table exists
    rows = db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='event_log'"
    ).fetchall()
    assert len(rows) == 1
    db.close()


def test_database_save_event_persists(tmp_path):
    """Database.save_event should write row to event_log."""
    from ecos.persistence.db import Database, DatabaseConfig

    db = Database(DatabaseConfig(db_path=str(tmp_path / "test.db")))
    db.init_schema()
    db.upsert_student("student_001")
    db.save_event(
        event_id="evt_db_001",
        student_id="student_001",
        timestamp="2026-08-10T14:30:00",
        source="belief_updater",
        event_type="observation",
        payload_json='{"skill_id": "variables"}',
    )
    assert db.count_events("student_001") == 1
    db.close()


def test_database_load_event_history_returns_dict_rows(tmp_path):
    """Database.load_event_history should return list of dicts (not sqlite3.Row)."""
    from ecos.persistence.db import Database, DatabaseConfig

    db = Database(DatabaseConfig(db_path=str(tmp_path / "test.db")))
    db.init_schema()
    db.upsert_student("student_001")
    db.save_event(
        event_id="evt_db_002",
        student_id="student_001",
        timestamp="2026-08-10T14:31:00",
        source="belief_updater",
        event_type="observation",
        payload_json='{"score": 0.5}',
    )
    history = db.load_event_history("student_001")
    assert len(history) == 1
    assert isinstance(history[0], dict)
    assert history[0]["event_id"] == "evt_db_002"
    db.close()


def test_database_event_log_index_exists(tmp_path):
    """idx_event_log_student index should exist for fast student_id + timestamp queries."""
    from ecos.persistence.db import Database, DatabaseConfig

    db = Database(DatabaseConfig(db_path=str(tmp_path / "test.db")))
    db.init_schema()
    rows = db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_event_log_student'"
    ).fetchall()
    assert len(rows) == 1
    db.close()
