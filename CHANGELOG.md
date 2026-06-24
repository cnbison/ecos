# ECOS 变更日志

本文件记录 ECOS 项目的重要变更：文档版本、研究进展、架构调整、关键决策。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

## 版本号约定

- **主版本（major）**：0（项目仍处研究阶段）
- **次版本（minor）**：0.x —— x 每次内容增删改递增
- **修订号（patch）**：0.x.y —— y 用于小修正（错别字、链接失效等）
- **批次标签**：P0（必须修正）→ P1（建议修正）→ P2（可后续）→ P3（优化）

## 提交索引

| 版本 | 日期 | commit hash | 主要内容 |
|------|------|-------------|----------|
| 0.1.0 | 2026-06-24 | f5eeea0 | **项目初始建立**：从 SelfLab 迁移 5 份核心研究文档（5 轮 GPT 对话 + 深度研究 v2.0）+ 5 份选择性参考文档（共享工具箱 + 认知架构综述 + AiBeing 借鉴 + 借鉴分析）+ 14 个研究维度占位文件（00-overview/10-engineering/20-pedagogy/90-mvp）+ ecos/ Python 包骨架（9 个 __init__.py 占位 + llm_client.py + orchestrator.py）+ 完整项目级文档（README/CLAUDE/CHANGELOG/LICENSE/pyproject.toml/.gitignore/.env.example）|
| 0.2.0 | 2026-06-24 | 954e6ab | **战略层第 1 份文档**：research/00-overview/01-applications.md（v1.0，10 章节：起点/定位/用户三角/4 大核心场景/跨场景能力/不做清单/MVP 范围/差异化总图/关联/版本；明确学科诊断 + 自适应干预 + 长期成长轨迹 + 教师家长协作 4 大场景；7 项跨场景核心能力清单；9 项不做边界护栏；MVP 场景对应表）+ research/MIGRATION-FROM-SELFLAB.md（项目元文档）+ discussions/2026-06-24-ecos-migration-overview.md + discussions/2026-06-24-ecos-applications-doc.md（会话记录）|
| 0.3.0 | 2026-06-24 | c13e913 | **P0 第 1 份借鉴文档**：research/30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md（v1.0，451 行，CTA 数学基础：L0 POMDP/HMM + L1 BKT/DKT + L2 MIRT + L3 CD-CAT + L4 Causal Inference 5 层数学栈；填补 v2.0 §3.3 "只提名字"gap；含与 LLM 关系 + 与 LCA 接口 + MVP 实施路线）+ discussions/2026-06-24-ecos-cta-math-foundations.md（会话记录）|
| 0.4.0 | 2026-06-24 | ea8d72a | **P0 第 2 份借鉴文档**：research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md（v1.0，420 行，LCA 教学法基础：Cognitive Load Theory + Bjork 四件套 + Cognitive Apprenticeship；填补 v2.0 §3.4 "有策略列表无理论论证"gap；含 5 类干预 × 教学法对应表 + 与 POMDP 决策接口 + 与 CTA 因果归因闭环 + 与竞品差异表）+ discussions/2026-06-24-ecos-lca-instructional-foundations.md（会话记录）|
| 0.5.0 | 2026-06-24 | eff50d9 | **P0 第 3 份借鉴文档**：research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md（v1.0，414 行，C 维度内容库：Threshold Concepts + Misconceptions Research 双轨内容库；填补 v2.0 §3.3 "C 维度是抽象置信度"gap；含 liminal 状态识别 + 与 Q 矩阵集成 + 与 LCA 教学法整合 + MVP 候选 8 个 TC + 10 个 misconception）+ **P0 三件套完成**（CTA 数学基础 + LCA 教学法基础 + C 维度内容库）+ discussions/2026-06-24-ecos-c-dim-content-libraries.md（会话记录）|
| 0.6.0 | 2026-06-24 | 1e2ab64 | **理论借鉴路线图 SSOT**：research/30-shared-cognitive-tools/theoretical-foundations/README.md（v1.0，子目录 SSOT：P0 已完 3 份 + P1 待写 9 候选 + P2 待写 6 候选 + 借鉴档位判断标准 + 不吸收护栏 7 类）+ 更新 research/README.md（SSOT 入口加 theoretical-foundations/ 引用与 P0/P1/P2 摘要）|
| 0.7.0 | 2026-06-25 | (本次) | **战略层第 2 份文档**：research/00-overview/02-architecture.md（v1.0，703 行，11 章节，整体架构——整合 P0 三件套到 ECOS 架构总图：三层视角 ASCII 图 + 三空间架构 + 双 Agent 详细架构 + 完整数据流 + 状态估计工程实现 + 干预策略工程实现 + 双 Agent 互校机制 + 持久化 + MVP 架构范围 + 与 v2.0 §3 关系表）+ discussions/2026-06-25-ecos-architecture-doc.md（会话记录）|

---

## [0.1.0] - 2026-06-24 (ECOS 项目初始建立)

### 背景

Bisen 在前面对话中判断：学生数字孪生 + AI 学习教练为核心的下一代教育系统（ECOS）应作为与 SelfLab 并列的独立项目，而不是 SelfLab 的子项目。理由：
1. 避免散乱：SelfLab 已聚焦 SGE，ECOS 独立避免目录结构复杂
2. 独立发展：SGE 关注"AI 自我涌现"，ECOS 关注"教育认知操作系统"——研究目标、目标用户、技术栈都不同
3. 降低认知负担：研究者可在两个项目间清晰切换
4. 合作灵活：未来 ECOS 与教育机构合作时，独立项目身份更合适

本次操作：建立新项目 `/Users/loubicheng/project/ecos/`，从 SelfLab 复制 ECOS 相关文档。

### 新增

- **项目根级文件**：
  - `README.md` — 项目入口（含核心架构图、项目目标、与 SelfLab 关系、当前状态、下一步）
  - `CLAUDE.md` — Claude Code 协作指南（参照 SelfLab 风格但简化，移除 SGE/Phase 3 特定内容）
  - `LICENSE` — MIT License
  - `pyproject.toml` — Python 包配置（包名 ecos，Python ≥ 3.11）
  - `.gitignore` — Python + macOS 通用
  - `.env.example` — LLM API key 示例

- **Python 包骨架**（`ecos/`）：
  - `__init__.py` — 包入口
  - `cta/__init__.py` — Cognitive Twin Agent 占位
  - `lca/__init__.py` — Learning Coach Agent 占位
  - `dual_agent/__init__.py` — 双 Agent 互校占位
  - `bloom/__init__.py` — Bloom Goal Library 占位
  - `persistence/__init__.py` — 学生状态持久化占位
  - `session/__init__.py` — 长期会话管理占位
  - `llm_client.py` — LLM 客户端占位
  - `orchestrator.py` — ECOSOrchestrator 占位

- **核心研究文档**（从 SelfLab 迁移）：
  - `research/README.md` — SSOT 入口
  - `research/deep-research/Cognitive-Digital-Twin-Deep-Research.md` — v2.0 深度研究（1778 行，6 部分 + 5 附录）
  - `research/gpt-dialogues/01-cognitive-state-a-to-b-research.md` — 7 页综合调研站点
  - `research/gpt-dialogues/02-cognitive-digital-twin-rounds-1-3.md` — 第 1-3 轮对话
  - `research/gpt-dialogues/03-cognitive-digital-twin-rounds-4-5.md` — 第 4-5 轮对话
  - `research/gpt-dialogues/04-cognitive-digital-twin-v01-report.md` — 5 轮综合 v0.1

- **战略层占位**（`research/00-overview/`）：
  - `01-applications.md` — 4 个应用场景占位
  - `02-architecture.md` — 双 Agent 架构占位
  - `03-roadmap.md` — 路线图占位
  - `04-risks.md` — 风险矩阵占位

- **工程层占位**（`research/10-engineering/`）：
  - `01-cta-belief-engine.md` — CTA 信念状态估计
  - `02-lca-policy-engine.md` — LCA 干预策略
  - `03-bloom-goal-library.md` — Bloom 目标库
  - `04-dual-agent-calibration.md` — 双 Agent 互校机制
  - `05-persistence-session.md` — 持久化与会话管理

- **教学法层占位**（`research/20-pedagogy/`）：
  - `01-k12-cognitive-structure.md` — K12 认知结构
  - `02-bloom-application.md` — Bloom 在 K12 的应用
  - `03-learning-strategies.md` — 学习策略空间
  - `04-zpd-application.md` — ZPD 在 ECOS 的应用

- **共享工具箱**（从 SelfLab 迁移，`research/30-shared-cognitive-tools/`）：
  - `shared-cognitive-science-toolbox.md` — 7 个认知科学工具（与 SelfLab 共享）

- **AiBeing 借鉴**（从 SelfLab 迁移，`research/40-aibeing-borrowing/`）：
  - `01-concept-borrowing.md` — 概念层借鉴（来自 `SGE-Learning-from-AiBeing.md`）
  - `02-application-layer-borrowing.md` — 应用层借鉴（来自 `sge-phase3-aibeing-reflection.md`）

- **MVP 实施占位**（`research/90-mvp/`）：
  - `README.md` — MVP 设计总览

- **参考资料**（从 SelfLab 迁移，`references/`）：
  - `cognitive-architectures-overview.md` — 8 个经典认知架构综述
  - `aibeing-core-engine-reference.md` — AiBeing 完整引擎参考

- **占位目录**：
  - `experiments/README.md` — Phase 4+ 一次性实验代码占位
  - `prototypes/README.md` — 架构原型占位

- **会话记录**（`discussions/`）：
  - `2026-06-24-ecos-project-establishment.md` — 项目建立会话记录

### 项目状态

- **Phase 0**（理论奠基）：🚧 进行中（项目刚建立）
- **Phase 4**（MVP 实施）：📋 待启动
- **Phase 5**（产品化）：📋 待启动
- **Phase 6**（系统完善）：📋 待启动

### 与 SelfLab 的关系

- 兄弟项目（与 SelfLab 并列，非子项目）
- 共享基础：7 个认知科学工具（贝叶斯、记忆分层、预测加工、双系统、BDI、元认知、经典架构）
- 不共享：SGE value/drive 机制（不适合建模"对学生的理解"）
- SGE 可作为 ECOS 的"教师侧人格引擎"（LCA 内在人格由 SGE 提供）

### 下一步

| 优先级 | 任务 | 详见 |
|--------|------|------|
| P0 | 战略层 4 份文档填充 | `research/00-overview/` |
| P0 | 工程层关键模块设计 | `research/10-engineering/` |
| P1 | 教学法层 K12 认知结构 | `research/20-pedagogy/` |
| P1 | MVP 设计（初中数学 + 50-100 学生）| `research/90-mvp/` |
| P2 | Python 包实现（CTA + LCA 基础类）| `ecos/` |

---

## [0.2.0] - 2026-06-24 (战略层第 1 份文档：应用场景)

### 背景

ECOS 战略层 4 份文档按依赖链依次填充（applications → architecture → roadmap → risks）。本文档为第 1 份，回答"ECOS 为谁做什么不做什么"，基于 v2.0 深度研究与 v0.1 综合报告整合而成。

### 新增

- **research/00-overview/01-applications.md**（v1.0，约 350 行）
  - 10 章节：起点（三代教育系统局限）/ 核心定位 / 用户三角 / 4 大核心场景 / 跨场景核心能力 / 不做清单 / MVP 范围 / 差异化总图 / 关联 / 版本
  - **4 大核心应用场景**：
    - A 学科诊断（CTA 5D 信念分布 + BloomProfile）
    - B 自适应干预（LCA 策略优化 + 双 Agent 互校）
    - C 长期成长轨迹（5D 轨迹 + BloomProfile 演化 + LearningDNA 稳定性）
    - D 教师/家长协作（CTA 信念可解释性输出）
  - **目标用户三角**：K12 学生（主）+ 教师（次）+ 家长（辅）
  - **7 项跨场景核心能力清单**：CTA / LCA / 互校 / Bloom / LearningDNA / 持久化 / 可解释性
  - **9 项不做边界**：内容生产 / 题库生成 / 学科广度 / 直播课 / 教师备课 / 家长社交 / 通识兴趣 / 成人教育 / 情感陪伴
  - **MVP 范围**：A+B 必含 + C 仅学期内 + D 不含
- **discussions/2026-06-24-ecos-applications-doc.md**：本次会话简要记录

### 关键决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 用户优先级 | 学生为主、教师为次、家长为辅 | 不可本末倒置（不能让家长端成为日常入口） |
| MVP 学科 | 初中数学（代数 + 几何）| K12 学科差异巨大，必须先在一个学科验证 |
| MVP 学生规模 | 50-100 学生（沿用 v2.0 定义）| 既验证 CTA/LCA 有效性，又控制实验成本 |
| Phase 5 拓展 | 高中数学 + 初中物理 | 数学/物理是 CTA 5D 状态建模最成熟的学科 |
| 教师/家长端 | Phase 5 之前不做 | MVP 阶段仅学生端，避免 UX 复杂度爆炸 |

### 项目状态

- Phase 0（理论奠基）：🚧 进行中
- 战略层进度：4 份中 1 份完成（25%）
- 工程层进度：5 份中 0 份（占位）
- 教学法层进度：4 份中 0 份（占位）
- MVP 设计：📋 仅 README 占位

### 下一步

| 优先级 | 任务 | 详见 |
|--------|------|------|
| **P0** | 战略层 02-architecture.md（整体架构）| `research/00-overview/` |
| **P0** | 战略层 03-roadmap.md（阶段划分）| `research/00-overview/` |
| P0 | 战略层 04-risks.md（风险矩阵）| `research/00-overview/` |
| P0 | 工程层关键模块设计（CTA + LCA + Bloom + 互校）| `research/10-engineering/` |

---

## [0.4.0] - 2026-06-24 (P0 第 2 份借鉴：LCA 教学法基础)

### 背景

[v2.0 深度研究 §3.4](../research/deep-research/Cognitive-Digital-Twin-Deep-Research.md) 已给出 LCA 的"干预空间"——按 Bloom 层级分类的策略字典（flashcard / worked_examples / socratic_questioning 等），但**没有教学法理论论证**。本次借鉴 3 大核心理论群，建立 LCA 干预策略的**教学法基础**。

### 新增

- **`research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md`**（v1.0，420 行）
  - **3 大核心理论群**：
    - **Cognitive Load Theory (Sweller, 1988; 2019)** —— 三类负荷（Intrinsic / Extraneous / Germane）+ worked example effect + split-attention effect + expertise reversal effect
    - **Bjork 学派四件套**（合意困难）：
      - Testing Effect (Roediger & Karpicke, 2006) — 主动提取 > 被动重读
      - Desirable Difficulties (Bjork & Bjork, 1992, 2011) — 教学性合意 vs 环境性不合意
      - Spacing Effect (Ebbinghaus, 1885 / Cepeda, 2006) — 间隔 vs 集中练习
      - Interleaving (Rohrer & Taylor, 2007) — 交错练习 vs 集中练习
    - **Cognitive Apprenticeship** (Collins, Brown & Newman, 1989) — 6 阶段：Modeling → Coaching → Scaffolding → Articulation → Reflection → Exploration
  - 整合：LCA 干预决策完整算法栈（CTA L0-L2 + LCA L3-L4）+ 5 类干预 × 教学法对应表 + 参数化空间（4 维 + 5 离散）+ POMDP 接口 + 与 CTA 因果归因闭环
  - 与竞品差异表：ECOS 是**唯一**把教学法理论显式编码到 AI 系统中的产品
  - MVP 实施路线：CLT 基础 + Bjork 双件套 + Cognitive Apprenticeship Stage 1-3（Phase 4）→ 完整 Bjork + Stage 4-6 + 因果归因（Phase 5）→ POMDP + POMCP + 个性化认知学徒制（Phase 6）
- **`discussions/2026-06-24-ecos-lca-instructional-foundations.md`**（本次会话记录）

### 关键决策

| 决策项 | 选择 | 理由 |
|---|---|---|
| **MIRT 形式**（沿用 v0.3.0）| 非补偿型（Bi-factor MIRT）| 避免"伪掌握" |
| **CLT 呈现方式** | 4 级自适应（新手/进阶/熟练/专家）| expertise reversal effect 自动化 |
| **Bjork 优先级** | MVP：测试效应 + 间隔；Phase 5+：合意困难 + 交错 | MVP 简化实施 |
| **Cognitive Apprenticeship 6 阶段** | 全部支持，但 LCA 在后台判断阶段 | 不让 UI 强制 6 步骤流程 |
| **Scaffolding 衰减** | 连续 N 次成功后自动撤走（CTA 触发）| expertise reversal 自动化 |
| **数学层不用 LLM**（沿用 v0.3.0）| ❌ 否（硬底线）| 任何 LLM 直接生成干预策略都是退路 |

### 完整 L0-L4 算法栈（v0.3.0 + v0.4.0 整合）

```
L4 LCA 策略优化层        Cognitive Apprenticeship 6 阶段框架（LCA 决策）
L3 LCA 干预类型选择层    Bjork 四件套 + CLT（LCA 决策）
L2 状态估计层（CTA）     MIRT + CD-CAT（CTA 估计）
L1 时间演化层（CTA）     BKT/DKT + Spaced Repetition（CTA 估计 + LCA 触发）
L0 概率框架层（CTA）     POMDP / HMM（CTA 估计）
```

### 下一步

| 优先级 | 任务 | 详见 |
|---|---|---|
| **P0** | `03-c-dimension-content-libraries.md`（C 维度内容库）| `theoretical-foundations/` |
| P0 | 战略层 02-architecture.md（整体架构）| `research/00-overview/` |
| P0 | 战略层 03-roadmap.md（阶段划分）| `research/00-overview/` |
| P0 | 战略层 04-risks.md（风险矩阵）| `research/00-overview/` |

---

## [0.3.0] - 2026-06-24 (P0 第 1 份借鉴：CTA 数学基础)

### 背景

[v2.0 深度研究 §3.3](../research/deep-research/Cognitive-Digital-Twin-Deep-Research.md) 把 CTA 定义为 "State Estimator"，但只提到 IRT/BKT/DKT 等心理测量学方法**名字**，未给出具体算法框架。本次借鉴 5 个核心理论，填补这一 gap，建立 CTA 信念分布的 **L0→L4 数学栈**。

### 新增

- **`research/30-shared-cognitive-tools/theoretical-foundations/`**（新子目录，ECOS 独有理论借鉴）
- **`01-cta-mathematical-foundations.md`**（v1.0，451 行）
  - **5 个核心理论**构成 L0→L4 数学栈：
    - **L0 POMDP / HMM**（统一概率框架）
    - **L1 BKT / DKT**（单知识点时间演化）
    - **L2 MIRT**（5D 多维联合估计）
    - **L3 CD-CAT**（自适应选择）
    - **L4 Causal Inference**（干预归因）
  - 每理论含：**核心观点 / 与 ECOS CTA 对接 / 借鉴决策 / 实施注意事项**
  - 整合章节：CTA 信念分布完整数学框架（含与 LLM 关系 + 与 LCA 接口）
  - MVP 实施路线：**BKT + MIRT + 简化 CD-CAT**（Phase 4）→ POMDP + Causal Forest（Phase 5）→ DKT/DKVMN + POMCP（Phase 6）
  - 关键开源依赖：pyBKT, mirt, GDINA, DoWhy, pgmpy
- **`discussions/2026-06-24-ecos-cta-math-foundations.md`**（本次会话记录）

### 关键决策

| 决策项 | 选择 | 理由 |
|---|---|---|
| MIRT 形式 | 非补偿型（Bi-factor MIRT）| 避免"伪掌握"（K 弱 P 强被误判掌握）|
| CD-CAT 算法 | GDINA + PWKL 选题 | DINA 最一般化扩展 + 兼顾信息量与诊断明确性 |
| BKT 算法 | 经典 4 参数（MVP）| 简单可解释，Phase 5+ 升级 DKT/DKVMN |
| POMDP 求解 | 扩展卡尔曼滤波（EKF）+ 离散属性精确推断 | 工程可行，性能可接受 |
| 因果框架 | DoWhy + Causal Forest | 处理高维协变量 + 异质性处理 |
| **数学层是否用 LLM** | **❌ 否（硬底线）**| 任何让 LLM 直接生成信念估计的设计都是退路 |

### MVP 实施路线

```
Phase 4（MVP）：BKT（4 参数）+ MIRT（5D 非补偿）+ 简化 CD-CAT（GDINA 基础）
Phase 5（产品化）：POMDP 整合（LCA 决策统一接口）+ Causal Forest 归因
Phase 6（系统完善）：DKT/DKVMN 跨知识点关联 + 完全 POMCP
```

### 下一步

| 优先级 | 任务 | 详见 |
|---|---|---|
| **P0** | `02-lca-instructional-foundations.md`（LCA 教学法基础）| `theoretical-foundations/` |
| **P0** | `03-c-dimension-content-libraries.md`（C 维度内容库）| `theoretical-foundations/` |
| P0 | 战略层 02-architecture.md（整体架构）| `research/00-overview/` |
| P0 | 战略层 03-roadmap.md（阶段划分）| `research/00-overview/` |
| P0 | 战略层 04-risks.md（风险矩阵）| `research/00-overview/` |

---

## [0.5.0] - 2026-06-24 (P0 第 3 份借鉴 + P0 三件套全部完成)

### 背景

[v0.1 综合报告 §第四部分](../research/gpt-dialogues/04-cognitive-digital-twin-v01-report.md) 把 CTA 5D 中的 C 维度定义为"认知置信度（Confidence）"，[v2.0 §3.3](../research/deep-research/Cognitive-Digital-Twin-Deep-Research.md) 沿用为 ConfidenceState。但**没有给出 C 维度的科学评估基础**——CTA 不知道"伪置信"如何识别、不知道"liminal 状态"如何处理。

本次借鉴 2 大内容库，让 C 维度从抽象"confidence"变为可科学评估的维度。

### P0 三件套全部完成

```
v0.3.0  CTA 数学基础        (5 层数学栈)            ✅
v0.4.0  LCA 教学法基础      (3 大理论群)            ✅
v0.5.0  C 维度内容库         (TC + Misconceptions 双轨) ✅
─────────────────────────────────────────────────
P0 借鉴全部完成（v0.3.0 + v0.4.0 + v0.5.0）
```

**v0.3.0 + v0.4.0 + v0.5.0 共同填补 v2.0 §3.3-3.4 的全部 gap**：
- §3.3 "只提名字（IRT/BKT/DKT）" → v0.3.0 5 层数学栈
- §3.4 "有策略列表无理论论证" → v0.4.0 3 大教学法理论群
- §3.3 "C 维度是抽象置信度" → v0.5.0 TC + Misconceptions 双轨

### 新增

- **`research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md`**（v1.0，414 行）
  - **2 大内容库**：
    - **Threshold Concepts** (Meyer & Land, 2003) —— 5 特征（Transformative / Irreversible / Integrative / Bounded / Troublesome）+ Liminality 中间态 + MVP 候选 8 个初中数学 TC
    - **Misconceptions** (Driver, 1980s-; Chi, 1992) —— 三分类 + 经典案例库（数学/物理/生物）+ MVP 候选 10 条初中数学 misconception
  - 双轨内容库总览：正向骨架（TC）+ 反向补丁（Misconceptions）
  - 与 [Q 矩阵（CD-CAT）](../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md) 集成：每个题目标注考察属性 + TC + Misconception + Bloom 层级
  - CTA C 维度评估的具体算法（整合 BKT + LLM Critic + TC 检测 + POMDP）
  - 与 [LCA 教学法基础](../30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md) 整合：liminal 状态触发 CLT worked example，misconception 触发 Bjork 测试效应
- **`discussions/2026-06-24-ecos-c-dim-content-libraries.md`**（本次会话记录）

### 关键决策

| 决策项 | 选择 | 理由 |
|---|---|---|
| **TC 库规模** | MVP：5-8 个（初中数学）；Phase 5+：15-20 个（高中 + 物理）| 80/20 原则 |
| **Misconception 库规模** | MVP：30-50 条；Phase 5+：100-150 条 | 学术文献覆盖度优先 |
| **TC 库构建** | 教师 + CTA 联合（教师提候选，CTA 验证）| 学术权威 + 数据驱动 |
| **Misconception 检测** | LLM Critic + 关键词匹配（hybrid）| LLM 灵活 + 关键词精确 |
| **Liminal 状态识别** | 启发式 + 元认知信号（MVP）；ML（Phase 6）| MVP 简化 |
| **TC 不可逆性建模** | post-liminal C 维度永不下降（除非遗忘整个学科）| 体现 TC 特征 |
| **数学层不用 LLM**（沿用）| ❌ 否（硬底线）| TC 和 Misconception 检测可用 LLM，信念估计不用 |

### P0 三件套整合：CTA + LCA + C 维度完整图

```
┌────────────────────────────────────────────────────────────────────┐
│ L4 LCA 策略优化层        Cognitive Apprenticeship 6 阶段框架       │
│ L3 LCA 干预类型选择层    Bjork 四件套 + CLT                       │
├────────────────────────────────────────────────────────────────────┤
│ L2 状态估计层（CTA）     MIRT + CD-CAT（含 TC + Misconception 标注）│
│ L1 时间演化层（CTA）     BKT/DKT + Spaced Repetition              │
│ L0 概率框架层（CTA）     POMDP / HMM                              │
│ L0.5 内容基础层          Threshold Concepts + Misconceptions 库   │
│                            （v0.5.0 新增）                         │
└────────────────────────────────────────────────────────────────────┘
```

### 下一步

| 优先级 | 任务 | 详见 |
|---|---|---|
| **P0** | 战略层 02-architecture.md（整体架构——整合 P0 三件套到架构）| `research/00-overview/` |
| **P0** | 战略层 03-roadmap.md（阶段划分）| `research/00-overview/` |
| **P0** | 战略层 04-risks.md（风险矩阵）| `research/00-overview/` |
| P1 | 工程层 5 份文档（10-engineering/）| `research/10-engineering/` |
| P1 | 教学法层 4 份文档（20-pedagogy/）| `research/20-pedagogy/` |
| P1 | MVP 设计（90-mvp/）| `research/90-mvp/` |
| P2 | `ecos/` Python 包实现 | `ecos/` |

---

## [0.6.0] - 2026-06-24 (理论借鉴路线图 SSOT)

### 背景

P0 三件套（v0.3.0 + v0.4.0 + v0.5.0）全部完成后，发现对话中口头列出的 P1（9 个候选）+ P2（6 个候选）理论借鉴清单**没有持久化到任何文档**——这意味着未来会话切换后清单可能丢失。

Bisen 指出此风险后立即补救：本版本建立 `theoretical-foundations/` 子目录的 SSOT（README.md），明确记录 P0（已完）+ P1（待写）+ P2（待写）的完整借鉴路线图。

### 新增

- **`research/30-shared-cognitive-tools/theoretical-foundations/README.md`**（v1.0，新子目录 SSOT）
  - **P0（全部完成，3 份）**：CTA 数学基础 + LCA 教学法基础 + C 维度内容库
  - **P1（待写，9 个候选）**：
    1. Self-Regulated Learning (Zimmerman)
    2. Schema Theory (Bartlett/Rumelhart)
    3. Working Memory Model (Baddeley)
    4. Conceptual Graphs + Ontology Engineering
    5. Mastery Learning (Bloom, 1968)
    6. Assessment for Learning (Black & Wiliam)
    7. DINA / DINO / Rule Space / Fusion Model
    8. Contextual Bandits
    9. Cognitive Apprenticeship 完整版（深化 v0.4.0）
  - **P2（待写，6 个候选）**：
    1. Piaget 认知发展阶段论
    2. Transfer of Learning
    3. EDM / Learning Analytics
    4. Knowledge Space Theory
    5. Enactivism / 自生理论
    6. 东方教育哲学（孔子 / 王阳明 / 佐藤学）
  - **借鉴档位判断标准**：P0/P1/P2 的判定逻辑
  - **不吸收护栏**：7 类明确不吸收的理论（避免方向漂移）
  - **借鉴路线图**：P1/P2 不是按编号顺序写，而是**工程层实施过程中遇到具体 gap 时按需写**
- **更新 `research/README.md`**（SSOT 入口）：添加 `theoretical-foundations/` 子目录引用 + P0/P1/P2 借鉴清单摘要

### 关键决策

| 决策项 | 选择 | 理由 |
|---|---|---|
| **借鉴路线图存放位置** | `theoretical-foundations/README.md`（子目录 SSOT） | 与 [shared-cognitive-science-toolbox.md](../research/30-shared-cognitive-tools/shared-cognitive-science-toolbox.md)（共享工具箱）平级 |
| **P1/P2 借鉴触发条件** | 工程层实施中遇到具体 gap 时按需写 | 避免凭空写"为了完整性"的文档 |
| **新增理论评估流程** | 先在 README 评估档位，再决定是否写 | 避免"P0 应该吸收但被忽略"的盲点 |
| **P0 借鉴保持现状** | v0.3.0 + v0.4.0 + v0.5.0 全部完成，无需修订 | 已通过用户审查 |

### 不吸收护栏（明确列出）

避免 ECOS 偏离"科学化认知估计"方向：
- ❌ 深度现象学 / 金观涛真实性哲学
- ❌ 神经科学细节（fMRI/EEG）
- ❌ 婴幼儿认知发展
- ❌ 特殊教育专项（ADHD/自闭症）
- ❌ Embodied Cognition 完整理论
- ❌ 多 Agent 教学系统完整体系
- ❌ 行为主义学习理论

### 下一步

| 优先级 | 任务 | 详见 |
|---|---|---|
| **P0** | 战略层 02-architecture.md（整体架构——整合 P0 三件套到架构）| `research/00-overview/` |
| **P0** | 战略层 03-roadmap.md（阶段划分）| `research/00-overview/` |
| **P0** | 战略层 04-risks.md（风险矩阵）| `research/00-overview/` |
| P1 | 工程层 5 份（10-engineering/）| `research/10-engineering/` |
| P1 | 教学法层 4 份（20-pedagogy/）| `research/20-pedagogy/` |
| P1 | MVP 设计（90-mvp/）| `research/90-mvp/` |
| P2 | `ecos/` Python 包实现 | `ecos/` |
| 按需 | 理论借鉴 P1（工程实施遇 gap 时）| `theoretical-foundations/` |

---

## [0.7.0] - 2026-06-25 (战略层第 2 份文档：整体架构)

### 背景

战略层依赖链（01-applications.md → 02-architecture.md → 03-roadmap.md → 04-risks.md）的第 2 份。v2.0 §3 已给出 ECOS 架构骨架（Bloom Goal Space → LCA → CTA → Student），但**没有把 P0 三件套（CTA 数学基础 + LCA 教学法基础 + C 维度内容库）整合到工程实现层**。

本次完成架构文档，把 P0 三件套嵌入架构总图，明确每个组件的工程实现细节。

### 新增

- **`research/00-overview/02-architecture.md`**（v1.0，703 行，11 章节）
  - **§0 架构定位**：与 v2.0 §3 的关系——"补充 + 细化（不冲突）"
  - **§1 核心架构总图**（P0 三件套整合）：三层视角 ASCII 图（顶层三空间 + 中层双 Agent + 底层内容库）+ 4 大架构原则（数学层不用 LLM、LLM Critic 边界、双 Agent 解耦、内容库与算法解耦）
  - **§2 三空间架构**：State Space（5D + BloomProfile + LearningDNA + Trajectory 完整结构）+ Bloom Goal Space（6 层 K12 数学例子）+ Policy Space（5 类干预 × 4 参数 + Bloom 层选择）
  - **§3 双 Agent 详细架构**：CTA 5 层数学栈 + LCA 2 层教学法栈 + 双 Agent 互校机制（互校循环伪代码 + 3 个对抗幻觉机制 + 4 个交互模式）
  - **§4 完整数据流**：7 步端到端伪代码 + 时序图
  - **§5 状态估计工程实现**：CTA 5 层数学栈的工程映射（开源依赖）+ Q 矩阵扩展（CD-CAT 集成）+ C 维度评估的具体流程（v0.5.0 整合）+ LLM Critic 的精确边界
  - **§6 干预策略工程实现**：LCA L3-L4 教学法栈的工程映射 + 干预参数化空间 + L4 策略优化（Contextual Bandits MVP / POMCP Phase 5+）
  - **§7 持久化与长期会话管理**：学生状态 SQL 结构 + 干预历史 + 证据日志 + 跨会话状态继承 + 跨学期/学段画像演化（Phase 5+）
  - **§8 MVP 架构**：Phase 4 实现范围表（MVP 包含/不包含组件）+ 简化数据流
  - **§9 与 v2.0 §3 关系**：10 维度对照表（v2.0 提供什么、本文档补充什么）
  - **§10 关联文档** + **§11 版本与维护**
- **`discussions/2026-06-25-ecos-architecture-doc.md`**（本次会话记录）

### 关键架构决策

| 决策项 | 选择 | 理由 |
|---|---|---|
| **数学层不用 LLM**（沿用）| ❌ 否（硬底线）| v0.3.0 + v0.4.0 + v0.5.0 已确立 |
| **LLM Critic 边界** | 仅感知层 + 解释层 + Misconception 检测 | 不污染数学层 |
| **双 Agent 接口** | POMDP `(S, A, O, T, R, Ω)` | v0.3.0 已确立 |
| **MVP 策略优化** | Contextual Bandits (LinUCB) | POMCP 太重，MVP 用轻量级 RL |
| **持久化** | SQLite + JSON 序列化（MVP）| 工程简单可调试 |
| **跨学期/学段** | Phase 5+（MVP 仅学期内）| 与 01-applications.md §7 MVP 范围一致 |

### 与 v2.0 §3 的关系（10 维度对照）

| 维度 | v2.0 提供 | 本文档补充 |
|---|---|---|
| 三空间架构骨架 | ✅ 完整 | 不重复 |
| CTA 思维模式 | ✅ 心理测量学家 | L0-L4 数学栈工程映射 |
| LCA 思维模式 | ✅ 教练 + RL | L3-L4 教学法栈工程映射 |
| BloomProfile | ✅ 6 层分布 | 不重复 |
| 互校机制 | ✅ 核心循环 + 3 机制 + 4 模式 | 互校 + L4 因果归因整合 |
| 完整数据流 | ✅ 伪代码骨架 | 工程细节 + 开源依赖 |
| 状态估计工程 | ⚠️ 只提名字 | L0-L4 完整工程映射 |
| 干预策略工程 | ⚠️ 有列表无理论 | L3-L4 教学法栈 |
| C 维度内容库 | ⚠️ 抽象置信度 | TC + Misconceptions 双轨 |
| 持久化 | ✅ 基本表结构 | 跨会话 + 跨学期边界 |

### 下一步

| 优先级 | 任务 | 详见 |
|---|---|---|
| **P0** | 战略层 03-roadmap.md（阶段划分）| `research/00-overview/` |
| **P0** | 战略层 04-risks.md（风险矩阵）| `research/00-overview/` |
| P1 | 工程层 5 份（10-engineering/）| `research/10-engineering/` |
| P1 | 教学法层 4 份（20-pedagogy/）| `research/20-pedagogy/` |
| P1 | MVP 设计（90-mvp/）| `research/90-mvp/` |
| P2 | `ecos/` Python 包实现 | `ecos/` |
