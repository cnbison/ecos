"""v0.97.2 calibration_view test suite (CogMirror A1 移植).

对应:
  - CogMirror tests/test_calibration.py 语义覆盖 (桶划分 / Laplace 数学 /
    correction_factor 语义 / min_n 回退 / None 跳过 / 空输入)
  - ECOS 本地化差异: 输入 = response_history 条目 (self_confidence None /
    缺键跳过), 判对 = correct 字段优先 + score>=0.6 兜底

覆盖:
- bucket_confidence 边界 (clamp 1.0→0.9 桶 / 负值→0.0 桶)
- Laplace 平滑数学 (n=1 全错 1/3, n=1 全对 2/3)
- 判对阈值 0.6 线 (score 0.6 对 / 0.5 错; correct 字段优先)
- correction_factor 语义 (过度自信 <1, 欠自信 >1)
- 未自评条目跳过 + 计数 (None / 缺键, 不猜不映射)
- expected_accuracy min_n 诚实回退 (n<5 → None, 无桶 → None)
- 纯函数幂等 (同输入同输出, 不改输入)
"""
from __future__ import annotations

import pytest

from ecos.cta.calibration_view import (
    BUCKET_WIDTH,
    MIN_BUCKET_N,
    CalibrationCurve,
    CalibrationView,
    bucket_confidence,
    calibration_view,
    expected_accuracy,
)


def recs(n: int, conf: float, correct: bool) -> list[dict]:
    """构造 n 条自评记录 (score 0.9 对 / 0.0 错, 同 CogMirror 测试模式)."""
    score = 0.9 if correct else 0.0
    return [{"skill_id": "S1", "self_confidence": conf, "score": score, "correct": int(correct)}] * n


class TestBucketConfidence:
    @pytest.mark.parametrize("conf,want", [
        (0.0, "0.0"), (0.05, "0.0"), (0.099, "0.0"),
        (0.1, "0.1"), (0.34, "0.3"), (0.99, "0.9"),
        (1.0, "0.9"),  # clamp 0.999 -> 0.9 桶
        (-0.2, "0.0"),
        # 学生端 4 档映射值落桶: 0.9/0.7/0.5/0.3
        (0.9, "0.9"), (0.7, "0.7"), (0.5, "0.5"), (0.3, "0.3"),
    ])
    def test_bucket(self, conf, want):
        assert bucket_confidence(conf) == want


class TestCalibrationView:
    def test_laplace_math(self):
        # n=1 全错: (0+1)/(1+2) = 1/3; n=1 全对: (1+1)/3 = 2/3
        view = calibration_view(recs(1, 0.35, correct=False))
        assert len(view.curves) == 1
        c = view.curves[0]
        assert c.bucket == "0.3"
        assert c.n == 1 and c.correct == 0
        assert c.actual_rate == pytest.approx(1 / 3)
        assert c.predicted == pytest.approx(0.35)

        view = calibration_view(recs(1, 0.35, correct=True))
        assert view.curves[0].actual_rate == pytest.approx(2 / 3)
        assert view.curves[0].correct == 1

    def test_correct_threshold_uses_06_line(self):
        # score 0.6 -> correct (与引擎 partial credit 派生一致); 0.5 -> 错
        records = [
            {"self_confidence": 0.55, "score": 0.6, "correct": 1},
            {"self_confidence": 0.55, "score": 0.5, "correct": 0},
        ]
        view = calibration_view(records)
        assert view.curves[0].n == 2
        # Laplace: (1+1)/(2+2) = 0.5
        assert view.curves[0].actual_rate == pytest.approx(0.5)

    def test_correct_field_missing_falls_back_to_score(self):
        """老条目只有 score 无 correct → score >= 0.6 兜底 (同 _entry_correct)."""
        records = [
            {"self_confidence": 0.55, "score": 0.7},   # 对 (无 correct 键)
            {"self_confidence": 0.55, "score": 0.5},   # 错
        ]
        view = calibration_view(records)
        assert view.curves[0].n == 2
        assert view.curves[0].correct == 1
        assert view.curves[0].actual_rate == pytest.approx(0.5)

    def test_correction_factor_semantics(self):
        # 过度自信 (自评 0.9 桶全错) -> factor < 1
        view = calibration_view(recs(10, 0.9, correct=False))
        assert view.curves[0].correction_factor < 1.0
        # 欠自信 (自评 0.2 桶全对) -> factor > 1
        view = calibration_view(recs(10, 0.2, correct=True))
        assert view.curves[0].correction_factor > 1.0

    def test_none_self_confidence_skipped_and_counted(self):
        """未自评 (None) 条目跳过并计数; 桶按升序排列."""
        records = [{"skill_id": "S1", "self_confidence": None, "score": 1.0, "correct": 1}] \
            + recs(2, 0.8, correct=True) + recs(1, 0.1, correct=False)
        view = calibration_view(records)
        assert [c.bucket for c in view.curves] == ["0.1", "0.8"]
        assert view.curves[1].n == 2
        assert view.n_total == 4
        assert view.n_self_assessed == 3
        assert view.n_skipped == 1

    def test_missing_key_skipped(self):
        """v0.97.2 前老条目无 self_confidence 键 → 跳过 (不猜不映射)."""
        records = [
            {"skill_id": "S1", "score": 1.0, "correct": 1},   # 老条目
            {"skill_id": "S1", "self_confidence": 0.7, "score": 1.0, "correct": 1},
        ]
        view = calibration_view(records)
        assert view.n_skipped == 1
        assert view.n_self_assessed == 1
        assert [c.bucket for c in view.curves] == ["0.7"]

    def test_empty_history(self):
        view = calibration_view([])
        assert view.curves == []
        assert view.n_total == 0
        assert view.has_data is False

    def test_all_unassessed_has_no_data(self):
        """全部未自评 → 无曲线, has_data False (不造曲线)."""
        records = [{"self_confidence": None, "score": 1.0}] * 10
        view = calibration_view(records)
        assert view.curves == []
        assert view.has_data is False

    def test_has_data_requires_min_bucket_n(self):
        """n >= MIN_BUCKET_N 的桶才够数据; n < 5 时 has_data False."""
        view = calibration_view(recs(MIN_BUCKET_N - 1, 0.5, correct=True))
        assert view.has_data is False
        view = calibration_view(recs(MIN_BUCKET_N, 0.5, correct=True))
        assert view.has_data is True

    def test_pure_function_does_not_mutate_input(self):
        records = recs(2, 0.5, correct=True)
        snapshot = [dict(r) for r in records]
        calibration_view(records)
        assert records == snapshot

    def test_constants_cogmirror_parity(self):
        """移植保真: 桶宽 / 平滑语义与 CogMirror A1 一致."""
        assert BUCKET_WIDTH == 0.1
        assert MIN_BUCKET_N == 5


class TestPortingFixes:
    """移植偏差修正 (vs CogMirror A1): 浮点截断落错桶.

    CogMirror 源模式 `int(c / 0.1)` 在 0.7/0.3 上因浮点表示 (0.7/0.1 =
    6.999...) 截断落错桶 (0.7 → "0.6")。CogMirror 连续滑条未踩中; ECOS
    4 档映射 0.9/0.7/0.5/0.3 全踩中 → epsilon 修正 (见 bucket_confidence
    docstring)。此 bug 应回馈 CogMirror 侧修复。
    """

    @pytest.mark.parametrize("conf,want", [
        (0.7, "0.7"), (0.3, "0.3"), (0.9, "0.9"), (0.5, "0.5"),
        (0.099, "0.0"),  # epsilon 不破坏下边界语义
        (0.999, "0.9"), (0.34, "0.3"),
    ])
    def test_scale_values_land_correct_bucket(self, conf, want):
        assert bucket_confidence(conf) == want

    def test_scale_records_use_declared_bucket(self):
        """4 档自评记录落进与档位声明一致的桶 (回归: 0.7 曾落 '0.6')."""
        view = calibration_view(recs(6, 0.7, correct=True) + recs(6, 0.3, correct=False))
        assert [c.bucket for c in view.curves] == ["0.3", "0.7"]


class TestExpectedAccuracy:
    def test_returns_actual_rate_when_bucket_full(self):
        view = calibration_view(recs(6, 0.7, correct=False))
        # Laplace: (0+1)/(6+2) = 0.125
        assert expected_accuracy(view, 0.7) == pytest.approx(0.125)

    def test_returns_none_when_bucket_below_min_n(self):
        """桶样本 < 5 → None (数据不足诚实回退, 不造数)."""
        view = calibration_view(recs(3, 0.7, correct=True))
        assert expected_accuracy(view, 0.7) is None

    def test_returns_none_when_no_bucket(self):
        """从未在该区间自评过 → None."""
        view = calibration_view(recs(6, 0.3, correct=True))
        assert expected_accuracy(view, 0.9) is None

    def test_returns_none_on_empty_view(self):
        assert expected_accuracy(calibration_view([]), 0.5) is None


class TestCalibrationViewDataclass:
    def test_curve_frozen(self):
        view = calibration_view(recs(1, 0.3, correct=True))
        with pytest.raises(Exception):
            view.curves[0].n = 99

    def test_scale_documentation_anchor(self):
        """学生端 4 档映射的文档化锚点 (改映射须同步 AnswerPage.tsx)."""
        from ecos.cta.calibration_view import SELF_CONFIDENCE_SCALE
        assert SELF_CONFIDENCE_SCALE == {
            "肯定会对": 0.9, "应该会": 0.7, "不确定": 0.5, "可能不会": 0.3,
        }
