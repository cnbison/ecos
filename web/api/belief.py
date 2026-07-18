"""BeliefEngine Web 封装--会话状态管理 + API 集成。

每个学生 ID 对应一个 BeliefEngine 实例 + 当前 BeliefState(内存中)。
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig, Observation
from ecos.cta.belief_state import BloomLevel, BeliefState
from ecos.cta.content import PYTHON_BASICS_MISCONCEPTION_LIBRARY_STR
from ecos.cta.l1_evolution import EvolutionConfig
from ecos.cta.l2_mirt import MIRTConfig, MIRTItemParams
from ecos.llm_client import ECOSLLMClient
from ecos.persistence.db import Database

# 数据库实例(全局单例)
_db: Database | None = None


def _get_db() -> Database:
    global _db
    if _db is None:
        _db = Database("web/ecos.db")
        _db.init_schema()
    return _db


# 全局状态映射(student_id → {engine, state})
_STUDENT_STATES: dict[str, dict] = {}


def _get_or_create_student(student_id: str) -> dict:
    if student_id not in _STUDENT_STATES:
        db = _get_db()
        # 尝试从 DB 恢复
        db_row = db.load_student_state(student_id)
        if db_row is not None:
            # DB 中有记录--创建 engine + state(MVP:部分字段从 DB 恢复)
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

            # 部分恢复:theta_mean / bloom_profile / learning_dna
            import json as _json
            theta_str = db_row.get("current_state_5d")
            if theta_str:
                try:
                    theta_list = _json.loads(theta_str)
                    state.theta_mean = np.array(theta_list, dtype=float)
                except Exception:
                    pass
            bloom_str = db_row.get("current_bloom_profile")
            if bloom_str:
                try:
                    bp = _json.loads(bloom_str)
                    state.bloom_profile.remember = bp.get("remember", 0.0)
                    state.bloom_profile.understand = bp.get("understand", 0.0)
                    state.bloom_profile.apply = bp.get("apply", 0.0)
                    state.bloom_profile.analyze = bp.get("analyze", 0.0)
                    state.bloom_profile.evaluate = bp.get("evaluate", 0.0)
                    state.bloom_profile.create = bp.get("create", 0.0)
                    state.bloom_profile.confidence = bp.get("confidence", 0.0)
                    state.bloom_profile.update_dominant()
                except Exception:
                    pass
            dna_str = db_row.get("current_learning_dna")
            if dna_str:
                try:
                    dna = _json.loads(dna_str)
                    state.learning_dna.input_preference = dna.get("input_preference")
                    state.learning_dna.feedback_preference = dna.get("feedback_preference")
                    state.learning_dna.confidence = dna.get("confidence", 0.0)
                except Exception:
                    pass
            _STUDENT_STATES[student_id] = {"engine": engine, "state": state}

            # W5 (2026-07-18): 恢复整体置信度(从 DB confidence 字段)
            db_conf = db_row.get("confidence")
            if db_conf is not None:
                try:
                    state.overall_confidence = float(db_conf)
                except (TypeError, ValueError):
                    pass

            # W5 (2026-07-18): 恢复状态机字段(从 DB 读)
            warmup_count = int(db_row.get("warmup_count") or 0)
            probe_due_in = int(db_row.get("probe_due_in") or engine.config.probe_interval)
            probe_count = int(db_row.get("probe_count") or 0)
            response_history_json = db_row.get("response_history")
            engine._warmup_count[student_id] = warmup_count
            engine._probe_due_in[student_id] = probe_due_in
            engine._probe_count[student_id] = probe_count
            if response_history_json:
                try:
                    history_serializable = json.loads(response_history_json)
                    # 反序列化为 [(problem_id, int(correct), BloomLevel), ...]
                    from ecos.cta.belief_state import BloomLevel as _BloomLevel
                    history = []
                    for item in history_serializable:
                        pid, correct, bl_name = item[0], item[1], item[2]
                        try:
                            bl = _BloomLevel[bl_name]
                        except KeyError:
                            bl = _BloomLevel.APPLY
                        history.append((pid, correct, bl))
                    engine._response_history[student_id] = history
                except Exception:
                    pass
        else:
            # DB 中无记录--创建全新状态并写入 DB
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
            db.upsert_student(student_id, subject="python")
    return _STUDENT_STATES[student_id]


def get_student_state(student_id: str) -> dict[str, Any]:
    """获取学生当前完整信念状态(7 组件)。W1 升级:增加 warm-up + bloom Δ 字段。"""
    student = _get_or_create_student(student_id)
    state = student["state"]
    engine = student["engine"]
    theta = state.theta_mean
    dims = ["K", "P", "S", "C", "X"]
    bloom = state.bloom_profile

    # 每维的 confidence 和 se(来自 DimensionState)
    dim_conf = {}
    dim_se = {}
    for i, d in enumerate(dims):
        dim_state = getattr(state, d)
        dim_conf[d] = round(float(dim_state.confidence), 4)
        dim_se[d] = round(float(dim_state.se), 4)

    # TC states(挂在 C 维度上)
    tc_list = []
    for tc_id, tc_state in state.C.tc_states.items():
        tc_list.append({
            "id": tc_id,
            "status": tc_state.status,
            "progress": round(float(tc_state.progress), 3),
            "confidence": round(float(tc_state.confidence), 3),
            "irreversible": tc_state.irreversible,
        })

    # LearningDNA
    ldn = state.learning_dna
    learning_dna = {
        "input_preference": ldn.input_preference or "示例驱动",
        "feedback_preference": ldn.feedback_preference or "即时反馈",
        "confidence": round(float(ldn.confidence), 4),
    }

    # Trajectory 最近 10 条
    trajectory_snapshots = []
    try:
        snapshots = state.trajectory.last_n(10)
        for snap in snapshots:
            trajectory_snapshots.append({
                "timestamp": snap.timestamp.isoformat() if hasattr(snap.timestamp, 'isoformat') else str(snap.timestamp),
                "theta_5d": [round(float(v), 4) for v in snap.theta_5d],
                "confidence": round(float(snap.confidence), 4),
                "bloom_dominant": snap.bloom_profile.dominant_layer.name if snap.bloom_profile.dominant_layer else None,
            })
    except Exception:
        trajectory_snapshots = []

    # W1: warm-up 状态机字段
    warmup = engine.warmup_progress(student_id)

    # W1: Bloom 距下一层距离
    bloom_distance = bloom.distance_to_next_layer() if hasattr(bloom, "distance_to_next_layer") else None

    # W3: 探针题状态机字段
    probe = engine.probe_progress(student_id)

    return {
        "student_id": student_id,
        # 组件1: 5D mean
        "theta": {dims[i]: round(float(theta[i]), 4) for i in range(5)},
        # 组件1补充: 每维方差(对角线)和置信度
        "theta_cov_diag": {dims[i]: round(float(state.theta_cov[i, i]), 4) for i in range(5)},
        "theta_confidence": dim_conf,
        "theta_se": dim_se,
        # 组件2: 6级 Bloom
        "bloom_profile": {
            "dominant": bloom.dominant_layer.name if bloom.dominant_layer else None,
            "confidence": round(float(bloom.confidence), 4),
            "bloom_levels": {
                "L1": round(float(bloom.remember), 3),
                "L2": round(float(bloom.understand), 3),
                "L3": round(float(bloom.apply), 3),
                "L4": round(float(bloom.analyze), 3),
                "L5": round(float(bloom.evaluate), 3),
                "L6": round(float(bloom.create), 3),
            },
        },
        # W1 新增: Bloom 距下一层距离
        "bloom_layer_distance": bloom_distance,
        # 组件3: TC states
        "tc_states": tc_list,
        # 组件4: LearningDNA
        "learning_dna": learning_dna,
        # 组件5: Trajectory
        "trajectory": trajectory_snapshots,
        # 组件6: Misconceptions(来自快照历史)
        "misc_history": [],  # 在 trajectory snapshots 中
        # 组件7: overall_confidence
        "overall_confidence": round(state.overall_confidence, 4),
        "c_discount_factor": round(
            state.C.discount_factor if hasattr(state.C, "discount_factor") else 1.0, 3
        ),
        # W1 新增: warm-up 状态机
        **warmup,
        # W3 新增: 探针题状态机
        **probe,
    }


def submit_answer(
    student_id: str,
    problem_id: str,
    skill_id: str,
    correct: bool,
    bloom_layer: str,
    explanation_text: str = "",
) -> dict[str, Any]:
    """提交答案 → BeliefEngine.update() → 返回干预建议(如果需要)。"""
    student = _get_or_create_student(student_id)
    engine = student["engine"]
    current_state = student["state"]

    # 注册该题目的 loading vector(从 Q-matrix)
    from web.api.qmatrix import get_question_detail
    prob = get_question_detail(problem_id)
    if prob and "a_specialized" in prob:
        item_params = MIRTItemParams(
            problem_id=problem_id,
            a_specialized=np.array(prob["a_specialized"]),
            a_general=prob.get("mirt_params", {}).get("discrimination", 1.0) * 0.5,
            difficulty=prob.get("mirt_params", {}).get("difficulty", 0.0),
        )
        engine.l2.register_item(item_params)

    # 转换 bloom 层
    bloom_map = {
        "L1": BloomLevel.REMEMBER,
        "L2": BloomLevel.UNDERSTAND,
        "L3": BloomLevel.APPLY,
        "L4": BloomLevel.ANALYZE,
        "L5": BloomLevel.EVALUATE,
        "L6": BloomLevel.CREATE,
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

    # 持久化:每次答题后保存到 SQLite（W5 传 engine 持久化状态机）
    try:
        _get_db().save_student_state(student_id, updated_state, engine=engine)
    except Exception:
        pass  # 持久化失败不影响主流程

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
