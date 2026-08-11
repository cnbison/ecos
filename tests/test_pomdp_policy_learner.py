"""v0.87.0-d: POMDP 集成 PolicyLearner + 真 A/B 3-policy 测试套件.

对应 12-kernel-mapping §1.3 Policy Engine (3-way A/B Test).

测试覆盖:
- LCAPolicyLearner POMDP (4): default_no_pomdp / pomdp_select / pomdp_update / apply_penalty_skip
- PolicyLearner config (3): default_no_pomdp / pomdp_seed_propagation / invalid_policy_type
- PolicyABTest 3-policy (4): pomdp_create_fresh / compare_linucb_vs_pomdp / compare_thompson_vs_pomdp / 3-way
- 集成 (3): LinUCB unchanged / Thompson unchanged / POMDP new

向后兼容:
- 默认 policy_type="linucb" (v0.86.0-d 兼容)
- LCAPolicyLearner pomdp 路径接口同 LinUCB/Thompson
- PolicyABTest 3-way A/B test 5% winner threshold
- 防御性自检 [8] 仍 hard block
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pytest

from ecos.cta.belief_state import BeliefState
from ecos.cta.event_log import LearningEvent
from ecos.evaluation.policy_ab_test import ABTestResult, PolicyABTest
from ecos.lca.intervention import Intervention, InterventionType
from ecos.lca.l4_optimization import (
    BanditConfig,
    LCAPolicyLearner,
    POMDPPolicy,
    ThompsonSampling,
)
from ecos.lca.policy_learner import PolicyLearner, PolicyLearnerConfig


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────


def _make_intervention(idx: int) -> Intervention:
    """构造 dummy Intervention (测试用)."""
    from ecos.cta.belief_state import BloomLevel
    return Intervention(
        intervention_id=f"iv_{idx}",
        intervention_type=InterventionType.FEEDBACK,
        bloom_target=BloomLevel.APPLY,
        difficulty=0.5,
        scaffolding_level=1,
    )


def _make_state() -> BeliefState:
    return BeliefState(student_id="lbc_test")


def _make_event(student_id: str, score: float) -> LearningEvent:
    return LearningEvent(
        event_id=f"evt_{student_id}_{score}",
        student_id=student_id,
        timestamp=datetime.now(),
        source="test",
        event_type="response_submitted",
        payload={"score": score, "correct": score >= 0.7},
    )


# ────────────────────────────────────────────────────────────────────
# LCAPolicyLearner POMDP (4 tests)
# ────────────────────────────────────────────────────────────────────


def test_lca_policy_learner_default_no_pomdp():
    """LCAPolicyLearner 默认 policy_type='linucb' (v0.86.0-d 兼容)."""
    learner = LCAPolicyLearner(BanditConfig(n_arms=10))
    assert learner.policy_type == "linucb"
    assert learner.pomdp is None
    assert learner.thompson is None


def test_lca_policy_learner_pomdp_select():
    """policy_type='pomdp' → select_intervention 走 POMDP 路径."""
    learner = LCAPolicyLearner(
        BanditConfig(n_arms=5), policy_type="pomdp", pomdp_seed=42,
    )
    assert learner.policy_type == "pomdp"
    assert learner.pomdp is not None
    assert isinstance(learner.pomdp, POMDPPolicy)
    assert learner.pomdp.n_arms == 5

    candidates = [_make_intervention(i) for i in range(5)]
    chosen = learner.select_intervention(_make_state(), candidates)
    assert isinstance(chosen, Intervention)


def test_lca_policy_learner_pomdp_update():
    """policy_type='pomdp' → update 走 POMDP 简化 update (追踪 arm_pull_counts)."""
    learner = LCAPolicyLearner(
        BanditConfig(n_arms=5), policy_type="pomdp", pomdp_seed=42,
    )
    candidates = [_make_intervention(i) for i in range(5)]
    state = _make_state()
    chosen = learner.select_intervention(state, candidates)

    # update 应走 POMDP 简化 update
    learner.update(chosen, state, reward=0.7)
    assert learner.pomdp.arm_pull_counts.sum() == 1
    # chosen arm 的 arm_pull_counts 增加 1
    chosen_arm = learner._last_arm
    assert learner.pomdp.arm_pull_counts[chosen_arm] == 1


def test_lca_policy_learner_apply_penalty_skip_on_pomdp():
    """policy_type='pomdp' → apply_penalty 跳过 (LinUCB 专属)."""
    learner = LCAPolicyLearner(
        BanditConfig(n_arms=5), policy_type="pomdp", pomdp_seed=42,
    )
    result = learner.apply_penalty(arm=0, factor=10.0)
    assert result is False
    # penalty_counts 不变
    assert learner._penalty_counts[0] == 0


# ────────────────────────────────────────────────────────────────────
# PolicyLearner config (3 tests)
# ────────────────────────────────────────────────────────────────────


def test_policy_learner_default_no_pomdp():
    """PolicyLearnerConfig 默认 pomdp_seed=None."""
    config = PolicyLearnerConfig()
    assert config.pomdp_seed is None
    assert config.thompson_seed is None
    assert config.policy_type == "linucb"


def test_policy_learner_propagates_pomdp_seed_to_learner():
    """PolicyLearner 透传 pomdp_seed 到 LCAPolicyLearner."""
    config = PolicyLearnerConfig(
        policy_type="pomdp",
        pomdp_seed=42,
    )
    learner = PolicyLearner(config)
    inner = learner._get_learner("lbc_test")
    assert inner.policy_type == "pomdp"
    assert inner.pomdp is not None
    assert inner.pomdp.n_arms == 10  # 默认


def test_policy_learner_invalid_policy_type_raises():
    """未知 policy_type 抛 ValueError (4 值校验: linucb/thompson/pomdp)."""
    with pytest.raises(ValueError, match="未知 policy_type"):
        LCAPolicyLearner(BanditConfig(n_arms=5), policy_type="unknown_policy")
    with pytest.raises(ValueError, match="未知 policy_type"):
        LCAPolicyLearner(BanditConfig(n_arms=5), policy_type="e_greedy")  # 不支持


# ────────────────────────────────────────────────────────────────────
# PolicyABTest 3-policy (4 tests)
# ────────────────────────────────────────────────────────────────────


def test_policy_ab_test_pomdp_create_fresh():
    """v0.87.0-d: PolicyABTest._create_fresh_bandit('pomdp') → POMDPPolicy 实例."""
    bandit = PolicyABTest._create_fresh_bandit("pomdp")
    assert isinstance(bandit, POMDPPolicy)
    assert bandit.n_arms == 10
    assert bandit.n_states == 4


def test_policy_ab_test_compare_linucb_vs_pomdp():
    """v0.87.0-d: 真 A/B Test 支持 linucb vs pomdp."""
    ab = PolicyABTest()
    events = [_make_event("lbc_test", 0.7) for _ in range(10)]
    result = ab.compare("lbc_test", "linucb", "pomdp", events=events)
    assert isinstance(result, ABTestResult)
    assert result.n_a == 10
    assert result.n_b == 10
    # mean_reward 都是 0.7 (所有 event score=0.7)
    assert abs(result.mean_reward_a - 0.7) < 1e-9
    assert abs(result.mean_reward_b - 0.7) < 1e-9


def test_policy_ab_test_compare_thompson_vs_pomdp():
    """v0.87.0-d: 真 A/B Test 支持 thompson vs pomdp."""
    ab = PolicyABTest()
    events = [_make_event("lbc_test", 0.5) for _ in range(20)]
    result = ab.compare("lbc_test", "thompson", "pomdp", events=events)
    assert isinstance(result, ABTestResult)
    assert result.n_a == 20
    assert result.n_b == 20
    # mean_reward 都是 0.5
    assert abs(result.mean_reward_a - 0.5) < 1e-9
    assert abs(result.mean_reward_b - 0.5) < 1e-9


def test_policy_ab_test_3_way_a_b_works():
    """v0.87.0-d: 3-way A/B test (linucb / thompson / pomdp) 全部支持."""
    ab = PolicyABTest()
    events = [_make_event("lbc_test", 0.6) for _ in range(8)]

    # linucb vs thompson
    r1 = ab.compare("lbc_test", "linucb", "thompson", events=events)
    # linucb vs pomdp
    r2 = ab.compare("lbc_test", "linucb", "pomdp", events=events)
    # thompson vs pomdp
    r3 = ab.compare("lbc_test", "thompson", "pomdp", events=events)
    assert r1.n_a == 8 and r1.n_b == 8
    assert r2.n_a == 8 and r2.n_b == 8
    assert r3.n_a == 8 and r3.n_b == 8


# ────────────────────────────────────────────────────────────────────
# 集成 (3 tests)
# ────────────────────────────────────────────────────────────────────


def test_lca_policy_learner_linucb_path_unchanged():
    """默认 LinUCB 路径行为不变 (v0.86.0-d 兼容)."""
    learner = LCAPolicyLearner(BanditConfig(n_arms=5))
    candidates = [_make_intervention(i) for i in range(5)]
    state = _make_state()
    chosen = learner.select_intervention(state, candidates)
    assert isinstance(chosen, Intervention)

    initial_pulls = learner.bandit.arm_pull_counts.sum()
    learner.update(chosen, state, reward=0.5)
    # LinUCB arm_pull_counts 增 1, Thompson / POMDP 都不参与
    assert learner.bandit.arm_pull_counts.sum() == initial_pulls + 1
    assert learner.thompson is None
    assert learner.pomdp is None


def test_lca_policy_learner_thompson_path_unchanged():
    """Thompson 路径行为不变 (v0.86.0-c 兼容)."""
    learner = LCAPolicyLearner(
        BanditConfig(n_arms=5), policy_type="thompson", thompson_seed=42,
    )
    candidates = [_make_intervention(i) for i in range(5)]
    state = _make_state()
    chosen = learner.select_intervention(state, candidates)

    learner.update(chosen, state, reward=0.5)
    assert learner.thompson.arm_pull_counts.sum() == 1
    assert learner.pomdp is None


def test_lca_policy_learner_pomdp_new_path():
    """POMDP 新路径生效 (跟 LinUCB/Thompson 完全独立)."""
    learner_pomdp = LCAPolicyLearner(
        BanditConfig(n_arms=5), policy_type="pomdp", pomdp_seed=42,
    )
    learner_linucb = LCAPolicyLearner(BanditConfig(n_arms=5))

    candidates = [_make_intervention(i) for i in range(5)]
    state = _make_state()

    chosen_pomdp = learner_pomdp.select_intervention(state, candidates)
    chosen_linucb = learner_linucb.select_intervention(state, candidates)
    # 都返回 Intervention (具体选哪个 arm 不同, 但接口一致)
    assert isinstance(chosen_pomdp, Intervention)
    assert isinstance(chosen_linucb, Intervention)

    # update 走各自路径
    learner_pomdp.update(chosen_pomdp, state, reward=0.5)
    learner_linucb.update(chosen_linucb, state, reward=0.5)
    assert learner_pomdp.pomdp.arm_pull_counts.sum() == 1
    assert learner_linucb.bandit.arm_pull_counts.sum() == 1
