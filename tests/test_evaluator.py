"""v0.82.0-c: LCA Evaluator 评估层测试套件.

目标 (按 v0.82.0-c Definition of Done):
  - Evaluator 独立可构造, 持有 EvaluatorConfig + LCAAttribution
  - estimate_gain / estimate_risk 跟 v0.81 LCAEngine._estimate_gain / _estimate_risk 行为一致
  - record_intervention / attribute_effect 委托 self.attribution (保持行为)
  - LCAEngine.select_intervention 委托 self.evaluator.estimate_gain/risk
  - LCAEngine.update() 委托 self.evaluator.attribute_effect
  - LCAEngine._estimate_gain backward-compat shim 委托 evaluator (dual_agent 路径)
  - LCAEngine.attribution 仍可访问 (tests/test_lca_update_reward_actual_outcome.py monkey-patch)
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def belief_state():
    """构造最小 BeliefState (跟 test_lca_wired.py 一致)."""
    from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig
    from ecos.cta.l1_evolution import EvolutionConfig
    from ecos.cta.l2_mirt import MIRTConfig

    config = BeliefEngineConfig(
        evolution_config=EvolutionConfig(),
        mirt_config=MIRTConfig(
            prior_mean=[0.0] * 5,
            prior_cov=None,
            default_a_specialized=[0.8] * 5,
            default_a_general=0.5,
            default_difficulty=0.0,
        ),
    )
    engine = BeliefEngine(config=config, llm_client=None)
    return engine.create_initial_state("test_evaluator_student")


@pytest.fixture
def intervention():
    """构造一个标准 Intervention 用于 estimate_gain/risk 测试."""
    from ecos.lca.intervention import Intervention, InterventionType, CLTLevel, CAStage
    from ecos.cta.belief_state import BloomLevel

    return Intervention(
        intervention_type=InterventionType.PRACTICE,
        bloom_target=BloomLevel.APPLY,
        clt_level=CLTLevel.DEVELOPING,
        ca_stage=CAStage.COACHING,
        difficulty=0.5,
        scaffolding_level=0.6,
    )


# ──────────────────────────────────────────────────────────────────────
# 1. Evaluator 构造 + 默认行为 (2 tests)
# ──────────────────────────────────────────────────────────────────────


class TestEvaluatorConstruction:
    """v0.82.0-c: Evaluator 构造 + 默认行为."""

    def test_evaluator_default_construction(self):
        """默认 config 构造 Evaluator, 持有 default LCAAttribution + default CTA_L4_Backend."""
        from ecos.lca.evaluator import Evaluator, EvaluatorConfig
        from ecos.lca.l4_optimization import LCAAttribution, CTA_L4_Backend

        ev = Evaluator()
        assert isinstance(ev.config, EvaluatorConfig)
        assert isinstance(ev.attribution, LCAAttribution)
        assert isinstance(ev.attribution.backend, CTA_L4_Backend)
        # 默认 gain_scale = 0.3 (跟 v0.81 LCAEngineConfig.expected_gain_scale 一致)
        assert ev.config.gain_scale == 0.3
        assert ev.config.risk_gap_coef == 0.5

    def test_evaluator_custom_attribution(self):
        """自定义 LCAAttribution 注入."""
        from ecos.lca.evaluator import Evaluator
        from ecos.lca.l4_optimization import LCAAttribution, CTA_L4_Backend

        custom_attr = LCAAttribution(CTA_L4_Backend())
        ev = Evaluator(attribution=custom_attr)
        assert ev.attribution is custom_attr


# ──────────────────────────────────────────────────────────────────────
# 2. estimate_gain / estimate_risk 行为 (4 tests)
# ──────────────────────────────────────────────────────────────────────


class TestEvaluatorEstimateGainRisk:
    """v0.82.0-c: estimate_gain / estimate_risk 跟 v0.81 行为一致."""

    def test_estimate_gain_zero_mastery(self, intervention, belief_state):
        """bloom_mastery=0 → gain = scale × 1.0 × scaffolding_factor."""
        from ecos.lca.evaluator import Evaluator
        from ecos.cta.belief_state import BloomLevel

        # 把 bloom_profile.apply 设为 0
        belief_state.bloom_profile.apply = 0.0
        intervention.bloom_target = BloomLevel.APPLY

        ev = Evaluator()
        gain = ev.estimate_gain(intervention, belief_state)
        # expected: 0.3 × (1 - 0) × (0.5 + 0.5 × 0.6) = 0.3 × 1.0 × 0.8 = 0.24
        assert abs(gain - 0.24) < 0.01, \
            f"mastery=0 应 gain=0.24, 实际={gain}"

    def test_estimate_gain_full_mastery(self, intervention, belief_state):
        """bloom_mastery=1 → gain = 0."""
        from ecos.lca.evaluator import Evaluator
        from ecos.cta.belief_state import BloomLevel

        belief_state.bloom_profile.apply = 1.0
        intervention.bloom_target = BloomLevel.APPLY

        ev = Evaluator()
        gain = ev.estimate_gain(intervention, belief_state)
        assert abs(gain - 0.0) < 0.01, f"mastery=1 应 gain=0, 实际={gain}"

    def test_estimate_risk_low_mastery_high_difficulty(self, belief_state):
        """K_mastery=0.3 + difficulty=0.8 → 高 frustration 风险."""
        from ecos.lca.evaluator import Evaluator
        from ecos.lca.intervention import Intervention, InterventionType, CLTLevel, CAStage
        from ecos.cta.belief_state import BloomLevel

        belief_state.K.mastery_prob = 0.3
        iv = Intervention(
            intervention_type=InterventionType.PRACTICE,
            bloom_target=BloomLevel.APPLY,
            clt_level=CLTLevel.EXPERT,  # 低 scaffolding
            ca_stage=CAStage.COACHING,
            difficulty=0.8,
            scaffolding_level=0.1,
        )

        ev = Evaluator()
        risk = ev.estimate_risk(iv, belief_state)
        # k_gap = 0.8 - 0.3 = 0.5
        # risk = 0.5 × 0.5 × (1 - 0.1) = 0.225
        assert abs(risk - 0.225) < 0.01, f"高难度+低 mastery+低 scaffolding 应 risk≈0.225, 实际={risk}"

    def test_estimate_risk_high_mastery_low_difficulty(self, belief_state):
        """K_mastery=0.9 + difficulty=0.2 → 低 frustration 风险 (k_gap 负 → 0)."""
        from ecos.lca.evaluator import Evaluator
        from ecos.lca.intervention import Intervention, InterventionType, CLTLevel, CAStage
        from ecos.cta.belief_state import BloomLevel

        belief_state.K.mastery_prob = 0.9
        iv = Intervention(
            intervention_type=InterventionType.PRACTICE,
            bloom_target=BloomLevel.APPLY,
            clt_level=CLTLevel.NOVICE,  # 高 scaffolding 缓解
            ca_stage=CAStage.COACHING,
            difficulty=0.2,
            scaffolding_level=0.9,
        )

        ev = Evaluator()
        risk = ev.estimate_risk(iv, belief_state)
        # k_gap = 0.2 - 0.9 = -0.7 → max(0, -0.7) = 0
        # risk = 0 × 0.5 × (1 - 0.9) = 0
        assert abs(risk - 0.0) < 0.01, f"低难度+高 mastery 应 risk=0, 实际={risk}"


# ──────────────────────────────────────────────────────────────────────
# 3. 归因接口 (2 tests)
# ──────────────────────────────────────────────────────────────────────


class TestEvaluatorAttribution:
    """v0.82.0-c: record_intervention / attribute_effect 委托 self.attribution."""

    def test_record_intervention_delegates(self, intervention):
        """record_intervention 委托 self.attribution.record_intervention."""
        from ecos.lca.evaluator import Evaluator
        from unittest.mock import MagicMock

        ev = Evaluator()
        # mock attribution
        ev.attribution = MagicMock()
        ev.record_intervention(intervention, "test_student")
        # verify delegation
        ev.attribution.record_intervention.assert_called_once_with(intervention, "test_student")

    def test_attribute_effect_delegates(self, intervention):
        """attribute_effect 委托 self.attribution.attribute_effect (返回 CausalEffect)."""
        from ecos.lca.evaluator import Evaluator
        from ecos.lca.l4_optimization import CausalEffect
        from unittest.mock import MagicMock

        ev = Evaluator()
        # mock attribution 返回 CausalEffect
        mock_effect = CausalEffect(
            intervention_type="practice",
            student_id="test_student",
            state_delta=0.3,
            estimated_ate=0.3,
            confidence=0.1,
        )
        ev.attribution = MagicMock()
        ev.attribution.attribute_effect.return_value = mock_effect

        result = ev.attribute_effect(intervention, "test_student", state_delta=0.3)
        assert result is mock_effect
        ev.attribution.attribute_effect.assert_called_once_with(
            intervention=intervention,
            student_id="test_student",
            state_delta=0.3,
        )


# ──────────────────────────────────────────────────────────────────────
# 4. LCAEngine 集成 (4 tests)
# ──────────────────────────────────────────────────────────────────────


class TestLCAEngineEvaluatorIntegration:
    """v0.82.0-c: LCAEngine select_intervention / update 委托 Evaluator."""

    def test_lca_engine_constructs_with_default_evaluator(self):
        """LCAEngine 默认构造时 self.evaluator 存在."""
        from ecos.lca import LCAEngine, EvaluatorConfig

        engine = LCAEngine()
        assert engine.evaluator is not None
        assert isinstance(engine.config.evaluator_config, EvaluatorConfig)

    def test_lca_engine_attribution_is_evaluator_attribution(self):
        """LCAEngine.attribution 引用 = LCAEngine.evaluator.attribution (shared).

        原因: tests/test_lca_update_reward_actual_outcome.py:196 monkey-patch
              lca_engine.attribution.attribute_effect, 必须共享同一对象.
        """
        from ecos.lca import LCAEngine

        engine = LCAEngine()
        assert engine.attribution is engine.evaluator.attribution, \
            f"engine.attribution ({engine.attribution}) 应 == engine.evaluator.attribution ({engine.evaluator.attribution})"

    def test_lca_engine_estimate_gain_shim(self, intervention, belief_state):
        """LCAEngine._estimate_gain 委托 self.evaluator.estimate_gain (backward compat).

        原因: dual_agent/orchestrator.py:579 调 `self.lca_engine._estimate_gain(...)`,
              必须保持方法签名.
        """
        from ecos.lca import LCAEngine

        engine = LCAEngine()
        gain_via_shim = engine._estimate_gain(intervention, belief_state)
        gain_via_evaluator = engine.evaluator.estimate_gain(intervention, belief_state)
        assert abs(gain_via_shim - gain_via_evaluator) < 1e-9, \
            f"_estimate_gain shim 应 == evaluator.estimate_gain, " \
            f"shim={gain_via_shim}, evaluator={gain_via_evaluator}"

    def test_lca_engine_select_uses_evaluator(self, belief_state):
        """LCAEngine.select_intervention 委托 self.evaluator.estimate_gain/risk.

        验证: select 后 LCAResult.expected_gain 来自 self.evaluator.estimate_gain(...)
        """
        from ecos.lca import LCAEngine
        from ecos.lca.cta_input import CTAInput
        from unittest.mock import patch

        engine = LCAEngine()
        cta_input = CTAInput(student_id="test_evaluator_student", belief_state=belief_state)

        with patch.object(
            engine.evaluator, "estimate_gain", return_value=0.42,
        ) as spy_gain, patch.object(
            engine.evaluator, "estimate_risk", return_value=0.13,
        ) as spy_risk:
            result = engine.select_intervention(cta_input)

        assert spy_gain.call_count == 1
        assert spy_risk.call_count == 1
        assert result.expected_gain == 0.42
        assert result.expected_risk == 0.13


# ──────────────────────────────────────────────────────────────────────
# 5. 防御性自检 (1 test)
# ──────────────────────────────────────────────────────────────────────


class TestEvaluatorDefensiveChecks:
    """v0.82.0-c: Evaluator 防御性自检 (silent pass 扫描)."""

    def test_no_silent_pass_in_evaluator(self):
        """evaluator.py 全部 except 块必须有 logger.warning."""
        import inspect
        from ecos.lca import evaluator as ev_mod

        source = inspect.getsource(ev_mod)
        lines = source.split("\n")

        except_blocks = []
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.lstrip()
            if stripped.startswith("except") and line.rstrip().endswith(":"):
                except_indent = len(line) - len(line.lstrip())
                block_lines = []
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    if not next_line.strip():
                        i += 1
                        continue
                    next_indent = len(next_line) - len(next_line.lstrip())
                    if next_indent > except_indent:
                        block_lines.append(next_line)
                        i += 1
                    else:
                        break
                except_blocks.append("\n".join(block_lines))
            else:
                i += 1

        for idx, block in enumerate(except_blocks):
            has_warning = "warning" in block
            has_raise = "raise " in block or block.strip().endswith("raise")
            has_silent_pass = "pass" in block and not has_warning

            if has_silent_pass:
                pytest.fail(
                    f"evaluator.py except 块 #{idx + 1} 是 silent pass:\n{block}\n"
                    "防御性自检 [1]: 必须改 logger.warning(..., exc_info=True)"
                )
            if not has_warning and not has_raise:
                pytest.fail(
                    f"evaluator.py except 块 #{idx + 1} 无 warning 也无 raise:\n{block}\n"
                    "防御性自检 [1]: 必须有 logger.warning 或显式 raise"
                )


# ──────────────────────────────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
