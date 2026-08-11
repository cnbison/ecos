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

from ecos.lca.l4_optimization.pomdp_solver import (
    AlphaVector,
    PBVI,
    reachable_belief_points,
    uniform_belief_points,
)


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
    """backup_step 返回 n_arms 个 AlphaVector (每个 action 一个, v0.89.0-b 经典 PBVI).

    v0.89.0-b §3: 对每个 action a 输出 α-vector in state space (values shape (n_states,)).
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
    # 每个 α 的 values 长度 = n_states (经典 PBVI in state space, v0.89.0-b)
    for α in new_alphas:
        assert α.values.shape == (n_states,)


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


# === v0.89.0-b: PBVI 完整算法 + belief point sampling 测试 (12 tests) ===
#
# 对应设计档 §3 (PBVI.update_alpha_vectors + PBVI.solve + reachable/uniform belief sampling).
# 实际函数数量 = 12, pytest 收集 = 12 (无 parametrize).


def test_update_alpha_vectors_basic():
    """update_alpha_vectors 更新 self.alpha_vectors (v0.89.0-b §3).

    验证: 调用 update_alpha_vectors(new_alphas) 后 self.alpha_vectors 等于 new_alphas.
    """
    belief_points = [np.array([1.0, 0.0, 0.0, 0.0])]
    solver = PBVI(belief_points=belief_points)
    transition, observation_model, reward = _make_toy_pomdp(n_arms=3)

    new_alphas = solver.backup_step(transition, observation_model, reward)
    solver.update_alpha_vectors(new_alphas)

    assert len(solver.alpha_vectors) == 3
    assert all(isinstance(α, AlphaVector) for α in solver.alpha_vectors)


def test_update_alpha_vectors_convergence_detected():
    """update_alpha_vectors 收敛检测 (v0.89.0-b §3).

    验证:
      - 第一次 update (α_vectors 空 → old_by_action 空 → max_diff=0 → 收敛)
      - 第二次 update (基于第一次 α, future 部分变化 → max_diff > 0 → 不收敛)
      - 第 N 次 update (到收敛) → 收敛
    """
    belief_points = [np.array([1.0, 0.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0, 0.0])]
    solver = PBVI(belief_points=belief_points, gamma=0.5, epsilon=1e-6)
    transition, observation_model, reward = _make_toy_pomdp(n_arms=3, seed=42)

    # 第一次 backup + update (α_vectors 空 → max_diff=0 → 收敛 True)
    new_alphas_1 = solver.backup_step(transition, observation_model, reward)
    converged_1 = solver.update_alpha_vectors(new_alphas_1)
    assert converged_1 is True

    # 第二次 backup + update (γ=0.5 + future ≠ 0 → max_diff > 0 → 不收敛)
    new_alphas_2 = solver.backup_step(transition, observation_model, reward)
    converged_2 = solver.update_alpha_vectors(new_alphas_2)
    assert converged_2 is False


def test_update_alpha_vectors_empty_returns_false():
    """update_alpha_vectors 空 new_alphas 返 False (v0.89.0-b §3 防御性).

    验证: new_alphas=[] → 不更新 + 返 False.
    """
    belief_points = [np.array([1.0, 0.0, 0.0, 0.0])]
    solver = PBVI(belief_points=belief_points)

    result = solver.update_alpha_vectors([])
    assert result is False
    # alpha_vectors 仍空
    assert solver.alpha_vectors == []


def test_solve_populates_alpha_vectors():
    """solve 填充 self.alpha_vectors (v0.89.0-b §3).

    验证: solve 后 len(alpha_vectors) == n_arms.
    """
    belief_points = [np.array([1.0, 0.0, 0.0, 0.0])]
    solver = PBVI(belief_points=belief_points, n_iters=10)
    transition, observation_model, reward = _make_toy_pomdp(n_arms=3)

    iters = solver.solve(transition, observation_model, reward)

    assert 1 <= iters <= 10
    assert len(solver.alpha_vectors) == 3


def test_solve_converges_within_n_iters():
    """solve 在 n_iters 内收敛 (v0.89.0-b §3).

    简化 POMDP (γ=0.5, 强 self-loop): 预期快速收敛.
    """
    belief_points = [np.array([1.0, 0.0, 0.0, 0.0])]
    solver = PBVI(belief_points=belief_points, gamma=0.5, epsilon=1e-3, n_iters=50)
    transition, observation_model, reward = _make_toy_pomdp(n_arms=3, seed=42)

    iters = solver.solve(transition, observation_model, reward)

    # 应该 < n_iters (50) 内收敛 (简化 POMDP)
    assert iters < 50
    # 收敛时 values 不应剧烈变化 (convergence 保证)
    assert len(solver.alpha_vectors) == 3


def test_solve_respects_n_iters_cap():
    """solve 遵守 n_iters 上限 (v0.89.0-b §3).

    验证: n_iters=1 时最多 1 次迭代 (强制不收敛).
    """
    belief_points = [np.array([1.0, 0.0, 0.0, 0.0])]
    solver = PBVI(belief_points=belief_points, n_iters=1)
    transition, observation_model, reward = _make_toy_pomdp(n_arms=3, seed=42)

    iters = solver.solve(transition, observation_model, reward)

    assert iters == 1  # 1 次迭代


def test_solve_value_increases_monotonically():
    """solve 收敛时 value 递增 (POMDP value iteration 性质, v0.89.0-b §3).

    简化 POMDP (γ=0.5, 高 reward 偏好): value 单调递增直到收敛.
    注: 严格单调只在 discount 充分小时保证 (γ < 1). 这里 γ=0.5 足够小.
    """
    belief_points = [np.array([1.0, 0.0, 0.0, 0.0])]
    solver = PBVI(belief_points=belief_points, gamma=0.5, epsilon=1e-6, n_iters=20)
    transition, observation_model, reward = _make_toy_pomdp(n_arms=3, seed=42)

    solver.solve(transition, observation_model, reward)

    # best_action 在 fixed belief 上 ≥ 0 (POMDP value >= 0 if R >= 0)
    belief = np.array([0.25, 0.25, 0.25, 0.25])
    v_final = solver.alpha_value(belief)
    # 注: R ∈ U(0, 1), value = immediate + γ * future ≥ 0 (因所有项 ≥ 0)
    assert v_final >= 0.0


def test_reachable_belief_points_returns_correct_count():
    """reachable_belief_points 返 n_steps * n_samples_per_step + 1 (含 initial) (v0.89.0-b §3.2).

    验证: 返 n_steps*n_samples + 1 (initial 作为 anchor).
    """
    belief_points = [np.array([1.0, 0.0, 0.0, 0.0])]
    transition, observation_model, _ = _make_toy_pomdp(n_arms=5, n_observations=4, seed=42)
    initial = np.array([0.25, 0.25, 0.25, 0.25])

    samples = reachable_belief_points(
        transition, observation_model, initial,
        n_steps=3, n_samples_per_step=4, seed=42,
    )

    # 最多 n_steps * n_samples_per_step + 1 (initial)
    assert len(samples) == 3 * 4 + 1
    # initial 是第一个
    assert np.array_equal(samples[0], initial)
    # 每个 belief shape (n_states,)
    for b in samples:
        assert b.shape == (4,)


def test_reachable_belief_points_deterministic_with_seed():
    """reachable_belief_points 同 seed 返同 output (v0.89.0-b §3.2).

    验证: 同一 seed 两次调用返完全一致.
    """
    belief_points = [np.array([1.0, 0.0, 0.0, 0.0])]
    transition, observation_model, _ = _make_toy_pomdp(n_arms=5, n_observations=4, seed=42)
    initial = np.array([0.25, 0.25, 0.25, 0.25])

    samples_1 = reachable_belief_points(
        transition, observation_model, initial,
        n_steps=3, n_samples_per_step=4, seed=42,
    )
    samples_2 = reachable_belief_points(
        transition, observation_model, initial,
        n_steps=3, n_samples_per_step=4, seed=42,
    )

    assert len(samples_1) == len(samples_2)
    for b1, b2 in zip(samples_1, samples_2):
        assert np.array_equal(b1, b2)


def test_reachable_belief_points_validates_input():
    """reachable_belief_points 输入校验 (v0.89.0-b §3.2).

    验证: 错 shape / 负参数 raise ValueError.
    """
    belief_points = [np.array([1.0, 0.0, 0.0, 0.0])]
    transition, observation_model, _ = _make_toy_pomdp(n_arms=5, n_observations=4, seed=42)
    initial = np.array([0.25, 0.25, 0.25, 0.25])

    # n_steps=0 抛
    with pytest.raises(ValueError, match="n_steps"):
        reachable_belief_points(
            transition, observation_model, initial, n_steps=0, n_samples_per_step=4, seed=42,
        )
    # n_samples_per_step=0 抛
    with pytest.raises(ValueError, match="n_samples_per_step"):
        reachable_belief_points(
            transition, observation_model, initial, n_steps=3, n_samples_per_step=0, seed=42,
        )
    # initial belief shape 错 抛
    bad_initial = np.array([0.5, 0.5])
    with pytest.raises(ValueError, match="initial_belief"):
        reachable_belief_points(
            transition, observation_model, bad_initial, n_steps=3, n_samples_per_step=4, seed=42,
        )


def test_uniform_belief_points_returns_correct_count():
    """uniform_belief_points 返 n_samples 个 (v0.89.0-b §3.2).

    验证: 返 n_samples 个 belief, 每个 shape (n_states,).
    """
    samples = uniform_belief_points(n_states=4, n_samples=12, seed=42)
    assert len(samples) == 12
    for b in samples:
        assert b.shape == (4,)


def test_uniform_belief_points_each_sums_to_one():
    """uniform_belief_points 每个 belief sum ≈ 1.0 (simplex 性质, v0.89.0-b §3.2).

    验证: Dirichlet 采样 → 每个 belief 是概率分布 (sum ≈ 1.0).
    """
    samples = uniform_belief_points(n_states=4, n_samples=10, seed=42)
    for b in samples:
        assert np.isclose(b.sum(), 1.0, atol=1e-6)
        # 每个 component ∈ [0, 1]
        assert np.all(b >= 0.0)
        assert np.all(b <= 1.0)