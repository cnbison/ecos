# Phase 5 C 主导题题库设计（PHA5-Q-MATRIX-C v1.0）

> **日期**：2026-07-23
> **触发**：Bisen 2026-07-22 lbc001 27-29 题测试 + v0.54.0 Phase 5 启动
> **状态**：🟢 v0.54.0-b 当前（C 主导题 5 道题样）, v0.54.1 计划扩 20+ 题
> **依赖**：
> - [07-phase5-partial-credit-implementation.md](07-phase5-partial-credit-implementation.md)（v0.54.0-a 实施文档）
> - [discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md](../../discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md)（12.2 KB）— Phase 5 双目标
> - [python-basics-q-matrix-design.md §9.2](../90-mvp/python-basics-q-matrix-design.md)（v0.52.1 扩充 C/X 缺口）

---

## 0. 概述

### 0.1 一句话目标

**为 ECOS 5D 评估的 C 维度（Common mistakes / 错误分析 / 调试策略）设计专属题库，让 lbc001 C 维度 confidence 从 0.504 永久低位的状态变为可真实评估的维度。**

### 0.2 范围

| 范围内（v0.54.0-b）| 范围外（v0.54.1+）|
|---|---|
| ✅ 5 道 C 主导题题样（PB-C01 ~ PB-C05）| 📋 扩 20+ 题（v0.54.1）|
| ✅ Q 矩阵标注（a_specialized 5 维权重 + misconceptions）| 📋 X 主导题 20+ 题（v0.54.2）|
| ✅ partial credit 评分标准（debug 题天然适合）| 📋 X 维度 misconception 库 M9-M16（v0.55.0）|
| ✅ 5 类 C 主导题型定义（debug / error analysis / code reading / debug strategy）| 📋 LCA 策略推荐（v0.56.0+）|

### 0.3 当前题库现状

| 指标 | 当前 | 改造后（v0.54.0-b）|
|------|------|---------------------|
| 总题数 | 26 | 26 + 5 = 31 |
| C 主导题 | 0 | 5 |
| X 主导题 | 0 | 0（v0.54.2 扩）|
| 5D 评估完整性 | 3/5 真评估 | 4/5 真评估（K/P/S/C 真评估，X 仍待启用）|

### 0.4 lbc001 C 维度数据（v0.54.0 启动前）

- C θ: 0.216（初始值，未变）
- C SE: 0.983（高度不确定）
- C confidence: 0.504（理论值，无数据验证）
- C misconception_hits: []（空，从未触发）

**改造后预期**：lbc001 答 5+ 道 C 主导题后，C θ 应在 0.3-0.7 区间波动，SE 下降，confidence 提升到 0.6+。

---

## 1. 4 类 C 主导题型

### 1.1 类型 1: 调试题（Debug Bug）

**定义**：给一段**已知有 bug** 的代码，问学生"错在哪？怎么修？"

**特点**：
- 学生需**识别** bug 位置（不是写代码）
- 天然适合 partial credit（找到 1 个 bug ≠ 找到所有）
- C 维度权重最高（识别错误是核心能力）

**partial credit 评分**：
- 0.0：未识别任何 bug
- 0.3：识别了部分 bug 位置但没说清原因
- 0.6：识别了所有 bug 位置 + 部分原因
- 1.0：识别所有 bug + 完整原因 + 给出修复

### 1.2 类型 2: 错误分析（Error Analysis）

**定义**：给一段代码 + 错误信息（运行时 / 编译时），问学生"为什么？"

**特点**：
- 学生需**推理**错误原因
- 测试 debugging 思维链（错误信息 → 定位 → 推理）
- C + S 维度都触发（推理 = Strategy）

**partial credit 评分**：
- 0.0：无法解释
- 0.3：猜测（未基于错误信息）
- 0.6：基于错误信息给出部分原因
- 1.0：基于错误信息 + 代码逻辑完整推理

### 1.3 类型 3: 代码阅读（Code Reading）

**定义**：给一段代码，问学生"输出什么？做了什么？"

**特点**：
- 学生需**理解**代码（不是写）
- 测试 trace 能力（step-by-step 模拟）
- C + K 维度触发（理解 = Common + Knowledge）

**partial credit 评分**：
- 0.0：完全错误
- 0.3：部分理解（部分输出对）
- 0.6：理解主体但漏边界
- 1.0：完整理解所有细节

### 1.4 类型 4: 调试策略（Debug Strategy）

**定义**：给一个 bug 现象（不直接给代码），问学生"用什么方法定位？"

**特点**：
- 学生需**规划**调试方法（print / debugger / 拆函数 / 单元测试）
- 测试元认知能力
- C + S 维度都触发（策略 = Strategy）

**partial credit 评分**：
- 0.0：未给出方法
- 0.3：单一方法（print）但不系统
- 0.6：多方法但没排序
- 1.0：系统化方法（先 print 定位 → 拆函数隔离 → 单元测试验证）

---

## 2. 5 道 C 主导题题样设计

### 2.1 PB-C01 (L3, loops, 调试题, 类型 1)

**题目**：
```python
# 以下代码期望输出 1, 2, 3, 4, 5，但实际输出 1, 2, 3, 4
# 错在哪？怎么修？

for i in range(1, 5):
    print(i)
```

**正确答案**：
- Bug 位置：`range(1, 5)` → `range(1, 6)`
- 原因：`range(1, 5)` 不包含 5
- 修复：`range(1, 6)` 或 `range(1, n+1)`

**Q 矩阵标注**：
- `topic`: python.loops
- `bloom_layer_observed`: L3 (Apply)
- `a_specialized`: [0.3, 0.4, 0.3, **1.2**, 0.0]  ← **C 维度高权重**
- `mirt_params`: {difficulty: -0.5, a_general: 0.8}
- `misconceptions`: ["M3"]（v0.52.0 fix 后已能检测，range 不包含右端点）

**partial credit 评分**：
- 0.0：说"代码对"或没回答
- 0.3：识别 `range(1, 5)` 但说"5 应该在"
- 0.6：识别 `range(1, 5)` 错 + 修复为 `range(1, 6)` 但没说原因
- 1.0：完整：位置 + 原因 + 修复

### 2.2 PB-C02 (L4, loops, 调试题, 类型 1)

**题目**：
```python
# 以下代码期望输出 1, 2, 3，但实际什么都没有输出
# 错在哪？怎么修？

for i in range(1, 4):
    if i == 2:
        continue
    print(i)
```

**正确答案**：
- 这段代码**实际是对的**（输出 1, 3, skip 2）
- 但题目说"实际什么都没有输出"是诱饵
- 正确回答："代码实际是对的，输出 1 和 3，skip 2"

**Q 矩阵标注**：
- `topic`: python.loops
- `bloom_layer_observed`: L4 (Analyze)
- `a_specialized`: [0.3, 0.4, 0.3, **1.3**, 0.0]  ← **C 维度更高（识别陷阱题）**
- `mirt_params`: {difficulty: 0.2, a_general: 0.8}
- `misconceptions`: []

**partial credit 评分**：
- 0.0：说"代码错在某行"
- 0.3：识别 `continue` 但说"跳过了所有"
- 0.6：识别"输出 1, 3, skip 2"但没说"代码是对的"
- 1.0：完整：识别陷阱 + 正确 trace

### 2.3 PB-C03 (L5, functions, 错误分析, 类型 2)

**题目**：
```python
# 运行以下代码会报错：
# TypeError: unsupported operand type(s) for +: 'int' and 'str'
# 错在哪？怎么修？

def add(a, b):
    return a + b

x = add(1, "2")
print(x)
```

**正确答案**：
- 错误原因：`add(1, "2")` 中 1 是 int，"2" 是 str，不能直接相加
- 修复：转类型 `add(1, int("2"))` 或 `add(str(1), "2")`（按需）

**Q 矩阵标注**：
- `topic`: python.functions
- `bloom_layer_observed`: L5 (Evaluate)
- `a_specialized`: [0.4, **0.6**, 0.4, **1.0**, 0.0]  ← **C + P 维度高（错误分析）**
- `mirt_params`: {difficulty: 0.0, a_general: 0.9}
- `misconceptions`: []

**partial credit 评分**：
- 0.0：未识别类型问题
- 0.3：识别 "int 和 str 不能加" 但没说怎么修
- 0.6：识别 + 给出 `int()` 转换
- 1.0：完整：错误原因 + 多种修复方案 + 适用场景

### 2.4 PB-C04 (L5, scope, 代码阅读 + 错误分析, 类型 3 + 2)

**题目**：
```python
# 以下代码输出什么？为什么？

x = 10

def foo():
    x = 20
    print(x)

foo()
print(x)
```

**正确答案**：
- 输出：`20` 然后 `10`
- 原因：`foo()` 内的 `x = 20` 是局部变量，不影响外部 `x = 10`

**Q 矩阵标注**：
- `topic`: python.scope
- `bloom_layer_observed`: L5 (Evaluate)
- `a_specialized`: [0.3, 0.3, 0.3, **1.1**, 0.0]  ← **C 维度高（理解作用域边界）**
- `mirt_params`: {difficulty: -0.3, a_general: 0.9}
- `misconceptions`: ["M-candidate-scope-confusion"]（lbc001 答过类似 scope 题）

**partial credit 评分**：
- 0.0：说"输出 20"（部分对）
- 0.3：说"输出 20, 20"（不理解 scope）
- 0.6：说"输出 20, 10" 但没说原因
- 1.0：完整：输出 + 原因（局部 vs 全局）

### 2.5 PB-C05 (L4, recursion, 调试策略, 类型 4)

**题目**：
```python
# 运行 fib(5) 卡死很长时间
# 不用看代码，你打算用什么方法快速定位问题？

def fib(n):
    if n <= 1:
        return n
    return fib(n-1) + fib(n-2)
```

**正确答案（策略列表）**：
1. **加 print 跟踪**：在函数入口 print n 看调用次数
2. **画递归树**：手算 fib(5) 的递归树，识别重复计算
3. **测小输入**：先 fib(3) 看是否也慢
4. **用 lru_cache / memoization**：直接验证是重复计算问题

**Q 矩阵标注**：
- `topic`: python.recursion
- `bloom_layer_observed`: L4 (Analyze)
- `a_specialized`: [0.2, **0.5**, **0.8**, 0.6, 0.0]  ← **S + C 维度高（策略 + 调试）**
- `mirt_params`: {difficulty: 0.3, a_general: 0.7}
- `misconceptions`: ["M-candidate-recursion-no-memo"]

**partial credit 评分**：
- 0.0：未给方法
- 0.3：单一方法（"加 print"）但不系统
- 0.6：多方法（print + 测小输入）但没排序
- 1.0：系统化方法（先 print 跟踪 → 识别重复 → memoization 验证）

---

## 3. Q 矩阵 JSON 格式（追加到 python_basics_q_matrix.json）

### 3.1 顶层 metadata 更新

```json
{
  "metadata": {
    "version": "v0.54.0",
    "phase": 5,
    "c_dominant_questions": 5,
    "added_questions": ["PB-C01", "PB-C02", "PB-C03", "PB-C04", "PB-C05"]
  },
  "problems": [
    // ... 原有 26 题
    { /* PB-C01 */ },
    { /* PB-C02 */ },
    { /* PB-C03 */ },
    { /* PB-C04 */ },
    { /* PB-C05 */ }
  ]
}
```

### 3.2 单题 schema（与现有对齐）

```json
{
  "problem_id": "PB-C01",
  "topic": "python.loops",
  "skill_name": "Debug: range bounds",
  "problem_text": "以下代码期望输出 1, 2, 3, 4, 5，但实际输出 1, 2, 3, 4\n错在哪？怎么修？\n\nfor i in range(1, 5):\n    print(i)",
  "correct_answer": "Bug 在 range(1, 5) 不包含 5，应改为 range(1, 6)",
  "bloom_goal_id": "debug-range-bounds",
  "bloom_layer_observed": 3,
  "a_specialized": [0.3, 0.4, 0.3, 1.2, 0.0],
  "mirt_params": {
    "a_general": 0.8,
    "difficulty": -0.5
  },
  "misconceptions": ["M3"],
  "intervention_types": ["explanation", "scaffolding"],
  "partial_credit_rubric": {
    "0.0": "未识别或答错",
    "0.3": "识别 range(1,5) 但说 '5 应该在'",
    "0.6": "识别 + 修复为 range(1,6) 但没说原因",
    "1.0": "完整: 位置 + 原因 + 修复"
  }
}
```

---

## 4. 4 大设计决策

### 4.1 决策 1: C 维度 a_specialized 权重 1.0-1.3

- 比 K/P/S 维度（0.3-0.4）高 3-4 倍
- 反映 C 维度是"主导"维度
- MIRT 公式自动加权

### 4.2 决策 2: partial credit 评分 4 档（0.0/0.3/0.6/1.0）

- 与 v0.54.0 partial credit 模型对齐（score >= 0.6 算 correct）
- 4 档足够表达 debug 题的 partial 程度
- LLM 评判 prompt 强制 4 档输出

### 4.3 决策 3: 题库数量 5 道先小试，v0.54.1 扩 20+

- v0.54.0-b 5 道先验证 partial credit 改造
- v0.54.1 扩到 20+ 道（topic 分布 5:5:4:3:3）
- X 主导题 v0.54.2 单独做（避免一次 commit 太大）

### 4.4 决策 4: misconceptions 字段保留

- 复用现有 M1-M8 Python 库
- 新增 C 主导题专属 M-candidate 候选（如 M-candidate-scope-confusion）
- v0.55.0 正式入 X misconception 库

---

## 5. 验收标准

### 5.1 lbc001 端到端测试（v0.54.0-f）

**步骤**：
1. lbc001 答 5 道 C 主导题（PB-C01 ~ PB-C05）
2. AI 评判返回 `score: float`
3. partial credit 评分生效（如 PB-C01 答对 60% → score=0.6）
4. C 维度 θ 变化（应脱离 0.216，趋向 0.3-0.7 区间）
5. C confidence 提升（应突破 0.6）

**通过条件**：
- ✅ 5 题全部提交成功
- ✅ response_history 含 `score` 字段
- ✅ C θ 在 0.3-0.7 区间
- ✅ C confidence > 0.6

### 5.2 5D 完整性提升

- 改造前：5D 评估 3/5 真评估（K/P/S）
- 改造后：5D 评估 **4/5 真评估**（K/P/S/C）
- 待 v0.54.2 X 主导题：5D 评估 5/5

### 5.3 防御性自检

- silent failure：0 新增
- 版本号：v0.54.0 同步
- Q 矩阵 JSON schema 校验通过
- AI 评判 prompt 适配新字段

---

## 6. 测试计划

### 6.1 单元测试

- ❌ pytest 套件：v0.55.0+ 实施
- ✅ 手动测试：lbc001 答 5 道 C 主导题

### 6.2 集成测试

- ✅ Q 矩阵加载：PB-C01 ~ PB-C05 能被 `/api/question` 选中
- ✅ AI 评判：partial credit score 返回正确
- ✅ BeliefEngine 接受 score，C 维度更新

### 6.3 数据验证

- ✅ lbc001 C 维度从 0.216 → 0.3-0.7
- ✅ lbc001 C confidence 从 0.504 → > 0.6
- ✅ 5D 评估完整性 3/5 → 4/5

---

## 7. 风险与回退

### 7.1 风险

| # | 风险 | 严重度 | 缓解 |
|---|------|--------|------|
| 1 | LLM 评判 partial credit 不稳定（不同 LLM 给 0.6 vs 0.7）| 中 | 加 schema 验证 + 多次试验 |
| 2 | Q 矩阵 JSON schema 不兼容（PB-C01-C05 加载失败）| 中 | 保留原 26 题 + 追加新 5 题 |
| 3 | C 主导题难度太高/太低（lbc001 全对/全错）| 低 | 先 5 道小试，v0.54.1 调整 |
| 4 | 5 道题 topic 分布不均（loops 2 + 其他各 1）| 低 | v0.54.1 补齐 |

### 7.2 回退方案

- v0.54.0-b 失败：Q 矩阵回滚到 26 题，partial credit 留 v0.54.1
- 5 道题不要：只追加前 2 道试
- 难度不合适：v0.54.1 调整

---

## 8. 与 v0.54.0 其他任务关系

### 8.1 与 v0.54.0-c/d（partial credit 改造）关系

- v0.54.0-c/d：partial credit 模型改造（schemas + belief_engine + web/api）
- v0.54.0-b：C 主导题题库（用 partial credit 评分）
- **依赖**：v0.54.0-c/d 必须先完成（否则 PB-C 没法 partial credit 评分）

### 8.2 与 v0.54.1（C 主导题扩 20+）关系

- v0.54.0-b：5 道样题验证
- v0.54.1：扩 20+ 道
- **关键**：v0.54.0-b 跑通端到端后，v0.54.1 才能扩

### 8.3 与 v0.54.2（X 主导题）关系

- v0.54.2：X 主导题 20+ 道（Python↔JS/Java/C++/Ruby 跨语言类比）
- **依赖**：v0.54.0-b + v0.54.1 完成 C 主导题后

### 8.4 与 v0.55.0（X misconception 库）关系

- v0.55.0：M9-M16 X 维度 misconception 库
- C 主导题的 misconceptions 字段先用 M-candidate 占位
- v0.55.0 正式入 X misconception 库

---

## 9. 决策记录

**Bisen 2026-07-23 决策**：
- ✅ v0.54.0-b 设计 5 道 C 主导题样题
- ✅ partial credit 评分 4 档（0.0/0.3/0.6/1.0）
- ✅ C 维度 a_specialized 权重 1.0-1.3（K/P/S 的 3-4 倍）
- ✅ Q 矩阵追加，不替换（保留原 26 题兼容性）
- 📋 v0.54.1 扩 20+ 道（基于 5 道样题的反馈调整）
- 📋 v0.54.2 X 主导题 20+ 道
- 📋 v0.55.0 X 维度 misconception 库

**Mavis 2026-07-23 反思**：
- 关键发现：debug 题天然适合 partial credit（找到 1 个 bug ≠ 找到所有）
- 题库设计要平衡"难度"和"信息量"——5 道先小试，避免一次 commit 太大
- 复用现有 M1-M8 misconception 库，不引入新库（M-candidate 候选）
- C 主导题与 K/P/S 主导题互补，不替代（lbc001 仍需写代码题训练 K/P/S）

---

## 10. 关联文档

- [07-phase5-partial-credit-implementation.md](07-phase5-partial-credit-implementation.md)（v0.54.0-a 实施文档）
- [discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md](../../discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md)
- [python-basics-q-matrix-design.md §9.2](../90-mvp/python-basics-q-matrix-design.md)
- [data/python_basics_q_matrix.json](../../data/python_basics_q_matrix.json)（原 26 题）
- [ecos/cta/content/python_basics_misconceptions.py](../../ecos/cta/content/python_basics_misconceptions.py)（M1-M8 Python 库）
- [research/00-overview/03-roadmap.md §3.4](../00-overview/03-roadmap.md)
- [research/00-overview/07-project-comprehensive-audit-2026-07-22.md §11](../00-overview/07-project-comprehensive-audit-2026-07-22.md)

---

**创建日期**：2026-07-23
**维护者**：Bisen & Mavis
**下次更新**：v0.54.0-c/d 实施后 + lbc001 答 5 道 C 主导题反馈
