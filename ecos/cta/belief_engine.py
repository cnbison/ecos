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
from .event_log import EventLog
from .feature_extractor import FeatureExtractor
from .inference_engine import InferenceEngine, ObservationContext
from .l1_evolution import BKTEvolutionLayer, EvolutionConfig
from .l2_mirt import BiFactorMIRT5D, MIRTConfig, MIRTItemParams
from .observation_engine import ObservationEngine
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

    # v0.81.0-b: EventLog payload serialization (mirrors BeliefState.to_dict pattern)
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for EventLog payload. BloomLevel -> name, datetime -> ISO."""
        return {
            "skill_id": self.skill_id,
            "problem_id": self.problem_id,
            "correct": self.correct,
            "score": float(self.score),
            "bloom_level": self.bloom_level.name,
            "explanation_text": self.explanation_text,
            "problem_text": self.problem_text,
            "correct_answer": self.correct_answer,
            "user_answer": self.user_answer,
            "ai_reasoning": self.ai_reasoning,
            "timestamp": self.timestamp.isoformat(),
            "response_time_sec": float(self.response_time_sec),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Observation":
        """Deserialize from dict (EventLog payload -> Observation). Mirrors to_dict."""
        # BloomLevel by name (e.g. "APPLY" -> BloomLevel.APPLY); default APPLY if missing/invalid
        bloom_name = d.get("bloom_level", "APPLY")
        try:
            bloom_level = BloomLevel[bloom_name]
        except (KeyError, ValueError):
            bloom_level = BloomLevel.APPLY
        # Timestamp parse with fallback to now()
        ts_str = d.get("timestamp")
        if ts_str:
            try:
                timestamp = datetime.fromisoformat(ts_str)
            except ValueError:
                timestamp = datetime.now()
        else:
            timestamp = datetime.now()
        return cls(
            skill_id=d.get("skill_id", ""),
            problem_id=d.get("problem_id", ""),
            correct=bool(d.get("correct", False)),
            score=float(d.get("score", 0.0)),
            bloom_level=bloom_level,
            explanation_text=d.get("explanation_text", ""),
            problem_text=d.get("problem_text", ""),
            correct_answer=d.get("correct_answer", ""),
            user_answer=d.get("user_answer", ""),
            ai_reasoning=d.get("ai_reasoning", ""),
            timestamp=timestamp,
            response_time_sec=float(d.get("response_time_sec", 0.0)),
        )


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
        # v0.81.0-b: EventLog injection (optional, for replay/simulation)
        #   production: web/api/belief.py attaches EventLog.from_sqlite(DB_PATH)
        #   tests: None (default) or EventLog.in_memory()
        event_log: Optional[EventLog] = None,
    ) -> None:
        self.config = config or BeliefEngineConfig()
        self.llm_client = llm_client
        self.misconception_library_str = misconception_library_str
        self.l1 = BKTEvolutionLayer(self.config.evolution_config)
        self.l2 = BiFactorMIRT5D(self.config.mirt_config)
        self.tc_detector = TCStateDetector()

        # v0.80.0-c: 4-layer split - ObservationEngine (warmup/probe) + FeatureExtractor (history)
        # Own _warmup_count / _warmup_pool_cursor / _probe_due_in / _probe_count / _response_history
        # moved out of BeliefEngine. __getattr__ forwards direct access for web/api/belief.py:189-191 compat.
        self._observation_engine = ObservationEngine()
        # v0.84.0-a: FeatureExtractor 接受 optional event_log (response_submitted 双写)
        self._feature_extractor = FeatureExtractor(event_log=event_log)

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
        # v0.81.0-b: BeliefUpdator now owns event_log (sole logging site)
        self._belief_updater = BeliefUpdator(self._state_engine, event_log)
        self._event_log = event_log  # keep ref for replay() / simulate() introspection

        # LLM Critic（M2 W3，延迟初始化）- kept on facade for backward compat (perception_critic / misc_detector properties)
        self._perception_critic: Optional["PerceptionCritic"] = None
        self._misc_detector: Optional["MisconceptionDetector"] = None

    # v0.80.0-c: __getattr__ forwarding for web/api/belief.py:189-191 + 224 direct dict writes.
    # When engine._warmup_count[sid] = X is called, __getattr__ returns the ObservationEngine's
    # _warmup_count dict, then __setitem__ mutates it in place (same object).
    # BeliefEngine itself no longer owns these dicts (moved to ObservationEngine / FeatureExtractor).
    _FORWARDED_INTERNAL_DICTS = {
        "_warmup_count", "_warmup_pool_cursor", "_probe_due_in", "_probe_count",
        "_response_history",
    }

    def __getattr__(self, name: str) -> Any:
        """Forward internal dict access to owning layer.

        Triggered only when normal attribute lookup fails (i.e. the attr is not
        in self.__dict__). We forward _warmup_count etc to _observation_engine,
        and _response_history to _feature_extractor.
        """
        if name in BeliefEngine._FORWARDED_INTERNAL_DICTS:
            # _observation_engine / _feature_extractor are set in __init__ before any
            # external code can touch the forwarded dicts. If they're missing, it means
            # __init__ hasn't completed yet - raise AttributeError to avoid infinite recursion.
            oe = self.__dict__.get("_observation_engine")
            fe = self.__dict__.get("_feature_extractor")
            if name == "_response_history":
                if fe is not None:
                    return fe._response_history
            else:
                if oe is not None:
                    return getattr(oe, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    # ── W1 warm-up 状态机（W1 2026-07-17 新增, v0.80.0-c delegate to ObservationEngine）──

    def is_warmup(self, student_id: str) -> bool:
        """是否处于 warm-up 期（前 N 题）。"""
        return self._observation_engine.is_warmup(student_id, self.config)

    def warmup_remaining(self, student_id: str) -> int:
        """距离 warm-up 结束还剩几题。0 表示刚刚结束。"""
        return self._observation_engine.warmup_remaining(student_id, self.config)

    def warmup_progress(self, student_id: str) -> dict:
        """返回 warm-up 状态完整信息（供 API 层使用）。"""
        return self._observation_engine.warmup_progress(student_id, self.config)

    # ── W3 探针题状态机 API（W3 2026-07-17 新增, v0.80.0-c delegate to ObservationEngine）──

    def should_probe_now(self, student_id: str) -> bool:
        """下次选题是否应插入探针题。"""
        return self._observation_engine.should_probe_now(student_id, self.config)

    def consume_probe(self, student_id: str) -> None:
        """标记"已插入探针题",重置 _probe_due_in 为 probe_interval。"""
        self._observation_engine.consume_probe(student_id, self.config)

    def probe_progress(self, student_id: str) -> dict:
        """返回探针题状态完整信息（供 API 层使用）。"""
        return self._observation_engine.probe_progress(student_id, self.config)

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
        log_event: bool = True,
    ) -> BeliefState:
        """主更新入口--每次新观测后调用.

        v0.80.0-c: 4-layer split complete
          - ObservationEngine.run() -> ObservationContext (warmup/probe state + score/correct/bloom_step)
          - FeatureExtractor.extract() -> {history, history_entry}
          - InferenceEngine.run() -> InferenceResult (NO state mutation)
          - BeliefUpdator.apply() -> event_id (sole mutation site, calls StateEngine.commit)

        v0.81.0-b: log_event param propagated to BeliefUpdator.apply
          - Default True: all production callers + tests unchanged
          - replay()/simulate() pass log_event=False to avoid polluting event log

        Args:
            state: 当前 BeliefState
            observation: 结构化观测
            lca_result: LCA 干预结果（Phase 4+ 使用）
            log_event: v0.81.0-b - if True AND event_log attached, persist LearningEvent.
                       replay()/simulate() pass False.

        Returns:
            更新后的 BeliefState
        """
        student_id = state.student_id

        # Layer 1: ObservationEngine (warmup/probe state machine + score/correct/bloom_step derivation)
        ctx = self._observation_engine.run(student_id, observation, self.config)

        # Layer 2: FeatureExtractor (response_history accumulation, maxlen=100)
        feat = self._feature_extractor.extract(student_id, observation, ctx)

        # Layer 3: InferenceEngine (BKT + MIRT + Bloom + LLM critic + TC -> InferenceResult, NO mutation)
        result = self._inference_engine.run(state, observation, ctx, feat["history"])

        # Layer 4: BeliefUpdator (sole mutation site, calls StateEngine.commit for versioning + event_id)
        self._belief_updater.apply(
            state, result, observation, feat["history_entry"], log_event=log_event
        )

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
        self._feature_extractor.reset_student(student_id)
        self._observation_engine.reset_student(student_id)

    # ── v0.81.0-c: Replay + Simulation ────────────────────────────────────────

    def replay(
        self,
        events: List["LearningEvent"],
        student_id: str,
    ) -> BeliefState:
        """Replay events to rebuild state from scratch.

        Pure: passes log_event=False to update() so event_log is not polluted.

        Args:
            events: list of LearningEvent (chronological order, oldest first).
                    Use EventLog.load_events() to get them sorted.
            student_id: which student to rebuild state for.

        Returns:
            Fresh BeliefState after applying all events.
        """
        return self._state_engine.replay(
            events,
            student_id=student_id,
            update_fn=lambda s, o: self.update(s, o, log_event=False),
            create_state_fn=self.create_initial_state,
        )

    def simulate(
        self,
        events: List["LearningEvent"],
        student_id: str,
        fork_at_idx: int,
        alternative_events: List["LearningEvent"],
    ) -> BeliefState:
        """Replay events[0:fork_at_idx] then apply alternative_events.

        Used for counterfactual exploration: "what if the student had answered
        these different questions after question N?"

        Pure: passes log_event=False to update() so event_log is not polluted.

        Args:
            events: original event list (chronological order)
            student_id: student to simulate
            fork_at_idx: index in events to fork at (events[0:fork_at_idx] replayed)
            alternative_events: alternative future events to apply after fork

        Returns:
            Simulated BeliefState.
        """
        return self._state_engine.simulate(
            events,
            student_id=student_id,
            fork_at_idx=fork_at_idx,
            alternative_events=alternative_events,
            update_fn=lambda s, o: self.update(s, o, log_event=False),
            create_state_fn=self.create_initial_state,
        )
