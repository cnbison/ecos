# ECOS 2.0 架构提案 - 下一代教育认知运行时

> **版本**：v0.1（2026-08-03，Bisen 战略方向询问后,基于 ChatGPT 系统性深度分析提案)
> **性质**：**架构设计建议（Architecture Proposal）**，不是当前项目已实现的内容。基于 ChatGPT 系统性深度分析前九章形成的 ECOS 2.0 蓝图。
> **基于**：[ECOS系统性深度分析-混合优化版.md](../deep-research/ECOS系统性深度分析-混合优化版.md) 第十部分 + [02-architecture.md v1.4](02-architecture.md) + [10-comprehensive-deep-analysis-2026-08-01.md](10-comprehensive-deep-analysis-2026-08-01.md)
> **后续**：[12-kernel-mapping-current-vs-2.0.md](12-kernel-mapping-current-vs-2.0.md)（现状 vs 蓝图映射表）
> **维护者**：Bisen & Claude

---

## 0. 文档定位

### 0.1 为什么需要这份文档

ECOS 已经在 v0.54.0 -> v0.68.0 高速迭代中长出了完整的功能层：
- **5D MIRT 信念引擎**（K/P/S/C/X 多维 IRT）
- **Bloom Goal Space 6 层目标**
- **TC（Threshold Concept）检测**
- **dual_agent 互校 + LinUCB 策略学习**
- **持久化 + 跨会话状态恢复**
- **245+291 测试套件 + 防御性自检 + 本地 hooks**

但功能堆叠过程中,**架构一致性**开始松动：
- `belief_engine.py` 既是 State Estimator 又是 State Mutator（CQRS 缺失）
- LinUCB `reward` 信号语义在 dual_agent 路径和教学 LCA 路径分叉（v0.69.0 才修）
- Event 概念散落在多个组件（`Observation` / `CalibrationMessage` / `LearningEvent` 没统一）
- Evidence 没有 Engine,只在 calibration_log 里隐式存在

ChatGPT 系统性深度分析（第十部分）提出：**ECOS 2.0 不应该只是增加功能,而应重新定义 Kernel**。本文档承接这个提案,把它写成正式 PRD。

### 0.2 这份文档不是什么

| 这份文档 **不是** | 这份文档 **是** |
|---|---|
| 已实现的代码 | 设计建议（Architecture Proposal） |
| 立即执行的 TODO | 长期演进方向（5 年视角） |
| 推翻现有架构 | 现有架构的沉淀 + 抽象 |
| Phase 5+ 的具体 sprint | Phase 6+ 的 Kernel 重构指南 |

### 0.3 与现有文档的关系

```
v2.0 深度研究 §3 ECOS 完整架构  (理论骨架)
        ↓
02-architecture.md v1.4            (P0 三件套整合 + 工程细化)
        ↓
10-comprehensive-deep-analysis    (4 必答点 + 竞品对比)
        ↓
11-ecos-2.0-architecture-proposal.md  (本文档, Kernel 重构蓝图)
        ↓
12-kernel-mapping-current-vs-2.0.md   (现状 vs 蓝图映射, 演进路线)
```

---

## 1. 设计原则：State-first Computing

### 1.1 ECOS 真正的创新不是 CTA/LCA

ChatGPT 分析的第九部分提出一个关键判断：

> **ECOS 真正的创新,不是 CTA,也不是 LCA。真正创新的是 State-first Computing。**

传统 AI Tutor 是 `Prompt -> Response`,传统 Agent Framework 是 `Observe -> Reason -> Act`。ECOS 多出了一层：

```
Observe
      ↓
Estimate State   ← ECOS 的核心创新
      ↓
Update Twin
      ↓
Plan Policy
      ↓
Execute Learning
      ↓
Collect Evidence
      ↓
Update Belief
```

这意味着 ECOS 不是聊天系统,而是**认知控制系统（Cognitive Control System）**：
- 真实世界 -> Observation -> State Estimation -> Controller -> Action -> Environment
- 对应 ECOS: Student -> Learning Event -> CTA -> Student Twin -> LCA -> Teaching Strategy

教育只是它控制的对象。控制框架不需要变化,控制对象可以变化。

### 1.2 ECOS 的三个关键词

如果不用教育术语,用 AI 系统设计语言描述 ECOS：

> **ECOS 是一种以 State 为中心、以 Evidence 为驱动、以 Policy 为目标的认知计算框架。**

- **State**：长期维护"状态",而不是仅维护"记忆"。Memory 是历史,State 是当前最优解释。
- **Evidence**：数据资产是 Evidence,而不是 Conversation。Conversation 容易过时,Evidence 可以被新模型重新解释。
- **Policy**：决策之前先估计状态,而不是直接 Prompt -> Response。

### 1.3 ECOS 2.0 的核心一句话

> **Everything revolves around State Evolution.（一切围绕状态演化。）**

系统真正关心的不是一次回答是否正确,而是学生状态是否发生了有价值的变化。整个 Runtime 都围绕 State Evolution 来组织。

---

## 2. Kernel 重新定义

### 2.1 引擎层 + 对象层

ECOS 2.0 的 Kernel 由**引擎层**与**对象层**两部分组成--引擎管机制、对象是数据,二者分层不可混淆：

```
                    ECOS 2.0 Kernel

  +------------ 引擎层（Engine，管理机制，不可替换）-------------+
  |  State Engine   Event Engine   Policy Engine              |
  |  Evidence Engine   Evaluation Engine                     |
  +--------------------------------------------------------+
                              |
  +------------ 对象层（Object，被引擎管理的核心数据）-----------+
  |   Twin   Belief   Goal   Event   Policy   Evidence       |
  +--------------------------------------------------------+
```

**Policy 与 Evidence 既是对象、又各自由同名 Engine 管理**（对象是数据,Engine 是机制）,二者并不冲突。

### 2.2 引擎层（5 个 Engine）

#### 2.2.1 State Engine

整个系统**唯一允许修改状态的地方**,负责：
- 状态迁移（State Transition）
- 状态校验（State Validation）
- 状态版本（State Versioning）
- 状态 Replay（按 Event 序列重放）
- 状态 Snapshot（某时刻的完整状态快照）
- 状态 Diff（两个 Snapshot 之间的差异）

**CQRS 原则**：只有 CTA 通过 State Engine 写 Twin,LCA read-only。

#### 2.2.2 Event Engine

统一 Learning Event 的发布、消费与事件流管理,支撑：
- **Replay**：按时间序重放历史事件,重建任意时刻的 Twin 状态
- **Audit**：完整审计链路,任何 Belief 变化可追溯到触发它的 Event
- **Simulation**：在历史事件流上跑假设场景（"如果当时选另一道题会怎样"）
- **Offline Evaluation**：用历史 Event 重新评估 Policy 质量

#### 2.2.3 Policy Engine

维护可学习、可评估、可演化的策略库：
- LinUCB（Contextual Bandits,当前 v0.69.0 已有）
- Thompson Sampling（贝叶斯 Bandit,Phase 6+）
- POMDP Policy（部分可观测 MDP,Phase 7+）
- LLM-as-Policy（LLM 直接做策略推荐,Phase 7+ 实验）

每个 Policy 可独立评估,可热插拔。

#### 2.2.4 Evidence Engine

统一管理 Evidence 的：
- **来源**：哪道题、哪个 Learning Event 触发
- **可信度**：partial credit 0-1 + LLM judge confidence
- **时间戳**：何时收集
- **关联 Goal**：支持哪个 Bloom Goal
- **关联 Belief**：更新了哪个 5D 维度

所有 Belief 都必须由 Evidence 支持。Evidence 是整个系统真正的资产。

#### 2.2.5 Evaluation Engine

回答系统最缺的三个问题：
- **Twin 为何提高？** 归因到具体 Policy / Event / Goal
- **哪个 Policy 最好？** 跨 Policy 对比,AB test 框架
- **哪个 Goal 真正完成？** Goal completion 的客观判定

没有 Evaluation Engine,系统无法持续优化。

### 2.3 对象层（6 个 Object）

#### 2.3.1 Twin（学生数字孪生）

不再保存所有数据,而是整个 Student Aggregate 的入口,负责统一组织：
- **Cognitive Profile**：5D MIRT K/P/S/C/X
- **Learning Profile**：Bloom Profile + TC（Threshold Concept）状态
- **Motivation Profile**：Frustration / Engagement / Confidence 时序
- **Preference Profile**：LearningDNA（visual/auditory/kinesthetic 等）

Twin 不负责计算,Twin 负责一致性。

#### 2.3.2 Belief（统一状态表达）

成为 Runtime 的统一状态表达,字段：
- **Subject**：Belief 针对的对象（如 K 维度 / L3 Bloom / TC-M3）
- **Probability**：概率值 0-1
- **Confidence**：对该概率的把握度 0-1
- **Evidence**：支持该 Belief 的 Evidence 列表
- **UpdatedAt**：最后更新时间

未来 Knowledge / Emotion / Motivation 全部统一为 Belief。

#### 2.3.3 Goal（目标本体）

不再只是 Bloom,而应成为 **Goal Ontology**：
- **Capability**：能力（如"Python 变量理解"）
- **Objective**：目标（如"L3 Apply 层掌握"）
- **Metric**：度量（如"答对概率 ≥ 0.7"）
- **Evidence**：达成证据

这样教育、科研、职业全部支持。

#### 2.3.4 Event（统一输入）

任何输入统一为 Event：
- `AnswerSubmitted`
- `ReflectionCompleted`
- `GoalChanged`
- `HintRequested`
- `IdleDetected`

系统没有其它输入。

#### 2.3.5 Policy（策略对象）

策略对象,由 Policy Engine 管理并可学习演化。包含：
- 策略类型（LinUCB / Thompson / POMDP / LLM）
- 策略参数（LinUCB 的 A/b 矩阵,LLM 的 prompt template）
- 评估指标（accuracy / calibration / engagement）

#### 2.3.6 Evidence（证据）

成为整个系统真正的资产,所有 Belief 都必须由 Evidence 支持。Evidence 包含：
- 来源（哪个 Event 触发）
- 可信度（partial credit + LLM confidence）
- 时间戳
- 关联 Goal
- 关联 Belief

---

## 3. CTA 4 层拆分

### 3.1 当前 CTA 的问题

当前 `belief_engine.py` 把多件事混在一起：
- 接收 Observation（输入）
- 提取特征（feature engineering）
- 推断状态变化（inference）
- 更新 BeliefState（state mutation）

随着 CTA 越来越复杂（v0.69.0+ 要加 LLM Critic / TC Detection / Misconception Detection）,这种混合会让代码难以维护。

### 3.2 ECOS 2.0 CTA 拆分

```
Observation Engine      ← 接收 + 校验输入
        ↓
Feature Extractor       ← 提取特征（partial credit / response time / pattern）
        ↓
Inference Engine         ← 推断（不会 / 粗心 / 猜错 / 知识缺口）
        ↓
Belief Update            ← 通过 State Engine 更新 Twin
```

**职责分离的理由**：
- 学生答错,Observation 只是事实,Inference 才是"不会、粗心、还是猜错"
- 如果混在一起,CTA 会越来越复杂,且无法独立评估每个环节

### 3.3 拆分后的代码组织（建议）

```
ecos/cta/
├── observation_engine.py     # 输入校验 + 标准化
├── feature_extractor.py      # 特征工程
├── inference_engine.py       # 推断（IRT / BKT / DKT / LLM Critic）
├── belief_updater.py         # BeliefState 更新（通过 State Engine）
└── belief_state.py           # 数据结构（不改）
```

---

## 4. LCA 4 层拆分

### 4.1 当前 LCA 的问题

当前 `lca/orchestrator.py` 的 `select_intervention` 一个方法做了 8 步（Bloom 目标 / CA 阶段 / CLT 级别 / Bjork 触发 / 候选生成 / LinUCB 选择 / rationale / 归因）。`_estimate_gain` 简化估算与 LinUCB 预测的语义在 dual_agent 路径和教学 LCA 路径分叉（v0.69.0 才修）。

### 4.2 ECOS 2.0 LCA 拆分

```
Planner                 ← 决定下一步（选 Bloom / CA / CLT）
        ↓
Experiment Designer     ← 设计教学实验（生成候选 + 评估设计）
        ↓
Evaluator               ← 判断效果（actual_outcome + calibration）
        ↓
Policy Learner          ← 长期优化（LinUCB / Thompson / POMDP）
```

**职责分离的理由**：
- Planner 决定"做什么"
- Experiment Designer 决定"怎么做"（设计教学实验）
- Evaluator 决定"做得怎么样"
- Policy Learner 决定"下次怎么改"

这样 LCA 真正成长,而不是 Prompt 越来越长。

### 4.3 拆分后的代码组织（建议）

```
ecos/lca/
├── planner.py                # Bloom / CA / CLT 决策
├── experiment_designer.py    # 候选生成 + 实验设计
├── evaluator.py              # 效果评估
├── policy_learner.py         # LinUCB + Thompson + POMDP
└── intervention.py           # 数据结构（不改）
```

---

## 5. Runtime 生命周期（Event-driven）

### 5.1 当前 Runtime 偏 Workflow

当前 `process_observation` 是同步 workflow：
```
observation -> CTA.update -> LCA.select -> intervention -> next
```

ECOS 2.0 建议完全 Event-driven：

```
Learning Event
        ↓
   Event Bus
        ↓
       CTA
        ↓
   State Engine
        ↓
   Twin Updated
        ↓
       LCA
        ↓
   Intervention
        ↓
   New Event
```

整个闭环自动运行。Runtime 不关心 LLM,只关心 State。

### 5.2 Event-driven 的好处

- **Replay**：任何时刻可重放事件流,重建 Twin
- **Audit**：完整审计链路
- **Simulation**：在事件流上跑假设场景
- **Decoupling**：CTA / LCA / UI 完全解耦,通过 Event Bus 通信

---

## 6. Runtime API

### 6.1 核心 API

ECOS 2.0 的 Runtime 围绕 6 个核心 API：

```python
# 估计当前状态（基于历史 Event）
state = runtime.estimate(student_id)

# 更新 Belief（基于新 Evidence）
runtime.update_belief(student_id, evidence)

# 重放历史事件（重建某时刻状态）
state_at_t = runtime.replay(student_id, timestamp=t)

# 评估 Policy 质量
metrics = runtime.evaluate(student_id, policy_id)

# 模拟假设场景
sim_result = runtime.simulate(student_id, hypothetical_event)

# 规划下一步干预
intervention = runtime.plan(student_id)
```

### 6.2 API 设计原则

- 任何 UI / Agent / LLM **只能通过 Runtime API** 与 Kernel 交互
- 不能直接操作 Twin / Belief / Goal
- 不能直接调 LCA.select_intervention 或 CTA.update
- Plugin 只能产生 Event,不能直接修改 State

---

## 7. Plugin SDK 边界

### 7.1 当前 Plugin 边界模糊

当前 `web/api/` 下的端点（`/api/answer` / `/api/judge` / `/api/dual_agent`）直接操作 BeliefEngine / LCAEngine,没有清晰的 Plugin 边界。

### 7.2 ECOS 2.0 Plugin 原则

如果 ECOS 未来开放 SDK,建议：
- **Plugin 不调用 Twin**（不能直接 BeliefState）
- **Plugin 只能产生 Event**（例如 Quiz Plugin -> Answer Event -> Runtime）
- **Plugin 通过 Runtime API 读状态**（read-only）

这样 Plugin 永远不会破坏 Kernel,这是大型平台最重要的原则。

### 7.3 Plugin 类型示例

| Plugin 类型 | 输入 | 输出（Event） |
|---|---|---|
| Quiz Plugin | 题目数据 | `AnswerSubmitted` |
| Reflection Plugin | 学生反思文本 | `ReflectionCompleted` |
| Hint Plugin | 提示请求 | `HintRequested` |
| Analytics Plugin | 订阅 Event 流 | （无输出,只读） |

---

## 8. 现状 vs 2.0 蓝图映射

### 8.1 现有代码已经接近的部分

| ECOS 2.0 概念 | 现有代码 | 接近度 |
|---|---|---|
| State Engine（部分） | `ecos/cta/belief_engine.py` | 60% -- 既是 State Estimator 又是 Mutator,CQRS 缺失 |
| Twin（部分） | `ecos/cta/belief_state.py` 的 `BeliefState` | 70% -- 已有 5D + Bloom + TC + LearningDNA,缺 Motivation Profile 独立 |
| Belief（部分） | `DimensionState` (K/P/S/C/X) | 60% -- 已有 mastery_prob + confidence,缺 Evidence 关联 |
| Goal（部分） | `BloomProfile` + `select_bloom_target` | 50% -- 只有 Bloom,缺 Capability / Objective / Metric / Evidence |
| Event（部分） | `Observation` + `CalibrationMessage` | 40% -- 概念散落,没统一 |
| Policy Engine（部分） | `ecos/lca/l4_optimization/linucb.py` | 80% -- LinUCB 已有,缺 Thompson / POMDP / LLM |
| Evidence Engine（缺失） | `calibration_log` 表（隐式） | 20% -- 数据在但没 Engine 管理 |
| Evaluation Engine（缺失） | `compute_h3_ece.py`（外部脚本） | 10% -- 只是 H3 验证,不是 Runtime 组件 |
| Event Engine（缺失） | 无 | 0% -- 完全没有 |

### 8.2 详细映射见 12-kernel-mapping-current-vs-2.0.md

本文档只做概念性映射,详细到文件:行号的映射见 [12-kernel-mapping-current-vs-2.0.md](12-kernel-mapping-current-vs-2.0.md)。

---

## 9. 演进路线（5 年视角）

### 9.1 Phase 5 后期（v0.71-0.73）-- Kernel 稳定化

前提：v0.69.0 H3 验证通过（B4+C1+D1 方案有效）。

- **v0.71.0**：把 `belief_engine.py` 拆为 `State Engine` + `Belief 对象`（CQRS 落地）
- **v0.72.0**：引入 `Event Engine`（统一 Observation + CalibrationMessage 为 LearningEvent）
- **v0.73.0**：引入 `Evaluation Engine`（runtime 内置评估,替代外部脚本）

### 9.2 Phase 6（v0.74-0.78）-- CTA / LCA 拆分

- **v0.74.0**：CTA 4 层拆分（Observation / Feature / Inference / Belief Update）
- **v0.75.0**：LCA 4 层拆分（Planner / Experiment Designer / Evaluator / Policy Learner）
- **v0.76.0**：引入 Thompson Sampling（Policy Engine 第二个 Policy）
- **v0.77.0**：引入 Evidence Engine（统一 Evidence 管理）
- **v0.78.0**：Runtime API 公开（estimate / update_belief / replay / evaluate / simulate / plan）

### 9.3 Phase 7+（v0.79+）-- 通用 Cognitive Runtime 推演

前提：Phase 6 Kernel 稳定 + 真实数据验证 + 5 学科扩展完成。

- 抽象 Student Twin -> Human Twin
- 抽象 Learning Goal -> Goal
- 抽象 CTA -> State Estimator
- 抽象 LCA -> Policy Planner
- 抽象 Learning Event -> Cognitive Event

这样 ECOS 不再依赖教育,变成通用 Cognitive Runtime。**这是推演,不是当前项目已实现的能力**。

### 9.4 5 年后（2030 年前后）

ChatGPT 分析的判断：

> 那个时候教育只是 Runtime 的第一个 Domain,未来还会出现 Research Runtime / Healthcare Runtime / Career Runtime / Creative Runtime,而 Kernel 其实一样。

ECOS 的长期价值取决于它是否能够把这些设计从"架构理念"转化为"经过真实数据验证的科学系统"。

---

## 10. 不做的事（Out of Scope）

### 10.1 ECOS 2.0 明确不做

1. **不推倒现有架构** -- 现有 CTA/LCA/dual_agent 设计是对的,只是需要沉淀
2. **不立即拆分 CTA/LCA** -- 先稳定 H3 验证 + Kernel 抽象,再拆
3. **不引入新 LLM** -- LLM 是实现方式,不是设计思想
4. **不做多 Domain 扩展** -- Phase 7+ 才考虑,现在专注教育
5. **不做 Plugin SDK 公开** -- Plugin 边界先在内部落地,再考虑开放
6. **不做 Production 部署** -- ECOS 仍是研究项目,不追求 SLA

### 10.2 何时启动 Kernel 重构

**触发条件**（满足任一即可启动）：
- v0.69.0 H3 验证通过（B4 方案有效,confidence 指标选对了）
- 现有架构在加新功能时反复出现 CQRS 违反 / Event 散落 / Evidence 缺失
- Bisen 主动决定推进 Kernel 稳定化

**不触发条件**（满足任一则推迟）：
- v0.69.0 H3 验证失败（B4 方案无效,需回滚或重设计）
- 现有架构能稳定支持新功能（不阻塞）
- Bisen 认为应该先做 5 学科扩展 / 教师端 / 家长端

---

## 11. 三个核心判断（承接 ChatGPT 分析）

经过 10 个部分的分析,整份报告可收敛为三个核心判断：

### 11.1 ECOS 的真正创新

> **ECOS 的真正创新不在于 AI Tutor,而在于 Student Twin 驱动的状态建模。**

它尝试把教育从"课程中心"转向"状态中心",这是比功能创新更深的一层架构创新。

### 11.2 ECOS 已经具备形成 Educational Cognitive Runtime 的基本框架

CTA/LCA、Belief、Goal、Learning Event 等核心对象之间已形成较完整的闭环,但 State Engine、Evidence Engine、Evaluation Engine 等基础能力仍需进一步沉淀。

### 11.3 ECOS 的长期价值取决于数据 + Belief + Policy 的科学化

> **真正的护城河不会来自某个大模型,也不会来自某个 Prompt,而来自长期积累的认知数据、可解释的 Belief 模型以及能够持续优化的 Policy 机制。**

---

## 12. 最后的自我修正

本文档区分**事实**与**推演**：

- **根据当前源码和设计,可以明确支持的结论**：ECOS 正在构建一个以 Student Twin 为核心的教育认知运行时（Educational Cognitive Runtime）。
- **根据其抽象层次所做的推演**：如果未来进一步抽象 Twin、Goal、Event 等核心概念,它**具有**扩展到更广泛认知领域的潜力,但这仍需要新的理论定义、工程实现和实际验证。

保持这种"事实"与"推演"的边界,会让本提案既有前瞻性,也保持技术分析应有的严谨性。

---

## 附：与 ChatGPT 分析的对应关系

| ChatGPT 分析章节 | 本文档章节 |
|---|---|
| 第十部分 §1 重新定义 Kernel | §2 Kernel 重新定义 |
| 第十部分 §2 重新定义 Kernel（5+6） | §2.2 + §2.3 |
| 第十部分 §3 重新设计 CTA | §3 CTA 4 层拆分 |
| 第十部分 §4 重新设计 LCA | §4 LCA 4 层拆分 |
| 第十部分 §5 增加三个新的 Engine | §2.2.4 + §2.2.5 + (Evaluation Engine) |
| 第十部分 §6 重新设计 Runtime | §5 Runtime 生命周期 |
| 第十部分 §7 重新定义 Plugin SDK | §7 Plugin SDK 边界 |
| 第十部分 §8 新增 Runtime API | §6 Runtime API |
| 第十部分 §9 ECOS 2.0 总体架构 | §2.1 + §5.1 |
| 第十部分 §10 站在五年后的视角 | §9.4 5 年后 |
| 第十部分 §11 最终评价 | §11 三个核心判断 |
| 第十部分 最后的自我修正 | §12 最后的自我修正 |

---

**创建日期**：2026-08-03
**维护者**：Bisen & Claude
**下次更新**：v0.71.0 Kernel 重构启动时（前提：v0.69.0 H3 验证通过）
