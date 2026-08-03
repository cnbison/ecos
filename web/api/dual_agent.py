"""v0.61.0: dual_agent 接入主循环 + 持久化 (Phase 4 of v0.58.0 完整版).

v0.60.0 dual_agent 接入主循环 (in-memory state, 重启丢).
v0.61.0 改造 (CLAUDE.md [5] 8 字段对齐):
  - dual_agent in-memory state (state / intervention_history / state_trajectory /
    calibration_round / warnings / belief_challenges / strategy_challenges /
    consecutive_ineffective) 持久化到 SQLite (student_dual_agent_state 表)
  - 启动 lazy load: 第一次访问 sid 从 DB 加载
  - 每次 process_observation 末尾 save_state (跟 LCA 同样"每次都落盘"模式)
  - 持久化失败不污染 in-memory (跟 LCAStore 同样 try/except + warning)

v0.61.0 顺手修:
  - actual_outcome 改 score 派生 (跟 belief_engine.py:292 一致)
    之前二元 correct 派生 0.0/1.0 → 现在 score 优先 (0.0-1.0)

按 CLAUDE.md [7] 防御性自检 (Bisen 2026-07-28 23:30 拍板):
  - 触碰运行时 state, 但**用 feature flag 隔离** (默认 False)
  - ECOS_DUAL_AGENT_ENABLED=1 python -m web.api.app → 走 dual_agent 路径
  - 默认 False → 现有 lbc001 / lbc002 答题完全不变

设计:
  - dual_agent 共享 LCAEngine (跟 web/api/lca.py 同一实例)
  - 互校结果写 calibration_log 表 (已经有 schema, 0 行)
  - dual_agent in-memory state 写 student_dual_agent_state 表 (v0.61.0 新增)
  - 失败不污染 belief_engine / LCA state (CLAUDE.md [6])

历史 state 影响 (DUAL_AGENT_ENABLED=True 时):
  - students.*: 不动
  - student_lca_state.*: 不动 (但 LCA 同一实例, arm_pull 涨 1, 是已知 trade-off, 留 v0.62.0+)
  - calibration_log: 新增写入 (设计意图)
  - student_dual_agent_state: 新增写入 (v0.61.0 启动, 0 行起步)
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, Optional

_log = logging.getLogger(__name__)

# v0.60.0: feature flag, 默认 False (跟 v0.57.0 LCA_ENABLED 一样的隔离模式)
#   False = submit_answer 走老路径, dual_agent 不跑
#   True  = submit_answer 后调 dual_agent.process_observation, 写 calibration_log
#   设置方式: ECOS_DUAL_AGENT_ENABLED=1 python -m web.api.app
DUAL_AGENT_ENABLED: bool = os.environ.get("ECOS_DUAL_AGENT_ENABLED", "0") == "1"

# v0.61.0: dual_agent 持久化 DB 路径 (跟 LCA / Database 单例共享 web/ecos.db)
DUAL_AGENT_DB_PATH = os.environ.get("ECOS_DB_PATH", "web/ecos.db")

# 单例 (lazy init)
_orchestrator: Optional[Any] = None
# v0.61.0: DualAgentStore 单例
_dual_store: Optional[Any] = None
# v0.61.0: 已加载到 orch 的学生集合 (避免重复 load_state, 跟 LCA 同样模式)
_loaded_students: set[str] = set()


# ─── Lazy-init helpers ───────────────────────────────────────────────────────


def get_dual_orchestrator():
    """获取 DualAgentOrchestrator 单例 (lazy init).

    防御性自检 [1]: lazy init 失败必须有日志, 不能 silent pass.

    v0.62.0-A 设计: dual_agent 用**独立 LCAEngine 实例**, 跟 web/api/lca.py 隔离.
      - 之前 v0.60.0 共享 LCAEngine: 同一次答题 arm_pull 涨 2 次 (lca_select 1 + dual_agent 1)
      - 现在 dual_agent 内部 LCAEngine 独立 → arm_pull 互不串扰
      - dual_agent 内部 LCA state (per-student bandit) **不持久化**, 重启后冷启动
        (dual_agent 8 字段持久化照常, calibration_round / intervention_history 等)
      - 教学决策 LCAEngine (web/api/lca.py) 完全不动, lbc001 32+ 道训练数据保留
    """
    global _orchestrator
    if _orchestrator is None:
        try:
            from ecos.cta.belief_engine import BeliefEngine
            from ecos.dual_agent import DualAgentConfig, DualAgentOrchestrator
            from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig

            cta_engine = BeliefEngine()
            # v0.62.0-A: 独立 LCAEngine 实例, 跟 web/api/lca.py 隔离
            lca_engine = LCAEngine(config=LCAEngineConfig())
            cfg = DualAgentConfig(
                cta_config=cta_engine.config,
                lca_config=lca_engine.config,
                timeout_sec=10,
            )
            _orchestrator = DualAgentOrchestrator(
                config=cfg,
                cta_engine=cta_engine,
                lca_engine=lca_engine,
            )
            _log.info(
                "DualAgentOrchestrator 初始化完成 (DUAL_AGENT_ENABLED=%s, "
                "timeout_sec=%d, lca_engine=独立实例_v0.62.0)",
                DUAL_AGENT_ENABLED, cfg.timeout_sec,
            )
        except Exception:
            _log.warning(
                "DualAgentOrchestrator 单例初始化失败, dual_agent 不可用 "
                "(feature flag=%s)",
                DUAL_AGENT_ENABLED, exc_info=True,
            )
            raise
    return _orchestrator


def get_dual_agent_store():
    """获取 DualAgentStore 单例 (lazy init, v0.61.0 持久化用).

    防御性自检 [1]: init 失败必须 warning, 不能 silent pass.
    """
    global _dual_store
    if _dual_store is None:
        try:
            from ecos.persistence.dual_agent_store import get_dual_agent_store
            _dual_store = get_dual_agent_store(db_path=DUAL_AGENT_DB_PATH)
        except Exception:
            _log.warning(
                "DualAgentStore 单例初始化失败 (db=%s), dual_agent 持久化不可用",
                DUAL_AGENT_DB_PATH, exc_info=True,
            )
            raise
    return _dual_store


def _load_dual_state_if_needed(student_id: str) -> None:
    """从 DB 加载 dual_agent 状态到 orch (v0.61.0 启动 lazy load, 跟 LCA 同样模式).

    行为 (v0.62.1 升级: bloom_target 跟 belief.py 对齐):
      - 已加载过 (在 _loaded_students 里) 跳过
      - 首次访问 → 从 DB load, 写入 orch 内部 dict + 加 _loaded_students
      - DB 有状态 → load (v0.61.0 行为)
      - DB 无状态 → **v0.62.1 改**: 从 web/api/belief.py 拿最新 state 深拷贝,
        避免 v0.60.4 验证时 bloom_target=REMEMBER 跟 belief.py EVALUATE 错位
      - belief.py 也没该学生 (新学生) → 兜底 create_initial_state (跟 v0.60.0 行为)
      - load 失败 → _log.warning + 冷启动 (create_initial_state)

    CLAUDE.md 防御性自检 [1]: 失败必须有日志, 不能 silent pass.
    """
    orch = get_dual_orchestrator()
    if student_id in _loaded_students:
        return
    if orch.has_state(student_id):
        # orch 内部已有 (同进程内, 之前 process_observation 走过)
        _loaded_students.add(student_id)
        return

    store = get_dual_agent_store()
    if not store.has_state(student_id):
        # DB 无状态 → v0.62.1: 从 belief.py 拿最新 state 深拷贝
        _init_dual_state_from_belief_py(student_id, orch)
        _loaded_students.add(student_id)
        return

    # DB 有状态 → 加载到 orch
    snapshot = store.load_state(student_id)
    if snapshot is None:
        # load 失败 (已 _log.warning), 走冷启动
        _loaded_students.add(student_id)
        return

    # dump 格式 dict (跟 orch.load_state 期望的格式一致, 8 字段一一对应)
    dump_dict = {
        "state_snapshot": snapshot.state_snapshot,
        "intervention_history": snapshot.intervention_history,
        "state_trajectory": snapshot.state_trajectory,
        "calibration_round": snapshot.calibration_round,
        "warnings": snapshot.warnings,
        "belief_challenges": snapshot.belief_challenges,
        "strategy_challenges": snapshot.strategy_challenges,
        "consecutive_ineffective": snapshot.consecutive_ineffective,
    }
    orch.ensure_state_loaded(student_id, snapshot=dump_dict)
    _loaded_students.add(student_id)


def _init_dual_state_from_belief_py(student_id: str, orch) -> None:
    """v0.62.1: 从 web/api/belief.py 拿最新 BeliefState 深拷贝, 喂给 dual_agent orch.

    解决 v0.60.4 验证时 bloom_target=REMEMBER 跟 belief.py 最新 EVALUATE 错位 BUG.

    行为:
      - 调 _get_or_create_student(sid) 拿 belief.py 模块级 dict 里的 state
      - 用 BeliefState.from_dict(state.to_dict()) 深拷贝 (v0.61.0 序列化基础)
      - 覆盖 orch.state[sid], 其他 7 字段 (intervention_history / calibration_round 等) 仍走 _init_fresh_state 默认值
      - belief.py 也没该学生 → 兜底 _init_fresh_state (跟 v0.60.0 行为一致)
      - 任何异常 → _log.warning + 兜底 _init_fresh_state (CLAUDE.md [1] 防御性)

    为什么不直接引用 belief_state:
      - dual_agent 改 state 不应污染 belief.py
      - belief.py 改 state 不应污染 dual_agent
      - 用 from_dict 重新构造 BeliefState 实例, 100% 隔离
    """
    try:
        from ecos.cta.belief_state import BeliefState
        from web.api.belief import _get_or_create_student

        belief_student = _get_or_create_student(student_id)
        belief_state = belief_student["state"]
        # 深拷贝: from_dict 重新构造 BeliefState 实例, 5D / Bloom / TC / Misc / np.ndarray 全隔离
        copied_state = BeliefState.from_dict(belief_state.to_dict())
        copied_state.student_id = student_id  # 强制 sid 一致 (兜底)

        # 其他 7 字段仍走 _init_fresh_state 默认值 (intervention_history / calibration_round 等)
        orch._init_fresh_state(student_id)
        # 覆盖 state 为 belief.py 深拷贝
        orch.state[student_id] = copied_state
        _log.info(
            "v0.62.1: dual_agent state 从 belief.py 深拷贝 (sid=%s, "
            "bloom_dominant=%s, K.theta=%.4f)",
            student_id,
            copied_state.bloom_profile.dominant_layer.name,
            copied_state.K.theta,
        )
    except Exception:
        # CLAUDE.md [1]: 失败必须有日志, 不能 silent pass
        # 兜底: 跟 v0.60.0 同样冷启动 (create_initial_state)
        _log.warning(
            "v0.62.1: _init_dual_state_from_belief_py 失败 (sid=%s), 兜底冷启动",
            student_id, exc_info=True,
        )
        orch._init_fresh_state(student_id)


# ─── Public API ─────────────────────────────────────────────────────────────


def process_observation_for_student(
    student_id: str,
    problem_id: str,
    skill_id: str,
    correct: bool,
    score: float,
    bloom_layer: str = "L2",
) -> Optional[Dict[str, Any]]:
    """主入口: 处理一次答题观测 (在 submit_answer 末尾调).

    Args:
        student_id: 学生 ID
        problem_id: 题 ID
        skill_id: 知识点 ID
        correct: 是否答对 (>= 0.6)
        score: partial credit 0.0-1.0
        bloom_layer: Bloom 层级 ("L1" - "L6")

    Returns:
        dict {round, intervention_type, bloom_target, warnings, calibration_id} 或
        None (feature flag off / 失败兜底)
    """
    if not DUAL_AGENT_ENABLED:
        return None  # 默认 off, 现有路径完全不变

    start = time.time()
    try:
        from ecos.cta.belief_engine import Observation
        from ecos.cta.belief_state import BloomLevel

        # Bloom 层级字符串 → enum (L1-L6)
        try:
            bloom_enum = BloomLevel(int(bloom_layer.replace("L", "")))
        except (ValueError, AttributeError):
            bloom_enum = BloomLevel.APPLY  # fallback

        obs = Observation(
            problem_id=problem_id,
            skill_id=skill_id,
            correct=correct,
            score=score,
            bloom_level=bloom_enum,
            response_time_sec=0.0,  # 暂无此数据
        )

        # v0.61.0: 启动 lazy load (确保 sid state 已加载, 避免冷启动覆盖 DB 状态)
        _load_dual_state_if_needed(student_id)

        orch = get_dual_orchestrator()
        result = orch.process_observation(obs, student_id=student_id)

        duration_ms = int((time.time() - start) * 1000)

        # v0.61.0: 每次 process_observation 末尾 save_state (跟 LCA 同样"每次都落盘")
        #   持久化失败不污染 in-memory (load 失败已经 try/except 兜底)
        try:
            _save_dual_state(student_id, orch)
        except Exception:
            _log.warning(
                "save_dual_state 失败 (student=%s), 不影响本次响应, "
                "下次重启前这部分 in-memory 改动没落盘",
                student_id, exc_info=True,
            )

        # v0.64.0: 回写 prev calibration_log.actual_outcome
        #   之前 (v0.60.4 留下的 BUG): prev_calibrated.actual_outcome 在
        #   orch.process_observation 内部被填上 (基于本次 observation.score),
        #   但**没回写 DB**. 所以 calibration_log 表里所有 prev 行的
        #   actual_outcome 都是 None, H3 验证算不出 ECE.
        #   修复: 写新 calibration_log 前, 先 UPDATE 上一轮 (round-1) 的
        #   actual_outcome 到 DB. 失败 _log.warning + 兜底 (主流程不受影响).
        prev_round = result.calibration_round - 1
        if prev_round >= 1:
            try:
                _write_prev_actual_outcome(
                    student_id=student_id,
                    prev_round=prev_round,
                    orch=orch,
                )
            except Exception:
                _log.warning(
                    "_write_prev_actual_outcome 失败 (student=%s, round=%s), "
                    "prev calibration_log actual_outcome 留 None, H3 验证会回填",
                    student_id, prev_round, exc_info=True,
                )

        # 写 calibration_log
        calibration_id = _write_calibration_log(
            student_id=student_id,
            result=result,
            orch=orch,
            duration_ms=duration_ms,
        )

        return {
            "round": result.calibration_round,
            "intervention_type": result.intervention.intervention_type.value
                if result.intervention else None,
            "bloom_target": result.bloom_target.name
                if result.bloom_target else None,
            "warnings": orch.get_warnings(student_id),
            "degraded_mode": result.degraded_mode,
            "calibration_id": calibration_id,
            "duration_ms": duration_ms,
        }

    except Exception:
        # CLAUDE.md [6]: 失败不污染 state, 但必须有日志
        _log.warning(
            "dual_agent.process_observation_for_student 失败 "
            "(student=%s, problem=%s), 不影响主响应",
            student_id, problem_id, exc_info=True,
        )
        return None


# ─── v0.61.0 持久化 helpers ─────────────────────────────────────────────────


def _save_dual_state(student_id: str, orch) -> None:
    """dump orch 内部 8 字段 → DualAgentStore.save_state.

    防御性自检:
      - [1] 失败 _log.warning(..., exc_info=True) (在 DualAgentStore.save_state 内部)
      - [5] 8 字段一次全 dump, 跟 load_state 字段一一对应
      - [6] 失败不污染 in-memory state (DualAgentStore.save_state 内部 raise)

    注意: DualAgentStore.save_state 自己已经 try/except + _log.warning, 这里
    再包一层 try/except 防止其 raise 影响主流程.
    """
    dumped = orch.dump_state(student_id)
    if dumped is None:
        # sid 没在 orch 内部 (冷启动 race?), 不保存
        _log.debug("dual_agent.dump_state 返回 None (sid=%s), skip save", student_id)
        return
    store = get_dual_agent_store()
    store.save_state(
        student_id=student_id,
        state_snapshot=dumped["state_snapshot"],
        intervention_history=dumped["intervention_history"],
        state_trajectory=dumped["state_trajectory"],
        calibration_round=dumped["calibration_round"],
        warnings=dumped["warnings"],
        belief_challenges=dumped["belief_challenges"],
        strategy_challenges=dumped["strategy_challenges"],
        consecutive_ineffective=dumped["consecutive_ineffective"],
    )


def get_dual_agent_debug_info(student_id: str) -> Dict[str, Any]:
    """教师后台 / 调试接口: 返回学生 dual_agent 状态."""
    if not DUAL_AGENT_ENABLED:
        return {"enabled": False}

    try:
        orch = get_dual_orchestrator()
        if student_id not in orch.state:
            return {
                "enabled": True,
                "has_state": False,
                "calibration_round": 0,
                "warnings": [],
            }
        return {
            "enabled": True,
            "has_state": True,
            "calibration_round": orch.calibration_round.get(student_id, 0),
            "warnings": orch.get_warnings(student_id),
            "belief_challenges_count": len(orch.get_belief_challenges(student_id)),
            "strategy_challenges_count": len(orch.get_strategy_challenges(student_id)),
            "history_count": len(orch.get_history(student_id)),
        }
    except Exception:
        _log.warning(
            "get_dual_agent_debug_info 失败 (student=%s)",
            student_id, exc_info=True,
        )
        return {"enabled": True, "error": "debug info not available"}


# ─── Internal helpers ───────────────────────────────────────────────────────


def _write_prev_actual_outcome(
    student_id: str,
    prev_round: int,
    orch,
) -> int:
    """v0.64.0: 回写 prev calibration_log.actual_outcome 到 DB.

    背景 (v0.60.4 留下的 BUG):
      prev_calibrated.actual_outcome 在 orch.process_observation 内部被填上
      (基于本次 observation.score), 但**没回写 DB**. 所以 calibration_log 表里
      所有 prev 行的 actual_outcome 都是 None, H3 验证算不出 ECE.

    修复: 写新 calibration_log 前, 拿 orch.intervention_history[sid][-2] (prev)
          的 actual_outcome, UPDATE 到 DB prev_round 行.
          注: process_observation 末尾 append calibrated, 所以 history[-1] 是当前
              calibrated, history[-2] 是 prev (被 Step 0 改了 actual_outcome).

    Args:
        student_id: 学生 ID
        prev_round: 上一轮 calibration_round (>= 1)
        orch: DualAgentOrchestrator 实例

    Returns:
        更新的行数 (0 表示 prev_round 不存在 / orch 内部 prev 是 None, 1 表示成功).
        任何异常都 raise (让 caller _log.warning + 兜底).
    """
    history = orch.intervention_history.get(student_id, [])
    # 至少 2 条 (prev + 当前) 才能拿 prev
    if len(history) < 2:
        # orch 内部 history 只有 1 条或 0 条, prev 是 None 或没出现
        return 0

    # history[-1] 是当前 calibrated, history[-2] 是 prev (被 Step 0 改 actual_outcome)
    prev = history[-2]
    if prev.actual_outcome is None:
        return 0

    from ecos.persistence.db import get_db
    db = get_db()
    return db.update_calibration_actual_outcome(
        student_id=student_id,
        calibration_round=prev_round,
        actual_outcome=prev.actual_outcome,
    )


def _write_calibration_log(
    student_id: str,
    result,
    orch,
    duration_ms: int,
) -> int:
    """写 calibration_log 表 (db.py 已有 schema, 0 行).

    Returns:
        calibration_id (新插入的 rowid), 失败时 0.
    """
    try:
        from ecos.persistence.db import get_db

        db = get_db()
        # state_before / state_after 简化为 None (完整 BeliefState 太长)
        # 重要信息存 message_payload (JSON)
        # v0.68.0: message_payload 加 state_overall_confidence (state_after belief_state 整体 confidence)
        #   - 之前 round-by-round confidence 只能在 dual_agent_state.state_trajectory 拿到 (受 thread-safety BUG 限制)
        #   - 现在 calibration_log 直接存, H3 V2 (overall_confidence) 验证可以拿全 30+ 样本
        #   - orch.state[student_id] 是 process_observation 末尾 Step 6 的 new_state (state_after)
        state_overall_confidence = None
        try:
            if (
                hasattr(orch, "state")
                and student_id in orch.state
                and orch.state[student_id] is not None
            ):
                state_overall_confidence = float(
                    orch.state[student_id].overall_confidence
                )
        except Exception:
            # 防御性自检 [1]: 拿 confidence 失败不能影响 calibration_log 落盘
            _log.debug(
                "拿 state_overall_confidence 失败 (student=%s), 留 None",
                student_id, exc_info=True,
            )
            state_overall_confidence = None

        # v0.69.0-c: 从 result.metadata 拿 dual_agent_confidence + source
        #   - dual_agent 内部 process_observation Step 3 末尾计算, 写入 calibrated.metadata
        #   - 跟 v0.68.0 state_overall_confidence 同模式 (失败兜底 None, 不阻断落盘)
        #   - 老数据 (v0.69.0 之前) 没这 2 字段, compute_h3_ece V3 优先逻辑跳过 (V2/V1 兜底)
        dual_agent_confidence = None
        dual_agent_confidence_source = None
        try:
            metadata = getattr(result, "metadata", None) or {}
            if metadata.get("dual_agent_confidence") is not None:
                dual_agent_confidence = float(metadata["dual_agent_confidence"])
                dual_agent_confidence_source = str(
                    metadata.get("dual_agent_confidence_source", "linucb")
                )
        except Exception:
            # 防御性自检 [1]: 拿 confidence 失败不能影响 calibration_log 落盘
            _log.debug(
                "拿 dual_agent_confidence 失败 (student=%s), 留 None",
                student_id, exc_info=True,
            )
            dual_agent_confidence = None
            dual_agent_confidence_source = None

        message_payload = {
            "intervention_id": result.intervention.intervention_id
                if result.intervention else None,
            "intervention_type": result.intervention.intervention_type.value
                if result.intervention else None,
            "bloom_target": result.bloom_target.name if result.bloom_target else None,
            "expected_gain": result.expected_gain,
            "expected_risk": result.expected_risk,
            "rationale_preview": (result.rationale or "")[:100],
            "actual_outcome": result.actual_outcome,
            "degraded_mode": result.degraded_mode,
            "state_overall_confidence": state_overall_confidence,  # v0.68.0 (V2)
            "dual_agent_confidence": dual_agent_confidence,  # v0.69.0 (V3, 优先)
            "dual_agent_confidence_source": dual_agent_confidence_source,  # v0.69.0
        }
        # trigger_reason: 来自 process_observation 后的 belief_challenges
        challenges = orch.get_belief_challenges(student_id)
        last_challenge = challenges[-1] if challenges else None
        trigger_reason = (
            f"belief_challenge:{last_challenge.challenged_dimension}"
            if last_challenge else "normal_cycle"
        )
        trigger_evidence = (
            last_challenge.experimental_evidence if last_challenge else {}
        )

        data = {
            "calibration_round": result.calibration_round,
            "message_type": "cta_lca_calibrated",
            "message_payload": message_payload,
            "state_before": "",  # 简化, 完整 state 太长
            "state_after": "",
            "trigger_reason": trigger_reason,
            "trigger_evidence": trigger_evidence,
            "interaction_mode": "degraded" if result.degraded_mode else "normal",
            "outcome": json.dumps({
                "actual_outcome": result.actual_outcome,
                "degraded": result.degraded_mode,
            }),
            "human_review_requested": 0,
            "fallback_to_single_agent": 1 if result.degraded_mode else 0,
            "duration_ms": duration_ms,
        }
        return db.save_calibration(student_id, data)
    except Exception:
        _log.warning(
            "_write_calibration_log 失败 (student=%s), 互校结果未持久化",
            student_id, exc_info=True,
        )
        return 0


__all__ = [
    "DUAL_AGENT_ENABLED",
    "get_dual_orchestrator",
    "process_observation_for_student",
    "get_dual_agent_debug_info",
]
