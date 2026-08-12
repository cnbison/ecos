"""v0.91.0-a: Twin → Human Twin 抽象 — CognitiveTwinAgent 数据结构.

对应设计: discussions/2026-08-12-v091-design.md §2.

v0.91.0-a 范围 (Phase 7+ 第 4 个 sub-version, Twin → Human Twin 数据结构):
  - **HumanFeedbackEntry** (frozen dataclass, 跟 AlphaVector frozen 同模式):
    - 4 event_type: hint_requested / idle_detected / goal_changed / reflection_completed
    - payload (Dict[str, Any]) + source (默认 "plugin") + schema_version="0.91.0"
    - to_dict / from_dict round-trip + schema_version 校验
    - from_event(event: LearningEvent) factory (Plugin SDK 4 endpoint 集成)
  - **HumanFeedbackTrajectory** (跟 TrajectoryState 同 pattern, cap 500):
    - entries: List[HumanFeedbackEntry]
    - append(entry) (allowlisted mutation 走 CognitiveTwinAgent.append_human_feedback)
    - last_n(n) + count_by_type(event_type)
  - **CognitiveTwinAgent** (3-tuple 聚合层, 跟 v0.83 Evidence Engine 同 pattern):
    - belief_state: BeliefState (不变)
    - trajectory: TrajectoryState (从 belief_state.trajectory 派生)
    - human_feedback: HumanFeedbackTrajectory (新增)
    - action_history: Optional[Dict] = None (v0.92+ 占位)
    - schema_version="0.91.0"
    - from_state(state: BeliefState) 静态方法 (单一入口)
    - append_human_feedback(entry) allowlisted mutation (defensive check [8])

v0.92.0-a 扩展 (Phase 7+ 第 5 个 sub-version, HumanTwinSnapshot ActionHistory 占位兑现):
  - **ActionEntry** (frozen dataclass): LCA 自动记录的事件 (跟 HumanFeedbackEntry 同模式)
    - 5 action_type: intervention_selected / dual_agent_calibrated / reward_recorded / policy_updated / goal_changed
    - intervention_id (UUID4) + reward (Optional[float]) + metadata (Dict)
    - source 默认 "lca" (LCAEngine 内部), 留 v0.93+ 扩展 "teacher" / "parent"
  - **ActionHistory** (跟 HumanFeedbackTrajectory 同 pattern, cap 500):
    - append(entry) (allowlisted mutation 走 CognitiveTwinAgent.append_action_history)
    - last_n(n) + count_by_type(action_type)
  - **CognitiveTwinAgent 3-tuple → 4-tuple**: action_history 字段从 Optional[Dict]=None 升级为 ActionHistory 实例
  - **append_action_history(entry)** allowlisted mutation (FUNC_ALLOWLIST 扩张)
  - **SCHEMA_VERSION 升级**: "0.91.0" → "0.92.0" (老 snapshot raise per 防御性自检 [5])

不引入 Runtime / LCA / Plugin SDK 修改 (留 b/c/d).

防御性自检:
  - [1] silent pass: 越界 / 非法字段 raise ValueError (跟 POMDPPolicy.update 风格一致)
  - [8] direct state mutation: CognitiveTwinAgent.append_human_feedback + append_action_history 走 allowlist
  - schema_version="0.92.0": 老 snapshot raise ValueError (d 阶段实现 load_state 校验)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

_log = logging.getLogger(__name__)

# v0.91.0-a: 4 事件类型 (跟 LearningEventType 4 frontend stub factory 对齐)
HUMAN_FEEDBACK_EVENT_TYPES = frozenset({
    "hint_requested",
    "idle_detected",
    "goal_changed",
    "reflection_completed",
})

# v0.92.0-a: 5 事件类型 (LCA 自动记录, 跟前 3 维度 human_feedback 主动注入 pattern 不同)
ACTION_HISTORY_EVENT_TYPES = frozenset({
    "intervention_selected",    # LCAEngine.select_intervention Step 7 记录
    "dual_agent_calibrated",   # dual_agent 互校完成 (v0.92+ 接线)
    "reward_recorded",         # LCAEngine.update reward 反馈
    "policy_updated",          # LinUCB / Thompson / POMDP policy update
    "goal_changed",            # 跟 human_feedback.goal_changed 同事件 (LCA 视角)
})

# v0.92.0-a: schema version 升级 (独立版本, 跟 POMDPPolicy SCHEMA_VERSION 同 pattern)
# d 阶段 load_state 校验: 老 "0.91.0" / "0.90.0" / None / 其他 raise ValueError
SCHEMA_VERSION = "0.92.0"

if TYPE_CHECKING:
    from .belief_state import BeliefState, TrajectoryState
    from .event_log import LearningEvent


@dataclass(frozen=True)
class HumanFeedbackEntry:
    """Human-in-loop 信号 (v0.91.0-a).

    4 event_type: hint_requested / idle_detected / goal_changed / reflection_completed.
    source 默认 "plugin" (Plugin SDK 4 endpoint), 留 v0.92+ 扩展 "teacher" / "parent".

    frozen (跟 AlphaVector v0.89.0-a 同模式): 防止外部 mutation 干扰内部状态.
    增量更新走 HumanFeedbackTrajectory.append + CognitiveTwinAgent.append_human_feedback.
    """

    student_id: str
    timestamp: datetime
    event_type: str
    payload: Dict[str, Any]
    source: str = "plugin"
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.event_type not in HUMAN_FEEDBACK_EVENT_TYPES:
            raise ValueError(
                f"HumanFeedbackEntry.event_type 必须是 HUMAN_FEEDBACK_EVENT_TYPES 之一, "
                f"got={self.event_type!r} (valid: {sorted(HUMAN_FEEDBACK_EVENT_TYPES)})"
            )
        if not isinstance(self.payload, dict):
            raise ValueError(
                f"HumanFeedbackEntry.payload 必须是 dict, got type={type(self.payload).__name__}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 dict (用于 JSON 持久化, d 阶段 LCAEngine.dump_state 集成)."""
        return {
            "student_id": self.student_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "payload": dict(self.payload),  # copy 防止外部 mutation
            "source": self.source,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, state: Dict[str, Any]) -> "HumanFeedbackEntry":
        """从 dict 反序列化 + schema_version 校验.

        老 snapshot (None / 其他 schema_version) raise ValueError (per 防御性自检 [5]).
        """
        schema_version = state.get("schema_version")
        if schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"HumanFeedbackEntry.from_dict: 不支持的 schema_version={schema_version!r}, "
                f"expected={SCHEMA_VERSION!r}. 老 snapshot 请升级或丢弃."
            )
        return cls(
            student_id=state["student_id"],
            timestamp=datetime.fromisoformat(state["timestamp"]),
            event_type=state["event_type"],
            payload=dict(state["payload"]),
            source=state.get("source", "plugin"),
        )

    @classmethod
    def from_event(cls, event: "LearningEvent") -> "HumanFeedbackEntry":
        """v0.91.0-b: 从 LearningEvent 构造 HumanFeedbackEntry (Plugin SDK 4 endpoint 集成).

        4 factory 对应:
          - from_hint_requested → HumanFeedbackEntry(event_type="hint_requested", payload={"problem_id", "hint_level"})
          - from_idle_detected → HumanFeedbackEntry(event_type="idle_detected", payload={"idle_seconds"})
          - from_goal_changed → HumanFeedbackEntry(event_type="goal_changed", payload={"old_goal_id", "new_goal_id"})
          - from_reflection_completed → HumanFeedbackEntry(event_type="reflection_completed", payload={"reflection_text", "problem_id"})

        Args:
            event: LearningEvent 实例 (event_type 必须是 4 值之一).

        Returns:
            HumanFeedbackEntry 实例.

        Raises:
            ValueError: event.event_type 不是 4 HUMAN_FEEDBACK_EVENT_TYPES 之一.
        """
        return cls(
            student_id=event.student_id,
            timestamp=event.timestamp,
            event_type=event.event_type,
            payload=dict(event.payload),
            source=event.source,
        )


@dataclass(frozen=True)
class ActionEntry:
    """LCA 自动记录的事件 (v0.92.0-a).

    5 action_type: intervention_selected / dual_agent_calibrated / reward_recorded /
    policy_updated / goal_changed (跟前 3 维度 human_feedback 主动注入 pattern 不同 — action
    由 LCAEngine / dual_agent / PolicyLearner 内部自动记录, 不是 Human-in-loop 信号源).

    frozen (跟 AlphaVector v0.89.0-a + HumanFeedbackEntry v0.91.0-a 同模式).
    增量更新走 ActionHistory.append + CognitiveTwinAgent.append_action_history (allowlist).
    """

    student_id: str
    timestamp: datetime
    action_type: str
    intervention_id: Optional[str] = None  # 关联 Intervention.intervention_id (UUID4 hex)
    reward: Optional[float] = None  # [0, 1], 答对概率 or mastery gain
    metadata: Dict[str, Any] = field(default_factory=dict)  # 扩展字段: expected_gain/risk/audience/policy_type
    source: str = "lca"  # 默认 "lca" (LCAEngine 内部), 留 v0.93+ 扩展 "teacher"/"parent"
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.action_type not in ACTION_HISTORY_EVENT_TYPES:
            raise ValueError(
                f"ActionEntry.action_type 必须是 ACTION_HISTORY_EVENT_TYPES 之一, "
                f"got={self.action_type!r} (valid: {sorted(ACTION_HISTORY_EVENT_TYPES)})"
            )
        if self.reward is not None and not (0.0 <= self.reward <= 1.0):
            raise ValueError(
                f"ActionEntry.reward 必须在 [0, 1], got={self.reward!r}"
            )
        if not isinstance(self.metadata, dict):
            raise ValueError(
                f"ActionEntry.metadata 必须是 dict, got type={type(self.metadata).__name__}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 dict (用于 JSON 持久化, d 阶段 LCAEngine.dump_state 集成)."""
        return {
            "student_id": self.student_id,
            "timestamp": self.timestamp.isoformat(),
            "action_type": self.action_type,
            "intervention_id": self.intervention_id,
            "reward": self.reward,
            "metadata": dict(self.metadata),
            "source": self.source,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, state: Dict[str, Any]) -> "ActionEntry":
        """从 dict 反序列化 + schema_version 校验 (per 防御性自检 [5])."""
        schema_version = state.get("schema_version")
        if schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"ActionEntry.from_dict: 不支持的 schema_version={schema_version!r}, "
                f"expected={SCHEMA_VERSION!r}. 老 snapshot 请升级或丢弃."
            )
        return cls(
            student_id=state["student_id"],
            timestamp=datetime.fromisoformat(state["timestamp"]),
            action_type=state["action_type"],
            intervention_id=state.get("intervention_id"),
            reward=state.get("reward"),
            metadata=dict(state.get("metadata", {})),
            source=state.get("source", "lca"),
        )


@dataclass
class HumanFeedbackTrajectory:
    """Human feedback 轨迹 (v0.91.0-a). 跟 TrajectoryState (belief_state.py:213) 同 pattern.

    cap 500 entries (跟 TrajectoryState maxlen 对齐, per belief_engine.py:167 trajectory_maxlen=500).
    append 是 dataclass mutation, 但调用方走 CognitiveTwinAgent.append_human_feedback (allowlisted)
    走单一入口, 防御性自检 [8] 仍 hard block.

    Attributes:
        entries: 历史 entries (按时间升序, 最近 N 次)
        maxlen:  cap (默认 500, 跟 TrajectoryState 一致)
    """

    entries: List[HumanFeedbackEntry] = field(default_factory=list)
    maxlen: int = 500

    def append(self, entry: HumanFeedbackEntry) -> None:
        """追加 entry, 超 cap 截断 (跟 TrajectoryState.append 同 pattern)."""
        self.entries.append(entry)
        if len(self.entries) > self.maxlen:
            # 截断最老的, 保留最近 maxlen
            self.entries = self.entries[-self.maxlen:]

    def last_n(self, n: int) -> List[HumanFeedbackEntry]:
        """返回最近 n 条 entries (跟 TrajectoryState.last_n 同 pattern)."""
        if n < 0:
            raise ValueError(f"HumanFeedbackTrajectory.last_n: n 必须 >= 0, got={n}")
        return self.entries[-n:]

    def count_by_type(self, event_type: str) -> int:
        """统计指定 event_type 出现次数 (ExperimentDesigner._human_feedback_itype_override 用).

        Args:
            event_type: 4 HUMAN_FEEDBACK_EVENT_TYPES 之一.

        Returns:
            出现次数 (int >= 0).
        """
        if event_type not in HUMAN_FEEDBACK_EVENT_TYPES:
            raise ValueError(
                f"HumanFeedbackTrajectory.count_by_type: event_type 必须是 "
                f"HUMAN_FEEDBACK_EVENT_TYPES 之一, got={event_type!r}"
            )
        return sum(1 for e in self.entries if e.event_type == event_type)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 dict (d 阶段 CognitiveTwinAgent.dump_state 集成)."""
        return {
            "entries": [e.to_dict() for e in self.entries],
            "maxlen": self.maxlen,
            "schema_version": SCHEMA_VERSION,
        }

    @classmethod
    def from_dict(cls, state: Dict[str, Any]) -> "HumanFeedbackTrajectory":
        """从 dict 反序列化 + schema_version 校验 (per 防御性自检 [5])."""
        schema_version = state.get("schema_version")
        if schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"HumanFeedbackTrajectory.from_dict: 不支持的 schema_version={schema_version!r}, "
                f"expected={SCHEMA_VERSION!r}"
            )
        entries = [HumanFeedbackEntry.from_dict(e) for e in state.get("entries", [])]
        maxlen = int(state.get("maxlen", 500))
        return cls(entries=entries, maxlen=maxlen)


@dataclass
class ActionHistory:
    """LCA action 轨迹 (v0.92.0-a). 跟 HumanFeedbackTrajectory (cap 500) 完全同 pattern.

    cap 500 entries (跟 HumanFeedbackTrajectory maxlen 对齐).
    append 是 dataclass mutation, 但调用方走 CognitiveTwinAgent.append_action_history (allowlisted)
    走单一入口, 防御性自检 [8] 仍 hard block.

    Attributes:
        entries: 历史 entries (按时间升序, 最近 N 次)
        maxlen:  cap (默认 500, 跟 HumanFeedbackTrajectory 一致)
    """

    entries: List[ActionEntry] = field(default_factory=list)
    maxlen: int = 500

    def append(self, entry: ActionEntry) -> None:
        """追加 entry, 超 cap 截断 (跟 HumanFeedbackTrajectory.append 同 pattern)."""
        self.entries.append(entry)
        if len(self.entries) > self.maxlen:
            self.entries = self.entries[-self.maxlen:]

    def last_n(self, n: int) -> List[ActionEntry]:
        """返回最近 n 条 entries (跟 HumanFeedbackTrajectory.last_n 同 pattern)."""
        if n < 0:
            raise ValueError(f"ActionHistory.last_n: n 必须 >= 0, got={n}")
        return self.entries[-n:]

    def count_by_type(self, action_type: str) -> int:
        """统计指定 action_type 出现次数.

        Args:
            action_type: 5 ACTION_HISTORY_EVENT_TYPES 之一.

        Returns:
            出现次数 (int >= 0).
        """
        if action_type not in ACTION_HISTORY_EVENT_TYPES:
            raise ValueError(
                f"ActionHistory.count_by_type: action_type 必须是 "
                f"ACTION_HISTORY_EVENT_TYPES 之一, got={action_type!r}"
            )
        return sum(1 for e in self.entries if e.action_type == action_type)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 dict (d 阶段 CognitiveTwinAgent.dump_state 集成)."""
        return {
            "entries": [e.to_dict() for e in self.entries],
            "maxlen": self.maxlen,
            "schema_version": SCHEMA_VERSION,
        }

    @classmethod
    def from_dict(cls, state: Dict[str, Any]) -> "ActionHistory":
        """从 dict 反序列化 + schema_version 校验 (per 防御性自检 [5])."""
        schema_version = state.get("schema_version")
        if schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"ActionHistory.from_dict: 不支持的 schema_version={schema_version!r}, "
                f"expected={SCHEMA_VERSION!r}"
            )
        entries = [ActionEntry.from_dict(e) for e in state.get("entries", [])]
        maxlen = int(state.get("maxlen", 500))
        return cls(entries=entries, maxlen=maxlen)


@dataclass
class CognitiveTwinAgent:
    """Twin → Human Twin 4-tuple 聚合层 (v0.91.0-a → v0.92.0-a 升级).

    聚合 (BeliefState, TrajectoryState, HumanFeedbackTrajectory, ActionHistory):
    - belief_state: 完整 CTA 5D + Bloom + DomainExtension + Motivation 状态 (不变)
    - trajectory:    成长轨迹 (从 belief_state.trajectory 派生, 已内嵌)
    - human_feedback: Human feedback 轨迹 (v0.91.0-a, 4 event_type 跟踪 — Plugin SDK 4 endpoint 主动注入)
    - action_history: LCA action 轨迹 (v0.92.0-a, 5 action_type 跟踪 — LCA 内部自动记录)
    - schema_version: "0.92.0" (独立版本, 跟 POMDPPolicy SCHEMA_VERSION 同 pattern)

    跟 v0.83 Evidence Engine (跨 3 表聚合) 同 pattern: 聚合多个数据源, 单一 facade.
    from_state(state) 静态方法是单一入口, 跟 v0.81 StateEngine.replay + v0.83 EvidenceEngine 同模式.

    防御性自检 [8]: append_human_feedback (v0.91.0-a) + append_action_history (v0.92.0-a) 是 allowlisted
    mutation site (跟 append_trajectory_snapshot / add_evidence / set_domain_extension /
    add_motivation_observation 同模式, FUNC_ALLOWLIST += 扩张).
    """

    belief_state: "BeliefState"
    trajectory: "TrajectoryState"
    human_feedback: HumanFeedbackTrajectory = field(default_factory=HumanFeedbackTrajectory)
    action_history: ActionHistory = field(default_factory=ActionHistory)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        # 防御性: schema_version 必须等于 SCHEMA_VERSION (老 snapshot 走 load_state 校验)
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"CognitiveTwinAgent.schema_version 必须是 {SCHEMA_VERSION!r}, "
                f"got={self.schema_version!r}"
            )
        # 防御性: trajectory 必须等于 belief_state.trajectory (防止两个不同 TrajectoryState)
        # 注: BeliefState.snapshot() 返回新 StateSnapshot, 但 TrajectoryState 引用保持
        if self.trajectory is not self.belief_state.trajectory:
            _log.warning(
                "CognitiveTwinAgent: trajectory (%s) != belief_state.trajectory (%s). "
                "建议 from_state() 单一入口构造, 避免双源不一致.",
                id(self.trajectory), id(self.belief_state.trajectory),
            )

    @staticmethod
    def from_state(state: "BeliefState") -> "CognitiveTwinAgent":
        """v0.91.0-a (3-tuple) → v0.92.0-a (4-tuple) 升级: 从 BeliefState 派生 CognitiveTwinAgent.

        trajectory 从 belief_state.trajectory 直接拿引用 (不复制, 避免双源).
        human_feedback 初始空 (Plugin SDK 4 endpoint 注入走 LCAEngine.append_human_feedback).
        action_history 初始空 (LCA 内部自动记录走 LCAEngine.append_action_history).

        Args:
            state: BeliefState 实例 (cta/belief_state.py).

        Returns:
            CognitiveTwinAgent 4-tuple 聚合.
        """
        return CognitiveTwinAgent(
            belief_state=state,
            trajectory=state.trajectory,
            human_feedback=HumanFeedbackTrajectory(),
            action_history=ActionHistory(),
        )

    def append_human_feedback(self, entry: HumanFeedbackEntry) -> None:
        """v0.91.0-a: 追加 HumanFeedbackEntry (allowlisted mutation site).

        防御性自检 [8]: 这是 CognitiveTwinAgent 的 sole mutation site for human_feedback
        (跟 append_trajectory_snapshot / add_evidence / set_domain_extension /
        add_motivation_observation 同模式). FUNC_ALLOWLIST += "append_human_feedback".

        Plugin SDK 4 endpoint subscriber (v0.91.0-b) → LCAEngine.append_human_feedback
        → CognitiveTwinAgent.append_human_feedback (单一入口).

        Args:
            entry: HumanFeedbackEntry 实例 (frozen, 4 event_type 校验已通过).
        """
        self.human_feedback.append(entry)

    def append_action_history(self, entry: ActionEntry) -> None:
        """v0.92.0-a: 追加 ActionEntry (allowlisted mutation site, 跟 append_human_feedback 同模式).

        防御性自检 [8]: 这是 CognitiveTwinAgent 的 sole mutation site for action_history
        (跟 append_human_feedback / append_trajectory_snapshot / add_evidence /
        set_domain_extension / add_motivation_observation 同模式). FUNC_ALLOWLIST +=
        "append_action_history".

        LCAEngine.append_action_history (v0.92.0-b) → CognitiveTwinAgent.append_action_history
        (单一入口). LCAEngine.select_intervention (Step 7) + update (reward 反馈) 内部调用.

        Args:
            entry: ActionEntry 实例 (frozen, 5 action_type 校验已通过).
        """
        self.action_history.append(entry)

    def dump_state(self) -> Dict[str, Any]:
        """v0.91.0-d → v0.92.0-d 升级: 序列化为 dict (用于 LCAEngine.dump_state + DB 持久化).

        含 4 字段:
          - human_feedback: HumanFeedbackTrajectory.to_dict() (entries + maxlen)
          - action_history: ActionHistory.to_dict() (v0.92.0-a 兑现占位, entries + maxlen)
          - schema_version: "0.92.0"
          - belief_state_ref: str (student_id 引用, 不重复 dump BeliefState — 跟 LCAEngine
                              dump_state 共享)

        Returns:
            Dict 可 JSON 序列化, d 阶段 LCAEngine.dump_state 加 cognitive_twin 字段.
        """
        return {
            "human_feedback": self.human_feedback.to_dict(),
            "action_history": self.action_history.to_dict(),
            "schema_version": self.schema_version,
            "belief_state_ref": self.belief_state.student_id,
        }

    @classmethod
    def load_state(cls, state: Dict[str, Any], belief_state: "BeliefState") -> "CognitiveTwinAgent":
        """v0.91.0-d → v0.92.0-d 升级: 从 dict 反序列化 (LCAEngine.load_state 调).

        Args:
            state: dump_state() 输出 (含 human_feedback / action_history / schema_version / belief_state_ref)
            belief_state: 已恢复的 BeliefState 实例 (外部传入, CognitiveTwinAgent 不自己恢复)

        Returns:
            CognitiveTwinAgent 实例 (4-tuple 聚合, belief_state 用外部传入)

        Raises:
            ValueError: schema_version 不匹配 (per 防御性自检 [5])
        """
        schema_version = state.get("schema_version")
        if schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"CognitiveTwinAgent.load_state: 不支持的 schema_version={schema_version!r}, "
                f"expected={SCHEMA_VERSION!r}. 老 snapshot 请升级或丢弃."
            )
        # human_feedback 解析 (含 entries + schema_version 校验)
        hf_dict = state.get("human_feedback", {})
        human_feedback = HumanFeedbackTrajectory.from_dict(hf_dict)
        # action_history 解析 (v0.92.0-a, 含 entries + schema_version 校验)
        ah_dict = state.get("action_history", {})
        action_history = ActionHistory.from_dict(ah_dict)
        return cls(
            belief_state=belief_state,
            trajectory=belief_state.trajectory,
            human_feedback=human_feedback,
            action_history=action_history,
            schema_version=schema_version,
        )