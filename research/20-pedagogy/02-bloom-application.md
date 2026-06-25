# Bloom 分类学在 K12 的应用（Bloom's Taxonomy in K12）

> **版本**：v1.0（2026-06-25）
> **性质**：教学法层第 2 份文档——Bloom 6 层认知层级在 K12 各学段/各学科的应用与 ECOS 教学策略
> **基于**：[01-k12-cognitive-structure.md](01-k12-cognitive-structure.md)、[03-bloom-goal-library.md](../10-engineering/03-bloom-goal-library.md)（工程层第 3 份 Bloom 库）、[v0.4.0 LCA 教学法基础 §3.1 Cognitive Apprenticeship 6 阶段](../30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md)、[v2.0 §1.4 Bloom 目标空间](../deep-research/Cognitive-Digital-Twin-Deep-Research.md)、[v0.3.0 CTA 数学基础 §2 CD-CAT](../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md)
> **后续**：[03-learning-strategies.md](03-learning-strategies.md)、[04-zpd-application.md](04-zpd-application.md)
> **维护者**：Bisen & Claude

---

## 0. 模块定位

### 0.1 核心职责

**Bloom 在 K12 的应用**文档回答：**ECOS 如何用 Bloom 6 层认知层级解决"会做但不会想"的中国教育痛点？**

- [v0.1 综合报告 §第八部分 Bloom 分类学的价值](../gpt-dialogues/04-cognitive-digital-twin-v01-report.md) 给出 6 层定义
- [03-bloom-goal-library.md](../10-engineering/03-bloom-goal-library.md) 给出工程化数据结构
- **本文档填补**：教学法落地——如何在 K12 各学段/各学科中**实际应用** Bloom 目标

### 0.2 与 ECOS 其他模块的关系

```
┌─────────────────────────────────────────────────────────────┐
│ Bloom 在 K12 的应用（本文档）—— 教学法落地                  │
│   ↓ 跨层级策略 + 评估方法                                  │
│ CTA（[01-cta-belief-engine.md](../10-engineering/01-cta-belief-engine.md)）│
│   ↓ BloomProfile 估计                                       │
│ LCA（[02-lca-policy-engine.md](../10-engineering/02-lca-policy-engine.md)）│
│   ↓ 选择目标 Bloom 层 + 干预策略                            │
│ Bloom Library（[03-bloom-goal-library.md](../10-engineering/03-bloom-goal-library.md)）│
│   ↓ 各知识点 × Bloom 层目标                                 │
└─────────────────────────────────────────────────────────────┘
```

### 0.3 核心问题

> **中国教育痛点**：学生能解题（Apply），但不会分析（Analyze）、评价（Evaluate）、创造（Create）。
> **ECOS 解决方案**：用 BloomProfile 显式建模 6 层分布，主动引导学生从 L3 向 L4-L6 进阶。

---

## 1. Bloom 6 层在 K12 各学段的分布

### 1.1 各年级 Bloom 层级达标期望

| 年级 | 主要达标层级 | 次要层级 | 备注 |
|---|---|---|---|
| 1-2 年级 | L1 Remember | — | 几乎纯记忆 |
| 3-4 年级 | L1-L2 | L3 萌芽 | 守恒 + 简单应用 |
| 5-6 年级 | L1-L2 | L3 | 多步应用题 |
| 7 年级 | L1-L3 | L4 萌芽 | 变量 + 函数 + 简单分析 |
| 8 年级 | L2-L3 | L4 | 函数 + 几何证明起步 |
| 9 年级 | L3 | L2 / L4 | 中考导向 + 分析能力 |
| 10 年级 | L3 | L4 | 高中函数 + 分析 |
| 11 年级 | L3-L4 | L5 萌芽 | 高考导向 + 评价能力 |
| 12 年级 | L3-L4 | L5 / L6 | 自主学习 + 创造萌芽 |

### 1.2 小学阶段（1-6 年级）Bloom 分布

```
L1 ████████████████████ 80-90%
L2 ████ 10-20%
L3 █ <5%
L4-L6 — 不适用
```

**特征**：

- 几乎纯记忆 + 理解（L1 主导）
- L3 Apply 极少（小学阶段主要是简单应用）
- L4-L6 不适用（Piaget 具体运算阶段限制）

**ECOS 行动**：
- CTA 主要估计 L1 + L2
- LCA 干预以 EXPLANATORY（讲解）+ PRACTICE（练习）为主
- 不强推 L3+（避免认知超载）

### 1.3 初中阶段（7-9 年级）Bloom 分布

```
L1 ██████ 25-30%
L2 ████████████ 25-30%
L3 ████████████████ 20-30%
L4 ██ 5-10%
L5-L6 █ <5%
```

**特征**：

- L1-L2 仍重要（基础记忆 + 概念理解）
- L3 Apply 显著提升（中考导向）
- L4 Analyze 萌芽（几何证明）
- L5-L6 偶尔（综合题）

**ECOS 行动**：
- CTA 估计 L1-L4（完整 5D 启用）
- LCA 干预类型多样化（PRACTICE + EXPLANATORY + INQUIRY + METACOGNITIVE）
- 重点支持 L3 → L4 进阶（通过 Cognitive Apprenticeship Stage 4-5）

### 1.4 高中阶段（10-12 年级）Bloom 分布

```
L1 ████ 15-20%
L2 ████████ 20-25%
L3 ████████████████ 30-40%
L4 ██████████ 15-20%
L5 ███ 5-10%
L6 █ <5%
```

**特征**：

- L3 Apply 主导（解题为主）
- L4 Analyze 显著提升（高考导数 + 解析几何）
- L5 Evaluate 萌芽（议论文写作）
- L6 Create 偶尔（研究性学习）

**ECOS 行动**：
- CTA 估计 L1-L5
- LCA 干预以 PRACTICE + INQUIRY 为主
- 强推 L4 → L5 进阶（议论文 + 评价）
- 探索 L6（项目式学习）

---

## 2. 各学科 Bloom 目标分布

### 2.1 数学

[03-bloom-goal-library.md §3 数学 8 核心知识点](../10-engineering/03-bloom-goal-library.md) 已给出具体定义。

**各 Bloom 层占比**（基于中国课程标准）：

| 学段 | L1 | L2 | L3 | L4 | L5 | L6 |
|---|---|---|---|---|---|---|
| 小学 | 70% | 20% | 8% | 2% | 0% | 0% |
| 初中 | 30% | 25% | 30% | 10% | 4% | 1% |
| 高中 | 20% | 25% | 35% | 15% | 4% | 1% |

**数学的 Bloom 特征**：
- L1-L3 主导（解题导向）
- L4 Analyze 是难点（证明、分类）
- L5-L6 罕见（奥数 / 研究项目）

### 2.2 物理

**各 Bloom 层占比**：

| 学段 | L1 | L2 | L3 | L4 | L5 | L6 |
|---|---|---|---|---|---|---|
| 初中 | 30% | 30% | 25% | 12% | 3% | 0% |
| 高中 | 20% | 25% | 30% | 18% | 5% | 2% |

**物理的 Bloom 特征**：
- L1-L3 主导（公式 + 解题）
- L4 Analyze 是核心（力学分析、电磁分析）
- L5 Evaluate 是难点（模型选择、方案评估）
- L6 Create 通过实验设计培养

### 2.3 语文

**各 Bloom 层占比**（与数学/物理显著不同）：

| 学段 | L1 | L2 | L3 | L4 | L5 | L6 |
|---|---|---|---|---|---|---|
| 小学 | 60% | 30% | 5% | 5% | 0% | 0% |
| 初中 | 30% | 35% | 10% | 15% | 8% | 2% |
| 高中 | 25% | 30% | 10% | 20% | 12% | 3% |

**语文的 Bloom 特征**：
- L1-L2 主导（记忆 + 理解）
- L3 Apply 较少（语言应用不同于数学）
- L4 Analyze 重要（修辞分析、文言文理解）
- L5 Evaluate 是核心（议论文 / 文学评价）
- L6 Create 是终极目标（写作）

### 2.4 英语

**各 Bloom 层占比**（与语文类似但更侧重应用）：

| 学段 | L1 | L2 | L3 | L4 | L5 | L6 |
|---|---|---|---|---|---|---|
| 小学 | 50% | 30% | 15% | 5% | 0% | 0% |
| 初中 | 30% | 30% | 25% | 12% | 3% | 0% |
| 高中 | 25% | 25% | 25% | 18% | 5% | 2% |

**英语的 Bloom 特征**：
- L1-L3 主导（词汇 + 语法 + 应用）
- L4 Analyze 重要（阅读理解）
- L5-L6 较少（写作）

### 2.5 化学 / 生物

**各 Bloom 层占比**（与物理类似）：

| 学段 | L1 | L2 | L3 | L4 | L5 | L6 |
|---|---|---|---|---|---|---|
| 初中（化学）| 30% | 30% | 25% | 12% | 3% | 0% |
| 高中（化学）| 20% | 25% | 30% | 18% | 5% | 2% |
| 高中（生物）| 25% | 25% | 30% | 15% | 4% | 1% |

**化学/生物特征**：
- L1-L3 主导（元素 + 反应 + 计算）
- L4 Analyze 重要（实验分析）
- L5 Evaluate 较少

---

## 3. Bloom 跨层级教学策略

### 3.1 Remember → Understand 的进阶

**关键挑战**：学生能背诵公式但不理解意义。

**ECOS 教学策略**：

```
L1: "二次函数顶点公式 y = a(x-h)² + k"
        ↓ (CLT NOVICE + 讲解型)
        ↓ 类比：把抛物线想象成山丘，h 是山顶横坐标，k 是山顶纵坐标
        ↓ (Cognitive Apprenticeship Stage 1: Modeling)
L2: "为什么 a 决定开口方向？为什么 h 是对称轴？"
```

**具体方法**：
- 讲解型干预（EXPLANATORY）+ CLT NOVICE
- 类比教学（v0.4.0 §1 CLT）
- 教师示范（CA Stage 1 Modeling）
- 学生复述（避免"鹦鹉学舌"）

### 3.2 Understand → Apply 的进阶

**关键挑战**：学生理解概念但不会迁移到新情境。

**ECOS 教学策略**：

```
L2: "理解抛物线的几何意义"
        ↓ (CLT DEVELOPING + 练习型)
        ↓ 应用：建立实际情境的二次函数模型（"投掷运动的最大高度"）
        ↓ (CA Stage 2-3: Coaching + Scaffolding)
L3: "能用顶点公式解决新情境的最值问题"
```

**具体方法**：
- 练习型干预（PRACTICE）+ CLT DEVELOPING
- 变式练习（v0.4.0 §2 Bjork 测试效应）
- 工作ed example → 填空 → 独立解题（CLT 4 级）
- 即时反馈 + rationale

### 3.3 Apply → Analyze 的进阶（核心难点）

**关键挑战**：学生会解题但不会拆解——这是中国教育最大痛点。

**ECOS 教学策略**：

```
L3: "会用顶点公式求最值"
        ↓ (CLT PROFICIENT + 探究型)
        ↓ 分析：对比"配方求最值" vs "导数求最值"
        ↓ 拆解：配方法的步骤 → 识别模式
        ↓ (CA Stage 4-5: Articulation + Reflection)
L4: "能分析两种方法的优劣，选择合适方法"
```

**具体方法**：
- 探究型干预（INQUIRY）+ CLT PROFICIENT
- 拆解 + 比较（修辞手法辨析、几何证明）
- **Articulation（自我解释）**：学生讲出思路（[v0.4.0 §3.1 CA Stage 4](../30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md)）
  - Chi 1994：自我解释可产生 30% 学习增益
- **Reflection（对比反思）**：学生对比自己与示范的差异
- 元认知型干预（METACOGNITIVE）

### 3.4 Analyze → Evaluate → Create 的进阶（K12 难点）

**关键挑战**：学生达到 L4 后很少进入 L5-L6（K12 评价 + 创造最难培养）。

**ECOS 教学策略**：

```
L4: "能分析两种方法"
        ↓ (CLT EXPERT + 探究型)
        ↓ 评价：基于标准评判"这道题用哪种方法更优"
        ↓ 辩护：为什么这样选？有没有反例？
        ↓ (CA Stage 5-6: Reflection + Exploration)
L5: "能评价方法并基于标准辩护"
        ↓ 探索：设计新题型 / 写议论文
L6: "能综合多种方法创造新方案"
```

**具体方法**：
- 探究型干预（INQUIRY）+ CLT EXPERT
- 议论文写作（L5 Evaluate 核心）
- 项目式学习（PBL）
- 学生互评（peer review）—— 同时培养 L5 Evaluate

**K12 L5-L6 的特殊考量**（[04-risks.md §B1 Bloom 风险](../00-overview/04-risks.md)）：
- L5-L6 在 K12 不常达到，但 ECOS 应**主动引导**——不能因为"难"就放弃
- 高中阶段可重点培养 L5（议论文 + 方案评价）
- L6 通过研究性学习 + 项目式学习培养

---

## 4. BloomProfile 评估方法

### 4.1 行为锚定评估（与课程标准对接）

[03-bloom-goal-library.md §3.3](../10-engineering/03-bloom-goal-library.md) 已给出课程标准对接。本节强调 BloomProfile 的评估方法：

```python
class BloomProfileEvaluator:
    """BloomProfile 评估——行为锚定"""

    def evaluate(
        self,
        student_id: str,
        skill_id: str,
        bloom_layer: BloomLevel,
        observation: 'Observation',
    ) -> float:
        """评估学生在某 Bloom 层的掌握度"""
        # 1. 检查认知行为动词是否达成
        behavior_verbs = BLOOM_LEVELS[bloom_layer].cognitive_verb
        for verb in behavior_verbs:
            if not self._check_behavior(verb, observation):
                return 0.0  # 任一行为动词未达成 → 该层未掌握

        # 2. 检查评估标准
        criteria = BLOOM_LEVELS[bloom_layer].assessment_criteria
        for criterion in criteria:
            if not self._check_criterion(criterion, observation):
                return 0.5  # 部分达成

        return 1.0  # 完全达成

    def _check_behavior(self, verb: str, observation: 'Observation') -> bool:
        """检查认知行为动词（如"解释"、"归纳"）"""
        # 使用 LLM rubric 辅助
        prompt = f"学生作答中是否包含'{verb}'的认知行为？..."
        return self.llm_judge(prompt, observation.text_response)
```

### 4.2 多题取样（避免单题偏差）

[01-cta-belief-engine.md §2.1 BeliefState](../10-engineering/01-cta-belief-engine.md) 中 BloomProfile 是 6 层分布——每层应有多个样本题目。

**MVP 取样策略**：

| Bloom 层 | 每层最少样本数 | 评估时间 |
|---|---|---|
| L1 Remember | 3-5 道 | 5-10 分钟 |
| L2 Understand | 3-5 道 | 10-15 分钟 |
| L3 Apply | 5-10 道 | 15-30 分钟 |
| L4 Analyze | 3-5 道 | 20-40 分钟 |
| L5 Evaluate | 2-3 道 | 30-60 分钟 |
| L6 Create | 1-2 个项目 | 60+ 分钟 |

**频率**：MVP 阶段每周 1 次 BloomProfile 评估（避免频繁打扰学生）。

### 4.3 LLM rubric 辅助（主观题）

**问题**：L4-L6 评估需要 LLM rubric（主观性强）——但这违反 [v0.3.0 + v0.4.0 硬底线](../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md)（数学层不用 LLM）。

**解决方案**：LLM rubric 仅用于**主观题评估**（如议论文、阅读理解），**不用于数学/物理等结构化答案**。

```python
class LLMRubricEvaluator:
    """LLM rubric——用于语文主观题 L4-L6 评估"""

    def evaluate_essay(
        self,
        essay_text: str,
        bloom_target: BloomLevel,
        rubric_criteria: List[str],
    ) -> float:
        """评估议论文（语文 L5）"""
        prompt = f"""你是语文教师。基于以下评分标准评估议论文：

Bloom 目标层：{bloom_target.name} ({bloom_target.name_cn})
评分标准：
{chr(10).join(rubric_criteria)}

学生作文：
{essay_text}

请给出 0-1 的评分，并简述理由。
"""
        return self.llm_client.generate(prompt, temperature=0.2)
```

**注意事项**：
- LLM rubric 仅用于**感知 + 解释**层（v0.3.0 边界）
- 数学/物理等结构化答案**绝不用 LLM rubric**（避免幻觉污染）
- LLM rubric 输出必须**人工审核样本**（每月抽样）

---

## 5. 解决"会做但不会想"的中国教育痛点

### 5.1 痛点分析

中国 K12 教育的典型痛点：

> **学生能解题（L3 Apply）但不会分析（L4 Analyze）、评价（L5 Evaluate）、创造（L6 Create）**

**根本原因**（基于 [v0.1 §第二部分 教育的真正问题](../gpt-dialogues/04-cognitive-digital-twin-v01-report.md)）：

1. **教学导向**：以"掌握知识点"为目标（L1-L3），而非"培养思维能力"（L4-L6）
2. **评估导向**：考试以"会解题"为标准（L3），不评估"会思考"（L4-L6）
3. **练习导向**：题海战术强化 L3，但弱化 L4-L6

### 5.2 ECOS 解决方案：BloogProfile 高层引导

ECOS 通过显式建模 BloomProfile 主动解决此痛点：

```
传统教学：
  目标 → 解题（L3）
  评估 → 考试分数
  反馈 → 错题订正

ECOS 教学：
  目标 → BloomProfile 6 层分布（含 L4-L6）
  评估 → BloomProfile 6 层掌握度（CTA 估计）
  反馈 → "你在 L3 已经掌握，但 L4 Analyze 较弱——需要拆题训练"
```

**具体机制**：

1. **CTA 显式建模 6 层分布**（不仅是 L3）——学生能看到自己的 L4-L6 缺口
2. **LCA 主动引导高层 Bloom** ——Contextual Bandits 选择"提升 L4"的干预（即使 L3 还可优化）
3. **教学策略多元化** ——INQUIRY + METACOGNITIVE 干预（不是纯 PRACTICE）
4. **可视化展示** ——雷达图显示 6 层分布，家长/教师看到 L4-L6 缺口

### 5.3 实施步骤

| 步骤 | 内容 | 时间 |
|---|---|---|
| **Step 1** | CTA 估计 BloomProfile 6 层分布（首次完整评估）| MVP 启动时 |
| **Step 2** | 识别 L4-L6 缺口（vs 同年级标准）| 评估后立即 |
| **Step 3** | LCA 推荐"L4 提升"干预（即使 L3 仍有缺口）| 每次干预时 |
| **Step 4** | 每月重新评估 BloomProfile，跟踪 L4-L6 进步 | 每月 |
| **Step 5** | 家长/教师端展示 6 层雷达图 | 实时 |

---

## 6. Bloom 与课程标准对接

### 6.1 中国课程标准中的 Bloom 层级

中国教育部课程标准（数学 2011 版 + 2022 版）的行为动词：

| 课程标准动词 | 对应 Bloom 层 |
|---|---|
| 了解 / 知道 / 识别 | L1 Remember |
| 理解 / 解释 / 说明 | L2 Understand |
| 应用 / 运用 / 计算 | L3 Apply |
| 分析 / 比较 / 推断 | L4 Analyze |
| 评价 / 评判 / 反思 | L5 Evaluate |
| 设计 / 创造 / 综合 | L6 Create |

### 6.2 课程标准与 ECOS BloomGoal 的映射

```python
# ecos/bloom/curriculum/mapper.py
CURRICULUM_VERB_TO_BLOOM = {
    '了解': BloomLevel.REMEMBER,
    '知道': BloomLevel.REMEMBER,
    '识别': BloomLevel.REMEMBER,
    '理解': BloomLevel.UNDERSTAND,
    '解释': BloomLevel.UNDERSTAND,
    '说明': BloomLevel.UNDERSTAND,
    '应用': BloomLevel.APPLY,
    '运用': BloomLevel.APPLY,
    '计算': BloomLevel.APPLY,
    '分析': BloomLevel.ANALYZE,
    '比较': BloomLevel.ANALYZE,
    '推断': BloomLevel.ANALYZE,
    '评价': BloomLevel.EVALUATE,
    '评判': BloomLevel.EVALUATE,
    '反思': BloomLevel.EVALUATE,
    '设计': BloomLevel.CREATE,
    '创造': BloomLevel.CREATE,
    '综合': BloomLevel.CREATE,
}
```

### 6.3 课程标准与 BloomProfile 的对应

| 课程标准达成 | BloomProfile 阈值 |
|---|---|
| 课程标准要求 L1 | BloomProfile.remember ≥ 0.7 |
| 课程标准要求 L2 | BloomProfile.understand ≥ 0.7 |
| 课程标准要求 L3 | BloomProfile.apply ≥ 0.6 |
| 课程标准要求 L4 | BloomProfile.analyze ≥ 0.5 |
| 课程标准要求 L5 | BloomProfile.evaluate ≥ 0.4 |
| 课程标准要求 L6 | BloomProfile.create ≥ 0.3 |

---

## 7. ECOS 教学建议（基于 Bloom 6 层）

### 7.1 给学生的建议

| 当前层级 | 建议 |
|---|---|
| L1 不足 | 加强记忆（间隔重复 + 测试）|
| L1 足够但 L2 不足 | 多解释（Articulation）|
| L2 足够但 L3 不足 | 多练习（变式练习）|
| L3 足够但 L4 不足 | 多分析（拆题 + 比较）|
| L4 足够但 L5 不足 | 多评价（议论文 / 方案选择）|
| L5 足够但 L6 不足 | 多创造（项目式学习）|

### 7.2 给教师的建议

1. **显式标注 Bloom 层**——教案和作业明确标注 L1-L6
2. **不要跳过 L2**——确保学生理解而不仅是记忆
3. **强推 L4**——通过拆题 + 比较培养分析能力（最难但最重要）
4. **培养 L5**——通过议论文 / 方案评价
5. **允许 L6**——通过项目式学习 / 研究性学习

### 7.3 给家长的建议

1. **不要只关注分数**——分数只反映 L3，分数高 ≠ 思维强
2. **关注 BloomProfile**——6 层雷达图比单点分数更有信息
3. **L4-L6 才是长期竞争力**——这些能力在大学和职场更重要

---

## 8. 关联文档

- **同级教学法层**：
  - [01-k12-cognitive-structure.md](01-k12-cognitive-structure.md) — K12 各学段差异化建模
  - [03-learning-strategies.md](03-learning-strategies.md) — 学习策略空间
  - [04-zpd-application.md](04-zpd-application.md) — ZPD 在 ECOS 的应用
- **工程层**（按本文档配置调整）：
  - [03-bloom-goal-library.md](../10-engineering/03-bloom-goal-library.md) — BloomGoal 数据结构 + 32 条 MVP 数学目标
  - [01-cta-belief-engine.md](../10-engineering/01-cta-belief-engine.md) — CTA 引擎（BloogProfile 估计）
  - [02-lca-policy-engine.md](../10-engineering/02-lca-policy-engine.md) — LCA 引擎（基于 BloomProfile 选目标层）
- **P0 借鉴**（理论依据）：
  - [v0.4.0 LCA 教学法基础 §3.1 CA 6 阶段](../30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md) — 与 Bloom 跨层级的对应
  - [v0.5.0 C 维度内容库 §1.3 Liminality](../30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md) — Bloom 跨越的 liminal 状态
- **上层文档**：
  - [02-architecture.md §2.2 Bloom Goal Space](../00-overview/02-architecture.md) — 三空间架构
  - [04-risks.md §B1 Bloom 风险](../00-overview/04-risks.md) — 风险评估
- **核心论证**：
  - [v2.0 §1.4 Bloom 目标空间](../deep-research/Cognitive-Digital-Twin-Deep-Research.md) — 三空间架构

---

## 9. 版本与维护

- **v1.0**（2026-06-25）— 初版

**待办（影响本文档时同步更新）**：
- 当 [03-learning-strategies.md](03-learning-strategies.md) 完成后，§3 跨层级教学策略引用 §2 学习策略空间
- 当 Phase 4 MVP 实验完成后，回填 §4 评估指标的实际效果
- 当 Phase 5+ 语文/英语库完成后，更新 §2 各学科 Bloom 分布

---

**创建日期**：2026-06-25
**维护者**：Bisen & Claude
