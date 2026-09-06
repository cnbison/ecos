"""v0.80.0-b: BeliefUpdator - 2.0 §3 Layer 4.

Converts InferenceResult to state mutations. Sole mutation site (via StateEngine.commit).

Replaces belief_engine.py:359-373, 385-388, 408, 418, 442-444, 447 + _llm_critic_perception
mutations (481-489) + _llm_critic_misconception mutations (521-533).

v0.81.0-b: + sole event logging site
  - apply(..., log_event: bool = True) param
  - When event_log is attached AND log_event=True, persists LearningEvent after commit
  - replay() / simulate() pass log_event=False to avoid polluting the log

Design:
    BeliefUpdator.apply(state, result, observation, history_entry) -> event_id
    - Applies dim_updates / bloom / llm_perception / llm_misconception / tc / overall to state
    - Appends trajectory snapshot
    - Calls StateEngine.commit(state, None, source='belief_updater') for versioning + event_id
    - v0.81.0-b: If event_log attached AND log_event=True, persists LearningEvent
    - Returns event_id

Critical invariant: BeliefUpdator is the SOLE mutation site AND sole event logging site.
InferenceEngine.run() produces InferenceResult (no mutation, no logging).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from .belief_state import BeliefState
from .event_log import EventLog, LearningEvent
from .inference_engine import InferenceResult
from .state_engine import StateEngine

logger = logging.getLogger(__name__)


class BeliefUpdator:
    """2.0 §3 Layer 4: Belief Updater.

    Converts InferenceResult to StateEngine.commit calls.
    Sole mutation site for BeliefState (via StateEngine).
    v0.81.0-b: Also sole event logging site (when event_log attached).
    """

    def __init__(
        self,
        state_engine: StateEngine,
        event_log: Optional[EventLog] = None,
        evidence_engine: Optional[Any] = None,  # v0.83.0-b: optional Evidence Engine
    ) -> None:
        self.state_engine = state_engine
        self.event_log = event_log  # v0.81.0-b: optional event persistence
        # v0.83.0-b: 注入 Evidence Engine (optional, 不传则 fallback 到原 evidence_ids.append)
        self.evidence_engine = evidence_engine

    def apply(
        self,
        state: BeliefState,
        result: InferenceResult,
        observation: Any,
        history_entry: Dict[str, Any],
        log_event: bool = True,
    ) -> str:
        """Apply InferenceResult to state via StateEngine.commit.

        Args:
            state: target BeliefState (mutated in place)
            result: InferenceResult from InferenceEngine.run()
            observation: original Observation (for timestamp fallback + event payload)
            history_entry: response history entry dict (for mastery_prob_after backfill)
            log_event: v0.81.0-b - if True AND event_log attached, persist LearningEvent.
                       replay()/simulate() pass False to avoid polluting log.

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
            # v0.83.0-b: 如果 evidence_engine 注入, 走 Evidence Engine 路径
            #   (Evidence Engine.add 创建新 evidence, state.add_evidence 关联)
            #   否则 fallback 到原 evidence_ids.append(updates["evidence_id"])
            # v0.98.0 (b-a): log_event=False (replay/simulate) 时抑制 Evidence
            #   Engine 写库 — 与 event_log 抑制语义一致, replay 不污染 evidence_log
            #   (legacy append 分支只动 in-memory state, 无需抑制)。
            if self.evidence_engine is not None and log_event:
                self._register_evidence(
                    dim_char, updates["evidence_id"], observation, state,
                )
            else:
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

        # v0.81.0-b: persist LearningEvent (sole logging site, mirrors "sole mutation site")
        # log_event=False suppresses (used by replay()/simulate() to avoid polluting log)
        if self.event_log is not None and log_event:
            try:
                payload = (
                    observation.to_dict()
                    if hasattr(observation, "to_dict")
                    else {"_raw": str(observation)}
                )
            except Exception:
                logger.warning(
                    "BeliefUpdator: observation.to_dict() failed, logging partial payload",
                    exc_info=True,
                )
                payload = {"_error": "to_dict_failed"}

            self.event_log.log_event(
                LearningEvent(
                    event_id=event_id,
                    student_id=state.student_id,
                    timestamp=(
                        observation.timestamp
                        if hasattr(observation, "timestamp")
                        else datetime.now()
                    ),
                    source="belief_updater",
                    event_type="observation",
                    payload=payload,
                )
            )

        return event_id

    # ---------------------------------------------------------------
    # v0.83.0-b: Evidence Engine 集成 helper
    # ---------------------------------------------------------------

    def _register_evidence(
        self,
        dim: str,
        evidence_id: int,
        observation: Any,
        state: "BeliefState",
    ) -> None:
        """v0.83.0-b: 把 evidence_id 走 Evidence Engine 注册, 并关联到 state.

        调用流程:
          1. 通过 EvidenceEngine.add 创建 Evidence 记录 (跨 3 表持久化)
          2. 调用 state.add_evidence(dim, evidence_id) 关联到 Twin

        如果 Evidence Engine 调用失败, _log.warning + 跳过 (不影响主流程).
        """
        if self.evidence_engine is None:
            return  # fallback: 不调 (跟 v0.81 行为一致)
        try:
            from datetime import datetime
            from ..evidence import Evidence, EvidenceSource

            # 从 observation 派生 payload (沿用 v0.81 observation.to_dict)
            if hasattr(observation, "to_dict"):
                payload = observation.to_dict()
            elif isinstance(observation, dict):
                payload = observation
            else:
                payload = {"_raw": str(observation)}

            # v0.98.0 (b-a): payload 加 dim 标记 — per-dim 5 行 evidence_log 行
            #   payload 原本全同无法区分维度 (Bisen 拍板保留 per-dim 5 行 + dim 标记)。
            #   dict() 拷贝: 5 次 dim 调用共享同一 to_dict() 返回值, 原地改会互相覆盖。
            payload = dict(payload)
            payload["dim"] = dim

            # confidence 从 history_entry 派生 (mastery_prob 或 score)
            confidence = float(payload.get("score", 0.5) or 0.5)

            ev = Evidence(
                source=EvidenceSource.RESPONSE_HISTORY,
                student_id=state.student_id,
                timestamp=datetime.now(),
                payload=payload,
                confidence=confidence,
                problem_id=payload.get("problem_id"),
            )
            new_evidence_id = self.evidence_engine.add(ev)
            # v0.98.0 (b-a): add 返回 0 = 写库失败 (如 FK 违反被 _add_to_evidence_log
            #   吞掉), 不关联到 state, 避免 evidence_ids 指向不存在的行。
            if new_evidence_id == 0:
                logger.warning(
                    "BeliefUpdator._register_evidence: add 返回 0 (写库失败), "
                    "跳过 state.add_evidence (dim=%s, sid=%s)",
                    dim, state.student_id,
                )
                return
            # v0.83.0-b: state.add_evidence 是 allowlist 入口 (跟 append_trajectory_snapshot 模式一致)
            state.add_evidence(dim, new_evidence_id)
        except Exception as e:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "BeliefUpdator._register_evidence 失败 (dim=%s, evidence_id=%s): %s",
                dim, evidence_id, e, exc_info=True,
            )
