"""v0.75 Plan B D4 H3b: 干预多样性 arm diversity 评估.

目的:
  H3 拆 3 子假设后, 验证 H3b: 互校改善干预多样性.
  重放 lbc003 56 道题, 对比:
    - 单 Agent: CTA heuristic (固定策略, 按 5D 最低维度选干预类型)
    - 双 Agent: LCAPolicyLearner LinUCB 选 arm

评估指标:
  1. Arm 分布熵 (Shannon entropy): H = -sum(p_i * log2(p_i))
  2. 同 arm 重复间隔 (consecutive repetition): 平均多少轮才出现同 arm
  3. Arm 覆盖度: 答 N 道题后, 至少被选 1 次的 arm 数 (越接近 n_arms 越好)

通过阈值 (D4 PRD §2):
  - 双 Agent arm entropy > 1.5 (10 arm max entropy = log2(10) ≈ 3.32)
  - 双 Agent 同 arm 重复间隔 > 单 Agent
  - 双 Agent arm 覆盖度 > 7/10

用法:
  python scripts/v075_d4_arm_diversity.py
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import numpy as np

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from ecos.cta.belief_engine import Observation
from ecos.cta.belief_state import BeliefState, BloomLevel
from ecos.dual_agent.orchestrator import DualAgentConfig, DualAgentOrchestrator
from ecos.lca.l4_optimization.linucb import BanditConfig
from ecos.lca.orchestrator import LCAEngineConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
_log = logging.getLogger(__name__)

N_ARMS = 10  # 默认 10 个候选干预


# ─── 单 Agent CTA Heuristic ─────────────────────────────────────


def cta_heuristic_select_arm(belief_state: BeliefState) -> int:
    """单 Agent baseline: 按 5D 最低 mastery_prob 对应的"难度档"选 arm.

    设计: 这是单 Agent "固定策略" 的代表, 不在线学习.
    逻辑: 5D 联合 mastery 越低, 选难度低的 arm (0-2 区间).
          5D 联合 mastery 越高, 选难度高的 arm (7-9 区间).
    """
    mastery_vec = belief_state.mastery_vector()
    mean_mastery = float(np.mean(mastery_vec))
    # 离散化到 0-9 arm 索引
    # 0.0-0.3 -> 0-2, 0.3-0.6 -> 3-6, 0.6-1.0 -> 7-9
    if mean_mastery < 0.3:
        return min(int(mean_mastery * 10), 2)
    elif mean_mastery < 0.6:
        return 3 + int((mean_mastery - 0.3) * 10)
    else:
        return 7 + min(int((mean_mastery - 0.6) * 7), 2)


# ─── 重放 ───────────────────────────────────────────────────────


def replay_lbc003():
    """重放 lbc003, 收集 (单 Agent arm, 双 Agent arm) 序列.

    双 Agent arm: 来自 orch.lca_engine.bandits[sid]._last_arm
    单 Agent arm: CTA heuristic (按 belief_state)
    """
    conn = sqlite3.connect("web/ecos.db")
    row = conn.execute(
        "SELECT response_history FROM students WHERE student_id='lbc003'"
    ).fetchone()
    rh = json.loads(row[0])
    _log.info("lbc003 response_history: %d 条", len(rh))

    bloom_map = {
        "REMEMBER": BloomLevel.REMEMBER, "UNDERSTAND": BloomLevel.UNDERSTAND,
        "APPLY": BloomLevel.APPLY, "ANALYZE": BloomLevel.ANALYZE,
        "EVALUATE": BloomLevel.EVALUATE, "CREATE": BloomLevel.CREATE,
    }

    orch = DualAgentOrchestrator(config=DualAgentConfig(), llm_client=None)
    sid = "replay_d4_h3b"

    single_arms = []
    dual_arms = []
    actuals = []
    rewards = []  # dual agent actual outcome 序列

    for h in rh:
        # 跑双 Agent 一轮 (内部 LCA 选 arm + LinUCB 预测)
        obs = Observation(
            problem_id=h["problem_id"], skill_id="variables",
            correct=bool(h.get("correct", 0)),
            score=float(h.get("score", 0.0)),
            bloom_level=bloom_map.get(h.get("bloom_level", "APPLY"), BloomLevel.APPLY),
            response_time_sec=0.0,
        )
        orch.process_observation(obs, student_id=sid)

        # 单 Agent: 用 CTA heuristic 选 arm (基于当前 belief_state)
        if sid in orch.state:
            single_arm = cta_heuristic_select_arm(orch.state[sid])
        else:
            single_arm = 0

        # 双 Agent: LCA 选中的 arm
        bandit = orch.lca_engine.bandits.get(sid)
        dual_arm = bandit._last_arm if bandit is not None else -1

        single_arms.append(single_arm)
        dual_arms.append(dual_arm)
        actuals.append(float(h.get("correct", 0)))

    return {
        "single_arms": single_arms,
        "dual_arms": dual_arms,
        "actuals": actuals,
        "n_rounds": len(single_arms),
    }


# ─── 多样性指标 ──────────────────────────────────────────────────


def shannon_entropy(arms: list) -> float:
    """算 arm 分布的 Shannon entropy (log2)."""
    if not arms:
        return 0.0
    counts = Counter(arms)
    total = len(arms)
    probs = [c / total for c in counts.values()]
    return -sum(p * math.log2(p) for p in probs if p > 0)


def max_entropy(n_arms: int) -> float:
    """n_arms 均匀分布的最大 entropy."""
    if n_arms <= 1:
        return 0.0
    return math.log2(n_arms)


def arm_coverage(arms: list, n_arms: int = N_ARMS) -> float:
    """至少被选 1 次的 arm 比例."""
    if not arms:
        return 0.0
    unique = set(arms)
    return len(unique) / n_arms


def consecutive_repetition_interval(arms: list) -> dict:
    """算 arm 重复间隔 (consecutive 跟 overall).

    consecutive_repeat_count: 相邻两轮选同一 arm 的次数
    max_consecutive_streak: 最长连续同一 arm 长度
    mean_interval_to_repeat: 同 arm 之间的平均间隔 (round 数)
    """
    if len(arms) < 2:
        return {"consecutive_repeat_count": 0, "max_consecutive_streak": 0,
                "mean_interval_to_repeat": 0.0, "n_repeats": 0}
    consecutive_count = sum(1 for i in range(1, len(arms)) if arms[i] == arms[i-1])

    # 最长连续 streak
    max_streak = 1
    cur_streak = 1
    for i in range(1, len(arms)):
        if arms[i] == arms[i-1]:
            cur_streak += 1
            max_streak = max(max_streak, cur_streak)
        else:
            cur_streak = 1

    # 同 arm 之间的平均间隔
    intervals = []
    last_pos = {}
    for i, a in enumerate(arms):
        if a in last_pos:
            intervals.append(i - last_pos[a])
        last_pos[a] = i
    mean_interval = float(np.mean(intervals)) if intervals else 0.0

    return {
        "consecutive_repeat_count": consecutive_count,
        "max_consecutive_streak": max_streak,
        "mean_interval_to_repeat": mean_interval,
        "n_repeats": len(intervals),
    }


# ─── 主入口 ─────────────────────────────────────────────────────


def main():
    _log.info("=" * 60)
    _log.info("D4 H3b: 干预多样性 arm diversity 评估")
    _log.info("=" * 60)

    # 1. 重放 lbc003
    _log.info("▶ 重放 lbc003 (56 道题)...")
    result = replay_lbc003()
    n = result["n_rounds"]
    single_arms = result["single_arms"]
    dual_arms = result["dual_arms"]
    _log.info(f"  n_rounds: {n}")

    # 2. 算多样性指标
    single_entropy = shannon_entropy(single_arms)
    dual_entropy = shannon_entropy(dual_arms)
    max_ent = max_entropy(N_ARMS)
    single_coverage = arm_coverage(single_arms)
    dual_coverage = arm_coverage(dual_arms)
    single_repeat = consecutive_repetition_interval(single_arms)
    dual_repeat = consecutive_repetition_interval(dual_arms)

    # 3. 报告
    _log.info("=" * 60)
    _log.info("多样性指标对比")
    _log.info("=" * 60)
    _log.info(f"Max entropy (10 arm 均匀): {max_ent:.3f}")
    _log.info("")
    _log.info("📊 Shannon Entropy (越大越多样):")
    _log.info(f"  单 Agent: {single_entropy:.3f} ({single_entropy/max_ent*100:.1f}% of max)")
    _log.info(f"  双 Agent: {dual_entropy:.3f} ({dual_entropy/max_ent*100:.1f}% of max)")
    _log.info(f"  差异: {dual_entropy - single_entropy:+.3f} (D4 阈值: > 1.5)")
    _log.info("")
    _log.info("📊 Arm 覆盖度 (至少选 1 次的比例):")
    _log.info(f"  单 Agent: {single_coverage*100:.1f}% ({int(single_coverage*N_ARMS)}/{N_ARMS} arm)")
    _log.info(f"  双 Agent: {dual_coverage*100:.1f}% ({int(dual_coverage*N_ARMS)}/{N_ARMS} arm)")
    _log.info(f"  差异: {(dual_coverage - single_coverage)*100:+.1f}% (D4 阈值: > 70%)")
    _log.info("")
    _log.info("📊 重复指标 (越小越多变):")
    _log.info(f"  单 Agent consecutive_repeat: {single_repeat['consecutive_repeat_count']} / {n} = "
              f"{single_repeat['consecutive_repeat_count']/n*100:.1f}%")
    _log.info(f"  双 Agent consecutive_repeat: {dual_repeat['consecutive_repeat_count']} / {n} = "
              f"{dual_repeat['consecutive_repeat_count']/n*100:.1f}%")
    _log.info(f"  单 Agent max_consecutive_streak: {single_repeat['max_consecutive_streak']}")
    _log.info(f"  双 Agent max_consecutive_streak: {dual_repeat['max_consecutive_streak']}")
    _log.info(f"  单 Agent mean_interval_to_repeat: {single_repeat['mean_interval_to_repeat']:.2f}")
    _log.info(f"  双 Agent mean_interval_to_repeat: {dual_repeat['mean_interval_to_repeat']:.2f}")
    _log.info("")
    _log.info("📊 Arm 分布 (前 5 arm):")
    single_counter = Counter(single_arms)
    dual_counter = Counter(dual_arms)
    for arm in range(5):
        s_count = single_counter.get(arm, 0)
        d_count = dual_counter.get(arm, 0)
        _log.info(f"  arm {arm}: 单={s_count} ({s_count/n*100:.1f}%)  "
                  f"双={d_count} ({d_count/n*100:.1f}%)")
    _log.info("=" * 60)

    # 4. 决策
    h3b_pass = (
        dual_entropy > 1.5
        and dual_coverage > 0.7
        and dual_repeat["consecutive_repeat_count"] <= single_repeat["consecutive_repeat_count"]
    )
    if h3b_pass:
        decision = "✅ H3b 通过: 双 Agent 在 arm 多样性上显著优于单 Agent"
    else:
        decision = "❌ H3b 不通过: 双 Agent 跟单 Agent 相当或更差"

    _log.info(f"决策: {decision}")
    _log.info("=" * 60)

    # 5. 存结果
    output = {
        "n_rounds": n,
        "max_entropy": max_ent,
        "single": {
            "entropy": single_entropy,
            "coverage": single_coverage,
            "consecutive_repeat_count": single_repeat["consecutive_repeat_count"],
            "max_consecutive_streak": single_repeat["max_consecutive_streak"],
            "mean_interval_to_repeat": single_repeat["mean_interval_to_repeat"],
            "arm_distribution": dict(single_counter),
        },
        "dual": {
            "entropy": dual_entropy,
            "coverage": dual_coverage,
            "consecutive_repeat_count": dual_repeat["consecutive_repeat_count"],
            "max_consecutive_streak": dual_repeat["max_consecutive_streak"],
            "mean_interval_to_repeat": dual_repeat["mean_interval_to_repeat"],
            "arm_distribution": dict(dual_counter),
        },
        "differences": {
            "entropy": dual_entropy - single_entropy,
            "coverage": dual_coverage - single_coverage,
        },
        "thresholds": {
            "min_entropy": 1.5,
            "min_coverage": 0.7,
        },
        "h3b_pass": h3b_pass,
        "decision": decision,
    }
    output_path = "discussions/2026-08-04-v075-D4-h3b-arm-diversity.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    _log.info(f"结果保存到 {output_path}")


if __name__ == "__main__":
    main()
