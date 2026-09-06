"""ParentEngagementPlugin —— 第一方 Plugin: 家长 engagement dashboard (v0.94.0-c → v0.98.0 UI 可消费).

对应 docs/plugin_library.md §5 + examples/plugin_sample_pomdp_diagnostic.py
use_case_parent_engagement_dashboard 升级到 SDK Plugin ABC.

设计:
    - 订阅 topic: pomdp_diagnostic_updated (Plugin-internal topic, v0.93.0-b)
    - 读 POMDPDiagnostic (T/R 后验 + most_likely_state) + evolution 序列 (K=10, v0.93.0-c)
    - v0.98.0 (a-a) 复活: 从 _log.info 升级为 UI 可消费 (仿 TeacherProgressPlugin v0.95.1) —
      每个学生派生结构化 report 存到 self._reports, 暴露 report_for() / get_reports()
      / ingest_diagnostic() / ingest_evolution() 查询入口, 供 /api/parent/* 直接读.
    - evolution 读取路径: POMDPDiagnostic.to_dict() 不含 evolution (留在
      POMDPPolicy._evolution), API 层经 Runtime.diagnose_pomdp_evolution (第 9 API)
      拿序列后 ingest_evolution() 喂入.
    - _build_advice: 规则表驱动 (不调 LLM, deterministic 可测), 阈值为先验值, v0.98 试点校准.

不变量:
    - Plugin 不调 POMDPPolicy.get_evolution() (Kernel 路径), 仅经 ingest 入口喂入
    - Plugin 不 mutate Kernel state (defensive check [8] 仍 hard block)
    - evolution 缺失时 graceful skip (演化追踪是 optional)
    - exception 兜底 _log.warning + 返 None (不 raise)
"""

from __future__ import annotations

import logging
from datetime import datetime as _dt
from typing import Any, Dict, List, Optional, Set

from ecos.cta.event_log import LearningEvent
from ecos.lca.l4_optimization.pomdp_diagnostic import POMDPDiagnostic
from ecos.plugins.base import Plugin, PluginMetadata

_log = logging.getLogger(__name__)

# POMDP 状态名映射 (跟 TeacherProgressPlugin / LCAEngine.pomdp_path 一致)
_POMDP_STATE_NAMES = ("Engaged", "Frustrated", "Bored", "Confused")

# 冷启动判断阈值: coverage.min() < 5 → 冷启动期 (跟 TeacherProgressPlugin 一致)
COLD_START_COVERAGE_THRESHOLD = 5

# 「持续投入」判定窗口: 最近 N 个 snapshot 全 Engaged → 正向建议
# 先验值, v0.98 试点校准
SUSTAINED_ENGAGED_WINDOW = 3


def _state_name(idx: Any) -> str:
    """状态 index → 名字 (越界返 Unknown(n), 防御性)."""
    if isinstance(idx, int) and 0 <= idx < len(_POMDP_STATE_NAMES):
        return _POMDP_STATE_NAMES[idx]
    return f"Unknown({idx})"


class ParentEngagementPlugin(Plugin):
    """第一方 plugin: 家长 engagement dashboard (v0.94.0-c → v0.98.0 UI 可消费).

    订阅 pomdp_diagnostic_updated topic + 支持直接 ingest 双路径, 读
    POMDPDiagnostic (most_likely_state / coverage) + evolution 序列
    (K=10 cap timed snapshots, v0.93.0-c), 产出家长可读报告:

      - 当前状态 + 最近 K 个 snapshot 的 most_likely_state 序列
      - 状态变化检测 (帮助家长理解学生 engagement 模式)
      - 规则表驱动的中文建议条目 (trigger + severity, 不调 LLM)

    v0.98.0 (a-a) UI 可消费升级 (仿 TeacherProgressPlugin v0.95.1):
        - on_event / ingest_diagnostic 共享 _build_report 单一派生逻辑 (DRY)
        - report_for(student_id) / get_reports() 供 /api/parent/* 直接查询
        - ingest_evolution(student_id, evolution) 喂 Runtime.diagnose_pomdp_evolution 结果

    用法:
        >>> plugin = ParentEngagementPlugin()
        >>> "pomdp_diagnostic_updated" in plugin.get_subscribed_topics()
        True
        >>> plugin.metadata.name
        'parent_engagement'
        >>> plugin.metadata.version
        '1.1.0'
    """

    metadata = PluginMetadata(
        name="parent_engagement",
        version="1.1.0",
        description=(
            "Parent dashboard: read POMDPDiagnostic + evolution (timed snapshots) "
            "and surface most_likely_state trends + rule-based advice for parents "
            "(v0.98.0 UI 可消费)"
        ),
        subscribed_topics=("pomdp_diagnostic_updated",),
    )

    def __init__(self) -> None:
        # v0.98.0: per-student 结构化报告 (UI 可消费, /api/parent/* 查询入口)
        self._reports: Dict[str, Dict[str, Any]] = {}
        # per-student 最近状态缓存 (on_event 路径的状态变化检测用)
        self._last_state_index: Dict[str, int] = {}

    # ---------------------------------------------------------------
    # 共享派生 (on_event 与 ingest_diagnostic 双路径单一实现)
    # ---------------------------------------------------------------

    def _build_report(
        self,
        student_id: str,
        most_likely_idx: int,
        min_coverage: int,
        recent_states: List[str],
    ) -> Dict[str, Any]:
        """从诊断字段派生家长可读报告 (双路径共享, DRY).

        Args:
            student_id: 学生 ID
            most_likely_idx: 当前 most_likely_state index
            min_coverage: coverage.min() (冷启动判断)
            recent_states: 演化序列的状态名列表 (旧→新, 可为空)

        Returns:
            report dict (结构见 _build_advice / module docstring).
        """
        current_state = _state_name(most_likely_idx)
        prev_idx = self._last_state_index.get(student_id)
        state_changed = prev_idx is not None and prev_idx != most_likely_idx
        self._last_state_index[student_id] = most_likely_idx

        cold_start = min_coverage < COLD_START_COVERAGE_THRESHOLD

        return {
            "student_id": student_id,
            "current_state": current_state,
            "current_state_index": most_likely_idx,
            "recent_states": recent_states,
            "evolution_count": len(recent_states),
            "state_changed": state_changed,
            "cold_start": cold_start,
            "advice": self._build_advice(
                current_state=current_state,
                recent_states=recent_states,
                cold_start=cold_start,
                state_changed=state_changed,
            ),
            "updated_at": _dt.now().isoformat(),
        }

    def _build_advice(
        self,
        current_state: str,
        recent_states: List[str],
        cold_start: bool,
        state_changed: bool,
    ) -> List[Dict[str, Any]]:
        """规则表驱动建议派生 (deterministic, 不调 LLM).

        阈值为先验值, v0.98 试点校准. severity 三档:
          - "info": 正常/正向信息
          - "warning": 需要关注 (负面状态)
          - "attention": 需要介入 (持续负面)

        Returns:
            [{"trigger": ..., "severity": ..., "message": ...}, ...]
        """
        advice: List[Dict[str, Any]] = []

        if cold_start:
            advice.append({
                "trigger": "cold_start",
                "severity": "info",
                "message": (
                    f"学生画像建立中 (数据覆盖不足, min_coverage < "
                    f"{COLD_START_COVERAGE_THRESHOLD}), 状态判断仅供参考"
                ),
            })

        # 负面状态: 单次 warning / 持续 attention
        negative_triggers = {
            "Frustrated": ("连续多次处于 Frustrated, 建议了解题目难度是否过高",
                           "attention"),
            "Bored": ("连续多次处于 Bored, 建议确认任务挑战度是否偏低", "attention"),
            "Confused": ("出现 Confused 状态, 建议陪伴复盘近期错题", "warning"),
        }
        if current_state in negative_triggers:
            message, single_severity = negative_triggers[current_state]
            sustained = (
                len(recent_states) >= SUSTAINED_ENGAGED_WINDOW
                and all(s == current_state for s in recent_states[-SUSTAINED_ENGAGED_WINDOW:])
            )
            advice.append({
                "trigger": f"state={current_state.lower()}",
                "severity": single_severity if sustained else "warning",
                "message": message,
            })

        if state_changed:
            advice.append({
                "trigger": "state_changed",
                "severity": "info",
                "message": f"学习状态发生变化 (当前: {current_state}), 可与学生聊聊近况",
            })

        if (
            len(recent_states) >= SUSTAINED_ENGAGED_WINDOW
            and all(s == "Engaged" for s in recent_states[-SUSTAINED_ENGAGED_WINDOW:])
        ):
            advice.append({
                "trigger": "sustained_engaged",
                "severity": "info",
                "message": "近期持续投入, 状态良好",
            })

        if not advice:
            advice.append({
                "trigger": "default",
                "severity": "info",
                "message": f"当前学习状态: {current_state}",
            })
        return advice

    # ---------------------------------------------------------------
    # 数据喂入路径 (event / ingest 双轨)
    # ---------------------------------------------------------------

    def _evolution_states_from_dicts(
        self, evolution: List[Any]
    ) -> List[str]:
        """从 to_dict evolution list 提取状态名序列 (on_event 路径)."""
        recent_states: List[str] = []
        for snap in evolution:
            if not isinstance(snap, dict):
                continue
            s_idx = snap.get("most_likely_state")
            if isinstance(s_idx, int) and 0 <= s_idx < len(_POMDP_STATE_NAMES):
                recent_states.append(_POMDP_STATE_NAMES[s_idx])
        return recent_states

    def on_event(self, event: LearningEvent) -> Optional[Dict[str, Any]]:
        """处理 pomdp_diagnostic_updated event: 读 diagnostic + 派生 report + 缓存.

        Args:
            event: LearningEvent (from_pomdp_diagnostic_updated factory 构造).
                  payload.diagnostic 是 POMDPDiagnostic.to_dict() 输出.

        Returns:
            report dict (已缓存到 self._reports[student_id]). 返 None 表示 skip.

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

            recent_states = self._evolution_states_from_dicts(
                diagnostic_dict.get("evolution", [])
            )
            report = self._build_report(
                student_id=student_id,
                most_likely_idx=diagnostic.most_likely_state,
                min_coverage=int(diagnostic.coverage.min()),
                recent_states=recent_states,
            )
            self._reports[student_id] = report

            _log.info(
                "ParentEngagementPlugin: (sid=%s) 当前状态=%s, 最近 %d 个 snapshot%s "
                "(report 已缓存, Parent API 可查询)",
                student_id, report["current_state"], report["evolution_count"],
                " (状态变化!)" if report["state_changed"] else "",
            )
            return report
        except Exception:
            _log.warning("ParentEngagementPlugin.on_event 异常, skip", exc_info=True)
            return None

    def ingest_diagnostic(
        self,
        student_id: str,
        diagnostic: POMDPDiagnostic,
    ) -> Dict[str, Any]:
        """v0.98.0: API 层直接喂 POMDPDiagnostic (非 event 路径), 返回 report.

        复用 _build_report 单一实现 — Parent API 调 Runtime.diagnose_pomdp 拿到
        POMDPDiagnostic 后, 喂给 plugin 让报告逻辑只存在一份 (DRY).
        evolution 不在此喂 (diagnostic 不含 evolution) — 用 ingest_evolution().

        Args:
            student_id: 学生 ID
            diagnostic: POMDPDiagnostic frozen dataclass

        Returns:
            report dict (跟 on_event 返回完全同构, 已缓存到 self._reports[student_id]).
        """
        report = self._build_report(
            student_id=student_id,
            most_likely_idx=diagnostic.most_likely_state,
            min_coverage=int(diagnostic.coverage.min()),
            recent_states=self._reports.get(student_id, {}).get("recent_states", []),
        )
        self._reports[student_id] = report
        return report

    def ingest_evolution(
        self,
        student_id: str,
        evolution: List[Any],
    ) -> Optional[Dict[str, Any]]:
        """v0.98.0: 喂演化序列 (Runtime.diagnose_pomdp_evolution 结果), 更新 report.

        Args:
            student_id: 学生 ID
            evolution: List[POMDPDiagnostic] (frozen dataclass, K=10 FIFO);
                      也兼容 to_dict list (防御性, 逐个解析失败 skip)

        Returns:
            更新后的 report dict; 该学生无已有 report 时返 None
            (evolution 单独无 current_state/coverage 语义, 不新建 report).
        """
        try:
            existing = self._reports.get(student_id)
            if existing is None:
                _log.warning(
                    "ParentEngagementPlugin.ingest_evolution: (sid=%s) 无已有 report, "
                    "先 ingest_diagnostic 再喂 evolution",
                    student_id,
                )
                return None
            recent_states: List[str] = []
            for snap in evolution:
                try:
                    idx = snap.most_likely_state  # POMDPDiagnostic dataclass
                except AttributeError:
                    idx = snap.get("most_likely_state") if isinstance(snap, dict) else None
                if isinstance(idx, int) and 0 <= idx < len(_POMDP_STATE_NAMES):
                    recent_states.append(_POMDP_STATE_NAMES[idx])
            existing["recent_states"] = recent_states
            existing["evolution_count"] = len(recent_states)
            existing["advice"] = self._build_advice(
                current_state=existing["current_state"],
                recent_states=recent_states,
                cold_start=existing["cold_start"],
                state_changed=existing["state_changed"],
            )
            existing["updated_at"] = _dt.now().isoformat()
            return existing
        except Exception:
            _log.warning(
                "ParentEngagementPlugin.ingest_evolution 异常 (sid=%s), skip",
                student_id, exc_info=True,
            )
            return None

    # ---------------------------------------------------------------
    # 查询入口 (UI 可消费)
    # ---------------------------------------------------------------

    def report_for(self, student_id: str) -> Optional[Dict[str, Any]]:
        """v0.98.0: 查询单个学生的家长报告 (UI 可消费入口).

        Returns:
            最近一次 report dict, 或 None (该学生还没有数据).
        """
        return self._reports.get(student_id)

    def get_reports(self) -> Dict[str, Dict[str, Any]]:
        """v0.98.0: 查询全部学生的家长报告 (roster 视图用).

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
        self._last_state_index.clear()

    def disable(self) -> None:
        """Lifecycle: 禁用 plugin (清零 state 缓存, 跟 enable 对称)."""
        self._reports.clear()
        self._last_state_index.clear()


__all__ = ["ParentEngagementPlugin", "COLD_START_COVERAGE_THRESHOLD"]
