"""BeliefEngine Web 封装——会话状态管理 + API 集成。

每个学生 ID 对应一个 BeliefEngine 实例 + 当前 BeliefState（内存中）。
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig, Observation
from ecos.cta.belief_state import BloomLevel, BeliefState
from ecos.cta.content import PYTHON_BASICS_MISCONCEPTION_LIBRARY_STR
from ecos.cta.l1_evolution import EvolutionConfig
from ecos.cta.l2_mirt import MIRTConfig
from ecos.llm_client import ECOSLLMClient

# 全局状态映射（student_id → {engine, state}）
_STUDENT_STATES: dict[str, dict] = {}


def _get_or_create_student(student_id: str) -> dict:
    if student_id not in _STUDENT_STATES:
        mirt_config = MIRTConfig(
            prior_mean=np.zeros(5),
            prior_cov=np.eye(5),
            default_a_specialized=np.ones(5) * 0.8,
            default_a_general=0.5,
            default_difficulty=0.0,
        )
        config = BeliefEngineConfig(
            evolution_config=EvolutionConfig(),
            mirt_config=mirt_config,
        )
        engine = BeliefEngine(config=config)
        state = engine.create_initial_state(student_id)
        _STUDENT_STATES[student_id] = {"engine": engine, "state": state}
    return _STUDENT_STATES[student_id]


def get_student_state(student_id: str) -> dict[str, Any]:
    """获取学生当前 5D 信念状态。"""
    student = _get_or_create_student(student_id)
    state = student["state"]
    theta = state.theta_mean
    dims = ["K", "P", "S", "C", "X"]
    bloom = state.bloom_profile

    return {
        "student_id": student_id,
        "theta": {dims[i]: round(float(theta[i]), 4) for i in range(5)},
        "bloom_profile": {
            "dominant": bloom.dominant_layer.name if bloom.dominant_layer else None,
            "bloom_levels": {
                "L1": round(float(bloom.remember), 3),
                "L2": round(float(bloom.understand), 3),
                "L3": round(float(bloom.apply), 3),
                "L4": round(float(bloom.analyze), 3),
            },
        },
        "overall_confidence": round(state.overall_confidence, 4),
        "c_discount_factor": round(
            state.C.discount_factor if hasattr(state.C, "discount_factor") else 1.0, 3
        ),
    }


def submit_answer(
    student_id: str,
    problem_id: str,
    skill_id: str,
    correct: bool,
    bloom_layer: str,
    explanation_text: str = "",
) -> dict[str, Any]:
    """提交答案 → BeliefEngine.update() → 返回干预建议（如果需要）。"""
    student = _get_or_create_student(student_id)
    engine = student["engine"]
    current_state = student["state"]

    # 转换 bloom 层
    bloom_map = {
        "L1": BloomLevel.REMEMBER,
        "L2": BloomLevel.UNDERSTAND,
        "L3": BloomLevel.APPLY,
        "L4": BloomLevel.ANALYZE,
    }
    bloom = bloom_map.get(bloom_layer, BloomLevel.APPLY)

    obs = Observation(
        skill_id=skill_id,
        problem_id=problem_id,
        correct=correct,
        bloom_level=bloom,
        explanation_text=explanation_text,
    )

    updated_state = engine.update(current_state, obs)
    student["state"] = updated_state

    # 检测 misconception
    misc_triggered = False
    detection = None
    if explanation_text:
        try:
            detection = engine.misc_detector.detect(
                student_explanation=explanation_text,
                problem="",
                library_str=PYTHON_BASICS_MISCONCEPTION_LIBRARY_STR,
            )
            misc_triggered = detection.misc_id != ""
        except Exception:
            pass

    # 构建响应
    theta = updated_state.theta_mean
    dims = ["K", "P", "S", "C", "X"]
    response = {
        "correct": correct,
        "theta": {dims[i]: round(float(theta[i]), 4) for i in range(5)},
        "misc_triggered": misc_triggered,
        "misc_id": detection.misc_id if detection else "",
        "misc_confidence": detection.confidence if detection else 0.0,
        "c_discount_factor": round(
            updated_state.C.discount_factor if hasattr(updated_state.C, "discount_factor") else 1.0, 3
        ),
    }
    return response
