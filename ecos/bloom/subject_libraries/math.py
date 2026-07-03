"""Bloom Goal Library — 初中数学（Math 8 知识点 × 4 层）。

对应 research/10-engineering/03-bloom-goal-library.md §3
+ research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md §1.7。

MVP 范围（4-6 周实验周期内可覆盖）：
  - 8 个核心知识点（代数 / 几何 / 函数 / 概率各 2 个）
  - 每知识点 4 层（L1 Remember → L4 Analyze；L5 Evaluate / L6 Create MVP 不评估）

Bloom Goal = (知识点 ID, Bloom Level) 唯一标识。
LCA 据此选择下一个学习目标（默认：当前 dominant_layer + 1）。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from ...cta.belief_state import BloomLevel


class MathTopic(Enum):
    """初中数学 MVP 覆盖的 8 个核心知识点."""
    ALGEBRA_LINEAR = "math.algebra.linear"           # 一次方程与方程组
    ALGEBRA_QUADRATIC = "math.algebra.quadratic"     # 一元二次方程
    FRACTION = "math.fraction"                        # 分数运算
    FUNCTION_BASICS = "math.function.basics"         # 函数基础（正比例/反比例）
    GEOMETRY_TRIANGLE = "math.geometry.triangle"      # 三角形与全等
    GEOMETRY_CIRCLE = "math.geometry.circle"          # 圆的基本性质
    STATISTICS = "math.statistics"                    # 统计与概率基础
    INEQUALITY = "math.inequality"                    # 不等式与不等式组


@dataclass(frozen=True)
class BloomGoalEntry:
    """单条 Bloom Goal（知识点 × Bloom 层）。

    Attributes:
        goal_id: 唯一标识，如 "math.algebra.linear-L2"
        topic: 知识点 ID
        bloom_level: Bloom 认知层级
        description: 目标的自然语言描述（LCA 展示用）
        success_criteria: 可观测的成功标准（用于判定目标达成）
        prerequisite_goals: 前置目标 ID（MVP 简化：可为空）
        typical_duration_days: 典型达成周期（MVP 估计值，供 Bjork CLT 用）
    """
    goal_id: str
    topic: str
    bloom_level: BloomLevel
    description: str
    success_criteria: str
    prerequisite_goals: tuple[str, ...]
    typical_duration_days: int


class MathBloomLibrary:
    """初中数学 Bloom Goal 库（MVP，8 × 4 = 32 条）。

    用法：
        library = MathBloomLibrary()
        goals = library.get_goals_by_topic("math.algebra.linear")
        goals_L2_plus = [g for g in goals if g.bloom_level.value >= BloomLevel.UNDERSTAND.value]
    """

    # ============================================================
    # 产出表：8 topics × 4 layers = 32 条
    # ============================================================
    _entries: ClassVar[list[BloomGoalEntry]] = [
        # ── Topic 1: 一次方程与方程组 ────────────────────────────
        BloomGoalEntry(
            goal_id="math.algebra.linear-L1",
            topic=MathTopic.ALGEBRA_LINEAR.value,
            bloom_level=BloomLevel.REMEMBER,
            description="记忆一元一次方程的标准形式 ax=b（a≠0）及解的表达式",
            success_criteria="给定 ax=b，能写出 x=b/a 的通解表达式",
            prerequisite_goals=(),
            typical_duration_days=1,
        ),
        BloomGoalEntry(
            goal_id="math.algebra.linear-L2",
            topic=MathTopic.ALGEBRA_LINEAR.value,
            bloom_level=BloomLevel.UNDERSTAND,
            description="理解等式性质的推导过程，能解释为何移项要变号",
            success_criteria="能用『两边同时加/减/乘/除（不为零）相同数，等式仍成立』解释移项步骤",
            prerequisite_goals=("math.algebra.linear-L1",),
            typical_duration_days=2,
        ),
        BloomGoalEntry(
            goal_id="math.algebra.linear-L3",
            topic=MathTopic.ALGEBRA_LINEAR.value,
            bloom_level=BloomLevel.APPLY,
            description="熟练求解一元一次方程及简单二元一次方程组（代入法/加减法）",
            success_criteria="在 3 分钟内正确求解 3 道一元一次方程和 1 道方程组",
            prerequisite_goals=("math.algebra.linear-L2",),
            typical_duration_days=3,
        ),
        BloomGoalEntry(
            goal_id="math.algebra.linear-L4",
            topic=MathTopic.ALGEBRA_LINEAR.value,
            bloom_level=BloomLevel.ANALYZE,
            description="分析方程组解的存在性条件（唯一解/无解/无穷多解），并联系实际应用题列方程",
            success_criteria="能判断方程组类型并给出几何解释（平行/重合/相交）；能根据题意列方程",
            prerequisite_goals=("math.algebra.linear-L3",),
            typical_duration_days=5,
        ),
        # ── Topic 2: 一元二次方程 ──────────────────────────────
        BloomGoalEntry(
            goal_id="math.algebra.quadratic-L1",
            topic=MathTopic.ALGEBRA_QUADRATIC.value,
            bloom_level=BloomLevel.REMEMBER,
            description="记忆一元二次方程 ax²+bx+c=0（a≠0）的标准形式及判别式 Δ=b²-4ac",
            success_criteria="给定方程，能正确识别 a、b、c 并写出判别式",
            prerequisite_goals=("math.algebra.linear-L3",),
            typical_duration_days=1,
        ),
        BloomGoalEntry(
            goal_id="math.algebra.quadratic-L2",
            topic=MathTopic.ALGEBRA_QUADRATIC.value,
            bloom_level=BloomLevel.UNDERSTAND,
            description="理解求根公式的推导逻辑，知道 Δ>0/=0/<0 对应哪种解的情况",
            success_criteria="能用『完全平方』推导过程说明求根公式的来源；能解释 Δ 的三种情形",
            prerequisite_goals=("math.algebra.quadratic-L1",),
            typical_duration_days=2,
        ),
        BloomGoalEntry(
            goal_id="math.algebra.quadratic-L3",
            topic=MathTopic.ALGEBRA_QUADRATIC.value,
            bloom_level=BloomLevel.APPLY,
            description="熟练使用求根公式、因式分解法解一元二次方程",
            success_criteria="给定方程，能在 4 分钟内选择正确方法求出全部解",
            prerequisite_goals=("math.algebra.quadratic-L2",),
            typical_duration_days=4,
        ),
        BloomGoalEntry(
            goal_id="math.algebra.quadratic-L4",
            topic=MathTopic.ALGEBRA_QUADRATIC.value,
            bloom_level=BloomLevel.ANALYZE,
            description="分析韦达定理（根与系数关系）的推导，能用它构造方程或判断根的符号",
            success_criteria="能用韦达定理由根构造方程；能判断 Δ>0 时两根同号/异号的条件",
            prerequisite_goals=("math.algebra.quadratic-L3",),
            typical_duration_days=5,
        ),
        # ── Topic 3: 分数运算 ─────────────────────────────────
        BloomGoalEntry(
            goal_id="math.fraction-L1",
            topic=MathTopic.FRACTION.value,
            bloom_level=BloomLevel.REMEMBER,
            description="记忆分数的基本性质：分子分母同乘（除）不为零的数，分数值不变",
            success_criteria="能写出 3/5 的两个等值分数；能说明分数基本性质的表述",
            prerequisite_goals=(),
            typical_duration_days=1,
        ),
        BloomGoalEntry(
            goal_id="math.fraction-L2",
            topic=MathTopic.FRACTION.value,
            bloom_level=BloomLevel.UNDERSTAND,
            description="理解通分的目的是找公分母，能用自己的话解释『等值分数』与『通分』的关系",
            success_criteria="给定两道异分母分数，能正确找到最小公倍数并通分",
            prerequisite_goals=("math.fraction-L1",),
            typical_duration_days=2,
        ),
        BloomGoalEntry(
            goal_id="math.fraction-L3",
            topic=MathTopic.FRACTION.value,
            bloom_level=BloomLevel.APPLY,
            description="熟练进行分数的加减乘除运算（含带分数、混合运算）",
            success_criteria="能在 5 分钟内完成 5 道分数混合运算（含乘除法），正确率≥80%",
            prerequisite_goals=("math.fraction-L2",),
            typical_duration_days=3,
        ),
        BloomGoalEntry(
            goal_id="math.fraction-L4",
            topic=MathTopic.FRACTION.value,
            bloom_level=BloomLevel.ANALYZE,
            description="分析分数运算中的典型错误（通分错误、约分遗漏、符号错误），能识别并解释",
            success_criteria="给定 5 道错误解法，能逐一指出错误原因并给出正确步骤",
            prerequisite_goals=("math.fraction-L3",),
            typical_duration_days=4,
        ),
        # ── Topic 4: 函数基础（正比例/反比例）───────────────────
        BloomGoalEntry(
            goal_id="math.function.basics-L1",
            topic=MathTopic.FUNCTION_BASICS.value,
            bloom_level=BloomLevel.REMEMBER,
            description="记忆正比例函数 y=kx（k≠0）和反比例函数 y=k/x（k≠0）的标准形式",
            success_criteria="给定 y=3x，能判断是正比例函数并说出 k 值；给定 y=2/x，能说出 k 值",
            prerequisite_goals=("math.algebra.linear-L2",),
            typical_duration_days=1,
        ),
        BloomGoalEntry(
            goal_id="math.function.basics-L2",
            topic=MathTopic.FUNCTION_BASICS.value,
            bloom_level=BloomLevel.UNDERSTAND,
            description="理解 k 的几何意义（斜率），能用『每增加 1 个单位，y 增加 k 个单位』描述变化",
            success_criteria="给定 k=2，能描述 y 随 x 的变化关系；能说出 k>0 和 k<0 时图像的特征",
            prerequisite_goals=("math.function.basics-L1",),
            typical_duration_days=2,
        ),
        BloomGoalEntry(
            goal_id="math.function.basics-L3",
            topic=MathTopic.FUNCTION_BASICS.value,
            bloom_level=BloomLevel.APPLY,
            description="能在坐标系中正确描点画图，根据图像求特定 x（或 y）对应的 y（或 x）",
            success_criteria="给定 y=3x 和 y=-2/x，能在坐标系中正确画出两图像并标注交点",
            prerequisite_goals=("math.function.basics-L2",),
            typical_duration_days=3,
        ),
        BloomGoalEntry(
            goal_id="math.function.basics-L4",
            topic=MathTopic.FUNCTION_BASICS.value,
            bloom_level=BloomLevel.ANALYZE,
            description="分析正比例与反比例函数的对称性差异，能从解析式和图像两个角度解释差异",
            success_criteria="能从 k 的正负、图像所在象限、解析式形式三个维度说明两者的本质区别",
            prerequisite_goals=("math.function.basics-L3",),
            typical_duration_days=5,
        ),
        # ── Topic 5: 三角形与全等 ───────────────────────────────
        BloomGoalEntry(
            goal_id="math.geometry.triangle-L1",
            topic=MathTopic.GEOMETRY_TRIANGLE.value,
            bloom_level=BloomLevel.REMEMBER,
            description="记忆三角形内角和=180°，能说出 SSS/SAS/ASA/AAS/HL 五种全等判定方法",
            success_criteria="给定两个三角形，能识别哪条对应边或角相等（口述）",
            prerequisite_goals=(),
            typical_duration_days=1,
        ),
        BloomGoalEntry(
            goal_id="math.geometry.triangle-L2",
            topic=MathTopic.GEOMETRY_TRIANGLE.value,
            bloom_level=BloomLevel.UNDERSTAND,
            description="理解『内角和=180°』的证明思路（平行线内错角），理解全等不是相似（大小相等）",
            success_criteria="能独立写出内角和=180°的平行线证明过程；能说明全等与相似的区别",
            prerequisite_goals=("math.geometry.triangle-L1",),
            typical_duration_days=2,
        ),
        BloomGoalEntry(
            goal_id="math.geometry.triangle-L3",
            topic=MathTopic.GEOMETRY_TRIANGLE.value,
            bloom_level=BloomLevel.APPLY,
            description="能运用全等三角形判定定理证明两条线段相等或两个角相等",
            success_criteria="给定几何证明题，能在 8 分钟内完成证明（含已知、求证、证明过程）",
            prerequisite_goals=("math.geometry.triangle-L2",),
            typical_duration_days=5,
        ),
        BloomGoalEntry(
            goal_id="math.geometry.triangle-L4",
            topic=MathTopic.GEOMETRY_TRIANGLE.value,
            bloom_level=BloomLevel.ANALYZE,
            description="分析『SSA 能否判定全等』的反例，理解为何 HL 成立而 SSA 不成立（两边及其中一边对角）",
            success_criteria="能用几何画图解释 SSA 反例（已知两边及其中一边对角不全等于另一三角形）",
            prerequisite_goals=("math.geometry.triangle-L3",),
            typical_duration_days=4,
        ),
        # ── Topic 6: 圆的基本性质 ───────────────────────────────
        BloomGoalEntry(
            goal_id="math.geometry.circle-L1",
            topic=MathTopic.GEOMETRY_CIRCLE.value,
            bloom_level=BloomLevel.REMEMBER,
            description="记忆圆周率定义（周长/直径）、圆面积公式 S=πr²、弧长公式",
            success_criteria="给定半径 r=3，能求出周长 C=2πr=6π，面积 S=πr²=9π",
            prerequisite_goals=("math.number.pi_definition",),
            typical_duration_days=1,
        ),
        BloomGoalEntry(
            goal_id="math.geometry.circle-L2",
            topic=MathTopic.GEOMETRY_CIRCLE.value,
            bloom_level=BloomLevel.UNDERSTAND,
            description="理解圆周率是无理数（不可精确表示为分数），理解弧长是圆周的一部分",
            success_criteria="能解释为何 π 是无理数（给一个不循环小数）；能用弧长=圆心角度数/360×2πr",
            prerequisite_goals=("math.geometry.circle-L1",),
            typical_duration_days=2,
        ),
        BloomGoalEntry(
            goal_id="math.geometry.circle-L3",
            topic=MathTopic.GEOMETRY_CIRCLE.value,
            bloom_level=BloomLevel.APPLY,
            description="综合运用圆的性质（圆周角定理、垂径定理）求解角度和长度问题",
            success_criteria="给定圆与弦、圆周角组合的几何题，能正确运用定理求出指定角度",
            prerequisite_goals=("math.geometry.circle-L2",),
            typical_duration_days=4,
        ),
        BloomGoalEntry(
            goal_id="math.geometry.circle-L4",
            topic=MathTopic.GEOMETRY_CIRCLE.value,
            bloom_level=BloomLevel.ANALYZE,
            description="分析『圆周角定理的逆定理』成立的条件，能识别并构造反例（圆内接四边形的对角互补）",
            success_criteria="能说明圆周角定理及其推论的条件差异；能用反例说明『顶点在圆内的角』不满足圆周角定理",
            prerequisite_goals=("math.geometry.circle-L3",),
            typical_duration_days=5,
        ),
        # ── Topic 7: 统计与概率基础 ─────────────────────────────
        BloomGoalEntry(
            goal_id="math.statistics-L1",
            topic=MathTopic.STATISTICS.value,
            bloom_level=BloomLevel.REMEMBER,
            description="记忆平均数、中位数、众数的定义及计算公式",
            success_criteria="给定数据集 {2,3,3,5,7}，能口算说出平均数=4，中位数=3，众数=3",
            prerequisite_goals=(),
            typical_duration_days=1,
        ),
        BloomGoalEntry(
            goal_id="math.statistics-L2",
            topic=MathTopic.STATISTICS.value,
            bloom_level=BloomLevel.UNDERSTAND,
            description="理解三种集中趋势指标在不同数据分布中的适用性，能判断哪种指标更能描述数据中心",
            success_criteria="能解释为何某数据集用中位数比平均数更合适（如有异常值）",
            prerequisite_goals=("math.statistics-L1",),
            typical_duration_days=2,
        ),
        BloomGoalEntry(
            goal_id="math.statistics-L3",
            topic=MathTopic.STATISTICS.value,
            bloom_level=BloomLevel.APPLY,
            description="能计算简单事件的概率（古典概型），用频率估计概率（大数定律的直观理解）",
            success_criteria="给定摸球实验（不放回），能正确计算某事件概率；能解释为何大量重复后频率趋近概率",
            prerequisite_goals=("math.statistics-L2",),
            typical_duration_days=3,
        ),
        BloomGoalEntry(
            goal_id="math.statistics-L4",
            topic=MathTopic.STATISTICS.value,
            bloom_level=BloomLevel.ANALYZE,
            description="分析『独立事件 vs 非独立事件』的区别，能识别生活中的相关不等于因果",
            success_criteria="能举出两个统计相关但无因果关系的例子（如冰淇淋销量与溺水人数）；能说明独立事件的乘法法则",
            prerequisite_goals=("math.statistics-L3",),
            typical_duration_days=5,
        ),
        # ── Topic 8: 不等式与不等式组 ───────────────────────────
        BloomGoalEntry(
            goal_id="math.inequality-L1",
            topic=MathTopic.INEQUALITY.value,
            bloom_level=BloomLevel.REMEMBER,
            description="记忆不等式的基本性质（对称性、传递性、可加性、可乘性）",
            success_criteria="能默写 4 条基本性质的条文（对称/传递/同加/同乘正/同乘负变号）",
            prerequisite_goals=("math.algebra.linear-L1",),
            typical_duration_days=1,
        ),
        BloomGoalEntry(
            goal_id="math.inequality-L2",
            topic=MathTopic.INEQUALITY.value,
            bloom_level=BloomLevel.UNDERSTAND,
            description="理解为何『同乘负数要变号』，能用数轴解释不等式解集的几何含义",
            success_criteria="能在数轴上正确标出 x>-2 和 x≤1 的解集；能说明两解集的交集如何求",
            prerequisite_goals=("math.inequality-L1",),
            typical_duration_days=2,
        ),
        BloomGoalEntry(
            goal_id="math.inequality-L3",
            topic=MathTopic.INEQUALITY.value,
            bloom_level=BloomLevel.APPLY,
            description="求解一元一次不等式及简单不等式组，用数轴表示解集",
            success_criteria="给定 3 道一元一次不等式和 1 道不等式组，能正确求解并在数轴上表示",
            prerequisite_goals=("math.inequality-L2",),
            typical_duration_days=3,
        ),
        BloomGoalEntry(
            goal_id="math.inequality-L4",
            topic=MathTopic.INEQUALITY.value,
            bloom_level=BloomLevel.ANALYZE,
            description="分析『不等式两边同乘负数变号』的深层原理，对比等式与不等式变换规则的差异",
            success_criteria="能写出等式性质与不等式性质的一一对应表，并指出变号规则的来源",
            prerequisite_goals=("math.inequality-L3",),
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

    def next_up(self, current_level: BloomLevel) -> list[BloomGoalEntry]:
        """返回当前层级+1的目标（MVP 默认策略）。"""
        next_val = current_level.value + 1
        if next_val > BloomLevel.ANALYZE.value:
            return []
        next_level = BloomLevel(next_val)
        return self.get_goals_by_level(next_level)

    def all_entries(self) -> list[BloomGoalEntry]:
        return list(self._entries)

    def all_topic_ids(self) -> list[str]:
        return [t.value for t in MathTopic]
