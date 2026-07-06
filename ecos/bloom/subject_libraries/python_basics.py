"""Bloom Goal Library — Python 基础学习目标.

M2 战略调整（v1.1）：聚焦 Python 基础认知助手（自学者产品方向）。
LLM 充当领域专家。

达标线（4 闸）：
  ① TC_python 跨越
  ② Bloom: Understand ≥ 0.85 AND Apply ≥ 0.75
  ③ Misconception 清零（M1-M8 全部消除）
  ④ C 是"挣来的"（伪置信 = false）

5 个 topic × 4 层（L1-L4）= 20 条 Bloom Goal。
L5 Evaluate / L6 Create 在 MVP 阶段不评估。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from ...cta.belief_state import BloomLevel


class PythonBasicsTopic(Enum):
    VARIABLES = "python.variables"
    LOOPS = "python.loops"
    FUNCTIONS = "python.functions"
    RECURSION = "python.recursion"
    SCOPE = "python.scope"


@dataclass(frozen=True)
class BloomGoalEntry:
    """单条 Bloom Goal（知识点 × Bloom 层）。

    Attributes:
        goal_id: 唯一标识，如 "python.variables-L2"
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


class PythonBasicsBloomLibrary:
    """Python 基础 Bloom Goal 库（5 topic × 4 layer = 20 条）。

    用法：
        library = PythonBasicsBloomLibrary()
        goals = library.get_goals_by_topic("python.variables")
        goals_l2 = library.get_goals_by_level(BloomLevel.UNDERSTAND)
    """

    _entries: ClassVar[list[BloomGoalEntry]] = [
        # ═══════════════════════════════════════════════════════════
        # Topic: 变量与赋值
        # ═══════════════════════════════════════════════════════════
        BloomGoalEntry(
            goal_id="python.variables-L1",
            topic=PythonBasicsTopic.VARIABLES.value,
            bloom_level=BloomLevel.REMEMBER,
            description="记忆变量的基本概念：变量是存储值的名字，赋值用 = ",
            success_criteria="能写出变量赋值的正确语法，能区分左边的变量名和右边的表达式",
            prerequisite_goals=(),
            typical_duration_days=1,
        ),
        BloomGoalEntry(
            goal_id="python.variables-L2",
            topic=PythonBasicsTopic.VARIABLES.value,
            bloom_level=BloomLevel.UNDERSTAND,
            description="理解变量是标签而非盒子——赋值是让名字指向对象，而非把对象装进盒子",
            success_criteria="能用自己的话解释为什么 x = x + 1 不是矛盾，能说明'='是赋值不是相等",
            prerequisite_goals=("python.variables-L1",),
            typical_duration_days=2,
        ),
        BloomGoalEntry(
            goal_id="python.variables-L3",
            topic=PythonBasicsTopic.VARIABLES.value,
            bloom_level=BloomLevel.APPLY,
            description="能在实际问题中正确使用变量赋值，包括自增、自减、多重赋值",
            success_criteria="给定一个计数场景，能正确写出 x = x + 1；给定 a, b = b, a 能说出交换原理",
            prerequisite_goals=("python.variables-L2",),
            typical_duration_days=3,
        ),
        BloomGoalEntry(
            goal_id="python.variables-L4",
            topic=PythonBasicsTopic.VARIABLES.value,
            bloom_level=BloomLevel.ANALYZE,
            description="分析引用语义与赋值拷贝的区别，能解释为何修改列表会影响其他引用",
            success_criteria="给定代码 a = [1,2]; b = a; b.append(3)，能说明 a 和 b 的关系以及为什么",
            prerequisite_goals=("python.variables-L3",),
            typical_duration_days=5,
        ),
        # ═══════════════════════════════════════════════════════════
        # Topic: 循环
        # ═══════════════════════════════════════════════════════════
        BloomGoalEntry(
            goal_id="python.loops-L1",
            topic=PythonBasicsTopic.LOOPS.value,
            bloom_level=BloomLevel.REMEMBER,
            description="记忆 for 和 while 循环的基本语法，包括 range() 函数的用法",
            success_criteria="能写出 for i in range(n): 和 while 条件: 的基本结构，能说出 range(5) 产生哪些数",
            prerequisite_goals=(),
            typical_duration_days=1,
        ),
        BloomGoalEntry(
            goal_id="python.loops-L2",
            topic=PythonBasicsTopic.LOOPS.value,
            bloom_level=BloomLevel.UNDERSTAND,
            description="理解 for 循环的 range(start, stop, step) 三段式，理解 stop 是开区间（不包含）",
            success_criteria="能解释 range(1, 5) 和 range(5) 的区别，能正确计算 range(0, 10, 2) 的输出序列",
            prerequisite_goals=("python.loops-L1",),
            typical_duration_days=2,
        ),
        BloomGoalEntry(
            goal_id="python.loops-L3",
            topic=PythonBasicsTopic.LOOPS.value,
            bloom_level=BloomLevel.APPLY,
            description="能用循环解决实际问题，包括遍历列表、累加、查找，能正确设置循环终止条件",
            success_criteria="能写出从 1 加到 100 的正确代码；给定列表 [3, 7, 2, 9]，能找到最大值",
            prerequisite_goals=("python.loops-L2",),
            typical_duration_days=3,
        ),
        BloomGoalEntry(
            goal_id="python.loops-L4",
            topic=PythonBasicsTopic.LOOPS.value,
            bloom_level=BloomLevel.ANALYZE,
            description="分析死循环的成因，理解循环基准情形（variant/invariant），能诊断并修复常见循环错误",
            success_criteria="给定一个有死循环嫌疑的代码，能指出缺少的基准情形更新；能解释 while True: 如何正确退出",
            prerequisite_goals=("python.loops-L3",),
            typical_duration_days=5,
        ),
        # ═══════════════════════════════════════════════════════════
        # Topic: 函数
        # ═══════════════════════════════════════════════════════════
        BloomGoalEntry(
            goal_id="python.functions-L1",
            topic=PythonBasicsTopic.FUNCTIONS.value,
            bloom_level=BloomLevel.REMEMBER,
            description="记忆函数定义的基本语法：def 函数名(参数): 以及 return 语句的作用",
            success_criteria="能写出带参数和返回值的函数基本结构，能说出 return 和 print() 的区别",
            prerequisite_goals=(),
            typical_duration_days=1,
        ),
        BloomGoalEntry(
            goal_id="python.functions-L2",
            topic=PythonBasicsTopic.FUNCTIONS.value,
            bloom_level=BloomLevel.UNDERSTAND,
            description="理解函数可以有 return 也可以没有（void）——没有 return 的函数执行副作用而非返回值",
            success_criteria="能解释为什么 print() 返回 None；能给出一个 void 函数的合理使用场景",
            prerequisite_goals=("python.functions-L1",),
            typical_duration_days=2,
        ),
        BloomGoalEntry(
            goal_id="python.functions-L3",
            topic=PythonBasicsTopic.FUNCTIONS.value,
            bloom_level=BloomLevel.APPLY,
            description="能在实际问题中设计并调用函数，包括参数传递、返回值处理、多函数协作",
            success_criteria="能设计一个判断质数的函数并在主程序中调用；能写出接受多个参数并返回多个值的函数",
            prerequisite_goals=("python.functions-L2",),
            typical_duration_days=3,
        ),
        BloomGoalEntry(
            goal_id="python.functions-L4",
            topic=PythonBasicsTopic.FUNCTIONS.value,
            bloom_level=BloomLevel.ANALYZE,
            description="分析参数传递机制（值传递 vs 引用传递），理解函数调用栈和作用域规则的交互",
            success_criteria="给定函数参数是列表时，能说明在函数内修改列表会影响外部变量的原因",
            prerequisite_goals=("python.functions-L3",),
            typical_duration_days=5,
        ),
        # ═══════════════════════════════════════════════════════════
        # Topic: 递归
        # ═══════════════════════════════════════════════════════════
        BloomGoalEntry(
            goal_id="python.recursion-L1",
            topic=PythonBasicsTopic.RECURSION.value,
            bloom_level=BloomLevel.REMEMBER,
            description="记忆递归的定义：函数调用自身，理解递归需要 base case（基准情形）",
            success_criteria="能说出递归的两个必要条件：调用自身 + 基准情形，能给出递归的日常例子（如镜子中的镜子）",
            prerequisite_goals=("python.functions-L1",),
            typical_duration_days=1,
        ),
        BloomGoalEntry(
            goal_id="python.recursion-L2",
            topic=PythonBasicsTopic.RECURSION.value,
            bloom_level=BloomLevel.UNDERSTAND,
            description="理解递归与循环的本质区别：递归是通过函数调用分解问题，循环是通过重复执行代码块",
            success_criteria="能解释递归的核心思想是'化归'——把复杂问题化为同类子问题，能对比递归和 for 循环的适用场景",
            prerequisite_goals=("python.recursion-L1",),
            typical_duration_days=2,
        ),
        BloomGoalEntry(
            goal_id="python.recursion-L3",
            topic=PythonBasicsTopic.RECURSION.value,
            bloom_level=BloomLevel.APPLY,
            description="能用递归解决经典问题：阶乘、斐波那契数列、字符串反转、汉诺塔等",
            success_criteria="能正确实现阶乘和斐波那契数列的递归版本，能解释为什么斐波那契递归效率低并说出优化方向",
            prerequisite_goals=("python.recursion-L2",),
            typical_duration_days=3,
        ),
        BloomGoalEntry(
            goal_id="python.recursion-L4",
            topic=PythonBasicsTopic.RECURSION.value,
            bloom_level=BloomLevel.ANALYZE,
            description="分析递归调用栈，理解栈溢出（maximum recursion depth exceeded）的成因，能判断何时递归优于迭代",
            success_criteria="能解释 Python 默认递归深度限制（约 1000）是哪里来的，能分析树结构遍历何时递归是自然选择",
            prerequisite_goals=("python.recursion-L3",),
            typical_duration_days=5,
        ),
        # ═══════════════════════════════════════════════════════════
        # Topic: 作用域
        # ═══════════════════════════════════════════════════════════
        BloomGoalEntry(
            goal_id="python.scope-L1",
            topic=PythonBasicsTopic.SCOPE.value,
            bloom_level=BloomLevel.REMEMBER,
            description="记忆 Python 作用域的基本层级：局部（local）→ 封闭（enclosing）→ 全局（global）→ 内建（builtin）",
            success_criteria="能说出 LEGB 的四个层级，能识别简单代码中的局部变量和全局变量",
            prerequisite_goals=("python.variables-L1",),
            typical_duration_days=1,
        ),
        BloomGoalEntry(
            goal_id="python.scope-L2",
            topic=PythonBasicsTopic.SCOPE.value,
            bloom_level=BloomLevel.UNDERSTAND,
            description="理解函数内部的变量遮蔽（shadowing）：局部变量与全局变量同名时，局部变量优先",
            success_criteria="能解释为什么在函数内给 x 赋值不会修改全局 x，除非使用 global 声明；能说明 global 关键字的作用",
            prerequisite_goals=("python.scope-L1",),
            typical_duration_days=2,
        ),
        BloomGoalEntry(
            goal_id="python.scope-L3",
            topic=PythonBasicsTopic.SCOPE.value,
            bloom_level=BloomLevel.APPLY,
            description="能在函数内外正确传递和修改变量，理解 nonlocal 的用途，能设计避免全局变量污染的代码结构",
            success_criteria="能写出需要读取和修改全局变量时的正确代码（用 global）；能给出一个使用 nonlocal 的合理场景",
            prerequisite_goals=("python.scope-L2",),
            typical_duration_days=3,
        ),
        BloomGoalEntry(
            goal_id="python.scope-L4",
            topic=PythonBasicsTopic.SCOPE.value,
            bloom_level=BloomLevel.ANALYZE,
            description="分析嵌套作用域的闭包机制，理解 Python 中 nonlocal 的工作原理，能识别常见的闭包陷阱（如循环中的函数引用）",
            success_criteria="能解释为什么循环中创建函数时所有函数返回相同值（闭包陷阱），能给出正确的解决方法（默认参数/工厂函数）",
            prerequisite_goals=("python.scope-L3",),
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
