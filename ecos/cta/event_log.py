"""v0.81.0-a: EventLog - persists LearningEvents for replay/simulation.

2.0 §2.2.1 State Engine 6 职责中的 Replay + Simulation 的前置基础设施.
StateEngine.commit 生成 event_id, EventLog 持久化 event_id + payload, StateEngine.replay 用 events 重建 state.

Dual-mode:
- in_memory: list backed (tests / mock)
- from_sqlite: sqlite3 connection backed (production)

Schema (sqlite, mirrors calibration_log per db.py:119-138):
    CREATE TABLE IF NOT EXISTS event_log (
        event_id TEXT PRIMARY KEY,
        student_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        source TEXT NOT NULL,
        event_type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        FOREIGN KEY (student_id) REFERENCES students(student_id)
    );
    CREATE INDEX IF NOT EXISTS idx_event_log_student ON event_log(student_id, timestamp);

Forward-compat (Option D):
- v0.81: only event_type="observation" (Observation payload via to_dict/from_dict)
- v0.82+: event_type="calibration" etc added without breaking v0.81 schema
"""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

_log = logging.getLogger(__name__)


@dataclass
class LearningEvent:
    """v0.81 EventLog record.

    Thin envelope: event_type + payload dict. v0.82+ extends event_type
    (e.g. "calibration", "llm_critic") without changing this dataclass.

    Attributes:
        event_id: evt_xxx (matches StateEngine.commit's event_id)
        student_id: which student this event belongs to
        timestamp: when the event occurred (observation.timestamp for "observation" type)
        source: who committed (e.g. "belief_updater", "db_restore", "replay")
        event_type: "observation" for v0.81; future: "calibration", "llm_critic"
        payload: dict serialization of the event body (Observation.to_dict() for "observation")
    """

    event_id: str
    student_id: str
    timestamp: datetime
    source: str
    event_type: str = "observation"
    payload: Dict[str, Any] = field(default_factory=dict)


class EventLog:
    """Persists LearningEvents. Dual-mode: in-memory (tests) + sqlite (production).

    Usage:
        # In-memory (tests)
        log = EventLog.in_memory()
        log.log_event(event)
        events = log.load_events("student_001")

        # sqlite (production)
        log = EventLog.from_sqlite("ecos.db")
        log.log_event(event)
        events = log.load_events("student_001", since=datetime(2026, 8, 1))
        log.close()

    Forward-compat: v0.82+ adds event_type="calibration" without schema change.
    """

    def __init__(self) -> None:
        # Common state; _events only used by in_memory mode
        self._events: Optional[List[LearningEvent]] = None
        self._conn: Optional[sqlite3.Connection] = None
        self._mode: str = "uninitialized"

    # ── Constructors ────────────────────────────────────────────────────────

    @classmethod
    def in_memory(cls) -> "EventLog":
        """In-memory list-backed EventLog (for tests / mock)."""
        log = cls()
        log._events = []
        log._mode = "in_memory"
        return log

    @classmethod
    def from_sqlite(cls, db_path: str) -> "EventLog":
        """sqlite-backed EventLog (production).

        Opens own connection. Table DDL is in ecos/persistence/db.py SCHEMA_SQL
        (event_log table). If db_path doesn't exist, sqlite3.connect creates it.
        If event_log table doesn't exist yet (old DB), create it idempotently.
        """
        log = cls()
        log._conn = sqlite3.connect(
            db_path,
            check_same_thread=False,  # v0.51.1: same as Database.conn
        )
        log._conn.row_factory = sqlite3.Row
        log._conn.execute("PRAGMA journal_mode = WAL")
        log._mode = "sqlite"
        # Idempotent table creation (mirrors Database.init_schema pattern)
        log._conn.executescript(_EVENT_LOG_DDL)
        log._conn.commit()
        return log

    # ── API ─────────────────────────────────────────────────────────────────

    def log_event(self, event: LearningEvent) -> None:
        """Persist a LearningEvent. Idempotent on event_id (PRIMARY KEY)."""
        if self._mode == "in_memory":
            assert self._events is not None
            # Dedup by event_id (mirrors sqlite PRIMARY KEY semantics)
            for existing in self._events:
                if existing.event_id == event.event_id:
                    return
            self._events.append(event)
            return

        if self._mode == "sqlite":
            assert self._conn is not None
            self._conn.execute(
                """
                INSERT OR IGNORE INTO event_log (
                    event_id, student_id, timestamp, source, event_type, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.student_id,
                    event.timestamp.isoformat(),
                    event.source,
                    event.event_type,
                    json.dumps(event.payload, default=_json_default),
                ),
            )
            self._conn.commit()
            return

        raise RuntimeError(f"EventLog not initialized (mode={self._mode})")

    def load_events(
        self,
        student_id: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[LearningEvent]:
        """Load events for a student, optionally filtered by time range.

        Returns events in chronological order (oldest first) - ready for replay().
        """
        if self._mode == "in_memory":
            assert self._events is not None
            events = [e for e in self._events if e.student_id == student_id]
            if since is not None:
                events = [e for e in events if e.timestamp >= since]
            if until is not None:
                events = [e for e in events if e.timestamp <= until]
            events.sort(key=lambda e: e.timestamp)
            if limit is not None:
                events = events[:limit]
            return events

        if self._mode == "sqlite":
            assert self._conn is not None
            query = "SELECT * FROM event_log WHERE student_id = ?"
            params: List[Any] = [student_id]
            if since is not None:
                query += " AND timestamp >= ?"
                params.append(since.isoformat())
            if until is not None:
                query += " AND timestamp <= ?"
                params.append(until.isoformat())
            query += " ORDER BY timestamp ASC"
            if limit is not None:
                query += " LIMIT ?"
                params.append(limit)
            rows = self._conn.execute(query, params).fetchall()
            return [_row_to_event(row) for row in rows]

        raise RuntimeError(f"EventLog not initialized (mode={self._mode})")

    def count_events(self, student_id: str) -> int:
        """Count events for a student (convenience for tests/debugging)."""
        if self._mode == "in_memory":
            assert self._events is not None
            return sum(1 for e in self._events if e.student_id == student_id)
        if self._mode == "sqlite":
            assert self._conn is not None
            row = self._conn.execute(
                "SELECT COUNT(*) FROM event_log WHERE student_id = ?",
                (student_id,),
            ).fetchone()
            return int(row[0]) if row else 0
        raise RuntimeError(f"EventLog not initialized (mode={self._mode})")

    def close(self) -> None:
        """Close sqlite connection (no-op for in_memory)."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        self._mode = "closed"

    @property
    def mode(self) -> str:
        """Current mode: 'in_memory' / 'sqlite' / 'closed'."""
        return self._mode


# ─── Module-level helpers ──────────────────────────────────────────────────

_EVENT_LOG_DDL = """
CREATE TABLE IF NOT EXISTS event_log (
    event_id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    source TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

CREATE INDEX IF NOT EXISTS idx_event_log_student ON event_log(student_id, timestamp);
"""


def _row_to_event(row: sqlite3.Row) -> LearningEvent:
    """Convert sqlite Row -> LearningEvent (deserialize payload JSON + timestamp)."""
    payload = json.loads(row["payload_json"]) if row["payload_json"] else {}
    # Parse ISO timestamp; tolerate both with/without microseconds
    ts_str = row["timestamp"]
    try:
        timestamp = datetime.fromisoformat(ts_str)
    except ValueError:
        # Fallback: strip fractional seconds if non-ISO
        _log.warning("EventLog: failed to parse timestamp %r, using now()", ts_str)
        timestamp = datetime.now()
    return LearningEvent(
        event_id=row["event_id"],
        student_id=row["student_id"],
        timestamp=timestamp,
        source=row["source"],
        event_type=row["event_type"],
        payload=payload,
    )


def _json_default(obj: Any) -> Any:
    """JSON serializer for objects not serializable by default json code."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "tolist"):  # numpy arrays
        return obj.tolist()
    if hasattr(obj, "item"):  # numpy scalars
        return obj.item()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
