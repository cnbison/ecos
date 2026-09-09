"""v0.99.0 试点信号采集批次回归 (F-05 / F-09 / F-10 / F-11, dogfood 2026-09-08).

四个「schema 在、链路断」的 built≠wired 一次性收口:
  - F-05 judge 审计落库 (model/attempts/latency/raw_output → judge_audit_log)
  - F-09 答题时延采集 (前端 payload → Observation.response_time_sec → evidence)
  - F-10 误解检测接通 (explanation_text 缺省 fallback user_answer)
  - F-11 行为事件落库 (hint/idle/goal_change/reflection → event_log 表)
"""

from __future__ import annotations

import json
import sqlite3
from unittest.mock import patch

import pytest


@pytest.fixture
def flask_client():
    from web.api.app import app
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    """测试统一 get_llm → None (无 API key 语境, 与 test_web_evidence_injection 同惯例).

    防止 /api/answer 触发真实 LLM 调用 (misconception/perception critic).
    judge 测试内部用 with patch("web.api.app.get_llm", ...) 显式覆盖.
    """
    import web.api.app as app_mod
    monkeypatch.setattr(app_mod, "get_llm", lambda: None)


@pytest.fixture
def tmp_db():
    """conftest isolated_ecos_db 已设 ECOS_DB_PATH; 这里确保 schema + 学生行."""
    import os
    from ecos.persistence.db import Database
    db = Database(os.environ["ECOS_DB_PATH"])
    db.init_schema()
    db.upsert_student("stu-sig")
    return db


def _db_conn():
    import os
    return sqlite3.connect(os.environ["ECOS_DB_PATH"])


# ─── F-11: 行为事件落库 ──────────────────────────────────────────────────


class TestF11BehaviorEventPersistence:
    def test_hint_event_persisted_to_event_log(self, flask_client, tmp_db):
        """POST /api/event/hint → event_log 表出现 hint_requested 行."""
        resp = flask_client.post("/api/event/hint", json={
            "student_id": "stu-sig", "problem_id": "PB-Q01", "hint_level": 1,
        })
        assert resp.status_code == 200
        with _db_conn() as conn:
            rows = conn.execute(
                "SELECT event_type FROM event_log WHERE student_id='stu-sig' "
                "AND event_type='hint_requested'"
            ).fetchall()
        assert len(rows) >= 1

    def test_reflection_event_persisted_to_event_log(self, flask_client, tmp_db):
        """POST /api/event/reflection → event_log 表出现 reflection 行 (Bisen 笔记丢失案回归)."""
        resp = flask_client.post("/api/event/reflection", json={
            "student_id": "stu-sig", "problem_id": "PB-Q02",
            "reflection_text": "我把赋值当复制了，b=a 后两者指向同一列表",
        })
        assert resp.status_code == 200
        with _db_conn() as conn:
            rows = conn.execute(
                "SELECT event_type FROM event_log WHERE student_id='stu-sig' "
                "AND event_type LIKE '%reflection%'"
            ).fetchall()
        assert len(rows) >= 1

    def test_goal_change_event_persisted(self, flask_client, tmp_db):
        """POST /api/event/goal_change → event_log 表出现 goal_changed 行."""
        resp = flask_client.post("/api/event/goal_change", json={
            "student_id": "stu-sig", "old_goal_id": "a:L1", "new_goal_id": "b:L2",
        })
        assert resp.status_code == 200
        with _db_conn() as conn:
            rows = conn.execute(
                "SELECT event_type FROM event_log WHERE student_id='stu-sig' "
                "AND event_type='goal_changed'"
            ).fetchall()
        assert len(rows) >= 1


# ─── F-10: 误解检测输入接通 ──────────────────────────────────────────────


class TestF10ExplanationFallback:
    def test_explanation_text_defaults_to_user_answer(self, flask_client, tmp_db):
        """前端不传 explanation_text → 后端 fallback user_answer (误解检测器输入)."""
        captured = {}

        def fake_submit_answer(**kwargs):
            captured.update(kwargs)
            return {"student_id": kwargs["student_id"], "persisted": True}

        with patch("web.api.app.submit_answer", side_effect=fake_submit_answer):
            resp = flask_client.post("/api/answer", json={
                "student_id": "stu-sig",
                "problem_id": "PB-Q04",
                "skill_id": "python.variables",
                "correct": False,
                "score": 0.0,
                "bloom_layer": "L4",
                "user_answer": "[1, 2]，因为 b=a 是复制值",  # 解释在 user_answer 里
                "self_confidence": 0.5,
            })
        assert resp.status_code == 200
        assert captured["explanation_text"] == "[1, 2]，因为 b=a 是复制值"
        assert captured["user_answer"] == "[1, 2]，因为 b=a 是复制值"

    def test_explicit_explanation_text_not_overridden(self, flask_client, tmp_db):
        """显式传 explanation_text 时优先 (不被 user_answer 覆盖)."""
        captured = {}

        def fake_submit_answer(**kwargs):
            captured.update(kwargs)
            return {"student_id": kwargs["student_id"], "persisted": True}

        with patch("web.api.app.submit_answer", side_effect=fake_submit_answer):
            resp = flask_client.post("/api/answer", json={
                "student_id": "stu-sig",
                "problem_id": "PB-Q04",
                "skill_id": "python.variables",
                "correct": False,
                "bloom_layer": "L4",
                "user_answer": "[1, 2]",
                "explanation_text": "显式解释",
            })
        assert resp.status_code == 200
        assert captured["explanation_text"] == "显式解释"


# ─── F-09: 答题时延采集 ──────────────────────────────────────────────────


class TestF09ResponseTime:
    def test_response_time_lands_in_evidence(self, flask_client, tmp_db):
        """/api/answer 带 response_time → evidence_log.raw_response_time 落列.

        注: 首题走冷启动路径不写 evidence (既有行为, 与 F-09 无关),
        所以先答一题预热再验证第二题.
        """
        # 第一题: 预热 (冷启动, 不写 evidence)
        resp1 = flask_client.post("/api/answer", json={
            "student_id": "stu-sig",
            "problem_id": "PB-Q01",
            "skill_id": "python.variables",
            "correct": True,
            "score": 1.0,
            "bloom_layer": "L1",
            "user_answer": "5",
        })
        assert resp1.status_code == 200
        # 第二题: 带 response_time
        resp2 = flask_client.post("/api/answer", json={
            "student_id": "stu-sig",
            "problem_id": "PB-Q02",
            "skill_id": "python.variables",
            "correct": True,
            "score": 1.0,
            "bloom_layer": "L1",
            "user_answer": "0\n1\n2",
            "response_time": 42,
        })
        assert resp2.status_code == 200
        with _db_conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT raw_response_time FROM evidence_log "
                "WHERE student_id='stu-sig' AND problem_id='PB-Q02'"
            ).fetchall()
        assert rows, "第二题 evidence 行应存在"
        assert any(r[0] == 42.0 for r in rows), f"raw_response_time 应为 42, got {rows}"

    def test_invalid_response_time_defaults_to_zero(self, flask_client, tmp_db):
        """response_time 非数字 → 0.0 + 不阻断 (诚实降级留 warning)."""
        resp = flask_client.post("/api/answer", json={
            "student_id": "stu-sig",
            "problem_id": "PB-Q05",
            "skill_id": "python.loops",
            "correct": True,
            "score": 1.0,
            "bloom_layer": "L1",
            "user_answer": "0\n1\n2",
            "response_time": "not-a-number",
        })
        assert resp.status_code == 200


# ─── F-05: judge 审计落库 ────────────────────────────────────────────────


class _FakeProvider:
    value = "minimax"


class _FakeConfig:
    provider = _FakeProvider()
    model = "fake-model"


class FakeJudgeLLM:
    config = _FakeConfig()  # v0.99.0: F-05 审计读 provider/model

    def __init__(self, plan):
        self.plan = plan if isinstance(plan, list) else [plan]
        self.calls = 0

    def chat(self, messages, **kwargs):
        self.calls += 1
        item = self.plan[min(self.calls, len(self.plan)) - 1]
        if isinstance(item, Exception):
            raise item
        return item


class TestF05JudgeAudit:
    def test_success_judge_writes_audit_row(self, flask_client, tmp_db):
        """判分成功 → judge_audit_log 出现 judged=1 行, model/attempts 记录."""
        from web.api.app import get_llm
        good = json.dumps({"correct": True, "reasoning": "对", "score": 1.0})
        llm = FakeJudgeLLM(good)
        with patch("web.api.app.get_llm", return_value=llm):
            resp = flask_client.post("/api/judge", json={
                "student_id": "stu-sig", "problem_id": "PB-Q01",
                "student_answer": "5",
            })
        assert resp.status_code == 200
        with _db_conn() as conn:
            rows = conn.execute(
                "SELECT student_id, problem_id, attempts, judged, error_code "
                "FROM judge_audit_log WHERE student_id='stu-sig'"
            ).fetchall()
        assert len(rows) == 1
        assert rows[0][2] == 1          # attempts
        assert rows[0][3] == 1          # judged
        assert rows[0][4] is None       # error_code

    def test_failed_judge_writes_audit_row_with_raw_output(self, flask_client, tmp_db):
        """3 次 retry 全失败 → judged=0 行 + raw_output 留最后一次原始返回."""
        llm = FakeJudgeLLM(["bad1", "bad2", "bad3"])
        with patch("web.api.app.get_llm", return_value=llm):
            resp = flask_client.post("/api/judge", json={
                "student_id": "stu-sig", "problem_id": "PB-Q02",
                "student_answer": "x",
            })
        assert resp.status_code == 422
        with _db_conn() as conn:
            rows = conn.execute(
                "SELECT judged, error_code, raw_output FROM judge_audit_log "
                "WHERE student_id='stu-sig' AND problem_id='PB-Q02'"
            ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 0                          # judged
        assert rows[0][1] == "LLM_JUDGE_FAILED"         # error_code
        assert "bad3" in (rows[0][2] or "")             # 最后一次原始返回留痕
