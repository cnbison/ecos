"""ECOS POMDP Diagnostic 3 Use Case 示例 (v0.93.0-d).

对应设计: docs/pomdp_diagnostic.md §八.

Use Case:
  1. 教师后台 progress_review: 订阅 pomdp_diagnostic_updated → 读 POMDPDiagnostic → 显示学生当前最可能状态 + 冷启动判断
  2. 家长 engagement dashboard: 订阅 pomdp_diagnostic_updated → 读 POMDPDiagnostic.evolution → 显示 POMDP 趋势
  3. 学生 self_reflection: 调 Runtime.diagnose_pomdp → 读 most_likely_state → 生成学习建议

Plugin 原则 (per docs/pomdp_diagnostic.md §一):
  - Plugin 不调 POMDPPolicy (POMDPPolicy.update / bayes_update)
  - Plugin 只订阅 EventBus topic + 读 POMDPDiagnostic
  - Runtime 是 sole entry (PluginRuntime 调 Runtime.diagnose_pomdp)

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

_log = logging.getLogger(__name__)


# ── Use Case 1: 教师后台 progress_review ─────────────────────────────────


def _teacher_progress_handler(event: Any) -> None:
    """Teacher progress review handler: 读 POMDPDiagnostic 派生教学分析.

    Plugin 不调 POMDPPolicy.get_diagnostic, 仅接收 event.payload (Runtime.diagnose_pomdp 输出).
    """
    try:
        student_id = event.payload.get("student_id")
        diagnostic_dict = event.payload.get("diagnostic")
        if diagnostic_dict is None:
            _log.warning("Teacher progress handler: diagnostic 为空 (sid=%s), skip", student_id)
            return
        diagnostic = POMDPDiagnostic.from_dict(diagnostic_dict)

        # 1) 显示最可能状态
        state_names = ("Engaged", "Frustrated", "Bored", "Confused")
        most_likely = state_names[diagnostic.most_likely_state]
        _log.info(
            "教师进度分析 (sid=%s): 最可能状态=%s (belief=%s)",
            student_id, most_likely, diagnostic.belief.round(3).tolist(),
        )

        # 2) 冷启动判断: coverage < 5 → 冷启动期, 教学建议保守
        min_coverage = int(diagnostic.coverage.min())
        if min_coverage < 5:
            _log.info(
                "教师进度分析 (sid=%s): 冷启动期 (min_coverage=%d), 建议保守教学",
                student_id, min_coverage,
            )
        else:
            _log.info(
                "教师进度分析 (sid=%s): 已冷启动完成 (min_coverage=%d), 可基于 POMDP 后验定制教学",
                student_id, min_coverage,
            )
    except Exception:
        _log.warning("Teacher progress handler 异常, skip", exc_info=True)


def use_case_teacher_progress_review(bus: EventBus) -> str:
    """Use Case 1: 教师后台 progress_review.

    订阅 pomdp_diagnostic_updated topic, 读 POMDPDiagnostic, 显示:
      - 学生当前最可能状态 (most_likely_state)
      - T 后验覆盖度 (coverage[s, a] per (s, a), 冷启动判断核心)
      - belief 分布 (4 状态 posterior)
    """
    return bus.subscribe("pomdp_diagnostic_updated", _teacher_progress_handler)


# ── Use Case 2: 家长 engagement dashboard ──────────────────────────────────


def _parent_engagement_handler(event: Any) -> None:
    """Parent engagement dashboard handler: 读 POMDPDiagnostic 演化追踪.

    注: 演化追踪走 POMDPPolicy.get_evolution() (FIFO cap K=10), Plugin 不调 POMDPPolicy,
    仅通过 diagnostic_dict 中的 evolution 字段读.
    """
    try:
        student_id = event.payload.get("student_id")
        diagnostic_dict = event.payload.get("diagnostic")
        if diagnostic_dict is None:
            return
        diagnostic = POMDPDiagnostic.from_dict(diagnostic_dict)

        # 读 evolution (K=10 snapshot 趋势) — 来自 LCAEngine.dump_state 或 POMDPPolicy.get_evolution()
        evolution: List[dict] = diagnostic_dict.get("evolution", [])
        state_names = ("Engaged", "Frustrated", "Bored", "Confused")
        recent_states = [state_names[snap["most_likely_state"]] for snap in evolution]
        _log.info(
            "家长 dashboard (sid=%s): 最近 %d 个 POMDP snapshot 状态序列: %s",
            student_id, len(recent_states), recent_states,
        )

        # 显示当前状态 + 趋势 (帮助家长理解学生 engagement 模式)
        current_state = state_names[diagnostic.most_likely_state]
        _log.info(
            "家长 dashboard (sid=%s): 当前状态=%s",
            student_id, current_state,
        )
    except Exception:
        _log.warning("Parent engagement handler 异常, skip", exc_info=True)


def use_case_parent_engagement_dashboard(bus: EventBus) -> str:
    """Use Case 2: 家长 engagement dashboard.

    订阅 pomdp_diagnostic_updated topic, 读 POMDPDiagnostic 演化追踪 (evolution K=10 cap).
    显示学生 POMDP 趋势: 最近 10 个 snapshot 的 most_likely_state 序列.
    """
    return bus.subscribe("pomdp_diagnostic_updated", _parent_engagement_handler)


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

    注: 实际订阅 / LCAEngine 注入需在 web/api/ 子模块中执行, 本 smoke 仅验证 entrypoint.
    """
    bus = get_default_bus()

    # Use Case 1 + 2 注册 subscriber
    sub_id_1 = use_case_teacher_progress_review(bus)
    sub_id_2 = use_case_parent_engagement_dashboard(bus)
    print(f"Use Case 1 (teacher) subscription_id: {sub_id_1}")
    print(f"Use Case 2 (parent) subscription_id: {sub_id_2}")

    # Use Case 3: 需 LCAEngine 实例, smoke 仅演示 signature
    print("Use Case 3 (student self_reflection) signature: use_case_student_self_reflection(lca_engine, student_id)")
    print("✅ POMDP Diagnostic 3 use case smoke PASS")


if __name__ == "__main__":
    smoke_test()