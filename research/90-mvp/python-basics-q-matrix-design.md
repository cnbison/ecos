# Python 基础领域 Q 矩阵设计与规划

> 文档位置：`research/90-mvp/python-basics-q-matrix-design.md`
> 对应数据：`data/python_basics_q_matrix.json`
> 对应代码：`ecos/bloom/subject_libraries/python_basics.py`、`ecos/cta/content/python_basics_misconceptions.py`、`web/api/qmatrix.py`
> 版本：v1.0（2026-07-21）
> 状态：Phase 4 Product Demo 已落地，覆盖 5 topic × 6 Bloom 层，共 26 题

---

## 1. 设计目标与定位

Python 基础 Q 矩阵是 ECOS Product Demo 阶段的**内容基础设施**。它的核心任务不是“出一份试卷”，而是为双 Agent（CTA + LCA）提供可计算的学习证据：

- 每道题必须同时服务于 **诊断**（MIRT 5D 能力估计）和 **教学**（Bloom 目标覆盖 + Misconception 检测）。
- 题目与知识点、认知层级、典型误解、干预类型之间形成**显式映射**，让 CTA 的 belief update 和 LCA 的 intervention 都有据可依。
- 题库规模控制在“能支撑 Demo 完整跑通”的最小可用集合：当前 26 题，覆盖 5 个核心 topic 的 L1–L6。

---

## 2. 领域拆分：5 个核心 topic

Q 矩阵将 Python 基础自学者最需要突破的 5 个认知模块作为 topic：

| topic ID | 中文名 | 学习重心 | 5D 主导维度 |
|---|---|---|---|
| `python.variables` | 变量与赋值 | 理解“变量是名字/标签，不是装值的盒子” | **K**（Knowledge） |
| `python.loops` | 循环 | 掌握 range 边界、循环不变式、死循环诊断 | **S**（Strategy） |
| `python.functions` | 函数 | 定义/调用/参数/返回值/高阶函数 | **P**（Procedure） |
| `python.recursion` | 递归 | base case、递归vs迭代、调用栈、优化 | **S**（Strategy） |
| `python.scope` | 作用域 | LEGB、global/nonlocal、闭包 | **P**（Procedure） |

**拆分逻辑**：

1. 这 5 个 topic 几乎覆盖了 Python 入门阶段所有“概念性卡点”，且每个 topic 都有明确的典型误解（见第 4 节）。
2. `variables` 与 `scope`、`loops` 与 `recursion` 之间存在天然依赖：不理解变量就无法理解作用域；不理解循环就难以理解递归的 base case。
3. 5D 主导维度的分配不是随意标注，而是基于认知类型：
   - **K 主导**（variables）：重在概念语义（引用、赋值、可变对象）。
   - **P 主导**（functions、scope）：重在程序结构和语法规则（def、return、global、闭包）。
   - **S 主导**（loops、recursion）：重在策略选择和问题分解（循环终止、递归化归）。

---

## 3. Bloom 6 层覆盖：从 Remember 到 Create

每个 topic 按 Bloom 修订版认知层级设计 6 个目标（L1–L6），形成一条从“记忆事实”到“创造性应用”的渐进路径。Q 矩阵的题目直接映射到这些目标：

```
L1 Remember    → 识别语法 / 预测简单代码输出
L2 Understand  → 解释语义 / 区分易混淆概念
L3 Apply       → 独立写代码解决标准问题
L4 Analyze     → 分析错误 / 解释执行机制
L5 Evaluate    → 比较方案 / 判断优劣
L6 Create      → 设计程序 / 组合多个知识点
```

### 3.1 当前覆盖矩阵

| topic | L1 | L2 | L3 | L4 | L5 | L6 |
|---|---|---|---|---|---|---|
| variables | PB-Q01 | PB-Q02 | PB-Q03 | PB-Q04 | PB-Q17 | PB-Q18 |
| loops | PB-Q05 | PB-Q06 | PB-Q07 | PB-Q08 | PB-Q19 | PB-Q20 |
| functions | PB-Q09 | PB-Q10 | PB-Q11 | — | PB-Q21 | PB-Q22 |
| recursion | PB-Q12 | PB-Q13 | PB-Q14 | — | PB-Q23 | PB-Q24 |
| scope | — | PB-Q15 | PB-Q16 | — | PB-Q25 | PB-Q26 |

**说明**：

- variables / loops 是“双塔”topic，L1–L6 全部有题，用于验证 5D + Bloom 6 层的完整可视化。
- functions / recursion / scope 在 L4 存在空缺：这是 Phase 4 Demo 的已知取舍，因为 Analyze 层在这三个 topic 上更依赖解释性任务，而 Demo 当前以代码输出/写代码题为主。
- scope 没有 L1，直接从 L2 开始：因为 L1 只是记忆 LEGB 层级，与变量 L1 高度重叠，且 self-learner 通常通过 L2 的具体错误案例反而更容易入门。

### 3.2 题目在 Bloom 层上的题型分布

| Bloom 层 | 典型题型 | 示例题 |
|---|---|---|
| L1 | 代码输出预测 | PB-Q01 `x=5; print(x)` |
| L2 | 概念解释 / 辨析 | PB-Q02 `x=x+1`、PB-Q13 递归 vs 循环 |
| L3 | 独立写代码 | PB-Q03 交换变量、PB-Q11 判断质数 |
| L4 | 错误诊断 / 机制分析 | PB-Q04 列表引用、PB-Q08 死循环修复 |
| L5 | 方案比较 / 效率分析 | PB-Q17 交换方案、PB-Q21 质数判断效率 |
| L6 | 综合设计 | PB-Q18 逆序数、PB-Q24 递归反转字符串 |

---

## 4. Misconception 标签：8 条典型认知障碍

每道题可以标注 0–N 个 misconception ID。这些不是“错误答案类型”，而是**学生头脑中需要被修正的认知结构**。Misconception 库独立维护于 `ecos/cta/content/python_basics_misconceptions.py`。

| ID | 名称 | 触发知识点 | 典型触发话语 | Q 矩阵中触发题目 |
|---|---|---|---|---|
| M1 | 变量 = 数学等式 | variables | “x=x+1 不是无解吗？” | —（已在 L2 由 M2 覆盖） |
| M2 | x=x+1 非法 | variables | “x 怎么可能等于 x 加 1？” | PB-Q02 |
| M3 | for 循环 off-by-one | loops | “range(5) 应该是 0–5 吧？” | PB-Q06 |
| M4 | 函数必有返回值 | functions | “没有 return 叫什么函数？” | PB-Q10 |
| M5 | 递归 = 循环 | recursion | “递归不就是循环吗？” | PB-Q13、PB-Q23 |
| M6 | 变量 = 存储值的盒子 | variables | “改 a 就是改 b？” | PB-Q04 |
| M7 | while 基准情形遗漏 | loops | “为什么程序卡住了？” | PB-Q08、PB-Q19 |
| M8 | 全局/局部作用域混淆 | scope | “函数里改不了外面的 x？” | PB-Q15、PB-Q25 |

**设计原则**：

1. **一题可触发多个 misconception**，但当前 Demo 中每道题最多关联 2 个，便于 LLM Critic 聚焦。
2. **L2/L5 是 misconception 高发层**：L2 涉及概念理解，L5 涉及方案比较，都容易暴露深层误解。
3. **M1 与 M2 的合并策略**：M1 是更泛化的“等式误解”，M2 是其在 Python 自增语句上的具体表现。Q 矩阵在 PB-Q02 只标 M2，避免 LLM Critic 输出重复标签。

---

## 5. MIRT 5D 参数设计

Q 矩阵中的每道题都带有一组 MIRT 参数，供 `BiFactorMIRT5D` 进行能力估计。

### 5.1 5D 状态空间

| 维度 | 含义 | 在 Python 学习中的体现 |
|---|---|---|
| K | Knowledge | 概念理解：变量引用、作用域、递归语义 |
| P | Procedure | 程序技能：函数定义、闭包语法、global/nonlocal |
| S | Strategy | 策略能力：循环终止、递归化归、算法选择 |
| C | Confidence | 认知置信度（含 misconception 折扣后的综合置信） |
| X | External Support | 外部支架依赖程度 |

### 5.2 `a_specialized`：topic-维度专家向量

每个 topic 有一个主导的 5D 载荷向量，同一 topic 下的所有题目共享该向量（当前 Demo 设计）：

```json
{
  "python.variables": [0.9, 0.2, 0.4, 0.1, 0.1],  // K 主导
  "python.loops":     [0.2, 0.3, 0.9, 0.1, 0.1],  // S 主导
  "python.functions": [0.3, 0.9, 0.2, 0.1, 0.1],  // P 主导
  "python.recursion": [0.2, 0.3, 0.9, 0.1, 0.1],  // S 主导
  "python.scope":     [0.3, 0.9, 0.2, 0.1, 0.1]   // P 主导
}
```

**设计理由**：

- K/P/S 三个维度有实际教学意义，C/X 当前作为辅助维度，载荷较低。
- 非主导维度不为 0：例如变量题也涉及一定策略（S=0.4），因为“理解引用”需要学生主动构建心智模型。
- 共享向量的简化：每道题不再单独微调 a_specialized，降低标注成本；未来题库扩大后可过渡到题目级精细标注。

### 5.3 `mirt_params`：经典 IRT 三参数

```json
{
  "difficulty": 0.5,      // b：题目难度，范围约 0.1–0.8
  "discrimination": 1.0,  // a：区分度，通常 1.0–1.2
  "guessing": 0.0         // c：猜测概率，L1 可设 0.05，L3+ 写代码题设 0
}
```

**难度设计规律**：

| Bloom 层 | difficulty 范围 | 原因 |
|---|---|---|
| L1 | 0.1–0.3 | 记忆/识别型，错误率低 |
| L2 | 0.3–0.5 | 概念理解，开始出现典型误解 |
| L3 | 0.4–0.5 | 独立写代码，需要综合运用 |
| L4 | 0.6 | 错误诊断，需要逆向推理 |
| L5 | 0.7 | 方案评估，需要比较和判断 |
| L6 | 0.8 | 综合设计，最高认知负荷 |

**区分度与猜测概率**：

- 选择题/输出预测题：`discrimination=1.2`，`guessing=0.05`（存在蒙对可能）。
- 写代码题/解释题：`discrimination=1.0`，`guessing=0.0`（需要真实能力，难以猜测）。

---

## 6. 题目形式与答案设计

Q 矩阵中的题目全部采用**开放式问答**（写代码或自然语言解释），而不是选择题。这是 Product Demo 的关键决策：

1. **更贴近真实自学场景**：自学者通常是在写代码、查错误、读文档，而不是做选择题。
2. **便于 LLM Critic 评估**：开放式答案能暴露学生的推理过程，使 misconception 检测和干预更有依据。
3. **与 intervention 类型联动**：
   - `PRACTICE`：学生答对了但可能需要巩固，推荐同类型练习。
   - `EXPLANATORY`：学生答错或触发 misconception，推荐解释性干预。

### 6.1 题型示例

**L1 Remember（代码输出预测）**

```text
以下代码的输出是什么？

x = 5
print(x)
```

**L3 Apply（独立写代码）**

```text
用 for 循环写代码计算 1+2+...+100 的和
```

**L5 Evaluate（方案比较）**

```text
以下两个函数都能判断质数，哪个效率更高？为什么？

def is_prime_a(n): ...
def is_prime_b(n): ...
```

**L6 Create（综合设计）**

```text
设计一个闭包函数 make_counter(start=0)，返回一个计数器函数，
每次调用返回并递增计数器的值。
```

---

## 7. 选题策略：Warm-up / Adaptive / Probe

Q 矩阵本身只定义“有什么题”，真正决定“下一道出什么题”的是 `web/api/qmatrix.py` 中的三层选题策略。

### 7.1 Warm-up 覆盖性选题（前 5 题）

- **目标**：快速探测 5D 各维度，避免能力估计偏斜。
- **策略**：按 topic 轮询，同一 topic 内优先选最低未答 Bloom 层。
- **保证**：5 题内覆盖 ≥3 个 topic，确保 K/P/S 三个主维度都有观测。

### 7.2 Adaptive 自适应选题（5 题后）

- **目标**：在最小题目数下最大化信息增益，同时推进教学目标。
- **评分函数**（4 维加权）：
  1. **维度 SE 匹配（0.4）**：优先出对当前 SE 最大维度有最大载荷的题。
  2. **Topic 弱度（0.3）**：如果某维度 θ 为负，优先出该维度的题。
  3. **Bloom Δ 匹配（0.2）**：匹配目标 Bloom 层。
  4. **随机性（0.1）**：避免每次都出同一道题。

### 7.3 Probe 探针选题（强制诊断）

- **目标**：当 CTA 对某维度估计不确定时，专门出一道能“压低 SE”的题。
- **策略**：忽略教学目标，直接选 `a_specialized[d_star]` 最大的题。
- **触发**：由前端或教师端显式调用 `force_probe=True`。

---

## 8. 设计原则总结

1. **教学先行，测量跟上**：每道题首先对应一个明确的 Bloom 学习目标，然后才标注 MIRT 参数。
2. **Misconception 显性化**：题目设计时就考虑“学生会怎么错”，并把错误模式编码到 misconception 标签。
3. **K/P/S 维度可解释**：5D 载荷不是黑箱，而是与知识点类型直接关联，便于生成学生报告。
4. **最小可用题库**：26 题足以支撑 Demo 的 5D 分化、Bloom 6 层可视化、misconception 检测三条主线。
5. **开放式题型**：避免选择题的猜测参数干扰，让 LLM Critic 和 LCA 获得更多诊断信息。

---

## 9. 当前状态与后续扩展

### 9.1 已验证

- M2 W6 实验证明：在差异化 `a_specialized` 设计下，学生模拟作答后 K/P/S 能够分化（如 K=0.549 / P=0.592 / S=0.778）。
- 4-gate Demo 已能跑通：TC 跨越、Bloom 达标、misconception 清零、置信度真实。
- 学生端 UI 已能通过 Q 矩阵实时展示 5D、Bloom 6 层、LearningDNA、Trajectory。

### 9.2 已知缺口

| 缺口 | 影响 | 计划 |
|---|---|---|
| functions / recursion / scope 缺少 L4 | Bloom 6 层可视化在这些 topic 上出现断层 | Phase 4 后续补充每 topic 至少 1 道 L4 Analyze 题 |
| L5/L6 题目偏少 | 高阶能力估计方差较大 | 每 topic 至少补充 1 道 L5 + 1 道 L6 |
| `a_specialized` topic 级共享 | 无法区分同一 topic 内不同题目的认知侧重点 | 题库扩大后过渡到题目级精细标注 |
| C/X 维度载荷低 | 置信度和支架依赖的测量不够敏感 | 随着 misconception 检测和 intervention 日志积累，逐步校准 |

### 9.3 下一步

1. 补充 functions-L4、recursion-L4、scope-L4 题目，补全 Bloom 覆盖矩阵。
2. 将 `a_specialized` 从 topic 级共享迁移到题目级标注。
3. 基于真实学生交互数据，校准 difficulty / discrimination / guessing。
4. 引入“阈值概念（Threshold Concepts）”标签，与 TC_python 跨越检测联动。

---

## 10. 参考链接

- [data/python_basics_q_matrix.json](../../data/python_basics_q_matrix.json)
- [ecos/bloom/subject_libraries/python_basics.py](../../ecos/bloom/subject_libraries/python_basics.py)
- [ecos/cta/content/python_basics_misconceptions.py](../../ecos/cta/content/python_basics_misconceptions.py)
- [web/api/qmatrix.py](../../web/api/qmatrix.py)
- [research/10-engineering/01-cta-belief-engine.md](../10-engineering/01-cta-belief-engine.md)
