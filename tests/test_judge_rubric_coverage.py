"""F-06 回归: 写代码题必须配 partial_credit_rubric + judge prompt 防幻觉要求 (v0.98.8).

拦截历史:
  - dogfood PB-Q16 (global x 写代码题) 概念全对仅缺冒号判 0 分 — 8 道写
    代码题无 rubric 走二元 prompt, score 由 correct 派生 0/1; 且 judge
    reasoning 幻觉「函数体缺少缩进」(DB 原始作答缩进完好).
  - v0.98.8: 补 8 题 rubric (机制 v0.58.0 现成) + prompt 双分支加
    「指出错误必须引用学生答案原文」.
"""

from __future__ import annotations

from web.api.app import _build_judge_prompt
from web.api.qmatrix import get_all_problems

RUBRIC_KEYS = {"0.0", "0.3", "0.6", "1.0"}


def _is_code_question(p: dict) -> bool:
    """写代码类题判定: 正确答案含代码结构 或 题目要求写出代码."""
    ca = p.get("correct_answer", "")
    pt = p.get("problem_text", "")
    return ("def " in ca or "写出代码" in pt or "print(" in ca)


class TestRubricCoverage:
    def test_code_questions_have_rubric(self):
        """F-06 主断言: 写代码类题必须配 partial_credit_rubric."""
        missing = [
            p["problem_id"]
            for p in get_all_problems()
            if _is_code_question(p) and not p.get("partial_credit_rubric")
        ]
        assert missing == [], f"写代码题缺 rubric: {missing}"

    def test_rubric_is_4_tier(self):
        """每份 rubric 必须是 4 档分 (0.0/0.3/0.6/1.0), 档位描述非空."""
        for p in get_all_problems():
            rubric = p.get("partial_credit_rubric")
            if not rubric:
                continue
            assert set(rubric.keys()) == RUBRIC_KEYS, \
                f"{p['problem_id']} rubric 档位异常: {sorted(rubric.keys())}"
            for k, v in rubric.items():
                assert v and v.strip(), f"{p['problem_id']} rubric {k} 分档描述为空"

    def test_pb_q16_rubric_exists(self):
        """F-06 直接当事题: PB-Q16 必须有 rubric, 0.6 档覆盖缺冒号场景."""
        p = next(x for x in get_all_problems() if x["problem_id"] == "PB-Q16")
        rubric = p["partial_credit_rubric"]
        assert "轻微语法瑕疵" in rubric["0.6"] or "缺冒号" in rubric["0.6"]


class TestJudgePromptAntiHallucination:
    """防御性自检 [7]: 改 /api/judge prompt 必加测试."""

    def test_rubric_branch_contains_quote_requirement(self):
        prompt = _build_judge_prompt(
            problem_text="题目",
            correct_answer="答案",
            student_answer="学生答案",
            partial_credit_rubric={"0.0": "错", "0.3": "部分", "0.6": "概念对", "1.0": "全对"},
        )
        assert "引用学生答案原文" in prompt
        assert "不得凭空声称" in prompt

    def test_legacy_branch_contains_quote_requirement(self):
        prompt = _build_judge_prompt(
            problem_text="题目",
            correct_answer="答案",
            student_answer="学生答案",
            partial_credit_rubric=None,
        )
        assert "引用学生答案原文" in prompt
        assert "不得凭空声称" in prompt
        # 输出 JSON 契约不变 (parse 兼容)
        assert '"correct": true/false' in prompt
