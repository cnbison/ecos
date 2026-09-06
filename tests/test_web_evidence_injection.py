"""v0.98.0 (b-b): web 注入 EvidenceEngine + EventLog 集成测试.

对应 web/api/belief.py 两处 BeliefEngine 构造 (DB 恢复路径 + 全新路径)
注入 evidence_engine + event_log (接线审计实例 ③ web 侧收口):

  - submit 答题 -> evidence_log 落 per-dim 5 行 (payload 含 dim 标记)
  - submit 答题 -> event_log 落 2 行 (response_submitted + observation)
  - event_log retention 配置生效 (max_per_student / retention_days)
  - FK 写库失败兜底 (add 返回 0 不炸主流程)
  - event_id 幂等 (EventLog 主键 INSERT OR IGNORE)
"""
from __future__ import annotations

import json
import os
import tempfile

import pytest

from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig
from ecos.cta.event_log import EventLog
from ecos.persistence.db import Database, DatabaseConfig
from web.api import belief as belief_api


@pytest.fixture
def tmp_db():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "b.db")
        db = Database(DatabaseConfig(db_path=path))
        try:
            db.init_schema()
            yield db
        finally:
            db.close()


@pytest.fixture
def wired_env(tmp_db, monkeypatch):
    """隔离环境: _get_db 指向 tmp_db, event_log 用 in-memory, 重置单例缓存.

    注意: _evidence_engine 单例不预置 (None), 让 _get_evidence_engine()
    用 monkeypatch 后的 _get_db()/_get_web_event_log() 重建 —— 这正是
    被测行为本身 (单例按当前依赖组装)。测试后重置全局, 防污染其他测试。
    """
    monkeypatch.setattr(belief_api, "_get_db", lambda: tmp_db)
    monkeypatch.setattr(
        belief_api, "_web_event_log", EventLog.in_memory(),
    )
    monkeypatch.setattr(belief_api, "_evidence_engine", None)
    # get_llm 无 API key 会 raise, 测试统一给 None (与测试环境惯例一致)
    import web.api.app as app_mod
    monkeypatch.setattr(app_mod, "get_llm", lambda: None)
    yield tmp_db
    # 重置单例缓存 (monkeypatch 会还原属性, 但显式重置防 session 泄漏)
    belief_api._evidence_engine = None
    belief_api._web_event_log = None
    belief_api._db = None
    # 清掉本 fixture 期间创建的 _STUDENT_STATES 条目 (engine 绑定已关闭的 tmp db)
    for sid in [
        s for s in belief_api._STUDENT_STATES if s.startswith("stu_v098_")
    ]:
        belief_api._STUDENT_STATES.pop(sid, None)


def test_fresh_path_injects_evidence_engine_and_event_log(wired_env):
    """全新路径 (DB 无记录): BeliefEngine 构造注入 evidence_engine + event_log."""
    student = belief_api._get_or_create_student("stu_v098_fresh")
    engine = student["engine"]
    assert engine._belief_updater.evidence_engine is not None
    assert engine._belief_updater.event_log is not None
    # FeatureExtractor 同样拿到 event_log (response_submitted emit)
    assert engine._feature_extractor._event_log is not None


def test_db_restore_path_injects_evidence_engine_and_event_log(wired_env):
    """DB 恢复路径 (已有记录): 同样注入 (漏一处 = 恢复学生静默无 evidence)."""
    db = wired_env
    db.upsert_student("stu_v098_restore", subject="python")
    student = belief_api._get_or_create_student("stu_v098_restore")
    engine = student["engine"]
    assert engine._belief_updater.evidence_engine is not None
    assert engine._feature_extractor._event_log is not None


def test_submit_writes_evidence_log_per_dim_with_marker(wired_env, monkeypatch):
    """submit 真实 update 路径 -> evidence_log 落 per-dim 行, payload 含 dim.

    dim_updates 仅在 len(history) >= 2 时产出 (inference_engine.py:204),
    所以连答 2 题后再断言。"""
    db = wired_env
    monkeypatch.setattr(
        belief_api, "_update_via_plugin_or_legacy",
        lambda engine, state, obs, student_id: engine.update(state, obs),
    )
    student = belief_api._get_or_create_student("stu_v098_evi")
    engine = student["engine"]
    state = student["state"]

    for pid in ("prob_001", "prob_002"):
        belief_api.submit_answer(
            student_id="stu_v098_evi", problem_id=pid,
            skill_id="math.frac", correct=True, bloom_layer="L3", score=1.0,
        )

    rows = db.load_evidence("stu_v098_evi", limit=50)
    assert len(rows) >= 5  # 第 2 题起 5 dim 各 1 行
    dims = set()
    for row in rows:
        payload = json.loads(row["raw_response"])
        dims.add(payload.get("dim"))
    assert {"K", "P", "S", "C", "X"} <= dims
    # state 侧 allowlist 入口也真实化
    assert len(state.K.evidence_ids) >= 1
    assert all(eid != 0 for eid in state.K.evidence_ids)


def test_submit_writes_event_log_two_event_types(wired_env, monkeypatch):
    """submit 真实 update 路径 -> event_log 落 response_submitted + observation 两类."""
    db = wired_env
    monkeypatch.setattr(
        belief_api, "_update_via_plugin_or_legacy",
        lambda engine, state, obs, student_id: engine.update(state, obs),
    )
    belief_api._get_or_create_student("stu_v098_evt")

    for pid in ("prob_001", "prob_002"):
        belief_api.submit_answer(
            student_id="stu_v098_evt", problem_id=pid,
            skill_id="math.frac", correct=True, bloom_layer="L3", score=1.0,
        )

    event_log = belief_api._get_web_event_log()
    events = event_log.load_events("stu_v098_evt")
    event_types = {e.event_type for e in events}
    assert "response_submitted" in event_types
    assert "observation" in event_types


def test_web_event_log_sqlite_singleton_carries_retention(tmp_db, monkeypatch):
    """sqlite 路径单例: _get_web_event_log() 带 retention 配置.

    monkeypatch _WEB_DB_PATH 指向 tmp 目录, 避免触碰生产 web/ecos.db;
    用独立测试不复用 wired_env (那里 event_log 被 in-memory 替换)。"""
    with tempfile.TemporaryDirectory() as d:
        monkeypatch.setattr(belief_api, "_WEB_DB_PATH", os.path.join(d, "evt.db"))
        monkeypatch.setattr(belief_api, "_web_event_log", None)
        log = belief_api._get_web_event_log()
        cfg = log._config
        assert cfg.max_per_student == belief_api._EVENT_LOG_MAX_PER_STUDENT
        assert cfg.retention_days == belief_api._EVENT_LOG_RETENTION_DAYS
        assert cfg.auto_prune_on_log is True
        assert log._mode == "sqlite"
        belief_api._web_event_log = None  # 关闭后重置, 防 tmp 文件句柄悬挂


def test_evidence_fk_failure_returns_zero_not_crash(wired_env):
    """FK 写库失败 (student 行不存在) -> _add_to_evidence_log 吞为 0, 不 raise."""
    from datetime import datetime

    from ecos.evidence import Evidence, EvidenceSource

    engine = belief_api._get_evidence_engine()
    ev = Evidence(
        source=EvidenceSource.RESPONSE_HISTORY,
        student_id="stu_v098_nofk",  # 不 upsert, FK 违反
        timestamp=datetime.now(),
        payload={"score": 1.0, "dim": "K"},
        confidence=0.9,
    )
    evidence_id = engine.add(ev)  # 不应 raise
    assert evidence_id == 0


def test_event_log_event_id_idempotent(wired_env):
    """EventLog 主键幂等: 同 event_id 重复 log_event 不产生第二行."""
    from datetime import datetime

    from ecos.cta.event_log import LearningEvent

    log = belief_api._get_web_event_log()
    event = LearningEvent(
        event_id="evt_v098_dup", student_id="stu_v098_idem",
        timestamp=datetime.now(), source="test", event_type="observation",
        payload={"k": 1},
    )
    log.log_event(event)
    log.log_event(event)  # 重复
    events = log.load_events("stu_v098_idem")
    assert len(events) == 1


def test_evidence_engine_singleton_reuses_instance(wired_env):
    """_get_evidence_engine 单例: 二次调用返回同一实例 (不重复建 engine)."""
    e1 = belief_api._get_evidence_engine()
    e2 = belief_api._get_evidence_engine()
    assert e1 is e2


# ──────────────────────────────────────────────────────────────────────
# v0.98.0 (b-b): evidence_log CASCADE 迁移 (v0.97.3 a-fix 同类, 硬规则 #8)
# ──────────────────────────────────────────────────────────────────────


def _make_old_schema_db(path: str) -> Database:
    """构造老 schema (无 CASCADE) evidence_log 的 DB, 模拟升级前 dev DB.

    做法: 先建全量新 schema, 再把 evidence_log 降级为老 DDL
    (students 全列保留, 避免 init_schema 的 IF NOT EXISTS 跳过建表)。"""
    db = Database(DatabaseConfig(db_path=path))
    db.init_schema()
    db.conn.executescript("""
    DROP TABLE evidence_log;
    CREATE TABLE evidence_log (
        evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        problem_id TEXT,
        timestamp TEXT NOT NULL,
        raw_response TEXT,
        quality_score REAL,
        FOREIGN KEY (student_id) REFERENCES students(student_id)
    );
    """)
    db.conn.commit()
    db.close()
    return Database(DatabaseConfig(db_path=path))


class TestEvidenceLogCascadeMigration:
    """v0.98.0 (b-b): evidence_log ON DELETE CASCADE 迁移 (rename→rebuild→搬数据)."""

    def test_migration_adds_cascade_and_preserves_rows(self, tmp_path):
        """老 schema 升级: CASCADE 出现 + 已有行保留."""
        path = str(tmp_path / "old.db")
        db = _make_old_schema_db(path)
        try:
            db.init_schema()  # 触发迁移 (老 schema -> CASCADE)
            ddl = db.conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='evidence_log'"
            ).fetchone()[0]
            assert "ON DELETE CASCADE" in ddl

            db.upsert_student("mig_stu", subject="python")
            db.conn.execute(
                "INSERT INTO evidence_log (student_id, problem_id, timestamp, raw_response) "
                "VALUES ('mig_stu', 'p1', '2026-09-06T00:00:00', '{}')"
            )
            db.conn.commit()
            db.close()

            # 重新 open + init_schema (幂等) -> 已有行保留
            db2 = Database(DatabaseConfig(db_path=path))
            try:
                db2.init_schema()
                rows = db2.conn.execute(
                    "SELECT * FROM evidence_log WHERE student_id='mig_stu'"
                ).fetchall()
                assert len(rows) == 1
            finally:
                db2.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_migration_idempotent(self, tmp_path):
        """已是新 schema 的 DB 再跑 init_schema 不重建 (行数不翻倍)."""
        path = str(tmp_path / "new.db")
        db = Database(DatabaseConfig(db_path=path))
        try:
            db.init_schema()
            db.init_schema()  # 二次调用
            ddl = db.conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='evidence_log'"
            ).fetchone()[0]
            assert "ON DELETE CASCADE" in ddl
            assert db.conn.execute("SELECT COUNT(*) FROM evidence_log").fetchone()[0] == 0
        finally:
            db.close()

    def test_cascade_deletes_evidence_with_student(self, tmp_path):
        """删除 students 行 -> evidence_log 行随 CASCADE 清理."""
        path = str(tmp_path / "cas.db")
        db = Database(DatabaseConfig(db_path=path))
        try:
            db.init_schema()
            db.upsert_student("cas_stu", subject="python")
            db.conn.execute(
                "INSERT INTO evidence_log (student_id, problem_id, timestamp, raw_response) "
                "VALUES ('cas_stu', 'p1', '2026-09-06T00:00:00', '{}')"
            )
            db.conn.commit()
            db.conn.execute("PRAGMA foreign_keys=ON")
            db.conn.execute("DELETE FROM students WHERE student_id='cas_stu'")
            db.conn.commit()
            remaining = db.conn.execute(
                "SELECT COUNT(*) FROM evidence_log WHERE student_id='cas_stu'"
            ).fetchone()[0]
            assert remaining == 0
        finally:
            db.close()


class TestEventLogCascadeMigration:
    """v0.98.0 (b-b): event_log ON DELETE CASCADE 迁移 (硬规则 #8 同类扫描发现)."""

    def test_migration_adds_cascade_and_preserves_rows(self, tmp_path):
        """老 schema (无 CASCADE) -> init_schema 迁移后 CASCADE + 行保留."""
        path = str(tmp_path / "evt_old.db")
        db = Database(DatabaseConfig(db_path=path))
        db.init_schema()
        # 降级为老 DDL (模拟升级前 dev DB)
        db.conn.executescript("""
        DROP TABLE event_log;
        CREATE TABLE event_log (
            event_id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            source TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        );
        """)
        db.upsert_student("evt_stu", subject="python")
        db.conn.execute(
            "INSERT INTO event_log VALUES ('e1', 'evt_stu', '2026-09-06T00:00:00', "
            "'dual_agent', 'calibration', '{}')"
        )
        db.conn.commit()
        db.close()

        db2 = Database(DatabaseConfig(db_path=path))
        try:
            db2.init_schema()  # 触发迁移
            ddl = db2.conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='event_log'"
            ).fetchone()[0]
            assert "ON DELETE CASCADE" in ddl
            rows = db2.conn.execute("SELECT * FROM event_log").fetchall()
            assert len(rows) == 1  # 已有行保留
        finally:
            db2.close()
            if os.path.exists(path):
                os.unlink(path)

    def test_cascade_deletes_events_with_student(self, tmp_path):
        """删除 students 行 -> event_log 行随 CASCADE 清理."""
        path = str(tmp_path / "evt_cas.db")
        db = Database(DatabaseConfig(db_path=path))
        try:
            db.init_schema()
            db.upsert_student("evt_cas_stu", subject="python")
            db.conn.execute(
                "INSERT INTO event_log VALUES ('e2', 'evt_cas_stu', "
                "'2026-09-06T00:00:00', 'test', 'observation', '{}')"
            )
            db.conn.commit()
            db.conn.execute("PRAGMA foreign_keys=ON")
            db.conn.execute("DELETE FROM students WHERE student_id='evt_cas_stu'")
            db.conn.commit()
            remaining = db.conn.execute(
                "SELECT COUNT(*) FROM event_log WHERE student_id='evt_cas_stu'"
            ).fetchone()[0]
            assert remaining == 0
        finally:
            db.close()
