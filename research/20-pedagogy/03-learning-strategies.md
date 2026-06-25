# 学习策略空间（Learning Strategy Space）

> **版本**：v1.0（2026-06-25）
> **性质**：教学法层第 3 份文档——K12 学习策略分类 + 学科特定策略 + ECOS 干预映射
> **基于**：[01-k12-cognitive-structure.md](01-k12-cognitive-structure.md)、[02-bloom-application.md](02-bloom-application.md)、[v0.4.0 LCA 教学法基础（CLT + Bjork + CA）](../30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md)、[02-lca-policy-engine.md §2 Intervention 数据结构](../10-engineering/02-lca-policy-engine.md)、[v0.1 综合报告 §第八部分 Bloom](../gpt-dialogues/04-cognitive-digital-twin-v01-report.md)
> **后续**：[04-zpd-application.md](04-zpd-application.md)
> **维护者**：Bisen & Claude

---

## 0. 模块定位

### 0.1 核心职责

**学习策略空间**文档回答：**ECOS 应该向学生推荐哪些学习策略？如何匹配 Bloom 层级 + 学科 + LearningDNA？**

- 经典学习策略分类（Pintrich 1990; Weinstein 1988）：认知 / 元认知 / 资源管理
- 各学科特定策略（数学解题 / 语文阅读 / 英语听说 / 物理建模）
- 学习策略与 Bloom 层级的映射
- 学习策略与 LearningDNA 的个性化匹配
- 学习策略效果归因（与 [v0.3.0 §5 Causal Inference](../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md) 整合）

### 0.2 与 ECOS 其他模块的关系

```
┌─────────────────────────────────────────────────────────────┐
│ 学习策略空间（本文档）—— 策略知识库                          │
│   ↓ 策略选择 + 效果归因                                    │
│ LCA（[02-lca-policy-engine.md](../10-engineering/02-lca-policy-engine.md)）│
│   ↓ 推荐策略 + 干预参数                                   │
│ CTA（[01-cta-belief-engine.md](../10-engineering/01-cta-belief-engine.md)）│
│   ↓ 估计策略效果 + BloomProfile 更新                       │
└─────────────────────────────────────────────────────────────┘
```

### 0.3 经典学习策略分类

基于 [Pintrich 1990](https://www.sciencedirect.com/science/article/pii/S0361476X01000138) 与 [Weinstein 1988](https://www.springer.com/journal/10648)：

| 大类 | 子类 | 描述 |
|---|---|---|
| **认知策略** | 复述（Rehearsal）| 重复记忆（朗读、抄写）|
| | 精细加工（Elaboration）| 联想、类比、自我解释 |
| | 组织（Organization）| 归纳、做笔记、画思维导图 |
| **元认知策略** | 计划（Planning）| 设定目标、规划时间 |
| | 监控（Monitoring）| 自我评估、错误检测 |
| | 调节（Regulating）| 调整策略、寻求帮助 |
| **资源管理策略** | 时间管理 | 分配时间、设置优先级 |
| | 环境管理 | 选择学习环境 |
| | 努力管理 | 保持注意力、克服拖延 |
| | 寻求帮助 | 主动求助 |

---

## 1. 认知策略（Cognitive Strategies）

### 1.1 复述策略（Rehearsal）

**定义**：通过重复记忆巩固知识。

**具体方法**：

| 方法 | 适用 | ECOS 实现 |
|---|---|---|
| **朗读 / 抄写** | 词汇、公式 | PRACTICE 干预（v0.4.0 §2.1）|
| **闪卡（SRS）**| 间隔重复 | FSRS 算法（[02-lca-policy-engine.md §3.3](../10-engineering/02-lca-policy-engine.md)）|
| **列表记忆** | 列表型知识 | PRACTICE + 列表题 |

**适用 Bloom 层**：L1 Remember

**效果**：
- 短期有效（强化记忆）
- 长期有限（不促进理解）
- 中国学生最常用但**不是最优策略**

### 1.2 精细加工策略（Elaboration）

**定义**：通过联想、类比、自我解释深化理解。

**具体方法**：

| 方法 | 适用 | ECOS 实现 |
|---|---|---|
| **类比学习** | 抽象概念 | EXPLANATORY + CLT NOVICE（v0.4.0 §1.2）|
| **自我解释（Self-Explanation）**| 解题步骤 | METACOGNITIVE + Articulation（v0.4.0 §3.1 CA Stage 4）|
| **关键词法** | 词汇、概念 | METACOGNITIVE + 联想笔记 |
| **勾画 / 标注** | 阅读理解 | FEEDBACK 干预 |

**适用 Bloom 层**：L2 Understand + L4 Analyze

**效果**：
- Chi 1994：自我解释可产生 **30% 学习增益**
- 比复述策略更深入（促进理解而非仅记忆）
- ECOS 应**主动推荐**精细加工策略（替代单纯复述）

### 1.3 组织策略（Organization）

**定义**：通过归纳、做笔记、画思维导图结构化知识。

**具体方法**：

| 方法 | 适用 | ECOS 实现 |
|---|---|---|
| **思维导图** | 知识体系 | METACOGNITIVE + Concept Map（v0.4.0 §1.4）|
| **归纳笔记** | 章节学习 | FEEDBACK + 笔记模板 |
| **大纲 / 表格** | 比较学习 | EXPLANATORY + 比较结构 |

**适用 Bloom 层**：L4 Analyze + L6 Create

**效果**：
- 促进知识结构化（schema 形成）
- 与 [v0.3.0 §1 MIRT](../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md) 的 Σ_θ 协方差结构契合
- 长期记忆显著提升

---

## 2. 元认知策略（Metacognitive Strategies）

[v0.4.0 §3.1 Cognitive Apprenticeship 6 阶段](../30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md) 中的 **Stage 4 Articulation + Stage 5 Reflection** 直接对应元认知策略。

### 2.1 计划策略（Planning）

**定义**：设定学习目标、规划学习时间。

**具体方法**：

| 方法 | 适用 | ECOS 实现 |
|---|---|---|
| **目标设定** | 学期/月度目标 | CTA next_target + Bloom Library（[03-bloom-goal-library.md §7](../10-engineering/03-bloom-goal-library.md)）|
| **时间表** | 复习计划 | FSRS + 间隔重复（v0.4.0 §2.3）|
| **任务分解** | 复杂任务 | LCA scaffolding + CA Stage 3 |

**适用 Bloom 层**：所有层（特别 L3 Apply）

### 2.2 监控策略（Monitoring）

**定义**：自我评估学习状态、检测错误。

**具体方法**：

| 方法 | 适用 | ECOS 实现 |
|---|---|---|
| **自我提问** | 解题时 | EXPLANATORY + Socratic |
| **错误检查** | 答题后 | FEEDBACK + rationale |
| **反思日志** | 阶段性学习 | METACOGNITIVE + Articulation |

**适用 Bloom 层**：L4 Analyze + L5 Evaluate

### 2.3 调节策略（Regulating）

**定义**：根据监控结果调整学习策略。

**具体方法**：

| 方法 | 适用 | ECOS 实现 |
|---|---|---|
| **策略调整** | 效果不佳时 | LCA + Contextual Bandits（[02-lca-policy-engine.md §4.2](../10-engineering/02-lca-policy-engine.md)）|
| **寻求帮助** | 卡住时 | EXPLANATORY + 教师审核 |
| **重新规划** | 目标调整时 | CA Stage 5 Reflection + Stage 6 Exploration |

**适用 Bloom 层**：所有层（特别 L5 Evaluate）

---

## 3. 资源管理策略（Resource Management Strategies）

### 3.1 时间管理

**具体方法**：

| 方法 | 适用 | ECOS 实现 |
|---|---|---|
| **番茄工作法** | 短时专注 | LCA 估计_duration_sec |
| **间隔复习** | 长期记忆 | FSRS 调度（v0.4.0 §2.3）|
| **时间审计** | 自我评估 | FEEDBACK + 月度报告 |

### 3.2 环境管理

**具体方法**：

| 方法 | 适用 | ECOS 实现 |
|---|---|---|
| **安静环境** | 专注学习 | App 层 UI 设计 |
| **同伴学习** | 协作 | LCA + Group Learning（Phase 5+）|
| **线上资源** | 拓展 | App + 推荐资源 |

### 3.3 努力管理

**具体方法**：

| 方法 | 适用 | ECOS 实现 |
|---|---|---|
| **目标分解** | 大任务 | CA Stage 3 Scaffolding |
| **自我激励** | 维持兴趣 | Game 化（[01-k12-cognitive-structure.md §8](../20-pedagogy/01-k12-cognitive-structure.md)）|
| **避免拖延** | 时间管理 | LCA 提醒 + deadline |

### 3.4 寻求帮助

**具体方法**：

| 方法 | 适用 | ECOS 实现 |
|---|---|---|
| **问 AI** | 即时 | LCA + rationale |
| **问老师** | 系统性 | 教师后台（[02-lca-policy-engine.md §5.3](../10-engineering/02-lca-policy-engine.md)）|
| **问同学** | 协作 | Group Learning（Phase 5+）|

---

## 4. 学科特定学习策略

### 4.1 数学解题策略

[Polya 1945 问题解决四阶段](https://math.berkeley.edu/~gmelvin/polya.pdf)：

| 阶段 | 描述 | ECOS 实现 |
|---|---|---|
| **1. 理解问题** | 识别已知/未知/条件 | EXPLANATORY + 提问引导 |
| **2. 制定计划** | 选择策略 | LCA + CA Stage 2 Coaching |
| **3. 执行计划** | 实施计算 | PRACTICE + 即时反馈 |
| **4. 回顾反思** | 检验答案、总结方法 | METACOGNITIVE + Reflection |

**数学特定策略**：

| 策略 | 适用 | 效果 |
|---|---|---|
| **画图 / 表格** | 应用题 | 高（空间表征）|
| **逆推** | 解方程 | 中 |
| **特例化** | 验证答案 | 高 |
| **类比** | 新概念 | 高 |
| **分解** | 复杂题 | 高（与 v0.4.0 CLT 一致）|

### 4.2 语文阅读策略

| 策略 | 适用 | 效果 |
|---|---|---|
| **略读 / 扫读** | 把握大意 | 中 |
| **精读** | 理解细节 | 高 |
| **批注** | 深度理解 | 高（Articulation）|
| **复述** | 记忆 | 中 |
| **比较阅读** | 多文本 | 高（Analyze）|

**ECOS 实现**：

```python
# 语文 LCA 干预类型选择
def select_language_intervention(belief_state, target_skill):
    if target_skill == 'text_comprehension':
        return Intervention(
            type=InterventionType.EXPLANATORY,
            # 精读 + 批注
            presentation_params={'method': 'close_reading', 'annotate': True},
            rationale="精读 + 批注促进深度理解（Articulation 策略）",
        )
    elif target_skill == 'essay_writing':
        return Intervention(
            type=InterventionType.METACOGNITIVE,
            # Teach-back 自我解释
            presentation_params={'method': 'teach_back', 'peer_review': True},
            rationale="Teach-back + peer review 提升议论文写作",
        )
```

### 4.3 英语听说策略

| 策略 | 适用 | 效果 |
|---|---|---|
| **影子跟读（Shadowing）**| 听力 | 高 |
| **大声朗读** | 口语 | 中 |
| **听写** | 拼写 | 中 |
| **看英文视频（无字幕）**| 听力 | 高 |
| **造句** | 应用 | 中 |

### 4.4 物理建模策略

| 策略 | 适用 | 效果 |
|---|---|---|
| **画受力图** | 力学 | 高 |
| **画电路图** | 电学 | 高 |
| **建立坐标系** | 运动学 | 高 |
| **类比日常现象** | 抽象概念 | 高 |

**物理与数学建模的迁移**（[01-k12-cognitive-structure.md §5.3 跨学科迁移](../20-pedagogy/01-k12-cognitive-structure.md)）：
- 数学 P ↔ 物理 P 迁移率 70%
- 物理建模策略可从数学解题策略迁移

---

## 5. ECOS 5 类干预 × 学习策略对应

[02-lca-policy-engine.md §2.2 5 类干预 × 4 参数](../10-engineering/02-lca-policy-engine.md) 与学习策略的对应：

| ECOS 干预类型 | 主要学习策略 | 次要策略 | 适用 Bloom 层 |
|---|---|---|---|
| **EXPLANATORY** | 精细加工（类比）| 组织（思维导图）| L2-L3 |
| **PRACTICE** | 复述（间隔重复）| 精细加工（变式）| L1-L3 |
| **INQUIRY** | 组织（归纳）| 元认知（监控）| L3-L4 |
| **FEEDBACK** | 元认知（调节）| 精细加工（错误分析）| L1-L4 |
| **METACOGNITIVE** | 元认知（计划 + 监控 + 调节）| 精细加工（自我解释）| L4-L6 |

**推荐策略组合**（基于 [v0.4.0 LCA 教学法基础](../30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md)）：

```
L1-L2 记忆 + 理解：
  EXPLANATORY（CLT NOVICE）+ PRACTICE（FSRS 间隔）

L2-L3 理解 + 应用：
  EXPLANATORY（CLT DEVELOPING）+ PRACTICE（变式练习）

L3-L4 应用 + 分析：
  INQUIRY（探究型）+ METACOGNITIVE（Articulation）

L4-L5 分析 + 评价：
  METACOGNITIVE（Reflection + peer review）+ INQUIRY

L5-L6 评价 + 创造：
  INQUIRY（项目式）+ METACOGNITIVE（Exploration）
```

---

## 6. 学习策略与 Bloom 层级映射

### 6.1 完整映射表

| Bloom 层 | 主要策略 | 次要策略 | ECOS 干预类型 |
|---|---|---|---|
| **L1 Remember** | 复述（朗读、闪卡、列表）| — | PRACTICE（FSRS 间隔）|
| **L2 Understand** | 精细加工（类比、关键词）| 复述 | EXPLANATORY（CLT NOVICE）|
| **L3 Apply** | 精细加工（变式）| 复述 + 计划 | PRACTICE + INQUIRY |
| **L4 Analyze** | 组织（思维导图、归纳）| 精细加工（自我解释）| INQUIRY + METACOGNITIVE（Articulation）|
| **L5 Evaluate** | 元认知（监控 + 调节）| 组织（比较）| METACOGNITIVE（peer review）|
| **L6 Create** | 组织（设计）| 元认知（计划 + 探索）| INQUIRY（项目式）|

### 6.2 学习策略的 ATE 估计

[Weinstein & Mayer 1986](https://www.researchgate.net/publication/232556858_Classroom_Strategies_Research) 经典研究的学习策略 effect size：

| 策略 | effect size | 适用学段 |
|---|---|---|
| 复述 | 0.20-0.35 | 小学 |
| 精细加工 | 0.65-0.85 | 初中 + 高中 |
| 组织 | 0.60-0.75 | 初中 + 高中 |
| 元认知 | 0.55-0.70 | 初中 + 高中 |

**关键洞察**：精细加工 + 组织 + 元认知策略的 effect size 显著高于纯复述。ECOS 应**主动推荐高 effect size 策略**（特别是精细加工），避免中国学生过度依赖复述。

---

## 7. 学习策略与 LearningDNA 匹配

[01-cta-belief-engine.md §2.1 LearningDNA](../10-engineering/01-cta-belief-engine.md) 5 维个性化特征：

| LearningDNA 维度 | 匹配的学习策略 |
|---|---|
| **输入偏好**（视觉 / 听觉 / 动觉）| 视觉 → 思维导图 + 表格<br>听觉 → 朗读 + 听写<br>动觉 → 实际操作 |
| **反馈偏好**（即时 / 延迟）| 即时 → FEEDBACK 立即反馈<br>延迟 → FEEDBACK 延迟反馈 |
| **疲劳模式** | 高疲劳时段 → 短间隔 PRACTICE<br>低疲劳时段 → 长时间 INQUIRY |
| **错误模式** | 重复错误 → 复述强化<br>理解错误 → 精细加工 |
| **动机模式** | 高动机 → INQUIRY 探究<br>低动机 → 游戏化 + 即时反馈 |

### 7.1 LCA 干预的个性化推荐

```python
# 02-lca-policy-engine.md §6 LCAOrchestrator 扩展
class PersonalizedStrategySelector:
    """基于 LearningDNA 的策略选择"""

    def select(
        self,
        belief_state: 'BeliefState',
        learning_dna: 'LearningDNAState',
        bloom_target: BloomLevel,
    ) -> Intervention:
        """个性化选择学习策略"""
        # 1. 基于 Bloom 层选主要策略
        base_strategy = self._bloom_to_strategy(bloom_target)

        # 2. 基于 LearningDNA 调整
        if learning_dna.input_preference == 'visual':
            base_strategy['method'] = 'mind_map'
        elif learning_dna.input_preference == 'auditory':
            base_strategy['method'] = 'read_aloud'

        # 3. 基于反馈偏好
        if learning_dna.feedback_preference == 'immediate':
            base_strategy['feedback_density'] = 1.0
        else:
            base_strategy['feedback_density'] = 0.3

        # 4. 基于动机模式
        if learning_dna.motivation_pattern.get('weekday', 0.5) < 0.4:
            base_strategy['gamification'] = True

        return Intervention(**base_strategy)
```

---

## 8. 学习策略效果归因

### 8.1 与 CTA L4 因果归因整合

[01-cta-belief-engine.md §7 L4 因果归因](../10-engineering/01-cta-belief-engine.md) + [04-dual-agent-calibration.md §4.3 因果归因强制](../10-engineering/04-dual-agent-calibration.md)：

```python
class LearningStrategyAttribution:
    """学习策略效果归因"""

    def __init__(self, cta_l4: 'ABTestAttributor'):
        self.cta_l4 = cta_l4

    def attribute_strategy_effect(
        self,
        strategy_type: str,
        student_id: str,
        state_delta: float,
    ) -> 'CausalEffect':
        """归因特定学习策略的因果效果"""
        return self.cta_l4.attribute(
            intervention_type=f"strategy_{strategy_type}",
            student_id=student_id,
            state_delta=state_delta,
            is_control=False,
        )

    def compare_strategies(
        self,
        student_id: str,
        strategy_a: str,
        strategy_b: str,
    ) -> Dict[str, float]:
        """比较两种策略的因果效果"""
        # 收集两种策略的 state_delta 数据
        # 用 A/B test 比较
        # 返回 {strategy_a_ate, strategy_b_ate, significant}
        pass
```

### 8.2 学习策略的元分析

基于 Weinstein & Mayer 1986 + Pintrich 1990 + 后续 meta-analyses：

| 策略 | ECOS 推荐强度 | 适用 Bloom |
|---|---|---|
| 复述（朗读）| 低（仅 L1）| L1 |
| 复述（间隔重复 / FSRS）| 中（仍有效）| L1 |
| 精细加工（类比）| 高（CLT + 核心）| L2-L3 |
| 精细加工（自我解释）| 高（Chi 30% 增益）| L2-L4 |
| 组织（思维导图）| 中 | L4 |
| 组织（归纳笔记）| 中 | L4-L6 |
| 元认知（计划）| 中 | 全部 |
| 元认知（监控）| 高（与 [v0.5.0 反思日志](../30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md) 整合）| L4-L5 |
| 元认知（调节）| 高（与 Contextual Bandits 整合）| 全部 |
| 资源管理（时间）| 中 | L1-L3 |

### 8.3 中国 K12 学习策略的特殊考量

**中国学生偏好**：复述 + 题海（低 Bloom 高负荷）。

**ECOS 主动引导**：基于 [02-bloom-application.md §5 解决"会做但不会想"](../20-pedagogy/02-bloom-application.md)：

1. **降低复述策略比重**（占比 ≤ 30%）
2. **提升精细加工 + 元认知策略比重**（占比 ≥ 50%）
3. **拒绝纯题海战术**（CLAIM：Bjork 合意困难 + 交错练习是更高效策略）
4. **引导家长**理解"分数高 ≠ 思维强"

---

## 9. 学习策略与 ECOS 状态的反馈循环

### 9.1 CTA → LCA → 学生的反馈循环

```
学生使用策略（如"思维导图"）
        ↓
学生状态变化（CTA 估计 BloomProfile）
        ↓
LCA 归因策略效果（CATE）
        ↓
LCA Contextual Bandits 更新策略权重
        ↓
下次干预推荐更优策略
        ↓
循环
```

### 9.2 学习策略效果的个性化

```python
class PersonalizedStrategyEffect:
    """学习策略效果的个性化"""

    def __init__(self):
        # 每个学生 × 每个策略的效果矩阵
        self.effect_matrix: Dict[Tuple[student_id, strategy], List[float]] = {}

    def record(self, student_id: str, strategy: str, state_delta: float):
        """记录策略效果"""
        key = (student_id, strategy)
        if key not in self.effect_matrix:
            self.effect_matrix[key] = []
        self.effect_matrix[key].append(state_delta)

    def recommend_best_strategy(
        self,
        student_id: str,
        candidate_strategies: List[str],
    ) -> str:
        """推荐该学生最有效的策略"""
        best_strategy = None
        best_avg_gain = -float('inf')
        for strategy in candidate_strategies:
            history = self.effect_matrix.get((student_id, strategy), [])
            if history:
                avg_gain = sum(history) / len(history)
                if avg_gain > best_avg_gain:
                    best_avg_gain = avg_gain
                    best_strategy = strategy
        return best_strategy or candidate_strategies[0]
```

---

## 10. 评估指标（对照 04-risks.md §C2 文化适配）

| 指标 | 阈值 | 测试场景 |
|---|---|---|
| **策略推荐接受率** | ≥ 60% | 学生行为日志 |
| **策略效果 CATE** | ≥ 0.10 | 因果归因 |
| **精细加工策略占比** | ≥ 50% | 推荐策略分布 |
| **元认知策略完成率** | ≥ 40% | 学生反馈 |
| **家长反对率** | ≤ 30% | 家长问卷 |
| **策略效果方差** | 显著 | 个性化推荐 |

**家长沟通**（[04-risks.md §C2 缓解策略](../00-overview/04-risks.md)）：

- 用 [02-bloom-application.md §7 给家长的建议](../20-pedagogy/02-bloom-application.md) 沟通"分数高 ≠ 思维强"
- 显式说明"我们推荐 X 策略（替代纯题海），效果更好"
- 渐进引入（先保留中国家长熟悉的"刷题"元素，逐步加入合意困难）

---

## 11. 关联文档

- **同级教学法层**：
  - [01-k12-cognitive-structure.md](01-k12-cognitive-structure.md) — K12 学段差异化
  - [02-bloom-application.md](02-bloom-application.md) — Bloom 跨层级策略
  - [04-zpd-application.md](04-zpd-application.md) — ZPD 在 ECOS 的应用
- **P0 借鉴**（理论依据）：
  - [v0.4.0 LCA 教学法基础 §1 CLT](../30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md) — 工作记忆负荷
  - [v0.4.0 §2 Bjork 四件套](../30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md) — 合意困难
  - [v0.4.0 §3 Cognitive Apprenticeship 6 阶段](../30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md) — 元认知策略
  - [v0.5.0 §3 Misconception 库](../30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md) — 反思日志整合
- **工程层**（按本文档配置实现）：
  - [02-lca-policy-engine.md](../10-engineering/02-lca-policy-engine.md) — LCA 引擎（推荐策略）
  - [01-cta-belief-engine.md](../10-engineering/01-cta-belief-engine.md) — CTA 引擎（归因策略效果）
  - [04-dual-agent-calibration.md](../10-engineering/04-dual-agent-calibration.md) — 双 Agent 互校
- **上层文档**：
  - [02-architecture.md §6 干预策略](../00-overview/02-architecture.md) — 工程实现依据
  - [04-risks.md §C2 文化适配](../00-overview/04-risks.md) — 中国 K12 风险

---

## 12. 版本与维护

- **v1.0**（2026-06-25）— 初版

**待办（影响本文档时同步更新）**：
- 当 [04-zpd-application.md](04-zpd-application.md) 完成后，§1.1 与 §2.1 学习策略与 ZPD 关联
- 当 Phase 4 MVP 实验完成后，回填 §10 评估指标的实际效果

---

**创建日期**：2026-06-25
**维护者**：Bisen & Claude
