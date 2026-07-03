"""L3 CLT 4 级题目模板（教学法决策树的最后一层）.

对应：
  - research/10-engineering/02-lca-policy-engine.md §3.2 CLTTemplate
  - research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md §1.3

设计：
  - 4 套模板 × 5 类干预类型 = 最多 20 套呈现
  - MVP 实现核心 5 套（NOVICE+EXPLANATORY, DEVELOPING+EXPLANATORY, DEVELOPING+PRACTICE, PROFICIENT+PRACTICE, EXPERT+PRACTICE）
  - 其余组合 fallback 到 default 模板
"""

from __future__ import annotations

from typing import Optional

from ...intervention import CLTLevel, InterventionType


class CLTTemplate:
    """CLT 4 级题目模板——生成具体呈现参数.

    用法：
        template = CLTTemplate(level=CLTLevel.NOVICE, intervention_type=InterventionType.EXPLANATORY)
        presentation = template.generate(problem={...})
    """

    def __init__(self, level: CLTLevel, intervention_type: InterventionType):
        self.level = level
        self.intervention_type = intervention_type

    def generate(self, problem: dict) -> dict:
        """生成呈现参数.

        Returns:
            {
              show_worked_example: bool,
              worked_example_steps: str | None,  # 'complete' / 'partial' / None
              fill_in_blanks: list | None,
              show_explanation: bool,
              explanation_length: str | None,    # 'detailed' / 'moderate' / 'brief' / None
              scaffolding: float,                # [0, 1]
              hints_available: int,
              feedback_timing: str,              # 'immediate' / 'delayed'
              feedback_delay_sec: int | None,
            }
        """
        lvl = self.level
        itype = self.intervention_type

        # 核心 5 套（文档定义）
        if lvl == CLTLevel.NOVICE and itype == InterventionType.EXPLANATORY:
            return {
                "show_worked_example": True,
                "worked_example_steps": "complete",
                "show_explanation": True,
                "explanation_length": "detailed",
                "scaffolding": 0.9,
                "hints_available": 3,
                "feedback_timing": "immediate",
                "feedback_delay_sec": 0,
                "fill_in_blanks": None,
            }

        if lvl == CLTLevel.DEVELOPING and itype == InterventionType.EXPLANATORY:
            return {
                "show_worked_example": True,
                "worked_example_steps": "partial",
                "fill_in_blanks": ["step_2", "step_4"],
                "show_explanation": True,
                "explanation_length": "moderate",
                "scaffolding": 0.6,
                "hints_available": 2,
                "feedback_timing": "immediate",
                "feedback_delay_sec": 0,
            }

        if (
            lvl in (CLTLevel.DEVELOPING, CLTLevel.PROFICIENT)
            and itype == InterventionType.PRACTICE
        ):
            return {
                "show_worked_example": False,
                "scaffolding": 0.4 if lvl == CLTLevel.DEVELOPING else 0.3,
                "hints_available": 2 if lvl == CLTLevel.DEVELOPING else 1,
                "feedback_timing": "immediate",
                "feedback_delay_sec": 0,
                "worked_example_steps": None,
                "fill_in_blanks": None,
                "explanation_length": None,
            }

        if lvl == CLTLevel.EXPERT:
            # 专家：独立解题 + 延迟反馈（最大化 retrieval practice）
            return {
                "show_worked_example": False,
                "scaffolding": 0.1,
                "hints_available": 0,
                "feedback_timing": "delayed",
                "feedback_delay_sec": 300,  # 5 分钟
                "worked_example_steps": None,
                "fill_in_blanks": None,
                "explanation_length": None,
            }

        # 默认 fallback（其他组合）
        return self._default_template()

    def _default_template(self) -> dict:
        """默认模板——按 level 选基础呈现."""
        lvl = self.level
        if lvl == CLTLevel.NOVICE:
            scaffolding, hints = 0.8, 3
        elif lvl == CLTLevel.DEVELOPING:
            scaffolding, hints = 0.5, 2
        elif lvl == CLTLevel.PROFICIENT:
            scaffolding, hints = 0.3, 1
        else:  # EXPERT
            scaffolding, hints = 0.1, 0
        return {
            "show_worked_example": lvl.value <= CLTLevel.DEVELOPING.value,
            "worked_example_steps": "complete" if lvl == CLTLevel.NOVICE else None,
            "fill_in_blanks": None,
            "show_explanation": lvl.value <= CLTLevel.DEVELOPING.value,
            "explanation_length": "moderate" if lvl.value <= CLTLevel.DEVELOPING.value else None,
            "scaffolding": scaffolding,
            "hints_available": hints,
            "feedback_timing": (
                "immediate" if lvl != CLTLevel.EXPERT else "delayed"
            ),
            "feedback_delay_sec": 0 if lvl != CLTLevel.EXPERT else 300,
        }


__all__ = ["CLTTemplate"]
