"""死锁避免子包——超时 + 优先级仲裁 + 降级.

对应 spec §5：
  - timeout.py（超时保护）
  - priority.py（优先级仲裁）—— Phase 5+（无竞争消息场景）
  - fallback.py（降级到单 Agent）
"""

from .fallback import SingleAgentFallback
from .timeout import TimeoutGuard

__all__ = ["TimeoutGuard", "SingleAgentFallback"]