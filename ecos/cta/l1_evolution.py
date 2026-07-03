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

from dataclasses import dataclass, field
from typing import Dict

import numpy as np


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