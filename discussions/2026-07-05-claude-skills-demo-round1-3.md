# ECOS Claude Skills Demo 存档

**日期**：2026-07-05
**主题**：Claude Skills 认知干预闭环验证（Round 1-3）
**参与者**：Bisen（学生角色） + ECOS AI（CTA/LCA）
**对应文档**：ECA/wu-ecos README.md §案例约定

---

## Demo 背景

在正式招募学生/教师之前，用"学习 Claude Skills"作为让学校认可 ECOS 价值的演示案例。Bisen 扮演学生角色，演示 ECOS 如何：检测 misconception → 靶向干预 → 验证效果。

**5 条 Misconception（来源：`ecos/cta/content/claude_skills_misconceptions.py`）**：

| ID | 名称 | 核心误解 |
|----|------|---------|
| M1 | Skill 等于斜杠命令 | Skill 是按 description 自主加载，不是 /command 召唤 |
| M2 | Skill 等于 MCP Server | Skill 是本地 description，MCP 是外部进程调用 |
| M3 | Skill 等于自动化/Hook | Skill 是 LLM 驱动，不是自动触发脚本 |
| M4 | Skill 等于 Prompt 模板 | description 是 LLM 指令，不是填充模板 |
| M5 | Skill 总是被加载 | 加载是概率性的，由 LLM 自主判断 |

**4 闸达标标准**：

1. TC_skill 跨越（"skill 是按 description 相关性自主加载的能力，不是宏/外部进程"）
2. Bloom: Understand ≥ 0.85 AND Apply ≥ 0.75
3. Misconception 清零（M1-M5 全部消除）
4. C 是"挣来的"（伪置信 = false）

---

## Round 1：初始 Belief State 测量

### 题目：

- Q1: skill 可以用斜杠命令来直接调用。
- Q2: 我不知道 skill 跟 MCP server 有什么区别。
- Q3: description 就是 SKILL 的简介，跟 system prompt 应该不是一回事。

### Misconception 检测结果：

| 问题 | 命中 ID | 置信度 | 证据 |
|------|---------|--------|------|
| Q1 | **M1** | **0.95** | "skill可以用斜杠命令来直接调用" |
| Q2 | **M2** | **0.95** | "我不知道skill跟MCP server有什么区别" |
| Q3 | 无 | 0.0 | — |

**C 维度初始状态**：`discount_factor` 因 M1、M2 命中而下降。

---

## Round 2：干预建议生成

### CTA → LCA 策略推荐：

| Misconception | 干预类型 | 核心策略 | 类比/工具 |
|---------------|---------|---------|---------|
| M1（Skill ≠ 斜杠命令） | EXPLANATORY | deconstruct_skill_vs_slash_command | Skill = 图书馆索引卡（LLM 自主判断）；斜杠命令 = 点菜（确定性执行） |
| M2（Skill ≠ MCP Server） | EXPLANATORY | skill_is_local_description_not_external_server | Skill = 索引卡（头脑内）；MCP = 外卖系统（外部进程真实执行） |

### LCA 决策：执行 EXPLANATORY 类型干预（直接向学生解释）

---

## Round 3：干预执行 + Belief State 重新测量

### 执行的干预内容：

**M1 干预（LLM 直接对学生说）**：

> Skill 不是你"打什么它做什么"的命令，两者有本质区别：
> - 斜杠命令像是点菜——你点什么，服务员做什么，是确定性执行
> - Skill 更像是图书馆索引卡系统——当你描述问题时，LLM 自己判断哪张卡相关，主动调出来给你看
>
> **关键**：Skill 的触发是 LLM 基于 description 相关性自主判断的，不是你用斜杠"召唤"出来的

**M2 干预（LLM 直接对学生说）**：

> Skill 和 MCP Server 是完全不同的东西：
> - Skill 是本地指令——LLM 自己读、自己理解、自己决定是否调用，没有外部进程参与
> - MCP Server 是外部进程——通过协议调用真实运行在外的程序
>
> 类比：Skill 像图书馆索引卡系统（全是文字卡片，管理员自己判断）；MCP Server 像外卖订单系统（有真实的东西送过来）

### 重新检测结果：

| 问题 | Round 1 | Round 3 | 变化 |
|------|---------|---------|------|
| Q1 | M1 触发（0.95） | **未触发（0.0）** | ✅ misconception 清除 |
| Q2 | M2 触发（0.95） | **未触发（0.0）** | ✅ misconception 清除 |
| Q3 | 未触发 | 未触发 | 一致 |

**C 维度状态更新**：`discount_factor` 恢复（misconception_hits 清空）。

---

## Demo 结论

- M1 和 M2 均通过靶向干预成功清除
- ECOS 完整闭环验证通过
- 该 demo 可作为向学校展示 ECOS 认知干预价值的案例

**下一步（待人工）**：

- 正式招募学生/教师
- 用真实 K12 数学内容跑完整闭环
