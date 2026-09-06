"""SQLite 数据库层——连接管理 + Schema 初始化.

对应 research/10-engineering/05-persistence-session.md §2。

MVP 范围：6 张核心表（students / interventions / evidence_log /
calibration_log / bloom_goals / trajectory_snapshots）。
隐私保护（MVP 简化）：SQLite 文件加密由文件系统层负责，不在应用层实现。
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Iterable, Optional

from ..cta.belief_state import BeliefState, BloomProfileState, DimensionState

_log = logging.getLogger(__name__)

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

# v0.97.3: misconception_evidence 表 (P2 A2 reconcile 持久化).
#   CogMirror A2 同款, ECOS 多人版加 student_id 区分. PK = (student_id, misc_id)
#   保证 save_misconception_evidence 多次调用 upsert 不重复.
_MISCONCEPTION_EVIDENCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS misconception_evidence (
    student_id TEXT NOT NULL,
    misc_id TEXT NOT NULL,
    success_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    last_updated TEXT NOT NULL,
    PRIMARY KEY (student_id, misc_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

CREATE INDEX IF NOT EXISTS idx_misconception_evidence_student
    ON misconception_evidence(student_id);
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
                # v0.51.1: Flask dev server threaded=True, SQLite 对象跨线程报错
                #   "SQLite objects created in a thread can only be used in that same thread"
                #   Bisen 反馈 v0.51.0 刷新后第一次 /api/state 报 HTTP 500
                #   根因: connection 在主线程创建,后续新线程请求复用同一 connection
                #   修复: check_same_thread=False + WAL 模式 (WAL 允许 reader/writer 并发)
                check_same_thread=False,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute("PRAGMA journal_mode = WAL")
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
        # v0.97.3: P2 A2 reconcile misconception_evidence 表 (per-student per-misc
        #   成功/失败计数, PK=(student_id, misc_id) upsert 幂等; 不放 evidence_log
        #   是因为这是 derived 状态, 走自己表干净, 跟 calibration_log 同样模式)
        with self.tx() as _:
            self.conn.executescript(_MISCONCEPTION_EVIDENCE_SCHEMA)
        # W5 (2026-07-18): 增量 schema 迁移,加 warmup_count / probe_due_in / probe_count / response_history
        # v0.47.9: 加 theta_cov (5x5 MIRT 后验协方差矩阵,JSON 序列化)
        #   Bisen 反馈: 重启后 theta_se 全是 1.0,因为 theta_cov 不存 DB → 走 np.eye(5) 默认
        #   存上后才能正确反映 MIRT 估算的不确定度
        # 用 try/except 容忍 "duplicate column" 错误(老 DB 已有字段)
        for alter_sql in [
            "ALTER TABLE students ADD COLUMN warmup_count INTEGER DEFAULT 0",
            "ALTER TABLE students ADD COLUMN probe_due_in INTEGER DEFAULT 8",
            "ALTER TABLE students ADD COLUMN probe_count INTEGER DEFAULT 0",
            "ALTER TABLE students ADD COLUMN response_history TEXT",
            "ALTER TABLE students ADD COLUMN theta_cov TEXT",
            # v0.91.0-d: cognitive_twin 字段 (Twin → Human Twin 抽象)
            #   JSON dump CognitiveTwinAgent (含 HumanFeedbackTrajectory entries)
            "ALTER TABLE students ADD COLUMN cognitive_twin TEXT",
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

    def save_student_state(
        self,
        student_id: str,
        state: BeliefState,
        engine=None,
        cognitive_twin_json: Optional[str] = None,
    ) -> None:
        """保存学生完整 BeliefState（MVP JSON 序列化, W5 扩展:warm-up / probe / response_history）。

        Args:
            student_id: 学生 ID
            state: 完整 BeliefState
            engine: 可选 BeliefEngine 实例(W5 用于持久化 warmup_count / probe 状态 / response_history)
            cognitive_twin_json: v0.91.0-d: 可选 CognitiveTwinAgent.dump_state() JSON 序列化结果
                                 (Twin → Human Twin 抽象, 由 caller 提供)
        """
        now = datetime.now().isoformat()

        # 5D theta
        theta_5d = json.dumps(state.theta_vector().tolist())
        # v0.47.9: 5D 后验协方差矩阵(MIRT 估算的不确定度)
        #   之前不存 → 重启后 theta_se 全是 1.0(np.eye(5) 默认)
        #   存上后,DB 恢复时反序列化,get_student_state 返回的 theta_se 才是真实估算值
        theta_cov_json = json.dumps(state.theta_cov.tolist()) if state.theta_cov is not None else None
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
            # response_history: v0.49.2 起改 dict 格式（含 user_answer/timestamp）
            #   兼容老 3-tuple 数据
            history = engine._response_history.get(student_id, [])
            history_serializable = []
            for h in history:
                if isinstance(h, dict):
                    # 新格式: 去掉内部字段 _bloom_level_enum（不存 DB）
                    serializable = {k: v for k, v in h.items() if not k.startswith("_")}
                    history_serializable.append(serializable)
                else:
                    # 老 3-tuple 格式 (v0.49.2 之前)
                    pid, correct, bl = h
                    history_serializable.append({
                        "problem_id": pid,
                        "correct": int(correct),
                        "bloom_level": bl.name if hasattr(bl, "name") else str(bl),
                        "user_answer": None,
                        "correct_answer": None,
                        "ai_reasoning": None,  # v0.52.2: 老数据无 reasoning
                        "timestamp": None,
                    })
            response_history_json = json.dumps(history_serializable)

        # W5+ (2026-07-18): 持久化 TC states（之前漏了——Bisen 反馈"TC 状态重启后没了"）
        tc_states_dict = {
            tc_id: {
                "tc_id": tc.tc_id,
                "status": tc.status,
                "progress": tc.progress,
                "confidence": tc.confidence,
                "liminal_signals": tc.liminal_signals,
                "post_liminal_jump_detected": tc.post_liminal_jump_detected,
                "irreversible": tc.irreversible,
                "timestamp": tc.timestamp.isoformat() if hasattr(tc.timestamp, "isoformat") else str(tc.timestamp),
            }
            for tc_id, tc in getattr(state.C, "tc_states", {}).items()
        }
        tc_states_json = json.dumps(tc_states_dict)

        # W5+ (2026-07-18): 持久化 trajectory 最近 N 个 snapshot
        # （之前漏了——Bisen 反馈"成长轨迹重启后没了"）
        # v0.47.5: last_n(20) → last_n(500),配 in-memory cap 扩大,完整保留成长轨迹
        # v0.47.5: except: pass/continue 改 logger.warning(..., exc_info=True)
        #   解决"silent failure 丢数据"问题(Bisen 反馈 7-19 17:14 答的那题没存但 history 里也没有)
        trajectory_snapshots = []
        import logging
        _log = logging.getLogger(__name__)
        try:
            recent_snapshots = state.trajectory.last_n(500)
            for snap in recent_snapshots:
                try:
                    snap_dict = {
                        "timestamp": snap.timestamp.isoformat() if hasattr(snap.timestamp, "isoformat") else str(snap.timestamp),
                        "theta_5d": [float(v) for v in snap.theta_5d],
                        "confidence": float(snap.confidence),
                        "bloom_dominant": snap.bloom_profile.dominant_layer.name if (snap.bloom_profile and snap.bloom_profile.dominant_layer) else None,
                        "misc_history": list(snap.misc_history) if hasattr(snap, "misc_history") else [],
                    }
                    # TC states in snapshot
                    snap_tc = {}
                    if hasattr(snap, "tc_states") and snap.tc_states:
                        for tc_id, tc in snap.tc_states.items():
                            snap_tc[tc_id] = {
                                "status": tc.status,
                                "progress": tc.progress,
                            }
                    if snap_tc:
                        snap_dict["tc_states"] = snap_tc
                    trajectory_snapshots.append(snap_dict)
                except Exception as e:
                    # v0.47.5: 之前静默 continue,某条 snapshot 失败直接丢,数据不完整但没人知道
                    _log.warning(
                        "trajectory snapshot 序列化失败 (student=%s, ts=%s): %s",
                        student_id,
                        getattr(snap, "timestamp", "?"),
                        e,
                        exc_info=True,
                    )
                    continue
        except Exception as e:
            _log.warning(
                "trajectory 整体序列化失败 (student=%s, %d snapshots): %s",
                student_id, len(state.trajectory.snapshots), e,
                exc_info=True,
            )
            trajectory_snapshots = []
        trajectory_summary_json = json.dumps(trajectory_snapshots)

        with self.tx() as _:
            self.conn.execute(
                """
                UPDATE students SET
                    current_state_5d = :theta,
                    current_bloom_profile = :bloom,
                    current_learning_dna = :dna,
                    tc_states = :tc_states,
                    misconception_history = :misc,
                    trajectory_summary = :trajectory,
                    confidence = :conf,
                    warmup_count = :warmup_count,
                    probe_due_in = :probe_due_in,
                    probe_count = :probe_count,
                    response_history = :rh,
                    theta_cov = :theta_cov,
                    cognitive_twin = :cognitive_twin,
                    last_active_at = :now
                WHERE student_id = :id
                """,
                dict(
                    id=student_id,
                    theta=theta_5d,
                    bloom=json.dumps(bloom_profile_dict),
                    dna=json.dumps(learning_dna_dict),
                    tc_states=tc_states_json,
                    misc=json.dumps(misc_hits),
                    trajectory=trajectory_summary_json,
                    conf=state.overall_confidence,
                    warmup_count=warmup_count,
                    probe_due_in=probe_due_in,
                    probe_count=probe_count,
                    rh=response_history_json,
                    theta_cov=theta_cov_json,
                    cognitive_twin=cognitive_twin_json,
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

    def update_calibration_actual_outcome(
        self,
        student_id: str,
        calibration_round: int,
        actual_outcome: float,
    ) -> int:
        """v0.64.0: 回写 calibration_log 某行的 actual_outcome 字段.

        背景 (v0.60.4 留下的 BUG):
          prev_calibrated.actual_outcome 在 orch.process_observation 内部被填上
          (基于本次 observation.score), 但**没回写 DB**. 所以 calibration_log 表里
          所有 prev 行的 actual_outcome 都是 None, H3 验证算不出 ECE.

        修复: dual_agent._write_calibration_log 前先调这个方法, 把 prev (round-1)
              的 actual_outcome 回写.

        Args:
            student_id: 学生 ID
            calibration_round: 哪一轮 (通常是 prev 的 round)
            actual_outcome: 实际 outcome (0.0-1.0, v0.61.0 改 score 派生)

        Returns:
            更新的行数 (0 表示 round 不存在, 1 表示更新成功).
        """
        # 防御性自检 [1]: 失败 _log.warning + raise (让 caller 决定怎么处理)
        try:
            # 先查现有 message_payload (避免覆盖其他字段)
            row = self.conn.execute(
                """SELECT message_payload FROM calibration_log
                   WHERE student_id = ? AND calibration_round = ?""",
                (student_id, calibration_round),
            ).fetchone()
            if row is None:
                return 0
            existing = json.loads(row["message_payload"]) if row["message_payload"] else {}
            existing["actual_outcome"] = float(actual_outcome)
            with self.tx():
                self.conn.execute(
                    """UPDATE calibration_log
                       SET message_payload = ?
                       WHERE student_id = ? AND calibration_round = ?""",
                    (
                        json.dumps(existing, ensure_ascii=False),
                        student_id,
                        calibration_round,
                    ),
                )
            return 1
        except Exception:
            _log.warning(
                "update_calibration_actual_outcome 失败 (student=%s, round=%s), "
                "prev calibration_log 实际 outcome 留 None",
                student_id, calibration_round, exc_info=True,
            )
            raise

    # ─── Event Log (v0.81.0-a) ──────────────────────────────────────────────────

    def save_event(
        self,
        event_id: str,
        student_id: str,
        timestamp: str,
        source: str,
        event_type: str,
        payload_json: str,
    ) -> None:
        """v0.81.0-a: 持久化 LearningEvent 到 event_log 表.

        Mirror calibration_log save pattern. INSERT OR IGNORE dedups by event_id PRIMARY KEY.
        Callers normally use EventLog.log_event() (ecos/cta/event_log.py) which wraps this.
        This method is exposed on Database for direct DB-level integration tests.
        """
        with self.tx() as _:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO event_log (
                    event_id, student_id, timestamp, source, event_type, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (event_id, student_id, timestamp, source, event_type, payload_json),
            )

    def load_event_history(
        self,
        student_id: str,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[dict]:
        """v0.81.0-a: 加载学生的 event_log 历史 (按时间升序, 用于 replay).

        Args:
            student_id: 学生 ID
            since: ISO timestamp, 包含
            until: ISO timestamp, 包含
            limit: 最多返回 N 条 (None = 不限)

        Returns:
            list of dict (event_id, student_id, timestamp, source, event_type, payload_json)
            按时间升序排, 直接喂给 StateEngine.replay / BeliefEngine.replay.
        """
        query = "SELECT * FROM event_log WHERE student_id = ?"
        params: list[Any] = [student_id]
        if since is not None:
            query += " AND timestamp >= ?"
            params.append(since)
        if until is not None:
            query += " AND timestamp <= ?"
            params.append(until)
        query += " ORDER BY timestamp ASC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def count_events(self, student_id: str) -> int:
        """v0.81.0-a: 统计学生 event_log 条数 (用于测试 / debug)."""
        row = self.conn.execute(
            "SELECT COUNT(*) FROM event_log WHERE student_id = ?",
            (student_id,),
        ).fetchone()
        return int(row[0]) if row else 0

    # ─── Misconception Evidence (v0.97.3, P2 A2 reconcile) ──────────────────

    def save_misconception_evidence(
        self,
        student_id: str,
        rows: list[dict],
    ) -> int:
        """v0.97.3: 落 per-misconception 证据 (CogMirror A2 移植, ECOS 多人版).

        Args:
            student_id: 学生 ID
            rows: list of dict, 每条含 misc_id / success_count / failure_count
                  / last_updated (MisconceptionEvidenceTracker.dump() 格式)

        Returns:
            实际写入/更新行数 (UPSERT: PK=(student_id, misc_id) 已存在则覆盖
            计数并更新 last_updated; 不存在则插入)
        """
        if not rows:
            return 0
        written = 0
        with self.tx() as _:
            for r in rows:
                misc_id = r.get("misc_id")
                if not misc_id:
                    continue
                self.conn.execute(
                    """
                    INSERT INTO misconception_evidence (
                        student_id, misc_id, success_count, failure_count, last_updated
                    ) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(student_id, misc_id) DO UPDATE SET
                        success_count = excluded.success_count,
                        failure_count = excluded.failure_count,
                        last_updated = excluded.last_updated
                    """,
                    (
                        student_id,
                        misc_id,
                        int(r.get("success_count", 0)),
                        int(r.get("failure_count", 0)),
                        r.get("last_updated", "") or datetime.now().isoformat(),
                    ),
                )
                written += 1
        return written

    def load_misconception_evidence(
        self,
        student_id: str,
        misc_id: str | None = None,
    ) -> list[dict]:
        """v0.97.3: 加载 per-misconception 证据 (web 答题流注入 + 教师端展示用).

        Args:
            student_id: 学生 ID
            misc_id: 可选, 只查单条 misc (None = 该学生全部)

        Returns:
            list of dict, 每条含 misc_id / success_count / failure_count /
            last_updated (与 save_misconception_evidence 输出一致, 可直接
            喂给 MisconceptionEvidenceTracker.load())
        """
        if misc_id is not None:
            rows = self.conn.execute(
                """SELECT misc_id, success_count, failure_count, last_updated
                   FROM misconception_evidence
                   WHERE student_id = ? AND misc_id = ?
                   ORDER BY misc_id""",
                (student_id, misc_id),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT misc_id, success_count, failure_count, last_updated
                   FROM misconception_evidence
                   WHERE student_id = ?
                   ORDER BY misc_id""",
                (student_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_misconception_evidence(self, student_id: str) -> int:
        """v0.97.3: 清除某学生全部 per-misconception 证据 (合规删除 / 测试用).

        Returns:
            删除行数
        """
        with self.tx() as _:
            cur = self.conn.execute(
                "DELETE FROM misconception_evidence WHERE student_id = ?",
                (student_id,),
            )
            return cur.rowcount or 0

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


# ─── Singleton accessor (v0.60.1: 给 web/api/dual_agent.py 用) ───

_db_instance: Optional["Database"] = None


def get_db(db_path: str = "web/ecos.db") -> "Database":
    """获取 Database 全局单例 (lazy init).

    防御性自检 [1]: init 失败必须 warning, 不能 silent pass.

    v0.60.1 新增: web/api/dual_agent.py (双 Agent 互校接入) 需要
    复用 Database 单例, 避免每次新建 connection + 重复 init_schema.
    """
    global _db_instance
    if _db_instance is None:
        try:
            _db_instance = Database(DatabaseConfig(db_path=db_path))
            # v0.60.1 修 (CI 失败 root cause #2): 调 init_schema() 确保 schema 存在
            # 幂等: CREATE TABLE IF NOT EXISTS + ALTER TABLE ... try/except
            # CI 干净环境 (无 web/ecos.db) 必须 init_schema, 否则 save_calibration 失败
            # 跟 web/api/belief.py:_get_db() 同样模式
            _db_instance.init_schema()
        except Exception:
            _log.warning(
                "Database 单例初始化失败 (db=%s), 持久化不可用",
                db_path, exc_info=True,
            )
            raise
    return _db_instance

