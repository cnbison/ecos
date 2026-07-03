"""双 Agent 互校 4 个交互模式.

对应 spec §3：
  - normal.py（常态循环）
  - belief_challenge.py（信念质疑）
  - strategy_challenge.py（策略质疑）
  - meta_reflection.py（元反思）—— Phase 5+ 占位
"""

from .belief_challenge import (
    BLOOM_JUMP_THRESHOLD,
    HIGH_CONFIDENCE_THRESHOLD,
    BeliefChallengeMode,
    should_trigger_belief_challenge,
)
from .normal import NormalCycle
from .strategy_challenge import (
    DETECT_WINDOW,
    INEFFECTIVE_GAIN_THRESHOLD,
    StrategyChallengeMode,
)

__all__ = [
    # 常态
    "NormalCycle",
    # 信念质疑
    "BeliefChallengeMode",
    "should_trigger_belief_challenge",
    "HIGH_CONFIDENCE_THRESHOLD",
    "BLOOM_JUMP_THRESHOLD",
    # 策略质疑
    "StrategyChallengeMode",
    "DETECT_WINDOW",
    "INEFFECTIVE_GAIN_THRESHOLD",
]