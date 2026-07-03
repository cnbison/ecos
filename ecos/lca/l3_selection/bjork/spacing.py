"""L3 Bjork 间隔效应（Spacing Effect）——分散复习 > 集中练习.

对应：
  - research/10-engineering/02-lca-policy-engine.md §3.4 BjorkSpacingEffect
  - research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md §2.3
  - CTA L1 BKTEvolutionLayer 间隔衰减

Phase 4 MVP 简化：
  - 使用静态间隔表（Cepeda 2006 经典曲线）替代完整 FSRS 算法
  - 不引入 fsrs 依赖（避免膨胀依赖）
  - 后续可平滑替换为 FSRS（02-lca §3.4 提到 ts-fsrs/py-fsrs）
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class BjorkSpacingConfig:
    """间隔效应配置（MVP 静态表）."""

    # Cepeda 2006 风格间隔（按 mastery 分桶）
    short_term_interval_days: int = 2   # 短间隔（默认 2 天后复习）
    long_term_interval_days: int = 30   # 长间隔（30 天后巩固复习）


class BjorkSpacingEffect:
    """Bjork 间隔效应——决定何时安排复习.

    用法：
        spacing = BjorkSpacingEffect()
        schedule = spacing.get_review_schedule(
            skill_id="quadratic.roots",
            current_mastery=0.7,
            last_review_date=datetime.now() - timedelta(days=1),
        )
    """

    def __init__(self, config: Optional[BjorkSpacingConfig] = None):
        self.config = config or BjorkSpacingConfig()

    def get_review_schedule(
        self,
        skill_id: str,
        current_mastery: float,
        last_review_date: Optional[datetime] = None,
        now: Optional[datetime] = None,
    ) -> dict:
        """返回复习时间表.

        Args:
            skill_id: 知识点 ID
            current_mastery: 当前掌握度 [0, 1]
            last_review_date: 上次复习日期（None 表示从未复习）
            now: 当前时间（测试友好）

        Returns:
            {
              next_short_review: datetime,
              next_long_review: datetime,
              mastery: float,
            }
        """
        now = now or datetime.now()
        base = last_review_date or now

        # 间隔按 mastery 自适应
        if current_mastery < 0.4:
            short_days = 1   # 弱：每天复习
        elif current_mastery < 0.7:
            short_days = self.config.short_term_interval_days  # 中：2 天
        else:
            short_days = max(4, self.config.short_term_interval_days * 2)  # 强：4 天

        next_short = base + timedelta(days=short_days)
        next_long = next_short + timedelta(days=self.config.long_term_interval_days)

        return {
            "skill_id": skill_id,
            "mastery": current_mastery,
            "next_short_review": next_short,
            "next_long_review": next_long,
        }


__all__ = ["BjorkSpacingEffect", "BjorkSpacingConfig"]
