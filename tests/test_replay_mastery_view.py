"""v0.97.1 replay_mastery_view 无状态重放视图 test suite.

对应:
  - docs/wiring-audit-2026-09-05.md A 类接线的数据供给 (bjork_spacing/ca_scaffolding)
  - CogMirror P3 方案: BKT 不持久化, 峰值由重放推导, 衰减是读时计算
  - 验收标准: 幂等 (双跑全等) / 老数据缺 skill_id 安全跳过 / 衰减数学正确 /
    只读 (不触碰 engine.l1)

覆盖:
- 幂等性: 同输入双跑结果全等
- 峰值语义: 全对序列 peak==current; 对-对-错 peak > current (峰值≠当前值)
- 衰减数学: now=last_ts+30d → decayed == peak · e^(-1) (默认 τ=30d)
- 无 timestamp → 保守不衰减 (decayed==peak, days_since==0)
- 老条目缺 skill_id → 跳过不误报; correct 缺失时 score>=0.6 兜底
- streaks: 末尾连续对/错计数
- per-skill 隔离: 交错序列各自独立重放
- 只读保证: BeliefEngine.decayed_mastery_view 前后 engine.l1 模型值不变
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

import pytest

from ecos.cta.belief_engine import BeliefEngine, Observation
from ecos.cta.belief_state import BloomLevel
from ecos.cta.l1_evolution import replay_mastery_view


BASE = datetime(2026, 9, 1, 8, 0, 0)


def _entry(skill_id: str, correct: int, ts: datetime | None = None,
           **extra) -> dict:
    entry = {"skill_id": skill_id, "correct": correct}
    if ts is not None:
        entry["timestamp"] = ts.isoformat()
    entry.update(extra)
    return entry


# ── 幂等性 ────────────────────────────────────────────────────────────


def test_replay_is_idempotent():
    """同输入双跑必须全等 (只读重放, 无 RNG/时间泄漏)."""
    history = [
        _entry("python.loops", 1, BASE + timedelta(minutes=5 * i))
        for i in range(6)
    ] + [
        _entry("python.scope", 0, BASE + timedelta(minutes=5 * i))
        for i in range(3)
    ]
    now = BASE + timedelta(days=10)
    view_a = replay_mastery_view(history, now=now)
    view_b = replay_mastery_view(history, now=now)
    assert view_a == view_b


# ── 峰值语义 ──────────────────────────────────────────────────────────


def test_all_correct_peak_equals_current():
    """全对序列: 峰值 = 末次更新后的 p_mastered."""
    history = [_entry("s1", 1, BASE + timedelta(minutes=5 * i)) for i in range(5)]
    view = replay_mastery_view(history, now=BASE)
    assert view["s1"]["peak"] == pytest.approx(view["s1"]["current"])
    assert view["s1"]["peak"] > 0.5


def test_peak_differs_from_current_on_recent_wrong():
    """对-对-...-错: 峰值 > 当前值 (峰值≠当前值是本 API 存在的理由)."""
    history = (
        [_entry("s1", 1, BASE + timedelta(minutes=5 * i)) for i in range(4)]
        + [_entry("s1", 0, BASE + timedelta(minutes=25))]
    )
    view = replay_mastery_view(history, now=BASE)
    assert view["s1"]["peak"] > view["s1"]["current"]


def test_all_wrong_stays_near_p_init_floor():
    """全错序列: 峰值有 p_init 下限 (不会为 0); p_learn 转移使 p 缓慢上升
    → 峰值 = 末次值 (单调上升序列 peak==current), 但始终贴近 p_init."""
    history = [_entry("s1", 0, BASE + timedelta(minutes=5 * i)) for i in range(5)]
    view = replay_mastery_view(history, now=BASE)
    assert view["s1"]["peak"] >= 0.1
    assert view["s1"]["peak"] == pytest.approx(view["s1"]["current"])
    assert view["s1"]["current"] < 0.2  # 贴近 p_init, 远未掌握


# ── 衰减数学 ──────────────────────────────────────────────────────────


def test_decay_math_30_days_is_exp_minus_one():
    """now = last_ts + 30d → decayed == peak · e^(-1) (默认 τ=30d)."""
    history = [_entry("s1", 1, BASE + timedelta(minutes=5 * i)) for i in range(5)]
    now = BASE + timedelta(minutes=20) + timedelta(days=30)  # 末条 +20min
    view = replay_mastery_view(history, now=now)
    assert view["s1"]["days_since"] == pytest.approx(30.0)
    assert view["s1"]["decayed"] == pytest.approx(
        view["s1"]["peak"] * math.exp(-1.0), rel=1e-9
    )


def test_no_elapsed_time_means_no_decay():
    """now == last_ts → decayed == peak (无衰减)."""
    history = [_entry("s1", 1, BASE + timedelta(minutes=5 * i)) for i in range(5)]
    view = replay_mastery_view(history, now=BASE + timedelta(minutes=20))  # 末条时刻
    assert view["s1"]["days_since"] == pytest.approx(0.0)
    assert view["s1"]["decayed"] == pytest.approx(view["s1"]["peak"])


def test_missing_timestamp_conservatively_no_decay():
    """无 timestamp → days_since=0, decayed=peak (无时间证据不衰减)."""
    history = [_entry("s1", 1)]  # 无 timestamp
    view = replay_mastery_view(history, now=BASE)
    assert view["s1"]["last_ts"] is None
    assert view["s1"]["days_since"] == 0.0
    assert view["s1"]["decayed"] == pytest.approx(view["s1"]["peak"])


# ── 老数据兼容 ────────────────────────────────────────────────────────


def test_legacy_entries_without_skill_id_are_skipped():
    """v0.97.1 前老条目缺 skill_id → 跳过, 不猜不映射, 不抛异常."""
    history = [
        {"problem_id": "P001", "correct": 1},  # 老条目
        _entry("s1", 1, BASE),
    ]
    view = replay_mastery_view(history, now=BASE)
    assert set(view.keys()) == {"s1"}
    assert view["s1"]["n_observations"] == 1


def test_missing_correct_falls_back_to_score():
    """correct 缺失时 score>=0.6 兜底 (与 MIRT 兼容约定一致)."""
    history = [
        {"skill_id": "s1", "score": 0.8},
        {"skill_id": "s1", "score": 0.3},
    ]
    view = replay_mastery_view(history, now=BASE)
    assert view["s1"]["streak_fail"] == 1  # 最后一条 score 0.3 = 错
    assert view["s1"]["n_observations"] == 2


# ── streaks ───────────────────────────────────────────────────────────


def test_trailing_streak_fail():
    """[对,对,对,错,错] → streak_fail=2, streak_success=0."""
    history = [_entry("s1", c, BASE) for c in [1, 1, 1, 0, 0]]
    view = replay_mastery_view(history, now=BASE)
    assert view["s1"]["streak_fail"] == 2
    assert view["s1"]["streak_success"] == 0


def test_trailing_streak_success():
    """[对,错,对,对,对] → streak_success=3, streak_fail=0."""
    history = [_entry("s1", c, BASE) for c in [1, 0, 1, 1, 1]]
    view = replay_mastery_view(history, now=BASE)
    assert view["s1"]["streak_success"] == 3
    assert view["s1"]["streak_fail"] == 0


# ── per-skill 隔离 ────────────────────────────────────────────────────


def test_interleaved_skills_replay_independently():
    """交错序列: 各 skill 只重放自己的条目 (答对/答错互不串扰)."""
    history = [
        _entry("easy", 1, BASE),
        _entry("hard", 0, BASE),
        _entry("easy", 1, BASE),
        _entry("hard", 0, BASE),
    ]
    view = replay_mastery_view(history, now=BASE)
    assert view["easy"]["peak"] > view["hard"]["current"]
    assert view["hard"]["n_observations"] == 2
    assert view["easy"]["streak_success"] == 2


# ── 只读保证 (BeliefEngine facade) ────────────────────────────────────


def _make_observation(skill_id: str, score: float, ts: datetime) -> Observation:
    return Observation(
        skill_id=skill_id,
        problem_id=f"P_{skill_id}_{ts.strftime('%H%M%S')}",
        correct=score >= 0.6,
        score=score,
        bloom_level=BloomLevel.APPLY,
        user_answer="42",
        correct_answer="42",
        ai_reasoning="ok",
        timestamp=ts,
    )


def test_belief_engine_facade_is_read_only():
    """decayed_mastery_view 前后 engine.l1 模型值不变 (只读保证)."""
    engine = BeliefEngine(llm_client=None)
    state = engine.create_initial_state("lbc_view_test")
    for i, score in enumerate([1.0, 1.0, 0.0]):
        engine.update(state, _make_observation("python.loops", score,
                                               BASE + timedelta(minutes=5 * i)))

    before = {
        sid: (m.p_mastered, m.n_updates)
        for sid, m in engine.l1.skill_models.items()
    }
    view = engine.decayed_mastery_view("lbc_view_test", now=BASE + timedelta(minutes=10))
    after = {
        sid: (m.p_mastered, m.n_updates)
        for sid, m in engine.l1.skill_models.items()
    }

    assert before == after, "replay 视图不得触碰 engine.l1"
    assert "python.loops" in view
    # 峰值 (对-对) 高于重放后 current (对-对-错), 且不等于 l1 的当前值语义
    assert view["python.loops"]["peak"] > view["python.loops"]["current"]


def test_belief_engine_facade_matches_manual_replay():
    """facade 结果 == 直接对 get_history 手动 replay (数据源一致性)."""
    engine = BeliefEngine(llm_client=None)
    state = engine.create_initial_state("lbc_view_test2")
    for i, score in enumerate([1.0, 0.0, 1.0]):
        engine.update(state, _make_observation("python.scope", score,
                                               BASE + timedelta(minutes=5 * i)))

    now = BASE + timedelta(hours=1)
    from ecos.cta.l1_evolution import replay_mastery_view as rmv
    manual = rmv(engine._feature_extractor.get_history("lbc_view_test2"), now=now)
    facade = engine.decayed_mastery_view("lbc_view_test2", now=now)
    assert facade == manual
