"""v0.72.0 P0-i: V3 confidence 后校准 (Platt Scaling).

触发:
  v0.71.0 P0-g 修 LinUCB A 矩阵爆炸后, V3 ECE = 0.57 (阈值 0.10).
  Reliability diagram 诊断 (§discussions/2026-08-03-v0710-reliability-diagram-diagnosis.md) 显示
  V3 全局系统性低估 0.54 (平均 conf 0.32 vs 平均 acc 0.85).
  所有 V3 预测集中在 [0.1, 0.4] 区间, 没有任何样本 > 0.4.

  根因: LinUCB 线性模型 + 16 维 + 54 样本数学上拟合不了 lbc003 高 baseline (0.85).
  模型本身不可信, 但修复 BUG 后已经学到一些信息 (gap -0.46 < -0.72 cold start).

方案 A: Platt Scaling (per-student 后校准)
  P(actual=1 | raw_conf) = sigmoid(A * raw_conf + B)
  通过 MLE 拟合 (raw_conf, actual_outcome) pairs.
  经典 calibration 方案, 工业级验证 (Platt 1999).

用法:
  tracker = StudentCalibrationTracker(min_samples_to_fit=5)
  tracker.add_pair(raw_conf=0.32, actual_outcome=1.0)  # 第 1 次
  tracker.add_pair(raw_conf=0.28, actual_outcome=0.0)  # 第 2 次
  ...
  calibrated = tracker.calibrate(0.30)  # 返回 sigmoid(A*0.30 + B)

设计:
  - 每学生独立 scaler (calibration 跨学生可能漂移)
  - 冷启动期 (n_samples < min_samples_to_fit, 默认 5): 返回 raw_conf (不变)
  - 每次 add_pair 触发 refit (数据量小, refit 成本可忽略)
  - 失败兜底: 任何 scipy 优化失败 -> _log.warning + 返回 raw_conf (不破坏 V3 已有路径)

防御性自检 [1]: 任何失败 _log.warning, 不 raise, 不 silent pass
防御性自检 [6]: 失败不污染 in-memory state
"""

from __future__ import annotations

import logging
from typing import List, Tuple

import numpy as np
from scipy.optimize import minimize

_log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# 1. PlattScaler 核心
# ──────────────────────────────────────────────────────────────────────


class PlattScaler:
    """Platt Scaling 校准器: P(actual=1 | raw_conf) = sigmoid(A * raw_conf + B).

    通过最大化 log-likelihood 拟合 (raw_conf, actual_outcome) pairs:
      max sum[ actual * log(sigmoid(A*raw + B)) + (1-actual) * log(1 - sigmoid(A*raw + B)) ]

    Attributes:
        A: 斜率 (raw_conf -> calibrated 映射的斜率, 默认 1.0)
        B: 截距 (calibrated 偏移, 默认 0.0)
        _fitted: 是否已 fitted (True 后才能 transform)
    """

    def __init__(self):
        self.A: float = 1.0
        self.B: float = 0.0
        self._fitted: bool = False

    def fit(self, raw_confs, actuals) -> "PlattScaler":
        """最大似然拟合 sigmoid 参数 (A, B).

        Args:
            raw_confs: List/array of raw V3 confidence (float, [0, 1])
            actuals: List/array of actual outcome (float, {0.0, 1.0} 或 [0, 1] partial credit)

        Returns:
            self (链式调用)

        Notes:
            - 样本 < 2: 跳过拟合, 保持 identity (A=1, B=0)
            - 优化失败: _log.warning, 保持 identity, 不 raise
        """
        raw_confs = np.asarray(raw_confs, dtype=float)
        actuals = np.asarray(actuals, dtype=float)

        if len(raw_confs) < 2 or len(actuals) < 2:
            _log.debug(
                "PlattScaler.fit: 样本数 %s < 2, 跳过拟合 (保持 identity)",
                len(raw_confs),
            )
            return self

        if len(raw_confs) != len(actuals):
            _log.warning(
                "PlattScaler.fit: raw_confs (%s) 和 actuals (%s) 长度不一致, 跳过拟合",
                len(raw_confs), len(actuals),
            )
            return self

        try:
            def neg_log_lik(params):
                a, b = params
                z = a * raw_confs + b
                # numerically stable: log(sigmoid(z)) = -softplus(-z)
                # log(1 - sigmoid(z)) = -softplus(z)
                ll = np.sum(
                    actuals * (-np.logaddexp(0, -z))
                    + (1.0 - actuals) * (-np.logaddexp(0, z))
                )
                return -ll

            result = minimize(
                neg_log_lik,
                x0=[1.0, 0.0],
                method="Nelder-Mead",
                options={"xatol": 1e-4, "fatol": 1e-4, "maxiter": 200},
            )

            if result.success or result.fun < neg_log_lik([1.0, 0.0]):
                # 即使 result.success=False, 但目标函数有改善, 也接受
                self.A, self.B = float(result.x[0]), float(result.x[1])
                self._fitted = True
            else:
                _log.warning(
                    "PlattScaler.fit: scipy 优化失败 (status=%s, fun=%s), 保持 identity",
                    result.status, result.fun,
                )
        except Exception:
            _log.warning(
                "PlattScaler.fit: 异常, 保持 identity (A=1, B=0)",
                exc_info=True,
            )

        return self

    def transform(self, raw_conf: float) -> float:
        """校准单个 raw_conf.

        Args:
            raw_conf: V3 原始 confidence (float, [0, 1])

        Returns:
            calibrated confidence (float, (0, 1))
            若未 fitted, 返回 clip(raw_conf, 0, 1) (等价于不校准)
        """
        if not self._fitted:
            return float(np.clip(raw_conf, 0.0, 1.0))

        z = self.A * raw_conf + self.B
        # numerically stable sigmoid (avoid overflow in exp)
        from scipy.special import expit
        return float(expit(z))

    def fit_transform(self, raw_confs, actuals) -> np.ndarray:
        """fit + transform 一次完成.

        Returns:
            np.ndarray of calibrated values
        """
        self.fit(raw_confs, actuals)
        return np.array([self.transform(c) for c in raw_confs])


# ──────────────────────────────────────────────────────────────────────
# 2. StudentCalibrationTracker: 每学生独立 buffer + scaler
# ──────────────────────────────────────────────────────────────────────


class StudentCalibrationTracker:
    """v0.72.0: 每学生 V3 calibration 跟踪器.

    维护 per-student (raw_conf, actual_outcome) 配对 buffer, 触发 refit.
    冷启动期 (n_pairs < min_samples_to_fit): 返回 raw_conf (不校准).
    refit 后: 用 PlattScaler.transform(raw_conf) 校准.

    Attributes:
        min_samples_to_fit: 触发首次 refit 的最小样本数 (默认 5)
        _pairs: List of (raw_conf, actual_outcome)
        _scaler: 当前 PlattScaler 实例
    """

    def __init__(self, min_samples_to_fit: int = 5):
        if min_samples_to_fit < 1:
            raise ValueError(f"min_samples_to_fit 必须 >= 1, got {min_samples_to_fit}")
        self.min_samples_to_fit = min_samples_to_fit
        self._pairs: List[Tuple[float, float]] = []
        self._scaler: PlattScaler = PlattScaler()

    @property
    def n_pairs(self) -> int:
        return len(self._pairs)

    @property
    def is_fitted(self) -> bool:
        return self._scaler._fitted

    def add_pair(self, raw_conf: float, actual_outcome: float) -> None:
        """添加一对 (raw_V3, actual_outcome) 并触发 refit (若够样本).

        Args:
            raw_conf: 原始 V3 confidence (clamp to [0, 1])
            actual_outcome: 答对 outcome (0.0 / 1.0, 或 partial credit [0, 1])
        """
        raw_clamped = float(np.clip(raw_conf, 0.0, 1.0))
        actual_clamped = float(np.clip(actual_outcome, 0.0, 1.0))
        self._pairs.append((raw_clamped, actual_clamped))

        if self.n_pairs >= self.min_samples_to_fit:
            self._refit()

    def _refit(self) -> None:
        """用全部历史 pairs 重训 PlattScaler."""
        if self.n_pairs < 2:
            return
        raw_confs, actuals = zip(*self._pairs)
        # 新建 scaler (避免污染旧 scaler 参数)
        self._scaler = PlattScaler()
        self._scaler.fit(list(raw_confs), list(actuals))

    def calibrate(self, raw_conf: float) -> float:
        """校准 V3 confidence.

        Args:
            raw_conf: 原始 V3 confidence (float, [0, 1])

        Returns:
            calibrated confidence
            - 未 fitted (n_pairs < min_samples_to_fit): 返回 raw_conf (clip 到 [0, 1])
            - fitted: 返回 PlattScaler.transform(raw_conf)
        """
        raw_clamped = float(np.clip(raw_conf, 0.0, 1.0))
        if not self.is_fitted:
            return raw_clamped
        return self._scaler.transform(raw_clamped)

    def get_state(self) -> dict:
        """导出状态 (用于调试 + 持久化)."""
        return {
            "n_pairs": self.n_pairs,
            "is_fitted": self.is_fitted,
            "A": self._scaler.A,
            "B": self._scaler.B,
            "min_samples_to_fit": self.min_samples_to_fit,
        }
