"""ECE (Expected Calibration Error) 校准度指标 (v0.63.0 新增).

对应:
  - research/00-overview/03-roadmap.md §2.3 H3 验证
  - research/90-mvp/README.md §7.3 数据分析 (双 Agent 互校 ECE)
  - research/00-overview/04-risks.md §4-risks A9 (ECE 阈值 0.10)

定义 (Guo et al. 2017 "On Calibration of Modern Neural Networks"):
  ECE = sum over bins (|bin_confidence - bin_accuracy| * n_bin / n_total)

其中:
  - bin_confidence: 该 bin 内所有样本 confidence 的平均值
  - bin_accuracy: 该 bin 内所有样本的实际 accuracy (0/1) 的平均值
  - n_bin / n_total: 该 bin 样本权重

校准度意义:
  - confidence 跟 accuracy 越接近 → 模型越"知道自己不知道"
  - ECE = 0: 完美校准
  - ECE 越大: 校准越差
  - ECOS H3 阈值: 双 Agent ECE ≤ 0.10

设计原则:
  - 纯函数, 无副作用
  - 输入 numpy array / Python list 均可
  - 输出 float (ECE) / dict (reliability diagram)
  - 跟 sklearn.calibration.calibration_curve 接口对齐 (未来替换方便)
  - 缺数据 bin 不计入 (避免小样本噪声)
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Union

import numpy as np


# ─── 核心: Expected Calibration Error ─────────────────────────────


def expected_calibration_error(
    confidences: Sequence[float],
    accuracies: Sequence[float],
    n_bins: int = 10,
    bin_strategy: str = "uniform",
) -> float:
    """计算 Expected Calibration Error (ECE).

    Args:
        confidences: 模型预测的 confidence 序列 (0.0-1.0).
                     例子: BeliefState.K.mastery_prob
        accuracies: 实际 accuracy 序列 (0.0-1.0).
                    二元: 0 或 1; 连续: partial credit score
        n_bins: 分 bin 数量, 默认 10 (Guo et al. 2017 标准).
        bin_strategy: 分 bin 策略.
            - "uniform": 等宽 [0, 1/n_bins], [1/n_bins, 2/n_bins], ...
            - "quantile": 等样本数 (跟 sklearn.calibration.calibration_curve 一样)

    Returns:
        ECE 值 (0.0-1.0). 越小越校准.
        空输入 → 返回 1.0 (最大不校准, 兜底).

    Examples:
        >>> # 完美校准
        >>> expected_calibration_error([0.1, 0.5, 0.9], [0.0, 0.5, 1.0])
        0.0
        >>> # 完全不校准 (高 confidence 但 0% accuracy)
        >>> expected_calibration_error([0.9, 0.9, 0.9], [0.0, 0.0, 0.0])
        0.9
    """
    confs = np.asarray(confidences, dtype=float)
    accs = np.asarray(accuracies, dtype=float)

    if len(confs) == 0 or len(accs) == 0:
        return 1.0  # 兜底: 无数据视为最大不校准
    if len(confs) != len(accs):
        raise ValueError(
            f"confidences ({len(confs)}) 和 accuracies ({len(accs)}) 长度不一致"
        )

    bin_edges = _compute_bin_edges(confs, n_bins, bin_strategy)
    n_total = len(confs)
    ece = 0.0

    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        if bin_strategy == "uniform":
            # uniform: 左闭右开 [lo, hi)
            in_bin = (confs >= lo) & (confs < hi)
            # 最后一个 bin 右闭
            if i == n_bins - 1:
                in_bin = (confs >= lo) & (confs <= hi)
        else:  # quantile
            # quantile: bin_edges[i] <= conf < bin_edges[i+1]
            in_bin = (confs >= lo) & (confs < hi)
            if i == n_bins - 1:
                in_bin = (confs >= lo) & (confs <= hi)

        n_bin = int(in_bin.sum())
        if n_bin == 0:
            continue  # 空 bin 跳过, 不计入 ECE (避免小样本噪声)

        bin_conf = float(confs[in_bin].mean())
        bin_acc = float(accs[in_bin].mean())
        ece += abs(bin_conf - bin_acc) * (n_bin / n_total)

    return float(ece)


# ─── Reliability diagram 数据 ───────────────────────────────────


def reliability_diagram_data(
    confidences: Sequence[float],
    accuracies: Sequence[float],
    n_bins: int = 10,
    bin_strategy: str = "uniform",
) -> Dict[str, Union[List[float], List[int]]]:
    """计算 reliability diagram 数据 (用于画校准曲线).

    Reliability diagram 是 ECE 的可视化:
      - x 轴: bin confidence (预测)
      - y 轴: bin accuracy (实际)
      - 完美校准 → y = x 对角线
      - 曲线在 y=x 上方 → over-confident (高估自己)
      - 曲线在 y=x 下方 → under-confident (低估自己)

    Returns:
        dict 含:
          - bin_centers: list[float] bin 中心 confidence
          - bin_confidences: list[float] bin 平均 confidence
          - bin_accuracies: list[float] bin 平均 accuracy
          - bin_counts: list[int] 每个 bin 样本数
          - ece: float ECE 值 (跟 expected_calibration_error 等价)
    """
    confs = np.asarray(confidences, dtype=float)
    accs = np.asarray(accuracies, dtype=float)

    if len(confs) == 0 or len(accs) == 0:
        return {
            "bin_centers": [],
            "bin_confidences": [],
            "bin_accuracies": [],
            "bin_counts": [],
            "ece": 1.0,
        }
    if len(confs) != len(accs):
        raise ValueError(
            f"confidences ({len(confs)}) 和 accuracies ({len(accs)}) 长度不一致"
        )

    bin_edges = _compute_bin_edges(confs, n_bins, bin_strategy)
    bin_centers = []
    bin_confs = []
    bin_accs = []
    bin_counts = []

    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        if bin_strategy == "uniform":
            in_bin = (confs >= lo) & (confs < hi)
            if i == n_bins - 1:
                in_bin = (confs >= lo) & (confs <= hi)
        else:
            in_bin = (confs >= lo) & (confs < hi)
            if i == n_bins - 1:
                in_bin = (confs >= lo) & (confs <= hi)

        n_bin = int(in_bin.sum())
        if n_bin == 0:
            continue

        bin_centers.append((lo + hi) / 2)
        bin_confs.append(float(confs[in_bin].mean()))
        bin_accs.append(float(accs[in_bin].mean()))
        bin_counts.append(n_bin)

    return {
        "bin_centers": bin_centers,
        "bin_confidences": bin_confs,
        "bin_accuracies": bin_accs,
        "bin_counts": bin_counts,
        "ece": expected_calibration_error(confs, accs, n_bins, bin_strategy),
    }


# ─── 二元校准: confidence + correct → accuracy ───────────────────


def binary_calibration(
    confidences: Sequence[float],
    corrects: Sequence[bool],
    n_bins: int = 10,
) -> Dict[str, float]:
    """二元校准 (跟 expected_calibration_error 等价, 但 inputs 是 bool 序列).

    Args:
        confidences: 模型预测 confidence (0.0-1.0).
        corrects: 实际是否答对 (bool).
        n_bins: 分 bin 数量.

    Returns:
        dict 含:
          - ece: float
          - n_samples: int
          - accuracy: float 平均 accuracy
          - avg_confidence: float 平均 confidence
    """
    confs = list(confidences)
    accs = [1.0 if c else 0.0 for c in corrects]
    ece = expected_calibration_error(confs, accs, n_bins)
    return {
        "ece": ece,
        "n_samples": len(confs),
        "accuracy": float(np.mean(accs)) if accs else 0.0,
        "avg_confidence": float(np.mean(confs)) if confs else 0.0,
    }


# ─── Helpers ─────────────────────────────────────────────────────


def _compute_bin_edges(
    confidences: np.ndarray,
    n_bins: int,
    bin_strategy: str,
) -> np.ndarray:
    """计算 bin 边界.

    Args:
        confidences: confidence 序列 (用于 quantile 策略).
        n_bins: bin 数量.
        bin_strategy: "uniform" 或 "quantile".

    Returns:
        np.ndarray 长度 n_bins+1, 第 i 个 bin 是 [edges[i], edges[i+1]).
    """
    if bin_strategy == "uniform":
        return np.linspace(0.0, 1.0, n_bins + 1)
    elif bin_strategy == "quantile":
        # 跟 sklearn.calibration.calibration_curve 一样: 等样本数分 bin
        quantiles = np.linspace(0.0, 1.0, n_bins + 1)
        edges = np.quantile(confidences, quantiles)
        # 确保 edges 严格递增 (避免 quantile 相等导致空 bin)
        edges[0] = 0.0
        edges[-1] = 1.0
        # 处理 quantiles 相等 (样本少时常见)
        for i in range(1, len(edges)):
            if edges[i] <= edges[i - 1]:
                edges[i] = edges[i - 1] + 1e-10
        return edges
    else:
        raise ValueError(
            f"未知 bin_strategy: {bin_strategy}, 应为 'uniform' 或 'quantile'"
        )


__all__ = [
    "expected_calibration_error",
    "reliability_diagram_data",
    "binary_calibration",
]
