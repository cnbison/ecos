"""v0.84.0-d: PluginRuntime - Plugin SDK 雏形.

kernel-mapping §6 Plugin SDK 边界: "Plugin 不调用 Twin, Plugin 只能产生 Event".

v0.84.0-d 范围:
  - 1 endpoint (/api/answer) 改造为 Plugin 路径
  - PluginRuntime 包装 Runtime API 作为 EventBus subscriber
  - 验证 "Plugin 只产生 Event" 原则
  - 留 /api/judge / /api/dual_agent / /api/lca 给 v0.85

设计:
  - PluginRuntime.start() 注册 subscriber 到 EventBus
  - subscriber handler 从 event.payload 重建 Observation
  - 调用 Runtime.update_belief (委托 BeliefEngine.update + 持久化)
  - state_factory 是 web/api/belief.py:_get_or_create_student (共享 _STUDENT_STATES dict)

Per discussions/2026-08-11-v084-design.md §5.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, List, Optional, Tuple

_log = logging.getLogger(__name__)


class PluginRuntime:
    """v0.84.0-d: Plugin SDK 雏形 - Runtime API as EventBus subscriber.

    注册 handler 到 EventBus 接收 Plugin event, 委托 Runtime API 处理.

    Plugin 原则 (kernel-mapping §6):
      - Plugin (web/api/) 不直接调 BeliefEngine.update
      - Plugin 只构造 event + publish 到 bus
      - PluginRuntime 作为 Runtime 端 subscriber, 接收 event 后调 Runtime.update_belief

    v0.84.0-d: 只接 1 subscriber (response_submitted). /api/judge
    / /api/dual_agent / /api/lca 留 v0.85+ 接.

    Usage:
        # 启动 (在 Flask app 启动时调一次)
        runtime = PluginRuntime(state_factory=_get_or_create_student)
        runtime.start()

        # 测试隔离
        runtime.stop()
    """

    def __init__(
        self,
        bus: Optional[Any] = None,
        state_factory: Optional[Callable[[str], Tuple[Any, Any]]] = None,
    ) -> None:
        self._bus = bus
        self._state_factory = state_factory or _default_state_factory
        self._subscription_ids: List[str] = []
        self._started = False

    def start(self) -> None:
        """注册 subscriber 到 bus.

        v0.84.0-d: 只注册 response_submitted. 其它 event_type 留 v0.85+.
        """
        if self._started:
            _log.warning("PluginRuntime.start: 已启动, 跳过重复 start")
            return

        bus = self._get_bus()
        # v0.84.0-d 唯一 subscriber
        sub_id = bus.subscribe("response_submitted", self._handle_response_submitted)
        self._subscription_ids.append(sub_id)
        self._started = True
        _log.info(
            "PluginRuntime 启动 (bus=%s, subscriptions=%d)",
            type(bus).__name__, len(self._subscription_ids),
        )

    def stop(self) -> None:
        """取消所有 subscriber (test isolation + 重新配置)."""
        bus = self._get_bus()
        for sub_id in self._subscription_ids:
            bus.unsubscribe(sub_id)
        self._subscription_ids.clear()
        self._started = False
        _log.info("PluginRuntime 停止")

    def _get_bus(self) -> Any:
        """Lazy get default bus (if not injected)."""
        if self._bus is None:
            from ecos.event import get_default_bus
            self._bus = get_default_bus()
        return self._bus

    def _handle_response_submitted(self, event: Any) -> Any:
        """Handle response_submitted event: delegate to Runtime.update_belief.

        Args:
            event: LearningEvent (event_type="response_submitted", payload=Observation.to_dict())

        Returns:
            BeliefState (updated). Mutations are in-place; same object as state_factory returned.
        """
        # Lazy imports to avoid circular deps at module load
        from ecos.cta.belief_engine import Observation
        from ecos.runtime.api import update_belief

        # Reconstruct Observation from event.payload
        # student_id: 优先从 event.student_id 拿 (factory 用它定位 state)
        student_id = event.student_id
        obs = Observation.from_dict(event.payload)

        # Get/create state via state_factory (shares _STUDENT_STATES dict with web/api/belief.py)
        engine, state = self._state_factory(student_id)

        # Delegate to Runtime.update_belief (which calls engine.update internally)
        # - state kwarg: 复用已有 state 对象 (跟 web/api/belief.py 同一引用)
        # - log_event=False: FeatureExtractor already emit response_submitted, 不重复
        updated_state = update_belief(
            student_id=student_id,
            evidence=obs,
            belief_engine=engine,
            state=state,
            log_event=False,
        )
        return updated_state

    @property
    def is_started(self) -> bool:
        """Whether start() has been called."""
        return self._started

    @property
    def subscription_count(self) -> int:
        """Number of active subscriptions."""
        return len(self._subscription_ids)


# ── Module-level helpers ────────────────────────────────────────────────────

def _default_state_factory(student_id: str) -> Tuple[Any, Any]:
    """Default state_factory: delegate to web/api/belief.py:_get_or_create_student.

    Lazy import to avoid circular dep at module load.
    Returns (engine, state) tuple.
    """
    from web.api.belief import _get_or_create_student
    student = _get_or_create_student(student_id)
    return student["engine"], student["state"]
