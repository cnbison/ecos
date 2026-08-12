"""v0.93.0-b: Runtime.diagnose_pomdp API 测试 (Runtime 第 8 API).

对应设计: discussions/2026-08-12-v093-design.md §3.

测试范围 (6 tests):
  1. Runtime.diagnose_pomdp 委托 LCAEngine (1 test): 返 POMDPDiagnostic 或 None
  2. Runtime.diagnose_pomdp POMDP policy + learner (2 tests): 缓存命中 / lazy collect
  3. Runtime.diagnose_pomdp 非 POMDP (1 test): 返 None
  4. Runtime.diagnose_pomdp kwargs lca_engine 注入 (1 test): 自定义 LCAEngine 路径
  5. Runtime.diagnose_pomdp __all__ 暴露 (1 test): 跟 plan_* API 同列
"""

from __future__ import annotations

import pytest

from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig
from ecos.lca.l4_optimization.linucb import BanditConfig
from ecos.lca.policy_learner import PolicyLearnerConfig
from ecos.runtime import api as runtime_api


# ---------------------------------------------------------------------------
# 1. Runtime.diagnose_pomdp 委托 LCAEngine (1 test)
# ---------------------------------------------------------------------------


def test_runtime_diagnose_pomdp_delegates_to_lca_engine():
    """Runtime.diagnose_pomdp(student_id) 委托 LCAEngine.get_pomdp_diagnostic, 返 POMDPDiagnostic."""
    from ecos.lca.l4_optimization.policy_learner import LCAPolicyLearner

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

    diag = runtime_api.diagnose_pomdp("lbc001", lca_engine=lca)
    assert diag is not None
    assert diag.T.mean.shape == (4, 4, 4)
    assert diag.R.mean.shape == (4, 4)


# ---------------------------------------------------------------------------
# 2. Runtime.diagnose_pomdp POMDP policy + learner (2 tests)
# ---------------------------------------------------------------------------


def test_runtime_diagnose_pomdp_caches_across_calls():
    """Runtime.diagnose_pomdp 第二次调用返 LCAEngine._pomdp_diagnostic 缓存 (同对象)."""
    from ecos.lca.l4_optimization.policy_learner import LCAPolicyLearner

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

    diag1 = runtime_api.diagnose_pomdp("lbc001", lca_engine=lca)
    diag2 = runtime_api.diagnose_pomdp("lbc001", lca_engine=lca)
    # 缓存命中 — 同对象 (POMDPDiagnostic frozen dataclass 不可变, identity 守恒)
    assert diag1 is diag2


def test_runtime_diagnose_pomdp_lazy_collect_after_select():
    """Runtime.plan_action_aware pomdp path 后 → diagnose_pomdp 返缓存 (auto-collect 触发)."""
    from ecos.lca.cta_input import CTAInput
    from ecos.cta.belief_state import BeliefState

    cfg = LCAEngineConfig(
        policy_learner_config=PolicyLearnerConfig(
            bandit_config=BanditConfig(n_arms=4),
            policy_type="pomdp", pomdp_seed=42,
            pomdp_use_pbvi=True, pomdp_use_learned_t_r=True,
        )
    )
    lca = LCAEngine(config=cfg)
    state = BeliefState(student_id="lbc001")
    cta_input = CTAInput(student_id="lbc001", belief_state=state)

    # 触发 plan_action_aware pomdp path → LCAEngine.select_intervention pomdp path → auto-collect
    runtime_api.plan_action_aware(
        student_id="lbc001", audience="student", lca_engine=lca, cta_input=cta_input,
    )

    # auto-collect 后缓存命中
    diag = runtime_api.diagnose_pomdp("lbc001", lca_engine=lca)
    assert diag is not None
    assert diag.T.mean.shape == (4, 4, 4)


# ---------------------------------------------------------------------------
# 3. Runtime.diagnose_pomdp 非 POMDP (1 test)
# ---------------------------------------------------------------------------


def test_runtime_diagnose_pomdp_returns_none_for_non_pomdp():
    """Runtime.diagnose_pomdp policy_type='linucb' → 返 None (per LCAEngine fallback)."""
    cfg = LCAEngineConfig(
        policy_learner_config=PolicyLearnerConfig(
            bandit_config=BanditConfig(n_arms=4),
            policy_type="linucb",
        )
    )
    lca = LCAEngine(config=cfg)

    diag = runtime_api.diagnose_pomdp("lbc001", lca_engine=lca)
    assert diag is None


# ---------------------------------------------------------------------------
# 4. Runtime.diagnose_pomdp kwargs lca_engine 注入 (1 test)
# ---------------------------------------------------------------------------


def test_runtime_diagnose_pomdp_lca_engine_kwarg():
    """Runtime.diagnose_pomdp(student_id, lca_engine=...) kwargs 注入自定义 LCAEngine."""
    from ecos.lca.l4_optimization.policy_learner import LCAPolicyLearner

    # 自定义 LCAEngine (跟 default singleton 隔离)
    cfg = LCAEngineConfig(
        policy_learner_config=PolicyLearnerConfig(
            bandit_config=BanditConfig(n_arms=4),
            policy_type="pomdp", pomdp_seed=99,
            pomdp_use_pbvi=True, pomdp_use_learned_t_r=True,
        )
    )
    custom_lca = LCAEngine(config=cfg)
    custom_lca.policy_learner._learners["lbc_custom"] = LCAPolicyLearner(
        BanditConfig(n_arms=4), policy_type="pomdp", pomdp_seed=99,
        pomdp_use_pbvi=True, pomdp_use_learned_t_r=True,
    )

    # kwargs 注入 — 走 custom LCAEngine (不是 default singleton)
    diag = runtime_api.diagnose_pomdp("lbc_custom", lca_engine=custom_lca)
    assert diag is not None


# ---------------------------------------------------------------------------
# 5. Runtime.diagnose_pomdp __all__ 暴露 (1 test)
# ---------------------------------------------------------------------------


def test_runtime_diagnose_pomdp_in_all():
    """Runtime.diagnose_pomdp 在 runtime_api.__all__ 暴露 (跟 plan_* API 同列)."""
    assert "diagnose_pomdp" in runtime_api.__all__