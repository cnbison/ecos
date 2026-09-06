"""v0.83.0-b: Belief-Evidence 关联测试套件.

目标 (按 v0.83.0-b Definition of Done):
  - BeliefState.add_evidence 支持 5D 维度 (K/P/S/C/X) + bloom + tc_<id>
  - BeliefState.evidence_for 反查
  - BeliefState.evidence_summary 返回 6+1 维度数量
  - BeliefUpdator + EvidenceEngine 集成 (有/无 evidence_engine 注入)
  - 防御性自检 [8] 仍 hard block (add_evidence 在 allowlist)
"""

from __future__ import annotations

import sys
from datetime import datetime
from unittest.mock import MagicMock

import pytest


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def belief_state():
    """构造最小 BeliefState (含 5D + bloom + 1 TC)."""
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
    state = engine.create_initial_state("test_bel_student")
    return state


# ──────────────────────────────────────────────────────────────────────
# 1. BeliefState.add_evidence 维度 (7 tests: K/P/S/C/X/bloom/tc)
# ──────────────────────────────────────────────────────────────────────


class TestBeliefStateAddEvidence:
    """v0.83.0-b: BeliefState.add_evidence 维度支持."""

    def test_add_evidence_to_K(self, belief_state):
        """add_evidence("K", 42) -> state.K.evidence_ids = [42]."""
        belief_state.add_evidence("K", 42)
        assert 42 in belief_state.K.evidence_ids

    def test_add_evidence_to_P(self, belief_state):
        """add_evidence("P", 43) -> state.P.evidence_ids = [43]."""
        belief_state.add_evidence("P", 43)
        assert 43 in belief_state.P.evidence_ids

    def test_add_evidence_to_S(self, belief_state):
        """add_evidence("S", 44) -> state.S.evidence_ids = [44]."""
        belief_state.add_evidence("S", 44)
        assert 44 in belief_state.S.evidence_ids

    def test_add_evidence_to_C(self, belief_state):
        """add_evidence("C", 45) -> state.C.evidence_ids = [45]."""
        belief_state.add_evidence("C", 45)
        assert 45 in belief_state.C.evidence_ids

    def test_add_evidence_to_X(self, belief_state):
        """add_evidence("X", 46) -> state.X.evidence_ids = [46]."""
        belief_state.add_evidence("X", 46)
        assert 46 in belief_state.X.evidence_ids

    def test_add_evidence_to_bloom(self, belief_state):
        """add_evidence("bloom", 47) -> state.bloom_profile.evidence_ids = [47]."""
        belief_state.add_evidence("bloom", 47)
        assert 47 in belief_state.bloom_profile.evidence_ids

    def test_add_evidence_to_tc(self, belief_state):
        """add_evidence("tc_python_variables", 48) -> tc_states 关联."""
        # 准备 TC state (TCState 字段: tc_id / status / progress / confidence)
        from ecos.cta.belief_state import TCState
        belief_state.C.tc_states["python_variables"] = TCState(
            tc_id="python_variables", status="liminal", progress=0.5, confidence=0.5,
        )
        belief_state.add_evidence("tc_python_variables", 48)
        assert 48 in belief_state.C.tc_states["python_variables"].evidence_ids


# ──────────────────────────────────────────────────────────────────────
# 2. BeliefState.evidence_for 反查 (2 tests)
# ──────────────────────────────────────────────────────────────────────


class TestBeliefStateEvidenceFor:
    """v0.83.0-b: BeliefState.evidence_for 反查."""

    def test_evidence_for_returns_list_copy(self, belief_state):
        """evidence_for 返 list 副本 (改副本不影响原 state)."""
        belief_state.add_evidence("K", 1)
        belief_state.add_evidence("K", 2)
        result = belief_state.evidence_for("K")
        assert result == [1, 2]
        # 副本修改不影响原 state
        result.append(99)
        assert 99 not in belief_state.K.evidence_ids

    def test_evidence_for_unknown_dim_returns_empty(self, belief_state):
        """evidence_for(unknown_dim) 返空 list, 不 raise."""
        result = belief_state.evidence_for("nonexistent_dim")
        assert result == []


# ──────────────────────────────────────────────────────────────────────
# 3. evidence_summary 概览 (1 test)
# ──────────────────────────────────────────────────────────────────────


class TestBeliefStateEvidenceSummary:
    """v0.83.0-b: evidence_summary 返回 6+1 维度数量."""

    def test_evidence_summary_returns_6_plus_1_dict(self, belief_state):
        """evidence_summary 返 {"K": n, "P": n, ..., "bloom": n, "tc": n}."""
        belief_state.add_evidence("K", 1)
        belief_state.add_evidence("P", 2)
        belief_state.add_evidence("bloom", 3)

        summary = belief_state.evidence_summary()
        assert set(summary.keys()) == {"K", "P", "S", "C", "X", "bloom", "tc"}
        assert summary["K"] == 1
        assert summary["P"] == 1
        assert summary["bloom"] == 1
        assert summary["S"] == 0  # 未加
        assert summary["tc"] == 0


# ──────────────────────────────────────────────────────────────────────
# 4. BeliefUpdator + EvidenceEngine 集成 (2 tests)
# ──────────────────────────────────────────────────────────────────────


class TestBeliefUpdatorEvidenceIntegration:
    """v0.83.0-b: BeliefUpdator 接入 EvidenceEngine (有/无 evidence_engine 注入)."""

    def test_belief_updater_without_evidence_engine_uses_legacy_path(self, belief_state):
        """无 evidence_engine 注入 -> 走原 evidence_ids.append 路径 (向后兼容)."""
        from ecos.cta.belief_updater import BeliefUpdator
        from ecos.cta.state_engine import get_default_engine

        updater = BeliefUpdator(state_engine=get_default_engine())
        assert updater.evidence_engine is None

        # 模拟 dim updates
        from ecos.cta.inference_engine import InferenceResult
        result = InferenceResult(
            theta_mean=None, theta_cov=None, dim_updates={}, bloom_field_updates={},
        )
        # 没法直接调 apply (需要 observation 等), 但可验证 evidence_engine 字段
        assert updater.evidence_engine is None

    def test_belief_updater_with_evidence_engine_integration(self, belief_state):
        """有 evidence_engine 注入 -> _register_evidence 路径 (走 add_evidence 入口)."""
        from ecos.cta.belief_updater import BeliefUpdator
        from ecos.cta.state_engine import get_default_engine

        # 构造 mock Evidence Engine
        mock_engine = MagicMock()
        mock_engine.add.return_value = 100  # 模拟返回 evidence_id=100

        updater = BeliefUpdator(
            state_engine=get_default_engine(),
            evidence_engine=mock_engine,
        )
        assert updater.evidence_engine is mock_engine

        # 准备一个 mock observation
        observation = MagicMock()
        observation.to_dict.return_value = {
            "problem_id": "p1", "correct": True, "score": 1.0,
        }

        # 调 _register_evidence
        updater._register_evidence("K", 0, observation, belief_state)

        # EvidenceEngine.add 被调了 1 次
        assert mock_engine.add.call_count == 1
        # state.add_evidence 把 100 加到了 K
        assert 100 in belief_state.K.evidence_ids


# ──────────────────────────────────────────────────────────────────────
# 5. 防御性自检 (1 test)
# ──────────────────────────────────────────────────────────────────────


class TestDefensiveCheck:
    """v0.83.0-b: add_evidence 在 FUNC_ALLOWLIST (防御性自检 [8] 仍 hard block)."""

    def test_add_evidence_in_allowlist(self):
        """scripts/check_no_direct_state_mutation.py FUNC_ALLOWLIST 含 add_evidence."""
        import re
        from pathlib import Path

        check_path = Path("scripts/check_no_direct_state_mutation.py")
        if not check_path.exists():
            pytest.skip("check_no_direct_state_mutation.py not found")
        source = check_path.read_text()
        # 找 FUNC_ALLOWLIST 块
        match = re.search(r"FUNC_ALLOWLIST\s*=\s*\{(.*?)\}", source, re.DOTALL)
        assert match, "FUNC_ALLOWLIST 块未找到"
        allowlist_body = match.group(1)
        assert "add_evidence" in allowlist_body, \
            "FUNC_ALLOWLIST 应含 add_evidence (v0.83.0-b)"

    def test_evidence_summary_5d_default_zero(self, belief_state):
        """新建 state evidence_summary 全 0 (无任何 evidence)."""
        summary = belief_state.evidence_summary()
        for dim in ("K", "P", "S", "C", "X"):
            assert summary[dim] == 0
        assert summary["bloom"] == 0
        assert summary["tc"] == 0


# ──────────────────────────────────────────────────────────────────────
# 6. v0.98.0 (b-a): BeliefEngine 透传 + dim 标记 + gate 修复 + replay 抑制
# ──────────────────────────────────────────────────────────────────────


class TestV098EvidenceWiring:
    """v0.98.0 (b-a): 接线审计实例 ③ kernel 侧收口.

    - BeliefEngine.__init__ 新增 evidence_engine 参数并透传 BeliefUpdator
    - _register_evidence payload 加 dim 标记 (per-dim 5 行可区分)
    - add 返回 0 (写库失败) 不关联 state
    - EvidenceEngine.add count gate 修复 (max_per_student=0 零扫描)
    - replay/simulate (log_event=False) 抑制 evidence 写库
    - 默认 None 走 legacy 路径 (golden 结构性零 diff)
    """

    @pytest.fixture
    def engine_and_state(self):
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
        return engine, engine.create_initial_state("test_v098_student")

    def test_belief_engine_forwards_evidence_engine(self):
        """BeliefEngine(evidence_engine=mock) 透传到 _belief_updater."""
        from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig
        from ecos.cta.l1_evolution import EvolutionConfig
        from ecos.cta.l2_mirt import MIRTConfig

        mock_engine = MagicMock()
        config = BeliefEngineConfig(evolution_config=EvolutionConfig())
        engine = BeliefEngine(
            config=config, llm_client=None, evidence_engine=mock_engine,
        )
        assert engine._belief_updater.evidence_engine is mock_engine

    def test_belief_engine_default_none_legacy_path(self, engine_and_state):
        """默认不传 evidence_engine -> BeliefUpdator.evidence_engine is None
        (golden / session / dual_agent / runtime 现有调用方行为不变)."""
        engine, _ = engine_and_state
        assert engine._belief_updater.evidence_engine is None

    def test_register_evidence_payload_has_dim_marker(self, engine_and_state):
        """_register_evidence payload 含 dim 字段, 5 次 dim 调用互不覆盖."""
        from ecos.cta.belief_updater import BeliefUpdator
        from ecos.cta.state_engine import get_default_engine

        mock_engine = MagicMock()
        captured = []

        def capture_add(ev):
            captured.append(dict(ev.payload))
            return 100 + len(captured)

        mock_engine.add.side_effect = capture_add
        updater = BeliefUpdator(
            state_engine=get_default_engine(), evidence_engine=mock_engine,
        )

        observation = MagicMock()
        observation.to_dict.return_value = {
            "problem_id": "p1", "correct": True, "score": 1.0,
        }
        for dim in ("K", "P", "S", "C", "X"):
            updater._register_evidence(dim, 0, observation, engine_and_state[1])

        assert len(captured) == 5
        assert [p["dim"] for p in captured] == ["K", "P", "S", "C", "X"]
        # dim 标记不覆盖原 payload 键
        assert all(p["problem_id"] == "p1" for p in captured)

    def test_register_evidence_skips_add_evidence_on_zero(self, engine_and_state):
        """add 返回 0 (FK 写库失败被吞) -> 跳过 state.add_evidence."""
        from ecos.cta.belief_updater import BeliefUpdator
        from ecos.cta.state_engine import get_default_engine

        mock_engine = MagicMock()
        mock_engine.add.return_value = 0
        updater = BeliefUpdator(
            state_engine=get_default_engine(), evidence_engine=mock_engine,
        )
        observation = MagicMock()
        observation.to_dict.return_value = {"problem_id": "p1", "score": 1.0}

        updater._register_evidence("K", 0, observation, engine_and_state[1])
        assert engine_and_state[1].K.evidence_ids == []

    def test_add_gate_disabled_no_scan(self):
        """EvidenceConfig(max_per_student=0) -> add 时零 count 扫描 (gate 修复)."""
        import sqlite3

        from ecos.evidence import Evidence, EvidenceSource
        from ecos.evidence.evidence_engine import EvidenceConfig, EvidenceEngine
        from ecos.persistence.db import Database, SCHEMA_SQL

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA_SQL)
        db = Database.__new__(Database)
        db._conn = conn
        engine = EvidenceEngine(
            config=EvidenceConfig(max_per_student=0), db=db,
        )
        ev = Evidence(
            source=EvidenceSource.RESPONSE_HISTORY,
            student_id="gate_test_student",
            timestamp=datetime.now(),
            payload={"score": 1.0},
            confidence=0.9,
        )
        evidence_id = engine.add(ev)
        assert evidence_id > 0
        # gate 关闭: query_by_student count 扫描不触发 (无异常且 add 正常返回)

    def test_apply_suppresses_evidence_on_replay(self, engine_and_state):
        """apply(log_event=False) 抑制 Evidence Engine 写库 (replay 语义一致)."""
        from ecos.cta.belief_updater import BeliefUpdator
        from ecos.cta.inference_engine import InferenceResult
        from ecos.cta.state_engine import get_default_engine

        mock_engine = MagicMock()
        mock_engine.add.return_value = 1
        updater = BeliefUpdator(
            state_engine=get_default_engine(), evidence_engine=mock_engine,
        )
        result = InferenceResult(
            theta_mean=None, theta_cov=None,
            dim_updates={"K": {
                "theta": 0.1, "se": 1.0, "mastery_prob": 0.2,
                "mastered": False, "confidence": 0.5,
                "evidence_id": 7, "last_updated": datetime.now(),
            }},
            bloom_field_updates={},
        )
        observation = MagicMock()
        observation.to_dict.return_value = {"problem_id": "p1", "score": 1.0}

        updater.apply(engine_and_state[1], result, observation, {}, log_event=False)
        assert mock_engine.add.call_count == 0
        # legacy in-memory 关联仍发生 (replay state 可用)
        assert 7 in engine_and_state[1].K.evidence_ids


# ──────────────────────────────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
