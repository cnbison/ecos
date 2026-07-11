"""TC 状态检测器——Threshold Concept 跨越判定。

对应 research/10-engineering/01-cta-belief-engine.md §8.2 TC 检测器设计。

TC 状态机：
  pre_liminal → liminal → post_liminal（不可逆）

触发条件：
  - pre_liminal → liminal：Apply(L3) 正确 + 无 active misconception
  - liminal → post_liminal：持续 3 次 L3+ 正确
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

import numpy as np

from ecos.cta.belief_state import BloomLevel, TCState


# TC 定义（每 topic 一个 TC）
DEFAULT_TC_LIBRARY: Dict[str, dict] = {
    "python.variables": {
        "name": "变量是引用而非赋值",
        "liminal_signal": "理解 x = x + 1 的语义",
        "threshold": 0.7,
    },
    "python.loops": {
        "name": "循环是重复执行",
        "liminal_signal": "能用循环解决实际问题",
        "threshold": 0.7,
    },
    "python.functions": {
        "name": "函数是输入-输出映射",
        "liminal_signal": "理解 return 的语义",
        "threshold": 0.7,
    },
    "python.recursion": {
        "name": "递归是函数自调用分解",
        "liminal_signal": "理解 base case 的必要性",
        "threshold": 0.7,
    },
    "python.scope": {
        "name": "局部/全局作用域隔离",
        "liminal_signal": "理解 global 关键字",
        "threshold": 0.7,
    },
}


@dataclass
class TCStateDetector:
    """TC 状态检测器。

    检测学生是否跨越阈值概念（liminal → post_liminal）。
    基于 Bloom L3+ 正确响应 + misconception 状态启发式判断。
    """

    tc_library: Dict[str, dict] = field(default_factory=lambda: DEFAULT_TC_LIBRARY.copy())
    liminal_threshold: float = 0.7  # progress 达到此值 → liminal
    post_liminal_streak: int = 3   # liminal 后需连续 N 次 L3+ 正确 → post_liminal

    def detect(
        self,
        topic: str,
        correct: bool,
        bloom_level: BloomLevel,
        current_tc_state: Optional[TCState],
        has_active_misc: bool,
    ) -> TCState:
        """给定一个观测，判断该 topic 的 TC 状态更新。

        Args:
            topic: 知识点 ID（如 python.variables）
            correct: 本次是否正确
            bloom_level: 本次题目的 Bloom 层
            current_tc_state: 当前 TC 状态（首次为 None）
            has_active_misc: 是否有 active misconception（影响 liminal 判断）

        Returns:
            更新后的 TCState
        """
        tc_def = self.tc_library.get(topic, {"name": topic, "threshold": 0.7})
        threshold = tc_def.get("threshold", 0.7)
        is_l3_plus = bloom_level.value >= BloomLevel.APPLY.value

        # 初始化
        if current_tc_state is None:
            current_tc_state = TCState(
                tc_id=topic,
                status="pre_liminal",
                progress=0.0,
                confidence=0.0,
                liminal_signals=[],
                post_liminal_jump_detected=False,
                irreversible=False,
            )

        # 已 post_liminal → 不可退回
        if current_tc_state.irreversible:
            return current_tc_state

        status = current_tc_state.status
        progress = current_tc_state.progress
        signals = list(current_tc_state.liminal_signals)

        if status == "pre_liminal":
            if not has_active_misc and correct and is_l3_plus:
                # 触发 liminal signal
                signal = tc_def.get("liminal_signal", "L3+ correct with no misc")
                if signal not in signals:
                    signals.append(signal)
                # progress 增加
                progress = min(1.0, progress + 0.3)
                # 检查进入 liminal
                if progress >= threshold:
                    status = "liminal"
                current_tc_state.liminal_signals = signals
            elif correct:
                progress = min(1.0, progress + 0.05)

        elif status == "liminal":
            if correct and is_l3_plus:
                # 连续 L3+ 正确 → 累加 progress
                progress = min(1.0, progress + 0.25)
                # 检查达到 post_liminal
                streak = current_tc_state.liminal_signals.count("post_liminal_candidate")
                if progress >= 1.0 or streak >= self.post_liminal_streak:
                    status = "post_liminal"
                    current_tc_state.post_liminal_jump_detected = True
                    current_tc_state.irreversible = True
            elif not correct:
                # 答错减少 progress，但不离 liminal
                progress = max(threshold * 0.8, progress - 0.15)

        current_tc_state.status = status
        current_tc_state.progress = float(np.clip(progress, 0.0, 1.0))
        current_tc_state.confidence = float(np.clip(
            current_tc_state.confidence + 0.1, 0.0, 1.0
        ))
        return current_tc_state
