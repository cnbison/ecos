"""Tests for LearningEvent.from_pomdp_diagnostic_updated factory (v0.94.0-c).

对应 12-kernel-mapping §2.4 Event 统一输入 + Phase 7+ 抽象推演 #7.

5 tests covering:
    - factory 接受 POMDPDiagnostic 实例 (to_dict 路径)
    - factory 接受 dict (PluginRuntime 内调用时是 dict)
    - factory 拒绝非 POMDPDiagnostic / 非 dict 类型 raise TypeError
    - event_type 是 "pomdp_diagnostic_updated" (Plugin-internal topic)
    - payload 含 diagnostic 序列化 dict
"""

from __future__ import annotations

import datetime
from typing import Any, Dict

import numpy as np
import pytest

from ecos.cta.event_log import LearningEvent, LearningEventType
from ecos.lca.l4_optimization.pomdp_diagnostic import (
    POMDPDiagnostic,
    RewardPosteriorSnapshot,
    SCHEMA_VERSION as POMDP_DIAG_SCHEMA,
    TransitionPosteriorSnapshot,
)


def _make_diagnostic() -> POMDPDiagnostic:
    """Construct minimal POMDPDiagnostic."""
    n_states, n_arms = 4, 3
    mean_T = np.full((n_states, n_states, n_arms), 1.0 / n_states)
    count_T = np.full((n_states, n_states, n_arms), 5, dtype=int)
    T_snapshot = TransitionPosteriorSnapshot(
        mean=mean_T, count=count_T, alpha0=1.0, schema_version=POMDP_DIAG_SCHEMA,
    )
    alpha_R = np.full((n_states, n_arms), 5.0)
    beta_R = np.full((n_states, n_arms), 5.0)
    mean_R = alpha_R / (alpha_R + beta_R)
    variance_R = np.full((n_states, n_arms), 0.05)
    R_snapshot = RewardPosteriorSnapshot(
        mean=mean_R, alpha=alpha_R, beta=beta_R, alpha0=1.0,
        variance=variance_R, schema_version=POMDP_DIAG_SCHEMA,
    )
    belief = np.full(n_states, 0.25)
    coverage = np.full((n_states, n_arms), 5, dtype=int)
    return POMDPDiagnostic(
        T=T_snapshot, R=R_snapshot,
        belief=belief, coverage=coverage,
        most_likely_state=0,
        last_updated=datetime.datetime.now(),
        schema_version=POMDP_DIAG_SCHEMA,
    )


# ──────────────────────────────────────────────────────────────────────
# from_pomdp_diagnostic_updated factory (5 tests)
# ──────────────────────────────────────────────────────────────────────


def test_factory_accepts_pomdp_diagnostic_instance():
    """from_pomdp_diagnostic_updated 接受 POMDPDiagnostic 实例 (走 to_dict 路径)."""
    diagnostic = _make_diagnostic()
    event = LearningEvent.from_pomdp_diagnostic_updated("lbc001", diagnostic)

    assert event.event_type == "pomdp_diagnostic_updated"
    assert event.student_id == "lbc001"
    assert "diagnostic" in event.payload
    # diagnostic 字段是 dict (to_dict 输出)
    assert isinstance(event.payload["diagnostic"], dict)
    assert event.payload["diagnostic"]["schema_version"] == POMDP_DIAG_SCHEMA
    assert event.payload["diagnostic"]["most_likely_state"] == 0


def test_factory_accepts_dict_directly():
    """from_pomdp_diagnostic_updated 接受 dict (PluginRuntime 内调用时已序列化好)."""
    diagnostic = _make_diagnostic()
    diag_dict = diagnostic.to_dict()
    event = LearningEvent.from_pomdp_diagnostic_updated("lbc001", diag_dict)

    assert event.event_type == "pomdp_diagnostic_updated"
    assert event.payload["diagnostic"] == diag_dict
    # dict 是引用同一对象 (factory 不深拷贝)
    assert event.payload["diagnostic"] is diag_dict


def test_factory_rejects_non_diagnostic_type():
    """from_pomdp_diagnostic_updated 拒绝非 POMDPDiagnostic / 非 dict 类型 raise TypeError."""
    # str 不是合法 diagnostic
    with pytest.raises(TypeError, match="必须是 POMDPDiagnostic 或 dict"):
        LearningEvent.from_pomdp_diagnostic_updated("lbc001", "not_a_diagnostic")  # type: ignore[arg-type]
    # int 也不是
    with pytest.raises(TypeError, match="必须是 POMDPDiagnostic 或 dict"):
        LearningEvent.from_pomdp_diagnostic_updated("lbc001", 123)  # type: ignore[arg-type]
    # list 也不是 (没有 to_dict, 不是 dict)
    with pytest.raises(TypeError, match="必须是 POMDPDiagnostic 或 dict"):
        LearningEvent.from_pomdp_diagnostic_updated("lbc001", [1, 2, 3])  # type: ignore[arg-type]


def test_factory_event_type_is_plugin_internal_topic():
    """from_pomdp_diagnostic_updated event_type = "pomdp_diagnostic_updated" (Plugin-internal).

    验证: 不在 LearningEventType enum 内, 是 PluginRuntime 内部 routing topic.
    """
    diagnostic = _make_diagnostic()
    event = LearningEvent.from_pomdp_diagnostic_updated("lbc001", diagnostic)

    # event_type 是字符串 "pomdp_diagnostic_updated"
    assert event.event_type == "pomdp_diagnostic_updated"
    # 不在 LearningEventType enum 内 (enum 只有 10 个 LearningEventType 值)
    enum_values = {e.value for e in LearningEventType}
    assert "pomdp_diagnostic_updated" not in enum_values


def test_factory_payload_contains_serialized_diagnostic():
    """from_pomdp_diagnostic_updated payload 含完整 diagnostic 序列化 (T/R/belief/coverage)."""
    diagnostic = _make_diagnostic()
    event = LearningEvent.from_pomdp_diagnostic_updated("lbc001", diagnostic)

    diag_dict = event.payload["diagnostic"]
    # 验证 6 字段都在 (T / R / belief / coverage / most_likely_state / last_updated / schema_version)
    assert "T" in diag_dict
    assert "R" in diag_dict
    assert "belief" in diag_dict
    assert "coverage" in diag_dict
    assert "most_likely_state" in diag_dict
    assert "last_updated" in diag_dict
    assert "schema_version" in diag_dict

    # T/R schema_version 校验 (跟 POMDPDiagnostic 一致)
    assert diag_dict["T"]["schema_version"] == POMDP_DIAG_SCHEMA
    assert diag_dict["R"]["schema_version"] == POMDP_DIAG_SCHEMA

    # belief 是 1D list of float
    assert isinstance(diag_dict["belief"], list)
    assert len(diag_dict["belief"]) == 4
    assert abs(sum(diag_dict["belief"]) - 1.0) < 1e-6

    # coverage 是 2D list of int
    assert isinstance(diag_dict["coverage"], list)
    assert len(diag_dict["coverage"]) == 4
    assert all(len(row) == 3 for row in diag_dict["coverage"])