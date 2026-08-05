"""双 Agent 互校包——CTA ↔ LCA 互校循环 + 抗幻觉 + 死锁保护.

> **v0.75.1 H3 修订说明** (2026-08-04):
> "互校抗 LLM 幻觉" 假设在 D2 + D4 评估后不成立 (D2: 单 Agent 6 Bloom 0.108 ≈ 双 Agent 0.110; D4: H3a 失败, H3b/c 部分通过).
> **互校架构保留**, 实际价值定位调整为: **Fast Calibration (LinUCB 14 题 < 0.15 ECE) + Wide Coverage (100% arm 覆盖) + Adaptive Reward (在线学习)**.
> `anti_hallucination` 子模块名保留 (v0.75.1 docstring 已说明), 模块功能不变.
> 详见 [discussions/2026-08-04-v0751-H3-redefinition-PRD.md](../../discussions/2026-08-04-v0751-H3-redefinition-PRD.md).

对应：
  - research/10-engineering/04-dual-agent-calibration.md v1.0
  - research/00-overview/02-architecture.md §3.3 双 Agent 互校
  - research/00-overview/04-risks.md §A1 + §A4

M2 W4 实现范围 (spec §1-5 MVP):
  - 消息协议 (MessageType + CTAOutput + CalibratedLCAResult + Challenge 数据类)
  - 状态机 (12 状态)
  - 抗幻觉 3 机制 (信念分布检查 + 实验设计验证 + 人工审核触发)
    注：因果归因强制 (机制 3) 依赖 CTA L4 真实实现, Phase 5+
  - 死锁保护 (超时 + 降级)
  - 4 模式 (常态 + 信念质疑 + 策略质疑; 元反思 Phase 5+)
  - DualAgentOrchestrator 主编排

Phase 5+ 扩展：
  - MetaReflectionMode (4 周停滞检测)
  - CausalAttributionEnforcer
  - PriorityArbitrator
  - 持久化 (intervention_history / state_trajectory → DB)
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

__status__ = "v0.59.0-tested-not-wired"

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