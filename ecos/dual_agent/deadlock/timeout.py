"""互校超时保护（spec §5.1）.

Phase 4 MVP：使用 time.time() 计时（避免 signal 在多线程下的复杂性）。

用法：
    guard = TimeoutGuard(default_timeout_sec=30)
    with guard.timeout(seconds=5):
        do_something()  # > 5s 会抛 TimeoutError
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Optional


class TimeoutGuard:
    """互校循环超时保护."""

    def __init__(self, default_timeout_sec: int = 30):
        self.default_timeout = default_timeout_sec

    @contextmanager
    def timeout(self, seconds: Optional[int] = None):
        """超时上下文.

        Yields:
            dict {'elapsed': float, 'exceeded': bool}：调用方可在结束时检查是否超时
        Raises:
            TimeoutError: 操作超过指定秒数
        """
        seconds = seconds or self.default_timeout
        start = time.time()
        info = {"elapsed": 0.0, "exceeded": False}
        try:
            yield info
        finally:
            elapsed = time.time() - start
            info["elapsed"] = elapsed
            if elapsed > seconds:
                info["exceeded"] = True
                raise TimeoutError(f"互校操作超过 {seconds} 秒（实际 {elapsed:.2f}s）")


__all__ = ["TimeoutGuard"]