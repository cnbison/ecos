"""Motivation Profile — X 维度抽出, 独立 Profile (v0.87.0-a).

对应 12-kernel-mapping §2.1 Motivation Profile.

模块:
    - profile.py: MotivationProfile + MotivationObservation

向后兼容:
    - X 维度保留在 BeliefState (v0.86 兼容, lbc001/lbc002 历史数据不变)
    - Motivation Profile 独立新增 (渐进迁移)
    - 防御性自检 [8] 仍 hard block (add_observation 是 allowlist)
"""

from .profile import MotivationObservation, MotivationProfile

__all__ = [
    "MotivationProfile",
    "MotivationObservation",
]
