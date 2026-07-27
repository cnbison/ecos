"""LCA (Learning Coach Agent) 主循环接入层 — v0.57.0 (LCA 持久化).

v0.56.0 接入 LCA 框架 (passthrough 模式).
v0.57.0 改造:
  - LCAEngine 改成 per-student bandit (修复 v0.56.0 多学生数据冲突 BUG)
  - LCA 状态 (7 字段) 持久化到 SQLite, 跨进程恢复
  - 启动时 lazy load (首次访问 student_id 时从 DB 加载)
  - 每次 select/update 后立即落盘 (避免数据丢失)

CLAUDE.md 防御性自检 [5] 7 字段:
  1. intervention_history   (List[Intervention.to_dict()])
  2. bandit_a               (List[List[List[float]]])
  3. bandit_b               (List[List[float]])
  4. arm_pull_counts        (List[int])
  5. last_intervention      (Intervention.to_dict() | None)
  6. update_count           (int)
  7. select_count           (int)

v0.57.0 不改的事 (等 v0.57.0+ 或 v0.58.0):
  - 每 N 步自动落盘 (现在每次都落盘, 单学生单条 LLM 调用 9-17s 跟 DB 写入 < 100ms 比, 落盘开销可接受)
  - multi-process 同步 (单 Flask 进程足够 Phase 4-5; 后续如果多 worker 启动, 再加 lock)
  - LCA 状态清理 cascade (学生删除时 LCA state 孤儿, v0.59.0+ 加)

防御性自检 (CLAUDE.md 规范):
  - [1] silent pass 全部 _log.warning(..., exc_info=True)
  - [5] 7 字段对齐 (LCAStore + LCAEngine.dump_state/load_state 一次性列全)
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from ecos.cta.belief_state import BeliefState
from ecos.lca.intervention import Intervention
from ecos.lca.orchestrator import (
    CTAInput,
    LCAEngine,
    LCAEngineConfig,
    LCAResult,
)
from ecos.persistence.lca_store import LCAStore, get_lca_store

_log = logging.getLogger(__name__)

# v0.56.0: feature flag, 默认 False (passthrough 观察模式)
#   False = LCA 调一次 select + update, 不发 LLM rationale, 不影响选题
#   True = LCA 完整启用 (rationale 用 LLM 生成, 决策影响干预推荐)
#   设置方式: ECOS_LCA_ENABLED=1 python -m web.api.app
LCA_ENABLED = os.environ.get("ECOS_LCA_ENABLED", "0") == "1"

# v0.57.0: DB 路径配置 (跟 belief.py 共享 web/ecos.db)
LCA_DB_PATH = os.environ.get("ECOS_DB_PATH", "web/ecos.db")


# v0.57.0: 移除模块级 in-memory dict (intervention_history / update_count / select_count)
#   改用 LCAEngine 内部 per-student 状态 + LCAStore 持久化
#   _engine 仍单例 (lazy init)
_engine: Optional[LCAEngine] = None
# v0.57.0: LCAStore 句柄
_store: Optional[LCAStore] = None
# v0.57.0: 已加载到 engine 的学生集合 (避免重复 load_state)
_loaded_students: set[str] = set()


# ─── Lazy-init helpers ───────────────────────────────────────────────────────


def get_lca_engine() -> LCAEngine:
    """获取 LCAEngine 单例 (lazy init).

    防御性自检 [1]: lazy init 失败必须有日志, 不能 silent pass.
    """
    global _engine
    if _engine is None:
        try:
            from web.api.app import get_llm  # 避免循环 import

            # LCA_ENABLED=False 时不传 llm_client, RationaleGenerator 走模板 fallback
            llm_client = get_llm() if LCA_ENABLED else None
            _engine = LCAEngine(
                config=LCAEngineConfig(),
                llm_client=llm_client,
            )
        except Exception:
            _log.warning(
                "LCAEngine 单例初始化失败, LCA 不可用 (feature flag=%s)",
                LCA_ENABLED, exc_info=True,
            )
            raise
    return _engine


def get_store() -> LCAStore:
    """获取 LCAStore 单例 (lazy init).

    防御性自检 [1]: store init 失败必须有日志, 不能 silent pass.
    """
    global _store
    if _store is None:
        try:
            _store = get_lca_store(db_path=LCA_DB_PATH)
        except Exception:
            _log.warning(
                "LCAStore 单例初始化失败 (db=%s), LCA 持久化不可用",
                LCA_DB_PATH, exc_info=True,
            )
            raise
    return _store


def _get_or_create_lca_state(student_id: str) -> None:
    """从 DB 加载 LCA 状态到 engine (CLAUDE.md [5] 命名).

    行为:
      - 第一次访问 student_id 时从 DB 加载到 engine
      - 已加载过 (在 _loaded_students 里) 跳过
      - DB 无该学生状态 (新学生) → 不做任何事, LinUCB 冷启动

    防御性自检 [1]: load 失败必须 warning, 不能 silent pass.
    """
    if student_id in _loaded_students:
        return

    try:
        engine = get_lca_engine()
        store = get_store()

        if store.has_state(student_id):
            snapshot = store.load_state(student_id)
            if snapshot is not None:
                engine.load_state(student_id, snapshot.to_dict())
                _log.info(
                    "LCA state loaded from DB: student=%s, "
                    "history=%d, arm_pulls=%s, update_count=%d",
                    student_id,
                    len(snapshot.intervention_history),
                    snapshot.arm_pull_counts,
                    snapshot.update_count,
                )
        # 无论是否有 DB 状态, 都标记为已加载 (新学生 LinUCB 冷启动也算加载完)
        _loaded_students.add(student_id)
    except Exception:
        _log.warning(
            "LCA state 加载失败 (student=%s), 走冷启动",
            student_id, exc_info=True,
        )
        # 失败也要标已加载, 避免每次 select 都重试 load
        _loaded_students.add(student_id)


def _save_lca_state(student_id: str) -> None:
    """保存 LCA 状态到 DB (CLAUDE.md [5] 7 字段).

    防御性自检 [1]: save 失败必须 warning, 不能 silent pass.
    防御性自检 [5]: 一次性 save 7 字段, 避免分批漏.
    """
    try:
        engine = get_lca_engine()
        store = get_store()

        snapshot = engine.dump_state(student_id)
        # dump_state() 返回 dict, 7 关键字段:
        store.save_state(
            student_id=student_id,
            intervention_history=snapshot["intervention_history"],
            bandit_a=snapshot["bandit_a"],
            bandit_b=snapshot["bandit_b"],
            arm_pull_counts=snapshot["arm_pull_counts"],
            last_intervention=snapshot["last_intervention"],
            update_count=snapshot["update_count"],
            select_count=snapshot["select_count"],
        )
    except Exception:
        _log.warning(
            "LCA state 落盘失败 (student=%s), 本次 select/update 状态进程重启会丢",
            student_id, exc_info=True,
        )


# ─── Public API (跟 belief.py / app.py 调用契约) ───────────────────────────


def select_intervention(
    student_id: str,
    belief_state: BeliefState,
) -> Optional[LCAResult]:
    """LCAEngine.select_intervention 包装 (v0.56.0 passthrough, v0.57.0 持久化).

    即使 LCA_ENABLED=False 也调一次, 用于:
      - 验证 LCA 在调用栈里 (test_lca_wired.py)
      - 收集数据: LinUCB update 能跑通
      - 行为不变: 返回的 result 不传给前端, 不影响 qmatrix 选题

    v0.57.0 新增:
      - 调用前 _get_or_create_lca_state (从 DB 加载历史状态)
      - 调用后 _save_lca_state (持久化新状态)
      - 失败时不污染 LCA state (LinUCB 状态保持)

    Returns:
        LCAResult 成功; 失败时 None (走 CTA 兜底).
    """
    # v0.57.0: 启动加载 (lazy, 只第一次)
    _get_or_create_lca_state(student_id)

    try:
        engine = get_lca_engine()
        cta_input = CTAInput(
            student_id=student_id,
            belief_state=belief_state,
        )
        result = engine.select_intervention(cta_input)
        # v0.57.0: 立即落盘 (select 改了 bandit._arm_fingerprints + _last_arm, 不落盘会丢)
        _save_lca_state(student_id)
        return result
    except Exception:
        _log.warning(
            "LCA select_intervention 失败 (student=%s), 走 CTA 兜底",
            student_id, exc_info=True,
        )
        return None


def update_with_reward(
    student_id: str,
    belief_state: BeliefState,
    score: float,
    bloom_layer: str,
) -> None:
    """v0.56.0: reward 计算 + LCAEngine.update, v0.57.0: + 持久化.

    Reward 公式 (v0.56.0 计划):
        bloom_progress = 1.0 if score >= 0.6 else 0.0
        raw_reward = score + 0.5 * bloom_progress   # [0, 1.5]
        reward = raw_reward / 1.5                    # 归一化到 [0, 1]

    v0.57.0:
      - 启动加载 (lazy)
      - update 后立即落盘 (LinUCB A/b 矩阵已更新)
      - update 失败时不污染 state (不写 LCA 状态)

    防御性自检 [1]: update 失败必须 warning, 不能 silent pass.
    """
    # v0.57.0: 启动加载 (lazy)
    _get_or_create_lca_state(student_id)

    engine = get_lca_engine()

    # v0.57.0: 从 LCAEngine dump_state 拿 last_intervention (替代旧 in-memory dict)
    snapshot = engine.dump_state(student_id)
    if not snapshot.get("last_intervention"):
        # 没选过 intervention (e.g. select 失败过, 或新学生)
        # v0.56.0: 跳过 update, 不报错 (LinUCB 冷启动容错)
        return

    # 防御性: score 必须是 [0, 1]
    score = max(0.0, min(1.0, float(score)))

    # reward 计算
    bloom_progress = 1.0 if score >= 0.6 else 0.0
    raw_reward = score + 0.5 * bloom_progress       # [0, 1.5]
    reward = max(0.0, min(1.0, raw_reward / 1.5))   # 归一化到 [0, 1]

    # 从 last_intervention dict 反序列化为 Intervention
    from ecos.lca.intervention import Intervention as _IV
    last = _IV.from_dict(snapshot["last_intervention"])

    try:
        engine.update(
            student_id=student_id,
            intervention=last,
            new_state=belief_state,
            state_delta=reward,
        )
        # v0.57.0: 立即落盘 (update 改了 LinUCB A/b 矩阵, 不落盘会丢)
        _save_lca_state(student_id)
    except Exception:
        _log.warning(
            "LCAEngine.update 失败 (student=%s, reward=%.3f), 这次 reward 丢失",
            student_id, reward, exc_info=True,
        )


def get_lca_debug_info(student_id: str) -> Dict[str, Any]:
    """v0.57.0: 给教师后台 /api/lca_debug 用的调试信息.

    v0.57.0 改造: 不再维护模块级 in-memory dict, 全部从 LCAEngine dump_state 拿.
    """
    # v0.57.0: lazy load (如果是新学生, dump_state 返回空状态)
    _get_or_create_lca_state(student_id)

    bandit_stats: Dict[str, Any] = {}
    snapshot: Dict[str, Any] = {}
    try:
        engine = get_lca_engine()
        snapshot = engine.dump_state(student_id)
        if hasattr(engine, "_get_bandit"):
            # per-student bandit (v0.57.0 改造后)
            learner = engine._get_bandit(student_id)
            if hasattr(learner.bandit, "get_arm_stats"):
                bandit_stats = learner.bandit.get_arm_stats()
    except Exception:
        _log.warning(
            "get_lca_debug_info: snapshot 获取失败 (student=%s), 调试接口降级",
            student_id, exc_info=True,
        )
        snapshot = {}
        bandit_stats = {"error": "snapshot not available"}

    has_last = bool(snapshot.get("last_intervention"))
    return {
        "enabled": LCA_ENABLED,
        "has_last_intervention": has_last,
        "last_intervention_type": snapshot.get("last_intervention", {}).get("intervention_type") if has_last else None,
        "last_intervention_id": snapshot.get("last_intervention", {}).get("intervention_id") if has_last else None,
        "last_bloom_target": snapshot.get("last_intervention", {}).get("bloom_target") if has_last else None,
        "select_count": snapshot.get("select_count", 0),
        "update_count": snapshot.get("update_count", 0),
        "bandit_stats": bandit_stats,
    }


__all__ = [
    "LCA_ENABLED",
    "get_lca_engine",
    "get_store",
    "select_intervention",
    "update_with_reward",
    "get_lca_debug_info",
]
