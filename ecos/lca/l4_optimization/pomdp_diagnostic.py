"""POMDP 诊断数据结构 (v0.93.0-a, Phase 7+ 抽象推演 #6).

对应设计: discussions/2026-08-12-v093-design.md §2.

v0.93.0-a 范围 (Phase 7+ 第 6 个 sub-version, POMDP T/R 后验可视化 #1):
  - **TransitionPosteriorSnapshot** (frozen dataclass, 跟 v0.89.0-a AlphaVector / v0.91.0-a HumanFeedbackEntry 同模式):
    - mean (3D ndarray) + count (3D ndarray) + alpha0 (float) + schema_version="0.93.0"
    - to_dict / from_dict round-trip + schema_version 校验
    - 派生 from POMDPPolicy._transition_posterior (lazy / 已注入)
  - **RewardPosteriorSnapshot** (frozen dataclass, 跟 TransitionPosteriorSnapshot 同模式):
    - mean (2D ndarray) + alpha (2D ndarray) + beta (2D ndarray) + alpha0 (float) + variance (2D ndarray) + schema_version="0.93.0"
    - variance = αβ / ((α+β)² (α+β+1)) (Beta 后验方差)
  - **POMDPDiagnostic** (frozen dataclass, 三件套 + coverage):
    - T: TransitionPosteriorSnapshot
    - R: RewardPosteriorSnapshot
    - belief (1D ndarray n_states) + coverage (2D ndarray n_states × n_arms) + most_likely_state (int) + last_updated (datetime)
    - schema_version="0.93.0"
    - to_dict / from_dict round-trip (JSON 可序列化)

防御性自检:
  - [1] silent pass: 越界 / 非法 shape raise ValueError
  - [5] schema_version: from_dict 校验 "0.93.0", 老版本 raise
  - [8] direct state mutation: POMDPDiagnostic 不持有 BeliefState 引用, 0 新 mutation site

后续 (b/c/d):
  - b 阶段: Runtime.diagnose_pomdp + LCAEngine.get_pomdp_diagnostic + Plugin SDK 第 8 subscriber
  - c 阶段: 演化追踪 (timed snapshots N=50/K=10) + 持久化 (LCAStore pomdp_diagnostic 列 + SCHEMA 0.93.0)
  - d 阶段: H3-c4 canary + 老 v0.92 snapshot graceful skip + docs/pomdp_diagnostic.md + examples/

约定:
  - T snapshot.count 跟 POMDPPolicy.transition_count 字段对齐 (v0.90.0-b 持久化)
  - R snapshot.alpha / beta 跟 POMDPPolicy.reward_alpha / reward_beta 字段对齐
  - belief 直接来自 POMDPPolicy.belief_state (1D, n_states)
  - coverage = transition_posterior.total_evidence() per (s, a) 派生 (v0.90.0-d total_evidence pattern)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict

import numpy as np

_log = logging.getLogger(__name__)

# v0.93.0-a: 独立 schema version (跟 POMDPPolicy "0.93.0" + CognitiveTwinAgent "0.93.0" 同步)
SCHEMA_VERSION = "0.93.0"


@dataclass(frozen=True)
class TransitionPosteriorSnapshot:
    """T(s'|s, a) Dirichlet 后验 snapshot (v0.93.0-a).

    派生 from POMDPPolicy._transition_posterior:
      - mean = posterior.mean() (n_states × n_states × n_arms)
      - count = posterior.count (3D, 持久化字段)
      - alpha0 = posterior.alpha0 (uniform prior 默认 1.0)

    frozen (跟 AlphaVector / HumanFeedbackEntry 同模式): 防止外部 mutation 干扰.
    派生走 POMDPPolicy.get_diagnostic() 单一入口, 不持有 BeliefState 引用.
    """

    mean: np.ndarray  # shape (n_states, n_states, n_arms)
    count: np.ndarray  # shape (n_states, n_states, n_arms), int dtype
    alpha0: float
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        # Convert list/tuple to ndarray (允许 from_dict 传入 list)
        if not isinstance(self.mean, np.ndarray):
            object.__setattr__(self, "mean", np.asarray(self.mean, dtype=float))
        if not isinstance(self.count, np.ndarray):
            object.__setattr__(self, "count", np.asarray(self.count, dtype=int))

        # 防御性自检 [1] (silent pass 防御): shape 校验 raise
        if self.mean.ndim != 3:
            raise ValueError(
                f"TransitionPosteriorSnapshot.mean 必须是 3D (n_states × n_states × n_arms), "
                f"got shape={self.mean.shape}"
            )
        if self.count.ndim != 3:
            raise ValueError(
                f"TransitionPosteriorSnapshot.count 必须是 3D (n_states × n_states × n_arms), "
                f"got shape={self.count.shape}"
            )
        if self.mean.shape != self.count.shape:
            raise ValueError(
                f"TransitionPosteriorSnapshot.mean shape != count.shape "
                f"(mean={self.mean.shape}, count={self.count.shape})"
            )
        if (self.count < 0).any():
            raise ValueError(
                f"TransitionPosteriorSnapshot.count 不能为负 (got min={self.count.min()})"
            )
        if self.alpha0 <= 0:
            raise ValueError(
                f"TransitionPosteriorSnapshot.alpha0 必须 > 0 (got={self.alpha0})"
            )
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"TransitionPosteriorSnapshot.schema_version 必须是 {SCHEMA_VERSION!r}, "
                f"got={self.schema_version!r}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """JSON 可序列化 dict (含 ndarray → list + schema_version 校验)."""
        return {
            "mean": self.mean.tolist(),
            "count": self.count.tolist(),
            "alpha0": float(self.alpha0),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, state: Dict[str, Any]) -> "TransitionPosteriorSnapshot":
        """从 dict 重建 (防御性自检 [5]: schema_version 校验 raise)."""
        schema_version = state.get("schema_version")
        if schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"TransitionPosteriorSnapshot schema_version 不匹配: "
                f"expected={SCHEMA_VERSION!r}, got={schema_version!r}. "
                f"老 snapshot 不兼容, 需要迁移或丢弃."
            )
        return cls(
            mean=state["mean"],  # __post_init__ 转为 ndarray
            count=state["count"],
            alpha0=float(state["alpha0"]),
            schema_version=schema_version,
        )


@dataclass(frozen=True)
class RewardPosteriorSnapshot:
    """R(s, a) Beta 后验 snapshot (v0.93.0-a).

    派生 from POMDPPolicy._reward_posterior:
      - mean = posterior.mean() (n_states × n_arms)
      - alpha / beta (2D ndarray, 持久化字段)
      - alpha0 (uniform prior 默认 1.0)
      - variance = αβ / ((α+β)² (α+β+1)) (Beta 后验方差, 派生)

    frozen (跟 TransitionPosteriorSnapshot / AlphaVector 同模式).
    """

    mean: np.ndarray  # shape (n_states, n_arms)
    alpha: np.ndarray  # shape (n_states, n_arms), float dtype
    beta: np.ndarray  # shape (n_states, n_arms), float dtype
    alpha0: float
    variance: np.ndarray  # shape (n_states, n_arms), 派生
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        # Convert to ndarray
        if not isinstance(self.mean, np.ndarray):
            object.__setattr__(self, "mean", np.asarray(self.mean, dtype=float))
        if not isinstance(self.alpha, np.ndarray):
            object.__setattr__(self, "alpha", np.asarray(self.alpha, dtype=float))
        if not isinstance(self.beta, np.ndarray):
            object.__setattr__(self, "beta", np.asarray(self.beta, dtype=float))
        if not isinstance(self.variance, np.ndarray):
            object.__setattr__(self, "variance", np.asarray(self.variance, dtype=float))

        # 防御性自检 [1]: shape 校验 raise
        if self.mean.ndim != 2:
            raise ValueError(
                f"RewardPosteriorSnapshot.mean 必须是 2D (n_states × n_arms), "
                f"got shape={self.mean.shape}"
            )
        if self.alpha.shape != self.mean.shape:
            raise ValueError(
                f"RewardPosteriorSnapshot.alpha shape != mean.shape "
                f"(alpha={self.alpha.shape}, mean={self.mean.shape})"
            )
        if self.beta.shape != self.mean.shape:
            raise ValueError(
                f"RewardPosteriorSnapshot.beta shape != mean.shape "
                f"(beta={self.beta.shape}, mean={self.mean.shape})"
            )
        if self.variance.shape != self.mean.shape:
            raise ValueError(
                f"RewardPosteriorSnapshot.variance shape != mean.shape "
                f"(variance={self.variance.shape}, mean={self.mean.shape})"
            )
        if (self.alpha <= 0).any() or (self.beta <= 0).any():
            raise ValueError(
                f"RewardPosteriorSnapshot.alpha/beta 必须 > 0 "
                f"(alpha min={self.alpha.min()}, beta min={self.beta.min()})"
            )
        if (self.variance < 0).any():
            raise ValueError(
                f"RewardPosteriorSnapshot.variance 不能为负 (got min={self.variance.min()})"
            )
        if self.alpha0 <= 0:
            raise ValueError(
                f"RewardPosteriorSnapshot.alpha0 必须 > 0 (got={self.alpha0})"
            )
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"RewardPosteriorSnapshot.schema_version 必须是 {SCHEMA_VERSION!r}, "
                f"got={self.schema_version!r}"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mean": self.mean.tolist(),
            "alpha": self.alpha.tolist(),
            "beta": self.beta.tolist(),
            "alpha0": float(self.alpha0),
            "variance": self.variance.tolist(),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, state: Dict[str, Any]) -> "RewardPosteriorSnapshot":
        schema_version = state.get("schema_version")
        if schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"RewardPosteriorSnapshot schema_version 不匹配: "
                f"expected={SCHEMA_VERSION!r}, got={schema_version!r}"
            )
        return cls(
            mean=state["mean"],
            alpha=state["alpha"],
            beta=state["beta"],
            alpha0=float(state["alpha0"]),
            variance=state["variance"],
            schema_version=schema_version,
        )


def _compute_beta_variance(alpha: np.ndarray, beta: np.ndarray) -> np.ndarray:
    """派生 Beta 后验方差: var = αβ / ((α+β)² (α+β+1)).

    Args:
        alpha: Beta α 参数 (n_states × n_arms), > 0
        beta:  Beta β 参数 (n_states × n_arms), > 0

    Returns:
        variance ndarray 同 shape, >= 0
    """
    alpha_plus_beta = alpha + beta
    numerator = alpha * beta
    denominator = (alpha_plus_beta ** 2) * (alpha_plus_beta + 1.0)
    # 防御性: denominator 接近 0 时返 0 (避免 NaN)
    variance = np.where(
        denominator > 1e-10,
        numerator / np.maximum(denominator, 1e-10),
        0.0,
    )
    return variance.astype(float)


@dataclass(frozen=True)
class POMDPDiagnostic:
    """POMDP 诊断 surface (v0.93.0-a).

    一次性暴露 POMDP 全部可观测字段:
      - T: TransitionPosteriorSnapshot (Dirichlet 后验)
      - R: RewardPosteriorSnapshot (Beta 后验)
      - belief: 4 状态 posterior (POMDPPolicy.belief_state 一致)
      - coverage: per (s, a) 样本数 (transition_posterior.total_evidence() 派生)
      - most_likely_state: argmax(belief)
      - last_updated: datetime (调用时算, 不持久化)
      - schema_version: "0.93.0"

    v0.95+ Teacher/Parent Dashboard 可直接 to_dict() 反序列化渲染.

    frozen (跟 TransitionPosteriorSnapshot / RewardPosteriorSnapshot 同模式):
    派生走 POMDPPolicy.get_diagnostic() 单一入口, 不持有 BeliefState 引用.

    防御性自检 [8]: POMDPDiagnostic 不持有 BeliefState 引用, 0 新 mutation site.
    """

    T: TransitionPosteriorSnapshot
    R: RewardPosteriorSnapshot
    belief: np.ndarray  # shape (n_states,)
    coverage: np.ndarray  # shape (n_states, n_arms)
    most_likely_state: int
    last_updated: datetime
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        # Convert to ndarray
        if not isinstance(self.belief, np.ndarray):
            object.__setattr__(self, "belief", np.asarray(self.belief, dtype=float))
        if not isinstance(self.coverage, np.ndarray):
            object.__setattr__(self, "coverage", np.asarray(self.coverage, dtype=int))

        # 防御性自检 [1]: shape 校验 raise
        if self.belief.ndim != 1:
            raise ValueError(
                f"POMDPDiagnostic.belief 必须是 1D (n_states,), "
                f"got shape={self.belief.shape}"
            )
        if self.coverage.ndim != 2:
            raise ValueError(
                f"POMDPDiagnostic.coverage 必须是 2D (n_states × n_arms), "
                f"got shape={self.coverage.shape}"
            )
        if abs(self.belief.sum() - 1.0) > 1e-6:
            raise ValueError(
                f"POMDPDiagnostic.belief 必须归一化 (sum=1.0), got sum={self.belief.sum()}"
            )
        if (self.coverage < 0).any():
            raise ValueError(
                f"POMDPDiagnostic.coverage 不能为负 (got min={self.coverage.min()})"
            )
        if self.T.mean.shape[0] != self.belief.shape[0]:
            raise ValueError(
                f"POMDPDiagnostic.T.n_states={self.T.mean.shape[0]} 跟 belief.n_states={self.belief.shape[0]} 不匹配"
            )
        if self.R.mean.shape != self.coverage.shape:
            raise ValueError(
                f"POMDPDiagnostic.R.shape={self.R.mean.shape} 跟 coverage.shape={self.coverage.shape} 不匹配"
            )
        if not (0 <= self.most_likely_state < self.belief.shape[0]):
            raise ValueError(
                f"POMDPDiagnostic.most_likely_state={self.most_likely_state} 越界 [0, {self.belief.shape[0]})"
            )
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"POMDPDiagnostic.schema_version 必须是 {SCHEMA_VERSION!r}, "
                f"got={self.schema_version!r}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """JSON 可序列化 dict (含 ndarray → list + datetime ISO + schema_version)."""
        return {
            "T": self.T.to_dict(),
            "R": self.R.to_dict(),
            "belief": self.belief.tolist(),
            "coverage": self.coverage.tolist(),
            "most_likely_state": int(self.most_likely_state),
            "last_updated": self.last_updated.isoformat(),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, state: Dict[str, Any]) -> "POMDPDiagnostic":
        """从 dict 重建 (防御性自检 [5]: schema_version 校验 raise)."""
        schema_version = state.get("schema_version")
        if schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"POMDPDiagnostic schema_version 不匹配: "
                f"expected={SCHEMA_VERSION!r}, got={schema_version!r}. "
                f"老 snapshot 不兼容, 需要迁移或丢弃."
            )
        return cls(
            T=TransitionPosteriorSnapshot.from_dict(state["T"]),
            R=RewardPosteriorSnapshot.from_dict(state["R"]),
            belief=state["belief"],
            coverage=state["coverage"],
            most_likely_state=int(state["most_likely_state"]),
            last_updated=datetime.fromisoformat(state["last_updated"]),
            schema_version=schema_version,
        )


__all__ = [
    "POMDPDiagnostic",
    "TransitionPosteriorSnapshot",
    "RewardPosteriorSnapshot",
    "SCHEMA_VERSION",
    "_compute_beta_variance",
]