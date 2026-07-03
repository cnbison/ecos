"""Persistence 层——学生状态持久化 + 4 层记忆 + 会话管理.

对应 research/10-engineering/05-persistence-session.md。
MVP 范围：6 张 SQLite 表 + ECOSSession + chunk 隔离。
"""

from .db import Database, DatabaseConfig

__status__ = "m2-w3-persistence"

__all__ = [
    "Database",
    "DatabaseConfig",
]
