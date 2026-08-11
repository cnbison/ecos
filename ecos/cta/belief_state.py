"""CTA BeliefState 数据结构.

对应 research/10-engineering/01-cta-belief-engine.md §2.

5D + BloomProfile + LearningDNA + Trajectory 完整状态对象。
M2 W1 范围：基础 dataclass + 序列化（不实现网络/磁盘持久化，Persistence 层负责）。
"""

from __future__ import annotations

import logging

_log = logging.getLogger(__name__)

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

import numpy as np

# v0.86.0-a: Goal Ontology 关联 (TYPE_CHECKING 避免循环 import)
# BeliefState 持 List[Goal] 实例. Goal dataclass 在 ecos/goal/goal.py, 不引用 BeliefState, 无循环
# 序列化走 Goal.to_dict() / Goal.from_dict()
if TYPE_CHECKING:
    from ..goal.goal import Goal


class BloomLevel(Enum):
    """Bloom 认知层级 L1-L6."""

    REMEMBER = 1
    UNDERSTAND = 2
    APPLY = 3
    ANALYZE = 4
    EVALUATE = 5
    CREATE = 6


class DimensionId(Enum):
    """5D 状态的维度标识."""

    K = "K"  # Knowledge（知识掌握）
    P = "P"  # Procedure（程序技能）
    S = "S"  # Strategy（策略能力）
    C = "C"  # Confidence（认知置信度，含 misconception 折扣）
    X = "X"  # External Support（外部支架）

    @classmethod
    def to_index(cls) -> Dict[str, int]:
        """维度字符 → 5D 向量索引."""
        return {d.value: i for i, d in enumerate(cls)}


DIM_INDEX: Dict[str, int] = DimensionId.to_index()


@dataclass
class DimensionState:
    """单个维度的状态（连续 MIRT θ + 离散 CD-CAT α + 元数据）.

    Attributes:
        theta: MIRT 能力估计（连续值，ℝ）
        se: 标准误
        mastered: CD-CAT 二值掌握判定
        mastery_prob: 掌握概率（α=1 后验）
        confidence: CTA 对该维度估计的置信度 0-1
        evidence_ids: 支撑证据 ID（关联 evidence_log）
        last_updated: 最近一次更新时间
        dimension: 维度字符 'K' / 'P' / 'S' / 'C' / 'X'
    """

    theta: float = 0.0
    se: float = 1.0
    mastered: bool = False
    mastery_prob: float = 0.5
    confidence: float = 0.0
    evidence_ids: List[int] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)
    dimension: str = "K"


@dataclass
class BloomProfileState:
    """BloomProfile 6 层认知层级分布.

    Attributes:
        remember: L1 Remember 掌握概率
        understand: L2 Understand 掌握概率
        apply: L3 Apply 掌握概率
        analyze: L4 Analyze 掌握概率
        evaluate: L5 Evaluate 掌握概率
        create: L6 Create 掌握概率
        dominant_layer: 当前掌握概率最高的层级
        confidence: BloomProfile 整体置信度
        evidence_ids: 支撑证据 ID
    """

    remember: float = 0.5
    understand: float = 0.5
    apply: float = 0.5
    analyze: float = 0.5
    evaluate: float = 0.5
    create: float = 0.5
    dominant_layer: BloomLevel = BloomLevel.UNDERSTAND
    confidence: float = 0.0
    evidence_ids: List[int] = field(default_factory=list)

    def as_vector(self) -> np.ndarray:
        """返回 6 维向量 [L1..L6] 顺序."""
        return np.array([
            self.remember,
            self.understand,
            self.apply,
            self.analyze,
            self.evaluate,
            self.create,
        ])

    def update_dominant(self) -> None:
        """根据 6 层概率重新判定 dominant_layer."""
        probs = self.as_vector()
        # BloomLevel 是 1-indexed，对应数组索引 0..5
        self.dominant_layer = BloomLevel(int(probs.argmax()) + 1)

    def __post_init__(self) -> None:
        """W1（2026-07-17）：初始化时按 6 层概率重新计算 dominant_layer。

        不依赖硬编码默认值（L2 UNDERSTAND），让默认状态由实际数据驱动。
        """
        self.update_dominant()

    def distance_to_next_layer(self) -> dict:
        """计算"距下一层"的距离（W1 2026-07-17 新增）。

        用于 dashboard 展示"当前 Bloom 层 → 下一层"的进步空间。

        Returns:
            {
                "current": str,        # 当前 dominant 层名，如 "L2"
                "current_value": int,  # 当前 dominant 层数值 (1-6)
                "next": str | None,    # 下一层名（L6 时为 None）
                "next_value": int | None,  # 下一层数值
                "current_prob": float, # 当前层掌握概率
                "next_prob": float | None,  # 下一层掌握概率
                "gap": float | None,   # next_prob - current_prob（gap > 0 表示已超过）
            }
        """
        current_val = int(self.dominant_layer.value)
        current_name = f"L{current_val}"
        current_prob = float(self.as_vector()[current_val - 1])

        if current_val >= 6:
            return {
                "current": current_name,
                "current_value": current_val,
                "next": None,
                "next_value": None,
                "current_prob": round(current_prob, 4),
                "next_prob": None,
                "gap": None,
            }

        next_val = current_val + 1
        next_name = f"L{next_val}"
        next_prob = float(self.as_vector()[next_val - 1])
        gap = next_prob - current_prob

        return {
            "current": current_name,
            "current_value": current_val,
            "next": next_name,
            "next_value": next_val,
            "current_prob": round(current_prob, 4),
            "next_prob": round(next_prob, 4),
            "gap": round(gap, 4),
        }


@dataclass
class LearningDNAState:
    """学习者个性化特征.

    v0.1.0 占位：仅 dataclass，真实估计逻辑待 Phase 4+。
    """

    input_preference: str = "visual"  # 'visual' / 'auditory' / 'kinesthetic'
    feedback_preference: str = "immediate"  # 'immediate' / 'delayed'
    fatigue_pattern: Dict[str, float] = field(default_factory=dict)
    error_pattern: List[str] = field(default_factory=list)
    motivation_pattern: Dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0


@dataclass
class StateSnapshot:
    """单次状态快照（轨迹序列中的节点）."""

    timestamp: datetime
    theta_5d: np.ndarray  # 5D 能力向量 [K, P, S, C, X]
    bloom_profile: BloomProfileState
    tc_states: Dict[str, "TCState"] = field(default_factory=dict)
    misc_history: List[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class TrajectoryState:
    """成长轨迹（时间序列）.

    Attributes:
        snapshots: 历史快照（按时间升序，最近 N 次）
        predictions: 未来预测，如 {"4w_bloom_apply": 0.85}
    """

    snapshots: List[StateSnapshot] = field(default_factory=list)
    predictions: Dict[str, float] = field(default_factory=dict)

    def append(self, snapshot: StateSnapshot) -> None:
        self.snapshots.append(snapshot)

    def last_n(self, n: int) -> List[StateSnapshot]:
        return self.snapshots[-n:]


@dataclass
class MisconceptionHit:
    """单次 misconception 命中（v0.5.0 整合）.

    Attributes:
        misc_id: misconception 标识，如 "M1"
        confidence: 命中置信度 0-1
        trigger_problem_id: 触发的题目 ID
        evidence_text: 学生解释文本（LLM Critic 输入）
        timestamp: 命中时间
        correction_strategy: 修正策略 ID
    """

    misc_id: str
    confidence: float
    trigger_problem_id: str
    evidence_text: str
    timestamp: datetime = field(default_factory=datetime.now)
    correction_strategy: str = ""


@dataclass
class TCState:
    """Threshold Concept 状态（v0.5.0 整合）.

    Attributes:
        tc_id: TC 标识，如 "TC_function"
        status: "pre_liminal" / "liminal" / "post_liminal"
        progress: 0-1，跨越进度
        confidence: CTA 对状态的置信度
        liminal_signals: 触发 liminal 的信号列表
        post_liminal_jump_detected: 是否检测到质变
        irreversible: TC 不可逆性
        timestamp: 状态更新时间
        evidence_ids: v0.83.0-b 新增, 关联 Evidence Engine 的 evidence_id 列表
    """

    tc_id: str
    status: str = "pre_liminal"
    progress: float = 0.0
    confidence: float = 0.0
    liminal_signals: List[str] = field(default_factory=list)
    post_liminal_jump_detected: bool = False
    irreversible: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    # v0.83.0-b: 新增 evidence_ids 字段 (关联 Evidence Engine)
    evidence_ids: List[int] = field(default_factory=list)


@dataclass
class ConfidenceDimensionState(DimensionState):
    """C 维度扩展——含 misconception 折扣与 TC 状态.

    在标准 DimensionState 基础上加:
    - misconception_hits: 历史命中记录
    - tc_states: 每个 TC 的状态
    - illusory_confidence_flag: 伪置信标记
    - discount_factor: misconception 折扣（默认 1.0）
    """

    misconception_hits: List[MisconceptionHit] = field(default_factory=list)
    tc_states: Dict[str, TCState] = field(default_factory=dict)
    illusory_confidence_flag: bool = False
    discount_factor: float = 1.0


@dataclass
class BeliefState:
    """完整 CTA 信念状态.

    Attributes:
        student_id: 学生标识
        K/P/S/C/X: 5D 各维度状态
        theta_mean: 5D 联合均值向量 [θ_K, θ_P, θ_S, θ_C, θ_X]
        theta_cov: 5D 联合协方差矩阵 (5x5)
        bloom_profile: BloomProfile 6 层分布
        learning_dna: 学习者个性化特征
        trajectory: 时间序列轨迹
        overall_confidence: 整体置信度 0-1
        last_updated: 最近更新时间
        version: 数据结构版本
    """

    student_id: str
    K: DimensionState = field(default_factory=lambda: DimensionState(dimension="K"))
    P: DimensionState = field(default_factory=lambda: DimensionState(dimension="P"))
    S: DimensionState = field(default_factory=lambda: DimensionState(dimension="S"))
    C: ConfidenceDimensionState = field(default_factory=lambda: ConfidenceDimensionState(dimension="C"))
    X: DimensionState = field(default_factory=lambda: DimensionState(dimension="X"))
    theta_mean: np.ndarray = field(default_factory=lambda: np.zeros(5))
    theta_cov: np.ndarray = field(default_factory=lambda: np.eye(5))
    bloom_profile: BloomProfileState = field(default_factory=BloomProfileState)
    learning_dna: LearningDNAState = field(default_factory=LearningDNAState)
    trajectory: TrajectoryState = field(default_factory=TrajectoryState)
    overall_confidence: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)
    version: str = "v1.0"
    # v0.86.0-a: Goal Ontology 关联 (Phase 6+ Kernel 扩展)
    # 存 Goal 实例 (List["Goal"]), 序列化走 Goal.to_dict() / from_dict()
    # 防御性自检 [8] 仍 hard block: append_goals() 是 allowlisted mutation (跟 append_trajectory_snapshot 模式一致)
    current_goals: List["Goal"] = field(default_factory=list)

    def theta_vector(self) -> np.ndarray:
        """返回 [θ_K, θ_P, θ_S, θ_C, θ_X] 5D 向量."""
        return np.array([self.K.theta, self.P.theta, self.S.theta, self.C.theta, self.X.theta])

    def mastery_vector(self) -> np.ndarray:
        """返回 5D mastery_prob 向量."""
        return np.array([
            self.K.mastery_prob,
            self.P.mastery_prob,
            self.S.mastery_prob,
            self.C.mastery_prob,
            self.X.mastery_prob,
        ])

    def confidence_vector(self) -> np.ndarray:
        """返回 5D confidence 向量."""
        return np.array([
            self.K.confidence,
            self.P.confidence,
            self.S.confidence,
            self.C.confidence,
            self.X.confidence,
        ])

    def snapshot(self) -> StateSnapshot:
        """生成当前状态快照（用于 trajectory 记录）."""
        return StateSnapshot(
            timestamp=self.last_updated,
            theta_5d=self.theta_vector(),
            bloom_profile=self.bloom_profile,
            confidence=self.overall_confidence,
        )

    # ── v0.80.0: StateEngine integration ────────────────────────────────

    def validate(self) -> Tuple[bool, List[str]]:
        """v0.80.0: Schema + range validation.

        Rules:
            - K/P/S/C/X.mastery_prob ∈ [0, 1]
            - K/P/S/C/X.confidence ∈ [0, 1]
            - bloom_profile 6 fields ∈ [0, 1]
            - bloom_profile.confidence ∈ [0, 1]
            - C.discount_factor ∈ [0, 1]
            - C.tc_states[*].progress ∈ [0, 1]
            - C.tc_states[*].confidence ∈ [0, 1]
            - overall_confidence ∈ [0, 1]
            - theta_mean.shape == (5,)
            - theta_cov.shape == (5, 5)

        Returns:
            (is_valid: bool, issues: List[str]) - soft, does NOT raise.
        """
        issues: List[str] = []

        # 5D dim fields
        for dim_name in ("K", "P", "S", "C", "X"):
            dim = getattr(self, dim_name)
            if not (0.0 <= float(dim.mastery_prob) <= 1.0):
                issues.append(f"{dim_name}.mastery_prob={dim.mastery_prob} out of [0,1]")
            if not (0.0 <= float(dim.confidence) <= 1.0):
                issues.append(f"{dim_name}.confidence={dim.confidence} out of [0,1]")

        # C-specific
        if not (0.0 <= float(self.C.discount_factor) <= 1.0):
            issues.append(f"C.discount_factor={self.C.discount_factor} out of [0,1]")
        for tc_id, tc in self.C.tc_states.items():
            if not (0.0 <= float(tc.progress) <= 1.0):
                issues.append(f"C.tc_states[{tc_id}].progress={tc.progress} out of [0,1]")
            if not (0.0 <= float(tc.confidence) <= 1.0):
                issues.append(f"C.tc_states[{tc_id}].confidence={tc.confidence} out of [0,1]")

        # bloom_profile
        for field_name in ("remember", "understand", "apply", "analyze", "evaluate", "create", "confidence"):
            v = getattr(self.bloom_profile, field_name)
            if not (0.0 <= float(v) <= 1.0):
                issues.append(f"bloom_profile.{field_name}={v} out of [0,1]")

        # overall_confidence
        if not (0.0 <= float(self.overall_confidence) <= 1.0):
            issues.append(f"overall_confidence={self.overall_confidence} out of [0,1]")

        # shape constraints
        if self.theta_mean.shape != (5,):
            issues.append(f"theta_mean.shape={self.theta_mean.shape} != (5,)")
        if self.theta_cov.shape != (5, 5):
            issues.append(f"theta_cov.shape={self.theta_cov.shape} != (5,5)")

        return (len(issues) == 0, issues)

    def bump_version(self, event_id: str) -> None:
        """v0.80.0: Update version field with event_id binding.

        Called by StateEngine.commit after applying delta.
        Format: 'v1.0+<event_id>' (e.g. 'v1.0+evt_abc123def456').
        """
        self.version = f"v1.0+{event_id}"
        self.last_updated = datetime.now()

    # ── 序列化（v0.61.0 dual_agent 持久化用）───────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 dict（用于 JSON 持久化 / dual_agent_state 表）.

        v0.61.0 新增：dual_agent 持久化需要 BeliefState 落盘.
        np.ndarray 用 .tolist() 转 Python list, datetime 用 ISO format.

        v0.86.0-a: 加入 current_goals 序列化 (Goal.to_dict()).

        防御性自检：保持跟 dump_state() 调用一致, 字段一一对应.
        """
        return {
            "student_id": self.student_id,
            "K": _dim_to_dict(self.K),
            "P": _dim_to_dict(self.P),
            "S": _dim_to_dict(self.S),
            "C": _conf_dim_to_dict(self.C),
            "X": _dim_to_dict(self.X),
            "theta_mean": self.theta_mean.tolist(),
            "theta_cov": self.theta_cov.tolist(),
            "bloom_profile": _bloom_to_dict(self.bloom_profile),
            "learning_dna": _dna_to_dict(self.learning_dna),
            "trajectory": _traj_to_dict(self.trajectory),
            "overall_confidence": self.overall_confidence,
            "last_updated": self.last_updated.isoformat(),
            "version": self.version,
            "current_goals": [g.to_dict() for g in self.current_goals],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BeliefState":
        """从 dict 反序列化（v0.61.0 dual_agent 持久化 load 用）.

        缺失字段用 default 兜底, 保持跟 to_dict 对称.
        student_id 缺失时 fallback "" (orch.load_state 会用 sid 强制覆盖).

        v0.86.0-a: 恢复 current_goals (Goal.from_dict 还原每条 Goal)
        """
        import numpy as np
        # v0.86.0-a: Goal Ontology 恢复 (lazy import 避免循环)
        from ..goal.goal import Goal
        return cls(
            student_id=d.get("student_id", ""),
            K=_dim_from_dict(d.get("K", {}), default_dim="K"),
            P=_dim_from_dict(d.get("P", {}), default_dim="P"),
            S=_dim_from_dict(d.get("S", {}), default_dim="S"),
            C=_conf_dim_from_dict(d.get("C", {})),
            X=_dim_from_dict(d.get("X", {}), default_dim="X"),
            theta_mean=np.array(d.get("theta_mean", np.zeros(5).tolist())),
            theta_cov=np.array(d.get("theta_cov", np.eye(5).tolist())),
            bloom_profile=_bloom_from_dict(d.get("bloom_profile", {})),
            learning_dna=_dna_from_dict(d.get("learning_dna", {})),
            trajectory=_traj_from_dict(d.get("trajectory", {})),
            overall_confidence=float(d.get("overall_confidence", 0.0)),
            last_updated=_parse_iso(d.get("last_updated")),
            version=d.get("version", "v1.0"),
            current_goals=[Goal.from_dict(g) for g in d.get("current_goals", [])],
        )

    def apply_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """v0.77.1 DB restore entry. v0.80.0 delegates to StateEngine.commit.

        Kept for backward compat:
            - web/api/belief.py:152 calls state.apply_snapshot(snapshot)
            - test_apply_snapshot.py 19 tests call this directly

        v0.80.0: routes through StateEngine._default_engine.commit(state, snapshot, source='db_restore')
        Field application logic lives in _apply_delta_fields (extracted from v0.77.1 body).
        """
        from .state_engine import _default_engine
        _default_engine.commit(self, snapshot, source="db_restore")

    def append_trajectory_snapshot(self, snap: Any) -> None:
        """v0.81.0-d: DB restore path - append trajectory snapshot via allowlisted method.

        Replaces direct `state.trajectory.snapshots.append(snap)` mutation in
        web/api/belief.py:175. Routes through TrajectoryState.append (which is
        the canonical way to add a snapshot, also used by BeliefUpdator.apply step 9).

        Allowlisted in check_no_direct_state_mutation.py FUNC_ALLOWLIST
        (method name match: "append_trajectory_snapshot").
        """
        self.trajectory.append(snap)

    def append_goal(self, goal: Any) -> None:
        """v0.86.0-a: Append Goal to current_goals via allowlisted method.

        取代直接 `state.current_goals.append(goal)` mutation. 跟 append_trajectory_snapshot
        模式一致, allowlisted in check_no_direct_state_mutation.py FUNC_ALLOWLIST.

        Args:
            goal: Goal 实例 (ecos/goal/goal.py). 非法类型 _log.warning 跳过.
        """
        from ..goal.goal import Goal
        if not isinstance(goal, Goal):
            _log.warning(
                "BeliefState.append_goal: 期望 Goal 实例, 实际=%s, skip",
                type(goal).__name__,
            )
            return
        self.current_goals.append(goal)

    def remove_goal(self, goal_id: str) -> bool:
        """v0.86.0-a: 按 goal_id 移除 Goal. 移除成功返回 True, 不存在返回 False.

        允许直接 mutation (跟 discard/remove 模式一致, single-purpose method).
        """
        for i, g in enumerate(self.current_goals):
            if g.goal_id == goal_id:
                self.current_goals.pop(i)
                return True
        return False

    # ---------------------------------------------------------------
    # v0.83.0-b: Belief-Evidence 关联方法 (3 个)
    # ---------------------------------------------------------------

    def add_evidence(self, dim: str, evidence_id: int) -> None:
        """v0.83.0-b: 把 evidence_id 附加到指定维度的 evidence_ids 列表.

        支持维度 (跟 kernel-mapping §2.2.1 一致):
          - "K" / "P" / "S" / "C" / "X" (5D DimensionState)
          - "bloom" (BloomProfileState)
          - "tc_<id>" (TCState, e.g. "tc_python_variables")

        防御性自检 [8] 仍 hard block: 这是允许的 state mutation (BeliefState.add_evidence
        在 allowlist 扩展里, 跟 append_trajectory_snapshot 模式一致).
        """
        if not isinstance(evidence_id, int):
            _log.warning(
                "BeliefState.add_evidence: evidence_id 应为 int, 实际=%s, skip",
                type(evidence_id).__name__,
            )
            return

        if dim in ("K", "P", "S", "C", "X"):
            getattr(self, dim).evidence_ids.append(evidence_id)
        elif dim == "bloom":
            self.bloom_profile.evidence_ids.append(evidence_id)
        elif dim.startswith("tc_"):
            tc_id = dim[3:]
            if tc_id in self.C.tc_states:
                self.C.tc_states[tc_id].evidence_ids.append(evidence_id)
            else:
                _log.warning(
                    "BeliefState.add_evidence: TC id=%s 不在 C.tc_states 中, skip",
                    tc_id,
                )
        else:
            _log.warning("BeliefState.add_evidence: unknown dim=%s, skip", dim)

    def evidence_for(self, dim: str) -> List[int]:
        """v0.83.0-b: 反查 dim 关联的 evidence_ids 列表 (副本).

        支持维度同 add_evidence. 未知 dim 返空 list (不 raise).
        """
        if dim in ("K", "P", "S", "C", "X"):
            return list(getattr(self, dim).evidence_ids)
        elif dim == "bloom":
            return list(self.bloom_profile.evidence_ids)
        elif dim.startswith("tc_"):
            tc_id = dim[3:]
            if tc_id in self.C.tc_states:
                return list(self.C.tc_states[tc_id].evidence_ids)
        return []

    def evidence_summary(self) -> Dict[str, int]:
        """v0.83.0-b: 返回每维度的 evidence_ids 数量 (Twin 概览).

        返回示例:
          {"K": 5, "P": 3, "S": 2, "C": 1, "X": 0, "bloom": 7, "tc": 12}

        用途: 调试面板 / Runtime API evidence_summary 端点 / Twin 一致性校验
              (Phase 6+ 接入, v0.83.0-b 仅做概览).
        """
        return {
            "K": len(self.K.evidence_ids),
            "P": len(self.P.evidence_ids),
            "S": len(self.S.evidence_ids),
            "C": len(self.C.evidence_ids),
            "X": len(self.X.evidence_ids),
            "bloom": len(self.bloom_profile.evidence_ids),
            "tc": sum(len(tc.evidence_ids) for tc in self.C.tc_states.values()),
        }

    def _apply_delta_fields(self, snapshot: Dict[str, Any]) -> None:
        """v0.80.0: extracted from apply_snapshot body. Field application logic.

        接管字段（选择性, snapshot 含哪个就更新哪个, 缺失保留原值）:
            - theta_mean (np.ndarray 5 元素)
            - theta_cov (5x5 协方差, 形状不匹配时跳过)
            - bloom_profile (6 层概率 + confidence + update_dominant)
            - learning_dna (6 字段全)
            - overall_confidence (float)
            - C.tc_states (Dict[str, TCState dict])

        不接管（保留 caller 单独处理）:
            - trajectory: 涉及 snap.bloom_profile 共享当前 state.bloom_profile
            - K/P/S/C/X 的 dim 派生字段: caller 后续重算
            - student_id: caller 控制 sid 兜底
        """
        if "theta_mean" in snapshot:
            self.theta_mean = np.array(snapshot["theta_mean"], dtype=float)
        if "theta_cov" in snapshot:
            cov = snapshot["theta_cov"]
            if (
                isinstance(cov, list)
                and len(cov) == 5
                and all(isinstance(r, list) and len(r) == 5 for r in cov)
            ):
                self.theta_cov = np.array(cov, dtype=float)
        if "bloom_profile" in snapshot:
            bp = snapshot["bloom_profile"]
            self.bloom_profile.remember = float(bp.get("remember", 0.5))
            self.bloom_profile.understand = float(bp.get("understand", 0.5))
            self.bloom_profile.apply = float(bp.get("apply", 0.5))
            self.bloom_profile.analyze = float(bp.get("analyze", 0.5))
            self.bloom_profile.evaluate = float(bp.get("evaluate", 0.5))
            self.bloom_profile.create = float(bp.get("create", 0.5))
            self.bloom_profile.confidence = float(bp.get("confidence", 0.0))
            self.bloom_profile.update_dominant()
        if "learning_dna" in snapshot:
            dna = snapshot["learning_dna"]
            self.learning_dna.input_preference = dna.get("input_preference", "visual")
            self.learning_dna.feedback_preference = dna.get("feedback_preference", "immediate")
            self.learning_dna.fatigue_pattern = dict(dna.get("fatigue_pattern", {}))
            self.learning_dna.error_pattern = list(dna.get("error_pattern", []))
            self.learning_dna.motivation_pattern = dict(dna.get("motivation_pattern", {}))
            self.learning_dna.confidence = float(dna.get("confidence", 0.0))
        if "overall_confidence" in snapshot:
            self.overall_confidence = float(snapshot["overall_confidence"])
        if "C" in snapshot:
            c_data = snapshot.get("C") or {}
            tc_states_data = c_data.get("tc_states", {})
            for tc_id, tc_data in tc_states_data.items():
                ts_str = tc_data.get("timestamp")
                try:
                    ts = datetime.fromisoformat(ts_str) if ts_str else datetime.now()
                except (ValueError, TypeError):
                    ts = datetime.now()
                self.C.tc_states[tc_id] = TCState(
                    tc_id=tc_data.get("tc_id", tc_id),
                    status=tc_data.get("status", "pre_liminal"),
                    progress=float(tc_data.get("progress", 0.0)),
                    confidence=float(tc_data.get("confidence", 0.0)),
                    liminal_signals=list(tc_data.get("liminal_signals", [])),
                    post_liminal_jump_detected=bool(tc_data.get("post_liminal_jump_detected", False)),
                    irreversible=bool(tc_data.get("irreversible", False)),
                    timestamp=ts,
                )
        # v0.86.0-a: 接管 current_goals (Goal Ontology 持久化)
        if "current_goals" in snapshot:
            from ..goal.goal import Goal
            self.current_goals = [
                Goal.from_dict(g) if isinstance(g, dict) else g
                for g in snapshot["current_goals"]
            ]


# ── Helper 序列化函数（BeliefState 嵌套结构用）────────────────────────

def _iso(dt: Any) -> str:
    """datetime → ISO str (None → '')."""
    return dt.isoformat() if dt else ""


def _parse_iso(s: Any) -> Any:
    """ISO str → datetime (None / 空 / 解析失败 → datetime.now())."""
    if not s:
        from datetime import datetime
        return datetime.now()
    try:
        from datetime import datetime
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        from datetime import datetime
        return datetime.now()


def _dim_to_dict(d: Any) -> Dict[str, Any]:
    return {
        "theta": float(d.theta),
        "se": float(d.se),
        "mastered": bool(d.mastered),
        "mastery_prob": float(d.mastery_prob),
        "confidence": float(d.confidence),
        "evidence_ids": list(d.evidence_ids),
        "last_updated": _iso(d.last_updated),
        "dimension": d.dimension,
    }


def _dim_from_dict(d: Dict[str, Any], default_dim: str = "K") -> Any:
    return DimensionState(
        theta=float(d.get("theta", 0.0)),
        se=float(d.get("se", 1.0)),
        mastered=bool(d.get("mastered", False)),
        mastery_prob=float(d.get("mastery_prob", 0.5)),
        confidence=float(d.get("confidence", 0.0)),
        evidence_ids=list(d.get("evidence_ids", [])),
        last_updated=_parse_iso(d.get("last_updated")),
        dimension=d.get("dimension", default_dim),
    )


def _conf_dim_to_dict(c: Any) -> Dict[str, Any]:
    base = _dim_to_dict(c)
    base.update({
        "misconception_hits": [
            {
                "misc_id": h.misc_id,
                "confidence": float(h.confidence),
                "trigger_problem_id": h.trigger_problem_id,
                "evidence_text": h.evidence_text,
                "timestamp": _iso(h.timestamp),
                "correction_strategy": h.correction_strategy,
            }
            for h in c.misconception_hits
        ],
        "tc_states": {
            k: {
                "tc_id": v.tc_id,
                "status": v.status,
                "progress": float(v.progress),
                "confidence": float(v.confidence),
                "liminal_signals": list(v.liminal_signals),
                "post_liminal_jump_detected": bool(v.post_liminal_jump_detected),
                "irreversible": bool(v.irreversible),
                "timestamp": _iso(v.timestamp),
            }
            for k, v in c.tc_states.items()
        },
        "illusory_confidence_flag": bool(c.illusory_confidence_flag),
        "discount_factor": float(c.discount_factor),
    })
    return base


def _conf_dim_from_dict(d: Dict[str, Any]) -> Any:
    base = _dim_from_dict(d, default_dim="C")
    return ConfidenceDimensionState(
        theta=base.theta,
        se=base.se,
        mastered=base.mastered,
        mastery_prob=base.mastery_prob,
        confidence=base.confidence,
        evidence_ids=base.evidence_ids,
        last_updated=base.last_updated,
        dimension=base.dimension,
        misconception_hits=[
            MisconceptionHit(
                misc_id=h["misc_id"],
                confidence=float(h.get("confidence", 0.0)),
                trigger_problem_id=h.get("trigger_problem_id", ""),
                evidence_text=h.get("evidence_text", ""),
                timestamp=_parse_iso(h.get("timestamp")),
                correction_strategy=h.get("correction_strategy", ""),
            )
            for h in d.get("misconception_hits", [])
        ],
        tc_states={
            k: TCState(
                tc_id=v["tc_id"],
                status=v.get("status", "pre_liminal"),
                progress=float(v.get("progress", 0.0)),
                confidence=float(v.get("confidence", 0.0)),
                liminal_signals=list(v.get("liminal_signals", [])),
                post_liminal_jump_detected=bool(v.get("post_liminal_jump_detected", False)),
                irreversible=bool(v.get("irreversible", False)),
                timestamp=_parse_iso(v.get("timestamp")),
            )
            for k, v in d.get("tc_states", {}).items()
        },
        illusory_confidence_flag=bool(d.get("illusory_confidence_flag", False)),
        discount_factor=float(d.get("discount_factor", 1.0)),
    )


def _bloom_to_dict(b: Any) -> Dict[str, Any]:
    return {
        "remember": float(b.remember),
        "understand": float(b.understand),
        "apply": float(b.apply),
        "analyze": float(b.analyze),
        "evaluate": float(b.evaluate),
        "create": float(b.create),
        "dominant_layer": b.dominant_layer.name,
        "confidence": float(b.confidence),
        "evidence_ids": list(b.evidence_ids),
    }


def _bloom_from_dict(d: Dict[str, Any]) -> Any:
    try:
        dominant = BloomLevel[d.get("dominant_layer", "UNDERSTAND")]
    except KeyError:
        dominant = BloomLevel.UNDERSTAND
    return BloomProfileState(
        remember=float(d.get("remember", 0.5)),
        understand=float(d.get("understand", 0.5)),
        apply=float(d.get("apply", 0.5)),
        analyze=float(d.get("analyze", 0.5)),
        evaluate=float(d.get("evaluate", 0.5)),
        create=float(d.get("create", 0.5)),
        dominant_layer=dominant,
        confidence=float(d.get("confidence", 0.0)),
        evidence_ids=list(d.get("evidence_ids", [])),
    )


def _dna_to_dict(d: Any) -> Dict[str, Any]:
    return {
        "input_preference": d.input_preference,
        "feedback_preference": d.feedback_preference,
        "fatigue_pattern": dict(d.fatigue_pattern),
        "error_pattern": list(d.error_pattern),
        "motivation_pattern": dict(d.motivation_pattern),
        "confidence": float(d.confidence),
    }


def _dna_from_dict(d: Dict[str, Any]) -> Any:
    return LearningDNAState(
        input_preference=d.get("input_preference", "visual"),
        feedback_preference=d.get("feedback_preference", "immediate"),
        fatigue_pattern=dict(d.get("fatigue_pattern", {})),
        error_pattern=list(d.get("error_pattern", [])),
        motivation_pattern=dict(d.get("motivation_pattern", {})),
        confidence=float(d.get("confidence", 0.0)),
    )


def _traj_to_dict(t: Any) -> Dict[str, Any]:
    return {
        "snapshots": [
            {
                "timestamp": _iso(s.timestamp),
                "theta_5d": s.theta_5d.tolist() if hasattr(s.theta_5d, "tolist") else list(s.theta_5d),
                "bloom_profile": _bloom_to_dict(s.bloom_profile),
                "tc_states": {
                    k: {
                        "tc_id": v.tc_id,
                        "status": v.status,
                        "progress": float(v.progress),
                        "confidence": float(v.confidence),
                        "liminal_signals": list(v.liminal_signals),
                        "post_liminal_jump_detected": bool(v.post_liminal_jump_detected),
                        "irreversible": bool(v.irreversible),
                        "timestamp": _iso(v.timestamp),
                    }
                    for k, v in s.tc_states.items()
                },
                "misc_history": list(s.misc_history),
                "confidence": float(s.confidence),
            }
            for s in t.snapshots
        ],
        "predictions": dict(t.predictions),
    }


def _traj_from_dict(d: Dict[str, Any]) -> Any:
    import numpy as np
    snapshots = []
    for s in d.get("snapshots", []):
        snapshots.append(StateSnapshot(
            timestamp=_parse_iso(s.get("timestamp")),
            theta_5d=np.array(s.get("theta_5d", np.zeros(5).tolist())),
            bloom_profile=_bloom_from_dict(s.get("bloom_profile", {})),
            confidence=float(s.get("confidence", 0.0)),
        ))
    return TrajectoryState(
        snapshots=snapshots,
        predictions=dict(d.get("predictions", {})),
    )