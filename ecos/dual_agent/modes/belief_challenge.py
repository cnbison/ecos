"""信念质疑模式（spec §3.2）——LCA 不认同 CTA 状态判断.

触发条件（M2 W4）：
  1. CTA 高置信度但学生实际答错（K.mastery_prob > 0.7 + correct=False）
  2. BloomProfile dominant_layer 在短时间内突变（前后 > 2 层差）
  3. CTA 预测 high P 但 response_time 异常（> 60s）

触发后：
  - 构造 BeliefChallenge 消息
  - 标记 CTAOutput.belief_challenge_pending = True
  - 用新 observation 让 CTA 重新估计
  - 对比前后信念变化，记录到 challenge_history
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ...cta.belief_engine import BeliefEngine
from ...cta.belief_state import BeliefState, BloomLevel
from ..protocol.messages import BeliefChallenge, CTAOutput


# 高置信度阈值（CTA 自信但答错 → 触发质疑）
HIGH_CONFIDENCE_THRESHOLD = 0.7
# BloomProfile dominant_layer 突变阈值
BLOOM_JUMP_THRESHOLD = 2
# P 维度高 + 答题慢阈值
HIGH_P_THRESHOLD = 0.6
SLOW_RESPONSE_THRESHOLD_SEC = 60.0


def should_trigger_belief_challenge(
    cta_output: CTAOutput,
    new_observation,
    prev_dominant_layer: Optional[BloomLevel] = None,
) -> Tuple[bool, Optional[str]]:
    """判断是否应触发信念质疑.

    Returns:
        (should_trigger, dimension)：
          - should_trigger: True 表示应触发
          - dimension: 被质疑的维度（'K' / 'bloom_dominant' / 'P'）
    """
    bs = cta_output.belief_state

    # 规则 1：K 高 mastery 但答错
    if bs.K.mastery_prob > HIGH_CONFIDENCE_THRESHOLD and not new_observation.correct:
        return True, "K"

    # 规则 2：BloomProfile dominant_layer 突变
    if prev_dominant_layer is not None:
        curr = bs.bloom_profile.dominant_layer
        diff = abs(curr.value - prev_dominant_layer.value)
        if diff >= BLOOM_JUMP_THRESHOLD:
            return True, "bloom_dominant"

    # 规则 3：CTA 高估 P + 答题慢
    if (
        bs.P.mastery_prob > HIGH_P_THRESHOLD
        and new_observation.response_time_sec > SLOW_RESPONSE_THRESHOLD_SEC
    ):
        return True, "P"

    return False, None


@dataclass
class BeliefChallengeMode:
    """信念质疑模式（CTA 重新审视 + 记录质疑历史）."""

    cta_engine: BeliefEngine

    def trigger_challenge(
        self,
        cta_output: CTAOutput,
        new_observation,
        challenged_dimension: str,
    ) -> BeliefChallenge:
        """构造 BeliefChallenge 消息.

        Args:
            cta_output: 当前 CTA 输出
            new_observation: 触发质疑的新观测
            challenged_dimension: 'K' / 'P' / 'S' / 'C' / 'X' / 'bloom_dominant'

        Returns:
            BeliefChallenge 对象
        """
        bs = cta_output.belief_state
        # 提取被质疑维度的当前值
        if challenged_dimension == "bloom_dominant":
            cta_claim = float(bs.bloom_profile.dominant_layer.value)
        else:
            cta_claim = float(getattr(bs, challenged_dimension).theta)

        challenge = BeliefChallenge(
            student_id=cta_output.student_id,
            challenged_dimension=challenged_dimension,
            cta_claim=cta_claim,
            experimental_evidence={
                "dimension": challenged_dimension,
                "correct": new_observation.correct,
                "problem_id": new_observation.problem_id,
                "response_time_sec": new_observation.response_time_sec,
                "skill_id": new_observation.skill_id,
            },
            confidence_in_evidence=0.8 if not new_observation.correct else 0.5,
            calibration_round=cta_output.calibration_round,
        )
        cta_output.belief_challenge_pending = True
        return challenge

    def resolve_challenge(
        self,
        cta_output: CTAOutput,
        challenge: BeliefChallenge,
        new_observation,
        prev_state: BeliefState,
        new_state: BeliefState,
    ) -> CTAOutput:
        """CTA 重新审视信念并更新 challenge_history.

        Args:
            cta_output: 当前 CTA 输出
            challenge: 待解决的 BeliefChallenge
            new_observation: 新观测
            prev_state: 质疑前的 BeliefState
            new_state: 重新 CTA.update 后的 BeliefState

        Returns:
            更新后的 CTAOutput（belief_challenge_pending=False, challenge_history 追加一条）
        """
        # 对比前后信念
        dim_name = challenge.challenged_dimension
        if dim_name == "bloom_dominant":
            old_value = float(challenge.cta_claim)
            new_value = float(new_state.bloom_profile.dominant_layer.value)
        else:
            old_value = float(challenge.cta_claim)
            new_dim = getattr(new_state, dim_name, None)
            new_value = float(new_dim.theta) if new_dim else old_value
        belief_change = abs(new_value - old_value)

        # 记录到 challenge_history
        cta_output.challenge_history.append(
            f"{dim_name}: {old_value:.3f} → {new_value:.3f} (Δ={belief_change:.3f})"
        )
        cta_output.belief_challenge_pending = False
        challenge.resolved = True
        challenge.belief_change = belief_change

        # 更新 CTAOutput 的 belief_state 引用
        cta_output.belief_state = new_state
        return cta_output


__all__ = [
    "BeliefChallengeMode",
    "should_trigger_belief_challenge",
    "HIGH_CONFIDENCE_THRESHOLD",
    "BLOOM_JUMP_THRESHOLD",
]