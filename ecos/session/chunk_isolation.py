"""Chunk 隔离机制.

对应 research/10-engineering/05-persistence-session.md §4.3。

职责：在长期运行（6-12 年）过程中，防止单次会话状态丢失。
机制：滚动 chunk 计数器，每 N 个 epoch 强制持久化一次快照。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ChunkIsolation:
    """Chunk 隔离——滚动 epoch 计数器 + 快照触发。

    用法：
        chunk = ChunkIsolation(student_id="s1", threshold_epochs=100)
        for epoch in range(250):
            if chunk.should_snapshot(epoch):
                # 保存快照并重置
                chunk.reset_counter()
    """

    student_id: str
    threshold_epochs: int = 100
    _counter: int = 0

    def should_snapshot(self, current_epoch: int) -> bool:
        """判断是否应触发快照（每 threshold_epochs 次）。"""
        self._counter = current_epoch % self.threshold_epochs
        return self._counter == 0 and current_epoch > 0

    def reset_counter(self) -> None:
        """重置计数器（在快照后调用）。"""
        self._counter = 0

    @property
    def current_chunk_index(self) -> int:
        """当前 chunk 序号（从 1 开始）。"""
        return self._counter
