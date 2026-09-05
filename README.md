# ECOS — Educational Cognitive Operating System

> **教育认知操作系统**：面向 K12 学生的下一代 AI 辅助学习系统
> 基于"**学生认知数字孪生 + AI 学习教练**"双 Agent 共进化架构
> v0.95+ 演进为 **ECOS 2.0 双内核架构**：**State-based Cognitive Kernel（状态优先的通用认知内核）** + **Cognitive Runtime（领域无关的认知运行时）**——教育（K12）是第一个垂直落地领域

[![Status](https://img.shields.io/badge/status-v0.96.0--prod-brightgreen)]()
[![Version](https://img.shields.io/badge/version-0.96.0-blue)]()
[![Tests](https://img.shields.io/badge/pytest-1393-brightgreen)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

---

## 什么是 ECOS？

**ECOS（Educational Cognitive Operating System）** 是一个面向小学、初中和高中学生的教育系统。核心由两个长期共进化的 AI Agent 协作（这是**教育映射层的通俗叙事**）：

- **CTA（Cognitive Twin Agent，认知孪生 Agent）** —— 理解学生
  - 像"认知科学家 + 心理测量学家"——保守、基于证据、维护置信度、避免幻觉
  - 维护学生认知状态的**信念分布**（不是事实判断）
  - 回答："这个学生现在是谁？卡在哪？"

- **LCA（Learning Coach Agent，学习教练 Agent）** —— 改变学生
  - 像"教练 + 强化学习策略器"——主动、实验、探索、优化
  - 基于 CTA 的状态选择最优干预策略
  - 回答："下一步怎么办？如何成长最快？"

- **Bloom Goal Space（布鲁姆目标空间）** —— 目标坐标系
  - 6 层认知层级：Remember → Understand → Apply → Analyze → Evaluate → Create
  - 让 B 从"掌握二次函数"变成"掌握二次函数：Bloom Level 4"——可计算
  - 解决"会做但不会想"的中国教育痛点

两者通过**互校循环**（CTA 提出假设 → LCA 设计实验 → 观察结果 → CTA 更新信念 → LCA 重新规划）共同进化，对抗 LLM 幻觉，形成"**自适应科学实验系统**"。

### ECOS 2.0 架构演进（v0.80+）

> 底层实现已从"双 Agent 叙事"升级为 **State-first Computing（状态优先计算）**——**一切围绕状态演化**。
> 双 Agent（CTA/LCA）是教育领域的**语义映射**；真正的底座是一个**领域无关的通用认知内核**：

- **State-based Cognitive Kernel（通用认知内核）** —— 领域无关的认知基础设施
  - **5 引擎**：State Engine（状态机） / Event Engine（事件总线） / Policy Engine（策略学习） / Evidence Engine（证据引擎） / Evaluation Engine（评估引擎）
  - **6 对象**：Twin / Belief / Goal / Event / Policy / Evidence
  - **策略谱系**：LinUCB → Thompson Sampling → POMDP + PBVI（点基值迭代）→ T/R 在线后验（Beta-Multinomial conjugate）
  - 彻底解决"会做但不会想"的教育痛点：目标、证据、策略全部**可计算、可追溯、可验证**

- **Cognitive Runtime（认知运行时）** —— 领域无关的运行时抽象
  - 8 个 plan API：estimate / update_belief / replay / evaluate / simulate / plan + domain / human_feedback / action_aware 变体
  - **教育是第一个 Domain**（v0.88 Multi-Domain：Education / Science / Career 3 套 schema）
  - Plugin SDK（v0.85/0.94）：Plugin 不碰状态、只产 Event——AST 扫描强制 0 mutation site

- **应用层（React 三端 SPA）** —— 验证链路呈现面
  - v0.95 教师端（证据链视图"系统为什么这么判断"）→ v0.96 学生端（信息架构三问 + 通俗化全接）→ v0.97 家长端（规划中）

**一句话**：ECOS 不是"一个会出题判分的 K12 应用"，而是一个**可承载教育（乃至更广领域）认知状态演化与策略学习的操作系统**——K12 学生是第一个使用者，双 Agent 互校是第一个落地范式。

## 核心架构

### 教育映射层（双 Agent 互校）

```
┌──────────────────────────────────────────────────────────┐
│              Bloom Goal Space（目标坐标系）                 │
│  Remember → Understand → Apply → Analyze → Evaluate → Create │
└──────────────────────────────────────────────────────────┘
                            ↕
┌──────────────────────────────────────────────────────────┐
│       Learning Coach Agent (LCA) — Policy Optimizer       │
│       思维模式：教练 + 强化学习策略器                        │
│       输出：intervention_type + parameters + expected_gain │
└──────────────────────────────────────────────────────────┘
                            ↕
┌──────────────────────────────────────────────────────────┐
│     Cognitive Twin Agent (CTA) — State Estimator          │
│     思维模式：认知科学家 + 心理测量学家                     │
│     状态：K/P/S/C/X + BloomProfile + LearningDNA + Trajectory │
└──────────────────────────────────────────────────────────┘
                            ↕
                         Student
```

### ECOS 2.0 底座（State-first Computing）

```
┌──────────────────────────────────────────────────────────────────┐
│                     Cognitive Runtime（认知运行时）                 │
│         8 plan API：estimate / update / replay / evaluate /       │
│         simulate / plan (+domain / human_feedback / action_aware) │
└──────────────────────────────────────────────────────────────────┘
                            ↕
┌──────────────────────────────────────────────────────────────────┐
│              State-based Cognitive Kernel（通用认知内核）           │
│   State Engine ─ Event Engine ─ Policy Engine ─ Evidence Engine ─ Evaluation Engine │
│   对象：Twin / Belief / Goal / Event / Policy / Evidence           │
│   策略：LinUCB → Thompson → POMDP + PBVI → T/R 在线后验            │
└──────────────────────────────────────────────────────────────────┘
                            ↕
┌──────────────────────────────────────────────────────────────────┐
│              Domain Layer（领域层）Education/Science/Career        │
└──────────────────────────────────────────────────────────────────┘
                            ↕
┌──────────────────────────────────────────────────────────────────┐
│              应用层（React SPA）：教师端 / 学生端 / 家长端           │
└──────────────────────────────────────────────────────────────────┘
```

详细架构见 [`research/deep-research/Cognitive-Digital-Twin-Deep-Research.md`](research/deep-research/Cognitive-Digital-Twin-Deep-Research.md) v2.0 + [`research/00-overview/11-ecos-2.0-architecture-proposal.md`](research/00-overview/11-ecos-2.0-architecture-proposal.md)（ECOS 2.0 蓝图）。

## 项目目标

构建一个**能够持续 6~12 年陪伴学生成长的教育认知操作系统**：

- **目标用户**：K12 学生（小学/初中/高中）——当前第一垂直领域
- **核心能力**：持续理解 + 主动引导 + 长期共进化
- **护城河**：3 年以上的个性化认知画像（数据资产壁垒）
- **差异化**：相比 Khanmigo / Duolingo Max / Squirrel AI，是从"知识图谱 + AI 问答"升级为"理解学生 + 改变学生"的下一代架构

## 与 SelfLab（SGE）的关系

ECOS 是与 [SelfLab](https://github.com/cnbison/SelfLab) **并列的独立项目**：

| 维度 | SelfLab (SGE) | ECOS |
|------|---------------|------|
| **核心问题** | AI 能否形成持续自我 | AI 能否理解并帮助学生成长 |
| **核心架构** | 单一 Agent 12 步编排 | 双 Agent 互校（CTA + LCA）→ ECOS 2.0 Kernel + Runtime |
| **状态空间** | AI 自身 value/drive | 学生 9D + BloomProfile |
| **应用方向** | Personal AI、协作 agent、历史人物 | K12 教育（第一领域）→ 通用认知运行时 |
| **共享基础** | 7 个认知科学工具（贝叶斯、记忆分层、预测加工、双系统、BDI、元认知、经典架构）|

**为什么作为独立项目**：

1. **避免散乱**：SelfLab 已聚焦 SGE，ECOS 有独立的研究方向和目标用户
2. **独立发展**：SGE 关注"AI 自我涌现"，ECOS 关注"教育认知操作系统"——互不干扰
3. **降低认知负担**：研究者可在两个项目间清晰切换
4. **合作灵活**：ECOS 未来与教育机构合作时，独立项目身份更合适

详细决策过程见 [`discussions/2026-06-24-ecos-project-establishment.md`](discussions/2026-06-24-ecos-project-establishment.md)。

## 文档结构

```
ecos/
├── cta/               # Cognitive Twin Agent（4 层：Observation / FeatureExtractor / Inference / BeliefUpdate）
├── lca/               # Learning Coach Agent（4 层：Planner / ExperimentDesigner / Evaluator / PolicyLearner）
├── twin/              # Cognitive Twin + Human Twin（CognitiveTwinAgent：belief + trajectory + human_feedback + action_history）
├── dual_agent/        # 双 Agent 互校（CTA + LCA）
├── bloom/             # Bloom Goal Library
├── goal/              # Goal Ontology（Capability → Objective → Metric → Evidence）
├── domain/            # Multi-Domain（Domain base + Education/Science/Career 3 schema）
├── motivation/        # Motivation Profile（frustration / engagement / confidence / recent_trajectory）
├── metrics/           # 评估指标
├── event/             # Event Engine（EventBus + LearningEvent + EventLog + retention）
├── evidence/          # Evidence Engine（6 来源 + 跨表 CRUD）
├── evaluation/        # Evaluation Engine（Twin attribution + Policy AB + Goal completion）
├── plugins/           # Plugin SDK（Plugin ABC + PluginRegistry + 3 first-party plugin：HintFatigue / ParentEngagement / TeacherProgress）
├── runtime/           # Cognitive Runtime（8 plan API + PolicyABTest）
├── persistence/       # 状态持久化（DB）
├── session/           # 长期会话管理
├── llm_client.py      # LLM 客户端（MiniMax / Moonshot）
└── orchestrator.py    # 编排入口
web/
├── api/               # Flask API（app.py 路由 + belief.py 状态 + teacher.py 教师 5 端点 + interpretation.py 通俗化 + event_stub.py 行为事件）
├── frontend/          # React 18 + Vite 6 + TS SPA（教师端 index.html + 学生端 student.html，Vite 多页 build）
├── student/           # 旧版 vanilla JS 学生端（迁移期兜底，dist 缺失时 fallback）
└── teacher/           # 旧版 vanilla JS 教师端（迁移期兜底）
tests/                 # pytest 1393（69 文件）
scripts/               # 防御性自检（check_defensive.sh）+ 一次性脚本
githooks/              # pre-commit / pre-push hooks（本地强制）
docs/                  # 使用/设计文档（web-ui-quickstart / plugin_sdk / plugin_library / pomdp_diagnostic / business-logic-flow）
research/              # 核心研究文档
  ├── README.md        # SSOT 入口
  ├── deep-research/   # 深度研究（v2.0）
  ├── gpt-dialogues/   # 5 轮 GPT 对话原文
  ├── 00-overview/     # 战略层（应用/架构/路线图/风险/ECOS 2.0 蓝图/现状对照）
  ├── 10-engineering/  # 工程层
  ├── 20-pedagogy/     # 教学法层
  ├── 30-shared-cognitive-tools/  # 共享认知科学工具箱
  ├── 40-aibeing-borrowing/       # AiBeing 借鉴
  └── 90-mvp/          # MVP 实施
references/            # 参考资料
experiments/           # 一次性实验代码
discussions/           # 讨论存档（含 2026-08-17 方向审查）
prototypes/            # 架构原型
Makefile               # 快捷命令（test / check / frontend-dev / frontend-build / frontend）
```

## 当前状态（2026-09-05）— **▶️ 已恢复开发：基于外部认知架构的学校教育方向**（搁置 14 天后重启）

> **2026-09-05 恢复标记**: ecos 恢复开发——负责人判断**基于外部认知架构的学校教育**值得进一步推进。搁置期 2026-08-22 → 09-05（无代码变更, 本段 v0.96 状态快照仍准确）。恢复期 backlog 见 §下一步（首项 = built≠wired 接线审计, 3 项已知实例）。恢复决策与适用性分析见 [discussions/2026-09-05-CogMirror迁移适用性分析-与built-unwired接线审计.md](discussions/2026-09-05-CogMirror迁移适用性分析-与built-unwired接线审计.md)。
>
> **历史**: 2026-08-22 曾搁置并选择性迁移重启为独立项目 **CogMirror**（抛开 K12, 面向**成年自学者**的 Python 学习认知教练, 无 LLM 依赖）。ecos 恢复后两项目**并行**——CogMirror 兼任 ECOS 确定性算法的廉价试验场（A1/A2/A4 类无 LLM 统计层先在单人环境验证, 再决定进 ECOS kernel）。详见 [discussions/2026-08-22-CogMirror迁移-ecos搁置.md](discussions/2026-08-22-CogMirror迁移-ecos搁置.md)。

> **Bisen 路线（2026-08-17 方向审查拍板）**: Kernel 深化收口（v0.83-v0.94 共 12 版本, pytest 1365, 缺失清单 0）后, 重心切换:
> **从"Kernel 深化/抽象推演"→"验证优先 + 应用层产品化落地"**。抽象推演冻结（Plugin SDK 独立打包等只在真实需求牵引时启动）。
> 方向审查全文见 [discussions/2026-08-17-v095方向审查-验证滞后于抽象与应用层产品化规划.md](discussions/2026-08-17-v095方向审查-验证滞后于抽象与应用层产品化规划.md)。

**ECOS 7 组件当前状态** (v0.96.0):
| 组件 | 状态 | 详情 |
|------|------|------|
| 5D + θ_cov | ✅ 真评估 | K/P/S/C/X 五维均非零 (lbc001 C=-0.12 X=0.47; lbc002 C=-0.20 X=0.82) |
| Bloom 6 级 | ✅ 真评估 | L1-L6 累积, dominant_layer |
| TC 状态 | ✅ 真评估 | 5 topic × 3 阶段, post_liminal 不可逆 |
| Trajectory | ✅ 真评估 | 时间序列, 折叠面板, cap 500 |
| Misconceptions | ✅ 真评估 | M1-M8 Python 库, v0.52.0 修过库 ID 错配 |
| overall_confidence | ✅ 真评估 | `mean(5D conf)`, v0.48.1 改的 |
| LearningDNA | ⚠️ **标"待启用"** | v0.1.0 占位, 等 ≥50 题 + 交互行为数据 (v0.97 推进启用条件) |

**ECOS 2.0 Kernel 深化进度 (v0.83.0 → v0.94.0, 已收口)**:
- ✅ **Evidence Engine + Runtime API 100%** (v0.83.0): 4 子包 + 6 核心 API
- ✅ **Event Engine 100%** (v0.84.0): LearningEvent unification + EventBus + retention
- ✅ **Plugin SDK 100%** (v0.84.0 → v0.85.0): Plugin Runtime + 4 endpoint 全走 Plugin path + Flask startup
- ✅ **Goal Ontology 100%** (v0.86.0): Capability → Objective → Metric → Evidence
- ✅ **Twin Consistency 100%** (v0.86.0): 真 A/B 3-way LinUCB / Thompson / POMDP
- ✅ **Thompson Sampling 95%** (v0.86.0): 第二个 Bandit Policy
- ✅ **Motivation Profile 100%** (v0.87.0): frustration / engagement / confidence / recent_trajectory
- ✅ **POMDP Policy 100%** (v0.87.0-d + v0.88.0-c/d): 4 状态 + Bayesian belief + 依赖型 T(s'|s,a) + R(s,a) + Runtime 集成
- ✅ **PBVI (Point-Based Value Iteration) 100%** (v0.89.0-a/b/c/d): α-vector 完整算法 + 收敛检测 + reachable_belief_points sampling
- ✅ **POMDP T/R 在线学习 100%** (v0.90.0-a/b/c/d): Beta-Multinomial conjugate posterior + posterior mean 接入 PBVI + 冷启动保护
- ✅ **Multi-Domain 抽象 100%** (v0.88.0-a/b): Domain base class + 3 Domain schemas (Education/Science/Career) + Runtime 集成
- ✅ **Human Twin 100%** (v0.91.0-a/b/c/d/e + v0.92.0-a/b/c/d): CognitiveTwinAgent 4-tuple (belief + trajectory + human_feedback + action_history) + LCA 5 factor chain + Plugin SDK 7→8 subscriber
- ✅ **POMDP Diagnostic 100%** (v0.93.0-a/b/c/d): POMDPDiagnostic 三件套 + 演化追踪 N=50/K=10 + LCAStore 第 9 列
- ✅ **第一方 Plugin 库 100%** (v0.94.0-a/b/c/d): Plugin(ABC) + PluginRegistry singleton + 3 first-party plugin + PluginRegistryStore 持久化
- 详见 [research/00-overview/12-kernel-mapping-current-vs-2.0.md](research/00-overview/12-kernel-mapping-current-vs-2.0.md) §1.3 + §3 + §6 + §8.2

**应用层产品化进度 (v0.95 → v0.96, React 双端)**:
- ✅ **v0.95 教师端 React 真实化** (2026-08-17): React 底座 + 教师 API 5 端点 (roster / detail / 5D evidence 聚合可下钻 / POMDP diagnostic / interventions) + TeacherProgressPlugin UI 化 + 学生端接通 4 行为事件端点 (hint/idle/goal_change/reflection)
- ✅ **v0.96 学生端 React 重写** (2026-08-17): 信息架构三问 (学习首页三卡 / 答题页收敛 / 移动端响应式) + interpretation 通俗化全接 + MotivationProfile 首次前端呈现 + CodeMirror 代码编辑器 + 4 行为事件端点保留 + `__APP_VERSION__` 编译期注入 + 6 页面 2 组件 (Login/Home/Answer/Where/Growth/Settings + CodeEditor/MotivationPanel)
- 技术栈: React 18 + Vite 6 + TS 5.6 + TanStack Query + ECharts, Vite 多页 build → `web/frontend/dist` → Flask 托管 (dist 优先 + legacy fallback)

**Bisen 测试发现与跟进 (2026-07-22 → 2026-08-11)**:
- ✅ **Partial Credit 已实施**: v0.54.0 接入 `partial_score` 端到端, MIRT 支持部分对。
  详见 [CHANGELOG.md](CHANGELOG.md) v0.54.0 + [discussions/2026-07-22-partial-credit重大学术弊端发现.md](discussions/2026-07-22-partial-credit重大学术弊端发现.md)
- ✅ **C/X 0 主导题已修复**: v0.54.2/3 各加 5 主导题, v0.65.0 解除"待启用"灰底。
  详见 [discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md](discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md)
- ✅ **H3 验证通过（小样本）**: v0.69.0 重新设计 dual_agent confidence 指标, v0.86.0 真 A/B 3-way 通过; 但样本仍小 (3 测试用户、1 学科), 规模验证是 v0.97+ 主线。
  详见 [discussions/2026-07-30-H3-verification-B-report.md](discussions/2026-07-30-H3-verification-B-report.md)

**三个科学问题跟踪表**（验证欠债显式化, 2026-08-17 方向审查决策 3; 度量什么就会推进什么）:

| # | 科学问题 | 当前证据 | 目标 | 状态 |
|---|---------|---------|------|------|
| ① | **Twin 是否准确？**（认知孪生估计 vs 学生真实状态） | 3 测试用户 (lbc001/002/003), 1 学科 (Python), 5D 均非零 + H3-c4 fingerprint | 小规模试点 5-10 学生 (lbc004+) + H1 数据收集方案 | 🔴 未规模验证 |
| ② | **Policy 是否有效？**（LCA 干预 vs 随机/对照） | H3 真 A/B 3-way 通过 (v0.86), 但小样本 | 试点内 Policy AB 对照, 复现 H3 | 🟡 通过未复现 |
| ③ | **是否具有长期增益？**（6-12 个月纵向成长） | LearningDNA 仍"待启用", 无纵向数据 | LearningDNA ≥50 题启用 + 3 年数据护城河积累 | 🔴 未启动 |

**累计产出** (v0.1.0 → v0.96.0, 2026-06-24 ~ 2026-08-18):
- 303 commits; v0.80 → v0.94 共 15 个 Kernel 深化版本 (41 sub-commit) + v0.95/v0.96 应用层产品化
- 端到端流程: Q 矩阵设计 → 出题 → 答题 → AI 评判 → 状态更新 → 持久化 → LCA 干预 → dual_agent 互校 → 个人画像
- **pytest: 958 → 1393** (+435; 含 v0.95.1 +26 / v0.96.0 +2)
  详见 [research/90-mvp/06-ecos-end-to-end-flow-analysis.md](research/90-mvp/06-ecos-end-to-end-flow-analysis.md)

## 开发环境设置

ECOS Python 包需要 Python 3.11+。**强烈建议使用虚拟环境**：

```bash
# 1. 创建虚拟环境（使用 conda 提供的 python3 或系统 python3）
python3 -m venv .venv

# 2. 激活虚拟环境
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows

# 3. 安装项目（editable 模式，依赖自动解析）
pip install -e ".[dev]"            # 含 dev extras（pytest/black/ruff/mypy）

# 4. 配置 LLM API（可选，仅在调用 LLM 时需要）
cp .env.example .env               # .env 已在 .gitignore 中
# 编辑 .env 填入 MINIMAX_API_KEY=sk-...

# 5. 验证安装
python experiments/scripts/m2_w1_cta_basics_validation.py   # CTA 数学骨架
python experiments/scripts/m2_w1_llm_client_smoke.py         # LLM 客户端
```

### 启动 Web UI 与答题

> Phase 4 起 Product Demo 形态：启动 Flask 后直接在浏览器答题，无需手动跑验证脚本。
> v0.96 起前端为 React SPA（学生端 + 教师端双页，Vite build → `web/frontend/dist/`，Flask 托管）。
> **详细使用说明见 [docs/web-ui-quickstart.md](./docs/web-ui-quickstart.md)**。以下为快速入口。

```bash
# 1) 先构建前端产物（dist/ 已 gitignore，首次必须构建一次）
cd web/frontend && npm install && npm run build && cd ..

# 2) 启动 Flask（端口 5173，debug 模式，改代码自动重载）
ECOS_DUAL_AGENT_ENABLED=1 python -m web.api.app
```

| 入口 | 地址 |
|---|---|
| 学生端（React SPA，v0.96） | `http://localhost:5173/`（dist 优先，无 dist 时 fallback 旧版 `web/student/`）|
| 教师端（React SPA，v0.95） | `http://localhost:5173/teacher/`（dist 优先，无 dist 时 fallback 旧版 `web/teacher/`）|

**前端开发模式（热更新）**：后端照常跑在 5173，另开终端 `cd web/frontend && npm run dev`
→ Vite 5174（proxy `/api` → Flask 5173），学生端 `http://localhost:5174/student.html`、教师端 `http://localhost:5174/`。

> **`ECOS_DUAL_AGENT_ENABLED`** 默认关闭（`"0"`）。设为 `1` 才走 dual_agent（CTA+LCA 协同）路径；
> 不设则只走老路径，dual_agent 不启用、v0.69.0 confidence 指标也不跑。
> 启动日志看到 `DualAgentOrchestrator 初始化完成 (DUAL_AGENT_ENABLED=True, ...)` 即确认已启用。
> 想在本 session 持续生效可先 `export ECOS_DUAL_AGENT_ENABLED=1` 再启动。

### 依赖清单（自动从 pyproject.toml 解析）

| 包 | 用途 |
|---|---|
| `numpy>=1.24` | 5D 状态向量、BKT/MIRT 计算 |
| `scipy>=1.11` | MIRT MAP 估计的 L-BFGS-B + Hessian 逆 |
| `openai>=1.0` | LLM 客户端（OpenAI-Compatible Protocol：MiniMax-M3 / Moonshot Kimi）|
| `pytest` / `black` / `ruff` / `mypy`（dev extras）| 测试 + 格式化 + 静态检查 |

### LLM Provider 配置

`ECOSLLMClient.from_env(provider="...")` 支持两个 provider：

| Provider | 用途 | Base URL | 模型 | 环境变量 |
|---|---|---|---|---|
| `minimax`（默认）| 项目主用 | `https://api.minimax.io/v1` | `MiniMax-M3` | `MINIMAX_API_KEY` |
| `moonshot` | 中文教育场景备选 | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` | `MOONSHOT_API_KEY` 或 `KIMI_API_KEY` |

> `.env` 文件会在 `from_env()` 调用时自动加载，无需手动 `source`。

## 下一步（恢复期 backlog, 2026-09-05 解冻并更新）

> **2026-09-05 解冻**: ecos 恢复开发, 本表解冻并并入恢复期 backlog（接线审计 → 黄金回归 → 学生自评 → A2 reconcile, Bisen 2026-09-05 认可排序）。搁置前规划 v0.97 家长端保留, 与接线审计天然汇合（家长透明化 = Evidence/Event Engine 注入答题流的预设触发条件, 见 [kernel-mapping §1.4](research/00-overview/12-kernel-mapping-current-vs-2.0.md)）。

**搁置前状态**: v0.96.0 应用层产品化 (React 双端) 全部完成, 方向审查收口 (Kernel 收口 + 抽象推演冻结 + 验证欠债显式化)。
恢复期新增依据: [discussions/2026-09-05-CogMirror迁移适用性分析-与built-unwired接线审计.md](discussions/2026-09-05-CogMirror迁移适用性分析-与built-unwired接线审计.md)（built≠wired 三项清单 + CogMirror A1-A4/B1-B2 适用性映射）。

| 优先级 | 任务 | 触发条件 | 详见 |
|--------|------|---------|------|
| **P0** | ~~全量 built≠wired 接线审计~~ **✅ 已完成 (2026-09-05)**: 全仓 715 个函数/方法扫描, 结果 **Tier A 死代码候选 47 + Tier B 产品路径未接线 72 + 孤儿实例属性 2**, 已知三项实例均扩大（报告 §七）。后续接线动作的前置缺口: BKT/l1 不持久化 + 原地乘法双重衰减陷阱（解法 = 无状态视图 + 历史重放推导峰值）; 复跑工具 `python scripts/wiring_audit.py` | ✅ 完成; 接线动作待黄金回归基建后 | [审计报告](docs/wiring-audit-2026-09-05.md) |
| **P0** | ~~接线审计 A 类首两例~~ **✅ 已完成 (v0.97.1, 2026-09-05)**: `replay_mastery_view` 无状态重放视图（BKT 不持久化, 峰值重放推导 + 衰减读时计算, Option A）+ planner 接线 `bjork_spacing`/`ca_scaffolding`（孤儿转真实消费, spacing 阈值承接 CogMirror P3, scaffolding ±0.2 有界增量失败优先）+ web 两处 CTAInput 注入 view（失败降级 legacy 规则）。**黄金回归基线零 diff**（新行为全走可选注入）; `apply_decay` 保持 dead code + 禁止激活标注 | ✅ 完成; 阈值 0.7/0.55/0.15/±0.2 为先验值, v0.98 试点数据回来后校准 | [CHANGELOG §0.97.1](CHANGELOG.md) |
| **P0** | **v0.98 家长端 + 验证主线**（原 v0.97, 因 v0.97.0 被黄金回归基建占用顺延）: a. ParentEngagementPlugin 落地家长端 (engagement 演化 + 家校协同建议); b. Evidence/Event Engine 注入答题流（= 接线审计实例 ③, 触发条件随家长端出现）; c. 小规模真实试点 5-10 学生 (lbc004+), 定义 H1/Twin 准确性数据收集方案; d. LearningDNA 启用条件推进 (≥50 题) | 接线审计完成 | [方向审查 §四](discussions/2026-08-17-v095方向审查-验证滞后于抽象与应用层产品化规划.md) |
| P1 | ~~A3 式黄金回归基建~~ **✅ 已完成 (v0.97.0, 2026-09-05)**: `tests/golden/` 5 条合成学习者序列 + `baseline.json` 基线快照 + 容差断言 (atol 1e-8) + 证伪自检 3 项 (seeded drift 必被抓到 / BLAS 微漂移不误报 / 双跑全等抓 RNG 泄漏)。覆盖 deterministic 段 (做题 → 5D/BKT/Bloom/TC 更新 → LCA 干预选择), LLM judge/critic 层后置。基线更新流程: `ECOS_GOLDEN_REGEN=1` + 文档化 diff, 禁止静默覆盖 | ✅ 完成; 后续所有引擎改动跑 `pytest -m regression` | [tests/test_golden_regression.py](tests/test_golden_regression.py) |
| P1 | **观测层补学生自评**: 答题 UI 自评控件 + DB 列 → 9D Confidence 维度获得第二证据源（自报 vs LLM 推断互校; CogMirror A1 校准曲线算法可借鉴） | 黄金回归基建后 | 同上 §三/§四 |
| P1 | H1 形式化验证 (原设 50-100 学生, 视试点结果缩放) | 试点完成 | 方向审查 §四 |
| P1 | C/X 主导题扩量 (从各 5 道到 20+ 道) | lbc001/lbc003 答完现有 C/X 题 | [C/X 重新设计路线图](discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md) |
| P1 | LearningDNA 真实实现 | ≥50 题 + 交互行为数据 | — |
| P2 | **A2 reconcile**: per-misconception 证据驱动权重（evidence_log 原料已就位）, 用学生后续同 skill 表现校准 LLM critic 检测置信度 | 学生自评观测落地后 | 同上 §四 |
| P2 | Plugin SDK 独立打包 / Science-Career 词汇表 / Multi-Domain 落地 | 真实需求牵引 (第二个接入方/领域) | 方向审查结论 3 |

## 关联项目

- **SelfLab（兄弟项目）**：[github.com/cnbison/SelfLab](https://github.com/cnbison/SelfLab)
  - SGE（Self Genesis Engine）—— AI 自我涌现引擎
  - 共享 7 个认知科学工具箱
- **CogMirror（衍生项目, 2026-08-22 从 ECOS 迁移重启）**：本地目录 `/Users/loubicheng/project/CogMirror`
  - 面向成年自学者的 Python 学习认知教练——无 LLM 依赖（静态题库 + 确定性判分）, 与 ECOS 设计取舍相反但互补
  - 兼任 ECOS 确定性算法的廉价试验场（校准曲线 / 证据驱动权重 / 间隔衰减先在单人环境验证）

## 维护者

- **发起人**：Bisen
- **协作**：Claude Code

## 许可证

[MIT License](LICENSE)

---

**创建日期**：2026-06-24
**当前版本**：v0.96.0（2026-08-18 应用层产品化 React 双端：教师端 v0.95 + 学生端 v0.96；Kernel 深化 v0.83-v0.94 收口；验证主线 v0.97 启动）
