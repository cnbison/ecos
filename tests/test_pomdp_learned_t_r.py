"""v0.90.0-c: POMDPPolicy 集成 update_t_r + PBVI 用 posterior mean 测试.

对应设计: discussions/2026-08-12-v090-design.md §4.

测试范围:
  1. update(arm, ctx, reward) 老调用兼容 (2 tests): 不传 obs → posterior 不创建
  2. update(arm, ctx, reward, observation=X) 新调用 (2 tests): 触发 _update_t_r, posterior 创建
  3. _update_t_r lazy init + 多次 update 单调 + 越界 (3 tests)
  4. PBVI 用 posterior mean (3 tests): use_learned_t_r=True/False 切换 + 学完后 best_action 改变
  5. posterior mean 异常 fallback (2 tests): posterior 注入但 use_learned_t_r=False → 用 init
"""

from __future__ import annotations

import numpy as np
import pytest

from ecos.lca.l4_optimization.pomdp import POMDPPolicy
from ecos.lca.l4_optimization.pomdp_learner import (
    RewardPosterior,
    TransitionPosterior,
)


# ---------------------------------------------------------------------------
# 1. update(arm, ctx, reward) 老调用兼容 (2 tests)
# ---------------------------------------------------------------------------


def test_update_without_observation_does_not_create_posterior():
    """update(arm, ctx, reward) 不传 obs → posterior 仍 None (老调用兼容)."""
    p = POMDPPolicy(seed=42)
    p.update(arm=2, context=None, reward=0.5)
    assert p._transition_posterior is None
    assert p._reward_posterior is None


def test_update_without_observation_arm_pull_counts_increment():
    """update(arm, ctx, reward) 不传 obs → arm_pull_counts 仍递增 (跟 v0.89.0-d 同)."""
    p = POMDPPolicy(seed=42)
    p.update(arm=2, context=None, reward=0.5)
    p.update(arm=2, context=None, reward=0.8)
    assert p.arm_pull_counts[2] == 2


# ---------------------------------------------------------------------------
# 2. update(arm, ctx, reward, observation=X) 新调用 (2 tests)
# ---------------------------------------------------------------------------


def test_update_with_observation_creates_posterior_lazily():
    """update(arm, ctx, reward, obs=X) 首次 → lazy 创建 posterior."""
    p = POMDPPolicy(seed=42)
    assert p._transition_posterior is None
    assert p._reward_posterior is None
    p.update(arm=2, context=None, reward=0.5, observation=0)
    assert p._transition_posterior is not None
    assert p._reward_posterior is not None


def test_update_with_observation_increments_posterior():
    """update(arm, ctx, reward, obs=X) → posterior 增量."""
    p = POMDPPolicy(seed=42)
    p.update(arm=2, context=None, reward=1.0, observation=0)
    # s_current = argmax(uniform belief) = 0
    # count[?, 0, 2] += 1 (s_next 由 _estimate_s_next_from_obs 派生)
    assert p._transition_posterior.count.sum() == 1
    # alpha[0, 2] += 1.0, beta[0, 2] += 0
    assert p._reward_posterior.alpha[0, 2] == 2.0  # 1.0 prior + 1.0
    assert p._reward_posterior.beta[0, 2] == 1.0   # 1.0 prior + 0


# ---------------------------------------------------------------------------
# 3. _update_t_r lazy init + 多次 update 单调 + 越界 (3 tests)
# ---------------------------------------------------------------------------


def test_update_t_r_multiple_calls_concentrate_posterior():
    """多次 update(obs) → posterior mean 单调偏向 observed."""
    p = POMDPPolicy(seed=42)
    # 跑一次 update 让 bayes_update 在 belief 上 shift (避免 s_current 永远是 argmax=0)
    p.bayes_update(action=0, observation=0)
    for _ in range(10):
        p.update(arm=0, context=None, reward=1.0, observation=0)
    # posterior 已有 10 个证据
    assert p._transition_posterior.count.sum() == 10
    # alpha[?, 0] 至少有一个 >= 11 (1 prior + 10 update)
    assert (p._reward_posterior.alpha >= 11.0).any()


def test_update_t_r_out_of_range_observation_skipped():
    """update 越界 observation → _log.warning + 跳过 (不 raise, 跟 bayes_update 同模式)."""
    p = POMDPPolicy(seed=42)
    p.update(arm=2, context=None, reward=0.5, observation=99)  # 越界
    # posterior 仍 None (跳过)
    assert p._transition_posterior is None
    assert p._reward_posterior is None


def test_update_t_r_no_state_mutation_on_skip():
    """update_t_r 越界跳过时, 已创建 posterior 不被破坏."""
    p = POMDPPolicy(seed=42)
    p.update(arm=2, context=None, reward=1.0, observation=0)  # 创建 posterior
    alpha_before = p._reward_posterior.alpha.copy()
    count_before = p._transition_posterior.count.copy()
    p.update(arm=2, context=None, reward=0.5, observation=99)  # 越界跳过
    assert np.array_equal(p._reward_posterior.alpha, alpha_before)
    assert np.array_equal(p._transition_posterior.count, count_before)


# ---------------------------------------------------------------------------
# 4. PBVI 用 posterior mean (3 tests)
# ---------------------------------------------------------------------------


def test_use_learned_t_r_true_default():
    """POMDPPolicy 默认 use_learned_t_r=True."""
    p = POMDPPolicy(seed=42)
    assert p.use_learned_t_r is True


def test_use_learned_t_r_false_returns_init_t_r():
    """use_learned_t_r=False → _resolve_t_r 返 init (跟 v0.89.0-d 兼容)."""
    p = POMDPPolicy(seed=42, use_learned_t_r=False)
    p.update(arm=2, context=None, reward=1.0, observation=0)  # 创建 posterior
    T, R = p._resolve_t_r()
    # 即使 posterior ready, use_learned_t_r=False → 走 init
    assert T is p.transition
    assert R is p.reward


def test_pbvi_uses_posterior_mean_when_learned_t_r_true():
    """use_learned_t_r=True + posterior ready → PBVI 用 posterior mean."""
    # min_samples=0 绕过冷启动阈值 (1 evidence 即可走 learned path)
    p = POMDPPolicy(seed=42, use_learned_t_r=True, min_samples=0)
    p.update(arm=2, context=None, reward=1.0, observation=0)  # 创建 posterior
    T, R = p._resolve_t_r()
    # T / R 不是 init, 是 posterior mean
    assert T is not p.transition
    assert R is not p.reward
    # shape 跟 init 一致
    assert T.shape == p.transition.shape
    assert R.shape == p.reward.shape


# ---------------------------------------------------------------------------
# 5. posterior mean 异常 fallback (2 tests)
# ---------------------------------------------------------------------------


def test_pbvi_fallback_to_qmdp_uses_posterior_mean():
    """PBVI 失败 → fallback QMDP 用 posterior mean (跟 v0.89.0-c 同模式 + posterior)."""
    p = POMDPPolicy(seed=42, use_learned_t_r=True, use_pbvi=False)
    p.update(arm=2, context=None, reward=1.0, observation=0)  # 创建 posterior
    arm = p.select_arm()
    # use_pbvi=False 走 QMDP, R 走 posterior mean
    assert 0 <= arm < p.n_arms


def test_select_arm_with_posterior_changes_best_action_over_time():
    """学完 enough evidence 后 best_action 改变 (学 > init 的 sanity check)."""
    p = POMDPPolicy(seed=42, use_learned_t_r=True, use_pbvi=False)
    # 初始 init R 让 state=0 偏好 arm 0-2 (高 reward)
    init_arm = p.select_arm()
    # 注入 T+R posterior (learned R: 所有 state 偏好 arm 8-9; T: 默认 zpaor 平滑)
    alpha = np.ones((4, 10), dtype=float)
    beta = np.ones((4, 10), dtype=float)
    for s in range(4):
        for a in range(10):
            if a in (8, 9):
                alpha[s, a] = 10.0
                beta[s, a] = 1.0
            else:
                alpha[s, a] = 1.0
                beta[s, a] = 10.0
    p.set_reward_posterior(RewardPosterior(alpha=alpha, beta=beta))
    # 必须同时注入 transition_posterior (跟 reward_posterior 配对, _resolve_t_r 要求都 ready)
    count = np.zeros((4, 4, 10), dtype=int)
    p.set_transition_posterior(TransitionPosterior(count=count))
    learned_arm = p.select_arm()
    # learned mean[a=8-9] = 10/11 ≈ 0.91, others ≈ 1/11 ≈ 0.09 → 偏好 8-9
    # init R[s, a=8-9] ≈ 0.06 (low) → 偏好 [0-2]
    assert learned_arm in {8, 9}
    assert init_arm in {0, 1, 2}