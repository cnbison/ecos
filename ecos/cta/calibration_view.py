"""calibration_view — 自评校准曲线无状态视图 (v0.97.2, P1 观测层).

对应:
  - README 恢复期 backlog P1 "观测层补学生自评" (自报 vs 实绩互校)
  - CogMirror A1 校准曲线算法移植 (cogmirror/calibration.py, PersonalAGI
    `src/genesis/calibration/` 纯算法核心, 零 LLM)
  - 方案决策 (2026-09-05 讨论, Bisen 拍板): 本期只读 — 不接 C 维度更新,
    等 v0.98 试点数据回来再定 (与 A2 reconcile 同批数据)

移植时的本地化 (与 CogMirror 的差异):
  - 输入 = FeatureExtractor response_history 条目 (含 v0.97.2 self_confidence
    + score), 不是 CogMirror 的独立作答记录。self_confidence 为 None 的条目
    跳过 (未自评不参与校准, 不猜不映射; v0.97.2 前老条目天然全跳过)。
  - 判对语义沿用 ECOS 引擎约定: score >= 0.6 记 correct (v0.54.0 派生,
    CogMirror 同款阈值即源于此)。
  - Laplace 平滑 actual_rate = (correct+1)/(n+2) 保留: ECOS 试点 5-10 学生
    桶更稀疏, 无平滑会出现 0/1 极端桶, 平滑是兜底而非风格选择。

设计同 replay_mastery_view (v0.97.1): 纯函数、无状态、不持久化、不触碰
BeliefState —— 同输入同输出, 幂等。校准曲线是读时派生量, 不是状态。

预期消费方:
  - web 教师端 /api/teacher/students/<id>/calibration (c 段)
  - A2 reconcile (per-misconception 证据驱动权重, 数据回来后)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── 常量 (CogMirror A1 同款 + ECOS 本地化) ────────────────────────────

# 桶宽 (PersonalAGI 同款 0.1)
BUCKET_WIDTH = 0.1
# 置信度 clamp 上界: 1.0 会落出最后一个 0.1 桶, 源模式 clamp 到 0.999
CONF_MAX = 0.999
# expected_accuracy 的最小桶样本: 低于此返回 None (数据不足诚实回退)
MIN_BUCKET_N = 5
# 判对阈值 (ECOS v0.54.0 派生, CogMirror A1 同款)
CORRECT_THRESHOLD = 0.6

# 学生端 4 档语义化自评 → 数值映射 (前端 UI 呈现用, kernel 只收 float;
# 文档化锚点, 改映射须同步 web/frontend/src/student/pages/AnswerPage.tsx)
SELF_CONFIDENCE_SCALE: Dict[str, float] = {
    "肯定会对": 0.9,
    "应该会": 0.7,
    "不确定": 0.5,
    "可能不会": 0.3,
}


def bucket_confidence(conf: float) -> str:
    """置信度 -> 0.1 宽桶标签 ("0.3" 表示 [0.3, 0.4)).

    clamp 到 [0, 0.999]: 负值入 0.0 桶, 1.0 入 0.9 桶 (0.999 的 int 截断)。

    移植偏差修正 (vs CogMirror A1): 源模式 `int(c / 0.1)` 在 0.7/0.3 等
    值上因浮点表示 (0.7/0.1 = 6.999...) 截断落错桶 (0.7 → "0.6")。
    CogMirror 用连续滑条未踩中; ECOS 4 档映射恰为 0.9/0.7/0.5/0.3 全踩中,
    加 1e-9 epsilon 修正 (对 0.099 → "0.0" 等边界语义无影响)。
    """
    c = min(max(float(conf), 0.0), CONF_MAX)
    return f"{int(c / BUCKET_WIDTH + 1e-9) * BUCKET_WIDTH:.1f}"


@dataclass(frozen=True)
class CalibrationCurve:
    """单个置信度桶的校准数据.

    Attributes:
        bucket: 桶标签 ("0.3" = 自评 [0.3, 0.4))
        n: 该桶样本数 (原始计数, 未经平滑)
        correct: 该桶判对次数 (score >= CORRECT_THRESHOLD)
        predicted: 桶中点 (自评的标称置信度)
        actual_rate: Laplace 平滑后的真实答对率 (correct+1)/(n+2)
        correction_factor: actual_rate / predicted (自评高于实绩 -> <1)
    """

    bucket: str
    n: int
    correct: int
    predicted: float
    actual_rate: float
    correction_factor: float


@dataclass(frozen=True)
class CalibrationView:
    """单个学生的自评校准视图 (只读派生量, 不持久化).

    Attributes:
        curves: 按桶排序的校准曲线 (空 = 无自评数据)
        n_total: 响应历史总条数
        n_self_assessed: 有 self_confidence 的条数 (参与校准)
        n_skipped: 未自评条数 (None / 老条目无键)
    """

    curves: List[CalibrationCurve]
    n_total: int
    n_self_assessed: int
    n_skipped: int

    @property
    def has_data(self) -> bool:
        """是否有足够自评数据 (至少一桶 n >= MIN_BUCKET_N)。"""
        return any(c.n >= MIN_BUCKET_N for c in self.curves)


def calibration_view(history: List[Dict[str, Any]]) -> CalibrationView:
    """从响应历史计算自评校准视图 (纯函数, 无状态).

    Args:
        history: FeatureExtractor.get_history(student_id) 的响应历史。
            条目需含 self_confidence (v0.97.2 起) + score/correct;
            self_confidence 为 None 或缺键的条目跳过 (未自评不参与校准)。

    Returns:
        CalibrationView (curves 按桶升序; 无自评数据 → curves 为空列表,
        has_data False — 调用方据此回退"数据不足"展示, 不造曲线)。
    """
    n_total = len(history)
    n_skipped = 0
    by_bucket: Dict[str, tuple] = {}

    for entry in history:
        conf = entry.get("self_confidence")
        if conf is None:
            n_skipped += 1
            continue
        # 判对语义与引擎一致: 优先 correct 字段, 缺失时 score >= 0.6 兜底
        # (与 l1_evolution._entry_correct 的兼容约定一致)
        correct = entry.get("correct")
        if correct is None:
            correct = float(entry.get("score", 0)) >= CORRECT_THRESHOLD
        b = bucket_confidence(float(conf))
        n, c = by_bucket.get(b, (0, 0))
        by_bucket[b] = (n + 1, c + int(bool(correct)))

    curves = []
    for b in sorted(by_bucket):
        n, correct = by_bucket[b]
        predicted = float(b) + BUCKET_WIDTH / 2.0
        actual_rate = (correct + 1) / (n + 2)
        factor = actual_rate / predicted if predicted > 0.0 else 1.0
        curves.append(CalibrationCurve(
            bucket=b, n=n, correct=correct,
            predicted=predicted, actual_rate=actual_rate,
            correction_factor=factor,
        ))

    return CalibrationView(
        curves=curves,
        n_total=n_total,
        n_self_assessed=n_total - n_skipped,
        n_skipped=n_skipped,
    )


def expected_accuracy(view: CalibrationView, claimed_conf: float) -> Optional[float]:
    """查询 "自评 claimed_conf 的题, 实际答对率是多少" (Laplace 平滑后).

    桶样本 < MIN_BUCKET_N 或无该桶 (从未在该区间自评过) → None
    (数据不足诚实回退, 调用方不造数)。A2 reconcile 的查询入口。
    """
    b = bucket_confidence(claimed_conf)
    for c in view.curves:
        if c.bucket == b:
            return c.actual_rate if c.n >= MIN_BUCKET_N else None
    return None
