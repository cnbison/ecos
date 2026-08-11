"""v0.86.0-a: Goal Ontology 测试套件.

对应 12-kernel-mapping §2.3 Goal Ontology.
Capability → Objective → Metric → Evidence.

测试覆盖:
- Goal dataclass (4): basic / to_dict_roundtrip / to_goal_id_str / validation
- Capability dataclass (2): creation / frozen
- GoalOntology registry (5): register / get / query_by_domain / from_capability / reset
- BeliefState 集成 (4): default empty / to_dict / from_dict / append_goal
- GoalCompletion.check_goal (3): K / Bloom / TC + check Union 兼容

向后兼容:
- GoalCompletion.check 仍接受 str goal_id (v0.83.0-c)
- BeliefState 老 JSON snapshot 加载 current_goals 兜底 []
"""

from __future__ import annotations

import numpy as np
import pytest

from ecos.cta.belief_state import BeliefState, TCState
from ecos.evaluation.goal_completion import GoalCompletion, GoalStatus
from ecos.goal import (
    Capability,
    Goal,
    GoalOntology,
    get_default_ontology,
    reset_default_ontology,
)


# ────────────────────────────────────────────────────────────────────
# Goal dataclass (4 tests)
# ────────────────────────────────────────────────────────────────────


def test_goal_basic_creation():
    """Goal dataclass 默认值 + 显式构造."""
    goal = Goal(
        goal_id="goal.python_variables.L3",
        capability="python_variables",
        objective="apply_variable_concepts",
    )
    assert goal.goal_id == "goal.python_variables.L3"
    assert goal.capability == "python_variables"
    assert goal.objective == "apply_variable_concepts"
    assert goal.bloom_level == 3
    assert goal.metric_dimension == "K"
    assert goal.metric_threshold == 0.7
    assert goal.evidence_ids == []
    assert goal.status == "active"


def test_goal_to_dict_from_dict_roundtrip():
    """Goal.to_dict() + Goal.from_dict() round-trip 一致."""
    goal = Goal(
        goal_id="g1",
        capability="loops",
        objective="use_for_loop",
        bloom_level=4,
        metric_dimension="Bloom",
        metric_threshold=0.6,
        evidence_ids=[101, 102],
        status="active",
    )
    data = goal.to_dict()
    restored = Goal.from_dict(data)
    assert restored.goal_id == goal.goal_id
    assert restored.capability == goal.capability
    assert restored.objective == goal.objective
    assert restored.bloom_level == goal.bloom_level
    assert restored.metric_dimension == goal.metric_dimension
    assert restored.metric_threshold == goal.metric_threshold
    assert restored.evidence_ids == goal.evidence_ids
    assert restored.status == goal.status


def test_goal_to_goal_id_str_3_dimensions():
    """Goal.to_goal_id_str() 输出 3 类 GoalCompletion 兼容字符串."""
    g_k = Goal("g_k", "python_vars", "apply", metric_dimension="K", metric_threshold=0.7)
    assert g_k.to_goal_id_str() == "K.mastery>=0.7"

    g_b = Goal("g_b", "loops", "analyze", bloom_level=3, metric_dimension="Bloom", metric_threshold=0.6)
    assert g_b.to_goal_id_str() == "Bloom.L3>=0.6"

    g_tc = Goal("g_tc", "python_variables", "pass", metric_dimension="TC", metric_threshold=1.0)
    assert g_tc.to_goal_id_str() == "TC.python_variables.pass"


def test_goal_post_init_validation_warnings():
    """__post_init__: 非法 metric_dimension / bloom_level 触发 warning 但不 raise."""
    goal = Goal(
        goal_id="g_invalid",
        capability="x",
        objective="y",
        metric_dimension="UNKNOWN",
        bloom_level=99,
    )
    # 非法值不 raise, dataclass 仍创建
    assert goal.metric_dimension == "UNKNOWN"
    assert goal.bloom_level == 99


# ────────────────────────────────────────────────────────────────────
# Capability dataclass (2 tests)
# ────────────────────────────────────────────────────────────────────


def test_capability_creation_and_to_dict():
    """Capability dataclass + to_dict."""
    cap = Capability(name="python_variables", description="Python 变量赋值", domain="python")
    assert cap.name == "python_variables"
    assert cap.description == "Python 变量赋值"
    assert cap.domain == "python"
    data = cap.to_dict()
    assert data["name"] == "python_variables"
    assert data["description"] == "Python 变量赋值"
    assert data["domain"] == "python"


def test_capability_is_frozen():
    """Capability 是 frozen dataclass, 直接属性赋值应 raise."""
    cap = Capability(name="x", description="y")
    with pytest.raises(Exception):  # FrozenInstanceError
        cap.name = "z"


# ────────────────────────────────────────────────────────────────────
# GoalOntology registry (5 tests)
# ────────────────────────────────────────────────────────────────────


def test_ontology_register_and_get_capability():
    """register_capability + get_capability."""
    onto = GoalOntology()
    cap = Capability(name="python_variables", description="Python 变量")
    onto.register_capability(cap)
    assert onto.get_capability("python_variables") == cap
    assert onto.has_capability("python_variables") is True
    assert onto.get_capability("nonexistent") is None


def test_ontology_query_by_domain():
    """query_capabilities_by_domain 按 domain 过滤."""
    onto = GoalOntology()
    onto.register_capability(Capability("vars", "Python 变量", "python"))
    onto.register_capability(Capability("loops", "Python 循环", "python"))
    onto.register_capability(Capability("fractions", "数学分数", "math"))

    py_caps = onto.query_capabilities_by_domain("python")
    assert len(py_caps) == 2
    assert {c.name for c in py_caps} == {"vars", "loops"}

    math_caps = onto.query_capabilities_by_domain("math")
    assert len(math_caps) == 1
    assert math_caps[0].name == "fractions"


def test_ontology_from_capability_factory():
    """from_capability 构造 Goal, 默认 objective / goal_id 自动生成."""
    onto = GoalOntology()
    onto.register_capability(Capability("python_variables", "Python 变量"))
    goal = onto.from_capability("python_variables", metric_dimension="K", metric_threshold=0.7)
    assert goal.goal_id == "goal.python_variables.L3"
    assert goal.capability == "python_variables"
    assert goal.objective == "achieve_python_variables"
    assert goal.bloom_level == 3
    assert goal.metric_dimension == "K"
    assert goal.metric_threshold == 0.7


def test_ontology_from_capability_unregistered_raises():
    """未注册 capability 调 from_capability 抛 ValueError."""
    onto = GoalOntology()
    with pytest.raises(ValueError, match="未注册"):
        onto.from_capability("nonexistent_capability")


def test_ontology_reset_clears_registry():
    """reset() 清空所有 Capability."""
    onto = GoalOntology()
    onto.register_capability(Capability("a", "x"))
    onto.register_capability(Capability("b", "y"))
    assert len(onto.list_capabilities()) == 2
    onto.reset()
    assert len(onto.list_capabilities()) == 0
    assert onto.has_capability("a") is False


# ────────────────────────────────────────────────────────────────────
# BeliefState 集成 (4 tests)
# ────────────────────────────────────────────────────────────────────


def test_belief_state_default_current_goals_empty():
    """BeliefState() 默认 current_goals=[] (向后兼容)."""
    state = BeliefState(student_id="lbc_test")
    assert state.current_goals == []
    assert isinstance(state.current_goals, list)


def test_belief_state_to_dict_includes_current_goals():
    """to_dict() 序列化 current_goals (Goal.to_dict())."""
    state = BeliefState(student_id="lbc_test")
    state.append_goal(Goal(
        goal_id="g1", capability="python_variables", objective="apply",
        bloom_level=3, metric_dimension="K", metric_threshold=0.7,
    ))
    data = state.to_dict()
    assert "current_goals" in data
    assert len(data["current_goals"]) == 1
    assert data["current_goals"][0]["goal_id"] == "g1"
    assert data["current_goals"][0]["capability"] == "python_variables"


def test_belief_state_from_dict_restores_current_goals():
    """from_dict() 恢复 current_goals (Goal.from_dict)."""
    original = BeliefState(student_id="lbc_test")
    original.append_goal(Goal(
        goal_id="g1", capability="loops", objective="use_for",
        bloom_level=4, metric_dimension="Bloom", metric_threshold=0.6,
        evidence_ids=[101],
    ))
    data = original.to_dict()
    restored = BeliefState.from_dict(data)
    assert restored.student_id == "lbc_test"
    assert len(restored.current_goals) == 1
    g = restored.current_goals[0]
    assert g.goal_id == "g1"
    assert g.capability == "loops"
    assert g.bloom_level == 4
    assert g.metric_dimension == "Bloom"
    assert g.evidence_ids == [101]


def test_belief_state_append_and_remove_goal():
    """append_goal / remove_goal 操作 current_goals."""
    state = BeliefState(student_id="lbc_test")
    g1 = Goal("g1", "vars", "apply")
    g2 = Goal("g2", "loops", "use")

    state.append_goal(g1)
    state.append_goal(g2)
    assert len(state.current_goals) == 2

    assert state.remove_goal("g1") is True
    assert len(state.current_goals) == 1
    assert state.current_goals[0].goal_id == "g2"

    # 不存在的 goal_id 返 False
    assert state.remove_goal("nonexistent") is False


# ────────────────────────────────────────────────────────────────────
# GoalCompletion.check_goal (3 tests)
# ────────────────────────────────────────────────────────────────────


def test_goal_completion_check_goal_K():
    """GoalCompletion.check_goal(state, Goal) 走 K.mastery 路径."""
    state = BeliefState(student_id="lbc_test")
    state.K.mastery_prob = 0.75
    goal = Goal("g1", "vars", "apply", metric_dimension="K", metric_threshold=0.7)
    gc = GoalCompletion()
    status = gc.check_goal(state, goal)
    assert isinstance(status, GoalStatus)
    assert status.completed is True
    assert status.current_value == 0.75
    assert status.target_value == 0.7


def test_goal_completion_check_goal_Bloom_and_TC():
    """GoalCompletion.check_goal 走 Bloom / TC 路径."""
    state = BeliefState(student_id="lbc_test")
    state.bloom_profile.apply = 0.7
    state.bloom_profile.analyze = 0.7
    state.bloom_profile.evaluate = 0.7
    state.bloom_profile.create = 0.7

    # Bloom L3+ (L3..L6 平均)
    goal_b = Goal("g_b", "loops", "analyze", bloom_level=3, metric_dimension="Bloom", metric_threshold=0.6)
    gc = GoalCompletion()
    status_b = gc.check_goal(state, goal_b)
    assert status_b.completed is True
    assert abs(status_b.current_value - 0.7) < 1e-6

    # TC pass
    state.C.tc_states["python_variables"] = TCState(tc_id="python_variables", status="post_liminal")
    goal_tc = Goal("g_tc", "python_variables", "pass", metric_dimension="TC", metric_threshold=1.0)
    status_tc = gc.check_goal(state, goal_tc)
    assert status_tc.completed is True
    assert status_tc.current_value == 1.0


def test_goal_completion_check_accepts_goal_instance():
    """GoalCompletion.check(state, Goal) Union 路径仍 work (向后兼容)."""
    state = BeliefState(student_id="lbc_test")
    state.K.mastery_prob = 0.5
    goal = Goal("g1", "vars", "apply", metric_dimension="K", metric_threshold=0.7)
    gc = GoalCompletion()
    # check() 接受 Goal 实例 (Union[str, Goal] dispatch)
    status = gc.check(state, goal)
    assert status.completed is False
    assert status.target_value == 0.7
    assert any("K.mastery_prob" in m for m in status.missing_dimensions)
