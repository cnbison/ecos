"""L3 Bjork 测试效应（Testing Effect）——主动提取 > 被动重读.

对应：
  - research/10-engineering/02-lca-policy-engine.md §3.3 BjorkTestingEffect
  - research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md §2.1

触发规则（M2 W2 简化）：
  - 规则 1：BKT P(L) > 0.7 + 最近 1 天未测试 → 触发 'test'
  - 规则 2：trajectory 中 Bloom level 连续 ≥5 次练习无测试 → 触发 'test'

测试形式不限于做题：自我解释、Teach-back、自由回忆、Elaboration。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from ....cta.belief_state import BeliefState


@dataclass
class BjorkTestingConfig:
    """测试效应配置."""

    mastery_threshold: float = 0.7    # P(L) 阈值
    inactivity_threshold: timedelta = timedelta(days=1)
    consecutive_practice_threshold: int = 5


class BjorkTestingEffect:
    """Bjork 测试效应触发器.

    用法：
        bjork = BjorkTestingEffect(BjorkTestingConfig())
        if bjork.should_insert_test(belief_state, last_test_time):
            intervention.bjork_triggers.append("test")
    """

    def __init__(self, config: Optional[BjorkTestingConfig] = None):
        self.config = config or BjorkTestingConfig()

    def should_insert_test(
        self,
        belief_state: BeliefState,
        last_test_time: Optional[datetime] = None,
        now: Optional[datetime] = None,
    ) -> bool:
        """判断是否应插入测试.

        Args:
            belief_state: CTA 输出
            last_test_time: 最近一次测试时间（None 表示从未测试）
            now: 当前时间（用于测试；默认 datetime.now）

        Returns:
            True = 应触发测试效应
        """
        now = now or datetime.now()

        # 规则 1：K 维度 mastery_prob > 0.7 + 超过 1 天未测试
        if belief_state.K.mastery_prob > self.config.mastery_threshold:
            if last_test_time is None or (now - last_test_time) > self.config.inactivity_threshold:
                return True

        # 规则 2：trajectory 中连续 N 次都是同一 Bloom 层（推断为"只做练习未测试"）
        if self._has_long_practice_streak(belief_state):
            return True

        return False

    def _has_long_practice_streak(self, belief_state: BeliefState) -> bool:
        """检测 trajectory 是否长时间停留在同一 Bloom 层级（推断为只练习未测试）."""
        snapshots = belief_state.trajectory.snapshots
        if len(snapshots) < self.config.consecutive_practice_threshold:
            return False
        recent = snapshots[-self.config.consecutive_practice_threshold:]
        # 如果最近 N 次都在同一 Bloom 层，认为是"练习未测试"
        bloom_layers = {s.bloom_level for s in recent}
        return len(bloom_layers) == 1


__all__ = ["BjorkTestingEffect", "BjorkTestingConfig"]
