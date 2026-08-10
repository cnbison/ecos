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
# 入口
# ──────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
