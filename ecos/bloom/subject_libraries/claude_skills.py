"""Bloom Goal Library — Claude Skills 学习目标.

对应 ECA/wu-ecos README.md §案例约定。

达标线（4 闸）：
  ① TC_skill 跨越
  ② Bloom: Understand ≥ 0.85 AND Apply ≥ 0.75
  ③ Misconception 清零（M1-M5 全部消除）
  ④ C 是"挣来的"（伪置信 = false）

5 条 Bloom Goal，映射 L1 Remember → L4 Analyze（Evaluate/Create MVP 不评估）。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from ...cta.belief_state import BloomLevel


class ClaudeSkillsTopic(Enum):
    SKILL_DEFINITION = "claude_skills.definition"
    SKILL_DESCRIPTION = "claude_skills.description"
    SKILL_LOADING = "claude_skills.loading"
    SKILL_PRACTICE = "claude_skills.practice"
    SKILL_SCOPING = "claude_skills.scoping"


@dataclass(frozen=True)
class BloomGoalEntry:
    """单条 Bloom Goal（知识点 × Bloom 层）。

    Attributes:
        goal_id: 唯一标识，如 "claude_skills.definition-L2"
        topic: 知识点 ID
        bloom_level: Bloom 认知层级
        description: 目标的自然语言描述
        success_criteria: 可观测的成功标准
        prerequisite_goals: 前置目标 ID
        typical_duration_days: 典型达成周期（估计值）
    """
    goal_id: str
    topic: str
    bloom_level: BloomLevel
    description: str
    success_criteria: str
    prerequisite_goals: tuple[str, ...]
    typical_duration_days: int


class ClaudeSkillsBloomLibrary:
    """Claude Skills Bloom Goal 库（5 topic × 4 layer = 20 条）。

    对应 ECA/wu-ecos README.md §案例约定。

    用法：
        library = ClaudeSkillsBloomLibrary()
        goals = library.get_goals_by_topic("claude_skills.definition")
    """

    _entries: ClassVar[list[BloomGoalEntry]] = [
        # ── Topic: Skill 定义 ────────────────────────────────────
        BloomGoalEntry(
            goal_id="claude_skills.definition-L1",
            topic=ClaudeSkillsTopic.SKILL_DEFINITION.value,
            bloom_level=BloomLevel.REMEMBER,
            description="记忆 Skill 的定义：按 description 相关性自主加载的能力单元",
            success_criteria="能完整复述 Skill 的定义，说出它和斜杠命令/MCP Server 的基本区别",
            prerequisite_goals=(),
            typical_duration_days=1,
        ),
        BloomGoalEntry(
            goal_id="claude_skills.definition-L2",
            topic=ClaudeSkillsTopic.SKILL_DEFINITION.value,
            bloom_level=BloomLevel.UNDERSTAND,
            description="理解 Skill 的核心机制：description 是给 LLM 看的指令，LLM 根据相关性自主决定加载",
            success_criteria="能用自己的话解释为什么 Skill 不等于斜杠命令、不等于 MCP Server、不等于 hook",
            prerequisite_goals=("claude_skills.definition-L1",),
            typical_duration_days=2,
        ),
        BloomGoalEntry(
            goal_id="claude_skills.definition-L3",
            topic=ClaudeSkillsTopic.SKILL_DEFINITION.value,
            bloom_level=BloomLevel.APPLY,
            description="能在具体场景中判断是否应该使用 Skill，给出理由",
            success_criteria="给定 3 个场景，能判断哪些适合用 Skill、哪些不适合，并说明理由",
            prerequisite_goals=("claude_skills.definition-L2",),
            typical_duration_days=3,
        ),
        BloomGoalEntry(
            goal_id="claude_skills.definition-L4",
            topic=ClaudeSkillsTopic.SKILL_DEFINITION.value,
            bloom_level=BloomLevel.ANALYZE,
            description="分析 Skill 与其他类似概念（MCP Server / 斜杠命令 / Hook / Prompt 模板）的本质差异",
            success_criteria="能写出 Skill 与上述 4 个概念的对比表，指出每个概念的加载机制和适用场景",
            prerequisite_goals=("claude_skills.definition-L3",),
            typical_duration_days=5,
        ),
        # ── Topic: Skill Description ───────────────────────────
        BloomGoalEntry(
            goal_id="claude_skills.description-L1",
            topic=ClaudeSkillsTopic.SKILL_DESCRIPTION.value,
            bloom_level=BloomLevel.REMEMBER,
            description="记忆 Skill description 的基本结构要素",
            success_criteria="能列出 description 的核心组成部分（name / instructions / description）",
            prerequisite_goals=(),
            typical_duration_days=1,
        ),
        BloomGoalEntry(
            goal_id="claude_skills.description-L2",
            topic=ClaudeSkillsTopic.SKILL_DESCRIPTION.value,
            bloom_level=BloomLevel.UNDERSTAND,
            description="理解 description 是给 LLM 的指令，不是给用户的说明",
            success_criteria="能说明 description 的受众是 LLM 而非用户，能区分 instructions 和 description 的作用",
            prerequisite_goals=("claude_skills.description-L1",),
            typical_duration_days=2,
        ),
        BloomGoalEntry(
            goal_id="claude_skills.description-L3",
            topic=ClaudeSkillsTopic.SKILL_DESCRIPTION.value,
            bloom_level=BloomLevel.APPLY,
            description="能根据任务需求写出质量合格的 Skill description",
            success_criteria="给定一个具体任务，能写出包含清晰 name / instructions / description 的 Skill，能被 LLM 正确加载",
            prerequisite_goals=("claude_skills.description-L2",),
            typical_duration_days=3,
        ),
        BloomGoalEntry(
            goal_id="claude_skills.description-L4",
            topic=ClaudeSkillsTopic.SKILL_DESCRIPTION.value,
            bloom_level=BloomLevel.ANALYZE,
            description="分析 Skill description 质量对加载准确性的影响，能识别低质量 description 的问题",
            success_criteria="给定 3 个有问题的 description，能指出每个的问题所在并提出改进方案",
            prerequisite_goals=("claude_skills.description-L3",),
            typical_duration_days=5,
        ),
        # ── Topic: Skill Loading ────────────────────────────────
        BloomGoalEntry(
            goal_id="claude_skills.loading-L1",
            topic=ClaudeSkillsTopic.SKILL_LOADING.value,
            bloom_level=BloomLevel.REMEMBER,
            description="记忆 Skill 加载的基本条件：description 相关性触发加载",
            success_criteria="能说出 Skill 加载的基本触发条件",
            prerequisite_goals=(),
            typical_duration_days=1,
        ),
        BloomGoalEntry(
            goal_id="claude_skills.loading-L2",
            topic=ClaudeSkillsTopic.SKILL_LOADING.value,
            bloom_level=BloomLevel.UNDERSTAND,
            description="理解 Skill 加载是概率性的、由 LLM 自主判断，不是确定性规则匹配",
            success_criteria="能解释 Skill 加载为什么不是确定性的，能举出一个加载结果不符合预期的例子",
            prerequisite_goals=("claude_skills.loading-L1",),
            typical_duration_days=2,
        ),
        BloomGoalEntry(
            goal_id="claude_skills.loading-L3",
            topic=ClaudeSkillsTopic.SKILL_LOADING.value,
            bloom_level=BloomLevel.APPLY,
            description="能通过调整 description 改善 Skill 的加载准确性",
            success_criteria="给定一个加载不准确的 Skill，能通过改写 description 提高加载准确率",
            prerequisite_goals=("claude_skills.loading-L2",),
            typical_duration_days=3,
        ),
        BloomGoalEntry(
            goal_id="claude_skills.loading-L4",
            topic=ClaudeSkillsTopic.SKILL_LOADING.value,
            bloom_level=BloomLevel.ANALYZE,
            description="分析多 Skill 共存时的加载竞争与优先级问题",
            success_criteria="能分析当多个 Skill description 都部分匹配时，LLM 如何做加载决策，能提出多 Skill 场景下的描述优化策略",
            prerequisite_goals=("claude_skills.loading-L3",),
            typical_duration_days=5,
        ),
        # ── Topic: Skill Practice ──────────────────────────────
        BloomGoalEntry(
            goal_id="claude_skills.practice-L1",
            topic=ClaudeSkillsTopic.SKILL_PRACTICE.value,
            bloom_level=BloomLevel.REMEMBER,
            description="记忆常见 Skill 的使用场景",
            success_criteria="能列出 3 个以上 Skill 的典型使用场景",
            prerequisite_goals=(),
            typical_duration_days=1,
        ),
        BloomGoalEntry(
            goal_id="claude_skills.practice-L2",
            topic=ClaudeSkillsTopic.SKILL_PRACTICE.value,
            bloom_level=BloomLevel.UNDERSTAND,
            description="理解 Skill 在实际工作流中的定位（不是替代思考，而是扩展能力边界）",
            success_criteria="能说明 Skill 在什么情况下是最佳选择，在什么情况下应该用普通对话",
            prerequisite_goals=("claude_skills.practice-L1",),
            typical_duration_days=2,
        ),
        BloomGoalEntry(
            goal_id="claude_skills.practice-L3",
            topic=ClaudeSkillsTopic.SKILL_PRACTICE.value,
            bloom_level=BloomLevel.APPLY,
            description="能在真实任务中主动使用 Skill，提升任务完成质量和效率",
            success_criteria="在复杂任务中能识别出适合用 Skill 的时机，并正确调用",
            prerequisite_goals=("claude_skills.practice-L2",),
            typical_duration_days=5,
        ),
        BloomGoalEntry(
            goal_id="claude_skills.practice-L4",
            topic=ClaudeSkillsTopic.SKILL_PRACTICE.value,
            bloom_level=BloomLevel.ANALYZE,
            description="分析 Skill 使用效果的评估维度，能判断 Skill 是否真正提升了任务质量",
            success_criteria="能提出一套评估 Skill 有效性的指标，并能对实际使用的 Skill 进行效果分析",
            prerequisite_goals=("claude_skills.practice-L3",),
            typical_duration_days=5,
        ),
        # ── Topic: Skill Scoping ───────────────────────────────
        BloomGoalEntry(
            goal_id="claude_skills.scoping-L1",
            topic=ClaudeSkillsTopic.SKILL_SCOPING.value,
            bloom_level=BloomLevel.REMEMBER,
            description="记忆 Skill 的边界概念：一个 Skill 应该对应一个明确的能力域",
            success_criteria="能说明为什么 Skill 不应该做得太泛或太窄",
            prerequisite_goals=(),
            typical_duration_days=1,
        ),
        BloomGoalEntry(
            goal_id="claude_skills.scoping-L2",
            topic=ClaudeSkillsTopic.SKILL_SCOPING.value,
            bloom_level=BloomLevel.UNDERSTAND,
            description="理解 Skill 边界设计的两个极端：过宽导致加载不稳定，过窄导致使用场景局限",
            success_criteria="能解释为什么 description 太泛会导致误加载、太窄会导致有用 Skill 加载不到",
            prerequisite_goals=("claude_skills.scoping-L1",),
            typical_duration_days=2,
        ),
        BloomGoalEntry(
            goal_id="claude_skills.scoping-L3",
            topic=ClaudeSkillsTopic.SKILL_SCOPING.value,
            bloom_level=BloomLevel.APPLY,
            description="能根据任务需求合理设计 Skill 的边界",
            success_criteria="给定一个具体任务域，能设计出边界清晰、description 准确的 Skill 方案",
            prerequisite_goals=("claude_skills.scoping-L2",),
            typical_duration_days=3,
        ),
        BloomGoalEntry(
            goal_id="claude_skills.scoping-L4",
            topic=ClaudeSkillsTopic.SKILL_SCOPING.value,
            bloom_level=BloomLevel.ANALYZE,
            description="分析 Skill 与 Agent 边界的关系，能判断哪些适合用 Skill 封装，哪些适合用 Agent 封装",
            success_criteria="能提出 Skill 和 Agent 的分工原则，并能对现有能力进行分类判断",
            prerequisite_goals=("claude_skills.scoping-L3",),
            typical_duration_days=5,
        ),
    ]

    def __init__(self) -> None:
        self._by_id: dict[str, BloomGoalEntry] = {e.goal_id: e for e in self._entries}

    def get(self, goal_id: str) -> BloomGoalEntry | None:
        return self._by_id.get(goal_id)

    def get_goals_by_topic(self, topic: str) -> list[BloomGoalEntry]:
        return [e for e in self._entries if e.topic == topic]

    def get_goals_by_level(self, level: BloomLevel) -> list[BloomGoalEntry]:
        return [e for e in self._entries if e.bloom_level == level]

    def all_entries(self) -> list[BloomGoalEntry]:
        return list(self._entries)
