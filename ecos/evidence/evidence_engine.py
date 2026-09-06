"""Evidence Engine —— v0.83 Kernel Engine 第 1 个.

对应:
  - research/00-overview/12-kernel-mapping-current-vs-2.0.md §1.4 Evidence Engine
  - kernel-mapping 演进建议: v0.77.0 (延迟到 v0.83.0-a) 引入 Evidence Engine

职责:
  - 统一 5+ Evidence 来源 (RESPONSE_HISTORY / CALIBRATION_LOG / PARTIAL_CREDIT /
    LLM_CRITIC / MISCONCEPTION / EVENT_LOG)
  - 提供 CRUD: add / query_by_id / query_by_student / query_by_source / query_by_goal
  - 不破坏现有 db.py evidence_log / calibration_log / event_log 3 张表 schema
  - 跨来源统一查询 (Python 层 join)

设计原则:
  - EvidenceEngine 是 2.0 §1.4 Engine 之一, 不持有 Belief state
  - 复用 evidence_log 表 (经 _add_to_evidence_log 直写 SQL) / db.save_calibration (existing calibration_log)
  - 复用 EventLog (v0.81 已有) for EVENT_LOG 源
  - LLM_CRITIC / MISCONCEPTION / PARTIAL_CREDIT: 派生自 RESPONSE_HISTORY payload (filter by sub-source 字段)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .evidence import Evidence, EvidenceSource

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# EvidenceConfig
# ---------------------------------------------------------------------------

@dataclass
class EvidenceConfig:
    """Evidence Engine 配置.

    Attributes:
        max_per_student:     int  每学生最大 Evidence 数, 触发 auto-prune 警告
                              (v0.83.0-a 仅警告, v0.85+ retention policy 实际 prune)
        auto_prune_days:     int  auto-prune threshold (0 = 不自动 prune)
        enable_event_log_integration: bool  (默认 True, 集成 v0.81 event_log)
    """

    max_per_student: int = 10000
    auto_prune_days: int = 0  # 0 = 不自动 prune
    enable_event_log_integration: bool = True


# ---------------------------------------------------------------------------
# EvidenceEngine 类
# ---------------------------------------------------------------------------

class EvidenceEngine:
    """统一 Evidence Engine (v0.83 Kernel Engine 第 1 个).

    用法:
        engine = EvidenceEngine(config=EvidenceConfig())
        # 1) 添加 Evidence
        evidence = Evidence(
            source=EvidenceSource.RESPONSE_HISTORY,
            student_id="student_001",
            timestamp=datetime.now(),
            payload={"skill_id": "s1", "correct": True, "score": 1.0},
            confidence=0.9,
            problem_id="p1",
        )
        evidence_id = engine.add(evidence)
        # 2) 查询
        evidences = engine.query_by_student("student_001", since=..., until=...)
        evidences = engine.query_by_source(EvidenceSource.LLM_CRITIC, "student_001")
        # 3) 反查 Belief (v0.83.0-b 接入)
        # engine.attach_to_belief(evidence, state, dim="K")

    集成 5+ 来源 (现有 3 张表, 不破坏 schema):
      - RESPONSE_HISTORY: 落 evidence_log 表 (经 _add_to_evidence_log 直写 SQL)
      - CALIBRATION_LOG:  落 calibration_log 表 (db.save_calibration)
      - EVENT_LOG:        落 event_log 表 (EventLog.log_event)
      - LLM_CRITIC:       派生自 RESPONSE_HISTORY payload (filter by "source_subtype" 字段)
      - MISCONCEPTION:    派生自 RESPONSE_HISTORY payload (filter by "source_subtype" 字段)
      - PARTIAL_CREDIT:   派生自 RESPONSE_HISTORY payload (filter by "source_subtype" 字段)
    """

    def __init__(
        self,
        config: Optional[EvidenceConfig] = None,
        db: Optional[Any] = None,
        event_log: Optional[Any] = None,
    ):
        self.config = config or EvidenceConfig()
        # 注入依赖 (默认懒加载, 避免循环 import)
        self._db = db
        self._event_log = event_log
        # 缓存: evidence_id -> Evidence (防止 query_by_id 多次查 db)
        self._cache: Dict[int, Evidence] = {}

    # ---------------------------------------------------------------
    # 依赖懒加载
    # ---------------------------------------------------------------

    @property
    def db(self):
        if self._db is None:
            from ecos.persistence.db import get_default_database
            self._db = get_default_database()
        return self._db

    @property
    def event_log(self):
        if self._event_log is None:
            from ecos.cta.event_log import EventLog
            # 默认 in_memory (避免强制 sqlite 路径, 测试用 in_memory 更轻量)
            self._event_log = EventLog.in_memory()
        return self._event_log

    # ---------------------------------------------------------------
    # CRUD: add / query
    # ---------------------------------------------------------------

    def add(self, evidence: Evidence) -> int:
        """添加 Evidence, 返回 evidence_id.

        落表策略 (按 source 路由):
          - RESPONSE_HISTORY: 落 evidence_log (经 _add_to_evidence_log 直写 SQL)
          - CALIBRATION_LOG:  落 calibration_log (走 db.save_calibration)
          - EVENT_LOG:        落 event_log (走 EventLog.log_event, 仅当 enable_event_log_integration=True)
          - LLM_CRITIC / MISCONCEPTION / PARTIAL_CREDIT:
            视为 RESPONSE_HISTORY 子类型, payload 标 source_subtype 字段
            落 evidence_log (跟 v0.81 之前 5 字段 evidence 一致)
        """
        if evidence.evidence_id is not None:
            _log.warning(
                "EvidenceEngine.add: evidence_id=%s 已设置, 仍 add (会创建新行)",
                evidence.evidence_id,
            )

        if evidence.source == EvidenceSource.RESPONSE_HISTORY or \
           evidence.source in (EvidenceSource.LLM_CRITIC, EvidenceSource.MISCONCEPTION,
                               EvidenceSource.PARTIAL_CREDIT):
            evidence_id = self._add_to_evidence_log(evidence)
        elif evidence.source == EvidenceSource.CALIBRATION_LOG:
            evidence_id = self._add_to_calibration_log(evidence)
        elif evidence.source == EvidenceSource.EVENT_LOG:
            evidence_id = self._add_to_event_log(evidence)
        else:
            _log.warning(
                "EvidenceEngine.add: unknown source=%s, fallback to evidence_log",
                evidence.source,
            )
            evidence_id = self._add_to_evidence_log(evidence)

        # 缓存
        evidence.evidence_id = evidence_id
        self._cache[evidence_id] = evidence

        # Auto-prune 警告 (v0.83.0-a 仅警告, 不实际 prune)
        # v0.98.0 (b-a): gate 修复 — 原条件 `auto_prune_days > 0 or max_per_student > 0`
        #   把无关的 auto_prune_days 也当触发条件, 且 max_per_student=0 (unlimited)
        #   时 count > 0 恒真会刷警告。改为仅 max_per_student > 0 才做 count 扫描。
        #   (web 注入传 max_per_student=0 -> 每次 add 零扫描, 否则 5 dim x 3 表全扫/submit)
        if self.config.max_per_student > 0:
            try:
                count = len(self.query_by_student(evidence.student_id, limit=10**6))
                if count > self.config.max_per_student:
                    _log.warning(
                        "EvidenceEngine: student=%s Evidence 数 %d 超过 max_per_student=%d, 建议 prune",
                        evidence.student_id, count, self.config.max_per_student,
                    )
            except Exception:
                _log.warning("auto_prune 警告查询失败 (student=%s), 跳过",
                             evidence.student_id, exc_info=True)

        return evidence_id

    def query_by_id(self, evidence_id: int) -> Optional[Evidence]:
        """按 evidence_id 反查 Evidence.

        跨 3 张表查找: evidence_log / calibration_log / event_log.
        """
        # 先查缓存
        if evidence_id in self._cache:
            return self._cache[evidence_id]

        # 查 evidence_log
        try:
            row = self.db.conn.execute(
                "SELECT * FROM evidence_log WHERE evidence_id = ?",
                (evidence_id,),
            ).fetchone()
            if row:
                return self._row_to_evidence(dict(row), EvidenceSource.RESPONSE_HISTORY)
        except Exception:
            _log.warning("evidence_log 查询失败", exc_info=True)

        # 查 calibration_log
        try:
            row = self.db.conn.execute(
                "SELECT * FROM calibration_log WHERE calibration_round = ?",
                (evidence_id,),
            ).fetchone()
            if row:
                return self._row_to_evidence(dict(row), EvidenceSource.CALIBRATION_LOG)
        except Exception:
            _log.warning("calibration_log 查询失败", exc_info=True)

        # 查 event_log (event_id 是 TEXT PK)
        try:
            row = self.db.conn.execute(
                "SELECT * FROM event_log WHERE event_id = ?",
                (str(evidence_id),),
            ).fetchone()
            if row:
                return self._row_to_evidence(dict(row), EvidenceSource.EVENT_LOG)
        except Exception:
            _log.warning("event_log 查询失败", exc_info=True)

        return None

    def query_by_student(
        self,
        student_id: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[Evidence]:
        """按学生查 Evidence (跨 3 张表, 可选时间范围 + limit).

        Returns:
            List[Evidence] (按 timestamp 倒序, 跨表合并)
        """
        results: List[Evidence] = []

        # evidence_log
        try:
            rows = self.db.load_evidence(student_id, limit=limit or 1000)
            for row in rows:
                ev = self._row_to_evidence(row, EvidenceSource.RESPONSE_HISTORY)
                if ev is None:
                    continue
                if since and ev.timestamp < since:
                    continue
                if until and ev.timestamp > until:
                    continue
                results.append(ev)
        except Exception:
            _log.warning("evidence_log query_by_student 失败", exc_info=True)

        # calibration_log
        try:
            # calibration_log 没有 load_by_student 公开方法, 直接查
            rows = self.db.conn.execute(
                "SELECT * FROM calibration_log WHERE student_id = ? ORDER BY timestamp DESC",
                (student_id,),
            ).fetchall()
            for row in rows:
                ev = self._row_to_evidence(dict(row), EvidenceSource.CALIBRATION_LOG)
                if ev is None:
                    continue
                if since and ev.timestamp < since:
                    continue
                if until and ev.timestamp > until:
                    continue
                results.append(ev)
        except Exception:
            _log.warning("calibration_log query_by_student 失败", exc_info=True)

        # event_log
        if self.config.enable_event_log_integration:
            try:
                events = self.event_log.load_events(
                    student_id=student_id, since=since, until=until, limit=limit,
                )
                for ev_obj in events:
                    ev = self._event_to_evidence(ev_obj)
                    if ev:
                        results.append(ev)
            except Exception:
                _log.warning("event_log query_by_student 失败", exc_info=True)

        # 按 timestamp 倒序
        results.sort(key=lambda e: e.timestamp, reverse=True)

        # limit
        if limit is not None and limit > 0:
            results = results[:limit]

        return results

    def query_by_source(
        self,
        source: EvidenceSource,
        student_id: str,
    ) -> List[Evidence]:
        """按来源 + 学生查 Evidence.

        LLM_CRITIC / MISCONCEPTION / PARTIAL_CREDIT 视为 RESPONSE_HISTORY 子类型
        (从 payload.source_subtype 过滤).
        """
        all_ev = self.query_by_student(student_id)

        if source in (EvidenceSource.LLM_CRITIC, EvidenceSource.MISCONCEPTION,
                      EvidenceSource.PARTIAL_CREDIT):
            # 子类型过滤: _row_to_evidence 已经把 source 设回子类型,
            # 直接按 source 过滤即可 (不需要再 cross-check payload.source_subtype)
            return [ev for ev in all_ev if ev.source == source]

        return [ev for ev in all_ev if ev.source == source]

    def query_by_goal(self, goal_id: str) -> List[Evidence]:
        """按 goal 查 Evidence (v0.83.0-a stub: 返回空 list).

        Phase 5+ 接入 Goal Ontology 后, 实现基于 goal_id 反查.
        v0.83.0-a 行为: 永远返回 [] (Goal Ontology 0%).
        """
        _log.debug("query_by_goal(%s) v0.83.0-a stub: 永远返回空 (Goal Ontology 0%)",
                   goal_id)
        return []

    # ---------------------------------------------------------------
    # v0.83.0-b 集成钩子 (a 阶段 stub, b 阶段接入)
    # ---------------------------------------------------------------

    def attach_to_belief(
        self,
        evidence: Evidence,
        belief_state: Any,
        dim: str,
    ) -> None:
        """把 evidence_id 附加到 BeliefState.{dim}.evidence_ids (v0.83.0-b 接入).

        v0.83.0-a: stub, 不实现 (留给 b 阶段).
        """
        _log.debug(
            "EvidenceEngine.attach_to_belief v0.83.0-a stub (b 阶段接入): evidence_id=%s dim=%s",
            evidence.evidence_id, dim,
        )

    # ---------------------------------------------------------------
    # 内部工具
    # ---------------------------------------------------------------

    def _add_to_evidence_log(self, evidence: Evidence) -> int:
        """落 evidence_log 表 (RESPONSE_HISTORY + LLM_CRITIC + MISCONCEPTION + PARTIAL_CREDIT).

        v0.83.0-a: 直接写 SQL (不走 Database 级 save_evidence——该方法已于
                    v0.98.0 删除, 因重复死路径), 因为它强制 timestamp=now,
                    不接受 evidence.timestamp.
                    Evidence Engine 接受任意历史 timestamp (用于 replay/simulate).
        """
        ts_str = evidence.timestamp.isoformat()
        # payload 标 source_subtype (LLM_CRITIC / MISCONCEPTION / PARTIAL_CREDIT 子类型)
        payload_with_subtype = dict(evidence.payload)
        if evidence.source != EvidenceSource.RESPONSE_HISTORY:
            payload_with_subtype.setdefault("source_subtype", evidence.source.value)

        data = {
            "problem_id": evidence.problem_id or "",
            "timestamp": ts_str,
            "raw_response": json.dumps(payload_with_subtype, default=str),
            "raw_response_time": evidence.payload.get("response_time_sec", 0.0),
            "raw_explanation": evidence.payload.get("explanation_text", ""),
            "raw_reflection": evidence.payload.get("reflection", ""),
            "llm_critic_input": evidence.payload.get("llm_input", ""),
            "llm_critic_output": evidence.payload.get("llm_output", ""),
            "llm_critic_temperature": evidence.payload.get("llm_temperature"),
            "llm_critic_tokens": evidence.payload.get("llm_tokens"),
            "structured_correctness": int(evidence.payload.get("correct", False)),
            "structured_explanation_quality": evidence.payload.get("explanation_quality", 0.0),
            "structured_confusion_signals": evidence.payload.get("confusion_signals", []),
            "structured_self_evaluation": evidence.payload.get("self_evaluation", 0.0),
            "state_before_update": json.dumps(evidence.payload.get("state_before", {})),
            "state_after_update": json.dumps(evidence.payload.get("state_after", {})),
            "state_delta": evidence.state_delta or 0.0,
            "misc_hits": evidence.payload.get("misc_hits", []),
            "tc_signals": evidence.payload.get("tc_signals", []),
            "quality_score": evidence.confidence,
        }
        try:
            with self.db.tx() as _:
                cur = self.db.conn.execute(
                    """
                    INSERT INTO evidence_log (
                        student_id, problem_id, timestamp,
                        raw_response, raw_response_time, raw_explanation, raw_reflection,
                        llm_critic_input, llm_critic_output, llm_critic_temperature, llm_critic_tokens,
                        structured_correctness, structured_explanation_quality,
                        structured_confusion_signals, structured_self_evaluation,
                        state_before_update, state_after_update, state_delta,
                        misc_hits, tc_signals, quality_score
                    ) VALUES (
                        :sid, :pid, :ts,
                        :raw, :rtime, :expl, :refl,
                        :llm_in, :llm_out, :llm_temp, :llm_tokens,
                        :correct, :qual,
                        :confusion, :self_eval,
                        :before, :after, :delta,
                        :misc, :tc, :quality
                    )
                    """,
                    dict(
                        sid=evidence.student_id,
                        pid=data["problem_id"],
                        ts=data["timestamp"],
                        raw=data["raw_response"],
                        rtime=data["raw_response_time"],
                        expl=data["raw_explanation"],
                        refl=data["raw_reflection"],
                        llm_in=data["llm_critic_input"],
                        llm_out=data["llm_critic_output"],
                        llm_temp=data["llm_critic_temperature"],
                        llm_tokens=data["llm_critic_tokens"],
                        correct=data["structured_correctness"],
                        qual=data["structured_explanation_quality"],
                        confusion=json.dumps(data["structured_confusion_signals"]),
                        self_eval=data["structured_self_evaluation"],
                        before=data["state_before_update"],
                        after=data["state_after_update"],
                        delta=data["state_delta"],
                        misc=json.dumps(data["misc_hits"]),
                        tc=json.dumps(data["tc_signals"]),
                        quality=data["quality_score"],
                    ),
                )
                return cur.lastrowid or 0
        except Exception:
            _log.warning("_add_to_evidence_log 失败 (student=%s)", evidence.student_id,
                         exc_info=True)
            return 0

    def _add_to_calibration_log(self, evidence: Evidence) -> int:
        """落 calibration_log 表 (CALIBRATION_LOG)."""
        # db.save_calibration 的 schema 不一致, 简化用通用 save
        data = {
            "message_payload": json.dumps(evidence.payload, default=str),
            "actual_outcome": evidence.payload.get("actual_outcome"),
            "dual_agent_confidence": evidence.payload.get("dual_agent_confidence"),
            "dual_agent_confidence_source": evidence.payload.get("dual_agent_confidence_source"),
            "expected_gain": evidence.payload.get("expected_gain"),
            "intervention_id": evidence.payload.get("intervention_id"),
        }
        return self.db.save_calibration(evidence.student_id, data)

    def _add_to_event_log(self, evidence: Evidence) -> int:
        """落 event_log 表 (EVENT_LOG, v0.81)."""
        from ecos.cta.event_log import LearningEvent
        # evidence_id (int) -> event_id (str) 转换
        event = LearningEvent(
            event_id=f"evt_{evidence.evidence_id or id(evidence)}",
            student_id=evidence.student_id,
            timestamp=evidence.timestamp,
            source="evidence_engine",
            event_type=evidence.source.value,
            payload=evidence.payload,
        )
        self.event_log.log_event(event)
        # 返回 hash 后的 int 作为伪 evidence_id
        return abs(hash(event.event_id)) % (10 ** 8)

    def _row_to_evidence(self, row: dict, source: EvidenceSource) -> Optional[Evidence]:
        """db row -> Evidence."""
        try:
            # payload 从 raw_response 解析
            raw = row.get("raw_response", "")
            if isinstance(raw, str) and raw:
                try:
                    payload = json.loads(raw)
                except (json.JSONDecodeError, TypeError) as e:
                    _log.warning(
                        "_row_to_evidence raw_response 不是合法 JSON, fallback: %s",
                        e, exc_info=True,
                    )
                    payload = {"raw": raw}
            else:
                payload = dict(row)  # fallback: 整行作为 payload

            # timestamp
            ts_str = row.get("timestamp")
            if not ts_str:
                return None
            if isinstance(ts_str, datetime):
                ts = ts_str
            else:
                ts = datetime.fromisoformat(ts_str)

            # confidence 从 quality_score 取
            confidence = float(row.get("quality_score", 0.5))

            # v0.83.0-a: 如果 payload 含 source_subtype, 覆盖 source (LLM_CRITIC / MISCONCEPTION / PARTIAL_CREDIT)
            #   这些子类型在 db 落表时存 evidence_log, 物理上 source=response_history,
            #   但语义上是子类型. _row_to_evidence 还原语义.
            actual_source = source
            source_subtype = payload.get("source_subtype")
            if source_subtype:
                try:
                    actual_source = EvidenceSource.from_value(source_subtype)
                except ValueError:
                    _log.warning(
                        "_row_to_evidence 未知 source_subtype=%s, 保留主 source=%s",
                        source_subtype, source.value,
                    )
                    # 未知 subtype, 保留主 source

            return Evidence(
                evidence_id=row.get("evidence_id"),
                source=actual_source,
                student_id=row.get("student_id", ""),
                timestamp=ts,
                payload=payload,
                confidence=confidence,
                problem_id=row.get("problem_id"),
                skill_id=payload.get("skill_id"),
                state_delta=row.get("state_delta"),
            )
        except Exception:
            _log.warning("_row_to_evidence 失败, row=%s", row, exc_info=True)
            return None

    def _event_to_evidence(self, event) -> Optional[Evidence]:
        """LearningEvent -> Evidence."""
        try:
            evidence_id = abs(hash(event.event_id)) % (10 ** 8)
            return Evidence(
                evidence_id=evidence_id,
                source=EvidenceSource.EVENT_LOG,
                student_id=event.student_id,
                timestamp=event.timestamp,
                payload=event.payload,
                confidence=event.payload.get("confidence", 0.5),
            )
        except Exception:
            _log.warning("_event_to_evidence 失败, event=%s", event, exc_info=True)
            return None


__all__ = [
    "EvidenceEngine",
    "EvidenceConfig",
]
