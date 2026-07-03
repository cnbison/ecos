"""ECOS Session 层——跨会话状态管理 + chunk 隔离.

对应 research/10-engineering/05-persistence-session.md §4。
MVP 范围：ECOSSession + ChunkIsolation + 自动保存 + epoch 快照。
"""

from .ecos_session import ECOSSession, ECOSSessionConfig
from .chunk_isolation import ChunkIsolation

__status__ = "m2-w3-persistence"

__all__ = [
    "ECOSSession",
    "ECOSSessionConfig",
    "ChunkIsolation",
]
