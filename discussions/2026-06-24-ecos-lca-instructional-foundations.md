# 2026-06-24 · LCA 教学法基础借鉴文档撰写

## 主题

完成 P0 第 2 份理论借鉴文档 `research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md`（v1.0，420 行），建立 LCA 干预策略的 3 大教学法理论群基础。

## 日期

2026-06-24

## 背景

[v2.0 深度研究 §3.4](../research/deep-research/Cognitive-Digital-Twin-Deep-Research.md) 已给出 LCA 的"干预空间"——按 Bloom 层级分类的策略字典（flashcard / worked_examples / socratic_questioning 等），但**没有教学法理论论证**。LCA 不知道**为什么**某个干预对某个学生有效。

本次借鉴填补这一 gap，建立 LCA 干预策略空间的**教学法基础**。

## 核心成果：3 大核心理论群

| 理论群 | 核心命题 | 借鉴到 LCA 的哪个环节 |
|---|---|---|
| **Cognitive Load Theory (Sweller)** | 工作记忆容量有限，超载则无效 | LCA **设计题目的硬约束**（4 级自适应呈现）|
| **Bjork 学派四件套** | 合意困难（desirable difficulties）提升长期学习 | LCA **干预策略的四把武器**（测试 / 间隔 / 合意 / 交错）|
| **Cognitive Apprenticeship (Collins/Brown)** | 专家思维可被显式教学（6 阶段）| LCA **教学过程的框架**（建模 → 教练 → 脚手架 → 表达 → 反思 → 探索）|

## 核心决策

### 1. CLT 4 级自适应呈现

根据学生 BloomProfile 自适应 4 级呈现（新手 / 进阶 / 熟练 / 专家）——expertise reversal effect 自动化：新手需要完整 worked example，专家需要独立解题。

### 2. Bjork 四件套的优先级

| 优先级 | 工具 | MVP 状态 |
|---|---|---|
| P0 | 测试效应（Testing Effect）| ✅ MVP |
| P0 | 间隔效应（Spacing Effect）| ✅ MVP |
| P1 | 合意困难（Desirable Difficulties）| Phase 5+ |
| P1 | 交错练习（Interleaving）| Phase 5+ |

### 3. Cognitive Apprenticeship 6 阶段 + CTA 触发

LCA 在后台判断当前 6 阶段位置（不暴露给 UI），CTA 触发 scaffolding 衰减——连续 N 次成功后自动撤走支持。

### 4. 与 CTA 数学基础的整合

完整 L0-L4 算法栈：

```
L4 LCA 策略优化层    Cognitive Apprenticeship 6 阶段框架
L3 LCA 干预类型选择层  Bjork 四件套 + CLT
L2 状态估计层（CTA）  MIRT + CD-CAT
L1 时间演化层（CTA）  BKT/DKT + Spaced Repetition
L0 概率框架层（CTA）  POMDP / HMM
```

**关键架构澄清**：
- CTA 拥有 L0-L2（纯统计实现，不调用 LLM）
- LCA 拥有 L3-L4（教学法决策）
- L3 是"翻译层"——把 CTA 统计输出翻译成教学法动作

## 产出文件

| 文件 | 角色 | 行数 |
|---|---|---|
| `research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md` | **主文档**——LCA 教学法基础借鉴（v1.0，3 大理论群）| 420 |
| `discussions/2026-06-24-ecos-lca-instructional-foundations.md` | **本文件**——本次会话简要记录 | ~80 |
| `CHANGELOG.md` | 升级到 v0.4.0 | — |

## 关键引用来源

- **Cognitive Load Theory**：Sweller (1988). *Cognitive load during problem solving*. Cognitive Science. / Sweller, van Merrienboer & Paas (2019). *Cognitive Architecture and Instructional Design*. EBR.
- **Testing Effect**：Roediger & Karpicke (2006). *Test-Enhanced Learning*. Psychological Science.
- **Desirable Difficulties**：Bjork & Bjork (1992, 2011). *A new theory of disuse and an old theory of stimulus fluctuation*.
- **Spacing Effect**：Cepeda et al. (2006). *Distributed Practice in Verbal Recall Tasks*. Psychological Bulletin.
- **Interleaving**：Rohrer & Taylor (2007). *The shuffling of mathematics problems improves learning*. Applied Cognitive Psychology.
- **Cognitive Apprenticeship**：Collins, Brown & Newman (1989). *Cognitive Apprenticeship: Teaching the Craft of Reading, Writing, and Mathematics*.

## 与 ECOS 现有借鉴的整合

```
v0.3.0 CTA 数学基础（5 层数学栈）        ✅
v0.4.0 LCA 教学法基础（3 大理论群）      ✅
v0.5.0 C 维度内容库（待写）              ⏳
战略层 02-architecture.md                ⏳
战略层 03-roadmap.md                     ⏳
战略层 04-risks.md                       ⏳
工程层 5 份文档                          ⏳
```

## 关联文档

- [README.md](../../README.md) — ECOS 项目入口
- [CHANGELOG.md](../../CHANGELOG.md) — 变更日志（v0.4.0）
- [research/30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md](../../research/30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md) — 上份文档（CTA 数学基础）
- [research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md](../../research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md) — 本次主产出
- [v2.0 深度研究 §3.4 LCA — Policy Optimizer](../../research/deep-research/Cognitive-Digital-Twin-Deep-Research.md) — 本文档填补的 gap

## 下一步

- **P0 第 3 份（最后一份）**：`03-c-dimension-content-libraries.md`（C 维度内容库：Threshold Concepts + Misconceptions Research）
- 完成后 P0 借鉴全部完成，回到战略层（02-architecture.md → 03-roadmap.md → 04-risks.md）

---

**创建日期**：2026-06-24
**维护者**：Bisen & Claude
**版本**：v0.4.0
