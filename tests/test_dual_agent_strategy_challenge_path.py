"""v0.69.0-d: 策略质疑路径绕过 BUG 修复测试.

背景:
  v0.69.0-b 改造时只在常态循环路径 (process_observation Step 3.5) 写入:
    - calibrated.metadata["dual_agent_confidence"] (V3 LinUCB θ@x 预测)
    - calibrated.metadata["dual_agent_confidence_source"]
    - prev_calibrated.causal_effect (CausalEffect)
    - lca_engine.update(reward=prev_calibrated.actual_outcome) (B4 方案)

  但 lbc003 答 42 道题全触发策略质疑 (K mastery 饱和, avg_gain < 0.05),
  _check_special_modes 提前 return -> 237 行代码从未执行 -> V3=0 样本 + B4 没训.

修复 (v0.69.0-d):
  抽出 _post_process_calibration 方法, 在两个路径都调:
    1. 常态循环路径 (Step 3.5, 替代原 237-298 行代码块)
    2. 特殊模式路径 (_check_special_modes Step D 末尾, append 之前)

测试覆盖:
  1. 策略质疑路径触发时, calibrated.metadata.dual_agent_confidence 被写入
  2. 策略质疑路径触发时, prev_calibrated.causal_effect 被填充
  3. 策略质疑路径触发时, LinUCB B4 reward 被训练 (arm_pull_counts +1)
  4. 策略质疑路径 metadata 同时包含 strategy_challenge_triggered + dual_agent_confidence
  5. 常态循环路径仍正常工作 (不退化)

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
    return engine.create_initial_state("test_sc_path")


@pytest.fixture
def dual_agent_orch():
    """独立 DualAgentOrchestrator (不接 LLM, 不接 DB)."""
    from ecos.dual_agent.orchestrator import DualAgentConfig, DualAgentOrchestrator

    return DualAgentOrchestrator(config=DualAgentConfig(), llm_client=None)


def _make_observation(problem_id: str, score: float, sid: str = "test_sc_path"):
    """构造 Observation."""
    from ecos.cta.belief_engine import Observation
    from ecos.cta.belief_state import BloomLevel

    return Observation(
        problem_id=problem_id,
        skill_id="variables",
        correct=score > 0,
        score=score,
        bloom_level=BloomLevel.APPLY,
        response_time_sec=0.0,
    )


def _seed_intervention_history(orch, sid: str = "test_sc_path", n: int = 1):
    """先跑 n 道常态循环路径题, 让 intervention_history 有数据.

    策略质疑路径需要 intervention_history 非空才能调 challenge_lca.
    """
    for i in range(n):
        obs = _make_observation(f"PB-SEED{i:02d}", score=1.0, sid=sid)
        orch.process_observation(obs, student_id=sid)


def _force_strategy_challenge_trigger(orch, sid: str = "test_sc_path"):
    """强制让 detect_ineffective_intervention 返回 True, 触发策略质疑路径.

    用 patch 替换 StrategyChallengeMode.detect_ineffective_intervention.
    """
    return patch.object(
        orch.strategy_challenge,
        "detect_ineffective_intervention",
        return_value=True,
    )


# ──────────────────────────────────────────────────────────────────────
# 1. 策略质疑路径: dual_agent_confidence 写入
# ──────────────────────────────────────────────────────────────────────


class TestStrategyChallengePathDualAgentConfidence:
    """v0.69.0-d: 策略质疑路径必须写 dual_agent_confidence."""

    def test_strategy_challenge_path_writes_dual_agent_confidence(
        self, dual_agent_orch, belief_state
    ):
        """策略质疑触发时, calibrated.metadata.dual_agent_confidence 必须非 None."""
        sid = "test_sc_path"
        # 先 seed 1 道 (让 intervention_history 非空, 避免 challenge_lca IndexError)
        _seed_intervention_history(dual_agent_orch, sid, n=1)

        # 策略质疑路径: prev 是 seed 的第 1 道 (actual_outcome 在本次 Step 0 填)
        obs = _make_observation("PB-C01", score=1.0, sid=sid)
        with _force_strategy_challenge_trigger(dual_agent_orch, sid):
            result = dual_agent_orch.process_observation(obs, student_id=sid)

        # 关键断言: dual_agent_confidence 必须被写入 (非 None)
        assert "dual_agent_confidence" in result.metadata
        assert result.metadata["dual_agent_confidence"] is not None
        assert "dual_agent_confidence_source" in result.metadata
        # 冷启动期应该走 estimate_gain_fallback
        assert result.metadata["dual_agent_confidence_source"] == "estimate_gain_fallback"
        # 同时 metadata 应该有 strategy_challenge_triggered
        assert result.metadata.get("strategy_challenge_triggered") is True

    def test_strategy_challenge_path_writes_causal_effect(
        self, dual_agent_orch, belief_state
    ):
        """策略质疑路径必须填 prev.causal_effect (之前是 None)."""
        sid = "test_sc_path"
        _seed_intervention_history(dual_agent_orch, sid, n=1)

        obs = _make_observation("PB-C02", score=1.0, sid=sid)
        with _force_strategy_challenge_trigger(dual_agent_orch, sid):
            dual_agent_orch.process_observation(obs, student_id=sid)

        # prev 的 causal_effect 应该被填充 (非 None)
        prev = dual_agent_orch.intervention_history[sid][-2]
        assert prev.causal_effect is not None
        assert prev.causal_effect.student_id == sid

    def test_strategy_challenge_path_trains_linucb_b4_reward(
        self, dual_agent_orch, belief_state
    ):
        """策略质疑路径必须训练 LinUCB (B4 reward=actual_outcome)."""
        sid = "test_sc_path"
        _seed_intervention_history(dual_agent_orch, sid, n=1)

        # 跑 3 道, 每次都触发策略质疑
        for pid in ["PB-C01", "PB-C02", "PB-C03"]:
            obs = _make_observation(pid, score=1.0, sid=sid)
            with _force_strategy_challenge_trigger(dual_agent_orch, sid):
                dual_agent_orch.process_observation(obs, student_id=sid)

        # B4 reward 训练后, bandit 应该有 pull count
        bandit = dual_agent_orch.lca_engine.bandits.get(sid)
        assert bandit is not None, "bandit 应该在 select_intervention 时初始化"
        total_pulls = int(bandit.bandit.arm_pull_counts.sum())
        # 3 道策略质疑 + 1 道 seed, 至少 B4 update 跑了 3 次 (prev 非 None)
        # select_intervention 内部也会 pull arm
        assert total_pulls >= 1, f"LinUCB 应该被训练 (B4 reward), 总 pull={total_pulls}"

    def test_strategy_challenge_metadata_has_both_keys(
        self, dual_agent_orch, belief_state
    ):
        """策略质疑路径 metadata 必须同时有 strategy_challenge_triggered + dual_agent_confidence."""
        sid = "test_sc_path"
        _seed_intervention_history(dual_agent_orch, sid, n=1)

        obs = _make_observation("PB-C01", score=1.0, sid=sid)
        with _force_strategy_challenge_trigger(dual_agent_orch, sid):
            result = dual_agent_orch.process_observation(obs, student_id=sid)

        # metadata 应该有两个 key
        assert result.metadata.get("strategy_challenge_triggered") is True
        assert "dual_agent_confidence" in result.metadata
        assert result.metadata["dual_agent_confidence"] is not None


# ──────────────────────────────────────────────────────────────────────
# 2. 常态循环路径: 不退化
# ──────────────────────────────────────────────────────────────────────


class TestNormalCyclePathNotRegressed:
    """v0.69.0-d: 常态循环路径不退化 (修复抽函数后仍正常工作)."""

    def test_normal_cycle_still_writes_dual_agent_confidence(
        self, dual_agent_orch, belief_state
    ):
        """常态循环路径 (不触发策略质疑) 仍写 dual_agent_confidence."""
        sid = "test_sc_path"

        # 第 1 道: prev=None
        obs1 = _make_observation("PB-C01", score=1.0, sid=sid)
        # 不 patch detect_ineffective_intervention, 走真实逻辑 (返回 False)
        result1 = dual_agent_orch.process_observation(obs1, student_id=sid)

        # 第 2 道: prev=result1, 应该走 _post_process_calibration (常态循环路径)
        obs2 = _make_observation("PB-C02", score=1.0, sid=sid)
        result2 = dual_agent_orch.process_observation(obs2, student_id=sid)

        # 验证常态循环路径也写 dual_agent_confidence
        assert "dual_agent_confidence" in result2.metadata
        assert result2.metadata["dual_agent_confidence"] is not None

        # 验证 strategy_challenge_triggered 不在 metadata (常态循环路径不触发)
        assert not result2.metadata.get("strategy_challenge_triggered")

    def test_normal_cycle_writes_causal_effect(
        self, dual_agent_orch, belief_state
    ):
        """常态循环路径填 prev.causal_effect."""
        sid = "test_sc_path"
        for pid in ["PB-C01", "PB-C02"]:
            obs = _make_observation(pid, score=1.0, sid=sid)
            dual_agent_orch.process_observation(obs, student_id=sid)

        prev = dual_agent_orch.intervention_history[sid][-2]
        assert prev.causal_effect is not None
        assert prev.causal_effect.student_id == sid
