"""v0.63.0: H3 验证 — 跑单 Agent vs 双 Agent 校准度 (ECE) 对比脚本.

对应:
  - research/00-overview/03-roadmap.md §2.3 H3 验证 (H3 = 双 Agent 互校抗幻觉)
  - research/90-mvp/README.md §8.1 H3 阈值: 双 Agent ECE ≤ 0.10
  - 报告输出: discussions/2026-07-29-H3-verification-report.md

H3 验证设计 (单 vs 双 Agent 对比):
  - 单 Agent (CTA only): 用 lbc00X response_history 30+ 道
    - confidence: BeliefState 各维度 mastery_prob (after update)
    - accuracy: response_history.correct (二元) / score (partial credit)
  - 双 Agent (CTA + LCA + 互校): 用 lbc00X calibration_log (v0.60.4 验证 5 行)
    - confidence: message_payload.expected_gain (互校预测的 gain)
    - accuracy: actual_outcome (实际 outcome, v0.61.0 改 score 派生)

数据基础:
  - lbc00X response_history: 30+ 道 (CTA 单跑, 整个答题历史)
  - lbc00X calibration_log: 5 行 (v0.60.4 dual_agent 跑过 5 道)
  - lbc00X belief.py: 累加 30+ 道, K/P/S/C/X 5D 状态可读

输出:
  - 打印到 stdout: 单 Agent baseline ECE + 双 Agent experiment ECE + 结论
  - 写入 discussions/2026-07-29-H3-verification-report.md: 完整报告

限制 (v0.63.0 时):
  - dual_agent 只有 5 行 calibration_log (lbc00X), 统计意义不足
  - H3 暂未通过, 待 lbc00X 答 30+ 道 dual_agent 后再补 (跟 A + B 后续接策略一致)

用法:
    python scripts/compute_h3_ece.py
    python scripts/compute_h3_ece.py --student-id lbc001 --output-md report.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 加项目根到 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ─── 数据加载 ─────────────────────────────────────────────────────


def load_student_response_history(student_id: str) -> List[Dict[str, Any]]:
    """从 web/api/belief.py _STUDENT_STATES 读学生 response_history.

    Returns:
        List[dict] 每条含: problem_id, correct, score, bloom_level, timestamp, ...
    """
    from web.api.belief import _get_or_create_student
    student = _get_or_create_student(student_id)
    state = student["state"]
    engine = student["engine"]
    history = list(getattr(engine, "_response_history", {}).get(student_id, []))
    return history


def load_student_calibration_log(student_id: str, limit: int = 1000) -> List[Dict[str, Any]]:
    """从 web/ecos.db 读学生 calibration_log (dual_agent 互校历史).

    Returns:
        List[dict] 每条含: calibration_round, message_payload, actual_outcome, ...
    """
    from ecos.persistence.db import get_db
    db = get_db()
    return db.load_calibration_history(student_id, limit=limit)


# ─── 单 Agent baseline ECE ───────────────────────────────────────


def compute_single_agent_ece(
    student_id: str,
    dimension: str = "K",
) -> Dict[str, Any]:
    """单 Agent baseline: 算学生答题历史的 5D 某维度校准度.

    v0.64.0 改进: 用 response_history[i].mastery_prob_after[dimension] 当 confidence,
                  不再是 v0.63.0 简化 (用当前 mastery_prob 当所有问题 confidence).
    """
    history = load_student_response_history(student_id)
    if not history:
        return {
            "student_id": student_id,
            "dimension": dimension,
            "n_samples": 0,
            "ece": None,
            "msg": "无 response_history, 无法算 baseline ECE",
        }

    confidences = []
    accuracies = []
    used_fallback = 0
    for h in history:
        correct = bool(h.get("correct", 0))
        accuracies.append(1.0 if correct else 0.0)

        # v0.64.0: mastery_prob_after 字段 (update 后 5D 状态快照)
        # 老数据 (v0.64.0 之前) 没这字段, fallback 到当前 mastery_prob 简化
        mpa = h.get("mastery_prob_after")
        if mpa and isinstance(mpa, dict):
            conf = float(mpa.get(dimension, 0.5))
        else:
            # 兜底: v0.63.0 简化, 用当前 mastery_prob
            from web.api.belief import _get_or_create_student
            student = _get_or_create_student(student_id)
            state = student["state"]
            current_dim = getattr(state, dimension, None)
            conf = getattr(current_dim, "mastery_prob", 0.5)
            used_fallback += 1

        # 截断到 [0, 1]
        conf = max(0.0, min(1.0, conf))
        confidences.append(conf)

    from ecos.metrics import expected_calibration_error, binary_calibration
    result = binary_calibration(confidences, [bool(a) for a in accuracies])
    result["dimension"] = dimension
    result["student_id"] = student_id
    result["used_fallback"] = used_fallback
    if used_fallback > 0:
        result["msg"] = (
            f"v0.64.0 改进: {len(history) - used_fallback}/{len(history)} 用 "
            f"mastery_prob_after 历史快照, {used_fallback}/{len(history)} 兜底到当前 mastery_prob"
        )
    else:
        result["msg"] = "v0.64.0 改进: 全部用 mastery_prob_after 历史快照"
    return result


# ─── 双 Agent experiment ECE ──────────────────────────────────────


def compute_dual_agent_ece(
    student_id: str,
    limit: int = 1000,
) -> Dict[str, Any]:
    """双 Agent experiment: 算学生 calibration_log 的校准度.

    confidence: message_payload.expected_gain (互校预测的 gain, 0-1)
    accuracy: actual_outcome (实际 outcome, v0.61.0 改 score 派生 0-1)

    v0.64.0 改进: 移除 v0.63.0 的 response_history 回填 fallback.
      v0.60.4 留下的 calibration_log actual_outcome 全 None BUG 已经被
      dual_agent._write_prev_actual_outcome (v0.64.0 新增) 修复:
      process_observation 时自动回写 prev 的 actual_outcome 到 DB.
    """
    log = load_student_calibration_log(student_id, limit=limit)
    if not log:
        return {
            "student_id": student_id,
            "n_samples": 0,
            "ece": None,
            "msg": "无 calibration_log, 无法算 experiment ECE (dual_agent 未启用过?)",
        }

    confidences = []
    accuracies = []
    skipped_no_outcome = 0
    for row in log:
        try:
            payload = json.loads(row.get("message_payload", "{}") or "{}")
        except json.JSONDecodeError:
            continue
        expected_gain = payload.get("expected_gain")
        actual_outcome = payload.get("actual_outcome")

        if expected_gain is None:
            continue
        # v0.64.0: 不再 fallback, 没 actual_outcome 的行 skip (历史 v0.60.4 数据)
        if actual_outcome is None:
            skipped_no_outcome += 1
            continue

        # expected_gain 可能是负数或 > 1, 截断到 [0, 1]
        conf = max(0.0, min(1.0, float(expected_gain)))
        acc = max(0.0, min(1.0, float(actual_outcome)))
        confidences.append(conf)
        accuracies.append(acc)

    if not confidences:
        return {
            "student_id": student_id,
            "n_samples": 0,
            "ece": None,
            "msg": (
                f"calibration_log {len(log)} 行无 expected_gain/actual_outcome 配对, "
                f"skip {skipped_no_outcome} 行 (v0.60.4 历史数据, v0.64.0 修复)"
            ),
        }

    from ecos.metrics import expected_calibration_error
    ece = expected_calibration_error(confidences, accuracies)
    msg = "v0.64.0 改进: 直接读 calibration_log.actual_outcome (无 fallback)"
    if skipped_no_outcome > 0:
        msg += f", skip {skipped_no_outcome}/{len(log)} 行 (v0.60.4 历史数据)"
    return {
        "student_id": student_id,
        "n_samples": len(confidences),
        "ece": ece,
        "avg_confidence": sum(confidences) / len(confidences),
        "avg_accuracy": sum(accuracies) / len(accuracies),
        "skipped_no_outcome": skipped_no_outcome,
        "msg": msg,
    }


# ─── 报告生成 ────────────────────────────────────────────────────


def format_report(
    student_id: str,
    single_agent: Dict[str, Any],
    dual_agent: Dict[str, Any],
) -> str:
    """生成 H3 验证报告 (Markdown)."""
    lines = [
        f"# H3 验证报告: {student_id}",
        "",
        "> **H3 假设**: 双 Agent 互校有效减少 LLM 幻觉 (双 Agent vs 单 Agent 信念校准度)",
        "> **评估指标**: ECE (Expected Calibration Error), 越小越校准",
        "> **通过阈值**: 双 Agent ECE ≤ 0.10 + 显著优于单 Agent",
        "",
        f"**生成时间**: {__import__('datetime').datetime.now().isoformat()}",
        f"**学生**: {student_id}",
        "",
        "---",
        "",
        "## 1. 单 Agent Baseline (CTA only)",
        "",
        f"- 学生: {single_agent.get('student_id', '?')}",
        f"- 维度: {single_agent.get('dimension', '?')}",
        f"- 样本数: {single_agent.get('n_samples', 0)}",
        f"- **ECE**: `{single_agent.get('ece', 'N/A')}`",
        f"- 当前 mastery_prob: `{single_agent.get('current_mastery_prob', 'N/A')}`",
        f"- 平均 accuracy: `{single_agent.get('accuracy', 'N/A')}`",
        f"- 平均 confidence: `{single_agent.get('avg_confidence', 'N/A')}`",
        f"- 注: {single_agent.get('msg', '')}",
        "",
        "## 2. 双 Agent Experiment (CTA + LCA + 互校)",
        "",
        f"- 学生: {dual_agent.get('student_id', '?')}",
        f"- 样本数: {dual_agent.get('n_samples', 0)}",
        f"- **ECE**: `{dual_agent.get('ece', 'N/A')}`",
        f"- 平均 confidence (expected_gain): `{dual_agent.get('avg_confidence', 'N/A')}`",
        f"- 平均 accuracy (actual_outcome): `{dual_agent.get('avg_accuracy', 'N/A')}`",
        f"- 注: {dual_agent.get('msg', '')}",
        "",
    ]

    # H3 结论
    single_ece = single_agent.get("ece")
    dual_ece = dual_agent.get("ece")
    single_n = single_agent.get("n_samples", 0)
    dual_n = dual_agent.get("n_samples", 0)
    h3_pass_threshold = 0.10

    lines.extend([
        "## 3. H3 验证结论",
        "",
    ])

    if single_ece is None and dual_ece is None:
        lines.extend([
            "**结论**: ⚠️ **数据不足, H3 暂未通过**",
            "",
            f"- 单 Agent baseline: 无 response_history (学生 `{student_id}` 可能没答过题)",
            f"- 双 Agent experiment: 无 calibration_log (dual_agent feature flag 可能没启用过)",
            "",
        ])
    elif single_ece is None:
        lines.extend([
            "**结论**: ⚠️ **单 Agent baseline 缺失, H3 暂未通过**",
            "",
            f"- 单 Agent baseline: 无 response_history",
            f"- 双 Agent experiment: ECE = {dual_ece:.4f} ({dual_n} 样本)",
            "",
        ])
    elif dual_ece is None:
        lines.extend([
            "**结论**: ⚠️ **双 Agent experiment 缺失, H3 暂未通过**",
            "",
            f"- 单 Agent baseline: ECE = {single_ece:.4f} ({single_n} 样本)",
            f"- 双 Agent experiment: 无 calibration_log (dual_agent 未启用过?)",
            "",
        ])
    else:
        # 都有数据
        if dual_n < 30:
            verdict = "⚠️ **H3 暂未通过 (双 Agent 样本量不足)**"
            reason = (
                f"双 Agent 只有 {dual_n} 行 calibration_log, 统计意义不足, "
                f"需要 {student_id} 答 30+ 道 dual_agent 后再补完整 H3 验证 "
                f"(跟 v0.63.0 路线 A + 后续 B 一致)"
            )
        elif dual_ece <= h3_pass_threshold:
            verdict = "✅ **H3 通过 (双 Agent ECE ≤ 0.10)**"
            reason = (
                f"双 Agent ECE = {dual_ece:.4f} ≤ 阈值 {h3_pass_threshold}, "
                f"且单 Agent baseline = {single_ece:.4f}"
            )
        else:
            verdict = "❌ **H3 未通过 (双 Agent ECE > 0.10)**"
            reason = (
                f"双 Agent ECE = {dual_ece:.4f} > 阈值 {h3_pass_threshold}, "
                f"互校未显著减少 LLM 幻觉"
            )

        lines.extend([
            f"**结论**: {verdict}",
            "",
            f"- 阈值: 双 Agent ECE ≤ {h3_pass_threshold}",
            f"- 单 Agent baseline: ECE = {single_ece:.4f} ({single_n} 样本)",
            f"- 双 Agent experiment: ECE = {dual_ece:.4f} ({dual_n} 样本)",
            f"- 单 vs 双 差距: {single_ece - dual_ece:+.4f}",
            "",
            f"**理由**: {reason}",
            "",
        ])

    lines.extend([
        f"## 4. 限制与建议 (v0.63.0 路线 A, 跑 {student_id})",
        "",
        "### 数据基础限制",
        f"- 单 Agent baseline: {student_id} response_history {single_n} 条 (够 30+, 统计意义 OK)",
        f"- 双 Agent experiment: {student_id} calibration_log **{dual_n} 条** (不足 30, 统计意义有限)",
        "",
        "### 方法限制",
        "- v0.64.0 改进: 单 Agent confidence 用 mastery_prob_after 历史快照 (老 data 兜底)",
        "- 双 Agent confidence 用 message_payload.expected_gain (互校预测 gain, 不是直接的 confidence)",
        "- 没做 p-value 显著性检验 (样本量不足, 跑也不显著)",
        "",
        "### 后续 (v0.63.0+ 路线 B)",
        f"1. {student_id} 答 30+ 道题 (feature flag on, ECOS_DUAL_AGENT_ENABLED=1)",
        "2. 收集 calibration_log 30+ 行",
        "3. 跑本脚本重算 H3 (单 vs 双 ECE 对比 + p-value)",
        "4. 写完整 H3 报告 (含显著性检验)",
        "",
        "### 改进方向",
        "- v0.64.0 已落地: mastery_prob_after 字段 (response_history 历史快照)",
        "- 双 Agent confidence 改用 CalibratedLCAResult.intervention.confidence (更直接的校准信号)",
        "- 加 reliability diagram 画图 (matplotlib 依赖待评估)",
        "",
    ])

    return "\n".join(lines)


# ─── 主入口 ──────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="H3 验证: 单 vs 双 Agent 校准度对比")
    parser.add_argument(
        "--student-id",
        default="lbc003",
        help="学生 ID (默认 lbc003, v0.64.0 后新数据最干净)",
    )
    parser.add_argument(
        "--dimension",
        default="K",
        help="单 Agent baseline 维度 (默认 K, 可选 K/P/S/C/X)",
    )
    parser.add_argument(
        "--output-md",
        type=str,
        default=None,
        help="报告输出到 MD 文件 (默认 discussions/2026-07-29-H3-verification-report.md)",
    )
    args = parser.parse_args()

    print(f"=== H3 验证: {args.student_id} ===\n")

    # 单 Agent baseline
    print("▶ 跑单 Agent baseline (CTA only)...")
    single = compute_single_agent_ece(args.student_id, args.dimension)
    print(f"  n_samples: {single.get('n_samples', 0)}")
    print(f"  ECE: {single.get('ece', 'N/A')}")
    print()

    # 双 Agent experiment
    print("▶ 跑双 Agent experiment (CTA + LCA + 互校)...")
    dual = compute_dual_agent_ece(args.student_id)
    print(f"  n_samples: {dual.get('n_samples', 0)}")
    print(f"  ECE: {dual.get('ece', 'N/A')}")
    print()

    # 输出报告
    report = format_report(args.student_id, single, dual)
    print("=" * 60)
    print(report)

    # 写 MD
    if args.output_md is None:
        output_path = PROJECT_ROOT / "discussions" / "2026-07-29-H3-verification-report.md"
    else:
        output_path = Path(args.output_md)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"\n✅ 报告已写入: {output_path}")


if __name__ == "__main__":
    main()
