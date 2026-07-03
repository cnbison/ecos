"""双 Agent 互校消息协议——CTA ↔ LCA 通信契约.

对应：
  - research/10-engineering/04-dual-agent-calibration.md §1.5 接口契约 + §2.1 消息格式
  - research/10-engineering/04-dual-agent-calibration.md §3.4-3.5 challenge 数据结构

设计：
  - MessageType 枚举：互校过程中所有消息类型
  - CTAOutput：包装 BeliefState + 互校元数据（CTA → 互校层 → LCA）
  - CalibratedLCAResult：包装 LCA 的 LCAResult + 互校元数据（actual_outcome / causal_effect 等）
  - CalibrationMessage：统一消息格式（用于优先级仲裁、未来持久化）
  - BeliefChallenge / StrategyChallenge / HumanReviewRequest：质疑 + 人工审核消息
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ...cta.belief_state import BeliefState, BloomLevel
from ...lca.intervention import Intervention
from ...lca.l4_optimization.attribution import CausalEffect
from ...lca.orchestrator import LCAResult


class MessageType(Enum):
    """互校消息类型（spec §2.1）."""

    CTA_OUTPUT = "cta_output"                  # CTA 信念输出
    LCA_INTERVENTION = "lca_intervention"      # LCA 干预选择
    OBSERVATION = "observation"                # 观察结果
    CTA_UPDATE = "cta_update"                  # CTA 信念更新
    CAUSAL_ATTRIBUTION = "causal"              # LCA 因果归因
    BELIEF_CHALLENGE = "belief_challenge"      # 信念质疑
    STRATEGY_CHALLENGE = "strategy_challenge"  # 策略质疑
    META_REFLECTION = "meta_reflection"        # 元反思
    HUMAN_REVIEW_REQUEST = "human_review"      # 人工审核请求
    COMPLETED = "completed"                    # 互校完成


# ---------------------------------------------------------------------------
# CTA 输出（包装 BeliefState + 互校元数据）
# ---------------------------------------------------------------------------

@dataclass
class CTAOutput:
    """CTA 输出（互校层契约）.

    Attributes:
        student_id:              学生 ID
        belief_state:            CTA 估计的 BeliefState（M2 W1 数据结构）
        bloom_target_candidates: 候选 Bloom 层（默认全 6 层）
        intervention_hints:      CTA 给 LCA 的干预提示（如"避免高难度题"）
        overall_confidence:      CTA 整体置信度 [0, 1]
        timestamp:               时间戳
        calibration_round:       当前互校轮次（由 orchestrator 填充）
        challenge_history:       历史质疑记录
        belief_challenge_pending:是否有未解决的信念质疑
    """

    student_id: str
    belief_state: BeliefState
    bloom_target_candidates: Optional[List[BloomLevel]] = None
    intervention_hints: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    calibration_round: int = 0
    challenge_history: List[str] = field(default_factory=list)
    belief_challenge_pending: bool = False

    @classmethod
    def from_belief_state(
        cls,
        belief_state: BeliefState,
        calibration_round: int = 0,
        challenge_history: Optional[List[str]] = None,
        intervention_hints: Optional[List[str]] = None,
        belief_challenge_pending: bool = False,
    ) -> "CTAOutput":
        """从 BeliefState 构造 CTAOutput（便捷构造器）."""
        return cls(
            student_id=belief_state.student_id,
            belief_state=belief_state,
            calibration_round=calibration_round,
            challenge_history=list(challenge_history or []),
            intervention_hints=list(intervention_hints or []),
            belief_challenge_pending=belief_challenge_pending,
            timestamp=belief_state.last_updated.timestamp(),
        )

    @property
    def overall_confidence(self) -> float:
        """整体置信度——代理 belief_state.overall_confidence."""
        return self.belief_state.overall_confidence

    def to_dict(self) -> dict:
        """序列化（持久化 / 调试用）."""
        return {
            "student_id": self.student_id,
            "calibration_round": self.calibration_round,
            "overall_confidence": self.overall_confidence,
            "belief_challenge_pending": self.belief_challenge_pending,
            "challenge_history": list(self.challenge_history),
            "intervention_hints": list(self.intervention_hints),
            "bloom_target_candidates": (
                [b.name for b in self.bloom_target_candidates]
                if self.bloom_target_candidates
                else None
            ),
        }


# ---------------------------------------------------------------------------
# 校准后的 LCA 结果
# ---------------------------------------------------------------------------

@dataclass
class CalibratedLCAResult:
    """LCA 输出 + 互校扩展字段（spec §1.5）.

    相比 LCA 自身的 LCAResult，扩展：
      - actual_outcome:          实际观测结果（next observation 后填充）
      - causal_effect:           因果效应估计（CATE）
      - calibration_round:       互校轮次
      - strategy_challenge_pending: 是否有未解决的策略质疑
      - degraded_mode:           是否为降级模式（互校失败时）
      - metadata:                扩展字段（fallback_reason / 警告等）
    """

    student_id: str
    intervention: Intervention
    rationale: str
    expected_gain: float
    expected_risk: float
    bloom_target: BloomLevel
    clt_level: Any  # CLTLevel (avoid circular)
    ca_stage: Any   # CAStage
    timestamp: float = field(default_factory=time.time)
    # 互校扩展字段
    actual_outcome: Optional[float] = None
    causal_effect: Optional[CausalEffect] = None
    calibration_round: int = 0
    strategy_challenge_pending: bool = False
    degraded_mode: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_lca_result(
        cls,
        lca_result: LCAResult,
        calibration_round: int = 0,
        actual_outcome: Optional[float] = None,
        causal_effect: Optional[CausalEffect] = None,
    ) -> "CalibratedLCAResult":
        """从 LCA 的 LCAResult 构造（保持向后兼容）."""
        return cls(
            student_id=lca_result.student_id,
            intervention=lca_result.intervention,
            rationale=lca_result.rationale,
            expected_gain=lca_result.expected_gain,
            expected_risk=lca_result.expected_risk,
            bloom_target=lca_result.bloom_target,
            clt_level=lca_result.clt_level,
            ca_stage=lca_result.ca_stage,
            timestamp=lca_result.timestamp.timestamp(),
            calibration_round=calibration_round,
            actual_outcome=actual_outcome,
            causal_effect=causal_effect,
        )

    def to_dict(self) -> dict:
        """序列化（持久化 / 教师后台接口使用）."""
        return {
            "student_id": self.student_id,
            "intervention": self.intervention.to_dict(),
            "rationale": self.rationale,
            "expected_gain": self.expected_gain,
            "expected_risk": self.expected_risk,
            "bloom_target": self.bloom_target.name,
            "clt_level": self.clt_level.name,
            "ca_stage": self.ca_stage.name,
            "calibration_round": self.calibration_round,
            "actual_outcome": self.actual_outcome,
            "has_causal_effect": self.causal_effect is not None,
            "strategy_challenge_pending": self.strategy_challenge_pending,
            "degraded_mode": self.degraded_mode,
            "metadata": dict(self.metadata),
        }


# ---------------------------------------------------------------------------
# 统一消息格式（spec §2.1）
# ---------------------------------------------------------------------------

@dataclass
class CalibrationMessage:
    """互校消息统一格式（spec §2.1）.

    Attributes:
        message_id:        消息 UUID
        message_type:      消息类型
        student_id:        学生 ID
        timestamp:         unix time
        version:           协议版本
        calibration_round: 互校轮次
        payload:           消息内容（dict）
        priority:          优先级（0=normal, 1=high, 2=critical）
        timeout_sec:       期望响应时间
        metadata:          扩展字段
    """

    message_type: MessageType
    student_id: str
    timestamp: float = field(default_factory=time.time)
    version: str = "v1.0"
    calibration_round: int = 0
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    timeout_sec: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "message_type": self.message_type.value,
            "student_id": self.student_id,
            "timestamp": self.timestamp,
            "version": self.version,
            "calibration_round": self.calibration_round,
            "payload": dict(self.payload),
            "priority": self.priority,
            "timeout_sec": self.timeout_sec,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CalibrationMessage":
        return cls(
            message_id=d.get("message_id", uuid.uuid4().hex[:12]),
            message_type=MessageType(d["message_type"]),
            student_id=d["student_id"],
            timestamp=d.get("timestamp", time.time()),
            version=d.get("version", "v1.0"),
            calibration_round=d.get("calibration_round", 0),
            payload=d.get("payload", {}),
            priority=d.get("priority", 0),
            timeout_sec=d.get("timeout_sec", 30),
            metadata=d.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# Challenge 消息（信念质疑 + 策略质疑）
# ---------------------------------------------------------------------------

@dataclass
class BeliefChallenge:
    """信念质疑消息（LCA → CTA）.

    Attributes:
        student_id:             学生 ID
        challenged_dimension:   被质疑的维度（K/P/S/C/X 或 'bloom_dominant'）
        cta_claim:              CTA 当时声明的值（如 K.theta）
        experimental_evidence:  证据 dict（含 dimension / actual / observed 等）
        confidence_in_evidence: 证据置信度 [0, 1]
        calibration_round:      互校轮次
        resolved:               是否已解决
        belief_change:          解决前后的变化量（解决后填充）
    """

    student_id: str
    challenged_dimension: str
    cta_claim: float
    experimental_evidence: Dict[str, Any]
    confidence_in_evidence: float = 0.8
    calibration_round: int = 0
    resolved: bool = False
    belief_change: Optional[float] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class StrategyChallenge:
    """策略质疑消息（CTA → LCA）.

    Attributes:
        student_id:                   学生 ID
        current_intervention_type:    当前无效干预类型
        cta_suggestion:               CTA 建议的替代
        evidence:                     质疑证据描述
        calibration_round:            互校轮次
        resolved:                     是否已解决
        revised_intervention_id:      调整后的干预 ID（解决后填充）
    """

    student_id: str
    current_intervention_type: str
    cta_suggestion: str
    evidence: str = ""
    calibration_round: int = 0
    resolved: bool = False
    revised_intervention_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class HumanReviewRequest:
    """人工审核请求.

    Attributes:
        student_id:             学生 ID
        reason:                 触发原因
        priority:               优先级（low / normal / high / critical）
        belief_state_snapshot:  触发时的 BeliefState（快照）
        calibration_round:      互校轮次
    """

    student_id: str
    reason: str
    priority: str = "normal"
    belief_state_snapshot: Optional[BeliefState] = None
    calibration_round: int = 0
    timestamp: float = field(default_factory=time.time)


__all__ = [
    "MessageType",
    "CTAOutput",
    "CalibratedLCAResult",
    "CalibrationMessage",
    "BeliefChallenge",
    "StrategyChallenge",
    "HumanReviewRequest",
]