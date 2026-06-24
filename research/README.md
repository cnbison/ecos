# ECOS Research — SSOT 入口

> **ECOS 核心研究文档结构化目录**
> 本目录是 ECOS 项目所有研究文档的 SSOT（Single Source of Truth）入口

## 当前状态（2026-06-24）

| 状态 | 数量 | 说明 |
|------|------|------|
| ✅ 已建立 | 4 + 1 + 2 + 1 = 8 份 | 从 SelfLab 迁移的核心研究文档 |
| 📋 占位 | 14 份 | 战略层 + 工程层 + 教学法层 + MVP 占位 |

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
├── 00-overview/                             # 战略层（待填充）
│   ├── 01-applications.md
│   ├── 02-architecture.md
│   ├── 03-roadmap.md
│   └── 04-risks.md
├── 10-engineering/                          # 工程层（待填充）
│   ├── 01-cta-belief-engine.md
│   ├── 02-lca-policy-engine.md
│   ├── 03-bloom-goal-library.md
│   ├── 04-dual-agent-calibration.md
│   └── 05-persistence-session.md
├── 20-pedagogy/                             # 教学法层（待填充）
│   ├── 01-k12-cognitive-structure.md
│   ├── 02-bloom-application.md
│   ├── 03-learning-strategies.md
│   └── 04-zpd-application.md
├── 30-shared-cognitive-tools/               # 共享工具箱（与 SelfLab 共享）
│   └── shared-cognitive-science-toolbox.md
├── 40-aibeing-borrowing/                    # AiBeing 借鉴
│   ├── 01-concept-borrowing.md
│   └── 02-application-layer-borrowing.md
└── 90-mvp/                                  # MVP 实施
    └── README.md
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

7. **AiBeing 借鉴** — `40-aibeing-borrowing/01-02.md`
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
**下次更新**：战略层 4 份文档填充后
