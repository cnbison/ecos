"""L3 Cognitive Apprenticeship Scaffolding 衰减.

对应：
  - research/10-engineering/02-lca-policy-engine.md §3.5 CAScaffoldingDecay
  - research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md §3.3

规则：
  - 连续 N 次成功后自动撤走支持（expertise reversal 自动化）
  - 当连续失败时，scaffolding 保持或提升（避免学生陷入 frustration）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class CAConfig:
    """CA Scaffolding 配置."""

    fade_threshold: int = 3      # 连续 N 次成功后撤走支持
    fade_step: float = 0.1       # 每次撤走步长
    restore_threshold: int = 2   # 连续 N 次失败后恢复支持
    restore_step: float = 0.15   # 每次恢复步长
    min_scaffolding: float = 0.0
    max_scaffolding: float = 1.0


class CAScaffoldingDecay:
    """Cognitive Apprenticeship Scaffolding 衰减器.

    用法：
        decay = CAScaffoldingDecay(CAConfig())
        new_level = decay.update_scaffolding_level(
            current_level=0.5,
            consecutive_successes=4,  # 连续 4 次成功
            consecutive_failures=0,
        )
        # → 0.4
    """

    def __init__(self, config: Optional[CAConfig] = None):
        self.config = config or CAConfig()

    def update_scaffolding_level(
        self,
        current_level: float,
        consecutive_successes: int = 0,
        consecutive_failures: int = 0,
    ) -> float:
        """根据连续成功/失败更新 scaffolding 水平.

        Args:
            current_level: 当前 scaffolding 水平 [0, 1]
            consecutive_successes: 连续成功次数
            consecutive_failures: 连续失败次数

        Returns:
            新的 scaffolding 水平
        """
        new_level = current_level

        # 成功路径：撤走支持
        if consecutive_successes >= self.config.fade_threshold:
            fade_count = consecutive_successes // self.config.fade_threshold
            new_level = current_level - self.config.fade_step * fade_count

        # 失败路径：恢复支持
        if consecutive_failures >= self.config.restore_threshold:
            restore_count = consecutive_failures // self.config.restore_threshold
            new_level = new_level + self.config.restore_step * restore_count

        return max(
            self.config.min_scaffolding,
            min(self.config.max_scaffolding, new_level),
        )


__all__ = ["CAScaffoldingDecay", "CAConfig"]
