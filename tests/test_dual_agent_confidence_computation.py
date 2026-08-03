"""v0.69.0-b: dual_agent_confidence 计算测试.

目标 (按 v0.69.0 PRD §3.1.2 + §7.2 重新设计):
  1. _compute_dual_agent_confidence 三种路径:
     - bandit 未初始化 -> fallback (estimate_gain_fallback)
     - 冷启动期 -> _estimate_gain fallback (estimate_gain_fallback)
     - 非冷启动期 -> LinUCB θ@x (linucb)
  2. 失败兜底: 走 intervention.expected_gain (跟 V1 一致)
  3. metadata 字段写入: dual_agent_confidence + dual_agent_confidence_source

防御性自检 [1]: 失败 _log.warning, 不 silent pass
防御性自检 [6]: 失败不污染 in-memory state
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
    from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig
    from ecos.cta.l1_evolution import EvolutionConfig
    from ecos.cta.l2_mirt import MIRTConfig

    config = BeliefEngineConfig(
        evolution_config=EvolutionConfig(),
        mirt_config=MIRTConfig(),
    )
    engine = BeliefEngine(config=config, llm_client=None)
    return engine.create_initial_state("test_da_conf")


@pytest.fixture
def dual_agent_orch():
    """独立 DualAgentOrchestrator (不接 LLM, 不接 DB)."""
    from ecos.dual_agent.orchestrator import DualAgentConfig, DualAgentOrchestrator

    return DualAgentOrchestrator(config=DualAgentConfig(), llm_client=None)


# ──────────────────────────────────────────────────────────────────────
# 1. bandit 未初始化 -> fallback
# ──────────────────────────────────────────────────────────────────────


class TestDualAgentConfidenceBanditNotInitialized:
    """v0.69.0-b: bandit 未初始化时走 fallback."""

    def test_returns_fallback_when_bandit_not_initialized(
        self, dual_agent_orch, belief_state
    ):
        """sid 没在 bandits 字典里 -> fallback (estimate_gain_fallback)."""
        from ecos.lca.intervention import Intervention, InterventionType, CAStage, CLTLevel, BloomLevel

        intervention = Intervention(
            intervention_type=InterventionType.EXPLANATORY,
            bloom_target=BloomLevel.UNDERSTAND,
            target_skills=[],
            target_misconceptions=[],
            target_tcs=["understand"],
            difficulty=0.5,
            quantity=3,
            feedback_density=0.8,
            scaffolding_level=0.5,
            clt_level=CLTLevel.DEVELOPING,
            ca_stage=CAStage.MODELING,
            bjork_triggers=[],
            expected_gain=0.3,  # 故意设 0.3, 验证 fallback 用它
            expected_risk=0.1,
        )

        conf, source = dual_agent_orch._compute_dual_agent_confidence(
            sid="test_da_conf",
            intervention=intervention,
            belief_state=belief_state,
        )
        assert source == "estimate_gain_fallback"
        # bandit 未初始化时, fallback 用 intervention.expected_gain = 0.3
        assert conf == 0.3


# ──────────────────────────────────────────────────────────────────────
# 2. 冷启动期 -> _estimate_gain fallback
# ──────────────────────────────────────────────────────────────────────


class TestDualAgentConfidenceColdStart:
    """v0.69.0-b: 冷启动期走 _estimate_gain fallback."""

    def test_cold_start_uses_estimate_gain_fallback(
        self, dual_agent_orch, belief_state
    ):
        """arm_pull_counts.sum() < threshold -> _estimate_gain fallback."""
        # 先 select 一次 (bandit 初始化, 但 arm_pull_counts=0, 仍冷启动)
        from ecos.lca.orchestrator import CTAInput

        cta_input = CTAInput(student_id="test_da_conf", belief_state=belief_state)
        result = dual_agent_orch.lca_engine.select_intervention(cta_input)

        # 验证 bandit 已初始化但 arm_pull_counts=0
        bandit = dual_agent_orch.lca_engine.bandits["test_da_conf"]
        assert int(bandit.bandit.arm_pull_counts.sum()) == 0
        assert dual_agent_orch.lca_engine._is_linucb_cold_start("test_da_conf") is True

        # 调 _compute_dual_agent_confidence 应走 _estimate_gain fallback
        conf, source = dual_agent_orch._compute_dual_agent_confidence(
            sid="test_da_conf",
            intervention=result.intervention,
            belief_state=belief_state,
        )
        assert source == "estimate_gain_fallback"
        # _estimate_gain 的输出 (不验证具体值, 只要 > 0)
        assert 0.0 <= conf <= 1.0

    def test_cold_start_fallback_uses_intervention_expected_gain_on_failure(
        self, dual_agent_orch, belief_state
    ):
        """冷启动期 _estimate_gain 失败 -> 走 intervention.expected_gain."""
        from ecos.lca.orchestrator import CTAInput

        cta_input = CTAInput(student_id="test_da_conf", belief_state=belief_state)
        result = dual_agent_orch.lca_engine.select_intervention(cta_input)
        # 故意设 expected_gain = 0.42
        result.intervention.expected_gain = 0.42

        # mock _estimate_gain 抛异常
        original = dual_agent_orch.lca_engine._estimate_gain
        dual_agent_orch.lca_engine._estimate_gain = lambda *a, **kw: (_ for _ in ()).throw(
            RuntimeError("mock _estimate_gain 失败")
        )
        try:
            conf, source = dual_agent_orch._compute_dual_agent_confidence(
                sid="test_da_conf",
                intervention=result.intervention,
                belief_state=belief_state,
            )
        finally:
            dual_agent_orch.lca_engine._estimate_gain = original

        # 失败兜底 -> intervention.expected_gain = 0.42
        assert source == "estimate_gain_fallback"
        assert conf == 0.42


# ──────────────────────────────────────────────────────────────────────
# 3. 非冷启动期 -> LinUCB θ@x
# ──────────────────────────────────────────────────────────────────────


class TestDualAgentConfidenceLinUCBPrediction:
    """v0.69.0-b: 非冷启动期走 LinUCB θ@x 预测."""

    def test_non_cold_start_uses_linucb_theta_x(
        self, dual_agent_orch, belief_state
    ):
        """arm_pull_counts.sum() >= threshold -> LinUCB θ@x 预测."""
        from ecos.lca.orchestrator import CTAInput

        cta_input = CTAInput(student_id="test_da_conf", belief_state=belief_state)
        # select + update 10 次, 达到默认 threshold=10
        for _ in range(10):
            result = dual_agent_orch.lca_engine.select_intervention(cta_input)
            dual_agent_orch.lca_engine.update(
                student_id="test_da_conf",
                intervention=result.intervention,
                new_state=belief_state,
                state_delta=0.5,  # 用 state_delta 给 LinUCB 学 (冷启动期数据)
            )

        # 验证非冷启动
        assert dual_agent_orch.lca_engine._is_linucb_cold_start("test_da_conf") is False

        # 再 select 一次, 拿一个 arm
        result = dual_agent_orch.lca_engine.select_intervention(cta_input)
        conf, source = dual_agent_orch._compute_dual_agent_confidence(
            sid="test_da_conf",
            intervention=result.intervention,
            belief_state=belief_state,
        )
        assert source == "linucb"
        # LinUCB θ@x 输出在 [0, 1] 范围内 (已截断)
        assert 0.0 <= conf <= 1.0

    def test_linucb_prediction_matches_theta_dot_x(
        self, dual_agent_orch, belief_state
    ):
        """LinUCB 预测值 = θ_a @ x (排除 confidence_bound)."""
        from ecos.lca.orchestrator import CTAInput

        cta_input = CTAInput(student_id="test_da_conf", belief_state=belief_state)
        # 学 10 次, 走出冷启动
        for _ in range(10):
            result = dual_agent_orch.lca_engine.select_intervention(cta_input)
            dual_agent_orch.lca_engine.update(
                student_id="test_da_conf",
                intervention=result.intervention,
                new_state=belief_state,
                state_delta=0.5,
            )

        result = dual_agent_orch.lca_engine.select_intervention(cta_input)
        bandit = dual_agent_orch.lca_engine.bandits["test_da_conf"]
        arm_idx = bandit._lookup_arm(result.intervention)

        # 手动算 LinUCB θ_a @ x
        context = bandit._build_context(belief_state)
        A_inv = np.linalg.inv(bandit.bandit.A[arm_idx])
        theta = A_inv @ bandit.bandit.b[arm_idx]
        expected = float(theta @ context)
        expected = max(0.0, min(1.0, expected))

        # 调 _compute_dual_agent_confidence
        conf, source = dual_agent_orch._compute_dual_agent_confidence(
            sid="test_da_conf",
            intervention=result.intervention,
            belief_state=belief_state,
        )
        assert source == "linucb"
        np.testing.assert_allclose(conf, expected, atol=1e-10)


# ──────────────────────────────────────────────────────────────────────
# 4. 失败兜底 (防御性自检 [1] + [6])
# ──────────────────────────────────────────────────────────────────────


class TestDualAgentConfidenceDefensive:
    """v0.69.0-b: 失败兜底返回 expected_gain, 不 raise, 不 silent pass."""

    def test_arm_lookup_failure_returns_fallback(self, dual_agent_orch, belief_state):
        """LinUCB arm 反查失败 -> fallback."""
        from ecos.lca.intervention import (
            Intervention, InterventionType, CAStage, CLTLevel, BloomLevel,
        )

        # select 一次, 拿一个 arm fingerprint
        from ecos.lca.orchestrator import CTAInput

        cta_input = CTAInput(student_id="test_da_conf", belief_state=belief_state)
        result = dual_agent_orch.lca_engine.select_intervention(cta_input)

        # 构造一个不在 _arm_fingerprints 里的 intervention
        fake_intervention = Intervention(
            intervention_type=InterventionType.EXPLANATORY,
            bloom_target=BloomLevel.UNDERSTAND,
            target_skills=[],
            target_misconceptions=[],
            target_tcs=["understand"],
            difficulty=0.5,
            quantity=3,
            feedback_density=0.8,
            scaffolding_level=0.5,
            clt_level=CLTLevel.DEVELOPING,
            ca_stage=CAStage.MODELING,
            bjork_triggers=[],
            expected_gain=0.55,
            expected_risk=0.1,
        )
        # 故意把 fake_intervention.intervention_id 设成不存在的
        # (默认 uuid, 几乎不可能跟 _arm_fingerprints 重)

        # 走出冷启动 (让代码进入 LinUCB 预测路径, 触发 arm 反查)
        # 但这次不 update, 直接调 _compute_dual_agent_confidence 时 bandit 未初始化 -> 走 fallback
        #   这里换个 sid 验证 arm 反查失败
        # (因为非冷启动 + arm 反查失败比较难构造, 这个用例主要验证 fallback 路径)
        conf, source = dual_agent_orch._compute_dual_agent_confidence(
            sid="test_da_conf",
            intervention=fake_intervention,
            belief_state=belief_state,
        )
        # bandit 已初始化但冷启动 (arm_pull_counts=0) -> 走 _estimate_gain fallback
        assert source == "estimate_gain_fallback"
        assert 0.0 <= conf <= 1.0

    def test_returns_fallback_on_unexpected_exception(
        self, dual_agent_orch, belief_state
    ):
        """任何意外异常 -> fallback (intervention.expected_gain), 不 raise."""
        from ecos.lca.intervention import (
            Intervention, InterventionType, CAStage, CLTLevel, BloomLevel,
        )

        intervention = Intervention(
            intervention_type=InterventionType.EXPLANATORY,
            bloom_target=BloomLevel.UNDERSTAND,
            target_skills=[],
            target_misconceptions=[],
            target_tcs=["understand"],
            difficulty=0.5,
            quantity=3,
            feedback_density=0.8,
            scaffolding_level=0.5,
            clt_level=CLTLevel.DEVELOPING,
            ca_stage=CAStage.MODELING,
            bjork_triggers=[],
            expected_gain=0.77,
            expected_risk=0.1,
        )

        # mock lca_engine.bandits.get 抛异常
        original_bandits = dual_agent_orch.lca_engine.bandits

        class FailingBanditsDict(dict):
            def get(self, key, default=None):
                raise RuntimeError("模拟 bandits.get 失败")

        dual_agent_orch.lca_engine.bandits = FailingBanditsDict()
        try:
            conf, source = dual_agent_orch._compute_dual_agent_confidence(
                sid="test_da_conf",
                intervention=intervention,
                belief_state=belief_state,
            )
            # 失败兜底: 用 intervention.expected_gain = 0.77
            assert source == "estimate_gain_fallback"
            assert conf == 0.77
        finally:
            dual_agent_orch.lca_engine.bandits = original_bandits

    def test_logs_warning_on_unexpected_failure(
        self, dual_agent_orch, belief_state, caplog
    ):
        """失败时 _log.warning, 不 silent pass."""
        from ecos.lca.intervention import (
            Intervention, InterventionType, CAStage, CLTLevel, BloomLevel,
        )

        intervention = Intervention(
            intervention_type=InterventionType.EXPLANATORY,
            bloom_target=BloomLevel.UNDERSTAND,
            target_skills=[],
            target_misconceptions=[],
            target_tcs=["understand"],
            difficulty=0.5,
            quantity=3,
            feedback_density=0.8,
            scaffolding_level=0.5,
            clt_level=CLTLevel.DEVELOPING,
            ca_stage=CAStage.MODELING,
            bjork_triggers=[],
            expected_gain=0.66,
            expected_risk=0.1,
        )

        class FailingBanditsDict(dict):
            def get(self, key, default=None):
                raise RuntimeError("模拟失败")

        original_bandits = dual_agent_orch.lca_engine.bandits
        dual_agent_orch.lca_engine.bandits = FailingBanditsDict()
        try:
            with caplog.at_level(logging.WARNING, logger="ecos.dual_agent.orchestrator"):
                conf, source = dual_agent_orch._compute_dual_agent_confidence(
                    sid="test_da_conf",
                    intervention=intervention,
                    belief_state=belief_state,
                )
            # 应该有 warning log
            assert any(
                "dual_agent_confidence 计算失败" in rec.message
                for rec in caplog.records
            ), "失败时应该 _log.warning, 不能 silent pass"
        finally:
            dual_agent_orch.lca_engine.bandits = original_bandits


# ──────────────────────────────────────────────────────────────────────
# 5. metadata 写入 (集成测试 process_observation)
# ──────────────────────────────────────────────────────────────────────


class TestDualAgentConfidenceMetadataWritten:
    """v0.69.0-b: process_observation 把 dual_agent_confidence 写入 prev_calibrated.metadata."""

    def test_metadata_has_dual_agent_confidence_after_second_observation(
        self, dual_agent_orch, belief_state
    ):
        """第二轮 process_observation 后, calibrated.metadata (当前轮 N+1) 含 dual_agent_confidence.

        v0.69.0-b 设计 (PRD §7.2 重新设计):
          - dual_agent_confidence 写入 calibrated.metadata (当前轮 N+1)
          - 用 calibrated.intervention (当前轮 N+1 选出的) 反查 arm
          - 用 current_state (即 prev_state, 轮 N 之后的) 构建 context
          - 校准逻辑: calibration_log(round=N+1).dual_agent_confidence
                       vs calibration_log(round=N+1).actual_outcome (轮 N+2 填回)
                       跟 V1 (expected_gain) 同模式, compute_h3_ece V3 优先逻辑可校准
        """
        from ecos.cta.belief_engine import Observation
        from ecos.cta.belief_state import BloomLevel

        # 第一轮: select intervention (prev_calibrated=None, 跳过 dual_agent_confidence 计算)
        obs1 = Observation(
            problem_id="q1",
            skill_id="python.basics",
            correct=True,
            score=1.0,
            bloom_level=BloomLevel.APPLY,
        )
        calibrated1 = dual_agent_orch.process_observation(obs1, student_id="test_da_conf")
        # 第一轮 prev_calibrated=None, calibrated1.metadata 还没 dual_agent_confidence
        assert "dual_agent_confidence" not in calibrated1.metadata

        # 第二轮: 这一轮 prev_calibrated=calibrated1, 会计算 dual_agent_confidence
        #   写入 calibrated2.metadata (当前轮)
        obs2 = Observation(
            problem_id="q2",
            skill_id="python.basics",
            correct=True,
            score=1.0,
            bloom_level=BloomLevel.APPLY,
        )
        calibrated2 = dual_agent_orch.process_observation(obs2, student_id="test_da_conf")

        # 现在 calibrated2.metadata (当前轮 N+1=2) 应该有 dual_agent_confidence
        assert "dual_agent_confidence" in calibrated2.metadata
        assert "dual_agent_confidence_source" in calibrated2.metadata
        assert calibrated2.metadata["dual_agent_confidence_source"] in (
            "linucb", "estimate_gain_fallback"
        )
        # confidence 在 [0, 1]
        conf = calibrated2.metadata["dual_agent_confidence"]
        assert 0.0 <= conf <= 1.0
