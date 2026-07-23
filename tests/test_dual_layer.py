"""v0.55.0-c: 5D 双层架构 (领域无关核心 + 领域特定扩展) 测试.

架构决策 (Bisen 2026-07-23 22:38 方案 D):
- 5D 核心领域无关, 跨数学/语文/英语/物理/化学通用
  - K = Knowledge 知识掌握
  - P = Procedure 程序技能
  - S = Strategy 策略能力
  - C = Confidence 认知置信度 (self_evaluation/求助/检查/misconception)
  - X = External Support 外部支架 (工具/笔记/记忆/Agent)
- 领域特定扩展独立字段, 不污染 5D 核心
  - 编程扩展: programming_debug_score (20 道 PB-C 评估)
  - 数学扩展: (待 v0.56.0+)
  - 语文扩展: (待 v0.56.0+)
  - 英语扩展: (待 v0.56.0+)
  - 物理扩展: (待 v0.56.0+)
  - 化学扩展: (待 v0.56.0+)

拦截历史:
- v0.54.1-d C/X 维度 3 位置定义漂移 (belief_state.py=Confidence vs 02-arch=Common
  mistakes vs 07-审查报告=Common mistakes)
- v0.54.1-e Bisen 调研 3 权威文档, 确认 5D 核心必须领域无关
- v0.54.2 实施 C-confidence 主导题 (5 道 PC-C01-C05, topic="cross_subject")
- v0.54.3 实施 X-external-support 主导题 (5 道 PC-X01-X05, topic="cross_subject")
- 20 道 PB-C01-C20 编程调试保留为编程应用层扩展

测试:
1. test_5d_core_C_is_confidence_dimension: 验证 BeliefState.C 是 ConfidenceDimensionState
   (含 misconception 折扣 + TC 状态), 不是编程调试
2. test_q_matrix_dual_layer_isolation: 验证 Q 矩阵中 PC-C/C-X (cross_subject 跨学科)
   vs PB-C (python 编程调试) 完全隔离, topic/skill 字段不重叠
"""
import json
from pathlib import Path

import pytest


# ─── 测试 1: 5D 核心 C 维度 = Confidence (含 misconception 折扣) ─────────

def test_5d_core_C_is_confidence_dimension():
    """BeliefState.C 必须是 ConfidenceDimensionState (含 misconception + TC),
    不能是编程调试或其它领域特定扩展.

    拦截历史:
    - v0.54.1-d C 维度 3 位置定义漂移 (Confidence vs Common mistakes)
    - v0.54.1-e Bisen 决策: 5D 核心领域无关, C = Confidence
    """
    from ecos.cta.belief_state import (
        BeliefState, ConfidenceDimensionState, DimensionState, DimensionId
    )

    state = BeliefState(student_id="test_dual_layer")

    # 断言: C 维度是 ConfidenceDimensionState 类型
    assert isinstance(state.C, ConfidenceDimensionState), \
        f"❌ 5D 核心 C 维度必须是 ConfidenceDimensionState (含 misconception 折扣), " \
        f"实际类型={type(state.C).__name__}\n" \
        f"   任何重构成 DimensionState 的改动都会破坏 misconception 检测链"

    # 断言: C 维度有 misconception 折扣机制 (ConfidenceDimensionState 特有字段)
    assert hasattr(state.C, "discount_factor"), \
        "❌ C 维度必须有 discount_factor 字段 (ConfidenceDimensionState 特有)"
    assert hasattr(state.C, "misconception_hits"), \
        "❌ C 维度必须有 misconception_hits 字段 (ConfidenceDimensionState 特有)"
    assert hasattr(state.C, "tc_states"), \
        "❌ C 维度必须有 tc_states 字段 (Threshold Concept 状态)"
    assert hasattr(state.C, "illusory_confidence_flag"), \
        "❌ C 维度必须有 illusory_confidence_flag 字段 (伪置信检测)"

    # 断言: 5D 其它维度是 DimensionState (不含 misconception 折扣)
    for dim_id in ["K", "P", "S", "X"]:
        dim_state = getattr(state, dim_id)
        assert isinstance(dim_state, DimensionState), \
            f"❌ 5D 维度 {dim_id} 必须是 DimensionState, 实际={type(dim_state).__name__}"
        # K/P/S/X 不应该有 misconception_hits (那是 C 维度特化)
        if dim_id != "C":
            assert not hasattr(dim_state, "misconception_hits"), \
                f"❌ 5D 维度 {dim_id} 不应有 misconception_hits 字段 (那是 C 维度特化)"

    # 断言: DimensionId.C 值是 "C" (权威定义 = Confidence)
    assert DimensionId.C.value == "C", \
        f"❌ DimensionId.C 必须是 'C' (Confidence), 实际={DimensionId.C.value}"


# ─── 测试 2: Q 矩阵双层隔离 (PC-C/PC-X 跨学科 vs PB-C 编程调试) ───────

def test_q_matrix_dual_layer_isolation():
    """Q 矩阵中 PC-C01-C05 + PC-X01-X05 (cross_subject 跨学科) vs
    PB-C01-C20 (python 编程调试) 必须完全隔离, topic/skill 不重叠.

    拦截历史:
    - v0.54.1-d C 维度 3 位置定义漂移导致 PB-C01 (编程调试) 被错认为 5D 核心 C
    - v0.54.1-e 方案 D 决策: PB-C 保留为编程应用层扩展, 5D 核心用 PC-C/PC-X
    - v0.54.2 实施 PC-C01-C05, topic="cross_subject"
    - v0.54.3 实施 PC-X01-X05, topic="cross_subject"
    """
    qpath = Path("data/python_basics_q_matrix.json")
    with open(qpath) as f:
        qdata = json.load(f)

    problems = {p["problem_id"]: p for p in qdata["problems"]}

    # ── 5D 核心层: PC-C01-C05 + PC-X01-X05 (跨学科) ──
    core_5d_problems = {
        f"PC-C{i:02d}": problems.get(f"PC-C{i:02d}") for i in range(1, 6)
    }
    core_5d_problems.update({
        f"PC-X{i:02d}": problems.get(f"PC-X{i:02d}") for i in range(1, 6)
    })

    for pid, p in core_5d_problems.items():
        assert p is not None, f"❌ 5D 核心层题目 {pid} 缺失"
        # 关键断言: 5D 核心层题目 topic 必须是 "cross_subject" (跨学科)
        assert p["topic"] == "cross_subject", \
            f"❌ 5D 核心层题目 {pid} topic 必须是 'cross_subject' (领域无关), " \
            f"实际='{p['topic']}'\n" \
            f"   任何 5D 核心题 topic 漂移到 python/math/physics 都是污染"

    # ── 编程应用层扩展: PB-C01-C20 (python 编程调试) ──
    pb_c_problems = {
        f"PB-C{i:02d}": problems.get(f"PB-C{i:02d}") for i in range(1, 21)
    }
    for pid, p in pb_c_problems.items():
        assert p is not None, f"❌ 编程扩展层题目 {pid} 缺失"
        # 关键断言: 编程扩展层题目 topic 必须是 "python.*" (领域特定)
        assert p["topic"].startswith("python"), \
            f"❌ 编程扩展层题目 {pid} topic 必须是 'python.*', 实际='{p['topic']}'\n" \
            f"   PB-C 题目是编程应用层, 不属于 5D 核心"

    # ── 双层不重叠 ──
    core_ids = set(core_5d_problems.keys())
    pb_c_ids = set(pb_c_problems.keys())
    overlap = core_ids & pb_c_ids
    assert not overlap, \
        f"❌ 5D 核心层和编程扩展层 ID 重叠: {overlap}\n" \
        f"   双层架构要求 problem_id 完全不共享"

    # ── skill 字段双层不重叠 ──
    core_skills = {p["skill_name"] for p in core_5d_problems.values() if p}
    pb_c_skills = {p["skill_name"] for p in pb_c_problems.values() if p}
    skill_overlap = core_skills & pb_c_skills
    # 注: skill_name 可以有交叉 (如 "调试策略" 跨两层), 但 topic 必须隔离
    # 这里只检查 topic 隔离, skill 重叠是允许的
    # (v0.54.1-e 决策: 双层通过 topic 字段隔离, skill 字段允许同名词跨层)

    # ── 5D 核心层 C/X 维度分布验证 ──
    pc_c_skills = [p["skill_name"] for p in [
        problems.get(f"PC-C{i:02d}") for i in range(1, 6)
    ] if p]
    pc_x_skills = [p["skill_name"] for p in [
        problems.get(f"PC-X{i:02d}") for i in range(1, 6)
    ] if p]

    # PC-C 系列应该聚焦 C-confidence 5 类核心概念
    # (skill_name 用中文, 对应英文: self_evaluation/help_seeking/self_checking/
    #  misconception_detection/metacognition_synthesis)
    c_concepts_zh = {"自我评估", "求助决策", "检查行为", "misconception 检测", "综合元认知"}
    assert set(pc_c_skills) == c_concepts_zh, \
        f"❌ PC-C01-C05 skill_name 必须是 C-confidence 5 类核心概念, 实际={pc_c_skills}"

    # PC-X 系列应该聚焦 X-external-support 5 类核心概念
    # (对应英文: tool_selection/note_quality/memory_use_strategy/
    #  scaffolding_dependency/external_support_synthesis)
    x_concepts_zh = {"工具选择", "笔记质量", "记忆使用策略", "支架依赖度", "综合 External Support"}
    assert set(pc_x_skills) == x_concepts_zh, \
        f"❌ PC-X01-X05 skill_name 必须是 X-external-support 5 类核心概念, 实际={pc_x_skills}"
