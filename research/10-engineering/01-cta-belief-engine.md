# 01 - CTA 信念状态估计引擎

> **状态**：📋 占位（待 Phase 4.1 填充详细设计）
> **关联**：[deep-research v2.0 §3.3 CTA 设计](../../deep-research/Cognitive-Digital-Twin-Deep-Research.md)

## CTA 核心职责

- 维护学生认知状态的**信念分布**（不是事实判断）
- 基于 BKT/IRT/DKT + LLM rubric 做状态估计
- 输出每个状态变量的 confidence 和 evidence

## 状态空间（9D + Bloom）

- K (Knowledge) - 知识掌握
- P (Procedure) - 程序技能
- S (Strategy) - 策略能力
- C (Confidence) - 认知置信度
- X (External Support) - 外部支架
- BloomProfile - 6 层认知层级
- LearningDNA - 5 维个性化特征
- GrowthTrajectory - 成长轨迹
- BeliefDistribution - 信念分布

## 待填充章节

1. BeliefState 数据结构（分布而非事实）
2. K/P/S/C/X 估计方法（IRT/BKT/DKT + rubric）
3. BloomProfile 估计（6 套独立测评 + 跨层级相关分析）
4. LearningDNA 推断（聚类 + 相似学生迁移）
5. GrowthTrajectory 维护（时间序列 + 预测）
6. 估计精度评估（与人工标注对比）

---

**创建日期**：2026-06-24
**维护者**：Bisen & Claude
