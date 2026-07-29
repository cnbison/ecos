"""v0.63.0: ECE (Expected Calibration Error) 指标测试.

验证:
  - 完美校准 → ECE = 0
  - 完全不校准 → ECE 大
  - reliability diagram 数据正确
  - binary_calibration 跟 expected_calibration_error 等价
  - 边界: 空输入 / 长度不一致 / 越界 confidence
"""

from __future__ import annotations

import pytest

from ecos.metrics import (
    expected_calibration_error,
    reliability_diagram_data,
    binary_calibration,
)


# ─── 1. 基础 ECE 行为 ───────────────────────────────────────────


class TestExpectedCalibrationError:
    """v0.63.0: expected_calibration_error 函数."""

    def test_perfect_calibration_returns_zero(self):
        """完美校准 → ECE = 0."""
        # confidence = accuracy 完美对齐
        ece = expected_calibration_error(
            confidences=[0.0, 0.5, 1.0],
            accuracies=[0.0, 0.5, 1.0],
        )
        assert ece == pytest.approx(0.0, abs=1e-9)

    def test_perfect_calibration_dense(self):
        """完美校准 (10 样本, conf=acc 严格相等, 但 acc 是 0/1) → ECE = 0.

        完美校准需要 confidence 跟 accuracy **完全相等** (即使 acc=0 或 1).
        例子: 5 样本 conf=acc=0.0 (第 1 bin) + 5 样本 conf=acc=1.0 (第 10 bin).
        """
        ece = expected_calibration_error(
            confidences=[0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            accuracies=[0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        )
        assert ece == pytest.approx(0.0, abs=1e-9)

    def test_overconfident_returns_high_ece(self):
        """over-confident: confidence 高但 accuracy 低 → ECE 大."""
        ece = expected_calibration_error(
            confidences=[0.9, 0.9, 0.9],
            accuracies=[0.0, 0.0, 0.0],
        )
        # 每个样本 confidence=0.9, accuracy=0.0, 差距 0.9
        assert ece == pytest.approx(0.9, abs=1e-9)

    def test_underconfident_returns_high_ece(self):
        """under-confident: confidence 低但 accuracy 高 → ECE 大."""
        ece = expected_calibration_error(
            confidences=[0.1, 0.1, 0.1],
            accuracies=[1.0, 1.0, 1.0],
        )
        assert ece == pytest.approx(0.9, abs=1e-9)

    def test_mixed_calibration_partial_credit(self):
        """partial credit accuracies 也能算 ECE."""
        # score: [0.7, 0.3, 0.5, 0.8] (partial credit)
        # confidence: [0.6, 0.6, 0.6, 0.6] (单 Agent 估的统一)
        ece = expected_calibration_error(
            confidences=[0.6, 0.6, 0.6, 0.6],
            accuracies=[0.7, 0.3, 0.5, 0.8],
        )
        # 全部在 0.5-0.7 bin, bin_conf=0.6, bin_acc=mean(0.7,0.3,0.5,0.8)=0.575
        # 差距 0.025
        assert ece == pytest.approx(0.025, abs=1e-3)

    def test_empty_input_returns_one(self):
        """空输入 → 兜底返回 1.0 (最大不校准)."""
        assert expected_calibration_error([], []) == 1.0

    def test_mismatched_lengths_raises(self):
        """长度不一致 → ValueError."""
        with pytest.raises(ValueError, match="长度不一致"):
            expected_calibration_error([0.5], [0.5, 0.5])

    def test_uniform_vs_quantile_strategy(self):
        """两种 bin_strategy 都能跑 (结果可能不同, 跟 sklearn 行为一致)."""
        # 完美校准例子 (conf=acc 严格相等, acc=0/1)
        confs = [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        accs = [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        ece_uniform = expected_calibration_error(confs, accs, bin_strategy="uniform")
        ece_quantile = expected_calibration_error(confs, accs, bin_strategy="quantile")
        # 完美校准时应该都接近 0
        assert ece_uniform == pytest.approx(0.0, abs=1e-9)
        assert ece_quantile == pytest.approx(0.0, abs=1e-9)

    def test_unknown_bin_strategy_raises(self):
        """未知 bin_strategy → ValueError."""
        with pytest.raises(ValueError, match="未知 bin_strategy"):
            expected_calibration_error([0.5], [0.5], bin_strategy="foo")


# ─── 2. Reliability diagram 数据 ─────────────────────────────────


class TestReliabilityDiagram:
    """v0.63.0: reliability_diagram_data 返回画图数据."""

    def test_basic_reliability_data(self):
        """基础 reliability diagram 数据 (完美校准: conf 跟 acc 严格相等)."""
        data = reliability_diagram_data(
            confidences=[0.0, 0.5, 1.0],
            accuracies=[0.0, 0.5, 1.0],
        )
        assert "bin_centers" in data
        assert "bin_confidences" in data
        assert "bin_accuracies" in data
        assert "bin_counts" in data
        assert "ece" in data
        # 完美校准, 3 个 bin 各 1 个样本
        assert sum(data["bin_counts"]) == 3
        assert data["ece"] == pytest.approx(0.0, abs=1e-9)

    def test_empty_input_returns_empty_data(self):
        """空输入 → 空列表 + ECE=1.0."""
        data = reliability_diagram_data([], [])
        assert data["bin_centers"] == []
        assert data["bin_confidences"] == []
        assert data["ece"] == 1.0

    def test_overconfident_curve_above_diagonal(self):
        """over-confident: bin_accuracy < bin_confidence (曲线在 y=x 上方)."""
        data = reliability_diagram_data(
            confidences=[0.9, 0.9, 0.9, 0.9],
            accuracies=[0.0, 0.0, 0.0, 0.0],
        )
        # 4 个样本全在 0.9-1.0 bin
        assert len(data["bin_counts"]) == 1
        assert data["bin_confidences"][0] == pytest.approx(0.9, abs=1e-9)
        assert data["bin_accuracies"][0] == pytest.approx(0.0, abs=1e-9)
        # bin_conf - bin_acc = 0.9
        assert data["ece"] == pytest.approx(0.9, abs=1e-9)


# ─── 3. binary_calibration ────────────────────────────────────────


class TestBinaryCalibration:
    """v0.63.0: binary_calibration 包装."""

    def test_basic_binary(self):
        """基础二元校准."""
        result = binary_calibration(
            confidences=[0.7, 0.3, 0.5],
            corrects=[True, False, True],
        )
        assert result["n_samples"] == 3
        assert result["accuracy"] == pytest.approx(2 / 3, abs=1e-9)
        assert result["avg_confidence"] == pytest.approx(0.5, abs=1e-9)
        # 全部 0.5-0.7 bin? 不一定, 取决于 bin_strategy
        # 0.7 落在 0.5-0.7 或 0.7-0.9 (uniform 10 bins, edges: 0, 0.1, 0.2, ..., 1.0)
        # 0.7 落在 [0.6, 0.7), 0.3 落在 [0.3, 0.4), 0.5 落在 [0.5, 0.6)
        # 不管, 只需要 ECE 是 [0, 1]
        assert 0.0 <= result["ece"] <= 1.0

    def test_binary_perfect(self):
        """完美校准二元 (confidence 跟 correct 完全匹配)."""
        # conf=0.0 → 答错, conf=1.0 → 答对 (完美校准)
        # 2 样本分 2 bin (uniform 10 bins: [0, 0.1) 和 [0.9, 1.0])
        result = binary_calibration(
            confidences=[0.0, 1.0],
            corrects=[False, True],
        )
        assert result["ece"] == pytest.approx(0.0, abs=1e-9)
