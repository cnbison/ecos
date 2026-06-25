# ECOS 业务流程演示：初二学生小张的 4 周完整学习流程

> **版本**：v1.0（2026-06-25）
> **性质**：业务流程演示文档——基于已完成的 14 份核心文档（战略层 4 + 工程层 5 + 教学法层 4 + MVP 设计 1），展示一个具体场景下 ECOS 各模块如何协同工作
> **使用场景**：研究回顾 / 工程实施参考 / 团队培训 / 学术合作沟通
> **关联**：本文档引用了 [Phase 0 全部 14 份核心文档](#关联文档)，请配合阅读
> **维护者**：Bisen & Claude

---

## 0. 场景设定

### 学生信息

| 维度 | 信息 |
|---|---|
| 姓名 | 小张 |
| 性别 / 年龄 | 男 / 14 岁 |
| 年级 / 学科 | 初二 / 初中数学 |
| 学校 | XX 中学 |
| 当前问题 | 二次函数应用题反复出错 |
| 家长 | 已签署 ECOS 数据同意书 |
| 教师 | 数学教师王老师，参与 Q 矩阵审核 |

### 初始 5D 状态（基于预测试 + 教师评估）

```yaml
K (知识):
  theta: 0.55
  mastery_prob: 0.55
  evidence_ids: [初始评估]
  含义: 二次函数顶点公式"基本记得但应用易错"

P (程序):
  theta: 0.30
  mastery_prob: 0.30
  含义: 多步解题程序薄弱（"分情况讨论"子缺口）

S (策略):
  theta: 0.45
  含义: 策略能力中等

C (置信度):
  theta: 0.60   # ★ 伪置信——以为掌握，实际没有
  含义: 学生自我评估 0.8，但实际理解 0.41

X (外部支架):
  theta: 0.40
  含义: 家长辅导较多
```

### 初始 BloomProfile（6 层分布）

| Bloom 层 | 掌握度 | 评估 |
|---|---|---|
| L1 Remember（记忆）| 0.85 | 公式基本记得 |
| L2 Understand（理解）| 0.65 | 理解抛物线几何意义 |
| L3 Apply（应用）| 0.40 | 应用到新情境较弱（核心弱点）|
| L4 Analyze（分析）| 0.15 | 几乎不会拆题 |
| L5 Evaluate（评价）| 0.05 | — |
| L6 Create（创造）| 0.00 | — |
| **dominant_layer** | **Apply** | 主层 |

### 初始 LearningDNA 推断（基于 5 道预测试）

```yaml
input_preference: visual          # 视觉型
feedback_preference: immediate   # 喜欢即时反馈
fatigue_pattern:
  下午_3_5点: 高疲劳
  其他: 低
error_pattern:
  - 分情况讨论错误
  - 不等式符号翻转
motivation_pattern:
  weekday: 0.6
```

### 初始 TC 状态（[v0.5.0 C 维度内容库 §1](../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md)）

| TC | 状态 | 说明 |
|---|---|---|
| **TC_变量** | **liminal** | ★ 卡在"变量"概念（从具体数到符号的跨越）|
| TC_函数 | pre_liminal | 尚未开始跨越 |
| TC_几何证明 | pre_liminal | 尚未开始跨越 |

### 初始 Misconception 历史

- 空（首次评估未触发）

### 关键观察（初始状态分析的 3 个核心发现）

1. **C（置信度）= 0.60 是伪置信**——学生自我评估 0.8，但实际只有 0.55。这种"伪自信"如果不识别，会导致 ECOS 推荐过难的任务，引发反复失败。
2. **TC_变量处于 liminal 状态**——学生在跨越"变量"概念的关键节点。liminal 状态不是"退步"，而是"正在突破"——LCA 不应判定为失败，应增加 scaffolding。
3. **L3 Apply 只有 0.40 + L4 Analyze 0.15**——核心痛点。BloomProfile 5D 联合显示：学生"会记公式但不会用 + 不会拆题"——典型的"会做但不会想"中国教育痛点。

---

## 1. 注册与初始化（Day 1）

### Step 1：合规与同意

依据：[04-risks.md §D1 未成年人数据合规](../research/00-overview/04-risks.md)

```
家长签署：
  - 数据收集同意书（最小化原则）
  - 端侧计算同意（敏感字段本地处理）
  - 第三方审计知情

系统生成：
  student_id: 'S2025-00842'         # 不可逆 ID（SHA256 + salt）
  anonymized_id: 'a3f8e9b2'         # 用于学术研究
  consent_version: 2                 # 中国《个人信息保护法》合规版本
```

### Step 2：首次 BloomProfile 完整评估

依据：[02-bloom-application.md §4.2 多题取样](../research/20-pedagogy/02-bloom-application.md)

| Bloom 层 | 评估方式 | 题目数 | 用时 |
|---|---|---|---|
| L1 Remember | 公式记忆题（自动评分）| 5 道 | 5 分钟 |
| L2 Understand | 解释题（LLM rubric）| 3 道 | 10 分钟 |
| L3 Apply | 应用题（自动评分）| 5 道 | 15 分钟 |
| L4 Analyze | 拆解题（LLM rubric）| 3 道 | 20 分钟 |
| **总计** | — | **16 道** | **50 分钟** |

**关键设计决策**（[01-cta-belief-engine.md §6.2 Q 矩阵扩展](../research/10-engineering/01-cta-belief-engine.md)）：每题标注完整元数据

```python
Q_MATRIX[problem_id="MATH.QUAD.PROB.L3.001"]:
    bloom_goal_id: "MATH.QUAD.L3"           # 应用层
    attributes: ["二次函数概念", "分情况讨论"]
    threshold_concepts: ["TC_变量"]          # 关联 TC
    misconceptions: ["M-J3"]                # 关联 Misconception
    difficulty: 0.65
    clt_level: 2  # DEVELOPING
```

### Step 3：5D 状态初始化

依据：[01-cta-belief-engine.md §2 BeliefState 数据结构](../research/10-engineering/01-cta-belief-engine.md)

```python
belief_state = BeliefState(
    student_id="S2025-00842",
    K=DimensionState(theta=0.55, mastery_prob=0.55, confidence=0.6),
    P=DimensionState(theta=0.30, mastery_prob=0.30, confidence=0.5),
    S=DimensionState(theta=0.45, mastery_prob=0.45, confidence=0.5),
    C=DimensionState(theta=0.60, mastery_prob=0.60, confidence=0.5),  # ★ 伪置信
    X=DimensionState(theta=0.40, mastery_prob=0.40, confidence=0.5),
    theta_mean=np.array([0.55, 0.30, 0.45, 0.60, 0.40]),
    theta_cov=np.eye(5) * 0.1,
    bloom_profile=BloomProfileState(
        remember=0.85, understand=0.65, apply=0.40,
        analyze=0.15, evaluate=0.05, create=0.00,
        dominant_layer=BloomLevel.APPLY
    ),
    overall_confidence=0.5,  # 初始低置信度
    tc_states={
        "TC_变量": TCState(status="liminal", progress=0.3, confidence=0.5),
        "TC_函数": TCState(status="pre_liminal"),
        "TC_几何证明": TCState(status="pre_liminal")
    },
    misconception_history=[]
)
```

### Step 4：加密持久化

依据：[05-persistence-session.md §2 SQLite Schema + §7.1 加密存储](../research/10-engineering/05-persistence-session.md)

```sql
-- 加密存储到 students 表（Fernet + msgpack）
INSERT INTO students VALUES (
    'S2025-00842', 8, 'math', '2026-06-25', '2026-06-25',
    ENCRYPT(5D_state),                  -- current_state_5d（加密）
    ENCRYPT(bloom_profile),           -- current_bloom_profile（加密）
    ENCRYPT(learning_dna),            -- current_learning_dna（加密）
    ENCRYPT(tc_states),               -- tc_states（加密）
    ENCRYPT([]),                       -- misconception_history（空）
    ENCRYPT(trajectory_summary),       -- trajectory_summary（加密）
    0.5,                              -- overall_confidence
    'v1.0',                           -- version
    2,                                -- consent_version
    'a3f8e9b2'                        -- anonymized_id
);
```

### Step 5：ZPD 计算

依据：[04-zpd-application.md §1.3 ZPD 边界](../research/20-pedagogy/04-zpd-application.md)

```python
zpd = ZPD.compute(
    student_id="S2025-00842",
    bloom_target=BloomLevel.APPLY,  # 当前主层
    adl=ActualDevelopmentLevel(...),  # 0.40
    pdl=PotentialDevelopmentLevel(...),  # 0.55 (ADL + 0.15 scaffolding 增量)
)
# 结果:
#   zpd_lower = 0.45  (ADL 0.40 + 0.05)
#   zpd_upper = 0.50  (PDL 0.55 - 0.05)
#   recommended_difficulty = 0.475 (中位数)
```

**关键判断**：小张当前 L3 Apply 的 ZPD 是 **[0.45, 0.50]**——非常窄（仅 0.05 宽度），说明：
- 学生已经接近掌握（0.40）
- 但仍未达 ZPD 下界（0.45）
- 需要任务难度略高于当前水平
- ZPD 窄说明教学空间小——需要在 0.45-0.50 内精挑细选

---

## 2. 典型回合（Day 3 - 做题 → 干预）

### Step 1：学生做题

**题目**（来自 [03-bloom-goal-library.md §3 数学 BloomGoal 库](../research/10-engineering/03-bloom-goal-library.md)）：

> 某商店销售某商品，每件商品售价 60 元时，每天可卖 20 件。每降价 1 元，每天多卖 2 件。问售价多少时每天销售额最大？

**小张作答**：

```
列式:     y = (60 - x)(20 + 2x)             # 正确
化简:     y = -2x² + 100x + 1200           # 正确
求最值:   x = -100 / (2 × -2) = 25         # ★ 错误应用顶点公式
结果:     售价 = 60 - 25 = 35 元           # 最终答案对，但过程有问题
```

### Step 2：LLM Critic 感知

依据：[01-cta-belief-engine.md §9.1 感知层](../research/10-engineering/01-cta-belief-engine.md)

```python
# 输入到 LLM Critic（temperature=0.2 → 稳定结构化输出）
critic_input = {
    "题目": "某商店销售...",
    "学生作答": "y = (60-x)(20+2x), 化简 y = -2x² + 100x + 1200, x = 25, 售价 35 元",
    "正确答案": "x = 25, 售价 35 元",
}

# LLM Critic 输出（结构化）
critic_output = {
    "correctness": True,             # 最终答案正确
    "explanation_quality": 0.65,
    "confusion_signals": ["不确定 x 是什么变量", "使用顶点公式但不理解含义"],
    "self_evaluation": 0.8,          # ★ 学生自我感觉很好（伪置信）
    "error_pattern": "理解变量 x 是'降价'，但误以为是'售价'——变量定义混乱"
}
```

### Step 3：CTA 状态更新

依据：[01-cta-belief-engine.md §10 CTAOrchestrator](../research/10-engineering/01-cta-belief-engine.md)

**Step 3.1：L1 BKT 更新（每个知识点）**

```python
for skill in structured_obs.skills_touched:  # ["二次函数应用题", "分情况讨论"]
    if skill == "二次函数应用题":
        new_k = bkt.update(skill, correct=True)   # K: 0.55 → 0.58 (+0.03)
    if skill == "分情况讨论":
        new_p = bkt.update(skill, correct=False)  # P: 0.30 → 0.27 (-0.03)
```

**Step 3.2：L2 MIRT 联合估计（5D）**

```python
theta_5d_new = mirt_5d.update(observation)
# 5D 联合更新:
#   K: 0.55 → 0.58 (+0.03, 答对)
#   P: 0.30 → 0.27 (-0.03, "分情况讨论"未掌握)
#   S: 0.45 → 0.46 (微升, 化简过程正确)
#   C: 0.60 → 0.58 (-0.02, LLM Critic 检测到 confusion)
#   X: 0.40 → 0.40 (不变)
```

**Step 3.3：L5 Misconception 检测（关键！）**

```python
misc_hit = misconception_detector.detect(
    student_explanation="x = 25, 售价 35 元",
    problem_id="MATH.QUAD.PROB.L3.001",
    response_data=observation
)
# 检测结果:
#   misc_id = "M-J3-变体"  # 变量定义混乱（接近 M-J3 不等式性质推广）
#   confidence = 0.78
#   trigger_problem_id = "MATH.QUAD.PROB.L3.001"
#   correction_strategy = "明确变量定义 + 数值代入验证"
```

**Step 3.4：C 维度更新（v0.5.0 Misconception 折扣）**

```python
if misc_hit:
    state.C.theta *= 0.7   # 伪置信折扣！
    state.C.illusory_confidence_flag = True
    state.C.misconception_hits.append(misc_hit)
# C: 0.58 → 0.58 * 0.7 = 0.41 (大幅下调，反映真实状态) ★
```

**Step 3.5：TC 状态更新**

```python
for tc_id in ["TC_变量", "TC_函数"]:
    tc_state = tc_detector.detect(tc_id, observation, current_state)
    if tc_id == "TC_变量":
        # liminal 信号：连续错误 + 解释含"不确定"
        tc_state = TCState(
            tc_id="TC_变量",
            status="liminal",          # 仍 liminal
            progress=0.3,
            confidence=0.5,
            liminal_signals=["consecutive_errors", "meta_confusion"]
        )
        # LCA 不判定为"退步"——而是"正在跨越 TC"
```

**更新后的状态**：

```yaml
5D 状态:
  K: 0.55 → 0.58 (+0.03, 答对)
  P: 0.30 → 0.27 (-0.03, 分情况讨论错)  ★ 进一步下降
  S: 0.45 → 0.46 (微升)
  C: 0.60 → 0.41 (-0.19, Misconception 折扣 × 0.7)  ★ 关键：伪置信纠正
  X: 0.40 (不变)

BloomProfile:
  L1: 0.85 (不变)
  L2: 0.65 (不变)
  L3: 0.40 → 0.39 (微降, 答对但 misconception)
  L4: 0.15 (不变)
  dominant_layer: 仍 Apply

TC_变量: liminal → liminal (持续 liminal 状态)

新增 Misconception: M-J3-变体 (置信度 0.78)
```

### Step 4：双 Agent 互校（信念质疑模式触发）

依据：[04-dual-agent-calibration.md §3.2 信念质疑 + §6 orchestrator](../research/10-engineering/04-dual-agent-calibration.md)

```python
# 触发条件：CTA 之前高置信（C=0.60）但实验发现学生实际有 misconception
belief_challenge = BeliefChallenge(
    student_id="S2025-00842",
    challenged_dimension="C",
    cta_claim=0.60,                   # 之前 CTA 估计
    experimental_evidence={
        "dimension": "C",
        "misconception_id": "M-J3-变体",
        "misconception_confidence": 0.78,
        "self_evaluation": 0.8,        # 学生自我感觉很好
        "actual_understanding": 0.41   # 实际理解
    },
    confidence_in_evidence=0.85
)
# CTA 接收挑战 + 新证据 → 更新信念
# C: 0.41 (反映真实状态)
```

**互校记录（calibration_log 表）**：

```sql
INSERT INTO calibration_log VALUES (
    'S2025-00842', '2026-06-28 14:23:00', 5,
    'belief_challenge',                                -- 信念质疑模式
    '{"dimension": "C", "cta_claim": 0.60, "evidence": "M-J3-变体"}',
    '{"before": 0.60, "after": 0.41}',
    'LCA 实验发现学生实际有 misconception，与 CTA 高置信矛盾',
    'belief_challenge',
    'CTA 重审 + 更新 C 维度',
    0, 0,
    1523                                              -- 耗时 1.5 秒
);
```

### Step 5：LCA 选干预

依据：[02-lca-policy-engine.md §6 LCAOrchestrator.select_intervention](../research/10-engineering/02-lca-policy-engine.md)

**Step 5.1：选 Bloom 目标**

```python
bloom_target = select_bloom_target(
    belief_state=belief_state,
    bloom_target_candidates=[BloomLevel.APPLY, BloomLevel.ANALYZE],
    learning_dna=learning_dna
)
# 当前 L3=0.39（微降）, 提升空间大 → 选 L3 Apply
# 但 L4 Analyze 提升空间更大（0.15）→ 选 L3 但引导 L4
```

**Step 5.2：选 CA 阶段**

```python
ca_stage = ca_state_machine.transition(
    "S2025-00842", belief_state, intervention_history
)
# 当前: Articulation（学生需要讲出思路）
```

**Step 5.3：CLT 4 级呈现**

```python
clt_level = clt.determine_level("S2025-00842", belief_state)
# 触发 liminal 状态 → 升级到 NOVICE
# CLTLevel.NOVICE
```

**Step 5.4：ZPD 检查（关键）**

```python
zpd_l3 = ZPD.compute("S2025-00842", BloomLevel.APPLY, adl, pdl)
# zpd_l3 = [0.45, 0.50] — 非常窄
```

**Step 5.5：Contextual Bandits 选干预**

```python
candidates = generate_candidates(bloom_target, clt_level, ca_stage, ...)
# 候选:
#   - EXPLANATORY (讲解"分情况讨论" + NOVICE) — 修 misconception
#   - PRACTICE (变式练习, 难度 0.45) — 在 ZPD 下界
#   - METACOGNITIVE (Articulation + peer_review) — 引导学生讲思路

selected = bandit.select_intervention(belief_state, candidates)
# 选择: EXPLANATORY + CLT NOVICE
# 理由:
#   - Misconception M-J3-变体 需要讲解
#   - liminal 状态需要更多 scaffolding
#   - 学生在 ZPD 下界（需要降到 ZPD 内）
```

**Step 5.6：生成 rationale（LLM 表达层）**

```python
rationale = rationale_gen.generate(
    intervention=selected,
    belief_state=belief_state,
    audience="student"  # 学生友好版
)
# rationale: "我看到你在二次函数应用题上有些混淆——
#             变量 x 的含义和分情况讨论是常见难点。
#             让我们先看一个完整的例子，理解后自己做一次。"
```

**Step 5.7：输出 LCAResult**

```python
lca_result = LCAResult(
    student_id="S2025-00842",
    intervention=Intervention(
        type=InterventionType.EXPLANATORY,
        bloom_target=BloomLevel.APPLY,
        target_skills=["二次函数应用题", "分情况讨论"],
        target_misconceptions=["M-J3-变体"],   # ★ 针对性修正
        difficulty=0.40,                       # 略低于 ZPD 下界 0.45
        clt_level=CLTLevel.NOVICE,            # 完整 worked example
        ca_stage=CAStage.MODELING,            # 专家示范
        scaffolding_level=0.9
    ),
    rationale=rationale,
    expected_gain=0.05,
    bloom_target=BloomLevel.APPLY,
    timestamp=now()
)
```

### Step 6：App 层执行

```python
# 推送讲解视频 + 引导问题
app_layer.execute(
    intervention_type="explanatory",
    problem_id="MATH.QUAD.PROB.L2.001",   # 讲解型题目
    presentation={
        "show_worked_example": True,
        "worked_example_steps": "complete",
        "scaffolding": 0.9,
        "hints_available": 3,
        "feedback_timing": "immediate"
    },
    rationale=rationale
)

# 学生看讲解视频（5 分钟）
# 完成 1 道讲解型题目（10 分钟）
# 立即反馈（每步都对 → C 维度 +0.05）
```

### Step 7：CTA 更新（L4 因果归因）

依据：[01-cta-belief-engine.md §7 L4 因果归因](../research/10-engineering/01-cta-belief-engine.md)

```python
# 学生完成讲解型题目
observation_2 = Observation(
    correct=True,
    response_time=120,  # 2 分钟
    explanation="我明白了——变量 x 是'降价'，不是'售价'。"
)

# L1 BKT 更新
new_k = bkt.update("二次函数应用题", correct=True)
# K: 0.58 → 0.61 (新知识 +0.03)
new_p = bkt.update("分情况讨论", correct=True)
# P: 0.27 → 0.30 (分情况讨论 +0.03)  # ★ P 回升！

# L4 因果归因（A/B test）
causal_effect = lca_l4.attribute(
    intervention_type="explanatory",
    student_id="S2025-00842",
    state_delta=0.04,  # K + P 改善
    is_control=False
)
# ATE = 0.08, p-value = 0.02, significant = True
# "讲解型干预对 P（程序技能）有显著效果（ATE=0.08, p<0.05）"
```

**LinUCB 更新策略权重**（[02-lca-policy-engine.md §4.2](../research/10-engineering/02-lca-policy-engine.md)）：

```python
# Context: [0.61, 0.30, 0.46, 0.41, 0.40, 0.85, 0.65, 0.39, 0.15, ...]
# Arm: explanatory_no_misconception
# Reward: 0.04
bandit.update(arm, context, reward)
# 后续推荐该策略的 UCB 增加
```

### Step 8：持久化（L1 → L2 → L3 → L4 写入）

依据：[05-persistence-session.md §3 4 层记忆](../research/10-engineering/05-persistence-session.md)

```python
# L1 短期记忆（Hawking）
short_term.add(observation_2)

# L2 中期记忆（Crystallizer）— evidence_log
mid_term.add_evidence(observation_2)

# L3 长期记忆（Identity）— students 表更新
long_term.save_state("S2025-00842", belief_state)
# 加密存储:
#   current_state_5d = ENCRYPT(new 5D)
#   current_bloom_profile = ENCRYPT(new BloomProfile)
#   tc_states = ENCRYPT(updated TC states)
#   misconception_history = ENCRYPT([M-J3-变体])

# L4 持久记忆（Archive）— trajectory_snapshots
archive.save_snapshot(
    "S2025-00842", belief_state,
    snapshot_type="session_end",
    epoch=1
)
```

---

## 3. 4 周后突破检测（Day 28）

### 累计数据（W1-W4）

```yaml
W1-W4 累计:
  总观测数: 120 次（平均每天 4-5 题）
  BKT 更新次数: 5 个知识点 × 120 题 = 600 次
  MIRT 5D 联合更新: 120 次
  互校触发:
    常态循环: 120 次
    信念质疑: 3 次（M-J3-变体 / M-J9 / M-J10）
    策略质疑: 1 次（连续 5 次 EXPLANATORY 无效 → 切换 INQUIRY）
    元反思: 1 次（W4 末整体回顾）
  干预类型分布:
    EXPLANATORY: 45 次（37.5%）
    PRACTICE: 50 次（41.7%）
    INQUIRY: 15 次（12.5%）
    FEEDBACK: 8 次（6.7%）
    METACOGNITIVE: 2 次（1.7%）

最终 5D 状态:
  K: 0.55 → 0.78 (+0.23)  # 显著提升
  P: 0.30 → 0.62 (+0.32)  # ★ 最大提升
  S: 0.45 → 0.58 (+0.13)
  C: 0.60 → 0.72 (+0.12)  # 真实置信度提升（伪置信纠正后）
  X: 0.40 → 0.30 (-0.10)  # 外部支架减少（独立学习能力提升）

最终 BloomProfile:
  L1: 0.85 → 0.92
  L2: 0.65 → 0.82
  L3: 0.40 → 0.71  # ★ 突破（原 ZPD 0.45-0.50 已超过）
  L4: 0.15 → 0.32  # ★ 跨越"变量"TC 后 L4 显著提升
  L5: 0.05 → 0.08
  dominant_layer: Apply（仍主层，但 L3 已成熟）

TC 状态:
  TC_变量: liminal → post_liminal  # ★ 成功跨越！
  TC_函数: pre_liminal → liminal   # 进入 liminal，准备跨越
  TC_几何证明: pre_liminal（未变）

新增 Misconception 历史:
  - M-J3-变体（变量定义混乱）—— 后续已部分修正
  - M-J9（几何证明 = 计算）—— 检测到 1 次，未复发
  - M-J10（概率是运气）—— 检测到 1 次，未复发
```

### ZPD 突破检测

依据：[04-zpd-application.md §3 ZPD 突破检测](../research/20-pedagogy/04-zpd-application.md)

```python
# ZPD 突破判断
prev_zpd = ZPD.compute("S2025-00842", BloomLevel.APPLY, 4 周前的 adl, pdl)
# prev_zpd.zpd_upper = 0.50
curr_adl_mastery = belief_state.bloom_profile.apply  # 0.71
# curr_adl_mastery (0.71) >= prev_zpd_upper (0.50)
# ★ ZPD 突破！

breakthrough = ZPDBreakthrough(
    student_id="S2025-00842",
    bloom_target=BloomLevel.APPLY,
    prev_zpd_upper=0.50,
    curr_adl_mastery=0.71,
    improvement=0.21,  # 显著进步
    timestamp=now()
)
```

### 突破归因（与 CTA L4 Causal Inference 整合）

```python
# 取最近 5 次干预
recent = intervention_history[-5:]
contributions = {}
for iv in recent:
    if iv.actual_state_delta and iv.actual_state_delta > 0.05:
        causal = cta_l4.attribute(
            intervention_type=iv.intervention.intervention_type.value,
            student_id="S2025-00842",
            state_delta=iv.actual_state_delta,
            is_control=False
        )
        contributions[iv.intervention.intervention_type.value] = causal.ate

# 结果（示例）:
# EXPLANATORY（讲解型）: ATE 0.12 (主要贡献)
# PRACTICE（变式练习）: ATE 0.08
# METACOGNITIVE（自我解释）: ATE 0.05
# 其他: ATE 0.02
```

### 家长/教师报告（MVP 阶段生成但不实现 UI）

```markdown
# 小张 ZPD 突破报告（30 天）

## 突破摘要
- BloomProfile L3 Apply: 0.40 → 0.71 (+0.31)
- 5D 中 P（程序）提升最大: +0.32
- TC "变量" 成功跨越（post-liminal）

## ZPD 突破
- L3 Apply 实际能力 (0.71) > 原 ZPD 上界 (0.50)
- ★ 突破！建议进入 L4 Analyze 进阶

## 突破归因（基于因果归因）
1. 讲解型干预 40% (ATE 0.12)
2. 变式练习 27% (ATE 0.08)
3. 自我解释 17% (ATE 0.05)
4. 其他 16% (ATE 0.02)

## 关键事件
- Day 5: 检测到 M-J3-变体 misconception（伪置信纠正）
- Day 14: 互校信念质疑触发 → C 维度从 0.60 调整到 0.41
- Day 28: TC "变量" 成功跨越

## 下一步建议
- 继续 L3 Apply 巩固（保持 70%+）
- 开始 L4 Analyze 入门（拆解题）
- 下次评估：Day 56（2 个月后）
```

---

## 4. 关键事件时间线（4 周）

```
Day 1    初始化: 5D + BloomProfile + ZPD + Misconception（空）
         → ZPD L3 = [0.45, 0.50]（窄）
         → 家长签署同意书
         → 首次完整 BloomProfile 评估（50 分钟）

Day 3    第一次做题 → 答对但检测到 M-J3-变体（伪置信纠正）
         → C: 0.60 → 0.41（伪置信识别）
         → BloomProfile L3: 0.40 → 0.39
         → 双 Agent 互校：信念质疑触发
         → LCA 推荐 EXPLANATORY + CLT NOVICE
         → 学生完成讲解 + 立即反馈
         → P: 0.27 → 0.30（程序回升）

Day 7    W1 末: BloomProfile L3 稳定在 0.45
         → 进入 ZPD 下界
         → TC_变量 仍 liminal（liminal 信号持续）

Day 14   W2 末: BloomProfile L3: 0.45 → 0.55
         → 互校策略质疑触发（EXPLANATORY 连续 5 次效果减弱）
         → 切换 INQUIRY（探究型）+ 配合 PRACTICE
         → 5D: K=0.65, P=0.40, C=0.50

Day 21   W3 末: BloomProfile L3: 0.55 → 0.65
         → TC_变量 仍 liminal
         → 继续 PRACTICE + METACOGNITIVE 组合
         → ARTICULATION 阶段：学生开始讲思路

Day 28   W4 末: ★ ZPD 突破！BloomProfile L3: 0.65 → 0.71
         → TC_变量 → post_liminal（成功跨越）
         → P（程序）从 0.30 → 0.62（最大提升 +0.32）
         → C 真实提升到 0.72（伪置信纠正后）
         → 家长报告 + 教师报告生成
```

---

## 5. 关键洞察（场景演示的核心发现）

### 洞察 1：5D 状态的"伪置信"自动纠正机制是 ECOS 关键差异化能力

**问题**：小张 C（置信度）= 0.60 是伪自信——实际只有 0.41。如果不识别，ECOS 会推荐过难任务，引发反复失败，破坏学习动机。

**ECOS 解决方案**（[v0.5.0 §2.3](../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md)）：
- LLM Critic Misconception 检测 → C 维度 × 0.7 折扣
- 双 Agent 互校信念质疑触发 → CTA 重审
- C 维度反映"真实理解度"而非"自我感觉"

**对比其他 AI 教育系统**：Khanmigo / Squirrel AI 都没有"伪置信识别"机制——这是 ECOS 关键差异化能力。

### 洞察 2：BloomProfile 6 层数据在每个环节流转

| 环节 | BloomProfile 角色 |
|---|---|
| 注册 | 完整评估（L1-L4，16 道题，50 分钟）|
| 每次做题 | MIRT 联合更新 + BloomGoal 关联 |
| LCA 选目标 | next_target 算法（基于当前层 + 提升空间）|
| 干预设计 | 干预类型与 Bloom 层映射 |
| 突破检测 | 当前层 vs ZPD 上界 |
| 评估 | 月度完整评估 |

**核心洞察**：BloomProfile 不是"分数"——是**6 维分布**，提供比传统分数丰富得多的信息。

### 洞察 3：ZPD 突破 + TC 跨越 + Misconception 检测三者联动

这是 ECOS 区别于其他 AI 教育系统的**核心差异化能力**：

| 维度 | 其他 AI 系统 | ECOS |
|---|---|---|
| **ZPD** | 没有显式建模 | 显式 ADL/ZPD/PDL 三层结构 |
| **TC** | 没有 TC 库 | 8 个 MVP TC + 跨越检测 + liminal 状态 |
| **Misconception** | 没有 misconception 库 | 30-50 条 misconception + LLM Critic 检测 + 折扣机制 |

**三者联动示例**：
- M-J3-变体 命中 → C 维度折扣 → 触发信念质疑
- TC_变量 liminal → 升级 CLT 到 NOVICE
- ZPD L3 [0.45, 0.50] 突破 → 准备 L4 Analyze 进阶

### 洞察 4：MVP 范围严格遵守的体现

**MVP 不实现的部分**：
- ❌ 教师端 UI（仅生成报告）
- ❌ 家长端 UI（仅生成报告）
- ❌ 跨学科（MVP 仅数学）
- ❌ 跨学期（MVP 仅学期内）
- ❌ L5-L6（MVP 仅初中 K12）

**MVP 实现的部分**：
- ✅ 学生端做题 + 干预展示
- ✅ CTA + LCA + 双 Agent 互校
- ✅ 持久化 + 4 层记忆
- ✅ 报告生成（Markdown/PDF）

---

## 6. 关联文档

### 6.1 战略层（场景分析依据）

- [01-applications.md](../research/00-overview/01-applications.md) — 4 大应用场景（场景 A 学科诊断 + B 自适应干预 + C 成长轨迹 + D 教师家长协作）
- [02-architecture.md §5 状态估计工程实现](../research/00-overview/02-architecture.md) — CTA 5 层数学栈
- [02-architecture.md §6 干预策略工程实现](../research/00-overview/02-architecture.md) — LCA 3 大理论群
- [03-roadmap.md §2 M2-M3 里程碑](../research/00-overview/03-roadmap.md) — 50-100 学生实验设计
- [04-risks.md §D1 未成年人数据合规](../research/00-overview/04-risks.md) — 隐私保护

### 6.2 工程层（数据流转具体实现）

- [01-cta-belief-engine.md](../research/10-engineering/01-cta-belief-engine.md) — CTA 信念引擎（5 层数学栈 + 内容库 + LLM Critic）
- [02-lca-policy-engine.md](../research/10-engineering/02-lca-policy-engine.md) — LCA 策略引擎（L3-L4 教学法 + Contextual Bandits）
- [03-bloom-goal-library.md](../research/10-engineering/03-bloom-goal-library.md) — Bloom 目标库（数学 8 知识点 × 4 层 = 32 条 MVP）
- [04-dual-agent-calibration.md](../research/10-engineering/04-dual-agent-calibration.md) — 双 Agent 互校（4 模式 + 3 抗幻觉机制）
- [05-persistence-session.md](../research/10-engineering/05-persistence-session.md) — 持久化（4 层记忆 + 加密）

### 6.3 教学法层（教学法依据）

- [01-k12-cognitive-structure.md](../research/20-pedagogy/01-k12-cognitive-structure.md) — K12 学段差异化（初二：形式运算初期）
- [02-bloom-application.md](../research/20-pedagogy/02-bloom-application.md) — Bloom 跨层级策略（L3 Apply 是核心）
- [03-learning-strategies.md](../research/20-pedagogy/03-learning-strategies.md) — 学习策略空间（EXPLANATORY + PRACTICE 组合）
- [04-zpd-application.md](../research/20-pedagogy/04-zpd-application.md) — ZPD 在 ECOS（突破检测 + liminal 状态）

### 6.4 P0 三件套（理论借鉴）

- [v0.3.0 CTA 数学基础](../research/30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md) — 5 层数学栈
- [v0.4.0 LCA 教学法基础](../research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md) — CLT + Bjork + CA
- [v0.5.0 C 维度内容库](../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md) — TC + Misconceptions 双轨

### 6.5 MVP 设计（整体集成）

- [90-mvp/README.md](../research/90-mvp/README.md) — M2-M3 详细设计 + H1-H4 假设验证

---

## 7. 版本与维护

- **v1.0**（2026-06-25）— 初版

**使用建议**：
- 阅读顺序：先读"场景设定"理解初始状态 → 然后"典型回合"理解单次流程 → 最后"突破检测"理解长期效果
- 教学使用：可作为团队培训材料、学术合作沟通材料、工程实施参考
- 二次创作：可基于本文档编写其他场景（高中生 L4-L6、教师端班级数据、特殊学生）

**待办**：
- 当 Phase 4 MVP 实验完成后，更新"4 周后突破检测"为真实数据
- 当 Phase 5 跨学科扩展后，增加高中物理/语文示例
- 当 ECOS Python 包实现后，附加可运行的代码示例

---

**创建日期**：2026-06-25
**维护者**：Bisen & Claude
