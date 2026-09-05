"""v0.97.1 Planner view 接线 test suite (bjork_spacing / ca_scaffolding 消费逻辑).

对应:
  - docs/wiring-audit-2026-09-05.md A 类 (L3 两效应对象孤儿实例接线)
  - tests/test_planner.py:75-76 存在性断言掩盖模式 → 本文件补真实调用断言

覆盖:
- 无 view 回退: PlanDecision.review_schedule 为空 / scaffolding_adjust None /
  legacy space 规则不变 (黄金回归 no-view 路径零 diff 的语义保证)
- view spacing: peak≥0.7 且衰减到位 → space 触发 + review_schedule 数据完整
- view 不触发: 高峰无衰减 / 峰值不足 → 不误触发
- scaffolding 有界增量: streak fail → +0.15, streak success → -0.1,
  失败优先不叠加, clamp ±0.2
- ExperimentDesigner 消费: scaffolding_adjust 叠加 CLT 映射 + review_schedule
  写入 Intervention.metadata (可 JSON 持久化: 无 datetime 残留)
"""
from __future__ import annotations

import pytest

from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig
from ecos.cta.l1_evolution import EvolutionConfig
from ecos.cta.l2_mirt import MIRTConfig
from ecos.lca.cta_input import CTAInput
from ecos.lca.experiment_designer import ExperimentDesigner, ExperimentDesignerConfig
from ecos.lca.intervention import CLTLevel
from ecos.lca.planner import Planner, PlannerConfig

from datetime import datetime, timedelta

BASE = datetime(2026, 9, 1, 8, 0, 0)


@pytest.fixture
def belief_state():
    config = BeliefEngineConfig(
        evolution_config=EvolutionConfig(),
        mirt_config=MIRTConfig(
            prior_mean=[0.0] * 5,
            prior_cov=None,
            default_a_specialized=[0.8] * 5,
            default_a_general=0.5,
            default_difficulty=0.0,
        ),
    )
    engine = BeliefEngine(config=config, llm_client=None)
    return engine.create_initial_state("test_view_wiring_student")


def _make_input(belief_state, view=None, ts=None) -> CTAInput:
    return CTAInput(
        student_id="test_view_wiring_student",
        belief_state=belief_state,
        skill_mastery_view=view,
        timestamp=ts or BASE,
    )


def _view_entry(**kw) -> dict:
    entry = {
        "peak": 0.5, "current": 0.5, "decayed": 0.5, "days_since": 0.0,
        "last_ts": None, "streak_success": 0, "streak_fail": 0,
        "n_observations": 5,
    }
    entry.update(kw)
    return entry


# ── 无 view 回退 (向后兼容语义) ──────────────────────────────────────


class TestNoViewFallback:
    def test_no_view_no_review_schedule_no_adjust(self, belief_state):
        plan = Planner().plan(_make_input(belief_state))
        assert plan.review_schedule == {}
        assert plan.scaffolding_adjust is None

    def test_no_view_legacy_space_rule_intact(self, belief_state):
        """legacy 规则: K.mastery_prob > 0.5 + trajectory >= 5 → space.

        initial state K.mastery_prob = 0.5, 不超阈值 → 不触发 (冷启动语义)。
        """
        plan = Planner().plan(_make_input(belief_state))
        assert "space" not in plan.bjork_triggers


# ── view spacing 触发 ────────────────────────────────────────────────


class TestViewSpacing:
    def test_decayed_skill_triggers_space_and_schedule(self, belief_state):
        """peak 0.85 → decayed 0.45 (掉幅 0.4): 触发 + 时间表数据完整."""
        view = {"python.loops": _view_entry(
            peak=0.85, decayed=0.45, last_ts=BASE - timedelta(days=30),
        )}
        plan = Planner().plan(_make_input(belief_state, view=view))
        assert "space" in plan.bjork_triggers
        sched = plan.review_schedule["python.loops"]
        assert sched["skill_id"] == "python.loops"
        assert sched["mastery"] == pytest.approx(0.45)
        assert sched["peak"] == pytest.approx(0.85)
        # isoformat 字符串 (可 JSON 持久化); 锚点是 last_review_date,
        # decayed 0.45 → 短间隔 2 天 (上次复习 30 天前 + 2 天 = 已过期, 语义正确)
        short = datetime.fromisoformat(sched["next_short_review"])
        long_ = datetime.fromisoformat(sched["next_long_review"])
        assert short == BASE - timedelta(days=30) + timedelta(days=2)
        assert long_ > short

    def test_peak_without_decay_does_not_trigger(self, belief_state):
        """peak 0.85 无衰减 (decayed==peak): 不触发 (无间隔证据)."""
        view = {"python.loops": _view_entry(peak=0.85, decayed=0.85)}
        plan = Planner().plan(_make_input(belief_state, view=view))
        assert "space" not in plan.bjork_triggers
        assert plan.review_schedule == {}

    def test_low_peak_does_not_trigger(self, belief_state):
        """peak 0.4 < 0.7: 从未掌握到位, 谈不上遗忘, 不触发间隔复习."""
        view = {"python.loops": _view_entry(peak=0.4, decayed=0.2)}
        plan = Planner().plan(_make_input(belief_state, view=view))
        assert "space" not in plan.bjork_triggers

    def test_borderline_drop_triggers(self, belief_state):
        """peak 0.75 → decayed 0.55: peak<0.7 之外靠掉幅 0.2 ≥ 0.15 触发."""
        view = {"s1": _view_entry(peak=0.75, decayed=0.55)}
        plan = Planner().plan(_make_input(belief_state, view=view))
        assert "space" in plan.bjork_triggers


# ── scaffolding 有界增量 ─────────────────────────────────────────────


class TestScaffoldingAdjust:
    def test_failure_streak_restores(self, belief_state):
        """streak_fail=2 (restore_threshold) → +0.15 增量."""
        view = {"s1": _view_entry(streak_fail=2)}
        plan = Planner().plan(_make_input(belief_state, view=view))
        assert plan.scaffolding_adjust == pytest.approx(0.15)

    def test_success_streak_fades(self, belief_state):
        """streak_success=4 (fade_threshold=3) → 0.5-0.1 = -0.1 增量."""
        view = {"s1": _view_entry(streak_success=4)}
        plan = Planner().plan(_make_input(belief_state, view=view))
        assert plan.scaffolding_adjust == pytest.approx(-0.1)

    def test_failure_dominates_success(self, belief_state):
        """一个 skill 连错一个 skill 连对: 失败优先 (frustration 保护), 不叠加."""
        view = {
            "bad": _view_entry(streak_fail=2),
            "good": _view_entry(streak_success=4),
        }
        plan = Planner().plan(_make_input(belief_state, view=view))
        assert plan.scaffolding_adjust == pytest.approx(0.15)

    def test_subthreshold_streaks_no_adjust(self, belief_state):
        """streak_success=2 / streak_fail=1 均未达阈值 → None (不调整)."""
        view = {
            "a": _view_entry(streak_success=2),
            "b": _view_entry(streak_fail=1),
        }
        plan = Planner().plan(_make_input(belief_state, view=view))
        assert plan.scaffolding_adjust is None

    def test_huge_streaks_clamped(self, belief_state):
        """streak_fail=10 → 原始增量 0.75, clamp 到 +0.2."""
        view = {"s1": _view_entry(streak_fail=10)}
        plan = Planner().plan(_make_input(belief_state, view=view))
        assert plan.scaffolding_adjust == pytest.approx(0.2)


# ── ExperimentDesigner 消费 ──────────────────────────────────────────


class TestDesignerConsumption:
    def test_scaffolding_adjust_applied_on_clt_mapping(self, belief_state):
        """designer: scaffolding = clamp(CLT 映射 + adjust, 0, 1)."""
        planner = Planner()
        designer = ExperimentDesigner(ExperimentDesignerConfig())
        view = {"s1": _view_entry(streak_success=4)}  # adjust = -0.1

        plan = planner.plan(_make_input(belief_state, view=view))
        base = ExperimentDesignerConfig().scaffolding_by_clt[plan.clt_level]
        candidates = designer.design(plan, _make_input(belief_state, view=view))

        assert len(candidates) > 0
        for itv in candidates:
            expected = max(0.0, min(1.0, base - 0.1))
            assert itv.scaffolding_level == pytest.approx(expected)

    def test_review_schedule_lands_in_metadata_json_safe(self, belief_state):
        """review_schedule 写入 Intervention.metadata, 全 JSON 可序列化."""
        import json

        planner = Planner()
        designer = ExperimentDesigner(ExperimentDesignerConfig())
        view = {"python.loops": _view_entry(
            peak=0.85, decayed=0.45, last_ts=BASE - timedelta(days=30),
        )}
        cta_input = _make_input(belief_state, view=view)
        plan = planner.plan(cta_input)
        candidates = designer.design(plan, cta_input)

        assert len(candidates) > 0
        for itv in candidates:
            assert "review_schedule" in itv.metadata
            # 确认无 datetime 残留 (to_dict/from_dict 往返安全)
            json.dumps(itv.to_dict(), ensure_ascii=False)
            sched = itv.metadata["review_schedule"]["python.loops"]
            datetime.fromisoformat(sched["next_short_review"])

    def test_no_view_keeps_metadata_empty(self, belief_state):
        """无 view: metadata 不含 review_schedule 键 (向后兼容)."""
        planner = Planner()
        designer = ExperimentDesigner(ExperimentDesignerConfig())
        cta_input = _make_input(belief_state)
        plan = planner.plan(cta_input)
        candidates = designer.design(plan, cta_input)
        assert all("review_schedule" not in itv.metadata for itv in candidates)
