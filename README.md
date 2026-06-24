# ECOS — Educational Cognitive Operating System

> **教育认知操作系统**：面向 K12 学生的下一代 AI 辅助学习系统
> 基于"**学生认知数字孪生 + AI 学习教练**"双 Agent 共进化架构

[![Status](https://img.shields.io/badge/status-planning-yellow)]()
[![Version](https://img.shields.io/badge/version-0.1.0-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

---

## 什么是 ECOS？

**ECOS（Educational Cognitive Operating System）** 是一个面向小学、初中和高中学生的下一代教育系统，核心由两个长期共进化的 AI Agent 协作：

- **CTA（Cognitive Twin Agent，认知孪生 Agent）** —— 理解学生
  - 像"认知科学家 + 心理测量学家"——保守、基于证据、维护置信度、避免幻觉
  - 维护学生认知状态的**信念分布**（不是事实判断）
  - 回答："这个学生现在是谁？卡在哪？"

- **LCA（Learning Coach Agent，学习教练 Agent）** —— 改变学生
  - 像"教练 + 强化学习策略器"——主动、实验、探索、优化
  - 基于 CTA 的状态选择最优干预策略
  - 回答："下一步怎么办？如何成长最快？"

- **Bloom Goal Space（布鲁姆目标空间）** —— 目标坐标系
  - 6 层认知层级：Remember → Understand → Apply → Analyze → Evaluate → Create
  - 让 B 从"掌握二次函数"变成"掌握二次函数：Bloom Level 4"——可计算
  - 解决"会做但不会想"的中国教育痛点

两者通过**互校循环**（CTA 提出假设 → LCA 设计实验 → 观察结果 → CTA 更新信念 → LCA 重新规划）共同进化，对抗 LLM 幻觉，形成"**自适应科学实验系统**"。

## 核心架构

```
┌──────────────────────────────────────────────────────────┐
│              Bloom Goal Space（目标坐标系）                 │
│  Remember → Understand → Apply → Analyze → Evaluate → Create │
└──────────────────────────────────────────────────────────┘
                            ↕
┌──────────────────────────────────────────────────────────┐
│       Learning Coach Agent (LCA) — Policy Optimizer       │
│       思维模式：教练 + 强化学习策略器                        │
│       输出：intervention_type + parameters + expected_gain │
└──────────────────────────────────────────────────────────┘
                            ↕
┌──────────────────────────────────────────────────────────┐
│     Cognitive Twin Agent (CTA) — State Estimator          │
│     思维模式：认知科学家 + 心理测量学家                     │
│     状态：K/P/S/C/X + BloomProfile + LearningDNA + Trajectory │
└──────────────────────────────────────────────────────────┘
                            ↕
                         Student
```

详细架构见 [`research/deep-research/Cognitive-Digital-Twin-Deep-Research.md`](research/deep-research/Cognitive-Digital-Twin-Deep-Research.md) v2.0。

## 项目目标

构建一个**能够持续 6~12 年陪伴学生成长的教育认知操作系统**：

- **目标用户**：K12 学生（小学/初中/高中）
- **核心能力**：持续理解 + 主动引导 + 长期共进化
- **护城河**：3 年以上的个性化认知画像（数据资产壁垒）
- **差异化**：相比 Khanmigo / Duolingo Max / Squirrel AI，是从"知识图谱 + AI 问答"升级为"理解学生 + 改变学生"的下一代架构

## 与 SelfLab（SGE）的关系

ECOS 是与 [SelfLab](https://github.com/cnbison/SelfLab) **并列的独立项目**：

| 维度 | SelfLab (SGE) | ECOS |
|------|---------------|------|
| **核心问题** | AI 能否形成持续自我 | AI 能否理解并帮助学生成长 |
| **核心架构** | 单一 Agent 12 步编排 | 双 Agent 互校（CTA + LCA）|
| **状态空间** | AI 自身 value/drive | 学生 9D + BloomProfile |
| **应用方向** | Personal AI、协作 agent、历史人物 | K12 教育 |
| **共享基础** | 7 个认知科学工具（贝叶斯、记忆分层、预测加工、双系统、BDI、元认知、经典架构）|

**为什么作为独立项目**：

1. **避免散乱**：SelfLab 已聚焦 SGE，ECOS 有独立的研究方向和目标用户
2. **独立发展**：SGE 关注"AI 自我涌现"，ECOS 关注"教育认知操作系统"——互不干扰
3. **降低认知负担**：研究者可在两个项目间清晰切换
4. **合作灵活**：ECOS 未来与教育机构合作时，独立项目身份更合适

详细决策过程见 [`discussions/2026-06-24-ecos-project-establishment.md`](discussions/2026-06-24-ecos-project-establishment.md)。

## 文档结构

```
ecos/
├── README.md                          # 本文件（项目入口）
├── CLAUDE.md                          # Claude Code 协作指南
├── CHANGELOG.md                       # 变更日志
├── LICENSE                            # MIT License
├── pyproject.toml                     # Python 包配置
├── ecos/                              # Python 包（未来实现）
│   ├── cta/                           # Cognitive Twin Agent
│   ├── lca/                           # Learning Coach Agent
│   ├── dual_agent/                    # 双 Agent 互校
│   ├── bloom/                         # Bloom Goal Library
│   ├── persistence/                   # 学生状态持久化
│   ├── session/                       # 长期会话管理
│   ├── llm_client.py
│   └── orchestrator.py
├── research/                          # 核心研究文档
│   ├── README.md                      # SSOT 入口
│   ├── deep-research/                 # 深度研究（v2.0）
│   ├── gpt-dialogues/                 # 5 轮 GPT 对话原文
│   ├── 00-overview/                   # 战略层
│   ├── 10-engineering/                # 工程层
│   ├── 20-pedagogy/                   # 教学法层
│   ├── 30-shared-cognitive-tools/     # 共享认知科学工具箱
│   ├── 40-aibeing-borrowing/          # AiBeing 借鉴
│   └── 90-mvp/                        # MVP 实施
├── references/                        # 参考资料
├── experiments/                       # 一次性实验代码
├── discussions/                       # 讨论记录
└── prototypes/                        # 架构原型
```

## 当前状态（2026-06-24）

| 层级 | 状态 |
|------|------|
| 战略层（research/00-overview/）| 📋 占位（待 Phase 4.1 填充）|
| 工程层（research/10-engineering/）| 📋 占位 |
| 教学法层（research/20-pedagogy/）| 📋 占位 |
| 共享工具箱（research/30-shared-cognitive-tools/）| ✅ 已建立（从 SelfLab 迁移）|
| AiBeing 借鉴（research/40-aibeing-borrowing/）| ✅ 已建立（从 SelfLab 迁移）|
| MVP 实施（research/90-mvp/）| 📋 占位 |
| Python 包（ecos/）| 📋 骨架（__init__.py 占位）|
| 深度研究文档 | ✅ v2.0（从 SelfLab 迁移，1778 行）|
| 5 轮 GPT 对话 | ✅ 已迁移（4 份文件）|

## 下一步（立即）

| 优先级 | 任务 | 详见 |
|--------|------|------|
| **P0** | 战略层 4 份文档填充（00-overview）| [research/00-overview/] |
| **P0** | 工程层关键模块设计（CTA + LCA + 互校）| [research/10-engineering/] |
| **P1** | 教学法层（K12 认知结构 + Bloom 应用）| [research/20-pedagogy/] |
| **P1** | MVP 设计（初中数学 + 50-100 学生）| [research/90-mvp/] |
| **P2** | Python 包实现（CTA + LCA 基础类）| [ecos/] |

## 关联项目

- **SelfLab（兄弟项目）**：[github.com/cnbison/SelfLab](https://github.com/cnbison/SelfLab)
  - SGE（Self Genesis Engine）—— AI 自我涌现引擎
  - 共享 7 个认知科学工具箱

## 维护者

- **发起人**：Bisen
- **协作**：Claude Code

## 许可证

[MIT License](LICENSE)

---

**创建日期**：2026-06-24
**当前版本**：0.1.0（项目建立）
