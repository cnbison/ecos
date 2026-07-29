"""v0.62.0-A: dual_agent LCAEngine 独立实例测试.

目标 (按 v0.62.0-A Definition of Done):
  1. dual_agent LCAEngine 跟 web/api/lca.py LCAEngine 是不同实例
  2. dual_agent 内部 select/update 不影响 lca.py arm_pull_counts
  3. lca.py select/update 不影响 dual_agent 内部 arm_pull_counts
  4. per-student bandit 仍隔离 (v0.57.0 LCA 已有, v0.62.0-A 不破坏)

根因 (v0.60.0 留的 trade-off):
  之前 web/api/dual_agent.py:56 lca_engine = get_lca_engine() → 共享 LCAEngine
  同一次答题 lca_select 涨 1 + dual_agent internal select 涨 1 = arm_pull 涨 2
  v0.62.0-A 修复: dual_agent 用独立 LCAEngine 实例
"""

from __future__ import annotations

import pytest


# ─── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def fresh_both():
    """重置 dual_agent + lca 模块状态 (跟 test_lca_persistence 同样模式)."""
    import web.api.dual_agent as dual_mod
    import web.api.lca as lca_mod

    dual_mod._orchestrator = None
    dual_mod._dual_store = None
    dual_mod._loaded_students = set()
    dual_mod.DUAL_AGENT_ENABLED = True

    lca_mod._engine = None
    lca_mod._store = None
    lca_mod._loaded_students = set()
    lca_mod.LCA_ENABLED = False

    yield dual_mod, lca_mod

    # 测后清理
    dual_mod._orchestrator = None
    lca_mod._engine = None


# ─── 1. LCAEngine 实例隔离 ─────────────────────────────────────────


class TestLCAEngineInstanceIsolation:
    """v0.62.0-A: dual_agent LCAEngine 跟 lca.py LCAEngine 是不同实例."""

    def test_dual_agent_uses_independent_lca_engine(self, fresh_both):
        """dual_agent LCAEngine != lca.py LCAEngine (核心 DoD)."""
        from web.api.dual_agent import get_dual_orchestrator
        from web.api.lca import get_lca_engine

        dual_orch = get_dual_orchestrator()
        lca_engine = get_lca_engine()

        # 核心断言: dual_agent 内部 LCAEngine != lca.py 共享 LCAEngine
        assert dual_orch.lca_engine is not lca_engine, (
            "v0.62.0-A 修复失败: dual_agent 跟 lca.py 仍共享同一 LCAEngine"
        )

    def test_dual_agent_lca_engine_has_independent_bandit_dict(self, fresh_both):
        """dual_agent 内部 LCAEngine 有独立的 self.bandits dict."""
        from web.api.dual_agent import get_dual_orchestrator
        from web.api.lca import get_lca_engine

        dual_orch = get_dual_orchestrator()
        lca_engine = get_lca_engine()

        # 都是空 dict (lazy init)
        assert dual_orch.lca_engine.bandits is not lca_engine.bandits
        assert dual_orch.lca_engine.bandits == {}
        assert lca_engine.bandits == {}


# ─── 2. arm_pull_counts 互不串扰 ─────────────────────────────────


class TestArmPullCountsIsolation:
    """v0.62.0-A: dual_agent LCAEngine 跟 lca.py LCAEngine arm_pull 互不串扰."""

    def test_dual_agent_select_does_not_increment_lca_arm_pull(self, fresh_both):
        """dual_agent 跑 process_observation 后, lca.py arm_pull_counts 不变.

        关键事实 (v0.62.0-A 调研发现):
          - LinUCB.select_arm **不涨** arm_pull (只选 arm 不更新 state)
          - 只有 LinUCB.update(arm, context, reward) 才涨 arm_pull[arm] += 1
          - LCAEngine.select_intervention → 涨 0
          - LCAEngine.update → 涨 1
        """
        from web.api.dual_agent import get_dual_orchestrator
        from web.api.lca import get_lca_engine
        from ecos.cta.belief_engine import Observation
        from ecos.cta.belief_state import BloomLevel
        from ecos.lca.intervention import (
            CAStage, CLTLevel, Intervention, InterventionType,
        )

        dual_orch = get_dual_orchestrator()
        lca_engine = get_lca_engine()

        sid = "test_isolation_a"

        # 预置: lca.py 跑 1 次 select + 1 次 update (完整答题 cycle)
        from ecos.lca.orchestrator import CTAInput
        cta_state = dual_orch.cta_engine.create_initial_state(sid)
        cta_input = CTAInput(student_id=sid, belief_state=cta_state)
        lca_result = lca_engine.select_intervention(cta_input)  # 涨 0
        # 模拟 1 次 update
        intervention = Intervention(
            intervention_type=InterventionType.PRACTICE,
            bloom_target=BloomLevel.APPLY,
            clt_level=CLTLevel.DEVELOPING,
            ca_stage=CAStage.COACHING,
        )
        lca_engine.update(
            student_id=sid,
            intervention=lca_result.intervention,
            new_state=cta_state,
            state_delta=0.5,
        )  # 涨 1
        lca_total_before = sum(
            lca_engine._get_bandit(sid).bandit.arm_pull_counts.tolist()
        )
        assert lca_total_before == 1, (
            f"lca.py 预置 select+update 后 arm_pull 应为 1, 实际 {lca_total_before}"
        )

        # 跑 dual_agent 一次 (内部 select 涨 0 + update 涨 1, 但只走独立 LCAEngine)
        obs = Observation(
            problem_id="P1",
            skill_id="S1",
            correct=True,
            score=1.0,
            bloom_level=BloomLevel.APPLY,
            response_time_sec=0.0,
        )
        # 第二次 process_observation 才会触发 update (prev_calibrated 不为 None)
        dual_orch.process_observation(obs, student_id=sid)
        # 拿一个 intervention 喂给 prev, 让第二次能 update
        from ecos.dual_agent.protocol.messages import CalibratedLCAResult
        # 直接调 orch 内部 update 模拟, 不走完整 process_observation
        dual_orch.lca_engine.update(
            student_id=sid,
            intervention=lca_result.intervention,
            new_state=cta_state,
            state_delta=0.3,
        )

        # 验证: lca_engine arm_pull 没变 (仍是 1)
        lca_total_after = sum(
            lca_engine._get_bandit(sid).bandit.arm_pull_counts.tolist()
        )
        assert lca_total_after == 1, (
            f"v0.62.0-A 修复失败: dual_agent 跑后 lca.py arm_pull 从 1 → {lca_total_after}, "
            f"应该是 1 (dual_agent 走独立 LCAEngine 不应污染 lca.py)"
        )

    def test_lca_select_does_not_increment_dual_agent_arm_pull(self, fresh_both):
        """lca.py 跑 update 后, dual_agent 内部 arm_pull_counts 不变."""
        from web.api.dual_agent import get_dual_orchestrator
        from web.api.lca import get_lca_engine
        from ecos.lca.orchestrator import CTAInput
        from ecos.cta.belief_engine import Observation
        from ecos.cta.belief_state import BloomLevel
        from ecos.lca.intervention import (
            CAStage, CLTLevel, Intervention, InterventionType,
        )

        dual_orch = get_dual_orchestrator()
        lca_engine = get_lca_engine()

        sid = "test_isolation_b"

        # 预置: dual_agent 跑 1 次 process_observation (第一次, 无 prev → update 不调)
        obs = Observation(
            problem_id="P1",
            skill_id="S1",
            correct=True,
            score=1.0,
            bloom_level=BloomLevel.APPLY,
            response_time_sec=0.0,
        )
        dual_orch.process_observation(obs, student_id=sid)
        # 第一次 process_observation: select 涨 0 + update 不调 (无 prev) = arm_pull 涨 0
        dual_total_before = sum(
            dual_orch.lca_engine._get_bandit(sid).bandit.arm_pull_counts.tolist()
        )
        assert dual_total_before == 0, (
            f"dual_agent 预置 (首次) 后 arm_pull 应为 0 (select 不涨, update 无 prev 不调), "
            f"实际 {dual_total_before}"
        )

        # 跑 lca.py select + update
        cta_state = dual_orch.cta_engine.create_initial_state(sid)
        cta_input = CTAInput(student_id=sid, belief_state=cta_state)
        lca_result = lca_engine.select_intervention(cta_input)
        lca_engine.update(
            student_id=sid,
            intervention=lca_result.intervention,
            new_state=cta_state,
            state_delta=0.5,
        )

        # 验证: dual_agent 内部 arm_pull 没变 (仍是 0)
        dual_total_after = sum(
            dual_orch.lca_engine._get_bandit(sid).bandit.arm_pull_counts.tolist()
        )
        assert dual_total_after == 0, (
            f"v0.62.0-A 修复失败: lca.py 跑后 dual_agent arm_pull 从 0 → {dual_total_after}, "
            f"应该是 0 (独立 LCAEngine)"
        )


# ─── 3. per-student bandit 仍隔离 (回归测试) ─────────────────────


class TestPerStudentBanditStillIsolated:
    """v0.62.0-A 回归: v0.57.0 per-student bandit 隔离不破坏."""

    def test_two_students_bandit_isolated(self, fresh_both):
        """两学生 dual_agent 内部 LCAEngine 仍 per-student 隔离.

        注: select 不涨 arm_pull (LinUCB 内部行为), 只 update 涨.
            所以这个测试改成 select + update 验证 isolation.
        """
        from web.api.dual_agent import get_dual_orchestrator
        from ecos.lca.orchestrator import CTAInput
        from ecos.lca.intervention import (
            CAStage, CLTLevel, Intervention, InterventionType,
        )
        from ecos.cta.belief_state import BloomLevel

        dual_orch = get_dual_orchestrator()
        sid_a = "test_student_a"
        sid_b = "test_student_b"

        cta_state_a = dual_orch.cta_engine.create_initial_state(sid_a)
        cta_state_b = dual_orch.cta_engine.create_initial_state(sid_b)

        # student_a 跑 3 次完整 cycle (select + update)
        for _ in range(3):
            result_a = dual_orch.lca_engine.select_intervention(
                CTAInput(student_id=sid_a, belief_state=cta_state_a)
            )
            dual_orch.lca_engine.update(
                student_id=sid_a,
                intervention=result_a.intervention,
                new_state=cta_state_a,
                state_delta=0.5,
            )

        # student_b 跑 1 次完整 cycle
        result_b = dual_orch.lca_engine.select_intervention(
            CTAInput(student_id=sid_b, belief_state=cta_state_b)
        )
        dual_orch.lca_engine.update(
            student_id=sid_b,
            intervention=result_b.intervention,
            new_state=cta_state_b,
            state_delta=0.5,
        )

        # 验证: a 的 arm_pull 总和 == 3, b == 1
        a_total = sum(
            dual_orch.lca_engine._get_bandit(sid_a).bandit.arm_pull_counts.tolist()
        )
        b_total = sum(
            dual_orch.lca_engine._get_bandit(sid_b).bandit.arm_pull_counts.tolist()
        )
        assert a_total == 3
        assert b_total == 1
        # per-student bandit dict 隔离
        assert dual_orch.lca_engine.bandits[sid_a] is not dual_orch.lca_engine.bandits[sid_b]
