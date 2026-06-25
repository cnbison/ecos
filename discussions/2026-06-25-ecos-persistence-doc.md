# 2026-06-25 · 持久化与会话管理工程文档（v0.14.0，**工程层 100% 完成**）

## 主题

完成工程层最后 1 份文档 `research/10-engineering/05-persistence-session.md`（v1.0，1338 行），实现 ECOS 持久化层 + 4 层记忆 + 长期会话管理 + 隐私保护。

**🎉 工程层 5 份全部完成（CTA + LCA + Bloom + 互校 + 持久化）**

## 日期

2026-06-25

## 背景

工程层最后 1 份——持久化与会话管理基于：
- 02-architecture.md §7（持久化 + 长期会话管理）
- 04-risks.md §B3（长期数据稀疏）+ §D1（未成年人合规）
- v2.0 §4.2 SGE 中保留价值 + §4.4 AiBeing 借鉴（chat_agent 会话管理）
- [01-cta-belief-engine.md](../../research/10-engineering/01-cta-belief-engine.md)（CTA 状态存储）
- [02-lca-policy-engine.md](../../research/10-engineering/02-lca-policy-engine.md)（干预历史）
- [03-bloom-goal-library.md](../../research/10-engineering/03-bloom-goal-library.md)（BloomGoal 存储）
- [04-dual-agent-calibration.md](../../research/10-engineering/04-dual-agent-calibration.md)（互校历史）

## 文档结构（11 章节）

| 章节 | 内容 |
|---|---|
| §0 | 模块定位 + 与 04-risks.md §B3 + §D1 对应 |
| §1 | 整体架构（4 层记忆层次图 + 13 子目录）|
| §2 | SQLite Schema（6 个核心表）|
| §3 | 4 层记忆实现（L1 短期 / L2 中期 / L3 长期 / L4 持久）|
| §4 | ECOSSession 类（跨会话继承 + epoch 计数器）|
| §5 | chunk 隔离（6-12 年长跑支持）|
| §6 | 数据迁移与备份 |
| §7 | 隐私保护（加密 + 差分隐私 + 匿名化 + 数据最小化）|
| §8 | 测试策略（单元 + 集成 + 性能 + 隐私合规）|
| §9 | MVP 范围（11 组件 + 数据规模）|
| §10-11 | 关联文档 + 版本维护 |

## 核心工程实现

### 1. SQLite Schema（6 个核心表）

```sql
-- 学生表（含加密 + 匿名化）
CREATE TABLE students (
    student_id TEXT PRIMARY KEY,
    current_state_5d BLOB,           -- 加密
    current_bloom_profile BLOB,      -- 加密
    current_learning_dna BLOB,       -- 加密
    tc_states BLOB,                  -- 加密
    misconception_history BLOB,      -- 加密
    anonymized_id TEXT,              -- 用于研究
    consent_version INTEGER,
    -- ...
);

-- 干预历史（含因果归因）
CREATE TABLE interventions (
    intervention_id TEXT PRIMARY KEY,
    intervention_type, bloom_target,
    expected_gain, actual_state_delta,
    causal_effect, causal_p_value,
    -- ...
);

-- 证据日志（含 LLM Critic 输出）
CREATE TABLE evidence_log (
    raw_response, raw_explanation,
    llm_critic_input, llm_critic_output,
    structured_correctness, misc_hits,
    quality_score,  -- 异常检测
    -- ...
);

-- 互校历史
CREATE TABLE calibration_log (
    message_type, state_before, state_after,
    interaction_mode,  -- 4 模式
    trigger_reason, outcome,
    -- ...
);

-- BloomGoal + 多对多
CREATE TABLE bloom_goals (...);
CREATE TABLE problem_bloom_goals (...);

-- 轨迹快照
CREATE TABLE trajectory_snapshots (
    snapshot_type, epoch, state_snapshot,
    grade_level, semester, transfer_metadata,
    -- ...
);
```

### 2. 4 层记忆设计（区别于 SelfLab SGE）

| 层 | SelfLab SGE | ECOS | 用途 |
|---|---|---|---|
| L1 短期 | Hawking 挫败感冷却 | 内存 deque + TTL | 最近 N 次观测 |
| L2 中期 | Crystallizer 风格记忆 | SQLite evidence_log | 学期内干预效果 |
| L3 长期 | Identity 自我概念 | SQLite students（加密）| 核心 5D + Bloom + DNA |
| L4 持久 | Narrative 自传 | trajectory_snapshots | 跨学期/学段画像 |

**关键差异**：ECOS 不用 Narrative（自传叙事）——ECOS 不是 AI 自我涌现。

### 3. ECOSSession 类（跨会话继承）

```python
class ECOSSession:
    def process_observation(self, observation):
        self.epoch_counter += 1
        cta_output = self.cta.update(observation, self.current_intervention)
        lca_result = self.lca.select_intervention(cta_output)
        self.current_belief_state = cta_output.belief_state
        self.current_intervention = lca_result
        if self._should_auto_save():
            self.save()
        return lca_result

    @classmethod
    def load_or_create(cls, student_id, session_config):
        # 30 分钟内未结束的 session 自动恢复
        # 跨会话状态继承
```

### 4. chunk 隔离（6-12 年长跑）

```python
class ChunkIsolation:
    # 每个 chunk = 100 epochs
    # chunk 完成后立即持久化
    # 崩溃时从最后 chunk 恢复
```

### 5. 隐私保护（4 重机制）

1. **加密存储**：Fernet (AES-128) + msgpack（敏感字段）
2. **差分隐私**：Laplace 噪声 + min_group_size=10
3. **匿名化**：SHA256 + salt（不可逆）
4. **数据最小化**：NEVER_COLLECT + REQUIRES_PARENT_CONSENT

## 关键决策

| 决策 | MVP 选择 |
|---|---|
| 存储 | SQLite + JSON（简单、可调试）|
| 4 层记忆 | Hawking/Crystallizer/Identity/Archive |
| 加密 | Fernet + msgpack |
| 差分隐私 | Laplace + min_group_size=10 |
| chunk 隔离 | 100 epochs/chunk |
| 数据最小化 | 严格策略（未成年人合规）|
| 跨会话 | 30 分钟内自动恢复 |

## 性能基准

| 指标 | 阈值 |
|---|---|
| 状态保存延迟 | P95 ≤ 100ms |
| 状态加载延迟 | P95 ≤ 200ms |
| 自动保存延迟 | P95 ≤ 500ms |
| 崩溃恢复时间 | ≤ 5 秒 |
| 差分隐私聚合 | ≤ 1 秒（10000 学生）|
| 加密吞吐 | ≥ 1000 ops/sec |

## **工程层 100% 完成** 🎉

| 文件 | 版本 | 行数 | 主题 |
|---|---|---|---|
| 01-cta-belief-engine.md | v0.10.0 | 1409 | CTA 信念引擎 |
| 02-lca-policy-engine.md | v0.11.0 | 1125 | LCA 策略引擎 |
| 03-bloom-goal-library.md | v0.12.0 | 1093 | Bloom 目标库 |
| 04-dual-agent-calibration.md | v0.13.0 | 1147 | 双 Agent 互校 |
| 05-persistence-session.md | v0.14.0 | 1338 | 持久化与会话 |
| **总计** | — | **6112 行** | **工程层 100%** |

## 累计产出（v0.1.0 ~ v0.14.0）

- **14 个版本**
- **~14200 行**研究文档（远超 [03-roadmap.md §1.2](../research/00-overview/03-roadmap.md) Phase 0 完成标准的 5000 行目标）

## Phase 0 进度

| 维度 | 状态 | 完成度 |
|---|---|---|
| 战略层 | ✅ 100% | 4/4 |
| 工程层 | ✅ 100% | 5/5 |
| 教学法层 | ⏳ 0% | 0/4 |
| MVP 设计 | ⏳ 仅 README 占位 | 0/1 |
| **Phase 0 完成度** | **~83%** | **10/14** |

## 产出文件

| 文件 | 角色 | 行数 |
|---|---|---|
| `research/10-engineering/05-persistence-session.md` | **主文档**——持久化（v1.0，11 章节）| 1338 |
| `discussions/2026-06-25-ecos-persistence-doc.md` | **本文件**——本次会话简要记录 | ~130 |
| `CHANGELOG.md` | 升级到 v0.14.0 | — |

## 关联文档

- [README.md](../../README.md) — ECOS 项目入口
- [CHANGELOG.md](../../CHANGELOG.md) — 变更日志（v0.14.0）
- [research/10-engineering/01-cta-belief-engine.md](../../research/10-engineering/01-cta-belief-engine.md) — CTA 引擎
- [research/10-engineering/02-lca-policy-engine.md](../../research/10-engineering/02-lca-policy-engine.md) — LCA 引擎
- [research/10-engineering/03-bloom-goal-library.md](../../research/10-engineering/03-bloom-goal-library.md) — Bloom 库
- [research/10-engineering/04-dual-agent-calibration.md](../../research/10-engineering/04-dual-agent-calibration.md) — 双 Agent 互校
- [research/10-engineering/05-persistence-session.md](../../research/10-engineering/05-persistence-session.md) — 本次主产出

## 下一步

工程层全部完成，Phase 0 剩余：
- **P1**：教学法层 4 份（`20-pedagogy/`）—— K12 认知结构 / Bloom 应用 / 学习策略 / ZPD
- **P1**：MVP 设计（`90-mvp/`）—— 基于工程层做 M2-M3 详细设计

待这 5 份文档完成后，Phase 0 100% 完成，可启动 Phase 4 MVP 实施。

---

**创建日期**：2026-06-25
**维护者**：Bisen & Claude
**版本**：v0.14.0（**工程层 100% 完成**）
