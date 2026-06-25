# CTA 信念状态估计引擎（CTA Belief Engine）

> **版本**：v1.0（2026-06-25）
> **性质**：工程层第 1 份文档——CTA（Cognitive Twin Agent）信念引擎的工程实现设计
> **基于**：[v0.3.0 CTA 数学基础](../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md)（5 层数学栈）、[v0.5.0 C 维度内容库](../30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md)（TC + Misconceptions）、[02-architecture.md §5 状态估计工程实现](../00-overview/02-architecture.md)、[03-roadmap.md §2 M2 里程碑](../00-overview/03-roadmap.md)、[04-risks.md §A 技术风险](../00-overview/04-risks.md)
> **后续**：[02-lca-policy-engine.md](02-lca-policy-engine.md)、[03-bloom-goal-library.md](03-bloom-goal-library.md)、[04-dual-agent-calibration.md](04-dual-agent-calibration.md)、[05-persistence-session.md](05-persistence-session.md)
> **维护者**：Bisen & Claude

---

## 0. 模块定位

### 0.1 核心职责

**CTA 信念引擎**是 ECOS 双 Agent 架构中的"理解学生"组件。核心职责：

1. **维护学生认知状态的信念分布**——不是事实判断（如"学生 K 弱"），而是带置信度的概率分布（如"K 弱概率 0.6，置信度 0.8"）
2. **基于心理测量学方法做状态估计**——贝叶斯 / IRT / BKT / DKT 等科学方法，**不是 LLM 直觉**
3. **输出每个状态变量的 confidence 和 evidence**——可解释、可追溯、可校准

**关键边界**（v0.3.0 + v0.4.0 确立的硬底线）：
- ✅ 数学层（L0-L2）使用统计方法
- ✅ LLM 仅在感知层（自然语言→结构化）+ 解释层（统计值→自然语言）+ Misconception 检测
- ❌ **LLM 不可用于直接生成 5D 状态估计**

### 0.2 与其他模块的接口

```
┌────────────────────────────────────────────────────────────┐
│ App 层（数据采集）                                           │
│   ↓ observation（结构化观测）                                │
│ CTA Belief Engine（本模块）                                 │
│   ↓ b(s) 信念分布 + BloomProfile + TC 状态                  │
│ LCA Policy Engine（[02-lca-policy-engine.md](02-lca-policy-engine.md)）│
│   ↑ π(a|s) 干预策略                                         │
│   ↓ causal_effect 干预效果                                  │
│ CTA Belief Engine（互校反馈，更新信念）                      │
│   ↓ state_delta                                             │
│ Persistence Layer（[05-persistence-session.md](05-persistence-session.md)）│
└────────────────────────────────────────────────────────────┘
```

### 0.3 文档目标读者

- **工程实现者**：按本文档实现 `ecos/cta/` Python 模块
- **算法研究人员**：理解 L0-L4 数学栈的算法选择与实现
- **测试人员**：理解测试策略与评估指标

---

## 1. 整体架构

### 1.1 5 层数学栈的工程映射

[v0.3.0 CTA 数学基础 §6 整合](../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md) 给出完整 5 层数学栈：

| 层 | 学术方法 | 工程实现 | 开源依赖 | 文件位置 |
|---|---|---|---|---|
| **L0 概率框架** | POMDP / HMM | 扩展卡尔曼滤波（EKF）+ 离散属性精确推断 | `pgmpy`, `pykalman`, `filterpy` | `ecos/cta/l0_pomdp/` |
| **L1 时间演化** | BKT / DKT | 经典 4 参数 BKT（MVP）+ FSRS 间隔效应 | `pyBKT`, `ts-fsrs` | `ecos/cta/l1_evolution/` |
| **L2 状态估计** | MIRT | Bi-factor 非补偿 MIRT | `mirt` (R, rpy2) / 自研 | `ecos/cta/l2_mirt/` |
| **L3 自适应选择** | CD-CAT | GDINA + PWKL 选题 | `GDINA` (R, rpy2) / 自研 | `ecos/cta/l3_cdcat/` |
| **L4 因果归因** | Causal Inference | MVP: 单变量 A/B + T-test；Phase 5+: Causal Forest | `DoWhy`, `scipy.stats` | `ecos/cta/l4_causal/` |
| **L0.5 内容库**（v0.5.0 新增）| TC + Misconceptions | JSON 库 + LLM Critic | 自研 + `pgmpy` | `ecos/cta/content/` |

### 1.2 模块目录结构

```
ecos/cta/
├── __init__.py
├── belief_state.py            # BeliefState 数据结构 + 5D 状态空间
├── observation.py             # 结构化观测数据结构
├── l0_pomdp/
│   ├── __init__.py
│   ├── pomdp.py               # POMDP 框架
│   ├── belief_updater.py      # 信念更新（EKF + 离散精确推断）
│   └── pomcp.py               # POMCP 求解（Phase 5+）
├── l1_evolution/
│   ├── __init__.py
│   ├── bkt.py                 # 经典 4 参数 BKT
│   ├── dkt.py                 # DKT（Phase 5+，MVP 不实现）
│   ├── spaced_repetition.py   # 间隔效应衰减（FSRS 算法）
│   └── transition.py          # 学习/遗忘转移概率
├── l2_mirt/
│   ├── __init__.py
│   ├── mirt_5d.py             # 5D 非补偿 Bi-factor MIRT
│   ├── covariance.py          # 协方差结构学习
│   └── calibration.py         # 参数校准（EM 算法）
├── l3_cdcat/
│   ├── __init__.py
│   ├── gdina.py               # GDINA 模型
│   ├── q_matrix.py            # Q 矩阵（含 TC + Misconception 标注）
│   ├── pwkl_selector.py       # PWKL 选题
│   └── stop_rule.py           # 停止规则
├── l4_causal/
│   ├── __init__.py
│   ├── ab_test.py             # MVP: 单变量 A/B + T-test
│   ├── causal_forest.py       # Phase 5+: Causal Forest
│   └── attribution.py         # 干预效果归因
├── content/
│   ├── __init__.py
│   ├── threshold_concepts.py  # TC 库（8 个 MVP）
│   ├── misconceptions.py      # Misconceptions 库（30-50 条 MVP）
│   ├── tc_detector.py         # TC 跨越检测（liminal/post-liminal）
│   └── misc_detector.py       # Misconception 检测（LLM Critic）
├── llm_critic/
│   ├── __init__.py
│   ├── perception.py          # 感知层（自然语言→结构化）
│   ├── explanation.py         # 解释层（统计值→自然语言）
│   └── critic_prompts.py      # LLM Critic 提示词库
├── orchestrator.py            # CTA 主流程编排（5 层 + 内容库 + LLM 集成）
└── tests/
    ├── test_bkt.py            # BKT 单元测试
    ├── test_mirt.py           # MIRT 单元测试
    ├── test_cdcat.py          # CD-CAT 单元测试
    ├── test_content.py        # TC + Misconception 测试
    └── test_integration.py    # 集成测试
```

### 1.3 与 LCA / Persistence 的接口契约

**CTA → LCA 接口**：

```python
# CTA 输出（被 LCA 消费）
@dataclass
class CTAOutput:
    student_id: str
    belief_state: BeliefState           # 5D + BloomProfile + Trajectory
    bloom_target_candidates: List[BloomLevel]  # LCA 选目标层
    intervention_hints: Dict[str, Any]   # 干预提示（如"分情况讨论子缺口"）
    confidence: float                   # 整体置信度
    timestamp: datetime
```

**LCA → CTA 接口**（互校反馈）：

```python
# LCA 输出（被 CTA 消费，用于信念更新）
@dataclass
class LCAResult:
    intervention_type: str
    intervention_params: Dict[str, Any]
    expected_gain: float
    actual_outcome: Optional[float]      # 干预后观察到的效果（None 表示待观察）
    causal_effect: Optional[float]       # L4 因果归因结果
    timestamp: datetime
```

---

## 2. BeliefState 数据结构

### 2.1 5D + BloomProfile 完整结构

[v2.0 §3.3](../deep-research/Cognitive-Digital-Twin-Deep-Research.md) 已给出 9D 结构。本模块基于 v0.3.0 + v0.5.0 扩展为完整工程结构：

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import numpy as np

class BloomLevel(Enum):
    REMEMBER = 1
    UNDERSTAND = 2
    APPLY = 3
    ANALYZE = 4
    EVALUATE = 5
    CREATE = 6

@dataclass
class DimensionState:
    """单个维度的状态（含分布与置信度）"""
    # 连续值（MIRT θ ∈ ℝ）
    theta: float                          # 能力估计
    se: float                             # 标准误
    # 离散化（CD-CAT 属性 α ∈ {0,1}）
    mastered: bool                        # 二值掌握判定
    mastery_prob: float                   # 掌握概率
    # 元数据
    confidence: float                     # 0-1，CTA 对该维度估计的置信度
    evidence_ids: List[int]               # 支撑证据 ID（关联 evidence_log）
    last_updated: datetime
    # 5 维中的位置
    dimension: str                        # 'K' / 'P' / 'S' / 'C' / 'X'

@dataclass
class BloomProfileState:
    """BloomProfile（6 层认知层级分布）"""
    # 6 层分别掌握概率
    remember: float                       # L1
    understand: float                     # L2
    apply: float                          # L3
    analyze: float                        # L4
    evaluate: float                       # L5
    create: float                         # L6
    # 主层（掌握概率最高的层）
    dominant_layer: BloomLevel
    # 元数据
    confidence: float                     # 0-1
    evidence_ids: List[int]

@dataclass
class LearningDNAState:
    """学习者个性化特征（5 维）"""
    input_preference: str                 # 'visual' / 'auditory' / 'kinesthetic'
    feedback_preference: str              # 'immediate' / 'delayed'
    fatigue_pattern: Dict[str, float]     # 时段-疲劳度映射
    error_pattern: List[str]              # 错误模式列表
    motivation_pattern: Dict[str, float]  # 动机强度（按周/天）
    confidence: float

@dataclass
class TrajectoryState:
    """成长轨迹（时间序列）"""
    snapshots: List['StateSnapshot']      # 历史快照（最近 N 次）
    predictions: Dict[str, float]         # 未来预测（如 "4 周后 BloomProfile.apply ≈ 0.85"）

@dataclass
class StateSnapshot:
    """单次状态快照"""
    timestamp: datetime
    theta_5d: np.ndarray                  # 5D 能力向量 [K, P, S, C, X]
    bloom_profile: BloomProfileState
    tc_states: Dict[str, 'TCState']       # TC 状态（v0.5.0）
    misc_history: List[str]               # misconception 历史（v0.5.0）
    confidence: float

@dataclass
class BeliefState:
    """完整 CTA 信念状态"""
    student_id: str
    # 5D 核心状态
    K: DimensionState                     # 知识掌握
    P: DimensionState                     # 程序技能
    S: DimensionState                     # 策略能力
    C: DimensionState                     # 认知置信度（含 misconception 折扣）
    X: DimensionState                     # 外部支架
    # 信念分布
    theta_mean: np.ndarray                # 5D 联合均值 [θ_K, θ_P, θ_S, θ_C, θ_X]
    theta_cov: np.ndarray                 # 5D 联合协方差矩阵（5x5）
    # 第二维坐标
    bloom_profile: BloomProfileState
    # 学习者特征
    learning_dna: LearningDNAState
    # 时间维度
    trajectory: TrajectoryState
    # 整体置信度
    overall_confidence: float
    # 元数据
    last_updated: datetime
    version: str = "v1.0"
```

### 2.2 C 维度特殊处理（v0.5.0 整合）

**C 维度（Confidence / 认知置信度）有特殊的"伪置信"处理**：

```python
@dataclass
class ConfidenceDimensionState(DimensionState):
    """C 维度扩展——含 misconception 折扣与 TC 状态"""
    # 基础 C 维度（同 DimensionState）
    # v0.5.0 扩展
    misconception_hits: List[MisconceptionHit]  # 历史命中记录
    tc_states: Dict[str, 'TCState']             # 每个 TC 的状态
    illusory_confidence_flag: bool              # 伪置信标记
    discount_factor: float                      # misconception 折扣（默认 1.0）

@dataclass
class MisconceptionHit:
    """单次 misconception 命中"""
    misc_id: str                                # e.g. "M1", "M2"
    confidence: float                           # 命中置信度 0-1
    trigger_problem_id: str
    evidence_text: str                          # 学生解释文本
    timestamp: datetime
    correction_strategy: str                    # 修正策略 ID

@dataclass
class TCState:
    """Threshold Concept 状态（v0.5.0 整合）"""
    tc_id: str                                  # e.g. "TC_function"
    status: str                                 # "pre_liminal" / "liminal" / "post_liminal"
    progress: float                             # 0-1，跨越进度
    confidence: float                           # CTA 对状态的置信度
    liminal_signals: List[str]                  # 触发 liminal 状态的信号
    post_liminal_jump_detected: bool            # 是否检测到质变
    irreversible: bool                          # TC 不可逆性
    timestamp: datetime
```

### 2.3 信念更新的统一接口

```python
class BeliefEngine:
    """CTA 信念引擎主类"""

    def update(self, observation: Observation, lca_result: Optional[LCAResult] = None) -> BeliefState:
        """
        主更新接口——每次新观测后调用

        Args:
            observation: 结构化观测（App 层采集）
            lca_result: LCA 干预结果（可选，用于因果归因）

        Returns:
            更新后的 BeliefState
        """
        # Step 1: LLM Critic 感知层（自然语言 → 结构化）
        structured_obs = self.llm_critic.perceive(observation)

        # Step 2: L0 POMDP 信念预测
        predicted_belief = self.l0_pomdp.predict(self.current_state, last_action)

        # Step 3: L1 BKT 更新（每个知识点）
        for skill in structured_obs.skills_touched:
            self.l1_evolution.update_bkt(skill, structured_obs)

        # Step 4: L2 MIRT 联合估计
        self.l2_mirt.update(self.current_state, structured_obs)

        # Step 5: C 维度内容库集成（v0.5.0）
        self._update_c_dimension(structured_obs)

        # Step 6: L3 CD-CAT 选下一题
        next_problem = self.l3_cdcat.select_next(...)

        # Step 7: L4 因果归因（如果 LCA 提供结果）
        if lca_result and lca_result.actual_outcome is not None:
            self.l4_causal.attribute(lca_result)

        return self.current_state
```

---

## 3. L0 概率框架层（POMDP / HMM）

### 3.1 学术背景

[v0.3.0 §4 POMDP / HMM](../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md) 给出 POMDP 的完整数学定义：

```
POMDP = (S, A, O, T, R, Ω, γ)
  S - 状态空间（隐藏）
  A - 动作空间
  O - 观测空间（不完整）
  T - 状态转移 T(s'|s, a)
  R - 奖励 R(s, a)
  Ω - 观测概率 Ω(o|s')
  γ - 折扣因子
```

### 3.2 状态空间定义

**CTA 的隐藏状态**（[v0.3.0 §4.2 对接](../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md)）：

| POMDP 元素 | ECOS CTA 对应 |
|---|---|
| **隐藏状态 S** | `(5D 状态, BloomProfile, TC 状态)` 的连续/离散混合空间 |
| **动作 A** | 干预类型（5 类）+ 参数（4 维）|
| **观测 O** | 学生作答、答题时间、解释文本、反思日志 |
| **状态转移 T** | 学习效应 + 遗忘衰减 + 干预影响 |
| **观测概率 Ω** | 学生行为随机性（猜测、失误、注意力波动）|
| **奖励 R** | 状态改善度（P(L) 上升 + BloomProfile 上调）|

### 3.3 工程实现（MVP）

**关键挑战**：连续状态空间维度爆炸（5D + Bloom 6 层 = 11D），必须用因子化或稀疏表示。

**MVP 实现策略**：扩展卡尔曼滤波（EKF） + 离散属性精确推断

```python
# ecos/cta/l0_pomdp/pomdp.py
import numpy as np
from filterpy.kalman import ExtendedKalmanFilter

class CTAPOMDP:
    """
    CTA POMDP 框架——L0 概率框架层

    状态空间：连续 5D（θ ∈ ℝ⁵）+ 离散属性（α ∈ {0,1}ᴬ）
    转移模型：L1 BKT 提供的学习/遗忘转移
    观测模型：L2 MIRT 提供的概率观测
    """

    def __init__(self, config: POMDPConfig):
        self.config = config
        # 连续部分：扩展卡尔曼滤波
        self.ekf = ExtendedKalmanFilter(
            dim_x=5,    # 5D 状态
            dim_z=5,    # 5D 观测
        )
        # 离散部分：精确推断（适用于小属性数 A ≤ 20）
        self.discrete_attrs: Dict[str, DiscreteAttributeState] = {}

    def predict(self, state: BeliefState, last_action: Optional[Action]) -> BeliefState:
        """L0 POMDP 预测步骤"""
        # 连续部分：EKF 预测
        self.ekf.F = self._build_transition_matrix(last_action)  # 5x5
        self.ekf.Q = self._build_process_noise()                  # 5x5
        self.ekf.predict()

        # 离散部分：转移概率预测
        for attr_id, attr_state in self.discrete_attrs.items():
            attr_state.predict(last_action)

        return self._extract_belief_state()

    def update(self, observation: Observation) -> BeliefState:
        """L0 POMDP 更新步骤"""
        # 连续部分：EKF 更新
        z = self._observation_to_vector(observation)  # 5D
        self.ekf.update(z, HJacobian=self._H_jacobian, Hx=self._H_x)

        # 离散部分：贝叶斯更新
        for attr_id, attr_state in self.discrete_attrs.items():
            attr_state.update(observation)

        return self._extract_belief_state()
```

### 3.4 关键算法细节

**转移矩阵 F**（5×5）：
- 对角线元素：各维度的自转移（如 0.95 表示轻微衰减）
- 非对角线：维度间相关性（如 K→P 的学习迁移）
- 来源：从 L1 BKT 学习到的转移概率

**观测矩阵 H**（5×5）：
- 单位阵的扩展（每个维度观测自身）
- 允许 cross-observation（如 X（外部支架）的观测可推测 S（策略能力））

**过程噪声 Q**（5×5）：
- 学习 + 遗忘的不确定性
- 不同维度噪声不同（C 维度最大，K 维度最小）

### 3.5 POMCP 求解（Phase 5+）

完整 POMDP 求解（MVP 不实现）：
- 算法：POMCP（POMDP 的 MCTS 求解）
- 求解目标：给定 belief state b(s)，找到最优动作 a
- 实际用途：LCA 的策略优化（[02-lca-policy-engine.md](02-lca-policy-engine.md)）

**MVP 替代方案**：LCA 使用 Contextual Bandits（[02 §6.3](../00-overview/02-architecture.md)）。

---

## 4. L1 时间演化层（BKT + Spaced Repetition）

### 4.1 BKT 经典 4 参数

[v0.3.0 §3.1 BKT 核心](../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md) 给出 BKT 的完整数学定义：

```
4 个参数：
  P(L₀) - 初始掌握概率（先验）
  P(T)  - 学习转移概率（未掌握→已掌握）
  P(G)  - 猜测概率（未掌握却答对）
  P(S)  - 失误概率（已掌握却答错）

更新规则（每道题）：
  P(L_n | 答对) = P(L_{n-1}) · (1 - P(S)) / [...]
  P(L_n | 答错) = P(L_{n-1}) · P(S) / [...]
  P(L_n) = P(L_{n-1} | 观测) + (1 - P(L_{n-1} | 观测)) · P(T)
```

### 4.2 工程实现

```python
# ecos/cta/l1_evolution/bkt.py
from dataclasses import dataclass
import numpy as np

@dataclass
class BKTParams:
    """BKT 4 参数"""
    p_init: float = 0.1   # P(L₀) 初始掌握概率
    p_learn: float = 0.1  # P(T) 学习转移概率
    p_guess: float = 0.2  # P(G) 猜测概率
    p_slip: float = 0.1   # P(S) 失误概率

    def __post_init__(self):
        assert 0 <= self.p_init <= 1
        assert 0 <= self.p_learn <= 1
        assert 0 <= self.p_guess <= 1
        assert 0 <= self.p_slip <= 1

class BKTModel:
    """单个知识点的 BKT 模型"""

    def __init__(self, skill_id: str, params: BKTParams):
        self.skill_id = skill_id
        self.params = params
        self.p_mastered = params.p_init  # 当前 P(L)

    def update(self, correct: bool) -> float:
        """
        更新 BKT 并返回新的 P(L)

        Args:
            correct: 学生作答是否正确

        Returns:
            新的掌握概率 P(L_n)
        """
        if correct:
            numerator = self.p_mastered * (1 - self.params.p_slip)
            denominator = (self.p_mastered * (1 - self.params.p_slip)
                          + (1 - self.p_mastered) * self.params.p_guess)
        else:
            numerator = self.p_mastered * self.params.p_slip
            denominator = (self.p_mastered * self.params.p_slip
                          + (1 - self.p_mastered) * (1 - self.params.p_guess))

        # 观测更新
        p_after_observation = numerator / denominator if denominator > 0 else self.p_mastered

        # 学习转移
        self.p_mastered = p_after_observation + (1 - p_after_observation) * self.params.p_learn

        return self.p_mastered

class BKTEvolutionLayer:
    """L1 时间演化层——管理所有知识点的 BKT"""

    def __init__(self, config: EvolutionConfig):
        self.config = config
        self.skill_models: Dict[str, BKTModel] = {}

    def update(self, skill_id: str, correct: bool) -> float:
        """更新指定知识点的 BKT"""
        if skill_id not in self.skill_models:
            self.skill_models[skill_id] = BKTModel(
                skill_id, self.config.get_params(skill_id)
            )
        return self.skill_models[skill_id].update(correct)

    def apply_decay(self, skill_id: str, days_since_last: int) -> float:
        """应用间隔效应衰减（v0.4.0 Bjork spacing effect）"""
        model = self.skill_models[skill_id]
        # Ebbinghaus 衰减曲线：P(L) → P(L) · e^(-days/decay_constant)
        decay_constant = self.config.get_decay_constant(skill_id)
        model.p_mastered *= np.exp(-days_since_last / decay_constant)
        return model.p_mastered
```

### 4.3 间隔效应衰减（v0.4.0 整合）

[v0.4.0 §2.3 Spacing Effect](../30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md)：

```python
# ecos/cta/l1_evolution/spaced_repetition.py
from fsrs import FSRS, Card, Rating

class SpacedRepetitionScheduler:
    """基于 FSRS 算法的间隔重复调度"""

    def __init__(self):
        self.fsrs = FSRS()

    def get_next_review_date(self, skill_id: str, current_p: float) -> datetime:
        """
        根据当前掌握度计算下次复习时间

        Args:
            skill_id: 知识点 ID
            current_p: 当前掌握概率

        Returns:
            下次复习的建议时间
        """
        # FSRS 根据稳定性 + 难度计算最优间隔
        card = Card(stability=current_p, difficulty=0.5)
        rating = Rating.Good if current_p > 0.7 else Rating.Hard
        return self.fsrs.next_review(card, rating)
```

### 4.4 DKT / DKVMN（Phase 5+，MVP 不实现）

[v0.3.0 §3.2 DKT 核心](../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md)：

```python
# Phase 5+ 实现
class DKTModel:
    """Deep Knowledge Tracing (Piech et al., 2015)"""
    # 输入：作答序列 (x_1, ..., x_t)
    # 输出：每个知识点的掌握概率 p_t
    # 模型：LSTM
    # 优势：跨知识点关联
    # 劣势：黑箱、可解释性弱
    pass
```

---

## 5. L2 状态估计层（MIRT）

### 5.1 5D 非补偿 MIRT

[v0.3.0 §1 MIRT 核心](../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md)：

```python
# ecos/cta/l2_mirt/mirt_5d.py
import numpy as np
from scipy.optimize import minimize

class BiFactorMIRT5D:
    """
    Bi-factor 5D 非补偿 MIRT

    状态：θ ∈ ℝ⁵ + 一般维度 G ∈ ℝ（Bi-factor 结构）
    题目参数：a_i ∈ ℝ⁵ + a_G_i ∈ ℝ + d_i ∈ ℝ
    """

    def __init__(self):
        # 5 个特化维度 + 1 个一般维度
        self.theta_dim = 6  # 5 + 1
        # 参数预分配
        self.a_specialized: np.ndarray = np.zeros((0, 5))  # 5D 特化区分度
        self.a_general: np.ndarray = np.zeros(0)             # 一般区分度
        self.difficulty: np.ndarray = np.zeros(0)            # 难度
        self.guess: np.ndarray = np.zeros(0)                 # 猜测

    def update(self, responses: np.ndarray, problem_ids: List[str]) -> Tuple[np.ndarray, np.ndarray]:
        """
        EM 算法更新 MIRT 参数 + 学生能力估计

        Args:
            responses: 学生作答矩阵 (n_students × n_problems)
            problem_ids: 题目 ID 列表

        Returns:
            theta_mean: 学生能力均值 (n_students × 5)
            theta_cov: 学生能力协方差 (n_students × 5 × 5)
        """
        # E-step：估计学生能力后验
        theta_posterior = self._e_step(responses)

        # M-step：更新题目参数
        self._m_step(responses, theta_posterior)

        return theta_posterior.mean, theta_posterior.cov
```

### 5.2 协方差结构学习

[v0.3.0 §1.2 关键挑战](../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md)：

```python
# ecos/cta/l2_mirt/covariance.py
class CovarianceLearner:
    """
    5D 协方差结构学习

    关键挑战：不同学科维度相关性不同
    - 数学：K-P 强相关（K 强通常 P 也强）
    - 语文：K-P 弱相关
    """

    def __init__(self, prior_subject: str):
        # 根据学科加载先验协方差
        self.prior_cov = self._load_subject_prior(prior_subject)

    def learn(self, theta_samples: np.ndarray) -> np.ndarray:
        """从学生能力样本学习协方差"""
        # EM 算法 + 正则化（避免奇异矩阵）
        emp_cov = np.cov(theta_samples.T)
        # 加权先验 + 经验协方差
        smoothed_cov = self.alpha * self.prior_cov + (1 - self.alpha) * emp_cov
        # 正定化（避免奇异）
        smoothed_cov = self._ensure_positive_definite(smoothed_cov)
        return smoothed_cov
```

### 5.3 校准与冷启动

[v0.3.0 §1.4 实施注意事项](../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md)：

- **冷启动**：新学生/新学科的 MIRT 参数需要历史数据校准——MVP 用默认先验 + 短期预测试
- **预测试**：每个新学生先做 5-10 道预测试题，初始化 θ
- **Q 矩阵构建**：与教师协作（[03-bloom-goal-library.md](03-bloom-goal-library.md) + 教师标注）

---

## 6. L3 自适应选择层（CD-CAT）

### 6.1 GDINA 模型

[v0.3.0 §2.2 与 ECOS CTA 的对接](../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md)：

```python
# ecos/cta/l3_cdcat/gdina.py
class GDINAModel:
    """
    Generalized DINA (de la Torre, 2011)

    CD-CAT 的核心算法——估计学生对每个属性的掌握模式
    """

    def __init__(self, q_matrix: QMatrix):
        self.q_matrix = q_matrix
        # 每个属性的 ID
        self.attributes = q_matrix.attributes
        # 每个属性的 P(掌握) 估计
        self.alpha_estimates: Dict[str, np.ndarray] = {}

    def estimate_attribute_mastery(self, responses: np.ndarray) -> np.ndarray:
        """
        估计学生的属性掌握模式 α ∈ {0,1}ᴬ

        Args:
            responses: 作答序列 (n_problems × 1)

        Returns:
            alpha: 属性掌握模式 (n_attributes,)
        """
        # EM 算法 + 边际最大似然
        # 详见 v0.3.0 §2.2 对接
        pass
```

### 6.2 Q 矩阵扩展（v0.5.0 整合）

[v0.5.0 §3.2 与 Q 矩阵集成](../30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md)：

```python
# ecos/cta/l3_cdcat/q_matrix.py
@dataclass
class ProblemMetadata:
    problem_id: str
    # 题目属性
    attributes: List[str]              # 考察的属性
    bloom_layer: BloomLevel            # L1-L6
    # v0.5.0 扩展
    threshold_concept: Optional[str]  # 跨越的 TC
    misconceptions: List[str]          # 触发的 misconception IDs
    # MIRT 参数
    mirt_params: 'MIRTItemParams'
    difficulty: float
    # LCA 集成
    intervention_types: List[str]
    clt_level: int                    # CLT 呈现级别 1-4
```

### 6.3 PWKL 选题算法

[v0.3.0 §2.3 借鉴决策 PWKL](../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md)：

```python
# ecos/cta/l3_cdcat/pwkl_selector.py
class PWKLSelector:
    """
    Posterior Weighted Kullback-Leibler 选题算法

    选对当前 α 估计最有用（KL 散度最大）的题目
    """

    def select_next(
        self,
        candidate_problems: List[ProblemMetadata],
        current_alpha: np.ndarray,
        bloom_target: BloomLevel,
    ) -> ProblemMetadata:
        """
        选择下一题

        算法：argmax_{problem} E_α[KL(P(α|new_resp, problem) || P(α))]
        """
        best_problem = None
        best_kl = -np.inf

        for problem in candidate_problems:
            # 模拟答对 + 答错的属性更新
            kl_after = self._compute_pwkl(problem, current_alpha)
            if kl_after > best_kl:
                best_kl = kl_after
                best_problem = problem

        return best_problem
```

---

## 7. L4 因果归因层（Causal Inference）

### 7.1 MVP 实现（单变量 A/B）

[v0.3.0 §5.3 借鉴决策 MVP 简化版](../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md)：

```python
# ecos/cta/l4_causal/ab_test.py
from scipy import stats
import numpy as np

class ABTestAttributor:
    """
    MVP 因果归因——单变量 A/B + T-test

    简化版：每种干预类型独立做 A/B
    - 实验组：接受该干预的学生
    - 对照组：未接受该干预的学生（自然成熟）
    - 指标：state_delta（CTA 测量的状态变化）
    """

    def __init__(self, config: ABTestConfig):
        self.config = config
        self.experiment_data: Dict[str, List[float]] = {}  # 干预类型 → state_delta
        self.control_data: Dict[str, List[float]] = {}

    def attribute(
        self,
        intervention_type: str,
        student_id: str,
        state_delta: float,
        is_control: bool,
    ) -> 'CausalEffect':
        """归因单次干预的因果效果"""
        if is_control:
            self.control_data.setdefault(intervention_type, []).append(state_delta)
        else:
            self.experiment_data.setdefault(intervention_type, []).append(state_delta)

        # 当样本量足够时计算 ATE
        if (len(self.experiment_data.get(intervention_type, [])) >= self.config.min_samples
            and len(self.control_data.get(intervention_type, [])) >= self.config.min_samples):
            return self._compute_ate(intervention_type)

        return CausalEffect(pending=True)

    def _compute_ate(self, intervention_type: str) -> 'CausalEffect':
        """计算 ATE（Average Treatment Effect）"""
        exp = self.experiment_data[intervention_type]
        ctrl = self.control_data[intervention_type]
        ate = np.mean(exp) - np.mean(ctrl)
        t_stat, p_value = stats.ttest_ind(exp, ctrl)
        return CausalEffect(
            ate=ate,
            p_value=p_value,
            significant=p_value < self.config.alpha,
            sample_size=len(exp),
        )
```

### 7.2 Causal Forest（Phase 5+）

```python
# ecos/cta/l4_causal/causal_forest.py
class CausalForestAttributor:
    """
    Causal Forest（Wager & Athey, 2018）

    处理高维协变量 + 异质性
    """

    def __init__(self):
        from econml.dml import CausalForestDML
        self.model = CausalForestDML()

    def estimate_cate(
        self,
        treatment: np.ndarray,    # 干预 (binary)
        outcome: np.ndarray,      # 状态变化
        covariates: np.ndarray,   # 5D + BloomProfile + LearningDNA
    ) -> np.ndarray:
        """估计 CATE（Conditional ATE）"""
        self.model.fit(outcome, treatment, X=covariates)
        return self.model.effect(covariates)
```

---

## 8. C 维度内容库集成（v0.5.0 整合）

### 8.1 Misconception 检测

[v0.5.0 §2.3 与 ECOS CTA 的对接](../30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md)：

```python
# ecos/cta/content/misc_detector.py
class MisconceptionDetector:
    """
    Misconception 检测——LLM Critic + 关键词匹配（hybrid）

    库规模（MVP）：30-50 条初中数学
    """

    def __init__(self, misc_library: 'MisconceptionLibrary', llm_critic: 'LLMCritic'):
        self.library = misc_library
        self.llm_critic = llm_critic

    def detect(
        self,
        student_explanation: str,
        problem_id: str,
        response_data: 'ResponseData',
    ) -> Optional['MisconceptionHit']:
        """
        检测学生是否触发 misconception

        Returns:
            MisconceptionHit（命中）或 None（未命中）
        """
        # Step 1: 关键词匹配（精确但覆盖率低）
        keyword_matches = self._keyword_match(student_explanation)

        # Step 2: LLM Critic 语义匹配（灵活但可能幻觉）
        llm_matches = self.llm_critic.detect_misconception(
            explanation=student_explanation,
            candidate_misc=keyword_matches,
        )

        if llm_matches:
            best_match = max(llm_matches, key=lambda m: m.confidence)
            if best_match.confidence > self.config.threshold:
                return MisconceptionHit(
                    misc_id=best_match.misc_id,
                    confidence=best_match.confidence,
                    trigger_problem_id=problem_id,
                    evidence_text=student_explanation,
                    correction_strategy=self.library.get_correction(best_match.misc_id),
                )

        return None
```

### 8.2 TC 跨越检测

[v0.5.0 §1.4 与 ECOS CTA 的对接](../30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md)：

```python
# ecos/cta/content/tc_detector.py
class TCStateDetector:
    """
    TC 状态检测——Liminal / Post-liminal 识别

    库规模（MVP）：8 个初中数学 TC
    """

    def __init__(self, tc_library: 'ThresholdConceptLibrary'):
        self.library = tc_library

    def detect(
        self,
        tc_id: str,
        observation: 'Observation',
        current_state: 'BeliefState',
    ) -> 'TCState':
        """
        检测 TC 的当前状态

        Returns:
            TCState（pre_liminal / liminal / post_liminal）
        """
        # Step 1: liminal 信号检测（启发式 + 元认知信号）
        liminal_signals = self._detect_liminal_signals(tc_id, observation, current_state)
        if liminal_signals:
            return TCState(
                tc_id=tc_id,
                status="liminal",
                progress=0.3,
                confidence=0.6,
                liminal_signals=liminal_signals,
                post_liminal_jump_detected=False,
                irreversible=False,
            )

        # Step 2: post-liminal 质变检测
        if self._detect_postliminal_jump(tc_id, observation, current_state):
            return TCState(
                tc_id=tc_id,
                status="post_liminal",
                progress=1.0,
                confidence=0.9,
                liminal_signals=[],
                post_liminal_jump_detected=True,
                irreversible=True,  # TC 不可逆
            )

        return TCState(
            tc_id=tc_id,
            status="pre_liminal",
            progress=0.0,
            confidence=0.5,
            liminal_signals=[],
            post_liminal_jump_detected=False,
            irreversible=False,
        )

    def _detect_liminal_signals(self, tc_id, observation, state) -> List[str]:
        """
        Liminal 信号检测规则（MVP 启发式）

        信号列表：
        - 连续 N 次错误（但学生在 liminal 状态会有"反复错"）
        - BloomProfile 突然倒退
        - 元认知反思文本含"困惑"、"迷茫"
        - 答题时间异常长（思考过度）
        """
        signals = []
        if state.consecutive_errors >= 3:
            signals.append("consecutive_errors")
        if state.bloom_profile.recent_decline:
            signals.append("bloom_decline")
        if self._contains_confusion_keywords(observation.reflection_text):
            signals.append("meta_confusion")
        return signals

    def _detect_postliminal_jump(self, tc_id, observation, state) -> bool:
        """
        Post-liminal 质变检测——CTA 状态突然跃迁
        """
        prev_state = state.trajectory.snapshots[-2] if len(state.trajectory.snapshots) >= 2 else None
        if prev_state is None:
            return False
        # 检测状态跃迁（质变 > 渐变）
        delta = self._compute_state_delta(prev_state, state)
        return delta > self.config.jump_threshold
```

### 8.3 C 维度更新（伪置信折扣）

```python
# ecos/cta/content/__init__.py
def update_c_dimension_with_content(
    state: BeliefState,
    misc_hit: Optional[MisconceptionHit],
    tc_states: Dict[str, TCState],
) -> BeliefState:
    """C 维度更新——含 misconception 折扣与 TC 不可逆性"""

    # 1. 基础 BKT 更新（与 K/P/S/X 一致）
    # ...（略）

    # 2. Misconception 折扣（v0.5.0 关键规则）
    if misc_hit:
        state.C.theta *= 0.7  # 折扣 30%（伪置信检测）
        state.C.illusory_confidence_flag = True
        state.C.discount_factor = 0.7
        state.C.misconception_hits.append(misc_hit)

    # 3. TC 不可逆性建模（一旦 post-liminal，C 不再下降）
    for tc_id, tc_state in tc_states.items():
        if tc_state.status == "post_liminal" and tc_state.irreversible:
            state.C.tc_states[tc_id] = tc_state
            # post-liminal 后 C 在该 TC 范围内永不下降
            # （除非整个学科遗忘）

    return state
```

---

## 9. LLM Critic 边界

[v0.3.0 §6.2 与 LLM 的关系](../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md)：

| 层级 | CTA 实现 | LLM 角色 |
|---|---|---|
| L0-L2 数学层 | 纯统计 | **零使用 LLM**——保证数学严谨性 |
| 感知层（o_t 提取）| 结构化提取 | **LLM Critic** 把自然语言作答转结构化 |
| 解释层 | 模板 + 统计值 | **LLM** 生成自然语言解释 |

### 9.1 感知层

```python
# ecos/cta/llm_critic/perception.py
class PerceptionCritic:
    """
    LLM Critic 感知层——把自然语言转结构化数据

    输入：学生原始作答（自由文本）
    输出：结构化信号
      - correctness（bool）
      - explanation_quality（0-1）
      - confusion_signals（list of strings）
      - self_evaluation（0-1，学生的自我评估）
    """

    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.prompt_template = self._load_prompt_template("perception.txt")

    def perceive(self, observation: Observation) -> StructuredObservation:
        """自然语言 → 结构化"""
        prompt = self.prompt_template.format(
            student_response=observation.text_response,
            problem=observation.problem.description,
        )
        response = self.llm_client.generate(prompt, temperature=0.2)
        return StructuredObservation.parse(response)
```

### 9.2 解释层

```python
# ecos/cta/llm_critic/explanation.py
class ExplanationCritic:
    """
    LLM Critic 解释层——统计值 → 自然语言

    输入：BeliefState（统计值）
    输出：自然语言诊断报告
    """

    def explain(self, state: BeliefState, audience: str = "teacher") -> str:
        """
        生成诊断报告

        Args:
            state: CTA 信念状态
            audience: 'teacher' / 'parent' / 'student'（不同受众风格不同）
        """
        template = self._load_template(audience)
        prompt = template.format(
            k_mastery=state.K.theta,
            p_mastery=state.P.theta,
            s_strategy=state.S.theta,
            c_confidence=state.C.theta,
            bloom_profile=state.bloom_profile,
            tc_states=state.C.tc_states,
        )
        return self.llm_client.generate(prompt, temperature=0.3)
```

### 9.3 Misconception 检测（v0.5.0 整合）

```python
# ecos/cta/llm_critic/critic_prompts.py
class CriticPrompts:
    """LLM Critic 提示词库"""

    PERCEPTION = """
你是教育评估专家。请分析学生的作答：

题目：{problem}
学生作答：{student_response}
正确作答：{correct_answer}

请提取：
1. correctness（对/错）
2. explanation_quality（0-1）：学生解释的质量
3. confusion_signals：困惑信号（如"我不确定"、"可能是"）
4. self_evaluation（0-1）：学生对自己作答的自信程度

JSON 输出：
{
  "correctness": true/false,
  "explanation_quality": 0.0-1.0,
  "confusion_signals": [...],
  "self_evaluation": 0.0-1.0
}
"""

    MISCONCEPTION_DETECTION = """
你是数学教师。检查学生是否触发了常见 misconception：

学生解释：{student_explanation}
候选 misconception：
{candidate_misconceptions}

如果触发，请指出最可能的 misconception ID 和置信度。
"""

    EXPLANATION_TEACHER = """
你是教育顾问。基于以下学生状态生成诊断报告：

5D 状态：
- K（知识）：{k_mastery}
- P（程序）：{p_mastery}
- S（策略）：{s_strategy}
- C（置信度）：{c_confidence}

BloomProfile：{bloom_profile}
TC 状态：{tc_states}

请生成 200 字以内的诊断报告，包含：
1. 学生目前最强与最弱的维度
2. 推荐的干预方向
3. 与 Bloom 目标空间的差距
"""
```

---

## 10. CTA 主流程编排

```python
# ecos/cta/orchestrator.py
class CTAOrchestrator:
    """CTA 主流程编排——5 层 + 内容库 + LLM Critic 集成"""

    def __init__(self, config: CTAConfig):
        # 5 层数学栈
        self.l0_pomdp = CTAPOMDP(config.pomdp)
        self.l1_evolution = BKTEvolutionLayer(config.evolution)
        self.l2_mirt = BiFactorMIRT5D(config.mirt)
        self.l3_cdcat = GDINAModel(config.cdcat)
        self.l4_causal = ABTestAttributor(config.causal)
        # 内容库
        self.tc_library = ThresholdConceptLibrary.load(config.subject)
        self.misc_library = MisconceptionLibrary.load(config.subject)
        self.tc_detector = TCStateDetector(self.tc_library)
        self.misc_detector = MisconceptionDetector(self.misc_library, ...)
        # LLM Critic
        self.perception = PerceptionCritic(...)
        self.explanation = ExplanationCritic(...)
        # 当前状态
        self.current_state: Optional[BeliefState] = None

    def update(
        self,
        observation: Observation,
        lca_result: Optional[LCAResult] = None,
    ) -> CTAOutput:
        """主更新流程"""
        # Step 1: LLM Critic 感知
        structured_obs = self.perception.perceive(observation)

        # Step 2: L0 POMDP 预测
        self.current_state = self.l0_pomdp.predict(self.current_state, lca_result)

        # Step 3: L1 BKT 更新（每个技能）
        for skill in structured_obs.skills_touched:
            self.l1_evolution.update(skill, structured_obs.correct)

        # Step 4: L2 MIRT 联合估计
        self.l2_mirt.update(self.current_state, structured_obs)

        # Step 5: C 维度内容库更新
        misc_hit = self.misc_detector.detect(
            observation.text_response, observation.problem_id, structured_obs
        )
        tc_states = {
            tc_id: self.tc_detector.detect(tc_id, observation, self.current_state)
            for tc_id in self.tc_library.all_tcs
        }
        self.current_state = update_c_dimension_with_content(
            self.current_state, misc_hit, tc_states
        )

        # Step 6: L3 CD-CAT 选下一题（给 LCA）
        next_problem = self.l3_cdcat.select_next(
            candidate_problems=self._get_candidate_problems(),
            current_alpha=self.current_state.attribute_estimates,
            bloom_target=self._infer_bloom_target(),
        )

        # Step 7: L4 因果归因（如有 LCA 结果）
        if lca_result and lca_result.actual_outcome is not None:
            causal_effect = self.l4_causal.attribute(
                intervention_type=lca_result.intervention_type,
                student_id=observation.student_id,
                state_delta=lca_result.actual_outcome,
                is_control=lca_result.is_control,
            )
            self.current_state.last_causal_effect = causal_effect

        # Step 8: 输出（给 LCA + App 层）
        return CTAOutput(
            student_id=observation.student_id,
            belief_state=self.current_state,
            bloom_target_candidates=self._get_bloom_target_candidates(),
            intervention_hints=self._extract_intervention_hints(),
            confidence=self.current_state.overall_confidence,
            timestamp=datetime.now(),
        )

    def generate_report(self, audience: str = "teacher") -> str:
        """生成诊断报告"""
        return self.explanation.explain(self.current_state, audience)
```

---

## 11. 测试策略

### 11.1 单元测试（覆盖率 ≥ 80%）

[v0.3.0 §3.5 实施注意事项 + 04-risks.md §A2 缓解策略](../00-overview/04-risks.md)：

| 模块 | 测试重点 | 覆盖率目标 |
|---|---|---|
| `l0_pomdp/` | EKF 准确性、信念更新数学正确性 | ≥ 90% |
| `l1_evolution/bkt.py` | BKT 更新规则、参数边界 | ≥ 90% |
| `l2_mirt/` | EM 算法收敛、协方差正定性 | ≥ 85% |
| `l3_cdcat/` | PWKL 选题最优性、GDINA 估计 | ≥ 85% |
| `l4_causal/` | A/B test 显著性检验 | ≥ 90% |
| `content/tc_detector.py` | liminal/post-liminal 识别 F1 | ≥ 80% |
| `content/misc_detector.py` | Misconception 检测 F1 ≥ 0.7 | 核心目标 |
| `llm_critic/` | Prompt 模板正确性、JSON 解析 | ≥ 70% |

### 11.2 集成测试

```python
# ecos/cta/tests/test_integration.py
def test_full_cta_pipeline():
    """完整 CTA 流程测试"""
    cta = CTAOrchestrator(config_for_test())

    # 模拟 100 次学生作答
    for i in range(100):
        observation = generate_synthetic_observation(i)
        lca_result = generate_synthetic_lca_result(i)
        output = cta.update(observation, lca_result)

    # 验证信念状态合理性
    assert 0 <= output.belief_state.overall_confidence <= 1
    assert output.belief_state.K.theta > 0  # 应该学会
    assert output.belief_state.bloom_profile.apply > 0  # 应该能应用

    # 验证因果归因
    assert output.belief_state.last_causal_effect is not None
```

### 11.3 评估指标（对照 04-risks.md §A 风险阈值）

| 指标 | 阈值 | 测试场景 |
|---|---|---|
| **CTA 5D 预测 AUC** | ≥ 0.75（vs IRT baseline 0.65）| M3 实验 |
| **Misconception 检测 F1** | ≥ 0.7 | 100 标注样本 |
| **TC 跨越检测 F1** | ≥ 0.6 | 50 标注样本 |
| **ECE（双 Agent 校准度）** | ≤ 0.10 | M3 实验 |
| **互校循环延迟 P95** | ≤ 5 秒 | 性能测试 |
| **LLM API 成本** | ≤ 50 次/学生/天 | 成本监控 |

---

## 12. MVP 范围（Phase 4）

### 12.1 MVP 包含的组件

| 组件 | 实现状态 |
|---|---|
| L0 POMDP（EKF + 离散精确推断）| ✅ MVP |
| L0 POMCP | ❌ Phase 5+ |
| L1 BKT 经典 4 参数 | ✅ MVP |
| L1 DKT / DKVMN | ❌ Phase 5+ |
| L1 FSRS 间隔效应 | ✅ MVP |
| L2 MIRT 5D 非补偿 Bi-factor | ✅ MVP |
| L2 协方差结构学习 | ✅ MVP（简化）|
| L3 GDINA + PWKL | ✅ MVP |
| L3 Q 矩阵扩展（含 TC + Misc）| ✅ MVP |
| L4 A/B test + T-test | ✅ MVP（简化版）|
| L4 Causal Forest | ❌ Phase 5+ |
| C 维度 TC 库（8 个）| ✅ MVP |
| C 维度 Misconceptions 库（30-50 条）| ✅ MVP |
| LLM Critic 感知层 | ✅ MVP |
| LLM Critic 解释层 | ✅ MVP |
| LLM Critic Misconception 检测 | ✅ MVP |

### 12.2 MVP 不包含的组件

- ❌ POMCP 完整求解
- ❌ DKT / DKVMN 深度知识追踪
- ❌ Causal Forest 异质性处理
- ❌ 跨学科 TC / Misconceptions 库
- ❌ 学生级深度个性化

### 12.3 MVP 数据流

```
Student → App（做题） → CTAOrchestrator.update()
                       ↓
                       LLM Critic（感知层）
                       ↓
                       L0-L4 数学栈 + 内容库
                       ↓
                       CTAOutput（信念分布 + 干预提示）
                       ↓
                       LCA（消费 CTAOutput）
```

---

## 13. 关联文档

- **同级工程层**（按依赖顺序）：
  - [02-lca-policy-engine.md](02-lca-policy-engine.md) — LCA 策略引擎（CTA 的下游消费者）
  - [03-bloom-goal-library.md](03-bloom-goal-library.md) — Bloom 目标库（CTA 状态映射）
  - [04-dual-agent-calibration.md](04-dual-agent-calibration.md) — 双 Agent 互校（CTA + LCA 接口契约）
  - [05-persistence-session.md](05-persistence-session.md) — 持久化（CTA 状态存储）
- **P0 借鉴**（理论依据）：
  - [v0.3.0 CTA 数学基础](../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md) — 5 层数学栈的完整数学定义
  - [v0.5.0 C 维度内容库](../30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md) — TC + Misconceptions 整合
- **上层文档**：
  - [02-architecture.md §5 状态估计工程实现](../00-overview/02-architecture.md) — 本文档的架构依据
  - [03-roadmap.md §2.2 M2 里程碑](../00-overview/03-roadmap.md) — W1-W6 工程任务
  - [04-risks.md §A 技术风险](../00-overview/04-risks.md) — 风险缓解策略
- **核心论证**：
  - [v2.0 §3.3 CTA 设计](../deep-research/Cognitive-Digital-Twin-Deep-Research.md) — CTA 思维模式 + 9D 状态空间

---

## 14. 版本与维护

- **v1.0**（2026-06-25）— 初版

**待办（影响本文档时同步更新）**：
- 当 [02-lca-policy-engine.md](02-lca-policy-engine.md) 完成后，回填 §1.3 与 LCA 接口契约
- 当 [04-dual-agent-calibration.md](04-dual-agent-calibration.md) 完成后，回填 §7 因果归因在互校中的角色
- 当 Phase 4 MVP 实验完成后，回填 §11.3 实际评估指标 vs 阈值

---

**创建日期**：2026-06-25
**维护者**：Bisen & Claude
