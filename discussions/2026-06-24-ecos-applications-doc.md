# 2026-06-24 · ECOS 应用场景战略文档撰写

## 主题

完成 ECOS 战略层第 1 份文档 `research/00-overview/01-applications.md`（v1.0），定义 ECOS 的应用场景、目标用户、核心能力边界与 MVP 范围。

## 日期

2026-06-24

## 背景

ECOS v0.1.0 项目初始建立后，战略层 4 份文档按依赖链（applications → architecture → roadmap → risks）依次填充。本文档是第 1 份，回答"ECOS 为谁做什么不做什么"。

## 核心决策

### 1. ECOS 的"第四代"定位

承接 v0.1 综合报告 §第一部分的"三代教育系统演进"框架（第一代内容教育 → 第二代自适应学习 → 第三代 AI Tutor），明确 ECOS 是"第四代——理解学生并帮助成长的系统"。不是更好的"会答问题的老师"，而是 v0.1 §第二部分 的 A→B 闭环系统（学生现在是谁 → 应该成长成什么样 → 如何帮助其成长）。

### 2. 三大核心定位关键词（缺一不可）

- **科学化认知估计**（CTA 用贝叶斯/IRT/BKT/DKT 等心理测量学方法）
- **自适应干预**（LCA 基于 CTA 状态选择最优干预）
- **长期认知陪伴**（持续 6~12 年维护学生画像/轨迹/学习基因）

### 3. 目标用户三角

- **主**：K12 学生（小学高年级 ~ 高中）
- **次**：教师（每周 1-3 次阶段性查阅）
- **辅**：家长（每月 1-4 次接收成长报告）

**核心原则**：产品形态以学生端为主，教师/家长端为辅；不可本末倒置。

### 4. 四大核心应用场景

| 场景 | 核心 ECOS 能力 | MVP 范围 |
|---|---|---|
| A 学科诊断 | CTA 5D 信念分布 + BloomProfile | ✅ 必含 |
| B 自适应干预 | LCA 策略优化 + 双 Agent 互校 | ✅ 必含 |
| C 长期成长轨迹 | 5D 轨迹 + BloomProfile 演化 + LearningDNA | ⚠️ 仅学期内 |
| D 教师/家长协作 | CTA 信念可解释性输出 | ❌ 不含 |

### 5. 9 项"不做"边界（明确护栏）

不做的清单（重要程度等同于"做什么"）：

- ❌ 内容生产 / 题库生成
- ❌ 学科覆盖广度（Phase 4 仅初中数学）
- ❌ 实时直播课 / 教师备课工具
- ❌ 家长社交 / 通识兴趣教育
- ❌ 成人教育（考研/职业培训）
- ❌ 情感陪伴（不做心理健康）

每一条都对应一个"避免方向漂移的护栏"。

### 6. 差异化总图（市场定位）

用两个轴定义 ECOS 在 AI 教育市场的位置：
- X 轴：是否理解学生（CTA）
- Y 轴：是否改变学生（LCA）

ECOS 在两个轴上都达到"是"——目前市场上没有竞品同时做到。

## 产出文件

| 文件 | 角色 | 行数 |
|---|---|---|
| `research/00-overview/01-applications.md` | **主文档**——应用场景战略文档（v1.0，10 章节）| ~350 |
| `discussions/2026-06-24-ecos-applications-doc.md` | **本文件**——本次会话简要记录 | ~80 |
| `CHANGELOG.md` | 更新到 v0.2.0（次版本递增）| — |

## 关键引用来源

- [v2.0 深度研究 §执行摘要](../research/deep-research/Cognitive-Digital-Twin-Deep-Research.md) — ECOS 整体定位
- [v2.0 深度研究 §3.3 CTA](../research/deep-research/Cognitive-Digital-Twin-Deep-Research.md) — 状态估计器细节
- [v2.0 深度研究 §3.4 LCA](../research/deep-research/Cognitive-Digital-Twin-Deep-Research.md) — 策略优化器细节
- [v2.0 深度研究 §3.5 双 Agent 互校](../research/deep-research/Cognitive-Digital-Twin-Deep-Research.md) — 互校机制
- [v0.1 综合报告 §第一部分](../research/gpt-dialogues/04-cognitive-digital-twin-v01-report.md) — 三代教育系统框架
- [v0.1 综合报告 §第四部分](../research/gpt-dialogues/04-cognitive-digital-twin-v01-report.md) — 5D 状态模型
- [v0.1 综合报告 §第五部分](../research/gpt-dialogues/04-cognitive-digital-twin-v01-report.md) — LearningDNA
- [v0.1 综合报告 §第六部分](../research/gpt-dialogues/04-cognitive-digital-twin-v01-report.md) — 双 Agent 闭环
- [v0.1 综合报告 §第十部分](../research/gpt-dialogues/04-cognitive-digital-twin-v01-report.md) — 成长轨迹

## 关联文档

- [README.md](../../README.md) — ECOS 项目入口
- [CHANGELOG.md](../../CHANGELOG.md) — 变更日志（v0.2.0）
- [research/README.md](../../research/README.md) — Research SSOT 入口
- [research/00-overview/01-applications.md](../../research/00-overview/01-applications.md) — 本次主产出
- [research/MIGRATION-FROM-SELFLAB.md](../../research/MIGRATION-FROM-SELFLAB.md) — 上一份文档

## 下一步

按战略层依赖链：02-architecture.md（整体架构）→ 03-roadmap.md（路线图）→ 04-risks.md（风险矩阵）→ 进入工程层（10-engineering/）。

---

**创建日期**：2026-06-24
**维护者**：Bisen & Claude
**版本**：v0.2.0
