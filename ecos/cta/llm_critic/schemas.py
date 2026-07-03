"""LLM Critic 的 JSON 输出 Schema（3 类 prompt）。

对应 research/10-engineering/01-cta-belief-engine.md §9.1-§9.3。
这些 dataclass 定义了 LLM 每次 JSON 输出的结构和类型约束。

M2 W3 温度：0.2（结构化输出稳定性优先）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..belief_state import BloomLevel


# ─── 感知层 Schema（§9.1）────────────────────────────────────────

@dataclass(frozen=True)
class PerceptionOutput:
    """感知层 LLM 输出的结构化数据。

    来源：research/10-engineering/01-cta-belief-engine.md §9.1。

    Attributes:
        correctness: LLM 判断学生作答是否正确（可能与题目对错标注不一致，用于 C 维度）
        explanation_quality: 学生解释文本的质量评分 0-1
        confusion_signals: 学生表达困惑的关键词列表（如"我不确定""可能是"）
        self_evaluation: 学生对自己作答的自信程度 0-1
        skill_ids: 从解释文本推断出的知识点 ID 列表（逗号分隔字符串）
        bloom_level: LLM 推断的学生认知层级（可能高于/低于题目原本预设）
        key_concepts: 解释中涉及的关键概念（list）
    """

    correctness: bool
    explanation_quality: float  # 0.0-1.0
    confusion_signals: tuple[str, ...] = field(default_factory=tuple)
    self_evaluation: float = 0.5  # 0.0-1.0
    skill_ids: tuple[str, ...] = field(default_factory=tuple)
    bloom_level: Optional[BloomLevel] = None
    key_concepts: tuple[str, ...] = field(default_factory=tuple)


# ─── 解释层 Schema（§9.2）────────────────────────────────────────

@dataclass(frozen=True)
class ExplanationOutput:
    """解释层 LLM 输出的诊断报告。

    来源：research/10-engineering/01-cta-belief-engine.md §9.2。

    Attributes:
        report: 自然语言诊断报告（200 字以内，面向不同受众）
        audience: 报告受众（'student' / 'teacher' / 'parent'）
        strongest_dimension: 5D 中最强的维度（K/P/S/C/X）
        weakest_dimension: 5D 中最弱的维度（K/P/S/C/X）
        recommended_intervention: 推荐干预方向（简短描述）
        bloom_gap: 当前 BloomProfile 与目标的差距（简短描述）
    """

    report: str
    audience: str = "student"
    strongest_dimension: str = "K"
    weakest_dimension: str = "C"
    recommended_intervention: str = ""
    bloom_gap: str = ""


# ─── Misconception 检测 Schema（§9.3）────────────────────────────────

@dataclass(frozen=True)
class MisconceptionDetectionOutput:
    """Misconception 检测结果。

    来源：research/10-engineering/01-cta-belief-engine.md §9.3。

    Attributes:
        misc_id: 命中的 misconception ID（如 "M1"，空字符串表示未命中）
        confidence: 命中置信度 0-1（0 表示无命中）
        evidence_text: 支持该判断的学生解释文本片段
        correction_strategy: 建议的修正策略 ID（来自 MisconceptionEntry.correction_strategy）
    """

    misc_id: str = ""
    confidence: float = 0.0
    evidence_text: str = ""
    correction_strategy: str = ""
