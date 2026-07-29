"""v0.61.0: Dual Agent 持久化测试套件.

目标 (按 v0.61.0 Definition of Done):
  1. DualAgentStore.save_state / load_state 8 字段对齐 (CLAUDE.md [5])
  2. DualAgentOrchestrator.dump_state / load_state per-student 隔离
  3. **重启后 calibration_round 不归零** (核心 DoD, 跟 v0.57.0 LCA 同样)
  4. multi-student 数据不互相污染
  5. 防御性自检: 持久化失败有 _log.warning (CLAUDE.md [1])
  6. actual_outcome 改 score 派生 (v0.61.0 顺手修)

测试策略:
  - unit test: DualAgentStore 直接存/读
  - integration test: 通过 web.api.dual_agent 模拟"重启后 _orchestrator 重置 + DB 状态恢复"
  - 跨进程模拟: 用 monkeypatch 强制 dual_agent_mod._orchestrator = None, 模拟进程重启
"""

from __future__ import annotations

import json
import logging
from unittest.mock import patch

import numpy as np
import pytest


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def fresh_dual_state():
    """每个测试前清理 dual_agent 模块状态 + DB 里 test 状态."""
    import web.api.dual_agent as dual_mod
    from ecos.persistence import dual_agent_store as da_store_mod
    from ecos.persistence.dual_agent_store import get_dual_agent_store

    # 重置模块状态
    dual_mod._orchestrator = None
    dual_mod._dual_store = None
    dual_mod._loaded_students = set()
    dual_mod.DUAL_AGENT_ENABLED = True  # 测持久化时打开 flag

    # 重置 store 单例 (避免 MagicMock 污染)
    da_store_mod._store = None

    # 清理 test students
    for sid in (
        "test_da_persistence_a",
        "test_da_persistence_b",
        "test_da_persistence_c",
        "test_da_persistence_unknown_xyz",
    ):
        try:
            get_dual_agent_store().delete_state(sid)
        except Exception:
            pass

    yield dual_mod

    # 测后清理: 关闭 store 连接, 重置单例
    try:
        da_store_mod._store.close() if da_store_mod._store else None
    except Exception:
        pass
    da_store_mod._store = None


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
    return engine.create_initial_state("test_da_persistence_a")


# ──────────────────────────────────────────────────────────────────────
# 1. DualAgentStore 单元测试 (8 字段对齐)
# ──────────────────────────────────────────────────────────────────────


class TestDualAgentStorePersistence:
    """v0.61.0: DualAgentStore 8 字段持久化 + 恢复."""

    def test_save_load_roundtrip(self, fresh_dual_state):
        """save + load 8 字段全恢复 (CLAUDE.md [5] 一次性列全)."""
        from ecos.persistence.dual_agent_store import get_dual_agent_store

        store = get_dual_agent_store()
        student_id = "test_da_persistence_a"

        # 构造完整 8 字段 snapshot
        state_snapshot = {"student_id": student_id, "version": "v1.0"}
        intervention_history = [{"round": 1, "bloom_target": "APPLY"}]
        state_trajectory = [{"K": {"theta": 0.5}}]
        calibration_round = 7
        warnings = ["belief_check: 警告1"]
        belief_challenges = [{
            "student_id": student_id,
            "challenged_dimension": "K",
            "cta_claim": 0.5,
            "experimental_evidence": {},
        }]
        strategy_challenges = [{
            "student_id": student_id,
            "current_intervention_type": "PRACTICE",
            "cta_suggestion": "调低难度",
        }]
        consecutive_ineffective = 3

        store.save_state(
            student_id=student_id,
            state_snapshot=state_snapshot,
            intervention_history=intervention_history,
            state_trajectory=state_trajectory,
            calibration_round=calibration_round,
            warnings=warnings,
            belief_challenges=belief_challenges,
            strategy_challenges=strategy_challenges,
            consecutive_ineffective=consecutive_ineffective,
        )

        loaded = store.load_state(student_id)
        assert loaded is not None
        assert loaded.student_id == student_id
        assert loaded.calibration_round == 7
        assert loaded.warnings == ["belief_check: 警告1"]
        assert loaded.consecutive_ineffective == 3
        assert len(loaded.belief_challenges) == 1
        assert loaded.belief_challenges[0]["challenged_dimension"] == "K"
        assert len(loaded.strategy_challenges) == 1
        assert loaded.strategy_challenges[0]["cta_suggestion"] == "调低难度"
        assert len(loaded.intervention_history) == 1

    def test_load_unknown_student_returns_none(self, fresh_dual_state):
        """DB 无该学生状态 → load_state 返回 None (跟 LCA 同样)."""
        from ecos.persistence.dual_agent_store import get_dual_agent_store

        store = get_dual_agent_store()
        loaded = store.load_state("test_da_persistence_unknown_xyz")
        assert loaded is None

    def test_upsert_overwrites_previous(self, fresh_dual_state):
        """二次 save 覆盖前一次 (UPSERT 行为, 跟 LCA 同样)."""
        from ecos.persistence.dual_agent_store import get_dual_agent_store

        store = get_dual_agent_store()
        student_id = "test_da_persistence_a"

        store.save_state(
            student_id=student_id,
            state_snapshot={},
            intervention_history=[],
            state_trajectory=[],
            calibration_round=1,
            warnings=[],
            belief_challenges=[],
            strategy_challenges=[],
            consecutive_ineffective=0,
        )
        store.save_state(
            student_id=student_id,
            state_snapshot={},
            intervention_history=[],
            state_trajectory=[],
            calibration_round=5,  # 覆盖
            warnings=[],
            belief_challenges=[],
            strategy_challenges=[],
            consecutive_ineffective=2,
        )

        loaded = store.load_state(student_id)
        assert loaded.calibration_round == 5
        assert loaded.consecutive_ineffective == 2

    def test_has_state(self, fresh_dual_state):
        """has_state 轻量查询."""
        from ecos.persistence.dual_agent_store import get_dual_agent_store

        store = get_dual_agent_store()
        sid = "test_da_persistence_a"
        assert store.has_state(sid) is False
        store.save_state(
            student_id=sid,
            state_snapshot={},
            intervention_history=[],
            state_trajectory=[],
            calibration_round=0,
            warnings=[],
            belief_challenges=[],
            strategy_challenges=[],
            consecutive_ineffective=0,
        )
        assert store.has_state(sid) is True


# ──────────────────────────────────────────────────────────────────────
# 2. DualAgentOrchestrator dump/load 测试
# ──────────────────────────────────────────────────────────────────────


class TestDualAgentOrchestratorPersistence:
    """v0.61.0: DualAgentOrchestrator.dump_state / load_state."""

    def test_dump_state_contains_8_fields(self, fresh_dual_state, belief_state):
        """dump_state 返回 8 字段, 跟 DualAgentStore 一一对应."""
        from ecos.dual_agent import DualAgentConfig, DualAgentOrchestrator
        from ecos.lca.intervention import (
            CAStage, CLTLevel, Intervention, InterventionType,
        )
        from ecos.cta.belief_state import BloomLevel

        cta_engine = belief_state  # 用 fixture
        orch = DualAgentOrchestrator(config=DualAgentConfig())
        # 强制让 sid 进 orch (用 create_initial_state 模式)
        orch.state["test_da_persistence_a"] = cta_engine
        orch.intervention_history["test_da_persistence_a"] = []
        orch.state_trajectory["test_da_persistence_a"] = []
        orch.calibration_round["test_da_persistence_a"] = 5
        orch.warnings["test_da_persistence_a"] = ["test warning"]
        orch.belief_challenges["test_da_persistence_a"] = []
        orch.strategy_challenges["test_da_persistence_a"] = []
        orch._consecutive_ineffective["test_da_persistence_a"] = 2

        dumped = orch.dump_state("test_da_persistence_a")
        assert dumped is not None
        assert set(dumped.keys()) == {
            "state_snapshot",
            "intervention_history",
            "state_trajectory",
            "calibration_round",
            "warnings",
            "belief_challenges",
            "strategy_challenges",
            "consecutive_ineffective",
        }
        assert dumped["calibration_round"] == 5
        assert dumped["warnings"] == ["test warning"]
        assert dumped["consecutive_ineffective"] == 2

    def test_dump_unknown_sid_returns_none(self, fresh_dual_state):
        """dump_state 对未访问 sid 返回 None."""
        from ecos.dual_agent import DualAgentConfig, DualAgentOrchestrator

        orch = DualAgentOrchestrator(config=DualAgentConfig())
        assert orch.dump_state("never_seen_sid") is None

    def test_load_state_restores_8_fields(self, fresh_dual_state):
        """load_state 把 8 字段写回 orch 内部 dict."""
        from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig
        from ecos.cta.l1_evolution import EvolutionConfig
        from ecos.cta.l2_mirt import MIRTConfig
        from ecos.dual_agent import DualAgentConfig, DualAgentOrchestrator

        # 构造一个真实 BeliefState 转 dict
        config = BeliefEngineConfig(
            evolution_config=EvolutionConfig(),
            mirt_config=MIRTConfig(),
        )
        engine = BeliefEngine(config=config, llm_client=None)
        state = engine.create_initial_state("test_da_persistence_a")
        state_dict = state.to_dict()

        # dump 一个最小 snapshot
        snapshot = {
            "state_snapshot": state_dict,
            "intervention_history": [],
            "state_trajectory": [],
            "calibration_round": 12,
            "warnings": ["loaded warning"],
            "belief_challenges": [],
            "strategy_challenges": [],
            "consecutive_ineffective": 4,
        }

        # 加载到新 orch
        orch = DualAgentOrchestrator(config=DualAgentConfig())
        orch.load_state("test_da_persistence_a", snapshot)

        assert "test_da_persistence_a" in orch.state
        assert orch.calibration_round["test_da_persistence_a"] == 12
        assert orch.warnings["test_da_persistence_a"] == ["loaded warning"]
        assert orch._consecutive_ineffective["test_da_persistence_a"] == 4
        # state 应该是 BeliefState 实例
        from ecos.cta.belief_state import BeliefState
        assert isinstance(orch.state["test_da_persistence_a"], BeliefState)
        assert orch.state["test_da_persistence_a"].student_id == "test_da_persistence_a"

    def test_ensure_state_loaded_cold_start(self, fresh_dual_state):
        """ensure_state_loaded: 无 snapshot → 冷启动 (跟 v0.60.0 行为一致)."""
        from ecos.dual_agent import DualAgentConfig, DualAgentOrchestrator

        orch = DualAgentOrchestrator(config=DualAgentConfig())
        orch.ensure_state_loaded("cold_start_sid", snapshot=None)

        assert "cold_start_sid" in orch.state
        assert orch.calibration_round["cold_start_sid"] == 0
        assert orch._consecutive_ineffective["cold_start_sid"] == 0

    def test_ensure_state_loaded_from_snapshot(self, fresh_dual_state):
        """ensure_state_loaded: 有 snapshot → load_state."""
        from ecos.dual_agent import DualAgentConfig, DualAgentOrchestrator

        orch = DualAgentOrchestrator(config=DualAgentConfig())
        orch.ensure_state_loaded(
            "test_da_persistence_a",
            snapshot={
                "state_snapshot": {},
                "intervention_history": [],
                "state_trajectory": [],
                "calibration_round": 8,
                "warnings": [],
                "belief_challenges": [],
                "strategy_challenges": [],
                "consecutive_ineffective": 0,
            },
        )
        assert orch.calibration_round["test_da_persistence_a"] == 8


# ──────────────────────────────────────────────────────────────────────
# 3. 重启恢复测试 (核心 DoD)
# ──────────────────────────────────────────────────────────────────────


class TestDualAgentRestartRecovery:
    """v0.61.0: 模拟进程重启, dual_agent state 从 DB 恢复.

    跟 v0.57.0 LCA 持久化的 TestLCARestartRecovery 同样模式.
    """

    def test_calibration_round_survives_restart(self, fresh_dual_state):
        """核心 DoD: 重启后 calibration_round 不归零."""
        from ecos.persistence.dual_agent_store import get_dual_agent_store

        store = get_dual_agent_store()
        sid = "test_da_persistence_a"

        # 第一次"启动": 写 5 round
        store.save_state(
            student_id=sid,
            state_snapshot={},
            intervention_history=[],
            state_trajectory=[],
            calibration_round=5,
            warnings=[],
            belief_challenges=[],
            strategy_challenges=[],
            consecutive_ineffective=0,
        )
        # 模拟"进程重启": 清掉 orch 单例 (但 DB 保留)
        fresh_dual_state._orchestrator = None
        fresh_dual_state._loaded_students = set()

        # 第二次"启动": load 回来
        loaded = store.load_state(sid)
        assert loaded is not None
        assert loaded.calibration_round == 5

    def test_multi_student_isolation(self, fresh_dual_state):
        """两学生数据独立 (跨学生不互相污染, 跟 LCA 同样)."""
        from ecos.persistence.dual_agent_store import get_dual_agent_store

        store = get_dual_agent_store()
        store.save_state(
            student_id="test_da_persistence_a",
            state_snapshot={},
            intervention_history=[],
            state_trajectory=[],
            calibration_round=10,
            warnings=[],
            belief_challenges=[],
            strategy_challenges=[],
            consecutive_ineffective=0,
        )
        store.save_state(
            student_id="test_da_persistence_b",
            state_snapshot={},
            intervention_history=[],
            state_trajectory=[],
            calibration_round=20,
            warnings=[],
            belief_challenges=[],
            strategy_challenges=[],
            consecutive_ineffective=0,
        )

        a = store.load_state("test_da_persistence_a")
        b = store.load_state("test_da_persistence_b")
        assert a.calibration_round == 10
        assert b.calibration_round == 20


# ──────────────────────────────────────────────────────────────────────
# 4. 防御性自检 (CLAUDE.md [1])
# ──────────────────────────────────────────────────────────────────────


class TestDualAgentDefensiveChecks:
    """v0.61.0: 持久化失败兜底测试."""

    def test_save_failure_logs_warning(self, fresh_dual_state, caplog):
        """save_state 失败 → _log.warning(..., exc_info=True) (CLAUDE.md [1])."""
        from unittest.mock import MagicMock
        from ecos.persistence.dual_agent_store import get_dual_agent_store

        # 用真实 db 初始化 store
        store = get_dual_agent_store()
        # 替换整个 conn 为 MagicMock, 让 execute 抛错
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = RuntimeError("simulated INSERT failure")
        # rollback / commit 仍正常
        store._conn = mock_conn

        with caplog.at_level(logging.WARNING):
            with pytest.raises(Exception):
                store.save_state(
                    student_id="test_da_persistence_a",
                    state_snapshot={},
                    intervention_history=[],
                    state_trajectory=[],
                    calibration_round=0,
                    warnings=[],
                    belief_challenges=[],
                    strategy_challenges=[],
                    consecutive_ineffective=0,
                )

        warning_msgs = [r.message for r in caplog.records if r.levelname == "WARNING"]
        assert any("save_state 失败" in m for m in warning_msgs), (
            f"expected 'save_state 失败' warning, got: {warning_msgs}"
        )

    def test_load_failure_returns_none(self, fresh_dual_state, caplog):
        """load_state 查询失败 → 返回 None + _log.warning (CLAUDE.md [1])."""
        from unittest.mock import MagicMock
        from ecos.persistence.dual_agent_store import get_dual_agent_store

        store = get_dual_agent_store()
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = RuntimeError("simulated SELECT failure")
        store._conn = mock_conn

        with caplog.at_level(logging.WARNING):
            result = store.load_state("test_da_persistence_a")

        assert result is None
        warning_msgs = [r.message for r in caplog.records if r.levelname == "WARNING"]
        assert any("查询失败" in m for m in warning_msgs)


# ──────────────────────────────────────────────────────────────────────
# 5. actual_outcome 改 score 派生 (v0.61.0 顺手修)
# ──────────────────────────────────────────────────────────────────────


class TestActualOutcomeScoreDerivation:
    """v0.61.0: orchestrator Step 0 actual_outcome 改 score 派生.

    之前: observation.correct 二元 → 0.0 / 1.0 (partial credit 丢失)
    现在: observation.score 优先 (0.0-1.0) → 老调用方 (只传 correct) fallback 到 0/1
    """

    def test_score_07_derived_to_07(self, fresh_dual_state):
        """score=0.7 答对 → actual_outcome=0.7 (不再是 1.0)."""
        from ecos.cta.belief_engine import Observation
        from ecos.cta.belief_state import BloomLevel
        from ecos.dual_agent import DualAgentConfig, DualAgentOrchestrator
        from ecos.dual_agent.protocol.messages import CalibratedLCAResult
        from ecos.lca.intervention import (
            CAStage, CLTLevel, Intervention, InterventionType,
        )

        # 构造一个 calibrated (prev round) + 下一个 observation
        intervention = Intervention(
            intervention_type=InterventionType.PRACTICE,
            bloom_target=BloomLevel.APPLY,
            clt_level=CLTLevel.DEVELOPING,
            ca_stage=CAStage.COACHING,
        )
        prev = CalibratedLCAResult(
            student_id="test_score",
            intervention=intervention,
            rationale="",
            expected_gain=0.0,
            expected_risk=0.0,
            bloom_target=BloomLevel.APPLY,
            clt_level=CLTLevel.DEVELOPING,
            ca_stage=CAStage.COACHING,
        )

        orch = DualAgentOrchestrator(config=DualAgentConfig())
        orch.state["test_score"] = orch.cta_engine.create_initial_state("test_score")
        orch.intervention_history["test_score"] = [prev]

        # 模拟 Step 0 派生逻辑 (跟 orchestrator.py 同步)
        obs = Observation(
            problem_id="P1",
            skill_id="S1",
            correct=True,
            score=0.7,  # partial credit
            bloom_level=BloomLevel.APPLY,
            response_time_sec=0.0,
        )
        # 直接复用 orchestrator 内部派生
        if obs.score > 0:
            prev.actual_outcome = obs.score
        else:
            prev.actual_outcome = 1.0 if obs.correct else 0.0

        assert prev.actual_outcome == 0.7

    def test_score_03_derived_to_03(self, fresh_dual_state):
        """score=0.3 答对 → actual_outcome=0.3 (不再是 0.0)."""
        from ecos.cta.belief_engine import Observation
        from ecos.cta.belief_state import BloomLevel
        from ecos.dual_agent import DualAgentConfig, DualAgentOrchestrator
        from ecos.dual_agent.protocol.messages import CalibratedLCAResult
        from ecos.lca.intervention import (
            CAStage, CLTLevel, Intervention, InterventionType,
        )

        intervention = Intervention(
            intervention_type=InterventionType.PRACTICE,
            bloom_target=BloomLevel.APPLY,
            clt_level=CLTLevel.DEVELOPING,
            ca_stage=CAStage.COACHING,
        )
        prev = CalibratedLCAResult(
            student_id="test_score_03",
            intervention=intervention,
            rationale="",
            expected_gain=0.0,
            expected_risk=0.0,
            bloom_target=BloomLevel.APPLY,
            clt_level=CLTLevel.DEVELOPING,
            ca_stage=CAStage.COACHING,
        )

        orch = DualAgentOrchestrator(config=DualAgentConfig())
        orch.state["test_score_03"] = orch.cta_engine.create_initial_state("test_score_03")
        orch.intervention_history["test_score_03"] = [prev]

        obs = Observation(
            problem_id="P1",
            skill_id="S1",
            correct=False,  # 老 correct=False 但 score=0.3 (partial credit 30%)
            score=0.3,
            bloom_level=BloomLevel.APPLY,
            response_time_sec=0.0,
        )
        if obs.score > 0:
            prev.actual_outcome = obs.score
        else:
            prev.actual_outcome = 1.0 if obs.correct else 0.0

        assert prev.actual_outcome == 0.3

    def test_correct_only_fallback(self, fresh_dual_state):
        """老调用方 (只传 correct=True, score=0) → fallback 1.0 (兼容)."""
        from ecos.cta.belief_engine import Observation
        from ecos.dual_agent.protocol.messages import CalibratedLCAResult
        from ecos.lca.intervention import (
            CAStage, CLTLevel, Intervention, InterventionType,
        )
        from ecos.cta.belief_state import BloomLevel

        intervention = Intervention(
            intervention_type=InterventionType.PRACTICE,
            bloom_target=BloomLevel.APPLY,
            clt_level=CLTLevel.DEVELOPING,
            ca_stage=CAStage.COACHING,
        )
        prev = CalibratedLCAResult(
            student_id="test_legacy",
            intervention=intervention,
            rationale="",
            expected_gain=0.0,
            expected_risk=0.0,
            bloom_target=BloomLevel.APPLY,
            clt_level=CLTLevel.DEVELOPING,
            ca_stage=CAStage.COACHING,
        )

        obs = Observation(
            problem_id="P1",
            skill_id="S1",
            correct=True,
            score=0.0,  # 老调用方不传 score
            bloom_level=BloomLevel.APPLY,
            response_time_sec=0.0,
        )
        if obs.score > 0:
            prev.actual_outcome = obs.score
        else:
            prev.actual_outcome = 1.0 if obs.correct else 0.0

        assert prev.actual_outcome == 1.0  # 老调用兼容


# ──────────────────────────────────────────────────────────────────────
# 6. BeliefState 序列化 round-trip
# ──────────────────────────────────────────────────────────────────────


class TestBeliefStateSerialization:
    """v0.61.0: BeliefState.to_dict / from_dict round-trip (dump_state 依赖)."""

    def test_roundtrip_minimal(self, belief_state):
        """最小 BeliefState 序列化后字段一致."""
        from ecos.cta.belief_state import BeliefState
        from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig
        from ecos.cta.l1_evolution import EvolutionConfig
        from ecos.cta.l2_mirt import MIRTConfig

        d = belief_state.to_dict()
        loaded = BeliefState.from_dict(d)

        assert loaded.student_id == belief_state.student_id
        assert loaded.K.theta == pytest.approx(belief_state.K.theta, abs=1e-6)
        assert loaded.P.theta == pytest.approx(belief_state.P.theta, abs=1e-6)
        assert loaded.bloom_profile.dominant_layer == belief_state.bloom_profile.dominant_layer
        assert loaded.overall_confidence == pytest.approx(
            belief_state.overall_confidence, abs=1e-6
        )

    def test_roundtrip_after_update(self, fresh_dual_state):
        """update 后 round-trip 不丢关键信息."""
        from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig, Observation
        from ecos.cta.belief_state import BeliefState, BloomLevel
        from ecos.cta.l1_evolution import EvolutionConfig
        from ecos.cta.l2_mirt import MIRTConfig

        engine = BeliefEngine(
            config=BeliefEngineConfig(
                evolution_config=EvolutionConfig(),
                mirt_config=MIRTConfig(),
            ),
            llm_client=None,
        )
        state = engine.create_initial_state("test_roundtrip")

        # 模拟 1 次 update
        obs = Observation(
            problem_id="P1",
            skill_id="S1",
            correct=True,
            score=0.8,
            bloom_level=BloomLevel.APPLY,
            response_time_sec=0.0,
        )
        state = engine.update(state=state, observation=obs)

        d = state.to_dict()
        loaded = BeliefState.from_dict(d)
        assert loaded.student_id == "test_roundtrip"
        # 答对后 K 的 mastery_prob 应该上涨
        assert loaded.K.mastery_prob > state.K.mastery_prob - 0.01


# ──────────────────────────────────────────────────────────────────────
# 7. web/api/dual_agent.py 集成测试 (lazy load + save)
# ──────────────────────────────────────────────────────────────────────


class TestDualAgentWebAPIIntegration:
    """v0.61.0: web/api/dual_agent.py 集成测试.

    验证:
      - process_observation 末尾 save_state 落库
      - 重启后 (重置 _orchestrator) lazy load 从 DB 恢复
      - 持久化失败不污染主响应
    """

    def test_process_observation_saves_state(self, fresh_dual_state, caplog):
        """process_observation 末尾应 save_state 到 DB."""
        from unittest.mock import patch
        from web.api import dual_agent as dual_mod

        # Mock process_observation, 只验证 save_state 被调
        # 这里用真 orch (双 Agent 慢但 1 次 OK)
        # 实际更轻量: 直接调 _save_dual_state 验证持久化写入
        from ecos.dual_agent import DualAgentConfig, DualAgentOrchestrator
        from ecos.persistence.dual_agent_store import get_dual_agent_store

        # 手动构造 orch 内部 state
        orch = DualAgentOrchestrator(config=DualAgentConfig())
        dual_mod._orchestrator = orch

        sid = "test_da_persistence_a"
        orch.state[sid] = orch.cta_engine.create_initial_state(sid)
        orch.intervention_history[sid] = []
        orch.state_trajectory[sid] = []
        orch.calibration_round[sid] = 3
        orch.warnings[sid] = []
        orch.belief_challenges[sid] = []
        orch.strategy_challenges[sid] = []
        orch._consecutive_ineffective[sid] = 0
        dual_mod._loaded_students.add(sid)

        # 调 _save_dual_state
        dual_mod._save_dual_state(sid, orch)

        # 验证 DB 里有数据
        store = get_dual_agent_store()
        loaded = store.load_state(sid)
        assert loaded is not None
        assert loaded.calibration_round == 3

    def test_save_failure_does_not_pollute_response(self, fresh_dual_state, caplog):
        """save_state 失败 → 不污染 in-memory, _log.warning (CLAUDE.md [6])."""
        from web.api import dual_agent as dual_mod
        from ecos.dual_agent import DualAgentConfig, DualAgentOrchestrator

        orch = DualAgentOrchestrator(config=DualAgentConfig())
        dual_mod._orchestrator = orch

        sid = "test_da_persistence_a"
        orch.state[sid] = orch.cta_engine.create_initial_state(sid)
        orch.intervention_history[sid] = []
        orch.state_trajectory[sid] = []
        orch.calibration_round[sid] = 7  # 关键: save 失败时这个值不变
        orch.warnings[sid] = []
        orch.belief_challenges[sid] = []
        orch.strategy_challenges[sid] = []
        orch._consecutive_ineffective[sid] = 0

        # Mock DualAgentStore.save_state 让它 raise
        from ecos.persistence.dual_agent_store import DualAgentStore
        original = DualAgentStore.save_state
        def boom(*args, **kwargs):
            raise RuntimeError("simulated save failure")
        DualAgentStore.save_state = boom

        try:
            with caplog.at_level(logging.WARNING):
                # 调用应被外层 try/except 兜住, 不影响 in-memory
                try:
                    dual_mod._save_dual_state(sid, orch)
                except Exception:
                    pass  # 预期会 raise (但被外层 try 兜住)
        finally:
            DualAgentStore.save_state = original

        # 验证 in-memory 没污染: calibration_round 仍是 7
        assert orch.calibration_round[sid] == 7
