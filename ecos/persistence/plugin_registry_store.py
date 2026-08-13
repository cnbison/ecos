"""Plugin Registry 持久化层 —— v0.94.0-d (Phase 7+ 抽象推演 #7).

对应设计: discussions/2026-08-13-v094-design.md §d 阶段 + 12-kernel-mapping §6 Plugin SDK.

设计:
    - 独立表 `plugin_registry` (per-deployment global, 不污染 LCAStore per-student lca_state)
    - Plugin metadata 是 per-deployment 配置 (跟 student 无关), 跟 LCA state 隔离
    - schema_version "0.94.0" 独立 schema (跟 POMDPPolicy 0.93.0 / CognitiveTwinAgent 0.92.0 / LCAStore 0.93.0 隔离)

schema:
    - name TEXT PRIMARY KEY
    - version TEXT NOT NULL
    - enabled INTEGER NOT NULL DEFAULT 1 (0/1)
    - subscribed_topics TEXT NOT NULL (JSON array)
    - metadata TEXT (JSON: full PluginMetadata.to_dict() dict, 含 schema_version)
    - schema_version TEXT NOT NULL DEFAULT "0.94.0"
    - registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

防御性自检:
    - [1] silent pass → _log.warning(..., exc_info=True) 全部
    - [5] 老 DB 兼容: CREATE TABLE IF NOT EXISTS (幂等) + ALTER TABLE (best-effort)
    - [8] PluginRegistryStore.save/load 不触及 BeliefState, 0 新 mutation site
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

_log = logging.getLogger(__name__)


# ─── Schema SQL ───────────────────────────────────────────────────────────────

PLUGIN_REGISTRY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS plugin_registry (
    name TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    subscribed_topics TEXT NOT NULL,
    metadata TEXT NOT NULL,
    schema_version TEXT NOT NULL DEFAULT '0.94.0',
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_plugin_registry_enabled
    ON plugin_registry(enabled);
"""


# ─── PluginRegistryStore ──────────────────────────────────────────────────────


class PluginRegistryStore:
    """Plugin registry 元数据持久化 (SQLite).

    v0.94.0-d 范围:
      - save_plugin(metadata) — 写入 1 个 plugin (幂等: INSERT OR REPLACE)
      - load_plugin(name) — 读 1 个 plugin metadata dict (None = 不存在)
      - list_all() — 列所有 plugin metadata dict
      - delete_plugin(name) — 删 1 个 plugin (rare, 跟 unregister 配对)
      - 老 DB 兼容: CREATE TABLE IF NOT EXISTS (幂等, 不需 ALTER TABLE 因是新表)

    设计原则 (跟 LCAStore 完全 parallel 模式):
      - per-plugin 简单直接, 6 字段全 JSON 序列化 (含 metadata dict)
      - 不做 incremental save / 缓存 — 每次 save 是全量覆盖
      - enable/disable 走 enabled 字段 (0/1 INTEGER)
    """

    def __init__(self, db_path: str = "web/ecos.db") -> None:
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._init_schema()

    @property
    def conn(self) -> sqlite3.Connection:
        """Lazy 数据库连接 (单例).

        v0.68.0: check_same_thread=False + WAL 模式 (跟 LCAStore / db.py 同样范式).
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
        """初始化表 (幂等). 老 DB (v0.93 前) 无 plugin_registry 表, CREATE TABLE IF NOT EXISTS 兜底."""
        try:
            with self._tx():
                self.conn.executescript(PLUGIN_REGISTRY_SCHEMA_SQL)
        except Exception:
            _log.warning(
                "PluginRegistryStore schema init 失败 (db=%s), 持久化不可用",
                self.db_path, exc_info=True,
            )
            raise

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                _log.warning("PluginRegistryStore.close 失败", exc_info=True)
            finally:
                self._conn = None

    # ─── Save / Load / Delete / List ───────────────────────────────────────

    def save_plugin(
        self,
        name: str,
        version: str,
        enabled: bool,
        subscribed_topics: List[str],
        metadata: Dict[str, Any],
        schema_version: str = "0.94.0",
    ) -> None:
        """保存 1 个 plugin metadata (幂等: INSERT OR REPLACE by PRIMARY KEY).

        Args:
            name: plugin name (跟 PluginMetadata.name 一致).
            version: plugin version (semver string).
            enabled: 当前 enabled 状态 (True/False → 1/0).
            subscribed_topics: 订阅的 topic 列表 (JSON array 序列化).
            metadata: 完整 PluginMetadata.to_dict() dict (含 schema_version).
            schema_version: 独立 schema version (跟 POMDPPolicy / CognitiveTwinAgent 隔离).

        防御性:
            - subscribed_topics 必须是 list (不是 tuple / set)
            - metadata 必须是 dict
            - 字段非法 raise TypeError / ValueError
        """
        if not isinstance(name, str) or not name:
            raise ValueError(f"PluginRegistryStore.save_plugin: name 必须是非空 str, got={name!r}")
        if not isinstance(version, str) or not version:
            raise ValueError(f"PluginRegistryStore.save_plugin: version 必须是非空 str, got={version!r}")
        if not isinstance(subscribed_topics, (list, tuple)):
            raise TypeError(
                f"PluginRegistryStore.save_plugin: subscribed_topics 必须是 list/tuple, "
                f"got type={type(subscribed_topics).__name__}"
            )
        if not isinstance(metadata, dict):
            raise TypeError(
                f"PluginRegistryStore.save_plugin: metadata 必须是 dict, "
                f"got type={type(metadata).__name__}"
            )

        with self._tx():
            self.conn.execute(
                """
                INSERT OR REPLACE INTO plugin_registry (
                    name, version, enabled, subscribed_topics, metadata, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(name),
                    str(version),
                    1 if enabled else 0,
                    json.dumps(list(subscribed_topics)),
                    json.dumps(metadata, default=str),
                    str(schema_version),
                ),
            )

    def load_plugin(self, name: str) -> Optional[Dict[str, Any]]:
        """读 1 个 plugin metadata dict.

        Args:
            name: plugin name.

        Returns:
            dict 含 6 字段 (name / version / enabled / subscribed_topics / metadata /
            schema_version / registered_at). None = 不存在.
        """
        try:
            row = self.conn.execute(
                "SELECT * FROM plugin_registry WHERE name = ?",
                (str(name),),
            ).fetchone()
            if row is None:
                return None
            return {
                "name": row["name"],
                "version": row["version"],
                "enabled": bool(row["enabled"]),
                "subscribed_topics": json.loads(row["subscribed_topics"]),
                "metadata": json.loads(row["metadata"]),
                "schema_version": row["schema_version"],
                "registered_at": row["registered_at"],
            }
        except Exception:
            _log.warning(
                "PluginRegistryStore.load_plugin 失败 (name=%s), 返 None",
                name, exc_info=True,
            )
            return None

    def list_all(self) -> List[Dict[str, Any]]:
        """列所有 plugin metadata dict (sorted by name).

        Returns:
            List[dict] — 每项含 6 字段 (跟 load_plugin 一致 schema). 空 list = 表为空.
        """
        try:
            rows = self.conn.execute(
                "SELECT * FROM plugin_registry ORDER BY name ASC"
            ).fetchall()
            return [
                {
                    "name": row["name"],
                    "version": row["version"],
                    "enabled": bool(row["enabled"]),
                    "subscribed_topics": json.loads(row["subscribed_topics"]),
                    "metadata": json.loads(row["metadata"]),
                    "schema_version": row["schema_version"],
                    "registered_at": row["registered_at"],
                }
                for row in rows
            ]
        except Exception:
            _log.warning(
                "PluginRegistryStore.list_all 失败, 返空 list",
                exc_info=True,
            )
            return []

    def delete_plugin(self, name: str) -> bool:
        """删 1 个 plugin (跟 unregister 配对).

        Args:
            name: plugin name.

        Returns:
            bool — True = 已删, False = 不存在.
        """
        try:
            cursor = self.conn.execute(
                "DELETE FROM plugin_registry WHERE name = ?",
                (str(name),),
            )
            return cursor.rowcount > 0
        except Exception:
            _log.warning(
                "PluginRegistryStore.delete_plugin 失败 (name=%s)",
                name, exc_info=True,
            )
            return False

    def set_enabled(self, name: str, enabled: bool) -> bool:
        """更新 1 个 plugin 的 enabled 状态 (跟 PluginRegistry.enable/disable 配对).

        Args:
            name: plugin name.
            enabled: 新 enabled 状态.

        Returns:
            bool — True = 已更新, False = 不存在.
        """
        try:
            cursor = self.conn.execute(
                "UPDATE plugin_registry SET enabled = ? WHERE name = ?",
                (1 if enabled else 0, str(name)),
            )
            return cursor.rowcount > 0
        except Exception:
            _log.warning(
                "PluginRegistryStore.set_enabled 失败 (name=%s, enabled=%s)",
                name, enabled, exc_info=True,
            )
            return False


__all__ = ["PluginRegistryStore", "PLUGIN_REGISTRY_SCHEMA_SQL"]