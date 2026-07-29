"""ECOS 指标模块 (v0.63.0 新增).

Phase 4 / Phase 5 验证需要的统计指标 (ECE, reliability diagram 等).
所有指标纯函数实现, 不依赖 sklearn / scipy, 保持项目零外部依赖.

包含:
  - ece: Expected Calibration Error (H3 验证核心指标)
  - 未来扩展: AUC, Brier score, Cohen's d 等

设计原则:
  - 纯函数, 无副作用
  - 输入 numpy array 或 Python list
  - 输出 float / dict, 跟 sklearn.calibration 接口对齐 (方便后续替换)
"""

from .ece import (
    expected_calibration_error,
    reliability_diagram_data,
    binary_calibration,
)

__all__ = [
    "expected_calibration_error",
    "reliability_diagram_data",
    "binary_calibration",
]
