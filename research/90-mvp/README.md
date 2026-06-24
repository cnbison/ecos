# 90 - MVP 实施

> **状态**：📋 占位（待 Phase 4.1 填充详细设计）
> **关联**：[deep-research v2.0 §5.2 MVP 设计](../../deep-research/Cognitive-Digital-Twin-Deep-Research.md)

## MVP 范围（推荐）

```
学科：初中数学（二次函数、几何证明、概率初步）
年级：初一、初二
用户：50-100 名学生
时长：4 周
```

## 4 周里程碑

| Week | 任务 | 产出 |
|------|------|------|
| W1 | 数据采集 + CTA 状态估计原型 | BKT 估计 K + LLM rubric 估计 BloomProfile |
| W2 | LCA 干预选择 + Bloom Goal Library | 规则策略 + 数学知识点 × 6 层映射 |
| W3 | 双 Agent 互校循环 + 简单 UI | 端到端：做题 → CTA 估计 → LCA 干预 → 验证 |
| W4 | 实验对比 + 评估报告 | 3 组对照 + 报告 |

## 4 个关键假设验证

| 假设 | 验证方法 | 成功标准 |
|------|---------|---------|
| H1: 5D + BloomProfile 优于单一分数 | BKT vs ECOS 模型对比 | AUC + 0.1，校准误差降低 30% |
| H2: 双 Agent 互校优于单 Agent | 3 组对照 | 满意度 + 20%，进步速度 + 15% |
| H3: Bloom 目标空间有效 | 50 名学生分组 | 有 Bloom 组 analyze/evaluate 提升 + 0.15 |
| H4: CTA/LCA 分工有效 | 双 Agent vs 合并 | 分工组元认知 + 0.2 |

## 待填充章节

1. 详细 Week 1-4 任务分解
2. 数据采集方案（合作学校 / 在线招募）
3. CTA 状态估计工程实现
4. LCA 干预选择工程实现
5. 实验设计与对照组
6. 评估指标与统计方法
7. 风险与缓解

---

**创建日期**：2026-06-24
**维护者**：Bisen & Claude
