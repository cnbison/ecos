"""v0.54.1-b: 追加 20 道 PB-C 主导题到 data/python_basics_q_matrix.json.

按 v0.54.1-a 设计文档 (research/90-mvp/09-phase5-c-dimension-questions-expanded.md)
生成 20 道 C 主导题, 5 topic × 4 Bloom 层均匀分布.

Schema 对齐现有 26 题 (problem_id, topic, skill_name, problem_text,
correct_answer, bloom_layer_observed, a_specialized, mirt_params,
misconceptions, intervention_types).

运行: python scripts/add_pb_c_questions.py
"""
import json
from pathlib import Path

Q_MATRIX_PATH = Path("data/python_basics_q_matrix.json")


# 20 道 PB-C 题定义 (按 v0.54.1-a 设计)
PB_C_QUESTIONS = [
    # ──── v0.54.0-b 已设计 5 道 ────
    {
        "problem_id": "PB-C01",
        "topic": "python.loops",
        "skill_name": "循环边界",
        "bloom_goal_id": "python.loops-L3",
        "problem_text": (
            "以下代码期望输出 1, 2, 3, 4, 5，但实际输出 1, 2, 3, 4\n"
            "错在哪？怎么修？\n\n"
            "for i in range(1, 5):\n"
            "    print(i)"
        ),
        "correct_answer": (
            "Bug 在 range(1, 5) 不包含 5，应改为 range(1, 6)。\n"
            "原因: range(a, b) 是左闭右开区间 [a, b)，不包含 b。"
        ),
        "bloom_layer_observed": "L3",
        "a_specialized": [0.3, 0.4, 0.3, 1.2, 0.0],
        "mirt_params": {"difficulty": -0.5, "discrimination": 1.0, "guessing": 0.0},
        "misconceptions": ["M3"],
        "intervention_types": ["EXPLANATION", "SCAFFOLDING"],
        "c_dimension_type": "调试题",
        "partial_credit_rubric": {
            "0.0": "未识别或答错",
            "0.3": "识别 range(1,5) 但说 '5 应该在'",
            "0.6": "识别 + 修复为 range(1,6) 但没说原因",
            "1.0": "完整: 位置 + 原因 + 修复",
        },
    },
    {
        "problem_id": "PB-C02",
        "topic": "python.loops",
        "skill_name": "循环 continue 行为",
        "bloom_goal_id": "python.loops-L4",
        "problem_text": (
            "以下代码期望输出 1, 2, 3，但实际什么都没有输出（题目描述）\n"
            "错在哪？怎么修？\n\n"
            "for i in range(1, 4):\n"
            "    if i == 2:\n"
            "        continue\n"
            "    print(i)"
        ),
        "correct_answer": (
            "这段代码实际是对的，输出 1 和 3 (skip 2)。\n"
            "题目说'实际什么都没有输出'是诱饵。\n"
            "正确回答: 代码实际是对的，输出 1, 3, skip 2。"
        ),
        "bloom_layer_observed": "L4",
        "a_specialized": [0.3, 0.4, 0.3, 1.3, 0.0],
        "mirt_params": {"difficulty": 0.2, "discrimination": 1.0, "guessing": 0.0},
        "misconceptions": [],
        "intervention_types": ["EXPLANATION"],
        "c_dimension_type": "调试题(诱饵)",
        "partial_credit_rubric": {
            "0.0": "说'代码错在某行'",
            "0.3": "识别 continue 但说'跳过了所有'",
            "0.6": "识别'输出 1, 3, skip 2' 但没说'代码是对的'",
            "1.0": "完整: 识别陷阱 + 正确 trace",
        },
    },
    {
        "problem_id": "PB-C03",
        "topic": "python.functions",
        "skill_name": "类型错误分析",
        "bloom_goal_id": "python.functions-L5",
        "problem_text": (
            "运行以下代码会报错:\n"
            "TypeError: unsupported operand type(s) for +: 'int' and 'str'\n"
            "错在哪？怎么修？\n\n"
            "def add(a, b):\n"
            "    return a + b\n\n"
            "x = add(1, '2')\n"
            "print(x)"
        ),
        "correct_answer": (
            "错误原因: add(1, '2') 中 1 是 int，'2' 是 str，不能直接相加。\n"
            "修复: 转类型 add(1, int('2')) 或 add(str(1), '2') (按需)。"
        ),
        "bloom_layer_observed": "L5",
        "a_specialized": [0.4, 0.6, 0.4, 1.0, 0.0],
        "mirt_params": {"difficulty": 0.0, "discrimination": 1.2, "guessing": 0.0},
        "misconceptions": [],
        "intervention_types": ["EXPLANATION", "PRACTICE"],
        "c_dimension_type": "错误分析",
        "partial_credit_rubric": {
            "0.0": "未识别类型问题",
            "0.3": "识别 int+str 但没说怎么修",
            "0.6": "识别 + 给出 int() 转换",
            "1.0": "完整: 错误原因 + 多种修复方案 + 适用场景",
        },
    },
    {
        "problem_id": "PB-C04",
        "topic": "python.scope",
        "skill_name": "局部 vs 全局",
        "bloom_goal_id": "python.scope-L5",
        "problem_text": (
            "以下代码输出什么？为什么？\n\n"
            "x = 10\n\n"
            "def foo():\n"
            "    x = 20\n"
            "    print(x)\n\n"
            "foo()\n"
            "print(x)"
        ),
        "correct_answer": (
            "输出: 20 然后 10。\n"
            "原因: foo() 内的 x = 20 是局部变量，不影响外部 x = 10。"
        ),
        "bloom_layer_observed": "L5",
        "a_specialized": [0.3, 0.3, 0.3, 1.1, 0.0],
        "mirt_params": {"difficulty": -0.3, "discrimination": 1.1, "guessing": 0.0},
        "misconceptions": ["M-candidate-scope-confusion"],
        "intervention_types": ["EXPLANATION", "WORKED_EXAMPLE"],
        "c_dimension_type": "代码阅读",
        "partial_credit_rubric": {
            "0.0": "说'输出 20'（部分对）",
            "0.3": "说'输出 20, 20'（不理解 scope）",
            "0.6": "说'输出 20, 10' 但没说原因",
            "1.0": "完整: 输出 + 原因（局部 vs 全局）",
        },
    },
    {
        "problem_id": "PB-C05",
        "topic": "python.recursion",
        "skill_name": "递归调试方法",
        "bloom_goal_id": "python.recursion-L4",
        "problem_text": (
            "运行 fib(5) 卡死很长时间\n"
            "不用看代码，你打算用什么方法快速定位问题？\n\n"
            "def fib(n):\n"
            "    if n <= 1:\n"
            "        return n\n"
            "    return fib(n-1) + fib(n-2)"
        ),
        "correct_answer": (
            "调试方法列表:\n"
            "1. 加 print 跟踪: 在函数入口 print n 看调用次数\n"
            "2. 画递归树: 手算 fib(5) 的递归树，识别重复计算\n"
            "3. 测小输入: 先 fib(3) 看是否也慢\n"
            "4. 用 lru_cache / memoization: 直接验证是重复计算问题"
        ),
        "bloom_layer_observed": "L4",
        "a_specialized": [0.2, 0.5, 0.8, 0.6, 0.0],
        "mirt_params": {"difficulty": 0.3, "discrimination": 0.9, "guessing": 0.0},
        "misconceptions": ["M-candidate-recursion-no-memo"],
        "intervention_types": ["EXPLANATION", "SCAFFOLDING"],
        "c_dimension_type": "调试策略",
        "partial_credit_rubric": {
            "0.0": "未给方法",
            "0.3": "单一方法（加 print）但不系统",
            "0.6": "多方法（print + 测小输入）但没排序",
            "1.0": "系统化方法（先 print 跟踪 → 识别重复 → memoization 验证）",
        },
    },
    # ──── v0.54.1 新增 15 道 ────
    {
        "problem_id": "PB-C06",
        "topic": "python.variables",
        "skill_name": "变量赋值",
        "bloom_goal_id": "python.variables-L3",
        "problem_text": (
            "以下代码输出什么？为什么？\n\n"
            "x = 5\n"
            "y = x\n"
            "x = 10\n"
            "print(y)"
        ),
        "correct_answer": "5，因为 y = x 时 y 指向 5 这个 int 对象，x 重新赋值不改变 y。",
        "bloom_layer_observed": "L3",
        "a_specialized": [0.4, 0.3, 0.2, 1.0, 0.0],
        "mirt_params": {"difficulty": -0.3, "discrimination": 1.0, "guessing": 0.0},
        "misconceptions": [],
        "intervention_types": ["EXPLANATION"],
        "c_dimension_type": "代码阅读",
        "partial_credit_rubric": {
            "0.0": "答 10（不理解变量赋值）",
            "0.3": "答 5 但没说原因",
            "0.6": "答 5 + 简单解释（'y 不变'）",
            "1.0": "完整: 答 5 + 解释变量指向 + 引用 vs 复制",
        },
    },
    {
        "problem_id": "PB-C07",
        "topic": "python.variables",
        "skill_name": "可变对象引用",
        "bloom_goal_id": "python.variables-L4",
        "problem_text": (
            "以下代码输出什么？为什么？\n\n"
            "a = [1, 2]\n"
            "b = a\n"
            "b.append(3)\n"
            "print(a)"
        ),
        "correct_answer": "[1, 2, 3]，因为 b = a 让 b 指向 a 同一 list 对象，append 改了 list。",
        "bloom_layer_observed": "L4",
        "a_specialized": [0.3, 0.2, 0.4, 1.1, 0.0],
        "mirt_params": {"difficulty": 0.0, "discrimination": 1.1, "guessing": 0.0},
        "misconceptions": ["M-candidate-mutable-confusion"],
        "intervention_types": ["EXPLANATION", "WORKED_EXAMPLE"],
        "c_dimension_type": "调试题",
        "partial_credit_rubric": {
            "0.0": "答 [1, 2]（不理解 mutable）",
            "0.3": "答 [1, 2, 3] 但没说原因",
            "0.6": "答 [1, 2, 3] + 解释 b = a 共享对象",
            "1.0": "完整: mutable vs immutable 区分 + 修法（b = a.copy()）",
        },
    },
    {
        "problem_id": "PB-C08",
        "topic": "python.variables",
        "skill_name": "dict 键错误",
        "bloom_goal_id": "python.variables-L5",
        "problem_text": (
            "运行以下代码报错:\n"
            "KeyError: 'age'\n"
            "错在哪？至少给出 2 种修法。\n\n"
            "user = {'name': 'Bisen'}\n"
            "print(user['age'])"
        ),
        "correct_answer": (
            "原因: dict 没 'age' 键。\n"
            "修法 1: user.get('age', default_value)\n"
            "修法 2: try/except KeyError\n"
            "修法 3: if 'age' in user: ..."
        ),
        "bloom_layer_observed": "L5",
        "a_specialized": [0.3, 0.5, 0.3, 1.2, 0.0],
        "mirt_params": {"difficulty": -0.2, "discrimination": 1.0, "guessing": 0.0},
        "misconceptions": [],
        "intervention_types": ["EXPLANATION", "PRACTICE"],
        "c_dimension_type": "错误分析",
        "partial_credit_rubric": {
            "0.0": "未识别 KeyError 原因",
            "0.3": "识别 + 单一修法（if 'age' in user）",
            "0.6": "识别 + 2 种修法",
            "1.0": "识别 + 3 种修法 + 适用场景对比",
        },
    },
    {
        "problem_id": "PB-C09",
        "topic": "python.variables",
        "skill_name": "系统化调试方法",
        "bloom_goal_id": "python.variables-L6",
        "problem_text": (
            "以下代码期望 x=5 时输出 'matched', 否则 'unmatched'\n"
            "但实际无论 x 等于什么, 都输出 'unmatched'\n"
            "不用看代码, 你打算用什么方法快速定位问题？\n\n"
            "x = 5\n"
            "if x == 5:\n"
            "    print('matched')\n"
            "print('unmatched')"
        ),
        "correct_answer": (
            "调试方法列表:\n"
            "1. print 跟踪: 在 if x == 5: 前 print x 看实际值\n"
            "2. 断点调试: 用 pdb / IDE 断点停在 if 处\n"
            "3. 单元测试: 写 assert x == 5 测试 if 条件\n"
            "4. 删代码法: 先注掉 print('unmatched') 看 if 是否进入"
        ),
        "bloom_layer_observed": "L6",
        "a_specialized": [0.2, 0.6, 0.9, 0.5, 0.0],
        "mirt_params": {"difficulty": 0.4, "discrimination": 0.9, "guessing": 0.0},
        "misconceptions": [],
        "intervention_types": ["EXPLANATION", "SCAFFOLDING"],
        "c_dimension_type": "调试策略",
        "partial_credit_rubric": {
            "0.0": "未给方法",
            "0.3": "单方法（加 print）",
            "0.6": "多方法（print + 注释）但没排序",
            "1.0": "系统化方法（print 跟踪 → 验证 if 条件 → 单元测试）",
        },
    },
    {
        "problem_id": "PB-C10",
        "topic": "python.loops",
        "skill_name": "IndexError 越界",
        "bloom_goal_id": "python.loops-L5",
        "problem_text": (
            "运行以下代码报错:\n"
            "IndexError: list index out of range\n"
            "错在哪？怎么修？\n\n"
            "nums = [1, 2, 3]\n"
            "for i in range(5):\n"
            "    print(nums[i])"
        ),
        "correct_answer": (
            "原因: range(5) 包含 0-4，但 nums 只有 0-2。\n"
            "修法 1: range(len(nums)) 或 range(3)\n"
            "修法 2: try/except IndexError\n"
            "修法 3: if i < len(nums):"
        ),
        "bloom_layer_observed": "L5",
        "a_specialized": [0.3, 0.5, 0.3, 1.1, 0.0],
        "mirt_params": {"difficulty": -0.1, "discrimination": 1.1, "guessing": 0.0},
        "misconceptions": ["M3"],
        "intervention_types": ["EXPLANATION", "PRACTICE"],
        "c_dimension_type": "错误分析",
        "partial_credit_rubric": {
            "0.0": "未识别越界",
            "0.3": "识别 + 单一修法（if i < len(nums)）",
            "0.6": "识别 + 2 种修法",
            "1.0": "识别 + 3 种修法 + 适用场景对比",
        },
    },
    {
        "problem_id": "PB-C11",
        "topic": "python.loops",
        "skill_name": "嵌套循环 break 行为",
        "bloom_goal_id": "python.loops-L6",
        "problem_text": (
            "以下代码卡死（题目描述）\n"
            "找出哪一行错？怎么修？\n\n"
            "for i in range(3):\n"
            "    for j in range(3):\n"
            "        print(i, j)\n"
            "        if j == 1:\n"
            "            break"
        ),
        "correct_answer": (
            "这段代码其实是对的（外层 i 仍循环 0-2，内层 j 到 1 时 break）。\n"
            "题目说'卡死'是诱饵。\n"
            "真正卡死: 内层 j 写 while True: 或 for j in range(i, 3): 当 i=0。"
        ),
        "bloom_layer_observed": "L6",
        "a_specialized": [0.3, 0.5, 0.6, 1.0, 0.0],
        "mirt_params": {"difficulty": 0.5, "discrimination": 0.9, "guessing": 0.0},
        "misconceptions": ["M-candidate-nested-loop-confusion"],
        "intervention_types": ["EXPLANATION"],
        "c_dimension_type": "调试题(诱饵)",
        "partial_credit_rubric": {
            "0.0": "说'内层 j 错'",
            "0.3": "说'break 错'",
            "0.6": "识别代码其实是对的，但没给出真正卡死的例子",
            "1.0": "完整: 识别陷阱 + 解释 break 行为 + 真正卡死例子",
        },
    },
    {
        "problem_id": "PB-C12",
        "topic": "python.functions",
        "skill_name": "return 位置",
        "bloom_goal_id": "python.functions-L3",
        "problem_text": (
            "以下代码输出什么？\n\n"
            "def foo(x):\n"
            "    if x > 0:\n"
            "        return x\n"
            "    print('negative')\n"
            "    return 0\n\n"
            "print(foo(5))\n"
            "print(foo(-3))"
        ),
        "correct_answer": (
            "foo(5): x=5 > 0, return 5 → 打印 5。\n"
            "foo(-3): x=-3, 跳过 if, print 'negative', return 0 → 打印 negative 然后 0。"
        ),
        "bloom_layer_observed": "L3",
        "a_specialized": [0.3, 0.3, 0.2, 1.0, 0.0],
        "mirt_params": {"difficulty": -0.5, "discrimination": 1.0, "guessing": 0.0},
        "misconceptions": [],
        "intervention_types": ["EXPLANATION"],
        "c_dimension_type": "代码阅读",
        "partial_credit_rubric": {
            "0.0": "答错",
            "0.3": "答对 foo(5) 部分",
            "0.6": "两个都答对",
            "1.0": "两个都答对 + 解释 return 提前退出",
        },
    },
    {
        "problem_id": "PB-C13",
        "topic": "python.functions",
        "skill_name": "lambda 三元表达式",
        "bloom_goal_id": "python.functions-L4",
        "problem_text": (
            "以下代码报错（题目描述）:\n"
            "SyntaxError: cannot assign to conditional expression\n"
            "错在哪？怎么修？\n\n"
            "square = lambda x: x if x > 0 else -x\n"
            "print(square(-5))"
        ),
        "correct_answer": (
            "实际这段代码也是对的——Python 三元表达式 x if cond else -x 是合法 lambda。\n"
            "题目说'报错'是诱饵。\n"
            "真正会报错的是 lambda x: if x > 0: x else -x (lambda 体不能是 statement)。"
        ),
        "bloom_layer_observed": "L4",
        "a_specialized": [0.3, 0.4, 0.3, 1.2, 0.0],
        "mirt_params": {"difficulty": 0.3, "discrimination": 1.0, "guessing": 0.0},
        "misconceptions": [],
        "intervention_types": ["EXPLANATION"],
        "c_dimension_type": "调试题(诱饵)",
        "partial_credit_rubric": {
            "0.0": "说'语法错'",
            "0.3": "识别三元表达式",
            "0.6": "识别代码其实是对的",
            "1.0": "完整: 识别陷阱 + lambda vs def 对比 + 解释 Python ternary",
        },
    },
    {
        "problem_id": "PB-C14",
        "topic": "python.functions",
        "skill_name": "装饰器调试",
        "bloom_goal_id": "python.functions-L6",
        "problem_text": (
            "以下装饰器使用后函数行为异常\n"
            "不用看代码细节, 你打算用什么方法定位问题？\n\n"
            "def my_decorator(func):\n"
            "    def wrapper(*args):\n"
            "        print('calling', func.__name__)\n"
            "        return func(*args)\n"
            "    return wrapper\n\n"
            "@my_decorator\n"
            "def add(a, b):\n"
            "    return a + b\n\n"
            "print(add(2, 3))"
        ),
        "correct_answer": (
            "调试方法列表:\n"
            "1. print 跟踪: 在 wrapper 内 print args 看参数\n"
            "2. 单元测试: 单独测 add 函数 vs 装饰后 add\n"
            "3. 断点: 在 wrapper 内断点\n"
            "4. 简化: 先去掉装饰器，看 add 本身是否对"
        ),
        "bloom_layer_observed": "L6",
        "a_specialized": [0.2, 0.7, 0.8, 0.6, 0.0],
        "mirt_params": {"difficulty": 0.5, "discrimination": 0.9, "guessing": 0.0},
        "misconceptions": [],
        "intervention_types": ["EXPLANATION", "SCAFFOLDING"],
        "c_dimension_type": "调试策略",
        "partial_credit_rubric": {
            "0.0": "未给方法",
            "0.3": "单方法（加 print）",
            "0.6": "多方法（print + 单测）但没排序",
            "1.0": "系统化方法（先简化 → 单独测试 → 加 print → 断点）",
        },
    },
    {
        "problem_id": "PB-C15",
        "topic": "python.recursion",
        "skill_name": "缺 base case",
        "bloom_goal_id": "python.recursion-L3",
        "problem_text": (
            "运行以下代码会发生什么？\n\n"
            "def foo(n):\n"
            "    return foo(n-1) + 1\n\n"
            "print(foo(5))"
        ),
        "correct_answer": (
            "RecursionError: maximum recursion depth exceeded。\n"
            "因为没有 base case，递归无限。"
        ),
        "bloom_layer_observed": "L3",
        "a_specialized": [0.3, 0.3, 0.2, 1.1, 0.0],
        "mirt_params": {"difficulty": -0.2, "discrimination": 1.0, "guessing": 0.0},
        "misconceptions": [],
        "intervention_types": ["EXPLANATION"],
        "c_dimension_type": "错误分析",
        "partial_credit_rubric": {
            "0.0": "说'输出 5'（不理解递归）",
            "0.3": "说'卡住'",
            "0.6": "说'RecursionError'",
            "1.0": "RecursionError + 解释栈帧爆栈 + 修法（加 base case）",
        },
    },
    {
        "problem_id": "PB-C16",
        "topic": "python.recursion",
        "skill_name": "stack overflow 修复方法",
        "bloom_goal_id": "python.recursion-L5",
        "problem_text": (
            "fib(50) 报 RecursionError\n"
            "不用改代码, 你有哪些方法让 fib(50) 能跑通？"
        ),
        "correct_answer": (
            "方法:\n"
            "1. 加 sys.setrecursionlimit(10000) — 提高栈深度\n"
            "2. 改迭代版 fib — 用循环代替递归\n"
            "3. 加 @lru_cache — memoization\n"
            "4. trampoline 函数 — 尾递归优化"
        ),
        "bloom_layer_observed": "L5",
        "a_specialized": [0.2, 0.6, 0.7, 0.8, 0.0],
        "mirt_params": {"difficulty": 0.3, "discrimination": 1.0, "guessing": 0.0},
        "misconceptions": [],
        "intervention_types": ["EXPLANATION", "PRACTICE"],
        "c_dimension_type": "调试策略",
        "partial_credit_rubric": {
            "0.0": "未给方法",
            "0.3": "单方法（加 sys.setrecursionlimit）",
            "0.6": "2 种方法（递归深度 + memoization）",
            "1.0": "4 种方法 + 适用场景对比（哪个适合生产）",
        },
    },
    {
        "problem_id": "PB-C17",
        "topic": "python.recursion",
        "skill_name": "可变默认值陷阱",
        "bloom_goal_id": "python.recursion-L4",
        "problem_text": (
            "以下函数多次调用时, 列表会累积\n"
            "错在哪？怎么修？\n\n"
            "def add_item(item, lst=[]):\n"
            "    lst.append(item)\n"
            "    return lst\n\n"
            "print(add_item(1))  # [1]\n"
            "print(add_item(2))  # 期望 [2], 实际 [1, 2]"
        ),
        "correct_answer": (
            "原因: 默认参数 lst=[] 在函数定义时创建一次，多次调用共享。\n"
            "修法: 用 None 哨兵\n"
            "def add_item(item, lst=None):\n"
            "    if lst is None:\n"
            "        lst = []\n"
            "    lst.append(item)\n"
            "    return lst"
        ),
        "bloom_layer_observed": "L4",
        "a_specialized": [0.3, 0.3, 0.5, 1.1, 0.0],
        "mirt_params": {"difficulty": 0.0, "discrimination": 1.1, "guessing": 0.0},
        "misconceptions": ["M-candidate-mutable-default"],
        "intervention_types": ["EXPLANATION", "WORKED_EXAMPLE"],
        "c_dimension_type": "调试题",
        "partial_credit_rubric": {
            "0.0": "未识别共享",
            "0.3": "识别共享但说'每次 new list'",
            "0.6": "用 None 哨兵修",
            "1.0": "完整: 识别陷阱 + None 哨兵 + 解释 Python 默认参数求值时机",
        },
    },
    {
        "problem_id": "PB-C18",
        "topic": "python.scope",
        "skill_name": "UnboundLocalError",
        "bloom_goal_id": "python.scope-L3",
        "problem_text": (
            "运行以下代码报错:\n"
            "UnboundLocalError: local variable 'x' referenced before assignment\n"
            "错在哪？怎么修？\n\n"
            "x = 10\n"
            "def foo():\n"
            "    x = x + 1\n"
            "    print(x)\n\n"
            "foo()"
        ),
        "correct_answer": (
            "原因: foo() 内的 x = x + 1 让 x 变成局部变量，但 x + 1 时 x 还未定义。\n"
            "修法: 加 global x 或 nonlocal x。\n"
            "或传参数: def foo(x): return x + 1。"
        ),
        "bloom_layer_observed": "L3",
        "a_specialized": [0.3, 0.3, 0.2, 1.0, 0.0],
        "mirt_params": {"difficulty": -0.1, "discrimination": 1.0, "guessing": 0.0},
        "misconceptions": ["M-candidate-scope-confusion"],
        "intervention_types": ["EXPLANATION", "SCAFFOLDING"],
        "c_dimension_type": "调试题",
        "partial_credit_rubric": {
            "0.0": "未识别 UnboundLocalError",
            "0.3": "识别 + 加 global x",
            "0.6": "加 global + 测试",
            "1.0": "完整: global / nonlocal / 参数传递 3 种方案对比",
        },
    },
    {
        "problem_id": "PB-C19",
        "topic": "python.scope",
        "skill_name": "nonlocal 缺失",
        "bloom_goal_id": "python.scope-L4",
        "problem_text": (
            "以下代码期望 outer_var 累加\n"
            "实际每次调用都重置为 0\n"
            "错在哪？怎么修？\n\n"
            "def make_counter():\n"
            "    outer_var = 0\n"
            "    def inner():\n"
            "        outer_var = outer_var + 1\n"
            "        return outer_var\n"
            "    return inner\n\n"
            "counter = make_counter()\n"
            "print(counter())  # 期望 1\n"
            "print(counter())  # 期望 2, 实际 1"
        ),
        "correct_answer": (
            "原因: inner() 内的 outer_var = outer_var + 1 让 outer_var 变局部变量。\n"
            "修法: 加 nonlocal outer_var。"
        ),
        "bloom_layer_observed": "L4",
        "a_specialized": [0.3, 0.3, 0.4, 1.1, 0.0],
        "mirt_params": {"difficulty": 0.2, "discrimination": 1.1, "guessing": 0.0},
        "misconceptions": ["M-candidate-scope-confusion"],
        "intervention_types": ["EXPLANATION", "WORKED_EXAMPLE"],
        "c_dimension_type": "调试题",
        "partial_credit_rubric": {
            "0.0": "未识别",
            "0.3": "识别 + 加 nonlocal",
            "0.6": "加 nonlocal + 测试",
            "1.0": "完整: global / nonlocal / 闭包变量绑定陷阱 + 对比",
        },
    },
    {
        "problem_id": "PB-C20",
        "topic": "python.scope",
        "skill_name": "闭包变量绑定陷阱",
        "bloom_goal_id": "python.scope-L6",
        "problem_text": (
            "以下代码创建 5 个 lambda, 每个都返回 i\n"
            "但调用时全部返回 4\n"
            "不用看代码细节, 你打算用什么方法修复？\n\n"
            "funcs = [lambda: i for i in range(5)]\n"
            "for f in funcs:\n"
            "    print(f())"
        ),
        "correct_answer": (
            "原因: 闭包变量绑定陷阱，所有 lambda 共享同一个 i，最终 i=4。\n"
            "修法 1: 默认参数 lambda i=i: i\n"
            "修法 2: functools.partial\n"
            "修法 3: 函数包装 def make_f(i): return lambda: i"
        ),
        "bloom_layer_observed": "L6",
        "a_specialized": [0.2, 0.6, 0.7, 0.9, 0.0],
        "mirt_params": {"difficulty": 0.4, "discrimination": 0.9, "guessing": 0.0},
        "misconceptions": ["M-candidate-closure-binding"],
        "intervention_types": ["EXPLANATION", "SCAFFOLDING"],
        "c_dimension_type": "调试策略",
        "partial_credit_rubric": {
            "0.0": "未给方法",
            "0.3": "单方法（默认参数 i=i）",
            "0.6": "2 种方法",
            "1.0": "3 种方法 + 适用场景对比 + 解释 Python late binding",
        },
    },
]


def main() -> None:
    # 1. 读现有 Q 矩阵
    with open(Q_MATRIX_PATH, encoding="utf-8") as f:
        data = json.load(f)

    # 2. 检查 ID 不重复
    existing_ids = {p["problem_id"] for p in data["problems"]}
    for q in PB_C_QUESTIONS:
        if q["problem_id"] in existing_ids:
            print(f"⚠️ {q['problem_id']} 已存在, 跳过")
        else:
            data["problems"].append(q)
            print(f"✅ 添加 {q['problem_id']} ({q['topic']} L{q['bloom_layer_observed'][1]} {q['c_dimension_type']})")

    # 3. 更新 metadata
    if "metadata" not in data:
        data["metadata"] = {}
    data["metadata"]["version"] = "v0.54.1"
    data["metadata"]["phase"] = 5
    data["metadata"]["c_dominant_questions_count"] = sum(
        1 for p in data["problems"] if p["problem_id"].startswith("PB-C")
    )
    data["metadata"]["total_questions"] = len(data["problems"])
    data["metadata"]["last_updated"] = "2026-07-23"

    # 4. 写回
    with open(Q_MATRIX_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print()
    print(f"✅ Q 矩阵更新完成: {len(data['problems'])} 题 (原 26 + 新 {len(PB_C_QUESTIONS)})")
    print(f"   - PB-Q (K/P/S 主导): {sum(1 for p in data['problems'] if p['problem_id'].startswith('PB-Q'))}")
    print(f"   - PB-C (C 主导): {sum(1 for p in data['problems'] if p['problem_id'].startswith('PB-C'))}")


if __name__ == "__main__":
    main()
