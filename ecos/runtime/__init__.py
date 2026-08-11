"""Runtime API 6 核心 API —— v0.83 Kernel API 层.

对应 kernel-mapping §5 Runtime API:
  - estimate / update_belief / replay / evaluate / simulate / plan
  - v0.86.0-d: plan_goal_aware
  - v0.87.0-b: plan_motivation_aware
  - v0.88.0-b: plan_domain_aware

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
    plan_goal_aware,
    plan_motivation_aware,
    plan_domain_aware,
)

__status__ = "v0.88.0-b"

__all__ = [
    "estimate",
    "update_belief",
    "replay",
    "evaluate",
    "simulate",
    "plan",
    "plan_goal_aware",
    "plan_motivation_aware",
    "plan_domain_aware",
]
