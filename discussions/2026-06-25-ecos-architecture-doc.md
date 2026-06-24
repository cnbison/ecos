# 2026-06-25 · ECOS 整体架构文档撰写（v0.7.0）

## 主题

完成战略层第 2 份文档 `research/00-overview/02-architecture.md`（v1.0，703 行），把 P0 三件套（CTA 数学基础 + LCA 教学法基础 + C 维度内容库）整合到 ECOS 整体架构总图。

## 日期

2026-06-25

## 背景

战略层依赖链（01-applications.md → 02-architecture.md → 03-roadmap.md → 04-risks.md）的第 2 份。

[v2.0 深度研究 §3](../research/deep-research/Cognitive-Digital-Twin-Deep-Research.md) 已给出 ECOS 架构骨架（Bloom Goal Space → LCA → CTA → Student），但**没有把 P0 三件套整合到工程实现层**。本次完成架构文档，填补这一 gap。

## 核心成果：三层视角架构总图

```
【顶层】三空间（State + Bloom Goal + Policy）
        ↓
【中层】双 Agent（CTA + LCA + 互校机制）
        - CTA L0-L4 数学栈（POMDP/HMM + BKT/DKT + MIRT + CD-CAT + Causal Inference）
        - LCA L3-L4 教学法栈（CLT + Bjork 四件套 + Cognitive Apprenticeship 6 阶段）
        - 双 Agent 互校（互校循环 + L4 因果归因）
        ↓
【底层】内容基础（TC + Misconceptions + Knowledge Ontology）
        ↓
【接口层】App 层（数据采集 + 干预执行）
        ↓
       Student
```

## 核心架构原则

1. **数学层不用 LLM（硬底线）**：CTA L0-L2 是纯统计实现
2. **LLM Critic 边界**：LLM 仅用于感知层（自然语言→结构化）+ 解释层（统计值→自然语言）+ Misconception 检测
3. **双 Agent 解耦**：CTA 通过 POMDP 接口 `(S, A, O, T, R, Ω)` 与 LCA 协作
4. **内容库与算法解耦**：TC + Misconceptions 是内容，CTA/LCA 是算法——内容更新不影响算法

## 11 章节结构

| 章节 | 内容 |
|---|---|
| §0 架构定位 | 与 v2.0 §3 关系（补充 + 细化，不冲突）|
| §1 核心架构总图 | 三层视角 ASCII 图 + 4 大架构原则 |
| §2 三空间架构 | State Space 完整结构 + Bloom Goal Space 例子 + Policy Space 参数化 |
| §3 双 Agent 详细架构 | CTA 5 层数学栈 + LCA 2 层教学法栈 + 互校机制 |
| §4 完整数据流 | 7 步端到端伪代码 + 时序图 |
| §5 状态估计工程实现 | CTA 5 层数学栈工程映射 + Q 矩阵扩展 + C 维度评估流程 + LLM Critic 精确边界 |
| §6 干预策略工程实现 | LCA L3-L4 教学法栈工程映射 + 干预参数化 + Contextual Bandits MVP |
| §7 持久化与长期会话管理 | SQL 结构 + 跨会话继承 + 跨学期/学段演化（Phase 5+）|
| §8 MVP 架构 | Phase 4 实现范围表 + 简化数据流 |
| §9 与 v2.0 §3 关系 | 10 维度对照表 |
| §10 关联文档 + §11 版本与维护 | 链接 P0 三件套 + 工程层占位 |

## MVP 范围（明确）

| 组件 | MVP 状态 |
|---|---|
| CTA L0 POMDP | ✅ EKF + 离散属性精确推断 |
| CTA L1 BKT | ✅ 经典 4 参数 |
| CTA L2 MIRT | ✅ 5D 非补偿 Bi-factor |
| CTA L3 CD-CAT | ✅ GDINA + PWKL 选题 |
| CTA L4 因果归因 | ⚠️ 简化 A/B + T-test（不实现 Causal Forest）|
| CTA C 维度内容库 | ✅ TC 8 个 + Misconceptions 30-50 条 |
| LCA L3 CLT | ✅ 4 级自适应呈现 |
| LCA L3 Bjork | ✅ 测试效应 + 间隔；⚠️ 合意困难 + 交错 Phase 5+ |
| LCA L4 6 阶段 | ✅ Stage 1-3；⚠️ Stage 4-6 Phase 5+ |
| LCA L4 策略优化 | ✅ Contextual Bandits (LinUCB) |
| 持久化 | ✅ SQLite + JSON |
| 跨学期 | ⚠️ Phase 5+ |

## 与 v2.0 §3 关系（10 维度对照）

v2.0 §3 提供了 4 个完整项（三空间骨架 / CTA 思维模式 / LCA 思维模式 / BloomProfile）+ 5 个补充项（互校机制 / 完整数据流 / 持久化等）。本文档主要补充：
- 状态估计工程（L0-L4 完整工程映射）
- 干预策略工程（L3-L4 教学法栈）
- C 维度内容库（TC + Misconceptions 双轨）
- MVP 架构范围（明确包含/不包含组件）

## 产出文件

| 文件 | 角色 | 行数 |
|---|---|---|
| `research/00-overview/02-architecture.md` | **主文档**——ECOS 整体架构（v1.0，11 章节）| 703 |
| `discussions/2026-06-25-ecos-architecture-doc.md` | **本文件**——本次会话简要记录 | ~110 |
| `CHANGELOG.md` | 升级到 v0.7.0 | — |

## 关联文档

- [README.md](../../README.md) — ECOS 项目入口
- [CHANGELOG.md](../../CHANGELOG.md) — 变更日志（v0.7.0）
- [research/00-overview/01-applications.md](../../research/00-overview/01-applications.md) — 上份战略层文档（应用场景）
- [research/00-overview/02-architecture.md](../../research/00-overview/02-architecture.md) — 本次主产出
- [v2.0 深度研究 §3 ECOS 完整架构](../../research/deep-research/Cognitive-Digital-Twin-Deep-Research.md) — 本文档的骨架来源
- [P0 三件套](../../research/30-shared-cognitive-tools/theoretical-foundations/README.md) — 本文档的整合来源

## 下一步

战略层剩余 2 份：
- **P0**：`03-roadmap.md`（阶段划分——基于本架构定义 M0-M7 详细任务）
- **P0**：`04-risks.md`（风险矩阵——基于本架构 + 路线图识别风险）

战略层完成后，进入工程层（`10-engineering/`）和教学法层（`20-pedagogy/`）。

---

**创建日期**：2026-06-25
**维护者**：Bisen & Claude
**版本**：v0.7.0
