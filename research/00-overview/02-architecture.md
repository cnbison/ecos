# ECOS 整体架构（Architecture）

> **版本**：v1.0（2026-06-25）
> **性质**：ECOS 战略层第 2 份文档，**整合 P0 三件套到架构总图**——填补 v2.0 §3 的工程细化 + 教学法基础
> **基于**：[v2.0 深度研究 §3 ECOS 完整架构](../../deep-research/Cognitive-Digital-Twin-Deep-Research.md)、[v0.3.0 CTA 数学基础](../../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md)、[v0.4.0 LCA 教学法基础](../../30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md)、[v0.5.0 C 维度内容库](../../30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md)、[01-applications.md](01-applications.md)
> **后续**：[03-roadmap.md](03-roadmap.md)（阶段划分）、[04-risks.md](04-risks.md)（风险矩阵）
> **维护者**：Bisen & Claude

---

## 0. 架构定位

### 0.1 与 v2.0 深度研究的关系

[v2.0 §3 ECOS 完整架构](../../deep-research/Cognitive-Digital-Twin-Deep-Research.md) 已给出架构骨架：

```
Bloom Goal Space → LCA → CTA → Student
```

**本文档不重复 v2.0 的骨架**，而是**整合 P0 三件套**：

| 整合内容 | 来源 | v2.0 缺口 |
|---|---|---|
| CTA L0-L4 数学栈 | [v0.3.0](../../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md) | §3.3 "只提 IRT/BKT/DKT 名字" |
| LCA L3-L4 教学法栈 | [v0.4.0](../../30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md) | §3.4 "有策略列表无理论论证" |
| C 维度双轨内容库 | [v0.5.0](../../30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md) | §3.3 "C 维度是抽象置信度" |

### 0.2 文档目标读者

- **战略层读者**：理解 ECOS 全貌，决定投资/合作
- **工程层读者**：按本文档实现 `ecos/` Python 包
- **教学法层读者**：理解 L3-L4 教学法决策的工程接口
- **学术研究者**：理解 ECOS 与学术传统的关系

---

## 1. 核心架构总图（P0 三件套整合）

### 1.1 三层视角架构

```
┌────────────────────────────────────────────────────────────────────────┐
│  【顶层】三空间（State + Bloom Goal + Policy）                           │
│                                                                        │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐ │
│  │  State Space     │ ←→ │ Bloom Goal Space │ ←→ │ Policy Space     │ │
│  │  (CTA 维护)      │    │ (LCA 目标坐标系) │    │ (LCA 维护)       │ │
│  │ 5D + BloomProfile│    │ Remember-Create  │    │ 5 类干预 × 4 参数 │ │
│  │ + LearningDNA    │    │ (6 层)           │    │ (20+ 维策略空间)  │ │
│  └────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘ │
└───────────┼───────────────────────┼───────────────────────┼───────────┘
            │                       │                       │
            ▼                       ▼                       ▼
┌────────────────────────────────────────────────────────────────────────┐
│  【中层】双 Agent（CTA + LCA + 互校机制）                                │
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ CTA — Cognitive Twin Agent (State Estimator)                      │  │
│  │ ┌─────────────────────────────────────────────────────────────┐ │  │
│  │ │ L4 因果归因层     Causal Inference（DoWhy + Causal Forest） │ │  │
│  │ │ L3 自适应选择层   CD-CAT（GDINA + PWKL 选题）               │ │  │
│  │ │ L2 状态估计层     MIRT（5D 非补偿多维能力向量）             │ │  │
│  │ │ L1 时间演化层     BKT/DKT + Spaced Repetition               │ │  │
│  │ │ L0 概率框架层     POMDP / HMM                               │ │  │
│  │ └─────────────────────────────────────────────────────────────┘ │  │
│  │ 状态：5D (K/P/S/C/X) + BloomProfile + LearningDNA + Trajectory │  │
│  │ 思维模式：认知科学家 + 心理测量学家（保守、基于证据、维护置信度）│  │
│  └──────────────────────────────┬──────────────────────────────────┘  │
│                                  ↕ 双 Agent 互校循环                    │
│  ┌──────────────────────────────┴──────────────────────────────────┐  │
│  │ LCA — Learning Coach Agent (Policy Optimizer)                   │  │
│  │ ┌─────────────────────────────────────────────────────────────┐ │  │
│  │ │ L4 策略优化层       Cognitive Apprenticeship 6 阶段框架     │ │  │
│  │ │ L3 干预类型选择层   Bjork 四件套 + CLT (4 级自适应呈现)     │ │  │
│  │ └─────────────────────────────────────────────────────────────┘ │  │
│  │ 干预：5 类型 × 4 参数 (difficulty × quantity × feedback × ...)│  │
│  │ 思维模式：教练 + 强化学习策略器（主动、实验、探索、优化）     │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
            ↕
┌────────────────────────────────────────────────────────────────────────┐
│  【底层】内容基础（TC + Misconceptions + Knowledge Ontology）          │
│                                                                        │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐ │
│  │ Threshold        │    │ Misconceptions   │    │ Knowledge        │ │
│  │ Concepts         │    │ Library          │    │ Ontology         │ │
│  │ (Meyer & Land)   │    │ (Driver, Chi)    │    │ (学科本体)       │ │
│  │ MVP: 8 个初中数学 │    │ MVP: 30-50 条    │    │ 数学/物理/...    │ │
│  │ 跨越前 → liminal │    │ trigger + 修正   │    │ Q 矩阵基础       │ │
│  │ → post-liminal   │    │                  │    │                  │ │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘ │
└────────────────────────────────────────────────────────────────────────┘
            ↕
┌────────────────────────────────────────────────────────────────────────┐
│  【接口层】App 层（数据采集 + 干预执行）                                │
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ 数据采集：做题记录 / 答题时间 / 解释文本 / 反思日志 / Agent 使用 │  │
│  │ 干预执行：题目推送 / 讲解视频 / worked example / 测试题         │  │
│  │ 反馈展示：诊断报告 / 学习建议 / 成长轨迹可视化                 │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
            ↕
                         Student
```

### 1.2 关键架构原则

1. **数学层不用 LLM（硬底线）**：CTA L0-L2 是纯统计实现——任何让 LLM 直接生成信念估计的设计都是退路
2. **LLM Critic 边界**：LLM 仅用于感知层（自然语言→结构化）+ 解释层（统计值→自然语言）+ Misconception 检测
3. **双 Agent 解耦**：CTA 通过 POMDP 接口 `(S, A, O, T, R, Ω)` 与 LCA 协作，两者独立可替换
4. **内容库与算法解耦**：TC + Misconceptions 是内容，CTA/LCA 是算法——内容更新不影响算法

---

## 2. 三空间架构

ECOS 的核心数学结构是 **三空间**：State Space（CTA 维护）+ Bloom Goal Space（LCA 目标）+ Policy Space（LCA 维护）。

### 2.1 State Space（状态空间）

**CTA 维护的学生状态完整结构**（整合 [v2.0 §3.3](../../deep-research/Cognitive-Digital-Twin-Deep-Research.md) + [v0.3.0 §1 MIRT](../../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md)）：

```python
class StudentState:
    # 5D 核心状态（v1.0 基础）— MIRT 多维能力向量
    K: KnowledgeState       # 知识掌握 — θ_K ∈ ℝ
    P: ProcedureState       # 程序技能 — θ_P ∈ ℝ
    S: StrategyState        # 策略能力 — θ_S ∈ ℝ
    C: ConfidenceState      # 认知置信度 — θ_C ∈ ℝ（含 misconception 折扣）
    X: ExternalSupportState # 外部支架 — θ_X ∈ ℝ

    # 5D 信念分布（v2.0 新增）
    BeliefDistribution: BeliefState  # 5D 联合分布 N(μ, Σ)
    UncertainEvidence: EvidenceList  # 待补全证据清单

    # BloomProfile（第二维坐标）
    BloomProfile: BloomState         # 6 层认知层级分布
                                   # remember/understand/apply/analyze/evaluate/create

    # 学习者特征
    LearningDNA: LearningDNA         # 5 维个性化特征
                                   # (输入偏好/反馈偏好/疲劳模式/错误模式/动机模式)

    # 时间维度
    GrowthTrajectory: Trajectory     # 跨会话成长轨迹

    # 状态空间元数据
    Confidence: float               # CTA 对当前信念的总体置信度 0-1
    LastUpdated: timestamp          # 上次更新时间
    TCStates: Dict[str, TCState]    # 每个 TC 的 liminal/post-liminal 状态（v0.5.0）
```

**5D × 6 Bloom = 30 维状态空间**——MIRT 提供数学框架（[v0.3.0 §1](../../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md)）。

### 2.2 Bloom Goal Space（目标坐标系）

**6 层认知层级**（[v0.1 综合报告 §第八部分](../../gpt-dialogues/04-cognitive-digital-twin-v01-report.md)）：

| 层 | 名称 | 含义 | K12 例子（数学）|
|---|---|---|---|
| **L1** | Remember | 记忆定义/公式/事实 | 二次函数顶点公式 y = a(x-h)² + k |
| **L2** | Understand | 解释/分类/归纳 | 为什么抛物线开口方向由 a 决定 |
| **L3** | Apply | 应用到新情境 | 用顶点公式求最值 |
| **L4** | Analyze | 分解/比较/识别模式 | 区分"配方求最值"与"导数求最值" |
| **L5** | Evaluate | 评判/辩护/选择 | 选择最优建模方法 |
| **L6** | Create | 综合/设计/创造 | 设计新题型 |

**BloomProfile** 是学生在每个 Bloom 层的掌握度（0-1）。

**目标选择**：LCA 在每次干预时选择**目标 Bloom 层**——不是随机选，而是基于 CTA 状态 + Bloom 跨越路径。

### 2.3 Policy Space（策略空间）

**5 类干预 × 4 参数**（整合 [v0.4.0 §4.3](../../30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md)）：

```
Policy Space = 5 离散类型 × 4 连续参数 + Bloom 层选择
             ≈ 5 × ∞⁴ × 6 = 高维连续 + 离散策略空间
```

| 干预类型 | 含义 | 教学法对应 |
|---|---|---|
| **讲解型** | analogy / worked example / socratic | CLT Modeling + Cognitive Apprenticeship Stage 1 |
| **练习型** | varied practice / deliberate practice | Bjork 测试效应 + 间隔 |
| **探究型** | project-based / inquiry / open task | Cognitive Apprenticeship Stage 6 |
| **反馈型** | immediate / delayed / detailed / sparse | CLT 反馈密度 |
| **元认知型** | self-explanation / reflection / teach-back | Cognitive Apprenticeship Stage 4-5 |

**LCA 的策略选择** = POMDP 的 `π(a|s)`：根据 CTA 状态 `s` 选择干预 `a`。

---

## 3. 双 Agent 详细架构

### 3.1 CTA（Cognitive Twin Agent）— State Estimator

**核心职责**："这个学生现在是谁？卡在哪？" —— 维护 5D 信念分布，不主动干预。

**内部结构（5 层数学栈）**（[v0.3.0 §6 整合](../../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md)）：

```
┌──────────────────────────────────────────────────────────┐
│ L4 因果归因层     Causal Inference（DoWhy + Causal Forest）│
│   ↑                                                  ↑   │
│   │ 接受 LCA 干预反馈，更新干预因果归因                 │   │
│   │                                                  │   │
│ L3 自适应选择层   CD-CAT（GDINA + PWKL 选题）         │   │
│   ↑                                                  ↑   │
│   │ 选下一题 / 下一干预                               │   │
│   │                                                  │   │
│ L2 状态估计层     MIRT（5D 非补偿多维能力向量）       │   │
│   ↑                                                  ↑   │
│   │ 状态联合估计 + Σ_θ 协方差                         │   │
│   │                                                  │   │
│ L1 时间演化层     BKT / DKT + Spaced Repetition       │   │
│   ↑                                                  ↑   │
│   │ P(L_n) 更新 + 间隔效应衰减                        │   │
│   │                                                  │   │
│ L0 概率框架层     POMDP / HMM（信念状态 b(s)）        │   │
│   ↑                                                  ↑   │
│   └─── LLM Critic 边界 ──────────────────────────────┘   │
│        (感知层: 自然语言 → 结构化)                       │
└──────────────────────────────────────────────────────────┘
```

**LLM Critic 边界**（**硬底线**）：
- ✅ LLM 可用：感知层（学生解释文本 → 5D 更新信号）+ 解释层（统计值 → 自然语言报告）+ Misconception 检测
- ❌ LLM 不可用：直接生成 5D 状态估计——任何此类设计都是退路

**C 维度内容库整合**（[v0.5.0](../../30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md)）：

```
CTA 状态更新：
  1. 基础 BKT 更新（5D 整体）
  2. Misconception 检测（LLM Critic）→ C 维度下调 + 标记伪置信
  3. TC 跨越检测 → liminal/post-liminal 状态
  4. POMDP 整合更新
```

### 3.2 LCA（Learning Coach Agent）— Policy Optimizer

**核心职责**："下一步怎么办？如何成长最快？" —— 基于 CTA 状态选择最优干预，主动实验。

**内部结构（L3-L4 教学法栈）**（[v0.4.0 §4 整合](../../30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md)）：

```
┌──────────────────────────────────────────────────────────┐
│ L4 策略优化层     Cognitive Apprenticeship 6 阶段框架     │
│   ↑                                                    ↑   │
│   │ 当前在 Modeling / Coaching / Scaffolding / ...      │   │
│   │                                                    │   │
│ L3 干预类型选择层  Bjork 四件套 + CLT（4 级自适应呈现）  │   │
│   ↑                                                    ↑   │
│   └─── 接受 CTA 信念分布 ──────────────────────────────┘   │
│        (POMDP 接口：状态 b(s) → 策略 π(a|s))              │
└──────────────────────────────────────────────────────────┘
```

**LCA 的关键决策**：
1. **目标 Bloom 层选择**：基于 CTA 5D 状态 + Bloom 跨越路径
2. **干预类型选择**：基于 Cognitive Apprenticeship 6 阶段位置 + Bjork 策略空间
3. **干预参数选择**：基于 CLT 4 级自适应呈现 + LearningDNA 个性化
4. **停止规则**：基于 Mastery Learning 阈值（如 P(L) ≥ 0.8）

### 3.3 双 Agent 互校机制

**核心循环**（整合 [v2.0 §3.5](../../deep-research/Cognitive-Digital-Twin-Deep-Research.md) + POMDP 接口）：

```
┌──────────────────────────────────────────────────────────────────┐
│                    双 Agent 互校循环                               │
├──────────────────────────────────────────────────────────────────┤
│  Step 1: CTA 提出假设                                            │
│    "学生 K=0.4, 程序技能弱 + 二级 misconception"                 │
│                                                                  │
│  Step 2: LCA 设计实验验证                                        │
│    "设计 3 道'读题 → 识别模型'的讲解型 + 练习型"                │
│                                                                  │
│  Step 3: 观察结果（App 层数据采集）                              │
│    "3 道错 2 道，错误集中在分情况讨论"                          │
│                                                                  │
│  Step 4: CTA 更新信念（基于观测）                                │
│    "程序技能 0.35 → 0.30 + 检测到分情况讨论子缺口"               │
│                                                                  │
│  Step 5: LCA 因果归因（L4 Causal Inference）                     │
│    "本次干预对程序技能贡献 -0.05（CATE）"                        │
│                                                                  │
│  Step 6: LCA 重新规划                                            │
│    "切换目标 Bloom 层 + 调整干预类型"                            │
│                                                                  │
│  循环：Step 1 ...                                                │
└──────────────────────────────────────────────────────────────────┘
```

**互校对抗幻觉的 3 个机制**（[v2.0 §3.5](../../deep-research/Cognitive-Digital-Twin-Deep-Research.md)）：
1. **CTA 保守 vs LCA 主动**：CTA 不轻易下结论，LCA 必须用实验验证
2. **CTA 数学严格 vs LCA 教学法灵活**：数学层不容妥协，教学法可调整
3. **L4 因果归因强制**：每个干预效果必须经因果归因（不能仅看相关性）

**互校的 4 个交互模式**（[v2.0 §3.5](../../deep-research/Cognitive-Digital-Twin-Deep-Research.md)）：
- **常态模式**：CTA 估计 → LCA 干预 → 数据反馈
- **冲突模式**：CTA 与 LCA 对学生状态判断分歧（CTA 说"会"，LCA 实验发现"不会"）→ CTA 必须修正
- **学习模式**：LCA 因果归因发现某类干预有效/无效 → 调整策略空间权重
- **发现模式**：CTA 信念更新中发现 TC 跨越 → 触发 liminal 状态处理

---

## 4. 完整数据流（端到端）

### 4.1 数据流伪代码（整合 [v2.0 §3.6](../../deep-research/Cognitive-Digital-Twin-Deep-Research.md)）

```python
# ===== 1. 数据采集（App 层）=====
# 来源：做题记录、答题时间、解释文本、反思日志、Agent 使用记录
observation = app_layer.collect(
    student_id, problem_id, answer, response_time,
    explanation_text, reflection_text
)

# ===== 2. CTA 状态更新（CTA 内部 — 数学层）=====
# LLM Critic 仅在感知层使用
structured_obs = llm_critic.perceive(observation)  # 自然语言 → 结构化

# L0 POMDP 信念预测
b_predicted = cta.pomdp_predict(state_prior, last_action)

# L1 BKT 更新（每个知识点）
for skill in structured_obs.skills_touched:
    p_mastered = cta.bkt_update(skill, structured_obs.correct)

# L2 MIRT 联合估计（5D 状态）
state_theta = cta.mirt_update(b_predicted, structured_obs)

# L5 C 维度内容库整合
for misc_hit in cta.misconception_detector.detect(structured_obs):
    state_theta.C *= 0.7  # 伪置信折扣

for tc_id in structured_obs.tcs_touched:
    if cta.detect_liminal(tc_id, structured_obs):
        cta.tc_states[tc_id] = LiminalState(...)
    elif cta.detect_postliminal(tc_id, structured_obs):
        cta.tc_states[tc_id] = PostliminalState(irreversible=True)

# L3 CD-CAT 选下一题
next_problem = cta.cdcat_select_next(state_theta, available_problems)

# ===== 3. LCA 干预选择（LCA 内部 — 教学法层）=====
# L4 Cognitive Apprenticeship 6 阶段判断
stage = lca.current_stage(cta.tc_states, state_theta)

# L3 Bjork + CLT 干预类型选择
intervention_type = lca.select_intervention_type(
    state_theta, stage, structured_obs
)

# CLT 4 级自适应呈现参数
presentation = lca.clt_adaptive_presentation(
    intervention_type, state_theta, learning_dna
)

# ===== 4. 干预执行（App 层）=====
app_layer.execute(intervention_type, presentation, next_problem)

# ===== 5. 干预效果评估（CTA + LCA 协作）=====
# 等待下一轮观测
new_observation = wait_for_next_observation(student_id)

# CTA 测量状态变化
state_delta = cta.measure_state_change(state_theta, new_state_theta)

# L4 LCA 因果归因（Causal Inference）
causal_effect = lca.causal_forest.estimate(
    treatment=last_intervention,
    outcome=state_delta,
    covariates=state_theta,
    control='natural_maturation_baseline'
)

# ===== 6. 信念更新（CTA 内部 — POMDP）=====
cta.pomdp_update(new_observation, reward=causal_effect.cate)

# ===== 7. 轨迹记录（App 层）=====
app_layer.record_trajectory(
    student_id, timestamp, state_theta, intervention,
    outcome, causal_effect
)
```

### 4.2 数据流时序图

```
Student  ─→  App 层  ─→  CTA 数学层  ─→  LCA 教学法层  ─→  App 层  ─→  Student
   ↑           ↑             ↑                ↑             ↑           │
   │           │             │                │             │           │
   └─── 反馈 ──┴─── 状态 ────┴── 干预决策 ────┴── 推送 ─────┴─── 学习 ───┘
```

每个"回合"约 30 秒-10 分钟（取决于干预类型）。

---

## 5. 状态估计工程实现（CTA）

### 5.1 CTA 5 层数学栈的工程映射

| 层 | 学术方法 | 工程实现 | 开源依赖 |
|---|---|---|---|
| L0 概率框架 | POMDP / HMM | 扩展卡尔曼滤波 + 离散属性精确推断 | `pgmpy`, `pymdp` |
| L1 时间演化 | BKT / DKT | 经典 4 参数 BKT（MVP）+ DKT（Phase 5+）| `pyBKT` |
| L2 状态估计 | MIRT | Bi-factor 非补偿 MIRT | `mirt` (R) 或自研 |
| L3 自适应选择 | CD-CAT | GDINA + PWKL 选题 | `GDINA` (R) 或自研 |
| L4 因果归因 | Causal Inference | DoWhy + Causal Forest | `DoWhy`, `EconML` |
| L0.5 内容库 | TC + Misconceptions | JSON 库 + LLM Critic | 自研 + `pgmpy` |

### 5.2 Q 矩阵扩展（CD-CAT 集成）

每个题目标注：

```python
class ProblemMetadata:
    problem_id: str
    # 题目属性
    attributes: List[str]              # 考察的属性（如 ["二次函数概念", "分情况讨论"]）
    bloom_layer: BloomLevel            # L1-L6
    # v0.5.0 扩展
    threshold_concept: Optional[str]  # 跨越的 TC（如 "函数"）or None
    misconceptions: List[str]          # 触发的 misconception IDs
    # CTA 集成
    mirt_params: MIRTParams            # (a_i, d_i, c_i)
    difficulty: float                  # 0-1
    # LCA 集成
    intervention_types: List[InterventionType]  # 适合的干预类型
    clt_level: CLTLevel                # CLT 呈现级别（1-4）
```

### 5.3 C 维度评估的具体流程（v0.5.0 整合）

```
学生作答 + 解释文本
        ↓
[LLM Critic] 提取结构化信号（correct, time, explanation, reflection）
        ↓
[BKT] 基础 P(L) 更新
        ↓
[Misconception Detector] LLM + 关键词匹配
        ├─ 命中 → C 维度 × 0.7 + 标记 illusory_confidence
        └─ 未命中 → 继续
        ↓
[TC Detector] 启发式 + 元认知信号
        ├─ liminal 信号 → TCState = LiminalState(progress=0.3)
        ├─ post-liminal 质变 → TCState = PostliminalState(irreversible=True)
        └─ 无信号 → 继续
        ↓
[POMDP Update] 整合到 5D 信念分布
        ↓
输出：StudentState.C + tc_states
```

### 5.4 LLM Critic 的精确边界

| 任务 | LLM 可用？ | 理由 |
|---|---|---|
| 学生解释文本 → 结构化（correctness, misconception_flag）| ✅ | 自然语言理解，LLM 适合 |
| Misconception 检测 | ✅ | 需要语义理解，LLM + 关键词混合 |
| 5D 状态数值估计 | ❌ **硬底线** | 数学方法 |
| POMDP 信念更新 | ❌ | 概率推理 |
| BKT 参数学习 | ❌ | 统计推断 |
| 自然语言解释生成（统计值 → 报告）| ✅ | 表达层 |

---

## 6. 干预策略工程实现（LCA）

### 6.1 LCA L3-L4 教学法栈的工程映射

| 层 | 学术方法 | 工程实现 | 开源依赖 |
|---|---|---|---|
| L3 干预类型选择 | CLT + Bjork 四件套 | 规则启发（教学法决策树）| 自研 |
| L3 CLT 4 级呈现 | expertise reversal effect | 模板系统（4 套题目模板）| 自研 |
| L3 Bjork 测试效应 | spaced repetition | FSRS 算法 | `ts-fsrs` 或 `py-fsrs` |
| L3 Bjork 交错练习 | interleaving scheduler | 学科单元内调度 | 自研 |
| L4 6 阶段框架 | Cognitive Apprenticeship | 状态机 + Scaffolding 衰减 | 自研 |
| L4 策略优化 | Contextual Bandits（MVP）/ POMCP（Phase 5+）| LinUCB 或类似算法 | `vowpalwabbit` |

### 6.2 干预参数化空间

```python
class Intervention:
    type: InterventionType  # 5 选 1
    bloom_target: BloomLevel  # 6 选 1
    # 4 连续参数（CLT 4 级自适应）
    difficulty: float         # 0-1，匹配 BloomProfile
    quantity: int             # 1-10，Bjork 测试效应最佳频次
    feedback_density: float   # 0-1，立即 vs 延迟反馈
    scaffolding_level: float # 0-1，expertise reversal 衰减

    # 元数据
    expected_gain: float      # 期望状态改善量
    expected_risk: float      # 期望风险（liminal 状态误判等）
    clt_level: CLTLevel       # CLT 呈现级别 1-4
    cognitive_apprenticeship_stage: CAStage  # 当前 6 阶段位置
```

### 6.3 L4 策略优化（MVP = Contextual Bandits）

**MVP 阶段**：LCA 用 **Contextual Bandits**（[P1.8 待写](../../30-shared-cognitive-tools/theoretical-foundations/README.md)）作为轻量级 RL 框架：

```
状态（context） = CTA 5D + BloomProfile + LearningDNA
动作（arm） = Intervention(type, bloom_target, difficulty, ...)
奖励（reward） = state_delta（P(L) 改善 + BloomProfile 改善）
策略 = LinUCB / Thompson Sampling
```

**Phase 5+**：升级到 POMCP（POMDP 的 MCTS 求解）作为完整 RL 框架。

---

## 7. 持久化与长期会话管理

### 7.1 学生状态持久化

**存储结构**：

```sql
-- 学生核心表
CREATE TABLE students (
    student_id TEXT PRIMARY KEY,
    grade_level INT,
    created_at TIMESTAMP,
    -- 当前状态
    current_state_5d BLOB,           -- MIRT 5D + Σ_θ
    current_bloom_profile BLOB,
    current_learning_dna BLOB,
    -- 内容库状态
    tc_states BLOB,                   -- 每个 TC 的状态
    misconception_history BLOB,       -- 命中的 misconception 历史
    -- 成长轨迹
    trajectory BLOB,                  -- 跨会话轨迹
    -- 元数据
    last_updated TIMESTAMP,
    confidence REAL
);

-- 干预历史表（用于因果归因 + 策略学习）
CREATE TABLE interventions (
    intervention_id TEXT PRIMARY KEY,
    student_id TEXT,
    timestamp TIMESTAMP,
    intervention_type TEXT,
    bloom_target TEXT,
    parameters BLOB,                  -- (difficulty, quantity, feedback_density, ...)
    -- 因果归因结果
    causal_effect REAL,
    cate REAL,                        -- 条件平均处理效应
    outcome_state_delta BLOB
);

-- 证据表（CTA 的 BeliefDistribution 完整记录）
CREATE TABLE evidence_log (
    evidence_id INT PRIMARY KEY AUTOINCREMENT,
    student_id TEXT,
    problem_id TEXT,
    timestamp TIMESTAMP,
    observation BLOB,                 -- 结构化观测
    state_update BLOB,                -- 信念更新
    llm_critic_output BLOB,           -- LLM 感知层输出
    misconception_hits BLOB           -- 命中的 misconception
);
```

### 7.2 长期会话状态管理

**会话边界**：每次 LCA 干预 → 学生完成 → 数据采集 → CTA 更新 构成一个"会话回合"。

**跨会话状态继承**：

```
会话 N 结束：
  CTA.persist(student_state)         # 5D + BloomProfile + LearningDNA + Trajectory
  evidence_log.append(...)            # 追加证据
  trajectory.append(state_snapshot)   # 追加轨迹快照

会话 N+1 开始：
  CTA.load(student_id)                # 加载完整状态
  CTA.restore_belief_distribution()   # 恢复 BeliefDistribution
  evidence_log.load_recent(N)         # 加载最近 N 次证据
  LCA.inherit_trajectory_context()    # LCA 继承轨迹上下文
```

### 7.3 跨学期/学段画像演化（Phase 5+）

**Phase 4（MVP）**：仅学期内（约 4 个月），不跨学期。

**Phase 5+**：跨学期/学段画像演化
- 学期切换：保存完整 Trajectory + LearningDNA 更新
- 学段切换（如初中 → 高中）：BloomProfile 重置到下一学段起点，5D 状态迁移
- 长期衰减：长时间未使用 ECOS，状态按衰减模型更新（避免错误的高置信度）

---

## 8. MVP 架构（Phase 4 实现范围）

### 8.1 MVP 包含的组件

| 组件 | MVP 实现 |
|---|---|
| CTA L0 POMDP | ✅ EKF + 离散属性精确推断（简化版）|
| CTA L1 BKT | ✅ 经典 4 参数 |
| CTA L2 MIRT | ✅ 5D 非补偿 Bi-factor |
| CTA L3 CD-CAT | ✅ GDINA + PWKL 选题 |
| CTA L4 因果归因 | ⚠️ 简化：单变量 A/B + T-test（不实现 Causal Forest）|
| CTA C 维度内容库 | ✅ TC 库 8 个 + Misconceptions 库 30-50 条 + LLM Critic 检测 |
| LCA L3 CLT | ✅ 4 级自适应呈现（4 套模板）|
| LCA L3 Bjork | ✅ 测试效应 + 间隔效应（FSRS）；⚠️ 合意困难 + 交错 Phase 5+ |
| LCA L4 6 阶段 | ✅ Stage 1-3（Modeling/Coaching/Scaffolding）；⚠️ Stage 4-6 Phase 5+ |
| LCA L4 策略优化 | ✅ Contextual Bandits（LinUCB）|
| 持久化 | ✅ SQLite + JSON 序列化 |
| 会话管理 | ✅ 学期内；⚠️ 跨学期 Phase 5+ |

### 8.2 MVP 不包含的组件（明确边界）

- ❌ POMCP（完整 POMDP 求解器）
- ❌ DKT / DKVMN（深度知识追踪）
- ❌ Causal Forest（仅用简化 A/B 测试）
- ❌ 跨学期/学段画像演化
- ❌ 学科本体自动构建
- ❌ 教师/家长端 UI（仅学生端）

### 8.3 MVP 数据流（简化）

```
Student → App → CTA(BKT+MIRT+TC+Misconception)
              ↓
              LCA(Contextual Bandit: 5 类干预 × 4 参数)
              ↓
              App → Student
              ↓
              反馈 → CTA 更新 → 循环
```

---

## 9. 与 v2.0 §3 架构的关系

| 维度 | v2.0 §3 提供 | 本文档补充 |
|---|---|---|
| **三空间架构骨架** | ✅ 完整（State + Bloom + Policy）| 不重复，明确引用 |
| **CTA 思维模式** | ✅ 认知科学家 + 心理测量学家 | L0-L4 数学栈工程映射 |
| **LCA 思维模式** | ✅ 教练 + RL 策略器 | L3-L4 教学法栈工程映射 |
| **BloomProfile** | ✅ 6 层认知层级分布 | 不重复 |
| **互校机制** | ✅ 核心循环 + 3 个机制 + 4 个模式 | 互校 + L4 因果归因整合 |
| **完整数据流** | ✅ 伪代码骨架 | 工程细节 + 开源依赖 |
| **状态估计工程** | ⚠️ 只提 IRT/BKT/DKT 名字 | L0-L4 数学栈 + Q 矩阵扩展 |
| **干预策略工程** | ⚠️ 有策略列表无理论 | L3-L4 教学法栈 + Contextual Bandits MVP |
| **C 维度内容库** | ⚠️ 抽象置信度 | TC + Misconceptions 双轨 |
| **持久化** | ✅ 学生状态 + 干预历史 + 证据 | 跨会话 + 跨学期边界 |

**核心关系**：本文档是 v2.0 §3 的**工程细化 + 教学法整合**——不与 v2.0 冲突，填补工程实现层。

---

## 10. 关联文档

- **上层战略**：
  - [01-applications.md](01-applications.md) — 4 大核心应用场景（依赖本架构）
  - [03-roadmap.md](03-roadmap.md) — 阶段划分（基于本架构）
  - [04-risks.md](04-risks.md) — 风险矩阵（基于本架构 + 路线图）
- **P0 三件套（架构整合来源）**：
  - [v0.3.0 CTA 数学基础](../../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md) — §3/5/7 整合到 §3.1/5
  - [v0.4.0 LCA 教学法基础](../../30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md) — §4 整合到 §3.2/6
  - [v0.5.0 C 维度内容库](../../30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md) — §3 整合到 §3.1/5.3
- **核心论证**：
  - [v2.0 深度研究 §3 ECOS 完整架构](../../deep-research/Cognitive-Digital-Twin-Deep-Research.md) — 本文档的骨架来源
  - [v2.0 §3.5 双 Agent 互校机制](../../deep-research/Cognitive-Digital-Twin-Deep-Research.md) — 整合到 §3.3
  - [v2.0 §3.6 完整数据流](../../deep-research/Cognitive-Digital-Twin-Deep-Research.md) — 整合到 §4
- **工程层**（待填充）：
  - [10-engineering/01-cta-belief-engine.md](../../10-engineering/01-cta-belief-engine.md) — CTA 工程实现（按本文档 §5）
  - [10-engineering/02-lca-policy-engine.md](../../10-engineering/02-lca-policy-engine.md) — LCA 工程实现（按本文档 §6）
  - [10-engineering/03-bloom-goal-library.md](../../10-engineering/03-bloom-goal-library.md) — Bloom 目标库（按本文档 §2.2）
  - [10-engineering/04-dual-agent-calibration.md](../../10-engineering/04-dual-agent-calibration.md) — 双 Agent 互校（按本文档 §3.3）
  - [10-engineering/05-persistence-session.md](../../10-engineering/05-persistence-session.md) — 持久化（按本文档 §7）
- **背景**：
  - [research/README.md](../../README.md) — Research SSOT 入口
  - [MIGRATION-FROM-SELFLAB.md](../../MIGRATION-FROM-SELFLAB.md) — 项目迁移梳理

---

## 11. 版本与维护

- **v1.0**（2026-06-25）— 初版，整合 P0 三件套到 ECOS 整体架构总图

**待办（影响本文档时同步更新）**：
- 当 [10-engineering/](../../10-engineering/) 任意文档完成后，回填对应章节的工程实现细节
- 当 Phase 4 MVP 实验完成后，回填"实际效果"段落（MVP 架构的实证表现）
- 当 P1 理论借鉴（Contextual Bandits / Cognitive Apprenticeship 深化 / Working Memory）完成后，相应更新 §6

---

**创建日期**：2026-06-25
**维护者**：Bisen & Claude
