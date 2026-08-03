"""v0.72.0 P0-i: Platt Scaling 后校准测试.

背景:
  v0.71.0 P0-g 修 LinUCB A 矩阵爆炸后, reliability diagram 显示 V3 全局低估 0.54.
  v0.72.0 引入 Platt Scaling 校准 (per-student tracker), 期望:
    - PlattScaler 基础行为: identity / fit / transform
    - StudentCalibrationTracker: 冷启动期不校准, 配对足够后 refit
    - 数值正确性: 已知 sigmoid 关系, fit 后能反推 A, B
    - 校准效果: lbc003 54 样本重放, calibrated V3 ECE 应显著低于 raw V3 ECE
    - 失败兜底: 异常不污染 state, 写 raw V3 兜底

设计:
  - 测试 PlattScaler 单测 (8 个) + StudentCalibrationTracker 单测 (4 个)
  - 测试 orchestrator 集成 (2 个) + lbc003 重放 (1 个)
"""

from __future__ import annotations

import logging

import numpy as np
import pytest


# ──────────────────────────────────────────────────────────────────────
# 1. PlattScaler 基础行为
# ──────────────────────────────────────────────────────────────────────


class TestPlattScalerBasic:
    """v0.72.0: PlattScaler 基础行为."""

    def test_identity_when_unfitted(self):
        """未 fitted 时, transform 等价于 clip(raw, 0, 1)."""
        from ecos.dual_agent.calibration import PlattScaler
        scaler = PlattScaler()
        assert not scaler._fitted
        assert scaler.transform(0.5) == 0.5
        assert scaler.transform(-0.1) == 0.0
        assert scaler.transform(1.5) == 1.0

    def test_fit_too_few_samples_keeps_identity(self):
        """样本 < 2 时, fit 跳过, 保持 identity."""
        from ecos.dual_agent.calibration import PlattScaler
        scaler = PlattScaler()
        result = scaler.fit([0.5], [1.0])
        assert result is scaler
        assert not scaler._fitted
        assert scaler.transform(0.5) == 0.5

    def test_fit_recovers_known_sigmoid_params(self):
        """已知生成式: P=1|sigmoid(A*x+B), fit 后 A, B 接近真值."""
        from ecos.dual_agent.calibration import PlattScaler
        np.random.seed(42)
        # 真值: A=5.0, B=-2.0
        true_A, true_B = 5.0, -2.0
        raw = np.linspace(0.0, 1.0, 50)
        z = true_A * raw + true_B
        p = 1.0 / (1.0 + np.exp(-z))
        actuals = (np.random.rand(50) < p).astype(float)
        scaler = PlattScaler()
        scaler.fit(raw, actuals)
        assert scaler._fitted
        # A, B 应该接近真值 (有一定误差, 但符号和数量级对)
        assert scaler.A > 0, f"A 应该 > 0, got {scaler.A}"
        assert 1.0 < scaler.A < 15.0, f"A 应该在 [1, 15], got {scaler.A}"
        assert -5.0 < scaler.B < 1.0, f"B 应该在 [-5, 1], got {scaler.B}"

    def test_fit_length_mismatch_skips(self, caplog):
        """raw_confs 和 actuals 长度不一致, fit 跳过 + warning."""
        from ecos.dual_agent.calibration import PlattScaler
        scaler = PlattScaler()
        with caplog.at_level(logging.WARNING):
            result = scaler.fit([0.1, 0.2, 0.3], [0.0, 1.0])
        assert not scaler._fitted
        assert "长度不一致" in caplog.text

    def test_transform_monotonic(self):
        """fit 后 transform 单调递增."""
        from ecos.dual_agent.calibration import PlattScaler
        np.random.seed(0)
        raw = np.linspace(0.0, 1.0, 30)
        actuals = (raw > 0.5).astype(float)
        scaler = PlattScaler()
        scaler.fit(raw, actuals)
        prev = -1.0
        for r in np.linspace(0.0, 1.0, 20):
            c = scaler.transform(r)
            assert c >= prev, f"transform({r})={c} < prev {prev}, 非单调"
            prev = c

    def test_transform_bounded_0_1(self):
        """fit 后 transform 输出严格在 (0, 1)."""
        from ecos.dual_agent.calibration import PlattScaler
        np.random.seed(1)
        raw = np.random.rand(30)
        actuals = (np.random.rand(30) > 0.5).astype(float)
        scaler = PlattScaler()
        scaler.fit(raw, actuals)
        for r in [0.0, 0.1, 0.5, 0.9, 1.0, -0.5, 1.5]:
            c = scaler.transform(r)
            assert 0.0 < c < 1.0, f"transform({r})={c} 越界"

    def test_fit_transform_combined(self):
        """fit_transform 一次返回 calibrated array."""
        from ecos.dual_agent.calibration import PlattScaler
        np.random.seed(2)
        raw = np.array([0.1, 0.3, 0.5, 0.7, 0.9])
        actuals = np.array([0.0, 0.0, 1.0, 1.0, 1.0])
        scaler = PlattScaler()
        result = scaler.fit_transform(raw, actuals)
        assert len(result) == 5
        assert scaler._fitted
        # 后半段应该比前半段大 (单调性)
        assert result[2] > result[0]

    def test_fit_with_scipy_failure_keeps_identity(self, monkeypatch, caplog):
        """scipy 优化失败时, scaler 保持 identity + warning."""
        from ecos.dual_agent import calibration as calib_mod
        from ecos.dual_agent.calibration import PlattScaler

        def fake_minimize(*args, **kwargs):
            from scipy.optimize import OptimizeResult
            return OptimizeResult(x=[1.0, 0.0], success=False, fun=999.0, status=-1)

        monkeypatch.setattr(calib_mod, "minimize", fake_minimize)
        scaler = PlattScaler()
        with caplog.at_level(logging.WARNING):
            scaler.fit([0.1, 0.2, 0.3], [0.0, 1.0, 1.0])
        # 优化失败 (且没有改善), 保持 identity
        assert scaler.A == 1.0
        assert scaler.B == 0.0


# ──────────────────────────────────────────────────────────────────────
# 2. StudentCalibrationTracker
# ──────────────────────────────────────────────────────────────────────


class TestStudentCalibrationTracker:
    """v0.72.0: StudentCalibrationTracker 行为."""

    def test_cold_start_returns_raw(self):
        """冷启动期 (n_pairs < min_samples_to_fit), calibrate 返回 raw."""
        from ecos.dual_agent.calibration import StudentCalibrationTracker
        tracker = StudentCalibrationTracker(min_samples_to_fit=5)
        for i in range(4):
            tracker.add_pair(0.3, 1.0)
        assert not tracker.is_fitted
        assert tracker.calibrate(0.5) == 0.5
        assert tracker.calibrate(0.1) == 0.1

    def test_first_refit_at_min_samples(self):
        """n_pairs == min_samples_to_fit 时, 触发首次 refit."""
        from ecos.dual_agent.calibration import StudentCalibrationTracker
        np.random.seed(0)
        raw = np.full(20, 0.3) + np.random.rand(20) * 0.1
        actuals = (np.random.rand(20) < 0.8).astype(float)
        tracker = StudentCalibrationTracker(min_samples_to_fit=5)
        for r, a in zip(raw, actuals):
            tracker.add_pair(r, a)
        assert tracker.is_fitted
        assert tracker.n_pairs == 20
        # calibrate(0.3) 应该比 0.3 大 (因为实际准确率高)
        calibrated = tracker.calibrate(0.3)
        assert calibrated > 0.5, f"calibrated {calibrated} 应该 > 0.5 (因为 actual 高)"

    def test_refit_uses_all_historical_pairs(self):
        """每次 add_pair 后 refit 都用全部历史 pairs."""
        from ecos.dual_agent.calibration import StudentCalibrationTracker
        tracker = StudentCalibrationTracker(min_samples_to_fit=3)
        tracker.add_pair(0.2, 1.0)
        tracker.add_pair(0.3, 1.0)
        assert not tracker.is_fitted
        assert len(tracker._pairs) == 2
        tracker.add_pair(0.4, 1.0)
        assert tracker.is_fitted
        tracker.add_pair(0.5, 1.0)
        assert tracker.n_pairs == 4

    def test_clamp_inputs(self):
        """raw_conf 和 actual_outcome 都 clamp 到 [0, 1]."""
        from ecos.dual_agent.calibration import StudentCalibrationTracker
        tracker = StudentCalibrationTracker(min_samples_to_fit=2)
        tracker.add_pair(2.0, 1.5)
        assert tracker._pairs[0] == (1.0, 1.0)
        tracker.add_pair(-0.5, -0.5)
        assert tracker._pairs[1] == (0.0, 0.0)


# ──────────────────────────────────────────────────────────────────────
# 3. Orchestrator 集成
# ──────────────────────────────────────────────────────────────────────


class TestOrchestratorPlattScalingIntegration:
    """v0.72.0: DualAgentOrchestrator 集成 Platt Scaling."""

    def test_calibrated_field_written_after_post_process(self):
        """_post_process_calibration 触发后, calibrated 字段写入."""
        from ecos.dual_agent.orchestrator import DualAgentConfig, DualAgentOrchestrator
        from ecos.cta.belief_engine import Observation
        from ecos.cta.belief_state import BloomLevel

        orch = DualAgentOrchestrator(config=DualAgentConfig(), llm_client=None)
        sid = 'test_platt_integration'
        obs1 = Observation(
            problem_id='p1', skill_id='variables',
            correct=True, score=1.0,
            bloom_level=BloomLevel.APPLY, response_time_sec=0.0,
        )
        orch.process_observation(obs1, student_id=sid)
        assert 'dual_agent_confidence_calibrated' not in orch.intervention_history[sid][-1].metadata

        obs2 = Observation(
            problem_id='p2', skill_id='variables',
            correct=True, score=1.0,
            bloom_level=BloomLevel.APPLY, response_time_sec=0.0,
        )
        orch.process_observation(obs2, student_id=sid)
        last = orch.intervention_history[sid][-1]
        assert 'dual_agent_confidence_calibrated' in last.metadata
        # 1 pair < min_samples_to_fit=5, 走 raw_v3
        assert last.metadata['dual_agent_confidence_calibrated_source'] == 'raw_v3'
        raw = last.metadata['dual_agent_confidence']
        calibrated = last.metadata['dual_agent_confidence_calibrated']
        assert abs(raw - calibrated) < 1e-6, f"raw={raw} calibrated={calibrated}"

    def test_platt_scaling_activates_after_5_pairs(self):
        """5+ pairs 后, calibrated 走 platt_scaling source."""
        from ecos.dual_agent.orchestrator import DualAgentConfig, DualAgentOrchestrator
        from ecos.cta.belief_engine import Observation
        from ecos.cta.belief_state import BloomLevel

        orch = DualAgentOrchestrator(config=DualAgentConfig(), llm_client=None)
        sid = 'test_platt_activate'
        for i in range(8):
            obs = Observation(
                problem_id=f'p{i}', skill_id='variables',
                correct=True, score=1.0,
                bloom_level=BloomLevel.APPLY, response_time_sec=0.0,
            )
            orch.process_observation(obs, student_id=sid)

        last = orch.intervention_history[sid][-1]
        assert last.metadata['dual_agent_confidence_calibrated_source'] == 'platt_scaling'
        tracker = orch._calibration_trackers[sid]
        assert tracker.is_fitted
        # 8 rounds: round 1 V3 未写入 (early return prev=None),
        # rounds 2-7 add 6 pairs (round 8 calibrate 时, 还没 add prev=round7)
        assert tracker.n_pairs == 6


# ──────────────────────────────────────────────────────────────────────
# 4. lbc003 重放: Platt Scaling 后 ECE 改善
# ──────────────────────────────────────────────────────────────────────


class TestLbc003PlattScalingImprovement:
    """v0.72.0: lbc003 重放, raw V3 ECE vs calibrated V3 ECE."""

    def test_calibrated_ece_lower_than_raw_ece(self):
        """lbc003 56 道题重放, calibrated V3 ECE 应显著低于 raw V3 ECE.

        预期:
          - raw V3 ECE ≈ 0.57 (v0.71.0 P0-g 修复后)
          - calibrated V3 ECE < 0.40 (Platt Scaling 后)
        """
        import sqlite3, json
        from ecos.dual_agent.orchestrator import DualAgentConfig, DualAgentOrchestrator
        from ecos.cta.belief_engine import Observation
        from ecos.cta.belief_state import BloomLevel

        conn = sqlite3.connect('web/ecos.db')
        row = conn.execute("SELECT response_history FROM students WHERE student_id='lbc003'").fetchone()
        rh = json.loads(row[0])

        orch = DualAgentOrchestrator(config=DualAgentConfig(), llm_client=None)
        sid = 'test_lbc003_platt'
        bloom_map = {
            'REMEMBER': BloomLevel.REMEMBER, 'UNDERSTAND': BloomLevel.UNDERSTAND,
            'APPLY': BloomLevel.APPLY, 'ANALYZE': BloomLevel.ANALYZE,
            'EVALUATE': BloomLevel.EVALUATE, 'CREATE': BloomLevel.CREATE,
        }

        for h in rh:
            obs = Observation(
                problem_id=h['problem_id'], skill_id='variables',
                correct=bool(h.get('correct', 0)), score=float(h.get('score', 0.0)),
                bloom_level=bloom_map.get(h.get('bloom_level', 'APPLY'), BloomLevel.APPLY),
                response_time_sec=0.0,
            )
            orch.process_observation(obs, student_id=sid)

        hist = orch.intervention_history[sid]
        raw_pairs = []
        calibrated_pairs = []
        for i in range(len(hist)):
            raw = hist[i].metadata.get('dual_agent_confidence')
            calibrated = hist[i].metadata.get('dual_agent_confidence_calibrated')
            actual = hist[i].actual_outcome
            if raw is not None and calibrated is not None and actual is not None:
                raw_pairs.append((raw, actual))
                calibrated_pairs.append((calibrated, actual))

        def ece(pairs):
            return float(np.mean([abs(c - a) for c, a in pairs]))

        raw_ece = ece(raw_pairs)
        calibrated_ece = ece(calibrated_pairs)

        print(f"\nraw V3 ECE: {raw_ece:.4f} (n={len(raw_pairs)})")
        print(f"calibrated V3 ECE: {calibrated_ece:.4f} (n={len(calibrated_pairs)})")
        print(f"改善: {raw_ece - calibrated_ece:.4f}")

        assert calibrated_ece < raw_ece, (
            f"calibrated ECE ({calibrated_ece:.4f}) 应低于 raw ECE ({raw_ece:.4f})"
        )
        assert calibrated_ece < 0.40, f"calibrated ECE {calibrated_ece:.4f} 应 < 0.40"
