"""Policy 对比框架 —— v0.83.0-c Evaluation Engine 第 2 个 evaluator.

对应 kernel-mapping §1.5: "Policy 对比 (AB test LinUCB vs Thompson)".

v0.83.0-c 范围:
  - 仅 1 个 Policy 真实实现 (LinUCB, 通过 LCAEngine.policy_learner)
  - PolicyABTest 框架: 接受 policy_id (string), 委派给 LCAEngine
  - "linucb_baseline" 对比: 同 LinUCB 自身 (假 baseline, 永远 winner=None)
  - 未来 v0.83.x: 加 Thompson Sampling 后, 真 A/B test 才有意义

设计:
  - PolicyABTest 是 policy_id-agnostic, 通过 kwargs 注入 LCAEngine
  - ABTestResult 含 winner 字段 ("a" / "b" / None)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from ..cta.belief_state import BeliefState

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ABTestResult 数据类
# ---------------------------------------------------------------------------

@dataclass
class ABTestResult:
    """Policy AB test 结果.

    Attributes:
        student_id:     学生 ID
        policy_a:       Policy A 标识 (e.g. "linucb")
        policy_b:       Policy B 标识 (e.g. "linucb_baseline")
        mean_reward_a:  Policy A 平均 reward (LinUCB 历史 reward 均值)
        mean_reward_b:  Policy B 平均 reward
        n_a:            Policy A 样本数
        n_b:            Policy B 样本数
        winner:         "a" / "b" / None (不显著)
    """

    student_id: str
    policy_a: str
    policy_b: str
    mean_reward_a: float
    mean_reward_b: float
    n_a: int
    n_b: int
    winner: Optional[str]

    def to_dict(self) -> dict:
        return {
            "student_id": self.student_id,
            "policy_a": self.policy_a,
            "policy_b": self.policy_b,
            "mean_reward_a": self.mean_reward_a,
            "mean_reward_b": self.mean_reward_b,
            "n_a": self.n_a,
            "n_b": self.n_b,
            "winner": self.winner,
        }


# ---------------------------------------------------------------------------
# PolicyABTest 类
# ---------------------------------------------------------------------------

class PolicyABTest:
    """Policy 对比框架 (v0.83.0-c).

    用法:
        ab = PolicyABTest(lca_engine=engine)
        result = ab.compare("student_001", "linucb", "linucb_baseline")
        # -> ABTestResult(mean_reward_a=0.65, mean_reward_b=0.65, n_a=20, n_b=20, winner=None)

        # 未来 v0.83.x: 加 Thompson Sampling 后
        # result = ab.compare("student_001", "linucb", "thompson")
        # -> ABTestResult(mean_reward_a=0.65, mean_reward_b=0.72, n_a=20, n_b=20, winner="b")

    v0.83.0-c 限制:
      - 仅支持 "linucb" (Policy A) vs "linucb_baseline" (Policy B = 自身)
      - 无真 A/B test 能力 (v0.83.x 引入 Thompson Sampling 后, 框架自然扩展)
    """

    def __init__(self, lca_engine: Optional["LCAEngine"] = None):
        # lca_engine optional, 不传则 ab test 只能跑 baseline (返 winner=None)
        self.lca_engine = lca_engine

    def compare(
        self,
        student_id: str,
        policy_a: str,
        policy_b: str,
        events: Optional[List] = None,
    ) -> ABTestResult:
        """对比 Policy A 和 Policy B 在 student_id 的预期 reward.

        Args:
            student_id: 学生 ID
            policy_a:   Policy A 标识 (e.g. "linucb")
            policy_b:   Policy B 标识 (e.g. "linucb_baseline" / 未来 "thompson")
            events:     可选, 历史事件 (v0.83.0-c 未用, 未来真 A/B test 用)

        Returns:
            ABTestResult

        实现:
          - 当前 v0.83.0-c 仅有 LinUCB, 无法真 A/B test
          - 占位: 都返 policy_a 自身统计 (mean_reward_a 来自 LCAEngine, mean_reward_b 同)
          - 未来 v0.83.x: Thompson Sampling 接入后, 此处真正 replay 两条 Policy

        防御性: 任何异常兜底 _log.warning + 返 winner=None
        """
        if policy_a == policy_b:
            _log.debug(
                "PolicyABTest.compare: policy_a == policy_b (%s), 返 winner=None",
                policy_a,
            )
            return ABTestResult(
                student_id=student_id,
                policy_a=policy_a,
                policy_b=policy_b,
                mean_reward_a=0.0,
                mean_reward_b=0.0,
                n_a=0,
                n_b=0,
                winner=None,
            )

        if self.lca_engine is None:
            _log.warning(
                "PolicyABTest: lca_engine 未注入, 无法跑 A/B test, 返 winner=None",
            )
            return ABTestResult(
                student_id=student_id,
                policy_a=policy_a,
                policy_b=policy_b,
                mean_reward_a=0.0,
                mean_reward_b=0.0,
                n_a=0,
                n_b=0,
                winner=None,
            )

        try:
            # v0.83.0-c: 仅支持 linucb / linucb_baseline (两者等价, 永远平局)
            # 未来 v0.83.x: Thompson Sampling 接入, 真正 replay
            supported = ("linucb", "linucb_baseline", "thompson")
            if policy_a not in supported or policy_b not in supported:
                _log.warning(
                    "PolicyABTest: 不支持的 policy (a=%s, b=%s), 返 winner=None",
                    policy_a, policy_b,
                )
                return ABTestResult(
                    student_id=student_id,
                    policy_a=policy_a,
                    policy_b=policy_b,
                    mean_reward_a=0.0,
                    mean_reward_b=0.0,
                    n_a=0,
                    n_b=0,
                    winner=None,
                )

            # 占位: mean_reward 来自 LCAEngine 历史 reward (来自 dump_state.intervention_history)
            # 简化: 用 _last_intervention 估计 (v0.83.0-c 暂用 LCAEngine 内干预历史)
            n_a = len(self.lca_engine.intervention_history.get(student_id, []))
            n_b = n_a  # 简化: 同一 Policy 不同 policy_id, 共享样本

            # 计算 mean reward (从 intervention_history 估算)
            history = self.lca_engine.intervention_history.get(student_id, [])
            if history:
                mean_reward_a = sum(
                    iv.expected_gain for iv in history
                ) / len(history)
                mean_reward_b = mean_reward_a
            else:
                mean_reward_a = 0.0
                mean_reward_b = 0.0

            return ABTestResult(
                student_id=student_id,
                policy_a=policy_a,
                policy_b=policy_b,
                mean_reward_a=mean_reward_a,
                mean_reward_b=mean_reward_b,
                n_a=n_a,
                n_b=n_b,
                winner=None,  # v0.83.0-c 永远 None (无真 A/B)
            )
        except Exception:
            _log.warning(
                "PolicyABTest.compare 失败 (student=%s, a=%s, b=%s)",
                student_id, policy_a, policy_b, exc_info=True,
            )
            return ABTestResult(
                student_id=student_id,
                policy_a=policy_a,
                policy_b=policy_b,
                mean_reward_a=0.0,
                mean_reward_b=0.0,
                n_a=0,
                n_b=0,
                winner=None,
            )


__all__ = [
    "PolicyABTest",
    "ABTestResult",
]
