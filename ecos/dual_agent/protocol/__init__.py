"""双 Agent 互校协议子包——消息格式 + 状态机 + 版本."""

from .messages import (
    BeliefChallenge,
    CalibratedLCAResult,
    CalibrationMessage,
    CTAOutput,
    HumanReviewRequest,
    MessageType,
    StrategyChallenge,
)
from .state_machine import CalibrationState, CalibrationStateMachine
from .version import PROTOCOL_VERSION, VersionCompatibility

__all__ = [
    # Messages
    "BeliefChallenge",
    "CalibratedLCAResult",
    "CalibrationMessage",
    "CTAOutput",
    "HumanReviewRequest",
    "MessageType",
    "StrategyChallenge",
    # State machine
    "CalibrationState",
    "CalibrationStateMachine",
    # Version
    "PROTOCOL_VERSION",
    "VersionCompatibility",
]