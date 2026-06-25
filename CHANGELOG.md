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
| 0.7.0 | 2026-06-25 | 604d048 | **战略层第 2 份文档**：research/00-overview/02-architecture.md（v1.0，703 行，11 章节，整体架构——整合 P0 三件套到 ECOS 架构总图：三层视角 ASCII 图 + 三空间架构 + 双 Agent 详细架构 + 完整数据流 + 状态估计工程实现 + 干预策略工程实现 + 双 Agent 互校机制 + 持久化 + MVP 架构范围 + 与 v2.0 §3 关系表）+ discussions/2026-06-25-ecos-architecture-doc.md（会话记录）|
| 0.8.0 | 2026-06-25 | (本次) | **战略层第 3 份文档**：research/00-overview/03-roadmap.md（v1.0，407 行，10 章节，路线图——基于架构定义 M0-M7 共 8 个里程碑；M2-M3 MVP 验证 + M4-M5 产品化 + M6-M7 系统完善；H1-H7 共 7 个核心假设；**批判性修正**：MVP 时间从 v2.0 的 2-4 周修正为 4-8 周；明确"失败回溯"路径 + 团队预算粗估）+ discussions/2026-06-25-ecos-roadmap-doc.md（会话记录）|

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

---

## [0.8.0] - 2026-06-25 (战略层第 3 份文档：路线图)

### 背景

战略层依赖链（01-applications.md → 02-architecture.md → 03-roadmap.md → 04-risks.md）的第 3 份。v2.0 §执行摘要 已给出 3 阶段产品化路径（MVP 2-4 周 / 产品化 2-3 月 / 平台化 6-12 月），但**没有细化为具体里程碑 + 假设验证 + 评估指标**。

本次完成路线图，把架构映射为 M0-M7 共 8 个里程碑，并**批判性修正** v2.0 的 MVP 时间估计。

### 新增

- **`research/00-overview/03-roadmap.md`**（v1.0，407 行，10 章节）
  - **§0 路线图定位**：与 v2.0 关系（扩展）+ 3 大原则（里程碑驱动 / 假设验证导向 / 数据资产累积 / 小步快跑）+ M0-M7 vs v2.0 Phase 对照表
  - **§1 Phase 0 进度盘点**：已完成 7 个版本（v0.1.0-v0.7.0，~2600 行）+ Phase 0 完成定义（战略层 + 工程层 + 教学法层完成）
  - **§2 Phase 4 / M2-M3（MVP 验证）**：M2 工程实现（4-6 周，12 任务按周分解）+ M3 实验分析（2-4 周，H1-H3 验证）
  - **§3 Phase 5 / M4-M5（产品化）**：M4 学科扩展 + M5 商业模式
  - **§4 Phase 6 / M6-M7（系统完善）**：M6 K12 全学段 + M7 数据资产护城河
  - **§5 依赖图与关键路径**：3 个关键决策点 + 总时长 32-44 周（理想）/ 36-52 周（保守）
  - **§6 团队与预算**：各阶段团队配置 + 预算粗估（100-1900 万）
  - **§7 关键风险与对应**：8 类风险 + 对应假设
  - **§8 与 v2.0 产品化路径的关系**：8 维度对照表
- **`discussions/2026-06-25-ecos-roadmap-doc.md`**（本次会话记录）

### 关键决策与批判性修正

| 决策项 | v2.0 原估计 | 本文档修正 | 理由 |
|---|---|---|---|
| **MVP 时间** | 2-4 周 | **4-8 周** | 12 个 MVP 组件工程量 |
| **核心假设数** | 3 个 | **7 个** | M4/M6/M7 各加 1 |
| **失败回溯** | 隐含 | **显式路径** | 避免"all-in 单一假设"陷阱 |
| **里程碑数** | 3 阶段 | **8 个 M0-M7** | 每 2-6 周一个完成定义 |
| **评估阈值** | 概念性 | **具体数字** | H1 AUC≥0.75 / Bloom 60% / 双 Agent ECE≤0.10 |

### 下一步

| 优先级 | 任务 | 详见 |
|---|---|---|
| **P0** | 战略层 04-risks.md（风险矩阵）| `research/00-overview/` |
| P1 | 工程层 5 份（10-engineering/）| `research/10-engineering/` |
| P1 | 教学法层 4 份（20-pedagogy/）| `research/20-pedagogy/` |
| P1 | MVP 设计（90-mvp/）| `research/90-mvp/` |
| P2 | `ecos/` Python 包实现 | `ecos/` |


---

## [0.8.0] - 2026-06-25 (战略层第 3 份文档：路线图)

### 背景

战略层依赖链（01-applications.md → 02-architecture.md → 03-roadmap.md → 04-risks.md）的第 3 份。v2.0 §执行摘要 已给出 3 阶段产品化路径（MVP 2-4 周 / 产品化 2-3 月 / 平台化 6-12 月），但**没有细化为具体里程碑 + 假设验证 + 评估指标**。

本次完成路线图，把架构映射为 M0-M7 共 8 个里程碑，并**批判性修正** v2.0 的 MVP 时间估计。

### 新增

- **`research/00-overview/03-roadmap.md`**（v1.0，407 行，10 章节）
  - **§0 路线图定位**：与 v2.0 关系（扩展）+ 3 大原则（里程碑驱动 / 假设验证导向 / 数据资产累积 / 小步快跑）+ M0-M7 vs v2.0 Phase 对照表
  - **§1 Phase 0 进度盘点**：已完成 7 个版本（v0.1.0-v0.7.0，~2600 行）+ Phase 0 完成定义
  - **§2 Phase 4 / M2-M3（MVP 验证）**：M2 工程实现（4-6 周）+ M3 实验分析（2-4 周，H1-H3 验证）
  - **§3 Phase 5 / M4-M5（产品化）**：M4 学科扩展 + M5 商业模式
  - **§4 Phase 6 / M6-M7（系统完善）**：M6 K12 全学段 + M7 数据资产护城河
  - **§5 依赖图与关键路径**：3 个关键决策点 + 总时长 32-44 周（理想）/ 36-52 周（保守）
  - **§6 团队与预算**：各阶段团队配置 + 预算粗估（100-1900 万）
  - **§7 关键风险与对应**：8 类风险 + 对应假设
  - **§8 与 v2.0 产品化路径的关系**：8 维度对照表
- **`discussions/2026-06-25-ecos-roadmap-doc.md`**（本次会话记录）

### 关键决策与批判性修正

| 决策项 | v2.0 原估计 | 本文档修正 | 理由 |
|---|---|---|---|
| **MVP 时间** | 2-4 周 | **4-8 周** | 12 个 MVP 组件工程量 |
| **核心假设数** | 3 个 | **7 个** | M4/M6/M7 各加 1 |
| **失败回溯** | 隐含 | **显式路径** | 避免"all-in 单一假设"陷阱 |
| **里程碑数** | 3 阶段 | **8 个 M0-M7** | 每 2-6 周一个完成定义 |
| **评估阈值** | 概念性 | **具体数字** | H1 AUC≥0.75 / Bloom 60% / 双 Agent ECE≤0.10 |

### 下一步

| 优先级 | 任务 | 详见 |
|---|---|---|
| **P0** | 战略层 04-risks.md（风险矩阵）| `research/00-overview/` |
| P1 | 工程层 5 份（10-engineering/）| `research/10-engineering/` |
| P1 | 教学法层 4 份（20-pedagogy/）| `research/20-pedagogy/` |
| P1 | MVP 设计（90-mvp/）| `research/90-mvp/` |
| P2 | `ecos/` Python 包实现 | `ecos/` |


---

## [0.9.0] - 2026-06-25 (战略层第 4 份文档：风险矩阵 + 战略层全部完成)

### 背景

战略层依赖链（01-applications.md → 02-architecture.md → 03-roadmap.md → 04-risks.md）的第 4 份（最后 1 份）。v2.0 §5.5 已给出 5 大风险，但**没有触发条件、影响评估、缓解策略、应急预案、监控指标五要素结构化**。

本次完成风险矩阵，从 5 类扩展到 18 类（更细粒度），并**完成整个战略层**——下一步进入工程层（`10-engineering/`）+ 教学法层（`20-pedagogy/`）。

### 新增

- **`research/00-overview/04-risks.md`**（v1.0，713 行，10 章节）
  - **A 技术风险（4 类）**：双 Agent 工程复杂度 / CTA 5D 预测精度 / LCA 可解释性 / 双 Agent 互校抗幻觉
  - **B 产品风险（4 类）**：Bloom 6 层适用性 / 早期体验 / 长期数据稀疏 / 数据采集质量
  - **C 教育专业风险（3 类）**：教师协作成本 / 教学法文化适配 / 学科本体构建
  - **D 伦理与法律风险（3 类）**：未成年人数据合规 / 家长控制透明度 / 教育部门监管
  - **E 商业模式风险（4 类）**：B2C 付费意愿 / B2B 决策周期 / 竞品压力 / 数据资产护城河
  - **F 风险监控与应对机制**：监控看板 + 升级流程 + 应急预案 + 维护规则
  - **G 风险总览表（速查）**：18 类风险 + 等级 + 对应假设 + 主要缓解
  - **H 与 v2.0 §5.5 的关系**：5 类 → 18 类扩展对照表
- **`discussions/2026-06-25-ecos-risks-doc.md`**（本次会话记录）

### 关键设计决策

| 决策项 | v2.0 §5.5 | 本文档 |
|---|---|---|
| 风险数量 | 5 类 | **18 类**（A 技术 4 + B 产品 4 + C 教育 3 + D 伦理 3 + E 商业 4）|
| 每类结构 | 影响 + 缓解（2 要素）| **触发条件 + 影响评估 + 缓解策略 + 应急预案 + 监控指标**（5 要素）|
| 风险等级 | 隐含 | 显式 🔴 高 / 🟡 中 / 🟢 低 |
| 风险与假设对应 | 无 | 显式映射（H1 → A2 / H2 → B1 / H3 → A4 / H5 → E1+E2 / H7 → E4）|
| 红线指标 | 无 | 5 个（数据泄露/合规/留存率/LLM 成本/监管约谈）|
| 升级流程 | 无 | 4 级（个人 → 团队 → 创始人 → 暂停回溯）|

### 风险统计

```
🔴 高风险（5 个）：A1 / A2 / A4 / D1 / E4
🟡 中风险（13 个）：A3 / B1-B4 / C1-C3 / D2 / D3 / E1-E3
🟢 低风险（0 个）
```

### 战略层全部完成（Phase 0 进度）

```
✅ 01-applications.md （v0.2.0）10 章节，4 大场景
✅ 02-architecture.md  （v0.7.0）11 章节，P0 三件套整合
✅ 03-roadmap.md      （v0.8.0）10 章节，M0-M7 共 8 个里程碑
✅ 04-risks.md        （v0.9.0）10 章节，18 类风险矩阵
─────────────────────────────────────────────────
战略层 4 份全部完成 ✅
Phase 0 完成度：~70%（待工程层 + 教学法层 + MVP 设计）
```

### 下一步

| 优先级 | 任务 | 详见 |
|---|---|---|
| P1 | 工程层 5 份（10-engineering/01-05）| `research/10-engineering/` |
| P1 | 教学法层 4 份（20-pedagogy/01-04）| `research/20-pedagogy/` |
| P1 | MVP 设计（90-mvp/）| `research/90-mvp/` |
| 按需 | 理论借鉴 P1（工程实施遇 gap 时）| `theoretical-foundations/` |
| P2 | `ecos/` Python 包实现 | `ecos/` |

### Phase 0 完成定义

按 [03-roadmap.md §1.2](../../00-overview/03-roadmap.md)：
- ✅ 战略层 4 份全部完成
- ⏳ 工程层 5 份完成（CTA 信念引擎 + LCA 策略引擎 + Bloom 目标库 + 双 Agent 互校 + 持久化）
- ⏳ 教学法层 4 份完成（K12 认知结构 + Bloom 应用 + 学习策略 + ZPD 应用）
- ⏳ MVP 设计完成（90-mvp/）
- **总文档 ≥ 5000 行**（当前 ~3300 行，需 ~1700 行补充）


---

## [0.10.0] - 2026-06-25 (工程层第 1 份文档：CTA 信念引擎)

### 背景

战略层全部完成后（v0.9.0），进入工程层（`10-engineering/`）。5 份工程文档按依赖顺序：01-cta → 02-lca → 03-bloom → 04-dual-agent → 05-persistence。

CTA 信念引擎是双 Agent 架构的核心——基于 v0.3.0 数学基础 + v0.5.0 C 维度内容库 + 02-architecture.md §5 实现。

### 新增

- **`research/10-engineering/01-cta-belief-engine.md`**（v1.0，1409 行，14 章节）
  - **§0 模块定位**：核心职责 + 与其他模块接口 + 文档目标读者
  - **§1 整体架构**：5 层数学栈工程映射（L0 POMDP / L1 BKT / L2 MIRT / L3 CD-CAT / L4 Causal）+ L0.5 内容库 + 完整模块目录结构（13 个子目录）+ 与 LCA / Persistence 接口契约
  - **§2 BeliefState 数据结构**：完整 Python dataclass（DimensionState / BloomProfileState / LearningDNAState / TrajectoryState / BeliefState）+ C 维度扩展（含 MisconceptionHit + TCState）+ 信念更新统一接口
  - **§3 L0 POMDP**：CTAPOMDP 类（EKF + 离散属性精确推断）+ 转移矩阵 / 观测矩阵 / 过程噪声 + POMCP Phase 5+ 占位
  - **§4 L1 BKT + Spaced Repetition**：BKTModel（4 参数）+ BKTEvolutionLayer（管理所有知识点）+ FSRS 间隔效应 + DKT Phase 5+ 占位
  - **§5 L2 MIRT**：BiFactorMIRT5D（非补偿 Bi-factor）+ CovarianceLearner（学科自适应）+ 校准与冷启动
  - **§6 L3 CD-CAT**：GDINAModel + Q 矩阵扩展（v0.5.0 TC + Misc 标注）+ PWKLSelector + 停止规则
  - **§7 L4 Causal**：ABTestAttributor（MVP 简化版）+ CausalForestAttributor（Phase 5+）
  - **§8 C 维度内容库集成**：MisconceptionDetector（LLM Critic + 关键词混合）+ TCStateDetector（Liminal/Post-liminal 识别）+ C 维度更新（伪置信折扣 + TC 不可逆性）
  - **§9 LLM Critic 边界**：PerceptionCritic（感知层）+ ExplanationCritic（解释层）+ CriticPrompts（3 类 prompt 模板）
  - **§10 CTA 主流程编排**：CTAOrchestrator（7 步骤完整流程）+ report 生成
  - **§11 测试策略**：单元测试覆盖率（核心 ≥ 85%）+ 集成测试 + 评估指标对照（vs 04-risks.md §A 阈值）
  - **§12 MVP 范围**：16 个 MVP 组件状态表
  - **§13 关联文档** + **§14 版本与维护**
- **`discussions/2026-06-25-ecos-cta-engine-doc.md`**（本次会话记录）

### 关键工程实现决策

| 决策项 | MVP 选择 | 理由 |
|---|---|---|
| **L0 POMDP 求解** | EKF + 离散属性精确推断 | 11D 状态空间需因子化，POMCP 太重 |
| **L1 BKT 算法** | 经典 4 参数 | 可解释、易调参 |
| **L2 MIRT 结构** | Bi-factor 非补偿 5D + 1 一般维度 | 避免"伪掌握" |
| **L3 CD-CAT 算法** | GDINA + PWKL 选题 | DINA 最一般化 + 兼顾信息量 |
| **L4 因果归因** | 单变量 A/B + T-test（MVP）/ Causal Forest（Phase 5+）| MVP 简化 |
| **Misconception 检测** | LLM Critic + 关键词混合 | LLM 灵活 + 关键词精确 |
| **TC 状态检测** | 启发式 + 元认知信号 | MVP 简化 |
| **TC 不可逆性** | post-liminal C 维度永不下降 | TC 核心特征 |
| **数学层是否用 LLM** | ❌ 否（硬底线）| 任何 LLM 直接生成信念估计都是退路 |

### 测试覆盖目标

| 模块 | 目标覆盖率 | 关键指标 |
|---|---|---|
| L0 POMDP | ≥ 90% | EKF 准确性 |
| L1 BKT | ≥ 90% | 更新规则数学正确性 |
| L2 MIRT | ≥ 85% | EM 收敛 |
| L3 CD-CAT | ≥ 85% | PWKL 选题最优性 |
| L4 Causal | ≥ 90% | T-test 显著性 |
| Content | ≥ 80% | Misconception F1 ≥ 0.7, TC F1 ≥ 0.6 |
| LLM Critic | ≥ 70% | JSON 解析正确性 |

### 累计文档产出（v0.1.0 ~ v0.10.0）

| 类别 | 数量 | 行数（约）|
|---|---|---|
| 战略层 00-overview/ | 4 份 ✅ | ~2200 行 |
| **工程层 10-engineering/** | **1 份（进行中）** | **1409 行** |
| P0 借鉴 theoretical-foundations/ | 4 份 ✅ | ~1700 行 |
| 共享 + AiBeing 借鉴 + 5 轮对话 + 深度研究 | 8 份（迁移）| — |
| 项目级 + 讨论记录 | 16+ 份 | ~2000 行 |
| **总计** | **~33+ 份** | **~7300+ 行** |

### 下一步

| 优先级 | 任务 | 详见 |
|---|---|---|
| P1 | 工程层 02-lca-policy-engine.md（LCA 策略引擎）| `research/10-engineering/` |
| P1 | 工程层 03-bloom-goal-library.md（Bloom 目标库）| `research/10-engineering/` |
| P1 | 工程层 04-dual-agent-calibration.md（双 Agent 互校）| `research/10-engineering/` |
| P1 | 工程层 05-persistence-session.md（持久化）| `research/10-engineering/` |
| P2 | 教学法层 4 份（20-pedagogy/）| `research/20-pedagogy/` |
| P2 | MVP 设计（90-mvp/）| `research/90-mvp/` |


---

## [0.11.0] - 2026-06-25 (工程层第 2 份文档：LCA 策略引擎)

### 背景

工程层第 2 份——LCA 策略引擎，基于 v0.4.0 LCA 教学法基础（3 大理论群：CLT + Bjork + Cognitive Apprenticeship）+ 02-architecture.md §6 实现。

LCA 是双 Agent 架构的"改变学生"组件——基于 CTA 状态选择最优干预 + 可解释 rationale 输出。

### 新增

- **`research/10-engineering/02-lca-policy-engine.md`**（v1.0，1125 行，10 章节）
  - **§0 模块定位**：核心职责 + 与 CTA 接口 + 硬底线（LLM 仅用于 rationale 表达层）+ 文档目标读者
  - **§1 整体架构**：L3-L4 教学法栈工程映射（11 组件）+ 12 个子目录 + 与 CTA / App 接口契约
  - **§2 干预参数化空间**：完整 Python dataclass（InterventionType / CLTLevel / CAStage / Intervention）+ 5 类干预 × 4 参数 + Bloom 目标选择算法
  - **§3 L3 干预类型选择层**：
    - §3.1 CLT 4 级自适应呈现（expertise reversal 自动化）
    - §3.2 CLT 4 级题目模板（NOVICE/DEVELOPING/PROFICIENT/EXPERT）
    - §3.3 Bjork 测试效应（FSRS 集成）
    - §3.4 Bjork 间隔效应（FSRS + 衰减模型）
    - §3.5 CA Scaffolding 衰减（连续成功撤走支持）
  - **§4 L4 策略优化层**：
    - §4.1 Cognitive Apprenticeship 6 阶段状态机（自动转移规则）
    - §4.2 Contextual Bandits LinUCB MVP（5D + Bloom + LearningDNA = 16 维 context）
    - §4.3 POMCP（Phase 5+ 占位）
    - §4.4 因果归因（与 CTA L4 协作）
  - **§5 可解释性输出**：rationale 生成器（学生/教师/家长 3 套 prompt）+ 教师后台接口
  - **§6 LCA 主流程编排**：8 步骤完整流程
  - **§7 测试策略**：单元测试覆盖率 ≥ 75% + 集成测试 + 评估指标（vs 04-risks.md §A3 + §C2 阈值）
  - **§8 MVP 范围**：11 组件状态表（MVP 实现 Stage 1-3 + LinUCB + rationale）
  - **§9-10 关联文档 + 版本维护**
- **`discussions/2026-06-25-ecos-lca-engine-doc.md`**（本次会话记录）

### 关键工程实现决策

| 决策项 | MVP 选择 | 理由 |
|---|---|---|
| **L3 决策算法** | 规则启发（教学法决策树）| 可解释、易调试、不依赖 LLM |
| **L3 CLT 4 级呈现** | 自适应模板系统（4 套）| expertise reversal 自动化 |
| **L3 Bjork** | MVP: 测试 + 间隔；Phase 5+: 合意困难 + 交错 | MVP 简化 |
| **L3 CA Stage** | MVP: Stage 1-3；Phase 5+: Stage 4-6 | MVP 简化 |
| **L4 策略学习** | Contextual Bandits LinUCB（MVP）/ POMCP（Phase 5+）| MVP 轻量级 RL |
| **L4 因果归因** | 与 CTA L4 共享 ABTestAttributor | 避免重复实现 |
| **Rationale 输出** | LLM 表达层（不污染教学法决策）| 学生/教师/家长 3 套 prompt |
| **教学法决策是否用 LLM** | ❌ 否（硬底线）| 任何 LLM 直接选择干预类型都是退路 |

### 完整 L3-L4 教学法栈

```
L3 干预类型选择层
├── CLT 4 级自适应呈现（expertise reversal）
├── Bjork 测试效应（FSRS）
├── Bjork 间隔效应（FSRS）
├── Bjork 合意困难（Phase 5+）
├── Bjork 交错练习（Phase 5+）
└── CA Scaffolding 衰减

L4 策略优化层
├── Cognitive Apprenticeship 6 阶段状态机
├── Contextual Bandits LinUCB（MVP）
├── POMCP（Phase 5+）
└── 因果归因（与 CTA L4 共享）
```

### 评估指标（对照 04-risks.md）

| 指标 | 阈值 | 测试场景 |
|---|---|---|
| 教师 rationale 满意度 | ≥ 4/5 | 教师问卷 |
| 家长接受率 | ≥ 70% | 家长问卷 |
| 学生干预接受率 | ≥ 60% | 行为日志 |
| LinUCB 收敛 | ≤ 50 次交互 | 模拟实验 |
| rationale 生成延迟 | P95 ≤ 3 秒 | 性能测试 |
| 可解释性 vs 性能权衡 | 性能损失 ≤ 10% | A/B 实验 |

### 工程层进度

```
✅ 01-cta-belief-engine.md    （v0.10.0，1409 行）
✅ 02-lca-policy-engine.md    （v0.11.0，1125 行）★
⏳ 03-bloom-goal-library.md
⏳ 04-dual-agent-calibration.md
⏳ 05-persistence-session.md
40% 完成
```

### 下一步

| 优先级 | 任务 | 详见 |
|---|---|---|
| P1 | 工程层 03-bloom-goal-library.md（Bloom 目标库）| `research/10-engineering/` |
| P1 | 工程层 04-dual-agent-calibration.md（双 Agent 互校）| `research/10-engineering/` |
| P1 | 工程层 05-persistence-session.md（持久化）| `research/10-engineering/` |
| P2 | 教学法层 4 份（20-pedagogy/）| `research/20-pedagogy/` |
| P2 | MVP 设计（90-mvp/）| `research/90-mvp/` |


---

## [0.12.0] - 2026-06-25 (工程层第 3 份文档：Bloom Goal Library)

### 背景

工程层第 3 份——Bloom 目标库（CTA 与 LCA 的"共同语言"）。基于 v2.0 §3.4 + 02-architecture.md §2.2 + v0.5.0 C 维度内容库 + 01-cta-belief-engine.md + 02-lca-policy-engine.md。

Bloom Goal Library 把 Bloom 6 层认知层级工程化为可计算的目标库——作为 CTA 状态估计的目标 + LCA 干预选择的目标。

### 新增

- **`research/10-engineering/03-bloom-goal-library.md`**（v1.0，1093 行，13 章节）
  - **§0 模块定位**：核心职责（CTA + LCA 的共同语言）+ 与 v0.5.0 关系
  - **§1 整体架构**：6 层 Bloom 学科映射表 + 12 子目录 + 与 CTA / LCA 接口契约
  - **§2 Bloom 数据结构**：BloomLevel 枚举（含前置关系）+ BloomGoal 完整 dataclass + BloomGoalLibrary 容器（多维索引）
  - **§3 数学 Bloom 目标库（MVP 核心）**：8 知识点 × 4 层 = 32 条 BloomGoal（含二次函数完整 4 层样例）+ 中国课程标准对接（人教版）
  - **§4-5 物理/语文 Bloom 目标库**（Phase 5+）：占位 + 与数学的差异分析
  - **§6 跨学科 Bloom 整合**：跨学科 BloomGoal（数学建模）+ 数学 P 与物理 P 的迁移建模
  - **§7 next_target 选择算法**：NextBloomTargetSelector（基于 CTA 状态 + 前置检查 + 学习路径构造）
  - **§8 与 TC / Misconception 库集成**：TC 跨越后 BloomProfile 提升 + Misconception 命中后下调 + Q 矩阵扩展
  - **§9 查询接口**：3 个使用示例
  - **§10 测试策略**：单元测试覆盖率 ≥ 80% + 集成测试 + 评估指标（vs 04-risks.md §B1 阈值）
  - **§11 MVP 范围**：8 组件状态表 + 数据规模（32 → 235 → 670 条）
  - **§12-13 关联文档 + 版本维护**
- **`discussions/2026-06-25-ecos-bloom-library-doc.md`**（本次会话记录）

### 关键设计决策

| 决策项 | MVP 选择 | 理由 |
|---|---|---|
| **MVP 学科** | 数学 | K12 学科中 CTA 5D 状态建模最成熟 |
| **MVP 库规模** | 8 知识点 × 4 层 = 32 条 BloomGoal | 80/20 原则 |
| **L5/L6 处理** | MVP 不实现（K12 不常达到）| 04-risks.md §B1 风险评估 |
| **课程标准对接** | 中国教育部人教版（数学）| MVP 服务中国 K12 |
| **TC 集成** | TC 跨越后 BloomProfile 自动 +0.1 | TC 是 Bloom 跨越的关键节点 |
| **Misconception 集成** | 命中后 BloomProfile × 0.7 | 伪置信折扣 |
| **next_target 算法** | 当前层 + 1（但不超过能力上限）| 渐进式挑战 |
| **数学 P 与物理 P 迁移** | MVP 不实现（Phase 5+）| 跨学科能力需更多数据 |

### MVP 数据规模

| 库 | MVP | Phase 5 | Phase 6 |
|---|---|---|---|
| 数学 | 32 条 BloomGoal | 100 条 | 300 条 |
| 物理 | 0 | 80 条 | 200 条 |
| 语文 | 0 | 50 条 | 150 条 |
| 跨学科 | 0 | 5 条 | 20 条 |
| **总计** | **32 条** | **235 条** | **670 条** |

### 工程层进度

```
✅ 01-cta-belief-engine.md    （v0.10.0，1409 行）
✅ 02-lca-policy-engine.md    （v0.11.0，1125 行）
✅ 03-bloom-goal-library.md   （v0.12.0，1093 行）★
⏳ 04-dual-agent-calibration.md
⏳ 05-persistence-session.md
60% 完成
```

### 累计产出（v0.1.0 ~ v0.12.0）

| 类别 | 数量 | 行数（约）|
|---|---|---|
| 战略层 00-overview/ | 4 份 ✅ | ~2400 行 |
| 工程层 10-engineering/ | 3 份（进行中）| ~3700 行 |
| P0 借鉴 theoretical-foundations/ | 4 份 ✅ | ~1700 行 |
| 共享 + AiBeing + 5 轮 + 深度研究 | 8 份（迁移）| — |
| 项目级 + 讨论记录 | 20+ 份 | ~3000 行 |
| **总计** | **~40+ 份** | **~10800+ 行** |

### 下一步

| 优先级 | 任务 | 详见 |
|---|---|---|
| P1 | 工程层 04-dual-agent-calibration.md（双 Agent 互校）| `research/10-engineering/` |
| P1 | 工程层 05-persistence-session.md（持久化）| `research/10-engineering/` |
| P2 | 教学法层 4 份（20-pedagogy/）| `research/20-pedagogy/` |
| P2 | MVP 设计（90-mvp/）| `research/90-mvp/` |


---

## [0.13.0] - 2026-06-25 (工程层第 4 份文档：双 Agent 互校机制)

### 背景

工程层第 4 份——双 Agent 互校机制（CTA ↔ LCA 接口契约）。基于 v2.0 §3.5 + 02-architecture.md §3.3 + 01-cta-belief-engine.md + 02-lca-policy-engine.md + 04-risks.md §A1 + §A4。

这是 ECOS 的"抗幻觉核心"——通过 CTA 保守 vs LCA 主动的互相质疑 + 4 个交互模式 + 3 个机制防止 LLM 幻觉。

### 新增

- **`research/10-engineering/04-dual-agent-calibration.md`**（v1.0，1147 行，10 章节）
  - **§0 模块定位**：核心职责（CTA ↔ LCA 共同对抗幻觉）+ 与 04-risks.md §A1 + §A4 对应
  - **§1 整体架构**：互校循环总览 + 4 模式 + 3 机制 + 11 子目录 + 接口契约（CalibratedCTAOutput / CalibratedLCAResult）
  - **§2 互校循环协议**：消息格式（CalibrationMessage + 9 种 MessageType）+ 互校状态机（11 状态）+ version 协议
  - **§3 4 个交互模式**：
    - §3.1 常态循环（6 步骤完整流程）
    - §3.2 信念质疑（LCA 不认同 CTA 状态）+ 触发条件
    - §3.3 策略质疑（CTA 发现 LCA 干预无效）+ 检测算法
    - §3.4 元反思（4 周无 BloomProfile 提升）+ 双 Agent 整体复盘
  - **§4 对抗幻觉的 3 个机制**：
    - §4.1 CTA 信念分布（非事实判断）
    - §4.2 LCA 实验设计（非直接给答案）
    - §4.3 因果归因强制（不允许"只看相关性"）
    - §4.4 人工审核触发（置信度 < 0.6 / 信念分布不合理 / 连续 3 次干预无效）
  - **§5 死锁避免**：超时保护 + 优先级仲裁 + 单 Agent 降级
  - **§6 互校循环主流程编排**：DualAgentOrchestrator（process_observation 主入口）
  - **§7 测试策略**：单元测试覆盖率 ≥ 80% + 5 个关键测试场景 + 性能基准（vs 04-risks.md §A1 + §A4 阈值）
  - **§8 MVP 范围**：6 组件状态表 + 性能预算
  - **§9-10 关联文档 + 版本维护**
- **`discussions/2026-06-25-ecos-dual-agent-doc.md`**（本次会话记录）

### 关键设计决策

| 决策项 | MVP 选择 | 理由 |
|---|---|---|
| **互校循环模式** | 同步（不异步）| 实时性优先，避免异步复杂度 |
| **状态机** | 11 状态（IDLE + CTA + LCA + 观察 + 特殊模式 + 人工）| 完整覆盖所有交互 |
| **4 模式触发** | 常态（自动）/ 信念质疑（实验不符）/ 策略质疑（连续无效）/ 元反思（4 周停滞）| 自动检测 + 显式触发 |
| **抗幻觉机制 1** | CTA 信念分布 + confidence + evidence_ids | 避免事实判断 |
| **抗幻觉机制 2** | LCA 实验设计验证（避免直接给答案）| 难度匹配 + 反馈密度合理 |
| **抗幻觉机制 3** | L4 因果归因强制 | 不允许只看相关性 |
| **人工审核触发** | 置信度 < 0.6 / 信念不合理 / 连续 3 次无效 | 3 种触发条件 |
| **死锁避免** | 超时（30s）+ 优先级仲裁 + 单 Agent 降级 | 3 重保护 |

### 4 个交互模式触发条件

| 模式 | 触发条件 | 处理 |
|---|---|---|
| **常态循环** | 新观测（无异常）| 6 步骤完整流程 |
| **信念质疑** | CTA 高置信 + 学生实际表现差 / 信念变化超阈值 / 实验不符 | CTA 重审 + 更新 |
| **策略质疑** | 连续 5 次干预平均改善 < 0.05 | LCA 调整策略空间 |
| **元反思** | 4 周无 BloomProfile 关键层提升 ≥ 0.05 | 双 Agent 整体复盘 |

### 3 个抗幻觉机制

1. **CTA 信念分布**：每维度含 confidence + evidence_ids，避免事实判断
2. **LCA 实验设计**：练习型需 difficulty 匹配、讲解型需目标技能、元认知型不能过频繁
3. **L4 因果归因强制**：每个干预效果必须经因果归因，缺失则抛 ValueError

### 性能基准（vs 04-risks.md §A1 + §A4 阈值）

| 指标 | 阈值 |
|---|---|
| 常态循环延迟 | P95 ≤ 5 秒 |
| 互校循环总延迟 | P95 ≤ 10 秒 |
| 接口错误率 | ≤ 0.1% |
| 信念质疑 F1 | ≥ 0.7 |
| 策略质疑 F1 | ≥ 0.6 |
| **ECE（双 Agent 校准度）** | **≤ 0.10**（H3 假设验证）|
| 人工审核触发率 | ≤ 5% |

### 工程层进度

```
✅ 01-cta-belief-engine.md    （v0.10.0，1409 行）
✅ 02-lca-policy-engine.md    （v0.11.0，1125 行）
✅ 03-bloom-goal-library.md   （v0.12.0，1093 行）
✅ 04-dual-agent-calibration  （v0.13.0，1147 行）★
⏳ 05-persistence-session.md
80% 完成
```

### 累计产出（v0.1.0 ~ v0.13.0）

| 类别 | 数量 | 行数（约）|
|---|---|---|
| 战略层 00-overview/ | 4 份 ✅ | ~2400 行 |
| 工程层 10-engineering/ | 4 份（进行中）| ~4800 行 |
| P0 借鉴 theoretical-foundations/ | 4 份 ✅ | ~1700 行 |
| 共享 + AiBeing + 5 轮 + 深度研究 | 8 份（迁移）| — |
| 项目级 + 讨论记录 | 22+ 份 | ~3500 行 |
| **总计** | **~42+ 份** | **~12400+ 行** |

### 下一步

| 优先级 | 任务 | 详见 |
|---|---|---|
| P1 | 工程层 05-persistence-session.md（持久化）| `research/10-engineering/` |
| P2 | 教学法层 4 份（20-pedagogy/）| `research/20-pedagogy/` |
| P2 | MVP 设计（90-mvp/）| `research/90-mvp/` |


---

## [0.14.0] - 2026-06-25 (工程层第 5 份文档：持久化与会话管理 + **工程层 100% 完成**)

### 背景

工程层最后 1 份——持久化与会话管理。基于 02-architecture.md §7 + 04-risks.md §B3（长期数据稀疏）+ §D1（未成年人合规）+ v2.0 §4.2/§4.4（SelfLab SGE + AiBeing 借鉴）。

**工程层 5 份全部完成**——CTA 引擎 + LCA 引擎 + Bloom 库 + 双 Agent 互校 + 持久化全部落地。

### 新增

- **`research/10-engineering/05-persistence-session.md`**（v1.0，1338 行，11 章节）
  - **§0 模块定位**：核心职责 + 与 04-risks.md §B3 + §D1 对应
  - **§1 整体架构**：4 层记忆层次图 + 13 子目录 + 与 CTA/LCA/互校/Bloom 接口契约
  - **§2 SQLite Schema 设计**（6 个核心表）：
    - `students`（学生核心 + 加密 + 匿名化）
    - `interventions`（干预历史 + 因果归因）
    - `evidence_log`（证据日志 + LLM Critic 输出 + 质量评分）
    - `calibration_log`（互校历史 + 4 模式触发记录）
    - `bloom_goals` + `problem_bloom_goals`（多对多关联）
    - `trajectory_snapshots`（轨迹快照 + 跨学期元数据）
  - **§3 4 层记忆实现**：
    - §3.1 L1 短期（Hawking 风格）—— 内存 deque + TTL
    - §3.2 L2 中期（Crystallizer 风格）—— SQLite evidence_log
    - §3.3 L3 长期（Identity 风格）—— SQLite students 表（加密）
    - §3.4 L4 持久（Archive 风格，区别于 SelfLab Narrative）—— trajectory_snapshots 表
  - **§4 ECOSSession 类**：跨会话继承 + epoch 计数器 + 自动保存 + 崩溃恢复
  - **§5 chunk 隔离**：支持 6-12 年长跑（chunk_size=100 epochs）+ 崩溃恢复
  - **§6 数据迁移与备份**：v1→v2 migration + 数据导出
  - **§7 隐私保护**（04-risks.md §D1）：
    - §7.1 加密存储（Fernet + msgpack）
    - §7.2 差分隐私（拉普拉斯噪声 + 聚合匿名化）
    - §7.3 匿名化（SHA256 + salt）
    - §7.4 数据最小化策略（NEVER_COLLECT + REQUIRES_PARENT_CONSENT）
  - **§8 测试策略**：单元测试 ≥ 80% + 集成测试 + 性能基准 + 3 个隐私合规测试
  - **§9 MVP 范围**：11 组件状态表 + 数据规模（50-100 → 500-1000 → 5000-10000 学生）
  - **§10-11 关联文档 + 版本维护**
- **`discussions/2026-06-25-ecos-persistence-doc.md`**（本次会话记录）

### 关键设计决策

| 决策项 | MVP 选择 | 理由 |
|---|---|---|
| **存储技术** | SQLite + JSON | 简单、可调试、无运维 |
| **4 层记忆** | Hawking/Crystallizer/Identity/Archive（区别于 SelfLab Narrative）| ECOS 不是 AI 自我，不需要"自传叙事" |
| **加密** | Fernet (AES-128) + msgpack | 标准加密 + 高效序列化 |
| **差分隐私** | Laplace 噪声 + 聚合匿名化（min_group_size=10）| 学术研究数据发布 |
| **chunk 隔离** | 100 epochs/chunk | 支持 6-12 年长跑 |
| **数据最小化** | NEVER_COLLECT + REQUIRES_PARENT_CONSENT | 未成年人数据合规 |
| **跨会话继承** | 30 分钟内未结束的 session 自动恢复 | 学生体验连续性 |
| **崩溃恢复** | chunk + L3 长期记忆双层 | 防止 6-12 年状态丢失 |

### 4 层记忆设计（与 SelfLab SGE 对比）

| 层 | SelfLab SGE | ECOS | 差异 |
|---|---|---|---|
| **L1 短期** | Hawking 挫败感冷却 | 内存 deque + TTL | 实现类似 |
| **L2 中期** | Crystallizer 长期风格记忆 | SQLite evidence_log | ECOS 是学习证据，SelfLab 是风格 |
| **L3 长期** | Identity Layer 自我概念 | SQLite students 表 | ECOS 是学生能力，SelfLab 是 AI 自我 |
| **L4 持久** | Narrative 自传叙事 | trajectory_snapshots | **ECOS 不用 Narrative**——不建模 AI 自传 |

### MVP 数据规模

| 数据 | MVP | Phase 5 | Phase 6 |
|---|---|---|---|
| 学生数 | 50-100 | 500-1000 | 5000-10000 |
| 每学生 evidence_log | 100-1000 | 1000-10000 | 10000-50000 |
| 每学生 interventions | 20-100 | 200-1000 | 2000-5000 |
| 每学生 trajectory_snapshots | 4-16 | 50-200 | 500-2000 |
| BloomGoal 库 | 32 条 | 235 条 | 670 条 |

### 性能基准（vs 04-risks.md §B3 + §D1 阈值）

| 指标 | 阈值 |
|---|---|
| 状态保存延迟 | P95 ≤ 100ms |
| 状态加载延迟 | P95 ≤ 200ms |
| 自动保存延迟 | P95 ≤ 500ms |
| 崩溃恢复时间 | ≤ 5 秒 |
| 差分隐私聚合延迟 | ≤ 1 秒（10000 学生）|
| 加密/解密吞吐 | ≥ 1000 ops/sec |

### **工程层 100% 完成** 🎉

```
✅ 01-cta-belief-engine.md    （v0.10.0，1409 行）
✅ 02-lca-policy-engine.md    （v0.11.0，1125 行）
✅ 03-bloom-goal-library.md   （v0.12.0，1093 行）
✅ 04-dual-agent-calibration  （v0.13.0，1147 行）
✅ 05-persistence-session.md   （v0.14.0，1338 行）★
─────────────────────────────────────────────
工程层 5 份全部完成 ✅
```

### 累计产出（v0.1.0 ~ v0.14.0）

| 类别 | 数量 | 行数（约）|
|---|---|---|
| 战略层 00-overview/ | 4 份 ✅ | ~2400 行 |
| **工程层 10-engineering/** | **5 份 ✅** | **~6100 行** |
| P0 借鉴 theoretical-foundations/ | 4 份 ✅ | ~1700 行 |
| 共享 + AiBeing + 5 轮 + 深度研究 | 8 份（迁移）| — |
| 项目级 + 讨论记录 | 24+ 份 | ~4000 行 |
| **总计** | **~45+ 份** | **~14200+ 行** |

### 下一步

| 优先级 | 任务 | 详见 |
|---|---|---|
| P1 | 教学法层 4 份（20-pedagogy/）| `research/20-pedagogy/` |
| P1 | MVP 设计（90-mvp/）| `research/90-mvp/` |
| 按需 | 理论借鉴 P1（工程实施遇 gap 时）| `theoretical-foundations/` |
| P2 | `ecos/` Python 包实现 | `ecos/` |

### Phase 0 进度

| 维度 | 状态 | 完成度 |
|---|---|---|
| 战略层 | ✅ 100% | 4/4 |
| 工程层 | ✅ 100% | 5/5 |
| 教学法层 | ⏳ 0% | 0/4 |
| MVP 设计 | ⏳ 仅 README 占位 | 0/1 |
| **Phase 0 完成度** | **~83%** | **10/14** |

剩余 4 份即可 Phase 0 全部完成（目标：5000 行 → 已 14200 行，远超目标）。


---

## [0.15.0] - 2026-06-25 (教学法层第 1 份文档：K12 认知结构)

### 背景

教学法层第 1 份——K12 认知结构（小学/初中/高中各学段认知发展特征与 ECOS CTA 建模差异化）。基于 v2.0 §1.4 + v0.5.0 C 维度内容库 + 02-architecture.md + 01-cta-belief-engine.md + 03-bloom-goal-library.md。

回答核心问题：**ECOS 在小学、初中、高中各学段应该如何差异化建模学生认知？**

### 新增

- **`research/20-pedagogy/01-k12-cognitive-structure.md`**（v1.0，516 行，11 章节）
  - **§0 模块定位**：核心职责（学段差异化的"基础配置"）
  - **§1 小学阶段认知发展（1-6 年级）**：Piaget 视角 + ECOS 建模差异（5D 默认 + BloomProfile）+ 小学 TC 库候选 4 个 + Misconception 库候选 3 个 + LCA 干预约束
  - **§2 初中阶段认知发展（7-9 年级）**：形式运算初期 + 完整 5D 启用 + 8 个核心 TC（含 v0.5.0 候选）+ 10 条 Misconception + 干预难度提升
  - **§3 高中阶段认知发展（10-12 年级）**：形式运算成熟 + 学科专业化 + 7 个 TC 候选（Phase 5+）+ 4 条 Misconception + 完整难度
  - **§4 学段过渡的关键节点**：小学→初中/初中→高中挑战 + 状态迁移算法 + Liminal 状态预警
  - **§5 学科 × 认知结构映射**：数学 vs 语文 vs 物理 + ECOS 多学科配置 + 跨学科迁移
  - **§6 关键认知节点与里程碑**：小学 5 个 + 初中 7 个 + 高中 4 个（Phase 5+）
  - **§7 与中国课程标准对接**：核心知识点数 + 课程标准 ↔ ECOS 状态映射
  - **§8 ECOS 产品形态**：小学（高色彩 + 游戏化）/ 初中（数据可视化）/ 高中（极简 + 工具化）
  - **§9 评估指标**（vs 04-risks.md 阈值）：CTA AUC / Bloom 方差 / 双 Agent ECE / TC F1 / 留存率
- **`discussions/2026-06-25-ecos-k12-cog-structure-doc.md`**（本次会话记录）

### 关键差异化设计

| 维度 | 小学 | 初中 | 高中 |
|---|---|---|---|
| **Piaget 阶段** | 具体运算前期 + 中期 | 形式运算初期 | 形式运算成熟 |
| **5D 启用** | 单维为主（K）+ X 重要 | 完整 5D | 完整 5D + 学科专业化 |
| **BloomProfile** | L1 主导（80-90%）| L1-L2 主导（50-60%）+ L3 显著 | L3 主导（30-40%）+ L4 显著 |
| **CLT 默认级别** | NOVICE | DEVELOPING | PROFICIENT |
| **元认知干预** | 不适用 | 有限使用（Articulation）| 完整使用（含 Reflection）|
| **干预时长** | ≤ 15 分钟/次 | ≤ 30 分钟/次 | ≤ 45 分钟/次 |
| **家长端频率** | 每周 | 每月 | 每月或季度 |

### 学段过渡的 ECOS 应对

```
小学 → 初中：抽象思维突然要求
  → TC 检测 + liminal 状态预警（v0.5.0）
  → BloomProfile 重新校准

初中 → 高中：形式化要求
  → BloomProfile 重新校准
  → 干预降级（增加 scaffolding）

高中 → 大学：自主学习能力
  → LearningDNA 推断
  → 元认知型干预完成率
```

### 各学段 TC / Misconception 库规模

| 学段 | TC 候选 | Misconception 候选 |
|---|---|---|
| 小学 | 4 个（分数、负数、乘法意义、守恒）| 3 条 |
| 初中 | 8 个（函数、变量、等式、几何证明、二次函数、极限初步等）| 10 条（v0.5.0 §2.6）|
| 高中 | 7 个（极限严格化、微积分、概率、向量空间等）| 4 条（Phase 5+）|

### Phase 0 进度

| 维度 | 状态 | 完成度 |
|---|---|---|
| 战略层 | ✅ 100% | 4/4 |
| 工程层 | ✅ 100% | 5/5 |
| **教学法层** | **25%（1/4）** | **1/4** |
| MVP 设计 | ⏳ 仅 README 占位 | 0/1 |
| **Phase 0 总完成度** | **~89%** | **11/14** |

### 累计产出（v0.1.0 ~ v0.15.0）

| 类别 | 数量 | 行数（约）|
|---|---|---|
| 战略层 00-overview/ | 4 份 ✅ | ~2400 行 |
| 工程层 10-engineering/ | 5 份 ✅ | ~6100 行 |
| **教学法层 20-pedagogy/** | **1 份（进行中）** | **~520 行** |
| P0 借鉴 theoretical-foundations/ | 4 份 ✅ | ~1700 行 |
| 共享 + AiBeing + 5 轮 + 深度研究 | 8 份（迁移）| — |
| 项目级 + 讨论记录 | 26+ 份 | ~4300 行 |
| **总计** | **~47+ 份** | **~15000+ 行** |

### 下一步

| 优先级 | 任务 | 详见 |
|---|---|---|
| P1 | 教学法层 02-bloom-application.md（Bloom 在 K12 的应用）| `research/20-pedagogy/` |
| P1 | 教学法层 03-learning-strategies.md（学习策略空间）| `research/20-pedagogy/` |
| P1 | 教学法层 04-zpd-application.md（ZPD 在 ECOS 的应用）| `research/20-pedagogy/` |
| P1 | MVP 设计（90-mvp/）| `research/90-mvp/` |
