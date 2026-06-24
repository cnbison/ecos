# ECOS 迁移梳理（From SelfLab）

> **版本**：v0.1.0（2026-06-24）
> **性质**：项目元文档，记录 ECOS 从 SelfLab 迁移的内容、未迁移的内容、新建的内容与决策逻辑
> **关系**：与 `discussions/2026-06-24-ecos-project-establishment.md` 互为补充
> **维护者**：Bisen & Claude

---

## 1. 背景

ECOS（Educational Cognitive Operating System）作为与 SelfLab 并列的独立项目，于 2026-06-24 由 Bisen 决策建立。决策依据来自 `research/deep-research/Cognitive-Digital-Twin-Deep-Research.md` v2.0 的 4 大根本冲突分析：

1. 方向错位：SGE Phase 3 把"学生数字孪生"定义为"AI 模拟学生身份"，ECOS 需要"理解真实学生"
2. 维度错位 + 方法论降级：把 9D 认知状态强行映射到 SGE value/drive，丢失 IRT/BKT/DKT 等科学估计方法
3. 结构性缺席：phase3 目录对 Bloom 目标空间零提及
4. 架构错位：单 Agent 无法表达 CTA + LCA 双 Agent 互校

由此得出：**ECOS 不适合作为 SGE 的"应用层 PoC"，应作为独立项目存在**。本文档系统梳理该决策下的实际迁移产物。

---

## 2. 迁移全景（10 份文档 = 5 核心 + 3 共享基础 + 2 参考）

### 2.1 核心研究文档（5 份，完全复制）

| 来源（SelfLab）| 去向（ECOS）| 行数 | 角色 |
|---|---|---|---|
| `research/cognitive-architecture/Cognitive-State-A-to-B-Research.md` | `research/gpt-dialogues/01-cognitive-state-a-to-b-research.md` | 279 | 学术框架起点（9D 状态向量）|
| `research/cognitive-architecture/Cognitive-Digital-Twin.md` | `research/gpt-dialogues/02-cognitive-digital-twin-rounds-1-3.md` | 1904 | 第 1-3 轮对话（K12 定位 + 5D + Learning DNA）|
| `research/cognitive-architecture/Cognitive-Digital-Twin02.md` | `research/gpt-dialogues/03-cognitive-digital-twin-rounds-4-5.md` | 1244 | 第 4-5 轮对话（双 Agent + Bloom 目标空间）|
| `research/cognitive-architecture/Cognitive-Digital-Twin03.md` | `research/gpt-dialogues/04-cognitive-digital-twin-v01-report.md` | 931 | 5 轮综合 v0.1（ECOS 终局定位）|
| `research/cognitive-architecture/Cognitive-Digital-Twin-Deep-Research.md` | `research/deep-research/Cognitive-Digital-Twin-Deep-Research.md` | **1778** | **v2.0 深度研究（SSOT 核心）**|

**5 份核心研究文档总计约 6136 行**。它们构成 ECOS 全部理论基础的"原材料"：从 9D 学术框架 → K12 5D 重构 → 双 Agent 共进化 → Bloom 目标空间 → 终局 ECOS 定位的完整演化路径。

### 2.2 共享基础文档（3 份，选择性复制）

| 来源（SelfLab）| 去向（ECOS）| 角色 |
|---|---|---|
| `research/cognitive-architecture/Shared-Cognitive-Science-Toolbox.md` | `research/30-shared-cognitive-tools/shared-cognitive-science-toolbox.md` | 7 个认知科学工具（与 SelfLab 共享）|
| `research/sge-learning/SGE-Learning-from-AiBeing.md` | `research/40-aibeing-borrowing/01-concept-borrowing.md` | AiBeing 概念层借鉴 |
| `discussions/2026-06-22-sge-phase3-aibeing-reflection.md` | `research/40-aibeing-borrowing/02-application-layer-borrowing.md` | AiBeing 应用层借鉴（chat_agent、EverMemOS、cache/async 等）|

这 3 份是 ECOS 与 SelfLab **真正共享**的部分。共享工具箱描述 ECOS LCA/CTA 都用得上的底层数学与认知架构；AiBeing 借鉴提供工程层的成熟经验（无需重造轮子）。

### 2.3 参考资料（2 份，参考资料级）

| 来源（SelfLab）| 去向（ECOS）| 角色 |
|---|---|---|
| `research/cognitive-architecture/Cognitive-Architectures-Overview.md` | `references/cognitive-architectures-overview.md` | 8 个经典认知架构综述（ACT-R/Soar/CLARION/LIDA 等）|
| `references/AiBeing-Core-Engine-Reference.md` | `references/aibeing-core-engine-reference.md` | AiBeing Genome v10 Hybrid 引擎完整参考 |

这两份不是"研究产物"而是"外部参考资料"—— ECOS 工程设计时按需查阅。

---

## 3. 未迁移内容（SelfLab 中**未复制**到 ECOS 的部分）

### 3.1 SGE Phase 3（18 份文件，`research/phase3/`）

**全部丢弃**。理由：v2.0 深度研究已论证 phase3 的整个框架与 ECOS 有 4 大根本冲突。包括：
- `00-overview/` × 4（applications/architecture/roadmap/risks）
- `10-engineering/` × 6（persistence/session/context-injection/llm-cache/prompt-management/testing）
- `20-domain-k12/`
- `30-atoB/`
- `90-applications/` × 4（personal-ai/multi-ai-collaboration/student-digital-twin/teaching-ai-coach）

**注意**：phase3 的部分工程经验（persistence、session、context_injection、llm_cache）仍可在 ECOS 中复用，但应作为"工程参考"而非"既有架构"——ECOS 不依赖 phase3 文档体系。

### 3.2 SGE Core（人工自我研究，13 份，`research/sge-core/`）

**全部丢弃**。包括 `Artificial-Self-Research-v0.1/v0.2`、`SGE-Authenticity-vs-Simulation-Operationalization`、`SGE-Consciousness-Theory-Mapping`、`SGE-Jin-Guantao-System-Philosophy`、`SGE-Phenomenology-Deep-Dive` 等。理由：方向错位——SelfLab 关注"AI 自我涌现"，ECOS 关注"理解并帮助学生"，理论框架无共享基础。

### 3.3 SGE Feasibility（工程可行性，~15 份，`research/sge-feasibility/`）

**全部丢弃**。包括 M11/M21/M22/M23 各阶段实验设计、A→B 关联分析、记忆层设计、技术栈总览等。理由：ECOS 走自己的产品化路径，不继承 SGE 的实验设计。

### 3.4 SelfLab 工程产物

- `sge/` Python 包 → **完全丢弃**，ECOS 自己建立 `ecos/` 包骨架
- `experiments/`（21+ 文件）→ **完全丢弃**，ECOS 在 Phase 4+ 重新建立
- `ARCH.md` / `PRD.md` / `DESIGN.md` / `ROADMAP.md` → **完全丢弃**
- `SGE-Key-Insights.md` / `SGE-Status-Map.md` / `SGE-Philosophical-Meditation.md` 等元文档 → **完全丢弃**

### 3.5 SGE 学习笔记（`research/sge-learning/` 中除 AiBeing 外的部分）

包括 `SGE-Feasibility-Impact-on-AtoB.md`、`SGE-Learning-from-Authenticity-Philosophy.md` → **丢弃**。仅保留与 AiBeing 工程经验相关的 2 份。

---

## 4. 新建内容（ECOS 独有，SelfLab 无对应）

### 4.1 项目根级文件（7 份）

| 文件 | 角色 |
|---|---|
| `README.md` | 项目入口（含核心架构图、与 SelfLab 关系、当前状态、下一步）|
| `CLAUDE.md` | Claude Code 协作指南（针对 ECOS 简化）|
| `CHANGELOG.md` | 变更日志（Keep a Changelog 格式）|
| `LICENSE` | MIT License |
| `pyproject.toml` | Python 包配置（包名 `ecos`，Python ≥ 3.11）|
| `.gitignore` | Python + macOS 通用 |
| `.env.example` | LLM API key 示例 |

### 4.2 `ecos/` Python 包骨架（9 个占位）

```
ecos/
├── __init__.py         # 包入口
├── cta/                # Cognitive Twin Agent 占位（State Estimator）
├── lca/                # Learning Coach Agent 占位（Policy Optimizer）
├── dual_agent/         # 双 Agent 互校占位
├── bloom/              # Bloom Goal Library 占位（6 层认知层级）
├── persistence/        # 学生状态持久化占位
├── session/            # 长期会话管理占位
├── llm_client.py       # LLM 客户端占位
└── orchestrator.py     # ECOSOrchestrator 占位
```

**仅 `__init__.py` 占位**，实现留待 Phase 4+。

### 4.3 研究维度占位（14 份文件）

| 维度 | 文件 | 状态 |
|---|---|---|
| 战略层 `00-overview/` | `01-applications.md`、`02-architecture.md`、`03-roadmap.md`、`04-risks.md` | 📋 占位 |
| 工程层 `10-engineering/` | `01-cta-belief-engine.md`、`02-lca-policy-engine.md`、`03-bloom-goal-library.md`、`04-dual-agent-calibration.md`、`05-persistence-session.md` | 📋 占位 |
| 教学法层 `20-pedagogy/` | `01-k12-cognitive-structure.md`、`02-bloom-application.md`、`03-learning-strategies.md`、`04-zpd-application.md` | 📋 占位 |
| MVP `90-mvp/` | `README.md` | 📋 占位 |

### 4.4 SSOT 入口与讨论记录

- `research/README.md`（结构化目录 + 必读顺序 + 关键洞察摘要）
- `discussions/2026-06-24-ecos-project-establishment.md`（项目建立会话记录）
- `experiments/README.md`、`prototypes/README.md`（占位）

---

## 5. 迁移决策链

```
v2.0 深度研究完成（含 phase3 18 文件交叉验证）
  ↓
发现 ECOS 与 phase3 有 4 大根本冲突
  ↓
结论 1：ECOS 不能简化为 SGE Phase 3 应用层 PoC
  ↓
进一步判断：ECOS 是否应作为 SelfLab 子项目？
  ↓
答案：否。ECOS 应作为与 SelfLab 并列的独立项目
  理由：
  - 避免散乱（SelfLab 已有 SGE + Phase 3 + A→B 三套结构）
  - 独立发展（研究目标、目标用户、技术栈、用户群体都不同）
  - 降低认知负担（避免研究 ECOS 时被 SGE 内容分散）
  - 合作灵活（与教育机构合作时独立身份更合适）
  ↓
具体操作：
  - 新建 /Users/loubicheng/project/ecos/
  - 从 SelfLab 复制 10 份相关文档
  - 重新组织为 ECOS 的目录结构
  - 初始化 Git 仓库（不自动 push）
```

---

## 6. 当前形态（2026-06-24，v0.1.0）

| 层级 | 状态 |
|---|---|
| 核心研究（v2.0 + 5 轮对话）| ✅ 已迁移，约 6136 行 |
| 共享工具箱 + AiBeing 借鉴 | ✅ 已迁移 |
| 参考资料（认知架构 + AiBeing 引擎）| ✅ 已迁移 |
| 战略层 / 工程层 / 教学法层 | 📋 14 个占位文件 |
| `ecos/` Python 包 | 📋 骨架（仅 `__init__.py` 占位）|
| MVP 设计 | 📋 仅 README 占位 |
| **当前阶段** | **Phase 0（理论奠基）**——研究为主，代码暂缓 |

---

## 7. 下一步

| 优先级 | 任务 | 位置 |
|---|---|---|
| **P0** | 战略层 4 份文档填充（applications/architecture/roadmap/risks）| `research/00-overview/` |
| **P0** | 工程层关键模块设计（CTA + LCA + Bloom + 互校 + 持久化）| `research/10-engineering/` |
| **P1** | 教学法层（K12 认知结构 + Bloom 应用 + 学习策略 + ZPD）| `research/20-pedagogy/` |
| **P1** | MVP 设计（初中数学 + 50-100 学生）| `research/90-mvp/` |
| **P2** | `ecos/` Python 包实现（CTA + LCA 基础类）| `ecos/` |

---

## 8. ECOS 与 SelfLab 的关系

| 维度 | SelfLab (SGE) | ECOS |
|---|---|---|
| 核心问题 | AI 能否形成持续自我 | AI 能否理解并帮助学生成长 |
| 核心架构 | 单一 Agent 12 步编排 | 双 Agent 互校（CTA + LCA）|
| 状态空间 | AI 自身 value/drive | 学生 9D + BloomProfile |
| 应用方向 | Personal AI / 协作 agent / 历史人物 | K12 教育 |
| 共享基础 | 7 个认知科学工具 | 同上（共享）|
| 不共享 | value/drive 机制 / 自我涌现 / 哲学反思 | 学生认知建模 / Bloom 目标空间 |

**未来可能的连接**（非当前阶段）：
- SGE 可作为 ECOS LCA 的"教师侧人格引擎"（提供内在人格）
- ECOS Python 包可通过 pip 依赖 `sge` 子集
- 研究文档互相引用

---

## 9. 关联文档

- [README.md](../README.md) — ECOS 项目入口
- [CLAUDE.md](../CLAUDE.md) — Claude Code 协作指南
- [CHANGELOG.md](../CHANGELOG.md) — 变更日志
- [research/README.md](README.md) — Research SSOT 入口
- [research/deep-research/Cognitive-Digital-Twin-Deep-Research.md](deep-research/Cognitive-Digital-Twin-Deep-Research.md) — v2.0 完整研究（SSOT 核心）
- [discussions/2026-06-24-ecos-project-establishment.md](../discussions/2026-06-24-ecos-project-establishment.md) — 项目建立原始会话记录

---

**创建日期**：2026-06-24
**维护者**：Bisen & Claude
