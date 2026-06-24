# 2026-06-24 · ECOS 独立项目建立

## 主题

建立 ECOS（Educational Cognitive Operating System）独立项目，作为与 SelfLab 并列的兄弟项目。完成从 SelfLab 的 10 份文档迁移，初始化 Git 仓库，建立完整项目结构。

## 日期

2026-06-24

## 背景

Bisen 在 v2.0 深度研究文档（`research/deep-research/Cognitive-Digital-Twin-Deep-Research.md`）的 4 大冲突分析中已经判断 ECOS 不适合作为 SGE 的"应用"。进一步思考后，Bisen 认为 **ECOS 更适合作为与 SelfLab 并列的独立项目**，而不是 SelfLab 的子项目。

理由：

1. **避免散乱**：SelfLab 已有 SGE（主项目）+ Phase 3（应用化）+ A→B（调研子项目），再加 ECOS 子项目会让目录结构复杂
2. **独立发展**：SGE 关注"AI 自我涌现"，ECOS 关注"教育认知操作系统"——研究目标、目标用户、技术栈、用户群体都不同
3. **降低认知负担**：Bisen 在研究 ECOS 时被 SGE 内容分散注意力
4. **合作灵活**：未来 ECOS 与教育机构合作时，独立项目身份更合适

## 决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 项目名 | ECOS | 短、好记、与 sge/ecos Python 包名一致 |
| 项目路径 | /Users/loubicheng/project/ecos | 与 SelfLab 同级，独立的 Git 仓库 |
| SelfLab 端处理 | 删除并标注已迁移 | 目录最干净 |
| Git 初始化 | 初始化为新仓库（不自动 push）| 让 Bisen 决定何时推送到 GitHub |

## 核心架构

```
┌──────────────────────────────────────────────────────────┐
│              Bloom Goal Space（目标坐标系）                 │
│  Remember → Understand → Apply → Analyze → Evaluate → Create │
└──────────────────────────────────────────────────────────┘
                            ↕
┌──────────────────────────────────────────────────────────┐
│       Learning Coach Agent (LCA) — Policy Optimizer       │
└──────────────────────────────────────────────────────────┘
                            ↕
┌──────────────────────────────────────────────────────────┐
│     Cognitive Twin Agent (CTA) — State Estimator          │
│     状态：K/P/S/C/X + BloomProfile + LearningDNA + Trajectory │
└──────────────────────────────────────────────────────────┘
                            ↕
                         Student
```

## 产出文件

### 完全复制（5 份核心研究文档）

| SelfLab 源 | ECOS 目标 |
|----------|---------|
| `research/cognitive-architecture/Cognitive-State-A-to-B-Research.md` | `research/gpt-dialogues/01-cognitive-state-a-to-b-research.md` |
| `research/cognitive-architecture/Cognitive-Digital-Twin.md` | `research/gpt-dialogues/02-cognitive-digital-twin-rounds-1-3.md` |
| `research/cognitive-architecture/Cognitive-Digital-Twin02.md` | `research/gpt-dialogues/03-cognitive-digital-twin-rounds-4-5.md` |
| `research/cognitive-architecture/Cognitive-Digital-Twin03.md` | `research/gpt-dialogues/04-cognitive-digital-twin-v01-report.md` |
| `research/cognitive-architecture/Cognitive-Digital-Twin-Deep-Research.md` | `research/deep-research/Cognitive-Digital-Twin-Deep-Research.md` |

### 选择性复制（3 份共享基础参考）

| SelfLab 源 | ECOS 目标 |
|----------|---------|
| `research/cognitive-architecture/Shared-Cognitive-Science-Toolbox.md` | `research/30-shared-cognitive-tools/shared-cognitive-science-toolbox.md` |
| `research/sge-learning/SGE-Learning-from-AiBeing.md` | `research/40-aibeing-borrowing/01-concept-borrowing.md` |
| `discussions/2026-06-22-sge-phase3-aibeing-reflection.md` | `research/40-aibeing-borrowing/02-application-layer-borrowing.md` |

### 选择性复制（2 份参考资料）

| SelfLab 源 | ECOS 目标 |
|----------|---------|
| `research/cognitive-architecture/Cognitive-Architectures-Overview.md` | `references/cognitive-architectures-overview.md` |
| `references/AiBeing-Core-Engine-Reference.md` | `references/aibeing-core-engine-reference.md` |

### 新建（项目根级文件 + 包骨架 + 占位 + 入口）

- README.md, CLAUDE.md, CHANGELOG.md, LICENSE, pyproject.toml, .gitignore, .env.example
- ecos/ Python 包骨架（9 个 __init__.py + llm_client.py + orchestrator.py）
- 14 个研究维度占位文件
- experiments/README.md, prototypes/README.md
- research/README.md SSOT 入口
- discussions/2026-06-24-ecos-project-establishment.md（本文件）

## 项目结构

```
/Users/loubicheng/project/ecos/
├── README.md
├── CLAUDE.md
├── CHANGELOG.md
├── LICENSE
├── pyproject.toml
├── .gitignore
├── .env.example
├── ecos/                          # Python 包骨架
│   ├── __init__.py
│   ├── cta/
│   ├── lca/
│   ├── dual_agent/
│   ├── bloom/
│   ├── persistence/
│   ├── session/
│   ├── llm_client.py
│   └── orchestrator.py
├── research/
│   ├── README.md
│   ├── deep-research/
│   │   └── Cognitive-Digital-Twin-Deep-Research.md  (1778 行)
│   ├── gpt-dialogues/
│   │   ├── 01-cognitive-state-a-to-b-research.md
│   │   ├── 02-cognitive-digital-twin-rounds-1-3.md
│   │   ├── 03-cognitive-digital-twin-rounds-4-5.md
│   │   └── 04-cognitive-digital-twin-v01-report.md
│   ├── 00-overview/                # 4 个战略层占位
│   ├── 10-engineering/             # 5 个工程层占位
│   ├── 20-pedagogy/                # 4 个教学法占位
│   ├── 30-shared-cognitive-tools/  # 共享工具箱（已迁移）
│   ├── 40-aibeing-borrowing/       # AiBeing 借鉴（已迁移）
│   └── 90-mvp/                     # MVP 实施
├── references/                     # 2 份参考资料
├── experiments/                    # 占位
├── discussions/                    # 会话记录
└── prototypes/                     # 占位
```

## 当前状态（v0.1.0）

| 层级 | 状态 |
|------|------|
| 战略层 | 📋 占位（待 Phase 4.1 填充）|
| 工程层 | 📋 占位 |
| 教学法层 | 📋 占位 |
| 共享工具箱 | ✅ 已建立 |
| AiBeing 借鉴 | ✅ 已建立 |
| MVP 实施 | 📋 占位 |
| Python 包 | 📋 骨架（__init__.py 占位）|
| 深度研究 | ✅ v2.0 |
| 5 轮对话 | ✅ 已迁移 |

## 下一步

| 优先级 | 任务 | 详见 |
|--------|------|------|
| P0 | 战略层 4 份文档填充 | `research/00-overview/` |
| P0 | 工程层关键模块设计 | `research/10-engineering/` |
| P1 | 教学法层 K12 认知结构 | `research/20-pedagogy/` |
| P1 | MVP 设计（初中数学 + 50-100 学生）| `research/90-mvp/` |
| P2 | Python 包实现 | `ecos/` |

## 与 SelfLab 的关系

ECOS 是与 SelfLab 并列的独立项目：

| 维度 | SelfLab (SGE) | ECOS |
|------|---------------|------|
| 核心问题 | AI 自我涌现 | AI 理解并帮助学生成长 |
| 核心架构 | 单一 Agent 12 步 | 双 Agent 互校（CTA + LCA）|
| 状态空间 | AI 自身 value/drive | 学生 9D + BloomProfile |
| 共享基础 | 7 个认知科学工具 | 同上（共享）|
| 不共享 | 自我/身份涌现 | value/drive（方向错位）|

**未来可能的连接**：
- SGE 可作为 ECOS LCA 的"教师侧人格引擎"（提供内在人格）
- ECOS Python 包可通过 pip 依赖 `sge` 子集
- 研究文档互相引用

## 关联文档

- [README.md](../../README.md) — ECOS 项目入口
- [CLAUDE.md](../../CLAUDE.md) — Claude Code 协作指南
- [research/README.md](../README.md) — Research SSOT 入口
- [research/deep-research/Cognitive-Digital-Twin-Deep-Research.md](../deep-research/Cognitive-Digital-Twin-Deep-Research.md) — v2.0 完整研究

## SelfLab 端处理

详见 [SelfLab discussions/2026-06-24-ecos-independent-project-decision.md](https://github.com/cnbison/SelfLab/blob/main/discussions/2026-06-24-ecos-independent-project-decision.md)

---

**维护者**：Bisen & Claude
**创建日期**：2026-06-24
**版本**：v0.1.0
