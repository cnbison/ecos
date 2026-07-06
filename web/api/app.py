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
    """获取下一道题目。"""
    try:
        # 获取已答题目的 ID（从 _STUDENT_STATES 历史）
        answered_ids: set[str] = set()
        if student_id in _STUDENT_STATES:
            engine = _STUDENT_STATES[student_id]["engine"]
            if hasattr(engine, "_response_history") and student_id in engine._response_history:
                answered_ids = {h[0] for h in engine._response_history[student_id]}

        prob = select_question_for_student(answered_ids)
        if prob is None:
            return jsonify({"done": True, "message": "所有题目已完成"})

        return jsonify(normalize_problem(prob))
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

        result = submit_answer(
            student_id=student_id,
            problem_id=problem_id,
            skill_id=skill_id,
            correct=correct,
            bloom_layer=bloom_layer,
            explanation_text=explanation_text,
        )
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
