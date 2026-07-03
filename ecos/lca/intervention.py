"""LCA 干预数据结构——5 类干预 + 参数 + 期望效果.

对应：
  - research/10-engineering/02-lca-policy-engine.md §2 Intervention 数据结构
  - research/20-pedagogy/03-bloom-pedagogy.md §4 干预分类
  - research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md §1 CLT 4 级

设计原则：
  - Intervention 是 LCA 推荐的"动作描述"（不直接执行，由 App 层执行）
  - 包含 4 个连续参数（difficulty / quantity / feedback_density / scaffolding_level）
    用于 LinUCB 的 arm 编码
  - 包含 expected_gain / expected_risk 用于 L4 因果归因
  - rationale 字段为 None 时由 RationaleGenerator 后续填充
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from ..cta.belief_state import BeliefState, BloomLevel, LearningDNAState


class InterventionType(Enum):
    """5 类干预类型（v0.4.0 LCA 教学法基础 §1）.

    - EXPLANATORY: 讲解型（worked example / 概念讲解 / 视频）
    - PRACTICE:    练习型（变式训练 / 刻意练习 / drills）
    - INQUIRY:     探究型（提问引导 / 苏格拉底式 / Teach-back）
    - FEEDBACK:    反馈型（rubric 评估 / 同伴互评 / 教师批注）
    - METACOGNITIVE: 元认知型（反思日志 / 学习策略调整 / self-explanation）
    """

    EXPLANATORY = "explanatory"
    PRACTICE = "practice"
    INQUIRY = "inquiry"
    FEEDBACK = "feedback"
    METACOGNITIVE = "metacognitive"


class CLTLevel(Enum):
    """CLT 4 级呈现级别（expertise reversal effect）.

    - NOVICE:      完整 worked example + 即时反馈（germane load 最大）
    - DEVELOPING:  部分 worked example + 完成题（fade 启动）
    - PROFICIENT:  无 worked example + 即时反馈（独立解题）
    - EXPERT:      无 worked example + 延迟反馈（最大化 retrieval practice）
    """

    NOVICE = 1
    DEVELOPING = 2
    PROFICIENT = 3
    EXPERT = 4


class CAStage(Enum):
    """Cognitive Apprenticeship 6 阶段（v0.4.0 §3.2）.

    M2 W2 实现 Stage 1-3（Phase 4 MVP），Stage 4-6 留 Phase 5+
    """

    MODELING = 1
    COACHING = 2
    SCAFFOLDING = 3
    ARTICULATION = 4  # Phase 5+
    REFLECTION = 5    # Phase 5+
    EXPLORATION = 6   # Phase 5+


@dataclass
class Intervention:
    """LCA 干预数据结构（LCA → App 层）.

    Attributes:
        intervention_id:    唯一 ID（默认 UUID4 hex）
        intervention_type:  干预类型（5 类之一）
        bloom_target:       目标 Bloom 层
        target_skills:      目标知识点 ID 列表
        target_misconceptions: 目标 misconceptions（CTA C 维度）
        target_tcs:         目标 TC 列表（待跨越的概念边界）
        difficulty:         难度 [0, 1]（0=极易, 1=极难）
        quantity:           题目数量（整数，1-20）
        feedback_density:   反馈密度 [0, 1]（0=无反馈, 1=逐步反馈）
        scaffolding_level:  支持程度 [0, 1]（CLT 启发式）
        clt_level:          CLT 呈现级别
        ca_stage:           CA 阶段
        bjork_triggers:     Bjork 触发标签（test/space/difficulty/interleave）
        expected_gain:      期望状态增量（LinUCB reward 估计）
        expected_risk:      期望风险（Frustration/Cheating 概率）
        estimated_duration_sec: 预计时长（秒）
        rationale:          自然语言理由（学生/教师/家长视角，由 RationaleGenerator 填充）
        metadata:           扩展字段（持久化 / 教师后台接口用）
    """

    intervention_type: InterventionType
    bloom_target: BloomLevel
    target_skills: List[str] = field(default_factory=list)
    target_misconceptions: List[str] = field(default_factory=list)
    target_tcs: List[str] = field(default_factory=list)
    difficulty: float = 0.5
    quantity: int = 5
    feedback_density: float = 0.5
    scaffolding_level: float = 0.5
    clt_level: CLTLevel = CLTLevel.DEVELOPING
    ca_stage: CAStage = CAStage.COACHING
    bjork_triggers: List[str] = field(default_factory=list)
    expected_gain: float = 0.0
    expected_risk: float = 0.0
    estimated_duration_sec: int = 600
    rationale: Optional[str] = None
    intervention_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    metadata: dict = field(default_factory=dict)

    # ---------------------------------------------------------------
    # 工具方法
    # ---------------------------------------------------------------

    def to_dict(self) -> dict:
        """导出为可序列化的 dict（持久化 + 教师后台接口使用）."""
        return {
            "intervention_id": self.intervention_id,
            "intervention_type": self.intervention_type.value,
            "bloom_target": self.bloom_target.name,
            "target_skills": list(self.target_skills),
            "target_misconceptions": list(self.target_misconceptions),
            "target_tcs": list(self.target_tcs),
            "difficulty": self.difficulty,
            "quantity": self.quantity,
            "feedback_density": self.feedback_density,
            "scaffolding_level": self.scaffolding_level,
            "clt_level": self.clt_level.name,
            "ca_stage": self.ca_stage.name,
            "bjork_triggers": list(self.bjork_triggers),
            "expected_gain": self.expected_gain,
            "expected_risk": self.expected_risk,
            "estimated_duration_sec": self.estimated_duration_sec,
            "rationale": self.rationale,
            "metadata": dict(self.metadata),
        }


# ---------------------------------------------------------------------------
# Bloom 目标选择算法（02-lca-policy-engine.md §2.3）
# ---------------------------------------------------------------------------

def select_bloom_target(
    belief_state: BeliefState,
    candidates: List[BloomLevel],
    learning_dna: LearningDNAState,
) -> BloomLevel:
    """根据 CTA 状态选择最优 Bloom 目标层.

    算法：
      score(layer) = (1 - mastery) × bkt_support × dna_weight
      其中：
        - mastery = belief_state.bloom_profile 估计的该层掌握度（伪测）
        - bkt_support = 1.0 if 5D K 中有相关技能支持，0.5 otherwise（待 Phase 4+ 接入 Q-Matrix）
        - dna_weight = learning_dna 对该层类型的偏好权重

    返回 candidates 中 score 最高的 BloomLevel。

    Phase 4 MVP 简化：
      - mastery 用 bloom_profile 各类计数归一化估计
      - bkt_support 暂固定为 1.0（Phase 5+ 接入 Q-Matrix）
      - dna_weight 暂固定为 1.0（Phase 5+ 接入个性化偏好）

    Args:
        belief_state: CTA 输出
        candidates: 候选 Bloom 层（一般 6 层全部传入；LCA 可筛选）
        learning_dna: 学生 LearningDNA（M2 W1 占位，使用默认）

    Returns:
        score 最高的 BloomLevel
    """
    if not candidates:
        raise ValueError("candidates 必须非空")

    bp = belief_state.bloom_profile
    # 估计每层的"掌握度"——逆序（高层掌握度低 → 增长空间大 → 优先选择）
    # MVP 简化：使用 dominance 估计 + 均匀 fallback
    bloom_layer_mastery = {
        BloomLevel.REMEMBER: bp.remember,
        BloomLevel.UNDERSTAND: bp.understand,
        BloomLevel.APPLY: bp.apply,
        BloomLevel.ANALYZE: bp.analyze,
        BloomLevel.EVALUATE: bp.evaluate,
        BloomLevel.CREATE: bp.create,
    }

    best_target = candidates[0]
    best_score = -float("inf")

    for layer in candidates:
        mastery = bloom_layer_mastery.get(layer, 0.5)
        # 增长潜力：1 - mastery
        gain_potential = 1.0 - mastery
        # BKT 支持（MVP 简化：统一 1.0）
        bkt_support = 1.0
        # DNA 权重（MVP 简化：统一 1.0）
        dna_weight = 1.0
        score = gain_potential * bkt_support * dna_weight
        if score > best_score:
            best_score = score
            best_target = layer

    return best_target


__all__ = [
    "InterventionType",
    "CLTLevel",
    "CAStage",
    "Intervention",
    "select_bloom_target",
]
