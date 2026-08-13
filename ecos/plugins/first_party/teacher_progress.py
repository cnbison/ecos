"""TeacherProgressPlugin —— 第一方 Plugin: 教师 progress review (v0.94.0-c).

对应 docs/plugin_library.md §5 + examples/plugin_sample_pomdp_diagnostic.py
use_case_teacher_progress_review 升级到 SDK Plugin ABC.

设计:
    - 订阅 topic: pomdp_diagnostic_updated (Plugin-internal topic, v0.93.0-b)
    - 读 POMDPDiagnostic.coverage (per-(s,a) sample count, v0.93.0-a)
    - 派生: min_coverage (跨 (s,a) 最少的样本数) → 冷启动判断
    - 输出: _log.info (供 Teacher Dashboard v0.95+ 接)

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
            "judgment + most_likely_state for教学分析"
        ),
        subscribed_topics=("pomdp_diagnostic_updated",),
    )

    def __init__(self) -> None:
        # per-student 上次报告的 min_coverage (供 _log.info 简化用)
        self._last_min_coverage: Dict[str, int] = {}

    def on_event(self, event: LearningEvent) -> Optional[Dict[str, Any]]:
        """处理 pomdp_diagnostic_updated event: 读 diagnostic + 冷启动判断 + 当前状态.

        Args:
            event: LearningEvent (from_pomdp_diagnostic_updated factory 构造).
                  payload.diagnostic 是 POMDPDiagnostic.to_dict() 输出.

        Returns:
            dict {"student_id": ..., "most_likely_state": ..., "min_coverage": ...,
                  "cold_start": ...} 供 PluginRegistry / 调试用. 返 None 表示 skip.

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

            # 当前状态
            most_likely_idx = diagnostic.most_likely_state
            most_likely_state = (
                _POMDP_STATE_NAMES[most_likely_idx]
                if 0 <= most_likely_idx < len(_POMDP_STATE_NAMES)
                else f"Unknown({most_likely_idx})"
            )

            # 冷启动判断: min(coverage) 跨 (s, a)
            min_coverage = int(diagnostic.coverage.min())
            cold_start = min_coverage < COLD_START_COVERAGE_THRESHOLD

            # 教学建议
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

            _log.info(
                "TeacherProgressPlugin: (sid=%s) 状态=%s, %s",
                student_id, most_likely_state, advice,
            )

            self._last_min_coverage[student_id] = min_coverage

            return {
                "student_id": student_id,
                "most_likely_state": most_likely_state,
                "most_likely_state_index": most_likely_idx,
                "belief": diagnostic.belief.tolist(),
                "min_coverage": min_coverage,
                "cold_start": cold_start,
                "advice": advice,
            }
        except Exception:
            _log.warning("TeacherProgressPlugin.on_event 异常, skip", exc_info=True)
            return None

    def get_subscribed_topics(self) -> Set[str]:
        """返订阅的 topic 集合."""
        return set(self.metadata.subscribed_topics)

    def enable(self) -> None:
        """Lifecycle: 启用 plugin (清零 state 缓存)."""
        self._last_min_coverage.clear()

    def disable(self) -> None:
        """Lifecycle: 禁用 plugin (清零 state 缓存, 跟 enable 对称)."""
        self._last_min_coverage.clear()


__all__ = ["TeacherProgressPlugin", "COLD_START_COVERAGE_THRESHOLD"]