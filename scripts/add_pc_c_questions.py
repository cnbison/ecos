"""v0.54.1-f-b: 追加 5 道 C-confidence 主导题到 data/python_basics_q_matrix.json.

按 v0.54.1-f 设计文档 (research/90-mvp/10-phase5-c-confidence-questions-design.md)
生成 5 道 C-confidence 主导题 (PC-C01 ~ PC-C05), 领域无关 (跨数学/语文/英语/物理/化学通用).

字段扩展:
  - domain_agnostic: True  # 跨学科通用
  - c_dimension_type: self_evaluation / help_seeking / self_checking / misconception_detection / metacognition_synthesis
  - 跟 v0.54.1-b PB-C 20 道 (编程领域应用层) 区分: problem_id 前缀 PC-C vs PB-C

5D 完整性目标: K/P/S/C 真评估 (3/5 → 4/5 → 5/5)
编程扩展: 20 道 PB-C 保留, 评估 programming_debug_score (独立字段)

运行: python scripts/add_pc_c_questions.py
"""
import json
from pathlib import Path

Q_MATRIX_PATH = Path("data/python_basics_q_matrix.json")


# 5 道 C-confidence 主导题 (按 v0.54.1-f 设计)
PC_C_QUESTIONS = [
    {
        "problem_id": "PC-C01",
        "topic": "cross_subject",
        "skill_name": "自我评估",
        "bloom_goal_id": "cross_subject-L3",
        "problem_text": (
            "这道题你能答对的可能性有多大？\n"
            "A. 90% (非常确定)\n"
            "B. 70% (比较确定)\n"
            "C. 50% (一半一半)\n"
            "D. 30% (不太确定)\n"
            "E. 10% (完全不会)"
        ),
        "correct_answer": (
            "B (70% 比较确定). "
            "基于 lbc001 实际 K/P 维度评估, L3 题目答对可能性约 70-80%."
        ),
        "bloom_layer_observed": "L3",
        "a_specialized": [0.2, 0.2, 0.3, 1.1, 0.2],  # C 主导
        "mirt_params": {"difficulty": 0.0, "discrimination": 1.0, "guessing": 0.0},
        "misconceptions": [],
        "intervention_types": ["EXPLANATION", "SCAFFOLDING"],
        "c_dimension_type": "self_evaluation",
        "domain_agnostic": True,
        "partial_credit_rubric": {
            "0.0": "选 E (完全不会) — 自我评估严重不准",
            "0.3": "选 D (30% 不太确定) — 低估",
            "0.6": "选 C (50% 一半一半) — 模糊",
            "1.0": "选 B (70% 比较确定) — 准确自我评估",
        },
    },
    {
        "problem_id": "PC-C02",
        "topic": "cross_subject",
        "skill_name": "求助决策",
        "bloom_goal_id": "cross_subject-L4",
        "problem_text": (
            "遇到难题你打算怎么办？\n"
            "A. 直接放弃\n"
            "B. 猜一个答案\n"
            "C. 看笔记/教材\n"
            "D. 问老师/同学\n"
            "E. 独立思考 + 查资料"
        ),
        "correct_answer": "E (独立思考 + 查资料). 元认知最优策略.",
        "bloom_layer_observed": "L4",
        "a_specialized": [0.2, 0.2, 0.3, 1.2, 0.2],  # C 主导
        "mirt_params": {"difficulty": 0.0, "discrimination": 1.0, "guessing": 0.0},
        "misconceptions": ["M-illinois-confidence-avoid-help"],
        "intervention_types": ["EXPLANATION", "SCAFFOLDING"],
        "c_dimension_type": "help_seeking_strategy",
        "domain_agnostic": True,
        "partial_credit_rubric": {
            "0.0": "选 A (直接放弃)",
            "0.3": "选 B (猜答案) — 元认知差",
            "0.6": "选 C/D (单策略) — 单一求助",
            "1.0": "选 E (综合策略) — 元认知优",
        },
    },
    {
        "problem_id": "PC-C03",
        "topic": "cross_subject",
        "skill_name": "检查行为",
        "bloom_goal_id": "cross_subject-L5",
        "problem_text": (
            "答完代码后，你会检查吗？\n"
            "A. 不会检查\n"
            "B. 简单看一遍\n"
            "C. 跑几个测试用例\n"
            "D. 完整边界测试 + 异常处理"
        ),
        "correct_answer": "C/D (检查行为). 元认知行为.",
        "bloom_layer_observed": "L5",
        "a_specialized": [0.2, 0.2, 0.3, 1.0, 0.3],  # C + X (检查 = 工具使用)
        "mirt_params": {"difficulty": 0.0, "discrimination": 1.0, "guessing": 0.0},
        "misconceptions": [],
        "intervention_types": ["EXPLANATION", "SCAFFOLDING"],
        "c_dimension_type": "self_checking_behavior",
        "domain_agnostic": True,
        "partial_credit_rubric": {
            "0.0": "选 A (不检查)",
            "0.3": "选 B (简单看)",
            "0.6": "选 C (跑测试)",
            "1.0": "选 D (完整测试) — 元认知优",
        },
    },
    {
        "problem_id": "PC-C04",
        "topic": "cross_subject",
        "skill_name": "misconception 检测",
        "bloom_goal_id": "cross_subject-L5",
        "problem_text": (
            "概念检测：以下说法哪些是常见误解？\n"
            "A. range(1, 5) 包括 5\n"
            "B. Python 中变量赋值是复制值\n"
            "C. 函数内修改全局变量无需声明\n"
            "D. 以上都是误解"
        ),
        "correct_answer": (
            "D (以上都是误解). "
            "A: range(1,5) 不包含 5. "
            "B: 变量赋值是引用, 不是复制. "
            "C: 函数内修改全局变量需 global 声明."
        ),
        "bloom_layer_observed": "L5",
        "a_specialized": [0.3, 0.2, 0.2, 1.3, 0.0],  # C 主导 (misconception 折扣)
        "mirt_params": {"difficulty": 0.2, "discrimination": 1.2, "guessing": 0.0},
        "misconceptions": ["M3", "M-candidate-mutable-confusion", "M-candidate-scope-confusion"],
        "intervention_types": ["EXPLANATION", "PRACTICE"],
        "c_dimension_type": "misconception_detection",
        "domain_agnostic": True,
        "partial_credit_rubric": {
            "0.0": "选 A/B/C (单一误解识别, 漏掉其他)",
            "0.6": "选 D (但没说明每个误解)",
            "1.0": "选 D + 详细解释每个误解",
        },
    },
    {
        "problem_id": "PC-C05",
        "topic": "cross_subject",
        "skill_name": "综合元认知",
        "bloom_goal_id": "cross_subject-L6",
        "problem_text": (
            "综合元认知评估：\n"
            "1. 答完题是否会检查？\n"
            "2. 遇到难题会求助还是独立思考？\n"
            "3. 自我评估准不准？\n"
            "4. 是否有常见误解？\n"
            "请综合评估你的元认知水平 (0-10 分)."
        ),
        "correct_answer": (
            "综合元认知评估. "
            "高分 (8-10): 检查 + 独立思考 + 自我评估准 + 无误解. "
            "中分 (5-7): 部分行为. "
            "低分 (0-4): 元认知弱."
        ),
        "bloom_layer_observed": "L6",
        "a_specialized": [0.2, 0.2, 0.3, 1.2, 0.2],  # C 主导
        "mirt_params": {"difficulty": 0.3, "discrimination": 1.0, "guessing": 0.0},
        "misconceptions": [],
        "intervention_types": ["EXPLANATION", "SCAFFOLDING"],
        "c_dimension_type": "metacognition_synthesis",
        "domain_agnostic": True,
        "partial_credit_rubric": {
            "0.0": "低分 (0-4) — 元认知弱",
            "0.3": "中低分 (4-5)",
            "0.6": "中分 (6-7)",
            "1.0": "高分 (8-10) — 元认知优",
        },
    },
]


def main() -> None:
    # 1. 读现有 Q 矩阵
    with open(Q_MATRIX_PATH, encoding="utf-8") as f:
        data = json.load(f)

    # 2. 检查 ID 不重复
    existing_ids = {p["problem_id"] for p in data["problems"]}
    for q in PC_C_QUESTIONS:
        if q["problem_id"] in existing_ids:
            print(f"⚠️ {q['problem_id']} 已存在, 跳过")
        else:
            data["problems"].append(q)
            print(f"✅ 添加 {q['problem_id']} ({q['c_dimension_type']}, 领域无关)")

    # 3. 更新 metadata
    if "metadata" not in data:
        data["metadata"] = {}
    data["metadata"]["version"] = "v0.54.1-f"
    data["metadata"]["phase"] = 5
    data["metadata"]["c_confidence_questions_count"] = sum(
        1 for p in data["problems"] if p["problem_id"].startswith("PC-C")
    )
    data["metadata"]["c_programming_questions_count"] = sum(
        1 for p in data["problems"] if p["problem_id"].startswith("PB-C")
    )
    data["metadata"]["total_questions"] = len(data["problems"])
    data["metadata"]["last_updated"] = "2026-07-23"
    data["metadata"]["dual_layer_architecture"] = {
        "core_5d": "K/P/S/C/X (领域无关)",
        "programming_extension": "PB-C 20 道 (编程领域)",
        "c_confidence_core": "PC-C 5 道 (领域无关)",
    }

    # 4. 写回
    with open(Q_MATRIX_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print()
    print(f"✅ Q 矩阵更新完成: {len(data['problems'])} 题")
    print(f"   - PB-Q (K/P/S 主导): {sum(1 for p in data['problems'] if p['problem_id'].startswith('PB-Q'))}")
    print(f"   - PB-C (C 主导, 编程扩展): {sum(1 for p in data['problems'] if p['problem_id'].startswith('PB-C'))}")
    print(f"   - PC-C (C 主导, 领域无关): {sum(1 for p in data['problems'] if p['problem_id'].startswith('PC-C'))}")
    print(f"   - 总题数: {len(data['problems'])}")


if __name__ == "__main__":
    main()
