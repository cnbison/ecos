"""Runtime API 6 核心 API —— v0.83 Kernel API 层.

对应 kernel-mapping §5 Runtime API:
  - estimate / update_belief / replay / evaluate / simulate / plan

风格: 纯函数 + kwargs (跟 StateEngine.replay/simulate 现有 v0.81 模式一致).
Runtime API 是旁路, web/api/belief.py 仍是主入口 (向后兼容).
"""

from .api import (
    estimate,
    update_belief,
    replay,
    evaluate,
    simulate,
    plan,
)

__status__ = "v0.83.0-d"

__all__ = [
    "estimate",
    "update_belief",
    "replay",
    "evaluate",
    "simulate",
    "plan",
]
