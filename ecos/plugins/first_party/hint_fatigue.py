"""HintFatiguePlugin —— 第一方 Plugin: 提示疲劳检测 (v0.94.0-c).

对应 docs/plugin_library.md §5 + examples/plugin_sample_human_feedback.py
use_case_hint_fatigue_detection 升级到 SDK Plugin ABC.

设计:
    - 订阅 topic: hint_requested (LearningEventType.HINT_REQUESTED, v0.85.0-d)
    - 计数: per-student hint 数
    - 阈值: HINT_FATIGUE_THRESHOLD = 5 (跟 v0.91 examples 一致)
    - 告警: 计数 > 阈值 _log.warning (供 Teacher Dashboard v0.95+ 接 warning)

不变量 (per docs/plugin_library.md §6):
    - Plugin 不调 Runtime API (Runtime.update_belief 等 write API)
    - Plugin 不 mutate BeliefState / LCAEngine state
    - Plugin 是 process_event pattern: 读 event.payload + 计数 + log warning
    - on_event 返回 dict (供 PluginRegistry / 调试追踪用)

向后兼容:
    - PluginMetadata.name="hint_fatigue" (跟 DomainRegistry.name pattern 一致)
    - subscribed_topics=("hint_requested",) 跟 v0.91 examples 完全一致
    - 行为: 计数 > 5 告警 (跟 v0.91 use_case_hint_fatigue_detection 阈值一致)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, Optional, Set

from ecos.cta.event_log import LearningEvent
from ecos.plugins.base import Plugin, PluginMetadata

_log = logging.getLogger(__name__)

HINT_FATIGUE_THRESHOLD = 5


class HintFatiguePlugin(Plugin):
    """第一方 plugin: hint 疲劳检测 (v0.94.0-c).

    订阅 hint_requested topic, per-student 计数 hint 数. 超过阈值 (default 5)
    触发 _log.warning (供 Teacher Dashboard v0.95+ 接 warning).

    跟 examples/plugin_sample_human_feedback.py::use_case_hint_fatigue_detection
    完全 parallel 模式 (阈值 5 + 计数 + 告警), 升级为 SDK-level Plugin ABC.

    用法:
        >>> plugin = HintFatiguePlugin()
        >>> "hint_requested" in plugin.get_subscribed_topics()
        True
        >>> plugin.metadata.name
        'hint_fatigue'
        >>> plugin.metadata.version
        '1.0.0'
    """

    metadata = PluginMetadata(
        name="hint_fatigue",
        version="1.0.0",
        description="Detect students who overuse hints (count > threshold)",
        subscribed_topics=("hint_requested",),
    )

    def __init__(self, threshold: int = HINT_FATIGUE_THRESHOLD) -> None:
        self._threshold = threshold
        # per-student hint 计数 (enable/disable 时清零)
        self._counts: Dict[str, int] = defaultdict(int)

    @property
    def threshold(self) -> int:
        """暴露阈值 (test introspection 用)."""
        return self._threshold

    def get_hint_count(self, student_id: str) -> int:
        """返 student_id 当前 hint 计数 (test introspection 用)."""
        return self._counts.get(student_id, 0)

    def on_event(self, event: LearningEvent) -> Optional[Dict[str, Any]]:
        """处理 hint_requested event: 计数 + 阈值告警.

        Args:
            event: LearningEvent (from_hint_requested factory 构造), event_type
                  必须是 "hint_requested". payload 含 problem_id / hint_level.

        Returns:
            dict {"student_id": ..., "hint_count": ...} 供 PluginRegistry / 调试用.
            返 None 表示 event_type 不匹配 skip.

        防御性:
            - event_type != "hint_requested" 时 skip (防 subscribed_topics 配置错误)
            - exception 兜底 _log.warning + 返 None (不 raise)
        """
        try:
            if event.event_type != "hint_requested":
                return None  # skip, 防 subscribed_topics 配置错误
            student_id = event.student_id
            if not student_id:
                _log.warning("HintFatiguePlugin: event 无 student_id, skip")
                return None
            self._counts[student_id] += 1
            current_count = self._counts[student_id]
            if current_count > self._threshold:
                _log.warning(
                    "HintFatiguePlugin: student_id=%s hit %d hints (threshold=%d), "
                    "学生可能过度依赖 hint, 建议教师介入",
                    student_id, current_count, self._threshold,
                )
            return {
                "student_id": student_id,
                "hint_count": current_count,
                "threshold_exceeded": current_count > self._threshold,
            }
        except Exception:
            _log.warning("HintFatiguePlugin.on_event 异常, skip", exc_info=True)
            return None

    def get_subscribed_topics(self) -> Set[str]:
        """返订阅的 topic 集合."""
        return set(self.metadata.subscribed_topics)

    def enable(self) -> None:
        """Lifecycle: 启用 plugin (清零计数)."""
        self._counts.clear()

    def disable(self) -> None:
        """Lifecycle: 禁用 plugin (清零计数, 跟 enable 对称)."""
        self._counts.clear()


__all__ = ["HintFatiguePlugin", "HINT_FATIGUE_THRESHOLD"]