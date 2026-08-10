"""Evaluation Engine —— v0.83 Kernel Engine 第 3 个.

对应 kernel-mapping §1.5: "回答 Twin 为何提高 / 哪个 Policy 最好 / 哪个 Goal 完成".

v0.83.0-c 范围: 3 个 evaluator (TwinAttribution + PolicyABTest + GoalCompletion) + EvaluationEngine facade.
"""

from .evaluation_engine import EvaluationConfig, EvaluationEngine
from .goal_completion import GoalCompletion, GoalStatus
from .policy_ab_test import ABTestResult, PolicyABTest
from .twin_attribution import TwinAttribution, TwinAttributionResult

__status__ = "v0.83.0-c"

__all__ = [
    # Facade
    "EvaluationEngine",
    "EvaluationConfig",
    # Twin attribution
    "TwinAttribution",
    "TwinAttributionResult",
    # Policy AB test
    "PolicyABTest",
    "ABTestResult",
    # Goal completion
    "GoalCompletion",
    "GoalStatus",
]
