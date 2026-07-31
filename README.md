# ECOS — Educational Cognitive Operating System

> **教育认知操作系统**：面向 K12 学生的下一代 AI 辅助学习系统
> 基于"**学生认知数字孪生 + AI 学习教练**"双 Agent 共进化架构

[![Status](https://img.shields.io/badge/status-demo--v0.68.0-brightgreen)]()
[![Version](https://img.shields.io/badge/version-0.68.0-blue)]()
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

## 当前状态（2026-07-30，v0.68.0）— **🚀 Phase 5 已启动：partial credit / C/X 主导题 / LCA / dual_agent / H3 验证落地**

> **Bisen 路线**: Phase 1-4 是 UI 改进路线, 跟 ROADMAP Phase 0/4/5/6 不同。
> 2026-07-22 v0.52.3 已完成 Phase 1-4 (顶栏精简 / 题目合并 / 轨迹折叠 / 2 位小数 / Tab 导航 /
> CSS 变量 / 5D badge / SVG icon / 拆文件 / API 封装 / URL hash 路由)。
> 2026-07-23 ~ 2026-07-30 完成 Phase 5 核心骨架: partial credit / C/X 主导题 / LCA 接入与持久化 /
> dual_agent 接入与持久化 / H3 验证 A+B 报告。
> 详细见 [CHANGELOG.md](CHANGELOG.md) v0.54.0 → v0.68.0。

**ECOS 7 组件当前状态** (v0.68.0):
| 组件 | 状态 | 详情 |
|------|------|------|
| 5D + θ_cov | ✅ 真评估 | K/P/S/C/X 五维均非零 (lbc001 C=-0.12 X=0.47; lbc002 C=-0.20 X=0.82) |
| Bloom 6 级 | ✅ 真评估 | L1-L6 累积, dominant_layer |
| TC 状态 | ✅ 真评估 | 5 topic × 3 阶段, post_liminal 不可逆 |
| Trajectory | ✅ 真评估 | 时间序列, 折叠面板, cap 500 |
| Misconceptions | ✅ 真评估 | M1-M8 Python 库, v0.52.0 修过库 ID 错配 |
| overall_confidence | ✅ 真评估 | `mean(5D conf)`, v0.48.1 改的 |
| LearningDNA | ⚠️ **标"待启用"** | v0.1.0 占位, 等 ≥50 题 + 交互行为数据 |

**Bisen 测试发现与跟进 (2026-07-22 → 2026-07-30)**:
- ✅ **Partial Credit 已实施**: v0.54.0 接入 `partial_score` 端到端, MIRT 支持部分对。
  详见 [CHANGELOG.md](CHANGELOG.md) v0.54.0 + [discussions/2026-07-22-partial-credit重大学术弊端发现.md](discussions/2026-07-22-partial-credit重大学术弊端发现.md)
- ✅ **C/X 0 主导题已修复**: v0.54.2/3 各加 5 主导题, v0.65.0 解除"待启用"灰底。
  详见 [discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md](discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md)
- ⚠️ **H3 验证当前未通过, 根因是 confidence 指标选错**: v0.68.0 B 报告显示 V1/V2 ECE 均反向;
  v0.69.0 重新设计 dual_agent confidence 指标 (LinUCB reward = actual_outcome)。
  详见 [discussions/2026-07-30-H3-verification-B-report.md](discussions/2026-07-30-H3-verification-B-report.md)

**累计产出** (v0.1.0 → v0.68.0, 2026-06-24 ~ 2026-07-30):
- 102 Python 文件 / 96 MD 文件 / 16 JSON 文件
- 178 commits, 其中 57 个在 2026-07-22 之后
- 端到端流程: Q 矩阵设计 → 出题 → 答题 → AI 评判 → 状态更新 → 持久化 → LCA 干预 → dual_agent 互校 → 个人画像
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

## 下一步（Phase 5 进行中）

**当前状态**: v0.68.0 Phase 5 已启动并推进: partial credit / C/X 主导题 / LCA / dual_agent 均已落地,
H3 验证 A+B 报告已完成, 等待 v0.69.0 confidence 指标重设计后重跑 H3。

| 优先级 | 任务 | 触发条件 | 详见 |
|--------|------|---------|------|
| **P0** | **重新设计 dual_agent confidence 指标** (B4+C1+D1 方案) | v0.69.0 立即启动 | [discussions/2026-07-30-v0690-confidence-redesign-PRD.md](discussions/2026-07-30-v0690-confidence-redesign-PRD.md) |
| **P0** | **H3 重跑** (用 V3 confidence 指标) | v0.69.0 落地后 | [discussions/2026-07-30-H3-verification-B-report.md](discussions/2026-07-30-H3-verification-B-report.md) |
| P1 | C/X 主导题继续扩量 (从各 5 道到 20+ 道) | lbc001/lbc003 答完现有 C/X 题 | [discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md](discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md) |
| P1 | LCA bandit 数据观察 + 干预效果分析 | v0.57.0 持久化数据积累 2 周 | CHANGELOG v0.57.0 |
| P2 | LearningDNA 真实实现 | ≥50 题 + 交互行为数据 | — |
| P2 | 老师端骨架 | A 端跑稳后做 | 路线图 |

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
**当前版本**：v0.68.0（2026-07-30 dual_agent thread-safety + H3 B 报告）
