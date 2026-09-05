# built≠wired 全量接线审计报告（2026-09-05）

> **触发**：恢复期 backlog P0 #1（[README §下一步](../README.md) / [discussions/2026-09-05 §二](../discussions/2026-09-05-CogMirror迁移适用性分析-与built-unwired接线审计.md)）
> **工具**：`scripts/wiring_audit.py`（AST 名字级初筛 + 人工复核，保留可复跑）
> **范围**：`ecos/` 全部 715 个函数/方法定义；引用语料 = 产品路径（ecos/ + web/）+ 辅助（tests/ + examples/ + scripts/）；prototypes/ 归档不计入
> **性质**：一次性审计登记，不改变任何行为

---

## 一、结果总览

| 层 | 数量 | 占比 | 定义 |
|---|---|---|---|
| **Tier A 死代码候选** | 47 | 6.6% | 全仓零引用（含测试），非 `__all__` 导出 |
| **Tier B 产品路径未接线** | 72 | 10.1% | 仅 tests/examples 引用（其中 12 项是 `__all__` 导出的 SDK API） |
| **产品路径已接线** | ~596 | 83.4% | ecos/ + web/ 内有真实调用 |
| **孤儿实例属性** | 2 | — | 实例化后本模块无任何再引用（含构造器注入检查） |

## 二、复核方法与误报三型（方法论记录）

初筛结果经过人工复核，修正了三种误报模式——后续复跑或升格为常驻自检时必须内置：

1. **构造器注入**：`self.l2 = BiFactorMIRT5D()` 后以 `InferenceEngine(l2=self.l2, ...)` 注入——属性本身零方法调用但已接线（belief_engine.py:216-217、orchestrator.py:102 均属此类）。修正：孤儿判定改为"出现次数 == 赋值目标次数"。
2. **懒加载 property**：`self._perception_critic = None` + `@property` 内延迟构造（inference_engine.py:165-177）。修正：property 模式直接豁免。
3. **`__getattr__` 转发 + 存在性断言**：`LCAEngine._FORWARDED_PLANNER_ATTRS` 转发 `bjork_spacing`/`ca_scaffolding`（lca/orchestrator.py:236-253），tests 断言 `planner.bjork_spacing is not None`（test_planner.py:75-76）——**测试绿灯但全仓零方法调用**。这是"测试覆盖了属性存在、而非行为接线"的典型案例，无法用静态规则完全消除，只能人工判读。

另确认：`ecos/` 内 `getattr(...)` 动态分发仅 8 处且均为属性兜底（`getattr(usage, "prompt_tokens", 0)` 型）或已识别的 `__getattr__` 转发，对 Tier A 名单无救活性影响。

## 三、Tier A 人工复核分类（47 项全清单）

### A. 引擎能力未接线（有产品语义，恢复期需决策接线或显式降级）— 14 项

| 位置 | 方法 | 说明 |
|---|---|---|
| `cta/l1_evolution.py:149` | `BKTEvolutionLayer.apply_decay` | **已知实例 #1**。Ebbinghaus 衰减，零调用 |
| `cta/l1_evolution.py:146,161,166` | `get_model` / `reset_skill` / `all_skills` | BKT 管理面整面死代码 |
| `cta/l1_evolution.py:112` | `BKTModel.accuracy` | 同上 |
| `lca/l3_selection/bjork/spacing.py:45` | `BjorkSpacingEffect.get_review_schedule` | **已知实例 #2**。复习时机判定，零调用 |
| `lca/l3_selection/ca/scaffolding.py:46` | `CAScaffoldingDecay.update_scaffolding_level` | **新发现**：脚手架衰减，零调用（与 spacing 同为 planner 孤儿属性，见 §四） |
| `lca/l3_selection/clt/adaptive_4level.py:98,106` | `get_persisted_level` / `generate_presentation` | CLT 自适应呈现生成死代码（`student_clt_level` 状态读取已接线） |
| `cta/llm_critic/explanation.py:101` | `ExplanationCritic.explain` | **LLM critic 解释能力从未被调用** |
| `evidence/evidence_engine.py:175,323` | `query_by_id` / `attach_to_belief` | Evidence 查询/关联 API 零调用 |
| `cta/belief_state.py:365` | `BeliefState.confidence_vector` | 5D confidence 向量属性零使用 |
| `dual_agent/calibration.py:431` | `StudentCalibrationTracker.get_state` | 校准器状态导出零调用 |

### B. persistence 写/读路径未接线（与已知实例 #3 同族，随 v0.97 家长端统一处理）— 10 项

| 位置 | 方法 | 说明 |
|---|---|---|
| `persistence/db.py:519,573` | `save_intervention` / `load_intervention_history` | 干预历史持久化零调用 |
| `persistence/db.py:587` | `save_evidence` | **重复死路径**：EvidenceEngine 有自己的 evidence_log 写入；此 Database 级方法零调用 |
| `persistence/db.py:831,873` | `save_bloom_goal` / `load_bloom_goals` | Bloom 目标持久化零调用 |
| `persistence/db.py:930` | `load_trajectory_snapshots` | 与"答题流不落 trajectory_snapshots 表"（kernel-mapping §1.4）互为因果——写入端在但读出端死 |
| `persistence/dual_agent_store.py:316`、`lca_store.py:372` | `get_all_students_with_*_state` | 全学生状态扫描零调用（教师端 roster 走的是别的路径） |
| `persistence/plugin_registry_store.py:246,268` | `delete_plugin` / `set_enabled` | store 级生命周期方法零调用；docs/plugin_library.md §六声称的"注册生命周期"实际只有 registry 级 + examples 覆盖 |

### C. 协议/诊断类（需处置决策）— 6 项

| 位置 | 方法 | 说明 |
|---|---|---|
| `dual_agent/protocol/version.py:17,22` | `VersionCompatibility.is_compatible` / `negotiate` | 协议版本协商机制从未使用 |
| `lca/l4_optimization/pomdp_solver.py:245` | `PBVI.get_alpha_stats` | 求解器诊断零调用 |
| `lca/l4_optimization/policy_learner.py:342` | `LCAPolicyLearner.get_penalty_counts` | 惩罚计数诊断零调用 |
| `cta/llm_critic/schemas.py:51` | `PerceptionOutput.is_correct` | 属性零读取 |
| `session/chunk_isolation.py:40` | `ChunkIsolation.current_chunk_index` | 零调用 |

### D. SDK 便利方法（合法保留，待消费方）— 17 项

Bloom 学科库访问器（`get_goals_by_topic` ×3 / `all_entries` ×3 / `next_up` / `all_topic_ids`）、Misconception 库过滤器（`filter_by_skill` / `filter_by_category` / `all_entries` ×3 / `all_categories`）、ThresholdConcepts（`all_entries` / `all_tc_ids`）、`BiFactorMIRT5D.register_items_bulk`。这些是 pip 包 + Plugin SDK 的公开表面，仓库内无 caller 属正常设计（多学科扩展时的接入面）。

## 四、孤儿实例属性（2 项，均已确认真死）

```python
# ecos/lca/planner.py:130-131
self.bjork_spacing = BjorkSpacingEffect()        # 实例化后全仓零方法调用
self.ca_scaffolding = CAScaffoldingDecay(...)    # 同上
```

planner.py 模块 docstring「Step 4: Bjork 触发判定 (BjorkTestingEffect + BjorkSpacingEffect)」**半真**：`bjork_testing` 已接线，`bjork_spacing` 从未参与判定。两者经 `LCAEngine._FORWARDED_PLANNER_ATTRS` 转发暴露、被 `test_planner.py:75-76` 存在性断言覆盖，但行为层面从未进入选择链路。

**已知实例 #2 由此扩大**：L3 选择层两个效应对象（间隔效应 + 脚手架衰减）均为纸面能力。

## 五、Tier B 定性（72 项，不逐项登记）

Tier B = "kernel 跑在应用前面"的量化。分包统计：l4_optimization 8 / goal.ontology 7 / belief_state+event_log 各 5 / domain.base 5 / plugins.registry 5 / event.bus 4 / db 4 / belief_engine 3 / runtime.api 3 / 其余 23 项分散。

其中 12 项为 `__all__` 导出的 SDK API（产品路径未接、测试已覆盖）：

- **Runtime plan API 3 个**：`plan_motivation_aware` / `plan_domain_aware` / `plan_human_feedback_aware`（plan_action_aware 同类）
- singleton 重置工具 4 个：`reset_default_bus` / `reset_default_ontology` / `reset_default_registry` / `reset_default_checker`
- metrics 2 个：`reliability_diagram_data` / `binary_calibration`（ECE 的伴生指标，验证线工具）
- domain 注册 2 个 + `uniform_belief_points` 1 个

这一层**不建议处置**——它们是 SDK 完整度的组成部分（与 v0.96 kernel-mapping「kernel 模块 100% ≠ web 答题流接入」的已知结论一致），但数量本身是"应用层消费滞后"的度量，值得在 v0.97+ 每版本跟踪趋势。

## 六、处置建议

| 类别 | 处置 | 时机 |
|---|---|---|
| A 类（引擎能力） | `bjork_spacing`/`ca_scaffolding`/`apply_decay` 接线——前置：BKT/l1 持久化决策 + 无状态衰减视图（防复合衰减）；`ExplanationCritic.explain` 等接线或显式降级标注 | 黄金回归基建（P1）之后，防止接线行为无基线可判 |
| B 类（persistence） | 随 v0.97 家长端接线（家长透明化 = Evidence/Event 注入触发条件，kernel-mapping §1.4 已预留注入点）；`save_evidence` 重复路径接线时顺带收口或删除 | v0.97 |
| C 类（协议/诊断） | 逐项决策：`VersionCompatibility` 若 dual_agent 协议无演进计划可删；诊断类保留（观测成本为零） | 恢复期顺手 |
| D 类（SDK 表面） | 保留不动 | — |
| Tier B 72 项 | 不处置，按版本跟踪数量趋势 | 每版本 |

**是否升格防御自检第 9 项**：本次 Tier A 误报率极低（名字级零引用 + 无字符串分发），但§二的三型误报（尤其存在性断言）无法静态消除。建议：**暂不升格常驻 hook**，恢复期每版本手工跑一次 `python scripts/wiring_audit.py` 对比差集（新增 Tier A 项需在 commit 中说明），试点稳定后再评估。

## 七、对已知三项清单的更新

- 实例 #1（apply_decay）→ **扩大**为 BKTEvolutionLayer 管理面 5 方法整面死代码
- 实例 #2（BjorkSpacingEffect）→ **扩大**为 L3 两个效应对象（+ CAScaffoldingDecay），且发现"存在性断言测试掩盖"模式
- 实例 #3（Evidence/Event 未注入答题流）→ **同族扩大**：6 个 db.py 写/读方法 + 2 个 store 扫描方法与之互为因果
