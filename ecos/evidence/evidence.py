"""Evidence 统一数据结构 —— v0.83 Kernel Engine 第 1 个 (Evidence Engine).

对应:
  - research/00-overview/12-kernel-mapping-current-vs-2.0.md §1.4 Evidence Engine
  - 旧 evidence_log / calibration_log / event_log 散落 5+ 来源
  - v0.83.0-a 目标: 统一 schema + 跨来源查询

设计:
  - 6 顶层字段: evidence_id / source / student_id / timestamp / payload / confidence
  - 4 派生字段: problem_id / skill_id / goal_id / state_delta (从 payload 提取, 索引加速)
  - EvidenceSource 枚举: 5+ 来源 (RESPONSE_HISTORY / CALIBRATION_LOG / PARTIAL_CREDIT /
    LLM_CRITIC / MISCONCEPTION / EVENT_LOG)
  - 5+ 来源 通过 EvidenceEngine._add_to_evidence_log / save_calibration / event_log 落表
    (不破坏现有 schema; db.save_evidence 已于 v0.98.0 删除——重复死路径)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# EvidenceSource 枚举 (5+ 种来源)
# ---------------------------------------------------------------------------

class EvidenceSource(Enum):
    """Evidence 来源枚举 (v0.83.0-a 6 种, v0.84+ 可加).

    Attributes:
        RESPONSE_HISTORY:  答题历史 (来自 web/api/belief.py submit_answer)
        CALIBRATION_LOG:   dual_agent 互校 (来自 web/api/dual_agent.py)
        PARTIAL_CREDIT:    MIRT partial credit (来自 ecos/cta/l2_mirt.py)
        LLM_CRITIC:        LLM Critic (来自 ecos/cta/llm_critic/perception.py)
        MISCONCEPTION:     误概念检测 (来自 ecos/cta/llm_critic/misconception_detector.py)
        EVENT_LOG:         v0.81 LearningEvent 流 (来自 event_log.py)
    """

    RESPONSE_HISTORY = "response_history"
    CALIBRATION_LOG = "calibration_log"
    PARTIAL_CREDIT = "partial_credit"
    LLM_CRITIC = "llm_critic"
    MISCONCEPTION = "misconception"
    EVENT_LOG = "event_log"

    @classmethod
    def from_value(cls, v: str) -> "EvidenceSource":
        """从字符串构造 (兼容 db 读出的 raw string)."""
        for member in cls:
            if member.value == v:
                return member
        raise ValueError(f"Unknown EvidenceSource: {v!r}")


# ---------------------------------------------------------------------------
# Evidence 数据类
# ---------------------------------------------------------------------------

@dataclass
class Evidence:
    """统一 Evidence schema (6 字段 + 4 派生字段).

    Attributes:
        evidence_id:  int  (sqlite PRIMARY KEY AUTOINCREMENT, 写时 None)
        source:       EvidenceSource (5+ 种来源)
        student_id:   str
        timestamp:    datetime
        payload:      dict  (原始数据: observation / message_payload / perception_output)
        confidence:   float  (0-1, optional, 从 payload 派生)
        # 派生字段 (从 payload 提取, 索引加速查询)
        problem_id:   Optional[str]
        skill_id:     Optional[str]
        goal_id:      Optional[str]  # 关联 Goal (v0.83+ Phase 5+ 接入)
        state_delta:  Optional[float]  # 状态变化 (从 state_after - state_before 派生)
    """

    source: EvidenceSource
    student_id: str
    timestamp: datetime
    payload: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5
    evidence_id: Optional[int] = None
    problem_id: Optional[str] = None
    skill_id: Optional[str] = None
    goal_id: Optional[str] = None
    state_delta: Optional[float] = None

    # ---------------------------------------------------------------
    # 序列化
    # ---------------------------------------------------------------

    def to_dict(self) -> dict:
        """序列化为 dict (持久化 / Runtime API / 测试用).

        字段映射:
          - evidence_id / source / student_id / timestamp / confidence 顶层
          - payload 序列化为 payload_json (json.dumps, default=str 处理 datetime)
          - 派生字段 (problem_id / skill_id / goal_id / state_delta) 顶层
        """
        return {
            "evidence_id": self.evidence_id,
            "source": self.source.value,
            "student_id": self.student_id,
            "timestamp": self.timestamp.isoformat(),
            "payload_json": json.dumps(self.payload, default=str),
            "confidence": self.confidence,
            "problem_id": self.problem_id,
            "skill_id": self.skill_id,
            "goal_id": self.goal_id,
            "state_delta": self.state_delta,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Evidence":
        """从 dict 反序列化 (Runtime API / EvidenceEngine 查询结果用)."""
        payload_json = d.get("payload_json", "{}")
        return cls(
            evidence_id=d.get("evidence_id"),
            source=EvidenceSource.from_value(d["source"]),
            student_id=d["student_id"],
            timestamp=datetime.fromisoformat(d["timestamp"]),
            payload=json.loads(payload_json) if isinstance(payload_json, str) else payload_json,
            confidence=d.get("confidence", 0.5),
            problem_id=d.get("problem_id"),
            skill_id=d.get("skill_id"),
            goal_id=d.get("goal_id"),
            state_delta=d.get("state_delta"),
        )


__all__ = [
    "Evidence",
    "EvidenceSource",
]
