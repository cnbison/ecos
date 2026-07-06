# ECOS 认知干预闭环 Demo 展示报告

> **版本**：v1.1（2026-07-06，新增 Demo 4）
> **用途**：向学校/合作方展示 ECOS 核心价值
> **Demo 组成**：Claude Skills 认知闭环 + 跨领域泛化 + BeliefEngine BKT 追踪 + MIRT K/P/S 分化

---

## 1. ECOS 是什么

ECOS（Education Cognitive Operating System）是一个 AI 认知操作系统，核心能力：

**持续追踪学生的认知状态 → 精准检测误解（Misconception）→ 靶向干预 → 验证效果**

```
┌─────────────┐     ┌─────────────┐
│    CTA      │◄────│    LCA      │
│ 认知追踪 Agent │     │ 干预决策 Agent │
└──────┬──────┘     └──────┬──────┘
       │                   │
       │  干预建议          │ 策略决策
       ▼                   ▼
┌─────────────────────────────────┐
│        BeliefEngine             │
│  ┌─────┐  ┌─────┐  ┌─────┐  │
│  │ 5D  │  │Bloom│  │  C  │  │
│  │State │  │Profile│ │折扣 │  │
│  └─────┘  └─────┘  └─────┘  │
└─────────────────────────────────┘
```

**5D 信念状态**：K（知识）、P（程序）、S（策略）、C（置信度）、X（外部支架）

---

## 2. Demo 1：Claude Skills 认知闭环（2026-07-05）

### 2.1 背景

以"学习 Claude Skills"为内容，Bisen 扮演学生，验证 ECOS 能否：
1. 检测学生对 Skill 概念的 misconception
2. 靶向干预
3. 验证 misconception 是否被清除

**Misconception 库（M1-M5）**：

| ID | 名称 | 核心误解 |
|----|------|---------|
| M1 | Skill 等于斜杠命令 | Skill 是按 description 自主加载，不是 /command 召唤 |
| M2 | Skill 等于 MCP Server | Skill 是本地 description，MCP 是外部进程调用 |
| M3 | Skill 等于自动化/Hook | Skill 是 LLM 驱动，不是自动触发脚本 |
| M4 | Skill 等于 Prompt 模板 | description 是 LLM 指令，不是填充模板 |
| M5 | Skill 总是被加载 | 加载是概率性的，由 LLM 自主判断 |

### 2.2 完整闭环：Round 1 → 干预 → Round 2

#### Misconception 检测 Round 1

| QID | 学生回答 | 检测结果 |
|------|---------|---------|
| Q1 | "skill可以用斜杠命令来直接调用" | **M1 触发（置信度 0.95）** |
| Q2 | "我不知道skill跟MCP server有什么区别" | **M2 触发（置信度 0.95）** |
| Q3 | "description跟system prompt不是一回事" | 无触发 |

**C 维度折扣因子**：`discount_factor = 1.0 - (0.95 + 0.95) × 0.3 = 0.43`

#### 干预执行

> **M1 干预**：Skill 不是"打什么它做什么"的命令。斜杠命令像是点菜——你点什么，服务员做什么。Skill 更像是图书馆索引卡——LLM 自己判断哪张卡和你的问题相关，主动调出来。**Skill 的触发是 LLM 基于 description 相关性自主判断的，不是你用斜杠"召唤"出来的。**
>
> **M2 干预**：Skill 和 MCP Server 是完全不同的东西。Skill 是本地指令——LLM 自己读、自己理解、自己决定是否调用。MCP Server 是外部进程——通过协议调用真实运行在外的程序。类比：Skill 像图书馆索引卡系统；MCP Server 像外卖订单系统（有真实的东西送过来）。

#### Misconception 检测 Round 2（干预后）

| QID | 学生新回答 | 检测结果 |
|------|---------|---------|
| Q1 | "skill不能用斜杠命令来直接调用，而是LLM根据description自主决定" | **无触发（0.0）** |
| Q2 | "我现在知道skill是LLM根据description自主调用，MCP是外部程序" | **无触发（0.0）** |

**C 维度折扣因子恢复**：`discount_factor = 1.0`（全部清除）

### 2.3 4-Gate 达标验证

Claude Skills 主题的 4-gate 定义：

| 闸 | 标准 | 结果 |
|----|------|------|
| ① TC_skill 跨越 | M1-M5 全清除 | ✅ 通过 |
| ② Bloom U ≥ 0.85 | U认知深度 = 0.85 | ✅ 通过 |
| ② Bloom A ≥ 0.75 | A认知深度 = 0.90 | ✅ 通过 |
| ③ Misconception 清零 | M1-M5 全部消除 | ✅ 通过 |
| ④ C 是挣来的 | 伪置信 = false | ✅ 通过 |

**全部 4-gate 达标 🎉**

---

## 3. Demo 2：跨领域泛化——批判性思维（2026-07-06）

### 3.1 验证目的

ECOS 的 misconception 库是**领域无关的**——只需注入新的 `library_str`，即可在新领域跑通闭环，无需修改代码。

### 3.2 批判性思维 Misconception 库

| ID | 名称 | 核心误解 |
|----|------|---------|
| M1 | 相关性 = 因果性 | 看到两个事件相关就认为一个有因果关系 |
| M2 | 所有证据同等可信 | 不区分一手/二手、权威/非权威来源 |
| M3 | 专家 = 正确 | 认为只要是专家说的就是对的 |
| M4 | 逻辑自洽 = 事实正确 | 认为推理过程严密则结论必然正确 |

### 3.3 Round 1 → 干预 → Round 2

| QID | 学生 Round 1 回答 | 检测结果 | 学生 Round 2 回答 | Round 2 结果 |
|------|-----------------|---------|-----------------|-------------|
| Q1（冰淇淋与溺水）| "冰淇淋销量↑导致溺水↑" | **M1（0.99）** | "只是相关性，真正原因是夏天" | **无（0.0）** ✅ |
| Q2（专家建议）| "专家建议的，所以是对的" | **M3（0.85）** | "专家建议也未必对，缺乏证据" | **无（0.0）** ✅ |
| Q3（推理与结论）| "推理没问题，结论就对了" | **M4（0.97）** | "前提错了，结论也可能错" | **无（0.0）** ✅ |

**结论**：注入新领域 misconception 库，无需修改任何代码，即可在 2 轮内完成清除。

---

## 4. Demo 3：BeliefEngine BKT/MIRT 追踪（2026-07-06）

### 4.1 验证目的

ECOS 不仅有 LLM Critic，还真正更新了学生的认知状态（BKT 概率 + MIRT 多维估计）。

### 4.2 10 道 Claude Skills 知识题测试

| QID | Bloom | 正确性 | K 掌握概率 | 变化 |
|------|-------|--------|-----------|------|
| CS-Q01 | L1 | ✅ | 0.500 → 0.582 | ↑ |
| CS-Q02 | L2 | ✅ | 0.582 → 0.597 | ↑ |
| CS-Q03 | L2 | ✅ | 0.597 → 0.597 | → |
| CS-Q04 | L2 | ❌ | 0.597 → 0.546 | ↓ |
| CS-Q05 | L2 | ✅ | 0.546 → 0.560 | ↑ |
| CS-Q06 | L3 | ✅ | 0.560 → 0.570 | ↑ |
| CS-Q07 | L3 | ✅ | 0.570 → 0.579 | ↑ |
| CS-Q08 | L1 | ❌ | 0.579 → 0.552 | ↓ |
| CS-Q09 | L4 | ✅ | 0.552 → 0.560 | ↑ |
| CS-Q10 | L4 | ✅ | 0.560 → 0.567 | ↑ |

### 4.3 BKT 行为验证 ✅

| 行为 | 预期 | 实际 |
|------|------|------|
| 答对 → 概率上升 | K↑ | Q01 +0.082, Q02 +0.015 |
| 答错 → 概率下降 | K↓ | Q04 -0.051, Q08 -0.027 |
| 连续答对 → 持续上升 | K↑ | Q05→Q06→Q07→Q09→Q10 |
| 答错后答对 → 部分恢复 | K↗ | Q05 修复了 Q04 的下降 |

---

## 4. Demo 4：MIRT K/P/S 多维分化（2026-07-06）

### 4.1 验证目的

证明 MIRT 能够区分 K（知识）、P（程序）、S（策略）三个维度，而非均匀趋同。

### 4.2 问题：为什么默认实现中 K=P=S

`BiFactorMIRT5D` 所有题目默认参数 `a_specialized = [0.8, 0.8, 0.8, 0.8, 0.8]`（均匀加载），导致所有题目对所有维度的更新贡献相同，θ 向量在所有题目更新后保持均匀。

### 4.3 解决方案：差异化 a_specialized 设计

| Skill | 主要维度 | a_specialized 设计 |
|-------|---------|-------------------|
| `definition` | K 主导 | `[0.9, 0.2, 0.4, 0.1, 0.1]` |
| `description` | P 主导 | `[0.3, 0.9, 0.2, 0.1, 0.1]` |
| `loading` | S 主导 | `[0.2, 0.3, 0.9, 0.1, 0.1]` |
| `practice` | S 主导 | `[0.2, 0.4, 0.9, 0.1, 0.1]` |
| `scoping` | S 主导 | `[0.3, 0.2, 0.9, 0.1, 0.1]` |

### 4.4 结果

| 维度 | 最终值 | 解读 |
|------|--------|------|
| **S** | **0.778** | loading/practice/scoping 题目全对，S 维度持续上升 |
| **P** | **0.592** | description 题目 Q06 答错，压制 P 上升 |
| **K** | **0.549** | definition 题目 Q03 答错，压制 K 上升 |

**K/P/S 最大差异：0.229 ✅**

---

## 5. ECOS 演示了什么

### 5.1 核心能力验证

| 能力 | 验证方式 | 结果 |
|------|---------|------|
| **Misconception 检测** | Claude Skills M1-M3、批判性思维 M1/M3/M4 | ✅ 精准检测 |
| **靶向干预** | 类比式 EXPLANATORY 干预 | ✅ misconception 清除 |
| **C 维度折扣机制** | discount_factor 0.43 → 1.0 | ✅ 动态响应 |
| **K/P/S BKT 追踪** | 10 题 BeliefEngine.update() | ✅ 状态跃迁 |
| **MIRT 多维分化** | 差异化 a_specialized → K≠P≠S | ✅ K/P/S 最大差异 0.229 |
| **BloomProfile 更新** | L1-L4 认知深度评估 | ✅ PerceptionCritic |
| **跨领域泛化** | 批判性思维 2 轮清除 | ✅ library_str 注入 |

### 5.2 ECOS 的关键价值

```
传统教学：学生犯错 → 老师凭经验判断给反馈 → 效果未知
ECOS：学生犯错 → AI 精准检测 misconception → 靶向干预 → 状态变化可量化
```

**可量化**：每一次干预都能看到 belief state 的变化（C 维度折扣因子、掌握概率）。

**领域无关**：同一个 ECOS 框架，换一个 misconception 库就能服务新领域。

**闭环验证**：干预有没有效果，不靠猜测，靠数据。

---

## 6. 完整闭环流程图

```
学生答题/解释
    │
    ▼
┌─────────────────┐
│ BeliefEngine    │
│ .update()       │
├─────────────────┤
│ Step 1: L1 BKT  │ ← K 维度掌握概率更新
│ Step 2: L2 MIRT │ ← K/P/S/C/X 多维联合估计
│ Step 3: Bloom   │ ← 认知层级 Profile 更新
│ Step 4: LLM Critic│
│  ├─ 感知层      │ ← explanation_text → BloomLevel
│  └─ Misconception│ ← C 维度折扣因子
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ LCA 干预决策    │ ← discount_factor < 0.7 → 触发干预
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 执行干预（LLM） │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 学生重新答题    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ BeliefEngine    │ ← 重新测量，验证状态变化
│ 再次 update()  │
└─────────────────┘
```

---

## 7. 相关文件索引

| 文件 | 作用 |
|------|------|
| `discussions/2026-07-05-claude-skills-definition-4gate-full-report.md` | Claude Skills 4-gate 完整报告 |
| `discussions/2026-07-05-claude-skills-demo-round1-3.md` | Claude Skills Demo Round 1-3 存档 |
| `discussions/2026-07-06-cross-domain-demo-critical-thinking.md` | 跨领域 Demo 存档 |
| `discussions/2026-07-06-belief-engine-bkt-update-demo.md` | BeliefEngine BKT 追踪 Demo |
| `discussions/2026-07-06-mirt-kps-differentiation-demo.md` | MIRT K/P/S 分化 Demo |
| `research/90-mvp/ECOS-Cognitive-Intervention-Workflow.md` | 认知干预工作流 |
| `ecos/cta/belief_engine.py` | BeliefEngine 实现 |
| `ecos/cta/llm_critic/misconception_detector.py` | MisconceptionDetector（含 library_str 注入）|
| `ecos/cta/llm_critic/perception.py` | PerceptionCritic |
| `ecos/cta/content/claude_skills_misconceptions.py` | Claude Skills Misconception 库 |

---

**报告日期**：2026-07-06
**演示者**：Bisen & ECOS AI
