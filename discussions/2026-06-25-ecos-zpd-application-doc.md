# 2026-06-25 · ZPD 应用教学法文档（v0.18.0，**教学法层 100% 完成**）

## 主题

完成教学法层最后 1 份文档 `research/20-pedagogy/04-zpd-application.md`（v1.0，780 行），把 Vygotsky ZPD 理论形式化到 ECOS 系统中。

**🎉 教学法层 4 份全部完成**

## 日期

2026-06-25

## 背景

教学法层最后 1 份——基于：
- Vygotsky 1978 最近发展区理论
- [01-k12-cognitive-structure.md](01-k12-cognitive-structure.md)（学段差异）
- [02-bloom-application.md](02-bloom-application.md)（Bloom 跨层级）
- [03-learning-strategies.md](03-learning-strategies.md)（学习策略）
- [v0.4.0 §3.1 CA Scaffolding 衰减](../../research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md)
- [v0.5.0 C 维度内容库（TC + Misconception）](../../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md)

## 文档结构（12 章节）

| 章节 | 内容 |
|---|---|
| §0 | ZPD 核心思想（ADL + ZPD + PDL）+ 与其他教学法理论关系 |
| §1 | ZPD 在 CTA 状态估计中的形式化（ADL/PDL/ZPD 边界 + 实时更新）|
| §2 | ZPD 在 LCA 干预选择中的应用（任务选择 + 难度选择 + Scaffolding）|
| §3 | ZPD 突破检测（信号 + 归因 + 可视化）|
| §4 | ZPD × Bloom 层级结合（L4 ZPD 最宽，核心难点）|
| §5 | ZPD 在不同学段的差异（小学窄 / 初中中 / 高中宽）|
| §6 | ZPD 与学习障碍识别（4 级诊断流程）|
| §7 | ZPD 与 TC / Misconception 库的关联 |
| §8 | 可视化与家长/教师沟通 |
| §9 | 评估指标 |
| §10-12 | 教学法层完成 + 关联文档 + 版本维护 |

## 核心内容

### 1. ZPD 三层结构

```
实际发展区 (ADL)          ZPD (教学目标)         潜在发展区 (PDL)
─────────────────────────────────────────────────────→
已掌握任务                                       在帮助下能完成
        ↑               ↑                ↑
    太简单           教学应聚焦        太难
```

### 2. ZPD 边界计算

```python
zpd_lower = adl + 0.05      # ZPD 下界
zpd_upper = pdl - 0.05      # ZPD 上界
recommended_difficulty = (zpd_lower + zpd_upper) / 2
```

### 3. 学段差异

| 学段 | ZPD 宽度 | 突破频率 | 评估频率 |
|---|---|---|---|
| 小学 | 0.05-0.10（窄）| 每月 0.5-1 次 | 每周 |
| 初中 | 0.10-0.15（中）| 每月 1-3 次 | 月度 |
| 高中 | 0.15-0.25（宽）| 每月 3-5 次 | 季度 |

### 4. L4 Analyze ZPD 宽度最大（0.15-0.20）

**核心洞察**：L4 Analyze 是中国学生最难突破的层级，ZPD 宽度最大——应给予最多教学资源。

### 5. 4 级诊断流程（学习障碍识别）

```
Level 1：暂时困难？（< 4 周）→ 等待恢复
Level 2：misconception？ → 调整干预
Level 3：策略不当？ → 调整策略
Level 4：学习障碍？（> 12 周 + 多学科） → 人工审核 + 专业评估
```

### 6. TC 跨越 = ZPD 突破的极端案例

- TC 跨越前：ZPD [ADL, TC_后_能力]
- TC 跨越成功：ADL 永久改变（不可逆）
- BloomProfile 自动 +0.1（[03-bloom-goal-library.md §8.1](../research/10-engineering/03-bloom-goal-library.md)）

### 7. Misconception 与 ZPD 收缩

- 伪置信 → ADL 拉高 → ZPD 边界错误
- LCA 推荐过难 → 反复失败 → ZPD 收缩
- ECOS 联动：[v0.5.0 §3](../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md) 集成 → C × 0.7 → ZPD 重算

## 关键决策

| 决策 | MVP 选择 |
|---|---|
| ZPD 三层结构 | ADL + ZPD + PDL（Vygotsky 标准）|
| 边界计算 | 下界 = ADL + 0.05；上界 = PDL - 0.05 |
| 实时更新 | 每次 CTA 状态更新后 |
| Scaffolding 衰减 | 与 CA Stage 3 整合 |
| 突破归因 | 与 CTA L4 Causal Inference 整合 |
| TC 与 ZPD | TC 跨越 = ZPD 突破极端案例（不可逆）|
| Misconception 与 ZPD | 伪置信 → ZPD 收缩（联动机制）|

## **教学法层 100% 完成** 🎉

| 文件 | 版本 | 行数 | 主题 |
|---|---|---|---|
| 01-k12-cognitive-structure.md | v0.15.0 | 516 | K12 学段差异化 |
| 02-bloom-application.md | v0.16.0 | 564 | Bloom 跨层级策略 |
| 03-learning-strategies.md | v0.17.0 | 575 | 学习策略空间 |
| 04-zpd-application.md | v0.18.0 | 780 | ZPD 在 ECOS |
| **总计** | — | **2435 行** | **教学法层 100%** |

## Phase 0 进度

| 维度 | 状态 | 完成度 |
|---|---|---|
| 战略层 | ✅ 100% | 4/4 |
| 工程层 | ✅ 100% | 5/5 |
| **教学法层** | **✅ 100%** | **4/4** |
| MVP 设计 | ⏳ 0% | 0/1 |
| **总完成度** | **~99%** | **14/14**（剩 MVP 1 份）|

## 累计产出（v0.1.0 ~ v0.18.0）

- **18 个版本**
- **~18000 行**研究文档（远超 Phase 0 完成标准 5000 行）

## 产出文件

| 文件 | 角色 | 行数 |
|---|---|---|
| `research/20-pedagogy/04-zpd-application.md` | **主文档**——ZPD 应用（v1.0，12 章节）| 780 |
| `discussions/2026-06-25-ecos-zpd-application-doc.md` | **本文件**——本次会话简要记录 | ~140 |
| `CHANGELOG.md` | 升级到 v0.18.0 | — |

## 关联文档

- [README.md](../../README.md) — ECOS 项目入口
- [CHANGELOG.md](../../CHANGELOG.md) — 变更日志（v0.18.0）
- [research/20-pedagogy/04-zpd-application.md](../../research/20-pedagogy/04-zpd-application.md) — 本次主产出
- [research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md](../../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md) — v0.5.0 TC + Misconception

## 下一步

教学法层全部完成，Phase 0 剩 1 份：
- **MVP 设计**（`90-mvp/README.md`）—— 整合战略层 + 工程层 + 教学法层的 M2-M3 详细设计

完成 MVP 设计后，Phase 0 100% 完成，可启动 Phase 4（MVP 实施）。

---

**创建日期**：2026-06-25
**维护者**：Bisen & Claude
**版本**：v0.18.0（**教学法层 100% 完成**）
