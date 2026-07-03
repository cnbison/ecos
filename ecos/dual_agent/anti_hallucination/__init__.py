"""抗幻觉子包——3 机制 + 1 人工审核触发.

对应 spec §4：
  - belief_check.py（机制 1：信念分布检查）
  - experiment_design.py（机制 2：实验设计验证）
  - causal_attribution.py（机制 3：因果归因强制）—— Phase 5+（依赖 CTA L4 真实实现）
  - human_review.py（人工审核触发）
"""

from .belief_check import BeliefDistributionCheck
from .experiment_design import ExperimentDesignValidator
from .human_review import HumanReviewConfig, HumanReviewTrigger

__all__ = [
    "BeliefDistributionCheck",
    "ExperimentDesignValidator",
    "HumanReviewConfig",
    "HumanReviewTrigger",
]