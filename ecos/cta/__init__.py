"""CTA - Cognitive Twin Agent（认知孪生 Agent）.

负责"理解学生"——像认知科学家 + 心理测量学家一样：
- 维护学生认知状态的信念分布（不是事实判断）
- 基于 BKT/MIRT/DKT + LLM rubric 做状态估计
- 输出每个状态变量的 confidence 和 evidence

核心状态空间：
- 5D 状态：K (Knowledge) / P (Procedure) / S (Strategy) /
            C (Confidence) / X (External Support)
- BloomProfile：6 层认知层级
- LearningDNA：5 维个性化特征
- GrowthTrajectory：成长轨迹

工程文档：research/10-engineering/01-cta-belief-engine.md
M2 W3 状态：5D BeliefState + BKT + 5D MIRT(MAP) + BeliefEngine 编排器
        + LLM Critic（感知层 + 解释层 + Misconception 检测）
        + Content Libraries（30 条 misconception + 8 条 TC + 32 条 Bloom 目标）
"""

from .belief_engine import (
    BeliefEngine,
    BeliefEngineConfig,
    LCAResult,
    Observation,
)
from .belief_state import (
    BeliefState,
    BloomLevel,
    BloomProfileState,
    ConfidenceDimensionState,
    DimensionId,
    DimensionState,
    LearningDNAState,
    MisconceptionHit,
    StateSnapshot,
    TCState,
    TrajectoryState,
)
from .content import (
    MisconceptionEntry,
    MisconceptionLibrary,
    ThresholdConceptEntry,
    ThresholdConceptLibrary,
    TCStatus,
)
from .l1_evolution import (
    BKTModel,
    BKTParams,
    BKTEvolutionLayer,
    EvolutionConfig,
)
from .l2_mirt import (
    BiFactorMIRT5D,
    MIRTConfig,
    MIRTItemParams,
)
from .llm_critic import (
    ExplanationCritic,
    MisconceptionDetector,
    PerceptionCritic,
)

__status__ = "m2-w3-llm-critic"

__all__ = [
    # Engine
    "BeliefEngine",
    "BeliefEngineConfig",
    "Observation",
    "LCAResult",
    # State
    "BeliefState",
    "BloomLevel",
    "BloomProfileState",
    "ConfidenceDimensionState",
    "DimensionId",
    "DimensionState",
    "LearningDNAState",
    "MisconceptionHit",
    "StateSnapshot",
    "TCState",
    "TrajectoryState",
    # Content Libraries
    "MisconceptionEntry",
    "MisconceptionLibrary",
    "ThresholdConceptEntry",
    "ThresholdConceptLibrary",
    "TCStatus",
    # L1 BKT
    "BKTModel",
    "BKTParams",
    "BKTEvolutionLayer",
    "EvolutionConfig",
    # L2 MIRT
    "BiFactorMIRT5D",
    "MIRTConfig",
    "MIRTItemParams",
    # LLM Critic
    "PerceptionCritic",
    "ExplanationCritic",
    "MisconceptionDetector",
]