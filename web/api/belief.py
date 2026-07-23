"""BeliefEngine Web 封装--会话状态管理 + API 集成。

每个学生 ID 对应一个 BeliefEngine 实例 + 当前 BeliefState(内存中)。

v0.47.5: silent failure 治理
  - 所有 except: pass 改为 logger.warning(..., exc_info=True)
  - DB 恢复 / 持久化 失败不再静默
  - Bisen 反馈 7-19 17:14 答的题 response_history/trajectory_summary 都没存,
    怀疑就是 submit_answer 内某处 except: pass 吞了异常
"""

from __future__ import annotations

import json
import logging
from datetime import datetime as _dt
from typing import Any

import numpy as np

from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig, Observation
from ecos.cta.belief_state import BloomLevel, BeliefState

_log = logging.getLogger(__name__)
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
            # v0.49.3: 传 llm_client 给 BeliefEngine, 避免 misc_detector / perception_critic
            #   在 self.llm is None 时崩 (NoneType has no attribute chat_json)
            # v0.52.0: 传 misconception_library_str (BUG 2.1 修复)
            from web.api.app import get_llm
            engine = BeliefEngine(
                config=config,
                llm_client=get_llm(),
                misconception_library_str=PYTHON_BASICS_MISCONCEPTION_LIBRARY_STR,
            )
            state = engine.create_initial_state(student_id)

            # 部分恢复:theta_mean / bloom_profile / learning_dna
            import json as _json
            theta_str = db_row.get("current_state_5d")
            if theta_str:
                try:
                    theta_list = _json.loads(theta_str)
                    state.theta_mean = np.array(theta_list, dtype=float)
                except Exception:
                    _log.warning(
                        "_get_or_create_student DB 恢复失败(student=%s)",
                        student_id, exc_info=True,
                    )
            # v0.47.9: 恢复 theta_cov (5x5 后验协方差矩阵)
            #   之前不存 → 重启后 theta_se 全是 1.0
            #   存上后,dim.se = sqrt(cov[i,i]) 才是真实估算值
            # 老数据(0.47.9 之前)没这个字段 → 走 default np.eye(5)
            theta_cov_str = db_row.get("theta_cov")
            if theta_cov_str:
                try:
                    cov_list = _json.loads(theta_cov_str)
                    if isinstance(cov_list, list) and len(cov_list) == 5 and all(len(row) == 5 for row in cov_list):
                        state.theta_cov = np.array(cov_list, dtype=float)
                except Exception:
                    _log.warning(
                        "_get_or_create_student 恢复 theta_cov 失败(student=%s), 走 np.eye(5) 默认",
                        student_id, exc_info=True,
                    )
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
                    _log.warning(
                        "_get_or_create_student DB 恢复失败(student=%s)",
                        student_id, exc_info=True,
                    )
            dna_str = db_row.get("current_learning_dna")
            if dna_str:
                try:
                    dna = _json.loads(dna_str)
                    state.learning_dna.input_preference = dna.get("input_preference")
                    state.learning_dna.feedback_preference = dna.get("feedback_preference")
                    state.learning_dna.confidence = dna.get("confidence", 0.0)
                except Exception:
                    _log.warning(
                        "_get_or_create_student DB 恢复失败(student=%s)",
                        student_id, exc_info=True,
                    )

            # W5+ (2026-07-18): 恢复 TC states（Bisen 反馈"TC 状态重启后没了"）
            tc_states_str = db_row.get("tc_states")
            if tc_states_str:
                try:
                    from ecos.cta.belief_state import TCState as _TCState
                    tc_dict = _json.loads(tc_states_str)
                    for tc_id, tc_data in tc_dict.items():
                        try:
                            ts_str = tc_data.get("timestamp")
                            ts = _dt.fromisoformat(ts_str) if ts_str else _dt.now()
                        except Exception:
                            ts = _dt.now()
                        tc_state = _TCState(
                            tc_id=tc_data.get("tc_id", tc_id),
                            status=tc_data.get("status", "pre_liminal"),
                            progress=tc_data.get("progress", 0.0),
                            confidence=tc_data.get("confidence", 0.0),
                            liminal_signals=tc_data.get("liminal_signals", []),
                            post_liminal_jump_detected=tc_data.get("post_liminal_jump_detected", False),
                            irreversible=tc_data.get("irreversible", False),
                            timestamp=ts,
                        )
                        state.C.tc_states[tc_id] = tc_state
                except Exception:
                    _log.warning(
                        "_get_or_create_student DB 恢复失败(student=%s)",
                        student_id, exc_info=True,
                    )

            # W5+ (2026-07-18): 恢复 trajectory 最近 N 个 snapshot（Bisen 反馈"成长轨迹重启后没了"）
            trajectory_str = db_row.get("trajectory_summary")
            if trajectory_str:
                try:
                    from ecos.cta.belief_state import StateSnapshot as _Snapshot
                    snap_list = _json.loads(trajectory_str)
                    for snap_data in snap_list:
                        try:
                            ts_str = snap_data.get("timestamp")
                            ts = _dt.fromisoformat(ts_str) if ts_str else _dt.now()
                        except Exception:
                            ts = _dt.now()
                        snap = _Snapshot(
                            timestamp=ts,
                            theta_5d=np.array(snap_data.get("theta_5d", [0, 0, 0, 0, 0]), dtype=float),
                            bloom_profile=state.bloom_profile,  # 共享当前 bloom profile
                            confidence=snap_data.get("confidence", 0.0),
                        )
                        if "misc_history" in snap_data:
                            snap.misc_history = list(snap_data["misc_history"])
                        state.trajectory.snapshots.append(snap)
                except Exception:
                    _log.warning(
                        "_get_or_create_student DB 恢复失败(student=%s)",
                        student_id, exc_info=True,
                    )

            _STUDENT_STATES[student_id] = {"engine": engine, "state": state}

            # W5 (2026-07-18): 恢复整体置信度(从 DB confidence 字段)
            db_conf = db_row.get("confidence")
            if db_conf is not None:
                try:
                    state.overall_confidence = float(db_conf)
                except (TypeError, ValueError):
                    _log.warning(
                        "_get_or_create_student DB 恢复失败(student=%s)",
                        student_id, exc_info=True,
                    )

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
                    # v0.49.2: response_history 改 dict 格式, 兼容老 3-list 格式
                    #   老: [pid, correct, bloom_name]
                    #   新: {"problem_id": ..., "correct": ..., "bloom_level": ..., "user_answer": ..., "correct_answer": ..., "timestamp": ...}
                    from ecos.cta.belief_state import BloomLevel as _BloomLevel
                    history = []
                    for item in history_serializable:
                        if isinstance(item, dict):
                            # 新格式: 直接存, 把 bloom_level str 转 BloomLevel enum 供 belief_engine 内部用
                            try:
                                item["_bloom_level_enum"] = _BloomLevel[item["bloom_level"]]
                            except KeyError:
                                item["_bloom_level_enum"] = _BloomLevel.APPLY
                            history.append(item)
                        else:
                            # 老 3-list 格式: 迁移到 dict
                            pid, correct, bl_name = item[0], item[1], item[2]
                            try:
                                bl = _BloomLevel[bl_name]
                            except KeyError:
                                bl = _BloomLevel.APPLY
                            history.append({
                                "problem_id": pid,
                                "correct": int(correct),
                                "bloom_level": str(bl.name),
                                "_bloom_level_enum": bl,  # 内部用, 不存 DB
                                "user_answer": None,
                                "correct_answer": None,
                                "timestamp": None,
                            })
                    engine._response_history[student_id] = history
                except Exception:
                    _log.warning(
                        "_get_or_create_student DB 恢复失败(student=%s)",
                        student_id, exc_info=True,
                    )

                # v0.47.4: 重新注册 history 中所有题目的 MIRT 参数（避免 default fallback 放大信号）
                # Bisen 反馈: 重启后错一题 K 暴跌 0.86 → -0.05（掉了 0.91）
                # 根因: default_a_specialized = [0.8]*5, 所有维度都被等权放大,signal 暴增
                # 修复: 从 Q 矩阵按 problem_id 加载真实 a_specialized,再 register 到 engine.l2
                try:
                    from web.api.qmatrix import get_question_detail
                    seen_pids: set[str] = set()
                    # v0.49.2: response_history 改 dict 格式, 同时兼容老 3-tuple
                    for h in engine._response_history.get(student_id, []):
                        pid = h["problem_id"] if isinstance(h, dict) else h[0]
                        if pid in seen_pids:
                            continue
                        seen_pids.add(pid)
                        prob = get_question_detail(pid)
                        if not prob or "a_specialized" not in prob:
                            continue
                        item_params = MIRTItemParams(
                            problem_id=pid,
                            a_specialized=np.array(prob["a_specialized"]),
                            a_general=prob.get("mirt_params", {}).get("discrimination", 1.0) * 0.5,
                            difficulty=prob.get("mirt_params", {}).get("difficulty", 0.0),
                        )
                        engine.l2.register_item(item_params)
                except Exception:
                    _log.warning(
                        "_get_or_create_student DB 恢复失败(student=%s)",
                        student_id, exc_info=True,
                    )

            # v0.47.8: 同步重算每维度的 theta/confidence/se/mastery_prob
            # Bisen 反馈: 重启后 5D 区域显示 theta 正确(0.89/0.34/0.36/0.25/0.25)
            #   但每维度单独置信度都是 0% (与总置信度 0.400 不一致)
            # 根因: DB 只存 state.theta_mean 和 bloom_profile,不存 dim.{K,P,S,C,X}.{theta,confidence,se}
            #   get_student_state 读 dim_state.confidence,DB 恢复后是 dataclass 默认 0.0
            # 修复: 复用 update() Step 3 同样的公式,按 theta_mean + theta_cov 重建每维度状态
            #   dim.confidence = min(1.0, len(history) / 30.0)  ← 和 overall_confidence 公式一致
            #   dim.theta = state.theta_mean[i]
            #   dim.se = sqrt(max(theta_cov[i, i], 1e-6))
            #   dim.mastery_prob = sigmoid(theta)
            #   dim.mastered = mastery_prob >= 0.5
            try:
                import numpy as _np
                for i, dim_char in enumerate(["K", "P", "S", "C", "X"]):
                    dim_state = getattr(state, dim_char)
                    dim_state.theta = float(state.theta_mean[i])
                    # v0.47.9: 用恢复的 theta_cov 算真实 SE(不再走 np.eye(5) 默认 1.0)
                    # 老数据(0.47.9 之前)没存 theta_cov → state.theta_cov 是 default I
                    #   se = sqrt(1.0) = 1.0 (与之前行为一致,平滑过渡)
                    if state.theta_cov is not None and state.theta_cov.shape == (5, 5):
                        cov_i = float(state.theta_cov[i, i])
                    else:
                        cov_i = 1.0
                    dim_state.se = float(_np.sqrt(max(cov_i, 1e-6)))
                    dim_state.mastery_prob = float(1.0 / (1.0 + _np.exp(-dim_state.theta)))
                    dim_state.mastered = dim_state.mastery_prob >= 0.5
                    # v0.48.0: dim.confidence 反映该维度**自己**的 SE
                    #   公式: 1 / (1 + SE) — 5 维度会按各自估算质量分化
                    #   注意: 不能再用 len(history) / 30.0（5 维度共用会导致 5 维度 conf 全一样）
                    dim_state.confidence = float(1.0 / (1.0 + dim_state.se))
            except Exception:
                _log.warning(
                    "_get_or_create_student 重算 dim.{theta,confidence,se} 失败(student=%s)",
                    student_id, exc_info=True,
                )

            # W5+: overall_confidence 重算（覆盖 DB 存的老值,避免老 0.4 与 5 维度 0.5+ 矛盾）
            # v0.48.1: 改成 5 维度 confidence 均值(与 dim.confidence 同公式,数据一致)
            #   Bisen 反馈: 5 维度 0.5+ 但 overall 0.4 不一致
            #   旧公式 len(history)/30 → 0.4,新公式 mean(dim.confidence) → 0.5+
            # 关键: 必须放在"重算每维度"**之后**,否则 mean 时 dim.confidence 还是 0
            try:
                import numpy as _np
                state.overall_confidence = float(_np.mean([
                    state.K.confidence, state.P.confidence, state.S.confidence,
                    state.C.confidence, state.X.confidence,
                ]))
            except Exception:
                _log.warning(
                    "_get_or_create_student 重算 overall_confidence 失败(student=%s), 走 0.0 兜底",
                    student_id, exc_info=True,
                )
                state.overall_confidence = 0.0
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
            # v0.49.3: 传 llm_client 给 BeliefEngine, 避免 misc_detector / perception_critic
            #   在 self.llm is None 时崩 (NoneType has no attribute chat_json)
            # v0.52.0: 传 misconception_library_str (BUG 2.1 修复)
            from web.api.app import get_llm
            engine = BeliefEngine(
                config=config,
                llm_client=get_llm(),
                misconception_library_str=PYTHON_BASICS_MISCONCEPTION_LIBRARY_STR,
            )
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

    # Trajectory 全量（v0.47.5: 之前 last_n(10) 截断,Bisen 反馈"应该按实际数量显示"）
    # 配合 in-memory cap (trajectory_maxlen=500) 和 DB persist last_n(500)
    trajectory_snapshots = []
    try:
        snapshots = state.trajectory.last_n(500)
        for snap in snapshots:
            trajectory_snapshots.append({
                "timestamp": snap.timestamp.isoformat() if hasattr(snap.timestamp, 'isoformat') else str(snap.timestamp),
                "theta_5d": [round(float(v), 4) for v in snap.theta_5d],
                "confidence": round(float(snap.confidence), 4),
                "bloom_dominant": snap.bloom_profile.dominant_layer.name if snap.bloom_profile.dominant_layer else None,
            })
    except Exception as e:
        # v0.47.5: 之前 except: pass 静默吞,Bisen 反馈"答了题没存"也看不到
        import logging
        logging.getLogger(__name__).warning(
            "trajectory 序列化失败 (%d snapshots): %s", len(state.trajectory.snapshots), e,
            exc_info=True,
        )
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
    user_answer: str = "",  # v0.49.2: 给答题历史详情页用
    correct_answer: str = "",  # v0.49.2: 正确答案(从 Q 矩阵读)
    # v0.52.2: AI 评判的具体 reasoning (Bisen 反馈 partial credit 缺失,
    #   短期先存 response_history, Phase 5 partial credit 训练用历史数据)
    ai_reasoning: str = "",
    # v0.54.0-e: partial credit 评分 0.0-1.0 (1.0=完全对, 0.0=完全错, 0.7=70%对)
    #   优先级高于 correct: score >= 0.6 派生 correct=True
    #   老调用方不传 score 时, fallback: correct=True → score=1.0, else 0.0
    score: float = 0.0,
) -> dict[str, Any]:
    """提交答案 → BeliefEngine.update() → 返回干预建议(如果需要)。

    v0.54.0-e: partial credit 改造
    - 接收 score: float 参数 (0.0-1.0)
    - 派生 correct = score >= 0.6
    - 老调用方只传 correct=True: 派生 score=1.0, correct=True (兼容)
    - 新调用方传 score=0.7: 派生 correct=True (70% 算对)
    """
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
    # v0.49.2: 如果调用方没传 correct_answer，从 Q 矩阵读
    if not correct_answer and prob and "correct_answer" in prob:
        correct_answer = str(prob["correct_answer"])

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
        # v0.54.0-e: partial credit score 字段
        #   老调用方不传 score 时 (score=0.0), engine.update() 内部派生:
        #     score=0.0 + correct=True → fallback score=1.0 (兼容)
        #     score=0.0 + correct=False → fallback score=0.0
        #   新调用方传 score=0.7 → engine.update() 派生 correct=True (>=0.6)
        score=score,
        bloom_level=bloom,
        explanation_text=explanation_text,
        user_answer=user_answer,
        correct_answer=correct_answer,
        ai_reasoning=ai_reasoning,  # v0.52.2: 存 AI reasoning
    )

    updated_state = engine.update(current_state, obs)
    student["state"] = updated_state

    # 持久化:每次答题后保存到 SQLite（W5 传 engine 持久化状态机）
    # v0.47.5: silent pass → logger.warning
    # v0.48.5: 加 persisted 标志返回给前端
    #   Bisen 反馈 7-19 ~ 7-21 期间答的 4 道题没存
    #   根因: 之前 Flask 进程跑的是老代码 (0.47.5 之前),silent pass 吞 save 失败
    #   0.47.5 commit 之后,silent pass → _log.warning,但 Bisen 没重启 Flask 进程
    #   修复: 返回 persisted 字段给前端,save 失败时 alert,不让用户以为成功
    persisted = False
    try:
        _get_db().save_student_state(student_id, updated_state, engine=engine)
        persisted = True
    except Exception:
        _log.warning(
            "submit_answer: save_student_state 失败(student=%s, problem=%s), 答题数据全丢!",
            student_id, problem_id, exc_info=True,
        )

    # v0.52.0: 从 updated_state 读 misconception (BUG 2.2 修复)
    #   之前 belief.py 末尾独立调 engine.misc_detector.detect(),
    #   只把结果返回前端 response, 没 append 到 state.C.misconception_hits
    #   → save_student_state 持久化的 misc_hits 始终空
    #   → DB misconception_history 永远没数据
    #   修复: 删末尾独立检测, 改从 updated_state.C.misconception_hits 读最新一条
    #         (engine.update 内部 _llm_critic_misconception 已 append, 见 BUG 2.1 修复)
    latest_misc = None
    for h in reversed(getattr(updated_state.C, "misconception_hits", [])):
        if h.trigger_problem_id == problem_id:
            latest_misc = h
            break

    # 构建响应
    theta = updated_state.theta_mean
    dims = ["K", "P", "S", "C", "X"]
    # v0.54.0-e: 派生 correct (跟 observation.score 一致, score >= 0.6)
    derived_correct = score >= 0.6 if score > 0 else correct
    response = {
        "correct": derived_correct,  # v0.54.0: 派生自 score
        "score": score,  # v0.54.0: partial credit 评分
        "theta": {dims[i]: round(float(theta[i]), 4) for i in range(5)},
        "misc_triggered": latest_misc is not None,
        "misc_id": latest_misc.misc_id if latest_misc else "",
        "misc_confidence": round(float(latest_misc.confidence), 4) if latest_misc else 0.0,
        "c_discount_factor": round(
            updated_state.C.discount_factor if hasattr(updated_state.C, "discount_factor") else 1.0, 3
        ),
        # v0.48.5: 持久化标志,前端据此判断是否需要重试/报警
        #   false = save 失败,答题数据全丢(可能 next refresh 看不到更新)
        "persisted": persisted,
    }
    return response
