# C / X 维度语义决策文档（PHA5-DEC-CX v1.0）

> **日期**：2026-07-23
> **触发**：Bisen 2026-07-23 21:28 "C和X维度的真实含义是什么？对5D的完整性是否很重要和必要？"
> **状态**：🟡 **PENDING Bisen 决策**（3 个方案待选）
> **重要性**：🔴 **P0 架构级决策** —— 影响 v0.54.1 / v0.54.2 / Phase 5 / 整体 5D 架构
> **关联**：
> - [07-project-comprehensive-audit-2026-07-22.md](07-project-comprehensive-audit-2026-07-22.md) §11.2 C/X 0 主导题弊端
> - [research/90-mvp/09-phase5-c-dimension-questions-expanded.md](../90-mvp/09-phase5-c-dimension-questions-expanded.md)（v0.54.1 C 主导题 20 道）
> - [discussions/2026-07-23-C主导题让C维度真实化发现+缺口分析.md](../../discussions/2026-07-23-C主导题让C维度真实化发现+缺口分析.md)（v0.54.1-c 端到端测试发现）
> - [discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md](../../discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md)

---

## 0. 触发事件

Bisen 2026-07-23 17:51 反馈 PB-Q22 答对但 S 维度跌 0.03，根因是 MIRT 联合 MAP 估计的固有 trade-off（已记录）。

Bisen 2026-07-23 21:13 决定推 v0.54.1 C 主导题扩 20 道（v0.54.0-b 5 道 + 新增 15 道 = 20 道 PB-C）。

Bisen 2026-07-23 21:17 端到端集成测试发现 lbc001 C 维度 θ 从 0.2145 跌到 -0.07（"真实化"）—— C 主导题让 ECOS C 维度从"占位 0.21（K/P/S 协方差推断）" → "真实 -0.07"。

Bisen 2026-07-23 21:28 追问 **"C 和 X 维度的真实含义是什么？对 5D 的完整性是否很重要和必要？"**

**Mavis 2026-07-23 调研发现**：C 和 X 维度在 ECOS 不同文档里**定义不一致**——这是**严重的文档漂移**，是 ECOS 5D 架构的根本性设计问题。

---

## 1. C / X 维度定义漂移（3 个位置不一致）

### 1.1 5D 维度的 3 个"权威定义"对比

| 维度 | `belief_state.py:30-37` 代码 | 02-architecture.md 战略层 | 07-审查报告 端到端流程 | **一致性** |
|------|----------------------------|------------------------|---------------------|-----------|
| **K** | Knowledge 知识掌握 | Knowledge 知识掌握 | Knowledge 知识掌握 | ✅ 一致 |
| **P** | Procedure 程序技能 | Procedure 程序技能 | Procedure 程序技能 | ✅ 一致 |
| **S** | Strategy 策略能力 | Strategy 策略能力 | Strategy 策略能力 | ✅ 一致 |
| **C** | **Confidence 认知置信度**（含 misconception 折扣）| **Common mistakes 调试题 / 错误分析** | **Common mistakes 调试题 / 错误分析** | ❌ **漂移** |
| **X** | **External Support 外部支架** | **外部支架** | **跨语言迁移** | ❌ **漂移** |

### 1.2 漂移根因分析

**C 维度漂移**：
- `belief_state.py` 设计时（v0.1.0）C 维度是"Confidence 认知置信度"——心理测量层概念
- 战略层 + 端到端流程文档（v0.52.0+）C 维度是"Common mistakes 调试能力"——**教学法层概念**
- **两个概念不同**：调试能力强的学生不一定置信度高，调试能力弱但自信过度的学生（illusory confidence）是伪置信

**X 维度漂移**：
- `belief_state.py` 设计时（v0.1.0）X 维度是"External Support 外部支架"——ZPD 理论自足性概念
- 战略层 + 审查报告（v0.52.1+）X 维度是"跨语言迁移"——**应用层概念**
- **两个概念不同**：自足性高的学生不一定跨域迁移强，依赖支持的学生可能通过支持快速迁移

### 1.3 漂移的实际影响

**问题 1：v0.54.1 C 主导题让 lbc001 C θ 跌到 -0.07 是评估什么的？**
- 如果 C = "Common mistakes 调试能力"：-0.07 表示 lbc001 调试能力中等偏下（5 题 partial credit 0.68 表现）
- 如果 C = "Confidence 认知置信度"：-0.07 表示 lbc001 置信度低，但 lbc001 5 题答对 4 题应该置信度不错
- **结论**：v0.54.1 C 主导题实际评估的是**调试能力**（Common mistakes），但**信念引擎 C 维度定义是 Confidence**——**评估与定义不匹配**

**问题 2：v0.54.2 X 主导题如果基于"跨域迁移"设计，trigger 后会发生什么？**
- 信念引擎 X 维度更新：`state.X.theta` + `state.X.se` + `state.X.confidence`
- 但 X 维度定义是"External Support 外部支架"——`theta` 应该是"自足性"评分
- 跨域迁移题 trigger 后，X.theta 涨 0.1（如果答对），但**自足性应该下降（用了更多支持）**
- **结论**：跨域迁移题实际**误更新 X 维度**——如果 X 真义是"自足性"，跨域迁移题答对应该让 X 维度**降**（学生不依赖外部支持了），但 MIRT 会让 X 维度**升**

**问题 3：5D 评估完整性的"4/5"实际意义模糊**
- v0.54.1 文档说"5D 评估完整性 3/5 → 4/5"
- 实际是"K/P/S/C 真评估，X 占位"
- 但 C 真评估的"调试能力"≠ 信念引擎定义"置信度"
- **结论**："4/5 真评估"是基于"教学法层"评估的，跟"信念引擎层"定义不一致

---

## 2. C 维度 2 种解读深度分析

### 2.1 解读 1: **Common mistakes 调试能力**（教学法层 / v0.54.1 设计文档）

**定义**：学生对常见错误的**识别、避免、修复**能力。

**教学法依据**：
- 调试能力是程序设计核心能力（ACM/IEEE CS 2017 课程体系）
- 调试分 4 个层次：定位 → 推理 → 修复 → 预防
- 调试能力强的学生能避免常见错误（off-by-one / 类型错误 / 作用域错误等）

**典型题型**：
- 调试题（Debug Bug）：给已知 bug 的代码，问错在哪
- 错误分析（Error Analysis）：给代码 + 错误信息，问原因
- 代码阅读（Code Reading）：给代码，问输出/做了什么
- 调试策略（Debug Strategy）：给 bug 现象，问定位方法

**v0.54.1 设计 20 道 PB-C**：完全基于这一定义（[research/90-mvp/09-phase5-c-dimension-questions-expanded.md](../90-mvp/09-phase5-c-dimension-questions-expanded.md)）

**评估方式**：
- a_specialized C 权重 1.0-1.3（K/P/S 0.3-0.4 的 3-4 倍）
- partial credit 评分 4 档（0.0/0.3/0.6/1.0）
- MIRT MAP 估计 C.theta + C.se

**lbc001 实际评估**：C θ=0.2145 → -0.07（5 题 partial credit 0.68 平均）

### 2.2 解读 2: **Confidence 认知置信度**（信念引擎 / `belief_state.py`）

**定义**：学生对自己答案的**置信度**（心理测量概念）。

**信念引擎实现**（`belief_state.py:262-273`）：
```python
class ConfidenceDimensionState(DimensionState):
    """C 维度扩展——含 misconception 折扣与 TC 状态.

    在标准 DimensionState 基础上加:
    - misconception_hits: 历史命中记录
    - tc_states: 每个 TC 的状态
    - illusory_confidence_flag: 伪置信标记
    - discount_factor: misconception 折扣（默认 1.0）
    """
```

**核心字段**：
- `theta`：置信度数值（MIRT 估计）
- `se`：估计标准误
- `confidence = 1/(1+se)`：估计可信度（不是学生置信度）
- `misconception_hits`：历史命中 misconception 记录
- `tc_states`：每个 TC 的状态
- `illusory_confidence_flag`：伪置信标记（学生自信但实际错）
- `discount_factor`：misconception 折扣（影响整体置信度）

**注意：`confidence` 字段在 v0.48.0 改造后是"估计可信度"（meta-confidence），不是"学生置信度"（student-confidence）**——这又是一个概念漂移！

**典型评估方式**：
- LLM Critic 感知层返回 `self_evaluation`（学生对自己答案的自信 0-1）
- 学生答错但 self_evaluation 高 → 触发 `illusory_confidence_flag`
- 学生答对且 self_evaluation 准确 → C.theta 涨

**lbc001 实际评估**：C θ=0.2145（占位值，无真实评估）

### 2.3 两种解读的差异

| 维度 | 解读 1: Common mistakes 调试能力 | 解读 2: Confidence 认知置信度 |
|------|--------------------------------|------------------------------|
| **核心问题** | "学生能调试错误吗？" | "学生对自己答案的置信度如何？" |
| **教学法依据** | ACM CS 课程体系 / 调试分 4 层 | 心理测量学 / 元认知 |
| **典型题型** | 调试题 / 错误分析 / 调试策略 | 反思题 / 自评题 |
| **评估信号** | 答对调试题 / 答对错误分析 | `self_evaluation` 字段准确度 |
| **数据来源** | 5 题 PB-C partial credit 评分 | LLM 评判 `self_evaluation` 字段 |
| **典型 θ 高** | 调试能力强 | 置信度准确（不过度也不不足）|
| **lbc001 实际** | θ=-0.07 (5 题调试能力中等偏下) | θ=0.21 (占位，无真实评估) |

**关键洞察**：两个解读**测量不同能力**：
- 调试能力**强**的学生不一定置信度**准确**（可能过度自信）
- 调试能力**弱**的学生可能置信度**准确**（知道自己不会）
- 调试能力**强** + 置信度**准确** = 真正的"理解"（既有能力又有元认知）

---

## 3. X 维度 2 种解读深度分析

### 3.1 解读 1: **External Support 外部支架**（信念引擎 / `belief_state.py`）

**定义**：学生**依赖外部支持的程度**（ZPD 理论自足性概念）。

**信念引擎实现**：`X: DimensionState = field(default_factory=lambda: DimensionState(dimension="X"))`

**典型评估**：
- 学生需要看提示 → X 维度高
- 学生需要 worked example → X 维度高
- 学生能独立完成 → X 维度低
- X 维度 = 1 - self_sufficiency

**ZPD 理论依据**（Vygotsky）：
- 最近发展区：学生独立能做 + 在支持下能做之间的差距
- 自足性 = 1 / 差距
- X 维度 = 差距 = 1 - 自足性

**v0.54.1 当前状态**：X θ=0.2145（占位值，无真实评估）

### 3.2 解读 2: **跨语言 / 跨域迁移**（战略层 / v0.54.2 设计）

**定义**：学生**从一种情境迁移到另一种情境**的能力（应用层概念）。

**教学法依据**：
- 学习的最重要标志是"举一反三"
- 跨语言类比（Python↔JS/Java/C++/Ruby）训练迁移能力
- 迁移能力强的学生能快速适应新领域

**典型题型**：
- 跨语言类比："Python 的列表推导式对应 JavaScript 的什么？"
- 设计模式识别："这个 Python 装饰器模式在 Ruby 里叫什么？"
- 算法跨语言实现："Python 的快排怎么翻译成 C++？"

**v0.54.2 计划设计 20+ 道 X 主导题**：完全基于这一定义

**评估方式**：
- a_specialized X 权重 1.0-1.3（C 主导题同模式）
- partial credit 评分 4 档

### 3.3 两种解读的差异

| 维度 | 解读 1: External Support 外部支架 | 解读 2: 跨语言 / 跨域迁移 |
|------|-----------------------------------|--------------------------|
| **核心问题** | "学生需要多少外部支持？" | "学生能跨情境迁移吗？" |
| **教学法依据** | ZPD 理论 / Vygotsky | 迁移学习理论 / 举一反三 |
| **典型题型** | 提示需求 / worked example 需求 | 跨语言类比 / 设计模式识别 |
| **评估信号** | 学生是否独立完成 | 学生能否在不同情境应用知识 |
| **典型 θ 高** | 依赖外部支持多 | 跨域迁移能力强 |
| **lbc001 实际** | θ=0.21 (占位) | θ=0.21 (占位) |

**关键洞察**：两个解读**完全相反的方向**：
- 解读 1：θ 高 = 需要支持（**负向**指标）
- 解读 2：θ 高 = 迁移能力强（**正向**指标）

**如果 v0.54.2 X 主导题答对，MIRT 让 X.theta 涨 0.1**：
- 按解读 1（自足性）：X 维度变高 = 需要更多支持（**反了**）
- 按解读 2（迁移能力）：X 维度变高 = 迁移能力变强（**对了**）

**结论**：当前 `belief_state.py` X 维度定义（External Support）+ v0.54.2 X 主导题设计（跨域迁移）**完全冲突**——必须先统一概念。

---

## 4. 5D 完整性的必要性和重要性

### 4.1 教学法完整性

5D 覆盖了学习的 4 个核心维度：

| 学习目标 | 5D 维度 | 教学法依据 |
|----------|---------|-----------|
| **掌握知识** | K | 知识表征理论 / Anderson 1983 |
| **会做技能** | P | 程序性知识 / 自动化 |
| **会选方法** | S | 元认知 / 策略选择 |
| **避开陷阱** | C (Common mistakes) | 错误分析 / Bjork 合意困难 |
| **举一反三** | X (跨域迁移) | 迁移学习 / 举一反三 |

**5D 缺一不可**：
- 缺 C：学生犯常见错 → 知识扎实但效率低
- 缺 X：学生只能套同种题 → 知识无法迁移
- **5D = 完整学习画像**

### 4.2 心理测量完整性

| 测量角度 | 5D 维度 | 心理测量依据 |
|----------|---------|--------------|
| **能力** | K/P/S 直接测 | IRT / MIRT |
| **校准** | C (Confidence) | 元认知 / calibration |
| **自足** | X (External Support) | ZPD / scaffolding |

**5D 提供 3 个测量角度**：能力 + 校准 + 自足，缺一就只看到"对错"。

### 4.3 工程必要性

lbc001 v0.52.1 真实数据：
- K θ=1.253, P θ=0.955, S θ=0.034, C θ=0.216, X θ=0.216
- 5 维度 SE：K=0.773, P=0.699, S=0.590, C=0.983, X=0.983
- 5 维度 confidence：K=0.564, P=0.589, S=0.629, C=0.504, X=0.504
- `overall = mean(5D conf) = 0.5579`（5 维均值）

**问题**：C/X confidence 0.504（占位 1/(1+SE) = 1/(1+0.983) = 0.504），**整体置信度被虚低**——C/X 真实化才能让 `overall` 真实化。

### 4.4 学术完整性

- 5D 是 ECOS 5D 评估的核心卖点
- 论文/对外宣传都说"5 维度"
- 实际只 3 维度真评估（K/P/S），**学术诚信问题**
- 5D 评估完整性"4/5"或"5/5"是 ECOS 学术价值的关键指标

---

## 5. 3 个方案对比

### 方案 A: **信念引擎改 C/X 定义**（激进）

**操作**：
- `belief_state.py` C 维度从 "Confidence" 改 "Common mistakes"
- `belief_state.py` X 维度从 "External Support" 改 "跨域迁移"
- `ConfidenceDimensionState` 类改名为 `CommonMistakesState`（或保留类名但改文档）
- `illusory_confidence_flag` / `discount_factor` 字段保留作为 C 维度扩展

**优点**：
- 信念引擎与教学法定义完全一致
- v0.54.1 C 主导题 + v0.54.2 X 主导题直接使用
- 5D 评估"4/5 → 5/5"实际意义清晰

**缺点**：
- 大量代码改造（`belief_engine.py` / `belief_state.py` / `web/api/*`）
- `self_evaluation` 字段 / LLM 评判 schema 需重新设计
- 跟 deep-research v2.0 文档冲突（v2.0 第 3 部分 C = "Confidence 认知置信度"）
- 历史数据中 C 维度含义已变 —— lbc001 C θ=0.21 现在评估"调试能力"而非"置信度"

**风险**：🔴 高
- 重构影响所有 5D 评估输出
- `overall_confidence = mean(5D conf)` 公式意义变化
- UI 展示"5D 维度"含义变化

**工作量**：🔴 大（1-2 周 + 多文件修改 + 完整回归测试）

### 方案 B: **C 主导题基于 Common mistakes，信念引擎维持 Confidence**（保守）

**操作**：
- v0.54.1 C 主导题继续基于 "Common mistakes" 教学法定义
- 信念引擎 C 维度维持 "Confidence" 心理测量定义
- **接受两者不匹配**——C 主导题 trigger 后更新 C.theta + C.se，但 C 维度实际含义"调试能力"在文档中说明

**优点**：
- 不改代码
- v0.54.1 C 主导题已经按这个模式工作
- 教学法层和心理测量层"共存"——C 主导题测调试能力，C 维度 θ 反映调试能力（**含义扩展**）
- 5D 评估完整性"4/5"基于教学法层评估

**缺点**：
- 文档不统一——`belief_state.py` C 维度说"Confidence"，02-architecture.md 说"Common mistakes"
- Bisen 在 UI 展示时可能困惑
- 学术诚信模糊——C 维度含义没明确定义

**风险**：🟢 低
- 不动代码
- 文档漂移已存在，不加剧

**工作量**：🟢 小（只改文档，不改代码）

### 方案 C: **C/X 双含义 + 字段解耦**（中间路线）

**操作**：
- C 维度定义：**"调试能力 + 置信度"双含义**（互补）
  - `C.theta`：调试能力（Common mistakes 主导，C 主导题更新）
  - `C.confidence = 1/(1+SE)`：估计可信度（meta-confidence）
  - `C.misconception_hits`：错误历史命中（独立于 θ）
  - `C.self_evaluation_avg`：学生自评均值（LLM Critic 提取）
- X 维度定义：**"跨域迁移 + 自足性"双含义**（互补）
  - `X.theta`：跨域迁移能力（X 主导题更新）
  - `X.confidence = 1/(1+SE)`：估计可信度
  - `X.support_usage_history`：外部支持使用历史（独立于 θ）

**优点**：
- 教学法层（Common mistakes / 跨域迁移）和心理测量层（Confidence / 自足性）**共存**——C/X 维度是复合维度
- v0.54.1 C 主导题 + v0.54.2 X 主导题直接使用
- 5D 评估"4/5 → 5/5"清晰——C/X 真评估
- 字段解耦，每个字段含义明确
- Bisen 在 UI 展示时可以分层展示（"C 维度：调试能力 X.XX，置信度 Y.YY"）

**缺点**：
- 概念较复杂（Bisen 需要理解双含义）
- 字段增加（X 需要新字段 `support_usage_history`）
- 文档需明确双含义

**风险**：🟡 中
- 加字段需要 schema 迁移
- 文档要清晰说明双含义
- 学术论文需说明设计选择

**工作量**：🟡 中（2-3 天 + 多文件 + 文档）

---

## 6. Bisen 决策选项

| 选项 | 描述 | 影响 |
|------|------|------|
| **方案 A** | 信念引擎改 C/X 定义为教学法层 | 激进，1-2 周重构 |
| **方案 B** | C 主导题基于 Common mistakes，信念引擎维持 Confidence | 保守，文档修复 |
| **方案 C** | C/X 双含义 + 字段解耦 | 中间路线，2-3 天 |

**Bisen 决策点**：
1. C 维度：Common mistakes 调试能力 / Confidence 认知置信度 / 双含义？
2. X 维度：跨域迁移 / External Support 外部支架 / 双含义？
3. 整体方案：A / B / C 哪个？

---

## 7. 决策影响（对 v0.54.1 / v0.54.2 / Phase 5 / 整体架构）

### 7.1 对 v0.54.1（C 主导题已落地）

| 方案 | 影响 |
|------|------|
| A | v0.54.1 C 主导题保留，信念引擎 C 维度改名"Common mistakes" |
| B | v0.54.1 C 主导题保留，信念引擎 C 维度维持"Confidence"但文档说明 C 主导题更新的是调试能力 |
| C | v0.54.1 C 主导题保留，信念引擎 C 维度加 `common_mistakes_score` 字段（独立于 confidence） |

### 7.2 对 v0.54.2（X 主导题计划中）

| 方案 | 影响 |
|------|------|
| A | v0.54.2 X 主导题保留，信念引擎 X 维度改名"跨域迁移" |
| B | v0.54.2 X 主导题**问题**——信念引擎 X 维度维持"External Support"，但 X 主导题答对会让 X.theta 涨 0.1（按解读 1 是"自足性下降"）|
| C | v0.54.2 X 主导题保留，信念引擎 X 维度加 `cross_domain_score` 字段 |

### 7.3 对 Phase 5 整体

| 方案 | 影响 |
|------|------|
| A | Phase 5 推进快，但风险大（重构） |
| B | Phase 5 推进慢（文档统一 + 学术诚信风险） |
| C | Phase 5 推进中速（中等工作量，可控） |

### 7.4 对 5D 整体架构

| 方案 | 影响 |
|------|------|
| A | 5D 维度定义清晰统一 |
| B | 5D 维度定义文档漂移持续 |
| C | 5D 维度定义双含义 + 字段解耦 |

---

## 8. 反思：为什么之前没发现这个文档漂移

### 8.1 历史背景

- **v0.1.0 Phase 0**（2026-06-25）：C = "Confidence"，X = "External Support"（信念引擎设计）
- **v0.2.0 ~ v0.7.0**（2026-06-25 ~ 2026-07-10）：C 维度在 belief_state.py 实现
- **v0.40.0 ~ v0.52.3**（2026-07-13 ~ 2026-07-22）：UI + 教学法层概念（C 主导题设计）
- **v0.52.1**（2026-07-22）：C 主导题 "待启用"（审查报告）—— **C 维度定义基于教学法层**
- **v0.53.1**（2026-07-22）：审查报告 §11.2 "C/X 0 主导题"—— **C 维度定义基于"调试题/错误分析"**
- **v0.53.2**（2026-07-22）：ROADMAP v1.4 §3.4 "C 主导题 20+ 题"—— **C 维度定义基于"调试题/错误分析"**
- **v0.54.0-b**（2026-07-23）：C 主导题 5 道设计 —— **C 维度定义基于"Common mistakes"**
- **v0.54.1**（2026-07-23）：C 主导题扩 20 道 —— **C 维度定义基于"Common mistakes"**
- **v0.54.1-c**（2026-07-23）：端到端测试发现 C 维度"真实化" —— **C 维度含义再次暴露漂移**

### 8.2 根因分析

- **CLAUDE.md §防御性自检规范**没覆盖"文档一致性"检查
- v0.52.1 审查报告和 v0.54.0-b C 主导题设计都基于教学法层，但**没交叉验证** `belief_state.py` C 维度定义
- v0.53.1 审查报告 §1.4.2 提到"C 主导题"但**没质疑** C 维度的双重定义
- 端到端测试 v0.54.1-c 触发后，C 维度跌 0.28 暴露问题——**Bisen 提问是发现文档漂移的触发**

### 8.3 防御性自检规范扩展建议

**CLAUDE.md §防御性自检规范**新增第 6 项：

```bash
# 6) 文档一致性检查（动 C/X 维度 / 5D 架构时）
grep -nE "C.*Common|C.*Confidence|C.*认知置信度|C.*调试题" research/ ecos/ web/ | head -20
grep -nE "X.*External|X.*跨语言|X.*跨域" research/ ecos/ web/ | head -20
#   检查 C/X 维度定义在不同文档中是否一致
#   修复: 选定一个权威定义，更新其他文档
```

**CI gate v0.53.0+** 新增第 4 条：5D 维度定义跨文档一致性

---

## 9. 决策记录

### 9.1 待 Bisen 决策

- [ ] **C 维度定义**：Common mistakes 调试能力 / Confidence 认知置信度 / 双含义？
- [ ] **X 维度定义**：跨域迁移 / External Support 外部支架 / 双含义？
- [ ] **整体方案**：A / B / C 哪个？
- [ ] **决策时间窗**：Bisen 决定（建议 24 小时内）

### 9.2 决策后行动

- **方案 A 选定**：
  1. 重构 `belief_state.py` C/X 维度定义
  2. 更新 `belief_engine.py` `web/api/*` 引用
  3. 更新 deep-research v2.0 文档
  4. 完整回归测试
  5. v0.55.0 commit

- **方案 B 选定**：
  1. 更新 02-architecture.md / 07-审查报告 / 09-c-dimension-questions 文档说明 C 主导题更新的是调试能力
  2. belief_state.py 文档加注释说明"Confidence 字段同时反映调试能力（MIRT 更新）和置信度（self_evaluation）"
  3. v0.54.1-d commit

- **方案 C 选定**：
  1. 加 C 维度字段 `common_mistakes_score` / `self_evaluation_avg`
  2. 加 X 维度字段 `cross_domain_score` / `support_usage_history`
  3. schema 迁移
  4. UI 展示分层
  5. v0.54.1-d commit

### 9.3 文档维护规则（决策后）

- 选定 1 个 C/X 维度定义（教学法层或心理测量层或双含义）
- 更新所有相关文档（CLAUDE.md / 02-architecture.md / 07-审查报告 / 09-c-dimension-questions / deep-research v2.0）
- CI gate 6: 5D 维度定义跨文档一致性检查

---

## 10. 关联文档

- [07-project-comprehensive-audit-2026-07-22.md](07-project-comprehensive-audit-2026-07-22.md) §11.2 C/X 0 主导题弊端
- [research/90-mvp/09-phase5-c-dimension-questions-expanded.md](../90-mvp/09-phase5-c-dimension-questions-expanded.md)（v0.54.1 C 主导题 20 道）
- [discussions/2026-07-23-C主导题让C维度真实化发现+缺口分析.md](../../discussions/2026-07-23-C主导题让C维度真实化发现+缺口分析.md)（v0.54.1-c 端到端测试发现）
- [discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md](../../discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md)
- [ecos/cta/belief_state.py:30-37](../../ecos/cta/belief_state.py) DimensionId 定义
- [ecos/cta/belief_state.py:262-273](../../ecos/cta/belief_state.py) ConfidenceDimensionState 详细
- [research/00-overview/02-architecture.md §3](02-architecture.md) 双 Agent 架构
- [research/deep-research/Cognitive-Digital-Twin-Deep-Research.md v2.0 §3](../deep-research/Cognitive-Digital-Twin-Deep-Research.md) 5D 定义来源

---

**创建日期**：2026-07-23
**维护者**：Bisen & Mavis
**下次更新**：Bisen 决策后（v0.54.1-d）
