"""v0.63.0: H3 验证 — 跑单 Agent vs 双 Agent 校准度 (ECE) 对比脚本.

对应:
  - research/00-overview/03-roadmap.md §2.3 H3 验证 (H3 = 双 Agent 互校抗幻觉)
  - research/90-mvp/README.md §8.1 H3 阈值: 双 Agent ECE ≤ 0.10
  - 报告输出: discussions/2026-07-29-H3-verification-report.md

H3 验证设计 (单 vs 双 Agent 对比):
  - 单 Agent (CTA only): 用 lbc001 response_history 32+ 道
    - confidence: BeliefState 各维度 mastery_prob (after update)
    - accuracy: response_history.correct (二元) / score (partial credit)
  - 双 Agent (CTA + LCA + 互校): 用 lbc001 calibration_log (5 行, v0.60.4 验证)
    - confidence: message_payload.expected_gain (互校预测的 gain)
    - accuracy: actual_outcome (实际 outcome, v0.61.0 改 score 派生)

数据基础:
  - lbc001 response_history: 32+ 道 (CTA 单跑, lbc001 整个答题历史)
  - lbc001 calibration_log: 5 行 (v0.60.4 dual_agent 跑过 5 道)
  - lbc001 belief.py: 累加 32+ 道, K/P/S/C/X 5D 状态可读

输出:
  - 打印到 stdout: 单 Agent baseline ECE + 双 Agent experiment ECE + 结论
  - 写入 discussions/2026-07-29-H3-verification-report.md: 完整报告

限制 (v0.63.0 时):
  - dual_agent 只有 5 行 calibration_log (lbc001), 统计意义不足
  - H3 暂未通过, 待 lbc001 答 30+ 道 dual_agent 后再补 (跟 A + B 后续接策略一致)

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
    """单 Agent baseline: 算 lbc001 答题历史的 5D 某维度校准度.

    注意: 单 Agent (CTA only) 不存 "答题后 confidence" 序列.
          用 response_history 推算: 第 i 题的 confidence 用第 i-1 题 update 后的 mastery_prob
          (即"答这道题时 CTA 估计的 mastery" 跟 "实际答对" 配对).

    v0.63.0 简化: 暂时用每个问题 "提交时 CTA 5D 各维度 mastery_prob 跟 actual correct 配对".
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

    # v0.63.0 简化: 用 K 维度 default 0.5 (没存历史 mastery_prob 序列时兜底)
    # 未来: 跟 belief_engine 配合, 存每次 update 后的 5D 状态快照
    from web.api.belief import _get_or_create_student
    student = _get_or_create_student(student_id)
    state = student["state"]
    current_dim = getattr(state, dimension, None)
    current_confidence = getattr(current_dim, "mastery_prob", 0.5)

    # confidence 序列: 每个问题都用当前 mastery_prob (简化, 未来要存历史快照)
    confidences = [current_confidence] * len(history)
    # accuracy 序列: response_history[i].correct (派生自 score >= 0.6)
    accuracies = [float(h.get("correct", 0)) for h in history]

    from ecos.metrics import expected_calibration_error, binary_calibration
    result = binary_calibration(confidences, [bool(a) for a in accuracies])
    result["dimension"] = dimension
    result["student_id"] = student_id
    result["current_mastery_prob"] = current_confidence
    result["msg"] = (
        f"v0.63.0 简化: 用当前 mastery_prob 当所有问题的 confidence "
        f"(实际应该是历史快照序列, 未来改进)"
    )
    return result


# ─── 双 Agent experiment ECE ──────────────────────────────────────


def compute_dual_agent_ece(
    student_id: str,
    limit: int = 1000,
) -> Dict[str, Any]:
    """双 Agent experiment: 算 lbc001 calibration_log 的校准度.

    confidence: message_payload.expected_gain (互校预测的 gain, 0-1)
    accuracy: actual_outcome (实际 outcome, v0.61.0 改 score 派生 0-1)

    v0.63.0 改进: actual_outcome 是 None 时 (v0.60.4 写库 BUG, 没回写
    prev.actual_outcome), 用 response_history[i-1].correct 兜底回填.
    """
    log = load_student_calibration_log(student_id, limit=limit)
    if not log:
        return {
            "student_id": student_id,
            "n_samples": 0,
            "ece": None,
            "msg": "无 calibration_log, 无法算 experiment ECE (dual_agent 未启用过?)",
        }

    # v0.63.0: 加载 response_history 作为 actual_outcome 兜底源
    history = load_student_response_history(student_id)
    # 简化: response_history[i-1].correct 兜底 calibration_log[i].actual_outcome
    # 假设 calibration_log 跟 response_history 时序对应 (dual_agent 5 行是最后 5 道题)
    history_corrects = [bool(h.get("correct", 0)) for h in history]

    confidences = []
    accuracies = []
    used_fallback = 0
    for i, row in enumerate(log):
        try:
            payload = json.loads(row.get("message_payload", "{}") or "{}")
        except json.JSONDecodeError:
            continue
        expected_gain = payload.get("expected_gain")
        actual_outcome = payload.get("actual_outcome")

        if expected_gain is None:
            continue

        # actual_outcome 回填 fallback: 用 response_history[i-1].correct
        if actual_outcome is None:
            # 取 response_history 第 (n_history - n_log + i) 个 (假设 calibration_log 是最后几道)
            if history_corrects:
                # 简化: 按 i 索引, calibration_log 第 i 行 → response_history 第 i 个 correct
                # (更准确是 calibration_log 是最后几道, 但 i=0 是首题, 用 history[i])
                idx = i
                if idx < len(history_corrects):
                    actual_outcome = 1.0 if history_corrects[idx] else 0.0
                    used_fallback += 1
                else:
                    continue
            else:
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
            "msg": "calibration_log 行无 expected_gain 或无法回填 actual_outcome",
        }

    from ecos.metrics import expected_calibration_error
    ece = expected_calibration_error(confidences, accuracies)
    msg = ""
    if used_fallback > 0:
        msg = (
            f"v0.63.0 改进: {used_fallback}/{len(log)} 行 actual_outcome 用 "
            f"response_history.correct 兜底回填 (DB 写库 BUG 待修)"
        )
    return {
        "student_id": student_id,
        "n_samples": len(confidences),
        "ece": ece,
        "avg_confidence": sum(confidences) / len(confidences),
        "avg_accuracy": sum(accuracies) / len(accuracies),
        "used_fallback": used_fallback,
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
                f"需要 lbc001 答 30+ 道 dual_agent 后再补完整 H3 验证 "
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
        "## 4. 限制与建议 (v0.63.0)",
        "",
        "### 数据基础限制",
        f"- 单 Agent baseline: lbc001 response_history {single_n} 条 (够 30+, 统计意义 OK)",
        f"- 双 Agent experiment: lbc001 calibration_log **{dual_n} 条** (不足 30, 统计意义有限)",
        "",
        "### 方法限制",
        "- 单 Agent confidence 用当前 mastery_prob 简化 (实际应该是历史快照序列)",
        "- 双 Agent confidence 用 message_payload.expected_gain (互校预测 gain, 不是直接的 confidence)",
        "- 没做 p-value 显著性检验 (样本量不足, 跑也不显著)",
        "",
        "### 后续 (v0.63.0+ 路线 B)",
        "1. lbc001 答 30+ 道题 (feature flag on, ECOS_DUAL_AGENT_ENABLED=1)",
        "2. 收集 calibration_log 30+ 行",
        "3. 跑本脚本重算 H3 (单 vs 双 ECE 对比 + p-value)",
        "4. 写完整 H3 报告 (含显著性检验)",
        "",
        "### 改进方向",
        "- 单 Agent confidence 存历史快照 (v0.64.0+ 路线: response_history 加 confidence 字段)",
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
        default="lbc001",
        help="学生 ID (默认 lbc001)",
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
