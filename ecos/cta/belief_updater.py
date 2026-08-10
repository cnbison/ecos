"""v0.80.0-b: BeliefUpdator - 2.0 §3 Layer 4.

Converts InferenceResult to state mutations. Sole mutation site (via StateEngine.commit).

Replaces belief_engine.py:359-373, 385-388, 408, 418, 442-444, 447 + _llm_critic_perception
mutations (481-489) + _llm_critic_misconception mutations (521-533).

Design:
    BeliefUpdator.apply(state, result, observation, history_entry) -> event_id
    - Applies dim_updates / bloom / llm_perception / llm_misconception / tc / overall to state
    - Appends trajectory snapshot
    - Calls StateEngine.commit(state, None, source='belief_updater') for versioning + event_id
    - Returns event_id

Critical invariant: BeliefUpdator is the SOLE mutation site for BeliefState.
InferenceEngine.run() produces InferenceResult (no mutation).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from .belief_state import BeliefState
from .inference_engine import InferenceResult
from .state_engine import StateEngine

logger = logging.getLogger(__name__)


class BeliefUpdator:
    """2.0 §3 Layer 4: Belief Updater.

    Converts InferenceResult to StateEngine.commit calls.
    Sole mutation site for BeliefState (via StateEngine).
    """

    def __init__(self, state_engine: StateEngine) -> None:
        self.state_engine = state_engine

    def apply(
        self,
        state: BeliefState,
        result: InferenceResult,
        observation: Any,
        history_entry: Dict[str, Any],
    ) -> str:
        """Apply InferenceResult to state via StateEngine.commit.

        Args:
            state: target BeliefState (mutated in place)
            result: InferenceResult from InferenceEngine.run()
            observation: original Observation (for timestamp fallback)
            history_entry: response history entry dict (for mastery_prob_after backfill)

        Returns:
            event_id (str)
        """
        # Step 3: MIRT 5D dim updates
        if result.theta_mean is not None:
            state.theta_mean = result.theta_mean.copy()
        if result.theta_cov is not None:
            state.theta_cov = result.theta_cov.copy()

        for dim_char, updates in result.dim_updates.items():
            dim_state = getattr(state, dim_char)
            dim_state.theta = updates["theta"]
            dim_state.se = updates["se"]
            dim_state.mastery_prob = updates["mastery_prob"]
            dim_state.mastered = updates["mastered"]
            dim_state.confidence = updates["confidence"]
            dim_state.evidence_ids.append(updates["evidence_id"])
            dim_state.last_updated = updates["last_updated"]

        # Step 4: BloomProfile update
        for field_name, new_prob in result.bloom_field_updates.items():
            setattr(state.bloom_profile, field_name, new_prob)
        if result.bloom_dominant_recompute:
            state.bloom_profile.update_dominant()
        if result.bloom_confidence is not None:
            state.bloom_profile.confidence = result.bloom_confidence
        if result.bloom_evidence_id is not None:
            state.bloom_profile.evidence_ids.append(result.bloom_evidence_id)

        # Step 5: LLM perception mutations
        if result.llm_perception_bloom_target is not None:
            target_name, new_prob = result.llm_perception_bloom_target
            setattr(state.bloom_profile, target_name, new_prob)
        if result.llm_perception_dominant_recompute:
            state.bloom_profile.update_dominant()
        if result.llm_perception_c_confidence is not None:
            state.C.confidence = result.llm_perception_c_confidence

        # Step 6: LLM misconception mutations
        if result.llm_misc_hit is not None:
            state.C.misconception_hits.append(result.llm_misc_hit)
            state.C.illusory_confidence_flag = result.llm_misc_illusory_flag
            if result.llm_misc_c_discount_factor is not None:
                state.C.discount_factor = result.llm_misc_c_discount_factor
            if result.llm_misc_c_mastery_prob is not None:
                state.C.mastery_prob = result.llm_misc_c_mastery_prob
            if result.llm_misc_c_mastered is not None:
                state.C.mastered = result.llm_misc_c_mastered
            if result.llm_misc_c_evidence_id is not None:
                state.C.evidence_ids.append(result.llm_misc_c_evidence_id)

        # Step 7: TC state
        if result.tc_skill_id is not None and result.tc_state is not None:
            state.C.tc_states[result.tc_skill_id] = result.tc_state

        # Step 8: overall_confidence
        if result.overall_confidence is not None:
            state.overall_confidence = result.overall_confidence

        # Step 9: trajectory snapshot (computed AFTER all mutations, so snapshot reflects post-update state)
        if result.trajectory_maxlen is not None:
            snapshot = state.snapshot()
            state.trajectory.append(snapshot)
            if len(state.trajectory.snapshots) > result.trajectory_maxlen:
                state.trajectory.snapshots = state.trajectory.snapshots[-result.trajectory_maxlen:]

        # Step 10: mastery_prob_after backfill on history_entry (mutates engine-internal history, not BeliefState)
        if history_entry is not None:
            history_entry["mastery_prob_after"] = {
                "K": float(state.K.mastery_prob),
                "P": float(state.P.mastery_prob),
                "S": float(state.S.mastery_prob),
                "C": float(state.C.mastery_prob),
                "X": float(state.X.mastery_prob),
                "bloom_dominant": state.bloom_profile.dominant_layer.name,
                "bloom_confidence": float(state.bloom_profile.confidence),
                "overall_confidence": float(state.overall_confidence),
            }

        # Step 11: last_updated (set BEFORE commit; bump_version in commit overrides with now(),
        # so we re-set AFTER commit to preserve observation.timestamp semantics)
        # Call StateEngine.commit for versioning + event_id binding
        # None payload = no-op mutation, just bump version + return event_id
        event_id = self.state_engine.commit(state, None, source="belief_updater")

        if result.last_updated is not None:
            state.last_updated = result.last_updated

        return event_id
