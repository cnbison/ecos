"""双 Agent 互校主编排器（spec §6 DualAgentOrchestrator）.

主入口：process_observation(observation) → CalibratedLCAResult

持有：
  - cta_engine（BeliefEngine）：CTA 信念引擎
  - lca_engine（LCAEngine）：LCA 策略引擎
  - state_machine：12 状态机
  - 4 模式：常态 / 信念质疑 / 策略质疑 / 元反思（Phase 5+）
  - 3 抗幻觉 + 1 人工审核触发
  - 2 死锁保护：超时 + 降级

状态管理：
  - state: Dict[student_id, BeliefState]（每个学生的当前 BeliefState）
  - intervention_history: Dict[student_id, List[CalibratedLCAResult]]
  - state_trajectory: Dict[student_id, List[BeliefState]]
  - calibration_round: Dict[student_id, int]
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..cta.belief_engine import BeliefEngine, BeliefEngineConfig
from ..cta.belief_state import BeliefState
from ..lca.orchestrator import LCAEngine, LCAEngineConfig
from .anti_hallucination import (
    BeliefDistributionCheck,
    ExperimentDesignValidator,
    HumanReviewConfig,
    HumanReviewTrigger,
)
from .deadlock import SingleAgentFallback, TimeoutGuard
from .modes import (
    NormalCycle,
    StrategyChallengeMode,
    should_trigger_belief_challenge,
)
from .protocol.messages import (
    BeliefChallenge,
    CalibratedLCAResult,
    CTAOutput,
    HumanReviewRequest,
    MessageType,
    StrategyChallenge,
)
from .protocol.state_machine import (
    CalibrationState,
    CalibrationStateMachine,
)

_log = logging.getLogger(__name__)


@dataclass
class DualAgentConfig:
    """双 Agent 配置."""

    cta_config: BeliefEngineConfig = field(default_factory=BeliefEngineConfig)
    lca_config: LCAEngineConfig = field(default_factory=LCAEngineConfig)
    human_review_config: HumanReviewConfig = field(default_factory=HumanReviewConfig)
    timeout_sec: int = 30
    enable_timeout: bool = True
    # Phase 5+: enable_meta_reflection: bool = False


class DualAgentOrchestrator:
    """双 Agent 互校主编排器.

    用法：
        orch = DualAgentOrchestrator(config)
        result = orch.process_observation(observation)
        # result is CalibratedLCAResult

    状态由 orch 持有——首次遇到 student_id 自动 create_initial_state。
    """

    def __init__(
        self,
        config: Optional[DualAgentConfig] = None,
        cta_engine: Optional[BeliefEngine] = None,
        lca_engine: Optional[LCAEngine] = None,
        llm_client=None,
    ):
        self.config = config or DualAgentConfig()

        # CTA + LCA 引擎（支持外部注入）
        self.cta_engine = cta_engine or BeliefEngine(self.config.cta_config)
        self.lca_engine = lca_engine or self._build_lca_engine(llm_client)

        # 状态机
        self.state_machine = CalibrationStateMachine()

        # 4 个交互模式（meta_reflection Phase 5+）
        self.normal_cycle = NormalCycle(
            self.cta_engine, self.lca_engine, self.state_machine,
        )
        self.strategy_challenge = StrategyChallengeMode(self.lca_engine)
        # belief_challenge 用函数式（spec §3.2）—— 无状态

        # 抗幻觉 + 人工审核
        self.belief_check = BeliefDistributionCheck()
        self.experiment_validator = ExperimentDesignValidator()
        self.human_review = HumanReviewTrigger(self.config.human_review_config)

        # 死锁保护
        self.timeout_guard = TimeoutGuard(self.config.timeout_sec)
        self.fallback = SingleAgentFallback(self.cta_engine, self.lca_engine)

        # 状态（每个学生）
        self.state: Dict[str, BeliefState] = {}
        self.intervention_history: Dict[str, List[CalibratedLCAResult]] = {}
        self.state_trajectory: Dict[str, List[BeliefState]] = {}
        self.calibration_round: Dict[str, int] = {}

        # 抗幻觉警告 + challenge 历史（用于教师后台接口）
        self.warnings: Dict[str, List[str]] = {}
        self.belief_challenges: Dict[str, List[BeliefChallenge]] = {}
        self.strategy_challenges: Dict[str, List[StrategyChallenge]] = {}

        # 连续无效干预计数（Phase 5+ 接持久化）
        self._consecutive_ineffective: Dict[str, int] = {}

    def _build_lca_engine(self, llm_client) -> LCAEngine:
        """构造 LCA 引擎（注入 LLM client）."""
        # 更新 config 使 LCA 知道是否启用 LLM rationale
        lca_cfg = self.config.lca_config
        if llm_client is not None:
            lca_cfg.use_llm_rationale = True
        return LCAEngine(config=lca_cfg, llm_client=llm_client)

    # ---------------------------------------------------------------
    # 主入口
    # ---------------------------------------------------------------

    def process_observation(
        self,
        observation,
        student_id: Optional[str] = None,
    ) -> CalibratedLCAResult:
        """处理一次观测——主入口.

        Args:
            observation: 学生观测（Observation 或有 student_id 字段的对象）
            student_id: 可选——若 Observation 不含 student_id，用此参数

        Returns:
            CalibratedLCAResult（含 intervention + rationale + actual_outcome 等）
        """
        # 兼容：observation.student_id 不存在时用参数
        sid = getattr(observation, "student_id", student_id)
        if sid is None:
            raise ValueError("必须提供 student_id")

        # 状态准备：首次访问 → create_initial_state
        if sid not in self.state:
            self.state[sid] = self.cta_engine.create_initial_state(sid)
            self.intervention_history[sid] = []
            self.state_trajectory[sid] = []
            self.calibration_round[sid] = 0
            self.warnings[sid] = []
            self.belief_challenges[sid] = []
            self.strategy_challenges[sid] = []
            self._consecutive_ineffective[sid] = 0

        current_state = self.state[sid]
        prev_calibrated: Optional[CalibratedLCAResult] = (
            self.intervention_history[sid][-1] if self.intervention_history[sid] else None
        )

        # Step 0: 填充上一轮的 actual_outcome（基于本次 observation）
        if prev_calibrated is not None:
            # v0.61.0 改: observation.score 优先 (跟 belief_engine.py:292 一致)
            #   之前: 二元 correct 派生 0.0/1.0, partial credit 0.7 答对被当 1.0
            #   现在: score 优先 (0.0-1.0), 老调用方 (只传 correct) fallback 到 0/1
            prev_calibrated.actual_outcome = (
                observation.score
                if observation.score > 0
                else (1.0 if observation.correct else 0.0)
            )

        # Step 1: 检查特殊模式（策略质疑 + 元反思）
        special_result = self._check_special_modes(sid, observation)
        if special_result is not None:
            return special_result

        # Step 2: 信念质疑检测（在常态循环之前）
        cta_output_preview = CTAOutput.from_belief_state(
            current_state,
            calibration_round=self.calibration_round[sid],
        )
        # 检测前一次 bloom dominant
        prev_dominant = (
            self.state_trajectory[sid][-1].bloom_profile.dominant_layer
            if self.state_trajectory[sid]
            else None
        )
        should_challenge, challenge_dim = should_trigger_belief_challenge(
            cta_output_preview, observation, prev_dominant_layer=prev_dominant,
        )
        belief_challenge_to_record: Optional[BeliefChallenge] = None
        if should_challenge and challenge_dim:
            challenge = self._mode_belief_challenge(
                cta_output_preview, observation, challenge_dim,
            )
            self.belief_challenges[sid].append(challenge)
            belief_challenge_to_record = challenge

        # Step 3: 常态循环（带超时保护 + 降级）
        try:
            if self.config.enable_timeout:
                with self.timeout_guard.timeout(self.config.timeout_sec):
                    new_state, cta_output, calibrated = self.normal_cycle.run(
                        state=current_state,
                        observation=observation,
                        previous_lca_result=prev_calibrated,
                        challenge_history=cta_output_preview.challenge_history,
                    )
            else:
                new_state, cta_output, calibrated = self.normal_cycle.run(
                    state=current_state,
                    observation=observation,
                    previous_lca_result=prev_calibrated,
                    challenge_history=cta_output_preview.challenge_history,
                )
        except TimeoutError:
            return self.fallback.run_degraded(
                state=current_state,
                observation=observation,
                previous_lca_result=prev_calibrated,
                fallback_reason="互校循环超时",
            )

        # 填充上一轮的 causal_effect（基于本次 state 变化）
        if prev_calibrated is not None and prev_calibrated.actual_outcome is not None:
            state_delta = float(
                new_state.K.mastery_prob - current_state.K.mastery_prob
            )
            from ..lca.l4_optimization.attribution import CausalEffect
            prev_calibrated.causal_effect = CausalEffect(
                intervention_type=prev_calibrated.intervention.intervention_type.value,
                student_id=sid,
                state_delta=state_delta,
                estimated_ate=state_delta,  # M2 W4 简化
                confidence=min(1.0, len(self.intervention_history[sid]) / 30.0),
                n_samples=len(self.intervention_history[sid]),
            )

            # v0.69.0-b: 计算 dual_agent_confidence (LinUCB θ@x 预测答对概率)
            #   - 用 calibrated.intervention (当前轮 N+1 选出的) 反查 arm
            #   - 用 current_state (即 prev_state, 轮 N 之后的) 构建 context
            #   - 冷启动期: 走 _estimate_gain fallback (source="estimate_gain_fallback")
            #   - 非冷启动期: 走 LinUCB θ@x (source="linucb")
            #   写入 calibrated.metadata (当前轮), _write_calibration_log 读取落盘
            #   校准逻辑: calibration_log(round=N+1).dual_agent_confidence
            #             vs calibration_log(round=N+1).actual_outcome (轮 N+2 填回)
            #             跟 V1 (expected_gain) 同模式, compute_h3_ece V3 优先逻辑可校准
            dual_agent_confidence, dual_agent_confidence_source = (
                self._compute_dual_agent_confidence(
                    sid=sid,
                    intervention=calibrated.intervention,
                    belief_state=current_state,
                )
            )
            calibrated.metadata["dual_agent_confidence"] = dual_agent_confidence
            calibrated.metadata["dual_agent_confidence_source"] = (
                dual_agent_confidence_source
            )

            # v0.69.0-b: LinUCB update reward 改 actual_outcome (B4 方案)
            #   之前: reward = state_delta (mastery 增长预测)
            #   现在: reward = actual_outcome (partial credit 0-1, 答对概率直接度量)
            #   设计: dual_agent 内部 LCAEngine 是 v0.62.0-A 独立实例, 改 reward 不污染教学 LCA
            #   state_delta 仍传 (attribution 用, 不变)
            try:
                self.lca_engine.update(
                    student_id=sid,
                    intervention=prev_calibrated.intervention,
                    new_state=new_state,
                    state_delta=state_delta,
                    reward=prev_calibrated.actual_outcome,
                )
            except Exception:
                _log.warning(
                    "dual_agent LCAEngine.update reward=actual_outcome 失败 (sid=%s), "
                    "fallback state_delta=%s",
                    sid, state_delta, exc_info=True,
                )
                # 防御性自检 [6]: 失败不污染 in-memory, 走老路径 (state_delta reward)
                #   跟 v0.68.0 行为一致, 但 dual_agent_confidence 字段已写入 metadata
                self.lca_engine.update(
                    student_id=sid,
                    intervention=prev_calibrated.intervention,
                    new_state=new_state,
                    state_delta=state_delta,
                )

        # Step 4: 抗幻觉检查（warn-only，不阻断）
        self._anti_hallucination_checks(cta_output, calibrated)

        # Step 5: 处理信念质疑（resolve）
        if belief_challenge_to_record is not None:
            self._resolve_belief_challenge(
                sid, belief_challenge_to_record, observation, current_state, new_state,
            )

        # Step 6: 更新状态 + 历史
        self.state[sid] = new_state
        self.intervention_history[sid].append(calibrated)
        self.state_trajectory[sid].append(new_state)
        # 限制 trajectory 长度
        maxlen = 100
        if len(self.state_trajectory[sid]) > maxlen:
            self.state_trajectory[sid] = self.state_trajectory[sid][-maxlen:]
        self.calibration_round[sid] += 1
        calibrated.calibration_round = self.calibration_round[sid]

        # Step 7: 累计连续无效次数 (基于上一轮的 actual_outcome, 不是当前 calibrated)
        # v0.59.0 修: 原代码检查 calibrated.actual_outcome (刚创建, 还是 None), 应该检查 prev
        if prev_calibrated is not None and prev_calibrated.actual_outcome is not None:
            if prev_calibrated.actual_outcome < 0.3:
                self._consecutive_ineffective[sid] += 1
            else:
                self._consecutive_ineffective[sid] = 0

        return calibrated

    # ---------------------------------------------------------------
    # v0.69.0-b: dual_agent_confidence 计算 (B4 方案)
    # ---------------------------------------------------------------

    def _compute_dual_agent_confidence(
        self,
        sid: str,
        intervention,
        belief_state: BeliefState,
    ) -> tuple:
        """计算 dual_agent_confidence (LinUCB θ@x 预测答对概率).

        v0.69.0 PRD §3.1.2 + §7.2 重新设计:
          - dual_agent 内部 LCAEngine 是 v0.62.0-A 独立实例, 不持久化 bandit 数据
          - 冷启动期 (arm_pull_counts.sum() < cold_start_threshold): 走 _estimate_gain fallback
          - 非冷启动期: 走 LinUCB θ@x (排除 confidence_bound, 只取 expected_reward)
          - 失败兜底: 走 intervention.expected_gain (跟 V1 一致)

        Args:
            sid: 学生 ID
            intervention: 选中的干预 (用于反查 arm 索引)
            belief_state: 当前 BeliefState (用于构建 LinUCB context)

        Returns:
            (dual_agent_confidence, source_str) tuple
              - dual_agent_confidence: float [0, 1] 答对概率预测
              - source_str: "linucb" 或 "estimate_gain_fallback"

        防御性自检 [1]: 任何失败都 fallback, 不 raise, 不 silent pass (有 _log.debug)
        防御性自检 [6]: 失败不污染 in-memory state
        """
        # 默认 fallback: intervention.expected_gain (跟 V1 一致)
        fallback_value = float(
            getattr(intervention, "expected_gain", 0.5) or 0.5
        )
        fallback_source = "estimate_gain_fallback"

        try:
            # 拿 LinUCB bandit 实例 (dual_agent 内部 LCAEngine.bandits)
            bandit = self.lca_engine.bandits.get(sid)
            if bandit is None:
                # bandit 未初始化 -> 冷启动, 走 fallback
                return fallback_value, fallback_source

            # 冷启动判定 (调用 LCAEngine._is_linucb_cold_start)
            if self.lca_engine._is_linucb_cold_start(sid):
                # 冷启动期: 走 _estimate_gain fallback
                #   跟 v0.68.0 之前 V1 expected_gain 数值上接近, 但写入字段不同
                try:
                    est_gain = self.lca_engine._estimate_gain(
                        intervention, belief_state
                    )
                    return float(est_gain), fallback_source
                except Exception:
                    _log.debug(
                        "_estimate_gain fallback 失败 (sid=%s), 用 expected_gain",
                        sid, exc_info=True,
                    )
                    return fallback_value, fallback_source

            # 非冷启动期: LinUCB θ@x 预测
            #   拿 chosen arm 的 θ_a = A_a^{-1} b_a
            #   context = _build_context(belief_state)
            #   expected_reward = θ_a @ x
            import numpy as np

            context = bandit._build_context(belief_state)
            arm_idx = bandit._lookup_arm(intervention)
            if arm_idx is None:
                # arm 反查失败 (e.g. 新会话, intervention 不在 _arm_fingerprints 里)
                _log.debug(
                    "LinUCB arm_idx 反查失败 (sid=%s, intervention=%s), fallback",
                    sid, intervention.intervention_id,
                )
                return fallback_value, fallback_source

            # θ_a = A_a^{-1} b_a
            try:
                A_inv = np.linalg.inv(bandit.bandit.A[arm_idx])
            except np.linalg.LinAlgError:
                _log.debug(
                    "LinUCB A matrix 奇异 (sid=%s, arm=%d), fallback",
                    sid, arm_idx,
                )
                return fallback_value, fallback_source
            theta = A_inv @ bandit.bandit.b[arm_idx]
            expected_reward = float(theta @ context)

            # 截断到 [0, 1] (LinUCB 预测可能轻微超出, 因为 theta @ x 没约束)
            expected_reward = max(0.0, min(1.0, expected_reward))
            return expected_reward, "linucb"

        except Exception:
            _log.warning(
                "dual_agent_confidence 计算失败 (sid=%s), fallback expected_gain=%s",
                sid, fallback_value, exc_info=True,
            )
            return fallback_value, fallback_source

    # ---------------------------------------------------------------
    # 特殊模式 + 抗幻觉 + 质疑处理
    # ---------------------------------------------------------------

    def _check_special_modes(self, sid: str, observation) -> Optional[CalibratedLCAResult]:
        """检查是否应触发特殊模式（策略质疑 / 元反思）.

        策略质疑触发时：
          1. 先 CTA.update（让 CTA 学习当前 observation）
          2. 在 LinUCB 端惩罚当前 arm
          3. LCA 重新选择干预
          4. 追加 history + trajectory（用 update 后的新 state）
        """
        if self.strategy_challenge.detect_ineffective_intervention(
            intervention_history=self.intervention_history[sid],
            state_trajectory=self.state_trajectory[sid],
        ):
            # Step A: CTA 先学习本次 observation（关键——否则 mastery 不增长）
            current_state = self.state[sid]
            updated_state = self.cta_engine.update(
                state=current_state,
                observation=observation,
                lca_result=self.intervention_history[sid][-1] if self.intervention_history[sid] else None,
            )
            self.state[sid] = updated_state

            # Step B: 触发策略质疑 + 重新选择
            challenge = self.strategy_challenge.challenge_lca(
                student_id=sid,
                intervention_history=self.intervention_history[sid],
                calibration_round=self.calibration_round[sid],
            )
            self.strategy_challenges[sid].append(challenge)

            # Step C: LCA 重新选择（在 LinUCB 中惩罚上一 arm）
            from ..lca.orchestrator import CTAInput
            cta_input = CTAInput(student_id=sid, belief_state=updated_state)
            new_lca_result = self.strategy_challenge.lca_revise_policy(
                challenge, updated_state, cta_input,
            )

            # Step D: 构造 calibrated + 追加 history/trajectory
            self.calibration_round[sid] += 1
            calibrated = CalibratedLCAResult.from_lca_result(
                new_lca_result,
                calibration_round=self.calibration_round[sid],
            )
            calibrated.metadata["strategy_challenge_triggered"] = True
            self.intervention_history[sid].append(calibrated)
            self.state_trajectory[sid].append(updated_state)
            # v0.59.0 修: 跟正常路径对齐, trajectory 也限 100 (CLAUDE.md [7])
            maxlen = 100
            if len(self.state_trajectory[sid]) > maxlen:
                self.state_trajectory[sid] = self.state_trajectory[sid][-maxlen:]
            return calibrated

        # 元反思（Phase 5+ 占位：暂不实现）
        return None

    def _mode_belief_challenge(
        self,
        cta_output_preview: CTAOutput,
        observation,
        challenge_dim: str,
    ) -> BeliefChallenge:
        """信念质疑触发（无状态操作）."""
        from .modes import BeliefChallengeMode
        mode = BeliefChallengeMode(self.cta_engine)
        return mode.trigger_challenge(
            cta_output_preview, observation, challenge_dim,
        )

    def _resolve_belief_challenge(
        self,
        sid: str,
        challenge: BeliefChallenge,
        observation,
        prev_state: BeliefState,
        new_state: BeliefState,
    ) -> None:
        """信念质疑解决——记录 history."""
        from .modes import BeliefChallengeMode
        mode = BeliefChallengeMode(self.cta_engine)
        # 构造一个新的 CTAOutput 让 resolve_challenge 写入 history
        cta_output = CTAOutput.from_belief_state(new_state)
        mode.resolve_challenge(cta_output, challenge, observation, prev_state, new_state)
        # 更新挑战历史到 orch
        if cta_output.challenge_history:
            last_entry = cta_output.challenge_history[-1]
            self.warnings.setdefault(sid, []).append(f"belief_challenge: {last_entry}")

    def _anti_hallucination_checks(
        self,
        cta_output: CTAOutput,
        calibrated: CalibratedLCAResult,
    ) -> None:
        """抗幻觉检查（warn-only）."""
        sid = cta_output.student_id

        # 检查 1：信念分布合理性
        is_well, issues = self.belief_check.is_well_formed(cta_output.belief_state)
        if not is_well:
            self.warnings[sid].extend([f"belief_check: {i}" for i in issues[:3]])

        # 检查 2：实验设计合理性
        is_valid, design_issues = self.experiment_validator.validate_intervention(
            calibrated.intervention,
        )
        if not is_valid:
            self.warnings[sid].extend([f"experiment_design: {i}" for i in design_issues[:3]])

        # 检查 3：人工审核触发
        should_review, request = self.human_review.should_request_human_review(
            cta_output,
            consecutive_ineffective=self._consecutive_ineffective.get(sid, 0),
        )
        if should_review and request is not None:
            self.human_review.queue_review(request)

    # ---------------------------------------------------------------
    # 调试 / 教师后台接口
    # ---------------------------------------------------------------

    def get_warnings(self, sid: str) -> List[str]:
        return list(self.warnings.get(sid, []))

    def get_belief_challenges(self, sid: str) -> List[BeliefChallenge]:
        return list(self.belief_challenges.get(sid, []))

    def get_strategy_challenges(self, sid: str) -> List[StrategyChallenge]:
        return list(self.strategy_challenges.get(sid, []))

    def get_history(self, sid: str) -> List[CalibratedLCAResult]:
        return list(self.intervention_history.get(sid, []))

    def get_state_trajectory(self, sid: str) -> List[BeliefState]:
        return list(self.state_trajectory.get(sid, []))

    # ---------------------------------------------------------------
    # 持久化接口 (v0.61.0 dual_agent 持久化用)
    # ---------------------------------------------------------------

    def dump_state(self, sid: str) -> Optional[Dict[str, Any]]:
        """导出 dual_agent 内部 state (8 字段全打包, 跟 DualAgentStore 一一对应).

        CLAUDE.md 防御性自检 [5]: 8 字段必须一次全 dump, 避免分批漏字段.
        CLAUDE.md 防御性自检 [6]: dump 失败不能污染 in-memory (这里只读, 不改).

        Returns:
            8 字段 dict (state_snapshot / intervention_history / state_trajectory /
                         calibration_round / warnings / belief_challenges /
                         strategy_challenges / consecutive_ineffective),
            sid 未知时返回 None.
        """
        if sid not in self.state:
            return None
        return {
            "state_snapshot": self.state[sid].to_dict(),
            "intervention_history": [
                r.to_dict() for r in self.intervention_history[sid]
            ],
            "state_trajectory": [
                s.to_dict() for s in self.state_trajectory[sid]
            ],
            "calibration_round": int(self.calibration_round[sid]),
            "warnings": list(self.warnings[sid]),
            "belief_challenges": [
                c.to_dict() for c in self.belief_challenges[sid]
            ],
            "strategy_challenges": [
                c.to_dict() for c in self.strategy_challenges[sid]
            ],
            "consecutive_ineffective": int(self._consecutive_ineffective.get(sid, 0)),
        }

    def load_state(self, sid: str, snapshot: Dict[str, Any]) -> None:
        """从 dump 恢复 dual_agent 内部 state (8 字段全恢复).

        CLAUDE.md 防御性自检 [5]: 8 字段必须一次全 load, 缺字段 fallback 0/[].
        CLAUDE.md 防御性自检 [6]: load 失败不能污染 in-memory (caller 负责 try/except).

        跟 v0.57.0 LCAEngine.load_state 同样模式: 字段缺失用 default 兜底.
        """
        from ..cta.belief_state import BeliefState
        from .protocol.messages import BeliefChallenge, StrategyChallenge

        self.state[sid] = BeliefState.from_dict(snapshot.get("state_snapshot", {}))
        # 确保 student_id 一致 (snapshot 是从 sid dump 出来的, 但保险起见)
        self.state[sid].student_id = sid

        self.intervention_history[sid] = [
            CalibratedLCAResult.from_dict(r)
            for r in snapshot.get("intervention_history", [])
        ]
        self.state_trajectory[sid] = [
            BeliefState.from_dict(s) for s in snapshot.get("state_trajectory", [])
        ]
        self.calibration_round[sid] = int(snapshot.get("calibration_round", 0))
        self.warnings[sid] = list(snapshot.get("warnings", []))
        self.belief_challenges[sid] = [
            BeliefChallenge.from_dict(c) for c in snapshot.get("belief_challenges", [])
        ]
        self.strategy_challenges[sid] = [
            StrategyChallenge.from_dict(c) for c in snapshot.get("strategy_challenges", [])
        ]
        self._consecutive_ineffective[sid] = int(snapshot.get("consecutive_ineffective", 0))

    def has_state(self, sid: str) -> bool:
        """检查 orch 内部是否有该 sid 的 state (跟 LCAEngine._get_bandit 同样模式)."""
        return sid in self.state

    def ensure_state_loaded(self, sid: str, snapshot: Optional[Dict[str, Any]]) -> None:
        """确保 sid 的 state 已加载 (v0.61.0 启动 lazy init 用).

        行为:
          - 已有 state (in-memory) → 跳过
          - 无 state 但有 snapshot (from DB) → load_state
          - 无 state 且无 snapshot → 冷启动 (create_initial_state, 跟 v0.60.0 同样行为)

        防御性自检 [1]: load 失败必须 warning, 不能 silent pass.
        """
        if sid in self.state:
            return
        if snapshot is not None:
            try:
                self.load_state(sid, snapshot)
                _log.info(
                    "dual_agent state loaded from DB (sid=%s, calibration_round=%d)",
                    sid, self.calibration_round.get(sid, 0),
                )
            except Exception:
                _log.warning(
                    "dual_agent.load_state 失败 (sid=%s), 回退冷启动",
                    sid, exc_info=True,
                )
                # 兜底: 跟没 snapshot 一样冷启动
                self._init_fresh_state(sid)
        else:
            self._init_fresh_state(sid)

    def _init_fresh_state(self, sid: str) -> None:
        """冷启动 (跟 v0.60.0 同样行为, 抽出函数)."""
        self.state[sid] = self.cta_engine.create_initial_state(sid)
        self.intervention_history[sid] = []
        self.state_trajectory[sid] = []
        self.calibration_round[sid] = 0
        self.warnings[sid] = []
        self.belief_challenges[sid] = []
        self.strategy_challenges[sid] = []
        self._consecutive_ineffective[sid] = 0


__all__ = ["DualAgentOrchestrator", "DualAgentConfig"]