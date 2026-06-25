# 2026-06-25 · K12 认知结构教学法文档（v0.15.0，教学法层第 1 份）

## 主题

完成教学法层第 1 份文档 `research/20-pedagogy/01-k12-cognitive-structure.md`（v1.0，516 行），定义 ECOS 在小学/初中/高中各学段的差异化认知建模。

## 日期

2026-06-25

## 背景

教学法层第 1 份——基于：
- v2.0 §1.4（K12 三大优势：数据丰富 + B 易定义 + 易验证）
- [v0.5.0 C 维度内容库](../../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md)（TC 库 + Misconception 库）
- [02-architecture.md §2.1 State Space](../research/00-overview/02-architecture.md)
- [01-cta-belief-engine.md §2](../research/10-engineering/01-cta-belief-engine.md)
- [03-bloom-goal-library.md §11](../research/10-engineering/03-bloom-goal-library.md)

## 文档结构（11 章节）

| 章节 | 内容 |
|---|---|
| §0 | 模块定位（学段差异化的"基础配置"）|
| §1 | 小学阶段（1-6 年级）+ TC 库候选 4 + Misconception 库候选 3 |
| §2 | 初中阶段（7-9 年级）+ TC 库 8 + Misconception 库 10 |
| §3 | 高中阶段（10-12 年级）+ TC 库 7 + Misconception 库 4 |
| §4 | 学段过渡关键节点 |
| §5 | 学科 × 认知结构映射（数学 vs 语文 vs 物理）|
| §6 | 关键认知节点与里程碑（小学 5 + 初中 7 + 高中 4）|
| §7 | 中国课程标准对接 |
| §8 | ECOS 产品形态（UI/频率/时长）|
| §9 | 评估指标（vs 04-risks.md）|
| §10-11 | 关联文档 + 版本维护 |

## 关键差异化设计

| 维度 | 小学 | 初中 | 高中 |
|---|---|---|---|
| Piaget | 具体运算前期 + 中期 | 形式运算初期 | 形式运算成熟 |
| 5D 启用 | 单维 + X 重要 | 完整 5D | 完整 5D + 学科专业化 |
| BloomProfile | L1 主导（80-90%）| L1-L2 主导 + L3 显著 | L3 主导 + L4 显著 |
| CLT 默认 | NOVICE | DEVELOPING | PROFICIENT |
| 元认知干预 | 不适用 | 有限使用 | 完整使用 |
| 干预时长 | ≤ 15 分钟 | ≤ 30 分钟 | ≤ 45 分钟 |
| 家长端频率 | 每周 | 每月 | 每月或季度 |

## 各学段 TC / Misconception 库

| 学段 | TC 候选 | Misconception 候选 |
|---|---|---|
| 小学 | 4 个（分数、负数、乘法意义、守恒）| 3 条 |
| 初中 | 8 个（函数、变量、等式、几何证明、二次函数、极限初步等）| 10 条（v0.5.0 §2.6）|
| 高中 | 7 个（极限严格化、微积分、概率、向量空间等）| 4 条（Phase 5+）|

## 学段过渡的 ECOS 应对

- **小学 → 初中**：抽象思维突然要求 → TC 检测 + liminal 状态预警
- **初中 → 高中**：形式化要求 → BloomProfile 重新校准 + 干预降级
- **高中 → 大学**：自主学习能力 → LearningDNA 推断 + 元认知型干预完成率

## 产品形态差异

- **小学**：高色彩 + 游戏化 + 进度条；家长端每周
- **初中**：简洁专业 + 数据可视化；家长端每月
- **高中**：极简 + 工具化；家长端每月或季度

## Phase 0 进度

| 维度 | 状态 | 完成度 |
|---|---|---|
| 战略层 | ✅ 100% | 4/4 |
| 工程层 | ✅ 100% | 5/5 |
| **教学法层** | **25%** | **1/4** |
| MVP 设计 | ⏳ 0% | 0/1 |
| **总完成度** | **~89%** | **11/14** |

## 累计产出（v0.1.0 ~ v0.15.0）

- **15 个版本**
- **~15000 行**研究文档

## 产出文件

| 文件 | 角色 | 行数 |
|---|---|---|
| `research/20-pedagogy/01-k12-cognitive-structure.md` | **主文档**——K12 认知结构（v1.0，11 章节）| 516 |
| `discussions/2026-06-25-ecos-k12-cog-structure-doc.md` | **本文件**——本次会话简要记录 | ~100 |
| `CHANGELOG.md` | 升级到 v0.15.0 | — |

## 关联文档

- [README.md](../../README.md) — ECOS 项目入口
- [CHANGELOG.md](../../CHANGELOG.md) — 变更日志（v0.15.0）
- [research/20-pedagogy/01-k12-cognitive-structure.md](../../research/20-pedagogy/01-k12-cognitive-structure.md) — 本次主产出
- [research/10-engineering/03-bloom-goal-library.md §3.2](../../research/10-engineering/03-bloom-goal-library.md) — 数学 8 核心 TC 详细定义
- [research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md](../../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md) — v0.5.0 TC + Misconception

## 下一步

教学法层剩余 3 份：
- **02-bloom-application.md**（Bloom 在 K12 的应用）
- **03-learning-strategies.md**（学习策略空间）
- **04-zpd-application.md**（ZPD 在 ECOS 的应用）

然后是 MVP 设计（90-mvp/）——Phase 0 最后 1 份。

---

**创建日期**：2026-06-25
**维护者**：Bisen & Claude
**版本**：v0.15.0（教学法层第 1 份）
