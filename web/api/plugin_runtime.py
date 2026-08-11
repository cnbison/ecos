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

    v0.84.0-d: 接 1 subscriber (response_submitted).
    v0.85.0-b: 加 1 subscriber (request_calibration).
    v0.85.0-c: 加 1 subscriber (request_intervention) [TODO].
    v0.85.0-d: production activation (Flask startup 注册) [TODO].

    Usage:
        # 启动 (在 Flask app 启动时调一次)
        runtime = PluginRuntime(
            state_factory=_get_or_create_student,
            dual_orchestrator_factory=get_dual_orchestrator,
        )
        runtime.start()

        # 测试隔离
        runtime.stop()
    """

    def __init__(
        self,
        bus: Optional[Any] = None,
        state_factory: Optional[Callable[[str], Tuple[Any, Any]]] = None,
        dual_orchestrator_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self._bus = bus
        self._state_factory = state_factory or _default_state_factory
        # v0.85.0-b: dual_agent orchestrator factory (lazy import 避免循环)
        self._dual_orchestrator_factory = dual_orchestrator_factory or _default_dual_orchestrator_factory
        # v0.85.0-b: per-student calibration result dict (plugin 读 result 用)
        self._calibration_results: Dict[str, Any] = {}
        self._subscription_ids: List[str] = []
        self._started = False

    def start(self) -> None:
        """注册 subscriber 到 bus.

        v0.84.0-d: 注册 response_submitted.
        v0.85.0-b: 加注册 request_calibration.
        """
        if self._started:
            _log.warning("PluginRuntime.start: 已启动, 跳过重复 start")
            return

        bus = self._get_bus()
        # v0.84.0-d: response_submitted
        sub_id = bus.subscribe("response_submitted", self._handle_response_submitted)
        self._subscription_ids.append(sub_id)
        # v0.85.0-b: request_calibration
        sub_id = bus.subscribe("request_calibration", self._handle_request_calibration)
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
        self._calibration_results.clear()
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

    def _handle_request_calibration(self, event: Any) -> Any:
        """v0.85.0-b: Handle request_calibration event: delegate to orchestrator.process_observation.

        Subscriber reconstructs Observation from event.payload, calls
        orchestrator.process_observation, and stores CalibratedLCAResult in
        _calibration_results[student_id] for plugin (process_observation_for_student)
        to read after publish() returns (sync mode guarantees order).

        Args:
            event: LearningEvent (event_type="request_calibration", payload={problem_id, skill_id, correct, score, bloom_layer})

        Returns:
            CalibratedLCAResult. Also stored in self._calibration_results[student_id].
        """
        # Lazy imports to avoid circular deps at module load
        from ecos.cta.belief_engine import Observation
        from ecos.cta.belief_state import BloomLevel

        student_id = event.student_id
        payload = event.payload

        # Reconstruct Observation from payload
        bloom_layer = payload.get("bloom_layer", "L2")
        try:
            bloom_enum = BloomLevel(int(bloom_layer.replace("L", "")))
        except (ValueError, AttributeError):
            bloom_enum = BloomLevel.APPLY  # fallback (跟 web/api/dual_agent.py 一致)

        obs = Observation(
            problem_id=payload["problem_id"],
            skill_id=payload["skill_id"],
            correct=payload["correct"],
            score=payload["score"],
            bloom_level=bloom_enum,
            response_time_sec=0.0,
        )

        # v0.61.0: lazy load dual state (跟 web/api/dual_agent.py:process_observation_for_student 一致)
        from web.api.dual_agent import _load_dual_state_if_needed
        _load_dual_state_if_needed(student_id)

        # Get dual_agent orchestrator
        orch = self._dual_orchestrator_factory()

        # Process observation
        result = orch.process_observation(obs, student_id=student_id)

        # Store for plugin to read (sync mode: publish returns after handler completes)
        self._calibration_results[student_id] = result
        return result

    def get_last_calibration_result(self, student_id: str) -> Optional[Any]:
        """v0.85.0-b: Get last calibration result for student (called by plugin after publish).

        Returns:
            CalibratedLCAResult or None (no calibration ran yet).
        """
        return self._calibration_results.get(student_id)

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


def _default_dual_orchestrator_factory() -> Any:
    """v0.85.0-b: Default dual_agent orchestrator factory.

    Lazy import to avoid circular dep at module load.
    Returns DualAgentOrchestrator singleton instance.
    """
    from web.api.dual_agent import get_dual_orchestrator
    return get_dual_orchestrator()


# v0.85.0-b: Module-level PluginRuntime singleton (lazy init).
# web/api/dual_agent.py:process_observation_for_student 通过 get_plugin_runtime()
# 读取 subscriber 处理后的 CalibratedLCAResult.
_plugin_runtime_singleton: Optional[PluginRuntime] = None


def get_plugin_runtime() -> PluginRuntime:
    """v0.85.0-b: Get the module-level PluginRuntime singleton (lazy init).

    Plugin (process_observation_for_student) 调用 get_plugin_runtime() 读
    _calibration_results[student_id] (subscriber 写入的结果).

    Production activation: Flask startup 注册 PluginRuntime.start() (v0.85.0-d).
    """
    global _plugin_runtime_singleton
    if _plugin_runtime_singleton is None:
        _plugin_runtime_singleton = PluginRuntime()
    return _plugin_runtime_singleton


def reset_plugin_runtime() -> None:
    """v0.85.0-b: Reset module-level PluginRuntime singleton (test isolation)."""
    global _plugin_runtime_singleton
    _plugin_runtime_singleton = None
