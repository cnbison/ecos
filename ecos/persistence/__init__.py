"""Student State Persistence（学生状态持久化）.

实现学生长期认知画像的持久化：
- SQLite + JSON（参考 SelfLab SGE Phase 3 的 TwinStateDB 设计）
- Per-user 隔离
- 4 层记忆（Hawking 短期 / Crystallizer 中期 / Identity / Narrative）

借鉴 SelfLab SGE persistence.py 的工程经验（详见 discussions/2026-06-22-sge-phase3-aibeing-reflection.md）。

Phase 4+ 实施细节：见 research/10-engineering/05-persistence-session.md
"""

__status__ = "placeholder"
