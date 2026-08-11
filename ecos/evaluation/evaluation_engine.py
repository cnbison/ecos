"""Evaluation Engine facade —— v0.83.0-c Kernel Engine 第 3 个.

对应 kernel-mapping §1.5: "回答 Twin 为何提高 / 哪个 Policy 最好 / 哪个 Goal 完成".

职责:
  - Twin 变化归因 (TwinAttribution)
  - Policy 对比 (PolicyABTest)
  - Goal completion (GoalCompletion)
  - Unified facade: 3 方法委托 (跟 v0.80 CTA 4-layer / v0.82 LCA 4-layer 模式一致)

设计:
  - EvaluationEngine 是 2.0 §1.5 Engine 之一, 不持有 Belief state
  - 3 个 evaluator 子组件, 通过 kwargs 注入
  - 默认 enable 全 3 evaluator, 可单独 disable
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, List, Optional

from ..cta.belief_state import BeliefState
from .goal_completion import GoalCompletion, GoalStatus
from .policy_ab_test import ABTestResult, PolicyABTest
from .twin_attribution import TwinAttribution, TwinAttributionResult

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# EvaluationConfig
# ---------------------------------------------------------------------------

@dataclass
class EvaluationConfig:
    """Evaluation Engine 配置.

    Attributes:
        enable_twin_attribution: bool  (默认 True, 启用 TwinAttribution)
        enable_policy_ab_test:   bool  (默认 True, 启用 PolicyABTest)
        enable_goal_completion:   bool  (默认 True, 启用 GoalCompletion)
    """

    enable_twin_attribution: bool = True
    enable_policy_ab_test: bool = True
    enable_goal_completion: bool = True


# ---------------------------------------------------------------------------
# EvaluationEngine facade
# ---------------------------------------------------------------------------

class EvaluationEngine:
    """统一 Evaluation Engine facade (v0.83 Kernel Engine 第 3 个).

    用法:
        evaluator = EvaluationEngine(
            config=EvaluationConfig(),
            evidence_engine=engine,  # optional, 来自 v0.83.0-a EvidenceEngine
            lca_engine=lca_engine,  # optional, 来自 v0.82 LCAEngine (for PolicyABTest)
        )
        # 1) Twin 变化归因
        result = evaluator.attribute_state_change(
            student_id="s1", before=before_state, after=after_state, since=...
        )
        # 2) Policy 对比
        ab = evaluator.compare_policies(
            student_id="s1", policy_a="linucb", policy_b="linucb_baseline"
        )
        # 3) Goal completion
        goal = evaluator.check_goal_completion(
            state=state, goal_id="K.mastery>=0.7"
        )

    对应 kernel-mapping §1.5: 回答 "Twin 为何提高 / 哪个 Policy 最好 / 哪个 Goal 完成".
    """

    def __init__(
        self,
        config: Optional[EvaluationConfig] = None,
        evidence_engine: Optional[Any] = None,
        lca_engine: Optional[Any] = None,
    ):
        self.config = config or EvaluationConfig()
        # 3 个 evaluator 子组件 (v0.83.0-c 引入)
        #  evidence_engine optional (用于 TwinAttribution 拉证据来源分布)
        #  lca_engine optional (用于 PolicyABTest 拉历史 reward)
        self.attributor = TwinAttribution(evidence_engine=evidence_engine) if self.config.enable_twin_attribution else None
        self.ab_tester = PolicyABTest(lca_engine=lca_engine) if self.config.enable_policy_ab_test else None
        self.goal_checker = GoalCompletion() if self.config.enable_goal_completion else None

    # ---------------------------------------------------------------
    # 3 个主入口 (委托 3 个 evaluator)
    # ---------------------------------------------------------------

    def attribute_state_change(
        self,
        student_id: str,
        before: BeliefState,
        after: BeliefState,
        since: Optional[Any] = None,
    ) -> TwinAttributionResult:
        """Twin 变化归因 (委托 TwinAttribution).

        Args:
            student_id: 学生 ID
            before:     变化前 BeliefState
            after:      变化后 BeliefState
            since:      起始时间 (optional)

        Returns:
            TwinAttributionResult (含 state_diff + dominant_factor)
        """
        if self.attributor is None:
            _log.warning(
                "EvaluationEngine.attribute_state_change: TwinAttribution 已 disable, 返空结果"
            )
            return TwinAttributionResult(
                student_id=student_id,
                since=since,
                state_diff={},
                evidence_attribution=[],
                dominant_factor="(TwinAttribution disabled)",
            )
        return self.attributor.attribute(student_id, before, after, since)

    def compare_policies(
        self,
        student_id: str,
        policy_a: str,
        policy_b: str,
        events: Optional[List] = None,
    ) -> ABTestResult:
        """Policy 对比 (委托 PolicyABTest)."""
        if self.ab_tester is None:
            _log.warning(
                "EvaluationEngine.compare_policies: PolicyABTest 已 disable, 返空结果"
            )
            return ABTestResult(
                student_id=student_id,
                policy_a=policy_a,
                policy_b=policy_b,
                mean_reward_a=0.0,
                mean_reward_b=0.0,
                n_a=0,
                n_b=0,
                winner=None,
            )
        return self.ab_tester.compare(student_id, policy_a, policy_b, events)

    def check_goal_completion(
        self,
        state: BeliefState,
        goal_or_goal_id: "Union[str, Goal]",  # noqa: F821
    ) -> GoalStatus:
        """Goal 完成判定 (委托 GoalCompletion).

        v0.86.0-d: 接受 Union[str, Goal] (Goal 对象 转 goal_id_str 走 check 路径)
        """
        # v0.86.0-d: lazy import 避免循环
        from ..goal.goal import Goal
        if isinstance(goal_or_goal_id, Goal):
            goal_id = goal_or_goal_id.to_goal_id_str()
        else:
            goal_id = goal_or_goal_id

        if self.goal_checker is None:
            _log.warning(
                "EvaluationEngine.check_goal_completion: GoalCompletion 已 disable, 返未完成"
            )
            return GoalStatus(
                goal_id=goal_id,
                completed=False,
                current_value=0.0,
                target_value=0.0,
                missing_dimensions=["GoalCompletion disabled"],
            )
        return self.goal_checker.check(state, goal_id)


__all__ = [
    "EvaluationEngine",
    "EvaluationConfig",
]
