"""M2 W1 CTA 基础骨架验证脚本.

对应：
  - research/90-mvp/README.md §2.1 (Week 1: CTA + LCA 基础)
  - research/10-engineering/01-cta-belief-engine.md §2.3 (BeliefEngine)

目的：
  在合成数据上验证 CTA 5D BeliefState + BKT + 5D MIRT(MAP) 骨架：
  1) BKT 单知识点掌握概率是否随正确/错误观测合理演化
  2) MIRT MAP 估计能否在 50 道题后接近学生真实能力
  3) BloomProfile 6 层分布是否反映题目 Bloom 层级分布

运行：
  PYTHONPATH=. python experiments/scripts/m2_w1_cta_basics_validation.py

产物：纯 stdout 输出（M2 W1 不写文件，避免污染 git）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

# 让脚本能找到 ecos 包
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from ecos.cta import (  # noqa: E402
    BeliefEngine,
    BeliefEngineConfig,
    BloomLevel,
    BKTParams,
    EvolutionConfig,
    MIRTConfig,
    MIRTItemParams,
    Observation,
)


# ---------------------------------------------------------------------------
# 合成数据：item → skill / bloom 映射（与 items 列表顺序对应）
# ---------------------------------------------------------------------------

_SKILL_MAP: dict[str, str] = {
    "Q01": "K.quadratic", "Q02": "K.quadratic", "Q03": "K.quadratic",
    "Q04": "K.linear", "Q05": "K.linear",
    "Q06": "P.arithmetic", "Q07": "P.arithmetic",
    "Q08": "S.problem_solving", "Q09": "S.problem_solving",
}

_BLOOM_MAP: dict[str, BloomLevel] = {
    "Q01": BloomLevel.REMEMBER, "Q02": BloomLevel.APPLY, "Q03": BloomLevel.ANALYZE,
    "Q04": BloomLevel.REMEMBER, "Q05": BloomLevel.APPLY,
    "Q06": BloomLevel.REMEMBER, "Q07": BloomLevel.APPLY,
    "Q08": BloomLevel.APPLY, "Q09": BloomLevel.ANALYZE,
}


def synth_responses(
    true_theta: np.ndarray,
    item_params_list: list[MIRTItemParams],
    rng: np.random.Generator,
) -> np.ndarray:
    """按 5D MIRT 模型生成学生作答序列.

    P(correct | θ, item) = sigmoid(a_sp · θ + a_g · mean(θ) - d)
    """
    responses = np.empty(len(item_params_list), dtype=int)
    for i, item in enumerate(item_params_list):
        g = float(np.mean(true_theta))
        logit = float(np.dot(item.a_specialized, true_theta)) + item.a_general * g - item.difficulty
        p = 1.0 / (1.0 + np.exp(-logit))
        responses[i] = int(rng.random() < p)
    return responses


def make_item(
    problem_id: str,
    a_sp: np.ndarray,
    a_g: float,
    difficulty: float,
) -> MIRTItemParams:
    return MIRTItemParams(
        problem_id=problem_id,
        a_specialized=a_sp,
        a_general=a_g,
        difficulty=difficulty,
    )


def build_items() -> list[MIRTItemParams]:
    """构造 9 个 item 模板（4 知识点 × 3 Bloom 层）。"""
    return [
        # K.quadratic 偏 K/P 维度
        make_item("Q01", np.array([1.0, 0.4, 0.1, 0.1, 0.0]), a_g=0.3, difficulty=-0.5),
        make_item("Q02", np.array([1.2, 0.8, 0.2, 0.1, 0.0]), a_g=0.3, difficulty=0.3),
        make_item("Q03", np.array([1.4, 1.0, 0.4, 0.2, 0.0]), a_g=0.3, difficulty=1.0),
        # K.linear 偏 K
        make_item("Q04", np.array([0.9, 0.3, 0.1, 0.0, 0.0]), a_g=0.3, difficulty=-0.8),
        make_item("Q05", np.array([1.1, 0.6, 0.2, 0.1, 0.0]), a_g=0.3, difficulty=0.0),
        # P.arithmetic 偏 P
        make_item("Q06", np.array([0.3, 1.0, 0.2, 0.0, 0.0]), a_g=0.3, difficulty=-0.6),
        make_item("Q07", np.array([0.5, 1.2, 0.3, 0.1, 0.0]), a_g=0.3, difficulty=0.2),
        # S.problem_solving 偏 S
        make_item("Q08", np.array([0.4, 0.3, 1.1, 0.2, 0.0]), a_g=0.3, difficulty=0.5),
        make_item("Q09", np.array([0.5, 0.4, 1.3, 0.3, 0.0]), a_g=0.3, difficulty=1.2),
    ]


# ---------------------------------------------------------------------------
# 主验证流程
# ---------------------------------------------------------------------------

def main() -> int:
    rng = np.random.default_rng(seed=20260703)

    # 学生真实 5D 能力（中等偏上 K/P，较弱 S/C/X）
    true_theta = np.array([1.5, 1.2, 0.5, 0.8, 0.3])

    items = build_items()
    skills = sorted(set(_SKILL_MAP.values()))
    bloom_levels = sorted(set(_BLOOM_MAP.values()), key=lambda b: b.value)

    # 生成 50 道题作答序列（循环使用 9 个 item 模板）
    seq = [items[i % len(items)] for i in range(50)]
    responses = synth_responses(true_theta, seq, rng)

    # ---------------- CTA 引擎初始化 ----------------
    evolution_config = EvolutionConfig(
        default_params=BKTParams(p_init=0.2, p_learn=0.15, p_guess=0.2, p_slip=0.1),
    )
    mirt_config = MIRTConfig(
        prior_mean=np.zeros(5),
        prior_cov=np.eye(5),
        default_a_specialized=np.ones(5) * 0.7,
        default_a_general=0.3,
    )
    engine_config = BeliefEngineConfig(
        evolution_config=evolution_config,
        mirt_config=mirt_config,
        bloom_update_step=0.04,
    )
    engine = BeliefEngine(engine_config)
    engine.l2.register_items_bulk(items)

    state = engine.create_initial_state(student_id="synthetic_001")

    # ---------------- 模拟 50 步 ----------------
    accuracy_log: list[bool] = []

    for item, correct in zip(seq, responses):
        obs = Observation(
            skill_id=_SKILL_MAP[item.problem_id],
            problem_id=item.problem_id,
            correct=bool(correct),
            bloom_level=_BLOOM_MAP[item.problem_id],
        )
        state = engine.update(state, obs)
        accuracy_log.append(bool(correct))

    # ---------------- 输出报告 ----------------
    print("=" * 78)
    print("M2 W1 CTA 基础骨架验证报告")
    print("=" * 78)
    print(f"\n学生 synthetic_001：真实 5D θ = {true_theta.round(3).tolist()}")
    print(f"模拟 {len(seq)} 道题（{len(items)} 个 item 模板循环）")
    print(f"整体准确率：{np.mean(accuracy_log):.2%}")

    print("\n--- 1. BKT 单知识点掌握概率演化（最终值） ---")
    print(f"{'知识点':<25} {'初始':>8} {'最终':>8} {'增量':>8}")
    print("-" * 50)
    p_init = engine_config.evolution_config.default_params.p_init
    for s in skills:
        p_end = engine.get_bkt_mastery(s)
        n_touch = sum(1 for it in seq if _SKILL_MAP[it.problem_id] == s)
        print(f"{s:<25} {p_init:>8.3f} {p_end:>8.3f} {p_end - p_init:>+8.3f} (n={n_touch})")

    print("\n--- 2. MIRT 5D θ 估计 vs 真实 θ ---")
    print(f"{'维度':<6} {'真实':>8} {'初始':>8} {'最终':>8} {'误差':>8}")
    print("-" * 42)
    for i, dim in enumerate(["K", "P", "S", "C", "X"]):
        print(f"{dim:<6} {true_theta[i]:>+8.3f} {0.0:>+8.3f} "
              f"{state.theta_mean[i]:>+8.3f} {state.theta_mean[i] - true_theta[i]:>+8.3f}")

    print("\n--- 3. BloomProfile 6 层最终分布 ---")
    print(f"{'层级':<12} {'概率':>8}")
    print("-" * 22)
    for b in bloom_levels:
        p = getattr(state.bloom_profile, b.name.lower())
        marker = " ◀ dominant" if state.bloom_profile.dominant_layer == b else ""
        print(f"{b.name:<12} {p:>8.3f}{marker}")
    print(f"  overall_confidence = {state.overall_confidence:.3f}")

    print("\n--- 4. 轨迹长度 ---")
    print(f"trajectory.snapshots 数量 = {len(state.trajectory.snapshots)}")

    print("\n--- 5. 关键 sanity check ---")
    sanity_pass = True
    for s in skills:
        p = engine.get_bkt_mastery(s)
        if not (0.0 <= p <= 1.0):
            print(f"  ❌ BKT[{s}] = {p} 超出 [0,1]")
            sanity_pass = False
    for b in bloom_levels:
        p = getattr(state.bloom_profile, b.name.lower())
        if not (0.0 <= p <= 1.0):
            print(f"  ❌ BloomProfile[{b.name}] = {p} 超出 [0,1]")
            sanity_pass = False
    eigvals = np.linalg.eigvalsh(state.theta_cov)
    if np.any(eigvals <= 0):
        print(f"  ❌ theta_cov 非正定：最小特征值 = {eigvals.min():.6f}")
        sanity_pass = False
    if len(state.trajectory.snapshots) != len(seq):
        print(f"  ❌ trajectory 长度 = {len(state.trajectory.snapshots)} 不等于观测次数 = {len(seq)}")
        sanity_pass = False
    if len(state.theta_vector()) != 5:
        print(f"  ❌ theta 向量长度 = {len(state.theta_vector())} 不等于 5")
        sanity_pass = False

    if sanity_pass:
        print("  ✅ 所有 sanity check 通过")

    print("\n" + "=" * 78)
    print("验证完成")
    print("=" * 78)
    return 0 if sanity_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())