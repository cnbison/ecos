# Phase 5 C-Confidence 主导题设计 v0.54.1-f

> **日期**：2026-07-23
> **触发**：Bisen 2026-07-23 22:38 决策 — 方案 D + D-2 保留 PB-C 为编程扩展
> **状态**：🟢 v0.54.1-f 当前（C-confidence 5 道样题）
> **重要性**：🔴 P0 架构级 — 5D 核心 C 维度真评估（领域无关）
> **关联**：
> - [research/00-overview/08-cx-dimension-semantic-decision.md v1.1 §11.5](../00-overview/08-cx-dimension-semantic-decision.md)（Bisen 决策：方案 D）
> - [research/90-mvp/09-phase5-c-dimension-questions-expanded.md](../90-mvp/09-phase5-c-dimension-questions-expanded.md)（v0.54.1-b 编程领域 PB-C 20 道，保留为编程扩展）
> - [discussions/2026-07-23-C主导题让C维度真实化发现+缺口分析.md](../../discussions/2026-07-23-C主导题让C维度真实化发现+缺口分析.md)
> - [research/deep-research/Cognitive-Digital-Twin-Deep-Research.md v2.0 §3.3](../deep-research/Cognitive-Digital-Twin-Deep-Research.md)（权威定义）

---

## 0. 概述

### 0.1 一句话目标

**C 维度从占位值 → 真评估**：5 道 C-confidence 主导题（领域无关）让 ECOS 5D 评估完整性从 4/5 → **5/5**。

### 0.2 范围

| 范围内（v0.54.1-f）| 范围外（v0.54.1-g）|
|---|---|
| ✅ 5 道 C-confidence 主导题样题设计（PC-C01~PC-C05）| 📋 扩 20+ 道 C-confidence 主导题（v0.54.1-g）|
| ✅ 字段解耦：`programming_debug_score` 独立于 5D 核心 | 📋 X-external-support 主导题（v0.54.2）|
| ✅ 端到端测试（lbc001 5 题 C-confidence） | 📋 pytest 单元测试（v0.55.0）|

### 0.3 5D 完整性目标

| 维度 | 含义 | 领域无关 | 改造前 | v0.54.1-f 后 |
|------|------|----------|--------|--------------|
| K | Knowledge 知识 | ✅ | ✅ | ✅ |
| P | Procedure 程序技能 | ✅ | ✅ | ✅ |
| S | Strategy 策略 | ✅ | ✅ | ✅ |
| **C** | **Confidence 自我评估/元认知** | ✅ | ❌ 占位 | ✅ **真评估** |
| **X** | **External Support 工具/笔记/记忆** | ✅ | ❌ 占位 | 📋 v0.54.2 |
| **5D 完整性** | | | **3/5** | **5/5** ✅ |
| (扩展) `programming_debug_score` | 编程调试 | ❌ 编程特定 | ✅ 评估 | ✅ 保留 20 道 PB-C |

### 0.4 关键设计原则

1. **领域无关**：5 道样题跨数学/语文/英语/物理/化学都适用
2. **权威定义**：C = Confidence（self_evaluation / 求助 / 检查 / misconception）
3. **双层架构**：5D 核心（领域无关）+ 应用层扩展（编程领域）
4. **字段解耦**：`programming_debug_score` 独立于 5D C 维度

---

## 1. C-confidence 5 道样题设计

### 1.1 PC-C01 (L3 自我评估)

**题目**：
```python
# 这道题你能答对的可能性有多大？
# A. 90% (非常确定)
# B. 70% (比较确定)
# C. 50% (一半一半)
# D. 30% (不太确定)
# E. 10% (完全不会)
```

**正确答案**：基于 lbc001 实际 K/P 维度评估（L3 题目，K=0.69, P=1.23），答对可能性约 70-80%，选 B

**Q 矩阵**：
- `topic`: cross_subject 跨学科
- `bloom_layer_observed`: L3 (Apply)
- `a_specialized`: [0.2, 0.2, 0.3, **1.1**, 0.2]  # C 主导，K/P/S/X 权重低
- `mirt_params`: {difficulty: 0.0, discrimination: 1.0, guessing: 0.0}
- `misconceptions`: []
- `c_dimension_type`: self_evaluation
- `domain_agnostic`: True  # 跨学科通用

**partial credit 评分**：
- 0.0：选 E (完全不会) — 自我评估严重不准
- 0.3：选 D (30% 不太确定) — 低估
- 0.6：选 C (50% 一半一半) — 模糊
- 1.0：选 B (70% 比较确定) — 准确自我评估

### 1.2 PC-C02 (L4 求助决策)

**题目**：
```python
# 遇到难题你打算怎么办？
# A. 直接放弃
# B. 猜一个答案
# C. 看笔记/教材
# D. 问老师/同学
# E. 独立思考 + 查资料
```

**正确答案**：E (独立思考 + 查资料) — 元认知最优策略

**Q 矩阵**：
- `topic`: cross_subject
- `bloom_layer_observed`: L4 (Analyze)
- `a_specialized`: [0.2, 0.2, 0.3, **1.2**, 0.2]
- `mirt_params`: {difficulty: 0.0, discrimination: 1.0, guessing: 0.0}
- `misconceptions`: ["M-illinois-confidence-avoid-help"]  # 求助逃避
- `c_dimension_type`: help_seeking_strategy
- `domain_agnostic`: True

**partial credit 评分**：
- 0.0：选 A (直接放弃)
- 0.3：选 B (猜答案) — 元认知差
- 0.6：选 C/D (单策略) — 单一求助
- 1.0：选 E (综合策略) — 元认知优

### 1.3 PC-C03 (L5 检查行为)

**题目**：
```python
# 答完代码后，你会检查吗？
# A. 不会检查
# B. 简单看一遍
# C. 跑几个测试用例
# D. 完整边界测试 + 异常处理
```

**正确答案**：C/D（检查行为）— 元认知行为

**Q 矩阵**：
- `topic`: cross_subject
- `bloom_layer_observed`: L5 (Evaluate)
- `a_specialized`: [0.2, 0.2, 0.3, **1.0**, **0.3**]  # C + X（检查 = 工具使用）
- `mirt_params`: {difficulty: 0.0, discrimination: 1.0, guessing: 0.0}
- `misconceptions`: []
- `c_dimension_type`: self_checking_behavior
- `domain_agnostic`: True

**partial credit 评分**：
- 0.0：选 A (不检查)
- 0.3：选 B (简单看)
- 0.6：选 C (跑测试)
- 1.0：选 D (完整测试) — 元认知优

### 1.4 PC-C04 (L5 misconception 检测)

**题目**：
```python
# 概念检测：以下说法哪些是常见误解？
# A. range(1, 5) 包括 5
# B. Python 中变量赋值是复制值
# C. 函数内修改全局变量无需声明
# D. 以上都是误解
```

**正确答案**：D (以上都是误解) — misconception 综合检测

**Q 矩阵**：
- `topic`: cross_subject
- `bloom_layer_observed`: L5 (Evaluate)
- `a_specialized`: [0.3, 0.2, 0.2, **1.3**, 0.0]  # C 主导（misconception 折扣）
- `mirt_params`: {difficulty: 0.2, discrimination: 1.2, guessing: 0.0}
- `misconceptions`: ["M3", "M-candidate-mutable-confusion", "M-candidate-scope-confusion"]
- `c_dimension_type`: misconception_detection
- `domain_agnostic`: True  # misconception 是心理学通用概念

**partial credit 评分**：
- 0.0：选 A/B/C (单一误解识别，漏掉其他)
- 0.6：选 D (但没说明每个误解)
- 1.0：选 D + 详细解释每个误解

### 1.5 PC-C05 (L6 综合 Confidence)

**题目**：
```python
# 综合元认知评估：
# 1. 答完题是否会检查？
# 2. 遇到难题会求助还是独立思考？
# 3. 自我评估准不准？
# 4. 是否有常见误解？
```

**正确答案**：综合评估（元认知水平）

**Q 矩阵**：
- `topic`: cross_subject
- `bloom_layer_observed`: L6 (Create)
- `a_specialized`: [0.2, 0.2, 0.3, **1.2**, 0.2]
- `mirt_params`: {difficulty: 0.3, discrimination: 1.0, guessing: 0.0}
- `misconceptions`: []
- `c_dimension_type`: metacognition_synthesis
- `domain_agnostic`: True

**partial credit 评分**：综合 4 个行为评估

---

## 2. 领域无关性验证

| 题目 | 数学 | 语文 | 英语 | 物理 | 化学 |
|------|------|------|------|------|------|
| PC-C01 自我评估 | ✅ | ✅ | ✅ | ✅ | ✅ |
| PC-C02 求助决策 | ✅ | ✅ | ✅ | ✅ | ✅ |
| PC-C03 检查行为 | ✅ | ✅ | ✅ | ✅ | ✅ |
| PC-C04 misconception | ✅ | ✅ | ✅ | ✅ | ✅ |
| PC-C05 综合 | ✅ | ✅ | ✅ | ✅ | ✅ |

**全部领域无关**——5 道样题跨数学/语文/英语/物理/化学都适用。

---

## 3. 与编程领域 PB-C 主导题的关系

| 维度 | C-confidence 主导题 | PB-C 编程扩展 |
|------|-------------------|----------------|
| **含义** | 自我评估/求助/检查/misconception | 调试能力（Common mistakes）|
| **5D 核心** | ✅ C 维度（领域无关）| ❌ 编程领域应用层 |
| **字段** | `C.theta` MIRT 评估 | `programming_debug_score` 独立字段 |
| **题库** | 5 道样题 → 20+ 道扩 | 20 道 PB-C（保留） |
| **a_specialized C 权重** | 1.0-1.3 | 1.0-1.3 |
| **领域** | 跨学科（数学/语文/英语/物理/化学）| 编程领域 |

**双层架构**：
- **5D 核心**：C 维度 = C-confidence 主导题评估
- **编程扩展**：`programming_debug_score` = PB-C 主导题评估

---

## 4. 字段解耦设计

### 4.1 信念引擎扩展

```python
class StudentState:
    # 5D 核心（领域无关）
    K: KnowledgeState        # 知识掌握
    P: ProcedureState        # 程序技能
    S: StrategyState         # 策略能力
    C: ConfidenceState       # 认知置信度（自我评估/元认知）
    X: ExternalSupportState  # 外部支架（工具/笔记/记忆）

    # 应用层扩展（领域特定）
    # 编程领域
    programming_debug_score: Optional[float] = None  # 编程调试能力（PB-C 主导题评估）
    # 跨学科时此字段不应用
```

### 4.2 编程调试能力评估（programming_debug_score）

- 独立字段，不在 5D 核心内
- PB-C 主导题 20 道 trigger 后更新
- MIRT MAP 估计独立于 5D 联合估计
- UI 展示"5D 评估"（4/5 → 5/5 真评估）+ "编程领域扩展"（1/1）

### 4.3 lbc001 实际数据重新解释

- v0.54.1-c 端到端测试 lbc001 C θ=0.2145 → -0.07（5 道 PB-C partial credit 0.68）
- **不是 5D C 维度（Confidence）变化**——是 `programming_debug_score` 评估
- 5D C 维度（Confidence）= 0.2145（仍是占位值，待 C-confidence 主导题真评估）

---

## 5. 实施步骤

### 5.1 v0.54.1-f-a (当前): 设计文档 ✅
- 文件: research/90-mvp/10-phase5-c-confidence-questions-design.md
- 5 道 PC-C 样题设计 + 领域无关性验证 + 字段解耦

### 5.2 v0.54.1-f-b: Q 矩阵 JSON 追加 + 字段解耦
- 追加 5 道 PC-C 到 data/python_basics_q_matrix.json
- 字段: `domain_agnostic: True` (标记跨学科通用)
- 字段: `c_dimension_type: self_evaluation / help_seeking / self_checking / misconception_detection / metacognition_synthesis`
- 字段: `programming_debug_score` 独立于 5D（不实现 schema 改动，文档说明）

### 5.3 v0.54.1-f-c: 端到端测试脚本
- 模拟 lbc001 答 5 道 C-confidence（PC-C01~PC-C05）
- 模拟 AI 评分（基于 partial_credit_rubric）
- 不调真实 LLM（省 API 成本）
- 验证:
  - 5D C 维度真评估（不是占位）
  - 编程扩展 `programming_debug_score` 独立评估
  - 5D 完整性 4/5 → 5/5

---

## 6. 验收标准

### 6.1 lbc001 端到端测试（v0.54.1-f-c）

**步骤**：
1. lbc001 答 5 道 C-confidence（PC-C01~PC-C05）
2. AI 模拟评分（partial credit）
3. 5D C 维度 θ 变化（脱离 0.2145 占位值）
4. 5D C 维度 confidence 提升

**通过条件**：
- ✅ 5 题全部提交成功 + DB 持久化
- ✅ 5D C 维度 θ 变化（不再占位）
- ✅ 5D 完整性 5/5

### 6.2 编程领域扩展独立评估

- 之前 5 道 PB-C 答题数据保留为 `programming_debug_score`
- 跟 5D C 维度（Confidence）独立
- UI 分层展示

### 6.3 防御性自检

- silent failure：0 新增
- 版本号：v0.54.1 同步
- Q 矩阵 JSON schema 校验
- 文档一致性（5D 维度定义跨文档 = deep-research v2.0 / 02-arch / 01-cta）

---

## 7. 风险与回退

### 7.1 风险

| # | 风险 | 严重度 | 缓解 |
|---|------|--------|------|
| 1 | C-confidence 题型"太软"（self_evaluation 难精准评估）| 中 | LLM 评判 + 多次评估取平均 |
| 2 | 5 道样题量不够，lbc001 答完 C 维度仍波动大 | 中 | v0.54.1-g 扩 20+ 道 |
| 3 | 编程扩展字段不实现（仅文档说明）| 低 | 文档明确说明，v0.56.0+ 实施 |
| 4 | misconception 检测（PC-C04）依赖具体 M-ID | 低 | 通用 misconception 概念（不绑定 M3）|

### 7.2 回退方案

- v0.54.1-f 失败：保留 v0.54.1-c 端到端测试数据，重新设计 5 道题
- C-confidence 题型不准：v0.54.1-g 重新设计
- 编程扩展冲突：v0.55.0 实施 schema

---

## 8. 与 v0.54.1 编程领域 PB-C 主导题的关系

| 维度 | C-confidence 主导题（v0.54.1-f）| PB-C 编程扩展（v0.54.1-b 保留）|
|------|-------------------------------|-------------------------------|
| **含义** | 自我评估/元认知（领域无关）| 调试能力（编程领域）|
| **5D 核心** | ✅ C 维度 | ❌ 编程扩展 |
| **题库** | 5 道样题 → 20+ 道 | 20 道 |
| **字段** | `state.C.theta` MIRT 评估 | `state.programming_debug_score` |
| **更新机制** | 5D 联合 MIRT MAP | 独立 MIRT（可选）|
| **UI** | 5D 评估（5/5 真评估）| 编程领域扩展（1/1 评估）|
| **领域** | 跨学科 | 编程领域 |

**双层架构**：
- **5D 核心 = 领域无关**（K/P/S/C/X）—— ECOS 5D 评估完整性 5/5
- **编程扩展 = 领域特定**（programming_debug_score）—— 编程领域能力评估

---

## 9. 决策记录

**Bisen 2026-07-23 22:38 决策**：
- ✅ 方案 D（领域无关 + 恢复权威定义）
- ✅ D-2 保留 20 道 PB-C 为编程扩展
- ✅ 下一步 v0.54.1-f（C-confidence 5 道样题 + 端到端测试）

**Mavis 2026-07-23 22:40 反思**：
- 关键设计：C-confidence 主导题领域无关，跨数学/语文/英语/物理/化学通用
- 5 道样题 + partial credit 评分（基于 self_evaluation / help_seeking / self_checking / misconception_detection / metacognition_synthesis）
- 双层架构：5D 核心（领域无关）+ 编程扩展（领域特定）
- v0.54.1-c 端到端测试 lbc001 C θ=-0.07 重新解释：`programming_debug_score`（不是 5D C 维度）
- 5D 完整性目标 5/5 + 编程扩展 1/1

---

## 10. 关联文档

- [research/00-overview/08-cx-dimension-semantic-decision.md v1.1 §11.5](../00-overview/08-cx-dimension-semantic-decision.md)（Bisen 决策：方案 D）
- [research/90-mvp/09-phase5-c-dimension-questions-expanded.md](../90-mvp/09-phase5-c-dimension-questions-expanded.md)（v0.54.1-b 编程领域 PB-C 20 道保留为扩展）
- [discussions/2026-07-23-C主导题让C维度真实化发现+缺口分析.md](../../discussions/2026-07-23-C主导题让C维度真实化发现+缺口分析.md)
- [research/deep-research/Cognitive-Digital-Twin-Deep-Research.md v2.0 §3.3](../deep-research/Cognitive-Digital-Twin-Deep-Research.md)（权威定义）
- [research/00-overview/02-architecture.md §2.1 State Space](../00-overview/02-architecture.md)
- [research/30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md §1.2 CTA 对接](../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md)
- [ecos/cta/belief_state.py](../../ecos/cta/belief_state.py) DimensionId 定义

---

**创建日期**：2026-07-23
**维护者**：Bisen & Mavis
**下次更新**：v0.54.1-f-c 端到端测试后
