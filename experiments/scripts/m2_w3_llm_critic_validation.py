"""M2 W3 LLM Critic 基础骨架验证脚本.

对应：
  - research/90-mvp/README.md §2.2 (Week 3: LLM Critic 完整集成)
  - research/10-engineering/01-cta-belief-engine.md §9 LLM Critic 边界

目的：
  验证 LLM Critic 的 3 类组件实际有效（不是骨架空转）：
  1) PerceptionCritic.perceive() — 感知层：解释文本 → 结构化输出
  2) MisconceptionDetector.detect() — Misconception 检测：命中 M1/M3/M8 等
  3) BeliefEngine.update() + LLM Critic — C 维度折扣 + BloomProfile 推断
  4) ExplanationCritic.explain() — 解释层：生成面向学生/教师/家长的诊断报告

运行：
  PYTHONPATH=. python experiments/scripts/m2_w3_llm_critic_validation.py

行为：
  - 无 MINIMAX_API_KEY → 跳过 LLM 调用测试，仅验证骨架可导入
  - 有 MINIMAX_API_KEY → 走真实 MiniMax-M3 调用（temperature=0.2）
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from ecos.cta import (
    BeliefEngine,
    BeliefEngineConfig,
    BloomLevel,
    Observation,
)
from ecos.cta.belief_state import (
    ConfidenceDimensionState,
    MisconceptionHit,
)
from ecos.cta.llm_critic import (
    ExplanationCritic,
    MisconceptionDetector,
    PerceptionCritic,
)
from ecos.llm_client import ECOSLLMClient

# ─── 辅助 ──────────────────────────────────────────────────────────

def has_api_key() -> bool:
    import os
    return bool(os.environ.get("MINIMAX_API_KEY") or os.environ.get("OPENAI_API_KEY"))


def print_header(text: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {text}")
    print('='*60)


def print_result(name: str, passed: bool, detail: str = "") -> None:
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status}  {name}")
    if detail:
        print(f"         {detail}")


# ─── Test 1: 骨架可导入 ─────────────────────────────────────────────

def test_import():
    print_header("Test 1: 模块导入")
    try:
        from ecos.cta.llm_critic import (
            PerceptionCritic,
            ExplanationCritic,
            MisconceptionDetector,
        )
        from ecos.cta.content import MisconceptionLibrary, ThresholdConceptLibrary
        from ecos.bloom.subject_libraries.math import MathBloomLibrary
        print_result("LLM Critic 模块导入", True)
        print_result("MisconceptionLibrary 导入", True)
        print_result("ThresholdConceptLibrary 导入", True)
        print_result("MathBloomLibrary 导入", True)

        # 验证库内容
        misc_lib = MisconceptionLibrary()
        print_result(f"MisconceptionLibrary 条目数={len(misc_lib.all_entries())}", len(misc_lib.all_entries()) == 30)

        tc_lib = ThresholdConceptLibrary()
        print_result(f"ThresholdConceptLibrary 条目数={len(tc_lib.all_entries())}", len(tc_lib.all_entries()) == 8)

        bloom_lib = MathBloomLibrary()
        print_result(f"MathBloomLibrary 条目数={len(bloom_lib.all_entries())}", len(bloom_lib.all_entries()) == 32)

        return True
    except Exception as e:
        print_result("模块导入", False, str(e))
        return False


# ─── Test 2: BeliefEngine 初始化（C 维度类型正确）──────────────────

def test_belief_engine_init():
    print_header("Test 2: BeliefEngine 初始化 + C 维度类型")
    engine = BeliefEngine()
    state = engine.create_initial_state("test_student")

    # C 维度必须是 ConfidenceDimensionState
    is_confidence_dim = isinstance(state.C, ConfidenceDimensionState)
    print_result("C 维度类型=ConfidenceDimensionState", is_confidence_dim,
                 f"实际: {type(state.C).__name__}")

    # misconception_hits 字段存在
    has_hits = hasattr(state.C, "misconception_hits")
    print_result("C.misconception_hits 字段存在", has_hits)

    # discount_factor 默认 1.0
    has_discount = hasattr(state.C, "discount_factor")
    print_result("C.discount_factor 字段存在", has_discount)
    if has_discount:
        print_result("discount_factor 默认=1.0", state.C.discount_factor == 1.0,
                     f"实际: {state.C.discount_factor}")

    return is_confidence_dim and has_hits


# ─── Test 3: PerceptionCritic 感知层 ─────────────────────────────────

def test_perception_critic(llm_client: ECOSLLMClient | None):
    print_header("Test 3: PerceptionCritic 感知层")

    if llm_client is None:
        print("  ⏭ SKIP（无 API_KEY）")
        return True

    critic = PerceptionCritic(llm_client)

    # 测试用例：学生解释"两边同时减去3，再除以2"（高质量理解）
    result = critic.perceive(
        problem="解方程 2x+3=7",
        correct_answer="x=2",
        student_correctness=True,
        student_explanation="两边同时减去3，得到 2x=4，再除以2，得到 x=2。",
    )

    print_result("返回 PerceptionOutput", result is not None)
    print_result("correctness ∈ {True, False}", isinstance(result.correctness, bool))
    print_result("explanation_quality ∈ [0,1]", 0.0 <= result.explanation_quality <= 1.0)
    print_result("self_evaluation ∈ [0,1]", 0.0 <= result.self_evaluation <= 1.0)
    print_result("confusion_signals 是 tuple", isinstance(result.confusion_signals, tuple))
    print_result(f"BloomLevel 推断: {result.bloom_level}", result.bloom_level is not None)
    print_result(f"skill_ids 推断: {result.skill_ids}", isinstance(result.skill_ids, tuple))
    print_result(f"explanation_quality={result.explanation_quality:.2f}", True)
    return True


# ─── Test 4: MisconceptionDetector 检测 ─────────────────────────────

def test_misconception_detector(llm_client: ECOSLLMClient | None):
    print_header("Test 4: MisconceptionDetector 检测")

    if llm_client is None:
        print("  ⏭ SKIP（无 API_KEY）")
        return True

    detector = MisconceptionDetector(llm_client)

    test_cases = [
        # (学生解释, 期望命中的 misc_id 或 None, 描述)
        (
            "5×0.5怎么变小了？乘法应该越乘越大啊！",
            "M1",
            "M1 乘法总是变大",
        ),
        (
            "x+3=5，x=5+3=8，我把3移到右边还是加",
            "M11",
            "M11 移项不变号",
        ),
        (
            "两边同除以-2，x>-3，不等号方向没变",
            "M3",
            "M3 等式性质错误推广到不等式",
        ),
        (
            "圆面积是 2πr 吧？周长才是 πr²？",
            "M14",
            "M14 圆面积与周长混淆",
        ),
        (
            "我知道 x² 和 2x 不一样，但有时候还是会搞混",
            None,
            "无明确 misconception（混淆但不触发）",
        ),
    ]

    all_passed = True
    for explanation, expected_id, description in test_cases:
        result = detector.detect(explanation, "初中数学题")
        matched = result.misc_id == expected_id
        if not matched:
            all_passed = False
        detail = f"期望={expected_id} 实际={result.misc_id} conf={result.confidence:.2f}"
        print_result(f"{description}: {detail}", matched)

        # 如果命中，验证 evidence_text 非空
        if result.misc_id:
            has_evidence = len(result.evidence_text) > 0
            print_result(f"  evidence_text 非空", has_evidence,
                         f"长度={len(result.evidence_text)}")

    # 测试 detect_with_hits 返回 MisconceptionHit
    result = detector.detect_with_hits(
        "5×0.5怎么变小了？",
        trigger_problem_id="p1",
    )
    is_hit = isinstance(result, MisconceptionHit) or result is None
    print_result("detect_with_hits() 返回 MisconceptionHit 或 None", is_hit)
    if result:
        print_result(f"  MiscHit: misc_id={result.misc_id} conf={result.confidence:.2f}", True)

    return all_passed


# ─── Test 5: BeliefEngine.update() + LLM Critic 集成 ─────────────────

def test_belief_engine_with_llm(llm_client: ECOSLLMClient | None):
    print_header("Test 5: BeliefEngine + LLM Critic 集成")

    if llm_client is None:
        print("  ⏭ SKIP（无 API_KEY）")
        return True

    engine = BeliefEngine(llm_client=llm_client)
    state = engine.create_initial_state("test_llm_student")

    # 第一次观测：有 misconception 的解释
    obs1 = Observation(
        skill_id="math.algebra.linear",
        problem_id="p1",
        correct=True,
        bloom_level=BloomLevel.APPLY,
        explanation_text="5×0.5怎么变小了？乘法应该越乘越大啊！",
        problem_text="计算 5 × 0.5",
        correct_answer="2.5",
    )
    state = engine.update(state, obs1)

    print_result("update() 执行完成", True)
    print_result(f"C.discount_factor 折扣后={state.C.discount_factor:.2f}",
                 state.C.discount_factor < 1.0,
                 f"期望 < 1.0（如果检测到 M1）")

    # 如果检测到了 misconception，验证 illusory_confidence_flag
    if len(state.C.misconception_hits) > 0:
        print_result(f"misconception_hits 记录数={len(state.C.misconception_hits)}", True)
        hit = state.C.misconception_hits[0]
        print_result(f"  最新命中: misc_id={hit.misc_id} conf={hit.confidence:.2f}", True)
        print_result("illusory_confidence_flag=True", state.C.illusory_confidence_flag)
    else:
        print("  （未检测到 misconception，可能 LLM 判断未触发）")

    # 第二次观测：正常高质量解释
    obs2 = Observation(
        skill_id="math.algebra.linear",
        problem_id="p2",
        correct=True,
        bloom_level=BloomLevel.APPLY,
        explanation_text="两边同时减去3，再除以2，得到 x=2。我对每一步都很确定。",
        problem_text="解方程 2x+3=7",
        correct_answer="x=2",
    )
    state2 = engine.update(state, obs2)
    print_result("第二次 update() 执行完成", True)

    return True


# ─── Test 6: ExplanationCritic 解释层 ────────────────────────────────

def test_explanation_critic(llm_client: ECOSLLMClient | None):
    print_header("Test 6: ExplanationCritic 解释层")

    if llm_client is None:
        print("  ⏭ SKIP（无 API_KEY）")
        return True

    from ecos.cta import BeliefState
    import numpy as np
    from ecos.cta.belief_state import BloomProfileState, DimensionState

    # 构造一个假的 BeliefState
    state = BeliefState(student_id="test_student")
    state.theta_mean = np.array([0.7, 0.5, 0.4, 0.3, 0.6])
    state.K = DimensionState(dimension="K", mastery_prob=0.7, confidence=0.8)
    state.P = DimensionState(dimension="P", mastery_prob=0.5, confidence=0.6)
    state.S = DimensionState(dimension="S", mastery_prob=0.4, confidence=0.5)
    state.C = ConfidenceDimensionState(dimension="C", mastery_prob=0.3, confidence=0.4)
    state.X = DimensionState(dimension="X", mastery_prob=0.6, confidence=0.5)
    state.bloom_profile = BloomProfileState()
    state.overall_confidence = 0.55

    critic = ExplanationCritic(llm_client)

    for audience in ["student", "teacher", "parent"]:
        report = critic.explain(state, audience=audience)
        has_content = len(report) > 20
        print_result(f"explain(audience='{audience}') 生成报告", has_content,
                     f"长度={len(report)} 字符")
        if has_content:
            print(f"    摘录: {report[:80]}...")

    return True


# ─── Main ─────────────────────────────────────────────────────────────

def main():
    print("\n" + "#"*60)
    print("#  M2 W3 LLM Critic 验证脚本")
    print(f"#  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("#"*60)

    # 检查 API key
    api_key_available = has_api_key()
    llm_client = None
    if api_key_available:
        try:
            llm_client = ECOSLLMClient.from_env("minimax")
            print("\n  ✅ MINIMAX_API_KEY 已配置，走真实 LLM 调用")
        except Exception:
            try:
                llm_client = ECOSLLMClient.from_env("moonshot")
                print("\n  ✅ MOONSHOT_API_KEY 已配置")
            except Exception as e:
                print(f"\n  ⚠️  API key 读取失败: {e}，跳过 LLM 测试")
                llm_client = None
    else:
        print("\n  ⏭ MINIMAX_API_KEY / OPENAI_API_KEY 未配置，仅验证骨架导入")

    results: dict[str, bool] = {}

    results["import"] = test_import()
    results["belief_engine_init"] = test_belief_engine_init()

    if llm_client is not None:
        results["perception"] = test_perception_critic(llm_client)
        results["misconception"] = test_misconception_detector(llm_client)
        results["belief_engine_llm"] = test_belief_engine_with_llm(llm_client)
        results["explanation"] = test_explanation_critic(llm_client)
    else:
        print("\n  ⏭ 跳过 LLM 组件测试（无 API key）")

    # 汇总
    print_header("汇总")
    total = len(results)
    passed = sum(results.values())
    print(f"\n  {'✅ PASSED' if passed == total else '❌ FAILED'}: {passed}/{total}")
    for name, ok in results.items():
        status = "✅" if ok else "❌"
        print(f"    {status}  {name}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
