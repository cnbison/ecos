# Theoretical Foundations（理论借鉴子目录）

> **性质**：ECOS 理论借鉴子目录 SSOT（Single Source of Truth）——记录 ECOS 需要吸收借鉴的认知/学习/教学法理论清单与完成状态
> **关系**：[research/README.md](../../README.md)（上层 SSOT）、[shared-cognitive-science-toolbox.md](../shared-cognitive-science-toolbox.md)（与 SelfLab 共享的工具箱）
> **维护者**：Bisen & Claude
> **建立日期**：2026-06-24（P0 三件套完成后建立）

---

## 0. 本目录存在的意义

ECOS 不能仅依赖 [shared-cognitive-science-toolbox.md](../shared-cognitive-science-toolbox.md)（与 SelfLab 共享的 7 个工具）——这些工具覆盖**通用认知科学**（贝叶斯、记忆、预测加工等），但**K12 教育 + 心理测量学 + 教学法**领域需要额外吸收。

**本目录 = ECOS 独有理论借鉴库**（与 SelfLab 共享的工具箱互补）：
- 共享工具箱：通用认知科学（架构、记忆、推理）
- 本目录：教育特定理论（心理测量、教学法、概念建构）

**关键区分**：本目录的"借鉴"≠"复制"——借鉴方向是"理论核心观点 → 借鉴到 ECOS 哪个环节"，不重复理论的完整介绍。

---

## 1. 当前状态（2026-06-24）

| 借鉴档位 | 文档数 | 状态 | 完成度 |
|---|---|---|---|
| **P0**（强烈建议立即吸收）| 3 | ✅ 全部完成 | 100% |
| **P1**（重要补充）| 9 | 📋 待写 | 0% |
| **P2**（背景与边界补充）| 6 | 📋 待写 | 0% |

---

## 2. P0（强烈建议立即吸收）— ✅ 全部完成

### v0.3.0 — CTA 数学基础（5 层数学栈）

**文件**：[01-cta-mathematical-foundations.md](01-cta-mathematical-foundations.md)（v1.0，451 行）

**填补的 gap**：[v2.0 深度研究 §3.3 CTA — State Estimator](../../deep-research/Cognitive-Digital-Twin-Deep-Research.md) "只提 IRT/BKT/DKT 名字，无具体算法"

**5 层数学栈**：
```
L4 因果归因层    Causal Inference（DoWhy + Causal Forest）
L3 自适应选择层  CD-CAT（GDINA + PWKL 选题）
L2 状态估计层    MIRT（5D 非补偿多维能力向量）
L1 时间演化层    BKT / DKT（单知识点掌握度演化）
L0 概率框架层    POMDP / HMM（隐藏状态 + 部分观测）
```

**核心决策**：非补偿型 MIRT / 数学层不用 LLM（硬底线）/ POMDP 接口解耦 CTA 与 LCA

---

### v0.4.0 — LCA 教学法基础（3 大理论群）

**文件**：[02-lca-instructional-foundations.md](02-lca-instructional-foundations.md)（v1.0，420 行）

**填补的 gap**：[v2.0 深度研究 §3.4 LCA — Policy Optimizer](../../deep-research/Cognitive-Digital-Twin-Deep-Research.md) "有策略列表无理论论证"

**3 大理论群**：
- **Cognitive Load Theory** (Sweller) — 工作记忆负荷硬约束（4 级自适应呈现）
- **Bjork 学派四件套** — Testing Effect + Desirable Difficulties + Spacing Effect + Interleaving
- **Cognitive Apprenticeship** (Collins/Brown/Newman) — 6 阶段教学法框架

**核心决策**：MVP 实现测试效应 + 间隔效应；Phase 5+ 实现合意困难 + 交错 + Cognitive Apprenticeship Stage 4-6

---

### v0.5.0 — C 维度内容库（双轨内容库）

**文件**：[03-c-dimension-content-libraries.md](03-c-dimension-content-libraries.md)（v1.0，414 行）

**填补的 gap**：[v2.0 §3.3 C 维度是"抽象置信度"](../../deep-research/Cognitive-Digital-Twin-Deep-Research.md)，无内容评估基础

**双轨内容库**：
- **正向骨架**：Threshold Concepts（Meyer & Land, 2003）— MVP 候选 8 个初中数学 TC
- **反向补丁**：Misconceptions（Driver, 1985; Chi, 1992）— MVP 候选 10 条初中数学 misconception

**核心决策**：TC 不可逆性建模 + Liminal 状态识别 + LLM Critic misconception 检测

---

## 3. P1（重要补充）— 📋 待写

> **优先级说明**：P1 候选在 ECOS 框架中重要性次之——MVP 阶段可暂不实现，但 Phase 5+ 必须吸收

### P1.1 — Self-Regulated Learning (Zimmerman, Pintrich)

**核心**：自我调节学习模型——元认知 + 动机 + 行为三维度循环

**借鉴到 ECOS**：
- CTA 5D 中 X 维度（外部支架 + 元认知）需要从"静态状态"变为"动态循环"
- 与 Cognitive Apprenticeship Stage 4-5（Articulation + Reflection）整合
- 与 SRL 的 Forethought → Performance → Self-Reflection 三阶段循环对应

**预期文档规模**：~250-400 行

---

### P1.2 — Schema Theory (Bartlett, Rumelhart)

**核心**：图式（schema）是组织知识的认知结构；新知识通过与已有图式整合被理解

**借鉴到 ECOS**：
- CTA 5D 中 C 维度（概念联结）需要"图式激活强度"维度——超越纯 misconception 检测
- BloomProfile 的层级评估应基于"图式复杂度"而非"题目难度"
- 与 v0.5.0 Threshold Concepts 整合：每个 TC 是一个新图式的核心

**预期文档规模**：~250-400 行

---

### P1.3 — Working Memory Model (Baddeley, 2000)

**核心**：工作记忆多成分模型——语音环路、视觉空间画板、中央执行系统、情景缓冲器

**借鉴到 ECOS**：
- [v0.4.0 LCA 教学法基础 §1 CLT](02-lca-instructional-foundations.md) 已有 CLT 基础——本文档深化"工作记忆容量 4±1 chunks"的神经认知基础
- LCA 题目设计的精确参数化（不同成分负荷：语言/视觉/中央执行）
- 与 Learning DNA 整合：不同学生的工作记忆容量差异

**预期文档规模**：~200-350 行

---

### P1.4 — Conceptual Graphs + Ontology Engineering

**核心**：概念图谱与本体工程方法——结构化表示学科知识

**借鉴到 ECOS**：
- CTA 数学基础 L2 MIRT 需要学科本体支撑——数学/物理知识如何分类组织
- [v0.5.0 C 维度内容库](03-c-dimension-content-libraries.md) 的 TC 库需要本体化（TC 之间的关系：前驱/后继/并列）
- BloomProfile 跨越需要本体支持——L1 Remember → L6 Create 在学科内的"路径"

**预期文档规模**：~300-450 行

---

### P1.5 — Mastery Learning (Bloom, 1968)

**核心**：掌握学习理论——每个学生必须达到掌握阈值（80-90%）才能进入下一单元

**借鉴到 ECOS**：
- CTA 5D 的"掌握度阈值"明确化——BKT 的 P(L) 阈值（如 ≥0.8）作为升级条件
- LCA 策略空间加入"未达阈值 → 重复 + 变式"规则
- 与 v2.0 深度研究"成长轨迹"哲学整合

**预期文档规模**：~200-300 行

---

### P1.6 — Assessment for Learning (Black & Wiliam, 1998)

**核心**：形成性评估——通过持续评估 + 反馈提升学习，meta-analysis 显示 effect size 0.4-0.7

**借鉴到 ECOS**：
- CTA 的"诊断"本质是形成性评估——本文档提供理论框架
- LCA 反馈设计原则——立即反馈 + 具体改进建议 + 学生自我评估机会
- 教师/家长报告的理论基础

**预期文档规模**：~250-350 行

---

### P1.7 — DINA / DINO / Rule Space / Fusion Model

**核心**：认知诊断具体算法——超越 GDINA 的多模型比较

**借鉴到 ECOS**：
- [v0.3.0 CTA 数学基础 §2 CD-CAT](01-cta-mathematical-foundations.md) 已选定 GDINA 作为 MVP——本文档扩展到 DINA/DINO 等比较
- 为 Phase 5+ 升级 CTA 算法准备候选清单
- 与 Q 矩阵设计的最佳实践

**预期文档规模**：~300-450 行

---

### P1.8 — Contextual Bandits

**核心**：上下文多臂老虎机——轻量级强化学习框架，适合 LCA 干预选择

**借鉴到 ECOS**：
- LCA 干预选择可建模为 contextual bandit（学生状态 = context，干预 = arm，状态改善 = reward）
- 相比 POMDP 更轻量——MVP 阶段可用 contextual bandit 替代 POMCP
- 与 [v0.3.0 §4 POMDP](01-cta-mathematical-foundations.md) 形成"轻量 vs 完整"两档决策框架

**预期文档规模**：~250-400 行

---

### P1.9 — Cognitive Apprenticeship 完整版（深化 v0.4.0）

**核心**：本文档是 v0.4.0 §3 的深化——补充 6 阶段的实施细节 + 学科应用案例

**借鉴到 ECOS**：
- v0.4.0 已给出 6 阶段 + 与 ECOS 对接——本文档深化具体算法（如 Scaffolding 衰减曲线、Articulation 的 prompt 模板）
- 各学科应用案例（数学 vs 物理 vs 语文）

**预期文档规模**：~300-450 行

---

## 4. P2（背景与边界补充）— 📋 待写

> **优先级说明**：P2 是 ECOS 的"理论护城河"与"边界澄清"——不在 MVP 实施范围，但研究层与战略层需要明确

### P2.1 — Piaget 认知发展阶段论

**核心**：感知运动 → 前运算 → 具体运算 → 形式运算 四阶段

**借鉴到 ECOS**：
- ECOS 是 4 年级以上（具体运算后期 + 形式运算）——本文档澄清 ECOS 不服务的学段
- 阶段过渡的诊断信号（11-12 岁从具体到形式运算的过渡）

**预期文档规模**：~200-300 行

---

### P2.2 — Transfer of Learning

**核心**：近迁移 vs 远迁移——学习迁移的层次结构

**借鉴到 ECOS**：
- BloomProfile 高层级（Apply/Analyze/Evaluate/Create）本质是迁移能力——本文档提供迁移理论框架
- LCA 干预设计的迁移导向（如学完"二次函数"如何迁移到"二次不等式"）

**预期文档规模**：~250-350 行

---

### P2.3 — Educational Data Mining (EDM) / Learning Analytics

**核心**：教育数据挖掘方法论——聚类、序列模式、因果发现、异常检测

**借鉴到 ECOS**：
- ECOS 的 50-100 学生规模（MVP）需要 EDM 方法识别学习者类型
- CTA 的批量分析需要 EDM 标准（GAIA、OpenLA）
- 与教育机构对接的接口规范

**预期文档规模**：~200-300 行

---

### P2.4 — Knowledge Space Theory (Doignon & Falmagne)

**核心**：知识空间理论——学生状态的偏序集合结构

**借鉴到 ECOS**：
- CTA 5D 状态空间的结构化——不是任意状态都可达到
- 学科知识的前驱图（学习"二次函数"前必须掌握"一次函数"）

**预期文档规模**：~200-300 行

---

### P2.5 — Enactivism / 自生理论 (Maturana, Varela)

**核心**：认知是有机体-环境互动涌现——反对表征主义

**借鉴到 ECOS**：
- "长期认知陪伴"的哲学基础——学生认知不是"存储"而是"涌现"
- 与 SGE Phase 3 哲学基础对话（SelfLab 的"涌现自我"传统）

**预期文档规模**：~200-300 行

---

### P2.6 — 东方教育哲学（孔子 / 王阳明 / 佐藤学）

**核心**：中国/东亚传统教育思想与现代教育改革

**借鉴到 ECOS**：
- ECOS 服务中国 K12 学生——需要对话资源
- 与"刻意练习"中国家长文化的整合策略
- 避免西方中心主义（误用 CLT 等理论的文化前提）

**预期文档规模**：~200-300 行

---

## 5. ECOS 明确不吸收的理论（护栏）

避免 ECOS 偏离"科学化认知估计"方向：

| 不吸收 | 理由 |
|---|---|
| ❌ **深度现象学 / 金观涛真实性哲学** | SelfLab 已有；ECOS 不深入 |
| ❌ **神经科学细节**（fMRI / EEG）| ECOS 仅行为数据 |
| ❌ **婴幼儿认知发展**（Piaget 早期）| ECOS 是 4 年级以上 |
| ❌ **特殊教育专项**（ADHD / 自闭症）| ECOS 主流学生 |
| ❌ **Embodied Cognition 完整理论** | 仅作为哲学背景 |
| ❌ **多 Agent 教学系统完整体系** | 已部分覆盖于 ITS 范式 |
| ❌ **行为主义学习理论**（Skinner）| 与 ECOS 建构主义方向冲突 |

---

## 6. 借鉴档位的判断标准

什么样的理论是 P0 / P1 / P2？

### P0（强烈建议立即吸收）
- ✅ **直接填补 v2.0 已有 gap**（如 v2.0 §3.3-3.4 的"未明确"部分）
- ✅ **CTA/LCA/Bloom 三空间必有的算法/教学法基底**
- ✅ **MVP 实施必依赖**

### P1（重要补充）
- ⚠️ **Phase 5+ 实施需要**（但 MVP 可暂缓）
- ⚠️ **深化 P0 已借鉴的理论**（如 P1.9 深化 v0.4.0 Cognitive Apprenticeship）
- ⚠️ **CTA/LCA/Bloom 精细度提升**（如 P1.3 工作记忆深化 CLT）

### P2（背景与边界补充）
- 📋 **不直接驱动 ECOS 实现**——是"理论护城河"或"边界澄清"
- 📋 **战略层决策的理论依据**（如不吸收婴幼儿认知 → ECOS 学段边界）
- 📋 **与 SelfLab/竞品的理论差异化**（如 P2.5 Enactivism 对话 SGE）

---

## 7. 借鉴路线图（推荐执行顺序）

```
当前完成 (P0):
  v0.3.0 CTA 数学基础      ✅
  v0.4.0 LCA 教学法基础    ✅
  v0.5.0 C 维度内容库      ✅

战略层优先（依赖 P0 整合）：
  P0 02-architecture.md     📋 待写（项目任务，非理论借鉴）
  P0 03-roadmap.md          📋 待写
  P0 04-risks.md            📋 待写

理论借鉴（按需）：
  P1.9 Cognitive Apprenticeship 完整版  📋 待写（深化 v0.4.0）
  P1.3 Working Memory Model            📋 待写（深化 v0.4.0 CLT）
  P1.7 DINA/DINO 等算法比较            📋 待写（深化 v0.3.0 CD-CAT）
  P1.8 Contextual Bandits              📋 待写（深化 v0.3.0 POMDP）
  P1.4 Conceptual Graphs + Ontology    📋 待写（深化 v0.5.0 TC 库）
  P1.6 Assessment for Learning         📋 待写（贯穿 CTA/LCA）
  P1.5 Mastery Learning                📋 待写（贯穿 CTA 阈值）
  P1.1 Self-Regulated Learning         📋 待写（深化 X 维度）
  P1.2 Schema Theory                   📋 待写（深化 C 维度）

P2 借鉴（Phase 5+ 或战略层）：
  P2.1 Piaget 阶段论         📋 待写
  P2.2 Transfer of Learning   📋 待写
  P2.3 EDM / Learning Analytics 📋 待写
  P2.4 Knowledge Space Theory 📋 待写
  P2.5 Enactivism             📋 待写
  P2.6 东方教育哲学            📋 待写
```

**实际触发条件**：理论借鉴 P1/P2 不是按编号顺序写，而是**在工程层实施过程中遇到具体 gap 时按需写**。例如：
- 工程层写 LCA 干预选择时发现需要 Contextual Bandits → 写 P1.8
- 工程层写 CTA C 维度时发现需要 Schema Theory → 写 P1.2

---

## 8. 关联文档

- **上层 SSOT**：
  - [research/README.md](../../README.md) — Research SSOT 入口
  - [shared-cognitive-science-toolbox.md](../shared-cognitive-science-toolbox.md) — 与 SelfLab 共享的 7 个认知科学工具
- **同级 P0 借鉴**：
  - [01-cta-mathematical-foundations.md](01-cta-mathematical-foundations.md) — CTA 数学基础
  - [02-lca-instructional-foundations.md](02-lca-instructional-foundations.md) — LCA 教学法基础
  - [03-c-dimension-content-libraries.md](03-c-dimension-content-libraries.md) — C 维度内容库
- **上层战略**：
  - [01-applications.md](../../00-overview/01-applications.md) — 应用场景
- **项目元文档**：
  - [MIGRATION-FROM-SELFLAB.md](../../MIGRATION-FROM-SELFLAB.md) — 项目迁移梳理

---

## 9. 版本与维护

- **v1.0**（2026-06-24）— 初版（P0 三件套完成后建立）

**维护规则**：
- 每完成一份 P1/P2 借鉴，在本文档第 3/4 节添加对应条目，标注完成日期与版本号
- 每完成一份 P0 借鉴（已在 P0 列表中），在对应行标注 commit hash
- 当发现新的"应吸收但未列"理论时，先在此处评估档位（P0/P1/P2），再决定是否写

---

**创建日期**：2026-06-24
**维护者**：Bisen & Claude
