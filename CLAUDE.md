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

> **当前阶段（2026-07-22）**：**Phase 4（Product Demo 完整化）** — ✅ 实际完成 v0.52.3 (Bisen 自定义 Phase 1-4 全部落地, 含 5D 视觉化 / 答题历史 / Tab 导航 / Phase 4 架构现代化)。
> ECOS 7 组件: 5D+cov / Bloom 6级 / TC 状态 / LearningDNA (标"待启用") / Trajectory / Misconceptions / overall_confidence。
> 详见 [03-roadmap.md](./research/00-overview/03-roadmap.md) (v1.3 → v1.4 待更新)。
>
> **当前已知重大弊端 (Bisen 2026-07-22 测试发现)**:
> - **Partial Credit 缺失** — 学生答对 70% 但缺 I/O 时, ECOS 按 0% 处理, K 维度多跌 0.27, L6 多跌 0.2。Phase 5 必修。
>   详见 [discussions/2026-07-22-partial-credit重大学术弊端发现.md](./discussions/2026-07-22-partial-credit重大学术弊端发现.md)
> - **C/X 维度 0 主导题** — 5D 评估实际是 3D 评估 (K/P/S 真评估, C/X 标"待启用")。Phase 5 重新设计 C/X 主导题。
>   详见 [discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md](./discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md)
> - **ECOS 端到端流程** — 8 阶段闭环 + 5D/Bloom 数值变化的通俗化解读 (Bisen 触发 2026-07-22)
>   详见 [research/90-mvp/06-ecos-end-to-end-flow-analysis.md](./research/90-mvp/06-ecos-end-to-end-flow-analysis.md)
>
> **lbc001 27 道题测试发现 4 个 BUG** (2026-07-21):
> 详见 [discussions/2026-07-21-lbc001测试发现4个BUG分析与修复计划.md](./discussions/2026-07-21-lbc001测试发现4个BUG分析与修复计划.md)
>
> 权威状态源：[README.md §当前状态](./README.md)。任何"当前阶段是 Phase 0"或类似过时标注都以此为准。

**关键区分**：
- **Product Demo 代码 = 可分发应用**：Phase 4 的代码不再是"一次性实验"，而是**完整可展示的产品 Demo**——需要错误处理、边界状态、用户可感知价值
- **ecos/ Python 包**（Phase 4）—— pip install ecos 即可使用，是 ECOS 应用探索的**基础设施**，当前已实现 BeliefEngine/Bloom/MIRT/Misconception/TC 全部核心组件
- **ecos/ Python 包**（Phase 5+）—— 扩展为完整产品化包，含教师端、家长端、跨领域注入

**Bisen 自定义 Phase 1-4 路线 (UI 改进, 跟 ROADMAP Phase 0/4/5/6 不同)**:
| Phase | 内容 | 状态 | 版本 |
|---|---|---|---|
| 1 | 顶栏精简 / 题目合并 / 轨迹折叠 / 2 位小数 | ✅ | v0.48.7-0.49.0 |
| 2 | Tab 导航 (学习/轨迹/设置) | ✅ | v0.49.1 |
| 3 | CSS 变量 / 进度条 8px / SVG 图标 | ✅ | v0.50.0 |
| 4 | 拆文件 / API 封装 / URL hash 路由 | ✅ (C 状态管理留 v0.52.0) | v0.51.0 |
| 5 | 状态管理 (App 对象) | 📋 后续 | v0.52.0+ |

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

## 防御性自检规范（2026-07-19 Bisen 反馈后新增，v0.55.0 自动化）

> 起源：本日（2026-07-19）项目连发 6 个 commit，期间 Bisen 多次反馈"重启后状态丢失"、"重启后题目从头开始"、"重启后错一题 K 暴跌 0.91"、"成长轨迹只显示 10 条"、"CSS 没生效纯文本显示"等连续 bug。
>
> 反思：根因是"修一处即提交一处"心态——每次只修 Bisen 报的那一个点，没顺手做同类问题扫描，**导致同一类问题（silent pass、版本号、文件引用、字段恢复）在 1-2 周内反复出现 3 次以上**。
>
> 本节规范从此强制生效。
>
> **v0.55.0 自动化** (2026-07-23)：5 项防御性自检 + pytest 22 测试已统一到 `bash scripts/check_defensive.sh`，本地 `make check` / GitHub Actions `.github/workflows/test.yml` 都跑，避免手动漏检。详见 [§v0.55.0 pytest 自动化套件](#v0550-pytest-自动化套件-2207-23-新增)。

### 每次 commit 前的自检清单（必跑）

```bash
# 1) silent failure 扫描：禁止新增 'except Exception: pass' / 'except: continue'
grep -nE "except.*: *$" --include="*.py" -r ecos/ web/
#   输出任何 'except Exception: pass' 都先改成 logger.warning(..., exc_info=True)

# 2) 版本号同步检查：ecos/__init__.py 是否 bump
grep "__version__" ecos/__init__.py
#   commit message 含功能/修复时,版本号必须同步 bump,否则 push 前补

# 3) git diff stat 全文扫一遍
git diff --stat HEAD
#   任何"看起来跟当前任务无关"的文件改动都要确认意图

# 4) CSS 引用关系检查（动样式时）
grep "<link rel=stylesheet\|<style" web/student/index.html
#   v0.51.0 Phase 4 拆文件后: student CSS 在独立 styles.css, HTML <link> 引用 + ?v= cache-busting
#   Flask 静态路由 /student/<path:filename> + no-cache header 防缓存
#   v0.47.3 教训: 改样式没 link 引用 → 浏览器只看到 inline 旧版样式 (修复前是 inline)
#   ⚠️ 改 CSS 选择器时, 同步 grep HTML class 名确认匹配 (v0.50.0 5D badge class 错配教训)

# 5) DB 恢复路径检查（动 belief.py / db.py 时）
grep -n "_get_or_create_student\|save_student_state\|load_student_state" web/api/belief.py ecos/persistence/db.py
#   任何 DB 恢复字段变更,都要查"对应持久化字段是否也恢复"——历史上至少 3 次漏
#   (import json 漏 import / tc_states 漏 / trajectory 漏 / item_params 漏)
```

### 修一处 bug 时的"同类模式扫描"

**规范**：修一个 bug 后，**至少 grep 一次**确认同类问题没在别处出现。

- 修 `except: pass` → grep `except.*pass` 全文件
- 修 `_get_or_create_student` 恢复流程 → grep `_STUDENT_STATES` 全部字段，检查持久化是否对齐
- 修 `__version__` 漏 bump → grep `__version__` + git log 最近 5 个 commit 的 `__version__` 改动
- 修 CSS 渲染 → grep `<link rel=stylesheet` 确认是 inline 还是外链

### commit message 表达规范

**禁止**混用"已做"和"计划"标记，导致 Bisen 误以为已落地。

- ✅ 已做：用 `✅` / `🆕` / 直接陈述
- 📋 计划 / TODO：用 `📋 后续` / `Phase X+ 计划` / `TODO:`
- commit message 末尾的 "后续" 章节**单独标注**，不与主变更混排

### 沉默失败原则

> 任何 `except ...: pass`（无日志、无告警）都是 **anti-pattern**。
> 必须改成 `except ...: _log.warning(..., exc_info=True)` 或显式 `raise`。
>
> 例外：仅在 `__init__.py` 的 `Optional` import 兜底，或 `feature flag` 关闭分支允许 silent pass——但**必须加注释说明**。

### v0.55.0 pytest 自动化套件 (2026-07-23 新增)

**入口**：
- 本地：`bash scripts/check_defensive.sh` 或 `make check`
- GitHub Actions：`.github/workflows/test.yml` (push main / PR main / 手动触发)
- pytest：`make test` 或 `python -m pytest tests/ -v`

**5 项防御性自检**（自动化）：

| # | 项 | 拦截历史 | 工具 |
|---|----|---------|-----|
| 1 | silent pass 扫描 | v0.47.5 / v0.53.3 / v0.55.0-a (qmatrix.py 2 处) | `grep` 排除注释行 + 测试代码 |
| 2 | `__version__` 同步 | 多次漏 bump 致 API report hardcoded | 提取 `ecos/__init__.py` 单一权威源 |
| 3 | `detect_with_hits` 传 `library_str` | v0.52.0 BUG 2.1 库 ID 错配 | multi-line grep + 排除函数定义 + 注释行 |
| 4 | HTML class 与 CSS 对齐 | v0.47.3 inline / v0.50.0 5D badge class 错配 | `grep` HTML class vs CSS 选择器 (warning) |
| 5 | DB 恢复 6 关键字段 | 4 次漏字段 (json/tc_states/trajectory/item_params) | 检查 6 字段全在 belief.py + db.py |

**22 pytest 测试**（4 个文件）：
- `test_defensive.py` (5)：5 项防御性自检的 pytest 版本（CI gate）
- `test_partial_credit.py` (5)：partial credit + MIRT 回归保护
- `test_dual_layer.py` (2)：5D 双层架构（领域无关核心 + 编程应用层）
- `test_cross_subject.py` (10)：跨学科迁移（5 学科 × 2 维度 = 10 测试）

### 计划中的防御机制（v0.47.6+ TODO）

- [x] **CI gate v0.52.0**：写 commit message 列"已做"功能时, 必须 devtools 验证功能**真在跑**（BUG 防止）
  - 触发背景: Bisen 4 次反馈"虚标"bug:
    - v0.50.0 5D badge CSS class 名错配 (HTML `f-lbl` vs CSS `.lbl`)
    - v0.50.0 把 LearningDNA 列为"7 组件完整产品形态"但 confidence=0.0 永远不涨
    - v0.51.0 Phase 4 拆文件后 URL hash 路由忘了 auto-start
    - v0.51.4 设置页 hardcoded 版本号没动态化
    - v0.52.0 写 commit message "P0 必修"但 engine.update 内部 misconception
      检测库 ID 错配 + belief.py 末尾独立检测结果不写回 state (lbc001 22 道
      题 0 个 misconception 命中)
  - 实施: 写功能前 `grep -E 'state\.\w+\.confidence\s*='` 确认组件真有 update
    逻辑; dashboard 展示的"7 组件"必须 devtools 看 1 轮答题后至少 1 个组件
    confidence 变化
  - 防 3 次同类: 未来 commit 列组件/字段前, 必须先看代码确认实现, 不能再
    "写 message 时想当然"
  - **v0.55.0 自动化**：5 项自检 + pytest 22 测试全跑,任何"虚标"功能若代码
    没真实现,CI 必 fail
- [x] **CI gate v0.52.0**：库 ID 错配 (BUG 2.1 教训)
  - 触发背景: `_llm_critic_misconception` 调 `detect_with_hits()` 没传
    `library_str`, detector fallback 到 K12 通用数学库 M1-M30, 但实际
    需要 Python misconception 库 M1-M8 → LLM 永远找不到 Python 相关的 M3
  - 实施: 任何 `detect_with_hits(...)` / `detect(...)` 调用必须显式传
    `library_str=...`, 不能依赖默认; 配合 git grep 自检:
    `git grep -nE 'detect_with_hits|self\.misc_detector\.detect' -- ecos/ web/`
  - 防 3 次同类: 任何 detector 调用, library_str 都是必需参数, 必须传
  - **v0.55.0 自动化**：[3/5] 防御性自检 `scripts/check_defensive.sh` 已拦截
    任何 detect 调用未传 library_str
- [x] **CI gate v0.52.2**：MIRT 简化 (partial credit 缺失) (Bisen 2026-07-22 反馈)
  - 触发背景: lbc001 答 PB-Q18 (L6 variables) 截图分析
    - 学生答: 核心算法对 (提取个/十/百位 + 倒序组合), 缺 input()/print()
    - AI 评判: ❌ 完全错 (`correct: false`)
    - 5D 影响: K 1.18 → 0.9638 (跌 0.22)
    - 70% 答对被当 0% 答对处理, K 多跌 0.27, L6 多跌 0.2
    - 详见 [discussions/2026-07-22-partial-credit重大学术弊端发现.md](./discussions/2026-07-22-partial-credit重大学术弊端发现.md)
  - 实施: Phase 5 partial credit 必修, 短期 v0.52.2 已存 AI reasoning
    留历史数据训练
  - 防 3 次同类: 任何"MIRT 二元对错"假设的延伸改动, 必须确认是否引入
    partial credit 缺失风险
  - **v0.55.0 自动化**：`tests/test_partial_credit.py` 5 测试保护
    - test_mirt_partial_score_continuous (l2_mirt.py:135 公式接受 [0,1] 连续)
    - test_partial_credit_reduces_k_decline (lbc001 PB-Q18 跌幅 < 0.10)
    - test_response_history_score_compat (老数据 fallback)
    - test_mirt_estimate_theta_continuous_inputs (estimate_theta 接受连续值)
    - test_mirt_estimate_theta_discrete_backward_compat (老用法 [0,1] 仍工作)
- [x] **CI gate v0.55.0-a**：silent pass 扫描 (防御性自检 [1/5])
  - 实施: `scripts/check_defensive.sh` 第 1 项,排除注释行 + 测试代码
  - 防 5 次同类: silent pass 必改成 `logger.warning(..., exc_info=True)`
- [x] **CI gate v0.55.0-c**：5D 双层架构 (领域无关核心 + 领域特定扩展)
  - 实施: `tests/test_dual_layer.py` 2 测试
    - test_5d_core_C_is_confidence_dimension (C 必须是 ConfidenceDimensionState)
    - test_q_matrix_dual_layer_isolation (PC-C/PC-X 跨学科 vs PB-C 编程隔离)
  - 防 v0.54.1-d 教训: C 维度定义漂移 (Confidence vs Common mistakes)
- [x] **CI gate v0.55.0-d**：跨学科迁移 5 学科 slot
  - 实施: `tests/test_cross_subject.py` 10 测试
    - 5 学科 (math/chinese/english/physics/chemistry) 各 10 道设计目标
    - 当前 5 学科扩展 0 题,防 v0.56.0+ 之前虚标
  - 防 v0.54.1-e 教训: 5D 核心必须领域无关,跨学科题库设计是 Phase 6 必修
- [x] **CI gate v0.55.0-e**：CI 集成 (`.github/workflows/test.yml` + `Makefile`)
  - 触发: push main / PR main / 手动
  - 步骤: install deps → check_defensive (5 项) → pytest (22)
  - macOS runner + Python 3.12 (Bisen 主开发机)
- [ ] `save_student_state` 加 `fail_count` 字段，统计丢了几条 snapshot
- [ ] `db.py` 持久化后做 integrity check（存完再 load，对比 length）
- [ ] Bisen 反馈过任何 2 次以上的同类 bug，必须写 CI gate 堵住第 3 次
