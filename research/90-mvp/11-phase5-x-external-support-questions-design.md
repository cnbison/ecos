# Phase 5 X-External-Support 主导题设计 v0.54.3

> **日期**：2026-07-23
> **触发**：Bisen 2026-07-23 22:52 "继续 v0.54.2+（X-external-support 主导题）"
> **状态**：🟢 v0.54.3 当前（X-external-support 5 道样题 + 端到端测试）
> **重要性**：🔴 P0 — 5D 核心 X 维度真评估（领域无关）
> **关联**：
> - [research/00-overview/08-cx-dimension-semantic-decision.md v1.1 §11.8](../00-overview/08-cx-dimension-semantic-decision.md)（Bisen 决策：方案 D + X-external-support 主导题）
> - [research/90-mvp/10-phase5-c-confidence-questions-design.md](../90-mvp/10-phase5-c-confidence-questions-design.md)（v0.54.2 C-confidence 主导题设计）
> - [research/deep-research/Cognitive-Digital-Twin-Deep-Research.md v2.0 §3.3](../deep-research/Cognitive-Digital-Twin-Deep-Research.md)（X = 工具调用/笔记质量/Agent 记忆）

---

## 0. 概述

### 0.1 一句话目标

**X 维度从占位值 → 真评估**：5 道 X-external-support 主导题（领域无关）让 ECOS 5D 评估完整性保持 **5/5**（C-confidence 已达 5/5，X-external-support 巩固）。

### 0.2 范围

| 范围内（v0.54.3）| 范围外（v0.54.4+）|
|---|---|
| ✅ 5 道 X-external-support 主导题样题设计（PC-X01~PC-X05）| 📋 扩 20+ 道 X 主导题（v0.54.4）|
| ✅ 端到端测试（lbc001 5 题 X-external-support）| 📋 pytest 单元测试（v0.55.0）|
| ✅ 5D 完整性保持 5/5 | 📋 跨学科迁移验证（数学/语文/英语）|

### 0.3 5D 完整性目标

| 维度 | 含义 | 领域无关 | v0.54.2 (C-confidence) | v0.54.3 (X-external-support) |
|------|------|----------|------------------------|-------------------------------|
| K | Knowledge 知识 | ✅ | ✅ | ✅ |
| P | Procedure 程序技能 | ✅ | ✅ | ✅ |
| S | Strategy 策略 | ✅ | ✅ | ✅ |
| **C** | **Confidence 自我评估/元认知** | ✅ | ✅ **真评估** | ✅ |
| **X** | **External Support 工具/笔记/记忆** | ✅ | ❌ 占位 | ✅ **真评估** |
| **5D 完整性** | | | **5/5** | **5/5（巩固）** |

### 0.4 关键设计原则（跟 v0.54.2 C-confidence 一致）

1. **领域无关**：5 道样题跨数学/语文/英语/物理/化学都适用
2. **权威定义**：X = External Support（工具调用 / 笔记 / Agent 记忆）
3. **跟编程领域应用层扩展区分**：编程工具（debugger/print/IDE）是 X 维度的"应用层实例"，不污染 5D 核心
4. **字段解耦**：5D 核心 X 维度（领域无关）+ 编程工具使用偏好（领域特定，独立字段）

---

## 1. X-external-support 5 道样题设计

### 1.1 PX-X01 (L3 工具选择)

**题目**：
```python
# 遇到难题你用什么工具？
# A. 不查工具
# B. 查字典/计算器/实验仪器
# C. 查笔记
# D. 查 AI 助手
# E. 综合（B + C + D）
```

**正确答案**：E（综合）— 多工具组合是 X 维度最佳策略

**Q 矩阵**：
- `topic`: cross_subject
- `skill_name`: 工具选择
- `bloom_goal_id`: cross_subject-L3
- `a_specialized`: [0.2, 0.2, 0.2, 0.2, **1.0**]  # X 主导
- `mirt_params`: {difficulty: 0.0, discrimination: 1.0, guessing: 0.0}
- `misconceptions`: ["M-illinois-tool-avoidance"]  # 工具逃避
- `x_dimension_type`: tool_selection
- `domain_agnostic`: True

**领域无关验证**：
- 数学：计算器/几何工具/草稿纸
- 语文：字典/语法书/参考书
- 英语：翻译工具/语法书/电子词典
- 物理：实验仪器/计算器/参考书
- 化学：实验工具/化学手册/计算器

**partial credit 评分**：
- 0.0：选 A (不查工具) — 工具逃避
- 0.3：选 D (单 AI 助手) — 过度依赖单一工具
- 0.6：选 B 或 C (单类工具) — 单一策略
- 1.0：选 E (综合工具) — X 维度最佳

### 1.2 PX-X02 (L4 笔记质量)

**题目**：
```python
# 好的笔记应包含什么？
# A. 答案
# B. 答案 + 思路
# C. 答案 + 思路 + 易错点
# D. 全部（答案 + 思路 + 易错点 + 反思 + 跨学科联系）
```

**正确答案**：D（全部）— 完整笔记是 X 维度高质量标志

**Q 矩阵**：
- `topic`: cross_subject
- `skill_name`: 笔记质量
- `bloom_goal_id`: cross_subject-L4
- `a_specialized`: [0.2, 0.2, 0.4, 0.2, **1.0**]  # X + S（笔记质量涉及策略）
- `mirt_params`: {difficulty: 0.0, discrimination: 1.0, guessing: 0.0}
- `misconceptions`: []
- `x_dimension_type`: note_quality
- `domain_agnostic`: True

**领域无关验证**：跨学科笔记都应包含答案/思路/易错点/反思

**partial credit 评分**：
- 0.0：选 A (仅答案)
- 0.3：选 B (答案+思路)
- 0.6：选 C (答案+思路+易错点)
- 1.0：选 D (全部) — X 维度高质量笔记

### 1.3 PX-X03 (L5 记忆使用)

**题目**：
```python
# 你如何决定"是否查之前类似题"？
# A. 每次都查 (过度依赖)
# B. 偶尔查
# C. 不查 (过度自信)
# D. 综合（偶尔查 + 记在脑里 + 标注重点）
```

**正确答案**：D（综合）— 平衡记忆使用是 X 维度元认知

**Q 矩阵**：
- `topic`: cross_subject
- `skill_name`: 记忆使用策略
- `bloom_goal_id`: cross_subject-L5
- `a_specialized`: [0.2, 0.2, 0.2, 0.2, **1.1**]  # X 主导
- `mirt_params`: {difficulty: 0.2, discrimination: 1.0, guessing: 0.0}
- `misconceptions`: ["M-illinois-overconfidence", "M-illinois-overdependence"]
- `x_dimension_type`: memory_use_strategy
- `domain_agnostic`: True

**领域无关验证**：跨学科都适用"查/记/标注"策略

**partial credit 评分**：
- 0.0：选 C (不查) — 过度自信
- 0.3：选 A (每次都查) — 过度依赖
- 0.6：选 B (偶尔查) — 单策略
- 1.0：选 D (综合策略) — X 维度平衡

### 1.4 PX-X04 (L5 支架依赖)

**题目**：
```python
# 遇到新概念你如何应对？
# A. 等老师讲 (被动)
# B. 看 worked example (高依赖)
# C. 直接尝试 (低依赖)
# D. 综合 (worked example + 直接尝试 + 讨论)
```

**正确答案**：D（综合）— 平衡支架依赖是 X 维度元认知

**Q 矩阵**：
- `topic`: cross_subject
- `skill_name`: 支架依赖度
- `bloom_goal_id`: cross_subject-L5
- `a_specialized`: [0.2, 0.2, 0.3, 0.3, **1.0**]  # X 主导
- `mirt_params`: {difficulty: 0.2, discrimination: 1.0, guessing: 0.0}
- `misconceptions`: ["M-illinois-scaffolding-overdependence"]
- `x_dimension_type`: scaffolding_dependency
- `domain_agnostic`: True

**领域无关验证**：跨学科"worked example + 尝试 + 讨论"都适用

**partial credit 评分**：
- 0.0：选 A (等老师讲) — 完全依赖
- 0.3：选 C (直接尝试) — 不借力
- 0.6：选 B (worked example) — 单一支架
- 1.0：选 D (综合) — X 维度平衡

### 1.5 PX-X05 (L6 综合 External Support)

**题目**：
```python
# 综合 External Support 评估：
# 1. 工具使用频率（每天用几次字典/计算器/AI？）
# 2. 笔记习惯（每次学习是否做笔记？质量如何？）
# 3. 记忆使用（如何决定查/记脑里？）
# 4. 求助策略（独立思考 + 查资料 + 问老师？）
# 请综合评估你的 External Support 使用水平 (0-10 分).
```

**正确答案**：综合 4 维度评估

**Q 矩阵**：
- `topic`: cross_subject
- `skill_name`: 综合 External Support
- `bloom_goal_id`: cross_subject-L6
- `a_specialized`: [0.2, 0.2, 0.3, 0.3, **1.1**]  # X 主导
- `mirt_params`: {difficulty: 0.3, discrimination: 1.0, guessing: 0.0}
- `misconceptions`: []
- `x_dimension_type`: external_support_synthesis
- `domain_agnostic`: True

**partial credit 评分**：综合 4 维度评估（0-4 低分, 5-7 中分, 8-10 高分）

---

## 2. 领域无关性验证

| 题目 | 数学 | 语文 | 英语 | 物理 | 化学 |
|------|------|------|------|------|------|
| PX-X01 工具选择 | ✅ | ✅ | ✅ | ✅ | ✅ |
| PX-X02 笔记质量 | ✅ | ✅ | ✅ | ✅ | ✅ |
| PX-X03 记忆使用 | ✅ | ✅ | ✅ | ✅ | ✅ |
| PX-X04 支架依赖 | ✅ | ✅ | ✅ | ✅ | ✅ |
| PX-X05 综合 | ✅ | ✅ | ✅ | ✅ | ✅ |

**全部领域无关**——5 道样题跨数学/语文/英语/物理/化学都适用。

---

## 3. 5D 核心 X 维度 vs 编程领域工具使用

| 维度 | X-external-support 主导题 | 编程领域工具使用 |
|------|------------------------|------------------|
| **含义** | 工具/笔记/记忆（领域无关）| 编程工具（debugger/IDE/print）|
| **5D 核心** | ✅ X 维度 | ❌ 编程领域应用层 |
| **字段** | `state.X.theta` MIRT 评估 | `programming_tool_score` 独立字段 |
| **题库** | 5 道样题 → 20+ 道扩 | 编程工具相关题（PB-C 包含部分）|
| **领域** | 跨学科 | 编程领域 |

**双层架构**：
- **5D 核心**：X 维度 = X-external-support 主导题评估
- **编程扩展**：`programming_tool_score` = 编程工具使用评估

---

## 4. 字段解耦设计

### 4.1 信念引擎扩展（5D 核心 X 维度）

```python
class StudentState:
    # 5D 核心（领域无关）
    K: KnowledgeState        # 知识掌握
    P: ProcedureState        # 程序技能
    S: StrategyState         # 策略能力
    C: ConfidenceState       # 认知置信度（self_evaluation/求助/检查/misconception）
    X: ExternalSupportState  # 外部支架（工具/笔记/记忆/Agent）

    # 应用层扩展（领域特定）
    programming_debug_score: Optional[float] = None  # 编程调试能力（PB-C 评估）
    programming_tool_score: Optional[float] = None    # 编程工具使用（v0.54.2+ 扩展）
    # 跨学科时这些字段不应用
```

### 4.2 5D 完整性 vs 编程扩展

| 评估层 | 字段 | 5D 完整性 | 跨学科 |
|--------|------|----------|--------|
| K | `state.K.theta` | ✅ | ✅ |
| P | `state.P.theta` | ✅ | ✅ |
| S | `state.S.theta` | ✅ | ✅ |
| C | `state.C.theta` | ✅ | ✅ |
| **X** | **`state.X.theta`** | ✅ | ✅ |
| **(扩展) programming_debug_score** | 独立字段 | n/a | ❌ |
| **(扩展) programming_tool_score** | 独立字段 | n/a | ❌ |

**5D 评估完整性 = 5/5（K/P/S/C/X 全部真评估）**

---

## 5. 实施步骤

### 5.1 v0.54.3-a (当前): 设计文档 ✅
- 文件: research/90-mvp/11-phase5-x-external-support-questions-design.md
- 5 道 PC-X 样题设计 + 领域无关性验证 + 字段解耦

### 5.2 v0.54.3-b: Q 矩阵 JSON 追加 5 道 PC-X
- 追加 5 道 PC-X 到 data/python_basics_q_matrix.json
- 字段: `domain_agnostic: True` + `x_dimension_type: tool_selection / note_quality / memory_use / scaffolding_dependency / external_support_synthesis`

### 5.3 v0.54.3-c: 端到端测试脚本
- 模拟 lbc001 答 5 道 PC-X
- 模拟 AI 评分（基于 partial_credit_rubric）
- 验证:
  - 5D X 维度真评估（从占位 → 真实值）
  - 5D 完整性保持 5/5
  - 编程扩展（programming_debug_score）独立评估

---

## 6. 验收标准

### 6.1 lbc001 端到端测试（v0.54.3-c）

**步骤**：
1. lbc001 答 5 道 PC-X（PX-X01~PX-X05）
2. AI 模拟评分（partial credit）
3. 5D X 维度 θ 变化（脱离 0.2496 占位值）
4. 5D X 维度 confidence 提升

**通过条件**：
- ✅ 5 题全部提交成功 + DB 持久化
- ✅ 5D X 维度 θ 变化（不再占位）
- ✅ 5D 完整性保持 5/5

### 6.2 编程领域扩展独立

- 之前 5 道 PB-C 答题数据保留为 `programming_debug_score`
- 5D X 维度真评估（领域无关）
- 编程扩展独立（领域特定）

### 6.3 防御性自检

- silent failure：0 新增
- 版本号：v0.54.3 同步
- Q 矩阵 JSON schema 校验
- 文档一致性（5D 维度定义跨文档 = deep-research v2.0 / 02-arch / 01-cta）

---

## 7. 风险与回退

### 7.1 风险

| # | 风险 | 严重度 | 缓解 |
|---|------|--------|------|
| 1 | X-external-support 题型"太软"（工具/笔记/记忆难精准评估）| 中 | LLM 评判 + 多次评估 |
| 2 | 5 道样题量不够，X 维度评估仍波动 | 中 | v0.54.4 扩 20+ 道 |
| 3 | 跟 v0.54.2 C-confidence 测试混淆 | 低 | problem_id 前缀 PC-X vs PC-C |

### 7.2 回退方案

- v0.54.3 失败：保留 v0.54.2 C-confidence 评估，重新设计 5 道 PC-X
- X 维度题型不准：v0.54.4 重新设计

---

## 8. 与 v0.54.2 C-confidence 主导题对比

| 维度 | C-confidence 主导题（v0.54.2）| X-external-support 主导题（v0.54.3）|
|------|------------------------------|-----------------------------------|
| **含义** | self_evaluation / help_seeking / self_checking / misconception | tool_selection / note_quality / memory_use / scaffolding_dependency |
| **5D 核心** | ✅ C 维度 | ✅ X 维度 |
| **题库** | 5 道 PC-C (PC-C01~PC-C05) | 5 道 PC-X (PX-X01~PX-X05) |
| **字段** | `state.C.theta` | `state.X.theta` |
| **领域** | 跨学科 | 跨学科 |
| **状态** | ✅ v0.54.2 落地 | 📋 v0.54.3 当前 |

**5D 完整性进展**：
- v0.54.2: C 维度真评估 (5/5)
- v0.54.3: X 维度真评估 (5/5 巩固)

---

## 9. 决策记录

**Bisen 2026-07-23 22:52 决策**：
- ✅ 继续 v0.54.2+（X-external-support 主导题）
- ✅ 跟 C-confidence 主导题同模式（5 道样题 + 端到端测试）

**Mavis 2026-07-23 22:54 反思**：
- 关键设计：X 维度 = External Support（工具/笔记/记忆/Agent），领域无关
- 5 道 PC-X 样题：tool_selection / note_quality / memory_use / scaffolding_dependency / external_support_synthesis
- 跟 v0.54.2 C-confidence 主导题同模式 + 同字段（domain_agnostic + x_dimension_type）
- 5D 完整性保持 5/5（X 维度从占位 → 真评估）
- 编程领域工具使用（debugger/IDE/print）作为应用层扩展（programming_tool_score，独立字段）

---

## 10. 关联文档

- [research/00-overview/08-cx-dimension-semantic-decision.md v1.1 §11.8](../00-overview/08-cx-dimension-semantic-decision.md)（Bisen 决策：方案 D + X-external-support 主导题）
- [research/90-mvp/10-phase5-c-confidence-questions-design.md](../90-mvp/10-phase5-c-confidence-questions-design.md)（v0.54.2 C-confidence 主导题设计）
- [research/deep-research/Cognitive-Digital-Twin-Deep-Research.md v2.0 §3.3](../deep-research/Cognitive-Digital-Twin-Deep-Research.md)（X = 工具调用/笔记/Agent 记忆）
- [research/00-overview/02-architecture.md §2.1 State Space](../00-overview/02-architecture.md)
- [research/30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md §1.2 CTA 对接](../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md)
- [ecos/cta/belief_state.py](../../ecos/cta/belief_state.py) DimensionId 定义

---

**创建日期**：2026-07-23
**维护者**：Bisen & Mavis
**下次更新**：v0.54.3-c 端到端测试后
