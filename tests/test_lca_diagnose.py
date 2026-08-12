"""v0.93.0-b: LCAEngine POMDP diagnostic 测试 (LCAEngine.get_pomdp_diagnostic + _collect_pomdp_diagnostic).

对应设计: discussions/2026-08-12-v093-design.md §3.

测试范围 (4 tests):
  1. LCAEngine.get_pomdp_diagnostic 缓存命中 (1 test): select 后缓存, get 返缓存
  2. LCAEngine.get_pomdp_diagnostic 缓存 miss + lazy collect (1 test): POMDP policy + 没缓存 → lazy
  3. LCAEngine.get_pomdp_diagnostic 非 POMDP policy (1 test): 返 None + warning
  4. LCAEngine._collect_pomdp_diagnostic 派生异常 (1 test): _log.warning + 返 None
"""

from __future__ import annotations

import logging

import pytest

from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig
from ecos.lca.l4_optimization.linucb import BanditConfig
from ecos.lca.policy_learner import PolicyLearnerConfig


# ---------------------------------------------------------------------------
# 1. LCAEngine.get_pomdp_diagnostic 缓存命中 (1 test)
# ---------------------------------------------------------------------------


def test_lca_engine_get_pomdp_diagnostic_cached_after_select(monkeypatch, caplog):
    """LCAEngine.select_intervention pomdp path 后 → get_pomdp_diagnostic 返缓存."""
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

    # 构造 minimal BeliefState (Lazy init 时 LCAEngine.select_intervention 用)
    state = BeliefState(student_id="lbc001")
    cta_input = CTAInput(student_id="lbc001", belief_state=state)

    # 触发 select_intervention pomdp path → auto-collect diagnostic
    lca.select_intervention(cta_input, audience="student")

    # 缓存命中
    diag = lca.get_pomdp_diagnostic("lbc001")
    assert diag is not None
    assert diag.T.mean.shape == (4, 4, 4)
    assert diag.R.mean.shape == (4, 4)
    assert diag.belief.shape == (4,)
    assert diag.schema_version == "0.93.0"


# ---------------------------------------------------------------------------
# 2. LCAEngine.get_pomdp_diagnostic 缓存 miss + lazy collect (1 test)
# ---------------------------------------------------------------------------


def test_lca_engine_get_pomdp_diagnostic_lazy_collect_on_miss():
    """LCAEngine.get_pomdp_diagnostic 缓存 miss → lazy collect (POMDP policy + learner 存在)."""
    cfg = LCAEngineConfig(
        policy_learner_config=PolicyLearnerConfig(
            bandit_config=BanditConfig(n_arms=4),
            policy_type="pomdp", pomdp_seed=42,
            pomdp_use_pbvi=True, pomdp_use_learned_t_r=True,
        )
    )
    lca = LCAEngine(config=cfg)

    # 触发 lazy init POMDPPolicy (PolicyLearner._get_learner 路径)
    # LCAEngine.get_pomdp_diagnostic 缓存 miss 时会查 _learners[student_id]
    # 这里需要手动 _learners[student_id] = LCAPolicyLearner(...) 触发 lazy
    from ecos.lca.l4_optimization import POMDPPolicy
    from ecos.lca.l4_optimization.policy_learner import LCAPolicyLearner

    lca.policy_learner._learners["lbc001"] = LCAPolicyLearner(
        BanditConfig(n_arms=4), policy_type="pomdp", pomdp_seed=42,
        pomdp_use_pbvi=True, pomdp_use_learned_t_r=True,
    )

    # 缓存 miss → lazy collect (POMDP policy + learner 存在)
    diag = lca.get_pomdp_diagnostic("lbc001")
    assert diag is not None
    assert diag.T.mean.shape == (4, 4, 4)


# ---------------------------------------------------------------------------
# 3. LCAEngine.get_pomdp_diagnostic 非 POMDP policy (1 test)
# ---------------------------------------------------------------------------


def test_lca_engine_get_pomdp_diagnostic_non_pomdp_returns_none(caplog):
    """LCAEngine.get_pomdp_diagnostic policy_type='linucb' → 返 None + _log.warning."""
    cfg = LCAEngineConfig(
        policy_learner_config=PolicyLearnerConfig(
            bandit_config=BanditConfig(n_arms=4),
            policy_type="linucb",
        )
    )
    lca = LCAEngine(config=cfg)

    with caplog.at_level(logging.WARNING):
        diag = lca.get_pomdp_diagnostic("lbc001")
    assert diag is None
    assert any("不是 POMDP" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# 4. LCAEngine._collect_pomdp_diagnostic 派生异常 (1 test)
# ---------------------------------------------------------------------------


def test_lca_engine_collect_pomdp_diagnostic_exception_returns_none(
    monkeypatch, caplog,
):
    """LCAEngine._collect_pomdp_diagnostic POMDPPolicy.get_diagnostic 抛异常 → _log.warning + 返 None."""
    cfg = LCAEngineConfig(
        policy_learner_config=PolicyLearnerConfig(
            bandit_config=BanditConfig(n_arms=4),
            policy_type="pomdp", pomdp_seed=42,
            pomdp_use_pbvi=True, pomdp_use_learned_t_r=True,
        )
    )
    lca = LCAEngine(config=cfg)

    # 触发 lazy init
    from ecos.lca.l4_optimization.policy_learner import LCAPolicyLearner

    lca.policy_learner._learners["lbc001"] = LCAPolicyLearner(
        BanditConfig(n_arms=4), policy_type="pomdp", pomdp_seed=42,
        pomdp_use_pbvi=True, pomdp_use_learned_t_r=True,
    )

    # monkeypatch POMDPPolicy.get_diagnostic 抛异常
    def boom(self):
        raise RuntimeError("simulated failure")

    from ecos.lca.l4_optimization.pomdp import POMDPPolicy
    monkeypatch.setattr(POMDPPolicy, "get_diagnostic", boom)

    with caplog.at_level(logging.WARNING):
        result = lca._collect_pomdp_diagnostic("lbc001")
    assert result is None
    assert any(
        "POMDPPolicy.get_diagnostic 失败" in rec.message for rec in caplog.records
    )