"""v0.75 P0-h Plan B D2: 5D reliability diagram 形态对比.

目的:
  Plan B D2 提议: 改用 reliability diagram 形态评估, 不用单 ECE 数字.
  5D 各画一张 (K/P/S/C/X), 对比 单 Agent baseline (CTA mastery_prob) vs
  双 Agent calibrated V3, 看哪种形态更接近 y=x 对角线.

输入:
  - 单 Agent: lbc003 response_history[i].mastery_prob_after[dim]
  - 双 Agent: calibrated V3 (production path: cold start fallback + Platt + Isotonic)

输出:
  - discussions/2026-08-04-v075-D2-reliability-diagram-5d.png (5D 形态对比)
  - discussions/2026-08-04-v075-D2-reliability-diagram-5d.json (per-dim 数据)

用法:
  python scripts/plot_reliability_diagram_5d.py
"""

from __future__ import annotations

import json
import logging
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import numpy as np

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root))

import matplotlib
matplotlib.use('Agg')  # 非交互式后端
import matplotlib.pyplot as plt

from ecos.cta.belief_engine import Observation
from ecos.cta.belief_state import BloomLevel
from ecos.dual_agent.orchestrator import DualAgentConfig, DualAgentOrchestrator

logging.basicConfig(level=logging.WARNING, format='%(name)s %(levelname)s %(message)s')

DIMENSIONS = ['remember', 'understand', 'apply', 'analyze', 'evaluate', 'create']


def load_lbc003_response_history():
    conn = sqlite3.connect('web/ecos.db')
    row = conn.execute("SELECT response_history FROM students WHERE student_id='lbc003'").fetchone()
    return json.loads(row[0]) if row and row[0] else []


def bloom_str_to_enum(bloom_str: str) -> BloomLevel:
    mapping = {
        'REMEMBER': BloomLevel.REMEMBER, 'UNDERSTAND': BloomLevel.UNDERSTAND,
        'APPLY': BloomLevel.APPLY, 'ANALYZE': BloomLevel.ANALYZE,
        'EVALUATE': BloomLevel.EVALUATE, 'CREATE': BloomLevel.CREATE,
    }
    return mapping.get(bloom_str, BloomLevel.APPLY)


def collect_pairs():
    """重放 lbc003, 收集 (单 Agent 5D mastery_prob_after, 双 Agent calibrated V3, actual) 三元组.

    Returns:
        list of (single_5d: dict, calibrated_v3: float, actual: float, source: str) tuples
    """
    rh = load_lbc003_response_history()
    orch = DualAgentOrchestrator(config=DualAgentConfig(), llm_client=None)
    sid = 'lbc003_d2_reliability'

    # 跑全部 56 道
    for h in rh:
        obs = Observation(
            problem_id=h['problem_id'], skill_id='variables',
            correct=bool(h.get('correct', 0)), score=float(h.get('score', 0.0)),
            bloom_level=bloom_str_to_enum(h.get('bloom_level', 'APPLY')),
            response_time_sec=0.0,
        )
        orch.process_observation(obs, student_id=sid)

    # 收集三元组: 单 Agent 5D + 双 Agent V3 + actual
    # 单 Agent confidence: orchestrator.state[sid] 的 5D mastery_prob (在 process_observation 跑完后, 已是 update 后状态)
    # 双 Agent confidence: calibrated V3 (calibrated.metadata["dual_agent_confidence_calibrated"])
    # actual: hist[i].actual_outcome
    triples = []
    for i, cal in enumerate(orch.intervention_history[sid]):
        actual = cal.actual_outcome
        cal_v3 = cal.metadata.get('dual_agent_confidence_calibrated')
        source = cal.metadata.get('dual_agent_confidence_calibrated_source', 'unknown')
        # 单 Agent 6 Bloom confidence: orchestrator 内部的 belief_state (orch.state[sid])
        if sid in orch.state:
            s = orch.state[sid]
            single_5d = {
                'remember': float(s.bloom_profile.remember),
                'understand': float(s.bloom_profile.understand),
                'apply': float(s.bloom_profile.apply),
                'analyze': float(s.bloom_profile.analyze),
                'evaluate': float(s.bloom_profile.evaluate),
                'create': float(s.bloom_profile.create),
            }
        else:
            single_5d = None
        if actual is not None and cal_v3 is not None and single_5d is not None:
            triples.append({
                'single_5d': single_5d,
                'cal_v3': float(cal_v3),
                'actual': float(actual),
                'source': source,
                'round': cal.calibration_round,
            })
    return triples


def compute_reliability_bins(confidences, accuracies, n_bins=10):
    """算 reliability diagram bin 数据."""
    confs = np.array(confidences)
    accs = np.array(accuracies)
    bin_edges = np.linspace(0, 1, n_bins + 1)
    bins = []
    for i in range(n_bins):
        low, high = bin_edges[i], bin_edges[i + 1]
        if i == n_bins - 1:
            mask = (confs >= low) & (confs <= high)
        else:
            mask = (confs >= low) & (confs < high)
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


def compute_ece(confidences, accuracies, n_bins=10):
    """算 ECE (per-sample weighted)."""
    confs = np.array(confidences)
    accs = np.array(accuracies)
    bin_edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n = len(confs)
    for i in range(n_bins):
        low, high = bin_edges[i], bin_edges[i + 1]
        if i == n_bins - 1:
            mask = (confs >= low) & (confs <= high)
        else:
            mask = (confs >= low) & (confs < high)
        if mask.sum() == 0:
            continue
        bin_conf = confs[mask].mean()
        bin_acc = accs[mask].mean()
        ece += (mask.sum() / n) * abs(bin_conf - bin_acc)
    return float(ece)


def compute_diagonal_proximity(bins):
    """D2 关键指标: bin 点到 y=x 对角线的均方根距离 (RMS).

    数值越小 = 形态越接近 perfect calibration.
    比 ECE 更关注"形态对不对", 不只"平均差多少".
    """
    distances = []
    weights = []
    for b in bins:
        if b['n_samples'] == 0:
            continue
        # 距离 = sqrt((conf - acc)^2) = |gap|
        dist = abs(b['mean_confidence'] - b['mean_accuracy'])
        distances.append(dist)
        weights.append(b['n_samples'])
    if not distances:
        return None
    distances = np.array(distances)
    weights = np.array(weights, dtype=float)
    weights /= weights.sum()
    return float(np.sqrt((weights * distances ** 2).sum()))


def plot_5d_reliability(triples, save_path):
    """画 5D reliability diagram 对比: 单 Agent (mastery_prob_after) vs 双 Agent (calibrated V3)."""
    n_dims = len(DIMENSIONS)
    fig, axes = plt.subplots(2, n_dims, figsize=(4 * n_dims, 8), sharex=True, sharey=True)
    fig.suptitle('lbc003 Reliability Diagrams: 单 Agent (CTA mastery_prob_after) vs 双 Agent (Calibrated V3)',
                 fontsize=14, fontweight='bold')

    summary = {}

    for col, dim in enumerate(DIMENSIONS):
        # 提取单/双 Agent confidence 跟 actual
        single_confs = [t['single_5d'].get(dim, 0.5) for t in triples]
        dual_confs = [t['cal_v3'] for t in triples]
        actuals = [t['actual'] for t in triples]

        # 算 bins + ECE + RMS
        single_bins = compute_reliability_bins(single_confs, actuals)
        dual_bins = compute_reliability_bins(dual_confs, actuals)
        single_ece = compute_ece(single_confs, actuals)
        dual_ece = compute_ece(dual_confs, actuals)
        single_rms = compute_diagonal_proximity(single_bins)
        dual_rms = compute_diagonal_proximity(dual_bins)

        summary[dim] = {
            'n_samples': len(triples),
            'single_ece': single_ece,
            'dual_ece': dual_ece,
            'single_rms': single_rms,
            'dual_rms': dual_rms,
            'single_bins': single_bins,
            'dual_bins': dual_bins,
        }

        # 上图: 单 Agent
        ax_top = axes[0, col]
        bin_centers = [(b['bin_low'] + b['bin_high']) / 2 for b in single_bins]
        has_samples = [i for i, b in enumerate(single_bins) if b['n_samples'] > 0]
        ax_top.plot([0, 1], [0, 1], 'k--', alpha=0.5, label='Perfect')
        if has_samples:
            ax_top.plot(
                [bin_centers[i] for i in has_samples],
                [single_bins[i]['mean_accuracy'] for i in has_samples],
                'ro-', markersize=8, label=f'Single (ECE={single_ece:.3f})',
            )
        ax_top.set_title(f'{dim} - 单 Agent')
        ax_top.set_xlim(-0.05, 1.05)
        ax_top.set_ylim(-0.05, 1.05)
        ax_top.grid(True, alpha=0.3)
        ax_top.legend(fontsize=8)

        # 下图: 双 Agent
        ax_bot = axes[1, col]
        has_samples = [i for i, b in enumerate(dual_bins) if b['n_samples'] > 0]
        ax_bot.plot([0, 1], [0, 1], 'k--', alpha=0.5, label='Perfect')
        if has_samples:
            ax_bot.plot(
                [bin_centers[i] for i in has_samples],
                [dual_bins[i]['mean_accuracy'] for i in has_samples],
                'bo-', markersize=8, label=f'Dual (ECE={dual_ece:.3f})',
            )
        ax_bot.set_title(f'{dim} - 双 Agent')
        ax_bot.set_xlabel('Mean Confidence')
        ax_bot.set_xlim(-0.05, 1.05)
        ax_bot.set_ylim(-0.05, 1.05)
        ax_bot.grid(True, alpha=0.3)
        ax_bot.legend(fontsize=8)

    axes[0, 0].set_ylabel('Mean Accuracy')
    axes[1, 0].set_ylabel('Mean Accuracy')

    plt.tight_layout()
    plt.savefig(save_path, dpi=120, bbox_inches='tight')
    print(f'✅ 图已保存: {save_path}')

    return summary


def main():
    print('=== D2: 5D reliability diagram 形态评估 ===\n')
    print('▶ 重放 lbc003, 收集 (单 Agent 5D, 双 Agent V3, actual) 三元组...')
    triples = collect_pairs()
    print(f'  有效三元组数: {len(triples)}')

    source_dist = Counter([t['source'] for t in triples])
    print(f'  source 分布: {dict(source_dist)}\n')

    # 画图 + 算指标
    save_path = 'discussions/2026-08-04-v075-D2-reliability-diagram-5d.png'
    summary = plot_5d_reliability(triples, save_path)

    # 打印 ECE + RMS 对比表
    print('\n=== 5D 指标对比 ===')
    print(f'{"Dim":<4} {"Single ECE":<12} {"Dual ECE":<12} {"Single RMS":<12} {"Dual RMS":<12} {"Winner"}')
    print('-' * 70)
    for dim in DIMENSIONS:
        s = summary[dim]
        winner = 'Single' if s['single_rms'] < s['dual_rms'] else 'Dual'
        if abs(s['single_rms'] - s['dual_rms']) < 0.01:
            winner = 'Tie'
        print(
            f'{dim:<4} {s["single_ece"]:<12.4f} {s["dual_ece"]:<12.4f} '
            f'{s["single_rms"]:<12.4f} {s["dual_rms"]:<12.4f} {winner}'
        )

    # 全局平均
    avg_single_ece = np.mean([summary[d]['single_ece'] for d in DIMENSIONS])
    avg_dual_ece = np.mean([summary[d]['dual_ece'] for d in DIMENSIONS])
    avg_single_rms = np.mean([summary[d]['single_rms'] for d in DIMENSIONS])
    avg_dual_rms = np.mean([summary[d]['dual_rms'] for d in DIMENSIONS])
    print('-' * 70)
    print(f'{"Avg":<4} {avg_single_ece:<12.4f} {avg_dual_ece:<12.4f} '
          f'{avg_single_rms:<12.4f} {avg_dual_rms:<12.4f}')

    # 保存 JSON
    output = {
        'n_samples': len(triples),
        'source_dist': dict(source_dist),
        'per_dim': summary,
        'avg_single_ece': avg_single_ece,
        'avg_dual_ece': avg_dual_ece,
        'avg_single_rms': avg_single_rms,
        'avg_dual_rms': avg_dual_rms,
    }
    # 序列化 (numpy → python float)
    def convert(o):
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, (np.integer, np.floating)):
            return float(o)
        if isinstance(o, dict):
            return {k: convert(v) for k, v in o.items()}
        if isinstance(o, list):
            return [convert(v) for v in o]
        return o
    output = convert(output)

    json_path = 'discussions/2026-08-04-v075-D2-reliability-diagram-5d.json'
    with open(json_path, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f'\n✅ JSON 已保存: {json_path}')


if __name__ == '__main__':
    main()
