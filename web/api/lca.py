"""LCA (Learning Coach Agent) 主循环接入层 — v0.56.0 实施.

LCA 框架代码 2026-07-03 已完整 (ecos/lca/):
  - LCAEngine + LinUCB (l4_optimization)
  - 5 类干预 + 4 级 CLT + 6 阶段 CA (intervention.py)
  - L3 自适应 + Bjork + Scaffolding (l3_selection)
  - RationaleGenerator (rationale)

但 v0.56.0 之前没接通主循环——belief.py grep "LCA" 0 匹配,
所有"下一步该做什么"实际是 CTA 状态估计 + 简单选题加权.

v0.56.0 接入 (passthrough 模式, **不改变选题行为**):
  1. /api/question 调用 LCAEngine.select_intervention() 记录干预决策
     (不传给前端, 不影响 qmatrix 选题——CTA 选题作为降级兜底)
  2. /api/answer 调用 LCAEngine.update() + 计算 reward
  3. LCA_ENABLED feature flag 默认 False, 验证完 1 周数据后再开

后续版本 (v0.57.0+):
  - LCA 持久化 (intervention_history + LinUCB A/b 矩阵落盘)
  - LCA 决策作为 qmatrix 选题权重的参考信号之一
  - 双 Agent 互校

防御性自检 (CLAUDE.md §防御性自检规范):
  - [1] silent pass 全部改 _log.warning(..., exc_info=True)
  - [2] __version__ 同步 bump (ecos/__init__.py)
  - [3] detect_with_hits 必须传 library_str (本次不涉及 misconception)
  - [4] HTML class 对齐 (本次不动 HTML)
  - [5] DB 恢复 6 字段 (本次不动 db.py / belief.py 恢复路径)
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

_log = logging.getLogger(__name__)

# v0.56.0: feature flag, 默认 False (passthrough 观察模式)
#   False = LCA 调一次 select + update, 不发 LLM rationale, 不影响选题
#   True = LCA 完整启用 (rationale 用 LLM 生成, 决策影响干预推荐)
#   设置方式: ECOS_LCA_ENABLED=1 python -m web.api.app
LCA_ENABLED = os.environ.get("ECOS_LCA_ENABLED", "0") == "1"

# v0.56.0: LCAEngine 全局单例 (lazy init)
_engine: Optional[LCAEngine] = None

# v0.56.0: 记录每个学生最近一次 intervention (供 /api/answer 回调用)
#   v0.57.0 计划: 持久化到 SQLite, 跨进程恢复
_last_intervention: Dict[str, Intervention] = {}

# v0.56.0: 调试 + 教师后台接口统计
_update_count: Dict[str, int] = {}
_select_count: Dict[str, int] = {}


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


def select_intervention(
    student_id: str,
    belief_state: BeliefState,
) -> Optional[LCAResult]:
    """LCAEngine.select_intervention 包装 (v0.56.0 passthrough).

    即使 LCA_ENABLED=False 也调一次, 用于:
      - 验证 LCA 在调用栈里 (test_lca_wired.py)
      - 收集数据: LinUCB update 能跑通
      - 行为不变: 返回的 result 不传给前端, 不影响 qmatrix 选题

    Returns:
        LCAResult 成功; 失败时 None (走 CTA 兜底).
    """
    try:
        engine = get_lca_engine()
        cta_input = CTAInput(
            student_id=student_id,
            belief_state=belief_state,
        )
        result = engine.select_intervention(cta_input)
        _last_intervention[student_id] = result.intervention
        _select_count[student_id] = _select_count.get(student_id, 0) + 1
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
    """v0.56.0: reward 计算 + LCAEngine.update.

    Reward 公式 (v0.56.0 计划):
        bloom_progress = 1.0 if score >= 0.6 else 0.0
        raw_reward = score + 0.5 * bloom_progress   # [0, 1.5]
        reward = raw_reward / 1.5                    # 归一化到 [0, 1]

    注: K 维度变化用 partial credit score 近似 (v0.54.0-e 已实现);
        bloom_progress 反映是否答对该 Bloom 层.

    简化版: 只用 K + bloom, 不算 5D 全量 state_delta
    (完整版需 5D 联合 + 6 Bloom 联合, v0.57.0+ 升级).

    防御性自检 [1]: update 失败必须 warning, 不能 silent pass.
    """
    if student_id not in _last_intervention:
        # 没选过 intervention (e.g. 进程刚启动, 上一题选过但重启了)
        # v0.56.0: 跳过 update, 不报错 (LinUCB 冷启动容错)
        return

    last = _last_intervention[student_id]

    # 防御性: score 必须是 [0, 1]
    score = max(0.0, min(1.0, float(score)))

    # reward 计算
    bloom_progress = 1.0 if score >= 0.6 else 0.0
    raw_reward = score + 0.5 * bloom_progress       # [0, 1.5]
    reward = max(0.0, min(1.0, raw_reward / 1.5))   # 归一化到 [0, 1]

    try:
        engine = get_lca_engine()
        engine.update(
            student_id=student_id,
            intervention=last,
            new_state=belief_state,
            state_delta=reward,
        )
        _update_count[student_id] = _update_count.get(student_id, 0) + 1
    except Exception:
        _log.warning(
            "LCAEngine.update 失败 (student=%s, reward=%.3f), 这次 reward 丢失",
            student_id, reward, exc_info=True,
        )


def get_lca_debug_info(student_id: str) -> Dict[str, Any]:
    """v0.56.0: 给教师后台 /api/lca_debug 用的调试信息.

    Returns:
        dict 含 enabled / has_last_intervention / last_intervention_type /
              update_count / select_count / bandit_arm_stats
    """
    has_last = student_id in _last_intervention
    last = _last_intervention.get(student_id)
    bandit_stats: Dict[str, Any] = {}
    try:
        # LCAEngine.bandit 是 LCAPolicyLearner; 内部 LinUCB 有 get_arm_stats
        engine = get_lca_engine()
        if hasattr(engine.bandit, "bandit") and hasattr(engine.bandit.bandit, "get_arm_stats"):
            bandit_stats = engine.bandit.bandit.get_arm_stats()
    except Exception:
        # 防御性自检 [1]: 调试接口失败也必须 warning, 不能 silent pass
        _log.warning(
            "get_lca_debug_info: bandit_stats 获取失败 (student=%s), 调试接口降级",
            student_id, exc_info=True,
        )
        bandit_stats = {"error": "bandit not available"}

    return {
        "enabled": LCA_ENABLED,
        "has_last_intervention": has_last,
        "last_intervention_type": last.intervention_type.name if last else None,
        "last_intervention_id": getattr(last, "intervention_id", None) if last else None,
        "last_bloom_target": last.bloom_target.name if last else None,
        "select_count": _select_count.get(student_id, 0),
        "update_count": _update_count.get(student_id, 0),
        "bandit_stats": bandit_stats,
    }


__all__ = [
    "LCA_ENABLED",
    "get_lca_engine",
    "select_intervention",
    "update_with_reward",
    "get_lca_debug_info",
]
