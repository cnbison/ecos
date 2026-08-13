"""v0.84.0-d: PluginRuntime - Plugin SDK 雏形.

kernel-mapping §6 Plugin SDK 边界: "Plugin 不调用 Twin, Plugin 只能产生 Event".

v0.84.0-d 范围:
  - 1 endpoint (/api/answer) 改造为 Plugin 路径
  - PluginRuntime 包装 Runtime API 作为 EventBus subscriber
  - 验证 "Plugin 只产生 Event" 原则
  - 留 /api/judge / /api/dual_agent / /api/lca 给 v0.85

v0.91.0-b 范围:
  - 加 4 subscribers (hint_requested / idle_detected / goal_changed / reflection_completed)
  - 4 handlers 调 LCAEngine.append_human_feedback (Twin → Human Twin 抽象)
  - subscription_count: 3 → 7 (v0.85 production activation 兼容)

设计:
  - PluginRuntime.start() 注册 subscriber 到 EventBus
  - subscriber handler 从 event.payload 重建 Observation / HumanFeedbackEntry
  - 调用 Runtime.update_belief / LCAEngine.append_human_feedback (委托 + 持久化)
  - state_factory 是 web/api/belief.py:_get_or_create_student (共享 _STUDENT_STATES dict)

Per discussions/2026-08-11-v084-design.md §5 + discussions/2026-08-12-v091-design.md §3.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

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
    v0.91.0-b: 加 4 subscribers (hint_requested / idle_detected / goal_changed / reflection_completed)
                - 4 frontend stub endpoint (v0.85.0-d 已 production activation, 但仅
                  produce event → bus.publish, 没 Runtime subscriber). v0.91.0-b 接通,
                  Plugin SDK 4 endpoint 走 LCAEngine.append_human_feedback → CognitiveTwinAgent
                  append_human_feedback (allowlisted mutation, FUNC_ALLOWLIST += "append_human_feedback").
    v0.93.0-b: 加 1 subscriber (pomdp_diagnostic_updated)
                - Plugin (frontend dashboard) 触发 pomdp_diagnostic_updated event → PluginRuntime
                  委派 Runtime.diagnose_pomdp(student_id) → 返 POMDPDiagnostic 写入
                  _diagnostic_results[student_id] 给 Plugin 读取 (跟 _intervention_results /
                  _calibration_results 完全 parallel pattern). subscription_count: 7 → 8.
    v0.94.0-b: PluginRegistry DI 集成 (Phase 7+ 抽象推演 #7 — 第一方 plugin 库 Kernel-only SDK)
                - 加 plugin_registry_factory kwarg (DI 注入 PluginRegistry, 默认 None → 从 singleton 拉)
                - start() 在 8 built-in subscriber 注册后, 调 PluginRegistry.subscribe_all(bus)
                  挂载 first-party plugin (HintFatiguePlugin / ParentEngagementPlugin / TeacherProgressPlugin)
                - stop() 调 PluginRegistry.unsubscribe_all(bus) 反挂载
                - subscription_count 维持 8 (built-in) — Plugin registry 内部自己 track subscription_ids
                  互不干扰. Plugin registry 是 additional layer, 不是替换 built-in.

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
        lca_engine_factory: Optional[Callable[[], Any]] = None,
        plugin_registry_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self._bus = bus
        self._state_factory = state_factory or _default_state_factory
        # v0.85.0-b: dual_agent orchestrator factory (lazy import 避免循环)
        self._dual_orchestrator_factory = dual_orchestrator_factory or _default_dual_orchestrator_factory
        # v0.85.0-c: LCAEngine factory (lazy import 避免循环)
        self._lca_engine_factory = lca_engine_factory or _default_lca_engine_factory
        # v0.94.0-b: PluginRegistry factory (DI 注入, 跟 DomainRegistry v0.88.0-a singleton 模式一致)
        self._plugin_registry_factory = plugin_registry_factory or _default_plugin_registry_factory
        # v0.85.0-b: per-student calibration result dict (plugin 读 result 用)
        self._calibration_results: Dict[str, Any] = {}
        # v0.85.0-c: per-student intervention result dict
        self._intervention_results: Dict[str, Any] = {}
        # v0.93.0-b: per-student POMDP diagnostic result dict (Plugin dashboard 读 result 用)
        self._diagnostic_results: Dict[str, Any] = {}
        self._subscription_ids: List[str] = []
        self._started = False

    def start(self) -> None:
        """注册 subscriber 到 bus.

        v0.84.0-d: 注册 response_submitted.
        v0.85.0-b: 加注册 request_calibration.
        v0.85.0-c: 加注册 request_intervention.
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
        # v0.85.0-c: request_intervention
        sub_id = bus.subscribe("request_intervention", self._handle_request_intervention)
        self._subscription_ids.append(sub_id)
        # v0.91.0-b: 4 frontend stub endpoint 接通 (hint / idle / goal_change / reflection)
        #   handler 调 LCAEngine.append_human_feedback → CognitiveTwinAgent.append_human_feedback
        #   (allowlisted mutation, FUNC_ALLOWLIST += "append_human_feedback")
        for event_type, handler in (
            ("hint_requested", self._handle_hint_requested),
            ("idle_detected", self._handle_idle_detected),
            ("goal_changed", self._handle_goal_changed),
            ("reflection_completed", self._handle_reflection_completed),
        ):
            sub_id = bus.subscribe(event_type, handler)
            self._subscription_ids.append(sub_id)
        # v0.93.0-b: 第 8 subscriber pomdp_diagnostic_updated
        #   handler 调 Runtime.diagnose_pomdp(student_id) → 返 POMDPDiagnostic
        #   写入 _diagnostic_results[student_id] 给 Plugin dashboard 读
        sub_id = bus.subscribe(
            "pomdp_diagnostic_updated", self._handle_pomdp_diagnostic_updated,
        )
        self._subscription_ids.append(sub_id)
        # v0.94.0-b: PluginRegistry 挂载 first-party plugin (HintFatigue / ParentEngagement / TeacherProgress)
        #   PluginRegistry.subscribe_all() 内部调 plugin.enable() + bus.subscribe(plugin.on_event)
        #   返 Dict[plugin_name, List[sub_id]], PluginRegistry 内部 track _subscription_ids 供 unsubscribe 用
        #   subscription_count (built-in) 维持 8 — Plugin registry 是 additional layer
        registry = self._plugin_registry_factory()
        try:
            registry.subscribe_all(bus)
        except Exception:
            _log.warning(
                "PluginRuntime.start: PluginRegistry.subscribe_all failed",
                exc_info=True,
            )
        self._started = True
        _log.info(
            "PluginRuntime 启动 (bus=%s, built_in_subscriptions=%d, registry_plugins=%s)",
            type(bus).__name__,
            len(self._subscription_ids),
            registry.list_names(),
        )

    def stop(self) -> None:
        """取消所有 subscriber (test isolation + 重新配置)."""
        bus = self._get_bus()
        for sub_id in self._subscription_ids:
            bus.unsubscribe(sub_id)
        self._subscription_ids.clear()
        self._calibration_results.clear()
        self._intervention_results.clear()
        # v0.93.0-b: 清理 _diagnostic_results
        self._diagnostic_results.clear()
        # v0.94.0-b: 反挂载 first-party plugin (PluginRegistry.unsubscribe_all)
        try:
            registry = self._plugin_registry_factory()
            registry.unsubscribe_all(bus)
        except Exception:
            _log.warning(
                "PluginRuntime.stop: PluginRegistry.unsubscribe_all failed",
                exc_info=True,
            )
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

    def _handle_request_intervention(self, event: Any) -> Any:
        """v0.85.0-c: Handle request_intervention event: delegate to Runtime.plan.

        Subscriber reconstructs CTAInput from state_factory (跟 belief.py 共享
        _STUDENT_STATES dict), calls Runtime.plan(student_id, audience, cta_input,
        lca_engine), and stores LCAResult in _intervention_results[student_id]
        for plugin (select_intervention) to read after publish() returns.

        Args:
            event: LearningEvent (event_type="request_intervention", payload={audience})

        Returns:
            LCAResult. Also stored in self._intervention_results[student_id].
        """
        # Lazy imports to avoid circular deps at module load
        from ecos.lca.cta_input import CTAInput
        from ecos.runtime.api import plan as runtime_plan

        student_id = event.student_id
        payload = event.payload
        audience = payload.get("audience", "student")

        # Get state via state_factory (shares _STUDENT_STATES dict with belief.py)
        _, state = self._state_factory(student_id)

        # Construct CTAInput (跟 web/api/lca.py:select_intervention 一致)
        cta_input = CTAInput(student_id=student_id, belief_state=state)

        # Get LCAEngine + Runtime.plan
        lca_engine = self._lca_engine_factory()
        result = runtime_plan(
            student_id=student_id,
            audience=audience,
            cta_input=cta_input,
            lca_engine=lca_engine,
        )

        # v0.57.0: save LCA state after select (跟 web/api/lca.py:select_intervention 一致)
        # lazy load + save 在 Runtime.plan 内部调用 (Runtime.plan → lca.select_intervention → lca._save_lca_state)
        # 这里额外 save 一次保证 Plugin 路径跟 legacy 路径行为一致
        try:
            from web.api.lca import _save_lca_state
            _save_lca_state(student_id)
        except Exception:
            _log.warning(
                "_save_lca_state 失败 (sid=%s), Plugin 路径不影响主响应",
                student_id, exc_info=True,
            )

        # Store for plugin to read
        self._intervention_results[student_id] = result
        return result

    # ── v0.91.0-b: 4 frontend stub subscribers (Twin → Human Twin 抽象) ──

    def _handle_human_feedback_event(
        self,
        event: Any,
        event_type: str,
    ) -> Optional[Any]:
        """v0.91.0-b: 共用 helper: LearningEvent → HumanFeedbackEntry → LCAEngine.append_human_feedback.

        Plugin SDK 4 endpoint (hint_requested / idle_detected / goal_changed / reflection_completed)
        都走同一路径, 区别仅在 event_type (已经包含在 event.event_type).

        Args:
            event: LearningEvent (event_type 必须是 4 HUMAN_FEEDBACK_EVENT_TYPES 之一)
            event_type: str (冗余参数, 主要为 logging 用)

        Returns:
            HumanFeedbackEntry (新建). 不返回 CognitiveTwinAgent (LCAEngine 内部维护).

        防御性自检 [1]: handler exception _log.warning 不 raise (per v0.84.0-b EventBus 设计).
        """
        from ecos.cta.cognitive_twin import HumanFeedbackEntry

        student_id = event.student_id
        try:
            entry = HumanFeedbackEntry.from_event(event)
        except (ValueError, KeyError, AttributeError) as e:
            _log.warning(
                "PluginRuntime._handle_human_feedback_event (%s): HumanFeedbackEntry.from_event 失败 "
                "(sid=%s, err=%s), skip",
                event_type, student_id, e, exc_info=True,
            )
            return None

        try:
            lca_engine = self._lca_engine_factory()
            # 调 state_factory 拿 state for lazy init cognitive_twin (跟 _handle_response_submitted 同 pattern)
            _, state = self._state_factory(student_id)
            lca_engine.append_human_feedback(student_id, entry, state=state)
        except Exception as e:  # noqa: BLE001
            _log.warning(
                "PluginRuntime._handle_human_feedback_event (%s): LCAEngine.append_human_feedback 失败 "
                "(sid=%s, err=%s), skip (handler 不破坏 bus)",
                event_type, student_id, e, exc_info=True,
            )
            return None

        return entry

    def _handle_hint_requested(self, event: Any) -> Any:
        """v0.91.0-b: hint_requested → CognitiveTwinAgent.append_human_feedback.

        Student 主动请求 hint → LCA 后续 select 时 ExperimentDesigner 可降难度 (c 阶段消费).
        """
        return self._handle_human_feedback_event(event, "hint_requested")

    def _handle_idle_detected(self, event: Any) -> Any:
        """v0.91.0-b: idle_detected → CognitiveTwinAgent.append_human_feedback.

        Frontend 检测 N 秒无操作 → LCA 后续 select 时 ExperimentDesigner 可调整 itype (c 阶段消费).
        """
        return self._handle_human_feedback_event(event, "idle_detected")

    def _handle_goal_changed(self, event: Any) -> Any:
        """v0.91.0-b: goal_changed → CognitiveTwinAgent.append_human_feedback.

        Student 切换学习目标 → LCA 后续 select 时考虑目标调整后巩固 (c 阶段消费).
        """
        return self._handle_human_feedback_event(event, "goal_changed")

    def _handle_reflection_completed(self, event: Any) -> Any:
        """v0.91.0-b: reflection_completed → CognitiveTwinAgent.append_human_feedback.

        Student 完成反思 → LCA 后续 select 时 ExperimentDesigner 可 PRACTICE 巩固 + reward boost (c 阶段).
        """
        return self._handle_human_feedback_event(event, "reflection_completed")

    # ── v0.93.0-b: 第 8 subscriber — pomdp_diagnostic_updated (POMDP T/R 后验可视化) ──

    def _handle_pomdp_diagnostic_updated(self, event: Any) -> Any:
        """v0.93.0-b: pomdp_diagnostic_updated → Runtime.diagnose_pomdp.

        Plugin (frontend dashboard) 触发 pomdp_diagnostic_updated event → handler
        委派 Runtime.diagnose_pomdp(student_id, lca_engine=...) → 返 POMDPDiagnostic →
        写入 _diagnostic_results[student_id] 给 Plugin 读.

        Args:
            event: LearningEvent (event_type="pomdp_diagnostic_updated", payload={})

        Returns:
            POMDPDiagnostic (新建). 不返 LCAEngine (LCAEngine 内部维护缓存).

        防御性自检 [1]: handler exception _log.warning 不 raise (per v0.84.0-b EventBus 设计).

        v0.93.0-b: 用 _lca_engine_factory 注入 lca_engine kwarg, 避免 Runtime 默认
                  singleton 路径覆盖 (跟 _handle_request_intervention 完全 parallel pattern).
        """
        from ecos.runtime.api import diagnose_pomdp

        student_id = event.student_id
        try:
            lca_engine = self._lca_engine_factory()
            diagnostic = diagnose_pomdp(student_id=student_id, lca_engine=lca_engine)
            self._diagnostic_results[student_id] = diagnostic
            return diagnostic
        except Exception as e:  # noqa: BLE001
            _log.warning(
                "PluginRuntime._handle_pomdp_diagnostic_updated: diagnose_pomdp 失败 "
                "(sid=%s, err=%s), skip",
                student_id, e, exc_info=True,
            )
            return None

    def get_last_calibration_result(self, student_id: str) -> Optional[Any]:
        """v0.85.0-b: Get last calibration result for student (called by plugin after publish).

        Returns:
            CalibratedLCAResult or None (no calibration ran yet).
        """
        return self._calibration_results.get(student_id)

    def get_last_intervention_result(self, student_id: str) -> Optional[Any]:
        """v0.85.0-c: Get last intervention result for student (called by plugin after publish).

        Returns:
            LCAResult or None (no intervention ran yet).
        """
        return self._intervention_results.get(student_id)

    def get_last_diagnostic_result(self, student_id: str) -> Optional[Any]:
        """v0.93.0-b: Get last POMDP diagnostic result for student (called by plugin after publish).

        Returns:
            POMDPDiagnostic or None (no diagnostic ran yet / non-POMDP policy).
        """
        return self._diagnostic_results.get(student_id)

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


def _default_lca_engine_factory() -> Any:
    """v0.85.0-c: Default LCAEngine factory.

    Lazy import to avoid circular dep at module load.
    Returns LCAEngine singleton instance.
    """
    from web.api.lca import get_lca_engine
    return get_lca_engine()


def _default_plugin_registry_factory() -> Any:
    """v0.94.0-b: Default PluginRegistry factory.

    Lazy import to avoid circular dep at module load.
    Returns PluginRegistry singleton instance (跟 DomainRegistry v0.88.0-a 完全 parallel).
    """
    from ecos.plugins.registry import get_default_registry
    return get_default_registry()


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
