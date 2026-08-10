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
- v0.84.0-a: LearningEventType enum (7 值) + factory methods (from_observation
  /from_calibration_message/from_response_submitted). event_type 字段仍是
  string (backward compat), enum 只是 type hint + factory 辅助.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

_log = logging.getLogger(__name__)


class LearningEventType(Enum):
    """v0.84.0-a: LearningEvent 类型枚举 (kernel-mapping §2.4 Event 统一输入).

    Forward-compat with v0.81.0-a schema (event_type 字段是 TEXT, 兼容任意 string).
    7 个值:
      - OBSERVATION: v0.81 老值, BeliefUpdator commit 后 emit
      - CALIBRATION: v0.84.0-a 新增, dual_agent orchestrator 互校完成后 emit
      - RESPONSE_SUBMITTED: v0.84.0-a 新增, FeatureExtractor 学生提交答案时 emit
      - HINT_REQUESTED: v0.84.0-a 占位, frontend v0.85+ 接
      - IDLE_DETECTED: v0.84.0-a 占位, frontend v0.85+ 接
      - GOAL_CHANGED: v0.84.0-a 占位, frontend v0.85+ 接
      - REFLECTION_COMPLETED: v0.84.0-a 占位, frontend v0.85+ 接

    老调用方传 string ("observation") 仍 work, 枚举值是 .value.
    """

    OBSERVATION = "observation"
    CALIBRATION = "calibration"
    RESPONSE_SUBMITTED = "response_submitted"
    HINT_REQUESTED = "hint_requested"
    IDLE_DETECTED = "idle_detected"
    GOAL_CHANGED = "goal_changed"
    REFLECTION_COMPLETED = "reflection_completed"

    @classmethod
    def from_value(cls, value: Any) -> "LearningEventType":
        """Accept both string ("observation") and enum (LearningEventType.OBSERVATION).

        Unknown string -> defaults to OBSERVATION (backward compat for old data).
        Unknown type -> _log.warning + defaults to OBSERVATION (defensive).
        """
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            try:
                return cls(value)
            except ValueError:
                _log.warning(
                    "LearningEventType.from_value: unknown event_type %r, "
                    "defaulting to OBSERVATION",
                    value,
                )
                return cls.OBSERVATION
        _log.warning(
            "LearningEventType.from_value: non-str/non-enum %r, "
            "defaulting to OBSERVATION",
            value,
        )
        return cls.OBSERVATION


def _make_event_id() -> str:
    """v0.84.0-a: 统一的 event_id 生成器 (跟 StateEngine.commit 同模式).

    Returns:
        "evt_xxxxxxxxxxxx" (12 hex chars)
    """
    return f"evt_{uuid.uuid4().hex[:12]}"


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
        event_type: "observation" for v0.81; v0.84+ uses LearningEventType enum values
                   (observation/calibration/response_submitted/hint_requested/...)
        payload: dict serialization of the event body (Observation.to_dict() for "observation")

    v0.84.0-a: factory methods (from_observation / from_calibration_message /
    from_response_submitted) wrap construction with appropriate event_type.
    """

    event_id: str
    student_id: str
    timestamp: datetime
    source: str
    event_type: str = "observation"
    payload: Dict[str, Any] = field(default_factory=dict)

    # ── v0.84.0-a: factory methods ────────────────────────────────────────────

    @classmethod
    def from_observation(
        cls,
        observation: Any,
        source: str = "belief_updater",
        event_type: Any = LearningEventType.OBSERVATION,
        event_id: Optional[str] = None,
    ) -> "LearningEvent":
        """Construct LearningEvent from an Observation (v0.84.0-a factory).

        Args:
            observation: Observation dataclass (must have to_dict + .timestamp
                         + .skill_id for student_id fallback). For duck-typed
                         compat, accepts any object with .to_dict() / .timestamp
                         / .student_id.
            source: who produced the event (default "belief_updater").
            event_type: LearningEventType enum or string. Default OBSERVATION.
                        Pass RESPONSE_SUBMITTED to mark a "pre-judge" submission.
            event_id: optional pre-generated event_id (matches StateEngine.commit).

        Returns:
            LearningEvent with payload=observation.to_dict().
        """
        # Resolve event_type (accept both enum and string)
        evt_type = LearningEventType.from_value(event_type).value
        # student_id: try .student_id, fall back to .skill_id (some legacy callers)
        student_id = getattr(observation, "student_id", None) or getattr(observation, "skill_id", "")
        return cls(
            event_id=event_id or _make_event_id(),
            student_id=str(student_id),
            timestamp=observation.timestamp,
            source=source,
            event_type=evt_type,
            payload=observation.to_dict(),
        )

    @classmethod
    def from_calibration_message(
        cls,
        calibration_message: Any,
        source: str = "dual_agent_orchestrator",
        student_id: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> "LearningEvent":
        """Construct LearningEvent from a CalibrationMessage (v0.84.0-a factory).

        Dual-write use case: orchestrator writes calibration_log (db.py:638) +
        event_log (this LearningEvent, event_type="calibration"). The two writes
        preserve H3 ECE validation (calibration_log) + unified LearningEvent
        stream (event_log).

        Args:
            calibration_message: CalibrationMessage dataclass (must have
                                 .student_id / .timestamp / .to_dict()).
            source: who produced (default "dual_agent_orchestrator").
            student_id: override student_id (default from message).
            event_id: optional pre-generated event_id.

        Returns:
            LearningEvent with payload=calibration_message.to_dict() and
            event_type="calibration".
        """
        # Convert timestamp (unix time float) -> datetime
        ts_raw = calibration_message.timestamp
        if isinstance(ts_raw, (int, float)):
            timestamp = datetime.fromtimestamp(ts_raw)
        elif isinstance(ts_raw, datetime):
            timestamp = ts_raw
        else:
            timestamp = datetime.now()
        sid = student_id or calibration_message.student_id
        return cls(
            event_id=event_id or _make_event_id(),
            student_id=str(sid),
            timestamp=timestamp,
            source=source,
            event_type=LearningEventType.CALIBRATION.value,
            payload=calibration_message.to_dict(),
        )

    @classmethod
    def from_response_submitted(
        cls,
        observation: Any,
        source: str = "feature_extractor",
        event_id: Optional[str] = None,
    ) -> "LearningEvent":
        """Construct LearningEvent for response_submitted (v0.84.0-a factory).

        Distinct from from_observation (event_type="observation"): emitted by
        FeatureExtractor when student first submits (pre-judge), so that
        response_history has both an in-memory hot cache (FeatureExtractor
        _response_history cap 100) AND a persistent event_log entry.

        Args:
            observation: Observation dataclass.
            source: who produced (default "feature_extractor").
            event_id: optional pre-generated event_id.

        Returns:
            LearningEvent with event_type="response_submitted".
        """
        return cls.from_observation(
            observation,
            source=source,
            event_type=LearningEventType.RESPONSE_SUBMITTED,
            event_id=event_id,
        )


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
