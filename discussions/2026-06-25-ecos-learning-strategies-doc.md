# 2026-06-25 · 学习策略空间教学法文档（v0.17.0，教学法层第 3 份）

## 主题

完成教学法层第 3 份文档 `research/20-pedagogy/03-learning-strategies.md`（v1.0，575 行），定义 ECOS 应该向学生推荐的学习策略 + Bloom 层级 + 学科 + LearningDNA 匹配。

## 日期

2026-06-25

## 背景

教学法层第 3 份——基于：
- [01-k12-cognitive-structure.md](01-k12-cognitive-structure.md)（学段差异化）
- [02-bloom-application.md](02-bloom-application.md)（Bloom 跨层级策略）
- [v0.4.0 LCA 教学法基础（CLT + Bjork + CA）](../../research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md)
- [02-lca-policy-engine.md §2 Intervention 数据结构](../research/10-engineering/02-lca-policy-engine.md)
- 经典学习策略研究：Pintrich 1990 / Weinstein 1986 / Polya 1945

## 文档结构（12 章节）

| 章节 | 内容 |
|---|---|
| §0 | 模块定位 + 经典分类（Pintrich 1990）|
| §1 | 认知策略（复述 + 精细加工 + 组织）|
| §2 | 元认知策略（计划 + 监控 + 调节）|
| §3 | 资源管理策略（时间 + 环境 + 努力 + 帮助）|
| §4 | 学科特定策略（数学/语文/英语/物理）|
| §5 | ECOS 5 类干预 × 学习策略对应 |
| §6 | Bloom 层级 × 学习策略映射 |
| §7 | LearningDNA 匹配（5 维个性化）|
| §8 | 学习策略效果归因（与 CTA L4 整合）|
| §9 | 反馈循环 + 个性化推荐 |
| §10-12 | 评估指标 + 关联文档 + 版本维护 |

## 核心内容

### 1. 经典学习策略分类

| 大类 | 子类 | 描述 |
|---|---|---|
| **认知策略** | 复述 | 重复记忆 |
| | 精细加工 | 联想、类比、自我解释 |
| | 组织 | 归纳、做笔记、思维导图 |
| **元认知策略** | 计划 | 目标 + 时间表 |
| | 监控 | 自我评估 + 错误检测 |
| | 调节 | 调整策略 + 寻求帮助 |
| **资源管理策略** | 时间 + 环境 + 努力 + 寻求帮助 | — |

### 2. ECOS 5 类干预 × 学习策略

| ECOS 干预 | 主要策略 | 适用 Bloom |
|---|---|---|
| EXPLANATORY | 精细加工（类比）| L2-L3 |
| PRACTICE | 复述 + 变式 | L1-L3 |
| INQUIRY | 组织 + 元认知监控 | L3-L4 |
| FEEDBACK | 元认知调节 + 错误分析 | L1-L4 |
| METACOGNITIVE | 元认知 + Articulation | L4-L6 |

### 3. 关键 effect size（Weinstein 1986）

| 策略 | effect size |
|---|---|
| 精细加工 | 0.65-0.85 ⭐ |
| 自我解释（Chi）| 30% 增益 |
| 复述 | 0.20-0.35 |

**关键洞察**：精细加工 effect size 远高于复述。ECOS 应主动推荐精细加工（替代中国学生偏好的纯复述）。

### 4. 中国 K12 特殊考量

[04-risks.md §C2 文化适配](../research/00-overview/04-risks.md)：
- 中国学生偏好：复述 + 题海（低 Bloom 高负荷）
- ECOS 主动引导：精细加工 + 元认知 ≥ 50%
- 渐进引入（保留中国家长熟悉的"刷题"元素）

### 5. LearningDNA 匹配（个性化）

| LearningDNA 维度 | 匹配策略 |
|---|---|
| 视觉 | 思维导图 + 表格 |
| 听觉 | 朗读 + 听写 |
| 动觉 | 实际操作 |
| 即时反馈 | FEEDBACK 立即 |
| 延迟反馈 | FEEDBACK 延迟 |
| 高动机 | INQUIRY 探究 |
| 低动机 | 游戏化 + 即时 |

## 关键决策

| 决策 | 选择 |
|---|---|
| 学习策略分类 | Pintrich 1990 |
| 精细加工权重 | ≥ 50% |
| 元认知策略 | 与 CA Stage 4-5 整合 |
| 效果归因 | 与 CTA L4 Causal Inference 整合 |
| 中国 K12 | 渐进引入精细加工 |

## Phase 0 进度

| 维度 | 状态 | 完成度 |
|---|---|---|
| 战略层 | ✅ 100% | 4/4 |
| 工程层 | ✅ 100% | 5/5 |
| **教学法层** | **75%** | **3/4** |
| MVP 设计 | ⏳ 0% | 0/1 |
| **总完成度** | **~96%** | **13/14** |

## 累计产出（v0.1.0 ~ v0.17.0）

- **17 个版本**
- **~16700 行**研究文档

## 产出文件

| 文件 | 角色 | 行数 |
|---|---|---|
| `research/20-pedagogy/03-learning-strategies.md` | **主文档**——学习策略空间（v1.0，12 章节）| 575 |
| `discussions/2026-06-25-ecos-learning-strategies-doc.md` | **本文件**——本次会话简要记录 | ~110 |
| `CHANGELOG.md` | 升级到 v0.17.0 | — |

## 关联文档

- [README.md](../../README.md) — ECOS 项目入口
- [CHANGELOG.md](../../CHANGELOG.md) — 变更日志（v0.17.0）
- [research/20-pedagogy/03-learning-strategies.md](../../research/20-pedagogy/03-learning-strategies.md) — 本次主产出
- [research/20-pedagogy/02-bloom-application.md](../../research/20-pedagogy/02-bloom-application.md) — 上份文档

## 下一步

教学法层剩 1 份：
- **04-zpd-application.md**（ZPD 在 ECOS 的应用）

然后是 MVP 设计（90-mvp/）——Phase 0 最后 1 份。

---

**创建日期**：2026-06-25
**维护者**：Bisen & Claude
**版本**：v0.17.0（教学法层第 3 份）
