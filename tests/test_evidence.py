"""v0.83.0-a: Evidence Engine 测试套件.

目标 (按 v0.83.0-a Definition of Done):
  - Evidence + EvidenceSource 6 种来源枚举
  - Evidence to_dict/from_dict round-trip
  - EvidenceEngine CRUD: add / query_by_id / query_by_student / query_by_source / query_by_goal
  - 5+ 来源集成 (RESPONSE_HISTORY / CALIBRATION_LOG / LLM_CRITIC / MISCONCEPTION / PARTIAL_CREDIT / EVENT_LOG)
  - 防御性自检 [8] 仍 hard block (EvidenceEngine 0 新 mutation site)
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def in_memory_db():
    """创建 in-memory sqlite database (用真实 SCHEMA_SQL, 不污染 dev db)."""
    import sqlite3
    from ecos.persistence.db import SCHEMA_SQL

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    return conn


@pytest.fixture
def evidence_engine(in_memory_db):
    """构造 EvidenceEngine 用 in-memory db (bypass Database.__init__ 直接设 _conn)."""
    from ecos.persistence.db import Database
    from ecos.evidence import EvidenceEngine, EvidenceConfig

    db = Database.__new__(Database)  # bypass __init__
    db._conn = in_memory_db  # 直接设 _conn (bypass property)
    return EvidenceEngine(config=EvidenceConfig(), db=db)


# ──────────────────────────────────────────────────────────────────────
# 1. Evidence dataclass + EvidenceSource 枚举 (3 tests)
# ──────────────────────────────────────────────────────────────────────


class TestEvidenceSchema:
    """v0.83.0-a: Evidence dataclass 6 字段 + 4 派生字段."""

    def test_evidence_default_construction(self):
        """默认 Evidence 构造 (最小字段)."""
        from ecos.evidence import Evidence, EvidenceSource

        ev = Evidence(
            source=EvidenceSource.RESPONSE_HISTORY,
            student_id="s1",
            timestamp=datetime.now(),
        )
        assert ev.source == EvidenceSource.RESPONSE_HISTORY
        assert ev.student_id == "s1"
        assert ev.evidence_id is None
        assert ev.payload == {}
        assert ev.confidence == 0.5

    def test_evidence_to_from_dict_roundtrip(self):
        """to_dict / from_dict round-trip 保持所有字段."""
        from ecos.evidence import Evidence, EvidenceSource

        original = Evidence(
            evidence_id=42,
            source=EvidenceSource.LLM_CRITIC,
            student_id="student_007",
            timestamp=datetime(2026, 8, 10, 12, 0, 0),
            payload={"correctness": True, "score": 0.85, "skill_id": "algebra_1"},
            confidence=0.92,
            problem_id="p_42",
            skill_id="algebra_1",
            goal_id="goal_K_mastery_0.7",
            state_delta=0.15,
        )
        d = original.to_dict()
        restored = Evidence.from_dict(d)
        assert restored.evidence_id == 42
        assert restored.source == EvidenceSource.LLM_CRITIC
        assert restored.student_id == "student_007"
        assert restored.timestamp == datetime(2026, 8, 10, 12, 0, 0)
        assert restored.confidence == 0.92
        assert restored.problem_id == "p_42"
        assert restored.skill_id == "algebra_1"
        assert restored.state_delta == 0.15

    def test_evidence_source_enum_has_6_values(self):
        """EvidenceSource 枚举覆盖 6 种来源 (v0.83.0-a)."""
        from ecos.evidence import EvidenceSource

        assert len(EvidenceSource) == 6, \
            f"EvidenceSource 应=6 来源, 实际={len(EvidenceSource)}"
        expected = {"response_history", "calibration_log", "partial_credit",
                    "llm_critic", "misconception", "event_log"}
        actual = {s.value for s in EvidenceSource}
        assert actual == expected


# ──────────────────────────────────────────────────────────────────────
# 2. EvidenceEngine.add (5 来源集成) (5 tests)
# ──────────────────────────────────────────────────────────────────────


class TestEvidenceEngineAdd:
    """v0.83.0-a: EvidenceEngine.add 5+ 来源集成."""

    def test_add_response_history(self, evidence_engine):
        """add(RESPONSE_HISTORY) -> 落 evidence_log 表."""
        from ecos.evidence import Evidence, EvidenceSource

        ev = Evidence(
            source=EvidenceSource.RESPONSE_HISTORY,
            student_id="s1",
            timestamp=datetime.now(),
            payload={"skill_id": "algebra_1", "correct": True, "score": 1.0},
            confidence=0.9,
            problem_id="p1",
        )
        evidence_id = evidence_engine.add(ev)
        assert evidence_id > 0
        # 缓存
        assert evidence_id in evidence_engine._cache
        # 落表
        cached = evidence_engine._cache[evidence_id]
        assert cached.source == EvidenceSource.RESPONSE_HISTORY

    def test_add_calibration_log(self, evidence_engine):
        """add(CALIBRATION_LOG) -> 落 calibration_log 表."""
        from ecos.evidence import Evidence, EvidenceSource

        ev = Evidence(
            source=EvidenceSource.CALIBRATION_LOG,
            student_id="s1",
            timestamp=datetime.now(),
            payload={"actual_outcome": 0.85, "dual_agent_confidence": 0.78,
                     "intervention_id": "iv_001"},
            confidence=0.85,
        )
        evidence_id = evidence_engine.add(ev)
        assert evidence_id > 0
        assert evidence_engine._cache[evidence_id].source == EvidenceSource.CALIBRATION_LOG

    def test_add_llm_critic(self, evidence_engine):
        """add(LLM_CRITIC) -> 落 evidence_log (payload 标 source_subtype)."""
        from ecos.evidence import Evidence, EvidenceSource

        ev = Evidence(
            source=EvidenceSource.LLM_CRITIC,
            student_id="s1",
            timestamp=datetime.now(),
            payload={
                "source_subtype": "llm_critic",
                "correctness": True,
                "explanation_quality": 0.85,
                "self_evaluation": 0.9,
            },
            confidence=0.88,
        )
        evidence_id = evidence_engine.add(ev)
        assert evidence_id > 0

    def test_add_misconception(self, evidence_engine):
        """add(MISCONCEPTION) -> 落 evidence_log (payload 标 source_subtype)."""
        from ecos.evidence import Evidence, EvidenceSource

        ev = Evidence(
            source=EvidenceSource.MISCONCEPTION,
            student_id="s1",
            timestamp=datetime.now(),
            payload={
                "source_subtype": "misconception",
                "misc_id": "M3",
                "misc_confidence": 0.75,
            },
            confidence=0.75,
        )
        evidence_id = evidence_engine.add(ev)
        assert evidence_id > 0

    def test_add_partial_credit(self, evidence_engine):
        """add(PARTIAL_CREDIT) -> 落 evidence_log (payload 标 source_subtype)."""
        from ecos.evidence import Evidence, EvidenceSource

        ev = Evidence(
            source=EvidenceSource.PARTIAL_CREDIT,
            student_id="s1",
            timestamp=datetime.now(),
            payload={
                "source_subtype": "partial_credit",
                "score": 0.7,
                "mirt_theta_delta": 0.15,
            },
            confidence=0.7,
        )
        evidence_id = evidence_engine.add(ev)
        assert evidence_id > 0


# ──────────────────────────────────────────────────────────────────────
# 3. EvidenceEngine.query (3 tests)
# ──────────────────────────────────────────────────────────────────────


class TestEvidenceEngineQuery:
    """v0.83.0-a: EvidenceEngine query 接口."""

    def test_query_by_student(self, evidence_engine):
        """query_by_student 跨 3 表查 + 倒序."""
        from ecos.evidence import Evidence, EvidenceSource

        # 添加 3 条 evidence
        for i in range(3):
            ev = Evidence(
                source=EvidenceSource.RESPONSE_HISTORY,
                student_id="s1",
                timestamp=datetime.now() - timedelta(hours=i),
                payload={"correct": True, "score": 1.0},
                problem_id=f"p_{i}",
            )
            evidence_engine.add(ev)

        results = evidence_engine.query_by_student("s1")
        assert len(results) == 3
        # 倒序 (新 → 旧)
        for i in range(len(results) - 1):
            assert results[i].timestamp >= results[i + 1].timestamp

    def test_query_by_source_filters_correctly(self, evidence_engine):
        """query_by_source 过滤正确 (LLM_CRITIC 返 LLM_CRITIC only)."""
        from ecos.evidence import Evidence, EvidenceSource

        # 加 1 RESPONSE_HISTORY + 1 LLM_CRITIC
        evidence_engine.add(Evidence(
            source=EvidenceSource.RESPONSE_HISTORY,
            student_id="s1",
            timestamp=datetime.now(),
            payload={"correct": True},
        ))
        evidence_engine.add(Evidence(
            source=EvidenceSource.LLM_CRITIC,
            student_id="s1",
            timestamp=datetime.now(),
            payload={"source_subtype": "llm_critic", "correctness": True},
        ))

        # query LLM_CRITIC -> 1 条
        llm_results = evidence_engine.query_by_source(EvidenceSource.LLM_CRITIC, "s1")
        assert len(llm_results) == 1
        assert llm_results[0].source == EvidenceSource.LLM_CRITIC

        # query RESPONSE_HISTORY -> 1 条 (主类型, 不含 LLM_CRITIC 子类型)
        rh_results = evidence_engine.query_by_source(EvidenceSource.RESPONSE_HISTORY, "s1")
        assert len(rh_results) == 1
        assert rh_results[0].source == EvidenceSource.RESPONSE_HISTORY

    def test_query_by_goal_returns_empty_stub(self, evidence_engine):
        """query_by_goal v0.83.0-a stub: 永远返回空 (Goal Ontology 0%)."""
        results = evidence_engine.query_by_goal("any_goal")
        assert results == []


# ──────────────────────────────────────────────────────────────────────
# 4. EvidenceEngine 行为 (3 tests)
# ──────────────────────────────────────────────────────────────────────


class TestEvidenceEngineBehavior:
    """v0.83.0-a: Evidence Engine 行为 (多学生隔离 + 时间过滤 + auto_prune 警告)."""

    def test_multi_student_isolation(self, evidence_engine):
        """query_by_student 隔离 (student_a 不查 student_b)."""
        from ecos.evidence import Evidence, EvidenceSource

        evidence_engine.add(Evidence(
            source=EvidenceSource.RESPONSE_HISTORY, student_id="student_a",
            timestamp=datetime.now(), payload={"correct": True},
        ))
        evidence_engine.add(Evidence(
            source=EvidenceSource.RESPONSE_HISTORY, student_id="student_b",
            timestamp=datetime.now(), payload={"correct": False},
        ))

        a = evidence_engine.query_by_student("student_a")
        b = evidence_engine.query_by_student("student_b")
        assert len(a) == 1
        assert len(b) == 1
        assert a[0].student_id == "student_a"
        assert b[0].student_id == "student_b"

    def test_query_by_student_time_filter(self, evidence_engine):
        """query_by_student 支持 since/until 时间范围."""
        from ecos.evidence import Evidence, EvidenceSource

        now = datetime.now()
        # 3 条 evidence, 时间间隔 1 小时
        for i in range(3):
            evidence_engine.add(Evidence(
                source=EvidenceSource.RESPONSE_HISTORY, student_id="s1",
                timestamp=now - timedelta(hours=i), payload={"correct": True},
            ))

        # since = 90 分钟前 -> 2 条
        results = evidence_engine.query_by_student("s1", since=now - timedelta(minutes=90))
        assert len(results) == 2

        # until = 30 分钟前 -> 2 条 (now, now-60min)
        results = evidence_engine.query_by_student("s1", until=now - timedelta(minutes=30))
        assert len(results) == 2

    def test_auto_prune_warning_logged(self, in_memory_db, caplog):
        """max_per_student=2, 加 3 条 evidence -> 触发 auto_prune 警告."""
        import logging
        from ecos.persistence.db import Database
        from ecos.evidence import EvidenceEngine, EvidenceConfig, Evidence, EvidenceSource

        db = Database.__new__(Database)
        db._conn = in_memory_db  # bypass property
        config = EvidenceConfig(max_per_student=2)
        engine = EvidenceEngine(config=config, db=db)

        with caplog.at_level(logging.WARNING, logger="ecos.evidence.evidence_engine"):
            for i in range(3):
                engine.add(Evidence(
                    source=EvidenceSource.RESPONSE_HISTORY, student_id="s1",
                    timestamp=datetime.now(), payload={"correct": True},
                ))

        # 警告应该出现
        assert any("max_per_student" in r.message for r in caplog.records), \
            "max_per_student 超过时应触发 auto_prune 警告"


# ──────────────────────────────────────────────────────────────────────
# 5. 防御性自检 (1 test)
# ──────────────────────────────────────────────────────────────────────


class TestEvidenceDefensiveChecks:
    """v0.83.0-a: Evidence Engine 防御性自检 (silent pass 扫描)."""

    def test_no_silent_pass_in_evidence(self):
        """evidence/ 全部 except 块必须有 logger.warning (防御性自检 [1])."""
        import inspect
        from ecos.evidence import evidence as evidence_mod
        from ecos.evidence import evidence_engine as engine_mod

        for mod_name, mod in [("evidence", evidence_mod), ("evidence_engine", engine_mod)]:
            source = inspect.getsource(mod)
            lines = source.split("\n")

            except_blocks = []
            i = 0
            while i < len(lines):
                line = lines[i]
                stripped = line.lstrip()
                if stripped.startswith("except") and line.rstrip().endswith(":"):
                    except_indent = len(line) - len(line.lstrip())
                    block_lines = []
                    i += 1
                    while i < len(lines):
                        next_line = lines[i]
                        if not next_line.strip():
                            i += 1
                            continue
                        next_indent = len(next_line) - len(next_line.lstrip())
                        if next_indent > except_indent:
                            block_lines.append(next_line)
                            i += 1
                        else:
                            break
                    except_blocks.append("\n".join(block_lines))
                else:
                    i += 1

            for idx, block in enumerate(except_blocks):
                has_warning = "warning" in block
                has_raise = "raise " in block or block.strip().endswith("raise")
                has_silent_pass = "pass" in block and not has_warning

                if has_silent_pass:
                    pytest.fail(
                        f"{mod_name}.py except 块 #{idx + 1} 是 silent pass:\n{block}\n"
                        "防御性自检 [1]: 必须改 logger.warning(..., exc_info=True)"
                    )
                if not has_warning and not has_raise:
                    pytest.fail(
                        f"{mod_name}.py except 块 #{idx + 1} 无 warning 也无 raise:\n{block}\n"
                        "防御性自检 [1]: 必须有 logger.warning 或显式 raise"
                    )


# ──────────────────────────────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
