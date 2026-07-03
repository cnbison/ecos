"""CTA LLM Critic 模块.

对应 research/10-engineering/01-cta-belief-engine.md §9（LLM Critic 边界）。
M2 W3 范围：严格只做感知层 + 解释层 + Misconception 检测，不做规划/决策/反思。

3 类组件：
  - PerceptionCritic    → 感知层：自然语言 → 结构化（belief_state 更新）
  - ExplanationCritic  → 解释层：统计值 → 自然语言（给学生/教师的诊断报告）
  - MisconceptionDetector → 检测 explanation_text 中的 misconception 命中

温度：0.2（结构化 JSON 输出稳定）
复用：ECOSLLMClient.chat_json()
"""

from .explanation import ExplanationCritic
from .misconception_detector import MisconceptionDetector
from .perception import PerceptionCritic
from .schemas import (
    MisconceptionDetectionOutput,
    PerceptionOutput,
    ExplanationOutput,
)

__all__ = [
    "PerceptionCritic",
    "ExplanationCritic",
    "MisconceptionDetector",
    "PerceptionOutput",
    "ExplanationOutput",
    "MisconceptionDetectionOutput",
]
