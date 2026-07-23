"""v0.54.3-b: 追加 5 道 X-external-support 主导题到 data/python_basics_q_matrix.json.

按 v0.54.3 设计文档 (research/90-mvp/11-phase5-x-external-support-questions-design.md)
生成 5 道 X-external-support 主导题 (PC-X01 ~ PC-X05), 领域无关 (跨数学/语文/英语/物理/化学通用).

字段扩展:
  - domain_agnostic: True  # 跨学科通用
  - x_dimension_type: tool_selection / note_quality / memory_use_strategy / scaffolding_dependency / external_support_synthesis
  - 跟 v0.54.2 PC-C 5 道 (C-confidence 领域无关) 区分: problem_id 前缀 PC-X vs PC-C

5D 完整性目标: K/P/S/C-confidence/X-external-support 全部真评估 (5/5 巩固)
编程扩展: 20 道 PB-C 保留, 评估 programming_debug_score (独立字段)

运行: python scripts/add_pc_x_questions.py
"""
import json
from pathlib import Path

Q_MATRIX_PATH = Path("data/python_basics_q_matrix.json")


# 5 道 X-external-support 主导题 (按 v0.54.3 设计)
PC_X_QUESTIONS = [
    {
        "problem_id": "PC-X01",
        "topic": "cross_subject",
        "skill_name": "工具选择",
        "bloom_goal_id": "cross_subject-L3",
        "problem_text": (
            "遇到难题你用什么工具？\n"
            "A. 不查工具\n"
            "B. 查字典/计算器/实验仪器\n"
            "C. 查笔记\n"
            "D. 查 AI 助手\n"
            "E. 综合（B + C + D）"
        ),
        "correct_answer": "E (综合). 多工具组合是 X 维度最佳策略.",
        "bloom_layer_observed": "L3",
        "a_specialized": [0.2, 0.2, 0.2, 0.2, 1.0],  # X 主导
        "mirt_params": {"difficulty": 0.0, "discrimination": 1.0, "guessing": 0.0},
        "misconceptions": ["M-illinois-tool-avoidance"],
        "intervention_types": ["EXPLANATION", "SCAFFOLDING"],
        "x_dimension_type": "tool_selection",
        "domain_agnostic": True,
        "partial_credit_rubric": {
            "0.0": "选 A (不查工具) — 工具逃避",
            "0.3": "选 D (单 AI 助手) — 过度依赖单一工具",
            "0.6": "选 B 或 C (单类工具) — 单一策略",
            "1.0": "选 E (综合工具) — X 维度最佳",
        },
    },
    {
        "problem_id": "PC-X02",
        "topic": "cross_subject",
        "skill_name": "笔记质量",
        "bloom_goal_id": "cross_subject-L4",
        "problem_text": (
            "好的笔记应包含什么？\n"
            "A. 答案\n"
            "B. 答案 + 思路\n"
            "C. 答案 + 思路 + 易错点\n"
            "D. 全部（答案 + 思路 + 易错点 + 反思 + 跨学科联系）"
        ),
        "correct_answer": "D (全部). 完整笔记是 X 维度高质量标志.",
        "bloom_layer_observed": "L4",
        "a_specialized": [0.2, 0.2, 0.4, 0.2, 1.0],  # X + S (笔记质量涉及策略)
        "mirt_params": {"difficulty": 0.0, "discrimination": 1.0, "guessing": 0.0},
        "misconceptions": [],
        "intervention_types": ["EXPLANATION", "SCAFFOLDING"],
        "x_dimension_type": "note_quality",
        "domain_agnostic": True,
        "partial_credit_rubric": {
            "0.0": "选 A (仅答案)",
            "0.3": "选 B (答案+思路)",
            "0.6": "选 C (答案+思路+易错点)",
            "1.0": "选 D (全部) — X 维度高质量笔记",
        },
    },
    {
        "problem_id": "PC-X03",
        "topic": "cross_subject",
        "skill_name": "记忆使用策略",
        "bloom_goal_id": "cross_subject-L5",
        "problem_text": (
            "你如何决定\"是否查之前类似题\"？\n"
            "A. 每次都查 (过度依赖)\n"
            "B. 偶尔查\n"
            "C. 不查 (过度自信)\n"
            "D. 综合（偶尔查 + 记在脑里 + 标注重点）"
        ),
        "correct_answer": "D (综合). 平衡记忆使用是 X 维度元认知.",
        "bloom_layer_observed": "L5",
        "a_specialized": [0.2, 0.2, 0.2, 0.2, 1.1],  # X 主导
        "mirt_params": {"difficulty": 0.2, "discrimination": 1.0, "guessing": 0.0},
        "misconceptions": ["M-illinois-overconfidence", "M-illinois-overdependence"],
        "intervention_types": ["EXPLANATION", "SCAFFOLDING"],
        "x_dimension_type": "memory_use_strategy",
        "domain_agnostic": True,
        "partial_credit_rubric": {
            "0.0": "选 C (不查) — 过度自信",
            "0.3": "选 A (每次都查) — 过度依赖",
            "0.6": "选 B (偶尔查) — 单策略",
            "1.0": "选 D (综合策略) — X 维度平衡",
        },
    },
    {
        "problem_id": "PC-X04",
        "topic": "cross_subject",
        "skill_name": "支架依赖度",
        "bloom_goal_id": "cross_subject-L5",
        "problem_text": (
            "遇到新概念你如何应对？\n"
            "A. 等老师讲 (被动)\n"
            "B. 看 worked example (高依赖)\n"
            "C. 直接尝试 (低依赖)\n"
            "D. 综合 (worked example + 直接尝试 + 讨论)"
        ),
        "correct_answer": "D (综合). 平衡支架依赖是 X 维度元认知.",
        "bloom_layer_observed": "L5",
        "a_specialized": [0.2, 0.2, 0.3, 0.3, 1.0],  # X 主导
        "mirt_params": {"difficulty": 0.2, "discrimination": 1.0, "guessing": 0.0},
        "misconceptions": ["M-illinois-scaffolding-overdependence"],
        "intervention_types": ["EXPLANATION", "SCAFFOLDING"],
        "x_dimension_type": "scaffolding_dependency",
        "domain_agnostic": True,
        "partial_credit_rubric": {
            "0.0": "选 A (等老师讲) — 完全依赖",
            "0.3": "选 C (直接尝试) — 不借力",
            "0.6": "选 B (worked example) — 单一支架",
            "1.0": "选 D (综合) — X 维度平衡",
        },
    },
    {
        "problem_id": "PC-X05",
        "topic": "cross_subject",
        "skill_name": "综合 External Support",
        "bloom_goal_id": "cross_subject-L6",
        "problem_text": (
            "综合 External Support 评估：\n"
            "1. 工具使用频率（每天用几次字典/计算器/AI？）\n"
            "2. 笔记习惯（每次学习是否做笔记？质量如何？）\n"
            "3. 记忆使用（如何决定查/记脑里？）\n"
            "4. 求助策略（独立思考 + 查资料 + 问老师？）\n"
            "请综合评估你的 External Support 使用水平 (0-10 分)."
        ),
        "correct_answer": (
            "综合 External Support 评估. "
            "高分 (8-10): 工具 + 笔记 + 记忆 + 求助 4 维度都平衡. "
            "中分 (5-7): 部分维度平衡. "
            "低分 (0-4): 4 维度都不平衡."
        ),
        "bloom_layer_observed": "L6",
        "a_specialized": [0.2, 0.2, 0.3, 0.3, 1.1],  # X 主导
        "mirt_params": {"difficulty": 0.3, "discrimination": 1.0, "guessing": 0.0},
        "misconceptions": [],
        "intervention_types": ["EXPLANATION", "SCAFFOLDING"],
        "x_dimension_type": "external_support_synthesis",
        "domain_agnostic": True,
        "partial_credit_rubric": {
            "0.0": "低分 (0-4) — 4 维度都不平衡",
            "0.3": "中低分 (4-5)",
            "0.6": "中分 (6-7)",
            "1.0": "高分 (8-10) — X 维度平衡",
        },
    },
]


def main() -> None:
    # 1. 读现有 Q 矩阵
    with open(Q_MATRIX_PATH, encoding="utf-8") as f:
        data = json.load(f)

    # 2. 检查 ID 不重复
    existing_ids = {p["problem_id"] for p in data["problems"]}
    for q in PC_X_QUESTIONS:
        if q["problem_id"] in existing_ids:
            print(f"⚠️ {q['problem_id']} 已存在, 跳过")
        else:
            data["problems"].append(q)
            print(f"✅ 添加 {q['problem_id']} ({q['x_dimension_type']}, 领域无关)")

    # 3. 更新 metadata
    if "metadata" not in data:
        data["metadata"] = {}
    data["metadata"]["version"] = "v0.54.3"
    data["metadata"]["phase"] = 5
    data["metadata"]["x_external_support_questions_count"] = sum(
        1 for p in data["problems"] if p["problem_id"].startswith("PC-X")
    )
    data["metadata"]["c_confidence_questions_count"] = sum(
        1 for p in data["problems"] if p["problem_id"].startswith("PC-C")
    )
    data["metadata"]["c_programming_questions_count"] = sum(
        1 for p in data["problems"] if p["problem_id"].startswith("PB-C")
    )
    data["metadata"]["total_questions"] = len(data["problems"])
    data["metadata"]["last_updated"] = "2026-07-23"
    data["metadata"]["dual_layer_architecture_5d_complete"] = True

    # 4. 写回
    with open(Q_MATRIX_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print()
    print(f"✅ Q 矩阵更新完成: {len(data['problems'])} 题")
    print(f"   - PB-Q (K/P/S 主导): {sum(1 for p in data['problems'] if p['problem_id'].startswith('PB-Q'))}")
    print(f"   - PB-C (C 主导, 编程扩展): {sum(1 for p in data['problems'] if p['problem_id'].startswith('PB-C'))}")
    print(f"   - PC-C (C 主导, 领域无关): {sum(1 for p in data['problems'] if p['problem_id'].startswith('PC-C'))}")
    print(f"   - PC-X (X 主导, 领域无关): {sum(1 for p in data['problems'] if p['problem_id'].startswith('PC-X'))}")
    print(f"   - 总题数: {len(data['problems'])}")


if __name__ == "__main__":
    main()
