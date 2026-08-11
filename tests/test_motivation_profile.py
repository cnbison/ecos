"""v0.87.0-a: Motivation Profile 测试套件.

对应 12-kernel-mapping §2.1 Motivation Profile.

测试覆盖:
- MotivationObservation (3): basic / to_dict_from_dict / validation
- MotivationProfile (6): default / add_frustration / add_engagement / add_confidence / trajectory_only / deque_maxlen
- BeliefState 集成 (4): default_motivation / to_dict_includes / from_dict_restores / add_motivation_observation_allowlisted
- evidence + edge (3): evidence_id_added / unknown_signal_type / evidence_from_dict

向后兼容:
- BeliefState.X 字段保留 (lbc001/lbc002 历史数据不变)
- 老 JSON snapshot 加载 motivation 兜底空 dict
- 防御性自检 [8] 仍 hard block (add_motivation_observation 是 allowlist)
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pytest

from ecos.cta.belief_state import BeliefState
from ecos.motivation import MotivationObservation, MotivationProfile


# ────────────────────────────────────────────────────────────────────
# MotivationObservation (3 tests)
# ────────────────────────────────────────────────────────────────────


def test_observation_basic_creation():
    """MotivationObservation 默认值 + 显式构造."""
    obs = MotivationObservation(
        timestamp=datetime(2026, 8, 11, 12, 0, 0),
        signal_type="frustration",
        value=0.7,
    )
    assert obs.signal_type == "frustration"
    assert obs.value == 0.7
    assert obs.source == "runtime"
    assert obs.evidence_id is None


def test_observation_to_dict_from_dict_roundtrip():
    """MotivationObservation.to_dict() + from_dict() round-trip 一致."""
    obs = MotivationObservation(
        timestamp=datetime(2026, 8, 11, 12, 0, 0),
        signal_type="engagement",
        value=0.6,
        source="llm_critic",
        evidence_id=123,
    )
    data = obs.to_dict()
    restored = MotivationObservation.from_dict(data)
    assert restored.signal_type == obs.signal_type
    assert abs(restored.value - obs.value) < 1e-9
    assert restored.source == obs.source
    assert restored.evidence_id == obs.evidence_id
    assert restored.timestamp == obs.timestamp


def test_observation_validation_warnings():
    """__post_init__: 非法 signal_type / value 触发 warning 但不 raise."""
    obs = MotivationObservation(
        timestamp=datetime.now(),
        signal_type="unknown_type",
        value=1.5,  # 超出 [0, 1]
    )
    # 非法值不 raise, dataclass 仍创建
    assert obs.signal_type == "unknown_type"
    assert obs.value == 1.5


# ────────────────────────────────────────────────────────────────────
# MotivationProfile (6 tests)
# ────────────────────────────────────────────────────────────────────


def test_profile_default_values():
    """MotivationProfile 默认值 (frustration=0.0 / engagement=0.5 / confidence=0.5)."""
    profile = MotivationProfile()
    assert profile.frustration == 0.0
    assert profile.engagement == 0.5
    assert profile.confidence == 0.5
    assert len(profile.recent_trajectory) == 0
    assert profile.evidence_ids == []


def test_profile_add_frustration_observation():
    """add_observation(frustration) → frustration 更新 + 追加 trajectory."""
    profile = MotivationProfile()
    obs = MotivationObservation(
        timestamp=datetime.now(),
        signal_type="frustration",
        value=0.7,
    )
    profile.add_observation(obs)
    assert profile.frustration == 0.7
    assert len(profile.recent_trajectory) == 1
    assert profile.recent_trajectory[0] == obs


def test_profile_add_engagement_observation():
    """add_observation(engagement) → engagement 更新."""
    profile = MotivationProfile()
    obs = MotivationObservation(
        timestamp=datetime.now(),
        signal_type="engagement",
        value=0.9,
    )
    profile.add_observation(obs)
    assert profile.engagement == 0.9
    assert profile.frustration == 0.0  # 不影响其他维度
    assert profile.confidence == 0.5  # 默认值保留


def test_profile_add_confidence_observation():
    """add_observation(confidence) → confidence 更新."""
    profile = MotivationProfile()
    obs = MotivationObservation(
        timestamp=datetime.now(),
        signal_type="confidence",
        value=0.8,
    )
    profile.add_observation(obs)
    assert profile.confidence == 0.8
    assert len(profile.recent_trajectory) == 1


def test_profile_trajectory_only_observation():
    """add_observation(trajectory) → 仅追加 trajectory, 不更新 current 状态."""
    profile = MotivationProfile(frustration=0.3, engagement=0.4, confidence=0.5)
    obs = MotivationObservation(
        timestamp=datetime.now(),
        signal_type="trajectory",
        value=0.5,  # value 不被读取
    )
    profile.add_observation(obs)
    # 3 维度不变
    assert profile.frustration == 0.3
    assert profile.engagement == 0.4
    assert profile.confidence == 0.5
    # trajectory 追加
    assert len(profile.recent_trajectory) == 1


def test_profile_recent_trajectory_deque_maxlen_100():
    """recent_trajectory 是 deque(maxlen=100), 第 101 个 observation 自动 truncate."""
    profile = MotivationProfile()
    # 添加 105 个 observation
    for i in range(105):
        obs = MotivationObservation(
            timestamp=datetime.now(),
            signal_type="trajectory",
            value=0.0,
        )
        profile.add_observation(obs)
    # 只保留最后 100 个
    assert len(profile.recent_trajectory) == 100


# ────────────────────────────────────────────────────────────────────
# BeliefState 集成 (4 tests)
# ────────────────────────────────────────────────────────────────────


def test_belief_state_default_motivation():
    """BeliefState() 默认 motivation=MotivationProfile()."""
    state = BeliefState(student_id="lbc_test")
    assert isinstance(state.motivation, MotivationProfile)
    assert state.motivation.frustration == 0.0
    assert state.motivation.engagement == 0.5
    assert state.motivation.confidence == 0.5
    # X 维度保留 (向后兼容, v0.86 兼容)
    assert hasattr(state, "X")
    assert state.X.dimension == "X"


def test_belief_state_to_dict_includes_motivation():
    """to_dict() 序列化 motivation (MotivationProfile.to_dict())."""
    state = BeliefState(student_id="lbc_test")
    state.motivation.frustration = 0.8
    state.motivation.confidence = 0.7
    data = state.to_dict()
    assert "motivation" in data
    assert data["motivation"]["frustration"] == 0.8
    assert data["motivation"]["confidence"] == 0.7


def test_belief_state_from_dict_restores_motivation():
    """from_dict() 恢复 motivation (MotivationProfile.from_dict)."""
    original = BeliefState(student_id="lbc_test")
    original.motivation.frustration = 0.6
    original.motivation.engagement = 0.9
    original.motivation.confidence = 0.3
    # 加 observation (trajectory 类型, 不影响 current 状态)
    obs = MotivationObservation(
        timestamp=datetime.now(),
        signal_type="trajectory",
        value=0.5,
        source="test",
    )
    original.motivation.add_observation(obs)

    data = original.to_dict()
    restored = BeliefState.from_dict(data)
    assert restored.student_id == "lbc_test"
    assert restored.motivation.frustration == 0.6
    assert restored.motivation.engagement == 0.9
    assert restored.motivation.confidence == 0.3
    assert len(restored.motivation.recent_trajectory) == 1


def test_belief_state_add_motivation_observation_allowlisted():
    """add_motivation_observation 是 allowlisted mutation (跟 append_goal 模式一致)."""
    state = BeliefState(student_id="lbc_test")
    obs = MotivationObservation(
        timestamp=datetime.now(),
        signal_type="engagement",
        value=0.8,
    )
    state.add_motivation_observation(obs)
    assert state.motivation.engagement == 0.8
    assert len(state.motivation.recent_trajectory) == 1


# ────────────────────────────────────────────────────────────────────
# evidence + edge (3 tests)
# ────────────────────────────────────────────────────────────────────


def test_observation_with_evidence_id():
    """observation 带 evidence_id → profile.evidence_ids 追加."""
    profile = MotivationProfile()
    obs = MotivationObservation(
        timestamp=datetime.now(),
        signal_type="frustration",
        value=0.6,
        evidence_id=101,
    )
    profile.add_observation(obs)
    assert profile.evidence_ids == [101]


def test_observation_unknown_signal_type_logs_warning():
    """unknown signal_type → _log.warning + 仅追加 trajectory."""
    profile = MotivationProfile()
    obs = MotivationObservation(
        timestamp=datetime.now(),
        signal_type="weird_signal",
        value=0.5,
    )
    profile.add_observation(obs)
    # 不更新任何 current 状态
    assert profile.frustration == 0.0
    assert profile.engagement == 0.5
    assert profile.confidence == 0.5
    # trajectory 仍追加
    assert len(profile.recent_trajectory) == 1


def test_profile_evidence_ids_from_dict_restored():
    """from_dict 恢复 evidence_ids 列表."""
    data = {
        "frustration": 0.5,
        "engagement": 0.6,
        "confidence": 0.7,
        "recent_trajectory": [
            {
                "timestamp": datetime.now().isoformat(),
                "signal_type": "frustration",
                "value": 0.4,
                "source": "test",
                "evidence_id": 201,
            },
        ],
        "evidence_ids": [201, 202],
    }
    profile = MotivationProfile.from_dict(data)
    assert profile.evidence_ids == [201, 202]
    assert len(profile.recent_trajectory) == 1
    assert profile.recent_trajectory[0].evidence_id == 201
