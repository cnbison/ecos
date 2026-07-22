# Partial Credit 缺失: 影响实际应用的重大弊端发现

> **日期**: 2026-07-22
> **触发**: lbc001 答 PB-Q18 (L6 variables) 截图分析
> **作者**: Bisen & Claude
> **状态**: 🔴 已记录, ⏳ 短期 v0.52.2 存 AI reasoning, **Phase 5 必解** partial credit
> **关联**:
> - [2026-07-22-Phase5-Q矩阵CX重新设计路线图.md](2026-07-22-Phase5-Q矩阵CX重新设计路线图.md) (已加 partial credit 任务)
> - [2026-07-21-lbc001测试发现4个BUG分析与修复计划.md](2026-07-21-lbc001测试发现4个BUG分析与修复计划.md) (lbc001 测试发现的 4 个 BUG)

---

## 0. 触发事件

lbc001 答 PB-Q18 (L6 variables, 题目: 设计一个程序, 用户输入一个三位数, 程序输出它的逆序数)

**学生答案**:
```python
a = num % 10       //个位
b = num//10 % 10   //十位
c = num//100       //百位
rev = a*100 + b*10 + c
```

**AI 评判**: ❌ 错误

**AI 评论**:
> 核心算法逻辑正确 (提取个、十、百位并倒序组合), 但缺少 `input()` 获取用户输入和 `print()` 输出结果, 不构成完整可运行程序

**5D 影响** (DB 现状):
- K: 1.18 → 0.9638 (**跌 0.22**)
- P: 不变
- S: 0.71 → 0.0542 (累计效应, 之前 loops 错题拉低)
- C/X: 不变 (标"待启用")

---

## 1. 重大弊端: Partial Credit 缺失

### 1.1 现象

学生答案:
- ✅ **核心算法对** (提取个/十/百位 + 倒序组合)
- ❌ **缺 `input()` 和 `print()`**, 不构成完整可运行程序
- 实际能力: **70-80%** (算法思维正确, I/O 缺失)

ECOS 评判: **完全错** (`correct: false`)

### 1.2 影响量化

| 指标 | 答对 (假设) | 答错 (实际) | 差距 |
|------|------------|------------|------|
| K 维度 | +0.05 (MIRT 微涨) | -0.22 (MIRT 拉向 0) | **0.27** |
| Bloom L6 | +0.1 (设计展示 L6 思维) | -0.1 (L6 跌) | **0.2** |
| TC progress | +0.05 | -0.05 | **0.1** |
| 整体置信度 | 0.59 (涨) | 0.56 (跌) | **0.03** |

**70% 答对被当 0% 答对处理, K 维度多扣 0.27, L6 多扣 0.2**。

### 1.3 简化本质

**MIRT 框架假设"答对=有该项能力, 答错=无该项能力"** (二元对错)。

**实际学习更复杂**:
- "理解但粗心" (K 不变, 录入"粗心"标签)
- "理解但缺 I/O" (K 微跌, L 维度"完整性"扣)
- "不理解" (K 大跌)
- "概念混淆" (K 大跌, misconception 触发)

ECOS 把这 4 种情况都按"不理解"处理。

---

## 2. 其他 4 个相关弊端

### 2.1 对错不区分错误类型 ⚠️

| 错误类型 | 现实影响 | ECOS 处理 |
|---------|---------|----------|
| 粗心 | K 不变, 录入"粗心" | K 大跌 |
| 不理解 | K 大跌 | K 大跌 ✓ |
| 概念混淆 | K 大跌, misconception 触发 | K 大跌 ✓ 但 misconception 没分类 |
| API 记错 | K 微跌 | K 大跌 |

### 2.2 答对不等于"理解"

学生答对但"死记硬背"和"深度理解"涨的 theta 一样。

- 答对可能涨 L6 Bloom (实际只是抄答案)
- 答错可能跌 L6 Bloom (实际展示了 L6 思维但少了 I/O)

### 2.3 response_history 不存 AI reasoning ⚠️ 立即可修

当前 `response_history` 字段:
```python
{
    "problem_id": "PB-Q18",
    "correct": False,
    "bloom_level": "CREATE",
    "user_answer": "...",
    "correct_answer": "...",
    "timestamp": "...",
    # ↓ 全部没存:
    # - AI reasoning (具体评论)
    # - 错误类型分类
    # - 哪个 step 错了
}
```

后果: Phase 5 想做"AI reasoning 分析 → 调整 confidence" 没数据回溯。

**短期 v0.52.2 修复**: 把 AI reasoning 存进 response_history。

### 2.4 跨题目无关联

每次 `engine.update()` 独立。
- 不看 lbc001 之前 loops 答错 6/9 题, 现在 PB-Q18 又错, 错误模式是"arithmetic reasoning"
- 不能识别"学习模式" (如"lbc001 在算术表达式上系统性弱")
- TC 状态检测只看"对错 + has_active_misc", 不分析"对在哪错在哪"

---

## 3. 根本原因: MIRT 框架的 trade-off

| 设计选择 | 优点 | 代价 |
|---------|------|------|
| 二元对错 (`correct: bool`) | 简单, 可计算 | partial credit 丢失 |
| MIRT 单题 MAP 估计 | 贝叶斯严谨 | 不分析"思维过程" |
| Bloom 累积靠对错 | 跟踪认知层级 | "对错"≠"认知层级" |
| TC 状态机 | 跟踪阈值概念跨越 | 不区分错误子类型 |

**MIRT 框架本身假设"答对=有该项能力, 答错=无该项能力"**。这个假设对**短程答题**有效, 但**对学习过程不准确**。

---

## 4. 改进方向 (Phase 5 必修)

### 4.1 Partial Credit (v0.53.0+ 必修)

**LLM 评判输出 `score: 0.0-1.0`, 不用 `correct: bool`**

新评判 prompt:
```json
{
    "score": 0.7,        // 0.0-1.0, 部分对
    "correct": false,    // score >= 0.6 仍算对
    "reasoning": "核心算法对, 缺 I/O",
    "error_type": "incomplete",  // 粗心/不理解/概念混淆/API记错/不完整
    "missing_components": ["input()", "print()"],
    "demonstrated_skills": ["arithmetic_extraction", "reverse_composition"]
}
```

新 MIRT 更新 (partial credit):
- `theta` 更新按 score 加权 (score=0.7 时 K 涨 0.7×0.05 而非 0 或 0.22)
- `cov` 更新按 (1 - score) 加噪声
- `dim.confidence` 公式不变 (仍是 1/(1+SE))

新 Bloom 更新 (按 demonstrated_skills):
- 即使 `correct=false`, 如果 demonstrated_skills 含 L6 元素, L6 confidence 不跌
- 如果 missing_components 是 L1-L2 (I/O 完整性), 不影响 L6

新 TC 更新 (按 error_type):
- "粗心" → TC 不变
- "不理解" → TC progress 跌
- "概念混淆" → TC progress 跌 + misconception 触发

### 4.2 错误类型分类 (v0.53.0+)

LLM 评判同时分类错误:
- `careless` (粗心, 答案对但有 typo)
- `incomplete` (不完整, 缺关键步骤)
- `misconception` (概念混淆)
- `unfamiliar` (不理解)
- `api_misremember` (API 记错)

每种类型对应不同的 theta 更新策略。

### 4.3 AI Reasoning 入库 (v0.52.2 短期, 已决定)

```python
{
    "problem_id": "PB-Q18",
    "correct": False,
    "bloom_level": "CREATE",
    "user_answer": "...",
    "correct_answer": "...",
    "timestamp": "...",
    "reasoning": "核心算法对, 缺 I/O",  # ← v0.52.2 加
    "score": None,                        # ← v0.53.0 partial credit 时加
    "error_type": None,                   # ← v0.53.0 错误类型时加
}
```

### 4.4 跨题关联 (v0.54.0+)

Trajectory summary 增强:
- 存"错误模式聚类" (loops 错率 67% + arithmetic 错)
- 存"学习增益" (从错到对的 transition)
- 存"topic 弱项排名" (top 3 weak topics)

---

## 5. 实施计划

| 版本 | 内容 | 风险 |
|------|------|------|
| **v0.52.2 (本周末)** | response_history 存 AI reasoning | 低 (新加字段) |
| v0.53.0 | partial credit + error_type (Phase 5 启动) | 中 (MIRT 公式改) |
| v0.54.0 | 跨题关联 + 错误模式聚类 | 中 (trajectory 结构改) |
| v0.55.0 | C/X 主导题扩 (已规划) | 中 (Q 矩阵扩) |

---

## 6. 反思

**这次发现是 ECOS MIRT 框架的**根本**局限**, 不是 bug**。

但截图里"算法对但缺 I/O = 完全错"是个**典型反例**——ECOS 把"70% 对"按"0% 对"处理, 导致 K 跌 0.22。

**Bisen 这次测试 (lbc001 27 题) 暴露了 MIRT 框架的根本简化**。**Phase 5 partial credit 是必解任务**, 不能推迟。

短期 v0.52.2 存 AI reasoning 是**数据基础**——Phase 5 partial credit 模型需要历史 reasoning 训练。

---

## 7. 关联文档

- [2026-07-22-Phase5-Q矩阵CX重新设计路线图.md](2026-07-22-Phase5-Q矩阵CX重新设计路线图.md) — partial credit 任务 (v0.53.0+ 必修)
- [2026-07-21-lbc001测试发现4个BUG分析与修复计划.md](2026-07-21-lbc001测试发现4个BUG分析与修复计划.md) — 4 BUG 根因
- `ecos/cta/belief_engine.py` — engine.update() Step 1-9 流程
- `web/api/belief.py` — submit_answer() 入口
- `web/student/app.js` — submit() 端到端调用

---

## 8. 决策记录

**Bisen 2026-07-22 决策**:
- 这个问题属于"影响实际应用的重大弊端发现", 记入项目文档
- 短期 v0.52.2 先加 response_history 存 AI reasoning
- Phase 5 路线图必须解决 partial credit 问题
- 不推迟 (避免重蹈 v0.50.0 "LearningDNA 7 组件虚标"覆辙)
