#!/usr/bin/env python3
"""v0.56.1 一次性脚本: 重跑被 LLM judge fallback 误判的题.

触发背景 (Bisen 2026-07-24 22:24):
  lbc001 答 PB-Q26 (L6 闭包设计), 答案完全正确 (用 nonlocal)
  LLM judge 返回非 JSON 格式 → 触发 /api/judge 端点旧版 fallback
  旧 fallback 走字符串严格相等比较 (nonlocal 答案 vs list 包装答案 字面不同)
  → score=0, correct=0, 5D P 维度被错罚

本脚本作用:
  1. 扫 web/ecos.db 里所有学生 response_history
  2. 找出 ai_reasoning == "（自动评判）答案文本匹配" 的条目 (被 fallback 误判的题)
  3. 用现版 /api/judge retry helper 重跑 LLM judge
  4. 成功 → 更新 score / correct / ai_reasoning / needs_rejudge=False
  5. 仍失败 → 标 needs_rejudge=True, score 写 None
  6. 跑完打印 summary (修复条数 / 重判失败条数 / 学生 ID 列表)

可重入 (idempotent): 已重跑过的条目 (ai_reasoning != "（自动评判）答案文本匹配" 且 has needs_rejudge 标记) 不会重复处理.

用法:
    python scripts/rejudge_misjudged.py [--student lbc001] [--dry-run]
        --student: 只处理指定学生 ID (默认全部)
        --dry-run: 只扫描不写入
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

# 项目根目录加入 sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# 标记: v0.56.1 前的 fallback 是这个 reasoning 字符串
FALLBACK_REASONING = "（自动评判）答案文本匹配"


def find_misjudged_entries(db_path: str, student_filter: str | None) -> list[dict]:
    """扫 DB 找出被 fallback 误判的 response_history 条目.

    Returns:
        list of {"student_id", "history_index", "problem_id", "user_answer", "correct_answer", ...}
    """
    results = []
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        if student_filter:
            cur.execute(
                "SELECT student_id, response_history FROM students WHERE student_id = ?",
                (student_filter,),
            )
        else:
            cur.execute("SELECT student_id, response_history FROM students")
        rows = cur.fetchall()

        for student_id, rh_json in rows:
            if not rh_json:
                continue
            try:
                history = json.loads(rh_json)
            except json.JSONDecodeError:
                continue
            for idx, entry in enumerate(history):
                if not isinstance(entry, dict):
                    continue
                # 识别 v0.56.1 前 fallback 误判的条目
                if entry.get("ai_reasoning") == FALLBACK_REASONING:
                    results.append({
                        "student_id": student_id,
                        "history_index": idx,
                        "problem_id": entry.get("problem_id"),
                        "user_answer": entry.get("user_answer"),
                        "correct_answer": entry.get("correct_answer"),
                        "bloom_level": entry.get("bloom_level"),
                        "old_score": entry.get("score"),
                        "old_correct": entry.get("correct"),
                    })
    return results


def load_problem_meta(problem_id: str) -> dict | None:
    """从 Q 矩阵读题目元信息 (problem_text, correct_answer)."""
    from web.api.qmatrix import get_question_detail
    return get_question_detail(problem_id)


def build_judge_prompt(problem_text: str, correct_answer: str, student_answer: str) -> str:
    return f"""你是一位严格的 Python 老师。请评判学生答案是否正确。

题目：
{problem_text}

正确答案：
{correct_answer}

学生答案：
{student_answer}

请以 JSON 格式返回评判结果（只返回 JSON，不要其他内容）：
{{"correct": true/false, "reasoning": "简短说明为什么对或错（1-2句话）"}}
"""


def rejudge_with_retry(llm_client, prompt: str) -> tuple[dict | None, int]:
    """调 web.api.app._call_llm_judge_with_retry (Bisen 原则 retry).

    Returns:
        (result_dict, attempts) on success
        (None, attempts) on failure
    """
    from web.api.app import _call_llm_judge_with_retry
    return _call_llm_judge_with_retry(llm_client, prompt)


def update_history_entry(
    db_path: str, student_id: str, history_index: int, updated_entry: dict
) -> None:
    """更新 response_history 单条 entry (其余条目保持不变).

    注: 这是直接 SQL UPDATE, 绕过 save_student_state (因为脚本运行时不持有 engine 实例).
    """
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT response_history FROM students WHERE student_id = ?", (student_id,)
        )
        row = cur.fetchone()
        if not row or not row[0]:
            return
        history = json.loads(row[0])
        if history_index >= len(history):
            return
        history[history_index] = updated_entry
        cur.execute(
            "UPDATE students SET response_history = ? WHERE student_id = ?",
            (json.dumps(history, ensure_ascii=False), student_id),
        )
        conn.commit()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--student", default=None, help="只处理指定学生 ID (默认全部)")
    parser.add_argument("--dry-run", action="store_true", help="只扫描不写入")
    parser.add_argument("--db", default="web/ecos.db", help="SQLite DB 路径")
    args = parser.parse_args()

    print(f"🔍 扫描 DB: {args.db}")
    if args.student:
        print(f"   学生过滤: {args.student}")
    if args.dry_run:
        print(f"   ⚠️  DRY-RUN 模式: 只扫描不写入")

    misjudged = find_misjudged_entries(args.db, args.student)
    print(f"\n📊 发现 {len(misjudged)} 条被 fallback 误判的 entry")

    if not misjudged:
        print("✅ 没有需要重判的 entry")
        return 0

    # 拿到 LLM client
    print("\n🤖 初始化 LLM client...")
    from web.api.app import get_llm
    llm = get_llm()
    print(f"   LLM client ready")

    # 按 student_id 分组
    from collections import defaultdict
    by_student = defaultdict(list)
    for m in misjudged:
        by_student[m["student_id"]].append(m)

    success_count = 0
    fail_count = 0
    fail_list = []

    for student_id, entries in by_student.items():
        print(f"\n👤 处理学生 {student_id}: {len(entries)} 条误判")
        for entry in entries:
            problem_id = entry["problem_id"]
            user_answer = entry["user_answer"] or ""
            correct_answer = entry["correct_answer"] or ""

            # 拿 Q 矩阵元信息
            prob = load_problem_meta(problem_id)
            if not prob:
                print(f"   ⚠️  {problem_id}: Q 矩阵无此题, 跳过 (保留 needs_rejudge=True)")
                fail_count += 1
                fail_list.append((student_id, problem_id, "Q 矩阵无此题"))
                continue

            problem_text = prob.get("problem_text", "")
            if not problem_text or not correct_answer:
                # fallback 字符串匹配时, correct_answer 可能为 null
                # 从 Q 矩阵补全
                correct_answer = prob.get("correct_answer", correct_answer)
                problem_text = problem_text or "(题目描述缺失)"

            if not user_answer:
                print(f"   ⚠️  {problem_id}: user_answer 为空, 跳过")
                fail_count += 1
                fail_list.append((student_id, problem_id, "user_answer 为空"))
                continue

            prompt = build_judge_prompt(problem_text, correct_answer, user_answer)
            result, attempts = rejudge_with_retry(llm, prompt)

            if result is None:
                # 3 次 retry 失败: 标 needs_rejudge=True, score 写 None
                print(f"   ❌ {problem_id}: LLM judge 3 次 retry 失败, 标 needs_rejudge=True")
                if not args.dry_run:
                    updated = dict(entry)
                    updated["score"] = None
                    updated["needs_rejudge"] = True
                    updated["ai_reasoning"] = "（脚本重判失败，需要人工复核）"
                    update_history_entry(args.db, student_id, entry["history_index"], updated)
                fail_count += 1
                fail_list.append((student_id, problem_id, "LLM retry 3 次失败"))
                continue

            # 成功: 更新 entry
            new_correct = bool(result.get("correct", False))
            new_reasoning = str(result.get("reasoning", ""))
            new_score = 1.0 if new_correct else 0.0

            print(
                f"   ✅ {problem_id}: correct={entry['old_correct']}→{int(new_correct)}, "
                f"score={entry['old_score']}→{new_score}, attempts={attempts}"
            )
            if not args.dry_run:
                updated = dict(entry)
                updated["correct"] = int(new_correct)
                updated["score"] = new_score
                updated["ai_reasoning"] = new_reasoning
                updated["needs_rejudge"] = False
                updated["rejudge_timestamp"] = "2026-07-24-v0.56.1-script"
                update_history_entry(args.db, student_id, entry["history_index"], updated)
            success_count += 1

    # Summary
    print("\n" + "=" * 60)
    print("📊 重判结果汇总")
    print("=" * 60)
    print(f"✅ 成功重判: {success_count} 条")
    print(f"❌ 失败 (需人工复核): {fail_count} 条")
    if fail_list:
        print("\n失败列表:")
        for sid, pid, reason in fail_list:
            print(f"   - {sid} / {pid}: {reason}")
    print(f"\n模式: {'DRY-RUN (未写入)' if args.dry_run else '已写入 DB'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
