"""L3 CLT 4 级自适应呈现（expertise reversal effect 自动化）.

对应：
  - research/10-engineering/02-lca-policy-engine.md §3.1 AdaptiveCLTPresender
  - research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md §1
    CLT (Cognitive Load Theory) 4 级呈现

规则（02-lca §3.1）：
  - 默认级别由 BloomProfile.dominant_layer 决定（L1-L2 → NOVICE, L3-L4 → DEVELOPING, L5-L6 → PROFICIENT）
  - 连续 N 错 → 升级 CLT 级别（提供更多 scaffolding）
  - 连续 N 对 → 降级 CLT 级别（撤走 worked example）
  - TC liminal 状态 → 升级（需要更多支持跨越概念边界）

Phase 4 MVP 简化：
  - 学生级别用 Dict[student_id, CLTLevel] 内存持久化（Phase 5+ 接入 persistence）
  - consecutive_correct / consecutive_error 信号由 BeliefEngine 通过 trajectory.snapshots 推断
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from ....cta.belief_state import BeliefState, TCState
from ...intervention import CLTLevel


@dataclass
class CLTConfig:
    """CLT 自适应配置."""

    consecutive_threshold: int = 3   # 连续 N 次触发升级/降级
    low_threshold: float = 0.4       # 正确率 < 0.4 → 升级
    high_threshold: float = 0.85     # 正确率 > 0.85 → 降级
    # 升级时支持级别增量：NOVICE(1) -> DEVELOPING(2) -> ...


class AdaptiveCLTPresender:
    """CLT 4 级自适应呈现器.

    用法：
        presender = AdaptiveCLTPresender(CLTConfig())
        level = presender.determine_level("student_001", belief_state)
        template = presender.generate_presentation(
            intervention_type=InterventionType.EXPLANATORY,
            clt_level=level,
        )
    """

    def __init__(self, config: Optional[CLTConfig] = None):
        self.config = config or CLTConfig()
        # 学生级别的 CLT level（持久化层 Phase 5+ 接入）
        self.student_clt_level: Dict[str, CLTLevel] = {}

    # ---------------------------------------------------------------
    # Level 判断
    # ---------------------------------------------------------------

    def determine_level(
        self,
        student_id: str,
        belief_state: BeliefState,
    ) -> CLTLevel:
        """基于学生状态确定 CLT 4 级呈现级别.

        Returns:
            CLTLevel（NOVICE / DEVELOPING / PROFICIENT / EXPERT）
        """
        # Step 1: 默认级别（基于 BloomProfile.dominant_layer）
        bloom = belief_state.bloom_profile
        default_level = self._default_level_from_bloom(bloom.dominant_layer)

        # Step 2: 调整（基于历史表现）
        history = belief_state.trajectory.snapshots
        if len(history) >= self.config.consecutive_threshold:
            recent_correct_rate = self._compute_recent_correct_rate(
                history, self.config.consecutive_threshold * 2
            )
            if recent_correct_rate < self.config.low_threshold:
                default_level = self._upgrade(default_level)
            elif recent_correct_rate > self.config.high_threshold:
                default_level = self._downgrade(default_level)

        # Step 3: 检查 TC liminal 状态（需要更多支持跨越概念边界）
        # M2 W2: 当前 BeliefState.C 是 DimensionState，TC 容器将在 Phase 5+ 完整接入
        # 优雅处理：当学生已有观测信号（trajectory ≥ 3），且 C.confidence 较低
        # 时才升级。空 trajectory 时跳过（默认 confidence=0 是没信号，不是真低）。
        if (
            len(belief_state.trajectory.snapshots) >= 3
            and belief_state.C.confidence < 0.3
        ):
            default_level = self._upgrade(default_level)

        # Step 4: 持久化学生级别
        self.student_clt_level[student_id] = default_level
        return default_level

    def get_persisted_level(self, student_id: str) -> Optional[CLTLevel]:
        """查询持久化的 CLT level（用于恢复会话）."""
        return self.student_clt_level.get(student_id)

    # ---------------------------------------------------------------
    # 模板生成
    # ---------------------------------------------------------------

    def generate_presentation(
        self,
        intervention_type,  # InterventionType (避免循环 import)
        clt_level: CLTLevel,
        problem: Optional[dict] = None,
    ) -> dict:
        """生成 CLT 4 级呈现参数.

        Args:
            intervention_type: 5 类干预之一
            clt_level: CLT level
            problem: 题目的 ProblemMetadata（Phase 4+ 接入，MVP 用 dict 占位）

        Returns:
            呈现参数字典（含 worked_example, scaffolding, hints, feedback_timing）
        """
        from ...intervention import InterventionType  # 避免循环

        template = CLTTemplate(level=clt_level, intervention_type=intervention_type)
        return template.generate(problem or {})

    # ---------------------------------------------------------------
    # 内部工具
    # ---------------------------------------------------------------

    @staticmethod
    def _default_level_from_bloom(bloom_layer) -> CLTLevel:
        """基于 Bloom dominant 层选默认 CLT level."""
        # bloom_layer is BloomLevel enum; .value is 1-6
        lvl = bloom_layer.value
        if lvl <= 2:
            return CLTLevel.NOVICE
        if lvl <= 4:
            return CLTLevel.DEVELOPING
        return CLTLevel.PROFICIENT  # L5/L6 → PROFICIENT（EXPERT 在自适应后才达到）

    @staticmethod
    def _compute_recent_correct_rate(history, window: int) -> float:
        """计算最近 N 次快照的表现代理值.

        M2 W2 简化：StateSnapshot 没有 `correct` 字段（M2 W1 schema），
        使用 `confidence` 字段做隐式信号——
          - confidence > 0.5 → 视为"表现良好"（≈答对）
          - confidence ≤ 0.5 → 视为"表现不足"
        返回 [0, 1] 范围内近似正确率。
        """
        if not history:
            return 0.5
        recent = history[-window:]
        if not recent:
            return 0.5
        # confidence 阈值 0.5 二值化后求平均
        good = sum(1 for s in recent if getattr(s, "confidence", 0.5) > 0.5)
        return good / len(recent)

    @staticmethod
    def _upgrade(level: CLTLevel) -> CLTLevel:
        """升级 CLT level（提供更多 scaffolding）."""
        if level.value >= CLTLevel.EXPERT.value:
            return CLTLevel.EXPERT
        return CLTLevel(level.value + 1)

    @staticmethod
    def _downgrade(level: CLTLevel) -> CLTLevel:
        """降级 CLT level（撤走支持）."""
        if level.value <= CLTLevel.NOVICE.value:
            return CLTLevel.NOVICE
        return CLTLevel(level.value - 1)


__all__ = ["AdaptiveCLTPresender", "CLTConfig"]
