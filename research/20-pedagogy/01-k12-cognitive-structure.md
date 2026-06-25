# K12 认知结构（K12 Cognitive Structure）

> **版本**：v1.0（2026-06-25）
> **性质**：教学法层第 1 份文档——K12 各学段认知发展特征与 ECOS CTA 建模差异化
> **基于**：[v2.0 §1.4 K12 三大优势](../../research/deep-research/Cognitive-Digital-Twin-Deep-Research.md)、[v0.5.0 C 维度内容库（TC 库）](../../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md)、[02-architecture.md §2.1 State Space](../research/00-overview/02-architecture.md)、[01-cta-belief-engine.md §2](../research/10-engineering/01-cta-belief-engine.md)、[03-bloom-goal-library.md §11 MVP 范围](../research/10-engineering/03-bloom-goal-library.md)
> **后续**：[02-bloom-application.md](02-bloom-application.md)、[03-learning-strategies.md](03-learning-strategies.md)、[04-zpd-application.md](04-zpd-application.md)
> **维护者**：Bisen & Claude

---

## 0. 模块定位

### 0.1 核心职责

**K12 认知结构**文档回答：**ECOS 在小学、初中、高中各学段应该如何差异化建模学生认知？**

- 不同学段学生认知结构差异巨大
- ECOS 5D 状态向量 + BloomProfile + LearningDNA 在各学段应该有**不同的默认参数**
- CTA 状态估计的精度预期 + LCA 干预的难度梯度应随学段调整

### 0.2 与 ECOS 其他模块的关系

```
┌─────────────────────────────────────────────────────────────┐
│ K12 认知结构（本文档）—— 学段差异化的"基础配置"               │
│   ↓ 默认参数 + 评估阈值                                     │
│ CTA（[01-cta-belief-engine.md](../10-engineering/01-cta-belief-engine.md)）│
│   ↓ 5D + BloomProfile 估计                                   │
│ LCA（[02-lca-policy-engine.md](../10-engineering/02-lca-policy-engine.md)）│
│   ↓ 干预策略选择                                             │
│ Bloom（[03-bloom-goal-library.md](../10-engineering/03-bloom-goal-library.md)）│
│   ↓ 各学段 Bloom 目标库                                     │
└─────────────────────────────────────────────────────────────┘
```

### 0.3 与 v0.5.0 C 维度内容库的关系

TC（Threshold Concepts）跨越往往与学段过渡相关：
- **小学 TC**：分数 / 负数 / 函数初步
- **初中 TC**：变量 / 函数 / 几何证明 / 极限初步
- **高中 TC**：极限严格化 / 微积分 / 概率论基础

每个 TC 跨越都会触发 BloomProfile 的"质变"（v0.5.0 §1.4）。

---

## 1. 小学阶段认知发展（1-6 年级）

### 1.1 Piaget 视角：具体运算阶段前期 + 中期

[Piaget 认知发展阶段论](https://www.simplypsychology.org/piaget.html)：

| 年级 | Piaget 阶段 | 核心特征 |
|---|---|---|
| 1-2 年级 | 前运算阶段（Preoperational）| 象征思维，但缺乏守恒概念 |
| 3-4 年级 | 具体运算阶段早期 | 守恒概念出现，能做简单逻辑 |
| 5-6 年级 | 具体运算阶段成熟 | 能做多步逻辑，但抽象思维有限 |

### 1.2 ECOS 小学阶段的 CTA 建模差异

**5D 状态向量**（[v0.3.0 §1 MIRT](../../research/30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md)）：

| 维度 | 小学特点 | CTA 建模调整 |
|---|---|---|
| **K（知识）** | 主要记忆事实（九九表、生字、单词）| MIRT 单维为主（5D 过细）|
| **P（程序）** | 简单程序（加减乘除步骤）| BKT 4 参数够用 |
| **S（策略）** | 缺乏元认知策略 | S 维度权重低（重要性次要）|
| **C（置信度）** | 常过度自信 | 必须用 Misconception 检测（v0.5.0） |
| **X（外部支架）** | 高度依赖家长/老师 | X 维度特别重要 |

**BloomProfile 调整**（v0.3.0 §2 CD-CAT）：

- **L1 Remember 主导**（80-90%）
- **L2 Understand 有限**（10-20%）
- **L3 Apply 极少**（< 5%）
- **L4-L6 不适用**（小学阶段）

### 1.3 小学 TC 库候选（v0.5.0 §1.7 候选的细化）

基于 [v0.5.0 C 维度内容库](../../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md) + 小学阶段特征：

| # | TC 名 | 跨越年级 | 跨越标志 |
|---|---|---|---|
| 1 | **分数** | 3-4 年级 | 从"部分" → "整体关系" |
| 2 | **负数** | 5-6 年级 | 从"减法结果" → "数轴对称" |
| 3 | **乘法意义** | 3-4 年级 | 从"加法重复" → "比例/面积" |
| 4 | **守恒概念** | 3-4 年级 | 数量守恒（不随容器形状改变）|

### 1.4 小学 Misconception 库候选

| ID | Misconception | 年级 | 修正方法 |
|---|---|---|---|
| M-F1 | 乘法总是变大 | 3 年级 | 数轴 + 面积图 |
| M-F2 | 分母大 → 分数大 | 4 年级 | 同样大小的"披萨切分数" |
| M-F3 | 负数不存在 | 5 年级 | 负债类比 + 数轴 |

### 1.5 LCA 干预的难度梯度

**关键约束**：小学阶段的学生**难以承受高认知负荷**（[v0.4.0 CLT](../../research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md)）：

- 单次干预元素 ≤ 3 个（工作记忆容量有限）
- CLT 4 级自适应默认 = NOVICE（full worked example）
- 练习型干预数量 ≤ 5（避免疲劳）
- 元认知型干预**不适用**（学生无元认知能力）

---

## 2. 初中阶段认知发展（7-9 年级）

### 2.1 Piaget 视角：具体运算后期 + 形式运算初期

| 年级 | Piaget 阶段 | 核心特征 |
|---|---|---|
| 7 年级 | 具体运算过渡期 | 抽象思维开始出现 |
| 8 年级 | 形式运算初期 | 能做假设性推理 |
| 9 年级 | 形式运算巩固 | 抽象逻辑成熟 |

### 2.2 ECOS 初中阶段的 CTA 建模差异

**5D 状态向量**：

| 维度 | 初中特点 | CTA 建模调整 |
|---|---|---|
| **K（知识）** | 系统化知识（定理、规则）| MIRT 5D 完整启用 |
| **P（程序）** | 多步解题程序（方程组步骤）| BKT 跨知识点关联 |
| **S（策略）** | 元认知策略发展 | S 维度权重提升 |
| **C（置信度）** | 伪置信高发期 | Misconception 检测关键 |
| **X（外部支架）** | 逐渐独立 | X 维度权重降低 |

**BloomProfile 调整**：

- **L1-L2 主导**（50-60%）
- **L3 Apply 显著**（20-30%）
- **L4 Analyze 萌芽**（5-10%）
- **L5-L6 偶尔**（< 5%）

### 2.3 初中 TC 库候选（v0.5.0 §1.7）

[03-bloom-goal-library.md §3.2 数学 8 核心知识点](../research/10-engineering/03-bloom-goal-library.md) 中前 8 个 TC：

| # | TC 名 | 跨越年级 | 跨越标志 |
|---|---|---|---|
| 1 | **函数** | 8-9 年级 | 从"y 随 x 变化" → "集合到集合的映射" |
| 2 | **变量** | 7-8 年级 | 从"未知数" → "代表一类数的符号" |
| 3 | **等式 vs 不等式** | 7-8 年级 | 从"两边相等" → "约束关系" |
| 4 | **几何证明** | 8-9 年级 | 从"计算" → "逻辑论证" |
| 5 | **二次函数** | 9 年级 | 从"一般式" → "顶点式 + 对称轴" |
| 6 | **极限（初步）**| 9 年级 | 从"算术" → "无限接近的严格概念" |

### 2.4 初中 Misconception 库候选（[v0.5.0 §2.6 候选 10 条](../../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md)）

| ID | Misconception | 修正方法 |
|---|---|---|
| M-J1 | 乘法总是变大 | 数轴 + 面积图 |
| M-J2 | 分母大 → 分数大 | 同样大小的"披萨切分数" |
| M-J3 | 等式性质推广到不等式 | 反例 + 符号翻转规则 |
| M-J4 | 负数不存在 | 负债类比 + 数轴 |
| M-J5 | 0 是"没有" | 数轴上的零点 |
| M-J6 | 圆周率是 3.14 | 测量 + 极限 |
| M-J7 | 平方 = 2 倍 | 数值代入 + 几何图 |
| M-J8 | 函数必过原点 | 反例：f(x) = x + 1 |
| M-J9 | 几何证明 = 计算 | 区分计算与论证 |
| M-J10 | 概率是"运气" | 大数定律 + 频数实验 |

### 2.5 LCA 干预的难度梯度

初中阶段可以承受更高认知负荷：

- 单次干预元素 ≤ 5 个
- CLT 4 级自适应：DEVELOPING 起步（worked example + 填空）
- 练习型干预数量 ≤ 10
- 元认知型干预**有限使用**（Articulation 引导）

---

## 3. 高中阶段认知发展（10-12 年级）

### 3.1 Piaget 视角：形式运算完全成熟

| 年级 | Piaget 阶段 | 核心特征 |
|---|---|---|
| 10 年级 | 形式运算成熟 | 完全抽象思维 |
| 11 年级 | 形式运算 + 元认知 | 自我反思能力 |
| 12 年级 | 元认知 + 自主学习 | 接近成人认知 |

### 3.2 ECOS 高中阶段的 CTA 建模差异

**5D 状态向量**：

| 维度 | 高中特点 | CTA 建模调整 |
|---|---|---|
| **K（知识）** | 学科专业化（数学/物理/化学/生物分科）| MIRT 多学科本体 |
| **P（程序）** | 复杂多步程序（微积分、立体几何）| BKT 跨章节关联 |
| **S（策略）** | 元认知成熟 | S 维度权重高 |
| **C（置信度）** | 伪置信减少 | 但新型 misconception（更隐蔽）|
| **X（外部支架）** | 主要靠同学/网络资源 | X 维度可弱化 |

**BloomProfile 调整**：

- **L1-L2 减少**（30-40%）
- **L3 Apply 主导**（30-40%）
- **L4 Analyze 显著**（15-20%）
- **L5 Evaluate 萌芽**（5-10%）
- **L6 Create 偶尔**（< 5%）

### 3.3 高中 TC 库候选（Phase 5+ 扩展）

基于 [v0.5.0 §1.7](../../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md) + 高中特征：

| # | TC 名 | 跨越年级 | 跨越标志 |
|---|---|---|---|
| 1 | **极限严格化** | 10-11 年级 | 从"无限接近" → "ε-δ 定义" |
| 2 | **微积分基础** | 11 年级 | 从"切线斜率" → "导数极限定义" |
| 3 | **概率论基础** | 11-12 年级 | 从"古典概型" → "概率公理化" |
| 4 | **向量空间** | 12 年级 | 从"几何向量" → "代数向量空间" |
| 5 | **函数连续性** | 11 年级 | 从"画图连续" → "ε-δ 连续" |
| 6 | **电磁感应** | 11 年级 | 从"力作用" → "场作用" |
| 7 | **化学平衡** | 11 年级 | 从"反应完全" → "动态平衡" |

### 3.4 高中 Misconception 库候选（Phase 5+）

| ID | Misconception | 修正方法 |
|---|---|---|
| M-S1 | 极限 = 直接代入 | ε-δ 严格定义 |
| M-S2 | 导数 = 切线斜率（无极限）| 极限定义 |
| M-S3 | 电流被"消耗" | 串联恒定 + 类比水管 |
| M-S4 | 平衡 = 反应停止 | 动态平衡（正逆反应等速）|

### 3.5 LCA 干预的难度梯度

高中阶段可以承受完整难度：

- 单次干预元素 5-10 个
- CLT 4 级自适应：PROFICIENT 起步（独立解题 + 即时反馈）
- 练习型干预数量 ≤ 10
- 元认知型干预**完整使用**（含 Reflection + Exploration）

---

## 4. 学段过渡的关键节点

### 4.1 学段过渡的认知挑战

| 过渡 | 关键挑战 | ECOS 应对 |
|---|---|---|
| **小学 → 初中** | 抽象思维突然要求（变量 / 函数 / 证明）| TC 检测 + liminal 状态预警 |
| **初中 → 高中** | 形式化要求（ε-δ / 严格证明）| BloomProfile 重新校准 + 干预降级 |
| **高中 → 大学** | 自主学习能力 | LearningDNA 推断 + 元认知型干预 |

### 4.2 学段过渡时的 ECOS 行为

**CTA 状态迁移**：

```python
def handle_grade_transition(student_id, old_grade, new_grade):
    """学段切换处理"""
    # 1. 保存学段结束快照到 L4 持久记忆
    archive.save_snapshot(student_id, ..., snapshot_type='grade_transition')

    # 2. BloomProfile 迁移到下一学段起点
    # - 小学 → 初中：L1-L2 主导 → L1-L2 + L3 Apply
    # - 初中 → 高中：L3 Apply → L4 Analyze

    # 3. 5D 状态迁移
    # - 保留 K/P（学科知识持续累积）
    # - 重置 C（misconception 历史保留但权重调整）
    # - 保留 LearningDNA（跨学段稳定）

    # 4. LearningDNA 推断（如果新学段缺失）
    if new_grade == 10:  # 初升高
        # 通过预测试推断 LearningDNA
        learning_dna = infer_from_pretest(student_id)
```

### 4.3 学段过渡的诊断信号

[04-risks.md §B1 Bloom 风险评估](../research/00-overview/04-risks.md) + [v0.5.0 §1.4 Liminality](../../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md)：

**Liminal 状态预警**：

```
学生进入新学段（前 1-2 个月）
        ↓
BloomProfile 突然倒退（如 L3 突然降为 L1）
        ↓
元认知困惑（反思文本含"困惑"/"迷茫"）
        ↓
连续 3 次错误
        ↓
CTA 检测到 liminal 信号
        ↓
LCA 干预策略调整（增加 scaffolding + CLT NOVICE 级别）
        ↓
不判定为"退步"——而是"TC 跨越的预期混乱"
```

---

## 5. 学科 × 认知结构映射

### 5.1 数学 vs 语文 vs 物理的认知结构差异

| 维度 | 数学 | 语文 | 物理 |
|---|---|---|---|
| **核心 TC** | 函数 / 变量 / 证明 | 文本多义性 / 意象 / 修辞 | 能量守恒 / 场作用 / 模型切换 |
| **Misconception 模式** | 结构性误解（分母大）| 语义性误解（字面理解）| 本体论误解（"力是属性"）|
| **Bloom 适用** | L1-L4 主导 | L1-L2 主导 + L4 修辞 | L1-L4 主导 |
| **LCA 干预类型偏好** | PRACTICE + EXPLANATORY | METACOGNITIVE + FEEDBACK | INQUIRY + FEEDBACK |
| **跨学科迁移** | 数学 P ↔ 物理 P 强迁移 | 语文能力迁移弱 | 物理建模 ↔ 数学建模 |

### 5.2 ECOS 多学科建模差异

```python
def get_subject_cog_config(subject: str, grade: int) -> 'CogConfig':
    """获取学科认知配置"""
    if subject == 'math':
        return MathCogConfig(grade=grade)
    elif subject == 'language':
        return LanguageCogConfig(grade=grade)
    elif subject == 'physics':
        return PhysicsCogConfig(grade=grade)

class MathCogConfig:
    """数学认知配置"""
    def __init__(self, grade):
        if grade <= 6:  # 小学
            self.bloom_dominant = [BloomLevel.REMEMBER, BloomLevel.UNDERSTAND]
            self.clt_default = CLTLevel.NOVICE
            self.tc_focus = ['fractions', 'negative_numbers', 'conservation']
            self.misc_library_size = 5
        elif grade <= 9:  # 初中
            self.bloom_dominant = [BloomLevel.UNDERSTAND, BloomLevel.APPLY]
            self.clt_default = CLTLevel.DEVELOPING
            self.tc_focus = ['function', 'variable', 'proof']
            self.misc_library_size = 30  # v0.5.0 候选
        else:  # 高中
            self.bloom_dominant = [BloomLevel.APPLY, BloomLevel.ANALYZE]
            self.clt_default = CLTLevel.PROFICIENT
            self.tc_focus = ['limit', 'derivative', 'probability']  # Phase 5+
            self.misc_library_size = 50  # Phase 5+

class LanguageCogConfig:
    """语文认知配置"""
    def __init__(self, grade):
        # 语文 K12 主要是 L1-L2（记忆 + 理解）
        # L4（分析修辞手法）在阅读中
        # L5-L6（评价 + 创造）在写作中
        self.bloom_dominant = [BloomLevel.REMEMBER, BloomLevel.UNDERSTAND, BloomLevel.ANALYZE]
        # 语文评估需要 LLM rubric 辅助（主观性强）
        self.assessment_method = 'llm_rubric'
```

### 5.3 跨学科能力迁移建模（Phase 5+）

```python
class CrossSubjectTransfer:
    """跨学科能力迁移"""

    # 数学 P ↔ 物理 P 迁移矩阵（MVP 占位）
    TRANSFER_MATRIX = {
        ('math', 'physics'): 0.7,    # 70% 迁移
        ('physics', 'math'): 0.6,
        ('math', 'language'): 0.2,   # 弱迁移
        ('language', 'math'): 0.1,
    }

    def transfer_estimate(
        self,
        from_subject: str,
        from_skill: str,
        to_subject: str,
        to_skill: str,
        from_estimate: float,
    ) -> float:
        """迁移能力估计"""
        coef = self.TRANSFER_MATRIX.get((from_subject, to_subject), 0.0)
        return from_estimate * coef
```

---

## 6. 关键认知节点与里程碑

### 6.1 小学阶段里程碑（5 个）

| 年级 | 里程碑 | 评估方法 |
|---|---|---|
| 2 年级末 | 简单加减法熟练 | K 维度 P(L) ≥ 0.8 |
| 4 年级末 | 分数概念掌握 | TC "分数" 跨越 |
| 5 年级末 | 多步应用题能力 | L3 Apply 维度达标 |
| 6 年级末 | 负数概念建立 | TC "负数" 跨越 |
| 6 年级末 | 学习习惯养成 | LearningDNA 推断 |

### 6.2 初中阶段里程碑（7 个）

| 年级 | 里程碑 | 评估方法 |
|---|---|---|
| 7 年级末 | 变量理解 | TC "变量" 跨越 |
| 8 年级末 | 函数理解 | TC "函数" 跨越 + BloomProfile L3 ≥ 0.7 |
| 8 年级末 | 一元一次方程熟练 | K + P 维度 P(L) ≥ 0.8 |
| 9 年级初 | 几何证明入门 | TC "几何证明" 跨越 |
| 9 年级中 | 二次函数掌握 | TC "二次函数" 跨越 |
| 9 年级末 | 概率初步 | BloomProfile L3 ≥ 0.6 |
| 9 年级末 | 元认知策略养成 | S 维度达标 |

### 6.3 高中阶段里程碑（Phase 5+）

| 年级 | 里程碑 | 评估方法 |
|---|---|---|
| 10 年级末 | 极限严格化 | TC "极限" 跨越 |
| 11 年级末 | 微积分基础 | TC "导数" 跨越 + L4 Analyze 达标 |
| 12 年级末 | 概率论基础 | TC "概率" 跨越 |
| 12 年级末 | 自主学习能力 | S 维度 + 元认知型干预完成率 |

---

## 7. 与中国课程标准对接

[03-bloom-goal-library.md §3.3 中国课程标准](../research/10-engineering/03-bloom-goal-library.md) 已给出对接机制。本节强调学段差异：

### 7.1 各学段核心知识点

| 学段 | 核心知识点数 | 课程标准 |
|---|---|---|
| 小学（1-6）| ~30 个核心 | 人教版数学 1-12 册 |
| 初中（7-9）| ~40 个核心 | 人教版数学 7-9 年级 + 二次函数 + 几何证明 |
| 高中（10-12）| ~50 个核心 | 人教版数学 + 物理 + 化学 + 生物 |

### 7.2 课程标准与 ECOS 状态的映射

| 课程标准 | ECOS 状态 |
|---|---|
| "理解" | BloomProfile L2 Understand 维度 |
| "掌握" | BKT P(L) ≥ 0.8 |
| "应用" | BloomProfile L3 Apply ≥ 0.7 |
| "分析" | BloomProfile L4 Analyze ≥ 0.6 |

---

## 8. ECOS 在不同学段的产品形态

### 8.1 小学阶段产品形态

- **UI 风格**：高色彩 + 游戏化 + 进度条
- **家长端频率**：每周（家长是主要决策者）
- **教师端频率**：每月（教师使用班级数据）
- **干预时长**：≤ 15 分钟/次
- **核心场景**：作业辅导 + 错题订正

### 8.2 初中阶段产品形态

- **UI 风格**：简洁专业 + 数据可视化
- **家长端频率**：每月
- **教师端频率**：每周（教师更关注）
- **干预时长**：≤ 30 分钟/次
- **核心场景**：作业辅导 + 复习备考 + 错题分析

### 8.3 高中阶段产品形态

- **UI 风格**：极简 + 工具化
- **家长端频率**：每月或季度
- **教师端频率**：每 2 周（高中教师面对 50-100 学生）
- **干预时长**：≤ 45 分钟/次
- **核心场景**：复习备考 + 难题攻克 + 自主学习

---

## 9. 评估指标（对照 04-risks.md）

| 指标 | 阈值 | 学段差异 |
|---|---|---|
| CTA 5D 预测力（H1）| AUC ≥ 0.75 | 初中最高（数据最丰富）|
| Bloom 6 层方差解释（H2）| ≥ 60% | 小学/初中较高，高中更复杂 |
| 双 Agent ECE（H3）| ≤ 0.10 | 各学段一致 |
| TC 检测 F1 | ≥ 0.6 | 高中更高（TC 更明确）|
| Misconception 检测 F1 | ≥ 0.7 | 初中最高（数据集中）|
| 留存率 | ≥ 60%（4 个月）| 小学最难（家长决定）|
| 元认知干预完成率 | ≥ 50% | 高中最高 |

---

## 10. 关联文档

- **同级教学法层**（按依赖顺序）：
  - [02-bloom-application.md](02-bloom-application.md) — Bloom 在 K12 的应用
  - [03-learning-strategies.md](03-learning-strategies.md) — 学习策略空间
  - [04-zpd-application.md](04-zpd-application.md) — ZPD 在 ECOS 的应用
- **P0 借鉴**（理论依据）：
  - [v0.5.0 C 维度内容库 §1.7 数学 TC 库](../../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md) — TC 库候选
  - [v0.5.0 §2.6 初中数学 Misconception 库](../../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md) — Misconception 候选
- **上层文档**：
  - [02-architecture.md §2.1 State Space](../research/00-overview/02-architecture.md) — 5D 状态向量
  - [01-applications.md §6 不做清单](../research/00-overview/01-applications.md) — 学段边界
  - [04-risks.md §B1 + §B3](../research/00-overview/04-risks.md) — 风险评估
- **核心论证**：
  - [v2.0 §1.4 K12 三大优势](../../research/deep-research/Cognitive-Digital-Twin-Deep-Research.md) — 数据丰富 + B 易定义 + 易验证
- **工程层**（按本文档配置调整）：
  - [01-cta-belief-engine.md](../research/10-engineering/01-cta-belief-engine.md) — CTA 引擎
  - [02-lca-policy-engine.md](../research/10-engineering/02-lca-policy-engine.md) — LCA 引擎
  - [03-bloom-goal-library.md](../research/10-engineering/03-bloom-goal-library.md) — Bloom 库

---

## 11. 版本与维护

- **v1.0**（2026-06-25）— 初版

**待办（影响本文档时同步更新）**：
- 当 [02-bloom-application.md](02-bloom-application.md) 完成后，§3 BloomProfile 调整引用 §2.1 各学段 Bloom 适用性
- 当 Phase 5+ 物理/语文库完成后，更新 §5.1 学科 × 认知结构映射
- 当 Phase 4 MVP 实验完成后，回填 §9 实际评估指标 vs 阈值

---

**创建日期**：2026-06-25
**维护者**：Bisen & Claude
