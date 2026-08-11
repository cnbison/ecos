"""Goal Ontology — 目标本体 (v0.86.0-a).

对应 12-kernel-mapping §2.3 Goal Ontology:
    Capability → Objective → Metric → Evidence

模块:
    - goal.py:       Goal + Capability dataclass
    - ontology.py:   GoalOntology (singleton + Capability registry + factory)

向后兼容:
    - GoalCompletion.check(state, "K.mastery>=0.7") 字符串路径仍 work (v0.83.0-c)
    - 防御性自检 [8] 仍 hard block (Goal dataclass 不 mutate state)
"""

from .goal import Capability, Goal
from .ontology import GoalOntology, get_default_ontology, reset_default_ontology

__all__ = [
    "Capability",
    "Goal",
    "GoalOntology",
    "get_default_ontology",
    "reset_default_ontology",
]
