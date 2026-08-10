"""v0.83.0-c: Evaluation Engine 测试套件.

目标 (按 v0.83.0-c Definition of Done):
  - TwinAttribution: state diff 计算 + 主导因子 + 空 evidence
  - PolicyABTest: 单 policy baseline + 不支持 policy 兜底
  - GoalCompletion: K mastery / Bloom L3+ / TC pass / 多条件 / 未知 goal 兜底
  - EvaluationEngine facade: 3 方法委托
  - 防御性自检 [8] 仍 hard block (0 新 mutation site)
"""

from __future__ import annotations

import sys
from datetime import datetime
from unittest.mock import MagicMock

import pytest


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def belief_states():
    """构造 before/after BeliefState 对 (mastery_prob 不同)."""
    from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig
    from ecos.cta.l1_evolution import EvolutionConfig
    from ecos.cta.l2_mirt import MIRTConfig

    def _build(student_id, k_mastery=0.5, apply_bloom=0.3):
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
        state = BeliefEngine(config=config, llm_client=None).create_initial_state(student_id)
        state.K.mastery_prob = k_mastery
        state.bloom_profile.apply = apply_bloom
        return state

    # K 变化大 (0.5 -> 0.9, +0.4), Bloom 变化小 (0.3 -> 0.4, +0.1)
    # 主导因子应该是 K (|0.4| > |0.1|)
    before = _build("s1", k_mastery=0.5, apply_bloom=0.3)
    after = _build("s1", k_mastery=0.9, apply_bloom=0.4)
    return before, after


# ──────────────────────────────────────────────────────────────────────
# 1. TwinAttribution (4 tests)
# ──────────────────────────────────────────────────────────────────────


class TestTwinAttribution:
    """v0.83.0-c: TwinAttribution state diff + 主导因子 + 空 evidence."""

    def test_attribute_state_change(self, belief_states):
        """attribute 返 TwinAttributionResult 含 state_diff + dominant_factor."""
        from ecos.evaluation import TwinAttribution

        before, after = belief_states
        attributor = TwinAttribution()
        result = attributor.attribute("s1", before, after, since=datetime.now())

        assert result.student_id == "s1"
        # K.mastery_prob: 0.5 -> 0.9 (+0.4)
        assert "K.mastery_prob" in result.state_diff
        diff = result.state_diff["K.mastery_prob"]
        assert abs(diff["old"] - 0.5) < 0.01
        assert abs(diff["new"] - 0.9) < 0.01
        assert abs(diff["delta"] - 0.4) < 0.01
        # 主导因子: K.mastery_prob 变化最大 (|0.4| > |0.1|)
        assert "K.mastery_prob" in result.dominant_factor

    def test_dominant_factor_max_abs_delta(self, belief_states):
        """主导因子 = |delta| 最大的字段."""
        from ecos.evaluation import TwinAttribution

        before, after = belief_states
        # 改 P 大幅变化
        before.P.mastery_prob = 0.2
        after.P.mastery_prob = 0.9
        # 改 K 小幅
        before.K.mastery_prob = 0.5
        after.K.mastery_prob = 0.55

        attributor = TwinAttribution()
        result = attributor.attribute("s1", before, after)

        # 主导因子应该是 P.mastery_prob (delta=0.7 > 0.05)
        assert "P.mastery_prob" in result.dominant_factor

    def test_attribute_no_change_returns_empty(self):
        """before == after -> state_diff={}, dominant_factor="(无变化)"."""
        from ecos.evaluation import TwinAttribution
        from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig
        from ecos.cta.l1_evolution import EvolutionConfig
        from ecos.cta.l2_mirt import MIRTConfig

        config = BeliefEngineConfig(
            evolution_config=EvolutionConfig(),
            mirt_config=MIRTConfig(prior_mean=[0.0] * 5, prior_cov=None,
                                   default_a_specialized=[0.8] * 5,
                                   default_a_general=0.5, default_difficulty=0.0),
        )
        state = BeliefEngine(config=config, llm_client=None).create_initial_state("s1")
        attributor = TwinAttribution()
        result = attributor.attribute("s1", state, state)

        assert result.state_diff == {}
        assert result.dominant_factor == "(无变化)"

    def test_attribute_with_evidence_engine(self, belief_states):
        """evidence_engine 注入 -> evidence_attribution 含 source_dist."""
        from ecos.evaluation import TwinAttribution

        before, after = belief_states
        # 给 after 加 evidence
        after.add_evidence("K", 1)
        after.add_evidence("bloom", 2)

        # 构造 mock evidence_engine
        mock_engine = MagicMock()
        mock_engine.query_by_student.return_value = []  # 空 evidence 列表

        attributor = TwinAttribution(evidence_engine=mock_engine)
        result = attributor.attribute("s1", before, after)

        # evidence_attribution 应该有 K 和 bloom
        dims = [e["dim"] for e in result.evidence_attribution]
        assert "K" in dims
        assert "bloom" in dims


# ──────────────────────────────────────────────────────────────────────
# 2. PolicyABTest (3 tests)
# ──────────────────────────────────────────────────────────────────────


class TestPolicyABTest:
    """v0.83.0-c: PolicyABTest 单 policy baseline + 不支持 policy 兜底."""

    def test_compare_same_policy_returns_no_winner(self):
        """policy_a == policy_b -> 返 winner=None."""
        from ecos.evaluation import PolicyABTest

        ab = PolicyABTest()
        result = ab.compare("s1", "linucb", "linucb")
        assert result.winner is None
        assert result.n_a == 0
        assert result.n_b == 0

    def test_compare_without_lca_engine(self):
        """lca_engine 未注入 -> 返 winner=None + 警告."""
        from ecos.evaluation import PolicyABTest

        ab = PolicyABTest()  # 无 lca_engine
        result = ab.compare("s1", "linucb", "linucb_baseline")
        assert result.winner is None
        assert result.n_a == 0
        assert result.n_b == 0

    def test_compare_unsupported_policy(self):
        """不支持的 policy (a="foo") -> 返 winner=None."""
        from ecos.evaluation import PolicyABTest

        ab = PolicyABTest()
        result = ab.compare("s1", "foo", "linucb")
        assert result.winner is None
        assert result.n_a == 0


# ──────────────────────────────────────────────────────────────────────
# 3. GoalCompletion (4 tests)
# ──────────────────────────────────────────────────────────────────────


class TestGoalCompletion:
    """v0.83.0-c: GoalCompletion K mastery / Bloom L3+ / TC pass / 未知 goal."""

    def test_check_k_mastery_above_threshold(self):
        """K.mastery=0.8, goal="K.mastery>=0.7" -> completed=True."""
        from ecos.evaluation import GoalCompletion
        from ecos.cta.belief_state import BeliefState
        from datetime import datetime
        import numpy as np

        state = BeliefState(student_id="s1")
        state.K.mastery_prob = 0.8
        state.theta_mean = np.zeros(5)
        state.theta_cov = np.eye(5)
        state.last_updated = datetime.now()

        gc = GoalCompletion()
        status = gc.check(state, "K.mastery>=0.7")
        assert status.completed is True
        assert status.current_value == 0.8
        assert status.target_value == 0.7
        assert status.missing_dimensions == []

    def test_check_k_mastery_below_threshold(self):
        """K.mastery=0.5, goal="K.mastery>=0.7" -> completed=False + missing."""
        from ecos.evaluation import GoalCompletion
        from ecos.cta.belief_state import BeliefState
        from datetime import datetime
        import numpy as np

        state = BeliefState(student_id="s1")
        state.K.mastery_prob = 0.5
        state.theta_mean = np.zeros(5)
        state.theta_cov = np.eye(5)
        state.last_updated = datetime.now()

        gc = GoalCompletion()
        status = gc.check(state, "K.mastery>=0.7")
        assert status.completed is False
        assert len(status.missing_dimensions) == 1
        assert "K.mastery_prob" in status.missing_dimensions[0]

    def test_check_bloom_l3_achieved(self):
        """Bloom L3+ (apply/analyze/evaluate/create) 全部 >= 0.6 -> completed=True."""
        from ecos.evaluation import GoalCompletion
        from ecos.cta.belief_state import BeliefState
        from datetime import datetime
        import numpy as np

        state = BeliefState(student_id="s1")
        state.theta_mean = np.zeros(5)
        state.theta_cov = np.eye(5)
        state.last_updated = datetime.now()
        state.bloom_profile.apply = 0.7
        state.bloom_profile.analyze = 0.7
        state.bloom_profile.evaluate = 0.7
        state.bloom_profile.create = 0.7

        gc = GoalCompletion()
        status = gc.check(state, "Bloom.L3>=0.6")
        assert status.completed is True
        assert abs(status.current_value - 0.7) < 0.01

    def test_check_tc_pass(self):
        """TC.python_variables status=post_liminal -> completed=True."""
        from ecos.evaluation import GoalCompletion
        from ecos.cta.belief_state import BeliefState, TCState
        from datetime import datetime
        import numpy as np

        state = BeliefState(student_id="s1")
        state.theta_mean = np.zeros(5)
        state.theta_cov = np.eye(5)
        state.last_updated = datetime.now()
        state.C.tc_states["python_variables"] = TCState(
            tc_id="python_variables", status="post_liminal", progress=1.0, confidence=0.9,
        )

        gc = GoalCompletion()
        status = gc.check(state, "TC.python_variables.pass")
        assert status.completed is True
        assert status.current_value == 1.0

    def test_check_unknown_goal_returns_uncompleted(self):
        """未知 goal_id 格式 -> 返 completed=False + missing."""
        from ecos.evaluation import GoalCompletion
        from ecos.cta.belief_state import BeliefState
        from datetime import datetime
        import numpy as np

        state = BeliefState(student_id="s1")
        state.theta_mean = np.zeros(5)
        state.theta_cov = np.eye(5)
        state.last_updated = datetime.now()

        gc = GoalCompletion()
        status = gc.check(state, "unknown_goal_format")
        assert status.completed is False
        assert "unknown_goal_format" in status.missing_dimensions[0]


# ──────────────────────────────────────────────────────────────────────
# 4. EvaluationEngine facade (3 tests)
# ──────────────────────────────────────────────────────────────────────


class TestEvaluationEngineFacade:
    """v0.83.0-c: EvaluationEngine 3 方法委托."""

    def test_facade_3_methods_delegate(self, belief_states):
        """3 个 facade 方法委托给对应 evaluator."""
        from ecos.evaluation import EvaluationEngine

        before, after = belief_states
        evaluator = EvaluationEngine()

        # 1) attribute_state_change -> TwinAttributionResult
        attr = evaluator.attribute_state_change("s1", before, after)
        assert attr.student_id == "s1"

        # 2) compare_policies -> ABTestResult
        ab = evaluator.compare_policies("s1", "linucb", "linucb_baseline")
        assert ab.student_id == "s1"

        # 3) check_goal_completion -> GoalStatus
        goal = evaluator.check_goal_completion(after, "K.mastery>=0.7")
        assert goal.goal_id == "K.mastery>=0.7"

    def test_facade_disable_evaluator_returns_empty(self, belief_states):
        """config disable TwinAttribution -> attribute_state_change 返空结果."""
        from ecos.evaluation import EvaluationEngine, EvaluationConfig

        before, after = belief_states
        config = EvaluationConfig(enable_twin_attribution=False)
        evaluator = EvaluationEngine(config=config)

        attr = evaluator.attribute_state_change("s1", before, after)
        assert attr.state_diff == {}
        assert "(TwinAttribution disabled)" in attr.dominant_factor

    def test_facade_with_evidence_and_lca_engine(self, belief_states):
        """evidence_engine + lca_engine 注入 -> TwinAttribution evidence + PolicyABTest 走 lca."""
        from ecos.evaluation import EvaluationEngine

        before, after = belief_states
        mock_evidence = MagicMock()
        mock_evidence.query_by_student.return_value = []
        mock_lca = MagicMock()
        mock_lca.intervention_history = {"s1": []}

        evaluator = EvaluationEngine(
            evidence_engine=mock_evidence,
            lca_engine=mock_lca,
        )
        attr = evaluator.attribute_state_change("s1", before, after)
        assert attr.student_id == "s1"
        ab = evaluator.compare_policies("s1", "linucb", "linucb_baseline")
        assert ab.student_id == "s1"


# ──────────────────────────────────────────────────────────────────────
# 5. 防御性自检 (1 test)
# ──────────────────────────────────────────────────────────────────────


class TestEvaluationDefensiveChecks:
    """v0.83.0-c: Evaluation Engine 防御性自检 (silent pass 扫描)."""

    def test_no_silent_pass_in_evaluation(self):
        """evaluation/ 全部 except 块必须有 logger.warning."""
        import inspect
        from ecos.evaluation import (
            twin_attribution as ta_mod,
            policy_ab_test as pa_mod,
            goal_completion as gc_mod,
            evaluation_engine as ee_mod,
        )

        for mod_name, mod in [
            ("twin_attribution", ta_mod),
            ("policy_ab_test", pa_mod),
            ("goal_completion", gc_mod),
            ("evaluation_engine", ee_mod),
        ]:
            source = inspect.getsource(mod)
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
                        f"{mod_name}.py except 块 #{idx + 1} 是 silent pass:\n{block}\n"
                        "防御性自检 [1]: 必须改 logger.warning(..., exc_info=True)"
                    )
                if not has_warning and not has_raise:
                    pytest.fail(
                        f"{mod_name}.py except 块 #{idx + 1} 无 warning 也无 raise:\n{block}\n"
                        "防御性自检 [1]: 必须有 logger.warning 或显式 raise"
                    )


# ──────────────────────────────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
