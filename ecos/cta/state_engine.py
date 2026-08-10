"""v0.80.0 StateEngine - 2.0 §2.2.1 mutation single entry point.

Scope (v0.80):
  - Transition: ✅ (BeliefEngine.update mutations route here via BeliefUpdator)
  - Validation: ✅ (delegates to BeliefState.validate)
  - Snapshot: ✅ (with version/event_id binding)
  - Diff: ✅ (structured, not scalar)
  - Replay: ❌ (deferred to v0.81 Event Engine)
  - Versioning: ✅ (event_id + version field)

TODO v0.82: promote to ecos/state_engine.py when scope expands beyond BeliefState.

Usage:
    engine = StateEngine()
    event_id = engine.commit(state, delta={"theta_mean": [...]}, source="mirt")
    is_valid, issues = engine.validate(state)
    snapshot_id = engine.snapshot(state, source_event_id=event_id)
    diff = engine.diff(state_before, state_after)
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .belief_state import BeliefState

_log = logging.getLogger(__name__)


@dataclass
class StateDelta:
    """Structured delta for StateEngine.commit.

    Either new_state (full replacement) or delta (partial dict).
    Source: who is committing (e.g. "bkt", "mirt", "llm_critic_perception", "db_restore").
    """
    new_state: Optional[BeliefState] = None
    delta: Optional[Dict[str, Any]] = None
    source: str = "unknown"
    event_id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class StateDiff:
    """Structured diff between two BeliefStates."""
    changed_fields: List[str] = field(default_factory=list)
    old_values: Dict[str, Any] = field(default_factory=dict)
    new_values: Dict[str, Any] = field(default_factory=dict)
    delta_magnitudes: Dict[str, float] = field(default_factory=dict)


class StateEngine:
    """2.0 §2.2.1 StateEngine - sole mutation entry for BeliefState.

    BeliefState.apply_snapshot (v0.77.1) delegates here for DB restore path.
    BeliefUpdator (v0.80.0-b+) delegates here for runtime mutations.
    """

    def __init__(self, snapshot_store: Optional[List[Dict[str, Any]]] = None) -> None:
        # In-memory snapshot ring (v0.80). v0.81+ replaces with EventLog.
        self._snapshots: List[Dict[str, Any]] = snapshot_store if snapshot_store is not None else []
        self._max_snapshots: int = 1000

    def commit(
        self,
        state: BeliefState,
        new_state_or_delta: Any,
        source: str,
        validate: bool = False,
    ) -> str:
        """Apply mutation to state, return event_id.

        Args:
            state: target BeliefState (mutated in place)
            new_state_or_delta:
                - BeliefState: full replacement (copy fields)
                - dict: partial delta, route to state._apply_delta_fields
                - StateDelta: explicit delta object
            source: who is committing (e.g. "bkt", "mirt", "db_restore")
            validate: if True, validate state after commit; raises on invalid

        Returns:
            event_id (str)
        """
        event_id = f"evt_{uuid.uuid4().hex[:12]}"

        if isinstance(new_state_or_delta, StateDelta):
            payload = new_state_or_delta.new_state if new_state_or_delta.new_state else new_state_or_delta.delta
            source = new_state_or_delta.source
            event_id = new_state_or_delta.event_id
        else:
            payload = new_state_or_delta

        if isinstance(payload, BeliefState):
            self._copy_state_fields(state, payload)
        elif isinstance(payload, dict):
            state._apply_delta_fields(payload)
        elif payload is None:
            pass  # no-op commit (event_id only, for snapshot binding)
        else:
            raise TypeError(f"Unsupported new_state_or_delta type: {type(payload)}")

        state.bump_version(event_id)

        if validate:
            is_valid, issues = state.validate()
            if not is_valid:
                raise ValueError(f"State validation failed after commit (source={source}): {issues}")

        return event_id

    def validate(self, state: BeliefState) -> Tuple[bool, List[str]]:
        """Schema + range validation. Delegates to BeliefState.validate()."""
        return state.validate()

    def snapshot(self, state: BeliefState, source_event_id: str) -> str:
        """Take snapshot, bind to event_id. Returns snapshot_id.

        Snapshot is a deep-ish copy of state's key fields at this moment.
        Stored in in-memory ring buffer (max 1000). v0.81+ persists to EventLog.
        """
        snapshot_id = f"snap_{uuid.uuid4().hex[:12]}"
        snapshot_data = {
            "snapshot_id": snapshot_id,
            "source_event_id": source_event_id,
            "timestamp": datetime.now().isoformat(),
            "state": state.to_dict(),
        }
        self._snapshots.append(snapshot_data)
        if len(self._snapshots) > self._max_snapshots:
            self._snapshots.pop(0)
        return snapshot_id

    def diff(self, s1: BeliefState, s2: BeliefState) -> StateDiff:
        """Structured diff between two BeliefStates.

        Compares:
            - 5D theta / mastery_prob / confidence (K/P/S/C/X)
            - theta_mean vector
            - bloom_profile 6 fields + confidence
            - overall_confidence
            - C.discount_factor
        """
        diff = StateDiff()

        # 5D dim fields
        for dim_name in ("K", "P", "S", "C", "X"):
            d1 = getattr(s1, dim_name)
            d2 = getattr(s2, dim_name)
            for field_name in ("theta", "mastery_prob", "confidence"):
                v1 = getattr(d1, field_name)
                v2 = getattr(d2, field_name)
                if v1 != v2:
                    key = f"{dim_name}.{field_name}"
                    diff.changed_fields.append(key)
                    diff.old_values[key] = v1
                    diff.new_values[key] = v2
                    try:
                        diff.delta_magnitudes[key] = abs(float(v2) - float(v1))
                    except (TypeError, ValueError) as e:
                        _log.warning(
                            "diff: cannot compute magnitude for %s (v1=%r, v2=%r): %s",
                            key, v1, v2, e,
                        )

        # C.discount_factor
        if s1.C.discount_factor != s2.C.discount_factor:
            key = "C.discount_factor"
            diff.changed_fields.append(key)
            diff.old_values[key] = s1.C.discount_factor
            diff.new_values[key] = s2.C.discount_factor
            diff.delta_magnitudes[key] = abs(float(s2.C.discount_factor) - float(s1.C.discount_factor))

        # theta_mean vector (5 elements)
        if not np.array_equal(s1.theta_mean, s2.theta_mean):
            for i in range(5):
                if s1.theta_mean[i] != s2.theta_mean[i]:
                    key = f"theta_mean[{i}]"
                    diff.changed_fields.append(key)
                    diff.old_values[key] = float(s1.theta_mean[i])
                    diff.new_values[key] = float(s2.theta_mean[i])
                    diff.delta_magnitudes[key] = abs(float(s2.theta_mean[i]) - float(s1.theta_mean[i]))

        # bloom_profile 6 fields + confidence
        for field_name in ("remember", "understand", "apply", "analyze", "evaluate", "create", "confidence"):
            v1 = getattr(s1.bloom_profile, field_name)
            v2 = getattr(s2.bloom_profile, field_name)
            if v1 != v2:
                key = f"bloom_profile.{field_name}"
                diff.changed_fields.append(key)
                diff.old_values[key] = v1
                diff.new_values[key] = v2
                diff.delta_magnitudes[key] = abs(float(v2) - float(v1))

        # overall_confidence
        if s1.overall_confidence != s2.overall_confidence:
            key = "overall_confidence"
            diff.changed_fields.append(key)
            diff.old_values[key] = s1.overall_confidence
            diff.new_values[key] = s2.overall_confidence
            diff.delta_magnitudes[key] = abs(float(s2.overall_confidence) - float(s1.overall_confidence))

        return diff

    def get_snapshots(self) -> List[Dict[str, Any]]:
        """Return all stored snapshots (for debugging/testing)."""
        return list(self._snapshots)

    def clear_snapshots(self) -> None:
        """Clear snapshot ring (for test isolation)."""
        self._snapshots.clear()

    def _copy_state_fields(self, target: BeliefState, source: BeliefState) -> None:
        """Copy all fields from source to target (full replacement).

        Used when commit receives a full BeliefState instead of delta dict.
        """
        target.K = source.K
        target.P = source.P
        target.S = source.S
        target.C = source.C
        target.X = source.X
        target.theta_mean = source.theta_mean.copy()
        target.theta_cov = source.theta_cov.copy()
        target.bloom_profile = source.bloom_profile
        target.learning_dna = source.learning_dna
        target.trajectory = source.trajectory
        target.overall_confidence = source.overall_confidence
        # Don't copy student_id (target retains its identity)


# Module-level singleton for backward-compat shims (apply_snapshot delegates here)
_default_engine = StateEngine()


def get_default_engine() -> StateEngine:
    """Get the module-level default StateEngine (used by BeliefState.apply_snapshot shim)."""
    return _default_engine
