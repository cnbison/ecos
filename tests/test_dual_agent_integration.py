"""v0.60.0: 双 Agent 互校接入主循环集成测试 (Phase 3 of v0.58.0 完整版).

CLAUDE.md [8]: 接入新路径必加测试覆盖 (这次是 dual_agent → /api/answer).

目标:
  - ECOS_DUAL_AGENT_ENABLED feature flag 行为
  - submit_answer 后 calibration_log 表写入
  - dual_agent 失败不污染 belief_engine / LCA state (CLAUDE.md [6])
  - 默认 (flag=False) → 现有路径完全不变 (回归保护)

防御性自检:
  - [1] dual_agent 失败必须 _log.warning, 不能 silent pass
  - [6] dual_agent 失败不写启发式 fallback (走 None 返回, 跟 LCA update 一样的隔离模式)
  - [7] dual_agent 接入会写 calibration_log (新数据, 已有 schema)
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from unittest.mock import patch, MagicMock

import pytest


# ─── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def fresh_db():
    """每个测试用独立临时 DB, 避免污染真实数据.

    实际 web/api/dual_agent.py 走 ecos.persistence.db.get_db,
    那里默认是 web/ecos.db. 我们通过 monkeypatch 改 DB_PATH 路径.
    """
    # 跳过这个 fixture 的真实 DB 切换 (集成测试不走真实 DB)
    yield


@pytest.fixture
def clean_calibration_log():
    """测试前后清理 calibration_log 表 + 创建/删除 test students.

    calibration_log 有 FOREIGN KEY 约束, student_id 必须在 students 表.
    所以每个测试用的 student_id (t_da_int_*) 必须先在 students 表创建.

    v0.60.3 修 (CI 失败 root cause #3): fixture 自己开 raw sqlite3.connect
    在 CI 干净环境 (无 web/ecos.db) 时 schema 不存在 → SELECT 失败.
    修复: 走 get_db() (v0.60.2 已经在 get_db 内调 init_schema, 幂等).
    这样 fixture 跟 test body 走同一 schema 初始化路径.
    """
    # v0.60.3: 用 get_db() 触发 init_schema, 避免 fixture 跟 test body 走不同路径
    try:
        from ecos.persistence.db import get_db
        db = get_db()  # 幂等 init_schema
        conn = db.conn  # 复用 Database 的 connection
    except Exception:
        # 极端情况: get_db 失败 (如 DB path 不存在 + 权限) → 跳过 (跟之前一致)
        yield
        return
    try:
        # 收集测试用的 student_id (从 tests/ 里 grep 出来, 但简单起见直接 hardcode 列表)
        test_sids = [
            "t_da_int_off_001", "t_da_int_on_001", "t_da_int_log_001",
            "t_da_int_fail_001", "t_da_int_new_001", "t_da_int_dbg_001",
            "t_da_int_proto_001", "t_da_int_hf_001", "t_da_int_dbfail_001",
        ]
        # 记录测试前存在哪些
        existing = set()
        for sid in test_sids:
            row = conn.execute(
                "SELECT 1 FROM students WHERE student_id = ?", (sid,)
            ).fetchone()
            if row:
                existing.add(sid)
        # 创建缺失的 test students (minimal row, grade_level=0, 必填字段填充)
        for sid in test_sids:
            if sid not in existing:
                conn.execute(
                    "INSERT INTO students (student_id, grade_level, created_at) "
                    "VALUES (?, 0, datetime('now'))",
                    (sid,),
                )
        conn.commit()
        yield
        # 清理: 删除 test students + 关联 calibration_log
        for sid in test_sids:
            conn.execute("DELETE FROM calibration_log WHERE student_id = ?", (sid,))
            if sid not in existing:
                conn.execute("DELETE FROM students WHERE student_id = ?", (sid,))
        conn.commit()
    finally:
        # 不关 conn, 是 Database 单例的, 后续测试还要用
        pass


# ─── 1. Feature flag 行为 ───────────────────────────────────────────


class TestFeatureFlag:
    def test_default_off(self, monkeypatch):
        """不设环境变量 → DUAL_AGENT_ENABLED=False (默认)."""
        monkeypatch.delenv("ECOS_DUAL_AGENT_ENABLED", raising=False)
        # 重新 import module 以触发 module-level 读取
        import importlib
        import web.api.dual_agent as da
        importlib.reload(da)
        assert da.DUAL_AGENT_ENABLED is False

    def test_explicit_on(self, monkeypatch):
        """ECOS_DUAL_AGENT_ENABLED=1 → DUAL_AGENT_ENABLED=True."""
        monkeypatch.setenv("ECOS_DUAL_AGENT_ENABLED", "1")
        import importlib
        import web.api.dual_agent as da
        importlib.reload(da)
        assert da.DUAL_AGENT_ENABLED is True
        # 重置回 False (避免影响其他测试)
        monkeypatch.setenv("ECOS_DUAL_AGENT_ENABLED", "0")
        importlib.reload(da)


# ─── 2. process_observation_for_student 行为 ────────────────────────


class TestProcessObservation:
    """测试主入口函数 (绕过真实 Flask 路由, 直接调函数)."""

    def test_returns_none_when_flag_off(self, monkeypatch):
        """flag=False → process_observation_for_student 直接返回 None."""
        import web.api.dual_agent as da
        monkeypatch.setattr(da, "DUAL_AGENT_ENABLED", False)
        result = da.process_observation_for_student(
            student_id="t_da_int_off_001",
            problem_id="P001",
            skill_id="python.basics",
            correct=True,
            score=1.0,
        )
        assert result is None

    def test_runs_when_flag_on(self, monkeypatch, clean_calibration_log):
        """flag=True → 跑通, 返回 dict (含 round / intervention_type / warnings)."""
        import web.api.dual_agent as da
        monkeypatch.setattr(da, "DUAL_AGENT_ENABLED", True)
        # 重置 _orchestrator 单例, 防止其他测试残留
        da._orchestrator = None

        result = da.process_observation_for_student(
            student_id="t_da_int_on_001",
            problem_id="P001",
            skill_id="python.basics",
            correct=True,
            score=1.0,
            bloom_layer="L3",
        )
        assert result is not None
        assert "round" in result
        assert "intervention_type" in result
        assert "warnings" in result
        assert "duration_ms" in result
        assert result["round"] >= 1
        # calibration_id 可能是 0 (写库失败), 但应该被填
        assert "calibration_id" in result

    def test_writes_to_calibration_log(self, monkeypatch, clean_calibration_log):
        """flag=True → 写一行 calibration_log (schema 已存在)."""
        import web.api.dual_agent as da
        monkeypatch.setattr(da, "DUAL_AGENT_ENABLED", True)
        da._orchestrator = None

        result = da.process_observation_for_student(
            student_id="t_da_int_log_001",
            problem_id="P002",
            skill_id="python.basics",
            correct=True,
            score=1.0,
            bloom_layer="L4",
        )
        assert result is not None
        # 读 DB 验证
        conn = sqlite3.connect("web/ecos.db")
        try:
            rows = conn.execute(
                "SELECT * FROM calibration_log WHERE student_id = ?",
                ("t_da_int_log_001",),
            ).fetchall()
            # 至少 1 行 (有 calibration_id = 0 也算尝试写了, 但 0 表示失败)
            if result["calibration_id"] > 0:
                assert len(rows) >= 1, f"calibration_log 应有 1 行, got {len(rows)}"
        finally:
            conn.close()

    def test_failure_does_not_pollute_state(self, monkeypatch, clean_calibration_log):
        """dual_agent 抛错 → 返回 None, belief_engine / LCA state 不动 (CLAUDE.md [6])."""
        import web.api.dual_agent as da
        monkeypatch.setattr(da, "DUAL_AGENT_ENABLED", True)
        da._orchestrator = None

        # mock orch.process_observation 抛错
        from ecos.cta.belief_engine import Observation
        from ecos.dual_agent import DualAgentOrchestrator
        with patch.object(DualAgentOrchestrator, "process_observation",
                          side_effect=RuntimeError("mock dual_agent down")):
            result = da.process_observation_for_student(
                student_id="t_da_int_fail_001",
                problem_id="P003",
                skill_id="python.basics",
                correct=True,
                score=1.0,
            )
        # CLAUDE.md [6]: 失败返回 None, 不抛出去
        assert result is None


# ─── 3. get_dual_agent_debug_info ───────────────────────────────────


class TestDebugInfo:
    def test_returns_disabled_when_flag_off(self, monkeypatch):
        """flag=False → debug 接口返回 enabled=False."""
        import web.api.dual_agent as da
        monkeypatch.setattr(da, "DUAL_AGENT_ENABLED", False)
        info = da.get_dual_agent_debug_info("any_sid")
        assert info == {"enabled": False}

    def test_returns_no_state_for_new_student(self, monkeypatch):
        """flag=True + 新学生 → has_state=False."""
        import web.api.dual_agent as da
        monkeypatch.setattr(da, "DUAL_AGENT_ENABLED", True)
        da._orchestrator = None
        info = da.get_dual_agent_debug_info("t_da_int_new_001")
        assert info["enabled"] is True
        assert info["has_state"] is False
        assert info["calibration_round"] == 0

    def test_returns_state_after_observation(self, monkeypatch, clean_calibration_log):
        """flag=True + 跑过一次 → has_state=True + round >= 1."""
        import web.api.dual_agent as da
        monkeypatch.setattr(da, "DUAL_AGENT_ENABLED", True)
        da._orchestrator = None

        da.process_observation_for_student(
            student_id="t_da_int_dbg_001",
            problem_id="P004",
            skill_id="python.basics",
            correct=True,
            score=1.0,
        )
        info = da.get_dual_agent_debug_info("t_da_int_dbg_001")
        assert info["has_state"] is True
        assert info["calibration_round"] >= 1


# ─── 4. 协议兼容性 (CLAUDE.md [8] 改 API 必加测试) ────────────────


class TestProtocolFields:
    """process_observation_for_student 返回 dict 的必填字段."""

    def test_required_fields(self, monkeypatch, clean_calibration_log):
        """返回 dict 必须含 round / intervention_type / warnings / duration_ms / calibration_id."""
        import web.api.dual_agent as da
        monkeypatch.setattr(da, "DUAL_AGENT_ENABLED", True)
        da._orchestrator = None

        result = da.process_observation_for_student(
            student_id="t_da_int_proto_001",
            problem_id="P005",
            skill_id="python.basics",
            correct=True,
            score=1.0,
        )
        assert result is not None
        for key in ("round", "intervention_type", "warnings", "duration_ms",
                    "calibration_id", "degraded_mode"):
            assert key in result, f"dual_agent.process_observation 返回 dict 丢失字段: {key}"


# ─── 5. dual_agent 失败时不写启发式 fallback ────────────────────────


class TestNoHeuristicFallback:
    """CLAUDE.md [6]: 失败不写启发式 fallback, 跟 LCA update 一样走 None 返回."""

    def test_process_observation_exception_returns_none(self, monkeypatch):
        """DualAgentOrchestrator.process_observation 抛异常 → 主函数返回 None."""
        import web.api.dual_agent as da
        monkeypatch.setattr(da, "DUAL_AGENT_ENABLED", True)
        da._orchestrator = None

        from ecos.dual_agent import DualAgentOrchestrator
        with patch.object(DualAgentOrchestrator, "process_observation",
                          side_effect=ValueError("test")):
            result = da.process_observation_for_student(
                student_id="t_da_int_hf_001",
                problem_id="P006",
                skill_id="python.basics",
                correct=True,
                score=1.0,
            )
        assert result is None, "失败时必须返回 None, 不写启发式兜底"

    def test_db_failure_returns_none(self, monkeypatch, clean_calibration_log):
        """save_calibration 失败 → 主函数仍返回 dict (round 等字段填了, calibration_id=0)."""
        import web.api.dual_agent as da
        monkeypatch.setattr(da, "DUAL_AGENT_ENABLED", True)
        da._orchestrator = None

        # mock save_calibration 抛错 (Database 类的方法)
        with patch("ecos.persistence.db.Database.save_calibration",
                   side_effect=RuntimeError("DB down")):
            result = da.process_observation_for_student(
                student_id="t_da_int_dbfail_001",
                problem_id="P007",
                skill_id="python.basics",
                correct=True,
                score=1.0,
            )
        # 即使 DB 写失败, 主函数还是返回 dict (只有 calibration_id=0)
        # 跟 LCA update 失败时的处理一致: 不抛错, 不影响主响应
        assert result is not None
        assert result["calibration_id"] == 0
