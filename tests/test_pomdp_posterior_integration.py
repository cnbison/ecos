"""v0.90.0-b: POMDPPolicy 后验注入 + 持久化 + schema_version 升级测试.

对应设计: discussions/2026-08-12-v090-design.md §3.

测试范围:
  1. set_*_posterior 注入 (3 tests): transition / reward / posterior 引用保留
  2. _learned_t_r_posterior_mean 派生 (3 tests): 返回 None / mean shape / count=0+alpha=beta=1 → 0.5
  3. dump_state + load_state posterior 字段 (3 tests): round-trip / shape 校验 / 老 v0.89.0-c raise
  4. 老 v0.89.0-c snapshot raise + 防御性 (3 tests): schema_version 校验 / posterior shape mismatch
"""

from __future__ import annotations

import numpy as np
import pytest

from ecos.lca.l4_optimization.pomdp import POMDPPolicy, SCHEMA_VERSION
from ecos.lca.l4_optimization.pomdp_learner import (
    RewardPosterior,
    TransitionPosterior,
)


# ---------------------------------------------------------------------------
# 1. set_*_posterior 注入 (3 tests)
# ---------------------------------------------------------------------------


def test_set_transition_posterior_lazy_inject():
    """set_transition_posterior 注入后 _transition_posterior 引用保留."""
    p = POMDPPolicy(seed=42)
    assert p._transition_posterior is None
    tp = TransitionPosterior(count=np.zeros((4, 4, 10), dtype=int))
    p.set_transition_posterior(tp)
    assert p._transition_posterior is tp


def test_set_reward_posterior_lazy_inject():
    """set_reward_posterior 注入后 _reward_posterior 引用保留."""
    p = POMDPPolicy(seed=42)
    assert p._reward_posterior is None
    rp = RewardPosterior(
        alpha=np.ones((4, 10), dtype=float),
        beta=np.ones((4, 10), dtype=float),
    )
    p.set_reward_posterior(rp)
    assert p._reward_posterior is rp


def test_set_posteriors_does_not_mutate_self_transition_reward():
    """set_*_posterior 注入不 mutate self.transition / self.reward (c 阶段才替换)."""
    p = POMDPPolicy(seed=42)
    T_before = p.transition.copy()
    R_before = p.reward.copy()
    tp = TransitionPosterior(count=np.full((4, 4, 10), 5, dtype=int))
    rp = RewardPosterior(
        alpha=np.full((4, 10), 3.0),
        beta=np.full((4, 10), 1.0),
    )
    p.set_transition_posterior(tp)
    p.set_reward_posterior(rp)
    # self.transition / self.reward 仍 init 值 (c 阶段 PBVI 才消费 posterior mean)
    assert np.array_equal(p.transition, T_before)
    assert np.array_equal(p.reward, R_before)


# ---------------------------------------------------------------------------
# 2. _learned_t_r_posterior_mean 派生 (3 tests)
# ---------------------------------------------------------------------------


def test_learned_t_r_posterior_mean_returns_none_when_not_set():
    """posterior 未注入 → _learned_t_r_posterior_mean() 返 None."""
    p = POMDPPolicy(seed=42)
    assert p._learned_t_r_posterior_mean() is None


def test_learned_t_r_posterior_mean_shape_matches():
    """posterior 注入后 mean shape 跟 self.transition / self.reward 对齐."""
    p = POMDPPolicy(seed=42)
    tp = TransitionPosterior(count=np.zeros((4, 4, 10), dtype=int))
    rp = RewardPosterior(
        alpha=np.ones((4, 10), dtype=float),
        beta=np.ones((4, 10), dtype=float),
    )
    p.set_transition_posterior(tp)
    p.set_reward_posterior(rp)
    T_mean, R_mean = p._learned_t_r_posterior_mean()
    assert T_mean.shape == (4, 4, 10)
    assert R_mean.shape == (4, 10)


def test_learned_t_r_posterior_mean_uniform_prior():
    """count=0 + alpha=beta=1 (uniform prior) → R_mean = 0.5, T_mean 均匀."""
    p = POMDPPolicy(seed=42)
    tp = TransitionPosterior(count=np.zeros((4, 4, 10), dtype=int))
    rp = RewardPosterior(
        alpha=np.ones((4, 10), dtype=float),
        beta=np.ones((4, 10), dtype=float),
    )
    p.set_transition_posterior(tp)
    p.set_reward_posterior(rp)
    T_mean, R_mean = p._learned_t_r_posterior_mean()
    # R_mean 全 0.5 (uniform prior Beta(1, 1))
    assert np.allclose(R_mean, 0.5)
    # T_mean 全 1/4 (uniform prior)
    assert np.allclose(T_mean, 1.0 / 4.0)


# ---------------------------------------------------------------------------
# 3. dump_state + load_state posterior 字段 (3 tests)
# ---------------------------------------------------------------------------


def test_dump_state_includes_posterior_fields_when_injected():
    """posterior 注入后 dump_state 含 transition_count / reward_alpha / reward_beta."""
    p = POMDPPolicy(seed=42)
    count = np.full((4, 4, 10), 3, dtype=int)
    alpha = np.full((4, 10), 2.5)
    beta = np.full((4, 10), 1.5)
    p.set_transition_posterior(TransitionPosterior(count=count.copy()))
    p.set_reward_posterior(RewardPosterior(alpha=alpha.copy(), beta=beta.copy()))
    state = p.dump_state()
    assert state["schema_version"] == "0.90.0"
    assert state["transition_count"] is not None
    assert state["reward_alpha"] is not None
    assert state["reward_beta"] is not None
    assert np.array_equal(np.array(state["transition_count"]), count)
    assert np.array_equal(np.array(state["reward_alpha"]), alpha)
    assert np.array_equal(np.array(state["reward_beta"]), beta)


def test_dump_state_posterior_none_when_not_injected():
    """posterior 未注入 → dump_state posterior 字段全 None (向后兼容 c 阶段 lazy)."""
    p = POMDPPolicy(seed=42)
    state = p.dump_state()
    assert state["schema_version"] == "0.90.0"
    assert state["transition_count"] is None
    assert state["reward_alpha"] is None
    assert state["reward_beta"] is None


def test_dump_load_state_round_trip_with_posterior():
    """dump_state + load_state round-trip 保留 posterior."""
    p1 = POMDPPolicy(seed=42)
    count = np.full((4, 4, 10), 7, dtype=int)
    alpha = np.full((4, 10), 4.0)
    beta = np.full((4, 10), 2.0)
    p1.set_transition_posterior(TransitionPosterior(count=count.copy()))
    p1.set_reward_posterior(RewardPosterior(alpha=alpha.copy(), beta=beta.copy()))
    state = p1.dump_state()
    # 在新实例上 load
    p2 = POMDPPolicy(seed=42)
    p2.load_state(state)
    assert p2._transition_posterior is not None
    assert p2._reward_posterior is not None
    assert np.array_equal(p2._transition_posterior.count, count)
    assert np.array_equal(p2._reward_posterior.alpha, alpha)
    assert np.array_equal(p2._reward_posterior.beta, beta)


# ---------------------------------------------------------------------------
# 4. 老 v0.89.0-c snapshot raise + 防御性 (3 tests)
# ---------------------------------------------------------------------------


def test_load_state_raises_on_old_v089_c_schema():
    """老 v0.89.0-c snapshot (schema_version 不匹配) raise ValueError."""
    p = POMDPPolicy(seed=42)
    old_state = {
        "schema_version": "0.89.0-c",
        "n_arms": 10,
        "n_states": 4,
        "n_observations": 4,
        "belief_state": [0.25, 0.25, 0.25, 0.25],
        "transition": np.zeros((4, 4, 10)).tolist(),
        "observation_model": np.zeros((4, 4)).tolist(),
        "reward": np.zeros((4, 10)).tolist(),
    }
    with pytest.raises(ValueError, match=r"schema_version 不匹配"):
        p.load_state(old_state)


def test_load_state_raises_on_old_v088_c_schema():
    """老 v0.88.0-c snapshot raise ValueError (per 防御性自检 [5])."""
    p = POMDPPolicy(seed=42)
    old_state = {
        "schema_version": "0.88.0-c",
        "n_arms": 10,
        "n_states": 4,
        "n_observations": 4,
        "belief_state": [0.25, 0.25, 0.25, 0.25],
        "transition": np.zeros((4, 4, 10)).tolist(),
        "observation_model": np.zeros((4, 4)).tolist(),
        "reward": np.zeros((4, 10)).tolist(),
    }
    with pytest.raises(ValueError, match=r"schema_version 不匹配"):
        p.load_state(old_state)


def test_learned_t_r_posterior_mean_shape_mismatch_raises():
    """posterior.n_states 跟 POMDPPolicy 不匹配 → raise ValueError."""
    p = POMDPPolicy(seed=42)
    # n_states=3 不匹配 self.n_states=4
    tp = TransitionPosterior(count=np.zeros((3, 3, 10), dtype=int))
    p.set_transition_posterior(tp)
    rp = RewardPosterior(
        alpha=np.ones((4, 10), dtype=float),
        beta=np.ones((4, 10), dtype=float),
    )
    p.set_reward_posterior(rp)
    with pytest.raises(ValueError, match=r"TransitionPosterior shape 跟 POMDPPolicy 不匹配"):
        p._learned_t_r_posterior_mean()


def test_load_state_inconsistent_posterior_alpha_beta_raises():
    """reward_alpha 非 None + reward_beta None → raise (不一致, 防御性)."""
    p = POMDPPolicy(seed=42)
    state = p.dump_state()
    # 改 dump 出来的 state: 把 reward_alpha 设为 valid, reward_beta 设为 None
    state["reward_alpha"] = np.ones((4, 10), dtype=float).tolist()
    state["reward_beta"] = None
    with pytest.raises(ValueError, match=r"reward_alpha / reward_beta 必须同时"):
        p.load_state(state)