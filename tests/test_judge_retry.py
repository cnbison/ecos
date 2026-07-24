"""v0.56.1: /api/judge retry + 422 + 不污染 state 测试 (Bisen 原则).

测试目标:
  1. LLM JSON parse 失败时 retry, 3 次后仍 fail
  2. retry 全部失败 → return 422 + needs_rejudge=True
  3. 失败路径**不污染 state** (response_history / 5D / Bloom)
  4. retry 第 2/3 次成功 → 返回正确结果
  5. 每次失败有 _log.warning (防御性自检 [1])
  6. 不调任何启发式 fallback (防御性自检 [6])

Bisen 原则 (2026-07-24): LLM judge 失败 = 系统故障, 显式 fail, 不污染 state.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from unittest.mock import MagicMock, patch

import pytest


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


class FakeLLM:
    """模拟 LLM client: 根据 plan 返回结果.

    plan 是 list of strings (LLM raw responses), 每次 chat() 调用取一个.
    如果 list 长度 < 调用次数, 抛 RuntimeError 模拟网络错误.
    """

    def __init__(self, plan: list[str] | str, raise_on_exhausted: bool = True):
        # 如果是 str, 视为单次成功响应
        if isinstance(plan, str):
            self.plan = [plan]
        else:
            self.plan = list(plan)
        self.raise_on_exhausted = raise_on_exhausted
        self.call_count = 0

    def chat(self, messages, **kwargs):
        self.call_count += 1
        if self.call_count > len(self.plan):
            if self.raise_on_exhausted:
                raise RuntimeError(f"FakeLLM exhausted after {len(self.plan)} calls (call #{self.call_count})")
            return self.plan[-1]
        return self.plan[self.call_count - 1]


@pytest.fixture
def flask_client():
    """Flask test client fixture."""
    from web.api.app import app
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def lbc001_state_backup():
    """测试前备份 lbc001 state, 测试后恢复 (避免测试污染真实数据)."""
    from web.api.belief import _STUDENT_STATES
    from ecos.persistence.db import Database

    # 清空 in-memory state (避免 _response_history 污染)
    _STUDENT_STATES.clear()

    # 备份 DB lbc001 state
    db = Database("web/ecos.db")
    original = db.load_student_state("lbc001")

    yield original

    # 恢复
    if original is not None:
        try:
            db.update_student_state_full("lbc001", original)
        except Exception:
            pass  # 恢复失败不影响测试结论


# ──────────────────────────────────────────────────────────────────────
# 1. _call_llm_judge_with_retry 单元测试
# ──────────────────────────────────────────────────────────────────────


class TestJudgeHelperRetry:
    """v0.56.1: _call_llm_judge_with_retry 单元测试."""

    def test_helper_succeeds_on_first_attempt(self):
        """第一次 LLM 调用成功, 直接返回."""
        from web.api.app import _call_llm_judge_with_retry

        valid_json = json.dumps({"correct": True, "reasoning": "对"})
        fake_llm = FakeLLM(plan=valid_json)

        result, attempts = _call_llm_judge_with_retry(fake_llm, "fake prompt")

        assert result is not None
        assert result["correct"] is True
        assert attempts == 1
        assert fake_llm.call_count == 1

    def test_helper_succeeds_on_retry(self):
        """第一次 parse 失败, 第二次成功."""
        from web.api.app import _call_llm_judge_with_retry

        invalid_json = "这不是 JSON 格式"
        valid_json = json.dumps({"correct": True, "reasoning": "对"})
        fake_llm = FakeLLM(plan=[invalid_json, valid_json])

        result, attempts = _call_llm_judge_with_retry(fake_llm, "fake prompt")

        assert result is not None
        assert result["correct"] is True
        assert attempts == 2
        assert fake_llm.call_count == 2

    def test_helper_returns_none_after_max_retries(self):
        """3 次都失败 → return (None, 3)."""
        from web.api.app import _call_llm_judge_with_retry

        # 3 次都返回非 JSON
        fake_llm = FakeLLM(plan=["invalid1", "invalid2", "invalid3"])
        result, attempts = _call_llm_judge_with_retry(fake_llm, "fake prompt")

        assert result is None
        assert attempts == 3
        assert fake_llm.call_count == 3

    def test_helper_logs_warnings_on_parse_failure(self, caplog):
        """每次 parse 失败必须 _log.warning (防御性自检 [1])."""
        from web.api.app import _call_llm_judge_with_retry

        fake_llm = FakeLLM(plan=["bad json"] * 3)

        with caplog.at_level(logging.WARNING):
            _call_llm_judge_with_retry(fake_llm, "fake prompt")

        warning_logs = [r for r in caplog.records if r.levelname == "WARNING"]
        parse_warnings = [r for r in warning_logs if "JSON parse 失败" in r.message]
        assert len(parse_warnings) == 3, \
            f"应该有 3 次 JSON parse 失败 warning, 实际={len(parse_warnings)}"

    def test_helper_logs_warnings_on_chat_failure(self, caplog):
        """LLM chat() 抛异常时也必须 _log.warning (防御性自检 [1])."""
        from web.api.app import _call_llm_judge_with_retry

        class RaisingLLM:
            call_count = 0
            def chat(self, *args, **kwargs):
                self.call_count += 1
                raise RuntimeError("mock LLM down")

        with caplog.at_level(logging.WARNING):
            result, attempts = _call_llm_judge_with_retry(RaisingLLM(), "fake prompt")

        assert result is None
        assert attempts == 3
        chat_warnings = [r for r in caplog.records if r.levelname == "WARNING" and "chat 调用失败" in r.message]
        assert len(chat_warnings) == 3, "应该有 3 次 chat 调用失败 warning"

    def test_helper_rejects_llm_response_without_correct_field(self):
        """LLM 返回 JSON 但缺 'correct' 字段 → 视为 parse 失败, retry."""
        from web.api.app import _call_llm_judge_with_retry

        # 第 1 次缺 correct 字段, 第 2 次正常
        bad_json = json.dumps({"reasoning": "没 correct 字段"})
        good_json = json.dumps({"correct": True, "reasoning": "ok"})
        fake_llm = FakeLLM(plan=[bad_json, good_json])

        result, attempts = _call_llm_judge_with_retry(fake_llm, "fake prompt")

        assert result is not None
        assert result["correct"] is True
        assert attempts == 2


# ──────────────────────────────────────────────────────────────────────
# 2. /api/judge 端点集成测试
# ──────────────────────────────────────────────────────────────────────


class TestJudgeEndpoint:
    """v0.56.1: /api/judge 端点行为."""

    def test_judge_returns_422_on_max_retries(self, flask_client):
        """3 次 retry 全失败 → 422 + needs_rejudge=True."""
        fake_llm = FakeLLM(plan=["invalid1", "invalid2", "invalid3"])

        with patch("web.api.app.get_llm", return_value=fake_llm):
            resp = flask_client.post("/api/judge", json={
                "student_id": "lbc001",
                "problem_id": "PB-Q26",
                "student_answer": "def make_counter(start=0): ...",
            })

        assert resp.status_code == 422
        data = resp.get_json()
        assert data["judged"] is False
        assert data["error_code"] == "LLM_JUDGE_FAILED"
        assert data["needs_rejudge"] is True
        assert data["retry_count"] == 3
        assert "AI 评判服务故障" in data["error"]

    def test_judge_returns_200_on_success(self, flask_client):
        """LLM judge 成功 → 200 + judged=True + attempts=1."""
        valid_json = json.dumps({"correct": True, "reasoning": "完全正确"})
        fake_llm = FakeLLM(plan=valid_json)

        with patch("web.api.app.get_llm", return_value=fake_llm):
            resp = flask_client.post("/api/judge", json={
                "student_id": "lbc001",
                "problem_id": "PB-Q26",
                "student_answer": "def make_counter(start=0): nonlocal count ...",
            })

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["judged"] is True
        assert data["correct"] is True
        assert data["attempts"] == 1

    def test_judge_returns_200_on_retry_success(self, flask_client):
        """第 1 次 fail, 第 2 次成功 → 200 + attempts=2."""
        valid_json = json.dumps({"correct": True, "reasoning": "ok"})
        fake_llm = FakeLLM(plan=["bad json", valid_json])

        with patch("web.api.app.get_llm", return_value=fake_llm):
            resp = flask_client.post("/api/judge", json={
                "student_id": "lbc001",
                "problem_id": "PB-Q26",
                "student_answer": "def make_counter...",
            })

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["judged"] is True
        assert data["attempts"] == 2

    def test_judge_400_on_empty_answer(self, flask_client):
        """空答案 → 400 (Bisen 原则: 早 fail, 不调 LLM)."""
        resp = flask_client.post("/api/judge", json={
            "student_id": "lbc001",
            "problem_id": "PB-Q26",
            "student_answer": "   ",
        })
        assert resp.status_code == 400

    def test_judge_404_on_missing_problem(self, flask_client):
        """题目不存在 → 404."""
        resp = flask_client.post("/api/judge", json={
            "student_id": "lbc001",
            "problem_id": "PB-NONEXISTENT",
            "student_answer": "anything",
        })
        assert resp.status_code == 404


# ──────────────────────────────────────────────────────────────────────
# 3. 关键: 失败时不污染 state (Bisen 原则核心)
# ──────────────────────────────────────────────────────────────────────


class TestJudgeNoStatePollution:
    """v0.56.1: 失败时绝不污染 response_history / 5D / Bloom / TC."""

    def test_judge_failure_does_not_call_submit_answer(self, flask_client, lbc001_state_backup):
        """LLM judge 全部失败时, 不能调 /api/answer 或 submit_answer 写 state.

        验证方法: mock submit_answer, 如果被调用就 fail.
        """
        fake_llm = FakeLLM(plan=["bad"] * 3)

        with patch("web.api.app.get_llm", return_value=fake_llm):
            with patch("web.api.belief.submit_answer") as mock_submit:
                resp = flask_client.post("/api/judge", json={
                    "student_id": "lbc001",
                    "problem_id": "PB-Q26",
                    "student_answer": "def make_counter...",
                })

        assert resp.status_code == 422
        # 关键断言: submit_answer 不应被调
        mock_submit.assert_not_called(), \
            "/api/judge 失败时不能调 submit_answer (会污染 5D state)"

    def test_judge_failure_does_not_write_response_history(self, flask_client, lbc001_state_backup):
        """LLM judge 全部失败时, response_history 不应被写入新条目."""
        import sqlite3
        from web.api.belief import _STUDENT_STATES

        # 备份当前 response_history 长度
        with sqlite3.connect("web/ecos.db") as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT response_history FROM students WHERE student_id = 'lbc001'"
            )
            row = cur.fetchone()
            if row and row[0]:
                history_before = json.loads(row[0])
            else:
                history_before = []
            history_len_before = len(history_before)

        fake_llm = FakeLLM(plan=["bad"] * 3)

        with patch("web.api.app.get_llm", return_value=fake_llm):
            resp = flask_client.post("/api/judge", json={
                "student_id": "lbc001",
                "problem_id": "PB-Q26",
                "student_answer": "def make_counter...",
            })

        assert resp.status_code == 422

        # 验证 response_history 长度不变
        with sqlite3.connect("web/ecos.db") as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT response_history FROM students WHERE student_id = 'lbc001'"
            )
            row = cur.fetchone()
            if row and row[0]:
                history_after = json.loads(row[0])
            else:
                history_after = []
            history_len_after = len(history_after)

        assert history_len_after == history_len_before, \
            f"/api/judge 失败时 response_history 长度应不变, " \
            f"before={history_len_before}, after={history_len_after}"

    def test_judge_failure_does_not_update_5d_theta(self, flask_client, lbc001_state_backup):
        """LLM judge 全部失败时, 5D theta 不应被更新."""
        import numpy as np

        # 备份当前 5D theta (DB 存的是 JSON 字符串, 需要 parse)
        theta_str = lbc001_state_backup.get("current_state_5d") or "[0.0,0.0,0.0,0.0,0.0]"
        theta_before = np.array(json.loads(theta_str), dtype=float)

        fake_llm = FakeLLM(plan=["bad"] * 3)

        with patch("web.api.app.get_llm", return_value=fake_llm):
            resp = flask_client.post("/api/judge", json={
                "student_id": "lbc001",
                "problem_id": "PB-Q26",
                "student_answer": "def make_counter...",
            })

        assert resp.status_code == 422

        # 验证 5D theta 不变
        with sqlite3.connect("web/ecos.db") as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT current_state_5d FROM students WHERE student_id = 'lbc001'"
            )
            row = cur.fetchone()
            theta_after_str = row[0] if row and row[0] else "[0.0,0.0,0.0,0.0,0.0]"
            theta_after = np.array(json.loads(theta_after_str), dtype=float)

        np.testing.assert_array_almost_equal(
            theta_before, theta_after, decimal=6,
            err_msg=f"/api/judge 失败时 5D theta 应不变, "
                    f"before={theta_before.tolist()}, after={theta_after.tolist()}",
        )


# ──────────────────────────────────────────────────────────────────────
# 4. 防御性自检
# ──────────────────────────────────────────────────────────────────────


class TestDefensiveChecks:
    """v0.56.1: 防御性自检套件."""

    def test_no_heuristic_fallback_in_judge(self):
        """防御性自检 [6] (v0.56.1 新增): 不写启发式 fallback.

        检查 app.py 的 /api/judge 实现中, 没有 ast / 函数名匹配 / 字符串宽松化 / 用户自评 等降级路径.
        注: 用 ast 解析拿 code body, 排除 docstring 和 comment 里的字面提及.
        """
        import ast
        import inspect
        from web.api import app as app_mod

        def get_code_body(func) -> str:
            """用 ast 拿函数 body 的代码行 (排除 docstring)."""
            source = inspect.getsource(func)
            tree = ast.parse(source)
            func_def = tree.body[0]
            # 拿函数体 (排除 docstring expr, docstring 是第一个 Expr statement)
            body_lines = []
            for stmt in func_def.body:
                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                    continue  # 跳过 docstring
                body_lines.append(ast.unparse(stmt))
            return "\n".join(body_lines)

        judge_body = get_code_body(app_mod.api_judge_answer)
        helper_body = get_code_body(app_mod._call_llm_judge_with_retry)
        combined = judge_body + "\n" + helper_body

        # 禁止出现的代码 pattern (启发式 / 字符串宽松化 / 自评)
        forbidden_patterns = [
            ("ast.parse", "AST 启发式"),
            ("astunparse", "AST 启发式"),
            ("string_match", "字符串匹配"),
            ("user_eval", "用户自评"),
            ("self_evaluate", "用户自评"),
            ("text_match", "文本匹配"),
            ("diff_match", "diff 启发式"),
            ("strip().lower() ==", "字符串宽松化"),
        ]

        for pattern, name in forbidden_patterns:
            assert pattern not in combined, \
                f"防御性自检 [6]: /api/judge 禁止 {name} ('{pattern}'), " \
                f"LLM 失败应直接显式 fail"

    def test_judge_logs_422_failure(self, flask_client, caplog):
        """422 返回时必须有 logger.warning (防御性自检 [1])."""
        fake_llm = FakeLLM(plan=["bad"] * 3)

        with patch("web.api.app.get_llm", return_value=fake_llm):
            with caplog.at_level(logging.WARNING):
                resp = flask_client.post("/api/judge", json={
                    "student_id": "lbc001",
                    "problem_id": "PB-Q26",
                    "student_answer": "anything",
                })

        assert resp.status_code == 422
        failure_warnings = [
            r for r in caplog.records
            if r.levelname == "WARNING" and "全部" in r.message and "retry 失败" in r.message
        ]
        assert len(failure_warnings) >= 1, \
            "422 返回时必须有 logger.warning 记录失败原因"


# ──────────────────────────────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
