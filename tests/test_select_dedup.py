"""v0.99.3 (F-14): LCA select 去重记账 + PluginRuntime ensure_started 幂等.

背景 (dogfood-findings-2026-09.md F-14):
  - legacy select 路径每次 /api/question 拉题都无条件 append intervention_history,
    同状态重复决策 (refetch) 反复记账 → 重启后 7→10 实锤
  - PluginRuntime 激活只写在 app.py __main__ → 记账口径随启动方式漂移

本文件测:
  1. _decision_fingerprint: 易变键排除 + 内容敏感
  2. select 去重: 同决策不重复记账, 不同决策正常记录
  3. ensure_started: 幂等 + 失败不抛出
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig
from ecos.cta.belief_state import BloomLevel
from ecos.lca import LCAEngine
from ecos.lca.cta_input import CTAInput
from ecos.lca.intervention import Intervention, InterventionType
from ecos.lca.orchestrator import _decision_fingerprint


@pytest.fixture
def belief_state():
    """最小可用 BeliefState (同 test_lca_wired 口径)."""
    config = BeliefEngineConfig()
    engine = BeliefEngine(config=config, llm_client=None)
    return engine.create_initial_state("test_dedup_student")


@pytest.fixture
def engine():
    return LCAEngine()


class TestDecisionFingerprint:
    def test_volatile_keys_excluded(self):
        """id / created_at / expected_gain / expected_risk 不同 → 指纹相同."""
        base = dict(
            intervention_type=InterventionType.PRACTICE,
            bloom_target=BloomLevel.CREATE,
            rationale="r",
        )
        a = Intervention(**base, intervention_id="aaaa", created_at="2026-01-01",
                         expected_gain=0.1, expected_risk=0.2)
        b = Intervention(**base, intervention_id="bbbb", created_at="2026-02-02",
                         expected_gain=0.9, expected_risk=0.8)
        assert _decision_fingerprint(a) == _decision_fingerprint(b)

    def test_content_sensitive(self):
        """核心决策字段 (bloom_target) 不同 → 指纹不同."""
        a = Intervention(intervention_type=InterventionType.PRACTICE,
                         bloom_target=BloomLevel.CREATE)
        b = Intervention(intervention_type=InterventionType.PRACTICE,
                         bloom_target=BloomLevel.ANALYZE)
        assert _decision_fingerprint(a) != _decision_fingerprint(b)

    def test_rationale_sensitive(self):
        """rationale 不同 → 指纹不同 (F-14a 测试锚: 变理由 = 变决策)."""
        a = Intervention(intervention_type=InterventionType.PRACTICE,
                         bloom_target=BloomLevel.CREATE, rationale="r1")
        b = Intervention(intervention_type=InterventionType.PRACTICE,
                         bloom_target=BloomLevel.CREATE, rationale="r2")
        assert _decision_fingerprint(a) != _decision_fingerprint(b)


class TestSelectDedup:
    def test_duplicate_decision_not_recorded(self, engine, belief_state):
        """同状态连续两次 select → 结果都返回, 但 history/select_count 只记 1 次."""
        sid = "test_dedup_student"
        cta_input = CTAInput(student_id=sid, belief_state=belief_state)
        r1 = engine.select_intervention(cta_input)
        r2 = engine.select_intervention(cta_input)
        assert r1 is not None and r2 is not None
        assert len(engine.intervention_history.get(sid, [])) == 1
        assert engine._select_count[sid] == 1

    def test_different_decision_recorded(self, engine, belief_state):
        """决策实质变化 (rationale 变) → 正常追加记账."""
        sid = "test_dedup_student"
        cta_input = CTAInput(student_id=sid, belief_state=belief_state)
        engine.select_intervention(cta_input)
        # rationale 是决策指纹的一部分 — 状态真变了 (理由变了) 就该记
        with patch.object(engine.rationale_gen, "generate", return_value="状态变化后的新理由"):
            engine.select_intervention(cta_input)
        assert len(engine.intervention_history.get(sid, [])) == 2
        assert engine._select_count[sid] == 2

    def test_per_student_independent(self, engine, belief_state):
        """不同学生各自记账, 互不去重."""
        cta_a = CTAInput(student_id="test_dedup_a", belief_state=belief_state)
        cta_b = CTAInput(student_id="test_dedup_b", belief_state=belief_state)
        engine.select_intervention(cta_a)
        engine.select_intervention(cta_b)
        assert len(engine.intervention_history["test_dedup_a"]) == 1
        assert len(engine.intervention_history["test_dedup_b"]) == 1

    def test_duplicate_still_returns_fresh_result(self, engine, belief_state):
        """重复决策不记账但结果照常返回 (前端 lca_decision 不受影响)."""
        sid = "test_dedup_student"
        cta_input = CTAInput(student_id=sid, belief_state=belief_state)
        r1 = engine.select_intervention(cta_input)
        r2 = engine.select_intervention(cta_input)
        assert r2.intervention.intervention_type == r1.intervention.intervention_type
        assert r2.intervention.bloom_target == r1.intervention.bloom_target
        # 与正常路径同构: 返回完整 LCAResult (不是裸 Intervention)
        assert r1.bloom_target is not None and r2.bloom_target is not None


class TestEnsureStarted:
    def test_idempotent_and_starts_once(self):
        """ensure_started 幂等: 二次调用 True 且订阅数不变."""
        from ecos.event import get_default_bus
        from web.api.plugin_runtime import ensure_started, get_plugin_runtime, reset_plugin_runtime

        reset_plugin_runtime()
        try:
            bus = get_default_bus()
            assert ensure_started() is True
            runtime = get_plugin_runtime()
            assert runtime._started is True
            subs_after_first = runtime.subscription_count
            # 二次调用 no-op
            assert ensure_started() is True
            assert runtime.subscription_count == subs_after_first
        finally:
            runtime = get_plugin_runtime()
            try:
                runtime.stop()
            except Exception:
                pass
            reset_plugin_runtime()
            del bus

    def test_start_failure_returns_false_not_raises(self):
        """start() 抛异常 → ensure_started 捕获返 False (不向上传播)."""
        import web.api.plugin_runtime as pr

        pr.reset_plugin_runtime()
        try:
            with patch.object(
                pr.PluginRuntime, "start", side_effect=RuntimeError("boom"),
            ):
                assert pr.ensure_started() is False
        finally:
            pr.reset_plugin_runtime()
