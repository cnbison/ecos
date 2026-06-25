# ZPD（最近发展区）在 ECOS 的应用（ZPD Application）

> **版本**：v1.0（2026-06-25）
> **性质**：教学法层第 4 份文档（最后 1 份）——Vygotsky ZPD 理论在 ECOS 中的形式化与工程实现
> **基于**：[01-k12-cognitive-structure.md](01-k12-cognitive-structure.md)、[02-bloom-application.md](02-bloom-application.md)、[03-learning-strategies.md](03-learning-strategies.md)、[v0.4.0 §3.1 Cognitive Apprenticeship 6 阶段（Scaffolding 衰减）](../../research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md)、[02-lca-policy-engine.md §3.5 Scaffolding 衰减](../research/10-engineering/02-lca-policy-engine.md)、[v0.5.0 C 维度内容库（TC + Misconception）](../../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md)
> **后续**：教学法层全部完成后，启动 [90-mvp/](../90-mvp/)（Phase 0 最后 1 份）
> **维护者**：Bisen & Claude

---

## 0. 模块定位

### 0.1 ZPD 核心思想（Vygotsky 1978）

[Vygotsky 最近发展区理论](https://www.simplypsychology.org/vygotsky.html)：

> 学生有**实际发展区**（能独立完成的任务）和**潜在发展区**（在帮助下能完成的任务），两者之间的差距叫**最近发展区（ZPD）**。
> **教学应聚焦 ZPD**——既不是太简单（学生已掌握），也不是太难（超出能力）。

```
实际发展区                ZPD（教学目标）         潜在发展区
─────────────────────────────────────────────────────────→
已掌握任务                                          在帮助下能完成
        ↑               ↑                ↑
    太简单           教学应聚焦        太难
```

### 0.2 ECOS 中 ZPD 的实现位置

```
┌─────────────────────────────────────────────────────────────┐
│ ZPD 在 ECOS（本文档）—— 教学法核心                            │
│   ↓ ZPD 形式化 + ZPD 突破检测                                │
│ CTA（[01-cta-belief-engine.md](../research/10-engineering/01-cta-belief-engine.md)）│
│   - 估计实际发展区（当前 5D + BloomProfile）                  │
│   - 估计潜在发展区（在 Bloom 目标下的能力上限）              │
│   ↓                                                            │
│ LCA（[02-lca-policy-engine.md](../research/10-engineering/02-lca-policy-engine.md)）│
│   - 选择 ZPD 内的干预（既不简单也不难）                       │
│   - Scaffolding 衰减（与 CA Stage 3 整合）                    │
│   ↓                                                            │
│ ZPD 突破检测（潜在 → 实际）                                  │
└─────────────────────────────────────────────────────────────┘
```

### 0.3 ZPD 与 ECOS 其他教学法理论的关系

| 教学法理论 | 与 ZPD 的关系 |
|---|---|
| [Cognitive Apprenticeship 6 阶段](https://en.wikipedia.org/wiki/Cognitive_apprenticeship) | Stage 3 Scaffolding 直接对应 ZPD 支持 |
| Bloom 跨层级教学 | ZPD 边界 = Bloom 目标层 |
| [v0.4.0 CLT 工作记忆负荷](../../research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md) | ZPD 内任务的负荷应符合学生 CLT 级别 |
| LearningDNA | ZPD 内的策略应个性化匹配 LearningDNA |
| Threshold Concepts | TC 跨越 = ZPD 突破的极端案例 |
| Misconceptions | Misconception 持续 = ZPD 收缩 |

---

## 1. ZPD 在 CTA 状态估计中的形式化

### 1.1 实际发展区估计（Actual Development Level, ADL）

**定义**：学生能独立完成的任务（不需要任何帮助）。

```python
@dataclass
class ActualDevelopmentLevel:
    """实际发展区——学生当前能独立完成的任务"""
    # 5D 状态（CTA BKT/MIRT 估计）
    knowledge: float          # K 维度（知识掌握度）
    procedure: float         # P 维度（程序技能）
    strategy: float          # S 维度（策略能力）
    confidence: float        # C 维度（含 misconception 折扣）
    external_support: float  # X 维度（外部支架依赖度，X 越低说明越独立）

    # BloomProfile（6 层当前掌握度）
    bloom_profile: BloomProfileState

    def can_independently_handle(
        self,
        bloom_target: BloomLevel,
        difficulty: float,
    ) -> bool:
        """判断学生是否能独立处理某任务"""
        # Bloom 层对应能力下限
        layer_mastery = getattr(self.bloom_profile, bloom_target.name.lower())
        # 难度匹配
        return layer_mastery >= difficulty and difficulty >= 0.3
```

### 1.2 潜在发展区估计（Potential Development Level, PDL）

**定义**：学生在帮助下能完成的任务（需要 scaffolding / 提示 / 同伴）。

```python
@dataclass
class PotentialDevelopmentLevel:
    """潜在发展区——学生在帮助下能完成的任务"""
    # 在最高 scaffold 下的能力估计
    knowledge_with_full_scaffold: float   # 完整 worked example 下的 K
    procedure_with_full_scaffold: float  # 完整示范下的 P

    # 与 Bloom 目标 + scaffolding 等级相关
    @staticmethod
    def estimate(
        adl: ActualDevelopmentLevel,
        learning_dna: 'LearningDNAState',
        bloom_target: BloomLevel,
        full_scaffold: bool = True,
    ) -> float:
        """
        估计潜在发展区（PDL）

        公式：PDL = ADL + 增量
        增量与以下因素相关：
        - 同伴支持（学习风格）
        - worked example 支持（CLT NOVICE）
        - 提示支持（CA Stage 3 Scaffolding）
        """
        base_increment = 0.2  # 基础增量 20%

        # 同伴支持增量
        if learning_dna.peer_preference:
            base_increment += 0.05

        # 完整 scaffold 增量
        if full_scaffold:
            base_increment += 0.10  # CLT NOVICE 显著提升

        # 元认知支持增量
        if learning_dna.metacognitive_aware:
            base_increment += 0.05

        return min(1.0, adl.__dict__[bloom_target.name.lower()] + base_increment)
```

### 1.3 ZPD 边界

```python
@dataclass
class ZPD:
    """最近发展区"""
    student_id: str
    bloom_target: BloomLevel

    # 三个关键值
    actual_level: float         # 实际发展区（ADL）能力估计
    zpd_lower: float           # ZPD 下界（比 ADL 略高）
    zpd_upper: float           # ZPD 上界（潜在发展区上限）
    potential_level: float     # 潜在发展区（PDL）能力估计

    # 边界计算
    @classmethod
    def compute(
        cls,
        student_id: str,
        bloom_target: BloomLevel,
        adl: ActualDevelopmentLevel,
        pdl: float,
    ) -> 'ZPD':
        actual = getattr(adl.bloom_profile, bloom_target.name.lower())
        zpd_lower = actual + 0.05  # ZPD 下界（比 ADL 略高 5%）
        zpd_upper = pdl - 0.05     # ZPD 上界（比 PDL 略低 5%）

        return cls(
            student_id=student_id,
            bloom_target=bloom_target,
            actual_level=actual,
            zpd_lower=zpd_lower,
            zpd_upper=zpd_upper,
            potential_level=pdl,
        )

    def is_in_zpd(self, difficulty: float) -> bool:
        """判断某任务难度是否在 ZPD 内"""
        return self.zpd_lower <= difficulty <= self.zpd_upper

    def get_recommended_difficulty(self) -> float:
        """获取推荐任务难度（ZPD 中位数）"""
        return (self.zpd_lower + self.zpd_upper) / 2
```

### 1.4 ZPD 的实时更新

```python
class ZPDUpdater:
    """ZPD 实时更新——基于 CTA 状态估计"""

    def __init__(self, cta: 'CTAOrchestrator'):
        self.cta = cta

    def update_zpd(
        self,
        student_id: str,
        bloom_target: BloomLevel,
    ) -> ZPD:
        """每次 CTA 状态更新后，重新计算 ZPD"""
        belief_state = self.cta.current_belief_state

        # 1. 估计 ADL
        adl = self._estimate_adl(belief_state)

        # 2. 估计 PDL
        pdl = self._estimate_pdl(adl, belief_state.learning_dna, bloom_target)

        # 3. 计算 ZPD
        return ZPD.compute(student_id, bloom_target, adl, pdl)
```

---

## 2. ZPD 在 LCA 干预选择中的应用

### 2.1 ZPD 内的任务选择原则

[LCA 引擎](../research/10-engineering/02-lca-policy-engine.md) 的干预选择必须考虑 ZPD：

```python
class ZPDAwareInterventionSelector:
    """ZPD 感知的干预选择器"""

    def select(
        self,
        student_id: str,
        belief_state: 'BeliefState',
        candidate_interventions: List['Intervention'],
    ) -> 'Intervention':
        """选择 ZPD 内的干预"""
        # 1. 计算 ZPD
        zpd = self.zpd_updater.update_zpd(
            student_id,
            candidate_interventions[0].bloom_target,
        )

        # 2. 过滤出 ZPD 内的候选
        zpd_candidates = [
            iv for iv in candidate_interventions
            if zpd.is_in_zpd(iv.difficulty)
        ]

        # 3. 如果 ZPD 内没有候选（任务过易或过难）→ 调整 Bloom 层
        if not zpd_candidates:
            # 任务过易 → 提升 Bloom 层
            if all(iv.difficulty < zpd.zpd_lower for iv in candidate_interventions):
                return self._select_higher_bloom(belief_state)
            # 任务过难 → 降低 Bloom 层或增加 scaffolding
            if all(iv.difficulty > zpd.zpd_upper for iv in candidate_interventions):
                return self._select_lower_bloom_or_more_scaffold(
                    belief_state, candidate_interventions
                )

        # 4. 在 ZPD 内按 LinUCB 选择最优
        return self.bandit.select(belief_state, zpd_candidates)

    def _select_higher_bloom(self, belief_state):
        """任务过易 → 提升 Bloom 层（如从 Apply 升到 Analyze）"""
        current = belief_state.bloom_profile.dominant_layer
        if current.value < BloomLevel.ANALYZE.value:
            return Intervention(
                intervention_type=InterventionType.INQUIRY,
                bloom_target=BloomLevel(current.value + 1),
                # ...
            )

    def _select_lower_bloom_or_more_scaffold(self, belief_state, candidates):
        """任务过难 → 降低 Bloom 层或增加 scaffolding"""
        # 默认：增加 scaffolding（CLT NOVICE 级别）
        return Intervention(
            intervention_type=candidates[0].intervention_type,
            bloom_target=BloomLevel(candidates[0].bloom_target.value - 1),
            clt_level=CLTLevel.NOVICE,  # 完整 worked example
            scaffolding_level=0.9,
        )
```

### 2.2 干预难度选择算法

```python
class InterventionDifficultySelector:
    """基于 ZPD 的干预难度选择"""

    def select_difficulty(
        self,
        zpd: ZPD,
        intervention_type: 'InterventionType',
        clt_level: 'CLTLevel',
    ) -> float:
        """选择干预难度"""
        # 基础：ZPD 中位数
        base_difficulty = zpd.get_recommended_difficulty()

        # 干预类型调整
        if intervention_type == InterventionType.EXPLANATORY:
            # 讲解型 → 略低（提供支持）
            base_difficulty -= 0.05
        elif intervention_type == InterventionType.INQUIRY:
            # 探究型 → 略高（挑战）
            base_difficulty += 0.05
        elif intervention_type == InterventionType.METACOGNITIVE:
            # 元认知型 → 中等（不过难）
            pass  # 保持基础

        # CLT 级别调整（与 [v0.4.0 §1.3 expertise reversal effect](../../research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md) 对齐）
        if clt_level == CLTLevel.NOVICE:
            # 新手 → 略低（完整 worked example）
            base_difficulty -= 0.10
        elif clt_level == CLTLevel.EXPERT:
            # 专家 → 略高（撤走支持）
            base_difficulty += 0.10

        # 限制在 ZPD 范围内
        return max(zpd.zpd_lower, min(zpd.zpd_upper, base_difficulty))
```

### 2.3 Scaffolding 衰减（与 [v0.4.0 §3.3 CA Stage 3 Scaffolding 衰减](../../research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md) 整合）

```python
class CAScaffoldingDecay:
    """Cognitive Apprenticeship Scaffolding 衰减——ZPD 突破后撤走支持"""

    def __init__(self, zpd_updater: ZPDUpdater, config: CAConfig):
        self.zpd_updater = zpd_updater
        self.config = config

    def update_scaffolding(
        self,
        student_id: str,
        current_scaffolding: float,
        consecutive_successes: int,
        bloom_target: BloomLevel,
    ) -> float:
        """更新 scaffolding 水平"""
        # 规则 1：连续成功 → 撤走支持（expertise reversal）
        if consecutive_successes >= self.config.fade_threshold:
            new_scaffolding = max(0.0, current_scaffolding - self.config.fade_step)
            return new_scaffolding

        # 规则 2：连续失败 → 增加支持（回到 ZPD 内部）
        if consecutive_successes <= -self.config.help_threshold:
            new_scaffolding = min(1.0, current_scaffolding + self.config.help_step)
            return new_scaffolding

        return current_scaffolding

    def should_break_zpd(
        self,
        student_id: str,
        bloom_target: BloomLevel,
    ) -> bool:
        """判断是否突破 ZPD（潜在 → 实际）"""
        # 获取当前 ZPD
        zpd = self.zpd_updater.update_zpd(student_id, bloom_target)

        # 检查学生是否已掌握 ZPD 上界
        adl = self.zpd_updater._estimate_adl(
            self.zpd_updater.cta.current_belief_state
        )
        adl_mastery = getattr(adl.bloom_profile, bloom_target.name.lower())

        # 如果 ADL 已达到原 ZPD 上界 → 突破
        return adl_mastery >= zpd.zpd_upper
```

---

## 3. ZPD 突破检测

### 3.1 突破的信号

**ZPD 突破 = 学生独立完成原本需要帮助的任务**：

```python
class ZPDBreakthroughDetector:
    """ZPD 突破检测"""

    def __init__(self, zpd_history: List[ZPD]):
        self.zpd_history = zpd_history

    def detect_breakthrough(
        self,
        student_id: str,
        bloom_target: BloomLevel,
        current_adl: ActualDevelopmentLevel,
    ) -> Optional['ZPDBreakthrough']:
        """检测 ZPD 突破"""
        if len(self.zpd_history) < 2:
            return None

        # 取最近 2 次 ZPD 比较
        prev_zpd = self.zpd_history[-2]
        curr_zpd = self.zpd_history[-1]

        # 突破条件：当前 ADL 已达原 ZPD 上界
        curr_adl_mastery = getattr(
            current_adl.bloom_profile, bloom_target.name.lower()
        )
        prev_zpd_upper = prev_zpd.zpd_upper

        if curr_adl_mastery >= prev_zpd_upper:
            return ZPDBreakthrough(
                student_id=student_id,
                bloom_target=bloom_target,
                timestamp=datetime.now(),
                prev_zpd_upper=prev_zpd_upper,
                curr_adl_mastery=curr_adl_mastery,
                improvement=curr_adl_mastery - prev_zpd_upper,
            )
        return None

    def detect_regression(
        self,
        student_id: str,
        bloom_target: BloomLevel,
        current_adl: ActualDevelopmentLevel,
    ) -> Optional['ZPDRegression']:
        """检测 ZPD 收缩（退步）"""
        # 与 detect_breakthrough 类似但方向相反
        pass
```

### 3.2 突破的归因

[01-cta-belief-engine.md §7 L4 因果归因](../research/10-engineering/01-cta-belief-engine.md) 整合：

```python
class BreakthroughAttribution:
    """ZPD 突破的因果归因"""

    def __init__(self, cta_l4: 'ABTestAttributor'):
        self.cta_l4 = cta_l4

    def attribute_breakthrough(
        self,
        breakthrough: 'ZPDBreakthrough',
        intervention_history: List['CalibratedLCAResult'],
    ) -> Dict[str, float]:
        """归因 ZPD 突破的原因"""
        # 取最近 5 次干预
        recent = intervention_history[-5:]

        # 计算每种干预对突破的贡献
        contributions = {}
        for iv in recent:
            # 该干预的 state_delta
            if iv.actual_state_delta and iv.actual_state_delta > 0.1:
                # 因果归因（ATE）
                causal = self.cta_l4.attribute(
                    intervention_type=iv.intervention.intervention_type.value,
                    student_id=breakthrough.student_id,
                    state_delta=iv.actual_state_delta,
                    is_control=False,
                )
                contributions[iv.intervention.intervention_type.value] = causal.ate

        return contributions
```

### 3.3 突破的可视化

**家长/教师端展示**：

```
张三的 ZPD 突破（最近 30 天）
─────────────────────────────
二次函数 L3 Apply
  30 天前：ADL 0.55, ZPD [0.60, 0.85]
  今天：ADL 0.88 ★ 突破！
  归因：
    变式练习 (40%)
    工作ed example (35%)
    自我解释 (25%)
```

---

## 4. ZPD 与 Bloom 层级结合

### 4.1 BloomProfile × ZPD 联合建模

```python
class BloomZPDModel:
    """Bloom × ZPD 联合建模"""

    def __init__(self, zpd_updater: ZPDUpdater):
        self.zpd_updater = zpd_updater

    def get_zpd_for_each_layer(
        self,
        student_id: str,
        belief_state: 'BeliefState',
    ) -> Dict[BloomLevel, ZPD]:
        """为每个 Bloom 层计算 ZPD"""
        zpds = {}
        for layer in BloomLevel:
            if layer.value > BloomLevel.ANALYZE.value:
                continue  # 小学/初中跳过 L5-L6
            zpd = self.zpd_updater.update_zpd(student_id, layer)
            zpds[layer] = zpd
        return zpds

    def find_optimal_layer(
        self,
        zpds: Dict[BloomLevel, ZPD],
        available_difficulty: float,
    ) -> Optional[BloomLevel]:
        """找到最优 Bloom 层（任务难度匹配的层）"""
        for layer, zpd in sorted(zpds.items()):
            if zpd.is_in_zpd(available_difficulty):
                return layer
        return None
```

### 4.2 各 Bloom 层的 ZPD 特征

| Bloom 层 | ZPD 宽度 | 突破难度 | ECOS 建议 |
|---|---|---|---|
| **L1 Remember** | 窄（0.05-0.10）| 低 | 快速突破（无需重点关注）|
| **L2 Understand** | 中（0.10-0.15）| 中 | 通过类比 + 自我解释突破 |
| **L3 Apply** | 中（0.10-0.15）| 中 | 通过变式练习突破 |
| **L4 Analyze** | **宽（0.15-0.20）** | **高（核心难点）** | **重点突破**（拆解 + Articulation）|
| **L5 Evaluate** | 中（0.10-0.15）| 高 | 通过议论文 + peer review |
| **L6 Create** | 宽（0.15-0.25）| 极高 | 通过项目式学习（Phase 5+）|

**L4 Analyze ZPD 宽度最大**——这是中国学生最难突破的层级，应给予最多教学资源。

---

## 5. ZPD 在不同学段的差异

### 5.1 小学 ZPD（窄）

**特征**：
- ZPD 宽度窄（0.05-0.10）—— 学生能力提升缓慢
- 突破频率低（每月 0.5-1 次）
- 需要密切监控（学习障碍早发现）

**ECOS 建议**：
- 任务难度严格控制在 ZPD 内
- 频繁评估（每周）
- 家长参与决策（X 维度高依赖）

### 5.2 初中 ZPD（中）

**特征**：
- ZPD 宽度中等（0.10-0.15）
- 突破频率中等（每月 1-3 次）
- 抽象思维 ZPD 出现（变量/函数/证明）

**ECOS 建议**：
- 强推 L3→L4 进阶（核心难点）
- 月度评估
- 关注 TC 跨越信号（liminal 预警）

### 5.3 高中 ZPD（宽）

**特征**：
- ZPD 宽度宽（0.15-0.25）
- 突破频率高（每月 3-5 次）
- 自适应能力增强（学习者调节）

**ECOS 建议**：
- 任务可适度挑战（超出 ZPD 但不超 PDL）
- 季度评估（充分时间积累）
- 培养自主学习（元认知策略）

---

## 6. ZPD 与学习障碍识别

[04-risks.md §B 学习障碍识别](../research/00-overview/04-risks.md) 是关键风险。

### 6.1 学习障碍的信号

```python
class LearningDisabilityDetector:
    """学习障碍检测——基于 ZPD 持续未突破"""

    def __init__(self, zpd_history: List[ZPD], config: LDConfig):
        self.zpd_history = zpd_history
        self.config = config

    def detect(
        self,
        student_id: str,
        bloom_target: BloomLevel,
    ) -> Optional['LearningDisabilityAlert']:
        """检测学习障碍"""
        if len(self.zpd_history) < self.config.history_window:
            return None

        # 取最近 history_window 个 ZPD
        recent = self.zpd_history[-self.config.history_window:]

        # 条件 1：ZPD 持续未突破（无显著进步）
        adl_progress = recent[-1].actual_level - recent[0].actual_level
        if adl_progress < self.config.min_progress:
            # 条件 2：Scaffolding 持续高（学生高度依赖）
            # 条件 3：连续失败 ≥ N 次
            # ...（省略）

            return LearningDisabilityAlert(
                student_id=student_id,
                bloom_target=bloom_target,
                severity='high',
                recommendation='人工审核 + 教学干预调整',
            )
        return None
```

### 6.2 ZPD 持续未突破的诊断

```
诊断流程：

学生 ZPD 持续 8 周未突破
        ↓
Level 1：暂时困难？
  - 最近是否有生病 / 家庭问题？
  - 是否缺乏学习时间？
  - → 暂时困难，无需特殊干预

Level 2：misconception 未检测？
  - [v0.5.0 Misconception 检测](03-c-dimension-content-libraries.md) F1 ≥ 0.7？
  - → 如有 misconception，调整干预

Level 3：策略不当？
  - 当前 LCA 推荐策略是否合适？
  - → 调整策略

Level 4：学习障碍？
  - 持续 ≥ 12 周未突破
  - 多学科同时受影响
  - → 人工审核 + 专业评估
```

### 6.3 学习障碍 vs 暂时困难

| 维度 | 暂时困难 | 学习障碍 |
|---|---|---|
| 持续时间 | < 4 周 | > 12 周 |
| 多学科影响 | 单学科 | 多学科 |
| Scaffolding 依赖 | 短暂高 | 持续高 |
| 归因 | 外部（生病/家庭）| 内部（神经/认知）|
| ECOS 响应 | 等待恢复 + 监测 | 人工审核 + 专业评估 |

---

## 7. ZPD 与 TC / Misconception 库的关联

### 7.1 TC 跨越与 ZPD 突破

[v0.5.0 C 维度内容库 §1 Threshold Concepts](../../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md)：

```
TC 跨越 = ZPD 突破的极端案例

学生卡在 TC liminal 状态
        ↓
ZPD 上界 = TC 跨越后的能力（潜在发展区）
ZPD 下界 = TC 跨越前的能力（实际发展区）
        ↓
TC 跨越成功 = ZPD 突破到更高层次（认知结构永久改变）
```

**ECOS 行动**：
- TC 跨越检测 → ZPD 重新计算
- 跨越成功后 → BloomProfile 自动 +0.1（[03-bloom-goal-library.md §8.1 TC 集成](../research/10-engineering/03-bloom-goal-library.md)）
- Scaffolding 完全撤走（不可逆）

### 7.2 Misconception 与 ZPD 收缩

```
学生有 misconception
        ↓
实际发展区 ADL 被"伪置信"拉高（如认为自己掌握 L3，实际只能 L2）
        ↓
ZPD 边界错误（基于伪置信估计）
        ↓
LCA 推荐过难任务 → 学生反复失败 → ZPD 收缩
        ↓
[04-risks.md §B4 学习障碍风险](../research/00-overview/04-risks.md)
```

**ECOS 行动**：
- [v0.5.0 §3 C 维度内容库](../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md) 集成：misconception 检测 → C 维度 × 0.7（伪置信折扣）
- ZPD 重新计算（基于真实 ADL）
- 避免错误推荐

---

## 8. ECOS ZPD 可视化与家长沟通

### 8.1 学生端可视化

```
张三的认知发展（最近 30 天）
─────────────────────────────────────
            ADL（实际）  ZPD       PDL（潜在）
二次函数 L3  0.55  →  [0.60-0.85]  ← 0.88  ★ 突破！
            ↑             ↑             ↑
          ZPD 下界      ZPD 中位数      ZPD 上界
```

### 8.2 家长沟通

**给家长的解释**（简化版）：

> "张三最近 30 天在二次函数的'应用'层级（ZPD 内 [0.60, 0.85]）取得突破，**实际能力从 0.55 提升到 0.88**——超过原 ZPD 上界。这是显著进步。
>
> ECOS 推荐的下一步任务：继续保持 L3 巩固，同时尝试'分析'层级（L4 拆解）的入门任务。"

### 8.3 教师沟通

**给教师的解释**（完整版）：

> "张三的 ZPD 突破归因：
> - 变式练习（ATE 0.18，p < 0.01）
> - 工作ed example（ATE 0.16，p < 0.01）
> - 自我解释（ATE 0.11，p < 0.05）
>
> 建议下一步干预：增加 INQUIRY（探究型）干预，目标 L4 Analyze。"

---

## 9. 评估指标（对照 04-risks.md §B4）

| 指标 | 阈值 | 测试场景 |
|---|---|---|
| **任务难度在 ZPD 内比例** | ≥ 80% | 推荐干预分布 |
| **ZPD 突破频率** | 每月 ≥ 1 次（小学）/ ≥ 3 次（高中）| 长期追踪 |
| **学习障碍检测 F1** | ≥ 0.7 | 标注数据 |
| **ZPD 收缩检测 F1** | ≥ 0.6 | misconception 案例 |
| **Scaffolding 衰减准确率** | ≥ 80% | 教师审核 |

---

## 10. 教学法层全部完成 🎉

```
✅ 01-k12-cognitive-structure.md （v0.15.0，516 行）
✅ 02-bloom-application.md        （v0.16.0，564 行）
✅ 03-learning-strategies.md      （v0.17.0，575 行）
✅ 04-zpd-application.md          （v0.18.0，[TBD] 行）★
────────────────────────────────────────────────
教学法层 4 份全部完成 ✅
```

## 11. 关联文档

- **同级教学法层**：
  - [01-k12-cognitive-structure.md](01-k12-cognitive-structure.md) — K12 学段差异化
  - [02-bloom-application.md](02-bloom-application.md) — Bloom 跨层级策略
  - [03-learning-strategies.md](03-learning-strategies.md) — 学习策略空间
- **P0 借鉴**（理论依据）：
  - [v0.4.0 §3.1 Cognitive Apprenticeship 6 阶段](../../research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md) — Scaffolding 与 ZPD 整合
  - [v0.5.0 C 维度内容库 §1.3 Liminality + §2.3](../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md) — TC 跨越 + Misconception 与 ZPD 关联
- **工程层**（按本文档实现）：
  - [01-cta-belief-engine.md](../research/10-engineering/01-cta-belief-engine.md) — CTA 引擎（ZPD 计算）
  - [02-lca-policy-engine.md](../research/10-engineering/02-lca-policy-engine.md) — LCA 引擎（ZPD 内的干预选择）
- **上层文档**：
  - [02-architecture.md §3.2 LCA 设计](../research/00-overview/02-architecture.md) — 工程实现依据
  - [04-risks.md §B4 学习障碍](../research/00-overview/04-risks.md) — 风险评估
- **核心论证**：
  - Vygotsky 1978. *Mind in Society*. Harvard University Press.
  - [v0.1 综合报告 §第八部分 Bloom](../research/gpt-dialogues/04-cognitive-digital-twin-v01-report.md) — Bloom 分类学

---

## 12. 版本与维护

- **v1.0**（2026-06-25）— 初版（**教学法层最后 1 份**）

**待办（影响本文档时同步更新）**：
- 当 [90-mvp/README.md](../90-mvp/README.md) 完成后，§2 ZPD 集成到 MVP 设计
- 当 Phase 4 MVP 实验完成后，回填 §9 评估指标的实际效果

---

**创建日期**：2026-06-25
**维护者**：Bisen & Claude
