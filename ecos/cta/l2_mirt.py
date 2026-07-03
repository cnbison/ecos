"""L2 状态估计层：5D MIRT (Multi-dimensional Item Response Theory).

对应 research/10-engineering/01-cta-belief-engine.md §5.1.

M2 W1 范围：Bi-factor 5D MIRT 的 MAP（最大后验）估计。
Phase 5+ 才实现完整 EM（同时估计题目参数 a/d 与学生 θ）。

Bi-factor 结构（v0.1.0 简化版）：
  θ ∈ ℝ⁵ —— 5 个特化维度 (K/P/S/C/X)
  G ∈ ℝ  —— 一般因子（M2 W1 用 mean(θ) 近似；Phase 4+ 改为独立变量）

  P(correct | θ, a_sp, a_g, d) = sigmoid(a_sp · θ + a_g · G - d)

参考 v0.3.0 §1 MIRT 核心。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit  # sigmoid


@dataclass
class MIRTItemParams:
    """单题的 MIRT 参数.

    Attributes:
        problem_id: 题目标识
        a_specialized: 5D 特化区分度向量 ∈ ℝ⁵
        a_general: 一般因子区分度（标量）
        difficulty: 难度参数（标量，ℝ）
    """

    problem_id: str
    a_specialized: np.ndarray  # shape (5,)
    a_general: float = 0.0
    difficulty: float = 0.0


@dataclass
class MIRTConfig:
    """L2 层配置."""

    theta_dim: int = 5  # 5D 状态
    # MAP 先验——冷启动用
    prior_mean: np.ndarray = field(default_factory=lambda: np.zeros(5))
    prior_cov: np.ndarray = field(default_factory=lambda: np.eye(5))
    # 题目参数默认（无独立参数时用）
    default_a_specialized: np.ndarray = field(default_factory=lambda: np.ones(5) * 0.8)
    default_a_general: float = 0.5
    default_difficulty: float = 0.0


class BiFactorMIRT5D:
    """Bi-factor 5D MIRT（M2 W1 简化版）.

    单学生 MAP 估计 + 多学生 EM 协调骨架（EM 完整版待 Phase 5+）。
    """

    def __init__(self, config: MIRTConfig | None = None) -> None:
        self.config = config or MIRTConfig()
        # 题目参数库（problem_id → MIRTItemParams）
        self.item_params: Dict[str, MIRTItemParams] = {}

    def register_item(self, params: MIRTItemParams) -> None:
        """注册题目参数."""
        self.item_params[params.problem_id] = params

    def register_items_bulk(self, params_list: List[MIRTItemParams]) -> None:
        for p in params_list:
            self.register_item(p)

    def default_item_params(self, problem_id: str) -> MIRTItemParams:
        """生成默认题目参数（未注册题目使用）."""
        return MIRTItemParams(
            problem_id=problem_id,
            a_specialized=self.config.default_a_specialized.copy(),
            a_general=self.config.default_a_general,
            difficulty=self.config.default_difficulty,
        )

    def get_item_params(self, problem_id: str) -> MIRTItemParams:
        return self.item_params.get(problem_id, self.default_item_params(problem_id))

    @staticmethod
    def predict_probability(theta: np.ndarray, item: MIRTItemParams) -> float:
        """预测学生答对该题的概率 P(correct | θ, item)."""
        g = float(np.mean(theta))  # 一般因子（M2 W1 简化）
        logit = float(np.dot(item.a_specialized, theta)) + item.a_general * g - item.difficulty
        return float(expit(logit))

    @staticmethod
    def predict_probabilities(theta: np.ndarray, items: List[MIRTItemParams]) -> np.ndarray:
        """批量预测多个题目的 P(correct)."""
        probs = np.empty(len(items))
        for i, item in enumerate(items):
            probs[i] = BiFactorMIRT5D.predict_probability(theta, item)
        return probs

    def estimate_theta(
        self,
        responses: np.ndarray,  # shape (n_items,), 0/1
        problem_ids: List[str],
    ) -> Tuple[np.ndarray, np.ndarray]:
        """MAP 估计单个学生的 5D θ.

        优化目标（负对数后验）：
          L(θ) = -Σ log P(r_i | θ, item_i) - log P(θ)  (prior: N(μ, Σ))

        Returns:
            theta_hat: 估计的 5D θ
            theta_cov: 估计的协方差（基于 Hessian 逆）
        """
        if len(responses) != len(problem_ids):
            raise ValueError("responses and problem_ids must have same length")

        if len(responses) == 0:
            return self.config.prior_mean.copy(), self.config.prior_cov.copy()

        items = [self.get_item_params(pid) for pid in problem_ids]
        responses = np.asarray(responses, dtype=float)

        prior_mean = self.config.prior_mean
        prior_cov_inv = np.linalg.inv(self.config.prior_cov)

        def neg_log_posterior(theta: np.ndarray) -> float:
            # 似然项
            probs = self.predict_probabilities(theta, items)
            # 数值保护：clip 避免 log(0)
            probs = np.clip(probs, 1e-9, 1.0 - 1e-9)
            log_lik = float(np.sum(responses * np.log(probs) + (1.0 - responses) * np.log(1.0 - probs)))
            # 先验项
            diff = theta - prior_mean
            log_prior = -0.5 * float(diff @ prior_cov_inv @ diff)
            return -(log_lik + log_prior)

        def neg_log_posterior_grad(theta: np.ndarray) -> np.ndarray:
            # 数值梯度（scipy 简化；后续可换解析梯度）
            eps = 1e-5
            grad = np.zeros_like(theta)
            f0 = neg_log_posterior(theta)
            for i in range(len(theta)):
                theta_p = theta.copy()
                theta_p[i] += eps
                grad[i] = (neg_log_posterior(theta_p) - f0) / eps
            return grad

        x0 = self.config.prior_mean.copy()
        result = minimize(
            neg_log_posterior,
            x0,
            jac=neg_log_posterior_grad,
            method="L-BFGS-B",
            options={"maxiter": 200, "ftol": 1e-6},
        )

        theta_hat = result.x
        # 协方差用 Hessian 逆近似（数值）
        eps = 1e-4
        n = len(theta_hat)
        hessian = np.zeros((n, n))
        f0 = neg_log_posterior(theta_hat)
        for i in range(n):
            for j in range(n):
                theta_pp = theta_hat.copy()
                theta_pp[i] += eps
                theta_pp[j] += eps
                theta_pm = theta_hat.copy()
                theta_pm[i] += eps
                theta_pm[j] -= eps
                theta_mp = theta_hat.copy()
                theta_mp[i] -= eps
                theta_mp[j] += eps
                theta_mm = theta_hat.copy()
                theta_mm[i] -= eps
                theta_mm[j] -= eps
                hessian[i, j] = (
                    neg_log_posterior(theta_pp)
                    - neg_log_posterior(theta_pm)
                    - neg_log_posterior(theta_mp)
                    + neg_log_posterior(theta_mm)
                ) / (4.0 * eps * eps)
        try:
            theta_cov = np.linalg.inv(hessian)
            # 对角线保正（数值稳定）
            diag = np.diag(theta_cov).copy()
            diag = np.where(diag > 0, diag, 1.0)
            theta_cov = np.diag(diag)
        except np.linalg.LinAlgError:
            theta_cov = self.config.prior_cov.copy()

        return theta_hat, theta_cov

    def update(
        self,
        responses: np.ndarray,  # shape (n_students, n_items)
        problem_ids: List[str],
    ) -> Tuple[np.ndarray, np.ndarray]:
        """完整 EM 协调骨架.

        单学生场景：直接调 estimate_theta。
        多学生场景（M2 W1 简化）：逐学生调用 estimate_theta 后堆叠。

        Returns:
            theta_mean: (n_students, 5)
            theta_cov: (n_students, 5, 5)
        """
        responses = np.atleast_2d(responses)
        n_students = responses.shape[0]
        theta_means = np.zeros((n_students, 5))
        theta_covs = np.zeros((n_students, 5, 5))

        for s in range(n_students):
            theta_hat, theta_cov = self.estimate_theta(responses[s], problem_ids)
            theta_means[s] = theta_hat
            theta_covs[s] = theta_cov

        return theta_means, theta_covs