"""v0.86.0-c: Thompson Sampling 测试套件.

对应 12-kernel-mapping §1.3 Policy Engine:
    "v0.76.0: 引入 Thompson Sampling (Policy Engine 第二个 Policy)".

测试覆盖:
- ThompsonSampling class (8): init / select_arm / update / update_zero / predict preference / dump_load / get_arm_stats / seed
- LCAPolicyLearner policy_type (4): default_linucb / thompson_select / thompson_update / apply_penalty skip
- PolicyLearner config (2): default_linucb / policy_type propagation
- 向后兼容 (2): linucb_path_unchanged / dump_load_linucb

向后兼容:
- 默认 policy_type="linucb" (v0.82.0-d 兼容)
- 接口同构: select_arm(context) / update(arm, context, reward) 跟 LinUCB 一致
- 防御性自检 [8] 仍 hard block (ThompsonSampling 不 mutate state)
"""

from __future__ import annotations

import numpy as np
import pytest

from ecos.cta.belief_state import BeliefState
from ecos.lca.intervention import Intervention
from ecos.lca.l4_optimization import (
    BanditConfig,
    LCAPolicyLearner,
    ThompsonSampling,
)
from ecos.lca.policy_learner import PolicyLearner, PolicyLearnerConfig


# ────────────────────────────────────────────────────────────────────
# ThompsonSampling (8 tests)
# ────────────────────────────────────────────────────────────────────


def test_thompson_initial_uniform():
    """v0.86.0-c: Thompson 初始 (α=1, β=1) uniform prior."""
    bandit = ThompsonSampling(n_arms=10, seed=42)
    assert bandit.n_arms == 10
    assert np.allclose(bandit.alpha, np.ones(10))
    assert np.allclose(bandit.beta, np.ones(10))
    assert np.all(bandit.arm_pull_counts == 0)


def test_thompson_select_arm_returns_valid_index():
    """select_arm 返 [0, n_arms) 内的整数."""
    bandit = ThompsonSampling(n_arms=5, seed=42)
    arm = bandit.select_arm(context=None)
    assert isinstance(arm, int)
    assert 0 <= arm < 5


def test_thompson_update_increases_alpha():
    """update(arm, reward=1.0) → α += 1, β += 0."""
    bandit = ThompsonSampling(n_arms=3, seed=42)
    initial_alpha = bandit.alpha[0]
    bandit.update(arm=0, context=None, reward=1.0)
    assert bandit.alpha[0] == initial_alpha + 1.0
    assert bandit.beta[0] == 1.0  # β unchanged
    assert bandit.arm_pull_counts[0] == 1


def test_thompson_update_zero_increases_beta():
    """update(arm, reward=0.0) → α += 0, β += 1."""
    bandit = ThompsonSampling(n_arms=3, seed=42)
    initial_beta = bandit.beta[1]
    bandit.update(arm=1, context=None, reward=0.0)
    assert bandit.alpha[1] == 1.0  # α unchanged
    assert bandit.beta[1] == initial_beta + 1.0
    assert bandit.arm_pull_counts[1] == 1


def test_thompson_select_prefers_high_alpha_arm():
    """经过多次 reward=1 update 后, 该 arm 倾向被选."""
    bandit = ThompsonSampling(n_arms=2, seed=42)
    # arm 0 多次 reward=1 → α 高, β 不变
    for _ in range(20):
        bandit.update(arm=0, context=None, reward=1.0)
    # arm 1 多次 reward=0 → β 高, α 不变
    for _ in range(20):
        bandit.update(arm=1, context=None, reward=0.0)

    # 多次 select_arm, arm 0 应该 100% 被选
    counts = {0: 0, 1: 0}
    for _ in range(50):
        arm = bandit.select_arm(context=None)
        counts[arm] += 1
    assert counts[0] >= 45  # 至少 90% 选中 arm 0


def test_thompson_dump_load_state():
    """dump_state + load_state round-trip 一致."""
    bandit = ThompsonSampling(n_arms=5, seed=42)
    bandit.update(arm=0, context=None, reward=1.0)
    bandit.update(arm=1, context=None, reward=0.5)
    bandit.update(arm=2, context=None, reward=0.0)

    state = bandit.dump_state()
    assert "alpha" in state
    assert "beta" in state
    assert "arm_pull_counts" in state
    assert state["n_arms"] == 5

    # 创建新 bandit + load_state
    bandit2 = ThompsonSampling(n_arms=5, seed=99)
    bandit2.load_state(state)
    assert np.allclose(bandit2.alpha, bandit.alpha)
    assert np.allclose(bandit2.beta, bandit.beta)
    assert np.array_equal(bandit2.arm_pull_counts, bandit.arm_pull_counts)


def test_thompson_get_arm_stats():
    """get_arm_stats() 含 8 字段 (跟 LinUCB 接口同构)."""
    bandit = ThompsonSampling(n_arms=3, seed=42)
    bandit.update(arm=0, context=None, reward=1.0)
    bandit.update(arm=0, context=None, reward=0.5)
    stats = bandit.get_arm_stats()
    assert stats["n_arms"] == 3
    assert stats["alpha_prior"] == 1.0
    assert stats["beta_prior"] == 1.0
    assert len(stats["alpha"]) == 3
    assert len(stats["beta"]) == 3
    assert len(stats["arm_pull_counts"]) == 3
    assert stats["total_pulls"] == 2
    assert len(stats["expected_reward"]) == 3
    # arm 0: α=2.5, β=1.5 → expected_reward = 2.5/4.0 = 0.625
    assert abs(stats["expected_reward"][0] - 0.625) < 1e-9


def test_thompson_seed_reproducibility():
    """固定 seed → select_arm 序列可重现."""
    bandit1 = ThompsonSampling(n_arms=5, seed=42)
    bandit2 = ThompsonSampling(n_arms=5, seed=42)
    arms1 = [bandit1.select_arm(context=None) for _ in range(20)]
    arms2 = [bandit2.select_arm(context=None) for _ in range(20)]
    assert arms1 == arms2


# ────────────────────────────────────────────────────────────────────
# LCAPolicyLearner policy_type (4 tests)
# ────────────────────────────────────────────────────────────────────


def _make_intervention(idx: int) -> Intervention:
    """构造 dummy Intervention (测试用)."""
    from ecos.lca.intervention import InterventionType
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


def test_lca_policy_learner_default_linucb():
    """LCAPolicyLearner 默认 policy_type='linucb' (向后兼容)."""
    learner = LCAPolicyLearner(BanditConfig(n_arms=10))
    assert learner.policy_type == "linucb"
    assert learner.thompson is None


def test_lca_policy_learner_thompson_select():
    """policy_type='thompson' → select_intervention 走 Thompson 路径."""
    learner = LCAPolicyLearner(
        BanditConfig(n_arms=5), policy_type="thompson", thompson_seed=42,
    )
    assert learner.policy_type == "thompson"
    assert learner.thompson is not None
    assert learner.thompson.n_arms == 5

    candidates = [_make_intervention(i) for i in range(5)]
    chosen = learner.select_intervention(_make_state(), candidates)
    assert isinstance(chosen, Intervention)
    # Thompson select_arm 返 [0, 5) → idx = arm % 5
    assert chosen.intervention_id.startswith("iv_")


def test_lca_policy_learner_thompson_update():
    """policy_type='thompson' → update 走 Thompson Beta update."""
    learner = LCAPolicyLearner(
        BanditConfig(n_arms=5), policy_type="thompson", thompson_seed=42,
    )
    candidates = [_make_intervention(i) for i in range(5)]
    state = _make_state()
    chosen = learner.select_intervention(state, candidates)

    # update 应走 Thompson Beta update
    learner.update(chosen, state, reward=1.0)
    assert learner.thompson.arm_pull_counts.sum() == 1
    # chosen arm 的 α 增加 1
    chosen_arm = learner._last_arm
    assert learner.thompson.alpha[chosen_arm] == 2.0  # α=1 + 1
    assert learner.thompson.beta[chosen_arm] == 1.0  # β unchanged


def test_lca_policy_learner_apply_penalty_skip_on_thompson():
    """policy_type='thompson' → apply_penalty 跳过 (LinUCB 专属)."""
    learner = LCAPolicyLearner(
        BanditConfig(n_arms=5), policy_type="thompson", thompson_seed=42,
    )
    result = learner.apply_penalty(arm=0, factor=10.0)
    assert result is False  # Thompson 路径不支持
    # penalty_counts 不变
    assert learner._penalty_counts[0] == 0


# ────────────────────────────────────────────────────────────────────
# PolicyLearner config (2 tests)
# ────────────────────────────────────────────────────────────────────


def test_policy_learner_default_linucb_through_config():
    """PolicyLearnerConfig 默认 policy_type='linucb' (向后兼容)."""
    config = PolicyLearnerConfig()
    assert config.policy_type == "linucb"
    assert config.thompson_seed is None


def test_policy_learner_propagates_policy_type_to_learner():
    """PolicyLearner 透传 policy_type 到 LCAPolicyLearner."""
    config = PolicyLearnerConfig(
        policy_type="thompson",
        thompson_seed=42,
    )
    learner = PolicyLearner(config)
    inner = learner._get_learner("lbc_test")
    assert inner.policy_type == "thompson"
    assert inner.thompson is not None
    assert inner.thompson.n_arms == 10  # 默认


# ────────────────────────────────────────────────────────────────────
# 向后兼容 (2 tests)
# ────────────────────────────────────────────────────────────────────


def test_lca_policy_learner_linucb_path_unchanged():
    """默认 LinUCB 路径行为不变 (跟 v0.82.0-d 一致)."""
    learner = LCAPolicyLearner(BanditConfig(n_arms=5))
    candidates = [_make_intervention(i) for i in range(5)]
    state = _make_state()
    chosen = learner.select_intervention(state, candidates)
    assert isinstance(chosen, Intervention)

    # LinUCB arm_pull_counts 不变 (Thompson 不参与)
    initial_linucb_pulls = learner.bandit.arm_pull_counts.sum()
    learner.update(chosen, state, reward=0.5)
    assert learner.bandit.arm_pull_counts.sum() == initial_linucb_pulls + 1


def test_lca_policy_learner_invalid_policy_type_raises():
    """未知 policy_type 抛 ValueError."""
    with pytest.raises(ValueError, match="未知 policy_type"):
        LCAPolicyLearner(BanditConfig(n_arms=5), policy_type="unknown_policy")
