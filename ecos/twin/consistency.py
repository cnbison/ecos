"""Twin Consistency Check — 跨 Profile 校验 (v0.86.0-b).

对应 12-kernel-mapping §2.1 Twin 一致性保证:
    "K mastery + Bloom L3 + TC 通过 一致性校验".

v0.86.0-b 范围: 5 规则初始版本 (Phase 6 初始).

校验规则:
    1. K.mastery >= 0.7  →  Bloom.L3+_avg >= 0.5       (知识掌握 + 认知层级 一致)
    2. TC.<tc_id>.pass    →  K.mastery >= 0.6          (TC 概念转变 + 知识掌握 一致)
    3. Goal.status="completed"  →  overall_confidence >= 0.7  (目标完成 + 系统把握度 一致)
    4. Bloom.L6+_avg >= 0.5  →  C.confidence >= 0.3    (高阶认知 + 信心 一致)
    5. current_goals 非空  →  至少 1 个 Goal 关联 evidence  (Goal 不悬空)

触发时机: Runtime.plan 选 intervention 前 (per Bisen 决策 2026-08-11)
失败处理: 不阻断 plan, emit goal_changed event + log warning + 走 fallback

向后兼容:
    - goal=None 走 state-only 检查 (v0.85 plan 调用兼容)
    - Checker 只产 result, 不 mutate state (防御性自检 [8] hard block)
    - 5 规则阈值硬编码 (Phase 6 初始), 后续可配置化

设计:
    - TwinConsistencyChecker 类 (无状态, 单实例复用)
    - module-level singleton (懒加载)
    - TwinConsistencyResult dataclass: consistent / violations / recommendation / goal_id
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from ..cta.belief_state import BeliefState
    from ..goal.goal import Goal

_log = logging.getLogger(__name__)


# 5 规则阈值常量 (Phase 6 初始版本, 后续可配置化)
RULE_K_MASTERY_THRESHOLD = 0.7
RULE_K_BLOOM_MIN_AVG = 0.5
RULE_TC_K_MASTERY_MIN = 0.6
RULE_GOAL_COMPLETED_CONFIDENCE_MIN = 0.7
RULE_BLOOM_L6_MIN_AVG = 0.5
RULE_C_CONFIDENCE_MIN = 0.3


@dataclass
class TwinConsistencyResult:
    """Twin Consistency Check 结果.

    Attributes:
        consistent:      True if 0 violations
        violations:      List[str] 每条 violation 一行 (e.g. "K.mastery=0.75 >= 0.7 但 Bloom.L3+_avg=0.4 < 0.5")
        recommendation:  "continue" | "fallback_intervention" | "human_review"
        goal_id:         关联 Goal ID (若传入 goal 参数)
    """

    consistent: bool
    violations: List[str] = field(default_factory=list)
    recommendation: str = "continue"
    goal_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "consistent": self.consistent,
            "violations": list(self.violations),
            "recommendation": self.recommendation,
            "goal_id": self.goal_id,
        }


class TwinConsistencyChecker:
    """Twin Consistency Check 主类 (v0.86.0-b).

    设计:
        - 无状态 (除 5 规则阈值常量), check() 可重入
        - 调用方提供 state (BeliefState) + 可选 goal (Goal)
        - 5 规则相互独立, 顺序无关, 全跑 (累积 violations)
        - 失败时推荐 "fallback_intervention" (默认) 或 "human_review" (Goal 关联 evidence 缺失)

    Usage:
        checker = TwinConsistencyChecker()
        result = checker.check(state)
        if not result.consistent:
            ...
    """

    def check(
        self,
        state: "BeliefState",
        goal: Optional["Goal"] = None,
    ) -> TwinConsistencyResult:
        """检查 Twin 一致性 (5 规则).

        Args:
            state: BeliefState (5D + Bloom + TC + current_goals)
            goal:  可选 Goal (若传, 校验该 Goal 关联 evidence; 若不传, state-level 校验)

        Returns:
            TwinConsistencyResult (consistent / violations / recommendation / goal_id)
        """
        violations: List[str] = []

        # Rule 1: K.mastery >= 0.7 → Bloom.L3+_avg >= 0.5
        violations.extend(self._check_rule_k_bloom(state))

        # Rule 2: TC.<tc_id>.pass → K.mastery >= 0.6
        violations.extend(self._check_rule_tc_k(state))

        # Rule 3: Goal.status="completed" → overall_confidence >= 0.7
        violations.extend(self._check_rule_goal_completed(state))

        # Rule 4: Bloom.L6+_avg >= 0.5 → C.confidence >= 0.3
        violations.extend(self._check_rule_bloom_confidence(state))

        # Rule 5: current_goals 非空 → 至少 1 个 Goal 关联 evidence (or goal 关联 evidence)
        violations.extend(self._check_rule_goals_evidence(state, goal))

        # 推荐: 默认 fallback, Goal evidence 缺失 → human_review
        recommendation = "continue"
        if violations:
            recommendation = "fallback_intervention"
            if any("Goal" in v and "evidence" in v for v in violations):
                recommendation = "human_review"

        return TwinConsistencyResult(
            consistent=(len(violations) == 0),
            violations=violations,
            recommendation=recommendation,
            goal_id=goal.goal_id if goal else None,
        )

    # ── 5 规则检查 (内部方法) ─────────────────────────────────────────

    @staticmethod
    def _check_rule_k_bloom(state: "BeliefState") -> List[str]:
        """Rule 1: K.mastery >= 0.7 → Bloom.L3+_avg >= 0.5."""
        if state.K.mastery_prob >= RULE_K_MASTERY_THRESHOLD:
            # 计算 L3..L6 平均
            bp = state.bloom_profile
            l3_to_l6 = (bp.apply + bp.analyze + bp.evaluate + bp.create) / 4.0
            if l3_to_l6 < RULE_K_BLOOM_MIN_AVG:
                return [
                    f"K.mastery={state.K.mastery_prob:.3f} >= {RULE_K_MASTERY_THRESHOLD} "
                    f"但 Bloom.L3+_avg={l3_to_l6:.3f} < {RULE_K_BLOOM_MIN_AVG}"
                ]
        return []

    @staticmethod
    def _check_rule_tc_k(state: "BeliefState") -> List[str]:
        """Rule 2: TC.<tc_id>.pass → K.mastery >= 0.6."""
        violations = []
        for tc_id, tc in state.C.tc_states.items():
            if tc.status == "post_liminal" and state.K.mastery_prob < RULE_TC_K_MASTERY_MIN:
                violations.append(
                    f"TC.{tc_id}.pass (post_liminal) 但 K.mastery={state.K.mastery_prob:.3f} < {RULE_TC_K_MASTERY_MIN}"
                )
        return violations

    @staticmethod
    def _check_rule_goal_completed(state: "BeliefState") -> List[str]:
        """Rule 3: Goal.status="completed" → overall_confidence >= 0.7."""
        violations = []
        for goal in state.current_goals:
            if goal.status == "completed" and state.overall_confidence < RULE_GOAL_COMPLETED_CONFIDENCE_MIN:
                violations.append(
                    f"Goal.{goal.goal_id}.status=completed 但 overall_confidence={state.overall_confidence:.3f} < {RULE_GOAL_COMPLETED_CONFIDENCE_MIN}"
                )
        return violations

    @staticmethod
    def _check_rule_bloom_confidence(state: "BeliefState") -> List[str]:
        """Rule 4: Bloom.L6+_avg (L5+L6) >= 0.5 → C.confidence >= 0.3."""
        bp = state.bloom_profile
        l6_avg = (bp.evaluate + bp.create) / 2.0
        if l6_avg >= RULE_BLOOM_L6_MIN_AVG and state.C.confidence < RULE_C_CONFIDENCE_MIN:
            return [
                f"Bloom.L6+_avg={l6_avg:.3f} >= {RULE_BLOOM_L6_MIN_AVG} "
                f"但 C.confidence={state.C.confidence:.3f} < {RULE_C_CONFIDENCE_MIN}"
            ]
        return []

    @staticmethod
    def _check_rule_goals_evidence(
        state: "BeliefState",
        goal: Optional["Goal"],
    ) -> List[str]:
        """Rule 5: current_goals 非空 → 至少 1 个 Goal 关联 evidence.

        - goal 传入: 校验该 Goal 关联 evidence (stricter)
        - goal=None: state-level 检查 current_goals 列表
        """
        if goal is not None:
            # 严格: 该 Goal 必须有 evidence
            if not goal.evidence_ids:
                return [f"Goal.{goal.goal_id} 无 evidence 关联 (悬空 Goal)"]
            return []

        # state-level
        if not state.current_goals:
            return []  # 空列表不触发
        has_evidence = any(g.evidence_ids for g in state.current_goals)
        if not has_evidence:
            return [
                f"state.current_goals 含 {len(state.current_goals)} 个 Goal 但都无 evidence 关联"
            ]
        return []


# ── Module-level singleton ─────────────────────────────────────────────

_default_checker: Optional[TwinConsistencyChecker] = None


def get_default_checker() -> TwinConsistencyChecker:
    """获取 process-level singleton (懒加载)."""
    global _default_checker
    if _default_checker is None:
        _default_checker = TwinConsistencyChecker()
    return _default_checker


def reset_default_checker() -> None:
    """清空 singleton (test isolation 用)."""
    global _default_checker
    _default_checker = None


__all__ = [
    "TwinConsistencyChecker",
    "TwinConsistencyResult",
    "get_default_checker",
    "reset_default_checker",
]
