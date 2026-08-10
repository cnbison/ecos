"""Goal 完成判定 —— v0.83.0-c Evaluation Engine 第 3 个 evaluator.

对应 kernel-mapping §1.5: "Goal completion 判定 (e.g. K ≥ 0.7 + Bloom L3 + TC 通过)".

v0.83.0-c 范围: 支持 3 类 Goal
  - K.mastery >= <threshold>     (5D mastery_prob 阈值)
  - Bloom.L3+ achieved          (Bloom apply/analyze/evaluate/create >= threshold)
  - TC.<tc_id> pass              (TC status = "post_liminal")

设计:
  - GoalCompletion 是纯函数式 (无 side effect)
  - GoalStatus 输出完整 (completed + current/target + missing_dimensions)
  - Goal ID 字符串格式: "K.mastery>=0.7" / "Bloom.L3>=0.6" / "TC.python_variables.pass"
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

from ..cta.belief_state import BeliefState

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Goal Status 数据类
# ---------------------------------------------------------------------------

@dataclass
class GoalStatus:
    """Goal 完成状态.

    Attributes:
        goal_id:             Goal 标识 (e.g. "K.mastery>=0.7")
        completed:           True / False
        current_value:       当前数值 (mastery_prob / bloom_layer / tc_status 编码)
        target_value:        目标数值
        missing_dimensions:  List[str]  (e.g. ["K.mastery_prob=0.6<0.7", "Bloom.apply=0.5<0.6"])
    """

    goal_id: str
    completed: bool
    current_value: float
    target_value: float
    missing_dimensions: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "goal_id": self.goal_id,
            "completed": self.completed,
            "current_value": self.current_value,
            "target_value": self.target_value,
            "missing_dimensions": list(self.missing_dimensions),
        }


# ---------------------------------------------------------------------------
# GoalCompletion 类
# ---------------------------------------------------------------------------

class GoalCompletion:
    """Goal 完成判定 (v0.83.0-c).

    用法:
        gc = GoalCompletion()
        status = gc.check(state, "K.mastery>=0.7")
        # -> GoalStatus(completed=False, current_value=0.6, target_value=0.7,
        #                missing_dimensions=["K.mastery_prob=0.6<0.7"])

        status = gc.check(state, "Bloom.L3>=0.6")
        # -> Bloom L3+ (apply + analyze + evaluate + create) 全部 >= 0.6 才完成

        status = gc.check(state, "TC.python_variables.pass")
        # -> TC.post_liminal (status == "post_liminal") 才完成

    支持的 Goal ID 格式 (regex):
      - r"K\\.mastery>=([\\d.]+)"     -> K 维度 mastery_prob
      - r"Bloom\\.L(\\d+)>=([\\d.]+)"  -> Bloom 层级 (L3+) 平均 mastery
      - r"TC\\.([\\w_]+)\\.pass"        -> TC status
      - 其他: 返 GoalStatus(completed=False, current=0.0, target=0.0, missing=["unknown_goal_format"])
    """

    def check(self, state: BeliefState, goal_id: str) -> GoalStatus:
        """判定 Goal 是否完成.

        Args:
            state:   BeliefState (5D + Bloom + TC)
            goal_id: Goal 标识

        Returns:
            GoalStatus (含 completed / current_value / target_value / missing_dimensions)
        """
        # K.mastery >= X
        m = re.match(r"^K\.mastery>=([\d.]+)$", goal_id)
        if m:
            return self._check_k_mastery(state, float(m.group(1)), goal_id)

        # Bloom.L<N>>=X (L3 = apply, L4 = analyze, L5 = evaluate, L6 = create)
        m = re.match(r"^Bloom\.L(\d+)>=([\d.]+)$", goal_id)
        if m:
            level = int(m.group(1))
            threshold = float(m.group(2))
            return self._check_bloom(state, level, threshold, goal_id)

        # TC.<tc_id>.pass
        m = re.match(r"^TC\.([\w_]+)\.pass$", goal_id)
        if m:
            tc_id = m.group(1)
            return self._check_tc(state, tc_id, goal_id)

        # 未知 Goal 格式
        _log.warning("GoalCompletion: 未知 goal_id 格式 goal_id=%s, 返未完成", goal_id)
        return GoalStatus(
            goal_id=goal_id,
            completed=False,
            current_value=0.0,
            target_value=0.0,
            missing_dimensions=[f"unknown_goal_format: {goal_id}"],
        )

    # ---------------------------------------------------------------
    # 内部: 3 类 Goal 检查
    # ---------------------------------------------------------------

    @staticmethod
    def _check_k_mastery(state: BeliefState, threshold: float, goal_id: str) -> GoalStatus:
        current = float(state.K.mastery_prob)
        completed = current >= threshold
        return GoalStatus(
            goal_id=goal_id,
            completed=completed,
            current_value=current,
            target_value=threshold,
            missing_dimensions=[] if completed else [
                f"K.mastery_prob={current:.3f}<{threshold}",
            ],
        )

    @staticmethod
    def _check_bloom(state: BeliefState, level: int, threshold: float, goal_id: str) -> GoalStatus:
        """Bloom L<N>+=threshold: 取 L<N>..L6 的平均 mastery_prob (>=threshold)."""
        # level 1-6 对应 bloom_profile 字段
        bp = state.bloom_profile
        layer_map = {
            1: bp.remember,
            2: bp.understand,
            3: bp.apply,
            4: bp.analyze,
            5: bp.evaluate,
            6: bp.create,
        }
        if level < 1 or level > 6:
            return GoalStatus(
                goal_id=goal_id,
                completed=False,
                current_value=0.0,
                target_value=threshold,
                missing_dimensions=[f"Bloom level={level} 超出 [1,6]"],
            )
        # 计算 L<level>..L6 平均
        current_values = [layer_map[L] for L in range(level, 7)]
        current = sum(current_values) / len(current_values)
        completed = current >= threshold
        missing = [
            f"Bloom.L{level}+_avg={current:.3f}<{threshold}"
        ] if not completed else []
        return GoalStatus(
            goal_id=goal_id,
            completed=completed,
            current_value=current,
            target_value=threshold,
            missing_dimensions=missing,
        )

    @staticmethod
    def _check_tc(state: BeliefState, tc_id: str, goal_id: str) -> GoalStatus:
        if tc_id not in state.C.tc_states:
            return GoalStatus(
                goal_id=goal_id,
                completed=False,
                current_value=0.0,
                target_value=1.0,  # pass = 1.0
                missing_dimensions=[f"TC.{tc_id} 不在 C.tc_states 中"],
            )
        tc = state.C.tc_states[tc_id]
        # pass: status == "post_liminal"
        passed = tc.status == "post_liminal"
        # 编码: post_liminal=1.0, liminal=0.5, pre_liminal=0.0
        status_value = {
            "post_liminal": 1.0,
            "liminal": 0.5,
            "pre_liminal": 0.0,
        }.get(tc.status, 0.0)
        return GoalStatus(
            goal_id=goal_id,
            completed=passed,
            current_value=status_value,
            target_value=1.0,
            missing_dimensions=[] if passed else [
                f"TC.{tc_id} status={tc.status} (需 post_liminal)",
            ],
        )


__all__ = [
    "GoalCompletion",
    "GoalStatus",
]
