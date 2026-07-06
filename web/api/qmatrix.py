"""Python 基础 Q 矩阵加载器。

从 data/python_basics_q_matrix.json 加载题目，按 Bloom 层和 topic 分层抽样。
"""

from __future__ import annotations

import json
import sys
import random
from pathlib import Path
from typing import Any

# 添加项目根目录
_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_root))

_Q_MATRIX: dict[str, Any] | None = None
_Q_PROBLEMS: list[dict] | None = None


def _load_q_matrix() -> dict[str, Any]:
    global _Q_MATRIX, _Q_PROBLEMS
    if _Q_MATRIX is None:
        root = Path(__file__).parent.parent.parent
        path = root / "data" / "python_basics_q_matrix.json"
        with open(path, encoding="utf-8") as f:
            _Q_MATRIX = json.load(f)
        _Q_PROBLEMS = _Q_MATRIX["problems"]
    return _Q_MATRIX


def get_all_problems() -> list[dict]:
    _load_q_matrix()
    return _Q_PROBLEMS


def get_problems_by_topic(topic: str) -> list[dict]:
    return [p for p in get_all_problems() if p["topic"] == topic]


def get_problems_by_bloom(bloom_layer: str) -> list[dict]:
    return [p for p in get_all_problems() if p["bloom_goal_id"].endswith(f"-{bloom_layer}")]


def select_question_for_student(
    answered_ids: set[str],
    min_bloom: str = "L1",
    prefer_topics: list[str] | None = None,
) -> dict | None:
    """为学生选一道未答的题目。

    策略：优先选学生薄弱 topic + 低 Bloom 层题目，逐步提升。
    """
    all_probs = get_all_problems()
    unanswered = [p for p in all_probs if p["problem_id"] not in answered_ids]
    if not unanswered:
        return None

    # 优先选指定 topic（prefer_topics 优先）
    if prefer_topics:
        preferred = [p for p in unanswered if p["topic"] in prefer_topics]
        if preferred:
            return random.choice(preferred)

    # 否则随机选一道未答的
    return random.choice(unanswered)


def get_question_detail(problem_id: str) -> dict | None:
    for p in get_all_problems():
        if p["problem_id"] == problem_id:
            return p
    return None


def normalize_problem(prob: dict) -> dict:
    """将 Q 矩阵题目规范化为前端需要的格式（去除答案等敏感字段）。"""
    return {
        "problem_id": prob["problem_id"],
        "bloom_goal_id": prob["bloom_goal_id"],
        "topic": prob["topic"],
        "skill_name": prob["skill_name"],
        "bloom_layer": prob["bloom_goal_id"].split("-")[-1],
        "problem_text": prob["problem_text"],
        "misconceptions": prob.get("misconceptions", []),
        "intervention_types": prob.get("intervention_types", []),
    }
