"""v0.98.0 (a-b): 家长端 API 测试 (/api/parent/* 只读).

覆盖:
  - /api/parent/students roster (只读, 严禁 _get_or_create_student — 防幽灵学生)
  - /api/parent/students/<id>/overview 单聚合 (engagement + five_d + interventions)
  - engagement 双路径: plugin 缓存命中 / 缓存 miss 按需诊断 (ingest 喂入)
  - 防御性: 学生不存在 → 404 且不产生 DB 行; 非 POMDP policy → engagement null
  - db.load_intervention_history 接线 (wiring-audit B 类 dead code → 接活)
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
from ecos.plugins.first_party.parent_engagement import ParentEngagementPlugin

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "web" / "ecos_test_parent.db"


def _make_diagnostic(
    coverage_value: int = 10,
    most_likely_state: int = 0,
) -> POMDPDiagnostic:
    """构造最小 POMDPDiagnostic (跟 test_teacher_api._make_diagnostic 同模式)."""
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
    """temp DB 造 2 个学生 (有数据 + 冷启动), 跟 test_teacher_api 同模式."""
    os.environ["ECOS_DB_PATH"] = str(TEST_DB)
    if TEST_DB.exists():
        TEST_DB.unlink()

    from ecos.persistence.db import Database
    db = Database(str(TEST_DB))
    db.init_schema()

    # lbc-p1: 有答题记录 + 5D state
    db.upsert_student("lbc-p1", subject="python")
    history = [
        {"problem_id": "PB-Q01", "correct": True, "score": 1.0, "bloom_level": "L1",
         "user_answer": "x = 5", "correct_answer": "x = 5",
         "timestamp": "2026-09-06T10:00:00", "ai_reasoning": "正确"},
        {"problem_id": "PB-Q02", "correct": False, "score": 0.3, "bloom_level": "L3",
         "user_answer": "x = x + 1", "correct_answer": "x += 1",
         "timestamp": "2026-09-06T10:05:00", "ai_reasoning": "缺少增量赋值"},
    ]
    db.conn.execute(
        "UPDATE students SET current_state_5d=?, current_bloom_profile=?, theta_cov=?, "
        "confidence=?, response_history=?, last_active_at=? WHERE student_id=?",
        (
            json.dumps([1.2, 0.8, 0.3, -0.1, 0.5]),
            json.dumps({
                "remember": 0.9, "understand": 0.7, "apply": 0.6,
                "analyze": 0.4, "evaluate": 0.3, "create": 0.2,
                "dominant_layer": "APPLY", "confidence": 0.6,
            }),
            json.dumps([[0.25] * 5] * 5),
            0.7,
            json.dumps(history),
            "2026-09-06T12:00:00",
            "lbc-p1",
        ),
    )
    # lbc-p2: 无答题记录 (冷启动)
    db.upsert_student("lbc-p2", subject="python")

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


@pytest.fixture
def registered_plugin():
    """把 ParentEngagementPlugin 注册进 default registry (测试后清理)."""
    from ecos.plugins.registry import get_default_registry
    plugin = ParentEngagementPlugin()
    plugin.enable()
    get_default_registry().register(plugin)
    yield plugin
    get_default_registry()._plugins.pop("parent_engagement", None)


# ── roster (3 tests) ─────────────────────────────────────────────────────────


class TestParentRoster:
    def test_roster_returns_students(self, client):
        """roster 返回种子学生 + 关键字段."""
        resp = client.get("/api/parent/students")
        assert resp.status_code == 200
        data = resp.get_json()
        by_id = {s["student_id"]: s for s in data["students"]}
        assert "lbc-p1" in by_id and "lbc-p2" in by_id
        p1 = by_id["lbc-p1"]
        assert p1["answered_count"] == 2
        assert p1["correct_rate"] == 0.5
        assert p1["subject"] == "python"

    def test_roster_is_read_only_no_ghost_students(self, client):
        """roster 只读: 请求前后 students 表行数不变 (幽灵学生防御)."""
        from ecos.persistence.db import Database
        db = Database(str(TEST_DB))
        before = db.conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        resp = client.get("/api/parent/students")
        after = db.conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        db.close()
        assert resp.status_code == 200
        assert before == after

    def test_roster_empty_db_returns_empty_list(self, client, monkeypatch):
        """空 DB → 空列表 (不报错不建行)."""
        import web.api.parent as parent_api
        from ecos.persistence.db import Database

        class _FakeDB:
            def load_student_ids(self, limit=100):
                return []

        monkeypatch.setattr(
            "web.api.teacher._get_db", lambda: _FakeDB()
        )
        # _load_student_row 不会被调 (sids 为空), 但保险起见同样 patch
        monkeypatch.setattr(
            "web.api.teacher._load_student_row", lambda sid: None
        )
        resp = client.get("/api/parent/students")
        assert resp.status_code == 200
        assert resp.get_json() == {"students": []}


# ── overview (4 tests) ───────────────────────────────────────────────────────


class TestParentOverview:
    def test_overview_404_missing_student_no_ghost(self, client):
        """学生不存在 → 404 且不产生 DB 行 (严禁 _get_or_create_student)."""
        from ecos.persistence.db import Database
        db = Database(str(TEST_DB))
        before = db.conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        resp = client.get("/api/parent/students/stu_ghost/overview")
        after = db.conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        db.close()
        assert resp.status_code == 404
        assert before == after

    def test_overview_five_d_and_interventions(self, client):
        """overview 返回 five_d (mastery/bloom/confidence) + interventions."""
        resp = client.get("/api/parent/students/lbc-p1/overview")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["student_id"] == "lbc-p1"
        mastery = data["five_d"]["mastery"]
        assert set(mastery.keys()) == {"K", "P", "S", "C", "X"}
        assert mastery["K"] == 1.2
        assert data["five_d"]["bloom"]["levels"]["L1"] == 0.9
        assert data["five_d"]["bloom"]["dominant"] == "APPLY"
        assert data["five_d"]["overall_confidence"] == 0.7
        assert data["interventions"] == []  # load_intervention_history 接线 (空历史)

    def test_overview_engagement_from_plugin_cache(self, client, registered_plugin):
        """engagement 走 plugin 缓存 (report_for 命中 → 不触发按需诊断)."""
        registered_plugin.ingest_diagnostic(
            "lbc-p1", _make_diagnostic(most_likely_state=1)
        )
        resp = client.get("/api/parent/students/lbc-p1/overview")
        assert resp.status_code == 200
        engagement = resp.get_json()["engagement"]
        assert engagement is not None
        assert engagement["current_state"] == "Frustrated"
        assert isinstance(engagement["advice"], list) and engagement["advice"]

    def test_overview_engagement_null_when_no_plugin_and_non_pomdp(self, client):
        """无 plugin + 默认非 POMDP policy → engagement null (不报错)."""
        resp = client.get("/api/parent/students/lbc-p1/overview")
        assert resp.status_code == 200
        assert resp.get_json()["engagement"] is None


# ── engagement 按需诊断路径 (2 tests) ────────────────────────────────────────


class TestEngagementOnDemand:
    def test_engagement_on_demand_full_path(self, client, registered_plugin, monkeypatch):
        """缓存 miss → diagnose_pomdp + diagnose_pomdp_evolution → ingest 双喂入."""
        from ecos.lca.l4_optimization.linucb import BanditConfig
        from ecos.lca.l4_optimization.policy_learner import LCAPolicyLearner
        from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig
        from ecos.lca.policy_learner import PolicyLearnerConfig
        import web.api.lca as lca_api

        cfg = LCAEngineConfig(
            policy_learner_config=PolicyLearnerConfig(
                bandit_config=BanditConfig(n_arms=4),
                policy_type="pomdp", pomdp_seed=42,
                pomdp_use_pbvi=True, pomdp_use_learned_t_r=True,
            )
        )
        lca = LCAEngine(config=cfg)
        lca.policy_learner._learners["lbc-p1"] = LCAPolicyLearner(
            BanditConfig(n_arms=4), policy_type="pomdp", pomdp_seed=42,
            pomdp_use_pbvi=True, pomdp_use_learned_t_r=True,
        )
        lca.policy_learner._learners["lbc-p1"].pomdp._take_evolution_snapshot()

        monkeypatch.setattr(
            lca_api, "_get_or_create_lca_state", lambda sid: None
        )
        monkeypatch.setattr(lca_api, "get_lca_engine", lambda: lca)

        resp = client.get("/api/parent/students/lbc-p1/overview")
        assert resp.status_code == 200
        engagement = resp.get_json()["engagement"]
        assert engagement is not None
        assert engagement["current_state"] == "Engaged"
        # evolution 经第 9 Runtime API 喂入 → recent_states 非空
        assert engagement["evolution_count"] >= 1

    def test_engagement_no_plugin_direct_diagnose_fallback(self, monkeypatch):
        """无 plugin 时 _get_engagement_report 返 None (不依赖 plugin, 不报错)."""
        import web.api.parent as parent_api
        monkeypatch.setattr(parent_api, "_get_parent_engagement_plugin", lambda: None)
        monkeypatch.setattr(
            "web.api.lca._get_or_create_lca_state", lambda sid: (_ for _ in ()).throw(
                RuntimeError("no lca"))
        )
        # lca state 拿不到 → 异常兜底返 None (防御性自检 [1])
        result = parent_api._get_engagement_report("lbc-p1")
        assert result is None


# ── 前端 route 服务 (1 test) ─────────────────────────────────────────────────


class TestParentFrontendRoutes:
    def test_parent_route_serves_placeholder_pre_build(self, client):
        """/parent/ 可访问 (dist build 前 fallback web/parent/index.html 占位页)."""
        resp = client.get("/parent/")
        assert resp.status_code == 200
        assert "ECOS 家长端".encode("utf-8") in resp.data


# ── 入口 ─────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
