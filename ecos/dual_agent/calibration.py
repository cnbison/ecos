"""v0.72.0+ P0-i: V3 confidence 后校准 (Platt Scaling + Isotonic Regression).

v0.72.0 触发:
  v0.71.0 P0-g 修 LinUCB A 矩阵爆炸后, V3 ECE = 0.57 (阈值 0.10).
  Reliability diagram 诊断 (§discussions/2026-08-03-v0710-reliability-diagram-diagnosis.md) 显示
  V3 全局系统性低估 0.54 (平均 conf 0.32 vs 平均 acc 0.85).
  所有 V3 预测集中在 [0.1, 0.4] 区间, 没有任何样本 > 0.4.

  根因: LinUCB 线性模型 + 16 维 + 54 样本数学上拟合不了 lbc003 高 baseline (0.85).

v0.72.0 方案 A: Platt Scaling (per-student 后校准)
  P(actual=1 | raw_conf) = sigmoid(A * raw_conf + B)
  通过 MLE 拟合 (raw_conf, actual_outcome) pairs.
  经典 calibration 方案, 工业级验证 (Platt 1999).

v0.73.0 方案 A+C 优化:
  1. Isotonic Regression 替代 sigmoid (更灵活, 能 fit 非单调偏差)
     - sklearn.isotonic.IsotonicRegression (PAVA 算法)
     - 单调性保持 (calibration 的核心要求)
     - 需要 20+ pairs (比 Platt 5+ 多, 因为更灵活)
  2. L2 正则化 (Platt 1999 原文) 加到 PlattScaler 损失函数
     - 惩罚 A^2 + B^2, 避免极端参数
     - 防止小样本过拟合

用法:
  tracker = StudentCalibrationTracker(
      min_samples_to_fit_platt=5,
      min_samples_to_fit_isotonic=20,
  )
  tracker.add_pair(raw_conf=0.32, actual_outcome=1.0)
  ...
  calibrated = tracker.calibrate(0.30)  # 自动选 Platt (5-19) 或 Isotonic (20+)

冷启动调度:
  - n_pairs < 5:                       raw V3,        source = "raw_v3"
  - 5 <= n_pairs < 20:                 PlattScaling,  source = "platt_scaling"
  - n_pairs >= 20:                     IsotonicReg,   source = "isotonic_regression"

设计:
  - 每学生独立 tracker (calibration 跨学生可能漂移)
  - 冷启动期: 返回 raw_conf (不变)
  - 每次 add_pair 触发 refit (数据量小, refit 成本可忽略)
  - 失败兜底: 任何 scipy/sklearn 优化失败 -> _log.warning + 返回 raw_conf

防御性自检 [1]: 任何失败 _log.warning, 不 raise, 不 silent pass
防御性自检 [6]: 失败不污染 in-memory state
"""

from __future__ import annotations

import logging
from typing import List, Tuple

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

_log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# 1. PlattScaler (v0.72.0 + v0.73.0 L2 正则化)
# ──────────────────────────────────────────────────────────────────────


class PlattScaler:
    """Platt Scaling 校准器: P(actual=1 | raw_conf) = sigmoid(A * raw_conf + B).

    通过最大化 log-likelihood 拟合 (raw_conf, actual_outcome) pairs:
      max sum[ actual * log(sigmoid(A*raw + B)) + (1-actual) * log(1 - sigmoid(A*raw + B)) ]
                  - l2_lambda * (A^2 + B^2)            # v0.73.0 L2 正则化

    Attributes:
        A: 斜率 (raw_conf -> calibrated 映射的斜率, 默认 1.0)
        B: 截距 (calibrated 偏移, 默认 0.0)
        l2_lambda: L2 正则化系数 (v0.73.0 新增, 默认 0.01)
                   - 0.0: 跟 v0.72.0 行为一致 (无正则化)
                   - 0.01: 轻微正则化, 防止小样本过拟合
                   - 0.1: 强正则化, 参数被强烈拉向 (1, 0)
        _fitted: 是否已 fitted (True 后才能 transform)
    """

    def __init__(self, l2_lambda: float = 0.01):
        if l2_lambda < 0:
            raise ValueError(f"l2_lambda 必须 >= 0, got {l2_lambda}")
        self.A: float = 1.0
        self.B: float = 0.0
        self.l2_lambda: float = l2_lambda
        self._fitted: bool = False

    def fit(self, raw_confs, actuals) -> "PlattScaler":
        """最大似然拟合 sigmoid 参数 (A, B), v0.73.0 加 L2 正则化.

        Args:
            raw_confs: List/array of raw V3 confidence (float, [0, 1])
            actuals: List/array of actual outcome (float, {0.0, 1.0} 或 [0, 1] partial credit)

        Returns:
            self (链式调用)

        Notes:
            - 样本 < 2: 跳过拟合, 保持 identity (A=1, B=0)
            - 优化失败: _log.warning, 保持 identity, 不 raise
            - v0.73.0: 损失函数加 l2_lambda * (A^2 + B^2), 惩罚极端参数
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
                # v0.73.0: L2 正则化 (Platt 1999 原文)
                #   惩罚项 = lambda * (A^2 + B^2)
                l2_penalty = self.l2_lambda * (a * a + b * b)
                return -ll + l2_penalty

            result = minimize(
                neg_log_lik,
                x0=[1.0, 0.0],
                method="Nelder-Mead",
                options={"xatol": 1e-4, "fatol": 1e-4, "maxiter": 200},
            )

            if result.success or result.fun < neg_log_lik([1.0, 0.0]):
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
        return float(expit(z))

    def fit_transform(self, raw_confs, actuals) -> np.ndarray:
        """fit + transform 一次完成.

        Returns:
            np.ndarray of calibrated values
        """
        self.fit(raw_confs, actuals)
        return np.array([self.transform(c) for c in raw_confs])


# ──────────────────────────────────────────────────────────────────────
# 2. IsotonicCalibrator (v0.73.0 新增)
# ──────────────────────────────────────────────────────────────────────


class IsotonicCalibrator:
    """Isotonic Regression 校准器: 单调分段常数函数 (PAVA 算法).

    比 Platt Scaling 更灵活:
      - 不假设 sigmoid 形式
      - 能 fit 任何单调 (或非单调如果 increasing='auto') 偏差模式
      - sklearn.isotonic.IsotonicRegression 工业级实现

    适用场景:
      - 样本量足够 (>= 20 推荐)
      - V3 confidence vs actual outcome 关系非 sigmoid
      - v0.72.0 案例: bin [0.9, 1.0] Platt 高估 0.13, Isotonic 可直接 map 到 0.85

    Attributes:
        _model: sklearn.isotonic.IsotonicRegression 实例 (None until fitted)
        _fitted: 是否已 fitted
    """

    def __init__(self, increasing: bool = True, out_of_bounds: str = "clip"):
        """
        Args:
            increasing: 校准曲线方向 (默认 True, 跟 calibration 假设一致)
            out_of_bounds: 越界处理 ("clip" / "nan"), 默认 "clip" 安全
        """
        if out_of_bounds not in ("clip", "nan"):
            raise ValueError(f"out_of_bounds 必须 'clip' 或 'nan', got {out_of_bounds}")
        self.increasing = increasing
        self.out_of_bounds = out_of_bounds
        self._model = None
        self._fitted: bool = False

    def fit(self, raw_confs, actuals) -> "IsotonicCalibrator":
        """拟合 Isotonic Regression.

        Args:
            raw_confs: List/array of raw V3 confidence (float, [0, 1])
            actuals: List/array of actual outcome (float, [0, 1])

        Returns:
            self (链式调用)

        Notes:
            - 样本 < 2: 跳过拟合, _fitted = False
            - 样本 2-19: PAVA 算法可能过拟合, _log.debug 提示但仍 fit
            - 优化失败: _log.warning, _fitted = False
        """
        raw_confs = np.asarray(raw_confs, dtype=float)
        actuals = np.asarray(actuals, dtype=float)

        if len(raw_confs) < 2 or len(actuals) < 2:
            _log.debug(
                "IsotonicCalibrator.fit: 样本数 %s < 2, 跳过拟合",
                len(raw_confs),
            )
            return self

        if len(raw_confs) != len(actuals):
            _log.warning(
                "IsotonicCalibrator.fit: raw_confs (%s) 和 actuals (%s) 长度不一致, 跳过拟合",
                len(raw_confs), len(actuals),
            )
            return self

        if len(raw_confs) < 20:
            _log.debug(
                "IsotonicCalibrator.fit: 样本数 %s < 20, PAVA 可能过拟合, 谨慎使用",
                len(raw_confs),
            )

        try:
            from sklearn.isotonic import IsotonicRegression
            self._model = IsotonicRegression(
                increasing=self.increasing,
                out_of_bounds=self.out_of_bounds,
                y_min=0.0,
                y_max=1.0,
            )
            self._model.fit(raw_confs, actuals)
            self._fitted = True
        except Exception:
            _log.warning(
                "IsotonicCalibrator.fit: 异常, _fitted = False",
                exc_info=True,
            )
            self._fitted = False

        return self

    def transform(self, raw_conf: float) -> float:
        """校准单个 raw_conf.

        Args:
            raw_conf: V3 原始 confidence (float, [0, 1])

        Returns:
            calibrated confidence (float, (0, 1))
            若未 fitted, 返回 clip(raw_conf, 0, 1)
        """
        if not self._fitted or self._model is None:
            return float(np.clip(raw_conf, 0.0, 1.0))

        return float(self._model.predict([raw_conf])[0])

    def fit_transform(self, raw_confs, actuals) -> np.ndarray:
        """fit + transform 一次完成.

        Returns:
            np.ndarray of calibrated values
        """
        self.fit(raw_confs, actuals)
        return np.array([self.transform(c) for c in raw_confs])


# ──────────────────────────────────────────────────────────────────────
# 3. StudentCalibrationTracker: 每学生独立 buffer + Platt/Isotonic 切换
# ──────────────────────────────────────────────────────────────────────


class StudentCalibrationTracker:
    """v0.72.0+: 每学生 V3 calibration 跟踪器.

    维护 per-student (raw_conf, actual_outcome) 配对 buffer, 触发 refit.

    冷启动调度 (v0.73.0):
      - n_pairs < min_samples_to_fit_platt (默认 5):    raw V3, source = "raw_v3"
      - min_samples_to_fit_platt <= n_pairs < min_samples_to_fit_isotonic (默认 20):
            PlattScaling, source = "platt_scaling"
      - n_pairs >= min_samples_to_fit_isotonic (默认 20):
            IsotonicReg, source = "isotonic_regression"

    Attributes:
        min_samples_to_fit_platt: 触发 Platt Scaling 的最小样本数 (默认 5)
        min_samples_to_fit_isotonic: 触发 Isotonic Regression 的最小样本数 (默认 20)
        l2_lambda: L2 正则化系数, 传给 PlattScaler (默认 0.01)
        _pairs: List of (raw_conf, actual_outcome)
        _scaler: 当前 PlattScaler 或 IsotonicCalibrator 实例
        _active_calibrator: "raw_v3" / "platt_scaling" / "isotonic_regression"
    """

    def __init__(
        self,
        min_samples_to_fit_platt: int = 5,
        min_samples_to_fit_isotonic: int = 20,
        l2_lambda: float = 0.01,
    ):
        if min_samples_to_fit_platt < 1:
            raise ValueError(f"min_samples_to_fit_platt 必须 >= 1, got {min_samples_to_fit_platt}")
        if min_samples_to_fit_isotonic < min_samples_to_fit_platt:
            raise ValueError(
                f"min_samples_to_fit_isotonic ({min_samples_to_fit_isotonic}) 必须 "
                f">= min_samples_to_fit_platt ({min_samples_to_fit_platt})"
            )
        self.min_samples_to_fit_platt = min_samples_to_fit_platt
        self.min_samples_to_fit_isotonic = min_samples_to_fit_isotonic
        self.l2_lambda = l2_lambda
        self._pairs: List[Tuple[float, float]] = []
        self._scaler = PlattScaler(l2_lambda=l2_lambda)
        self._active_calibrator: str = "raw_v3"

    @property
    def n_pairs(self) -> int:
        return len(self._pairs)

    @property
    def is_fitted(self) -> bool:
        return self._scaler._fitted

    @property
    def active_calibrator(self) -> str:
        """当前生效的 calibrator 类型 (raw_v3 / platt_scaling / isotonic_regression)."""
        return self._active_calibrator

    def add_pair(self, raw_conf: float, actual_outcome: float) -> None:
        """添加一对 (raw_V3, actual_outcome) 并触发 refit.

        Args:
            raw_conf: 原始 V3 confidence (clamp to [0, 1])
            actual_outcome: 答对 outcome (0.0 / 1.0, 或 partial credit [0, 1])
        """
        raw_clamped = float(np.clip(raw_conf, 0.0, 1.0))
        actual_clamped = float(np.clip(actual_outcome, 0.0, 1.0))
        self._pairs.append((raw_clamped, actual_clamped))

        self._refit()

    def _refit(self) -> None:
        """用全部历史 pairs 重训 calibrator (Platt 或 Isotonic 根据 n_pairs 切换)."""
        n = self.n_pairs

        if n < self.min_samples_to_fit_platt:
            self._scaler = PlattScaler(l2_lambda=self.l2_lambda)
            self._active_calibrator = "raw_v3"
            return
        if n < 2:
            return

        raw_confs, actuals = zip(*self._pairs)

        if n >= self.min_samples_to_fit_isotonic:
            # 切到 IsotonicCalibrator
            self._scaler = IsotonicCalibrator()
            self._scaler.fit(list(raw_confs), list(actuals))
            if self._scaler._fitted:
                self._active_calibrator = "isotonic_regression"
            else:
                # Isotonic fit 失败, 退到 Platt
                self._scaler = PlattScaler(l2_lambda=self.l2_lambda)
                self._scaler.fit(list(raw_confs), list(actuals))
                if self._scaler._fitted:
                    self._active_calibrator = "platt_scaling"
                else:
                    self._active_calibrator = "raw_v3"
        else:
            # n 在 [platt_min, isotonic_min), 走 Platt
            self._scaler = PlattScaler(l2_lambda=self.l2_lambda)
            self._scaler.fit(list(raw_confs), list(actuals))
            if self._scaler._fitted:
                self._active_calibrator = "platt_scaling"
            else:
                self._active_calibrator = "raw_v3"

    def calibrate(self, raw_conf: float) -> float:
        """校准 V3 confidence.

        Args:
            raw_conf: 原始 V3 confidence (float, [0, 1])

        Returns:
            calibrated confidence
            - n_pairs < min_samples_to_fit_platt: raw_conf (clip 到 [0, 1])
            - Platt 阶段: PlattScaler.transform(raw_conf)
            - Isotonic 阶段: IsotonicCalibrator.transform(raw_conf)
        """
        raw_clamped = float(np.clip(raw_conf, 0.0, 1.0))
        if self._active_calibrator == "raw_v3":
            return raw_clamped
        return self._scaler.transform(raw_clamped)

    def get_state(self) -> dict:
        """导出状态 (用于调试 + 持久化)."""
        state = {
            "n_pairs": self.n_pairs,
            "is_fitted": self.is_fitted,
            "active_calibrator": self._active_calibrator,
            "min_samples_to_fit_platt": self.min_samples_to_fit_platt,
            "min_samples_to_fit_isotonic": self.min_samples_to_fit_isotonic,
            "l2_lambda": self.l2_lambda,
        }
        if isinstance(self._scaler, PlattScaler):
            state.update({"A": self._scaler.A, "B": self._scaler.B})
        return state
