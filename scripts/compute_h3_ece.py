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

    v0.68.0 改进: 按 calibration_round DISTINCT 去重 (取每 round 最新的 row).
      背景: lbc003 在 dual_agent_state 落盘 thread-safety BUG 期间,
            orch 重启时 round 5-8 各被 process_observation 跑 2 次,
            同一 calibration_round 在 calibration_log 出现 2 行 (重复行).
            H3 验证必须按 round 去重, 否则同一数据被算 2 次.

    Returns:
        List[dict] 每条含: calibration_round, message_payload, actual_outcome, ...
        按 calibration_round 升序, 每个 round 只保留 1 行 (最新的).
    """
    from ecos.persistence.db import get_db
    db = get_db()
    raw = db.load_calibration_history(student_id, limit=limit)
    # 按 timestamp DESC 排序 (load_calibration_history 已经 DESC), 同 round 取第一行
    by_round: Dict[int, Dict[str, Any]] = {}
    duplicates = 0
    for row in raw:
        cr = row.get("calibration_round")
        if cr is None:
            continue
        if cr in by_round:
            duplicates += 1
            continue
        by_round[cr] = row
    # 按 calibration_round 升序返回
    return {"rows": [by_round[cr] for cr in sorted(by_round.keys())],
            "duplicates_dropped": duplicates}


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
    # v0.68.0: 加 calibration_errors (显著性检验用)
    result["calibration_errors"] = [
        abs(c - a) for c, a in zip(confidences, accuracies)
    ]
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

    confidence 来源 (v0.69.0 V3 优先):
      V3 (dual_agent_confidence): LinUCB θ@x 预测答对概率 (v0.69.0+ 新数据)
      V2 (state_overall_confidence): belief_state 5D 平均 (v0.68.0+ 新数据)
      V1 (expected_gain): _estimate_gain 简化估算 (老数据兜底)

    accuracy: actual_outcome (实际 outcome, v0.61.0 改 score 派生 0-1)

    v0.64.0 改进: 移除 v0.63.0 的 response_history 回填 fallback.
      v0.60.4 留下的 calibration_log actual_outcome 全 None BUG 已经被
      dual_agent._write_prev_actual_outcome (v0.64.0 新增) 修复:
      process_observation 时自动回写 prev 的 actual_outcome 到 DB.

    v0.68.0 改进: load_student_calibration_log 已按 calibration_round DISTINCT 去重,
      避免 dual_agent_state 落盘 BUG 期间同 round 重复行被算 2 次.

    v0.69.0 改进: V3 优先 confidence + 冷启动期分段 ECE.
      - 冷启动期 (source="estimate_gain_fallback"): 前 N 道 LinUCB 没数据, expected_gain 用 _estimate_gain
      - 非冷启动期 (source="linucb"): LinUCB θ@x 预测
      - 报告分两段算 ECE, 让 Bisen 直观看到 LinUCB 预测质量
    """
    loaded = load_student_calibration_log(student_id, limit=limit)
    log = loaded["rows"] if isinstance(loaded, dict) else loaded
    duplicates = loaded["duplicates_dropped"] if isinstance(loaded, dict) else 0
    if not log:
        return {
            "student_id": student_id,
            "n_samples": 0,
            "ece": None,
            "msg": "无 calibration_log, 无法算 experiment ECE (dual_agent 未启用过?)",
        }

    # v0.69.0: V3 优先 / V2 其次 / V1 兜底, 同时记录版本分布 + 冷启动标记
    confidences = []
    accuracies = []
    versions = []  # "V3" / "V2" / "V1" per 样本
    cold_start_flags = []  # bool per 样本 (True if source == estimate_gain_fallback)
    skipped_no_outcome = 0
    version_counts = {"V3": 0, "V2": 0, "V1": 0}
    cold_start_counts = {"linucb": 0, "estimate_gain_fallback": 0, "unknown": 0}

    for row in log:
        try:
            payload = json.loads(row.get("message_payload", "{}") or "{}")
        except json.JSONDecodeError:
            continue
        actual_outcome = payload.get("actual_outcome")
        # v0.64.0: 不再 fallback, 没 actual_outcome 的行 skip (历史 v0.60.4 数据)
        if actual_outcome is None:
            skipped_no_outcome += 1
            continue

        # v0.69.0: V3 优先 / V2 其次 / V1 兜底
        dual_conf = payload.get("dual_agent_confidence")
        overall_conf = payload.get("state_overall_confidence")
        expected_gain = payload.get("expected_gain")
        source = payload.get("dual_agent_confidence_source")

        if dual_conf is not None:
            conf = float(dual_conf)
            version = "V3"
            version_counts["V3"] += 1
            # 冷启动标记 (仅 V3 有 source 字段)
            if source == "estimate_gain_fallback":
                cold_start_flags.append(True)
                cold_start_counts["estimate_gain_fallback"] += 1
            elif source == "linucb":
                cold_start_flags.append(False)
                cold_start_counts["linucb"] += 1
            else:
                # V3 数据但 source 缺失 (不应该发生, 但兜底)
                cold_start_flags.append(False)
                cold_start_counts["unknown"] += 1
        elif overall_conf is not None:
            conf = float(overall_conf)
            version = "V2"
            version_counts["V2"] += 1
            # V2 没有 source 字段, 假设非冷启动 (v0.68.0 数据)
            cold_start_flags.append(False)
            cold_start_counts["unknown"] += 1
        else:
            conf = float(expected_gain) if expected_gain is not None else None
            version = "V1"
            version_counts["V1"] += 1
            # V1 没有 source 字段
            cold_start_flags.append(False)
            cold_start_counts["unknown"] += 1

        if conf is None:
            # expected_gain 也是 None, 跳过
            continue

        # 截断到 [0, 1]
        conf = max(0.0, min(1.0, conf))
        acc = max(0.0, min(1.0, float(actual_outcome)))
        confidences.append(conf)
        accuracies.append(acc)
        versions.append(version)

    if not confidences:
        return {
            "student_id": student_id,
            "n_samples": 0,
            "ece": None,
            "msg": (
                f"calibration_log {len(log)} 行无 confidence/actual_outcome 配对, "
                f"skip {skipped_no_outcome} 行 (v0.60.4 历史数据, v0.64.0 修复)"
            ),
        }

    from ecos.metrics import expected_calibration_error
    ece = expected_calibration_error(confidences, accuracies)

    # v0.69.0: 冷启动期 vs 非冷启动期分段 ECE
    #   冷启动期 (前 N 道 LinUCB 没数据, source=estimate_gain_fallback)
    #   非冷启动期 (LinUCB θ@x 预测, source=linucb)
    cold_conf = [c for c, cs in zip(confidences, cold_start_flags) if cs]
    cold_acc = [a for a, cs in zip(accuracies, cold_start_flags) if cs]
    noncold_conf = [c for c, cs in zip(confidences, cold_start_flags) if not cs]
    noncold_acc = [a for a, cs in zip(accuracies, cold_start_flags) if not cs]

    cold_ece = (
        expected_calibration_error(cold_conf, cold_acc)
        if cold_conf else None
    )
    noncold_ece = (
        expected_calibration_error(noncold_conf, noncold_acc)
        if noncold_conf else None
    )

    msg = "v0.69.0 V3 优先 (dual_agent_confidence) / V2 (overall_confidence) / V1 (expected_gain) 兜底"
    if skipped_no_outcome > 0:
        msg += f", skip {skipped_no_outcome}/{len(log)} 行 (v0.60.4 历史数据)"
    if duplicates > 0:
        msg += f", v0.68.0 DISTINCT 去重 drop {duplicates} 行重复 round"

    return {
        "student_id": student_id,
        "n_samples": len(confidences),
        "ece": ece,
        "avg_confidence": sum(confidences) / len(confidences),
        "avg_accuracy": sum(accuracies) / len(accuracies),
        "skipped_no_outcome": skipped_no_outcome,
        "duplicates_dropped": duplicates,
        "calibration_errors": [abs(c - a) for c, a in zip(confidences, accuracies)],
        # v0.69.0 新增字段
        "version_counts": version_counts,
        "versions": versions,  # per 样本版本标记 (供报告分析)
        "cold_start_counts": cold_start_counts,
        "cold_start_flags": cold_start_flags,
        "cold_start_ece": cold_ece,
        "cold_start_n_samples": len(cold_conf),
        "non_cold_start_ece": noncold_ece,
        "non_cold_start_n_samples": len(noncold_conf),
        "msg": msg,
    }


# ─── 报告生成 ────────────────────────────────────────────────────


def compute_significance(
    single: Dict[str, Any],
    dual: Dict[str, Any],
) -> Dict[str, Any]:
    """v0.68.0: 算单 vs 双 Agent 校准误差的显著性 (Welch's t-test + Mann-Whitney U).

    校准误差定义: |confidence - accuracy| per 样本 (越小越校准).
    比较单 vs 双 两组独立样本的校准误差均值, 看双 Agent 是否显著降低校准误差.

    用两个互补检验:
      1. Welch's t-test (scipy.stats.ttest_ind, equal_var=False): 假设近似正态, 参数检验
      2. Mann-Whitney U test (scipy.stats.mannwhitneyu): 非参数, 不要求正态

    p < 0.05 视为统计显著 (H3: 双 Agent 显著优于单 Agent = 校准误差显著更小).

    Returns:
        dict 含 test_name / statistic / p_value / verdict / single_errors / dual_errors.
    """
    from scipy import stats

    single_errors = single.get("calibration_errors", [])
    dual_errors = dual.get("calibration_errors", [])
    if not single_errors or not dual_errors:
        return {
            "test_name": "N/A",
            "statistic": None,
            "p_value": None,
            "verdict": "数据不足, 无法算显著性 (单或双 calibration_errors 空)",
            "single_errors": single_errors,
            "dual_errors": dual_errors,
        }

    # Welch's t-test (independent, unequal variance)
    t_stat, t_p = stats.ttest_ind(single_errors, dual_errors, equal_var=False)
    # Mann-Whitney U test (non-parametric, two-sided)
    u_stat, u_p = stats.mannwhitneyu(single_errors, dual_errors, alternative="two-sided")

    # 选更保守的 p (max of two tests)
    p = max(t_p, u_p)
    test_name = f"Welch t-test + Mann-Whitney U (max p)"

    # H3 假设: 双 Agent < 单 Agent (calibration error)
    single_mean = sum(single_errors) / len(single_errors)
    dual_mean = sum(dual_errors) / len(dual_errors)
    if dual_mean < single_mean and p < 0.05:
        verdict = f"✅ 显著: 双 Agent 校准误差 ({dual_mean:.4f}) < 单 Agent ({single_mean:.4f}), p={p:.4f}"
    elif dual_mean < single_mean and p < 0.10:
        verdict = f"⚠️ 趋势显著: 双 Agent 校准误差 < 单 Agent, p={p:.4f} (< 0.10 但 ≥ 0.05)"
    elif dual_mean < single_mean:
        verdict = f"⚠️ 方向对 (双 < 单) 但 p={p:.4f} ≥ 0.05, 样本量不足"
    elif dual_mean > single_mean:
        verdict = f"❌ 方向反: 双 Agent ({dual_mean:.4f}) > 单 Agent ({single_mean:.4f}), 互校没起作用, p={p:.4f}"
    else:
        verdict = f"➖ 双 = 单, p={p:.4f}"

    return {
        "test_name": test_name,
        "t_stat": float(t_stat),
        "t_p": float(t_p),
        "u_stat": float(u_stat),
        "u_p": float(u_p),
        "p_value": float(p),
        "single_mean": single_mean,
        "dual_mean": dual_mean,
        "single_n": len(single_errors),
        "dual_n": len(dual_errors),
        "verdict": verdict,
        "single_errors": single_errors,
        "dual_errors": dual_errors,
    }


def format_report(
    student_id: str,
    single_agent: Dict[str, Any],
    dual_agent: Dict[str, Any],
    significance: Optional[Dict[str, Any]] = None,
) -> str:
    """生成 H3 验证报告 (Markdown).

    v0.68.0: 加 significance 参数 (单 vs 双 calibration error 显著性检验).
    """
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
        f"- 平均 confidence (v0.69.0 V3 优先): `{dual_agent.get('avg_confidence', 'N/A')}`",
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

    # v0.68.0: §5 显著性检验 (单 vs 双 calibration error)
    if significance is not None and significance.get("p_value") is not None:
        lines.extend([
            "## 5. 显著性检验 (v0.68.0 新增)",
            "",
            f"**检验方法**: {significance.get('test_name', '?')}",
            f"**校准误差定义**: per 样本 |confidence - accuracy| (越小越校准)",
            "",
            f"- 单 Agent 校准误差均值: `{significance.get('single_mean', 0):.4f}` ({significance.get('single_n', 0)} 样本)",
            f"- 双 Agent 校准误差均值: `{significance.get('dual_mean', 0):.4f}` ({significance.get('dual_n', 0)} 样本)",
            f"- Welch's t-test: t = {significance.get('t_stat', 0):.4f}, p = {significance.get('t_p', 0):.4f}",
            f"- Mann-Whitney U: U = {significance.get('u_stat', 0):.4f}, p = {significance.get('u_p', 0):.4f}",
            f"- **综合 p-value (取 max)**: `{significance.get('p_value', 0):.4f}`",
            "",
            f"**结论**: {significance.get('verdict', '?')}",
            "",
            "### 显著性解读",
            "- p < 0.05: 强烈支持 H3 (双 Agent 显著降低校准误差)",
            "- 0.05 ≤ p < 0.10: 趋势支持, 建议增大样本量再验",
            "- p ≥ 0.10: 当前数据不足以支持 H3, 方向对但需更多样本",
            "",
        ])
    else:
        lines.extend([
            "## 5. 显著性检验 (v0.68.0 新增)",
            "",
            "**跳过**: 数据不足, 无法算显著性",
            "",
        ])

    # v0.69.0: §6 V3/V2/V1 版本分布 + 冷启动分段
    version_counts = dual_agent.get("version_counts", {})
    cold_start_counts = dual_agent.get("cold_start_counts", {})
    cold_ece = dual_agent.get("cold_start_ece")
    cold_n = dual_agent.get("cold_start_n_samples", 0)
    noncold_ece = dual_agent.get("non_cold_start_ece")
    noncold_n = dual_agent.get("non_cold_start_n_samples", 0)

    lines.extend([
        "## 6. v0.69.0 Confidence 版本分布 + 冷启动分段",
        "",
        "### 6.1 Confidence 来源版本分布 (V3 优先 / V2 其次 / V1 兜底)",
        "",
        f"- V3 (dual_agent_confidence, LinUCB θ@x): **{version_counts.get('V3', 0)} 样本**",
        f"- V2 (state_overall_confidence, belief_state 5D 平均): **{version_counts.get('V2', 0)} 样本**",
        f"- V1 (expected_gain, _estimate_gain 简化估算): **{version_counts.get('V1', 0)} 样本**",
        f"- 合计: {sum(version_counts.values())} 样本",
        "",
        "### 6.2 冷启动期 vs 非冷启动期分段 (仅 V3 数据有 source 标记)",
        "",
        f"- LinUCB 预测 (source=\"linucb\"): **{cold_start_counts.get('linucb', 0)} 样本**",
        f"- _estimate_gain fallback (source=\"estimate_gain_fallback\"): **{cold_start_counts.get('estimate_gain_fallback', 0)} 样本**",
        f"- source 缺失 (V2/V1 老数据): **{cold_start_counts.get('unknown', 0)} 样本**",
        "",
    ])

    # 冷启动分段 ECE
    if cold_ece is not None and noncold_ece is not None:
        lines.extend([
            "### 6.3 分段 ECE 对比 (验证 B4 LinUCB 预测质量)",
            "",
            f"- **冷启动期 ECE** (LinUCB 没数据, 走 _estimate_gain fallback): `{cold_ece:.4f}` ({cold_n} 样本)",
            f"- **非冷启动期 ECE** (LinUCB θ@x 预测): `{noncold_ece:.4f}` ({noncold_n} 样本)",
            "",
        ])
        if noncold_ece < cold_ece:
            lines.extend([
                f"**结论**: ✅ 非冷启动期 ECE ({noncold_ece:.4f}) < 冷启动期 ({cold_ece:.4f})",
                f"  LinUCB θ@x 预测质量优于 _estimate_gain fallback, B4 方案有效",
                "",
            ])
        elif noncold_ece > cold_ece:
            lines.extend([
                f"**结论**: ❌ 非冷启动期 ECE ({noncold_ece:.4f}) > 冷启动期 ({cold_ece:.4f})",
                f"  LinUCB θ@x 预测质量反而差于 _estimate_gain fallback, B4 方案失败",
                f"  可能原因: LinUCB reward=actual_outcome 改造后, 历史 calibration_round",
                f"  数据对比性下降 (老数据 reward=state_delta, 新数据 reward=actual_outcome)",
                "",
            ])
        else:
            lines.extend([
                f"**结论**: ➖ 非冷启动期 ECE = 冷启动期 ECE, LinUCB 预测质量与 fallback 相同",
                "",
            ])
    elif cold_ece is not None:
        lines.extend([
            "### 6.3 分段 ECE 对比",
            "",
            f"- 冷启动期 ECE: `{cold_ece:.4f}` ({cold_n} 样本)",
            f"- 非冷启动期 ECE: 数据不足 (LinUCB 还没积累 10+ arm pulls)",
            "",
            "**结论**: ⚠️ LinUCB 还在冷启动期, 等 lbc003 答 10+ 道后再看非冷启动段 ECE",
            "",
        ])
    elif noncold_ece is not None:
        lines.extend([
            "### 6.3 分段 ECE 对比",
            "",
            f"- 冷启动期 ECE: 数据不足 (无 source=estimate_gain_fallback 样本)",
            f"- 非冷启动期 ECE: `{noncold_ece:.4f}` ({noncold_n} 样本)",
            "",
        ])
    else:
        lines.extend([
            "### 6.3 分段 ECE 对比",
            "",
            "**数据不足**: 没有带 source 标记的 V3 样本, 无法分段",
            "",
        ])

    lines.extend([
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
        help="报告输出到 MD 文件 (默认 discussions/2026-07-30-v0690-H3-verification-report.md, v0.69.0 改 B+ 报告, 不覆盖 B)",
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

    # v0.68.0: 算单 vs 双 显著性 (校准误差)
    print("▶ 算单 vs 双 显著性 (Welch t + Mann-Whitney U)...")
    significance = compute_significance(single, dual)
    if significance.get("p_value") is not None:
        print(f"  单 Agent 校准误差均值: {significance['single_mean']:.4f} ({significance['single_n']} 样本)")
        print(f"  双 Agent 校准误差均值: {significance['dual_mean']:.4f} ({significance['dual_n']} 样本)")
        print(f"  p-value: {significance['p_value']:.4f}")
        print(f"  verdict: {significance['verdict']}")
    else:
        print(f"  {significance.get('verdict', '?')}")
    print()

    # 输出报告 (v0.68.0: 加 significance 参数)
    report = format_report(args.student_id, single, dual, significance)
    print("=" * 60)
    print(report)

    # 写 MD (v0.69.0: default 改 B+ 报告, 不覆盖 B)
    if args.output_md is None:
        output_path = PROJECT_ROOT / "discussions" / "2026-07-30-v0690-H3-verification-report.md"
    else:
        output_path = Path(args.output_md)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"\n✅ 报告已写入: {output_path}")


if __name__ == "__main__":
    main()
