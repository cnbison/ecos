# 2026-06-25 · Bloom Goal Library 工程文档（v0.12.0，工程层第 3 份）

## 主题

完成工程层第 3 份文档 `research/10-engineering/03-bloom-goal-library.md`（v1.0，1093 行），把 Bloom 6 层认知层级工程化为可计算的目标库——作为 CTA 与 LCA 之间的"共同语言"。

## 日期

2026-06-25

## 背景

工程层第 3 份——Bloom Goal Library 基于：
- v2.0 §3.4（LCA + Bloom 映射）
- 02-architecture.md §2.2（Bloom Goal Space）
- v0.5.0 C 维度内容库（TC + Misconceptions）
- [01-cta-belief-engine.md](../../research/10-engineering/01-cta-belief-engine.md)（CTA 接口）
- [02-lca-policy-engine.md](../../research/10-engineering/02-lca-policy-engine.md)（LCA 接口）

## 文档结构（13 章节）

| 章节 | 内容 |
|---|---|
| §0 | 模块定位（CTA + LCA 共同语言）|
| §1 | 整体架构（6 层 × 学科 + 12 子目录）|
| §2 | Bloom 数据结构（6 层枚举 + BloomGoal + Library 容器）|
| §3 | 数学 Bloom 目标库（MVP 核心）|
| §4 | 物理 Bloom 目标库（Phase 5+）|
| §5 | 语文 Bloom 目标库（Phase 5+）|
| §6 | 跨学科 Bloom 整合 |
| §7 | next_target 选择算法 |
| §8 | 与 TC / Misconception 库集成 |
| §9 | 查询接口（3 个示例）|
| §10 | 测试策略 |
| §11 | MVP 范围（8 组件 + 数据规模）|
| §12-13 | 关联文档 + 版本维护 |

## 核心工程实现

### 1. 完整 BloomGoal 数据结构

```python
@dataclass
class BloomGoal:
    goal_id, subject, skill_id, skill_name
    bloom_layer: BloomLevel
    description, cognitive_objectives, assessment_criteria
    threshold_concepts, misconceptions  # v0.5.0 整合
    prerequisites, follow_ups  # 学习路径
    problem_ids, estimated_duration_min
    curriculum_standard_ref  # 中国课程标准对接
```

### 2. MVP 候选：数学 8 知识点 × 4 层 = 32 条

| # | 知识点 | TC | L1 | L2 | L3 | L4 |
|---|---|---|---|---|---|---|
| 1 | 二次函数 | TC_quadratic | ✅ | ✅ | ✅ | ✅ |
| 2 | 函数 | TC_function | ✅ | ✅ | ✅ | ✅ |
| 3 | 变量 | TC_variable | ✅ | ✅ | ✅ | ✅ |
| 4 | 一次函数 | - | ✅ | ✅ | ✅ | ✅ |
| 5 | 反比例函数 | - | ✅ | ✅ | ✅ | ✅ |
| 6 | 几何证明 | TC_proof | ✅ | ✅ | ✅ | ✅ |
| 7 | 三角形 | - | ✅ | ✅ | ✅ | ✅ |
| 8 | 概率与统计 | - | ✅ | ✅ | ✅ | ✅ |

**L5/L6 MVP 不实现**（K12 不常达到，[04-risks.md §B1](../../research/00-overview/04-risks.md)）。

### 3. 6 层认知行为定义

```python
BLOOM_LEVELS = {
    REMEMBER: {"定义", "列出", "回忆", "识别", "命名"},
    UNDERSTAND: {"解释", "归纳", "分类", "总结", "推断"},
    APPLY: {"应用", "使用", "执行", "实施", "解决"},
    ANALYZE: {"分解", "比较", "对比", "识别模式", "归因"},
    EVALUATE: {"评判", "辩护", "选择", "论证", "批评"},
    CREATE: {"设计", "综合", "构建", "创造", "发明"},
}
```

### 4. next_target 选择算法

```python
class NextBloomTargetSelector:
    def select(self, student_id, belief_state, target_skill_id=None):
        # Step 1: 选目标知识点（提升空间最大 + TC 跨越考量）
        # Step 2: 选目标 Bloom 层（当前层 + 1，但不超过能力上限）
        # Step 3: 验证前置条件（前置 BloomGoal 是否已掌握）
        # Step 4: 输出学习路径（前置 + 当前 + 后置）
```

### 5. 与 v0.5.0 集成

- **TC 跨越后 BloomProfile 提升**：crossed TC → affected BloomGoals → +0.1
- **Misconception 命中后 BloomProfile 下调**：hit misconception → affected BloomGoals × 0.7
- **Q 矩阵扩展**：每题标注 BloomGoal + TC + Misconception

## 关键决策

| 决策 | MVP 选择 |
|---|---|
| 学科 | 数学（MVP）|
| 库规模 | 8 知识点 × 4 层 = 32 条 |
| L5/L6 | MVP 不实现（K12 不常达到）|
| 课程标准 | 中国教育部人教版 |
| TC 集成 | 跨越后 BloomProfile +0.1 |
| Misconception 集成 | 命中后 BloomProfile × 0.7 |
| 跨学科 | MVP 仅占位，Phase 5+ 扩展 |

## 数据规模演化

| 库 | MVP | Phase 5 | Phase 6 |
|---|---|---|---|
| 数学 | 32 条 | 100 条 | 300 条 |
| 物理 | 0 | 80 条 | 200 条 |
| 语文 | 0 | 50 条 | 150 条 |
| 跨学科 | 0 | 5 条 | 20 条 |
| **总计** | **32 条** | **235 条** | **670 条** |

## 评估指标

| 指标 | 阈值 |
|---|---|
| BloomProfile 方差解释 | ≥ 60% |
| 数学库覆盖率 | ≥ 80% 课程标准核心知识点 |
| 课程标准对接准确率 | ≥ 90% |
| next_target 合理性 | ≥ 80% 接受率 |
| TC 跨越后 Bloom 提升 | ≥ 0.1 绝对提升 |
| L5/L6 误推率 | 0%（K12 应不推荐）|

## 产出文件

| 文件 | 角色 | 行数 |
|---|---|---|
| `research/10-engineering/03-bloom-goal-library.md` | **主文档**——Bloom 目标库（v1.0，13 章节）| 1093 |
| `discussions/2026-06-25-ecos-bloom-library-doc.md` | **本文件**——本次会话简要记录 | ~120 |
| `CHANGELOG.md` | 升级到 v0.12.0 | — |

## 关联文档

- [README.md](../../README.md) — ECOS 项目入口
- [CHANGELOG.md](../../CHANGELOG.md) — 变更日志（v0.12.0）
- [research/10-engineering/01-cta-belief-engine.md](../../research/10-engineering/01-cta-belief-engine.md) — 上份文档（CTA 信念引擎）
- [research/10-engineering/02-lca-policy-engine.md](../../research/10-engineering/02-lca-policy-engine.md) — 上份文档（LCA 策略引擎）
- [research/10-engineering/03-bloom-goal-library.md](../../research/10-engineering/03-bloom-goal-library.md) — 本次主产出
- [research/00-overview/02-architecture.md §2.2](../../research/00-overview/02-architecture.md) — Bloom Goal Space 架构

## 下一步

工程层剩余 2 份：
- **04-dual-agent-calibration.md**（双 Agent 互校）—— CTA ↔ LCA 接口契约
- **05-persistence-session.md**（持久化）—— BloomGoal + CTA 状态 + 干预历史存储

待 5 份工程文档完成后，工程层 100% 完成。

---

**创建日期**：2026-06-25
**维护者**：Bisen & Claude
**版本**：v0.12.0（工程层第 3 份）
