"""v0.84.0-b: EventBus - in-process pub/sub for LearningEvent distribution.

kernel-mapping §1.2 Event Engine Bus (0% → 100%) + §2.4 Event 统一输入.

设计原则:
  - 简单: subscribe(topic, handler) → sub_id, publish(topic, event) → success_count
  - 默认 sync: publish 同步调所有 subscriber handler
  - 防御性: handler raise 不阻断其他 handler (catch + _log.warning + continue)
  - 测试隔离: reset_default_bus() + kwargs 注入 default bus
  - Forward-compat: async mode 留 Phase 7+ (YAGNI for v0.84.0-b)

NOT in scope for v0.84.0-b:
  - async mode (Phase 7+)
  - 跨进程 bus (Phase 7+)
  - Event filtering (Phase 7+)

Per discussions/2026-08-11-v084-design.md §3.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

_log = logging.getLogger(__name__)


@dataclass
class EventBusConfig:
    """EventBus configuration.

    Attributes:
        mode: "sync" (default, publish 同步调 handler) or "async" (Phase 7+).
        buffer_size: for async mode (Phase 7+), max events in queue.
        max_subscribers_per_topic: hard cap per topic (防御性, 防止内存泄漏).
    """

    mode: str = "sync"
    buffer_size: int = 1000
    max_subscribers_per_topic: int = 10


class EventBus:
    """In-process pub/sub for LearningEvent distribution.

    Usage:
        bus = EventBus()
        sub_id = bus.subscribe("observation", my_handler)
        success = bus.publish("observation", event)  # 同步调 my_handler(event)
        bus.unsubscribe(sub_id)

    Default sync mode: publish() invokes each handler synchronously. Handler
    exceptions are caught and logged (defensive), but don't block other handlers.

    Forward-compat (Phase 7+): async mode (queue + worker) and cross-process
    bridges (Redis/NATS). v0.84.0-b only implements sync.

    Critical invariants:
      - subscribe() always returns a sub_id (even if max_subscribers reached,
        to keep caller's reference valid; publish() will silently skip).
      - unsubscribe() returns False (not raise) for unknown sub_id.
      - publish() returns int (successful handler count), never raises.
    """

    def __init__(self, config: Optional[EventBusConfig] = None) -> None:
        self._subscribers: Dict[str, List[Tuple[str, Callable[[Any], None]]]] = {}
        self._config = config or EventBusConfig()

    # ── API ─────────────────────────────────────────────────────────────────

    def subscribe(
        self,
        topic: str,
        handler: Callable[[Any], None],
    ) -> str:
        """Register handler for topic, return subscription_id.

        Args:
            topic: event topic (e.g. "observation", "calibration", "response_submitted").
                   Topics are arbitrary strings; no schema validation.
            handler: callable(event) -> None. Receives the event published to topic.
                     Handler should NOT raise; exceptions are caught and logged.

        Returns:
            subscription_id (str, "sub_xxxxxxxxxxxx"). Use to unsubscribe.

        Note:
            If topic already has max_subscribers_per_topic handlers, the new
            subscription is recorded but won't be invoked on publish().
            _log.warning is emitted.
        """
        sub_id = f"sub_{uuid.uuid4().hex[:12]}"
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        if len(self._subscribers[topic]) >= self._config.max_subscribers_per_topic:
            _log.warning(
                "EventBus: max_subscribers_per_topic=%d reached for topic %s, "
                "subscription %s recorded but won't be invoked",
                self._config.max_subscribers_per_topic, topic, sub_id,
            )
        self._subscribers[topic].append((sub_id, handler))
        return sub_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """Remove handler by subscription_id.

        Args:
            subscription_id: the id returned by subscribe().

        Returns:
            True if removed, False if not found (defensive, never raises).
        """
        for topic, handlers in self._subscribers.items():
            for i, (sid, _) in enumerate(handlers):
                if sid == subscription_id:
                    handlers.pop(i)
                    return True
        return False

    def publish(self, topic: str, event: Any) -> int:
        """Publish event to all subscribers of topic (sync mode).

        Args:
            topic: event topic. Subscribers registered for this exact topic are invoked.
            event: event payload (typically a LearningEvent). Passed as-is to handlers.

        Returns:
            Number of handlers successfully invoked (excludes failed handlers).

        Defensive:
            Handler exceptions are caught + _log.warning + skipped. publish()
            never raises, ensuring EventBus is fail-safe for Plugin SDK use.

        Note:
            sync mode: handlers run in publish()'s call stack. Phase 7+ async
            mode will enqueue + return immediately.
        """
        if self._config.mode != "sync":
            _log.warning(
                "EventBus: async mode not yet implemented (v0.84.0-b scope), "
                "falling back to sync for topic %s",
                topic,
            )

        handlers = self._subscribers.get(topic, [])
        success = 0
        for sub_id, handler in handlers:
            try:
                handler(event)
                success += 1
            except Exception:
                _log.warning(
                    "EventBus: handler %s for topic %s raised, skipping",
                    sub_id, topic, exc_info=True,
                )
        return success

    def get_subscribers(self, topic: str) -> List[Callable[[Any], None]]:
        """Get list of handlers registered for topic (test/debug).

        Returns a copy; modifying the returned list doesn't affect the bus.
        """
        return [h for _, h in self._subscribers.get(topic, [])]

    def get_topic_count(self, topic: str) -> int:
        """Get number of subscribers for topic."""
        return len(self._subscribers.get(topic, []))

    def reset(self) -> None:
        """Clear all subscribers (test isolation)."""
        self._subscribers.clear()

    @property
    def mode(self) -> str:
        """Current mode: 'sync' (Phase 7+: 'async')."""
        return self._config.mode


# ── Module-level singleton ─────────────────────────────────────────────────

_default_bus: Optional[EventBus] = None


def get_default_bus() -> EventBus:
    """Get the module-level default EventBus (lazy init, kwargs-injectable).

    Production callers should use this; tests can construct EventBus() directly
    for isolation or pass a custom bus via kwargs.

    Pattern matches ecos/runtime/api.py:_default_belief_engine etc.
    """
    global _default_bus
    if _default_bus is None:
        _default_bus = EventBus()
    return _default_bus


def reset_default_bus() -> None:
    """Reset module-level singleton (test isolation).

    After reset, get_default_bus() constructs a fresh EventBus on next call.
    Use this in test fixtures (autouse) to prevent cross-test contamination.
    """
    global _default_bus
    _default_bus = None
