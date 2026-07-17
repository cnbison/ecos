"""Python 基础 Q 矩阵加载器。

从 data/python_basics_q_matrix.json 加载题目，按 Bloom 层和 topic 分层抽样。

W1（2026-07-17）：select_question_for_student 拆为双策略——
  - warm-up 期：覆盖性选题（按 topic × bloom 分组轮询）
  - 5 题后：自适应选题（基于 SE 最大维度 + 弱 topic + Bloom Δ）
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

# warm-up 覆盖性选题的轮询游标（按 student_id 隔离）
# 每次 warm-up 选题后 cursor + 1，轮询 (topic × bloom) 所有组合
_WARMUP_CURSORS: dict[str, int] = {}


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


def _build_warmup_groups() -> list[tuple[str, str]]:
    """构建 (topic, bloom) 覆盖组合——按 Q 矩阵实际数据动态生成。

    返回：所有 (topic, bloom) 组合的列表，按 topic 字母序 + bloom 数字序排列。
    """
    all_probs = get_all_problems()
    seen: set[tuple[str, str]] = set()
    for p in all_probs:
        topic = p["topic"]
        bloom = p["bloom_goal_id"].split("-")[-1]
        seen.add((topic, bloom))
    return sorted(seen)  # 排序保证游标可复现


def _select_warmup_question(
    unanswered: list[dict],
    student_id: str,
    prefer_topics: list[str] | None = None,
) -> dict:
    """Warm-up 期覆盖性选题——按 topic 轮询，同一 topic 内选 lowest unanswered bloom。

    设计目标（W1 2026-07-17）：
      - 5 题覆盖 ≥3 个 topic（5D 各维度有探测机会）
      - 同一 topic 内，先打基础（L1）→ L2 → L3 ...
      - Q 矩阵 5 个 topic + 26 题，受限于题量不要求全覆盖 L1-L6

    Args:
        unanswered: 未答过的题目列表
        student_id: 学生 ID（用于游标隔离）
        prefer_topics: 优先 topic 列表（如果提供，先在这些 topic 内轮询）

    Returns:
        选中的题目 dict（带 _strategy="warmup" 标记）
    """
    # 提取所有可选 topic
    available_topics = sorted(set(p["topic"] for p in unanswered))
    if prefer_topics:
        # prefer_topics 排在最前（与 available_topics 求交）
        available_topics = [t for t in prefer_topics if t in available_topics] or available_topics

    cursor = _WARMUP_CURSORS.get(student_id, 0)

    # 从 cursor 位置开始轮询 topic
    for offset in range(len(available_topics)):
        idx = (cursor + offset) % len(available_topics)
        topic = available_topics[idx]
        # 在该 topic 内,选 lowest unanswered bloom
        topic_probs = [p for p in unanswered if p["topic"] == topic]
        if not topic_probs:
            continue
        # 按 bloom 数字升序（L1 < L2 < ...），取最小的
        topic_probs.sort(key=lambda p: p["bloom_goal_id"].split("-")[-1])
        # 选完后游标 +1
        _WARMUP_CURSORS[student_id] = (cursor + offset + 1) % len(available_topics)
        chosen = topic_probs[0]
        chosen["_strategy"] = "warmup"
        chosen["_warmup_group"] = f"{topic}:{chosen['bloom_goal_id'].split('-')[-1]}"
        return chosen

    # 理论上不会到这里（unanswered 非空）
    chosen = random.choice(unanswered)
    chosen["_strategy"] = "warmup"
    chosen["_warmup_group"] = "fallback"
    return chosen


def _select_adaptive_question(
    unanswered: list[dict],
    prefer_topics: list[str] | None = None,
    theta_mean: list[float] | None = None,
    theta_cov_diag: list[float] | None = None,
    target_bloom: str | None = None,
) -> dict:
    """自适应选题——基于 SE 最大维度 + 弱 topic + Bloom Δ（W1 2026-07-17 落地）。

    策略：
      1. 找 SE 最大的维度 d*（theta_cov_diag 最大）
      2. 该维度薄弱 topic（theta_mean[d*] 较低）
      3. 当前 Bloom 层 → 下一层（target_bloom 优先）
      4. 综合上述权重选 1 道

    Args:
        unanswered: 未答过的题目列表
        prefer_topics: 优先 topic 列表
        theta_mean: 5D 能力向量 [K, P, S, C, X]
        theta_cov_diag: 5D 协方差对角线 [var_K, var_P, var_S, var_C, var_X]
        target_bloom: 优先 Bloom 层（如 "L3"）

    Returns:
        选中的题目 dict（带 _strategy="adaptive" 标记）
    """
    candidates = list(unanswered)

    # prefer_topics 过滤
    if prefer_topics:
        preferred = [p for p in candidates if p["topic"] in prefer_topics]
        if preferred:
            candidates = preferred

    # target_bloom 优先
    if target_bloom:
        bloom_matched = [p for p in candidates if p["bloom_goal_id"].endswith(f"-{target_bloom}")]
        if bloom_matched:
            candidates = bloom_matched

    # 基于 a_specialized 权重：题目对 SE 最大维度的"匹配度" = a_specialized[d*]
    # d* = argmax(theta_cov_diag)
    if theta_cov_diag is not None and len(theta_cov_diag) == 5:
        d_star = int(max(range(5), key=lambda i: theta_cov_diag[i]))
    else:
        d_star = None

    def _score(p: dict) -> float:
        score = 0.0
        # 1. a_specialized 对 d* 的匹配度（信息量）
        if d_star is not None and "a_specialized" in p and len(p["a_specialized"]) == 5:
            score += float(p["a_specialized"][d_star]) * 1.0
        # 2. 优先 Bloom 匹配加权
        if target_bloom and p["bloom_goal_id"].endswith(f"-{target_bloom}"):
            score += 0.3
        # 3. prefer_topics 加权
        if prefer_topics and p["topic"] in prefer_topics:
            score += 0.2
        # 4. 加入少量随机性（避免每次都选同一道）
        score += random.random() * 0.1
        return score

    candidates_scored = sorted(candidates, key=_score, reverse=True)
    chosen = candidates_scored[0]
    chosen["_strategy"] = "adaptive"
    chosen["_adaptive_dim_star"] = d_star
    return chosen


def select_question_for_student(
    answered_ids: set[str],
    min_bloom: str = "L1",
    prefer_topics: list[str] | None = None,
    is_warmup: bool = False,
    theta_mean: list[float] | None = None,
    theta_cov_diag: list[float] | None = None,
    target_bloom: str | None = None,
    student_id: str = "_default",
) -> dict | None:
    """为学生选一道未答的题目。

    W1 升级（2026-07-17）：
      - is_warmup=True → 走覆盖性选题（按 topic × bloom 分组轮询）
      - is_warmup=False → 走自适应选题（基于 SE + Bloom Δ）

    旧版兼容：is_warmup 默认 False，走"prefer_topics → 随机"逻辑。
    """
    all_probs = get_all_problems()
    unanswered = [p for p in all_probs if p["problem_id"] not in answered_ids]
    if not unanswered:
        return None

    if is_warmup:
        return _select_warmup_question(unanswered, student_id, prefer_topics)

    # 自适应选题——如果没传 theta_cov_diag，降级为旧版 prefer_topics + 随机
    if theta_cov_diag is None:
        if prefer_topics:
            preferred = [p for p in unanswered if p["topic"] in prefer_topics]
            if preferred:
                chosen = random.choice(preferred)
                chosen["_strategy"] = "legacy_prefer"
                return chosen
        chosen = random.choice(unanswered)
        chosen["_strategy"] = "legacy_random"
        return chosen

    return _select_adaptive_question(
        unanswered,
        prefer_topics=prefer_topics,
        theta_mean=theta_mean,
        theta_cov_diag=theta_cov_diag,
        target_bloom=target_bloom,
    )


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
