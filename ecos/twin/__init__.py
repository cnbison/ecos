"""Twin Consistency Check — 跨 Profile 校验 (v0.86.0-b).

对应 12-kernel-mapping §2.1 Twin 一致性保证:
    "K mastery + Bloom L3 + TC 通过 一致性校验".

模块:
    - consistency.py: TwinConsistencyChecker + TwinConsistencyResult

触发时机: Runtime.plan 选 intervention 前 (per Bisen 决策 2026-08-11)
失败处理: 不阻断 plan, emit goal_changed event + log warning + 走 fallback
"""

from .consistency import (
    TwinConsistencyChecker,
    TwinConsistencyResult,
    get_default_checker,
    reset_default_checker,
)

__all__ = [
    "TwinConsistencyChecker",
    "TwinConsistencyResult",
    "get_default_checker",
    "reset_default_checker",
]
