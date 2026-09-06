"""v0.98.0 (a-a): POMDP evolution 读取路径测试 (Runtime 第 9 API).

对应:
  - LCAEngine.get_pomdp_evolution (orchestrator, 紧邻 get_pomdp_diagnostic)
  - Runtime.diagnose_pomdp_evolution (第 9 Runtime API, 跟 diagnose_pomdp 并列)
  - evolution 断层: POMDPDiagnostic.to_dict() 不含 evolution (留在
    POMDPPolicy._evolution K=10), 此 API 补读取路径供 ParentEngagementPlugin
    / Parent API 消费

测试范围 (4 tests):
  1. get_pomdp_evolution 返演化序列 (snapshot 后)
  2. 非 POMDP policy → 返 None + warning
  3. learner 不存在 → 返 None
  4. Runtime.diagnose_pomdp_evolution 全链路 + __all__ 导出
"""

from __future__ import annotations

import pytest


def _make_pomdp_lca():
    """构造 POMDP policy LCAEngine + 注册一个 learner (复用 test_plugin_sdk_pomdp 模式)."""
    from ecos.lca.l4_optimization.linucb import BanditConfig
    from ecos.lca.l4_optimization.policy_learner import LCAPolicyLearner
    from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig
    from ecos.lca.policy_learner import PolicyLearnerConfig

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
    return lca


def test_get_pomdp_evolution_returns_snapshot_sequence():
    """snapshot 后 get_pomdp_evolution 返演化序列 (K=10 cap 内)."""
    lca = _make_pomdp_lca()
    learner = lca.policy_learner._learners["lbc001"]
    # 触发 2 次演化快照 (走 POMDPPolicy._take_evolution_snapshot 真实路径)
    learner.pomdp._take_evolution_snapshot()
    learner.pomdp._take_evolution_snapshot()

    evolution = lca.get_pomdp_evolution("lbc001")
    assert evolution is not None
    assert len(evolution) == 2
    # 元素是 POMDPDiagnostic frozen dataclass
    from ecos.lca.l4_optimization.pomdp_diagnostic import POMDPDiagnostic
    assert all(isinstance(d, POMDPDiagnostic) for d in evolution)


def test_get_pomdp_evolution_non_pomdp_policy_returns_none():
    """非 POMDP policy (linucb) → 返 None + warning (防御性自检 [1])."""
    from ecos.lca.l4_optimization.linucb import BanditConfig
    from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig
    from ecos.lca.policy_learner import PolicyLearnerConfig

    cfg = LCAEngineConfig(
        policy_learner_config=PolicyLearnerConfig(
            bandit_config=BanditConfig(n_arms=4),
            policy_type="linucb",
        )
    )
    lca = LCAEngine(config=cfg)
    assert lca.get_pomdp_evolution("lbc001") is None


def test_get_pomdp_evolution_missing_learner_returns_none():
    """learner 不存在 → 返 None (不 raise)."""
    lca = _make_pomdp_lca()
    assert lca.get_pomdp_evolution("stu_missing") is None


def test_runtime_diagnose_pomdp_evolution_end_to_end():
    """Runtime.diagnose_pomdp_evolution 全链路 (第 9 API) + __all__ 导出."""
    from ecos.runtime import api as runtime_api

    assert "diagnose_pomdp_evolution" in runtime_api.__all__

    lca = _make_pomdp_lca()
    learner = lca.policy_learner._learners["lbc001"]
    learner.pomdp._take_evolution_snapshot()

    evolution = runtime_api.diagnose_pomdp_evolution(
        "lbc001", lca_engine=lca,
    )
    assert evolution is not None and len(evolution) == 1
    # 与 kernel 路径同源 (POMDPPolicy._evolution 拷贝)
    assert evolution == learner.pomdp.get_evolution()


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
