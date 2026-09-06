"""v0.97.3 (c) 教师端 per-misconception 证据 API 测试.

对应 web/api/teacher.py:api_teacher_student_misconceptions 端点
(DB 直读 misconception_evidence 表, 读时派生 evidence view,
无状态 — 同 v0.97.1 mastery view / v0.97.2 calibration view 模式).
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from ecos.persistence.db import Database, DatabaseConfig


TEST_DB = Path(tempfile.gettempdir()) / "ecos_test_misconceptions_v0973.db"


@pytest.fixture(scope="module", autouse=True)
def _seed_temp_db():
    """用 temp DB 造 1 个学生的教师端数据 (DB 直读, 不 init BeliefEngine)."""
    os.environ["ECOS_DB_PATH"] = str(TEST_DB)
    if TEST_DB.exists():
        TEST_DB.unlink()
    db = Database(str(TEST_DB))
    db.init_schema()
    db.upsert_student("stu_c1", grade_level=5, subject="math")
    yield
    os.environ.pop("ECOS_DB_PATH", None)
    if TEST_DB.exists():
        TEST_DB.unlink()


@pytest.fixture(autouse=True)
def _clean_misconception_evidence():
    """每测试前清空 misconception_evidence (测试间隔离)."""
    db = Database(str(TEST_DB))
    db.delete_misconception_evidence("stu_c1")
    yield


@pytest.fixture
def client():
    from web.api.app import app
    with app.test_client() as c:
        yield c


def test_endpoint_returns_empty_for_student_with_no_misconceptions(client):
    resp = client.get("/api/teacher/students/stu_c1/misconceptions")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["student_id"] == "stu_c1"
    assert data["has_data"] is False
    assert data["items"] == []


def test_endpoint_returns_404_for_missing_student(client):
    resp = client.get("/api/teacher/students/no_such/misconceptions")
    assert resp.status_code == 404


def test_endpoint_returns_misconception_items_with_metadata(client):
    """有 evidence 时返回 per-misc 元数据 (name/description/correction_strategy)
    + Laplace 置信度 + quarantine 标记."""
    db = Database(str(TEST_DB))
    db.save_misconception_evidence("stu_c1", [
        {"misc_id": "M1", "success_count": 3, "failure_count": 0,
         "last_updated": "2026-09-05T10:00:00"},
    ])

    resp = client.get("/api/teacher/students/stu_c1/misconceptions")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["has_data"] is True
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["misc_id"] == "M1"
    assert item["success_count"] == 3
    assert item["failure_count"] == 0
    assert item["total"] == 3
    assert item["laplace_confidence"] == 0.8
    assert item["quarantined"] is False
    # 元数据来自 PythonBasicsMisconceptionLibrary
    assert "name" in item and item["name"]
    assert "description" in item and item["description"]
    assert "correction_strategy" in item and item["correction_strategy"]


def test_endpoint_marks_quarantined_misconceptions(client):
    """3+ failure, conf<0.3 -> quarantined=True (CogMirror 5.x 同款)."""
    db = Database(str(TEST_DB))
    db.save_misconception_evidence("stu_c1", [
        {"misc_id": "M1", "success_count": 0, "failure_count": 5,
         "last_updated": "2026-09-05T10:00:00"},
    ])

    resp = client.get("/api/teacher/students/stu_c1/misconceptions")
    assert resp.status_code == 200
    data = resp.get_json()
    item = data["items"][0]
    assert item["quarantined"] is True
    assert item["laplace_confidence"] < 0.3


def test_endpoint_handles_unknown_misc_id_gracefully(client):
    """DB 里有但库找不到的 misc_id (库升级/老数据) -> name fallback."""
    db = Database(str(TEST_DB))
    db.save_misconception_evidence("stu_c1", [
        {"misc_id": "M99_legacy", "success_count": 1, "failure_count": 0,
         "last_updated": "2026-09-05T10:00:00"},
    ])

    resp = client.get("/api/teacher/students/stu_c1/misconceptions")
    data = resp.get_json()
    item = data["items"][0]
    assert item["misc_id"] == "M99_legacy"
    # 找不到 -> name 退化到 misc_id, description 空
    assert item["name"] == "M99_legacy"
    assert item["description"] == ""


def test_endpoint_sorts_items_by_misc_id(client):
    """items 按 misc_id 升序 (与 tracker.all_evidence 排序约定一致)."""
    db = Database(str(TEST_DB))
    db.save_misconception_evidence("stu_c1", [
        {"misc_id": "M3", "success_count": 1, "failure_count": 0, "last_updated": ""},
        {"misc_id": "M1", "success_count": 1, "failure_count": 0, "last_updated": ""},
        {"misc_id": "M2", "success_count": 1, "failure_count": 0, "last_updated": ""},
    ])

    resp = client.get("/api/teacher/students/stu_c1/misconceptions")
    data = resp.get_json()
    assert [i["misc_id"] for i in data["items"]] == ["M1", "M2", "M3"]


def test_endpoint_returns_500_on_internal_failure(client, monkeypatch):
    """misconceptions 内部计算失败 -> 500 (load_student_row 通过, 进入 misconception try)."""
    from ecos.cta import misconception_reconcile

    def _boom(*_a, **_kw):
        raise RuntimeError("tracker 加载炸了")
    # monkeypatch load_tracker_for_student 让 misconception 段炸
    monkeypatch.setattr(
        misconception_reconcile, "load_tracker_for_student", _boom,
    )
    resp = client.get("/api/teacher/students/stu_c1/misconceptions")
    assert resp.status_code == 500
    body = resp.get_json()
    assert "error" in body
