"""v0.95.1: 教师端 API 测试 (班级列表 / 学生详情 / 证据链 / POMDP 诊断 / 干预历史).

覆盖:
  - TeacherProgressPlugin UI 化升级 (report_for / get_reports / ingest_diagnostic)
  - /api/teacher/students 班级列表 (roster)
  - /api/teacher/students/<id> 学生详情
  - /api/teacher/students/<id>/evidence 证据链 (按 5D 维度聚合 + 下钻)
  - /api/teacher/students/<id>/diagnostic POMDP 诊断 (非 POMDP learner → diagnostic null)
  - /api/teacher/students/<id>/interventions 干预历史
  - 防御性: teacher.py 只读 DB, 不 init BeliefEngine (证据链从 DB 直读)

Per discussions/2026-08-17-v095方向审查 §决策 1 (班级视图优先 + 单生深潜 +
证据链按 5D 维度聚合可下钻, Bisen 拍板 2026-08-17).
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from ecos.lca.l4_optimization.pomdp_diagnostic import (
    POMDPDiagnostic,
    SCHEMA_VERSION as POMDP_DIAG_SCHEMA,
    RewardPosteriorSnapshot,
    TransitionPosteriorSnapshot,
)
from ecos.plugins.first_party.teacher_progress import TeacherProgressPlugin

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "web" / "ecos_test_teacher.db"


def _make_diagnostic(
    coverage_value: int = 10,
    most_likely_state: int = 0,
) -> POMDPDiagnostic:
    """构造最小 POMDPDiagnostic (跟 test_first_party_plugins._make_diagnostic 同模式)."""
    n_states, n_arms = 4, 3
    T_snapshot = TransitionPosteriorSnapshot(
        mean=np.full((n_states, n_states, n_arms), 1.0 / n_states),
        count=np.full((n_states, n_states, n_arms), coverage_value, dtype=int),
        alpha0=1.0,
        schema_version=POMDP_DIAG_SCHEMA,
    )
    alpha_R = np.full((n_states, n_arms), 5.0)
    beta_R = np.full((n_states, n_arms), 5.0)
    R_snapshot = RewardPosteriorSnapshot(
        mean=alpha_R / (alpha_R + beta_R),
        alpha=alpha_R, beta=beta_R, alpha0=1.0,
        variance=np.full((n_states, n_arms), 0.05),
        schema_version=POMDP_DIAG_SCHEMA,
    )
    belief = np.full(n_states, 0.1)
    belief[most_likely_state] = 0.7
    return POMDPDiagnostic(
        T=T_snapshot, R=R_snapshot,
        belief=belief,
        coverage=np.full((n_states, n_arms), coverage_value, dtype=int),
        most_likely_state=most_likely_state,
        last_updated=datetime.now(),
        schema_version=POMDP_DIAG_SCHEMA,
    )


@pytest.fixture(scope="module", autouse=True)
def _seed_temp_db():
    """用 temp DB 造 2 个学生的教师端数据 (DB 直读, 不 init BeliefEngine)."""
    os.environ["ECOS_DB_PATH"] = str(TEST_DB)
    if TEST_DB.exists():
        TEST_DB.unlink()

    from ecos.persistence.db import Database
    db = Database(str(TEST_DB))
    db.init_schema()

    # lbc-t1: 3 道题 (有答题记录 + misconception + TC)
    db.upsert_student("lbc-t1", subject="python")
    history = [
        {"problem_id": "PB-Q01", "correct": True, "score": 1.0, "bloom_level": "L1",
         "user_answer": "x = 5", "correct_answer": "x = 5", "timestamp": "2026-08-17T10:00:00",
         "ai_reasoning": "正确"},
        {"problem_id": "PB-Q02", "correct": True, "score": 1.0, "bloom_level": "L2",
         "user_answer": "for i in range(5):", "correct_answer": "for i in range(5):",
         "timestamp": "2026-08-17T10:05:00", "ai_reasoning": "正确"},
        {"problem_id": "PB-Q03", "correct": False, "score": 0.3, "bloom_level": "L3",
         "user_answer": "x = x + 1", "correct_answer": "x += 1", "timestamp": "2026-08-17T10:10:00",
         "ai_reasoning": "缺少增量赋值"},
    ]
    db.conn.execute(
        "UPDATE students SET current_state_5d=?, current_bloom_profile=?, theta_cov=?, "
        "tc_states=?, confidence=?, response_history=?, misconception_history=?, last_active_at=? "
        "WHERE student_id=?",
        (
            json.dumps([1.2, 0.8, 0.3, -0.1, 0.5]),
            json.dumps({
                "remember": 0.9, "understand": 0.7, "apply": 0.6,
                "analyze": 0.4, "evaluate": 0.3, "create": 0.2,
                "dominant_layer": "APPLY", "confidence": 0.6,
            }),
            json.dumps([[0.25] * 5] * 5),
            json.dumps({
                "planning": {"status": "active", "progress": 0.8, "confidence": 0.7, "irreversible": False},
                "self_monitoring": {"status": "developing", "progress": 0.4, "confidence": 0.5, "irreversible": False},
            }),
            0.7,
            json.dumps(history),
            json.dumps([{"misc_id": "M3", "confidence": 0.8, "timestamp": "2026-08-17T10:10:00"}]),
            "2026-08-17T12:00:00",
            "lbc-t1",
        ),
    )

    # lbc-t2: 无答题记录 (冷启动学生)
    db.upsert_student("lbc-t2", subject="python")

    yield
    os.environ.pop("ECOS_DB_PATH", None)
    if TEST_DB.exists():
        TEST_DB.unlink()


@pytest.fixture
def client():
    """Flask test client (ECOS_DB_PATH 已指向 temp DB)."""
    from web.api.app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ── TeacherProgressPlugin UI 化 (4 tests) ────────────────────────────────────


class TestTeacherProgressPluginUI:
    """v0.95.1: plugin 从 _log.info 升级为 UI 可消费 (report 缓存 + 查询)."""

    def test_report_for_after_ingest(self):
        """ingest_diagnostic 后 report_for 能查到结构化报告."""
        plugin = TeacherProgressPlugin()
        plugin.enable()
        diag = _make_diagnostic(coverage_value=3, most_likely_state=0)
        result = plugin.ingest_diagnostic("stu-1", diag)
        assert result["student_id"] == "stu-1"
        assert result["cold_start"] is True
        assert result["most_likely_state"] == "Engaged"
        assert plugin.report_for("stu-1")["most_likely_state"] == "Engaged"
        assert set(plugin.get_reports().keys()) == {"stu-1"}
        plugin.disable()

    def test_report_has_ui_fields(self):
        """report 含 UI 需要全部字段 (updated_at / belief / advice)."""
        plugin = TeacherProgressPlugin()
        diag = _make_diagnostic(coverage_value=10, most_likely_state=2)
        report = plugin.ingest_diagnostic("stu-2", diag)
        for field in ("student_id", "most_likely_state", "most_likely_state_index",
                      "belief", "min_coverage", "cold_start", "advice", "updated_at"):
            assert field in report, f"report 缺 {field}"
        assert report["most_likely_state"] == "Bored"
        assert report["cold_start"] is False
        assert "已冷启动完成" in report["advice"]

    def test_ingest_diagnostic_shares_report_logic_with_on_event(self):
        """ingest_diagnostic 与 on_event 派生同一 report 结构 (DRY)."""
        from ecos.cta.event_log import LearningEvent
        plugin = TeacherProgressPlugin()
        diag = _make_diagnostic(coverage_value=7, most_likely_state=0)
        d = diag.to_dict()
        d["evolution"] = []
        event = LearningEvent.from_pomdp_diagnostic_updated("stu-3", d)
        r_event = plugin.on_event(event)
        r_ingest = plugin.ingest_diagnostic("stu-3", diag)
        assert r_event is not None
        for key in ("most_likely_state", "min_coverage", "cold_start", "advice"):
            assert r_event[key] == r_ingest[key]

    def test_enable_disable_clears_reports(self):
        """enable/disable 清空报告缓存 (生命周期对称)."""
        plugin = TeacherProgressPlugin()
        plugin.ingest_diagnostic("stu-4", _make_diagnostic())
        assert plugin.report_for("stu-4") is not None
        plugin.disable()
        assert plugin.report_for("stu-4") is None
        assert plugin.get_reports() == {}


# ── 班级列表 roster (2 tests) ────────────────────────────────────────────────


class TestRoster:
    def test_roster_returns_students(self, client):
        """班级列表返回学生 + 关键字段."""
        resp = client.get("/api/teacher/students")
        assert resp.status_code == 200
        data = resp.get_json()
        sids = [s["student_id"] for s in data["students"]]
        assert "lbc-t1" in sids
        assert "lbc-t2" in sids

        t1 = next(s for s in data["students"] if s["student_id"] == "lbc-t1")
        assert t1["answered_count"] == 3
        assert t1["correct_rate"] == pytest.approx(2 / 3, abs=5e-5)
        assert t1["bloom_dominant"] == "APPLY"
        assert t1["overall_confidence"] == pytest.approx(0.7)
        # 字段完整 (前端渲染契约)
        for field in ("last_active_at", "subject", "grade_level", "cold_start",
                      "most_likely_state", "risk", "intervention_count"):
            assert field in t1, f"roster 缺 {field}"

    def test_roster_cold_start_student(self, client):
        """无答题记录学生 (lbc-t2): answered_count=0, 无 risk 判定."""
        resp = client.get("/api/teacher/students")
        t2 = next(s for s in resp.get_json()["students"] if s["student_id"] == "lbc-t2")
        assert t2["answered_count"] == 0
        assert t2["intervention_count"] == 0


# ── 学生详情 (2 tests) ───────────────────────────────────────────────────────


class TestStudentDetail:
    def test_detail_returns_state_summary(self, client):
        """学生详情返回 state 摘要 + 报告."""
        resp = client.get("/api/teacher/students/lbc-t1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["student_id"] == "lbc-t1"
        assert data["answered_count"] == 3
        assert data["theta_5d"]["K"] == pytest.approx(1.2)
        assert data["bloom_profile"]["dominant"] == "APPLY"
        assert data["overall_confidence"] == pytest.approx(0.7)

    def test_detail_404_for_unknown(self, client):
        """未知学生 → 404."""
        resp = client.get("/api/teacher/students/no-such-student")
        assert resp.status_code == 404


# ── 证据链 (2 tests) ─────────────────────────────────────────────────────────


class TestEvidenceChain:
    def test_evidence_has_5_dimensions(self, client):
        """证据链按 5D 维度聚合 (K/P/S/C/X)."""
        resp = client.get("/api/teacher/students/lbc-t1/evidence")
        assert resp.status_code == 200
        data = resp.get_json()
        assert set(data["dimensions"].keys()) == {"K", "P", "S", "C", "X"}
        # 每个维度有标签 + 信念字段 (前端渲染契约)
        for dim in ("K", "P", "S", "C", "X"):
            d = data["dimensions"][dim]
            for field in ("label", "full", "desc", "theta", "se", "confidence",
                          "mastered", "response_count", "correct_rate", "responses"):
                assert field in d, f"dim {dim} 缺 {field}"

    def test_evidence_responses_and_cross_dim(self, client):
        """证据链含答题记录 + 跨维度 misconception/TC."""
        resp = client.get("/api/teacher/students/lbc-t1/evidence")
        data = resp.get_json()
        assert data["summary"]["answered_count"] == 3
        assert isinstance(data["misconceptions"], list)
        assert len(data["misconceptions"]) == 1
        assert isinstance(data["tc_states"], list)
        assert len(data["tc_states"]) == 2


# ── POMDP 诊断 (1 test) ──────────────────────────────────────────────────────


class TestDiagnostic:
    def test_diagnostic_graceful_when_no_pomdp(self, client):
        """非 POMDP learner → diagnostic=null, report 不崩 (防御性)."""
        resp = client.get("/api/teacher/students/lbc-t1/diagnostic")
        assert resp.status_code == 200
        data = resp.get_json()
        # lbc-t1 在测试 DB 里无 LCA state, 非 POMDP policy → diagnostic None
        assert data["diagnostic"] is None
        assert data["pomdp_state_names"] == ["Engaged", "Frustrated", "Bored", "Confused"]


# ── 干预历史 (1 test) ────────────────────────────────────────────────────────


class TestInterventions:
    def test_interventions_returns_list(self, client):
        """干预历史返回 list (空 DB 下为空列表)."""
        resp = client.get("/api/teacher/students/lbc-t1/interventions")
        assert resp.status_code == 200
        assert resp.get_json()["interventions"] == []


# ── 防御性 (2 tests) ─────────────────────────────────────────────────────────


class TestTeacherApiDefensive:
    def test_no_silent_pass(self):
        """teacher.py 无 silent pass."""
        import subprocess
        result = subprocess.run(
            ["grep", "-nE", r"^\s*except.*:[[:space:]]*(pass|continue)\s*$",
             "web/api/teacher.py"],
            capture_output=True, text=True,
        )
        assert result.stdout.strip() == "", f"silent pass: {result.stdout}"

    def test_blueprint_registered(self, client):
        """teacher_bp 注册到 app."""
        from web.api.app import app
        assert "teacher.api_teacher_students" in app.view_functions
        assert "teacher.api_teacher_student_evidence" in app.view_functions
