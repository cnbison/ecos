"""v0.95.1: 教师端 API — 班级列表 + 学生详情 (证据链 / POMDP 诊断 / 干预历史).

Teacher Dashboard 数据源 (全部只读, 不 mutate Kernel state, 防御性自检 [8] 0 mutation):
  - students 表: 班级名单 + last_active + bloom + confidence (DB 直读, 不 init BeliefEngine)
  - response_history: 答题证据链 (按 Q 矩阵 a_specialized 分配到 5D 维度)
  - misconception_history / tc_states: misconception + TC 证据
  - TeacherProgressPlugin: 教学建议 / 冷启动判断 (v0.95.1 UI 可消费)
  - Runtime.diagnose_pomdp: POMDP T/R 后验诊断 (lazy load LCA state)
  - LCAStore: 干预历史 (intervention_history)

对应 discussions/2026-08-17-v095方向审查 §决策 1 + §结论 4 (UI 是 Evidence 呈现面):
  - 班级视图优先: 教师先扫全班 (冷启动/状态 flag), 再单生深潜
  - 证据链按 5D 维度聚合 + 可下钻: "系统为什么这么判断"
  - Bisen 拍板 2026-08-17: 班级视图优先 + 单生深潜; 证据链按 5D 维度聚合可下钻

端点:
  GET /api/teacher/students                       — 班级列表 (roster)
  GET /api/teacher/students/<student_id>          — 学生详情 (state 摘要 + 教学建议)
  GET /api/teacher/students/<student_id>/evidence — 证据链 (按 5D 维度聚合 + 下钻)
  GET /api/teacher/students/<student_id>/diagnostic  — POMDP 诊断 (belief/coverage/advice)
  GET /api/teacher/students/<student_id>/interventions — 干预历史
  GET /api/teacher/students/<student_id>/calibration  — 自评校准视图 (v0.97.2)
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify

_log = logging.getLogger(__name__)

teacher_bp = Blueprint("teacher", __name__)

# v0.95.1: 5D 维度元数据 (教师端展示用)
DIMENSION_LABELS: Dict[str, Dict[str, str]] = {
    "K": {"label": "知识", "full": "Knowledge", "desc": "概念与事实性知识"},
    "P": {"label": "程序", "full": "Procedural", "desc": "步骤与流程执行"},
    "S": {"label": "策略", "full": "Strategic", "desc": "解题策略与规划"},
    "C": {"label": "置信", "full": "Confidence", "desc": "自我评估与把握度"},
    "X": {"label": "支架", "full": "Scaffolding", "desc": "外部支持依赖度"},
}

# POMDP 状态名 (跟 TeacherProgressPlugin / LCAEngine 一致)
_POMDP_STATE_NAMES = ("Engaged", "Frustrated", "Bored", "Confused")

# 维度加载阈值: a_specialized[dim] >= 0.2 才算该响应为该维度的证据
_DIM_LOADING_THRESHOLD = 0.2


# ─── DB 直读 helpers (不 init BeliefEngine) ───────────────────────────────────


def _get_db() -> Any:
    # ECOS_DB_PATH 可配置 (跟 web/api/lca.py 一致, 测试用 temp DB)
    import os
    from ecos.persistence.db import Database
    db_path = os.environ.get("ECOS_DB_PATH", "web/ecos.db")
    return Database(db_path)


def _load_student_row(student_id: str) -> Optional[Dict[str, Any]]:
    """读 students 表单行 (DB 直读, 不 init engine).

    Returns:
        dict(row) 或 None (学生不存在).
    """
    try:
        return _get_db().load_student_state(student_id)
    except Exception:
        _log.warning(
            "teacher: load_student_row 失败 (sid=%s)", student_id, exc_info=True
        )
        return None


def _json_field(row: Dict[str, Any], key: str) -> Any:
    """安全解析 JSON 列 (失败返回 None + warning, 不 silent pass)."""
    raw = row.get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        _log.warning(
            "teacher: 解析 JSON 列 %s 失败 (sid=%s), 返回 None",
            key, row.get("student_id"), exc_info=True,
        )
        return None


def _parse_responses(student_id: str) -> List[Dict[str, Any]]:
    """解析 response_history (DB 直读, 含每题的 a_specialized 维度加载).

    Returns:
        list of {problem_id, correct, score, bloom_level, timestamp,
                 user_answer, correct_answer, ai_reasoning, dims (5D bool)}
    """
    row = _load_student_row(student_id)
    if row is None:
        return []
    history = _json_field(row, "response_history")
    if not isinstance(history, list):
        return []

    from web.api.qmatrix import get_question_detail

    responses: List[Dict[str, Any]] = []
    for h in history:
        if isinstance(h, dict):
            pid = h.get("problem_id")
        else:
            # 老 3-tuple 兜底
            pid = h[0] if len(h) > 0 else None
        if not pid:
            continue

        # 维度加载向量 (从 Q 矩阵, 失败默认全 False)
        dims: List[bool] = [False] * 5
        prob = None
        try:
            prob = get_question_detail(pid)
        except Exception:
            _log.warning(
                "teacher: get_question_detail 失败 (pid=%s), 证据维度 fallback",
                pid, exc_info=True,
            )
        if prob and "a_specialized" in prob:
            try:
                a = prob["a_specialized"]
                dims = [bool(v >= _DIM_LOADING_THRESHOLD) for v in a]
            except Exception:
                _log.warning(
                    "teacher: a_specialized 解析失败 (pid=%s)", pid, exc_info=True
                )

        responses.append({
            "problem_id": pid,
            "correct": bool(h.get("correct")) if isinstance(h, dict) else bool(h[1]) if len(h) > 1 else False,
            "score": float(h.get("score", 1.0 if h.get("correct") else 0.0)) if isinstance(h, dict) else 1.0,
            "bloom_level": str(h.get("bloom_level")) if isinstance(h, dict) else str(h[2]),
            "timestamp": h.get("timestamp") if isinstance(h, dict) else None,
            "user_answer": h.get("user_answer") if isinstance(h, dict) else None,
            "correct_answer": h.get("correct_answer") if isinstance(h, dict) else None,
            "ai_reasoning": h.get("ai_reasoning") if isinstance(h, dict) else None,
            "dims": dims,
        })
    return responses


def _parse_misconceptions(student_id: str) -> List[Dict[str, Any]]:
    """解析 misconception_history (DB 直读)."""
    row = _load_student_row(student_id)
    if row is None:
        return []
    data = _json_field(row, "misconception_history")
    if not isinstance(data, list):
        return []
    return [
        {
            "misc_id": str(m.get("misc_id", "")),
            "confidence": float(m.get("confidence", 0.0)),
            "timestamp": m.get("timestamp"),
        }
        for m in data
        if isinstance(m, dict)
    ]


def _parse_tc_states(student_id: str) -> List[Dict[str, Any]]:
    """解析 TC states (DB 直读, 跨维度证据)."""
    row = _load_student_row(student_id)
    if row is None:
        return []
    data = _json_field(row, "tc_states")
    if not isinstance(data, dict):
        return []
    return [
        {
            "id": str(tc_id),
            "status": str(v.get("status", "")) if isinstance(v, dict) else "",
            "progress": float(v.get("progress", 0.0)) if isinstance(v, dict) else 0.0,
            "confidence": float(v.get("confidence", 0.0)) if isinstance(v, dict) else 0.0,
            "irreversible": bool(v.get("irreversible", False)) if isinstance(v, dict) else False,
        }
        for tc_id, v in data.items()
    ]


def _parse_bloom_summary(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """解析 current_bloom_profile → {dominant, confidence, levels}."""
    data = _json_field(row, "current_bloom_profile")
    if not isinstance(data, dict):
        return None
    return {
        "dominant": data.get("dominant_layer"),
        "confidence": float(data.get("confidence", 0.0)),
        "levels": {
            "L1": float(data.get("remember", 0.0)),
            "L2": float(data.get("understand", 0.0)),
            "L3": float(data.get("apply", 0.0)),
            "L4": float(data.get("analyze", 0.0)),
            "L5": float(data.get("evaluate", 0.0)),
            "L6": float(data.get("create", 0.0)),
        },
    }


def _parse_theta(row: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """解析 current_state_5d → {K,P,S,C,X: theta}."""
    data = _json_field(row, "current_state_5d")
    if not isinstance(data, list) or len(data) != 5:
        return None
    return {dim: round(float(data[i]), 4) for i, dim in enumerate(["K", "P", "S", "C", "X"])}


# ─── TeacherProgressPlugin 接入 (v0.95.1 UI 可消费) ───────────────────────────


def _get_teacher_progress_plugin() -> Any:
    """从 PluginRegistry 拿 TeacherProgressPlugin 实例.

    Returns:
        plugin 实例或 None (registry 未注册 / 不是该 plugin).
    """
    try:
        from ecos.plugins.registry import get_default_registry
        return get_default_registry().get("teacher_progress")
    except Exception:
        _log.warning("teacher: 拿 TeacherProgressPlugin 失败", exc_info=True)
        return None


def _get_progress_report(student_id: str) -> Optional[Dict[str, Any]]:
    """获取学生的教学建议报告 (插件缓存 → 按需诊断).

    优先级:
      1. TeacherProgressPlugin.report_for(student_id) (bus 事件已缓存)
      2. 缓存 miss → Runtime.diagnose_pomdp 按需派生 → ingest_diagnostic 喂 plugin

    Returns:
        report dict (most_likely_state / cold_start / advice / belief) 或 None
        (非 POMDP policy / 学生无 LCA 状态 / 派生失败).
    """
    plugin = _get_teacher_progress_plugin()
    if plugin is not None:
        cached = plugin.report_for(student_id)
        if cached is not None:
            return cached

    # 缓存 miss: 按需诊断 (lazy load LCA state, 跟 PluginRuntime 一致)
    try:
        from web.api.lca import _get_or_create_lca_state, get_lca_engine
        _get_or_create_lca_state(student_id)
        lca_engine = get_lca_engine()

        from ecos.runtime.api import diagnose_pomdp
        diagnostic = diagnose_pomdp(student_id=student_id, lca_engine=lca_engine)
        if diagnostic is None:
            return None

        if plugin is not None:
            return plugin.ingest_diagnostic(student_id, diagnostic)

        # 无 plugin 时, 直接派生最小 report (不依赖 plugin)
        from ecos.plugins.first_party.teacher_progress import (
            COLD_START_COVERAGE_THRESHOLD,
        )
        min_coverage = int(diagnostic.coverage.min())
        cold_start = min_coverage < COLD_START_COVERAGE_THRESHOLD
        most_likely_idx = diagnostic.most_likely_state
        most_likely_state = (
            _POMDP_STATE_NAMES[most_likely_idx]
            if 0 <= most_likely_idx < len(_POMDP_STATE_NAMES)
            else f"Unknown({most_likely_idx})"
        )
        return {
            "student_id": student_id,
            "most_likely_state": most_likely_state,
            "most_likely_state_index": most_likely_idx,
            "belief": diagnostic.belief.tolist(),
            "min_coverage": min_coverage,
            "cold_start": cold_start,
            "advice": (
                f"冷启动期 (min_coverage={min_coverage}), 建议保守教学"
                if cold_start
                else f"已冷启动完成 (min_coverage={min_coverage})"
            ),
            "updated_at": None,
        }
    except Exception:
        _log.warning(
            "teacher: 按需诊断失败 (sid=%s), report=None",
            student_id, exc_info=True,
        )
        return None


# ─── 干预历史 ────────────────────────────────────────────────────────────────


def _get_intervention_history(student_id: str) -> List[Dict[str, Any]]:
    """读 LCAStore 的 intervention_history (跟 lca.py 持久化同一数据源).

    Returns:
        list of Intervention.to_dict() (intervention_type / bloom_target /
        expected_gain / expected_risk / rationale / clt_level / ca_stage ...)
    """
    try:
        from web.api.lca import get_store
        store = get_store()
        if not store.has_state(student_id):
            return []
        snap = store.load_state(student_id)
        if snap is None:
            return []
        return list(snap.intervention_history)
    except Exception:
        _log.warning(
            "teacher: 读干预历史失败 (sid=%s), 返空列表",
            student_id, exc_info=True,
        )
        return []


# ─── Endpoints ────────────────────────────────────────────────────────────────


@teacher_bp.route("/api/teacher/students")
def api_teacher_students():
    """班级列表 (roster): 教师扫全班入口.

    Returns:
        {"students": [ {student_id, last_active_at, subject, grade_level,
                        answered_count, correct_rate, bloom_dominant,
                        overall_confidence, cold_start, most_likely_state,
                        risk, intervention_count} ]}
    """
    try:
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
            correct_rate = round(correct_count / answered_count, 4) if answered_count else 0.0

            bloom = _parse_bloom_summary(row)
            report = _get_progress_report(sid)

            # 风险 flag: Frustrated / Bored / Confused → 需关注
            risk = "ok"
            if report is not None:
                state = report.get("most_likely_state")
                if state in ("Frustrated", "Bored", "Confused"):
                    risk = "attention"

            students.append({
                "student_id": sid,
                "last_active_at": row.get("last_active_at"),
                "subject": row.get("subject"),
                "grade_level": row.get("grade_level"),
                "answered_count": answered_count,
                "correct_rate": correct_rate,
                "bloom_dominant": (bloom or {}).get("dominant"),
                "overall_confidence": round(float(row.get("confidence") or 0.0), 4),
                "cold_start": (report or {}).get("cold_start"),
                "most_likely_state": (report or {}).get("most_likely_state"),
                "risk": risk,
                "intervention_count": len(_get_intervention_history(sid)),
            })

        return jsonify({"students": students})
    except Exception:
        _log.warning("teacher: /api/teacher/students 失败", exc_info=True)
        return jsonify({"error": "班级列表获取失败", "students": []}), 500


@teacher_bp.route("/api/teacher/students/<student_id>")
def api_teacher_student_detail(student_id: str):
    """学生详情: state 摘要 + 教学建议 (单生深潜的概览卡).

    Returns:
        {student_id, answered_count, correct_rate, bloom_profile, theta_5d,
         overall_confidence, report, trajectory_summary}
    """
    try:
        row = _load_student_row(student_id)
        if row is None:
            return jsonify({"error": "学生不存在"}), 404

        responses = _parse_responses(student_id)
        answered_count = len(responses)
        correct_count = sum(1 for r in responses if r["correct"])
        correct_rate = round(correct_count / answered_count, 4) if answered_count else 0.0

        trajectory = _json_field(row, "trajectory_summary")
        if not isinstance(trajectory, list):
            trajectory = []

        return jsonify({
            "student_id": student_id,
            "answered_count": answered_count,
            "correct_rate": correct_rate,
            "bloom_profile": _parse_bloom_summary(row),
            "theta_5d": _parse_theta(row),
            "overall_confidence": round(float(row.get("confidence") or 0.0), 4),
            "report": _get_progress_report(student_id),
            "trajectory_summary": [
                {
                    "timestamp": t.get("timestamp"),
                    "theta_5d": t.get("theta_5d"),
                    "confidence": t.get("confidence"),
                    "bloom_dominant": t.get("bloom_dominant"),
                }
                for t in trajectory
                if isinstance(t, dict)
            ],
        })
    except Exception:
        _log.warning(
            "teacher: /api/teacher/students/%s 失败", student_id, exc_info=True
        )
        return jsonify({"error": "学生详情获取失败"}), 500


@teacher_bp.route("/api/teacher/students/<student_id>/evidence")
def api_teacher_student_evidence(student_id: str):
    """证据链视图: "系统为什么这么判断" — 按 5D 维度聚合 + 可下钻.

    每个维度: {theta, se, confidence, mastered, response_count, correct_rate,
              responses (该维度加载的答题记录, 含 user/correct answer + AI reasoning)}
    跨维度证据: misconceptions + tc_states.

    Returns:
        {student_id, dimensions: {K,P,S,C,X: {...}}, misconceptions, tc_states,
         summary: {answered_count, correct_rate}}
    """
    try:
        row = _load_student_row(student_id)
        if row is None:
            return jsonify({"error": "学生不存在"}), 404

        responses = _parse_responses(student_id)
        misconceptions = _parse_misconceptions(student_id)
        tc_states = _parse_tc_states(student_id)

        # theta_cov diag → SE (从 DB theta_cov 列)
        theta_cov = _json_field(row, "theta_cov")
        se_map: Dict[str, float] = {}
        if isinstance(theta_cov, list) and len(theta_cov) == 5:
            import math as _math
            for i, dim in enumerate(["K", "P", "S", "C", "X"]):
                try:
                    se_map[dim] = round(float(_math.sqrt(max(float(theta_cov[i][i]), 1e-6))), 4)
                except Exception:
                    se_map[dim] = 1.0

        theta = _parse_theta(row) or {d: 0.0 for d in ["K", "P", "S", "C", "X"]}

        # 按维度聚合证据
        dimensions: Dict[str, Dict[str, Any]] = {}
        for i, dim in enumerate(["K", "P", "S", "C", "X"]):
            dim_responses = [r for r in responses if r["dims"][i]]
            dim_count = len(dim_responses)
            dim_correct = sum(1 for r in dim_responses if r["correct"])
            mastered = 1.0 / (1.0 + 2.718281828459045 ** (-theta[dim])) >= 0.5
            dimensions[dim] = {
                "label": DIMENSION_LABELS[dim]["label"],
                "full": DIMENSION_LABELS[dim]["full"],
                "desc": DIMENSION_LABELS[dim]["desc"],
                "theta": theta[dim],
                "se": se_map.get(dim, 1.0),
                "confidence": round(1.0 / (1.0 + se_map.get(dim, 1.0)), 4),
                "mastered": mastered,
                "response_count": dim_count,
                "correct_rate": round(dim_correct / dim_count, 4) if dim_count else 0.0,
                "responses": [
                    {k: v for k, v in r.items() if k != "dims"}
                    for r in dim_responses
                ],
            }

        return jsonify({
            "student_id": student_id,
            "summary": {
                "answered_count": len(responses),
                "correct_rate": round(
                    sum(1 for r in responses if r["correct"]) / len(responses), 4
                ) if responses else 0.0,
            },
            "dimensions": dimensions,
            "misconceptions": misconceptions,
            "tc_states": tc_states,
        })
    except Exception:
        _log.warning(
            "teacher: /api/teacher/students/%s/evidence 失败", student_id, exc_info=True
        )
        return jsonify({"error": "证据链获取失败"}), 500


@teacher_bp.route("/api/teacher/students/<student_id>/diagnostic")
def api_teacher_student_diagnostic(student_id: str):
    """POMDP 诊断: belief 分布 + coverage + 教学建议 (T/R 后验可视化).

    Returns:
        {student_id, diagnostic: POMDPDiagnostic.to_dict() | null,
         report: TeacherProgressPlugin report | null,
         pomdp_state_names: [...]}
    """
    try:
        from web.api.lca import _get_or_create_lca_state, get_lca_engine
        _get_or_create_lca_state(student_id)
        lca_engine = get_lca_engine()

        from ecos.runtime.api import diagnose_pomdp
        diagnostic = diagnose_pomdp(student_id=student_id, lca_engine=lca_engine)

        report = None
        plugin = _get_teacher_progress_plugin()
        if diagnostic is not None:
            if plugin is not None:
                report = plugin.ingest_diagnostic(student_id, diagnostic)
            else:
                report = None

        return jsonify({
            "student_id": student_id,
            "diagnostic": diagnostic.to_dict() if diagnostic is not None else None,
            "report": report,
            "pomdp_state_names": list(_POMDP_STATE_NAMES),
        })
    except Exception:
        _log.warning(
            "teacher: /api/teacher/students/%s/diagnostic 失败", student_id, exc_info=True
        )
        return jsonify({"error": "POMDP 诊断获取失败"}), 500


@teacher_bp.route("/api/teacher/students/<student_id>/interventions")
def api_teacher_student_interventions(student_id: str):
    """干预历史: LCA 每次 select_intervention 的决策记录.

    Returns:
        {student_id, interventions: [Intervention.to_dict()]}
    """
    try:
        return jsonify({
            "student_id": student_id,
            "interventions": _get_intervention_history(student_id),
        })
    except Exception:
        _log.warning(
            "teacher: /api/teacher/students/%s/interventions 失败",
            student_id, exc_info=True,
        )
        return jsonify({"error": "干预历史获取失败"}), 500


@teacher_bp.route("/api/teacher/students/<student_id>/calibration")
def api_teacher_student_calibration(student_id: str):
    """自评校准视图 (v0.97.2): 自报 vs 实绩互校 — "系统为什么这么判断" 的 C 维度补充面.

    数据源 = students.response_history (DB 直读, 含 v0.97.2 self_confidence);
    计算 = calibration_view 无状态纯函数 (CogMirror A1 移植, 读时派生,
    不持久化)。无自评数据 → has_data False + curves 空 (前端展示"数据不足",
    不造曲线)。

    Returns:
        {student_id, has_data, n_total, n_self_assessed, n_skipped,
         curves: [{bucket, n, correct, predicted, actual_rate,
                   correction_factor}]}
    """
    try:
        row = _load_student_row(student_id)
        if row is None:
            return jsonify({"error": "学生不存在"}), 404

        history = _json_field(row, "response_history")
        if not isinstance(history, list):
            history = []

        from ecos.cta.calibration_view import calibration_view

        view = calibration_view([h for h in history if isinstance(h, dict)])
        return jsonify({
            "student_id": student_id,
            "has_data": view.has_data,
            "n_total": view.n_total,
            "n_self_assessed": view.n_self_assessed,
            "n_skipped": view.n_skipped,
            "curves": [
                {
                    "bucket": c.bucket,
                    "n": c.n,
                    "correct": c.correct,
                    "predicted": round(c.predicted, 4),
                    "actual_rate": round(c.actual_rate, 4),
                    "correction_factor": round(c.correction_factor, 4),
                }
                for c in view.curves
            ],
        })
    except Exception:
        _log.warning(
            "teacher: /api/teacher/students/%s/calibration 失败",
            student_id, exc_info=True,
        )
        return jsonify({"error": "校准视图获取失败"}), 500


__all__ = [
    "teacher_bp",
    "DIMENSION_LABELS",
]
