# CLAUDE.md - ECOS 项目指南

> **本文件是 Claude Code 在 ECOS 项目中的协作指南**。ECOS 是与 SelfLab 并列的独立项目（Educational Cognitive Operating System，教育认知操作系统）。
> **协作规则只此一份；历史与进度归档不在此**：版本进度见 [README §当前状态](./README.md)，变更明细见 [CHANGELOG](./CHANGELOG.md)，防御性自检历史见 [docs/defensive-history.md](./docs/defensive-history.md)。

## 项目性质

**ECOS 是研究规划 + 产品 Demo 项目**：产出 = 研究文档（PRD/ARCH/DESIGN/ROADMAP）+ 可分发应用代码。核心工作围绕：

- 双 Agent 架构（CTA + LCA）设计与论证、Bloom 目标空间在 K12 教育中的应用
- **ECOS 2.0 认知内核深化**：State-based Cognitive Kernel（5 引擎 6 对象）+ Cognitive Runtime（8 plan API），教育是第一垂直领域
- 教学法与认知科学的探讨

**当前阶段（2026-09-06）**: v0.98.0 家长端 + Evidence/Event 注入答题流（接线审计实例 ③ 收口）完成，下一步 = v0.98 试点执行（H1/Twin 数据收集方案已交付）。当前按 2026-08-17 方向审查（验证优先 + 应用层产品化，抽象推演冻结）推进。

**权威状态源 = [README §当前状态](./README.md)**：任何"当前阶段 / 组件状态 / pytest 规模"标注都以它为准，CLAUDE.md 不再重复维护进度副本。

**关键区分**：
- **Product Demo 代码 = 可分发应用**：需要错误处理、边界状态、用户可感知价值（不是"一次性实验"）
- **ecos/ Python 包 = 应用基础设施**：pip install ecos 可用，已含 CTA/LCA/Evidence/Event/Policy/Runtime/Plugin 全内核

## 项目背景

ECOS 探索"教育认知操作系统"——AI 能否通过双 Agent 共进化系统（CTA + LCA + Bloom Goal Space）持续理解并帮助 K12 学生成长；v0.80+ 底座升级为领域无关的状态优先计算（Kernel + Runtime）。核心研究纲领见 `research/` 目录，关键洞察见深度研究文档 v2.0。

## 与 SelfLab 的关系

ECOS 与 SelfLab 是**并列的独立项目**，共享认知科学工具箱但应用方向不同：

| 维度 | SelfLab (SGE) | ECOS |
|------|---------------|------|
| 核心问题 | AI 自我涌现 | AI 理解并帮助学生成长 |
| 核心架构 | 单一 Agent 12 步 | 双 Agent 互校（CTA + LCA）→ ECOS 2.0 Kernel + Runtime |
| 状态空间 | AI 自身 value/drive | 学生 9D + BloomProfile |
| 借鉴 | 7 个认知科学工具 | 同上（共享）|
| 不借鉴 | 自我/身份涌现 | value/drive（方向错位）|

详细背景见 `research/deep-research/Cognitive-Digital-Twin-Deep-Research.md` v2.0 第 4 部分。

## 用户与协作

**项目发起人**：Bisen——关注 AI 认知架构、教育认知操作系统、人工自我；专业领域：哲学（现象学、金观涛真实性哲学）、认知科学、AI 架构、教学法。协作偏好：深度讨论与跨工具协作（ChatGPT/Gemini/Claude 并行）、重视哲学层面硬问题、结构化可追溯文档、接受挑战既有框架的批判性思考。

**AI 协作伙伴预期角色**：研究助手 / 架构师 / 评审者 / 文档维护者。

**协作者背景假设**：Bisen 熟悉金观涛真实性哲学、ACT-R/SOAR/LIDA 等经典认知架构、Bloom 分类学、LLM 基础概念——可直接使用专业术语，无需展开基础解释。

## 协作规范

- 文档语言以中文为主，技术术语保留英文
- 研究纲领使用版本号管理（v0.1、v0.2 ...）
- 讨论记录应标注参与者和日期
- 引用外部理论时注明来源

## 核心工作流：探讨 → 洞察 → 修正（闭环）

【0】深度分析 → 存档到 `research/` 对应子目录
【1】讨论存档 → `discussions/YYYY-MM-DD-主题关键词.md`（含背景/核心观点/论证过程/结论/开放问题）
【2】判断关键洞察：是否提出新概念/推翻假设/建立新映射/明确哲学立场？是 → 加入 ECOS 关键洞察集
【3】检查项目文档是否受影响：`research/00-overview/01-applications.md`、`02-architecture.md`、`03-roadmap.md`、`research/10-engineering/`、`CHANGELOG.md` → 修正受影响者并记 CHANGELOG
【4】git add + commit + push（自动同步推送，**原子 commit**：每次只做一类变更）

## 目录约定（要点；完整结构见 README 文档结构）

- `README.md` — 项目入口（**权威状态源** + 开发环境/启动指南）
- `CLAUDE.md` — 本文件（协作规则）
- `CHANGELOG.md` — 变更日志（pytest 分文件清单也在这）
- `ecos/` — Python 内核包（17 包：cta / lca / twin / domain / dual_agent / evaluation / event / evidence / goal / metrics / motivation / persistence / plugins / runtime / session / bloom）
- `web/` — Flask API（`api/`）+ React SPA（`frontend/`：教师端 index.html + 学生端 student.html）+ legacy vanilla JS（`student/` `teacher/`，迁移期兜底）
- `tests/` — pytest · `scripts/` — 防御性自检 + 一次性脚本 · `githooks/` — pre-commit / pre-push hooks · `docs/` — 使用/设计文档
- `research/` — 核心研究文档（`README.md` 是 SSOT 入口）· `references/` 参考资料 · `experiments/` 一次性实验 · `discussions/` 讨论存档 · `prototypes/` 架构原型

> 术语使用约定：所有文档涉及核心术语时与 `references/cognitive-architectures-overview.md` 保持一致；CTA、LCA、Bloom Goal Space、互校循环、信念分布等定义见深度研究 v2.0 第 3 部分。

## Product Demo 代码约定

### 允许的代码形态

| 形态 | 用途 | 存放位置 | 生命周期 |
|------|------|---------|---------|
| **Jupyter notebook** | 单次实验运行、参数探索、结果可视化 | `experiments/notebooks/` | 实验完成后归档 |
| **ad-hoc 脚本** | 一次性验证（如跑 100 Epoch 收集价值轨迹）| `experiments/scripts/` | 实验完成后归档 |
| **数据处理脚本** | 实验结果分析（统计、可视化、报告生成）| `experiments/analysis/` | 实验完成后归档 |
| **配置文件** | 实验参数（YAML）| `experiments/configs/` | 与对应实验归档 |

### 阶段要求

- **ecos/ Python 包（可复用基础设施）**：✅ 已实现全内核——核心组件需有模块级 docstring
- **生产级代码（CI/CD、测试套件、部署配置）**：这是应用项目，不是研究项目
- **命名约定**：API 路由 `/api/<resource>/<action>`（如 `/api/answer`, `/api/judge`）；学生端 React = `web/frontend/src/student/`（legacy fallback `web/student/index.html`）；教师端 React = `web/frontend/` index.html（legacy fallback `web/teacher/index.html`）；核心组件 `ecos/cta/belief_engine.py`, `ecos/cta/l2_mirt.py`

### 与项目级文档的同步

- **实验代码必须与文档关联**：每个 notebook/脚本头部需说明"对应 ROADMAP §M4.1"、"对应 PRD §FR-4"等
- **实验结果必须文档化**：跑完实验后，结果（数据 + 分析）记录在 `discussions/` 或 `research/90-mvp/` 下的报告中
- **不演进为可复用系统**：实验代码不追求"代码质量"（覆盖率、CI、文档字符串），追求"假设验证"
- **何时停止使用实验代码**：实验完成后归档（不删除，不再修改）；不进入主分支演进路径；新可复用代码放 `ecos/`

## 深度分析存档策略

- 用户说"深度分析/深度研究" → 默认存为 `research/` 对应子目录下的 MD 文件（00-overview/10-engineering/20-pedagogy/30-shared-cognitive-tools/40-aibeing-borrowing/90-mvp/），完成后告知文件路径
- 用户说"深度探讨" → 走完整闭环（见上）
- **会话记录**：每次对话结束时在 `discussions/` 生成简要会话记录 `YYYY-MM-DD-主题.md`（日期/主题/核心结论/产出文件列表）

## 自动同步推送策略

每次完成内容或文件的增删改任务后，自动执行 git add、commit 和 push，无需用户手动触发。commit message 应简要概括变更内容，保持原子性（每次 commit 只做一类变更）。

## 讨论风格

鼓励批判性思考与深度追问。不回避哲学层面的硬问题（教育本质、认知发展、主体性与学习的关系）。欢迎挑战既有框架，而非仅在框架内做修补。

## 防御性自检规范（强制）

> **为什么存在**：2026-07-19 连发 6 commit 期间多次"重启后状态丢失"等同类 bug 在 1-2 周内复发 3 次+，根因是"修一处即提交一处"没做同类扫描。本节从此强制。
> **完整历史（起源故事 / CI gate 逐条 / mutation 审计日志 / pytest 分文件清单）**：见 [docs/defensive-history.md](./docs/defensive-history.md)。

### 入口（自动强制，本地优先）

- `pre-commit` hook：`check_defensive.sh --static-only`（8 项静态 + 前端段，秒级）
- `pre-push` hook：全量（8 项 + 前端段 + pytest）—— **任何 1 个 fail 都 abort push**
- 手动：`make check` / `make test`；新机器 `bash scripts/install-hooks.sh`（设 core.hooksPath = githooks）
- GitHub Actions：**manual only**（CI 环境无 LLM/DB 跑不全；不消耗自动配额）
- **禁止 `--no-verify` 绕过**（紧急 hotfix 除外，绕过时须在 commit message 说明）
- **push 成功标准** = pre-push hook 跑完 + pytest 全绿，**不是** `git push` 退出码 0

### 8 项防御性自检（自动化）

| # | 项 | 拦截历史 | 工具 |
|---|----|---------|-----|
| 1 | silent pass 扫描 | v0.47.5 / v0.53.3 / v0.55.0-a | `grep` 排除注释行 + 测试代码 |
| 2 | `__version__` 同步 | 多次漏 bump 致 API report hardcoded | 读 `ecos/__init__.py` 单一权威源 |
| 3 | `detect_with_hits` 传 `library_str` | v0.52.0 库 ID 错配 | multi-line grep + 排除函数定义/注释 |
| 4 | HTML class 与 CSS 对齐 | v0.47.3 / v0.50.0 class 错配 | `grep`（warning）|
| 5 | DB 恢复 6 关键字段 | 4 次漏字段 | 检查 belief.py + db.py |
| 6 | DB 恢复走 apply_snapshot | v0.77.1 收口 | `grep apply_snapshot` |
| 7 | replay 脚本无字面量 skill_id | v0.78 H3-c4 | AST 检测 |
| 8 | 直接 state.X = value mutation | v0.80 收口；每版本审计 0 新增 | AST 扫描 + FUNC_ALLOWLIST（审计日志见归档）|

### 硬规则（违反 = 历史同类 bug 复发）

1. **无 silent pass**：任何 `except ...: pass` 都改 `_log.warning(..., exc_info=True)` 或显式 `raise`（例外仅 `__init__.py` Optional import / feature flag 关闭分支，**必须加注释说明**）
2. **版本同步**：commit 含功能/修复 → `ecos/__init__.py` 必须 bump；纯文档变更不 bump
3. **commit message 表达**：禁止混用"已做"（✅/🆕/直接陈述）与"计划"（📋 后续 / TODO）——防止 Bisen 误以为已落地；"后续"章节单独标注
4. **不虚标**：commit 列组件/字段前，先 grep 确认代码**真有 update 逻辑**，不写 message 时想当然（v0.52.0 教训）
5. **LLM judge 失败不降级**：retry 3 次全失败 → 422 + needs_rejudge；**不写启发式兜底**（字符串宽松/用户自评皆 silent degradation）；**不污染任何 state**（v0.56.1）
6. **架构升级涉及历史状态**：commit 前明确警告"会丢失什么 / 不丢失什么 / 写不写迁移脚本"（v0.57.0 教训）
7. **改 /api/judge prompt 必加测试**验证新输出格式（v0.58.0；不允许"改 prompt 不加测试"）
8. **同类模式扫描**：修一个 bug 后**至少 grep 一次**同类（except:pass / DB 恢复字段 / `__version__` / CSS 引用）确认没在别处复发
9. **新依赖 / 新 fixture**：加 import → grep 全项目 → 同步 `pyproject.toml` dependencies；新第三方 test fixture → 干净环境 `pip install -e ".[dev]"` 跑通 + pytest 全绿再 push
