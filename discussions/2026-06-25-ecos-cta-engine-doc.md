# 2026-06-25 · CTA 信念引擎工程文档（v0.10.0，工程层第 1 份）

## 主题

完成工程层第 1 份文档 `research/10-engineering/01-cta-belief-engine.md`（v1.0，1409 行），基于 v0.3.0 数学基础 + v0.5.0 C 维度内容库实现 CTA 5 层数学栈的工程实现。

## 日期

2026-06-25

## 背景

战略层 4 份全部完成（v0.9.0）后，进入工程层 5 份。CTA 信念引擎是双 Agent 架构核心——基于 v0.3.0 数学基础（5 层数学栈）+ v0.5.0 C 维度内容库（TC + Misconceptions）+ 02-architecture.md §5 实现。

## 文档结构（14 章节）

| 章节 | 内容 |
|---|---|
| §0 | 模块定位 + 与其他模块接口 |
| §1 | 整体架构（5 层 + 模块目录 + 接口契约）|
| §2 | BeliefState 数据结构（含 C 维度扩展）|
| §3 | L0 POMDP（EKF + 离散精确推断）|
| §4 | L1 BKT + Spaced Repetition（FSRS）|
| §5 | L2 MIRT（5D 非补偿 Bi-factor）|
| §6 | L3 CD-CAT（GDINA + PWKL + Q 矩阵扩展）|
| §7 | L4 Causal（A/B + T-test + Causal Forest 占位）|
| §8 | C 维度内容库（Misconception + TC 集成）|
| §9 | LLM Critic 边界（感知层 + 解释层 + 3 类 prompt）|
| §10 | CTA 主流程编排（7 步骤）|
| §11 | 测试策略（覆盖率 + 集成 + 评估指标）|
| §12 | MVP 范围（16 个组件状态）|
| §13-14 | 关联文档 + 版本维护 |

## 核心工程实现

### 1. 完整 Python 类设计

13 个子目录：
- `l0_pomdp/` — POMDP 框架（EKF + 离散精确推断）
- `l1_evolution/` — BKT + 间隔效应
- `l2_mirt/` — 5D 非补偿 Bi-factor
- `l3_cdcat/` — GDINA + PWKL
- `l4_causal/` — A/B test（MVP）+ Causal Forest（Phase 5+）
- `content/` — TC + Misconceptions 双库
- `llm_critic/` — 感知 + 解释 + prompt 库
- `orchestrator.py` — 主流程

### 2. 完整 BeliefState 数据结构

```python
@dataclass
class BeliefState:
    # 5D 核心状态
    K, P, S, C, X: DimensionState
    # 信念分布
    theta_mean: np.ndarray  # 5D 联合均值
    theta_cov: np.ndarray   # 5D 联合协方差
    # 第二维坐标
    bloom_profile: BloomProfileState
    # 学习者特征
    learning_dna: LearningDNAState
    # 时间维度
    trajectory: TrajectoryState
    # 整体置信度
    overall_confidence: float
```

### 3. C 维度 v0.5.0 扩展

- **MisconceptionHit**：单次命中（misc_id + 置信度 + 触发题目 + 修正策略）
- **TCState**：TC 状态（pre_liminal / liminal / post_liminal + 不可逆性）
- **C 维度更新**：misconception 折扣 0.7 + TC post-liminal 不可逆

### 4. LLM Critic 硬底线

- ✅ 感知层（自然语言 → 结构化）
- ✅ 解释层（统计值 → 自然语言）
- ✅ Misconception 检测（LLM + 关键词混合）
- ❌ **数学层 L0-L2 不用 LLM**

### 5. MVP 范围（16 个组件）

✅ 16 个组件（MVP 全部）—— 包含 L0 EKF + L1 BKT + L2 MIRT + L3 GDINA + L4 A/B + 内容库 + LLM Critic 3 层
❌ POMCP / DKT / Causal Forest（Phase 5+）

## 关键决策

| 决策 | MVP 选择 |
|---|---|
| L0 POMDP 求解 | EKF + 离散属性精确推断（避免 POMCP 太重）|
| L2 MIRT 结构 | Bi-factor 非补偿 5D + 1 一般维度（避免"伪掌握"）|
| L3 CD-CAT 算法 | GDINA + PWKL（DINA 最一般化）|
| L4 因果归因 | 单变量 A/B + T-test（MVP 简化）|
| Misconception 检测 | LLM + 关键词混合 |
| TC 检测 | 启发式 + 元认知信号（MVP 简化）|

## 测试策略

| 模块 | 目标覆盖率 | 关键指标 |
|---|---|---|
| L0 POMDP | ≥ 90% | EKF 准确性 |
| L1 BKT | ≥ 90% | 更新规则数学正确性 |
| L2 MIRT | ≥ 85% | EM 收敛 |
| L3 CD-CAT | ≥ 85% | PWKL 选题最优性 |
| Content | ≥ 80% | Misc F1 ≥ 0.7 / TC F1 ≥ 0.6 |
| LLM Critic | ≥ 70% | JSON 解析正确性 |

## 产出文件

| 文件 | 角色 | 行数 |
|---|---|---|
| `research/10-engineering/01-cta-belief-engine.md` | **主文档**——CTA 信念引擎工程实现（v1.0，14 章节）| 1409 |
| `discussions/2026-06-25-ecos-cta-engine-doc.md` | **本文件**——本次会话简要记录 | ~140 |
| `CHANGELOG.md` | 升级到 v0.10.0 | — |

## 关联文档

- [README.md](../../README.md) — ECOS 项目入口
- [CHANGELOG.md](../../CHANGELOG.md) — 变更日志（v0.10.0）
- [research/10-engineering/01-cta-belief-engine.md](../../research/10-engineering/01-cta-belief-engine.md) — 本次主产出
- [research/30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md](../../research/30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md) — v0.3.0 CTA 数学基础（理论依据）
- [research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md](../../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md) — v0.5.0 C 维度内容库（C 维度整合依据）
- [research/00-overview/02-architecture.md §5](../../research/00-overview/02-architecture.md) — 状态估计工程架构

## 下一步

工程层剩余 4 份：
- **02-lca-policy-engine.md**（LCA 策略引擎）—— CTA 的下游消费者
- **03-bloom-goal-library.md**（Bloom 目标库）—— CTA 状态映射
- **04-dual-agent-calibration.md**（双 Agent 互校）—— CTA + LCA 接口契约
- **05-persistence-session.md**（持久化）—— CTA 状态存储

待 5 份工程文档完成后，工程层 100% 完成。

---

**创建日期**：2026-06-25
**维护者**：Bisen & Claude
**版本**：v0.10.0（工程层第 1 份）
