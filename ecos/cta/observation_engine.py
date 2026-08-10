"""v0.80.0-c: ObservationEngine - 2.0 §3 Layer 1.

Manages warmup/probe state machine + builds ObservationContext.
Owns _warmup_count, _warmup_pool_cursor, _probe_due_in, _probe_count.

Replaces belief_engine.py:194-260 (warmup/probe methods) + 320-345 (warmup/probe
inline in update()).

Design:
    ObservationEngine.run(student_id, observation, config) -> ObservationContext
    - Increments _warmup_count
    - Updates _probe_due_in (state machine transitions)
    - Derives score/correct/in_warmup/just_exited_warmup/bloom_step
    - Builds ObservationContext (no state mutation on BeliefState)

Critical invariant: ObservationEngine does NOT touch BeliefState.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, TYPE_CHECKING

from .inference_engine import ObservationContext

if TYPE_CHECKING:
    from .belief_engine import BeliefEngineConfig, Observation

logger = logging.getLogger(__name__)


class ObservationEngine:
    """2.0 §3 Layer 1: Observation Engine.

    Owns warmup/probe state machine. Produces ObservationContext for InferenceEngine.
    Does NOT mutate BeliefState.
    """

    def __init__(self) -> None:
        # ── W1 warm-up 状态（W1 2026-07-17 落地）──
        # _warmup_count[student_id] = 已答题数（前 warmup_questions 题为 warm-up 期）
        self._warmup_count: Dict[str, int] = {}
        # _warmup_pool_cursor[student_id] = warm-up 覆盖性选题的轮询游标
        self._warmup_pool_cursor: Dict[str, int] = {}

        # ── W3 探针题状态机（2026-07-17 落地）──
        self._probe_due_in: Dict[str, int] = {}
        self._probe_count: Dict[str, int] = {}

    # ── W1 warm-up 状态机 ──────────────────────────────────────────────────

    def is_warmup(self, student_id: str, config: "BeliefEngineConfig") -> bool:
        """是否处于 warm-up 期（前 N 题）。"""
        return self._warmup_count.get(student_id, 0) < config.warmup_questions

    def warmup_remaining(self, student_id: str, config: "BeliefEngineConfig") -> int:
        """距离 warm-up 结束还剩几题。0 表示刚刚结束。"""
        n = self._warmup_count.get(student_id, 0)
        return max(0, config.warmup_questions - n)

    def warmup_progress(self, student_id: str, config: "BeliefEngineConfig") -> dict:
        """返回 warm-up 状态完整信息（供 API 层使用）。"""
        count = self._warmup_count.get(student_id, 0)
        return {
            "is_warmup": count < config.warmup_questions,
            "warmup_remaining": max(0, config.warmup_questions - count),
            "warmup_total": config.warmup_questions,
            "warmup_count": count,
        }

    # ── W3 探针题状态机 ─────────────────────────────────────────────────────

    def should_probe_now(self, student_id: str, config: "BeliefEngineConfig") -> bool:
        """下次选题是否应插入探针题。"""
        if self.is_warmup(student_id, config):
            return False
        return self._probe_due_in.get(student_id, 0) == 0

    def consume_probe(self, student_id: str, config: "BeliefEngineConfig") -> None:
        """标记"已插入探针题",重置 _probe_due_in 为 probe_interval。"""
        self._probe_count[student_id] = self._probe_count.get(student_id, 0) + 1
        self._probe_due_in[student_id] = config.probe_interval

    def probe_progress(self, student_id: str, config: "BeliefEngineConfig") -> dict:
        """返回探针题状态完整信息（供 API 层使用）。"""
        return {
            "should_probe": self.should_probe_now(student_id, config),
            "probe_due_in": self._probe_due_in.get(student_id, config.probe_interval),
            "probe_interval": config.probe_interval,
            "probe_count": self._probe_count.get(student_id, 0),
        }

    # ── 主入口 ─────────────────────────────────────────────────────────────

    def run(
        self,
        student_id: str,
        observation: "Observation",
        config: "BeliefEngineConfig",
    ) -> ObservationContext:
        """Run observation intake + state machine transitions, return ObservationContext.

        Args:
            student_id: student ID
            observation: raw Observation (skill_id, problem_id, score, correct, bloom_level)
            config: BeliefEngineConfig (for warmup_questions, probe_interval, etc)

        Returns:
            ObservationContext (for InferenceEngine.run())
        """
        skill_id = observation.skill_id
        problem_id = observation.problem_id
        # v0.54.0-d: partial credit score 派生 correct
        #   优先级: observation.score >= 0.6 > observation.correct (老调用兼容)
        #   老调用方只传 correct=True -> score=0.0 -> 派生 correct=False (强制用新 score)
        #   老代码改造: 应同时传 correct=True + score=1.0, 或只传 score=0.7
        score = observation.score if observation.score > 0 else (1.0 if observation.correct else 0.0)
        correct = score >= 0.6
        bloom_level = observation.bloom_level

        # ── W1 warm-up 计数累加（W1 2026-07-17 新增，在 Step 1 之前）──
        self._warmup_count[student_id] = self._warmup_count.get(student_id, 0) + 1
        in_warmup = self.is_warmup(student_id, config)

        # ── W3 探针题状态机触发（W3 2026-07-17 新增）──
        #   - warm-up 期间不触发探针（避免冷启动干扰）
        #   - 刚出 warm-up 期时初始化 _probe_due_in = probe_interval
        #   - 每次 update() 后 _probe_due_in -= 1
        #   - 当 _probe_due_in == 0 时,下次选题应插入探针题
        was_warmup = (
            self._warmup_count[student_id] - 1 < config.warmup_questions
        )  # 上一题是否还在 warm-up
        just_exited_warmup = was_warmup and not in_warmup
        if just_exited_warmup and config.probe_first_after_warmup:
            # 刚出 warm-up 期,初始化 _probe_due_in
            self._probe_due_in[student_id] = config.probe_interval
        elif student_id not in self._probe_due_in and not in_warmup:
            # 异常情况:不在 warm-up 但 _probe_due_in 未初始化（DB 恢复场景）
            self._probe_due_in[student_id] = config.probe_interval

        if student_id in self._probe_due_in:
            self._probe_due_in[student_id] = max(0, self._probe_due_in[student_id] - 1)

        # ── W1 warm-up 期 Bloom 步长切换（更大，让学生感到"在进步"）──
        step = config.warmup_step if in_warmup else config.bloom_update_step

        return ObservationContext(
            student_id=student_id,
            skill_id=skill_id,
            problem_id=problem_id,
            score=score,
            correct=correct,
            bloom_level=bloom_level,
            in_warmup=in_warmup,
            just_exited_warmup=just_exited_warmup,
            bloom_step=step,
            observation=observation,
        )

    def reset_student(self, student_id: str) -> None:
        """重置某学生的 warmup/probe 累积历史。"""
        self._warmup_count.pop(student_id, None)
        self._warmup_pool_cursor.pop(student_id, None)
        self._probe_due_in.pop(student_id, None)
        self._probe_count.pop(student_id, None)
