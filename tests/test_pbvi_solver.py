"""Tests for POMDP point-based solver — PBVI 雏形 (v0.89.0-a).

对应 12-kernel-mapping §1.3 Policy Engine:
    POMDP Policy → PBVI 雏形 (α-vector + 单步 backup).

v0.89.0-a 范围: 算法本体 (AlphaVector dataclass + PBVI class + 单步 backup +
alpha_value / best_action 雏形). b/c/d 范围 (solve / 集成 / Runtime) 留后续.

对应设计文档: discussions/2026-08-11-v089-design.md §2.

测试覆盖 (12 tests):
  1. AlphaVector 基本字段 (action / values)
  2. AlphaVector frozen 阻止 mutation
  3. AlphaVector equality + repr
  4. PBVI init 基本配置
  5. PBVI init 空 belief_points 抛 ValueError
  6. PBVI init 无效 gamma 抛 ValueError
  7. PBVI init 无效 epsilon / n_iters 抛 ValueError
  8. backup_step 返回 n_arms 个 AlphaVector
  9. backup_step 依赖 action (不同 action → 不同 α values)
 10. backup_step 包含 immediate reward (Σ_s b @ R[:, a])
 11. backup_step 输入 shape 不匹配抛 ValueError
 12. alpha_value / best_action 无 α-vector 时返 0
"""

from __future__ import annotations

import logging

import numpy as np
import pytest

from ecos.lca.l4_optimization.pomdp_solver import AlphaVector, PBVI


# === AlphaVector dataclass 测试 (3 tests) ===

def test_alpha_vector_creation_and_fields():
    """AlphaVector 创建 + action/values 字段.

    v0.89.0-a §2.3: AlphaVector = (action: int, values: np.ndarray[n_states])
    """
    values = np.array([0.1, 0.2, 0.3, 0.4])
    α = AlphaVector(action=2, values=values)
    assert α.action == 2
    assert α.values.shape == (4,)
    assert np.array_equal(α.values, values)


def test_alpha_vector_is_frozen():
    """AlphaVector frozen=True 阻止 mutation.

    v0.89.0-a §2.3: 不可变 (frozen) 防止 solver 内部 mutation 干扰外部.
    """
    α = AlphaVector(action=0, values=np.array([0.5, 0.5, 0.5, 0.5]))
    with pytest.raises((AttributeError, Exception)) as exc_info:
        α.action = 1  # type: ignore[misc]
    assert "frozen" in str(exc_info.value).lower() or "cannot assign" in str(exc_info.value).lower() or "setattr" in str(exc_info.value).lower()


def test_alpha_vector_repr_and_equality():
    """AlphaVector __repr__ + 字段 equality.

    v0.89.0-a §2.3: __repr__ 输出 'AlphaVector(action=X, values=[...])' 格式.
    注: 默认 dataclass == 触发 np.ndarray 元素比较 → ValueError, 测试用字段比较替代.
    """
    α1 = AlphaVector(action=1, values=np.array([0.1, 0.2]))
    α2 = AlphaVector(action=1, values=np.array([0.1, 0.2]))
    α3 = AlphaVector(action=2, values=np.array([0.1, 0.2]))
    # repr 包含 action + values
    repr_str = repr(α1)
    assert "AlphaVector" in repr_str
    assert "action=1" in repr_str
    assert "[0.1, 0.2]" in repr_str
    # 字段 equality (避开 np.ndarray == ambiguity)
    assert α1.action == α2.action
    assert np.array_equal(α1.values, α2.values)
    assert α1.action != α3.action


# === PBVI init 测试 (4 tests) ===

def test_pbvi_init_basic():
    """PBVI init 基本配置 (belief_points + gamma + epsilon + n_iters).

    v0.89.0-a §2.3: 接受 belief_points + 3 配置参数.
    """
    belief_points = [
        np.array([1.0, 0.0, 0.0, 0.0]),
        np.array([0.0, 1.0, 0.0, 0.0]),
    ]
    solver = PBVI(belief_points=belief_points, gamma=0.95, epsilon=1e-4, n_iters=50)
    assert solver.belief_points == belief_points
    assert solver.gamma == 0.95
    assert solver.epsilon == 1e-4
    assert solver.n_iters == 50
    assert solver.alpha_vectors == []  # 初始空


def test_pbvi_init_empty_belief_points_raises():
    """PBVI init 空 belief_points 抛 ValueError.

    v0.89.0-a §2.3: belief_points 不能为空.
    """
    with pytest.raises(ValueError, match="belief_points 不能为空"):
        PBVI(belief_points=[])


@pytest.mark.parametrize("invalid_gamma", [-0.1, 0.0, 1.1, 2.0])
def test_pbvi_init_invalid_gamma_raises(invalid_gamma):
    """PBVI init 无效 gamma 抛 ValueError.

    v0.89.0-a §2.3: gamma ∈ (0, 1] (折扣因子).
    """
    belief_points = [np.array([1.0, 0.0, 0.0, 0.0])]
    with pytest.raises(ValueError, match="gamma"):
        PBVI(belief_points=belief_points, gamma=invalid_gamma)


@pytest.mark.parametrize("invalid_eps", [-0.1, 0.0])
@pytest.mark.parametrize("invalid_iters", [-1, 0])
def test_pbvi_init_invalid_epsilon_or_n_iters_raises(invalid_eps, invalid_iters):
    """PBVI init 无效 epsilon / n_iters 抛 ValueError.

    v0.89.0-a §2.3: epsilon > 0, n_iters > 0.
    """
    belief_points = [np.array([1.0, 0.0, 0.0, 0.0])]
    with pytest.raises(ValueError):
        PBVI(belief_points=belief_points, epsilon=invalid_eps, n_iters=invalid_iters)


# === backup_step 测试 (4 tests) ===

def _make_toy_pomdp(n_states=4, n_arms=10, n_observations=4, seed=42):
    """构造 toy POMDP (跟 POMDPPolicy._init_* 简化一致).

    Returns:
        (transition, observation_model, reward)
    """
    rng = np.random.default_rng(seed)
    # transition: 强 self-loop (0.7) + 弱跨 (0.1) + 归一化
    transition = np.zeros((n_states, n_states, n_arms))
    for a in range(n_arms):
        base = np.eye(n_states) * 0.7 + np.ones((n_states, n_states)) * 0.1
        transition[:, :, a] = base / base.sum(axis=1, keepdims=True)
    # observation_model: 对角线 0.6 + 跨均匀
    obs_off = (1.0 - 0.6) / max(1, n_states - 1)
    observation_model = np.full((n_observations, n_states), obs_off)
    for s in range(n_states):
        observation_model[s, s] = 0.6
    observation_model = observation_model / observation_model.sum(axis=1, keepdims=True)
    # reward: 随机 (跟 POMDPPolicy 一致)
    reward = rng.uniform(0.0, 1.0, (n_states, n_arms))
    return transition, observation_model, reward


def test_backup_step_returns_n_arms_alpha_vectors():
    """backup_step 返回 n_arms 个 AlphaVector (每个 action 一个).

    v0.89.0-a §2.3: 对每个 action a 产生一个 α-vector.
    """
    n_states, n_arms = 4, 5
    belief_points = [np.array([1.0, 0.0, 0.0, 0.0]), np.array([0.25, 0.25, 0.25, 0.25])]
    solver = PBVI(belief_points=belief_points)
    transition, observation_model, reward = _make_toy_pomdp(n_states=n_states, n_arms=n_arms)

    new_alphas = solver.backup_step(transition, observation_model, reward)

    assert len(new_alphas) == n_arms
    # 每个 α 的 action 不同
    actions = sorted(α.action for α in new_alphas)
    assert actions == list(range(n_arms))
    # 每个 α 的 values 长度 = belief_points 数量
    for α in new_alphas:
        assert α.values.shape == (len(belief_points),)


def test_backup_step_uses_action_dependent_transition():
    """backup_step 依赖 action (不同 action → 不同 α values).

    v0.89.0-a §2.3: 单步 backup 雏形没有 future (alpha_vectors 空) 但不同 action
    会产生不同 α (因为 R[:, a] 不同). 雏形 backup_step 雏形依赖 reward 区分 action.

    注: 实际 future 部分也依赖 action (T[s'|s, a]), 但雏形 alpha_vectors 空
    所以 future=0. 验证 action 区分仅通过 reward (immediate) 即可.
    """
    belief_points = [np.array([1.0, 0.0, 0.0, 0.0])]
    solver = PBVI(belief_points=belief_points)
    transition, observation_model, reward = _make_toy_pomdp(seed=42)

    new_alphas = solver.backup_step(transition, observation_model, reward)

    # 至少 2 个 α 的 values 不同 (reward 区分)
    values_set = set(α.values.tobytes() for α in new_alphas)
    assert len(values_set) >= 2  # reward 至少让 2 个 action 不同


def test_backup_step_includes_immediate_reward():
    """backup_step 雏形只包含 immediate reward (α_vectors 空 → future=0).

    v0.89.0-a §2.3 限制: 雏形 backup_step 雏形 alpha_vectors 初始为空 → future=0.
    验证: V_a(b) = Σ_s b(s) * R(s, a) (immediate only).
    """
    belief_points = [np.array([1.0, 0.0, 0.0, 0.0])]
    solver = PBVI(belief_points=belief_points)
    transition, observation_model, reward = _make_toy_pomdp(seed=42)

    new_alphas = solver.backup_step(transition, observation_model, reward)

    # 对 belief_point[0] = [1, 0, 0, 0] (state 0), V_a(b) = R[0, a]
    for α in new_alphas:
        expected = reward[0, α.action]
        actual = float(α.values[0])
        assert np.isclose(actual, expected), (
            f"action={α.action}: expected immediate reward={expected}, got={actual}"
        )


@pytest.mark.parametrize("bad_transition,err_msg", [
    (np.zeros((4, 4)), "transition 必须是 3D"),  # 2D 错
    (np.zeros((4, 4, 4, 4)), "transition 必须是 3D"),  # 4D 错
])
def test_backup_step_validates_input_shapes(bad_transition, err_msg):
    """backup_step 输入 shape 不匹配抛 ValueError.

    v0.89.0-a §2.3: 防御性自检 [1] 输入校验.
    """
    belief_points = [np.array([1.0, 0.0, 0.0, 0.0])]
    solver = PBVI(belief_points=belief_points)
    transition, observation_model, reward = _make_toy_pomdp()

    with pytest.raises(ValueError, match=err_msg):
        solver.backup_step(bad_transition, observation_model, reward)


# === alpha_value / best_action 雏形测试 (1 test) ===

def test_alpha_value_and_best_action_with_no_alphas(caplog):
    """alpha_value / best_action 在无 α-vector 时返 0 + warning log.

    v0.89.0-a §2.3: 雏形退化 — 无 α-vector 时 alpha_value 返 0.0, best_action 返 0 + warning.
    """
    belief_points = [np.array([0.25, 0.25, 0.25, 0.25])]
    solver = PBVI(belief_points=belief_points)

    # alpha_value 无 α 时返 0.0
    assert solver.alpha_value(np.array([1.0, 0.0, 0.0, 0.0])) == 0.0

    # best_action 无 α 时返 0 + warning
    with caplog.at_level(logging.WARNING):
        action = solver.best_action(np.array([1.0, 0.0, 0.0, 0.0]))
    assert action == 0
    assert any("best_action" in rec.message for rec in caplog.records)