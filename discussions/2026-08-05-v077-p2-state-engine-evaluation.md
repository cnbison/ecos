# P2 评估：State Engine 抽象引入 (v0.71-0.73)

> **日期**：2026-08-05
> **作者**：Mavis (Claude Code)
> **关联**：[11-ecos-2.0-architecture-proposal.md](../research/00-overview/11-ecos-2.0-architecture-proposal.md) | [12-kernel-mapping-current-vs-2.0.md](../research/00-overview/12-kernel-mapping-current-vs-2.0.md) | [v0.75.3 H3-c3 PRD](./2026-08-05-v0753-H3-c3-linucb-decay-PRD.md) | [v0.76 cross-student validation](./2026-08-05-v076-cross-student-fingerprint-validation.md)
> **任务**：#8 P2: 评估 State Engine 抽象引入 (v0.71-0.73)

## 0. 评估结论（TL;DR）

| 项 | 评估结果 |
|---|---|
| **是否引入 State Engine 抽象** | **暂缓引入完整 State Engine，先做最小防御动作** |
| **触发条件是否满足** | 部分满足（H3 已通过 ✓，但 CQRS 违反没反复出现 ✗） |
| **完整重构成本** | 高（15+ 测试文件 + belief_engine.py 556 行 + db.py 890 行 + belief.py 592 行） |
| **完整重构收益** | 边际（LCA 已是 read-only，CQRS 违反仅集中在 DB 恢复路径） |
| **推荐动作** | v0.77 加 `BeliefState.apply_snapshot()` 收口 DB 恢复路径，Phase 6 (v0.78+) 启动完整 State Engine |
| **替代路径** | 直接进 Phase 5 H3-c4 跨 skill 验证 + Phase 6 CTA 4 层拆分（自然时机） |

---

## 1. 背景：为什么现在评估

### 1.1 P2 触发条件回顾

[12-kernel-mapping-current-vs-2.0.md §9.3](../research/00-overview/12-kernel-mapping-current-vs-2.0.md) 定义的 P2 启动条件：

> **触发条件**（满足任一即可启动 P2）：
> - v0.69.0 H3 验证通过（B4 方案有效）
> - 加新功能时反复出现 CQRS 违反 / Event 散落 / Evidence 缺失
>
> **不触发条件**：
> - v0.69.0 H3 验证失败（需回滚或重设计）
> - 现有架构能稳定支持新功能

### 1.2 v0.76 fingerprint 修复的启示

v0.75.3 + v0.76 fingerprint 修复带来一个关键认知：

- v0.69-v0.75 的 LinUCB 调参 / Platt Scaling / 冷启动 fallback 工作都基于"BUG 行为"的 theta 轨迹
- 修复 `_intervention_to_arm` 字典覆盖后，entropy 从 1.145 → 2.546（+122%），3 学生全部通过 H3-c3
- **但架构本身没出问题**：H3-c3 在修复 fingerprint 后直接通过，无需架构改动

这告诉我们：**架构是健壮的，能吸收行为修复**。这意味着 P2 的紧迫性比预期低。

### 1.3 评估任务定义

本评估要回答三个问题：

1. **现状**：CQRS 违反到底在哪些地方？多严重？
2. **成本**：完整 State Engine 重构要动多少代码 + 多少测试？
3. **收益**：引入后能解决什么现在解决不了的问题？

---

## 2. 现状审计：CQRS 违反在哪里

### 2.1 LCA 路径（应 read-only）

**审计方法**：grep `belief_state.*=` 在 ecos/lca/ 全目录

| 文件:行 | 操作 | 类型 | CQRS 违反？ |
|---|---|---|---|
| `lca/orchestrator.py:625` | `k_gap = intervention.difficulty - belief_state.K.mastery_prob` | 读 | ✗ 否（read-only） |
| `lca/l4_optimization/policy_learner.py:221-225` | `belief_state.K.theta` 等 5 维 context 构建 | 读 | ✗ 否（read-only） |
| `lca/l4_optimization/ca_state_machine.py:113,116,132` | `belief_state.K.mastery_prob` / `C.confidence` 条件判定 | 读 | ✗ 否（read-only） |
| `lca/l3_selection/bjork/testing.py:63` | `belief_state.K.mastery_prob > threshold` | 读 | ✗ 否（read-only） |
| `lca/l3_selection/clt/adaptive_4level.py:90` | `belief_state.C.confidence < 0.3` | 读 | ✗ 否（read-only） |
| `lca/rationale/generator.py:87,182-190` | 5 维 theta / mastery 读取生成 rationale | 读 | ✗ 否（read-only） |

**结论**：LCA 路径完全 read-only，**CQRS 原则已事实遵守**。

### 2.2 CTA 路径（Estimator + Mutator 混合）

| 文件:行 | 操作 | 类型 | CQRS 违反？ |
|---|---|---|---|
| `cta/belief_engine.py:267-449` | `BeliefEngine.update()` 整个方法 | 估算 + 写入 | ⚠️ 部分（Estimator + Mutator 混合） |
| `cta/belief_engine.py:361-372` | `dim_state.theta/se/mastery_prob/confidence` 写入 | 写 | ⚠️ 通过 mutation |
| `cta/belief_engine.py:489` | `state.C.confidence = state.C.confidence * 0.7 + ...` | 写 | ⚠️ 通过 mutation |
| `cta/belief_engine.py:521-533` | `state.C.misconception_hits.append(...)` 等 | 写 | ⚠️ 通过 mutation |

**结论**：CTA 内部把 Estimator（算新 theta）和 Mutator（写回 state）混在 `update()` 一个方法里。

**但这不是真正的 CQRS 违反**——CTA 本来就被允许写 Twin。问题只是"职责分离不清"，不是"LCA 偷偷写"。

### 2.3 API / 持久化路径（真正的 CQRS 违反）

| 文件:行 | 操作 | 类型 | CQRS 违反？ |
|---|---|---|---|
| `web/api/belief.py:82` | `state.theta_mean = np.array(theta_list, dtype=float)` | DB 恢复时直接写 | ✅ **是** |
| `web/api/belief.py:97` | `state.theta_cov = np.array(cov_list, dtype=float)` | DB 恢复时直接写 | ✅ **是** |
| `web/api/belief.py:107-114` | `state.bloom_profile.remember/understand/...` 6 个字段 | DB 恢复时直接写 | ✅ **是** |
| `web/api/belief.py:124-126` | `state.learning_dna.input_preference/...` | DB 恢复时直接写 | ✅ **是** |
| `web/api/belief.py:155` | `state.C.tc_states[tc_id] = tc_state` | DB 恢复时直接写 | ✅ **是** |
| `web/api/belief.py:182` | `state.trajectory.snapshots.append(snap)` | DB 恢复时直接写 | ✅ **是** |
| `web/api/belief.py:293-330` | `dim_state.theta/se/mastery_prob/confidence` 5 维重建 | DB 恢复时直接写 | ✅ **是**（最严重，绕过 Engine 重算） |
| `web/api/belief.py:195` | `state.overall_confidence = float(db_conf)` | DB 恢复时直接写 | ✅ **是** |
| `web/api/dual_agent.py:206` | `copied_state.student_id = student_id` | sid 兜底 | ⚠️ 极小（仅 sid） |

**真正的 CQRS 违反集中在 `web/api/belief.py` DB 恢复路径**——为了从 SQLite 反序列化 BeliefState，绕过 BeliefEngine 直接写 state 字段。共 **15+ 处直接 mutation**。

### 2.4 为什么 DB 恢复路径是真正的 CQRS 违反

理想流程（State Engine 引入后）：
```
SQLite JSON → BeliefState.from_dict() → State Engine.validate() → State Engine.commit()
```

当前流程：
```
SQLite JSON → _get_or_create_student() 直接 state.X = value（绕过 Engine）
```

后果：
1. **校验缺失**：DB 数据被污染（如 K.mastery_prob=1.5）也不会被发现
2. **重复逻辑**：`belief_engine.py` 已经在 `update()` 里写了"算 theta + 写 state"逻辑，`belief.py` 又写了"读 DB + 写 state"逻辑——两套独立 mutation 路径
3. **历史包袱**：v0.47.x → v0.65.0 每次加新字段（tc_states / trajectory / learning_dna / theta_cov / mastery_prob_after）都要同步改 belief.py，至少漏过 4 次（CLAUDE.md §防御性自检 [5] 记录）

---

## 3. 成本评估：完整 State Engine 重构要动多少

### 3.1 代码改动估算

| 模块 | 当前行数 | 改动类型 | 估算 |
|---|---|---|---|
| `ecos/cta/belief_engine.py` | 556 | 拆分为 `state_engine.py`（mutation 唯一入口） + `belief_updater.py`（Estimator） | 中（拆分 + 引入 StateEngine 类） |
| `ecos/cta/belief_state.py` | 611 | 加 `apply_snapshot()` / `validate()` 方法 + 保留 to_dict/from_dict | 小（已有 to_dict/from_dict 基础） |
| `ecos/persistence/db.py` | 890 | `save_student_state` / `get_student_state` 改走 StateEngine | 中（接口对接） |
| `web/api/belief.py` | 592 | **大改**：删掉 82-195 行直接 mutation，改调 `state.apply_snapshot(snapshot_dict)` | 大（核心 CQRS 修复） |
| `ecos/dual_agent/orchestrator.py` | 905 | `process_observation` Step 6 改调 StateEngine.commit | 中（一处 mutation 入口替换） |
| 新文件 `ecos/cta/state_engine.py` | 0 | 新建 StateEngine 类（commit / validate / snapshot / diff） | 中（~200 行新代码） |

**总估算**：~1500 行改动（新增 + 修改），其中 ~200 行新代码 + ~1300 行接口对接。

### 3.2 测试影响估算

| 测试文件 | 触及 BeliefEngine/state 数 | 影响 |
|---|---|---|
| `test_dual_agent_persistence.py` | 15 | 高（直接测 DB save/load） |
| `test_dual_agent.py` | 9 | 中（dual_agent 主路径） |
| `test_lca_persistence.py` | 7 | 中（LCA 持久化） |
| `test_partial_credit.py` | 5 | 中（MIRT score 连续值） |
| `test_dual_agent_belief_alignment.py` | 5 | 中 |
| `test_defensive.py` | 4 | 低（5 项自检，不直接动 state） |
| `test_dual_agent_confidence_computation.py` | 4 | 中 |
| `test_dual_agent_strategy_challenge_path.py` | 4 | 中 |
| `test_linucb_penalty_limit.py` | 4 | 低 |
| `test_lca_wired.py` | 4 | 低 |
| `test_v064_mastery_prob_after.py` | 4 | 低 |
| `test_dual_agent_integration.py` | 3 | 中 |
| `test_lca_update_reward_actual_outcome.py` | 3 | 低 |
| `test_linucb_cold_start.py` | 3 | 低 |
| `test_platt_scaler.py` | 3 | 低 |
| `test_cold_start_fallback.py` | 2 | 低 |
| `test_dual_agent_lca_isolation.py` | 2 | 低 |
| `test_v0753_linucb_decay.py` | 1 | 低 |
| `test_v075_difficulty_feature.py` | 1 | 低 |

**总测试**：18 / 30 文件触及 BeliefEngine / state，估算 60-80 测试需要回归验证。

### 3.3 风险

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| DB 恢复路径回归（lbc001/lbc002/lbc003 状态丢失） | 中 | 高（历史数据不可逆） | 分两步：先加 `apply_snapshot()` 让 belief.py 调它，再考虑 StateEngine 类 |
| Platt Scaling 校准失效（theta 轨迹变了） | 低 | 中（v0.72-0.74 校准工作白费） | StateEngine 走 to_dict/from_dict，不改 theta 数值 |
| 245 测试中 60+ 需要改 | 高 | 中（1-2 天工作量） | 分阶段：先加方法，老路径并行，再逐步迁移 |
| LinUCB fingerprint 修复成果回退 | 低 | 高（H3-c3 重新 FAIL） | StateEngine 不动 LinUCB 内部，只改 Twin mutation 路径 |

---

## 4. 收益评估：完整 State Engine 能解决什么

### 4.1 能解决的问题

| 问题 | 现状 | State Engine 后 |
|---|---|---|
| DB 恢复路径绕过 Engine | 15+ 处直接 mutation | 单一 `state.apply_snapshot()` 入口 |
| 字段新增漏恢复（历史 4 次） | 每次加字段要 grep belief.py 同步 | apply_snapshot + from_dict 一处，自动覆盖 |
| State validation 缺失 | K.mastery_prob=1.5 不会被拦截 | StateEngine.validate() 强制范围校验 |
| State diff 工具缺失 | 只有 `state_delta` 标量 | StateEngine.diff(s1, s2) 返回结构化 diff |
| State replay 缺失 | 不能按 Event 序列重放 Twin | StateEngine.replay(events) 重建任意时刻 |

### 4.2 不能解决（或没必要现在解决）的问题

| 问题 | 为什么现在不解决 |
|---|---|
| Event Bus（pub/sub） | 跟 State Engine 解耦，可独立加，不阻塞 P2 |
| Evidence Engine | 真正缺失的是 Evidence schema 统一，不是 mutation 路径 |
| Evaluation Engine 内置 | compute_h3_ece.py 外部脚本就够用，内置收益低 |
| Goal Ontology | Phase 6+ 才需要 |
| CTA 4 层拆分 | 跟 State Engine 解耦，可在 State Engine 之后做 |

### 4.3 边际收益估算

- **现在做**：解决 1 个真问题（DB 恢复 CQRS 违反）+ 4 个潜在问题（validation / diff / replay / 字段新增漏恢复）
- **Phase 6 做**：同样解决这 5 个问题，外加跟 CTA 4 层拆分 / Event Engine 一起设计，避免 2 次大改

**边际收益差**：现在做比 Phase 6 做多解决 0 个问题，但提前 3-6 个月拿到 validation / diff 能力。

---

## 5. v0.76 fingerprint 修复对架构假设的影响

### 5.1 v0.69-v0.75 架构假设是否建立在 BUG 上？

| 假设 | 是否受 fingerprint BUG 影响 | 现在还成立？ |
|---|---|---|
| LinUCB θ@x 预测可用于 V3 confidence | 部分受影响（theta 轨迹基于漏 update 的 A 矩阵） | ✅ 仍成立（修复后 theta 更准） |
| Platt Scaling 用 (raw_V3, actual_outcome) 对训练 | 部分受影响（raw_V3 来自 BUG 状态的 theta） | ✅ 仍成立（修复后 raw_V3 更可信） |
| Cold start fallback 用 CTA baseline 替换 raw V3 | 不受影响（fallback 是基于"arm_pull_counts < 10"判定） | ✅ 仍成立 |
| Per-student LinUCB 隔离（v0.57.0） | 不受影响 | ✅ 仍成立 |
| B4 方案：reward = actual_outcome 而非 state_delta | 不受影响（reward 信号本身没 BUG） | ✅ 仍成立 |
| decay_factor 默认 1.0（v0.75.3） | 不受影响（fingerprint 修复后 decay=1.0 就过 H3-c3） | ✅ 仍成立 |

**结论**：v0.69-v0.75 的架构假设**绝大部分不依赖 BUG 行为**。fingerprint BUG 只影响"theta 数值"，不影响"架构选择"。

### 5.2 这对 P2 决策意味着什么

- 如果 v0.69-v0.75 架构大量建立在 BUG 上 → P2 紧迫，需要重新审视
- 实际情况 → P2 不紧迫，可以按 [12-kernel-mapping §8.3](../research/00-overview/12-kernel-mapping-current-vs-2.0.md) 的优先级走：先 Phase 6 CTA/LCA 4 层拆分（v0.74-0.75），再 State Engine

---

## 6. 替代方案比较

### 6.1 方案 A：完整 State Engine（按 [12-kernel-mapping §1.1]）

| 项 | 评估 |
|---|---|
| 工作量 | ~1500 行 + 60-80 测试回归 |
| 收益 | DB 恢复 CQRS + validation + diff + replay |
| 风险 | 中-高（DB 恢复回归可能丢历史状态） |
| 时序 | 阻塞 Phase 5 H3-c4 + Phase 6 CTA 4 层拆分 |
| 推荐度 | ⭐⭐ |

### 6.2 方案 B：最小防御动作（v0.77 加 apply_snapshot）

```python
# ecos/cta/belief_state.py 新增
class BeliefState:
    def apply_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """从 dict 应用快照（DB 恢复路径单一入口）.
        
        取代 web/api/belief.py 直接 state.X = value 的 15+ 处 mutation.
        所有 DB 恢复必须经过此方法, 等价 to_dict 的逆操作.
        """
        # 复用现有 from_dict 逻辑, 但 in-place 而非构造新对象
        ...

# web/api/belief.py 改造
state.apply_snapshot(db_snapshot)  # 替代 82-195 行的直接 mutation
```

| 项 | 评估 |
|---|---|
| 工作量 | ~150 行（apply_snapshot + belief.py 替换） |
| 收益 | DB 恢复 CQRS + 字段新增不再漏（apply_snapshot 跟 to_dict 一一对应） |
| 风险 | 低（apply_snapshot 走 to_dict 逆运算，数值不变） |
| 时序 | 不阻塞 Phase 5 / Phase 6 |
| 推荐度 | ⭐⭐⭐⭐ |

### 6.3 方案 C：暂不做，等 Phase 6

| 项 | 评估 |
|---|---|
| 工作量 | 0 |
| 收益 | 0（继续累积技术债） |
| 风险 | 中（下次加字段再漏 1 次恢复） |
| 时序 | Phase 6 一起做（v0.78+） |
| 推荐度 | ⭐⭐⭐ |

### 6.4 方案 D：直接进 Phase 5 H3-c4 + Phase 6 CTA 拆分

跳过 P2，直接做 H3-c4 跨 skill 验证（业务价值高）+ Phase 6 CTA 4 层拆分（自然时机引入 State Engine）。

| 项 | 评估 |
|---|---|
| 工作量 | 0（P2 部分） |
| 收益 | 业务推进 + 自然时机做架构 |
| 风险 | 低（H3-c4 是 Phase 5 必做） |
| 时序 | Phase 5 → Phase 6 CTA 拆分时 State Engine 一起做 |
| 推荐度 | ⭐⭐⭐⭐⭐ |

---

## 7. 推荐方案

### 7.1 推荐：方案 B + 方案 D 组合

**短期（v0.77，1-2 天）**：方案 B - 加 `BeliefState.apply_snapshot()` 收口 DB 恢复路径

- 解决最严重的 CQRS 违反（DB 恢复 15+ 处直接 mutation）
- 解决"字段新增漏恢复"历史包袱（apply_snapshot 单一入口）
- 不阻塞 Phase 5 H3-c4
- 风险低（数值不变，只是路径收口）

**中期（Phase 6 v0.78+）**：方案 D - 跟 CTA 4 层拆分一起做完整 State Engine

- 自然时机：CTA 4 层拆分本来就要重写 belief_engine.py
- 一起做避免 2 次大改
- 可以加 validation / diff / replay 完整能力

### 7.2 推荐理由

1. **H3-c3 已通过，P2 不紧迫**：fingerprint 修复后 entropy=2.546，3 学生全过，没有架构压力
2. **v0.69-v0.75 架构没建立在 BUG 上**：fingerprint BUG 只影响 theta 数值，不影响架构选择
3. **LCA 路径已 read-only**：CQRS 已事实遵守，完整 State Engine 边际收益低
4. **DB 恢复路径是唯一真问题**：方案 B 解决这个就够，不必上完整 Engine
5. **Phase 6 是自然时机**：CTA 4 层拆分本来就要动 belief_engine.py，State Engine 一起做避免 2 次大改

### 7.3 不推荐方案 A 的理由

- 工作量大（1500 行 + 60-80 测试回归）
- 边际收益低（LCA 已 read-only，真正问题只在 DB 恢复）
- 阻塞 Phase 5 H3-c4 跨 skill 验证（业务价值更高）
- Phase 6 一起做能避免 2 次大改

---

## 8. 行动清单

### 8.1 短期（v0.77，方案 B）

- [ ] 在 `ecos/cta/belief_state.py` 加 `apply_snapshot(snapshot: Dict) -> None` 方法
- [ ] 在 `web/api/belief.py` 用 `state.apply_snapshot(db_snapshot)` 替代 82-195 行的直接 mutation
- [ ] 加测试 `test_apply_snapshot_restores_all_fields`（覆盖 15+ 字段恢复）
- [ ] 加防御性自检 [6]：DB 恢复路径必须走 apply_snapshot，禁止直接 state.X = value
- [ ] CHANGELOG v0.77 + version bump

### 8.2 中期（Phase 6 v0.78+，方案 D）

- [ ] CTA 4 层拆分（observation_engine / feature_extractor / inference_engine / belief_updater）
- [ ] 引入 `StateEngine` 类（commit / validate / snapshot / diff）
- [ ] `belief_engine.update()` 改调 `StateEngine.commit()` 而非直接 mutation
- [ ] 加 state validation（K.mastery_prob 范围 [0,1] 等）
- [ ] 加 state diff（用于 Evaluation Engine 评估 Twin 变化）

### 8.3 长期（Phase 7+）

- [ ] Event Bus（pub/sub 机制）
- [ ] Event Replay
- [ ] Event Simulation

---

## 9. 关键参考

- [12-kernel-mapping-current-vs-2.0.md §1.1 State Engine](../research/00-overview/12-kernel-mapping-current-vs-2.0.md) - 现状 vs 蓝图映射
- [11-ecos-2.0-architecture-proposal.md §2.2.1 State Engine](../research/00-overview/11-ecos-2.0-architecture-proposal.md) - 2.0 蓝图定义
- [v0.75.3 H3-c3 PRD](./2026-08-05-v0753-H3-c3-linucb-decay-PRD.md) - fingerprint 修复起源
- [v0.76 cross-student validation](./2026-08-05-v076-cross-student-fingerprint-validation.md) - fingerprint 修复普适性
- [CLAUDE.md §防御性自检 [5]](../CLAUDE.md) - DB 恢复 6 关键字段历史包袱

---

**创建日期**：2026-08-05
**维护者**：Mavis (Claude Code)
**下次更新**：v0.77 apply_snapshot 实施时 / Phase 6 CTA 4 层拆分启动时
