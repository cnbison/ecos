# MVP 实施（MVP Design）

> **版本**：v1.0（2026-06-25）
> **性质**：ECOS Phase 0 最后 1 份文档（**Phase 0 收官**）——M2-M3 详细设计与 H1-H4 假设验证
> **基于**：[01-applications.md §7 MVP 范围](../research/00-overview/01-applications.md)、[02-architecture.md §8 MVP 架构](../research/00-overview/02-architecture.md)、[03-roadmap.md §2 M2-M3 里程碑](../research/00-overview/03-roadmap.md)、[04-risks.md 18 类风险矩阵](../research/00-overview/04-risks.md)、工程层 5 份文档、教学法层 4 份文档、P0 三件套借鉴
> **关系**：战略层 + 工程层 + 教学法层 → MVP 实施
> **后续**：Phase 0 100% 完成 → 启动 Phase 4（M2 工程实现 + M3 实验分析）
> **维护者**：Bisen & Claude

---

## 0. 模块定位

### 0.1 文档作用

**MVP 设计**是 ECOS Phase 0 的**收官文档**——整合战略层 + 工程层 + 教学法层所有设计，定义：

1. **MVP 范围**：做什么 / 不做什么（与 [01-applications.md §6 不做清单](../research/00-overview/01-applications.md) 一致）
2. **详细 Week-by-Week 任务分解**：M2 工程实现（4-6 周）+ M3 实验分析（2-4 周）
3. **数据采集方案**：50-100 学生的合作学校招募
4. **CTA / LCA / 双 Agent / 持久化的工程集成**
5. **实验设计与 4 个核心假设验证**（H1-H4）
6. **风险与缓解**（精简 5 类关键风险）

### 0.2 Phase 0 收官意义

完成本文档后，Phase 0 完成度达到 **100%**：

```
✅ 战略层    100% (4/4)
✅ 工程层    100% (5/5)
✅ 教学法层  100% (4/4)
✅ MVP 设计  100% (1/1)  ★ 当前
─────────────────────────────────────
Phase 0 100% 完成 🎉
可以启动 Phase 4（MVP 实施）
```

### 0.3 与 [03-roadmap.md §2 M2-M3](../research/00-overview/03-roadmap.md) 的关系

[03-roadmap.md](../research/00-overview/03-roadmap.md) 给出 8 个里程碑（M0-M7）+ 时间线 + 假设验证——本文档聚焦 **M2-M3**（MVP 工程实现 + 实验分析），不重复 M4-M7。

---

## 1. MVP 总览

### 1.1 MVP 范围（4-8 周）

[01-applications.md §7 MVP 范围](../research/00-overview/01-applications.md) + [02-architecture.md §8 MVP 架构](../research/00-overview/02-architecture.md)：

| 维度 | MVP 范围 |
|---|---|
| **学科** | 初中数学（代数 + 几何） |
| **年级** | 初一 + 初二（部分） |
| **学生规模** | 50-100 学生（1 个实验班 + 1-2 个对照班） |
| **时长** | 4-8 周（v0.3.0 修正：原 v2.0 估计 2-4 周不切实际）|
| **场景** | A 学科诊断 + B 自适应干预 + C 成长轨迹（学期内）|
| **教师端** | 不实现（MVP 仅学生端） |
| **家长端** | 不实现（MVP 仅学生端） |
| **跨学科** | 不实现（MVP 仅数学）|
| **跨学期** | 不实现（MVP 仅学期内）|

### 1.2 时间规划（修正版）

[03-roadmap.md §2.2 M2 里程碑](../research/00-overview/03-roadmap.md) 已修正 v2.0 的 2-4 周 → **4-8 周**：

```
W1-W2（工程实现前 2 周）
├── CTA 基础（BKT + MIRT 5D）
├── LCA 基础（Contextual Bandits）
├── Bloom 库（数学 8 知识点 × 4 层 = 32 条）
└── 双 Agent 互校循环

W3-W4（系统集成）
├── 持久化 + 会话管理
├── UI（MVP 学生端）
├── LLM Critic 集成（感知 + 解释 + Misconception 检测）
└── 端到端集成测试

W5-W6（内部测试）
├── 教师协作（Q 矩阵 + TC + Misconception 库审核）
├── 学生招募（合作学校）
└── Beta 测试（10-20 学生）

W7-W8（MVP 实验）
├── 正式实验（50-100 学生）
├── 4 个假设验证（H1-H4）
└── 实验报告
```

### 1.3 团队配置（最小）

[03-roadmap.md §6.1 团队配置](../research/00-overview/03-roadmap.md)：

| 角色 | 人数 | 职责 |
|---|---|---|
| 算法工程师 | 1 | CTA + LCA + 双 Agent 互校 |
| 后端工程师 | 1 | 持久化 + API + LLM 集成 |
| 前端工程师 | 1 | UI（学生端 + 简化的教师后台）|
| 教研员 | 0.5 | Q 矩阵 + TC + Misconception 库 |
| **总计** | **3.5 FTE** | 8 周 MVP |

### 1.4 资源需求

| 资源 | 数量 | 备注 |
|---|---|---|
| LLM API 预算 | 5-10 万 | 50-100 学生 × 30 次/天 × 4 周 × ~1 元/次 ≈ 6000-12000 元 |
| 服务器 | 5-10 万 | SQLite 主 + Redis 缓存 + LLM API |
| 教师协作 | 5-10 万 | 教研员 0.5 FTE × 4 周 |
| 学生奖励 | 1-2 万 | 50-100 学生 × 200 元/人 |
| **总计** | **~16-32 万** | MVP 阶段 |

---

## 2. 详细 Week-by-Week 任务分解

### 2.1 Week 1-2：核心模块实现

#### Week 1：CTA + LCA 基础

| 任务 | 产出 | 依赖 |
|---|---|---|
| CTA BKT 实现（4 参数）| `ecos/cta/l1_evolution/bkt.py` | [v0.3.0 §3 BKT](../../research/30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md) |
| CTA MIRT 5D 实现 | `ecos/cta/l2_mirt/mirt_5d.py` | [v0.3.0 §1 MIRT](../../research/30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md) |
| CTA POMDP 框架（EKF）| `ecos/cta/l0_pomdp/pomdp.py` | [v0.3.0 §4 POMDP](../../research/30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md) |
| LCA Contextual Bandits (LinUCB) | `ecos/lca/l4_optimization/contextual_bandit.py` | [02-lca-policy-engine.md §4.2](../research/10-engineering/02-lca-policy-engine.md) |
| **单元测试** | CTA/LCA 测试覆盖率 ≥ 80% | — |

#### Week 2：Bloom 库 + 互校

| 任务 | 产出 | 依赖 |
|---|---|---|
| Bloom Goal Library（数学 32 条）| `ecos/bloom/subject_libraries/math.py` | [03-bloom-goal-library.md §3](../research/10-engineering/03-bloom-goal-library.md) |
| TC 库（8 个初中数学）| `ecos/cta/content/threshold_concepts.py` | [v0.5.0 §1.7](../../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md) |
| Misconceptions 库（30-50 条）| `ecos/cta/content/misconceptions.py` | [v0.5.0 §2.6](../../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md) |
| 双 Agent 互校循环 | `ecos/dual_agent/orchestrator.py` | [04-dual-agent-calibration.md §6](../research/10-engineering/04-dual-agent-calibration.md) |
| LLM Critic（感知层 + 解释层）| `ecos/cta/llm_critic/` | [v0.3.0 §6.2 边界](../../research/30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md) |

### 2.2 Week 3-4：系统集成 + UI

#### Week 3：持久化 + LLM 集成

| 任务 | 产出 | 依赖 |
|---|---|---|
| SQLite 持久化（4 张核心表）| `ecos/persistence/db.py` | [05-persistence-session.md §2](../research/10-engineering/05-persistence-session.md) |
| ECOSSession 跨会话继承 | `ecos/session/ecos_session.py` | [05-persistence-session.md §4](../research/10-engineering/05-persistence-session.md) |
| chunk 隔离（崩溃恢复）| `ecos/session/chunk_isolation.py` | [05-persistence-session.md §5](../research/10-engineering/05-persistence-session.md) |
| LLM Critic 完整集成 | `ecos/cta/llm_critic/`（3 类 prompt）| [v0.3.0 §6.2](../../research/30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md) |
| 双 Agent 互校 + L4 因果归因 | `ecos/dual_agent/anti_hallucination/` | [04-dual-agent-calibration.md §4](../research/10-engineering/04-dual-agent-calibration.md) |

#### Week 4：UI + 端到端集成

| 任务 | 产出 | 依赖 |
|---|---|---|
| MVP 学生端 UI（做题 + 干预展示）| `web/student/` | — |
| 简化教师后台（班级数据查看）| `web/teacher/` | — |
| 端到端集成测试 | `tests/e2e/` | — |
| 性能基准测试 | `tests/performance/` | — |

### 2.3 Week 5-6：内部测试 + Beta

#### Week 5：教师协作 + 招募

| 任务 | 产出 | 依赖 |
|---|---|---|
| Q 矩阵构建（与教师协作）| `data/q_matrix.json` | [03-bloom-goal-library.md §3.3](../research/10-engineering/03-bloom-goal-library.md) |
| TC + Misconceptions 库教师审核 | 教师签字确认 | [v0.5.0 §1.7 / §2.6](../../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md) |
| 合作学校招募 | 1 所学校（50-100 学生）| — |
| 学生家长同意书 | 100 份签字 | [04-risks.md §D1 缓解策略](../research/00-overview/04-risks.md) |

#### Week 6：Beta 测试

| 任务 | 产出 |
|---|---|
| Beta 测试（10-20 学生）| 系统稳定性 + 用户体验报告 |
| 题目库完整性检查 | 100-200 道初中数学题 |
| 数据质量初步评估 | 数据采集完整性 ≥ 80% |

### 2.4 Week 7-8：正式实验 + 评估

#### Week 7：正式实验

| 任务 | 产出 |
|---|---|
| 50-100 学生使用 MVP 系统 | 实验数据 |
| 4 个对照组实验设计 | 数据准备 |
| 每日监控 + 异常处理 | 稳定性报告 |

#### Week 8：评估 + 报告

| 任务 | 产出 |
|---|---|
| 4 个核心假设验证（H1-H4）| 验证结果 |
| 实验报告 | MVP 实验报告 |
| 下一阶段建议 | Phase 5 启动建议 |

---

## 3. 数据采集方案

### 3.1 合作学校招募

**目标**：1 所初中（50-100 学生，1 个实验班 + 1-2 个对照班）。

**合作学校要求**：
- 愿意配合 4-8 周实验
- 数学教师有时间参与 Q 矩阵 + TC + Misconceptions 库审核
- 学校有基本的计算机设备（学生端 UI）
- 家长愿意签署同意书（[04-risks.md §D1](../research/00-overview/04-risks.md) 强制要求）

**招募渠道**：
- 教育部门合作
- 师范院校附属学校
- 私人联系

### 3.2 学生招募

**学生要求**：
- 初一或初二（与 MVP 学科匹配）
- 数学成绩分布均匀（不只挑优等生）
- 家长签署同意书

**激励**：
- 现金奖励（200 元/人）
- 学习报告（家长可见）
- 优秀学生证书

### 3.3 数据范围

**采集的数据**（最小化原则）：
- ✅ 做题记录（题号 + 作答 + 答题时间）
- ✅ 解释文本（学生口述思路）
- ✅ 反思日志（每日 1 次）
- ✅ 学习状态（BloomProfile 评估）
- ❌ 姓名（仅学生 ID + 匿名化）
- ❌ 学校（仅学校 ID）
- ❌ 家庭信息
- ❌ 设备 ID / IP 地址（[05-persistence-session.md §7.4 NEVER_COLLECT](../research/10-engineering/05-persistence-session.md)）

### 3.4 隐私合规

[04-risks.md §D1 未成年人数据合规](../research/00-overview/04-risks.md) + [05-persistence-session.md §7 隐私保护](../research/10-engineering/05-persistence-session.md)：

- 家长/监护人书面同意书（强制）
- 最小化数据采集（仅必要）
- 数据本地化（服务器在中国境内）
- 端侧计算（敏感数据）
- 差分隐私（聚合数据）
- 加密存储（5D + BloomProfile + LearningDNA）
- 第三方合规审计（每年）

---

## 4. CTA 状态估计工程实现（MVP 范围）

[01-cta-belief-engine.md](../research/10-engineering/01-cta-belief-engine.md) 详细定义。

### 4.1 5D 状态估计（MVP）

| 5D 维度 | MVP 实现 | 数据来源 |
|---|---|---|
| **K（知识）** | BKT 经典 4 参数 | 作答对错（自动）|
| **P（程序）** | BKT（按解题步骤）| 作答步骤（自动 + LLM rubric）|
| **S（策略）** | MIRT 5D 联合估计 | 整体表现（自动）|
| **C（置信度）** | BKT + Misconception 折扣 | 解释文本（LLM Critic）|
| **X（外部支架）** | 简化（MVP 暂估 0）| 不采集 X 数据 |

### 4.2 BloomProfile 估计

| Bloom 层 | MVP 评估方法 |
|---|---|
| **L1 Remember** | 公式记忆题（自动）|
| **L2 Understand** | 解释题（LLM rubric）|
| **L3 Apply** | 应用题（自动）|
| **L4 Analyze** | 拆解题（LLM rubric）|
| **L5-L6** | 不评估（MVP 仅初中 K12）|

### 4.3 C 维度内容库集成

- **TC 库**：8 个初中数学 TC（[v0.5.0 §1.7](../../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md)）
- **Misconceptions 库**：30-50 条（[v0.5.0 §2.6](../../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md)）
- **LLM Critic Misconception 检测**：F1 ≥ 0.7

### 4.4 LLM Critic 集成

[01-cta-belief-engine.md §9](../research/10-engineering/01-cta-belief-engine.md)：
- 感知层（自然语言 → 结构化）
- 解释层（统计值 → 自然语言）
- Misconception 检测

**温度**：0.2（结构化输出稳定）

---

## 5. LCA 干预选择工程实现（MVP 范围）

[02-lca-policy-engine.md](../research/10-engineering/02-lca-policy-engine.md) 详细定义。

### 5.1 5 类干预（MVP）

| 干预类型 | MVP 实现 | 适用 Bloom |
|---|---|---|
| **EXPLANATORY** | 类比 + worked example | L2-L3 |
| **PRACTICE** | 变式练习 + FSRS | L1-L3 |
| **INQUIRY** | 探究型（简化）| L3-L4 |
| **FEEDBACK** | 即时反馈 + rationale | L1-L4 |
| **METACOGNITIVE** | Articulation 简化 | L4 |

### 5.2 Bloom 目标选择

[03-bloom-goal-library.md §7 next_target 算法](../research/10-engineering/03-bloom-goal-library.md)：
- 默认：当前层 + 1
- L5/L6 不推荐（MVP 仅初中 K12）

### 5.3 Contextual Bandits (LinUCB)

[02-lca-policy-engine.md §4.2](../research/10-engineering/02-lca-policy-engine.md)：
- Context：5D + BloomProfile + LearningDNA = 16 维
- Arm：Intervention(type × bloom_target × difficulty × ...)
- Reward：state_delta（CTA 测量的状态变化）
- 算法：LinUCB（探索-利用平衡 α=1.0）

### 5.4 ZPD 集成

[04-zpd-application.md §2](../research/20-pedagogy/04-zpd-application.md)：
- 任务难度在 ZPD 内比例 ≥ 80%
- Scaffolding 衰减（与 CA Stage 3 整合）

---

## 6. 双 Agent 互校（MVP 范围）

[04-dual-agent-calibration.md](../research/10-engineering/04-dual-agent-calibration.md) 详细定义。

### 6.1 MVP 互校范围

- **常态循环**：自动执行（6 步骤）
- **信念质疑**：自动触发（实验不符时）
- **策略质疑**：自动触发（连续 5 次干预无效）
- **元反思**：手动触发（实验结束时）
- **人工审核**：置信度 < 0.6 触发

### 6.2 4 个交互模式（MVP）

| 模式 | 触发条件 | MVP 处理 |
|---|---|---|
| 常态循环 | 新观测 | ✅ 自动 |
| 信念质疑 | CTA 高置信 + 学生表现差 | ✅ 自动 |
| 策略质疑 | 连续 5 次无效 | ✅ 自动 |
| 元反思 | 4 周停滞 + 班级整体 | ⚠️ 手动 |

### 6.3 抗幻觉 3 机制

[04-dual-agent-calibration.md §4](../research/10-engineering/04-dual-agent-calibration.md)：
1. CTA 信念分布检查
2. LCA 实验设计验证
3. L4 因果归因强制

### 6.4 性能预算

| 操作 | MVP 性能预算 |
|---|---|
| 一次互校循环 | ≤ 10 秒 |
| CTA 输出 | ≤ 3 秒 |
| LCA 选择 | ≤ 3 秒 |
| LLM 调用（rationale）| ≤ 3 秒 |
| 总延迟 P95 | ≤ 10 秒 |

---

## 7. 实验设计与对照组

### 7.1 4 个核心假设（H1-H4）

[03-roadmap.md §2.3 H1-H3](../research/00-overview/03-roadmap.md) 已定义 H1-H3。MVP 增加 **H4**：

| 假设 | 内容 | 验证阈值 | 统计方法 |
|---|---|---|---|
| **H1** | CTA 5D 状态预测力 ≥ 传统 IRT/BKT | AUC ≥ 0.75（vs IRT baseline 0.65）| 受试者工作特征曲线 |
| **H2** | Bloom 6 层在初中数学可行 | 6 层方差解释 ≥ 60% | 探索性因子分析 |
| **H3** | 双 Agent 互校抗幻觉 | 双 Agent ECE ≤ 0.10 | 期望校准误差 |
| **H4** | CTA/LCA 分工有效 | 分工组元认知提升 ≥ 0.2 | 双盲对照实验 |

### 7.2 对照组设计

| 组别 | 学生数 | 处理 | 目的 |
|---|---|---|---|
| **实验组（ECOS 完整）** | 30 | CTA + LCA + 双 Agent 互校 | H1 + H2 + H3 + H4 |
| **对照 1（仅 CTA）** | 30 | CTA 状态估计 + LLM 直接干预 | H4（验证 LCA 必要性）|
| **对照 2（传统教学）** | 30 | 现行教学（无 ECOS）| H1 + H2（baseline）|
| **总计** | **90** | — | — |

**统计方法**：
- 单因素方差分析（ANOVA）比较 3 组
- 后验检验（Tukey HSD）找出差异组
- 显著性水平 α = 0.05

### 7.3 数据分析

| 数据类型 | 分析方法 |
|---|---|
| CTA 状态估计 | AUC + 校准曲线 |
| BloomProfile | EFA（探索性因子分析）|
| 双 Agent 互校 | ECE + 决策一致性 |
| 学习效果 | t-test + Cohen's d 效应量 |
| 用户体验 | NPS + 定性访谈 |

---

## 8. 评估指标与成功标准

### 8.1 H1-H4 验证阈值

| 假设 | 阈值 | 通过条件 |
|---|---|---|
| H1 | AUC ≥ 0.75 | CTA 显著优于 IRT baseline（p < 0.05）|
| H2 | 方差解释 ≥ 60% | BloomProfile 6 层结构成立 |
| H3 | ECE ≤ 0.10 | 双 Agent 校准显著优于单 Agent |
| H4 | 元认知提升 ≥ 0.2 | 实验组显著优于对照 1（p < 0.05）|

### 8.2 性能基准

[01-cta-belief-engine.md §11.3](../research/10-engineering/01-cta-belief-engine.md)：

| 指标 | 阈值 |
|---|---|
| CTA 5D 预测 AUC | ≥ 0.75 |
| Misconception 检测 F1 | ≥ 0.7 |
| TC 跨越检测 F1 | ≥ 0.6 |
| **ECE（双 Agent 校准度）** | **≤ 0.10** |
| 互校循环延迟 P95 | ≤ 5 秒 |
| LLM API 成本 | ≤ 50 次/学生/天 |

### 8.3 用户体验指标

| 指标 | 阈值 |
|---|---|
| 7 日留存率 | ≥ 60% |
| 30 日留存率 | ≥ 40% |
| NPS | ≥ 30 |
| 教师 rationale 满意度 | ≥ 4/5 |
| 家长接受率 | ≥ 70% |

---

## 9. 风险与缓解（精简版）

[04-risks.md 18 类风险矩阵](../research/00-overview/04-risks.md) 是完整版本。本节聚焦 MVP 阶段的 **5 类关键风险**：

### 9.1 技术风险

#### A2 CTA 5D 预测精度不足 🔴（对应 H1）

- **影响**：H1 失败 → M3 回溯
- **缓解**：
  - 增量训练（从 50 学生开始）
  - 维度可降级（5D → 3D）
  - 人工审核 + 教师签字

#### A4 双 Agent 互校抗幻觉 🔴（对应 H3）

- **影响**：H3 失败 → M3 回溯
- **缓解**：
  - 数学层 L0-L2 绝不用 LLM（硬底线）
  - LLM Critic 边界（仅感知 + 解释 + Misconception）
  - 因果归因强制（[04-dual-agent-calibration.md §4.3](../research/10-engineering/04-dual-agent-calibration.md)）

### 9.2 产品风险

#### B1 Bloom 6 层不适用 K12 🟡（对应 H2）

- **影响**：H2 失败 → M3 回溯
- **缓解**：
  - MVP 用 L1-L4（不实现 L5-L6）
  - 学科适配（仅数学）
  - 教师验证

### 9.3 法律风险

#### D1 未成年人数据合规 🔴

- **影响**：法律风险（罚款 + 业务暂停）
- **缓解**：
  - 家长书面同意书（强制）
  - 最小化数据采集
  - 数据本地化 + 加密 + 差分隐私
  - 第三方合规审计（每年）

### 9.4 教育专业风险

#### C1 教师协作时间成本 🟡

- **影响**：Q 矩阵 + TC + Misconceptions 库延期
- **缓解**：
  - 分阶段协作（W5 仅审核）
  - 协作工具（CTA 自动建议 Q 矩阵）
  - 报酬机制（200-500 元/单元）

---

## 10. Phase 0 收官 + Phase 4 启动

### 10.1 Phase 0 完成清单

| 类别 | 文档数 | 状态 |
|---|---|---|
| 战略层 00-overview/ | 4 份 | ✅ 100% |
| 工程层 10-engineering/ | 5 份 | ✅ 100% |
| 教学法层 20-pedagogy/ | 4 份 | ✅ 100% |
| MVP 设计 90-mvp/ | 1 份 | ✅ 100% |
| P0 借鉴 theoretical-foundations/ | 4 份 + 1 README | ✅ 100% |
| 项目级 + 讨论记录 | 32+ 份 | ✅ |
| **总计** | **~56+ 份** | **~19000+ 行** |

### 10.2 Phase 4 启动清单

完成 MVP 设计后，进入 Phase 4（MVP 实施）：

- [ ] 团队组建（3.5 FTE）
- [ ] 合作学校招募
- [ ] LLM API 预算（5-10 万）
- [ ] 教师协作启动（Q 矩阵 + TC + Misconceptions 库审核）
- [ ] Week 1-8 按计划执行（[§2](#2-详细-week-by-week-任务分解)）
- [ ] H1-H4 假设验证（[§7](#7-实验设计与对照组)）
- [ ] MVP 实验报告

### 10.3 Phase 5 启动条件

基于 H1-H4 验证结果：

| 假设通过 | Phase 5 启动 |
|---|---|
| H1 + H2 + H3 + H4 全部通过 | 启动 M4-M5（学科扩展 + 商业模式）|
| 仅 H3 失败 | 强化 LLM Critic 边界，降低 LLM 介入深度 |
| 仅 H1 失败 | 简化为 3D 状态 + 重组 Bloom |
| 多假设失败 | 回溯 M2 重新设计 |

---

## 11. 关联文档

### 11.1 上层文档

- [01-applications.md](../research/00-overview/01-applications.md) — 4 大核心应用场景 + 9 项不做边界 + MVP 范围
- [02-architecture.md](../research/00-overview/02-architecture.md) — ECOS 整体架构 + MVP 架构
- [03-roadmap.md](../research/00-overview/03-roadmap.md) — M0-M7 共 8 个里程碑 + H1-H7 假设
- [04-risks.md](../research/00-overview/04-risks.md) — 18 类风险矩阵

### 11.2 工程层（按 MVP 集成顺序）

- [01-cta-belief-engine.md](../research/10-engineering/01-cta-belief-engine.md) — CTA 引擎
- [02-lca-policy-engine.md](../research/10-engineering/02-lca-policy-engine.md) — LCA 引擎
- [03-bloom-goal-library.md](../research/10-engineering/03-bloom-goal-library.md) — Bloom 库
- [04-dual-agent-calibration.md](../research/10-engineering/04-dual-agent-calibration.md) — 双 Agent 互校
- [05-persistence-session.md](../research/10-engineering/05-persistence-session.md) — 持久化

### 11.3 教学法层

- [01-k12-cognitive-structure.md](../research/20-pedagogy/01-k12-cognitive-structure.md) — K12 学段差异化
- [02-bloom-application.md](../research/20-pedagogy/02-bloom-application.md) — Bloom 跨层级
- [03-learning-strategies.md](../research/20-pedagogy/03-learning-strategies.md) — 学习策略空间
- [04-zpd-application.md](../research/20-pedagogy/04-zpd-application.md) — ZPD 在 ECOS

### 11.4 P0 三件套（理论借鉴）

- [v0.3.0 CTA 数学基础](../../research/30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md) — 5 层数学栈
- [v0.4.0 LCA 教学法基础](../../research/30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md) — 3 大理论群
- [v0.5.0 C 维度内容库](../../research/30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md) — TC + Misconceptions

### 11.5 核心论证

- [v2.0 §执行摘要 产品化路径](../../research/deep-research/Cognitive-Digital-Twin-Deep-Research.md) — MVP 时间估计基础
- [v0.1 综合报告 §第一/二/三部分](../research/gpt-dialogues/04-cognitive-digital-twin-v01-report.md) — 12 章原始论证

### 11.6 项目级文档

- [README.md](../../README.md) — ECOS 项目入口
- [CLAUDE.md](../../CLAUDE.md) — Claude Code 协作指南
- [CHANGELOG.md](../../CHANGELOG.md) — 变更日志
- [MIGRATION-FROM-SELFLAB.md](../../research/MIGRATION-FROM-SELFLAB.md) — 项目迁移梳理

---

## 12. 版本与维护

- **v1.0**（2026-06-25）— 初版（**Phase 0 最后 1 份**）

**Phase 0 收官标志**：战略层 + 工程层 + 教学法层 + MVP 设计全部完成 ✅

**待办（影响本文档时同步更新）**：
- 当 Phase 4 实际执行时，回填 §2 Week-by-Week 实际进度
- 当 H1-H4 验证完成后，§10.3 决策树更新实际结果
- 当 Phase 5 启动时，本文档成为 Phase 5 启动依据

---

**创建日期**：2026-06-25
**维护者**：Bisen & Claude
