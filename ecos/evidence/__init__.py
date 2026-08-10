"""Evidence Engine —— v0.83 Kernel Engine 第 1 个.

对应 kernel-mapping §1.4 (演进建议 v0.77.0, 延迟到 v0.83.0-a 实施).

v0.83.0-a 范围: 统一 schema (Evidence + EvidenceSource 枚举) + 跨 3 张表
(evidence_log / calibration_log / event_log) 集成 + Python 端 query.
"""

from .evidence import Evidence, EvidenceSource
from .evidence_engine import EvidenceConfig, EvidenceEngine

__status__ = "v0.83.0-a"

__all__ = [
    # 数据结构
    "Evidence",
    "EvidenceSource",
    # Engine
    "EvidenceEngine",
    "EvidenceConfig",
]
