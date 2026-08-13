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

> **当前阶段（2026-08-13）**：**Phase 4（Product Demo 完整化）实际完成，Phase 5（产品化）已启动 v0.54.0 → v0.94.0**。
> - Phase 4: ✅ 实际完成 v0.52.3 (Bisen 自定义 Phase 1-4 全部落地, 含 5D 视觉化 / 答题历史 / Tab 导航 / Phase 4 架构现代化)。
> - Phase 5: 🚀 已启动并推进：partial credit (v0.54.0) / C/X 主导题 (v0.54.2/3) / LCA 接入 + 持久化 (v0.56.0/0.57.0) /
>   dual_agent 接入 + 持久化 (v0.60.0/0.61.0/0.62.0) / H3 验证 A+B 报告 (v0.63.0/0.68.0) / v0.69.0 confidence 指标重设计 PRD /
>   **v0.80-0.85 kernel-deepening 全部完成**:
>   - v0.80 CTA 4-layer split
>   - v0.81 StateEngine 6/6 + EventLog + Replay/Simulation
>   - v0.82 LCA 4-layer split (Planner/ExperimentDesigner/Evaluator/PolicyLearner)
>   - v0.83 Evidence Engine + Runtime API (4 子包 + 6 核心 API)
>   - v0.84 Event Engine 100% + Plugin SDK 雏形 (4 sub-version a/b/c/d)
>   - v0.85 Plugin SDK 100% + Production Activation (4 endpoint 全走 Plugin path + Flask startup)
>   **v0.86.0 Phase 6+ Kernel 扩展 #1 全部完成** (Goal Ontology 100% + Twin Consistency 100% + Thompson Sampling 95% + Integration 100%)
>   **v0.87.0 Phase 6+ Kernel 扩展 #2 全部完成** (Motivation Profile 100% + POMDP Policy 雏形 + 真 A/B 3-way)
>   **v0.88.0 Phase 7+ 抽象推演 #1 全部完成 (a/b/c/d)**:
>   - v0.88.0-a: Domain base class + 3 domain schema (Education/Science/Career)
>   - v0.88.0-b: Multi-Domain 集成 Runtime + LCA + Evaluator (DomainExtension + Runtime.plan_domain_aware + ExperimentDesigner + Evaluator.domain_reward_adjustment)
>   - v0.88.0-c: POMDP 完整 (依赖型 T(s'|s,a) + 固定 init R(s,a) + bayes_update(action, obs) + schema_version 校验)
>   - v0.88.0-d: POMDP 集成 Runtime + 真 A/B 3-way 升级 (LCAPolicyLearner.set_observation + LCAEngine pomdp integration)
>   **v0.89.0 Phase 7+ 抽象推演 #2 全部完成 (a/b/c/d)**:
>   - v0.89.0-a: PBVI 雏形 + α-vector 数据结构 (AlphaVector frozen + PBVI 单步 backup + alpha_value/best_action)
>   - v0.89.0-b: PBVI 完整算法 + belief point sampling (update_alpha_vectors 收敛 + PBVI.solve 主算法 + reachable/uniform belief points)
>   - v0.89.0-c: POMDPPolicy 集成 PBVI (use_pbvi=True 默认 + 懒加载 + dump_state 持久化 solver_state + load_state 严格恢复 + schema_version 0.89.0-c)
>   - v0.89.0-d: Runtime + PolicyABTest 集成 PBVI (LCAPolicyLearner / LCAEngine.select_intervention 显式 solve_pbvi + PolicyABTest 工厂 use_pbvi=True + solve_pbvi 幂等 + PolicyLearnerConfig.pomdp_use_pbvi 透传)
>   **v0.90.0 Phase 7+ 抽象推演 #3 全部完成 (a/b/c/d)**:
>   - v0.90.0-a: T/R posterior 数据结构 + 增量 update (TransitionPosterior Dirichlet + RewardPosterior Beta 共轭)
>   - v0.90.0-b: posterior 注入 POMDPPolicy + 持久化 (transition_count / reward_alpha / reward_beta 字段) + schema_version 升级 0.89.0-c → 0.90.0
>   - v0.90.0-c: POMDPPolicy 集成 update_t_r + PBVI 用 posterior mean (use_learned_t_r=True 默认 + lazy init posterior + obs 透传)
>   - v0.90.0-d: Runtime + PolicyABTest + 冷启动 (LCAEngine.update 透传 obs + PolicyLearnerConfig.pomdp_use_learned_t_r + min_samples=5 + 3-way A/B 维持)
>   **v0.91.0 Phase 7+ 抽象推演 #4 全部完成 (a/b/c/d/e)**:
>   - v0.91.0-a: Twin → Human Twin 数据结构 (CognitiveTwinAgent 3-tuple: BeliefState + Trajectory + HumanFeedbackTrajectory) + HumanFeedbackEntry (4 event_type frozen dataclass)
>   - v0.91.0-b: Runtime + Plugin SDK 4 subscriber (LCAEngine._cognitive_twin dict + Runtime.plan_human_feedback_aware 第 6 plan API + PluginRuntime 7 subscribers hint/idle/goal/reflection)
>   - v0.91.0-c: LCA 4 layer 接入 Human feedback (ExperimentDesigner._human_feedback_itype_override + Evaluator.human_feedback_reward_adjustment + 多 factor chain)
>   - v0.91.0-d: 冷启动 + 持久化 + canary (CognitiveTwinAgent.dump_state/load_state + LCAEngine._cognitive_twin_pending + db cognitive_twin TEXT 列)
>   - v0.91.0-e: Plugin SDK 文档化 (docs/plugin_sdk.md + examples/plugin_sample_human_feedback.py 5 use case + tests/test_plugin_sdk_docs.py 4 doctest)
>   **v0.92.0 Phase 7+ 抽象推演 #5 全部完成 (a/b/c/d)**:
>   - v0.92.0-a: HumanTwinSnapshot ActionHistory 占位兑现 (CognitiveTwinAgent 3-tuple → 4-tuple 加 action_history: ActionHistory, ActionEntry frozen dataclass 5 action_type, ActionHistory cap 500 pattern 跟 HumanFeedbackTrajectory 完全 parallel)
>   - v0.92.0-b: Runtime + LCAEngine append_action_history 接入 (Runtime.plan_action_aware 第 7 plan API + LCAEngine.select_intervention Step 7 + update 自动记录 ActionEntry + POMDPPolicy SCHEMA_VERSION 0.91.0 → 0.92.0 升级)
>   - v0.92.0-c: LCA 4 layer 接入 (ExperimentDesigner._action_history_itype_override 5 case priority + Evaluator.action_history_reward_adjustment 4 case factor 0.85/1.05/1.15 + 5 factor chain: base × motivation × domain × human_feedback × action_history)
>   - v0.92.0-d: 冷启动 + 持久化 + canary (CognitiveTwinAgent 4-tuple dump_state/load_state round-trip + LCAEngine 4-tuple persistence + 老 v0.91 snapshot compat graceful skip + warning + v0.81 replay canary: action_history 走 LCA 路径)
>   **v0.93.0 Phase 7+ 抽象推演 #6 全部完成 (a/b/c/d)**:
>   - v0.93.0-a: POMDPDiagnostic 数据结构 + POMDPPolicy diagnostic API 雏形 (TransitionPosteriorSnapshot / RewardPosteriorSnapshot / POMDPDiagnostic frozen dataclass 三件套 + coverage + most_likely_state + get_diagnostic / get_transition_heatmap / get_reward_curves)
>   - v0.93.0-b: Runtime + LCAEngine + Plugin SDK 集成 diagnostic (Runtime.diagnose_pomdp 第 8 plan/query API + LCAEngine._pomdp_diagnostic per-student dict + LCAEngine.select_intervention POMDP path auto-collect + PluginRuntime 第 8 subscriber pomdp_diagnostic_updated)
>   - v0.93.0-c: 演化追踪 (timed snapshots N=50/K=10) + 持久化 (POMDPPolicy._evolution cap K=10 FIFO + _next_snapshot_at=50 + _take_evolution_snapshot + dump_state evolution/update_count/next_snapshot_at 字段 + LCAStore pomdp_diagnostic TEXT 第 9 列 + ALTER TABLE 老 DB 兼容 + SCHEMA_VERSION 0.92.0 → 0.93.0)
>   - v0.93.0-d: H3-c4 canary + 老 v0.92 snapshot graceful skip + docs/pomdp_diagnostic.md (8 section) + examples/plugin_sample_pomdp_diagnostic.py (3 use case: teacher_progress_review / parent_engagement / student_self_reflection) + tests/test_pomdp_diagnostic_docs.py (4 doctest)
>   **v0.94.0 Phase 7+ 抽象推演 #7 全部完成 (a/b/c/d)**:
>   - v0.94.0-a: Plugin ABC + PluginMetadata frozen dataclass (`ecos/plugins/base.py` + Plugin(ABC) 4 abstract method + PluginMetadata frozen dataclass schema_version="0.94.0" 独立 schema)
>   - v0.94.0-b: PluginRegistry singleton + Register API + PluginRuntime DI 集成 (PluginRegistry 跟 DomainRegistry v0.88.0-a 完全 parallel API + plugin_registry_factory DI 注入 + 3-way subscribe_all/unsubscribe_all)
>   - v0.94.0-c: First-party plugin library + LearningEvent factory + examples 升级 (HintFatiguePlugin / ParentEngagementPlugin / TeacherProgressPlugin 3 first-party plugin + LearningEvent.from_pomdp_diagnostic_updated factory)
>   - v0.94.0-d: Persistence + canary + docs + examples (PluginRegistryStore 独立 plugin_registry DB 表 + ALTER TABLE 老 DB 兼容 + docs/plugin_library.md 8 section + examples/plugin_sample_first_party.py 3 use case + H3-c4 + v0.81 replay canary)
> ECOS 7 组件: 5D+cov (K/P/S/C/X 均真评估) / Bloom 6级 / TC 状态 / LearningDNA (标"待启用") / Trajectory / Misconceptions / overall_confidence。
> 详见 [03-roadmap.md](./research/00-overview/03-roadmap.md) (v1.5+ 已同步) + [12-kernel-mapping-current-vs-2.0.md §8.2 v0.94.0 更新](./research/00-overview/12-kernel-mapping-current-vs-2.0.md)。
>
> **历史重大弊端跟进 (Bisen 2026-07-22 测试发现 → 2026-07-30 状态)**:
> - ✅ **Partial Credit 缺失 — v0.54.0 已修复**。学生答对 70% 但缺 I/O 时, ECOS 不再按 0% 处理。
>   详见 [discussions/2026-07-22-partial-credit重大学术弊端发现.md](./discussions/2026-07-22-partial-credit重大学术弊端发现.md) + CHANGELOG v0.54.0
> - ✅ **C/X 维度 0 主导题 — v0.54.2/3 + v0.65.0 已修复**。5D 评估现在是真 5D (lbc001 C=-0.12 X=0.47; lbc002 C=-0.20 X=0.82)。
>   详见 [discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md](./discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md)
> - ⚠️ **H3 验证当前未通过 — v0.68.0 B 报告显示 V1/V2 confidence 指标显著反向**。根因是指标选错 (expected_gain 不是答对概率 / overall_confidence 是系统把握度),
>   v0.69.0 按 B4+C1+D1 方案重设计后重跑。
>   详见 [discussions/2026-07-30-H3-verification-B-report.md](./discussions/2026-07-30-H3-verification-B-report.md) +
>   [discussions/2026-07-30-v0690-confidence-redesign-PRD.md](./discussions/2026-07-30-v0690-confidence-redesign-PRD.md)
> - ✅ **ECOS 端到端流程** — 8 阶段闭环 + 5D/Bloom 数值变化的通俗化解读 (Bisen 触发 2026-07-22)
>   详见 [research/90-mvp/06-ecos-end-to-end-flow-analysis.md](./research/90-mvp/06-ecos-end-to-end-flow-analysis.md)
>
> **lbc001 27 道题测试发现 4 个 BUG** (2026-07-21):
> 详见 [discussions/2026-07-21-lbc001测试发现4个BUG分析与修复计划.md](./discussions/2026-07-21-lbc001测试发现4个BUG分析与修复计划.md)
>
> **新增关键洞察 (2026-07-31 方向审查)**: README.md / 03-roadmap.md / CLAUDE.md 当前阶段标注停在 v0.53.1 (2026-07-22) 6-8 天,
> 与工程实际进度 (v0.68.0) 严重脱节。已同步修正。
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
| 5 | 状态管理 (App 对象 / LCA + dual_agent 持久化) | ⚠️ 部分: LCA (v0.57.0) + dual_agent (v0.61.0) 已持久化, App 对象统一状态管理仍待 | v0.52.0+ |

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
> **v0.64.1 自动化** (2026-07-29 Bisen 拍板改写)：7 项防御性自检 + pytest 377 测试已统一到 `bash scripts/check_defensive.sh`。**本地强制** (`pre-commit` hook 跑静态 / `pre-push` hook 跑全量) + **GitHub Actions 改 manual only**, 不再消耗 CI 自动配额. 详见 [§v0.64.1 本地强制 + CI 手动](#v0641-本地强制--ci-手动-2026-07-29-bisen-拍板改写).

### 每次 commit 前的自检清单（已自动化，hook 强制）

> **v0.64.1 后**: `pre-commit` hook 已自动跑 6 项静态 (秒级), `pre-push` hook 跑全部 6 项 + pytest (~30s-1min). 下面这些命令是 **hook 失败时手动 debug 用**, 不需要每次手动跑.

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

### [9] 本地 push 前必跑 (2026-07-28 Bisen 反馈后新增, v0.58.3 落规则 → v0.64.1 改写)

> **起源**: 2026-07-28 Bisen 反馈 5 封 GitHub Actions 失败邮件 (14:57 → 18:31, 5 个 commit 全 fail).
> **根因**: Mavis 每次 `git push` 退出码 0 就报"成功"收工, **从不回头查 CI 状态**. 累计 5 个 commit (f383e00 / 7397381 / cd89519 / 6909442 / ed54f96) 全部 fail 但没察觉. 实际原因: `pyproject.toml` 漏 `flask` 依赖, v0.55.0 加 CI 时漏写, v0.56.1 加 `flask_client` fixture 后才暴露.
> **v0.64.1 修正 (Bisen 拍板 2026-07-29)**: 旧规范是"push 后建 cron 监控 CI 5 分钟, 绿后删", 已被废弃.
> 根本问题是: **CI 环境没有真实 LLM / DB, 跑出来比本地少, 多次出现"本地绿 / CI 红"伪错配** (v0.58.3 flask 漏 / v0.58.4 DB 依赖 / v0.62.2 LLM mock 漏). 既然 CI 跑不全, 在 CI 上等结果就是浪费.
>
> **新规范 (v0.64.1)**:
> - **本地强制**: `pre-commit` hook 自动跑 6 项静态检查 (秒级), 不通过禁止 commit
> - **本地强制**: `pre-push` hook 自动跑 6 项静态 + pytest 全量 (~30s-1min), 不通过禁止 push
> - **GitHub Actions 改为 manual only** (`workflow_dispatch`), 仅排查"本地环境被污染"等问题时手动触发, 不消耗自动配额
> - **不要** `git commit --no-verify` / `git push --no-verify` 绕过 hook (紧急 hotfix 除外, 绕过时要在 commit message 说明)
> - **不要**再建 `monitor-ci-<short_sha>` cron 监控 CI (CI 不再自动跑, 没东西可监控)
>
> **Mavis 承诺 (沿用旧规范 [9] 精神)**:
> - push 后不能看 `git push` 退出码 0 就报"成功" → 必须看 **pre-push hook 跑了什么 + pytest 全绿** 才算成功
> - 加新依赖 → grep `from <pkg> import` / `import <pkg>` 全项目 → 同步更新 `pyproject.toml` dependencies
> - 加新 test fixture (尤其 import 第三方包) → 必须先 `pip install -e ".[dev]"` 干净环境跑通, pre-push hook pytest 全绿再 push
>
> **历史**: 旧"建 cron 监控 CI"规则 (2026-07-28 11:15 拍板) 已废弃, 因为 CI 不再自动跑, 没东西可监控.

### v0.64.1 本地强制 + CI 手动 (2026-07-29 Bisen 拍板改写)

**入口**（按拦截阶段排序）:
- `pre-commit` hook (`githooks/pre-commit`): commit 前自动跑 `check_defensive.sh --static-only` (6 项静态, ~0.5s)
- `pre-push` hook (`githooks/pre-push`): push 前自动跑 `check_defensive.sh` 全量 (6 项静态 + pytest, ~10-30s)
- 本地手动: `bash scripts/check_defensive.sh` 或 `make check`
- pytest 单独: `make test` 或 `python -m pytest tests/ -v`
- GitHub Actions: `.github/workflows/test.yml` (manual only, 排查"本地环境被污染"时手动触发)

**新机器启用** (clone 后跑一次):
```bash
bash scripts/install-hooks.sh    # 设 core.hooksPath = githooks/
# 验证: git config --get core.hooksPath  → 应输出 githooks
```

**8 项防御性自检**（自动化）：

| # | 项 | 拦截历史 | 工具 |
|---|----|---------|-----|
| 1 | silent pass 扫描 | v0.47.5 / v0.53.3 / v0.55.0-a (qmatrix.py 2 处) | `grep` 排除注释行 + 测试代码 |
| 2 | `__version__` 同步 | 多次漏 bump 致 API report hardcoded | 提取 `ecos/__init__.py` 单一权威源 |
| 3 | `detect_with_hits` 传 `library_str` | v0.52.0 BUG 2.1 库 ID 错配 | multi-line grep + 排除函数定义 + 注释行 |
| 4 | HTML class 与 CSS 对齐 | v0.47.3 inline / v0.50.0 5D badge class 错配 | `grep` HTML class vs CSS 选择器 (warning) |
| 5 | DB 恢复 6 关键字段 | 4 次漏字段 (json/tc_states/trajectory/item_params) | 检查 6 字段全在 belief.py + db.py |
| 6 | DB 恢复走 apply_snapshot | v0.77.1 收口 6 处直接 state.X = value mutation | `grep "state.apply_snapshot(" web/api/belief.py` |
| 7 | replay 脚本无字面量 skill_id | v0.78 H3-c4 artifact (7 个 replay 脚本硬编码 skill_id="variables") | AST 检测 `scripts/check_no_literal_skill_id.py`, 排除 docstring + dict .get() 默认 |
| 8 | 直接 state.X = value mutation 扫描 | v0.78 BeliefEngine.update() 含 ~46 处直接 mutation (v0.80 拆 4-layer 收口); v0.81 TODO mutations 迁移完成 + hard block; v0.82 LCA 4-layer 拆分 (LCAEngine 缩到 facade, 不引入新 mutation site); v0.83 Evidence Engine + Runtime API 0 新 mutation site (Runtime API 纯函数 + kwargs 注入, 符合 kernel-mapping §5 CQRS 原则); v0.84 Event Engine 100% + Plugin SDK 雏形 0 新 mutation site (EventBus 纯 pub/sub 不动 state, PluginRuntime 委托 Runtime.update_belief 经 engine.update 间接 mutate, LearningEvent factory 是 factory pattern 不 mutate state); v0.85 Plugin SDK 100% + production activation 0 新 mutation site (PluginRuntime.start() 在 if __name__ 块, Runtime subscriber 调 Runtime.update_belief/orchestrator.process_observation/Runtime.plan 间接 mutate, 4 frontend stub endpoint 只产 event 不写 state); **v0.86.0 / v0.87.0 / v0.88.0-a/b/c/d / v0.89.0-a/b/c/d / v0.90.0-a/b/c/d 同样 0 新 mutation site** (DomainExtension set_domain_extension 加入 allowlist, POMDP reward→observation 走 LCAPolicyLearner._reward_to_observation 静态方法不 mutate, LCAEngine._last_observation 是 instance dict 不在 state 上; PBVI solver 纯函数 backup_step 不 mutate state, LCAEngine pomdp path 显式 solve_pbvi 调 POMDPPolicy.solve_pbvi 内部走 self.solver.alpha_vectors 替换 仍属于 self mutation; TransitionPosterior / RewardPosterior dataclass 维护 self.count / self.alpha / self.beta mutation 不触及 BeliefState, _update_t_r lazy init 走 self._transition_posterior / self._reward_posterior mutation 仍属于 POMDPPolicy self mutation, 防御性自检 AST 扫描 49 文件无新增 mutation site); **v0.91.0-a/b/c/d/e 加入 1 项 allowlist + 0 新 mutation site** (CognitiveTwinAgent.append_human_feedback 加入 allowlist 跟 append_trajectory_snapshot 同模式, LCAEngine._cognitive_twin dict mutation 收口到 append_human_feedback 单一入口, _cognitive_twin_pending 是 internal dict 属 LCAEngine self mutation 不触及 BeliefState; ExperimentDesigner._human_feedback_itype_override / Evaluator.human_feedback_reward_adjustment 是纯函数 0 mutation; Runtime.plan_human_feedback_aware 是 plan 委托链 0 mutation; CognitiveTwinAgent.dump_state/load_state 是 LCAEngine.dump_state/load_state 内部 dict 读写不触及 BeliefState; docs/plugin_sdk.md + examples/plugin_sample_human_feedback.py 是 docs/sample 0 mutation; 防御性自检 AST 扫描 50 文件无新增 mutation site); **v0.92.0-a/b/c/d 加入 1 项 allowlist + 0 新 mutation site** (CognitiveTwinAgent.append_action_history 加入 allowlist 跟 append_human_feedback 完全 parallel 模式, LCAEngine._cognitive_twin dict mutation 收口到 append_action_history 单一入口; ExperimentDesigner._action_history_itype_override / Evaluator.action_history_reward_adjustment 是纯函数 0 mutation; Runtime.plan_action_aware 是 plan 委托链 0 mutation; CognitiveTwinAgent 4-tuple dump_state/load_state 是 LCAEngine.dump_state/load_state 内部 dict 读写不触及 BeliefState; 防御性自检 AST 扫描 51 文件无新增 mutation site); **v0.93.0-a/b/c/d 0 新 mutation site** (POMDPDiagnostic 是 frozen dataclass 不持有 BeliefState 引用, POMDPPolicy.get_diagnostic / get_transition_heatmap / get_reward_curves 是派生 API 不 mutate state; LCAEngine._pomdp_diagnostic dict mutation 走 LCAEngine self mutation (跟 _cognitive_twin / _last_intervention 完全 parallel pattern), Runtime.diagnose_pomdp 是 plan 委托链 0 mutation, PluginRuntime._handle_pomdp_diagnostic_updated 委托 Runtime.diagnose_pomdp 0 mutation; POMDPPolicy._evolution list mutation 走 POMDPPolicy self mutation 不触及 BeliefState, _take_evolution_snapshot 派生 POMDPDiagnostic 走 POMDPPolicy.get_diagnostic() 单一入口; LCAStore.save_state 9 字段 INSERT 走 SQL 不直接 mutation state; docs/pomdp_diagnostic.md + examples/plugin_sample_pomdp_diagnostic.py 是 docs/sample 0 mutation; 防御性自检 AST 扫描 51 文件无新增 mutation site); **v0.94.0-a/b/c/d 0 新 mutation site** (Plugin ABC 是 process_event 不 mutate Kernel state (on_event 返 Optional[Any] result dict, 不写 BeliefState); PluginRegistry 是 dict 管理 + bus.subscribe/unsubscribe 不触及 BeliefState mutation; 3 first-party plugin (HintFatiguePlugin / ParentEngagementPlugin / TeacherProgressPlugin) 全程 read-only + log warning, 走 self._counts / self._diagnostics_per_student / self._coverage_per_student instance dict mutation 不触及 BeliefState; PluginRuntime DI 集成 plugin_registry_factory kwarg 注入不 mutate; PluginRegistryStore 走 SQL INSERT 不直接 mutation state; PluginMetadata / LearningEvent.from_pomdp_diagnostic_updated 是 frozen dataclass + factory pattern 不 mutate state; docs/plugin_library.md + examples/plugin_sample_first_party.py 是 docs/sample 0 mutation; 防御性自检 AST 扫描 50 文件无新增 mutation site). |

**1044 pytest 测试**（截至 v0.88.0-d, 47 个文件）→ **1096 pytest 测试**（截至 v0.89.0-d, 50 个文件）→ **1143 pytest 测试**（截至 v0.90.0-d, 53 个文件）→ **1203 pytest 测试**（截至 v0.91.0-e, 58 个文件）→ **1259 pytest 测试**（截至 v0.92.0-d, 60 个文件）→ **1308 pytest 测试**（截至 v0.93.0-d, 64 个文件）→ **1365 pytest 测试**（截至 v0.94.0-d, 67 个文件）：
- `test_state_engine.py` (54)：v0.80.0-a StateEngine commit/validate/snapshot/diff + apply_snapshot shim
- `test_inference_engine.py` (28)：v0.80.0-b InferenceEngine (含 5 个 critical 不变量 test: run() 不 mutate state)
- `test_belief_updater.py` (34)：v0.80.0-b BeliefUpdator (sole mutation site, calls StateEngine.commit)
- `test_observation_engine.py` (22)：v0.80.0-c ObservationEngine (warmup/probe state machine)
- `test_feature_extractor.py` (14)：v0.80.0-c FeatureExtractor (response_history maxlen=100)
- `test_belief_engine_facade.py` (24)：v0.80.0-c BeliefEngine facade (__getattr__ forwarding + 4-layer orchestration)
- `test_event_log.py` (32)：v0.81.0-a EventLog + LearningEvent (in_memory + sqlite, schema, multi-student isolation)
- `test_belief_updater_event_log.py` (13)：v0.81.0-b BeliefUpdator event logging + Observation to_dict/from_dict round-trip
- `test_state_engine_replay.py` (14)：v0.81.0-c StateEngine.replay/simulate API + critical replay equivalence test
- `test_v081_regression_h3c4.py` (3)：v0.81.0-c H3-c4 canary (replay path == inline path, deterministic, simulate diverges)
- `test_planner.py` (16)：v0.82.0-a LCA Planner 决策层 (PlanDecision + Planner.plan + __getattr__ 转发)
- `test_experiment_designer.py` (13)：v0.82.0-b LCA ExperimentDesigner 实验设计层 (CA/Bjork/CLT 调整算法)
- `test_evaluator.py` (13)：v0.82.0-c LCA Evaluator 评估层 (estimate_gain/risk + LCAAttribution 包装)
- `test_policy_learner.py` (15)：v0.82.0-d LCA PolicyLearner 策略学习层 (LinUCB 包装 + dump/load + 冷启动)
- `test_evidence.py` (15)：v0.83.0-a Evidence Engine (统一 schema + 6 来源 + 跨 3 表 CRUD)
- `test_belief_evidence_link.py` (14)：v0.83.0-b Belief-Evidence 关联 (add_evidence + 反查 + 集成)
- `test_evaluation.py` (16)：v0.83.0-c Evaluation Engine (Twin attribution + Policy AB + Goal completion)
- `test_runtime.py` (18)：v0.83.0-d Runtime API (6 核心纯函数 + kwargs)
- `test_learning_event_unification.py` (19)：v0.84.0-a LearningEvent unification (LearningEventType enum + 3 factory methods + FeatureExtractor 双写)
- `test_event_bus.py` (15)：v0.84.0-b Event Bus (subscribe/publish/unsubscribe + 模块级 singleton)
- `test_event_log_retention.py` (11)：v0.84.0-c EventLog retention (max_per_student cap + retention_days purge + auto_prune_on_log)
- `test_plugin_sdk.py` (11 → 14 after v0.85.0-c)：Plugin SDK 雏形 (PluginRuntime + /api/answer bus path + 防御性 fallback)
- `test_judge_event.py` (10)：v0.85.0-a /api/judge 改造 (judge_completed event)
- `test_dual_agent_plugin.py` (11)：v0.85.0-b /api/dual_agent 改造 (request_calibration event + Runtime subscriber)
- `test_lca_plugin.py` (10)：v0.85.0-c /api/lca 改造 (request_intervention event + Runtime.plan)
- `test_event_stub.py` (13)：v0.85.0-d Production activation + 4 frontend stub endpoint (hint / idle / goal_change / reflection)
- `test_goal_ontology.py` / `test_twin_consistency.py` / `test_thompson_sampling.py` (30+)：v0.86.0 Phase 6+ Kernel 扩展 #1 (Goal Ontology 100% + Twin Consistency 100% + Thompson Sampling 95%)
- `test_motivation_profile.py` / `test_motivation_runtime.py` (24+)：v0.87.0 Phase 6+ Kernel 扩展 #2 (Motivation Profile 100% schema + Runtime integration)
- `test_pomdp_policy.py` / `test_pomdp_three_way.py` (24+)：v0.87.0 POMDP Policy 雏形 (4 状态 + Bayesian belief + 真 A/B 3-way)
- `test_domain_base.py` (12)：v0.88.0-a Domain base class + 3 domain schema (Education/Science/Career)
- `test_domain_extension.py` / `test_runtime_domain_aware.py` (26)：v0.88.0-b Multi-Domain 集成 (DomainExtension + Runtime.plan_domain_aware + LCA + Evaluator)
- `test_pomdp_action_dependent.py` (16)：v0.88.0-c POMDP 依赖型 T(s'|s,a) + 固定 init R(s,a) + schema_version
- `test_pomdp_runtime_integration.py` (17)：v0.88.0-d POMDP 集成 Runtime (LCAPolicyLearner.set_observation + LCAEngine pomdp integration)
- `test_pbvi_solver.py` (31 → 实际 31 含 parametrize)：v0.89.0-a/b PBVI 算法本体 + 完整 backup + 收敛 + belief point sampling
- `test_pomdp_pbvi_integration.py` (10)：v0.89.0-c POMDPPolicy 集成 PBVI (use_pbvi + solver 懒加载 + dump/load 持久化)
- `test_runtime_pbvi.py` (11)：v0.89.0-d Runtime + PolicyABTest 集成 PBVI (LCAPolicyLearner / LCAEngine / PolicyABTest 工厂 / 3-way A/B / replay canary / H3-c4)
- `test_pomdp_learner.py` (12)：v0.90.0-a T/R posterior 数据结构 + Dirichlet / Beta conjugate + 增量 update
- `test_pomdp_posterior_integration.py` (13)：v0.90.0-b posterior 注入 POMDPPolicy + 持久化 + schema_version 升级
- `test_pomdp_learned_t_r.py` (12)：v0.90.0-c POMDPPolicy 集成 update_t_r + PBVI 用 posterior mean
- `test_pomdp_runtime_learned_t_r.py` (10)：v0.90.0-d Runtime + PolicyABTest + 冷启动 min_samples=5 (LCAEngine obs 透传 + PolicyLearnerConfig + 3-way A/B 维持 + H3-c4)
- `test_cognitive_twin.py` (12)：v0.91.0-a CognitiveTwinAgent 数据结构 + HumanFeedbackEntry (3-tuple + 4 event_type + cap 500 + 防御性)
- `test_runtime_human_feedback.py` (15)：v0.91.0-b Runtime + Plugin SDK 4 subscriber (4 endpoint chain + plan kwargs + _cognitive_twin dict + 7 subscribers + POMDP 老 schema raise)
- `test_lca_human_feedback.py` (21)：v0.91.0-c LCA 4 layer 接入 Human feedback (_human_feedback_itype_override + human_feedback_reward_adjustment + LCAEngine integration + H3-c4 canary + kwargs 透传)
- `test_cognitive_twin_persistence.py` (8)：v0.91.0-d 冷启动 + 持久化 + canary (dump_state/load_state + LCAEngine cognitive_twin + 老 snapshot compat + replay canary)
- `test_plugin_sdk_docs.py` (4)：v0.91.0-e Plugin SDK 文档化 doctest (8 section / link 存在 / use case 暴露 / smoke PASS)
- `test_cognitive_twin_action_history.py` (12)：v0.92.0-a ActionEntry + ActionHistory + CognitiveTwinAgent 4-tuple (ActionEntry frozen + 5 action_type 校验 + cap 500 + round-trip + __post_init__ 防御性 + append_action_history allowlist)
- `test_runtime_action_aware.py` (15)：v0.92.0-b Runtime + LCAEngine append_action_history 接入 (select_intervention auto-record intervention_selected + update auto-record reward_recorded + plan_action_aware 第 7 plan API + lazy init + POMDP 老 schema 0.91.0 raise)
- `test_lca_action_history.py` (21)：v0.92.0-c LCA 4 layer 接入 (5 case _action_history_itype_override + 4 case action_history_reward_adjustment 0.85/1.05/1.15 + 5 factor chain base × motivation × domain × human_feedback × action_history + H3-c4 canary + kwargs 4 路并行透传)
- `test_action_history_persistence.py` (8)：v0.92.0-d 冷启动 + 持久化 + canary (CognitiveTwinAgent 4-tuple dump/load action_history round-trip + LCAEngine 4-tuple persistence 含 auto-record + 老 v0.91 snapshot graceful skip + warning + v0.81 replay canary: action_history 走 LCA 路径)
- `test_pomdp_diagnostic.py` (18)：v0.93.0-a POMDPDiagnostic 数据结构 + POMDPPolicy diagnostic API 雏形 (TransitionPosteriorSnapshot / RewardPosteriorSnapshot / POMDPDiagnostic frozen dataclass + get_diagnostic / get_transition_heatmap / get_reward_curves + 防御性 [1] silent pass 兜底)
- `test_lca_diagnose.py` (4) + `test_runtime_diagnose.py` (6) + `test_plugin_sdk_pomdp.py` (3)：v0.93.0-b Runtime + LCAEngine + Plugin SDK 集成 (Runtime.diagnose_pomdp 第 8 API + LCAEngine._pomdp_diagnostic per-student dict + PluginRuntime 第 8 subscriber + subscription_count 7 → 8)
- `test_pomdp_evolution.py` (4) + `test_pomdp_diagnostic_persistence.py` (3) + `test_lca_store_diagnostic.py` (3)：v0.93.0-c 演化追踪 + 持久化 (POMDPPolicy._evolution cap K=10 FIFO + N=50 触发 + dump_state evolution/update_count/next_snapshot_at 字段 + LCAStore pomdp_diagnostic TEXT 第 9 列 + ALTER TABLE 老 DB 兼容 + 老 v0.92 snapshot raise per 防御性 [5])
- `test_v093_canary.py` (4) + `test_pomdp_diagnostic_docs.py` (4)：v0.93.0-d H3-c4 canary + 老 v0.92 LCAEngine snapshot graceful skip + docs/pomdp_diagnostic.md 8 section 校验 + examples/plugin_sample_pomdp_diagnostic.py 3 use case 暴露 + smoke_test PASS
- `test_plugin_sdk_base.py` (12) + `test_plugin_registry.py` (8) + `test_plugin_runtime_registry_integration.py` (5)：v0.94.0-a/b Plugin ABC + PluginRegistry singleton + PluginRuntime DI 集成 (PluginMetadata __post_init__ 防御性 / PluginRegistry subscribe_all 走 bus.subscribe / 依赖校验 / DI 注入)
- `test_first_party_plugins.py` (10) + `test_learning_event_pomdp_factory.py` (5)：v0.94.0-c 3 first-party plugin (HintFatigue / ParentEngagement / TeacherProgress) + LearningEvent.from_pomdp_diagnostic_updated factory (订阅 hint_requested / pomdp_diagnostic_updated + POMDPDiagnostic 演化追踪读 evolution)
- `test_plugin_registry_persistence.py` (4) + `test_v094_canary.py` (4) + `test_plugin_library_docs.py` (4)：v0.94.0-d 持久化 + canary + 文档化 (PluginRegistryStore save/load round-trip + 老 DB CREATE TABLE IF NOT EXISTS 幂等 + H3-c4 Plugin 不污染 BeliefState + v0.81 replay canary Plugin 不参与 replay + docs/plugin_library.md 8 section 校验)
- `test_defensive.py` (8)：8 项防御性自检的 pytest 版本
- `test_apply_snapshot.py` (19)：v0.77.1 DB 恢复路径单一入口 (6 字段恢复 + 不接管边界 + round-trip)
- `test_partial_credit.py` (5)：partial credit + MIRT 回归保护
- `test_dual_layer.py` (2)：5D 双层架构
- `test_cross_subject.py` (10)：跨学科迁移
- `test_lca_persistence.py` / `test_lca_wired.py` / `test_dual_agent*.py` / `test_judge_*.py` / `test_rejudge_partial_credit.py` / `test_ece.py` / `test_v064_mastery_prob_after.py` 等: 后续 Phase 5+ 加的功能测试
- **本地 pre-push hook 强制全跑**, 任何 1 个 fail 都会 abort push

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
  - **v0.55.0 自动化**：6 项自检 + pytest 376 测试全跑,任何"虚标"功能若代码
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
- [x] **CI gate v0.55.0-e → v0.64.1 改写**：CI 集成改为 manual only (`.github/workflows/test.yml` + `Makefile` + 本地 `pre-commit`/`pre-push` hooks)
  - **v0.55.0-e 原始** (2026-07-23): 触发 = push main / PR main / 手动, 步骤 = install deps → check_defensive (5 项) → pytest (22), macOS runner + Python 3.12
  - **v0.64.1 改写** (2026-07-29 Bisen 拍板): CI 改 `workflow_dispatch` only, 因 CI 环境无 LLM/DB 跑不全 + 多次"本地绿 CI 红"伪错配. 拦截职责下放到本地 hook (commit 阶段 5 项静态, push 阶段 5 项 + pytest 245). CI 改 manual 是排查"本地环境被污染"时手动跑, 不消耗自动配额.
  - **新规范**: 任何 push 前必跑 `pre-push` hook (本地强制), 不再建 `monitor-ci-<short_sha>` cron 监控 CI (CI 不再自动跑). 详见 § [9] 本地 push 前必跑.
- [x] **CI gate v0.56.1**：不写启发式 fallback 替代 AI 评判 (silent degradation 变种) (Bisen 2026-07-24 原则)
  - 触发: lbc001 答 PB-Q26 完全正确, 但 LLM judge 返回非 JSON → /api/judge 旧版 fallback 走字符串严格相等, 把 nonlocal 答案 vs list 包装答案 判 false → score=0
  - 实施:
    - `web/api/app.py` /api/judge: retry 3 次 (100ms / 500ms / 2s 短-中-长), 全部失败 → 422 + needs_rejudge=True, **不写启发式兜底** (无 ast 函数名匹配, 无字符串宽松化, 无用户自评)
    - **核心原则**: LLM judge 失败 = 系统故障, 显式 fail, **不污染任何 state** (response_history / 5D / Bloom / TC / misconception 一概不写)
    - 一次性脚本 `scripts/rejudge_misjudged.py`: 扫 DB 历史误判条目, 重跑 LLM judge
    - 测试 `tests/test_judge_retry.py`: 11 测试覆盖 (retry 行为 / 422 / 不污染 state / 不写启发式 / 有 warning log)
  - 防 1 次同类: 任何 LLM 评判失败都不能降级 (启发式/字符串匹配/用户自评都是 silent degradation 变种)
- [x] **CI gate v0.57.0**：架构升级前必须明确警告历史状态丢失 (Bisen 2026-07-27 反馈)
  - 触发: v0.57.0 LCA 持久化实施时, 我 (Mavis) **没**在 commit 26a4498 之前警告 Bisen "v0.57.0 启动会清空 lbc001 + lbc002 历史 LinUCB 状态 (80+ 道题)".
  - Bisen 反馈原话: "lbc001 + lbc002 答 32+ 道题累积的 LinUCB 数据丢了是你疏忽造成的不可挽回的错误，还是本来就是这样设计的?"
  - 核心教训:
    - **架构升级涉及历史状态**时, 必须 commit 前明确警告 "会丢失什么 / 不丢失什么 / 写不写迁移脚本"
    - 不允许 "实施后 CHANGELOG 写'接受错了就错了'" 自我合理化
    - **CHANGELOG 写"错了就错了"是 Bisen 对单题判罚的容忍, 不能扩展为"架构升级清空历史"**
  - 防 1 次同类: 任何架构升级 (v0.5x → v0.5y) commit 前, 主动列出 "历史状态丢失清单 + 迁移方案"
- [x] **CI gate v0.58.0**：改 /api/judge prompt 必加测试覆盖输出格式变化 (Bisen 2026-07-27 拍板)
  - 触发: v0.54.0 partial credit 改造不彻底 — Q 矩阵 partial_credit_rubric 字段挂着但 LLM judge 不消费. Bisen 继续答题会被错判 (5D 状态不可逆污染). Bisen 拍板 v0.58.0-mini 半天修 root cause.
  - 实施:
    - `web/api/app.py` 新增 `_build_judge_prompt(problem_text, correct_answer, student_answer, partial_credit_rubric=None)`: 有 rubric 时注入 4 档分 + 要求 LLM 输出 score; 无 rubric 时走老 prompt (向后兼容)
    - `web/api/app.py` 新增 `_parse_judge_result(result)` 解析 (score 优先 correct, 老数据 correct 派生 score)
    - `_call_llm_judge_with_retry` 验证字段: result 必须有 correct 或 score 之一 (防御性自检 [8])
    - `/api/judge` 端点响应新增 `score` 字段 (前端可见)
  - 测试 `tests/test_judge_rubric.py` 16 测试覆盖 (rubric 注入 / score 优先 / 向后兼容 / retry 防御)
  - 防 1 次同类: 改任何 LLM judge prompt (新增/删除/重命名字段), **必须** 同步加测试验证新输出格式. 不允许 "改 prompt 不加测试" — 这是 silent 行为改变.
- [ ] `save_student_state` 加 `fail_count` 字段，统计丢了几条 snapshot
- [ ] `db.py` 持久化后做 integrity check（存完再 load，对比 length）
- [ ] Bisen 反馈过任何 2 次以上的同类 bug，必须写 CI gate 堵住第 3 次
