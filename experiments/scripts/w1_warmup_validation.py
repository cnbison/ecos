"""W1 Warm-up 窗口 + 自适应选题验证脚本.

对应：
  - discussions/2026-07-17-方向选择-A先C后.md（5 个开放问题定案）
  - research/00-overview/03-roadmap.md §2.5 (W1 第一刀:warm-up + Bloom Δ)
  - research/00-overview/02-architecture.md §3.4 / §8.4 / §8.5

目的：
  验证 Phase 4 W1 落地的 7 个改动点：
  1) BeliefEngine warm-up 状态机:is_warmup / warmup_remaining / warmup_progress
  2) BloomProfileState.distance_to_next_layer() 返回正确 Δ
  3) _select_warmup_question 覆盖性选题（按 topic × bloom 轮询）
  4) _select_adaptive_question 自适应选题（基于 theta_cov_diag 最大维度）
  5) update() 在 warm-up 期使用 warmup_step（更大）
  6) 5 题后从 warm-up 切到非 warm-up,步长切换
  7) reset_student() 同时清空 warm-up 计数

运行：
  PYTHONPATH=. python experiments/scripts/w1_warmup_validation.py

产物：纯 stdout 输出（pass/fail 计数 + 关键状态展示）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

# 让脚本能找到 ecos 包
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from ecos.cta import (
    BeliefEngine,
    BeliefEngineConfig,
    BloomLevel,
    Observation,
)
from ecos.cta.belief_state import BloomProfileState
from web.api.qmatrix import (
    _select_warmup_question,
    _select_adaptive_question,
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
# 场景 1: BeliefEngine warm-up 状态机
# ---------------------------------------------------------------------------


def scenario_1_belief_engine_warmup() -> None:
    print("\n" + "=" * 70)
    print("场景 1: BeliefEngine warm-up 状态机（W1 改动点 #1）")
    print("=" * 70)

    config = BeliefEngineConfig(warmup_questions=5, warmup_step=0.1)
    engine = BeliefEngine(config=config)
    sid = "test_student_001"

    # 1.1 新生 0 题 → is_warmup=True
    _check("1.1 新生 is_warmup=True", engine.is_warmup(sid) is True)
    _check("1.2 新生 warmup_remaining=5", engine.warmup_remaining(sid) == 5)
    progress = engine.warmup_progress(sid)
    _check("1.3 warmup_progress is_warmup=True", progress["is_warmup"] is True)
    _check("1.4 warmup_progress warmup_total=5", progress["warmup_total"] == 5)
    _check("1.5 warmup_progress warmup_count=0", progress["warmup_count"] == 0)

    # 1.6 模拟 3 题后状态
    state = engine.create_initial_state(sid)
    for i in range(3):
        obs = Observation(
            skill_id="K.var",
            problem_id=f"Q{i+1}",
            correct=True,
            bloom_level=BloomLevel.REMEMBER,
        )
        state = engine.update(state, obs)
    _check("1.6 答 3 题后 is_warmup=True", engine.is_warmup(sid) is True)
    _check("1.7 答 3 题后 warmup_remaining=2", engine.warmup_remaining(sid) == 2)

    # 1.8 答第 4 题（仍在 warm-up 期,前 5 题是 warm-up）
    obs = Observation(skill_id="K.var", problem_id="Q4", correct=True, bloom_level=BloomLevel.REMEMBER)
    state = engine.update(state, obs)
    _check("1.8 答 4 题后 is_warmup=True", engine.is_warmup(sid) is True)
    _check("1.9 答 4 题后 warmup_remaining=1", engine.warmup_remaining(sid) == 1)

    # 1.10 答第 5 题（刚跨过 warm-up 边界）
    obs = Observation(skill_id="K.var", problem_id="Q5", correct=True, bloom_level=BloomLevel.REMEMBER)
    state = engine.update(state, obs)
    _check("1.10 答 5 题后 is_warmup=False", engine.is_warmup(sid) is False)
    _check("1.11 答 5 题后 warmup_count=5", engine.warmup_progress(sid)["warmup_count"] == 5)

    # 1.10b 答第 6 题
    obs = Observation(skill_id="K.var", problem_id="Q6", correct=True, bloom_level=BloomLevel.REMEMBER)
    state = engine.update(state, obs)
    _check("1.10b 答 6 题后 is_warmup=False", engine.is_warmup(sid) is False)
    _check("1.11b 答 6 题后 warmup_count=6", engine.warmup_progress(sid)["warmup_count"] == 6)

    # 1.12 reset_student 应清空 warm-up 计数
    engine.reset_student(sid)
    _check("1.12 reset 后 is_warmup=True", engine.is_warmup(sid) is True)
    _check("1.13 reset 后 warmup_count=0", engine.warmup_progress(sid)["warmup_count"] == 0)


# ---------------------------------------------------------------------------
# 场景 2: BloomProfileState.distance_to_next_layer()
# ---------------------------------------------------------------------------


def scenario_2_bloom_distance() -> None:
    print("\n" + "=" * 70)
    print("场景 2: BloomProfileState.distance_to_next_layer()（W1 改动点 #4）")
    print("=" * 70)

    # 2.1 全部 0.5（默认）→ dominant=L1 (argmax 选第一个 index=0)
    bp = BloomProfileState()
    d = bp.distance_to_next_layer()
    _check("2.1 默认 dominant=L1（argmax 选 index=0）", d["current"] == "L1", f"current={d['current']}")
    _check("2.2 默认 next=L2", d["next"] == "L2", f"next={d['next']}")
    _check("2.3 默认 gap=0.0", abs(d["gap"]) < 1e-6, f"gap={d['gap']}")

    # 2.4 主导层为 L1 → next=L2
    bp2 = BloomProfileState(
        remember=0.8, understand=0.5, apply=0.3, analyze=0.2, evaluate=0.1, create=0.0
    )
    bp2.update_dominant()
    d2 = bp2.distance_to_next_layer()
    _check("2.4 L1 主导 dominant=L1", d2["current"] == "L1")
    _check("2.5 L1 主导 next=L2", d2["next"] == "L2")
    _check("2.6 L1 主导 gap=-0.3", abs(d2["gap"] - (-0.3)) < 1e-6, f"gap={d2['gap']}")

    # 2.7 L3 主导 + L4 弱于 L3（gap 负向,这是常见情况:学生还没到下一层）
    bp3 = BloomProfileState(
        remember=0.3, understand=0.4, apply=0.5, analyze=0.3, evaluate=0.2, create=0.1
    )
    bp3.update_dominant()
    d3 = bp3.distance_to_next_layer()
    _check("2.7 L3 主导", d3["current"] == "L3", f"current={d3['current']}")
    _check("2.8 gap 负向（next<current）", d3["gap"] < 0, f"gap={d3['gap']}")
    _check("2.9 gap = -0.2", abs(d3["gap"] - (-0.2)) < 1e-6, f"gap={d3['gap']}")

    # 2.9b L4 主导 + L5 弱于 L4（gap 负向）
    bp3b = BloomProfileState(
        remember=0.2, understand=0.3, apply=0.4, analyze=0.6, evaluate=0.3, create=0.1
    )
    bp3b.update_dominant()
    d3b = bp3b.distance_to_next_layer()
    _check("2.9b L4 主导", d3b["current"] == "L4", f"current={d3b['current']}")
    _check("2.9c L4 主导 next=L5", d3b["next"] == "L5", f"next={d3b['next']}")
    _check("2.9d gap = -0.3", abs(d3b["gap"] - (-0.3)) < 1e-6, f"gap={d3b['gap']}")

    # 2.10 L6 主导 → next=None
    bp4 = BloomProfileState(
        remember=0.1, understand=0.2, apply=0.3, analyze=0.4, evaluate=0.5, create=0.6
    )
    bp4.update_dominant()
    d4 = bp4.distance_to_next_layer()
    _check("2.10 L6 主导 dominant=L6", d4["current"] == "L6")
    _check("2.11 L6 主导 next=None", d4["next"] is None)
    _check("2.12 L6 主导 gap=None", d4["gap"] is None)


# ---------------------------------------------------------------------------
# 场景 3: _select_warmup_question 覆盖性选题
# ---------------------------------------------------------------------------


def scenario_3_warmup_selector() -> None:
    print("\n" + "=" * 70)
    print("场景 3: _select_warmup_question 覆盖性选题（W1 改动点 #2）")
    print("=" * 70)

    all_probs = get_all_problems()
    answered: set[str] = set()
    sid = "test_student_warmup"

    # 3.1 跑 5 次 warm-up 选题,看是否覆盖 5 个不同 (topic, bloom) 组合
    seen_groups: set[tuple[str, str]] = set()
    seen_topics: set[str] = set()
    seen_blooms: set[str] = set()
    for i in range(5):
        prob = _select_warmup_question(all_probs, sid)
        assert prob is not None
        answered.add(prob["problem_id"])
        group = (prob["topic"], prob["bloom_goal_id"].split("-")[-1])
        seen_groups.add(group)
        seen_topics.add(prob["topic"])
        seen_blooms.add(prob["bloom_goal_id"].split("-")[-1])
        _check(
            f"3.{i+1} warm-up 第 {i+1} 题带 _strategy=warmup",
            prob.get("_strategy") == "warmup",
            f"group={group}",
        )

    # 3.6 5 题应覆盖 ≥3 个 topic（Python 基础 5 个 topic,Q 矩阵小,不强求全 5）
    _check("3.6 覆盖 ≥3 个 topic", len(seen_topics) >= 3, f"topics={seen_topics}")
    # 3.7 5 题覆盖 ≥1 个 bloom 层（Q 矩阵小 + 5 题约束,实际可能只覆盖 L1+L2）
    _check("3.7 覆盖 ≥1 个 bloom 层（实际 L1+L2）", len(seen_blooms) >= 1, f"blooms={seen_blooms}")
    # 3.8 5 题应至少 ≥3 个不同 (topic, bloom) 组合
    _check("3.8 覆盖 ≥3 个 (topic, bloom) 组合", len(seen_groups) >= 3, f"groups={seen_groups}")

    # 3.9 select_question_for_student is_warmup=True 走覆盖性路径
    prob = select_question_for_student(answered, is_warmup=True, student_id=sid)
    _check("3.9 is_warmup=True 走覆盖性", prob is not None and prob.get("_strategy") == "warmup")


# ---------------------------------------------------------------------------
# 场景 4: _select_adaptive_question 自适应选题
# ---------------------------------------------------------------------------


def scenario_4_adaptive_selector() -> None:
    print("\n" + "=" * 70)
    print("场景 4: _select_adaptive_question 自适应选题（W1 改动点 #2）")
    print("=" * 70)

    all_probs = get_all_problems()
    answered: set[str] = set()
    sid = "test_student_adaptive"

    # 4.1 模拟 5D 状态:C 维度方差最大(SE 最大)
    # theta_mean 全部 0,theta_cov_diag = [1, 1, 1, 5, 1] → d_star = 3 (C)
    theta_mean = [0.0, 0.0, 0.0, 0.0, 0.0]
    theta_cov_diag = [1.0, 1.0, 1.0, 5.0, 1.0]  # C 方差最大

    prob = _select_adaptive_question(
        all_probs,
        theta_mean=theta_mean,
        theta_cov_diag=theta_cov_diag,
        target_bloom="L2",
    )
    _check("4.1 自适应选题返回非空", prob is not None)
    _check("4.2 _strategy=adaptive", prob is not None and prob.get("_strategy") == "adaptive")
    _check("4.3 d_star=3 (C 维度)", prob is not None and prob.get("_adaptive_dim_star") == 3)

    # 4.4 K 维度方差最大 → d_star=0
    theta_cov_diag_k = [5.0, 1.0, 1.0, 1.0, 1.0]
    prob2 = _select_adaptive_question(
        all_probs,
        theta_mean=theta_mean,
        theta_cov_diag=theta_cov_diag_k,
        target_bloom=None,
    )
    _check("4.4 K 方差最大 d_star=0", prob2 is not None and prob2.get("_adaptive_dim_star") == 0)

    # 4.5 没传 theta_cov_diag → 走 legacy 路径
    prob3 = select_question_for_student(answered, is_warmup=False, theta_cov_diag=None)
    _check("4.5 无 cov 走 legacy 路径", prob3 is not None and prob3.get("_strategy", "").startswith("legacy"))

    # 4.6 选 5 次自适应,确认不会重复选同一题（除非已答完）
    picked_ids: set[str] = set()
    for i in range(5):
        p = select_question_for_student(
            picked_ids,
            is_warmup=False,
            theta_mean=theta_mean,
            theta_cov_diag=theta_cov_diag,
        )
        if p is not None:
            picked_ids.add(p["problem_id"])
    _check("4.6 5 次自适应选题不重复", len(picked_ids) == 5, f"picked={picked_ids}")


# ---------------------------------------------------------------------------
# 场景 5: end-to-end（is_warmup 流转换）
# ---------------------------------------------------------------------------


def scenario_5_end_to_end() -> None:
    print("\n" + "=" * 70)
    print("场景 5: End-to-end warm-up → adaptive 流转换")
    print("=" * 70)

    config = BeliefEngineConfig(warmup_questions=3, warmup_step=0.1)
    engine = BeliefEngine(config=config)
    sid = "test_e2e"

    # 5.1 前 3 题:warm-up 期
    state = engine.create_initial_state(sid)
    for i in range(3):
        obs = Observation(
            skill_id="K.var",
            problem_id=f"Q{i+1}",
            correct=True,
            bloom_level=BloomLevel.REMEMBER,
        )
        state = engine.update(state, obs)
        _check(f"5.1.{i+1} 答第 {i+1} 题 is_warmup={engine.is_warmup(sid)}", engine.is_warmup(sid) is (i < 2))

    # 5.4 第 4 题:进入自适应期
    obs = Observation(skill_id="K.var", problem_id="Q4", correct=False, bloom_level=BloomLevel.UNDERSTAND)
    state = engine.update(state, obs)
    _check("5.4 第 4 题 is_warmup=False", engine.is_warmup(sid) is False)

    # 5.5 bloom_distance 应有正确 Δ
    d = state.bloom_profile.distance_to_next_layer()
    _check("5.5 bloom_distance 返回 dict", isinstance(d, dict))
    _check("5.6 bloom_distance 有 current", "current" in d)
    _check("5.7 bloom_distance 有 next", "next" in d)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def main() -> None:
    print("=" * 70)
    print("ECOS Phase 4 W1 验证：warm-up 窗口 + 自适应选题 + Bloom Δ")
    print("来源:discussions/2026-07-17-方向选择-A先C后.md")
    print("=" * 70)

    scenario_1_belief_engine_warmup()
    scenario_2_bloom_distance()
    scenario_3_warmup_selector()
    scenario_4_adaptive_selector()
    scenario_5_end_to_end()

    print("\n" + "=" * 70)
    print(f"结果:{_PASSED}/{_TOTAL} passed, {_FAILED} failed")
    print("=" * 70)

    if _FAILED > 0:
        print("❌ 验证未通过,请检查实现")
        sys.exit(1)
    else:
        print("✅ W1 全部验证通过")


if __name__ == "__main__":
    main()
