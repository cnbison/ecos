# Phase 5 Partial Credit 实施文档（PHA5-PRD-CR v1.0）

> **日期**：2026-07-23
> **触发**：Bisen 2026-07-22 lbc001 PB-Q18 截图分析 → 2026-07-23 lbc001 达 31 题 Phase 5 启动
> **状态**：🟢 Phase 5 v0.54.0 启动 — 红灯 v0.53.0 docs sync → v0.53.1 审查报告 → v0.53.2 ROADMAP v1.4 → v0.53.3 silent pass 修 → v0.54.0 Partial Credit 实施
> **依赖**：
> - [discussions/2026-07-22-partial-credit重大学术弊端发现.md](../../discussions/2026-07-22-partial-credit重大学术弊端发现.md)（8.2 KB）— 问题定义 + 4 个相关弊端
> - [discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md](../../discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md)（12.2 KB）— Phase 5 双目标
> - [research/90-mvp/06-ecos-end-to-end-flow-analysis.md](../90-mvp/06-ecos-end-to-end-flow-analysis.md)（26.7 KB）— 端到端流程
> - [research/90-mvp/python-basics-q-matrix-design.md §9.2](../90-mvp/python-basics-q-matrix-design.md)（v0.52.1 扩充 C/X 缺口）

---

## 0. 概述

### 0.1 一句话目标

**MIRT 二元对错（`correct: bool`）改为连续 partial credit（`score: float ∈ [0, 1]`），让 70% 答对按 0.7 处理而非 0% 处理，从根上修复 lbc001 PB-Q18 类问题的 5D 维度暴跌。**

### 0.2 范围

| 范围内 | 范围外 |
|--------|--------|
| ✅ `correct: bool` → `score: float` 字段映射 | ❌ error_type 分类（v0.55.0+）|
| ✅ AI 评判返回 `score` | ❌ 跨题关联 / 错误模式聚类（v0.55.0+）|
| ✅ MIRT 接受连续 `score` | ❌ 错误类型 → theta 更新策略映射（v0.55.0+）|
| ✅ 简化 Bloom 更新（按 `score`） | ❌ demonstrated_skills / missing_components 推断（v0.55.0+）|
| ✅ DB 兼容老 `correct: bool` 数据 | ❌ C 主导题扩 20+ 题（v0.54.1）|
| ✅ lbc001 端到端测试 | ❌ pytest 单元测试套件（v0.55.0）|

### 0.3 关键数据

- lbc001 当前 31 题（差 0 题，已达 Phase 5 启动条件）
- lbc001 答对 19-20 道（86%），错 3 道（PB-Q06 range / PB-Q18 反转 / 1 道 loops）
- 已知 partial credit 触发：lbc001 PB-Q18（K 维度多跌 0.27，L6 多跌 0.2）

---

## 1. 现状分析

### 1.1 当前 MIRT 公式（已支持连续值！）

`ecos/cta/l2_mirt.py:135` 实际公式：

```python
log_lik = float(np.sum(responses * np.log(probs) + (1.0 - responses) * np.log(1.0 - probs)))
```

**关键发现**：`responses * log(probs) + (1-responses) * log(1-probs)` 数学上已支持 `responses ∈ [0, 1]` 连续值！
- 当 `responses = 0`：`-log(1-probs)` → 最大化 `probs`（答错但模型预测高）
- 当 `responses = 1`：`log(probs)` → 最大化 `probs`（答对且模型预测高）
- 当 `responses = 0.7`：`0.7 * log(probs) + 0.3 * log(1-probs)` → 部分加权

**所以 MIRT 公式层不用改**，只需软件层让 `score` 传到 MIRT。

### 1.2 当前 BeliefEngine 关键代码

| 位置 | 当前实现 | 改造 |
|------|----------|------|
| `Observation.correct: bool` (line 64) | bool | 加 `score: float` 字段 |
| `engine.update()` 接收 `correct: bool` (line 286) | bool | 加 `score: float` 参数 |
| Step 1 BKT: `self.l1.update(skill_id, correct)` (line 316) | bool | 派生 `correct = score >= 0.6` |
| Step 2 history: `"correct": int(correct)` (line 326) | int 0/1 | 加 `"score": score` |
| Step 3 MIRT: `responses = np.array([h["correct"] for h in history], dtype=float)` (line 340) | float 0/1 | 改用 `h["score"]` |
| Step 4 Bloom: `if correct:` (line 361) | 二元 | 简化：`delta = (score - 0.5) * 2 * step` |
| Step 5 LLM: `student_correctness=observation.correct` (line 423) | bool | 改 `score` |

### 1.3 当前 AI 评判 Schema

`ecos/cta/llm_critic/schemas.py` PerceptionOutput：
- `correctness: bool`（line 28）
- 改为：`score: float ∈ [0, 1]` + `correctness: bool`（派生，score >= 0.6）

`web/api/belief.py` submit_answer：
- 接收 `correct: bool`
- 改为：接收 `score: float` + 派生 `correct: bool`

### 1.4 当前 DB 字段

`students.response_history` JSON 字段（v0.49.2 改 dict 格式 + v0.52.2 加 ai_reasoning）：

```python
{
    "problem_id": "PB-Q18",
    "correct": 0,        # ← 当前 int 0/1
    "score": None,       # ← v0.54.0 加（新数据填，老数据 None）
    "bloom_level": "CREATE",
    "user_answer": "...",
    "correct_answer": "...",
    "ai_reasoning": "...",
    "timestamp": "..."
}
```

**兼容方案**：
- 新数据：`score` 填实际值
- 老数据：`score = None` → 加载时 fallback 到 `correct ? 1.0 : 0.0`

---

## 2. 设计决策

### 2.1 决策 1：MIRT score 范围 [0, 1]

**选项**：
- A) `[0, 1]` 连续（如 0.7 = 70% 答对）
- B) `[-1, +1]`（正负方向）
- C) `{0, 0.5, 1}`（三档：错/部分对/对）

**选 A**：MIRT 公式已支持，语义直观（0.7 就是 70%）。

### 2.2 决策 2：correct 字段保留（兼容）

`correct: bool` 字段保留，作为 `score >= 0.6` 的派生值。
- 原因：DB 兼容 + UI 已有逻辑（如 `if correct`）
- 阈值 0.6：partial credit 文档推荐

### 2.3 决策 3：Bloom 更新简化

**当前**：`if correct: bloom += step else: bloom -= step`
**新版**：`bloom_delta = (score - 0.5) * 2 * step`
- score=0.0 → delta = -step（最大跌）
- score=0.5 → delta = 0（中性）
- score=1.0 → delta = +step（最大涨）

### 2.4 决策 4：MIRT 估计窗口不变

MIRT MAP 估计仍用最近 N 题（response_history 全量）。
- 优点：实现简单
- 缺点：MIRT 用 0.7 和 1.0 在 MIRT 内部是连续值，但 history 仍按时间排序

### 2.5 决策 5：LCA / Misconception / TC 暂不改造

只改 CTA 5D + Bloom 评估层。LCA / Misconception / TC 维持原样。
- 原因：v0.54.0 范围控制
- LCA：v0.56.0+ 实施
- Misconception：v0.52.0 已修库 ID，逻辑不变
- TC：v0.55.0+ 改造

### 2.6 决策 6：AI 评判 prompt 改造范围

**最小改造**：
- 新增字段：`score: float ∈ [0, 1]`
- 保留字段：`correctness: bool`（派生）
- 保留字段：`reasoning: str`
- **不**加 error_type / missing_components / demonstrated_skills（v0.55.0+）

---

## 3. 实施步骤（按 commit 拆解）

### 3.1 v0.54.0-a: PHA5-PRD-CR 文档（本文档）🟢 当前

### 3.2 v0.54.0-b: schemas.py 改造

**文件**：`ecos/cta/llm_critic/schemas.py`

**改动**：
```python
@dataclass(frozen=True)
class PerceptionOutput:
    # ...
    score: float = 0.0  # 0.0-1.0, v0.54.0 新增
    correctness: bool = False  # 派生：score >= 0.6
    # ...
```

**风险**：低（加字段，兼容老 PerceptionOutput(score=1.0 if correct else 0.0)）

### 3.3 v0.54.0-c: perception.py AI 评判 prompt 改造

**文件**：`ecos/cta/llm_critic/perception.py`

**改动**：
- LLM prompt 加 `score: float` 字段
- JSON schema 加 `score` 字段
- `correctness` 派生 `score >= 0.6`

**风险**：中（LLM 输出的稳定性需测试）

### 3.4 v0.54.0-d: belief_engine.py 改造（核心）

**文件**：`ecos/cta/belief_engine.py`

**改动**：
1. `Observation` dataclass 加 `score: float = 0.0` 字段
2. `engine.update()` 加 `score: float = 0.0` 参数（兼容老调用）
3. Step 1 BKT：`correct = score >= 0.6` 派生
4. Step 2 history：存 `score: float` + 派生 `correct: bool`
5. Step 3 MIRT：`responses = np.array([h.get("score", h.get("correct", 0)) for h in history], dtype=float)`
6. Step 4 Bloom：`bloom_delta = (score - 0.5) * 2 * self.config.bloom_update_step`
7. Step 5 LLM：传 `student_correctness=score`（不是 bool）

**风险**：高（核心引擎，需要 lbc001 端到端测试）

### 3.5 v0.54.0-e: web/api/belief.py 改造

**文件**：`web/api/belief.py`

**改动**：
- `submit_answer()` 接收 `score: float` 参数
- 派生 `correct: bool = score >= 0.6`
- 存 `response_history` 加 `score` 字段

**风险**：中（API 改动）

### 3.6 v0.54.0-f: web/student/app.js 端到端测试

**文件**：`web/student/app.js`

**改动**：
- `submit()` 调用 `/api/answer` 传 `score` 字段
- 实际不用改（前端只接收 LLM 评判结果）

**测试**：
- lbc001 答 1 道新题（PB-Q 编号递增）
- 检查 response_history 含 `score` 字段
- 检查 5D 维度变化符合 partial credit

### 3.7 v0.54.1: C 主导题扩 20+ 题

详见 [07-c-dimension-questions.md](07-c-dimension-questions.md)（v0.54.0-b 文档）

---

## 4. MIRT 公式推导（数学基础）

### 4.1 当前二元 MIRT

`P(correct | θ, a, d) = sigmoid(a · θ - d)`

似然函数：
`L(θ) = Π_i P(correct_i | θ, a_i, d_i)^r_i · (1 - P(correct_i))^（1 - r_i)`

其中 `r_i ∈ {0, 1}` 是二元 response。

### 4.2 新版连续 MIRT

`L(θ) = Π_i P_i^s_i · (1 - P_i)^(1 - s_i)`

其中 `s_i ∈ [0, 1]` 是 continuous score。

**数学等价**：
- s_i = 0: `L_i = (1 - P_i)`（模型预测 P_i 越低越好）
- s_i = 1: `L_i = P_i`（模型预测 P_i 越高越好）
- s_i = 0.7: `L_i = P_i^0.7 · (1 - P_i)^0.3`（加权混合）

**几何解释**：s_i 是"该题答对程度"——0.7 表示 70% 答对，模型既要倾向于预测 70% 概率（不是 100%），又要考虑 30% 的 1-P 成分。

### 4.3 θ 更新幅度

二元时：
- 答对：`θ += α · (1 - P)`（θ 朝"答对"方向更新）
- 答错：`θ -= α · P`（θ 朝"答错"方向更新）

连续时：
- score = 0.7：`θ += α · (0.7 - P) · weight`
- weight = score (s_i 本身作为更新权重)

**重要**：score=0.7 时的更新幅度是 score=1.0 时的 70%，与 MIRT 似然一致。

### 4.4 Bloom 更新公式

简化版：
```python
bloom_delta = (score - 0.5) * 2 * bloom_update_step
# score=0.0 → delta = -step (max 跌)
# score=0.5 → delta = 0 (中性)
# score=1.0 → delta = +step (max 涨)
```

**举例**（bloom_update_step=0.1）：
- score=0.0: -0.1
- score=0.3: -0.04
- score=0.5: 0
- score=0.7: +0.04
- score=1.0: +0.1

这与 partial credit 文档 §4.1 期望一致：score=0.7 时 K 涨 0.7×0.05 ≈ 0.035（不是 0 或 +0.22）。

---

## 5. 验收标准

### 5.1 lbc001 端到端测试

**步骤**：
1. lbc001 答 1 道已知部分对题（如改造后的 PB-Q18 类）
2. 提交时 AI 评判返回 `score: 0.7`
3. 5D 维度更新：K 微涨（不是大跌）
4. Bloom 维度：按 demonstrated skills 决定

**通过条件**：
- ✅ response_history 含 `score: 0.7`
- ✅ MIRT θ 更新幅度符合公式（K 涨约 0.04-0.07）
- ✅ 老数据兼容（response_history 中 score=None 的项，fallback 到 0.0/1.0）

### 5.2 回归测试

**步骤**：
1. lbc001 历史 31 题 response_history 不丢
2. 之前答对的题 (correct=1) score 应为 None 或 1.0
3. 之前答错的题 (correct=0) score 应为 None 或 0.0
4. 5D 维度 θ 与改造前不应有显著差异（< 0.1）

**通过条件**：
- ✅ response_history 长度 = 31
- ✅ 老数据 `score` 字段为 None
- ✅ 5D 维度误差 < 0.1

### 5.3 防御性自检

- silent failure 扫描：0 新增
- 版本号同步：0.54.0 之后
- git diff stat：每个 commit < 200 行
- CSS 引用关系：不适用
- DB 恢复路径：`response_history` schema 兼容

---

## 6. 测试计划

### 6.1 单元测试（v0.55.0 推迟）

- ❌ pytest 套件：v0.55.0+ 实施
- ✅ 手动测试：lbc001 答 1 道新题

### 6.2 集成测试

- ✅ lbc001 端到端：submit → AI 评判 → state update → DB 持久化
- ✅ 老数据兼容：reload response_history 31 题
- ✅ 5D 维度变化：partial credit 应反映在 MIRT

### 6.3 性能测试

- MIRT MAP 估计：response 数从 31 → 32，新增 < 1s
- AI 评判延迟：< 30s（已有超时保护）

---

## 7. 风险与回退

### 7.1 风险

| # | 风险 | 严重度 | 缓解 |
|---|------|--------|------|
| 1 | LLM 评判 score 字段不稳定（不同 LLM 输出 0.7 vs 0.8）| 中 | 加 schema 验证 + 多次试验取平均 |
| 2 | MIRT MAP 估计对连续 score 收敛慢 | 中 | 加 L-BFGS-B maxiter + tolerance |
| 3 | 老数据 score=None 处理边界情况 | 中 | fallback 到 correct ? 1.0 : 0.0 |
| 4 | Bloom 公式简化后误判 | 低 | 改前先看 dominant_layer 是否稳定 |

### 7.2 回退方案

- **v0.54.0 失败**：回滚到 v0.53.3，partial credit 留 v0.55.0
- **MIRT 公式失败**：保留 score 字段但 MIRT 仍按 correct=score>=0.6 二元
- **DB 兼容失败**：老数据 score=None 时强制 fallback 1.0/0.0

---

## 8. 与其他 Phase 5 任务关系

### 8.1 与 C 主导题关系

C 主导题（v0.54.1）的 partial credit 需求更高——debug / error analysis 题天然是 partial credit 的（找到 1 个 bug 不代表找到所有 bug）。
- v0.54.0 partial credit 模型
- v0.54.1 C 主导题题库用 partial credit 评分
- v0.55.0 X 主导题 + X 维度 misconception 库

### 8.2 与 lbc001 31 题数据关系

- 31 题中 19-20 道答对（86%）
- 3 道错（partial credit 触发：PB-Q18 / PB-Q06 / 1 道 loops）
- 改造后：3 道错题会"减轻惩罚"，但 K 维度仍反映真实能力

### 8.3 与 ROADMAP v1.4 §3.4 双目标关系

- ✅ 目标 A：Partial Credit 必修（v0.54.0 当前）
- 📋 目标 B：C 主导题 20+ 题（v0.54.1）

---

## 9. 决策记录

**Bisen 2026-07-23 决策**：
- ✅ Phase 5 v0.54.0 启动
- ✅ Partial Credit 改造先做（MIRT 公式已支持连续值，改造范围可控）
- ✅ C 主导题题库设计 v0.54.1 跟进
- 📋 v0.55.0 X 主导题 + X misconception 库 + pytest 套件
- 📋 v0.56.0 LCA 实施
- 不推迟（避免重蹈"标待启用"覆辙）

**Mavis 2026-07-23 反思**：
- 关键发现：`l2_mirt.py:135` 公式已支持连续值，节省了核心公式改造工作量
- 风险点：LLM 评判 schema 稳定性（不同 LLM 输出 score 可能不一致）
- 后续：每改一步 grep 一次（CLAUDE.md §防御性自检）

---

## 10. 关联文档

- [discussions/2026-07-22-partial-credit重大学术弊端发现.md](../../discussions/2026-07-22-partial-credit重大学术弊端发现.md)
- [discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md](../../discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md)
- [research/90-mvp/06-ecos-end-to-end-flow-analysis.md](../90-mvp/06-ecos-end-to-end-flow-analysis.md)
- [research/90-mvp/python-basics-q-matrix-design.md §9.2](../90-mvp/python-basics-q-matrix-design.md)
- [research/00-overview/03-roadmap.md §3.4](../00-overview/03-roadmap.md)
- [research/00-overview/07-project-comprehensive-audit-2026-07-22.md §11](../00-overview/07-project-comprehensive-audit-2026-07-22.md)
- [ecos/cta/l2_mirt.py:135](../../ecos/cta/l2_mirt.py)
- [ecos/cta/belief_engine.py:286-410](../../ecos/cta/belief_engine.py)
- [ecos/cta/llm_critic/schemas.py:28](../../ecos/cta/llm_critic/schemas.py)
- [web/api/belief.py](../../web/api/belief.py)

---

**创建日期**：2026-07-23
**维护者**：Bisen & Mavis
**下次更新**：v0.54.0-c/d 实施后
