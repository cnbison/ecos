"""v0.90.0-d: Runtime + PolicyABTest + 冷启动测试.

对应设计: discussions/2026-08-12-v090-design.md §5.

测试范围:
  1. LCAEngine.update 透传 observation → POMDPPolicy.update 收 obs + _update_t_r (3 tests)
  2. PolicyLearnerConfig.pomdp_use_learned_t_r 透传到 POMDPPolicy (2 tests)
  3. PolicyABTest 工厂 use_learned_t_r=True + 真 3-way A/B (2 tests)
  4. min_samples 切换 (证据 < 5 用 init, ≥ 5 切 learned) (2 tests)
  5. H3-c4 canary (POMDP 同 seed 确定性 + learned T/R 同分布) (1 test)
"""

from __future__ import annotations

import numpy as np
import pytest

from ecos.evaluation.policy_ab_test import PolicyABTest
from ecos.lca.l4_optimization import POMDPPolicy
from ecos.lca.l4_optimization.pomdp_learner import (
    RewardPosterior,
    TransitionPosterior,
)
from ecos.lca.policy_learner import PolicyLearner, PolicyLearnerConfig


# ---------------------------------------------------------------------------
# 1. LCAEngine.update 透传 observation → POMDPPolicy.update (3 tests)
# ---------------------------------------------------------------------------


def test_policy_learner_update_passes_observation_to_pomdp():
    """PolicyLearner.update 透传 observation 到 POMDPPolicy.update (触发 _update_t_r)."""
    cfg = PolicyLearnerConfig(
        policy_type="pomdp",
        pomdp_seed=42,
        pomdp_use_learned_t_r=True,
    )
    pl = PolicyLearner(cfg)
    # 先 select_intervention 注册 arm 索引 (否则 update 反查 arm 失败)
    intervention_list = [
        type("I", (), {"intervention_id": f"int-{i}"})()
        for i in range(10)
    ]
    learner = pl._get_learner("lbc001")
    chosen = learner.select_intervention(belief_state=None, candidate_interventions=intervention_list)
    # 注入 belief_state (POMDP non-contextual, 可 None)
    pl.update("lbc001", chosen, None, reward=0.7, observation=2)
    # posterior 应被 lazy 创建
    assert learner.pomdp._transition_posterior is not None
    assert learner.pomdp._reward_posterior is not None


def test_policy_learner_update_without_observation_does_not_create_posterior():
    """PolicyLearner.update(obs=None) → POMDPPolicy.update 不触发 _update_t_r."""
    cfg = PolicyLearnerConfig(
        policy_type="pomdp",
        pomdp_seed=42,
    )
    pl = PolicyLearner(cfg)
    intervention_list = [
        type("I", (), {"intervention_id": f"int-{i}"})()
        for i in range(10)
    ]
    learner = pl._get_learner("lbc001")
    chosen = learner.select_intervention(belief_state=None, candidate_interventions=intervention_list)
    pl.update("lbc001", chosen, None, reward=0.7, observation=None)
    assert learner.pomdp._transition_posterior is None
    assert learner.pomdp._reward_posterior is None


def test_policy_learner_pomdp_use_learned_t_r_defaults_true():
    """PolicyLearnerConfig.pomdp_use_learned_t_r=None → POMDPPolicy use_learned_t_r=True."""
    cfg = PolicyLearnerConfig(policy_type="pomdp", pomdp_seed=42)
    pl = PolicyLearner(cfg)
    learner = pl._get_learner("lbc001")
    assert learner.pomdp.use_learned_t_r is True


# ---------------------------------------------------------------------------
# 2. PolicyLearnerConfig.pomdp_use_learned_t_r 透传到 POMDPPolicy (2 tests)
# ---------------------------------------------------------------------------


def test_policy_learner_passes_use_learned_t_r_false():
    """PolicyLearnerConfig.pomdp_use_learned_t_r=False → POMDPPolicy use_learned_t_r=False."""
    cfg = PolicyLearnerConfig(
        policy_type="pomdp",
        pomdp_seed=42,
        pomdp_use_learned_t_r=False,
    )
    pl = PolicyLearner(cfg)
    learner = pl._get_learner("lbc001")
    assert learner.pomdp.use_learned_t_r is False


def test_policy_learner_passes_use_learned_t_r_true():
    """PolicyLearnerConfig.pomdp_use_learned_t_r=True → POMDPPolicy use_learned_t_r=True."""
    cfg = PolicyLearnerConfig(
        policy_type="pomdp",
        pomdp_seed=42,
        pomdp_use_learned_t_r=True,
    )
    pl = PolicyLearner(cfg)
    learner = pl._get_learner("lbc001")
    assert learner.pomdp.use_learned_t_r is True


# ---------------------------------------------------------------------------
# 3. PolicyABTest 工厂 use_learned_t_r=True + 真 3-way A/B (2 tests)
# ---------------------------------------------------------------------------


def test_policy_ab_test_pomdp_factory_uses_learned_t_r():
    """PolicyABTest._create_fresh_bandit POMDP 工厂 use_learned_t_r=True + min_samples=5."""
    p = PolicyABTest._create_fresh_bandit("pomdp")
    assert p.use_learned_t_r is True
    assert p.min_samples == 5


def test_policy_ab_test_3_way_with_learned_t_r_runs():
    """真 3-way A/B (linucb / thompson / pomdp+PBVI+learned T/R) 仍可运行."""
    import numpy as np
    p1 = PolicyABTest._create_fresh_bandit("linucb")
    p2 = PolicyABTest._create_fresh_bandit("thompson")
    p3 = PolicyABTest._create_fresh_bandit("pomdp")
    # 各自 select_arm 返回有效 arm 索引 (LinUCB 需要 16 维 context)
    ctx16 = np.zeros(16, dtype=float)
    for bandit, name, ctx in [
        (p1, "linucb", ctx16),
        (p2, "thompson", None),
        (p3, "pomdp", None),
    ]:
        arm = bandit.select_arm(context=ctx)
        assert 0 <= arm < 10, f"{name} select_arm 返 {arm}"


# ---------------------------------------------------------------------------
# 4. min_samples 切换 (证据 < 5 用 init, ≥ 5 切 learned) (2 tests)
# ---------------------------------------------------------------------------


def test_min_samples_uses_init_below_threshold():
    """min_samples=5 + evidence < 5 → _resolve_t_r 走 init T/R."""
    p = POMDPPolicy(seed=42, use_learned_t_r=True, min_samples=5)
    # 注入 posterior (仅 1 个 evidence, < min_samples=5)
    p.set_transition_posterior(TransitionPosterior(count=np.zeros((4, 4, 10), dtype=int)))
    p.set_reward_posterior(
        RewardPosterior(
            alpha=np.ones((4, 10), dtype=float),
            beta=np.ones((4, 10), dtype=float),
        )
    )
    p._transition_posterior.update(0, 0, 0)  # 1 evidence
    p._reward_posterior.update(0, 0, 1.0)
    assert p._transition_posterior.total_evidence() == 1
    T, R = p._resolve_t_r()
    # evidence=1 < min_samples=5 → 走 init
    assert T is p.transition
    assert R is p.reward


def test_min_samples_uses_learned_above_threshold():
    """min_samples=5 + evidence ≥ 5 → _resolve_t_r 走 posterior mean."""
    p = POMDPPolicy(seed=42, use_learned_t_r=True, min_samples=5)
    # 注入 posterior (≥ 5 evidence)
    p.set_transition_posterior(TransitionPosterior(count=np.zeros((4, 4, 10), dtype=int)))
    p.set_reward_posterior(
        RewardPosterior(
            alpha=np.ones((4, 10), dtype=float),
            beta=np.ones((4, 10), dtype=float),
        )
    )
    for _ in range(5):
        p._transition_posterior.update(0, 0, 0)
        p._reward_posterior.update(0, 0, 1.0)
    assert p._transition_posterior.total_evidence() == 5
    assert p._reward_posterior.total_evidence() == 5
    T, R = p._resolve_t_r()
    # evidence=5 ≥ min_samples=5 → 走 learned
    assert T is not p.transition
    assert R is not p.reward


# ---------------------------------------------------------------------------
# 5. H3-c4 canary (POMDP 同 seed 确定性) (1 test)
# ---------------------------------------------------------------------------


def test_pomdp_deterministic_with_seed_learned_t_r():
    """H3-c4 canary: POMDP 同 seed 返同 action (PBVI + learned T/R 同分布)."""
    p1 = POMDPPolicy(seed=42, use_learned_t_r=True, min_samples=0)
    p2 = POMDPPolicy(seed=42, use_learned_t_r=True, min_samples=0)
    # 学相同的 evidence
    for _ in range(3):
        p1.update(arm=0, reward=1.0, observation=0)
        p2.update(arm=0, reward=1.0, observation=0)
    arm1 = p1.select_arm()
    arm2 = p2.select_arm()
    assert arm1 == arm2