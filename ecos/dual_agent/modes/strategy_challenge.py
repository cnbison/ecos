"""策略质疑模式（spec §3.3）——CTA 发现 LCA 干预无效.

触发条件：最近 N 次干预后 K mastery_prob 平均改善 < 阈值。
触发后：
  - 构造 StrategyChallenge
  - 在 LinUCB 端对当前干预类型 arm 的 A 矩阵放大（降低 UCB）
  - 重新选择替代干预
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from ...lca.orchestrator import LCAEngine
from ...lca.orchestrator import LCAResult
from ...cta.belief_state import BeliefState
from ..protocol.messages import CalibratedLCAResult, StrategyChallenge


# 检测窗口：最近 N 次干预
DETECT_WINDOW = 5
# 平均改善阈值（低于此视为无效）
INEFFECTIVE_GAIN_THRESHOLD = 0.05
# LinUCB A 矩阵放大系数（spec §3.3）
LINUCB_PENALTY_FACTOR = 10.0


class StrategyChallengeMode:
    """策略质疑模式."""

    def __init__(self, lca_engine: LCAEngine):
        self.lca = lca_engine

    def detect_ineffective_intervention(
        self,
        intervention_history: List[CalibratedLCAResult],
        state_trajectory: List[BeliefState],
        window: int = DETECT_WINDOW,
    ) -> bool:
        """检测最近 window 次干预平均改善是否 < 阈值.

        Args:
            intervention_history: 干预历史（CalibratedLCAResult 列表）
            state_trajectory: 状态轨迹（BeliefState 列表，按时间顺序）
            window: 检测窗口大小

        Returns:
            True = 应触发策略质疑
        """
        if len(intervention_history) < window or len(state_trajectory) < window + 1:
            return False

        recent = intervention_history[-window:]
        recent_states = state_trajectory[-(window + 1):]

        # 计算相邻状态之间的 K mastery_prob 变化
        gains = []
        for i in range(len(recent_states) - 1):
            prev = recent_states[i].K.mastery_prob
            curr = recent_states[i + 1].K.mastery_prob
            gains.append(curr - prev)

        avg_gain = sum(gains) / len(gains) if gains else 0.0
        return avg_gain < INEFFECTIVE_GAIN_THRESHOLD

    def challenge_lca(
        self,
        student_id: str,
        intervention_history: List[CalibratedLCAResult],
        calibration_round: int = 0,
    ) -> StrategyChallenge:
        """CTA 发起策略质疑."""
        ineffective_type = intervention_history[-1].intervention.intervention_type.value
        return StrategyChallenge(
            student_id=student_id,
            current_intervention_type=ineffective_type,
            cta_suggestion="切换干预类型或降低目标 Bloom 层",
            evidence=f"最近 {DETECT_WINDOW} 次干预 K mastery 平均改善 < {INEFFECTIVE_GAIN_THRESHOLD}",
            calibration_round=calibration_round,
        )

    def lca_revise_policy(
        self,
        challenge: StrategyChallenge,
        state: BeliefState,
        cta_input,
    ) -> LCAResult:
        """LCA 接受挑战——惩罚当前干预 arm + 重新选择.

        实现：
          1. 在 LinUCB bandit 中放大当前干预类型对应 arm 的 A 矩阵（降低 UCB）
          2. 重新 select_intervention（倾向其他 arm）

        注：M2 W4 简化——直接将整个 bandit 的 A 全部放大（因为 n_arms=10 是候选池而非干预类型），
        实际策略空间索引需要在 Phase 5+ 重构。这里用更简单的方式：在 lca_engine.bandit 的
        _arm_fingerprints 中找到最近一次干预对应的 arm，扩大其 A 矩阵。
        """
        # 简化方案：通过 lca_engine.bandit.bandit 直接放大切换代价
        # （spec §3.3 原意是按 intervention_type，但当前实现按 arm 索引）
        # 取最近一次干预对应的 arm 索引
        last_arm = self.lca.bandit._last_arm
        if last_arm >= 0 and last_arm < len(self.lca.bandit.bandit.A):
            self.lca.bandit.bandit.A[last_arm] *= LINUCB_PENALTY_FACTOR

        # 重新选择
        new_lca_result = self.lca.select_intervention(cta_input)
        challenge.resolved = True
        challenge.revised_intervention_id = new_lca_result.intervention.intervention_id
        return new_lca_result


__all__ = [
    "StrategyChallengeMode",
    "DETECT_WINDOW",
    "INEFFECTIVE_GAIN_THRESHOLD",
]