# ECOS 指标体系：通俗解读

> **文档位置**：`research/10-engineering/06-metrics-and-indicators-overview.md`
> **生成时间**：2026-08-03
> **对应版本**：v0.74.1
> **适用读者**：想了解 ECOS 的人（不必先读代码；技术细节见附录 A/B/C）
> **触发**：Bisen 反馈"指标多（5D/H3/ECE/LinUCB），卡 H3 ECE 0.24，需通俗化罗列+解释+关联"。v1 偏重 ECE、通俗解读弱，v2 重排为通俗优先、技术作附录。

---

## 0. 一句话理解 ECOS，以及为什么有这么多指标

ECOS 是一个**“双 Agent 会诊”式**的教育系统：

- **CTA（认知孪生 Agent）**像一个“读懂学生的医生”--持续给学生的能力画像。
- **LCA（学习教练 Agent）**像“开处方的教练”--根据画像选下一步怎么帮学生。
- **双 Agent 互校**像“两个医生互相核对诊断”--防止单方自嗨/幻觉。
- **H3 / ECE** 是“验证核对有没有真的减少误诊”--用数据证明互校不是自吹。

每一层都需要量化指标，所以指标多。但它们其实只在回答**四个问题**：

| 问题 | 由哪层指标回答 | 通俗说 |
|---|---|---|
| ① 这个学生现在什么水平？ | CTA 认知层 | 学生画像 |
| ② 下一步该怎么帮他？ | LCA 决策层 | 干预处方 |
| ③ 系统的判断靠不靠谱？ | 双 Agent 互校层 | 互校抗幻觉 |
| ④ 怎么证明“靠得住”不是自吹？ | 验证层（ECE/H3） | 数据验证 |

> **最重要的提醒**：`confidence` 这个词在 ECOS 里指**至少 3 个不同的东西**（系统把握度 / 干预效果 / 答对概率）。这是新手最大的坑，也是 H3 一度卡住的根因（见 §4.1）。看懂这三个的区别，就懂了一大半。

---

## 1. 理解学生（CTA 认知层）

### 1.1 5D：学生的五种能力画像（不是“语数英”）

5D 不是学科分类，是**能力的五个侧面**。每道题都标了“主要测哪个侧面”（`a_specialized` 向量，5 个数）：

| 维度 | 全称 | 通俗说 | 打个比方 |
|---|---|---|---|
| **K** | Knowledge | 记住概念了吗 | 背了单词 |
| **P** | Procedure | 会按步骤操作吗 | 会套公式流程 |
| **S** | Strategy | 会选对方法吗 | 知道这题该用循环还是递归 |
| **C** | Confidence | 自我评估准不准、有没有被错误概念带偏 | “我以为对其实错” |
| **X** | External Support | 给提示/工具能用好吗 | 会查文档、用脚手架 |

**为什么是这 5 个**：传统只测 K/P（知识+技能），但学生答错常常不是因为不懂知识，而是“自信但错了”（C）或“不会用外部帮助”（X）。加上 C/X 才能解释“明明懂却答错”。

**⚠️ C 维度的历史坑**：C 的含义漂移过--早期叫 "Conditional/元认知"，v0.54.1 一度漂成 "Common mistakes"，后来锁定为 **Confidence（认知置信度，含 misconception 折扣）**。所以你在不同文档里会看到 C 的不同说法，以代码为准（见附录 A）。

### 1.2 theta_cov（常被误写成 "cov"）：这幅画像有多准

theta_cov 是 5D 画像的**“误差棒”**。

- 系统说“这学生 K=0.8”，但 0.8 准不准？theta_cov 就是这个不确定度。
- **它不是 "coverage"（覆盖率）**，是 5×5 协方差矩阵，对角线算出每维的误差范围。
- 数值大 = 系统还看不准这个学生（得多出题）；数值小 = 看准了。

### 1.3 Bloom 6 级：这题考的是哪种脑子

Bloom 把思维分 6 级（从低到高）：记住 → 理解 → 应用 → 分析 → 评价 → 创造。

- 一道“背定义”的题考 L1（记住），一道“设计新程序”的题考 L6（创造）。
- ECOS 给每级一个 0-1 的掌握概率，记录学生“在哪种思维层次上稳”。

### 1.4 TC（Threshold Concept，门槛概念）：顿悟时刻

有些概念一旦懂了就“回不去了”--比如从“变量是盒子”到“变量是标签”。ECOS 把这种概念分三阶段：

- **pre_liminal**（前门槛）：还没懂
- **liminal**（门槛中）：在挣扎，半懂不懂
- **post_liminal**（过门槛）：懂了，且不可逆（不会再退回错的概念）

TC 挂在 C 维度上（因为跨越门槛直接影响置信度）。

### 1.5 Misconception：根深蒂固的错误概念

不是“这道题错了”，是“系统性地用错误的方式理解”（如“0.1+0.2 一定等于 0.3”）。

- LLM 拿着一个**错误概念库**（`library_str`）去比对学生的答案，看命中哪个。
- 命中后会**折扣**学生的 C（自信）--因为你“自信地答错了”，正是 C 维度要抓的。
- 历史坑：曾经库 ID 错配（要 Python 库却用了数学库），导致永远找不到错误概念（见附录 A）。

### 1.6 LearningDNA：学习风格（还没启用）

记录学生偏好（视觉/听觉/动觉、是否要即时反馈等）。**目前是占位，没真实启用**（等积累够数据）。所以现在它进 LinUCB 的 context 是静态默认值，别以为它在起作用。

### 1.7 Trajectory：成长日记

每答一题，存一个“当时的快照”（5D 值 + Bloom + 时间）。相当于学生的成长日记，最多 500 条。

### 1.8 overall_confidence：系统有多确定“自己看准了”

⚠️ 这是新手最容易和“答对概率”搞混的指标。

- overall_confidence = “**我对这个学生的画像估得准不准**”的自评（5D 误差越小，把握越大）。
- **不是“学生答对概率”**。一个学生可能 overall_confidence 很高（系统很确定他 K=0.5），但他实际答对率 0.9。
- 这个区别正是 H3 一度用错指标的原因（见 §4.1 V2）。

### 1.9 mastery_prob / mastery_prob_after：掌握概率 + 历史快照

- **mastery_prob**：某能力当前的掌握概率（0-1），由 MIRT（多维项目反应理论）算出。
- **mastery_prob_after**：每题答完后存的“当时的 5D + Bloom + overall_confidence 快照”。有了它，H3 验证能用“当时的状态”而不是“最终状态”去对每道题，避免作弊。

---

## 2. 改变学生（LCA 决策层）

### 2.1 LinUCB：10 种干预手段，选哪个最可能帮到这个学生

**类比**：一个医生面对 10 种治疗手段（5 种类型 × 2 个难度），每次要根据病人当前状态选一种，试完后学“这种对这类病人效果如何”，越用越准。这就是 contextual bandit（上下文赌博机）。

- **arm（手臂/选项）**：10 种干预手段，类型有 讲解 / 练习 / 探究 / 反馈 / 元认知。
- **context（上下文）**：学生当前状态，16 维 = 5D 能力(5) + Bloom 6 级(6) + LearningDNA(5)。
- **reward（奖励）**：干预后学生答对了没（v0.69.0 后 = actual_outcome，即 partial credit）。
- **θ@x**：LinUCB 学出来的“这种干预对这种状态的学生，预期答对概率”。

> v0.69.0 之前 reward 用的是“能力进步量”（state_delta），导致 LinUCB 学的是“干预能带来多大进步”，而不是“答对概率”--这正是 V3 confidence 一度不靠谱的根因（见 §4.1）。

### 2.2 Intervention：一次具体的干预

LCA 选出来的那一次“处方”（比如“给一道 L3 的练习题，带 2 级脚手架”）。

### 2.3 expected_gain：这次干预能帮多少（预测）

预测“这次干预能让学生进步多少”。**注意：它不是答对概率，是“进步空间”**。一个已经很厉害的学生，expected_gain 会很低（没多少进步空间），但这不代表他答不对。这个区别也是 H3 用错 V1 的原因。

### 2.4 attribution：这次进步，真是这次干预带来的吗

学生这次答对了，是因为刚才的干预，还是他自己本来就会？attribution 用 state_delta 做因果归因，区分“干预的效果”和“自然波动”。注意：它和 LinUCB reward 用的是**不同信号**（reward 用答对率学预测，attribution 用进步量归因）。

---

## 3. 互校抗幻觉（双 Agent 层）

### 3.1 为什么需要互校

单个 LLM Agent 容易“自嗨”--它评判学生、生成干预、又自己评估效果，没有外部校验，容易幻觉。双 Agent 让 CTA 和 LCA 互相核对：你判的对不对，我来挑刺；我开的处方合理吗，你来把关。

### 3.2 confidence 三版（H3 卡住的根因，也是新手最大坑）

ECOS 的“双 Agent confidence”先后用过 3 个候选，**只有 V3 是答对概率**：

| 版本 | 是什么 | 回答的问题 | 是答对概率吗 | H3 用它结果 |
|---|---|---|---|---|
| **V1** expected_gain | 干预能带来多大进步 | “这次能帮多少” | ❌ 是进步空间 | 严重反向（ECE 0.73）|
| **V2** overall_confidence | 系统对画像的把握度 | “我看准学生了吗” | ❌ 是系统自信 | 仍反向（ECE 0.38）|
| **V3** dual_agent_confidence | 这次干预下学生答对概率 | “他会答对吗” | ✅ | 经校准后 0.24 |

**通俗讲为什么会错**：H3 要测“系统预测的答对概率准不准”，但 V1 测的是“进步空间”、V2 测的是“系统自信”，**拿这两个去比答对率，等于用体温计量血压**。v0.69.0 把 LinUCB 的 reward 改成 actual_outcome，θ@x 自然就变成答对概率预测（V3）。

### 3.3 calibration：把“盲目自信/自卑”校准成“准”

即便 V3 是答对概率，它一开始**系统性低估**：LinUCB 预测值总在 0.1-0.4，但学生实际答对率 0.85。根因是线性模型 + 16 维 + 54 样本，数学上拟合不了这么高的 baseline。

于是加了**后校准**（calibration）--拿历史数据拟合一个函数，把 raw 预测“拉”到接近实际：

- **Platt Scaling**：用 sigmoid 函数拉（v0.72.0）
- **Isotonic Regression**：用阶梯函数拉，更灵活（v0.73.0）
- **冷启动 fallback**：前几题还没数据时，先用 CTA 的能力均值顶上（v0.74.0）

### 3.4 actual_outcome：实际答对了吗

学生这次实际答对的程度（partial credit：0 / 0.3 / 0.6 / 1.0）。它是 LinUCB 的 reward，也是校准函数的“标准答案”，是 H3 验证里和 confidence 对照的“真值”。

---

## 4. 一次答题，系统里发生了什么（通俗数据流）

```
学生答一题
   │
   ▼
[AI 评判] 看 partial credit rubric，给 0/0.3/0.6/1.0 分 → score
   │
   ▼
[CTA 更新画像]
   ├─ 5D 能力值重估（用 score 喂 MIRT）→ theta_cov 也更新
   ├─ Bloom 6 级概率更新
   ├─ 查 misconception 库，命中就折扣 C（自信）
   ├─ 查 TC，够格就推进门槛阶段
   └─ 存 mastery_prob_after 快照 + Trajectory 日记
   │
   ▼ （开了 dual_agent 时）
[LCA 选干预]
   ├─ 读学生状态 → 16 维 context
   ├─ LinUCB UCB 选 arm（10 种干预里挑一个）
   └─ 算 dual_agent_confidence（V3 = θ@x，经 Platt/Isotonic 校准）
   │
   ▼
[互校记录] 写 calibration_log：存 confidence（V3）+ actual_outcome（score）
   │
   ▼
[H3 验证] 跑 compute_h3_ece.py：把 confidence vs actual_outcome 分 bin 比，算 ECE
```

**关键关联一句话**：score 是源头，它同时喂给 CTA（更新画像）和 dual_agent（当 reward 学答对概率 + 当校准的真值）。H3 最后拿“系统的 confidence 预测”和“score 真值”比，看系统预测得准不准。

---

## 附录 A：指标速查表（含 file:line）

| 指标 | 层 | 一句话 | 是答对概率？ | file:line |
|---|---|---|---|---|
| K/P/S/C/X | CTA | 5D 能力维度 | - | `ecos/cta/belief_state.py:30-42` |
| theta_cov | CTA | 5D 估计的 5×5 协方差（误差棒）| - | `belief_state.py:287` |
| mastery_prob | CTA | 5D 各维掌握概率 | ✅ 单 Agent 用 | `belief_engine.py:371` |
| mastery_prob_after | CTA | 每题 update 后历史快照 | ✅ 单 Agent baseline | `belief_engine.py:429` |
| overall_confidence | CTA | 系统把握度 = mean(1/(1+SE)) | ❌ 系统自信 | `belief_engine.py:418` |
| Bloom 6 级 | CTA | 认知层次掌握概率 | - | `belief_state.py:19-27` |
| TC | CTA | 门槛概念状态机（pre/liminal/post）| - | `ecos/cta/tc_detector.py` |
| Misconception | CTA | 错误概念检测（library_str 注入）| - | `misconception_detector.py:108` |
| LearningDNA | CTA | 学习风格（占位待启用）| - | `belief_state.py:171` |
| Trajectory | CTA | 成长快照（maxlen 500）| - | `belief_state.py:198` |
| LinUCB θ@x | LCA | 选 arm 的 expected_reward | ✅（reward 改后）| `linucb.py:82` |
| LinUCB UCB | LCA | θ@x + 探索 bonus | ❌ | `linucb.py:82-94` |
| expected_gain (V1) | LCA | 干预效果预测 | ❌ 增长空间 | `orchestrator.py:591` |
| CausalEffect | LCA | 因果归因（用 state_delta）| ❌ | `attribution.py:24` |
| dual_agent_confidence (V3) | 双 Agent | 答对概率预测 = LinUCB θ@x | ✅ | `dual_agent/orchestrator.py:534` |
| calibrated V3 | 双 Agent | Platt/Isotonic 校准后 V3 | ✅ | `dual_agent/calibration.py` |
| actual_outcome | 双 Agent | 实际 outcome = partial credit score | ✅（真值）| `web/api/dual_agent.py` |
| ECE | 验证 | Σ bin_conf−bin_acc 加权 | - | `ecos/metrics/ece.py:8` |
| 校准误差 | 验证 | per 样本 \|conf−acc\| | - | `compute_h3_ece.py:150` |

**MIRT theta 估计公式**（[`l2_mirt.py:104-196`](../../ecos/cta/l2_mirt.py#L104)）：`P(correct) = sigmoid(a_specialized·θ + a_general·mean(θ) − difficulty)`，N(0,I) 先验，Hessian 逆近似协方差。partial credit 直接进似然（支持 0-1 连续值）。

**各组件 confidence 字段对照**：

| 组件 | confidence 字段 | 计算方式 | file:line |
|---|---|---|---|
| 5D dim | `dim.confidence` | `1/(1+SE)`，SE=√theta_cov[i,i] | `belief_engine.py:371` |
| BloomProfile | `bloom.confidence` | `min(1.0, len(history)/30.0)` | `belief_engine.py:387` |
| TC | `tc_state.confidence` | 每次 detect `+0.1` clip [0,1] | `tc_detector.py:140-142` |
| LearningDNA | `learning_dna.confidence` | 默认 0.0（待启用） | `belief_state.py:182` |
| MisconceptionHit | `misc_hit.confidence` | LLM 返回的命中置信度 | `misconception_detector.py:152` |
| overall | `state.overall_confidence` | `mean(5D dim.confidence)` | `belief_engine.py:418-421` |

**题目前缀**（共 56 题）：

| 前缀 | 含义 | 数量 | 主导维度 |
|---|---|---|---|
| `PB-Q01`-`PB-Q26` | Python Basics 基础题 | 26 | K/P/S |
| `PB-C01`-`PB-C20` | Python Basics 编程调试 | 20 | 编程应用层扩展（非 5D 核心 C）|
| `PC-C01`-`PC-C05` | cross-subject C 主导题 | 5 | 5D 核心 C |
| `PC-X01`-`PC-X05` | cross-subject X 主导题 | 5 | 5D 核心 X |

PB-C（编程调试）和 PC-C（5D 核心 C）通过 topic 字段隔离，是 v0.54.1-d C 维度漂移的修复机制。跨学科 slot（math/chinese/english/physics/chemistry 各 10 道）当前全 0，待设计。

**partial credit rubric**（v0.54.0）：Q 矩阵 problem 的 `partial_credit_rubric` 字段，4 档分 `0.0/0.3/0.6/1.0`。LLM judge 有 rubric 时注入 4 档分，输出 `score`；`correct` 派生自 `score >= 0.6`。score 优先 correct（[`web/api/app.py:309-340`](../../web/api/app.py#L309) `_parse_judge_result`）。

---

## 附录 B：ECE / H3 卡点诊断（技术性）

### B.1 当前状态

- **H3 假设**：双 Agent 互校有效减少 LLM 幻觉（[compute_h3_ece.py:417-419](../../scripts/compute_h3_ece.py#L417)）。
- **阈值**：双 Agent ECE ≤ **0.10** + 显著优于单 Agent（项目自定义学术阈值，非 sklearn 标准）。
- **当前**：calibrated V3 ECE = **0.2366**（lbc003，56 道题），差阈值 0.14；单 Agent baseline = 0.1740（差 0.07，已接近）。
- **ECE 公式**（[`ecos/metrics/ece.py:8`](../../ecos/metrics/ece.py#L8)）：`ECE = Σ_bins(|bin_conf − bin_acc| × n_bin / n_total)`，默认 10 bin 等宽。

### B.2 版本演进（v0.69 → v0.74，ECE 0.76 → 0.24，改善 68.4%）

| 版本 | 改动 | 双 Agent V3 ECE |
|---|---|---|
| v0.69.0 | B4 reward=actual_outcome + C1 仅记录 + D1 落盘 V3 | （V3 未写入）|
| v0.70.0-d | 修策略质疑路径绕过 BUG（V3 写入率 0→98%）| 0.76 |
| v0.71.0 P0-g | 修 LinUCB A 矩阵爆炸（惩罚无上限）| 0.63 |
| v0.72.0 P0-i | Platt Scaling 后校准 | 0.28 |
| v0.73.0 P0-j | Isotonic Regression + L2 正则 | 0.28 |
| **v0.74.0 P0-k** | **冷启动 fallback**（CTA mastery 均值替 raw V3）| **0.2366** |

### B.3 卡点成因

raw V3（θ@x）系统性低估 0.54（avg conf 0.32 vs avg acc 0.85）。根因：LinUCB 是线性模型 + 16 维 + 54 样本，数学上拟合不了 lbc003 的 0.85 高 baseline。**这不是 BUG，是模型选择问题**。修了所有 BUG 仍低估，靠后校准补救。

ECE 剩余 0.24 的来源（v0.74 分段）：Platt 阶段 15 样本 ECE 0.16（单段最好）/ Isotonic 阶段 34 样本 0.25（小数据过拟合）/ 冷启动 5 样本 0.20。

### B.4 后续候选

| 方案 | 思路 | 预期 ECE | 代价 |
|---|---|---|---|
| 跨学生迁移 | global scaler + per-student 偏移，解决冷启动 | < 0.20 | 需多学生累积 30+ 题 |
| LinUCB 加 difficulty feature | 当前 16 维缺题目难度 | 不确定 | 改 context + 重训 |
| Isotonic 回退 Platt | Isotonic 在小数据过拟合 | ~0.20 | 改冷启动调度 |
| Plan B：重定义 H3 | 改测“互校减少 intervention 不一致性”等可验证子假设 | ECE 验证作废 | 推翻公开 H3 声明 |
| P2 State Engine 抽象 | 架构先行，H3 后补 | - | 架构改动大 |

> 短期 fallback 路径（冷启动 + Platt + Isotonic）已走到尽头。后续要么攒跨学生数据，要么加 feature，要么诚实重定义 H3。

### B.5 calibration_log 落盘字段

[`web/api/dual_agent.py:461-571`](../../web/api/dual_agent.py#L461) `_write_calibration_log`，写 `message_payload`（JSON）：

| 字段 | 版本 | 含义 |
|---|---|---|
| `expected_gain` | v0.60+ | V1（干预效果预测）|
| `actual_outcome` | v0.61+ | 实际 outcome（partial credit）|
| `state_overall_confidence` | v0.68.0 | V2（系统把握度）|
| `dual_agent_confidence` | v0.69.0 | V3（答对概率，θ@x 或 fallback）|
| `dual_agent_confidence_source` | v0.69.0 | `linucb` / `estimate_gain_fallback` |
| `dual_agent_confidence_calibrated` | v0.72.0 | 校准后 V3（Platt/Isotonic）|
| `dual_agent_confidence_calibrated_source` | v0.72.0 | `platt_scaling` / `isotonic_regression` / `mean_mastery_fallback` |

H3 脚本读法：V3 优先 → V2 其次 → V1 兜底（老数据自动降级）。

### B.6 LinUCB 技术细节

- **arm**：5 种 InterventionType（EXPLANATORY/PRACTICE/INQUIRY/FEEDBACK/METACOGNITIVE）× 2 难度 = 10 arm（[`intervention.py:26-40`](../../ecos/lca/intervention.py#L26)）
- **context**：16 维 = 5D θ + 6 Bloom + 5 LearningDNA（[`policy_learner.py:170-198`](../../ecos/lca/l4_optimization/policy_learner.py#L170)）
- **reward**：v0.69.0 B4 改 actual_outcome（[`orchestrator.py:379-424`](../../ecos/lca/orchestrator.py#L379)）；教学 LCA 路径仍用 state_delta
- **UCB**：`expected_reward + α·√(xᵀA_inv·x)`（[`linucb.py:82-94`](../../ecos/lca/l4_optimization/linucb.py#L82)）
- **V3**：只取 θ@x（排除 UCB 探索项），[`dual_agent/orchestrator.py:534-627`](../../ecos/dual_agent/orchestrator.py#L534)
- **冷启动判定**：`arm_pull_counts.sum() < 10`（[`orchestrator.py:430-462`](../../ecos/lca/orchestrator.py#L430)）
- **per-student 隔离**：v0.57.0 每学生独立 A/b（修多学生数据冲突）
- **dual_agent 独立实例**：v0.62.0-A，bandit 不持久化（重启冷启动），跟教学 LCA 隔离
- **显著性检验**：Welch t + Mann-Whitney U（取 max p），校准误差 per 样本 `|conf−acc|`（[`compute_h3_ece.py:332-401`](../../scripts/compute_h3_ece.py#L332)）

---

## 附录 C：相关文档

- H3 B+ 报告（最新 0.24，含 v0.69→v0.74 演进）：[discussions/2026-07-30-v0690-H3-verification-report.md](../../discussions/2026-07-30-v0690-H3-verification-report.md)
- v0.69.0 confidence 重设计 PRD（B4+C1+D1）：[discussions/2026-07-30-v0690-confidence-redesign-PRD.md](../../discussions/2026-07-30-v0690-confidence-redesign-PRD.md)
- v0.71.0 reliability diagram 诊断（V3 低估根因）：[discussions/2026-08-03-v0710-reliability-diagram-diagnosis.md](../../discussions/2026-08-03-v0710-reliability-diagram-diagnosis.md)
- H3 B 报告（V1/V2 失败）：[discussions/2026-07-30-H3-verification-B-report.md](../../discussions/2026-07-30-H3-verification-B-report.md)
- partial credit 弊端发现：[discussions/2026-07-22-partial-credit重大学术弊端发现.md](../../discussions/2026-07-22-partial-credit重大学术弊端发现.md)
- C/X 主导题路线图：[discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md](../../discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md)
- ECOS 端到端流程（8 阶段通俗化）：[research/90-mvp/06-ecos-end-to-end-flow-analysis.md](../90-mvp/06-ecos-end-to-end-flow-analysis.md)
