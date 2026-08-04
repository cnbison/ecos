# ECOS 指标体系总览：5D / LinUCB / Confidence / H3 / ECE 与相互关联

> **生成时间**：2026-08-03
> **作者**：Claude（协作）+ Bisen
> **对应版本**：v0.74.0
> **触发**：Bisen 反馈"各指标和术语比较多（5D / H3 / ECE / LinUCB 等），眼下卡在 H3：ECE 0.24 仍未过 0.10 阈值，后续进程不好开展"。需要一张把所有指标、定义、关联、卡点串起来的地图。
> **权威状态源**：本文指标定义以代码为准（带 `file:line`），数字以 [discussions/2026-07-30-v0690-H3-verification-report.md](../../discussions/2026-07-30-v0690-H3-verification-report.md) §12（v0.74.0 最新重放）为准。

---

## 0. TL;DR

- **当前卡点**：H3 验证未通过。双 Agent experiment 的 calibrated V3 **ECE = 0.2366**（lbc003，56 道题），阈值 **0.10**，差 0.14；单 Agent baseline ECE = 0.1740，差 0.07（已很接近）。
- **指标分四层**：CTA 认知层（理解学生）→ LCA 决策层（改变学生）→ 双 Agent 互校层（抗幻觉）→ 验证层（H3/ECE 测互校是否真抗幻觉）。
- **核心混淆点**：`confidence` 这个词在 ECOS 里至少指 **3 个完全不同的东西**——CTA 的"系统把握度"（`overall_confidence`）、LCA 的"干预效果预测"（`expected_gain`）、双 Agent 的"答对概率预测"（`dual_agent_confidence` V3）。H3 卡住的根因就是 v0.68.0 之前用错了前两个去测答对概率。
- **演进轨迹**（v0.69→v0.74，4 轮迭代把双 Agent ECE 从 0.76 拉到 0.24，改善 68.4%）：B4 改 reward → 修路径绕过 → 修 A 矩阵爆炸 → Platt/Isotonic 后校准 → 冷启动 fallback。短期 fallback 路径已走到尽头，后续候选见 §8。

---

## 1. 指标体系全景（四层）

```
┌─────────────────────────────────────────────────────────────────┐
│  验证层（H3 / ECE / reliability diagram / 显著性检验）            │
│   测：双 Agent 互校是否真"抗幻觉"（confidence 是否校准答对概率） │
└────────────────────────▲────────────────────────────────────────┘
                         │ 读取 calibration_log 的 confidence + actual_outcome
┌────────────────────────┴────────────────────────────────────────┐
│  双 Agent 互校层（CTA ↔ LCA 互校）                              │
│   confidence 三版 V1/V2/V3 · Platt/Isotonic 后校准 · 冷启动 fallback │
│   calibration_log 落盘 · actual_outcome / partial credit / score │
└────────────────────────▲────────────────────────────────────────┘
                         │ LCA 读 CTA belief_state 选 arm；CTA 读 LCA intervention 更新
┌────────────────────────┴───────────────┐  ┌──────────────────────┐
│  LCA 决策层（改变学生）                │  │  CTA 认知层（理解学生）│
│   LinUCB (arm/context/reward/θ@x)      │←→│   5D (K/P/S/C/X) +    │
│   Intervention / expected_gain         │  │   theta_cov / Bloom 6 │
│   attribution / CausalEffect           │  │   TC / Misconception  │
└────────────────────────────────────────┘  │   LearningDNA / Trajectory │
                                            │   overall_confidence     │
                                            └──────────────────────────┘
```

**一次答题的指标流转**（§6 详述）：学生答 → LLM judge 出 `score`（partial credit 0/0.3/0.6/1.0）→ CTA 用 score 更新 5D θ + Bloom + TC + Misconception（写 `mastery_prob_after` 快照）→ LCA 读 belief_state 选 Intervention arm（LinUCB UCB）→ 双 Agent 互校算 `dual_agent_confidence`（θ@x，经 Platt/Isotonic 校准）→ 写 `calibration_log`（confidence + actual_outcome）→ H3 脚本读 calibration_log 算 ECE。

---

## 2. CTA 认知层指标（理解学生）

### 2.1 5D 维度（K / P / S / C / X）+ theta_cov

**定义**（[`ecos/cta/belief_state.py:30-42`](../../ecos/cta/belief_state.py#L30) `DimensionId` 枚举）：

| 维度 | 全称 | 含义 |
|---|---|---|
| **K** | Knowledge | 知识掌握 |
| **P** | Procedure | 程序技能 |
| **S** | Strategy | 策略能力 |
| **C** | Confidence | 认知置信度（含 misconception 折扣）|
| **X** | External Support | 外部支架 |

**C 维度的特殊性**（v0.54.1-d 漂移后锁定）：C 是 `ConfidenceDimensionState` 类型，**不是** Common mistakes。[`tests/test_dual_layer.py:40-83`](../../tests/test_dual_layer.py#L40) 用 `test_5d_core_C_is_confidence_dimension` 强制断言，扩展类定义在 [`belief_state.py:262-277`](../../ecos/cta/belief_state.py#L262)（含 `discount_factor`/`misconception_hits`/`tc_states`/`illusory_confidence_flag`）。历史教训：v0.54.1 曾把 C 漂移成"Common mistakes"，CI gate 拦截。

**theta_cov（"cov"的真正含义）**：⚠️ **不是 "coverage"，是 5D 能力向量的 5×5 联合协方差矩阵**，代表 5D 估计的不确定度。定义在 [`belief_state.py:287,303`](../../ecos/cta/belief_state.py#L287)（`theta_cov: np.ndarray = field(default_factory=lambda: np.eye(5))`），由 MIRT `estimate_theta` 基于 Hessian 逆近似返回（[`l2_mirt.py:162-194`](../../ecos/cta/l2_mirt.py#L162)）。对角线 `theta_cov[i,i]` 派生每维 SE：`dim.se = sqrt(theta_cov[i,i])`（[`web/api/belief.py:294-301`](../../web/api/belief.py#L294)）。README "5D + θ_cov" 即此。

### 2.2 5D 更新机制（MIRT + partial credit + Q 矩阵）

**MIRT theta 估计**（[`ecos/lca/l2_mirt.py:104-196`](../../ecos/cta/l2_mirt.py#L104) `estimate_theta`，Bi-factor 简化版）：
- 预测公式（`predict_probability`，line 89-94）：`P(correct|θ,item) = sigmoid(a_specialized·θ + a_general·mean(θ) − difficulty)`
- 优化目标（负对数后验，line 130-139）：似然 `Σ[r·log P + (1−r)·log(1−P)]` + 先验 `−0.5·(θ−μ)·Σ⁻¹·(θ−μ)`（N(0,I) 先验）
- 协方差：Hessian 数值逆近似（line 162-194）
- 入口：`BeliefEngine.update` Step 3（[`belief_engine.py:347-373`](../../ecos/cta/belief_engine.py#L347)），每题累积 history 后重估全量 θ

**partial credit 进入 [0,1]**：MIRT 似然数学上已支持 `r_i ∈ [0,1]` 连续值（指数加权 `r=0.7 → L = P^0.7·(1−P)^0.3`），[`tests/test_partial_credit.py:21-55`](../../tests/test_partial_credit.py#L21) 保护。`belief_engine.py:354-357` 用 `h.get("score", h.get("correct", 0))` 兜底老数据。

**Q 矩阵映射题目到 5D**：通过 `problem["a_specialized"]` 5D 区分度向量。例：
- `python.variables = [0.9, 0.2, 0.4, 0.1, 0.1]` → K 主导
- `PC-C01 = [0.2, 0.2, 0.3, 1.1, 0.2]` → C 主导
- `PC-X01 = [0.2, 0.2, 0.2, 0.2, 1.0]` → X 主导

注册路径 [`web/api/belief.py:500-507`](../../web/api/belief.py#L500)：每次 `submit_answer` 调 `engine.l2.register_item(MIRTItemParams(...))`。Q 矩阵 design 见 [`data/python_basics_q_matrix.json`](../../data/python_basics_q_matrix.json) `metadata.a_specialized_design`。

### 2.3 题目前缀 + C/X 主导题 + 跨学科 slot

**4 种前缀**（共 56 题，[`tests/test_cross_subject.py:89-122`](../../tests/test_cross_subject.py#L89)）：

| 前缀 | 含义 | 数量 | topic | 主导维度 |
|---|---|---|---|---|
| `PB-Q01`-`PB-Q26` | Python Basics 基础题 | 26 | `python.*` | K/P/S |
| `PB-C01`-`PB-C20` | Python Basics 编程调试 | 20 | `python.*` | 编程应用层扩展（**非 5D 核心 C**）|
| `PC-C01`-`PC-C05` | cross-subject C 主导题 | 5 | `cross_subject` | **5D 核心 C** |
| `PC-X01`-`PC-X05` | cross-subject X 主导题 | 5 | `cross_subject` | **5D 核心 X** |

**双层隔离**（[`test_dual_layer.py:87-166`](../../tests/test_dual_layer.py#L87)）：PB-C（编程调试，topic=`python.*`）与 PC-C（5D 核心 C，topic=`cross_subject`）通过 topic 字段隔离，problem_id 不重叠。这是 v0.54.1-d C 维度漂移的修复机制。

**v0.54.2/3 修复**：v0.54.2 加 PC-C01-C05（skill_name = 自我评估/求助决策/检查行为/misconception 检测/综合元认知），v0.54.3 加 PC-X01-X05。修复前 C/X 的 `a_specialized` 恒为 0.1 → MIRT 永不变 → CTA "5D" 实际只是 3D。修复后 lbc001 实测 C=−0.12, X=0.47。

**跨学科 slot**（[`test_cross_subject.py`](../../tests/test_cross_subject.py)）：`metadata.subject_extensions` 定义 5 学科（math/chinese/english/physics/chemistry）各 10 道设计目标（共 50 道），当前 `current_count` 全为 0（v0.56.0+ 待设计）。topic 前缀协议：`math.*`/`chinese.*`/`english.*`/`physics.*`/`chemistry.*`。

### 2.4 Bloom 6 级

**枚举**（[`belief_state.py:19-27`](../../ecos/cta/belief_state.py#L19) `BloomLevel`）：REMEMBER=1, UNDERSTAND=2, APPLY=3, ANALYZE=4, EVALUATE=5, CREATE=6。

**状态对象** `BloomProfileState`（[`belief_state.py:73-167`](../../ecos/cta/belief_state.py#L73)）：6 个 float 字段（`remember`...`create`），每个是 [0,1] 掌握概率，默认 0.5。`dominant_layer` 由 `update_dominant()`（line 110-114）取 argmax+1。

**题目关联**：Q 矩阵 problem 的 `bloom_goal_id` 格式 `"<topic>-L<n>"`（如 `python.variables-L1`），在 [`web/api/belief.py:513-521`](../../web/api/belief.py#L513) 用 `bloom_map` 映射成 `BloomLevel` enum。

**更新公式**（partial credit 版，[`belief_engine.py:381-386`](../../ecos/cta/belief_engine.py#L381)）：
- `bloom_delta = (score − 0.5) × 2.0 × step`（step 默认 0.05，warm-up 期 0.1）
- score=0 → 最大跌；score=0.5 → 中性；score=1 → 最大涨；score=0.7 → +0.4·step
- `bloom.confidence = min(1.0, len(history)/30.0)`（line 387，数据累积度语义）

### 2.5 TC（Threshold Concept，门槛概念）

**状态机** [`ecos/cta/tc_detector.py`](../../ecos/cta/tc_detector.py)。`TCState`（[`belief_state.py:238-259`](../../ecos/cta/belief_state.py#L238)）字段：`status`（pre_liminal/liminal/post_liminal）、`progress`（0-1）、`confidence`、`irreversible`。

**触发规则**（tc_detector.py:109-137）：`pre_liminal → liminal` 需 L3+ 正确且无 active misconception，progress +0.3；`liminal → post_liminal` 需 progress≥1.0 或连续 3 次 L3+ 正确。存储在 `state.C.tc_states[skill_id]`（[`belief_engine.py:400-408`](../../ecos/cta/belief_engine.py#L400)），挂在 C 维度上（TC 跨越影响置信度）。

### 2.6 Misconception（错误概念检测）

**检测器** [`ecos/cta/llm_critic/misconception_detector.py:108-185`](../../ecos/cta/llm_critic/misconception_detector.py#L108)。`library_str` 参数（line 112, 162）是注入给 LLM 的 misconception 候选库文本。

**v0.52.0 BUG 2.1**：修复前不传 `library_str` → fallback 到 K12 通用数学库 M1-M30 → 但实际需要 Python 库 M1-M8 → 库 ID 错配 → LLM 永远找不到 Python 相关 M3。修复：`BeliefEngine.__init__(misconception_library_str=...)`（[`belief_engine.py:139`](../../ecos/cta/belief_engine.py#L139)），由 `web/api/belief.py` 注入 `PYTHON_BASICS_MISCONCEPTION_LIBRARY_STR`（[`ecos/cta/content/python_basics_misconceptions.py:11`](../../ecos/cta/content/python_basics_misconceptions.py#L11)）。这是防御性自检 [3] 拦截的根因。

**命中后折扣**：写入 `state.C.misconception_hits`，`discount = 1 − min(misc_hit.confidence × 0.3, 0.3)`（[`belief_engine.py:525`](../../ecos/cta/belief_engine.py#L525)），`state.C.mastery_prob *= discount_factor`（line 529）。

### 2.7 LearningDNA（待启用）

**状态对象** [`belief_state.py:171-182`](../../ecos/cta/belief_state.py#L171) `LearningDNAState`，字段 `input_preference`/`feedback_preference`/`fatigue_pattern`/`error_pattern`/`motivation_pattern`/`confidence`。docstring 明确 `v0.1.0 占位：仅 dataclass，真实估计逻辑待 Phase 4+`。`BeliefEngine.create_initial_state` 只赋默认值（[`belief_engine.py:258`](../../ecos/cta/belief_engine.py#L258)），无 update 逻辑。`confidence` 默认 0.0。README 标注"待启用，等 ≥50 题 + 交互行为数据"。进入 LinUCB context 的 5 维 LearningDNA 是静态默认值（见 §3.1）。

### 2.8 Trajectory（成长轨迹）

**状态对象** [`belief_state.py:198-213`](../../ecos/cta/belief_state.py#L198) `TrajectoryState`，含 `snapshots: List[StateSnapshot]`（每快照含 `timestamp`/`theta_5d`/`bloom_profile`/`confidence`）+ `predictions`。`BeliefEngine.update` Step 9 每题 append（[`belief_engine.py:442`](../../ecos/cta/belief_engine.py#L442)），`trajectory_maxlen=500`。

### 2.9 overall_confidence（CTA 系统把握度）

**定义**：CTA 系统对 5D 估计的把握度，公式 `mean(5D dim.confidence)`（[`belief_engine.py:418-421`](../../ecos/cta/belief_engine.py#L418)），其中 `dim.confidence = 1/(1+SE)`（line 371，SE 越小把握越大）。语义是"**我对学生能力估得准不准**的自评"，**不是答对概率**。

⚠️ 这是 v0.68.0 H3 验证 V2 用错的指标（见 §4.1）。

### 2.10 mastery_prob / mastery_prob_after

- `mastery_prob`：5D 各维当前掌握概率（MIRT θ 经 sigmoid 映射），单 Agent baseline 的 confidence 就是它。
- `mastery_prob_after`：每题 update 后的 5D + Bloom + overall_confidence **历史快照**（[`belief_engine.py:429-439`](../../ecos/cta/belief_engine.py#L429)）。v0.64.0 加，供 H3 单 Agent baseline 用历史快照而非当前值（避免"用最终状态当所有题的 confidence"失真）。

### 2.11 CTA 各组件 confidence 字段对照

| 组件 | confidence 字段 | 计算方式 | file:line |
|---|---|---|---|
| 5D dim (K/P/S/C/X) | `dim.confidence` | `1/(1+SE)`，SE=√theta_cov[i,i] | `belief_engine.py:371` |
| BloomProfile | `bloom.confidence` | `min(1.0, len(history)/30.0)` | `belief_engine.py:387` |
| TC | `tc_state.confidence` | 每次 detect `+0.1` clip [0,1] | `tc_detector.py:140-142` |
| LearningDNA | `learning_dna.confidence` | 默认 0.0（待启用，无 update） | `belief_state.py:182` |
| MisconceptionHit | `misc_hit.confidence` | LLM 返回的命中置信度 0-1 | `misconception_detector.py:152` |
| overall | `state.overall_confidence` | `mean(5D dim.confidence)` | `belief_engine.py:418-421` |

> 防御性自检 [v0.55.0-e] 要求：dashboard 展示的组件 confidence 必须真在变（防"虚标"）。

---

## 3. LCA 决策层指标（改变学生）

### 3.1 LinUCB（上下文 bandit）

**Arm（干预类型）**（[`ecos/lca/intervention.py:26-40`](../../ecos/lca/intervention.py#L26) 5 种 InterventionType）：
- `EXPLANATORY`（讲解）/ `PRACTICE`（练习）/ `INQUIRY`（探究）/ `FEEDBACK`（反馈）/ `METACOGNITIVE`（元认知）
- 默认候选池 10 arm = 5 类型 × 2 难度，硬编码在 [`orchestrator.py:119-131`](../../ecos/lca/orchestrator.py#L119) `DEFAULT_CANDIDATE_TYPES` + `DEFAULT_CANDIDATE_DIFFICULTIES`
- `BanditConfig.n_arms: int = 10`（[`linucb.py:36`](../../ecos/lca/l4_optimization/linucb.py#L36)）

**Context feature（16 维）**（[`policy_learner.py:170-198`](../../ecos/lca/l4_optimization/policy_learner.py#L170) `_build_context`）：
- 5 维 5D theta：`[K.theta, P.theta, S.theta, C.theta, X.theta]`
- 6 维 Bloom：`[remember, understand, apply, analyze, evaluate, create]`
- 5 维 LearningDNA：`[visual(0/1), auditory(0/1), kinesthetic(0/1), immediate_feedback(0/1), weekday_motivation]`
- `CONTEXT_DIM = 16`（policy_learner.py:37），跟 `BanditConfig.context_dim` 强制对齐

**Reward 来源（v0.69.0 B4 改造前后）**（[`orchestrator.py:379-424`](../../ecos/lca/orchestrator.py#L379) `LCAEngine.update`）：
- 签名：`update(student_id, intervention, new_state, state_delta, reward=None)`
- **v0.69.0 前**：`reward=None` → `linucb_reward = max(0, min(1, state_delta))`（mastery 增长预测）
- **v0.69.0 后**：dual_agent 路径传 `reward=actual_outcome`（partial credit 0-1 答对概率）；教学 LCA 路径不传 reward，仍用 state_delta 兜底
- LinUCB 内部 `update(arm, context, reward)` 公式不变：`A_a += x·xᵀ, b_a += r·x`（[`linucb.py:96-110`](../../ecos/lca/l4_optimization/linucb.py#L96)），**改的是 reward 语义不是公式**

**UCB 选 arm**（[`linucb.py:82-94`](../../ecos/lca/l4_optimization/linucb.py#L82)）：`ucb_value = expected_reward + confidence_bound`，其中 `expected_reward = θ_a @ x`，`confidence_bound = α·√(xᵀ·A_inv·x)`（探索 bonus）。

**per-student 隔离**（orchestrator.py:264, 468-476）：v0.57.0 改每学生独立 LinUCB A/b 矩阵（修 v0.56.0 单 bandit 多学生数据冲突 BUG）。

**dual_agent 内部 LCAEngine 独立实例**（[`web/api/dual_agent.py:69-75`](../../web/api/dual_agent.py#L69)）：v0.62.0-A 决策，dual_agent 用独立 LCAEngine，bandit 数据**不持久化**（重启冷启动），跟教学 LCA（`web/api/lca.py`）完全隔离。

### 3.2 Intervention / expected_gain / _estimate_gain

- **Intervention**：LCA 选出的干预（含 type/difficulty/scaffolding_level/expected_gain）。`expected_gain` 字段语义在 v0.69.0 后分裂：dual_agent 路径 = LinUCB θ@x 预测，教学 LCA 路径 = `_estimate_gain` 简化估算。
- **`_estimate_gain`**（[`orchestrator.py:591-611`](../../ecos/lca/orchestrator.py#L591)）：`expected_gain_scale × (1 − bp_mastery) × (0.5 + 0.5 × scaffolding_level)`，默认 `expected_gain_scale=0.3`（orchestrator.py:233）。语义是"**这次干预能带来多大状态增量**"（增长空间），**不是答对概率**。
- **冷启动期 fallback**：LinUCB 没数据时（`arm_pull_counts.sum() < cold_start_threshold`，默认 10），dual_agent_confidence 走 `_estimate_gain`，source 标 `"estimate_gain_fallback"`。

### 3.3 attribution（因果归因）

**归因器** [`ecos/lca/l4_optimization/attribution.py:118-132`](../../ecos/lca/l4_optimization/attribution.py#L118)。`LCAAttribution.attribute_effect(intervention, student_id, state_delta)` 用 **state_delta，不用 reward**（[`orchestrator.py:409`](../../ecos/lca/orchestrator.py#L409) 注释"因果归因仍用 state_delta，不用 reward"）。

**CausalEffect**（attribution.py:24-33）：`state_delta`（观测状态变化）+ `estimated_ate`（ATE 估计，MVP 简化=state_delta）+ `confidence`（随样本量增长 `min(1.0, n/30.0)`）。

> 注意：LinUCB reward（v0.69.0 后 = actual_outcome）和 attribution（始终 state_delta）用的是**不同信号**。reward 用于学答对概率，attribution 用于归因干预效果。

---

## 4. 双 Agent 互校层指标（抗幻觉）

### 4.1 confidence 三版（V1 / V2 / V3）—— H3 卡住的根因

ECOS 的"双 Agent confidence"先后出现过 3 个候选，只有 V3 是答对概率：

| 版本 | 字段 | 定义 | 计算来源 | 是答对概率？ | H3 表现 |
|---|---|---|---|---|---|
| **V1** | `expected_gain` | 干预效果预测（增长空间） | `_estimate_gain` = 0.3·(1−mastery)·(0.5+0.5·scaffold) | ❌ 是"增长空间" | ECE 0.7274，严重反向 |
| **V2** | `state_overall_confidence` | 系统对 5D 估计的把握度 | `mean(5D dim.confidence)` = `mean(1/(1+SE))` | ❌ 是"系统信心" | ECE 0.3769，仍反向 |
| **V3** | `dual_agent_confidence` | 答对概率预测 | LinUCB θ@x（v0.69.0 B4 改 reward=actual_outcome 后） | ✅ 是 | ECE 0.76→0.24（经校准）|

**V1/V2 反向的统一根因**（[PRD §1.2](../../discussions/2026-07-30-v0690-confidence-redesign-PRD.md)）：H3 要测"双 Agent 对每题答对概率的预测校准度"，但 V1 测干预效果、V2 测系统把握度，**两者都不是答对概率的直接度量**，硬比 ECE 失真。v0.69.0 B4 把 LinUCB reward 改成 actual_outcome，θ@x 自动变成答对概率预测（V3）。

**V3 计算**（[`ecos/dual_agent/orchestrator.py:534-627`](../../ecos/dual_agent/orchestrator.py#L534) `_compute_dual_agent_confidence`，返回 `(float, source_str)`）：
- 非冷启动期：`context = _build_context(belief_state)`，`theta = A_inv @ b`，`expected_reward = float(theta @ context)`（**排除 UCB 探索项**），clamp [0,1]，source=`"linucb"`
- 冷启动期：走 `_estimate_gain`，source=`"estimate_gain_fallback"`
- v0.72.0+ 后校准：`calibrated = calibrator(raw_V3)`，source 跟 `active_calibrator` 联动

**C1 决策**（[PRD §3.2](../../discussions/2026-07-30-v0690-confidence-redesign-PRD.md)）：V3 confidence **仅记录，不参与 arm 选择**。arm 选择仍用 UCB（linucb.py:82-94），V3 是选完 arm 后单独算。目的：让 H3 验证归因干净（"互校抗幻觉"独立于"决策策略"）。

### 4.2 calibration（后校准）—— v0.72.0+ 把 0.76 拉到 0.24

**根因**（[v0.71 diagnosis §3](../../discussions/2026-08-03-v0710-reliability-diagram-diagnosis.md)）：raw V3（θ@x）系统性低估 0.54（avg conf 0.32 vs avg acc 0.85）。LinUCB 是线性模型 + 16 维 + 54 样本，数学上拟合不了 lbc003 这种 0.85 高 baseline 学生。修了所有 BUG 仍低估，所以靠后校准 + 冷启动 fallback。

**校准器**（[`ecos/dual_agent/calibration.py`](../../ecos/dual_agent/calibration.py)）：
- **Platt Scaling**（v0.72.0 P0-i）：`P(correct=1|raw) = sigmoid(A·raw + B)`，MLE 拟合 (raw_V3, actual_outcome) pairs
- **Isotonic Regression**（v0.73.0 P0-j）：PAVA 算法，更灵活；加 L2 正则化 `l2_lambda·(A²+B²)` 避免极端参数
- **冷启动调度**（calibration.py:316-329）：
  - `n_pairs < 5`：raw_v3（v0.74.0 前）/ mean_mastery_fallback（v0.74.0 后）
  - `5 ≤ n_pairs < 20`：platt_scaling
  - `n_pairs ≥ 20`：isotonic_regression
- **per-student tracker** `StudentCalibrationTracker`：每学生独立累积 (raw, outcome) pairs，每次 add 触发 refit

**冷启动 fallback**（v0.74.0 P0-k，[`orchestrator.py:487-528`](../../ecos/dual_agent/orchestrator.py#L487) `_cold_start_fallback`）：冷启动期用 `mean(belief_state.mastery_vector())`（5D mastery 均值，即 CTA baseline）替换 raw V3，source=`"mean_mastery_fallback"`。把冷启动 5 样本 ECE 从 0.86 降到 0.20。

### 4.3 calibration_log 落盘字段

**落盘位置** [`web/api/dual_agent.py:461-571`](../../web/api/dual_agent.py#L461) `_write_calibration_log`，写 `calibration_log` 表 `message_payload`（JSON）。

**schema 演进**：

| 字段 | 版本 | 含义 |
|---|---|---|
| `expected_gain` | v0.60+ | V1 候选（干预效果预测）|
| `actual_outcome` | v0.61+ | 实际 outcome（partial credit 0-1，score 派生）|
| `state_overall_confidence` | v0.68.0 | V2 候选（系统把握度）|
| `dual_agent_confidence` | v0.69.0 | V3 候选（答对概率预测，θ@x 或 fallback）|
| `dual_agent_confidence_source` | v0.69.0 | 来源标记（`linucb`/`estimate_gain_fallback`）|
| `dual_agent_confidence_calibrated` | v0.72.0 | 校准后 V3（Platt/Isotonic）|
| `dual_agent_confidence_calibrated_source` | v0.72.0 | 校准来源（`platt_scaling`/`isotonic_regression`/`raw_v3`/`mean_mastery_fallback`）|

**H3 脚本读法**（[`compute_h3_ece.py:222-258`](../../scripts/compute_h3_ece.py#L222)）：V3 优先 → V2 其次 → V1 兜底，老数据（v0.69.0 前）无 V3/V2 字段自动走 V1。冷启动期 source=`estimate_gain_fallback`/`mean_mastery_fallback` 单独分段算 ECE。

### 4.4 actual_outcome / partial credit / score

**partial credit rubric**（v0.54.0）：Q 矩阵 problem 的 `partial_credit_rubric` 字段，dict 键 `"0.0"/"0.3"/"0.6"/"1.0"`，值为该档描述。例 `PB-C01`（循环边界）：`{"0.0":"未识别或答错","0.3":"识别 range(1,5) 但说'5 应该在'","0.6":"识别+修复为 range(1,6) 但没说原因","1.0":"完整:位置+原因+修复"}`。`PB-Q*` 系列无此字段（走老二元 correct prompt）。

**LLM judge 消费**（[`web/api/app.py:250-306`](../../web/api/app.py#L250) `_build_judge_prompt`）：有 rubric 时注入 4 档分，要求 LLM 输出 `{"score": 0.0/0.3/0.6/1.0, "correct": bool, "reasoning": "..."}`，`correct` 派生自 `score >= 0.6`。`_parse_judge_result`（app.py:309-340）**score 优先 correct**：有 score → clamp [0,1] → `correct = score >= 0.6`；只有 correct → 派生 `score = 1.0 if correct else 0.0`。

**score 流转链**：
1. `/api/judge`（app.py:343-419）：LLM 评判 → `_parse_judge_result` 得 `(correct, score, reasoning)`
2. `/api/answer` `submit_answer(..., score=score)`（[`belief.py:468-484`](../../web/api/belief.py#L468)）
3. `Observation(score=score, correct=correct)`（belief.py:523-538）
4. `BeliefEngine.update`（belief_engine.py:267-449）：Step 2 history append `{"score": float(score)}` → Step 3 MIRT 用 score 重估 5D θ → Step 4 Bloom 用 `(score−0.5)·2·step` 更新 → Step 8 写 `mastery_prob_after` 快照
5. dual_agent 路径：`actual_outcome = score`，作为 LinUCB reward（v0.69.0 B4）+ 校准 pair 的 y

**关键修复历史**：v0.54.0 加 score 字段但 LLM judge 未消费 → v0.58.0 root cause 修复（app.py:374-382）才真正注入 rubric。v0.56.1 还定了"LLM judge 失败不写启发式 fallback"原则（422 + needs_rejudge，不污染 state）。

---

## 5. 验证层指标

### 5.1 H3 假设

**文字表述**（多源一致）：
- [compute_h3_ece.py:417-419](../../scripts/compute_h3_ece.py#L417)：`双 Agent 互校有效减少 LLM 幻觉（双 Agent vs 单 Agent 信念校准度）`
- [research/00-overview/03-roadmap.md:258](../../research/00-overview/03-roadmap.md#L258)：`H3：双 Agent 互校有效减少 LLM 幻觉（实验对比：单 Agent vs 双 Agent 信念质量）`
- [research/90-mvp/README.md:381](../../research/90-mvp/README.md#L381)：`H3 | 双 Agent 互校抗幻觉 | 双 Agent ECE ≤ 0.10 | 期望校准误差`

**通过阈值**：双 Agent ECE ≤ **0.10** + 显著优于单 Agent。

### 5.2 ECE（Expected Calibration Error）

**公式**（[`ecos/metrics/ece.py:8-10, 40-106`](../../ecos/metrics/ece.py#L8)，引用 Guo et al. 2017）：

```
ECE = Σ_bins (|bin_confidence − bin_accuracy| × n_bin / n_total)
```

- 输入：`confidences`（预测概率 0-1）+ `accuracies`（实际 outcome 0-1，可二元可 partial credit）
- 分 bin：默认 `n_bins=10`，`bin_strategy="uniform"` 等宽 `[0,0.1), [0.1,0.2), ...`，最后 bin 右闭（ece.py:86-91）
- 空 bin 跳过（ece.py:99-100）；空输入兜底返回 1.0（ece.py:73-74）

**0.10 阈值来源**：代码常量 `h3_pass_threshold = 0.10`（[compute_h3_ece.py:453](../../scripts/compute_h3_ece.py#L453)），文档约定见 [research/90-mvp/README.md:381](../../research/90-mvp/README.md#L381) + [research/00-overview/04-risks.md](../../research/00-overview/04-risks.md) A9。**项目自定义学术阈值**，非 sklearn/scipy 标准。

**单 Agent baseline 用法**（compute_h3_ece.py:100-160）：confidence = `mastery_prob_after[dimension]`（v0.64.0 历史快照），accuracy = `correct` 派生 0/1。
**双 Agent experiment 用法**（compute_h3_ece.py:166-326）：confidence = V3/V2/V1 优先，accuracy = `actual_outcome`（partial credit 0-1）。

### 5.3 reliability diagram（可靠性图）

**脚本** [`scripts/plot_reliability_diagram.py`](../../scripts/plot_reliability_diagram.py)。分 10 bin 画 mean_confidence vs mean_accuracy + 直方图。v0.71.0 诊断用，发现 raw V3 全部集中在 [0.1, 0.4] 区间，全局低估 0.54。图：[discussions/2026-08-03-v0710-reliability-diagram.png](../../discussions/2026-08-03-v0710-reliability-diagram.png) + [v0.72.0 raw vs calibrated 对比](../../discussions/2026-08-03-v0720-reliability-diagram-raw-vs-calibrated.png)。

### 5.4 显著性检验

**方法**（[compute_h3_ece.py:332-401](../../scripts/compute_h3_ece.py#L332) `compute_significance`）：Welch's t-test（参数）+ Mann-Whitney U（非参数），取 max p 保守。
- 校准误差定义：per 样本 `|confidence − accuracy|`（越小越校准）
- p < 0.05 视为统计显著（H3：双 Agent 校准误差显著 < 单 Agent）

### 5.5 校准误差 vs ECE

- **ECE**：分 bin 后的加权平均绝对偏差（bin 级）。
- **校准误差**：per 样本 `|conf − acc|`（样本级），显著性检验用。
- 两者都衡量"confidence 离 accuracy 多远"，ECE 是 bin 聚合，校准误差是样本级。

---

## 6. 指标间关联（一次答题的完整数据流）

```
学生答题
   │
   ▼
[LLM judge] /api/judge  (app.py:343)
   │  有 rubric → 4 档分 prompt；无 → 二元 prompt
   │  _parse_judge_result: score 优先 correct (>=0.6)
   ▼
score ∈ {0.0, 0.3, 0.6, 1.0}  +  correct: bool  +  reasoning
   │
   ▼
[CTA] /api/answer submit_answer(score)  (belief.py:468)
   │
   ├─→ BeliefEngine.update (belief_engine.py:267)
   │     ├─ Step 2: history append {"score"}
   │     ├─ Step 3: MIRT estimate_theta(responses=[score...]) → 5D θ + theta_cov  (l2_mirt.py:104)
   │     ├─ Step 4: Bloom delta = (score-0.5)*2*step  →  6 级概率
   │     ├─ Step 5: TC detect (L3+ 正确 → liminal 推进)  →  state.C.tc_states
   │     ├─ Step 6: Misconception detect (library_str 注入 LLM)  →  state.C.misconception_hits + discount
   │     ├─ Step 8: mastery_prob_after 历史快照  (5D + Bloom + overall_confidence)
   │     └─ Step 9: Trajectory append snapshot
   │
   │   belief_state (5D θ + theta_cov + Bloom + TC + Misconception + overall_confidence)
   │
   ▼ (ECOS_DUAL_AGENT_ENABLED=1 时)
[dual_agent] DualAgentOrchestrator.process_observation  (dual_agent/orchestrator.py)
   │
   ├─ LCAEngine.select_intervention (orchestrator.py)
   │     ├─ build_context(belief_state) → 16 维 [5D θ + 6 Bloom + 5 DNA]
   │     ├─ LinUCB UCB = θ_a@x + α√(xᵀA_inv x)  →  选 arm (Intervention)
   │     └─ chosen.expected_gain (教学 LCA: _estimate_gain; dual_agent: θ@x)
   │
   ├─ _compute_dual_agent_confidence (orchestrator.py:534)
   │     ├─ 非冷启动: raw_V3 = θ_a @ x  (排除 UCB 探索项)
   │     ├─ 冷启动: _estimate_gain fallback
   │     └─ Platt/Isotonic 校准 → calibrated_V3  (calibration.py)
   │
   ├─ LCAEngine.update(reward=actual_outcome)  ← v0.69.0 B4 改动点  (orchestrator.py:379)
   │     └─ LinUCB A_a += x·xᵀ, b_a += actual_outcome·x  (学答对概率)
   │
   ├─ attribution.attribute_effect(state_delta)  ← 注意用 state_delta 不是 reward  (attribution.py:118)
   │
   ▼
[落盘] _write_calibration_log  (dual_agent.py:461)
   message_payload = {
     expected_gain,                      # V1
     actual_outcome,                     # = score
     state_overall_confidence,           # V2
     dual_agent_confidence,              # V3 raw (θ@x 或 fallback)
     dual_agent_confidence_source,       # linucb / estimate_gain_fallback
     dual_agent_confidence_calibrated,   # V3 校准后 (Platt/Isotonic)
     dual_agent_confidence_calibrated_source  # platt_scaling / isotonic / mean_mastery_fallback
   }
   │
   ▼
[H3 验证] compute_h3_ece.py
   ├─ 单 Agent baseline: confidence=mastery_prob_after[K], accuracy=correct → ECE
   ├─ 双 Agent: confidence=V3 优先 (calibrated), accuracy=actual_outcome → ECE
   ├─ 冷启动分段 ECE (source 标记)
   └─ 显著性检验 (Welch t + Mann-Whitney U)
```

**关键关联**：
1. **score 是源头**：LLM judge 的 partial credit score 同时喂给 CTA（更新 5D/Bloom）和 dual_agent（当 actual_outcome 当 LinUCB reward + 校准 pair y）。
2. **reward vs attribution 分叉**：v0.69.0 后 LinUCB reward 用 actual_outcome（学答对概率），但 attribution 仍用 state_delta（归因干预效果）。两者语义不同，不能混。
3. **confidence 三版来自不同层**：V1/V2 来自 LCA/CTA 的"附带"字段，V3 是 dual_agent 专门算的答对概率预测。H3 只该用 V3。
4. **calibration 是后处理**：raw V3（θ@x）系统性低估，Platt/Isotonic + 冷启动 fallback 是"事后修正"，没改 LinUCB 本身。

---

## 7. 版本演进（v0.69 → v0.74，ECE 0.76 → 0.24）

| 版本 | 改动 | 双 Agent V3 ECE | 单 Agent baseline ECE |
|---|---|---|---|
| v0.69.0 | B4 reward=actual_outcome + C1 仅记录 + D1 落盘 V3 | （V3 未写入，路径绕过）| 0.2366（旧）|
| v0.70.0-d | 修策略质疑路径绕过 BUG（V3 写入率 0→98%）| 0.76 | — |
| v0.71.0 P0-g | 修 LinUCB A 矩阵爆炸（惩罚无上限，A 放大 1.6e5 倍）| 0.63 | — |
| v0.72.0 P0-i | **Platt Scaling** 后校准 | 0.28 | — |
| v0.73.0 P0-j | Isotonic Regression + L2 正则（排除 cold-start 0.22）| 0.28 | — |
| **v0.74.0 P0-k** | **冷启动 fallback**（CTA mastery 均值替 raw V3）| **0.2366** | **0.1740** |
| **累计** | 4 阶段 | **0.76 → 0.24（改善 68.4%）** | 0.1740 |

> v0.69.0 重跑后单 Agent baseline 也从 0.2366 降到 0.1740（样本从 35→56，且 v0.64.0 用 mastery_prob_after 历史快照）。

---

## 8. 当前卡点诊断（ECE 0.24）

### 8.1 卡在哪

- **现状**：calibrated V3 ECE = 0.2366 > 阈值 0.10，差 0.14。
- **但已很接近单 Agent baseline**（0.1740，差 0.07）。后校准把全局 gap 从 +0.54 拉到 −0.02（mean conf 0.87 vs mean acc 0.85，几乎完美）。
- **ECE 剩余 0.24 的来源**（[v0.74 §12.2](../../discussions/2026-07-30-v0690-H3-verification-report.md) 分段）：
  - Platt 阶段（15 样本）：ECE 0.1635（单段最好）
  - Isotonic 阶段（34 样本）：ECE 0.2456（小数据过拟合）
  - 冷启动（5 样本，v0.74 fallback 后）：ECE 0.20
- **根因**（[v0.71 diagnosis §3](../../discussions/2026-08-03-v0710-reliability-diagram-diagnosis.md)）：LinUCB θ@x 是线性模型 + 16 维 + 54 样本，数学上拟合不了 lbc003 的 0.85 高 baseline。修了所有 BUG 仍低估，靠后校准补救。**这不是 BUG，是模型选择问题**。

### 8.2 后续候选（[v0.71 diagnosis §4](../../discussions/2026-08-03-v0710-reliability-diagram-diagnosis.md) + [v0.74 §12.6](../../discussions/2026-07-30-v0690-H3-verification-report.md)）

| 方案 | 思路 | 预期 ECE | 代价 |
|---|---|---|---|
| **跨学生迁移** | global scaler（lbc001+lbc002+lbc003 历史）+ per-student 偏移，解决冷启动 | < 0.20 | 需 lbc001/lbc002 累积 30+ 题 |
| **LinUCB 加 difficulty feature** | 当前 16 维缺题目难度，加 1 维改善高 conf bin | 不确定 | 改 context 维度 + 重训 |
| **Isotonic 回退 Platt** | Isotonic 在小数据过拟合，lbc003 案例 Platt 0.16 < Isotonic 0.25 | ~0.20 | 改冷启动调度阈值 |
| **Plan B：重定义 H3** | 承认"互校抗幻觉"假设过强，改测"互校减少 intervention 不一致性 / 提升 rationale 质量"等可验证子假设 | ECE 验证作废 | 推翻 v0.63/v0.68 公开 H3 声明 |
| **P2 State Engine 抽象** | 原 gate 在 H3 pass，是否提前启动（架构先行，H3 后补）| — | 架构改动大 |

> 短期 fallback 路径（冷启动 + Platt + Isotonic）已走到尽头（v0.74 §12.8 结论）。后续要么攒跨学生数据，要么加 feature，要么诚实重定义 H3。

---

## 9. 附录：指标速查表

| 指标 | 层 | 一句话定义 | 是答对概率？ | file:line |
|---|---|---|---|---|
| K/P/S/C/X | CTA | 5D 能力维度 | — | `belief_state.py:30-42` |
| theta_cov | CTA | 5D 估计的 5×5 协方差（不确定度）| — | `belief_state.py:287` |
| mastery_prob | CTA | 5D 各维掌握概率（θ→sigmoid）| ✅ 单 Agent 用 | `belief_engine.py:371` |
| mastery_prob_after | CTA | 每题 update 后历史快照 | ✅ 单 Agent baseline | `belief_engine.py:429` |
| overall_confidence | CTA | 系统对 5D 估计的把握度 = mean(1/(1+SE)) | ❌ 系统信心 | `belief_engine.py:418` |
| Bloom 6 级 | CTA | 认知层次掌握概率 | — | `belief_state.py:19-27` |
| TC | CTA | 门槛概念状态机（pre/liminal/post）| — | `tc_detector.py` |
| Misconception | CTA | 错误概念检测（library_str 注入）| — | `misconception_detector.py:108` |
| LearningDNA | CTA | 学习风格偏好（占位待启用）| — | `belief_state.py:171` |
| Trajectory | CTA | 成长轨迹快照（maxlen 500）| — | `belief_state.py:198` |
| LinUCB θ@x | LCA | 选 arm 的 expected_reward | ❌ reward 改前 | `linucb.py:82` |
| LinUCB UCB | LCA | θ@x + α√(xᵀA_inv x)（探索）| ❌ | `linucb.py:82-94` |
| expected_gain (V1) | LCA | 干预效果预测 = 0.3·(1−mastery)·(0.5+0.5·scaffold) | ❌ 增长空间 | `orchestrator.py:591` |
| CausalEffect | LCA | 因果归因（用 state_delta）| ❌ | `attribution.py:24` |
| dual_agent_confidence (V3) | 双 Agent | 答对概率预测 = LinUCB θ@x（reward=actual_outcome 后）| ✅ | `orchestrator.py:534` |
| calibrated V3 | 双 Agent | Platt/Isotonic 校准后 V3 | ✅ | `calibration.py` |
| actual_outcome | 双 Agent | 实际 outcome = partial credit score | ✅（真值）| `dual_agent.py` |
| ECE | 验证 | Σ bin_conf−bin_acc 加权 | — | `ece.py:8` |
| 校准误差 | 验证 | per 样本 |conf−acc| | — | `compute_h3_ece.py:150` |

---

## 10. 相关文档

- H3 B 报告（V1/V2 失败）：[discussions/2026-07-30-H3-verification-B-report.md](../../discussions/2026-07-30-H3-verification-B-report.md)
- H3 B+ 报告（v0.69→v0.74 演进，含最新 0.24）：[discussions/2026-07-30-v0690-H3-verification-report.md](../../discussions/2026-07-30-v0690-H3-verification-report.md)
- v0.69.0 confidence 重设计 PRD（B4+C1+D1）：[discussions/2026-07-30-v0690-confidence-redesign-PRD.md](../../discussions/2026-07-30-v0690-confidence-redesign-PRD.md)
- v0.71.0 reliability diagram 诊断（V3 低估根因 + 4 候选方案）：[discussions/2026-08-03-v0710-reliability-diagram-diagnosis.md](../../discussions/2026-08-03-v0710-reliability-diagram-diagnosis.md)
- partial credit 弊端发现：[discussions/2026-07-22-partial-credit重大学术弊端发现.md](../../discussions/2026-07-22-partial-credit重大学术弊端发现.md)
- C/X 主导题路线图：[discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md](../../discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md)
- ECOS 端到端流程：[research/90-mvp/06-ecos-end-to-end-flow-analysis.md](../90-mvp/06-ecos-end-to-end-flow-analysis.md)
