"""LCA - Learning Coach Agent（学习教练 Agent）.

负责"改变学生"——像教练 + 强化学习策略器一样：
- 主动设计干预实验
- 探索最优策略
- 持续优化 policy

M2 W2 实现（LCA 策略引擎骨架）：
- 5 类干预 + 4 级 CLT + 6 阶段 CA
- L3：CLT 自适应 + Bjork 测试/间隔 + CA Scaffolding 衰减
- L4：CA 状态机（Stage 1-3 MVP）+ LinUCB + 因果归因
- Rationale：LLM 表达层（ECOSLLMClient + 模板 fallback）
- LCAEngine 主流程编排

工程文档：research/10-engineering/02-lca-policy-engine.md v1.0
"""

from .cta_input import CTAInput
from .evaluator import Evaluator, EvaluatorConfig
from .experiment_designer import (
    DEFAULT_CANDIDATE_DIFFICULTIES,
    DEFAULT_CANDIDATE_TYPES,
    ExperimentDesigner,
    ExperimentDesignerConfig,
)
from .intervention import (
    CAStage,
    CLTLevel,
    Intervention,
    InterventionType,
    select_bloom_target,
)
from .policy_learner import PolicyLearner, PolicyLearnerConfig
from .l3_selection import (
    AdaptiveCLTPresender,
    BjorkSpacingConfig,
    BjorkSpacingEffect,
    BjorkTestingConfig,
    BjorkTestingEffect,
    CAConfig,
    CAScaffoldingDecay,
    CLTTemplate,
    CLTConfig,
)
from .l4_optimization import (
    BanditConfig,
    CAStateMachine,
    CTA_L4_Backend,
    CausalEffect,
    LCAAttribution,
    LCAPolicyLearner,
    LinUCB,
)
from .orchestrator import (
    LCAEngine,
    LCAEngineConfig,
    LCAResult,
)
from .planner import PlanDecision, Planner, PlannerConfig
from .rationale import PROMPT_TEMPLATES, RationaleGenerator

__status__ = "m2-w2-skeleton"

__all__ = [
    # 数据结构
    "InterventionType",
    "CLTLevel",
    "CAStage",
    "Intervention",
    "select_bloom_target",
    "CTAInput",  # v0.82.0-b: 迁到 cta_input.py
    # L3
    "AdaptiveCLTPresender",
    "BjorkSpacingConfig",
    "BjorkSpacingEffect",
    "BjorkTestingConfig",
    "BjorkTestingEffect",
    "CAConfig",
    "CAScaffoldingDecay",
    "CLTTemplate",
    "CLTConfig",
    # L4
    "BanditConfig",
    "CAStateMachine",
    "CTA_L4_Backend",
    "CausalEffect",
    "LCAAttribution",
    "LCAPolicyLearner",
    "LinUCB",
    # v0.82.0-a: LCA 4-layer 第 1 层 Planner
    "Planner",
    "PlannerConfig",
    "PlanDecision",
    # v0.82.0-b: LCA 4-layer 第 2 层 ExperimentDesigner
    "ExperimentDesigner",
    "ExperimentDesignerConfig",
    "DEFAULT_CANDIDATE_TYPES",
    "DEFAULT_CANDIDATE_DIFFICULTIES",
    # v0.82.0-c: LCA 4-layer 第 3 层 Evaluator
    "Evaluator",
    "EvaluatorConfig",
    # v0.82.0-d: LCA 4-layer 第 4 层 PolicyLearner
    "PolicyLearner",
    "PolicyLearnerConfig",
    # Orchestrator
    "LCAEngine",
    "LCAEngineConfig",
    "LCAResult",
    # Rationale
    "PROMPT_TEMPLATES",
    "RationaleGenerator",
]
