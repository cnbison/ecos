"""ECOS POMDP Diagnostic 3 Use Case 示例 (v0.93.0-d, v0.94.0-c 升级).

对应设计: docs/pomdp_diagnostic.md §八 + docs/plugin_library.md §5.

Use Case:
  1. 教师后台 progress_review: 订阅 pomdp_diagnostic_updated → 读 POMDPDiagnostic → 显示学生当前最可能状态 + 冷启动判断
     (v0.94.0-c 升级: 走 TeacherProgressPlugin SDK Plugin ABC)
  2. 家长 engagement dashboard: 订阅 pomdp_diagnostic_updated → 读 POMDPDiagnostic.evolution → 显示 POMDP 趋势
     (v0.94.0-c 升级: 走 ParentEngagementPlugin SDK Plugin ABC)
  3. 学生 self_reflection: 调 Runtime.diagnose_pomdp → 读 most_likely_state → 生成学习建议
     (use case 3 不需 plugin, 走 LCAEngine.get_pomdp_diagnostic 直接读)

Plugin 原则 (per docs/pomdp_diagnostic.md §一):
  - Plugin 不调 POMDPPolicy (POMDPPolicy.update / bayes_update)
  - Plugin 只订阅 EventBus topic + 读 POMDPDiagnostic
  - Runtime 是 sole entry (PluginRuntime 调 Runtime.diagnose_pomdp)
  - v0.94+ 第一方 plugin 走 SDK Plugin ABC (TeacherProgressPlugin / ParentEngagementPlugin),
    走 PluginRegistry 注册, 由 PluginRuntime.start() 触发 subscribe_all

不变量:
  - POMDPDiagnostic 是 frozen dataclass, 不持有 BeliefState 引用 (防御性自检 [8] hard block)
  - Plugin handler 异常 _log.warning 不 raise (防御性自检 [1])
  - LCAEngine._pomdp_diagnostic dict mutation 走 LCAEngine self mutation (LCAEngine self mutation 不触及 BeliefState)

本文件不直接执行, 仅作为 POMDP Diagnostic 使用模板. 真集成请在 web/api/ 子模块中订阅.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from ecos.lca.l4_optimization.pomdp_diagnostic import POMDPDiagnostic
from ecos.event import EventBus, get_default_bus
# v0.94.0-c: 第一方 plugin SDK
from ecos.plugins.first_party import ParentEngagementPlugin, TeacherProgressPlugin

_log = logging.getLogger(__name__)


# ── Use Case 1: 教师后台 progress_review ─────────────────────────────────


def use_case_teacher_progress_review(bus: EventBus) -> Optional[str]:
    """Use Case 1: 教师后台 progress_review.

    v0.94.0-c 升级: 走 SDK TeacherProgressPlugin (Plugin ABC 继承 + PluginRegistry 注册).
    Plugin 内部实现:
      - 读 POMDPDiagnostic.most_likely_state + belief (当前状态)
      - 读 POMDPDiagnostic.coverage.min() (冷启动判断)
      - 派生教学建议 (冷启动期保守 / 已冷启动基于后验定制)

    订阅 pomdp_diagnostic_updated topic, 实际挂载由 PluginRuntime.start() 触发.

    Returns:
        Optional[str]: subscription_id. v0.94+ 走 PluginRegistry 路径后,
        实际 sub_id 由 PluginRuntime 统一管理, 本函数返 None.
    """
    # 注册 TeacherProgressPlugin 到 default singleton registry (一次性)
    from ecos.plugins.registry import get_default_registry, PluginRegistry
    registry: PluginRegistry = get_default_registry()
    if not registry.has("teacher_progress"):
        registry.register(TeacherProgressPlugin())
    return None


# ── Use Case 2: 家长 engagement dashboard ──────────────────────────────────


def use_case_parent_engagement_dashboard(bus: EventBus) -> Optional[str]:
    """Use Case 2: 家长 engagement dashboard.

    v0.94.0-c 升级: 走 SDK ParentEngagementPlugin (Plugin ABC 继承 + PluginRegistry 注册).
    Plugin 内部实现:
      - 读 POMDPDiagnostic.most_likely_state (当前状态)
      - 读 POMDPDiagnostic.evolution (K=10 timed snapshots 趋势)
      - 派生状态变化检测 (跟上一 snapshot 比, 帮助家长理解 engagement 模式)

    订阅 pomdp_diagnostic_updated topic, 实际挂载由 PluginRuntime.start() 触发.

    Returns:
        Optional[str]: subscription_id. v0.94+ 走 PluginRegistry 路径后,
        实际 sub_id 由 PluginRuntime 统一管理, 本函数返 None.
    """
    # 注册 ParentEngagementPlugin 到 default singleton registry (一次性)
    from ecos.plugins.registry import get_default_registry, PluginRegistry
    registry: PluginRegistry = get_default_registry()
    if not registry.has("parent_engagement"):
        registry.register(ParentEngagementPlugin())
    return None


# ── Use Case 3: 学生 self_reflection ────────────────────────────────────────


def use_case_student_self_reflection(lca_engine: Any, student_id: str) -> Optional[str]:
    """Use Case 3: 学生 self_reflection.

    调 Runtime.diagnose_pomdp (或直接 LCAEngine.get_pomdp_diagnostic), 读 most_likely_state,
    生成学习建议 (e.g. "你可能需要更高难度题目" / "试着换个学习方式").

    Args:
        lca_engine: LCAEngine 实例
        student_id: 学生 ID

    Returns:
        str: 学习建议 (None 表示 diagnostic 不可用, 如非 POMDP policy)
    """
    try:
        diagnostic: Optional[POMDPDiagnostic] = lca_engine.get_pomdp_diagnostic(student_id)
        if diagnostic is None:
            _log.info("学生 self_reflection (sid=%s): POMDP diagnostic 不可用", student_id)
            return None

        state_names = ("Engaged", "Frustrated", "Bored", "Confused")
        most_likely = diagnostic.most_likely_state
        current_state = state_names[most_likely]

        # 根据当前状态生成学习建议
        suggestions = {
            0: "你状态很好! 建议尝试更高难度题目挑战自己.",
            1: "遇到挫折? 试着回顾已学内容, 巩固基础再挑战.",
            2: "感觉无聊? 建议尝试新题型或换学科.",
            3: "感到困惑? 试着分解问题, 或寻求 hint 帮助理解.",
        }
        suggestion = suggestions.get(most_likely, "继续加油!")
        _log.info(
            "学生 self_reflection (sid=%s): 状态=%s, 建议=%s",
            student_id, current_state, suggestion,
        )
        return suggestion
    except Exception:
        _log.warning("Student self_reflection 异常 (sid=%s), skip", student_id, exc_info=True)
        return None


# ── Smoke 测试入口 ──────────────────────────────────────────────────────────


def smoke_test() -> None:
    """Smoke 测试: 验证 3 个 use case 入口可调用.

    v0.94.0-c 升级: Use Case 1 + 2 走 PluginRegistry 注册 (返 None, sub_id 由
    PluginRuntime.start() 触发 subscribe_all 时分配). Use Case 3 不需 plugin.

    注: 实际订阅 / LCAEngine 注入需在 web/api/ 子模块中执行, 本 smoke 仅验证 entrypoint.
    """
    bus = get_default_bus()

    # Use Case 1 + 2: 注册 SDK plugin (TeacherProgressPlugin / ParentEngagementPlugin)
    # 到 default singleton registry. 实际挂载由 PluginRuntime.start() 调 subscribe_all.
    sub_id_1 = use_case_teacher_progress_review(bus)
    sub_id_2 = use_case_parent_engagement_dashboard(bus)
    print(f"Use Case 1 (teacher) registered (sub_id 由 PluginRuntime 管理): {sub_id_1}")
    print(f"Use Case 2 (parent) registered (sub_id 由 PluginRuntime 管理): {sub_id_2}")

    # Use Case 3: 需 LCAEngine 实例, smoke 仅演示 signature
    print("Use Case 3 (student self_reflection) signature: use_case_student_self_reflection(lca_engine, student_id)")
    print("✅ POMDP Diagnostic 3 use case smoke PASS")


if __name__ == "__main__":
    smoke_test()