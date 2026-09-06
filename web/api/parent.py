"""v0.98.0 (a-b): 家长端 API — 只读 roster + 单聚合 overview (Parent Dashboard 数据源).

Parent Dashboard 数据源 (全部只读, 不 mutate Kernel state, 防御性自检 [8] 0 mutation):
  - students 表: roster + five_d 摘要 (DB 直读, 不 init BeliefEngine)
  - ParentEngagementPlugin: engagement 状态 + 规则建议 (v0.98.0 (a-a) UI 可消费复活)
  - Runtime.diagnose_pomdp + diagnose_pomdp_evolution: POMDP 诊断 + 演化序列
    (lazy load LCA state, 缓存 miss 时按需诊断 → ingest 双喂入)
  - db.load_intervention_history: 干预历史 (接线审计 B 类 dead code → 本版本接活)

设计决策:
  - **严禁 _get_or_create_student** (v0.96.9 幽灵学生教训): 家长端只读,
    学生不存在直接 404, 不产生任何 DB 行
  - 单聚合端点 /overview: 家长端一次请求拿全部四卡数据 (Engagement / Advice /
    FiveD / Intervention), 避免多次往返
  - 不放校准视图 / misconceptions (Bisen 拍板 2026-09-06: 校准曲线是教师专业视图)
  - 复用 web.api.teacher 的 DB 直读 helpers (单一实现, 不复制解析逻辑)

端点:
  GET /api/parent/students                        — 学生列表 (roster, 只读)
  GET /api/parent/students/<student_id>/overview  — 单聚合 (engagement + advice + five_d + interventions)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify

_log = logging.getLogger(__name__)

parent_bp = Blueprint("parent", __name__)

# POMDP 状态名 (跟 ParentEngagementPlugin / teacher.py 一致)
_POMDP_STATE_NAMES = ("Engaged", "Frustrated", "Bored", "Confused")


def _get_parent_engagement_plugin() -> Any:
    """从 PluginRegistry 拿 ParentEngagementPlugin 实例 (跟 teacher.py 同模式).

    Returns:
        plugin 实例或 None (registry 未注册 / 不是该 plugin).
    """
    try:
        from ecos.plugins.registry import get_default_registry
        return get_default_registry().get("parent_engagement")
    except Exception:
        _log.warning("parent: 拿 ParentEngagementPlugin 失败", exc_info=True)
        return None


def _get_engagement_report(student_id: str) -> Optional[Dict[str, Any]]:
    """获取学生 engagement 报告 (插件缓存 → 按需诊断 + ingest 双喂入).

    优先级:
      1. ParentEngagementPlugin.report_for(student_id) (bus 事件已缓存)
      2. 缓存 miss → Runtime.diagnose_pomdp + diagnose_pomdp_evolution
         按需派生 → ingest_diagnostic + ingest_evolution 喂 plugin

    Returns:
        report dict (current_state / recent_states / advice / cold_start) 或 None
        (非 POMDP policy / 学生无 LCA 状态 / 派生失败).
    """
    plugin = _get_parent_engagement_plugin()
    if plugin is not None:
        cached = plugin.report_for(student_id)
        if cached is not None:
            return cached

    # 缓存 miss: 按需诊断 (lazy load LCA state, 跟 teacher.py _get_progress_report 一致)
    try:
        from web.api.lca import _get_or_create_lca_state, get_lca_engine
        _get_or_create_lca_state(student_id)
        lca_engine = get_lca_engine()

        from ecos.runtime.api import diagnose_pomdp, diagnose_pomdp_evolution
        diagnostic = diagnose_pomdp(student_id=student_id, lca_engine=lca_engine)
        if diagnostic is None:
            return None

        report: Optional[Dict[str, Any]] = None
        if plugin is not None:
            report = plugin.ingest_diagnostic(student_id, diagnostic)

        # evolution 序列 (diagnostic 不含 evolution, 经第 9 Runtime API 单独拿)
        evolution = diagnose_pomdp_evolution(student_id=student_id, lca_engine=lca_engine)
        if plugin is not None and evolution:
            report = plugin.ingest_evolution(student_id, evolution) or report

        return report
    except Exception:
        _log.warning(
            "parent: 按需诊断失败 (sid=%s), report=None",
            student_id, exc_info=True,
        )
        return None


@parent_bp.route("/api/parent/students")
def api_parent_students():
    """学生列表 (roster, 只读) — 家长端入口.

    严禁 _get_or_create_student (v0.96.9 幽灵学生教训):
    只读 students 表, 空表返回空列表, 不产生任何 DB 行.

    Returns:
        {"students": [ {student_id, subject, grade_level, last_active_at,
                        answered_count, correct_rate, current_state} ]}
    """
    try:
        from web.api.teacher import _get_db, _load_student_row, _parse_responses
        db = _get_db()
        sids = db.load_student_ids(limit=100)

        students: List[Dict[str, Any]] = []
        for sid in sids:
            row = _load_student_row(sid)
            if row is None:
                continue
            responses = _parse_responses(sid)
            answered_count = len(responses)
            correct_count = sum(1 for r in responses if r["correct"])
            correct_rate = (
                round(correct_count / answered_count, 4) if answered_count else 0.0
            )
            report = _get_engagement_report(sid)

            students.append({
                "student_id": sid,
                "subject": row.get("subject"),
                "grade_level": row.get("grade_level"),
                "last_active_at": row.get("last_active_at"),
                "answered_count": answered_count,
                "correct_rate": correct_rate,
                "current_state": (report or {}).get("current_state"),
            })

        return jsonify({"students": students})
    except Exception:
        _log.warning("parent: /api/parent/students 失败", exc_info=True)
        return jsonify({"error": "学生列表获取失败", "students": []}), 500


@parent_bp.route("/api/parent/students/<student_id>/overview")
def api_parent_student_overview(student_id: str):
    """单聚合 overview: engagement + advice + five_d + interventions (四卡数据).

    只读: 学生不存在 → 404 (不创建; 防幽灵学生).
    家长端不放校准视图 / misconceptions (教师专业视图, Bisen 拍板 2026-09-06).

    Returns:
        {student_id, engagement: {...report...}, five_d: {mastery, bloom},
         interventions: [...]}
    """
    try:
        from web.api.teacher import (
            _get_intervention_history,
            _load_student_row,
            _parse_bloom_summary,
            _parse_theta,
        )
        row = _load_student_row(student_id)
        if row is None:
            return jsonify({"error": "学生不存在", "student_id": student_id}), 404

        engagement = _get_engagement_report(student_id)
        interventions = _get_intervention_history(student_id)
        bloom = _parse_bloom_summary(row)
        theta = _parse_theta(row)

        return jsonify({
            "student_id": student_id,
            "subject": row.get("subject"),
            "engagement": engagement,
            "five_d": {
                "mastery": theta,
                "bloom": bloom,
                "overall_confidence": round(float(row.get("confidence") or 0.0), 4),
            },
            "interventions": interventions,
        })
    except Exception:
        _log.warning(
            "parent: /overview 失败 (sid=%s)", student_id, exc_info=True
        )
        return jsonify({"error": "概览获取失败", "student_id": student_id}), 500
