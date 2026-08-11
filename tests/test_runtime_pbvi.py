"""v0.89.0-d: Runtime + PolicyABTest PBVI 集成测试 (10 tests)."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from ecos.lca.l4_optimization import POMDPPolicy
from ecos.lca.l4_optimization.linucb import LinUCB
from ecos.lca.l4_optimization.policy_learner import LCAPolicyLearner
from ecos.lca.l4_optimization.thompson import ThompsonSampling


def _make_state() -> SimpleNamespace:
    return SimpleNamespace(theta_mean=np.zeros(5), bloom_level=1.0)


def _make_iv(idx: int) -> SimpleNamespace:
    return SimpleNamespace(
        intervention_id=f"iv_{idx}",
        difficulty=0.5,
        expected_gain=0.5,
    )


# === 1. LCAPolicyLearner POMDP 默认 use_pbvi=True ===

def test_lca_policy_learner_pomdp_uses_pbvi_by_default():
    learner = LCAPolicyLearner(policy_type="pomdp", pomdp_seed=42)
    assert learner.pomdp is not None
    assert learner.pomdp.use_pbvi is True


def test_lca_policy_learner_pomdp_use_pbvi_false_falls_back_to_qmdp():
    learner = LCAPolicyLearner(policy_type="pomdp", pomdp_seed=42, pomdp_use_pbvi=False)
    assert learner.pomdp.use_pbvi is False
    belief_state = _make_state()
    candidates = [_make_iv(i) for i in range(learner.config.n_arms)]
    chosen = learner.select_intervention(belief_state, candidates)
    assert chosen in candidates


# === 2. LCAPolicyLearner.select_intervention 显式 solve_pbvi ===

def test_lca_policy_learner_select_intervention_triggers_solve_pbvi():
    learner = LCAPolicyLearner(policy_type="pomdp", pomdp_seed=42)
    belief_state = _make_state()
    candidates = [_make_iv(i) for i in range(learner.config.n_arms)]
    assert learner.pomdp.solver is None
    learner.select_intervention(belief_state, candidates)
    assert learner.pomdp.solver is not None
    assert len(learner.pomdp.solver.alpha_vectors) == learner.pomdp.n_arms


def test_lca_policy_learner_solve_pbvi_idempotent_across_calls():
    learner = LCAPolicyLearner(policy_type="pomdp", pomdp_seed=42)
    belief_state = _make_state()
    candidates = [_make_iv(i) for i in range(learner.config.n_arms)]
    learner.select_intervention(belief_state, candidates)
    first = [α.values.tolist() for α in learner.pomdp.solver.alpha_vectors]
    learner.select_intervention(belief_state, candidates)
    second = [α.values.tolist() for α in learner.pomdp.solver.alpha_vectors]
    assert first == second  # 收敛后再次 solve 不变


# === 3. LCAEngine.select_intervention 双层 solve_pbvi 防御 ===

def test_lca_engine_select_intervention_triggers_solve_pbvi():
    from ecos.cta.belief_state import BeliefState
    from ecos.lca.cta_input import CTAInput
    from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig
    from ecos.lca.policy_learner import PolicyLearnerConfig

    cfg = LCAEngineConfig(
        policy_learner_config=PolicyLearnerConfig(
            policy_type="pomdp", pomdp_seed=42, pomdp_use_pbvi=True,
        ),
    )
    engine = LCAEngine(config=cfg)
    student_id = "lca_pbvi_d_001"
    belief_state = BeliefState(student_id=student_id)
    cta_input = CTAInput(student_id=student_id, belief_state=belief_state)
    engine.select_intervention(cta_input)
    learner = engine.policy_learner._get_learner(student_id)
    assert learner.pomdp.solver is not None
    assert len(learner.pomdp.solver.alpha_vectors) == learner.pomdp.n_arms


# === 4. PolicyABTest 工厂 + 3-way A/B ===

def test_policy_ab_test_factory_pomdp_uses_pbvi():
    from ecos.evaluation.policy_ab_test import PolicyABTest

    bandit = PolicyABTest._create_fresh_bandit("pomdp")
    assert isinstance(bandit, POMDPPolicy)
    assert bandit.use_pbvi is True


def test_policy_ab_test_3_way_a_b_with_pbvi():
    from ecos.evaluation.policy_ab_test import PolicyABTest

    ab = PolicyABTest()
    events = [
        SimpleNamespace(payload={"score": 0.6}),
        SimpleNamespace(payload={"score": 0.7}),
        SimpleNamespace(payload={"score": 0.5}),
        SimpleNamespace(payload={"score": 0.8}),
        SimpleNamespace(payload={"score": 0.65}),
    ]
    res = ab.compare("s_3way", "thompson", "pomdp", events=events)
    assert res.n_a >= 5 and res.n_b >= 5
    assert res.policy_a == "thompson"
    assert res.policy_b == "pomdp"
    assert res.winner in ("a", "b", None)


# === 5. PBVI α-vector 持久化 replay canary ===

def test_pbvi_replay_canary_dump_load_state():
    policy = POMDPPolicy(n_arms=4, n_states=2, seed=42)
    policy.solve_pbvi()
    state = policy.dump_state()
    restored = POMDPPolicy(n_arms=4, n_states=2, seed=99)
    restored.load_state(state)
    belief = np.array([0.5, 0.5])
    assert (
        policy.solver.best_action(belief) == restored.solver.best_action(belief)
    )


# === 6. PBVI solve 失败 fallback ===

def test_pbvi_solve_failure_falls_back_to_qmdp(monkeypatch):
    from ecos.lca.l4_optimization import pomdp as pomdp_mod

    def _boom(self):
        raise RuntimeError("simulated PBVI failure")

    monkeypatch.setattr(POMDPPolicy, "solve_pbvi", _boom)
    policy = POMDPPolicy(n_arms=4, n_states=2, seed=42)
    expected = int(np.argmax(policy.belief_state @ policy.reward))
    assert policy.select_arm() == expected


# === 7. H3-c4 canary: PBVI 同 seed 确定性 ===

def test_pbvi_deterministic_with_seed():
    p1 = POMDPPolicy(n_arms=4, n_states=2, seed=42, pbvi_seed=7)
    p2 = POMDPPolicy(n_arms=4, n_states=2, seed=42, pbvi_seed=7)
    p1.solve_pbvi()
    p2.solve_pbvi()
    belief = np.array([0.25, 0.75])
    assert p1.solver.best_action(belief) == p2.solver.best_action(belief)


# === 8. PBVI solver 真实暴露 best_action_via_solver (测试 helper) ===

def test_pbvi_solver_best_action_helper():
    from ecos.lca.l4_optimization.pomdp_solver import PBVI, reachable_belief_points

    policy = POMDPPolicy(n_arms=4, n_states=2, seed=42)
    belief_points = reachable_belief_points(
        policy.transition, policy.observation_model, policy.belief_state,
        n_steps=2, n_samples_per_step=2, seed=42,
    )
    solver = PBVI(belief_points=belief_points, n_iters=5)
    solver.solve(policy.transition, policy.observation_model, policy.reward)
    assert 0 <= solver.best_action(np.array([0.5, 0.5])) < 4
