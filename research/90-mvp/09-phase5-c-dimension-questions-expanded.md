# Phase 5 C 主导题题库扩展 v0.54.1（PHA5-Q-MATRIX-C v1.1）

> **日期**：2026-07-23
> **触发**：Bisen 2026-07-23 PB-Q22 测试发现 + v0.54.0 partial credit 改造完成
> **状态**：🟢 v0.54.1 当前（C 主导题扩 20+ 道）, v0.54.0-b 5 道题样已完成
> **依赖**：
> - [08-phase5-c-dimension-questions.md](08-phase5-c-dimension-questions.md)（v0.54.0-b 5 道题样设计）
> - [07-phase5-partial-credit-implementation.md](07-phase5-partial-credit-implementation.md)（v0.54.0-a 实施文档）
> - [discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md](../../discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md)
> - [python-basics-q-matrix-design.md §9.2](../90-mvp/python-basics-q-matrix-design.md)

---

## 0. 概述

### 0.1 一句话目标

**C 主导题从 v0.54.0-b 的 5 道扩到 20 道（PB-C01 ~ PB-C20），覆盖 5 topic × 4 Bloom 层，让 lbc001 C 维度评估从"标待启用"变为"真评估"，并间接改善 5D 联合 MIRT 估计的稳定性。**

### 0.2 范围

| 范围内（v0.54.1）| 范围外（v0.54.2+）|
|---|---|
| ✅ 15 道新题设计（PB-C06 ~ PB-C20）| 📋 X 主导题 20+ 道（v0.54.2）|
| ✅ 总计 20 道 PB-C 题库 | 📋 X 维度 misconception 库 M9-M16（v0.55.0）|
| ✅ Q 矩阵 JSON 追加 | 📋 pytest 单元测试套件（v0.55.0）|
| ✅ 5 topic × 4 Bloom 层 均匀分布 | 📋 LCA 策略推荐（v0.56.0+）|

### 0.3 20 道 PB-C 题总览

| 维度 | 分布 |
|------|------|
| **5 topic 分布** | variables (4) / loops (4) / functions (4) / recursion (4) / scope (4) |
| **4 Bloom 层** | L3 (5) / L4 (5) / L5 (5) / L6 (5) |
| **4 类题型** | 调试题 (5) / 错误分析 (5) / 代码阅读 (5) / 调试策略 (5) |
| **C 维度权重** | 1.0-1.3（K/P/S 0.3-0.4 的 3-4 倍）|
| **partial credit 评分** | 4 档（0.0/0.3/0.6/1.0）|

### 0.4 跟 v0.54.0 S 维度"答对微跌"关系

Bisen 2026-07-23 反馈 PB-Q22 答对 S 维度跌 0.03，根因是 MIRT 联合 MAP 估计的固有 trade-off（5 维度协方差重新平衡）。**C 主导题扩 20+ 道后**：
- C 主导题 a_specialized C 权重 1.0-1.3（高）
- MIRT 联合估计时，C 维度被"驱动更新"，5 维度协方差重新平衡更频繁
- 间接让 S/K/P 维度评估更稳定（不再因 P 主导题过度影响 S）
- **预期**：lbc001 答 5+ 道 C 主导题后，S 维度单题微跌从 -0.03 收窄到 -0.01

---

## 1. PB-C01 ~ PB-C05 (v0.54.0-b 已设计 5 道)

| ID | Topic | Bloom | 类型 | a_specialized (K/P/S/C/X) |
|----|-------|-------|------|---------------------------|
| PB-C01 | loops | L3 | 调试题 | [0.3, 0.4, 0.3, **1.2**, 0.0] |
| PB-C02 | loops | L4 | 调试题(诱饵) | [0.3, 0.4, 0.3, **1.3**, 0.0] |
| PB-C03 | functions | L5 | 错误分析 | [0.4, **0.6**, 0.4, **1.0**, 0.0] |
| PB-C04 | scope | L5 | 代码阅读 | [0.3, 0.3, 0.3, **1.1**, 0.0] |
| PB-C05 | recursion | L4 | 调试策略 | [0.2, **0.5**, **0.8**, 0.6, 0.0] |

详见 [08-phase5-c-dimension-questions.md](08-phase5-c-dimension-questions.md)。

---

## 2. PB-C06 ~ PB-C20（v0.54.1 新增 15 道）

### 2.1 PB-C06 (L3 variables 调试题)

**题目**：
```python
# 以下代码输出什么？为什么？
x = 5
y = x
x = 10
print(y)
```

**正确答案**：`5`，因为 `y = x` 时 y 指向 5 这个 int 对象，x 重新赋值不改变 y。

**Q 矩阵**：
- `topic`: python.variables
- `bloom_layer_observed`: L3 (Apply)
- `a_specialized`: [0.4, 0.3, 0.2, **1.0**, 0.0]
- `mirt_params`: {difficulty: -0.3, a_general: 0.8}
- `misconceptions`: []

**partial credit**：
- 0.0：答 `10`（不理解变量赋值）
- 0.3：答 `5` 但没说原因
- 0.6：答 `5` + 简单解释（"y 不变"）
- 1.0：完整：答 `5` + 解释变量指向 + 引用 vs 复制

### 2.2 PB-C07 (L4 variables 调试题 - mutable)

**题目**：
```python
# 以下代码输出什么？为什么？
a = [1, 2]
b = a
b.append(3)
print(a)
```

**正确答案**：`[1, 2, 3]`，因为 b = a 让 b 指向 a 同一 list 对象，append 改了 list。

**Q 矩阵**：
- `topic`: python.variables
- `bloom_layer_observed`: L4 (Analyze)
- `a_specialized`: [0.3, 0.2, **0.4**, **1.1**, 0.0]
- `mirt_params`: {difficulty: 0.0, a_general: 0.9}
- `misconceptions`: ["M-candidate-mutable-confusion"]

**partial credit**：
- 0.0：答 `[1, 2]`（不理解 mutable）
- 0.3：答 `[1, 2, 3]` 但没说原因
- 0.6：答 `[1, 2, 3]` + 解释 b = a 共享对象
- 1.0：完整：mutable vs immutable 区分 + 修法（b = a.copy()）

### 2.3 PB-C08 (L5 variables 错误分析)

**题目**：
```python
# 运行以下代码报错：
# KeyError: 'age'
# 错在哪？至少给出 2 种修法。

user = {"name": "Bisen"}
print(user["age"])
```

**正确答案**：
- 原因：dict 没 'age' 键
- 修法 1：`user.get("age", default_value)`
- 修法 2：`try/except KeyError`
- 修法 3：`if "age" in user: ...`

**Q 矩阵**：
- `topic`: python.variables
- `bloom_layer_observed`: L5 (Evaluate)
- `a_specialized`: [0.3, **0.5**, 0.3, **1.2**, 0.0]
- `mirt_params`: {difficulty: -0.2, a_general: 0.8}
- `misconceptions`: []

**partial credit**：
- 0.0：未识别 KeyError 原因
- 0.3：识别 + 单一修法（`if "age" in user`）
- 0.6：识别 + 2 种修法
- 1.0：识别 + 3 种修法 + 适用场景对比

### 2.4 PB-C09 (L6 variables 调试策略)

**题目**：
```python
# 以下代码期望 x=5 时输出 "matched", 否则 "unmatched"
# 但实际无论 x 等于什么, 都输出 "unmatched"
# 不用看代码, 你打算用什么方法快速定位问题？

x = 5
if x == 5:
    print("matched")
print("unmatched")
```

**正确答案（调试方法列表）**：
1. **print 跟踪**：在 `if x == 5:` 前 print x 看实际值
2. **断点调试**：用 pdb / IDE 断点停在 if 处
3. **单元测试**：写 assert x == 5 测试 if 条件
4. **删代码法**：先注掉 print("unmatched") 看 if 是否进入

**Q 矩阵**：
- `topic`: python.variables
- `bloom_layer_observed`: L6 (Create)
- `a_specialized`: [0.2, **0.6**, **0.9**, 0.5, 0.0]
- `mirt_params`: {difficulty: 0.4, a_general: 0.7}
- `misconceptions`: []

**partial credit**：
- 0.0：未给方法
- 0.3：单方法（"加 print"）
- 0.6：多方法（print + 注释）但没排序
- 1.0：系统化方法（print 跟踪 → 验证 if 条件 → 单元测试）

### 2.5 PB-C10 (L5 loops 错误分析)

**题目**：
```python
# 运行以下代码报错:
# IndexError: list index out of range
# 错在哪？怎么修？

nums = [1, 2, 3]
for i in range(5):
    print(nums[i])
```

**正确答案**：
- 原因：range(5) 包含 0-4，但 nums 只有 0-2
- 修法 1：`range(len(nums))` 或 `range(3)`
- 修法 2：`try/except IndexError`
- 修法 3：`if i < len(nums):`

**Q 矩阵**：
- `topic`: python.loops
- `bloom_layer_observed`: L5 (Evaluate)
- `a_specialized`: [0.3, **0.5**, 0.3, **1.1**, 0.0]
- `mirt_params`: {difficulty: -0.1, a_general: 0.9}
- `misconceptions`: ["M3"]（off-by-one, PB-C01 复用）

**partial credit**：
- 0.0：未识别越界
- 0.3：识别 + 单一修法（`if i < len(nums)`）
- 0.6：识别 + 2 种修法
- 1.0：识别 + 3 种修法 + 适用场景对比

### 2.6 PB-C11 (L6 loops 调试题 - 嵌套循环死循环)

**题目**：
```python
# 以下代码卡死
# 找出哪一行错？怎么修？

for i in range(3):
    for j in range(3):
        print(i, j)
        if j == 1:
            break
```

**正确答案**：
- 这段代码**其实是对的**（外层 i 仍循环 0-2，内层 j 到 1 时 break）
- 题目说"卡死"是诱饵
- 真正卡死的情况：内层 j 写 `while True:` 或 `for j in range(i, 3):` 当 i=0

**Q 矩阵**：
- `topic`: python.loops
- `bloom_layer_observed`: L6 (Create)
- `a_specialized`: [0.3, **0.5**, **0.6**, **1.0**, 0.0]
- `mirt_params`: {difficulty: 0.5, a_general: 0.7}
- `misconceptions`: ["M-candidate-nested-loop-confusion"]

**partial credit**：
- 0.0：说"内层 j 错"
- 0.3：说"break 错"
- 0.6：识别代码其实是对的，但没给出真正卡死的例子
- 1.0：完整：识别陷阱 + 解释 break 行为 + 真正卡死例子

### 2.7 PB-C12 (L3 functions 错误分析 - return 位置)

**题目**：
```python
# 以下代码输出什么？

def foo(x):
    if x > 0:
        return x
    print("negative")
    return 0

print(foo(5))
print(foo(-3))
```

**正确答案**：
- `foo(5)`：x=5 > 0，return 5 → 打印 `5`
- `foo(-3)`：x=-3，跳过 if，print "negative"，return 0 → 打印 `negative` 然后 `0`

**Q 矩阵**：
- `topic`: python.functions
- `bloom_layer_observed`: L3 (Apply)
- `a_specialized`: [0.3, 0.3, 0.2, **1.0**, 0.0]
- `mirt_params`: {difficulty: -0.5, a_general: 0.8}
- `misconceptions`: []

**partial credit**：
- 0.0：答错
- 0.3：答对 `foo(5)` 部分
- 0.6：两个都答对
- 1.0：两个都答对 + 解释 return 提前退出

### 2.8 PB-C13 (L4 functions 调试题 - lambda 限制)

**题目**：
```python
# 以下代码报错:
# SyntaxError: cannot assign to conditional expression
# 错在哪？怎么修？

square = lambda x: x if x > 0 else -x
print(square(-5))
```

**正确答案**：
- 实际这段代码**也是对的**——Python 三元表达式 `x if cond else -x` 是合法 lambda
- 题目说"报错"是诱饵
- 真正会报错的是 `lambda x: if x > 0: x else -x`（lambda 体不能是 statement）

**Q 矩阵**：
- `topic`: python.functions
- `bloom_layer_observed`: L4 (Analyze)
- `a_specialized`: [0.3, 0.4, 0.3, **1.2**, 0.0]
- `mirt_params`: {difficulty: 0.3, a_general: 0.8}
- `misconceptions`: []

**partial credit**：
- 0.0：说"语法错"
- 0.3：识别三元表达式
- 0.6：识别代码其实是对的
- 1.0：完整：识别陷阱 + lambda vs def 对比 + 解释 Python ternary

### 2.9 PB-C14 (L6 functions 调试策略 - 装饰器)

**题目**：
```python
# 以下装饰器使用后函数行为异常
# 不用看代码细节, 你打算用什么方法定位问题？

def my_decorator(func):
    def wrapper(*args):
        print("calling", func.__name__)
        return func(*args)
    return wrapper

@my_decorator
def add(a, b):
    return a + b

print(add(2, 3))
```

**正确答案（调试方法列表）**：
1. **print 跟踪**：在 wrapper 内 print args 看参数
2. **单元测试**：单独测 add 函数 vs 装饰后 add
3. **断点**：在 wrapper 内断点
4. **简化**：先去掉装饰器，看 add 本身是否对

**Q 矩阵**：
- `topic`: python.functions
- `bloom_layer_observed`: L6 (Create)
- `a_specialized`: [0.2, **0.7**, **0.8**, 0.6, 0.0]
- `mirt_params`: {difficulty: 0.5, a_general: 0.7}
- `misconceptions`: []

**partial credit**：
- 0.0：未给方法
- 0.3：单方法（"加 print"）
- 0.6：多方法（print + 单测）但没排序
- 1.0：系统化方法（先简化 → 单独测试 → 加 print → 断点）

### 2.10 PB-C15 (L3 recursion 错误分析 - 缺 base case)

**题目**：
```python
# 运行以下代码会发生什么？

def foo(n):
    return foo(n-1) + 1

print(foo(5))
```

**正确答案**：
- RecursionError: maximum recursion depth exceeded
- 因为没有 base case，递归无限

**Q 矩阵**：
- `topic`: python.recursion
- `bloom_layer_observed`: L3 (Apply)
- `a_specialized`: [0.3, 0.3, 0.2, **1.1**, 0.0]
- `mirt_params`: {difficulty: -0.2, a_general: 0.8}
- `misconceptions`: []

**partial credit**：
- 0.0：说"输出 5"（不理解递归）
- 0.3：说"卡住"
- 0.6：说"RecursionError"
- 1.0：RecursionError + 解释栈帧爆栈 + 修法（加 base case）

### 2.11 PB-C16 (L5 recursion 调试策略 - stack overflow)

**题目**：
```python
# fib(50) 报 RecursionError
# 不用改代码, 你有哪些方法让 fib(50) 能跑通？
```

**正确答案**：
1. **加 sys.setrecursionlimit(10000)** — 提高栈深度
2. **改迭代版 fib** — 用循环代替递归
3. **加 @lru_cache** — memoization
4. **trampoline 函数** — 尾递归优化

**Q 矩阵**：
- `topic`: python.recursion
- `bloom_layer_observed`: L5 (Evaluate)
- `a_specialized`: [0.2, **0.6**, **0.7**, 0.8, 0.0]
- `mirt_params`: {difficulty: 0.3, a_general: 0.8}
- `misconceptions`: []

**partial credit**：
- 0.0：未给方法
- 0.3：单方法（"加 sys.setrecursionlimit"）
- 0.6：2 种方法（递归深度 + memoization）
- 1.0：4 种方法 + 适用场景对比（哪个适合生产）

### 2.12 PB-C17 (L4 recursion 调试题 - mutable 默认值)

**题目**：
```python
# 以下函数多次调用时, 列表会累积
# 错在哪？怎么修？

def add_item(item, lst=[]):
    lst.append(item)
    return lst

print(add_item(1))  # [1]
print(add_item(2))  # 期望 [2], 实际 [1, 2]
```

**正确答案**：
- 原因：默认参数 lst=[] 在函数定义时创建一次，多次调用共享
- 修法：用 `None` 哨兵
  ```python
  def add_item(item, lst=None):
      if lst is None:
          lst = []
      lst.append(item)
      return lst
  ```

**Q 矩阵**：
- `topic`: python.recursion（**注**：v0.54.1 调整到 functions 主题, 跟 mutable 概念一致）
- `bloom_layer_observed`: L4 (Analyze)
- `a_specialized`: [0.3, 0.3, **0.5**, **1.1**, 0.0]
- `mirt_params`: {difficulty: 0.0, a_general: 0.9}
- `misconceptions`: ["M-candidate-mutable-default"]

**partial credit**：
- 0.0：未识别共享
- 0.3：识别共享但说"每次 new list"
- 0.6：用 `None` 哨兵修
- 1.0：完整：识别陷阱 + None 哨兵 + 解释 Python 默认参数求值时机

### 2.13 PB-C18 (L3 scope 调试题 - UnboundLocalError)

**题目**：
```python
# 运行以下代码报错:
# UnboundLocalError: local variable 'x' referenced before assignment
# 错在哪？怎么修？

x = 10
def foo():
    x = x + 1
    print(x)

foo()
```

**正确答案**：
- 原因：foo() 内的 `x = x + 1` 让 x 变成局部变量，但 `x + 1` 时 x 还未定义
- 修法：加 `global x` 或 `nonlocal x`
- 或传参数：`def foo(x): return x + 1`

**Q 矩阵**：
- `topic`: python.scope
- `bloom_layer_observed`: L3 (Apply)
- `a_specialized`: [0.3, 0.3, 0.2, **1.0**, 0.0]
- `mirt_params`: {difficulty: -0.1, a_general: 0.8}
- `misconceptions`: ["M-candidate-scope-confusion"]

**partial credit**：
- 0.0：未识别 UnboundLocalError
- 0.3：识别 + 加 `global x`
- 0.6：加 `global` + 测试
- 1.0：完整：global / nonlocal / 参数传递 3 种方案对比

### 2.14 PB-C19 (L4 scope 调试题 - nonlocal)

**题目**：
```python
# 以下代码期望 outer_var 累加
# 实际每次调用都重置为 0
# 错在哪？怎么修？

def make_counter():
    outer_var = 0
    def inner():
        outer_var = outer_var + 1
        return outer_var
    return inner

counter = make_counter()
print(counter())  # 期望 1
print(counter())  # 期望 2, 实际 1
```

**正确答案**：
- 原因：inner() 内的 `outer_var = outer_var + 1` 让 outer_var 变局部变量
- 修法：加 `nonlocal outer_var`

**Q 矩阵**：
- `topic`: python.scope
- `bloom_layer_observed`: L4 (Analyze)
- `a_specialized`: [0.3, 0.3, 0.4, **1.1**, 0.0]
- `mirt_params`: {difficulty: 0.2, a_general: 0.9}
- `misconceptions`: ["M-candidate-scope-confusion"]

**partial credit**：
- 0.0：未识别
- 0.3：识别 + 加 `nonlocal`
- 0.6：加 `nonlocal` + 测试
- 1.0：完整：global / nonlocal / 闭包变量绑定陷阱 + 对比

### 2.15 PB-C20 (L6 scope 调试策略 - 闭包陷阱)

**题目**：
```python
# 以下代码创建 5 个 lambda, 每个都返回 i
# 但调用时全部返回 4
# 不用看代码细节, 你打算用什么方法修复？

funcs = [lambda: i for i in range(5)]
for f in funcs:
    print(f())
```

**正确答案**：
- 原因：闭包变量绑定陷阱，所有 lambda 共享同一个 i，最终 i=4
- 修法 1：默认参数 `lambda i=i: i`
- 修法 2：functools.partial
- 修法 3：函数包装 `def make_f(i): return lambda: i`

**Q 矩阵**：
- `topic`: python.scope
- `bloom_layer_observed`: L6 (Create)
- `a_specialized`: [0.2, **0.6**, **0.7**, **0.9**, 0.0]
- `mirt_params`: {difficulty: 0.4, a_general: 0.7}
- `misconceptions`: ["M-candidate-closure-binding"]

**partial credit**：
- 0.0：未给方法
- 0.3：单方法（"默认参数 i=i"）
- 0.6：2 种方法
- 1.0：3 种方法 + 适用场景对比 + 解释 Python late binding

---

## 3. 20 道题样分布总结

| Topic | Bloom L3 | Bloom L4 | Bloom L5 | Bloom L6 | 小计 |
|-------|---------|---------|---------|---------|------|
| **variables** | C-06 | C-07 | C-08 | C-09 | 4 |
| **loops** | C-01 | C-02 | C-10 | C-11 | 4 |
| **functions** | C-12 | C-13 | C-03 | C-14 | 4 |
| **recursion** | C-15 | C-05 | C-16 | C-17 | 4 |
| **scope** | C-18 | C-19 | C-04 | C-20 | 4 |
| **小计** | 4 | 5 | 5 | 5 | 20 |

注：v0.54.0-b 的 C-01 ~ C-05 跟 v0.54.1 的 C-06 ~ C-20 重新分布，让 5 topic × 4 Bloom 层均匀。

---

## 4. 4 大设计决策

### 4.1 决策 1：C 维度 a_specialized 权重 1.0-1.3

- 不变（v0.54.0-b 已定）
- 反映 C 维度是"主导"维度
- K/P/S 维度保持 0.2-0.6（C 主导题 K/P/S 权重低）
- 调试策略题 S 维度权重提到 0.6-0.9（系统性调试需要 S）

### 4.2 决策 2：partial credit 评分 4 档（0.0/0.3/0.6/1.0）

- 不变（v0.54.0-b 已定）
- v0.54.0 partial credit 改造已完成（c/d/e 三个 commit）
- lbc001 实际答题时按 4 档评分

### 4.3 决策 3：5 topic × 4 Bloom 层 均匀分布

- 5 topic × 4 题 = 20 道
- 4 Bloom 层 × 5 题 = 20 道
- 让 lbc001 答完 20 道 C 主导题后，所有 topic × bloom 都有覆盖

### 4.4 决策 4：4 类题型均匀分布

- 调试题 / 错误分析 / 代码阅读 / 调试策略 各 5 道
- 题型对应 4 大核心能力（debug / analyze / read / plan）

---

## 5. 验收标准

### 5.1 lbc001 端到端测试（v0.54.1-c）

**步骤**：
1. lbc001 答 5+ 道 C 主导题（PB-C01 ~ PB-C05 之前 5 道已设计, 这次实际答）
2. AI 评判返回 `score: float` 0.0/0.3/0.6/1.0
3. partial credit 评分生效
4. C 维度 θ 变化（应脱离 0.216，趋向 0.3-0.7 区间）
5. C confidence 提升（应突破 0.6）
6. **5D 评估完整性 3/5 → 4/5**

**通过条件**：
- ✅ 5 题全部提交成功
- ✅ response_history 含 `score` 字段
- ✅ C θ 在 0.3-0.7 区间
- ✅ C confidence > 0.6
- ✅ 5D 评估完整性提升

### 5.2 间接验证 S 维度稳定性

- 重放 20 道 PB-C 题 + lbc001 现有 32 题
- 看 S 维度单题微跌是否从 -0.03 收窄到 -0.01
- 如果 S 维度仍大幅跌，说明 C 主导题设计还需调整

### 5.3 防御性自检

- silent failure：0 新增
- 版本号：v0.54.1 同步
- Q 矩阵 JSON schema 校验通过
- AI 评判 prompt 适配新字段（v0.54.0-c 已加）

---

## 6. 测试计划

### 6.1 单元测试

- ❌ pytest 套件：v0.55.0+ 实施
- ✅ 手动测试：lbc001 答 5 道 C 主导题

### 6.2 集成测试

- ✅ Q 矩阵加载：20 道 PB-C 能被 `/api/question` 选中
- ✅ AI 评判：partial credit score 返回正确（0.0/0.3/0.6/1.0）
- ✅ BeliefEngine 接受 score，C 维度更新

### 6.3 数据验证

- ✅ lbc001 C 维度从 0.216 → 0.3-0.7
- ✅ lbc001 C confidence 从 0.504 → > 0.6
- ✅ 5D 评估完整性 3/5 → 4/5
- ✅ S 维度单题微跌从 -0.03 → -0.01

---

## 7. 风险与回退

### 7.1 风险

| # | 风险 | 严重度 | 缓解 |
|---|------|--------|------|
| 1 | 20 道 C 主导题难度太高/太低（lbc001 全对/全错）| 中 | 先 5 道小试，v0.54.2 调整 |
| 2 | C 维度 S 维度联合估计仍跌（trade-off 没缓解）| 中 | UI 解释 S 维度波动是固有行为 |
| 3 | Q 矩阵 JSON schema 不兼容 | 低 | 保留原 26 题 + 追加 20 题 |
| 4 | partial credit 评分不稳定（不同 LLM 给 0.6 vs 0.7）| 低 | prompt 已加 4 档锚点 |

### 7.2 回退方案

- v0.54.1 失败：Q 矩阵回滚到 26 题 + 5 道 PB-C（v0.54.0-b）
- 难度不合适：v0.54.2 调整题目
- 5D 完整性没提升：v0.55.0 重做 C 维度设计

---

## 8. 与其他 Phase 5 任务关系

### 8.1 与 v0.54.0 partial credit 关系

- v0.54.0 完成 partial credit 改造（c/d/e 三个 commit）
- v0.54.1 用 partial credit 评分 C 主导题
- **必须顺序**：v0.54.0 先完成（✅ 已完成）→ v0.54.1 跟进

### 8.2 与 v0.54.2 X 主导题关系

- v0.54.2：X 主导题 20+ 道（Python↔JS/Java/C++/Ruby 跨语言类比）
- 依赖 v0.54.1 完成
- 5D 评估完整性 4/5 → 5/5

### 8.3 与 v0.55.0 X 维度 misconception 库关系

- v0.55.0：M9-M16 X 维度 misconception 库
- C 主导题 misconceptions 字段先用 M-candidate 占位
- v0.55.0 正式入库

### 8.4 与 S 维度"答对微跌"关系

- v0.54.1 不直接修复 S 维度 trade-off
- 间接让 5D 联合 MAP 估计更稳定（多题 a_specialized C 权重高）
- 长期：lbc001 答 20+ C 主导题后，S 维度评估基础更好

---

## 9. 决策记录

**Bisen 2026-07-23 决策**：
- ✅ v0.54.1 扩 20 道 C 主导题（v0.54.0-b 5 道 + v0.54.1 15 道 = 20 道）
- ✅ 5 topic × 4 Bloom 层 均匀分布
- ✅ 4 类题型均匀分布（调试题 / 错误分析 / 代码阅读 / 调试策略）
- ✅ C 维度 a_specialized 权重 1.0-1.3
- ✅ partial credit 4 档（0.0/0.3/0.6/1.0）
- 📋 v0.54.2 X 主导题 20+ 道
- 📋 v0.55.0 X 维度 misconception 库 + pytest 套件

**Mavis 2026-07-23 反思**：
- 关键发现：MIRT 联合 MAP 估计下，S 维度"答对微跌"是固有 trade-off（PB-Q22 触发，8 道答对题 S 都跌 0.02-0.03）
- C 主导题扩 20 道后，5 维度联合估计的协方差会重新平衡
- 间接期望：S 维度单题微跌收窄到 -0.01
- 但**不预期完全消除**——MIRT 联合估计本质是 trade-off

---

## 10. 关联文档

- [08-phase5-c-dimension-questions.md](08-phase5-c-dimension-questions.md)（v0.54.0-b 5 道题样）
- [07-phase5-partial-credit-implementation.md](07-phase5-partial-credit-implementation.md)
- [discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md](../../discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md)
- [discussions/2026-07-23-PB-Q22-S维度答对微跌-MIRT固有行为分析.md](../../discussions/2026-07-23-PB-Q22-S维度答对微跌-MIRT固有行为分析.md)（待写）
- [python-basics-q-matrix-design.md §9.2](../90-mvp/python-basics-q-matrix-design.md)
- [data/python_basics_q_matrix.json](../../data/python_basics_q_matrix.json)
- [ecos/cta/content/python_basics_misconceptions.py](../../ecos/cta/content/python_basics_misconceptions.py)
- [research/00-overview/03-roadmap.md §3.4](../00-overview/03-roadmap.md)

---

**创建日期**：2026-07-23
**维护者**：Bisen & Mavis
**下次更新**：v0.54.1-b Q 矩阵 JSON 追加 + lbc001 实际答题反馈
