"""CTA 信念引擎（编排器）.

对应 research/10-engineering/01-cta-belief-engine.md §2.3.

M2 W1 范围：
  ✅ L1 BKTEvolutionLayer（已实现 l1_evolution.py）
  ✅ L2 BiFactorMIRT5D MAP 估计（已实现 l2_mirt.py）
  🚧 L0 POMDP 框架（M2 W1 仅占位；Phase 4+ 实现 EKF）
  🚧 LLM Critic（M2 W1 跳过；Observation 直接用结构化字段）
  🚧 L3 CD-CAT 选题（M2 W1 仅接口占位；Phase 4+ 实现 PWKL）
  🚧 L4 因果归因（M2 W1 仅接口占位；Phase 4+ 实现 A/B Test）
  🚧 C 维度 misconception 折扣（M2 W1 占位；Phase 5+ 集成 TC/Misc 库）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np

from .belief_state import (
    BeliefState,
    BloomLevel,
    BloomProfileState,
    ConfidenceDimensionState,
    DimensionState,
    LearningDNAState,
    StateSnapshot,
    TrajectoryState,
)
from .l1_evolution import BKTEvolutionLayer, EvolutionConfig
from .l2_mirt import BiFactorMIRT5D, MIRTConfig, MIRTItemParams


@dataclass
class Observation:
    """单次学生观测（M2 W1 结构化版）.

    Attributes:
        skill_id: 涉及的知识点 ID（用于 BKT）
        problem_id: 题目 ID（用于 MIRT）
        correct: 作答是否正确
        bloom_level: 题目对应的 Bloom 层级（用于 BloomProfile 更新）
        explanation_text: 学生解释文本（LLM Critic 输入；M2 W1 不解析）
        timestamp: 观测时间
        response_time_sec: 答题耗时（秒；M2 W1 不使用）
    """

    skill_id: str
    problem_id: str
    correct: bool
    bloom_level: BloomLevel = BloomLevel.APPLY
    explanation_text: str = ""
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
    # BloomProfile 更新步长（每次观测叠加多少概率）
    bloom_update_step: float = 0.05
    # trajectory 保留最近 N 个快照
    trajectory_maxlen: int = 100


class BeliefEngine:
    """CTA 信念引擎（M2 W1 范围）.

    主入口:
        engine = BeliefEngine()
        state = engine.create_initial_state("student_001")
        state = engine.update(state, observation)
    """

    def __init__(self, config: BeliefEngineConfig | None = None) -> None:
        self.config = config or BeliefEngineConfig()
        self.l1 = BKTEvolutionLayer(self.config.evolution_config)
        self.l2 = BiFactorMIRT5D(self.config.mirt_config)
        # M2 W1 简化：engine 持有学生 → 响应历史（用于 MIRT MAP 估计）
        self._response_history: Dict[str, List[Tuple[str, int, BloomLevel]]] = {}
        # M2 W1 占位接口（Phase 4+ 实现）
        # self.l0_pomdp: CTAPOMDP = None
        # self.llm_critic: LLMCritic = None
        # self.l3_cdcat: CDCATSelector = None
        # self.l4_causal: ABTestAttributor = None

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
        return state

    def update(
        self,
        state: BeliefState,
        observation: Observation,
        lca_result: Optional[LCAResult] = None,
    ) -> BeliefState:
        """主更新入口——每次新观测后调用.

        Args:
            state: 当前 BeliefState
            observation: 结构化观测
            lca_result: LCA 干预结果（M2 W1 占位，不使用）

        Returns:
            更新后的 BeliefState
        """
        student_id = state.student_id
        skill_id = observation.skill_id
        problem_id = observation.problem_id
        correct = observation.correct
        bloom_level = observation.bloom_level

        # Step 1: L1 BKT 更新
        new_p_mastered = self.l1.update(skill_id, correct)

        # Step 2: 累积响应历史（用于 MIRT 估计）
        history = self._response_history.setdefault(student_id, [])
        history.append((problem_id, int(correct), bloom_level))
        # 防止历史无限增长：保留最近 100 次
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
            # 用 θ 估计更新 5D DimensionState
            for i, dim_char in enumerate(["K", "P", "S", "C", "X"]):
                dim_state = getattr(state, dim_char)
                dim_state.theta = float(theta_hat[i])
                # SE 由协方差对角线近似
                dim_state.se = float(np.sqrt(max(theta_cov[i, i], 1e-6)))
                # 掌握概率用 sigmoid 映射到 [0,1]
                dim_state.mastery_prob = float(1.0 / (1.0 + np.exp(-theta_hat[i])))
                dim_state.mastered = dim_state.mastery_prob >= 0.5
                # 置信度随样本量增加（饱和函数）
                dim_state.confidence = min(1.0, len(history) / 30.0)
                dim_state.evidence_ids.append(len(history))
                dim_state.last_updated = observation.timestamp

        # Step 4: BloomProfile 更新
        bloom_name = bloom_level.name.lower()
        current_prob = getattr(state.bloom_profile, bloom_name)
        step = self.config.bloom_update_step
        if correct:
            new_prob = min(1.0, current_prob + step)
        else:
            new_prob = max(0.0, current_prob - step * 0.5)  # 错题扣半分
        setattr(state.bloom_profile, bloom_name, new_prob)
        state.bloom_profile.update_dominant()
        # BloomProfile 置信度也随样本量增加
        state.bloom_profile.confidence = min(1.0, len(history) / 30.0)
        state.bloom_profile.evidence_ids.append(len(history))

        # Step 5: 整体置信度 = 5D confidence 平均 + BloomProfile confidence 加权
        c5d = np.mean([getattr(state, d).confidence for d in ["K", "P", "S", "C", "X"]])
        state.overall_confidence = 0.6 * c5d + 0.4 * state.bloom_profile.confidence

        # Step 6: 追加轨迹快照
        state.trajectory.append(state.snapshot())
        if len(state.trajectory.snapshots) > self.config.trajectory_maxlen:
            state.trajectory.snapshots = state.trajectory.snapshots[-self.config.trajectory_maxlen :]

        # Step 7: 时间戳
        state.last_updated = observation.timestamp

        # Step 8: L4 因果归因（M2 W1 占位；Phase 4+ 实现）
        # if lca_result and lca_result.actual_outcome is not None:
        #     self.l4_causal.attribute(lca_result)

        return state

    def get_bkt_mastery(self, skill_id: str) -> float:
        """便捷接口：获取 BKT 当前掌握概率."""
        return self.l1.get_mastery(skill_id)

    def get_theta(self, state: BeliefState) -> np.ndarray:
        """便捷接口：获取当前 5D θ."""
        return state.theta_vector()

    def select_next_problem(self, state: BeliefState) -> Optional[str]:
        """L3 CD-CAT 选下一题（M2 W1 占位；Phase 4+ 实现 PWKL）.

        当前行为：返回 None（不选）。由调用方决定 fallback 策略。
        """
        return None

    def reset_student(self, student_id: str) -> None:
        """重置某学生的累积历史."""
        if student_id in self._response_history:
            del self._response_history[student_id]