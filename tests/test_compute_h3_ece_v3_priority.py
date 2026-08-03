"""v0.69.0-d: compute_h3_ece V3 优先逻辑 + 冷启动分段测试.

目标 (按 v0.69.0 PRD §3.3.2 + §7.4):
  1. compute_dual_agent_ece V3 优先 / V2 其次 / V1 兜底
  2. 报告加版本分布统计 (V3/V2/V1 各多少样本)
  3. 冷启动期数据 (source="estimate_gain_fallback") 单独标记
  4. ECE 分两段算: 冷启动期 vs 非冷启动期

防御性自检 [5]: 老数据兼容 (None 字段)
"""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def make_calibration_row(
    calibration_round: int,
    expected_gain: float = 0.5,
    actual_outcome: float = 0.8,
    state_overall_confidence: float | None = None,
    dual_agent_confidence: float | None = None,
    dual_agent_confidence_source: str | None = None,
) -> dict:
    """构造一行 calibration_log."""
    payload = {
        "intervention_id": f"iv-{calibration_round}",
        "intervention_type": "explanatory",
        "bloom_target": "UNDERSTAND",
        "expected_gain": expected_gain,
        "expected_risk": 0.1,
        "rationale_preview": "test",
        "actual_outcome": actual_outcome,
        "degraded_mode": False,
    }
    if state_overall_confidence is not None:
        payload["state_overall_confidence"] = state_overall_confidence
    if dual_agent_confidence is not None:
        payload["dual_agent_confidence"] = dual_agent_confidence
    if dual_agent_confidence_source is not None:
        payload["dual_agent_confidence_source"] = dual_agent_confidence_source
    return {
        "calibration_round": calibration_round,
        "message_payload": json.dumps(payload),
    }


# ──────────────────────────────────────────────────────────────────────
# 1. V3 优先 / V2 其次 / V1 兜底
# ──────────────────────────────────────────────────────────────────────


class TestV3PriorityLogic:
    """v0.69.0-d: V3 优先 / V2 其次 / V1 兜底."""

    def test_v3_takes_priority_over_v2_and_v1(self):
        """样本同时有 V3/V2/V1 字段 -> 用 V3 (dual_agent_confidence)."""
        from scripts.compute_h3_ece import compute_dual_agent_ece

        rows = [
            make_calibration_row(
                calibration_round=1,
                expected_gain=0.1,  # V1
                state_overall_confidence=0.2,  # V2
                dual_agent_confidence=0.7,  # V3 优先
                dual_agent_confidence_source="linucb",
                actual_outcome=1.0,
            ),
        ]
        loaded = {"rows": rows, "duplicates_dropped": 0}

        with patch("scripts.compute_h3_ece.load_student_calibration_log", return_value=loaded):
            result = compute_dual_agent_ece("test_v3")

        assert result["n_samples"] == 1
        assert result["version_counts"]["V3"] == 1
        assert result["version_counts"]["V2"] == 0
        assert result["version_counts"]["V1"] == 0
        # confidence 应该是 0.7 (V3), 不是 0.1 (V1) 或 0.2 (V2)
        assert result["avg_confidence"] == 0.7

    def test_v2_used_when_v3_missing(self):
        """样本没 V3 -> 用 V2 (state_overall_confidence)."""
        from scripts.compute_h3_ece import compute_dual_agent_ece

        rows = [
            make_calibration_row(
                calibration_round=1,
                expected_gain=0.1,  # V1
                state_overall_confidence=0.55,  # V2 优先
                actual_outcome=1.0,
            ),
        ]
        loaded = {"rows": rows, "duplicates_dropped": 0}

        with patch("scripts.compute_h3_ece.load_student_calibration_log", return_value=loaded):
            result = compute_dual_agent_ece("test_v2")

        assert result["version_counts"]["V3"] == 0
        assert result["version_counts"]["V2"] == 1
        assert result["version_counts"]["V1"] == 0
        assert result["avg_confidence"] == 0.55

    def test_v1_used_when_v3_v2_missing(self):
        """样本没 V3 没 V2 -> 用 V1 (expected_gain) 兜底."""
        from scripts.compute_h3_ece import compute_dual_agent_ece

        rows = [
            make_calibration_row(
                calibration_round=1,
                expected_gain=0.42,  # V1 兜底
                actual_outcome=1.0,
            ),
        ]
        loaded = {"rows": rows, "duplicates_dropped": 0}

        with patch("scripts.compute_h3_ece.load_student_calibration_log", return_value=loaded):
            result = compute_dual_agent_ece("test_v1")

        assert result["version_counts"]["V3"] == 0
        assert result["version_counts"]["V2"] == 0
        assert result["version_counts"]["V1"] == 1
        assert result["avg_confidence"] == 0.42

    def test_mixed_versions_across_samples(self):
        """多样本混合 V3/V2/V1 -> 各自计数正确."""
        from scripts.compute_h3_ece import compute_dual_agent_ece

        rows = [
            # 样本 1: V3 (linucb)
            make_calibration_row(
                calibration_round=1,
                expected_gain=0.1,
                state_overall_confidence=0.2,
                dual_agent_confidence=0.7,
                dual_agent_confidence_source="linucb",
                actual_outcome=1.0,
            ),
            # 样本 2: V3 (estimate_gain_fallback 冷启动)
            make_calibration_row(
                calibration_round=2,
                expected_gain=0.3,
                dual_agent_confidence=0.3,
                dual_agent_confidence_source="estimate_gain_fallback",
                actual_outcome=0.5,
            ),
            # 样本 3: V2 (v0.68.0 数据, 没 V3)
            make_calibration_row(
                calibration_round=3,
                expected_gain=0.4,
                state_overall_confidence=0.55,
                actual_outcome=1.0,
            ),
            # 样本 4: V1 (老数据)
            make_calibration_row(
                calibration_round=4,
                expected_gain=0.5,
                actual_outcome=0.0,
            ),
        ]
        loaded = {"rows": rows, "duplicates_dropped": 0}

        with patch("scripts.compute_h3_ece.load_student_calibration_log", return_value=loaded):
            result = compute_dual_agent_ece("test_mixed")

        assert result["n_samples"] == 4
        assert result["version_counts"]["V3"] == 2
        assert result["version_counts"]["V2"] == 1
        assert result["version_counts"]["V1"] == 1


# ──────────────────────────────────────────────────────────────────────
# 2. 冷启动分段 ECE
# ──────────────────────────────────────────────────────────────────────


class TestColdStartSegmentation:
    """v0.69.0-d: 冷启动期 vs 非冷启动期分段 ECE."""

    def test_cold_start_segment_ece_separated(self):
        """冷启动期 (source=estimate_gain_fallback) 单独算 ECE."""
        from scripts.compute_h3_ece import compute_dual_agent_ece

        rows = [
            # 冷启动期: confidence=0.5, accuracy=1.0 -> error=0.5
            make_calibration_row(
                calibration_round=1,
                dual_agent_confidence=0.5,
                dual_agent_confidence_source="estimate_gain_fallback",
                actual_outcome=1.0,
            ),
            # 冷启动期: confidence=0.4, accuracy=1.0 -> error=0.6
            make_calibration_row(
                calibration_round=2,
                dual_agent_confidence=0.4,
                dual_agent_confidence_source="estimate_gain_fallback",
                actual_outcome=1.0,
            ),
            # 非冷启动: confidence=0.9, accuracy=1.0 -> error=0.1
            make_calibration_row(
                calibration_round=3,
                dual_agent_confidence=0.9,
                dual_agent_confidence_source="linucb",
                actual_outcome=1.0,
            ),
        ]
        loaded = {"rows": rows, "duplicates_dropped": 0}

        with patch("scripts.compute_h3_ece.load_student_calibration_log", return_value=loaded):
            result = compute_dual_agent_ece("test_cold")

        # 冷启动段: 2 样本, ECE 应该是 0.55 (0.5+0.6 / 2)
        assert result["cold_start_n_samples"] == 2
        assert result["cold_start_ece"] is not None
        assert abs(result["cold_start_ece"] - 0.55) < 0.01

        # 非冷启动段: 1 样本, ECE 应该是 0.1
        assert result["non_cold_start_n_samples"] == 1
        assert result["non_cold_start_ece"] is not None
        assert abs(result["non_cold_start_ece"] - 0.1) < 0.01

    def test_no_cold_start_data_returns_none_ece(self):
        """没有冷启动期数据 (全 linucb) -> cold_start_ece = None."""
        from scripts.compute_h3_ece import compute_dual_agent_ece

        rows = [
            make_calibration_row(
                calibration_round=1,
                dual_agent_confidence=0.9,
                dual_agent_confidence_source="linucb",
                actual_outcome=1.0,
            ),
        ]
        loaded = {"rows": rows, "duplicates_dropped": 0}

        with patch("scripts.compute_h3_ece.load_student_calibration_log", return_value=loaded):
            result = compute_dual_agent_ece("test_no_cold")

        assert result["cold_start_n_samples"] == 0
        assert result["cold_start_ece"] is None
        assert result["non_cold_start_n_samples"] == 1
        assert result["non_cold_start_ece"] is not None

    def test_v2_v1_data_treated_as_non_cold_start(self):
        """V2/V1 老数据 (没 source 字段) 算非冷启动段."""
        from scripts.compute_h3_ece import compute_dual_agent_ece

        rows = [
            # V2 数据 (v0.68.0)
            make_calibration_row(
                calibration_round=1,
                expected_gain=0.3,
                state_overall_confidence=0.55,
                actual_outcome=1.0,
            ),
            # V1 数据 (老)
            make_calibration_row(
                calibration_round=2,
                expected_gain=0.42,
                actual_outcome=0.0,
            ),
        ]
        loaded = {"rows": rows, "duplicates_dropped": 0}

        with patch("scripts.compute_h3_ece.load_student_calibration_log", return_value=loaded):
            result = compute_dual_agent_ece("test_old_data")

        # 没冷启动段数据
        assert result["cold_start_n_samples"] == 0
        assert result["cold_start_ece"] is None
        # 非冷启动段: 2 样本
        assert result["non_cold_start_n_samples"] == 2
        # source unknown 计数
        assert result["cold_start_counts"]["unknown"] == 2


# ──────────────────────────────────────────────────────────────────────
# 3. 向后兼容 (老数据 None 字段)
# ──────────────────────────────────────────────────────────────────────


class TestBackwardCompat:
    """v0.69.0-d: 老数据 (v0.69.0 之前) 兼容."""

    def test_old_data_without_v3_v2_fields(self):
        """老数据只有 expected_gain + actual_outcome -> 走 V1 兜底."""
        from scripts.compute_h3_ece import compute_dual_agent_ece

        rows = [
            make_calibration_row(
                calibration_round=1,
                expected_gain=0.5,
                actual_outcome=0.8,
            ),
            make_calibration_row(
                calibration_round=2,
                expected_gain=0.6,
                actual_outcome=1.0,
            ),
        ]
        loaded = {"rows": rows, "duplicates_dropped": 0}

        with patch("scripts.compute_h3_ece.load_student_calibration_log", return_value=loaded):
            result = compute_dual_agent_ece("test_old")

        assert result["n_samples"] == 2
        assert result["version_counts"]["V3"] == 0
        assert result["version_counts"]["V2"] == 0
        assert result["version_counts"]["V1"] == 2
        # ECE 仍可算
        assert result["ece"] is not None

    def test_skip_rows_without_actual_outcome(self):
        """没 actual_outcome 的行跳过 (v0.60.4 历史数据)."""
        from scripts.compute_h3_ece import compute_dual_agent_ece

        rows = [
            make_calibration_row(
                calibration_round=1,
                expected_gain=0.5,
                actual_outcome=0.8,
            ),
            # 没 actual_outcome (老数据 BUG)
            {
                "calibration_round": 2,
                "message_payload": json.dumps({
                    "intervention_id": "iv-2",
                    "expected_gain": 0.5,
                    # actual_outcome 缺失
                }),
            },
        ]
        loaded = {"rows": rows, "duplicates_dropped": 0}

        with patch("scripts.compute_h3_ece.load_student_calibration_log", return_value=loaded):
            result = compute_dual_agent_ece("test_skip")

        assert result["n_samples"] == 1
        assert result["skipped_no_outcome"] == 1


# ──────────────────────────────────────────────────────────────────────
# 4. format_report 含 V3/V2/V1 版本分布 + 冷启动分段
# ──────────────────────────────────────────────────────────────────────


class TestFormatReportV3Distribution:
    """v0.69.0-d: format_report 加 §6 版本分布 + 冷启动分段."""

    def test_report_contains_version_distribution(self):
        """报告含 §6 V3/V2/V1 版本分布."""
        from scripts.compute_h3_ece import format_report

        single = {"n_samples": 0, "ece": None, "student_id": "test", "dimension": "K"}
        dual = {
            "student_id": "test",
            "n_samples": 4,
            "ece": 0.2,
            "avg_confidence": 0.6,
            "avg_accuracy": 0.7,
            "version_counts": {"V3": 2, "V2": 1, "V1": 1},
            "cold_start_counts": {"linucb": 1, "estimate_gain_fallback": 1, "unknown": 2},
            "cold_start_ece": 0.5,
            "cold_start_n_samples": 1,
            "non_cold_start_ece": 0.1,
            "non_cold_start_n_samples": 1,
            "msg": "test",
        }

        report = format_report("test", single, dual)

        # §6 标题
        assert "## 6. v0.69.0 Confidence 版本分布 + 冷启动分段" in report
        # 版本分布
        assert "V3 (dual_agent_confidence, LinUCB θ@x): **2 样本**" in report
        assert "V2 (state_overall_confidence, belief_state 5D 平均): **1 样本**" in report
        assert "V1 (expected_gain, _estimate_gain 简化估算): **1 样本**" in report
        # 冷启动分段
        assert "LinUCB 预测 (source=\"linucb\"): **1 样本**" in report
        assert "_estimate_gain fallback" in report
        # 分段 ECE
        assert "冷启动期 ECE" in report
        assert "非冷启动期 ECE" in report
        # 结论
        assert "✅" in report  # 非冷启动 < 冷启动

    def test_report_shows_b4_failure_when_noncold_worse(self):
        """非冷启动 ECE > 冷启动 ECE -> 报告显示 B4 失败."""
        from scripts.compute_h3_ece import format_report

        single = {"n_samples": 0, "ece": None, "student_id": "test", "dimension": "K"}
        dual = {
            "student_id": "test",
            "n_samples": 2,
            "ece": 0.5,
            "avg_confidence": 0.4,
            "avg_accuracy": 0.5,
            "version_counts": {"V3": 2, "V2": 0, "V1": 0},
            "cold_start_counts": {"linucb": 1, "estimate_gain_fallback": 1, "unknown": 0},
            "cold_start_ece": 0.1,
            "cold_start_n_samples": 1,
            "non_cold_start_ece": 0.5,
            "non_cold_start_n_samples": 1,
            "msg": "test",
        }

        report = format_report("test", single, dual)

        # 结论应该是 B4 失败
        assert "❌" in report
        assert "B4 方案失败" in report
