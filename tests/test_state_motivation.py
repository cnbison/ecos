"""v0.96: /api/state 暴露 Motivation Profile (v0.87 Kernel 侧 → 前端首次呈现).

覆盖:
  - /api/state 响应含 motivation (frustration/engagement/confidence/observation_count)
  - 默认学生: 中性值 (frustration=0.0 / engagement=0.5 / confidence=0.5)
  - motivation 字段不崩 (防御性)

对应 discussions/2026-08-17-v096-学生端信息架构三问对齐.md (动机层呈现, v0.96-b).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "web" / "ecos_test_motivation.db"


@pytest.fixture(scope="module", autouse=True)
def _seed_temp_db():
    os.environ["ECOS_DB_PATH"] = str(TEST_DB)
    if TEST_DB.exists():
        TEST_DB.unlink()
    yield
    os.environ.pop("ECOS_DB_PATH", None)
    if TEST_DB.exists():
        TEST_DB.unlink()


@pytest.fixture
def client():
    from web.api.app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestStateMotivation:
    def test_state_has_motivation(self, client):
        """/api/state 含 motivation 4 字段."""
        resp = client.get("/api/state/mot-stu-1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "motivation" in data
        for field in ("frustration", "engagement", "confidence", "observation_count"):
            assert field in data["motivation"], f"motivation 缺 {field}"

    def test_default_motivation_neutral(self, client):
        """新学生 → 中性值."""
        data = client.get("/api/state/mot-stu-2").get_json()
        mot = data["motivation"]
        assert mot["frustration"] == pytest.approx(0.0)
        assert mot["engagement"] == pytest.approx(0.5)
        assert mot["confidence"] == pytest.approx(0.5)
        assert mot["observation_count"] == 0
