# 2026-06-24 · ECOS 迁移梳理会话记录

## 主题

ECOS 独立项目建立后，对从 SelfLab 迁移过来的内容进行系统梳理，生成项目级元文档。

## 日期

2026-06-24

## 背景

ECOS 已于 2026-06-24 完成 v0.1.0 初始建立（详见 [2026-06-24-ecos-project-establishment.md](2026-06-24-ecos-project-establishment.md)）。本次会话对迁移内容做一次系统性梳理，让 Bisen 对项目当前形态有清晰的全局图。

## 核心结论

### 迁移全景

- **5 份核心研究文档**（约 6136 行）—— 从 SelfLab `research/cognitive-architecture/` 完全复制
- **3 份共享基础文档**—— 共享工具箱 + AiBeing 概念层 + 应用层借鉴
- **2 份参考资料**—— 经典认知架构综述 + AiBeing 引擎参考
- **总计 10 份文档迁移**

### 未迁移内容

SelfLab 中以下内容被有意识地丢弃：
- **SGE Phase 3**（18 文件）—— 与 ECOS 有 4 大根本冲突
- **SGE Core**（13 文件）—— 人工自我研究，方向错位
- **SGE Feasibility**（~15 文件）—— 工程可行性，ECOS 走自己的路径
- **SelfLab 工程产物**（`sge/` 包、`experiments/`、`ARCH/PRD/DESIGN/ROADMAP`）—— 独立项目身份

### 新建内容

- **7 个项目根级文件**（README/CLAUDE/CHANGELOG/LICENSE/pyproject.toml/.gitignore/.env.example）
- **9 个 Python 包占位**（`ecos/cta/lca/dual_agent/bloom/persistence/session` + llm_client + orchestrator）
- **14 个研究维度占位**（00-overview/10-engineering/20-pedagogy/90-mvp）
- **SSOT 入口 + 讨论记录**

### 当前形态

| 层级 | 状态 |
|---|---|
| 核心研究 | ✅ 已迁移 |
| 共享工具箱 + AiBeing 借鉴 | ✅ 已迁移 |
| 战略/工程/教学法层 | 📋 占位 |
| Python 包 | 📋 骨架 |
| MVP 设计 | 📋 占位 |
| **当前阶段** | **Phase 0（理论奠基）**|

### 下一步 P0

- 战略层 4 份文档填充（`research/00-overview/`）
- 工程层关键模块设计（`research/10-engineering/`）

## 产出文件

| 文件 | 角色 |
|---|---|
| `research/MIGRATION-FROM-SELFLAB.md` | **主文档**——迁移梳理元文档（9 章节，约 220 行）|
| `discussions/2026-06-24-ecos-migration-overview.md` | **本文件**——本次会话简要记录 |

## 关联文档

- [README.md](../README.md) — ECOS 项目入口
- [CHANGELOG.md](../CHANGELOG.md) — 变更日志
- [research/README.md](../research/README.md) — Research SSOT 入口
- [research/deep-research/Cognitive-Digital-Twin-Deep-Research.md](../research/deep-research/Cognitive-Digital-Twin-Deep-Research.md) — v2.0 核心研究
- [discussions/2026-06-24-ecos-project-establishment.md](2026-06-24-ecos-project-establishment.md) — 项目建立原始记录
- [research/MIGRATION-FROM-SELFLAB.md](../research/MIGRATION-FROM-SELFLAB.md) — 本次主产出

---

**创建日期**：2026-06-24
**维护者**：Bisen & Claude
**版本**：v0.1.0
