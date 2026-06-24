# 02 - ECOS 整体架构

> **状态**：📋 占位（待 Phase 4.1 填充详细设计）
> **关联**：[deep-research v2.0 §3 ECOS 完整架构](../../deep-research/Cognitive-Digital-Twin-Deep-Research.md)

## 核心架构（占位）

```
┌──────────────────────────────────────────────────────────┐
│              Bloom Goal Space（目标坐标系）                 │
│  Remember → Understand → Apply → Analyze → Evaluate → Create │
└──────────────────────────────────────────────────────────┘
                            ↕
┌──────────────────────────────────────────────────────────┐
│       Learning Coach Agent (LCA) — Policy Optimizer       │
└──────────────────────────────────────────────────────────┘
                            ↕
┌──────────────────────────────────────────────────────────┐
│     Cognitive Twin Agent (CTA) — State Estimator          │
│     状态：K/P/S/C/X + BloomProfile + LearningDNA + Trajectory │
└──────────────────────────────────────────────────────────┘
                            ↕
                         Student
```

## 待填充章节

1. 双 Agent 详细架构（CTA + LCA + 互校机制）
2. 三空间架构（State + Bloom Goal + Policy）
3. 数据流（采集 → 状态估计 → 干预选择 → 执行 → 评估 → 更新）
4. 状态估计工程实现（IRT/BKT/DKT + LLM rubric）
5. 干预策略工程实现（Bloom → 策略映射 + RL/bandit）
6. 持久化与长期会话管理

---

**创建日期**：2026-06-24
**维护者**：Bisen & Claude
