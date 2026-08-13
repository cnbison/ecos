"""ECOS Plugin SDK 5 Use Case 示例 (v0.91.0-e, v0.94.0-c 升级).

对应设计: docs/plugin_sdk.md §八 + docs/plugin_library.md §5.

Use Case:
  1. 教师后台: 订阅 reflection_completed → 读 human_feedback_trajectory → 生成学生反思分析
  2. 家长 dashboard: 订阅 goal_changed → 读 human_feedback_trajectory → 显示学习目标调整历史
  3. 提示疲劳检测: 订阅 hint_requested → 计数 → 提示教师学生可能过度依赖 hint
     (v0.94.0-c 升级: 走 HintFatiguePlugin SDK Plugin ABC, 不再是内联 handler)
  4. 走神提醒: 订阅 idle_detected → 计数 → 提示教师学生可能需要干预
  5. 深度反思分析: 订阅 reflection_completed → LLM 分析 reflection_text → 写入 cognitive_twin

Plugin 原则 (per docs/plugin_sdk.md §一):
  - Plugin 不调用 Twin (BeliefEngine.update / LCAEngine.select_intervention)
  - Plugin 只产生 Event (LearningEvent) + 订阅 EventBus topic
  - Runtime 是 sole entry (PluginRuntime 调 Runtime API)
  - v0.94+ 第一方 plugin 走 SDK Plugin ABC (HintFatiguePlugin 等), 走 PluginRegistry 注册

不变量:
  - 任何 mutation 走 allowlist (FUNC_ALLOWLIST += CognitiveTwinAgent.append_human_feedback)
  - 不直接 state.X = value (防御性自检 [8] hard block)
  - handler 异常 _log.warning 不 raise (防御性自检 [1])

本文件不直接执行, 仅作为 Plugin SDK 使用模板. 真集成请在 web/api/ 子模块中订阅.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

# v0.91.0-a: CognitiveTwinAgent + HumanFeedbackEntry 数据结构
from ecos.cta.cognitive_twin import (
    CognitiveTwinAgent,
    HUMAN_FEEDBACK_EVENT_TYPES,
    HumanFeedbackEntry,
)
from ecos.cta.event_log import LearningEvent, LearningEventType
from ecos.event import EventBus, get_default_bus
# v0.94.0-c: 第一方 plugin SDK (HintFatiguePlugin 替代内联 hint_fatigue handler)
from ecos.plugins.first_party import HintFatiguePlugin

_log = logging.getLogger(__name__)


# ── Use Case 1: 教师后台 reflection_completed 反思分析 ──────────────────────


def use_case_teacher_reflection_analysis(
    bus: EventBus,
    lca_engine: Any,
) -> str:
    """Use Case 1: 教师后台 reflection_completed 反思分析.

    订阅 reflection_completed topic, 读 human_feedback_trajectory, 生成反思摘要.
    Plugin 调 CognitiveTwinAgent.append_human_feedback (allowlisted mutation).
    """
    subscription_id = bus.subscribe("reflection_completed", _teacher_reflection_handler)

    def _teacher_reflection_handler(event: LearningEvent) -> None:
        """Teacher 反思分析 handler: 读 LCAEngine._cognitive_twin[sid].human_feedback."""
        try:
            student_id = event.student_id
            # 1) Plugin 构造 HumanFeedbackEntry (不调 mutation)
            entry = HumanFeedbackEntry.from_event(event)
            # 2) Plugin 委托 LCAEngine.append_human_feedback (allowlisted mutation)
            #    (实际生产环境: 由 PluginRuntime._handle_reflection_completed 接管,
            #     本示例演示 Plugin 直接订阅时的等效路径)
            state = _get_or_create_belief_state(student_id)
            lca_engine.append_human_feedback(student_id, entry, state=state)
            # 3) Plugin 读 cognitive_twin 派生分析
            twin: Optional[CognitiveTwinAgent] = lca_engine._cognitive_twin.get(student_id)
            if twin is not None:
                reflection_count = twin.human_feedback.count_by_type("reflection_completed")
                _log.info(
                    "教师反思分析 (sid=%s): reflection_completed 累积 %d 次",
                    student_id, reflection_count,
                )
        except Exception:
            _log.warning("Teacher reflection handler 异常, skip", exc_info=True)

    return subscription_id


def _get_or_create_belief_state(student_id: str) -> Any:
    """Helper to get BeliefState (生产环境走 web/api/belief.py:_get_or_create_student).

    示例 stub, 返回 None (append_human_feedback state=None 时 graceful skip).
    """
    return None


# ── Use Case 2: 家长 dashboard goal_changed 目标调整历史 ──────────────────


def use_case_parent_goal_dashboard(bus: EventBus, lca_engine: Any) -> str:
    """Use Case 2: 家长 dashboard goal_changed 目标调整历史.

    订阅 goal_changed topic, 读 human_feedback_trajectory 显示目标调整序列.
    """
    subscription_id = bus.subscribe("goal_changed", _parent_goal_handler)

    def _parent_goal_handler(event: LearningEvent) -> None:
        """Parent dashboard handler: 读 goal_changed 序列."""
        try:
            student_id = event.student_id
            # 1) Plugin 构造 HumanFeedbackEntry
            entry = HumanFeedbackEntry.from_event(event)
            state = _get_or_create_belief_state(student_id)
            lca_engine.append_human_feedback(student_id, entry, state=state)
            # 2) 读 cognitive_twin 显示目标调整历史
            twin: Optional[CognitiveTwinAgent] = lca_engine._cognitive_twin.get(student_id)
            if twin is not None:
                goal_changes = twin.human_feedback.last_n(20)  # 最近 20 条
                goal_change_entries = [
                    e for e in goal_changes
                    if e.event_type == "goal_changed"
                ]
                _log.info(
                    "家长 dashboard (sid=%s): 最近 %d 次目标调整",
                    student_id, len(goal_change_entries),
                )
        except Exception:
            _log.warning("Parent goal handler 异常, skip", exc_info=True)

    return subscription_id


# ── Use Case 3: 提示疲劳检测 (hint_requested > 5) ─────────────────────────


def use_case_hint_fatigue_detection(bus: EventBus, lca_engine: Any) -> Optional[str]:
    """Use Case 3: 提示疲劳检测 (hint_requested > 5).

    v0.94.0-c 升级: 走 SDK HintFatiguePlugin (Plugin ABC 继承 + PluginRegistry 注册),
    不再是内联 handler. Plugin 内部 per-student 计数 + 阈值告警 (跟原 use case 行为一致).

    Plugin 走 PluginRuntime.subscribe_all 路径挂载, 跟 PluginRuntime built-in 8 subscriber 解耦.
    真正挂载到 bus 由 PluginRuntime.start() 触发 (调 registry.subscribe_all).

    Returns:
        Optional[str]: subscription_id. v0.94+ 走 PluginRegistry 路径后,
        实际 sub_id 由 PluginRuntime 统一管理, 本函数返 None.
        兼容老调用方 signature (Optional[str] 替代 str).
    """
    # 注册 HintFatiguePlugin 到 default singleton registry (一次性, PluginRuntime.start 时挂载)
    from ecos.plugins.registry import get_default_registry, PluginRegistry
    registry: PluginRegistry = get_default_registry()
    if not registry.has("hint_fatigue"):
        registry.register(HintFatiguePlugin())
    # PluginRuntime.start() 调 registry.subscribe_all(bus) 时, HintFatiguePlugin 会自动
    # enable + bus.subscribe("hint_requested", plugin.on_event). 这里返 None 表示
    # subscription_id 由 PluginRuntime 统一管理, 不返具体 sub_id.
    return None


# ── Use Case 4: 走神提醒 (idle_detected > 3) ───────────────────────────────


def use_case_idle_reminder(bus: EventBus, lca_engine: Any) -> str:
    """Use Case 4: 走神提醒 (idle_detected > 3).

    订阅 idle_detected topic, 计数 → 当 idle > 3 时提示教师学生可能需要干预.
    """
    subscription_id = bus.subscribe("idle_detected", _idle_reminder_handler)

    def _idle_reminder_handler(event: LearningEvent) -> None:
        """Idle reminder handler: 计数 idle_detected → 触发 alert."""
        try:
            student_id = event.student_id
            entry = HumanFeedbackEntry.from_event(event)
            state = _get_or_create_belief_state(student_id)
            lca_engine.append_human_feedback(student_id, entry, state=state)
            twin: Optional[CognitiveTwinAgent] = lca_engine._cognitive_twin.get(student_id)
            if twin is not None:
                idle_count = twin.human_feedback.count_by_type("idle_detected")
                if idle_count > 3:
                    _log.warning(
                        "走神提醒 (sid=%s): idle_detected=%d > 3, "
                        "学生可能走神, 建议推送互动干预",
                        student_id, idle_count,
                    )
        except Exception:
            _log.warning("Idle reminder handler 异常, skip", exc_info=True)

    return subscription_id


# ── Use Case 5: 深度反思分析 (reflection_completed → LLM 分析) ──────────────


def use_case_deep_reflection_analysis(bus: EventBus, lca_engine: Any, llm_client: Any = None) -> str:
    """Use Case 5: 深度反思分析 (reflection_completed → LLM 分析 reflection_text).

    订阅 reflection_completed topic, LLM 分析 reflection_text → 写入 cognitive_twin.
    (注: LLM 分析结果是 hint, 不直接 mutate state, 仅 emit 学习策略建议)
    """
    subscription_id = bus.subscribe("reflection_completed", _deep_reflection_handler)

    def _deep_reflection_handler(event: LearningEvent) -> None:
        """Deep reflection handler: LLM 分析 reflection_text → emit 学习策略建议."""
        try:
            student_id = event.student_id
            entry = HumanFeedbackEntry.from_event(event)
            state = _get_or_create_belief_state(student_id)
            lca_engine.append_human_feedback(student_id, entry, state=state)
            # 注: LLM 分析是副作用, 不 mutate state. 输出建议写到 event_log
            # 或 emit 新的 goal_changed event, 让下游 LCA 路由.
            if llm_client is not None:
                reflection_text = event.payload.get("reflection_text", "")
                # 实际 LLM 调用 (示例 stub)
                # analysis = llm_client.analyze_reflection(reflection_text)
                # _log.info("Deep reflection analysis (sid=%s): %s", student_id, analysis)
                _log.debug(
                    "Deep reflection (sid=%s, llm=%s): reflection_text=%s",
                    student_id, llm_client is not None, reflection_text[:50],
                )
        except Exception:
            _log.warning("Deep reflection handler 异常, skip", exc_info=True)

    return subscription_id


# ── Plugin SDK Entry Point ─────────────────────────────────────────────────


def register_all_use_cases(bus: EventBus, lca_engine: Any, llm_client: Any = None) -> Dict[str, Optional[str]]:
    """注册所有 5 个 use case subscribers. 返回 subscription_id 字典 (test isolation 用).

    生产环境: 在 Flask app startup 调一次, 跟 PluginRuntime.start() 一起注册.

    v0.94.0-c: hint_fatigue 走 SDK HintFatiguePlugin (PluginRegistry 路径),
    实际 sub_id 由 PluginRuntime.start() 时 subscribe_all 触发, 本函数返 None.
    其它 4 个 use case 仍走原 bus.subscribe 路径, 返具体 sub_id.
    """
    return {
        "teacher_reflection": use_case_teacher_reflection_analysis(bus, lca_engine),
        "parent_goal": use_case_parent_goal_dashboard(bus, lca_engine),
        "hint_fatigue": use_case_hint_fatigue_detection(bus, lca_engine),
        "idle_reminder": use_case_idle_reminder(bus, lca_engine),
        "deep_reflection": use_case_deep_reflection_analysis(bus, lca_engine, llm_client),
    }


# ── Module self-test (doctest-style smoke test) ─────────────────────────────


def _self_test_imports() -> bool:
    """Verify all imports work (smoke test for docs/plugin_sdk.md §七 linkage).

    Returns:
        True if all imports succeed.
    """
    try:
        from ecos.cta.cognitive_twin import CognitiveTwinAgent  # noqa: F401
        from ecos.cta.event_log import LearningEvent, LearningEventType  # noqa: F401
        from ecos.event import EventBus  # noqa: F401
        return True
    except ImportError as e:
        _log.error("Plugin SDK self-test failed: %s", e)
        return False


if __name__ == "__main__":
    # 本文件不直接执行, 但可作为 smoke test 跑
    import sys
    success = _self_test_imports()
    print(f"Plugin SDK self-test: {'PASS' if success else 'FAIL'}")
    sys.exit(0 if success else 1)