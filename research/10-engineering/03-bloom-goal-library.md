# Bloom Goal Library（Bloom 目标库）

> **版本**：v1.0（2026-06-25）
> **性质**：工程层第 3 份文档——Bloom 目标库的工程实现设计
> **基于**：[v2.0 §3.4 LCA + Bloom 映射](../deep-research/Cognitive-Digital-Twin-Deep-Research.md)、[02-architecture.md §2.2 Bloom Goal Space](../00-overview/02-architecture.md)、[v0.5.0 C 维度内容库](../30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md)、[01-cta-belief-engine.md](01-cta-belief-engine.md)、[02-lca-policy-engine.md](02-lca-policy-engine.md)、[03-roadmap.md §2.2 M2 里程碑](../00-overview/03-roadmap.md)、[04-risks.md §B1 Bloom 风险](../00-overview/04-risks.md)
> **后续**：[04-dual-agent-calibration.md](04-dual-agent-calibration.md)、[05-persistence-session.md](05-persistence-session.md)
> **维护者**：Bisen & Claude

---

## 0. 模块定位

### 0.1 核心职责

**Bloom Goal Library**是 ECOS 的"目标坐标系"——把 Bloom 分类学的 6 层认知层级工程化为可计算的目标库。核心职责：

1. **结构化定义 6 层认知层级**——每层有明确的认知行为 + 评估标准
2. **构建学科 Bloom 目标库**——数学（MVP）/ 物理 / 语文等学科每门 × 6 层的具体目标
3. **作为 CTA 状态估计的目标**——CTA 估计学生在每层的掌握度
4. **作为 LCA 干预选择的目标**——LCA 选干预时锁定 Bloom 层

**关键定位**：Bloom Goal Library 是 **CTA 与 LCA 之间的"共同语言"**——CTA 输出"学生在 L3 掌握 0.6"，LCA 据此选"目标 L4 的干预"。

### 0.2 与其他模块的接口

```
┌─────────────────────────────────────────────────────────────┐
│ Persistence Layer（[05-persistence-session.md](05-persistence-session.md)）│
│   ↓ curriculum_standards（中国教育部 / Common Core）        │
│ Bloom Goal Library（本模块）                                 │
│   ↓ BloomGoal[]（按知识点 + 层）                              │
│   ├→ CTA Belief Engine：学生 BloomProfile 估计              │
│   └→ LCA Policy Engine：next_target 选择 + 干预参数         │
└─────────────────────────────────────────────────────────────┘
```

### 0.3 与 v0.5.0 C 维度内容库的关系

- **BloomGoal 引用 TC**：每个 BloomGoal 可标注相关 Threshold Concept
- **BloomGoal 引用 Misconception**：每个 BloomGoal 可标注常见 misconception
- **TC 库决定 Bloom 跨越路径**：跨越"函数"TC 后 BloomProfile 自动提升
- **Misconception 检测影响 BloomProfile**：命中 misconception → BloomProfile 下调

### 0.4 文档目标读者

- **课程专家**：构建学科 Bloom 目标库
- **教师**：审核与课程标准的对接
- **工程实现者**：实现 `ecos/bloom/` Python 模块
- **CTA / LCA 实现者**：理解目标坐标系

---

## 1. 整体架构

### 1.1 6 层 Bloom 分类的工程化

[v2.0 §3.4 + 02-architecture.md §2.2](../00-overview/02-architecture.md) 已给出 6 层 Bloom + Policy Space 定义。本文档聚焦"目标库"的工程实现。

| Bloom 层 | 中文 | 含义 | 数学例子 | 物理例子 | 语文例子 |
|---|---|---|---|---|---|
| **L1 Remember** | 记忆 | 记忆定义/公式/事实 | 二次函数顶点公式 y=a(x-h)²+k | F=ma 公式 | 《静夜思》全文 |
| **L2 Understand** | 理解 | 解释/分类/归纳 | 为什么抛物线开口由 a 决定 | 牛顿第二定律的物理意义 | 古诗的意象 |
| **L3 Apply** | 应用 | 应用到新情境 | 用顶点公式求最值 | 用 F=ma 解题 | 用典故分析主题 |
| **L4 Analyze** | 分析 | 分解/比较/识别模式 | "配方求最值" vs "导数求最值" | 区分力学三种力 | 修辞手法辨析 |
| **L5 Evaluate** | 评价 | 评判/辩护/选择 | 选择最优建模方法 | 评价物理模型适用性 | 评价文学作品 |
| **L6 Create** | 创造 | 综合/设计/创造 | 设计新题型 | 设计物理实验 | 创作短文 |

### 1.2 模块目录结构

```
ecos/bloom/
├── __init__.py
├── levels.py                   # BloomLevel 枚举 + 行为定义
├── goal.py                     # BloomGoal 数据结构
├── library.py                  # BloomGoalLibrary 容器 + 查询接口
├── subject_libraries/
│   ├── __init__.py
│   ├── math.py                 # 数学 Bloom 目标库（MVP）
│   ├── physics.py              # 物理 Bloom 目标库（Phase 5+）
│   ├── language.py             # 语文 Bloom 目标库（Phase 5+）
│   └── cross_subject.py        # 跨学科 Bloom 整合
├── curriculum/
│   ├── __init__.py
│   ├── china_standard.py       # 中国教育部课程标准对接
│   ├── common_core.py          # Common Core 对接（Phase 5+）
│   └── mapper.py               # 课程标准 ↔ BloomGoal 映射
├── selection/
│   ├── __init__.py
│   └── next_target.py          # next_target 选择算法
├── integration/
│   ├── __init__.py
│   ├── tc_integration.py       # 与 v0.5.0 TC 库集成
│   ├── misc_integration.py     # 与 v0.5.0 Misconception 库集成
│   └── q_matrix.py             # Q 矩阵（含 Bloom + TC + Misconception）
├── tests/
│   ├── test_math_library.py    # 数学库测试
│   ├── test_next_target.py     # 选择算法测试
│   └── test_integration.py     # 集成测试
└── README.md                   # Bloom 库使用说明
```

### 1.3 与 CTA / LCA 接口契约

**CTA → Bloom Library 接口**：

```python
@dataclass
class BloomGoalQuery:
    """CTA 查询 Bloom 库"""
    skill_id: str                        # 知识点 ID
    bloom_layer: BloomLevel              # 目标 Bloom 层
    include_tcs: bool = True             # 是否包含 TC
    include_miscs: bool = True           # 是否包含 Misconception

@dataclass
class BloomGoalQueryResult:
    """Bloom 库返回"""
    bloom_goal: BloomGoal                # 完整 BloomGoal
    tcs: List[str]                       # 相关 TC IDs
    misconceptions: List[str]            # 相关 Misconception IDs
    problems: List[str]                  # 该 BloomGoal 的考察题目 IDs
    next_bloom_options: List[BloomLevel] # 该目标完成后可挑战的下一层
```

**LCA → Bloom Library 接口**：

```python
@dataclass
class BloomTargetSelection:
    """LCA 选择 Bloom 目标"""
    student_id: str
    current_bloom_profile: 'BloomProfileState'
    target_skill_id: str
    candidate_bloom_layers: List[BloomLevel]
    constraints: Dict[str, Any]           # 约束（如"L4+ 仅资深学生"）

@dataclass
class BloomTargetResult:
    """Bloom 库返回"""
    selected_layer: BloomLevel
    target_bloom_goal: BloomGoal
    learning_path: List[BloomGoal]       # 完整学习路径（含前置 + 当前 + 后置）
    expected_gain: float                 # 期望状态改善量
    prerequisites_met: bool              # 前置 BloomGoal 是否已掌握
```

---

## 2. Bloom 数据结构

### 2.1 BloomLevel 枚举（与 [01-cta-belief-engine.md](../10-engineering/01-cta-belief-engine.md) 一致）

```python
# ecos/bloom/levels.py
from enum import IntEnum
from dataclasses import dataclass

class BloomLevel(IntEnum):
    """Bloom 6 层（K12 适用）"""
    REMEMBER = 1
    UNDERSTAND = 2
    APPLY = 3
    ANALYZE = 4
    EVALUATE = 5
    CREATE = 6

@dataclass
class BloomLevelBehavior:
    """每层认知行为定义（与课程标准对齐）"""
    level: BloomLevel
    name_cn: str                         # 中文名
    name_en: str                         # 英文名
    cognitive_verb: List[str]            # 该层认知动词（如 Remember: "定义/列出/回忆"）
    description: str                     # 行为描述
    assessment_criteria: str             # 评估标准
    prerequisite_levels: List[BloomLevel]  # 前置层

BLOOM_LEVELS = {
    BloomLevel.REMEMBER: BloomLevelBehavior(
        level=BloomLevel.REMEMBER,
        name_cn="记忆",
        name_en="Remember",
        cognitive_verb=["定义", "列出", "回忆", "识别", "命名"],
        description="记忆事实、术语、定义、公式等基础知识",
        assessment_criteria="能准确回忆出所学知识点",
        prerequisite_levels=[],
    ),
    BloomLevel.UNDERSTAND: BloomLevelBehavior(
        level=BloomLevel.UNDERSTAND,
        name_cn="理解",
        name_en="Understand",
        cognitive_verb=["解释", "归纳", "分类", "总结", "推断"],
        description="解释概念、归纳规律、分类对象",
        assessment_criteria="能用自己语言解释概念或归纳规律",
        prerequisite_levels=[BloomLevel.REMEMBER],
    ),
    BloomLevel.APPLY: BloomLevelBehavior(
        level=BloomLevel.APPLY,
        name_cn="应用",
        name_en="Apply",
        cognitive_verb=["应用", "使用", "执行", "实施", "解决"],
        description="将所学应用到新情境或解决具体问题",
        assessment_criteria="能在新情境中正确应用所学",
        prerequisite_levels=[BloomLevel.UNDERSTAND],
    ),
    BloomLevel.ANALYZE: BloomLevelBehavior(
        level=BloomLevel.ANALYZE,
        name_cn="分析",
        name_en="Analyze",
        cognitive_verb=["分解", "比较", "对比", "识别模式", "归因"],
        description="分解信息、识别模式、比较方法",
        assessment_criteria="能拆解题目的结构并识别不同方法",
        prerequisite_levels=[BloomLevel.APPLY],
    ),
    BloomLevel.EVALUATE: BloomLevelBehavior(
        level=BloomLevel.EVALUATE,
        name_cn="评价",
        name_en="Evaluate",
        cognitive_verb=["评判", "辩护", "选择", "论证", "批评"],
        description="基于标准做出评判、为选择辩护",
        assessment_criteria="能基于标准选择最优方法并辩护",
        prerequisite_levels=[BloomLevel.ANALYZE],
    ),
    BloomLevel.CREATE: BloomLevelBehavior(
        level=BloomLevel.CREATE,
        name_cn="创造",
        name_en="Create",
        cognitive_verb=["设计", "综合", "构建", "创造", "发明"],
        description="综合要素、创造新事物、设计新方案",
        assessment_criteria="能综合多种方法设计新方案或题目",
        prerequisite_levels=[BloomLevel.EVALUATE],
    ),
}
```

### 2.2 BloomGoal 数据结构

```python
# ecos/bloom/goal.py
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from datetime import datetime

@dataclass
class BloomGoal:
    """单个 Bloom 目标——知识点 × Bloom 层"""
    # 基本信息
    goal_id: str                         # 唯一 ID，如 "MATH.QUAD.APL"
    subject: str                         # "math" / "physics" / "language"
    skill_id: str                        # 知识点 ID，如 "quadratic_function"
    skill_name: str                      # 知识点名，如 "二次函数"
    bloom_layer: BloomLevel              # 目标 Bloom 层
    # 目标定义
    description: str                     # 目标描述
    cognitive_objectives: List[str]      # 认知目标（动词 + 对象）
    assessment_criteria: List[str]       # 评估标准
    # 关联内容（v0.5.0 整合）
    threshold_concepts: List[str]        # 相关 TC IDs
    misconceptions: List[str]            # 相关 Misconception IDs
    # 学习路径
    prerequisites: List[str]             # 前置 BloomGoal IDs
    follow_ups: List[str]                # 后继 BloomGoal IDs
    # 评估题目
    problem_ids: List[str]               # 考察该 BloomGoal 的题目 IDs
    estimated_duration_min: int          # 估计完成时间
    # 课程标准对接
    curriculum_standard_ref: Optional[str] = None  # 课程标准引用（如"人教版数学八年级 §21.2"）
    difficulty_range: tuple = (0.0, 1.0) # 题目难度范围
    # 元数据
    created_by: str = "system"           # 创建者（system / teacher / expert）
    created_at: datetime = field(default_factory=datetime.now)
    version: str = "v1.0"

    def get_metadata(self) -> Dict[str, Any]:
        """获取元数据（用于序列化）"""
        return {
            'goal_id': self.goal_id,
            'subject': self.subject,
            'skill_id': self.skill_id,
            'skill_name': self.skill_name,
            'bloom_layer': self.bloom_layer.value,
            'description': self.description,
            'cognitive_objectives': self.cognitive_objectives,
            'assessment_criteria': self.assessment_criteria,
            'threshold_concepts': self.threshold_concepts,
            'misconceptions': self.misconceptions,
            'prerequisites': self.prerequisites,
            'follow_ups': self.follow_ups,
            'problem_ids': self.problem_ids,
            'curriculum_standard_ref': self.curriculum_standard_ref,
            'difficulty_range': self.difficulty_range,
        }
```

### 2.3 BloomGoalLibrary 容器

```python
# ecos/bloom/library.py
from typing import Dict, List, Optional
from collections import defaultdict

class BloomGoalLibrary:
    """Bloom 目标库容器——按 subject + skill + bloom_layer 索引"""

    def __init__(self):
        self.goals: Dict[str, BloomGoal] = {}  # goal_id → BloomGoal
        # 多维索引
        self.by_subject: Dict[str, List[str]] = defaultdict(list)
        self.by_skill: Dict[str, List[str]] = defaultdict(list)
        self.by_bloom_layer: Dict[BloomLevel, List[str]] = defaultdict(list)
        self.by_subject_skill: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))

    def add_goal(self, goal: BloomGoal):
        """添加 BloomGoal"""
        self.goals[goal.goal_id] = goal
        self.by_subject[goal.subject].append(goal.goal_id)
        self.by_skill[goal.skill_id].append(goal.goal_id)
        self.by_bloom_layer[goal.bloom_layer].append(goal.goal_id)
        self.by_subject_skill[goal.subject][goal.skill_id].append(goal.goal_id)

    def get_goal(self, goal_id: str) -> Optional[BloomGoal]:
        """按 ID 获取"""
        return self.goals.get(goal_id)

    def query(self, query: BloomGoalQuery) -> Optional[BloomGoalQueryResult]:
        """按 subject + skill + bloom_layer 查询"""
        goal_id = f"{query.skill_id}.L{query.bloom_layer.value}"
        goal = self.goals.get(goal_id)
        if goal is None:
            return None
        return BloomGoalQueryResult(
            bloom_goal=goal,
            tcs=goal.threshold_concepts if query.include_tcs else [],
            misconceptions=goal.misconceptions if query.include_miscs else [],
            problems=goal.problem_ids,
            next_bloom_options=self._get_next_bloom_options(goal),
        )

    def get_skill_all_layers(self, subject: str, skill_id: str) -> List[BloomGoal]:
        """获取某知识点在所有 Bloom 层的目标"""
        goal_ids = self.by_subject_skill[subject].get(skill_id, [])
        return [self.goals[gid] for gid in goal_ids]

    def get_subject_all_skills(self, subject: str) -> List[str]:
        """获取某学科的所有知识点"""
        return list(self.by_subject_skill[subject].keys())

    def get_bloom_layer_goals(self, subject: str, layer: BloomLevel) -> List[BloomGoal]:
        """获取某学科某 Bloom 层所有目标"""
        goal_ids = [
            gid for gid in self.by_bloom_layer[layer]
            if self.goals[gid].subject == subject
        ]
        return [self.goals[gid] for gid in goal_ids]
```

---

## 3. 数学 Bloom 目标库（MVP 核心）

### 3.1 数学 6 层定义

基于 [v0.5.0 §1.7 初中数学 TC 库（MVP 候选）](../30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md) + 中国人教版数学课程标准：

```python
# ecos/bloom/subject_libraries/math.py
from ..levels import BloomLevel
from ..goal import BloomGoal

# MVP：8 个核心知识点 × 6 层 = 48 条 BloomGoal
# 覆盖初中数学核心单元（人教版 7-9 年级）
MATH_GOALS_MVP = [
    # === 1. 二次函数 (quadratic_function) - TC ===
    BloomGoal(
        goal_id="MATH.QUAD.L1",
        subject="math",
        skill_id="quadratic_function",
        skill_name="二次函数",
        bloom_layer=BloomLevel.REMEMBER,
        description="记忆二次函数的标准形式 y=ax²+bx+c 与顶点式 y=a(x-h)²+k",
        cognitive_objectives=["定义二次函数", "写出标准形式与顶点式", "识别 a/b/c/h/k 参数"],
        assessment_criteria=["能准确写出二次函数标准式", "能从一般式转化顶点式", "能从顶点式识别对称轴与最值点"],
        threshold_concepts=["TC_function", "TC_quadratic_form"],
        misconceptions=["M7", "M8"],
        prerequisites=[],
        follow_ups=["MATH.QUAD.L2"],
        problem_ids=["MATH.QUAD.PROB.L1.001", "MATH.QUAD.PROB.L1.002"],
        estimated_duration_min=15,
        curriculum_standard_ref="人教版数学九年级 §26.1",
    ),
    BloomGoal(
        goal_id="MATH.QUAD.L2",
        subject="math",
        skill_id="quadratic_function",
        skill_name="二次函数",
        bloom_layer=BloomLevel.UNDERSTAND,
        description="理解二次函数图像（抛物线）与参数的关系",
        cognitive_objectives=["解释开口方向由 a 决定", "归纳对称轴与最值的几何意义", "对比一般式与顶点式的等价性"],
        assessment_criteria=["能解释为什么 a>0 时开口向上", "能归纳对称轴与最值点的关系", "能解释一般式与顶点式的等价性"],
        threshold_concepts=["TC_function"],
        misconceptions=["M7"],
        prerequisites=["MATH.QUAD.L1"],
        follow_ups=["MATH.QUAD.L3"],
        problem_ids=["MATH.QUAD.PROB.L2.001", "MATH.QUAD.PROB.L2.002"],
        estimated_duration_min=20,
        curriculum_standard_ref="人教版数学九年级 §26.2",
    ),
    BloomGoal(
        goal_id="MATH.QUAD.L3",
        subject="math",
        skill_id="quadratic_function",
        skill_name="二次函数",
        bloom_layer=BloomLevel.APPLY,
        description="应用二次函数解决最值问题（如抛物线型桥梁的最大高度）",
        cognitive_objectives=["应用顶点公式求最值", "建立实际情境的二次函数模型", "使用配方或导数方法求最值"],
        assessment_criteria=["能正确建立实际情境的二次函数模型", "能用顶点公式求最值", "能验证答案的合理性"],
        threshold_concepts=["TC_function"],
        misconceptions=["M10"],
        prerequisites=["MATH.QUAD.L2"],
        follow_ups=["MATH.QUAD.L4"],
        problem_ids=["MATH.QUAD.PROB.L3.001", "MATH.QUAD.PROB.L3.002"],
        estimated_duration_min=30,
        curriculum_standard_ref="人教版数学九年级 §26.3",
    ),
    BloomGoal(
        goal_id="MATH.QUAD.L4",
        subject="math",
        skill_id="quadratic_function",
        skill_name="二次函数",
        bloom_layer=BloomLevel.ANALYZE,
        description="分析不同方法（配方 vs 导数）求二次函数最值的优劣",
        cognitive_objectives=["分解配方法的步骤", "比较配方与导数", "识别两者的适用场景"],
        assessment_criteria=["能分解配方法的核心步骤", "能比较两种方法的计算量与适用性", "能识别何时用哪种方法"],
        threshold_concepts=[],
        misconceptions=[],
        prerequisites=["MATH.QUAD.L3"],
        follow_ups=[],
        problem_ids=["MATH.QUAD.PROB.L4.001"],
        estimated_duration_min=25,
        curriculum_standard_ref="人教版数学九年级 §26.4",
    ),
    # L5/L6 在 K12 不常达到（MVP 不实现，详见 04-risks.md §B1）
    # ...

    # === 2. 函数 (function) - TC（核心）===
    # 类似结构：L1-L4 各一条
    # ...

    # === 3. 一次函数 (linear_function) ===
    # === 4. 反比例函数 (inverse_proportion) ===
    # === 5. 几何证明 (geometric_proof) - TC ===
    # === 6. 三角形 (triangle) ===
    # === 7. 圆 (circle) ===
    # === 8. 概率与统计 (probability_statistics) ===
]

def load_math_library() -> BloomGoalLibrary:
    """加载数学 Bloom 目标库（MVP）"""
    library = BloomGoalLibrary()
    for goal in MATH_GOALS_MVP:
        library.add_goal(goal)
    return library
```

### 3.2 MVP 候选 8 个核心知识点（与 TC 库对齐）

基于 [v0.5.0 §1.7 初中数学 TC 库](../30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md)：

| # | 知识点 | TC | L1 | L2 | L3 | L4 | L5 | L6 |
|---|---|---|---|---|---|---|---|---|
| 1 | 二次函数 | TC_quadratic | ✅ | ✅ | ✅ | ✅ | ⚠️ | ⚠️ |
| 2 | 函数 | TC_function | ✅ | ✅ | ✅ | ✅ | ⚠️ | ⚠️ |
| 3 | 变量 | TC_variable | ✅ | ✅ | ✅ | ✅ | ⚠️ | ⚠️ |
| 4 | 一次函数 | - | ✅ | ✅ | ✅ | ✅ | ⚠️ | ⚠️ |
| 5 | 反比例函数 | - | ✅ | ✅ | ✅ | ✅ | ⚠️ | ⚠️ |
| 6 | 几何证明 | TC_proof | ✅ | ✅ | ✅ | ✅ | ⚠️ | ⚠️ |
| 7 | 三角形 | - | ✅ | ✅ | ✅ | ✅ | ⚠️ | ⚠️ |
| 8 | 概率与统计 | - | ✅ | ✅ | ✅ | ✅ | ⚠️ | ⚠️ |

**MVP 库规模**：8 知识点 × 4 层（实际实现 L1-L4）= **32 条 BloomGoal**

[L5/L6 在 K12 阶段不常达到](https://www.bloomschool.org/)（基于 [04-risks.md §B1 风险评估](../00-overview/04-risks.md)）—— v0.5.0 已识别；MVP 暂不实现 L5/L6，留待 Phase 5+。

### 3.3 与中国课程标准对接

```python
# ecos/bloom/curriculum/china_standard.py
class ChinaCurriculumStandard:
    """中国教育部课程标准对接

    数据来源：
    - 《义务教育数学课程标准（2011 年版）》
    - 《义务教育数学课程标准（2022 年版）》（如有）
    - 人教版 / 北师大版 / 苏教版教材
    """

    # 学段映射
    GRADE_TO_STAGE = {
        '小学 1-2 年级': 'stage1_1_2',
        '小学 3-4 年级': 'stage2_3_4',
        '小学 5-6 年级': 'stage3_5_6',
        '初中 7-9 年级': 'stage4_7_9',
        '高中 10-12 年级': 'stage5_10_12',
    }

    # 数学核心知识点（按学段）
    MATH_CORE_SKILLS = {
        'stage4_7_9': [  # 初中
            'quadratic_function', 'function', 'variable', 'linear_function',
            'inverse_proportion', 'geometric_proof', 'triangle', 'circle',
            'probability_statistics',
        ],
    }

    @classmethod
    def get_standard_ref(cls, subject: str, grade: str, skill_id: str) -> Optional[str]:
        """获取课程标准引用"""
        stage = cls.GRADE_TO_STAGE.get(grade)
        if stage is None:
            return None
        # 从标准库查询
        # 例如：人教版数学九年级 §26.1 = "二次函数图像"
        return cls._lookup_standard(subject, stage, skill_id)
```

### 3.4 课程标准 ↔ BloomGoal 映射

```python
# ecos/bloom/curriculum/mapper.py
class CurriculumStandardMapper:
    """课程标准 ↔ BloomGoal 双向映射"""

    def __init__(self, library: BloomGoalLibrary, standard: ChinaCurriculumStandard):
        self.library = library
        self.standard = standard

    def map_standard_to_bloom(self, standard_ref: str) -> List[BloomGoal]:
        """从课程标准引用映射到 BloomGoal 列表"""
        # 反向查找：人教版数学九年级 §26.1 → "quadratic_function" → L1
        skill_id, default_layer = self.standard._parse_ref(standard_ref)
        return self.library.get_skill_all_layers("math", skill_id)

    def map_bloom_to_standard(self, goal: BloomGoal) -> str:
        """从 BloomGoal 映射到课程标准引用"""
        return goal.curriculum_standard_ref or "未对应"
```

---

## 4. 物理 Bloom 目标库（Phase 5+ 扩展）

### 4.1 物理 6 层定义

基于人教版物理课程标准（初中 + 高中）。MVP 不实现，Phase 5+ 扩展：

```python
# ecos/bloom/subject_libraries/physics.py（Phase 5+）
PHYSICS_GOALS_PHASE_5 = [
    # === 力学 ===
    # F=ma: L1-L4
    # 力的分解: L1-L4
    # 圆周运动: L1-L4
    # === 电学 ===
    # 欧姆定律: L1-L4
    # 电磁感应: L1-L4
    # === 光学/热学 ===
    # ...
]
```

### 4.2 物理 vs 数学 Bloom 差异

| 维度 | 数学 | 物理 |
|---|---|---|
| **L1 Remember** | 公式记忆 | 公式 + 物理量定义 |
| **L2 Understand** | 概念解释 | 物理意义 + 实验现象 |
| **L3 Apply** | 解题 | 解题 + 实验操作 |
| **L4 Analyze** | 方法比较 | 物理模型比较（如力学三种力）|
| **L5 Evaluate** | 选最优方法 | 评价物理模型适用性 |
| **L6 Create** | 设计新题型 | 设计物理实验 |

---

## 5. 语文 Bloom 目标库（Phase 5+ 扩展）

### 5.1 语文 6 层定义（不同于数学/物理）

语文 Bloom 不能照搬数学/物理——语文强调"理解 + 表达"，层级结构不同：

```python
# ecos/bloom/subject_libraries/language.py（Phase 5+）
LANGUAGE_GOALS_PHASE_5 = [
    # === 古诗 ===
    # 静夜思: L1（记忆全文）+ L2（理解意象）+ L4（修辞手法）
    # === 现代文阅读 ===
    # 主题分析: L3（应用） + L4（分析）
    # === 写作 ===
    # 议论文: L4（分析论证结构）+ L5（评价论证质量）+ L6（独立创作）
]
```

### 5.2 语文 Bloom 的特殊考量

- **L1-L2 主导**：语文 K12 主要在 L1-L2（记忆 + 理解），L3-L4 在阅读中，L5-L6 在写作中
- **表达 vs 理解并重**：语文目标不仅是"理解"，还包括"表达"
- **主观性强**：语文评估比数学难（答案可能不完全唯一）——需要 LLM rubric 辅助

---

## 6. 跨学科 Bloom 整合

### 6.1 跨学科 BloomGoal

```python
# ecos/bloom/subject_libraries/cross_subject.py
CROSS_SUBJECT_GOALS = [
    BloomGoal(
        goal_id="CROSS.MODEL.L4",
        subject="cross_subject",
        skill_id="mathematical_modeling",
        skill_name="数学建模",
        bloom_layer=BloomLevel.ANALYZE,
        description="识别数学/物理情境中的共同建模模式",
        cognitive_objectives=["识别建模模式", "对比数学与物理建模方法", "迁移建模经验"],
        assessment_criteria=["能识别数学应用题与物理题的共同建模结构", "能对比两种建模方法的差异", "能跨学科迁移建模经验"],
        threshold_concepts=[],
        misconceptions=[],
        prerequisites=["MATH.QUAD.L3"],
        follow_ups=[],
        problem_ids=["CROSS.MODEL.PROB.L4.001"],
        estimated_duration_min=40,
        curriculum_standard_ref=None,
    ),
    # ...更多跨学科目标
]
```

### 6.2 数学 P 与物理 P 的迁移

[01-cta-belief-engine.md §2.1 5D 状态空间](../10-engineering/01-cta-belief-engine.md) 中 P（程序技能）在数学和物理间可迁移——但需要显式建模：

```python
class CrossSubjectTransfer:
    """跨学科能力迁移建模"""

    def __init__(self):
        self.transfer_matrix = self._build_transfer_matrix()

    def transfer_skill_estimate(
        self,
        from_subject: str,  # "math"
        from_skill: str,    # "quadratic_function"
        to_subject: str,    # "physics"
        to_skill: str,      # "projectile_motion"
        from_estimate: float,  # P(L) 在数学
    ) -> float:
        """迁移能力估计"""
        transfer_coef = self.transfer_matrix.get((from_subject, to_subject), 0.0)
        return from_estimate * transfer_coef
```

---

## 7. Bloom 目标选择算法

### 7.1 next_target 主算法

```python
# ecos/bloom/selection/next_target.py
class NextBloomTargetSelector:
    """next_target 选择算法——基于 CTA 状态选择下一个 Bloom 目标"""

    def __init__(self, library: BloomGoalLibrary, config: BloomConfig):
        self.library = library
        self.config = config

    def select(
        self,
        student_id: str,
        belief_state: 'BeliefState',
        target_skill_id: Optional[str] = None,
    ) -> BloomTargetResult:
        """
        选择下一个 Bloom 目标

        算法：
        1. 选目标知识点（默认：当前 BloomProfile 提升空间最大的）
        2. 选目标 Bloom 层（默认：当前层 + 1，但不超过能力上限）
        3. 验证前置条件（前置 BloomGoal 是否已掌握）
        4. 输出学习路径（前置 + 当前 + 后置）
        """
        # Step 1: 选目标知识点
        if target_skill_id is None:
            target_skill_id = self._select_target_skill(belief_state)

        # Step 2: 选目标 Bloom 层
        candidate_layers = self._get_candidate_layers(belief_state, target_skill_id)
        selected_layer = self._select_layer(belief_state, target_skill_id, candidate_layers)

        # Step 3: 获取 BloomGoal
        goal = self.library.query(
            BloomGoalQuery(skill_id=target_skill_id, bloom_layer=selected_layer)
        )

        # Step 4: 验证前置
        prereqs_met = self._check_prerequisites(belief_state, goal.bloom_goal)

        # Step 5: 构造学习路径
        learning_path = self._construct_learning_path(belief_state, goal.bloom_goal)

        return BloomTargetResult(
            selected_layer=selected_layer,
            target_bloom_goal=goal.bloom_goal,
            learning_path=learning_path,
            expected_gain=self._estimate_gain(belief_state, goal.bloom_goal),
            prerequisites_met=prereqs_met,
        )

    def _select_target_skill(self, belief_state: 'BeliefState') -> str:
        """选择目标知识点（提升空间最大 + TC 跨越考量）"""
        # 优先考虑：
        # 1. 当前 BloomProfile 提升空间最大的 skill
        # 2. 处于 liminal 状态的 TC 对应 skill（v0.5.0 整合）
        # 3. 已被 CTA 标记为 intervention_hint 的 skill

        # 默认：选 BloomProfile 最低的层 + 该层最弱的 skill
        bloom = belief_state.bloom_profile
        weakest_layer = min(
            [BloomLevel.REMEMBER, BloomLevel.UNDERSTAND, BloomLevel.APPLY, BloomLevel.ANALYZE],
            key=lambda l: getattr(bloom, l.name.lower(), 0)
        )
        # ...（省略：返回对应 skill_id）
        return "quadratic_function"  # 示例

    def _select_layer(
        self,
        belief_state: 'BeliefState',
        skill_id: str,
        candidates: List[BloomLevel],
    ) -> BloomLevel:
        """选择目标 Bloom 层"""
        # 默认：当前掌握层 + 1（确保挑战性）
        current_layer = belief_state.bloom_profile.dominant_layer
        # 但 BKT P(L) ≥ 0.5 才能挑战下一层
        if belief_state.K.mastery_prob >= 0.5:
            target_layer = min(BloomLevel.ANALYZE, BloomLevel(current_layer.value + 1))
        else:
            target_layer = current_layer  # 维持当前层

        # 但 L5-L6 在 K12 不常达到（MVP 限制）
        if target_layer.value >= 5:
            target_layer = BloomLevel.ANALYZE

        return target_layer

    def _check_prerequisites(
        self,
        belief_state: 'BeliefState',
        goal: BloomGoal,
    ) -> bool:
        """验证前置条件"""
        # 检查每个前置 BloomGoal 是否已掌握
        for prereq_id in goal.prerequisites:
            prereq = self.library.get_goal(prereq_id)
            if prereq is None:
                continue
            # 对应层的 BloomProfile 掌握度 ≥ 0.7 视为掌握
            layer_mastery = getattr(belief_state.bloom_profile, prereq.bloom_layer.name.lower(), 0)
            if layer_mastery < 0.7:
                return False
        return True

    def _construct_learning_path(
        self,
        belief_state: 'BeliefState',
        target_goal: BloomGoal,
    ) -> List[BloomGoal]:
        """构造完整学习路径"""
        path = []
        # 1. 前置路径
        for prereq_id in target_goal.prerequisites:
            prereq = self.library.get_goal(prereq_id)
            if prereq is not None:
                path.append(prereq)
        # 2. 当前目标
        path.append(target_goal)
        # 3. 后继路径（用于 LCA 设计"挑战题"）
        for followup_id in target_goal.follow_ups:
            followup = self.library.get_goal(followup_id)
            if followup is not None:
                path.append(followup)
        return path
```

### 7.2 与 CTA 状态映射

[01-cta-belief-engine.md §2.1](../10-engineering/01-cta-belief-engine.md) 的 BeliefState 中 BloomProfile 与 Bloom Library 的映射：

| CTA 输出 | Bloom Library 输入 | 用途 |
|---|---|---|
| `bloom_profile.remember` ~ `create` | 各层 BloomGoal 的当前掌握度 | 决定 next_target |
| `bloom_profile.dominant_layer` | 当前学生层级 | 决定挑战层 |
| `K.mastery_prob`, `P.mastery_prob` | 前置条件判断 | `_check_prerequisites` |
| `C.tc_states` | TC 状态 | 优先跨越 TC 对应 skill |

### 7.3 与 LCA 干预映射

[02-lca-policy-engine.md §2.2 5 类干预 × 4 参数](../10-engineering/02-lca-policy-engine.md) 中干预类型与 Bloom 层映射：

| Bloom 层 | 默认干预类型（v0.4.0 §4.2）| 说明 |
|---|---|---|
| **L1 Remember** | EXPLANATORY + PRACTICE | 闪卡 + 重复练习 |
| **L2 Understand** | EXPLANATORY + METACOGNITIVE | 类比 + 自我解释 |
| **L3 Apply** | PRACTICE + INQUIRY | 变式练习 + 应用题 |
| **L4 Analyze** | INQUIRY + METACOGNITIVE | 拆题 + 思维导图 |
| **L5 Evaluate** | INQUIRY + METACOGNITIVE | 辩论 + 评判（K12 少用）|
| **L6 Create** | INQUIRY | 项目学习（K12 少用）|

---

## 8. 与 TC / Misconception 库的集成

### 8.1 TC 集成（v0.5.0）

```python
# ecos/bloom/integration/tc_integration.py
class BloomTCIntegration:
    """Bloom Library ↔ v0.5.0 TC 库集成"""

    def __init__(self, bloom_library: BloomGoalLibrary, tc_library: 'ThresholdConceptLibrary'):
        self.bloom_library = bloom_library
        self.tc_library = tc_library

    def get_tcs_for_bloom_goal(self, goal: BloomGoal) -> List['ThresholdConcept']:
        """获取 BloomGoal 关联的 TC"""
        return [
            self.tc_library.get_tc(tc_id)
            for tc_id in goal.threshold_concepts
        ]

    def update_bloom_after_tc_crossing(
        self,
        belief_state: 'BeliefState',
        crossed_tc_id: str,
    ) -> 'BloomProfileState':
        """TC 跨越后 BloomProfile 自动提升"""
        # 找到该 TC 关联的所有 BloomGoal
        affected_goals = self._find_goals_by_tc(crossed_tc_id)

        # 每个 affected_goal 在 CTA BloomProfile 中提升
        new_bloom = belief_state.bloom_profile
        for goal in affected_goals:
            current = getattr(new_bloom, goal.bloom_layer.name.lower(), 0)
            setattr(new_bloom, goal.bloom_layer.name.lower(), min(1.0, current + 0.1))

        return new_bloom
```

### 8.2 Misconception 集成（v0.5.0）

```python
# ecos/bloom/integration/misc_integration.py
class BloomMisconceptionIntegration:
    """Bloom Library ↔ v0.5.0 Misconception 库集成"""

    def adjust_bloom_for_misconception(
        self,
        belief_state: 'BeliefState',
        misconception_hit: 'MisconceptionHit',
    ) -> 'BloomProfileState':
        """命中 misconception 后 BloomProfile 下调"""
        new_bloom = belief_state.bloom_profile
        # 找到该 misconception 关联的 BloomGoal
        affected_goals = self._find_goals_by_misc(misconception_hit.misc_id)

        for goal in affected_goals:
            current = getattr(new_bloom, goal.bloom_layer.name.lower(), 0)
            setattr(new_bloom, goal.bloom_layer.name.lower(), current * 0.7)  # 折扣 30%

        return new_bloom
```

### 8.3 Q 矩阵扩展（CD-CAT 集成）

[01-cta-belief-engine.md §6.2 Q 矩阵扩展](../10-engineering/01-cta-belief-engine.md) 给出 Q 矩阵应包含 BloomGoal ID + TC + Misconception：

```python
# ecos/bloom/integration/q_matrix.py
class QMatrixEntry:
    """Q 矩阵条目"""
    problem_id: str
    bloom_goal_id: str             # 来自 Bloom Library
    skill_id: str
    bloom_layer: BloomLevel
    threshold_concepts: List[str]  # 来自 v0.5.0 TC 库
    misconceptions: List[str]      # 来自 v0.5.0 Misconception 库
    difficulty: float
    mirt_params: 'MIRTItemParams'  # 来自 MIRT
```

---

## 9. Bloom Goal Library 查询接口

### 9.1 基础查询

```python
library = load_math_library()

# 查询：二次函数 + L3 Apply
result = library.query(
    BloomGoalQuery(
        skill_id="quadratic_function",
        bloom_layer=BloomLevel.APPLY,
    )
)
print(f"目标: {result.bloom_goal.skill_name} @ {result.bloom_goal.bloom_layer.name_cn}")
print(f"TCs: {result.tcs}")
print(f"Misconceptions: {result.misconceptions}")
print(f"题目: {result.problems}")
print(f"下一层: {[l.name_cn for l in result.next_bloom_options]}")
```

### 9.2 选择 next_target

```python
selector = NextBloomTargetSelector(library, BloomConfig())

# 模拟 CTA 状态
belief_state = BeliefState(
    bloom_profile=BloomProfileState(
        remember=0.9, understand=0.7, apply=0.5, analyze=0.2,
        evaluate=0.1, create=0.05,
        dominant_layer=BloomLevel.APPLY,
    ),
    K=DimensionState(theta=0.5, mastery_prob=0.5, ...),
    # ...
)

target = selector.select(student_id="S001", belief_state=belief_state)
print(f"下一目标: {target.target_bloom_goal.goal_id}")
print(f"前置满足: {target.prerequisites_met}")
print(f"学习路径: {[g.goal_id for g in target.learning_path]}")
```

### 9.3 集成示例（CTA + Bloom Library + LCA）

```python
# CTA 输入 → Bloom 选择 → LCA 输入
cta_output = cta.update(observation)  # CTAOutput
# CTAOutput 包含 bloom_target_candidates
selected = selector.select(
    student_id=cta_output.student_id,
    belief_state=cta_output.belief_state,
    target_skill_id=None,  # 自动选择
)
lca_result = lca.select_intervention(
    CTAInput(
        student_id=cta_output.student_id,
        belief_state=cta_output.belief_state,
        bloom_target_candidates=[selected.selected_layer],
        # ...
    )
)
```

---

## 10. 测试策略

### 10.1 单元测试（覆盖率 ≥ 80%）

| 模块 | 测试重点 | 覆盖率目标 |
|---|---|---|
| `levels.py` | 6 层定义正确性、前置关系 | ≥ 95% |
| `goal.py` | BloomGoal 序列化、元数据 | ≥ 90% |
| `library.py` | 查询接口、索引正确性 | ≥ 90% |
| `subject_libraries/math.py` | 32 条 MVP BloomGoal 完整性 | ≥ 80% |
| `curriculum/mapper.py` | 课程标准 ↔ BloomGoal 双向映射 | ≥ 85% |
| `selection/next_target.py` | 选择算法正确性（基于 CTA 状态）| ≥ 85% |
| `integration/tc_integration.py` | TC 跨越后 BloomProfile 提升 | ≥ 80% |
| `integration/misc_integration.py` | Misconception 命中后 BloomProfile 下调 | ≥ 80% |

### 10.2 集成测试

```python
# ecos/bloom/tests/test_integration.py
def test_full_bloom_pipeline():
    """完整 Bloom 库 + CTA + LCA 集成测试"""
    library = load_math_library()
    cta = CTAOrchestrator(config_for_test())
    lca = LCAOrchestrator(config_for_test())
    selector = NextBloomTargetSelector(library, BloomConfig())

    # 模拟 100 次学生交互
    for i in range(100):
        observation = generate_synthetic_observation(i)
        cta_output = cta.update(observation)
        target = selector.select(
            student_id=cta_output.student_id,
            belief_state=cta_output.belief_state,
        )
        lca_result = lca.select_intervention(...)
        new_observation = simulate_student_response(lca_result.intervention)
        cta.update(new_observation, lca_result)

    # 验证 BloomProfile 演化合理
    assert cta_output.belief_state.bloom_profile.apply > 0.5
    # 验证 L5/L6 未误推到 K12 学生
    assert cta_output.belief_state.bloom_profile.evaluate < 0.3
```

### 10.3 评估指标（对照 04-risks.md §B1 阈值）

| 指标 | 阈值 | 测试场景 |
|---|---|---|
| **BloomProfile 方差解释** | ≥ 60% | 100 学生 BloomProfile vs 学习表现相关性 |
| **数学库覆盖率** | ≥ 80% 课程标准核心知识点 | 与人教版课程标准对比 |
| **课程标准对接准确率** | ≥ 90% | 教师审核 |
| **next_target 合理性** | ≥ 80% 接受率 | 教师反馈 |
| **TC 跨越后 Bloom 提升** | ≥ 0.1 绝对提升 | 模拟实验 |
| **L5/L6 误推率** | 0% | K12 学生应不被推荐 L5/L6 |

---

## 11. MVP 范围（Phase 4）

### 11.1 MVP 包含的组件

| 组件 | 实现状态 |
|---|---|
| 6 层 Bloom 定义 | ✅ MVP |
| 数学 Bloom 目标库（8 知识点 × 4 层 = 32 条）| ✅ MVP |
| 中国课程标准对接（数学）| ✅ MVP |
| BloomGoalLibrary 容器 + 查询接口 | ✅ MVP |
| NextBloomTargetSelector 算法 | ✅ MVP |
| TC 集成（TC 跨越后 BloomProfile 提升）| ✅ MVP |
| Misconception 集成（命中后 BloomProfile 下调）| ✅ MVP |
| Q 矩阵扩展（Bloom + TC + Misconception）| ✅ MVP |

### 11.2 MVP 不包含的组件

- ❌ 物理 Bloom 目标库（Phase 5+）
- ❌ 语文 Bloom 目标库（Phase 5+）
- ❌ 跨学科 BloomGoal（MVP 仅占位）
- ❌ Common Core 对接（Phase 5+ 国际市场）
- ❌ L5/L6 BloomGoal（K12 不常达到）
- ❌ 跨学科能力迁移矩阵（Phase 5+）

### 11.3 数据规模

| 库 | MVP | Phase 5 | Phase 6 |
|---|---|---|---|
| 数学 | 32 条 BloomGoal | 100 条 | 300 条 |
| 物理 | 0 | 80 条 | 200 条 |
| 语文 | 0 | 50 条 | 150 条 |
| 跨学科 | 0 | 5 条 | 20 条 |
| **总计** | **32 条** | **235 条** | **670 条** |

---

## 12. 关联文档

- **同级工程层**：
  - [01-cta-belief-engine.md](01-cta-belief-engine.md) — CTA 信念引擎（消费 BloomGoalQuery）
  - [02-lca-policy-engine.md](02-lca-policy-engine.md) — LCA 策略引擎（消费 BloomTargetResult）
  - [04-dual-agent-calibration.md](04-dual-agent-calibration.md) — 双 Agent 互校（待写）
  - [05-persistence-session.md](05-persistence-session.md) — 持久化（BloomGoal 存储）
- **P0 借鉴**（理论依据）：
  - [v0.5.0 C 维度内容库 §1.7 数学 TC 库](../30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md) — 数学 8 个核心 TC
  - [v0.5.0 §3.2 Q 矩阵集成](../30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md) — Q 矩阵扩展
- **上层文档**：
  - [02-architecture.md §2.2 Bloom Goal Space](../00-overview/02-architecture.md) — 三空间架构
  - [03-roadmap.md §2.2 M2 里程碑](../00-overview/03-roadmap.md) — 工程任务
  - [04-risks.md §B1 Bloom 风险](../00-overview/04-risks.md) — 风险评估
- **核心论证**：
  - [v2.0 §3.4 LCA + Bloom 映射](../deep-research/Cognitive-Digital-Twin-Deep-Research.md) — 干预策略与 Bloom 层映射

---

## 13. 版本与维护

- **v1.0**（2026-06-25）— 初版

**待办（影响本文档时同步更新）**：
- 当 [04-dual-agent-calibration.md](04-dual-agent-calibration.md) 完成后，回填 §6 跨学科 BloomGoal 在双 Agent 互校中的作用
- 当 Phase 4 MVP 实验完成后，回填 §10.3 实际评估指标 vs 阈值
- 当 Phase 5+ 物理/语文库完成后，更新 §11.3 数据规模表

---

**创建日期**：2026-06-25
**维护者**：Bisen & Claude
