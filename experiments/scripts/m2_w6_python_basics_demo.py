#!/usr/bin/env python3
"""Python 基础认知干预 Demo（M2 W6）。

跑通 Python 基础 4-gate Demo：
  ① TC_python 跨越
  ② Bloom: Understand ≥ 0.85 AND Apply ≥ 0.75
  ③ Misconception 清零（M1-M8 全部消除）
  ④ C 是"挣来的"（伪置信 = false）

流程：
  Round 1: 学生回答问题 → Misconception 检测 → C 维度折扣
  干预：LLM 生成靶向干预（LLM 充当领域专家）
  Round 2: 重新回答相同问题 → 验证 misconception 清除

对应：research/00-overview/03-roadmap.md §2.4 M2 W6
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ecos.cta.belief_state import BloomLevel
from ecos.cta.content import (
    PYTHON_BASICS_MISCONCEPTION_LIBRARY_STR,
    PythonBasicsMisconceptionLibrary,
)
from ecos.cta.llm_critic.misconception_detector import MisconceptionDetector
from ecos.llm_client import ECOSLLMClient


def print_section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def print_subsection(title: str) -> None:
    print(f"\n## {title}")
    print("-" * 40)


def run_round1(client: ECOSLLMClient, detector: MisconceptionDetector) -> dict:
    """Round 1: 初始测量，检测学生 misconception"""
    print_section("Round 1: 初始 Belief State 测量")

    # 学生模拟回答（模拟带 Python misconception 的学生）
    student_answers = [
        {
            "qid": "PB-Q01",
            "problem": "以下代码的输出是什么？\n\nx = 5\nx = x + 1\nprint(x)",
            "answer": "x = x + 1？这不是无解吗？等号两边不相等，这代码肯定是错的。",
        },
        {
            "qid": "PB-Q02",
            "problem": "写一个计算 1+2+...+100 的 Python 程序",
            "answer": "for i in range(100):\n    total = total + i\nprint(total)",
        },
        {
            "qid": "PB-Q03",
            "problem": "以下代码的输出是什么？\n\nfor i in range(5):\n    print(i)",
            "answer": "输出应该是 0 1 2 3 4 5，因为 range(5) 就是从 0 数到 5。",
        },
        {
            "qid": "PB-Q04",
            "problem": "写一个函数判断一个数是否为质数",
            "answer": "def is_prime(n):\n    if n > 1:\n        return True\n    # 没有考虑 n <= 1 的情况，也没有循环检查因子",
        },
        {
            "qid": "PB-Q05",
            "problem": "递归和循环有什么区别？",
            "answer": "递归就是函数调用自己，循环就是重复执行一段代码，本质上是一样的，只是写法不同。",
        },
    ]

    results = []

    for item in student_answers:
        qid = item["qid"]
        problem = item["problem"]
        answer = item["answer"]

        print_subsection(f"{qid}: {problem[:60]}...")
        print(f"学生回答: {answer[:80]}...")

        # 检测 misconception
        detection = detector.detect(
            student_explanation=answer,
            problem=problem,
            library_str=PYTHON_BASICS_MISCONCEPTION_LIBRARY_STR,
        )

        print(f"  → 命中: {detection.misc_id or '无'}  置信度: {detection.confidence:.2f}")
        if detection.evidence_text:
            print(f"  → 证据: {detection.evidence_text[:80]}...")

        # 模拟 BloomLevel（基于题目类型推断）
        if qid == "PB-Q01":
            bloom = BloomLevel.UNDERSTAND
            correct = detection.misc_id in ("M1", "M2")  # 答错了才触发
            skill_id = "python.variables.assignment"
        elif qid == "PB-Q02":
            bloom = BloomLevel.APPLY
            correct = False  # 遗漏了 total=0 初始化，有 bug
            skill_id = "python.loops.for_range"
        elif qid == "PB-Q03":
            bloom = BloomLevel.UNDERSTAND
            correct = detection.misc_id == "M3"  # off-by-one 错误
            skill_id = "python.loops.for_range"
        elif qid == "PB-Q04":
            bloom = BloomLevel.APPLY
            correct = False  # 质数判断逻辑不完整
            skill_id = "python.functions.return_value"
        else:
            bloom = BloomLevel.ANALYZE
            correct = detection.misc_id == "M5"  # 递归=循环
            skill_id = "python.functions.recursion"

        results.append({
            "qid": qid,
            "detection": detection,
            "bloom": bloom,
            "correct": correct,
            "skill_id": skill_id,
            "problem": problem,
            "answer": answer,
        })

    # 汇总 Round 1
    print_subsection("Round 1 汇总")
    miscs_detected = set(r["detection"].misc_id for r in results if r["detection"].misc_id)
    print(f"  命中 misconception: {sorted(miscs_detected) or '无'}")

    return {
        "round": 1,
        "results": results,
        "miscs_detected": sorted(miscs_detected),
        "timestamp": datetime.now().isoformat(),
    }


def generate_interventions(
    client: ECOSLLMClient, detections: list[dict]
) -> dict[str, str]:
    """根据检测到的 misconception，LLM 生成靶向干预"""
    print_section("干预生成（LLM 充当领域专家）")

    # 按 misconception 分组干预
    interventions = {}

    for det in detections:
        misc_id = det["detection"].misc_id
        if not misc_id:
            continue

        # 获取 misconception 条目
        lib = PythonBasicsMisconceptionLibrary()
        entry = lib.get(misc_id)
        if not entry:
            continue

        prompt = f"""你是一位 Python 教学专家。学生的回答触发了以下 misconception：

Misconception ID: {entry.misc_id}
名称: {entry.name}
描述: {entry.description}

学生回答证据: {det["detection"].evidence_text}

请生成一段针对该 misconception 的靶向干预（100-200字），要求：
1. 用学生能理解的类比或解释
2. 直接指出学生理解的错误所在
3. 给出正确的理解

干预内容："""

        response = client.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            strip_think=True,
        )

        interventions[misc_id] = response
        print_subsection(f"【{misc_id}】{entry.name}")
        print(response[:200] + "..." if len(response) > 200 else response)

    return interventions


def run_round2(
    client: ECOSLLMClient, detector: MisconceptionDetector, interventions: dict[str, str]
) -> dict:
    """Round 2: 执行干预后重新测量"""
    print_section("Round 2: 干预后 Belief State 重新测量")

    # 学生重新回答（吸收干预后的正确理解）
    student_answers_r2 = [
        {
            "qid": "PB-Q01",
            "problem": "以下代码的输出是什么？\n\nx = 5\nx = x + 1\nprint(x)",
            # 吸收干预后：理解赋值是"存回去"，不是等式
            "answer": "x = 5 然后 x = x + 1，先算右边 x+1=6，再把 6 存回 x，所以输出 6。",
        },
        {
            "qid": "PB-Q02",
            "problem": "写一个计算 1+2+...+100 的 Python 程序",
            # 吸收干预后：理解了变量初始化
            "answer": "total = 0\nfor i in range(1, 101):\n    total = total + i\nprint(total)",
        },
        {
            "qid": "PB-Q03",
            "problem": "以下代码的输出是什么？\n\nfor i in range(5):\n    print(i)",
            # 吸收干预后：理解了 range(5) 是 0-4（开区间）
            "answer": "输出 0 1 2 3 4。range(5) 的 stop 是开区间，不包含 5。",
        },
        {
            "qid": "PB-Q04",
            "problem": "写一个函数判断一个数是否为质数",
            # 吸收干预后：理解了 void 函数
            "answer": "def is_prime(n):\n    if n <= 1:\n        return False\n    for i in range(2, int(n**0.5)+1):\n        if n % i == 0:\n            return False\n    return True",
        },
        {
            "qid": "PB-Q05",
            "problem": "递归和循环有什么区别？",
            # 吸收干预后：理解了递归需要 base case，递归是化归思想
            "answer": "递归通过函数调用自身把问题化为更小的同类子问题，需要 base case 终止。循环是重复执行代码块。递归天然适合树形结构，循环适合线性遍历。两者有各自的优势场景。",
        },
    ]

    results = []
    for item in student_answers_r2:
        qid = item["qid"]
        problem = item["problem"]
        answer = item["answer"]

        print_subsection(f"{qid}: {problem[:60]}...")
        print(f"学生回答: {answer[:80]}...")

        detection = detector.detect(
            student_explanation=answer,
            problem=problem,
            library_str=PYTHON_BASICS_MISCONCEPTION_LIBRARY_STR,
        )

        print(f"  → 命中: {detection.misc_id or '无'}  置信度: {detection.confidence:.2f}")

        results.append({
            "qid": qid,
            "detection": detection,
        })

    print_subsection("Round 2 汇总")
    miscs_detected_r2 = set(r["detection"].misc_id for r in results if r["detection"].misc_id)
    print(f"  命中 misconception: {sorted(miscs_detected_r2) or '无'}")

    return {
        "round": 2,
        "results": results,
        "miscs_detected": sorted(miscs_detected_r2),
        "timestamp": datetime.now().isoformat(),
    }


def evaluate_4gate(round1: dict, round2: dict, interventions: dict) -> dict:
    """评估 4-gate 达标情况"""
    print_section("4-Gate 达标评估")

    lib = PythonBasicsMisconceptionLibrary()
    all_miscs = {e.misc_id for e in lib.all_entries()}
    r1_miscs = set(round1["miscs_detected"])
    r2_miscs = set(round2["miscs_detected"])

    gate1_tc = "TC_python 跨越：学生理解 Skill 是按 description 相关性自主加载的能力（需人工评估）"
    gate2_bloom = "Bloom: U ≥ 0.85, A ≥ 0.75（BeliefEngine.update() 后定量评估）"
    gate3_misc = f" Misconception 清零: Round1 {r1_miscs} → Round2 {r2_miscs or '∅'}"
    gate4_confidence = "C 是挣来的: discount_factor → 1.0（伪置信 = false）"

    print(f"  Gate ① TC_python 跨越: {gate1_tc}")
    print(f"  Gate ② Bloom U/A: {gate2_bloom}")
    print(f"  Gate ③ Misc 清零: {gate3_misc}")
    print(f"  Gate ④ C 维度: {gate4_confidence}")

    # 计算清除率
    cleared = r1_miscs - r2_miscs
    remaining = r2_miscs
    print(f"\n  ✅ 清除: {sorted(cleared) or '无'}")
    print(f"  ❌ 残留: {sorted(remaining) or '无'}")

    return {
        "gate1_tc": gate1_tc,
        "gate2_bloom": gate2_bloom,
        "gate3_misc_cleared": sorted(cleared),
        "gate3_misc_remaining": sorted(remaining),
        "gate4_confidence": gate4_confidence,
    }


def _detection_to_dict(det) -> dict:
    """将 MisconceptionDetectionOutput dataclass 转为 dict"""
    return {
        "misc_id": det.misc_id,
        "confidence": det.confidence,
        "evidence_text": det.evidence_text,
        "correction_strategy": det.correction_strategy,
    }


def main() -> None:
    print_section("ECOS Python 基础 4-Gate Demo")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("LLM: MiniMax (充当领域专家 + 干预生成)")

    # 初始化
    client = ECOSLLMClient.from_env("minimax")
    detector = MisconceptionDetector(client)

    print("\n初始化完成，开始 Round 1...")

    # Round 1
    round1 = run_round1(client, detector)
    time.sleep(2)

    # 生成干预
    interventions = generate_interventions(client, round1["results"])
    time.sleep(2)

    # Round 2
    round2 = run_round2(client, detector, interventions)
    time.sleep(1)

    # 4-gate 评估
    gate_results = evaluate_4gate(round1, round2, interventions)

    # 构建 JSON 可序列化报告
    def _fmt_round(r: dict) -> dict:
        return {
            "round": r["round"],
            "miscs_detected": r["miscs_detected"],
            "timestamp": r["timestamp"],
            "results": [
                {
                    "qid": item["qid"],
                    "detection": _detection_to_dict(item["detection"]),
                    "bloom": item["bloom"].name,
                    "correct": item["correct"],
                    "skill_id": item["skill_id"],
                }
                for item in r["results"]
            ],
        }

    report = {
        "demo": "Python Basics 4-Gate Demo",
        "timestamp": datetime.now().isoformat(),
        "round1": _fmt_round(round1),
        "interventions": interventions,
        "round2": _fmt_round(round2),
        "gate_results": gate_results,
    }

    output_path = Path(__file__).parent.parent.parent / "discussions" / f"2026-07-06-python-basics-4gate-demo.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n报告已保存: {output_path}")


if __name__ == "__main__":
    main()
