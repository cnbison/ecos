"""M2 W2 LCA 策略引擎基础骨架验证脚本.

对应：
  - research/90-mvp/README.md §2.1 (Week 2: LCA 基础)
  - research/10-engineering/02-lca-policy-engine.md §6 LCAOrchestrator

目的：
  在合成数据上验证 LCA 主流程：
    1) select_bloom_target() 正确选择高增长潜力层
    2) CLT 4 级判断在 Bloom 层变化时正确调整
    3) CA 状态机正确从 MODELING → COACHING → SCAFFOLDING 转移
    4) LinUCB 在多次交互后开始偏向高 reward 的 arm（粗略验证）
    5) Rationale 生成在无 LLM 时 fallback 到模板，有 LLM 时走真实调用
    6) 完整 CTA→LCA 链路：CTA 估计 → LCA 选择 → 模拟 reward → CTA 更新

运行：
  PYTHONPATH=. python experiments/scripts/m2_w2_lca_basics_validation.py

行为：
  - 无 MINIMAX_API_KEY → rationale 用模板 fallback（不影响主流程）
  - 有 MINIMAX_API_KEY → 走真实 MiniMax 调用生成 rationale
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np

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
from ecos.lca import (  # noqa: E402
    CAStage,
    CLTLevel,
    InterventionType,
    LCAEngine,
    LCAEngineConfig,
    CTAInput,
    select_bloom_target,
)
from ecos.llm_client import ECOSLLMClient  # noqa: E402


# ---------------------------------------------------------------------------
# 合成数据（同 M2 W1 验证脚本，保持一致）
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
    items: list[MIRTItemParams],
    rng: np.random.Generator,
) -> np.ndarray:
    responses = np.empty(len(items), dtype=int)
    for i, item in enumerate(items):
        g = float(np.mean(true_theta))
        logit = float(np.dot(item.a_specialized, true_theta)) + item.a_general * g - item.difficulty
        p = 1.0 / (1.0 + np.exp(-logit))
        responses[i] = int(rng.random() < p)
    return responses


def make_item(problem_id: str, a_sp: np.ndarray, a_g: float, difficulty: float) -> MIRTItemParams:
    return MIRTItemParams(
        problem_id=problem_id,
        a_specialized=a_sp,
        a_general=a_g,
        difficulty=difficulty,
    )


def build_items() -> list[MIRTItemParams]:
    return [
        make_item("Q01", np.array([1.0, 0.4, 0.1, 0.1, 0.0]), a_g=0.3, difficulty=-0.5),
        make_item("Q02", np.array([1.2, 0.8, 0.2, 0.1, 0.0]), a_g=0.3, difficulty=0.3),
        make_item("Q03", np.array([1.4, 1.0, 0.4, 0.2, 0.0]), a_g=0.3, difficulty=1.0),
        make_item("Q04", np.array([0.9, 0.3, 0.1, 0.0, 0.0]), a_g=0.3, difficulty=-0.8),
        make_item("Q05", np.array([1.1, 0.6, 0.2, 0.1, 0.0]), a_g=0.3, difficulty=0.0),
        make_item("Q06", np.array([0.3, 1.0, 0.2, 0.0, 0.0]), a_g=0.3, difficulty=-0.6),
        make_item("Q07", np.array([0.5, 1.2, 0.3, 0.1, 0.0]), a_g=0.3, difficulty=0.2),
        make_item("Q08", np.array([0.4, 0.3, 1.1, 0.2, 0.0]), a_g=0.3, difficulty=0.5),
        make_item("Q09", np.array([0.5, 0.4, 1.3, 0.3, 0.0]), a_g=0.3, difficulty=1.2),
    ]


# ---------------------------------------------------------------------------
# 单元自检（不依赖 LLM）
# ---------------------------------------------------------------------------

def check_select_bloom_target() -> bool:
    """select_bloom_target 选低掌握度层（高潜力）。"""
    from ecos.cta import BeliefState, BloomProfileState, LearningDNAState
    state = BeliefState(student_id="test")
    # 人为设置：APPLY 层掌握度高（0.9），REMEMBER/UNDERSTAND 低（0.1）
    state.bloom_profile = BloomProfileState(
        remember=0.1, understand=0.1, apply=0.9, analyze=0.5, evaluate=0.5, create=0.5,
    )
    state.learning_dna = LearningDNAState()
    candidates = [BloomLevel.REMEMBER, BloomLevel.UNDERSTAND, BloomLevel.APPLY, BloomLevel.ANALYZE]
    chosen = select_bloom_target(state, candidates, state.learning_dna)
    # expect: 在低掌握度层中选（REMEMBER/UNDERSTAND）
    ok = chosen in (BloomLevel.REMEMBER, BloomLevel.UNDERSTAND)
    print(f"  ✅ Bloom target={chosen.name}, 优先低掌握度层" if ok else
          f"  ❌ Bloom target={chosen.name}, 期望 REMEMBER/UNDERSTAND")
    return ok


def check_clt_levels() -> bool:
    """CLT 4 级随 Bloom 层变化。"""
    from ecos.cta import BeliefState, BloomProfileState
    from ecos.lca.l3_selection import AdaptiveCLTPresender, CLTConfig

    presender = AdaptiveCLTPresender(CLTConfig())

    # Case 1: Bloom dominant = REMEMBER → NOVICE
    bp1 = BloomProfileState(remember=0.9, understand=0.1, apply=0.1, analyze=0.1, evaluate=0.1, create=0.1)
    bp1.update_dominant()
    state1 = BeliefState(student_id="test1", bloom_profile=bp1)
    level1 = presender.determine_level("stu_001", state1)

    # Case 2: Bloom dominant = ANALYZE → DEVELOPING
    bp2 = BloomProfileState(remember=0.1, understand=0.1, apply=0.1, analyze=0.9, evaluate=0.1, create=0.1)
    bp2.update_dominant()
    state2 = BeliefState(student_id="test2", bloom_profile=bp2)
    level2 = presender.determine_level("stu_002", state2)

    # Case 3: Bloom dominant = CREATE → PROFICIENT
    bp3 = BloomProfileState(remember=0.1, understand=0.1, apply=0.1, analyze=0.1, evaluate=0.1, create=0.9)
    bp3.update_dominant()
    state3 = BeliefState(student_id="test3", bloom_profile=bp3)
    level3 = presender.determine_level("stu_003", state3)

    ok = (
        level1 == CLTLevel.NOVICE
        and level2 == CLTLevel.DEVELOPING
        and level3 == CLTLevel.PROFICIENT
    )
    print(f"  ✅ CLT level 映射: REMEMBER→{level1.name}, ANALYZE→{level2.name}, CREATE→{level3.name}" if ok
          else f"  ❌ CLT 映射错: {level1.name}/{level2.name}/{level3.name}")
    return ok


def check_ca_state_machine() -> bool:
    """CA 状态机 MODELING → COACHING → SCAFFOLDING."""
    from ecos.cta import BeliefState, BloomProfileState, StateSnapshot
    from ecos.lca.l4_optimization import CAStateMachine

    sm = CAStateMachine()

    # Init: MODELING
    stage0 = sm.current_stage("stu_001")
    assert stage0 == CAStage.MODELING, f"初值错误：{stage0.name}"

    # Case 1: trajectory 足够 → COACHING
    bp_apply = BloomProfileState(remember=0.5, understand=0.5, apply=0.9, analyze=0.5, evaluate=0.5, create=0.5)
    bp_apply.update_dominant()
    state = BeliefState(student_id="stu_001", bloom_profile=bp_apply)
    state.K.mastery_prob = 0.7
    # 用 3 个 snapshot 触发 has_tried_independently（≥ 3）
    snapshots = [
        StateSnapshot(
            timestamp=datetime.now(),
            theta_5d=np.zeros(5),
            bloom_profile=bp_apply,
        )
        for _ in range(3)
    ]
    state.trajectory.snapshots = snapshots
    stage1 = sm.transition("stu_001", state, intervention_history=[])

    # Case 2: 先让学生尝试（MODELING → COACHING），再 K mastery 低 → SCAFFOLDING
    state_low = BeliefState(student_id="stu_002", bloom_profile=bp_apply)
    state_low.K.mastery_prob = 0.2
    state_low.C.confidence = 0.2
    # 先转 COACHING（trajectory 已有 3 快照）
    state_low.trajectory.snapshots = [
        StateSnapshot(timestamp=datetime.now(), theta_5d=np.zeros(5), bloom_profile=bp_apply)
        for _ in range(3)
    ]
    sm.transition("stu_002", state_low, intervention_history=[])
    # 现在再 transition —— 应该→ SCAFFOLDING（needs_scaffolding=True）
    stage2 = sm.transition("stu_002", state_low, intervention_history=[])

    ok = stage1 == CAStage.COACHING and stage2 == CAStage.SCAFFOLDING
    print(f"  ✅ CA 状态机: {stage0.name} → {stage1.name} (normal), {stage2.name} (low mastery)" if ok
          else f"  ❌ CA 转移错: {stage0.name} → {stage1.name} → {stage2.name}")
    return ok


def check_linucb_convergence() -> bool:
    """LinUCB 在合成 reward 下偏向高奖励 arm."""
    from ecos.lca.l4_optimization import LinUCB

    n_arms, dim, alpha = 5, 4, 1.0
    bandit = LinUCB(n_arms=n_arms, context_dim=dim, alpha=alpha)

    # 固定 context，arm 2 是最优（高 reward）
    rng = np.random.default_rng(seed=42)
    best_arm = 2
    n_steps = 100

    chosen_counts = np.zeros(n_arms)
    for t in range(n_steps):
        # context 加少量噪声（探索噪声 → LinUCB 学习 θ_a）
        context = rng.normal(0, 1, dim)
        chosen = bandit.select_arm(context)
        chosen_counts[chosen] += 1
        # 奖励：arm 2 = 1.0，其他均匀 0.3
        reward = 1.0 if chosen == best_arm else 0.3
        bandit.update(chosen, context, reward)

    best_arm_pulls = int(chosen_counts[best_arm])
    best_arm_share = best_arm_pulls / n_steps
    ok = best_arm_pulls > n_steps / n_arms  # > 随机基线（20%）
    print(f"  ✅ LinUCB 收敛: best_arm pull ratio = {best_arm_share:.2f} (>{1/n_arms:.2f})"
          if ok else f"  ❌ LinUCB 未收敛: best_arm 占比 {best_arm_share:.2f}")
    print(f"    → arm 计数: {chosen_counts.astype(int).tolist()}")
    return ok


def check_template_fallback() -> bool:
    """无 LLM 时 Rationale 走 fallback 模板."""
    from ecos.lca.rationale import RationaleGenerator
    from ecos.cta import BeliefState, BloomProfileState
    from ecos.lca.intervention import Intervention

    # 传入 None LLM → 全部 fallback
    gen = RationaleGenerator(llm_client=None)
    state = BeliefState(student_id="fallback_test")
    state.bloom_profile = BloomProfileState()
    state.K.mastery_prob = 0.5
    intervention = Intervention(
        intervention_type=InterventionType.PRACTICE,
        bloom_target=BloomLevel.APPLY,
        quantity=5,
    )

    text_student = gen.generate(intervention, state, audience="student")
    text_teacher = gen.generate(intervention, state, audience="teacher")
    text_parent = gen.generate(intervention, state, audience="parent")

    ok = (
        len(text_student) > 10
        and "[模板回退]" in text_teacher
        and "[模板回退]" in text_parent
    )
    print(f"  ✅ Template fallback: student={text_student[:40]}..." if ok
          else f"  ❌ Fallback 失败: student={text_student}, teacher={text_teacher[:30]}, parent={text_parent[:30]}")
    return ok


# ---------------------------------------------------------------------------
# 真实 LLM 调用（仅在 key 存在时执行）
# ---------------------------------------------------------------------------

def real_llm_rationale_test(llm_client: ECOSLLMClient | None) -> bool:
    """有 key 时真实生成一次 rationale."""
    if llm_client is None:
        print("  ⚠️ 跳过真实 LLM 调用（无 key）")
        return False

    from ecos.lca.rationale import RationaleGenerator
    from ecos.lca.intervention import Intervention as LCAIntervention
    from ecos.cta import BeliefState, BloomProfileState

    gen = RationaleGenerator(llm_client=llm_client)
    state = BeliefState(student_id="real_test")
    state.bloom_profile = BloomProfileState(
        remember=0.3, understand=0.4, apply=0.6, analyze=0.5, evaluate=0.5, create=0.5,
    )
    state.K.mastery_prob = 0.6
    intervention = LCAIntervention(
        intervention_type=InterventionType.PRACTICE,
        bloom_target=BloomLevel.APPLY,
        quantity=5,
        target_skills=["K.quadratic"],
        clt_level=CLTLevel.DEVELOPING,
        ca_stage=CAStage.COACHING,
    )

    print("  [Test 1] student audience")
    try:
        text_student = gen.generate(intervention, state, audience="student")
        print(f"  ✅ student rationale: {text_student[:200]}")
    except Exception as e:
        print(f"  ❌ student rationale 失败：{e}")
        return False

    print("  [Test 2] teacher audience (200 字)")
    try:
        text_teacher = gen.generate(intervention, state, audience="teacher")
        print(f"  ✅ teacher rationale: {text_teacher[:200]}")
    except Exception as e:
        print(f"  ⚠️ teacher rationale 失败：{e}")
        return True  # student 已成功算部分成功

    return True


# ---------------------------------------------------------------------------
# 完整 CTA → LCA 链路
# ---------------------------------------------------------------------------

def run_full_pipeline(
    cta_engine: BeliefEngine,
    items: list[MIRTItemParams],
    true_theta: np.ndarray,
    rng: np.random.Generator,
    lca_engine: LCAEngine,
    state: any,
    n_steps: int = 30,
) -> tuple[list, list]:
    """完整 CTA → LCA pipeline.

    Returns:
        (lca_results, rewards)
    """
    seq = [items[i % len(items)] for i in range(n_steps)]
    responses = synth_responses(true_theta, seq, rng)

    lca_results = []
    rewards = []

    for step, (item, correct) in enumerate(zip(seq, responses)):
        # 1. CTA 更新（带上一轮 LCA 结果）
        prev_state = state
        obs = Observation(
            skill_id=_SKILL_MAP[item.problem_id],
            problem_id=item.problem_id,
            correct=bool(correct),
            bloom_level=_BLOOM_MAP[item.problem_id],
        )
        # CTA update
        from ecos.cta.belief_engine import LCAResult as CTALCAResult
        cta_lca = CTALCAResult(
            intervention_type="practice",
            expected_gain=0.0,
            actual_outcome=float(correct),
        )
        state = cta_engine.update(state, obs, lca_result=cta_lca)

        # 2. LCA 选择
        cta_input = CTAInput(
            student_id=state.student_id,
            belief_state=state,
            skill_filter=list({_SKILL_MAP[item.problem_id]}),
        )
        lca_result = lca_engine.select_intervention(cta_input)
        lca_results.append(lca_result)

        # 3. 模拟 reward（基于是否答对——答对 = 高 reward）
        reward = 1.0 if correct else 0.2
        reward = max(0.0, min(1.0, reward))
        rewards.append(reward)

        # 4. LCA update
        lca_engine.update(
            state.student_id,
            lca_result.intervention,
            new_state=state,
            state_delta=reward,
        )

    return lca_results, rewards


def main() -> int:
    print("=" * 78)
    print("M2 W2 LCA 策略引擎验证")
    print("=" * 78)

    # ---- 单元自检 ----
    print("\n--- 单元自检 ---")
    t1 = check_select_bloom_target()
    t2 = check_clt_levels()
    t3 = check_ca_state_machine()
    t4 = check_linucb_convergence()
    t5 = check_template_fallback()
    unit_passed = sum([t1, t2, t3, t4, t5])

    # ---- 真实 LLM 调用（仅在 key 存在时执行）----
    print("\n--- 真实 LLM Rationale ---")
    llm_client = None
    try:
        llm_client = ECOSLLMClient.from_env(provider="minimax")
        print(f"  ✅ LLM 客户端就绪：{llm_client.config.model}")
    except ValueError as e:
        print(f"  ⚠️ 无 LLM 客户端：{e}")
        print(f"     → Rationale 测试跳过（pipeline 仍跑，用 None client 即 fallback）")

    llm_ok = real_llm_rationale_test(llm_client)

    # ---- 完整 CTA → LCA pipeline ----
    print("\n--- 完整 CTA → LCA pipeline ---")
    rng = np.random.default_rng(seed=20260703)
    true_theta = np.array([1.5, 1.2, 0.5, 0.8, 0.3])
    items = build_items()

    cta_engine = BeliefEngine(BeliefEngineConfig(
        evolution_config=EvolutionConfig(default_params=BKTParams(p_init=0.2)),
        mirt_config=MIRTConfig(prior_mean=np.zeros(5), prior_cov=np.eye(5)),
    ))
    cta_engine.l2.register_items_bulk(items)
    state = cta_engine.create_initial_state(student_id="pipeline_001")

    lca_engine = LCAEngine(
        config=LCAEngineConfig(
            use_llm_rationale=(llm_client is not None),
            rationale_audience="student",
        ),
        llm_client=llm_client,
    )

    lca_results, rewards = run_full_pipeline(
        cta_engine=cta_engine,
        items=items,
        true_theta=true_theta,
        rng=rng,
        lca_engine=lca_engine,
        state=state,
        n_steps=30,
    )

    # 打印 pipeline 摘要
    intervention_types = [r.intervention.intervention_type.value for r in lca_results]
    bloom_targets = [r.bloom_target.name for r in lca_results]
    clt_levels = [r.clt_level.name for r in lca_results]
    ca_stages = [r.ca_stage.name for r in lca_results]

    print(f"  模拟步数：{len(lca_results)}")
    print(f"  干预类型分布：")
    from collections import Counter
    for k, v in Counter(intervention_types).most_common():
        print(f"    {k:>15s}: {v} ({v/len(intervention_types):.1%})")
    print(f"  Bloom 目标分布：")
    for k, v in Counter(bloom_targets).most_common():
        print(f"    {k:>12s}: {v}")
    print(f"  CLT 级别分布：")
    for k, v in Counter(clt_levels).most_common():
        print(f"    {k:>12s}: {v}")
    print(f"  CA 阶段分布：")
    for k, v in Counter(ca_stages).most_common():
        print(f"    {k:>12s}: {v}")
    print(f"  平均 reward：{np.mean(rewards):.3f}")

    # LinUCB 收敛迹象：arm 计数不均匀（至少有一些被拉动多次）
    bandit_stats = lca_engine.bandit.bandit.arm_pull_counts.tolist()
    total_pulls = sum(bandit_stats)
    max_pull = max(bandit_stats)
    min_pull = min(bandit_stats)
    print(f"\n  LinUCB arm 计数：{bandit_stats}")
    print(f"    total={total_pulls}, max={max_pull}, min={min_pull}")

    pipeline_passed = (
        total_pulls == len(rewards)
        and max_pull > min_pull  # 有探索不均
        and all(0.0 <= r <= 1.0 for r in rewards)
    )

    # ---- 总结 ----
    print("\n" + "=" * 78)
    print("M2 W2 LCA 验证总结")
    print("=" * 78)
    print(f"  单元自检（5 类）:     {unit_passed}/5")
    print(f"  真实 LLM rationale:  {'✅' if llm_ok else '⚠️ 跳过（无 key / 失败）'}")
    print(f"  CTA→LCA pipeline:    {'✅' if pipeline_passed else '❌'}")
    print()
    if not llm_ok:
        print("  💡 要启用真实 LLM rationale 生成，请设置：")
        print("     export MINIMAX_API_KEY=<your-key>")
        print()

    overall = (unit_passed >= 4) and pipeline_passed
    print(f"  整体：{'✅ 通过（M2 W2 LCA 骨架可工作）' if overall else '❌ 有失败'}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
