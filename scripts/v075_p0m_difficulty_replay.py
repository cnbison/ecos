"""v0.75 P0-m: LinUCB difficulty feature (17 维 context) ECE 评估.

目标:
  v0.74 ECE 0.24 卡在 Platt/Isotonic 阶段 bin [0.9, 1.0] gap +0.10
  (49/54 样本, 90.7% 权重). 根因: 16 维 context 看不到干预难度, 同一
  raw_V3 0.40 对应易/难干预给同样预测, 校准后高 conf bin 系统误差.

方案:
  LinUCB context 16 -> 17 维 (末尾加 intervention.difficulty).
  use_arm_features=True 时, 每个候选独立 17 维 context 评估,
  LinUCB 能学到"这个学生 + 这个难度 -> 期望答对概率".

评估:
  重放 lbc003 对比 use_arm_features=False (v0.74 行为) vs True,
  读 calibrated V3 (production 路径: cold start fallback + Platt + Isotonic)
  算 calibrated V3 全局 ECE + 冷启动 + 分布.

用法:
  python scripts/v075_p0m_difficulty_replay.py
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
from ecos.lca.l4_optimization.linucb import BanditConfig
from ecos.lca.orchestrator import LCAEngineConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
_log = logging.getLogger(__name__)


def replay_lbc003(use_arm_features: bool) -> dict:
    """重放 lbc003, 返回 raw_V3 + actual + calibrated_V3 (production path) 序列.

    关键: 走完整 DualAgentOrchestrator, 让 calibration (cold start fallback +
    Platt + Isotonic) 自动跑. 读 metadata['dual_agent_confidence_calibrated'].

    Returns:
        dict {
            "raw_v3s": np.array,
            "actuals": np.array,
            "calibrated_v3s": np.array,  # 走 production calibration path
            "sources": list,  # source 标记 (raw_v3_fallback / mean_mastery_fallback / platt_scaling / ...)
        }
    """
    # 加载 lbc003 response_history
    conn = sqlite3.connect("web/ecos.db")
    row = conn.execute(
        "SELECT response_history FROM students WHERE student_id='lbc003'"
    ).fetchone()
    rh = json.loads(row[0])
    _log.info("lbc003 response_history: %d 条", len(rh))

    # v0.79: skill_id 从 Q 矩阵按 problem_id 查真实 topic (替代硬编码 "variables")
    qm_path = Path(__file__).resolve().parents[1] / "data" / "python_basics_q_matrix.json"
    with open(qm_path) as f:
        qm = json.load(f)
    pid_to_topic = {p["problem_id"]: p["topic"] for p in qm["problems"]}

    bloom_map = {
        "REMEMBER": BloomLevel.REMEMBER, "UNDERSTAND": BloomLevel.UNDERSTAND,
        "APPLY": BloomLevel.APPLY, "ANALYZE": BloomLevel.ANALYZE,
        "EVALUATE": BloomLevel.EVALUATE, "CREATE": BloomLevel.CREATE,
    }

    # 配置 LCA + dual_agent: use_arm_features 开关
    bandit_cfg = BanditConfig(use_arm_features=use_arm_features)
    lca_cfg = LCAEngineConfig(bandit_config=bandit_cfg)
    dual_cfg = DualAgentConfig(lca_config=lca_cfg)
    orch = DualAgentOrchestrator(config=dual_cfg, llm_client=None)
    sid = f"replay_v075_p0m_arm_{use_arm_features}"

    # 跑完全部 rounds (actual_outcome 在 process_observation 时写回 prev)
    for h in rh:
        pid = h["problem_id"]
        obs = Observation(
            problem_id=pid, skill_id=pid_to_topic.get(pid, "python.variables"),
            correct=bool(h.get("correct", 0)),
            score=float(h.get("score", 0.0)),
            bloom_level=bloom_map.get(h.get("bloom_level", "APPLY"), BloomLevel.APPLY),
            response_time_sec=0.0,
        )
        orch.process_observation(obs, student_id=sid)

    # 提取 (raw_V3, actual_outcome, calibrated_V3) triples
    raw_v3s, actuals, calibrated_v3s, sources = [], [], [], []
    for cal in orch.intervention_history[sid]:
        raw = cal.metadata.get("dual_agent_confidence")
        actual = cal.actual_outcome
        calibrated = cal.metadata.get("dual_agent_confidence_calibrated")
        source = cal.metadata.get("dual_agent_confidence_calibrated_source", "unknown")
        if raw is not None and actual is not None and calibrated is not None:
            raw_v3s.append(float(raw))
            actuals.append(float(actual))
            calibrated_v3s.append(float(calibrated))
            sources.append(source)

    return {
        "raw_v3s": np.array(raw_v3s),
        "actuals": np.array(actuals),
        "calibrated_v3s": np.array(calibrated_v3s),
        "sources": sources,
        "n_pairs": len(raw_v3s),
    }


def compute_ece(confidences: np.ndarray, accuracies: np.ndarray, n_bins: int = 10) -> float:
    """算 Expected Calibration Error (10-bin 等宽分箱)."""
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n = len(confidences)
    for i in range(n_bins):
        lo, hi = bin_boundaries[i], bin_boundaries[i + 1]
        # 最后一 bin 包含右端点 1.0
        if i == n_bins - 1:
            mask = (confidences >= lo) & (confidences <= hi)
        else:
            mask = (confidences >= lo) & (confidences < hi)
        if mask.sum() == 0:
            continue
        bin_conf = confidences[mask].mean()
        bin_acc = accuracies[mask].mean()
        ece += (mask.sum() / n) * abs(bin_conf - bin_acc)
    return float(ece)


def compute_bin_gaps(confidences: np.ndarray, accuracies: np.ndarray, n_bins: int = 10) -> list:
    """算每个 bin 的 (conf, acc, gap, n)."""
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    bins = []
    for i in range(n_bins):
        lo, hi = bin_boundaries[i], bin_boundaries[i + 1]
        if i == n_bins - 1:
            mask = (confidences >= lo) & (confidences <= hi)
        else:
            mask = (confidences >= lo) & (confidences < hi)
        n = int(mask.sum())
        if n == 0:
            continue
        bins.append({
            "bin": f"[{lo:.1f}, {hi:.1f}]",
            "n": n,
            "conf": float(confidences[mask].mean()),
            "acc": float(accuracies[mask].mean()),
            "gap": float(abs(confidences[mask].mean() - accuracies[mask].mean())),
        })
    return bins


def main():
    """跑 v0.75 P0-m ECE 评估: use_arm_features=False vs True."""
    _log.info("=" * 60)
    _log.info("v0.75 P0-m ECE 评估")
    _log.info("=" * 60)

    # 1. 跑两次: use_arm_features=False (v0.74 行为) vs True
    _log.info("▶ 跑 use_arm_features=False (v0.74 行为)...")
    off = replay_lbc003(use_arm_features=False)
    _log.info("  提取 %d pairs", off["n_pairs"])

    _log.info("▶ 跑 use_arm_features=True (v0.75 P0-m)...")
    on = replay_lbc003(use_arm_features=True)
    _log.info("  提取 %d pairs", on["n_pairs"])

    # 2. 算 ECE (raw + calibrated)
    off_raw_ece = compute_ece(off["raw_v3s"], off["actuals"])
    on_raw_ece = compute_ece(on["raw_v3s"], on["actuals"])
    off_cal_ece = compute_ece(off["calibrated_v3s"], off["actuals"])
    on_cal_ece = compute_ece(on["calibrated_v3s"], on["actuals"])

    # 3. 算 bin [0.9, 1.0] gap (主要瓶颈)
    off_bins = compute_bin_gaps(off["calibrated_v3s"], off["actuals"])
    on_bins = compute_bin_gaps(on["calibrated_v3s"], on["actuals"])

    def find_high_bin(bins):
        for b in bins:
            if b["bin"] == "[0.9, 1.0]":
                return b
        return None

    off_high = find_high_bin(off_bins)
    on_high = find_high_bin(on_bins)

    # 4. 算冷启动期 vs 非冷启动期分段
    n_cold = 5  # 跟 v0.74 mean_mastery_fallback 阈值一致
    off_cold_ece = compute_ece(off["calibrated_v3s"][:n_cold], off["actuals"][:n_cold])
    on_cold_ece = compute_ece(on["calibrated_v3s"][:n_cold], on["actuals"][:n_cold])
    off_noncold_ece = compute_ece(off["calibrated_v3s"][n_cold:], off["actuals"][n_cold:])
    on_noncold_ece = compute_ece(on["calibrated_v3s"][n_cold:], on["actuals"][n_cold:])

    # 5. source 分布
    from collections import Counter
    off_source_dist = dict(Counter(off["sources"]))
    on_source_dist = dict(Counter(on["sources"]))

    # 6. 报告
    _log.info("=" * 60)
    _log.info("结果对比")
    _log.info("=" * 60)
    _log.info("样本数: off=%d, on=%d (同 lbc003 response_history)", off["n_pairs"], on["n_pairs"])
    _log.info("")
    _log.info("📊 Raw V3 分布:")
    _log.info("  off: min=%.3f max=%.3f mean=%.3f std=%.3f",
              off["raw_v3s"].min(), off["raw_v3s"].max(),
              off["raw_v3s"].mean(), off["raw_v3s"].std())
    _log.info("  on:  min=%.3f max=%.3f mean=%.3f std=%.3f",
              on["raw_v3s"].min(), on["raw_v3s"].max(),
              on["raw_v3s"].mean(), on["raw_v3s"].std())
    _log.info("  std 差异: on - off = %.3f (期望 > 0, 因为 difficulty 加区分度)",
              on["raw_v3s"].std() - off["raw_v3s"].std())
    _log.info("")
    _log.info("📊 Calibrated V3 分布:")
    _log.info("  off: min=%.3f max=%.3f mean=%.3f std=%.3f",
              off["calibrated_v3s"].min(), off["calibrated_v3s"].max(),
              off["calibrated_v3s"].mean(), off["calibrated_v3s"].std())
    _log.info("  on:  min=%.3f max=%.3f mean=%.3f std=%.3f",
              on["calibrated_v3s"].min(), on["calibrated_v3s"].max(),
              on["calibrated_v3s"].mean(), on["calibrated_v3s"].std())
    _log.info("")
    _log.info("📊 ECE 对比:")
    _log.info("  raw V3 ECE:     off=%.4f  on=%.4f  (改善 %.4f)",
              off_raw_ece, on_raw_ece, off_raw_ece - on_raw_ece)
    _log.info("  calibrated V3:  off=%.4f  on=%.4f  (改善 %.4f) ⭐",
              off_cal_ece, on_cal_ece, off_cal_ece - on_cal_ece)
    _log.info("")
    _log.info("📊 冷启动期 ECE (前 5 轮):")
    _log.info("  off=%.4f  on=%.4f  (改善 %.4f)",
              off_cold_ece, on_cold_ece, off_cold_ece - on_cold_ece)
    _log.info("📊 非冷启动期 ECE (6+ 轮):")
    _log.info("  off=%.4f  on=%.4f  (改善 %.4f)",
              off_noncold_ece, on_noncold_ece, off_noncold_ece - on_noncold_ece)
    _log.info("")
    _log.info("📊 Bin [0.9, 1.0] gap (主要瓶颈):")
    if off_high:
        _log.info("  off: n=%d  conf=%.3f  acc=%.3f  gap=%.3f",
                  off_high["n"], off_high["conf"], off_high["acc"], off_high["gap"])
    if on_high:
        _log.info("  on:  n=%d  conf=%.3f  acc=%.3f  gap=%.3f",
                  on_high["n"], on_high["conf"], on_high["acc"], on_high["gap"])
    if off_high and on_high:
        _log.info("  bin gap 改善: %.3f", off_high["gap"] - on_high["gap"])
    _log.info("")
    _log.info("📊 Calibration source 分布:")
    _log.info("  off: %s", off_source_dist)
    _log.info("  on:  %s", on_source_dist)
    _log.info("=" * 60)

    # 7. 决策
    improvement = off_cal_ece - on_cal_ece
    if improvement > 0.05:
        decision = "✅ calibrated V3 ECE 改善 > 0.05, v0.75 P0-m 显著有效, 建议落地"
    elif improvement > 0:
        decision = f"⚠️ calibrated V3 ECE 改善 {improvement:.3f}, 边际改善, 跟 Bisen 讨论"
    else:
        decision = f"❌ calibrated V3 ECE 没改善 / 变差 ({improvement:+.3f}), v0.75 P0-m 无效"

    _log.info("决策: %s", decision)
    _log.info("=" * 60)

    # 8. 存结果
    output = {
        "off": {
            "n_pairs": off["n_pairs"],
            "raw_v3_stats": {
                "min": float(off["raw_v3s"].min()),
                "max": float(off["raw_v3s"].max()),
                "mean": float(off["raw_v3s"].mean()),
                "std": float(off["raw_v3s"].std()),
            },
            "calibrated_stats": {
                "min": float(off["calibrated_v3s"].min()),
                "max": float(off["calibrated_v3s"].max()),
                "mean": float(off["calibrated_v3s"].mean()),
                "std": float(off["calibrated_v3s"].std()),
            },
            "raw_ece": off_raw_ece,
            "cal_ece": off_cal_ece,
            "cold_ece": off_cold_ece,
            "noncold_ece": off_noncold_ece,
            "bins": off_bins,
            "source_dist": off_source_dist,
        },
        "on": {
            "n_pairs": on["n_pairs"],
            "raw_v3_stats": {
                "min": float(on["raw_v3s"].min()),
                "max": float(on["raw_v3s"].max()),
                "mean": float(on["raw_v3s"].mean()),
                "std": float(on["raw_v3s"].std()),
            },
            "calibrated_stats": {
                "min": float(on["calibrated_v3s"].min()),
                "max": float(on["calibrated_v3s"].max()),
                "mean": float(on["calibrated_v3s"].mean()),
                "std": float(on["calibrated_v3s"].std()),
            },
            "raw_ece": on_raw_ece,
            "cal_ece": on_cal_ece,
            "cold_ece": on_cold_ece,
            "noncold_ece": on_noncold_ece,
            "bins": on_bins,
            "source_dist": on_source_dist,
        },
        "improvement_cal_ece": improvement,
        "decision": decision,
    }
    output_path = "discussions/2026-08-04-v075-P0-m-difficulty-replay.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    _log.info("结果保存到 %s", output_path)


if __name__ == "__main__":
    main()
