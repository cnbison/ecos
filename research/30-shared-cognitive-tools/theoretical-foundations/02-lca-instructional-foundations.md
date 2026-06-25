# LCA 教学法基础：干预策略的教学理论与算法基底

> **版本**：v1.0（2026-06-24）
> **性质**：ECOS LCA（Learning Coach Agent）的教学法基础借鉴文档——填补 v2.0 §3.4 "有策略列表无理论论证"的 gap
> **关系**：[v2.0 深度研究 §3.4 LCA — Policy Optimizer](../../deep-research/Cognitive-Digital-Twin-Deep-Research.md)、[v2.0 §3.5 双 Agent 互校](../../deep-research/Cognitive-Digital-Twin-Deep-Research.md)、[CTA 数学基础](01-cta-mathematical-foundations.md)
> **后续**：`03-c-dimension-content-libraries.md`（C 维度内容库）
> **维护者**：Bisen & Claude

---

## 0. LCA 教学法基础的理论定位

[v2.0 §3.4](../../deep-research/Cognitive-Digital-Twin-Deep-Research.md) 已给出 LCA 的"干预空间"——按 Bloom 层级分类的策略字典：

```python
# v2.0 §3.4 已定义（无理论论证）
bloom_to_strategy = {
    REMEMBER:  {flashcard, spaced_repetition, rote_drill},
    UNDERSTAND:{analogy, visualization, concept_mapping, socratic_questioning},
    APPLY:     {varied_practice, deliberate_practice, worked_examples},
    ANALYZE:   {problem_decomposition, comparison, concept_map_advanced},
    EVALUATE:  {multi_solution_compare, debate, critique_exercise},
    CREATE:    {project_based_learning, inquiry_learning, open_task}
}
```

**本文档填补的 gap**：v2.0 §3.4 **有策略列表无理论论证**——LCA 不知道**为什么**某个干预对某个学生有效。LCA 的"算法基底"需要教学法理论支撑。

本文档借鉴 3 大核心理论群，构成 LCA 干预策略空间的**教学法基础**：

| 理论群 | 核心命题 | 借鉴到 LCA 的哪个环节 |
|---|---|---|
| **Cognitive Load Theory (Sweller)** | 工作记忆容量有限，超载则无效 | LCA **设计题目的硬约束** |
| **Bjork 学派四件套** | 合意困难（desirable difficulties）提升长期学习 | LCA **干预策略的四把武器** |
| **Cognitive Apprenticeship (Collins/Brown)** | 专家思维可被显式教学 | LCA **教学过程的 6 阶段框架** |

---

## 1. Cognitive Load Theory（认知负荷理论）

### 1.1 核心观点（Sweller, 1988; 2019）

**Cognitive Load Theory (CLT)** 是 Sweller 提出的工作记忆容量理论。核心观点：

**三类负荷（three types of cognitive load）**：
- **内在负荷（Intrinsic Load）**：任务本身的复杂度，由学习内容与学生先验知识的关系决定——不可消除
- **外在负荷（Extraneous Load）**：呈现方式带来的负荷（无关信息、装饰元素、复杂排版）——**应最小化**
- **关联负荷（Germane Load）**：用于图式建构（schema construction）的负荷——**应最大化**

**核心公式**：
```
Total Working Memory Load = Intrinsic + Extraneous + Germane
                          ≤ Working Memory Capacity
```

**关键教学原则**：
- **工作记忆容量有限**：7±2 chunks（Miller）→ 现代研究 4±1（更多实证）
- **长时记忆无限**：通过图式（schema）把多个 chunks 整合为 single chunk
- **图式构建**：学习的本质是图式构建——教学应促进自动化的图式形成
- **expertise reversal effect**：专家觉得"显然"的内容对新手是高负荷——**呈现方式要随学习进度变化**

**经典 CLT 效应**：
- **Worked Example Effect**：给初学者完整解题样例 > 让他们独立解题
- **Completion Effect**：给初学者部分解题（如填空）> 完全独立解题
- **Split-Attention Effect**：把相关信息空间分离（如文字+图分离）会增负荷——应整合
- **Modality Effect**：用视听双通道（如视频+解说）> 纯视觉

### 1.2 与 ECOS LCA 的对接

**LCA 干预设计的硬约束**：

| LCA 行为 | CLT 约束 |
|---|---|
| 设计题目呈现方式 | 单题外在负荷 ≤ 工作记忆容量 |
| 选干预类型 | 内在负荷匹配学生 BloomProfile（如新手用 worked example，专家用独立解题）|
| 控制同时呈现的元素数 | 4±1 chunks 上限 |
| 例题 vs 独立练习的选择 | 新手偏好 worked example，进阶偏好 completion，熟练独立练习 |
| 题目排版 | 文字+图应空间整合（避免 split-attention）|

**关键设计决策**：LCA 必须**自适应 CLT 负荷**——同一道题对不同 BloomProfile 学生呈现方式不同（基于 expertise reversal effect）。

### 1.3 借鉴决策

| 决策项 | 选择 | 理由 |
|---|---|---|
| **负荷评估方式** | CTA 估计的 BloomProfile + LearningDNA | BloomProfile 高 → 内在负荷低 → 可呈现更多元素 |
| **题目呈现模板** | 学生级别参数化（4 级）| 新手 / 进阶 / 熟练 / 专家 |
| **worked example vs 独立** | 规则：连续 3 道错 → worked example；连续 5 道对 → 撤走 worked example | expertise reversal 自动化 |
| **split-attention 检查** | CTA 评估题目 + 反馈"外在负荷过高"建议 | Phase 5+ 实现 |
| **负荷量化** | 简化为元素数 + BloomProfile 差值 | MVP 不需要精确测量 |

### 1.4 实施注意事项

- **避免过度简化**：CLT 不等于"少给信息"——新手需要完整 worked example，不是简化版
- **测量难题**：CLT 的"负荷"难以客观测量，ECOS 应用 CTA 估计的 BloomProfile 作为代理变量
- **学科差异**：数学/物理等结构化学科 CLT 效应强；语文/英语等非结构化学科效应弱
- **文化适应**：中国 K12 学生长期习惯"题海"，突然加入 CLT 原则可能不适应——需要渐进引入

---

## 2. Bjork 学派四件套（合意困难）

Bjork 学派（Robert Bjork & Elizabeth Bjork）是当代学习科学最有影响力的研究群。核心命题：**学习过程中遇到的"困难"如果设计得当，反而能提升长期记忆**——这种"合意困难"包括 4 个核心效应。

### 2.1 测试效应（Testing Effect / Retrieval Practice）

**核心观点**（Roediger & Karpicke, 2006）：
> 主动提取（retrieval）比被动重读（re-reading）产生显著更强的长期记忆。**测试本身**是学习工具——而非仅仅是评估工具。

**关键实验**：
- Karpicke & Roediger (2008)：4 组学生学同一文本
  - 重读 4 次组：1 周后记住 39%
  - 测试 1 次组：1 周后记住 53%
  - 测试 2 次组：1 周后记住 61%
  - **测试 3 次组**：1 周后记住 **75%**（远超重读组）

**与 ECOS LCA 的对接**：
- LCA 应**主动插入测试**——不只是"评估是否掌握"，而是"借测试学习"
- 测试形式不限于做题——**自我解释、Teach-back（讲给别人）、自由回忆**都是测试
- 反馈紧跟测试——**测试 + 立即反馈**是黄金组合

### 2.2 合意困难（Desirable Difficulties）

**核心观点**（Bjork & Bjork, 1992, 2011）：
> 短期内让学习变难的条件，若能促进长期记忆的提取与组织，就是"合意"的。

**合意 vs 不合意的区别**：

| 类型 | 合意（desirable）| 不合意（undesirable）|
|---|---|---|
| 检索 | 测试、做题 | — |
| 时间 | 间隔练习 | 疲劳、睡眠不足 |
| 变式 | 交错练习、变式题 | 噪音 |
| 反馈 | 测试后立即反馈 | 模糊反馈 |
| 努力 | 高认知投入 | 单纯工作记忆超载 |

**关键洞察**："困难"不是越多越好——**教学法层面的合意困难**（如交错）vs **环境层面的不合意困难**（如疲劳、压力）必须区分。

### 2.3 间隔效应（Spacing Effect / Distributed Practice）

**核心观点**（Ebbinghaus, 1885 / Cepeda et al., 2006）：
> 把学习分散到多次会话，比集中学习（massed practice）效果显著更好。**间隔越长，记忆越持久**——但单次学习量下降。

**Cepeda et al. 2006 经典曲线**：对于一周后测试，**最优间隔 ≈ 1-2 天**；对于 1 年后测试，**最优间隔 ≈ 25-30 天**。

**与 ECOS LCA 的对接**：
- LCA 必须**主动安排复习时间点**——根据 CTA 估计的 P(L)（BKT 掌握概率）衰减
- 不同 Bloom 层级的间隔衰减率不同——Remember 衰减快，Apply 衰减慢，Create 几乎不衰减
- 与 [CTA 数学基础 §3 BKT](01-cta-mathematical-foundations.md) 的 P(L) 衰减整合

### 2.4 交错练习（Interleaving）

**核心观点**（Rohrer & Taylor, 2007; Kornell & Bjork, 2008）：
> 混合练习不同类型/不同概念（如 ABABAB）vs 集中练习同类型（AAAA BBB）——**交错显著提升辨别能力与远迁移**。

**关键发现**：
- 集中练习组：练习期间表现好（A 题型正确率 90%）
- 交错练习组：练习期间表现差（A 题型正确率 60%）
- **测试时**：交错组正确率 65%，集中组正确率 45%（**逆转！**）

**代价**：练习期间主观体验"更困难"——学生可能认为交错无效，需要 LCA 的解释与引导。

**与 ECOS LCA 的对接**：
- LCA 应**主动交错题目类型**——避免连续 5 道"二次函数应用题"
- 交错策略：根据 CTA 5D 状态，把多个"接近但不同"的知识点交错呈现
- 与测试效应配合：**测试 + 交错**是 LTP（long-term potentiation）最强组合

### 2.5 与 ECOS LCA 的对接（4 把武器 + 与 CTA 接口）

**Bjork 四件套是 LCA 干预策略空间的"四把武器"**：

| 武器 | 触发条件（LCA 决策规则）| 与 CTA 接口 |
|---|---|---|
| **测试效应** | 当 CTA 估计 P(L) > 0.7 但学生未做测验 → 插入测试 | 测验后 CTA 更新 P(L) |
| **合意困难** | 当学生连续 3 次顺利 → 提升难度或加入交错 | CTA 估计 BloomProfile 上调 |
| **间隔效应** | 当 CTA 估计 P(L) < 0.5 + 上次作答 N 天前 → 触发复习 | CTA 用衰减模型给 LCA 推荐时机 |
| **交错练习** | 当学生连续 5 道同类型 → 切换到不同类型 | CTA 5D 中"接近"的状态触发交错 |

**关键设计原则**：4 把武器**组合使用**——例如"间隔 + 交错 + 测试"是 LTP 最强组合。

### 2.6 借鉴决策

| 决策项 | 选择 | 理由 |
|---|---|---|
| **核心算法** | SpacedRepetitionScheduler（如 FSRS 算法）+ Interleaving scheduler | FSRS 是现代 SRS 的 SOTA |
| **间隔衰减** | 与 CTA BKT 的 P(L) 衰减整合（见 §2.3）| 避免重复建模 |
| **测试频率** | 每 5-10 道题插入 1 道测试题（非评估，是学习）| 测试效应最佳频次 |
| **交错粒度** | 学科单元内（不跨学科）| 跨学科交错可能造成过度混乱 |
| **学生反馈** | "为什么我连续错了？""因为我们故意交错类似题型"——LCA 显式解释 | 避免学生放弃 |

### 2.7 实施注意事项

- **主观体验差**：交错练习期间学生体验"更差"——LCA 必须**显式沟通**（"刚开始错是正常的"）
- **家长沟通**：家长可能不理解交错——给家长报告时强调"长期效果"，不展示练习期成绩
- **中国文化适应**：中国家长偏好"题海"——LCA 需要平衡合意困难与家长预期
- **MVP 简化**：MVP 阶段先实现"测试效应 + 间隔"，"交错"放 Phase 5+

---

## 3. Cognitive Apprenticeship（认知学徒制）

### 3.1 核心观点（Collins, Brown & Newman, 1989）

**Cognitive Apprenticeship** 把传统手工艺学徒制（master-apprentice）迁移到认知技能学习。核心观点：**专家思维可被显式教学**——通过让学习者进入"专家认知过程"。

**6 阶段教学法**：

| 阶段 | 含义 | 教学法 |
|---|---|---|
| **1. Modeling** | 专家示范完整思维过程 | "看我是怎么做的" |
| **2. Coaching** | 学习者尝试，专家观察反馈 | "我做，你看，给我反馈" |
| **3. Scaffolding** | 专家提供支持（提示、简化） | "现在你做，我提示你" |
| **4. Articulation** | 学习者表达自己的思维 | "讲给我听你怎么想的" |
| **5. Reflection** | 学习者对比自己与专家/同伴的思维 | "比较你和我做法的差异" |
| **6. Exploration** | 学习者独立探索新问题 | "现在你独立解决一个新的" |

**关键洞察**：
- **传统教学只关注 Stage 1-2**（讲解 + 练习）—— ECOS 必须支持全部 6 阶段
- **Scaffolding 的淡出**（fading）是核心——支持随学生进步逐渐撤走
- **Articulation + Reflection 是"元认知"教学**——对应 ECOS X 维度

### 3.2 与 ECOS LCA 的对接

**LCA 是 AI 教练——天然适合认知学徒制**：

| 阶段 | LCA 实现 | 与 CTA 接口 |
|---|---|---|
| **1. Modeling** | LCA 完整示范解题（解题视频 / 完整 worked example）| CTA 不参与（独立步骤）|
| **2. Coaching** | LCA 实时反馈学生尝试 | CTA 估计学生当前能力，LCA 据此给提示强度 |
| **3. Scaffolding** | LCA 根据 CTA 状态给脚手架（如 worked example + 提示 + 填空）| CTA 评估脚手架是否需要撤走 |
| **4. Articulation** | LCA 引导学生"讲给我听怎么想的"（自我解释）| CTA 评估学生元认知（X 维度）|
| **5. Reflection** | LCA 引导学生对比自己与示范/同伴的差异 | CTA 评估反思深度 |
| **6. Exploration** | LCA 给出开放问题，学生独立探索 | CTA 评估探索过程的认知结构演化 |

**关键映射**：
- **Modeling → Worked Examples**：CLT 的 worked example effect
- **Coaching → Real-time Feedback**：LCA 的核心能力
- **Scaffolding → Adaptive Worked Examples**：CLT + 教学法整合
- **Articulation → Self-Explanation Effect (Chi, 1994)**：学生自我解释可产生 30% 学习增益
- **Reflection → Metacognitive Monitoring**：CTA 的 X 维度评估
- **Exploration → Project-Based Learning**：Bloom CREATE 层级的核心

### 3.3 借鉴决策

| 决策项 | 选择 | 理由 |
|---|---|---|
| **6 阶段映射** | 完整支持，但 LCA 自动判断当前阶段 | 不让 UI 强制 6 步骤流程 |
| **Scaffolding 衰减** | 连续 N 次成功后自动撤走（CTA 触发）| expertise reversal 自动化 |
| **Articulation 触发** | 关键节点（错题后 / 阶段性学习后）| 避免过度要求自我解释 |
| **Reflection 形式** | "对比这道题与之前一道的差异"——结构化对比 | 避免开放反思（学生难以胜任）|
| **Exploration 范围** | BloomProfile L4+ 才进入 exploration | 不让新手过早探索（增加负荷）|

### 3.4 实施注意事项

- **UI 复杂度**：6 阶段对 UI 设计挑战大——MVP 阶段 LCA 在后台判断阶段，UI 只展示最终结果
- **LCA 内在人格**：LCA 需要"教练"人格（不是"老师"人格）—— 教学性 + 鼓励性 + 不直接给答案
- **可解释性**：6 阶段必须可解释——学生/家长要知道"为什么 LCA 现在问我讲思路"
- **数据收集**：6 阶段每个学生反应都应记录——为 Phase 5+ 因果归因提供数据

---

## 4. 整合：LCA 干预策略空间的完整教学法基础

把 3 大理论群 + [CTA 数学基础 §0-L4 数学栈](01-cta-mathematical-foundations.md) 整合：

### 4.1 LCA 干预决策的完整算法栈

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ L4 LCA 策略优化层          │ Cognitive Apprenticeship 6 阶段框架             │
│                            │ （决定"当前应该用哪种教学法阶段"）              │
├─────────────────────────────────────────────────────────────────────────────┤
│ L3 LCA 干预类型选择层      │ Bjork 四件套 + CLT                              │
│                            │ （决定"具体用哪种干预"+"题目如何呈现"）         │
├─────────────────────────────────────────────────────────────────────────────┤
│ L2 状态估计层（CTA）       │ MIRT + CD-CAT（见 CTA 数学基础）                │
│                            │ （CTA 估计学生状态，喂给 LCA）                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ L1 时间演化层（CTA）       │ BKT / DKT + Spaced Repetition                  │
│                            │ （CTA 估计 P(L) 衰减，触发复习时机）            │
├─────────────────────────────────────────────────────────────────────────────┤
│ L0 概率框架层（CTA）       │ POMDP / HMM（见 CTA 数学基础）                 │
│                            │ （统一概率状态空间）                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

**关键架构澄清**：
- **CTA 拥有 L0-L2**（纯统计实现）
- **LCA 拥有 L3-L4**（教学法决策）
- **L3 是"翻译层"**——把 CTA 的统计输出翻译成教学法动作

### 4.2 5 类干预 × 教学法对应表

把 v2.0 §3.4 的干预空间用教学法理论重新论证：

| 干预类型 | v2.0 §3.4 列表 | 教学法论证（本文档补充）|
|---|---|---|
| **讲解型** | analogy, visualization, concept_mapping, socratic_questioning | CLT：外在负荷最低（worked example）+ Cognitive Apprenticeship Stage 1 (Modeling) |
| **练习型** | varied_practice, deliberate_practice | Bjork：测试效应 + 间隔效应 |
| **探究型** | inquiry_learning, project_based_learning, open_task | Cognitive Apprenticeship Stage 6 (Exploration) |
| **反馈型** | （v2.0 隐含）| CLT：反馈降低 germane load 转化为 schema + Cognitive Apprenticeship Stage 2 (Coaching) |
| **元认知型** | concept_map_advanced, critique_exercise | Cognitive Apprenticeship Stage 4-5 (Articulation + Reflection) + Bjork 测试效应 |

### 4.3 参数化空间

每种干预类型有 4 个核心参数：

```
Intervention = (type, difficulty, quantity, feedback_density)
              ↓
具体实例：例如
  Intervention(
    type='varied_practice',
    difficulty=0.65,           # CLT: 与学生 BloomProfile 匹配
    quantity=5,                # Bjork: 测试效应最佳频次
    feedback_density='immediate' # CLT: 立即反馈降低 germane load
  )
```

LCA 的策略空间 = 5 类型 × 4 参数 = 20 维连续 + 5 离散 = 高维策略空间。

### 4.4 与 POMDP 决策接口

```
POMDP 视角下：
  S（隐藏状态）  ←  CTA 5D + BloomProfile + LearningDNA（来自 [CTA 数学基础 §4](01-cta-mathematical-foundations.md)）
  A（动作）      ←  LCA 干预 (type × difficulty × quantity × feedback_density)
  O（观测）      ←  学生作答、答题时间、自我解释文本
  T（转移）      ←  学习效应 + 遗忘衰减 + CLT 负荷限制
  R（奖励）      ←  CTA 估计的状态改善量（ΔP(L) + ΔBloomProfile）
  Ω（观测概率）  ←  学生行为随机性（猜测、失误、注意力）

LCA 的策略 π(a|s) = f(CTA 信念, 教学法规则, 历史效果)
```

### 4.5 与 CTA 的因果归因闭环

```
LCA 执行干预 a → 观察学生状态变化 Δs
                    ↓
              CTA 用 [Causal Inference](01-cta-mathematical-foundations.md#5-核心理论-5causal-inference因果推断) 归因：
              P(进步 | 干预 a) vs P(进步 | do(无干预))
                    ↓
              CTA 输出 CATE（CATE = ATE | 学生协变量）
                    ↓
              LCA 据此调整 policy π(a|s) 权重
```

完整闭环：**教学法理论 → LCA 干预 → CTA 因果归因 → LCA 策略更新**。

---

## 5. LCA 教学法基础的 MVP 实施路线

| Phase | 内容 | 复杂度 |
|---|---|---|
| **MVP（Phase 4）**| CLT 基础（worked example + 4 级呈现）+ Bjork 双件套（测试效应 + 间隔）+ Cognitive Apprenticeship Stage 1-3 | 中等（依赖开源：FSRS, worked-example-generator）|
| **Phase 5** | Bjork 完整四件套（+ 合意困难 + 交错）+ Cognitive Apprenticeship Stage 4-6 + 因果归因整合 | 高 |
| **Phase 6** | 完整 POMDP + POMCP 求解 + 个性化认知学徒制 | 研究级 |

**MVP 阶段 MVP 范围**（与 [01-applications.md](../../00-overview/01-applications.md) §7 一致）：
- 场景 A 学科诊断：✅ 必含（CTA 数学基础已实现）
- 场景 B 自适应干预：✅ 必含（本文档定义的 LCA 教学法基础）
- 场景 C 长期成长轨迹：⚠️ 仅学期内（依赖 CTA 数学基础 + LCA 教学法基础）
- 场景 D 教师家长协作：❌ 不含（Phase 5 再加）

**关键开源依赖**：
- `FSRS`（Free Spaced Repetition Scheduler）
- `worked-example-generator`（待实现）
- `Cognitive-Apprenticeship-Templates`（待实现）
- 教学法决策树（人工编写 + LCA 微调）

---

## 6. LCA 教学法基础 vs 现有竞品的差异

| 对比项 | 错题本 | Khan Academy | Squirrel AI | **ECOS LCA** |
|---|---|---|---|---|
| **CLT 约束** | ❌ | ❌（呈现固定）| ⚠️ 部分 | ✅ 自适应 4 级呈现 |
| **测试效应** | ❌（错题=测试，但无主动插入）| ❌ | ⚠️ 自带测验 | ✅ Bjork 测试效应 |
| **间隔效应** | ❌ | ⚠️ 固定间隔 | ⚠️ SRS 算法 | ✅ CTA BKT P(L) 衰减触发 |
| **交错练习** | ❌ | ❌ | ❌ | ✅ LCA 主动交错 |
| **认知学徒制** | ❌ | ❌ | ❌ | ✅ 6 阶段 LCA 决策 |
| **教学法理论可追溯** | ❌ | ❌ | ❌ | ✅ 3 大理论群显式标注 |

**ECOS 是市场上**唯一**把教学法理论显式编码到 AI 系统中的产品**——这是 ECOS 与所有竞品的根本方法论差异。

---

## 7. 关联文档

- **同级借鉴**：
  - [01-cta-mathematical-foundations.md](01-cta-mathematical-foundations.md) — CTA 数学基础（POMDP 概率框架 + BKT + MIRT + CD-CAT + Causal Inference）
  - `03-c-dimension-content-libraries.md` — C 维度内容库（待写）
- **核心论证**：
  - [v2.0 深度研究 §3.4 LCA — Policy Optimizer](../../deep-research/Cognitive-Digital-Twin-Deep-Research.md) — 本文档填补的 gap
  - [v2.0 深度研究 §3.5 双 Agent 互校](../../deep-research/Cognitive-Digital-Twin-Deep-Research.md) — CTA-LCA 协作机制
- **上层战略**：
  - [01-applications.md](../../00-overview/01-applications.md) §场景 B（自适应干预）完全依赖本文档
- **工程层**（待填充）：
  - [10-engineering/02-lca-policy-engine.md](../../10-engineering/02-lca-policy-engine.md) — LCA 工程实现
- **背景**：
  - [MIGRATION-FROM-SELFLAB.md](../../MIGRATION-FROM-SELFLAB.md) §2.3 AiBeing 借鉴 — 应用层工程经验
  - [shared-cognitive-science-toolbox.md §预测加工理论](../shared-cognitive-science-toolbox.md) — 预测误差在教学法中的作用

---

## 8. 版本与维护

- **v1.0**（2026-06-24）— 初版

**待办（影响本文档时同步更新）**：
- 当 `03-c-dimension-content-libraries.md` 完成后，交叉引用 §3.2 Cognitive Apprenticeship 的 Scaffolding 部分（C 维度库可作为 scaffolding 内容）
- 当 [10-engineering/02-lca-policy-engine.md](../../10-engineering/02-lca-policy-engine.md) 完成后，回填 §5 MVP 实施路线的工程细节
- 当 Phase 4 MVP 实验完成后，回填"实际效果"段落（LCA 教学法基础的实证表现）

---

**创建日期**：2026-06-24
**维护者**：Bisen & Claude
