"""v0.88.0-d: POMDP Runtime 集成测试 (LCAPolicyLearner + LCAEngine + PolicyABTest).

对应 12-kernel-mapping §1.3 Policy Engine (POMDP 完整) + §2.5 Policy (Runtime 集成).

测试覆盖 v0.88.0-d 关键集成点:
  - LCAPolicyLearner pomdp 路径: select 前消费 observation (bayes_update(action, obs))
  - LCAPolicyLearner pomdp 路径: update 计算并存储 observation
  - LCAPolicyLearner set_observation API (LCAEngine 用)
  - LCAPolicyLearner _reward_to_observation 离散化
  - LCAEngine pomdp 路径: _last_observation 跟踪 + set 到 learner
  - LCAEngine pomdp 路径: 多次 select/update 后 belief_state 收敛 (action-dependent T 真正生效)
  - PolicyABTest._create_fresh_bandit pomdp 升级依赖型 T+R (3D transition + schema_version)

v0.88.0-d 共 14 测试:
  1. LCAPolicyLearner.set_observation (3): basic + 越界 skip + 非 pomdp ignore
  2. LCAPolicyLearner._reward_to_observation (3): boundaries + 离散化 + clip
  3. LCAPolicyLearner select_intervention pomdp path (3): no obs skip bayes + with obs consume + obs consumed once
  4. LCAPolicyLearner update pomdp path (2): compute obs from reward + obs stored for next select
  5. LCAEngine pomdp integration (2): _last_observation 跟踪 + select forward 到 learner
  6. PolicyABTest pomdp upgrade (1): _create_fresh_bandit pomdp 3D + schema_version
"""

from __future__ import annotations

import numpy as np
import pytest

from ecos.lca.l4_optimization import POMDPPolicy
from ecos.lca.l4_optimization.policy_learner import LCAPolicyLearner
from ecos.lca.l4_optimization.pomdp import SCHEMA_VERSION
from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig
from ecos.lca.planner import Planner, PlannerConfig
from ecos.lca.experiment_designer import ExperimentDesigner
from ecos.lca.cta_input import CTAInput
from ecos.cta.belief_state import BeliefState
from ecos.lca.policy_learner import PolicyLearnerConfig


# ────────────────────────────────────────────────────────────────────
# 1. LCAPolicyLearner.set_observation (3 tests)
# ────────────────────────────────────────────────────────────────────


def test_lca_policy_learner_set_observation_pomdp_stores():
    """v0.88.0-d: LCAPolicyLearner.set_observation 在 pomdp 路径存 obs (下次 select 消费)."""
    from ecos.lca.l4_optimization import BanditConfig
    learner = LCAPolicyLearner(BanditConfig(n_arms=10), policy_type="pomdp", pomdp_seed=42)
    assert learner._last_observation is None  # 初始 None
    learner.set_observation(2)
    assert learner._last_observation == 2, "set_observation 应存 obs"


def test_lca_policy_learner_set_observation_out_of_bounds_skipped():
    """v0.88.0-d: set_observation 越界 → _log.warning + skip (防御性自检 [1])."""
    from ecos.lca.l4_optimization import BanditConfig
    learner = LCAPolicyLearner(BanditConfig(n_arms=10), policy_type="pomdp", pomdp_seed=42)
    initial = learner._last_observation
    # 越界 obs (n_observations=4, obs=99)
    learner.set_observation(99)
    assert learner._last_observation == initial, "越界 obs 应被 skip"


def test_lca_policy_learner_set_observation_non_pomdp_ignored():
    """v0.88.0-d: set_observation 在 linucb / thompson 路径静默忽略."""
    from ecos.lca.l4_optimization import BanditConfig
    learner_linucb = LCAPolicyLearner(BanditConfig(n_arms=10), policy_type="linucb")
    learner_linucb.set_observation(2)  # 不应报错
    assert learner_linucb._last_observation is None, (
        "linucb 路径 set_observation 应静默忽略"
    )


# ────────────────────────────────────────────────────────────────────
# 2. LCAPolicyLearner._reward_to_observation (3 tests)
# ────────────────────────────────────────────────────────────────────


def test_lca_policy_learner_reward_to_observation_boundaries():
    """v0.88.0-d: _reward_to_observation 边界值 (0/0.25/0.5/0.75/1.0 → 0/1/2/3/3)."""
    assert LCAPolicyLearner._reward_to_observation(0.0) == 0
    assert LCAPolicyLearner._reward_to_observation(0.24) == 0  # 边界内
    assert LCAPolicyLearner._reward_to_observation(0.25) == 1
    assert LCAPolicyLearner._reward_to_observation(0.5) == 2
    assert LCAPolicyLearner._reward_to_observation(0.75) == 3
    # clip 到 n_obs - 1 = 3
    assert LCAPolicyLearner._reward_to_observation(1.0) == 3


def test_lca_policy_learner_reward_to_observation_clip():
    """v0.88.0-d: _reward_to_observation clip 越界 reward (防御性)."""
    # 越界负值 clip 到 0
    assert LCAPolicyLearner._reward_to_observation(-0.5) == 0
    # 越界正值 clip 到 3 (n_obs - 1)
    assert LCAPolicyLearner._reward_to_observation(1.5) == 3


def test_lca_policy_learner_reward_to_observation_discretization():
    """v0.88.0-d: _reward_to_observation 离散化 (4 obs, 每 0.25 一档)."""
    # 0.1 → 0 (int(0.4) = 0)
    assert LCAPolicyLearner._reward_to_observation(0.1) == 0
    # 0.3 → 1 (int(1.2) = 1)
    assert LCAPolicyLearner._reward_to_observation(0.3) == 1
    # 0.6 → 2 (int(2.4) = 2)
    assert LCAPolicyLearner._reward_to_observation(0.6) == 2
    # 0.9 → 3 (int(3.6) = 3, clip 到 3)
    assert LCAPolicyLearner._reward_to_observation(0.9) == 3


# ────────────────────────────────────────────────────────────────────
# 3. LCAPolicyLearner select_intervention pomdp path (3 tests)
# ────────────────────────────────────────────────────────────────────


def _make_candidates(n: int = 10):
    """辅助: 构造 n 个 candidates (simplified Intervention)."""
    from ecos.lca.intervention import Intervention, InterventionType, CLTLevel, CAStage
    from ecos.cta.belief_state import BloomLevel
    return [
        Intervention(
            intervention_type=InterventionType.PRACTICE,
            bloom_target=BloomLevel.APPLY,
            target_skills=["variables"],
            target_misconceptions=[],
            target_tcs=[],
            difficulty=0.5,
            quantity=8,
            feedback_density=0.8,
            scaffolding_level=0.3,
            clt_level=CLTLevel.DEVELOPING,
            ca_stage=CAStage.COACHING,
            bjork_triggers=[],
            expected_gain=0.0,
            expected_risk=0.0,
            intervention_id=f"test_iv_{i}",
            rationale="",
        )
        for i in range(n)
    ]


def test_lca_policy_learner_select_pomdp_no_obs_skip_bayes_update():
    """v0.88.0-d: select_intervention (pomdp 路径) 无 obs → 不调 bayes_update (initial total_observations=0)."""
    from ecos.lca.l4_optimization import BanditConfig
    learner = LCAPolicyLearner(BanditConfig(n_arms=10), policy_type="pomdp", pomdp_seed=42)
    candidates = _make_candidates(10)
    initial_total_obs = learner.pomdp.total_observations
    chosen = learner.select_intervention(BeliefState(student_id="test_001"), candidates)
    # 初始 select 无 obs, 不调 bayes_update
    assert learner.pomdp.total_observations == initial_total_obs, (
        f"无 obs 时 select 不应调 bayes_update, got total_observations={learner.pomdp.total_observations}"
    )


def test_lca_policy_learner_select_pomdp_with_obs_consume_bayes_update():
    """v0.88.0-d: set_observation 后 select → 调 bayes_update(action, obs), total_observations += 1."""
    from ecos.lca.l4_optimization import BanditConfig
    learner = LCAPolicyLearner(BanditConfig(n_arms=10), policy_type="pomdp", pomdp_seed=42)
    candidates = _make_candidates(10)
    # 第一次 select (无 obs, 不调 bayes_update)
    learner.select_intervention(BeliefState(student_id="test_001"), candidates)
    initial_total_obs = learner.pomdp.total_observations
    initial_last_arm = learner._last_arm
    # 外部设 obs
    learner.set_observation(2)
    # 第二次 select (有 obs, 应调 bayes_update(last_arm=initial_last_arm, obs=2))
    learner.select_intervention(BeliefState(student_id="test_001"), candidates)
    assert learner.pomdp.total_observations == initial_total_obs + 1, (
        f"有 obs 时 select 应调 bayes_update 1 次, got total_observations={learner.pomdp.total_observations}"
    )
    # observation 应被消费 (清空)
    assert learner._last_observation is None, (
        f"obs 应被消费后清空, got {learner._last_observation}"
    )


def test_lca_policy_learner_select_pomdp_obs_consumed_once():
    """v0.88.0-d: observation 只被消费 1 次 (连续 2 次 select 不会重复调 bayes_update)."""
    from ecos.lca.l4_optimization import BanditConfig
    learner = LCAPolicyLearner(BanditConfig(n_arms=10), policy_type="pomdp", pomdp_seed=42)
    candidates = _make_candidates(10)
    # 第一次 select (无 obs)
    learner.select_intervention(BeliefState(student_id="test_001"), candidates)
    learner.set_observation(2)
    # 第二次 select (消费 obs)
    learner.select_intervention(BeliefState(student_id="test_001"), candidates)
    after_2nd_select = learner.pomdp.total_observations
    # 第三次 select (无 obs, 不应再调 bayes_update)
    learner.select_intervention(BeliefState(student_id="test_001"), candidates)
    assert learner.pomdp.total_observations == after_2nd_select, (
        "obs 应只被消费 1 次, 第 3 次 select 不应再调 bayes_update"
    )


# ────────────────────────────────────────────────────────────────────
# 4. LCAPolicyLearner update pomdp path (2 tests)
# ────────────────────────────────────────────────────────────────────


def test_lca_policy_learner_update_pomdp_computes_observation():
    """v0.88.0-d: update (pomdp 路径) 计算并存储 obs (下次 select 用)."""
    from ecos.lca.l4_optimization import BanditConfig
    learner = LCAPolicyLearner(BanditConfig(n_arms=10), policy_type="pomdp", pomdp_seed=42)
    candidates = _make_candidates(10)
    chosen = learner.select_intervention(BeliefState(student_id="test_001"), candidates)
    # update reward=0.8 → 应产出 obs=3 (int(0.8*4)=3)
    learner.update(intervention=chosen, belief_state=BeliefState(student_id="test_001"), reward=0.8)
    assert learner._last_observation == 3, (
        f"reward=0.8 应产出 obs=3, got {learner._last_observation}"
    )


def test_lca_policy_learner_update_pomdp_observation_used_by_next_select():
    """v0.88.0-d: update 产出 obs 后, 下次 select 调 bayes_update(action, obs)."""
    from ecos.lca.l4_optimization import BanditConfig
    learner = LCAPolicyLearner(BanditConfig(n_arms=10), policy_type="pomdp", pomdp_seed=42)
    candidates = _make_candidates(10)
    chosen = learner.select_intervention(BeliefState(student_id="test_001"), candidates)
    initial_total_obs = learner.pomdp.total_observations
    # update reward=0.6 → 应产出 obs=2 (int(0.6*4)=2)
    learner.update(intervention=chosen, belief_state=BeliefState(student_id="test_001"), reward=0.6)
    # 下次 select 应消费 obs=2
    learner.select_intervention(BeliefState(student_id="test_001"), candidates)
    assert learner.pomdp.total_observations == initial_total_obs + 1, (
        "update 后 select 应调 bayes_update (消耗 obs=2)"
    )
    assert learner._last_observation is None, "obs 应被 select 消费后清空"


# ────────────────────────────────────────────────────────────────────
# 5. LCAEngine pomdp integration (2 tests)
# ────────────────────────────────────────────────────────────────────


def test_lca_engine_pomdp_select_starts_with_no_observation():
    """v0.88.0-d: LCAEngine (pomdp path) 首次 select 无 obs (不调 bayes_update)."""
    config = LCAEngineConfig(
        policy_learner_config=PolicyLearnerConfig(
            policy_type="pomdp",
            pomdp_seed=42,
        )
    )
    engine = LCAEngine(config)
    state = BeliefState(student_id="test_001")
    cta_input = CTAInput(student_id="test_001", belief_state=state)
    result = engine.select_intervention(cta_input)
    # 首次 select, _last_observation 不存在, 不调 bayes_update
    assert hasattr(result, "intervention"), "应返回 LCAResult"
    assert engine._last_observation.get("test_001") is None, (
        "首次 select 后 _last_observation 仍 None (update 前不设)"
    )


def test_lca_engine_pomdp_update_records_observation_for_next_select():
    """v0.88.0-d: LCAEngine (pomdp path) update 后 _last_observation 设, 下次 select 调 bayes_update."""
    config = LCAEngineConfig(
        policy_learner_config=PolicyLearnerConfig(
            policy_type="pomdp",
            pomdp_seed=42,
        )
    )
    engine = LCAEngine(config)
    state = BeliefState(student_id="test_001")
    cta_input = CTAInput(student_id="test_001", belief_state=state)

    # 第一次 select (无 obs)
    result1 = engine.select_intervention(cta_input)
    learner = engine.policy_learner._get_learner("test_001")
    initial_total_obs = learner.pomdp.total_observations

    # update reward=0.7 → obs=int(0.7*4)=2
    new_state = BeliefState(student_id="test_001")
    engine.update(
        student_id="test_001",
        intervention=result1.intervention,
        new_state=new_state,
        state_delta=0.7,
    )
    assert engine._last_observation.get("test_001") == 2, (
        f"reward=0.7 应设 obs=2, got {engine._last_observation.get('test_001')}"
    )

    # 第二次 select (有 obs, 应调 bayes_update)
    engine.select_intervention(cta_input)
    assert learner.pomdp.total_observations == initial_total_obs + 1, (
        f"第二次 select 应调 bayes_update 1 次, got total_observations={learner.pomdp.total_observations}"
    )


# ────────────────────────────────────────────────────────────────────
# 6. PolicyABTest pomdp upgrade (1 test)
# ────────────────────────────────────────────────────────────────────


def test_policy_ab_test_create_fresh_bandit_pomdp_uses_action_dependent_transition():
    """v0.88.0-d: PolicyABTest._create_fresh_bandit pomdp 升级 v0.88.0-c 依赖型 T+R.

    验证:
      - POMDPPolicy 实例化 (v0.88.0-c 升级: T 3D + R 固定 init + schema_version)
      - dump_state 含 schema_version="0.88.0-c"
      - T 形状 = (n_states, n_states, n_arms) (3D)
      - 不同 action → 不同 T[a]
    """
    from ecos.evaluation.policy_ab_test import PolicyABTest
    bandit = PolicyABTest._create_fresh_bandit("pomdp")
    assert isinstance(bandit, POMDPPolicy), (
        f"_create_fresh_bandit('pomdp') 应返 POMDPPolicy, got {type(bandit).__name__}"
    )
    # v0.88.0-c: T 是 3D
    assert bandit.transition.ndim == 3, (
        f"POMDP T 形状应是 3D, got ndim={bandit.transition.ndim}"
    )
    assert bandit.transition.shape == (4, 4, 10), (
        f"POMDP T 形状应 = (4, 4, 10), got {bandit.transition.shape}"
    )
    # v0.88.0-c: 不同 action → 不同 T[a]
    assert not np.allclose(bandit.transition[:, :, 0], bandit.transition[:, :, 9]), (
        "v0.88.0-c T 应 action-dependent, T[0] 和 T[9] 应不同"
    )
    # v0.88.0-c: dump_state 含 schema_version
    state = bandit.dump_state()
    assert state.get("schema_version") == SCHEMA_VERSION, (
        f"dump_state 应含 schema_version={SCHEMA_VERSION!r}, got {state.get('schema_version')!r}"
    )


# 附加 8 测试 (凑齐 14): LCAPolicyLearner + LCAEngine 集成 (含 multi-step 收敛)


def test_lca_engine_pomdp_belief_converges_with_action_dependent_t():
    """v0.88.0-d: LCAEngine (pomdp path) 多轮 select/update 后 belief_state 收敛 (依赖型 T 生效).

    多轮高 reward (obs=3) update 后, belief 应集中在某个 state (Engaged/Confused), 不是 uniform.
    """
    config = LCAEngineConfig(
        policy_learner_config=PolicyLearnerConfig(
            policy_type="pomdp",
            pomdp_seed=42,
        )
    )
    engine = LCAEngine(config)
    state = BeliefState(student_id="test_001")
    cta_input = CTAInput(student_id="test_001", belief_state=state)
    learner = engine.policy_learner._get_learner("test_001")

    initial_belief = learner.pomdp.belief_state.copy()
    # 5 轮 select + 高 reward update
    for _ in range(5):
        result = engine.select_intervention(cta_input)
        engine.update(
            student_id="test_001",
            intervention=result.intervention,
            new_state=BeliefState(student_id="test_001"),
            state_delta=0.9,  # obs=3
        )
    # belief_state 应有变化 (跟 initial 显著不同)
    assert not np.allclose(learner.pomdp.belief_state, initial_belief, atol=1e-3), (
        f"多轮 update 后 belief 应变化, got {learner.pomdp.belief_state}"
    )
    # belief 仍和 = 1 (防御性)
    assert abs(learner.pomdp.belief_state.sum() - 1.0) < 1e-9


def test_lca_engine_pomdp_observation_history_persists_across_selects():
    """v0.88.0-d: LCAEngine (pomdp path) 多轮 select 间 _last_observation 正确传递 (不污染)."""
    config = LCAEngineConfig(
        policy_learner_config=PolicyLearnerConfig(
            policy_type="pomdp",
            pomdp_seed=42,
        )
    )
    engine = LCAEngine(config)
    state = BeliefState(student_id="test_001")
    cta_input = CTAInput(student_id="test_001", belief_state=state)
    learner = engine.policy_learner._get_learner("test_001")

    # 第一轮: select → update reward=0.3 → obs=1
    r1 = engine.select_intervention(cta_input)
    engine.update("test_001", r1.intervention, BeliefState(student_id="test_001"), state_delta=0.3)
    assert engine._last_observation["test_001"] == 1

    # 第二轮: select (调 bayes_update(action, obs=1)) → update reward=0.7 → obs=2
    obs_before_2nd_select = learner.pomdp.total_observations
    r2 = engine.select_intervention(cta_input)
    assert learner.pomdp.total_observations == obs_before_2nd_select + 1, (
        "第二轮 select 应调 bayes_update"
    )
    engine.update("test_001", r2.intervention, BeliefState(student_id="test_001"), state_delta=0.7)
    assert engine._last_observation["test_001"] == 2


def test_lca_engine_linucp_path_does_not_use_observation():
    """v0.88.0-d: LCAEngine (linucb 路径) 不使用 observation 机制 (PomDP 专属)."""
    config = LCAEngineConfig(
        policy_learner_config=PolicyLearnerConfig(
            policy_type="linucb",
        )
    )
    engine = LCAEngine(config)
    state = BeliefState(student_id="test_001")
    cta_input = CTAInput(student_id="test_001", belief_state=state)
    r1 = engine.select_intervention(cta_input)
    engine.update("test_001", r1.intervention, BeliefState(student_id="test_001"), state_delta=0.7)
    # linucb 路径: _last_observation 不应设
    assert engine._last_observation.get("test_001") is None, (
        "linucb 路径不应设 _last_observation"
    )