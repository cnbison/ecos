"""v0.69.0-a: LinUCB 冷启动判定测试.

目标 (按 v0.69.0 PRD §7.1 Definition of Done):
  1. BanditConfig 加 cold_start_threshold 字段 (默认 10)
  2. LCAEngine._is_linucb_cold_start(sid) 判定逻辑:
     - bandit 未初始化 -> True (冷启动)
     - arm_pull_counts.sum() < threshold -> True (冷启动)
     - arm_pull_counts.sum() >= threshold -> False (非冷启动)
  3. cold_start_threshold 可配置 (改 BanditConfig)
  4. 防御性自检 [1]: 失败兜底返回 True (保守, 走 fallback)

测试策略:
  - 直接用 LCAEngine + BeliefState (不经 web.api.lca, 隔离单元测试)
  - 模拟 bandit 拉 N 次, 验证 threshold 边界
"""

from __future__ import annotations

import logging
from unittest.mock import patch

import numpy as np
import pytest


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def belief_state():
    """构造一个最小 BeliefState."""
    from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig
    from ecos.cta.l1_evolution import EvolutionConfig
    from ecos.cta.l2_mirt import MIRTConfig

    config = BeliefEngineConfig(
        evolution_config=EvolutionConfig(),
        mirt_config=MIRTConfig(),
    )
    engine = BeliefEngine(config=config, llm_client=None)
    return engine.create_initial_state("test_cold_start")


@pytest.fixture
def lca_engine():
    """构造一个独立 LCAEngine (默认 BanditConfig)."""
    from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig

    return LCAEngine(config=LCAEngineConfig(), llm_client=None)


# ──────────────────────────────────────────────────────────────────────
# 1. BanditConfig.cold_start_threshold 字段
# ──────────────────────────────────────────────────────────────────────


class TestBanditConfigColdStartThreshold:
    """v0.69.0-a: BanditConfig 加 cold_start_threshold 字段."""

    def test_default_cold_start_threshold_is_10(self):
        """默认 cold_start_threshold = 10 (10 个 arm 各拉 1 次)."""
        from ecos.lca.l4_optimization.linucb import BanditConfig

        config = BanditConfig()
        assert config.cold_start_threshold == 10

    def test_cold_start_threshold_configurable(self):
        """cold_start_threshold 可配置."""
        from ecos.lca.l4_optimization.linucb import BanditConfig

        config = BanditConfig(cold_start_threshold=5)
        assert config.cold_start_threshold == 5

        config = BanditConfig(cold_start_threshold=20)
        assert config.cold_start_threshold == 20

    def test_other_bandit_config_fields_unchanged(self):
        """v0.69.0 改动不影响其他 BanditConfig 字段."""
        from ecos.lca.l4_optimization.linucb import BanditConfig

        config = BanditConfig()
        assert config.n_arms == 10
        assert config.context_dim == 16
        assert config.alpha == 1.0
        assert config.min_reward == 0.0
        assert config.max_reward == 1.0


# ──────────────────────────────────────────────────────────────────────
# 2. LCAEngine._is_linucb_cold_start 判定
# ──────────────────────────────────────────────────────────────────────


class TestLinUCBColdStartDetection:
    """v0.69.0-a: LCAEngine._is_linucb_cold_start 判定逻辑."""

    def test_cold_start_when_bandit_not_initialized(self, lca_engine):
        """bandit 未初始化 (学生首次) -> True (冷启动)."""
        # student_id 不在 self.bandits 字典里
        assert "test_cold_start" not in lca_engine.bandits
        assert lca_engine._is_linucb_cold_start("test_cold_start") is True

    def test_cold_start_when_zero_arm_pulls(self, lca_engine, belief_state):
        """bandit 刚初始化 (0 次 arm pull) -> True (冷启动)."""
        from ecos.lca.orchestrator import CTAInput

        # 触发 _get_bandit 初始化 (调一次 select_intervention)
        cta_input = CTAInput(
            student_id="test_cold_start",
            belief_state=belief_state,
        )
        lca_engine.select_intervention(cta_input)

        # select 后, arm_pull_counts 仍为 0 (因为没 update)
        bandit = lca_engine.bandits["test_cold_start"]
        assert int(bandit.bandit.arm_pull_counts.sum()) == 0
        assert lca_engine._is_linucb_cold_start("test_cold_start") is True

    def test_not_cold_start_when_pulls_reach_threshold(self, lca_engine, belief_state):
        """arm_pull_counts.sum() == threshold -> False (非冷启动)."""
        from ecos.lca.orchestrator import CTAInput

        cta_input = CTAInput(
            student_id="test_cold_start",
            belief_state=belief_state,
        )
        # select + update 10 次, 达到默认 threshold=10
        for _ in range(10):
            result = lca_engine.select_intervention(cta_input)
            lca_engine.update(
                student_id="test_cold_start",
                intervention=result.intervention,
                new_state=belief_state,
                state_delta=0.5,
            )

        bandit = lca_engine.bandits["test_cold_start"]
        assert int(bandit.bandit.arm_pull_counts.sum()) == 10
        assert lca_engine._is_linucb_cold_start("test_cold_start") is False

    def test_cold_start_boundary_threshold_minus_1(self, lca_engine, belief_state):
        """arm_pull_counts.sum() == threshold - 1 -> True (边界, 仍冷启动)."""
        from ecos.lca.orchestrator import CTAInput

        cta_input = CTAInput(
            student_id="test_cold_start",
            belief_state=belief_state,
        )
        # select + update 9 次, threshold=10, 9 < 10 -> 仍冷启动
        for _ in range(9):
            result = lca_engine.select_intervention(cta_input)
            lca_engine.update(
                student_id="test_cold_start",
                intervention=result.intervention,
                new_state=belief_state,
                state_delta=0.5,
            )

        bandit = lca_engine.bandits["test_cold_start"]
        assert int(bandit.bandit.arm_pull_counts.sum()) == 9
        assert lca_engine._is_linucb_cold_start("test_cold_start") is True

    def test_cold_start_threshold_configurable(self, belief_state):
        """改 BanditConfig.cold_start_threshold = 5, 5 次 update 后非冷启动."""
        from ecos.lca.l4_optimization.linucb import BanditConfig
        from ecos.lca.orchestrator import CTAInput, LCAEngine, LCAEngineConfig

        config = LCAEngineConfig(
            bandit_config=BanditConfig(cold_start_threshold=5),
        )
        engine = LCAEngine(config=config, llm_client=None)

        cta_input = CTAInput(
            student_id="test_cold_start_threshold_5",
            belief_state=belief_state,
        )
        # 4 次 update: 4 < 5 -> 仍冷启动
        for _ in range(4):
            result = engine.select_intervention(cta_input)
            engine.update(
                student_id="test_cold_start_threshold_5",
                intervention=result.intervention,
                new_state=belief_state,
                state_delta=0.5,
            )
        assert engine._is_linucb_cold_start("test_cold_start_threshold_5") is True

        # 第 5 次 update: 5 == 5 -> 非冷启动
        result = engine.select_intervention(cta_input)
        engine.update(
            student_id="test_cold_start_threshold_5",
            intervention=result.intervention,
            new_state=belief_state,
            state_delta=0.5,
        )
        assert engine._is_linucb_cold_start("test_cold_start_threshold_5") is False


# ──────────────────────────────────────────────────────────────────────
# 3. 防御性自检 [1]: 失败兜底返回 True
# ──────────────────────────────────────────────────────────────────────


class TestLinUCBColdStartDefensive:
    """v0.69.0-a: 防御性自检 [1], 失败兜底返回 True (保守, 走 fallback)."""

    def test_returns_true_when_bandit_lookup_fails(self, lca_engine):
        """learners 字典读失败 -> 兜底返回 True (保守).

        v0.82.0-d: 旧测试 path 是 `lca_engine.bandits = FailingDict()` (直接替换 LCAEngine 旧字段).
                   新 path 是 `lca_engine.policy_learner._learners = FailingDict()` (替换 PolicyLearner 内部 dict,
                   因为 _is_linucb_cold_start 现在委托给 policy_learner.is_cold_start, 后者读 self._learners).
        """
        class FailingDict(dict):
            def get(self, key, default=None):
                raise RuntimeError("模拟 learner lookup 失败")

        original = lca_engine.policy_learner._learners
        try:
            object.__setattr__(lca_engine.policy_learner, "_learners", FailingDict())
            # 失败应兜底返回 True, 不应 raise
            assert lca_engine._is_linucb_cold_start("test_cold_start") is True
        finally:
            object.__setattr__(lca_engine.policy_learner, "_learners", original)

    def test_logs_warning_on_failure(self, lca_engine, caplog):
        """失败时 _log.warning, 不 silent pass (防御性自检 [1]).

        v0.82.0-d: 警告从 `ecos.lca.policy_learner` logger 发出 (不是 `ecos.lca.orchestrator`),
                   因为失败发生在 PolicyLearner.is_cold_start (LCA 4-layer 第 4 层).
        """
        class FailingDict(dict):
            def get(self, key, default=None):
                raise RuntimeError("模拟失败")

        original = lca_engine.policy_learner._learners
        try:
            object.__setattr__(lca_engine.policy_learner, "_learners", FailingDict())
            with caplog.at_level(logging.WARNING, logger="ecos.lca.policy_learner"):
                result = lca_engine._is_linucb_cold_start("test_cold_start")
            assert result is True
            # 应该有 warning log (来自 PolicyLearner.is_cold_start)
            assert any(
                "LinUCB 冷启动判定失败" in rec.message
                for rec in caplog.records
            ), "失败时应该 _log.warning, 不能 silent pass"
        finally:
            object.__setattr__(lca_engine.policy_learner, "_learners", original)


# ──────────────────────────────────────────────────────────────────────
# 4. 教学 LCA 路径不影响 (v0.62.0-A 隔离决策)
# ──────────────────────────────────────────────────────────────────────


class TestTeachingLCANotAffected:
    """v0.69.0-a: 教学 LCA 路径 (web/api/lca.py) 不动, 仅 dual_agent 路径改.

    注: v0.69.0-a 只加了 _is_linucb_cold_start 方法, 没改 select_intervention.
        教学 LCA 调 select_intervention 时不会触发 _is_linucb_cold_start (方法只被
        dual_agent orchestrator 在 v0.69.0-b 调用).
    """

    def test_cold_start_method_does_not_affect_select_intervention(
        self, lca_engine, belief_state
    ):
        """select_intervention 不调 _is_linucb_cold_start, 不受影响."""
        from ecos.lca.orchestrator import CTAInput

        cta_input = CTAInput(
            student_id="test_select_isolated",
            belief_state=belief_state,
        )
        # select_intervention 应该正常工作, 不依赖 _is_linucb_cold_start
        result = lca_engine.select_intervention(cta_input)
        assert result is not None
        assert result.intervention is not None
        # expected_gain 来源仍然是 _estimate_gain (教学 LCA 不变)
        # v0.69.0-b 才会改 dual_agent 路径的 expected_gain 来源
        assert result.expected_gain == result.intervention.expected_gain
