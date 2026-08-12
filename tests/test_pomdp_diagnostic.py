"""v0.93.0-a: POMDP 诊断数据结构测试 (POMDPDiagnostic + TransitionPosteriorSnapshot + RewardPosteriorSnapshot).

对应设计: discussions/2026-08-12-v093-design.md §2.

测试范围 (12 tests):
  1. TransitionPosteriorSnapshot dataclass shape (2 tests): 3D mean / 3D count / alpha0 / schema_version
  2. RewardPosteriorSnapshot dataclass shape (2 tests): 2D mean / 2D alpha+beta+variance
  3. POMDPDiagnostic dataclass shape (1 test): 1D belief / 2D coverage / most_likely_state
  4. to_dict round-trip (3 tests): TransitionPosteriorSnapshot / RewardPosteriorSnapshot / POMDPDiagnostic
  5. schema_version 防御性自检 [5] (1 test): 老 schema raise ValueError
  6. POMDPPolicy.get_diagnostic (3 tests): lazy init / posterior / most_likely_state
  7. POMDPPolicy.get_transition_heatmap (1 test): shape + sum
  8. POMDPPolicy.get_reward_curves (1 test): dict keys + shape
  9. POMDPDiagnostic frozen (1 test): mutation raises FrozenInstanceError
  10. coverage 派生 (1 test): per (s, a) 样本数
  11. _compute_beta_variance (1 test): Beta 后验方差
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pytest

from ecos.lca.l4_optimization.pomdp import POMDPPolicy
from ecos.lca.l4_optimization.pomdp_diagnostic import (
    POMDPDiagnostic,
    RewardPosteriorSnapshot,
    SCHEMA_VERSION,
    TransitionPosteriorSnapshot,
    _compute_beta_variance,
)


# ---------------------------------------------------------------------------
# 1. TransitionPosteriorSnapshot dataclass shape (2 tests)
# ---------------------------------------------------------------------------


def test_transition_snapshot_basic_shape():
    """TransitionPosteriorSnapshot 基本字段: 3D mean + 3D count + alpha0 + schema_version."""
    mean = np.full((4, 4, 10), 0.25)
    count = np.zeros((4, 4, 10), dtype=int)
    T = TransitionPosteriorSnapshot(mean=mean, count=count, alpha0=1.0)
    assert T.mean.shape == (4, 4, 10)
    assert T.count.shape == (4, 4, 10)
    assert T.alpha0 == 1.0
    assert T.schema_version == "0.93.0"


def test_transition_snapshot_invalid_shape_raise():
    """TransitionPosteriorSnapshot 非法 shape (mean 2D / count 3D 不匹配) → raise ValueError."""
    mean = np.full((4, 10), 0.25)  # 2D, 错
    count = np.zeros((4, 4, 10), dtype=int)
    with pytest.raises(ValueError, match="必须是 3D"):
        TransitionPosteriorSnapshot(mean=mean, count=count, alpha0=1.0)


# ---------------------------------------------------------------------------
# 2. RewardPosteriorSnapshot dataclass shape (2 tests)
# ---------------------------------------------------------------------------


def test_reward_snapshot_basic_shape():
    """RewardPosteriorSnapshot 基本字段: 2D mean/alpha/beta/variance + alpha0 + schema_version."""
    mean = np.full((4, 10), 0.5)
    alpha = np.ones((4, 10))
    beta = np.ones((4, 10))
    variance = np.zeros((4, 10))
    R = RewardPosteriorSnapshot(
        mean=mean, alpha=alpha, beta=beta, alpha0=1.0, variance=variance,
    )
    assert R.mean.shape == (4, 10)
    assert R.alpha.shape == (4, 10)
    assert R.beta.shape == (4, 10)
    assert R.variance.shape == (4, 10)
    assert R.alpha0 == 1.0
    assert R.schema_version == "0.93.0"


def test_reward_snapshot_invalid_shape_raise():
    """RewardPosteriorSnapshot alpha.shape != mean.shape → raise ValueError."""
    mean = np.full((4, 10), 0.5)
    alpha = np.ones((5, 10))  # shape mismatch
    beta = np.ones((4, 10))
    variance = np.zeros((4, 10))
    with pytest.raises(ValueError, match="alpha shape != mean.shape"):
        RewardPosteriorSnapshot(
            mean=mean, alpha=alpha, beta=beta, alpha0=1.0, variance=variance,
        )


# ---------------------------------------------------------------------------
# 3. POMDPDiagnostic dataclass shape (1 test)
# ---------------------------------------------------------------------------


def test_pomdp_diagnostic_basic_shape():
    """POMDPDiagnostic 基本字段: 1D belief + 2D coverage + most_likely_state + last_updated."""
    T = TransitionPosteriorSnapshot(
        mean=np.full((4, 4, 10), 0.25),
        count=np.zeros((4, 4, 10), dtype=int),
        alpha0=1.0,
    )
    R = RewardPosteriorSnapshot(
        mean=np.full((4, 10), 0.5),
        alpha=np.ones((4, 10)),
        beta=np.ones((4, 10)),
        alpha0=1.0,
        variance=np.zeros((4, 10)),
    )
    diag = POMDPDiagnostic(
        T=T, R=R,
        belief=np.array([0.1, 0.5, 0.2, 0.2]),
        coverage=np.zeros((4, 10), dtype=int),
        most_likely_state=1,
        last_updated=datetime.now(),
    )
    assert diag.belief.shape == (4,)
    assert diag.coverage.shape == (4, 10)
    assert diag.most_likely_state == 1
    assert diag.schema_version == "0.93.0"


# ---------------------------------------------------------------------------
# 4. to_dict round-trip (3 tests)
# ---------------------------------------------------------------------------


def test_transition_snapshot_to_dict_round_trip():
    """TransitionPosteriorSnapshot to_dict / from_dict round-trip."""
    mean = np.full((4, 4, 10), 0.25)
    count = np.zeros((4, 4, 10), dtype=int)
    count[0, 0, 0] = 5  # 加一点非零值测 round-trip
    T = TransitionPosteriorSnapshot(mean=mean, count=count, alpha0=1.0)
    d = T.to_dict()
    T2 = TransitionPosteriorSnapshot.from_dict(d)
    np.testing.assert_array_equal(T.mean, T2.mean)
    np.testing.assert_array_equal(T.count, T2.count)
    assert T.alpha0 == T2.alpha0
    assert T.schema_version == T2.schema_version


def test_reward_snapshot_to_dict_round_trip():
    """RewardPosteriorSnapshot to_dict / from_dict round-trip."""
    mean = np.full((4, 10), 0.5)
    alpha = np.full((4, 10), 2.0)
    beta = np.full((4, 10), 3.0)
    variance = np.full((4, 10), 0.05)
    R = RewardPosteriorSnapshot(
        mean=mean, alpha=alpha, beta=beta, alpha0=1.0, variance=variance,
    )
    d = R.to_dict()
    R2 = RewardPosteriorSnapshot.from_dict(d)
    np.testing.assert_array_almost_equal(R.mean, R2.mean)
    np.testing.assert_array_almost_equal(R.alpha, R2.alpha)
    np.testing.assert_array_almost_equal(R.beta, R2.beta)
    np.testing.assert_array_almost_equal(R.variance, R2.variance)
    assert R.alpha0 == R2.alpha0


def test_pomdp_diagnostic_to_dict_round_trip():
    """POMDPDiagnostic to_dict / from_dict round-trip (含 ndarray + datetime ISO)."""
    T = TransitionPosteriorSnapshot(
        mean=np.full((4, 4, 10), 0.25),
        count=np.zeros((4, 4, 10), dtype=int),
        alpha0=1.0,
    )
    R = RewardPosteriorSnapshot(
        mean=np.full((4, 10), 0.5),
        alpha=np.ones((4, 10)),
        beta=np.ones((4, 10)),
        alpha0=1.0,
        variance=np.zeros((4, 10)),
    )
    diag = POMDPDiagnostic(
        T=T, R=R,
        belief=np.array([0.1, 0.5, 0.2, 0.2]),
        coverage=np.zeros((4, 10), dtype=int),
        most_likely_state=1,
        last_updated=datetime(2026, 8, 12, 0, 0, 0),
    )
    d = diag.to_dict()
    # 验证 JSON 序列化字段
    assert isinstance(d["belief"], list)
    assert isinstance(d["coverage"], list)
    assert isinstance(d["last_updated"], str)
    assert d["schema_version"] == "0.93.0"
    diag2 = POMDPDiagnostic.from_dict(d)
    np.testing.assert_array_almost_equal(diag.belief, diag2.belief)
    np.testing.assert_array_equal(diag.coverage, diag2.coverage)
    assert diag.most_likely_state == diag2.most_likely_state
    assert diag.last_updated == diag2.last_updated


# ---------------------------------------------------------------------------
# 5. schema_version 防御性自检 [5] (1 test)
# ---------------------------------------------------------------------------


def test_pomdp_diagnostic_old_schema_version_raise():
    """POMDPDiagnostic 老 schema_version (0.92.0 / 0.91.0 / 0.90.0) → raise ValueError."""
    with pytest.raises(ValueError, match="schema_version"):
        POMDPDiagnostic(
            T=TransitionPosteriorSnapshot(
                mean=np.full((4, 4, 10), 0.25),
                count=np.zeros((4, 4, 10), dtype=int),
                alpha0=1.0,
            ),
            R=RewardPosteriorSnapshot(
                mean=np.full((4, 10), 0.5),
                alpha=np.ones((4, 10)),
                beta=np.ones((4, 10)),
                alpha0=1.0,
                variance=np.zeros((4, 10)),
            ),
            belief=np.array([0.25, 0.25, 0.25, 0.25]),
            coverage=np.zeros((4, 10), dtype=int),
            most_likely_state=0,
            last_updated=datetime.now(),
            schema_version="0.92.0",  # 老 schema
        )


# ---------------------------------------------------------------------------
# 6. POMDPPolicy.get_diagnostic (3 tests)
# ---------------------------------------------------------------------------


def test_pomdp_policy_get_diagnostic_lazy_init():
    """POMDPPolicy.get_diagnostic() lazy init posterior (未注入) → 返 valid diagnostic."""
    policy = POMDPPolicy(n_arms=10, n_states=4, n_observations=4, seed=42)
    assert policy._transition_posterior is None
    diag = policy.get_diagnostic()
    assert diag.T.mean.shape == (4, 4, 10)
    assert diag.R.mean.shape == (4, 10)
    assert diag.belief.shape == (4,)
    assert diag.coverage.shape == (4, 10)
    # lazy init 已触发
    assert policy._transition_posterior is not None
    assert policy._reward_posterior is not None


def test_pomdp_policy_get_diagnostic_with_posterior():
    """POMDPPolicy.get_diagnostic() posterior 已注入 → T.mean = posterior.mean()."""
    from ecos.lca.l4_optimization.pomdp_learner import (
        RewardPosterior,
        TransitionPosterior,
    )

    policy = POMDPPolicy(n_arms=10, n_states=4, n_observations=4, seed=42)
    # 注入 posterior
    tp_count = np.zeros((4, 4, 10), dtype=int)
    tp_count[0, 0, 0] = 10  # 一个 cell 高 evidence
    policy.set_transition_posterior(TransitionPosterior(count=tp_count))
    rp_alpha = np.full((4, 10), 2.0)
    rp_beta = np.full((4, 10), 3.0)
    policy.set_reward_posterior(RewardPosterior(alpha=rp_alpha, beta=rp_beta))

    diag = policy.get_diagnostic()
    # T.mean[0, 0, 0] = (10 + 1) / Σ(count[:, 0, 0] + 1)  — high prob
    expected_T_000 = 11.0 / (tp_count[:, 0, 0].sum() + 4 * 1.0)
    assert abs(diag.T.mean[0, 0, 0] - expected_T_000) < 1e-6
    # R.mean = α / (α + β) = 2 / 5 = 0.4
    np.testing.assert_array_almost_equal(diag.R.mean, np.full((4, 10), 0.4))


def test_pomdp_policy_get_diagnostic_most_likely_state():
    """POMDPPolicy.get_diagnostic() most_likely_state = argmax(belief)."""
    policy = POMDPPolicy(n_arms=10, n_states=4, n_observations=4, seed=42)
    # 强制设置 belief
    policy.belief_state = np.array([0.1, 0.6, 0.2, 0.1])  # state 1 = 0.6
    diag = policy.get_diagnostic()
    assert diag.most_likely_state == 1


# ---------------------------------------------------------------------------
# 7. POMDPPolicy.get_transition_heatmap (1 test)
# ---------------------------------------------------------------------------


def test_pomdp_policy_get_transition_heatmap_shape():
    """POMDPPolicy.get_transition_heatmap(action) → (n_states, n_states) sum = n_states."""
    policy = POMDPPolicy(n_arms=10, n_states=4, n_observations=4, seed=42)
    heatmap = policy.get_transition_heatmap(2)
    assert heatmap.shape == (4, 4)
    # 每行 sum = 1 (valid stochastic matrix) → 总 sum = n_states
    assert abs(heatmap.sum() - 4.0) < 1e-6


# ---------------------------------------------------------------------------
# 8. POMDPPolicy.get_reward_curves (1 test)
# ---------------------------------------------------------------------------


def test_pomdp_policy_get_reward_curves_keys():
    """POMDPPolicy.get_reward_curves(action) → dict 含 alpha/beta/mean/variance."""
    policy = POMDPPolicy(n_arms=10, n_states=4, n_observations=4, seed=42)
    curves = policy.get_reward_curves(3)
    assert set(curves.keys()) == {"alpha", "beta", "mean", "variance"}
    assert curves["alpha"].shape == (4,)
    assert curves["beta"].shape == (4,)
    assert curves["mean"].shape == (4,)
    assert curves["variance"].shape == (4,)
    # lazy init: posterior 注入前 alpha=beta=1 → mean=0.5
    np.testing.assert_array_almost_equal(curves["mean"], np.full(4, 0.5))


# ---------------------------------------------------------------------------
# 9. POMDPDiagnostic frozen (1 test)
# ---------------------------------------------------------------------------


def test_pomdp_diagnostic_frozen_immutable():
    """POMDPDiagnostic frozen → 字段 mutation 抛 FrozenInstanceError."""
    T = TransitionPosteriorSnapshot(
        mean=np.full((4, 4, 10), 0.25),
        count=np.zeros((4, 4, 10), dtype=int),
        alpha0=1.0,
    )
    R = RewardPosteriorSnapshot(
        mean=np.full((4, 10), 0.5),
        alpha=np.ones((4, 10)),
        beta=np.ones((4, 10)),
        alpha0=1.0,
        variance=np.zeros((4, 10)),
    )
    diag = POMDPDiagnostic(
        T=T, R=R,
        belief=np.array([0.25, 0.25, 0.25, 0.25]),
        coverage=np.zeros((4, 10), dtype=int),
        most_likely_state=0,
        last_updated=datetime.now(),
    )
    with pytest.raises((AttributeError, Exception)) as exc_info:
        diag.belief = np.array([0.1, 0.2, 0.3, 0.4])
    # frozen dataclass raise FrozenInstanceError (cannot assign to field 'belief')
    err_msg = str(exc_info.value).lower()
    assert ("frozen" in err_msg or "cannot assign" in err_msg
            or "FrozenInstance" in str(exc_info.value))


# ---------------------------------------------------------------------------
# 10. coverage 派生 (1 test)
# ---------------------------------------------------------------------------


def test_pomdp_policy_coverage_derives_from_posterior():
    """POMDPDiagnostic.coverage = transition_posterior.count.sum(axis=0) per (s, a)."""
    policy = POMDPPolicy(n_arms=10, n_states=4, n_observations=4, seed=42)
    # Trigger 5 updates with varying (arm, observation)
    for i in range(5):
        policy.update(arm=i % 10, reward=0.6, observation=i % 4)
    diag = policy.get_diagnostic()
    # coverage 总样本数 = sum count
    assert diag.coverage.sum() == 5
    # coverage shape (n_states, n_arms)
    assert diag.coverage.shape == (4, 10)


# ---------------------------------------------------------------------------
# 11. _compute_beta_variance (1 test)
# ---------------------------------------------------------------------------


def test_compute_beta_variance_uniform_prior():
    """_compute_beta_variance(α=1, β=1) uniform prior → variance = 1/12 ≈ 0.0833."""
    alpha = np.ones((4, 10))
    beta = np.ones((4, 10))
    var = _compute_beta_variance(alpha, beta)
    # Beta(1, 1) variance = αβ / ((α+β)² (α+β+1)) = 1 / (2² × 3) = 1/12
    expected = 1.0 / (4.0 * 3.0)
    np.testing.assert_array_almost_equal(var, np.full((4, 10), expected))


def test_schema_version_constant():
    """SCHEMA_VERSION = '0.93.0' (跟 POMDPPolicy + CognitiveTwinAgent 同步)."""
    assert SCHEMA_VERSION == "0.93.0"