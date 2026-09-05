"""黄金回归序列定义（v0.97.0 恢复期 backlog P1: A3 式黄金回归基建）.

对应:
  - README §下一步 P1「A3 式黄金回归基建」
  - discussions/2026-09-05-CogMirror迁移适用性分析-与built-unwired接线审计.md §四
  - 借鉴 CogMirror docs/implementation-plan.md P1 (PersonalAGI gauntlet_regression 模式)

设计约定:
  - 纯数据模块（无 import 依赖引擎），runner 负责映射到 Observation/BloomLevel
  - 每条序列 = 一个"合成学习者"，覆盖一种行为模式
  - timestamp 由 runner 按 step index 固定推导（CogMirror P1 复核教训:
    Observation 默认 datetime.now() 会让涉时间窗/衰减的断言不可复现）
  - explanation_text 恒为空——与产品路径现状一致（wiring-audit 前置缺口 A 同型:
    LLM critic 链路在无 LLM/无解释文本时不触发），LLM judge 层后置（P2+）
  - score >= 0.6 → correct（引擎 v0.54.0 派生规则）
"""

# 每条序列的字段:
#   name:        序列名（baseline.json key）
#   description: 行为模式说明
#   steps:       [ {skill_id, problem_id, score, bloom} ]
#   intent:      行为意图断言 key（runner 中 INTENT_CHECKS 映射，人工撰写）

GOLDEN_SEQUENCES = [
    {
        "name": "all_correct_learner",
        "description": "全对快速掌握: 3 skill 交错, 12 步全对, Bloom L1→L4 递进",
        "steps": [
            {"skill_id": "python.loops", "problem_id": "gold-01", "score": 1.0, "bloom": "REMEMBER"},
            {"skill_id": "python.functions", "problem_id": "gold-02", "score": 1.0, "bloom": "REMEMBER"},
            {"skill_id": "python.strings", "problem_id": "gold-03", "score": 1.0, "bloom": "UNDERSTAND"},
            {"skill_id": "python.loops", "problem_id": "gold-04", "score": 1.0, "bloom": "UNDERSTAND"},
            {"skill_id": "python.functions", "problem_id": "gold-05", "score": 1.0, "bloom": "UNDERSTAND"},
            {"skill_id": "python.strings", "problem_id": "gold-06", "score": 1.0, "bloom": "APPLY"},
            {"skill_id": "python.loops", "problem_id": "gold-07", "score": 1.0, "bloom": "APPLY"},
            {"skill_id": "python.functions", "problem_id": "gold-08", "score": 1.0, "bloom": "APPLY"},
            {"skill_id": "python.strings", "problem_id": "gold-09", "score": 1.0, "bloom": "ANALYZE"},
            {"skill_id": "python.loops", "problem_id": "gold-10", "score": 1.0, "bloom": "ANALYZE"},
            {"skill_id": "python.functions", "problem_id": "gold-11", "score": 1.0, "bloom": "ANALYZE"},
            {"skill_id": "python.strings", "problem_id": "gold-12", "score": 1.0, "bloom": "ANALYZE"},
        ],
    },
    {
        "name": "all_wrong_learner",
        "description": "全错挣扎: 同 3 skill, 12 步全错, Bloom L2-L4",
        "steps": [
            {"skill_id": "python.loops", "problem_id": "gold-21", "score": 0.0, "bloom": "UNDERSTAND"},
            {"skill_id": "python.functions", "problem_id": "gold-22", "score": 0.0, "bloom": "UNDERSTAND"},
            {"skill_id": "python.strings", "problem_id": "gold-23", "score": 0.0, "bloom": "UNDERSTAND"},
            {"skill_id": "python.loops", "problem_id": "gold-24", "score": 0.0, "bloom": "UNDERSTAND"},
            {"skill_id": "python.functions", "problem_id": "gold-25", "score": 0.0, "bloom": "APPLY"},
            {"skill_id": "python.strings", "problem_id": "gold-26", "score": 0.0, "bloom": "APPLY"},
            {"skill_id": "python.loops", "problem_id": "gold-27", "score": 0.0, "bloom": "APPLY"},
            {"skill_id": "python.functions", "problem_id": "gold-28", "score": 0.0, "bloom": "APPLY"},
            {"skill_id": "python.strings", "problem_id": "gold-29", "score": 0.0, "bloom": "ANALYZE"},
            {"skill_id": "python.loops", "problem_id": "gold-30", "score": 0.0, "bloom": "ANALYZE"},
            {"skill_id": "python.functions", "problem_id": "gold-31", "score": 0.0, "bloom": "ANALYZE"},
            {"skill_id": "python.strings", "problem_id": "gold-32", "score": 0.0, "bloom": "ANALYZE"},
        ],
    },
    {
        "name": "partial_credit_mixed",
        "description": "部分对混合: partial credit 全谱 (0.0/0.1/0.3/0.4/0.5/0.6/0.7/0.9/1.0), 2 skill",
        "steps": [
            {"skill_id": "python.scope", "problem_id": "gold-41", "score": 1.0, "bloom": "APPLY"},
            {"skill_id": "python.dicts", "problem_id": "gold-42", "score": 0.0, "bloom": "APPLY"},
            {"skill_id": "python.scope", "problem_id": "gold-43", "score": 0.3, "bloom": "APPLY"},
            {"skill_id": "python.dicts", "problem_id": "gold-44", "score": 0.7, "bloom": "UNDERSTAND"},
            {"skill_id": "python.scope", "problem_id": "gold-45", "score": 0.9, "bloom": "APPLY"},
            {"skill_id": "python.dicts", "problem_id": "gold-46", "score": 0.1, "bloom": "UNDERSTAND"},
            {"skill_id": "python.scope", "problem_id": "gold-47", "score": 0.5, "bloom": "ANALYZE"},
            {"skill_id": "python.dicts", "problem_id": "gold-48", "score": 1.0, "bloom": "APPLY"},
            {"skill_id": "python.scope", "problem_id": "gold-49", "score": 0.6, "bloom": "ANALYZE"},
            {"skill_id": "python.dicts", "problem_id": "gold-50", "score": 0.4, "bloom": "APPLY"},
        ],
    },
    {
        "name": "liminal_crossing_single_skill",
        "description": "TC liminal 跨越: 单 skill, 4 错 (低层) → 6 混合 (L3) → 4 对 (L4), 观察 tc_states 演化",
        "steps": [
            {"skill_id": "python.loops", "problem_id": "gold-61", "score": 0.0, "bloom": "REMEMBER"},
            {"skill_id": "python.loops", "problem_id": "gold-62", "score": 0.0, "bloom": "UNDERSTAND"},
            {"skill_id": "python.loops", "problem_id": "gold-63", "score": 0.0, "bloom": "UNDERSTAND"},
            {"skill_id": "python.loops", "problem_id": "gold-64", "score": 0.2, "bloom": "UNDERSTAND"},
            {"skill_id": "python.loops", "problem_id": "gold-65", "score": 0.6, "bloom": "APPLY"},
            {"skill_id": "python.loops", "problem_id": "gold-66", "score": 0.4, "bloom": "APPLY"},
            {"skill_id": "python.loops", "problem_id": "gold-67", "score": 1.0, "bloom": "APPLY"},
            {"skill_id": "python.loops", "problem_id": "gold-68", "score": 0.6, "bloom": "APPLY"},
            {"skill_id": "python.loops", "problem_id": "gold-69", "score": 0.9, "bloom": "APPLY"},
            {"skill_id": "python.loops", "problem_id": "gold-70", "score": 0.3, "bloom": "APPLY"},
            {"skill_id": "python.loops", "problem_id": "gold-71", "score": 1.0, "bloom": "ANALYZE"},
            {"skill_id": "python.loops", "problem_id": "gold-72", "score": 1.0, "bloom": "ANALYZE"},
            {"skill_id": "python.loops", "problem_id": "gold-73", "score": 1.0, "bloom": "ANALYZE"},
            {"skill_id": "python.loops", "problem_id": "gold-74", "score": 1.0, "bloom": "ANALYZE"},
        ],
    },
    {
        "name": "dense_single_skill",
        "description": "密集单 skill: 20 步全对驱动 warmup/probe 状态机 + Bloom L2-L5 全谱",
        "steps": [
            {"skill_id": "python.functions", "problem_id": f"gold-{80 + i}", "score": 1.0,
             "bloom": ["UNDERSTAND", "APPLY", "ANALYZE", "EVALUATE", "CREATE"][i % 5]}
            for i in range(20)
        ],
    },
]

# 黄金序列的固定时间基准（runner 用 base + step_index * 5min 推导 timestamp）
GOLDEN_BASE_DATETIME = (2026, 9, 5, 8, 0, 0)

__all__ = ["GOLDEN_SEQUENCES", "GOLDEN_BASE_DATETIME"]
