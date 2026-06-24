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
| 0.1.0 | 2026-06-24 | (本次) | **项目初始建立**：从 SelfLab 迁移 5 份核心研究文档（5 轮 GPT 对话 + 深度研究 v2.0）+ 5 份选择性参考文档（共享工具箱 + 认知架构综述 + AiBeing 借鉴 + 借鉴分析）+ 14 个研究维度占位文件（00-overview/10-engineering/20-pedagogy/90-mvp）+ ecos/ Python 包骨架（9 个 __init__.py 占位 + llm_client.py + orchestrator.py）+ 完整项目级文档（README/CLAUDE/CHANGELOG/LICENSE/pyproject.toml/.gitignore/.env.example）|

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
