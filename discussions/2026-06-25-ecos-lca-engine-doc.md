# 2026-06-25 · LCA 策略引擎工程文档（v0.11.0，工程层第 2 份）

## 主题

完成工程层第 2 份文档 `research/10-engineering/02-lca-policy-engine.md`（v1.0，1125 行），基于 v0.4.0 LCA 教学法基础（3 大理论群）+ 02-architecture.md §6 实现 LCA L3-L4 教学法栈的工程实现。

## 日期

2026-06-25

## 背景

工程层第 2 份——LCA 是双 Agent 架构的"改变学生"组件。基于 [v0.4.0 LCA 教学法基础](../../research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md)（CLT + Bjork 四件套 + Cognitive Apprenticeship 6 阶段）+ 02-architecture.md §6 + [01-cta-belief-engine.md](../../research/10-engineering/01-cta-belief-engine.md) CTA 接口。

## 文档结构（10 章节）

| 章节 | 内容 |
|---|---|
| §0 | 模块定位 + 与 CTA 接口 + 硬底线 |
| §1 | 整体架构（L3-L4 工程映射 + 12 子目录 + 接口契约）|
| §2 | 干预参数化空间（5 类 × 4 参数 + Bloom 目标选择）|
| §3 | L3 干预类型选择层（CLT + Bjork + CA Scaffolding）|
| §4 | L4 策略优化层（CA 状态机 + LinUCB + POMCP + 因果归因）|
| §5 | 可解释性输出（rationale 生成器 + 教师后台）|
| §6 | LCA 主流程编排（8 步骤）|
| §7 | 测试策略（覆盖率 + 集成 + 评估指标）|
| §8 | MVP 范围（11 组件状态表）|
| §9-10 | 关联文档 + 版本维护 |

## 核心工程实现

### 1. 完整 L3-L4 教学法栈

```
L3 干预类型选择层
├── CLT 4 级自适应呈现（expertise reversal）
├── Bjork 测试效应（FSRS）
├── Bjork 间隔效应（FSRS）
├── Bjork 合意困难（Phase 5+）
├── Bjork 交错练习（Phase 5+）
└── CA Scaffolding 衰减

L4 策略优化层
├── Cognitive Apprenticeship 6 阶段状态机
├── Contextual Bandits LinUCB（MVP）
├── POMCP（Phase 5+）
└── 因果归因（与 CTA L4 共享）
```

### 2. 完整 Intervention 数据结构

```python
@dataclass
class Intervention:
    # 基本信息
    intervention_id, student_id, intervention_type
    # 目标
    bloom_target, target_skills, target_misconceptions, target_tcs
    # 参数（v0.4.0 §4.3）
    difficulty, quantity, feedback_density, scaffolding_level
    # 教学法元数据
    clt_level, ca_stage, bjork_triggers
    # 期望输出
    expected_gain, expected_risk
    # 时间
    estimated_duration_sec, created_at
```

### 3. Contextual Bandits LinUCB MVP

```python
class LinUCB:
    # Context：CTA 5D (5) + BloomProfile (6) + LearningDNA (5) = 16 维
    # Arm：Intervention(type, bloom_target, difficulty, ...)
    # Reward：state_delta（CTA 测量的状态变化）
    # 算法：argmax_a (θ_a^T x + α √(x^T A_a^{-1} x))
```

### 4. Cognitive Apprenticeship 6 阶段状态机

- Modeling → Coaching → Scaffolding → Articulation → Reflection → Exploration
- 自动转移规则（基于状态 + 干预历史）
- MVP 实现 Stage 1-3，Phase 5+ 实现 Stage 4-6

### 5. 可解释性输出

- 学生端：100 字以内友好语言
- 教师端：200 字以内教学顾问风格（包含"为什么"+"期望效果"+"可观察行为变化"）
- 家长端：150 字以内教育顾问风格（避免直接干预建议）

## 关键决策

| 决策 | MVP 选择 |
|---|---|
| L3 决策算法 | 规则启发（可解释，不依赖 LLM）|
| L3 CA Stage | Stage 1-3（MVP）/ Stage 4-6（Phase 5+）|
| L4 策略学习 | Contextual Bandits LinUCB（MVP）/ POMCP（Phase 5+）|
| 因果归因 | 与 CTA L4 共享 ABTestAttributor |
| Rationale | LLM 表达层（不污染教学法决策）|

## 硬底线

- ❌ **LLM 不可用于选择干预类型或参数**——任何此类设计都是退路
- ✅ LLM 仅用于 rationale 自然语言生成（表达层）

## 评估指标

| 指标 | 阈值 |
|---|---|
| 教师 rationale 满意度 | ≥ 4/5 |
| 家长接受率 | ≥ 70% |
| 学生干预接受率 | ≥ 60% |
| LinUCB 收敛 | ≤ 50 次交互 |
| rationale 生成延迟 | P95 ≤ 3 秒 |
| 可解释性 vs 性能权衡 | 性能损失 ≤ 10% |

## 产出文件

| 文件 | 角色 | 行数 |
|---|---|---|
| `research/10-engineering/02-lca-policy-engine.md` | **主文档**——LCA 策略引擎（v1.0，10 章节）| 1125 |
| `discussions/2026-06-25-ecos-lca-engine-doc.md` | **本文件**——本次会话简要记录 | ~120 |
| `CHANGELOG.md` | 升级到 v0.11.0 | — |

## 关联文档

- [README.md](../../README.md) — ECOS 项目入口
- [CHANGELOG.md](../../CHANGELOG.md) — 变更日志（v0.11.0）
- [research/10-engineering/01-cta-belief-engine.md](../../research/10-engineering/01-cta-belief-engine.md) — 上份工程文档（CTA 信念引擎）
- [research/10-engineering/02-lca-policy-engine.md](../../research/10-engineering/02-lca-policy-engine.md) — 本次主产出
- [research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md](../../research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md) — v0.4.0 LCA 教学法基础（理论依据）
- [research/00-overview/02-architecture.md §6](../../research/00-overview/02-architecture.md) — 干预策略架构

## 下一步

工程层剩余 3 份：
- **03-bloom-goal-library.md**（Bloom 目标库）—— LCA 的目标坐标系
- **04-dual-agent-calibration.md**（双 Agent 互校）—— CTA ↔ LCA 接口契约
- **05-persistence-session.md**（持久化）—— 干预历史存储

待 5 份工程文档完成后，工程层 100% 完成。

---

**创建日期**：2026-06-25
**维护者**：Bisen & Claude
**版本**：v0.11.0（工程层第 2 份）
