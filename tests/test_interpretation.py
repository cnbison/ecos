"""v0.96.6: 学习画像解读规则引擎 interpretation.py 回归测试.

覆盖:
  - v0.96.6: dominant 枚举名 → L-code 归一化 (belief.py 序列化 dominant_layer.name,
    原先 _BLOOM_LAYER_NAMES 以 "L1".."L6" 为 key 永远 miss, dominant_label 回退英文;
    WherePage 主导高亮 interp.bloom.dominant === lvl 也永远不命中)
  - v0.96.6: trajectory <2 点时不产出 delta_5d (GrowthPage Object.entries 崩溃前置条件)
  - 新鲜学生 (全 0.5 中性) 不跳 L6
"""
from __future__ import annotations

from typing import Any, Dict

from web.api.interpretation import build_interpretation


def _state(
    dominant: str = "REMEMBER",
    traj_len: int = 0,
    levels: Dict[str, float] | None = None,
) -> Dict[str, Any]:
    levels = levels or {f"L{i}": 0.5 for i in range(1, 7)}
    traj = [
        {
            "timestamp": f"2026-08-18T10:{i:02d}:00",
            "theta_5d": [round(0.1 * i, 4)] * 5,
        }
        for i in range(traj_len)
    ]
    return {
        "theta": {d: 0.0 for d in ("K", "P", "S", "C", "X")},
        "theta_confidence": {d: 0.0 for d in ("K", "P", "S", "C", "X")},
        "bloom_profile": {
            "dominant": dominant,
            "confidence": 0.5,
            "bloom_levels": levels,
        },
        "bloom_layer_distance": {"next": None, "gap": 0.0},
        "tc_states": [],
        "trajectory": traj,
        "overall_confidence": 0.3,
    }


# ─── 1. dominant 枚举名 → L-code 归一化 (v0.96.6) ────────────────────────

def test_bloom_dominant_normalized_to_l_code():
    """dominant 是枚举名 ("REMEMBER") 时, 归一化为 L-code 并给出中文 label."""
    r = build_interpretation(_state(dominant="REMEMBER"))
    bloom = r["bloom"]
    assert bloom["dominant"] == "L1"
    assert bloom["dominant_label"] == "记忆 (REMEMBER)"


def test_bloom_dominant_normalized_high_layer():
    """L3/L4/L5 全 1.0 → dominant EVALUATE → L5 + 中文 label (呼应 v0.96.5 kernel tie-break)."""
    levels = {"L1": 0.9, "L2": 0.8, "L3": 1.0, "L4": 1.0, "L5": 1.0, "L6": 0.65}
    r = build_interpretation(_state(dominant="EVALUATE", levels=levels))
    bloom = r["bloom"]
    assert bloom["dominant"] == "L5"
    assert bloom["dominant_label"] == "评价 (EVALUATE)"


def test_bloom_unprobed_computed_above_dominant():
    """v0.96.6: unprobed 原本因枚举名不在 layer_order 永远为空, 归一化后正确列出主层以上未探及层."""
    # dominant L1, L2-L6 都是中性 0.5 → 全部未探及
    r = build_interpretation(_state(dominant="REMEMBER"))
    assert r["bloom"]["unprobed_layers"] == ["L2", "L3", "L4", "L5", "L6"]


def test_bloom_unprobed_none_when_higher_probed():
    """L4 已探及 (0.7), dominant L1 → unprobed 只含 L2/L3 (L5/L6 也仍 0.5 应列出)."""
    levels = {"L1": 0.5, "L2": 0.5, "L3": 0.5, "L4": 0.7, "L5": 0.5, "L6": 0.5}
    r = build_interpretation(_state(dominant="REMEMBER", levels=levels))
    # 主层 L1 之上: L2(0.5) L3(0.5) 未探及; L4 已探及; L5/L6 仍 0.5 未探及
    assert r["bloom"]["unprobed_layers"] == ["L2", "L3", "L5", "L6"]


# ─── 2. trajectory <2 点不产出 delta_5d (GrowthPage 崩溃前置) ────────────

def test_trajectory_insufficient_no_delta_5d():
    """0 / 1 个轨迹点 → 无 delta_5d key (GrowthPage Object.entries 会崩溃, v0.96.6 前端已加 guard)."""
    r = build_interpretation(_state(traj_len=0))
    assert r["trajectory"]["length"] == 0
    assert "delta_5d" not in r["trajectory"]
    assert r["trajectory"]["trend"] == "数据不足"

    r1 = build_interpretation(_state(traj_len=1))
    assert "delta_5d" not in r1["trajectory"]


def test_trajectory_enough_produces_delta_5d():
    """≥2 个轨迹点 → delta_5d 五维差值."""
    r = build_interpretation(_state(traj_len=3))
    assert r["trajectory"]["length"] == 3
    assert r["trajectory"]["delta_5d"] == {"K": 0.2, "P": 0.2, "S": 0.2, "C": 0.2, "X": 0.2}


# ─── 3. 新鲜学生边界 ─────────────────────────────────────────────────────

def test_fresh_student_overall_sane():
    """新鲜学生不抛异常, 总评完整, next_steps 提示样本不足."""
    r = build_interpretation(_state(dominant="REMEMBER", traj_len=0))
    assert r["overall"]
    assert any("记忆 (REMEMBER)" in r["overall"] for _ in [0])
    assert any("样本" in s for s in r["next_steps"])
