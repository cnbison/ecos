#!/usr/bin/env python3
"""Python 基础 BeliefEngine 追踪 Demo（M2 W6）。

目标：验证 Python 基础 Q 矩阵下，K/P/S 三维度是否分化。

流程：
  1. 加载 python_basics_q_matrix.json（16 道题）
  2. 注册所有题目到 BiFactorMIRT5D（使用差异化 a_specialized）
  3. 模拟学生答题序列（体现主题差异化）
  4. BeliefEngine.update() 追踪 5D θ 演化
  5. 验证 K/P/S 最大差异 > 0.15

对应：research/00-overview/03-roadmap.md §2.4 M2 W6
数据：data/python_basics_q_matrix.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig, Observation
from ecos.cta.belief_state import BloomLevel
from ecos.cta.l1_evolution import EvolutionConfig
from ecos.cta.l2_mirt import BiFactorMIRT5D, MIRTConfig, MIRTItemParams


def load_q_matrix(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def register_q_matrix(mirt: BiFactorMIRT5D, q_matrix: dict) -> None:
    """将 Q 矩阵题目注册到 MIRT."""
    for prob in q_matrix["problems"]:
        params = MIRTItemParams(
            problem_id=prob["problem_id"],
            a_specialized=np.array(prob["a_specialized"], dtype=float),
            a_general=0.5,
            difficulty=prob["mirt_params"]["difficulty"],
        )
        mirt.register_item(params)


def simulate_student_responses() -> list[tuple[str, bool, BloomLevel, str]]:
    """模拟学生答题序列。

    策略：
      - variables（L2）：前几题答对（K 维度上升），后来答错（L4 理解引用）
      - loops（S 主导）：L1-L2 答对，S 上升
      - functions（P 主导）：L3 答错，P 压制
      - recursion（S 主导）：L2 答对，S 上升
      - scope（P 主导）：L2 答对，P 上升

    预期：S > P > K（因为 S 主导题全对，P 主导题部分对，K 主导题有失误）
    """
    return [
        # variables L1 — 答对
        ("PB-Q01", True, BloomLevel.REMEMBER, "python.variables"),
        # variables L2 — 答对（理解赋值）
        ("PB-Q02", True, BloomLevel.UNDERSTAND, "python.variables"),
        # loops L1 — 答对
        ("PB-Q05", True, BloomLevel.REMEMBER, "python.loops"),
        # loops L2 — 答对（理解了 off-by-one）
        ("PB-Q06", True, BloomLevel.UNDERSTAND, "python.loops"),
        # recursion L1 — 答对
        ("PB-Q12", True, BloomLevel.REMEMBER, "python.recursion"),
        # recursion L2 — 答对（理解了递归≠循环）
        ("PB-Q13", True, BloomLevel.UNDERSTAND, "python.recursion"),
        # recursion L3 — 答对
        ("PB-Q14", True, BloomLevel.APPLY, "python.recursion"),
        # loops L3 — 答对
        ("PB-Q07", True, BloomLevel.APPLY, "python.loops"),
        # loops L4 — 答对（理解了死循环根源）
        ("PB-Q08", True, BloomLevel.ANALYZE, "python.loops"),
        # scope L2 — 答对
        ("PB-Q15", True, BloomLevel.UNDERSTAND, "python.scope"),
        # scope L3 — 答对
        ("PB-Q16", True, BloomLevel.APPLY, "python.scope"),
        # variables L3 — 答对
        ("PB-Q03", True, BloomLevel.APPLY, "python.variables"),
        # functions L1 — 答对
        ("PB-Q09", True, BloomLevel.REMEMBER, "python.functions"),
        # functions L2 — 答错！（触发 M4：函数必有返回值）
        ("PB-Q10", False, BloomLevel.UNDERSTAND, "python.functions"),
        # functions L3 — 答对
        ("PB-Q11", True, BloomLevel.APPLY, "python.functions"),
        # variables L4 — 答错（触发 M6：变量=盒子）
        ("PB-Q04", False, BloomLevel.ANALYZE, "python.variables"),
    ]


def run_tracking() -> dict:
    q_matrix_path = Path(__file__).parent.parent.parent / "data" / "python_basics_q_matrix.json"
    q_matrix = load_q_matrix(q_matrix_path)

    # 配置 MIRT（允许协方差矩阵自适应）
    mirt_config = MIRTConfig(
        prior_mean=np.zeros(5),
        prior_cov=np.eye(5),
        default_a_specialized=np.ones(5) * 0.8,
        default_a_general=0.5,
        default_difficulty=0.0,
    )

    # 构建 BeliefEngine（用同一 MIRT 实例）
    mirt = BiFactorMIRT5D(mirt_config)
    register_q_matrix(mirt, q_matrix)

    # 注入到 BeliefEngineConfig
    config = BeliefEngineConfig(
        evolution_config=EvolutionConfig(),
        mirt_config=mirt_config,
        bloom_update_step=0.05,
    )
    engine = BeliefEngine(config=config)
    # 直接用 MIRT 实例（绕过私有属性）
    engine.l2 = mirt

    # 初始状态
    student_id = "demo_python_belief"
    state = engine.create_initial_state(student_id)

    print("初始 θ:", np.round(state.theta_mean, 3))

    # 模拟答题
    responses = simulate_student_responses()
    trajectory = []

    for i, (prob_id, correct, bloom, skill_id) in enumerate(responses):
        obs = Observation(
            skill_id=skill_id,
            problem_id=prob_id,
            correct=correct,
            bloom_level=bloom,
        )
        state = engine.update(state, obs)
        theta = state.theta_mean
        trajectory.append({
            "step": i + 1,
            "prob_id": prob_id,
            "correct": correct,
            "bloom": bloom.name,
            "skill": skill_id,
            "theta": np.round(theta, 4).tolist(),
            "K": round(theta[0], 4),
            "P": round(theta[1], 4),
            "S": round(theta[2], 4),
        })

    return trajectory, state, q_matrix


def main() -> None:
    print("=" * 60)
    print("  Python 基础 BeliefEngine K/P/S 追踪 Demo")
    print("=" * 60)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    trajectory, final_state, q_matrix = run_tracking()

    # 打印演化轨迹
    print(f"\n{'步':>2} {'题目':<10} {'对?':>4} {'Bloom':<8} {'Skill':<18} {'K':>7} {'P':>7} {'S':>7}")
    print("-" * 75)
    for row in trajectory:
        print(
            f"{row['step']:>2} {row['prob_id']:<10} {str(row['correct']):>4} "
            f"{row['bloom']:<8} {row['skill']:<18} "
            f"{row['K']:>7.4f} {row['P']:>7.4f} {row['S']:>7.4f}"
        )

    # 最终状态
    theta = final_state.theta_mean
    dims = ["K", "P", "S", "C", "X"]
    print("\n" + "=" * 60)
    print("  最终 5D θ")
    print("=" * 60)
    for i, d in enumerate(dims):
        print(f"  {d}: {theta[i]:.4f}")

    # K/P/S 分化验证
    k, p, s = theta[0], theta[1], theta[2]
    max_diff = max(abs(k - p), abs(k - s), abs(p - s))
    print(f"\nK/P/S 最大差异: {max_diff:.4f}")
    if max_diff > 0.15:
        print("✅ K/P/S 维度成功分化（> 0.15）")
    else:
        print(f"⚠️  K/P/S 维度分化不足（≤ 0.15）")

    print(f"\nK={k:.3f}  P={p:.3f}  S={s:.3f}")

    # 保存轨迹
    output = {
        "timestamp": datetime.now().isoformat(),
        "student_id": "demo_python_belief",
        "trajectory": trajectory,
        "final_theta": {d: round(theta[i], 4) for i, d in enumerate(dims)},
        "k_p_s_max_diff": round(max_diff, 4),
    }
    out_path = Path(__file__).parent.parent.parent / "discussions" / "2026-07-06-python-basics-belief-tracking.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"\n轨迹已保存: {out_path}")


if __name__ == "__main__":
    main()
