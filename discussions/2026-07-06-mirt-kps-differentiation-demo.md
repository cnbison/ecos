# MIRT K/P/S 分化验证 Demo

**日期**：2026-07-06
**主题**：跨 skill_id 差异化 a_specialized 设计 → MIRT 多维 θ 分化
**学生角色**：Bisen（模拟）
**对应文档**：`ecos/cta/l2_mirt.py`、`discussions/2026-07-06-belief-engine-bkt-update-demo.md`

---

## 1. 问题：为什么 K/P/S 趋同

### 1.1 初始 Demo 的结果

在单 skill_id Demo（`discussions/2026-07-06-belief-engine-bkt-update-demo.md`）中，14 道题全部围绕同一个 skill_id，结果：

```
K = P = S = 0.567
K/P/S 最大差异: 0.000
```

### 1.2 根本原因

`BiFactorMIRT5D` 的所有题目默认参数：

```python
a_specialized = [0.8, 0.8, 0.8, 0.8, 0.8]  # 均匀加载
```

所有题目对所有维度的加载完全相同，MIRT 无法区分维度，θ 向量在所有题目更新后保持均匀。

---

## 2. 解决方案：差异化 a_specialized 设计

### 2.1 理论依据

ECOS 5D 中，K/P/S 理论上对应不同的认知能力：

| 维度 | 含义 | 对应活动 |
|------|------|---------|
| **K** | 概念知识 | 记忆/理解定义、区分概念 |
| **P** | 程序性知识 | 描述结构、写作流程、指令规范 |
| **S** | 策略性知识 | 何时调用、何为主动加载、边界设计 |

不同 skill_id 的题目天然激活不同维度：

| Skill | 主要维度 | 次要维度 |
|-------|---------|---------|
| `definition` | K（概念）| S（加载策略）|
| `description` | P（程序）| K（理解结构）|
| `loading` | S（策略）| P（优化描述）|
| `practice` | S（策略）| P（调用流程）|
| `scoping` | S（策略）| K（边界知识）|

### 2.2 a_specialized 设计

为每道题手动设置 `a_specialized` 向量，模拟专家设计的 Q 矩阵：

```python
# a_specialized[0]=K, [1]=P, [2]=S, [3]=C, [4]=X

# definition: K 主导
CS-Q01: a_spec = [0.9, 0.2, 0.4, 0.1, 0.1]
CS-Q02: a_spec = [0.9, 0.2, 0.4, 0.1, 0.1]
CS-Q03: a_spec = [0.9, 0.2, 0.4, 0.1, 0.1]  # 答错 → 压制 K

# description: P 主导
CS-Q04: a_spec = [0.3, 0.9, 0.2, 0.1, 0.1]
CS-Q05: a_spec = [0.3, 0.9, 0.2, 0.1, 0.1]
CS-Q06: a_spec = [0.3, 0.9, 0.2, 0.1, 0.1]  # 答错 → 压制 P

# loading: S 主导
CS-Q07: a_spec = [0.2, 0.3, 0.9, 0.1, 0.1]
CS-Q08: a_spec = [0.2, 0.3, 0.9, 0.1, 0.1]
CS-Q09: a_spec = [0.2, 0.3, 0.9, 0.1, 0.1]

# practice: S 主导
CS-Q10: a_spec = [0.2, 0.4, 0.9, 0.1, 0.1]
CS-Q11: a_spec = [0.2, 0.4, 0.9, 0.1, 0.1]
CS-Q12: a_spec = [0.2, 0.4, 0.9, 0.1, 0.1]

# scoping: S 主导
CS-Q13: a_spec = [0.3, 0.2, 0.9, 0.1, 0.1]
CS-Q14: a_spec = [0.3, 0.2, 0.9, 0.1, 0.1]
```

---

## 3. 结果

### 3.1 演化轨迹

| QID | Skill | Bloom | OK | K | P | S |
|------|-------|-------|----|----|----|----|
| 初始 | — | — | — | 0.500 | 0.500 | 0.500 |
| CS-Q01 | definition | L1 | Y | 0.500 | 0.500 | 0.500 |
| CS-Q02 | definition | L2 | Y | **0.645** | 0.545 | 0.574 |
| CS-Q03 | definition | L4 | **N** | **0.561** ↓ | 0.518 | 0.530 |
| CS-Q04 | description | L1 | Y | 0.567 | **0.597** | 0.542 |
| CS-Q05 | description | L3 | Y | 0.571 | **0.649** | 0.551 |
| CS-Q06 | description | L2 | **N** | 0.564 | **0.561** ↓ | 0.537 |
| CS-Q07 | loading | L2 | Y | 0.558 | 0.568 | **0.604** |
| CS-Q08 | loading | L3 | Y | 0.554 | 0.573 | **0.650** |
| CS-Q09 | loading | L4 | Y | 0.551 | 0.577 | **0.685** |
| CS-Q10 | practice | L2 | Y | 0.548 | 0.584 | **0.711** |
| CS-Q11 | practice | L3 | Y | 0.546 | 0.590 | **0.731** |
| CS-Q12 | practice | L4 | Y | 0.544 | 0.595 | **0.749** |
| CS-Q13 | scoping | L2 | Y | 0.546 | 0.594 | **0.764** |
| CS-Q14 | scoping | L4 | Y | 0.549 | 0.592 | **0.778** |

### 3.2 最终状态

| 维度 | 最终值 | 解读 |
|------|--------|------|
| **S** | **0.778** | loading/practice/scoping 题目（S 主导）全对，持续推高 |
| **P** | **0.592** | description 题目（P 主导）Q06 答错，压制了 P 的上升 |
| **K** | **0.549** | definition 题目（K 主导）Q03 答错，压制了 K |

**K/P/S 最大差异：0.229** ✅

### 3.3 关键观察

1. **S 维度最高（0.778）**：因为 loading/practice/scoping 题目（S 主导）全部答对，S 的高加载题目持续推高 S

2. **K 被 Q03 答错压制**：Q03 是 definition 高 K 加载题目，答错后 K 从 0.645 高点跌至 0.561，之后未能完全恢复

3. **P 被 Q06 答错压制**：Q06 是 description 高 P 加载题目，答错后 P 短暂下降后继续上升（description 其他题答对）

4. **C 维度（置信度）始终跟随**：C ≈ 0.55，与 K/P/S 同步变化

---

## 4. 结论

### 4.1 MIRT 多维区分能力验证 ✅

差异化 `a_specialized` 设计使得 MIRT 能够：

- 将"答对 definition 题"的信息主要更新到 **K** 维度
- 将"答对 description 题"的信息主要更新到 **P** 维度
- 将"答对 loading/practice/scoping 题"的信息主要更新到 **S** 维度

### 4.2 现实意义

在真实 Beta 测试中，这个 Q 矩阵需要由领域专家标注（每个题目由教师标注其在 K/P/S/C/X 各维度的加载强度），而非手动设计。这正是 `data/q_matrix.json` 的用途。

---

## 5. 相关文件

- `ecos/cta/l2_mirt.py` — BiFactorMIRT5D 实现
- `ecos/cta/belief_engine.py` — BeliefEngine.update()
- `data/q_matrix.json` — Q 矩阵模板（教师协作填充）
- `discussions/2026-07-06-belief-engine-bkt-update-demo.md` — 单 skill_id Demo
