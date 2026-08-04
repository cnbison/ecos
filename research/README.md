# ECOS Research — SSOT 入口

> **ECOS 核心研究文档结构化目录**
> 本目录是 ECOS 项目所有研究文档的 SSOT（Single Source of Truth）入口

## 当前状态（2026-08-03，v0.74.1）

| 状态 | 数量 | 说明 |
|------|------|------|
| ✅ 已建立 | 8 战略层 + 5 工程层 + 4 教学法层 + 10+ MVP/Demo = 29+ 份 | Phase 0 全部完成（2026-06-25）+ Phase 4 Demo 完整化（v0.52.3）+ Phase 5 进行中（v0.54.0 -> v0.74.1）|
| 📋 占位 | 0 份 | 所有初始占位已填充 |

## 目录结构

```
research/
├── README.md                                # 本文件（SSOT 入口）
├── deep-research/                           # 深度研究文档
│   └── Cognitive-Digital-Twin-Deep-Research.md  # v2.0（1778 行，5 轮对话 + SGE/AiBeing 整合）
├── gpt-dialogues/                           # 5 轮 GPT 对话原文
│   ├── 01-cognitive-state-a-to-b-research.md   # 7 页综合调研站点
│   ├── 02-cognitive-digital-twin-rounds-1-3.md # 第 1-3 轮对话
│   ├── 03-cognitive-digital-twin-rounds-4-5.md # 第 4-5 轮对话
│   └── 04-cognitive-digital-twin-v01-report.md # 5 轮综合 v0.1
├── 00-overview/                             # 战略层（✅ 全部完成）
│   ├── 01-applications.md                   # 应用场景（v1.1，先 A 后 C）
│   ├── 02-architecture.md                   # 整体架构（v1.4，三空间 + 双 Agent）
│   ├── 03-roadmap.md                        # 路线图（v1.5，M0-M7 + H1-H7）
│   ├── 04-risks.md                          # 风险矩阵
│   ├── 05-user-friendly-demo.md             # 用户友好 Demo
│   ├── 07-project-comprehensive-audit-2026-07-22.md  # 项目全面审查
│   ├── 08-cx-dimension-semantic-decision.md # C/X 维度语义决策
│   ├── 10-comprehensive-deep-analysis-2026-08-01.md  # ⭐ 项目综合深度分析（4 必答点）
│   ├── 11-ecos-2.0-architecture-proposal.md # ⭐ ECOS 2.0 架构提案（5 引擎 + 6 对象 + CTA/LCA 拆分）
│   └── 12-kernel-mapping-current-vs-2.0.md # ⭐ Kernel 现状 vs 2.0 蓝图映射表
├── 10-engineering/                          # 工程层（✅ 全部完成）
│   ├── 01-cta-belief-engine.md              # CTA 5 层数学栈
│   ├── 02-lca-policy-engine.md              # LCA LinUCB + CA 6 阶段
│   ├── 03-bloom-goal-library.md             # Bloom 目标库
│   ├── 04-dual-agent-calibration.md         # 双 Agent 互校
│   ├── 05-persistence-session.md           # 持久化 + 跨会话
│   └── 06-metrics-and-indicators-overview.md # ⭐ 指标体系总览（5D/LinUCB/confidence/H3/ECE）
├── 20-pedagogy/                             # 教学法层（✅ 全部完成）
│   ├── 01-k12-cognitive-structure.md        # K12 学段差异化
│   ├── 02-bloom-application.md              # Bloom 在 K12 应用
│   ├── 03-learning-strategies.md            # 学习策略空间
│   └── 04-zpd-application.md                # ZPD 形式化
├── 30-shared-cognitive-tools/               # 共享工具箱（与 SelfLab 共享）
│   ├── shared-cognitive-science-toolbox.md
│   └── theoretical-foundations/             # ECOS 独有理论借鉴（SSOT: README.md）
│       ├── README.md                        # P0/P1/P2 借鉴路线图
│       ├── 01-cta-mathematical-foundations.md  # P0：CTA 5 层数学栈
│       ├── 02-lca-instructional-foundations.md # P0：LCA 3 大理论群
│       └── 03-c-dimension-content-libraries.md # P0：C 维度双轨内容库
├── 40-aibeing-borrowing/                    # AiBeing 借鉴
│   ├── 01-concept-borrowing.md
│   └── 02-application-layer-borrowing.md
└── 90-mvp/                                  # MVP / Demo 实施（✅ 多份文档）
    ├── README.md                            # MVP 设计总览
    ├── 06-ecos-end-to-end-flow-analysis.md # ⭐ 8 阶段端到端流程 + 5D/Bloom 通俗化
    ├── 07-phase5-partial-credit-implementation.md
    ├── 08-phase5-c-dimension-questions.md
    ├── 09-phase5-c-dimension-questions-expanded.md
    ├── 10-phase5-c-confidence-questions-design.md
    ├── 11-phase5-x-external-support-questions-design.md
    ├── ECOS-Cognitive-Intervention-Workflow.md
    ├── ECOS-Demo-Showcase-2026-07-06.md
    └── python-basics-q-matrix-design.md    # Python Q 矩阵设计
```

## 必读文档（按重要性）

### 立即必读

1. **深度研究 v2.0** — `deep-research/Cognitive-Digital-Twin-Deep-Research.md`
   - 1778 行，6 部分 + 5 附录
   - 完整 ECOS 架构 + 与 SGE Phase 3 冲突分析 + 产品化路径 + SelfLab 项目层建议

2. **5 轮综合 v0.1** — `gpt-dialogues/04-cognitive-digital-twin-v01-report.md`
   - 12 章研究报告
   - ECOS 终局定位

### 后续必读

3. **第 4-5 轮对话** — `gpt-dialogues/03-cognitive-digital-twin-rounds-4-5.md`
   - 第 4 轮：双 Agent 系统（CTA + LCA 互校）
   - 第 5 轮：Bloom 目标空间（State + Bloom Goal + Policy 三空间）

4. **第 1-3 轮对话** — `gpt-dialogues/02-cognitive-digital-twin-rounds-1-3.md`
   - 第 1 轮：成人/科研场景可行性
   - 第 2 轮：K12 场景下 5 维状态 + AI 学习教练
   - 第 3 轮：定位确定后的 7 大修改建议

5. **7 页综合调研站点** — `gpt-dialogues/01-cognitive-state-a-to-b-research.md`
   - 学术框架（9D 状态向量）
   - A→B 学习系统闭环

### 共享基础（与 SelfLab 共享）

6. **共享工具箱** — `30-shared-cognitive-tools/shared-cognitive-science-toolbox.md`
   - 7 个认知科学工具（贝叶斯、记忆分层、预测加工、双系统、BDI、元认知、经典架构）

7. **理论借鉴（ECOS 独有）** — `30-shared-cognitive-tools/theoretical-foundations/README.md`
   - **P0（全部完成）**：CTA 数学基础 + LCA 教学法基础 + C 维度内容库
   - **P1（待写）**：Self-Regulated Learning / Schema Theory / Working Memory / Ontology / Mastery Learning / AfL / DINA 算法 / Contextual Bandits / Cognitive Apprenticeship 深化
   - **P2（待写）**：Piaget / Transfer / EDM / Knowledge Space / Enactivism / 东方哲学
   - 完整路线图见该 README

8. **AiBeing 借鉴** — `40-aibeing-borrowing/01-02.md`
   - 概念层借鉴 + 应用层借鉴

## 关键洞察摘要（来自 v2.0 深度研究）

### 1. 三大核心架构判断

- **CTA（Cognitive Twin Agent）** —— State Estimator，像"认知科学家 + 心理测量学家"
- **LCA（Learning Coach Agent）** —— Policy Optimizer，像"教练 + 强化学习策略器"
- **Bloom Goal Space** —— State + Bloom Goal + Policy 三空间的目标坐标系

### 2. 双 Agent 互校循环

```
CTA: 提出假设（"知识缺口 60%"）
LCA: 设计实验验证（"先做概念题"）
观察结果
LCA: 返回（"程序技能问题概率上升"）
CTA: 更新信念（"知识缺口 20%, 程序 65%"）
LCA: 重新规划
```

### 3. 与 SGE Phase 3 4 大根本冲突

1. 方向错位：phase3 把"学生数字孪生"定义为"AI 模拟学生身份"，ECOS 需要"理解真实学生"
2. 维度错位 + 方法论降级：phase3 把 9D 强行映射到 value/drive，丢失 IRT/BKT 等科学估计方法
3. Bloom 目标空间结构性缺席：phase3 目录零提及
4. 单 Agent 架构无法表达双 Agent 互校

### 4. 与 SelfLab（SGE）的关系

- 兄弟项目（不是子项目）
- 共享 7 个认知科学工具
- 不共享 SGE value/drive 机制
- SGE 可作为 ECOS LCA 的"教师侧人格引擎"

## 文档维护约定

- **深度研究文档**：版本号管理（v1.0, v2.0 ...），每次重大更新递增主版本
- **GPT 对话原文**：保留原样不修改（仅在文件名前加编号便于引用）
- **战略层 + 工程层 + 教学法层 + MVP**：按编号顺序填充（01-, 02-, 03- ...）
- **共享工具箱 + AiBeing 借鉴**：从 SelfLab 复制后调整为 ECOS 视角

## 关联项目

- **SelfLab**（兄弟项目）：[github.com/cnbison/SelfLab](https://github.com/cnbison/SelfLab)
  - SGE（Self Genesis Engine）
  - 7 个认知科学工具箱共享

---

**创建日期**：2026-06-24
**维护者**：Bisen & Claude
**下次更新**：按需同步（新文档添加 / 阶段切换 / 假设验证结果更新时）
