"""抗幻觉机制 2：LCA 实验设计验证（spec §4.2）.

确保 LCA 不是直接给答案，而是设计有教学法价值的干预。

Phase 4 MVP 检查项：
  1. PRACTICE 高难度（> 0.8）+ 无 scaffolding → 不合理（学生放弃风险）
  2. EXPLANATORY 无 target_skills → 不合理（无明确目标）
  3. METACOGNITIVE quantity > 1 → 警告（元认知负担）
  4. feedback_density + scaffolding 同时 > 0.8 → 认知超载风险
  5. INQUIRY 无 target_skills → 警告（探究目标不明确）
"""

from __future__ import annotations

from typing import List, Tuple

from ...lca.intervention import Intervention, InterventionType


class ExperimentDesignValidator:
    """实验设计验证器.

    用法：
        ok, issues = ExperimentDesignValidator.validate_intervention(intervention)
        if not ok:
            log_warning(issues)
    """

    PRACTICE_HIGH_DIFFICULTY_THRESHOLD = 0.8
    HIGH_DENSITY_THRESHOLD = 0.8
    METACOGNITIVE_MAX_QUANTITY = 1

    @classmethod
    def validate_intervention(cls, intervention: Intervention) -> Tuple[bool, List[str]]:
        """验证干预设计是否合理.

        Returns:
            (is_ok, issues)：
              - is_ok: True 表示全部通过；False 表示至少一项不合规
              - issues: 不合规项描述列表
        """
        issues: List[str] = []
        itype = intervention.intervention_type

        # 检查 1：PRACTICE 高难度 + 无 scaffolding
        if itype == InterventionType.PRACTICE:
            if (
                intervention.difficulty > cls.PRACTICE_HIGH_DIFFICULTY_THRESHOLD
                and intervention.scaffolding_level < 0.3
            ):
                issues.append(
                    f"PRACTICE 干预难度 {intervention.difficulty:.2f} 过高 "
                    f"但 scaffolding 仅 {intervention.scaffolding_level:.2f}，学生可能放弃"
                )

        # 检查 2：EXPLANATORY 必须有目标技能
        if itype == InterventionType.EXPLANATORY:
            if not intervention.target_skills:
                issues.append("EXPLANATORY 干预缺少 target_skills")

        # 检查 3：METACOGNITIVE 不应大量堆叠
        if itype == InterventionType.METACOGNITIVE:
            if intervention.quantity > cls.METACOGNITIVE_MAX_QUANTITY:
                issues.append(
                    f"METACOGNITIVE 干预数量 {intervention.quantity} > {cls.METACOGNITIVE_MAX_QUANTITY}，"
                    f"可能造成认知负担"
                )

        # 检查 4：feedback + scaffolding 同时过高 → 认知超载
        if (
            intervention.feedback_density > cls.HIGH_DENSITY_THRESHOLD
            and intervention.scaffolding_level > cls.HIGH_DENSITY_THRESHOLD
        ):
            issues.append(
                f"feedback_density {intervention.feedback_density:.2f} + "
                f"scaffolding_level {intervention.scaffolding_level:.2f} 同时过高，"
                f"可能认知超载"
            )

        # 检查 5：INQUIRY 缺目标技能 → 警告
        if itype == InterventionType.INQUIRY and not intervention.target_skills:
            issues.append("INQUIRY 干预缺少 target_skills，探究目标不明确")

        return len(issues) == 0, issues


__all__ = ["ExperimentDesignValidator"]