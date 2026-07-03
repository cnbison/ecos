"""双 Agent 互校状态机（spec §2.2）.

12 个状态：
  IDLE / CTA_HYPOTHESIS / LCA_EXPERIMENT / OBSERVATION_PENDING /
  CTA_UPDATE / LCA_CAUSAL / LCA_REPLAN / BELIEF_CHALLENGE /
  STRATEGY_CHALLENGE / META_REFLECTION / HUMAN_REVIEW / COMPLETED

转移规则（按 spec §2.2）：
  IDLE → CTA_HYPOTHESIS → LCA_EXPERIMENT → OBSERVATION_PENDING →
  CTA_UPDATE → LCA_CAUSAL → LCA_REPLAN → COMPLETED → IDLE

特殊转移（任意状态可触发）：
  → BELIEF_CHALLENGE（信念质疑）
  → STRATEGY_CHALLENGE（策略质疑）
  → META_REFLECTION（元反思）
  → HUMAN_REVIEW（人工审核）

Phase 4 MVP：
  - 状态机本身完整实现（spec 12 状态 + 转移表）
  - 元反思、人工审核、COMPLETED 状态实现但 Phase 5+ 完整使用
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Optional

from .messages import MessageType


class CalibrationState(Enum):
    """互校状态枚举（spec §2.2）."""

    IDLE = "idle"                              # 空闲，等待下一观测
    CTA_HYPOTHESIS = "cta_hypothesis"          # CTA 提出假设
    LCA_EXPERIMENT = "lca_experiment"          # LCA 设计实验
    OBSERVATION_PENDING = "obs_pending"        # 等待观察结果
    CTA_UPDATE = "cta_update"                  # CTA 更新信念
    LCA_CAUSAL = "lca_causal"                  # LCA 因果归因
    LCA_REPLAN = "lca_replan"                  # LCA 重新规划
    BELIEF_CHALLENGE = "belief_challenge"      # 信念质疑中
    STRATEGY_CHALLENGE = "strategy_challenge"  # 策略质疑中
    META_REFLECTION = "meta_reflection"        # 元反思中
    HUMAN_REVIEW = "human_review"              # 等待人工审核
    COMPLETED = "completed"                    # 本轮互校完成


# 状态转移表（spec §2.2）
# key: (current_state, event_message_type) -> next_state
_TRANSITIONS: Dict[tuple, CalibrationState] = {
    # 常态循环
    (CalibrationState.IDLE, MessageType.CTA_OUTPUT): CalibrationState.CTA_HYPOTHESIS,
    (CalibrationState.CTA_HYPOTHESIS, MessageType.LCA_INTERVENTION): CalibrationState.LCA_EXPERIMENT,
    (CalibrationState.LCA_EXPERIMENT, MessageType.OBSERVATION): CalibrationState.OBSERVATION_PENDING,
    (CalibrationState.OBSERVATION_PENDING, MessageType.CTA_UPDATE): CalibrationState.CTA_UPDATE,
    (CalibrationState.CTA_UPDATE, MessageType.CAUSAL_ATTRIBUTION): CalibrationState.LCA_CAUSAL,
    (CalibrationState.LCA_CAUSAL, MessageType.LCA_INTERVENTION): CalibrationState.LCA_REPLAN,
    (CalibrationState.LCA_REPLAN, MessageType.COMPLETED): CalibrationState.COMPLETED,
    (CalibrationState.COMPLETED, MessageType.CTA_OUTPUT): CalibrationState.IDLE,
    # 特殊转移（从 IDLE 触发）
    (CalibrationState.IDLE, MessageType.BELIEF_CHALLENGE): CalibrationState.BELIEF_CHALLENGE,
    (CalibrationState.IDLE, MessageType.STRATEGY_CHALLENGE): CalibrationState.STRATEGY_CHALLENGE,
    (CalibrationState.IDLE, MessageType.META_REFLECTION): CalibrationState.META_REFLECTION,
    (CalibrationState.IDLE, MessageType.HUMAN_REVIEW_REQUEST): CalibrationState.HUMAN_REVIEW,
    # 完成态可被新事件重置
    (CalibrationState.COMPLETED, MessageType.OBSERVATION): CalibrationState.OBSERVATION_PENDING,
}


class CalibrationStateMachine:
    """互校状态机.

    用法：
        sm = CalibrationStateMachine()
        sm.transition("stu_001", MessageType.CTA_OUTPUT)
        # → CalibrationState.CTA_HYPOTHESIS
    """

    def __init__(self):
        self.state: Dict[str, CalibrationState] = {}  # student_id → 当前状态
        self.history: Dict[str, list] = {}            # student_id → 转移历史

    def current_state(self, student_id: str) -> CalibrationState:
        """获取学生当前互校状态（默认 IDLE）."""
        return self.state.get(student_id, CalibrationState.IDLE)

    def transition(
        self,
        student_id: str,
        event: MessageType,
    ) -> CalibrationState:
        """根据事件转移状态（无匹配规则时保持当前状态）.

        Args:
            student_id: 学生 ID
            event: 触发事件的消息类型

        Returns:
            转移后的 CalibrationState
        """
        current = self.current_state(student_id)
        next_state = _TRANSITIONS.get((current, event), current)
        self.state[student_id] = next_state
        # 记录历史
        self.history.setdefault(student_id, []).append((current, event, next_state))
        return next_state

    def reset(self, student_id: str) -> None:
        """重置学生互校状态（用于降级后恢复）."""
        self.state[student_id] = CalibrationState.IDLE

    def get_history(self, student_id: str) -> list:
        """获取状态转移历史（调试 + 教师后台接口使用）."""
        return list(self.history.get(student_id, []))


__all__ = ["CalibrationState", "CalibrationStateMachine"]