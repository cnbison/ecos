# 2026-06-25 · Bloom 在 K12 应用教学法文档（v0.16.0，教学法层第 2 份）

## 主题

完成教学法层第 2 份文档 `research/20-pedagogy/02-bloom-application.md`（v1.0，564 行），定义 Bloom 6 层在 K12 各学段/各学科的应用与 ECOS 教学策略。

## 日期

2026-06-25

## 背景

教学法层第 2 份——基于：
- [01-k12-cognitive-structure.md](01-k12-cognitive-structure.md)（学段差异化）
- [03-bloom-goal-library.md](../research/10-engineering/03-bloom-goal-library.md)（BloomGoal 数据结构）
- [v0.4.0 §3.1 CA 6 阶段](../research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md)（与 Bloom 的对应）
- [v2.0 §1.4 Bloom 目标空间](../research/deep-research/Cognitive-Digital-Twin-Deep-Research.md)

## 文档结构（9 章节）

| 章节 | 内容 |
|---|---|
| §0 | 模块定位 + 核心问题（解决"会做但不会想"中国痛点）|
| §1 | 各学段 Bloom 分布（小学 / 初中 / 高中）|
| §2 | 各学科 Bloom 目标分布（数学/物理/语文/英语/化生）|
| §3 | 4 个跨层级教学策略（L1→L2 / L2→L3 / L3→L4 / L4→L5→L6）|
| §4 | BloomProfile 评估方法（行为锚定 + 多题取样 + LLM rubric）|
| §5 | 解决"会做但不会想"（ECOS 解决方案 + 5 步实施）|
| §6 | Bloom 与课程标准对接（18 个动词 ↔ 6 层）|
| §7 | ECOS 教学建议（给学生/教师/家长）|
| §8-9 | 关联文档 + 版本维护 |

## 核心内容

### 1. 各学段 Bloom 分布

| 学段 | 主要层级 | 次要层级 |
|---|---|---|
| 小学 | L1 80-90% | L2 10-20% |
| 初中 | L1-L2 50-60% | L3 20-30% / L4 5-10% |
| 高中 | L3 30-40% | L4 15-20% / L5 5-10% |

### 2. 4 个跨层级教学策略

```
L1 → L2: CLT NOVICE + EXPLANATORY + 类比
L2 → L3: CLT DEVELOPING + PRACTICE + 变式练习
L3 → L4: **核心难点** — INQUIRY + 拆解 + Articulation + Reflection
L4 → L5 → L6: INQUIRY + 议论文 + 项目式学习
```

### 3. 各学科 Bloom 特征

| 学科 | L4 重要性 | L5-L6 重要性 |
|---|---|---|
| 数学 | **难点** | 罕见 |
| 物理 | **核心** | 较少 |
| **语文** | 重要 | **核心**（议论文 + 写作）|
| 英语 | 重要 | 较少 |
| 化生 | 重要 | 较少 |

### 4. 解决"会做但不会想"5 步

1. CTA 估计 BloomProfile 6 层分布
2. 识别 L4-L6 缺口
3. LCA 推荐"L4 提升"干预
4. 每月重新评估
5. 家长/教师端展示 6 层雷达图

### 5. 评估方法关键决策

- 行为锚定评估（与课程标准对接）
- 多题取样（每层 2-10 道题）
- LLM rubric 仅用于语文 L4-L6 主观题（数学/物理绝不用）

## 关键设计决策

| 决策 | 选择 |
|---|---|
| 学段 Bloom 分布 | 小学 L1 / 初中 L1-L2+L3 / 高中 L3+L4 |
| 核心痛点 | 显式建模 L4-L6 + 主动引导 |
| L3→L4 进阶 | INQUIRY + 拆解 + Articulation |
| LLM rubric 边界 | 仅语文主观题（数学/物理绝不用）|
| 课程标准 | 18 个动词 ↔ 6 层 Bloom |

## Phase 0 进度

| 维度 | 状态 | 完成度 |
|---|---|---|
| 战略层 | ✅ 100% | 4/4 |
| 工程层 | ✅ 100% | 5/5 |
| **教学法层** | **50%** | **2/4** |
| MVP 设计 | ⏳ 0% | 0/1 |
| **总完成度** | **~93%** | **12/14** |

## 累计产出（v0.1.0 ~ v0.16.0）

- **16 个版本**
- **~15900 行**研究文档

## 产出文件

| 文件 | 角色 | 行数 |
|---|---|---|
| `research/20-pedagogy/02-bloom-application.md` | **主文档**——Bloom 在 K12（v1.0，9 章节）| 564 |
| `discussions/2026-06-25-ecos-bloom-application-doc.md` | **本文件**——本次会话简要记录 | ~120 |
| `CHANGELOG.md` | 升级到 v0.16.0 | — |

## 关联文档

- [README.md](../../README.md) — ECOS 项目入口
- [CHANGELOG.md](../../CHANGELOG.md) — 变更日志（v0.16.0）
- [research/20-pedagogy/01-k12-cognitive-structure.md](../../research/20-pedagogy/01-k12-cognitive-structure.md) — 上份文档
- [research/20-pedagogy/02-bloom-application.md](../../research/20-pedagogy/02-bloom-application.md) — 本次主产出
- [research/10-engineering/03-bloom-goal-library.md §3 数学 8 核心 TC](../../research/10-engineering/03-bloom-goal-library.md) — Bloom 库详细定义

## 下一步

教学法层剩余 2 份：
- **03-learning-strategies.md**（学习策略空间）
- **04-zpd-application.md**（ZPD 在 ECOS 的应用）

然后是 MVP 设计（90-mvp/）——Phase 0 最后 1 份。

---

**创建日期**：2026-06-25
**维护者**：Bisen & Claude
**版本**：v0.16.0（教学法层第 2 份）
