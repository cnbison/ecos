"""v0.97.3 (b) 答题流 A2 reconcile 注入集成测试.

对应 web/api/belief.py:submit_answer 末尾注入的 reconcile 调用
(session 窗口 = in-memory response_history, 不写 evidence_log 旁路).
"""
from __future__ import annotations

import inspect
import os
import tempfile
from dataclasses import dataclass

import pytest

from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig
from ecos.persistence.db import Database, DatabaseConfig
from web.api import belief as belief_api


@pytest.fixture
def tmp_db():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "b.db")
        db = Database(DatabaseConfig(db_path=path))
        try:
            db.init_schema()
            db.upsert_student("stu_b1", grade_level=5, subject="math")
            yield db
        finally:
            db.close()


@pytest.fixture
def fresh_engine():
    return BeliefEngine(BeliefEngineConfig())


def _h(problem_id, skill_id, correct, score, ts="2026-09-05T10:00:00"):
    return {
        "problem_id": problem_id, "skill_id": skill_id,
        "correct": int(bool(correct)), "score": float(score),
        "self_confidence": None, "bloom_level": "APPLY",
        "user_answer": "", "correct_answer": "", "ai_reasoning": "",
        "timestamp": ts,
    }


@dataclass
class _FakeHit:
    misc_id: str
    confidence: float
    trigger_problem_id: str
    evidence_text: str = ""
    correction_strategy: str = ""


def _make_misc_hit(misc_id, problem_id, confidence=0.85):
    return _FakeHit(misc_id=misc_id, confidence=confidence, trigger_problem_id=problem_id)


def test_submit_answer_triggers_reconcile_with_session_history(
    tmp_db, fresh_engine, monkeypatch
):
    monkeypatch.setattr(belief_api, "_get_db", lambda: tmp_db)
    student_id = "stu_b1"
    engine = fresh_engine
    # state 独立于 engine 存在; 模拟 state.C.misconception_hits
    state = engine.create_initial_state(student_id)
    state.C.misconception_hits.append(_make_misc_hit("M8", "prob_001"))
    history = [
        _h("prob_001", "math.frac", correct=0, score=0.0, ts="2026-09-05T10:00:00"),
        _h("prob_002", "math.frac", correct=1, score=1.0, ts="2026-09-05T10:01:00"),
    ]
    engine.feature_extractor.set_history(student_id, history)
    monkeypatch.setattr(
        belief_api, "_get_or_create_student",
        lambda sid: {"engine": engine, "state": state},
    )
    monkeypatch.setattr(
        belief_api, "_update_via_plugin_or_legacy",
        lambda **_kw: state,
    )

    belief_api.submit_answer(
        student_id=student_id, problem_id="prob_002",
        skill_id="math.frac", correct=True, bloom_layer="L3",
        explanation_text="", score=1.0,
    )

    rows = tmp_db.load_misconception_evidence(student_id)
    assert len(rows) == 1
    assert rows[0]["misc_id"] == "M8"
    assert rows[0]["failure_count"] == 1


def test_submit_answer_reconcile_persistent_records_success(
    tmp_db, fresh_engine, monkeypatch
):
    monkeypatch.setattr(belief_api, "_get_db", lambda: tmp_db)
    student_id = "stu_b1"
    engine = fresh_engine
    state = engine.create_initial_state(student_id)
    state.C.misconception_hits.append(_make_misc_hit("M1", "prob_001"))
    history = [
        _h("prob_001", "math.frac", correct=0, score=0.0, ts="2026-09-05T10:00:00"),
        _h("prob_002", "math.frac", correct=0, score=0.0, ts="2026-09-05T10:01:00"),
    ]
    engine.feature_extractor.set_history(student_id, history)
    monkeypatch.setattr(
        belief_api, "_get_or_create_student",
        lambda sid: {"engine": engine, "state": state},
    )
    monkeypatch.setattr(
        belief_api, "_update_via_plugin_or_legacy",
        lambda **_kw: state,
    )

    belief_api.submit_answer(
        student_id=student_id, problem_id="prob_002",
        skill_id="math.frac", correct=False, bloom_layer="L3", score=0.0,
    )

    rows = tmp_db.load_misconception_evidence(student_id)
    assert len(rows) == 1
    assert rows[0]["success_count"] == 1
    assert rows[0]["failure_count"] == 0


def test_submit_answer_no_misconception_skips_reconcile(
    tmp_db, fresh_engine, monkeypatch
):
    monkeypatch.setattr(belief_api, "_get_db", lambda: tmp_db)
    student_id = "stu_b1"
    engine = fresh_engine
    state = engine.create_initial_state(student_id)
    history = [_h("prob_001", "math.frac", correct=1, score=1.0)]
    engine.feature_extractor.set_history(student_id, history)
    monkeypatch.setattr(
        belief_api, "_get_or_create_student",
        lambda sid: {"engine": engine, "state": state},
    )
    monkeypatch.setattr(
        belief_api, "_update_via_plugin_or_legacy",
        lambda **_kw: state,
    )

    belief_api.submit_answer(
        student_id=student_id, problem_id="prob_001",
        skill_id="math.frac", correct=True, bloom_layer="L3", score=1.0,
    )

    assert tmp_db.load_misconception_evidence(student_id) == []


def test_submit_answer_reconcile_does_not_break_main_flow_on_failure(
    tmp_db, fresh_engine, monkeypatch
):
    def _boom_db():
        raise RuntimeError("db init 炸了")
    monkeypatch.setattr(belief_api, "_get_db", _boom_db)
    student_id = "stu_b1"
    engine = fresh_engine
    state = engine.create_initial_state(student_id)
    history = [_h("prob_001", "math.frac", correct=1, score=1.0)]
    engine.feature_extractor.set_history(student_id, history)
    monkeypatch.setattr(
        belief_api, "_get_or_create_student",
        lambda sid: {"engine": engine, "state": state},
    )
    monkeypatch.setattr(
        belief_api, "_update_via_plugin_or_legacy",
        lambda **_kw: state,
    )

    resp = belief_api.submit_answer(
        student_id=student_id, problem_id="prob_001",
        skill_id="math.frac", correct=True, bloom_layer="L3", score=1.0,
    )
    assert resp["persisted"] is False
    assert resp["correct"] is True


def test_submit_answer_reconcile_uses_session_window_not_full_db(
    tmp_db, fresh_engine, monkeypatch
):
    monkeypatch.setattr(belief_api, "_get_db", lambda: tmp_db)
    student_id = "stu_b1"
    engine = fresh_engine
    state = engine.create_initial_state(student_id)
    tmp_db.save_misconception_evidence(student_id, [
        {"misc_id": "M1", "success_count": 5, "failure_count": 0,
         "last_updated": "2026-09-01"},
    ])
    history = [_h("prob_001", "math.frac", correct=1, score=1.0)]
    engine.feature_extractor.set_history(student_id, history)
    monkeypatch.setattr(
        belief_api, "_get_or_create_student",
        lambda sid: {"engine": engine, "state": state},
    )
    monkeypatch.setattr(
        belief_api, "_update_via_plugin_or_legacy",
        lambda **_kw: state,
    )

    belief_api.submit_answer(
        student_id=student_id, problem_id="prob_001",
        skill_id="math.frac", correct=True, bloom_layer="L3", score=1.0,
    )

    rows = tmp_db.load_misconception_evidence(student_id, "M1")
    assert rows[0]["success_count"] == 5


def test_submit_answer_reconcile_window_sorts_by_timestamp(
    tmp_db, fresh_engine, monkeypatch
):
    """history 乱序时, reconcile 按时间升序 join (防时序错算错 outcome).

    场景: prob_a (M8 命中, math.frac) -> prob_b (跨 skill math.alg, 不参与
    prob_a 后续) -> prob_c (答对, math.frac, no misc). 期望 prob_a 下一条
    同 skill = prob_c 答对 -> failure=1, success=0.
    """
    monkeypatch.setattr(belief_api, "_get_db", lambda: tmp_db)
    student_id = "stu_b1"
    engine = fresh_engine
    state = engine.create_initial_state(student_id)
    state.C.misconception_hits.append(_make_misc_hit("M8", "prob_a"))
    # 故意乱序, prob_b 跨 skill 不污染 prob_a 的 next-skill 判定
    history = [
        _h("prob_b", "math.alg", correct=1, score=1.0, ts="2026-09-05T10:02:00"),
        _h("prob_c", "math.frac", correct=1, score=1.0, ts="2026-09-05T10:03:00"),
        _h("prob_a", "math.frac", correct=0, score=0.0, ts="2026-09-05T10:01:00"),
    ]
    engine.feature_extractor.set_history(student_id, history)
    monkeypatch.setattr(
        belief_api, "_get_or_create_student",
        lambda sid: {"engine": engine, "state": state},
    )
    monkeypatch.setattr(
        belief_api, "_update_via_plugin_or_legacy",
        lambda **_kw: state,
    )

    belief_api.submit_answer(
        student_id=student_id, problem_id="prob_c",
        skill_id="math.frac", correct=True, bloom_layer="L3", score=1.0,
    )

    rows = tmp_db.load_misconception_evidence(student_id)
    assert len(rows) == 1
    assert rows[0]["misc_id"] == "M8"
    assert rows[0]["failure_count"] == 1
    assert rows[0]["success_count"] == 0


def test_no_silent_pass_in_belief_reconcile_block():
    """防御性自检 [1] 回归: submit_answer 末尾 reconcile 注入段无 except: pass."""
    src = inspect.getsource(belief_api.submit_answer)
    marker_start = src.find("v0.97.3 (b): A2 reconcile")
    marker_end = src.find("# 构建响应", marker_start)
    assert marker_start > 0 and marker_end > marker_start
    block = src[marker_start:marker_end]
    bad = [ln for ln in block.splitlines() if "pass" in ln and "except" in ln]
    assert not bad, f"reconcile 注入段发现 except: pass, 防御性自检 [1] 违规: {bad}"
