"""v0.93.0-b: PluginRuntime 第 8 subscriber pomdp_diagnostic_updated 测试.

对应设计: discussions/2026-08-12-v093-design.md §3.

测试范围 (3 tests):
  1. PluginRuntime.start() 注册 8 subscriber (1 test): subscription_count == 8
  2. PluginRuntime._handle_pomdp_diagnostic_updated (1 test): 调 Runtime.diagnose_pomdp + 写结果
  3. PluginRuntime.get_last_diagnostic_result (1 test): Plugin 读 _diagnostic_results[student_id]
"""

from __future__ import annotations

from datetime import datetime

import pytest


# ---------------------------------------------------------------------------
# 1. PluginRuntime.start() 注册 8 subscriber (1 test)
# ---------------------------------------------------------------------------


def test_plugin_runtime_start_registers_8_subscribers():
    """PluginRuntime.start() 注册 8 subscriber (含 pomdp_diagnostic_updated).

    7 subscribers (v0.91.0-b): response_submitted, request_calibration,
    request_intervention, hint_requested, idle_detected, goal_changed,
    reflection_completed.
    v0.93.0-b: +1 = pomdp_diagnostic_updated → 共 8 subscribers.
    """
    from ecos.event import get_default_bus
    from web.api.plugin_runtime import PluginRuntime

    runtime = PluginRuntime(bus=get_default_bus())
    try:
        runtime.start()
        assert runtime.subscription_count == 8
        assert runtime.is_started is True
    finally:
        runtime.stop()


# ---------------------------------------------------------------------------
# 2. PluginRuntime._handle_pomdp_diagnostic_updated (1 test)
# ---------------------------------------------------------------------------


def test_plugin_runtime_handle_pomdp_diagnostic_updated_writes_result():
    """PluginRuntime._handle_pomdp_diagnostic_updated 调 Runtime.diagnose_pomdp + 写 _diagnostic_results."""
    from ecos.cta.event_log import LearningEvent
    from ecos.event import get_default_bus
    from ecos.lca.l4_optimization.policy_learner import LCAPolicyLearner
    from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig
    from ecos.lca.l4_optimization.linucb import BanditConfig
    from ecos.lca.policy_learner import PolicyLearnerConfig
    from web.api.plugin_runtime import PluginRuntime

    # 准备 LCAEngine (POMDP policy)
    cfg = LCAEngineConfig(
        policy_learner_config=PolicyLearnerConfig(
            bandit_config=BanditConfig(n_arms=4),
            policy_type="pomdp", pomdp_seed=42,
            pomdp_use_pbvi=True, pomdp_use_learned_t_r=True,
        )
    )
    lca = LCAEngine(config=cfg)
    lca.policy_learner._learners["lbc001"] = LCAPolicyLearner(
        BanditConfig(n_arms=4), policy_type="pomdp", pomdp_seed=42,
        pomdp_use_pbvi=True, pomdp_use_learned_t_r=True,
    )

    runtime = PluginRuntime(
        bus=get_default_bus(), lca_engine_factory=lambda: lca,
    )
    try:
        runtime.start()

        # publish pomdp_diagnostic_updated event
        import uuid as _uuid
        event = LearningEvent(
            event_id=f"evt_{_uuid.uuid4().hex[:8]}",
            student_id="lbc001",
            event_type="pomdp_diagnostic_updated",
            timestamp=datetime.now(),
            source="plugin",
            payload={},
        )
        get_default_bus().publish("pomdp_diagnostic_updated", event)

        # handler 写入 _diagnostic_results
        diag = runtime.get_last_diagnostic_result("lbc001")
        assert diag is not None
        assert diag.T.mean.shape == (4, 4, 4)
    finally:
        runtime.stop()


# ---------------------------------------------------------------------------
# 3. PluginRuntime.get_last_diagnostic_result (1 test)
# ---------------------------------------------------------------------------


def test_plugin_runtime_get_last_diagnostic_result_returns_none_when_no_event():
    """PluginRuntime.get_last_diagnostic_result 没 publish event → 返 None."""
    from web.api.plugin_runtime import PluginRuntime

    runtime = PluginRuntime()
    try:
        runtime.start()
        result = runtime.get_last_diagnostic_result("lbc001")
        assert result is None
    finally:
        runtime.stop()