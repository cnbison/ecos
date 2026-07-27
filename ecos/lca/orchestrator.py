"""LCA 主流程编排——L3-L4 教学法栈 + Contextual Bandits.

对应：
  - research/10-engineering/02-lca-policy-engine.md §6 LCAOrchestrator
  - research/00-overview/02-architecture.md §6 双 Agent 互校接口

主入口：
    LCAEngine(config=LCAEngineConfig()).select_intervention(cta_input)
    LCAEngine(config=LCAEngineConfig()).update(student_id, intervention, new_state, reward)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from ..cta.belief_state import BeliefState, BloomLevel, LearningDNAState
from ..llm_client import ECOSLLMClient
from .intervention import (
    CAStage,
    CLTLevel,
    Intervention,
    InterventionType,
    select_bloom_target,
)
from .l3_selection import (
    AdaptiveCLTPresender,
    BjorkSpacingEffect,
    BjorkTestingEffect,
    CAConfig,
    CLTConfig,
    CAScaffoldingDecay,
)
from .l4_optimization import (
    BanditConfig,
    CAStateMachine,
    CTA_L4_Backend,
    LCAAttribution,
    LCAPolicyLearner,
)
from .rationale import RationaleGenerator


# ---------------------------------------------------------------------------
# LCA Input / Output 数据结构
# ---------------------------------------------------------------------------

@dataclass
class CTAInput:
    """LCA 接收的 CTA 输出（M2 W2 简化版）.

    Attributes:
        student_id:              学生 ID
        belief_state:            CTA 估计的 BeliefState
        bloom_target_candidates: 候选 Bloom 层（默认全 6 层）
        skill_filter:            可选——只针对特定技能列表
        timestamp:               时间戳
    """

    student_id: str
    belief_state: BeliefState
    bloom_target_candidates: Optional[List[BloomLevel]] = None
    skill_filter: Optional[List[str]] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class LCAResult:
    """LCA 输出（完整版——与 CTA belief_engine.py 占位 LCAResult 区分）.

    这个 LCAResult 是 LCA → App 层的契约。

    Attributes:
        student_id:    学生 ID
        intervention:  选中的干预
        rationale:     自然语言理由（LLM 生成或 fallback）
        expected_gain: 期望状态增量（用于 App 层 + 教师后台接口）
        expected_risk: 期望风险（Frustration 概率）
        bloom_target:  选中的目标 Bloom 层
        clt_level:     CLT 呈现级别
        ca_stage:      CA 阶段
        timestamp:     时间戳
    """

    student_id: str
    intervention: Intervention
    rationale: str
    expected_gain: float
    expected_risk: float
    bloom_target: BloomLevel
    clt_level: CLTLevel
    ca_stage: CAStage
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """序列化为 dict（持久化 + 教师后台接口使用）."""
        return {
            "student_id": self.student_id,
            "intervention": self.intervention.to_dict(),
            "rationale": self.rationale,
            "expected_gain": self.expected_gain,
            "expected_risk": self.expected_risk,
            "bloom_target": self.bloom_target.name,
            "clt_level": self.clt_level.name,
            "ca_stage": self.ca_stage.name,
            "timestamp": self.timestamp.isoformat(),
        }


# ---------------------------------------------------------------------------
# 候选干预生成（02-lca §6 step 5）
# ---------------------------------------------------------------------------

# 默认候选池（5 类型 × 2 难度 = 10 arm，对应 default n_arms=10）
DEFAULT_CANDIDATE_TYPES = [
    InterventionType.EXPLANATORY,
    InterventionType.EXPLANATORY,
    InterventionType.PRACTICE,
    InterventionType.PRACTICE,
    InterventionType.INQUIRY,
    InterventionType.FEEDBACK,
    InterventionType.METACOGNITIVE,
    InterventionType.EXPLANATORY,
    InterventionType.PRACTICE,
    InterventionType.INQUIRY,
]
DEFAULT_CANDIDATE_DIFFICULTIES = [0.3, 0.5, 0.4, 0.6, 0.5, 0.4, 0.5, 0.7, 0.7, 0.7]


def _generate_candidates(
    bloom_target: BloomLevel,
    clt_level: CLTLevel,
    ca_stage: CAStage,
    bjork_triggers: List[str],
    cta_input: CTAInput,
    skill_filter: Optional[List[str]] = None,
    n_candidates: int = 10,
) -> List[Intervention]:
    """生成 LCA 候选干预池.

    根据 bloom_target / clt_level / ca_stage / bjork_triggers 自动调整参数：
    - bjork trigger "test" → 倾向于 INQUIRY（Teach-back / self-explanation）
    - bjork trigger "space" → 间隔复习模式（lower quantity + spacing）
    - ca_stage = MODELING → EXPLANATORY 主导（演示）
    - ca_stage = COACHING → PRACTICE 主导
    - ca_stage = SCAFFOLDING → EXPLANATORY + 高 scaffolding
    """
    candidates: List[Intervention] = []
    target_skills = skill_filter or []
    # 取 bloom 标签作为 target_tcs 占位（Phase 4+ 接 Q-Matrix）
    target_tcs = [bloom_target.name.lower()]

    for i in range(n_candidates):
        itype = DEFAULT_CANDIDATE_TYPES[i % len(DEFAULT_CANDIDATE_TYPES)]
        difficulty = DEFAULT_CANDIDATE_DIFFICULTIES[i % len(DEFAULT_CANDIDATE_DIFFICULTIES)]

        # CA 阶段调整干预类型
        if ca_stage == CAStage.MODELING and i % 3 != 0:
            itype = InterventionType.EXPLANATORY
        elif ca_stage == CAStage.COACHING:
            if itype not in (InterventionType.PRACTICE, InterventionType.FEEDBACK):
                itype = InterventionType.PRACTICE
        elif ca_stage == CAStage.SCAFFOLDING:
            if itype not in (InterventionType.EXPLANATORY, InterventionType.METACOGNITIVE):
                itype = InterventionType.EXPLANATORY

        # Bjork 触发调整
        bjork = list(bjork_triggers)
        if "test" in bjork and itype == InterventionType.INQUIRY:
            # 强化测试效应
            bjork.append("retrieval")
        if "space" in bjork:
            # 间隔模式：更低难度 + 更高 feedback
            difficulty = min(difficulty, 0.5)

        # scaffolding_level 与 CLTLevel 对齐
        scaffolding = {
            CLTLevel.NOVICE: 0.9,
            CLTLevel.DEVELOPING: 0.6,
            CLTLevel.PROFICIENT: 0.3,
            CLTLevel.EXPERT: 0.1,
        }[clt_level]

        # quantity 调整
        quantity = {
            InterventionType.EXPLANATORY: 3,
            InterventionType.PRACTICE: 8,
            InterventionType.INQUIRY: 5,
            InterventionType.FEEDBACK: 4,
            InterventionType.METACOGNITIVE: 3,
        }[itype]

        feedback_density = 0.8 if clt_level != CLTLevel.EXPERT else 0.4

        intervention = Intervention(
            intervention_type=itype,
            bloom_target=bloom_target,
            target_skills=target_skills[:3],
            # Phase 5+ 接 TC 容器：当前用空 list（M2 W2 不阻塞）
            target_misconceptions=[],
            target_tcs=target_tcs,
            difficulty=difficulty,
            quantity=quantity,
            feedback_density=feedback_density,
            scaffolding_level=scaffolding,
            clt_level=clt_level,
            ca_stage=ca_stage,
            bjork_triggers=bjork,
            expected_gain=0.0,  # 由 LCA 在 select 阶段补全
            expected_risk=0.0,
        )
        candidates.append(intervention)
    return candidates


# ---------------------------------------------------------------------------
# LCA Engine 主类
# ---------------------------------------------------------------------------

@dataclass
class LCAEngineConfig:
    """LCA Engine 配置."""

    clt_config: CLTConfig = field(default_factory=CLTConfig)
    ca_config: CAConfig = field(default_factory=CAConfig)
    bandit_config: BanditConfig = field(default_factory=BanditConfig)
    use_llm_rationale: bool = True
    rationale_audience: str = "student"  # 默认 student
    expected_gain_scale: float = 0.3    # expected_gain = scale × (1 - mastery)


class LCAEngine:
    """LCA 主引擎——L3-L4 教学法栈 + Contextual Bandits + Rationale.

    用法：
        engine = LCAEngine(config=LCAEngineConfig(), llm_client=client)
        result = engine.select_intervention(cta_input)
        # 观测到 reward 后
        engine.update(student_id, result.intervention, new_state, reward)
    """

    def __init__(
        self,
        config: Optional[LCAEngineConfig] = None,
        llm_client: Optional[ECOSLLMClient] = None,
    ):
        self.config = config or LCAEngineConfig()

        # L3 组件
        self.clt = AdaptiveCLTPresender(self.config.clt_config)
        self.bjork_testing = BjorkTestingEffect()
        self.bjork_spacing = BjorkSpacingEffect()
        self.ca_scaffolding = CAScaffoldingDecay(self.config.ca_config)

        # L4 组件
        self.ca_state_machine = CAStateMachine()
        # v0.57.0: per-student bandit 改造 (修复 v0.56.0 单 bandit 多学生数据冲突 BUG)
        #   之前 self.bandit 是单 bandit 全局共享, lbc001 + lbc002 答题会互相污染 LinUCB 状态
        #   现在 self.bandits[student_id] 隔离 per-student
        self.bandits: Dict[str, "LCAPolicyLearner"] = {}
        self.attribution = LCAAttribution(CTA_L4_Backend())

        # Rationale（按 config 决定是否接 LLM）
        rationale_client = llm_client if self.config.use_llm_rationale else None
        self.rationale_gen = RationaleGenerator(rationale_client)

        # 当前干预历史（M2 W2 用内存；Phase 5+ 接入 persistence）
        self.intervention_history: Dict[str, List[Intervention]] = {}

        # v0.57.0: per-student select_count / update_count (持久化)
        self._select_count: Dict[str, int] = {}
        self._update_count: Dict[str, int] = {}
        # v0.57.0: per-student last_intervention (持久化)
        self._last_intervention: Dict[str, Intervention] = {}

    # ---------------------------------------------------------------
    # 主入口
    # ---------------------------------------------------------------

    def select_intervention(
        self,
        cta_input: CTAInput,
        audience: Optional[str] = None,
    ) -> LCAResult:
        """LCA 主选择流程.

        Steps（02-lca §6）：
          1. 选 Bloom 目标层（select_bloom_target）
          2. 确定 CA 阶段（CAStateMachine）
          3. 确定 CLT 4 级呈现（AdaptiveCLTPresender）
          4. 检查 Bjork 触发条件
          5. 生成候选 + LinUCB 选择
          6. 生成 rationale
          7. 记录干预 + 归因
          8. 输出 LCAResult

        Args:
            cta_input: CTA 输入（含 BeliefState）
            audience: rationale 受众（student / teacher / parent）

        Returns:
            LCAResult（含 Intervention + rationale + expected_gain/risk）
        """
        belief_state = cta_input.belief_state
        student_id = cta_input.student_id
        audience = audience or self.config.rationale_audience
        candidates_bloom = cta_input.bloom_target_candidates or list(BloomLevel)

        # Step 1: Bloom 目标层
        bloom_target = select_bloom_target(
            belief_state,
            candidates_bloom,
            belief_state.learning_dna,
        )

        # Step 2: CA 阶段
        history = self.intervention_history.get(student_id, [])
        ca_stage = self.ca_state_machine.transition(student_id, belief_state, history)

        # Step 3: CLT 4 级
        clt_level = self.clt.determine_level(student_id, belief_state)

        # Step 4: Bjork 触发
        bjork_triggers: List[str] = []
        if self.bjork_testing.should_insert_test(belief_state):
            bjork_triggers.append("test")
        if self._should_review_spaced(belief_state):
            bjork_triggers.append("space")

        # Step 5: 生成候选 + LinUCB 选择
        candidates = _generate_candidates(
            bloom_target=bloom_target,
            clt_level=clt_level,
            ca_stage=ca_stage,
            bjork_triggers=bjork_triggers,
            cta_input=cta_input,
            skill_filter=cta_input.skill_filter,
            n_candidates=self.config.bandit_config.n_arms,
        )
        # v0.57.0: per-student bandit (修复 v0.56.0 多学生数据冲突)
        bandit = self._get_bandit(student_id)
        chosen = bandit.select_intervention(belief_state, candidates)
        # 触发标签回填
        chosen.bjork_triggers = bjork_triggers

        # Step 6: rationale
        rationale = self.rationale_gen.generate(chosen, belief_state, audience=audience)
        chosen.rationale = rationale

        # 估算 expected_gain / risk
        expected_gain = self._estimate_gain(chosen, belief_state)
        expected_risk = self._estimate_risk(chosen, belief_state)
        chosen.expected_gain = expected_gain
        chosen.expected_risk = expected_risk

        # Step 7: 记录干预
        self.intervention_history.setdefault(student_id, []).append(chosen)
        self.attribution.record_intervention(chosen, student_id)
        # v0.57.0: per-student 计数 + last_intervention 跟踪 (持久化用)
        self._last_intervention[student_id] = chosen
        self._select_count[student_id] = self._select_count.get(student_id, 0) + 1

        # Step 8: 输出
        return LCAResult(
            student_id=student_id,
            intervention=chosen,
            rationale=rationale,
            expected_gain=expected_gain,
            expected_risk=expected_risk,
            bloom_target=bloom_target,
            clt_level=clt_level,
            ca_stage=ca_stage,
        )

    def update(
        self,
        student_id: str,
        intervention: Intervention,
        new_state: BeliefState,
        state_delta: float,
    ) -> None:
        """基于干预效果更新策略（LinUCB + 因果归因）.

        Args:
            student_id: 学生 ID
            intervention: 选中的干预
            new_state: 干预后 CTA 状态
            state_delta: 状态增量（new_theta - old_theta，归一化到 [0, 1]）
        """
        # 归一化 state_delta 到 [0, 1]（reward 给 LinUCB）
        # M2 W2 简化：调用方已归一化（如未归一化，M2 W4 接入时调整）
        reward = max(0.0, min(1.0, state_delta))

        # 因果归因
        self.attribution.attribute_effect(
            intervention,
            student_id,
            state_delta=state_delta,
        )

        # v0.57.0: per-student bandit (修复 v0.56.0 多学生数据冲突)
        bandit = self._get_bandit(student_id)
        bandit.update(
            intervention=intervention,
            belief_state=new_state,
            reward=reward,
        )
        # v0.57.0: per-student update 计数
        self._update_count[student_id] = self._update_count.get(student_id, 0) + 1

    # ---------------------------------------------------------------
    # v0.57.0: per-student bandit 隔离 + 持久化接口
    # ---------------------------------------------------------------

    def _get_bandit(self, student_id: str) -> "LCAPolicyLearner":
        """获取 per-student bandit (lazy init).

        v0.57.0: 修复 v0.56.0 单 bandit 多学生数据冲突 BUG.
                  每个学生独立 LCAPolicyLearner 实例, LinUCB A/b 矩阵隔离.
        """
        if student_id not in self.bandits:
            self.bandits[student_id] = LCAPolicyLearner(self.config.bandit_config)
        return self.bandits[student_id]

    def dump_state(self, student_id: str) -> dict:
        """导出 per-student LCA 状态 (7 字段 + 内部辅助字段).

        Returns:
            dict 含 7 关键字段 (CLAUDE.md [5]):
              1. intervention_history  (List[Intervention.to_dict()])
              2. bandit_a              (List[List[List[float]]])
              3. bandit_b              (List[List[float]])
              4. arm_pull_counts       (List[int])
              5. last_intervention     (Intervention.to_dict() | None)
              6. update_count          (int)
              7. select_count          (int)
            + 内部字段:
              - arm_fingerprints       (Dict[str, str])  arm_idx → intervention_id
              - last_arm               (int)
        """
        import numpy as np

        bandit = self._get_bandit(student_id)
        linucb = bandit.bandit  # LinUCB 实例

        last_iv = self._last_intervention.get(student_id)
        return {
            # 7 关键字段
            "intervention_history": [iv.to_dict() for iv in self.intervention_history.get(student_id, [])],
            "bandit_a": [a.tolist() for a in linucb.A],
            "bandit_b": [b.tolist() for b in linucb.b],
            "arm_pull_counts": linucb.arm_pull_counts.tolist(),
            "last_intervention": last_iv.to_dict() if last_iv else None,
            "update_count": self._update_count.get(student_id, 0),
            "select_count": self._select_count.get(student_id, 0),
            # 内部辅助 (LinUCB select arm 需要)
            "arm_fingerprints": {str(k): v for k, v in bandit._arm_fingerprints.items()},
            "last_arm": bandit._last_arm,
        }

    def load_state(self, student_id: str, snapshot: dict) -> None:
        """加载 per-student LCA 状态 (7 字段全恢复).

        Args:
            student_id: 学生 ID
            snapshot: dump_state() 导出的 dict

        防御性自检 [5]: 7 关键字段必须全恢复, 缺一不可 (否则 LinUCB 学错位).

        注: context_dim 永远是 LCAPolicyLearner.CONTEXT_DIM=16 (常量),
             不从 snapshot 推断 (避免 schema 漂移导致 LinUCB 维度错位).
        """
        import numpy as np
        from .intervention import Intervention as _IV

        # 7 关键字段恢复
        # 1. intervention_history
        history = snapshot.get("intervention_history", []) or []
        self.intervention_history[student_id] = [_IV.from_dict(d) for d in history]

        # 2-4. LinUCB A/b 矩阵 + arm_pull_counts
        bandit = self._get_bandit(student_id)
        linucb = bandit.bandit

        bandit_a = snapshot.get("bandit_a", []) or []
        bandit_b = snapshot.get("bandit_b", []) or []
        arm_pull_counts = snapshot.get("arm_pull_counts", []) or []

        # 防御性: 维度校验 (防止 schema 漂移, 错位数据会污染 LinUCB)
        if bandit_a:
            expected_n_arms = linucb.n_arms
            expected_d = linucb.context_dim
            actual_n_arms = len(bandit_a)
            actual_d = len(bandit_a[0][0]) if bandit_a[0] and bandit_a[0][0] else 0

            if actual_n_arms != expected_n_arms or actual_d != expected_d:
                # 维度不匹配, 拒绝加载 (不污染 LinUCB)
                raise ValueError(
                    f"LinUCB state 维度不匹配 (student={student_id}): "
                    f"expected n_arms={expected_n_arms}, d={expected_d}, "
                    f"got n_arms={actual_n_arms}, d={actual_d}. "
                    f"可能 schema 漂移, 需手动清理 student_lca_state 行."
                )

            linucb.A = [np.array(a, dtype=float) for a in bandit_a]
            linucb.b = [np.array(b, dtype=float) for b in bandit_b]
            linucb.arm_pull_counts = np.array(arm_pull_counts, dtype=int)
        # 如果 snapshot 是空 (新学生), 保持默认 A=I, b=0 (LinUCB 冷启动)

        # 5. last_intervention
        last_iv_dict = snapshot.get("last_intervention")
        if last_iv_dict:
            self._last_intervention[student_id] = _IV.from_dict(last_iv_dict)
        else:
            self._last_intervention.pop(student_id, None)

        # 6-7. 计数
        self._update_count[student_id] = int(snapshot.get("update_count", 0))
        self._select_count[student_id] = int(snapshot.get("select_count", 0))

        # 内部辅助 (arm → intervention_id 映射, LinUCB select arm 需要)
        af_dict = snapshot.get("arm_fingerprints", {}) or {}
        bandit._arm_fingerprints = {int(k): v for k, v in af_dict.items()}
        bandit._last_arm = int(snapshot.get("last_arm", -1))

    # ---------------------------------------------------------------
    # 内部工具
    # ---------------------------------------------------------------

    def _should_review_spaced(self, belief_state: BeliefState) -> bool:
        """判断是否应触发间隔复习."""
        # 规则：K mastery_prob > 0.5 + 距上次轨迹 ≥ 5 步
        if belief_state.K.mastery_prob > 0.5:
            if len(belief_state.trajectory.snapshots) >= 5:
                return True
        return False

    def _estimate_gain(
        self,
        intervention: Intervention,
        belief_state: BeliefState,
    ) -> float:
        """估算 expected_gain = scale × (1 - K_mastery).

        gain_potential × scaffolding 比例。
        """
        bp_mastery = {
            BloomLevel.REMEMBER: belief_state.bloom_profile.remember,
            BloomLevel.UNDERSTAND: belief_state.bloom_profile.understand,
            BloomLevel.APPLY: belief_state.bloom_profile.apply,
            BloomLevel.ANALYZE: belief_state.bloom_profile.analyze,
            BloomLevel.EVALUATE: belief_state.bloom_profile.evaluate,
            BloomLevel.CREATE: belief_state.bloom_profile.create,
        }[intervention.bloom_target]
        gain = self.config.expected_gain_scale * (1.0 - bp_mastery)
        # scaffolding 提升 gain
        gain *= (0.5 + 0.5 * intervention.scaffolding_level)
        return max(0.0, min(1.0, gain))

    def _estimate_risk(
        self,
        intervention: Intervention,
        belief_state: BeliefState,
    ) -> float:
        """估算 expected_risk——Frustration / Cheating 概率.

        规则：
        - 高难度 + 低 K mastery → 高 frustration 风险
        - 低 scaffolding + 错误率历史 → 中风险
        """
        # 难度 - K mastery gap
        k_gap = intervention.difficulty - belief_state.K.mastery_prob
        risk = max(0.0, k_gap) * 0.5
        # scaffolding 缓解
        risk *= (1.0 - intervention.scaffolding_level)
        return max(0.0, min(1.0, risk))


__all__ = ["LCAEngine", "LCAEngineConfig", "LCAResult", "CTAInput"]
