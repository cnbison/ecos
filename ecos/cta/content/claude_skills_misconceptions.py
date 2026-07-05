"""CTA Claude Skills Misconception Library.

对应 ECA/wu-ecos README.md §案例约定。

5 条 misconception（M1-M5），覆盖 Claude Skills 学习中的典型误解。
来源：Bisen 专家经验 + ECOS 理论框架。

M2 W3 扩展：作为 ECOS 跨领域能力的演示案例。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from ..belief_state import BloomLevel


@dataclass(frozen=True)
class MisconceptionEntry:
    """单条 Misconception 条目.

    Attributes:
        misc_id: 唯一标识，M1-M5
        name: 短名称
        description: 1-2 句解释这个 misconception 是什么
        trigger_patterns: LLM Critic 输入的学生表述样例
        detection_keywords: 关键词匹配兜底
        skill_id: 关联知识点 ID
        correction_strategy: 修正策略 ID（LCA 据此选干预类型）
        bloom_layer: 通常触发的 Bloom 层
    """

    misc_id: str
    name: str
    description: str
    trigger_patterns: tuple[str, ...]
    detection_keywords: tuple[str, ...]
    skill_id: str
    correction_strategy: str
    bloom_layer: BloomLevel


class ClaudeSkillsMisconceptionLibrary:
    """Claude Skills Misconception 库（5 条）。

    来源：ECA/wu-ecos README.md §案例约定。

    用法：
        library = ClaudeSkillsMisconceptionLibrary()
        entry = library.get("M1")
    """

    _entries: ClassVar[list[MisconceptionEntry]] = [
        MisconceptionEntry(
            misc_id="M1",
            name="Skill 等于斜杠命令",
            description="认为 Claude Skill 就是斜杠命令（/command），不理解 Skill 是按 description 相关性自主加载的能力单元。",
            trigger_patterns=(
                "Skill 不就是 /command 吗？",
                "用 Skill 就是打 / 开头的命令吧？",
                "斜杠命令就是 Skill 的另一种说法",
            ),
            detection_keywords=("斜杠", "/command", "Slash 命令"),
            skill_id="claude_skills.definition",
            correction_strategy="deconstruct_skill_vs_slash_command",
            bloom_layer=BloomLevel.UNDERSTAND,
        ),
        MisconceptionEntry(
            misc_id="M2",
            name="Skill 等于 MCP Server",
            description="混淆 Skill 与 MCP Server，认为 Skill 是某种服务端工具或外部进程。",
            trigger_patterns=(
                "Skill 和 MCP Server 是什么关系？",
                "Skill 是不是就是调 API？",
                "MCP Server 和 Skill 有什么区别？",
            ),
            detection_keywords=("MCP", "server", "API", "外部进程"),
            skill_id="claude_skills.definition",
            correction_strategy="skill_is_local_description_not_external_server",
            bloom_layer=BloomLevel.UNDERSTAND,
        ),
        MisconceptionEntry(
            misc_id="M3",
            name="Skill 等于自动化/Hook",
            description="把 Skill 理解为自动化脚本或系统 hook，不理解它是一个 LLM 驱动的描述匹配机制。",
            trigger_patterns=(
                "Skill 是不是就是一个自动化脚本？",
                "Skill 是不是就是系统层的 hook？",
                "Skill 会在特定条件下自动触发对吧？",
            ),
            detection_keywords=("自动化", "hook", "自动触发", "脚本"),
            skill_id="claude_skills.definition",
            correction_strategy="skill_is_llm_matching_not_automation",
            bloom_layer=BloomLevel.ANALYZE,
        ),
        MisconceptionEntry(
            misc_id="M4",
            name="Skill 等于 Prompt 模板",
            description="认为 Skill 就是一个预先写好的 prompt 模板，每次调用直接填充，不理解 description 是 LLM 自己解释的。",
            trigger_patterns=(
                "Skill 就是一套写好的 prompt 模板吧？",
                "description 就是 system prompt 吗？",
                "Skill 的效果取决于 prompt 写得好不好",
            ),
            detection_keywords=("prompt", "模板", "system prompt", "填充"),
            skill_id="claude_skills.description",
            correction_strategy="skill_description_is_llm_instruction_not_template",
            bloom_layer=BloomLevel.UNDERSTAND,
        ),
        MisconceptionEntry(
            misc_id="M5",
            name="Skill 总是被加载",
            description="认为 Skill 一旦描述相关就会总是被加载，不理解加载决策由 LLM 基于相关性自主判断。",
            trigger_patterns=(
                "只要 description 匹配了，Skill 就会被调用吧？",
                "Skill 加载是确定性的，对吧？",
                "相关度够了 Skill 就一定会加载",
            ),
            detection_keywords=("总是", "一定", "确定性", "必然加载", "相关度"),
            skill_id="claude_skills.loading",
            correction_strategy="skill_loading_is_probabilistic_not_deterministic",
            bloom_layer=BloomLevel.APPLY,
        ),
    ]

    def __init__(self) -> None:
        self._by_id: dict[str, MisconceptionEntry] = {e.misc_id: e for e in self._entries}

    def get(self, misc_id: str) -> MisconceptionEntry | None:
        return self._by_id.get(misc_id)

    def all_entries(self) -> list[MisconceptionEntry]:
        return list(self._entries)
