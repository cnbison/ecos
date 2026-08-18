"""v0.85.0-d: Frontend event stub endpoints.

4 个 Flask endpoint 供 frontend 调用, emit 4 个新 event_type:
  - POST /api/event/hint         -> HINT_REQUESTED
  - POST /api/event/idle         -> IDLE_DETECTED
  - POST /api/event/goal_change  -> GOAL_CHANGED
  - POST /api/event/reflection   -> REFLECTION_COMPLETED

每个 endpoint 接收 JSON, 构造 LearningEvent, emit 到 default bus. Plugin
SDK 原则: endpoint 不写 state, 只产生 event (subscriber 处理).

Phase 7+ 计划: EventBus subscriber 可订阅这些 event, 触发 LCA 动态调整 /
LLM reflection 分析 / nudge 等高级行为. v0.85.0-d 只 framework, 无实际
subscriber 处理 (留 v0.86+).

Per discussions/2026-08-11-v085-design.md §5.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict

from flask import Blueprint, jsonify, request

_log = logging.getLogger(__name__)

# v0.85.0-d: Blueprint for frontend event stub endpoints
event_stub_bp = Blueprint("event_stub", __name__)

# v0.96.7: Bloom 层中文标签（hint 生成用）
_BLOOM_LABELS = {
    "L1": "记忆",
    "L2": "理解",
    "L3": "应用",
    "L4": "分析",
    "L5": "评价",
    "L6": "创造",
}

# v0.96.7: M-candidate-* / M-illinois-* 不在 PythonBasicsMisconceptionLibrary (M1-M8) 内,
# 手动兜底映射（描述取自 data/python_basics_q_matrix.json 对应题目上下文, 非权威库）。
_MISC_FALLBACK = {
    "M-candidate-scope-confusion": "作用域混淆：函数内直接 x = x + 1 会触发 UnboundLocalError，改全局变量要先声明 global。",
    "M-candidate-mutable-confusion": "可变对象引用混淆：变量是标签不是盒子，b = a 后 b.append 会同时改到 a。",
    "M-candidate-mutable-default": "可变默认参数陷阱：def f(x, lst=[]) 的 [] 只创建一次，多次调用会累积，改用 lst=None。",
    "M-candidate-recursion-no-memo": "递归未记忆化：fib(n) 不缓存会重复计算，量大时卡死，加 memo 或改自底向上。",
    "M-candidate-nested-loop-confusion": "嵌套循环混淆：break 只跳出内层循环，不会跳出外层。",
    "M-candidate-closure-binding": "闭包延迟绑定：循环内 lambda 捕获的是同一个变量，调用时才取值。",
    "M-illinois-confidence-avoid-help": "这道题在考察求助行为：先独立思考，再决定是否需要求助。",
    "M-illinois-tool-avoidance": "这道题在考察工具使用：不确定时查资料/笔记也是学习的一部分。",
    "M-illinois-overconfidence": "这道题在考察过度自信：做完请再检查一遍，别凭直觉直接提交。",
    "M-illinois-overdependence": "这道题在考察过度依赖：别每次都查，先凭已有知识试答。",
    "M-illinois-scaffolding-overdependence": "这道题在考察对讲解的依赖：先自己尝试，再决定是否需要示例。",
}


def _build_hint(problem) -> str:
    """基于题目元数据生成规则提示（不泄漏 correct_answer）。

    Hint 只取材: skill_name + Bloom 层中文标签 + misconceptions 描述 + 通用作答建议。
    """
    bloom = problem.get("bloom_goal_id", "").split("-")[-1]
    bloom_label = _BLOOM_LABELS.get(bloom, bloom)
    skill = problem.get("skill_name") or problem.get("topic") or "本题"
    lines = [f"这道题考查「{skill}」({bloom} {bloom_label})。"]

    misc_codes = problem.get("misconceptions") or []
    if misc_codes:
        lines.append("⚠️ 关联常见误区：")
        lib = None
        try:
            from ecos.cta.content.python_basics_misconceptions import (
                PythonBasicsMisconceptionLibrary,
            )
            lib = PythonBasicsMisconceptionLibrary()
        except Exception:
            _log.warning(
                "event_stub: misconception library 加载失败, 用兜底映射",
                exc_info=True,
            )
        for code in misc_codes[:2]:
            desc = None
            if lib is not None:
                entry = lib.get(code)
                if entry is not None:
                    desc = f"{entry.name}：{entry.description}"
            if desc is None:
                desc = _MISC_FALLBACK.get(code)
            if desc:
                lines.append(f"  · {desc}")
    else:
        lines.append("先回顾相关概念与示例，再动手作答。")

    lines.append("先写出思路与边界条件，再写代码，别急着提交。")
    return "\n".join(lines)


def _emit_event(student_id: str, event) -> Dict[str, Any]:
    """Helper: emit event to default bus + return {event_id, status}.

    Returns:
        {"event_id": str, "student_id": str, "status": "logged"}
    """
    try:
        from ecos.event import get_default_bus
        bus = get_default_bus()
        # 推断 topic = event.event_type (PluginRuntime 也用此 pattern)
        bus.publish(event.event_type, event)
    except Exception:
        _log.warning(
            "event_stub: emit event 失败 (sid=%s, type=%s), "
            "event 不写, response 仍正常返回",
            student_id, event.event_type, exc_info=True,
        )
    return {
        "event_id": event.event_id,
        "student_id": student_id,
        "status": "logged",
    }


@event_stub_bp.route("/api/event/hint", methods=["POST"])
def api_event_hint():
    """POST /api/event/hint — frontend 学生请求提示.

    v0.96.7: 除埋点外, 基于题目元数据返回规则生成的 hint 内容（不泄漏答案）。

    Request JSON:
        {"student_id": str, "problem_id": str, "hint_level": int (1-3, default 1)}

    Returns:
        {"event_id": str, "student_id": str, "status": "logged",
         "hint": str}  # v0.96.7: 规则生成提示; problem 未知时返回通用兜底提示

    Emits:
        LearningEvent(event_type="hint_requested", payload={problem_id, hint_level})
    """
    try:
        data = request.get_json()
        student_id = data["student_id"]
        problem_id = data["problem_id"]
        hint_level = int(data.get("hint_level", 1))

        from ecos.cta.event_log import LearningEvent
        event = LearningEvent.from_hint_requested(
            student_id=student_id,
            problem_id=problem_id,
            hint_level=hint_level,
        )
        result = _emit_event(student_id, event)

        from web.api.qmatrix import get_question_detail
        problem = get_question_detail(problem_id)
        if problem is None:
            _log.warning(
                "event_stub: hint 请求 problem_id=%r 不在 Q 矩阵, 返回兜底提示",
                problem_id,
            )
            result["hint"] = (
                "这道题暂时没有针对性的提示。先通读题目、回顾相关概念，"
                "把思路写出来再作答。"
            )
        else:
            result["hint"] = _build_hint(problem)
        return jsonify(result)
    except (KeyError, TypeError, ValueError) as e:
        return jsonify({"error": f"Bad request: {e}"}), 400
    except Exception as e:
        _log.warning("/api/event/hint 失败: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@event_stub_bp.route("/api/event/idle", methods=["POST"])
def api_event_idle():
    """POST /api/event/idle — frontend 检测学生 idle.

    Request JSON:
        {"student_id": str, "idle_seconds": float}

    Returns:
        {"event_id": str, "student_id": str, "status": "logged"}

    Emits:
        LearningEvent(event_type="idle_detected", payload={idle_seconds})
    """
    try:
        data = request.get_json()
        student_id = data["student_id"]
        idle_seconds = float(data["idle_seconds"])

        from ecos.cta.event_log import LearningEvent
        event = LearningEvent.from_idle_detected(
            student_id=student_id,
            idle_seconds=idle_seconds,
        )
        return jsonify(_emit_event(student_id, event))
    except (KeyError, TypeError, ValueError) as e:
        return jsonify({"error": f"Bad request: {e}"}), 400
    except Exception as e:
        _log.warning("/api/event/idle 失败: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@event_stub_bp.route("/api/event/goal_change", methods=["POST"])
def api_event_goal_change():
    """POST /api/event/goal_change — frontend 学生切换学习目标.

    Request JSON:
        {"student_id": str, "old_goal_id": str, "new_goal_id": str}

    Returns:
        {"event_id": str, "student_id": str, "status": "logged"}

    Emits:
        LearningEvent(event_type="goal_changed", payload={old_goal_id, new_goal_id})
    """
    try:
        data = request.get_json()
        student_id = data["student_id"]
        old_goal_id = data["old_goal_id"]
        new_goal_id = data["new_goal_id"]

        from ecos.cta.event_log import LearningEvent
        event = LearningEvent.from_goal_changed(
            student_id=student_id,
            old_goal_id=old_goal_id,
            new_goal_id=new_goal_id,
        )
        return jsonify(_emit_event(student_id, event))
    except (KeyError, TypeError, ValueError) as e:
        return jsonify({"error": f"Bad request: {e}"}), 400
    except Exception as e:
        _log.warning("/api/event/goal_change 失败: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@event_stub_bp.route("/api/event/reflection", methods=["POST"])
def api_event_reflection():
    """POST /api/event/reflection — frontend 学生完成反思.

    Request JSON:
        {"student_id": str, "reflection_text": str, "problem_id": str (optional)}

    Returns:
        {"event_id": str, "student_id": str, "status": "logged"}

    Emits:
        LearningEvent(event_type="reflection_completed", payload={reflection_text, problem_id})
    """
    try:
        data = request.get_json()
        student_id = data["student_id"]
        reflection_text = data["reflection_text"]
        problem_id = data.get("problem_id")  # optional

        from ecos.cta.event_log import LearningEvent
        event = LearningEvent.from_reflection_completed(
            student_id=student_id,
            reflection_text=reflection_text,
            problem_id=problem_id,
        )
        return jsonify(_emit_event(student_id, event))
    except (KeyError, TypeError, ValueError) as e:
        return jsonify({"error": f"Bad request: {e}"}), 400
    except Exception as e:
        _log.warning("/api/event/reflection 失败: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500
