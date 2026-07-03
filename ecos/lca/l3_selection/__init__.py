"""L3 教学法层——CLT + Bjork + CA scaffolding 组合."""

from .ca import CAConfig, CAScaffoldingDecay
from .clt import AdaptiveCLTPresender, CLTConfig, CLTTemplate
from .bjork import (
    BjorkSpacingConfig,
    BjorkSpacingEffect,
    BjorkTestingConfig,
    BjorkTestingEffect,
)

__all__ = [
    # CLT
    "AdaptiveCLTPresender",
    "CLTConfig",
    "CLTTemplate",
    # Bjork
    "BjorkSpacingConfig",
    "BjorkSpacingEffect",
    "BjorkTestingConfig",
    "BjorkTestingEffect",
    # CA
    "CAConfig",
    "CAScaffoldingDecay",
]
