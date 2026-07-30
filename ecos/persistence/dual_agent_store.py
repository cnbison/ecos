"""Dual Agent 互校状态持久化层 — v0.61.0 实施.

背景 (Bisen 2026-07-29 拍板):
  v0.60.0 dual_agent 接入主循环, 但 state / intervention_history / state_trajectory
  / calibration_round / warnings / belief_challenges / strategy_challenges /
  _consecutive_ineffective 全部 in-memory dict, 进程退丢.
  v0.60.4 验证完成 (lbc001 答 5 道) 但进程退后 state 全部丢.
  v0.61.0 启动: 8 字段持久化到 SQLite, 跨进程恢复.

设计原则 (CLAUDE.md 防御性自检 [5]):
  - 一次性列全 8 关键字段, 避免历史栽过的"分批漏字段"问题
  - 8 字段 (跟 DualAgentOrchestrator 内部 dict 一一对应):
      1. state_snapshot              (BeliefState 序列化, 当前 CTA 视角)
      2. intervention_history        (List[CalibratedLCAResult.to_dict()])
      3. state_trajectory            (List[BeliefState.to_dict()], max 100/sid)
      4. calibration_round           (int)
      5. warnings                    (List[str] 抗幻觉警告)
      6. belief_challenges           (List[BeliefChallenge.to_dict()])
      7. strategy_challenges         (List[StrategyChallenge.to_dict()])
      8. consecutive_ineffective      (int, _consecutive_ineffective 计数器)

架构选择 (跟 v0.57.0 LCAStore 一致):
  - 独立表 `student_dual_agent_state` (per-student 1 row, 1:1 with students)
  - 不污染 students 表 schema (dual_agent 是 dual_agent 独有状态)
  - 独立 db connection (跟 LCAStore 同样模式, 避免跟 Database 单例耦合)

防御性自检 (CLAUDE.md 规范):
  - [1] silent pass → _log.warning(..., exc_info=True) 全部
  - [5] 8 字段对齐 (本文件 + DualAgentOrchestrator.dump_state/load_state 一次性列全)
  - [6] 持久化失败不污染 in-memory state

v0.61.0 不做的事 (避免 scope creep):
  - dual_agent 独立 LCA 视图 (修复 v0.60.0 arm_pull 涨 1 trade-off, 留 v0.62.0+)
  - 元反思模式 4 周停滞检测 (留 v0.63.0+)
  - lbc001 / lbc002 历史 dual_agent 数据回溯 (v0.60.4 后已丢, 不写迁移脚本, 跟 v0.57.0 LCA 同样态度)
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

_log = logging.getLogger(__name__)


# ─── Schema SQL ───────────────────────────────────────────────────────────────

DUAL_AGENT_STATE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS student_dual_agent_state (
    student_id TEXT PRIMARY KEY,

    -- 8 字段 (CLAUDE.md 防御性自检 [5] 一次性列全)
    -- 跟 DualAgentOrchestrator 内部 dict 一一对应
    state_snapshot TEXT,             -- JSON: BeliefState.to_dict()
    intervention_history TEXT,        -- JSON: List[CalibratedLCAResult.to_dict()]
    state_trajectory TEXT,            -- JSON: List[BeliefState.to_dict()] (max 100/sid)
    calibration_round INTEGER DEFAULT 0,
    warnings TEXT,                   -- JSON: List[str] 抗幻觉警告
    belief_challenges TEXT,          -- JSON: List[BeliefChallenge.to_dict()]
    strategy_challenges TEXT,        -- JSON: List[StrategyChallenge.to_dict()]
    consecutive_ineffective INTEGER DEFAULT 0,

    last_active_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_dual_agent_state_last_active
    ON student_dual_agent_state(last_active_at);
"""


# ─── Data class ───────────────────────────────────────────────────────────────


@dataclass
class DualAgentStateSnapshot:
    """Dual Agent 状态快照 (per-student 8 字段全打包).

    Attributes:
        student_id: 学生 ID
        state_snapshot: 当前 BeliefState (CTA 视角)
        intervention_history: 互校历史 (List[CalibratedLCAResult.to_dict()])
        state_trajectory: 状态轨迹 (List[BeliefState.to_dict()], max 100/sid)
        calibration_round: 当前互校轮次
        warnings: 抗幻觉警告 (List[str])
        belief_challenges: 信念质疑历史 (List[BeliefChallenge.to_dict()])
        strategy_challenges: 策略质疑历史 (List[StrategyChallenge.to_dict()])
        consecutive_ineffective: 连续无效干预计数
        last_active_at: 最后活跃时间 (ISO format)
    """

    student_id: str
    state_snapshot: Dict[str, Any]
    intervention_history: List[Dict[str, Any]]
    state_trajectory: List[Dict[str, Any]]
    calibration_round: int
    warnings: List[str]
    belief_challenges: List[Dict[str, Any]]
    strategy_challenges: List[Dict[str, Any]]
    consecutive_ineffective: int
    last_active_at: str


# ─── DualAgentStore ──────────────────────────────────────────────────────────


class DualAgentStore:
    """Dual Agent 状态持久化 (SQLite).

    设计: 简单直接, 8 字段全 JSON 序列化.
    不做 incremental save / 缓存 — 每次 save 都是全量覆盖 (per-student 数据量小).

    v0.68.0: 修 Flask threaded dev server 跨线程 BUG.
      之前 sqlite3.connect 默认 check_same_thread=True, connection 绑定到主线程,
      子线程请求报 "SQLite objects created in a thread can only be used in that same thread".
      lbc003 答 35 题期间 dual_agent_state 只落盘 21/35 round, 副作用:
        - state_trajectory 长度 21 (缺 14 round)
        - calibration_round 卡在 21 (跟 calibration_log 写到 31 错位)
        - H3 V2 (overall_confidence) 只能拿到 20 样本 (不够 30 显著)
      修复: check_same_thread=False + WAL 模式 (跟 v0.51.1 db.py 同样范式).
    """

    def __init__(self, db_path: str = "web/ecos.db"):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._init_schema()

    @property
    def conn(self) -> sqlite3.Connection:
        """Lazy 数据库连接 (单例).

        v0.68.0: check_same_thread=False + WAL 模式 (跟 db.py v0.51.1 同样范式).
          WAL 允许 reader/writer 并发, 适合 Flask 多线程 dispatch.
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
        """初始化表 (幂等)."""
        try:
            with self._tx():
                self.conn.executescript(DUAL_AGENT_STATE_SCHEMA_SQL)
        except Exception:
            # 防御性自检 [1]: schema init 失败必须 warning, 不能 silent pass
            _log.warning(
                "DualAgentStore schema init 失败 (db=%s), 持久化不可用",
                self.db_path, exc_info=True,
            )
            raise

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                _log.warning("DualAgentStore.close 失败", exc_info=True)
            finally:
                self._conn = None

    # ─── Save / Load (CLAUDE.md [5] 8 字段对齐) ─────────────────────────────

    def save_state(
        self,
        student_id: str,
        state_snapshot: Dict[str, Any],
        intervention_history: List[Dict[str, Any]],
        state_trajectory: List[Dict[str, Any]],
        calibration_round: int,
        warnings: List[str],
        belief_challenges: List[Dict[str, Any]],
        strategy_challenges: List[Dict[str, Any]],
        consecutive_ineffective: int,
    ) -> None:
        """保存 Dual Agent 状态 (8 字段全存, 覆盖式).

        防御性自检 [1]: save 失败必须 _log.warning, 不能 silent pass.
        防御性自检 [5]: 8 字段必须一次全存, 避免分批漏字段.
        防御性自检 [6]: 持久化失败不污染 in-memory state (caller 负责 try/except).
        """
        now = datetime.now().isoformat()
        try:
            with self._tx():
                self.conn.execute(
                    """
                    INSERT INTO student_dual_agent_state (
                        student_id, state_snapshot, intervention_history,
                        state_trajectory, calibration_round, warnings,
                        belief_challenges, strategy_challenges,
                        consecutive_ineffective, last_active_at
                    ) VALUES (
                        :sid, :ss, :ih, :st, :cr, :w, :bc, :sc, :ci, :now
                    )
                    ON CONFLICT(student_id) DO UPDATE SET
                        state_snapshot = :ss,
                        intervention_history = :ih,
                        state_trajectory = :st,
                        calibration_round = :cr,
                        warnings = :w,
                        belief_challenges = :bc,
                        strategy_challenges = :sc,
                        consecutive_ineffective = :ci,
                        last_active_at = :now
                    """,
                    dict(
                        sid=student_id,
                        ss=json.dumps(state_snapshot, ensure_ascii=False),
                        ih=json.dumps(intervention_history, ensure_ascii=False),
                        st=json.dumps(state_trajectory, ensure_ascii=False),
                        cr=int(calibration_round),
                        w=json.dumps(warnings, ensure_ascii=False),
                        bc=json.dumps(belief_challenges, ensure_ascii=False),
                        sc=json.dumps(strategy_challenges, ensure_ascii=False),
                        ci=int(consecutive_ineffective),
                        now=now,
                    ),
                )
        except Exception:
            _log.warning(
                "DualAgentStore.save_state 失败 (student=%s), dual_agent 状态这次持久化丢失",
                student_id, exc_info=True,
            )
            raise

    def load_state(self, student_id: str) -> Optional[DualAgentStateSnapshot]:
        """加载 Dual Agent 状态 (8 字段全读).

        Returns:
            DualAgentStateSnapshot if found, None if not.
        """
        try:
            row = self.conn.execute(
                "SELECT * FROM student_dual_agent_state WHERE student_id = ?",
                (student_id,),
            ).fetchone()
        except Exception:
            _log.warning(
                "DualAgentStore.load_state 查询失败 (student=%s), 视为无 dual_agent 状态",
                student_id, exc_info=True,
            )
            return None

        if row is None:
            return None

        try:
            return DualAgentStateSnapshot(
                student_id=row["student_id"],
                state_snapshot=json.loads(row["state_snapshot"]) if row["state_snapshot"] else {},
                intervention_history=json.loads(row["intervention_history"]) if row["intervention_history"] else [],
                state_trajectory=json.loads(row["state_trajectory"]) if row["state_trajectory"] else [],
                calibration_round=int(row["calibration_round"] or 0),
                warnings=json.loads(row["warnings"]) if row["warnings"] else [],
                belief_challenges=json.loads(row["belief_challenges"]) if row["belief_challenges"] else [],
                strategy_challenges=json.loads(row["strategy_challenges"]) if row["strategy_challenges"] else [],
                consecutive_ineffective=int(row["consecutive_ineffective"] or 0),
                last_active_at=row["last_active_at"] or "",
            )
        except Exception:
            # 防御性自检 [1]: 解析失败必须 warning
            _log.warning(
                "DualAgentStore.load_state 解析失败 (student=%s), 返回 None (dual_agent 冷启动)",
                student_id, exc_info=True,
            )
            return None

    def has_state(self, student_id: str) -> bool:
        """检查是否有 dual_agent 状态 (轻量查询)."""
        try:
            row = self.conn.execute(
                "SELECT 1 FROM student_dual_agent_state WHERE student_id = ? LIMIT 1",
                (student_id,),
            ).fetchone()
            return row is not None
        except Exception:
            _log.warning(
                "DualAgentStore.has_state 查询失败 (student=%s)",
                student_id, exc_info=True,
            )
            return False

    def delete_state(self, student_id: str) -> None:
        """删除 dual_agent 状态 (清理用, 当前未使用)."""
        try:
            with self._tx():
                self.conn.execute(
                    "DELETE FROM student_dual_agent_state WHERE student_id = ?",
                    (student_id,),
                )
        except Exception:
            _log.warning(
                "DualAgentStore.delete_state 失败 (student=%s)",
                student_id, exc_info=True,
            )

    def get_all_students_with_dual_agent_state(self) -> List[str]:
        """返回所有有 dual_agent 状态的学生 ID 列表."""
        try:
            rows = self.conn.execute(
                "SELECT student_id FROM student_dual_agent_state ORDER BY last_active_at DESC"
            ).fetchall()
            return [r["student_id"] for r in rows]
        except Exception:
            _log.warning(
                "DualAgentStore.get_all_students_with_dual_agent_state 失败",
                exc_info=True,
            )
            return []


# ─── Module-level helpers ─────────────────────────────────────────────────────

# 全局单例 (lazy init)
_store: Optional[DualAgentStore] = None


def get_dual_agent_store(db_path: str = "web/ecos.db") -> DualAgentStore:
    """获取 DualAgentStore 全局单例 (lazy init).

    防御性自检 [1]: init 失败必须 warning, 不能 silent pass.
    """
    global _store
    if _store is None:
        try:
            _store = DualAgentStore(db_path=db_path)
        except Exception:
            _log.warning(
                "DualAgentStore 单例初始化失败 (db=%s), 持久化不可用",
                db_path, exc_info=True,
            )
            raise
    return _store


__all__ = [
    "DualAgentStateSnapshot",
    "DualAgentStore",
    "get_dual_agent_store",
]
