# LCA 干预策略引擎（LCA Policy Engine）

> **版本**：v1.0（2026-06-25）
> **性质**：工程层第 2 份文档——LCA（Learning Coach Agent）策略引擎的工程实现设计
> **基于**：[v0.4.0 LCA 教学法基础](../../30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md)（3 大理论群）、[01-cta-belief-engine.md](01-cta-belief-engine.md)（CTA 接口）、[02-architecture.md §6 干预策略工程实现](../00-overview/02-architecture.md)、[03-roadmap.md §2.2 M2 里程碑](../00-overview/03-roadmap.md)、[04-risks.md §A 技术风险 + §C 教育专业风险](../00-overview/04-risks.md)
> **后续**：[03-bloom-goal-library.md](03-bloom-goal-library.md)、[04-dual-agent-calibration.md](04-dual-agent-calibration.md)、[05-persistence-session.md](05-persistence-session.md)
> **维护者**：Bisen & Claude

---

## 0. 模块定位

### 0.1 核心职责

**LCA 策略引擎**是 ECOS 双 Agent 架构中的"改变学生"组件。核心职责：

1. **主动设计干预实验**——不是被动响应，而是"教练"主动探索最优策略
2. **基于 CTA 状态选择最优干预**——消费 CTAOutput（5D 信念分布 + BloomProfile + TC 状态）
3. **持续优化 policy**——基于因果归因反馈（CATE）调整策略权重
4. **生成可解释的 rationale**——让教师/家长理解"为什么推荐这个干预"

**核心思维模式**（v2.0 §3.4）："教练 + 强化学习策略器"——主动、实验、探索、优化

### 0.2 与其他模块的接口

```
┌────────────────────────────────────────────────────────────┐
│ CTA Belief Engine（[01-cta-belief-engine.md](01-cta-belief-engine.md)）│
│   ↓ CTAOutput（5D + BloomProfile + TC 状态 + 干预提示）       │
│ LCA Policy Engine（本模块）                                  │
│   ↓ Intervention（type × params × expected_gain）            │
│ App 层（题目推送 / 讲解视频 / worked example / 测试题）       │
│   ↓ 学生响应（observation）                                  │
│ LCA → CTA → LCAResult（含 causal_effect）→ CTA 更新信念     │
└────────────────────────────────────────────────────────────┘
```

### 0.3 硬底线（与 CTA 一致）

- ✅ **L3-L4 决策层可用 LLM 生成自然语言 rationale**（表达层）
- ✅ **L3 干预类型选择用规则启发 + 教学法决策树**（确定性，可解释）
- ✅ **L4 策略优化用统计学习（Contextual Bandits / POMCP）**（数学层）
- ❌ **LLM 不可用于直接选择干预类型或参数**——任何此类设计都是退路

### 0.4 文档目标读者

- **工程实现者**：按本文档实现 `ecos/lca/` Python 模块
- **教学法研究者**：理解 L3-L4 教学法栈的工程映射
- **教师/家长**：理解 LCA 推荐的可解释输出（rationale）

---

## 1. 整体架构

### 1.1 L3-L4 教学法栈工程映射

[v0.4.0 §6.1 L3-L4 教学法栈工程映射](../../30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md)：

| 层 | 学术方法 | 工程实现 | 开源依赖 | 文件位置 |
|---|---|---|---|---|
| **L3 干预类型选择** | CLT + Bjork 四件套 | 规则启发（教学法决策树）| 自研 | `ecos/lca/l3_selection/` |
| **L3 CLT 4 级呈现** | expertise reversal effect | 模板系统（4 套题目模板）| 自研 | `ecos/lca/l3_selection/clt/` |
| **L3 Bjork 测试效应** | spaced repetition | FSRS 算法 | `ts-fsrs` 或 `py-fsrs` | `ecos/lca/l3_selection/bjork/testing.py` |
| **L3 Bjork 间隔效应** | Ebbinghaus decay | FSRS + 衰减模型 | `ts-fsrs` | `ecos/lca/l3_selection/bjork/spacing.py` |
| **L3 Bjork 合意困难** | desirable difficulties | 启发式规则（Phase 5+）| 自研 | `ecos/lca/l3_selection/bjork/difficulty.py` |
| **L3 Bjork 交错练习** | interleaving | 学科单元内调度（Phase 5+）| 自研 | `ecos/lca/l3_selection/bjork/interleaving.py` |
| **L4 策略优化** | Cognitive Apprenticeship 6 阶段 | 状态机 | 自研 | `ecos/lca/l4_optimization/ca_state_machine.py` |
| **L4 策略学习** | Contextual Bandits（MVP）/ POMCP（Phase 5+）| LinUCB | `vowpalwabbit` 或自研 | `ecos/lca/l4_optimization/bandit.py` |
| **L4 因果归因** | Causal Inference | 与 [CTA L4](01-cta-belief-engine.md#7-l4-因果归因层causal-inference) 协作 | 共享 | `ecos/lca/l4_optimization/attribution.py` |
| **Rationale 输出** | LLM 自然语言生成 | LLM 表达层 | LLM client | `ecos/lca/rationale/` |

### 1.2 模块目录结构

```
ecos/lca/
├── __init__.py
├── intervention.py             # Intervention 数据结构
├── l3_selection/
│   ├── __init__.py
│   ├── selector.py             # 干预类型选择主类
│   ├── clt/
│   │   ├── __init__.py
│   │   ├── adaptive_4level.py  # CLT 4 级自适应呈现
│   │   └── templates.py        # 4 套题目模板
│   ├── bjork/
│   │   ├── __init__.py
│   │   ├── testing.py          # Bjork 测试效应（FSRS）
│   │   ├── spacing.py          # Bjork 间隔效应
│   │   ├── difficulty.py       # 合意困难（Phase 5+）
│   │   └── interleaving.py     # 交错练习（Phase 5+）
│   └── ca/
│       ├── __init__.py
│       └── scaffolding.py      # Cognitive Apprenticeship Scaffolding 衰减
├── l4_optimization/
│   ├── __init__.py
│   ├── ca_state_machine.py     # Cognitive Apprenticeship 6 阶段状态机
│   ├── contextual_bandit.py    # Contextual Bandits (LinUCB)
│   ├── pomcp.py                # POMCP（Phase 5+）
│   └── attribution.py          # 因果归因（与 CTA L4 共享）
├── rationale/
│   ├── __init__.py
│   ├── generator.py            # rationale 生成器
│   └── prompt_templates.py     # LLM prompt 模板
├── orchestrator.py             # LCA 主流程编排
└── tests/
    ├── test_clt.py
    ├── test_bjork.py
    ├── test_ca_state_machine.py
    ├── test_bandit.py
    └── test_integration.py
```

### 1.3 与 CTA / App 接口契约

**输入：CTAOutput**（来自 [01-cta-belief-engine.md §1.3](01-cta-belief-engine.md)）：

```python
@dataclass
class CTAInput:
    """LCA 消费的 CTA 输出"""
    student_id: str
    belief_state: 'BeliefState'              # 5D + BloomProfile + TC 状态
    bloom_target_candidates: List[BloomLevel] # 推荐的目标 Bloom 层
    intervention_hints: Dict[str, Any]        # 干预提示（如"分情况讨论子缺口"）
    confidence: float                        # CTA 整体置信度 0-1
    timestamp: datetime
```

**输出：LCAResult**（反馈给 CTA + App 层）：

```python
@dataclass
class LCAResult:
    """LCA 干预结果"""
    student_id: str
    intervention: 'Intervention'              # 选中的干预
    rationale: str                            # 自然语言解释
    expected_gain: float                      # 期望状态改善量
    expected_risk: float                      # 期望风险
    bloom_target: BloomLevel                  # 目标 Bloom 层
    timestamp: datetime
    # 互校反馈字段（事后填充）
    actual_outcome: Optional[float] = None     # 干预后实际状态变化
    causal_effect: Optional['CausalEffect'] = None  # L4 因果归因
```

**App 层执行接口**：

```python
@dataclass
class AppExecutionRequest:
    """LCA → App 层的执行请求"""
    student_id: str
    intervention_type: str
    problem_id: Optional[str]                  # 题目推送时
    presentation_params: Dict[str, Any]        # CLT 4 级呈现参数
    rationale: str
    expected_response_time: int                # 期望响应时间（秒）
```

---

## 2. 干预参数化空间

### 2.1 Intervention 数据结构

```python
# ecos/lca/intervention.py
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum

class InterventionType(Enum):
    """5 类干预（v0.4.0 §4.2 5 类干预 × 教学法对应）"""
    EXPLANATORY = "explanatory"      # 讲解型：analogy / worked example / socratic
    PRACTICE = "practice"            # 练习型：varied practice / deliberate practice
    INQUIRY = "inquiry"              # 探究型：project-based / inquiry / open task
    FEEDBACK = "feedback"            # 反馈型：immediate / delayed / detailed / sparse
    METACOGNITIVE = "metacognitive"  # 元认知型：self-explanation / reflection / teach-back

class CLTLevel(Enum):
    """CLT 4 级自适应呈现（v0.4.0 §1.3 expertise reversal effect）"""
    NOVICE = 1          # 新手：完整 worked example + 详细解释
    DEVELOPING = 2      # 进阶：worked example + 填空
    PROFICIENT = 3      # 熟练：独立解题 + 即时反馈
    EXPERT = 4          # 专家：独立解题 + 延迟反馈

class CAStage(Enum):
    """Cognitive Apprenticeship 6 阶段（v0.4.0 §3.1）"""
    MODELING = 1        # 建模：专家示范
    COACHING = 2        # 教练：尝试 + 反馈
    SCAFFOLDING = 3     # 脚手架：支持 + 提示
    ARTICULATION = 4    # 表达：讲出思路
    REFLECTION = 5      # 反思：对比差异
    EXPLORATION = 6     # 探究：独立探索

@dataclass
class Intervention:
    """完整干预数据结构"""
    # 基本信息
    intervention_id: str
    student_id: str
    intervention_type: InterventionType
    # 目标
    bloom_target: 'BloomLevel'                 # 目标 Bloom 层
    target_skills: List[str]                   # 目标技能/知识点
    target_misconceptions: List[str]           # 目标修正的 misconception
    target_tcs: List[str]                      # 目标跨越的 TC
    # 参数（v0.4.0 §4.3 参数化空间）
    difficulty: float                          # 0-1，匹配 BloomProfile
    quantity: int                              # 1-10，干预元素数量
    feedback_density: float                    # 0-1，立即 vs 延迟反馈
    scaffolding_level: float                   # 0-1，scaffolding 强度
    # 教学法元数据
    clt_level: CLTLevel                        # CLT 4 级呈现级别
    ca_stage: CAStage                          # 当前 CA 6 阶段位置
    bjork_triggers: List[str]                  # 触发的 Bjork 策略（如 "test" / "space"）
    # 期望输出
    expected_gain: float                       # 期望状态改善量
    expected_risk: float                       # 期望风险
    # 时间
    estimated_duration_sec: int                # 估计完成时长
    created_at: datetime
```

### 2.2 5 类干预 × 4 参数（v0.4.0 §4.3）

```
策略空间 = 5 离散类型 × 4 连续参数 + Bloom 层选择 + CLT 级别 + CA 阶段
         ≈ 5 × ∞⁴ × 6 × 4 × 6 = 高维策略空间
```

| 干预类型 | 教学法对应（v0.4.0）| 典型参数 |
|---|---|---|
| **EXPLANATORY** | CLT Modeling + CA Stage 1 | difficulty=0.3, quantity=1-3, scaffolding=0.9 |
| **PRACTICE** | Bjork 测试效应 + 间隔效应 | difficulty=0.6, quantity=5-10, feedback_density=0.8 |
| **INQUIRY** | CA Stage 6 Exploration | difficulty=0.7, quantity=1, scaffolding=0.2 |
| **FEEDBACK** | CLT 反馈密度 + CA Stage 2 | difficulty=NA, quantity=1, feedback_density=1.0 |
| **METACOGNITIVE** | CA Stage 4-5 + Bjork 测试 | difficulty=NA, quantity=1, scaffolding=0.5 |

### 2.3 Bloom 目标选择

```python
# ecos/lca/intervention.py
def select_bloom_target(
    belief_state: 'BeliefState',
    bloom_target_candidates: List[BloomLevel],
    learning_dna: 'LearningDNAState',
) -> BloomLevel:
    """
    基于 CTA 状态选择目标 Bloom 层

    算法：
    1. 优先选 CTA 候选中"提升空间最大"的层
    2. 但不超过学生当前能力（BKT P(L) ≥ 0.5 才能挑战）
    3. 考虑 LearningDNA（如视觉型偏好 Apply 层）
    """
    best_target = None
    best_score = -float('inf')

    for layer in bloom_target_candidates:
        # 当前 BloomProfile 掌握度
        current_mastery = getattr(belief_state.bloom_profile, layer.name.lower(), 0)
        # 提升空间 = 1 - current_mastery
        gain_potential = 1.0 - current_mastery
        # BKT 支持度
        bkt_support = belief_state.K.mastery_prob if layer.value >= 3 else 1.0
        # 综合评分
        score = gain_potential * bkt_support
        if score > best_score:
            best_score = score
            best_target = layer

    return best_target
```

---

## 3. L3 干预类型选择层

### 3.1 CLT 4 级自适应呈现

[v0.4.0 §1.2 与 ECOS LCA 的对接](../../30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md)：

```python
# ecos/lca/l3_selection/clt/adaptive_4level.py
from enum import Enum
from typing import Dict, List
import numpy as np

class AdaptiveCLTPresender:
    """
    CLT 4 级自适应呈现——expertise reversal effect 自动化

    规则：
    - 连续 3 道错 → 升级 CLT 级别（提供更多 scaffolding）
    - 连续 5 道对 → 降级 CLT 级别（撤走 worked example）
    """

    def __init__(self, config: CLTConfig):
        self.config = config
        # 学生级别的 CLT level（持久化）
        self.student_clt_level: Dict[str, CLTLevel] = {}

    def determine_level(
        self,
        student_id: str,
        belief_state: 'BeliefState',
    ) -> CLTLevel:
        """基于学生状态确定 CLT 4 级呈现级别"""
        # 1. 默认级别（基于 BloomProfile）
        bloom = belief_state.bloom_profile
        if bloom.dominant_layer.value <= 2:  # L1-L2 (Remember/Understand)
            default_level = CLTLevel.NOVICE
        elif bloom.dominant_layer.value <= 4:  # L3-L4 (Apply/Analyze)
            default_level = CLTLevel.DEVELOPING
        else:
            default_level = CLTLevel.PROFICIENT

        # 2. 调整（基于历史表现）
        history = belief_state.trajectory.snapshots
        if len(history) >= self.config.consecutive_threshold:
            recent_correct_rate = self._compute_recent_correct_rate(history)
            if recent_correct_rate < self.config.low_threshold:
                # 表现差 → 升级（提供更多 support）
                default_level = self._upgrade(default_level)
            elif recent_correct_rate > self.config.high_threshold:
                # 表现好 → 降级（撤走 support）
                default_level = self._downgrade(default_level)

        # 3. 检查 TC 状态（Liminal 状态需要更多 support）
        if any(tc.status == "liminal" for tc in belief_state.C.tc_states.values()):
            default_level = self._upgrade(default_level)

        self.student_clt_level[student_id] = default_level
        return default_level

    def generate_presentation(
        self,
        intervention_type: InterventionType,
        clt_level: CLTLevel,
        problem: 'ProblemMetadata',
    ) -> Dict[str, Any]:
        """生成 CLT 4 级呈现参数"""
        template = self._load_template(intervention_type, clt_level)
        return template.generate(problem)
```

### 3.2 CLT 4 级题目模板

```python
# ecos/lca/l3_selection/clt/templates.py
class CLTTemplate:
    """CLT 4 级题目模板"""

    def __init__(self, level: CLTLevel, intervention_type: InterventionType):
        self.level = level
        self.intervention_type = intervention_type

    def generate(self, problem: 'ProblemMetadata') -> Dict[str, Any]:
        """生成具体呈现"""
        if self.level == CLTLevel.NOVICE and self.intervention_type == InterventionType.EXPLANATORY:
            # 新手 + 讲解型：完整 worked example
            return {
                'show_worked_example': True,
                'worked_example_steps': 'complete',  # 完整步骤
                'show_explanation': True,
                'explanation_length': 'detailed',
                'scaffolding': 0.9,
                'hints_available': 3,
                'feedback_timing': 'immediate',
            }
        elif self.level == CLTLevel.DEVELOPING and self.intervention_type == InterventionType.EXPLANATORY:
            # 进阶 + 讲解型：worked example + 填空
            return {
                'show_worked_example': True,
                'worked_example_steps': 'partial',  # 部分填空
                'fill_in_blanks': ['step_2', 'step_4'],
                'explanation_length': 'moderate',
                'scaffolding': 0.6,
                'hints_available': 2,
            }
        elif self.level == CLTLevel.PROFICIENT:
            # 熟练：独立解题 + 即时反馈
            return {
                'show_worked_example': False,
                'scaffolding': 0.3,
                'hints_available': 1,
                'feedback_timing': 'immediate',
            }
        else:  # EXPERT
            # 专家：独立解题 + 延迟反馈
            return {
                'show_worked_example': False,
                'scaffolding': 0.1,
                'hints_available': 0,
                'feedback_timing': 'delayed',
                'feedback_delay_sec': 300,  # 5 分钟延迟
            }
```

### 3.3 Bjork 测试效应

[v0.4.0 §2.1 Testing Effect](../../30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md)：

```python
# ecos/lca/l3_selection/bjork/testing.py
from fsrs import FSRS, Card, Rating
from datetime import datetime, timedelta

class BjorkTestingEffect:
    """
    Bjork 测试效应——主动提取 > 被动重读

    触发规则：
    - 当 CTA 估计 P(L) > 0.7 但学生未做测验 → 插入测试
    - 测试形式不限于做题：自我解释、Teach-back、自由回忆
    - 测试 + 立即反馈 = 黄金组合
    """

    def __init__(self, fsrs: FSRS):
        self.fsrs = fsrs

    def should_insert_test(
        self,
        belief_state: 'BeliefState',
        last_test_time: Optional[datetime],
    ) -> bool:
        """判断是否应插入测试"""
        # 规则 1：P(L) > 0.7 + 最近 5 题未做测试 → 触发
        if belief_state.K.mastery_prob > 0.7:
            if last_test_time is None or (datetime.now() - last_test_time) > timedelta(days=1):
                return True

        # 规则 2：BKT P(L) 连续 5 次未更新（学生最近都在做练习未测试）→ 触发
        # （从 trajectory 推断）

        return False

    def schedule_next_test(
        self,
        skill_id: str,
        current_p: float,
    ) -> datetime:
        """基于 FSRS 算法计算下次测试时间"""
        card = Card(stability=current_p, difficulty=0.5)
        rating = Rating.Good if current_p > 0.7 else Rating.Hard
        return self.fsrs.next_review(card, rating)
```

### 3.4 Bjork 间隔效应（v0.4.0 §2.3）

```python
# ecos/lca/l3_selection/bjork/spacing.py
class BjorkSpacingEffect:
    """
    Bjork 间隔效应——分散复习 > 集中练习

    与 [CTA L1 间隔衰减](../01-cta-belief-engine.md#43-间隔效应衰减v040-整合) 整合
    """

    def __init__(self, fsrs: FSRS):
        self.fsrs = fsrs

    def get_review_schedule(
        self,
        skill_id: str,
        current_mastery: float,
        last_review_date: Optional[datetime],
    ) -> Dict[str, datetime]:
        """
        计算复习时间表

        基于 Cepeda 2006 经典曲线：
        - 1 周后测试：最优间隔 1-2 天
        - 1 年后测试：最优间隔 25-30 天
        """
        # FSRS 根据稳定性计算下次复习时间
        next_review = self.schedule_next_test(skill_id, current_mastery)
        # 长期复习（30 天后）
        long_term_review = next_review + timedelta(days=30)

        return {
            'next_short_review': next_review,
            'next_long_review': long_term_review,
        }
```

### 3.5 Cognitive Apprenticeship Scaffolding 衰减（v0.4.0 §3.3）

```python
# ecos/lca/l3_selection/ca/scaffolding.py
class CAScaffoldingDecay:
    """
    Cognitive Apprenticeship Scaffolding 衰减

    规则：连续 N 次成功后自动撤走支持（expertise reversal 自动化）
    """

    def __init__(self, config: CAConfig):
        self.config = config

    def update_scaffolding_level(
        self,
        student_id: str,
        current_level: float,
        consecutive_successes: int,
    ) -> float:
        """更新 scaffolding 水平"""
        if consecutive_successes >= self.config.fade_threshold:
            # 连续成功，撤走支持
            new_level = max(
                0.0,
                current_level - self.config.fade_step
            )
            return new_level
        return current_level
```

---

## 4. L4 策略优化层

### 4.1 Cognitive Apprenticeship 6 阶段状态机

[v0.4.0 §3.2 与 ECOS LCA 的对接](../../30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md)：

```python
# ecos/lca/l4_optimization/ca_state_machine.py
class CAStateMachine:
    """
    Cognitive Apprenticeship 6 阶段状态机

    LCA 在后台判断当前阶段（不暴露给 UI）
    """

    def __init__(self):
        self.state: Dict[str, CAStage] = {}  # student_id → CAStage

    def current_stage(self, student_id: str) -> CAStage:
        """获取学生当前 CA 阶段"""
        return self.state.get(student_id, CAStage.MODELING)  # 默认 Modeling

    def transition(
        self,
        student_id: str,
        belief_state: 'BeliefState',
        intervention_history: List['Intervention'],
    ) -> CAStage:
        """根据状态转移 CA 阶段"""
        current = self.current_stage(student_id)

        # 阶段转移规则
        if current == CAStage.MODELING:
            # Modeling → Coaching：学生开始尝试
            if self._has_tried_independently(intervention_history):
                self.state[student_id] = CAStage.COACHING
                return CAStage.COACHING

        elif current == CAStage.COACHING:
            # Coaching → Scaffolding：需要支持
            if self._needs_scaffolding(belief_state):
                self.state[student_id] = CAStage.SCAFFOLDING
                return CAStage.SCAFFOLDING
            # 或 → Articulation：学生讲出思路
            if self._can_articulate(intervention_history):
                self.state[student_id] = CAStage.ARTICULATION
                return CAStage.ARTICULATION

        elif current == CAStage.SCAFFOLDING:
            # Scaffolding → Coaching：支持减少
            if self._scaffolding_reduced(belief_state):
                self.state[student_id] = CAStage.COACHING
                return CAStage.COACHING

        elif current == CAStage.ARTICULATION:
            # Articulation → Reflection：进入对比反思
            if self._reflected_on_difference(intervention_history):
                self.state[student_id] = CAStage.REFLECTION
                return CAStage.REFLECTION

        elif current == CAStage.REFLECTION:
            # Reflection → Exploration：进入独立探究
            if belief_state.bloom_profile.dominant_layer.value >= 4:
                self.state[student_id] = CAStage.EXPLORATION
                return CAStage.EXPLORATION

        return current
```

### 4.2 Contextual Bandits MVP (LinUCB)

[v0.4.0 §6.3 L4 策略优化 + 02-architecture.md §6.3](../../00-overview/02-architecture.md)：

```python
# ecos/lca/l4_optimization/contextual_bandit.py
import numpy as np
from typing import Dict, List, Tuple

class LinUCB:
    """
    Contextual Bandits (LinUCB 算法) — MVP 策略学习

    Context：CTA 5D + BloomProfile + LearningDNA
    Arm：Intervention(type, bloom_target, difficulty, quantity, feedback_density, scaffolding_level)
    Reward：state_delta（CTA 测量的状态变化）

    算法：LinUCB（Li et al., 2010）
    - 每个 arm a 维护参数 θ_a
    - 选择 arm：argmax_a (θ_a^T x + α √(x^T A_a^{-1} x))
    - 探索-利用平衡：α 控制
    """

    def __init__(self, n_arms: int, context_dim: int, alpha: float = 1.0):
        self.n_arms = n_arms
        self.context_dim = context_dim
        self.alpha = alpha
        # 每个 arm 的协方差矩阵 + 参数
        self.A = [np.eye(context_dim) for _ in range(n_arms)]
        self.b = [np.zeros(context_dim) for _ in range(n_arms)]

    def select_arm(self, context: np.ndarray) -> int:
        """LinUCB 选择 arm"""
        ucb_values = np.zeros(self.n_arms)
        for arm in range(self.n_arms):
            A_inv = np.linalg.inv(self.A[arm])
            theta = A_inv @ self.b[arm]
            # 期望奖励
            expected_reward = theta @ context
            # 不确定性奖励（探索）
            confidence_bound = self.alpha * np.sqrt(context @ A_inv @ context)
            ucb_values[arm] = expected_reward + confidence_bound

        return int(np.argmax(ucb_values))

    def update(self, arm: int, context: np.ndarray, reward: float):
        """更新选中的 arm"""
        self.A[arm] += np.outer(context, context)
        self.b[arm] += reward * context

class LCAPolicyLearner:
    """LCA 策略学习器——LinUCB 包装"""

    def __init__(self, config: BanditConfig):
        # 上下文维度：CTA 5D (5) + BloomProfile (6) + LearningDNA (5) = 16
        context_dim = 5 + 6 + 5
        # Arm 数量：5 类型 × 6 Bloom × 4 CLT × 6 CA = 720（但实际采样受限于学生数）
        n_arms = config.n_arms
        self.bandit = LinUCB(n_arms, context_dim, alpha=config.alpha)

    def select_intervention(
        self,
        belief_state: 'BeliefState',
        candidate_interventions: List[Intervention],
    ) -> Intervention:
        """基于 LinUCB 选择最佳干预"""
        # 构造 context
        context = self._build_context(belief_state)
        # 选择 arm
        arm = self.bandit.select_arm(context)
        # 映射到 Intervention
        return candidate_interventions[arm]

    def _build_context(self, belief_state: 'BeliefState') -> np.ndarray:
        """构造 LinUCB context 向量"""
        return np.concatenate([
            [belief_state.K.theta, belief_state.P.theta, belief_state.S.theta,
             belief_state.C.theta, belief_state.X.theta],
            [belief_state.bloom_profile.remember, belief_state.bloom_profile.understand,
             belief_state.bloom_profile.apply, belief_state.bloom_profile.analyze,
             belief_state.bloom_profile.evaluate, belief_state.bloom_profile.create],
            [1.0 if belief_state.learning_dna.input_preference == 'visual' else 0.0,
             1.0 if belief_state.learning_dna.input_preference == 'auditory' else 0.0,
             1.0 if belief_state.learning_dna.input_preference == 'kinesthetic' else 0.0,
             belief_state.learning_dna.feedback_preference == 'immediate',
             belief_state.learning_dna.motivation_pattern.get('weekday', 0.5)],
        ])

    def update(
        self,
        intervention: Intervention,
        belief_state: 'BeliefState',
        state_delta: float,
    ):
        """基于干预效果更新策略"""
        context = self._build_context(belief_state)
        arm = self._intervention_to_arm(intervention)
        self.bandit.update(arm, context, state_delta)
```

### 4.3 POMCP（Phase 5+，MVP 不实现）

[v0.4.0 §6.3 L4 策略优化 Phase 5+](../../30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md)：

```python
# Phase 5+ 实现
class POMCP:
    """
    POMCP（POMDP 的 MCTS 求解）— Phase 5+ 完整 RL 框架

    相比 LinUCB 优势：
    - 处理延迟奖励（学生学习是长期过程）
    - 处理非平稳环境（学生状态持续演化）
    - 处理不确定状态（CTA 信念分布而非事实）
    """
    pass
```

### 4.4 因果归因（与 CTA L4 协作）

[v0.3.0 §5.3 MVP 因果归因](../../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md)：

```python
# ecos/lca/l4_optimization/attribution.py
class LCAAttribution:
    """
    LCA 因果归因——与 CTA L4 协作

    LCA 提供干预记录，CTA L4 计算 ATE
    """

    def __init__(self, cta_l4: 'ABTestAttributor'):
        self.cta_l4 = cta_l4

    def record_intervention(
        self,
        intervention: Intervention,
        student_id: str,
    ):
        """记录干预"""
        # 推到 CTA L4
        self.cta_l4.record_intervention(intervention, student_id)

    def attribute_effect(
        self,
        intervention: Intervention,
        student_id: str,
        state_delta: float,
    ) -> 'CausalEffect':
        """归因干预的因果效果"""
        # 调用 CTA L4
        return self.cta_l4.attribute(
            intervention_type=intervention.intervention_type.value,
            student_id=student_id,
            state_delta=state_delta,
            is_control=False,
        )
```

---

## 5. 可解释性输出（rationale）

[v0.4.0 §6 可解释性 + 04-risks.md §A3 缓解策略](../00-overview/04-risks.md)：

### 5.1 rationale 生成器

```python
# ecos/lca/rationale/generator.py
class RationaleGenerator:
    """
    LCA rationale 生成器——LLM 表达层（不污染教学法决策）

    每个干预附带自然语言理由（"你在二次函数的'分情况讨论'较弱，先做 3 道"）
    """

    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.templates = self._load_templates()

    def generate(
        self,
        intervention: Intervention,
        belief_state: 'BeliefState',
        audience: str = "student",
    ) -> str:
        """生成干预理由"""
        template = self.templates[audience]
        prompt = template.format(
            intervention_type=intervention.intervention_type.value,
            bloom_target=intervention.bloom_target.name,
            target_skills=intervention.target_skills,
            target_misconceptions=intervention.target_misconceptions,
            k_mastery=belief_state.K.theta,
            p_mastery=belief_state.P.theta,
            s_strategy=belief_state.S.theta,
            c_confidence=belief_state.C.theta,
            bloom_profile=belief_state.bloom_profile,
            clt_level=intervention.clt_level.name,
            ca_stage=intervention.ca_stage.name,
        )
        return self.llm_client.generate(prompt, temperature=0.3)
```

### 5.2 Prompt 模板

```python
# ecos/lca/rationale/prompt_templates.py
RATIONALE_TEMPLATES = {
    "student": """
你是友好的 AI 学习教练。请向学生解释推荐：

干预类型：{intervention_type}
目标 Bloom 层：{bloom_target}
目标技能：{target_skills}
目标修正 misconception：{target_misconceptions}

学生当前状态：
- 知识（K）：{k_mastery}
- 程序（P）：{p_mastery}
- 策略（S）：{s_strategy}
- 置信度（C）：{c_confidence}
- Bloom 层级：{bloom_profile}
- CLT 呈现级别：{clt_level}
- CA 阶段：{ca_stage}

请生成 100 字以内的解释（学生能理解的语言）：
""",

    "teacher": """
你是教学顾问。请向教师解释 LCA 推荐：

干预类型：{intervention_type}
目标 Bloom 层：{bloom_target}
目标技能/知识点：{target_skills}
目标修正 misconception：{target_misconceptions}
目标跨越 TC：{target_tcs}

学生状态：
- K/P/S/C/X 5D：{k_mastery}, {p_mastery}, {s_strategy}, {c_confidence}
- BloomProfile：{bloom_profile}
- TC 状态：liminal/post-liminal

请生成 200 字以内的解释（教师视角），包含：
1. 为什么推荐这个干预（基于 CTA 状态）
2. 期望的学习效果
3. 教师可观察的学生行为变化
""",

    "parent": """
你是教育顾问。请向家长解释 LCA 推荐：

干预类型：{intervention_type}
目标技能：{target_skills}
学生当前学习画像：{bloom_profile}

请生成 150 字以内的解释（家长能理解的语言）：
1. 孩子目前的学习状态
2. 这个练习/讲解的目的
3. 家长可以如何支持（避免直接干预）
""",
}
```

### 5.3 教师后台接口

```python
# ecos/lca/rationale/__init__.py
class TeacherBackend:
    """
    教师后台接口——LCA 推荐的可追溯

    教师可查看：
    - 每个学生的干预历史
    - 每个干预的 CTA 状态 + rationale + 期望效果 vs 实际效果
    - 班级整体干预模式（按知识点 / 按 Bloom 层）
    """

    def get_student_intervention_history(
        self,
        student_id: str,
        time_range: Tuple[datetime, datetime],
    ) -> List[Dict[str, Any]]:
        """获取学生干预历史"""
        # 从 persistence 层查询
        # 返回格式：[{timestamp, intervention, rationale, state_delta, causal_effect}, ...]
        pass

    def get_class_intervention_pattern(
        self,
        class_id: str,
        time_range: Tuple[datetime, datetime],
    ) -> Dict[str, Any]:
        """获取班级整体干预模式"""
        # 聚合统计：最常用的干预类型、最常见的 misconception、整体 BloomProfile 演化
        pass
```

---

## 6. LCA 主流程编排

```python
# ecos/lca/orchestrator.py
class LCAOrchestrator:
    """LCA 主流程编排——L3-L4 教学法栈 + Contextual Bandits"""

    def __init__(self, config: LCAConfig):
        # L3 组件
        self.clt = AdaptiveCLTPresender(config.clt)
        self.bjork_testing = BjorkTestingEffect(config.fsrs)
        self.bjork_spacing = BjorkSpacingEffect(config.fsrs)
        self.ca_scaffolding = CAScaffoldingDecay(config.ca)
        # L4 组件
        self.ca_state_machine = CAStateMachine()
        self.bandit = LCAPolicyLearner(config.bandit)
        self.attribution = LCAAttribution(config.cta_l4)
        # Rationale
        self.rationale_gen = RationaleGenerator(config.llm)
        # 当前干预历史
        self.intervention_history: Dict[str, List[Intervention]] = {}

    def select_intervention(self, cta_input: CTAInput) -> LCAResult:
        """主选择流程——基于 CTA 状态选择干预"""
        # Step 1: 选 Bloom 目标层
        bloom_target = select_bloom_target(
            cta_input.belief_state,
            cta_input.bloom_target_candidates,
            cta_input.belief_state.learning_dna,
        )

        # Step 2: 确定 CA 阶段
        history = self.intervention_history.get(cta_input.student_id, [])
        ca_stage = self.ca_state_machine.transition(
            cta_input.student_id, cta_input.belief_state, history
        )

        # Step 3: 确定 CLT 4 级呈现
        clt_level = self.clt.determine_level(
            cta_input.student_id, cta_input.belief_state
        )

        # Step 4: 检查 Bjork 触发条件
        bjork_triggers = []
        if self.bjork_testing.should_insert_test(
            cta_input.belief_state, self._last_test_time(cta_input.student_id)
        ):
            bjork_triggers.append("test")
        if self._should_review(cta_input.belief_state):
            bjork_triggers.append("space")

        # Step 5: L4 Contextual Bandit 选择候选干预
        candidates = self._generate_candidates(
            bloom_target, clt_level, ca_stage, bjork_triggers, cta_input
        )
        intervention = self.bandit.select_intervention(
            cta_input.belief_state, candidates
        )

        # Step 6: 生成 rationale
        rationale = self.rationale_gen.generate(
            intervention, cta_input.belief_state, audience="student"
        )

        # Step 7: 记录干预
        self.intervention_history.setdefault(
            cta_input.student_id, []
        ).append(intervention)
        self.attribution.record_intervention(intervention, cta_input.student_id)

        # Step 8: 输出 LCAResult
        return LCAResult(
            student_id=cta_input.student_id,
            intervention=intervention,
            rationale=rationale,
            expected_gain=self._estimate_gain(intervention, cta_input.belief_state),
            expected_risk=self._estimate_risk(intervention, cta_input.belief_state),
            bloom_target=bloom_target,
            timestamp=datetime.now(),
        )

    def update(
        self,
        student_id: str,
        intervention: Intervention,
        new_state: 'BeliefState',
        state_delta: float,
    ):
        """基于干预效果更新策略"""
        # 因果归因
        causal_effect = self.attribution.attribute_effect(
            intervention, student_id, state_delta
        )
        # 更新 LinUCB 策略
        self.bandit.update(
            intervention=intervention,
            belief_state=new_state,
            state_delta=state_delta,
        )
```

---

## 7. 测试策略

### 7.1 单元测试（覆盖率 ≥ 75%）

| 模块 | 测试重点 | 覆盖率目标 |
|---|---|---|
| `l3_selection/clt/adaptive_4level.py` | CLT 4 级判断正确性、升级/降级规则 | ≥ 85% |
| `l3_selection/clt/templates.py` | 4 套题目模板生成正确性 | ≥ 80% |
| `l3_selection/bjork/testing.py` | 测试效应触发规则、FSRS 集成 | ≥ 85% |
| `l3_selection/bjork/spacing.py` | 间隔效应时间表生成 | ≥ 80% |
| `l3_selection/ca/scaffolding.py` | Scaffolding 衰减规则 | ≥ 90% |
| `l4_optimization/ca_state_machine.py` | 6 阶段转移规则 | ≥ 85% |
| `l4_optimization/contextual_bandit.py` | LinUCB 选 arm 算法、update 正确性 | ≥ 90% |
| `rationale/generator.py` | LLM rationale 生成 + prompt 模板 | ≥ 70% |

### 7.2 集成测试

```python
# ecos/lca/tests/test_integration.py
def test_full_lca_pipeline():
    """完整 LCA 流程测试"""
    lca = LCAOrchestrator(config_for_test())
    cta = CTAOrchestrator(config_for_test())  # 模拟

    # 模拟 100 次学生交互
    for i in range(100):
        # CTA 估计状态
        cta_output = cta.update(observation=...)
        # LCA 选择干预
        lca_result = lca.select_intervention(cta_output)
        # 模拟学生响应
        new_observation = simulate_student_response(lca_result.intervention)
        # CTA 更新（包含 LCA 结果）
        new_cta_output = cta.update(new_observation, lca_result)
        # LCA 更新策略
        lca.update(lca_result.student_id, lca_result.intervention,
                   new_cta_output.belief_state, state_delta=...)

    # 验证策略学习
    assert lca.bandit.bandit.A[0].any()  # 至少有一个 arm 被采样过
```

### 7.3 评估指标（对照 04-risks.md §A3 + §C2 风险阈值）

| 指标 | 阈值 | 测试场景 |
|---|---|---|
| **教师 rationale 满意度** | ≥ 4/5 | 教师问卷 |
| **家长接受率** | ≥ 70% | 家长问卷 |
| **学生干预接受率** | ≥ 60% | 行为日志 |
| **LinUCB 收敛** | ≤ 50 次交互 | 模拟实验 |
| **rationale 生成延迟** | P95 ≤ 3 秒 | 性能测试 |
| **可解释性 vs 性能权衡** | 性能损失 ≤ 10% | A/B 实验 |

---

## 8. MVP 范围（Phase 4）

### 8.1 MVP 包含的组件

| 组件 | 实现状态 |
|---|---|
| L3 CLT 4 级自适应呈现 | ✅ MVP |
| L3 Bjork 测试效应 + 间隔效应 | ✅ MVP |
| L3 Bjork 合意困难 + 交错练习 | ❌ Phase 5+ |
| L3 CA Scaffolding 衰减 | ✅ MVP |
| L4 CA 6 阶段状态机（Stage 1-3）| ✅ MVP |
| L4 CA 6 阶段（Stage 4-6）| ❌ Phase 5+ |
| L4 Contextual Bandits (LinUCB) | ✅ MVP |
| L4 POMCP | ❌ Phase 5+ |
| L4 因果归因（与 CTA L4 协作）| ✅ MVP |
| Rationale 生成（学生/教师/家长）| ✅ MVP |
| 教师后台接口 | ✅ MVP |

### 8.2 MVP 不包含的组件

- ❌ Bjork 合意困难 + 交错练习（Phase 5+）
- ❌ CA Stage 4-6（Articulation + Reflection + Exploration，Phase 5+）
- ❌ POMCP（完整 RL 框架，Phase 5+）
- ❌ 跨学科策略空间
- ❌ 教师级深度个性化

### 8.3 MVP 数据流

```
CTA → CTAOutput → LCAOrchestrator.select_intervention()
                       ↓
                  L3 组件（CLT + Bjork + CA）
                       ↓
                  L4 Contextual Bandits（LinUCB）
                       ↓
                  Intervention + Rationale
                       ↓
                  App 层执行
                       ↓
                  学生响应 → CTA 更新（带 LCA 结果）
                       ↓
                  LCA 更新策略（LinUCB.update）
```

---

## 9. 关联文档

- **同级工程层**：
  - [01-cta-belief-engine.md](01-cta-belief-engine.md) — CTA 信念引擎（LCA 的上游）
  - [03-bloom-goal-library.md](03-bloom-goal-library.md) — Bloom 目标库（LCA 的目标坐标系）
  - [04-dual-agent-calibration.md](04-dual-agent-calibration.md) — 双 Agent 互校（CTA ↔ LCA 接口契约）
  - [05-persistence-session.md](05-persistence-session.md) — 持久化（干预历史存储）
- **P0 借鉴**（理论依据）：
  - [v0.4.0 LCA 教学法基础](../../30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md) — 3 大理论群（CLT + Bjork + CA）
  - [v0.3.0 CTA 数学基础 §4 POMDP](../../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md) — POMDP 接口（LCA 决策空间）
- **上层文档**：
  - [02-architecture.md §6 干预策略工程实现](../00-overview/02-architecture.md) — 本文档的架构依据
  - [03-roadmap.md §2.2 M2 里程碑](../00-overview/03-roadmap.md) — W1-W6 工程任务
  - [04-risks.md §A3 LCA 可解释性 + §C2 文化适配](../00-overview/04-risks.md) — 风险缓解策略
- **核心论证**：
  - [v2.0 §3.4 LCA 设计](../../research/deep-research/Cognitive-Digital-Twin-Deep-Research.md) — LCA 思维模式 + 5 类干预

---

## 10. 版本与维护

- **v1.0**（2026-06-25）— 初版

**待办（影响本文档时同步更新）**：
- 当 [04-dual-agent-calibration.md](04-dual-agent-calibration.md) 完成后，回填 §5.3 教师后台接口的"互校可见"部分
- 当 Phase 4 MVP 实验完成后，回填 §7.3 实际评估指标 vs 阈值

---

**创建日期**：2026-06-25
**维护者**：Bisen & Claude
