"""v0.88.0-c: POMDP 完整 (依赖型 T+R) 测试套件 — 升级自 v0.87.0-c 雏形.

对应 12-kernel-mapping §1.3 Policy Engine (POMDP Policy) — POMDP 完整化.

测试覆盖 v0.88.0-c 关键升级:
  - T(s'|s, a) 依赖 action: shape (n_states, n_states, n_arms) — 替换 v0.87.0-c 4x4 简化矩阵
  - R(s, a) 固定 init: 替换 v0.87.0-c random init (state s 偏好 arm 区间)
  - bayes_update(action, observation): 考虑 action (跟 v0.87.0-c 区分)
  - dump_state / load_state schema_version 校验 (老 snapshot 不兼容)
  - 接口同构 LinUCB/Thompson (select_arm / update 名称不变)

v0.88.0-c 共 16 测试:
  1. T 形状 (2 tests): 3D shape + per-action row sum = 1
  2. T 依赖 action (2 tests): 不同 action → 不同 T[a]
  3. R 固定 init (4 tests): state 偏好区间 + 区间外低 reward + seed 可重现 + R ∈ [0, 1]
  4. bayes_update 考虑 action (4 tests): 同 obs 不同 action → 不同 posterior + invalid 越界跳过
  5. dump_state/load_state schema (4 tests): 含 schema_version + 3D roundtrip + 老 snapshot raise + 缺失 schema 字段 raise
"""

from __future__ import annotations

import numpy as np
import pytest

from ecos.lca.l4_optimization import POMDPPolicy
from ecos.lca.l4_optimization.pomdp import SCHEMA_VERSION


# ────────────────────────────────────────────────────────────────────
# 1. T 形状 (2 tests)
# ────────────────────────────────────────────────────────────────────


def test_pomdp_transition_is_3d_action_dependent():
    """v0.88.0-c: T 形状 = (n_states, n_states, n_arms) (跟 v0.87.0-c 2D 区分)."""
    policy = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    assert policy.transition.ndim == 3, (
        f"transition 应是 3D (n_states x n_states x n_arms), got ndim={policy.transition.ndim}"
    )
    assert policy.transition.shape == (4, 4, 10), (
        f"transition 形状不对, 期望 (4, 4, 10), got {policy.transition.shape}"
    )


def test_pomdp_transition_per_action_row_sums_to_1():
    """v0.88.0-c: 每个 action 的 T[a] 每行 sum = 1 (valid stochastic matrix per action)."""
    policy = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    for a in range(policy.n_arms):
        row_sums = policy.transition[:, :, a].sum(axis=1)
        assert np.allclose(row_sums, np.ones(policy.n_states), atol=1e-6), (
            f"action={a} 时 T[a] 行 sum 不为 1: {row_sums}"
        )


# ────────────────────────────────────────────────────────────────────
# 2. T 依赖 action (2 tests)
# ────────────────────────────────────────────────────────────────────


def test_pomdp_transition_differs_per_action():
    """v0.88.0-c: 不同 action → 不同 T[a] (依赖 action, 跟 v0.87.0-c 不变区分)."""
    policy = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    # 至少 2 个 action 的 T[a] 不完全相同
    assert not np.allclose(policy.transition[:, :, 0], policy.transition[:, :, 1]), (
        "T[0] 和 T[1] 不应相同 (action 应有不同影响)"
    )
    # 所有 action 的 T[a] 两两不完全相同
    for a1 in range(policy.n_arms):
        for a2 in range(a1 + 1, policy.n_arms):
            assert not np.allclose(policy.transition[:, :, a1], policy.transition[:, :, a2]), (
                f"T[{a1}] 和 T[{a2}] 不应完全相同 (action 应有不同 transition)"
            )


def test_pomdp_transition_action_perturbation_structure():
    """v0.88.0-c: T[a] 跟 base T (v0.87.0-c 4x4) 的 perturbation 是 +0.1 cross-state.

    验证 init 算法正确:
      - base T[s'|s] = 0.7 self-loop + 0.1 cross
      - perturbation[a][s'|s] = +0.1 (off-diagonal)
      - T[a] = (base + perturbation) normalized
    """
    policy = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    # v0.87.0-c base T = eye*0.7 + ones*0.1 → row sum = 1.0 (n_states=4 时)
    base_T = np.eye(4) * 0.7 + np.ones((4, 4)) * 0.1
    # v0.88.0-c T[a] = (base + off_diag_perturbation) normalized
    # 行 sum 应该是 1.0 (已 normaliz), 但 off-diagonal 元素应 > base 的 off-diagonal (0.1)
    for a in range(policy.n_arms):
        T_a = policy.transition[:, :, a]
        # off-diagonal 元素: perturbation [+0.1] → normalized 后应 > base 的 0.1
        for s in range(policy.n_states):
            for s2 in range(policy.n_states):
                if s != s2:
                    assert T_a[s, s2] > base_T[s, s2], (
                        f"action={a} 时 T[{s},{s2}] 应 > base T[{s},{s2}] "
                        f"(+0.1 perturbation 后 normalized), got T={T_a[s,s2]}, base={base_T[s,s2]}"
                    )


# ────────────────────────────────────────────────────────────────────
# 3. R 固定 init (4 tests)
# ────────────────────────────────────────────────────────────────────


def test_pomdp_reward_state_prefers_arm_interval():
    """v0.88.0-c: R(s, a) 固定 init, state s 偏好 arm 区间 [s*n_arms/n_states, (s+1)*n_arms/n_states).

    注意 init 算法用 `s * n_arms // n_states` (operator precedence: 先 * 后 //),
    不等价于 `s * (n_arms // n_states)` (e.g. s=3, n_arms=10: 7 vs 6).

    验证: 偏好区间内 R[s, a] > 偏好区间外 R[s, a] (高 reward).
    """
    policy = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    for s in range(policy.n_states):
        # 注意: init 用 `s * self.n_arms // self.n_states` (operator precedence)
        start = s * policy.n_arms // policy.n_states
        end = (s + 1) * policy.n_arms // policy.n_states
        # 偏好区间
        interval_R = policy.reward[s, start:end]
        # 偏好区间外
        if start > 0:
            low_R = policy.reward[s, :start]
        else:
            low_R = np.array([])
        if end < policy.n_arms:
            high_R = policy.reward[s, end:]
        else:
            high_R = np.array([])
        # 偏好区间均 reward > 区间外均 reward (固定 init 模式)
        if len(low_R) > 0:
            assert interval_R.mean() > low_R.mean(), (
                f"state={s} 偏好区间均 reward 应 > 区间左均 reward: "
                f"interval={interval_R.mean():.3f}, low={low_R.mean():.3f}"
            )
        if len(high_R) > 0:
            assert interval_R.mean() > high_R.mean(), (
                f"state={s} 偏好区间均 reward 应 > 区间右均 reward: "
                f"interval={interval_R.mean():.3f}, high={high_R.mean():.3f}"
            )


def test_pomdp_reward_in_unit_interval():
    """v0.88.0-c: R(s, a) ∈ [0, 1] (跟 v0.87.0-c random uniform 同范围)."""
    policy = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    assert np.all(policy.reward >= 0), "R 应 ≥ 0"
    assert np.all(policy.reward <= 1), "R 应 ≤ 1"
    # 至少有一些值 ∈ [0.5, 1.0] (偏好区间)
    assert np.any(policy.reward >= 0.5), "R 应有偏好区间的 ≥0.5 高 reward"


def test_pomdp_reward_seed_reproducibility():
    """v0.88.0-c: 固定 seed → R(s, a) 完全可重现 (PRNG seed)."""
    policy1 = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    policy2 = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    assert np.array_equal(policy1.reward, policy2.reward), (
        "固定 seed 应产出完全相同的 R(s, a) 矩阵"
    )


def test_pomdp_reward_different_seed_differs():
    """v0.88.0-c: 不同 seed → 不同 R(s, a) (PRNG 行为)."""
    policy1 = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    policy2 = POMDPPolicy(n_arms=10, n_states=4, seed=99)
    # 至少有一些元素不同 (随机 init 的自然结果)
    assert not np.array_equal(policy1.reward, policy2.reward), (
        "不同 seed 应产出不同的 R(s, a) 矩阵 (PRNG random)"
    )


# ────────────────────────────────────────────────────────────────────
# 4. bayes_update 考虑 action (4 tests)
# ────────────────────────────────────────────────────────────────────


def test_pomdp_bayes_update_same_obs_different_action_different_posterior():
    """v0.88.0-c: 同 obs 不同 action → 不同 posterior (T 依赖 action 的核心证据).

    用非 uniform belief (集中到 state 0) 让 T[a] cross-state 差异可见.
    """
    policy_a = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    policy_b = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    # 非 uniform belief (集中到 state 0) — 让 T[a] 跨状态差异可见
    concentrated = np.array([0.7, 0.1, 0.1, 0.1])
    policy_a.belief_state = concentrated.copy()
    policy_b.belief_state = concentrated.copy()
    # 同 obs, 不同 action
    policy_a.bayes_update(action=0, observation=1)
    policy_b.bayes_update(action=9, observation=1)
    # belief_state 应不同 (因为 T[a=0] != T[a=9])
    assert not np.allclose(policy_a.belief_state, policy_b.belief_state), (
        f"同 obs 不同 action 应产生不同 posterior, "
        f"got a0={policy_a.belief_state}, a9={policy_b.belief_state}"
    )


def test_pomdp_bayes_update_considers_action_in_predict():
    """v0.88.0-c: bayes_update 中 predict 步骤 b_pred[s'] = Σ_s T[s'|s, a] * b(s) 真正用 action.

    验证方式: 相同 belief + 相同 obs, 不同 action 产生的 posterior 不同
    (需要非 uniform belief 让 T[a] 差异可见).
    """
    policy_a = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    policy_b = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    # 非 uniform belief (集中在 state 2) — 让 T[a] 跨状态差异可见
    concentrated = np.array([0.1, 0.1, 0.7, 0.1])
    policy_a.belief_state = concentrated.copy()
    policy_b.belief_state = concentrated.copy()
    # 同 obs, 不同 action (边界 actions 让 perturbation 差异最大)
    policy_a.bayes_update(action=0, observation=2)
    policy_b.bayes_update(action=9, observation=2)
    # posterior 必须不同 (T[0] vs T[9] 不同 → 不同 b_pred → 不同 b_post)
    assert not np.allclose(policy_a.belief_state, policy_b.belief_state), (
        "T 依赖 action 时, 不同 action 应产生不同 b_post "
        "(即使 belief 和 obs 都相同, 非 uniform belief 让差异可见)"
    )


def test_pomdp_bayes_update_invalid_action_ignored():
    """v0.88.0-c: bayes_update(越界 action) → 跳过, belief_state 不变 (跟 obs 越界同模式)."""
    policy = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    initial_belief = policy.belief_state.copy()
    initial_obs_count = policy.total_observations
    # 越界 action (n_arms=10, action=99)
    policy.bayes_update(action=99, observation=1)
    assert np.array_equal(policy.belief_state, initial_belief), (
        "越界 action 应被 skip, belief_state 不变"
    )
    assert policy.total_observations == initial_obs_count, (
        "越界 action 应被 skip, total_observations 不变"
    )


def test_pomdp_bayes_update_normalization_with_action():
    """v0.88.0-c: bayes_update(action, obs) 后 belief_state 仍 sum = 1 + all ≥ 0."""
    policy = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    for action, obs in [(0, 0), (3, 1), (7, 2), (5, 3)]:
        policy.bayes_update(action=action, observation=obs)
        assert abs(policy.belief_state.sum() - 1.0) < 1e-9, (
            f"action={action}, obs={obs} 后 belief sum != 1: {policy.belief_state.sum()}"
        )
        assert np.all(policy.belief_state >= 0), (
            f"action={action}, obs={obs} 后 belief 有负值: {policy.belief_state}"
        )
    assert policy.total_observations == 4


# ────────────────────────────────────────────────────────────────────
# 5. dump_state/load_state schema (4 tests)
# ────────────────────────────────────────────────────────────────────


def test_pomdp_dump_state_includes_schema_version_and_3d_transition():
    """v0.88.0-c: dump_state 含 schema_version + 3D transition (跟 v0.87.0-c 2D 区分)."""
    policy = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    state = policy.dump_state()
    # schema_version
    assert state.get("schema_version") == SCHEMA_VERSION, (
        f"dump_state 应含 schema_version={SCHEMA_VERSION!r}, got {state.get('schema_version')!r}"
    )
    # 3D transition
    transition = state["transition"]
    assert isinstance(transition, list), "transition 应是 list of list of list"
    assert len(transition) == 4, f"transition 第一维 = n_states=4, got {len(transition)}"
    for a_idx, T_a in enumerate(transition):
        assert len(T_a) == 4, f"transition 第二维 (action={a_idx}) 应 = n_states=4, got {len(T_a)}"
        for row in T_a:
            assert len(row) == 10, f"transition 第三维 应 = n_arms=10, got {len(row)}"


def test_pomdp_load_state_validates_schema_version():
    """v0.88.0-c: load_state 必须有 schema_version 字段 (缺失 → raise)."""
    policy = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    state_no_version = policy.dump_state()
    state_no_version.pop("schema_version")
    with pytest.raises(ValueError, match="schema_version"):
        policy.load_state(state_no_version)


def test_pomdp_load_state_rejects_old_snapshot():
    """v0.88.0-c: load_state schema_version 不匹配 → raise (老 snapshot 不兼容, per design §4.3)."""
    policy = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    old_state = {
        "schema_version": "0.87.0-c",  # 老版本
        "n_arms": 10,
        "n_states": 4,
        "n_observations": 4,
        "belief_state": [0.25, 0.25, 0.25, 0.25],
        # v0.87.0-c 是 2D transition
        "transition": [[0.7, 0.1, 0.1, 0.1]] * 4,
        "observation_model": [[0.6, 0.13, 0.13, 0.13]] * 4,
        "reward": [[0.5] * 10] * 4,
        "arm_pull_counts": [0] * 10,
        "total_observations": 0,
    }
    with pytest.raises(ValueError, match="schema_version"):
        policy.load_state(old_state)


def test_pomdp_load_state_3d_transition_roundtrip():
    """v0.88.0-c: dump_state + load_state 3D transition 完全一致 (含 action 维)."""
    policy1 = POMDPPolicy(n_arms=10, n_states=4, seed=42)
    # 修改 transition 某些 action 的值, 验证 roundtrip 保留
    policy1.transition[0, 1, 3] = 0.123
    policy1.transition[2, 3, 5] = 0.456
    state = policy1.dump_state()
    # 新 policy load
    policy2 = POMDPPolicy(n_arms=10, n_states=4, seed=99)
    policy2.load_state(state)
    assert policy2.transition.shape == policy1.transition.shape
    assert np.allclose(policy2.transition, policy1.transition), (
        "3D transition round-trip 应保留所有 action 维度的修改"
    )
    assert abs(policy2.transition[0, 1, 3] - 0.123) < 1e-9
    assert abs(policy2.transition[2, 3, 5] - 0.456) < 1e-9