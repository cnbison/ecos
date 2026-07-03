"""CTA BeliefState 数据结构.

对应 research/10-engineering/01-cta-belief-engine.md §2.

5D + BloomProfile + LearningDNA + Trajectory 完整状态对象。
M2 W1 范围：基础 dataclass + 序列化（不实现网络/磁盘持久化，Persistence 层负责）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List

import numpy as np


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
    """

    tc_id: str
    status: str = "pre_liminal"
    progress: float = 0.0
    confidence: float = 0.0
    liminal_signals: List[str] = field(default_factory=list)
    post_liminal_jump_detected: bool = False
    irreversible: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


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