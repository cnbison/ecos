"""LCA Rationale 生成器——LLM 表达层（不污染教学法决策).

对应：
  - research/10-engineering/02-lca-policy-engine.md §5 可解释性输出
  - research/00-overview/04-risks.md §A3 LCA 可解释性

设计原则：
  - LLM 仅用于自然语言生成，不参与决策（硬底线 02-lca §0.3）
  - 提供 student / teacher / parent 三种 audience
  - temperature 低（0.3-0.5）保证稳定性
  - 任何 LLM 失败 → 优雅 fallback 到模板字符串
"""

from __future__ import annotations

from typing import Optional

from ...cta.belief_state import BeliefState
from ...llm_client import ECOSLLMClient
from ..intervention import Intervention


# Prompt 模板（02-lca-policy-engine.md §5.2）
PROMPT_TEMPLATES = {
    "student": """你是友好的 AI 学习教练。请向学生解释推荐：

干预类型：{intervention_type}
目标 Bloom 层：{bloom_target}
目标技能：{target_skills}

学生当前状态：
- 知识（K）：{k_mastery:.2f}
- 程序（P）：{p_mastery:.2f}
- 策略（S）：{s_strategy:.2f}
- 置信度（C）：{c_confidence:.2f}
- Bloom 层（dominant）：{bloom_dominant}
- CLT 呈现级别：{clt_level}
- CA 阶段：{ca_stage}

请生成 100 字以内的解释（学生能理解的口语化中文），先共情再说明原因：""",

    "teacher": """你是教学顾问。请向教师解释 LCA 推荐：

干预类型：{intervention_type}
目标 Bloom 层：{bloom_target}
目标技能：{target_skills}
目标修正 misconception：{target_misconceptions}
目标跨越 TC：{target_tcs}

学生状态（CTA 估计）：
- K/P/S/C/X 5D theta：{k_theta:.2f}, {p_theta:.2f}, {s_theta:.2f}, {c_theta:.2f}, {x_theta:.2f}
- BloomProfile 6 层：{bloom_profile}
- K mastery 概率：{k_mastery:.2f}

请生成 200 字以内的解释（教师视角），包含：
1. 为什么推荐这个干预（基于 CTA 状态）
2. 期望的学习效果
3. 教师可观察的学生行为变化""",

    "parent": """你是教育顾问。请向家长解释 LCA 推荐：

干预类型：{intervention_type}
目标技能：{target_skills}
学生当前学习画像（Bloom dominant）：{bloom_dominant}

请生成 150 字以内的解释（家长能理解的口语化中文），包含：
1. 孩子目前的学习状态
2. 这个练习/讲解的目的
3. 家长可以如何支持（避免直接干预）""",
}


def _fallback_template(audience: str, intervention: Intervention, belief_state: BeliefState) -> str:
    """LLM 失败时的模板 fallback."""
    if audience == "student":
        return (
            f"推荐你做 {intervention.quantity} 道 "
            f"{intervention.bloom_target.name} 层的练习。"
            f"目前你的掌握度（{intervention.bloom_target.name}）还有提升空间，"
            f"通过这些针对性练习可以巩固。"
        )
    if audience == "teacher":
        bp = belief_state.bloom_profile
        return (
            f"[模板回退] 干预={intervention.intervention_type.value}, "
            f"Bloom 目标={intervention.bloom_target.name}, "
            f"Kθ={belief_state.K.theta:.2f}, "
            f"Bloom 分布=(R{bp.remember:.2f}/U{bp.understand:.2f}/A{bp.apply:.2f}/"
            f"An{bp.analyze:.2f}/E{bp.evaluate:.2f}/C{bp.create:.2f})"
        )
    # parent
    return (
        f"[模板回退] 孩子需要做 {intervention.quantity} 道练习，"
        f"建议家长以鼓励为主，避免直接指导答案。"
    )


class RationaleGenerator:
    """Rationale 自然语言生成器（LLM 表达层）.

    用法：
        gen = RationaleGenerator(llm_client)  # ECOSLLMClient
        text = gen.generate(intervention, belief_state, audience="student")
    """

    def __init__(
        self,
        llm_client: Optional[ECOSLLMClient] = None,
        default_temperature: float = 0.4,
    ):
        # 允许 None：None 时纯模板 fallback
        self.llm_client = llm_client
        self.default_temperature = default_temperature

    def generate(
        self,
        intervention: Intervention,
        belief_state: BeliefState,
        audience: str = "student",
    ) -> str:
        """生成自然语言 rationale.

        Args:
            intervention: 待解释的干预
            belief_state: CTA 输出
            audience: 受众（student / teacher / parent）

        Returns:
            自然语言理由（100-200 字）

        Note:
            LLM 失败时优雅 fallback 到模板，保证主流程不被阻塞。
        """
        if audience not in PROMPT_TEMPLATES:
            audience = "student"

        # 1. 准备 prompt 内容
        prompt = self._format_prompt(intervention, belief_state, audience)

        # 2. 调用 LLM（如可用）
        if self.llm_client is not None:
            try:
                messages = [{"role": "user", "content": prompt}]
                # strip_think=True：剥离 思考块；rationale 应只保留最终自然语言
                text = self.llm_client.chat(
                    messages=messages,
                    temperature=self.default_temperature,
                    max_tokens=512,
                    strip_think=True,
                )
                text = text.strip()
                if text:
                    return text
            except Exception:
                # LLM 失败 → fallback
                pass
        # 3. Fallback 模板
        return _fallback_template(audience, intervention, belief_state)

    # ---------------------------------------------------------------

    def _format_prompt(
        self,
        intervention: Intervention,
        belief_state: BeliefState,
        audience: str,
    ) -> str:
        bp = belief_state.bloom_profile
        template = PROMPT_TEMPLATES[audience]
        bloom_profile_str = (
            f"R={bp.remember:.2f} U={bp.understand:.2f} A={bp.apply:.2f} "
            f"An={bp.analyze:.2f} E={bp.evaluate:.2f} C={bp.create:.2f}"
        )
        return template.format(
            intervention_type=intervention.intervention_type.value,
            bloom_target=intervention.bloom_target.name,
            bloom_dominant=bp.dominant_layer.name,
            bloom_profile=bloom_profile_str,
            target_skills=", ".join(intervention.target_skills) or "（未指定）",
            target_misconceptions=", ".join(intervention.target_misconceptions) or "（无）",
            target_tcs=", ".join(intervention.target_tcs) or "（无）",
            k_mastery=belief_state.K.mastery_prob,
            p_mastery=belief_state.P.mastery_prob,
            s_strategy=belief_state.S.mastery_prob,
            c_confidence=belief_state.C.mastery_prob,
            x_theta=belief_state.X.theta,
            k_theta=belief_state.K.theta,
            p_theta=belief_state.P.theta,
            s_theta=belief_state.S.theta,
            c_theta=belief_state.C.theta,
            clt_level=intervention.clt_level.name,
            ca_stage=intervention.ca_stage.name,
        )


__all__ = ["RationaleGenerator", "PROMPT_TEMPLATES"]
