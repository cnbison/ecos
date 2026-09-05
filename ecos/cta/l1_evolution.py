"""L1 时间演化层：BKT（Bayesian Knowledge Tracing）.

对应 research/10-engineering/01-cta-belief-engine.md §4.2.

经典 4 参数 BKT (Corbett & Anderson, 1994):
  P(L₀) - 初始掌握概率（先验）
  P(T)  - 学习转移概率（未掌握→已掌握）
  P(G)  - 猜测概率（未掌握却答对）
  P(S)  - 失误概率（已掌握却答错）

M2 W1 范围：BKTParams / BKTModel / BKTEvolutionLayer。
Phase 5+ 才实现 DKT / DKVMN / FSRS 间隔调度。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class BKTParams:
    """BKT 4 参数.

    默认值来自 Corbett-Anderson 经典论文与 pyBKT 默认值。
    不同知识点（基础 vs 高阶）可在 EvolutionConfig 中覆盖。
    """

    p_init: float = 0.1   # P(L₀) 初始掌握概率
    p_learn: float = 0.1  # P(T) 学习转移概率
    p_guess: float = 0.2  # P(G) 猜测概率
    p_slip: float = 0.1   # P(S) 失误概率

    def __post_init__(self) -> None:
        if not (0.0 <= self.p_init <= 1.0):
            raise ValueError(f"p_init={self.p_init} not in [0,1]")
        if not (0.0 <= self.p_learn <= 1.0):
            raise ValueError(f"p_learn={self.p_learn} not in [0,1]")
        if not (0.0 <= self.p_guess <= 1.0):
            raise ValueError(f"p_guess={self.p_guess} not in [0,1]")
        if not (0.0 <= self.p_slip <= 1.0):
            raise ValueError(f"p_slip={self.p_slip} not in [0,1]")


@dataclass
class EvolutionConfig:
    """L1 层配置——管理不同知识点的 BKT 参数与衰减常数."""

    default_params: BKTParams = field(default_factory=BKTParams)
    skill_params_overrides: Dict[str, BKTParams] = field(default_factory=dict)
    # 间隔效应衰减常数（天）—— Ebbinghaus 曲线 e^(-days/decay_constant)
    default_decay_constant_days: float = 30.0
    skill_decay_overrides: Dict[str, float] = field(default_factory=dict)

    def get_params(self, skill_id: str) -> BKTParams:
        return self.skill_params_overrides.get(skill_id, self.default_params)

    def get_decay_constant(self, skill_id: str) -> float:
        return self.skill_decay_overrides.get(skill_id, self.default_decay_constant_days)


class BKTModel:
    """单个知识点的 BKT 模型.

    状态: 当前掌握概率 P(L_n) ∈ [0,1]
    """

    def __init__(self, skill_id: str, params: BKTParams) -> None:
        self.skill_id = skill_id
        self.params = params
        self.p_mastered: float = params.p_init
        self.n_updates: int = 0
        self.n_correct: int = 0

    def update(self, correct: bool) -> float:
        """更新 BKT 并返回新的 P(L).

        Args:
            correct: 学生作答是否正确

        Returns:
            新的掌握概率 P(L_n)
        """
        p_prev = self.p_mastered
        p_s = self.params.p_slip
        p_g = self.params.p_guess

        if correct:
            numerator = p_prev * (1.0 - p_s)
            denominator = numerator + (1.0 - p_prev) * p_g
        else:
            numerator = p_prev * p_s
            denominator = numerator + (1.0 - p_prev) * (1.0 - p_g)

        if denominator > 0.0:
            p_after_observation = numerator / denominator
        else:
            # 数值边界保护：分母为 0 时退化为先验
            p_after_observation = p_prev

        # 学习转移：未掌握者有概率转移到掌握
        self.p_mastered = p_after_observation + (1.0 - p_after_observation) * self.params.p_learn

        self.n_updates += 1
        if correct:
            self.n_correct += 1

        return self.p_mastered

    def accuracy(self) -> float:
        """历史准确率（仅供诊断）."""
        return self.n_correct / self.n_updates if self.n_updates > 0 else 0.0


class BKTEvolutionLayer:
    """L1 时间演化层——管理所有知识点的 BKT.

    用法:
        layer = BKTEvolutionLayer(EvolutionConfig())
        layer.update("K.func.quadratic", correct=True)
        p_mastered = layer.get_mastery("K.func.quadratic")
    """

    def __init__(self, config: EvolutionConfig | None = None) -> None:
        self.config = config or EvolutionConfig()
        self.skill_models: Dict[str, BKTModel] = {}

    def _ensure_model(self, skill_id: str) -> BKTModel:
        if skill_id not in self.skill_models:
            self.skill_models[skill_id] = BKTModel(skill_id, self.config.get_params(skill_id))
        return self.skill_models[skill_id]

    def update(self, skill_id: str, correct: bool) -> float:
        """更新指定知识点的 BKT，返回新 P(L)."""
        model = self._ensure_model(skill_id)
        return model.update(correct)

    def get_mastery(self, skill_id: str) -> float:
        """获取当前掌握概率（未初始化时返回 p_init）."""
        if skill_id not in self.skill_models:
            return self.config.get_params(skill_id).p_init
        return self.skill_models[skill_id].p_mastered

    def get_model(self, skill_id: str) -> BKTModel:
        return self._ensure_model(skill_id)

    def apply_decay(self, skill_id: str, days_since_last: int) -> float:
        """应用 Ebbinghaus 间隔效应衰减.

        P(L) → P(L) · e^(-days/decay_constant)

        ⚠️ v0.97.1: 本方法在产品路径是 dead code, 且**禁止激活**——in-place 乘法
        是破坏性衰减, 重入即双重衰减 (p · e^(-t/τ) 再乘 e^(-t/τ))。衰减应通过
        模块级 replay_mastery_view() 的无状态视图读时计算 (decayed = peak ·
        e^(-days/τ), 不落盘、不污染 state)。本方法仅保留给显式知晓风险的
        离线实验调用。
        """
        if skill_id not in self.skill_models or days_since_last <= 0:
            return self.get_mastery(skill_id)
        model = self.skill_models[skill_id]
        decay_constant = self.config.get_decay_constant(skill_id)
        model.p_mastered *= float(np.exp(-days_since_last / decay_constant))
        return model.p_mastered

    def reset_skill(self, skill_id: str) -> None:
        """重置单个知识点."""
        if skill_id in self.skill_models:
            del self.skill_models[skill_id]

    def all_skills(self) -> list[str]:
        return list(self.skill_models.keys())


def replay_mastery_view(
    history: List[Dict[str, Any]],
    config: EvolutionConfig | None = None,
    now: Optional[datetime] = None,
) -> Dict[str, Dict[str, Any]]:
    """无状态重放视图：从响应历史推导 per-skill BKT 峰值 + 衰减视图 (v0.97.1).

    对应: docs/wiring-audit-2026-09-05.md A 类 (bjork_spacing / ca_scaffolding
    接线的数据供给); CogMirror P3 方案 (BKT 不持久化, 峰值由重放推导, 衰减是
    读时计算不是状态)。

    语义:
      - **只读**: 内部用一次性 throwaway BKTModel 重放, 不触碰任何 engine.l1
        或 BeliefState —— 同输入同输出, 幂等。
      - **峰值**: 重放全程 max(p_init, 各次 update 后的 p_mastered)。
        峰值下限 = p_init (不会为 0; 注意 p_learn 转移使全错序列 p 缓慢
        上升, 此时峰值 = 末次值)。
      - **衰减视图**: decayed = peak · e^(-days_since/τ), τ 取
        EvolutionConfig.get_decay_constant(skill_id)。**不修改任何持久状态**,
        避免双重衰减陷阱 (见 BKTEvolutionLayer.apply_decay docstring)。
      - **streaks**: 末尾连续对/错计数 (ca_scaffolding fade/restore 输入)。
      - **时间**: last_ts 取该 skill 最后一条带 timestamp 的条目 (append 序
        最后回溯); 无 timestamp → days_since=0, decayed=peak (保守: 无时间
        证据不衰减)。now 可注入 (可测试性), 默认 datetime.now()。

    Args:
        history: FeatureExtractor.get_history(student_id) 的响应历史
            (DB restore 路径经 set_history 恢复, 重启存活)。
            条目需含 skill_id + correct (+ timestamp); v0.97.1 前的
            老条目缺 skill_id → 跳过并 warning 计数 (不猜不映射)。
        config: EvolutionConfig (None = 默认)。
        now: 衰减计算基准时间 (None = 当前时间)。

    Returns:
        {skill_id: {"peak": float, "current": float, "decayed": float,
                    "days_since": float, "last_ts": datetime|None,
                    "streak_success": int, "streak_fail": int,
                    "n_observations": int}}
    """
    config = config or EvolutionConfig()
    now = now or datetime.now()

    # 按 skill 分组 (保持 append 序; 老条目缺 skill_id 跳过)
    skipped = 0
    per_skill: Dict[str, List[Dict[str, Any]]] = {}
    for h in history:
        sid = h.get("skill_id")
        if not sid:
            skipped += 1
            continue
        per_skill.setdefault(sid, []).append(h)
    if skipped:
        logger.warning(
            "replay_mastery_view: %d/%d 条历史缺 skill_id (v0.97.1 前老数据), "
            "跳过不参与重放 (不猜不映射)",
            skipped, len(history),
        )

    views: Dict[str, Dict[str, Any]] = {}
    for sid, entries in per_skill.items():
        params = config.get_params(sid)
        model = BKTModel(sid, params)  # throwaway, 只读重放
        peak = params.p_init
        for e in entries:
            p = model.update(_entry_correct(e))
            peak = max(peak, p)
        current = model.p_mastered

        # 末尾连续对/错 (两者互斥: 有 streak_success 则 streak_fail=0)
        streak_success = 0
        for e in reversed(entries):
            if _entry_correct(e):
                streak_success += 1
            else:
                break
        streak_fail = 0
        for e in reversed(entries):
            if not _entry_correct(e):
                streak_fail += 1
            else:
                break

        last_ts = _entry_last_timestamp(entries)
        if last_ts is None:
            days_since = 0.0
            decayed = peak
        else:
            days_since = max(0.0, (now - last_ts).total_seconds() / 86400.0)
            tau = config.get_decay_constant(sid)
            decayed = peak * float(np.exp(-days_since / tau))

        views[sid] = {
            "peak": peak,
            "current": current,
            "decayed": decayed,
            "days_since": days_since,
            "last_ts": last_ts,
            "streak_success": streak_success,
            "streak_fail": streak_fail,
            "n_observations": len(entries),
        }
    return views


def _entry_correct(entry: Dict[str, Any]) -> bool:
    """条目 → 是否答对. 优先 correct 字段; 老条目缺 correct 时 score>=0.6 兜底
    (与 FeatureExtractor Step 3 MIRT 的兼容约定一致)."""
    correct = entry.get("correct")
    if correct is None:
        return float(entry.get("score", 0)) >= 0.6
    return bool(correct)


def _entry_last_timestamp(entries: List[Dict[str, Any]]) -> Optional[datetime]:
    """append 序倒序找第一条带 timestamp 的条目; 缺失/解析失败 → None."""
    for e in reversed(entries):
        raw = e.get("timestamp")
        if not raw:
            continue
        try:
            return datetime.fromisoformat(raw)
        except (TypeError, ValueError):
            logger.warning(
                "replay_mastery_view: timestamp 解析失败 (%r), 该条目视为无时间",
                raw, exc_info=True,
            )
    return None