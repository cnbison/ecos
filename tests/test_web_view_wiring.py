"""v0.97.1 web 产品路径 view 注入 test suite.

对应:
  - docs/wiring-audit-2026-09-05.md A 类收尾 (decayed_mastery_view 产品路径引用)
  - web/api/lca.py:_legacy_select_intervention + web/api/plugin_runtime.py:
    _handle_request_intervention 两处 CTAInput 构造点注入 skill_mastery_view

覆盖:
- _get_skill_mastery_view: engine 有历史 → 视图数据正确; belief 模块异常 →
  warning + None (增强失败不阻断主链路, 防御性自检 [1])
- legacy select 路径: 构造的 CTAInput 确实携带 view (对比无 view 的
  存在性断言掩盖模式, 这里断言真实传递)
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest


BASE = datetime(2026, 9, 1, 8, 0, 0)
SID = "test_web_view_student"


@pytest.fixture
def view_history_state():
    """构造带 response_history 的 engine + state, 注入 _STUDENT_STATES."""
    from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig
    from ecos.cta.l1_evolution import EvolutionConfig
    from ecos.cta.l2_mirt import MIRTConfig
    import web.api.belief as belief_mod

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
    state = engine.create_initial_state(SID)
    # 模拟答题历史 (对-对, 直写 _response_history, 与 belief.py DB 恢复路径同形)
    engine._response_history[SID] = [
        {"problem_id": "P1", "skill_id": "python.loops", "correct": 1,
         "score": 1.0, "timestamp": (BASE - timedelta(days=30)).isoformat()},
        {"problem_id": "P2", "skill_id": "python.loops", "correct": 1,
         "score": 1.0, "timestamp": (BASE - timedelta(days=30)).isoformat()},
    ]
    record = {"engine": engine, "state": state}
    return belief_mod, engine, record


# ── _get_skill_mastery_view ──────────────────────────────────────────


def test_view_returns_replay_data(view_history_state, monkeypatch):
    belief_mod, engine, record = view_history_state
    monkeypatch.setitem(belief_mod._STUDENT_STATES, SID, record)

    import web.api.lca as lca_mod
    view = lca_mod._get_skill_mastery_view(SID)

    assert view is not None
    assert "python.loops" in view
    info = view["python.loops"]
    assert info["n_observations"] == 2
    assert info["peak"] > 0.1  # 两次全对 → 重放出正峰值
    assert info["last_ts"] is not None


def test_view_failure_returns_none_not_raise(view_history_state, monkeypatch, caplog):
    """belief 模块异常 → warning + None (planner 走 legacy 规则, 不阻断)."""
    belief_mod, _, _ = view_history_state

    def _boom(student_id):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(belief_mod, "_get_or_create_student", _boom)

    import web.api.lca as lca_mod
    view = lca_mod._get_skill_mastery_view(SID)
    assert view is None
    assert any("skill_mastery_view 失败" in r.message for r in caplog.records)


# ── legacy select 路径真实传递 (对比存在性断言掩盖模式) ───────────────


def test_legacy_select_injects_view_into_cta_input(view_history_state, monkeypatch):
    belief_mod, _, record = view_history_state
    monkeypatch.setitem(belief_mod._STUDENT_STATES, SID, record)

    import web.api.lca as lca_mod

    # 重置模块全局 (对齐 test_lca_wired.fresh_lca_state 约定)
    lca_mod._engine = None
    lca_mod._store = None
    lca_mod._loaded_students = set()
    lca_mod.LCA_ENABLED = False

    captured = {}
    real_engine = lca_mod.get_lca_engine()

    class _CaptureEngine:
        def __getattr__(self, name):
            return getattr(real_engine, name)

        def select_intervention(self, cta_input):
            captured["input"] = cta_input
            return real_engine.select_intervention(cta_input)

    monkeypatch.setattr(lca_mod, "get_lca_engine", lambda: _CaptureEngine())

    result = lca_mod.select_intervention(SID, record["state"])
    assert result is not None, "LCA select_intervention 应该返回 LCAResult"
    assert "input" in captured, "select_intervention 应该走到 legacy 路径"
    assert captured["input"].skill_mastery_view is not None, \
        "产品路径 CTAInput 必须携带 skill_mastery_view (接线断言, 非存在性断言)"
    assert "python.loops" in captured["input"].skill_mastery_view
