"""v0.69.0-c: calibration_log dual_agent_confidence 字段落盘测试.

目标 (按 v0.69.0 PRD §3.3 + §7.3):
  1. _write_calibration_log 把 dual_agent_confidence + dual_agent_confidence_source 落盘
  2. 老数据 (v0.69.0 之前) 没这 2 字段 -> compute_h3_ece V3 优先逻辑跳过 (V2/V1 兜底)
  3. 失败兜底: 拿 confidence 失败 -> 留 None, 不阻断 calibration_log 落盘

防御性自检 [1]: 失败 _log.debug, 不 silent pass
防御性自检 [5]: 老数据兼容 (None 字段)
"""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock, patch

import pytest


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def fresh_dual_agent_state():
    """清理 dual_agent 模块状态 + DB 里 test 状态."""
    import web.api.dual_agent as da_mod
    from ecos.persistence.dual_agent_store import get_dual_agent_store

    da_mod._orch = None
    da_mod._loaded_students = set()
    da_mod.DUAL_AGENT_ENABLED = False

    for sid in ("test_da_conf_log",):
        try:
            get_dual_agent_store().delete_state(sid)
        except Exception:
            pass

    # 清 calibration_log
    try:
        from ecos.persistence.db import get_db
        db = get_db()
        db.execute(
            "DELETE FROM calibration_log WHERE student_id = ?",
            ("test_da_conf_log",),
        )
        db.commit()
    except Exception:
        pass

    yield da_mod


# ──────────────────────────────────────────────────────────────────────
# 1. _write_calibration_log 落盘 dual_agent_confidence
# ──────────────────────────────────────────────────────────────────────


class TestCalibrationLogDualConfidenceField:
    """v0.69.0-c: _write_calibration_log 把 dual_agent_confidence 落盘."""

    def test_message_payload_contains_dual_agent_confidence_fields(self):
        """message_payload 含 dual_agent_confidence + dual_agent_confidence_source 字段."""
        # 直接调 _write_calibration_log, mock DB
        from web.api.dual_agent import _write_calibration_log

        # 构造 mock result + mock orch
        mock_result = MagicMock()
        mock_result.intervention.intervention_id = "iv-001"
        mock_result.intervention.intervention_type.value = "explanatory"
        mock_result.bloom_target.name = "UNDERSTAND"
        mock_result.expected_gain = 0.5
        mock_result.expected_risk = 0.1
        mock_result.rationale = "test rationale"
        mock_result.actual_outcome = 0.8
        mock_result.degraded_mode = False
        mock_result.calibration_round = 1
        mock_result.metadata = {
            "dual_agent_confidence": 0.72,
            "dual_agent_confidence_source": "linucb",
        }

        mock_orch = MagicMock()
        mock_orch.state = {}
        mock_orch.get_belief_challenges.return_value = []

        # mock db.save_calibration 捕获 message_payload
        captured_payload = {}

        def fake_save_calibration(sid, data):
            captured_payload.update(data.get("message_payload", {}))
            return 1

        with patch("ecos.persistence.db.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.save_calibration = fake_save_calibration
            mock_get_db.return_value = mock_db

            _write_calibration_log(
                student_id="test_da_conf_log",
                result=mock_result,
                orch=mock_orch,
                duration_ms=100,
            )

        # 验证 message_payload 含 v0.69.0 新字段
        assert "dual_agent_confidence" in captured_payload
        assert "dual_agent_confidence_source" in captured_payload
        assert captured_payload["dual_agent_confidence"] == 0.72
        assert captured_payload["dual_agent_confidence_source"] == "linucb"

    def test_message_payload_handles_missing_metadata(self):
        """result.metadata 没有 dual_agent_confidence -> 字段为 None (老数据兼容)."""
        from web.api.dual_agent import _write_calibration_log

        mock_result = MagicMock()
        mock_result.intervention.intervention_id = "iv-002"
        mock_result.intervention.intervention_type.value = "explanatory"
        mock_result.bloom_target.name = "UNDERSTAND"
        mock_result.expected_gain = 0.5
        mock_result.expected_risk = 0.1
        mock_result.rationale = "test rationale"
        mock_result.actual_outcome = 0.8
        mock_result.degraded_mode = False
        mock_result.calibration_round = 1
        mock_result.metadata = {}  # 空 metadata (老数据 / 冷启动期没填)

        mock_orch = MagicMock()
        mock_orch.state = {}
        mock_orch.get_belief_challenges.return_value = []

        captured_payload = {}

        def fake_save_calibration(sid, data):
            captured_payload.update(data.get("message_payload", {}))
            return 1

        with patch("ecos.persistence.db.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.save_calibration = fake_save_calibration
            mock_get_db.return_value = mock_db

            _write_calibration_log(
                student_id="test_da_conf_log",
                result=mock_result,
                orch=mock_orch,
                duration_ms=100,
            )

        # 字段存在但为 None (老数据兼容)
        assert "dual_agent_confidence" in captured_payload
        assert "dual_agent_confidence_source" in captured_payload
        assert captured_payload["dual_agent_confidence"] is None
        assert captured_payload["dual_agent_confidence_source"] is None

    def test_message_payload_handles_none_metadata(self):
        """result.metadata 是 None (没 metadata 属性) -> 字段为 None."""
        from web.api.dual_agent import _write_calibration_log

        mock_result = MagicMock()
        mock_result.intervention.intervention_id = "iv-003"
        mock_result.intervention.intervention_type.value = "explanatory"
        mock_result.bloom_target.name = "UNDERSTAND"
        mock_result.expected_gain = 0.5
        mock_result.expected_risk = 0.1
        mock_result.rationale = "test"
        mock_result.actual_outcome = 0.8
        mock_result.degraded_mode = False
        mock_result.calibration_round = 1
        # mock_result.metadata 返回 None (getattr 默认值)
        mock_result.metadata = None

        mock_orch = MagicMock()
        mock_orch.state = {}
        mock_orch.get_belief_challenges.return_value = []

        captured_payload = {}

        def fake_save_calibration(sid, data):
            captured_payload.update(data.get("message_payload", {}))
            return 1

        with patch("ecos.persistence.db.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.save_calibration = fake_save_calibration
            mock_get_db.return_value = mock_db

            # 不应 raise
            _write_calibration_log(
                student_id="test_da_conf_log",
                result=mock_result,
                orch=mock_orch,
                duration_ms=100,
            )

        # 字段为 None
        assert captured_payload["dual_agent_confidence"] is None
        assert captured_payload["dual_agent_confidence_source"] is None

    def test_estimate_gain_fallback_source_recorded(self):
        """冷启动期 source="estimate_gain_fallback" 也落盘."""
        from web.api.dual_agent import _write_calibration_log

        mock_result = MagicMock()
        mock_result.intervention.intervention_id = "iv-004"
        mock_result.intervention.intervention_type.value = "explanatory"
        mock_result.bloom_target.name = "UNDERSTAND"
        mock_result.expected_gain = 0.5
        mock_result.expected_risk = 0.1
        mock_result.rationale = "test"
        mock_result.actual_outcome = 0.8
        mock_result.degraded_mode = False
        mock_result.calibration_round = 1
        mock_result.metadata = {
            "dual_agent_confidence": 0.42,
            "dual_agent_confidence_source": "estimate_gain_fallback",
        }

        mock_orch = MagicMock()
        mock_orch.state = {}
        mock_orch.get_belief_challenges.return_value = []

        captured_payload = {}

        def fake_save_calibration(sid, data):
            captured_payload.update(data.get("message_payload", {}))
            return 1

        with patch("ecos.persistence.db.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.save_calibration = fake_save_calibration
            mock_get_db.return_value = mock_db

            _write_calibration_log(
                student_id="test_da_conf_log",
                result=mock_result,
                orch=mock_orch,
                duration_ms=100,
            )

        assert captured_payload["dual_agent_confidence"] == 0.42
        assert captured_payload["dual_agent_confidence_source"] == "estimate_gain_fallback"


# ──────────────────────────────────────────────────────────────────────
# 2. 失败兜底 (防御性自检 [1])
# ──────────────────────────────────────────────────────────────────────


class TestCalibrationLogDualConfidenceFailure:
    """v0.69.0-c: 拿 dual_agent_confidence 失败 -> 留 None, 不阻断."""

    def test_failure_does_not_block_calibration_log(self):
        """拿 metadata 失败 -> 字段 None, 仍正常落盘 calibration_log."""
        from web.api.dual_agent import _write_calibration_log

        mock_result = MagicMock()
        mock_result.intervention.intervention_id = "iv-005"
        mock_result.intervention.intervention_type.value = "explanatory"
        mock_result.bloom_target.name = "UNDERSTAND"
        mock_result.expected_gain = 0.5
        mock_result.expected_risk = 0.1
        mock_result.rationale = "test"
        mock_result.actual_outcome = 0.8
        mock_result.degraded_mode = False
        mock_result.calibration_round = 1
        # 让 metadata 抛异常
        type(mock_result).metadata = property(lambda self: (_ for _ in ()).throw(
            RuntimeError("模拟 metadata 读失败")
        ))

        mock_orch = MagicMock()
        mock_orch.state = {}
        mock_orch.get_belief_challenges.return_value = []

        save_called = []

        def fake_save_calibration(sid, data):
            save_called.append(data.get("message_payload", {}))
            return 1

        with patch("ecos.persistence.db.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.save_calibration = fake_save_calibration
            mock_get_db.return_value = mock_db

            # 不应 raise
            _write_calibration_log(
                student_id="test_da_conf_log",
                result=mock_result,
                orch=mock_orch,
                duration_ms=100,
            )

        # 仍正常落盘
        assert len(save_called) == 1
        # dual_agent_confidence 字段为 None
        assert save_called[0]["dual_agent_confidence"] is None

    def test_failure_logs_debug(self, caplog):
        """失败时 _log.debug, 不 silent pass (防御性自检 [1])."""
        from web.api.dual_agent import _write_calibration_log

        mock_result = MagicMock()
        mock_result.intervention.intervention_id = "iv-006"
        mock_result.intervention.intervention_type.value = "explanatory"
        mock_result.bloom_target.name = "UNDERSTAND"
        mock_result.expected_gain = 0.5
        mock_result.expected_risk = 0.1
        mock_result.rationale = "test"
        mock_result.actual_outcome = 0.8
        mock_result.degraded_mode = False
        mock_result.calibration_round = 1
        type(mock_result).metadata = property(lambda self: (_ for _ in ()).throw(
            RuntimeError("模拟失败")
        ))

        mock_orch = MagicMock()
        mock_orch.state = {}
        mock_orch.get_belief_challenges.return_value = []

        with patch("ecos.persistence.db.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.save_calibration = lambda sid, data: 1
            mock_get_db.return_value = mock_db

            with caplog.at_level(logging.DEBUG, logger="web.api.dual_agent"):
                _write_calibration_log(
                    student_id="test_da_conf_log",
                    result=mock_result,
                    orch=mock_orch,
                    duration_ms=100,
                )

        # 应该有 debug log
        assert any(
            "拿 dual_agent_confidence 失败" in rec.message
            for rec in caplog.records
        ), "失败时应该 _log.debug, 不能 silent pass"


# ──────────────────────────────────────────────────────────────────────
# 3. v0.68.0 state_overall_confidence 字段不受影响 (向后兼容)
# ──────────────────────────────────────────────────────────────────────


class TestStateOverallConfidenceUnchanged:
    """v0.69.0-c: v0.68.0 的 state_overall_confidence 字段不受影响."""

    def test_state_overall_confidence_still_written(self):
        """v0.68.0 state_overall_confidence 字段仍正常落盘 (V2 兼容)."""
        from web.api.dual_agent import _write_calibration_log

        mock_result = MagicMock()
        mock_result.intervention.intervention_id = "iv-007"
        mock_result.intervention.intervention_type.value = "explanatory"
        mock_result.bloom_target.name = "UNDERSTAND"
        mock_result.expected_gain = 0.5
        mock_result.expected_risk = 0.1
        mock_result.rationale = "test"
        mock_result.actual_outcome = 0.8
        mock_result.degraded_mode = False
        mock_result.calibration_round = 1
        mock_result.metadata = {
            "dual_agent_confidence": 0.65,
            "dual_agent_confidence_source": "linucb",
        }

        # mock orch.state 含 overall_confidence
        mock_state = MagicMock()
        mock_state.overall_confidence = 0.55
        mock_orch = MagicMock()
        mock_orch.state = {"test_da_conf_log": mock_state}
        mock_orch.get_belief_challenges.return_value = []

        captured_payload = {}

        def fake_save_calibration(sid, data):
            captured_payload.update(data.get("message_payload", {}))
            return 1

        with patch("ecos.persistence.db.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.save_calibration = fake_save_calibration
            mock_get_db.return_value = mock_db

            _write_calibration_log(
                student_id="test_da_conf_log",
                result=mock_result,
                orch=mock_orch,
                duration_ms=100,
            )

        # v0.68.0 字段仍正常
        assert captured_payload["state_overall_confidence"] == 0.55
        # v0.69.0 字段也正常
        assert captured_payload["dual_agent_confidence"] == 0.65
        assert captured_payload["dual_agent_confidence_source"] == "linucb"
