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
| `ecos/cta/state_engine.py:StateEngine` (v0.80.0+v0.81.0) | 100% | 6/6 职责已实现: commit/validate/snapshot/diff (v0.80) + replay/simulate (v0.81.0-c). Hard block 保证 sole mutation invariant (v0.81.0-d) |
| `ecos/cta/belief_engine.py:BeliefEngine.update` | 80% | v0.80.0-c 走 4-layer facade (ObservationEngine + FeatureExtractor + InferenceEngine + BeliefUpdator). v0.81.0-b 加 log_event param. update() is 30-line pure orchestration |
| `ecos/cta/belief_engine.py:BeliefEngine.create_initial_state` | 80% | 已有冷启动 state init,接近 State Engine 的 create_snapshot |
| `ecos/cta/belief_state.py:StateSnapshot` | 60% | 已有快照概念,但不是 State Engine 管理的,而是 BeliefState 内嵌的 trajectory |
| `ecos/cta/belief_state.py:TrajectoryState` | 80% | 已有 state trajectory（500 个 snapshot 限长）,v0.81.0-c 起 StateEngine.replay 可从 events 重建 |
| `ecos/cta/belief_state.py:BeliefState.validate` (v0.80.0) | 100% | Schema + range 校验 (5D / bloom / C / TC / overall / theta shape) |
| `ecos/cta/belief_state.py:BeliefState.bump_version` (v0.80.0) | 100% | version = f'v1.0+{event_id}', last_updated = now() |
| `ecos/cta/belief_state.py:BeliefState.append_trajectory_snapshot` (v0.81.0-d) | 100% | DB restore 路径 trajectory snapshot append, allowlisted in check [8] |
| `ecos/cta/state_engine.py:StateEngine.diff` (v0.80.0) | 100% | 结构化 diff (changed_fields / old_values / new_values / delta_magnitudes) |
| `ecos/cta/state_engine.py:StateEngine.replay` (v0.81.0-c) | 100% | Apply events in chronological order to fresh state (pure, no DB coupling) |
| `ecos/cta/state_engine.py:StateEngine.simulate` (v0.81.0-c) | 100% | Fork+replay for counterfactual exploration (pure) |

**演进建议**：
- **v0.80.0** ✅: StateEngine + validate + snapshot + diff 落地 (4/6 职责). apply_snapshot 改 shim 委托 StateEngine.commit
- **v0.80.0-b** ✅: InferenceEngine (pure) + BeliefUpdator (sole mutator) 提取, `update()` 改 facade. 5 个 critical 不变量 test 验证 InferenceEngine.run() 不 mutate state. 4-layer 拆分完成度 30% -> 60%
- **v0.80.0-c** ✅: ObservationEngine + FeatureExtractor 提取, `__getattr__` forwarding 兼容 web/api/belief.py:189-191 直写. `update()` 改 pure orchestration (30 行). 4-layer 拆分完成度 60% -> 80%
- **v0.80.0 final** ✅: 防御性自检 [8] AST 扫描 direct state mutation (soft warning, v0.81 hard block). +177 tests (431 -> 554 pytest). H3-c4 全 3 学生 PASS
- **v0.80.0-d 决策**: InferenceEngine 不 sub-split (365 行含 110 行 dataclass, 实际逻辑 185 行, 5 子组件已分文件)
- **v0.81.0-a** ✅: EventLog + LearningEvent + db schema (event_log table + idx_event_log_student). 32 tests
- **v0.81.0-b** ✅: BeliefUpdator + BeliefEngine wire EventLog (sole event logging site). 13 tests. log_event param
- **v0.81.0-c** ✅: StateEngine.replay/simulate APIs (pure). 14 tests + 3 H3-c4 canary (replay path == inline path)
- **v0.81.0-d** ✅: TODO mutations 迁移完成 (web/api/belief.py + ecos_session.py). check [8] hard block (exit 1). LINE_ALLOWLIST 8 -> 1
- **v0.81.0 final** ✅: 6/6 StateEngine 职责, 616 tests (554 -> 616 +62), State Engine 抽象 100%
- **v0.82.0** ✅ (2026-08-10): LCA 4-layer split (Planner + ExperimentDesigner + Evaluator + PolicyLearner) + LCAEngine facade finalization (632 → 491 行, -22%). 4 sub-commits (a/b/c/d). 57 tests (16+13+13+15). 防御性自检 [8] 仍 hard block (LCAEngine 不引入新 mutation site)
- **v0.83.0** ✅ (2026-08-10): Evidence Engine + Runtime API. 4 sub-commits (a/b/c/d). 63 tests (15+14+16+18). 673 → 736 tests (+9.4%). 防御性自检 [8] 仍 hard block (Runtime API 0 新 mutation site, add_evidence 扩展 allowlist)

### 1.2 Event Engine

**2.0 定义**：统一 Learning Event 的发布 / 消费 / 事件流管理,支撑 Replay / Audit / Simulation / Offline Evaluation。

| 现有代码 | 接近度 | 说明 |
|---|---|---|
| `ecos/cta/event_log.py:LearningEvent` (v0.81.0-a) | 100% | dataclass: event_id/student_id/timestamp/source/event_type/payload. Forward-compat: v0.82+ 加 event_type="calibration" 不破坏 schema |
| `ecos/cta/event_log.py:EventLog` (v0.81.0-a) | 100% | dual-mode (in_memory + sqlite). log_event/load_events/count_events API. INSERT OR IGNORE dedup by event_id PK |
| `ecos/persistence/db.py:event_log table` (v0.81.0-a) | 100% | sqlite table + idx_event_log_student ON (student_id, timestamp). Mirror calibration_log precedent |
| `ecos/cta/belief_updater.py:BeliefUpdator.apply` (v0.81.0-b) | 100% | Sole event logging site (when event_log attached AND log_event=True). Mirrors "sole mutation site" principle |
| `ecos/cta/belief_engine.py:Observation.to_dict/from_dict` (v0.81.0-b) | 100% | Serialization for LearningEvent payload. BloomLevel -> name, datetime -> ISO |
| `ecos/cta/state_engine.py:StateEngine.replay` (v0.81.0-c) | 100% | Apply events in chronological order to fresh state. Pure: no DB, no logging |
| `ecos/cta/state_engine.py:StateEngine.simulate` (v0.81.0-c) | 100% | Fork+replay for counterfactual. Pure |
| `ecos/cta/belief_engine.py:BeliefEngine.replay` (v0.81.0-c) | 100% | Facade over StateEngine.replay, passes log_event=False |
| `ecos/cta/belief_engine.py:BeliefEngine.simulate` (v0.81.0-c) | 100% | Facade over StateEngine.simulate |
| `ecos/cta/belief_engine.py:Observation` | 60% | v0.81.0-b 加 to_dict/from_dict. 仍是 dataclass, 不是 Event Bus 消息 |
| `ecos/dual_agent/protocol/messages.py:CalibrationMessage` | 30% | 已有 Message 类型枚举, v0.82 统一到 LearningEvent (event_type="calibration") |
| `ecos/dual_agent/protocol/messages.py:MessageType` | 50% | 已有 10 种 MessageType, 接近 Event 类型分类 |
| `web/api/belief.py` _response_history | 40% | 隐式 Event 流（按时间序的答题记录）, v0.82+ 迁移到 EventLog |
| `web/api/dual_agent.py` calibration_log 表 | 30% | 隐式 Event 流（dual_agent 互校历史）, v0.82+ 统一到 event_log |
| **缺失：Event Bus** | 0% | 没有 pub/sub 机制 (deferred to v0.82+, YAGNI for now) |
| **缺失：EventLog retention policy** | 0% | event_log table 无限增长, v0.82+ 加 auto-prune |

**演进建议**：
- **v0.81.0** ✅: EventLog + LearningEvent + Replay/Simulation APIs (Option D direction, defer LearningEvent unification + Event Bus to v0.82+)
- **v0.82.0** (2026-08-10): LCA 4-layer split 优先级更高 (Kernel-first 战略), 抢占 v0.82 资源. LearningEvent unification / Event Bus / EventLog retention 推迟到 v0.82.x 后续 commit (不阻塞 LCA split)
- **v0.82.x**: 统一 `Observation` + `CalibrationMessage` 为 `LearningEvent` (event_type 扩展); Event Bus (in-process pub/sub); EventLog retention policy; 迁移已有 replay scripts (v078_h3c4_*, v0753_*) 到 StateEngine.replay (cleanup, not correctness)

### 1.3 Policy Engine

**2.0 定义**：维护可学习 / 可评估 / 可演化的策略库（LinUCB / Thompson / POMDP / LLM-as-Policy）。

| 现有代码 | 接近度 | 说明 |
|---|---|---|
| `ecos/lca/l4_optimization/linucb.py:LinUCB` | 80% | LinUCB 已有,接口清晰（select_arm / update） |
| `ecos/lca/l4_optimization/policy_learner.py:LCAPolicyLearner` | 80% | LinUCB 包装 + 上下文构建 + arm 候选映射 |
| `ecos/lca/l4_optimization/thompson.py:ThompsonSampling` (v0.86.0-c) | 100% | Beta-Bernoulli Bandit, 接口同构 LinUCB (select_arm/update/dump_state/load_state) |
| `ecos/lca/l4_optimization/pomdp.py:POMDPPolicy` (v0.90.0-d) | 100% | 4 状态 POMDP (Engaged/Frustrated/Bored/Confused) + 依赖型 T(s'|s,a) + learned R(s,a) Beta posterior + PBVI 默认 (α-vector 完整算法 + 收敛 + reachable belief points + lazy load + 持久化) + learned T/R online (use_learned_t_r=True 默认 + min_samples=5 冷启动) |
| `ecos/lca/orchestrator.py:LCAEngine._estimate_gain` | 60% | 简化估算策略（scale × (1-K) × scaffolding）,不是 LinUCB 但属于 Policy 库的一员 |
| `ecos/dual_agent/orchestrator.py:_compute_dual_agent_confidence` (v0.69.0) | 50% | LinUCB θ@x 预测,属于 Policy Engine 的"预测接口",但不是独立 Engine |
| **缺失：LLM-as-Policy** | 0% | LLM 只做 rationale / critic,不做策略推荐 |
| `ecos/evaluation/policy_ab_test.py:PolicyABTest` (v0.90.0-d) | 100% | v0.83.0-c 占位 + v0.86.0-d 真 A/B Test + v0.87.0-d 4-policy 支持 (LinUCB/linucb_baseline/Thompson/POMDP+PBVI+learned T/R 任意 2-way, v0.89.0-d 工厂 use_pbvi=True + v0.90.0-d 工厂 use_learned_t_r=True + min_samples=5) |

**演进建议**：
- **v0.76.0**：引入 Thompson Sampling（Policy Engine 第二个 Policy）✅ 2026-08-11 v0.86.0-c 落地 (Beta-Bernoulli Bandit, LinUCB 同接口, policy_type="thompson" 切换)
- **v0.77.0**：加 Policy 评估框架（offline evaluation + AB test）✅ 2026-08-11 v0.86.0-d 落地 (PolicyABTest 真 A/B Test, replay events, 5% winner 阈值)
- **v0.87.0+**：POMDP Policy (部分可观测 MDP, 推迟 v0.86 因为单 commit 太重)
- **Phase 7+**：实验 LLM-as-Policy

### 1.4 Evidence Engine

**2.0 定义**：统一管理 Evidence 的来源 / 可信度 / 时间 / 关联 Goal / 关联 Belief。所有 Belief 都必须由 Evidence 支持。

| 现有代码 | 接近度 | 说明 |
|---|---|---|
| `web/api/dual_agent.py` calibration_log 表 | 100% (v0.83.0-a) | 通过 EvidenceEngine.query_by_source(CALIBRATION_LOG) 统一访问 |
| `web/api/belief.py` _response_history | 100% (v0.83.0-a) | 通过 EvidenceEngine.query_by_source(RESPONSE_HISTORY) 统一访问 |
| `ecos/cta/belief_state.py:BeliefState.evidence_predictions` | 100% (v0.83.0-b) | BeliefState.add_evidence / evidence_for / evidence_summary 替代 dict 占位 |
| `ecos/cta/l2_mirt.py` partial credit 评分 | 100% (v0.83.0-a) | PARTIAL_CREDIT 是 EvidenceSource 6 种之一, payload 含 score + mirt_theta_delta |
| `ecos/cta/llm_critic/` | 100% (v0.83.0-a) | LLM_CRITIC / MISCONCEPTION 是 EvidenceSource 6 种, payload 含 source_subtype 字段 |
| `ecos/cta/event_log.py:LearningEvent` (v0.81) | 100% (v0.83.0-a) | EVENT_LOG 是 EvidenceSource 第 6 种, query_by_student 跨 3 表合并 |
| `ecos/evidence/evidence.py:Evidence` (v0.83.0-a) | 100% | 6 字段 (evidence_id / source / student_id / timestamp / payload / confidence) + 4 派生 |
| `ecos/evidence/evidence_engine.py:EvidenceEngine` (v0.83.0-a) | 100% | add / query_by_id / query_by_student / query_by_source / query_by_goal (stub) / attach_to_belief (stub) |
| `ecos/cta/belief_updater.py:BeliefUpdator._register_evidence` (v0.83.0-b) | 100% | apply() 注入 evidence_engine 走 Evidence.add 路径, 否则 fallback 到 evidence_ids.append |
| `scripts/check_no_direct_state_mutation.py` | 100% (v0.83.0-b) | FUNC_ALLOWLIST += add_evidence, 防御性自检 [8] 仍 hard block |

**演进建议**：
- **v0.77.0**：引入 Evidence Engine（统一 Evidence schema + 关联管理）✅ 2026-08-10 在 v0.83.0-a/b 落地
- **v0.78.0**：把 calibration_log + response_history + llm_critic_results 统一为 Evidence 流 ✅ 2026-08-10 在 v0.83.0-a 落地

### 1.5 Evaluation Engine

**2.0 定义**：回答"Twin 为何提高 / 哪个 Policy 最好 / 哪个 Goal 完成"。

| 现有代码 | 接近度 | 说明 |
|---|---|---|
| `scripts/compute_h3_ece.py` | 100% (v0.83.0-c 兼容) | H3 验证脚本保留, EvaluationEngine 复用 ECE metric |
| `ecos/lca/l4_optimization/attribution.py:LCAAttribution` | 100% (v0.83.0-c 兼容) | LCAAttribution 是 v0.82 Evaluator 子组件 |
| `ecos/dual_agent/orchestrator.py:_consecutive_ineffective` | 100% (v0.83.0-c 兼容) | 计数逻辑保留, EvaluationEngine 不强制迁 |
| `ecos/metrics/ece.py` | 100% (v0.83.0-c 复用) | expected_calibration_error 在 evaluate(metric="ece") 路径 |
| `ecos/evaluation/twin_attribution.py:TwinAttribution` (v0.83.0-c) | 100% | Twin 变化归因 (5D mastery + Bloom 6 层 + overall_confidence state diff) |
| `ecos/evaluation/policy_ab_test.py:PolicyABTest` (v0.83.0-c) | 100% | Policy 对比框架 (LinUCB vs LinUCB_baseline, 真 A/B 留 v0.83.x) |
| `ecos/evaluation/goal_completion.py:GoalCompletion` (v0.83.0-c) | 100% | Goal 完成判定 (K.mastery>=X / Bloom.L<N>>=X / TC.<id>.pass) |
| `ecos/evaluation/evaluation_engine.py:EvaluationEngine` (v0.83.0-c) | 100% | facade 3 evaluator + 3 主入口 (attribute_state_change / compare_policies / check_goal_completion) |

**演进建议**：
- **v0.73.0**：把 `compute_h3_ece.py` 内置为 Runtime Evaluation Engine ✅ 2026-08-10 v0.83.0-c 落地
- **v0.74.0**：加 Twin 变化归因（基于 Event 流 + State Diff）✅ 2026-08-10 v0.83.0-c 落地 (TwinAttribution)
- **v0.77.0**：加 Policy 对比框架 ✅ 2026-08-10 v0.83.0-c 落地 (PolicyABTest, 真 A/B 留 v0.83.x 等 Thompson Sampling)

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
| `BeliefState.current_goals` (v0.86.0-a) | 100% | Goal Ontology 关联 (Capability / Objective / Metric / Evidence) |
| `BeliefState.motivation` (v0.87.0-a) | 100% | Motivation Profile 关联 (4 维时序 frustration/engagement/confidence/recent_trajectory, X 维度保留向后兼容) |
| `ecos/twin/consistency.py:TwinConsistencyChecker` (v0.86.0-b) | 100% | Twin 一致性校验 (5 规则: K+Bloom / TC+K / Goal+confidence / Bloom+C / current_goals+evidence) |
| `ecos/lca/evaluator.py:Evaluator.motivation_reward_adjustment` (v0.87.0-b) | 100% | Motivation reward factor (0.7/0.8/1.0/1.3) |

**演进建议**：
- **v0.71.0**：把 `BeliefState` 重命名为 `StudentTwin`（语义清晰, 推迟 v0.86 没做 7 字段重命名风险大)
- **v0.72.0**：拆 Motivation Profile 独立（X 维度从 5D 抽出）✅ 2026-08-11 v0.87.0-a 落地 (MotivationProfile + 4 维时序, X 字段保留向后兼容)
- **v0.73.0**：加 Twin 一致性校验 ✅ 2026-08-11 v0.86.0-b 落地 (TwinConsistencyChecker + 5 规则 + Runtime.plan 触发)

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
| `ecos/goal/goal.py:Goal` (v0.86.0-a) | 100% | Goal 完整 4 字段: Capability / Objective + bloom_level / Metric (dimension + threshold) / Evidence (evidence_ids) |
| `ecos/goal/goal.py:Capability` (v0.86.0-a) | 100% | Capability dataclass (name / description / domain, frozen) |
| `ecos/goal/ontology.py:GoalOntology` (v0.86.0-a) | 100% | factory + registry (register/get/query_by_domain/from_capability) |
| `ecos/goal/registry.py:DEFAULT_CAPABILITIES_LIST` (v0.86.0-d) | 100% | 5 Python Capability (variables / loops / functions / conditionals / strings) |
| `ecos/cta/belief_state.py:BeliefState.current_goals` (v0.86.0-a) | 100% | Goal Ontology 集成 (to_dict / from_dict / append_goal / remove_goal) |
| `ecos/evaluation/goal_completion.py:GoalCompletion.check_goal` (v0.86.0-a) | 100% | accept Goal 对象 (Union[str, Goal] dispatch) |

**演进建议**：
- **Phase 6+**：引入 Goal Ontology（Capability -> Objective -> Metric -> Evidence）✅ 2026-08-11 v0.86.0-a 落地 (Goal + Capability + GoalOntology + current_goals + GoalCompletion.check_goal)
- **v0.86.0-d**：集成 Goal-aware Runtime.plan + DEFAULT_CAPABILITY_REGISTRY ✅ 2026-08-11 v0.86.0-d 落地 (5 Python 默认 Capability)
- **Phase 7+**：扩展到非教育 Domain（如科研 / 职业, v0.88+ 推迟）

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

## 3.1 Multi-Domain 抽象映射 (v0.88.0-a)

**2.0 定义**: Domain-agnostic Kernel 1 套 + Domain-specific Extension N 套. Kernel (LinUCB / Thompson / POMDP / Evidence / Runtime / StateEngine) 完全 Domain-agnostic; Domain 通过 profile_extensions 注入 BeliefState.

| 现有代码 | 接近度 | 说明 |
|---|---|---|
| `ecos/domain/base.py:Domain` ABC (v0.88.0-a) | 100% | 4 abstract property: name / description / capability_ontology / profile_extensions |
| `ecos/domain/base.py:DomainRegistry` singleton (v0.88.0-a) | 100% | register / get / list_names / has / clear / reset (单进程 1 份, 测试可隔离) |
| `ecos/domain/education.py:EducationDomain` (v0.88.0-a) | 100% | K12 默认 Domain. 5 Python default capability (复用 v0.86.0-d DEFAULT_CAPABILITIES_LIST) + grade_levels / learning_standards extension |
| `ecos/domain/science.py:ScienceDomain` (v0.88.0-a) | 100% | 科研 Domain. 3 capability (hypothesis/experiment/analysis) + research_methods / domain_categories extension |
| `ecos/domain/career.py:CareerDomain` (v0.88.0-a) | 100% | 职业 Domain. 3 capability (skill/portfolio/certification) + vocational_tracks / certification_levels extension |
| `ecos/domain/__init__.py:register_default_domains` (v0.88.0-a) | 100% | 注册 3 个 Domain 到 registry (idempotent, 同 name 覆盖) |
| **缺失: BeliefState domain_extension** | 0% | v0.88.0-b 加 Dict[str, Any] 字段, 渐进迁移 (per design doc §3) |
| **缺失: Runtime.plan_domain_aware** | 0% | v0.88.0-b 新 API (跟 plan_motivation_aware 模式一致) |
| **缺失: ExperimentDesigner domain-aware** | 0% | v0.88.0-b: education 走 K12 logic, science 走 INQUIRY 主导, career 走 PRACTICE 主导 |
| **缺失: Evaluator.domain_reward_adjustment** | 0% | v0.88.0-b: 根据 domain 调整 gain (跟 motivation_reward_adjustment 模式一致) |

**演进建议**:
- **v0.88.0-a** ✅ (2026-08-11): Domain 抽象层奠基. NEW `ecos/domain/{__init__,base,education,science,career}.py` 5 文件. Multi-Domain §3 0% → 80% (Domain 抽象层 100%, 集成留 v0.88.0-b)
- **v0.88.0-b** ✅ (2026-08-11): Multi-Domain 集成 (DomainExtension + Runtime + LCA). 4 个集成点全完成: BeliefState.domain_extension + Runtime.plan_domain_aware + ExperimentDesigner domain-aware + Evaluator.domain_reward_adjustment. 26 新增 tests (pytest 985 → 1011, +2.7%). 防御性自检 [8] 仍 hard block (set_domain_extension 加入 allowlist). H3-c4 + v0.81 replay canary 全 PASS. Multi-Domain §3 80% → 95%.
- **v0.88.0-c** ✅ (2026-08-11): POMDP 完整 (依赖型 T+R). 3D transition (n_states x n_states x n_arms) + R(s, a) 固定 init + bayes_update(action, observation) + schema_version 校验. 16 新增 tests (pytest 1011 → 1027, +1.6%). 防御性自检 [8] 仍 hard block. POMDP Policy §1.3 80% → 100%. 老 snapshot 不兼容 (per design §4.3, schema_version="0.88.0-c" 校验).
- **v0.88.0-d** ✅ (2026-08-11): POMDP 集成 Runtime + 真 A/B 3-way 升级. LCAEngine.select_intervention 前消费 observation (bayes_update(action, obs)) + LCAPolicyLearner.set_observation API + PolicyABTest 自动升级. 17 新增 tests (pytest 1027 → 1044, +1.7%). H3-c4 + v0.81 replay canary 全 PASS. 防御性自检 [8] 仍 hard block. POMDP Runtime 集成 + Multi-Domain 100%.
- **v0.88.0 final** ✅ (2026-08-11): 文档同步收口. README.md (badge + 当前状态 + Kernel 深化进度表 + 累计产出更新) + CLAUDE.md (当前阶段追加 v0.86/v0.87/v0.88 摘要 + 防御性自检 [8] 追加 mutation 状态 + pytest 测试清单 836 → 1044) + memory 新增 `project-v088-completion-state.md`. 缺失清单 0 项剩.
- **v0.89.0-a** ✅ (2026-08-12): PBVI 雏形 + α-vector 数据结构. NEW `ecos/lca/l4_optimization/pomdp_solver.py` (AlphaVector frozen dataclass + PBVI class 单步 backup + alpha_value/best_action 雏形). 19 新增 tests (含 parametrize, pytest 1044 → 1063). 防御性自检 [8] 仍 hard block. POMDP Policy §1.3 PBVI 雏形落地.
- **v0.89.0-b** ✅ (2026-08-12): PBVI 完整算法 + belief point sampling. update_alpha_vectors 收敛检测 + PBVI.solve 主算法 (iterative backup) + reachable_belief_points (随机采样) + uniform_belief_points (Dirichlet 均匀). 12 新增 tests (pytest 1063 → 1075). 经典 PBVI (Sondik 1971 简化): α-vector in state space, V(b) = α·b. 防御性自检 [8] 仍 hard block.
- **v0.89.0-c** ✅ (2026-08-12): POMDPPolicy 集成 PBVI. use_pbvi=True 默认 + 懒加载 reachable belief points + solve_pbvi() 显式入口 + dump_state/load_state 持久化 (use_pbvi / pbvi_config / solver_state). schema_version 0.89.0-c, 老 snapshot 0.88.0-c / 0.87.0-c raise ValueError. 10 新增 tests (pytest 1075 → 1085).
- **v0.89.0-d** ✅ (2026-08-12): Runtime + PolicyABTest 集成 PBVI. LCAPolicyLearner / LCAEngine.select_intervention POMDP 路径显式 solve_pbvi (双层防御) + PolicyABTest 工厂 use_pbvi=True + solve_pbvi 幂等 (α 缓存命中跳过) + PolicyLearnerConfig.pomdp_use_pbvi 透传. Runtime plan 签名稳定, opt-out kwargs 留 v0.90+. 11 新增 tests (pytest 1085 → 1096). 防御性自检 [8] 仍 hard block.
- **v0.90.0-a** ✅ (2026-08-12): T/R posterior 数据结构 + 增量 update. NEW `ecos/lca/l4_optimization/pomdp_learner.py` (TransitionPosterior Dirichlet 多项式共轭 + RewardPosterior Beta 共轭 + posterior mean MAP + 越界 raise + total_evidence 接口). 12 新增 tests (pytest 1096 → 1108). POMDP Policy §1.3 T/R 学习数据通路 0% → 起步. 接口同构 LinUCB/Thompson/POMDP 维持. 防御性自检 [8] 仍 hard block (posterior dataclass self mutation 不触及 BeliefState).
- **v0.90.0-b** ✅ (2026-08-12): posterior 注入 POMDPPolicy + 持久化 + schema_version 升级 0.89.0-c → 0.90.0. POMDPPolicy.set_transition_posterior / set_reward_posterior 注入接口 + _learned_t_r_posterior_mean 派生 T/R posterior mean + dump_state 加 transition_count / reward_alpha / reward_beta 3 字段 + load_state 校验 schema_version (老 snapshot raise). 13 新增 tests (pytest 1108 → 1121). 防御性自检 [5] schema_version 校验生效.
- **v0.90.0-c** ✅ (2026-08-12): POMDPPolicy 集成 update_t_r + PBVI 用 posterior mean. update(arm, ctx, reward, observation=None) 扩展 obs 参数 + _update_t_r lazy init posterior (越界 skip, 跟 bayes_update 一致) + _resolve_t_r 共享路径 (PBVI + QMDP fallback 都用 posterior mean) + use_learned_t_r=True 默认 + solve_pbvi 不直接 mutation self.transition / self.reward (走 transient T/R 输入参数, 防御性自检 [8] 仍 hard block). 12 新增 tests (pytest 1121 → 1133). POMDP Policy §1.3 30% → 70% (算法闭环).
- **v0.90.0-d** ✅ (2026-08-12): Runtime + PolicyABTest 集成 learned T/R + 冷启动. LCAEngine.update 透传 pomdp_observation 到 LCAPolicyLearner.update(obs) + PolicyLearnerConfig.pomdp_use_learned_t_r kwargs 注入 + PolicyABTest._create_fresh_bandit POMDP 工厂 use_learned_t_r=True + min_samples=5 + POMDPPolicy._resolve_t_r 冷启动保护 (evidence < 5 用 init, ≥ 5 切 learned) + RewardPosterior.total_evidence 公式修正 (2 * alpha0 per cell). 10 新增 tests (pytest 1133 → 1143). 3-way A/B (linucb / thompson / pomdp+PBVI+learned T/R) 维持. 防御性自检 [8] 仍 hard block (LCAEngine._last_observation 是 instance dict, 不在 state 上).
- **v0.91.0-a** ✅ (2026-08-12): CognitiveTwinAgent 数据结构 + HumanFeedbackEntry (Phase 7+ 抽象推演 #4 sub-version a). NEW `ecos/cta/cognitive_twin.py` (HumanFeedbackEntry frozen dataclass 4 event_type: hint_requested/idle_detected/goal_changed/reflection_completed + HumanFeedbackTrajectory cap 500 pattern 跟 TrajectoryState 同 + CognitiveTwinAgent 3-tuple (belief_state/trajectory/human_feedback) + action_history 占位留 v0.92+ + schema_version="0.91.0"). scripts/check_no_direct_state_mutation.py FUNC_ALLOWLIST += CognitiveTwinAgent.append_human_feedback (跟 append_trajectory_snapshot 同模式). 12 新增 tests (pytest 1143 → 1155). Plugin SDK 4 frontend stub endpoint (hint/idle/goal_change/reflection) Human-in-loop 信号源数据结构闭环. 防御性自检 [8] 仍 hard block (append_human_feedback 收口到 allowlist).
- **v0.91.0-b** ✅ (2026-08-12): Runtime + Plugin SDK 4 subscriber (Phase 7+ 抽象推演 #4 sub-version b). LCAEngine _cognitive_twin dict (per-student pattern 跟 _last_intervention / _last_observation / _cognitive_twin_pending 一致) + select_intervention cognitive_twin kwarg + append_human_feedback mutation 走 allowlist. NEW Runtime.plan_human_feedback_aware (6 plan API upper limit). PluginRuntime.start() 加 4 subscriber (hint/idle/goal/reflection) → subscription_count 3 → 7. POMDPPolicy SCHEMA_VERSION "0.90.0" → "0.91.0" (老 snapshot raise per 防御性自检 [5]). 15 新增 tests (pytest 1155 → 1170). Plugin SDK 4 endpoint 全接通 Human Twin, 不再是半成品. 防御性自检 [8] 仍 hard block (LCAEngine._cognitive_twin dict mutation 收口到 append_human_feedback).
- **v0.91.0-c** ✅ (2026-08-12): LCA 4 layer 接入 Human feedback (Phase 7+ 抽象推演 #4 sub-version c). ExperimentDesigner.cognitive_twin kwarg + _human_feedback_itype_override (hint>5→EXPLANATORY / idle>3→INQUIRY / reflection>3→PRACTICE / goal>1→PRACTICE, 优先级 hint>idle>reflection>goal). Evaluator.human_feedback_reward_adjustment (hint>5→0.8 / idle>3→0.9 / reflection>3→1.2 / goal>1→1.1, default→1.0). LCAEngine.select_intervention kwargs 透传 cognitive_twin → designer + evaluator. 21 新增 tests (pytest 1170 → 1191). H3-c4 canary 维持 (cognitive_twin=None 行为 == v0.90 baseline). 多 multiplicative factor chain: base × motivation × domain × human_feedback.
- **v0.91.0-d** ✅ (2026-08-12): 冷启动 + 持久化 + canary (Phase 7+ 抽象推演 #4 sub-version d). CognitiveTwinAgent.dump_state + load_state (schema_version="0.91.0" 校验, 老 raise per 防御性自检 [5]). LCAEngine.dump_state + load_state 加 cognitive_twin 字段 + bind_cognitive_twin helper (load_state 暂存 _cognitive_twin_pending, bind 时 materialize). persistence/db.py 加 cognitive_twin TEXT 列 (含 ALTER TABLE 增量迁移) + save_student_state cognitive_twin_json kwarg. 8 新增 tests (pytest 1191 → 1199). v0.81 replay canary 维持 (cognitive_twin 不通过 StateEngine.replay 重建, 走 LCA 路径).
- **v0.91.0-e** ✅ (2026-08-12): Plugin SDK 文档化 (Phase 7+ 抽象推演 #4 sub-version e, doctest only). NEW `docs/plugin_sdk.md` (8 section: Plugin 原则 / 7 Subscriber 契约 / LCAEngine.append_human_feedback / 防御性自检 / Runtime 6 plan API / 5 sub-commit 演进日志 / 相关文档 / 调用样例) + NEW `examples/plugin_sample_human_feedback.py` (5 use case: teacher_reflection / parent_goal / hint_fatigue / idle_reminder / deep_reflection) + NEW `tests/test_plugin_sdk_docs.py` (4 doctest: 8 section / link 存在 / use case 暴露 / smoke PASS). 防御性自检 [2] test_version_consistency regex 扩展允许 -e sub-version 后缀 (Phase 7+ 抽象推演第 5 sub-commit). 4 新增 tests (pytest 1199 → 1203, doctest only).
- **v0.92.0-a** ✅ (2026-08-12): HumanTwinSnapshot ActionHistory 占位兑现 — ActionEntry/ActionHistory 数据结构 (Phase 7+ 抽象推演 #5 sub-version a). NEW `ecos/cta/cognitive_twin.py` ActionEntry (frozen dataclass, 5 action_type: intervention_selected/dual_agent_calibrated/reward_recorded/policy_updated/goal_changed + intervention_id/reward/metadata/source/schema_version + __post_init__ 防御性校验) + ActionHistory (cap 500 pattern 跟 HumanFeedbackTrajectory 完全 parallel + append/last_n/count_by_type/to_dict/from_dict). CognitiveTwinAgent 3-tuple → 4-tuple (action_history: Optional[Dict] = None → ActionHistory default_factory) + SCHEMA_VERSION "0.91.0" → "0.92.0" + NEW append_action_history allowlisted mutation (跟 append_human_feedback 完全 parallel 模式). scripts/check_no_direct_state_mutation.py FUNC_ALLOWLIST += CognitiveTwinAgent.append_action_history. 12 新增 tests (pytest 1203 → 1215). v0.91 留 action_history 占位彻底兑现. 防御性自检 [8] 仍 hard block (append_action_history 收口到 allowlist).
- **v0.92.0-b** ✅ (2026-08-12): Runtime + LCAEngine append_action_history 接入 (Phase 7+ 抽象推演 #5 sub-version b). LCAEngine.append_action_history method (parallel to append_human_feedback, lazy init CognitiveTwinAgent from state) + select_intervention action_history kwarg + Step 7 自动记录 intervention_selected ActionEntry + update() reward 反馈路径自动记录 reward_recorded ActionEntry. NEW Runtime.plan_action_aware (第 7 plan API, 在 plan_human_feedback_aware 委托链尾). POMDPPolicy SCHEMA_VERSION "0.91.0" → "0.92.0" (老 snapshot raise per 防御性自检 [5]). 15 新增 tests (pytest 1215 → 1230). Plugin SDK 7 subscribers 维持 (不加新 subscriber — action_history 是 LCA 内部自动记录, 不是 Human-in-loop 信号源). 防御性自检 [8] 仍 hard block (LCAEngine._cognitive_twin dict mutation 收口到 append_action_history).
- **v0.92.0-c** ✅ (2026-08-12): LCA 4 layer 接入 ActionHistory (Phase 7+ 抽象推演 #5 sub-version c). ExperimentDesigner.action_history kwarg + _action_history_itype_override (5 case priority: reward_low / type_diversity / dual_agent / policy_cold / goal_changed). Evaluator.action_history_reward_adjustment (reward_recorded 平均<0.5→0.85 / >0.7→1.15 / dual_agent>0.5 半→1.05, default→1.0). LCAEngine.select_intervention kwargs 透传 action_history → designer + evaluator. 21 新增 tests (pytest 1230 → 1251). H3-c4 canary 维持 (action_history=None 行为 == v0.91 baseline). 多 multiplicative factor chain 升级: base × motivation × domain × human_feedback × action_history (4 因素 → 5 因素).
- **v0.92.0-d** ✅ (2026-08-12): 冷启动 + 持久化 + canary (Phase 7+ 抽象推演 #5 sub-version d). CognitiveTwinAgent 4-tuple dump_state/load_state round-trip (action_history 字段完整保留 + 老 action_history schema raise per 防御性自检 [5]). LCAEngine.dump_state/load_state cognitive_twin 字段含 4-tuple + 老 v0.91 snapshot (schema_version="0.91.0" / action_history 字段缺) graceful skip + warning (per 防御性自检 [1]). 8 新增 tests (pytest 1251 → 1259). v0.81 replay canary 维持 (action_history 不通过 StateEngine.replay 重建, 走 LCAEngine.append_action_history 路径). persistence/db.py cognitive_twin TEXT 列自动含 action_history 字段 (无 schema 改动). 累计 Kernel 深化 10 版本 (v0.83 → v0.92), pytest 736 → 1259 (+523, +71.1%).
- **v0.93.0-a** ✅ (2026-08-12): POMDPDiagnostic 数据结构 + POMDPPolicy diagnostic API 雏形 (Phase 7+ 抽象推演 #6 sub-version a). NEW `ecos/lca/l4_optimization/pomdp_diagnostic.py` (TransitionPosteriorSnapshot / RewardPosteriorSnapshot / POMDPDiagnostic frozen dataclass 三件套 + coverage + most_likely_state + schema_version="0.93.0"). NEW POMDPPolicy.get_diagnostic / get_transition_heatmap / get_reward_curves. POMDP Policy §1.3 70% → 100% (T/R 后验可视化 surface 落地). 18 新增 tests (pytest 1259 → 1277).
- **v0.93.0-b** ✅ (2026-08-12): Runtime + LCAEngine + Plugin SDK 集成 diagnostic (Phase 7+ 抽象推演 #6 sub-version b). NEW Runtime.diagnose_pomdp (第 8 plan/query API, 委托 LCAEngine.get_pomdp_diagnostic) + NEW LCAEngine._pomdp_diagnostic: Dict[str, POMDPDiagnostic] (per-student dict, 跟 _cognitive_twin 完全 parallel). LCAEngine.select_intervention POMDP path auto-collect diagnostic after Step 8. NEW PluginRuntime 第 8 subscriber pomdp_diagnostic_updated → _handle_pomdp_diagnostic_updated → Runtime.diagnose_pomdp (subscription_count 7 → 8). 13 新增 tests (pytest 1277 → 1290). POMDP diagnostic 全栈 production-ready.
- **v0.93.0-c** ✅ (2026-08-12): 演化追踪 (timed snapshots N=50/K=10) + 持久化 (Phase 7+ 抽象推演 #6 sub-version c). POMDPPolicy._evolution: List[POMDPDiagnostic] cap K=10 FIFO + _update_count + _next_snapshot_at=50 + _take_evolution_snapshot 触发 + get_evolution / evolution_snapshot_count getter. POMDPPolicy SCHEMA_VERSION "0.92.0" → "0.93.0" (老 0.92 snapshot raise per 防御性自检 [5]). dump_state ADD evolution/update_count/next_snapshot_at 3 字段 + load_state evolution graceful restore. LCAEngine.dump_state cognitive_twin ADD pomdp_diagnostic 子字段 (Twin 第 5 维度). LCAStore.lca_state ADD pomdp_diagnostic TEXT 列 (CLAUDE.md 防御性自检 [5] 9 字段对齐) + ALTER TABLE IF NOT EXISTS 老 DB 兼容 migration. 10 新增 tests (pytest 1290 → 1300).
- **v0.93.0-d** ✅ (2026-08-12): H3-c4 canary + 老 v0.92 snapshot graceful skip + docs/pomdp_diagnostic.md + examples (Phase 7+ 抽象推演 #6 sub-version d). NEW `docs/pomdp_diagnostic.md` (~250 行, 8 section: Diagnostic 原则 / POMDPDiagnostic 字段 / Runtime.diagnose_pomdp API / LCAEngine.get_pomdp_diagnostic API / Plugin SDK 第 8 subscriber / 演化追踪 / 防御性自检 / 调用样例). NEW `examples/plugin_sample_pomdp_diagnostic.py` (~180 行, 3 use case: teacher_progress_review / parent_engagement_dashboard / student_self_reflection). H3-c4 canary 维持 (POMDP diagnostic 走 LCA 路径, BeliefState 不受影响). v0.81 replay canary 维持 (POMDP diagnostic 不通过 StateEngine.replay 重建). 老 v0.92 LCAEngine snapshot graceful skip (pomdp_diagnostic 字段缺 / 老 schema_version). 8 新增 tests (pytest 1300 → 1308). 累计 Kernel 深化 11 版本 (v0.83 → v0.93), pytest 736 → 1308 (+572, +77.7%). POMDP Diagnostic 100% production-ready.
- **v0.94.0-a** ✅ (2026-08-13): Plugin ABC + PluginMetadata frozen dataclass (Phase 7+ 抽象推演 #7 sub-version a). NEW `ecos/plugins/{__init__,base}.py` (~150 行). Plugin(ABC) 4 abstract method (on_event / get_subscribed_topics / enable / disable). PluginMetadata(frozen=True) dataclass 跟 Domain ABC v0.88.0-a + Capability v0.86.0-a + POMDPDiagnostic v0.93.0-a 完全 parallel pattern (name/version/description/dependencies/subscribed_topics/schema_version). SCHEMA_VERSION="0.94.0" 独立 schema 跟 POMDPPolicy 0.93.0 / CognitiveTwinAgent 0.92.0 隔离. __post_init__ 防御性校验 (name lowercase alphanumeric / version semver / subscribed_topics 在 LearningEventType enum / dependencies 不能 self-loop). 12 新增 tests (pytest 1308 → 1320). Plugin SDK 从"硬编码 8 subscriber"提升到"SDK-level 基类 + 元数据契约", 为后续 PluginRegistry + first-party plugin 提供基类.
- **v0.94.0-b** ✅ (2026-08-13): PluginRegistry singleton + Register API + PluginRuntime DI 集成 (Phase 7+ 抽象推演 #7 sub-version b). NEW `ecos/plugins/registry.py` (~120 行). PluginRegistry 跟 DomainRegistry v0.88.0-a 完全 parallel API (register / get / list_names / list_plugins / has / clear / reset / subscribe_all / unsubscribe_all). subscribe_all 遍历所有 plugin, 调 enable() + bus.subscribe(topic, plugin.on_event). unsubscribe_all 调 disable() + bus.unsubscribe(). register 时校验 dependencies 已注册. MODIFY PluginRuntime.__init__ 加 plugin_registry_factory kwarg (DI 注入, 默认 None → 从 PluginRegistry.get_default() singleton 拉). start() 先 register built-in 8 subscriber, 然后调 registry.subscribe_all (顺序保证 built-in 优先). subscription_count 维持 8 (Plugin SDK 不增加新 built-in subscriber, first-party plugin 走 PluginRegistry 动态 subscribe). 13 新增 tests (pytest 1320 → 1333). Plugin SDK 从"基类"提升到"基类 + 注册管理 + DI 双轨", 为后续 first-party plugin 提供 register API.
- **v0.94.0-c** ✅ (2026-08-13): First-party plugin library + LearningEvent factory + examples 升级 (Phase 7+ 抽象推演 #7 sub-version c). NEW `ecos/plugins/first_party/{__init__,hint_fatigue,parent_engagement,teacher_progress}.py` (~80 行 each). HintFatiguePlugin (订阅 hint_requested, 计数 > 5 告警, 跟 examples/plugin_sample_human_feedback.py::use_case_hint_fatigue_detection 同模式但升级为 SDK-level Plugin ABC 继承). ParentEngagementPlugin (订阅 pomdp_diagnostic_updated, 读 POMDPDiagnostic.evolution K=10 timed snapshots + most_likely_state, 跟 examples/plugin_sample_pomdp_diagnostic.py::use_case_parent_engagement_dashboard 同模式但升级为 SDK-level Plugin ABC 继承). TeacherProgressPlugin (订阅 pomdp_diagnostic_updated, 读 POMDPDiagnostic.coverage 冷启动判断 + advice, 跟 examples/plugin_sample_pomdp_diagnostic.py::use_case_teacher_progress_review 同模式但升级为 SDK-level Plugin ABC 继承). MODIFY LearningEvent.from_pomdp_diagnostic_updated factory method (跟 from_hint_requested / from_idle_detected / from_goal_changed / from_reflection_completed 完全 parallel pattern). MODIFY examples/plugin_sample_human_feedback.py + examples/plugin_sample_pomdp_diagnostic.py 升级 use case 函数返回类型 Optional[str] (走 PluginRegistry 而非内联 handler). 15 新增 tests (pytest 1333 → 1348). Plugin SDK 从"基类 + 注册管理"提升到"基类 + 注册管理 + 3 first-party reference implementations", Plugin 开发者可直接继承 Plugin ABC 写新 plugin 或 register first-party.
- **v0.94.0-d** ✅ (2026-08-13): Persistence + canary + docs + examples (Phase 7+ 抽象推演 #7 sub-version d). NEW `ecos/persistence/plugin_registry_store.py` (~210 行). PluginRegistryStore class 跟 LCAStore 完全 parallel API (save_plugin / load_plugin / list_all / delete_plugin / set_enabled). plugin_registry 表 schema (name PRIMARY KEY / version / enabled / subscribed_topics JSON / metadata JSON / schema_version="0.94.0" / registered_at). CREATE TABLE IF NOT EXISTS 幂等 (老 DB v0.93 前无 plugin_registry 表自动建表). MODIFY PluginRegistry.save_to_db / load_from_db + _instantiate_first_party_plugin 辅助 (load 时 instantiate 3 first-party plugin 类). 老 schema_version 不匹配 graceful skip + _log.warning (跟 LCAStore 老 snapshot compat 一致). NEW `docs/plugin_library.md` (~280 行, 8 section: §一 原则 / §二 ABC 契约 / §三 Metadata 字段 / §四 PluginRegistry API / §五 3 first-party plugin 详解 / §六 注册生命周期 / §七 防御性自检 / §八 调用样例). NEW `examples/plugin_sample_first_party.py` (~200 行, 3 use case: register_three_first_party / enable_disable_lifecycle / hot_reload_from_db). MODIFY docs/plugin_sdk.md 7 → 8 subscriber table (v0.93.0-b 加的 pomdp_diagnostic_updated) + v0.94 Plugin SDK 表面化补充 (Plugin ABC / PluginRegistry / 3 first-party plugin 引用 docs/plugin_library.md). H3-c4 canary 维持 (Plugin lifecycle 不污染 BeliefState, 走 bus.subscribe(plugin.on_event) → plugin.on_event 返 result dict 不写 state). v0.81 replay canary 维持 (Plugin Registry 不参与 replay, Plugin 是 configuration 而非 per-student state). 老 DB compat (CREATE TABLE IF NOT EXISTS 幂等). 17 新增 tests (pytest 1348 → 1365, +4 +4 +4 +1 = 13 docs/doctest/regression tests). 累计 Kernel 深化 12 版本 (v0.83 → v0.94), pytest 736 → 1365 (+629, +85.5%). Plugin SDK 100% production-ready (Kernel-only SDK 100%, Teacher/Parent Dashboard 应用层落地推迟 v0.95+ per project-strategy-kernel-first.md).
- **v0.95.0+** (Phase 7+ 抽象推演 #8+ -> **2026-08-17 修订, Bisen 拍板**): Kernel-first 战略第二阶段 - **验证优先 + 应用层产品化落地** (原 Teacher/Parent Dashboard 应用层落地, 升级为验证载体定位). 详见 [discussions/2026-08-17-v095方向审查-验证滞后于抽象与应用层产品化规划.md](../../discussions/2026-08-17-v095方向审查-验证滞后于抽象与应用层产品化规划.md) + §8.2 v0.95+ 方向修订 block. 要点: ①抽象推演冻结 (#8+ 不再预排, 只在需求牵引时启动); ②v0.95 前端产品化底座 (React 18 + Vite + TS + ECharts) + 教师端真实化 (证据链视图); ③v0.96 学生端产品化改造 (含 4 个行为事件端点接通, 解锁 v0.91-v0.94 Kernel 投资); ④v0.97 家长端 + 验证主线 (三个科学问题跟踪表 + 小规模试点 5-10 学生). Kernel SDK 100% production-ready 状态不变, first-party plugin 仍直接挂载教师/家长 Dashboard.

**设计原则**:
- **Domain-agnostic Kernel 1 套**: LinUCB / Thompson / POMDP / Evidence / Runtime / StateEngine 不引用 Domain
- **Domain-specific Extension N 套**: 3 个 Domain 各有独立 capability_ontology + profile_extensions
- **Capability 是 Domain 入口**: 通过 `capability_ontology` 暴露 Domain 能力 (复用 v0.86.0-a Capability frozen dataclass)
- **BeliefState 不重命名** (v0.86.0 推迟): v0.88.0-b 才加 `domain_extension` 字段, 渐进迁移
- **防御性自检 [8] 仍 hard block**: Domain dataclass 不 mutate state

---

## 4. LCA 4 层拆分映射

**2.0 定义**：Planner -> Experiment Designer -> Evaluator -> Policy Learner。

| 现有代码 | 接近度 | 说明 |
|---|---|---|
| **Planner (v0.82.0-a)** | | |
| `ecos/lca/planner.py:Planner` | 100% | LCA 4-layer 第 1 层. 持有 L3 组件 (CLT/Bjork/CA scaffolding) + CAStateMachine. `plan(cta_input, intervention_history=None) -> PlanDecision` (4 步合一) |
| `ecos/lca/planner.py:PlanDecision` (frozen) | 100% | 不可变值对象: bloom_target/ca_stage/clt_level/bjork_triggers. 给后 3 层消费 |
| `ecos/lca/planner.py:PlannerConfig` | 100% | clt_config/ca_config/mastery_threshold=0.5/trajectory_min_len=5. 显式配置化 v0.81 LCAEngine 内联阈值 |
| **Experiment Designer (v0.82.0-b)** | | |
| `ecos/lca/experiment_designer.py:ExperimentDesigner` | 100% | LCA 4-layer 第 2 层. `design(plan, cta_input, n_candidates=None) -> List[Intervention]`. CA 阶段/Bjork/CLT 调整算法跟 v0.81 LCAEngine._generate_candidates 一致 |
| `ecos/lca/experiment_designer.py:ExperimentDesignerConfig` | 100% | n_candidates=10 / default_types / default_difficulties / quantity_by_type / scaffolding_by_clt / feedback_density 全部可注入 |
| `ecos/lca/cta_input.py:CTAInput` | 100% | v0.82.0-b 抽到独立文件 (打破 orchestrator ↔ experiment_designer 循环 import) |
| **Evaluator (v0.82.0-c)** | | |
| `ecos/lca/evaluator.py:Evaluator` | 100% | LCA 4-layer 第 3 层. `estimate_gain/risk` + `record_intervention/attribute_effect` (wrap LCAAttribution) |
| `ecos/lca/evaluator.py:EvaluatorConfig` | 100% | gain_scale=0.3 / risk_gap_coef=0.5 / scaffolding_factor 显式化. expected_gain_scale 从 LCAEngineConfig 移除 |
| **Policy Learner (v0.82.0-d)** | | |
| `ecos/lca/policy_learner.py:PolicyLearner` | 100% | LCA 4-layer 第 4 层. per-student LCAPolicyLearner lazy init (v0.57.0 隔离). `select/update/is_cold_start/dump/load` 委托 LCAPolicyLearner |
| `ecos/lca/policy_learner.py:PolicyLearnerConfig` | 100% | bandit_config + cold_start_threshold=10. v0.83+ 扩展 Thompson Sampling / POMDP 同接口 |
| `ecos/lca/l4_optimization/policy_learner.py:LCAPolicyLearner` | 100% | v0.82.0-d 仍是底层实现, PolicyLearner 包装它 |
| `ecos/lca/l4_optimization/linucb.py:LinUCB` | 100% | 核心算法, 跟 v0.81 一致 |
| `ecos/lca/l4_optimization/attribution.py:LCAAttribution` | 100% | 因果归因, Evaluator 包装它 |
| **LCAEngine facade (v0.82.0-d)** | | |
| `ecos/lca/orchestrator.py:LCAEngine` | 100% | 632 → 491 行 (-22%). 委托 4 子层. 保留 5 接口方法 (select_intervention/update/dump_state/load_state/_is_linucb_cold_start) + 5 backward-compat shim (_get_bandit/_estimate_gain/__getattr__ 5 字段转发/self.bandits 引用=self.policy_learner._learners/self.attribution 引用=self.evaluator.attribution) |

**演进建议 (a/b/c/d 4 sub-phases, 2026-08-10 全部完成)**：
- **v0.82.0-a** ✅ (2026-08-10): Planner 提取 (ec 193 行 + 16 tests + Planner.__getattr__ 5 字段转发)
- **v0.82.0-b** ✅ (2026-08-10): ExperimentDesigner 提取 (220 行 + 13 tests) + cta_input.py 打破循环 import (30 行)
- **v0.82.0-c** ✅ (2026-08-10): Evaluator 提取 (190 行 + 13 tests) + `engine.attribution` = `evaluator.attribution` shared reference (向后兼容 tests/test_lca_update_reward_actual_outcome.py monkey-patch)
- **v0.82.0-d** ✅ (2026-08-10): PolicyLearner 提取 (270 行 + 15 tests) + LCAEngine facade finalization (491 行, -22%) + `engine.bandits` = `policy_learner._learners` shared reference (向后兼容 dual_agent/orchestrator.py:569 `lca_engine.bandits.get(sid)`)
- **v0.83+**: Thompson Sampling / POMDP 在 PolicyLearner 同接口扩展 (LCA 4-layer 第 4 层演进)

### 4.5 Plugin Runtime 雏形 (v0.84.0-d)

v0.84.0-d 在 LCA 4-layer 之外, 引入 Plugin Runtime 雏形 (kernel-mapping §6 Plugin SDK):

| 现有代码 | 接近度 | 说明 |
|---|---|---|
| `web/api/plugin_runtime.py:PluginRuntime` (v0.84.0-d) | 100% | 包装 Runtime API 作为 EventBus subscriber, start() 注册 response_submitted, _handle_response_submitted 调 Runtime.update_belief(state=...) |
| `ecos/runtime/api.py:update_belief` 新增 `state` kwarg (v0.84.0-d) | 100% | 复用已有 BeliefState (Plugin SDK 路径), 不传时 estimate 创建新 (向后兼容) |
| `web/api/belief.py:_update_via_plugin_or_legacy` (v0.84.0-d) | 100% | submit_answer helper: bus.publish → PluginRuntime 处理, success=0 走 legacy fallback |
| `web/api/belief.py:submit_answer` (v0.84.0-d 改造) | 50% | Plugin 路径生效需 PluginRuntime.start() 注册 (production 激活留 v0.85+) |
| 缺失: /api/judge / /api/dual_agent / /api/lca Plugin 化 | 0% | 3 endpoint 直调 Engine.update / orchestrator.process_observation / LCA.select_intervention, 留 v0.85+ |

---

## 5. Runtime API 映射

**2.0 定义**：6 个核心 API（estimate / update_belief / replay / evaluate / simulate / plan）。

| API | 现有代码 | 接近度 |
|---|---|---|
| `estimate(student_id)` | `ecos/runtime/api.py:estimate` (v0.83.0-d) | 100% -- kwargs 注入 belief_engine, singleton 懒加载 |
| `update_belief(student_id, evidence)` | `ecos/runtime/api.py:update_belief` (v0.83.0-d) | 100% -- kwargs 注入 belief_engine / lca_result / log_event |
| `replay(student_id, events)` | `ecos/runtime/api.py:replay` (v0.83.0-d) | 100% -- 委托 BeliefEngine.replay (v0.81.0-c) |
| `evaluate(student_id, metric, **kwargs)` | `ecos/runtime/api.py:evaluate` (v0.83.0-d) | 100% -- 4 metric 路由 (twin_attribution / policy_ab / goal_completion / ece) 委托 EvaluationEngine |
| `simulate(student_id, events, fork_at_idx, alternative_events)` | `ecos/runtime/api.py:simulate` (v0.83.0-d) | 100% -- 委托 BeliefEngine.simulate (v0.81.0-c) |
| `plan(student_id, audience="student")` | `ecos/runtime/api.py:plan` (v0.83.0-d) | 100% -- kwargs 注入 lca_engine / cta_input, 委托 LCAEngine.select_intervention (v0.82.0) |

**演进建议**：
- **v0.78.0**：公开 Runtime API（6 个核心 API）✅ 2026-08-10 v0.83.0-d 落地
- **Phase 7+**：所有 UI / Agent / LLM 通过 Runtime API 交互

---

## 6. Plugin SDK 边界映射

**2.0 定义**：Plugin 不调用 Twin,Plugin 只能产生 Event。

| 现有代码 | 接近度 | 说明 |
|---|---|---|
| `web/api/answer.py` (POST /api/answer) | 100% | v0.84.0-d 改造为 "produce event → bus → Runtime.update_belief". Plugin Runtime subscriber 间接调 Runtime 委托, 不直接 mutate state |
| `web/api/judge.py` (POST /api/judge) | 100% | v0.85.0-a 改造. judge_completed event, Plugin Runtime subscriber 委托 Runtime. 不直接写 response_history |
| `web/api/dual_agent.py` (POST /api/dual_agent) | 100% | v0.85.0-b 改造. request_calibration event, Runtime subscriber 委托 DualAgentOrchestrator.process_observation. 持久化走 _write_calibration_log |
| `web/api/lca.py` (LCA 路径) | 100% | v0.85.0-c 改造. request_intervention event, Runtime subscriber 委托 Runtime.plan. 持久化走 _save_lca_state |
| `web/api/event/hint` (POST frontend stub) | 100% | v0.91.0-b 改造. hint_requested event, Plugin Runtime subscriber 委托 LCAEngine.append_human_feedback (allowlisted mutation) |
| `web/api/event/idle` (POST frontend stub) | 100% | v0.91.0-b 改造. idle_detected event, 同样路径 |
| `web/api/event/goal_change` (POST frontend stub) | 100% | v0.91.0-b 改造. goal_changed event, 同样路径 |
| `web/api/event/reflection` (POST frontend stub) | 100% | v0.91.0-b 改造. reflection_completed event, 同样路径 |
| **Plugin 只产生 Event 原则** | 100% | v0.91.0-e 文档化 (docs/plugin_sdk.md) + 5 use case sample (examples/plugin_sample_human_feedback.py). PluginRuntime 7 subscribers 全接通 Human Twin |
| **Plugin SDK surface (基类 + 元数据契约)** | 100% | v0.94.0-a/b NEW `ecos/plugins/{__init__,base,registry}.py` (Plugin(ABC) 4 abstract method + PluginMetadata(frozen=True) dataclass + PluginRegistry singleton 跟 DomainRegistry v0.88.0-a 完全 parallel API + DI 双轨 plugin_registry_factory kwarg 注入) |
| **Plugin first-party library** | 100% | v0.94.0-c NEW `ecos/plugins/first_party/` (HintFatiguePlugin + ParentEngagementPlugin + TeacherProgressPlugin 3 first-party reference plugin) |
| **Plugin persistence** | 100% | v0.94.0-d NEW `ecos/persistence/plugin_registry_store.py` (PluginRegistryStore save/load/list_all + plugin_registry DB 表 CREATE TABLE IF NOT EXISTS 幂等 + schema_version 隔离) |
| **Plugin SDK 文档化** | 100% | v0.91.0-e + v0.94.0-d NEW `docs/plugin_sdk.md` (8 section) + `docs/plugin_library.md` (NEW 8 section) + `examples/plugin_sample_human_feedback.py` + `examples/plugin_sample_pomdp_diagnostic.py` + `examples/plugin_sample_first_party.py` (3 NEW use case: register_three_first_party / enable_disable_lifecycle / hot_reload_from_db) |
| **Plugin 8 subscribers** | 100% | PluginRuntime 8 subscribers 全接通 (response_submitted / request_calibration / request_intervention / hint_requested / idle_detected / goal_changed / reflection_completed / pomdp_diagnostic_updated). v0.93.0-b 加 pomdp_diagnostic_updated, v0.94.0-d 升级 7→8 subscriber 文档化 |
| **Plugin 3 first-party 引用** | 100% | v0.94.0-c/d NEW HintFatiguePlugin / ParentEngagementPlugin / TeacherProgressPlugin 3 first-party plugin + PluginRegistry.subscribe_all 动态 subscribe + PluginRegistryStore 持久化 hot-reload |

**演进路径** (回顾):
- **v0.84.0-a/b/c/d**: Plugin SDK 雏形 (1 subscriber + EventBus + retention) — 10%
- **v0.85.0-a/b/c/d**: Plugin SDK 100% + Production Activation (3 subscribers + Flask startup) — 80%
- **v0.91.0-b/e**: Plugin SDK 100% production (4 frontend stub subscriber + docs + sample) — 100%
- **v0.94.0-a/b/c/d**: Kernel-only SDK 100% (Plugin ABC + PluginRegistry + 3 first-party + persistence + docs) — 100% (Kernel-first 战略第二阶段准备: Teacher/Parent Dashboard 应用层 v0.95+ 落地)

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
| 80%+ | LinUCB / LCAPolicyLearner / 测试基础设施 / 抗幻觉 / StateEngine (6/6) / EventLog + Replay + Simulation | 6 - **[v0.81.0]** State Engine 抽象 + Event Engine 80% 完成 |
| 100% (LCA 4-layer) | Planner / ExperimentDesigner / Evaluator / PolicyLearner / Intervention / LCAAttribution | 6 - **[v0.82.0]** LCA 4-layer split 100% 完成 (a/b/c/d 4 sub-phases, 2026-08-10) |
| 100% (v0.83.0) | Evidence Engine (6 来源 + 跨 3 表 CRUD) / Belief-Evidence 关联 (add_evidence + 反查) / Evaluation Engine (TwinAttribution + PolicyABTest + GoalCompletion) / Runtime API (6 核心纯函数 + kwargs) | 4 类 12 文件 - **[v0.83.0]** Evidence Engine + Runtime API 100% 完成 (a/b/c/d 4 sub-phases, 2026-08-10) |
| 100% (v0.84.0) | LearningEventType enum (7 值) / LearningEvent factory methods (3) / CalibrationMessage.to_learning_event / FeatureExtractor event_log 注入 / DualAgentOrchestrator event_log 注入 / EventBus pub/sub / EventLog retention policy / PluginRuntime + /api/answer Plugin 路径 | 8 类 17 文件 - **[v0.84.0]** Event Engine 100% + Event 统一输入 95% + Plugin SDK 10% 完成 (a/b/c/d 4 sub-phases, 2026-08-11) |
| 100% (v0.85.0) | LearningEventType enum (10 值) / 8 LearningEvent factory methods / PluginRuntime (3 subscriber: response_submitted + request_calibration + request_intervention) / /api/answer + /api/judge + /api/dual_agent + /api/lca 4 endpoint Plugin 路径 / Flask startup production activation / 4 frontend stub endpoint (hint / idle / goal_change / reflection) | 11 类 24 文件 - **[v0.85.0]** Plugin SDK 100% + Event 统一输入 100% + Runtime event-driven 50% 完成 (a/b/c/d 4 sub-phases, 2026-08-11) |
| 60-80% | BeliefState(Twin 雏形) / DimensionState(Belief 雏形) / MIRT(Inference) / BKT(Inference) | 4 |
| 40-60% | Observation / CalibrationMessage / partial credit / LLM Critic / attribution | 5 |
| 20-40% | calibration_log / response_history / evidence_predictions 占位 | 3 |
| 80% (v0.88.0-a) | Multi-Domain 抽象层 (Domain ABC + 3 Domain + DomainRegistry) | 1 |

### 8.2 缺失核心组件清单

完全缺失（接近度 ≤ 20%）：
1. **Multi-Domain 集成 (Runtime + LCA)** —— v0.88.0-b 目标 (Phase 7+ 抽象推演 #1)

> **[v0.88.0-b 更新 2026-08-11]**: Phase 7+ 抽象推演 #1 sub-version b 完成. Multi-Domain 集成 (DomainExtension + Runtime + LCA + Evaluator). 26 新增 tests (pytest 985 → 1011, +2.7%). 详情见 §3.1.
> - NEW BeliefState.domain_extension (Dict[str, Any] 字段 + set/get/has allowlisted mutation, 跟 motivation 模式一致)
> - NEW Runtime.plan_domain_aware API (跟 plan_motivation_aware 模式一致, plan / plan_goal_aware / plan_motivation_aware / plan_domain_aware 4-way 并行)
> - MODIFY ExperimentDesigner domain-aware 候选池 (domain_aware_types config, education=None / science=INQUIRY / career=PRACTICE, domain 在 CAStage 之后 final override)
> - NEW Evaluator.domain_reward_adjustment (DOMAIN_REWARD_FACTORS: education=1.0 / science=1.1 / career=1.2 / creative=0.9)
> - MODIFY LCAEngine.select_intervention domain_name kwarg (透传 Designer + 注入 reward factor)
> - MODIFY scripts/check_no_direct_state_mutation.py FUNC_ALLOWLIST += set_domain_extension (防御性自检 [8] 仍 hard block)
> - Domain-agnostic Kernel 不变 (POMDP / LinUCB / Thompson / Evidence 不感知 Domain)
> - H3-c4 + v0.81 replay canary 全 PASS. apply_snapshot 路径覆盖 domain_extension (兜底老 snapshot).
> - 下一阶段 v0.88.0-d: POMDP 集成 LCAEngine.select_intervention + PolicyABTest 升级.

> **[v0.88.0-c 更新 2026-08-11]**: Phase 7+ 抽象推演 #1 sub-version c 完成. POMDP 完整 (依赖型 T+R). 16 新增 tests (pytest 1011 → 1027, +1.6%). 详情见 §1.3 (Policy Engine).
> - MODIFY POMDPPolicy.transition: 2D (n_states x n_states, v0.87.0-c) → 3D (n_states x n_states x n_arms, v0.88.0-c). 不同 action → 不同 T[a].
> - MODIFY POMDPPolicy.reward: random uniform (v0.87.0-c) → 固定 init (state s 偏好 arm 区间, U(0.5, 1.0), 其他 U(0.0, 0.5))
> - MODIFY POMDPPolicy.bayes_update(observation) → bayes_update(action, observation) (考虑 action)
> - MODIFY POMDPPolicy.dump_state: 加 schema_version="0.88.0-c" 标识 (老 snapshot 不兼容)
> - MODIFY POMDPPolicy.load_state: schema_version 校验 (老 snapshot raise)
> - 接口同构 LinUCB/Thompson (select_arm / update 名称不变). bayes_update 是 POMDP-specific, 可变.
> - 防御性自检 [8] 仍 hard block. H3-c4 + v0.81 replay canary 全 PASS.
> - 下一阶段 v0.88.0 final: 文档同步 + memory v0.87.0 → v0.88.0 completion state.

> **[v0.88.0-d 更新 2026-08-11]**: Phase 7+ 抽象推演 #1 sub-version d 完成. POMDP 集成 Runtime + 真 A/B 3-way 升级. 17 新增 tests (pytest 1027 → 1044, +1.7%). 详情见 §1.3 + §2.5.
> - NEW LCAPolicyLearner.set_observation API (LCAEngine 调用)
> - NEW LCAPolicyLearner._reward_to_observation (reward → obs 离散化)
> - MODIFY LCAPolicyLearner select_intervention pomdp path: 消费 obs 后调 bayes_update(action, obs)
> - MODIFY LCAPolicyLearner update pomdp path: 计算 obs from reward 存 _last_observation
> - MODIFY LCAEngine: per-student _last_observation 跟踪 + select forward to learner + update records obs
> - 无需修改 PolicyABTest._create_fresh_bandit (POMDPPolicy(n_arms=10, seed=42) 自动用 v0.88.0-c schema)
> - 接口同构 LinUCB/Thompson (set_observation 在 linucb/thompson 路径静默忽略)
> - 防御性自检 [8] 仍 hard block. H3-c4 + v0.81 replay canary 全 PASS.
> - POMDP Runtime 集成 + Multi-Domain 100% 全部完成.
> - **v0.88.0 final 完成**: README.md / CLAUDE.md / 12-kernel-mapping §8.2 / memory (`project-v088-completion-state.md`) 全部同步. 缺失清单 0 项剩.
> - 下一阶段 v0.89.0+: Phase 7+ 抽象推演 #2+ (Twin → Human Twin + Plugin SDK 文档化 + Teacher/Parent Dashboard + 跨学科扩展) + POMDP point-based solver (POMCP / DESPOT).

> **[v0.89.0-a 更新 2026-08-12]**: Phase 7+ 抽象推演 #2 sub-version a 完成. POMDP point-based solver 雏形 (PBVI + α-vector). 19 新增 tests (pytest 1044 → 1063, +1.8%). 详情见 §1.3 + §3.1.
> - NEW `ecos/lca/l4_optimization/pomdp_solver.py` (AlphaVector frozen dataclass + PBVI class + 单步 backup + alpha_value/best_action)
> - 防御性自检 [8] 仍 hard block. H3-c4 + v0.81 replay canary 全 PASS.

> **[v0.89.0-b 更新 2026-08-12]**: Phase 7+ 抽象推演 #2 sub-version b 完成. PBVI 完整算法 + belief point sampling. 12 新增 tests (pytest 1063 → 1075, +1.1%). 详情见 §1.3.
> - MODIFY backup_step 算法: 经典 PBVI (Sondik 1971 简化) — 对每个 state s 算 V_a(δ_s), 输出 α.values shape (n_states,)
> - NEW PBVI.update_alpha_vectors 收敛检测 (max abs diff < epsilon)
> - NEW PBVI.solve 主算法 (iterative backup + 收敛)
> - NEW reachable_belief_points (随机采样, 含 initial anchor) + uniform_belief_points (Dirichlet 均匀)
> - 防御性自检 [8] 仍 hard block. H3-c4 + v0.81 replay canary 全 PASS.

> **[v0.89.0-c 更新 2026-08-12]**: Phase 7+ 抽象推演 #2 sub-version c 完成. POMDPPolicy 集成 PBVI. 10 新增 tests (pytest 1075 → 1085, +0.9%). 详情见 §1.3.
> - MODIFY POMDPPolicy: use_pbvi=True 默认 + pbvi_gamma/epsilon/n_iters/n_belief_points 配置 + lazy _init_pbvi_solver + solve_pbvi() 显式入口
> - MODIFY POMDPPolicy.select_arm: PBVI 路径 (solver.best_action) + PBVI 失败 fallback QMDP
> - MODIFY POMDPPolicy.dump_state: use_pbvi + pbvi_config + solver_state 持久化
> - MODIFY POMDPPolicy.load_state: schema_version="0.89.0-c" 校验 + α-vector state-space 维度校验
> - 防御性自检 [8] 仍 hard block. H3-c4 + v0.81 replay canary 全 PASS.

> **[v0.89.0-d 更新 2026-08-12]**: Phase 7+ 抽象推演 #2 sub-version d 完成. Runtime + PolicyABTest 集成 PBVI. 11 新增 tests (pytest 1085 → 1096, +1.0%). 详情见 §1.3.
> - MODIFY LCAPolicyLearner.__init__: pomdp_use_pbvi 形参 (默认 None → POMDPPolicy True)
> - MODIFY LCAPolicyLearner.select_intervention POMDP 路径: 显式 solve_pbvi (try/except 兜底)
> - MODIFY LCAEngine.select_intervention POMDP 路径: 显式 solve_pbvi (双层防御, dual_agent 直走也生效)
> - MODIFY PolicyABTest._create_fresh_bandit: POMDP 工厂 use_pbvi=True
> - MODIFY POMDPPolicy.solve_pbvi: 幂等 (α 缓存命中跳过重复 backup)
> - MODIFY PolicyLearnerConfig: pomdp_use_pbvi 透传
> - Runtime.plan 签名稳定, opt-out kwargs 留 v0.90+
> - 防御性自检 [8] 仍 hard block. H3-c4 + v0.81 replay canary 全 PASS.

> **[v0.89.0 final 完成 2026-08-12]**: README.md / CLAUDE.md / 12-kernel-mapping §1.3 + §8.2 / memory (`project-v089-completion-state.md`) 全部同步. 缺失清单 0 项剩.
> - 下一阶段 v0.90+: Phase 7+ 抽象推演 #2+ (Twin → Human Twin + Plugin SDK 文档化 + Teacher/Parent Dashboard + 跨学科扩展) + POMDP T(s'|s,a) / R(s,a) 在线学习.

> **[v0.90.0-a 更新 2026-08-12]**: Phase 7+ 抽象推演 #3 sub-version a 完成. POMDP T/R posterior 数据结构 (Beta-Multinomial conjugate). 12 新增 tests (pytest 1096 → 1108, +1.1%). 详情见 §1.3.
> - NEW `ecos/lca/l4_optimization/pomdp_learner.py` (TransitionPosterior Dirichlet 多项式共轭 + RewardPosterior Beta 共轭 + posterior mean MAP + 越界 raise + total_evidence + get_arm_stats 接口同构 ThompsonSampling)
> - POMDP Policy §1.3 T/R 学习数据通路 0% → 起步. 接口同构 LinUCB/Thompson/POMDP 维持.

> **[v0.90.0-b 更新 2026-08-12]**: Phase 7+ 抽象推演 #3 sub-version b 完成. posterior 注入 POMDPPolicy + 持久化 + schema_version 升级 0.89.0-c → 0.90.0. 13 新增 tests (pytest 1108 → 1121, +1.2%). 详情见 §1.3.
> - NEW POMDPPolicy.set_transition_posterior / set_reward_posterior 注入接口
> - NEW _learned_t_r_posterior_mean() 派生 T/R posterior mean
> - MODIFY SCHEMA_VERSION "0.89.0-c" → "0.90.0" (老 snapshot raise)
> - MODIFY dump_state / load_state 加 transition_count / reward_alpha / reward_beta 3 字段
> - 防御性自检 [5] schema_version 校验生效. 防御性自检 [8] 仍 hard block.

> **[v0.90.0-c 更新 2026-08-12]**: Phase 7+ 抽象推演 #3 sub-version c 完成. POMDPPolicy 集成 update_t_r + PBVI 用 posterior mean. 12 新增 tests (pytest 1121 → 1133, +1.1%). 详情见 §1.3.
> - MODIFY POMDPPolicy.__init__: use_learned_t_r=True 默认 + min_samples 形参
> - MODIFY POMDPPolicy.update: observation 可选参数 (默认 None, 老调用兼容)
> - NEW POMDPPolicy._update_t_r(arm, observation, reward): lazy init posterior + 越界 skip
> - NEW POMDPPolicy._resolve_t_r(): 共享路径 (PBVI + QMDP fallback 都用 posterior mean, use_learned_t_r=False → init T/R)
> - PBVI 不直接 mutation self.transition / self.reward (走 transient T/R 输入参数)
> - 防御性自检 [8] 仍 hard block. H3-c4 + v0.81 replay canary 全 PASS.

> **[v0.90.0-d 更新 2026-08-12]**: Phase 7+ 抽象推演 #3 sub-version d 完成. Runtime + PolicyABTest 集成 learned T/R + 冷启动. 10 新增 tests (pytest 1133 → 1143, +0.9%). 详情见 §1.3.
> - MODIFY PolicyLearnerConfig: pomdp_use_learned_t_r 透传 (默认 None → POMDPPolicy True)
> - MODIFY LCAPolicyLearner.__init__: pomdp_use_learned_t_r 形参 + update 透传 obs
> - MODIFY LCAEngine.update POMDP 路径: 透传 pomdp_observation 到 LCAPolicyLearner.update(obs)
> - MODIFY PolicyABTest._create_fresh_bandit POMDP 工厂: use_learned_t_r=True + min_samples=5 (3-way A/B 维持)
> - MODIFY POMDPPolicy._resolve_t_r: min_samples 冷启动保护 (evidence < 5 用 init, ≥ 5 切 learned)
> - FIX RewardPosterior.total_evidence: 公式从 `1 * alpha0` 修正为 `2 * alpha0` per cell (Beta α+β 各 1 prior, 5 evidence 期望)
> - 防御性自检 [8] 仍 hard block (LCAEngine._last_observation 是 instance dict). H3-c4 + v0.81 replay canary 全 PASS.

> **[v0.91.0-a 更新 2026-08-12]**: Phase 7+ 抽象推演 #4 sub-version a 完成. CognitiveTwinAgent 数据结构 + HumanFeedbackEntry. 12 新增 tests (pytest 1143 → 1155, +1.0%). 详情见 §1.4.
> - NEW `ecos/cta/cognitive_twin.py`: HumanFeedbackEntry (frozen dataclass, 4 event_type: hint_requested/idle_detected/goal_changed/reflection_completed) + HumanFeedbackTrajectory (cap 500 pattern 跟 TrajectoryState 同) + CognitiveTwinAgent 3-tuple (belief_state/trajectory/human_feedback) + action_history 占位留 v0.92+
> - scripts/check_no_direct_state_mutation.py FUNC_ALLOWLIST += CognitiveTwinAgent.append_human_feedback (跟 append_trajectory_snapshot 同模式)
> - Plugin SDK 4 frontend stub endpoint Human-in-loop 信号源数据结构闭环
> - 防御性自检 [8] 仍 hard block (append_human_feedback 收口到 allowlist)

> **[v0.91.0-b 更新 2026-08-12]**: Phase 7+ 抽象推演 #4 sub-version b 完成. Runtime + Plugin SDK 4 subscriber. 15 新增 tests (pytest 1155 → 1170, +1.3%). 详情见 §1.4 + §6.
> - MODIFY LCAEngine._cognitive_twin dict (per-student pattern 跟 _last_intervention / _last_observation / _cognitive_twin_pending 一致) + select_intervention cognitive_twin kwarg + append_human_feedback mutation 走 allowlist
> - NEW Runtime.plan_human_feedback_aware (6 plan API upper limit)
> - MODIFY PluginRuntime.start() 加 4 subscriber (hint/idle/goal/reflection) → subscription_count 3 → 7
> - MODIFY POMDPPolicy.SCHEMA_VERSION "0.90.0" → "0.91.0" (老 snapshot raise)
> - Plugin SDK 4 endpoint 全接通 Human Twin, 不再是半成品
> - 防御性自检 [8] 仍 hard block (LCAEngine._cognitive_twin dict mutation 收口到 append_human_feedback)

> **[v0.91.0-c 更新 2026-08-12]**: Phase 7+ 抽象推演 #4 sub-version c 完成. LCA 4 layer 接入 Human feedback. 21 新增 tests (pytest 1170 → 1191, +1.8%). 详情见 §1.4 + §4.1 + §4.2.
> - MODIFY ExperimentDesigner.cognitive_twin kwarg + _human_feedback_itype_override (hint>5→EXPLANATORY / idle>3→INQUIRY / reflection>3→PRACTICE / goal>1→PRACTICE, 优先级 hint>idle>reflection>goal)
> - MODIFY Evaluator.human_feedback_reward_adjustment (hint>5→0.8 / idle>3→0.9 / reflection>3→1.2 / goal>1→1.1, default→1.0)
> - MODIFY LCAEngine.select_intervention kwargs 透传 cognitive_twin → designer + evaluator
> - H3-c4 canary 维持 (cognitive_twin=None 行为 == v0.90 baseline). 多 multiplicative factor chain: base × motivation × domain × human_feedback

> **[v0.91.0-d 更新 2026-08-12]**: Phase 7+ 抽象推演 #4 sub-version d 完成. 冷启动 + 持久化 + canary. 8 新增 tests (pytest 1191 → 1199, +0.7%). 详情见 §1.4 + §5.
> - MODIFY CognitiveTwinAgent.dump_state + load_state (schema_version="0.91.0" 校验, 老 raise per 防御性自检 [5])
> - MODIFY LCAEngine.dump_state + load_state 加 cognitive_twin 字段 + bind_cognitive_twin helper (load_state 暂存 _cognitive_twin_pending, bind 时 materialize)
> - MODIFY persistence/db.py 加 cognitive_twin TEXT 列 (含 ALTER TABLE 增量迁移) + save_student_state cognitive_twin_json kwarg
> - v0.81 replay canary 维持 (cognitive_twin 不通过 StateEngine.replay 重建, 走 LCA 路径)

> **[v0.91.0-e 更新 2026-08-12]**: Phase 7+ 抽象推演 #4 sub-version e 完成. Plugin SDK 文档化 (doctest only). 4 新增 tests (pytest 1199 → 1203, +0.3%). 详情见 §6 + docs/plugin_sdk.md.
> - NEW `docs/plugin_sdk.md` (8 section: Plugin 原则 / 7 Subscriber 契约 / LCAEngine.append_human_feedback / 防御性自检 / Runtime 6 plan API / 5 sub-commit 演进日志 / 相关文档 / 调用样例)
> - NEW `examples/plugin_sample_human_feedback.py` (5 use case: teacher_reflection / parent_goal / hint_fatigue / idle_reminder / deep_reflection + register_all_use_cases entry + _self_test_imports smoke)
> - NEW `tests/test_plugin_sdk_docs.py` (4 doctest: 8 section / link 存在 / use case 暴露 / smoke PASS)
> - 防御性自检 [2] test_version_consistency regex 扩展允许 -e sub-version 后缀 (Phase 7+ 抽象推演第 5 sub-commit)

> **[v0.91.0 final 完成 2026-08-12]**: Phase 7+ 抽象推演 #4 (Twin → Human Twin 抽象 + Plugin SDK 文档化) 5 sub-commit 全部完成. README.md / CLAUDE.md / 12-kernel-mapping §8.2 / memory (`project-v091-completion-state.md`) 全部同步. 缺失清单 0 项剩.
> - pytest 1143 → 1203 (+60, +5.2%). 累计 Kernel 深化 9 版本 (v0.83 → v0.91), pytest 736 → 1203 (+467, +63.5%)
> - Plugin SDK 100% production (7 subscribers 全接通 Human Twin)
> - Runtime 6 plan API upper limit (plan_human_feedback_aware 是 v0.91 第 6 个)
> - LCA select_intervention kwargs 三路并行 (motivation / domain / cognitive_twin)
> - 下一阶段 v0.92+: Phase 7+ 抽象推演 #5+ (HumanTwinSnapshot ActionHistory 占位兑现 + 第一方 plugin 库 + POMDP T/R 后验可视化 + Teacher/Parent Dashboard 应用层)

> **[v0.92.0-a 更新 2026-08-12]**: Phase 7+ 抽象推演 #5 sub-version a 完成. HumanTwinSnapshot ActionHistory 占位兑现 (ActionEntry/ActionHistory 数据结构). 12 新增 tests (pytest 1203 → 1215, +1.0%). 详情见 §1.4 + §5.
> - NEW `ecos/cta/cognitive_twin.py` ActionEntry frozen dataclass (5 action_type: intervention_selected/dual_agent_calibrated/reward_recorded/policy_updated/goal_changed)
> - NEW ActionHistory cap 500 (跟 HumanFeedbackTrajectory 完全 parallel)
> - MODIFY CognitiveTwinAgent 3-tuple → 4-tuple (加 action_history: ActionHistory)
> - MODIFY SCHEMA_VERSION "0.91.0" → "0.92.0" (老 snapshot raise per 防御性自检 [5])
> - NEW append_action_history allowlisted mutation (FUNC_ALLOWLIST += CognitiveTwinAgent.append_action_history)

> **[v0.92.0-b 更新 2026-08-12]**: Phase 7+ 抽象推演 #5 sub-version b 完成. Runtime + LCAEngine append_action_history 接入 (Runtime 6 → 7 plan API, POMDP schema 0.91.0 → 0.92.0). 15 新增 tests (pytest 1215 → 1230, +1.2%). 详情见 §1.4 + §5.
> - MODIFY LCAEngine.append_action_history method (lazy init CognitiveTwinAgent from state, parallel to append_human_feedback)
> - MODIFY LCAEngine.select_intervention Step 7 自动记录 intervention_selected ActionEntry + update reward 反馈路径自动记录 reward_recorded ActionEntry
> - NEW Runtime.plan_action_aware (第 7 plan API, 委托链 plan → plan_goal_aware → plan_motivation_aware → plan_domain_aware → plan_human_feedback_aware → plan_action_aware)
> - MODIFY POMDPPolicy SCHEMA_VERSION "0.91.0" → "0.92.0"

> **[v0.92.0-c 更新 2026-08-12]**: Phase 7+ 抽象推演 #5 sub-version c 完成. LCA 4 layer 接入 (5 factor chain: base × motivation × domain × human_feedback × action_history). 21 新增 tests (pytest 1230 → 1251, +1.7%). 详情见 §1.4 + §5.
> - MODIFY ExperimentDesigner.action_history kwarg + _action_history_itype_override (5 case priority: reward_low / type_diversity / dual_agent / policy_cold / goal_changed)
> - NEW Evaluator.action_history_reward_adjustment (reward_recorded 平均<0.5→0.85, >0.7→1.15, dual_agent>0.5 半→1.05, default→1.0)
> - MODIFY LCAEngine.select_intervention kwargs 透传 action_history → designer + evaluator
> - H3-c4 canary 维持 (action_history=None 行为 == v0.91 baseline). 多 factor chain 升级到 5 因素.

> **[v0.92.0-d 更新 2026-08-12]**: Phase 7+ 抽象推演 #5 sub-version d 完成. 冷启动 + 持久化 + canary. 8 新增 tests (pytest 1251 → 1259, +0.6%). 详情见 §1.4 + §5.
> - MODIFY CognitiveTwinAgent 4-tuple dump_state + load_state round-trip (含 action_history 字段, schema_version="0.92.0" 校验)
> - MODIFY LCAEngine.dump_state/load_state cognitive_twin 字段含 4-tuple (human_feedback + action_history)
> - MODIFY LCAEngine.load_state 老 v0.91 snapshot (schema_version="0.91.0" / action_history 字段缺) graceful skip + warning (per 防御性自检 [1])
> - v0.81 replay canary 维持 (action_history 不通过 StateEngine.replay 重建, 走 LCA 路径)

> **[v0.92.0 final 完成 2026-08-12]**: Phase 7+ 抽象推演 #5 (HumanTwinSnapshot ActionHistory 占位兑现) 4 sub-commit 全部完成. README.md / CLAUDE.md / 12-kernel-mapping §1.4 + §8.2 / memory (`project-v092-completion-state.md`) 全部同步. 缺失清单 0 项剩.
> - pytest 1203 → 1259 (+56, +4.7%). 累计 Kernel 深化 10 版本 (v0.83 → v0.92), pytest 736 → 1259 (+523, +71.1%)
> - CognitiveTwinAgent 3-tuple → 4-tuple (加 action_history: ActionHistory)
> - Runtime 7 plan API (plan_action_aware 是 v0.92 第 7 个)
> - LCA select_intervention kwargs 四路并行 (motivation / domain / cognitive_twin / action_history)
> - LCA factor chain 4 → 5 因素 (base × motivation × domain × human_feedback × action_history)
> - Plugin SDK 7 subscribers 维持 (不加新 subscriber — action_history 是 LCA 内部自动记录)
> - 下一阶段 v0.93+: Phase 7+ 抽象推演 #6+ (第一方 plugin 库 + POMDP T/R 后验可视化 + Teacher/Parent Dashboard 应用层)

> **[v0.93.0 final 完成 2026-08-12]**: Phase 7+ 抽象推演 #6 (POMDP T/R 后验可视化) 4 sub-commit 全部完成. README.md / CLAUDE.md / 12-kernel-mapping §1.4 + §8.2 / memory (`project-v093-completion-state.md`) 全部同步. 缺失清单 0 项剩.
> - pytest 1259 → 1308 (+49, +3.9%). 累计 Kernel 深化 11 版本 (v0.83 → v0.93), pytest 736 → 1308 (+572, +77.7%)
> - POMDPDiagnostic 三件套 (TransitionPosteriorSnapshot / RewardPosteriorSnapshot / POMDPDiagnostic frozen dataclass + coverage + most_likely_state + schema_version="0.93.0")
> - POMDPPolicy.get_diagnostic / get_transition_heatmap / get_reward_curves 派生 API (POMDP T/R 后验可视化 surface 落地)
> - Runtime 8 plan/query API (diagnose_pomdp 是 v0.93 第 8 个)
> - LCAEngine._pomdp_diagnostic per-student dict (跟 _cognitive_twin 完全 parallel pattern)
> - Plugin SDK 8 subscribers (pomdp_diagnostic_updated 是 v0.93 第 8 个, 订阅后 LCAEngine.get_pomdp_diagnostic emit)
> - POMDPPolicy._evolution timed snapshots N=50/K=10 (演化追踪)
> - LCAStore lca_state 第 9 列 pomdp_diagnostic TEXT (CLAUDE.md 防御性自检 [5] 9 字段对齐) + ALTER TABLE 老 DB 兼容
> - docs/pomdp_diagnostic.md 8 section + examples/plugin_sample_pomdp_diagnostic.py 3 use case
> - 下一阶段 v0.94+: Phase 7+ 抽象推演 #7+ (第一方 plugin 库 + Teacher/Parent Dashboard 应用层)

> **[v0.94.0 final 完成 2026-08-13]**: Phase 7+ 抽象推演 #7 (Kernel-only SDK — Plugin ABC + Registry + First-party library) 4 sub-commit 全部完成. README.md / CLAUDE.md / 12-kernel-mapping §3.1 + §6 + §8.2 / memory (`project-v094-completion-state.md`) 全部同步. 缺失清单 0 项剩.
> - pytest 1308 → 1365 (+57, +4.4%). 累计 Kernel 深化 12 版本 (v0.83 → v0.94), pytest 736 → 1365 (+629, +85.5%)
> - Plugin SDK surface 100% production-ready: Plugin(ABC) 4 abstract method + PluginMetadata(frozen=True) dataclass (schema_version="0.94.0" 独立) + PluginRegistry singleton (跟 DomainRegistry v0.88.0-a 完全 parallel API) + PluginRuntime DI 集成 (plugin_registry_factory kwarg)
> - 3 first-party plugin reference implementations: HintFatiguePlugin (订阅 hint_requested, 计数 > 5 告警) + ParentEngagementPlugin (订阅 pomdp_diagnostic_updated, 读 POMDPDiagnostic.evolution K=10 timed snapshots + most_likely_state) + TeacherProgressPlugin (订阅 pomdp_diagnostic_updated, 读 POMDPDiagnostic.coverage 冷启动判断)
> - LearningEvent.from_pomdp_diagnostic_updated factory method (跟 from_hint_requested / from_idle_detected / from_goal_changed / from_reflection_completed 完全 parallel pattern)
> - Plugin persistence 100%: PluginRegistryStore 独立 plugin_registry DB 表 (跟 lca_state 隔离) + CREATE TABLE IF NOT EXISTS 幂等 (老 DB v0.93 前无 plugin_registry 表自动建表) + 老 schema_version 不匹配 graceful skip + _log.warning
> - Plugin docs 100%: docs/plugin_sdk.md (升级 7 → 8 subscriber table) + docs/plugin_library.md (NEW ~280 行, 8 section: §一 原则 / §二 ABC 契约 / §三 Metadata 字段 / §四 PluginRegistry API / §五 3 first-party plugin 详解 / §六 注册生命周期 / §七 防御性自检 / §八 调用样例)
> - Plugin examples 100%: examples/plugin_sample_human_feedback.py + plugin_sample_pomdp_diagnostic.py (MODIFY 升级 use case 返回类型 Optional[str] 走 PluginRegistry) + examples/plugin_sample_first_party.py (NEW ~200 行, 3 use case: register_three_first_party / enable_disable_lifecycle / hot_reload_from_db)
> - PluginRuntime 8 subscribers 维持 (Plugin SDK 不增加新 built-in subscriber, first-party plugin 走 PluginRegistry 动态 subscribe)
> - 防御性自检 [8] 0 新 mutation site (Plugin ABC 是 process_event 不 mutate Kernel state, PluginRegistry 是 dict 管理 + bus.subscribe/unsubscribe 不触及 BeliefState, 3 first-party plugin 全程 read-only + log warning, PluginRegistryStore 走 SQL INSERT 不直接 mutation state)
> - FUNC_ALLOWLIST 维持 51+0 = 51 文件 (Plugin 不需要 allowlist — 跟 POMDPDiagnostic 模式一致, frozen dataclass + 不持有 BeliefState 引用)
> - H3-c4 canary 维持 (Plugin lifecycle 不污染 BeliefState, 走 bus.subscribe(plugin.on_event) → plugin.on_event 返 result dict 不写 state)
> - v0.81 replay canary 维持 (Plugin Registry 不参与 replay, Plugin 是 configuration 而非 per-student state)
> - 下一阶段 v0.95+: Teacher/Parent Dashboard 应用层落地 (Kernel-first 战略第二阶段 — Kernel SDK 已 100% production-ready, 应用层可基于 PluginRegistry 直接 register first-party plugin 或继承 Plugin ABC 写新 plugin)

> **[v0.95+ 方向修订 2026-08-17, Bisen 拍板]**: Kernel 深化收口 (12 版本 v0.83-v0.94, pytest 736 -> 1365, 缺失清单 0) 后方向重心切换: **从"Kernel 深化/抽象推演"切换到"验证优先 + 应用层产品化落地"**. 审查依据: `research/deep-research/ECOS系统性深度分析-混合优化版.md` 全文对照 (架构蓝图逐项兑现 = 方向无偏移; 但文档核心结论 "下一阶段应完成科学验证" 滞后 -- 仍是 3 测试用户 / 1 学科, 三个科学问题 (Twin 准确性 / Policy 有效性 / 长期增益) 无一有规模验证; v0.88 Multi-Domain / v0.91 Human Twin 属文档【推演】分支的工程化, 文档第九部分自我修正强调事实/推演边界).
> - **抽象推演冻结**: Phase 7+ 抽象推演 #8+ 不再预排. Plugin SDK 独立打包 (依赖闭包: `ecos/plugins/base.py` 硬 import `ecos.cta.event_log` + 2 个 first_party plugin import `ecos.lca.l4_optimization.pomdp_diagnostic` + pyproject 单一 ecos distribution; 但 `PluginRegistry.subscribe_all(bus: Any)` duck-typing + `PluginRegistryStore` 纯 stdlib 已刻意解耦, 卡住的是事件契约和 first-party 内容) / Science-Career Plugin 词汇表, 仅在真实需求牵引时启动.
> - **v0.95**: 前端产品化底座 (React 18 + Vite + TypeScript + TanStack Query + ECharts; 迁移顺序 教师端先行 -> 学生端重写 -> 家长端复用; `check_defensive.sh` 扩前端段 tsc/eslint/vitest) + 教师端真实化 (NEW `/api/teacher/*`, 换掉 `web/teacher/index.html` 假数据占位, 证据链视图 "系统为什么这么判断" + POMDPDiagnostic 演化 + 干预历史; TeacherProgressPlugin 从 `_log.info` 升级 UI 可消费).
> - **v0.95 (并行, 不等 React)**: 学生端 `app.js` 接通 4 个行为事件端点 (hint / idle / goal_change / reflection, v0.85 建成但前端零调用) -- 解锁 v0.91 人类反馈 / v0.92 行动历史 / v0.94 HintFatiguePlugin 全部 Kernel 投资 + 开始积累 LearningDNA 启用条件 (≥50 题 + 交互行为数据).
> - **v0.96**: 学生端产品化改造 (React 重写 + 信息架构三问 "我在哪 / 我的成长 / 下一步学什么" + `web/api/interpretation.py` 通俗化层全接 + Motivation Profile (v0.87 Kernel 侧 100%) 前端首次呈现 + CodeMirror + 移动端适配).
> - **v0.97**: 家长端 (ParentEngagementPlugin 落地, 复用期成本最低) + 验证主线 (README / 本表新增 "三个科学问题" 跟踪表; 小规模试点 5-10 学生 lbc004+; LearningDNA ≥50 题推进).
> - **v0.98+ (需求牵引解锁)**: C/X 主导题扩量 (5 -> 20+); H1 形式化验证 (视试点缩放); Plugin SDK 独立打包 / Multi-Domain 落地.
> - 详见 [discussions/2026-08-17-v095方向审查-验证滞后于抽象与应用层产品化规划.md](../../discussions/2026-08-17-v095方向审查-验证滞后于抽象与应用层产品化规划.md).

> **三问跟踪表 (2026-08-18 落地, 方向审查决策 3 — 验证欠债显式化, 度量什么就会推进什么)**: 与 README.md §当前状态 同步维护, 像缺失清单一样逐条更新.
>
> | # | 科学问题 | 当前证据 | 目标 | 状态 |
> |---|---------|---------|------|------|
> | ① | **Twin 是否准确？** | 3 测试用户 (lbc001/002/003), 1 学科 (Python), 5D 均非零 + H3-c4 fingerprint | 小规模试点 5-10 学生 (lbc004+) + H1 数据收集方案 | 🔴 未规模验证 |
> | ② | **Policy 是否有效？** | H3 真 A/B 3-way 通过 (v0.86), 小样本 | 试点内 Policy AB 对照, 复现 H3 | 🟡 通过未复现 |
> | ③ | **是否具有长期增益？** | LearningDNA 仍"待启用", 无纵向数据 | LearningDNA ≥50 题启用 + 3 年数据护城河积累 | 🔴 未启动 |

> **[v0.87.0 完成 2026-08-11]**: 缺失清单 3→1 (Motivation Profile / POMDP Policy 全部落地). Phase 6+ Kernel 扩展第 2 个版本 4 sub-commit 全部完成 (a=Motivation schema/b=Motivation Runtime+c=POMDP 雏形/d=POMDP 集成 3-way A/B). pytest 898 → 958 (+60, +6.7%).

> **[v0.83.0 更新 2026-08-10]**: Evidence Engine + Runtime API 100% 落地. 4 sub-commits a/b/c/d. 63 新增 tests (15+14+16+18, pytest 673 → 736, +9.4%). 详情见 §1.4/§1.5/§5.
> - Evidence Engine 100% (统一 schema + 6 来源 + 跨 3 表 CRUD + Belief 关联)
> - Belief-Evidence 关联 100% (add_evidence / evidence_for / evidence_summary, 防御性自检 [8] 扩展 add_evidence allowlist)
> - Evaluation Engine 100% (TwinAttribution + PolicyABTest + GoalCompletion, 3 evaluator 纯函数 0 mutation)
> - Runtime API 100% (6 核心纯函数 estimate / update_belief / replay / evaluate / simulate / plan + kwargs 注入)
>
> v0.83 是 4 kernel-deepening 版本的第 4 个 (per 12-kernel-mapping §8.3, Bisen 2026-08-06 拍板 Kernel-first). 4 kernel-deepening 版本全部完成. 下一阶段 v0.84+: Plugin SDK (kernel-mapping §6) + LearningEvent unification (§2.4) + Event Bus / EventLog retention (§1.2 收尾).

> **[v0.84.0 更新 2026-08-11]**: Event Engine 100% + Event 统一输入 95% + Plugin SDK 10% 落地. 4 sub-commits a/b/c/d. 56 新增 tests (19+15+11+11, pytest 736 → 792, +7.6%). 详情见 §1.2/§2.4/§4.5/§6.
> - LearningEventType enum (7 值) + 3 factory methods (from_observation / from_calibration_message / from_response_submitted) + CalibrationMessage.to_learning_event
> - FeatureExtractor / DualAgentOrchestrator 接受 optional event_log 注入 (双写 event_log)
> - EventBus (in-process pub/sub, sync 模式, 默认 singleton) + retention policy (max_per_student cap + retention_days purge + auto_prune_on_log)
> - PluginRuntime 包装 Runtime API 作为 EventBus subscriber, /api/answer 改造为 "produce event → bus → Runtime subscriber → Runtime.update_belief"
> - 防御性自检 [8] 仍 hard block. H3-c4 + v0.81 replay canary 全 PASS
>
> v0.84 是 5 kernel-deepening 版本的第 1 个 (per 12-kernel-mapping §8.3, Bisen 2026-08-06 拍板 Kernel-first). 下一阶段 v0.85+: Plugin SDK 全量 (剩 /api/judge / /api/dual_agent / /api/lca) + Runtime 订阅 EventBus (Runtime API 改 event-driven) + frontend 接入 hint/idle/goal_changed/reflection_completed 4 个 event_type + 跨学科扩展 (Phase 7+ 推迟).

> **[v0.85.0 更新 2026-08-11]**: Plugin SDK 100% + Event 统一输入 100% + Runtime event-driven 50% 落地. 4 sub-commits a/b/c/d. 44 新增 tests (10+11+10+13, pytest 792 → 836, +5.6%). 详情见 §1.2/§2.4/§4.5/§6.
> - Plugin SDK 100% (4/4 endpoint 全走 Plugin path: /api/answer /judge/dual_agent/lca + Flask startup production activation via plugin_runtime.start())
> - Event 统一输入 100% (10 event_type + 8 factory methods + 4 frontend stub endpoint: hint/idle/goal_change/reflection)
> - Runtime event-driven 50% (3 subscriber 接 plugin path: response_submitted / request_calibration / request_intervention)
> - PluginRuntime 接受 dual_orchestrator_factory + lca_engine_factory kwarg, 委托 Runtime API (Runtime.update_belief / orchestrator.process_observation / Runtime.plan)
> - 防御性自检 [8] 仍 hard block. H3-c4 + v0.81 replay canary 全 PASS
>
> v0.85 是 6 kernel-deepening 版本的第 2 个 (per 12-kernel-mapping §8.3, Bisen 2026-08-06 拍板 Kernel-first). Plugin SDK 架构全部走通 (production activation). 下一阶段 v0.86+: Phase 6+ Kernel 扩展 (Goal Ontology / Twin 一致性保证 / Thompson Sampling / POMDP Policy) + Phase 7+ 抽象推演 (Twin → Human Twin + Multi-Domain + Plugin SDK 文档化).

> **[v0.86.0 更新 2026-08-11]**: Phase 6+ Kernel 扩展第 1 个版本. 4 sub-commits a/b/c/d. 62 新增 tests (18+14+16+14, pytest 836 → 898, +7.4%). 详情见 §1.3/§2.1/§2.3/§5.
> - Goal Ontology §2.3 100% (Capability → Objective → Metric → Evidence, 5 Python 默认 Capability)
> - Twin Consistency Check §2.1 100% (5 规则 + Runtime.plan 触发, goal_changed event 集成)
> - Thompson Sampling §1.3 95% (Beta-Bernoulli Bandit, LinUCB 同接口, policy_type 切换)
> - True A/B Test: LinUCB vs Thompson replay (5% winner 阈值 + 5 样本最小)
> - Runtime API Goal-aware: plan_goal_aware 新 API + evaluate 接受 Goal 对象
> - 防御性自检 [8] 仍 hard block (append_goal/remove_goal/Checker/Thompson/Runtime 0 新 mutation site)
> - H3-c4 + v0.81 replay canary 全 PASS
>
> v0.86 是 Phase 6+ Kernel 扩展第 1 个版本 (4 sub-commit a/b/c/d). 下一阶段 v0.87+: POMDP Policy (部分可观测 MDP) + Motivation Profile (X 维度从 5D 抽出) + Phase 7+ 抽象推演 (Twin → Human Twin + Multi-Domain + Plugin SDK 文档化).

> **[v0.87.0 更新 2026-08-11]**: Phase 6+ Kernel 扩展第 2 个版本. 4 sub-commits a/b/c/d. 60 新增 tests (16+14+16+14, pytest 898 → 958, +6.7%). 详情见 §1.3/§2.1/§5.
> - Motivation Profile §2.1 0% → 100% (X 维度抽出, 独立 4 维时序 frustration/engagement/confidence/recent_trajectory, X 字段保留向后兼容)
> - POMDP Policy §1.3 0% → 100% (4 状态 Engaged/Frustrated/Bored/Confused + Bayesian belief inference + Bayes rule update)
> - 真 A/B Test 3-way: linucb / thompson / pomdp 任意 2-way 对比 (PolicyABTest 4-policy 支持)
> - LCAPolicyLearner policy_type 3 值: linucb / thompson / pomdp (3 Policy 接口同构)
> - Runtime.plan_motivation_aware 新 API (motivation_observation emit + state.motivation fallback)
> - Evaluator.motivation_reward_adjustment: factor 0.7/0.8/1.0/1.3 (frustration / engagement / confidence+engagement / default)
> - ExperimentDesigner motivation-aware 候选池: frustration → EXPLANATORY, engagement → INQUIRY, confidence+engagement → PRACTICE
> - 防御性自检 [8] 仍 hard block (add_motivation_observation / LCAPolicyLearner POMDP 路径 / Runtime API 0 新 mutation site)
> - H3-c4 + v0.81 replay canary 全 PASS
>
> v0.87 是 Phase 6+ Kernel 扩展第 2 个版本 (4 sub-commit a/b/c/d). 缺失清单 3→1 (剩 Multi-Domain 扩展). 下一阶段 v0.88+: Multi-Domain 扩展 (科研 / 职业 / 创意) + POMDP 完整 (T(s'|s,a) + R(s,a) + point-based solver) + Phase 7+ 抽象推演.

> **[v0.88.0-a 更新 2026-08-11]**: Phase 7+ 抽象推演 #1 sub-version a 完成. Domain 抽象层奠基. 27 新增 tests (pytest 958 → 985, +2.8%). 详情见 §3.1 (NEW).
> **[v0.88.0-b 更新 2026-08-11]**: Phase 7+ 抽象推演 #1 sub-version b 完成. Multi-Domain 集成 (DomainExtension + Runtime + LCA + Evaluator). 26 新增 tests (pytest 985 → 1011, +2.7%). 详情见 §3.1.
> - NEW `ecos/domain/{__init__,base,education,science,career}.py` 5 文件 (Domain ABC + 3 Domain + DomainRegistry)
> - Domain ABC: 4 abstract property (name / description / capability_ontology / profile_extensions)
> - EducationDomain: K12, 5 Python default capability (复用 v0.86.0-d DEFAULT_CAPABILITIES_LIST) + grade_levels + learning_standards
> - ScienceDomain: 3 capability (hypothesis/experiment/analysis) + research_methods + domain_categories
> - CareerDomain: 3 capability (skill/portfolio/certification) + vocational_tracks + certification_levels
> - DomainRegistry singleton: register / get / list_names / has / clear (单进程 1 份, 测试可隔离)
> - `register_default_domains(registry=None)` helper: 注册 3 个 Domain (idempotent, 同 name 覆盖)
> - Domain-agnostic Kernel 不变 (LinUCB / Thompson / POMDP / Evidence / Runtime 都不引用 Domain)
> - Domain-specific Extension N 套 (3 个 Domain 各有独立 capability + profile_extensions)
> - 防御性自检 [8] 仍 hard block (Domain dataclass 不 mutate state). capability_ontology / profile_extensions 返 copy (防止外部 mutation)
> - H3-c4 + v0.81 replay canary 全 PASS

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
