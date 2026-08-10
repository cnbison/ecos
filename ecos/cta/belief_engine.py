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

v0.80.0-b: 4-layer split
  - InferenceEngine.run() produces InferenceResult (NO state mutation)
  - BeliefUpdator.apply() is sole mutation site (calls StateEngine.commit)
  - update() is pure orchestration: build ctx -> run inference -> apply mutations
  - _llm_critic_perception / _llm_critic_misconception moved to InferenceEngine
  - warmup/probe state machine + response_history accumulation still inline (extract v0.80.0-c)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

logger = logging.getLogger(__name__)

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
from .belief_updater import BeliefUpdator
from .inference_engine import InferenceEngine, ObservationContext
from .l1_evolution import BKTEvolutionLayer, EvolutionConfig
from .l2_mirt import BiFactorMIRT5D, MIRTConfig, MIRTItemParams
from .state_engine import StateEngine, get_default_engine
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
        correct: 作答是否正确（v0.54.0 派生自 score >= 0.6, 兼容老调用方传 bool）
        score: v0.54.0 partial credit 评分 0.0-1.0 (1.0=完全对, 0.0=完全错, 0.7=70%对)
        bloom_level: 题目对应的 Bloom 层级（用于 BloomProfile 更新）
        explanation_text: 学生解释文本（LLM Critic 输入；M2 W3 解析）
        problem_text: 题目原文（供 LLM Critic 感知层使用）
        correct_answer: 正确答案（供 LLM Critic 感知层使用）
        timestamp: 观测时间
        response_time_sec: 答题耗时（秒；M2 W1 不使用）
    """

    skill_id: str
    problem_id: str
    correct: bool = False  # 兼容老调用: 不传 score 时按 bool
    score: float = 0.0  # v0.54.0 partial credit, 0.0-1.0, 不传时 0.0
    bloom_level: BloomLevel = BloomLevel.APPLY
    explanation_text: str = ""
    problem_text: str = ""
    correct_answer: str = ""
    user_answer: str = ""  # v0.49.2: 学生提交的原始答案(给答题历史详情页用)
    # v0.52.2: AI 评判的具体 reasoning (Bisen 反馈 2026-07-22 partial credit 缺失,
    #   短期先存 reasoning, Phase 5 partial credit 训练用历史数据)
    ai_reasoning: str = ""
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
    # v0.47.5: 100 -> 500,配合 API / DB 持久化 last_n(500) 一起放大
    # Bisen 反馈"成长轨迹应该按实际数量显示",12 道题应该显示 12 条
    trajectory_maxlen: int = 500
    # ── W1 warm-up 窗口（W1 2026-07-17 落地，详见 discussions/2026-07-17-方向选择-A先C后.md）──
    warmup_questions: int = 5
    warmup_step: float = 0.1  # warm-up 期 Bloom 更新步长（更大，让学生感到进步）
    # ── W3 探针题机制（2026-07-17 落地）──
    probe_interval: int = 8  # 每 8-10 题穿插 1 道（无痕不计学习时长）
    probe_first_after_warmup: bool = True  # warm-up 结束后第 1 次探针何时插入


class BeliefEngine:
    """CTA 信念引擎（M2 W3 范围）.

    v0.80.0-b: facade over 4 layers (ObservationEngine + FeatureExtractor in v0.80.0-c).
    Currently orchestrates InferenceEngine + BeliefUpdator directly.

    主入口:
        from ecos.llm_client import ECOSLLMClient
        client = ECOSLLMClient.from_env()
        engine = BeliefEngine(llm_client=client)
        state = engine.create_initial_state("student_001")
        state = engine.update(state, observation)

    LLM Critic 集成（M2 W3, v0.80.0-b 移到 InferenceEngine）：
        - 感知层（PerceptionCritic）：解析 explanation_text -> Bloom 推断 + 知识点
        - Misconception 检测（MisconceptionDetector）：C 维度折扣
        - 解释层（ExplanationCritic）：由外部持有，BeliefEngine 不直接调用
    """

    def __init__(
        self,
        config: BeliefEngineConfig | None = None,
        llm_client: Optional["ECOSLLMClient"] = None,
        # v0.52.0: 注入 misconception 库(BUG 2.1 修复)
        #   之前 _llm_critic_misconception 调 detect_with_hits() 没传 library_str,
        #   fallback 到 detector 默认的 K12 通用数学库 M1-M30
        #   但 belief.py 实际想用 Python misconception 库 M1-M8
        #   库 ID 错配导致 LLM 永远找不到 Python 相关的 M3 (off-by-one)
        #   修复: BeliefEngine 接受 library_str, 内部 detector 调时传它
        #         belief.py 构造 engine 时传 PYTHON_BASICS_MISCONCEPTION_LIBRARY_STR
        misconception_library_str: Optional[str] = None,
    ) -> None:
        self.config = config or BeliefEngineConfig()
        self.llm_client = llm_client
        self.misconception_library_str = misconception_library_str
        self.l1 = BKTEvolutionLayer(self.config.evolution_config)
        self.l2 = BiFactorMIRT5D(self.config.mirt_config)
        self.tc_detector = TCStateDetector()
        self._response_history: Dict[str, List[Dict[str, Any]]] = {}  # v0.49.2: 3-tuple -> dict（user_answer/timestamp）

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

        # v0.80.0-b: 4-layer split - InferenceEngine (pure) + BeliefUpdator (sole mutator)
        self._state_engine = get_default_engine()
        self._inference_engine = InferenceEngine(
            l1=self.l1,
            l2=self.l2,
            tc_detector=self.tc_detector,
            config=self.config,
            llm_client=llm_client,
            misconception_library_str=misconception_library_str,
        )
        self._belief_updater = BeliefUpdator(self._state_engine)

        # LLM Critic（M2 W3，延迟初始化）- kept on facade for backward compat (perception_critic / misc_detector properties)
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
        """v0.80.0-b: delegates to InferenceEngine (kept for backward compat)."""
        return self._inference_engine.perception_critic

    @property
    def misc_detector(self) -> "MisconceptionDetector":
        """v0.80.0-b: delegates to InferenceEngine (kept for backward compat)."""
        return self._inference_engine.misc_detector

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
        """主更新入口--每次新观测后调用.

        v0.80.0-b: 4-layer split
          - warmup/probe state machine + response_history accumulation: inline (extract v0.80.0-c)
          - InferenceEngine.run() produces InferenceResult (NO state mutation)
          - BeliefUpdator.apply() is sole mutation site (calls StateEngine.commit)

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
        # v0.54.0-d: partial credit score 派生 correct
        #   优先级: observation.score >= 0.6 > observation.correct (老调用兼容)
        #   老调用方只传 correct=True -> score=0.0 -> 派生 correct=False (强制用新 score)
        #   老代码改造: 应同时传 correct=True + score=1.0, 或只传 score=0.7
        score = observation.score if observation.score > 0 else (1.0 if observation.correct else 0.0)
        correct = score >= 0.6
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

        # Step 2: 累积响应历史（用于 MIRT 估计 + 答题历史详情页 v0.49.2）
        #   v0.49.2: 改 append dict（之前是 3-tuple,缺 user_answer/timestamp）
        #   v0.52.2: 加 ai_reasoning (Bisen 反馈 partial credit 缺失, 短期先存 AI reasoning
        #     留 Phase 5 partial credit 训练用历史数据)
        #   v0.54.0: 加 score 字段 (partial credit)
        #   向后兼容老数据: load 时 _get_or_create_student 会把 3-tuple 迁移成 dict
        #                  老 dict 没 score 字段, Step 3 MIRT 用 h.get("score", h.get("correct", 0)) 兜底
        history = self._response_history.setdefault(student_id, [])
        history.append({
            "problem_id": problem_id,
            "correct": int(correct),  # 派生自 score >= 0.6, 保留兼容
            "score": float(score),  # v0.54.0 partial credit
            "bloom_level": str(bloom_level.name if hasattr(bloom_level, "name") else bloom_level),
            "user_answer": observation.user_answer,
            "correct_answer": observation.correct_answer,
            "ai_reasoning": observation.ai_reasoning,
            "timestamp": observation.timestamp.isoformat() if observation.timestamp else None,
        })
        if len(history) > 100:
            self._response_history[student_id] = history[-100:]
            history = self._response_history[student_id]

        # v0.80.0-b: 4-layer split - build ObservationContext, run InferenceEngine, apply BeliefUpdator
        # InferenceEngine.run() produces InferenceResult (NO state mutation, pure inference)
        # BeliefUpdator.apply() is sole mutation site (calls StateEngine.commit for versioning)
        # Step 1 BKT + Step 3 MIRT + Step 4 Bloom + Step 5 LLM perception + Step 6 LLM misconception
        # + Step 7 TC + Step 8 overall_confidence + Step 9 trajectory + Step 10 last_updated
        # all move to InferenceEngine.run() + BeliefUpdator.apply()
        ctx = ObservationContext(
            student_id=student_id,
            skill_id=skill_id,
            problem_id=problem_id,
            score=score,
            correct=correct,
            bloom_level=bloom_level,
            in_warmup=in_warmup,
            just_exited_warmup=just_exited_warmup,
            bloom_step=step,
            observation=observation,
        )
        result = self._inference_engine.run(state, observation, ctx, history)
        self._belief_updater.apply(state, result, observation, history[-1] if history else None)

        return state

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
