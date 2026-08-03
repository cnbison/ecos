"""v0.72.0 P0-i: V3 reliability diagram 诊断脚本 (raw + calibrated 对比)."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root))

import logging
logging.basicConfig(level=logging.WARNING, format='%(name)s %(levelname)s %(message)s')

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from ecos.dual_agent.orchestrator import DualAgentConfig, DualAgentOrchestrator
from ecos.cta.belief_engine import Observation
from ecos.cta.belief_state import BloomLevel


def load_lbc003_response_history():
    conn = sqlite3.connect('web/ecos.db')
    row = conn.execute("SELECT response_history FROM students WHERE student_id='lbc003'").fetchone()
    return json.loads(row[0]) if row and row[0] else []


def bloom_str_to_enum(bloom_str: str) -> BloomLevel:
    mapping = {
        'REMEMBER': BloomLevel.REMEMBER,
        'UNDERSTAND': BloomLevel.UNDERSTAND,
        'APPLY': BloomLevel.APPLY,
        'ANALYZE': BloomLevel.ANALYZE,
        'EVALUATE': BloomLevel.EVALUATE,
        'CREATE': BloomLevel.CREATE,
    }
    return mapping.get(bloom_str, BloomLevel.APPLY)


def collect_v3_pairs():
    rh = load_lbc003_response_history()
    orch = DualAgentOrchestrator(config=DualAgentConfig(), llm_client=None)
    sid = 'lbc003_reliability_diag_v0720'

    for h in rh:
        obs = Observation(
            problem_id=h['problem_id'], skill_id='variables',
            correct=bool(h.get('correct', 0)), score=float(h.get('score', 0.0)),
            bloom_level=bloom_str_to_enum(h.get('bloom_level', 'APPLY')),
            response_time_sec=0.0,
        )
        orch.process_observation(obs, student_id=sid)

    hist = orch.intervention_history[sid]
    raw_pairs = []
    calibrated_pairs = []
    for i in range(len(hist)):
        raw = hist[i].metadata.get('dual_agent_confidence')
        calibrated = hist[i].metadata.get('dual_agent_confidence_calibrated')
        calibrated_source = hist[i].metadata.get('dual_agent_confidence_calibrated_source', 'unknown')
        actual = hist[i].actual_outcome

        if raw is not None and actual is not None:
            raw_pairs.append((raw, actual, 'raw', hist[i].calibration_round))
        if calibrated is not None and actual is not None:
            calibrated_pairs.append((calibrated, actual, calibrated_source, hist[i].calibration_round))

    return raw_pairs, calibrated_pairs


def compute_reliability_bins(pairs, n_bins=10):
    confs = np.array([p[0] for p in pairs])
    accs = np.array([p[1] for p in pairs])

    bin_edges = np.linspace(0, 1, n_bins + 1)
    bins = []
    for i in range(n_bins):
        low, high = bin_edges[i], bin_edges[i + 1]
        mask = (confs >= low) & (confs < high)
        if i == n_bins - 1:
            mask = (confs >= low) & (confs <= high)
        n = int(mask.sum())
        if n > 0:
            mc = float(confs[mask].mean())
            ma = float(accs[mask].mean())
        else:
            mc, ma = 0.0, 0.0
        bins.append({
            'bin_low': float(low),
            'bin_high': float(high),
            'mean_confidence': mc,
            'mean_accuracy': ma,
            'n_samples': n,
            'gap': float(mc - ma),
        })
    return bins


def plot_reliability_diagram(raw_bins, calibrated_bins, save_path):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), gridspec_kw={'width_ratios': [2, 1]})

    bin_centers = [(b['bin_low'] + b['bin_high']) / 2 for b in raw_bins]

    ax1.plot([0, 1], [0, 1], 'k--', alpha=0.5, label='Perfect calibration')

    raw_accs = [b['mean_accuracy'] for b in raw_bins]
    raw_n = [b['n_samples'] for b in raw_bins]
    raw_has = [i for i, n in enumerate(raw_n) if n > 0]
    if raw_has:
        ax1.plot(
            [bin_centers[i] for i in raw_has],
            [raw_accs[i] for i in raw_has],
            'bo-', markersize=10, label='Raw V3 (LinUCB theta@x)',
        )

    cal_accs = [b['mean_accuracy'] for b in calibrated_bins]
    cal_n = [b['n_samples'] for b in calibrated_bins]
    cal_has = [i for i, n in enumerate(cal_n) if n > 0]
    if cal_has:
        ax1.plot(
            [bin_centers[i] for i in cal_has],
            [cal_accs[i] for i in cal_has],
            'rs-', markersize=10, label='Calibrated V3 (Platt Scaling)',
        )

    ax1.set_xlabel('Mean V3 Confidence')
    ax1.set_ylabel('Mean Actual Outcome (Accuracy)')
    ax1.set_title('Reliability Diagram (v0.72.0: raw vs calibrated)')
    ax1.set_xlim(-0.05, 1.05)
    ax1.set_ylim(-0.05, 1.05)
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    for i in cal_has:
        ax1.annotate(
            f'n={cal_n[i]}',
            (bin_centers[i], cal_accs[i]),
            textcoords="offset points",
            xytext=(0, -15),
            ha='center',
            fontsize=8,
            color='red',
        )

    ax2.bar(
        bin_centers,
        cal_n,
        width=0.08,
        alpha=0.7,
        color='red',
        edgecolor='black',
    )
    ax2.set_xlabel('Calibrated V3 Confidence Bin')
    ax2.set_ylabel('Sample Count')
    ax2.set_title('Calibrated V3 Distribution')
    ax2.set_xlim(-0.05, 1.05)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=120, bbox_inches='tight')
    print(f'图已保存: {save_path}')


def main():
    print('=== 收集 (V3 raw, V3 calibrated, actual_outcome) 配对 ===')
    raw_pairs, calibrated_pairs = collect_v3_pairs()
    print(f'Raw V3 配对数: {len(raw_pairs)}')
    print(f'Calibrated V3 配对数: {len(calibrated_pairs)}')

    raw_src = {}
    for _, _, src, _ in raw_pairs:
        raw_src[src] = raw_src.get(src, 0) + 1
    print(f'Raw V3 source 分布: {raw_src}')

    cal_src = {}
    for _, _, src, _ in calibrated_pairs:
        cal_src[src] = cal_src.get(src, 0) + 1
    print(f'Calibrated V3 source 分布: {cal_src}')

    print()
    print('=== Calibrated V3 按 10 bins 分组 ===')
    cal_bins = compute_reliability_bins(calibrated_pairs, n_bins=10)
    print(f'{"bin":<12} {"mean_conf":<12} {"mean_acc":<12} {"gap":<10} {"n":<5}')
    for b in cal_bins:
        print(
            f'[{b["bin_low"]:.1f},{b["bin_high"]:.1f}]'
            f'  {b["mean_confidence"]:.4f}      '
            f'  {b["mean_accuracy"]:.4f}      '
            f'  {b["gap"]:+.4f}    '
            f'  {b["n_samples"]}'
        )

    def stats(pairs, label):
        confs = np.array([p[0] for p in pairs])
        accs = np.array([p[1] for p in pairs])
        ece = float(np.mean(np.abs(confs - accs)))
        gap = float(accs.mean() - confs.mean())
        print(f'  {label}: conf={confs.mean():.4f}, acc={accs.mean():.4f}, gap={gap:+.4f}, ECE={ece:.4f}')
        return ece

    print()
    print('=== 全局统计对比 ===')
    raw_ece = stats(raw_pairs, 'Raw V3     ')
    cal_ece = stats(calibrated_pairs, 'Calibrated V3')
    print(f'  ECE 改善: {raw_ece - cal_ece:.4f} ({(raw_ece - cal_ece) / raw_ece * 100:.1f}%)')

    print()
    print('=== 参考: 单 Agent baseline (CTA mastery_prob) ECE = 0.1740 (56 样本) ===')
    print(f'  H3 阈值: 双 Agent ECE <= 0.10')
    print(f'  Raw V3 ECE: {raw_ece:.4f} ({"PASS" if raw_ece <= 0.10 else "FAIL"})')
    print(f'  Calibrated V3 ECE: {cal_ece:.4f} ({"PASS" if cal_ece <= 0.10 else "FAIL"})')

    print()
    print('=== 诊断判断 ===')
    if cal_ece < raw_ece - 0.1:
        print(f'=> Platt Scaling 显著改善 (ECE {raw_ece:.4f} -> {cal_ece:.4f}, 改善 {raw_ece - cal_ece:.4f})')
    elif cal_ece < raw_ece:
        print(f'=> Platt Scaling 略有改善 (ECE {raw_ece:.4f} -> {cal_ece:.4f}, 改善 {raw_ece - cal_ece:.4f})')
    else:
        print(f'=> Platt Scaling 无改善或反向 (raw {raw_ece:.4f} vs cal {cal_ece:.4f})')

    if cal_ece <= 0.10:
        print(f'=> H3 通过 (calibrated ECE {cal_ece:.4f} <= 0.10)')
    elif cal_ece < 0.30:
        print(f'=> H3 未通过, 但显著改善 ({cal_ece:.4f} < 0.30, 单 Agent baseline = 0.17)')
    else:
        print(f'=> H3 仍未通过 ({cal_ece:.4f} > 0.30, 模型本身不可信, 需重新设计)')

    raw_bins = compute_reliability_bins(raw_pairs, n_bins=10)
    save_path = 'discussions/2026-08-03-v0720-reliability-diagram-raw-vs-calibrated.png'
    plot_reliability_diagram(raw_bins, cal_bins, save_path)


if __name__ == '__main__':
    main()
