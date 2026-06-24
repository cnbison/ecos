# 2026-06-24 · 理论借鉴路线图 SSOT 建立（v0.6.0）

## 主题

建立 `research/30-shared-cognitive-tools/theoretical-foundations/README.md` 作为子目录 SSOT，明确记录 P0（已完）+ P1（待写 9 候选）+ P2（待写 6 候选）的完整理论借鉴路线图。

## 日期

2026-06-24

## 背景

P0 三件套（v0.3.0 + v0.4.0 + v0.5.0）全部完成后，发现对话中口头列出的 P1（9 个候选）+ P2（6 个候选）理论借鉴清单**没有持久化到任何文档**——这意味着未来会话切换后清单可能丢失。

Bisen 指出此风险后立即补救。

## 核心决策

### 1. 借鉴路线图存放位置

`theoretical-foundations/README.md` 作为子目录 SSOT——与 [shared-cognitive-science-toolbox.md](../research/30-shared-cognitive-tools/shared-cognitive-science-toolbox.md)（共享工具箱）平级。

理由：
- 共享工具箱是与 SelfLab 共享的 7 个认知科学工具
- 理论借鉴是 ECOS 独有的教育特定理论（心理测量、教学法、概念建构）
- 两者**互补**而非重复

### 2. P1/P2 借鉴的触发条件

**P1/P2 不是按编号顺序写**——而是**工程层实施过程中遇到具体 gap 时按需写**。

例子：
- 工程层写 LCA 干预选择时发现需要 Contextual Bandits → 写 P1.8
- 工程层写 CTA C 维度时发现需要 Schema Theory → 写 P1.2

这避免了"为了完整性凭空写文档"的问题——P1/P2 的真正价值在于"工程实现需要时立即可查"。

### 3. 新增理论的评估流程

当未来发现"应该吸收但未列"的理论时：
1. **先在 README 评估档位**（P0/P1/P2）
2. **再决定是否写**
3. **避免"P0 应该吸收但被忽略"的盲点**

### 4. P0 借鉴保持现状

v0.3.0 + v0.4.0 + v0.5.0 全部完成，无需修订。

## 借鉴路线图（README 已固化）

```
P0（全部完成）:
  ✅ v0.3.0 CTA 数学基础（5 层数学栈）
  ✅ v0.4.0 LCA 教学法基础（3 大理论群）
  ✅ v0.5.0 C 维度内容库（TC + Misconceptions 双轨）

P1（待写，9 个）:
  P1.1 Self-Regulated Learning (Zimmerman)
  P1.2 Schema Theory (Bartlett/Rumelhart)
  P1.3 Working Memory Model (Baddeley)
  P1.4 Conceptual Graphs + Ontology Engineering
  P1.5 Mastery Learning (Bloom, 1968)
  P1.6 Assessment for Learning (Black & Wiliam)
  P1.7 DINA / DINO / Rule Space / Fusion Model
  P1.8 Contextual Bandits
  P1.9 Cognitive Apprenticeship 完整版（深化 v0.4.0）

P2（待写，6 个）:
  P2.1 Piaget 认知发展阶段论
  P2.2 Transfer of Learning
  P2.3 EDM / Learning Analytics
  P2.4 Knowledge Space Theory
  P2.5 Enactivism / 自生理论
  P2.6 东方教育哲学

不吸收护栏（7 类）:
  ❌ 深度现象学 / 神经科学细节 / 婴幼儿认知 / 特殊教育 / 
     Embodied Cognition 完整 / 多 Agent 教学系统 / 行为主义
```

## 产出文件

| 文件 | 角色 | 行数 |
|---|---|---|
| `research/30-shared-cognitive-tools/theoretical-foundations/README.md` | **主文档**——理论借鉴路线图 SSOT | ~280 |
| `research/README.md`（更新）| SSOT 入口加 theoretical-foundations/ 引用 + P0/P1/P2 摘要 | — |
| `CHANGELOG.md`（更新）| 升级到 v0.6.0 | — |
| `discussions/2026-06-24-ecos-theoretical-roadmap.md` | **本文件**——本次会话简要记录 | ~100 |

## 关联文档

- [README.md](../../README.md) — ECOS 项目入口
- [CHANGELOG.md](../../CHANGELOG.md) — 变更日志（v0.6.0）
- [research/README.md](../../research/README.md) — Research SSOT 入口（已更新）
- [research/30-shared-cognitive-tools/theoretical-foundations/README.md](../../research/30-shared-cognitive-tools/theoretical-foundations/README.md) — 本次主产出
- [research/30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md](../../research/30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md) — P0-1
- [research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md](../../research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md) — P0-2
- [research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md](../../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md) — P0-3

## 下一步

回到主线（项目任务 P0 战略层）：
- **P0**：`02-architecture.md`（整体架构——整合 P0 三件套到架构）
- **P0**：`03-roadmap.md`（阶段划分）
- **P0**：`04-risks.md`（风险矩阵）

理论借鉴 P1/P2 留待工程层实施过程中按需触发。

---

**创建日期**：2026-06-24
**维护者**：Bisen & Claude
**版本**：v0.6.0
