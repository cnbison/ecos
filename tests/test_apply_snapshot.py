"""v0.77.1: BeliefState.apply_snapshot() 测试套件.

评估文档 §6.2 方案 B - DB 恢复路径单一入口.
详见 discussions/2026-08-05-v077-p2-state-engine-evaluation.md

拦截范围:
- apply_snapshot 接管 6 字段 (theta_mean / theta_cov / bloom_profile / learning_dna / overall_confidence / C.tc_states)
- 不接管 trajectory (snap.bloom_profile 共享当前 state, from_dict 会用 default 退化 dominant_layer)
- 不接管 K/P/S/C/X dim 派生字段 (caller 后续重算)
- 不动 student_id (caller 控制 sid 兜底)

拦截历史 (CLAUDE.md §防御性自检 [5]):
- v0.46.5 import json 漏 (3-tuple -> dict 迁移)
- v0.47.4 item_params 漏 (MIRT K 暴跌 0.91)
- v0.47.5 trajectory / tc_states 漏
- v0.47.9 theta_cov 漏
- v0.49.2 response_history 改 dict 格式
- v0.52.0 misconception_hits 漏
"""
from datetime import datetime

import numpy as np
import pytest

from ecos.cta.belief_state import (
    BeliefState,
    BloomLevel,
    ConfidenceDimensionState,
    DimensionState,
    LearningDNAState,
    TCState,
)


@pytest.fixture
def baseline_state() -> BeliefState:
    """构造一个 baseline state, 各字段都是非 default 值, 用于 apply 后比对."""
    state = BeliefState(student_id="lbc_test")
    state.K = DimensionState(theta=1.5, se=0.5, mastery_prob=0.8, confidence=0.6, dimension="K")
    state.P = DimensionState(theta=0.3, se=0.4, mastery_prob=0.6, confidence=0.7, dimension="P")
    state.S = DimensionState(theta=-0.2, se=0.6, mastery_prob=0.4, confidence=0.5, dimension="S")
    state.C = ConfidenceDimensionState(
        theta=0.1, se=0.3, mastery_prob=0.55, confidence=0.65, dimension="C",
        tc_states={"TC1": TCState(tc_id="TC1", status="liminal", progress=0.5)},
    )
    state.X = DimensionState(theta=0.0, se=0.5, mastery_prob=0.5, confidence=0.5, dimension="X")
    state.theta_mean = np.array([1.5, 0.3, -0.2, 0.1, 0.0])
    state.theta_cov = np.eye(5) * 2.0
    state.bloom_profile.remember = 0.9
    state.bloom_profile.understand = 0.7
    state.bloom_profile.apply = 0.5
    state.bloom_profile.analyze = 0.3
    state.bloom_profile.evaluate = 0.2
    state.bloom_profile.create = 0.1
    state.bloom_profile.confidence = 0.8
    state.bloom_profile.update_dominant()
    state.learning_dna = LearningDNAState(
        input_preference="auditory",
        feedback_preference="delayed",
        fatigue_pattern={"morning": 0.3},
        error_pattern=["off_by_one"],
        motivation_pattern={"challenge": 0.6},
        confidence=0.7,
    )
    state.overall_confidence = 0.65
    return state


# ─── 1. 6 字段恢复测试 ────────────────────────────────────────────────────

def test_apply_snapshot_restores_theta_mean(baseline_state: BeliefState):
    """theta_mean 从 snapshot 恢复 (np.array 转换)."""
    snapshot = {"theta_mean": [2.0, 1.0, 0.5, -0.3, 0.0]}
    baseline_state.apply_snapshot(snapshot)
    assert np.allclose(baseline_state.theta_mean, [2.0, 1.0, 0.5, -0.3, 0.0])
    assert baseline_state.theta_mean.dtype == np.float64


def test_apply_snapshot_restores_theta_cov(baseline_state: BeliefState):
    """theta_cov 从 snapshot 恢复 (5x5 形状校验)."""
    cov = [[1.0, 0.1, 0.0, 0.0, 0.0],
           [0.1, 1.0, 0.0, 0.0, 0.0],
           [0.0, 0.0, 1.0, 0.0, 0.0],
           [0.0, 0.0, 0.0, 1.0, 0.0],
           [0.0, 0.0, 0.0, 0.0, 1.0]]
    baseline_state.apply_snapshot({"theta_cov": cov})
    assert np.allclose(baseline_state.theta_cov, np.array(cov))


def test_apply_snapshot_restores_bloom_profile(baseline_state: BeliefState):
    """bloom_profile 6 层概率 + confidence + update_dominant."""
    snapshot = {"bloom_profile": {
        "remember": 0.3, "understand": 0.4, "apply": 0.6,
        "analyze": 0.8, "evaluate": 0.5, "create": 0.2,
        "confidence": 0.9,
    }}
    baseline_state.apply_snapshot(snapshot)
    assert baseline_state.bloom_profile.remember == 0.3
    assert baseline_state.bloom_profile.analyze == 0.8
    assert baseline_state.bloom_profile.confidence == 0.9
    # update_dominant 被调用 -> dominant 是 analyze (L4, 0.8 最高)
    assert baseline_state.bloom_profile.dominant_layer == BloomLevel.ANALYZE


def test_update_dominant_tie_breaks_to_highest_layer(baseline_state: BeliefState):
    """v0.96.4: 并列概率取最高层 — L3/L4/L5 同值 1.0 → EVALUATE (原 argmax 取 L3, 成长被低估)."""
    baseline_state.apply_snapshot({"bloom_profile": {
        "remember": 0.85, "understand": 0.75, "apply": 1.0,
        "analyze": 1.0, "evaluate": 1.0, "create": 0.65,
    }})
    assert baseline_state.bloom_profile.dominant_layer == BloomLevel.EVALUATE


def test_update_dominant_neutral_all_zero5_stays_lowest(baseline_state: BeliefState):
    """v0.96.4 边界: 全部 0.5 中性基线 → 不跳 L6, 取最底层 L1."""
    baseline_state.apply_snapshot({"bloom_profile": {
        "remember": 0.5, "understand": 0.5, "apply": 0.5,
        "analyze": 0.5, "evaluate": 0.5, "create": 0.5,
    }})
    assert baseline_state.bloom_profile.dominant_layer == BloomLevel.REMEMBER


def test_apply_snapshot_restores_learning_dna(baseline_state: BeliefState):
    """learning_dna 6 字段全恢复."""
    snapshot = {"learning_dna": {
        "input_preference": "kinesthetic",
        "feedback_preference": "immediate",
        "fatigue_pattern": {"evening": 0.5},
        "error_pattern": ["syntax", "logic"],
        "motivation_pattern": {"mastery": 0.8},
        "confidence": 0.85,
    }}
    baseline_state.apply_snapshot(snapshot)
    assert baseline_state.learning_dna.input_preference == "kinesthetic"
    assert baseline_state.learning_dna.feedback_preference == "immediate"
    assert baseline_state.learning_dna.fatigue_pattern == {"evening": 0.5}
    assert baseline_state.learning_dna.error_pattern == ["syntax", "logic"]
    assert baseline_state.learning_dna.motivation_pattern == {"mastery": 0.8}
    assert baseline_state.learning_dna.confidence == 0.85


def test_apply_snapshot_restores_overall_confidence(baseline_state: BeliefState):
    """overall_confidence 从 DB confidence column 恢复."""
    baseline_state.apply_snapshot({"overall_confidence": 0.42})
    assert baseline_state.overall_confidence == 0.42


def test_apply_snapshot_restores_tc_states(baseline_state: BeliefState):
    """C.tc_states 从 snapshot['C']['tc_states'] 恢复."""
    snapshot = {"C": {"tc_states": {
        "TC_func": {
            "tc_id": "TC_func",
            "status": "post_liminal",
            "progress": 0.9,
            "confidence": 0.85,
            "liminal_signals": ["signal_a", "signal_b"],
            "post_liminal_jump_detected": True,
            "irreversible": True,
            "timestamp": "2026-08-05T10:30:00",
        },
        "TC_loop": {
            "tc_id": "TC_loop",
            "status": "liminal",
            "progress": 0.5,
            "confidence": 0.6,
            "liminal_signals": [],
            "post_liminal_jump_detected": False,
            "irreversible": False,
            "timestamp": "2026-08-05T11:00:00",
        },
    }}}
    baseline_state.apply_snapshot(snapshot)
    assert "TC_func" in baseline_state.C.tc_states
    assert "TC_loop" in baseline_state.C.tc_states
    tc_func = baseline_state.C.tc_states["TC_func"]
    assert tc_func.status == "post_liminal"
    assert tc_func.progress == 0.9
    assert tc_func.confidence == 0.85
    assert tc_func.liminal_signals == ["signal_a", "signal_b"]
    assert tc_func.post_liminal_jump_detected is True
    assert tc_func.irreversible is True
    assert tc_func.timestamp == datetime.fromisoformat("2026-08-05T10:30:00")


# ─── 2. 不接管字段测试 ───────────────────────────────────────────────────

def test_apply_snapshot_does_not_touch_student_id(baseline_state: BeliefState):
    """student_id 不动 (caller 控制 sid 兜底)."""
    snapshot = {"student_id": "DIFFERENT_ID", "theta_mean": [1, 2, 3, 4, 5]}
    baseline_state.apply_snapshot(snapshot)
    assert baseline_state.student_id == "lbc_test"


def test_apply_snapshot_does_not_touch_trajectory(baseline_state: BeliefState):
    """trajectory 不接管 (snap.bloom_profile 共享当前 state 行为不变).

    拦截历史: trajectory 用 from_dict 会用 default BloomProfileState 退化 dominant_layer -> L1,
    而 belief.py 现状是 snap.bloom_profile = state.bloom_profile 共享当前. v0.77.1 保持现状.
    """
    # baseline trajectory 是空, apply_snapshot 后还是空
    assert len(baseline_state.trajectory.snapshots) == 0
    baseline_state.apply_snapshot({"trajectory": {"snapshots": [{"timestamp": "2026-08-05T10:00:00"}]}})
    assert len(baseline_state.trajectory.snapshots) == 0  # 仍空, 没接管


def test_apply_snapshot_does_not_touch_dim_fields(baseline_state: BeliefState):
    """K/P/S/C/X 的 dim 派生字段 (theta/se/mastery_prob/confidence) 不接管.

    拦截历史: caller 在 apply 后重算 dim 字段 (belief.py:289-330),
    apply_snapshot 接管 dim 字段会跟重算逻辑冲突.
    """
    # baseline K.theta = 1.5
    assert baseline_state.K.theta == 1.5
    # apply 含 K 字段, 但 apply_snapshot 不接管
    baseline_state.apply_snapshot({"K": {"theta": 99.0, "se": 0.1}})
    assert baseline_state.K.theta == 1.5  # 没变


# ─── 3. 选择性应用 + 边界 case ────────────────────────────────────────────

def test_apply_snapshot_partial_snapshot(baseline_state: BeliefState):
    """只传部分字段, 其他字段保留原值 (fail-soft)."""
    original_theta = baseline_state.theta_mean.copy()
    baseline_state.apply_snapshot({"overall_confidence": 0.99})
    # overall_confidence 改了
    assert baseline_state.overall_confidence == 0.99
    # theta_mean 没动
    assert np.allclose(baseline_state.theta_mean, original_theta)


def test_apply_snapshot_empty_snapshot(baseline_state: BeliefState):
    """空 snapshot 不破坏任何字段."""
    original = baseline_state.to_dict()
    baseline_state.apply_snapshot({})
    # 字段都没变
    assert np.allclose(baseline_state.theta_mean, original["theta_mean"])
    assert baseline_state.overall_confidence == original["overall_confidence"]


def test_apply_snapshot_skips_invalid_theta_cov(baseline_state: BeliefState):
    """theta_cov 形状不对 (非 5x5) 跳过, 保留原值."""
    original_cov = baseline_state.theta_cov.copy()
    baseline_state.apply_snapshot({"theta_cov": [[1, 2], [3, 4]]})  # 2x2 不是 5x5
    assert np.allclose(baseline_state.theta_cov, original_cov)  # 没动


def test_apply_snapshot_skips_non_list_theta_cov(baseline_state: BeliefState):
    """theta_cov 非 list (如 None / str) 跳过."""
    original_cov = baseline_state.theta_cov.copy()
    baseline_state.apply_snapshot({"theta_cov": None})
    assert np.allclose(baseline_state.theta_cov, original_cov)


def test_apply_snapshot_tc_state_broken_timestamp(baseline_state: BeliefState):
    """tc_state timestamp 解析失败兜底 datetime.now()."""
    snapshot = {"C": {"tc_states": {
        "TC_broken": {
            "tc_id": "TC_broken",
            "status": "pre_liminal",
            "progress": 0.0,
            "confidence": 0.0,
            "liminal_signals": [],
            "post_liminal_jump_detected": False,
            "irreversible": False,
            "timestamp": "INVALID_FORMAT",
        },
    }}}
    before = datetime.now()
    baseline_state.apply_snapshot(snapshot)
    after = datetime.now()
    tc = baseline_state.C.tc_states["TC_broken"]
    # timestamp 应该是 datetime.now() 兜底
    assert before <= tc.timestamp <= after


def test_apply_snapshot_tc_state_missing_timestamp(baseline_state: BeliefState):
    """tc_state timestamp 缺失兜底 datetime.now()."""
    snapshot = {"C": {"tc_states": {
        "TC_no_ts": {
            "tc_id": "TC_no_ts",
            "status": "pre_liminal",
            "progress": 0.0,
            "confidence": 0.0,
        },
    }}}
    before = datetime.now()
    baseline_state.apply_snapshot(snapshot)
    after = datetime.now()
    tc = baseline_state.C.tc_states["TC_no_ts"]
    assert before <= tc.timestamp <= after


def test_apply_snapshot_tc_state_missing_tc_id(baseline_state: BeliefState):
    """tc_data 缺 tc_id 时用 dict key 兜底 (belief.py 现状行为)."""
    snapshot = {"C": {"tc_states": {
        "TC_from_key": {
            "status": "liminal",
            "progress": 0.5,
        },
    }}}
    baseline_state.apply_snapshot(snapshot)
    tc = baseline_state.C.tc_states["TC_from_key"]
    assert tc.tc_id == "TC_from_key"  # 用 dict key 兜底


def test_apply_snapshot_empty_tc_states(baseline_state: BeliefState):
    """snapshot['C']['tc_states'] 是空 dict, 不破坏现有 tc_states."""
    # baseline 有 TC1
    assert "TC1" in baseline_state.C.tc_states
    baseline_state.apply_snapshot({"C": {"tc_states": {}}})
    assert "TC1" in baseline_state.C.tc_states  # 没清空


# ─── 4. 端到端 DB 恢复路径测试 (模拟 belief.py _get_or_create_student) ──────

def test_apply_snapshot_simulates_db_restore_path(baseline_state: BeliefState):
    """模拟 belief.py _get_or_create_student 的 DB 恢复路径:
    构造 snapshot dict (含 6 字段) -> apply_snapshot -> 验证字段恢复.
    """
    snapshot = {
        "theta_mean": [0.5, -0.3, 0.8, 0.2, -0.1],
        "theta_cov": [[0.5, 0, 0, 0, 0], [0, 0.4, 0, 0, 0], [0, 0, 0.3, 0, 0],
                       [0, 0, 0, 0.2, 0], [0, 0, 0, 0, 0.1]],
        "bloom_profile": {
            "remember": 0.8, "understand": 0.6, "apply": 0.4,
            "analyze": 0.2, "evaluate": 0.1, "create": 0.05,
            "confidence": 0.7,
        },
        "learning_dna": {
            "input_preference": "visual",
            "feedback_preference": "immediate",
            "fatigue_pattern": {},
            "error_pattern": [],
            "motivation_pattern": {},
            "confidence": 0.5,
        },
        "overall_confidence": 0.55,
        "C": {"tc_states": {
            "TC_test": {
                "tc_id": "TC_test",
                "status": "liminal",
                "progress": 0.4,
                "confidence": 0.5,
                "liminal_signals": ["s1"],
                "post_liminal_jump_detected": False,
                "irreversible": False,
                "timestamp": "2026-08-05T12:00:00",
            },
        }},
    }
    baseline_state.apply_snapshot(snapshot)
    # 验证 6 字段全恢复
    assert np.allclose(baseline_state.theta_mean, [0.5, -0.3, 0.8, 0.2, -0.1])
    assert np.allclose(baseline_state.theta_cov.diagonal(), [0.5, 0.4, 0.3, 0.2, 0.1])
    assert baseline_state.bloom_profile.remember == 0.8
    assert baseline_state.bloom_profile.confidence == 0.7
    assert baseline_state.learning_dna.input_preference == "visual"
    assert baseline_state.overall_confidence == 0.55
    assert baseline_state.C.tc_states["TC_test"].status == "liminal"


# ─── 5. 单元测试: 用 to_dict 输出做 round-trip ────────────────────────────

def test_apply_snapshot_round_trip_with_to_dict(baseline_state: BeliefState):
    """to_dict -> apply_snapshot 应等价 from_dict (在 apply_snapshot 接管字段范围内).

    验证 apply_snapshot 跟 from_dict 行为一致 (在 6 字段范围内).
    """
    snapshot = baseline_state.to_dict()
    # 新建空 state, apply snapshot
    new_state = BeliefState(student_id="new")
    new_state.apply_snapshot(snapshot)
    # 验证 6 字段都恢复
    assert np.allclose(new_state.theta_mean, baseline_state.theta_mean)
    assert np.allclose(new_state.theta_cov, baseline_state.theta_cov)
    assert new_state.bloom_profile.remember == baseline_state.bloom_profile.remember
    assert new_state.learning_dna.input_preference == baseline_state.learning_dna.input_preference
    assert new_state.overall_confidence == baseline_state.overall_confidence
    assert "TC1" in new_state.C.tc_states
