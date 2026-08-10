"""v0.80.0-b InferenceEngine test suite.

Critical invariant: InferenceEngine.run() does NOT mutate BeliefState.
All mutations happen in BeliefUpdator.apply() via StateEngine.commit.

Covers:
- run() produces InferenceResult (pure data)
- run() does NOT mutate state (critical invariant)
- BKT update called (mutates l1 internal, NOT BeliefState)
- MIRT MAP estimation when len(history) >= 2
- 5D dim_updates computed correctly
- Bloom update computation (delta, new_prob, dominant_recompute)
- LLM perception (bloom_target, c_confidence)
- LLM misconception (c_discount, c_mastery, c_mastered)
- TC state detection
- overall_confidence computation
- last_updated set from observation.timestamp
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig, Observation
from ecos.cta.belief_state import (
    BeliefState,
    BloomLevel,
    ConfidenceDimensionState,
    DimensionState,
    TCState,
)
from ecos.cta.inference_engine import InferenceEngine, InferenceResult, ObservationContext
from ecos.cta.l1_evolution import EvolutionConfig
from ecos.cta.l2_mirt import MIRTConfig
from ecos.cta.tc_detector import TCStateDetector


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def engine_config() -> BeliefEngineConfig:
    return BeliefEngineConfig(
        evolution_config=EvolutionConfig(),
        mirt_config=MIRTConfig(),
        bloom_update_step=0.05,
        warmup_step=0.1,
        trajectory_maxlen=500,
    )


@pytest.fixture
def fresh_state() -> BeliefState:
    """BeliefState with initialized theta/cov."""
    state = BeliefState(student_id="lbc_test")
    state.theta_mean = np.zeros(5)
    state.theta_cov = np.eye(5)
    state.C = ConfidenceDimensionState(dimension="C")
    state.last_updated = datetime(2026, 1, 1)
    return state


@pytest.fixture
def inference_engine(engine_config) -> InferenceEngine:
    """InferenceEngine with real l1/l2/tc_detector but no LLM client."""
    from ecos.cta.l1_evolution import BKTEvolutionLayer
    from ecos.cta.l2_mirt import BiFactorMIRT5D

    return InferenceEngine(
        l1=BKTEvolutionLayer(engine_config.evolution_config),
        l2=BiFactorMIRT5D(engine_config.mirt_config),
        tc_detector=TCStateDetector(),
        config=engine_config,
        llm_client=None,
    )


def _make_observation(score: float = 1.0, bloom: BloomLevel = BloomLevel.APPLY) -> Observation:
    return Observation(
        skill_id="addition",
        problem_id="P001",
        correct=score >= 0.6,
        score=score,
        bloom_level=bloom,
        explanation_text="",
        timestamp=datetime(2026, 8, 10, 12, 0, 0),
    )


def _make_ctx(
    score: float = 1.0,
    bloom: BloomLevel = BloomLevel.APPLY,
    in_warmup: bool = False,
) -> ObservationContext:
    return ObservationContext(
        student_id="lbc_test",
        skill_id="addition",
        problem_id="P001",
        score=score,
        correct=score >= 0.6,
        bloom_level=bloom,
        in_warmup=in_warmup,
        just_exited_warmup=False,
        bloom_step=0.05,
        observation=_make_observation(score, bloom),
    )


# ── InferenceResult: pure data ──────────────────────────────────────────


def test_inference_result_default_construction():
    """InferenceResult can be constructed with no args (all defaults)."""
    result = InferenceResult()
    assert result.theta_mean is None
    assert result.theta_cov is None
    assert result.dim_updates == {}
    assert result.bloom_field_updates == {}
    assert result.bloom_dominant_recompute is False
    assert result.llm_perception_bloom_target is None
    assert result.llm_misc_hit is None
    assert result.overall_confidence is None


def test_inference_result_field_groups_documented():
    """InferenceResult field groups exist (MIRT / Bloom / LLM perception / LLM misconception / TC / overall / trajectory / meta)."""
    result = InferenceResult()
    # MIRT
    assert hasattr(result, "theta_mean")
    assert hasattr(result, "theta_cov")
    assert hasattr(result, "dim_updates")
    # Bloom
    assert hasattr(result, "bloom_field_updates")
    assert hasattr(result, "bloom_dominant_recompute")
    # LLM perception
    assert hasattr(result, "llm_perception_bloom_target")
    assert hasattr(result, "llm_perception_c_confidence")
    # LLM misconception
    assert hasattr(result, "llm_misc_hit")
    assert hasattr(result, "llm_misc_c_discount_factor")
    # TC
    assert hasattr(result, "tc_skill_id")
    assert hasattr(result, "tc_state")
    # Overall
    assert hasattr(result, "overall_confidence")
    # Trajectory
    assert hasattr(result, "trajectory_maxlen")
    # Meta
    assert hasattr(result, "last_updated")


# ── run(): no state mutation (critical invariant) ──────────────────────


def test_run_does_not_mutate_state_theta(fresh_state, inference_engine):
    """run() must NOT mutate state.theta_mean / theta_cov (MIRT result goes to InferenceResult only)."""
    original_theta = fresh_state.theta_mean.copy()
    original_cov = fresh_state.theta_cov.copy()

    history = [
        {"problem_id": "P001", "correct": 1, "score": 1.0, "bloom_level": "APPLY"},
        {"problem_id": "P002", "correct": 0, "score": 0.0, "bloom_level": "APPLY"},
    ]
    obs = _make_observation()
    ctx = _make_ctx()

    result = inference_engine.run(fresh_state, obs, ctx, history)

    assert result.theta_mean is not None  # InferenceResult has it
    np.testing.assert_array_equal(fresh_state.theta_mean, original_theta)  # state unchanged
    np.testing.assert_array_equal(fresh_state.theta_cov, original_cov)  # state unchanged


def test_run_does_not_mutate_state_dim_fields(fresh_state, inference_engine):
    """run() must NOT mutate state.K/P/S/C/X (dim_updates go to InferenceResult only)."""
    original_k_theta = fresh_state.K.theta
    original_k_mastery = fresh_state.K.mastery_prob
    original_k_confidence = fresh_state.K.confidence
    original_k_evidence_len = len(fresh_state.K.evidence_ids)

    history = [
        {"problem_id": "P001", "correct": 1, "score": 1.0, "bloom_level": "APPLY"},
        {"problem_id": "P002", "correct": 1, "score": 1.0, "bloom_level": "APPLY"},
    ]
    obs = _make_observation()
    ctx = _make_ctx()

    result = inference_engine.run(fresh_state, obs, ctx, history)

    # InferenceResult has dim_updates
    assert "K" in result.dim_updates
    assert result.dim_updates["K"]["theta"] is not None
    # state.K unchanged
    assert fresh_state.K.theta == original_k_theta
    assert fresh_state.K.mastery_prob == original_k_mastery
    assert fresh_state.K.confidence == original_k_confidence
    assert len(fresh_state.K.evidence_ids) == original_k_evidence_len


def test_run_does_not_mutate_bloom_profile(fresh_state, inference_engine):
    """run() must NOT mutate state.bloom_profile (bloom_field_updates go to InferenceResult only)."""
    original_apply = fresh_state.bloom_profile.apply
    original_dominant = fresh_state.bloom_profile.dominant_layer
    original_confidence = fresh_state.bloom_profile.confidence
    original_evidence_len = len(fresh_state.bloom_profile.evidence_ids)

    history = [{"problem_id": "P001", "correct": 1, "score": 1.0, "bloom_level": "APPLY"}]
    obs = _make_observation()
    ctx = _make_ctx()

    result = inference_engine.run(fresh_state, obs, ctx, history)

    # InferenceResult has bloom_field_updates
    assert "apply" in result.bloom_field_updates
    # state.bloom_profile unchanged
    assert fresh_state.bloom_profile.apply == original_apply
    assert fresh_state.bloom_profile.dominant_layer == original_dominant
    assert fresh_state.bloom_profile.confidence == original_confidence
    assert len(fresh_state.bloom_profile.evidence_ids) == original_evidence_len


def test_run_does_not_mutate_overall_confidence(fresh_state, inference_engine):
    """run() must NOT mutate state.overall_confidence (computed value goes to InferenceResult)."""
    original_oc = fresh_state.overall_confidence

    history = [{"problem_id": "P001", "correct": 1, "score": 1.0, "bloom_level": "APPLY"}]
    obs = _make_observation()
    ctx = _make_ctx()

    result = inference_engine.run(fresh_state, obs, ctx, history)

    assert result.overall_confidence is not None
    assert fresh_state.overall_confidence == original_oc


def test_run_does_not_mutate_last_updated(fresh_state, inference_engine):
    """run() must NOT mutate state.last_updated (goes to InferenceResult.last_updated)."""
    original_last_updated = fresh_state.last_updated

    history = [{"problem_id": "P001", "correct": 1, "score": 1.0, "bloom_level": "APPLY"}]
    obs = _make_observation()
    ctx = _make_ctx()

    result = inference_engine.run(fresh_state, obs, ctx, history)

    assert result.last_updated == obs.timestamp
    assert fresh_state.last_updated == original_last_updated


# ── run(): BKT update (mutates l1 internal, NOT state) ─────────────────


def test_run_calls_l1_update(fresh_state, inference_engine):
    """run() calls l1.update(skill_id, correct) to update BKT internal."""
    history = [{"problem_id": "P001", "correct": 1, "score": 1.0, "bloom_level": "APPLY"}]
    obs = _make_observation()
    ctx = _make_ctx()

    with patch.object(inference_engine.l1, "update") as mock_update:
        inference_engine.run(fresh_state, obs, ctx, history)
        mock_update.assert_called_once_with("addition", True)


def test_run_calls_l1_update_with_false_on_wrong_answer(fresh_state, inference_engine):
    """run() passes correct=False to l1.update when score < 0.6."""
    history = [{"problem_id": "P001", "correct": 0, "score": 0.0, "bloom_level": "APPLY"}]
    obs = _make_observation(score=0.0)
    ctx = _make_ctx(score=0.0)

    with patch.object(inference_engine.l1, "update") as mock_update:
        inference_engine.run(fresh_state, obs, ctx, history)
        mock_update.assert_called_once_with("addition", False)


# ── run(): MIRT MAP estimation ──────────────────────────────────────────


def test_run_skips_mirt_when_history_too_short(fresh_state, inference_engine):
    """MIRT requires len(history) >= 2."""
    history = [{"problem_id": "P001", "correct": 1, "score": 1.0, "bloom_level": "APPLY"}]
    obs = _make_observation()
    ctx = _make_ctx()

    result = inference_engine.run(fresh_state, obs, ctx, history)

    assert result.theta_mean is None
    assert result.theta_cov is None
    assert result.dim_updates == {}


def test_run_runs_mirt_when_history_has_2(fresh_state, inference_engine):
    """MIRT runs when len(history) >= 2."""
    history = [
        {"problem_id": "P001", "correct": 1, "score": 1.0, "bloom_level": "APPLY"},
        {"problem_id": "P002", "correct": 0, "score": 0.0, "bloom_level": "APPLY"},
    ]
    obs = _make_observation()
    ctx = _make_ctx()

    result = inference_engine.run(fresh_state, obs, ctx, history)

    assert result.theta_mean is not None
    assert result.theta_mean.shape == (5,)
    assert result.theta_cov is not None
    assert result.theta_cov.shape == (5, 5)


def test_run_dim_updates_has_5_dimensions(fresh_state, inference_engine):
    """dim_updates contains all 5D: K, P, S, C, X."""
    history = [
        {"problem_id": "P001", "correct": 1, "score": 1.0, "bloom_level": "APPLY"},
        {"problem_id": "P002", "correct": 1, "score": 1.0, "bloom_level": "APPLY"},
    ]
    obs = _make_observation()
    ctx = _make_ctx()

    result = inference_engine.run(fresh_state, obs, ctx, history)

    assert set(result.dim_updates.keys()) == {"K", "P", "S", "C", "X"}


def test_run_dim_updates_has_required_fields(fresh_state, inference_engine):
    """Each dim_update has theta/se/mastery_prob/mastered/confidence/evidence_id/last_updated."""
    history = [
        {"problem_id": "P001", "correct": 1, "score": 1.0, "bloom_level": "APPLY"},
        {"problem_id": "P002", "correct": 1, "score": 1.0, "bloom_level": "APPLY"},
    ]
    obs = _make_observation()
    ctx = _make_ctx()

    result = inference_engine.run(fresh_state, obs, ctx, history)

    for dim in ["K", "P", "S", "C", "X"]:
        d = result.dim_updates[dim]
        assert "theta" in d
        assert "se" in d
        assert "mastery_prob" in d
        assert "mastered" in d
        assert "confidence" in d
        assert "evidence_id" in d
        assert "last_updated" in d
        assert isinstance(d["mastered"], bool)
        assert 0.0 <= d["mastery_prob"] <= 1.0
        assert 0.0 <= d["confidence"] <= 1.0


def test_run_dim_updates_evidence_id_is_history_len(fresh_state, inference_engine):
    """evidence_id = len(history)."""
    history = [
        {"problem_id": "P001", "correct": 1, "score": 1.0, "bloom_level": "APPLY"},
        {"problem_id": "P002", "correct": 1, "score": 1.0, "bloom_level": "APPLY"},
        {"problem_id": "P003", "correct": 1, "score": 1.0, "bloom_level": "APPLY"},
    ]
    obs = _make_observation()
    ctx = _make_ctx()

    result = inference_engine.run(fresh_state, obs, ctx, history)

    for dim in ["K", "P", "S", "C", "X"]:
        assert result.dim_updates[dim]["evidence_id"] == 3


# ── run(): Bloom update computation ────────────────────────────────────


def test_run_bloom_field_update_correct_dim(fresh_state, inference_engine):
    """Bloom field update targets the correct dim (e.g. APPLY -> apply)."""
    history = [{"problem_id": "P001", "correct": 1, "score": 1.0, "bloom_level": "APPLY"}]
    obs = _make_observation(bloom=BloomLevel.APPLY)
    ctx = _make_ctx(bloom=BloomLevel.APPLY)

    result = inference_engine.run(fresh_state, obs, ctx, history)

    assert "apply" in result.bloom_field_updates
    assert "remember" not in result.bloom_field_updates


def test_run_bloom_field_update_increases_on_correct(fresh_state, inference_engine):
    """Correct answer (score=1.0) -> bloom field increases."""
    fresh_state.bloom_profile.apply = 0.5
    history = [{"problem_id": "P001", "correct": 1, "score": 1.0, "bloom_level": "APPLY"}]
    obs = _make_observation(score=1.0, bloom=BloomLevel.APPLY)
    ctx = _make_ctx(score=1.0, bloom=BloomLevel.APPLY)

    result = inference_engine.run(fresh_state, obs, ctx, history)

    assert result.bloom_field_updates["apply"] > 0.5


def test_run_bloom_field_update_decreases_on_wrong(fresh_state, inference_engine):
    """Wrong answer (score=0.0) -> bloom field decreases."""
    fresh_state.bloom_profile.apply = 0.5
    history = [{"problem_id": "P001", "correct": 0, "score": 0.0, "bloom_level": "APPLY"}]
    obs = _make_observation(score=0.0, bloom=BloomLevel.APPLY)
    ctx = _make_ctx(score=0.0, bloom=BloomLevel.APPLY)

    result = inference_engine.run(fresh_state, obs, ctx, history)

    assert result.bloom_field_updates["apply"] < 0.5


def test_run_bloom_dominant_recompute_always_true(fresh_state, inference_engine):
    """bloom_dominant_recompute is True after bloom update (BeliefUpdator calls update_dominant)."""
    history = [{"problem_id": "P001", "correct": 1, "score": 1.0, "bloom_level": "APPLY"}]
    obs = _make_observation()
    ctx = _make_ctx()

    result = inference_engine.run(fresh_state, obs, ctx, history)

    assert result.bloom_dominant_recompute is True


def test_run_bloom_confidence_grows_with_history(fresh_state, inference_engine):
    """bloom_confidence = min(1.0, len(history) / 30.0)."""
    history = [{"problem_id": f"P{i:03d}", "correct": 1, "score": 1.0, "bloom_level": "APPLY"} for i in range(15)]
    obs = _make_observation()
    ctx = _make_ctx()

    result = inference_engine.run(fresh_state, obs, ctx, history)

    assert result.bloom_confidence == pytest.approx(15.0 / 30.0)


def test_run_bloom_confidence_capped_at_1(fresh_state, inference_engine):
    """bloom_confidence caps at 1.0 when history > 30."""
    history = [{"problem_id": f"P{i:03d}", "correct": 1, "score": 1.0, "bloom_level": "APPLY"} for i in range(50)]
    obs = _make_observation()
    ctx = _make_ctx()

    result = inference_engine.run(fresh_state, obs, ctx, history)

    assert result.bloom_confidence == 1.0


# ── run(): LLM perception (no LLM client -> skipped) ────────────────────


def test_run_skips_llm_perception_when_no_text(fresh_state, inference_engine):
    """LLM perception skipped when explanation_text is empty."""
    history = [{"problem_id": "P001", "correct": 1, "score": 1.0, "bloom_level": "APPLY"}]
    obs = Observation(
        skill_id="addition", problem_id="P001", correct=True, score=1.0,
        bloom_level=BloomLevel.APPLY, explanation_text="",
        timestamp=datetime(2026, 8, 10, 12, 0, 0),
    )
    ctx = _make_ctx()
    ctx.observation = obs

    result = inference_engine.run(fresh_state, obs, ctx, history)

    assert result.llm_perception_bloom_target is None
    assert result.llm_perception_c_confidence is None


def test_run_skips_llm_perception_when_no_client(fresh_state, inference_engine):
    """LLM perception skipped when llm_client is None (even if explanation_text present)."""
    history = [{"problem_id": "P001", "correct": 1, "score": 1.0, "bloom_level": "APPLY"}]
    obs = Observation(
        skill_id="addition", problem_id="P001", correct=True, score=1.0,
        bloom_level=BloomLevel.APPLY, explanation_text="I used a loop because...",
        timestamp=datetime(2026, 8, 10, 12, 0, 0),
    )
    ctx = _make_ctx()
    ctx.observation = obs

    result = inference_engine.run(fresh_state, obs, ctx, history)

    # llm_client is None -> perception path not entered
    assert result.llm_perception_bloom_target is None


# ── run(): TC state detection ───────────────────────────────────────────


def test_run_tc_state_computed(fresh_state, inference_engine):
    """run() calls tc_detector.detect and stores result in InferenceResult."""
    history = [{"problem_id": "P001", "correct": 1, "score": 1.0, "bloom_level": "APPLY"}]
    obs = _make_observation()
    ctx = _make_ctx()

    result = inference_engine.run(fresh_state, obs, ctx, history)

    assert result.tc_skill_id == "addition"
    assert result.tc_state is not None


# ── run(): overall_confidence ───────────────────────────────────────────


def test_run_overall_confidence_computed(fresh_state, inference_engine):
    """run() computes overall_confidence as mean of 5D confidences."""
    history = [
        {"problem_id": "P001", "correct": 1, "score": 1.0, "bloom_level": "APPLY"},
        {"problem_id": "P002", "correct": 1, "score": 1.0, "bloom_level": "APPLY"},
    ]
    obs = _make_observation()
    ctx = _make_ctx()

    result = inference_engine.run(fresh_state, obs, ctx, history)

    assert result.overall_confidence is not None
    assert 0.0 <= result.overall_confidence <= 1.0


def test_run_overall_confidence_uses_dim_updates_when_available(fresh_state, inference_engine):
    """When MIRT runs, overall_confidence uses dim_updates confidences (not state values)."""
    history = [
        {"problem_id": "P001", "correct": 1, "score": 1.0, "bloom_level": "APPLY"},
        {"problem_id": "P002", "correct": 1, "score": 1.0, "bloom_level": "APPLY"},
    ]
    obs = _make_observation()
    ctx = _make_ctx()

    result = inference_engine.run(fresh_state, obs, ctx, history)

    # Verify computed from dim_updates
    expected = float(np.mean([result.dim_updates[d]["confidence"] for d in ["K", "P", "S", "C", "X"]]))
    assert result.overall_confidence == pytest.approx(expected)


def test_run_overall_confidence_falls_back_to_state_when_no_mirt(fresh_state, inference_engine):
    """When MIRT not run (history<2), overall_confidence uses state.K/P/S/C/X.confidence."""
    # Set state confidences to known values
    for dim, conf in [("K", 0.4), ("P", 0.5), ("S", 0.6), ("C", 0.7), ("X", 0.8)]:
        d = getattr(fresh_state, dim)
        d.confidence = conf

    history = [{"problem_id": "P001", "correct": 1, "score": 1.0, "bloom_level": "APPLY"}]
    obs = _make_observation()
    ctx = _make_ctx()

    result = inference_engine.run(fresh_state, obs, ctx, history)

    expected = float(np.mean([0.4, 0.5, 0.6, 0.7, 0.8]))
    assert result.overall_confidence == pytest.approx(expected)


# ── run(): trajectory_maxlen ───────────────────────────────────────────


def test_run_sets_trajectory_maxlen(fresh_state, inference_engine):
    """run() sets trajectory_maxlen from config."""
    history = [{"problem_id": "P001", "correct": 1, "score": 1.0, "bloom_level": "APPLY"}]
    obs = _make_observation()
    ctx = _make_ctx()

    result = inference_engine.run(fresh_state, obs, ctx, history)

    assert result.trajectory_maxlen == 500


# ── run(): last_updated ────────────────────────────────────────────────


def test_run_sets_last_updated_from_observation(fresh_state, inference_engine):
    """run() sets last_updated = observation.timestamp."""
    history = [{"problem_id": "P001", "correct": 1, "score": 1.0, "bloom_level": "APPLY"}]
    obs = _make_observation()
    ctx = _make_ctx()
    expected_ts = datetime(2026, 8, 10, 12, 0, 0)
    obs.timestamp = expected_ts

    result = inference_engine.run(fresh_state, obs, ctx, history)

    assert result.last_updated == expected_ts


# ── perception_critic / misc_detector properties (lazy init) ────────────


def test_perception_critic_lazy_init_returns_object_with_none_client(inference_engine):
    """perception_critic property constructs PerceptionCritic even with llm_client=None.

    PerceptionCritic.__init__ accepts any llm_client (no validation).
    Failure manifests at .perceive() call time, not construction.
    """
    # InferenceEngine has llm_client=None -> perception_critic should still construct
    critic = inference_engine.perception_critic
    assert critic is not None
    assert critic.llm is None  # propagated


def test_misc_detector_lazy_init_returns_object_with_none_client(inference_engine):
    """misc_detector property constructs MisconceptionDetector even with llm_client=None."""
    critic = inference_engine.misc_detector
    assert critic is not None


def test_perception_critic_lazy_init_only_once(fresh_state, engine_config):
    """perception_critic is initialized once and cached."""
    from ecos.cta.l1_evolution import BKTEvolutionLayer
    from ecos.cta.l2_mirt import BiFactorMIRT5D

    mock_client = MagicMock()
    engine = InferenceEngine(
        l1=BKTEvolutionLayer(engine_config.evolution_config),
        l2=BiFactorMIRT5D(engine_config.mirt_config),
        tc_detector=TCStateDetector(),
        config=engine_config,
        llm_client=mock_client,
    )

    assert engine._perception_critic is None
    _ = engine.perception_critic
    assert engine._perception_critic is not None
    cached = engine._perception_critic
    _ = engine.perception_critic
    assert engine._perception_critic is cached  # same instance


# ── Integration: end-to-end run() ──────────────────────────────────────


def test_run_full_pipeline_returns_inference_result(fresh_state, inference_engine):
    """Full pipeline (BKT + MIRT + Bloom + TC + overall + trajectory_maxlen) returns InferenceResult."""
    history = [
        {"problem_id": "P001", "correct": 1, "score": 1.0, "bloom_level": "APPLY"},
        {"problem_id": "P002", "correct": 0, "score": 0.3, "bloom_level": "APPLY"},
        {"problem_id": "P003", "correct": 1, "score": 0.9, "bloom_level": "APPLY"},
    ]
    obs = _make_observation(score=0.8, bloom=BloomLevel.APPLY)
    ctx = _make_ctx(score=0.8, bloom=BloomLevel.APPLY)

    result = inference_engine.run(fresh_state, obs, ctx, history)

    # All expected fields populated
    assert isinstance(result, InferenceResult)
    assert result.theta_mean is not None
    assert result.theta_cov is not None
    assert len(result.dim_updates) == 5
    assert "apply" in result.bloom_field_updates
    assert result.bloom_dominant_recompute is True
    assert result.bloom_confidence is not None
    assert result.bloom_evidence_id == 3
    assert result.tc_skill_id == "addition"
    assert result.tc_state is not None
    assert result.overall_confidence is not None
    assert result.trajectory_maxlen == 500
    assert result.last_updated == obs.timestamp
