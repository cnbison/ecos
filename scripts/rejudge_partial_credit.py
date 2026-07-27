#!/usr/bin/env python3
"""v0.58.1 一次性脚本: 用 v0.58.0 新 prompt (注入 partial_credit_rubric) 重判历史 C/X 维度题.

触发背景 (Bisen 2026-07-27 15:46 拍板):
  v0.54.0 partial credit 改造不彻底 — Q 矩阵 partial_credit_rubric 字段挂着但 LLM judge prompt 不消费.
  历史 80+ 道题 (lbc001 50+ + lbc002 32 道) 中所有带 partial_credit_rubric 的题 (20 道: PB-C01-15 + PC-C01-05) 都被
  LLM 按"二元 correct" 判分, 错失了 partial credit 评分 (例如 PC-C03 B 选按 rubric 0.3 档但被判 0.0).

本脚本作用:
  1. 加载 Q 矩阵, 列出所有有 partial_credit_rubric 的题 (20 道)
  2. 扫 lbc001 + lbc002 response_history
  3. 找出 problem_id 在 rubric 题集合里的 entry
  4. 用 v0.58.0 _call_llm_judge_with_retry + _build_judge_prompt (注入 rubric) 重判
  5. 成功 → 更新 score / correct / ai_reasoning / rejudge_timestamp
  6. 失败 (3 次 retry) → 标 needs_rejudge=True, score 写 None
  7. 跑完打印 summary (修复条数 / 重判失败条数 / 学生 ID 列表)

可修范围:
  ✅ response_history 里的 score / correct / ai_reasoning / needs_rejudge / rejudge_timestamp 字段
  ❌ 5D theta 状态 (贝叶斯在线更新, 不可逆 — 见 CLAUDE.md 防御性自检 [7])

可重入 (idempotent):
  - 默认: 跳过已 rejudge 过的 entry (有 rejudge_timestamp 字段标记)
  - --force: 强制重判所有匹配 entry, 覆盖之前 rejudge 结果

用法:
    python scripts/rejudge_partial_credit.py [--student lbc001] [--dry-run] [--limit 5] [--force]
        --student: 只处理指定学生 ID (默认 lbc001 + lbc002)
        --dry-run: 只扫描不写入
        --limit:   限制处理 entry 数 (避免 token 燃烧, 默认不限)
        --force:   强制重判已 rejudge 过的 entry (覆盖)
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 项目根目录加入 sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# v0.58.1 标记
REJUDGE_TAG = "2026-07-27-v0.58.1-partial-credit"


def load_rubric_problem_ids(q_matrix_path: str) -> Dict[str, Dict[str, Any]]:
    """加载所有有 partial_credit_rubric 的题目, 返回 {problem_id: 完整题目 dict}."""
    with open(q_matrix_path) as f:
        qdata = json.load(f)

    rubric_problems = {}
    for p in qdata.get("problems", []):
        if "partial_credit_rubric" in p:
            rubric_problems[p["problem_id"]] = p
    return rubric_problems


def find_rubric_entries(
    db_path: str,
    student_filter: Optional[str],
    rubric_problem_ids: set,
    force: bool,
) -> List[Dict[str, Any]]:
    """扫 DB 找需要重判的 entry.

    Returns:
        list of {student_id, history_index, entry dict, problem_meta}
    """
    candidates = []
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
                pid = entry.get("problem_id", "")
                if pid not in rubric_problem_ids:
                    continue
                # 可重入: 跳过已 rejudge 过的 (除非 --force)
                if not force and REJUDGE_TAG in str(entry.get("rejudge_timestamp", "")):
                    continue
                candidates.append({
                    "student_id": student_id,
                    "history_index": idx,
                    "entry": entry,
                })
    return candidates


def update_history_entry(
    db_path: str, student_id: str, history_index: int, updated_entry: dict
) -> None:
    """更新 response_history 单条 entry (其余条目保持不变)."""
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
    parser.add_argument("--student", default=None, help="只处理指定学生 ID (默认 lbc001 + lbc002)")
    parser.add_argument("--dry-run", action="store_true", help="只扫描不写入")
    parser.add_argument("--limit", type=int, default=None, help="限制处理 entry 数 (避免 token 燃烧)")
    parser.add_argument("--force", action="store_true", help="强制重判已 rejudge 过的 entry (覆盖)")
    parser.add_argument("--q-matrix", default="data/python_basics_q_matrix.json", help="Q 矩阵路径")
    parser.add_argument("--db", default="web/ecos.db", help="SQLite DB 路径")
    args = parser.parse_args()

    # 1. 加载 rubric 题
    print(f"📂 加载 Q 矩阵: {args.q_matrix}")
    rubric_problems = load_rubric_problem_ids(args.q_matrix)
    print(f"   发现 {len(rubric_problems)} 道带 partial_credit_rubric 的题:")
    for pid in sorted(rubric_problems):
        skill = rubric_problems[pid].get("skill_name", "?")
        print(f"   - {pid:8s} | {skill}")
    print()

    # 2. 扫 DB 找需要重判的 entry
    print(f"🔍 扫描 DB: {args.db}")
    if args.student:
        print(f"   学生过滤: {args.student}")
    print(f"   force 模式: {args.force}")
    candidates = find_rubric_entries(
        args.db, args.student, set(rubric_problems.keys()), args.force
    )
    print(f"   找到 {len(candidates)} 条需重判的 entry")
    print()

    if not candidates:
        print("✅ 没有需要重判的 entry (可重入 — 默认跳过已 rejudge 的)")
        return 0

    # 限制条数
    if args.limit:
        candidates = candidates[: args.limit]
        print(f"⚠️  限制处理 {args.limit} 条 (避免 token 燃烧)")
        print()

    # 3. 拿到 LLM client
    print("🤖 初始化 LLM client...")
    from web.api.app import get_llm
    llm = get_llm()
    print(f"   LLM client ready")
    print()

    # 4. 逐条重判
    success_count = 0
    fail_count = 0
    fail_list = []
    changed_count = 0  # 跟原 score 不一样的 (说明历史确实错判)

    from web.api.app import _build_judge_prompt, _call_llm_judge_with_retry, _parse_judge_result

    for cand in candidates:
        student_id = cand["student_id"]
        entry = cand["entry"]
        pid = entry.get("problem_id", "?")
        old_score = entry.get("score")
        old_correct = entry.get("correct")
        old_ai_reasoning = entry.get("ai_reasoning", "")

        # 拿题目完整信息
        prob = rubric_problems[pid]
        problem_text = prob.get("problem_text", "")
        correct_answer = prob.get("correct_answer", "")
        partial_credit_rubric = prob.get("partial_credit_rubric")
        user_answer = entry.get("user_answer", "")

        if not user_answer:
            print(f"   ⚠️  {student_id}/{pid}: user_answer 为空, 跳过")
            fail_count += 1
            fail_list.append((student_id, pid, "user_answer 为空"))
            continue

        # v0.58.0: 用 _build_judge_prompt 注入 rubric
        prompt = _build_judge_prompt(
            problem_text=problem_text,
            correct_answer=correct_answer,
            student_answer=user_answer,
            partial_credit_rubric=partial_credit_rubric,
        )
        result, attempts = _call_llm_judge_with_retry(llm, prompt)

        if result is None:
            # 3 次 retry 失败: 标 needs_rejudge=True, score=None
            print(f"   ❌ {student_id}/{pid}: LLM judge 3 次 retry 失败, 标 needs_rejudge=True")
            if not args.dry_run:
                updated = dict(entry)
                updated["score"] = None
                updated["needs_rejudge"] = True
                updated["ai_reasoning"] = f"（v0.58.1 rejudge 失败，需要人工复核）原 reasoning: {old_ai_reasoning}"
                updated["rejudge_timestamp"] = REJUDGE_TAG
                update_history_entry(args.db, student_id, cand["history_index"], updated)
            fail_count += 1
            fail_list.append((student_id, pid, "LLM retry 3 次失败"))
            continue

        # 成功: v0.58.0 _parse_judge_result 解析
        new_correct, new_score, new_reasoning = _parse_judge_result(result)

        # 检测是否变化
        score_changed = (old_score != new_score) and (old_score is not None)
        correct_changed = (old_correct != new_correct) and (old_correct is not None)
        if score_changed or correct_changed:
            changed_count += 1
            change_marker = "🔄"  # 表示改了
        else:
            change_marker = "✓"   # 没改

        print(
            f"   {change_marker} {student_id}/{pid}: "
            f"score={old_score}→{new_score}, correct={old_correct}→{int(new_correct)}, "
            f"attempts={attempts}"
        )
        if not args.dry_run:
            updated = dict(entry)
            updated["correct"] = int(new_correct)
            updated["score"] = new_score
            updated["ai_reasoning"] = new_reasoning
            updated["needs_rejudge"] = False
            updated["rejudge_timestamp"] = REJUDGE_TAG
            update_history_entry(args.db, student_id, cand["history_index"], updated)
        success_count += 1

    # 5. Summary
    print()
    print("=" * 60)
    print("📊 rejudge 结果汇总")
    print("=" * 60)
    print(f"✅ 成功重判: {success_count} 条")
    print(f"🔄 改了 score/correct: {changed_count} 条 (历史确实错判)")
    print(f"❌ 失败 (需人工复核): {fail_count} 条")
    if fail_list:
        print("\n失败列表:")
        for sid, pid, reason in fail_list:
            print(f"   - {sid} / {pid}: {reason}")
    print(f"\n模式: {'DRY-RUN (未写入)' if args.dry_run else '已写入 DB'}")
    print(f"\n⚠️  注意: 5D theta 状态不可逆, 本脚本只修 response_history 里的 score/correct/ai_reasoning 字段")
    return 0


if __name__ == "__main__":
    sys.exit(main())
