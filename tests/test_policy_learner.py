"""v0.82.0-d: LCA PolicyLearner 策略学习层测试套件.

目标 (按 v0.82.0-d Definition of Done):
  - PolicyLearner 独立可构造, 持有 per-student LCAPolicyLearner (lazy init)
  - select(student_id, state, candidates) -> Intervention 委托 LCAPolicyLearner
  - update(student_id, intervention, new_state, reward) -> None 委托 LCAPolicyLearner
  - is_cold_start(student_id) -> bool 冷启动判定 (dual_agent_confidence 路径)
  - dump(student_id) -> dict 4 字段 + 2 内部
  - load(student_id, snapshot) -> None 含维度校验
  - LCAEngine._is_linucb_cold_start / _get_bandit / select / update 委托
  - LCAEngine.dump_state / load_state 7 字段全恢复 (含 PolicyLearner 部分)
  - self.bandits = self.policy_learner._learners (shared reference, backward compat)
  - LCAEngineConfig.policy_learner_config = None 时从 bandit_config 派生 cold_start_threshold
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest
import numpy as np


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
    return engine.create_initial_state("test_policy_student")


@pytest.fixture
def cta_input(belief_state):
    """构造 CTAInput."""
    from ecos.lca.cta_input import CTAInput

    return CTAInput(
        student_id="test_policy_student",
        belief_state=belief_state,
    )


# ──────────────────────────────────────────────────────────────────────
# 1. PolicyLearner 构造 + per-student 隔离 (3 tests)
# ──────────────────────────────────────────────────────────────────────


class TestPolicyLearnerConstruction:
    """v0.82.0-d: PolicyLearner 构造 + per-student 隔离."""

    def test_default_construction(self):
        """默认 config 构造 PolicyLearner, cold_start_threshold=10."""
        from ecos.lca.policy_learner import PolicyLearner, PolicyLearnerConfig

        pl = PolicyLearner()
        assert isinstance(pl.config, PolicyLearnerConfig)
        assert pl.config.cold_start_threshold == 10
        # per-student dict 初始为空
        assert pl._learners == {}

    def test_per_student_lazy_init(self):
        """_get_learner 触发 lazy init, 两个学生独立 LCAPolicyLearner."""
        from ecos.lca.policy_learner import PolicyLearner

        pl = PolicyLearner()
        learner_a = pl._get_learner("student_a")
        learner_b = pl._get_learner("student_b")
        # 两个学生独立实例
        assert learner_a is not learner_b
        # 都在 _learners dict 中
        assert "student_a" in pl._learners
        assert "student_b" in pl._learners
        assert pl._learners["student_a"] is learner_a
        assert pl._learners["student_b"] is learner_b

    def test_get_learner_returns_same_instance(self):
        """_get_learner 重复调用返回同一实例 (单例 per-student)."""
        from ecos.lca.policy_learner import PolicyLearner

        pl = PolicyLearner()
        learner1 = pl._get_learner("student_a")
        learner2 = pl._get_learner("student_a")
        assert learner1 is learner2


# ──────────────────────────────────────────────────────────────────────
# 2. select / update 委托 (2 tests)
# ──────────────────────────────────────────────────────────────────────


class TestPolicyLearnerSelectUpdate:
    """v0.82.0-d: select / update 委托 LCAPolicyLearner."""

    def test_select_uses_lcpolicy_learner(self, belief_state):
        """select() 委托 LCAPolicyLearner.select_intervention."""
        from ecos.lca.policy_learner import PolicyLearner
        from ecos.lca.experiment_designer import ExperimentDesigner
        from ecos.lca.planner import PlanDecision
        from ecos.lca.intervention import CAStage, CLTLevel
        from ecos.cta.belief_state import BloomLevel

        pl = PolicyLearner()
        designer = ExperimentDesigner()
        plan = PlanDecision(
            bloom_target=BloomLevel.APPLY,
            ca_stage=CAStage.COACHING,
            clt_level=CLTLevel.DEVELOPING,
            bjork_triggers=[],
        )
        from ecos.lca.cta_input import CTAInput
        cta_input = CTAInput(
            student_id="test_select",
            belief_state=belief_state,
        )
        candidates = designer.design(plan, cta_input, n_candidates=10)
        chosen = pl.select("test_select", belief_state, candidates)
        assert chosen is not None
        # bandit 已初始化
        assert "test_select" in pl._learners

    def test_update_increments_arm_pull_count(self, belief_state):
        """update() 委托 LCAPolicyLearner.update, arm_pull_counts 应增加.

        注意: LCAPolicyLearner.update 通过 last_arm 反查 arm, 必须先 select
              否则 _lookup_arm 返回 None, update silently 跳过 (v0.75.3 H3-c3 设计).
        """
        from ecos.lca.policy_learner import PolicyLearner
        from ecos.lca.experiment_designer import ExperimentDesigner
        from ecos.lca.planner import PlanDecision
        from ecos.lca.intervention import CAStage, CLTLevel
        from ecos.cta.belief_state import BloomLevel
        from ecos.lca.cta_input import CTAInput

        pl = PolicyLearner()
        designer = ExperimentDesigner()
        plan = PlanDecision(
            bloom_target=BloomLevel.APPLY,
            ca_stage=CAStage.COACHING,
            clt_level=CLTLevel.DEVELOPING,
            bjork_triggers=[],
        )
        cta_input = CTAInput(
            student_id="test_update",
            belief_state=belief_state,
        )
        # 先 select 一次 (让 last_arm + _arm_fingerprints 有值)
        candidates = designer.design(plan, cta_input, n_candidates=10)
        chosen = pl.select("test_update", belief_state, candidates)

        pl.update("test_update", chosen, belief_state, reward=0.5)

        learner = pl._learners["test_update"]
        # arm_pull_counts 至少有一个 > 0
        assert learner.bandit.arm_pull_counts.sum() >= 1


# ──────────────────────────────────────────────────────────────────────
# 3. is_cold_start 边界 (3 tests)
# ──────────────────────────────────────────────────────────────────────


class TestPolicyLearnerColdStart:
    """v0.82.0-d: is_cold_start 冷启动判定 (dual_agent_confidence 来源切换)."""

    def test_new_student_is_cold_start(self):
        """新学生 (learner 未初始化) -> 冷启动."""
        from ecos.lca.policy_learner import PolicyLearner

        pl = PolicyLearner()
        assert pl.is_cold_start("never_seen_student") is True

    def test_warm_student_not_cold_start(self):
        """非冷启动期 (arm_pull_counts.sum() >= threshold) -> False."""
        from ecos.lca.policy_learner import PolicyLearner, PolicyLearnerConfig

        pl = PolicyLearner(PolicyLearnerConfig(cold_start_threshold=3))
        # 初始化 learner 并把 arm_pull_counts[0] 设为 5 (超过 threshold=3)
        learner = pl._get_learner("warm_student")
        learner.bandit.arm_pull_counts[0] = 5
        assert pl.is_cold_start("warm_student") is False

    def test_failure_returns_true(self, caplog):
        """异常时 (e.g. _learners.get 失败) 兜底返回 True + warning log."""
        from ecos.lca.policy_learner import PolicyLearner
        import logging

        pl = PolicyLearner()

        class FailingDict(dict):
            def get(self, key, default=None):
                raise RuntimeError("模拟失败")

        original = pl._learners
        try:
            object.__setattr__(pl, "_learners", FailingDict())
            with caplog.at_level(logging.WARNING, logger="ecos.lca.policy_learner"):
                result = pl.is_cold_start("any_student")
            assert result is True
            assert any(
                "LinUCB 冷启动判定失败" in rec.message
                for rec in caplog.records
            )
        finally:
            object.__setattr__(pl, "_learners", original)


# ──────────────────────────────────────────────────────────────────────
# 4. dump / load 持久化 (3 tests)
# ──────────────────────────────────────────────────────────────────────


class TestPolicyLearnerPersistence:
    """v0.82.0-d: dump / load LinUCB 状态 (4 字段 + 2 内部)."""

    def test_dump_load_roundtrip(self):
        """dump -> load round-trip, 4 字段 + 2 内部全恢复."""
        from ecos.lca.policy_learner import PolicyLearner

        pl = PolicyLearner()
        # 初始化 learner + 模拟 arm_pull_counts
        learner = pl._get_learner("test_persistence")
        learner.bandit.arm_pull_counts[0] = 3
        learner.bandit.arm_pull_counts[1] = 2
        learner._arm_fingerprints[0] = "iv_001"
        learner._arm_fingerprints[1] = "iv_002"
        learner._last_arm = 1

        # dump
        snap = pl.dump("test_persistence")
        assert "bandit_a" in snap
        assert "bandit_b" in snap
        assert "arm_pull_counts" in snap
        assert "arm_fingerprints" in snap
        assert "last_arm" in snap
        assert snap["arm_pull_counts"][0] == 3
        assert snap["arm_pull_counts"][1] == 2
        assert snap["arm_fingerprints"]["0"] == "iv_001"
        assert snap["last_arm"] == 1

        # 改原状态, load 恢复
        learner.bandit.arm_pull_counts[0] = 0
        learner._last_arm = -1
        pl.load("test_persistence", snap)
        assert pl._learners["test_persistence"].bandit.arm_pull_counts[0] == 3
        assert pl._learners["test_persistence"].bandit.arm_pull_counts[1] == 2
        assert pl._learners["test_persistence"]._last_arm == 1

    def test_load_dimension_mismatch_raises(self):
        """load 时维度不匹配 -> raise ValueError (防御性自检 [5])."""
        from ecos.lca.policy_learner import PolicyLearner

        pl = PolicyLearner()
        # 正常 load 空 snapshot 应该 ok
        pl.load("test_dim", {})
        # 然后 load 一个错的 bandit_a (维度不对)
        wrong_snap = {
            "bandit_a": [[[1.0] * 5 for _ in range(5)] for _ in range(10)],
            "bandit_b": [[1.0] * 5 for _ in range(10)],
            "arm_pull_counts": [0] * 10,
        }
        with pytest.raises(ValueError, match="维度不匹配"):
            pl.load("test_dim", wrong_snap)

    def test_load_empty_snapshot_keeps_default(self):
        """load 空 snapshot (新学生) -> 保持默认 A=I, b=0 (LinUCB 冷启动)."""
        from ecos.lca.policy_learner import PolicyLearner

        pl = PolicyLearner()
        pl.load("test_new_student", {})
        learner = pl._learners["test_new_student"]
        # 默认 A 是 I, b 是 0
        # 简单验证: arm_pull_counts 全 0
        assert learner.bandit.arm_pull_counts.sum() == 0


# ──────────────────────────────────────────────────────────────────────
# 5. LCAEngine 集成 (4 tests)
# ──────────────────────────────────────────────────────────────────────


class TestLCAEnginePolicyLearnerIntegration:
    """v0.82.0-d: LCAEngine _is_linucb_cold_start / _get_bandit / select / update 委托."""

    def test_lca_engine_bandits_is_policy_learner_dict(self):
        """LCAEngine.bandits 引用 = LCAEngine.policy_learner._learners (shared)."""
        from ecos.lca import LCAEngine

        engine = LCAEngine()
        assert engine.bandits is engine.policy_learner._learners, \
            "engine.bandits 应 == engine.policy_learner._learners (shared reference)"

    def test_lca_engine_select_delegates_to_policy_learner(self, cta_input):
        """LCAEngine.select_intervention step 5 委托 self.policy_learner.select()."""
        from ecos.lca import LCAEngine

        engine = LCAEngine()
        with patch.object(
            engine.policy_learner, "select",
            wraps=engine.policy_learner.select,
        ) as spy_select:
            engine.select_intervention(cta_input)
        assert spy_select.call_count == 1

    def test_lca_engine_update_delegates_to_policy_learner(self, belief_state):
        """LCAEngine.update() 委托 self.policy_learner.update()."""
        from ecos.lca import LCAEngine
        from ecos.lca.cta_input import CTAInput
        from ecos.lca.intervention import Intervention, InterventionType, CAStage, CLTLevel
        from ecos.cta.belief_state import BloomLevel

        engine = LCAEngine()
        cta_input = CTAInput(
            student_id="test_engine_update",
            belief_state=belief_state,
        )
        # 先 select 一次 (让 policy_learner._learners 有 entry)
        engine.select_intervention(cta_input)
        intervention = Intervention(
            intervention_type=InterventionType.PRACTICE,
            bloom_target=BloomLevel.APPLY,
            clt_level=CLTLevel.DEVELOPING,
            ca_stage=CAStage.COACHING,
        )
        with patch.object(
            engine.policy_learner, "update",
            wraps=engine.policy_learner.update,
        ) as spy_update:
            engine.update(
                student_id="test_engine_update",
                intervention=intervention,
                new_state=belief_state,
                state_delta=0.3,
            )
        assert spy_update.call_count == 1

    def test_lca_engine_config_propagates_cold_start_threshold(self):
        """LCAEngineConfig.policy_learner_config=None 时从 bandit_config 派生."""
        from ecos.lca import LCAEngine, LCAEngineConfig
        from ecos.lca.l4_optimization import BanditConfig

        # 用户只设 bandit_config.cold_start_threshold=5
        cfg = LCAEngineConfig(
            bandit_config=BanditConfig(cold_start_threshold=5),
        )
        engine = LCAEngine(config=cfg)
        # policy_learner.config.cold_start_threshold 应 = 5 (派生)
        assert engine.policy_learner.config.cold_start_threshold == 5, \
            f"派生 cold_start_threshold 应=5, 实际={engine.policy_learner.config.cold_start_threshold}"


# ──────────────────────────────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
