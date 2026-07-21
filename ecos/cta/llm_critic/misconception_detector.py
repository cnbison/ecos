"""LLM Critic Misconception 检测层——MisconceptionDetector.

对应 research/10-engineering/01-cta-belief-engine.md §9.3。

职责：从学生的 explanation_text 检测是否触发了 Misconception 库中的条目。
边界：只做检测，不做修正（修正策略 ID 传给 LCA，由 LCA 选干预）。
温度：0.2（JSON 输出稳定性优先）。

M2 W3 集成点：
  BeliefEngine.update() 在 L1/L2 更新完成后，
  调用 MisconceptionDetector.detect() 获取 C 维度折扣因子 → 更新 state.C.discount_factor。
"""

from __future__ import annotations

import logging
from typing import Any

from ...llm_client import ECOSLLMClient
from ..belief_state import MisconceptionHit
from .schemas import MisconceptionDetectionOutput

logger = logging.getLogger(__name__)

# 注入的 misconception 条目（避免循环导入）
_MISCONCEPTION_LIBRARY_STR: str = """
候选 Misconception 条目：

ID | 名称 | 描述 | 关键 trigger 样例
M1 | 乘法总是变大 | 学生认为被乘数不变，乘数越大积越大 | "5×0.5怎么变小了"
M2 | 分母大→分数大 | 未理解分子也影响分数大小 | "1/8比1/4大吗？"
M3 | 等式性质错误推广到不等式 | 同乘负数不变号 | "两边同除以-2，x>-3"
M4 | 负数不存在 | 不理解数轴对称 | "苹果不能是负的"
M5 | 0是"没有" | 把0简单理解为空 | "原点就是0，没什么特别"
M6 | 圆周率是3.14 | 把π视为近似值而非无理数 | "π是精确值吗？"
M7 | 平方=2倍 | 混淆x²与2x | "x²就是2x吧？"
M8 | 函数必过原点 | 假设f(0)=0对所有函数成立 | "x=0时y一定是0"
M9 | 几何证明=计算 | 不理解证明的逻辑结构 | "证明题就是算出来"
M10 | 概率是"运气" | 不理解概率的频率解释 | "50%概率就意味着必发生一次"
M11 | 移项不变号 | 移项忘记变号 | "x+3=5，x=5+3=8"
M12 | 分数加减直接分母相加 | 不理解通分 | "1/2+1/3=2/5"
M13 | 一元二次方程判别式记错 | 混淆Δ=b²-4ac与b²+4ac | "判别式是b²+4ac吧？"
M14 | 圆面积公式与周长混淆 | 记成2πr（周长）| "圆面积是2πr吧？"
M15 | 三角形内角和死记 | 不理解180°证明 | "记住180度就行了"
M16 | 勾股定理滥用 | 对任意三角形直接用a²+b²=c² | "勾股定理直接用就行"
M17 | 正比例函数象限必在一三 | 未理解k的正负与象限关系 | "正比例函数都在一三象限"
M18 | 反比例函数图像画法错误 | 不理解双曲线两支永不相交 | "两支曲线会连起来吗？"
M19 | 二次函数顶点必是最大值 | 未理解开口方向与极值关系 | "顶点就是最高点"
M20 | 代入消元时符号丢失 | 代入后漏写负号或括号 | "y=x+1，代入后x+(x+1)=3"
M21 | 分式方程增根不检验 | 乘以公分母后产生增根但不检验 | "解完了，不用检验吧？"
M22 | 平均数必在最大最小之间 | 混淆平均数与中位数 | "平均数就是中间那个数吧？"
M23 | 相关=因果 | 混淆相关关系与因果关系 | "这两个数据相关，所以一个导致另一个"
M24 | 绝对值就是去符号 | 不理解绝对值的几何意义 | "绝对值就是把负号去掉"
M25 | 幂运算指数规则混淆 | a^m·a^n=a^{mn}（错）| "a²·a³=a⁶？"
M26 | 平行线角关系用错 | 混淆内错角与同位角 | "内错角相等，这是同位角吧？"
M27 | 因式分解与展开混淆 | (a+b)²=a²+b²漏2ab | "(a+b)²=a²+b²"
M28 | 科学计数法小数点方向记反 | 负指数时移动方向错误 | "10的负二次方往哪移？"
M29 | 菱形面积公式不理解来源 | 记½ac但不知为何对角线垂直时成立 | "菱形面积就是对角线相乘除以2"
M30 | 函数定义域默认全体实数 | 忽略分母不为零等限制 | "y=1/x，x可以是0吗？"
"""


_MISCONCEPTION_PROMPT = """请检查学生的回答是否触发了以下任意一条 misconception。

学生回答：
---
{student_explanation}
---

相关情境（参考）：
{problem}

{candidate_library}

请判断该回答是否触发了上述任意一条 misconception。

JSON 输出格式：
{{
  "misc_id": "M1"（如果命中，返回ID；无命中返回空字符串""），
  "confidence": 0.0到1.0之间（无命中时为0.0），
  "evidence_text": "支持该判断的学生回答原文片段（直接引用，不改写）",
  "correction_strategy": "对应misconception的修正策略（从表中查找）"
}}

注意：
- evidence_text 必须直接引用学生原文，不要改写或概括
- 如果没有明确的 misconception 触发迹象，confidence 设为 0.0，misc_id 设为 ""
- 一条回答可能同时反映多个问题，但请只选置信度最高的那一条
"""


class MisconceptionDetector:
    """LLM Critic Misconception 检测器。

    用法：
        detector = MisconceptionDetector(llm_client)
        result = detector.detect(
            student_explanation="5×0.5怎么变小了？乘法应该越乘越大啊",
            problem="计算 5 × 0.5",
        )
        if result.misc_id:
            discount = 1.0 - result.confidence * 0.3  # C 维度折扣
    """

    def __init__(self, llm_client: ECOSLLMClient) -> None:
        self.llm = llm_client

    def detect(
        self,
        student_explanation: str,
        problem: str = "",
        library_str: str | None = None,
    ) -> MisconceptionDetectionOutput:
        """检测学生解释文本中的 misconception 命中。

        v0.49.3: 若 LLM client 未配置, 返回空检测(misc_id=""), 由 belief.py
          错误隔离兜底。避免 self.llm is None 时 AttributeError 打 stderr。

        Args:
            student_explanation: 学生的解释文本
            problem: 题目描述（可选，提供上下文）
            library_str: 自定义 misconception 库字符串（默认使用数学库，
                        传入其他库内容可覆盖默认行为）

        Returns:
            MisconceptionDetectionOutput
        """
        if self.llm is None:
            logger.warning(
                "misconception_detector.detect: LLM client 未配置, 跳过(返回空检测)"
            )
            return MisconceptionDetectionOutput()

        if not student_explanation or not student_explanation.strip():
            return MisconceptionDetectionOutput()

        messages = [
            {
                "role": "user",
                "content": _MISCONCEPTION_PROMPT.format(
                    student_explanation=student_explanation,
                    problem=problem or "（未提供题目）",
                    candidate_library=library_str or _MISCONCEPTION_LIBRARY_STR,
                ),
            }
        ]

        raw: dict[str, Any] = self.llm.chat_json(messages, temperature=0.2)

        return MisconceptionDetectionOutput(
            misc_id=str(raw.get("misc_id", "")),
            confidence=float(raw.get("confidence", 0.0)),
            evidence_text=str(raw.get("evidence_text", "")),
            correction_strategy=str(raw.get("correction_strategy", "")),
        )

    def detect_with_hits(
        self,
        student_explanation: str,
        problem: str = "",
        trigger_problem_id: str = "",
        library_str: str | None = None,
    ) -> MisconceptionHit | None:
        """检测并返回 MisconceptionHit（供 BeliefEngine.update() 直接使用）。

        Args:
            student_explanation: 学生解释文本
            problem: 题目描述
            trigger_problem_id: 触发题目的 ID（来自 Observation）
            library_str: 自定义 misconception 库字符串

        Returns:
            MisconceptionHit 或 None（无命中时）
        """
        result = self.detect(student_explanation, problem, library_str=library_str)
        if not result.misc_id or result.confidence <= 0.0:
            return None

        return MisconceptionHit(
            misc_id=result.misc_id,
            confidence=result.confidence,
            trigger_problem_id=trigger_problem_id,
            evidence_text=result.evidence_text,
            correction_strategy=result.correction_strategy,
        )
