# ECOS 路线图（Roadmap）

> **版本**：v1.4（2026-07-22，加入 v0.40.0 → v0.53.1 实际进度盘点 + Phase 5 partial credit 必修 + 三大根本问题 + 6 项小漂移修复）
> **性质**：ECOS 战略层第 3 份文档，**基于架构定义 M0-M7 详细任务与阶段验证指标**
> **基于**：[01-applications.md](01-applications.md) §7 MVP 范围、[02-architecture.md](02-architecture.md) §8 MVP 架构、[v2.0 §执行摘要 产品化路径](../deep-research/Cognitive-Digital-Twin-Deep-Research.md)
> **后续**：[04-risks.md](04-risks.md)（风险矩阵）
> **v1.4 更新**：基于 [2026-07-22 项目全面审查报告](07-project-comprehensive-audit-2026-07-22.md) + [2026-07-21 lbc001 4 BUG 文档](../../discussions/2026-07-21-lbc001测试发现4个BUG分析与修复计划.md) + [2026-07-22 partial credit 文档](../../discussions/2026-07-22-partial-credit重大学术弊端发现.md) + [2026-07-22 Phase 5 Q 矩阵 CX 重新设计](../../discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md) + [2026-07-22 ECOS 端到端流程](../90-mvp/06-ecos-end-to-end-flow-analysis.md)。新增 §1.4 v0.40.0 → v0.53.1 实际进度盘点 / §3.4 Phase 5 启动条件 + 双目标 / §11 三大根本问题。
> **v1.3 更新**：基于 [2026-07-17 方向选择探讨](../../discussions/2026-07-17-方向选择-A先C后.md)，明确"先 A 后 C"商业化策略；§2.4 战略调整强化"先 C 端学习产品, B 端机构作为远期延伸"；§3.3 M5 商业模式 B2B 推迟；新增 §2.5 方向 B 混合架构落地路径
> **维护者**：Bisen & Claude

---

## 0. 路线图定位

### 0.1 与 v2.0 深度研究的关系

[v2.0 §执行摘要 产品化路径](../deep-research/Cognitive-Digital-Twin-Deep-Research.md) 已给出产品化路径：

| 阶段 | 时间 | 目标 |
|---|---|---|
| MVP | 2-4 周 | 初中数学 + 50-100 学生 |
| 产品化 | 2-3 月 | 完整 ECOS + 2 个学科 |
| 平台化 | 6-12 月 | K12 全学段 + 商业模式 |

**本文档的扩展**：
- 把 3 阶段细分为 **M0-M7 共 8 个里程碑**（每个 2-6 周）
- 基于 [02-architecture.md §8](02-architecture.md) 给出每个里程碑的具体工程任务
- 明确每个里程碑的**核心假设验证**（H1-H7）和**评估指标**
- **批判性修正**：MVP "2-4 周" 偏乐观——根据架构组件数量，建议 **4-8 周**

### 0.2 路线图原则

1. **里程碑驱动**：每个 M 必须有明确的"完成定义"（Definition of Done）
2. **假设验证导向**：每个 Phase 必须验证 1-3 个核心假设，失败可回溯
3. **数据资产累积**：从 MVP 开始累积学生画像数据——这是护城河
4. **小步快跑**：MVP 优先 1 个学科（MVP 数学）+ 1 个区域（华东/华北），不追求全国铺开
5. **真实场景验证**：Bisen 作为 lbc001 单用户手动测试，发现 4 BUG + 1 P0 弊端是黄金证据（2026-07-21/22）

### 0.3 阶段命名说明

为避免与 ECOS 项目分阶段混淆（CLAUDE.md 中 Phase 0/4/5/6 指**项目阶段**），本文档里程碑用 **M0-M7**（Milestone），与 v2.0 的 Phase 4/5/6 大致对应：

| Milestone | 对应 v2.0 Phase | 当前状态（v1.4 / 2026-07-22）|
|---|---|---|
| M0-M1 | Phase 0（理论奠基）| ✅ 已完成 2026-06-25 |
| M2-M3 | Phase 4（Product Demo 完整化）| ✅ **实际完成 v0.53.1**（Bisen 自定义 Phase 1-4 UI 路线 + CTA 实施）|
| M4-M5 | Phase 5（产品化）| 📋 **启动条件: lbc001 答 30+ 题 + Bisen 启动决策** |
| M6-M7 | Phase 6（系统完善）| 📋 远期 |

---

## 1. Phase 0 进度盘点（理论奠基）

### 1.1 已完成（v0.1.0 ~ v0.7.0）

| 版本 | 内容 | 行数 |
|---|---|---|
| **v0.1.0** | 项目初始建立 + 5 份核心研究文档迁移 + Python 包骨架 | — |
| **v0.2.0** | 战略层 §1 应用场景（10 章节，4 大场景 + 9 项不做边界）| 350 |
| **v0.3.0** | P0 §1 CTA 数学基础（5 层数学栈）| 451 |
| **v0.4.0** | P0 §2 LCA 教学法基础（3 大理论群）| 420 |
| **v0.5.0** | P0 §3 C 维度内容库（TC + Misconceptions 双轨）| 414 |
| **v0.6.0** | 理论借鉴路线图 SSOT（README.md）| 280 |
| **v0.7.0** | 战略层 §2 整体架构（11 章节，P0 三件套整合）| 703 |
| **小计** | **7 个版本，7 份主文档** | **~2600 行** |

### 1.2 Phase 0 完成定义（✅ 已完成 2026-06-25）

按战略层依赖链，Phase 0 在以下文件完成后即结束：

| 待完成 | 文件 | 依赖 | 状态 |
|---|---|---|---|
| **战略层 §3** | `03-roadmap.md`（本文件）| ✅ | ✅ v1.4 |
| **战略层 §4** | `04-risks.md` | 基于本文件 | ✅ v1.4 补 partial credit / 库 ID / LCA 未实施 |
| **战略层 §5** | `05-user-friendly-demo.md` | — | ✅ |
| **战略层 §6/§7** | `06/07-*.md` | — | 📋 v1.4 增 §7 审查报告 |
| **工程层 §1-5** | `10-engineering/` 全部 5 份 | 基于 02-architecture.md §5/6 | ✅ |
| **教学法层 §1-4** | `20-pedagogy/` 全部 4 份 | 基于 P0 三件套 | ✅ |

**Phase 0 完成标准**：
- ✅ 战略层 7 份全部完成（含审查报告）
- ✅ 工程层 5 份全部完成（CTA 信念引擎 + LCA 策略引擎 + Bloom 目标库 + 双 Agent 互校 + 持久化）
- ✅ 教学法层 4 份完成（K12 认知结构 + Bloom 应用 + 学习策略 + ZPD 应用）
- ✅ 总文档 ≥ 5000 行（实际 ~8000+ 行）

### 1.3 Phase 0 关键产出（核心）

| 维度 | 产出 |
|---|---|
| **架构** | 完整 ECOS 三层架构（顶层三空间 + 中层双 Agent + 底层内容库）|
| **数学基础** | CTA L0-L4 数学栈（POMDP + BKT + MIRT + CD-CAT + Causal Inference）|
| **教学法基础** | LCA L3-L4 教学法栈（CLT + Bjork 四件套 + Cognitive Apprenticeship）|
| **内容基础** | C 维度双轨（TC 8 个 + Misconceptions 30-50 条 MVP 候选）|
| **场景** | 4 大核心应用场景 + 9 项不做边界 + MVP 范围 |
| **风险** | 战略层 + 工程层 + 教学法层的核心风险（v1.4 增 partial credit / 库 ID / LCA 未实施）|

### 1.4 v0.40.0 → v0.53.1 实际进度盘点（v1.4 新增）

> **触发**：Bisen 2026-07-22 "项目进展到目前为止，是时候对整个项目所有文件以及开发过程，方向性决断等等信息进行细致而详尽的审查"
> **依据**：[07-project-comprehensive-audit-2026-07-22.md](07-project-comprehensive-audit-2026-07-22.md) 36.7 KB 全面审查报告

#### 1.4.1 累计产出（v0.40.0 → v0.53.1，10 天）

| 指标 | 数值 | 备注 |
|------|------|------|
| **Commit 数** | **124** | v0.40.0 → v0.53.1，10 天 |
| **Python 文件** | 78 | ecos/ + experiments/ + web/ |
| **Markdown 文件** | 113 | research/ + discussions/ + 项目级 |
| **JSON 文件** | 16 | 题库 / misconception 库 / 评测 / env 模板 |
| **lbc001 实际答题** | 27-29 道 | 19-20 正确，3 错，86% |

#### 1.4.2 7 组件当前状态（v0.53.1）

| 组件 | 状态 | 详情 |
|------|------|------|
| 5D + θ_cov | ✅ 真评估 | K/P/S 三维真评估, C/X 标"待启用"（Phase 5 重新设计）|
| Bloom 6 级 | ✅ 真评估 | L1-L6 累积, dominant_layer |
| TC 状态 | ✅ 真评估 | 5 topic × 3 阶段, post_liminal 不可逆 |
| Trajectory | ✅ 真评估 | 时间序列, 折叠面板, cap 500 |
| Misconceptions | ✅ 真评估 | M1-M8 Python 库, v0.52.0 修过库 ID 错配 |
| overall_confidence | ✅ 真评估 | `mean(5D conf)`, v0.48.1 改的 |
| LearningDNA | ⚠️ **标"待启用"** | lbc001 数据不足, 等 ≥50 题 + 交互行为数据 |

#### 1.4.3 Bisen 自定义 Phase 1-4 路线（UI 改进，v0.48.7-0.51.4）

| Phase | 内容 | 状态 | 版本 |
|---|---|---|---|
| 1 | 顶栏精简 / 题目合并 / 轨迹折叠 / 2 位小数 | ✅ | v0.48.7-0.49.0 |
| 2 | Tab 导航 (学习/轨迹/设置) + 答题历史 | ✅ | v0.49.1-0.49.2 |
| 3 | CSS 变量 / 进度条 8px / SVG 图标 / 5D 字母色 | ✅ | v0.50.0 + v0.51.3 |
| 4 | 拆文件 / API 封装 / URL hash 路由 / 错误恢复 | ✅ | v0.51.0-0.51.4 |
| 5 | 状态管理 (App 对象) | 📋 后续 | v0.52.0+ |

#### 1.4.4 端到端流程（2026-07-22 v0.52.3 文档化）

详见 [research/90-mvp/06-ecos-end-to-end-flow-analysis.md](../90-mvp/06-ecos-end-to-end-flow-analysis.md)（26.7 KB）。

**8 阶段闭环**：
1. Q 矩阵设计 → 2. 出题 → 3. 答题 → 4. AI 评判 → 5. 状态更新 → 6. 持久化 → 7. 干预 → 8. 个人画像

**5D 数值通俗化**：
- θ=能力估计，confidence=估计可信度，SE=不确定度，不是"对错率"
- dim.confidence = 1/(1+SE)（v0.48.0 改的，按各自 SE 分化）
- overall_confidence = mean(5D conf)（v0.48.1 改的）

**Bloom 数值通俗化**：
- L1-L6 = 记忆/理解/应用/分析/评价/创造
- dominant_layer = 最擅长层级

**TC 不可逆**：
- post_liminal 答错不回退（Meyer-Land 理论）

#### 1.4.5 11 项 P0 BUG 修复历史（v0.40.0 → v0.53.1）

| # | BUG | 修复版本 | 教训 |
|---|-----|----------|------|
| 1 | `ecos_version` 硬编码 | v0.47.0 | 读 `__version__` |
| 2 | `/api/question` race condition | v0.47.1 | start 入口加 `get_student_state()` 兜底 |
| 3 | dashboard 缺个人画像 | v0.47.2 | 加折叠面板 |
| 4 | `.report-*` CSS 误写 | v0.47.3 | 搬到 styles.css |
| 5 | MIRT K 暴跌 0.91 | v0.47.4 | DB 恢复时从 Q 矩阵重注册 item_params |
| 6 | 8 处 silent pass | v0.47.5 | 改 `logger.warning(exc_info=True)` |
| 7 | race condition 复发 | v0.47.7 | 再次加兜底 |
| 8 | dim.confidence 0% | v0.47.8 | 修置信度计算 |
| 9 | θ_cov 持久化 | v0.47.9 | 加 5x5 协方差矩阵字段 |
| 10 | 报告不更新 | v0.48.3 | 修 state diff 逻辑 |
| 11 | **misconception 库 ID 错配 + belief.py 末尾独立检测不写回** | **v0.52.0** | 传 `library_str` + 删独立检测 |

#### 1.4.6 5 次虚标模式归档（教训，CLAUDE.md §防御性自检规范 v0.47.6+）

| # | 虚标内容 | 触发 | 修复 |
|---|----------|------|------|
| 1 | v0.50.0 5D badge CSS class 名 | "5D 字母色不显示" | v0.51.3 |
| 2 | v0.50.0 LearningDNA 标"完整" | "LearningDNA 怎么没数据" | v0.52.0 标"待启用" |
| 3 | v0.51.0 URL hash 路由 | "刷新后跳到默认 tab" | v0.51.2 auto-start |
| 4 | v0.51.4 hardcoded 版本号 | "设置页版本号不对" | v0.51.4 动态拉 |
| 5 | v0.52.0 misconception 库 ID | "misco 怎么不触发" | v0.52.0 传 library_str |

详见 [CLAUDE.md §防御性自检规范](../../CLAUDE.md)。

---

## 2. Phase 4 / M2-M5（Product Demo 完整化）

### 2.1 目标

**验证 ECOS 核心假设**（H1-H3）：
- **H1**：CTA 5D 状态预测力 ≥ 传统 IRT/BKT（baseline 比较）
- **H2**：Bloom 目标空间在 Python 基础上可行（L1-L6 是否够用？）
- **H3**：双 Agent 互校有效减少 LLM 幻觉（实验对比：单 Agent vs 双 Agent 信念质量）

**Product Demo 范围**（v1.2 战略调整——完整产品形态）：
- **学科**：Python 基础（变量+循环+函数+递归+作用域）
- **用户**：自学者（Bisen 作为第一个真实用户）+ 跨领域 Demo 展示
- **核心交互**：做题 → LLM 评判对错 → AI 靶向干预
- **场景**：认知诊断 + 自适应干预 + 成长轨迹可视化
- **LLM 角色**：LLM 充当领域专家（评判答案 + 检测 misconception + 干预）
- **7 组件全展示**：5D+cov / 6级Bloom / TC状态 / LearningDNA / Trajectory / Misconceptions / overall_confidence

### 2.2 M2-M5 里程碑（Product Demo 完整化）

**时间**：8-12 周

**Definition of Done**：
- [x] `ecos/` Python 包可运行（CTA + LCA + 双 Agent 互校 + Bloom + Persistence + Session）
- [x] Python 基础 Q 矩阵覆盖 100-200 道题目（含 TC + Misconception 标注；LLM 充当领域专家）
- [x] Python 基础 TC 库 ≥ 8 个 + Misconceptions 库 ≥ 8 条
- [x] LLM Critic misconception 检测 F1 ≥ 0.7（在 100 个标注样本上）—— **部分通过**（v0.52.0 修库 ID 后 lbc001 1 条 M3 触发）
- [⚠️] CTA BKT/MIRT 单元测试覆盖率 ≥ 80% —— **未达**（无 pytest 套件，靠 lbc001 手动测试）
- [⚠️] LCA Contextual Bandits LinUCB 可运行 —— **未实施**（仅有脚手架）
- [x] SQLite 持久化 + 跨会话状态继承
- [x] MVP UI（学生端做题 + 干预 + 诊断报告）

**具体任务**：

| 周 | 任务 | 依赖 | 实际状态 |
|---|---|---|---|
| W1 | `ecos/cta/` 基础类实现（BKT + MIRT）| Phase 0 完成 | ✅ |
| W1 | `ecos/lca/` 基础类实现（Contextual Bandits）| Phase 0 完成 | ⚠️ 脚手架 |
| W2 | `ecos/bloom/` 目标库（Python 基础 Bloom L1-L4）| Phase 0 完成 | ✅ |
| W2 | `ecos/dual_agent/` 互校循环 | CTA + LCA | ⚠️ 占位 |
| W3 | `ecos/persistence/` SQLite + JSON 序列化 | CTA + LCA | ✅ |
| W3 | `ecos/session/` 跨会话状态继承 | Persistence | ✅ |
| W4 | LLM Critic 集成（Python 基础 misconception 检测）| C 维度库 | ✅（v0.52.0 修）|
| W4 | UI（MVP 学生端）| 后端 API | ✅ |
| W5 | Python 基础题目库 + Q 矩阵构建（LLM 充当领域专家）| — | ✅ |
| W5-W6 | 内部测试（开发团队）| 上述全部 | ✅（lbc001 27 题）|
| W6 | 自学者 Beta 测试 + 产品迭代 | — | 📋 Phase 5 |

**风险预警**：
- ⚠️ **Partial Credit 缺失**（v0.52.2 发现 P0 弊端，Phase 5 必修）—— 详见 §11.1
- ⚠️ **C/X 0 主导题**（v0.52.1 发现，5D 评估实际 3D）—— 详见 §11.2
- ⚠️ **MIRT 二元对错根本 trade-off**（v0.52.2 反思）—— 详见 §11.3

### 2.4 战略调整：从"等待学校"到"自我演示 + 跨领域泛化"（v1.1 新增）

> **触发背景**：Claude Skills Demo（2026-07-05）证明 ECOS 核心价值可在无真实学生的情况下验证。
> Bisen 扮演学生角色，3 轮跑完认知干预闭环，M1/M2 misconception 成功清除。

**原路径（串行阻塞）**：
```
W5: 教师协作 + 学校招募 → W6: Beta 测试
```
问题：学校招募未完成则 MVP 无法推进。

**新路径（并行验证）**：
```
W5: Q 矩阵模板 + Claude Skills Demo（✅ 已完成）
    ↓
W6+: Demo 深化（Claude Skills M3-M5 全清除 + Bloom L1→L4 路径验证）
    ↓
同时：学校招募 + 教师协作（不阻塞工程进度）
    ↓
W7+: 跨领域泛化（快速注入新领域，再次跑通闭环）
```

**新路径的工程价值**：
- ECOS 是**领域无关**的（`library_str` 注入任意 misconception 库）
- 无需等待真实学生，即可验证：CTA 状态追踪 + LCA 策略选择 + 干预效果
- Demo 报告可作为对外展示的核心材料（替代"干讲架构"）

**下一步工程任务（不依赖学校）**：
1. Claude Skills M3-M5 misconception 完整清除（当前仅 M1/M2 验证）
2. Bloom L1→L4 路径完整验证（4-gate 达标检测）
3. TC_skill 跨越验证（LLM 直接评估）
4. 跨领域 Demo（注入一个新的 misconception 库，如"批判性思维"或"编程初学者"）
5. Demo 完整报告（用于对外展示 ECOS 价值）

### 2.5 方向 B 混合架构落地路径（v1.3 新增）

> **决策来源**：[2026-07-10 诊断与教学相位分离探讨](../../discussions/2026-07-10-诊断与教学相位分离探讨.md) + [2026-07-17 方向选择探讨](../../discussions/2026-07-17-方向选择-A先C后.md)

**ECOS Phase 4 采用方向 B（混合架构）**——诊断与教学不分离为两阶段，而是单一流水线持续混合。详细架构决策见 [02-architecture.md §3.4](02-architecture.md)。

**Phase 4 工程实现路径（W1-W4）**：

| 周 | 任务 | 工作量 | 来源决策 | 实际状态 |
|------|------|--------|----------|----------|
| **W1** | warm-up 5 题无感化 + dashboard 加 "当前 Bloom 层 + 距下一层 Δ" | 1-2 天 | [方向选择探讨 问题 2 + 问题 5](../../discussions/2026-07-17-方向选择-A先C后.md) | ✅ v0.41.0 |
| **W1-W2** | 自适应选题层（SE 最大维度 + Bloom 差 + 弱 topic 接入 `select_question_for_student`）| 2-3 天 | 方向 B 核心补完 | ✅ v0.42.0 |
| **W2-W3** | 探针题机制（每 8-10 题穿插 1 道，无痕不计学习时长）| 1-2 天 | [方向选择探讨 问题 3](../../discussions/2026-07-17-方向选择-A先C后.md) | ✅ v0.42.0 |
| **W3** | 置信度 UI 透明化（< 0.5 时数字变灰 + tooltip 解释）| 1 天 | [方向 B 缓解措施](02-architecture.md) §3.4.1 | ✅ v0.43.0 |
| **W3-W4** | dashboard 加"导出学习报告"按钮（C 端接口）| 0.5 天 | 兼容性接口 | ✅ v0.43.0 |

**判断锚点**：任何 UI 决策先问"这是给学生自己看的,还是给老师看的?"——只要是后者,推到 Phase 5+。

### 2.6 商业化策略明确：先 A 后 C（v1.3 新增）

> **决策来源**：[2026-07-17 方向选择探讨](../../discussions/2026-07-17-方向选择-A先C后.md) + [01-applications.md §3.4](01-applications.md)

**核心定位**：Phase 4 / M2-M5 定位为 **C 端学生自主学习产品**，B 端机构采购作为**远期延伸**。

**为什么"先 A 后 C"**：
- ECOS 核心研究命题要求 A（自主学习场景最能验证"AI 持续理解并帮助学生成长"假设）
- 做好 A 转 C 是降维（数据、报告封装）；先做 C 几乎回不去 A（学生自主性被结构性削弱）
- A 跑通后自然会有 C 端机构主动找上门（真实数据 → 案例研究 → 方法论沉淀 → B 端询单）

**兼容性接口（数据层留,UI 不做）**：
- 学生 ID 支持"一对多"（为"班级"留位）
- dashboard 留"导出学习报告"按钮
- 进度曲线形态适合"对外汇报"
- 探针题 + 置信度曲线（给 B 端测量叙事留接口）

**反向决策锚点（什么时候可以开始认真做 C）**：
- A 端获客成本 > 学生 LTV
- B 端机构**主动找上门**且需求合理
- 12 个月内 A 端跑不到 100 个真实学生

否则,坚持 A。详见 [01-applications.md §3.4](01-applications.md)。

### 2.3 M3 里程碑（MVP 实验 + 分析）

**时间**：2-4 周（M2 完成后启动）

**Definition of Done**：
- [ ] 50-100 学生使用 MVP 系统 4 周（含对照班）
- [ ] 数据采集完整（做题 + 解释文本 + 反思日志）
- [ ] CTA 5D 状态预测准确度评估（vs 传统 IRT/BKT baseline）
- [ ] 双 Agent 互校 vs 单 Agent 信念质量对比
- [ ] BloomProfile 演化曲线可视化
- [ ] TC 跨越检测的 liminal 状态识别 F1 ≥ 0.6
- [ ] 报告：MVP 实验结果 + H1-H3 验证结论 + 下一阶段建议

**核心假设验证**：

| 假设 | 评估指标 | 通过阈值 | 当前状态（lbc001 27 题）|
|---|---|---|---|
| **H1 CTA 5D 状态预测力** | 5D 状态预测 vs 实际下次表现的 AUC | ≥ 0.75（vs IRT baseline 0.65）| ⚠️ 待 lbc001 答 30+ 题 |
| **H2 Bloom 6 层可行性** | 6 层在初中数学上的方差解释比例 | ≥ 60% | ✅ lbc001 L1=0.7 L2=0.725 L3=0.8 L4=0.6 L5=0.6 L6=0.5 |
| **H3 双 Agent 互校抗幻觉** | 双 Agent vs 单 Agent 的信念校准度（ECE）| 双 Agent ECE ≤ 0.10 | ⚠️ 双 Agent 互校未实施 |

**风险预案**：
- **若 H1 失败**：5D 维度可能过细，需简化为 3D（K/P + Bloom）或重新校准
- **若 H2 失败**：6 层重组为 4 层（L1-L4），去除 Evaluate/Create（MVP 阶段）
- **若 H3 失败**：增加人工审核层（教师每周签字），或降低 LLM 介入深度

---

## 3. Phase 5 / M4-M5（产品化）

### 3.1 目标

**业务验证 + 多学科扩展**（H4-H5）：
- **H4**：ECOS 在 2-3 学科的迁移可行性（数学 → 物理 → 英语）
- **H5**：商业模式可行（B2C 订阅 / B2B 学校合作 / 混合）

### 3.2 M4 里程碑（学科扩展 + 算法升级）

**时间**：8-12 周

**Definition of Done**：
- [ ] 新增 1-2 个学科（高中数学 + 初中物理）
- [ ] Phase 4 未实现的组件补齐：Causal Forest 归因 + Cognitive Apprenticeship Stage 4-6 + 合意困难 + 交错练习
- [ ] TC 库扩展到 15-20 个（高中数学 + 物理）
- [ ] Misconceptions 库扩展到 100-150 条
- [ ] 跨学期画像迁移（MVP 仅学期内，Phase 5 支持学期切换）
- [ ] 学生规模扩展到 500-1000（每学科 200-500 学生）

**具体任务**：

| 周 | 任务 |
|---|---|
| W1-W2 | 物理学科：CTA Q 矩阵 + TC 库 + Misconception 库（与物理教师协作）|
| W2-W3 | 高中数学学科扩展（与初中数学复用率 ≥ 70%）|
| W3-W4 | Causal Forest 归因 + POMDP 升级（L4）|
| W4-W5 | Cognitive Apprenticeship Stage 4-6（Articulation + Reflection + Exploration）|
| W5 | 合意困难 + 交错练习（Bjork 完整四件套）|
| W6 | 跨学期画像迁移（状态继承 + 衰减模型）|

### 3.3 M5 里程碑（商业模式 + 教师/家长端）

**时间**：8-12 周

**Definition of Done**：
- [ ] 教师/家长端 UI 实现（[01-applications.md §4 场景 D](01-applications.md)）
- [ ] B2C 订阅模式跑通（学生/家长直接付费）
- [ ] B2B 学校合作模式跑通（≥ 1 所学校签约）
- [ ] 教师/家长报告自动化（每周班级报告 + 每月学生成长报告）
- [ ] 数据资产累积：500-1000 学生 × 4-6 个月画像
- [ ] 用户留存率 ≥ 60%（4 个月活跃用户）

**商业模式候选（v1.3 调整：B2B 推迟，先 C 端）**：

> **决策来源**：[2026-07-17 方向选择探讨](../../discussions/2026-07-17-方向选择-A先C后.md) + [01-applications.md §3.4](01-applications.md)

| 模式 | 适用 | 客单价（估计）| **阶段定位（v1.3）** |
|---|---|---|---|
| **C 端订阅** | C 端学生/家长直接付费 | 99-299 元/月 | **M5 核心**：先跑通 C 端订阅模式 |
| **B 端机构** | K12 学校 / 培训机构 | 50-200 元/学生/学期 | **远期延伸**：A 跑通 100 学生后再启动 |
| **混合** | B 端为主 + C 端增值 | 组合定价 | **暂不启动**：避免双线并进稀释方向 |

**M5 阶段重点**：
- ✅ **C 端订阅模式跑通**（学生/家长直接付费）
- ✅ dashboard 加"导出学习报告"按钮（C 端→家长场景）
- ⏸️ B 端机构 UI 推迟到 A 端 100 学生验证后
- ⏸️ 教师/家长协作报告（[01-applications.md §4 场景 D](01-applications.md)）推迟

**风险预警**：
- C 端获客成本可能高于 LTV（K12 自学市场尚未充分验证）——准备应对 12 个月内跑不到 100 学生的情况
- 家长付费意愿取决于可见效果——MVP 必须证明"4 周内可见进步"
- **B 端决策周期长（学校招标 6-12 月）**——但**M5 阶段不主动做 B 端**，等 C 端跑通

### 3.4 Phase 5 启动条件 + 双目标（v1.4 新增）

> **触发**：Bisen 2026-07-22 触发 v0.53.0 docs sync + v0.53.1 审查报告
> **依据**：[discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md](../../discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md) + [discussions/2026-07-22-partial-credit重大学术弊端发现.md](../../discussions/2026-07-22-partial-credit重大学术弊端发现.md)

#### 3.4.1 启动条件

| 条件 | 当前状态 | 来源 |
|---|---|---|
| **lbc001 答 30+ 题** | 27-29 题（差 1-3 题）| 测试数据 |
| **Bisen 启动决策** | 📋 待 Bisen | 本文档 |
| **Phase 5 PRD 完成** | 📋 待写 | partial credit 文档 + Q 矩阵文档 |
| **C 主导题 20+ 题设计** | 📋 待 | Q 矩阵文档 |
| **partial credit 设计稿** | 📋 待 | partial credit 文档 |

#### 3.4.2 Phase 5 双目标（v0.53.0 / v0.54.0）

##### 目标 A：🔴 **Partial Credit 必修**（P0，Bisen 2026-07-22 触发）

详见 [discussions/2026-07-22-partial-credit重大学术弊端发现.md](../../discussions/2026-07-22-partial-credit重大学术弊端发现.md)。

**问题**：
- 现状：MIRT 二元对错（correct: true/false），70% 答对按 0% 处理
- 影响：lbc001 PB-Q18 触发 K 维度多跌 0.27、L6 多跌 0.2

**解决路径**：
- v0.52.2 已存 AI reasoning（Observation.ai_reasoning 字段）—— 留 Phase 5 训练用历史数据
- Phase 5 v0.53.0 设计 partial credit 模型：
  - Q 矩阵加权（5D 权重按 Bloom 层 + topic 重新分配）
  - AI 评判返回 `partial_score: float ∈ [0, 1]` 而非 `correct: bool`
  - MIRT 接受部分对（response scoring 改造）
- 短期：v0.52.2 已存 ai_reasoning + judgement rationale 留历史数据

##### 目标 B：🟡 **C 主导题扩 20+ 题**（P0）

详见 [discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md](../../discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md)。

**问题**：
- 现状：5D 评估实际 3D（K/P/S 真评估，C/X 因无题触发 confidence=0.504 但从不变）
- 影响：整体 5D 评估失真，C/X 维度永远显示低 confidence

**解决路径**：
- **C 主导题 20+ 题**（v0.53.0 起步）：
  - 调试题（debug 已知 bug）
  - 错误分析（code review / error classification）
  - code reading（理解代码而非编写）
  - debug strategy（系统化调试方法）
- **X 主导题 20+ 题**（v0.54.0）：
  - Python↔JS / Java / C++ / Ruby 跨语言类比
  - 设计模式识别 / 算法跨语言实现
- **X 维度 misconception 库**（v0.55.0，M9-M16，8 条候选）

#### 3.4.3 Phase 5 任务清单（v0.53.0 → v0.55.0）

| 版本 | 内容 | 触发 | 状态 |
|------|------|------|------|
| **v0.53.0** | Phase 5 启动 + partial credit 设计稿 + C 主导题 20+ 题 | lbc001 答 30+ 题 | 📋 启动条件已定 |
| **v0.54.0** | partial credit 实施 + X 主导题 20+ 题 | v0.53.0 完成 | 📋 |
| **v0.55.0** | X 维度 misconception 库（M9-M16, 8 条候选）+ pytest 单元测试套件 | v0.54.0 完成 | 📋 |
| **v0.56.0+** | LCA 实施 + 双 Agent 互校 + 干预策略 | 不依赖 lbc001 | 📋 远期 |

#### 3.4.4 短期 v0.53.2 立即任务

| 任务 | 优先级 | 来源 |
|---|---|---|
| 同步 README.md badge / 创建日期 | P1 | 审查报告 §3.2 |
| 同步 02-architecture.md（C/X / LearningDNA 标待启用）| P1 | 审查报告 §3.2 |
| 同步 04-risks.md（partial credit / 库 ID / LCA 未实施）| P0 | 审查报告 §3.2 |
| 加 pre-commit hook 自动化 CI gate 前 3 条 | P1 | 审查报告 §8.2 |

---

## 4. Phase 6 / M6-M7（系统完善）

### 4.1 目标

**平台化 + 数据资产护城河**（H6-H7）：
- **H6**：K12 全学段覆盖可行（小学高年级 + 初中 + 高中）
- **H7**：3 年以上纵向数据形成不可替代的护城河

### 4.2 M6 里程碑（K12 全学段 + 跨学科）

**时间**：6-8 周

**Definition of Done**：
- [ ] 全学段 Q 矩阵 + TC 库 + Misconception 库（小学高年级 + 初中 + 高中）
- [ ] 学段切换自动化（如小升初、初升高的状态迁移）
- [ ] 跨学科能力建模（如数学 P 与物理 P 的迁移）
- [ ] POMCP 完整版（取代 Contextual Bandits）
- [ ] DKT / DKVMN 实验集成（可选基线比较）
- [ ] 学生规模 5000-10000

### 4.3 M7 里程碑（数据资产 + 商业模式成熟）

**时间**：8-12 周

**Definition of Done**：
- [ ] 数据资产累积：5000-10000 学生 × 1-3 年纵向画像
- [ ] 跨年级、跨学科的认知演化模型可对外发布
- [ ] LearningDNA 跨学段稳定性研究出初步结论
- [ ] 商业模式规模化（B2B 校企合作 ≥ 10 所 / B2C 付费用户 ≥ 10000）
- [ ] 学术合作（与师范院校 / 教育研究机构联合发表）
- [ ] 团队扩张（教师协作网络 + 算法工程师 + 产品 + BD）

**数据资产护城河**：
- **3 年以上纵向认知数据**：市场上无人系统性积累
- **跨学科迁移模型**：ECOS 独有
- **LearningDNA 跨学段稳定性**：研究无人区

---

## 5. 依赖图与关键路径

### 5.1 关键路径

```
Phase 0 完成（文档）
    ↓
M2 MVP 工程实现（4-6 周）              ← ✅ v0.40.0-0.53.1 实际完成
    ↓
M3 MVP 实验（2-4 周）                  ← ⚠️ 部分: lbc001 27 题, 单用户测试
    ↓
[关键决策点：H1-H3 通过?]
    ├─ 是 → M4 学科扩展（4-6 周）      ← 📋 Phase 5 启动后
    │        ↓
    │       M5 商业模式（4-6 周）
    │        ↓
    │       [决策点：商业模式可行?]
    │        ├─ 是 → M6 K12 全学段（6-8 周）
    │        │        ↓
    │        │       M7 数据资产（8-12 周）
    │        └─ 否 → 调整商业模式 → M6'
    └─ 否 → 回溯调整 CTA/LCA 设计 → M2'
```

### 5.2 关键路径总时长

| 路径 | 总时长 |
|---|---|
| **理想路径**（所有假设通过）| Phase 0 + 4-6 + 2-4 + 4-6 + 4-6 + 6-8 + 8-12 = 32-44 周（~8-11 月）|
| **保守路径**（含回溯）| + 4-8 周回溯 = 36-52 周（~9-13 月）|
| **v2.0 原估计** | "6-12 月平台化" = 26-52 周 |
| **v1.4 实际进度** | Phase 0 + M2 (4 周) = 已完成, M3 部分（lbc001 27-29 题, 0.5 周, 单用户）|

**说明**：本文档把 v2.0 的 6-12 月压缩为 ~8-13 月（含回溯缓冲），更现实可行。

### 5.3 关键决策点

| 决策点 | 通过条件 | 失败动作 | 当前状态 |
|---|---|---|---|
| **M3 后：H1-H3** | CTA 预测力 + Bloom 可行 + 互校抗幻觉 | 简化为 3D + 重组 Bloom + 强化规则 | ⚠️ H2 通过, H1/H3 待验证 |
| **M5 后：H4-H5** | 跨学科 + 商业模式 | 聚焦单一学科 + 单一商业模式 | 📋 Phase 5 启动后 |
| **M7 后：H6-H7** | 全学段 + 护城河成立 | 维持现状（特定学段 + 学科）| 📋 远期 |

---

## 6. 团队与预算（粗略估计）

### 6.1 团队配置

| 阶段 | 最小团队 | 推荐团队 |
|---|---|---|
| **Phase 0**（已完成）| 1 人（Bisen + Claude）| 1 人 |
| **M2 MVP 工程** | 2 人（算法 + 全栈）| 3 人（算法 + 后端 + 前端）|
| **M3 MVP 实验** | 2 人（算法 + 教师协作）| 3 人 + 1 教研 |
| **M4-M5 产品化** | 4 人 | 6 人 + 1 教研 + 1 BD |
| **M6-M7 系统完善** | 8 人 | 12 人 + 2 教研 + 2 BD |

### 6.2 预算粗估（仅供路线图参考）

| 项目 | Product Demo（M2-M5）| 产品化（M4-M5）| 系统完善（M6-M7）|
|---|---|---|---|
| 人力（年化）| 80-150 万 | 200-400 万 | 500-1000 万 |
| LLM API | 5-10 万 | 30-100 万 | 200-500 万 |
| 服务器 | 5-10 万 | 30-50 万 | 100-200 万 |
| 教师协作 | 5-10 万 | 30-50 万 | 100-200 万 |
| **小计** | **~100-180 万** | **~300-600 万** | **~900-1900 万** |

**说明**：
- 这是粗估，实际可能因团队规模、地点、谈判能力而差异较大
- Phase 0 阶段成本极低（个人研究项目），主要成本在 MVP 之后

---

## 7. 关键风险与对应（详见 04-risks.md）

| 风险 | 等级 | 对应假设 | v1.4 更新 |
|---|---|---|---|
| **CTA 5D 状态预测不达 H1** | 高 | H1 | — |
| **Bloom 6 层在 K12 不适用** | 中 | H2 | — |
| **双 Agent 互校无法抗幻觉** | 高 | H3 | — |
| **学生数据采集质量差** | 中 | 跨所有 Phase | — |
| **教师协作时间成本超预期** | 中 | 跨所有 Phase | — |
| **商业模式 B2B 决策周期长** | 中 | H5 | — |
| **数据资产护城河形成太慢** | 高 | H7 | — |
| **法律合规（未成年人数据）** | 高 | 跨所有 Phase | — |
| **🔴 Partial Credit 缺失**（v0.52.2 发现）| **P0** | 跨所有 Phase | 🆕 v1.4 |
| **🟡 C/X 0 主导题**（v0.52.1 发现）| **P0** | 跨所有 Phase | 🆕 v1.4 |
| **🟠 MIRT 二元对错 trade-off**（v0.52.2 反思）| **P0** | 跨所有 Phase | 🆕 v1.4 |
| **🟠 misconception 库 ID 错配**（v0.52.0 已修，但风险仍存）| 中 | 工程层 | 🆕 v1.4 |
| **🟠 LCA 未实施**（仅有脚手架）| 中 | H3 | 🆕 v1.4 |
| **🟠 双 Agent 互校未实施**（仅有占位）| 高 | H3 | 🆕 v1.4 |
| **🟡 5 次虚标模式**（v0.47.6 起防御性自检规范强制）| 中 | 跨所有 Phase | 🆕 v1.4 |
| **🟡 无 pytest 自动化测试**（lbc001 单用户手动）| 中 | 跨所有 Phase | 🆕 v1.4 |

**04-risks.md 将对这些风险逐一展开 + 缓解策略。**

---

## 8. 与 v2.0 产品化路径的关系

| 维度 | v2.0 提供 | 本文档扩展 | v1.4 增 |
|---|---|---|---|
| **Phase 划分** | ✅ 3 阶段（MVP/产品化/平台化）| 细分为 M0-M7 共 8 个里程碑 | — |
| **时间估计** | MVP 2-4 周 | **修正为 4-8 周**（含工程实现）| — |
| **核心假设** | ✅ 5D 状态预测 + Bloom 可行 + 互校 | H1-H7 共 7 个假设，每阶段 1-3 个 | — |
| **评估指标** | ⚠️ 概念性 | 具体阈值（H1 AUC≥0.75 等）| + lbc001 实测值 |
| **依赖关系** | ⚠️ 隐含 | 显式关键路径图 | — |
| **风险预警** | ⚠️ 简略 | 8 类风险 + 对应假设（详见 04-risks.md）| + 7 类新风险 |
| **团队预算** | ❌ 无 | 粗估（仅路线图参考）| — |
| **实际进度** | ❌ 无 | — | 🆕 §1.4 v0.40.0 → v0.53.1 实际进度 |
| **Phase 5 启动** | ⚠️ 隐含 | — | 🆕 §3.4 启动条件 + 双目标 |

**核心修正**：
1. **MVP 时间从 2-4 周 → 4-8 周**——根据 12 个 MVP 组件的工程量
2. **假设从 3 个 → 7 个**——M4/M6/M7 各加 1 个（学科迁移 + 全学段 + 数据资产）
3. **明确"失败回溯"路径**——避免"all-in 单一假设"的陷阱
4. **v1.4 新增**：基于 124 commits 实际进度 + lbc001 27-29 题实测 + 5 次虚标教训

---

## 9. 关联文档

- **战略层**：
  - [01-applications.md](01-applications.md) §7 MVP 范围（4 大场景对应）
  - [02-architecture.md](02-architecture.md) §8 MVP 架构（12 个组件）
  - [04-risks.md](04-risks.md) — 风险矩阵（基于本路线图）
  - [05-user-friendly-demo.md](05-user-friendly-demo.md) — 用户友好 Demo 设计
  - [07-project-comprehensive-audit-2026-07-22.md](07-project-comprehensive-audit-2026-07-22.md) — 2026-07-22 项目全面审查报告（v1.4 新增引用）
- **P0 三件套**（路线图各 Milestone 的理论依据）：
  - [v0.3.0 CTA 数学基础](../30-shared-cognitive-tools/theoretical-foundations/01-cta-mathematical-foundations.md) §7 MVP 实施路线
  - [v0.4.0 LCA 教学法基础](../30-shared-cognitive-tools/theoretical-foundations/02-lca-instructional-foundations.md) §5 MVP 实施路线
  - [v0.5.0 C 维度内容库](../30-shared-cognitive-tools/theoretical-foundations/03-c-dimension-content-libraries.md) §4 MVP 实施路线
- **核心论证**：
  - [v2.0 §执行摘要 产品化路径](../deep-research/Cognitive-Digital-Twin-Deep-Research.md) — 本文档的扩展来源
- **教学法层 + 工程层**：
  - [10-engineering/](../10-engineering/) — 工程实现（M2/M4/M6 的工程任务）
  - [20-pedagogy/](../20-pedagogy/) — 教学法落地（M2/M4 涉及）
  - [90-mvp/](../90-mvp/) — MVP 设计（M2/M3 的细化）
- **discussions/ 关键决策**（v1.4 新增引用）：
  - [2026-07-17 方向选择-A先C后](../../discussions/2026-07-17-方向选择-A先C后.md) — 商业化策略
  - [2026-07-21 lbc001 4 BUG 分析与修复计划](../../discussions/2026-07-21-lbc001测试发现4个BUG分析与修复计划.md) — 4 BUG 修复历史
  - [2026-07-22 partial credit 重大学术弊端发现](../../discussions/2026-07-22-partial-credit重大学术弊端发现.md) — Phase 5 必修
  - [2026-07-22 Phase 5 Q 矩阵 CX 重新设计路线图](../../discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md) — Phase 5 双目标
- **端到端流程**（v1.4 新增引用）：
  - [research/90-mvp/06-ecos-end-to-end-flow-analysis.md](../90-mvp/06-ecos-end-to-end-flow-analysis.md) — ECOS 端到端流程 + 5D/Bloom 通俗化解读
  - [research/90-mvp/python-basics-q-matrix-design.md](../90-mvp/python-basics-q-matrix-design.md) — Python 基础 Q 矩阵设计

---

## 10. 版本与维护

- **v1.0**（2026-06-25）— 初版
- **v1.1**（2026-06-26）— 链接修复 + 路径修正
- **v1.2**（2026-07-10）— 战略调整：MVP → Product Demo 完整化
- **v1.3**（2026-07-17）— 加入"先 A 后 C"商业化策略（§2.6）；明确方向 B 混合架构 + warm-up 窗口 + 探针题机制（§2.5）；M5 商业模式 B2B 推迟
- **v1.4**（2026-07-22）— 加入 v0.40.0 → v0.53.1 实际进度盘点（§1.4）+ Phase 5 partial credit 必修 + 双目标（§3.4）+ 三大根本问题（§11）+ 5 次虚标模式归档（§1.4.6）+ 7 类新风险（§7）+ 关联文档扩展

**v1.4 后续待办（影响本文档时同步更新）**：
- 当 [04-risks.md](04-risks.md) 完成后，§7 风险简表扩展为完整风险矩阵
- 当 [90-mvp/](../90-mvp/) 设计完成后，回填 M2/M3 的细化任务
- 当 Phase 4 实验完成后，回填"实际结果 vs 假设"对比
- 每完成一个 Milestone（M0-M7），更新 §1.1 已完成清单
- 当 A 端跑通 100 真实学生 + B 端机构主动询单时，回填 §2.6 / §3.3 状态为"已启动 B 端"
- **v1.5 待办**：当 Phase 5 v0.53.0 partial credit 实施完成时，回填 §3.4 状态 + 加 §3.5 partial credit 实施方案
- **v1.5 待办**：当 C/X 主导题答 20+ 题时，回填 §3.4 状态 + 评估 5D 完整性

---

## 11. 三大根本问题（v1.4 新增）

> **触发**：Bisen 2026-07-22 lbc001 27-29 题测试发现
> **核心**：3 个 P0 问题共同决定 Phase 5 必修

### 11.1 🔴 Partial Credit 缺失（P0，Phase 5 必修）

**现状**：
- MIRT 二元对错（`correct: true/false`）
- 70% 答对按 0% 处理
- K 维度多跌 0.27，L6 多跌 0.2（lbc001 PB-Q18 触发）

**为什么是根本问题**：
- 不是 bug 而是设计选择——partial credit 改进需要重写 MAP 估计 + Q 矩阵结构
- 不修 partial credit → ECOS 永远无法在真实答题场景应用
- 影响所有维度的真实评估

**Phase 5 解决路径**：
- v0.52.2 已存 AI reasoning（Observation.ai_reasoning 字段）—— 留 Phase 5 训练用历史数据
- Phase 5 v0.53.0 设计 partial credit 模型：
  - Q 矩阵加权（5D 权重按 Bloom 层 + topic 重新分配）
  - AI 评判返回 `partial_score: float ∈ [0, 1]` 而非 `correct: bool`
  - MIRT 接受部分对（response scoring 改造）

**详见**：[discussions/2026-07-22-partial-credit重大学术弊端发现.md](../../discussions/2026-07-22-partial-credit重大学术弊端发现.md)（8.2 KB）

### 11.2 🟡 C/X 0 主导题（P0，Phase 5 双目标 B）

**现状**：
- 5D 评估实际 3D（C/X 维度因无题触发，confidence=0.504 但从不变）
- lbc001 当前 27-29 题均为 K/P/S 主导题（写代码题）
- C（Common mistakes / 调试题 / 错误分析）和 X（跨语言迁移）维度从未触发

**为什么是根本问题**：
- 5D 评估的"完整性"是 ECOS 核心价值
- C/X 0 主导题意味着 ECOS 实际只测 K/P/S，丢掉 40% 维度

**Phase 5 解决路径**：
- C 主导题 20+ 题（v0.53.0）：
  - 调试题（debug 已知 bug）
  - 错误分析（code review / error classification）
  - code reading（理解代码而非编写）
  - debug strategy（系统化调试方法）
- X 主导题 20+ 题（v0.54.0）：
  - Python↔JS / Java / C++ / Ruby 跨语言类比
  - 设计模式识别 / 算法跨语言实现
- X 维度 misconception 库（v0.55.0，M9-M16，8 条候选）

**方案选择**：方案 C（标"待启用"灰底）已落地 v0.52.1，优于方案 A（0.10→0.20 伪信号污染）/方案 B（扩 40 题）

**详见**：[discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md](../../discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md)（12.2 KB）

### 11.3 🟠 MIRT 二元对错根本 trade-off

**现状**：
- MIRT MAP 估计基于二元对错（response = 0/1）
- 接受部分对需要重写 response scoring 函数
- 影响所有 5D 维度的真实评估

**为什么是根本问题**：
- 跟 partial credit 缺失同源——不修 partial credit 永远无法实际应用
- 但 partial credit 改进需要：
  - AI 评判返回 partial_score: float
  - MIRT MAP 估计支持连续值（不仅是 0/1）
  - Q 矩阵结构重新设计
  - 历史数据需重新训练

**不是 bug 而是设计选择**——需要在 Phase 5 全面重做

**详见**：§11.1 partial credit 文档 + [research/90-mvp/python-basics-q-matrix-design.md](../90-mvp/python-basics-q-matrix-design.md) §9.2（v0.52.1 扩充 C/X 缺口）

---

## 12. 反思：v0.40.0 → v0.53.1 的 10 天学到了什么（v1.4 新增）

### 12.1 流程层面

1. **"修一处即提交一处"心态是 bug 反复出现的根因** —— 必须"修一处扫一类"
2. **commit message 表达规范强制化** —— "已做/计划"混排让 Bisen 误以为落地
3. **devtools 验证优于代码自信** —— 5 次虚标都是"想当然"
4. **DB 恢复字段对齐是历史重灾区** —— 4 次漏（import json / tc_states / trajectory / item_params）

### 12.2 架构层面

1. **MIRT 二元对错是根本 trade-off** —— 不是 bug 而是设计选择
2. **dim.confidence 按 SE 分化是正确选择** —— 比均值更反映真实
3. **TC 不可逆符合 Meyer-Land 理论** —— post_liminal 答错不回退
4. **Bloom dominant_layer 是核心 UX** —— 6 维转单维可解释

### 12.3 产品层面

1. **先 A 后 C 是正确战略** —— lbc001 单用户测试发现 4 BUG + 1 P0 弊端
2. **方案 C 标"待启用"优于伪信号** —— 不硬猜
3. **Phase 4 完整 Demo 形态价值巨大** —— 124 commits 产出可展示
4. **单用户产品也能产生学术价值** —— partial credit 弊端 / 库 ID 错配都是可发表发现

### 12.4 协作层面

1. **Bisen 反馈极其具体（commit hash + 行号）** —— 是最好的 code review
2. **Mavis 自我反思比掩饰好** —— 5 次虚标都诚实地写进 CLAUDE.md
3. **跨工具协作是常态** —— Bisen 同时用 ChatGPT/Gemini/Claude
4. **哲学硬问题不回避** —— 意识/主体性/教育本质都可讨论

---

**创建日期**：2026-06-25
**维护者**：Bisen & Claude
