"""Goal Ontology — capability registry + goal factory.

v0.86.0-a: Phase 6+ Kernel 扩展第 1 个 sub-version.
对应 12-kernel-mapping §2.3 Goal Ontology.

设计:
    - GoalOntology 是 module-level singleton (跨 student 共享)
    - Capability registry: Dict[str, Capability] (全局)
    - 不直接存 per-student goals (per-student list 放 BeliefState.current_goals)
    - 提供 factory methods: from_capability(capability_name, ...) 快速构造 Goal
    - 提供 query / reset (test isolation)

向后兼容:
    - BeliefState.current_goals 是 Goal 的 source of truth (per student)
    - GoalOntology 是辅助 registry + factory, 不引入新 mutation path
    - 防御性自检 [8] 仍 hard block
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from .goal import Capability, Goal

_log = logging.getLogger(__name__)


class GoalOntology:
    """Goal Ontology 辅助类 (singleton).

    用法:
        onto = get_default_ontology()
        onto.register_capability(Capability("python_variables", "...", "python"))
        goal = onto.from_capability("python_variables", metric_dimension="K", threshold=0.7)
        # -> Goal(goal_id="goal.python_variables.L3", capability="python_variables", ...)
    """

    def __init__(self) -> None:
        self._capabilities: Dict[str, Capability] = {}

    # ── Capability registry ────────────────────────────────────────

    def register_capability(self, capability: Capability) -> None:
        """注册 Capability (覆盖式, 同名 cap 替换)."""
        self._capabilities[capability.name] = capability

    def get_capability(self, name: str) -> Optional[Capability]:
        """查 Capability (不存返 None)."""
        return self._capabilities.get(name)

    def has_capability(self, name: str) -> bool:
        return name in self._capabilities

    def list_capabilities(self) -> List[Capability]:
        return list(self._capabilities.values())

    def query_capabilities_by_domain(self, domain: str) -> List[Capability]:
        """按 domain 查 Capability (substring 匹配)."""
        return [c for c in self._capabilities.values() if c.domain == domain]

    # ── Goal factory ───────────────────────────────────────────────

    def from_capability(
        self,
        capability_name: str,
        objective: Optional[str] = None,
        bloom_level: int = 3,
        metric_dimension: str = "K",
        metric_threshold: float = 0.7,
        goal_id: Optional[str] = None,
    ) -> Goal:
        """从 Capability 构造 Goal.

        Args:
            capability_name: Capability.name (必须已 register)
            objective:       目标描述 (None 则用 f"achieve_{capability_name}")
            bloom_level:     Bloom 层级 1-6 (default 3 = L3 Apply)
            metric_dimension: "K" / "Bloom" / "TC"
            metric_threshold: 度量阈值
            goal_id:         标识 (None 则用 f"goal.{capability_name}.L{bloom_level}")

        Returns:
            Goal dataclass

        Raises:
            ValueError: capability_name 未注册
        """
        if capability_name not in self._capabilities:
            raise ValueError(
                f"GoalOntology.from_capability: capability={capability_name} 未注册"
            )
        if objective is None:
            objective = f"achieve_{capability_name}"
        if goal_id is None:
            goal_id = f"goal.{capability_name}.L{bloom_level}"
        return Goal(
            goal_id=goal_id,
            capability=capability_name,
            objective=objective,
            bloom_level=bloom_level,
            metric_dimension=metric_dimension,
            metric_threshold=metric_threshold,
        )

    # ── Test isolation ─────────────────────────────────────────────

    def reset(self) -> None:
        """清空 Capability registry (test isolation 用)."""
        self._capabilities.clear()


# ── Module-level singleton ─────────────────────────────────────────────

_default_ontology: Optional[GoalOntology] = None


def get_default_ontology() -> GoalOntology:
    """获取 process-level singleton (懒加载)."""
    global _default_ontology
    if _default_ontology is None:
        _default_ontology = GoalOntology()
    return _default_ontology


def reset_default_ontology() -> None:
    """清空 singleton (test isolation 用)."""
    global _default_ontology
    _default_ontology = None


__all__ = [
    "GoalOntology",
    "get_default_ontology",
    "reset_default_ontology",
]
