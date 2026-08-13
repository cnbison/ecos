"""ParentEngagementPlugin —— 第一方 Plugin: 家长 engagement dashboard (v0.94.0-c).

对应 docs/plugin_library.md §5 + examples/plugin_sample_pomdp_diagnostic.py
use_case_parent_engagement_dashboard 升级到 SDK Plugin ABC.

设计:
    - 订阅 topic: pomdp_diagnostic_updated (Plugin-internal topic, v0.93.0-b)
    - 读 POMDPDiagnostic.evolution (timed snapshots K=10, v0.93.0-c)
    - 派生: 最近 K 个 snapshot 的 most_likely_state 序列 + 当前状态
    - 输出: _log.info (供 Parent Dashboard v0.95+ 接)

不变量:
    - Plugin 不调 POMDPPolicy.get_evolution() (Kernel 路径), 仅通过 event.payload 读
    - Plugin 不 mutate Kernel state (defensive check [8] 仍 hard block)
    - evolution 缺失时 graceful skip (演化追踪是 optional)
    - exception 兜底 _log.warning + 返 None (不 raise)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from ecos.cta.event_log import LearningEvent
from ecos.lca.l4_optimization.pomdp_diagnostic import POMDPDiagnostic
from ecos.plugins.base import Plugin, PluginMetadata

_log = logging.getLogger(__name__)

# POMDP 状态名映射 (跟 LCAEngine.pomdp_path / examples 一致)
_POMDP_STATE_NAMES = ("Engaged", "Frustrated", "Bored", "Confused")


class ParentEngagementPlugin(Plugin):
    """第一方 plugin: 家长 engagement dashboard (v0.94.0-c).

    订阅 pomdp_diagnostic_updated topic, 读 POMDPDiagnostic.evolution
    (K=10 cap timed snapshots, v0.93.0-c), 显示家长可读的 POMDP 趋势:

      - 最近 K 个 snapshot 的 most_likely_state 序列
      - 当前状态
      - 状态序列变化 (帮助家长理解学生 engagement 模式)

    跟 examples/plugin_sample_pomdp_diagnostic.py::use_case_parent_engagement_dashboard
    完全 parallel 模式, 升级为 SDK-level Plugin ABC.

    用法:
        >>> plugin = ParentEngagementPlugin()
        >>> "pomdp_diagnostic_updated" in plugin.get_subscribed_topics()
        True
        >>> plugin.metadata.name
        'parent_engagement'
    """

    metadata = PluginMetadata(
        name="parent_engagement",
        version="1.0.0",
        description=(
            "Parent dashboard: read POMDPDiagnostic.evolution (timed snapshots) "
            "and surface most_likely_state trends for parent visibility"
        ),
        subscribed_topics=("pomdp_diagnostic_updated",),
    )

    def __init__(self) -> None:
        # per-student evolution 缓存 (从 event.payload 读, 持久化可选)
        self._last_state_index: Dict[str, int] = {}

    def on_event(self, event: LearningEvent) -> Optional[Dict[str, Any]]:
        """处理 pomdp_diagnostic_updated event: 读 diagnostic.evolution + 当前状态.

        Args:
            event: LearningEvent (from_pomdp_diagnostic_updated factory 构造).
                  payload.diagnostic 是 POMDPDiagnostic.to_dict() 输出.

        Returns:
            dict {"student_id": ..., "current_state": ..., "evolution_count": ...}
            供 PluginRegistry / 调试用. 返 None 表示 diagnostic 缺失或 event_type 错.

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
                _log.warning("ParentEngagementPlugin: event 无 student_id, skip")
                return None
            diagnostic_dict = event.payload.get("diagnostic")
            if diagnostic_dict is None:
                _log.warning(
                    "ParentEngagementPlugin: diagnostic 缺失 (sid=%s), skip", student_id
                )
                return None
            # 防御性: from_dict 会校验 schema_version, 不匹配 raise
            # 这里 try/except 兜底, 老 schema skip 不污染 parent dashboard
            try:
                diagnostic = POMDPDiagnostic.from_dict(diagnostic_dict)
            except (ValueError, KeyError) as e:
                _log.warning(
                    "ParentEngagementPlugin: POMDPDiagnostic.from_dict 失败 "
                    "(sid=%s): %s, skip",
                    student_id, e,
                )
                return None

            # 当前状态
            most_likely_idx = diagnostic.most_likely_state
            current_state = (
                _POMDP_STATE_NAMES[most_likely_idx]
                if 0 <= most_likely_idx < len(_POMDP_STATE_NAMES)
                else f"Unknown({most_likely_idx})"
            )

            # 演化追踪: K=10 snapshot 序列 (FIFO cap)
            evolution: List[Dict[str, Any]] = diagnostic_dict.get("evolution", [])
            recent_states: List[str] = []
            for snap in evolution:
                if not isinstance(snap, dict):
                    continue
                s_idx = snap.get("most_likely_state")
                if isinstance(s_idx, int) and 0 <= s_idx < len(_POMDP_STATE_NAMES):
                    recent_states.append(_POMDP_STATE_NAMES[s_idx])

            # 状态变化检测 (跟上一 snapshot 比)
            prev_state_idx = self._last_state_index.get(student_id)
            state_changed = (
                prev_state_idx is not None and prev_state_idx != most_likely_idx
            )
            self._last_state_index[student_id] = most_likely_idx

            _log.info(
                "ParentEngagementPlugin: (sid=%s) 当前状态=%s, "
                "最近 %d 个 snapshot: %s%s",
                student_id, current_state, len(recent_states), recent_states,
                " (状态变化!)" if state_changed else "",
            )
            return {
                "student_id": student_id,
                "current_state": current_state,
                "current_state_index": most_likely_idx,
                "recent_states": recent_states,
                "evolution_count": len(recent_states),
                "state_changed": state_changed,
            }
        except Exception:
            _log.warning("ParentEngagementPlugin.on_event 异常, skip", exc_info=True)
            return None

    def get_subscribed_topics(self) -> Set[str]:
        """返订阅的 topic 集合."""
        return set(self.metadata.subscribed_topics)

    def enable(self) -> None:
        """Lifecycle: 启用 plugin (清零 state 缓存)."""
        self._last_state_index.clear()

    def disable(self) -> None:
        """Lifecycle: 禁用 plugin (清零 state 缓存, 跟 enable 对称)."""
        self._last_state_index.clear()


__all__ = ["ParentEngagementPlugin"]