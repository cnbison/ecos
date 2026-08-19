"""v0.80.0-c: FeatureExtractor - 2.0 §3 Layer 2.

Manages response_history accumulation + mastery_prob_after backfill.
Owns _response_history.

Replaces belief_engine.py:346-366 (response_history accumulation in update()).

Design:
    FeatureExtractor.extract(student_id, observation, ctx) -> {history, history_entry}
    - Appends to _response_history (maxlen=100)
    - Returns full history (for MIRT) + last entry (for mastery_prob_after backfill)

v0.84.0-a: response_history 双写到 event_log (kernel-mapping §2.4 Event 统一输入).
    - _response_history[sid] 保留 (in-memory hot cache cap 100)
    - 同时 emit LearningEvent(event_type="response_submitted") 到 event_log
    - FeatureExtractor 接受 optional event_log 注入 (None = 不 emit)

Critical invariant: FeatureExtractor does NOT touch BeliefState.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .belief_engine import Observation
    from .event_log import EventLog
    from .inference_engine import ObservationContext

logger = logging.getLogger(__name__)


class FeatureExtractor:
    """2.0 §3 Layer 2: Feature Extractor.

    Owns response_history. Produces history list (for MIRT) + history_entry (for backfill).
    Does NOT mutate BeliefState.

    v0.84.0-a: optional event_log injection for response_submitted LearningEvent emit.
    """

    def __init__(self, event_log: Optional["EventLog"] = None) -> None:
        self._response_history: Dict[str, List[Dict[str, Any]]] = {}
        # v0.84.0-a: optional event_log for double-write persistence.
        # None = in-memory only (legacy behavior, tests use this).
        self._event_log = event_log

    def extract(
        self,
        student_id: str,
        observation: "Observation",
        ctx: "ObservationContext",
        log_event: bool = True,
    ) -> Dict[str, Any]:
        """Append to response_history, return history + last entry.

        Args:
            student_id: student ID
            observation: raw Observation (for user_answer, correct_answer, ai_reasoning, timestamp)
            ctx: ObservationContext (for score, correct, bloom_level)

        Returns:
            {"history": List[Dict], "history_entry": Dict or None}
            - history: full list (maxlen=100) for MIRT estimation
            - history_entry: last appended dict, for mastery_prob_after backfill in BeliefUpdator
        """
        problem_id = observation.problem_id
        # Step 2: 累积响应历史（用于 MIRT 估计 + 答题历史详情页 v0.49.2）
        #   v0.49.2: 改 append dict（之前是 3-tuple,缺 user_answer/timestamp）
        #   v0.52.2: 加 ai_reasoning (Bisen 反馈 partial credit 缺失, 短期先存 AI reasoning
        #     留 Phase 5 partial credit 训练用历史数据)
        #   v0.54.0: 加 score 字段 (partial credit)
        #   向后兼容老数据: load 时 _get_or_create_student 会把 3-tuple 迁移成 dict
        #                  老 dict 没 score 字段, Step 3 MIRT 用 h.get("score", h.get("correct", 0)) 兜底
        history = self._response_history.setdefault(student_id, [])
        history.append({
            "problem_id": problem_id,
            "correct": int(ctx.correct),  # 派生自 score >= 0.6, 保留兼容
            "score": float(ctx.score),  # v0.54.0 partial credit
            "bloom_level": str(ctx.bloom_level.name if hasattr(ctx.bloom_level, "name") else ctx.bloom_level),
            "user_answer": observation.user_answer,
            "correct_answer": observation.correct_answer,
            "ai_reasoning": observation.ai_reasoning,
            "timestamp": observation.timestamp.isoformat() if observation.timestamp else None,
        })
        if len(history) > 100:
            self._response_history[student_id] = history[-100:]
            history = self._response_history[student_id]

        # v0.84.0-a: response_history 双写到 event_log (event_type="response_submitted")
        # v0.96.9: log_event=False (replay/simulate) 时不 emit —
        #   旧实现无条件 emit, 被 skill_id 错标掩盖; student_id 修正后污染暴露
        # 防御性自检 [1]: emit 失败不能阻断主流程 (response_history 已 in-memory)
        if self._event_log is not None and log_event:
            try:
                # Lazy import to avoid circular dep at module load
                from .event_log import LearningEvent
                event = LearningEvent.from_response_submitted(
                    observation,
                    source="feature_extractor",
                    student_id=student_id,
                )
                self._event_log.log_event(event)
            except Exception:
                logger.warning(
                    "FeatureExtractor.emit response_submitted 失败 (sid=%s), "
                    "走 in-memory only 兜底",
                    student_id, exc_info=True,
                )

        return {
            "history": history,
            "history_entry": history[-1] if history else None,
        }

    def get_history(self, student_id: str) -> List[Dict[str, Any]]:
        """Get response history for a student (empty list if none)."""
        return self._response_history.get(student_id, [])

    def set_history(self, student_id: str, history: List[Dict[str, Any]]) -> None:
        """Set response history for a student (DB restore path)."""
        self._response_history[student_id] = history

    def reset_student(self, student_id: str) -> None:
        """Reset response history for a student."""
        if student_id in self._response_history:
            del self._response_history[student_id]
