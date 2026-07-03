"""LLM Critic 解释层——ExplanationCritic.

对应 research/10-engineering/01-cta-belief-engine.md §9.2。

职责：把 CTA 的统计值（5D θ、BloomProfile、TC 状态）转换为自然语言诊断报告。
边界：只做解释生成，不做决策（干预选择是 LCA 的职责）。
温度：0.3（适度创造性，但不离谱）。

M2 W3 集成点：
  BeliefEngine.update() 完成后，外部调用方可调用 ExplanationCritic.explain()
  生成面向学生/教师/家长的诊断报告（BeliefEngine 不直接持有此组件，
  由外部 orchestrator 或 API 层持有）。
"""

from __future__ import annotations

from typing import Any

from ...llm_client import ECOSLLMClient
from ..belief_state import BeliefState


# ─── Prompt 模板 ─────────────────────────────────────────────────

_EXPLANATION_PROMPTS = {
    "student": """你是一位友好的学习教练。基于以下学生状态，用简洁易懂的语言（200字以内）生成诊断报告。

5D 状态：
- K（知识掌握）：{k_mastery:.2f}（0=完全不会，1=完全掌握）
- P（程序技能）：{p_mastery:.2f}
- S（策略能力）：{s_mastery:.2f}
- C（认知置信度）：{c_mastery:.2f}
- X（外部支架）：{x_mastery:.2f}

BloomProfile（各层掌握概率）：
{bloom_profile}

当前目标：{bloom_target}

请生成面向学生的诊断报告，包含：
1. 你现在最擅长的一个地方
2. 最需要加强的一个地方
3. 下一步建议（具体可操作）

语言风格：鼓励性、不打击、不使用专业术语。
""",
    "teacher": """你是一位数学教研员。基于以下学生状态，生成教师诊断报告（200字以内）。

学生ID：{student_id}
5D 状态：
- K（知识）：θ={k_mastery:.2f}，掌握概率={k_prob:.0%}
- P（程序）：θ={p_mastery:.2f}，掌握概率={p_prob:.0%}
- S（策略）：θ={s_mastery:.2f}，掌握概率={s_prob:.0%}
- C（置信度）：θ={c_mastery:.2f}，掌握概率={c_prob:.0%}
- X（支架）：θ={x_mastery:.2f}

BloomProfile（Dominant={dominant}，整体置信度={bloom_conf:.0%}）：
{bloom_profile}

TC 状态：{tc_summary}

推荐干预方向：{recommended_direction}

请生成教师诊断报告，包含：
1. 学生认知状态的总体判断
2. 需要关注的异常信号（如伪置信、C 维度异常）
3. 干预建议（简要）
""",
    "parent": """你是一位家庭教育顾问。基于以下学生状态，生成家长可读的诊断报告（200字以内）。

学生5D状态（0-1，越高越好）：
- 知识基础：{k_prob:.0%}
- 解题技能：{p_prob:.0%}
- 学习策略：{s_prob:.0%}
- 学习信心：{c_prob:.0%}

当前认知层级（Bloom）：{dominant}（自信心{bloom_conf:.0%}）

建议：
1. 如何在家里帮助孩子（具体做法，1-2条）
2. 需要注意的信号（如果有）
3. 鼓励孩子的话（简短）
""",
}


class ExplanationCritic:
    """LLM Critic 解释层——生成面向不同受众的诊断报告。

    用法：
        critic = ExplanationCritic(llm_client)
        report = critic.explain(state, audience="student")
    """

    def __init__(self, llm_client: ECOSLLMClient) -> None:
        self.llm = llm_client

    def explain(self, state: BeliefState, audience: str = "student") -> str:
        """生成诊断报告。

        Args:
            state: 当前 BeliefState（来自 BeliefEngine）
            audience: 'student' / 'teacher' / 'parent'

        Returns:
            自然语言诊断报告字符串
        """
        template = _EXPLANATION_PROMPTS.get(audience, _EXPLANATION_PROMPTS["student"])

        # 构建 bloom_profile 文本
        bp = state.bloom_profile
        bloom_lines = [
            f"  L1 Remember: {bp.remember:.0%}",
            f"  L2 Understand: {bp.understand:.0%}",
            f"  L3 Apply: {bp.apply:.0%}",
            f"  L4 Analyze: {bp.analyze:.0%}",
        ]
        bloom_profile_text = "\n".join(bloom_lines)

        # TC 状态摘要
        if isinstance(state.C, type(state.C)) and hasattr(state.C, "tc_states"):
            tc_items = [
                f"{tc_id}: {tc.status} ({tc.progress:.0%})"
                for tc_id, tc in state.C.tc_states.items()
            ]
            tc_summary = "; ".join(tc_items) if tc_items else "暂无 TC 数据"
        else:
            tc_summary = "暂无 TC 数据"

        # 推荐干预方向（简化：基于最弱维度生成一句话）
        dim_strengths = {d: getattr(state, d).mastery_prob for d in ["K", "P", "S", "C", "X"]}
        weakest = min(dim_strengths, key=dim_strengths.get)  # type: ignore
        recommended = {
            "K": "建议加强概念理解（K 维度偏低）",
            "P": "建议增加变式练习（程序技能需强化）",
            "S": "建议学习元认知策略（策略维度偏弱）",
            "C": "建议通过成功体验重建信心（置信度偏低）",
            "X": "建议提供更多外部支架支持",
        }.get(weakest, "建议与教师讨论学习策略")

        # 格式化模板
        k_prob = state.K.mastery_prob
        p_prob = state.P.mastery_prob
        s_prob = state.S.mastery_prob
        c_prob = state.C.mastery_prob
        x_prob = state.X.mastery_prob

        content = template.format(
            student_id=state.student_id,
            k_mastery=state.K.theta,
            p_mastery=state.P.theta,
            s_mastery=state.S.theta,
            c_mastery=state.C.theta,
            x_mastery=state.X.theta,
            k_prob=k_prob,
            p_prob=p_prob,
            s_prob=s_prob,
            c_prob=c_prob,
            x_prob=x_prob,
            bloom_profile=bloom_profile_text,
            bloom_conf=state.bloom_profile.confidence,
            dominant=bp.dominant_layer.name,
            bloom_target=f"L{bp.dominant_layer.value + 1}" if bp.dominant_layer.value < 4 else "L4（目标已达成）",
            tc_summary=tc_summary,
            recommended_direction=recommended,
        )

        messages = [{"role": "user", "content": content}]
        return self.llm.chat(messages, temperature=0.3, strip_think=True)
