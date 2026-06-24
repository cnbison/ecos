"""Dual Agent Calibration（双 Agent 互校）.

实现 CTA ⇄ LCA 的互校循环：
- CTA 提出假设 → LCA 设计实验 → 观察结果 → CTA 更新信念 → LCA 重新规划
- 4 个交互模式：常规循环 / 信念质疑 / 策略质疑 / 元反思

对抗 LLM 幻觉的 3 个机制：
1. CTA 维护信念分布而非事实
2. LCA 设计实验而非直接给答案
3. CTA 接收结果后做归因分析

Phase 4+ 实施细节：见 research/10-engineering/04-dual-agent-calibration.md
"""

__status__ = "placeholder"
