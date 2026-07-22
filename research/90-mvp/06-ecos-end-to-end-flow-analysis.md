# ECOS 端到端流程深度分析

> **文档位置**：`research/90-mvp/06-ecos-end-to-end-flow-analysis.md`
> **关联文档**：
> - [python-basics-q-matrix-design.md](./python-basics-q-matrix-design.md) — Q 矩阵设计基础
> - [ECOS-Cognitive-Intervention-Workflow.md](./ECOS-Cognitive-Intervention-Workflow.md) — 干预流程
> - [ECOS-Demo-Showcase-2026-07-06.md](./ECOS-Demo-Showcase-2026-07-06.md) — Phase 4 演示案例
> - [../00-overview/02-architecture.md](../00-overview/02-architecture.md) — ECOS 整体架构
> **状态**：✅ 完整流程梳理 (Bisen 2026-07-22 触发, 参照 Q 矩阵设计文档风格)
> **版本**：v1.0

---

## 0. 引言: ECOS 的 8 阶段闭环

ECOS 不是单一的"AI 评判系统"——它是一个**8 阶段闭环**：

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: Q 矩阵设计 (静态, 离线)                                  │
│  - 5 topic × 6 Bloom 等级 × 5D 维度                                │
│  - LLM 充当领域专家生成题目 + Misconception 标注 + a_specialized   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2: 选题 (动态, 每次答题)                                    │
│  - Warm-up 覆盖性选题 (前 5 题)                                    │
│  - Adaptive 自适应选题 (按 5D θ + SE)                              │
│  - Probe 探针题 (每 8-10 题穿插 1 道)                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Phase 3: 答题 (前端)                                              │
│  - 学生输入答案 + 提交                                              │
│  - 调 /api/judge 拿 AI 评判 (correct: bool + reasoning)             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Phase 4: AI 评判 (/api/judge)                                     │
│  - LLM 充当"老师", 看学生答案 vs 正确答案                          │
│  - 输出: {correct: bool, reasoning: str}                          │
│  ⚠️ 已知简化: 二元对错, partial credit 缺失 (Phase 5 必解)         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Phase 5: 状态更新 (BeliefEngine.update) ⭐ 核心                    │
│  - Step 1: L1 BKT 更新 (skill 维度主观概率)                        │
│  - Step 2: append response_history (答题历史)                       │
│  - Step 3: L2 MIRT MAP 估计 (5D θ + θ_cov 更新) ← **最关键**       │
│  - Step 4: Bloom profile 更新 (L1-L6 confidence 累积)              │
│  - Step 5: LLM Critic 感知层 (v0.52.0 修过 NoneType)               │
│  - Step 6: LLM Critic Misconception 检测 (v0.52.0 修过库 ID 错配)  │
│  - Step 7: TC 状态检测 (阈值概念跨越)                               │
│  - Step 8: overall_confidence = mean(5D conf)                       │
│  - Step 9: snapshot trajectory (时间序列记录)                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Phase 6: 持久化 (save_student_state)                               │
│  - SQLite 写 5D θ + θ_cov + Bloom + DNA + TC + trajectory            │
│  - response_history (v0.52.2 加 ai_reasoning 字段)                  │
│  - misconception_history (v0.52.0 修过库 ID 错配)                   │
│  - WAL 模式 (v0.51.1 修过跨线程错)                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Phase 7: 干预生成 (如有 misconception)                              │
│  - 调 /api/intervention/<sid>                                       │
│  - LLM 看 misconception 库 + 学生答案 → 生成靶向干预                │
│  - 显示在 dashboard "教练干预" 区域                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Phase 8: 个人学习画像 (/api/report/<sid>)                          │
│  - 6 段规则引擎: overall / 5D / Bloom / TC / trajectory / next_steps │
│  - 无 LLM 调用, 完全离线                                            │
│  - 折叠面板, 默认收起                                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Q 矩阵设计 (Phase 1 静态)

> 详见 [python-basics-q-matrix-design.md](./python-basics-q-matrix-design.md)

**Q 矩阵 = 题库元数据**, 不是"题库本身"。

每道题包含 6 个核心字段:
```json
{
  "problem_id": "PB-Q18",
  "bloom_goal_id": "python.variables-L6",
  "topic": "python.variables",
  "skill_name": "变量与赋值",
  "problem_text": "设计一个程序, 用户输入一个三位数...",
  "correct_answer": "def reverse(num): ...",
  "bloom_layer_observed": "L6",
  "a_specialized": [0.9, 0.2, 0.4, 0.1, 0.1],  // [K, P, S, C, X]
  "mirt_params": {"difficulty": 0.5, "discrimination": 1.2, "guessing": 0.05},
  "misconceptions": ["M1", "M2"],  // 可能触发的 misconception
  "intervention_types": ["PRACTICE"]
}
```

**a_specialized 5D 维度含义** (ECOS 理论核心):
- **K (Knowledge 知识)**: 学生对概念/事实的记忆与理解 (a_K 高 = 这道题主要测知识)
- **P (Procedural 程序)**: 学生对程序结构/调用流程的掌握
- **S (Strategic 策略)**: 学生选择/应用策略的能力 (如循环选 for/while)
- **C (Conditional 条件/元认知)**: 学生在条件判断/调试/自解释上的能力
- **X (eXpressive 跨域迁移)**: 学生把知识迁移到其他领域的能力

---

## 2. 选题 (Phase 2 动态)

**三类选题策略**, 每次答题时根据学生状态选择下一题:

### 2.1 Warm-up 覆盖性选题 (前 5 题)
**目标**: 不让任何 topic/Bloom 维度遗漏

```
按 topic 轮询 (variables → loops → functions → recursion → scope)
每个 topic 内, 选 lowest unanswered Bloom 层
```

### 2.2 Adaptive 自适应选题 (主路径)
**目标**: 选能"最大化信息量"的题

**信息量公式** (PWKL 简化):
- 选**当前 5D SE 最大的维度**的题
- 选该题 a_specialized 中最大维度对应的题
- 例: K SE=0.8 (最大) → 选 a_K 最高的题 (PB-Q18: a_K=0.9 ✓)

### 2.3 Probe 探针题 (每 8-10 题穿插 1 道)
**目标**: 不让自适应陷入局部最优

**机制**: engine.should_probe_now(student_id) → True 时强制选**随机未答题**, 不走 adaptive 路径
**v0.42.0 W3 实现**: 不告诉学生这是探针, 减少 bias

---

## 3. 答题 (Phase 3 前端)

**前端 submit() 流程** (`web/student/app.js` L336+):

```javascript
async function submit() {
  const a = document.getElementById('ans').value.trim();  // 学生答的答案
  if (!a) { alert('请输入答案'); return; }

  // 步骤 1: 调 /api/judge 拿 AI 评判 (30s AbortController timeout)
  const jd = await api.judgeAnswer({student_id, problem_id, student_answer: a});
  const ok = jd.correct;
  const reasoning = jd.reasoning || '';

  // 步骤 2: 调 /api/answer 提交答案 (含 v0.49.2 加的 user_answer/correct_answer)
  //         v0.52.2 加 ai_reasoning (reasoning 字段)
  const d = await api.submitAnswer({...correct, bloom_layer, explanation_text: a,
                                    reasoning, user_answer: a, correct_answer: q.correct_answer});

  // 步骤 3: 显示 AI 评判 + 5D 新值 + 干预 (如有)
  ...
}
```

---

## 4. AI 评判 (Phase 4 /api/judge)

**端点**: `POST /api/judge` (`web/api/app.py` L161+)

**LLM 提示词** (摘要):
```
你是一位 Python 老师。学生答的: {student_answer}
题目: {problem_text}
正确答案: {correct_answer}

判断学生答案是否正确, 并给出 reasoning (具体指出对在哪/错在哪)。

返回 JSON: {correct: bool, reasoning: str}
```

**简化**: 二元对错, **没有 partial credit**。Phase 5 必修。

---

## 5. 状态更新 (Phase 5 核心) ⭐

> 这是 Bisen 重点关注的阶段——**每次答题后 5D/Bloom 数值变化的通俗化解读**

### 5.1 Step 1: L1 BKT 更新

**BKT (Bayesian Knowledge Tracing)** 跟踪**单个 skill 维度的"已掌握"主观概率**:

```python
# 简化伪代码
prior_mastery = l1.get_mastery(skill_id)  # 上次后验, 初始 0.1
if correct:
    posterior_mastery = (prior_mastery * p_learn) / P(correct)
else:
    posterior_mastery = (prior_mastery * (1 - p_learn) * p_slip) / P(wrong)
l1.set_mastery(skill_id, posterior_mastery)
```

**BKT 是 skill 维度, 跟 5D 不直接对应**。PB-Q01 (skill=python.variables) 的 BKT 跟踪"变量与赋值"这个 skill 的掌握度。

### 5.2 Step 2: append response_history

新增 1 条 dict:
```python
{
    "problem_id": "PB-Q18",
    "correct": 0,
    "bloom_level": "CREATE",
    "user_answer": "...",
    "correct_answer": "...",
    "ai_reasoning": "核心算法对, 缺 I/O",  # v0.52.2 加
    "timestamp": "2026-07-22T..."
}
```

### 5.3 Step 3: L2 MIRT MAP 估计 ⭐ 5D 数值变化的来源

**MIRT (Multidimensional Item Response Theory)** 是 5D 评估的核心算法。

**数据**:
- 历史答题序列 `[(problem_id, correct), ...]`
- 每题的 `a_specialized[5]` 维度权重
- 每题的 `difficulty` 和 `discrimination`

**目标**: 估计学生 5D 能力向量 `theta = [θ_K, θ_P, θ_S, θ_C, θ_X]` 和后验协方差 `theta_cov[5x5]`

**算法** (MAP 估计):
```python
# 1. 构造 Fisher 信息矩阵 I(θ)
#    I(θ) = Σ_i [a_i ⊗ a_i] * P_i * (1 - P_i)
#    其中 P_i = sigmoid(a_i @ θ + d_i) 是学生答对第 i 题的概率

# 2. 求解 MAP 估计
#    θ_MAP = argmax_θ [log P(D|θ) + log P(θ)]
#         = I(θ)^{-1} @ ∇ log P(D|θ)

# 3. 后验协方差
#    θ_cov = (I(θ) + prior_prec)^{-1}
```

**a_specialized 含义**:
- PB-Q18: `a=[0.9, 0.2, 0.4, 0.1, 0.1]` → 这道题 90% 测 K, 40% 测 S, 微弱测 P
- 答对 → 主要涨 K, 次要涨 S
- 答错 → 主要跌 K, 次要跌 S

### 5.4 Step 4: Bloom profile 更新

**BloomProfileState** 跟踪 L1-L6 6 个层级的 confidence 累积:

```python
bloom_levels = {L1: 0.7, L2: 0.72, L3: 0.8, L4: 0.6, L5: 0.6, L6: 0.5}
dominant_layer = "APPLY"  # 最高的层级
```

**更新规则**:
- 答对题 (bloom_level=L4): `L4_confidence += 0.05` (上限 1.0)
- 答错题: `L4_confidence -= 0.05` (下限 0.0)
- dominant_layer: 取 confidence 最高的层级

### 5.5 Step 5-6: LLM Critic (v0.52.0 修过)

**Perception 感知层**: 评估学生解释文本质量 (可选, 答对/答错)
**Misconception 检测**: 调 `/api/misconception` 端点, LLM 看学生解释 vs 8 条 Python misconception 库 (M1-M8), 输出触发哪条 (v0.52.0 修过库 ID 错配)

### 5.6 Step 7: TC 状态检测

**TC (Threshold Concept 阈值概念)** 是 ECOS 借鉴 Meyer-Land 提出的概念——某些概念掌握后**不可逆**。

**5 个 TC** (5 个 topic):
- `python.variables` (post_liminal, lbc001 已掌握)
- `python.loops` (pre_liminal, 学生在 liminal 区间)
- `python.functions` (post_liminal)
- `python.recursion` (pre_liminal)
- `python.scope` (pre_liminal)

**3 阶段**:
- **pre_liminal**: 未掌握, 信号少
- **liminal**: 在"震荡"区间, 接近但还没跨越
- **post_liminal**: 已跨越, **不可逆** (irreversible=True)

**判定逻辑**: 看答对次数 + bloom 层 + has_active_misc, 输出 3 阶段之一

### 5.7 Step 8: overall_confidence

```python
overall_confidence = mean([K.confidence, P.confidence, S.confidence, C.confidence, X.confidence])
# dim.confidence = 1 / (1 + dim.se)
# dim.se = sqrt(theta_cov[i, i])
```

### 5.8 Step 9: snapshot trajectory

每 5 题快照 1 次 state 到 trajectory (时间序列), 未来做趋势分析。

---

## 6. ⭐ 5D 数值变化的通俗化解读 (Bisen 重点)

### 6.1 5D 维度含义 (通俗化)

| 维度 | 全称 | 通俗化含义 | 答对涨 | 答错跌 |
|------|------|----------|--------|--------|
| **K (Knowledge)** | 知识 | "我**知道**这个概念/事实是什么" | K θ +0.02~0.05 | K θ -0.10~0.20 |
| **P (Procedural)** | 程序 | "我能**按步骤**做对这件事" | P θ +0.01~0.03 | P θ -0.05~0.10 |
| **S (Strategic)** | 策略 | "我能**选对**用哪种方法/策略" | S θ +0.02~0.05 | S θ -0.10~0.20 |
| **C (Conditional)** | 条件/元认知 | "我能**判断**何时用, 也能**调试**错误" | C θ +0.01~0.02 | C θ -0.03~0.05 |
| **X (eXpressive)** | 跨域迁移 | "我能在**新情境**下用这个知识" | X θ +0.01~0.02 | X θ -0.03~0.05 |

**C/X 当前为 0.10 信号权重, 实际涨跌很小**——Phase 5 重新设计后会涨得更明显。

### 6.2 SE (Standard Error) 含义

**SE = 后验标准差 = 不确定度**

- 答了 0 题: SE = 1.0 (完全不确定)
- 答了 5 题 K 主导: SE ≈ 0.9
- 答了 20 题 K 主导: SE ≈ 0.7
- 答了 100 题 K 主导: SE ≈ 0.4

**dim.confidence = 1/(1+SE)** (v0.48.0 改的):
- SE=1.0 → conf=0.5 (随机水平)
- SE=0.5 → conf=0.67
- SE=0.0 → conf=1.0 (完全确定)

**所以 confidence 不是"对错率"**, 是"估计的可信度"。学生答 100 题对 99 题, K conf 也只到 0.85, 因为还有 SE。

### 6.3 θ vs confidence 区别

- **θ (theta)**: 能力估计 (高 = 强, 低 = 弱, 0 = 平均)
- **confidence**: 估计的可信度 (高 = 估计精确, 低 = 信息量不足)

**K theta=1.18, confidence=0.56** 解读: "学生 K 维度能力估计高于平均 1.18, 但因只答了 18 题, 估计可信度只有 56%"

### 6.4 实际案例: lbc001 27 道题后 5D 变化

```
5D 现状:
  K: theta=1.253  SE=0.773  confidence=0.564
  P: theta=0.955  SE=0.699  confidence=0.589
  S: theta=0.034  SE=0.590  confidence=0.629
  C: theta=0.216  SE=0.983  confidence=0.504  [待启用]
  X: theta=0.216  SE=0.983  confidence=0.504  [待启用]
```

**通俗化解读**:
- **K 维度**: 学生知识掌握高于平均 1.25 个标准差, 但因只答 5 道 K 主导题, 估计可信度只有 56%
- **P 维度**: 学生程序知识高于平均 0.95, 答了 4 道 P 主导, 可信度 59%
- **S 维度**: 学生策略知识**接近平均** (0.03), 但答了 6 道 S 主导, 可信度 63% (信息量足够)
  - **S 暴跌 0.71 → 0.034**: lbc001 loops 答了 9 题只对 3 题 (33%), MIRT 真实反映"策略弱"
- **C 维度**: 信息量极低 (SE=0.98), confidence 接近 0.5 (随机), 实际未评估
- **X 维度**: 同 C, 未评估

---

## 7. ⭐ Bloom 数值变化的通俗化解读 (Bisen 重点)

### 7.1 Bloom 6 层含义 (通俗化)

| 层级 | 名称 | 通俗化含义 | 例题 |
|------|------|----------|------|
| **L1 Remember** | 记忆 | "我**记得**这个事实/语法" | print(x) 输出什么? |
| **L2 Understand** | 理解 | "我**理解**这个概念是什么" | 为什么 x=x+1 不矛盾? |
| **L3 Apply** | 应用 | "我能在**新问题**应用这个知识" | 用 for 循环遍历列表 |
| **L4 Analyze** | 分析 | "我能**拆解**复杂问题, 找出错误" | 找出代码 bug |
| **L5 Evaluate** | 评价 | "我能**评估**方案的优劣" | 比较两种算法效率 |
| **L6 Create** | 创造 | "我能**设计**新方案" | 设计逆序数程序 (PB-Q18) |

### 7.2 Bloom 累积规则

```python
# 答对 (correct=true):
bloom_levels[题目的 bloom_level] += 0.05  # 上限 1.0
# 答错 (correct=false):
bloom_levels[题目的 bloom_level] -= 0.05  # 下限 0.0
```

### 7.3 Bloom confidence 含义

**不是"对错率"**, 是"在该认知层级累积的可信度"。

学生答对 10 道 L1 题 + 5 道 L2 题 + 3 道 L3 题:
- L1 conf = 0.5 + 10*0.05 = 1.0 (上限)
- L2 conf = 0.5 + 5*0.05 = 0.75
- L3 conf = 0.5 + 3*0.05 = 0.65
- L4-L6 conf = 0.5 (没答过)

### 7.4 dominant_layer 含义

**`dominant_layer` = confidence 最高的层级**, 表示学生当前最擅长的认知层级。

**lbc001 案例**:
- L1=0.7, L2=0.725, L3=0.8, L4=0.6, L5=0.6, L6=0.5
- dominant_layer = "APPLY" (L3 最高)
- **解读**: "学生最擅长'应用'层 (能照着例子做), 但'分析/评价/创造'层相对弱"

**答错 Bloom 影响**:
- 答错 PB-Q18 (L6): L6 跌 0.05 (从 0.55 跌到 0.50)
- 但 L6 之前是 0.5 (没答过), 答错会让 dominant_layer 从 L3 滑到 L2 (L2 0.725 > L3 0.8 > L4 0.6? 实际 L3 还是最高)

**PB-Q18 答错 Bloom 影响**:
- L3 confidence 不变 (因为 PB-Q18 是 L6)
- L6 confidence 跌 0.05 (0.55 → 0.50)
- 但 lbc001 之前 L3 (0.8) 远高于 L6, dominant_layer 仍是 L3

### 7.5 简化: 答对/答错不等于"对 L 层级的体现"

- 答对但展示 L1 思维 (死记) → L1 涨, 但 L6/L5 不涨
- 答错但展示 L4 思维 (调试) → L4 不涨, L6 跌
- **ECOS 简化**: 当前只看对错, 不分析"思维层级" (Phase 5 必修 partial credit)

---

## 8. TC 状态变化的通俗化解读

### 8.1 TC 3 阶段含义

| 阶段 | 通俗化含义 | 例子 |
|------|----------|------|
| **pre_liminal** | 还没"开窍", 答对率不稳定 | "我大概知道 for 循环, 但用起来老错" |
| **liminal** | 在"开窍"边缘, 信号混乱 | "我能用 for 循环做简单的, 但稍微复杂就懵" |
| **post_liminal** | 已**不可逆**掌握 | "for 循环我已经完全掌握, 不可能再忘" |

**判定逻辑** (TC 状态检测):
```python
if 答对次数 >= 3 且 bloom_level >= L3:
    return "post_liminal"  # 不可逆
elif 答对 + 答错 都有, 信号混乱:
    return "liminal"
else:
    return "pre_liminal"
```

### 8.2 答错对 TC 状态的影响

- post_liminal 状态**答错**: TC **不退回** (irreversible=True), 但 progress 跌 0.05
- pre_liminal 状态答错: progress 跌 0.1
- liminal 状态答错: progress 跌 0.2 (震荡期)

**lbc001 案例**:
- TC_python.variables: post_liminal, progress=1.0, irreversible=True
  - 即使 lbc001 在 PB-Q18 答错 (variables 维度), TC 仍 post_liminal, progress 微跌
- TC_python.loops: pre_liminal, progress=0.4
  - 答对/答错都会影响 progress, lbc001 loops 答 9 题对 3 题, progress 应该跌
- TC_python.recursion: pre_liminal, progress=0.6
- TC_python.functions: post_liminal (lbc001 答对多)
- TC_python.scope: pre_liminal, progress=0.6

### 8.3 TC 状态机的不可逆性

**post_liminal + irreversible=True** = 学生已"开窍", 任何后续错题不会让 TC 状态回退。

**理论依据** (Meyer-Land): 阈值概念一旦跨越, **不会遗忘**——这是 ECOS 设计"5D 评估"的核心假设之一。

---

## 9. 干预生成 (Phase 7)

**触发条件**: engine.update Step 6 检测到 misconception, 状态 `state.C.misconception_hits` 非空

**端点**: `POST /api/intervention/<sid>` (`web/api/app.py` L311+)

**LLM 提示词** (摘要):
```
学生触发了 misconception M3 (for 循环 off-by-one)
学生答: {student_answer}
题目: {problem_text}

请生成 100-200 字干预, 用类比/解释指出学生理解错误, 给出正确理解。
```

**输出**:
```json
{
  "intervention": "小助手发现你觉得 range(5) 会包含 5...",
  "type": "EXPLANATORY",
  "misc_id": "M3",
  "misc_name": "for 循环 off-by-one",
  "correction_strategy": "range_boundary_number_line"
}
```

**前端展示**: dashboard 题目卡下方"教练干预"区域, 折叠, 点击展开

---

## 10. 个人学习画像 (Phase 8)

**端点**: `GET /api/report/<sid>` (`web/api/app.py` L249+)

**规则引擎 6 段** (`web/api/interpretation.py`):
1. **整体评估**: overall confidence 解读 (0.0-0.3 弱, 0.3-0.7 中, 0.7-1.0 强)
2. **5D 评估**: 每个维度解读
3. **Bloom 评估**: dominant_layer 解读, 各层 confidence
4. **TC 状态**: 5 个 topic 当前阶段, 跨越信号
5. **成长轨迹**: 最近 5 个 snapshot, 趋势分析
6. **下一步建议**: 基于 state 给出干预方向 (如"C 维度 SE 过高, 需要更多调试题")

**完全离线**, 无 LLM 调用, 折叠面板, 用户主动展开看

---

## 11. 完整案例: lbc001 答 PB-Q18 后的所有数值变化

**答前状态** (v0.52.1 commit 后 28 题):
```
K: θ=1.18  SE=0.78  conf=0.56
P: θ=0.96  SE=0.70  conf=0.59
S: θ=0.71  SE=0.59  conf=0.63
C: θ=0.31  SE=0.98  conf=0.50
X: θ=0.31  SE=0.98  conf=0.50
overall: 0.56
Bloom: L1=0.7, L2=0.72, L3=0.8, L4=0.6, L5=0.6, L6=0.55
dominant: APPLY (L3)
TC: variables=post, loops=pre(0.4), functions=post, recursion=pre(0.6), scope=pre(0.6)
```

**答 PB-Q18 错题后** (AI: "核心算法对, 缺 I/O"):
```
K: θ=0.96 (-0.22) ← 主测维度, 跌
P: θ=1.00 (+0.04) ← 微弱测
S: θ=0.05 (-0.66) ← 次主测, 跌 (累计效应)
C: θ=0.22 (-0.09) ← 不动 (a=0.10)
X: θ=0.22 (-0.09) ← 不动 (a=0.10)
overall: 0.56 (不变, 因为 C/X 跌, K/S 也跌, mean 抵消)
Bloom L6: 0.50 (-0.05) ← 答错 L6 跌
TC variables: post_liminal, progress 不变 (post 不可逆)
   → 但实际 progress 跌 0.05 (post 答错微跌)
TC loops: pre_liminal, progress=0.4 不变 (lbc001 没答 loops 题)
```

**通俗化解读**:
- **K 跌 0.22**: "你答错了 K 主导题, ECOS 认为你对'变量赋值'知识掌握度下降, 但实际上你展示了'提取数字位 + 倒序'的算法思维, 缺的只是 I/O"
- **S 跌 0.66** (累计): "你在 loops/recursion 策略题上多次答错, ECOS 真实反映'策略选择能力弱'"
- **Bloom L6 跌 0.05**: "你在'创造'层答错, ECOS 标记 L6 能力下降, 但你展示了'设计程序'的 L6 思维 (只是缺 I/O)"
- **overall 0.56 不变**: "5 维度涨跌抵消, 但你的真实能力(算法对)被简化处理为'答错'"

**partial credit 缺失的影响** (Phase 5 必修):
- 实际能力 ~70% 被当 0% 处理
- K 多跌 0.15, L6 多跌 0.05
- 用户看到 K 跌可能误以为"知识掌握下降", 实际只是"缺 I/O"

---

## 12. 已知限制与改进方向

| 限制 | 影响 | 改进 |
|------|------|------|
| 二元对错 | partial credit 丢失 | Phase 5 partial credit (v0.53.0 必修) |
| 错误类型不分 | 粗心 ≠ 不理解 | Phase 5 error_type 分类 |
| AI reasoning 不入库 | 后期没法回溯 | v0.52.2 已修 (response_history 存 ai_reasoning) |
| 跨题无关联 | 不识别学习模式 | Phase 5 trajectory 错误聚类 |
| C/X 0 主导题 | 5D 评估实际 3D | Phase 5 C/X 题目扩 (v0.53.0-v0.55.0) |
| Bloom 按对错 | 答对≠展示 L 层思维 | Phase 5 partial credit + demonstrated_skills |
| 答对/答错不分 | 死记 vs 深度理解 | Phase 5 partial credit 改善 |

---

## 13. 反思

ECOS 是**理论严谨 + 工程简化**的系统:
- 理论严谨: 5D/Bloom/TC/MIRT/BKT 都有认知科学依据
- 工程简化: 二元对错 + 4-gate 演示, 优先跑通而非精雕

**MIRT 框架的根本 trade-off**: "答对=有该项能力, 答错=无该项能力" 的二元假设。

**实际学习更复杂**: partial credit / error type / demonstrated skills / 跨题关联。

**Phase 5 partial credit 是 ECOS 从"理论 demo"走向"实际应用"的关键。**

---

## 14. 关联文档

- [python-basics-q-matrix-design.md](./python-basics-q-matrix-design.md) — Q 矩阵设计基础
- [ECOS-Cognitive-Intervention-Workflow.md](./ECOS-Cognitive-Intervention-Workflow.md) — 干预流程
- [../00-overview/02-architecture.md](../00-overview/02-architecture.md) — ECOS 整体架构
- [../00-overview/03-roadmap.md](../00-overview/03-roadmap.md) — ECOS 路线图
- [../../discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md](../../discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md) — Phase 5 路线图
- [../../discussions/2026-07-22-partial-credit重大学术弊端发现.md](../../discussions/2026-07-22-partial-credit重大学术弊端发现.md) — partial credit 重大弊端
- [../../discussions/2026-07-21-lbc001测试发现4个BUG分析与修复计划.md](../../discussions/2026-07-21-lbc001测试发现4个BUG分析与修复计划.md) — 4 BUG 根因

---

## 15. 版本与维护

- v1.0 (2026-07-22): 初版, Bisen 触发, 参照 Q 矩阵设计文档风格
- 后续: 每次重大版本 (v0.53.0 partial credit, v0.55.0 C/X 主导题) 同步更新本文档
- 维护者: Bisen & Claude
