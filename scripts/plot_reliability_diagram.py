"""v0.71.0+ P0-h: V3 reliability diagram 诊断脚本.

目的:
  - 重放 lbc003 56 道题 (P0-g 修复后)
  - 收集 (V3 confidence, actual_outcome) 配对
  - 按 10 bins 分组 ([0, 0.1], [0.1, 0.2], ..., [0.9, 1.0])
  - 画 reliability diagram + 直方图
  - 输出 per-bin 平均 confidence + 平均 accuracy + 样本数

判断:
  - 如果 V3 全局偏低 (大部分 bin 在对角线下方) -> 换指标方向明确
  - 如果 V3 只在低 confidence 区偏差大 -> 可能小修就能改善
  - 如果 V3 高 confidence 区也偏差 -> 模型本身不可信
"""

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
matplotlib.use('Agg')  # 非交互式后端
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
    """重放 lbc003, 收集 (V3 confidence, actual_outcome) 配对.

    配对规则:
      - V3 是 calibrated.metadata["dual_agent_confidence"] (当前轮 N+1 预测)
      - actual_outcome 是 prev.actual_outcome (上一轮 N 的实际结果)
      - 校准逻辑: V3(round=N+1) 应该预测 round=N+1 的 outcome,
        但 actual_outcome(round=N+1) 要等 round=N+2 才填回 (Step 0)
      - 所以配对: (V3 of round N+1, actual_outcome of round N+1)
        = (V3 of round N+1, actual_outcome of round N+1 from NEXT round's prev)
    """
    rh = load_lbc003_response_history()
    orch = DualAgentOrchestrator(config=DualAgentConfig(), llm_client=None)
    sid = 'lbc003_reliability_diag'

    # 先跑所有 56 道
    for h in rh:
        obs = Observation(
            problem_id=h['problem_id'], skill_id='variables',
            correct=bool(h.get('correct', 0)), score=float(h.get('score', 0.0)),
            bloom_level=bloom_str_to_enum(h.get('bloom_level', 'APPLY')),
            response_time_sec=0.0,
        )
        orch.process_observation(obs, student_id=sid)

    # 收集配对
    # hist[i] 的 V3 配 hist[i].actual_outcome (但 actual_outcome 在 hist[i+1] 的 Step 0 才填)
    hist = orch.intervention_history[sid]
    pairs = []  # (v3_confidence, actual_outcome, source, round)
    for i in range(len(hist)):
        v3 = hist[i].metadata.get('dual_agent_confidence')
        v3_src = hist[i].metadata.get('dual_agent_confidence_source', 'unknown')
        # actual_outcome 在 hist[i+1] 的 Step 0 填回 (基于下一轮 observation)
        if i + 1 < len(hist):
            # hist[i+1] 是下一轮, 它的 Step 0 会把 hist[i].actual_outcome 填上
            # 但 process_observation 跑完后, hist[i].actual_outcome 已被填
            actual = hist[i].actual_outcome
        else:
            actual = hist[i].actual_outcome  # 最后一条可能 None

        if v3 is not None and actual is not None:
            pairs.append((v3, actual, v3_src, hist[i].calibration_round))

    return pairs


def compute_reliability_bins(pairs, n_bins=10):
    """按 V3 confidence 分 10 bins, 算每 bin 平均 confidence + accuracy + 样本数.

    Args:
        pairs: List of (v3_confidence, actual_outcome, source, round)
        n_bins: 默认 10

    Returns:
        bins: List of dict, 每个 bin 含:
          - bin_low, bin_high: bin 边界
          - mean_confidence: 该 bin 内 V3 平均
          - mean_accuracy: 该 bin 内 actual_outcome 平均
          - n_samples: 样本数
          - gap: mean_confidence - mean_accuracy (负 = 低估, 正 = 高估)
    """
    confs = np.array([p[0] for p in pairs])
    accs = np.array([p[1] for p in pairs])

    bin_edges = np.linspace(0, 1, n_bins + 1)
    bins = []
    for i in range(n_bins):
        low, high = bin_edges[i], bin_edges[i + 1]
        mask = (confs >= low) & (confs < high)
        # 最后一个 bin 包含 1.0
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
            'gap': float(mc - ma),  # 负 = 低估, 正 = 高估
        })
    return bins


def plot_reliability_diagram(bins, save_path):
    """画 reliability diagram + 直方图."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), gridspec_kw={'width_ratios': [2, 1]})

    # 左图: reliability diagram
    bin_centers = [(b['bin_low'] + b['bin_high']) / 2 for b in bins]
    mean_confs = [b['mean_confidence'] for b in bins]
    mean_accs = [b['mean_accuracy'] for b in bins]
    n_samples = [b['n_samples'] for b in bins]

    # 对角线 (perfect calibration)
    ax1.plot([0, 1], [0, 1], 'k--', alpha=0.5, label='Perfect calibration')

    # 只画有样本的 bin
    has_samples = [i for i, n in enumerate(n_samples) if n > 0]
    if has_samples:
        ax1.plot(
            [bin_centers[i] for i in has_samples],
            [mean_accs[i] for i in has_samples],
            'bo-', markersize=10, label='V3 (LinUCB θ@x)',
        )

    ax1.set_xlabel('Mean V3 Confidence')
    ax1.set_ylabel('Mean Actual Outcome (Accuracy)')
    ax1.set_title('Reliability Diagram (V3 vs Actual)')
    ax1.set_xlim(-0.05, 1.05)
    ax1.set_ylim(-0.05, 1.05)
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # 标注每个 bin 的样本数
    for i in has_samples:
        ax1.annotate(
            f'n={n_samples[i]}',
            (bin_centers[i], mean_accs[i]),
            textcoords="offset points",
            xytext=(0, 12),
            ha='center',
            fontsize=9,
        )

    # 右图: V3 confidence 分布直方图
    ax2.bar(
        bin_centers,
        n_samples,
        width=0.08,
        alpha=0.7,
        color='steelblue',
        edgecolor='black',
    )
    ax2.set_xlabel('V3 Confidence Bin')
    ax2.set_ylabel('Sample Count')
    ax2.set_title('V3 Confidence Distribution')
    ax2.set_xlim(-0.05, 1.05)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=120, bbox_inches='tight')
    print(f'✅ 图已保存: {save_path}')


def main():
    print('=== 收集 (V3, actual_outcome) 配对 ===')
    pairs = collect_v3_pairs()
    print(f'有效配对数: {len(pairs)}')

    # 分 source 统计
    src_counter = {}
    for _, _, src, _ in pairs:
        src_counter[src] = src_counter.get(src, 0) + 1
    print(f'source 分布: {src_counter}')

    print()
    print('=== 按 10 bins 分组 ===')
    bins = compute_reliability_bins(pairs, n_bins=10)
    print(f'{"bin":<12} {"mean_conf":<12} {"mean_acc":<12} {"gap":<10} {"n":<5}')
    for b in bins:
        print(
            f'[{b["bin_low"]:.1f},{b["bin_high"]:.1f}]'
            f'  {b["mean_confidence"]:.4f}      '
            f'  {b["mean_accuracy"]:.4f}      '
            f'  {b["gap"]:+.4f}    '
            f'  {b["n_samples"]}'
        )

    # 全局统计
    confs = np.array([p[0] for p in pairs])
    accs = np.array([p[1] for p in pairs])
    ece_per_sample = np.mean(np.abs(confs - accs))
    print()
    print('=== 全局统计 ===')
    print(f'平均 V3 confidence: {confs.mean():.4f}')
    print(f'平均 actual_outcome: {accs.mean():.4f}')
    print(f'全局偏差 (acc - conf): {accs.mean() - confs.mean():.4f}')
    print(f'ECE (per-sample |conf-acc| 平均): {ece_per_sample:.4f}')

    # 判断: V3 全局偏低还是局部偏低
    print()
    print('=== 诊断判断 ===')
    bins_with_samples = [b for b in bins if b['n_samples'] > 0]
    underestimated = [b for b in bins_with_samples if b['gap'] < -0.1]  # V3 < acc 超过 0.1
    overestimated = [b for b in bins_with_samples if b['gap'] > 0.1]
    calibrated = [b for b in bins_with_samples if abs(b['gap']) <= 0.1]

    print(f'有样本的 bin 数: {len(bins_with_samples)}')
    print(f'低估 bin (V3 < acc, gap < -0.1): {len(underestimated)}')
    print(f'高估 bin (V3 > acc, gap > 0.1): {len(overestimated)}')
    print(f'校准 bin (|gap| <= 0.1): {len(calibrated)}')

    if underestimated and not overestimated:
        print('=> V3 全局低估 (LinUCB θ@x 预测永远偏低)')
        print('   方向: 换 confidence 指标 (选项 2)')
    elif overestimated and not underestimated:
        print('=> V3 全局高估')
    elif underestimated and overestimated:
        print('=> V3 局部偏差 (低 confidence 区低估, 高 confidence 区高估或反之)')
        print('   方向: 小修可能改善 (如分 bin 校准)')

    # 画图
    save_path = 'discussions/2026-08-03-v0710-reliability-diagram.png'
    plot_reliability_diagram(bins, save_path)


if __name__ == '__main__':
    main()
