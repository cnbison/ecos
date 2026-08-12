"""v0.93.0-c: LCAStore POMDP 诊断持久化测试 (第 9 字段 pomdp_diagnostic).

对应设计: discussions/2026-08-12-v093-design.md §3.

v0.93.0-c LCAStore 持久化范围:
  - student_lca_state 表新增 pomdp_diagnostic TEXT 列 (CLAUDE.md 防御性自检 [5] 9 字段对齐)
  - 跟 v0.91.0-d cognitive_twin 列 migration pattern 一致: ALTER TABLE IF NOT EXISTS 老 DB 兼容
  - LCAStateSnapshot dataclass 加 pomdp_diagnostic Optional[Dict] 字段 (默认 None)
  - save_state 加 pomdp_diagnostic kwarg
  - load_state 用 row[...] 直接读 (老 row 缺列 → sqlite3.Row KeyError, 需 .get() 兜底)

测试范围 (3 tests):
  1. LCAStore.save_state / load_state round-trip 含 pomdp_diagnostic (1 test)
  2. LCAStore 9 字段对齐 (1 test): save_state 9 个字段全部持久化
  3. LCAStore 老 DB 兼容 migration (1 test): 缺 pomdp_diagnostic 列时 ALTER TABLE
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from ecos.persistence.lca_store import (
    LCAStateSnapshot,
    LCAStore,
    LCA_STATE_SCHEMA_SQL,
)


# ---------------------------------------------------------------------------
# 1. LCAStore.save_state / load_state round-trip 含 pomdp_diagnostic (1 test)
# ---------------------------------------------------------------------------


def test_lca_store_save_load_round_trip_with_pomdp_diagnostic(tmp_path: Path):
    """LCAStore.save_state 9 字段全存 + load_state 全读, pomdp_diagnostic round-trip 一致."""
    db_path = str(tmp_path / "ecos_lca_test.db")
    store = LCAStore(db_path=db_path)
    try:
        # 构造 minimal POMDPDiagnostic dict (POMDPDiagnostic.to_dict() 输出)
        diagnostic_dict = {
            "T": {"mean": [[[0.25] * 10] * 4] * 4, "count": [[[0] * 10] * 4] * 4, "alpha0": 1.0, "schema_version": "0.93.0"},
            "R": {"mean": [[0.5] * 10] * 4, "alpha": [[1.0] * 10] * 4, "beta": [[1.0] * 10] * 4,
                  "alpha0": 1.0, "variance": [[0.0] * 10] * 4, "schema_version": "0.93.0"},
            "belief": [0.25, 0.25, 0.25, 0.25],
            "coverage": [[0] * 10] * 4,
            "most_likely_state": 0,
            "last_updated": "2026-08-12T10:00:00",
            "schema_version": "0.93.0",
        }

        # 9 字段 save (含 pomdp_diagnostic)
        store.save_state(
            student_id="stu-evo-001",
            intervention_history=[{"ts": "2026-08-12T10:00:00", "type": "intervention"}],
            bandit_a=[[[0.1] * 10] * 10],
            bandit_b=[[0.1] * 10],
            arm_pull_counts=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            last_intervention={"id": "iv-001", "type": "hint"},
            update_count=5,
            select_count=10,
            cognitive_twin={"version": "0.92.0", "trajectory_count": 3},
            pomdp_diagnostic=diagnostic_dict,
        )

        # load 回 9 字段
        snap = store.load_state("stu-evo-001")
        assert snap is not None
        assert snap.student_id == "stu-evo-001"
        assert snap.pomdp_diagnostic == diagnostic_dict
        assert snap.cognitive_twin == {"version": "0.92.0", "trajectory_count": 3}
        assert snap.update_count == 5
        assert snap.select_count == 10
    finally:
        store.close()


# ---------------------------------------------------------------------------
# 2. LCAStore 9 字段对齐 (1 test)
# ---------------------------------------------------------------------------


def test_lca_store_9_fields_alignment(tmp_path: Path):
    """LCAStore.save_state 9 字段 (intervention_history/bandit_a/b/arm_pull_counts/last_intervention/update_count/select_count/cognitive_twin/pomdp_diagnostic) 全持久化.

    防御性自检 [5]: CLAUDE.md 9 字段对齐一次列全, 缺一不可 (跟 v0.92.0-d 8 字段 → v0.93.0-c 9 字段).
    """
    db_path = str(tmp_path / "ecos_lca_test.db")
    store = LCAStore(db_path=db_path)
    try:
        store.save_state(
            student_id="stu-evo-002",
            intervention_history=[],
            bandit_a=[[[0.0] * 10] * 10],
            bandit_b=[[0.0] * 10],
            arm_pull_counts=[0] * 10,
            last_intervention=None,
            update_count=0,
            select_count=0,
            cognitive_twin=None,
            pomdp_diagnostic=None,
        )

        # 直接查 DB 验证 9 字段列全在
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM student_lca_state WHERE student_id = ?",
                ("stu-evo-002",),
            ).fetchone()
            assert row is not None
            # 9 字段对齐
            assert row["intervention_history"] == "[]"
            assert row["bandit_a"] is not None
            assert row["bandit_b"] is not None
            assert row["arm_pull_counts"] == "[0, 0, 0, 0, 0, 0, 0, 0, 0, 0]"
            assert row["last_intervention"] is None
            assert row["update_count"] == 0
            assert row["select_count"] == 0
            assert row["cognitive_twin"] is None  # v0.91.0-d 新增
            assert row["pomdp_diagnostic"] is None  # v0.93.0-c 新增
            assert row["last_active_at"] is not None
        finally:
            conn.close()
    finally:
        store.close()


# ---------------------------------------------------------------------------
# 3. LCAStore 老 DB 兼容 migration (1 test)
# ---------------------------------------------------------------------------


def test_lca_store_migration_add_pomdp_diagnostic_column(tmp_path: Path):
    """老 DB (v0.92.0-d 升级前, 没 pomdp_diagnostic 列) 自动 ALTER TABLE 加列.

    模拟场景:
      1. 用旧 schema (无 cognitive_twin / pomdp_diagnostic 列) 建表
      2. LCAStore.__init__ 触发 _init_schema → _migrate_add_column_if_missing
      3. 验证 cognitive_twin + pomdp_diagnostic 列自动添加
    """
    db_path = str(tmp_path / "ecos_lca_old.db")

    # 1. 手动建老表 (v0.92.0-d schema, 只有 7 字段, 无 cognitive_twin / pomdp_diagnostic)
    old_schema = """
    CREATE TABLE IF NOT EXISTS student_lca_state (
        student_id TEXT PRIMARY KEY,
        intervention_history TEXT,
        bandit_a TEXT,
        bandit_b TEXT,
        arm_pull_counts TEXT,
        last_intervention TEXT,
        update_count INTEGER DEFAULT 0,
        select_count INTEGER DEFAULT 0,
        last_active_at TEXT
    );
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(old_schema)
        conn.commit()
    finally:
        conn.close()

    # 2. LCAStore.__init__ 应触发 migration (老 DB 缺 cognitive_twin + pomdp_diagnostic)
    store = LCAStore(db_path=db_path)
    try:
        # 3. 验证 cognitive_twin + pomdp_diagnostic 列已添加
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.execute("PRAGMA table_info(student_lca_state)")
            existing_columns = {row[1] for row in cursor.fetchall()}
            assert "cognitive_twin" in existing_columns  # v0.91.0-d migration
            assert "pomdp_diagnostic" in existing_columns  # v0.93.0-c migration
        finally:
            conn.close()

        # 4. 老 row (没 cognitive_twin / pomdp_diagnostic 数据) load 时返 None
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "INSERT INTO student_lca_state (student_id, intervention_history, bandit_a, bandit_b, arm_pull_counts, last_intervention) VALUES (?, ?, ?, ?, ?, ?)",
                ("stu-old-001", "[]", "[]", "[]", "[]", None),
            )
            conn.commit()
        finally:
            conn.close()

        snap = store.load_state("stu-old-001")
        assert snap is not None
        assert snap.cognitive_twin is None
        assert snap.pomdp_diagnostic is None
    finally:
        store.close()