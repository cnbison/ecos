"""CTA Python 基础 Misconception Library.

M2 战略调整（v1.1）：聚焦 Python 基础认知助手（自学者产品方向）。
LLM 充当领域专家（生成题目 + 评估 + 检测 misconception + 干预）。

8 条 misconception（M1-M8），覆盖 Python 基础学习中的典型认知障碍。

来源：Bisen 作为 Python 自学者经验 + ECOS 理论框架。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

# 供 MisconceptionDetector.detect(library_str=...) 直接注入的文本格式
PYTHON_BASICS_MISCONCEPTION_LIBRARY_STR: str = """
候选 Misconception 条目：

ID | 名称 | 描述 | 关键 trigger 样例
M1 | 变量=数学等式 | 认为赋值是声明等式成立，无法理解 x=x+1 | "x=x+1？这不是无解吗？"
M2 | x=x+1 非法 | 把赋值当数学等式，不理解先算右边再存回 | "x怎么可能等于x加1？"
M3 | for 循环 off-by-one | 对 range() 边界理解有误 | "range(5)应该是0到5吧？"
M4 | 函数必有返回值 | 无法理解 void 函数（无 return）的意义 | "没有 return 叫什么函数？"
M5 | 递归=循环 | 混淆递归与迭代，不理解 base case | "递归和 for 循环有什么区别？"
M6 | 变量=存储值的盒子 | 不理解引用语义，变量是标签非盒子 | "a和b指向同一个列表，改a就是改b？"
M7 | while 基准情形遗漏 | 死循环/无限递归的根源 | "为什么我的程序卡住了？"
M8 | 全局/局部作用域混淆 | 不理解 global 声明或局部/全局优先级 | "为什么函数里改不了外面的x？"
"""

from ..belief_state import BloomLevel


@dataclass(frozen=True)
class MisconceptionEntry:
    """单条 Misconception 条目.

    Attributes:
        misc_id: 唯一标识，M1-M8
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


class PythonBasicsMisconceptionLibrary:
    """Python 基础 Misconception 库（8 条）。

    覆盖：变量与赋值 / 循环 / 函数 / 递归 / 作用域。

    用法：
        library = PythonBasicsMisconceptionLibrary()
        entry = library.get("M1")
    """

    _entries: ClassVar[list[MisconceptionEntry]] = [
        # ─── 变量与赋值 ──────────────────────────────────────────────
        MisconceptionEntry(
            misc_id="M1",
            name="变量=数学等式",
            description="认为变量赋值是「声明等式成立」，而非「把值存入名字」。结果：无法理解 x = x + 1 这类自增语句。",
            trigger_patterns=(
                "x = x + 1？这不是无解吗？",
                "等号两边不相等，这不是错的吧？",
                "x 等于 x 加 1，这不矛盾吗？",
            ),
            detection_keywords=("等于", "等号", "无解", "矛盾", "x = x"),
            skill_id="python.variables.assignment",
            correction_strategy="variable_as_label_not_equation",
            bloom_layer=BloomLevel.UNDERSTAND,
        ),
        MisconceptionEntry(
            misc_id="M2",
            name="x=x+1 非法",
            description="把赋值语句当作数学等式，认为 x = x + 1 无解或矛盾，无法理解「先算右边再存回左边」的执行逻辑。",
            trigger_patterns=(
                "x 怎么可能等于 x 加 1？",
                "这个式子不成立吧？",
                "赋值和等号不是一回事？",
                "x = x + 1 报错啊，为什么？",
            ),
            detection_keywords=("x = x + 1", "自增", "赋值", "先算", "存回"),
            skill_id="python.variables.assignment",
            correction_strategy="assignment_vs_equality_explanation",
            bloom_layer=BloomLevel.APPLY,
        ),
        MisconceptionEntry(
            misc_id="M6",
            name="变量=存储值的盒子",
            description="把变量理解为「装东西的盒子」，无法理解引用语义——变量是标签，指向对象，而非对象本身。",
            trigger_patterns=(
                "变量就是一个小盒子对吧？",
                "我把列表传给函数，函数里改了我外面的列表也变了？",
                "a 和 b 指向同一个列表，改 a 也就是改 b？",
                "赋值就是拷贝一份对吧？",
            ),
            detection_keywords=("盒子", "拷贝", "引用", "指向", "同一个"),
            skill_id="python.variables.reference",
            correction_strategy="variable_as_name_tag_not_box",
            bloom_layer=BloomLevel.UNDERSTAND,
        ),
        MisconceptionEntry(
            misc_id="M8",
            name="全局/局部作用域混淆",
            description="不理解函数内部对全局变量的访问规则，常见错误：在函数内直接修改全局变量而不声明 global，或混淆局部变量与全局变量同名时的优先级。",
            trigger_patterns=(
                "为什么函数里改不了外面的 x？",
                "global 是干嘛用的？",
                "我在函数里给 x 赋值，为什么外面的 x 没变？",
                "全局变量和局部变量有什么区别？",
                "明明在外层定义了，为什么说没定义？",
            ),
            detection_keywords=("全局", "局部", "global", "作用域", "改不了"),
            skill_id="python.scope.global_local",
            correction_strategy="scope_ namespace_explanation",
            bloom_layer=BloomLevel.APPLY,
        ),
        # ─── 循环 ─────────────────────────────────────────────────
        MisconceptionEntry(
            misc_id="M3",
            name="for 循环 off-by-one",
            description="对 Python range() 的边界理解有误——常见错误：用 range(n) 时误以为会到 n，或混淆 start/stop 的含义。",
            trigger_patterns=(
                "range(5) 应该是 0 1 2 3 4 5 吧？",
                "为什么 range(1, 5) 只到 4？",
                "for i in range(n): 为什么最后一个不是 n？",
                "range(0, 10, 2) 输出的最后一个是 8 不是 10？",
                "我想遍历 1 到 100，写 range(1, 100) 少了一个？",
            ),
            detection_keywords=("range", "off-by-one", "边界", "最后一个", "停"),
            skill_id="python.loops.for_range",
            correction_strategy="range_boundary_number_line",
            bloom_layer=BloomLevel.APPLY,
        ),
        MisconceptionEntry(
            misc_id="M7",
            name="while 基准情形遗漏",
            description="编写 while 循环时忘记设置或更新基准情形（loop condition），导致死循环。这是无限循环最常见的根源。",
            trigger_patterns=(
                "为什么我的程序卡住了？",
                "while True: 怎么停止？",
                "明明有条件，为什么还是死循环？",
                "少写了什么导致死循环？",
                "循环条件我都写了，为什么不退出？",
            ),
            detection_keywords=("死循环", "无限循环", "while", "条件", "停止", "卡住"),
            skill_id="python.loops.while_condition",
            correction_strategy="loop_variant_invariant_explanation",
            bloom_layer=BloomLevel.APPLY,
        ),
        # ─── 函数 ─────────────────────────────────────────────────
        MisconceptionEntry(
            misc_id="M4",
            name="函数必有返回值",
            description="认为每个函数都必须有 return 语句并返回一个值，无法理解 void 函数（无 return）的意义。常见于接触 Java/C 后再学 Python 的学习者。",
            trigger_patterns=(
                "这个函数没有 return，它在干什么？",
                "函数不返回值那叫什么函数？",
                "print() 算返回值吗？",
                "为什么有些函数写 return 有些不写？",
                "没有 return 的函数执行完什么都没留下吧？",
            ),
            detection_keywords=("return", "返回值", "void", "没有返回", "print"),
            skill_id="python.functions.return_value",
            correction_strategy="void_function_side_effect_explanation",
            bloom_layer=BloomLevel.UNDERSTAND,
        ),
        MisconceptionEntry(
            misc_id="M5",
            name="递归=循环",
            description="将递归与循环（迭代）混同，无法理解递归的核心——函数调用自身，而非「重复执行代码块」。常见错误：写递归时没有 base case，或把递归当作另一种 for 循环。",
            trigger_patterns=(
                "递归不就是循环吗？有什么区别？",
                "递归和 for 循环哪个更好？",
                "为什么要自己调用自己？",
                "递归函数里没有 return 为什么会出错？",
                "我想用递归但是不懂 base case 是什么",
            ),
            detection_keywords=("递归", "循环", "base case", "自己调用自己", "终止条件"),
            skill_id="python.functions.recursion",
            correction_strategy="recursion_vs_iteration_framing",
            bloom_layer=BloomLevel.ANALYZE,
        ),
    ]

    def __init__(self) -> None:
        self._by_id: dict[str, MisconceptionEntry] = {e.misc_id: e for e in self._entries}

    def get(self, misc_id: str) -> MisconceptionEntry | None:
        return self._by_id.get(misc_id)

    def all_entries(self) -> list[MisconceptionEntry]:
        return list(self._entries)
