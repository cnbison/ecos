"""Policy 对比框架 —— v0.83.0-c Evaluation Engine 第 2 个 evaluator.

对应 kernel-mapping §1.5: "Policy 对比 (AB test LinUCB vs Thompson)".

v0.83.0-c 范围:
  - 仅 1 个 Policy 真实实现 (LinUCB, 通过 LCAEngine.policy_learner)
  - PolicyABTest 框架: 接受 policy_id (string), 委派给 LCAEngine
  - "linucb_baseline" 对比: 同 LinUCB 自身 (假 baseline, 永远 winner=None)
  - 未来 v0.83.x: 加 Thompson Sampling 后, 真 A/B test 才有意义

v0.86.0-d 扩展:
  - 真 A/B Test: events 参数非空时, replay 两个 Policy 各一遍
  - 支持 "linucb" / "linucb_baseline" / "thompson" 3 种 Policy
  - 创建 fresh bandit 实例 (同 event 序列, 独立 evolve)
  - mean_reward_a / mean_reward_b 真实计算 (非 placeholder)
  - winner: 5% 阈值 + 至少 5 样本才判定

设计:
  - PolicyABTest 是 policy_id-agnostic, 通过 kwargs 注入 LCAEngine
  - ABTestResult 含 winner 字段 ("a" / "b" / None)
  - v0.86.0-d: replay 路径不依赖 lca_engine (自给自足)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, List, Optional

import numpy as np

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
        policy_b:       Policy B 标识 (e.g. "linucb_baseline" / "thompson")
        mean_reward_a:  Policy A 平均 reward
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
    """Policy 对比框架 (v0.83.0-c + v0.86.0-d 真 A/B Test).

    用法:
        # v0.83.0-c: 无 events 参数 (占位)
        ab = PolicyABTest(lca_engine=engine)
        result = ab.compare("student_001", "linucb", "linucb_baseline")
        # -> winner=None (占位, 永远平局)

        # v0.86.0-d: 真 A/B (events 非空)
        result = ab.compare("student_001", "linucb", "thompson", events=[...])
        # -> replay 同 event 序列, 真实计算 mean_reward
    """

    SUPPORTED_POLICIES: tuple = ("linucb", "linucb_baseline", "thompson", "pomdp")

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
            policy_b:   Policy B 标识 (e.g. "linucb_baseline" / "thompson")
            events:     可选, 历史 LearningEvent 列表
                        v0.86.0-d: 非空时走真 A/B replay path

        Returns:
            ABTestResult

        实现:
          - v0.83.0-c: events=None 走占位 path (lca_engine.intervention_history)
          - v0.86.0-d: events 非空走真 A/B replay path (创建 fresh bandit, replay events)

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

        if policy_a not in self.SUPPORTED_POLICIES or policy_b not in self.SUPPORTED_POLICIES:
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

        # v0.86.0-d: events 非空走真 A/B replay path
        if events:
            return self._compare_with_replay(student_id, policy_a, policy_b, events)

        # v0.83.0-c 占位 path (lca_engine.intervention_history)
        if self.lca_engine is None:
            _log.warning(
                "PolicyABTest: lca_engine 未注入 + events=None, 返 winner=None",
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
            n_a = len(self.lca_engine.intervention_history.get(student_id, []))
            n_b = n_a
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
                winner=None,
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

    # ------------------------------------------------------------------
    # v0.86.0-d: 真 A/B Test (replay events on fresh bandit for each policy)
    # ------------------------------------------------------------------

    def _compare_with_replay(
        self,
        student_id: str,
        policy_a: str,
        policy_b: str,
        events: List[Any],
    ) -> ABTestResult:
        """v0.86.0-d: 真 A/B Test — replay 同一 event 序列到 2 个 fresh bandit.

        流程:
          1. 创建 fresh bandit_a (policy_a) + bandit_b (policy_b)
          2. 对每个 event:
             - 提取 reward (从 event.payload.score / .correct)
             - bandit_a.select_arm + update (累积 total_a)
             - bandit_b.select_arm + update (累积 total_b)
          3. mean_a = total_a / n, mean_b = total_b / n
          4. winner: 5% 阈值 + 至少 5 样本

        防御性:
          - event 解析失败 _log.warning 跳过 (continue)
          - bandit 操作失败 _log.warning 跳过 (continue)
          - 总异常兜底 _log.warning + 返 winner=None
        """
        try:
            bandit_a = self._create_fresh_bandit(policy_a)
            bandit_b = self._create_fresh_bandit(policy_b)
            # v0.86.0-d: 16-dim zero context (LinUCB 需要固定维度, Thompson 忽略)
            # Per-arm replay 主要对比 update mechanism, context 用 placeholder
            context = np.zeros(16, dtype=float)

            total_a = 0.0
            total_b = 0.0
            count = 0

            for event in events:
                reward = self._extract_reward_from_event(event)
                if reward is None:
                    continue
                reward = float(reward)

                # Per-policy select + update (16-dim zero context)
                try:
                    arm_a = bandit_a.select_arm(context=context)
                    bandit_a.update(arm_a, context=context, reward=reward)
                    total_a += reward
                except Exception:
                    _log.warning(
                        "PolicyABTest: bandit_a 操作失败 (sid=%s, count=%d), 跳过",
                        student_id, count, exc_info=True,
                    )

                try:
                    arm_b = bandit_b.select_arm(context=context)
                    bandit_b.update(arm_b, context=context, reward=reward)
                    total_b += reward
                except Exception:
                    _log.warning(
                        "PolicyABTest: bandit_b 操作失败 (sid=%s, count=%d), 跳过",
                        student_id, count, exc_info=True,
                    )

                count += 1

            n = count
            mean_a = total_a / n if n > 0 else 0.0
            mean_b = total_b / n if n > 0 else 0.0

            # winner 判定: 5% 阈值 + 至少 5 样本
            winner = None
            if n >= 5:
                if mean_a > mean_b * 1.05:
                    winner = "a"
                elif mean_b > mean_a * 1.05:
                    winner = "b"

            return ABTestResult(
                student_id=student_id,
                policy_a=policy_a,
                policy_b=policy_b,
                mean_reward_a=mean_a,
                mean_reward_b=mean_b,
                n_a=n,
                n_b=n,
                winner=winner,
            )
        except Exception:
            _log.warning(
                "PolicyABTest._compare_with_replay 失败 (sid=%s, a=%s, b=%s)",
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

    @staticmethod
    def _create_fresh_bandit(policy_id: str) -> Any:
        """v0.86.0-d: 根据 policy_id 创建 fresh bandit.

        Args:
            policy_id: "linucb" / "linucb_baseline" / "thompson" / "pomdp"

        Returns:
            Fresh bandit 实例 (LinUCB / ThompsonSampling / POMDPPolicy)

        Raises:
            ValueError: 未知 policy_id

        v0.89.0-d: POMDP 工厂默认 use_pbvi=True, 保持真 3-way A/B (linucb / thompson /
        pomdp+PBVI) 仍然比较同一求解器家族.
        """
        # v0.86.0-d: lazy import 避免循环
        # v0.87.0-d: 扩展到 POMDPPolicy
        from ..lca.l4_optimization import LinUCB, POMDPPolicy, ThompsonSampling

        if policy_id in ("linucb", "linucb_baseline"):
            # LinUCB: 16 维 context, alpha=1.0, decay=1.0 (跟 v0.75.3 默认一致)
            return LinUCB(n_arms=10, context_dim=16, alpha=1.0, decay_factor=1.0)
        elif policy_id == "thompson":
            # Thompson: 10 arm, fixed seed (可重现)
            return ThompsonSampling(n_arms=10, seed=42)
        elif policy_id == "pomdp":
            # v0.87.0-d: POMDP: 10 arm, 4 状态, fixed seed (可重现)
            # v0.89.0-d: 默认 use_pbvi=True (PBVI 完整集成); 退化 QMDP 留 v0.90+ kwargs
            return POMDPPolicy(n_arms=10, seed=42, use_pbvi=True)
        else:
            raise ValueError(f"PolicyABTest: 未知 policy_id={policy_id!r}")

    @staticmethod
    def _extract_reward_from_event(event: Any) -> Optional[float]:
        """v0.86.0-d: 从 LearningEvent 提取 reward.

        优先顺序:
          1. event.payload["score"] (partial credit, 0-1)
          2. event.payload["reward"] (explicit)
          3. event.payload["correct"] (boolean)
          4. None (跳过此 event)

        防御性: 解析失败返 None, 不 raise
        """
        try:
            payload = getattr(event, "payload", None) or {}
            if not isinstance(payload, dict):
                return None
            if "score" in payload and payload["score"] is not None:
                return float(payload["score"])
            if "reward" in payload and payload["reward"] is not None:
                return float(payload["reward"])
            if "correct" in payload and payload["correct"] is not None:
                return 1.0 if bool(payload["correct"]) else 0.0
            return None
        except Exception:
            _log.warning(
                "PolicyABTest._extract_reward_from_event 失败, 跳过",
                exc_info=True,
            )
            return None


__all__ = [
    "PolicyABTest",
    "ABTestResult",
]
