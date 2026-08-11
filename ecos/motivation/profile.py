"""Motivation Profile —— X 维度抽出, 独立 Profile (v0.87.0-a).

对应 12-kernel-mapping §2.1 Motivation Profile:
    "Frustration / Engagement / Confidence 时序独立组件 (X 维度接近但混在 5D 里)".

v0.87.0-a 范围 (Phase 6+ Kernel 扩展 #2 第 1 个 sub-version):
  - MotivationObservation dataclass (单事件 observation)
  - MotivationProfile dataclass (4 维时序: frustration/engagement/confidence/recent_trajectory)
  - add_observation(obs) 方法 (allowlisted mutation)
  - to_dict / from_dict 序列化 (跟 BeliefState 对称)

设计决策 (Bisen 2026-08-11):
  - X 维度保留 (向后兼容, lbc001/lbc002 历史数据不变)
  - Motivation Profile 独立新增 (渐进迁移)
  - 时序数据: deque(maxlen=100) (跟 FeatureExtractor.response_history 同模式)
  - Evidence 关联: evidence_ids 走现有 Evidence Engine

向后兼容:
  - 默认值 MotivationProfile() (frustration=0.0 / engagement=0.5 / confidence=0.5)
  - 老 JSON snapshot 加载 motivation 兜底为空 dict
  - 防御性自检 [8] 仍 hard block (add_observation 是 allowlist)
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar, Deque, Dict, List, Optional

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MotivationObservation 数据类
# ---------------------------------------------------------------------------

@dataclass
class MotivationObservation:
    """单事件 motivation observation (v0.87.0-a).

    Attributes:
        timestamp:    observation 时间
        signal_type:  "frustration" / "engagement" / "confidence" / "trajectory"
        value:        数值 [0, 1]
        source:       来源 ("runtime" / "llm_critic" / "frontend")
        evidence_id:  关联 Evidence Engine 的 evidence_id (optional)
    """

    VALID_SIGNAL_TYPES: ClassVar[tuple] = ("frustration", "engagement", "confidence", "trajectory")

    timestamp: datetime
    signal_type: str
    value: float
    source: str = "runtime"
    evidence_id: Optional[int] = None

    def __post_init__(self) -> None:
        """v0.87.0-a: 简单 validation."""
        if self.signal_type not in self.VALID_SIGNAL_TYPES:
            _log.warning(
                "MotivationObservation.__post_init__: unknown signal_type=%s, 应为 %s",
                self.signal_type, self.VALID_SIGNAL_TYPES,
            )
        if not (0.0 <= float(self.value) <= 1.0):
            _log.warning(
                "MotivationObservation.__post_init__: value=%s 超出 [0, 1]",
                self.value,
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "signal_type": self.signal_type,
            "value": float(self.value),
            "source": self.source,
            "evidence_id": self.evidence_id,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MotivationObservation":
        ts_str = d.get("timestamp")
        try:
            ts = datetime.fromisoformat(ts_str) if ts_str else datetime.now()
        except (ValueError, TypeError):
            ts = datetime.now()
        return cls(
            timestamp=ts,
            signal_type=str(d.get("signal_type", "trajectory")),
            value=float(d.get("value", 0.0)),
            source=str(d.get("source", "runtime")),
            evidence_id=d.get("evidence_id"),
        )


# ---------------------------------------------------------------------------
# MotivationProfile 数据类
# ---------------------------------------------------------------------------

@dataclass
class MotivationProfile:
    """Motivation Profile (v0.87.0-a).

    4 维时序 (跟 5D 平行, 但独立):
      - frustration:        挫败感 [0, 1] (0=无, 1=极端)
      - engagement:         投入度 [0, 1] (0=无, 1=专注)
      - confidence:         信心 [0, 1] (0=无, 1=充分)
      - recent_trajectory:  最近 100 个 observation (deque[maxlen=100])
      - evidence_ids:       关联 Evidence Engine evidence_id 列表

    默认值:
      - frustration: 0.0 (无挫败)
      - engagement: 0.5 (中性)
      - confidence: 0.5 (中性)
    """

    frustration: float = 0.0
    engagement: float = 0.5
    confidence: float = 0.5
    recent_trajectory: Deque[MotivationObservation] = field(
        default_factory=lambda: deque(maxlen=100),
    )
    evidence_ids: List[int] = field(default_factory=list)

    def add_observation(self, obs: MotivationObservation) -> None:
        """v0.87.0-a: 接收 observation, 更新对应维度 + 追加 trajectory.

        signal_type 映射:
          - "frustration": self.frustration = obs.value
          - "engagement":  self.engagement = obs.value
          - "confidence":  self.confidence = obs.value
          - "trajectory":  仅追加 (不更新 current 状态)

        防御性自检 [8]: 这是 allowlist method (scripts/check_no_direct_state_mutation.py)
        """
        if obs.signal_type == "frustration":
            self.frustration = max(0.0, min(1.0, float(obs.value)))
        elif obs.signal_type == "engagement":
            self.engagement = max(0.0, min(1.0, float(obs.value)))
        elif obs.signal_type == "confidence":
            self.confidence = max(0.0, min(1.0, float(obs.value)))
        elif obs.signal_type == "trajectory":
            pass  # 仅追加
        else:
            _log.warning(
                "MotivationProfile.add_observation: unknown signal_type=%s, 仅追加 trajectory",
                obs.signal_type,
            )

        # 追加 trajectory (deque maxlen=100 自动 truncate)
        self.recent_trajectory.append(obs)

        # 关联 Evidence
        if obs.evidence_id is not None:
            self.evidence_ids.append(obs.evidence_id)

    def to_dict(self) -> Dict[str, Any]:
        """JSON 序列化 (跟 BeliefState.to_dict 对称)."""
        return {
            "frustration": float(self.frustration),
            "engagement": float(self.engagement),
            "confidence": float(self.confidence),
            "recent_trajectory": [obs.to_dict() for obs in self.recent_trajectory],
            "evidence_ids": list(self.evidence_ids),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MotivationProfile":
        """从 dict 反序列化 (跟 BeliefState.from_dict 对称)."""
        trajectory_data = d.get("recent_trajectory", []) or []
        trajectory = deque(maxlen=100)
        for obs_d in trajectory_data:
            if isinstance(obs_d, dict):
                trajectory.append(MotivationObservation.from_dict(obs_d))

        return cls(
            frustration=float(d.get("frustration", 0.0)),
            engagement=float(d.get("engagement", 0.5)),
            confidence=float(d.get("confidence", 0.5)),
            recent_trajectory=trajectory,
            evidence_ids=list(d.get("evidence_ids", [])),
        )


__all__ = [
    "MotivationProfile",
    "MotivationObservation",
]
