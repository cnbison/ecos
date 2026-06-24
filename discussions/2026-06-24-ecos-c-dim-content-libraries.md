# 2026-06-24 · C 维度内容库借鉴文档撰写（P0 第 3 份 + P0 全部完成）

## 主题

完成 P0 第 3 份理论借鉴文档 `research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md`（v1.0，414 行），建立 CTA C 维度的双轨内容库。**P0 三件套全部完成**。

## 日期

2026-06-24

## 背景

[v0.1 综合报告 §第四部分](../research/gpt-dialogues/04-cognitive-digital-twin-v01-report.md) 把 CTA 5D 中的 C 维度定义为"认知置信度（Confidence）"——"知道自己会 / 知道自己不会 / 以为自己会（伪置信）/ 以为自己不会"。**但没有给出 C 维度的科学评估基础**——CTA 不知道"伪置信"如何识别、不知道"liminal 状态"如何处理。

本次借鉴 2 大内容库，让 C 维度从抽象"confidence"变为可科学评估的维度。

## 核心成果：双轨内容库

| 内容库 | 解决的挑战 | 借鉴到 ECOS CTA 的哪个环节 |
|---|---|---|
| **Threshold Concepts (Meyer & Land, 2003)** | 跨越阈限概念时的"质变" + Liminality 中间态 | CTA C 维度**关键节点识别** + 解释"质变" |
| **Misconceptions Research (Driver, 1980s-; Chi, 1992)** | 学生"伪置信"——以为懂但实际误解 | CTA C 维度**反例库** + LLM Critic 检测 |

两者构成 C 维度的**双轨内容库**——**TC 是正向骨架**（哪些概念必须掌握），**Misconceptions 是反向补丁**（哪些错误必须消除）。

## P0 三件套全部完成

```
v0.3.0  CTA 数学基础        (5 层数学栈)            ✅
v0.4.0  LCA 教学法基础      (3 大理论群)            ✅
v0.5.0  C 维度内容库         (TC + Misconceptions)  ✅
─────────────────────────────────────────────────
P0 借鉴全部完成
```

**v0.3.0 + v0.4.0 + v0.5.0 共同填补 v2.0 §3.3-3.4 的全部 gap**：
- §3.3 "只提名字（IRT/BKT/DKT）" → v0.3.0 5 层数学栈
- §3.4 "有策略列表无理论论证" → v0.4.0 3 大教学法理论群
- §3.3 "C 维度是抽象置信度" → v0.5.0 TC + Misconceptions 双轨

## 核心决策

### 1. TC 与 Misconception 的双轨结构

```
CTA C 维度评估基础：
  正向骨架: Threshold Concepts（5-8 个 MVP）
  反向补丁: Misconceptions（30-50 条 MVP）
         ↓
  CTA C 维度 = BKT + LLM Critic + TC 检测 + POMDP 整合
```

### 2. TC 不可逆性建模

TC 的 5 特征之一是 **Irreversible（不可逆）**——一旦 post-liminal，C 维度永不下降（除非遗忘整个学科）。这是 C 维度评估的关键规则。

### 3. Liminal 状态识别

学生在跨越 TC 时处于**Liminal（中间态）**——迷茫、挫败、可能退回，表现为"学过的忘了"。CTA 必须**正向沟通**"这是正常过程"（LCA 配合），而不是判定为"退步"。

### 4. 数学层不用 LLM（沿用 v0.3.0 硬底线）

信念估计不用 LLM，但 **Misconception 检测可用 LLM Critic**——这是检测层的合理使用，不违反硬底线。

## MVP 候选清单（初版）

### 初中数学 TC（8 个）
1. 函数 / 2. 变量 / 3. 等式 vs 不等式 / 4. 几何证明 / 5. 负数 / 6. 分数 / 7. 函数图像 / 8. 极限（初步）

### 初中数学 Misconception（10 个）
M1 乘法总是变大 / M2 分母大 → 分数大 / M3 等式性质推广到不等式 / M4 负数不存在 / M5 0 是"没有" / M6 圆周率是 3.14 / M7 平方 = 2 倍 / M8 函数必过原点 / M9 几何证明 = 计算 / M10 概率是"运气"

> 实际库需教师团队最终确认。

## 产出文件

| 文件 | 角色 | 行数 |
|---|---|---|
| `research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md` | **主文档**——C 维度内容库借鉴（v1.0，双轨内容库）| 414 |
| `discussions/2026-06-24-ecos-c-dim-content-libraries.md` | **本文件**——本次会话简要记录 | ~100 |
| `CHANGELOG.md` | 升级到 v0.5.0 | — |

## P0 三件套完整 L0-L4 算法栈

```
L4 LCA 策略优化层           Cognitive Apprenticeship 6 阶段框架（LCA 决策）
L3 LCA 干预类型选择层       Bjork 四件套 + CLT（LCA 决策）
L2 状态估计层（CTA）        MIRT + CD-CAT（含 TC + Misconception 标注）
L1 时间演化层（CTA）        BKT/DKT + Spaced Repetition
L0 概率框架层（CTA）        POMDP / HMM
L0.5 内容基础层             Threshold Concepts + Misconceptions 库  ← v0.5.0 新增
```

## 关键引用来源

- **Threshold Concepts**：Meyer & Land (2003, 2006). *Threshold Concepts and Troublesome Knowledge*. In *Improving Student Learning*.
- **Liminality**：Land, Cousin, Meyer & Davies (2005). *Threshold concepts and troublesome knowledge*.
- **Misconceptions Research**：Driver, Guesne & Tiberghien (1985). *Children's Ideas in Science*. Open University Press.
- **Ontological Misconceptions**：Chi (1992). *Conceptual change within and across ontological categories*. Cognitive Science.

## 关联文档

- [README.md](../../README.md) — ECOS 项目入口
- [CHANGELOG.md](../../CHANGELOG.md) — 变更日志（v0.5.0，P0 全部完成）
- [research/30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md](../../research/30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md) — P0 第 1 份
- [research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md](../../research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md) — P0 第 2 份
- [research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md](../../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md) — P0 第 3 份（本产出）
- [v2.0 深度研究 §3.3 CTA — State Estimator](../../research/deep-research/Cognitive-Digital-Twin-Deep-Research.md) — 本文档填补的 gap

## 下一步

P0 三件套完成后，回到战略层：
- **P0**：`02-architecture.md`（整体架构——整合 P0 三件套到 ECOS 架构）
- **P0**：`03-roadmap.md`（阶段划分）
- **P0**：`04-risks.md`（风险矩阵）

战略层完成后，进入工程层（`10-engineering/`）和教学法层（`20-pedagogy/`）。

---

**创建日期**：2026-06-24
**维护者**：Bisen & Claude
**版本**：v0.5.0（P0 三件套全部完成）
