"""v0.75 P0-l.1: Global Platt 训练 + offline cold start 模拟.

两步走 Phase 1:
  1. 重放 lbc001 (60) + lbc002 (45) = 105 pairs, 提取 (raw_V3, actual) pairs
  2. 训 global Platt Scaling (跟 v0.72 per-student 同样算法)
  3. 用 global Platt 给 lbc003 前 5 轮 cold start 预测
  4. 对比 global Platt 跟 v0.74 mean_mastery_fallback (gap 0.20) 的冷启动 ECE
  5. 决策: 改善 > 0.05 -> P0-l.3 跟 lbc004 验证; 否则放弃 v0.75 走 Plan B

防御性自检:
  - 数据分布检查: lbc001/2 raw_V3 vs lbc003 raw_V3 (Kolmogorov-Smirnov 或简单统计对比)
  - 任何 scipy 优化失败: _log.warning, 保持 identity, 不 raise
  - 不写 DB, 纯离线分析

用法:
  python scripts/v075_global_platt_analysis.py
"""

from __future__ import annotations

import json
import logging
import sqlite3
import sys
from pathlib import Path

import numpy as np

# 加 repo root 到 path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ecos.cta.belief_engine import Observation
from ecos.cta.belief_state import BloomLevel
from ecos.dual_agent.orchestrator import DualAgentConfig, DualAgentOrchestrator
from ecos.dual_agent.calibration import PlattScaler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
_log = logging.getLogger(__name__)


def replay_student(sid: str, response_history: list) -> list:
    """重放一个学生通过 DualAgentOrchestrator, 提取 (raw_V3, actual_outcome) pairs.

    关键: actual_outcome 在 round i+1 的 process_observation Step 0 写回 calibrated_i.
    所以必须先跑完所有 rounds, 再第二轮扫描 intervention_history 提取 pairs.

    Returns:
        list of (round, raw_V3, actual_outcome) tuples
    """
    bloom_map = {
        "REMEMBER": BloomLevel.REMEMBER, "UNDERSTAND": BloomLevel.UNDERSTAND,
        "APPLY": BloomLevel.APPLY, "ANALYZE": BloomLevel.ANALYZE,
        "EVALUATE": BloomLevel.EVALUATE, "CREATE": BloomLevel.CREATE,
    }

    # v0.79: skill_id 从 Q 矩阵按 problem_id 查真实 topic (替代硬编码 "variables")
    qm_path = Path(__file__).resolve().parents[1] / "data" / "python_basics_q_matrix.json"
    with open(qm_path) as f:
        qm = json.load(f)
    pid_to_topic = {p["problem_id"]: p["topic"] for p in qm["problems"]}

    orch = DualAgentOrchestrator(config=DualAgentConfig(), llm_client=None)

    # 步骤 1: 跑完全部 rounds
    for h in response_history:
        pid = h["problem_id"]
        obs = Observation(
            problem_id=pid, skill_id=pid_to_topic.get(pid, "python.variables"),
            correct=bool(h.get("correct", 0)), score=float(h.get("score", 0.0)),
            bloom_level=bloom_map.get(h.get("bloom_level", "APPLY"), BloomLevel.APPLY),
            response_time_sec=0.0,
        )
        orch.process_observation(obs, student_id=sid)

    # 步骤 2: 第二轮扫描, 提取 (raw_V3, actual) pairs
    #   - 过滤: raw_V3 / calibrated / actual 都 not None
    #   - 最后一轮 actual=None (没有 next round 写回), 会被过滤掉
    pairs = []
    for i, cal in enumerate(orch.intervention_history[sid]):
        raw_v3 = cal.metadata.get("dual_agent_confidence")
        actual = cal.actual_outcome
        if raw_v3 is not None and actual is not None:
            pairs.append((i, float(raw_v3), float(actual)))

    return pairs


def load_response_history(conn: sqlite3.Connection, sid: str) -> list:
    """从 DB 加载学生 response_history."""
    row = conn.execute(
        "SELECT response_history FROM students WHERE student_id=?",
        (sid,),
    ).fetchone()
    if not row or not row[0]:
        return []
    return json.loads(row[0])


def fit_global_platt(all_pairs: list, l2_lambda: float = 0.01) -> PlattScaler:
    """用全部 (raw_V3, actual) pairs 训 global Platt Scaling.

    Args:
        all_pairs: list of (raw_v3, actual_outcome) tuples
        l2_lambda: L2 正则化系数 (跟 per-student 一样, 默认 0.01)

    Returns:
        训好的 PlattScaler (single global instance, per-student offset 后续接)
    """
    raw_confs = np.array([p[0] for p in all_pairs], dtype=float)
    actuals = np.array([p[1] for p in all_pairs], dtype=float)

    _log.info(
        "训练 global Platt: n_pairs=%d, raw_V3 范围 [%.3f, %.3f], mean=%.3f",
        len(raw_confs), raw_confs.min(), raw_confs.max(), raw_confs.mean(),
    )

    scaler = PlattScaler(l2_lambda=l2_lambda)
    scaler.fit(raw_confs, actuals)
    _log.info(
        "global Platt 训好: A=%.4f, B=%.4f, _fitted=%s",
        scaler.A, scaler.B, scaler._fitted,
    )
    return scaler


def analyze_distribution(name: str, pairs: list) -> dict:
    """分析一组 (raw_V3, actual) pairs 的分布.

    Args:
        pairs: list of (round_index, raw_v3, actual_outcome) tuples
    """
    raw = np.array([p[1] for p in pairs])  # p[1] = raw_v3
    actual = np.array([p[2] for p in pairs])  # p[2] = actual_outcome
    return {
        "name": name,
        "n": len(pairs),
        "raw_min": float(raw.min()),
        "raw_max": float(raw.max()),
        "raw_mean": float(raw.mean()),
        "raw_std": float(raw.std()),
        "actual_mean": float(actual.mean()),
        "actual_std": float(actual.std()),
        "raw_percentiles": {
            "p10": float(np.percentile(raw, 10)),
            "p50": float(np.percentile(raw, 50)),
            "p90": float(np.percentile(raw, 90)),
        },
    }


def compare_cold_start(
    lbc003_pairs: list,
    global_platt: PlattScaler,
    cold_start_n: int = 5,
) -> dict:
    """对比 global Platt 跟 v0.74 mean_mastery_fallback 在 lbc003 cold start 的表现.

    Args:
        lbc003_pairs: lbc003 全部 (raw_V3, actual) pairs
        global_platt: 训好的 global Platt
        cold_start_n: cold start 样本数 (默认 5, 跟 v0.74 一致)

    Returns:
        dict 包含两种方法的 5 样本 conf vs actual 跟 gap
    """
    # lbc003 cold start: 前 5 轮 calibrated (跟 v0.74 一致)
    cold_pairs = lbc003_pairs[:cold_start_n]
    raw_confs = np.array([p[1] for p in cold_pairs])  # p[1] = raw_v3
    actuals = np.array([p[2] for p in cold_pairs])  # p[2] = actual_outcome

    # v0.74 baseline: mean_mastery_fallback 实测 conf 0.80 (lbc003 cold start 5 样本)
    v074_mean_mastery_conf = 0.80

    # global Platt 校准
    if global_platt._fitted:
        global_calibrated = np.array([global_platt.transform(float(c)) for c in raw_confs])
    else:
        global_calibrated = raw_confs.copy()

    # 计算两种方法的 gap
    v074_gaps = np.abs(np.full_like(actuals, v074_mean_mastery_conf) - actuals)
    global_gaps = np.abs(global_calibrated - actuals)

    return {
        "cold_start_n": cold_start_n,
        "raw_v3_mean": float(raw_confs.mean()),
        "raw_v3_mean_gap": float(np.mean(np.abs(raw_confs - actuals))),
        "v074_mean_mastery_conf": v074_mean_mastery_conf,
        "v074_mean_gap": float(v074_gaps.mean()),
        "global_platt_mean": float(global_calibrated.mean()),
        "global_platt_mean_gap": float(global_gaps.mean()),
        "improvement": float(v074_gaps.mean() - global_gaps.mean()),
        "raw_v3_values": [float(c) for c in raw_confs],
        "global_calibrated_values": [float(c) for c in global_calibrated],
        "actual_values": [float(a) for a in actuals],
    }


def main():
    """主函数: 重放 lbc001/2/3, 训 global Platt, 评估 cold start."""
    db_path = "web/ecos.db"
    conn = sqlite3.connect(db_path)

    # 1. 加载 lbc001/2/3 全部 response_history
    lbc001_rh = load_response_history(conn, "lbc001")
    lbc002_rh = load_response_history(conn, "lbc002")
    lbc003_rh = load_response_history(conn, "lbc003")
    _log.info(
        "加载 response_history: lbc001=%d, lbc002=%d, lbc003=%d",
        len(lbc001_rh), len(lbc002_rh), len(lbc003_rh),
    )

    # 2. 重放每个学生, 提取 (raw_V3, actual) pairs
    _log.info("开始重放 lbc001...")
    lbc001_pairs = replay_student("replay_lbc001", lbc001_rh)
    _log.info("lbc001 提取 %d pairs", len(lbc001_pairs))

    _log.info("开始重放 lbc002...")
    lbc002_pairs = replay_student("replay_lbc002", lbc002_rh)
    _log.info("lbc002 提取 %d pairs", len(lbc002_pairs))

    _log.info("开始重放 lbc003...")
    lbc003_pairs = replay_student("replay_lbc003", lbc003_rh)
    _log.info("lbc003 提取 %d pairs", len(lbc003_pairs))

    # 3. 数据分布对比 (关键防御性自检: lbc001/2 跟 lbc003 分布差异)
    lbc001_dist = analyze_distribution("lbc001", lbc001_pairs)
    lbc002_dist = analyze_distribution("lbc002", lbc002_pairs)
    lbc003_dist = analyze_distribution("lbc003", lbc003_pairs)
    _log.info("lbc001 分布: %s", lbc001_dist)
    _log.info("lbc002 分布: %s", lbc002_dist)
    _log.info("lbc003 分布: %s", lbc003_dist)

    # 4. 训 global Platt (lbc001 + lbc002 = 105+ pairs)
    source_pairs = [(p[1], p[2]) for p in lbc001_pairs + lbc002_pairs]
    global_platt = fit_global_platt(source_pairs)

    # 5. 评估 cold start (lbc003 前 5 轮)
    cold_start_result = compare_cold_start(lbc003_pairs, global_platt, cold_start_n=5)
    _log.info("=" * 60)
    _log.info("Cold start 评估 (lbc003 前 5 轮):")
    _log.info("  raw V3 mean gap: %.4f (v0.72/v0.73 实际)", cold_start_result["raw_v3_mean_gap"])
    _log.info("  v0.74 mean_mastery conf: %.4f, gap: %.4f",
              cold_start_result["v074_mean_mastery_conf"], cold_start_result["v074_mean_gap"])
    _log.info("  v0.75 global Platt conf: %.4f, gap: %.4f",
              cold_start_result["global_platt_mean"], cold_start_result["global_platt_mean_gap"])
    _log.info("  改善: %.4f (vs v0.74)", cold_start_result["improvement"])
    _log.info("=" * 60)
    _log.info("原始 raw_V3: %s", cold_start_result["raw_v3_values"])
    _log.info("global Platt 校准: %s", cold_start_result["global_calibrated_values"])
    _log.info("actual: %s", cold_start_result["actual_values"])

    # 6. 决策建议
    improvement = cold_start_result["improvement"]
    if improvement > 0.05:
        decision = "✅ 改善 > 0.05, 建议进 P0-l.3 (建 lbc004 验证)"
    elif improvement > 0:
        decision = "⚠️ 改善 0-0.05, 边际改善, 跟 Bisen 讨论后再决定"
    else:
        decision = "❌ 没改善 / 变差, 放弃 v0.75 跨学生迁移, 走 Plan B"

    _log.info("=" * 60)
    _log.info("决策: %s", decision)
    _log.info("=" * 60)

    # 7. 存结果到 JSON (给后续报告用)
    output = {
        "distributions": [lbc001_dist, lbc002_dist, lbc003_dist],
        "global_platt_params": {
            "A": global_platt.A,
            "B": global_platt.B,
            "l2_lambda": global_platt.l2_lambda,
            "fitted": global_platt._fitted,
        },
        "cold_start_evaluation": cold_start_result,
        "decision": decision,
    }
    output_path = "discussions/2026-08-04-v075-P0-l1-global-platt-analysis.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    _log.info("结果保存到 %s", output_path)


if __name__ == "__main__":
    main()
