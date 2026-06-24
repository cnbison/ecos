# 2026-06-24 · CTA 数学基础借鉴文档撰写

## 主题

完成 P0 第 1 份理论借鉴文档 `research/30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md`（v1.0，451 行），建立 CTA 信念分布的 L0→L4 数学栈。

## 日期

2026-06-24

## 背景

Bisen 在 review 完 ECOS 已吸收理论基础后，判断需要"按 P0 → P1 → P2 顺序逐步吸收"尚未借鉴但强烈契合的理论框架。本文档是 P0 首批 3 份借鉴的第 1 份。

**核心 gap**：[v2.0 深度研究 §3.3](../research/deep-research/Cognitive-Digital-Twin-Deep-Research.md) 把 CTA 定义为 "State Estimator"，但只提到 IRT/BKT/DKT 等心理测量学方法**名字**，未给出具体算法框架。

## 核心成果：CTA L0→L4 数学栈

5 个核心理论不是平行的，而是构成 **CTA 信念分布的 5 层数学栈**：

| 层级 | 理论 | 借鉴到 ECOS CTA 的哪个环节 |
|---|---|---|
| **L4 因果归因层** | Causal Inference（DoWhy + Causal Forest）| 干预效果归因 + 异质性处理 |
| **L3 自适应选择层** | CD-CAT（GDINA + PWKL 选题）| 下一题/下一干预的自适应选择 |
| **L2 状态估计层** | MIRT（5D 非补偿多维能力向量）| 5D 状态联合估计 + Σ_θ 协方差 |
| **L1 时间演化层** | BKT / DKT（单知识点掌握度演化）| P(L_n) 的更新（含间隔效应衰减）|
| **L0 概率框架层** | POMDP / HMM（隐藏状态 + 部分观测）| 信念状态 b(s) 的更新循环 |

## 核心决策

### 1. 数学层不调用 LLM（硬底线）

```
数学层（L0-L4）  ← 纯统计实现，不使用 LLM
感知层            ← LLM Critic 把自然语言转结构化
解释层            ← LLM 生成自然语言报告（基于统计值）
```

**任何让 LLM 直接生成信念估计的设计都是退路**——这是 ECOS "科学化认知估计"的硬底线。

### 2. 非补偿型 MIRT（避免"伪掌握"）

MIRT 默认是补偿型（K 弱可由 P 强补偿答对难题）—— ECOS 必须用**非补偿型 MIRT**，避免"知识弱但程序强被误判掌握"的诊断错误。

### 3. CTA 与 LCA 通过 POMDP 接口解耦

```
CTA → LCA：b(s) 信念分布 + BloomProfile + LearningDNA
LCA → CTA：a_t 干预选择 + r_t 干预奖励
```

POMDP 的 (S, A, O, T, R, Ω, γ) 接口让 CTA 与 LCA 解耦：CTA 只关心"状态怎么更新"，LCA 只关心"选什么干预最优"。

### 4. MVP 实施路线

| Phase | 算法栈 |
|---|---|
| **Phase 4（MVP）**| BKT（4 参数）+ MIRT（5D 非补偿）+ 简化 CD-CAT（GDINA 基础）|
| **Phase 5** | POMDP 整合 + Causal Forest 归因 |
| **Phase 6** | DKT/DKVMN 跨知识点关联 + 完全 POMCP |

依赖成熟开源库：pyBKT, mirt, GDINA, DoWhy, pgmpy。

## 产出文件

| 文件 | 角色 | 行数 |
|---|---|---|
| `research/30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md` | **主文档**——CTA 数学基础借鉴（v1.0，5 层数学栈）| 451 |
| `discussions/2026-06-24-ecos-cta-math-foundations.md` | **本文件**——本次会话简要记录 | ~80 |
| `CHANGELOG.md` | 升级到 v0.3.0（次版本递增）| — |

## 关键引用来源

- **MIRT**：Reckase (2009). *Multidimensional Item Response Theory*. Springer.
- **CD-CAT / GDINA**：Cheng (2009); de la Torre (2011). *GDINA: An R Package for Cognitive Diagnosis Modeling*.
- **BKT**：Corbett & Anderson (1994). *Knowledge tracing: Modeling the acquisition of procedural knowledge*. UMUAI.
- **DKT**：Piech et al. (2015). *Deep Knowledge Tracing*. NeurIPS.
- **POMDP**：Kaelbling, Littman & Cassandra (1998). *Planning and acting in partially observable stochastic domains*. AIJ.
- **Causal Inference**：Pearl (2009). *Causality*. Cambridge. / Wager & Athey (2018). *Estimation and Inference of Heterogeneous Treatment Effects using Random Forests*. JASA.

## 关联文档

- [README.md](../../README.md) — ECOS 项目入口
- [CHANGELOG.md](../../CHANGELOG.md) — 变更日志（v0.3.0）
- [research/00-overview/01-applications.md](../../research/00-overview/01-applications.md) — 战略层应用场景
- [research/30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md](../../research/30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md) — 本次主产出
- [v2.0 深度研究 §3.3](../../research/deep-research/Cognitive-Digital-Twin-Deep-Research.md) — 本文档填补的 gap

## 下一步

- **P0 第 2 份**：`02-lca-instructional-foundations.md`（LCA 教学法基础：Cognitive Load Theory + Bjork 四件套 + Cognitive Apprenticeship）
- **P0 第 3 份**：`03-c-dimension-content-libraries.md`（C 维度内容库：Threshold Concepts + Misconceptions Research）
- **P0 之后**：回到战略层（02-architecture.md → 03-roadmap.md → 04-risks.md）

---

**创建日期**：2026-06-24
**维护者**：Bisen & Claude
**版本**：v0.3.0
