"""SQLite 数据库层——连接管理 + Schema 初始化.

对应 research/10-engineering/05-persistence-session.md §2。

MVP 范围：6 张核心表（students / interventions / evidence_log /
calibration_log / bloom_goals / trajectory_snapshots）。
隐私保护（MVP 简化）：SQLite 文件加密由文件系统层负责，不在应用层实现。
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Iterable

from ..cta.belief_state import BeliefState, BloomProfileState, DimensionState

# ─── Schema SQL ───────────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,
    grade_level INTEGER,
    subject TEXT DEFAULT 'math',
    created_at TEXT NOT NULL,
    last_active_at TEXT,

    current_state_5d TEXT,
    current_bloom_profile TEXT,
    current_learning_dna TEXT,
    tc_states TEXT,
    misconception_history TEXT,
    trajectory_summary TEXT,

    confidence REAL DEFAULT 0.5,
    version TEXT DEFAULT 'v1.0',
    consent_version INTEGER DEFAULT 0,
    anonymized_id TEXT,

    UNIQUE(anonymized_id)
);

CREATE INDEX IF NOT EXISTS idx_students_grade ON students(grade_level);
CREATE INDEX IF NOT EXISTS idx_students_last_active ON students(last_active_at);

CREATE TABLE IF NOT EXISTS interventions (
    intervention_id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,

    intervention_type TEXT NOT NULL,
    bloom_target TEXT NOT NULL,
    target_skills TEXT,
    target_misconceptions TEXT,
    target_tcs TEXT,
    difficulty REAL,
    quantity INTEGER,
    feedback_density REAL,
    scaffolding_level REAL,
    clt_level INTEGER,
    ca_stage INTEGER,
    bjork_triggers TEXT,
    expected_gain REAL,
    expected_risk REAL,
    rationale_text TEXT,
    actual_state_delta REAL,
    actual_bloom_delta TEXT,
    causal_effect REAL,
    causal_p_value REAL,
    causal_significant INTEGER DEFAULT 0,
    calibration_round INTEGER DEFAULT 0,
    is_degraded_mode INTEGER DEFAULT 0,
    human_review_requested INTEGER DEFAULT 0,

    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

CREATE INDEX IF NOT EXISTS idx_interventions_student ON interventions(student_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_interventions_bloom ON interventions(bloom_target);

CREATE TABLE IF NOT EXISTS evidence_log (
    evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    problem_id TEXT,
    timestamp TEXT NOT NULL,

    raw_response TEXT,
    raw_response_time REAL,
    raw_explanation TEXT,
    raw_reflection TEXT,
    llm_critic_input TEXT,
    llm_critic_output TEXT,
    llm_critic_temperature REAL,
    llm_critic_tokens INTEGER,
    structured_correctness INTEGER,
    structured_explanation_quality REAL,
    structured_confusion_signals TEXT,
    structured_self_evaluation REAL,
    state_before_update TEXT,
    state_after_update TEXT,
    state_delta REAL,
    misc_hits TEXT,
    tc_signals TEXT,
    quality_score REAL,

    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

CREATE INDEX IF NOT EXISTS idx_evidence_student ON evidence_log(student_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_evidence_problem ON evidence_log(problem_id);

CREATE TABLE IF NOT EXISTS calibration_log (
    calibration_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    calibration_round INTEGER NOT NULL,

    message_type TEXT NOT NULL,
    message_payload TEXT,
    state_before TEXT,
    state_after TEXT,
    trigger_reason TEXT,
    trigger_evidence TEXT,
    interaction_mode TEXT,
    outcome TEXT,
    human_review_requested INTEGER DEFAULT 0,
    fallback_to_single_agent INTEGER DEFAULT 0,
    duration_ms INTEGER,

    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

CREATE INDEX IF NOT EXISTS idx_calibration_student ON calibration_log(student_id, timestamp);

CREATE TABLE IF NOT EXISTS bloom_goals (
    goal_id TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    skill_name TEXT,
    bloom_layer INTEGER NOT NULL,
    description TEXT,
    cognitive_objectives TEXT,
    assessment_criteria TEXT,
    threshold_concepts TEXT,
    misconceptions TEXT,
    prerequisites TEXT,
    follow_ups TEXT,
    curriculum_standard_ref TEXT,
    created_by TEXT,
    created_at TEXT,
    version TEXT DEFAULT 'v1.0',

    UNIQUE(subject, skill_id, bloom_layer)
);

CREATE INDEX IF NOT EXISTS idx_bloom_goals_subject ON bloom_goals(subject, bloom_layer);
CREATE INDEX IF NOT EXISTS idx_bloom_goals_skill ON bloom_goals(skill_id);

CREATE TABLE IF NOT EXISTS trajectory_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    snapshot_type TEXT,
    epoch INTEGER,
    state_snapshot BLOB,
    bloom_profile_snapshot BLOB,
    learning_dna_snapshot BLOB,
    grade_level INTEGER,
    semester TEXT,
    transfer_metadata TEXT,

    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

CREATE INDEX IF NOT EXISTS idx_trajectory_student ON trajectory_snapshots(student_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_trajectory_type ON trajectory_snapshots(snapshot_type);
"""


# ─── Database ─────────────────────────────────────────────────────────────────

@dataclass
class DatabaseConfig:
    """数据库配置."""
    db_path: str = "ecos.db"
    timeout_sec: float = 10.0


class Database:
    """SQLite 数据库主接口（MVP）。

    用法：
        db = Database("ecos.db")
        db.init_schema()
        db.save_student(student_id, belief_state)
    """

    def __init__(self, config: DatabaseConfig | str | None = None) -> None:
        if isinstance(config, str):
            config = DatabaseConfig(db_path=config)
        self.config = config or DatabaseConfig()
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                self.config.db_path,
                timeout=self.config.timeout_sec,
                detect_types=sqlite3.PARSE_DECLTYPES,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    @contextmanager
    def tx(self) -> Generator[sqlite3.Connection, None, None]:
        """事务上下文管理器."""
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def init_schema(self) -> None:
        """初始化数据库 schema（幂等）."""
        with self.tx() as _:
            self.conn.executescript(SCHEMA_SQL)
        # W5 (2026-07-18): 增量 schema 迁移,加 warmup_count / probe_due_in / probe_count / response_history
        # 用 try/except 容忍 "duplicate column" 错误(老 DB 已有字段)
        for alter_sql in [
            "ALTER TABLE students ADD COLUMN warmup_count INTEGER DEFAULT 0",
            "ALTER TABLE students ADD COLUMN probe_due_in INTEGER DEFAULT 8",
            "ALTER TABLE students ADD COLUMN probe_count INTEGER DEFAULT 0",
            "ALTER TABLE students ADD COLUMN response_history TEXT",
        ]:
            try:
                with self.tx() as _:
                    self.conn.execute(alter_sql)
            except Exception:
                # 字段已存在(老 DB),忽略
                pass

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ─── Students ───────────────────────────────────────────────────────────────

    def upsert_student(
        self,
        student_id: str,
        grade_level: int | None = None,
        subject: str = "math",
        anonymized_id: str | None = None,
    ) -> None:
        now = datetime.now().isoformat()
        with self.tx() as _:
            self.conn.execute(
                """
                INSERT INTO students (student_id, grade_level, subject, created_at, last_active_at, anonymized_id)
                VALUES (:id, :grade, :subject, :now, :now, :anon_id)
                ON CONFLICT(student_id) DO UPDATE SET
                    last_active_at = :now,
                    grade_level = COALESCE(:grade, grade_level)
                """,
                dict(id=student_id, grade=grade_level, subject=subject, now=now, anon_id=anonymized_id),
            )

    def save_student_state(self, student_id: str, state: BeliefState, engine=None) -> None:
        """保存学生完整 BeliefState（MVP JSON 序列化, W5 扩展:warm-up / probe / response_history）。

        Args:
            student_id: 学生 ID
            state: 完整 BeliefState
            engine: 可选 BeliefEngine 实例(W5 用于持久化 warmup_count / probe 状态 / response_history)
        """
        now = datetime.now().isoformat()

        # 5D theta
        theta_5d = json.dumps(state.theta_vector().tolist())
        # Bloom profile
        bp = state.bloom_profile
        bloom_profile_dict = {
            "remember": bp.remember,
            "understand": bp.understand,
            "apply": bp.apply,
            "analyze": bp.analyze,
            "evaluate": bp.evaluate,
            "create": bp.create,
            "dominant_layer": bp.dominant_layer.name,
            "confidence": bp.confidence,
            "evidence_ids": bp.evidence_ids,
        }
        # LearningDNA
        dna = state.learning_dna
        learning_dna_dict = {
            "input_preference": dna.input_preference,
            "feedback_preference": dna.feedback_preference,
            "fatigue_pattern": dna.fatigue_pattern,
            "error_pattern": dna.error_pattern,
            "motivation_pattern": dna.motivation_pattern,
            "confidence": dna.confidence,
        }
        # Misconception hits
        misc_hits = [
            {
                "misc_id": h.misc_id,
                "confidence": h.confidence,
                "trigger_problem_id": h.trigger_problem_id,
                "evidence_text": h.evidence_text,
                "timestamp": h.timestamp.isoformat(),
                "correction_strategy": h.correction_strategy,
            }
            for h in getattr(state.C, "misconception_hits", [])
        ]

        # W5 (2026-07-18): 持久化状态机字段(从 engine 读)
        warmup_count = 0
        probe_due_in = 8
        probe_count = 0
        response_history_json = None
        if engine is not None:
            warmup_count = engine._warmup_count.get(student_id, 0)
            probe_due_in = engine._probe_due_in.get(student_id, engine.config.probe_interval)
            probe_count = engine._probe_count.get(student_id, 0)
            # response_history: List[Tuple[problem_id, int(correct), bloom_level]]
            history = engine._response_history.get(student_id, [])
            # 序列化为 [problem_id, correct_int, bloom_name]
            history_serializable = [
                [pid, int(correct), bl.name if hasattr(bl, "name") else str(bl)]
                for (pid, correct, bl) in history
            ]
            response_history_json = json.dumps(history_serializable)

        with self.tx() as _:
            self.conn.execute(
                """
                UPDATE students SET
                    current_state_5d = :theta,
                    current_bloom_profile = :bloom,
                    current_learning_dna = :dna,
                    misconception_history = :misc,
                    confidence = :conf,
                    warmup_count = :warmup_count,
                    probe_due_in = :probe_due_in,
                    probe_count = :probe_count,
                    response_history = :rh,
                    last_active_at = :now
                WHERE student_id = :id
                """,
                dict(
                    id=student_id,
                    theta=theta_5d,
                    bloom=json.dumps(bloom_profile_dict),
                    dna=json.dumps(learning_dna_dict),
                    misc=json.dumps(misc_hits),
                    conf=state.overall_confidence,
                    warmup_count=warmup_count,
                    probe_due_in=probe_due_in,
                    probe_count=probe_count,
                    rh=response_history_json,
                    now=now,
                ),
            )

    def load_student_state(self, student_id: str) -> dict | None:
        """加载学生状态（返回 dict，MVP；未来可反序列化为 BeliefState）。"""
        row = self.conn.execute(
            "SELECT * FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def load_student_ids(self, limit: int = 100) -> list[str]:
        rows = self.conn.execute(
            "SELECT student_id FROM students ORDER BY last_active_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [r["student_id"] for r in rows]

    # ─── Interventions ──────────────────────────────────────────────────────────

    def save_intervention(self, intervention_id: str, student_id: str, data: dict) -> None:
        """保存一次干预记录（MVP 直接接收 dict）。"""
        now = datetime.now().isoformat()
        with self.tx() as _:
            self.conn.execute(
                """
                INSERT INTO interventions (
                    intervention_id, student_id, timestamp, intervention_type, bloom_target,
                    target_skills, target_misconceptions, target_tcs, difficulty, quantity,
                    feedback_density, scaffolding_level, clt_level, ca_stage, bjork_triggers,
                    expected_gain, expected_risk, rationale_text,
                    actual_state_delta, actual_bloom_delta,
                    causal_effect, causal_p_value, causal_significant,
                    calibration_round, is_degraded_mode, human_review_requested
                ) VALUES (
                    :id, :sid, :ts, :itype, :bloom,
                    :skills, :misc, :tcs, :diff, :qty,
                    :feedback, :scaffold, :clt, :ca, :bjork,
                    :gain, :risk, :rationale,
                    :delta, :bloom_delta,
                    :effect, :pval, :sig,
                    :cal_round, :degraded, :human_review
                )
                """,
                dict(
                    id=intervention_id,
                    sid=student_id,
                    ts=now,
                    itype=data.get("intervention_type", ""),
                    bloom=data.get("bloom_target", ""),
                    skills=json.dumps(data.get("target_skills", [])),
                    misc=json.dumps(data.get("target_misconceptions", [])),
                    tcs=json.dumps(data.get("target_tcs", [])),
                    diff=data.get("difficulty", 0.5),
                    qty=data.get("quantity", 5),
                    feedback=data.get("feedback_density", 0.5),
                    scaffold=data.get("scaffolding_level", 0.5),
                    clt=data.get("clt_level", 2),
                    ca=data.get("ca_stage", 0),
                    bjork=json.dumps(data.get("bjork_triggers", [])),
                    gain=data.get("expected_gain", 0.0),
                    risk=data.get("expected_risk", 0.0),
                    rationale=data.get("rationale_text", ""),
                    delta=data.get("actual_state_delta"),
                    bloom_delta=json.dumps(data.get("actual_bloom_delta", {})),
                    effect=data.get("causal_effect"),
                    pval=data.get("causal_p_value"),
                    sig=int(data.get("causal_significant", 0)),
                    cal_round=data.get("calibration_round", 0),
                    degraded=int(data.get("is_degraded_mode", 0)),
                    human_review=int(data.get("human_review_requested", 0)),
                ),
            )

    def load_intervention_history(
        self, student_id: str, limit: int = 100
    ) -> list[dict]:
        rows = self.conn.execute(
            """SELECT * FROM interventions
               WHERE student_id = ?
               ORDER BY timestamp DESC
               LIMIT ?""",
            (student_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    # ─── Evidence Log ────────────────────────────────────────────────────────

    def save_evidence(self, student_id: str, data: dict) -> int:
        """保存证据记录，返回 evidence_id（MVP 直接接收 dict）。"""
        now = datetime.now().isoformat()
        with self.tx() as _:
            cur = self.conn.execute(
                """
                INSERT INTO evidence_log (
                    student_id, problem_id, timestamp,
                    raw_response, raw_response_time, raw_explanation, raw_reflection,
                    llm_critic_input, llm_critic_output, llm_critic_temperature, llm_critic_tokens,
                    structured_correctness, structured_explanation_quality,
                    structured_confusion_signals, structured_self_evaluation,
                    state_before_update, state_after_update, state_delta,
                    misc_hits, tc_signals, quality_score
                ) VALUES (
                    :sid, :pid, :ts,
                    :raw, :rtime, :expl, :refl,
                    :llm_in, :llm_out, :llm_temp, :llm_tokens,
                    :correct, :qual,
                    :confusion, :self_eval,
                    :before, :after, :delta,
                    :misc, :tc, :quality
                )
                """,
                dict(
                    sid=student_id,
                    pid=data.get("problem_id", ""),
                    ts=now,
                    raw=data.get("raw_response", ""),
                    rtime=data.get("raw_response_time", 0.0),
                    expl=data.get("raw_explanation", ""),
                    refl=data.get("raw_reflection", ""),
                    llm_in=data.get("llm_critic_input", ""),
                    llm_out=data.get("llm_critic_output", ""),
                    llm_temp=data.get("llm_critic_temperature"),
                    llm_tokens=data.get("llm_critic_tokens"),
                    correct=int(data.get("structured_correctness", 0)),
                    qual=data.get("structured_explanation_quality", 0.0),
                    confusion=json.dumps(data.get("structured_confusion_signals", [])),
                    self_eval=data.get("structured_self_evaluation", 0.0),
                    before=data.get("state_before_update", ""),
                    after=data.get("state_after_update", ""),
                    delta=data.get("state_delta", 0.0),
                    misc=json.dumps(data.get("misc_hits", [])),
                    tc=json.dumps(data.get("tc_signals", [])),
                    quality=data.get("quality_score", 0.0),
                ),
            )
            return cur.lastrowid or 0

    def load_evidence(
        self, student_id: str, limit: int = 100, offset: int = 0
    ) -> list[dict]:
        rows = self.conn.execute(
            """SELECT * FROM evidence_log
               WHERE student_id = ?
               ORDER BY timestamp DESC
               LIMIT ? OFFSET ?""",
            (student_id, limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]

    # ─── Calibration Log ───────────────────────────────────────────────────────

    def save_calibration(self, student_id: str, data: dict) -> int:
        """保存互校记录（MVP 直接接收 dict）。"""
        now = datetime.now().isoformat()
        with self.tx() as _:
            cur = self.conn.execute(
                """
                INSERT INTO calibration_log (
                    student_id, timestamp, calibration_round,
                    message_type, message_payload,
                    state_before, state_after,
                    trigger_reason, trigger_evidence,
                    interaction_mode, outcome,
                    human_review_requested, fallback_to_single_agent,
                    duration_ms
                ) VALUES (
                    :sid, :ts, :round,
                    :msg_type, :payload,
                    :before, :after,
                    :reason, :evidence,
                    :mode, :outcome,
                    :human, :fallback,
                    :duration
                )
                """,
                dict(
                    sid=student_id,
                    ts=now,
                    round=data.get("calibration_round", 0),
                    msg_type=data.get("message_type", ""),
                    payload=json.dumps(data.get("message_payload", {})),
                    before=data.get("state_before", ""),
                    after=data.get("state_after", ""),
                    reason=data.get("trigger_reason", ""),
                    evidence=json.dumps(data.get("trigger_evidence", {})),
                    mode=data.get("interaction_mode", "normal"),
                    outcome=data.get("outcome", ""),
                    human=int(data.get("human_review_requested", 0)),
                    fallback=int(data.get("fallback_to_single_agent", 0)),
                    duration=data.get("duration_ms"),
                ),
            )
            return cur.lastrowid or 0

    def load_calibration_history(self, student_id: str, limit: int = 100) -> list[dict]:
        rows = self.conn.execute(
            """SELECT * FROM calibration_log
               WHERE student_id = ?
               ORDER BY timestamp DESC
               LIMIT ?""",
            (student_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    # ─── Bloom Goals ───────────────────────────────────────────────────────────

    def save_bloom_goal(self, goal_id: str, data: dict) -> None:
        """保存 Bloom 目标（MVP 直接接收 dict）。"""
        with self.tx() as _:
            self.conn.execute(
                """
                INSERT INTO bloom_goals (
                    goal_id, subject, skill_id, skill_name, bloom_layer,
                    description, cognitive_objectives, assessment_criteria,
                    threshold_concepts, misconceptions,
                    prerequisites, follow_ups,
                    curriculum_standard_ref, created_by, created_at, version
                ) VALUES (
                    :gid, :subj, :sid, :sname, :blvl,
                    :desc, :cog, :assess,
                    :tcs, :misc,
                    :prereq, :followup,
                    :std, :by, :now, :ver
                )
                ON CONFLICT(goal_id) DO UPDATE SET
                    description = :desc,
                    assessment_criteria = :assess
                """,
                dict(
                    gid=goal_id,
                    subj=data.get("subject", "math"),
                    sid=data.get("skill_id", ""),
                    sname=data.get("skill_name", ""),
                    blvl=data.get("bloom_layer", 3),
                    desc=data.get("description", ""),
                    cog=json.dumps(data.get("cognitive_objectives", [])),
                    assess=json.dumps(data.get("assessment_criteria", [])),
                    tcs=json.dumps(data.get("threshold_concepts", [])),
                    misc=json.dumps(data.get("misconceptions", [])),
                    prereq=json.dumps(data.get("prerequisites", [])),
                    followup=json.dumps(data.get("follow_ups", [])),
                    std=data.get("curriculum_standard_ref", ""),
                    by=data.get("created_by", ""),
                    now=datetime.now().isoformat(),
                    ver=data.get("version", "v1.0"),
                ),
            )

    def load_bloom_goals(
        self, subject: str = "math", bloom_layer: int | None = None
    ) -> list[dict]:
        if bloom_layer is None:
            rows = self.conn.execute(
                "SELECT * FROM bloom_goals WHERE subject = ? ORDER BY skill_id, bloom_layer",
                (subject,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM bloom_goals WHERE subject = ? AND bloom_layer = ? ORDER BY skill_id",
                (subject, bloom_layer),
            ).fetchall()
        return [dict(r) for r in rows]

    # ─── Trajectory Snapshots ──────────────────────────────────────────────────

    def save_trajectory_snapshot(
        self,
        student_id: str,
        snapshot_type: str,
        epoch: int,
        state_snapshot: bytes | None = None,
        bloom_snapshot: bytes | None = None,
        dna_snapshot: bytes | None = None,
        grade_level: int | None = None,
        semester: str | None = None,
    ) -> int:
        """保存轨迹快照（不可变）。"""
        now = datetime.now().isoformat()
        with self.tx() as _:
            cur = self.conn.execute(
                """
                INSERT INTO trajectory_snapshots (
                    student_id, timestamp, snapshot_type, epoch,
                    state_snapshot, bloom_profile_snapshot, learning_dna_snapshot,
                    grade_level, semester
                ) VALUES (
                    :sid, :ts, :stype, :epoch,
                    :state, :bloom, :dna,
                    :grade, :sem
                )
                """,
                dict(
                    sid=student_id,
                    ts=now,
                    stype=snapshot_type,
                    epoch=epoch,
                    state=state_snapshot,
                    bloom=bloom_snapshot,
                    dna=dna_snapshot,
                    grade=grade_level,
                    sem=semester,
                ),
            )
            return cur.lastrowid or 0

    def load_trajectory_snapshots(
        self,
        student_id: str,
        snapshot_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        if snapshot_type:
            rows = self.conn.execute(
                """SELECT * FROM trajectory_snapshots
                   WHERE student_id = ? AND snapshot_type = ?
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (student_id, snapshot_type, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT * FROM trajectory_snapshots
                   WHERE student_id = ?
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (student_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]
