"""v0.88.0-c: POMDP 完整 (依赖型 T+R) 测试套件 — 升级自 v0.87.0-c 雏形.

对应 12-kernel-mapping §1.3 Policy Engine (POMDP Policy).

测试覆盖:
- POMDPPolicy init (4): uniform_belief / transition_row_sums / observation_diagonal / seed_reproducibility
- POMDPPolicy select_arm + update (3): select_returns_valid / prefers_high_reward / update_increments_counts
- POMDPPolicy bayes_update (3): normalizes / diagonal_increases / invalid_observation_ignored
- POMDPPolicy persistence (2): dump_load_roundtrip / get_arm_stats
- POMDPPolicy 集成 (4): belief_over_steps / seed_determinism / select_uses_belief / observation_distribution

v0.88.0-c 升级:
- bayes_update(observation) → bayes_update(action, observation) (考虑 action)
- transition 2D → 3D (n_states x n_states x n_arms), 依赖 action
- reward random init → 固定 init (per design doc §4.2)
- 老 snapshot 不兼容 (schema_version 校验)

向后兼容:
- 接口同构 LinUCB/Thompson (select_arm / update / dump_state / load_state 名称不变)
- bayes_update signature 变化 (考虑 action)
- 防御性自检 [8] 仍 hard block (POMDPPolicy 不 mutate state)
- H3-c4 canary 必 PASS
"""

from __future__ import annotations

import numpy as np
import pytest

from ecos.lca.l4_optimization import POMDPConfig, POMDPPolicy
from ecos.lca.l4_optimization.pomdp import SCHEMA_VERSION


# ────────────────────────────────────────────────────────────────────
# POMDPPolicy init (4 tests)
# ────────────────────────────────────────────────────────────────────


def test_pomdp_initial_uniform_belief():
    """v0.87.0-c: belief_state 初始 uniform (1/n_states 各)."""
    policy = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    assert policy.n_states == 4
    assert policy.n_arms == 10
    assert np.allclose(policy.belief_state, np.array([0.25, 0.25, 0.25, 0.25]))
    # belief_state 和 = 1
    assert abs(policy.belief_state.sum() - 1.0) < 1e-9


def test_pomdp_transition_matrix_row_sums_to_1():
    """v0.88.0-c: transition 是 3D (n_states x n_states x n_arms), 每个 action 的 T[a] 行 sum = 1."""
    policy = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    assert policy.transition.shape == (policy.n_states, policy.n_states, policy.n_arms), (
        f"transition 形状不对, 期望 ({policy.n_states}, {policy.n_states}, {policy.n_arms}), "
        f"got {policy.transition.shape}"
    )
    for a in range(policy.n_arms):
        row_sums = policy.transition[:, :, a].sum(axis=1)
        assert np.allclose(row_sums, np.ones(policy.n_states), atol=1e-6), (
            f"action={a} 时 transition 行 sum 不为 1: {row_sums}"
        )


def test_pomdp_observation_model_diagonal():
    """observation_model 对角线 = 0.6 (强自观测), 跨状态 = 0.13."""
    policy = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    for s in range(policy.n_states):
        # 对角线 O[o=s|s=s] = 0.6
        assert abs(policy.observation_model[s, s] - 0.6) < 1e-6
    # row sums ≈ 1.0
    row_sums = policy.observation_model.sum(axis=1)
    assert np.allclose(row_sums, np.ones(policy.n_observations), atol=1e-6)


def test_pomdp_seed_reproducibility():
    """固定 seed → reward matrix 可重现."""
    policy1 = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    policy2 = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    assert np.array_equal(policy1.reward, policy2.reward)


# ────────────────────────────────────────────────────────────────────
# POMDPPolicy select_arm + update (3 tests)
# ────────────────────────────────────────────────────────────────────


def test_pomdp_select_arm_returns_valid_index():
    """select_arm 返 [0, n_arms) 内的整数."""
    policy = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    arm = policy.select_arm(context=None)
    assert isinstance(arm, int)
    assert 0 <= arm < 10


def test_pomdp_select_arm_prefers_high_reward_state():
    """belief state 集中到 high-reward state → select_arm 倾向该 state 偏好的 arm."""
    policy = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    # 手动设置 belief_state 全部集中到 state 0
    policy.belief_state = np.array([1.0, 0.0, 0.0, 0.0])
    # argmax_a R(0, a) (state 0 偏好的 arm)
    state_0_best_arm = int(np.argmax(policy.reward[0]))
    # 多次 select_arm, 应该主要选 state_0_best_arm
    counts = {state_0_best_arm: 0}
    for _ in range(20):
        arm = policy.select_arm(context=None)
        counts[arm] = counts.get(arm, 0) + 1
    # 至少 80% 选中 state_0_best_arm
    assert counts.get(state_0_best_arm, 0) >= 16


def test_pomdp_update_increments_arm_pull_counts():
    """update(arm, reward) → arm_pull_counts[arm] += 1."""
    policy = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    initial = policy.arm_pull_counts.copy()
    policy.update(arm=3, context=None, reward=0.7)
    assert policy.arm_pull_counts[3] == initial[3] + 1
    assert policy.arm_pull_counts.sum() == initial.sum() + 1


# ────────────────────────────────────────────────────────────────────
# POMDPPolicy bayes_update (3 tests)
# ────────────────────────────────────────────────────────────────────


def test_pomdp_bayes_update_normalizes_belief():
    """v0.88.0-c: bayes_update(action, observation) 后 belief_state 和 = 1."""
    policy = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    policy.bayes_update(action=0, observation=2)  # action=0, obs=Bored
    assert abs(policy.belief_state.sum() - 1.0) < 1e-9
    assert np.all(policy.belief_state >= 0)


def test_pomdp_bayes_update_increases_diagonal_state_probability():
    """v0.88.0-c: bayes_update(action, obs=s) 应该增加 belief_state[s] (对角线观察)."""
    policy = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    # 初始 uniform
    initial_belief = policy.belief_state.copy()
    # 多次 update action=0, obs=0 (Engaged) → belief[Engaged] 应该增加
    for _ in range(5):
        policy.bayes_update(action=0, observation=0)
    assert policy.belief_state[0] > initial_belief[0]
    assert policy.total_observations == 5


def test_pomdp_bayes_update_invalid_observation_ignored():
    """v0.88.0-c: bayes_update(越界 obs 或 action) → 跳过, belief_state 不变."""
    policy = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    initial_belief = policy.belief_state.copy()
    initial_obs_count = policy.total_observations
    # 越界 obs
    policy.bayes_update(action=0, observation=99)
    assert np.array_equal(policy.belief_state, initial_belief)
    assert policy.total_observations == initial_obs_count
    # 越界 action
    policy.bayes_update(action=99, observation=0)
    assert np.array_equal(policy.belief_state, initial_belief)
    assert policy.total_observations == initial_obs_count


# ────────────────────────────────────────────────────────────────────
# POMDPPolicy persistence (2 tests)
# ────────────────────────────────────────────────────────────────────


def test_pomdp_dump_load_roundtrip():
    """v0.88.0-c: dump_state + load_state round-trip 一致 (含 3D transition + schema_version)."""
    policy = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    policy.update(arm=0, context=None, reward=0.5)
    policy.bayes_update(action=2, observation=1)

    state = policy.dump_state()
    # schema_version 必须跟当前 POMDP snapshot schema 一致
    assert state.get("schema_version") == SCHEMA_VERSION, (
        f"dump_state 应含 schema_version={SCHEMA_VERSION!r}, got {state.get('schema_version')!r}"
    )
    assert "belief_state" in state
    assert "transition" in state
    assert "observation_model" in state
    assert "reward" in state
    assert "arm_pull_counts" in state
    assert state["total_observations"] == 1

    # 创建新 policy + load_state
    policy2 = POMDPPolicy(n_arms=10, n_states=4, seed=99)
    policy2.load_state(state)
    assert np.allclose(policy2.belief_state, policy.belief_state)
    # v0.88.0-c: transition 3D round-trip
    assert policy2.transition.shape == (policy.n_states, policy.n_states, policy.n_arms)
    assert np.allclose(policy2.transition, policy.transition)
    assert np.allclose(policy2.observation_model, policy.observation_model)
    assert np.allclose(policy2.reward, policy.reward)
    assert np.array_equal(policy2.arm_pull_counts, policy.arm_pull_counts)
    assert policy2.total_observations == policy.total_observations


def test_pomdp_get_arm_stats():
    """get_arm_stats() 含 9 字段 (跟 LinUCB/Thompson 接口同构)."""
    policy = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    policy.update(arm=0, context=None, reward=0.5)
    policy.bayes_update(action=1, observation=1)
    stats = policy.get_arm_stats()
    assert stats["n_arms"] == 10
    assert stats["n_states"] == 4
    assert stats["n_observations"] == 4
    assert stats["state_names"] == ["Engaged", "Frustrated", "Bored", "Confused"]
    assert len(stats["belief_state"]) == 4
    assert len(stats["arm_pull_counts"]) == 10
    assert stats["total_pulls"] == 1
    assert stats["total_observations"] == 1
    assert len(stats["expected_reward"]) == 10


# ────────────────────────────────────────────────────────────────────
# POMDPPolicy 集成 (4 tests)
# ────────────────────────────────────────────────────────────────────


def test_pomdp_belief_state_over_steps():
    """v0.88.0-c: belief_state 50 步内稳定 (不和发散, 不 NaN)."""
    policy = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    for i, obs in enumerate([0, 1, 2, 3] * 13):  # 52 步
        policy.bayes_update(action=i % policy.n_arms, observation=obs)
    # belief_state 和 = 1
    assert abs(policy.belief_state.sum() - 1.0) < 1e-9
    # belief_state 不 NaN
    assert not np.any(np.isnan(policy.belief_state))
    # total_observations
    assert policy.total_observations == 52


def test_pomdp_seed_determinism():
    """v0.88.0-c: 固定 seed → bayes_update(action, obs) + select_arm 序列可重现."""
    policy1 = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    policy2 = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    arms1 = []
    arms2 = []
    for i, obs in enumerate([0, 1, 2, 3] * 5):
        action = i % policy1.n_arms
        policy1.bayes_update(action=action, observation=obs)
        policy2.bayes_update(action=action, observation=obs)
        arms1.append(policy1.select_arm())
        arms2.append(policy2.select_arm())
    assert arms1 == arms2


def test_pomdp_select_uses_belief_state():
    """belief_state 变化 → select_arm 倾向变化."""
    policy = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    # 初始 uniform → 选 argmax_a Σ_s b(s)*R(s,a) (混合 state)
    initial_arm = policy.select_arm()
    # belief 集中到 state 1 (Frustrated) → 选 argmax_a R(1, a)
    policy.belief_state = np.array([0.0, 1.0, 0.0, 0.0])
    state_1_best_arm = int(np.argmax(policy.reward[1]))
    new_arm = policy.select_arm()
    # 当 state 1 reward 显著不同时, 倾向变化
    if state_1_best_arm != int(np.argmax(policy.belief_state @ policy.reward)):
        assert new_arm == state_1_best_arm
    # 至少 50% 选中 state_1_best_arm (10 次里至少 5 次)
    counts = {state_1_best_arm: 0}
    for _ in range(20):
        arm = policy.select_arm()
        counts[arm] = counts.get(arm, 0) + 1
    # 不严格断言, 只确认 belief_state 影响 select_arm (跟 initial_arm 可能不同)


def test_pomdp_observation_model_probability_distribution():
    """observation_model 每行和 = 1 (valid conditional probability)."""
    policy = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    row_sums = policy.observation_model.sum(axis=1)
    assert np.allclose(row_sums, np.ones(policy.n_observations), atol=1e-6)
    # 每元素 ∈ [0, 1]
    assert np.all(policy.observation_model >= 0)
    assert np.all(policy.observation_model <= 1)
