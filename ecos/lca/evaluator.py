"""LCA 评估层 (Evaluator) —— v0.82 LCA 4-layer split 第 3 层.

对应:
  - research/00-overview/11-ecos-2.0-architecture-proposal.md §2.2.1 LCA 4-layer
  - research/00-overview/12-kernel-mapping-current-vs-2.0.md §4 LCA Evaluator
  - 旧 LCAEngine._estimate_gain / _estimate_risk + self.attribution 引用
    (orchestrator.py v0.81.0)

职责:
  - expected_gain 估算 (scale × (1 - bloom_mastery) × scaffolding_factor)
  - expected_risk 估算 (Frustration / Cheating 概率 = difficulty - K_mastery gap)
  - 因果归因 (wrap LCAAttribution.record_intervention / attribute_effect)
  - v0.69.0 cold-start fallback 走 estimate_gain (dual_agent 路径用)

设计原则:
  - Evaluator 是 2.0 §2.2.1 评估层, 不持有 bandit state / rationale
  - 持有 LCAAttribution 引用 (默认构造 CTA_L4_Backend, 可注入)
  - 纯函数 estimate_gain / estimate_risk: 输入相同 → 输出相同
  - gain_scale 从 LCAEngineConfig.expected_gain_scale 迁到 EvaluatorConfig.gain_scale
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from ..cta.belief_state import BeliefState, BloomLevel
from .intervention import Intervention
from .l4_optimization import (
    CTA_L4_Backend,
    CausalEffect,
    LCAAttribution,
)

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Evaluator Config
# ---------------------------------------------------------------------------

@dataclass
class EvaluatorConfig:
    """Evaluator 配置.

    Attributes:
        gain_scale:        expected_gain = gain_scale × (1 - bloom_mastery)
                            旧 LCAEngineConfig.expected_gain_scale (默认 0.3)
        risk_gap_coef:     expected_risk = max(0, difficulty - K_mastery) × risk_gap_coef
                            旧 _estimate_risk 写死 0.5
        scaffolding_factor: gain 乘子: (0.5 + 0.5 × scaffolding_level)
                            旧 _estimate_gain 写死 (0.5 + 0.5 × scaffolding_level)
    """

    gain_scale: float = 0.3
    risk_gap_coef: float = 0.5
    scaffolding_factor_base: float = 0.5  # gain 乘子常数项
    scaffolding_factor_range: float = 0.5  # gain 乘子 scaffolding 系数


# ---------------------------------------------------------------------------
# Evaluator 类
# ---------------------------------------------------------------------------

class Evaluator:
    """LCA 评估层 (v0.82 LCA 4-layer split 第 3 层).

    用法:
        evaluator = Evaluator(EvaluatorConfig(), attribution=LCAAttribution())
        # 1) select 阶段估算
        gain = evaluator.estimate_gain(intervention, belief_state)
        risk = evaluator.estimate_risk(intervention, belief_state)
        # 2) record 阶段 (推给 CTA L4 backend)
        evaluator.record_intervention(intervention, student_id)
        # 3) update 阶段 (归因, 拿 CausalEffect)
        effect = evaluator.attribute_effect(intervention, student_id, state_delta=0.3)

    旧代码 (LCAEngine v0.81.0):
        expected_gain = self._estimate_gain(chosen, belief_state)
        expected_risk = self._estimate_risk(chosen, belief_state)
        # record
        self.attribution.record_intervention(chosen, student_id)
        # update
        self.attribution.attribute_effect(intervention, student_id, state_delta)

    v0.82.0-c: 上述 4 个方法抽到 Evaluator, LCAEngine 仅委托.
    """

    def __init__(
        self,
        config: Optional[EvaluatorConfig] = None,
        attribution: Optional[LCAAttribution] = None,
        cta_l4_backend: Optional[CTA_L4_Backend] = None,
    ):
        self.config = config or EvaluatorConfig()
        # 持 LCAAttribution (默认构造, 可注入)
        self.attribution = attribution or LCAAttribution(cta_l4_backend or CTA_L4_Backend())

    # ---------------------------------------------------------------
    # 估算接口 (select 阶段用)
    # ---------------------------------------------------------------

    def estimate_gain(
        self,
        intervention: Intervention,
        belief_state: BeliefState,
    ) -> float:
        """估算 expected_gain = scale × (1 - bloom_mastery) × scaffolding_factor.

        跟 v0.81 LCAEngine._estimate_gain 行为完全一致.

        Args:
            intervention:  候选干预 (含 bloom_target / scaffolding_level)
            belief_state:  CTA 估计的 BeliefState (含 bloom_profile)

        Returns:
            float in [0, 1] 期望状态增量
        """
        bp_mastery = {
            BloomLevel.REMEMBER: belief_state.bloom_profile.remember,
            BloomLevel.UNDERSTAND: belief_state.bloom_profile.understand,
            BloomLevel.APPLY: belief_state.bloom_profile.apply,
            BloomLevel.ANALYZE: belief_state.bloom_profile.analyze,
            BloomLevel.EVALUATE: belief_state.bloom_profile.evaluate,
            BloomLevel.CREATE: belief_state.bloom_profile.create,
        }[intervention.bloom_target]
        gain = self.config.gain_scale * (1.0 - bp_mastery)
        # scaffolding 提升 gain (factor = base + range × scaffolding_level)
        scaffolding_factor = (
            self.config.scaffolding_factor_base
            + self.config.scaffolding_factor_range * intervention.scaffolding_level
        )
        gain *= scaffolding_factor
        return max(0.0, min(1.0, gain))

    def estimate_risk(
        self,
        intervention: Intervention,
        belief_state: BeliefState,
    ) -> float:
        """估算 expected_risk —— Frustration / Cheating 概率.

        规则 (跟 v0.81 LCAEngine._estimate_risk 行为一致):
        - 高难度 + 低 K mastery → 高 frustration 风险
        - 低 scaffolding + 错误率历史 → 中风险

        Args:
            intervention:  候选干预 (含 difficulty / scaffolding_level)
            belief_state:  CTA 估计的 BeliefState (含 K.mastery_prob)

        Returns:
            float in [0, 1] 期望风险
        """
        # 难度 - K mastery gap
        k_gap = intervention.difficulty - belief_state.K.mastery_prob
        risk = max(0.0, k_gap) * self.config.risk_gap_coef
        # scaffolding 缓解
        risk *= (1.0 - intervention.scaffolding_level)
        return max(0.0, min(1.0, risk))

    # ---------------------------------------------------------------
    # 归因接口 (record / update 阶段用)
    # ---------------------------------------------------------------

    def record_intervention(self, intervention: Intervention, student_id: str) -> None:
        """记录干预 (推给 CTA L4 backend, 跟 v0.81 LCAEngine.attribution 行为一致).

        旧代码: self.attribution.record_intervention(chosen, student_id)
        """
        self.attribution.record_intervention(intervention, student_id)

    def attribute_effect(
        self,
        intervention: Intervention,
        student_id: str,
        state_delta: float,
    ) -> CausalEffect:
        """归因 (推给 CTA L4 backend, 返回 CausalEffect).

        旧代码: self.attribution.attribute_effect(intervention, student_id, state_delta)
        LCAEngine.update() 不显式传 is_control, 所以这里也不传 (跟 v0.81 LCAEngine 行为一致)
        """
        return self.attribution.attribute_effect(
            intervention=intervention,
            student_id=student_id,
            state_delta=state_delta,
        )


__all__ = [
    "Evaluator",
    "EvaluatorConfig",
]
