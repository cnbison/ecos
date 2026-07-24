"""Flask Web API——ECOS 学生端后端。

提供 REST API：
  GET  /api/state/<student_id>          — 获取学生当前信念状态
  GET  /api/question/<student_id>        — 获取下一道题目
  POST /api/answer                      — 提交答案，获取反馈 + 干预
  GET  /api/intervention/<student_id>    — 生成靶向干预（如果需要）
  GET  /api/history/<student_id>         — v0.49.2 答题历史详情
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

# 添加项目根目录到 Python 路径
_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_root))

from flask import Flask, jsonify, request, send_from_directory

from ecos.llm_client import ECOSLLMClient

from web.api.belief import get_student_state, submit_answer, _STUDENT_STATES
from web.api.interpretation import build_interpretation
from web.api.lca import get_lca_debug_info, select_intervention as lca_select
from web.api.qmatrix import get_question_detail, normalize_problem, select_question_for_student

_log = logging.getLogger(__name__)

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
                # v0.49.2: response_history 改 dict 格式, 兼容老 3-tuple
                answered_ids = {
                    h["problem_id"] if isinstance(h, dict) else h[0]
                    for h in engine._response_history[student_id]
                }

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

        # v0.56.0: LCA 接入 (passthrough——不改变选题行为, 仅记录干预决策)
        #   即使 LCA_ENABLED=False 也调, 用于:
        #   - 验证 LCA 在调用栈 (test_lca_wired.py)
        #   - 收集 LinUCB 训练数据
        #   - 失败时 fallback 到 CTA 选题 (现有逻辑不变)
        lca_info = None
        if state is not None:
            lca_result = lca_select(student_id, state)
            if lca_result is not None:
                lca_info = {
                    "intervention_type": lca_result.intervention.intervention_type.name,
                    "bloom_target": lca_result.bloom_target.name,
                    "clt_level": lca_result.clt_level.name,
                    "ca_stage": lca_result.ca_stage.name,
                    "expected_gain": round(lca_result.expected_gain, 3),
                    "expected_risk": round(lca_result.expected_risk, 3),
                }

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
        # v0.56.0: LCA 决策信息 (passthrough——前端可见, 不影响题目选择)
        if lca_info is not None:
            normalized["lca_decision"] = lca_info
        return jsonify(normalized)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── v0.56.1: LLM Judge retry helper (Bisen 原则) ─────────────────────────
def _call_llm_judge_with_retry(llm: ECOSLLMClient, prompt: str):
    """LLM judge retry loop (v0.56.1 修 BUG).

    Bisen 原则 (2026-07-24): LLM judge 失败时**不**启发式兜底, **不**字符串匹配兜底.
    任何 fallback 都是 silent degradation 变种, 失败就显式 fail.

    Args:
        llm: ECOSLLMClient 实例
        prompt: 评判 prompt

    Returns:
        (result_dict, attempt_count) 成功
        (None, attempt_count) 全部失败

    防御性自检 [1]: 每次重试失败必须 _log.warning(..., exc_info=True), 不能 silent pass.
    防御性自检 [6] (v0.56.1 新增): 不写启发式 fallback 替代 AI 评判.
    """
    delays = [0.1, 0.5, 2.0]  # 短-中-长 (s), Bisen 拍板 2026-07-24
    max_attempts = 3

    for attempt in range(1, max_attempts + 1):
        try:
            raw = llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                strip_think=True,
            )

            # 解析 JSON
            try:
                result = json.loads(raw)
                # 验证 result 至少有 correct 字段
                if "correct" not in result:
                    raise ValueError(f"LLM response missing 'correct' field: {(raw or '')[:100]}")
                return result, attempt
            except (json.JSONDecodeError, ValueError) as parse_err:
                _log.warning(
                    "/api/judge: LLM JSON parse 失败 (attempt %d/%d): %s, raw_truncated=%s",
                    attempt, max_attempts, parse_err, (raw or "")[:200],
                )
                if attempt < max_attempts:
                    time.sleep(delays[attempt - 1])
                continue
        except Exception as llm_err:
            _log.warning(
                "/api/judge: LLM chat 调用失败 (attempt %d/%d): %s",
                attempt, max_attempts, llm_err, exc_info=True,
            )
            if attempt < max_attempts:
                time.sleep(delays[attempt - 1])
            continue

    return None, max_attempts


@app.route("/api/judge", methods=["POST"])
def api_judge_answer():
    """LLM 充当老师，评判学生答案对错。

    v0.56.1 BUG 修复 (Bisen 原则 2026-07-24):
    - LLM judge 失败时**不**启发式兜底, **不**字符串匹配兜底 (silent degradation 变种)
    - retry 3 次 (100ms / 500ms / 2s delay, 短-中-长)
    - 全部失败 → return 422 + 显式 error + needs_rejudge=True
    - 关键: 任何失败路径**不污染 state** (response_history / 5D / Bloom / TC / misconception 一概不写)
    """
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
        result, attempts = _call_llm_judge_with_retry(llm, prompt)

        if result is None:
            # 3 次 retry 全部失败: 显式 fail, **不污染任何 state**
            # 防御性自检 [1]: 显式日志
            _log.warning(
                "/api/judge: LLM judge 全部 %d 次 retry 失败 (student=%s, problem=%s), "
                "返回 422 显式 fail, state 不污染",
                attempts, student_id, problem_id,
            )
            return jsonify({
                "judged": False,
                "error": "AI 评判服务故障，请稍后重试或跳过此题",
                "error_code": "LLM_JUDGE_FAILED",
                "problem_id": problem_id,
                "student_id": student_id,
                "retry_count": attempts,
                "needs_rejudge": True,
            }), 422

        return jsonify({
            "judged": True,
            "problem_id": problem_id,
            "student_id": student_id,
            "correct": bool(result.get("correct", False)),
            "reasoning": str(result.get("reasoning", "")),
            "attempts": attempts,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/answer", methods=["POST"])
def api_submit_answer():
    """提交答案，返回 BeliefEngine 更新结果。

    v0.54.0-e: partial credit 改造
    - 接收 score: float (0.0-1.0) 字段, 跟 correct: bool 配合
    - 老调用方不传 score: 用 correct 派生 (correct=True → score=1.0)
    - 新调用方传 score=0.7: 派生 correct=True (>=0.6)
    """
    try:
        data = request.get_json()
        student_id = data["student_id"]
        problem_id = data["problem_id"]
        skill_id = data["skill_id"]
        correct = bool(data["correct"])
        # v0.54.0-e: 接收 partial credit score 字段 (optional, 老调用方不传)
        #   优先级: score > correct (score >= 0.6 派生 correct)
        #   score 缺省时, 用 correct 派生 score (兼容老代码)
        raw_score = data.get("score", None)
        if raw_score is None:
            score = 1.0 if correct else 0.0  # 老代码兼容
        else:
            try:
                score = max(0.0, min(1.0, float(raw_score)))
            except (TypeError, ValueError):
                score = 1.0 if correct else 0.0  # 非数字 fallback
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
            user_answer=data.get("user_answer", ""),  # v0.49.2
            correct_answer=data.get("correct_answer", ""),  # v0.49.2
            # v0.52.2: AI reasoning 传给 submit_answer, 存进 response_history
            ai_reasoning=reasoning,
            # v0.54.0-e: partial credit score
            score=score,
        )
        result["reasoning"] = reasoning

        # v0.56.0: LCA update (基于 updated_state + score 计算 reward)
        #   必须在 submit_answer 拿到 updated_state 之后调, LCA 需要 new_state
        #   v0.56.0 简化版: reward = score + 0.5 * bloom_progress, 归一化到 [0, 1]
        #   防御性: LCA 失败不影响主响应
        try:
            from web.api.lca import update_with_reward as lca_update
            from ecos.cta.belief_state import BeliefState as _BS
            # 拿 updated_state (从 _STUDENT_STATES 读, 避免 submit_answer 返回值不带 state)
            student = _STUDENT_STATES.get(student_id, {})
            updated_state_obj = student.get("state")
            if isinstance(updated_state_obj, _BS):
                lca_update(
                    student_id=student_id,
                    belief_state=updated_state_obj,
                    score=score,
                    bloom_layer=bloom_layer,
                )
        except Exception:
            import logging as _lca_log
            _lca_log.getLogger(__name__).warning(
                "/api/answer LCA update 失败 (student=%s, problem=%s), 不影响主响应",
                student_id, problem_id, exc_info=True,
            )

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


@app.route("/api/lca_debug/<student_id>")
def api_lca_debug(student_id: str):
    """v0.56.0: LCA 调试接口 (教师后台 / 开发自检用).

    返回 LCA 内部状态 (last intervention / bandit arm 拉取次数等),
    不暴露学生个人隐私字段.

    注意: 这是调试接口, 跟 v0.51.4 settings 页版本号是同一类思路.
    """
    try:
        info = get_lca_debug_info(student_id)
        return jsonify(info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── v0.49.2: 答题历史详情 ───────────────────────────────────────────────────
@app.route("/api/history/<student_id>")
def api_get_history(student_id: str):
    """返回学生完整答题历史（按时间倒序）。

    每条 item:
      problem_id, correct(bool), bloom_level, user_answer, correct_answer, timestamp
    顶层: total, correct_rate
    """
    try:
        from web.api.belief import _get_or_create_student
        student = _get_or_create_student(student_id)
        engine = student["engine"]
        history = engine._response_history.get(student_id, [])

        # 按时间倒序（老数据 timestamp=None 排最后）
        def _ts_key(h):
            ts = h.get("timestamp") if isinstance(h, dict) else None
            return ts or ""
        items = sorted(history, key=_ts_key, reverse=True)

        # 去掉内部字段 _bloom_level_enum
        clean_items = []
        for h in items:
            if isinstance(h, dict):
                clean = {k: v for k, v in h.items() if not k.startswith("_")}
            else:
                # 老 3-tuple 数据兜底
                pid, correct, bl = h
                clean = {
                    "problem_id": pid,
                    "correct": int(correct),
                    "bloom_level": str(bl.name if hasattr(bl, "name") else bl),
                    "user_answer": None,
                    "correct_answer": None,
                    "timestamp": None,
                }
            clean_items.append(clean)

        total = len(clean_items)
        correct_count = sum(1 for x in clean_items if x.get("correct"))
        correct_rate = round(correct_count / total, 4) if total else 0.0
        return jsonify({
            "items": clean_items,
            "total": total,
            "correct_rate": correct_rate,
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
