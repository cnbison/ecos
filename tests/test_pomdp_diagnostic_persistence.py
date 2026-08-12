"""v0.93.0-c: POMDP 演化 + 诊断持久化测试.

对应设计: discussions/2026-08-12-v093-design.md §3.

v0.93.0-c 持久化范围:
  - POMDPPolicy.SCHEMA_VERSION 升级 "0.92.0" → "0.93.0"
  - POMDPPolicy.dump_state 加 evolution / update_count / next_snapshot_at 3 字段
  - POMDPPolicy.load_state 老 v0.92 snapshot raise ValueError (防御性自检 [5])
  - POMDPPolicy.load_state evolution 字段 graceful skip (per-snapshot exception _log.warning)

测试范围 (3 tests):
  1. dump_state 含 evolution 字段 (1 test): evolution List[Dict] 序列化正确
  2. load_state 恢复 evolution (1 test): round-trip 后 _evolution 一致
  3. 老 v0.92 snapshot raise (1 test): schema_version="0.92.0" raise ValueError
"""

from __future__ import annotations

import numpy as np
import pytest

from ecos.lca.l4_optimization.pomdp import POMDPPolicy


# ---------------------------------------------------------------------------
# 1. dump_state 含 evolution 字段 (1 test)
# ---------------------------------------------------------------------------


def test_dump_state_includes_evolution_field():
    """dump_state 含 evolution (List[Dict]) + update_count (int) + next_snapshot_at (int) 3 字段.

    跟 v0.90.0-b transition_count / reward_alpha / reward_beta 持久化字段对齐.
    """
    p = POMDPPolicy(seed=42)
    p._next_snapshot_at = 1
    p._evolution_interval = 1
    # 触发 3 个 snapshot
    for i in range(3):
        p.update(arm=0, reward=0.5, observation=0)

    state = p.dump_state()
    assert state["schema_version"] == "0.93.0"
    assert "evolution" in state
    assert isinstance(state["evolution"], list)
    assert len(state["evolution"]) == 3
    # 每个 snapshot 是 dict (POMDPDiagnostic.to_dict())
    for snap_dict in state["evolution"]:
        assert isinstance(snap_dict, dict)
        assert snap_dict["schema_version"] == "0.93.0"
        assert "T" in snap_dict
        assert "R" in snap_dict
        assert "belief" in snap_dict
        assert "coverage" in snap_dict
        assert "most_likely_state" in snap_dict
        assert "last_updated" in snap_dict

    assert state["update_count"] == 3
    assert state["next_snapshot_at"] == 4


# ---------------------------------------------------------------------------
# 2. load_state 恢复 evolution (1 test)
# ---------------------------------------------------------------------------


def test_load_state_restores_evolution():
    """dump_state + load_state round-trip 恢复 _evolution + counters."""
    p1 = POMDPPolicy(seed=42)
    p1._next_snapshot_at = 1
    p1._evolution_interval = 1
    for i in range(5):
        p1.update(arm=i % 10, reward=0.5, observation=0)

    state = p1.dump_state()
    p2 = POMDPPolicy(seed=42)
    p2.load_state(state)

    # _evolution 恢复 (5 个 snapshot)
    assert len(p2.get_evolution()) == 5
    # _update_count 恢复
    assert p2._update_count == 5
    # _next_snapshot_at 恢复
    assert p2._next_snapshot_at == 6

    # 每个 snapshot 是 POMDPDiagnostic frozen dataclass
    for snap in p2.get_evolution():
        assert snap.schema_version == "0.93.0"


# ---------------------------------------------------------------------------
# 3. 老 v0.92 snapshot raise (1 test)
# ---------------------------------------------------------------------------


def test_load_state_old_v092_raises():
    """老 v0.92 snapshot (schema_version="0.92.0") raise ValueError (防御性自检 [5]).

    v0.93.0-c schema_version 升级, 老 v0.92 不兼容 (per defensive check [5] 严格 raise).
    """
    p = POMDPPolicy(seed=42)
    old_state = {
        "schema_version": "0.92.0",  # v0.93.0-c 之前的 schema
        "n_arms": 10,
        "n_states": 4,
        "n_observations": 4,
        "belief_state": [0.25, 0.25, 0.25, 0.25],
        "transition": np.zeros((4, 4, 10)).tolist(),
        "observation_model": np.zeros((4, 4)).tolist(),
        "reward": [[0.5] * 10] * 4,
        "arm_pull_counts": [0] * 10,
        "total_observations": 0,
    }
    with pytest.raises(ValueError, match=r"schema_version 不匹配"):
        p.load_state(old_state)