# CLAUDE.md - ECOS 项目指南

> **本文件是 Claude Code 在 ECOS 项目中的协作指南**。ECOS 是与 SelfLab 并列的独立项目（Educational Cognitive Operating System，教育认知操作系统）。

## 项目性质

**ECOS 是研究规划与技术探讨项目**。本仓库的核心产物是**研究文档**（PRD/ARCH/DESIGN/ROADMAP 等），而不是可复用的应用代码。

所有工作应围绕以下活动展开：
- 研究文档的撰写、评审与迭代
- 双 Agent 架构（CTA + LCA）的设计与论证
- Bloom 目标空间在 K12 教育中的应用
- 技术路线的分析与比较
- 教学法与认知科学的探讨

**项目分阶段的活动边界**：

| 阶段 | 文档产出 | 代码产出 | 产物形态 |
|------|---------|---------|---------|
| **Phase 0（理论奠基，✅ 已完成 2026-06-25）** | 战略层 + 工程层 + 教学法层 + MVP 设计 14 份 | ❌ 无 | 纯研究 |
| **Phase 4（Product Demo 完整化，🔄 进行中）** | 实验报告 + 修订文档 | ✅ 完整 Python 包 + Web UI | 产品 Demo |
| **Phase 5（产品化，✅ 准备启动）** | 实验报告 + 修订文档 | ✅ 完整 Python 包 + Web UI | 完整产品 |
| **Phase 6（系统完善，待启动）** | 研究文档 + 应用原型设计 | ✅ ecos/ Python 包 + 实验代码 | 应用探索 |

> **当前阶段（2026-07-10）**：**Phase 4（Product Demo 完整化）** — 战略调整：聚焦 **Python 基础自学产品 Demo**（完整产品形态）。ECOS 7 组件全部实现并通过 UI 可视化展示：5D+cov/Bloom 6级/TC/LearningDNA/Trajectory/Misconceptions/overall_confidence。详见 [03-roadmap.md v1.2](./research/00-overview/03-roadmap.md)。
> 权威状态源：[README.md §当前状态](./README.md)。任何"当前阶段是 Phase 0"或类似过时标注都以此为准。

**关键区分**：
- **Product Demo 代码 = 可分发应用**：Phase 4 的代码不再是"一次性实验"，而是**完整可展示的产品 Demo**——需要错误处理、边界状态、用户可感知价值
- **ecos/ Python 包**（Phase 4）—— pip install ecos 即可使用，是 ECOS 应用探索的**基础设施**，当前已实现 BeliefEngine/Bloom/MIRT/Misconception/TC 全部核心组件
- **ecos/ Python 包**（Phase 5+）—— 扩展为完整产品化包，含教师端、家长端、跨领域注入

详细约定见 [§实验代码约定](#实验代码约定) 章节。

## Product Demo 代码约定

> **本节定义 Phase 4 Product Demo 代码的边界**——什么允许、什么不允许、放哪里、如何与文档同步。
> **2026-07-10 更新**：Phase 4 从"MVP 能用就行"转向"完整产品 Demo 形态"，本约定同步更新。

### 允许的代码形态

| 形态 | 用途 | 存放位置 | 生命周期 |
|------|------|---------|---------|
| **Jupyter notebook** | 单次实验运行、参数探索、结果可视化 | `experiments/notebooks/` | 实验完成后归档 |
| **ad-hoc 脚本** | 一次性验证（如跑 100 Epoch 收集价值轨迹）| `experiments/scripts/` | 实验完成后归档 |
| **数据处理脚本** | 实验结果分析（统计、可视化、报告生成）| `experiments/analysis/` | 实验完成后归档 |
| **配置文件** | 实验参数（YAML）| `experiments/configs/` | 与对应实验归档 |

### Product Demo 阶段要求

| 形态 | 原因 |
|------|------|
| ~~**可复用的 ecos/ Python 包**~~ | ✅ v0.1.0 已创建包骨架（仅 __init__.py 占位），未来 Phase 4+ 逐步实现 |
| **生产级代码（CI/CD、测试套件、部署配置）** | 这是应用项目，不是研究项目 |
| **无文档的核心组件** | BeliefEngine/MIRT 等核心组件需有模块级 docstring |

### 命名约定

- **API 路由**：`/api/<resource>/<action>`（如 `/api/answer`, `/api/judge`）
- **学生端**：`web/student/index.html`
- **教师端**：`web/teacher/index.html`
- **核心组件**：`ecos/cta/belief_engine.py`, `ecos/cta/l2_mirt.py`

### 与项目级文档的同步

- **实验代码必须与文档关联**：每个 notebook/脚本头部需说明"对应 ROADMAP §M4.1"、"对应 PRD §FR-4"等
- **实验结果必须文档化**：跑完实验后，结果（数据 + 分析）应记录在 `discussions/` 或 `research/90-mvp/` 下的报告中
- **不演进为可复用系统**：实验代码不追求"代码质量"（覆盖率、CI、文档字符串），追求"假设验证"

### 何时停止使用实验代码

- 实验完成后，代码归档（不删除，但不再修改）
- 实验代码不进入主分支的 develop/main 演进路径
- **Phase 4+ 已创建 `ecos/` 包**作为可复用代码的归宿——实验代码保留在 `experiments/`，新可复用代码放 `ecos/`

## 项目背景

ECOS 探索"教育认知操作系统"——AI 能否通过双 Agent 共进化系统（CTA + LCA + Bloom Goal Space）持续理解并帮助 K12 学生成长。核心研究纲领见 `research/` 目录，关键洞察见深度研究文档 v2.0。

## 与 SelfLab 的关系

ECOS 与 SelfLab 是**并列的独立项目**，共享认知科学工具箱但应用方向不同：

| 维度 | SelfLab (SGE) | ECOS |
|------|---------------|------|
| 核心问题 | AI 自我涌现 | AI 理解并帮助学生成长 |
| 核心架构 | 单一 Agent 12 步 | 双 Agent 互校（CTA + LCA）|
| 状态空间 | AI 自身 value/drive | 学生 9D + BloomProfile |
| 借鉴 | 7 个认知科学工具 | 同上（共享）|
| 不借鉴 | 自我/身份涌现 | value/drive（方向错位）|

详细背景见 `research/deep-research/Cognitive-Digital-Twin-Deep-Research.md` v2.0 第 4 部分。

## 用户与协作

**项目发起人**：Bisen
- **背景**：关注 AI 认知架构、教育认知操作系统、人工自我的研究者
- **专业领域**：哲学（现象学、金观涛真实性哲学）、认知科学、AI 架构、教学法
- **协作偏好**：
  - 深度讨论与跨工具协作（同时使用 ChatGPT、Gemini、Claude 等）
  - 重视哲学层面的硬问题（意识、主体性、教育本质）
  - 倾向于结构化、可追溯的文档体系
  - 接受挑战既有框架的批判性思考

**AI 协作伙伴的预期角色**：
- 研究助手：协助文献调研、概念梳理
- 架构师：辅助双 Agent 系统的设计与论证
- 评审者：对设计决策提供批判性反馈
- 文档维护者：确保文档体系的一致性和可追溯性

**协作者背景假设**：当与 Bisen 协作时，默认对方熟悉金观涛真实性哲学、ACT-R/SOAR/LIDA 等经典认知架构、Bloom 分类学、LLM 基础概念。可直接使用专业术语，无需展开基础解释。

## 协作规范

- 文档语言以中文为主，技术术语保留英文
- 研究纲领使用版本号管理（v0.1、v0.2 ...）
- 讨论记录应标注参与者和日期
- 引用外部理论时注明来源

## 核心工作流：探讨 → 洞察 → 修正

每次有价值的讨论应遵循以下闭环流程：

### 第一步：讨论存档

每次深度讨论结束后，将讨论内容保存到 `discussions/` 目录。文件命名格式：

```
discussions/YYYY-MM-DD-主题关键词.md
```

内容应包含：讨论背景、核心观点、论证过程、结论与开放问题。

### 第二步：洞察判断

讨论结束后，判断本次讨论是否产生了**关键洞察**。判断标准：

- 是否提出了新的核心概念或框架？
- 是否修正或推翻了之前的某个假设？
- 是否建立了新的理论映射或类比？
- 是否明确了项目的哲学立场或技术方向？

如果满足以上任一条件，将洞察添加到 ECOS 关键洞察集（待建立 `SGE-Key-Insights.md` 等价物）。

### 第三步：项目文档修正

每条新洞察产生后，检查以下项目级文档是否需要修正：

| 文档 | 检查内容 |
|------|---------|
| research/00-overview/01-applications.md | 核心应用场景是否受影响 |
| research/00-overview/02-architecture.md | 双 Agent 架构是否受影响 |
| research/00-overview/03-roadmap.md | 阶段划分、里程碑、依赖关系是否受影响 |
| research/10-engineering/ | 工程层设计是否受影响 |
| CHANGELOG.md | 记录本次变更 |

如果受影响，修正对应文档，并在 CHANGELOG.md 中记录。

### 第四步：自动同步推送

完成上述所有步骤后，执行 git add、commit 和 push。

### 流程示意

```
深度讨论 / 深度分析
    │
    ▼
【第 0 步】深度分析 → 存档到 research/ 对应子目录
    │
    ▼
【第 1 步】讨论存档 → discussions/YYYY-MM-DD-主题.md
    │
    ▼
【第 2 步】是否产生关键洞察？
    │
    ├── 否 → 继续
    │
    └── 是 → 添加到 ECOS 关键洞察集（待建立）
              │
              ▼
          【第 3 步】检查项目级文档是否需要修正
              │
              ├── 是 → 修正 research/00-overview/ + research/10-engineering/
              │         更新 CHANGELOG.md
              │
              └── 否 → 仅更新 CHANGELOG.md
    │
    ▼
【第 4 步】会话记录 → 在 discussions/ 生成简要记录
    │
    ▼
【第 5 步】git add + commit + push
```

## 目录约定

- `README.md` — 项目入口（含开发环境设置）
- `CLAUDE.md` — Claude Code 协作指南（本文件）
- `CHANGELOG.md` — 变更日志
- `LICENSE` — MIT 许可证
- `pyproject.toml` — Python 包配置（ecos 命名空间）
- `.venv/` — Python 虚拟环境（已 .gitignore，开发时 `pip install -e ".[dev]"`）
- `.env` — LLM API 配置（已 .gitignore，从 `.env.example` 复制）
- `research/` — 核心研究文档
  - `README.md` — SSOT 入口
  - `deep-research/` — 深度研究文档
  - `gpt-dialogues/` — 5 轮 GPT 对话原文
  - `00-overview/` — 战略层（应用、架构、路线图、风险）
  - `10-engineering/` — 工程层（CTA/LCA/双 Agent 实现）
  - `20-pedagogy/` — 教学法层（K12 认知结构、Bloom 应用、学习策略）
  - `30-shared-cognitive-tools/` — 共享认知科学工具箱（与 SelfLab 共享）
  - `40-aibeing-borrowing/` — AiBeing 借鉴（应用层经验）
  - `90-mvp/` — MVP 实施（MVP 设计已完成，Phase 4 启动 M2-M3）
- `references/` — 参考资料（认知架构综述、AiBeing 引擎参考）
- `ecos/` — Python 包骨架（未来实现）
- `experiments/` — Phase 4+ 一次性实验代码
- `discussions/` — 讨论存档
- `prototypes/` — 架构原型设计

> **术语使用约定**：所有 ECOS 文档涉及核心术语时，应与 `references/cognitive-architectures-overview.md` 保持一致。CTA、LCA、Bloom Goal Space、互校循环、信念分布等核心术语定义见 `research/deep-research/Cognitive-Digital-Twin-Deep-Research.md` v2.0 第 3 部分。

## 深度分析存档策略

当用户说"深度分析"或"深度研究"时，默认将分析结果保存为 `research/` 对应子目录下的 MD 文件（00-overview/10-engineering/20-pedagogy/30-shared-cognitive-tools/40-aibeing-borrowing/90-mvp/），而非仅在对话中输出。文件命名应体现主题，格式与现有研究文档保持一致。保存后告知用户文件路径。

当用户说"深度探讨"时，走完整闭环流程（见"核心工作流"章节）。

**会话记录**：无论"深度分析"还是"深度探讨"，每次对话结束时在 `discussions/` 目录生成一个简要的会话记录（`YYYY-MM-DD-主题.md`），包含日期、主题、核心结论、产出文件列表。

## 自动同步推送策略

每次完成内容或文件的增删改任务后，自动执行 git add、commit 和 push，无需用户手动触发。commit message 应简要概括变更内容。

**注意**：本项目是新建立的 Git 仓库，初始 commit 包含所有迁移文件。后续 commit 应保持原子性（每次 commit 只做一类变更）。

## 讨论风格

鼓励批判性思考与深度追问。不回避哲学层面的硬问题（教育本质、认知发展、主体性与学习的关系）。欢迎挑战既有框架，而非仅在框架内做修补。
