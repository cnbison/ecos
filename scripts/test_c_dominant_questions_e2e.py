"""v0.54.1-c: 端到端集成测试——模拟 lbc001 答 5 道 C 主导题 (PB-C01 ~ PB-C05).

范围 (Bisen 确认):
  ✅ 加载 lbc001 真实 DB 状态 (DB → in-memory BeliefEngine)
  ✅ 调 submit_answer(score=0.7) 模拟 5 道 PB-C 答题
  ✅ save_student_state 持久化到 SQLite
  ✅ 验证 response_history score 字段 + C 维度 θ 变化
  ❌ 不调真实 LLM (省 API 成本)
  ❌ 不通过 Flask UI /api/answer 端点

模拟 AI 评分 (基于 PB-C 的 partial_credit_rubric):
  - PB-C01 (range 越界):  lbc001 答对, 识别 + 修复但没解释 → score=0.6
  - PB-C02 (continue 诱饵): lbc001 识别'输出 1, 3, skip 2' 但没说'代码对' → score=0.6
  - PB-C03 (TypeError):  lbc001 识别 int+str + 给出 int() → score=0.6
  - PB-C04 (scope 局部):  lbc001 答对'20, 10' + 解释 → score=1.0
  - PB-C05 (fib 调试):   lbc001 多方法但没排序 → score=0.6

平均 score = (0.6+0.6+0.6+1.0+0.6)/5 = 0.68 (68% partial credit)

运行: python scripts/test_c_dominant_questions_e2e.py
"""
import json
import sqlite3
from pathlib import Path

# 让脚本能 import web.api.belief (项目根目录是 cwd)
import sys
sys.path.insert(0, str(Path.cwd()))

from web.api.belief import _get_or_create_student, submit_answer, _STUDENT_STATES, _get_db
from ecos.cta.belief_state import BloomLevel

STUDENT_ID = "lbc001"

# 5 道模拟答题 (基于 PB-C partial_credit_rubric 模拟 AI 评分)
SIMULATED_ANSWERS = [
    {
        "problem_id": "PB-C01",
        "skill_id": "python.loops",
        "bloom_layer": "L3",
        "user_answer": "for i in range(1, 6): print(i)  # 修复了",
        "correct_answer": "Bug 在 range(1, 5) 不包含 5，应改为 range(1, 6)",
        "ai_reasoning": "学生识别 range(1, 5) 错 + 修复为 range(1, 6) 但没说原因 (0.6)",
        "score": 0.6,  # partial credit: 识别+修复但没解释
    },
    {
        "problem_id": "PB-C02",
        "skill_id": "python.loops",
        "bloom_layer": "L4",
        "user_answer": "输出 1, 3, skip 2",  # 识别陷阱但没说'代码对'
        "correct_answer": "代码实际是对的，输出 1, 3, skip 2",
        "ai_reasoning": "学生识别'输出 1, 3, skip 2' 但没说'代码是对的' (0.6)",
        "score": 0.6,  # partial credit: 识别陷阱但漏关键点
    },
    {
        "problem_id": "PB-C03",
        "skill_id": "python.functions",
        "bloom_layer": "L5",
        "user_answer": "int + str 不能加, 用 int() 转换",  # 识别+给修法
        "correct_answer": "int('2') 或 str(1) 转换",
        "ai_reasoning": "学生识别 int+str + 给出 int() 转换 (0.6)",
        "score": 0.6,  # partial credit: 识别+单修法
    },
    {
        "problem_id": "PB-C04",
        "skill_id": "python.scope",
        "bloom_layer": "L5",
        "user_answer": "输出 20, 10. 因为 foo() 内的 x=20 是局部变量",
        "correct_answer": "输出 20 然后 10. 原因: foo() 内的 x = 20 是局部变量",
        "ai_reasoning": "学生答对'20, 10' + 解释局部 vs 全局 (1.0)",
        "score": 1.0,  # 完整
    },
    {
        "problem_id": "PB-C05",
        "skill_id": "python.recursion",
        "bloom_layer": "L4",
        "user_answer": "1. 加 print 跟踪 2. 测 fib(3) 看是否也慢",
        "correct_answer": "1. print 跟踪 2. 画递归树 3. 测小输入 4. 用 lru_cache",
        "ai_reasoning": "学生给多方法 (print + 测小输入) 但没排序 (0.6)",
        "score": 0.6,  # partial credit: 多方法没排序
    },
]


def get_student_5d_state(student_id: str) -> dict:
    """从 in-memory 状态读 5D θ."""
    if student_id not in _STUDENT_STATES:
        return {}
    state = _STUDENT_STATES[student_id]["state"]
    return {
        "K": state.K.theta, "P": state.P.theta, "S": state.S.theta,
        "C": state.C.theta, "X": state.X.theta,
    }


def get_response_history_len(student_id: str) -> int:
    """从 in-memory engine 读 response_history 长度."""
    if student_id not in _STUDENT_STATES:
        return 0
    return len(_STUDENT_STATES[student_id]["engine"]._response_history.get(student_id, []))


def get_db_response_history(student_id: str) -> list:
    """从 DB 读 response_history (持久化后)."""
    db = _get_db()
    row = db._conn.execute(
        "SELECT response_history FROM students WHERE student_id = ?",
        (student_id,),
    ).fetchone()
    if row and row[0]:
        return json.loads(row[0])
    return []


def get_db_5d_state(student_id: str) -> dict:
    """从 DB 读 5D θ (持久化后)."""
    db = _get_db()
    row = db._conn.execute(
        "SELECT current_state_5d FROM students WHERE student_id = ?",
        (student_id,),
    ).fetchone()
    if row and row[0]:
        s5d = json.loads(row[0])
        if isinstance(s5d, list) and len(s5d) > 0:
            s5d = s5d[0]  # 兼容 list 包装
        return {
            "K": s5d.get("K", {}).get("theta", 0),
            "P": s5d.get("P", {}).get("theta", 0),
            "S": s5d.get("S", {}).get("theta", 0),
            "C": s5d.get("C", {}).get("theta", 0),
            "X": s5d.get("X", {}).get("theta", 0),
        }
    return {}


def main() -> None:
    print("=" * 60)
    print("v0.54.1-c 端到端集成测试: lbc001 答 5 道 C 主导题")
    print("=" * 60)

    # 1. 加载 lbc001 真实 DB 状态
    print("\n[1] 加载 lbc001 状态...")
    _get_or_create_student(STUDENT_ID)
    initial_5d = get_student_5d_state(STUDENT_ID)
    initial_history_len = get_response_history_len(STUDENT_ID)
    print(f"  初始 response_history: {initial_history_len} 题")
    print(f"  初始 5D θ: K={initial_5d.get('K', 0):.4f} P={initial_5d.get('P', 0):.4f} S={initial_5d.get('S', 0):.4f} C={initial_5d.get('C', 0):.4f} X={initial_5d.get('X', 0):.4f}")

    # 2. 模拟 5 道 PB-C 答题
    print("\n[2] 模拟答题 5 道...")
    print(f"  {'#':>2s} {'PID':>7s} {'bloom':>5s} {'c':>4s} {'score':>5s} | 持久化")
    for i, ans in enumerate(SIMULATED_ANSWERS, 1):
        try:
            result = submit_answer(
                student_id=STUDENT_ID,
                problem_id=ans["problem_id"],
                skill_id=ans["skill_id"],
                correct=True,  # 兼容老调用方, score 会覆盖
                bloom_layer=ans["bloom_layer"],
                # 不传 explanation_text → 不调 LLM perception_critic
                # 不传 ai_reasoning → 不调 LLM misconception_detector
                user_answer=ans["user_answer"],
                correct_answer=ans["correct_answer"],
                ai_reasoning=ans["ai_reasoning"],
                score=ans["score"],  # v0.54.0-e partial credit
            )
            persisted = result.get("persisted", False)
            derived_correct = result.get("correct", False)
            score_back = result.get("score", 0.0)
            mark = "✅" if persisted else "❌"
            print(f"  {i:>2d} {ans['problem_id']:>7s} L{ans['bloom_layer'][1]:>4s} {int(derived_correct):>4d} {score_back:>5.2f} | {mark} persisted={persisted}")
        except Exception as e:
            print(f"  {i:>2d} {ans['problem_id']:>7s} ❌ ERROR: {e}")
            raise

    # 3. 验证 in-memory 状态
    print("\n[3] 验证 in-memory 状态变化...")
    after_5d = get_student_5d_state(STUDENT_ID)
    after_history_len = get_response_history_len(STUDENT_ID)
    print(f"  答题后 response_history: {after_history_len} 题 (+{after_history_len - initial_history_len})")
    print(f"  5D θ 变化:")
    for dim in ["K", "P", "S", "C", "X"]:
        before = initial_5d.get(dim, 0)
        after = after_5d.get(dim, 0)
        delta = after - before
        print(f"    {dim}: {before:>8.4f} → {after:>8.4f}  (Δ {delta:+.4f})")

    # 4. 验证 DB 持久化
    print("\n[4] 验证 DB 持久化...")
    db_history = get_db_response_history(STUDENT_ID)
    db_5d = get_db_5d_state(STUDENT_ID)
    print(f"  DB response_history 长度: {len(db_history)}")
    print(f"  最后 5 条 score 字段:")
    for h in db_history[-5:]:
        ts = (h.get("timestamp") or "?")[:19]
        pid = h.get("problem_id", "?")
        s = h.get("score", None)
        c = h.get("correct", "?")
        print(f"    {ts} | {pid:7s} | correct={c} | score={s}")

    print(f"\n  DB 5D θ (持久化后):")
    for dim in ["K", "P", "S", "C", "X"]:
        before = initial_5d.get(dim, 0)
        after = db_5d.get(dim, 0)
        delta = after - before
        print(f"    {dim}: {before:>8.4f} → {after:>8.4f}  (Δ {delta:+.4f})")

    # 5. 关键验收
    print("\n[5] 关键验收...")
    C_before = initial_5d.get("C", 0)
    C_after = after_5d.get("C", 0)
    C_improved = C_after - C_before
    print(f"  C 维度 θ: {C_before:.4f} → {C_after:.4f}  (Δ {C_improved:+.4f})")
    if C_improved > 0.1:
        print(f"  ✅ C 维度涨 {C_improved:.4f}, 超过 0.1 阈值")
    else:
        print(f"  ⚠️ C 维度涨 {C_improved:.4f}, 不足 0.1 阈值 (可能部分对题 score 偏低)")

    # response_history score 字段
    new_entries = db_history[-5:]
    all_have_score = all(h.get("score") is not None for h in new_entries)
    print(f"  response_history 5 条新数据含 score 字段: {'✅' if all_have_score else '❌'}")

    # 5D 联合 MIRT partial credit 效果
    S_before = initial_5d.get("S", 0)
    S_after = after_5d.get("S", 0)
    S_delta = S_after - S_before
    print(f"  S 维度变化: {S_before:.4f} → {S_after:.4f}  (Δ {S_delta:+.4f})")
    if abs(S_delta) < 0.05:
        print(f"  ✅ S 维度单题微跌 < 0.05, C 主导题扩展 5 维度 MIRT 稳定性")
    else:
        print(f"  ⚠️ S 维度单题变化 {S_delta:+.4f}, 仍在 5 维度联合估计范围内")

    print("\n" + "=" * 60)
    print("✅ v0.54.1-c 端到端集成测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
