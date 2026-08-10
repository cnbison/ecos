"""v0.80.0-b: InferenceEngine - 2.0 §3 Layer 3.

Orchestrates BKT / MIRT / Bloom / LLM critic / TC inference.
Produces InferenceResult (pure data, NO state mutation).
BeliefUpdator consumes InferenceResult and applies mutations via StateEngine.

Replaces belief_engine.py:322-408 + 423-439 + _llm_critic_perception + _llm_critic_misconception.

Design:
    InferenceEngine.run(state, observation, ctx, history) -> InferenceResult
    - Reads state (read-only)
    - Calls l1.update (mutates BKT layer's internal state, NOT BeliefState)
    - Calls l2.estimate_theta (pure function)
    - Computes 5D dim updates (theta, se, mastery_prob, mastered, confidence)
    - Computes Bloom updates (delta, new_prob)
    - Calls LLM perception critic (mutates LLM client state, NOT BeliefState)
    - Calls LLM misconception detector (mutates LLM client state, NOT BeliefState)
    - Calls tc_detector.detect (pure function)
    - Computes overall_confidence
    - Returns InferenceResult

Critical invariant: state is NOT mutated by InferenceEngine.run().
BeliefUpdator.apply() is the sole mutation site (via StateEngine.commit).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

import numpy as np

from .belief_state import (
    BeliefState,
    BloomLevel,
    MisconceptionHit,
    StateSnapshot,
    TCState,
)

if TYPE_CHECKING:
    from .belief_engine import BeliefEngineConfig, Observation
    from .l1_evolution import BKTEvolutionLayer
    from .l2_mirt import BiFactorMIRT5D
    from .tc_detector import TCStateDetector
    from ...llm_client import ECOSLLMClient
    from .llm_critic import MisconceptionDetector, PerceptionCritic

logger = logging.getLogger(__name__)


@dataclass
class ObservationContext:
    """Output of ObservationEngine.run() (v0.80.0-c extracts, inline for v0.80.0-b).

    Carries warmup/probe state + derived score/correct + bloom_step.
    """
    student_id: str
    skill_id: str
    problem_id: str
    score: float
    correct: bool
    bloom_level: BloomLevel
    in_warmup: bool
    just_exited_warmup: bool
    bloom_step: float
    observation: Any  # Observation (forward ref)


@dataclass
class InferenceResult:
    """Output of InferenceEngine.run() - consumed by BeliefUpdator.

    Pure data, no state mutation. BeliefUpdator converts this to StateEngine.commit calls.

    Field groups:
        - mirt: theta_mean, theta_cov, dim_updates (5D)
        - bloom: bloom_field_updates, bloom_dominant_recompute, bloom_confidence, bloom_evidence_id
        - llm_perception: bloom_target_name, bloom_target_new_prob, c_confidence_blend
        - llm_misconception: misc_hit, illusory_flag, c_discount_factor, c_mastery_prob, c_mastered, c_evidence_id
        - tc: tc_skill_id, tc_state
        - overall: overall_confidence
        - trajectory: trajectory_snapshot, trajectory_maxlen
        - meta: last_updated
    """

    # MIRT outputs (Step 3)
    theta_mean: Optional[np.ndarray] = None
    theta_cov: Optional[np.ndarray] = None
    dim_updates: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # dim_updates[dim_char] = {
    #     "theta": float, "se": float, "mastery_prob": float,
    #     "mastered": bool, "confidence": float,
    #     "evidence_id": int, "last_updated": datetime
    # }

    # Bloom outputs (Step 4)
    bloom_field_updates: Dict[str, float] = field(default_factory=dict)
    # e.g. {"apply": 0.65} - field_name -> new_prob
    bloom_dominant_recompute: bool = False
    bloom_confidence: Optional[float] = None
    bloom_evidence_id: Optional[int] = None

    # LLM perception outputs (Step 5)
    llm_perception_bloom_target: Optional[Tuple[str, float]] = None
    # (target_name, new_prob) - None if no perception update
    llm_perception_c_confidence: Optional[float] = None
    llm_perception_dominant_recompute: bool = False

    # LLM misconception outputs (Step 6)
    llm_misc_hit: Optional[MisconceptionHit] = None
    llm_misc_illusory_flag: bool = False
    llm_misc_c_discount_factor: Optional[float] = None
    llm_misc_c_mastery_prob: Optional[float] = None
    llm_misc_c_mastered: Optional[bool] = None
    llm_misc_c_evidence_id: Optional[int] = None

    # TC state (Step 7)
    tc_skill_id: Optional[str] = None
    tc_state: Optional[TCState] = None

    # Overall confidence (Step 8)
    overall_confidence: Optional[float] = None

    # Trajectory snapshot (Step 9) - applied directly, NOT via StateEngine
    trajectory_snapshot: Optional[StateSnapshot] = None
    trajectory_maxlen: Optional[int] = None

    # Last updated (Step 10) - applied via StateEngine.commit (bump_version)
    last_updated: Optional[datetime] = None


class InferenceEngine:
    """2.0 §3 Layer 3: Inference Engine.

    Orchestrates (no state mutation):
        - l1 (BKT) - mutates BKT layer's internal state, NOT BeliefState
        - l2 (MIRT MAP) - pure function
        - Bloom update computation
        - LLM critic (perception + misconception) - mutates LLM client state, NOT BeliefState
        - TC detector

    Returns InferenceResult for BeliefUpdator to commit via StateEngine.
    """

    def __init__(
        self,
        l1: "BKTEvolutionLayer",
        l2: "BiFactorMIRT5D",
        tc_detector: "TCStateDetector",
        config: "BeliefEngineConfig",
        llm_client: Optional["ECOSLLMClient"] = None,
        misconception_library_str: Optional[str] = None,
    ) -> None:
        self.l1 = l1
        self.l2 = l2
        self.tc_detector = tc_detector
        self.config = config
        self.llm_client = llm_client
        self.misconception_library_str = misconception_library_str
        self._perception_critic: Optional["PerceptionCritic"] = None
        self._misc_detector: Optional["MisconceptionDetector"] = None

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

    def run(
        self,
        state: BeliefState,
        observation: "Observation",
        ctx: ObservationContext,
        history: List[Dict[str, Any]],
    ) -> InferenceResult:
        """Run all inference steps, return InferenceResult (NO state mutation).

        Args:
            state: current BeliefState (read-only)
            observation: structured observation
            ctx: ObservationContext (from ObservationEngine)
            history: response history list (read-only, for MIRT)

        Returns:
            InferenceResult capturing all computed values
        """
        result = InferenceResult()
        result.last_updated = observation.timestamp

        # Step 1: L1 BKT update (mutates BKT internal state, NOT BeliefState)
        self.l1.update(ctx.skill_id, ctx.correct)

        # Step 3: L2 MIRT MAP estimation
        if len(history) >= 2:
            problem_ids = [h["problem_id"] for h in history]
            responses = np.array(
                [h.get("score", h.get("correct", 0)) for h in history],
                dtype=float,
            )
            theta_hat, theta_cov = self.l2.estimate_theta(responses, problem_ids)
            result.theta_mean = theta_hat
            result.theta_cov = theta_cov

            for i, dim_char in enumerate(["K", "P", "S", "C", "X"]):
                theta_val = float(theta_hat[i])
                se_val = float(np.sqrt(max(theta_cov[i, i], 1e-6)))
                mastery_prob = float(1.0 / (1.0 + np.exp(-theta_hat[i])))
                mastered = mastery_prob >= 0.5
                confidence = float(1.0 / (1.0 + se_val))
                result.dim_updates[dim_char] = {
                    "theta": theta_val,
                    "se": se_val,
                    "mastery_prob": mastery_prob,
                    "mastered": mastered,
                    "confidence": confidence,
                    "evidence_id": len(history),
                    "last_updated": observation.timestamp,
                }

        # Step 4: BloomProfile update
        bloom_name = ctx.bloom_level.name.lower()
        current_prob = float(getattr(state.bloom_profile, bloom_name))
        bloom_delta = (ctx.score - 0.5) * 2.0 * ctx.bloom_step
        new_prob = max(0.0, min(1.0, current_prob + bloom_delta))
        result.bloom_field_updates[bloom_name] = new_prob
        result.bloom_dominant_recompute = True
        result.bloom_confidence = min(1.0, len(history) / 30.0)
        result.bloom_evidence_id = len(history)

        # Step 5: LLM Critic 感知层
        if observation.explanation_text and self.llm_client is not None:
            self._compute_llm_perception(state, observation, ctx, result)

        # Step 6: LLM Critic Misconception 检测
        if observation.explanation_text and self.llm_client is not None:
            self._compute_llm_misconception(state, observation, ctx, result)

        # Step 7: TC 状态检测
        has_misc = result.llm_misc_hit is not None
        current_tc = state.C.tc_states.get(ctx.skill_id, None)
        updated_tc = self.tc_detector.detect(
            topic=ctx.skill_id,
            correct=ctx.correct,
            bloom_level=ctx.bloom_level,
            current_tc_state=current_tc,
            has_active_misc=has_misc,
        )
        result.tc_skill_id = ctx.skill_id
        result.tc_state = updated_tc

        # Step 8: overall_confidence
        # Use dim_updates if available (fresh computation), else fall back to state values
        k_conf = result.dim_updates.get("K", {}).get("confidence", state.K.confidence)
        p_conf = result.dim_updates.get("P", {}).get("confidence", state.P.confidence)
        s_conf = result.dim_updates.get("S", {}).get("confidence", state.S.confidence)
        c_conf = result.dim_updates.get("C", {}).get("confidence", state.C.confidence)
        x_conf = result.dim_updates.get("X", {}).get("confidence", state.X.confidence)

        # If LLM perception blended C.confidence, use that instead
        if result.llm_perception_c_confidence is not None:
            c_conf = result.llm_perception_c_confidence

        # If LLM misconception discounted C.mastery_prob, that doesn't change C.confidence
        # (confidence is about estimation quality, mastery_prob is about knowledge)

        result.overall_confidence = float(np.mean([k_conf, p_conf, s_conf, c_conf, x_conf]))

        # Step 9: trajectory snapshot (computed here, applied by BeliefUpdator)
        # Note: snapshot() reads current state, but we want the POST-update snapshot.
        # BeliefUpdator will compute this after applying mutations.
        result.trajectory_maxlen = self.config.trajectory_maxlen

        return result

    def _compute_llm_perception(
        self,
        state: BeliefState,
        observation: "Observation",
        ctx: ObservationContext,
        result: InferenceResult,
    ) -> None:
        """Step 5: LLM Critic 感知层 - populate InferenceResult (NO state mutation)."""
        try:
            p_out = self.perception_critic.perceive(
                problem=observation.problem_text or observation.skill_id,
                correct_answer=observation.correct_answer or "",
                student_correctness=observation.correct,
                student_explanation=observation.explanation_text,
            )
        except Exception:
            logger.warning(
                "_compute_llm_perception: LLM Critic.perceive 失败(student=%s, problem=%s), 跳过 Bloom 推断",
                state.student_id, observation.problem_id, exc_info=True,
            )
            return

        # Bloom 推断：仅当推断层高于当前 dominant_layer 时才采纳
        if p_out.bloom_level is not None:
            inferred_val = p_out.bloom_level.value
            current_dom_val = state.bloom_profile.dominant_layer.value
            if inferred_val > current_dom_val:
                target_name = p_out.bloom_level.name.lower()
                current_target_prob = float(getattr(state.bloom_profile, target_name))
                new_prob = min(1.0, current_target_prob + self.config.bloom_update_step)
                result.llm_perception_bloom_target = (target_name, new_prob)
                result.llm_perception_dominant_recompute = True

        # C 维度 confidence 混合 (perception quality 影响)
        blended = state.C.confidence * 0.7 + p_out.explanation_quality * 0.3
        result.llm_perception_c_confidence = float(blended)

    def _compute_llm_misconception(
        self,
        state: BeliefState,
        observation: "Observation",
        ctx: ObservationContext,
        result: InferenceResult,
    ) -> None:
        """Step 6: LLM Critic Misconception 检测 - populate InferenceResult (NO state mutation)."""
        try:
            misc_hit = self.misc_detector.detect_with_hits(
                student_explanation=observation.explanation_text,
                problem=observation.problem_text or observation.skill_id,
                trigger_problem_id=observation.problem_id,
                library_str=self.misconception_library_str,
            )
        except Exception:
            logger.warning(
                "_compute_llm_misconception: LLM 调用失败(student=%s, problem=%s)",
                state.student_id, observation.problem_id, exc_info=True,
            )
            return

        if misc_hit is None:
            return

        # Compute discounted values (don't mutate state yet)
        current_discount = float(state.C.discount_factor)
        discount = 1.0 - min(misc_hit.confidence * 0.3, 0.3)
        new_discount_factor = min(current_discount * discount, 1.0)

        # mastery_prob comes from dim_updates if MIRT ran, else from state
        if "C" in result.dim_updates:
            current_mastery = result.dim_updates["C"]["mastery_prob"]
        else:
            current_mastery = float(state.C.mastery_prob)
        discounted_mastery = current_mastery * new_discount_factor
        discounted_mastered = discounted_mastery >= 0.5

        result.llm_misc_hit = misc_hit
        result.llm_misc_illusory_flag = True
        result.llm_misc_c_discount_factor = new_discount_factor
        result.llm_misc_c_mastery_prob = discounted_mastery
        result.llm_misc_c_mastered = discounted_mastered
        result.llm_misc_c_evidence_id = len(observation.explanation_text)
