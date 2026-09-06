"""misconception 证据闭环 (v0.97.3, P2 观测/对账) — CogMirror A2 移植.

对应:
  - README 恢复期 backlog P2 "A2 reconcile" (evidence_log 原料就位后)
  - CogMirror A2 `cogmirror/misconception_tracker.py` 移植 (PersonalAGI
    `learning/procedural/misconception_evidence` 纯算法核心, 零 LLM)
  - 方案决策 (2026-09-05 讨论, Bisen 拍板 Option A): 本期只落地追踪器
    + reconcile 入口, **不挂 C 维度折扣**——v0.97.2 已决议 C 维度等
    试点数据回来再定; A2 同批接入试点校准后的 `confidence_for()`
    接法。

与 CogMirror 的差异 (ECOS 适配):
  - **多学生**: ECOS 多人共享同一 DB; tracker 按 student_id 实例化
    (CogMirror 单人, in-memory 全局态)。`MisconceptionEvidenceTracker`
    不是单例, 每次按学生加载。
  - **reconcile 输入**: CogMirror 用 `db.load_responses` 的最小子集
    (skill_id, misc_id, score); ECOS 原料在 `evidence_log` 表, 需
    `EvidenceEngine.query_by_source(MISCONCEPTION, student_id)` 反查
    + parse `misc_hits` JSON 列表展开为 (misc_id, skill_id, score, ts)
    行, 再按时间升序喂给 reconcile。
  - **判对语义**: 同 v0.97.2 calibration_view —— 优先 `correct` 字段,
    缺失时 `score >= 0.6` 兜底 (与 `_entry_correct` 兼容约定一致)。
  - **持久化**: 走 `db.save_misconception_evidence(student_id, rows)`,
    不是 evidence_log 旁路; A2 是 derived 状态, 走自己表干净。
  - **不接 C 折扣**: v0.97.2 拍板纪律; `confidence_for(misc_id)` 暴露
    但 BeliefEngine 不消费, 试点数据回来同批接。

计数语义 (沿用 CogMirror 5.1/5.6 可证伪标准):
  - `record_success`: 命中后同 skill 下一条响应仍错或重触发, 预测成立
  - `record_failure`: 命中后同 skill 答对且未重触发, 预测证伪
  - 方向 = "检测模式对学习者可靠度" (PredictionReconciler), 不混
    学习者视角 "答对=success" (那样 Laplace 置信度与验收方向相反)

无主动"过时"判定 (无 TTL/时间衰减): 靠失败降档隐式淘汰; `quarantined`
仅作查询 (conf < 0.3 且 s+f >= 3), 产品路径暂不消费。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── 常量 (CogMirror A2 同款 + ECOS 本地化) ────────────────────────────

# 判对阈值 (与 v0.97.2 calibration_view / ECOS v0.54.0 派生一致)
CORRECT_THRESHOLD = 0.6
# quarantine 判定阈值 (源模式: conf < 0.3 且 s+f >= 3)
QUARANTINE_CONF_MAX = 0.3
QUARANTINE_MIN_EVIDENCE = 3


@dataclass(frozen=True)
class MisconceptionEvidenceRow:
    """单条 per-misconception 证据 (持久化单元).

    Attributes:
        misc_id:        命中的 misconception ID (如 "M1")
        success_count:  检测被证实次数 (后续仍错/重触发)
        failure_count:  检测被证伪次数 (后续答对)
        last_updated:   ISO timestamp
    """

    misc_id: str
    success_count: int
    failure_count: int
    last_updated: str

    @property
    def total(self) -> int:
        return self.success_count + self.failure_count

    def laplace_confidence(self) -> float:
        """Laplace 平滑 (s+1)/(s+f+2); 无证据时调用方走 0.5 先验."""
        return (self.success_count + 1) / (self.success_count + self.failure_count + 2)


class MisconceptionEvidenceTracker:
    """per-misconception 证据追踪器 (单学生, in-memory 缓存 + DB 持久化).

    设计同 v0.97.1 BKTModel / v0.97.2 calibration_view: pure-functional
    API, 同输入同输出, 不主动拉 BeliefState。`reconcile(evidence_rows)`
    接受 EvidenceEngine 反查出来的 (skill_id, misc_id, score, ts) 行,
    按时间升序遍历, 对每条带 misc_id 的行 join 同 skill 下一响应
    计 success/failure (无下一响应 → 不更新)。
    """

    def __init__(self) -> None:
        self._evidence: Dict[str, Dict[str, Any]] = {}

    # ── 持久化 ──────────────────────────────────────────────────────

    def load(self, rows: List[Dict[str, Any]]) -> None:
        """从 DB 行恢复 (db.load_misconception_evidence 的输出格式).

        重复 load() 是累加 (合并 success/failure 取 max, last_updated
        取较新), 不 reset —— 调用方负责按需 `clear()`。
        """
        for r in rows:
            misc_id = r.get("misc_id")
            if not misc_id:
                continue
            s = int(r.get("success_count", 0))
            f = int(r.get("failure_count", 0))
            ts = r.get("last_updated", "")
            existing = self._evidence.get(misc_id)
            if existing is None:
                self._evidence[misc_id] = {
                    "success": s, "failure": f, "last_updated": ts,
                }
            else:
                # 合并: 计数累加 (来源是同一学生同一 misc 的多份备份),
                # last_updated 取 max
                self._evidence[misc_id] = {
                    "success": existing["success"] + s,
                    "failure": existing["failure"] + f,
                    "last_updated": max(existing["last_updated"], ts) or ts,
                }

    def clear(self) -> None:
        """清空 in-memory 状态 (测试 / 强制 reload)."""
        self._evidence.clear()

    def dump(self) -> List[Dict[str, Any]]:
        """导出为 DB 行格式 (db.save_misconception_evidence 的输入).

        按 misc_id 排序保证可复现。
        """
        return [
            {
                "misc_id": misc_id,
                "success_count": e["success"],
                "failure_count": e["failure"],
                "last_updated": e["last_updated"],
            }
            for misc_id, e in sorted(self._evidence.items())
        ]

    # ── 查询 (C 维度折扣接入点; 本期不挂 BeliefState) ───────────

    def confidence_for(self, misc_id: str) -> float:
        """查询 misconception 的 Laplace 置信度 (0-1, 无证据 → 0.5 先验).

        这是 A2 reconcile 的对外消费入口; 试点数据回来后, C 维度折扣
        函数 (当前 `1.0 - conf * 0.3`) 可改读本接口。v0.97.3 暂不挂。
        """
        e = self._evidence.get(misc_id)
        if e is None:
            return 0.5
        return (e["success"] + 1) / (e["success"] + e["failure"] + 2)

    def quarantined(self, misc_id: str) -> bool:
        """检测长期被证伪 → 该关键词模式对这个学生不可靠 (查询辅助)."""
        e = self._evidence.get(misc_id)
        if e is None:
            return False
        total = e["success"] + e["failure"]
        return total >= QUARANTINE_MIN_EVIDENCE and self.confidence_for(misc_id) < QUARANTINE_CONF_MAX

    def evidence_for(self, misc_id: str) -> Optional[MisconceptionEvidenceRow]:
        """查询 per-misc 完整证据 (Web 教师端展示 / 调试用)."""
        e = self._evidence.get(misc_id)
        if e is None:
            return None
        return MisconceptionEvidenceRow(
            misc_id=misc_id,
            success_count=e["success"],
            failure_count=e["failure"],
            last_updated=e["last_updated"],
        )

    def all_evidence(self) -> List[MisconceptionEvidenceRow]:
        """全部 per-misc 证据 (Web 教师端列表 / 持久化导出用)."""
        return [
            MisconceptionEvidenceRow(
                misc_id=m,
                success_count=e["success"],
                failure_count=e["failure"],
                last_updated=e["last_updated"],
            )
            for m, e in sorted(self._evidence.items())
        ]

    # ── 更新 ───────────────────────────────────────────────────────

    def record_success(self, misc_id: str, now: Optional[datetime] = None) -> None:
        """检测被证实 (误解持续) —— 证据计数 +1."""
        self._bump(misc_id, "success", now)

    def record_failure(self, misc_id: str, now: Optional[datetime] = None) -> None:
        """检测被证伪 (已克服/误报) —— 证据计数 +1."""
        self._bump(misc_id, "failure", now)

    def reconcile(
        self,
        evidence_rows: List[Dict[str, Any]],
        now: Optional[datetime] = None,
    ) -> int:
        """对账: 把 misc 命中 join 到同 skill 的下一条响应 (零 LLM).

        Args:
            evidence_rows: 由 EvidenceEngine 反查 + 解析 misc_hits JSON
                得到的 (skill_id, misc_id, score, correct?, ts) 行列表;
                需按 timestamp 升序 (调用方负责)。
                最小字段: skill_id, misc_id (str|None), score (float),
                correct (bool|None, 缺则 score>=0.6 兜底)。
                misc_id 为 None/"" 的行不参与 (未命中不计数)。
            now: 写入 last_updated 的时间; 默认 datetime.now()。

        Returns:
            本次 reconcile 更新过的 misc 计数 (success+failure); 0 表示
            无新证据 (如窗口内全未命中, 或命中后无同 skill 下一响应)。

        与 CogMirror 的差异 (5.7 方案): window 必须限本次会话增量,
        不要传全量历史; 跨会话的"下一条响应"可能隔很久, 语义不成立。
        此外 ECOS evidence_log 落表可能已包含老命中 → 全量传会重复
        计数。调用方按 session 边界裁剪。
        """
        updated = 0
        for i, r in enumerate(evidence_rows):
            misc_id = r.get("misc_id")
            if not misc_id:
                continue
            for r2 in evidence_rows[i + 1:]:
                if r2.get("skill_id") != r.get("skill_id"):
                    continue
                retriggered = r2.get("misc_id") == misc_id
                score2 = float(r2.get("score") or 0.0)
                correct2 = r2.get("correct")
                if correct2 is None:
                    correct2 = score2 >= CORRECT_THRESHOLD
                if retriggered or not correct2:
                    self.record_success(misc_id, now=now)
                else:
                    self.record_failure(misc_id, now=now)
                updated += 1
                break
        return updated

    def _bump(self, misc_id: str, key: str, now: Optional[datetime]) -> None:
        e = self._evidence.setdefault(
            misc_id, {"success": 0, "failure": 0, "last_updated": ""}
        )
        e[key] += 1
        e["last_updated"] = (now or datetime.now()).isoformat()


# ── 工厂: 按学生从 DB 加载 (web API 调用方模式) ──────────────────────


def load_tracker_for_student(db: Any, student_id: str) -> MisconceptionEvidenceTracker:
    """从 DB 加载某学生的 tracker (web API 答题流注入点模式).

    db 必为 `ecos.persistence.db.Database` 实例; load 不存在 → 返回
    空 tracker (首次使用)。失败抛 → 调用方 try/except 兜底走无 tracker
    路径 (reconcile 退化为空操作, 不污染 evidence_log)。
    """
    tracker = MisconceptionEvidenceTracker()
    rows = db.load_misconception_evidence(student_id)
    tracker.load(rows)
    return tracker


def reconcile_for_student(
    db: Any,
    student_id: str,
    evidence_rows: List[Dict[str, Any]],
    now: Optional[datetime] = None,
) -> int:
    """便捷封装: 加载 → reconcile → 落库 (web API 一行调用).

    Returns:
        本次更新的 evidence 计数 (success+failure 之和)。
        DB 写失败返回 -1, 调用方据此回退 (不污染 evidence_log)。
    """
    try:
        tracker = load_tracker_for_student(db, student_id)
        updated = tracker.reconcile(evidence_rows, now=now)
        if updated > 0:
            db.save_misconception_evidence(student_id, tracker.dump())
        return updated
    except Exception:
        logger.warning(
            "reconcile_for_student 失败 (student=%s), 跳过本轮 reconcile",
            student_id, exc_info=True,
        )
        return -1


__all__ = [
    "CORRECT_THRESHOLD",
    "QUARANTINE_CONF_MAX",
    "QUARANTINE_MIN_EVIDENCE",
    "MisconceptionEvidenceRow",
    "MisconceptionEvidenceTracker",
    "load_tracker_for_student",
    "reconcile_for_student",
]
