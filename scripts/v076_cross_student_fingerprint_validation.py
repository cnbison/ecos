"""v0.76 跨学生验证 fingerprint 修复普适性.

目的:
  v0.75.3 发现并修复了 LinUCB fingerprint 覆盖 BUG (_intervention_to_arm).
  在 lbc003 上验证 entropy 从 1.145 -> 2.546 (+122%).
  本脚本在 lbc001/lbc002 上重放, 验证修复不是 lbc003 特例.

方法:
  对每个学生跑两次:
    A. BUG 修复 (默认, _intervention_to_arm 启用)
    B. BUG 模拟 (monkey-patch _intervention_to_arm 为空, 强制走 _arm_fingerprints)
  对比 entropy / arm_coverage / max_streak.

预期:
  如果 fingerprint 修复普适, 三个学生在 A 模式下 entropy 都应该 > 1.5,
  且 A vs B 有显著差异 (A > B).

用法:
  python scripts/v076_cross_student_fingerprint_validation.py
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
from ecos.cta.belief_state import BloomLevel
from ecos.dual_agent.orchestrator import DualAgentConfig, DualAgentOrchestrator
from ecos.lca.l4_optimization import policy_learner as pl_mod

logging.basicConfig(level=logging.WARNING)
_log = logging.getLogger(__name__)

BLOOM_MAP = {
    "REMEMBER": BloomLevel.REMEMBER,
    "UNDERSTAND": BloomLevel.UNDERSTAND,
    "APPLY": BloomLevel.APPLY,
    "ANALYZE": BloomLevel.ANALYZE,
    "EVALUATE": BloomLevel.EVALUATE,
    "CREATE": BloomLevel.CREATE,
}


def load_history(student_id: str):
    db = _root / "web" / "ecos.db"
    conn = sqlite3.connect(str(db))
    row = conn.execute(
        "SELECT response_history FROM students WHERE student_id=?",
        (student_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"{student_id} not in DB")
    return json.loads(row[0])


def shannon_entropy(arms: list) -> float:
    if not arms:
        return 0.0
    counts = Counter(arms)
    total = len(arms)
    probs = [c / total for c in counts.values()]
    return -sum(p * math.log2(p) for p in probs if p > 0)


def arm_coverage(arms: list, n_arms: int = 10) -> float:
    if not arms:
        return 0.0
    return len(set(arms)) / n_arms


def max_consecutive_streak(arms: list) -> int:
    if not arms:
        return 0
    max_s = cur = 1
    for i in range(1, len(arms)):
        if arms[i] == arms[i - 1]:
            cur += 1
            max_s = max(max_s, cur)
        else:
            cur = 1
    return max_s


def replay_student(student_id: str, simulate_bug: bool = False) -> dict:
    """重放单个学生, 返回 arm 序列 + 指标.

    Args:
        student_id: 学生 ID
        simulate_bug: True = 模拟 v0.75.1 fingerprint 覆盖 BUG
                      (清空 _intervention_to_arm, 强制走 _arm_fingerprints)
    """
    rh = load_history(student_id)
    config = DualAgentConfig()
    config.lca_config.bandit_config.decay_factor = 1.0  # 默认无衰减
    orch = DualAgentOrchestrator(config=config, llm_client=None)
    sid = f"replay_v076_{student_id}_bug{'_on' if simulate_bug else '_off'}"

    arms = []
    for h in rh:
        obs = Observation(
            problem_id=h["problem_id"], skill_id="variables",
            correct=bool(h.get("correct", 0)),
            score=float(h.get("score", 0.0)),
            bloom_level=BLOOM_MAP.get(h.get("bloom_level", "APPLY"), BloomLevel.APPLY),
            response_time_sec=0.0,
        )
        orch.process_observation(obs, student_id=sid)

        bandit = orch.lca_engine.bandits.get(sid)
        if bandit is not None and simulate_bug:
            # 模拟 BUG: 清空 _intervention_to_arm, 强制走 _arm_fingerprints (会被覆盖)
            bandit._intervention_to_arm.clear()

        arms.append(bandit._last_arm if bandit is not None else -1)

    entropy = shannon_entropy(arms)
    coverage = arm_coverage(arms)
    streak = max_consecutive_streak(arms)
    dist = dict(sorted(Counter(arms).items()))

    return {
        "student_id": student_id,
        "n_rounds": len(arms),
        "entropy": round(entropy, 4),
        "entropy_pct_of_max": round(entropy / math.log2(10) * 100, 1),
        "arm_coverage": round(coverage, 4),
        "max_consecutive_streak": streak,
        "arm_distribution": {str(k): v for k, v in dist.items()},
        "h3c3_pass": entropy > 1.5,
    }


def main():
    print("=" * 72)
    print("v0.76 跨学生验证 fingerprint 修复普适性")
    print("=" * 72)

    students = ["lbc001", "lbc002", "lbc003"]
    results = []

    for sid in students:
        print(f"\n--- {sid} ---")
        # A. BUG 修复 (默认)
        result_fixed = replay_student(sid, simulate_bug=False)
        # B. BUG 模拟 (v0.75.1 行为)
        result_bug = replay_student(sid, simulate_bug=True)

        entropy_delta = result_fixed["entropy"] - result_bug["entropy"]
        streak_delta = result_bug["max_consecutive_streak"] - result_fixed["max_consecutive_streak"]

        print(f"  BUG 修复 (v0.75.3): entropy={result_fixed['entropy']} "
              f"({result_fixed['entropy_pct_of_max']}% of max), "
              f"coverage={result_fixed['arm_coverage']}, "
              f"streak={result_fixed['max_consecutive_streak']}, "
              f"h3c3={'PASS' if result_fixed['h3c3_pass'] else 'FAIL'}")
        print(f"  BUG 模拟 (v0.75.1): entropy={result_bug['entropy']} "
              f"({result_bug['entropy_pct_of_max']}% of max), "
              f"coverage={result_bug['arm_coverage']}, "
              f"streak={result_bug['max_consecutive_streak']}, "
              f"h3c3={'PASS' if result_bug['h3c3_pass'] else 'FAIL'}")
        print(f"  Delta: entropy +{entropy_delta:.3f}, streak -{streak_delta}")

        results.append({
            "student_id": sid,
            "bug_fixed": result_fixed,
            "bug_simulated": result_bug,
            "entropy_delta": round(entropy_delta, 4),
            "streak_delta": streak_delta,
            "fingerprint_fix_effective": entropy_delta > 0.3,
        })

    output = {
        "version": "v0.76",
        "date": "2026-08-05",
        "students": results,
        "summary": {
            "all_students_pass_h3c3_when_fixed": all(r["bug_fixed"]["h3c3_pass"] for r in results),
            "fix_effective_for_all": all(r["fingerprint_fix_effective"] for r in results),
            "avg_entropy_delta": round(np.mean([r["entropy_delta"] for r in results]), 4),
        },
        "conclusion": (
            "fingerprint 修复普适: 所有学生 BUG 修复后 entropy > 1.5, "
            "BUG 模拟下 entropy 显著降低."
            if all(r["bug_fixed"]["h3c3_pass"] and r["fingerprint_fix_effective"] for r in results)
            else "fingerprint 修复效果因学生而异, 需进一步分析."
        ),
    }

    out_path = _root / "discussions" / "2026-08-05-v076-cross-student-fingerprint-validation.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"\n结果保存: {out_path}")

    print(f"\n结论: {output['conclusion']}")
    print(f"平均 entropy delta: {output['summary']['avg_entropy_delta']}")


if __name__ == "__main__":
    main()
