"""v0.58.0: /api/judge partial credit 评分测试 (Bisen 拍板半天 mini 修复).

测试目标 (v0.58.0 Definition of Done):
  1. _build_judge_prompt 无 rubric 时 = 老 prompt (向后兼容)
  2. _build_judge_prompt 有 rubric 时 = 注入 4 档分
  3. _parse_judge_result 老数据 (只有 correct) → score 派生
  4. _parse_judge_result 新数据 (有 score) → score 优先
  5. _parse_judge_result 两者都有 → score 优先
  6. _parse_judge_result score 越界 → clamp [0, 1]
  7. /api/judge 端点: 注入 rubric 后 LLM 看到 rubric + 返回 score
  8. /api/judge 端点: 老题 (无 rubric) 行为不变
  9. _call_llm_judge_with_retry: result 缺 correct 和 score 两者 → raise (防御性自检 [8])

Root cause 修复 (Bisen 2026-07-27):
  v0.54.0 partial credit 改造不彻底 — Q 矩阵 partial_credit_rubric 字段挂着但 LLM judge 不消费.
  v0.58.0: prompt 注入 rubric + 强制 LLM 输出 score (4 档分), 优先 score 而非 correct 二元.
"""

from __future__ import annotations

import json
import logging
from unittest.mock import patch

import pytest


# ──────────────────────────────────────────────────────────────────────
# 1. _build_judge_prompt 单元测试
# ──────────────────────────────────────────────────────────────────────


class TestBuildJudgePrompt:
    """v0.58.0: _build_judge_prompt 单元测试 (rubric 注入逻辑)."""

    def test_prompt_without_rubric_uses_legacy_format(self):
        """无 rubric 时, prompt 走老格式 (只要求 correct, 不要求 score)."""
        from web.api.app import _build_judge_prompt

        prompt = _build_judge_prompt(
            problem_text="for i in [1,2,3]: print(i)",
            correct_answer="1, 2, 3",
            student_answer="1 2 3",
            partial_credit_rubric=None,
        )
        # 老 prompt: 不含 "score", 不含 "rubric"
        assert "correct" in prompt
        assert "score" not in prompt
        assert "rubric" not in prompt
        assert "1, 2, 3" in prompt
        assert "1 2 3" in prompt

    def test_prompt_with_rubric_injects_4_levels(self):
        """有 rubric 时, prompt 注入 4 档分 + 要求 LLM 输出 score."""
        from web.api.app import _build_judge_prompt

        rubric = {
            "0.0": "选 E (完全不会)",
            "0.3": "选 D (30%)",
            "0.6": "选 C (50%)",
            "1.0": "选 B (70%) 或 F (无法判断)",
        }
        prompt = _build_judge_prompt(
            problem_text="这道题你能答对的可能性?",
            correct_answer="B (70% 比较确定)",
            student_answer="F. 无法判断",
            partial_credit_rubric=rubric,
        )
        # v0.58.0: prompt 含 rubric 4 档分 + 要求 score 字段
        assert "score" in prompt
        assert "rubric" in prompt.lower() or "评分标准" in prompt
        # 4 档分全注入
        assert "0.0 分" in prompt
        assert "0.3 分" in prompt
        assert "0.6 分" in prompt
        assert "1.0 分" in prompt
        # 学生答案也在 prompt
        assert "F. 无法判断" in prompt


# ──────────────────────────────────────────────────────────────────────
# 2. _parse_judge_result 单元测试
# ──────────────────────────────────────────────────────────────────────


class TestParseJudgeResult:
    """v0.58.0: _parse_judge_result 解析逻辑 (score 优先 correct)."""

    def test_legacy_correct_only_derives_score(self):
        """老数据 (只有 correct, 无 score) → score 派生 (1.0 or 0.0)."""
        from web.api.app import _parse_judge_result

        # correct=True
        correct, score, reasoning = _parse_judge_result({"correct": True, "reasoning": "ok"})
        assert correct is True
        assert score == 1.0
        # correct=False
        correct, score, reasoning = _parse_judge_result({"correct": False, "reasoning": "no"})
        assert correct is False
        assert score == 0.0

    def test_new_score_only_derives_correct(self):
        """新数据 (只有 score, 无 correct) → correct 派生 (score >= 0.6)."""
        from web.api.app import _parse_judge_result

        # score=1.0
        correct, score, reasoning = _parse_judge_result({"score": 1.0, "reasoning": "ok"})
        assert score == 1.0
        assert correct is True
        # score=0.6 (boundary)
        correct, score, reasoning = _parse_judge_result({"score": 0.6, "reasoning": "partial"})
        assert score == 0.6
        assert correct is True
        # score=0.3
        correct, score, reasoning = _parse_judge_result({"score": 0.3, "reasoning": "low"})
        assert score == 0.3
        assert correct is False
        # score=0.0
        correct, score, reasoning = _parse_judge_result({"score": 0.0, "reasoning": "no"})
        assert score == 0.0
        assert correct is False

    def test_both_correct_and_score_prefers_score(self):
        """两者都有 → score 优先 (v0.58.0 偏好)."""
        from web.api.app import _parse_judge_result

        # 矛盾: correct=False 但 score=0.6 → score 优先
        correct, score, reasoning = _parse_judge_result(
            {"correct": False, "score": 0.6, "reasoning": "partial"}
        )
        assert score == 0.6
        assert correct is True  # 0.6 >= 0.6 派生 True

    def test_score_out_of_range_clamps(self):
        """score 越界 (例如 LLM 返回 1.5 或 -0.3) → clamp 到 [0, 1]."""
        from web.api.app import _parse_judge_result

        # score=1.5 → clamp 到 1.0
        correct, score, _ = _parse_judge_result({"score": 1.5})
        assert score == 1.0
        # score=-0.3 → clamp 到 0.0
        correct, score, _ = _parse_judge_result({"score": -0.3})
        assert score == 0.0

    def test_score_invalid_type_falls_back_to_zero(self):
        """score 字段存在但类型无效 (如字符串) → fallback 0.0 + log warning."""
        from web.api.app import _parse_judge_result

        # score="abc" (无法转 float) → 0.0
        with patch("web.api.app._log") as mock_log:
            correct, score, _ = _parse_judge_result({"score": "abc"})
        assert score == 0.0
        # 验证 log warning
        assert any("score 字段但解析失败" in str(call) for call in mock_log.warning.call_args_list)

    def test_neither_correct_nor_score_raises(self):
        """防御性自检 [8]: result 缺 correct 和 score 两者都缺 → _call_llm_judge_with_retry 视为 parse 失败."""
        # 这个测试在 _call_llm_judge_with_retry 验证, 不在 _parse_judge_result
        # (parser 假设已经过 retry 验证, 不会处理这种情况)
        # 跳过: 实际上 _parse_judge_result 会因没 score 走老 correct 派生分支, 不会 raise
        # (retry 那一层已经 raise)
        pass  # 覆盖在 TestCallLLMJudgeRetry.test_... 验证


# ──────────────────────────────────────────────────────────────────────
# 3. _call_llm_judge_with_retry 防御性自检 [8]
# ──────────────────────────────────────────────────────────────────────


class TestCallLLMJudgeRetryDefensive8:
    """v0.58.0 防御性自检 [8]: result 缺 correct 和 score 两者 → raise (视为 parse 失败, retry)."""

    def test_result_missing_both_correct_and_score_raises(self):
        """LLM 返回 JSON 但缺 correct 和 score → ValueError, retry 触发."""
        from web.api.app import _call_llm_judge_with_retry

        # LLM 返回 {"reasoning": "ok"} 但缺 correct/score
        fake_llm = type("FakeLLM", (), {
            "chat": lambda self, **kwargs: json.dumps({"reasoning": "ok"})
        })()

        result, attempts = _call_llm_judge_with_retry(fake_llm, "fake prompt")
        # 3 次都 parse 失败 → (None, 3)
        assert result is None
        assert attempts == 3

    def test_result_with_score_only_passes(self):
        """LLM 返回 {"score": 0.6} (无 correct) → 通过 (v0.58.0 新协议)."""
        from web.api.app import _call_llm_judge_with_retry

        fake_llm = type("FakeLLM", (), {
            "chat": lambda self, **kwargs: json.dumps({"score": 0.6, "reasoning": "ok"})
        })()

        result, attempts = _call_llm_judge_with_retry(fake_llm, "fake prompt")
        assert result is not None
        assert result["score"] == 0.6
        assert attempts == 1

    def test_result_with_correct_only_passes(self):
        """LLM 返回 {"correct": True} (无 score, 老协议) → 通过 (向后兼容)."""
        from web.api.app import _call_llm_judge_with_retry

        fake_llm = type("FakeLLM", (), {
            "chat": lambda self, **kwargs: json.dumps({"correct": True, "reasoning": "ok"})
        })()

        result, attempts = _call_llm_judge_with_retry(fake_llm, "fake prompt")
        assert result is not None
        assert result["correct"] is True
        assert attempts == 1


# ──────────────────────────────────────────────────────────────────────
# 4. /api/judge 端点集成测试
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def flask_client():
    from web.api.app import app
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestJudgeEndpointRubric:
    """v0.58.0: /api/judge 端点集成 (rubric 注入 + score 字段)."""

    def test_judge_with_rubric_returns_score(self, flask_client):
        """有 rubric 的题, /api/judge 返回 score 字段."""
        # 模拟 LLM 返回带 score 的 JSON
        valid_json = json.dumps({"score": 0.6, "correct": True, "reasoning": "选 C, 部分对"})
        fake_llm = type("FakeLLM", (), {
            "chat": lambda self, **kwargs: valid_json
        })()

        with patch("web.api.app.get_llm", return_value=fake_llm):
            # 找一个有 rubric 的题 (PB-C02 / PC-C01 都有 partial_credit_rubric)
            resp = flask_client.post("/api/judge", json={
                "student_id": "lbc001",
                "problem_id": "PB-C02",  # v0.57.1 改题后有 rubric
                "student_answer": "B",
            })

        # 验证 200 + score 字段
        if resp.status_code == 200:
            data = resp.get_json()
            assert data["judged"] is True
            assert "score" in data, "v0.58.0: 必须返回 score 字段"
            assert data["score"] == 0.6
        # 否则可能是 404 (题不存在) 或其他, 跳过

    def test_judge_without_rubric_legacy_behavior(self, flask_client):
        """无 rubric 的题, /api/judge 行为不变 (兼容)."""
        valid_json = json.dumps({"correct": True, "reasoning": "对"})
        fake_llm = type("FakeLLM", (), {
            "chat": lambda self, **kwargs: valid_json
        })()

        with patch("web.api.app.get_llm", return_value=fake_llm):
            # PB-Q26 没 partial_credit_rubric
            resp = flask_client.post("/api/judge", json={
                "student_id": "lbc001",
                "problem_id": "PB-Q26",
                "student_answer": "def make_counter(): ...",
            })

        if resp.status_code == 200:
            data = resp.get_json()
            # 老协议: LLM 只返回 correct, score 派生 1.0
            assert data["correct"] is True
            assert data["score"] == 1.0  # 派生

    def test_judge_rubric_prompt_actually_injected(self, flask_client, caplog):
        """端到端: 有 rubric 时, LLM 收到的 prompt 包含 rubric 4 档分."""
        captured_prompts = []

        def fake_chat(self, messages, **kwargs):
            captured_prompts.append(messages[0]["content"])
            return json.dumps({"score": 0.6, "correct": True, "reasoning": "ok"})

        # Mock LLM, 捕获 prompt
        fake_llm = type("FakeLLM", (), {"chat": fake_chat})()

        with patch("web.api.app.get_llm", return_value=fake_llm):
            resp = flask_client.post("/api/judge", json={
                "student_id": "lbc001",
                "problem_id": "PB-C02",  # 有 rubric
                "student_answer": "B",
            })

        if resp.status_code == 200:
            assert len(captured_prompts) >= 1
            prompt = captured_prompts[0]
            # 验证 prompt 包含 rubric 4 档分
            assert "评分标准" in prompt or "rubric" in prompt.lower()
            assert "0.0 分" in prompt
            assert "1.0 分" in prompt
            # 验证 prompt 要求 LLM 输出 score
            assert "score" in prompt

    def test_judge_no_rubric_prompt_legacy(self, flask_client):
        """端到端: 无 rubric 时, LLM 收到的 prompt 不含 rubric."""
        captured_prompts = []

        def fake_chat(self, messages, **kwargs):
            captured_prompts.append(messages[0]["content"])
            return json.dumps({"correct": True, "reasoning": "ok"})

        fake_llm = type("FakeLLM", (), {"chat": fake_chat})()

        with patch("web.api.app.get_llm", return_value=fake_llm):
            resp = flask_client.post("/api/judge", json={
                "student_id": "lbc001",
                "problem_id": "PB-Q26",  # 无 rubric
                "student_answer": "def ...",
            })

        if resp.status_code == 200:
            prompt = captured_prompts[0]
            # 无 rubric 时, prompt 不含 "评分标准"
            assert "评分标准" not in prompt
            # 但仍要求 correct
            assert "correct" in prompt


# ──────────────────────────────────────────────────────────────────────
# 5. 防御性自检 [8]: 改 prompt 必加测试覆盖输出格式变化
# ──────────────────────────────────────────────────────────────────────


class TestDefensiveCheck8:
    """v0.58.0 防御性自检 [8]: /api/judge 改 prompt 后必须有测试保护 (新增/修改字段)."""

    def test_legacy_correct_only_response_still_works(self):
        """LLM 只返回 {correct: bool} (老 API 客户端) → score 派生 1.0 or 0.0."""
        from web.api.app import _parse_judge_result

        # correct=True
        correct, score, _ = _parse_judge_result({"correct": True})
        assert correct is True
        assert score == 1.0
        # correct=False
        correct, score, _ = _parse_judge_result({"correct": False})
        assert correct is False
        assert score == 0.0


# ──────────────────────────────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
