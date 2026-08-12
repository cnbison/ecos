"""LCA (Learning Coach Agent) 持久化层 — v0.57.0 实施.

背景 (Bisen 2026-07-27 14:00 拍板):
  lbc002 答题 32 道, LCA bandit 数据健康 (10 arm 全部拉到过, 分布均匀).
  v0.57.0 启动: LCA 状态 (intervention_history + LinUCB A/b 矩阵 + arm 拉取计数)
  从 in-memory dict 改为 SQLite 持久化, 跨进程恢复.

设计原则 (CLAUDE.md 防御性自检 [5]):
  - 一次性列全 8 关键字段 (v0.93.0-c 加 pomdp_diagnostic → 9 字段)
  - 9 字段 (CLAUDE.md [5] 8 字段 + lca.py 实际多 1 个 select_count):
      1. intervention_history   (List[Intervention.to_dict()])
      2. bandit_a               (List[List[List[float]]]: n_arms × d × d)
      3. bandit_b               (List[List[float]]: n_arms × d)
      4. arm_pull_counts        (List[int]: n_arms)
      5. last_intervention      (Intervention.to_dict() | None)
      6. update_count           (int: 总 update 次数, LinUCB.update 调用累计)
      7. select_count           (int: 总 select 次数, LinUCB.select 调用累计)
      8. cognitive_twin         (Dict | None — v0.91.0-d 新增, Twin → Human Twin 抽象)
      9. pomdp_diagnostic       (Dict | None — v0.93.0-c 新增, Twin 第 5 维度)

架构选择:
  - 独立表 `student_lca_state` (per-student 1 row, 1:1 with students)
  - 不污染 students 表 schema (LCA 是 LCA 独有状态, 不跟 belief state 混)
  - 学生删除时 LCA state 自动孤儿, 需手动清理 (后续 v0.59.0+ 加 cascade)

防御性自检:
  - [1] silent pass → _log.warning(..., exc_info=True) 全部
  - [5] 9 字段对齐 (本文件), 缺一不可
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_log = logging.getLogger(__name__)


# ─── Schema SQL ───────────────────────────────────────────────────────────────

LCA_STATE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS student_lca_state (
    student_id TEXT PRIMARY KEY,

    -- 9 字段 (CLAUDE.md 防御性自检 [5] 一次性列全)
    -- 注: bandit_a / bandit_b / arm_pull_counts 来自 LinUCB 内部
    -- intervention_history / last_intervention 来自 LCAEngine.intervention_history
    -- update_count / select_count 来自 lca.py 模块级 dict
    -- cognitive_twin 来自 LCAEngine._cognitive_twin (v0.91.0-d)
    -- pomdp_diagnostic 来自 LCAEngine._pomdp_diagnostic (v0.93.0-c)
    intervention_history TEXT,     -- JSON: List[Intervention.to_dict()]
    bandit_a TEXT,                  -- JSON: List[List[List[float]]] (n_arms × d × d)
    bandit_b TEXT,                  -- JSON: List[List[float]] (n_arms × d)
    arm_pull_counts TEXT,           -- JSON: List[int] (n_arms,)
    last_intervention TEXT,         -- JSON: Intervention.to_dict() | null
    update_count INTEGER DEFAULT 0,
    select_count INTEGER DEFAULT 0,
    cognitive_twin TEXT,            -- JSON: CognitiveTwinAgent.dump_state() | null  (v0.91.0-d)
    pomdp_diagnostic TEXT,          -- JSON: POMDPDiagnostic.to_dict() | null  (v0.93.0-c)

    last_active_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_lca_state_last_active ON student_lca_state(last_active_at);
"""


# ─── Data class ───────────────────────────────────────────────────────────────


@dataclass
class LCAStateSnapshot:
    """LCA 状态快照 (per-student 9 字段全打包).

    Attributes:
        student_id: 学生 ID
        intervention_history: 干预历史 (List[Intervention.to_dict()])
        bandit_a: LinUCB A 矩阵 (List[List[List[float]]]: n_arms × d × d)
        bandit_b: LinUCB b 向量 (List[List[float]]: n_arms × d)
        arm_pull_counts: 各 arm 拉取次数 (List[int])
        last_intervention: 最近一次干预 (Intervention.to_dict() | None)
        update_count: 总 update 次数
        select_count: 总 select 次数
        cognitive_twin: v0.91.0-d 新增, CognitiveTwinAgent.dump_state() 或 None
        pomdp_diagnostic: v0.93.0-c 新增, POMDPDiagnostic.to_dict() 或 None
        last_active_at: 最后活跃时间 (ISO format)
    """

    student_id: str
    intervention_history: List[Dict[str, Any]]
    bandit_a: List[List[List[float]]]
    bandit_b: List[List[float]]
    arm_pull_counts: List[int]
    last_intervention: Optional[Dict[str, Any]]
    update_count: int
    select_count: int
    cognitive_twin: Optional[Dict[str, Any]]
    pomdp_diagnostic: Optional[Dict[str, Any]]
    last_active_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "student_id": self.student_id,
            "intervention_history": self.intervention_history,
            "bandit_a": self.bandit_a,
            "bandit_b": self.bandit_b,
            "arm_pull_counts": self.arm_pull_counts,
            "last_intervention": self.last_intervention,
            "update_count": self.update_count,
            "select_count": self.select_count,
            "cognitive_twin": self.cognitive_twin,
            "pomdp_diagnostic": self.pomdp_diagnostic,
            "last_active_at": self.last_active_at,
        }


# ─── LCAStore ────────────────────────────────────────────────────────────────


class LCAStore:
    """LCA 状态持久化 (SQLite).

    设计: 简单直接, 9 字段全 JSON 序列化 (v0.93.0-c 加 pomdp_diagnostic).
    不做 incremental save / 缓存 — 每次 save 都是全量覆盖 (per-student 数据量小).
    """

    def __init__(self, db_path: str = "web/ecos.db"):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._init_schema()

    @property
    def conn(self) -> sqlite3.Connection:
        """Lazy 数据库连接 (单例).

        v0.68.0: check_same_thread=False + WAL 模式 (跟 db.py v0.51.1 同样范式).
          之前默认 check_same_thread=True, Flask threaded dev server 跨线程
          报 "SQLite objects created in a thread can only be used in that same thread",
          lca_state 持久化全失败. 修复后 round-by-round LCA state 正常落盘.
        """
        if self._conn is None:
            self._conn = sqlite3.connect(
                self.db_path,
                timeout=10.0,
                check_same_thread=False,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode = WAL")
        return self._conn

    @contextmanager
    def _tx(self):
        """事务上下文."""
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def _init_schema(self) -> None:
        """初始化表 (幂等, 含 v0.93.0-c 老 DB migration)."""
        try:
            with self._tx():
                self.conn.executescript(LCA_STATE_SCHEMA_SQL)
                # v0.93.0-c: 老 DB (v0.92.0-d 升级前) 没 cognitive_twin / pomdp_diagnostic 列
                #   自动 ALTER TABLE 加列 (per-student 0 row 时 0 影响, 老 row NULL 兜底)
                #   跟 v0.91.0-d cognitive_twin 列 migration pattern 一致
                self._migrate_add_column_if_missing(
                    "student_lca_state", "cognitive_twin", "TEXT",
                )
                self._migrate_add_column_if_missing(
                    "student_lca_state", "pomdp_diagnostic", "TEXT",
                )
        except Exception:
            # 防御性自检 [1]: schema init 失败必须 warning, 不能 silent pass
            _log.warning(
                "LCAStore schema init 失败 (db=%s), 持久化不可用",
                self.db_path, exc_info=True,
            )
            raise

    def _migrate_add_column_if_missing(
        self, table: str, column: str, col_type: str,
    ) -> None:
        """v0.93.0-c: ALTER TABLE IF NOT EXISTS pattern (老 DB 兼容).

        检查表是否已存在 column, 缺则 ALTER TABLE ADD COLUMN.
        SQLite 没原生 IF NOT EXISTS for ADD COLUMN, 用 PRAGMA table_info 检查.
        失败 _log.warning 不 raise (老 DB 加列是 best-effort).
        """
        try:
            cursor = self.conn.execute(f"PRAGMA table_info({table})")
            existing_columns = {row[1] for row in cursor.fetchall()}
            if column in existing_columns:
                return
            self.conn.execute(
                f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
            )
            _log.info(
                "LCAStore migration: 加列 %s.%s (%s) 完成",
                table, column, col_type,
            )
        except Exception:
            _log.warning(
                "LCAStore migration: ALTER TABLE %s ADD COLUMN %s 失败 (best-effort)",
                table, column, exc_info=True,
            )

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                _log.warning("LCAStore.close 失败", exc_info=True)
            finally:
                self._conn = None

    # ─── Save / Load (CLAUDE.md [5] 9 字段对齐) ─────────────────────────────

    def save_state(
        self,
        student_id: str,
        intervention_history: List[Dict[str, Any]],
        bandit_a: List[List[List[float]]],
        bandit_b: List[List[float]],
        arm_pull_counts: List[int],
        last_intervention: Optional[Dict[str, Any]],
        update_count: int,
        select_count: int,
        cognitive_twin: Optional[Dict[str, Any]] = None,
        pomdp_diagnostic: Optional[Dict[str, Any]] = None,
    ) -> None:
        """保存 LCA 状态 (9 字段全存, 覆盖式).

        防御性自检 [1]: save 失败必须 _log.warning, 不能 silent pass.
        防御性自检 [5]: 9 字段必须一次全存, 避免分批漏字段.
        v0.91.0-d: 加 cognitive_twin 参数 (Twin → Human Twin 抽象).
        v0.93.0-c: 加 pomdp_diagnostic 参数 (Twin 第 5 维度 — POMDP T/R 后验可视化).
        """
        now = datetime.now().isoformat()
        try:
            with self._tx():
                self.conn.execute(
                    """
                    INSERT INTO student_lca_state (
                        student_id, intervention_history, bandit_a, bandit_b,
                        arm_pull_counts, last_intervention, update_count, select_count,
                        cognitive_twin, pomdp_diagnostic,
                        last_active_at
                    ) VALUES (
                        :sid, :ih, :ba, :bb,
                        :apc, :li, :uc, :sc,
                        :ct, :pd,
                        :now
                    )
                    ON CONFLICT(student_id) DO UPDATE SET
                        intervention_history = :ih,
                        bandit_a = :ba,
                        bandit_b = :bb,
                        arm_pull_counts = :apc,
                        last_intervention = :li,
                        update_count = :uc,
                        select_count = :sc,
                        cognitive_twin = :ct,
                        pomdp_diagnostic = :pd,
                        last_active_at = :now
                    """,
                    dict(
                        sid=student_id,
                        ih=json.dumps(intervention_history, ensure_ascii=False),
                        ba=json.dumps(bandit_a),
                        bb=json.dumps(bandit_b),
                        apc=json.dumps(arm_pull_counts),
                        li=json.dumps(last_intervention, ensure_ascii=False) if last_intervention else None,
                        uc=int(update_count),
                        sc=int(select_count),
                        ct=json.dumps(cognitive_twin, ensure_ascii=False) if cognitive_twin else None,
                        pd=json.dumps(pomdp_diagnostic, ensure_ascii=False) if pomdp_diagnostic else None,
                        now=now,
                    ),
                )
        except Exception:
            _log.warning(
                "LCAStore.save_state 失败 (student=%s), LCA 状态这次持久化丢失",
                student_id, exc_info=True,
            )
            raise

    def load_state(self, student_id: str) -> Optional[LCAStateSnapshot]:
        """加载 LCA 状态 (9 字段全读).

        Returns:
            LCAStateSnapshot if found, None if not.
        """
        try:
            row = self.conn.execute(
                "SELECT * FROM student_lca_state WHERE student_id = ?",
                (student_id,),
            ).fetchone()
        except Exception:
            _log.warning(
                "LCAStore.load_state 查询失败 (student=%s), 视为无 LCA 状态",
                student_id, exc_info=True,
            )
            return None

        if row is None:
            return None

        try:
            # v0.93.0-c: 老 v0.92 snapshot row 没 cognitive_twin / pomdp_diagnostic 列
            #   (迁移前 ALTER TABLE 已加列, 但老 row 数据 NULL, 走 .get() 兜底)
            return LCAStateSnapshot(
                student_id=row["student_id"],
                intervention_history=json.loads(row["intervention_history"]) if row["intervention_history"] else [],
                bandit_a=json.loads(row["bandit_a"]) if row["bandit_a"] else [],
                bandit_b=json.loads(row["bandit_b"]) if row["bandit_b"] else [],
                arm_pull_counts=json.loads(row["arm_pull_counts"]) if row["arm_pull_counts"] else [],
                last_intervention=json.loads(row["last_intervention"]) if row["last_intervention"] else None,
                update_count=int(row["update_count"] or 0),
                select_count=int(row["select_count"] or 0),
                # v0.91.0-d: cognitive_twin (老 row NULL 兜底)
                cognitive_twin=json.loads(row["cognitive_twin"]) if row["cognitive_twin"] else None,
                # v0.93.0-c: pomdp_diagnostic (老 row NULL 兜底)
                pomdp_diagnostic=json.loads(row["pomdp_diagnostic"]) if row["pomdp_diagnostic"] else None,
                last_active_at=row["last_active_at"] or "",
            )
        except Exception:
            # 防御性自检 [1]: 解析失败必须 warning
            _log.warning(
                "LCAStore.load_state 解析失败 (student=%s), 返回 None (LinUCB 冷启动)",
                student_id, exc_info=True,
            )
            return None

    def has_state(self, student_id: str) -> bool:
        """检查是否有 LCA 状态 (轻量查询)."""
        try:
            row = self.conn.execute(
                "SELECT 1 FROM student_lca_state WHERE student_id = ? LIMIT 1",
                (student_id,),
            ).fetchone()
            return row is not None
        except Exception:
            _log.warning(
                "LCAStore.has_state 查询失败 (student=%s)",
                student_id, exc_info=True,
            )
            return False

    def delete_state(self, student_id: str) -> None:
        """删除 LCA 状态 (清理用, 当前未使用)."""
        try:
            with self._tx():
                self.conn.execute(
                    "DELETE FROM student_lca_state WHERE student_id = ?",
                    (student_id,),
                )
        except Exception:
            _log.warning(
                "LCAStore.delete_state 失败 (student=%s)",
                student_id, exc_info=True,
            )

    def get_all_students_with_lca_state(self) -> List[str]:
        """返回所有有 LCA 状态的学生 ID 列表."""
        try:
            rows = self.conn.execute(
                "SELECT student_id FROM student_lca_state ORDER BY last_active_at DESC"
            ).fetchall()
            return [r["student_id"] for r in rows]
        except Exception:
            _log.warning(
                "LCAStore.get_all_students_with_lca_state 失败",
                exc_info=True,
            )
            return []


# ─── Module-level helpers ─────────────────────────────────────────────────────

# 全局单例 (lazy init)
_store: Optional[LCAStore] = None


def get_lca_store(db_path: str = "web/ecos.db") -> LCAStore:
    """获取 LCAStore 全局单例 (lazy init).

    防御性自检 [1]: init 失败必须 warning, 不能 silent pass.
    """
    global _store
    if _store is None:
        try:
            _store = LCAStore(db_path=db_path)
        except Exception:
            _log.warning(
                "LCAStore 单例初始化失败 (db=%s), 持久化不可用",
                db_path, exc_info=True,
            )
            raise
    return _store


__all__ = [
    "LCAStateSnapshot",
    "LCAStore",
    "get_lca_store",
]
