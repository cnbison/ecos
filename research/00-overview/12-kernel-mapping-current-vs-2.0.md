# ECOS Kernel 现状-蓝图映射表

> **版本**：v0.1（2026-08-03，承接 [11-ecos-2.0-architecture-proposal.md](11-ecos-2.0-architecture-proposal.md)）
> **性质**：**现状 vs 蓝图映射表**，把 ECOS 2.0 概念与现有代码对应,让"现状 vs 蓝图"差距可见,指导后续 P2 决策。
> **基于**：[11-ecos-2.0-architecture-proposal.md](11-ecos-2.0-architecture-proposal.md) + 现有 v0.69.0 代码
> **维护者**：Bisen & Claude

---

## 0. 文档目标

### 0.1 为什么需要这份映射表

[11-ecos-2.0-architecture-proposal.md](11-ecos-2.0-architecture-proposal.md) 提出了 ECOS 2.0 的 5 引擎 + 6 对象蓝图。但蓝图距离现有代码有多远? 现有代码哪些已经接近 2.0,哪些完全缺失?

这份映射表回答：
- **现有代码已经做了什么**（避免重复造轮子）
- **现有代码缺什么**（指导 P2 / Phase 6 重构）
- **现有代码做错了什么**（避免重蹈覆辙）

### 0.2 阅读方式

- 每行一个 2.0 概念,映射到现有代码的 文件:行号 或 类名
- **接近度**：0%（缺失）/ 20%（隐式存在）/ 50%（部分实现）/ 80%（已实现但需抽象）/ 100%（已实现且符合 2.0 设计）
- **演进建议**：每个映射给出 P2 / Phase 6 的具体动作

---

## 1. 引擎层映射（5 Engine）

### 1.1 State Engine

**2.0 定义**：整个系统唯一允许修改状态的地方,负责状态迁移 / 校验 / 版本 / Replay / Snapshot / Diff。CQRS 原则：只有 CTA 通过 State Engine 写 Twin,LCA read-only。

| 现有代码 | 接近度 | 说明 |
|---|---|---|
| `ecos/cta/state_engine.py:StateEngine` (v0.80.0) | 70% | 4/6 职责已实现: commit/validate/snapshot/diff. Replay/Simulation 推迟到 v0.81 Event Engine |
| `ecos/cta/belief_engine.py:BeliefEngine.update` | 60% | 已有 state mutation（K/P/S/C/X mastery_prob 更新）,但**既是 State Estimator 又是 State Mutator**（CQRS 缺失）. v0.80.0-b 起走 BeliefUpdator 委托 StateEngine.commit |
| `ecos/cta/belief_engine.py:BeliefEngine.create_initial_state` | 80% | 已有冷启动 state init,接近 State Engine 的 create_snapshot |
| `ecos/cta/belief_state.py:StateSnapshot` | 60% | 已有快照概念,但不是 State Engine 管理的,而是 BeliefState 内嵌的 trajectory |
| `ecos/cta/belief_state.py:TrajectoryState` | 70% | 已有 state trajectory（100 个 snapshot 限长）,接近 Replay 能力 |
| `ecos/cta/belief_state.py:BeliefState.validate` (v0.80.0) | 100% | Schema + range 校验 (5D / bloom / C / TC / overall / theta shape) |
| `ecos/cta/belief_state.py:BeliefState.bump_version` (v0.80.0) | 100% | version = f'v1.0+{event_id}', last_updated = now() |
| `ecos/cta/state_engine.py:StateEngine.diff` (v0.80.0) | 100% | 结构化 diff (changed_fields / old_values / new_values / delta_magnitudes) |

**演进建议**：
- **v0.80.0** ✅: StateEngine + validate + snapshot + diff 落地 (4/6 职责). apply_snapshot 改 shim 委托 StateEngine.commit
- **v0.80.0-b** ✅: InferenceEngine (pure) + BeliefUpdator (sole mutator) 提取, `update()` 改 facade. 5 个 critical 不变量 test 验证 InferenceEngine.run() 不 mutate state. 4-layer 拆分完成度 30% -> 60%
- **v0.80.0-c** ✅: ObservationEngine + FeatureExtractor 提取, `__getattr__` forwarding 兼容 web/api/belief.py:189-191 直写. `update()` 改 pure orchestration (30 行). 4-layer 拆分完成度 60% -> 80%
- **v0.80.0 final** ✅: 防御性自检 [8] AST 扫描 direct state mutation (soft warning, v0.81 hard block). +177 tests (431 -> 554 pytest). H3-c4 全 3 学生 PASS
- **v0.80.0-d 决策**: InferenceEngine 不 sub-split (365 行含 110 行 dataclass, 实际逻辑 185 行, 5 子组件已分文件)
- **v0.81.0**：Replay/Simulation (依赖 Event Engine)

### 1.2 Event Engine

**2.0 定义**：统一 Learning Event 的发布 / 消费 / 事件流管理,支撑 Replay / Audit / Simulation / Offline Evaluation。

| 现有代码 | 接近度 | 说明 |
|---|---|---|
| `ecos/cta/belief_engine.py:Observation` | 40% | 已有"观测"概念,但只是 dataclass,不是 Event Bus 上的消息 |
| `ecos/dual_agent/protocol/messages.py:CalibrationMessage` | 30% | 已有 Message 类型枚举（OBSERVATION / CTA_LCA_CALIBRATED 等）,但没 Event Bus |
| `ecos/dual_agent/protocol/messages.py:MessageType` | 50% | 已有 10 种 MessageType,接近 Event 类型分类 |
| `web/api/belief.py` _response_history | 40% | 隐式 Event 流（按时间序的答题记录）,但不是统一 Event |
| `web/api/dual_agent.py` calibration_log 表 | 30% | 隐式 Event 流（dual_agent 互校历史）,但跟 response_history 没统一 |
| **缺失：Event Bus** | 0% | 没有 pub/sub 机制 |
| **缺失：Event Replay** | 0% | 不能按 Event 序列重放重建 Twin |
| **缺失：Event Simulation** | 0% | 不能在历史 Event 流上跑假设场景 |

**演进建议**：
- **v0.72.0**：统一 `Observation` + `CalibrationMessage` 为 `LearningEvent`（Event Engine 入口）
- **v0.73.0**：加 Event Bus（in-process pub/sub）
- **Phase 6+**：加 Event Replay + Simulation

### 1.3 Policy Engine

**2.0 定义**：维护可学习 / 可评估 / 可演化的策略库（LinUCB / Thompson / POMDP / LLM-as-Policy）。

| 现有代码 | 接近度 | 说明 |
|---|---|---|
| `ecos/lca/l4_optimization/linucb.py:LinUCB` | 80% | LinUCB 已有,接口清晰（select_arm / update） |
| `ecos/lca/l4_optimization/policy_learner.py:LCAPolicyLearner` | 80% | LinUCB 包装 + 上下文构建 + arm 候选映射 |
| `ecos/lca/orchestrator.py:LCAEngine._estimate_gain` | 60% | 简化估算策略（scale × (1-K) × scaffolding）,不是 LinUCB 但属于 Policy 库的一员 |
| `ecos/dual_agent/orchestrator.py:_compute_dual_agent_confidence` (v0.69.0) | 50% | LinUCB θ@x 预测,属于 Policy Engine 的"预测接口",但不是独立 Engine |
| **缺失：Thompson Sampling** | 0% | 没有贝叶斯 Bandit |
| **缺失：POMDP Policy** | 0% | 没有部分可观测 MDP |
| **缺失：LLM-as-Policy** | 0% | LLM 只做 rationale / critic,不做策略推荐 |
| **缺失：Policy 评估框架** | 0% | 没有 AB test 框架（不能对比 LinUCB vs Thompson） |

**演进建议**：
- **v0.76.0**：引入 Thompson Sampling（Policy Engine 第二个 Policy）
- **v0.77.0**：加 Policy 评估框架（offline evaluation + AB test）
- **Phase 7+**：实验 LLM-as-Policy

### 1.4 Evidence Engine

**2.0 定义**：统一管理 Evidence 的来源 / 可信度 / 时间 / 关联 Goal / 关联 Belief。所有 Belief 都必须由 Evidence 支持。

| 现有代码 | 接近度 | 说明 |
|---|---|---|
| `web/api/dual_agent.py` calibration_log 表 | 30% | 隐式存 Evidence（actual_outcome / dual_agent_confidence）,但不是 Engine 管理 |
| `web/api/belief.py` _response_history | 30% | 隐式存 Evidence（答题历史 + mastery_prob_after）,但跟 calibration_log 没统一 |
| `ecos/cta/belief_state.py:BeliefState.evidence_predictions` | 40% | 已有"证据预测"字段（v0.5.0 加）,但只是 dict 占位 |
| `ecos/cta/l2_mirt.py` partial credit 评分 | 50% | 已经是 Evidence（partial credit 0-1 + ai_reasoning）,但没统一管理 |
| `ecos/cta/llm_critic/` | 40% | LLM Critic 产生 Evidence（confidence + reasoning）,但没 Engine |
| **缺失：Evidence 统一 schema** | 0% | Evidence 散落在 5+ 处,没统一数据结构 |
| **缺失：Evidence-Belief 关联** | 0% | 不能追溯"这个 K.mastery_prob=0.7 由哪些 Evidence 支持" |

**演进建议**：
- **v0.77.0**：引入 Evidence Engine（统一 Evidence schema + 关联管理）
- **v0.78.0**：把 calibration_log + response_history + llm_critic_results 统一为 Evidence 流

### 1.5 Evaluation Engine

**2.0 定义**：回答"Twin 为何提高 / 哪个 Policy 最好 / 哪个 Goal 完成"。

| 现有代码 | 接近度 | 说明 |
|---|---|---|
| `scripts/compute_h3_ece.py` | 30% | H3 验证脚本（外部）,评估"双 Agent 互校是否优于单",但不是 Runtime 内置 |
| `ecos/lca/l4_optimization/attribution.py:LCAAttribution` | 50% | 已有因果归因（CausalEffect + estimated_ate）,但简化版 |
| `ecos/dual_agent/orchestrator.py:_consecutive_ineffective` | 40% | 已有"连续无效干预"计数,接近 Evaluation 的雏形 |
| `ecos/metrics/ece.py` | 40% | 已有 ECE 计算（Expected Calibration Error）,但只是 metric,不是 Engine |
| **缺失：Twin 变化归因** | 0% | 不能回答"Twin 为何从 K=0.5 提到 K=0.7"（归因到具体 Policy / Event） |
| **缺失：Policy 对比** | 0% | 不能 AB test LinUCB vs Thompson |
| **缺失：Goal completion 判定** | 0% | 没有"Goal 完成"的客观判定（如 K ≥ 0.7 + Bloom L3 + TC 通过） |

**演进建议**：
- **v0.73.0**：把 `compute_h3_ece.py` 内置为 Runtime Evaluation Engine
- **v0.74.0**：加 Twin 变化归因（基于 Event 流 + State Diff）
- **v0.77.0**：加 Policy 对比框架

---

## 2. 对象层映射（6 Object）

### 2.1 Twin（学生数字孪生）

**2.0 定义**：整个 Student Aggregate 的入口,统一组织 Cognitive / Learning / Motivation / Preference Profile。Twin 不负责计算,负责一致性。

| 现有代码 | 接近度 | 说明 |
|---|---|---|
| `ecos/cta/belief_state.py:BeliefState` | 70% | 已有 5D + Bloom + TC + LearningDNA + trajectory + misconceptions,接近 Twin |
| `BeliefState.K/P/S/C/X` (DimensionState) | 80% | Cognitive Profile 已有 |
| `BeliefState.bloom_profile` | 80% | Learning Profile 已有（Bloom 部分） |
| `BeliefState.tc_states` | 70% | Learning Profile 已有（TC 部分） |
| `BeliefState.learning_dna` | 70% | Preference Profile 已有（但标"待启用"） |
| **缺失：Motivation Profile** | 0% | 没有 Frustration / Engagement / Confidence 时序独立组件（X 维度接近但混在 5D 里） |
| **缺失：Twin 一致性保证** | 0% | 没有跨 Profile 一致性校验（如 K mastery + Bloom L3 + TC 通过是否一致） |

**演进建议**：
- **v0.71.0**：把 `BeliefState` 重命名为 `StudentTwin`（语义清晰）
- **v0.72.0**：拆 Motivation Profile 独立（X 维度从 5D 抽出）
- **v0.73.0**：加 Twin 一致性校验

### 2.2 Belief（统一状态表达）

**2.0 定义**：Runtime 的统一状态表达,字段 Subject / Probability / Confidence / Evidence / UpdatedAt。未来 Knowledge / Emotion / Motivation 全部统一为 Belief。

| 现有代码 | 接近度 | 说明 |
|---|---|---|
| `ecos/cta/belief_state.py:DimensionState` | 60% | 已有 theta / se / mastery_prob / confidence,接近 Belief |
| `BeliefState.K.mastery_prob` | 70% | Probability 已有 |
| `BeliefState.K.confidence` | 70% | Confidence 已有 |
| **缺失：Subject 字段** | 0% | DimensionState 没有"针对什么"字段（隐含在属性名 K 里） |
| **缺失：Evidence 关联** | 0% | DimensionState 不关联 Evidence 列表 |
| **缺失：UpdatedAt** | 0% | DimensionState 没有独立时间戳（BeliefState 有 last_updated） |

**演进建议**：
- **v0.71.0**：把 `DimensionState` 改名为 `Belief`,加 `subject` + `evidence_ids` + `updated_at` 字段
- **v0.77.0**：把 Bloom / TC / LearningDNA 也统一为 Belief 表达

### 2.3 Goal（目标本体）

**2.0 定义**：Goal Ontology,字段 Capability / Objective / Metric / Evidence。不再只是 Bloom。

| 现有代码 | 接近度 | 说明 |
|---|---|---|
| `ecos/cta/belief_state.py:BloomProfileState` | 50% | 只有 Bloom 6 层（remember / understand / apply / analyze / evaluate / create）,不是 Goal Ontology |
| `ecos/lca/intervention.py:select_bloom_target` | 40% | 选 Bloom 目标层,但不是 Goal Ontology 的 Capability / Objective / Metric |
| `ecos/cta/belief_state.py:TCState` | 40% | TC 状态（post_liminal / mastery 等）,接近 Goal 的"完成判定"但不是 Goal 本身 |
| **缺失：Capability** | 0% | 没有"Python 变量理解"这种能力描述 |
| **缺失：Objective** | 0% | 没有"L3 Apply 层掌握"这种目标 |
| **缺失：Metric** | 0% | 没有"答对概率 ≥ 0.7"这种度量 |
| **缺失：Evidence 关联** | 0% | Goal 不关联达成证据 |

**演进建议**：
- **Phase 6+**：引入 Goal Ontology（Capability -> Objective -> Metric -> Evidence）
- **Phase 7+**：扩展到非教育 Domain（如科研 / 职业）

### 2.4 Event（统一输入）

**2.0 定义**：任何输入统一为 Event（AnswerSubmitted / ReflectionCompleted / GoalChanged / HintRequested / IdleDetected）。

| 现有代码 | 接近度 | 说明 |
|---|---|---|
| `ecos/cta/belief_engine.py:Observation` | 40% | 已有"观测"概念,但只是 dataclass,不是 Event 类型 |
| `ecos/dual_agent/protocol/messages.py:MessageType` | 50% | 已有 10 种 MessageType 枚举（OBSERVATION / CTA_LCA_CALIBRATED 等）,接近 Event 类型分类 |
| `ecos/dual_agent/protocol/messages.py:CalibrationMessage` | 40% | 已有 Message 包装,但不是统一 Event |
| **缺失：Event 类型统一** | 0% | Observation / CalibrationMessage / response_history 没统一为 LearningEvent |
| **缺失：AnswerSubmitted / ReflectionCompleted / GoalChanged / HintRequested / IdleDetected** | 0% | 没有这些具体 Event 类型 |
| **缺失：Event Bus** | 0% | 没有 pub/sub 机制 |

**演进建议**：
- **v0.72.0**：统一为 `LearningEvent`（含 5 种子类型）
- **v0.73.0**：加 Event Bus

### 2.5 Policy（策略对象）

**2.0 定义**：策略对象,由 Policy Engine 管理并可学习演化。包含策略类型 / 参数 / 评估指标。

| 现有代码 | 接近度 | 说明 |
|---|---|---|
| `ecos/lca/l4_optimization/linucb.py:LinUCB` | 70% | LinUCB 已有（A/b 矩阵 + arm_pull_counts）,接近 Policy 对象 |
| `ecos/lca/l4_optimization/policy_learner.py:LCAPolicyLearner` | 60% | LinUCB 包装,接近 Policy 对象,但策略类型不显式 |
| `ecos/lca/intervention.py:Intervention` | 50% | 已有 Intervention 数据结构,接近 Policy 的"输出",但不是 Policy 本身 |
| **缺失：策略类型字段** | 0% | LinUCB 不知道自己是 LinUCB（没 type 字段） |
| **缺失：策略参数抽象** | 0% | A/b 矩阵是 LinUCB 专属,Thompson / POMDP 没法复用 |
| **缺失：策略评估指标** | 0% | Policy 不带 accuracy / calibration / engagement 指标 |

**演进建议**：
- **v0.76.0**：抽象 `Policy` 基类（type / params / metrics）
- **v0.77.0**：LinUCB / Thompson / POMDP 都继承 `Policy`

### 2.6 Evidence（证据）

**2.0 定义**：整个系统真正的资产,所有 Belief 都必须由 Evidence 支持。

| 现有代码 | 接近度 | 说明 |
|---|---|---|
| `web/api/belief.py` _response_history 字段 | 40% | 隐式 Evidence（problem_id / correct / score / ai_reasoning） |
| `web/api/dual_agent.py` calibration_log.message_payload | 30% | 隐式 Evidence（actual_outcome / dual_agent_confidence） |
| `ecos/cta/belief_state.py:BeliefState.evidence_predictions` | 40% | 占位字段（v0.5.0 加）,没真正用 |
| `ecos/cta/l2_mirt.py:MIRTConfig.partial_credit` | 50% | partial credit 评分已经是 Evidence |
| `ecos/cta/llm_critic/` | 40% | LLM Critic 产生 Evidence |
| **缺失：Evidence 统一 schema** | 0% | Evidence 散落 5+ 处 |
| **缺失：Evidence-Belief 关联** | 0% | 不能追溯 Belief 由哪些 Evidence 支持 |
| **缺失：Evidence 可信度计算** | 0% | 没有"这条 Evidence 多可信"的统一算法 |

**演进建议**：
- **v0.77.0**：引入 Evidence Engine + 统一 schema
- **v0.78.0**：所有 Belief 必须关联 Evidence

---

## 3. CTA 4 层拆分映射

**2.0 定义**：Observation Engine -> Feature Extractor -> Inference Engine -> Belief Update。

| 现有代码 | 接近度 | 说明 |
|---|---|---|
| **Observation Engine** | | |
| `ecos/cta/belief_engine.py:Observation` dataclass | 40% | 已有 Observation 数据结构, v0.80.0-c 提取 ObservationEngine |
| `BeliefEngine.update` 输入校验 | 30% | 隐式输入校验（score 范围 / correct 派生）,但散落在 update 内 |
| **Feature Extractor** | | |
| `BeliefEngine.update` 内 feature engineering | 30% | 隐式特征提取（partial credit / correct / bloom_level）, v0.80.0-c 提取 FeatureExtractor |
| **Inference Engine** | | |
| `ecos/cta/inference_engine.py:InferenceEngine` (v0.80.0-b) | 80% | 已提取, 接口 `run(state, observation, ctx, history) -> InferenceResult` (pure, no state mutation). BKT/MIRT/TC/LLM Critic 内部调 |
| `ecos/cta/l2_mirt.py:MIRT.estimate_theta` | 60% | MIRT 推断（5D theta 估计）,已是 Inference 的一部分 |
| `ecos/cta/l1_evolution.py:EvolutionEngine` | 50% | BKT 进化（K/P/S/C/X mastery 演化）,已是 Inference |
| `ecos/cta/tc_detector.py:TCDetector` | 50% | TC 检测,属于 Inference（不会 / 粗心 / 猜错的判别） |
| `ecos/cta/llm_critic/` | 40% | LLM Critic,属于 Inference（深度推断） |
| **Belief Update** | | |
| `ecos/cta/belief_updater.py:BeliefUpdator` (v0.80.0-b) | 90% | 已提取, sole mutation site, `apply(state, result, observation, history_entry) -> event_id` 调 StateEngine.commit |

**演进建议**：
- **v0.74.0**：CTA 4 层拆分
  - `ecos/cta/observation_engine.py`（输入校验 + 标准化）
  - `ecos/cta/feature_extractor.py`（特征工程）
  - `ecos/cta/inference_engine.py`（MIRT + BKT + TC + LLM Critic 统一接口）
  - `ecos/cta/belief_updater.py`（通过 State Engine 更新 Twin）

---

## 4. LCA 4 层拆分映射

**2.0 定义**：Planner -> Experiment Designer -> Evaluator -> Policy Learner。

| 现有代码 | 接近度 | 说明 |
|---|---|---|
| **Planner** | | |
| `ecos/lca/orchestrator.py:LCAEngine.select_intervention` Step 1-4 | 50% | 已有 Bloom 目标 / CA 阶段 / CLT 级别 / Bjork 触发判定,但跟 Experiment Designer 混在一起 |
| **Experiment Designer** | | |
| `ecos/lca/orchestrator.py:_generate_candidates` | 50% | 已有候选生成,但跟 Planner 没分离 |
| `ecos/lca/intervention.py:Intervention` | 50% | 已有 Intervention 数据结构,但不是"实验设计"的语义 |
| **Evaluator** | | |
| `ecos/dual_agent/orchestrator.py` actual_outcome 填充 | 40% | 已有 actual_outcome 评估,但是 dual_agent 路径独有,教学 LCA 路径没 |
| `ecos/lca/l4_optimization/attribution.py:LCAAttribution` | 50% | 已有因果归因,接近 Evaluator |
| **Policy Learner** | | |
| `ecos/lca/l4_optimization/policy_learner.py:LCAPolicyLearner` | 80% | LinUCB Policy Learner 已有 |
| `ecos/lca/l4_optimization/linucb.py:LinUCB` | 80% | LinUCB 已有 |

**演进建议**：
- **v0.75.0**：LCA 4 层拆分
  - `ecos/lca/planner.py`（Bloom / CA / CLT 决策）
  - `ecos/lca/experiment_designer.py`（候选生成 + 实验设计）
  - `ecos/lca/evaluator.py`（actual_outcome + calibration + causal effect）
  - `ecos/lca/policy_learner.py`（LinUCB + Thompson + POMDP）

---

## 5. Runtime API 映射

**2.0 定义**：6 个核心 API（estimate / update_belief / replay / evaluate / simulate / plan）。

| API | 现有代码 | 接近度 |
|---|---|---|
| `estimate(student_id)` | `BeliefEngine.create_initial_state` + `state[student_id]` 查询 | 40% -- 只能查当前 state,不能基于历史 Event 重建 |
| `update_belief(student_id, evidence)` | `BeliefEngine.update(state, observation, ...)` | 60% -- 已有 update,但接口不是 Evidence-driven |
| `replay(student_id, timestamp=t)` | 无 | 0% -- 完全没有 |
| `evaluate(student_id, policy_id)` | `scripts/compute_h3_ece.py` (外部脚本) | 20% -- 外部脚本,不是 Runtime API |
| `simulate(student_id, hypothetical_event)` | 无 | 0% -- 完全没有 |
| `plan(student_id)` | `LCAEngine.select_intervention(cta_input)` | 60% -- 已有,但接口不是 Runtime API 风格 |

**演进建议**：
- **v0.78.0**：公开 Runtime API（6 个核心 API）
- **Phase 7+**：所有 UI / Agent / LLM 通过 Runtime API 交互

---

## 6. Plugin SDK 边界映射

**2.0 定义**：Plugin 不调用 Twin,Plugin 只能产生 Event。

| 现有代码 | 接近度 | 说明 |
|---|---|---|
| `web/api/answer.py` (POST /api/answer) | 40% | 已有 API 端点,但直接调 BeliefEngine.update,不是产生 Event |
| `web/api/judge.py` (POST /api/judge) | 40% | 已有 LLM judge,但直接更新 response_history,不是产生 Event |
| `web/api/dual_agent.py` (POST /api/dual_agent) | 40% | 已有 dual_agent 入口,但直接调 orch.process_observation,不是产生 Event |
| `web/api/lca.py` (LCA 路径) | 40% | 同上 |
| **缺失：Plugin 只产生 Event 原则** | 0% | 所有 web/api/ 端点直接操作内部 Engine |

**演进建议**：
- **v0.78.0+**：所有 `web/api/` 端点改为产生 Event,通过 Event Bus 推到 Runtime
- **Phase 7+**：开放 Plugin SDK

---

## 7. 抗幻觉与质量保障映射（v0.60.0+ 已有部分） — **[v0.75.1]** 章节保留, "抗幻觉"叙事已部分调整 (Fast Calibration + Wide Coverage)

**2.0 定义**：Kernel 纯粹性 + 抗幻觉机制。

| 现有代码 | 接近度 | 说明 |
|---|---|---|
| `ecos/dual_agent/anti_hallucination/belief_check.py:BeliefDistributionCheck` | 70% | 已有信念分布合理性检查 |
| `ecos/dual_agent/anti_hallucination/experiment_design.py:ExperimentDesignValidator` | 70% | 已有实验设计合理性检查 |
| `ecos/dual_agent/anti_hallucination/human_review.py:HumanReviewTrigger` | 60% | 已有人工审核触发 |
| `ecos/dual_agent/deadlock/timeout.py:TimeoutGuard` | 70% | 已有超时保护 |
| `ecos/dual_agent/deadlock/fallback.py:SingleAgentFallback` | 70% | 已有单 Agent 降级 |
| **245+291 测试 + 5 项防御性自检 + pre-commit/pre-push hooks** | 90% | 已有完善的测试 + 自检基础设施 |

**演进建议**：
- **保持**：抗幻觉机制和测试基础设施是 ECOS 的强项,2.0 不需要重做 — **[v0.75.1]** 模块 (anti_hallucination/) 实现保留, 命名保留, docstring 已加修订说明
- **加强**：把抗幻觉从 dual_agent 路径抽出来,作为 State Engine 的校验层（CQRS 配套）

---

## 8. 总览：现状 vs 蓝图差距

### 8.1 按接近度排序

| 接近度 | 组件 | 数量 |
|---|---|---|
| 80%+ | LinUCB / LCAPolicyLearner / 测试基础设施 / 抗幻觉 | 4 — **[v0.75.1]** "抗幻觉" 调整为 "互校机制 (Fast Calibration + Wide Coverage)" |
| 60-80% | BeliefState(Twin 雏形) / DimensionState(Belief 雏形) / MIRT(Inference) / BKT(Inference) | 4 |
| 40-60% | Observation / CalibrationMessage / partial credit / LLM Critic / attribution | 5 |
| 20-40% | calibration_log / response_history / evidence_predictions 占位 | 3 |
| 0-20% | State Engine 抽象 / Event Bus / Evidence Engine / Evaluation Engine / Goal Ontology / Replay / Simulation | 7 |

### 8.2 缺失核心组件清单

完全缺失（接近度 ≤ 20%）：
1. **State Engine 抽象**（CQRS 缺失）
2. **Event Bus**（pub/sub 机制）
3. **Evidence Engine**（Evidence 统一管理）
4. **Evaluation Engine**（Twin 变化归因 / Policy 对比 / Goal completion）
5. **Goal Ontology**（Capability / Objective / Metric / Evidence）
6. **Event Replay**（按 Event 序列重建 Twin）
7. **Event Simulation**（假设场景模拟）
8. **Policy 评估框架**（AB test LinUCB vs Thompson）

### 8.3 演进优先级建议

> **[v0.77 更新 2026-08-05]**: P2 State Engine 完整重构评估结论为"暂缓,等 Phase 6 自然时机"。
> 触发原因: v0.75.3 fingerprint 修复后 H3-c3 已通过 (entropy 2.546), v0.76 跨学生验证普适 (3/3 PASS),
> LCA 路径已 read-only (CQRS 事实遵守), 真正 CQRS 违反集中在 web/api/belief.py DB 恢复路径 (15+ 处直接 mutation)。
> 详见 [discussions/2026-08-05-v077-p2-state-engine-evaluation.md](../../discussions/2026-08-05-v077-p2-state-engine-evaluation.md)。
> 替代方案: v0.77 加 `BeliefState.apply_snapshot()` 收口 DB 恢复路径 (方案 B, ~150 行, 低风险), Phase 6 跟 CTA 4 层拆分一起做完整 State Engine (方案 D)。

**v0.77 (短期)** -- 最小防御动作（方案 B）：
- v0.77.0：`BeliefState.apply_snapshot()` 收口 DB 恢复路径 + 防御性自检 [6] 拦截直接 mutation

**Phase 6 (v0.78-0.82)** -- CTA/LCA 拆分 + Engine 补全（自然时机做完整 State Engine）：
- v0.78.0：CTA 4 层拆分 + StateEngine 类引入（commit / validate / snapshot / diff）
- v0.79.0：LCA 4 层拆分
- v0.80.0：Event Engine 雏形（LearningEvent 统一）
- v0.81.0：Policy Engine 第二个 Policy（Thompson Sampling）
- v0.82.0：Evidence Engine + Goal Ontology + Runtime API 公开
- ~~v0.73.0：Evaluation Engine 内置~~ (compute_h3_ece.py 外部脚本够用, 内置收益低)

**Phase 7+ (v0.83+)** -- 通用 Cognitive Runtime 推演：
- Twin -> Human Twin 抽象
- Learning Goal -> Goal 抽象
- 多 Domain 扩展（科研 / 职业 / 创意）

---

## 9. 重要判断：现在的代码"凌乱"吗?

### 9.1 Bisen 的"凌乱感"根因分析

Bisen 在 2026-08-03 反馈"开发进展到现在,我感觉是有些凌乱了"。根据本映射表分析：

**不是架构债,是文档债 + 阶段债**：
- 现有代码的 80% 接近 2.0（LinUCB / BeliefState / MIRT / BKT / 测试 / 抗幻觉）— **[v0.75.1]** "抗幻觉" = 互校机制 (Fast Calibration + Wide Coverage)
- 真正缺失的是抽象层（State Engine / Event Bus / Evidence Engine）
- "凌乱感"来自：
  1. **抽象缺失**：belief_engine.py 既是 Estimator 又是 Mutator,看起来"什么都做"
  2. **概念散落**：Event 概念在 5+ 处,没统一
  3. **文档滞后**：README/roadmap 在 7-31 才同步到 v0.68.0（之前停在 v0.53.1 长达 6-8 天）
  4. **版本号密集**：v0.54.0 -> v0.68.0 14 个版本,功能长出来快,抽象跟不上

### 9.2 不需要推倒重来

现有代码的方向是对的（State-first + 双 Agent + Bloom + 5D MIRT + LinUCB）。ChatGPT 分析给理论 9.5、架构 9.0 的评分也支持这个判断。

**真正需要的是沉淀,不是重构**：
- 把已有的 belief_engine.py / lca/orchestrator.py / dual_agent/orchestrator.py 沉淀成 State Engine / Policy Engine / Event Engine
- 不是推翻重写

### 9.3 何时启动 P2

**触发条件**（满足任一即可启动 P2）：
- v0.69.0 H3 验证通过（B4 方案有效）
- 加新功能时反复出现 CQRS 违反 / Event 散落 / Evidence 缺失

**不触发条件**：
- v0.69.0 H3 验证失败（需回滚或重设计）
- 现有架构能稳定支持新功能

### 9.4 [v0.77 2026-08-05] P2 评估结果

**触发条件状态**：
- ✅ H3 验证通过（v0.75.3 fingerprint 修复后 H3-c3 PASS, v0.76 跨学生验证 3/3 PASS）
- ❌ CQRS 违反没反复出现（LCA 路径已 read-only, 集中在 web/api/belief.py DB 恢复路径）

**评估结论**：暂缓完整 State Engine 重构, 改走方案 B (v0.77 加 apply_snapshot 收口 DB 恢复) + 方案 D (Phase 6 跟 CTA 4 层拆分一起做)。

**关键洞察**：v0.76 fingerprint 修复证明架构是健壮的 - BUG 只影响 theta 数值, 不影响架构选择。完整 State Engine 边际收益低 (LCA 已 read-only), Phase 6 是更自然的时机 (CTA 拆分本来就要重写 belief_engine.py)。

详见 [discussions/2026-08-05-v077-p2-state-engine-evaluation.md](../../discussions/2026-08-05-v077-p2-state-engine-evaluation.md)。

---

**创建日期**：2026-08-03
**维护者**：Bisen & Claude
**下次更新**：v0.77 apply_snapshot 实施时 / Phase 6 CTA 4 层拆分启动时
