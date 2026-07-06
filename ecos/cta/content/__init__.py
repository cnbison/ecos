"""CTA 内容库——TC + Misconception（供 BeliefEngine LLM Critic 集成用）。

对应 research/30-shared-cognitive-tools/theoretical-foundations/
03-c-dimension-content-libraries.md §1.7 + §2.6。
"""

from .misconceptions import MisconceptionEntry, MisconceptionLibrary
from .threshold_concepts import TCStatus, ThresholdConceptEntry, ThresholdConceptLibrary

from .python_basics_misconceptions import (
    PYTHON_BASICS_MISCONCEPTION_LIBRARY_STR,
    PythonBasicsMisconceptionLibrary,
)

__all__ = [
    "MisconceptionEntry",
    "MisconceptionLibrary",
    "ThresholdConceptEntry",
    "ThresholdConceptLibrary",
    "TCStatus",
    "PythonBasicsMisconceptionLibrary",
    "PYTHON_BASICS_MISCONCEPTION_LIBRARY_STR",
]
