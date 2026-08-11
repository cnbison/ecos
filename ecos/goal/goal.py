"""Goal Ontology — Goal + Capability dataclass.

v0.86.0-a: Phase 6+ Kernel 扩展第 1 个 sub-version.
对应 12-kernel-mapping §2.3 Goal Ontology:
    Capability → Objective → Metric → Evidence

关系:
    - Capability  描述 "这是什么能力" (e.g. "python_variables")
    - Objective   描述 "达到什么目标" (e.g. "apply_variable_concepts")
    - Metric      描述 "如何度量" (e.g. "K.mastery >= 0.7")
    - Evidence    描述 "达成证据" (list of evidence_id, 关联 Evidence Engine)

向后兼容:
    - GoalCompletion.check(state, "K.mastery>=0.7") 字符串路径仍 work (v0.83.0-c)
    - Goal.to_goal_id_str() 输出兼容现有 regex 格式
    - 防御性自检 [8] 仍 hard block (Goal dataclass 不 mutate state)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar, Dict, List, Optional

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Capability:
    """能力描述 (Goal Ontology 起点).

    Attributes:
        name:        能力标识 (e.g. "python_variables")
        description: 能力描述 (e.g. "Python 变量赋值与使用")
        domain:      学科领域 (e.g. "python" / "math" / "physics")
    """

    name: str
    description: str
    domain: str = "general"

    def to_dict(self) -> Dict[str, str]:
        return {
            "name": self.name,
            "description": self.description,
            "domain": self.domain,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Capability":
        return cls(
            name=str(d.get("name", "")),
            description=str(d.get("description", "")),
            domain=str(d.get("domain", "general")),
        )


@dataclass
class Goal:
    """Goal Ontology 单元: Capability → Objective → Metric → Evidence.

    Attributes:
        goal_id:           标识 (e.g. "goal.python_variables.L3")
        capability:        Capability.name (e.g. "python_variables")
        objective:         目标描述 (e.g. "apply_variable_concepts")
        bloom_level:       Bloom 层级 1-6 (default 3 = L3 Apply)
        metric_dimension:  度量维度 ("K" / "Bloom" / "TC")
        metric_threshold:  度量阈值 (e.g. 0.7)
        evidence_ids:      关联 Evidence Engine evidence_id 列表 (v0.83.0-a)
        status:            "active" / "completed" / "abandoned"
        created_at:        创建时间
    """

    # 合法 metric_dimension 值
    VALID_DIMENSIONS: ClassVar[List[str]] = ["K", "Bloom", "TC"]

    goal_id: str
    capability: str
    objective: str
    bloom_level: int = 3
    metric_dimension: str = "K"
    metric_threshold: float = 0.7
    evidence_ids: List[int] = field(default_factory=list)
    status: str = "active"
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        """v0.86.0-a: minimal validation.

        - metric_dimension 必须是 K / Bloom / TC 之一
        - bloom_level 必须在 1-6
        - 其他不强制 (capability / objective 字符串任意)
        """
        if self.metric_dimension not in self.VALID_DIMENSIONS:
            _log.warning(
                "Goal.__post_init__: unknown metric_dimension=%s, 应为 K/Bloom/TC",
                self.metric_dimension,
            )
        if not (1 <= self.bloom_level <= 6):
            _log.warning(
                "Goal.__post_init__: bloom_level=%s 超出 [1,6], skip",
                self.bloom_level,
            )

    def to_goal_id_str(self) -> str:
        """转换成 GoalCompletion.check 兼容的 goal_id 字符串.

        Returns:
            - "K.mastery>={threshold}"            if metric_dimension=="K"
            - "Bloom.L<N>>={threshold}"           if metric_dimension=="Bloom"
            - "TC.{capability}.pass"              if metric_dimension=="TC"

        Raises:
            ValueError: 未知 metric_dimension
        """
        if self.metric_dimension == "K":
            return f"K.mastery>={self.metric_threshold}"
        elif self.metric_dimension == "Bloom":
            return f"Bloom.L{self.bloom_level}>={self.metric_threshold}"
        elif self.metric_dimension == "TC":
            return f"TC.{self.capability}.pass"
        raise ValueError(
            f"Goal.to_goal_id_str: unknown metric_dimension={self.metric_dimension}"
        )

    def to_dict(self) -> Dict[str, Any]:
        """JSON 序列化 (跟 BeliefState.to_dict 对称)."""
        return {
            "goal_id": self.goal_id,
            "capability": self.capability,
            "objective": self.objective,
            "bloom_level": int(self.bloom_level),
            "metric_dimension": self.metric_dimension,
            "metric_threshold": float(self.metric_threshold),
            "evidence_ids": list(self.evidence_ids),
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Goal":
        """从 dict 反序列化 (跟 BeliefState.from_dict 对称)."""
        ts_str = d.get("created_at")
        try:
            ts = datetime.fromisoformat(ts_str) if ts_str else datetime.now()
        except (ValueError, TypeError):
            ts = datetime.now()
        return cls(
            goal_id=str(d.get("goal_id", "")),
            capability=str(d.get("capability", "")),
            objective=str(d.get("objective", "")),
            bloom_level=int(d.get("bloom_level", 3)),
            metric_dimension=str(d.get("metric_dimension", "K")),
            metric_threshold=float(d.get("metric_threshold", 0.7)),
            evidence_ids=list(d.get("evidence_ids", [])),
            status=str(d.get("status", "active")),
            created_at=ts,
        )


__all__ = [
    "Capability",
    "Goal",
]
