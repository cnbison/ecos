# 双 Agent 互校机制（Dual Agent Calibration）

> **版本**：v1.0（2026-06-25）
> **性质**：工程层第 4 份文档——CTA ↔ LCA 互校机制的工程实现设计
> **基于**：[v2.0 §3.5 双 Agent 互校](../deep-research/Cognitive-Digital-Twin-Deep-Research.md)、[02-architecture.md §3.3 双 Agent 详细架构](../00-overview/02-architecture.md)、[01-cta-belief-engine.md](01-cta-belief-engine.md)、[02-lca-policy-engine.md](02-lca-policy-engine.md)、[03-bloom-goal-library.md](03-bloom-goal-library.md)、[03-roadmap.md §2.3 M3 假设验证](../00-overview/03-roadmap.md)、[04-risks.md §A1 + §A4](../00-overview/04-risks.md)
> **后续**：[05-persistence-session.md](05-persistence-session.md)
> **维护者**：Bisen & Claude

---

## 0. 模块定位

### 0.1 核心职责

**双 Agent 互校机制**是 ECOS 的"抗幻觉核心"——通过 CTA（保守、基于证据）与 LCA（主动、实验、探索）的互相质疑，防止 LLM 幻觉污染。核心职责：

1. **互校循环协议**——CTA 输出信念 → LCA 设计实验 → 观察结果 → CTA 更新信念 → LCA 因果归因
2. **4 个交互模式**——常态循环 / 信念质疑 / 策略质疑 / 元反思
3. **3 个对抗幻觉机制**——CTA 信念分布 / LCA 设计实验 / 因果归因
4. **通信契约**——CTA 与 LCA 通过标准化消息格式交互

**关键定位**：[02-architecture.md §3.3 互校循环](../00-overview/02-architecture.md) + [v2.0 §3.5 互校对抗幻觉的 3 个机制](../deep-research/Cognitive-Digital-Twin-Deep-Research.md)

### 0.2 与其他模块的接口

```
┌─────────────────────────────────────────────────────────────┐
│ CTA Belief Engine（[01-cta-belief-engine.md](01-cta-belief-engine.md)）│
│   ↓ CTAOutput                                              │
│ Dual Agent Calibration（本模块）                             │
│   ├── 常态循环：直接转发 CTA → LCA → App                     │
│   ├── 信念质疑：CTA ↔ LCA 循环对话                            │
│   ├── 策略质疑：CTA 挑战 LCA 干预                            │
│   └── 元反思：双 Agent 整体复盘                              │
│   ↓ LCAResult（含 causal_effect）                           │
│ LCA Policy Engine（[02-lca-policy-engine.md](02-lca-policy-engine.md)）│
└─────────────────────────────────────────────────────────────┘
```

### 0.3 与 [04-risks.md §A1 + §A4](../00-overview/04-risks.md) 的对应

| 风险 | 缓解机制 |
|---|---|
| **A1 双 Agent 工程复杂度** | 模块化协议（JSON Schema）+ 超时保护 + 单元测试 |
| **A4 双 Agent 互校抗幻觉失败** | 数学层不用 LLM（硬底线）+ 人工审核触发 + 因果归因强制 |

### 0.4 文档目标读者

- **工程实现者**：按本文档实现 `ecos/dual_agent/` Python 模块
- **算法研究人员**：理解互校循环算法 + 4 个交互模式
- **测试人员**：理解测试策略 + 性能基准

---

## 1. 整体架构

### 1.1 互校循环总览

[02-architecture.md §3.3 + v2.0 §3.5 互校循环](../00-overview/02-architecture.md)：

```
┌──────────────────────────────────────────────────────────────────┐
│                    双 Agent 互校循环                               │
├──────────────────────────────────────────────────────────────────┤
│  Step 1: CTA 提出假设                                            │
│    "学生 K=0.4, 程序技能弱 + 二级 misconception"                 │
│                                                                  │
│  Step 2: LCA 设计实验验证                                        │
│    "设计 3 道'读题 → 识别模型'的讲解型 + 练习型"                │
│                                                                  │
│  Step 3: 观察结果（App 层数据采集）                              │
│    "3 道错 2 道，错误集中在分情况讨论"                          │
│                                                                  │
│  Step 4: CTA 更新信念（基于观测）                                │
│    "程序技能 0.35 → 0.30 + 检测到分情况讨论子缺口"               │
│                                                                  │
│  Step 5: LCA 因果归因（L4 Causal Inference）                     │
│    "本次干预对程序技能贡献 -0.05（CATE）"                        │
│                                                                  │
│  Step 6: LCA 重新规划                                            │
│    "切换目标 Bloom 层 + 调整干预类型"                            │
│                                                                  │
│  循环：Step 1 ...                                                │
└──────────────────────────────────────────────────────────────────┘
```

### 1.2 4 个交互模式

[v2.0 §3.5 互校的 4 个交互模式](../deep-research/Cognitive-Digital-Twin-Deep-Research.md)：

| 模式 | 触发条件 | 处理逻辑 |
|---|---|---|
| **常态循环** | 新事件/新证据 | 直接执行 Step 1-6 |
| **信念质疑** | LCA 不同意 CTA 状态判断 | 进入循环对话（CTA 重审信念 + LCA 重审建议）|
| **策略质疑** | CTA 发现 LCA 干预无效 | CTA 反馈给 LCA + LCA 调整策略空间 |
| **元反思** | 整体进步停滞（4 周无显著 BloomProfile 提升）| 双 Agent 整体复盘 + 重新对齐目标 |

### 1.3 3 个对抗幻觉机制

[v2.0 §3.5 互校对抗幻觉的 3 个机制](../deep-research/Cognitive-Digital-Twin-Deep-Research.md)：

1. **CTA 保守 vs LCA 主动**：CTA 不轻易下结论（维护信念分布），LCA 必须用实验验证
2. **CTA 数学严格 vs LCA 教学法灵活**：数学层不容妥协，教学法可调整
3. **L4 因果归因强制**：每个干预效果必须经因果归因（不能仅看相关性）

### 1.4 模块目录结构

```
ecos/dual_agent/
├── __init__.py
├── orchestrator.py            # 互校主流程编排
├── protocol/
│   ├── __init__.py
│   ├── messages.py            # 消息格式定义（CTAOutput / LCAResult 扩展）
│   ├── state_machine.py       # 互校状态机
│   └── version.py             # version 协议
├── modes/
│   ├── __init__.py
│   ├── normal.py              # 常态循环
│   ├── belief_challenge.py    # 信念质疑模式
│   ├── strategy_challenge.py  # 策略质疑模式
│   └── meta_reflection.py     # 元反思模式
├── anti_hallucination/
│   ├── __init__.py
│   ├── belief_check.py        # 信念分布检查
│   ├── experiment_design.py   # 实验设计验证
│   ├── causal_attribution.py  # 因果归因
│   └── human_review.py        # 人工审核触发
├── deadlock/
│   ├── __init__.py
│   ├── timeout.py             # 超时保护
│   ├── priority.py            # 优先级仲裁
│   └── fallback.py            # 降级到单 Agent
├── tests/
│   ├── test_normal.py
│   ├── test_belief_challenge.py
│   ├── test_strategy_challenge.py
│   ├── test_meta_reflection.py
│   ├── test_protocol.py
│   └── test_integration.py
└── README.md
```

### 1.5 与 CTA / LCA 接口契约

**CTA 输出**（已在 [01-cta-belief-engine.md §1.3](01-cta-belief-engine.md) 定义）：
- `CTAOutput`：student_id + belief_state + bloom_target_candidates + intervention_hints + confidence + timestamp

**LCA 输出**（已在 [02-lca-policy-engine.md §1.3](02-lca-policy-engine.md) 定义）：
- `LCAResult`：student_id + intervention + rationale + expected_gain/risk + bloom_target + timestamp + actual_outcome（互校后填充）+ causal_effect（互校后填充）

**互校扩展字段**（本模块定义）：

```python
@dataclass
class CalibratedCTAOutput(CTAOutput):
    """CTA 输出 + 互校元数据"""
    calibration_round: int = 0             # 互校轮次
    challenge_history: List[str] = field(default_factory=list)  # 历史质疑记录
    belief_challenge_pending: bool = False  # 是否有待解决的信念质疑

@dataclass
class CalibratedLCAResult(LCAResult):
    """LCA 输出 + 互校元数据"""
    calibration_round: int = 0
    strategy_challenge_pending: bool = False  # 是否有待解决的策略质疑
    expected_calibration_gain: float = 0.0   # 互校期望增益
```

---

## 2. 互校循环协议

### 2.1 消息格式（JSON Schema）

```python
# ecos/dual_agent/protocol/messages.py
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union
from enum import Enum

class MessageType(Enum):
    """互校消息类型"""
    CTA_OUTPUT = "cta_output"             # CTA 信念输出
    LCA_INTERVENTION = "lca_intervention" # LCA 干预选择
    OBSERVATION = "observation"           # 观察结果
    CTA_UPDATE = "cta_update"             # CTA 信念更新
    CAUSAL_ATTRIBUTION = "causal"         # LCA 因果归因
    BELIEF_CHALLENGE = "belief_challenge" # 信念质疑
    STRATEGY_CHALLENGE = "strategy_challenge"  # 策略质疑
    META_REFLECTION = "meta_reflection"   # 元反思
    HUMAN_REVIEW_REQUEST = "human_review" # 人工审核请求

@dataclass
class CalibrationMessage:
    """互校消息（统一格式）"""
    message_id: str                        # UUID
    message_type: MessageType
    student_id: str
    timestamp: float                       # unix time
    version: str = "v1.0"                  # 协议版本
    calibration_round: int = 0             # 当前互校轮次
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0                      # 优先级（0=normal, 1=high, 2=critical）
    timeout_sec: int = 30                  # 期望响应时间
    metadata: Dict[str, Any] = field(default_factory=dict)
```

### 2.2 互校状态机

```python
# ecos/dual_agent/protocol/state_machine.py
from enum import Enum

class CalibrationState(Enum):
    """互校状态"""
    IDLE = "idle"                          # 空闲，等待下一观测
    CTA_HYPOTHESIS = "cta_hypothesis"      # CTA 提出假设
    LCA_EXPERIMENT = "lca_experiment"      # LCA 设计实验
    OBSERVATION_PENDING = "obs_pending"    # 等待观察结果
    CTA_UPDATE = "cta_update"              # CTA 更新信念
    LCA_CAUSAL = "lca_causal"              # LCA 因果归因
    LCA_REPLAN = "lca_replan"              # LCA 重新规划
    BELIEF_CHALLENGE = "belief_challenge"  # 信念质疑中
    STRATEGY_CHALLENGE = "strategy_challenge"  # 策略质疑中
    META_REFLECTION = "meta_reflection"    # 元反思中
    HUMAN_REVIEW = "human_review"          # 等待人工审核
    COMPLETED = "completed"                # 本轮互校完成

class CalibrationStateMachine:
    """互校状态机"""

    def __init__(self):
        self.state: Dict[str, CalibrationState] = {}  # student_id → 当前状态

    def transition(
        self,
        student_id: str,
        event: MessageType,
    ) -> CalibrationState:
        """根据事件转移状态"""
        current = self.state.get(student_id, CalibrationState.IDLE)

        # 状态转移规则
        transitions = {
            (CalibrationState.IDLE, MessageType.CTA_OUTPUT): CalibrationState.CTA_HYPOTHESIS,
            (CalibrationState.CTA_HYPOTHESIS, MessageType.LCA_INTERVENTION): CalibrationState.LCA_EXPERIMENT,
            (CalibrationState.LCA_EXPERIMENT, MessageType.OBSERVATION): CalibrationState.OBSERVATION_PENDING,
            (CalibrationState.OBSERVATION_PENDING, MessageType.CTA_UPDATE): CalibrationState.CTA_UPDATE,
            (CalibrationState.CTA_UPDATE, MessageType.CAUSAL_ATTRIBUTION): CalibrationState.LCA_CAUSAL,
            (CalibrationState.LCA_CAUSAL, MessageType.LCA_INTERVENTION): CalibrationState.LCA_REPLAN,
            (CalibrationState.LCA_REPLAN, MessageType.COMPLETED): CalibrationState.IDLE,
            # 特殊转移
            (CalibrationState.IDLE, MessageType.BELIEF_CHALLENGE): CalibrationState.BELIEF_CHALLENGE,
            (CalibrationState.IDLE, MessageType.STRATEGY_CHALLENGE): CalibrationState.STRATEGY_CHALLENGE,
            (CalibrationState.IDLE, MessageType.META_REFLECTION): CalibrationState.META_REFLECTION,
            # 任意状态 → 人工审核
        }

        next_state = transitions.get((current, event), current)
        self.state[student_id] = next_state
        return next_state
```

### 2.3 version 协议

```python
# ecos/dual_agent/protocol/version.py
PROTOCOL_VERSION = "v1.0"

class VersionCompatibility:
    """协议版本兼容性"""

    SUPPORTED_VERSIONS = ["v1.0"]

    @classmethod
    def is_compatible(cls, version: str) -> bool:
        """检查版本兼容性"""
        return version in cls.SUPPORTED_VERSIONS

    @classmethod
    def negotiate(cls, local_version: str, remote_version: str) -> str:
        """协商共同版本"""
        if local_version == remote_version:
            return local_version
        # 简化：v1.x 之间互通
        if local_version.startswith("v1.") and remote_version.startswith("v1."):
            return min(local_version, remote_version)
        raise ValueError(f"不兼容的协议版本: {local_version} vs {remote_version}")
```

---

## 3. 4 个交互模式

### 3.1 常态循环（新事件/新证据）

[v2.0 §3.5 互校核心循环](../deep-research/Cognitive-Digital-Twin-Deep-Research.md)：

```python
# ecos/dual_agent/modes/normal.py
class NormalCycle:
    """常态循环——新事件/新证据时执行"""

    def __init__(
        self,
        cta: 'CTAOrchestrator',
        lca: 'LCAOrchestrator',
        state_machine: 'CalibrationStateMachine',
    ):
        self.cta = cta
        self.lca = lca
        self.state_machine = state_machine

    def run(
        self,
        observation: 'Observation',
        previous_lca_result: Optional['CalibratedLCAResult'] = None,
    ) -> 'CalibratedLCAResult':
        """执行一轮常态互校"""
        student_id = observation.student_id

        # Step 1: CTA 提出假设（基于新观测）
        cta_output = self.cta.update(observation, previous_lca_result)
        cta_output = CalibratedCTAOutput(
            **cta_output.__dict__,
            calibration_round=self._next_round(student_id),
        )
        self.state_machine.transition(student_id, MessageType.CTA_OUTPUT)

        # Step 2: LCA 设计实验（基于 CTA 信念）
        lca_result = self.lca.select_intervention(cta_output)
        lca_result = CalibratedLCAResult(
            **lca_result.__dict__,
            calibration_round=cta_output.calibration_round,
        )
        self.state_machine.transition(student_id, MessageType.LCA_INTERVENTION)

        # Step 3: 输出 LCAResult 给 App 层执行
        self.state_machine.transition(student_id, MessageType.OBSERVATION)
        return lca_result

    def _next_round(self, student_id: str) -> int:
        """获取下一轮互校序号"""
        # 简化：每观测一轮 +1
        # 实际应该持久化
        return 0
```

### 3.2 信念质疑模式

**触发条件**：LCA 不认同 CTA 状态判断（如 CTA 说"学生已掌握二次函数"，但 LCA 实验发现学生仍错）

```python
# ecos/dual_agent/modes/belief_challenge.py
class BeliefChallengeMode:
    """信念质疑模式——LCA 不同意 CTA 状态"""

    def __init__(
        self,
        cta: 'CTAOrchestrator',
        lca: 'LCAOrchestrator',
    ):
        self.cta = cta
        self.lca = lca

    def trigger_challenge(
        self,
        student_id: str,
        cta_output: 'CalibratedCTAOutput',
        experimental_evidence: Dict[str, Any],
    ) -> 'BeliefChallenge':
        """LCA 发起信念质疑"""
        # 构造质疑消息
        challenge = BeliefChallenge(
            student_id=student_id,
            challenged_dimension=experimental_evidence['dimension'],
            cta_claim=cta_output.belief_state.__dict__[experimental_evidence['dimension']].theta,
            experimental_evidence=experimental_evidence,
            confidence_in_evidence=experimental_evidence.get('confidence', 0.8),
        )
        cta_output.belief_challenge_pending = True
        return challenge

    def resolve_challenge(
        self,
        cta_output: 'CalibratedCTAOutput',
        challenge: 'BeliefChallenge',
        new_observation: 'Observation',
    ) -> 'CalibratedCTAOutput':
        """CTA 重新审视信念并更新"""
        # CTA 接收质疑 + 新证据，重新估计
        new_cta_output = self.cta.update(new_observation)

        # 比较新旧信念
        old_value = challenge.cta_claim
        new_value = new_cta_output.belief_state.__dict__[challenge.challenged_dimension].theta
        belief_change = abs(new_value - old_value)

        # 记录质疑历史
        cta_output.challenge_history.append(
            f"{challenge.challenged_dimension}: {old_value:.3f} → {new_value:.3f} (Δ={belief_change:.3f})"
        )
        cta_output.belief_challenge_pending = False
        return new_cta_output
```

**信念质疑触发条件**：

```python
def should_trigger_belief_challenge(
    cta_output: 'CalibratedCTAOutput',
    new_observation: 'Observation',
) -> bool:
    """判断是否应触发信念质疑"""
    # 条件 1：CTA 高置信度但学生实际表现差
    if cta_output.belief_state.K.mastery_prob > 0.7 and not new_observation.correct:
        return True
    # 条件 2：CTA 信念变化超过阈值（前后矛盾）
    # ...（省略）
    # 条件 3：LCA 实验结果与 CTA 预测不符
    if cta_output.belief_state.P.theta > 0.6 and new_observation.response_time > 60:  # 程序技能强但答题慢
        return True
    return False
```

### 3.3 策略质疑模式

**触发条件**：CTA 发现 LCA 干预无效（连续 N 次干预后状态无改善）

```python
# ecos/dual_agent/modes/strategy_challenge.py
class StrategyChallengeMode:
    """策略质疑模式——CTA 挑战 LCA 干预"""

    def __init__(self, cta: 'CTAOrchestrator', lca: 'LCAOrchestrator'):
        self.cta = cta
        self.lca = lca

    def detect_ineffective_intervention(
        self,
        student_id: str,
        intervention_history: List['CalibratedLCAResult'],
        state_trajectory: List['BeliefState'],
    ) -> bool:
        """检测干预是否无效"""
        if len(intervention_history) < 5:
            return False

        # 检查最近 5 次干预的状态变化
        recent = intervention_history[-5:]
        recent_states = state_trajectory[-5:]

        # 计算状态改善量
        gains = [
            recent_states[i+1].K.mastery_prob - recent_states[i].K.mastery_prob
            for i in range(len(recent) - 1)
        ]
        avg_gain = sum(gains) / len(gains) if gains else 0

        # 平均改善 < 0.05 视为无效
        return avg_gain < 0.05

    def challenge_lca(
        self,
        student_id: str,
        ineffective_intervention_type: str,
        proposed_alternative: str,
    ) -> 'StrategyChallenge':
        """CTA 向 LCA 发起策略质疑"""
        return StrategyChallenge(
            student_id=student_id,
            current_intervention_type=ineffective_intervention_type,
            cta_suggestion=proposed_alternative,
            evidence="连续 5 次干预平均改善 < 0.05",
        )

    def lca_revise_policy(
        self,
        challenge: 'StrategyChallenge',
        lca: 'LCAOrchestrator',
    ) -> 'LCAResult':
        """LCA 接受挑战并调整策略"""
        # 临时禁用当前干预类型
        lca.bandit.bandit.A[challenge.current_intervention_type] *= 10  # 增加协方差，降低 UCB
        # 重新选择干预
        return lca.select_intervention_from_history(challenge.student_id)
```

### 3.4 元反思模式

**触发条件**：整体进步停滞（4 周无显著 BloomProfile 提升）

```python
# ecos/dual_agent/modes/meta_reflection.py
class MetaReflectionMode:
    """元反思模式——整体进步停滞时触发"""

    def __init__(self, cta: 'CTAOrchestrator', lca: 'LCAOrchestrator'):
        self.cta = cta
        self.lca = lca

    def detect_stagnation(
        self,
        student_id: str,
        state_trajectory: List['BeliefState'],
        window_days: int = 28,
    ) -> bool:
        """检测整体进步停滞"""
        if len(state_trajectory) < 4:
            return False

        # 取最近 4 周的状态快照
        recent_snapshots = state_trajectory[-4:]
        # 计算 BloomProfile 提升量
        bloom_initial = recent_snapshots[0].bloom_profile
        bloom_current = recent_snapshots[-1].bloom_profile
        # 主要 Bloom 层提升 < 0.05 视为停滞
        key_layers = ['apply', 'analyze']  # 关键层
        stagnation = True
        for layer in key_layers:
            initial = getattr(bloom_initial, layer)
            current = getattr(bloom_current, layer)
            if current - initial >= 0.05:
                stagnation = False
                break
        return stagnation

    def run_meta_reflection(
        self,
        student_id: str,
        state_trajectory: List['BeliefState'],
        intervention_history: List['CalibratedLCAResult'],
    ) -> 'MetaReflectionReport':
        """双 Agent 整体复盘"""
        # CTA 重新审视信念估计是否有偏差
        cta_review = self._cta_review(student_id, state_trajectory)

        # LCA 重新审视策略空间是否合适
        lca_review = self._lca_review(student_id, intervention_history)

        # 共同反思：是否有共同假设错误
        joint_review = self._joint_review(cta_review, lca_review)

        return MetaReflectionReport(
            student_id=student_id,
            cta_review=cta_review,
            lca_review=lca_review,
            joint_review=joint_review,
            recommendations=joint_review['recommendations'],
        )

    def _cta_review(self, student_id, state_trajectory) -> Dict:
        """CTA 反思：信念估计是否合理"""
        # 分析：BKT P(L) 是否过于保守/乐观？
        # 误判率是否高？
        # Misconception 检测是否准确？
        return {
            'agent': 'CTA',
            'self_critique': '...',
            'adjustments': ['...'],
        }

    def _lca_review(self, student_id, intervention_history) -> Dict:
        """LCA 反思：策略空间是否合适"""
        # 分析：干预类型分布是否合理？
        # 是否过度依赖某种策略？
        # CA 阶段判断是否准确？
        return {
            'agent': 'LCA',
            'self_critique': '...',
            'adjustments': ['...'],
        }

    def _joint_review(self, cta_review, lca_review) -> Dict:
        """双 Agent 共同反思"""
        # 寻找 CTA 与 LCA 共同假设错误
        # 例如：双方都假设学生是"视觉型"，但实际是"动觉型"
        return {
            'joint_assumptions_to_test': ['...'],
            'recommendations': ['...'],
        }
```

---

## 4. 对抗幻觉的 3 个机制

[v2.0 §3.5 互校对抗幻觉的 3 个机制](../deep-research/Cognitive-Digital-Twin-Deep-Research.md)：

### 4.1 机制 1：CTA 信念分布（非事实判断）

```python
# ecos/dual_agent/anti_hallucination/belief_check.py
class BeliefDistributionCheck:
    """CTA 信念分布检查——确保信念是分布而非事实"""

    @staticmethod
    def is_well_formed(belief_state: 'BeliefState') -> Tuple[bool, List[str]]:
        """检查信念状态是否合理"""
        issues = []

        # 检查 1：每个维度都有 confidence
        for dim_name in ['K', 'P', 'S', 'C', 'X']:
            dim = getattr(belief_state, dim_name)
            if not hasattr(dim, 'confidence'):
                issues.append(f"{dim_name} 缺少 confidence")

        # 检查 2：confidence < 0.6 时应有 evidence_ids
        for dim_name in ['K', 'P', 'S', 'C', 'X']:
            dim = getattr(belief_state, dim_name)
            if dim.confidence < 0.6 and len(dim.evidence_ids) < 3:
                issues.append(f"{dim_name} 低置信度但证据不足")

        # 检查 3：不能单一 confidence = 1.0（避免过度自信）
        max_conf = max(getattr(belief_state, d).confidence for d in ['K', 'P', 'S', 'C', 'X'])
        if max_conf >= 0.99:
            issues.append(f"存在过度自信 (max_confidence={max_conf})")

        return len(issues) == 0, issues
```

### 4.2 机制 2：LCA 设计实验（非直接给答案）

```python
# ecos/dual_agent/anti_hallucination/experiment_design.py
class ExperimentDesignValidator:
    """LCA 实验设计验证——确保 LCA 不是直接给答案"""

    @staticmethod
    def validate_intervention(intervention: 'Intervention') -> Tuple[bool, List[str]]:
        """验证干预是否合理"""
        issues = []

        # 检查 1：练习型干预必须有"难度匹配"
        if intervention.intervention_type == InterventionType.PRACTICE:
            if intervention.difficulty > 0.8 and not intervention.scaffolding_level:
                issues.append("高难度练习缺少 scaffolding")

        # 检查 2：讲解型干预必须有"概念明确"
        if intervention.intervention_type == InterventionType.EXPLANATORY:
            if not intervention.target_skills:
                issues.append("讲解型干预缺少目标技能")

        # 检查 3：元认知型干预不能太频繁（防止负担）
        if intervention.intervention_type == InterventionType.METACOGNITIVE:
            if intervention.quantity > 1:
                issues.append("元认知干预数量过多，可能造成负担")

        # 检查 4：避免认知超载
        if intervention.feedback_density > 0.8 and intervention.scaffolding_level > 0.8:
            issues.append("反馈密度 + scaffolding 同时过高，可能认知超载")

        return len(issues) == 0, issues
```

### 4.3 机制 3：L4 因果归因强制

[01-cta-belief-engine.md §7 L4 因果归因](../10-engineering/01-cta-belief-engine.md) 已实现。这里强调"强制"——任何干预效果都必须经因果归因：

```python
# ecos/dual_agent/anti_hallucination/causal_attribution.py
class CausalAttributionEnforcer:
    """强制因果归因——不允许"只看相关性"的下结论"""

    @staticmethod
    def enforce_attribution(
        lca_result: 'CalibratedLCAResult',
        next_observation: 'Observation',
    ) -> 'CalibratedLCAResult':
        """强制填充 causal_effect 字段"""
        if lca_result.actual_outcome is None:
            # 实际结果未观测，跳过本次归因
            return lca_result

        if lca_result.causal_effect is None:
            # 必须做因果归因（不能仅看相关性）
            raise ValueError(
                f"干预 {lca_result.intervention.intervention_id} 缺少因果归因——"
                f"必须调用 CTA L4 Causal Inference 计算 ATE/CATE"
            )

        return lca_result

    @staticmethod
    def is_significant(causal_effect: 'CausalEffect', alpha: float = 0.05) -> bool:
        """判断因果效果是否统计显著"""
        return causal_effect.p_value < alpha
```

### 4.4 人工审核触发

[04-risks.md §A4 缓解策略](../00-overview/04-risks.md)：当 CTA 置信度 < 0.6，自动转人工。

```python
# ecos/dual_agent/anti_hallucination/human_review.py
class HumanReviewTrigger:
    """人工审核触发——置信度低于阈值时"""

    def __init__(self, config: HumanReviewConfig):
        self.config = config

    def should_request_human_review(
        self,
        cta_output: 'CalibratedCTAOutput',
    ) -> Tuple[bool, Optional['HumanReviewRequest']]:
        """判断是否应请求人工审核"""
        # 触发条件 1：整体置信度过低
        if cta_output.belief_state.overall_confidence < self.config.confidence_threshold:
            return True, HumanReviewRequest(
                student_id=cta_output.student_id,
                reason="CTA 整体置信度过低",
                priority="high",
                belief_state_snapshot=cta_output.belief_state,
            )

        # 触发条件 2：信念分布合理性检查失败
        from .belief_check import BeliefDistributionCheck
        is_well_formed, issues = BeliefDistributionCheck.is_well_formed(cta_output.belief_state)
        if not is_well_formed:
            return True, HumanReviewRequest(
                student_id=cta_output.student_id,
                reason=f"信念分布不合理: {issues}",
                priority="critical",
                belief_state_snapshot=cta_output.belief_state,
            )

        # 触发条件 3：连续 3 次干预无效
        if self._consecutive_ineffective(cta_output.student_id):
            return True, HumanReviewRequest(
                student_id=cta_output.student_id,
                reason="连续 3 次干预无显著效果",
                priority="high",
            )

        return False, None

    def _consecutive_ineffective(self, student_id: str) -> bool:
        """检查连续 3 次干预无效"""
        # 从 persistence 层查询最近 3 次干预效果
        # 简化：返回 False（实际实现查询数据库）
        return False
```

---

## 5. 死锁避免

### 5.1 超时保护

```python
# ecos/dual_agent/deadlock/timeout.py
import time
from contextlib import contextmanager

class TimeoutGuard:
    """互校循环超时保护"""

    def __init__(self, default_timeout_sec: int = 30):
        self.default_timeout = default_timeout_sec

    @contextmanager
    def timeout(self, seconds: int = None):
        """超时上下文"""
        seconds = seconds or self.default_timeout
        start = time.time()
        try:
            yield
        finally:
            elapsed = time.time() - start
            if elapsed > seconds:
                raise TimeoutError(f"互校操作超过 {seconds} 秒")

# 使用
with timeout_guard.timeout(5):
    cta_output = cta.update(observation)
```

### 5.2 优先级仲裁

```python
# ecos/dual_agent/deadlock/priority.py
class PriorityArbitrator:
    """优先级仲裁——多个互校消息竞争时"""

    PRIORITY_LEVELS = {
        MessageType.HUMAN_REVIEW_REQUEST: 3,  # 最高
        MessageType.META_REFLECTION: 2,
        MessageType.BELIEF_CHALLENGE: 1,
        MessageType.STRATEGY_CHALLENGE: 1,
        # 常态循环优先级 0
    }

    @classmethod
    def arbitrate(cls, messages: List['CalibrationMessage']) -> 'CalibrationMessage':
        """选择优先级最高的消息"""
        if not messages:
            raise ValueError("无消息可仲裁")
        return max(messages, key=lambda m: (
            cls.PRIORITY_LEVELS.get(m.message_type, 0),
            m.priority,
            -m.timestamp,  # 同优先级时，先进先出
        ))
```

### 5.3 降级到单 Agent

[04-risks.md §A1 应急预案](../00-overview/04-risks.md)：若双 Agent 不可行 → 退化为单 Agent + 人工审核层。

```python
# ecos/dual_agent/deadlock/fallback.py
class SingleAgentFallback:
    """降级到单 Agent 模式"""

    def __init__(self, cta: 'CTAOrchestrator', lca: 'LCAOrchestrator'):
        self.cta = cta
        self.lca = lca

    def run_degraded(
        self,
        observation: 'Observation',
    ) -> 'LCAResult':
        """降级模式——不经过双 Agent 互校"""
        # Step 1: CTA 估计
        cta_output = self.cta.update(observation)
        # Step 2: 直接 LCA 选择（无互校）
        lca_result = self.lca.select_intervention(cta_output)
        # Step 3: 标记为"降级模式"，便于人工审核
        lca_result.degraded_mode = True
        lca_result.metadata['fallback_reason'] = "互校循环超时或失败"
        return lca_result

    def should_fallback(self, error_count: int, time_elapsed_sec: float) -> bool:
        """判断是否应降级"""
        # 条件 1：连续 3 次错误
        if error_count >= 3:
            return True
        # 条件 2：单次互校超过 60 秒
        if time_elapsed_sec > 60:
            return True
        return False
```

---

## 6. 互校循环主流程编排

```python
# ecos/dual_agent/orchestrator.py
class DualAgentOrchestrator:
    """双 Agent 互校主流程编排"""

    def __init__(self, config: DualAgentConfig):
        self.cta = CTAOrchestrator(config.cta)
        self.lca = LCAOrchestrator(config.lca)
        self.state_machine = CalibrationStateMachine()
        # 4 个交互模式
        self.normal_cycle = NormalCycle(self.cta, self.lca, self.state_machine)
        self.belief_challenge = BeliefChallengeMode(self.cta, self.lca)
        self.strategy_challenge = StrategyChallengeMode(self.cta, self.lca)
        self.meta_reflection = MetaReflectionMode(self.cta, self.lca)
        # 抗幻觉 + 死锁保护
        self.belief_check = BeliefDistributionCheck()
        self.experiment_validator = ExperimentDesignValidator()
        self.human_review = HumanReviewTrigger(config.human_review)
        self.timeout_guard = TimeoutGuard()
        self.fallback = SingleAgentFallback(self.cta, self.lca)
        # 状态
        self.intervention_history: Dict[str, List['CalibratedLCAResult']] = {}
        self.state_trajectory: Dict[str, List['BeliefState']] = {}

    def process_observation(
        self,
        observation: 'Observation',
    ) -> 'CalibratedLCAResult':
        """处理一次观测——主入口"""
        student_id = observation.student_id

        # Step 0: 检查是否应触发特殊模式
        special_mode = self._check_special_modes(student_id, observation)
        if special_mode:
            return special_mode

        # Step 1: 常态循环（带超时保护）
        try:
            with self.timeout_guard.timeout(seconds=30):
                # 获取上一次 LCA 结果（用于因果归因）
                previous_lca = self._get_last_lca_result(student_id)

                # 执行常态循环
                lca_result = self.normal_cycle.run(observation, previous_lca)

                # 抗幻觉检查
                self._anti_hallucination_checks(lca_result, observation)

                # 记录历史
                self._record_history(student_id, lca_result)

                return lca_result

        except TimeoutError:
            # 超时降级
            return self.fallback.run_degraded(observation)

    def _check_special_modes(
        self,
        student_id: str,
        observation: 'Observation',
    ) -> Optional['CalibratedLCAResult']:
        """检查是否应触发特殊模式"""
        # 检查策略质疑
        history = self.intervention_history.get(student_id, [])
        trajectory = self.state_trajectory.get(student_id, [])

        if self.strategy_challenge.detect_ineffective_intervention(
            student_id, history, trajectory
        ):
            # 触发策略质疑
            challenge = self.strategy_challenge.challenge_lca(
                student_id,
                ineffective_intervention_type=history[-1].intervention.intervention_type.value,
                proposed_alternative="切换干预类型或降低目标 Bloom 层",
            )
            return self.strategy_challenge.lca_revise_policy(challenge, self.lca)

        # 检查元反思
        if self.meta_reflection.detect_stagnation(student_id, trajectory):
            return self.meta_reflection.run_meta_reflection(
                student_id, trajectory, history
            )

        return None

    def _anti_hallucination_checks(
        self,
        lca_result: 'CalibratedLCAResult',
        observation: 'Observation',
    ):
        """抗幻觉检查"""
        # 检查 1：信念分布合理性
        is_well_formed, issues = self.belief_check.is_well_formed(
            lca_result.intervention.belief_state
        )
        if not is_well_formed:
            raise ValueError(f"信念分布不合理: {issues}")

        # 检查 2：实验设计合理性
        is_valid, issues = self.experiment_validator.validate_intervention(
            lca_result.intervention
        )
        if not is_valid:
            raise ValueError(f"实验设计不合理: {issues}")

        # 检查 3：是否需要人工审核
        should_review, request = self.human_review.should_request_human_review(
            lca_result.intervention.belief_state
        )
        if should_review:
            self._queue_human_review(request)
```

---

## 7. 测试策略

### 7.1 单元测试（覆盖率 ≥ 80%）

| 模块 | 测试重点 | 覆盖率目标 |
|---|---|---|
| `protocol/messages.py` | 消息格式、JSON 序列化 | ≥ 90% |
| `protocol/state_machine.py` | 状态转移规则 | ≥ 95% |
| `modes/normal.py` | 常态循环 6 步骤 | ≥ 90% |
| `modes/belief_challenge.py` | 信念质疑触发 + 解决 | ≥ 85% |
| `modes/strategy_challenge.py` | 策略质疑 + 干预调整 | ≥ 85% |
| `modes/meta_reflection.py` | 停滞检测 + 反思报告 | ≥ 85% |
| `anti_hallucination/belief_check.py` | 信念分布检查 | ≥ 90% |
| `anti_hallucination/experiment_design.py` | 实验设计验证 | ≥ 90% |
| `deadlock/timeout.py` | 超时保护 | ≥ 90% |
| `deadlock/fallback.py` | 降级到单 Agent | ≥ 85% |

### 7.2 集成测试

```python
# ecos/dual_agent/tests/test_integration.py
def test_full_calibration_loop():
    """完整互校循环测试"""
    dual = DualAgentOrchestrator(config_for_test())

    for i in range(100):
        observation = generate_synthetic_observation(i)
        lca_result = dual.process_observation(observation)

        # 验证 LCAResult 字段
        assert lca_result.student_id == observation.student_id
        assert lca_result.intervention is not None
        assert lca_result.rationale is not None

    # 验证历史
    student_id = lca_result.student_id
    assert len(dual.intervention_history[student_id]) == 100

def test_belief_challenge_flow():
    """信念质疑流程测试"""
    dual = DualAgentOrchestrator(config_for_test())
    student_id = "S001"

    # 构造场景：CTA 高置信度但学生实际表现差
    for _ in range(10):
        # 高 mastery_prob 但不正确答案
        observation = generate_observation(student_id, correct=False, mastery_high=True)
        dual.process_observation(observation)

    # 应该触发信念质疑
    assert dual.belief_challenge_mode_active(student_id)

def test_strategy_challenge_flow():
    """策略质疑流程测试"""
    dual = DualAgentOrchestrator(config_for_test())
    student_id = "S001"

    # 构造场景：连续 5 次干预无效
    for _ in range(5):
        observation = generate_no_improvement_observation(student_id)
        dual.process_observation(observation)

    # 应该触发策略质疑
    assert dual.strategy_challenge_mode_active(student_id)
```

### 7.3 性能基准（对照 04-risks.md §A1 + §A4）

| 指标 | 阈值 | 测试场景 |
|---|---|---|
| **常态循环延迟** | P95 ≤ 5 秒 | 性能测试 |
| **互校循环总延迟** | P95 ≤ 10 秒 | 集成性能测试 |
| **接口错误率** | ≤ 0.1% | 长期运行 |
| **信念质疑触发准确率** | F1 ≥ 0.7 | 标注数据 |
| **策略质疑触发准确率** | F1 ≥ 0.6 | 标注数据 |
| **ECE（双 Agent 校准度）** | ≤ 0.10 | M3 实验 |
| **人工审核触发率** | ≤ 5% | 长期运行 |

### 7.4 关键测试场景

```python
def test_scenario_belief_challenge_resolved():
    """信念质疑成功解决"""
    # 设置 CTA 错误估计
    # 触发信念质疑
    # CTA 接收质疑 + 新证据 → 更新信念
    # 验证最终 CTA 信念与实际表现一致
    pass

def test_scenario_strategy_challenge_lca_adapts():
    """策略质疑成功——LCA 调整策略"""
    # 设置 LCA 连续无效干预
    # 触发策略质疑
    # LCA 调整策略空间
    # 验证后续干预有效
    pass

def test_scenario_meta_reflection_realignment():
    """元反思成功——双 Agent 重新对齐"""
    # 设置整体进步停滞
    # 触发元反思
    # 双 Agent 重新对齐目标
    # 验证后续进步恢复
    pass

def test_scenario_deadlock_timeout_fallback():
    """死锁超时降级"""
    # 模拟互校循环卡住
    # 触发超时保护
    # 降级到单 Agent 模式
    # 验证系统仍可用
    pass

def test_scenario_human_review_triggered():
    """人工审核触发"""
    # 设置 CTA 低置信度
    # 触发人工审核
    # 验证 human_review_queue 中有该学生
    pass
```

---

## 8. MVP 范围（Phase 4）

### 8.1 MVP 包含的组件

| 组件 | 实现状态 |
|---|---|
| 互校循环协议（消息格式 + version）| ✅ MVP |
| 互校状态机 | ✅ MVP |
| 4 个交互模式（常态 + 信念质疑 + 策略质疑 + 元反思）| ✅ MVP |
| 3 个抗幻觉机制（信念分布 + 实验设计 + 因果归因）| ✅ MVP |
| 人工审核触发（置信度阈值 + 信念合理性 + 连续无效）| ✅ MVP |
| 超时保护 + 优先级仲裁 + 单 Agent 降级 | ✅ MVP |

### 8.2 MVP 不包含的组件

- ❌ 异步互校（实时性优先，同步实现即可）
- ❌ 跨学生互校对比（Phase 5+）
- ❌ 自动学习互校模式选择（Phase 5+）

### 8.3 MVP 性能预算

| 操作 | 性能预算 |
|---|---|
| 一次互校循环 | ≤ 10 秒 |
| CTA 输出 | ≤ 3 秒 |
| LCA 选择 | ≤ 3 秒 |
| L4 因果归因 | ≤ 2 秒 |
| LLM 调用（rationale）| ≤ 3 秒 |
| 抗幻觉检查 | ≤ 1 秒 |

---

## 9. 关联文档

- **同级工程层**：
  - [01-cta-belief-engine.md](01-cta-belief-engine.md) — CTA 信念引擎（互校的"理解"端）
  - [02-lca-policy-engine.md](02-lca-policy-engine.md) — LCA 策略引擎（互校的"改变"端）
  - [03-bloom-goal-library.md](03-bloom-goal-library.md) — Bloom 目标库（共同语言）
  - [05-persistence-session.md](05-persistence-session.md) — 持久化（互校历史存储）
- **上层文档**：
  - [02-architecture.md §3.3 双 Agent 详细架构](../00-overview/02-architecture.md) — 本文档的架构依据
  - [03-roadmap.md §2.3 M3 假设验证](../00-overview/03-roadmap.md) — H3（双 Agent 互校抗幻觉）
  - [04-risks.md §A1 + §A4](../00-overview/04-risks.md) — 风险缓解策略
- **核心论证**：
  - [v2.0 §3.5 双 Agent 互校](../deep-research/Cognitive-Digital-Twin-Deep-Research.md) — 4 模式 + 3 机制 + 互校核心循环
  - [v0.3.0 CTA 数学基础 §4 POMDP](../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md) — POMDP 接口

---

## 10. 版本与维护

- **v1.0**（2026-06-25）— 初版

**待办（影响本文档时同步更新）**：
- 当 [05-persistence-session.md](05-persistence-session.md) 完成后，回填 §6 `_record_history` 的持久化细节
- 当 Phase 4 MVP 实验完成后，回填 §7.3 实际性能基准 vs 阈值

---

**创建日期**：2026-06-25
**维护者**：Bisen & Claude
