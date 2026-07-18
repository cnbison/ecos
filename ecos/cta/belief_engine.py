"""CTA 信念引擎（编排器）.

对应 research/10-engineering/01-cta-belief-engine.md §2.3.

M2 W1 范围：
  ✅ L1 BKTEvolutionLayer（已实现 l1_evolution.py）
  ✅ L2 BiFactorMIRT5D MAP 估计（已实现 l2_mirt.py）
  ✅ LLM Critic（M2 W3 集成：感知层 + Misconception 检测）
  🚧 L0 POMDP 框架（Phase 4+ 实现 EKF）
  🚧 L3 CD-CAT 选题（Phase 4+ 实现 PWKL）
  🚧 L4 因果归因（Phase 4+ 实现 A/B Test）
  ✅ C 维度 misconception 折扣（M2 W3 通过 ConfidenceDimensionState 实现）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

import numpy as np

from .belief_state import (
    BeliefState,
    BloomLevel,
    BloomProfileState,
    ConfidenceDimensionState,
    DimensionState,
    LearningDNAState,
    MisconceptionHit,
    StateSnapshot,
    TrajectoryState,
)
from .l1_evolution import BKTEvolutionLayer, EvolutionConfig
from .l2_mirt import BiFactorMIRT5D, MIRTConfig, MIRTItemParams
from .tc_detector import TCStateDetector

if TYPE_CHECKING:
    from ...llm_client import ECOSLLMClient
    from .llm_critic import MisconceptionDetector, PerceptionCritic


@dataclass
class Observation:
    """单次学生观测（M2 W1 结构化版）.

    Attributes:
        skill_id: 涉及的知识点 ID（用于 BKT）
        problem_id: 题目 ID（用于 MIRT）
        correct: 作答是否正确
        bloom_level: 题目对应的 Bloom 层级（用于 BloomProfile 更新）
        explanation_text: 学生解释文本（LLM Critic 输入；M2 W3 解析）
        problem_text: 题目原文（供 LLM Critic 感知层使用）
        correct_answer: 正确答案（供 LLM Critic 感知层使用）
        timestamp: 观测时间
        response_time_sec: 答题耗时（秒；M2 W1 不使用）
    """

    skill_id: str
    problem_id: str
    correct: bool
    bloom_level: BloomLevel = BloomLevel.APPLY
    explanation_text: str = ""
    problem_text: str = ""
    correct_answer: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    response_time_sec: float = 0.0


@dataclass
class LCAResult:
    """LCA 干预结果（用于 L4 因果归因；M2 W1 占位）.

    Attributes:
        intervention_type: 干预类型 ID
        expected_gain: 预期增益
        actual_outcome: 实际观测到的掌握度变化（None 表示未观测）
    """

    intervention_type: str = "review"
    expected_gain: float = 0.0
    actual_outcome: Optional[float] = None


@dataclass
class BeliefEngineConfig:
    """BeliefEngine 聚合配置."""

    evolution_config: EvolutionConfig = field(default_factory=EvolutionConfig)
    mirt_config: MIRTConfig = field(default_factory=MIRTConfig)
    bloom_update_step: float = 0.05
    trajectory_maxlen: int = 100
    # ── W1 warm-up 窗口（W1 2026-07-17 落地，详见 discussions/2026-07-17-方向选择-A先C后.md）──
    warmup_questions: int = 5
    warmup_step: float = 0.1  # warm-up 期 Bloom 更新步长（更大，让学生感到进步）
    # ── W3 探针题机制（2026-07-17 落地）──
    probe_interval: int = 8  # 每 8-10 题穿插 1 道（无痕不计学习时长）
    probe_first_after_warmup: bool = True  # warm-up 结束后第 1 次探针何时插入


class BeliefEngine:
    """CTA 信念引擎（M2 W3 范围）.

    主入口:
        from ecos.llm_client import ECOSLLMClient
        client = ECOSLLMClient.from_env()
        engine = BeliefEngine(llm_client=client)
        state = engine.create_initial_state("student_001")
        state = engine.update(state, observation)

    LLM Critic 集成（M2 W3）：
        - 感知层（PerceptionCritic）：解析 explanation_text → Bloom 推断 + 知识点
        - Misconception 检测（MisconceptionDetector）：C 维度折扣
        - 解释层（ExplanationCritic）：由外部持有，BeliefEngine 不直接调用
    """

    def __init__(
        self,
        config: BeliefEngineConfig | None = None,
        llm_client: Optional["ECOSLLMClient"] = None,
    ) -> None:
        self.config = config or BeliefEngineConfig()
        self.llm_client = llm_client
        self.l1 = BKTEvolutionLayer(self.config.evolution_config)
        self.l2 = BiFactorMIRT5D(self.config.mirt_config)
        self.tc_detector = TCStateDetector()
        self._response_history: Dict[str, List[Tuple[str, int, BloomLevel]]] = {}

        # ── W1 warm-up 状态（W1 2026-07-17 落地）──
        # _warmup_count[student_id] = 已答题数（前 warmup_questions 题为 warm-up 期）
        self._warmup_count: Dict[str, int] = {}
        # _warmup_pool_cursor[student_id] = warm-up 覆盖性选题的轮询游标
        self._warmup_pool_cursor: Dict[str, int] = {}

        # ── W3 探针题状态机（2026-07-17 落地）──
        # _probe_due_in[student_id] = 距下一次探针题还剩几题
        #   - warm-up 期间探针题禁用（避免冷启动干扰）
        #   - 答完 warm-up 期后,初始化为 probe_interval（即再答 N 题才触发）
        #   - 触发后重置为 probe_interval
        self._probe_due_in: Dict[str, int] = {}
        self._probe_count: Dict[str, int] = {}  # 已插入的探针题数

        # LLM Critic（M2 W3，延迟初始化）
        self._perception_critic: Optional["PerceptionCritic"] = None
        self._misc_detector: Optional["MisconceptionDetector"] = None

    # ── W1 warm-up 状态机（W1 2026-07-17 新增）──

    def is_warmup(self, student_id: str) -> bool:
        """是否处于 warm-up 期（前 N 题）。"""
        return self._warmup_count.get(student_id, 0) < self.config.warmup_questions

    def warmup_remaining(self, student_id: str) -> int:
        """距离 warm-up 结束还剩几题。0 表示刚刚结束。"""
        n = self._warmup_count.get(student_id, 0)
        return max(0, self.config.warmup_questions - n)

    def warmup_progress(self, student_id: str) -> dict:
        """返回 warm-up 状态完整信息（供 API 层使用）。

        Returns:
            {
                "is_warmup": bool,
                "warmup_remaining": int,
                "warmup_total": int,
                "warmup_count": int,
            }
        """
        count = self._warmup_count.get(student_id, 0)
        return {
            "is_warmup": count < self.config.warmup_questions,
            "warmup_remaining": max(0, self.config.warmup_questions - count),
            "warmup_total": self.config.warmup_questions,
            "warmup_count": count,
        }

    # ── W3 探针题状态机 API（W3 2026-07-17 新增）──

    def should_probe_now(self, student_id: str) -> bool:
        """下次选题是否应插入探针题。

        条件:
          - 不在 warm-up 期
          - _probe_due_in[student_id] == 0（已经答了 N 题,下次该插入探针）
        """
        if self.is_warmup(student_id):
            return False
        return self._probe_due_in.get(student_id, 0) == 0

    def consume_probe(self, student_id: str) -> None:
        """标记"已插入探针题",重置 _probe_due_in 为 probe_interval。

        调用时机：API 层在 /api/question 中检测 should_probe_now=True 后,
        走 _select_probe_question 路径,然后调用本方法重置状态机。
        """
        self._probe_count[student_id] = self._probe_count.get(student_id, 0) + 1
        self._probe_due_in[student_id] = self.config.probe_interval

    def probe_progress(self, student_id: str) -> dict:
        """返回探针题状态完整信息（供 API 层使用）。

        Returns:
            {
                "should_probe": bool,
                "probe_due_in": int,
                "probe_interval": int,
                "probe_count": int,
            }
        """
        return {
            "should_probe": self.should_probe_now(student_id),
            "probe_due_in": self._probe_due_in.get(student_id, self.config.probe_interval),
            "probe_interval": self.config.probe_interval,
            "probe_count": self._probe_count.get(student_id, 0),
        }

    @property
    def perception_critic(self) -> "PerceptionCritic":
        if self._perception_critic is None:
            from .llm_critic import PerceptionCritic
            self._perception_critic = PerceptionCritic(self.llm_client)
        return self._perception_critic

    @property
    def misc_detector(self) -> "MisconceptionDetector":
        if self._misc_detector is None:
            from .llm_critic import MisconceptionDetector
            self._misc_detector = MisconceptionDetector(self.llm_client)
        return self._misc_detector

    def create_initial_state(self, student_id: str) -> BeliefState:
        """创建新学生的初始 BeliefState."""
        state = BeliefState(student_id=student_id)
        state.theta_mean = np.zeros(5)
        state.theta_cov = np.eye(5)
        state.bloom_profile = BloomProfileState()
        state.bloom_profile.update_dominant()
        state.learning_dna = LearningDNAState()
        state.trajectory = TrajectoryState()
        state.overall_confidence = 0.0
        state.last_updated = datetime.now()
        # C 维度确保是 ConfidenceDimensionState（含 misconception_hits）
        if not isinstance(state.C, ConfidenceDimensionState):
            state.C = ConfidenceDimensionState(dimension="C")
        return state

    def update(
        self,
        state: BeliefState,
        observation: Observation,
        lca_result: Optional[LCAResult] = None,
    ) -> BeliefState:
        """主更新入口——每次新观测后调用.

        M2 W3 新增 Step 5-6：LLM Critic 感知层 + Misconception 检测。

        Args:
            state: 当前 BeliefState
            observation: 结构化观测
            lca_result: LCA 干预结果（Phase 4+ 使用）

        Returns:
            更新后的 BeliefState
        """
        student_id = state.student_id
        skill_id = observation.skill_id
        problem_id = observation.problem_id
        correct = observation.correct
        bloom_level = observation.bloom_level

        # ── W1 warm-up 计数累加（W1 2026-07-17 新增，在 Step 1 之前）──
        self._warmup_count[student_id] = self._warmup_count.get(student_id, 0) + 1
        in_warmup = self.is_warmup(student_id)

        # ── W3 探针题状态机触发（W3 2026-07-17 新增）──
        #   - warm-up 期间不触发探针（避免冷启动干扰）
        #   - 刚出 warm-up 期时初始化 _probe_due_in = probe_interval
        #   - 每次 update() 后 _probe_due_in -= 1
        #   - 当 _probe_due_in == 0 时,下次选题应插入探针题
        was_warmup = (
            self._warmup_count[student_id] - 1 < self.config.warmup_questions
        )  # 上一题是否还在 warm-up
        just_exited_warmup = was_warmup and not in_warmup
        if just_exited_warmup and self.config.probe_first_after_warmup:
            # 刚出 warm-up 期,初始化 _probe_due_in
            self._probe_due_in[student_id] = self.config.probe_interval
        elif student_id not in self._probe_due_in and not in_warmup:
            # 异常情况:不在 warm-up 但 _probe_due_in 未初始化（DB 恢复场景）
            self._probe_due_in[student_id] = self.config.probe_interval

        if student_id in self._probe_due_in:
            self._probe_due_in[student_id] = max(0, self._probe_due_in[student_id] - 1)

        # ── W1 warm-up 期 Bloom 步长切换（更大，让学生感到"在进步"）──
        step = self.config.warmup_step if in_warmup else self.config.bloom_update_step

        # Step 1: L1 BKT 更新
        self.l1.update(skill_id, correct)

        # Step 2: 累积响应历史（用于 MIRT 估计）
        history = self._response_history.setdefault(student_id, [])
        history.append((problem_id, int(correct), bloom_level))
        if len(history) > 100:
            self._response_history[student_id] = history[-100:]
            history = self._response_history[student_id]

        # Step 3: L2 MIRT MAP 估计
        if len(history) >= 2:
            problem_ids = [h[0] for h in history]
            responses = np.array([h[1] for h in history], dtype=float)
            theta_hat, theta_cov = self.l2.estimate_theta(responses, problem_ids)
            state.theta_mean = theta_hat
            state.theta_cov = theta_cov
            for i, dim_char in enumerate(["K", "P", "S", "C", "X"]):
                dim_state = getattr(state, dim_char)
                dim_state.theta = float(theta_hat[i])
                dim_state.se = float(np.sqrt(max(theta_cov[i, i], 1e-6)))
                dim_state.mastery_prob = float(1.0 / (1.0 + np.exp(-theta_hat[i])))
                dim_state.mastered = dim_state.mastery_prob >= 0.5
                dim_state.confidence = min(1.0, len(history) / 30.0)
                dim_state.evidence_ids.append(len(history))
                dim_state.last_updated = observation.timestamp

        # Step 4: BloomProfile 更新（基于题目预设 bloom_level）
        bloom_name = bloom_level.name.lower()
        current_prob = getattr(state.bloom_profile, bloom_name)
        if correct:
            new_prob = min(1.0, current_prob + step)
        else:
            new_prob = max(0.0, current_prob - step * 0.5)
        setattr(state.bloom_profile, bloom_name, new_prob)
        state.bloom_profile.update_dominant()
        state.bloom_profile.confidence = min(1.0, len(history) / 30.0)
        state.bloom_profile.evidence_ids.append(len(history))

        # Step 5: LLM Critic 感知层（M2 W3）——explanation_text 非空时调用
        if observation.explanation_text and self.llm_client is not None:
            self._llm_critic_perception(state, observation)

        # Step 6: LLM Critic Misconception 检测（M2 W3）——C 维度折扣
        if observation.explanation_text and self.llm_client is not None:
            self._llm_critic_misconception(state, observation)

        # Step 7: TC 状态检测（挂在 C 维度上）
        has_misc = bool(state.C.misconception_hits)
        current_tc = state.C.tc_states.get(skill_id, None)
        updated_tc = self.tc_detector.detect(
            topic=skill_id,
            correct=correct,
            bloom_level=bloom_level,
            current_tc_state=current_tc,
            has_active_misc=has_misc,
        )
        state.C.tc_states[skill_id] = updated_tc

        # Step 8: 整体置信度（W5+ 改进：直接用 history 长度算,不再依赖 dim.confidence 字段）
        # 旧公式:0.6 * c5d + 0.4 * bp.confidence,其中 c5d 和 bp.confidence 都是
        #   min(1.0, len(history) / 30.0) 的派生值
        # 新公式:ov = min(1.0, len(history) / 30.0) — 等价但更可靠
        # 优势:不需要存 dim.confidence 5 维,重启后从 response_history 长度直接算
        state.overall_confidence = min(1.0, len(history) / 30.0)

        # Step 9: 追加轨迹快照
        state.trajectory.append(state.snapshot())
        if len(state.trajectory.snapshots) > self.config.trajectory_maxlen:
            state.trajectory.snapshots = state.trajectory.snapshots[-self.config.trajectory_maxlen:]

        # Step 10: 时间戳
        state.last_updated = observation.timestamp

        return state

    def _llm_critic_perception(
        self,
        state: BeliefState,
        observation: Observation,
    ) -> None:
        """Step 5：LLM Critic 感知层——更新 BloomProfile（感知推断的 bloom_level）."""
        try:
            p_out = self.perception_critic.perceive(
                problem=observation.problem_text or observation.skill_id,
                correct_answer=observation.correct_answer or "",
                student_correctness=observation.correct,
                student_explanation=observation.explanation_text,
            )
        except Exception:
            # LLM 调用失败时跳过，不阻塞主流程
            return

        # Bloom 推断：仅当推断层高于当前 dominant_layer 时才采纳（避免过度更新）
        if p_out.bloom_level is not None:
            inferred_val = p_out.bloom_level.value
            current_dom_val = state.bloom_profile.dominant_layer.value
            if inferred_val > current_dom_val:
                target_name = p_out.bloom_level.name.lower()
                current_target_prob = getattr(state.bloom_profile, target_name)
                setattr(
                    state.bloom_profile,
                    target_name,
                    min(1.0, current_target_prob + self.config.bloom_update_step),
                )
                state.bloom_profile.update_dominant()

        # 更新 C 维度的 explanation_quality（感知质量影响置信度）
        state.C.confidence = state.C.confidence * 0.7 + p_out.explanation_quality * 0.3

    def _llm_critic_misconception(
        self,
        state: BeliefState,
        observation: Observation,
    ) -> None:
        """Step 6：LLM Critic Misconception 检测——C 维度折扣."""
        try:
            misc_hit = self.misc_detector.detect_with_hits(
                student_explanation=observation.explanation_text,
                problem=observation.problem_text or observation.skill_id,
                trigger_problem_id=observation.problem_id,
            )
        except Exception:
            # LLM 调用失败时跳过，不阻塞主流程
            return

        if misc_hit is None:
            return

        # 记录 misconception 命中
        state.C.misconception_hits.append(misc_hit)
        state.C.illusory_confidence_flag = True

        # 折扣因子：confidence 越高折扣越大（最多折扣 30%）
        discount = 1.0 - min(misc_hit.confidence * 0.3, 0.3)
        state.C.discount_factor = min(state.C.discount_factor * discount, 1.0)

        # 折扣后修正 mastery_prob（伪置信标记）
        state.C.mastery_prob = state.C.mastery_prob * state.C.discount_factor
        state.C.mastered = state.C.mastery_prob >= 0.5

        # evidence 记录
        state.C.evidence_ids.append(len(observation.explanation_text))

    def get_bkt_mastery(self, skill_id: str) -> float:
        """便捷接口：获取 BKT 当前掌握概率."""
        return self.l1.get_mastery(skill_id)

    def get_theta(self, state: BeliefState) -> np.ndarray:
        """便捷接口：获取当前 5D θ."""
        return state.theta_vector()

    def select_next_problem(self, state: BeliefState) -> Optional[str]:
        """L3 CD-CAT 选下一题（M2 W1 占位；Phase 4+ 实现 PWKL）."""
        return None

    def reset_student(self, student_id: str) -> None:
        """重置某学生的累积历史."""
        if student_id in self._response_history:
            del self._response_history[student_id]
        # W1 warm-up 状态一并重置
        self._warmup_count.pop(student_id, None)
        self._warmup_pool_cursor.pop(student_id, None)
        # W3 探针题状态一并重置
        self._probe_due_in.pop(student_id, None)
        self._probe_count.pop(student_id, None)
