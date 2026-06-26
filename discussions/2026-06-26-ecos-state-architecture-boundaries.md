# 2026-06-26 · ECOS 状态架构边界讨论

> **版本**：v1.0（2026-06-26）
> **性质**：架构边界分析——基于用户对 `discussions/2026-06-25-ecos-workflow-demo.md` 中 5D 状态 / BloomProfile / "含义" 三方面的追问
> **来源**：用户主动追问（关键洞察）
> **维护者**：Bisen & Claude

---

## 1. 讨论背景

Bisen 在阅读业务流程演示文档（`discussions/2026-06-25-ecos-workflow-demo.md`）时，对 ECOS 状态架构提出 3 个核心问题：

1. **5D 状态是每个学生一份数据吗？**
2. **BloomProfile 是一个学生一份还是针对知识点可以有多份？**
3. **5D 状态中 K（知识）的"含义"是出于解释需要补充的还是存在状态之中的？**

这些问题触及 ECOS 状态架构的**核心设计选择**——本文档系统分析并形成结论。

---

## 2. 核心结论（按问题）

### 2.1 问题 1：5D 状态是每个学生一份数据吗？

**答案**：**是**，每个学生有一份 `BeliefState`（5D + BloomProfile + LearningDNA + Trajectory + TC + Misconceptions）。

**关键点**：
- 5D 是**聚合状态**（不是按知识点分项）
- 具体到每个知识点的状态在 `evidence_log` 表 + BKT 内部模型中
- 每个知识点有自己的 BKT 模型实例（`BKTEvolutionLayer` 管理）
- BloomProfile 是聚合的 6 层分布（不是 8 知识点 × 6 层 = 48 条）

**架构边界**（批判性）：
- ✅ 简单：所有数值都聚合存储，查询高效
- ❌ 按知识点差异不显示（学生"二次函数学得好、一元二次方程学得差"被平均化）

### 2.2 问题 2：BloomProfile 是学生一份还是知识点多份？

**答案**：**两层结构**。

| 层 | 粒度 | 存储位置 | 含义 |
|---|---|---|---|
| **学生级** | 6 层分布（聚合）| `BeliefState.bloom_profile` | 学生"整体在哪一层" |
| **知识点级** | 知识点 × 6 层目标 | `BloomGoalLibrary` | 学生在每个知识点每层的具体目标 |

**举例**：
- 学生 BloomProfile L3 Apply = 0.40（**整体**应用层较弱）
- 但具体知识点级别：
  - 二次函数 L3 Apply = 0.50（中等）
  - 一元二次方程 L3 Apply = 0.30（较弱）
  - 函数图像 L3 Apply = 0.45（中等偏弱）

**潜在改进**（Phase 5+）：
```python
@dataclass
class BloomProfileState:
    # 当前：聚合 6 层
    remember, understand, apply, analyze, evaluate, create: float
    
    # 扩展：知识点×层级的详细矩阵（Phase 5+）
    per_skill: Dict[str, Dict[BloomLevel, float]] = field(default_factory=dict)
    # 例如 per_skill["quadratic_function"][BloomLevel.APPLY] = 0.50
```

### 2.3 问题 3：K 的"含义"是补充说明还是存在状态中？

**答案**：**不是 BeliefState 的字段**——BeliefState 只有数值。

`DimensionState` 数据结构（[01-cta-belief-engine.md §2.1](../research/10-engineering/01-cta-belief-engine.md)）：

```python
@dataclass
class DimensionState:
    theta: float                  # 数值（状态）
    se: float                     # 数值（状态）
    mastery_prob: float           # 数值（状态）
    confidence: float             # 数值（状态）
    evidence_ids: List[int]       # 数值列表（指向 evidence_log）
    last_updated: datetime
    # 注意：没有"含义"字段
```

**"二次函数顶点公式'基本记得但应用易错'"这种描述** 是 **LLM 解释层（[01-cta-belief-engine.md §9.2](../research/10-engineering/01-cta-belief-engine.md)）生成的自然语言诊断**——根据 BeliefState + BloomGoal + evidence_log 生成。

```
┌──────────────────────────────────────────────────────────────┐
│  BeliefState（持久化）                                          │
│    K.theta = 0.55                                              │
│    K.mastery_prob = 0.55                                        │
│    K.evidence_ids = [101, 102, 103]  ← 指向 evidence_log      │
└──────────────────────────────────────────────────────────────┘
                            ↓ LLM 解释层（每次新生成）
┌──────────────────────────────────────────────────────────────┐
│  Diagnosis Report（自然语言，ephemeral）                          │
│    "二次函数顶点公式基本记得但应用易错"                          │
│    "P 维度 0.30 提示多步解题程序薄弱"                          │
└──────────────────────────────────────────────────────────────┘
```

**架构边界**（批判性思考）：
- ✅ 数值状态持久化（BeliefState + evidence_log）
- ✅ "含义"每次 LLM 生成（基于当前状态）
- ❌ "含义"**不持久化**——下次查看要重新生成
- ❌ 历史"含义"丢失（无法回溯"当时认为学生已掌握"）

---

## 3. 当前架构边界总结

| 维度 | 是否持久化 | 是否按知识点分解 |
|---|---|---|
| 5D 数值（K/P/S/C/X）| ✅ | ❌（聚合）|
| BloomProfile 6 层 | ✅ | ❌（聚合）|
| BloomGoal 知识点×层 | ✅ | ✅（细粒度）|
| BKT 单知识点 P(L) | ✅ | ✅（细粒度）|
| evidence_log 原始作答 | ✅ | ✅（每题）|
| Misconception 命中历史 | ✅ | ✅ |
| TC 状态（liminal/post-liminal）| ✅ | ✅（每个 TC）|
| **LLM 生成的"含义"诊断** | **❌ ephemeral** | — |

---

## 4. Phase 5+ 推荐演进

### 4.1 持久化 LLM 诊断报告（`diagnostic_reports` 表）

```python
# 新增 diagnostic_reports 表
CREATE TABLE diagnostic_reports (
    report_id TEXT PRIMARY KEY,
    student_id TEXT,
    timestamp TIMESTAMP,
    belief_state_snapshot BLOB,   -- 当时的状态
    llm_explanation TEXT,          -- ★ 持久化 LLM 解释
    audience TEXT,                 -- 'teacher' / 'parent' / 'student'
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);
```

**价值**：
- 回溯"3 周前教师认为学生已掌握"——查阅 diagnostic_reports
- 跨时间比较"诊断风格变化"
- 学术研究"LLM 解释质量评估"

### 4.2 BloomProfile 增加 per_skill 详细矩阵

```python
@dataclass
class BloomProfileState:
    # 聚合 6 层（保持向后兼容）
    remember, understand, apply, analyze, evaluate, create: float
    
    # 新增：知识点×层级（Phase 5+）
    per_skill: Dict[str, Dict[BloomLevel, float]] = field(default_factory=dict)
```

**价值**：
- 显示学科/知识点差异
- 班级整体诊断（聚合）+ 个体精准诊断（细粒度）
- 学术研究"学生认知结构细粒度分析"

### 4.3 在评估报告中展示"聚合 vs 细粒度"对比

家长/教师报告：
```
聚合诊断：L3 Apply 0.40（整体弱）
细粒度诊断：
  - 二次函数 L3 Apply 0.50（中等）
  - 一元二次方程 L3 Apply 0.30（弱）
  - 函数图像 L3 Apply 0.45（中等偏弱）
建议：优先补强一元二次方程
```

---

## 5. 当前设计权衡（MVP 范围）

**当前设计的优势**：
- ✅ 简单：所有数值都聚合存储，查询高效
- ✅ LLM 解释基于最新数据（不依赖旧解释）
- ✅ MVP 范围可控（[90-mvp/README.md §1.4 资源需求 16-32 万](../research/90-mvp/README.md)）

**当前设计的边界**：
- ❌ 历史"诊断"无法回溯
- ❌ BloomProfile 6 层是聚合（不显示学科/知识点差异）
- ❌ LLM 解释不持久化（每次重新生成）

**决策**：
- **MVP 阶段（M2-M3）保持当前简化设计**——确保 MVP 验证 H1-H4 假设
- **Phase 5+ 引入上述演进**——基于 H1-H4 验证结果决定是否值得投入

---

## 6. 关键洞察

1. **架构边界 = 简化 vs 细粒度**——MVP 选简化，Phase 5+ 加细粒度
2. **"含义"是 LLM 生成的 ephemeral 输出**——不持久化是当前设计选择
3. **每层都有持久化的"事实依据"**——5D 数值、BloomGoal、evidence_log 都持久化
4. **MVP 优先验证 H1-H4**——架构演进基于实验结果决定

---

## 7. 关联文档

- 触发文档：[2026-06-25-ecos-workflow-demo.md](2026-06-25-ecos-workflow-demo.md) — 业务流程演示
- 上层架构：[02-architecture.md](../research/00-overview/02-architecture.md)
- 工程实现：
  - [01-cta-belief-engine.md §2.1 BeliefState 数据结构](../research/10-engineering/01-cta-belief-engine.md)
  - [03-bloom-goal-library.md §2 BloomGoal 数据结构](../research/10-engineering/03-bloom-goal-library.md)
  - [05-persistence-session.md §2 SQLite Schema](../research/10-engineering/05-persistence-session.md)
- MVP 范围：[90-mvp/README.md §8.1 MVP 包含的组件](../research/90-mvp/README.md)

---

## 8. 版本与维护

- **v1.0**（2026-06-26）— 初版

**待办（Phase 5+ 触发）**：
- 当 M2-M3 MVP 实验完成后，回填本讨论的"含义"实例（用真实 LLM 输出）
- 当决策引入 diagnostic_reports 表时，更新 [05-persistence-session.md](../research/10-engineering/05-persistence-session.md) §2 Schema
- 当决策引入 per_skill 矩阵时，更新 [01-cta-belief-engine.md](../research/10-engineering/01-cta-belief-engine.md) §2.1

---

**创建日期**：2026-06-26
**维护者**：Bisen & Claude
