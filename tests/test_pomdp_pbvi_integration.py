"""v0.89.0-c: POMDPPolicy 与 PBVI 集成测试."""

from __future__ import annotations

import copy

import numpy as np
import pytest

from ecos.lca.l4_optimization import POMDPPolicy
from ecos.lca.l4_optimization.pomdp import SCHEMA_VERSION
from ecos.lca.l4_optimization.pomdp_solver import PBVI


def test_use_pbvi_default_true():
    policy = POMDPPolicy(n_arms=4, n_states=2, seed=42)
    assert policy.use_pbvi is True
    assert policy.solver is None


def test_use_pbvi_false_falls_back_to_qmdp():
    policy = POMDPPolicy(n_arms=4, n_states=2, seed=42, use_pbvi=False)
    expected = int(np.argmax(policy.belief_state @ policy.reward))
    assert policy.select_arm() == expected
    assert policy.solver is None


def test_select_arm_uses_pbvi_when_enabled():
    policy = POMDPPolicy(n_arms=4, n_states=2, seed=42, use_pbvi=True)
    action = policy.select_arm()
    assert 0 <= action < policy.n_arms
    assert policy.solver is not None
    assert policy.solver.alpha_vectors


def test_init_pbvi_solver_is_lazy():
    policy = POMDPPolicy(n_arms=4, n_states=2, seed=42)
    assert policy.solver is None
    solver = policy._init_pbvi_solver()
    assert isinstance(solver, PBVI)


def test_init_pbvi_solver_returns_cached_after_first_call():
    policy = POMDPPolicy(n_arms=4, n_states=2, seed=42)
    first = policy._init_pbvi_solver()
    second = policy._init_pbvi_solver()
    assert first is second


def test_solve_pbvi_returns_iteration_count():
    policy = POMDPPolicy(n_arms=4, n_states=2, seed=42, pbvi_n_iters=3)
    iterations = policy.solve_pbvi()
    assert 1 <= iterations <= 3
    assert policy.solver is not None
    assert len(policy.solver.alpha_vectors) == policy.n_arms


def test_dump_state_includes_pbvi_fields():
    policy = POMDPPolicy(n_arms=4, n_states=2, seed=42)
    state = policy.dump_state()
    assert state["schema_version"] == SCHEMA_VERSION
    assert state["use_pbvi"] is True
    assert set(state["pbvi_config"]) == {
        "gamma", "epsilon", "n_iters", "n_belief_points"
    }
    assert state["solver_state"] is None


def test_load_state_restores_use_pbvi_and_pbvi_config():
    policy = POMDPPolicy(
        n_arms=4, n_states=2, seed=42, use_pbvi=False,
        pbvi_gamma=0.7, pbvi_epsilon=1e-3, pbvi_n_iters=7,
        pbvi_n_belief_points=8,
    )
    state = policy.dump_state()
    restored = POMDPPolicy(n_arms=4, n_states=2, seed=99)
    restored.load_state(state)
    assert restored.use_pbvi is False
    assert restored.pbvi_gamma == 0.7
    assert restored.pbvi_epsilon == 1e-3
    assert restored.pbvi_n_iters == 7
    assert restored.pbvi_n_belief_points == 8


def test_load_state_restores_solver_state():
    original = POMDPPolicy(n_arms=4, n_states=2, seed=42)
    original.solve_pbvi()
    state = original.dump_state()
    restored = POMDPPolicy(n_arms=4, n_states=2, seed=99)
    restored.load_state(state)
    assert restored.solver is not None
    assert len(restored.solver.alpha_vectors) == len(original.solver.alpha_vectors)
    for expected, actual in zip(original.solver.alpha_vectors, restored.solver.alpha_vectors):
        assert expected.action == actual.action
        assert np.array_equal(expected.values, actual.values)
    for expected, actual in zip(original.solver.belief_points, restored.solver.belief_points):
        assert np.array_equal(expected, actual)


def test_load_state_rejects_v088_schema():
    policy = POMDPPolicy(n_arms=4, n_states=2, seed=42)
    state = copy.deepcopy(policy.dump_state())
    state["schema_version"] = "0.88.0-c"
    with pytest.raises(ValueError, match="schema_version"):
        policy.load_state(state)
