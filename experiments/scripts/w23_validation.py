"""W2 + W3 验证脚本：自适应选题加权深化 + 探针题机制。

对应：
  - research/00-overview/03-roadmap.md §2.5（W2 + W3）
  - discussions/2026-07-17-方向选择-A先C后.md
  - research/00-overview/02-architecture.md §8.5（探针题机制）

目的：
  验证 Phase 4 W2 + W3 落地的 6 个改动点：
  W2（自适应选题层深化）：
    1) _select_adaptive_question 4 维加权（SE / topic 弱 / Bloom Δ / 随机）
    2) Bloom Δ 距离匹配
  W3（探针题机制）：
    3) _select_probe_question 选 a_specialized 最大题
    4) BeliefEngine 探针题状态机
    5) select_question_for_student force_probe 整合
    6) API 透传 is_probe / probe_dim_star

运行：
  PYTHONPATH=. python experiments/scripts/w23_validation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from ecos.cta import (
    BeliefEngine,
    BeliefEngineConfig,
    BloomLevel,
    Observation,
)
from web.api.qmatrix import (
    _select_adaptive_question,
    _select_probe_question,
    select_question_for_student,
    get_all_problems,
)


# ---------------------------------------------------------------------------
# 测试计数器
# ---------------------------------------------------------------------------

_TOTAL = 0
_PASSED = 0
_FAILED = 0


def _check(name: str, condition: bool, detail: str = "") -> bool:
    global _TOTAL, _PASSED, _FAILED
    _TOTAL += 1
    if condition:
        _PASSED += 1
        print(f"  ✅ {name}" + (f" — {detail}" if detail else ""))
        return True
    else:
        _FAILED += 1
        print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))
        return False


# ---------------------------------------------------------------------------
# 场景 1: W2 自适应选题加权深化
# ---------------------------------------------------------------------------


def scenario_1_adaptive_weighted() -> None:
    print("\n" + "=" * 70)
    print("场景 1: W2 _select_adaptive_question 加权深化")
    print("=" * 70)

    all_probs = get_all_problems()
    answered: set[str] = set()

    # 1.1 K 维度方差最大,d_star=0
    #   - 不带 prefer_topics / target_bloom
    #   - 应该选 a_specialized[0] 最大的题
    theta_mean = [0.0] * 5
    theta_cov_diag = [5.0, 1.0, 1.0, 1.0, 1.0]
    prob = _select_adaptive_question(
        all_probs,
        theta_mean=theta_mean,
        theta_cov_diag=theta_cov_diag,
        target_bloom=None,
    )
    _check("1.1 K 方差最大,d_star=0", prob.get("_adaptive_dim_star") == 0, f"d_star={prob.get('_adaptive_dim_star')}")
    _check("1.2 _strategy=adaptive", prob.get("_strategy") == "adaptive")
    # 1.3 选题应优先 a_specialized[0] 大的题
    top_a_k = max(p["a_specialized"][0] for p in all_probs if "a_specialized" in p)
    _check("1.3 选题 a_specialized[0] 接近 top", prob["a_specialized"][0] >= top_a_k - 0.01,
           f"a_K={prob['a_specialized'][0]} top_a_K={top_a_k}")

    # 1.4 target_bloom=L3 时,应优先选 L3 的题
    prob_l3 = _select_adaptive_question(
        all_probs,
        theta_mean=theta_mean,
        theta_cov_diag=theta_cov_diag,
        target_bloom="L3",
    )
    _check("1.4 target_bloom=L3 优先选 L3 题",
           prob_l3["bloom_goal_id"].endswith("-L3"),
           f"bloom={prob_l3['bloom_goal_id']}")

    # 1.5 target_bloom=L4 时,应优先选 L4 的题（或 L3/L5 接近层）
    prob_l4 = _select_adaptive_question(
        all_probs,
        theta_mean=theta_mean,
        theta_cov_diag=theta_cov_diag,
        target_bloom="L4",
    )
    p_bloom = prob_l4["bloom_goal_id"].split("-")[-1]
    _check("1.5 target_bloom=L4 优先选 L4 题（或 L3/L5）",
           p_bloom in ("L3", "L4", "L5"),
           f"bloom={prob_l4['bloom_goal_id']}")

    # 1.6 5D 全部方差相等时,d_star=0（argmax 选第一个）
    theta_cov_equal = [1.0, 1.0, 1.0, 1.0, 1.0]
    prob_eq = _select_adaptive_question(
        all_probs,
        theta_mean=theta_mean,
        theta_cov_diag=theta_cov_equal,
    )
    _check("1.6 全部方差相等 d_star=0（argmax 选 index=0）",
           prob_eq.get("_adaptive_dim_star") == 0,
           f"d_star={prob_eq.get('_adaptive_dim_star')}")


# ---------------------------------------------------------------------------
# 场景 2: W3 _select_probe_question
# ---------------------------------------------------------------------------


def scenario_2_probe_selector() -> None:
    print("\n" + "=" * 70)
    print("场景 2: W3 _select_probe_question 探针题选题")
    print("=" * 70)

    all_probs = get_all_problems()

    # 2.1 K 维度方差最大 → 选 a_specialized[0] 最大的题
    theta_cov_diag = [5.0, 1.0, 1.0, 1.0, 1.0]
    prob = _select_probe_question(all_probs, theta_cov_diag=theta_cov_diag)
    _check("2.1 探针题返回非空", prob is not None)
    _check("2.2 _strategy=probe", prob is not None and prob.get("_strategy") == "probe")
    _check("2.3 K 方差最大 d_star=0", prob is not None and prob.get("_probe_dim_star") == 0)
    top_a_k = max(p["a_specialized"][0] for p in all_probs if "a_specialized" in p)
    _check("2.4 探针题 a_specialized[0] 接近 top",
           prob["a_specialized"][0] >= top_a_k - 0.01,
           f"a_K={prob['a_specialized'][0]} top_a_K={top_a_k}")

    # 2.5 C 维度方差最大 → 选 a_specialized[3] 最大的题
    theta_cov_diag_c = [1.0, 1.0, 1.0, 5.0, 1.0]
    prob_c = _select_probe_question(all_probs, theta_cov_diag=theta_cov_diag_c)
    _check("2.5 C 方差最大 d_star=3", prob_c.get("_probe_dim_star") == 3)
    top_a_c = max(p["a_specialized"][3] for p in all_probs if "a_specialized" in p)
    _check("2.6 探针题 a_specialized[3] 接近 top",
           prob_c["a_specialized"][3] >= top_a_c - 0.01,
           f"a_C={prob_c['a_specialized'][3]} top_a_C={top_a_c}")

    # 2.7 无 cov 时退化为随机
    prob_no_cov = _select_probe_question(all_probs, theta_cov_diag=None)
    _check("2.7 无 cov 走随机 fallback", prob_no_cov is not None and prob_no_cov.get("_probe_dim_star") is None)


# ---------------------------------------------------------------------------
# 场景 3: BeliefEngine 探针题状态机
# ---------------------------------------------------------------------------


def scenario_3_probe_state_machine() -> None:
    print("\n" + "=" * 70)
    print("场景 3: BeliefEngine 探针题状态机（W3 改动点）")
    print("=" * 70)

    config = BeliefEngineConfig(warmup_questions=3, warmup_step=0.1, probe_interval=4)
    engine = BeliefEngine(config=config)
    sid = "test_probe_student"

    # 3.1 新生:warm-up 期,should_probe=False
    _check("3.1 新生 should_probe=False（warm-up 期）", engine.should_probe_now(sid) is False)
    progress = engine.probe_progress(sid)
    _check("3.2 新生 probe_count=0", progress["probe_count"] == 0)
    _check("3.3 新生 probe_interval=4", progress["probe_interval"] == 4)

    # 3.4 答 3 题（warm-up 期）,should_probe 仍 False
    state = engine.create_initial_state(sid)
    for i in range(3):
        obs = Observation(skill_id="K.var", problem_id=f"Q{i+1}", correct=True, bloom_level=BloomLevel.REMEMBER)
        state = engine.update(state, obs)
    _check("3.4 答完 warm-up 期,should_probe=False（刚出 warm-up,_probe_due_in=4）",
           engine.should_probe_now(sid) is False,
           f"due_in={engine._probe_due_in.get(sid, 'N/A')}")

    # 3.5 答第 4 题(刚出 warm-up,_probe_due_in 从 4 递减 1 = 3 后,再递减 1 = 2)
    obs = Observation(skill_id="K.var", problem_id="Q4", correct=True, bloom_level=BloomLevel.REMEMBER)
    state = engine.update(state, obs)
    # 答完第 4 题时,_probe_due_in 应是 2（刚出 warm-up 时初始化为 4,第 4 题再递减 1 = 2,实际是 3→2）
    # 等等,3.4 时第 3 题 _probe_due_in 已经初始化为 4 然后递减到 3;3.5 时再递减到 2
    _check("3.5 答 4 题后,probe_due_in=2",
           engine._probe_due_in.get(sid) == 2,
           f"due_in={engine._probe_due_in.get(sid, 'N/A')}")
    _check("3.6 答 4 题后,should_probe=False（还需 2 题）", engine.should_probe_now(sid) is False)

    # 3.7 答 5,6,7 题后,_probe_due_in=0,should_probe=True
    for i in range(5, 8):
        obs = Observation(skill_id="K.var", problem_id=f"Q{i}", correct=True, bloom_level=BloomLevel.REMEMBER)
        state = engine.update(state, obs)
    _check("3.7 答 7 题后,probe_due_in=0",
           engine._probe_due_in.get(sid) == 0,
           f"due_in={engine._probe_due_in.get(sid, 'N/A')}")
    _check("3.8 答 7 题后,should_probe=True", engine.should_probe_now(sid) is True)

    # 3.9 consume_probe 后,_probe_due_in 重置为 4
    engine.consume_probe(sid)
    _check("3.9 consume_probe 后,probe_due_in=4", engine._probe_due_in.get(sid) == 4)
    _check("3.10 consume_probe 后,probe_count=1", engine._probe_count.get(sid) == 1)
    _check("3.11 consume_probe 后,should_probe=False", engine.should_probe_now(sid) is False)

    # 3.12 reset_student 应清空 probe 状态
    engine.reset_student(sid)
    _check("3.12 reset 后,_probe_due_in 清空", sid not in engine._probe_due_in)
    _check("3.13 reset 后,_probe_count 清空", sid not in engine._probe_count)


# ---------------------------------------------------------------------------
# 场景 4: select_question_for_student 整合
# ---------------------------------------------------------------------------


def scenario_4_select_integration() -> None:
    print("\n" + "=" * 70)
    print("场景 4: select_question_for_student 整合探针题路径")
    print("=" * 70)

    all_probs = get_all_problems()
    answered: set[str] = set()
    sid = "test_select_integration"

    # 4.1 force_probe=True 走探针题路径
    theta_cov_diag = [5.0, 1.0, 1.0, 1.0, 1.0]
    prob = select_question_for_student(
        answered,
        theta_mean=[0.0] * 5,
        theta_cov_diag=theta_cov_diag,
        student_id=sid,
        force_probe=True,
    )
    _check("4.1 force_probe=True 走探针路径", prob is not None and prob.get("_strategy") == "probe")
    _check("4.2 探针题 _probe_dim_star=0", prob is not None and prob.get("_probe_dim_star") == 0)

    # 4.3 force_probe=True + is_warmup=True,探针优先级最高
    prob_warmup_probe = select_question_for_student(
        answered,
        is_warmup=True,
        theta_mean=[0.0] * 5,
        theta_cov_diag=theta_cov_diag,
        student_id=sid + "_2",
        force_probe=True,
    )
    _check("4.3 force_probe 优先级 > is_warmup",
           prob_warmup_probe is not None and prob_warmup_probe.get("_strategy") == "probe")

    # 4.4 is_warmup=True + force_probe=False 走覆盖性
    prob_warmup = select_question_for_student(
        answered,
        is_warmup=True,
        student_id=sid + "_3",
    )
    _check("4.4 is_warmup=True + force_probe=False 走覆盖性",
           prob_warmup is not None and prob_warmup.get("_strategy") == "warmup")

    # 4.5 is_warmup=False + force_probe=False + 有 cov 走自适应
    prob_adaptive = select_question_for_student(
        answered,
        is_warmup=False,
        theta_mean=[0.0] * 5,
        theta_cov_diag=theta_cov_diag,
        student_id=sid + "_4",
    )
    _check("4.5 is_warmup=False + 有 cov 走自适应",
           prob_adaptive is not None and prob_adaptive.get("_strategy") == "adaptive")


# ---------------------------------------------------------------------------
# 场景 5: End-to-end 完整流（warm-up → adaptive → probe）
# ---------------------------------------------------------------------------


def scenario_5_end_to_end() -> None:
    print("\n" + "=" * 70)
    print("场景 5: End-to-end 完整流（warm-up → adaptive → probe）")
    print("=" * 70)

    config = BeliefEngineConfig(warmup_questions=3, warmup_step=0.1, probe_interval=4)
    engine = BeliefEngine(config=config)
    sid = "test_e2e_probe"
    state = engine.create_initial_state(sid)
    answered: set[str] = set()

    history: list[str] = []  # 记录每次选的是什么策略

    # 5.1 模拟前 3 题 warm-up
    for i in range(3):
        prob = select_question_for_student(
            answered,
            is_warmup=engine.is_warmup(sid),
            student_id=sid,
        )
        history.append(prob.get("_strategy", "unknown"))
        answered.add(prob["problem_id"])
        # 模拟答题
        obs = Observation(skill_id="K.var", problem_id=prob["problem_id"], correct=True, bloom_level=BloomLevel.REMEMBER)
        state = engine.update(state, obs)
    _check("5.1 前 3 题走 warmup 策略",
           all(s == "warmup" for s in history),
           f"history={history}")

    # 5.2 答到第 7 题（warm-up 后 4 题）,should_probe 应为 True
    for i in range(3, 7):
        should_probe = engine.should_probe_now(sid)
        # 传 theta_cov_diag 让自适应路径走通
        theta_cov_diag = [float(state.theta_cov[j, j]) for j in range(5)]
        prob = select_question_for_student(
            answered,
            is_warmup=engine.is_warmup(sid),
            force_probe=should_probe,
            theta_mean=state.theta_mean.tolist(),
            theta_cov_diag=theta_cov_diag,
            student_id=sid,
        )
        history.append(prob.get("_strategy", "unknown"))
        answered.add(prob["problem_id"])
        obs = Observation(skill_id="K.var", problem_id=prob["problem_id"], correct=True, bloom_level=BloomLevel.REMEMBER)
        state = engine.update(state, obs)
        if should_probe:
            engine.consume_probe(sid)

    # 5.3 7 题中应有 1 题是 probe
    probe_count = sum(1 for s in history if s == "probe")
    _check("5.3 7 题中至少 1 题 probe", probe_count >= 1, f"history={history}")
    # 5.4 7 题中应有 ≥3 题是 adaptive
    adaptive_count = sum(1 for s in history if s == "adaptive")
    _check("5.4 7 题中 ≥3 题 adaptive", adaptive_count >= 3, f"history={history}")

    # 5.5 probe_count 应 ≥1
    _check("5.5 engine._probe_count ≥ 1", engine._probe_count.get(sid, 0) >= 1)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def main() -> None:
    print("=" * 70)
    print("ECOS Phase 4 W2 + W3 验证：自适应选题加权 + 探针题机制")
    print("=" * 70)

    scenario_1_adaptive_weighted()
    scenario_2_probe_selector()
    scenario_3_probe_state_machine()
    scenario_4_select_integration()
    scenario_5_end_to_end()

    print("\n" + "=" * 70)
    print(f"结果:{_PASSED}/{_TOTAL} passed, {_FAILED} failed")
    print("=" * 70)

    if _FAILED > 0:
        print("❌ 验证未通过,请检查实现")
        sys.exit(1)
    else:
        print("✅ W2 + W3 全部验证通过")


if __name__ == "__main__":
    main()
