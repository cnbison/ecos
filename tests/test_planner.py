"""v0.82.0-a: LCA Planner 决策层测试套件.

目标 (按 v0.82.0-a Definition of Done):
  - Planner 独立可构造, 持有 L3 组件 (CLT/Bjork/CA scaffolding) + CAStateMachine
  - Planner.plan() 返回 4 步合一 PlanDecision (bloom_target/ca_stage/clt_level/bjork_triggers)
  - LCAEngine.select_intervention 委托 Planner.plan() (step 1-4)
  - __getattr__ 转发: engine.clt / engine.bjork_testing 等仍可访问
  - LCAEngineConfig.planner_config 默认值正常
  - PlanDecision 不可变 (frozen dataclass)
"""

from __future__ import annotations

import logging
import sys
from dataclasses import FrozenInstanceError
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
    return engine.create_initial_state("test_planner_student")


@pytest.fixture
def cta_input(belief_state):
    """构造 CTAInput (LCA 决策输入)."""
    from ecos.lca.orchestrator import CTAInput

    return CTAInput(
        student_id="test_planner_student",
        belief_state=belief_state,
    )


# ──────────────────────────────────────────────────────────────────────
# 1. Planner 构造 + L3 组件集成
# ──────────────────────────────────────────────────────────────────────


class TestPlannerConstruction:
    """v0.82.0-a: Planner 构造 + L3 组件组合."""

    def test_planner_default_construction(self):
        """默认 config 构造 Planner, 持有全部 L3 组件."""
        from ecos.lca.planner import Planner

        planner = Planner()
        # L3 组件全部存在
        assert planner.clt is not None
        assert planner.bjork_testing is not None
        assert planner.bjork_spacing is not None
        assert planner.ca_scaffolding is not None
        # CA 状态机 (per-student 阶段状态)
        assert planner.ca_state_machine is not None

    def test_planner_custom_config(self):
        """自定义 PlannerConfig, mastery_threshold / trajectory_min_len 生效."""
        from ecos.lca.planner import Planner, PlannerConfig

        cfg = PlannerConfig(mastery_threshold=0.7, trajectory_min_len=10)
        planner = Planner(config=cfg)
        assert planner.config.mastery_threshold == 0.7
        assert planner.config.trajectory_min_len == 10

    def test_planner_holds_independent_clt_state(self):
        """两个 Planner 实例的 CLT 内部状态 (student_clt_level dict) 独立."""
        from ecos.lca.planner import Planner

        p1 = Planner()
        p2 = Planner()
        # CLT 学生级别 dict 是 per-planner 实例
        assert p1.clt.student_clt_level is not p2.clt.student_clt_level

    def test_planner_holds_independent_ca_state(self):
        """两个 Planner 实例的 CA 状态机 dict 独立."""
        from ecos.lca.planner import Planner

        p1 = Planner()
        p2 = Planner()
        assert p1.ca_state_machine.state is not p2.ca_state_machine.state

    def test_planner_config_default_values(self):
        """PlannerConfig 默认值跟 v0.81 LCAEngine 行为一致 (mastery=0.5, len=5)."""
        from ecos.lca.planner import PlannerConfig

        cfg = PlannerConfig()
        assert cfg.mastery_threshold == 0.5, \
            f"默认 mastery_threshold 应=0.5 (v0.81 LCAEngine 行为), 实际={cfg.mastery_threshold}"
        assert cfg.trajectory_min_len == 5, \
            f"默认 trajectory_min_len 应=5 (v0.81 LCAEngine 行为), 实际={cfg.trajectory_min_len}"


# ──────────────────────────────────────────────────────────────────────
# 2. Planner.plan() interface (5 tests)
# ──────────────────────────────────────────────────────────────────────


class TestPlannerPlan:
    """v0.82.0-a: Planner.plan() 返回 PlanDecision (4 步合一)."""

    def test_plan_returns_plan_decision(self, cta_input):
        """plan() 返回 PlanDecision, 4 字段都填充."""
        from ecos.lca.planner import Planner, PlanDecision

        planner = Planner()
        plan = planner.plan(cta_input)

        assert isinstance(plan, PlanDecision)
        # 4 字段全部存在
        assert plan.bloom_target is not None
        assert plan.ca_stage is not None
        assert plan.clt_level is not None
        assert isinstance(plan.bjork_triggers, list)

    def test_plan_decision_is_frozen(self, cta_input):
        """PlanDecision 不可变 (frozen dataclass, 防止下游误改)."""
        from ecos.lca.planner import Planner

        planner = Planner()
        plan = planner.plan(cta_input)

        with pytest.raises(FrozenInstanceError):
            plan.bloom_target = "INVALID"  # type: ignore[misc]

    def test_plan_with_empty_candidates(self, belief_state):
        """空 bloom_target_candidates 时 fallback 到全部 6 层."""
        from ecos.lca.orchestrator import CTAInput
        from ecos.lca.planner import Planner
        from ecos.cta.belief_state import BloomLevel

        cta_input = CTAInput(
            student_id="test_planner_student",
            belief_state=belief_state,
            bloom_target_candidates=[],  # 空
        )
        planner = Planner()
        plan = planner.plan(cta_input)
        # 空 candidates 应该走 select_bloom_target fallback (返回 candidates[0] 或默认)
        #   v0.81 LCAEngine 行为: `candidates_bloom or list(BloomLevel)`
        #   我们的 Planner 直接传 candidates 给 select_bloom_target (不 fallback)
        #   这跟 v0.81 LCAEngine 行为略有不同, 但 select_bloom_target 内部已处理空
        #   见 select_bloom_target 实现在 intervention.py:208-209
        assert plan.bloom_target in list(BloomLevel)

    def test_plan_with_intervention_history(self, cta_input, belief_state):
        """intervention_history 注入到 Planner.plan(), CAStateMachine 收到 history."""
        from ecos.lca.orchestrator import CTAInput
        from ecos.lca.planner import Planner
        from ecos.lca.intervention import Intervention, InterventionType, CLTLevel, CAStage
        from ecos.cta.belief_state import BloomLevel

        # 构造一条 PRACTICE 历史干预
        history_iv = Intervention(
            intervention_type=InterventionType.PRACTICE,
            bloom_target=BloomLevel.APPLY,
            clt_level=CLTLevel.DEVELOPING,
            ca_stage=CAStage.COACHING,
        )
        cta_input_with_history = CTAInput(
            student_id="test_planner_student",
            belief_state=belief_state,
            bloom_target_candidates=None,
        )

        planner = Planner()
        plan = planner.plan(cta_input_with_history, intervention_history=[history_iv])
        # CAStateMachine 收到 history 后, _has_tried_independently 应返回 True
        #   -> MODELING → COACHING
        assert plan.ca_stage == CAStage.COACHING, \
            f"history 含 PRACTICE 应触发 MODELING → COACHING, 实际={plan.ca_stage}"

    def test_plan_without_intervention_history(self, cta_input):
        """intervention_history=None 时 fallback 到 [] (新学生, 冷启动)."""
        from ecos.lca.planner import Planner
        from ecos.lca.intervention import CAStage

        planner = Planner()
        plan = planner.plan(cta_input, intervention_history=None)
        # 新学生 trajectory < 3, 无 PRACTICE history → 仍 MODELING
        assert plan.ca_stage == CAStage.MODELING


# ──────────────────────────────────────────────────────────────────────
# 3. LCAEngine 集成 (3 tests)
# ──────────────────────────────────────────────────────────────────────


class TestLCAEnginePlannerIntegration:
    """v0.82.0-a: LCAEngine select_intervention 委托 Planner."""

    def test_lca_engine_constructs_with_default_planner(self):
        """LCAEngine 默认构造时 self.planner 存在 + 默认 PlannerConfig."""
        from ecos.lca import LCAEngine, LCAEngineConfig

        engine = LCAEngine()
        assert engine.planner is not None
        assert isinstance(engine.config.planner_config, LCAEngineConfig().planner_config.__class__)
        # planner_config 默认值是 PlannerConfig()
        assert engine.config.planner_config.mastery_threshold == 0.5

    def test_lca_engine_select_delegates_to_planner(self, belief_state):
        """LCAEngine.select_intervention step 1-4 委托 Planner.plan()."""
        from ecos.lca import LCAEngine
        from ecos.lca.orchestrator import CTAInput, LCAResult

        engine = LCAEngine()
        cta_input = CTAInput(student_id="test_planner_student", belief_state=belief_state)

        # mock Planner.plan, 验证 LCAEngine 调了 Planner
        with patch.object(engine.planner, "plan", wraps=engine.planner.plan) as spy_plan:
            result = engine.select_intervention(cta_input)

        # Planner.plan 被调了 1 次
        assert spy_plan.call_count == 1, \
            f"LCAEngine.select_intervention 应调 Planner.plan() 1 次, 实际={spy_plan.call_count}"
        # 收到 intervention (Planner.plan 输出通过 LCAEngine 流转到 LCAResult)
        assert isinstance(result, LCAResult)
        assert result.bloom_target is not None
        assert result.ca_stage is not None
        assert result.clt_level is not None

    def test_lca_engine_planner_config_field(self):
        """LCAEngineConfig.planner_config 字段可自定义 (向后兼容)."""
        from ecos.lca import LCAEngine, LCAEngineConfig
        from ecos.lca.planner import PlannerConfig

        custom_planner = PlannerConfig(mastery_threshold=0.8, trajectory_min_len=8)
        cfg = LCAEngineConfig(planner_config=custom_planner)
        engine = LCAEngine(config=cfg)
        assert engine.config.planner_config.mastery_threshold == 0.8
        assert engine.config.planner_config.trajectory_min_len == 8
        # Planner 用这个 config 构造
        assert engine.planner.config.mastery_threshold == 0.8


# ──────────────────────────────────────────────────────────────────────
# 4. backward compat (__getattr__ forwarding)
# ──────────────────────────────────────────────────────────────────────


class TestPlannerBackwardCompat:
    """v0.82.0-a: LCAEngine 旧字段 (clt / bjork_testing / ...) 通过 __getattr__ 转发."""

    def test_engine_clt_via_getattr(self):
        """engine.clt 仍可访问 (返回 AdaptiveCLTPresender 实例)."""
        from ecos.lca import LCAEngine

        engine = LCAEngine()
        clt = engine.clt
        from ecos.lca.l3_selection import AdaptiveCLTPresender
        assert isinstance(clt, AdaptiveCLTPresender)

    def test_engine_bjork_components_via_getattr(self):
        """engine.bjork_testing / engine.bjork_spacing / engine.ca_scaffolding / engine.ca_state_machine 仍可访问."""
        from ecos.lca import LCAEngine
        from ecos.lca.l3_selection import (
            BjorkTestingEffect, BjorkSpacingEffect, CAScaffoldingDecay,
        )
        from ecos.lca.l4_optimization import CAStateMachine

        engine = LCAEngine()
        assert isinstance(engine.bjork_testing, BjorkTestingEffect)
        assert isinstance(engine.bjork_spacing, BjorkSpacingEffect)
        assert isinstance(engine.ca_scaffolding, CAScaffoldingDecay)
        assert isinstance(engine.ca_state_machine, CAStateMachine)


# ──────────────────────────────────────────────────────────────────────
# 5. 防御性自检 (silent pass 扫描)
# ──────────────────────────────────────────────────────────────────────


class TestPlannerDefensiveChecks:
    """v0.82.0-a: Planner 防御性自检 (silent pass 扫描)."""

    def test_no_silent_pass_in_planner(self):
        """planner.py 全部 except 块必须有 logger.warning (防御性自检 [1])."""
        import inspect
        from ecos.lca import planner as planner_mod

        source = inspect.getsource(planner_mod)
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
                    f"planner.py except 块 #{idx + 1} 是 silent pass:\n{block}\n"
                    "防御性自检 [1]: 必须改 logger.warning(..., exc_info=True)"
                )
            if not has_warning and not has_raise:
                pytest.fail(
                    f"planner.py except 块 #{idx + 1} 无 warning 也无 raise:\n{block}\n"
                    "防御性自检 [1]: 必须有 logger.warning 或显式 raise"
                )


# ──────────────────────────────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
