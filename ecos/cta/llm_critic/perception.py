"""LLM Critic 感知层——PerceptionCritic.

对应 research/10-engineering/01-cta-belief-engine.md §9.1。

职责：把学生的自然语言解释文本转成结构化信号。
边界：只做感知，不做解释（解释层在 explanation.py）。
温度：0.2（JSON 输出稳定性优先）。

M2 W3 集成点：
  BeliefEngine.update() 在处理完 L1 BKT / L2 MIRT 之后，
  调用 PerceptionCritic.perceive() 更新 BloomProfile（bloom_level 推断）
  和 C 维度感知质量（explanation_quality）。
"""

from __future__ import annotations

import logging
from typing import Any

from ...llm_client import ECOSLLMClient
from ..belief_state import BloomLevel
from .schemas import PerceptionOutput

logger = logging.getLogger(__name__)


# ─── Prompt 模板 ─────────────────────────────────────────────────

_PERCEPTION_PROMPT = """你是一位教育评估专家。请分析学生的作答，提取结构化信息。

题目：{problem}
题目正确答案：{correct_answer}
学生作答（正确/错误）：{student_correctness}
学生解释文本：{student_explanation}

请提取以下信息（JSON 格式）：
{{
  "correctness": true或false（你判断的学生实际是否理解，正确与否不是重点），
  "explanation_quality": 0.0到1.0之间（学生解释文本的认知深度评分），
  "confusion_signals": ["学生表达困惑的关键词或短语列表，如"我不确定"、"可能是"等"]，
  "self_evaluation": 0.0到1.0之间（学生对自己作答的自信程度），
  "skill_ids": ["从解释中推断的知识点ID，如math.algebra.linear"],
  "bloom_level": "L1"到"L4"之一（学生表现出的认知层级），
  "key_concepts": ["解释中涉及的关键概念名称列表"]
}}

注意事项：
- correctness 评估的是学生是否真正理解，不是题目是否做对（两者可能不一致）
- confusion_signals 如果学生没有表达困惑，返回空列表 []
- bloom_level 基于学生解释的认知深度判断（L1=记忆，L2=理解，L3=应用，L4=分析）
- skill_ids 如果无法推断，返回空列表 []
"""


class PerceptionCritic:
    """LLM Critic 感知层。

    用法：
        critic = PerceptionCritic(llm_client)
        result = critic.perceive(
            problem="解方程 2x+3=7",
            correct_answer="x=2",
            student_correctness=True,
            student_explanation="两边同时减去3，再除以2，得到x=2",
        )
    """

    def __init__(self, llm_client: ECOSLLMClient) -> None:
        self.llm = llm_client

    def perceive(
        self,
        problem: str,
        correct_answer: str,
        student_correctness: bool,
        student_explanation: str,
    ) -> PerceptionOutput:
        """将学生自然语言解释转为结构化感知结果。

        v0.49.3: 若 LLM client 未配置, 返回空感知(默认值), 由 belief.py
          错误隔离兜底。避免 self.llm is None 时 AttributeError 打 stderr。

        Args:
            problem: 题目描述
            correct_answer: 正确答案
            student_correctness: 学生作答是否正确
            student_explanation: 学生写的解释文本

        Returns:
            PerceptionOutput 结构化感知结果
        """
        if self.llm is None:
            logger.warning(
                "PerceptionCritic.perceive: LLM client 未配置, 跳过(返回空感知)"
            )
            return PerceptionOutput()
        messages = [
            {
                "role": "user",
                "content": _PERCEPTION_PROMPT.format(
                    problem=problem,
                    correct_answer=correct_answer,
                    student_correctness="正确" if student_correctness else "错误",
                    student_explanation=student_explanation or "（学生未提供解释）",
                ),
            }
        ]

        raw: dict[str, Any] = self.llm.chat_json(messages, temperature=0.2)
        raw_bloom = raw.get("bloom_level", "L2")
        bloom_level: BloomLevel | None = None
        if raw_bloom in ("L1", "L2", "L3", "L4", "L5", "L6"):
            bloom_level = BloomLevel[{"L1": "REMEMBER", "L2": "UNDERSTAND", "L3": "APPLY", "L4": "ANALYZE", "L5": "EVALUATE", "L6": "CREATE"}[raw_bloom]]

        return PerceptionOutput(
            correctness=bool(raw.get("correctness", student_correctness)),
            explanation_quality=float(raw.get("explanation_quality", 0.5)),
            confusion_signals=tuple(raw.get("confusion_signals", [])),
            self_evaluation=float(raw.get("self_evaluation", 0.5)),
            skill_ids=tuple(raw.get("skill_ids", [])),
            bloom_level=bloom_level,
            key_concepts=tuple(raw.get("key_concepts", [])),
        )
