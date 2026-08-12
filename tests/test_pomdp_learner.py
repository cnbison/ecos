"""v0.90.0-a: POMDP T/R 在线学习数据结构测试 (TransitionPosterior + RewardPosterior).

对应设计: discussions/2026-08-12-v090-design.md §2.

测试范围:
  1. TransitionPosterior 创建 (3 tests): shape / dtype / alpha0=1
  2. TransitionPosterior.update + mean (3 tests): 增量 / 归一化 / 多次 update 单调
  3. RewardPosterior 创建 / update / mean (3 tests): shape / alpha=beta=1 → 0.5 / 多次 update 单调
  4. 防御性 (3 tests): 越界 raise / shape 校验 / alpha=beta > 0 校验
"""

from __future__ import annotations

import numpy as np
import pytest

from ecos.lca.l4_optimization.pomdp_learner import (
    RewardPosterior,
    TransitionPosterior,
)


# ---------------------------------------------------------------------------
# 1. TransitionPosterior 创建 (3 tests)
# ---------------------------------------------------------------------------


def test_transition_posterior_create_basic():
    """TransitionPosterior 基本创建: 4 states × 4 states × 10 arms count = zeros."""
    count = np.zeros((4, 4, 10), dtype=int)
    tp = TransitionPosterior(count=count)
    assert tp.n_states == 4
    assert tp.n_arms == 10
    assert tp.alpha0 == 1.0
    assert tp.count.shape == (4, 4, 10)
    assert tp.count.sum() == 0


def test_transition_posterior_create_with_custom_alpha0():
    """TransitionPosterior 自定义 alpha0: alpha0=2.0 uniform prior."""
    count = np.zeros((3, 3, 5), dtype=int)
    tp = TransitionPosterior(count=count, alpha0=2.0)
    assert tp.alpha0 == 2.0
    assert tp.n_states == 3
    assert tp.n_arms == 5


def test_transition_posterior_create_invalid_shape():
    """TransitionPosterior count 维度 ≠ 3D → raise ValueError."""
    count = np.zeros((4, 4), dtype=int)  # 2D, 错
    with pytest.raises(ValueError, match="必须是 3D"):
        TransitionPosterior(count=count)


# ---------------------------------------------------------------------------
# 2. TransitionPosterior.update + mean (3 tests)
# ---------------------------------------------------------------------------


def test_transition_posterior_update_increments():
    """TransitionPosterior.update(s, a, s_next) increment count[s_next, s, a] (跟 POMDPPolicy.transition 同约定)."""
    count = np.zeros((4, 4, 10), dtype=int)
    tp = TransitionPosterior(count=count)
    tp.update(s=1, a=3, s_next=2)
    tp.update(s=1, a=3, s_next=2)
    tp.update(s=1, a=3, s_next=0)
    assert tp.count[2, 1, 3] == 2
    assert tp.count[0, 1, 3] == 1
    assert tp.count.sum() == 3


def test_transition_posterior_mean_uniform_with_no_evidence():
    """count 全 0 + alpha0=1 → mean = 1/n_states (uniform prior smoothing)."""
    count = np.zeros((4, 4, 10), dtype=int)
    tp = TransitionPosterior(count=count)
    mean = tp.mean()
    assert mean.shape == (4, 4, 10)
    # 每 (s, a) 列 sum = 1 (沿 axis=0 即 s_next 求和)
    assert np.allclose(mean.sum(axis=0), 1.0)
    # count 全 0 + alpha0=1 → 1/n_states = 0.25
    assert np.allclose(mean, 1.0 / 4.0)


def test_transition_posterior_mean_concentrates_after_updates():
    """多次 update 后 mean 偏向 observed transition."""
    count = np.zeros((4, 4, 10), dtype=int)
    tp = TransitionPosterior(count=count)
    # 9 次 self-loop + 1 次 cross
    for _ in range(9):
        tp.update(0, 0, 0)  # count[0, 0, 0] += 1
    tp.update(0, 0, 1)      # count[1, 0, 0] += 1
    mean = tp.mean()
    # 对 (s=0, a=0): count[s_next=0]=9, count[s_next=1]=1, count[s_next=2/3]=0
    # posterior = (10, 2, 1, 1), sum=14
    expected_self = (9 + 1) / 14
    expected_cross = (1 + 1) / 14
    expected_others = (0 + 1) / 14
    assert np.isclose(mean[0, 0, 0], expected_self, atol=1e-6)
    assert np.isclose(mean[1, 0, 0], expected_cross, atol=1e-6)
    assert np.isclose(mean[2, 0, 0], expected_others, atol=1e-6)
    # 每 (s, a) 列 sum = 1
    assert np.allclose(mean.sum(axis=0), 1.0)


# ---------------------------------------------------------------------------
# 3. RewardPosterior 创建 / update / mean (3 tests)
# ---------------------------------------------------------------------------


def test_reward_posterior_create_with_uniform_prior():
    """RewardPosterior alpha=beta=1 → mean = 0.5 (uniform prior)."""
    alpha = np.ones((4, 10), dtype=float)
    beta = np.ones((4, 10), dtype=float)
    rp = RewardPosterior(alpha=alpha, beta=beta)
    assert rp.n_states == 4
    assert rp.n_arms == 10
    assert rp.alpha0 == 1.0
    mean = rp.mean()
    assert mean.shape == (4, 10)
    assert np.allclose(mean, 0.5)


def test_reward_posterior_update_increments_alpha_beta():
    """RewardPosterior.update: alpha += reward, beta += 1 - reward."""
    alpha = np.ones((4, 10), dtype=float)
    beta = np.ones((4, 10), dtype=float)
    rp = RewardPosterior(alpha=alpha, beta=beta)
    rp.update(2, 5, reward=1.0)
    assert rp.alpha[2, 5] == 2.0  # 1 + 1
    assert rp.beta[2, 5] == 1.0   # 1 + 0
    rp.update(2, 5, reward=0.0)
    assert rp.alpha[2, 5] == 2.0  # 2 + 0
    assert rp.beta[2, 5] == 2.0   # 1 + 1
    rp.update(2, 5, reward=0.5)
    assert rp.alpha[2, 5] == 2.5  # 2 + 0.5
    assert rp.beta[2, 5] == 2.5   # 2 + 0.5


def test_reward_posterior_mean_tracks_evidence():
    """RewardPosterior mean 跟 evidence 收敛 (跟 Thompson Sampling 一致)."""
    alpha = np.ones((4, 10), dtype=float)
    beta = np.ones((4, 10), dtype=float)
    rp = RewardPosterior(alpha=alpha, beta=beta)
    # 5 次 reward=1.0 → alpha=6, beta=1 → mean = 6/7
    for _ in range(5):
        rp.update(0, 0, reward=1.0)
    expected = 6.0 / 7.0
    assert np.isclose(rp.mean()[0, 0], expected, atol=1e-6)
    # 其他 cell 仍 0.5 (uniform prior)
    assert np.isclose(rp.mean()[1, 1], 0.5, atol=1e-6)


# ---------------------------------------------------------------------------
# 4. 防御性 (3 tests)
# ---------------------------------------------------------------------------


def test_transition_posterior_update_out_of_range_raises():
    """TransitionPosterior.update 越界 raise ValueError."""
    count = np.zeros((4, 4, 10), dtype=int)
    tp = TransitionPosterior(count=count)
    with pytest.raises(ValueError, match=r"s=4 越界"):
        tp.update(4, 0, 0)  # s >= n_states
    with pytest.raises(ValueError, match=r"a=10 越界"):
        tp.update(0, 10, 0)  # a >= n_arms
    with pytest.raises(ValueError, match=r"s_next=4 越界"):
        tp.update(0, 0, 4)  # s_next >= n_states


def test_reward_posterior_update_out_of_range_raises():
    """RewardPosterior.update 越界 + reward 越界 raise ValueError."""
    alpha = np.ones((4, 10), dtype=float)
    beta = np.ones((4, 10), dtype=float)
    rp = RewardPosterior(alpha=alpha, beta=beta)
    with pytest.raises(ValueError, match=r"s=4 越界"):
        rp.update(4, 0, 0.5)
    with pytest.raises(ValueError, match=r"a=10 越界"):
        rp.update(0, 10, 0.5)
    with pytest.raises(ValueError, match=r"必须在 \[0, 1\]"):
        rp.update(0, 0, 1.5)
    with pytest.raises(ValueError, match=r"必须在 \[0, 1\]"):
        rp.update(0, 0, -0.1)


def test_reward_posterior_create_invalid_shape():
    """RewardPosterior alpha / beta shape 不匹配 → raise ValueError."""
    alpha = np.ones((4, 10), dtype=float)
    beta = np.ones((10, 4), dtype=float)  # 错 shape
    with pytest.raises(ValueError, match="alpha 必须是 2D"):
        RewardPosterior(alpha=np.ones((4,)), beta=np.ones((4,)))
    with pytest.raises(ValueError, match="beta shape 必须跟 alpha 一致"):
        RewardPosterior(alpha=alpha, beta=beta)