"""CTA Misconception Library（初中数学 MVP）.

对应 research/30-shared-cognitive-tools/theoretical-foundations/
03-c-dimension-content-libraries.md §2.6（MVP 候选 30 条）。

覆盖五大类：代数基础 / 方程求解 / 几何 / 函数 / 统计与概率 / 不等式。

M2 W3 范围：BeliefEngine.update() 集成 LLM Critic → C 维度折扣。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from ..belief_state import BloomLevel


@dataclass(frozen=True)
class MisconceptionEntry:
    """单条 Misconception 条目.

    Attributes:
        misc_id: 唯一标识，如 "M1"
        name: 短名称
        description: 1-2 句解释 misconception 是什么
        trigger_patterns: LLM Critic 输入的学生表述样例（tuple，2-4 条）
        detection_keywords: 关键词匹配兜底（tuple）
        skill_id: 关联知识点 ID（与 Q 矩阵对齐）
        correction_strategy: 修正策略 ID（LCA 据此选干预类型）
        bloom_layer: 通常触发的 Bloom 层
        category: 大类标签
    """

    misc_id: str
    name: str
    description: str
    trigger_patterns: tuple[str, ...]
    detection_keywords: tuple[str, ...]
    skill_id: str
    correction_strategy: str
    bloom_layer: BloomLevel
    category: str


class MisconceptionLibrary:
    """初中数学 Misconception 库（MVP，30 条）。

    用法：
        library = MisconceptionLibrary()
        entry = library.get("M1")
        hits = library.filter_by_skill("math.algebra.linear")
    """

    _entries: ClassVar[list[MisconceptionEntry]] = [
        # ─── 代数基础 ───────────────────────────────────────────────
        MisconceptionEntry(
            misc_id="M1",
            name="乘法总是变大",
            description="学生认为「被乘数不变，乘数越大积越大」，无法理解 0.5×5 < 5。",
            trigger_patterns=(
                "5×0.5 怎么变小了？",
                "乘法应该越乘越大啊",
                "0.5 个 5 为什么比 5 小？",
            ),
            detection_keywords=("变小", "越乘越大", "0.5", "乘以小数"),
            skill_id="math.decimal.multiplication",
            correction_strategy="number_line_visualization",
            bloom_layer=BloomLevel.APPLY,
            category="代数基础",
        ),
        MisconceptionEntry(
            misc_id="M2",
            name="分母大→分数大",
            description="直觉认为分母越大分数越小（对正分数成立），但未理解分子也起作用。",
            trigger_patterns=(
                "1/8 比 1/4 大吗？分母大不是更小吗？",
                "为什么 1/8 比 1/4 小？",
                "分母越大分数越小啊",
            ),
            detection_keywords=("分母大", "分数小", "1/8", "1/4"),
            skill_id="math.fraction.comparison",
            correction_strategy="pizza_slice_visualization",
            bloom_layer=BloomLevel.UNDERSTAND,
            category="代数基础",
        ),
        MisconceptionEntry(
            misc_id="M7",
            name="平方=2倍",
            description="混淆 x² 与 2x，认为它们是等价的。",
            trigger_patterns=(
                "x² 就是 2x 吧？",
                "平方不就是乘以 2 吗？",
                "3²=6，没问题啊",
            ),
            detection_keywords=("平方", "2x", "乘以2", "x平方"),
            skill_id="math.algebra.power",
            correction_strategy="geometry_square_area",
            bloom_layer=BloomLevel.APPLY,
            category="代数基础",
        ),
        MisconceptionEntry(
            misc_id="M11",
            name="移项不变号",
            description="解方程时移项忘记变号，或不理解为何要变号。",
            trigger_patterns=(
                "x+3=5，x=5+3=8",
                "3 移到右边还是加啊",
                "移项不变号吧？",
                "x-5=3，x=3-5=-2",
            ),
            detection_keywords=("移项", "变号", "方程"),
            skill_id="math.linear_equation.solve",
            correction_strategy="balance_scale_analogy",
            bloom_layer=BloomLevel.APPLY,
            category="代数基础",
        ),
        MisconceptionEntry(
            misc_id="M12",
            name="分数加减法直接分母相加",
            description="将 1/2 + 1/3 直接算成 2/5，不理解通分。",
            trigger_patterns=(
                "1/2+1/3=2/5，对吗？",
                "分母直接加一起",
                "1/2+1/3=2/5",
            ),
            detection_keywords=("分母加", "分数加", "通分"),
            skill_id="math.fraction.add",
            correction_strategy="fraction_tile_visualization",
            bloom_layer=BloomLevel.APPLY,
            category="代数基础",
        ),
        # ─── 方程求解 ──────────────────────────────────────────────
        MisconceptionEntry(
            misc_id="M3",
            name="等式性质错误推广到不等式",
            description="认为不等式两边同乘正负数都不变号，或混淆变号规则。",
            trigger_patterns=(
                "-2x>6，两边除以-2，x>-3",
                "不等式两边乘不变号吧？",
                "同乘一个负数不用变号",
                "两边同除以-2，符号不变",
            ),
            detection_keywords=("不等式", "变号", "负数", "两边同除"),
            skill_id="math.inequality.transform",
            correction_strategy="counter_example_symbol_flip",
            bloom_layer=BloomLevel.ANALYZE,
            category="方程求解",
        ),
        MisconceptionEntry(
            misc_id="M13",
            name="一元二次方程判别式记错",
            description="混淆 Δ=b²-4ac 与 b²+4ac，或忘记何时用判别式。",
            trigger_patterns=(
                "判别式是 b²+4ac 吧？",
                "Δ=b²+4ac",
                "什么时候用判别式？",
            ),
            detection_keywords=("判别式", "b平方", "4ac", "delta"),
            skill_id="math.quadratic.definition",
            correction_strategy="quadratic_formula_drill",
            bloom_layer=BloomLevel.APPLY,
            category="方程求解",
        ),
        MisconceptionEntry(
            misc_id="M20",
            name="代入消元时符号丢失",
            description="用代入法解方程组时，代入后漏写负号或括号。",
            trigger_patterns=(
                "y=x+1，代入后 x+(x+1)=3",
                "代入之后符号怎么变？",
                "y=2x-3，代入后 3x-(2x-3)=1",
            ),
            detection_keywords=("代入", "消元", "方程组", "符号"),
            skill_id="math.linear_system.substitution",
            correction_strategy="bracket_expansion_practice",
            bloom_layer=BloomLevel.APPLY,
            category="方程求解",
        ),
        MisconceptionEntry(
            misc_id="M21",
            name="分式方程增根不检验",
            description="解分式方程两边乘以公分母后产生增根，但不解检验步骤。",
            trigger_patterns=(
                "解完了，不用检验吧？",
                "1/(x-2)=3，x=7/3，检验太麻烦",
                "增根是什么？",
            ),
            detection_keywords=("分式方程", "增根", "检验", "公分母"),
            skill_id="math.rational_equation.solve",
            correction_strategy="extraneous_root_check",
            bloom_layer=BloomLevel.ANALYZE,
            category="方程求解",
        ),
        # ─── 几何 ─────────────────────────────────────────────────
        MisconceptionEntry(
            misc_id="M4",
            name="负数不存在",
            description="认为负数是「没有」或不存在，无法理解数轴上的对称性。",
            trigger_patterns=(
                "苹果不能是负的",
                "哪有负三个苹果？",
                "负数不是真实存在的数",
            ),
            detection_keywords=("负数", "不存在", "没有"),
            skill_id="math.number.negative",
            correction_strategy="debt_number_line_analogy",
            bloom_layer=BloomLevel.UNDERSTAND,
            category="几何",
        ),
        MisconceptionEntry(
            misc_id="M5",
            name="0是『没有』",
            description="把 0 简单理解为「空」或「无」，不理解 0 在不同语境中的角色（坐标/角度/温度）。",
            trigger_patterns=(
                "0就是什么也没有",
                "0°C 表示没有温度",
                "原点就是0，没什么特别的",
            ),
            detection_keywords=("0", "没有", "原点", "空"),
            skill_id="math.number.zero",
            correction_strategy="multi_context_zero_exploration",
            bloom_layer=BloomLevel.UNDERSTAND,
            category="几何",
        ),
        MisconceptionEntry(
            misc_id="M9",
            name="几何证明=计算",
            description="把几何证明题当作计算题来完成，不理解证明的逻辑结构。",
            trigger_patterns=(
                "证明题就是算出来",
                "这题怎么算？",
                "证明就是求角度吧？",
            ),
            detection_keywords=("证明", "计算", "求证"),
            skill_id="math.geometry.proof",
            correction_strategy="proof_structure_scaffold",
            bloom_layer=BloomLevel.ANALYZE,
            category="几何",
        ),
        MisconceptionEntry(
            misc_id="M14",
            name="圆面积公式与周长公式混淆",
            description="把圆面积记成 2πr（周长）或 πd²（错误指数）。",
            trigger_patterns=(
                "圆面积是 2πr 吧？",
                "πr² 我记成 πd 了",
                "面积不是周长吗？",
                "圆面积=πd",
            ),
            detection_keywords=("圆面积", "2πr", "πd", "周长"),
            skill_id="math.circle.area",
            correction_strategy="derivation_from_disk_partition",
            bloom_layer=BloomLevel.UNDERSTAND,
            category="几何",
        ),
        MisconceptionEntry(
            misc_id="M15",
            name="三角形内角和=180°需死记",
            description="接受三角形内角和=180°但不理解为何成立（平行线内错角）。",
            trigger_patterns=(
                "记住180度就行了",
                "为什么内角和是180度？",
                "不用证明吧，背下来就好",
            ),
            detection_keywords=("内角和", "180", "证明", "为什么"),
            skill_id="math.geometry.triangle_angle_sum",
            correction_strategy="parallel_line_cut_visualization",
            bloom_layer=BloomLevel.UNDERSTAND,
            category="几何",
        ),
        MisconceptionEntry(
            misc_id="M16",
            name="勾股定理滥用（任意三角形）",
            description="对任意三角形直接用 a²+b²=c²，不验证直角条件。",
            trigger_patterns=(
                "勾股定理直接用就行",
                "三边分别是3、4、5，直接套公式",
                "不是直角三角形也能用吧？",
            ),
            detection_keywords=("勾股", "直角", "a²+b²", "3、4、5"),
            skill_id="math.geometry.pythagorean",
            correction_strategy="right_angle_check_first",
            bloom_layer=BloomLevel.APPLY,
            category="几何",
        ),
        # ─── 函数 ─────────────────────────────────────────────────
        MisconceptionEntry(
            misc_id="M8",
            name="函数必过原点",
            description="假设 f(0)=0 对所有函数成立，不理解函数图像的平移。",
            trigger_patterns=(
                "x=0时y一定是0",
                "函数都过原点",
                "f(x)=x+1 在 x=0 时 y=0？",
            ),
            detection_keywords=("过原点", "f(0)", "函数", "原点"),
            skill_id="math.function.basics",
            correction_strategy="counter_example_f_x_plus_1",
            bloom_layer=BloomLevel.UNDERSTAND,
            category="函数",
        ),
        MisconceptionEntry(
            misc_id="M17",
            name="正比例函数图像必过一二象限",
            description="未理解 k 的正负与象限的关系，认为正比例函数必过一三象限。",
            trigger_patterns=(
                "正比例函数都在一三象限",
                "k是正的就在上面",
                "y=kx 不过二四象限吧？",
            ),
            detection_keywords=("正比例", "象限", "k", "过一三"),
            skill_id="math.function.linear",
            correction_strategy="k_sign_and_quadrant",
            bloom_layer=BloomLevel.ANALYZE,
            category="函数",
        ),
        MisconceptionEntry(
            misc_id="M18",
            name="反比例函数图像画法错误",
            description="在第一象限画完整双曲线，不理解双曲线两支永不相交坐标轴。",
            trigger_patterns=(
                "反比例函数图像是这样的吧？（画错）",
                "两支曲线会连起来吗？",
                "图像应该在坐标轴里面",
            ),
            detection_keywords=("反比例", "双曲线", "两支", "坐标轴"),
            skill_id="math.function.inverse",
            correction_strategy="hyperbola_asymptote_explanation",
            bloom_layer=BloomLevel.UNDERSTAND,
            category="函数",
        ),
        MisconceptionEntry(
            misc_id="M19",
            name="二次函数顶点必是最大值",
            description="未理解开口方向与顶点极值的关系，认为所有二次函数顶点都是最大值点。",
            trigger_patterns=(
                "顶点就是最高点",
                "二次函数开口向下才对",
                "顶点一定是最大值吧？",
            ),
            detection_keywords=("顶点", "最大值", "最小值", "开口向下"),
            skill_id="math.function.quadratic",
            correction_strategy="a_sign_and_extremum",
            bloom_layer=BloomLevel.ANALYZE,
            category="函数",
        ),
        # ─── 统计与概率 ───────────────────────────────────────────
        MisconceptionEntry(
            misc_id="M10",
            name="概率是『运气』",
            description="不理解概率的频率解释，认为 50% 概率意味着「一定会发生一次」。",
            trigger_patterns=(
                "50% 概率就意味着必发生一次",
                "我运气好，所以这次肯定对",
                "投硬币正面已经连续5次了，下次一定是反面",
            ),
            detection_keywords=("运气", "50%", "一定", "连续", "概率"),
            skill_id="math.probability.frequency",
            correction_strategy="law_of_large_numbers_simulation",
            bloom_layer=BloomLevel.UNDERSTAND,
            category="统计与概率",
        ),
        MisconceptionEntry(
            misc_id="M22",
            name="平均数必在最大值与最小值之间",
            description="知道平均数概念但不理解其统计含义，或混淆平均数与中位数。",
            trigger_patterns=(
                "平均数一定比最大的小吗？",
                "平均数就是中间那个数吧？",
                "中位数和平均数有什么区别？",
            ),
            detection_keywords=("平均数", "中位数", "最大", "最小"),
            skill_id="math.statistics.mean_median",
            correction_strategy="data_set_center_concept",
            bloom_layer=BloomLevel.UNDERSTAND,
            category="统计与概率",
        ),
        MisconceptionEntry(
            misc_id="M23",
            name="相关=因果",
            description="混淆相关关系与因果关系，认为两个统计相关的变量必有因果关系。",
            trigger_patterns=(
                "这两个数据相关，所以一个导致另一个",
                "冰淇淋销量和溺水人数相关，说明冰淇淋让人溺水",
                "身高和数学成绩相关，所以长高会导致数学变好",
            ),
            detection_keywords=("相关", "因果", "导致", "所以"),
            skill_id="math.statistics.correlation",
            correction_strategy="correlation_vs_causation_examples",
            bloom_layer=BloomLevel.ANALYZE,
            category="统计与概率",
        ),
        # ─── 数与式 ──────────────────────────────────────────────
        MisconceptionEntry(
            misc_id="M6",
            name="圆周率是3.14",
            description="把 π 视为近似值而非无理数，不理解圆周率的几何定义。",
            trigger_patterns=(
                "π就是3.14",
                "π 是精确值吗？",
                "圆周率算出来不是3.14吗？",
            ),
            detection_keywords=("π", "3.14", "圆周率", "精确值"),
            skill_id="math.circle.pi_definition",
            correction_strategy="circumference_limit_definition",
            bloom_layer=BloomLevel.UNDERSTAND,
            category="数与式",
        ),
        MisconceptionEntry(
            misc_id="M24",
            name="绝对值就是去符号",
            description="只记住 |a| 去掉负号，不理解绝对值的几何意义（距离）。",
            trigger_patterns=(
                "绝对值就是把负号去掉",
                "|−5|=5，就是去符号",
                "绝对值没有负的，对吧？",
            ),
            detection_keywords=("绝对值", "去符号", "负号", "|"),
            skill_id="math.number.absolute_value",
            correction_strategy="distance_on_number_line",
            bloom_layer=BloomLevel.UNDERSTAND,
            category="数与式",
        ),
        MisconceptionEntry(
            misc_id="M25",
            name="幂的运算规则混淆（指数加减 vs 乘法）",
            description="将 a^m · a^n = a^{m+n} 错误推广为 a^m · a^n = a^{mn}。",
            trigger_patterns=(
                "a²·a³=a⁶？指数相乘",
                "幂的乘法就是指数相乘吧？",
                "a²·a³=a⁵（对）或 a⁶（错）",
            ),
            detection_keywords=("幂", "指数", "相乘", "a^m"),
            skill_id="math.power.exponent_rules",
            correction_strategy="exponent_addition_vs_multiplication",
            bloom_layer=BloomLevel.APPLY,
            category="数与式",
        ),
        # ─── 补充（凑满 30 条，覆盖更多高频错误区）─────────────
        MisconceptionEntry(
            misc_id="M26",
            name="平行线性质用错（内错角相等当同位角）",
            description="混淆内错角与同位角，或在平行线判定中使用错误角对。",
            trigger_patterns=(
                "内错角相等，这是同位角吧？",
                "两条线被第三条线切，内错角相等就是平行",
                "平行线的同位角相等吧？",
            ),
            detection_keywords=("内错角", "同位角", "平行线", "相等"),
            skill_id="math.geometry.parallel_lines",
            correction_strategy="angle_pairVocabulary_drill",
            bloom_layer=BloomLevel.ANALYZE,
            category="几何",
        ),
        MisconceptionEntry(
            misc_id="M27",
            name="因式分解与展开混淆",
            description="将 (a+b)² 展开成 a²+b²，漏掉 2ab 交叉项。",
            trigger_patterns=(
                "(a+b)²=a²+b²，没问题",
                "展开就是因式分解反过来",
                "完全平方公式中间那项去哪了？",
            ),
            detection_keywords=("完全平方", "展开", "因式分解", "2ab"),
            skill_id="math.algebra.factorization",
            correction_strategy="area_model_square_expansion",
            bloom_layer=BloomLevel.APPLY,
            category="代数基础",
        ),
        MisconceptionEntry(
            misc_id="M28",
            name="科学计数法小数点移动方向记反",
            description="将 3.5×10⁻² 当作 0.035（正确）但无法解释，或混淆移动方向。",
            trigger_patterns=(
                "10的负二次方小数点往哪边移？",
                "负指数就是变小，数变小往左移",
                "3.5×10⁻²=0.00035？",
            ),
            detection_keywords=("科学计数法", "负指数", "小数点", "移动"),
            skill_id="math.number.scientific_notation",
            correction_strategy="decimal_place_value_chart",
            bloom_layer=BloomLevel.APPLY,
            category="数与式",
        ),
        MisconceptionEntry(
            misc_id="M29",
            name="菱形面积公式记为对角线乘积的一半（正确但不知来源）",
            description="记住 S=½ac 但不理解为何对角线垂直时成立（菱形对角线垂直平分）。",
            trigger_patterns=(
                "菱形面积就是对角线相乘除以2，背下来就行",
                "为什么对角线垂直时才能用这个公式？",
                "平行四边形也能用吗？",
            ),
            detection_keywords=("菱形", "对角线", "面积", "垂直"),
            skill_id="math.geometry.rhombus_area",
            correction_strategy="diagonal_perpendicular_property",
            bloom_layer=BloomLevel.UNDERSTAND,
            category="几何",
        ),
        MisconceptionEntry(
            misc_id="M30",
            name="函数定义域默认全体实数",
            description="求函数定义域时忽略分母不为零、偶次根号内非负等限制条件。",
            trigger_patterns=(
                "定义域就是 x 能取的数吧？x是全体实数",
                "y=1/x，x 可以是0吗？应该可以吧？",
                "根号里面要正的吗？不用管吧",
            ),
            detection_keywords=("定义域", "分母", "根号", "全体实数"),
            skill_id="math.function.domain",
            correction_strategy="domain_restriction_checklist",
            bloom_layer=BloomLevel.APPLY,
            category="函数",
        ),
    ]

    def __init__(self) -> None:
        self._by_id: dict[str, MisconceptionEntry] = {e.misc_id: e for e in self._entries}

    def get(self, misc_id: str) -> MisconceptionEntry | None:
        return self._by_id.get(misc_id)

    def filter_by_skill(self, skill_id: str) -> list[MisconceptionEntry]:
        return [e for e in self._entries if e.skill_id == skill_id]

    def filter_by_category(self, category: str) -> list[MisconceptionEntry]:
        return [e for e in self._entries if e.category == category]

    def all_entries(self) -> list[MisconceptionEntry]:
        return list(self._entries)

    def all_categories(self) -> list[str]:
        return sorted({e.category for e in self._entries})
