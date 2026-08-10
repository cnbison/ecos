"""v0.84.0-b: Event Bus - in-process pub/sub for LearningEvent distribution.

kernel-mapping §1.2 Event Engine 收尾 (Bus 0% → 100%) + §2.4 Event 统一输入.

Scope (v0.84.0-b):
  - EventBus class (subscribe / publish / unsubscribe / get_subscribers / reset)
  - EventBusConfig (mode=sync/async, buffer_size, max_subscribers_per_topic)
  - 模块级 _default_bus singleton (懒加载, kwargs 注入覆盖)
  - 默认 sync mode (publish 同步调 handler); async mode 留 Phase 7+ (YAGNI)

Forward-compat (Phase 7+):
  - async mode: publish 推 queue, 后台 worker 消费
  - multi-process: redis / nats pub/sub bridge
  - Event filtering: handler 可订阅 topic + filter func

Per discussions/2026-08-11-v084-design.md §3.
"""
from .bus import (
    EventBus,
    EventBusConfig,
    get_default_bus,
    reset_default_bus,
)

__all__ = [
    "EventBus",
    "EventBusConfig",
    "get_default_bus",
    "reset_default_bus",
]
