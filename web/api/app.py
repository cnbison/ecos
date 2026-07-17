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
    """获取下一道题目（W1 升级：透传 is_warmup + 自适应选题信息）。"""
    try:
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

        prob = select_question_for_student(
            answered_ids=answered_ids,
            is_warmup=is_warmup,
            theta_mean=theta_mean,
            theta_cov_diag=theta_cov_diag,
            target_bloom=target_bloom,
            student_id=student_id,
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
    return send_from_directory(
        Path(__file__).parent.parent / "student", "index.html"
    )


@app.route("/student/<path:filename>")
def student_static(filename: str):
    return send_from_directory(
        Path(__file__).parent.parent / "student", filename
    )


@app.route("/teacher/<path:filename>")
def teacher_static(filename: str):
    return send_from_directory(
        Path(__file__).parent.parent / "teacher", filename
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5173, debug=True)
