"""v0.69.0-d 重放脚本: 用 lbc003 response_history 重放 42+ 道 process_observation.

目的:
  - 修复策略质疑路径绕过 BUG 后, 验证 V3 (dual_agent_confidence) 字段实际被写入
  - 算修复后 H3 V3 ECE, 看 LinUCB θ@x 预测 vs actual_outcome 校准

注意:
  - **不写 DB**: 重放只跑 in-memory, calibration_log / dual_agent_state 不污染
  - **不复用 lbc003 的旧 dual_agent_state**: 用全新 DualAgentOrchestrator, 从 response_history[0] 开始
  - **不接 LLM**: llm_client=None, intervention 生成走 fallback (LinUCB 不依赖 LLM)

输出:
  - V3 写入率 (有 dual_agent_confidence 非 None 的 round 比例)
  - V3 source 分布 (linucb / estimate_gain_fallback)
  - V3 vs actual_outcome ECE
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

from ecos.dual_agent.orchestrator import DualAgentConfig, DualAgentOrchestrator
from ecos.cta.belief_engine import Observation, BeliefEngine, BeliefEngineConfig
from ecos.cta.l1_evolution import EvolutionConfig
from ecos.cta.l2_mirt import MIRTConfig
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


def replay(student_id: str = 'lbc003_replay'):
    """重放 lbc003 答题数据, 看修复后 V3 字段写入情况."""
    print(f'=== 重放 {student_id} ===')
    rh = load_lbc003_response_history()
    print(f'response_history 条数: {len(rh)}')

    # 全新 orch (不接 DB, 不接 LLM)
    orch = DualAgentOrchestrator(config=DualAgentConfig(), llm_client=None)

    # 跑每道题
    sc_triggered = 0
    v3_written = 0
    v3_linucb = 0
    v3_fallback = 0
    v3_none = 0
    v3_values = []  # (dual_agent_confidence, actual_outcome) pairs
    actual_outcomes = []

    for i, h in enumerate(rh):
        obs = Observation(
            problem_id=h['problem_id'],
            skill_id='variables',  # 简化, 不影响 dual_agent 路径
            correct=bool(h.get('correct', 0)),
            score=float(h.get('score', 0.0)),
            bloom_level=bloom_str_to_enum(h.get('bloom_level', 'APPLY')),
            response_time_sec=0.0,
        )
        result = orch.process_observation(obs, student_id=student_id)

        # 统计 strategy_challenge_triggered
        if result.metadata.get('strategy_challenge_triggered'):
            sc_triggered += 1

        # 统计 V3 字段写入
        v3 = result.metadata.get('dual_agent_confidence')
        v3_src = result.metadata.get('dual_agent_confidence_source')
        if v3 is not None:
            v3_written += 1
            if v3_src == 'linucb':
                v3_linucb += 1
            elif v3_src == 'estimate_gain_fallback':
                v3_fallback += 1
        else:
            v3_none += 1

        # 拿 prev (上一轮) 的 actual_outcome 来配对 V3 -> accuracy
        # 因为 V3 是当前轮预测, 实际 outcome 是下一轮 Step 0 填到 prev
        if i >= 1:
            hist = orch.intervention_history[student_id]
            if len(hist) >= 2:
                prev = hist[-2]
                if prev.actual_outcome is not None and v3 is not None:
                    # V3 是当前轮 (this result) 预测, 配对 prev (上一轮 actual_outcome)
                    # 实际上 V3 应该跟当前轮的 actual_outcome 配对 (下一轮填)
                    # 但下一轮还没跑, 所以用 prev.actual_outcome 配 prev 的 dual_agent_confidence
                    # 这里更精确: 用 prev.metadata.dual_agent_confidence (上一轮 V3) 配 prev.actual_outcome
                    prev_v3 = prev.metadata.get('dual_agent_confidence')
                    if prev_v3 is not None and prev.actual_outcome is not None:
                        v3_values.append((prev_v3, prev.actual_outcome))
                        actual_outcomes.append(prev.actual_outcome)

    print()
    print('=== 重放统计 ===')
    print(f'总答题数: {len(rh)}')
    print(f'触发策略质疑次数: {sc_triggered} ({sc_triggered/len(rh)*100:.1f}%)')
    print(f'V3 dual_agent_confidence 写入: {v3_written} ({v3_written/len(rh)*100:.1f}%)')
    print(f'  V3 source=linucb: {v3_linucb}')
    print(f'  V3 source=estimate_gain_fallback: {v3_fallback}')
    print(f'V3 None (prev None 跳过): {v3_none}')
    print()
    print(f'=== V3 vs actual_outcome ECE ===')
    print(f'有效配对数: {len(v3_values)}')
    if v3_values:
        # 算 ECE: 平均 |confidence - accuracy|
        errors = [abs(c - a) for c, a in v3_values]
        ece = sum(errors) / len(errors)
        # 算 accuracy 平均
        avg_conf = sum(c for c, _ in v3_values) / len(v3_values)
        avg_acc = sum(a for _, a in v3_values) / len(v3_values)
        print(f'平均 V3 confidence: {avg_conf:.4f}')
        print(f'平均 actual_outcome: {avg_acc:.4f}')
        print(f'ECE (per-sample |conf - acc| 平均): {ece:.4f}')
        print()
        print('=== V3 source 分布 ===')
        # 看 V3 source 分布 (从所有 round metadata 收集)
        src_counter = {'linucb': 0, 'estimate_gain_fallback': 0, 'none': 0}
        for r in orch.intervention_history[student_id]:
            v3 = r.metadata.get('dual_agent_confidence')
            v3_src = r.metadata.get('dual_agent_confidence_source')
            if v3 is None:
                src_counter['none'] += 1
            elif v3_src == 'linucb':
                src_counter['linucb'] += 1
            elif v3_src == 'estimate_gain_fallback':
                src_counter['estimate_gain_fallback'] += 1
        print(src_counter)

        # 冷启动状态
        bandit = orch.lca_engine.bandits.get(student_id)
        if bandit:
            total_pulls = int(bandit.bandit.arm_pull_counts.sum())
            print(f'\nLinUCB 总 pull 次数: {total_pulls}')
            print(f'是否冷启动 (pulls < 10)? {orch.lca_engine._is_linucb_cold_start(student_id)}')


if __name__ == '__main__':
    replay()
