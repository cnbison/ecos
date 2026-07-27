"""v0.57.0: LCA 持久化测试套件.

目标 (按 v0.57.0 Definition of Done):
  1. LCAStore.save_state / load_state 7 字段对齐 (CLAUDE.md [5])
  2. LCAEngine.dump_state / load_state per-student 隔离
  3. **重启后 LinUCB arm_pull_counts 不归零** (核心 DoD)
  4. 多学生数据不互相污染
  5. 防御性自检: 持久化失败有 _log.warning (CLAUDE.md [1])

测试策略:
  - unit test: LCAStore 直接存/读
  - integration test: 通过 web.api.lca 模拟"重启后 lca_mod._engine 重置 + DB 状态恢复"
  - 跨进程模拟: 用 monkeypatch 强制 lca_mod._engine = None, 模拟进程重启
"""

from __future__ import annotations

import json
import logging
from unittest.mock import patch

import numpy as np
import pytest


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def fresh_lca_state():
    """每个测试前清理 lca 模块状态 + DB 里 test 状态."""
    import web.api.lca as lca_mod
    from ecos.persistence.lca_store import get_lca_store

    # 重置模块状态
    lca_mod._engine = None
    lca_mod._store = None
    lca_mod._loaded_students = set()
    lca_mod.LCA_ENABLED = False

    # 清理 test students
    for sid in ("test_persistence_a", "test_persistence_b", "test_persistence_c"):
        try:
            get_lca_store().delete_state(sid)
        except Exception:
            pass

    yield lca_mod


@pytest.fixture
def belief_state():
    """构造一个最小 BeliefState."""
    from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig
    from ecos.cta.l1_evolution import EvolutionConfig
    from ecos.cta.l2_mirt import MIRTConfig

    config = BeliefEngineConfig(
        evolution_config=EvolutionConfig(),
        mirt_config=MIRTConfig(),
    )
    engine = BeliefEngine(config=config, llm_client=None)
    return engine.create_initial_state("test_persistence_a")


# ──────────────────────────────────────────────────────────────────────
# 1. LCAStore 单元测试 (7 字段对齐)
# ──────────────────────────────────────────────────────────────────────


class TestLCAStorePersistence:
    """v0.57.0: LCAStore 7 字段持久化 + 恢复."""

    def test_save_load_roundtrip(self, fresh_lca_state):
        """save + load 7 字段全恢复."""
        from ecos.persistence.lca_store import get_lca_store

        store = get_lca_store()
        # 7 字段测试数据 (LinUCB context_dim=16, n_arms=10)
        # bandit_a 维度: n_arms × d × d = 10 × 16 × 16
        bandit_a_sample = [
            [[float(i + j) for j in range(16)] for i in range(16)]
            for _ in range(10)
        ]
        # bandit_b 维度: n_arms × d = 10 × 16
        bandit_b_sample = [[float(i) * 0.1 for i in range(16)] for _ in range(10)]
        test_data = {
            "intervention_history": [
                {"intervention_id": "abc123", "intervention_type": "practice",
                 "bloom_target": "APPLY", "difficulty": 0.7}
            ],
            "bandit_a": bandit_a_sample,
            "bandit_b": bandit_b_sample,
            "arm_pull_counts": [3, 2, 5, 0, 1, 4, 2, 0, 1, 3],
            "last_intervention": {"intervention_id": "abc123", "intervention_type": "practice"},
            "update_count": 21,
            "select_count": 25,
        }
        store.save_state(
            student_id="test_persistence_a",
            intervention_history=test_data["intervention_history"],
            bandit_a=test_data["bandit_a"],
            bandit_b=test_data["bandit_b"],
            arm_pull_counts=test_data["arm_pull_counts"],
            last_intervention=test_data["last_intervention"],
            update_count=test_data["update_count"],
            select_count=test_data["select_count"],
        )

        snap = store.load_state("test_persistence_a")
        assert snap is not None
        assert snap.intervention_history == test_data["intervention_history"]
        assert snap.bandit_a == test_data["bandit_a"]
        assert snap.bandit_b == test_data["bandit_b"]
        assert snap.arm_pull_counts == test_data["arm_pull_counts"]
        assert snap.last_intervention == test_data["last_intervention"]
        assert snap.update_count == test_data["update_count"]
        assert snap.select_count == test_data["select_count"]

    def test_load_state_returns_none_for_unknown_student(self, fresh_lca_state):
        """未持久化的学生 load_state 返回 None."""
        from ecos.persistence.lca_store import get_lca_store

        store = get_lca_store()
        snap = store.load_state("never_persisted_student")
        assert snap is None

    def test_save_state_overwrites_existing(self, fresh_lca_state):
        """save 二次 (UPSERT) 覆盖式更新, 不抛异常."""
        from ecos.persistence.lca_store import get_lca_store

        store = get_lca_store()
        # 第一次 save
        store.save_state(
            student_id="test_persistence_a",
            intervention_history=[],
            bandit_a=[],
            bandit_b=[],
            arm_pull_counts=[0] * 10,
            last_intervention=None,
            update_count=0,
            select_count=0,
        )
        # 第二次 save (覆盖)
        store.save_state(
            student_id="test_persistence_a",
            intervention_history=[],
            bandit_a=[],
            bandit_b=[],
            arm_pull_counts=[1, 2, 3, 0, 0, 0, 0, 0, 0, 0],
            last_intervention=None,
            update_count=5,
            select_count=5,
        )
        snap = store.load_state("test_persistence_a")
        assert snap.update_count == 5
        assert snap.arm_pull_counts[0] == 1
        assert snap.arm_pull_counts[1] == 2


# ──────────────────────────────────────────────────────────────────────
# 2. LCAEngine dump_state / load_state 测试
# ──────────────────────────────────────────────────────────────────────


class TestLCAEnginePersistence:
    """v0.57.0: LCAEngine per-student dump_state / load_state."""

    def test_dump_state_contains_7_fields(self, fresh_lca_state, belief_state):
        """dump_state 返回 dict 含 7 关键字段."""
        import web.api.lca as lca_mod

        lca_mod.select_intervention("test_persistence_a", belief_state)
        engine = lca_mod.get_lca_engine()
        snap = engine.dump_state("test_persistence_a")

        # 7 关键字段
        assert "intervention_history" in snap
        assert "bandit_a" in snap
        assert "bandit_b" in snap
        assert "arm_pull_counts" in snap
        assert "last_intervention" in snap
        assert "update_count" in snap
        assert "select_count" in snap
        # 内部辅助字段
        assert "arm_fingerprints" in snap
        assert "last_arm" in snap

    def test_per_student_bandit_isolation(self, fresh_lca_state, belief_state):
        """per-student bandit 隔离: lca_mod select a 跟 select b 不互相污染."""
        import web.api.lca as lca_mod
        from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig
        from ecos.cta.l1_evolution import EvolutionConfig
        from ecos.cta.l2_mirt import MIRTConfig

        # 构造 2 个不同 BeliefState
        be = BeliefEngine(config=BeliefEngineConfig(
            evolution_config=EvolutionConfig(), mirt_config=MIRTConfig(),
        ), llm_client=None)
        state_a = be.create_initial_state("test_persistence_a")
        state_b = be.create_initial_state("test_persistence_b")

        # student_a 跑 3 次 select + 模拟 3 次 update
        for _ in range(3):
            result = lca_mod.select_intervention("test_persistence_a", state_a)
            engine = lca_mod.get_lca_engine()
            engine._get_bandit("test_persistence_a").update(
                intervention=result.intervention,
                belief_state=state_a,
                reward=0.7,
            )
            engine._update_count["test_persistence_a"] = engine._update_count.get("test_persistence_a", 0) + 1

        # student_b 跑 1 次 select
        lca_mod.select_intervention("test_persistence_b", state_b)

        # 验证隔离
        engine = lca_mod.get_lca_engine()
        snap_a = engine.dump_state("test_persistence_a")
        snap_b = engine.dump_state("test_persistence_b")

        # a 跑了 3 次, b 跑了 1 次 — count 应该不同
        assert snap_a["select_count"] == 3
        assert snap_b["select_count"] == 1
        # bandit_a 跟 bandit_b 是独立实例
        assert id(snap_a["bandit_a"]) != id(snap_b["bandit_a"])


# ──────────────────────────────────────────────────────────────────────
# 3. 核心: 跨进程重启恢复 (CLAUDE.md v0.57.0 DoD)
# ──────────────────────────────────────────────────────────────────────


class TestLCARestartRecovery:
    """v0.57.0 核心 DoD: 重启后 LinUCB arm 拉取次数不归零."""

    def test_arm_pull_counts_survive_engine_reset(self, fresh_lca_state, belief_state):
        """模拟 Flask 进程重启: _engine = None + 重新 select/update → arm 计数从 DB 恢复.

        注: LinUCB 设计 — arm_pull_counts 只在 update 时增加 (select 不算"拉取").
        """
        import web.api.lca as lca_mod

        # 第 1 阶段: 5 次 select + update
        for _ in range(5):
            lca_mod.select_intervention("test_persistence_a", belief_state)
            lca_mod.update_with_reward("test_persistence_a", belief_state, score=1.0, bloom_layer="L3")

        # 验证: arm_pull_counts 总和 = 5
        engine = lca_mod.get_lca_engine()
        snap_before = engine.dump_state("test_persistence_a")
        assert sum(snap_before["arm_pull_counts"]) == 5
        assert snap_before["select_count"] == 5
        assert snap_before["update_count"] == 5

        # 第 2 阶段: 模拟进程重启 (重置 _engine + _loaded_students)
        lca_mod._engine = None
        lca_mod._loaded_students = set()

        # 第 3 阶段: 再次 select + update — 触发 _get_or_create_lca_state 从 DB 加载
        lca_mod.select_intervention("test_persistence_a", belief_state)
        lca_mod.update_with_reward("test_persistence_a", belief_state, score=1.0, bloom_layer="L3")

        # 验证: arm_pull_counts 应该是 5 + 1 = 6 (不归零!)
        engine = lca_mod.get_lca_engine()
        snap_after = engine.dump_state("test_persistence_a")
        assert sum(snap_after["arm_pull_counts"]) == 6, \
            f"重启后 arm_pull_counts 应该累计而非归零, " \
            f"before={sum(snap_before['arm_pull_counts'])}, after={sum(snap_after['arm_pull_counts'])}"
        assert snap_after["select_count"] == 6, \
            f"重启后 select_count 应该累计, before={snap_before['select_count']}, after={snap_after['select_count']}"
        assert snap_after["update_count"] == 6, \
            f"重启后 update_count 应该累计, before={snap_before['update_count']}, after={snap_after['update_count']}"

    def test_update_count_survives_engine_reset(self, fresh_lca_state, belief_state):
        """重启后 update_count 也累计."""
        import web.api.lca as lca_mod

        # 第 1 阶段: select + update
        for _ in range(3):
            lca_mod.select_intervention("test_persistence_a", belief_state)
            lca_mod.update_with_reward("test_persistence_a", belief_state, score=1.0, bloom_layer="L3")

        engine = lca_mod.get_lca_engine()
        snap_before = engine.dump_state("test_persistence_a")
        assert snap_before["update_count"] == 3
        assert snap_before["select_count"] == 3

        # 重启
        lca_mod._engine = None
        lca_mod._loaded_students = set()

        # 再 select + update 1 次
        lca_mod.select_intervention("test_persistence_a", belief_state)
        lca_mod.update_with_reward("test_persistence_a", belief_state, score=1.0, bloom_layer="L3")

        engine = lca_mod.get_lca_engine()
        snap_after = engine.dump_state("test_persistence_a")
        assert snap_after["update_count"] == 4
        assert snap_after["select_count"] == 4

    def test_lca_state_persists_across_module_reload(self, fresh_lca_state, belief_state):
        """更真实的"重启": 重新 import web.api.lca 模块 (lca_mod._engine 强制重置)."""
        import importlib
        import web  # noqa: F401  (让 web.api 可被 reload)
        import web.api.lca as lca_mod

        # 1 次 select + update, 落盘
        lca_mod.select_intervention("test_persistence_a", belief_state)
        lca_mod.update_with_reward("test_persistence_a", belief_state, score=1.0, bloom_layer="L3")

        engine = lca_mod.get_lca_engine()
        snap_before = engine.dump_state("test_persistence_a")
        assert snap_before["select_count"] == 1
        assert sum(snap_before["arm_pull_counts"]) == 1

        # 模拟进程重启: reload lca_mod
        importlib.reload(web.api.lca)
        # reload 后 lca_mod 指向新模块 (老 lca_mod 引用被覆盖)
        import web.api.lca as new_lca
        new_lca._engine = None
        new_lca._loaded_students = set()

        # 新 select + update — 应该从 DB 恢复
        new_lca.select_intervention("test_persistence_a", belief_state)
        new_lca.update_with_reward("test_persistence_a", belief_state, score=1.0, bloom_layer="L3")
        engine = new_lca.get_lca_engine()
        snap_after = engine.dump_state("test_persistence_a")
        assert snap_after["select_count"] == 2, \
            f"reload 后 select_count 应=2 (DB 持久化), 实际={snap_after['select_count']}"
        # arm_pull_counts 总和 = 2 (不归零)
        assert sum(snap_after["arm_pull_counts"]) == 2

    def test_two_students_have_independent_lca_state(self, fresh_lca_state, belief_state):
        """lca_mod select a 不污染 b 的 LinUCB state (跨重启)."""
        import importlib
        import web  # noqa: F401
        import web.api.lca as lca_mod
        from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig
        from ecos.cta.l1_evolution import EvolutionConfig
        from ecos.cta.l2_mirt import MIRTConfig

        be = BeliefEngine(config=BeliefEngineConfig(
            evolution_config=EvolutionConfig(), mirt_config=MIRTConfig(),
        ), llm_client=None)
        state_a = be.create_initial_state("test_persistence_a")
        state_b = be.create_initial_state("test_persistence_b")

        # student_a 5 次 select+update, student_b 2 次 select+update
        for _ in range(5):
            lca_mod.select_intervention("test_persistence_a", state_a)
            lca_mod.update_with_reward("test_persistence_a", state_a, score=1.0, bloom_layer="L3")
        for _ in range(2):
            lca_mod.select_intervention("test_persistence_b", state_b)
            lca_mod.update_with_reward("test_persistence_b", state_b, score=1.0, bloom_layer="L3")

        # 重启
        importlib.reload(web.api.lca)
        import web.api.lca as new_lca
        new_lca._engine = None
        new_lca._loaded_students = set()

        # 验证: 新模块能从 DB 恢复两个学生独立状态
        new_lca._get_or_create_lca_state("test_persistence_a")
        new_lca._get_or_create_lca_state("test_persistence_b")
        engine = new_lca.get_lca_engine()
        snap_a = engine.dump_state("test_persistence_a")
        snap_b = engine.dump_state("test_persistence_b")

        assert snap_a["select_count"] == 5, \
            f"student_a select_count 应=5, 实际={snap_a['select_count']}"
        assert snap_b["select_count"] == 2, \
            f"student_b select_count 应=2 (独立), 实际={snap_b['select_count']}"
        # arm_pull_counts 也独立
        assert sum(snap_a["arm_pull_counts"]) == 5
        assert sum(snap_b["arm_pull_counts"]) == 2


# ──────────────────────────────────────────────────────────────────────
# 4. 防御性自检
# ──────────────────────────────────────────────────────────────────────


class TestDefensiveChecks:
    """v0.57.0: 防御性自检套件."""

    def test_save_failure_logs_warning(self, fresh_lca_state, belief_state, caplog):
        """持久化失败必须有 _log.warning (CLAUDE.md [1])."""
        import web.api.lca as lca_mod

        # Mock get_store 让 save 抛异常
        with patch.object(lca_mod, "get_store") as mock_get_store:
            mock_store = mock_get_store.return_value
            mock_store.save_state.side_effect = RuntimeError("mock DB fail")

            with caplog.at_level(logging.WARNING):
                lca_mod.select_intervention("test_persistence_a", belief_state)

        # 验证有 warning log
        save_warnings = [
            r for r in caplog.records
            if r.levelname == "WARNING" and "落盘失败" in r.message
        ]
        assert len(save_warnings) >= 1, \
            "save 失败时必须有 _log.warning (CLAUDE.md 防御性自检 [1])"

    def test_load_failure_logs_warning(self, fresh_lca_state, caplog):
        """load_state 失败必须有 _log.warning (CLAUDE.md [1])."""
        import web.api.lca as lca_mod

        with patch.object(lca_mod, "get_store") as mock_get_store:
            mock_store = mock_get_store.return_value
            mock_store.has_state.return_value = True
            mock_store.load_state.side_effect = RuntimeError("mock DB fail")

            with caplog.at_level(logging.WARNING):
                lca_mod._get_or_create_lca_state("test_persistence_a")

        load_warnings = [
            r for r in caplog.records
            if r.levelname == "WARNING" and "加载失败" in r.message
        ]
        assert len(load_warnings) >= 1, \
            "load 失败时必须有 _log.warning (CLAUDE.md 防御性自检 [1])"


# ──────────────────────────────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
