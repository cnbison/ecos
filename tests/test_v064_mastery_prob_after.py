"""v0.64.0 双修测试: mastery_prob_after 字段 + dual_agent prev.actual_outcome 回写.

v0.64.0 双修:
  - 修复 1: belief_engine update 后, history[-1] 补 mastery_prob_after 字段
            (5D 各维度 mastery_prob + bloom_dominant + bloom_confidence + overall_confidence)
  - 修复 2: dual_agent process_observation 时, 自动回写 prev calibration_log
            行 actual_outcome (v0.60.4 写库 BUG 修复)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ─── Fixtures ───────────────────────────────────────────────────


@pytest.fixture
def fresh_both(monkeypatch):
    """重置 dual_agent + belief.py + store 单例 + 清理 test students DB (避免累积)."""
    import web.api.dual_agent as dual_mod
    import web.api.belief as belief_mod
    from ecos.persistence import dual_agent_store as da_store_mod
    from ecos.persistence.db import get_db
    from ecos.persistence.dual_agent_store import get_dual_agent_store

    # mock LLM (CI 干净环境 robustness, 跟 v0.62.2 同样)
    mock_llm = MagicMock()
    monkeypatch.setattr("web.api.app.get_llm", lambda: mock_llm)

    dual_mod._orchestrator = None
    dual_mod._dual_store = None
    dual_mod._loaded_students = set()
    dual_mod.DUAL_AGENT_ENABLED = True

    belief_mod._STUDENT_STATES = {}
    da_store_mod._store = None

    # 清理 test students (dual_agent_store + calibration_log + students 表)
    test_sids = (
        "test_v064_a",
        "test_v064_b",
        "test_v064_c",
    )
    for sid in test_sids:
        try:
            get_dual_agent_store().delete_state(sid)
        except Exception:
            pass
    # 清理 calibration_log (避免跨测试累积)
    db = get_db()
    for sid in test_sids:
        try:
            db.conn.execute(
                "DELETE FROM calibration_log WHERE student_id = ?",
                (sid,),
            )
            db.conn.execute(
                "DELETE FROM students WHERE student_id = ?",
                (sid,),
            )
            db.conn.commit()
        except Exception:
            pass

    yield dual_mod, belief_mod

    try:
        da_store_mod._store.close() if da_store_mod._store else None
    except Exception:
        pass
    da_store_mod._store = None


# ─── 1. mastery_prob_after 字段 (修复 1) ────────────────────────


class TestMasteryProbAfterField:
    """v0.64.0: belief_engine.update 后 history[-1] 补 mastery_prob_after."""

    def test_history_entry_has_mastery_prob_after_after_update(self, fresh_both):
        """update 后, last history entry 包含 mastery_prob_after 字段."""
        from web.api.belief import submit_answer
        from ecos.cta.belief_state import BloomLevel

        belief_mod = fresh_both[1]
        sid = "test_v064_a"

        submit_answer(
            student_id=sid,
            problem_id="P1",
            skill_id="S1",
            correct=True,
            bloom_layer="L3",
            user_answer="x",
            correct_answer="x",
        )

        engine = belief_mod._STUDENT_STATES[sid]["engine"]
        history = engine._response_history.get(sid, [])
        assert len(history) == 1
        last = history[-1]
        # v0.64.0: mastery_prob_after 字段
        assert "mastery_prob_after" in last, (
            f"v0.64.0 修复失败: history[-1] 缺 mastery_prob_after 字段, "
            f"现有字段: {list(last.keys())}"
        )
        mpa = last["mastery_prob_after"]
        assert isinstance(mpa, dict)
        # 5D 维度
        for dim in ("K", "P", "S", "C", "X"):
            assert dim in mpa, f"mastery_prob_after 缺 {dim} 维度"
            assert 0.0 <= mpa[dim] <= 1.0
        # bloom
        assert mpa["bloom_dominant"] in ("REMEMBER", "UNDERSTAND", "APPLY", "ANALYZE", "EVALUATE", "CREATE")
        assert 0.0 <= mpa["bloom_confidence"] <= 1.0
        assert 0.0 <= mpa["overall_confidence"] <= 1.0

    def test_mastery_prob_after_reflects_after_update_not_before(self, fresh_both):
        """mastery_prob_after 是 update 后的状态 (不是 update 前的)."""
        from web.api.belief import submit_answer
        from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig
        from ecos.cta.l1_evolution import EvolutionConfig
        from ecos.cta.l2_mirt import MIRTConfig

        belief_mod = fresh_both[1]
        sid = "test_v064_b"

        # 答 2 道题, K 应该涨 (答对)
        submit_answer(
            student_id=sid, problem_id="P1", skill_id="S1",
            correct=True, bloom_layer="L3", user_answer="x", correct_answer="x",
        )
        submit_answer(
            student_id=sid, problem_id="P2", skill_id="S1",
            correct=True, bloom_layer="L3", user_answer="x", correct_answer="x",
        )

        engine = belief_mod._STUDENT_STATES[sid]["engine"]
        history = engine._response_history.get(sid, [])
        assert len(history) == 2

        # 第 2 题的 mastery_prob_after.K 应该 >= 第 1 题的 (答对涨)
        k1 = history[0]["mastery_prob_after"]["K"]
        k2 = history[1]["mastery_prob_after"]["K"]
        assert k2 >= k1, f"答对应涨 mastery_prob: k1={k1}, k2={k2}"

    def test_old_history_entry_without_mastery_prob_after_still_loadable(self, fresh_both):
        """老 data (v0.64.0 之前) 没 mastery_prob_after 字段, 应能正常 load."""
        # 模拟老 history entry (没 mastery_prob_after)
        from web.api.belief import _get_or_create_student
        from ecos.cta.belief_engine import BeliefEngine
        from ecos.cta.l1_evolution import EvolutionConfig
        from ecos.cta.l2_mirt import MIRTConfig

        belief_mod = fresh_both[1]
        sid = "test_v064_c"

        student = _get_or_create_student(sid)
        engine = student["engine"]
        # 直接 append 一个 "老" entry (没 mastery_prob_after 字段)
        engine._response_history[sid] = [
            {
                "problem_id": "OLD",
                "correct": 1,
                "score": 1.0,
                "bloom_level": "APPLY",
                "user_answer": "x",
                "correct_answer": "x",
                "ai_reasoning": "",
                "timestamp": "2026-07-29T00:00:00",
                # 故意没 mastery_prob_after 字段
            }
        ]
        # 验证 load 时不崩 (访问 .get("mastery_prob_after", {}) 兜底)
        mpa = engine._response_history[sid][0].get("mastery_prob_after", {})
        assert mpa == {}  # 兜底到空 dict


# ─── 2. dual_agent prev.actual_outcome 回写 (修复 2) ──────────────


class TestPrevActualOutcomeWriteback:
    """v0.64.0: dual_agent.process_observation 时, 自动回写 prev calibration_log 行 actual_outcome."""

    def test_prev_actual_outcome_written_back_after_2nd_observation(
        self, fresh_both, monkeypatch
    ):
        """第 2 次 process_observation 后, prev (第 1 轮) 的 actual_outcome 应被回写.

        v0.60.4 BUG: prev.actual_outcome 永远留 None.
        v0.64.0 修复: dual_agent 写新 calibration_log 前, 先 UPDATE prev 行.
        """
        from web.api.dual_agent import process_observation_for_student
        from ecos.persistence.db import get_db
        from ecos.cta.belief_state import BloomLevel

        dual_mod, belief_mod = fresh_both
        sid = "test_v064_a"

        # 第 1 次 process_observation (initial, no prev)
        r1 = process_observation_for_student(
            student_id=sid,
            problem_id="P1",
            skill_id="S1",
            correct=True,
            score=1.0,
            bloom_layer="L3",
        )
        assert r1 is not None
        assert r1["round"] == 1  # 第 1 轮

        # 第 2 次 process_observation (有 prev = r1)
        r2 = process_observation_for_student(
            student_id=sid,
            problem_id="P2",
            skill_id="S1",
            correct=False,
            score=0.0,
            bloom_layer="L3",
        )
        assert r2 is not None
        assert r2["round"] == 2

        # 验证: 第 1 轮 (prev) 的 actual_outcome 应被回写 = 0.0 (第 2 题 score=0.0)
        db = get_db()
        log = db.load_calibration_history(sid, limit=10)
        # 升序: round=1 在前, round=2 在后
        round1_row = next(r for r in log if r["calibration_round"] == 1)
        import json
        payload = json.loads(round1_row["message_payload"])
        assert payload.get("actual_outcome") is not None, (
            f"v0.64.0 修复失败: prev (round=1) 的 actual_outcome 仍 None, "
            f"payload: {payload}"
        )
        # 第 1 轮的 actual_outcome 应该来自第 2 次 obs 的 score=0.0
        assert payload["actual_outcome"] == 0.0

    def test_db_update_calibration_actual_outcome_unit(self, fresh_both):
        """db.update_calibration_actual_outcome 单测 (直接调 db 方法)."""
        from ecos.persistence.db import get_db
        import json

        db = get_db()
        sid = "test_v064_a"

        # calibration_log 有 FOREIGN KEY (student_id) REFERENCES students(student_id)
        # 先 INSERT students 表, 否则 save_calibration 抛 IntegrityError
        from datetime import datetime
        db.conn.execute(
            """INSERT OR IGNORE INTO students (student_id, subject, created_at, last_active_at)
               VALUES (?, 'python', ?, ?)""",
            (sid, datetime.now().isoformat(), datetime.now().isoformat()),
        )
        db.conn.commit()

        # 1. 直接插一行 calibration_log (模拟 v0.60.4 旧数据)
        db.save_calibration(sid, {
            "calibration_round": 1,
            "message_type": "cta_lca_calibrated",
            "message_payload": {
                "intervention_type": "explanatory",  # v0.62+ 用 lowercase enum value
                "bloom_target": "APPLY",
                "expected_gain": 0.12,
                "actual_outcome": None,  # 老数据, None
            },
            "interaction_mode": "normal",
            "duration_ms": 10,
        })

        # 2. 调 update_calibration_actual_outcome
        updated = db.update_calibration_actual_outcome(
            student_id=sid,
            calibration_round=1,
            actual_outcome=0.8,  # 80% 实际 outcome
        )
        assert updated == 1

        # 3. 读回, 验证 message_payload.actual_outcome 改成 0.8
        log = db.load_calibration_history(sid, limit=10)
        round1_row = next(r for r in log if r["calibration_round"] == 1)
        payload = json.loads(round1_row["message_payload"])
        assert payload["actual_outcome"] == 0.8
        # 验证其他字段 (intervention_type, bloom_target, expected_gain) 没被覆盖
        assert payload["intervention_type"] == "explanatory"
        assert payload["bloom_target"] == "APPLY"
        assert payload["expected_gain"] == 0.12

    def test_update_returns_0_for_nonexistent_round(self, fresh_both):
        """不存在的 round → 返回 0, 不报错."""
        from ecos.persistence.db import get_db

        db = get_db()
        updated = db.update_calibration_actual_outcome(
            student_id="nonexistent_student_xyz",
            calibration_round=999,
            actual_outcome=0.5,
        )
        assert updated == 0


# ─── 3. compute_h3_ece.py 行为 ────────────────────────────────


class TestComputeH3ECEV064:
    """v0.64.0: compute_h3_ece.py 移除回填, 用 mastery_prob_after / 直接读 actual_outcome."""

    def test_single_agent_uses_mastery_prob_after_when_available(self, fresh_both):
        """单 Agent: 有 mastery_prob_after 字段 → 用历史快照, 不用 fallback."""
        from web.api.belief import submit_answer
        from web.api.dual_agent import _load_dual_state_if_needed
        from scripts.compute_h3_ece import compute_single_agent_ece

        dual_mod, belief_mod = fresh_both
        sid = "test_v064_a"

        # 答 2 道 (触发 mastery_prob_after 写入)
        submit_answer(sid, "P1", "S1", True, "L3", "x", "x")
        submit_answer(sid, "P2", "S1", True, "L3", "x", "x")
        _load_dual_state_if_needed(sid)  # 触发 belief_state load

        result = compute_single_agent_ece(sid, dimension="K")
        assert result["n_samples"] == 2
        assert result["used_fallback"] == 0, (
            f"v0.64.0: 有 mastery_prob_after 应该全用, 实际 {result['used_fallback']} fallback"
        )
        assert result["ece"] is not None

    def test_dual_agent_directly_reads_actual_outcome(self, fresh_both):
        """双 Agent: 直接读 actual_outcome, 没 fallback."""
        from web.api.dual_agent import process_observation_for_student
        from scripts.compute_h3_ece import compute_dual_agent_ece

        dual_mod, belief_mod = fresh_both
        sid = "test_v064_b"

        # 跑 2 次 dual_agent, 触发 v0.64.0 回写
        process_observation_for_student(sid, "P1", "S1", True, 1.0, "L3")
        process_observation_for_student(sid, "P2", "S1", True, 1.0, "L3")

        result = compute_dual_agent_ece(sid)
        # 第 1 轮的 actual_outcome 应该是 1.0 (v0.64.0 回写, 第 2 题 score=1.0)
        # 第 2 轮的 actual_outcome 是 None (本次 prev 是 None, 没回写目标)
        # 期望 n_samples=1 (只有 1 个配对)
        assert result["n_samples"] == 1, (
            f"v0.64.0: calibration_log 2 行, 1 行 actual_outcome 配对, "
            f"实际 n_samples={result['n_samples']}, skipped={result.get('skipped_no_outcome', 0)}"
        )
        assert result["skipped_no_outcome"] == 1  # 第 2 行 (current) actual_outcome None
        assert result["ece"] is not None
