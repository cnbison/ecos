"""CTA - Cognitive Twin Agent（认知孪生 Agent）.

负责"理解学生"——像认知科学家 + 心理测量学家一样：
- 维护学生认知状态的信念分布（不是事实判断）
- 基于 BKT/IRT/DKT + LLM rubric 做状态估计
- 输出每个状态变量的 confidence 和 evidence

核心状态空间（v0.1.0 占位）：
- K (Knowledge) - 知识掌握
- P (Procedure) - 程序技能
- S (Strategy) - 策略能力
- C (Confidence) - 认知置信度
- X (External Support) - 外部支架
- BloomProfile - 6 层认知层级
- LearningDNA - 5 维个性化特征
- GrowthTrajectory - 成长轨迹

Phase 4+ 实施细节：见 research/10-engineering/01-cta-belief-engine.md
"""

__status__ = "placeholder"
