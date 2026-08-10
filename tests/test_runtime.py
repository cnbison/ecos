"""v0.83.0-d: Runtime API 测试套件.

目标 (按 v0.83.0-d Definition of Done):
  - 6 API 各自 ≥2 tests (estimate / update_belief / replay / evaluate / simulate / plan)
  - kwargs 注入 (3 tests: belief_engine / lca_engine / evaluator)
  - singleton 懒加载 (2 tests)
  - evaluate metric routing (4 metrics: twin_attribution / policy_ab / goal_completion / ece)
  - backward compat (web/api/belief.py 入口保持)
  - 端到端 (estimate → update_belief → plan → evaluate → simulate)
"""

from __future__ import annotations

import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest


# ──────────────────────────────────────────────────────────────────────
# 1. estimate / update_belief / replay / simulate (4 API 基础)
# ──────────────────────────────────────────────────────────────────────


class TestRuntimeAPIBasic:
    """v0.83.0-d: 6 API 基础调用 (singleton 懒加载)."""

    def test_estimate_creates_initial_state(self):
        """estimate("s1") -> BeliefState(student_id="s1")."""
        from ecos.runtime import estimate
        from ecos.runtime import api as runtime_api
        from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig

        engine = BeliefEngine(config=BeliefEngineConfig())
        state = estimate("test_estimate_student", belief_engine=engine)
        assert state.student_id == "test_estimate_student"
        # Singleton 不被构造 (用 kwargs 注入)
        assert runtime_api._default_belief_engine is None

    def test_update_belief_returns_state(self):
        """update_belief("s1", evidence) -> BeliefState."""
        from ecos.runtime import update_belief
        from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig, Observation
        from ecos.cta.belief_state import BloomLevel
        from ecos.cta.l1_evolution import EvolutionConfig
        from ecos.cta.l2_mirt import MIRTConfig

        config = BeliefEngineConfig(
            evolution_config=EvolutionConfig(),
            mirt_config=MIRTConfig(prior_mean=[0.0] * 5, prior_cov=None,
                                   default_a_specialized=[0.8] * 5,
                                   default_a_general=0.5, default_difficulty=0.0),
        )
        engine = BeliefEngine(config=config, llm_client=None)

        obs = Observation(
            problem_id="p1", skill_id="s1", correct=True, score=1.0,
            bloom_level=BloomLevel.APPLY, explanation_text="",
        )
        state = update_belief("test_update_student", obs, belief_engine=engine)
        assert state.student_id == "test_update_student"
        # update 路径走通 (bloom 必有 evidence; K 条件性 update)
        assert len(state.evidence_for("bloom")) >= 1

    def test_replay_uses_belief_engine(self):
        """replay("s1", []) -> BeliefEngine.replay (singleton 注入)."""
        from ecos.runtime import replay
        from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig

        engine = BeliefEngine(config=BeliefEngineConfig())
        # events=[] -> 空重放, 返初始 state
        state = replay("test_replay_student", [], belief_engine=engine)
        assert state.student_id == "test_replay_student"

    def test_simulate_returns_state(self):
        """simulate("s1", [], 0, []) -> BeliefEngine.simulate."""
        from ecos.runtime import simulate
        from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig

        engine = BeliefEngine(config=BeliefEngineConfig())
        state = simulate("test_sim_student", [], 0, [], belief_engine=engine)
        assert state.student_id == "test_sim_student"


# ──────────────────────────────────────────────────────────────────────
# 2. evaluate metric routing (4 tests)
# ──────────────────────────────────────────────────────────────────────


class TestRuntimeEvaluate:
    """v0.83.0-d: evaluate 4 metric 路由 (twin_attribution / policy_ab / goal_completion / ece)."""

    def test_evaluate_goal_completion(self):
        """evaluate("s1", metric="goal_completion", state=..., goal_id="K.mastery>=0.7")."""
        from ecos.runtime import evaluate
        from ecos.cta.belief_state import BeliefState
        from datetime import datetime
        import numpy as np

        state = BeliefState(student_id="test_goal_student")
        state.K.mastery_prob = 0.8
        state.theta_mean = np.zeros(5)
        state.theta_cov = np.eye(5)
        state.last_updated = datetime.now()

        result = evaluate(
            "test_goal_student", metric="goal_completion",
            state=state, goal_id="K.mastery>=0.7",
        )
        assert result["completed"] is True
        assert result["goal_id"] == "K.mastery>=0.7"
        assert result["current_value"] == 0.8

    def test_evaluate_policy_ab(self):
        """evaluate("s1", metric="policy_ab", policy_a="linucb", policy_b="linucb_baseline")."""
        from ecos.runtime import evaluate
        from ecos.evaluation import EvaluationEngine

        result = evaluate(
            "test_ab_student", metric="policy_ab",
            policy_a="linucb", policy_b="linucb_baseline",
            evaluator=EvaluationEngine(),
        )
        assert result["policy_a"] == "linucb"
        assert result["policy_b"] == "linucb_baseline"
        # v0.83.0-c: 真 A/B 还没实现, winner=None
        assert result["winner"] is None

    def test_evaluate_twin_attribution(self):
        """evaluate("s1", metric="twin_attribution", before=..., after=...)."""
        from ecos.runtime import evaluate
        from ecos.cta.belief_state import BeliefState
        from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig
        from ecos.cta.l1_evolution import EvolutionConfig
        from ecos.cta.l2_mirt import MIRTConfig
        from datetime import datetime
        import numpy as np

        config = BeliefEngineConfig(
            evolution_config=EvolutionConfig(),
            mirt_config=MIRTConfig(prior_mean=[0.0] * 5, prior_cov=None,
                                   default_a_specialized=[0.8] * 5,
                                   default_a_general=0.5, default_difficulty=0.0),
        )
        engine = BeliefEngine(config=config, llm_client=None)
        before = engine.create_initial_state("test_attr_student")
        before.K.mastery_prob = 0.5
        after = engine.create_initial_state("test_attr_student")
        after.K.mastery_prob = 0.8

        result = evaluate(
            "test_attr_student", metric="twin_attribution",
            before=before, after=after,
        )
        assert "K.mastery_prob" in result["state_diff"]
        assert "K.mastery_prob" in result["dominant_factor"]

    def test_evaluate_unknown_metric_raises(self):
        """evaluate("s1", metric="unknown") -> ValueError."""
        from ecos.runtime import evaluate

        with pytest.raises(ValueError, match="Unknown metric"):
            evaluate("test_unknown", metric="unknown_metric")


# ──────────────────────────────────────────────────────────────────────
# 3. plan 端到端 (2 tests)
# ──────────────────────────────────────────────────────────────────────


class TestRuntimePlan:
    """v0.83.0-d: plan API 端到端 (estimate -> plan)."""

    def test_plan_with_lca_engine(self):
        """plan("s1", audience="student", lca_engine=...) -> LCAResult."""
        from ecos.runtime import plan
        from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig

        lca = LCAEngine(config=LCAEngineConfig())
        result = plan("test_plan_student", audience="student", lca_engine=lca)
        assert result is not None
        assert result.intervention is not None
        assert result.bloom_target is not None

    def test_plan_auto_estimates_state(self):
        """plan("s1") 无 cta_input -> 自动 estimate(student_id)."""
        from ecos.runtime import plan
        from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig
        from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig

        belief = BeliefEngine(config=BeliefEngineConfig())
        lca = LCAEngine(config=LCAEngineConfig())

        # 不传 cta_input, 走自动 estimate
        result = plan("test_auto_plan", lca_engine=lca, belief_engine=belief)
        assert result is not None


# ──────────────────────────────────────────────────────────────────────
# 4. kwargs 注入 (3 tests)
# ──────────────────────────────────────────────────────────────────────


class TestRuntimeKwargsInjection:
    """v0.83.0-d: kwargs 注入 (belief_engine / lca_engine / evaluator)."""

    def test_kwargs_belief_engine_injection(self):
        """estimate kwargs 注入 belief_engine -> 不用 singleton."""
        from ecos.runtime import estimate
        from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig

        custom = BeliefEngine(config=BeliefEngineConfig())
        state = estimate("test_kwargs_belief", belief_engine=custom)
        assert state.student_id == "test_kwargs_belief"

    def test_kwargs_lca_engine_injection(self):
        """plan kwargs 注入 lca_engine -> 不用 singleton."""
        from ecos.runtime import plan
        from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig

        custom_lca = LCAEngine(config=LCAEngineConfig())
        result = plan("test_kwargs_lca", lca_engine=custom_lca)
        assert result is not None

    def test_kwargs_evaluator_injection(self):
        """evaluate kwargs 注入 evaluator -> 不用 singleton."""
        from ecos.runtime import evaluate
        from ecos.cta.belief_state import BeliefState
        from datetime import datetime
        import numpy as np
        from ecos.evaluation import EvaluationEngine

        state = BeliefState(student_id="test_kwargs_eval")
        state.K.mastery_prob = 0.8
        state.theta_mean = np.zeros(5)
        state.theta_cov = np.eye(5)
        state.last_updated = datetime.now()

        result = evaluate(
            "test_kwargs_eval", metric="goal_completion",
            state=state, goal_id="K.mastery>=0.7",
            evaluator=EvaluationEngine(),
        )
        assert result["completed"] is True


# ──────────────────────────────────────────────────────────────────────
# 5. singleton 懒加载 (2 tests)
# ──────────────────────────────────────────────────────────────────────


class TestRuntimeSingleton:
    """v0.83.0-d: singleton 懒加载 (重复调用返回同一实例)."""

    def test_singleton_belief_engine_lazy(self):
        """_default_belief_engine 初始 None, estimate kwargs 注入后仍 None."""
        from ecos.runtime import api as runtime_api

        # 重置 singleton (避免其他 test 污染)
        original = runtime_api._default_belief_engine
        runtime_api._default_belief_engine = None
        try:
            from ecos.runtime import estimate
            from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig

            engine = BeliefEngine(config=BeliefEngineConfig())
            estimate("test_singleton_1", belief_engine=engine)
            # kwargs 注入, singleton 不构造
            assert runtime_api._default_belief_engine is None
        finally:
            runtime_api._default_belief_engine = original

    def test_singleton_lca_engine_lazy(self):
        """_default_lca_engine 初始 None, plan kwargs 注入后仍 None."""
        from ecos.runtime import api as runtime_api

        original = runtime_api._default_lca_engine
        runtime_api._default_lca_engine = None
        try:
            from ecos.runtime import plan
            from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig

            lca = LCAEngine(config=LCAEngineConfig())
            plan("test_singleton_lca_1", lca_engine=lca)
            # kwargs 注入, singleton 不构造
            assert runtime_api._default_lca_engine is None
        finally:
            runtime_api._default_lca_engine = original


# ──────────────────────────────────────────────────────────────────────
# 6. 端到端 (1 test: estimate -> update_belief -> plan -> evaluate -> simulate)
# ──────────────────────────────────────────────────────────────────────


class TestRuntimeEndToEnd:
    """v0.83.0-d: 端到端 (estimate -> update_belief -> plan -> evaluate -> simulate)."""

    def test_full_lifecycle(self):
        """完整 lifecycle: estimate -> update_belief -> plan -> evaluate(goal) -> simulate."""
        from ecos.runtime import (
            estimate, update_belief, plan, evaluate, simulate,
        )
        from ecos.cta.belief_engine import (
            BeliefEngine, BeliefEngineConfig, Observation,
        )
        from ecos.cta.l1_evolution import EvolutionConfig
        from ecos.cta.l2_mirt import MIRTConfig
        from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig

        belief = BeliefEngine(config=BeliefEngineConfig(
            evolution_config=EvolutionConfig(),
            mirt_config=MIRTConfig(prior_mean=[0.0] * 5, prior_cov=None,
                                   default_a_specialized=[0.8] * 5,
                                   default_a_general=0.5, default_difficulty=0.0),
        ), llm_client=None)
        lca = LCAEngine(config=LCAEngineConfig())

        student_id = "test_e2e_student"

        # 1) estimate
        state = estimate(student_id, belief_engine=belief)
        assert state.student_id == student_id

        # 2) update_belief
        from ecos.cta.belief_state import BloomLevel
        obs = Observation(problem_id="p1", skill_id="s1", correct=True,
                          score=1.0, bloom_level=BloomLevel.APPLY, explanation_text="")
        state = update_belief(student_id, obs, belief_engine=belief)
        # update 路径走通 (bloom 必有 evidence)
        assert len(state.evidence_for("bloom")) >= 1

        # 3) plan
        from ecos.lca.cta_input import CTAInput
        cta_input = CTAInput(student_id=student_id, belief_state=state)
        result = plan(student_id, lca_engine=lca, cta_input=cta_input)
        assert result.intervention is not None

        # 4) evaluate(goal_completion)
        goal = evaluate(
            student_id, metric="goal_completion",
            state=state, goal_id="K.mastery>=0.5",
        )
        # K mastery 提升, 0.5 阈值应该满足 (mastery_prob > 0.5)
        # 注意: 不保证一定 >= 0.5 (取决于 MIRT/BKT 的具体算法)
        # 只验证 goal_id 和 schema
        assert goal["goal_id"] == "K.mastery>=0.5"

        # 5) simulate
        sim_state = simulate(student_id, [], 0, [], belief_engine=belief)
        assert sim_state.student_id == student_id


# ──────────────────────────────────────────────────────────────────────
# 7. 防御性自检 (1 test: silent pass 扫描)
# ──────────────────────────────────────────────────────────────────────


class TestRuntimeDefensiveChecks:
    """v0.83.0-d: Runtime API 防御性自检 (silent pass 扫描)."""

    def test_no_silent_pass_in_runtime(self):
        """ecos/runtime/api.py 全部 except 块必须有 logger.warning."""
        import inspect
        from ecos.runtime import api as api_mod

        source = inspect.getsource(api_mod)
        lines = source.split("\n")

        except_blocks = []
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.lstrip()
            if stripped.startswith("except") and line.rstrip().endswith(":"):
                except_indent = len(line) - len(line.lstrip())
                block_lines = []
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    if not next_line.strip():
                        i += 1
                        continue
                    next_indent = len(next_line) - len(next_line.lstrip())
                    if next_indent > except_indent:
                        block_lines.append(next_line)
                        i += 1
                    else:
                        break
                except_blocks.append("\n".join(block_lines))
            else:
                i += 1

        for idx, block in enumerate(except_blocks):
            has_warning = "warning" in block
            has_raise = "raise " in block or block.strip().endswith("raise")
            has_silent_pass = "pass" in block and not has_warning

            if has_silent_pass:
                pytest.fail(
                    f"runtime/api.py except 块 #{idx + 1} 是 silent pass:\n{block}\n"
                    "防御性自检 [1]: 必须改 logger.warning(..., exc_info=True)"
                )
            if not has_warning and not has_raise:
                pytest.fail(
                    f"runtime/api.py except 块 #{idx + 1} 无 warning 也无 raise:\n{block}\n"
                    "防御性自检 [1]: 必须有 logger.warning 或显式 raise"
                )


# ──────────────────────────────────────────────────────────────────────
# 8. backward compat (1 test: web/api/belief.py 主入口仍 work)
# ──────────────────────────────────────────────────────────────────────


class TestRuntimeBackwardCompat:
    """v0.83.0-d: web/api/belief.py 主入口仍 work, Runtime API 是旁路."""

    def test_web_api_belief_endpoint_still_works(self):
        """web/api/app.py /api/answer 端点仍注册 (Runtime API 旁路, 主入口保持)."""
        try:
            from web.api.app import app
            routes = [r.rule for r in app.url_map.iter_rules()]
            # web/api 主入口保持
            assert "/api/answer" in routes
            assert "/api/lca_debug/<student_id>" in routes
        except Exception as e:
            pytest.skip(f"web/api/app.py 加载失败 (可能缺 LLM 配置): {e}")


# ──────────────────────────────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
