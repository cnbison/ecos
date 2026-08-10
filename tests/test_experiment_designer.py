"""v0.82.0-b: LCA Experiment Designer 实验设计层测试套件.

目标 (按 v0.82.0-b Definition of Done):
  - ExperimentDesigner 独立可构造, 持有 ExperimentDesignerConfig
  - design(plan, cta_input, n_candidates) -> List[Intervention] 候选池生成
  - CA 阶段调整 (MODELING/COACHING/SCAFFOLDING) 行为跟 v0.81 _generate_candidates 一致
  - Bjork 触发调整 (test/space) 行为跟 v0.81 一致
  - CLT 4 级 → scaffolding_level 映射 (0.9/0.6/0.3/0.1) 保持
  - LCAEngine.select_intervention step 5 委托 self.experiment_designer.design()
  - 防御性自检 [8] 仍 hard block (LCAEngine 不引入新 mutation site)
"""

from __future__ import annotations

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
    return engine.create_initial_state("test_designer_student")


@pytest.fixture
def cta_input(belief_state):
    """构造 CTAInput (LCA 实验设计输入)."""
    from ecos.lca.cta_input import CTAInput

    return CTAInput(
        student_id="test_designer_student",
        belief_state=belief_state,
    )


@pytest.fixture
def plan_decision_default(belief_state):
    """构造默认 PlanDecision (CAStage.MODELING, CLTLevel.DEVELOPING, 无 bjork)."""
    from ecos.lca.planner import PlanDecision
    from ecos.lca.intervention import CAStage, CLTLevel
    from ecos.cta.belief_state import BloomLevel

    return PlanDecision(
        bloom_target=BloomLevel.APPLY,
        ca_stage=CAStage.MODELING,
        clt_level=CLTLevel.DEVELOPING,
        bjork_triggers=[],
    )


# ──────────────────────────────────────────────────────────────────────
# 1. ExperimentDesigner 构造 + 默认行为 (3 tests)
# ──────────────────────────────────────────────────────────────────────


class TestExperimentDesignerConstruction:
    """v0.82.0-b: ExperimentDesigner 构造 + 默认池."""

    def test_designer_default_construction(self):
        """默认 config 构造 ExperimentDesigner, 10 个候选池 + 默认池."""
        from ecos.lca.experiment_designer import (
            ExperimentDesigner, ExperimentDesignerConfig,
        )

        designer = ExperimentDesigner()
        assert isinstance(designer.config, ExperimentDesignerConfig)
        assert designer.config.n_candidates == 10
        # 默认池长度 = 10
        assert len(designer.config.default_types) == 10
        assert len(designer.config.default_difficulties) == 10

    def test_designer_custom_config(self):
        """自定义 ExperimentDesignerConfig (n_candidates=5, 自定义池)."""
        from ecos.lca.experiment_designer import ExperimentDesigner, ExperimentDesignerConfig
        from ecos.lca.intervention import InterventionType

        custom = ExperimentDesignerConfig(
            n_candidates=5,
            default_types=[InterventionType.PRACTICE] * 5,
            default_difficulties=[0.5] * 5,
        )
        designer = ExperimentDesigner(config=custom)
        assert designer.config.n_candidates == 5
        assert len(designer.config.default_types) == 5

    def test_design_produces_n_candidates(self, plan_decision_default, cta_input):
        """design() 返回 list 长度 = n_candidates."""
        from ecos.lca.experiment_designer import ExperimentDesigner
        from ecos.lca.intervention import Intervention

        designer = ExperimentDesigner()
        candidates = designer.design(plan_decision_default, cta_input, n_candidates=10)
        assert len(candidates) == 10
        for c in candidates:
            assert isinstance(c, Intervention)


# ──────────────────────────────────────────────────────────────────────
# 2. CA 阶段调整 (3 tests)
# ──────────────────────────────────────────────────────────────────────


class TestExperimentDesignerCAStage:
    """v0.82.0-b: CA 阶段调整 itype (跟 v0.81 _generate_candidates 行为一致)."""

    def test_modeling_stage_uses_explanatory(self, plan_decision_default, cta_input):
        """CAStage.MODELING: 大多数 itype → EXPLANATORY (除 i % 3 == 0)."""
        from ecos.lca.experiment_designer import ExperimentDesigner
        from ecos.lca.intervention import InterventionType, CAStage

        plan = plan_decision_default
        plan = type(plan)(
            bloom_target=plan.bloom_target,
            ca_stage=CAStage.MODELING,
            clt_level=plan.clt_level,
            bjork_triggers=plan.bjork_triggers,
        )
        designer = ExperimentDesigner()
        candidates = designer.design(plan, cta_input, n_candidates=10)

        # 验证 i % 3 != 0 的候选都是 EXPLANATORY
        for i, c in enumerate(candidates):
            if i % 3 != 0:
                assert c.intervention_type == InterventionType.EXPLANATORY, \
                    f"MODELING i={i} 应 EXPLANATORY, 实际={c.intervention_type}"

    def test_coaching_stage_uses_practice(self, plan_decision_default, cta_input):
        """CAStage.COACHING: 非 PRACTICE/FEEDBACK → PRACTICE."""
        from ecos.lca.experiment_designer import ExperimentDesigner
        from ecos.lca.intervention import InterventionType, CAStage

        plan = plan_decision_default
        plan = type(plan)(
            bloom_target=plan.bloom_target,
            ca_stage=CAStage.COACHING,
            clt_level=plan.clt_level,
            bjork_triggers=plan.bjork_triggers,
        )
        designer = ExperimentDesigner()
        candidates = designer.design(plan, cta_input, n_candidates=10)

        # 验证全部 itype 都在 (PRACTICE, FEEDBACK)
        for i, c in enumerate(candidates):
            assert c.intervention_type in (
                InterventionType.PRACTICE, InterventionType.FEEDBACK,
            ), f"COACHING i={i} 应 PRACTICE/FEEDBACK, 实际={c.intervention_type}"

    def test_scaffolding_stage_uses_explanatory(self, plan_decision_default, cta_input):
        """CAStage.SCAFFOLDING: 非 EXPLANATORY/METACOGNITIVE → EXPLANATORY."""
        from ecos.lca.experiment_designer import ExperimentDesigner
        from ecos.lca.intervention import InterventionType, CAStage

        plan = plan_decision_default
        plan = type(plan)(
            bloom_target=plan.bloom_target,
            ca_stage=CAStage.SCAFFOLDING,
            clt_level=plan.clt_level,
            bjork_triggers=plan.bjork_triggers,
        )
        designer = ExperimentDesigner()
        candidates = designer.design(plan, cta_input, n_candidates=10)

        for c in candidates:
            assert c.intervention_type in (
                InterventionType.EXPLANATORY, InterventionType.METACOGNITIVE,
            ), f"SCAFFOLDING 应 EXPLANATORY/METACOGNITIVE, 实际={c.intervention_type}"


# ──────────────────────────────────────────────────────────────────────
# 3. Bjork 触发 + CLT 映射 (3 tests)
# ──────────────────────────────────────────────────────────────────────


class TestExperimentDesignerBjorkAndCLT:
    """v0.82.0-b: Bjork 触发 + CLT → scaffolding 映射."""

    def test_bjork_test_adds_retrieval(self, plan_decision_default, cta_input):
        """bjork trigger 'test' + INQUIRY → 加 'retrieval' 标签."""
        from ecos.lca.experiment_designer import ExperimentDesigner
        from ecos.lca.intervention import InterventionType, CAStage, CLTLevel
        from ecos.cta.belief_state import BloomLevel
        from ecos.lca.planner import PlanDecision

        # 用 COACHING 之外的 stage 让 INQUIRY 保留, 然后强制设 bjork=test
        # 实际上 MODELING 也保留 INQUIRY (i % 3 == 0), 但其他 i 改 EXPLANATORY
        # 简化: 直接看 bjork test 配合 INQUIRY 是否加 retrieval
        plan = PlanDecision(
            bloom_target=BloomLevel.APPLY,
            ca_stage=CAStage.MODELING,
            clt_level=CLTLevel.DEVELOPING,
            bjork_triggers=["test"],
        )
        designer = ExperimentDesigner()
        candidates = designer.design(plan, cta_input, n_candidates=10)

        # 找 INQUIRY 类型的 candidate
        inquiry_candidates = [c for c in candidates if c.intervention_type == InterventionType.INQUIRY]
        # 至少应有 1 个 INQUIRY (i=4 在 default pool 是 INQUIRY, i % 3 == 4 % 3 == 1, MODELING 改 EXPLANATORY)
        #   所以 MODELING 状态下 INQUIRY 都被改 EXPLANATORY
        # 改用 ARTICULATION 阶段 (M2 W2 占位, 不调整 itype) - 但 ARTICULATION 是 Phase 5+
        # 简化: 用 COACHING + 改 config 让 INQUIRY 出现
        from ecos.lca.experiment_designer import ExperimentDesignerConfig
        custom_cfg = ExperimentDesignerConfig(
            n_candidates=10,
            default_types=[
                InterventionType.INQUIRY,  # 0
                InterventionType.PRACTICE,  # 1
                InterventionType.INQUIRY,  # 2
                InterventionType.PRACTICE,  # 3
                InterventionType.INQUIRY,  # 4
                InterventionType.PRACTICE,  # 5
                InterventionType.INQUIRY,  # 6
                InterventionType.PRACTICE,  # 7
                InterventionType.INQUIRY,  # 8
                InterventionType.PRACTICE,  # 9
            ],
        )
        designer2 = ExperimentDesigner(config=custom_cfg)
        # 用 ARTICULATION (M2 W2 不调整 itype, 保留原 pool)
        # 但 ARTICULATION = CAStage.ARTICULATION = 4, 走 None 分支
        # 实际是: _adjust_for_ca_stage 只处理 MODELING/COACHING/SCAFFOLDING
        #   其他 ca_stage (ARTICULATION/REFLECTION/EXPLORATION) 走 fallback return itype
        #   所以 INQUIRY 保留
        from ecos.lca.intervention import CAStage as CAS
        plan2 = PlanDecision(
            bloom_target=BloomLevel.APPLY,
            ca_stage=CAS.ARTICULATION,  # 不调整 itype
            clt_level=CLTLevel.DEVELOPING,
            bjork_triggers=["test"],
        )
        candidates2 = designer2.design(plan2, cta_input, n_candidates=10)
        inquiry_in_plan2 = [c for c in candidates2 if c.intervention_type == InterventionType.INQUIRY]
        assert len(inquiry_in_plan2) > 0, "应有 INQUIRY candidate"
        for c in inquiry_in_plan2:
            assert "retrieval" in c.bjork_triggers, \
                f"INQUIRY + bjork=test 应加 'retrieval', 实际={c.bjork_triggers}"

    def test_bjork_space_lowers_difficulty(self, plan_decision_default, cta_input):
        """bjork trigger 'space' → difficulty ≤ 0.5."""
        from ecos.lca.experiment_designer import ExperimentDesigner
        from ecos.lca.intervention import CAStage, CLTLevel
        from ecos.cta.belief_state import BloomLevel
        from ecos.lca.planner import PlanDecision

        plan = PlanDecision(
            bloom_target=BloomLevel.APPLY,
            ca_stage=CAStage.MODELING,
            clt_level=CLTLevel.DEVELOPING,
            bjork_triggers=["space"],
        )
        designer = ExperimentDesigner()
        candidates = designer.design(plan, cta_input, n_candidates=10)

        # 验证 difficulty 全部 ≤ 0.5
        for c in candidates:
            assert c.difficulty <= 0.5, \
                f"bjork=space 应让 difficulty ≤ 0.5, 实际={c.difficulty}"

    def test_clt_level_maps_to_scaffolding(self, plan_decision_default, cta_input):
        """CLT 4 级 → scaffolding_level 映射 (0.9/0.6/0.3/0.1)."""
        from ecos.lca.experiment_designer import ExperimentDesigner
        from ecos.lca.intervention import CAStage, CLTLevel
        from ecos.cta.belief_state import BloomLevel
        from ecos.lca.planner import PlanDecision

        designer = ExperimentDesigner()
        expected = {
            CLTLevel.NOVICE: 0.9,
            CLTLevel.DEVELOPING: 0.6,
            CLTLevel.PROFICIENT: 0.3,
            CLTLevel.EXPERT: 0.1,
        }
        for clt_level, expected_scaff in expected.items():
            plan = PlanDecision(
                bloom_target=BloomLevel.APPLY,
                ca_stage=CAStage.MODELING,
                clt_level=clt_level,
                bjork_triggers=[],
            )
            candidates = designer.design(plan, cta_input, n_candidates=1)
            assert candidates[0].scaffolding_level == expected_scaff, \
                f"CLT={clt_level} 应 scaffolding={expected_scaff}, 实际={candidates[0].scaffolding_level}"


# ──────────────────────────────────────────────────────────────────────
# 4. LCAEngine 集成 (3 tests)
# ──────────────────────────────────────────────────────────────────────


class TestLCAEngineDesignerIntegration:
    """v0.82.0-b: LCAEngine select_intervention step 5 委托 ExperimentDesigner."""

    def test_lca_engine_constructs_with_default_designer(self):
        """LCAEngine 默认构造时 self.experiment_designer 存在."""
        from ecos.lca import LCAEngine, ExperimentDesignerConfig

        engine = LCAEngine()
        assert engine.experiment_designer is not None
        assert isinstance(engine.config.experiment_designer_config, ExperimentDesignerConfig)

    def test_lca_engine_select_delegates_to_designer(self, belief_state):
        """LCAEngine.select_intervention step 5 委托 self.experiment_designer.design()."""
        from ecos.lca import LCAEngine
        from ecos.lca.cta_input import CTAInput

        engine = LCAEngine()
        cta_input = CTAInput(student_id="test_designer_student", belief_state=belief_state)

        with patch.object(
            engine.experiment_designer, "design",
            wraps=engine.experiment_designer.design,
        ) as spy_design:
            engine.select_intervention(cta_input)

        # designer.design 被调了 1 次
        assert spy_design.call_count == 1, \
            f"LCAEngine.select_intervention 应调 designer.design() 1 次, 实际={spy_design.call_count}"

    def test_lca_engine_designer_config_field(self):
        """LCAEngineConfig.experiment_designer_config 字段可自定义."""
        from ecos.lca import LCAEngine, LCAEngineConfig
        from ecos.lca.experiment_designer import ExperimentDesignerConfig
        from ecos.lca.intervention import InterventionType

        custom = ExperimentDesignerConfig(
            n_candidates=5,
            default_types=[InterventionType.PRACTICE] * 5,
        )
        cfg = LCAEngineConfig(experiment_designer_config=custom)
        engine = LCAEngine(config=cfg)
        assert engine.config.experiment_designer_config.n_candidates == 5


# ──────────────────────────────────────────────────────────────────────
# 5. 防御性自检 (1 test)
# ──────────────────────────────────────────────────────────────────────


class TestExperimentDesignerDefensiveChecks:
    """v0.82.0-b: ExperimentDesigner 防御性自检 (silent pass 扫描)."""

    def test_no_silent_pass_in_designer(self):
        """experiment_designer.py 全部 except 块必须有 logger.warning."""
        import inspect
        from ecos.lca import experiment_designer as designer_mod

        source = inspect.getsource(designer_mod)
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
                    f"experiment_designer.py except 块 #{idx + 1} 是 silent pass:\n{block}\n"
                    "防御性自检 [1]: 必须改 logger.warning(..., exc_info=True)"
                )
            if not has_warning and not has_raise:
                pytest.fail(
                    f"experiment_designer.py except 块 #{idx + 1} 无 warning 也无 raise:\n{block}\n"
                    "防御性自检 [1]: 必须有 logger.warning 或显式 raise"
                )


# ──────────────────────────────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
