"""双 Agent 互校包——CTA ↔ LCA 互校循环 + 抗幻觉 + 死锁保护.

对应：
  - research/10-engineering/04-dual-agent-calibration.md v1.0
  - research/00-overview/02-architecture.md §3.3 双 Agent 互校
  - research/00-overview/04-risks.md §A1 + §A4

M2 W4 实现范围（spec §1-5 MVP）：
  - 消息协议（MessageType + CTAOutput + CalibratedLCAResult + Challenge 数据类）
  - 状态机（12 状态）
  - 抗幻觉 3 机制（信念分布检查 + 实验设计验证 + 人工审核触发）
    注：因果归因强制（机制 3）依赖 CTA L4 真实实现，Phase 5+
  - 死锁保护（超时 + 降级）
  - 4 模式（常态 + 信念质疑 + 策略质疑；元反思 Phase 5+）
  - DualAgentOrchestrator 主编排

Phase 5+ 扩展：
  - MetaReflectionMode（4 周停滞检测）
  - CausalAttributionEnforcer
  - PriorityArbitrator
  - 持久化（intervention_history / state_trajectory → DB）
"""

from .anti_hallucination import (
    BeliefDistributionCheck,
    ExperimentDesignValidator,
    HumanReviewConfig,
    HumanReviewTrigger,
)
from .deadlock import SingleAgentFallback, TimeoutGuard
from .modes import (
    BeliefChallengeMode,
    NormalCycle,
    StrategyChallengeMode,
    should_trigger_belief_challenge,
)
from .orchestrator import DualAgentConfig, DualAgentOrchestrator
from .protocol import (
    BeliefChallenge,
    CalibratedLCAResult,
    CalibrationMessage,
    CalibrationState,
    CalibrationStateMachine,
    CTAOutput,
    HumanReviewRequest,
    MessageType,
    PROTOCOL_VERSION,
    StrategyChallenge,
    VersionCompatibility,
)

__status__ = "m2-w4-skeleton"

__all__ = [
    # Orchestrator
    "DualAgentOrchestrator",
    "DualAgentConfig",
    # Protocol
    "MessageType",
    "CTAOutput",
    "CalibratedLCAResult",
    "CalibrationMessage",
    "CalibrationState",
    "CalibrationStateMachine",
    "PROTOCOL_VERSION",
    "VersionCompatibility",
    # Challenges
    "BeliefChallenge",
    "StrategyChallenge",
    "HumanReviewRequest",
    # Modes
    "NormalCycle",
    "BeliefChallengeMode",
    "should_trigger_belief_challenge",
    "StrategyChallengeMode",
    # Anti-hallucination
    "BeliefDistributionCheck",
    "ExperimentDesignValidator",
    "HumanReviewConfig",
    "HumanReviewTrigger",
    # Deadlock
    "TimeoutGuard",
    "SingleAgentFallback",
]