# ECOS — Educational Cognitive Operating System

> **教育认知操作系统**：面向 K12 学生的下一代 AI 辅助学习系统
> 基于"**学生认知数字孪生 + AI 学习教练**"双 Agent 共进化架构

[![Status](https://img.shields.io/badge/status-demo--v0.52.3-brightgreen)]()
[![Version](https://img.shields.io/badge/version-0.52.3-blue)]()
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

## 当前状态（2026-07-22，v0.52.3）— **🎉 Bisen 自定义 Phase 1-4 全部完成, 标"待 Phase 5"**

> **Bisen 路线**: Phase 1-4 是 UI 改进路线, 跟 ROADMAP Phase 0/4/5/6 不同。
> 2026-07-22 v0.52.3 已完成: 顶栏精简 / 题目合并 / 轨迹折叠 / 2 位小数 / Tab 导航 /
> CSS 变量 / 5D badge / SVG icon / 拆文件 / API 封装 / URL hash 路由。
> 详细见 [research/90-mvp/06-ecos-end-to-end-flow-analysis.md §0](research/90-mvp/06-ecos-end-to-end-flow-analysis.md)。

**ECOS 7 组件当前状态** (v0.52.3):
| 组件 | 状态 | 详情 |
|------|------|------|
| 5D + θ_cov | ✅ 真评估 | K/P/S 三维真评估, C/X 标"待启用" (Phase 5 重新设计) |
| Bloom 6 级 | ✅ 真评估 | L1-L6 累积, dominant_layer |
| TC 状态 | ✅ 真评估 | 5 topic × 3 阶段, post_liminal 不可逆 |
| Trajectory | ✅ 真评估 | 时间序列, 折叠面板 |
| Misconceptions | ✅ 真评估 | M1-M8 Python 库, v0.52.0 修过库 ID 错配 |
| overall_confidence | ✅ 真评估 | `mean(5D conf)`, v0.48.1 改的 |
| LearningDNA | ⚠️ **标"待启用"** | v0.1.0 占位, lbc001 数据不足, 等 ≥50 题 + 交互行为数据 |

**Bisen 测试发现 (lbc001 27 道题) 重大弊端 (2026-07-22)**:
- 🔴 **Partial Credit 缺失**: 70% 答对按 0% 处理, K 多跌 0.27, L6 多跌 0.2。**Phase 5 必修**
  详见 [discussions/2026-07-22-partial-credit重大学术弊端发现.md](discussions/2026-07-22-partial-credit重大学术弊端发现.md)
- 🟡 **C/X 0 主导题**: 5D 评估实际 3D, Phase 5 重新设计 C/X 主导题
  详见 [discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md](discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md)

**累计产出** (v0.1.0 → v0.52.3, 2026-06-24 ~ 2026-07-22):
- 78 Python 文件 / 113 MD 文件 / 16 JSON 文件
- 124 commits, 近 1 周密集开发
- 端到端流程: Q 矩阵设计 → 出题 → 答题 → AI 评判 → 状态更新 → 持久化 → 干预 → 个人画像
  详见 [research/90-mvp/06-ecos-end-to-end-flow-analysis.md](research/90-mvp/06-ecos-end-to-end-flow-analysis.md) (26.7 KB)

## 开发环境设置

ECOS Python 包需要 Python 3.11+。**强烈建议使用虚拟环境**：

```bash
# 1. 创建虚拟环境（使用 conda 提供的 python3 或系统 python3）
python3 -m venv .venv

# 2. 激活虚拟环境
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows

# 3. 安装项目（editable 模式，依赖自动解析）
pip install -e ".[dev]"            # 含 dev extras（pytest/black/ruff/mypy）

# 4. 配置 LLM API（可选，仅在调用 LLM 时需要）
cp .env.example .env               # .env 已在 .gitignore 中
# 编辑 .env 填入 MINIMAX_API_KEY=sk-...

# 5. 验证安装
python experiments/scripts/m2_w1_cta_basics_validation.py   # CTA 数学骨架
python experiments/scripts/m2_w1_llm_client_smoke.py         # LLM 客户端
```

### 依赖清单（自动从 pyproject.toml 解析）

| 包 | 用途 |
|---|---|
| `numpy>=1.24` | 5D 状态向量、BKT/MIRT 计算 |
| `scipy>=1.11` | MIRT MAP 估计的 L-BFGS-B + Hessian 逆 |
| `openai>=1.0` | LLM 客户端（OpenAI-Compatible Protocol：MiniMax-M3 / Moonshot Kimi）|
| `pytest` / `black` / `ruff` / `mypy`（dev extras）| 测试 + 格式化 + 静态检查 |

### LLM Provider 配置

`ECOSLLMClient.from_env(provider="...")` 支持两个 provider：

| Provider | 用途 | Base URL | 模型 | 环境变量 |
|---|---|---|---|---|
| `minimax`（默认）| 项目主用 | `https://api.minimax.io/v1` | `MiniMax-M3` | `MINIMAX_API_KEY` |
| `moonshot` | 中文教育场景备选 | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` | `MOONSHOT_API_KEY` 或 `KIMI_API_KEY` |

> `.env` 文件会在 `from_env()` 调用时自动加载，无需手动 `source`。

## 下一步（Phase 5 启动条件: lbc001 答 30+ 题）

**当前状态**: v0.52.3 实际完成 Bisen 自定义 Phase 1-4 全部 + Phase 4 (ROADMAP) 7 组件完整 UI。
**Phase 5 启动条件**: lbc001 答 30+ 题（当前 27 题）+ Bisen 启动决策。

| 优先级 | 任务 | 触发条件 | 详见 |
|--------|------|---------|------|
| **P0** | **Partial Credit 必修** (Bisen 2026-07-22 重大弊端) | lbc001 答 30+ 题 | [discussions/2026-07-22-partial-credit重大学术弊端发现.md](discussions/2026-07-22-partial-credit重大学术弊端发现.md) |
| **P0** | **C 主导题扩 20+ 题** (调试题/错误分析/code reading/debug strategy) | 同上 | [discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md](discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md) |
| P1 | **X 主导题扩 20+ 题** (Python↔JS/Java/C++/Ruby 跨语言类比) | v0.53.0 C 主导题答 20+ 题 | 同上 |
| P1 | **X 维度 misconception 库** (M9-M16, 8 条候选) | v0.54.0 X 主导题答 20+ 题 | 同上 |
| P1 | **状态管理** (App 对象, v0.51.0 Phase 4.3 留 v0.52.0+) | 不依赖 lbc001 | Phase 4 路线图 |
| P2 | 老师端骨架接 lbc001 真实数据 | A 端跑稳后做 | 路线图 |

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
