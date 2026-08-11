"""Runtime API 6 核心 API —— v0.83 Kernel API 层.

对应 kernel-mapping §5 Runtime API:
  - estimate(student_id)                       -> BeliefState
  - update_belief(student_id, evidence)         -> BeliefState
  - replay(student_id, events)                  -> BeliefState
  - evaluate(student_id, metric, **kwargs)      -> Dict
  - simulate(student_id, events, fork_at_idx, alternative_events) -> BeliefState
  - plan(student_id, audience="student", **kwargs) -> LCAResult

风格: 纯函数 + kwargs (跟 StateEngine.replay/simulate 现有 v0.81 模式一致).
每个 API 接受 student_id (必) + kwargs (可选参数, 如 timestamp/policy_id/audience).
不持 state, 可独立调用, 适合多线程 + 微服务.

设计:
  - 模块级 singleton 默认 instance (懒加载, 首次调用时构造)
  - 每个函数接受 kwargs 注入 (e.g. belief_engine / lca_engine / evaluator)
  - 默认 singleton 走 web/api/belief.py 的 default db / engine 路径
  - Runtime API 是旁路, web/api/belief.py 仍是主入口 (向后兼容)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 模块级 singleton 默认 instance (懒加载)
# ---------------------------------------------------------------------------

_default_belief_engine: Optional[Any] = None
_default_lca_engine: Optional[Any] = None
_default_evaluator: Optional[Any] = None
_default_event_log: Optional[Any] = None


def _get_default_belief_engine():
    """懒加载默认 BeliefEngine (首次调用时构造)."""
    global _default_belief_engine
    if _default_belief_engine is None:
        try:
            from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig
            _default_belief_engine = BeliefEngine(config=BeliefEngineConfig())
        except Exception:
            _log.warning("Runtime API: 默认 BeliefEngine 构造失败, 需 kwargs 注入", exc_info=True)
            raise
    return _default_belief_engine


def _get_default_lca_engine():
    """懒加载默认 LCAEngine (首次调用时构造)."""
    global _default_lca_engine
    if _default_lca_engine is None:
        try:
            from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig
            _default_lca_engine = LCAEngine(config=LCAEngineConfig())
        except Exception:
            _log.warning("Runtime API: 默认 LCAEngine 构造失败, 需 kwargs 注入", exc_info=True)
            raise
    return _default_lca_engine


def _get_default_evaluator():
    """懒加载默认 EvaluationEngine (首次调用时构造)."""
    global _default_evaluator
    if _default_evaluator is None:
        try:
            from ecos.evaluation import EvaluationEngine, EvaluationConfig
            _default_evaluator = EvaluationEngine(config=EvaluationConfig())
        except Exception:
            _log.warning("Runtime API: 默认 EvaluationEngine 构造失败, 需 kwargs 注入", exc_info=True)
            raise
    return _default_evaluator


# ---------------------------------------------------------------------------
# 6 核心 API
# ---------------------------------------------------------------------------

def estimate(student_id: str, **kwargs) -> Any:
    """创建/恢复学生信念状态 (Runtime API 6.1).

    Args:
        student_id: 学生 ID
        **kwargs:
            belief_engine: Optional[BeliefEngine]  (默认 singleton)

    Returns:
        BeliefState (新建或 DB 恢复)
    """
    engine = kwargs.get("belief_engine") or _get_default_belief_engine()
    return engine.create_initial_state(student_id)


def update_belief(student_id: str, evidence: Any, **kwargs) -> Any:
    """写入新观测, 更新信念 (Runtime API 6.2).

    Args:
        student_id: 学生 ID
        evidence:   Observation (或 dict 含 skill_id/problem_id/correct/score)
        **kwargs:
            belief_engine: Optional[BeliefEngine]
            state:         Optional[BeliefState] (v0.84.0-d 新增, 复用已有 state)
                          不传时调用 estimate() 创建新 state (老行为, 向后兼容)
            lca_result:    Optional[LCAResult]  (v0.82 LCA 4-layer 输出)
            log_event:     bool = True

    Returns:
        BeliefState (更新后, 跟传入 state 是同一对象 if state kwarg 传入)
    """
    engine = kwargs.get("belief_engine") or _get_default_belief_engine()
    # v0.84.0-d: state kwarg 复用已有 state (Plugin SDK 路径), 否则 estimate 创建新
    state = kwargs.get("state") or estimate(student_id, belief_engine=engine)
    return engine.update(
        state,
        evidence,
        lca_result=kwargs.get("lca_result"),
        log_event=kwargs.get("log_event", True),
    )


def replay(student_id: str, events: List[Any], **kwargs) -> Any:
    """重放历史事件重建状态 (Runtime API 6.3).

    Args:
        student_id: 学生 ID
        events:     List[LearningEvent] (从 event_log.query_by_student 获取)
        **kwargs:
            belief_engine: Optional[BeliefEngine]

    Returns:
        BeliefState (重放后)
    """
    engine = kwargs.get("belief_engine") or _get_default_belief_engine()
    return engine.replay(events, student_id)


def evaluate(student_id: str, metric: str = "ece", **kwargs) -> Dict[str, Any]:
    """计算校准度指标 (Runtime API 6.4).

    Args:
        student_id: 学生 ID
        metric:     评估指标
                    "twin_attribution" / "policy_ab" / "goal_completion" / "ece"
        **kwargs:
            evaluator:      Optional[EvaluationEngine]
            # metric-specific kwargs:
            #   ece: dimension="K" (暂未实现, 走 external script)
            #   twin_attribution: before=state, after=state, since=...
            #   policy_ab: policy_a=..., policy_b=...
            #   goal_completion: state=..., goal_id=...

    Returns:
        Dict (含评估结果, 不同 metric 不同 schema)
    """
    evaluator = kwargs.get("evaluator") or _get_default_evaluator()

    if metric == "twin_attribution":
        before = kwargs.get("before")
        after = kwargs.get("after")
        since = kwargs.get("since")
        if before is None or after is None:
            raise ValueError(
                "evaluate(metric='twin_attribution') 需要 kwargs before=... 和 after=..."
            )
        result = evaluator.attribute_state_change(student_id, before, after, since)
        return result.to_dict()

    elif metric == "policy_ab":
        policy_a = kwargs.get("policy_a", "linucb")
        policy_b = kwargs.get("policy_b", "linucb_baseline")
        events = kwargs.get("events")
        result = evaluator.compare_policies(student_id, policy_a, policy_b, events)
        return result.to_dict()

    elif metric == "goal_completion":
        state = kwargs.get("state")
        goal_id = kwargs.get("goal_id")
        goal = kwargs.get("goal")  # v0.86.0-d: Goal 对象 (优先)
        if state is None:
            raise ValueError(
                "evaluate(metric='goal_completion') 需要 kwargs state=..."
            )
        if goal is None and goal_id is None:
            raise ValueError(
                "evaluate(metric='goal_completion') 需要 kwargs goal=... 或 goal_id=..."
            )
        # v0.86.0-d: goal 优先 (Union[str, Goal] dispatch)
        result = evaluator.check_goal_completion(state, goal or goal_id)
        return result.to_dict()

    elif metric == "ece":
        # v0.83.0-d: ece 暂未实现 (compute_h3_ece.py 外部脚本, 留 v0.83.x)
        _log.debug("Runtime API evaluate(metric='ece') 暂未实现, 返占位")
        return {"metric": "ece", "student_id": student_id, "value": None,
                "note": "compute_h3_ece.py 外部脚本, v0.83.x 接入"}

    else:
        raise ValueError(f"Unknown metric: {metric!r}")


def simulate(
    student_id: str,
    events: List[Any],
    fork_at_idx: int,
    alternative_events: List[Any],
    **kwargs,
) -> Any:
    """反事实模拟 (Runtime API 6.5).

    Args:
        student_id:         学生 ID
        events:             List[LearningEvent] (历史事件)
        fork_at_idx:        分叉索引 (events[:fork_at_idx] 是历史, 之后是 alternative)
        alternative_events: List[LearningEvent] (替代未来)
        **kwargs:
            belief_engine: Optional[BeliefEngine]

    Returns:
        BeliefState (反事实模拟后)
    """
    engine = kwargs.get("belief_engine") or _get_default_belief_engine()
    return engine.simulate(events, student_id, fork_at_idx, alternative_events)


def plan(student_id: str, audience: str = "student", **kwargs) -> Any:
    """生成干预计划 (Runtime API 6.6).

    Args:
        student_id: 学生 ID
        audience:   rationale 受众 ("student" / "teacher" / "parent")
        **kwargs:
            lca_engine: Optional[LCAEngine]
            cta_input:  Optional[CTAInput]  (默认自动 estimate(student_id))
            # v0.86.0-b: Twin Consistency Check
            goal:       Optional[Goal]      (若传, 校验该 Goal 关联 evidence)
            event_log:  Optional[EventLog]   (inconsistent 时 emit goal_changed event)

    Returns:
        LCAResult (含 Intervention + rationale + expected_gain/risk)

    v0.86.0-b: 选 intervention 前 run Twin Consistency Check, 若 inconsistent
        → emit goal_changed event + log warning + 继续 lca.select_intervention
        (不阻断 plan, 走 fallback 策略, per Bisen 决策 2026-08-11)
    v0.86.0-d: 委托 plan_goal_aware (新 API, 跟 plan 并行)
    """
    return plan_goal_aware(student_id, audience=audience, **kwargs)


def plan_goal_aware(student_id: str, audience: str = "student", **kwargs) -> Any:
    """v0.86.0-d: Goal-aware plan (新 API, 跟 plan 并行).

    跟 plan 的区别:
        - 显式接受 goal 参数 (optional)
        - 走 Twin Consistency Check (per goal)
        - 不阻断 plan (失败走 fallback)
        - 后续 v0.86.0-d 后续 commit 可以扩展: Thompson update with Goal.Metric reward

    Args:
        student_id: 学生 ID
        audience:   rationale 受众
        **kwargs:
            lca_engine: Optional[LCAEngine]
            cta_input:  Optional[CTAInput]
            goal:       Optional[Goal]      (若传, 校验该 Goal 关联 evidence)
            event_log:  Optional[EventLog]   (inconsistent 时 emit goal_changed event)

    Returns:
        LCAResult (跟 plan 同一返回)
    """
    lca = kwargs.get("lca_engine") or _get_default_lca_engine()
    cta_input = kwargs.get("cta_input")
    if cta_input is None:
        # 默认: 估计 student state, 构造 CTAInput
        state = estimate(student_id)
        from ecos.lca.cta_input import CTAInput
        cta_input = CTAInput(student_id=student_id, belief_state=state)

    # v0.86.0-b: Twin Consistency Check (前置 defensive)
    _run_twin_consistency_check(
        student_id=student_id,
        state=cta_input.belief_state,
        goal=kwargs.get("goal"),
        event_log=kwargs.get("event_log"),
    )

    return lca.select_intervention(cta_input, audience=audience)


def plan_motivation_aware(student_id: str, audience: str = "student", **kwargs) -> Any:
    """v0.87.0-b: Motivation-aware plan (新 API, 跟 plan / plan_goal_aware 并行).

    跟 plan_goal_aware 的区别:
        - 接受 motivation_observation (MotivationObservation) 参数
        - 自动 emit observation 到 state.motivation (allowlisted mutation)
        - 透传 motivation 到 LCAEngine.select_intervention
        - 走 Twin Consistency Check (per goal, 如传)

    Args:
        student_id: 学生 ID
        audience:   rationale 受众
        **kwargs:
            lca_engine: Optional[LCAEngine]
            cta_input:  Optional[CTAInput]
            goal:       Optional[Goal]      (若传, 校验该 Goal 关联 evidence)
            event_log:  Optional[EventLog]   (inconsistent 时 emit goal_changed event)
            motivation_observation: Optional[MotivationObservation]  (emit 到 state.motivation)
            motivation: Optional[MotivationProfile]  (直接透传 LCA, 不 emit)

    Returns:
        LCAResult (跟 plan / plan_goal_aware 同一返回)

    v0.87.0-b: motivation 考虑走 2 路径 (LCAEngine.select_intervention 走它ypoverride + reward)
    """
    lca = kwargs.get("lca_engine") or _get_default_lca_engine()
    cta_input = kwargs.get("cta_input")
    if cta_input is None:
        # 默认: 估计 student state, 构造 CTAInput
        state = estimate(student_id)
        from ecos.lca.cta_input import CTAInput
        cta_input = CTAInput(student_id=student_id, belief_state=state)

    # v0.86.0-b: Twin Consistency Check (前置 defensive)
    _run_twin_consistency_check(
        student_id=student_id,
        state=cta_input.belief_state,
        goal=kwargs.get("goal"),
        event_log=kwargs.get("event_log"),
    )

    # v0.87.0-b: motivation observation emit (allowlisted mutation)
    motivation_obs = kwargs.get("motivation_observation")
    if motivation_obs is not None:
        cta_input.belief_state.add_motivation_observation(motivation_obs)

    # v0.87.0-b: motivation 透传到 LCA (None 时 fallback to state.motivation)
    motivation = kwargs.get("motivation")
    return lca.select_intervention(
        cta_input, audience=audience, motivation=motivation,
    )


def plan_domain_aware(student_id: str, audience: str = "student", **kwargs) -> Any:
    """v0.88.0-b: Domain-aware plan (新 API, 跟 plan / plan_goal_aware / plan_motivation_aware 并行).

    跟 plan_motivation_aware 的区别:
        - 接受 domain_name 参数 (e.g. "education"/"science"/"career")
        - 自动 set_domain_extension("active_domain", ...) 到 state (allowlisted mutation)
        - 透传 domain_name 到 LCAEngine.select_intervention
        - 走 Twin Consistency Check (per goal, 如传)

    Args:
        student_id: 学生 ID
        audience:   rationale 受众
        **kwargs:
            lca_engine:  Optional[LCAEngine]
            cta_input:   Optional[CTAInput]
            goal:        Optional[Goal]      (若传, 校验该 Goal 关联 evidence)
            event_log:   Optional[EventLog]   (inconsistent 时 emit goal_changed event)
            domain_name: Optional[str]        (e.g. "education"/"science"/"career", 设入 domain_extension["active_domain"])
            motivation:  Optional[MotivationProfile]  (透传 motivation)

    Returns:
        LCAResult (跟 plan / plan_goal_aware / plan_motivation_aware 同一返回)

    v0.88.0-b: domain 考虑走 2 路径 (LCAEngine.select_intervention 走 itype override + reward factor).
    v0.88.0-b: Runtime.plan_domain_aware 跟 Runtime.plan_motivation_aware 独立, 不重叠
              (domain 选 intervention 类型, motivation 调 reward factor).
    """
    lca = kwargs.get("lca_engine") or _get_default_lca_engine()
    cta_input = kwargs.get("cta_input")
    if cta_input is None:
        # 默认: 估计 student state, 构造 CTAInput
        state = estimate(student_id)
        from ecos.lca.cta_input import CTAInput
        cta_input = CTAInput(student_id=student_id, belief_state=state)

    # v0.86.0-b: Twin Consistency Check (前置 defensive)
    _run_twin_consistency_check(
        student_id=student_id,
        state=cta_input.belief_state,
        goal=kwargs.get("goal"),
        event_log=kwargs.get("event_log"),
    )

    # v0.88.0-b: domain_name emit (allowlisted mutation, set_domain_extension)
    domain_name = kwargs.get("domain_name")
    if domain_name is not None:
        cta_input.belief_state.set_domain_extension("active_domain", domain_name)

    # v0.87.0-b: motivation observation emit (allowlisted mutation)
    motivation_obs = kwargs.get("motivation_observation")
    if motivation_obs is not None:
        cta_input.belief_state.add_motivation_observation(motivation_obs)

    # v0.87.0-b: motivation 透传到 LCA (None 时 fallback to state.motivation)
    motivation = kwargs.get("motivation")
    return lca.select_intervention(
        cta_input, audience=audience, motivation=motivation, domain_name=domain_name,
    )


def _run_twin_consistency_check(
    student_id: str,
    state: Any,
    goal: Any,
    event_log: Any,
) -> None:
    """v0.86.0-b: 内部 helper, run Twin Consistency Check + emit event.

    不阻断 plan (per Bisen 决策), 失败时 log warning + emit goal_changed event.
    Event 失败 _log.warning 不 raise (防御性自检 [1]).
    """
    try:
        from ecos.twin import get_default_checker
        checker = get_default_checker()
        result = checker.check(state, goal=goal)
        if not result.consistent:
            _log.warning(
                "Runtime.plan: Twin inconsistent (sid=%s, violations=%d, recommendation=%s)",
                student_id, len(result.violations), result.recommendation,
            )
            # Emit goal_changed event if event_log available
            if event_log is not None:
                try:
                    from ecos.cta.event_log import LearningEvent
                    event = LearningEvent.from_goal_changed(
                        student_id=student_id,
                        old_goal_id="",
                        new_goal_id="",
                        source="twin_consistency_check",
                    )
                    event_log.log_event(event)
                except Exception:
                    _log.warning(
                        "Runtime.plan: emit goal_changed event failed (sid=%s)",
                        student_id, exc_info=True,
                    )
    except Exception:
        # 防御性: check 本身失败不阻断 plan
        _log.warning(
            "Runtime.plan: Twin Consistency Check failed (sid=%s), 继续 plan",
            student_id, exc_info=True,
        )


__all__ = [
    "estimate",
    "update_belief",
    "replay",
    "evaluate",
    "simulate",
    "plan",
    "plan_goal_aware",
    "plan_motivation_aware",
    "plan_domain_aware",
]
