"""CTA Threshold Concept Library（初中数学 TC 库）。

对应 research/30-shared-cognitive-tools/theoretical-foundations/
03-c-dimension-content-libraries.md §1.7（初中数学 TC 库 MVP 候选 8 条）。

TC（Threshold Concept）特性：
  - 不可逆（一旦跨越难以退回）
  - 变革性（理解后学习者世界观发生质变）
  - 整合性（连接多个先前分离的概念）
  - 渐进性（有 liminal 中间态）

M2 W3：TCStateDetector 用此库检测学生是否跨越 TC。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from ..belief_state import BloomLevel


class TCStatus(Enum):
    """TC 跨越状态."""
    PRE_LIMITINAL = "pre_liminal"   # 未接触
    LIMINAL = "liminal"             # 中间态（似懂非懂）
    POST_LIMITINAL = "post_liminal"  # 已跨越


@dataclass(frozen=True)
class ThresholdConceptEntry:
    """单条 Threshold Concept 条目.

    Attributes:
        tc_id: 唯一标识，如 "TC_function"
        name: 中文名称
        description: 1-2 句描述该 TC 的核心内涵
        pre_conception: 跨越前的典型前概念（str）
        liminal_signals: 处于 liminal 态时的典型话语（tuple，2-3 条）
        post_conception: 跨越后的典型理解（str）
        crossing_indicators: 客观可观测的跨越信号（tuple，2-3 条）
        skill_ids: 关联的知识点 ID 列表
        bloom_layer: 跨越所需的 Bloom 层级
        irreversible: 是否不可逆（MVP 统一 True）
    """

    tc_id: str
    name: str
    description: str
    pre_conception: str
    liminal_signals: tuple[str, ...]
    post_conception: str
    crossing_indicators: tuple[str, ...]
    skill_ids: tuple[str, ...]
    bloom_layer: BloomLevel
    irreversible: bool = True


class ThresholdConceptLibrary:
    """初中数学 Threshold Concept 库（MVP，8 条）。

    用法：
        library = ThresholdConceptLibrary()
        tc = library.get("TC_function")
        liminal_entries = library.filter_liminal_signals("我觉得 y 随 x 变化有点道理")
    """

    _entries: ClassVar[list[ThresholdConceptEntry]] = [
        ThresholdConceptEntry(
            tc_id="TC_function",
            name="函数",
            description="从『y 随 x 变化』的变量依赖直觉，过渡到『集合到集合的映射』的严格定义。",
            pre_conception="y 随 x 变化，x 变 y 就变",
            liminal_signals=(
                "我知道 y 是 x 的函数，但说不清楚什么叫『每一个 x 都有唯一的 y』",
                "y=x² 是函数，但 f(2)=4 是什么意思？",
                "函数一定可以用公式表示吗？",
            ),
            post_conception="函数是两个数集之间的对应关系，每个输入对应唯一输出",
            crossing_indicators=(
                "能判断一个对应关系是否为函数（垂直线测试）",
                "能用集合语言描述函数",
                "能区分函数与关系",
            ),
            skill_ids=(
                "math.function.basics",
                "math.function.linear",
                "math.function.quadratic",
            ),
            bloom_layer=BloomLevel.ANALYZE,
        ),
        ThresholdConceptEntry(
            tc_id="TC_variable",
            name="变量",
            description="从『未知数』的算术直觉，过渡到『代表一类数的符号』的代数思维。",
            pre_conception="x 就是那个要求出来的数",
            liminal_signals=(
                "x 可以是任何数，但为什么还要用字母？",
                "我说不清『变量』和『未知数』的区别",
                "方程里的 x 和函数里的 x 是一个东西吗？",
            ),
            post_conception="变量是代表一类数的符号，未知数是变量的一种特殊情形",
            crossing_indicators=(
                "能区分『特定未知数』与『一般变量』",
                "能说出『当 x=3 时 y=5』中 x 和 y 的含义",
                "能理解参数与变量的区别",
            ),
            skill_ids=(
                "math.algebra.variable",
                "math.linear_equation.solve",
            ),
            bloom_layer=BloomLevel.UNDERSTAND,
        ),
        ThresholdConceptEntry(
            tc_id="TC_equation_vs_inequality",
            name="等式 vs 不等式",
            description="从『两边相等』的直觉，过渡到『约束关系』的认知——不等式变换时符号方向会翻转。",
            pre_conception="等式和不等式差不多，就是一个用 = 一个用 > 或 <",
            liminal_signals=(
                "不等式两边同乘负数为什么要变号？",
                "x>3 和 x≥3 有什么区别？不就是多一个点吗？",
                "我知道变号，但有时候还是会忘",
            ),
            post_conception="不等式描述的是数轴上的区间约束，变换时必须同步维护约束的方向性",
            crossing_indicators=(
                "能正确说出『同乘负数要变号』的原理",
                "能独立求解 -2x > 6 并检验",
                "能用数轴表示不等式的解集",
            ),
            skill_ids=(
                "math.inequality.transform",
                "math.linear_equation.solve",
            ),
            bloom_layer=BloomLevel.ANALYZE,
        ),
        ThresholdConceptEntry(
            tc_id="TC_geometric_proof",
            name="几何证明",
            description="从『计算得出答案』的操作直觉，过渡到『逻辑链条论证』的证明思维——证明不等于算对。",
            pre_conception="证明题就是利用已知条件算出来，步骤和计算题差不多",
            liminal_signals=(
                "我能看懂证明过程，但自己写的时候不知道从哪开始",
                "证明题要写那么多步，太麻烦了",
                "我说不清『因为』和『所以』的逻辑关系",
            ),
            post_conception="几何证明是从已知事实出发，通过逻辑推导建立结论，每一个结论必须有依据",
            crossing_indicators=(
                "能区分『计算题』和『证明题』的思维方式差异",
                "能独立写出三步以上的证明链条",
                "能用『因为...所以...』组织证明语言",
            ),
            skill_ids=(
                "math.geometry.proof",
                "math.geometry.parallel_lines",
                "math.geometry.triangle_angle_sum",
            ),
            bloom_layer=BloomLevel.ANALYZE,
        ),
        ThresholdConceptEntry(
            tc_id="TC_negative_number",
            name="负数",
            description="从『减法结果』的算术直觉，过渡到『数轴对称』的抽象认知——负数是实际存在的。",
            pre_conception="负数就是减出来的结果，-3 就是比 0 还小",
            liminal_signals=(
                "我知道 -3 在 0 的左边，但还是觉得别扭",
                "负数乘负数为什么变正？",
                "生活中真的有负数吗？",
            ),
            post_conception="负数与正数在数轴上对称，负号表示方向，数轴上每一点都有实际位置",
            crossing_indicators=(
                "能用数轴解释 (-3)×(-2)=6",
                "能理解负数在温度、海拔、资产负债等实际情境中的含义",
                "能在数轴上正确表示负数的大小关系",
            ),
            skill_ids=(
                "math.number.negative",
                "math.number.absolute_value",
            ),
            bloom_layer=BloomLevel.UNDERSTAND,
        ),
        ThresholdConceptEntry(
            tc_id="TC_fraction",
            name="分数",
            description="从『部分与整体』的直觉，过渡到『整体关系』的抽象认知——分数是有序数对 a/b 而非简单的『大卸八块』。",
            pre_conception="分数就是『把一个东西分成几份，取其中一份』",
            liminal_signals=(
                "1/2 + 1/3 为什么不是 2/5？分子分母分别加起来不行吗？",
                "分数大小比较，当分母不同时到底看谁？",
                "我可以用面积模型画出 1/2，但说不出为什么 1/2=3/6",
            ),
            post_conception="分数 a/b 是有理数，数轴上每一个点对应唯一分数，分子分母在不同操作中有不同角色",
            crossing_indicators=(
                "能用数轴说明 1/2=3/6 的合理性",
                "能正确进行异分母分数加减（通分）",
                "能用等值分数解释分数的性质",
            ),
            skill_ids=(
                "math.fraction.comparison",
                "math.fraction.add",
                "math.fraction.multiplication",
            ),
            bloom_layer=BloomLevel.APPLY,
        ),
        ThresholdConceptEntry(
            tc_id="TC_function_graph",
            name="函数图像",
            description="从『画图』的操作技能，过渡到『几何直观与代数表达对应』的分析工具——图即数，数即图。",
            pre_conception="函数图像就是把 x 值带进去算出 y 值，然后描点连线",
            liminal_signals=(
                "我知道图像能看出 y 随 x 怎么变，但说不出更深的",
                "为什么一次函数是直线，二次函数是抛物线？",
                "从图像上我能看出解，但列方程算和看图什么关系？",
            ),
            post_conception="函数图像是代数关系的几何表征，图像的斜率、截距、开口、对称性都对应代数量",
            crossing_indicators=(
                "能根据 k 的正负判断一次函数图像经过的象限",
                "能从 y=ax²+bx+c 的系数推断开口方向和顶点位置",
                "能用图像法解释方程组的解的几何意义",
            ),
            skill_ids=(
                "math.function.linear",
                "math.function.quadratic",
                "math.function.graph",
            ),
            bloom_layer=BloomLevel.ANALYZE,
        ),
        ThresholdConceptEntry(
            tc_id="TC_limit",
            name="极限（初步）",
            description="从『算术就是精确计算』的认知，过渡到『无限接近』的动态思维——有些值只能逼近不能到达。",
            pre_conception="0.999... 和 1 就是不一样的小数，最终差一点",
            liminal_signals=(
                "0.999...=1？为什么总是差那么一点点？",
                "无限接近但永远到不了，那不就是没有吗？",
                "老师说『趋向于』，但我理解不了『永远在接近』",
            ),
            post_conception="无限小数是有限小数的延伸极限，0.999... 的极限是 1，两者相等是极限定义的必然",
            crossing_indicators=(
                "能用自己的话解释『无限接近但永不相交』",
                "能用夹逼准则说明 0.999...=1",
                "能区分『精确值』与『极限值』的概念差异",
            ),
            skill_ids=(
                "math.number.scientific_notation",
                "math.circle.pi_definition",
            ),
            bloom_layer=BloomLevel.EVALUATE,
        ),
    ]

    def __init__(self) -> None:
        self._by_id: dict[str, ThresholdConceptEntry] = {e.tc_id: e for e in self._entries}

    def get(self, tc_id: str) -> ThresholdConceptEntry | None:
        return self._by_id.get(tc_id)

    def all_entries(self) -> list[ThresholdConceptEntry]:
        return list(self._entries)

    def all_tc_ids(self) -> list[str]:
        return [e.tc_id for e in self._entries]
