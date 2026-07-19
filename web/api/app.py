"""Flask Web API——ECOS 学生端后端。

提供 REST API：
  GET  /api/state/<student_id>          — 获取学生当前信念状态
  GET  /api/question/<student_id>        — 获取下一道题目
  POST /api/answer                      — 提交答案，获取反馈 + 干预
  GET  /api/intervention/<student_id>    — 生成靶向干预（如果需要）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_root))

from flask import Flask, jsonify, request, send_from_directory

from ecos.llm_client import ECOSLLMClient

from web.api.belief import get_student_state, submit_answer, _STUDENT_STATES
from web.api.interpretation import build_interpretation
from web.api.qmatrix import get_question_detail, normalize_problem, select_question_for_student

# Flask app
app = Flask(__name__, static_folder=None)

# LLM 客户端（全局）
_llm_client: ECOSLLMClient | None = None


def get_llm() -> ECOSLLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = ECOSLLMClient.from_env("minimax")
    return _llm_client


# ─── 学生端 API ────────────────────────────────────────────────────────────────

@app.route("/api/students/recent")
def api_get_recent_students():
    """返回最近活跃学生列表（W5 改进,用于登录页快捷选择）。

    数据源:SQLite `students` 表按 last_active_at 倒序前 N 个。
    """
    try:
        from ecos.persistence.db import Database
        # 共享 web/ecos.db 同一个 DB
        db = Database("web/ecos.db")
        # 不调用 init_schema(已存在),只读
        sids = db.load_student_ids(limit=5)
        return jsonify({"students": sids})
    except Exception as e:
        return jsonify({"error": str(e), "students": []}), 500


@app.route("/api/version")
def api_get_version():
    """返回 ECOS 版本号（W5+ 改进,用于 dashboard 角标显示）。

    用途:Bisen 反馈问题时能立即知道跑的代码版本,避免'是 cache 还是真 bug'的混淆。
    """
    try:
        import ecos
        return jsonify({"version": ecos.__version__})
    except Exception as e:
        return jsonify({"error": str(e), "version": "unknown"}), 500


@app.route("/api/state/<student_id>")
def api_get_state(student_id: str):
    """获取学生当前 5D 信念状态。"""
    try:
        state = get_student_state(student_id)
        return jsonify(state)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/question/<student_id>")
def api_get_question(student_id: str):
    """获取下一道题目（W3 升级：探针题机制 + is_warmup + 自适应选题信息）。

    v0.47.1 修复（Bisen 反馈"重启后题目从头开始"）：
      兜底触发 _get_or_create_student,保证 engine/state 已加载(DB → in-memory),
      否则重启后第一次访问会因 _STUDENT_STATES 为空,导致:
        - answered_ids 空集
        - is_warmup 默认 True
        - 选题器走 warmup 路径,从 Q 矩阵任意抽题(可能选到已答过的)
    """
    try:
        # v0.47.1: 兜底——确保 _STUDENT_STATES[student_id] 存在
        get_student_state(student_id)

        # 获取已答题目的 ID（从 _STUDENT_STATES 历史）
        answered_ids: set[str] = set()
        if student_id in _STUDENT_STATES:
            engine = _STUDENT_STATES[student_id]["engine"]
            if hasattr(engine, "_response_history") and student_id in engine._response_history:
                answered_ids = {h[0] for h in engine._response_history[student_id]}

        # W1: 透传 warm-up 状态 + 5D 状态给选题器
        engine = None
        state = None
        if student_id in _STUDENT_STATES:
            engine = _STUDENT_STATES[student_id]["engine"]
            state = _STUDENT_STATES[student_id]["state"]

        is_warmup = engine.is_warmup(student_id) if engine is not None else True
        theta_mean = state.theta_mean.tolist() if state is not None else None
        theta_cov_diag = [float(state.theta_cov[i, i]) for i in range(5)] if state is not None else None
        target_bloom = None
        if state is not None and hasattr(state.bloom_profile, "distance_to_next_layer"):
            d = state.bloom_profile.distance_to_next_layer()
            target_bloom = d.get("next") if d.get("next") else None

        # W3: 探针题判断（最高优先级）
        should_probe = engine.should_probe_now(student_id) if engine is not None else False
        force_probe = should_probe
        if force_probe:
            engine.consume_probe(student_id)  # 重置 _probe_due_in

        prob = select_question_for_student(
            answered_ids=answered_ids,
            is_warmup=is_warmup,
            theta_mean=theta_mean,
            theta_cov_diag=theta_cov_diag,
            target_bloom=target_bloom,
            student_id=student_id,
            force_probe=force_probe,
        )
        if prob is None:
            return jsonify({"done": True, "message": "所有题目已完成"})

        normalized = normalize_problem(prob)
        # W1: 在响应里加 is_warmup + strategy
        normalized["is_warmup"] = is_warmup
        normalized["strategy"] = prob.get("_strategy", "unknown")
        if "_warmup_group" in prob:
            normalized["warmup_group"] = prob["_warmup_group"]
        if "_adaptive_dim_star" in prob:
            normalized["adaptive_dim_star"] = prob["_adaptive_dim_star"]
        # W3: 探针题信息
        normalized["is_probe"] = force_probe
        if "_probe_dim_star" in prob:
            normalized["probe_dim_star"] = prob["_probe_dim_star"]
        return jsonify(normalized)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/judge", methods=["POST"])
def api_judge_answer():
    """LLM 充当老师，评判学生答案对错。"""
    try:
        data = request.get_json()
        student_id = data["student_id"]
        problem_id = data["problem_id"]
        student_answer = data.get("student_answer", "").strip()

        if not student_answer:
            return jsonify({"error": "答案不能为空"}), 400

        # 加载题目
        prob = get_question_detail(problem_id)
        if not prob:
            return jsonify({"error": "题目不存在"}), 404

        correct_answer = prob.get("correct_answer", "")
        problem_text = prob.get("problem_text", "")

        prompt = f"""你是一位严格的 Python 老师。请评判学生答案是否正确。

题目：
{problem_text}

正确答案：
{correct_answer}

学生答案：
{student_answer}

请以 JSON 格式返回评判结果（只返回 JSON，不要其他内容）：
{{"correct": true/false, "reasoning": "简短说明为什么对或错（1-2句话）"}}
"""

        llm = get_llm()
        raw = llm.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            strip_think=True,
        )

        import json as _json
        try:
            result = _json.loads(raw)
        except Exception:
            # LLM 输出格式不对，降级为字符串匹配
            result = {
                "correct": student_answer.strip().lower() == correct_answer.strip().lower(),
                "reasoning": "（自动评判）答案文本匹配"
            }

        return jsonify({
            "judged": True,
            "problem_id": problem_id,
            "student_id": student_id,
            "correct": bool(result.get("correct", False)),
            "reasoning": str(result.get("reasoning", "")),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/answer", methods=["POST"])
def api_submit_answer():
    """提交答案，返回 BeliefEngine 更新结果。"""
    try:
        data = request.get_json()
        student_id = data["student_id"]
        problem_id = data["problem_id"]
        skill_id = data["skill_id"]
        correct = bool(data["correct"])
        bloom_layer = data.get("bloom_layer", "L2")
        explanation_text = data.get("explanation_text", "")
        reasoning = data.get("reasoning", "")

        result = submit_answer(
            student_id=student_id,
            problem_id=problem_id,
            skill_id=skill_id,
            correct=correct,
            bloom_layer=bloom_layer,
            explanation_text=explanation_text,
        )
        result["reasoning"] = reasoning
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/report/<student_id>")
def api_get_report(student_id: str):
    """导出学生学习报告（W3+ 落地，详见 discussions/2026-07-17-方向选择-A先C后.md §任务 4）。

    C 端接口:学生/家长可下载 JSON 格式的完整学习状态。
    v0.47.0 升级:
    - ecos_version 改为读 ecos.__version__(避免硬编码漂移)
    - 新增 interpretation 字段(规则引擎生成,无 LLM 调用,离线可用)
      详见 web/api/interpretation.py
    """
    try:
        from datetime import datetime as _dt
        import ecos as _ecos
        state = get_student_state(student_id)
        # 计算一些 summary
        trajectory = state.get("trajectory", [])
        answered_count = len(trajectory)
        current_bloom = state.get("bloom_profile", {}).get("dominant", "—")
        warmup_complete = not state.get("is_warmup", True)
        bloom_distance = state.get("bloom_layer_distance", {})

        # v0.47.0: 规则引擎生成自然语言解读(5D/Bloom/TC/轨迹/总评/建议)
        try:
            interpretation = build_interpretation(state)
        except Exception as interp_err:
            # 解读失败不阻塞主报告,降级为 None + 错误信息
            interpretation = {"error": str(interp_err)}

        report = {
            "student_id": student_id,
            "generated_at": _dt.now().isoformat(),
            "ecos_version": _ecos.__version__,
            "summary": {
                "answered_count": answered_count,
                "current_bloom_layer": current_bloom,
                "bloom_layer_distance": bloom_distance,
                "warmup_complete": warmup_complete,
                "warmup_progress": {
                    "count": state.get("warmup_count", 0),
                    "total": state.get("warmup_total", 5),
                },
                "probe_progress": {
                    "count": state.get("probe_count", 0),
                    "interval": state.get("probe_interval", 8),
                    "due_in": state.get("probe_due_in", 0),
                },
                "overall_confidence": state.get("overall_confidence", 0.0),
                "c_discount_factor": state.get("c_discount_factor", 1.0),
            },
            "interpretation": interpretation,
            "state": state,
        }
        return jsonify(report)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/intervention/<student_id>", methods=["POST"])
def api_generate_intervention(student_id: str):
    """生成靶向干预（LLM 充当领域专家）。"""
    try:
        data = request.get_json()
        misc_id = data.get("misc_id", "")
        student_answer = data.get("student_answer", "")
        problem_text = data.get("problem_text", "")

        if not misc_id:
            return jsonify({"intervention": "", "type": "none"})

        # 从 misconception 库获取信息
        from ecos.cta.content import PythonBasicsMisconceptionLibrary

        lib = PythonBasicsMisconceptionLibrary()
        entry = lib.get(misc_id)
        if not entry:
            return jsonify({"intervention": "", "type": "none"})

        prompt = f"""你是一位 Python 教学专家。学生的回答触发了以下 misconception：

Misconception ID: {entry.misc_id}
名称: {entry.name}
描述: {entry.description}

学生回答证据: {student_answer}

请生成一段针对该 misconception 的靶向干预（100-200字），要求：
1. 用学生能理解的类比或解释
2. 直接指出学生理解的错误所在
3. 给出正确的理解

干预内容："""

        llm = get_llm()
        response = llm.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            strip_think=True,
        )

        return jsonify({
            "intervention": response,
            "type": "EXPLANATORY",
            "misc_id": misc_id,
            "misc_name": entry.name,
            "correction_strategy": entry.correction_strategy,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── 静态文件服务 ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """W5 修复：加 Cache-Control: no-cache 头,避免浏览器缓存旧版 index.html。
    Bisen 反馈：input 默认值是 W5 改动后的逻辑，但浏览器渲染异常，
    根因是浏览器缓存了 W4 之前版本的 JS。
    """
    response = send_from_directory(
        Path(__file__).parent.parent / "student", "index.html"
    )
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.route("/student/<path:filename>")
def student_static(filename: str):
    """W5 修复：加 Cache-Control: no-cache 头（同上）。"""
    response = send_from_directory(
        Path(__file__).parent.parent / "student", filename
    )
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.route("/teacher/<path:filename>")
def teacher_static(filename: str):
    """W5 修复：加 Cache-Control: no-cache 头（同上）。"""
    response = send_from_directory(
        Path(__file__).parent.parent / "teacher", filename
    )
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5173, debug=True)
