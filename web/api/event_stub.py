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

    Request JSON:
        {"student_id": str, "problem_id": str, "hint_level": int (1-3, default 1)}

    Returns:
        {"event_id": str, "student_id": str, "status": "logged"}

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
        return jsonify(_emit_event(student_id, event))
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
