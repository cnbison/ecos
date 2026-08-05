"""抗幻觉子包——3 机制 + 1 人工审核触发.

> **v0.75.1 H3 修订说明** (2026-08-04):
> 模块名 `anti_hallucination` 是历史命名 (v0.60-v0.75 沿用), **模块功能不变**.
> 实际上 H3 "互校抗 LLM 幻觉" 假设在 D2 + D4 评估后不成立 (单 Agent 6 Bloom 0.108 ≈ 双 Agent 0.110).
> **模块的真正价值**: 实现 Fast Calibration (14 题 ECE < 0.15) + Wide Coverage (100% arm) 的工程机制.
> **命名保留理由**: git 历史可追溯 / 16 个版本连贯性 / 教育价值 (新人看到名字会问 "为什么叫 anti_hallucination 但 H3 又改?" 引导理解 H3 修订).
> 详见 [discussions/2026-08-04-v0751-H3-redefinition-PRD.md](../../../discussions/2026-08-04-v0751-H3-redefinition-PRD.md).

对应 spec §4:
  - belief_check.py (机制 1: 信念分布检查)
  - experiment_design.py (机制 2: 实验设计验证)
  - causal_attribution.py (机制 3: 因果归因强制) — Phase 5+ (依赖 CTA L4 真实实现)
  - human_review.py (人工审核触发)
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