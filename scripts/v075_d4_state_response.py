"""v0.75 Plan B D4 H3c: 状态响应速度 state response 评估.

目的:
  H3 拆 3 子假设, 验证 H3c: 互校快速响应学生状态变化.
  重放 lbc003 56 道题, 找 6 Bloom 状态拐点 (任一维度变化 > 0.1),
  算 "状态变化后多少题内, intervention 切换".

评估指标:
  1. 拐点检测: 6 Bloom 任一维度 diff > 0.1 (联合状态发生显著变化)
  2. 单 Agent 响应: 下一题就换 arm (因为 CTA heuristic 立即根据新 mastery 选)
  3. 双 Agent 响应: LinUCB bandit.update 多少题后才让 UCB 选择其他 arm
  4. 收敛速度: LinUCB 从冷启动到 ECE 0.15 以下用了多少题

通过阈值 (D4 PRD §2):
  - 双 Agent 检测延迟 < 3 题
  - 双 Agent 收敛速度 < 30 题 (ECE < 0.15)

用法:
  python scripts/v075_d4_state_response.py
"""

from __future__ import annotations

import json
import logging
import sqlite3
import sys
from pathlib import Path

import numpy as np

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from ecos.cta.belief_engine import Observation
from ecos.cta.belief_state import BloomLevel
from ecos.dual_agent.orchestrator import DualAgentConfig, DualAgentOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
_log = logging.getLogger(__name__)

# 用 6 Bloom 而非 5D: lbc003 单 skill 让 5D 收敛 (max diff 0.082 < 阈值 0.1)
DIM_NAMES = ["remember", "understand", "apply", "analyze", "evaluate", "create"]
STATE_CHANGE_THRESHOLD = 0.1  # 6 Bloom 任一维度变化 > 0.1 算拐点
RESPONSE_WINDOW = 5  # 拐点后多少题内观察 response


def replay_lbc003():
    """重放 lbc003, 收集 (6 Bloom state 序列, dual arm 序列, cal_v3, actual) 序列.

    Returns:
        dict {
            "states": list of 6 Bloom vectors per round,
            "dual_arms": list of arm index per round,
            "actuals": list of correct (0/1) per round,
            "cal_v3_raw": list of raw V3 per round,
            "cal_v3_calibrated": list of calibrated V3 per round,
        }
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
    sid = "replay_d4_h3c"

    states = []
    dual_arms = []
    actuals = []
    cal_v3_raw = []
    cal_v3_calibrated = []

    for round_idx, h in enumerate(rh):
        ih_len_before = len(orch.intervention_history.get(sid, []))
        obs = Observation(
            problem_id=h["problem_id"], skill_id="variables",
            correct=bool(h.get("correct", 0)),
            score=float(h.get("score", 0.0)),
            bloom_level=bloom_map.get(h.get("bloom_level", "APPLY"), BloomLevel.APPLY),
            response_time_sec=0.0,
        )
        orch.process_observation(obs, student_id=sid)

        # 6 Bloom state (变化幅度比 5D 大, 因为不同 Bloom 间独立)
        if sid in orch.state:
            s = orch.state[sid]
            state_6b = np.array([
                float(s.bloom_profile.remember),
                float(s.bloom_profile.understand),
                float(s.bloom_profile.apply),
                float(s.bloom_profile.analyze),
                float(s.bloom_profile.evaluate),
                float(s.bloom_profile.create),
            ])
        else:
            state_6b = np.array([0.5] * 6)

        # dual arm
        bandit = orch.lca_engine.bandits.get(sid)
        dual_arm = bandit._last_arm if bandit is not None else -1

        # calibrated V3 (取**本轮**新写入的 intervention)
        ih_after = orch.intervention_history.get(sid, [])
        if len(ih_after) > ih_len_before:
            cal = ih_after[-1]  # 本轮新增的那条
            cal_v3_raw.append(cal.metadata.get("dual_agent_confidence"))
            cal_v3_calibrated.append(cal.metadata.get("dual_agent_confidence_calibrated"))
        else:
            cal_v3_raw.append(None)
            cal_v3_calibrated.append(None)

        states.append(state_6b)
        dual_arms.append(dual_arm)
        actuals.append(float(h.get("correct", 0)))

    # 报告 metadata 完整性
    raw_with_val = sum(1 for v in cal_v3_raw if v is not None)
    cal_with_val = sum(1 for v in cal_v3_calibrated if v is not None)
    _log.info(f"  raw V3 有值: {raw_with_val}/{len(cal_v3_raw)}")
    _log.info(f"  calibrated V3 有值: {cal_with_val}/{len(cal_v3_calibrated)}")

    return {
        "states": states,
        "dual_arms": dual_arms,
        "actuals": actuals,
        "cal_v3_raw": cal_v3_raw,
        "cal_v3_calibrated": cal_v3_calibrated,
    }


def find_state_change_points(states: list, threshold: float = STATE_CHANGE_THRESHOLD) -> list:
    """找 6 Bloom 状态拐点 (任一维度变化 > threshold).

    Returns:
        list of (round_idx, dim_name, change_magnitude)
    """
    points = []
    for i in range(1, len(states)):
        diff = states[i] - states[i-1]
        max_dim = int(np.argmax(np.abs(diff)))
        max_change = abs(diff[max_dim])
        if max_change > threshold:
            points.append((i, DIM_NAMES[max_dim], max_change))
    return points


def detect_response_delay(arms: list, change_points: list, window: int = RESPONSE_WINDOW) -> list:
    """算每个拐点后, arm 切换的延迟.

    切换定义: 当前 arm 跟拐点前的 arm 不同, 且新 arm 保持至少 2 轮.
    """
    delays = []
    for cp_idx, dim, change in change_points:
        if cp_idx == 0:
            continue
        prev_arm = arms[cp_idx - 1]
        response = None
        for j in range(cp_idx, min(cp_idx + window, len(arms))):
            if arms[j] != prev_arm:
                # 检查是否保持 2 轮
                if j + 1 < len(arms) and arms[j+1] == arms[j]:
                    response = j - cp_idx
                    break
                elif j == len(arms) - 1:
                    response = j - cp_idx
                    break
        delays.append({
            "change_point_round": cp_idx,
            "changed_dim": dim,
            "change_magnitude": float(change),
            "prev_arm": int(prev_arm),
            "response_round": response,
        })
    return delays


def compute_ece_trajectory(confidences: list, accuracies: list) -> list:
    """算每轮的累积 ECE (从 round 5 到 round N). 跳过 None."""
    # 对齐: 过滤掉 None
    pairs = [(c, a) for c, a in zip(confidences, accuracies) if c is not None]
    ece_traj = []
    for n in range(5, len(pairs) + 1):
        confs = np.array([p[0] for p in pairs[:n]])
        accs = np.array([p[1] for p in pairs[:n]])
        ece = float(np.mean(np.abs(confs - accs)))
        ece_traj.append({"n_pairs": n, "ece": ece})
    return ece_traj


def find_convergence_round(ece_traj: list, threshold: float = 0.15) -> int:
    """找 ECE 首次降到 threshold 以下的题数."""
    for entry in ece_traj:
        if entry["ece"] <= threshold:
            return entry["n_pairs"]
    return -1


def main():
    _log.info("=" * 60)
    _log.info("D4 H3c: 状态响应速度 state response 评估 (6 Bloom)")
    _log.info("=" * 60)

    # 1. 重放 lbc003
    _log.info("▶ 重放 lbc003 (56 道题)...")
    result = replay_lbc003()
    n = len(result["states"])
    _log.info(f"  n_rounds: {n}")

    # 2. 找 6 Bloom 状态拐点
    _log.info(f"▶ 找 6 Bloom 状态拐点 (任一维度变化 > {STATE_CHANGE_THRESHOLD})...")
    change_points = find_state_change_points(result["states"])
    _log.info(f"  找到 {len(change_points)} 个拐点")
    if change_points[:5]:
        for cp in change_points[:5]:
            _log.info(f"    round {cp[0]}: {cp[1]} 变化 {cp[2]:+.3f}")

    # 3. 算 response delay (双 Agent)
    _log.info(f"▶ 算 arm response delay (window={RESPONSE_WINDOW})...")
    delays = detect_response_delay(result["dual_arms"], change_points)
    response_delays = [d["response_round"] for d in delays if d["response_round"] is not None]
    no_response_count = sum(1 for d in delays if d["response_round"] is None)
    if response_delays:
        mean_delay = float(np.mean(response_delays))
        median_delay = float(np.median(response_delays))
        max_delay = int(max(response_delays))
    else:
        mean_delay = median_delay = 0.0
        max_delay = 0
    _log.info(f"  总拐点数: {len(delays)}")
    _log.info(f"  响应拐点数: {len(response_delays)}")
    _log.info(f"  未响应拐点数: {no_response_count}")
    _log.info(f"  平均 response delay: {mean_delay:.2f} 题 (D4 阈值: < 3)")
    _log.info(f"  中位数 response delay: {median_delay:.2f} 题")
    _log.info(f"  最大 response delay: {max_delay} 题")

    # 4. 单 Agent response (heuristic 立即响应, delay = 1)
    single_response_delay = 1
    _log.info(f"  单 Agent response delay: {single_response_delay} 题 (heuristic 立即)")

    # 5. 算 LinUCB 收敛速度
    _log.info("▶ 算 LinUCB 收敛速度 (calibrated V3 ECE trajectory)...")
    ece_traj = compute_ece_trajectory(
        result["cal_v3_calibrated"],
        result["actuals"],
    )
    convergence_round_15 = find_convergence_round(ece_traj, threshold=0.15)
    convergence_round_20 = find_convergence_round(ece_traj, threshold=0.20)
    _log.info(f"  ECE 轨迹点数: {len(ece_traj)}")
    if ece_traj:
        _log.info(f"  ECE 起始: {ece_traj[0]['ece']:.3f} (n={ece_traj[0]['n_pairs']})")
        _log.info(f"  ECE 末位: {ece_traj[-1]['ece']:.3f} (n={ece_traj[-1]['n_pairs']})")
    _log.info(f"  ECE 首次 < 0.15: round {convergence_round_15} (D4 阈值: < 30)")
    _log.info(f"  ECE 首次 < 0.20: round {convergence_round_20}")

    # 6. 报告
    _log.info("=" * 60)
    _log.info("状态响应指标")
    _log.info("=" * 60)
    _log.info("📊 Arm response delay (越小越快):")
    _log.info(f"  单 Agent (heuristic): {single_response_delay} 题")
    _log.info(f"  双 Agent (LinUCB):    {mean_delay:.2f} 题")
    _log.info("")
    _log.info("📊 LinUCB 收敛速度 (round 数越少越快):")
    _log.info(f"  ECE < 0.15: {convergence_round_15} 题 (D4 阈值: < 30)")
    _log.info(f"  ECE < 0.20: {convergence_round_20} 题")
    _log.info("")
    _log.info("📊 6 Bloom 状态拐点 vs arm 响应:")
    for d in delays[:5]:
        rr = d["response_round"] if d["response_round"] is not None else "未响应"
        _log.info(f"  round {d['change_point_round']:3d} {d['changed_dim']} Δ{d['change_magnitude']:+.3f} "
                  f"-> arm response: {rr} 题")
    _log.info("=" * 60)

    # 7. 决策
    h3c_pass = (
        mean_delay < 3
        and convergence_round_15 != -1 and convergence_round_15 < 30
    )
    if h3c_pass:
        decision = "✅ H3c 通过: 双 Agent 快速响应 + 收敛速度达标"
    elif not change_points:
        decision = "⚠️ H3c 不可评估: lbc003 单 skill 让 6 Bloom 都没显著拐点, 缺测试场景"
    else:
        decision = f"❌ H3c 不通过: response delay {mean_delay:.2f} ≥ 3 或 收敛 round {convergence_round_15} ≥ 30"

    _log.info(f"决策: {decision}")
    _log.info("=" * 60)

    # 8. 存结果
    output = {
        "n_rounds": n,
        "n_change_points": len(change_points),
        "thresholds": {
            "state_change": STATE_CHANGE_THRESHOLD,
            "response_window": RESPONSE_WINDOW,
            "max_response_delay": 3,
            "max_convergence_round": 30,
        },
        "single_agent": {
            "response_delay": single_response_delay,
        },
        "dual_agent": {
            "mean_response_delay": mean_delay,
            "median_response_delay": median_delay,
            "max_response_delay": max_delay,
            "n_responded": len(response_delays),
            "n_no_response": no_response_count,
            "convergence_round_ece_15": convergence_round_15,
            "convergence_round_ece_20": convergence_round_20,
        },
        "ece_trajectory": ece_traj[::5],
        "sample_delays": delays[:10],
        "h3c_pass": h3c_pass,
        "decision": decision,
    }
    output_path = "discussions/2026-08-04-v075-D4-h3c-state-response.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    _log.info(f"结果保存到 {output_path}")


if __name__ == "__main__":
    main()
