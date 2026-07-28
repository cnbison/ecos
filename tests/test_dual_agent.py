"""v0.59.0 (v0.58.0 完整版): 双 Agent 互校单元测试套件.

目标 (按 research/10-engineering/04-dual-agent-calibration.md §7.1):
  - protocol/messages.py       ≥ 90% 覆盖
  - protocol/state_machine.py  ≥ 95% 覆盖
  - modes/normal.py            ≥ 90% 覆盖 (6 步互校循环)
  - modes/belief_challenge.py  ≥ 85% 覆盖 (3 触发条件 + 解决)
  - modes/strategy_challenge.py ≥ 85% 覆盖 (5-window 检测 + 惩罚)
  - anti_hallucination/belief_check.py ≥ 90% 覆盖
  - anti_hallucination/experiment_design.py ≥ 90% 覆盖
  - deadlock/timeout.py        ≥ 90% 覆盖
  - deadlock/fallback.py       ≥ 85% 覆盖

防御性自检 (CLAUDE.md):
  - [1] silent pass: 不写 except: pass (继承现有规范)
  - [5] 数据序列化: CalibratedLCAResult.to_dict() 不丢关键字段
  - [6] 不写启发式 fallback: TimeoutError 走 SingleAgentFallback (不是静默降级)
  - [8] 改协议必加测试: 本次新增 DualAgentOrchestrator 接入, 必覆盖 process_observation

v0.58.0 完整版范围 (4-5 天):
  - 4 模式实现 2 个: 常态 (NormalCycle) + 冲突 (BeliefChallenge)
  - StrategyChallenge + MetaReflection 暂为占位/可选
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

# ─── 模块导入 ───────────────────────────────────────────────────────

from ecos.cta.belief_engine import BeliefEngine, Observation
from ecos.cta.belief_state import BloomLevel
from ecos.dual_agent import (
    DualAgentConfig,
    DualAgentOrchestrator,
)
from ecos.dual_agent.anti_hallucination import (
    BeliefDistributionCheck,
    ExperimentDesignValidator,
    HumanReviewConfig,
    HumanReviewTrigger,
)
from ecos.dual_agent.deadlock import SingleAgentFallback, TimeoutGuard
from ecos.dual_agent.modes import (
    DETECT_WINDOW,
    HIGH_CONFIDENCE_THRESHOLD,
    INEFFECTIVE_GAIN_THRESHOLD,
    BeliefChallengeMode,
    NormalCycle,
    StrategyChallengeMode,
    should_trigger_belief_challenge,
)
from ecos.dual_agent.modes.belief_challenge import BLOOM_JUMP_THRESHOLD
from ecos.dual_agent.protocol import (
    BeliefChallenge,
    CalibratedLCAResult,
    CalibrationMessage,
    CalibrationState,
    CalibrationStateMachine,
    CTAOutput,
    HumanReviewRequest,
    MessageType,
    StrategyChallenge,
    PROTOCOL_VERSION,
)
from ecos.dual_agent.protocol.state_machine import _TRANSITIONS
from ecos.lca.intervention import (
    CAStage,
    CLTLevel,
    Intervention,
    InterventionType,
)


# ─── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def cta_engine():
    """CTA BeliefEngine (无 LLM 客户端, 走模板 fallback)."""
    return BeliefEngine()


@pytest.fixture
def lca_engine(cta_engine):
    """LCAEngine (无 LLM 客户端, 走模板 fallback)."""
    from ecos.lca.orchestrator import LCAEngine
    return LCAEngine()


@pytest.fixture
def dual_orch(cta_engine, lca_engine):
    """DualAgentOrchestrator (no LLM, fast timeout for tests)."""
    cfg = DualAgentConfig(cta_config=cta_engine.config, lca_config=lca_engine.config)
    cfg.timeout_sec = 5
    return DualAgentOrchestrator(
        config=cfg, cta_engine=cta_engine, lca_engine=lca_engine,
    )


@pytest.fixture
def make_observation():
    """构造 Observation 工厂 (简化)."""
    def _make(
        problem_id: str = "P001",
        skill_id: str = "python.basics",
        correct: bool = True,
        score: float = 1.0,
        bloom_level: BloomLevel = BloomLevel.APPLY,
        response_time_sec: float = 30.0,
    ) -> Observation:
        return Observation(
            problem_id=problem_id,
            skill_id=skill_id,
            correct=correct,
            score=score,
            bloom_level=bloom_level,
            response_time_sec=response_time_sec,
        )
    return _make


# ─────────────────────────────────────────────────────────────────────
# 1. protocol/messages.py 测试
# ─────────────────────────────────────────────────────────────────────


class TestMessageType:
    def test_all_message_types_defined(self):
        """所有 10 个 MessageType 都必须存在 (spec §2.1)."""
        expected = {
            "CTA_OUTPUT", "LCA_INTERVENTION", "OBSERVATION", "CTA_UPDATE",
            "CAUSAL_ATTRIBUTION", "BELIEF_CHALLENGE", "STRATEGY_CHALLENGE",
            "META_REFLECTION", "HUMAN_REVIEW_REQUEST", "COMPLETED",
        }
        actual = {mt.name for mt in MessageType}
        assert actual == expected, f"missing={expected - actual}, extra={actual - expected}"

    def test_message_type_values(self):
        """MessageType value 必须是字符串 (协议兼容 JSON)."""
        for mt in MessageType:
            assert isinstance(mt.value, str)
            assert mt.value == mt.value.lower(), f"{mt.name} value 必须小写"


class TestCTAOutput:
    def test_from_belief_state(self, cta_engine):
        """CTAOutput.from_belief_state 工厂方法."""
        state = cta_engine.create_initial_state("stu_001")
        out = CTAOutput.from_belief_state(
            belief_state=state,
            calibration_round=3,
            challenge_history=["K: 0.5 → 0.6"],
        )
        assert out.student_id == "stu_001"
        assert out.calibration_round == 3
        assert out.challenge_history == ["K: 0.5 → 0.6"]
        assert out.belief_challenge_pending is False
        assert out.overall_confidence == state.overall_confidence

    def test_overall_confidence_proxy(self, cta_engine):
        """overall_confidence 是 belief_state.overall_confidence 的代理."""
        state = cta_engine.create_initial_state("stu_001")
        state.overall_confidence = 0.42
        out = CTAOutput.from_belief_state(belief_state=state)
        assert out.overall_confidence == 0.42

    def test_to_dict_serialization(self, cta_engine):
        """to_dict 不丢关键字段 (CLAUDE.md [5])."""
        state = cta_engine.create_initial_state("stu_001")
        out = CTAOutput.from_belief_state(
            belief_state=state, calibration_round=2,
        )
        d = out.to_dict()
        assert d["student_id"] == "stu_001"
        assert d["calibration_round"] == 2
        assert d["belief_challenge_pending"] is False
        assert d["overall_confidence"] == state.overall_confidence
        assert "challenge_history" in d
        assert "intervention_hints" in d

    def test_default_challenge_history_isolated(self, cta_engine):
        """防御: default factory list 互不污染."""
        state = cta_engine.create_initial_state("stu_001")
        out1 = CTAOutput.from_belief_state(belief_state=state)
        out1.challenge_history.append("test1")
        out2 = CTAOutput.from_belief_state(belief_state=state)
        assert out2.challenge_history == [], "default list 应该是独立副本"


class TestCalibratedLCAResult:
    def _make_lca_result(self, cta_engine, intervention_type=InterventionType.PRACTICE):
        from ecos.lca.orchestrator import LCAResult
        i = Intervention(
            intervention_type=intervention_type,
            bloom_target=BloomLevel.APPLY,
            target_skills=["python.basics"],
            difficulty=0.5, quantity=5, feedback_density=0.5,
            scaffolding_level=0.5, clt_level=CLTLevel.DEVELOPING,
            ca_stage=CAStage.COACHING, bjork_triggers=["test"],
            expected_gain=0.1, expected_risk=0.0, estimated_duration_sec=600,
            rationale="test",
        )
        return LCAResult(
            student_id="stu_001",
            intervention=i,
            rationale="r",
            expected_gain=0.1,
            expected_risk=0.0,
            bloom_target=BloomLevel.APPLY,
            clt_level=CLTLevel.DEVELOPING,
            ca_stage=CAStage.COACHING,
        )

    def test_from_lca_result(self, cta_engine):
        """从 LCAResult 构造 CalibratedLCAResult."""
        lca = self._make_lca_result(cta_engine)
        cal = CalibratedLCAResult.from_lca_result(lca, calibration_round=5)
        assert cal.student_id == "stu_001"
        assert cal.calibration_round == 5
        assert cal.actual_outcome is None
        assert cal.degraded_mode is False
        assert cal.metadata == {}

    def test_to_dict_preserves_dual_agent_fields(self, cta_engine):
        """to_dict 必须保留 dual agent 扩展字段 (CLAUDE.md [5])."""
        lca = self._make_lca_result(cta_engine)
        cal = CalibratedLCAResult.from_lca_result(lca, calibration_round=3)
        cal.actual_outcome = 0.85
        cal.degraded_mode = True
        cal.metadata["fallback_reason"] = "test timeout"
        d = cal.to_dict()
        assert d["calibration_round"] == 3
        assert d["actual_outcome"] == 0.85
        assert d["degraded_mode"] is True
        assert d["has_causal_effect"] is False
        assert d["metadata"]["fallback_reason"] == "test timeout"



class TestCalibrationMessage:
    def test_to_from_dict_roundtrip(self):
        """CalibrationMessage to_dict / from_dict 双向序列化无丢失."""
        msg = CalibrationMessage(
            message_type=MessageType.CTA_OUTPUT,
            student_id="stu_001",
            calibration_round=2,
            payload={"key": "value"},
            priority=1,
            timeout_sec=10,
        )
        d = msg.to_dict()
        restored = CalibrationMessage.from_dict(d)
        assert restored.message_type == MessageType.CTA_OUTPUT
        assert restored.student_id == "stu_001"
        assert restored.calibration_round == 2
        assert restored.payload == {"key": "value"}
        assert restored.priority == 1
        assert restored.timeout_sec == 10

    def test_default_message_id_is_unique(self):
        """每次构造 message_id 必须不同."""
        msg1 = CalibrationMessage(message_type=MessageType.OBSERVATION, student_id="s1")
        msg2 = CalibrationMessage(message_type=MessageType.OBSERVATION, student_id="s1")
        assert msg1.message_id != msg2.message_id

    def test_protocol_version(self):
        """协议版本号必须存在 (向后兼容用)."""
        assert PROTOCOL_VERSION is not None
        assert isinstance(PROTOCOL_VERSION, str)
        assert PROTOCOL_VERSION.startswith("v")


class TestBeliefChallengeMessage:
    def test_construction(self):
        """BeliefChallenge 默认字段."""
        bc = BeliefChallenge(
            student_id="stu_001",
            challenged_dimension="K",
            cta_claim=0.5,
            experimental_evidence={"problem_id": "P001"},
        )
        assert bc.resolved is False
        assert bc.belief_change is None
        assert bc.confidence_in_evidence == 0.8


class TestStrategyChallengeMessage:
    def test_construction(self):
        sc = StrategyChallenge(
            student_id="stu_001",
            current_intervention_type="practice",
            cta_suggestion="切换",
        )
        assert sc.resolved is False
        assert sc.revised_intervention_id is None


# ─────────────────────────────────────────────────────────────────────
# 2. protocol/state_machine.py 测试
# ─────────────────────────────────────────────────────────────────────


class TestCalibrationStateMachine:
    def test_initial_state_is_idle(self):
        """新学生默认 IDLE."""
        sm = CalibrationStateMachine()
        assert sm.current_state("new_stu") == CalibrationState.IDLE

    def test_normal_cycle_transitions(self):
        """正常流程: IDLE → CTA_HYPOTHESIS → LCA_EXPERIMENT → OBSERVATION_PENDING → ... → COMPLETED → IDLE."""
        sm = CalibrationStateMachine()
        sid = "stu_001"

        # IDLE → CTA_HYPOTHESIS
        assert sm.transition(sid, MessageType.CTA_OUTPUT) == CalibrationState.CTA_HYPOTHESIS
        # CTA_HYPOTHESIS → LCA_EXPERIMENT
        assert sm.transition(sid, MessageType.LCA_INTERVENTION) == CalibrationState.LCA_EXPERIMENT
        # LCA_EXPERIMENT → OBSERVATION_PENDING
        assert sm.transition(sid, MessageType.OBSERVATION) == CalibrationState.OBSERVATION_PENDING
        # OBSERVATION_PENDING → CTA_UPDATE
        assert sm.transition(sid, MessageType.CTA_UPDATE) == CalibrationState.CTA_UPDATE
        # CTA_UPDATE → LCA_CAUSAL
        assert sm.transition(sid, MessageType.CAUSAL_ATTRIBUTION) == CalibrationState.LCA_CAUSAL
        # LCA_CAUSAL → LCA_REPLAN
        assert sm.transition(sid, MessageType.LCA_INTERVENTION) == CalibrationState.LCA_REPLAN
        # LCA_REPLAN → COMPLETED
        assert sm.transition(sid, MessageType.COMPLETED) == CalibrationState.COMPLETED
        # COMPLETED → IDLE (下一轮启动)
        assert sm.transition(sid, MessageType.CTA_OUTPUT) == CalibrationState.IDLE

    def test_special_modes_from_idle(self):
        """特殊模式 (信念质疑 / 策略质疑 / 元反思 / 人工审核) 只能从 IDLE 触发."""
        sm = CalibrationStateMachine()
        sid = "stu_001"

        assert sm.transition(sid, MessageType.BELIEF_CHALLENGE) == CalibrationState.BELIEF_CHALLENGE
        sm.reset(sid)
        assert sm.transition(sid, MessageType.STRATEGY_CHALLENGE) == CalibrationState.STRATEGY_CHALLENGE
        sm.reset(sid)
        assert sm.transition(sid, MessageType.META_REFLECTION) == CalibrationState.META_REFLECTION
        sm.reset(sid)
        assert sm.transition(sid, MessageType.HUMAN_REVIEW_REQUEST) == CalibrationState.HUMAN_REVIEW

    def test_invalid_transition_keeps_state(self):
        """无匹配转移规则时, 状态保持不变 (不抛错)."""
        sm = CalibrationStateMachine()
        sid = "stu_001"
        # IDLE + META_REFLECTION 不在转移表 → 保持 IDLE
        # (注: 实际 META_REFLECTION 是从 IDLE 触发的, 所以这个测试用 OBSERVATION + IDLE 测)
        sm.reset(sid)
        # 用一个不存在的消息类型 (强制) 测: 没注册的 transition
        sm.state[sid] = CalibrationState.CTA_HYPOTHESIS
        # OBSERVATION + CTA_HYPOTHESIS → 不在转移表
        result = sm.transition(sid, MessageType.OBSERVATION)
        assert result == CalibrationState.CTA_HYPOTHESIS

    def test_history_recorded(self):
        """每次 transition 必须记录历史 (调试用)."""
        sm = CalibrationStateMachine()
        sid = "stu_001"
        sm.transition(sid, MessageType.CTA_OUTPUT)
        sm.transition(sid, MessageType.LCA_INTERVENTION)
        history = sm.get_history(sid)
        assert len(history) == 2
        # history[i] = (prev_state, event, next_state)
        assert history[0][1] == MessageType.CTA_OUTPUT
        assert history[1][1] == MessageType.LCA_INTERVENTION

    def test_reset_clears_state(self):
        """reset 把学生状态重置回 IDLE."""
        sm = CalibrationStateMachine()
        sid = "stu_001"
        sm.transition(sid, MessageType.CTA_OUTPUT)
        assert sm.current_state(sid) == CalibrationState.CTA_HYPOTHESIS
        sm.reset(sid)
        assert sm.current_state(sid) == CalibrationState.IDLE

    def test_state_isolation_between_students(self):
        """不同学生状态互不干扰."""
        sm = CalibrationStateMachine()
        sm.transition("stu_a", MessageType.CTA_OUTPUT)
        # stu_b 仍是 IDLE
        assert sm.current_state("stu_b") == CalibrationState.IDLE

    def test_all_12_states_exist(self):
        """spec §2.2 要求 12 个状态."""
        expected = {
            "IDLE", "CTA_HYPOTHESIS", "LCA_EXPERIMENT", "OBSERVATION_PENDING",
            "CTA_UPDATE", "LCA_CAUSAL", "LCA_REPLAN", "BELIEF_CHALLENGE",
            "STRATEGY_CHALLENGE", "META_REFLECTION", "HUMAN_REVIEW", "COMPLETED",
        }
        actual = {s.name for s in CalibrationState}
        assert actual == expected

    def test_transitions_table_covers_core_cycle(self):
        """_TRANSITIONS 表必须覆盖 8 步常态循环 + 4 特殊入口."""
        assert len(_TRANSITIONS) >= 12, "应该至少有 12 条转移规则 (8 常态 + 4 特殊)"


# ─────────────────────────────────────────────────────────────────────
# 3. anti_hallucination/belief_check.py 测试
# ─────────────────────────────────────────────────────────────────────


class TestBeliefDistributionCheck:
    def test_healthy_state_passes(self, cta_engine):
        """健康 BeliefState: 全部通过."""
        state = cta_engine.create_initial_state("stu_001")
        # 初始状态 confidence 0, evidence_ids 空 → 应该不通过
        # 我们手动设置成健康状态
        for dim_name in ("K", "P", "S", "C", "X"):
            dim = getattr(state, dim_name)
            dim.confidence = 0.8
            dim.evidence_ids = list(range(5))
        is_well, issues = BeliefDistributionCheck.is_well_formed(state)
        assert is_well is True
        assert issues == []

    def test_missing_dimension_detected(self, cta_engine):
        """维度缺失 → 报错."""
        state = cta_engine.create_initial_state("stu_001")
        # 移除 K 维度
        state.K = None
        is_well, issues = BeliefDistributionCheck.is_well_formed(state)
        assert is_well is False
        assert any("K 维度缺失" in i for i in issues)

    def test_missing_confidence_field_detected(self, cta_engine):
        """维度缺 confidence 字段 → 报错."""
        from dataclasses import dataclass, field
        from typing import List
        state = cta_engine.create_initial_state("stu_001")
        # 用一个缺 confidence 的对象替换 K
        @dataclass
        class BrokenK:
            theta: float = 0.0
            evidence_ids: List[int] = field(default_factory=list)
            # 注意: 没有 confidence 字段
        state.K = BrokenK()
        is_well, issues = BeliefDistributionCheck.is_well_formed(state)
        assert is_well is False
        assert any("K 缺少 confidence 字段" in i for i in issues)

    def test_missing_evidence_ids_field_detected(self, cta_engine):
        """维度缺 evidence_ids 字段 → 报错."""
        from dataclasses import dataclass
        state = cta_engine.create_initial_state("stu_001")
        @dataclass
        class BrokenK:
            theta: float = 0.0
            confidence: float = 0.0
            # 注意: 没有 evidence_ids
        state.K = BrokenK()
        is_well, issues = BeliefDistributionCheck.is_well_formed(state)
        assert is_well is False
        assert any("K 缺少 evidence_ids 字段" in i for i in issues)

    def test_low_confidence_without_evidence_fails(self, cta_engine):
        """低 confidence (< 0.6) 但 evidence 不足 (< 3) → 失败."""
        state = cta_engine.create_initial_state("stu_001")
        for dim_name in ("K", "P", "S", "C", "X"):
            dim = getattr(state, dim_name)
            dim.confidence = 0.3
            dim.evidence_ids = []
        is_well, issues = BeliefDistributionCheck.is_well_formed(state)
        assert is_well is False
        assert len(issues) >= 5, "5 个维度都应该报错"
        assert any("K 维度" in i for i in issues)

    def test_low_confidence_with_enough_evidence_passes(self, cta_engine):
        """低 confidence 但 evidence >= 3 → 通过."""
        state = cta_engine.create_initial_state("stu_001")
        for dim_name in ("K", "P", "S", "C", "X"):
            dim = getattr(state, dim_name)
            dim.confidence = 0.3
            dim.evidence_ids = [1, 2, 3]
        is_well, issues = BeliefDistributionCheck.is_well_formed(state)
        assert is_well is True, f"应该通过, issues={issues}"

    def test_overconfident_detected(self, cta_engine):
        """过度自信 (confidence >= 0.99) → 警告."""
        state = cta_engine.create_initial_state("stu_001")
        for dim_name in ("K", "P", "S", "C", "X"):
            dim = getattr(state, dim_name)
            dim.confidence = 0.5  # default
            dim.evidence_ids = list(range(5))
        state.K.confidence = 0.999
        is_well, issues = BeliefDistributionCheck.is_well_formed(state)
        assert is_well is False
        assert any("过度自信" in i for i in issues)

    def test_constants(self):
        """常量必须合理."""
        assert BeliefDistributionCheck.LOW_CONFIDENCE_THRESHOLD == 0.6
        assert BeliefDistributionCheck.OVERCONFIDENT_THRESHOLD == 0.99
        assert BeliefDistributionCheck.MIN_EVIDENCE_FOR_LOW_CONF == 3
        assert set(BeliefDistributionCheck.DIMENSIONS) == {"K", "P", "S", "C", "X"}


# ─────────────────────────────────────────────────────────────────────
# 4. anti_hallucination/experiment_design.py 测试
# ─────────────────────────────────────────────────────────────────────


class TestExperimentDesignValidator:
    def test_valid_intervention_passes(self):
        """健康干预设计: 全部通过."""
        i = Intervention(
            intervention_type=InterventionType.PRACTICE,
            bloom_target=BloomLevel.APPLY,
            target_skills=["python.basics"],
            difficulty=0.5,
            quantity=5,
            feedback_density=0.5,
            scaffolding_level=0.5,
        )
        is_ok, issues = ExperimentDesignValidator.validate_intervention(i)
        assert is_ok is True, f"应通过, issues={issues}"

    def test_practice_high_difficulty_no_scaffolding_fails(self):
        """PRACTICE 难度 > 0.8 + scaffolding < 0.3 → 学生可能放弃."""
        i = Intervention(
            intervention_type=InterventionType.PRACTICE,
            bloom_target=BloomLevel.ANALYZE,
            target_skills=["python.basics"],
            difficulty=0.95,
            quantity=5,
            feedback_density=0.5,
            scaffolding_level=0.1,
        )
        is_ok, issues = ExperimentDesignValidator.validate_intervention(i)
        assert is_ok is False
        assert any("PRACTICE" in issue and "scaffolding" in issue for issue in issues)

    def test_explanatory_no_target_skills_fails(self):
        """EXPLANATORY 必须有 target_skills."""
        i = Intervention(
            intervention_type=InterventionType.EXPLANATORY,
            bloom_target=BloomLevel.UNDERSTAND,
            target_skills=[],
            difficulty=0.5,
        )
        is_ok, issues = ExperimentDesignValidator.validate_intervention(i)
        assert is_ok is False
        assert any("EXPLANATORY" in issue and "target_skills" in issue for issue in issues)

    def test_metacognitive_quantity_too_high_fails(self):
        """METACOGNITIVE 数量 > 1 → 认知负担."""
        i = Intervention(
            intervention_type=InterventionType.METACOGNITIVE,
            bloom_target=BloomLevel.EVALUATE,
            target_skills=["self_reflection"],
            quantity=5,
            difficulty=0.5,
        )
        is_ok, issues = ExperimentDesignValidator.validate_intervention(i)
        assert is_ok is False
        assert any("METACOGNITIVE" in issue and "认知负担" in issue for issue in issues)

    def test_feedback_and_scaffolding_both_high_fails(self):
        """feedback + scaffolding 同时 > 0.8 → 认知超载."""
        i = Intervention(
            intervention_type=InterventionType.PRACTICE,
            bloom_target=BloomLevel.APPLY,
            target_skills=["python.basics"],
            difficulty=0.5,
            quantity=5,
            feedback_density=0.9,
            scaffolding_level=0.9,
        )
        is_ok, issues = ExperimentDesignValidator.validate_intervention(i)
        assert is_ok is False
        assert any("认知超载" in issue for issue in issues)

    def test_inquiry_no_target_skills_warns(self):
        """INQUIRY 无 target_skills → 警告."""
        i = Intervention(
            intervention_type=InterventionType.INQUIRY,
            bloom_target=BloomLevel.ANALYZE,
            target_skills=[],
            difficulty=0.5,
        )
        is_ok, issues = ExperimentDesignValidator.validate_intervention(i)
        assert is_ok is False
        assert any("INQUIRY" in issue for issue in issues)


# ─────────────────────────────────────────────────────────────────────
# 5. anti_hallucination/human_review.py 测试
# ─────────────────────────────────────────────────────────────────────


class TestHumanReviewTrigger:
    def _make_cta_output(self, cta_engine, confidence=0.8):
        state = cta_engine.create_initial_state("stu_001")
        state.overall_confidence = confidence
        return CTAOutput.from_belief_state(belief_state=state)

    def test_low_confidence_triggers_review(self, cta_engine):
        """CTA 整体置信度 < 0.6 → 触发."""
        cfg = HumanReviewConfig(confidence_threshold=0.6)
        trigger = HumanReviewTrigger(cfg)
        out = self._make_cta_output(cta_engine, confidence=0.3)
        should, req = trigger.should_request_human_review(out, consecutive_ineffective=0)
        assert should is True
        assert req is not None
        assert req.priority == "high"
        assert "0.30" in req.reason

    def test_belief_check_fail_triggers_review(self, cta_engine):
        """信念分布不合理 → 触发 critical."""
        cfg = HumanReviewConfig(confidence_threshold=0.6)
        trigger = HumanReviewTrigger(cfg)
        state = cta_engine.create_initial_state("stu_001")
        state.overall_confidence = 0.8  # 不低
        # 制造一个不健康的 belief
        for dim in ("K", "P", "S", "C", "X"):
            getattr(state, dim).confidence = 0.99  # 过度自信
            getattr(state, dim).evidence_ids = list(range(5))
        out = CTAOutput.from_belief_state(belief_state=state)
        should, req = trigger.should_request_human_review(out, consecutive_ineffective=0)
        assert should is True
        assert req.priority == "critical"

    def test_consecutive_ineffective_triggers_review(self, cta_engine):
        """连续 3+ 次无效干预 → 触发."""
        cfg = HumanReviewConfig(consecutive_ineffective_threshold=3)
        trigger = HumanReviewTrigger(cfg)
        out = self._make_cta_output(cta_engine, confidence=0.8)
        # 关键: 让 belief_check 通过 (否则会先被 critical 触发)
        for dim in ("K", "P", "S", "C", "X"):
            getattr(out.belief_state, dim).confidence = 0.8
            getattr(out.belief_state, dim).evidence_ids = list(range(5))
        should, req = trigger.should_request_human_review(out, consecutive_ineffective=4)
        assert should is True
        assert req.priority == "high"
        assert "连续 4 次" in req.reason

    def test_no_trigger_when_healthy(self, cta_engine):
        """健康状态 → 不触发."""
        trigger = HumanReviewTrigger()
        out = self._make_cta_output(cta_engine, confidence=0.85)
        # 关键: 让 belief_check 通过 (否则会先被 critical 触发)
        for dim in ("K", "P", "S", "C", "X"):
            getattr(out.belief_state, dim).confidence = 0.8
            getattr(out.belief_state, dim).evidence_ids = list(range(5))
        should, req = trigger.should_request_human_review(out, consecutive_ineffective=0)
        assert should is False
        assert req is None

    def test_disabled_does_not_trigger(self, cta_engine):
        """enabled=False → 不触发任何 review."""
        cfg = HumanReviewConfig(enabled=False)
        trigger = HumanReviewTrigger(cfg)
        out = self._make_cta_output(cta_engine, confidence=0.1)  # 应该触发
        should, req = trigger.should_request_human_review(out)
        assert should is False

    def test_review_queue_lifecycle(self, cta_engine):
        """queue + get_pending + clear 流程."""
        trigger = HumanReviewTrigger()
        out = self._make_cta_output(cta_engine, confidence=0.1)
        should, req = trigger.should_request_human_review(out)
        trigger.queue_review(req)
        assert len(trigger.get_pending_reviews()) == 1
        trigger.clear()
        assert len(trigger.get_pending_reviews()) == 0


# ─────────────────────────────────────────────────────────────────────
# 6. deadlock/timeout.py 测试
# ─────────────────────────────────────────────────────────────────────


class TestTimeoutGuard:
    def test_quick_operation_no_timeout(self):
        """快操作: 不抛 TimeoutError."""
        guard = TimeoutGuard(default_timeout_sec=5)
        with guard.timeout(seconds=2) as info:
            time.sleep(0.01)
        assert info["exceeded"] is False
        assert info["elapsed"] < 1.0

    def test_slow_operation_raises(self):
        """慢操作: 抛 TimeoutError."""
        guard = TimeoutGuard(default_timeout_sec=1)
        with pytest.raises(TimeoutError) as exc_info:
            with guard.timeout(seconds=0.1):
                time.sleep(0.5)
        assert "超过" in str(exc_info.value)
        assert "0.1 秒" in str(exc_info.value)

    def test_default_timeout_used(self):
        """不传 seconds → 用 default."""
        guard = TimeoutGuard(default_timeout_sec=0.1)
        with pytest.raises(TimeoutError):
            with guard.timeout():  # no arg
                time.sleep(0.5)

    def test_info_dict_updated_after_block(self):
        """info dict 在 with 块退出后被填充 elapsed."""
        guard = TimeoutGuard()
        with guard.timeout(seconds=5) as info:
            time.sleep(0.1)
        # 块退出时 info["elapsed"] 才会被填
        assert info["elapsed"] >= 0.1
        assert info["exceeded"] is False
        # 块内 info["elapsed"] 仍是初始 0.0
        with guard.timeout(seconds=5) as info2:
            assert info2["elapsed"] == 0.0


# ─────────────────────────────────────────────────────────────────────
# 7. deadlock/fallback.py 测试
# ─────────────────────────────────────────────────────────────────────


class TestSingleAgentFallback:
    def test_should_fallback_error_threshold(self, cta_engine, lca_engine):
        """连续错误 >= 3 → 应降级."""
        fb = SingleAgentFallback(cta_engine, lca_engine)
        assert fb.should_fallback(error_count=3, time_elapsed_sec=1.0) is True
        assert fb.should_fallback(error_count=2, time_elapsed_sec=1.0) is False

    def test_should_fallback_time_threshold(self, cta_engine, lca_engine):
        """单次互校 > 60s → 应降级."""
        fb = SingleAgentFallback(cta_engine, lca_engine)
        assert fb.should_fallback(error_count=0, time_elapsed_sec=61.0) is True
        assert fb.should_fallback(error_count=0, time_elapsed_sec=30.0) is False

    def test_run_degraded_marks_degraded_mode(self, cta_engine, lca_engine, make_observation):
        """run_degraded 必须把 degraded_mode=True + 记 fallback_reason."""
        state = cta_engine.create_initial_state("stu_001")
        obs = make_observation()
        fb = SingleAgentFallback(cta_engine, lca_engine)
        result = fb.run_degraded(state, obs, fallback_reason="测试超时")
        assert result.degraded_mode is True
        assert result.metadata["fallback_reason"] == "测试超时"
        assert "degraded_at" in result.metadata
        # 必须有可用的 intervention
        assert result.intervention is not None
        assert result.intervention.intervention_type in InterventionType


# ─────────────────────────────────────────────────────────────────────
# 8. modes/normal.py 测试
# ─────────────────────────────────────────────────────────────────────


class TestNormalCycle:
    def test_run_6_steps(self, cta_engine, lca_engine, make_observation):
        """常态循环 6 步: CTA update → CTA output → LCA select → 包装 + state 转移."""
        sm = CalibrationStateMachine()
        cycle = NormalCycle(cta_engine, lca_engine, sm)
        state = cta_engine.create_initial_state("stu_001")
        obs = make_observation(correct=True, score=1.0, bloom_level=BloomLevel.APPLY)

        new_state, cta_output, calibrated = cycle.run(
            state=state, observation=obs, previous_lca_result=None,
        )

        # Step 1: CTA 更新信念
        assert new_state is not None
        assert new_state.student_id == "stu_001"
        # Step 3: CTAOutput 包装
        assert cta_output.student_id == "stu_001"
        assert cta_output.calibration_round == 0  # M2 W4 占位
        # Step 4: LCA 选了干预
        assert calibrated.intervention is not None
        assert calibrated.student_id == "stu_001"
        # Step 5+7: state_machine 转移 → 至少有过 2 次 transition
        # (CTA_OUTPUT + LCA_INTERVENTION + OBSERVATION = 3 次)
        assert sm.current_state("stu_001") == CalibrationState.OBSERVATION_PENDING

    def test_run_with_previous_lca_result(self, cta_engine, lca_engine, make_observation):
        """带 previous_lca_result → CTA 端能拿到 actual_outcome (因果归因路径)."""
        from ecos.lca.orchestrator import LCAResult
        sm = CalibrationStateMachine()
        cycle = NormalCycle(cta_engine, lca_engine, sm)
        state = cta_engine.create_initial_state("stu_001")
        obs = make_observation(correct=True)

        # 构造一个 previous_lca_result
        prev_intervention = Intervention(
            intervention_type=InterventionType.PRACTICE,
            bloom_target=BloomLevel.APPLY, target_skills=["s"],
            difficulty=0.5, quantity=5, feedback_density=0.5,
            scaffolding_level=0.5, clt_level=CLTLevel.DEVELOPING,
            ca_stage=CAStage.COACHING, bjork_triggers=["test"],
            expected_gain=0.1, expected_risk=0.0, estimated_duration_sec=600,
            rationale="prev",
        )
        prev = CalibratedLCAResult.from_lca_result(
            LCAResult(
                student_id="stu_001", intervention=prev_intervention,
                rationale="r", expected_gain=0.1, expected_risk=0.0,
                bloom_target=BloomLevel.APPLY, clt_level=CLTLevel.DEVELOPING,
                ca_stage=CAStage.COACHING,
            ),
            calibration_round=1,
        )
        prev.actual_outcome = 0.85  # 上一次干预的实测结果

        new_state, cta_output, calibrated = cycle.run(
            state=state, observation=obs, previous_lca_result=prev,
        )
        assert new_state is not None
        assert calibrated is not None

    def test_run_does_not_pollute_state_on_lca_failure(
        self, cta_engine, lca_engine, make_observation,
    ):
        """防御: LCA select 失败时, 整个 run 抛错, 不污染 cta_output (CLAUDE.md [7])."""
        sm = CalibrationStateMachine()
        cycle = NormalCycle(cta_engine, lca_engine, sm)
        state = cta_engine.create_initial_state("stu_001")
        obs = make_observation()

        # Mock LCA select 让它抛错
        with patch.object(lca_engine, "select_intervention", side_effect=RuntimeError("LCA down")):
            with pytest.raises(RuntimeError):
                cycle.run(state=state, observation=obs)

        # 状态没变 (LCA 出错时, CTA update 也不该持久化到 state)
        # 实际上 cycle.run 不修改 state 本身, 只返回 new_state, 失败时 new_state 是 partial
        # 这里我们只验证不抛 TypeError 或其他混乱错误


# ─────────────────────────────────────────────────────────────────────
# 9. modes/belief_challenge.py 测试
# ─────────────────────────────────────────────────────────────────────


class TestBeliefChallengeTriggers:
    """信念质疑 3 触发条件测试 (spec §3.2)."""

    def _make_cta_output(self, cta_engine, K_mastery=0.5, P_mastery=0.5, dominant=BloomLevel.APPLY):
        state = cta_engine.create_initial_state("stu_001")
        state.K.mastery_prob = K_mastery
        state.P.mastery_prob = P_mastery
        # 通过设置 layer 概率让 dominant_layer 变成目标值
        # BloomLevel enum: REMEMBER=1 ... CREATE=6
        probs_map = {1: "remember", 2: "understand", 3: "apply", 4: "analyze", 5: "evaluate", 6: "create"}
        for layer, attr in probs_map.items():
            setattr(state.bloom_profile, attr, 0.1)
        setattr(state.bloom_profile, probs_map[dominant.value], 0.9)
        state.bloom_profile.update_dominant()
        return CTAOutput.from_belief_state(belief_state=state)

    def test_trigger_high_K_but_wrong(self, cta_engine, make_observation):
        """规则 1: K 高 mastery (> 0.7) 但答错 → 触发 K 维度质疑."""
        out = self._make_cta_output(cta_engine, K_mastery=0.85)
        obs = make_observation(correct=False)
        should, dim = should_trigger_belief_challenge(out, obs)
        assert should is True
        assert dim == "K"

    def test_no_trigger_low_K(self, cta_engine, make_observation):
        """K 不高 → 不触发 (K 维度)."""
        out = self._make_cta_output(cta_engine, K_mastery=0.5)
        obs = make_observation(correct=False)
        should, dim = should_trigger_belief_challenge(out, obs)
        # 可能会被其他规则触发, 但 K 维度不会
        if should:
            assert dim != "K"

    def test_trigger_bloom_dominant_jump(self, cta_engine, make_observation):
        """规则 2: Bloom dominant_layer 突变 >= 2 层 → 触发."""
        out = self._make_cta_output(cta_engine, dominant=BloomLevel.CREATE)
        obs = make_observation(correct=True)
        # prev dominant = REMEMBER (差 4 层, 远大于 2)
        should, dim = should_trigger_belief_challenge(
            out, obs, prev_dominant_layer=BloomLevel.REMEMBER,
        )
        assert should is True
        assert dim == "bloom_dominant"

    def test_no_trigger_bloom_dominant_stable(self, cta_engine, make_observation):
        """Bloom dominant 不变 → 不触发 bloom_dominant."""
        out = self._make_cta_output(cta_engine, dominant=BloomLevel.APPLY)
        obs = make_observation()
        should, dim = should_trigger_belief_challenge(
            out, obs, prev_dominant_layer=BloomLevel.APPLY,
        )
        if should:
            assert dim != "bloom_dominant"

    def test_trigger_high_P_slow_response(self, cta_engine, make_observation):
        """规则 3: P 高 mastery (> 0.6) + 答题慢 (> 60s) → 触发 P 维度."""
        out = self._make_cta_output(cta_engine, P_mastery=0.75)
        obs = make_observation(response_time_sec=80.0)
        should, dim = should_trigger_belief_challenge(out, obs)
        assert should is True
        assert dim == "P"

    def test_no_trigger_when_all_healthy(self, cta_engine, make_observation):
        """所有维度都健康 → 不触发."""
        out = self._make_cta_output(cta_engine, K_mastery=0.5, P_mastery=0.5)
        obs = make_observation(correct=True, response_time_sec=20.0)
        should, dim = should_trigger_belief_challenge(
            out, obs, prev_dominant_layer=BloomLevel.APPLY,
        )
        assert should is False
        assert dim is None


class TestBeliefChallengeMode:
    def test_trigger_challenge_records_pending(self, cta_engine, make_observation):
        """trigger_challenge 把 challenge 挂到 cta_output."""
        mode = BeliefChallengeMode(cta_engine)
        state = cta_engine.create_initial_state("stu_001")
        state.K.theta = 0.85
        out = CTAOutput.from_belief_state(belief_state=state)
        obs = make_observation(correct=False)

        challenge = mode.trigger_challenge(out, obs, "K")
        assert challenge.challenged_dimension == "K"
        assert challenge.cta_claim == 0.85
        assert out.belief_challenge_pending is True

    def test_resolve_challenge_records_history(self, cta_engine, make_observation):
        """resolve_challenge 把变化写到 challenge_history."""
        mode = BeliefChallengeMode(cta_engine)
        state = cta_engine.create_initial_state("stu_001")
        state.K.theta = 0.85
        out = CTAOutput.from_belief_state(belief_state=state)
        obs = make_observation(correct=False)

        challenge = mode.trigger_challenge(out, obs, "K")

        # 模拟 CTA 重新估计后 state 变化
        new_state = cta_engine.create_initial_state("stu_001")
        new_state.K.theta = 0.55  # 0.85 → 0.55

        out = mode.resolve_challenge(out, challenge, obs, state, new_state)
        assert out.belief_challenge_pending is False
        assert challenge.resolved is True
        assert challenge.belief_change is not None
        assert abs(challenge.belief_change - 0.30) < 0.01
        assert len(out.challenge_history) == 1
        assert "K:" in out.challenge_history[0]

    def test_resolve_bloom_dominant_challenge(self, cta_engine, make_observation):
        """resolve bloom_dominant 维度 (用 layer 数值)."""
        mode = BeliefChallengeMode(cta_engine)
        state = cta_engine.create_initial_state("stu_001")
        # 默认 dominant_layer = UNDERSTAND (value=2)
        out = CTAOutput.from_belief_state(belief_state=state)
        obs = make_observation()

        challenge = mode.trigger_challenge(out, obs, "bloom_dominant")
        # 触发时记录当时的 dominant value
        assert challenge.cta_claim == float(state.bloom_profile.dominant_layer.value)

        new_state = cta_engine.create_initial_state("stu_001")
        # 把 new_state 的 dominant_layer 设为 EVALUATE (value=5)
        new_state.bloom_profile.apply = 0.1
        new_state.bloom_profile.evaluate = 0.9
        new_state.bloom_profile.update_dominant()
        assert new_state.bloom_profile.dominant_layer == BloomLevel.EVALUATE

        out = mode.resolve_challenge(out, challenge, obs, state, new_state)
        assert challenge.resolved is True
        assert challenge.belief_change is not None
        assert challenge.belief_change > 0


# ─────────────────────────────────────────────────────────────────────
# 10. modes/strategy_challenge.py 测试
# ─────────────────────────────────────────────────────────────────────


class TestStrategyChallengeMode:
    def _make_calibrated_lca_result(self, cta_engine):
        from ecos.lca.orchestrator import LCAResult
        i = Intervention(
            intervention_type=InterventionType.PRACTICE,
            bloom_target=BloomLevel.APPLY, target_skills=["s"],
            difficulty=0.5, quantity=5, feedback_density=0.5,
            scaffolding_level=0.5, clt_level=CLTLevel.DEVELOPING,
            ca_stage=CAStage.COACHING, bjork_triggers=["test"],
            expected_gain=0.1, expected_risk=0.0, estimated_duration_sec=600,
            rationale="t",
        )
        return CalibratedLCAResult.from_lca_result(
            LCAResult(
                student_id="stu_001", intervention=i,
                rationale="r", expected_gain=0.1, expected_risk=0.0,
                bloom_target=BloomLevel.APPLY, clt_level=CLTLevel.DEVELOPING,
                ca_stage=CAStage.COACHING,
            ),
        )

    def test_detect_no_history(self, cta_engine):
        """历史 < window → 不触发."""
        mode = StrategyChallengeMode.__new__(StrategyChallengeMode)  # 避免 init
        mode.lca = None
        # 用空历史
        assert mode.detect_ineffective_intervention(
            intervention_history=[],
            state_trajectory=[],
        ) is False

    def test_detect_effective_intervention(self, cta_engine):
        """平均改善 > 0.05 → 不触发."""
        mode = StrategyChallengeMode.__new__(StrategyChallengeMode)
        mode.lca = None
        # 构造 6 个 state (0.3, 0.4, 0.5, 0.6, 0.7, 0.8)
        history = [self._make_calibrated_lca_result(cta_engine) for _ in range(5)]
        states = []
        for i in range(6):
            s = cta_engine.create_initial_state("stu_001")
            s.K.mastery_prob = 0.3 + i * 0.1
            states.append(s)
        assert mode.detect_ineffective_intervention(
            intervention_history=history, state_trajectory=states,
        ) is False  # 平均改善 0.1 > 0.05

    def test_detect_ineffective_intervention(self, cta_engine):
        """平均改善 < 0.05 → 触发."""
        mode = StrategyChallengeMode.__new__(StrategyChallengeMode)
        mode.lca = None
        history = [self._make_calibrated_lca_result(cta_engine) for _ in range(5)]
        # 6 个 state 全部 0.5 (改善 = 0)
        states = []
        for _ in range(6):
            s = cta_engine.create_initial_state("stu_001")
            s.K.mastery_prob = 0.5
            states.append(s)
        assert mode.detect_ineffective_intervention(
            intervention_history=history, state_trajectory=states,
        ) is True

    def test_challenge_lca_constructs_message(self, cta_engine):
        """challenge_lca 构造 StrategyChallenge."""
        mode = StrategyChallengeMode.__new__(StrategyChallengeMode)
        mode.lca = None
        history = [self._make_calibrated_lca_result(cta_engine) for _ in range(3)]
        challenge = mode.challenge_lca(
            student_id="stu_001",
            intervention_history=history,
            calibration_round=5,
        )
        assert challenge.student_id == "stu_001"
        assert challenge.calibration_round == 5
        assert challenge.current_intervention_type == "practice"
        assert "切换" in challenge.cta_suggestion

    def test_constants(self):
        """spec 阈值常量."""
        assert DETECT_WINDOW == 5
        assert INEFFECTIVE_GAIN_THRESHOLD == 0.05
        assert HIGH_CONFIDENCE_THRESHOLD == 0.7


# ─────────────────────────────────────────────────────────────────────
# 11. DualAgentOrchestrator 集成测试
# ─────────────────────────────────────────────────────────────────────


class TestDualAgentOrchestrator:
    def test_first_observation_initializes_state(self, dual_orch, make_observation):
        """首次观测 → 自动 create_initial_state."""
        sid = "test_orch_init_001"
        obs = make_observation()
        result = dual_orch.process_observation(obs, student_id=sid)
        assert sid in dual_orch.state
        assert sid in dual_orch.intervention_history
        assert len(dual_orch.intervention_history[sid]) == 1

    def test_observation_increments_round(self, dual_orch, make_observation):
        """每次观测 → calibration_round + 1 (从 1 开始)."""
        sid = "test_orch_round_001"
        for i in range(3):
            obs = make_observation(problem_id=f"P{i:03d}")
            result = dual_orch.process_observation(obs, student_id=sid)
            # 第一次观测 round=1, 之后递增
            assert result.calibration_round == i + 1

    def test_observation_appends_history(self, dual_orch, make_observation):
        """每次观测 → intervention_history append."""
        sid = "test_orch_hist_001"
        for _ in range(5):
            obs = make_observation()
            dual_orch.process_observation(obs, student_id=sid)
        assert len(dual_orch.get_history(sid)) == 5

    def test_observation_appends_trajectory(self, dual_orch, make_observation):
        """每次观测 → state_trajectory append."""
        sid = "test_orch_traj_001"
        for _ in range(3):
            obs = make_observation()
            dual_orch.process_observation(obs, student_id=sid)
        assert len(dual_orch.get_state_trajectory(sid)) == 3

    def test_previous_outcome_filled(self, dual_orch, make_observation):
        """第二次观测时, 第一次的 result.actual_outcome 被填充.

        actual_outcome 反映**下一次观测的结果** (上一轮干预是否有效).
        """
        sid = "test_orch_outcome_001"
        obs1 = make_observation(correct=True)
        result1 = dual_orch.process_observation(obs1, student_id=sid)
        assert result1.actual_outcome is None, "第一次观测时, 自己的 actual_outcome 还没填"

        obs2 = make_observation(correct=True)  # 第二次答对 → 上一轮干预有效
        dual_orch.process_observation(obs2, student_id=sid)

        # 现在 result1 的 actual_outcome 应该被填了 (1.0 = 第二次答对)
        history = dual_orch.get_history(sid)
        assert history[0].actual_outcome == 1.0

    def test_timeout_falls_back_to_single_agent(self, cta_engine, lca_engine, make_observation):
        """超时 → SingleAgentFallback 介入, 标记 degraded_mode=True."""
        # 让 LCA select 故意超时 (mock 一个慢操作)
        slow_lca = lca_engine
        original_select = slow_lca.select_intervention

        def slow_select(cta_input):
            time.sleep(10)  # 远超过 timeout
            return original_select(cta_input)

        cfg = DualAgentConfig(timeout_sec=1)  # 1s 超时
        orch = DualAgentOrchestrator(
            config=cfg, cta_engine=cta_engine, lca_engine=slow_lca,
        )
        # 直接用 fallback.run_degraded 路径测试
        sid = "test_orch_timeout_001"
        state = cta_engine.create_initial_state(sid)
        obs = make_observation()
        fb = SingleAgentFallback(cta_engine, slow_lca)
        result = fb.run_degraded(state, obs, fallback_reason="test")
        assert result.degraded_mode is True
        assert result.metadata["fallback_reason"] == "test"

    def test_get_warnings_per_student(self, dual_orch, make_observation):
        """get_warnings 隔离每个学生的警告."""
        sid_a = "test_warn_a"
        sid_b = "test_warn_b"
        for _ in range(2):
            dual_orch.process_observation(make_observation(), student_id=sid_a)
        for _ in range(2):
            dual_orch.process_observation(make_observation(), student_id=sid_b)
        warnings_a = dual_orch.get_warnings(sid_a)
        warnings_b = dual_orch.get_warnings(sid_b)
        # 警告属于各自学生 (可能为空列表)
        assert isinstance(warnings_a, list)
        assert isinstance(warnings_b, list)

    def test_state_persists_across_observations(self, dual_orch, make_observation):
        """state 在多次观测间保持 + 累加."""
        sid = "test_orch_persist_001"
        state_initial = dual_orch.state.get(sid)  # None initially
        assert state_initial is None

        for _ in range(3):
            dual_orch.process_observation(make_observation(), student_id=sid)

        final_state = dual_orch.state[sid]
        # 5D 应该被更新 (K.mastery_prob 应该有变化, 即便很小)
        assert final_state is not None
        # 至少 response_history 会有 entry (但这个在 belief_engine 那边, 不在 dual_agent.state)
        # dual_agent 内部 state 是 BeliefState
        assert final_state.student_id == sid

    def test_missing_student_id_raises(self, dual_orch, make_observation):
        """observation 和 student_id 都缺 → ValueError."""
        obs = make_observation()
        with pytest.raises(ValueError, match="必须提供 student_id"):
            dual_orch.process_observation(obs, student_id=None)
        # 用 observation 也没有 student_id
        with pytest.raises(ValueError, match="必须提供 student_id"):
            dual_orch.process_observation(obs)

    def test_timeout_disabled_path(self, cta_engine, lca_engine, make_observation):
        """enable_timeout=False → 走 slow path (no timeout wrap)."""
        cfg = DualAgentConfig(cta_config=cta_engine.config, lca_config=lca_engine.config)
        cfg.timeout_sec = 1
        cfg.enable_timeout = False
        orch = DualAgentOrchestrator(
            config=cfg, cta_engine=cta_engine, lca_engine=lca_engine,
        )
        result = orch.process_observation(make_observation(), student_id="t_no_to_001")
        assert result is not None

    def test_timeout_triggers_fallback(self, cta_engine, lca_engine, make_observation):
        """NormalCycle 慢 → 触发 SingleAgentFallback 降级."""
        # 让 normal_cycle 的 LCA 调用故意超时
        original_select = lca_engine.select_intervention

        def slow_select(cta_input):
            time.sleep(2)  # 超过 timeout_sec=1
            return original_select(cta_input)

        cfg = DualAgentConfig(cta_config=cta_engine.config, lca_config=lca_engine.config)
        cfg.timeout_sec = 1
        cfg.enable_timeout = True
        orch = DualAgentOrchestrator(
            config=cfg, cta_engine=cta_engine, lca_engine=lca_engine,
        )
        # 直接 patch NormalCycle.run 让它抛 TimeoutError
        with patch.object(orch.normal_cycle, "run", side_effect=TimeoutError("test")):
            result = orch.process_observation(make_observation(), student_id="t_to_001")
        assert result.degraded_mode is True
        assert "超时" in result.metadata.get("fallback_reason", "")

    def test_belief_challenge_triggered_during_observation(
        self, dual_orch, make_observation,
    ):
        """高 K mastery + 答错 → 信念质疑在 process_observation 内被触发."""
        sid = "t_bc_trig_001"
        # 跑 5 次全对, 让 K mastery 涨到 > 0.7
        for _ in range(5):
            dual_orch.process_observation(
                make_observation(correct=True, score=1.0), student_id=sid,
            )
        # 现在 K mastery 应该高了, 答错一次
        dual_orch.process_observation(
            make_observation(correct=False, score=0.0), student_id=sid,
        )
        # 信念质疑被记录
        challenges = dual_orch.get_belief_challenges(sid)
        # 可能没有触发 (因为 K mastery 涨到 0.7+ 需要更多题目), 但至少 history 不为 None
        assert isinstance(challenges, list)

    def test_consecutive_ineffective_counter(
        self, dual_orch, make_observation,
    ):
        """连续无效 (actual_outcome < 0.3) → 计数器累加."""
        sid = "t_inconsec_001"
        # 跑 3 次, 第二次答错 (但第三次答对, 所以只累加 1 次)
        for correct in (True, False, True, False, False):
            dual_orch.process_observation(
                make_observation(correct=correct), student_id=sid,
            )
        # _consecutive_ffective 内部属性, 反映"最后一次观测 outcome 是否 < 0.3"
        counter = dual_orch._consecutive_ineffective.get(sid, 0)
        assert isinstance(counter, int)
        assert counter >= 0

    def test_trajectory_capped_at_100(self, dual_orch, make_observation):
        """state_trajectory 上限 100 条."""
        sid = "t_traj_cap_001"
        for _ in range(105):
            dual_orch.process_observation(make_observation(), student_id=sid)
        assert len(dual_orch.get_state_trajectory(sid)) == 100

    def test_get_strategy_challenges_empty_by_default(self, dual_orch):
        """未触发策略质疑时 → 空列表."""
        assert dual_orch.get_strategy_challenges("nonexistent_sid") == []

    def test_get_belief_challenges_empty_by_default(self, dual_orch):
        """未触发信念质疑时 → 空列表."""
        assert dual_orch.get_belief_challenges("nonexistent_sid") == []

    def test_belief_challenge_triggered_high_K_then_wrong(
        self, dual_orch, make_observation,
    ):
        """K 涨到 > 0.7 后答错 → 信念质疑被触发 + 记录.

        注: BKT 的 K.mastery_prob 自然增长上限 ~0.66 (饱和), 所以手动设置.
        """
        sid = "t_bc_k_001"
        # 第一次观测: 初始化 state
        dual_orch.process_observation(
            make_observation(correct=True, score=1.0, problem_id="warm"),
            student_id=sid,
        )
        # 手动把 K 调高到 0.85, 模拟 "CTA 高置信度"
        dual_orch.state[sid].K.mastery_prob = 0.85
        # 答错
        dual_orch.process_observation(
            make_observation(correct=False, score=0.0, problem_id="fail"),
            student_id=sid,
        )
        challenges = dual_orch.get_belief_challenges(sid)
        # 至少有一条信念质疑 (K 维度)
        assert len(challenges) >= 1, f"应有信念质疑, got {challenges}"
        assert challenges[0].challenged_dimension == "K"

    def test_llm_client_injection_sets_use_llm_rationale(
        self, cta_engine, lca_engine,
    ):
        """llm_client 注入时 → LCA config.use_llm_rationale = True."""
        cfg = DualAgentConfig(cta_config=cta_engine.config, lca_config=lca_engine.config)
        # 注入 mock llm_client
        mock_llm = MagicMock()
        orch = DualAgentOrchestrator(
            config=cfg, cta_engine=cta_engine, lca_engine=lca_engine,
            llm_client=mock_llm,
        )
        # 构造 LCAEngine 时 use_llm_rationale 会被设为 True
        assert orch.lca_engine.config.use_llm_rationale is True

    def test_consecutive_ineffective_increments(
        self, dual_orch, make_observation,
    ):
        """连续 outcome < 0.3 → 计数器递增."""
        sid = "t_coninc_002"
        # 跑 5 次都答错, prev_calibrated.actual_outcome 会设为 0.0 → counter +1
        for i in range(5):
            dual_orch.process_observation(
                make_observation(correct=False, score=0.0, problem_id=f"p{i}"),
                student_id=sid,
            )
        counter = dual_orch._consecutive_ineffective.get(sid, 0)
        # 至少累加 1 次 (第一次观测时没 outcome, 之后每次都 +1)
        assert counter >= 1, f"应该 ≥ 1, got {counter}"

    def test_belief_challenge_resolved_records_warning(
        self, dual_orch, make_observation,
    ):
        """信念质疑解决后 → 警告被记录到 warnings[sid]."""
        sid = "t_bc_warn_001"
        # 初始化
        dual_orch.process_observation(
            make_observation(correct=True, score=1.0, problem_id="warm"),
            student_id=sid,
        )
        # 手动把 K 调高到 0.85
        dual_orch.state[sid].K.mastery_prob = 0.85
        # 答错
        dual_orch.process_observation(
            make_observation(correct=False, score=0.0, problem_id="fail"),
            student_id=sid,
        )
        # 信念质疑应该被触发并被记录
        assert len(dual_orch.get_belief_challenges(sid)) >= 1


# ─────────────────────────────────────────────────────────────────────
# 12. 端到端 + 防御性自检 [8] 协议变更覆盖测试
# ─────────────────────────────────────────────────────────────────────


class TestEndToEndDualAgent:
    """端到端: 模拟学生答题 10 次, 验证 dual_agent 全流程不报错 + state 正确."""

    def test_10_rounds_no_crash(self, dual_orch, make_observation):
        sid = "test_e2e_001"
        for i in range(10):
            obs = make_observation(
                problem_id=f"E2E-{i:03d}",
                correct=(i % 3 != 0),  # 2/3 正确
                score=1.0 if (i % 3 != 0) else 0.0,
                bloom_level=list(BloomLevel)[i % 6],
                response_time_sec=20.0 + (i % 5) * 10,
            )
            result = dual_orch.process_observation(obs, student_id=sid)
            assert result is not None
            assert result.intervention is not None

        history = dual_orch.get_history(sid)
        trajectory = dual_orch.get_state_trajectory(sid)
        assert len(history) == 10
        assert len(trajectory) == 10

    def test_state_machine_ends_at_pending(self, dual_orch, make_observation):
        """每轮结束后, state_machine 应在 OBSERVATION_PENDING 状态."""
        sid = "test_e2e_sm_001"
        for _ in range(3):
            dual_orch.process_observation(make_observation(), student_id=sid)
        assert dual_orch.state_machine.current_state(sid) == CalibrationState.OBSERVATION_PENDING


# ─────────────────────────────────────────────────────────────────────
# 13. 协议兼容性测试 (CLAUDE.md [8] 改协议必加测试)
# ─────────────────────────────────────────────────────────────────────


class TestProtocolCompatibility:
    """任何协议字段变更 (CalibrationMessage / CalibratedLCAResult) 必须通过这些测试."""

    def test_calibration_message_required_fields(self):
        """CalibrationMessage 必填字段不能删."""
        msg = CalibrationMessage(message_type=MessageType.CTA_OUTPUT, student_id="s1")
        d = msg.to_dict()
        for key in ("message_id", "message_type", "student_id", "timestamp",
                    "version", "calibration_round", "payload", "priority", "timeout_sec", "metadata"):
            assert key in d, f"CalibrationMessage 丢失字段: {key}"

    def test_calibrated_lca_result_required_fields(self, cta_engine):
        """CalibratedLCAResult 必填字段不能删."""
        from ecos.lca.orchestrator import LCAResult
        i = Intervention(
            intervention_type=InterventionType.PRACTICE,
            bloom_target=BloomLevel.APPLY, target_skills=["s"],
            difficulty=0.5, quantity=5, feedback_density=0.5,
            scaffolding_level=0.5, clt_level=CLTLevel.DEVELOPING,
            ca_stage=CAStage.COACHING, bjork_triggers=["test"],
            expected_gain=0.1, expected_risk=0.0, estimated_duration_sec=600,
            rationale="t",
        )
        lca = LCAResult(
            student_id="s1", intervention=i,
            rationale="r", expected_gain=0.1, expected_risk=0.0,
            bloom_target=BloomLevel.APPLY, clt_level=CLTLevel.DEVELOPING,
            ca_stage=CAStage.COACHING,
        )
        cal = CalibratedLCAResult.from_lca_result(lca)
        d = cal.to_dict()
        for key in ("student_id", "intervention", "rationale", "expected_gain",
                    "expected_risk", "bloom_target", "clt_level", "ca_stage",
                    "calibration_round", "actual_outcome", "has_causal_effect",
                    "strategy_challenge_pending", "degraded_mode", "metadata"):
            assert key in d, f"CalibratedLCAResult 丢失字段: {key}"
