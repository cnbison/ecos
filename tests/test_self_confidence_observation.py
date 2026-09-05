"""v0.97.2 self_confidence 观测通路 test suite.

对应:
  - README 恢复期 backlog P1 "观测层补学生自评" (2026-09-05 认可排序)
  - 方案决策 (2026-09-05 讨论): A 只读校准视图 + 4 档语义化 + 强制无默认
  - 通路完全复刻 v0.97.1a skill_id 模式 (None = 未自评, 全路径不变)

覆盖:
- Observation.self_confidence 默认 None (老调用方零影响)
- Observation.to_dict / from_dict 序列化 (值 / null / 老 payload 无键)
- FeatureExtractor history_entry 透传 (见 test_feature_extractor.py)
- web submit_answer 端到端透传 (belief.py → Observation → history_entry)
- 黄金回归零 diff 依据: baseline 只快照 belief state 数值维度,
  history_entry / event payload 不入基线 (test_golden_regression.py::_dim_snapshot)
"""
from __future__ import annotations

from datetime import datetime

import pytest

from ecos.cta.belief_engine import Observation
from ecos.cta.belief_state import BloomLevel


# ── Observation 默认值与序列化 ────────────────────────────────────────


def _make_obs(**kwargs) -> Observation:
    defaults = dict(
        skill_id="python.loops",
        problem_id="P001",
        correct=True,
        score=1.0,
        bloom_level=BloomLevel.APPLY,
        timestamp=datetime(2026, 9, 5, 12, 0, 0),
    )
    defaults.update(kwargs)
    return Observation(**defaults)


class TestObservationSelfConfidence:
    def test_default_is_none(self):
        """v0.97.2: 不传 self_confidence 默认 None (老调用方零影响)."""
        obs = _make_obs()
        assert obs.self_confidence is None

    def test_to_dict_serializes_value(self):
        d = _make_obs(self_confidence=0.9).to_dict()
        assert d["self_confidence"] == 0.9

    def test_to_dict_serializes_none_as_null(self):
        d = _make_obs().to_dict()
        assert d["self_confidence"] is None

    def test_roundtrip_value(self):
        obs = _make_obs(self_confidence=0.3)
        restored = Observation.from_dict(obs.to_dict())
        assert restored.self_confidence == pytest.approx(0.3)

    def test_from_dict_old_payload_without_key(self):
        """老 payload (v0.97.1 及之前) 无 self_confidence 键 → None 不炸."""
        d = _make_obs().to_dict()
        del d["self_confidence"]
        restored = Observation.from_dict(d)
        assert restored.self_confidence is None

    def test_from_dict_null_value(self):
        d = _make_obs().to_dict()
        assert d["self_confidence"] is None
        restored = Observation.from_dict(d)
        assert restored.self_confidence is None


# ── web submit_answer 端到端透传 ──────────────────────────────────────


class TestSubmitAnswerPassthrough:
    def test_submit_answer_passes_self_confidence_to_history(self):
        """submit_answer(self_confidence=0.7) → history_entry 末条带 0.7."""
        from web.api.belief import submit_answer, _get_or_create_student

        sid = "test_self_conf_passthrough"
        submit_answer(
            student_id=sid,
            problem_id="P1",
            skill_id="S1",
            correct=True,
            bloom_layer="L2",
            user_answer="ans",
            correct_answer="ans",
            self_confidence=0.7,
        )
        engine = _get_or_create_student(sid)["engine"]
        history = engine._response_history[sid]
        assert history[-1]["self_confidence"] == pytest.approx(0.7)

    def test_submit_answer_without_self_confidence_is_none(self):
        """老调用方不传 → history_entry 自评为 None (未自评), 引擎行为不变."""
        from web.api.belief import submit_answer, _get_or_create_student

        sid = "test_self_conf_legacy"
        submit_answer(
            student_id=sid,
            problem_id="P1",
            skill_id="S1",
            correct=False,
            bloom_layer="L2",
            user_answer="ans",
            correct_answer="ans",
        )
        engine = _get_or_create_student(sid)["engine"]
        history = engine._response_history[sid]
        assert history[-1]["self_confidence"] is None
