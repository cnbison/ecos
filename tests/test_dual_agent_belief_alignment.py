"""v0.62.1: dual_agent bloom_target 跟 belief.py 对齐测试.

目标 (按 v0.62.1 Definition of Done):
  1. dual_agent state 跟 belief.py state bloom_target 对齐 (v0.60.4 错位 BUG 修复)
  2. dual_agent 拿深拷贝, 改自己 state 不污染 belief.py
  3. belief.py 改 state 不影响 dual_agent (双向隔离)
  4. 新学生 (belief.py 也没状态) 兜底 create_initial_state

根因 (v0.60.4 验证发现):
  之前 web/api/dual_agent.py _load_dual_state_if_needed → orch._init_fresh_state →
  cta_engine.create_initial_state → 全 0 初始 state (bloom=REMEMBER)
  belief.py 累加 32+ 道后 bloom=EVALUATE → 双流程 bloom_target 错位
  v0.62.1 修复: DB 无状态时从 belief.py 拿深拷贝, 避免脱节
"""

from __future__ import annotations

import pytest


# ─── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def fresh_both():
    """重置 dual_agent + belief.py 模块状态 (跟 test_lca_persistence 同样模式)."""
    import web.api.dual_agent as dual_mod
    import web.api.belief as belief_mod
    from ecos.persistence import dual_agent_store as da_store_mod
    from ecos.persistence.dual_agent_store import get_dual_agent_store

    # 重置 dual_agent 模块状态
    dual_mod._orchestrator = None
    dual_mod._dual_store = None
    dual_mod._loaded_students = set()
    dual_mod.DUAL_AGENT_ENABLED = True

    # 重置 belief.py 模块状态
    belief_mod._STUDENT_STATES = {}

    # 重置 store 单例
    da_store_mod._store = None

    # 清理 test students
    for sid in (
        "test_belief_align_a",
        "test_belief_align_b",
        "test_belief_align_c",
        "test_belief_align_new",
    ):
        try:
            get_dual_agent_store().delete_state(sid)
        except Exception:
            pass

    yield dual_mod, belief_mod

    # 测后清理
    try:
        da_store_mod._store.close() if da_store_mod._store else None
    except Exception:
        pass
    da_store_mod._store = None


# ─── 1. bloom_target 对齐 (核心 DoD) ───────────────────────────────


class TestBloomTargetAlignment:
    """v0.62.1: dual_agent state 跟 belief.py state bloom_target 对齐."""

    def test_bloom_target_matches_belief_py_after_update(self, fresh_both):
        """belief.py 累加 3 道后, dual_agent state bloom_dominant 跟 belief.py 一致."""
        from web.api.belief import submit_answer, _get_or_create_student
        from web.api.dual_agent import get_dual_orchestrator, _load_dual_state_if_needed

        dual_mod, belief_mod = fresh_both
        sid = "test_belief_align_a"

        # 1. belief.py 累加 3 道题
        from ecos.cta.belief_state import BloomLevel
        for i, correct in enumerate([True, True, False]):
            submit_answer(
                student_id=sid,
                problem_id=f"P{i}",
                skill_id="S1",
                correct=correct,
                bloom_layer="L4",
                user_answer=f"answer_{i}",
                correct_answer="x",
            )
        # 拿 belief.py 最新 state
        belief_student = _get_or_create_student(sid)
        belief_state = belief_student["state"]
        belief_dominant = belief_state.bloom_profile.dominant_layer
        belief_k_theta = belief_state.K.theta

        # 2. dual_agent lazy load (DB 无状态 → 走 v0.62.1 新逻辑)
        _load_dual_state_if_needed(sid)
        dual_orch = get_dual_orchestrator()
        dual_state = dual_orch.state[sid]

        # 3. 验证: bloom_dominant / K.theta 跟 belief.py 一致
        assert dual_state.bloom_profile.dominant_layer == belief_dominant, (
            f"v0.62.1 修复失败: dual_agent bloom_dominant={dual_state.bloom_profile.dominant_layer.name} "
            f"!= belief.py bloom_dominant={belief_dominant.name}"
        )
        assert dual_state.K.theta == pytest.approx(belief_k_theta, abs=1e-6), (
            f"v0.62.1 修复失败: dual_agent K.theta={dual_state.K.theta} "
            f"!= belief.py K.theta={belief_k_theta}"
        )

    def test_new_student_falls_back_to_initial_state(self, fresh_both):
        """新学生 (belief.py 也没状态) → 兜底 create_initial_state, 跟 v0.60.0 行为一致."""
        from web.api.dual_agent import get_dual_orchestrator, _load_dual_state_if_needed
        from ecos.cta.belief_engine import BeliefEngine

        dual_mod, belief_mod = fresh_both
        sid = "test_belief_align_new"

        # 直接调 _load_dual_state_if_needed (不预置 belief.py 状态)
        # v0.62.1 实现: _init_dual_state_from_belief_py → _get_or_create_student 会自动 create_initial_state
        _load_dual_state_if_needed(sid)
        dual_orch = get_dual_orchestrator()

        # 验证: dual_agent state 是 initial state (K.theta=0, 默认 bloom)
        from ecos.cta.belief_state import BloomLevel
        assert sid in dual_orch.state
        assert dual_orch.state[sid].K.theta == pytest.approx(0.0, abs=1e-6)
        # 新学生 bloom_dominant 默认 L1 REMEMBER (跟 belief.py 一样)


# ─── 2. 双向隔离 (深拷贝验证) ──────────────────────────────────────


class TestStateIsolation:
    """v0.62.1: dual_agent 改自己 state 不污染 belief.py (深拷贝)."""

    def test_dual_agent_update_does_not_pollute_belief_py(self, fresh_both):
        """dual_agent 跑 process_observation 后, belief.py state K.theta 不变."""
        from web.api.belief import submit_answer, _get_or_create_student
        from web.api.dual_agent import get_dual_orchestrator, _load_dual_state_if_needed
        from ecos.cta.belief_engine import Observation
        from ecos.cta.belief_state import BloomLevel

        dual_mod, belief_mod = fresh_both
        sid = "test_belief_align_b"

        # 1. belief.py 累加 1 道
        submit_answer(
            student_id=sid,
            problem_id="P1",
            skill_id="S1",
            correct=True,
            bloom_layer="L3",
            user_answer="x",
            correct_answer="x",
        )
        belief_state_before = _get_or_create_student(sid)["state"]
        belief_k_theta_before = belief_state_before.K.theta

        # 2. dual_agent lazy load (拿深拷贝)
        _load_dual_state_if_needed(sid)
        dual_orch = get_dual_orchestrator()
        dual_k_theta_before = dual_orch.state[sid].K.theta
        assert dual_k_theta_before == pytest.approx(belief_k_theta_before, abs=1e-6)

        # 3. dual_agent 跑 process_observation (改自己 state)
        obs = Observation(
            problem_id="P2",
            skill_id="S1",
            correct=False,
            score=0.0,
            bloom_level=BloomLevel.APPLY,
            response_time_sec=0.0,
        )
        dual_orch.process_observation(obs, student_id=sid)

        # 4. 验证: belief.py state K.theta **不变** (深拷贝隔离)
        belief_state_after = _get_or_create_student(sid)["state"]
        assert belief_state_after.K.theta == pytest.approx(belief_k_theta_before, abs=1e-6), (
            f"v0.62.1 修复失败: dual_agent 改自己 state 污染了 belief.py "
            f"({belief_k_theta_before} → {belief_state_after.K.theta})"
        )
        # dual_agent 自己 state 可能已变 (K.theta 跌)
        # 但双流程隔离, belief.py 不受影响

    def test_belief_py_update_does_not_pollute_dual_agent(self, fresh_both):
        """belief.py 累加后, dual_agent 已加载的 state 不变 (snapshot 一致性)."""
        from web.api.belief import submit_answer, _get_or_create_student
        from web.api.dual_agent import get_dual_orchestrator, _load_dual_state_if_needed

        dual_mod, belief_mod = fresh_both
        sid = "test_belief_align_c"

        # 1. belief.py 累加 1 道
        submit_answer(
            student_id=sid,
            problem_id="P1",
            skill_id="S1",
            correct=True,
            bloom_layer="L2",
            user_answer="x",
            correct_answer="x",
        )

        # 2. dual_agent lazy load
        _load_dual_state_if_needed(sid)
        dual_orch = get_dual_orchestrator()
        dual_k_theta_after_load = dual_orch.state[sid].K.theta

        # 3. belief.py 再累加 1 道 (跟 dual_agent 已加载的 state 解耦)
        submit_answer(
            student_id=sid,
            problem_id="P2",
            skill_id="S1",
            correct=True,
            bloom_layer="L3",
            user_answer="x",
            correct_answer="x",
        )
        belief_k_theta_new = _get_or_create_student(sid)["state"].K.theta
        # 验证 belief.py 确实累加了
        assert belief_k_theta_new > dual_k_theta_after_load, (
            f"belief.py 应累加, 但 belief_k_theta_new={belief_k_theta_new} "
            f"<= dual_k_theta_after_load={dual_k_theta_after_load}"
        )

        # 4. dual_agent 已加载的 state **不变** (snapshot 隔离, 不会自动同步)
        # 这是设计意图: dual_agent 自己累加自己的 state, 不跟 belief.py 实时同步
        assert dual_orch.state[sid].K.theta == pytest.approx(
            dual_k_theta_after_load, abs=1e-6
        ), (
            f"v0.62.1 期望 dual_agent state 保持 load 时的 snapshot, "
            f"不应被 belief.py 后累加影响"
        )
