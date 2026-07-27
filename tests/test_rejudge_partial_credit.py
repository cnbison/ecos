"""v0.58.1: scripts/rejudge_partial_credit.py 测试套件.

测试目标 (跟 v0.56.1 rejudge_misjudged.py 单元测试模式一致):
  1. load_rubric_problem_ids 正确加载
  2. find_rubric_entries 正确找到 entry (默认 + force 模式 + student filter)
  3. update_history_entry 正确更新
  4. 端到端: mock LLM, 验证整个 rejudge 流程

防御性自检 [7] (v0.57.0): 脚本只改 score/correct/ai_reasoning 字段, 不改 5D.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


# ──────────────────────────────────────────────────────────────────────
# 1. load_rubric_problem_ids
# ──────────────────────────────────────────────────────────────────────


class TestLoadRubricProblemIds:
    """v0.58.1: 加载 Q 矩阵里所有带 partial_credit_rubric 的题."""

    def test_load_returns_rubric_problems(self, tmp_path):
        """加载返回所有带 partial_credit_rubric 的题."""
        from scripts.rejudge_partial_credit import load_rubric_problem_ids

        qfile = tmp_path / "q_matrix.json"
        qfile.write_text(json.dumps({
            "problems": [
                {"problem_id": "PB-C01", "partial_credit_rubric": {"0.0": "x"}},
                {"problem_id": "PB-C02", "partial_credit_rubric": {"0.0": "y"}},
                {"problem_id": "PB-Q01"},
                {"problem_id": "PC-C01", "partial_credit_rubric": {"0.0": "z"}},
            ]
        }))

        result = load_rubric_problem_ids(str(qfile))
        assert "PB-C01" in result
        assert "PB-C02" in result
        assert "PC-C01" in result
        assert "PB-Q01" not in result
        assert len(result) == 3

    def test_load_empty_q_matrix(self, tmp_path):
        """空 Q 矩阵返回空 dict."""
        from scripts.rejudge_partial_credit import load_rubric_problem_ids

        qfile = tmp_path / "empty.json"
        qfile.write_text(json.dumps({"problems": []}))
        result = load_rubric_problem_ids(str(qfile))
        assert result == {}


# ──────────────────────────────────────────────────────────────────────
# 2. find_rubric_entries
# ──────────────────────────────────────────────────────────────────────


class TestFindRubricEntries:
    """v0.58.1: 扫 DB 找需要重判的 entry."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """临时 DB, 含 lbc001 + lbc002 + rubric 题 entry."""
        db_path = str(tmp_path / "test.db")

        lbc001_history = [
            {"problem_id": "PB-C01", "correct": 0, "score": 0.6,
             "user_answer": "x", "correct_answer": "y",
             "ai_reasoning": "old reasoning"},
            {"problem_id": "PB-Q01", "correct": 1, "score": 1.0,
             "user_answer": "a", "correct_answer": "a"},
            {"problem_id": "PC-C01", "correct": 1, "score": 1.0,
             "user_answer": "f", "correct_answer": "B",
             "ai_reasoning": "old", "rejudge_timestamp": "2026-07-27-v0.58.1-partial-credit"},
        ]
        lbc002_history = [
            {"problem_id": "PB-C02", "correct": 0, "score": 0.0,
             "user_answer": "B", "correct_answer": "x",
             "ai_reasoning": "old"},
        ]

        import sqlite3
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("""CREATE TABLE students (
            student_id TEXT PRIMARY KEY,
            response_history TEXT
        )""")
        for sid, hist in [("lbc001", lbc001_history), ("lbc002", lbc002_history)]:
            cur.execute(
                "INSERT INTO students VALUES (?, ?)",
                (sid, json.dumps(hist, ensure_ascii=False)),
            )
        conn.commit()
        conn.close()
        return db_path

    def test_find_rubric_entries_default(self, temp_db):
        """默认模式: 找有 rubric 的 entry, 跳过已 rejudge 的."""
        from scripts.rejudge_partial_credit import find_rubric_entries

        rubric_ids = {"PB-C01", "PB-C02", "PC-C01"}
        result = find_rubric_entries(temp_db, None, rubric_ids, force=False)

        assert len(result) == 2
        pids = [c["entry"]["problem_id"] for c in result]
        assert "PB-C01" in pids
        assert "PB-C02" in pids
        assert "PC-C01" not in pids
        assert "PB-Q01" not in pids

    def test_find_rubric_entries_force(self, temp_db):
        """force 模式: 包括已 rejudge 的 entry."""
        from scripts.rejudge_partial_credit import find_rubric_entries

        rubric_ids = {"PB-C01", "PB-C02", "PC-C01"}
        result = find_rubric_entries(temp_db, None, rubric_ids, force=True)
        assert len(result) == 3
        pids = [c["entry"]["problem_id"] for c in result]
        assert "PC-C01" in pids

    def test_find_rubric_entries_student_filter(self, temp_db):
        """student filter: 只处理指定学生."""
        from scripts.rejudge_partial_credit import find_rubric_entries

        rubric_ids = {"PB-C01", "PB-C02", "PC-C01"}
        result = find_rubric_entries(temp_db, "lbc001", rubric_ids, force=False)
        assert all(c["student_id"] == "lbc001" for c in result)
        assert len(result) == 1
        assert result[0]["entry"]["problem_id"] == "PB-C01"


# ──────────────────────────────────────────────────────────────────────
# 3. update_history_entry
# ──────────────────────────────────────────────────────────────────────


class TestUpdateHistoryEntry:
    """v0.58.1: 更新 response_history 单条 entry."""

    def test_update_single_entry_keeps_others(self, tmp_path):
        """更新 history[1] 时, history[0] / history[2] 保持不变."""
        from scripts.rejudge_partial_credit import update_history_entry

        db_path = str(tmp_path / "test.db")
        history = [
            {"problem_id": "PB-C01", "correct": 0, "score": 0.0},
            {"problem_id": "PB-C02", "correct": 1, "score": 1.0},
            {"problem_id": "PB-C03", "correct": 0, "score": 0.0},
        ]

        import sqlite3
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("""CREATE TABLE students (
            student_id TEXT PRIMARY KEY,
            response_history TEXT
        )""")
        cur.execute(
            "INSERT INTO students VALUES (?, ?)",
            ("lbc001", json.dumps(history, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()

        updated_entry = {
            "problem_id": "PB-C02", "correct": 0, "score": 0.3,
            "rejudge_timestamp": "2026-07-27-v0.58.1-partial-credit",
        }
        update_history_entry(db_path, "lbc001", 1, updated_entry)

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT response_history FROM students WHERE student_id = 'lbc001'")
        new_history = json.loads(cur.fetchone()[0])

        assert new_history[0] == history[0]
        assert new_history[1] == updated_entry
        assert new_history[2] == history[2]

    def test_update_invalid_index_noop(self, tmp_path):
        """history_index 越界时, 不更新."""
        from scripts.rejudge_partial_credit import update_history_entry

        db_path = str(tmp_path / "test.db")
        history = [{"problem_id": "PB-C01", "correct": 0, "score": 0.0}]

        import sqlite3
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("""CREATE TABLE students (
            student_id TEXT PRIMARY KEY,
            response_history TEXT
        )""")
        cur.execute(
            "INSERT INTO students VALUES (?, ?)",
            ("lbc001", json.dumps(history, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()

        update_history_entry(db_path, "lbc001", 5, {"problem_id": "X"})

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT response_history FROM students WHERE student_id = 'lbc001'")
        new_history = json.loads(cur.fetchone()[0])
        assert new_history == history


# ──────────────────────────────────────────────────────────────────────
# 4. 端到端: mock LLM, 验证整个流程
# ──────────────────────────────────────────────────────────────────────


class TestEndToEndRejudge:
    """v0.58.1: 端到端 rejudge 流程 (mock LLM, 不真实调)."""

    @pytest.fixture
    def temp_q_matrix_and_db(self, tmp_path):
        """临时 Q 矩阵 + DB + lbc001 测试数据."""
        qfile = tmp_path / "q_matrix.json"
        qfile.write_text(json.dumps({
            "problems": [
                {
                    "problem_id": "PB-C01",
                    "skill_name": "循环边界",
                    "problem_text": "for i in range(1, 5): print(i) 期望输出 1,2,3,4,5 实际输出 1,2,3,4",
                    "correct_answer": "改 range(1, 6)",
                    "partial_credit_rubric": {
                        "0.0": "完全错",
                        "0.6": "识别 range 不包含 5",
                        "1.0": "正确修改"
                    }
                },
            ]
        }))

        db_path = str(tmp_path / "test.db")
        history = [
            {"problem_id": "PB-C01", "correct": 0, "score": 0.0,
             "user_answer": "改 range(1, 6)", "correct_answer": "改 range(1, 6)",
             "ai_reasoning": "old reasoning"},
        ]

        import sqlite3
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("""CREATE TABLE students (
            student_id TEXT PRIMARY KEY,
            response_history TEXT
        )""")
        cur.execute(
            "INSERT INTO students VALUES (?, ?)",
            ("lbc001", json.dumps(history, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()

        return str(qfile), db_path

    def test_end_to_end_rejudge_changes_score(self, temp_q_matrix_and_db, caplog):
        """端到端: LLM 返回 score=1.0 → entry 更新."""
        from scripts import rejudge_partial_credit as script_mod

        qfile, db_path = temp_q_matrix_and_db

        def fake_chat(self, messages, **kwargs):
            return json.dumps({"score": 1.0, "correct": True, "reasoning": "改对了"})

        fake_llm = type("FakeLLM", (), {"chat": fake_chat})()

        with patch("web.api.app.get_llm", return_value=fake_llm):
            import sys
            old_argv = sys.argv
            sys.argv = ["rejudge.py", "--db", db_path, "--q-matrix", qfile,
                        "--student", "lbc001"]
            try:
                script_mod.main()
            finally:
                sys.argv = old_argv

        import sqlite3
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT response_history FROM students WHERE student_id = 'lbc001'")
        history = json.loads(cur.fetchone()[0])
        entry = history[0]
        assert entry["score"] == 1.0
        assert entry["correct"] == 1
        assert entry["needs_rejudge"] is False
        assert "v0.58.1" in entry["rejudge_timestamp"]

    def test_end_to_end_rejudge_failure_marks_needs_rejudge(self, temp_q_matrix_and_db, caplog):
        """端到端: LLM 3 次 retry 失败 → entry 标 needs_rejudge=True."""
        from scripts import rejudge_partial_credit as script_mod

        qfile, db_path = temp_q_matrix_and_db

        def fake_chat(self, messages, **kwargs):
            return "not json"

        fake_llm = type("FakeLLM", (), {"chat": fake_chat})()

        with patch("web.api.app.get_llm", return_value=fake_llm):
            import sys
            old_argv = sys.argv
            sys.argv = ["rejudge.py", "--db", db_path, "--q-matrix", qfile,
                        "--student", "lbc001"]
            try:
                script_mod.main()
            finally:
                sys.argv = old_argv

        import sqlite3
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT response_history FROM students WHERE student_id = 'lbc001'")
        history = json.loads(cur.fetchone()[0])
        entry = history[0]
        assert entry["score"] is None
        assert entry["needs_rejudge"] is True
        assert "v0.58.1" in entry["rejudge_timestamp"]

    def test_end_to_end_dry_run_no_write(self, temp_q_matrix_and_db):
        """端到端: --dry-run 不写入 DB."""
        from scripts import rejudge_partial_credit as script_mod

        qfile, db_path = temp_q_matrix_and_db

        def fake_chat(self, messages, **kwargs):
            return json.dumps({"score": 1.0, "correct": True, "reasoning": "ok"})

        fake_llm = type("FakeLLM", (), {"chat": fake_chat})()

        import sqlite3
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT response_history FROM students WHERE student_id = 'lbc001'")
        original_history = json.loads(cur.fetchone()[0])
        conn.close()

        with patch("web.api.app.get_llm", return_value=fake_llm):
            import sys
            old_argv = sys.argv
            sys.argv = ["rejudge.py", "--db", db_path, "--q-matrix", qfile,
                        "--student", "lbc001", "--dry-run"]
            try:
                script_mod.main()
            finally:
                sys.argv = old_argv

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT response_history FROM students WHERE student_id = 'lbc001'")
        new_history = json.loads(cur.fetchone()[0])
        assert new_history == original_history

    def test_rejudge_only_modifies_response_history_not_5d(self, temp_q_matrix_and_db):
        """v0.57.0 防御性自检 [7]: rejudge 改 score/correct 字段, 5D 不可修."""
        from scripts import rejudge_partial_credit as script_mod

        qfile, db_path = temp_q_matrix_and_db

        import sqlite3
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("ALTER TABLE students ADD COLUMN current_state_5d TEXT")
        cur.execute("ALTER TABLE students ADD COLUMN current_bloom_profile TEXT")
        cur.execute(
            "UPDATE students SET current_state_5d = ?, current_bloom_profile = ? WHERE student_id = 'lbc001'",
            (json.dumps([0.5, 0.6, 0.7, 0.8, 0.9]),
             json.dumps({"remember": 0.5})),
        )
        conn.commit()
        conn.close()

        def fake_chat(self, messages, **kwargs):
            return json.dumps({"score": 1.0, "correct": True, "reasoning": "ok"})

        fake_llm = type("FakeLLM", (), {"chat": fake_chat})()

        with patch("web.api.app.get_llm", return_value=fake_llm):
            import sys
            old_argv = sys.argv
            sys.argv = ["rejudge.py", "--db", db_path, "--q-matrix", qfile,
                        "--student", "lbc001"]
            try:
                script_mod.main()
            finally:
                sys.argv = old_argv

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT current_state_5d, current_bloom_profile FROM students WHERE student_id = 'lbc001'")
        row = cur.fetchone()
        assert json.loads(row[0]) == [0.5, 0.6, 0.7, 0.8, 0.9]
        assert json.loads(row[1]) == {"remember": 0.5}


# ──────────────────────────────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
