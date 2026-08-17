"""TeacherProgressPlugin —— 第一方 Plugin: 教师 progress review (v0.94.0-c → v0.95.1 UI 可消费).

对应 docs/plugin_library.md §5 + examples/plugin_sample_pomdp_diagnostic.py
use_case_teacher_progress_review 升级到 SDK Plugin ABC.

设计:
    - 订阅 topic: pomdp_diagnostic_updated (Plugin-internal topic, v0.93.0-b)
    - 读 POMDPDiagnostic.coverage (per-(s,a) sample count, v0.93.0-a)
    - 派生: min_coverage (跨 (s,a) 最少的样本数) → 冷启动判断
    - v0.95.1 升级: 从 _log.info 升级为 UI 可消费 —
      每个学生派生结构化 report 存到 self._reports, 暴露 report_for() / get_reports()
      / ingest_diagnostic() 查询入口, 供 /api/teacher/* (Teacher Dashboard) 直接读.

不变量:
    - Plugin 不调 POMDPPolicy.get_diagnostic() (Kernel 路径), 仅通过 event.payload 读
    - Plugin 不 mutate Kernel state (defensive check [8] 仍 hard block)
    - coverage < COLD_START_COVERAGE_THRESHOLD → 冷启动期, 教师建议保守
    - exception 兜底 _log.warning + 返 None (不 raise)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Set

from ecos.cta.event_log import LearningEvent
from ecos.lca.l4_optimization.pomdp_diagnostic import POMDPDiagnostic
from ecos.plugins.base import Plugin, PluginMetadata

_log = logging.getLogger(__name__)

# 冷启动判断阈值: coverage.min() < 5 → 冷启动期, 教学建议保守
# 跟 examples/plugin_sample_pomdp_diagnostic.py 一致 (min_coverage < 5)
COLD_START_COVERAGE_THRESHOLD = 5

# POMDP 状态名映射 (跟 ParentEngagementPlugin / LCAEngine.pomdp_path 一致)
_POMDP_STATE_NAMES = ("Engaged", "Frustrated", "Bored", "Confused")


class TeacherProgressPlugin(Plugin):
    """第一方 plugin: 教师 progress review (v0.94.0-c).

    订阅 pomdp_diagnostic_updated topic, 读 POMDPDiagnostic.coverage
    (per-(s,a) sample count, v0.93.0-a), 显示教师可读的教学分析:

      - 当前最可能状态 (most_likely_state)
      - belief 分布 (4 状态 posterior)
      - T 后验覆盖度 (coverage[s, a], 冷启动判断核心)
      - 冷启动判断: min(coverage) < 5 → 冷启动期, 建议保守教学

    跟 examples/plugin_sample_pomdp_diagnostic.py::use_case_teacher_progress_review
    完全 parallel 模式, 升级为 SDK-level Plugin ABC.

    v0.95.1 UI 可消费升级:
        - on_event 除了 _log.info, 还把 report 存到 self._reports[student_id]
        - report_for(student_id) / get_reports() 供 /api/teacher/* 直接查询
        - ingest_diagnostic(student_id, POMDPDiagnostic) 供 Teacher API 非 event 路径喂数据
          (同步复用同一 report 派生逻辑, 避免双份实现)

    用法:
        >>> plugin = TeacherProgressPlugin()
        >>> "pomdp_diagnostic_updated" in plugin.get_subscribed_topics()
        True
        >>> plugin.metadata.name
        'teacher_progress'
    """

    metadata = PluginMetadata(
        name="teacher_progress",
        version="1.0.0",
        description=(
            "Teacher progress review: read POMDPDiagnostic.coverage for cold-start "
            "judgment + most_likely_state for教学分析 (v0.95.1 UI 可消费)"
        ),
        subscribed_topics=("pomdp_diagnostic_updated",),
    )

    def __init__(self) -> None:
        # v0.95.1: per-student 结构化报告 (UI 可消费, /api/teacher/* 查询入口)
        self._reports: Dict[str, Dict[str, Any]] = {}

    def _build_report(
        self,
        student_id: str,
        diagnostic: POMDPDiagnostic,
    ) -> Dict[str, Any]:
        """从 POMDPDiagnostic 派生教师可读报告 (on_event 与 ingest_diagnostic 共享).

        Args:
            student_id: 学生 ID
            diagnostic: POMDPDiagnostic frozen dataclass (v0.93.0-a)

        Returns:
            report dict:
                {
                    "student_id", "most_likely_state", "most_likely_state_index",
                    "belief" (4 状态 posterior list), "min_coverage", "cold_start",
                    "advice" (教学建议), "updated_at" (ISO datetime)
                }
        """
        most_likely_idx = diagnostic.most_likely_state
        most_likely_state = (
            _POMDP_STATE_NAMES[most_likely_idx]
            if 0 <= most_likely_idx < len(_POMDP_STATE_NAMES)
            else f"Unknown({most_likely_idx})"
        )

        min_coverage = int(diagnostic.coverage.min())
        cold_start = min_coverage < COLD_START_COVERAGE_THRESHOLD

        if cold_start:
            advice = (
                f"冷启动期 (min_coverage={min_coverage} < "
                f"{COLD_START_COVERAGE_THRESHOLD}), 建议保守教学"
            )
        else:
            advice = (
                f"已冷启动完成 (min_coverage={min_coverage}), "
                f"可基于 POMDP 后验定制教学"
            )

        from datetime import datetime as _dt
        return {
            "student_id": student_id,
            "most_likely_state": most_likely_state,
            "most_likely_state_index": most_likely_idx,
            "belief": diagnostic.belief.tolist(),
            "min_coverage": min_coverage,
            "cold_start": cold_start,
            "advice": advice,
            "updated_at": _dt.now().isoformat(),
        }

    def on_event(self, event: LearningEvent) -> Optional[Dict[str, Any]]:
        """处理 pomdp_diagnostic_updated event: 读 diagnostic + 冷启动判断 + 当前状态.

        Args:
            event: LearningEvent (from_pomdp_diagnostic_updated factory 构造).
                  payload.diagnostic 是 POMDPDiagnostic.to_dict() 输出.

        Returns:
            dict {"student_id": ..., "most_likely_state": ..., "min_coverage": ...,
                  "cold_start": ..., "advice": ...} 供 PluginRegistry / Teacher API 读.
                  同时缓存到 self._reports[student_id]. 返 None 表示 skip.

        防御性:
            - event_type != "pomdp_diagnostic_updated" 时 skip
            - diagnostic 缺失 / 非法时 _log.warning skip
            - exception 兜底 _log.warning + 返 None (不 raise)
        """
        try:
            if event.event_type != "pomdp_diagnostic_updated":
                return None
            student_id = event.student_id
            if not student_id:
                _log.warning("TeacherProgressPlugin: event 无 student_id, skip")
                return None
            diagnostic_dict = event.payload.get("diagnostic")
            if diagnostic_dict is None:
                _log.warning(
                    "TeacherProgressPlugin: diagnostic 缺失 (sid=%s), skip", student_id
                )
                return None
            try:
                diagnostic = POMDPDiagnostic.from_dict(diagnostic_dict)
            except (ValueError, KeyError) as e:
                _log.warning(
                    "TeacherProgressPlugin: POMDPDiagnostic.from_dict 失败 "
                    "(sid=%s): %s, skip",
                    student_id, e,
                )
                return None

            report = self._build_report(student_id, diagnostic)
            self._reports[student_id] = report

            _log.info(
                "TeacherProgressPlugin: (sid=%s) 状态=%s, %s (report 已缓存, "
                "Teacher API 可查询)",
                student_id, report["most_likely_state"], report["advice"],
            )

            return report
        except Exception:
            _log.warning("TeacherProgressPlugin.on_event 异常, skip", exc_info=True)
            return None

    def ingest_diagnostic(
        self,
        student_id: str,
        diagnostic: POMDPDiagnostic,
    ) -> Dict[str, Any]:
        """v0.95.1: Teacher API 直接喂 POMDPDiagnostic (非 event 路径), 返回 report.

        复用 _build_report 单一实现 — Teacher API 调 Runtime.diagnose_pomdp 拿到
        POMDPDiagnostic 后, 喂给 plugin 让报告逻辑只存在一份 (DRY).

        Args:
            student_id: 学生 ID
            diagnostic: POMDPDiagnostic frozen dataclass

        Returns:
            report dict (跟 on_event 返回完全同构, 已缓存到 self._reports[student_id]).
        """
        report = self._build_report(student_id, diagnostic)
        self._reports[student_id] = report
        return report

    def report_for(self, student_id: str) -> Optional[Dict[str, Any]]:
        """v0.95.1: 查询单个学生的教师报告 (UI 可消费入口).

        Returns:
            最近一次 report dict, 或 None (该学生还没有 pomdp_diagnostic_updated 事件
            也没被 ingest_diagnostic 喂过).
        """
        return self._reports.get(student_id)

    def get_reports(self) -> Dict[str, Dict[str, Any]]:
        """v0.95.1: 查询全部学生的教师报告 (班级视图冷启动/状态 flag 用).

        Returns:
            {student_id: report} dict 的 copy (防止外部 mutation).
        """
        return dict(self._reports)

    def get_subscribed_topics(self) -> Set[str]:
        """返订阅的 topic 集合."""
        return set(self.metadata.subscribed_topics)

    def enable(self) -> None:
        """Lifecycle: 启用 plugin (清零 state 缓存)."""
        self._reports.clear()

    def disable(self) -> None:
        """Lifecycle: 禁用 plugin (清零 state 缓存, 跟 enable 对称)."""
        self._reports.clear()


__all__ = ["TeacherProgressPlugin", "COLD_START_COVERAGE_THRESHOLD"]