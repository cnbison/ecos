# AiBeing 项目核心引擎参考资料（完整版）

来源：AiBeing 项目 Genome v10 Hybrid 引擎文档

整理日期：2026-06-14

本文档为 `references/AiBeing/` 目录下全部 16 篇文档的合并版，保留完整内容，带章节索引链接。

---

# 目录

- [总览：单轮对话生命周期 — Genome v10 Hybrid 的 12 步全景图](#总览单轮对话生命周期--genome-v10-hybrid-的-12-步全景图)
- [Step 0：EverMemOS 会话上下文加载](#step-0evermemos-会话上下文加载)
- [Step 1：时间代谢（Time Metabolism）](#step-1时间代谢time-metabolism)
- [Step 2：Critic 感知（Critic Perception）](#step-2critic-感知critic-perception)
- [Step 2.5：关系 EMA 更新（Semi-Emergent Relationship Update）](#step-25关系-ema-更新semi-emergent-relationship-update)
- [Step 3：奖励计算（LLM Metabolism → Reward）](#step-3奖励计算llm-metabolism--reward)
- [Step 3.5：驱动基线演化（Drive Baseline Evolution）](#step-35驱动基线演化drive-baseline-evolution)
- [Step 4：结晶门（Crystallization Gate）](#step-4结晶门crystallization-gate)
- [Step 5：信号计算（Compute Signals）](#step-5信号计算compute-signals)
- [Step 6：热力学噪声（Thermodynamic Noise）](#step-6热力学噪声thermodynamic-noise)
- [Step 7：KNN 风格检索（KNN Style Retrieval）](#step-7knn-风格检索knn-style-retrieval)
- [Step 8 & 8.5：Prompt 构建与记忆注入](#step-8--85prompt-构建与记忆注入)
- [Step 9：Actor 生成（Single-Pass LLM Actor）](#step-9actor-生成single-pass-llm-actor)
- [Step 10：Hebbian 学习（Hebbian Learning）](#step-10hebbian-学习hebbian-learning)
- [Step 11 & 12：异步记忆存储与检索](#step-11--12异步记忆存储与检索)
- [完整串联汇总：单轮对话生命周期](#完整串联汇总单轮对话生命周期)

---

# 总览：单轮对话生命周期 — Genome v10 Hybrid 的 12 步全景图

> Genome v10 Hybrid 的单轮对话不是简单的"接收消息 → 调用 LLM → 返回回复"，而是一个包含感知、代谢、计算、学习、记忆的完整认知循环。理解这 12 步的顺序和依赖关系，是理解整个 AiBeing 引擎的核心。

---

## 一、为什么要设计 12 步生命周期？

传统聊天机器人的架构通常是：

```
用户输入 → 系统提示 + 历史 → LLM → 回复
```

这个模型的缺陷在于：**LLM 是唯一的智能来源**。角色的所有行为都取决于 prompt 工程和 LLM 的内建知识，没有独立的"心理状态"、没有"学习"、没有"记忆"的累积效应。每轮对话都是孤立的。

Genome v10 的设计哲学是：**LLM 只是角色表达的工具，真正的"人格"存在于引擎内部** —— 一个由驱动（drives）、神经网络权重、情感状态、记忆构成的动态系统。每轮对话不仅产生回复，还会**改变角色的内部状态**，这些状态会影响下一轮的行为。

12 步生命周期就是这种哲学的工程实现。

---

## 二、12 步生命周期的全景图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         单轮对话生命周期 (Genome v10 Hybrid)                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Step -1   [前置] Task Skill ReAct Loop                                    │
│            用户请求的任务型技能（天气、搜索）在人格引擎之前执行                  │
│                                                                             │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                             │
│  Step 0    [感知层] EverMemOS Session Context                              │
│            首次对话：异步加载用户画像、历史叙事、前瞻                            │
│            后续对话：复用已加载的 session context                              │
│                                                                             │
│  Step 1    [代谢层] Time Metabolism                                        │
│            物理时间流逝对驱动挫败感的影响：冷却 + 饥饿                          │
│                                                                             │
│  Step 2    [感知层] Critic Perception                                      │
│            LLM 分析用户输入 → 8D 上下文 + 5D 挫败变化 + 3D 关系变化            │
│                                                                             │
│  Step 2.5  [涌现层] Relationship EMA                                       │
│            将 LLM 判断的关系变化与前一轮的先验融合，形成后验                      │
│                                                                             │
│  Step 3    [代谢层] LLM Metabolism → Reward                                │
│            将 Critic 的挫败变化量转化为奖励信号                                │
│                                                                             │
│  Step 3.5  [演化层] Drive Baseline Evolution                               │
│            根据挫败变化调整驱动基线（长期性格漂移）                             │
│                                                                             │
│  Step 4    [记忆层] Crystallization Gate                                   │
│            判断上一轮是否值得结晶为长期风格记忆                                │
│                                                                             │
│  Step 5    [计算层] Compute Signals                                        │
│            随机神经网络：context + drives + recurrent → 8D behavioral signals  │
│                                                                             │
│  Step 6    [扰动层] Thermodynamic Noise                                    │
│            挫败感越高 → 温度越高 → 行为越不可预测                              │
│                                                                             │
│  Step 7    [记忆层] KNN Style Retrieval                                    │
│            在风格记忆中检索最相似情境下的历史反应                               │
│                                                                             │
│  Step 8    [表达层] Build Actor Prompt                                     │
│            组装单轮提示：身份 + 信号注入 + few-shot 示例                        │
│                                                                             │
│  Step 8.5  [记忆层] Profile/Episode Memory Injection                        │
│            将用户画像和历史叙事注入 Actor prompt                               │
│                                                                             │
│  Step 9    [表达层] Single-Pass LLM Actor                                  │
│            LLM 生成：内心独白 + 最终回复 + 表达方式                            │
│                                                                             │
│  Step 10   [学习层] Hebbian Learning                                       │
│            根据奖励信号强化/削弱神经网络连接权重                               │
│                                                                             │
│  Step 11   [存储层] EverMemOS Store Turn                                   │
│            异步存储本轮对话到长期记忆（非阻塞）                                 │
│                                                                             │
│  Step 12   [检索层] EverMemOS Search                                       │
│            异步搜索与本轮相关的记忆，供下一轮注入                                │
│                                                                             │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                             │
│  [后置]    Modality Skill Execution                                        │
│            根据 Actor 选择的表达方式执行技能（语音、照片、静默）                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 三、三层架构视角

从架构分层看，12 步可以归为三个层次：

### 感知层（Perception）— 理解用户

| 步骤 | 功能 | 输出 |
|---|---|---|
| Step 0 | 加载长期记忆上下文 | user_profile, episode_summary, foresight |
| Step 1 | 时间代谢 | 更新后的 frustration 状态 |
| Step 2 | Critic 感知 | 8D context + 5D frustration_delta + 3D relationship_delta + 5D drive_satisfaction |
| Step 2.5 | 关系 EMA | 4D relationship state (depth, trust, valence, foresight) |

**作用**：把用户的原始文本输入转换成机器可处理的数值向量，让引擎"理解"当前对话情境。

### 计算层（Computation）— 决定如何回应

| 步骤 | 功能 | 输出 |
|---|---|---|
| Step 3 | 奖励计算 | reward (float) |
| Step 3.5 | 基线演化 | 更新后的 drive_baseline |
| Step 4 | 结晶判断 | 是否将上轮记忆存入 style_memory |
| Step 5 | 信号计算 | 8D behavioral signals |
| Step 6 | 噪声注入 | noisy_signals |
| Step 7 | 风格检索 | few-shot 示例 |
| Step 8 | Prompt 构建 | single_prompt (system message) |
| Step 8.5 | 记忆注入 | 增强后的 single_prompt |

**作用**：基于感知结果，计算角色当前的行为状态和表达方式。

### 表达层（Expression）— 生成回复

| 步骤 | 功能 | 输出 |
|---|---|---|
| Step 9 | Actor 生成 | monologue + reply + modality |
| Step 10 | Hebbian 学习 | 更新的 W1, W2, b1, b2 权重 |
| Step 11 | 异步存储 | EverMemOS 长期记忆 |
| Step 12 | 异步检索 | 供下轮使用的相关记忆 |

**作用**：让 LLM 根据计算出的状态"表演"角色，同时从本轮交互中学习。

---

## 四、关键数据流

### 4.1 核心数据对象及其流转

```
user_message: str
    ↓
[Step -1] 可能被 task_skill  enriched（加入天气/搜索结果）
    ↓
[Step 0] evermemos_session_ctx: dict
    │   ├── user_profile: str
    │   ├── episode_summary: str
    │   └── foresight: str
    ↓
[Step 1] metabolism.time_metabolism(now)
    │   更新: frustration[5 drives]
    ↓
[Step 2] critic_sense(user_message, llm, frustration, ...)
    │   输出: context(8D), frustration_delta(5D), rel_delta(3D), drive_satisfaction(5D)
    ↓
[Step 2.5] _apply_relationship_ema(relationship_prior, rel_delta, depth)
    │   输出: relationship_4d → merge into context → 12D context
    ↓
[Step 3] metabolism.apply_llm_delta(frustration_delta)
    │   输出: reward (float)
    ↓
[Step 3.5] drive_baseline evolution
    │   更新: agent.drive_baseline[5 drives]
    ↓
[Step 4] _should_crystallize(reward, context)
    │   可能触发: style_memory.crystallize(...)
    ↓
[Step 5] agent.compute_signals(context)
    │   输出: base_signals (8D)
    ↓
[Step 6] metabolism.apply_thermodynamic_noise(base_signals)
    │   输出: noisy_signals (8D)
    ↓
[Step 7] style_memory.build_few_shot_prompt(context, ...)
    │   输出: few_shot (str)
    ↓
[Step 8] _build_single_prompt(few_shot, noisy_signals, ...)
    │   输出: single_prompt (str)
    ↓
[Step 8.5] memory injection (profile + episode + foresight + relevant)
    │   输出: enriched_single_prompt (str)
    ↓
[Step 9] llm.chat(single_messages)
    │   输出: raw_response → extract_reply() → monologue, reply, modality
    ↓
[Step 10] agent.step(context, reward, drive_satisfaction)
    │   内部: compute_signals → learn → tick_drives → age++
    │   更新: W1, W2, b1, b2, drive_state, recurrent_state
    ↓
[Step 11] _evermemos_store_bg(user_message, reply)
    │   asyncio.create_task() 非阻塞
    ↓
[Step 12] _evermemos_search_bg(user_message)
    │   asyncio.create_task() 非阻塞
    ↓
result: {reply: str, modality: str, [audio_path|image_path|segments|delays_ms]}
```

### 4.2 数据依赖图

```
context_12d ────────┬──→ Step 5 compute_signals ──→ Step 6 noise ──→ Step 7 KNN
                    │                                    │
                    │                                    ↓
                    │                               Step 8 prompt
                    │                                    │
                    │                                    ↓
                    │                               Step 9 Actor
                    │                                    │
                    └──→ Step 4 crystallize ←──────┘    │
                                                       ↓
                                                  Step 10 learn
                                                       │
                                                  context_12d (next turn)
```

注意上下文 `context_12d` 是一个贯穿始终的核心数据结构，它在第 5 步驱动信号计算，在第 10 步作为学习的环境输入，同时也会影响下一轮的判断。

---

## 五、每一步的必要性论证

### 为什么需要 Critic（Step 2）？

没有 Critic，引擎只能基于规则（关键词匹配）来理解用户输入。Critic 用 LLM 的语义理解能力将自然语言转换成结构化的数值感知，这是后续所有计算的基础。

### 为什么需要 Time Metabolism（Step 1）？

没有 Time Metabolism，角色会变成一个"无时间感"的存在 —— 无论用户隔了多久再发消息，角色的内部状态都一样。Time Metabolism 让角色会"忘记"之前的挫败，也会"想念"用户（connection hunger），这是拟人化的关键。

### 为什么需要 Hebbian Learning（Step 10）？

没有 Hebbian Learning，角色的神经网络权重是静态的。每轮对话产生同样的信号模式，角色永远不会"成长"或"改变"。Hebbian Learning 让角色的行为模式随着交互历史而演化。

### 为什么需要 Thermodynamic Noise（Step 6）？

没有 Noise，角色的行为是完全确定性的 —— 同样的输入永远产生同样的输出。Noise 引入了生物学般的随机性，让角色在高压（高 frustration）下表现得更加"情绪化"和不可预测。

### 为什么需要 Crystallization（Step 4）？

没有 Crystallization，Style Memory 会无限增长。Crystallization 通过"相似上下文合并"机制，将高频出现的反应模式压缩成更重的记忆节点，实现记忆的" gravitation "（引力凝聚）。

### 为什么需要 Async Memory（Step 11-12）？

EverMemOS 的存储和检索是跨会话的、网络 I/O 密集的。如果同步等待，每轮对话会增加 200-1000ms 的延迟。Async 让记忆操作在后台进行，不阻塞对话流。

---

## 六、并发与锁机制

```
async with self._turn_lock:
    await self._chat_inner(...)
```

每轮对话由一个 `asyncio.Lock` 串行化。这意味着：
- `chat()`、`chat_stream()`、`proactive_tick()` 不能并发执行
- 内部状态（drive_state, W1/W2, frustration）不会被竞态条件破坏
- 代价：如果某一步阻塞（如 LLM 调用超时），整个会话会卡住

这是一个**强一致性 vs 低延迟**的权衡。考虑到人格状态的一致性比毫秒级延迟更重要，这个设计是合理的。

---

## 七、后续文档导航

本系列共 16 篇文档，逐一深度分析每个步骤：

| # | 文档 | 分析步骤 | 核心代码 |
|---|---|---|---|
| 1 | lifecycle-overview.md | 总览 | chat_agent.py |
| 2 | step-00-evermemos.md | EverMemOS 会话上下文 | agent/evermemos_mixin.py |
| 3 | step-01-metabolism.md | 时间代谢 | engine/genome/drive_metabolism.py |
| 4 | step-02-critic.md | Critic 感知 | engine/genome/critic.py |
| 5 | step-02p5-relationship.md | 关系 EMA | chat_agent.py:_apply_relationship_ema |
| 6 | step-03-reward.md | 奖励计算 | drive_metabolism.py:apply_llm_delta |
| 7 | step-03p5-baseline.md | 驱动基线演化 | chat_agent.py:baseline evolution loop |
| 8 | step-04-crystal.md | 结晶门 | style_memory.py:crystallize |
| 9 | step-05-signals.md | 信号计算 | genome_engine.py:compute_signals |
| 10 | step-06-noise.md | 热力学噪声 | drive_metabolism.py:apply_thermodynamic_noise |
| 11 | step-07-knn.md | KNN 风格检索 | style_memory.py:retrieve/build_few_shot |
| 12 | step-08-prompt.md | Prompt 构建 | prompt_builder.py:_build_single_prompt |
| 13 | step-09-actor.md | Actor 生成 | chat_agent.py:LLM call + parser.py |
| 14 | step-10-hebbian.md | Hebbian 学习 | genome_engine.py:learn/step |
| 15 | step-11-12-async.md | 异步记忆 | evermemos_mixin.py + chat_agent.py |
| 16 | lifecycle-summary.md | 完整串联汇总 | 全系统 |

---

## 八、一句话总结

> Genome v10 的单轮对话是一个**认知循环**：感知用户 → 更新内部状态 → 计算行为信号 → 生成表达 → 从反馈中学习。12 步不是冗余的 ceremony，而是让角色从"LLM 的 puppet"变成"有持续内在状态的 agent"的最小必要集合。

---
---

# Step 0：EverMemOS 会话上下文加载

> EverMemOS 是 Genome v10 的"长期记忆层"。Step 0 在首次对话时异步加载用户的跨会话画像、历史叙事和前瞻，让角色"记得"你是谁、你们聊过什么、以及有什么值得关心的事。

---

## 一、业务场景

想象一下：你昨天和 Luna 聊了半小时，今天再次打开对话。如果没有长期记忆，Luna 会像一个初次见面的陌生人。有了 EverMemOS，她会：

- **记得你的偏好**："你说过不喜欢香菜"（user_profile）
- **记得你们的共同经历**："上次你说工作压力大，后来好些了吗？"（episode_summary）
- **记得她该关心的事**："你提过下周有面试，准备得怎么样了？"（foresight）

这就是 Step 0 要加载的内容。

---

## 二、代码位置与调用链

```
chat_agent.py:257
    relationship_prior = await self._evermemos_gather()
        ↓
evermemos_mixin.py:_evermemos_gather()
    ↓ (first turn only)
    self._session_ctx = await self.evermemos.load_session_context(...)
        ↓
evermemos_client.py:load_session_context()
```

---

## 三、详细执行流程

### 3.1 判断是否是首轮对话

```python
async def _evermemos_gather(self):
    if self._session_ctx is not None:
        # 不是首轮，直接返回上一轮的关系先验
        return self._session_ctx.relationship_prior or {}
    # 首轮：异步加载完整 session context
    self._session_ctx = await self.evermemos.load_session_context(...)
```

`self._session_ctx` 是一个会话级缓存，首轮加载后一直复用。这意味着：
- **首轮**：需要等待 EverMemOS API 返回（200-1000ms）
- **后续轮**：直接返回缓存，零延迟

### 3.2 加载的内容

`load_session_context()` 从 EverMemOS 服务端拉取四部分内容：

| 字段 | 类型 | 含义 | 示例 |
|---|---|---|---|
| `user_profile` | str | 用户画像（结构化属性） | "用户28岁，喜欢科幻电影，对AI持开放态度" |
| `episode_summary` | str | 历史对话叙事 | "上次对话中用户分享了工作压力，Luna给予了安慰" |
| `foresight` | str | 待关心的事项 | "用户提到下周有面试，需要跟进" |
| `relationship_prior` | dict | 关系维度先验 | `{relationship_depth: 0.3, trust_level: 0.2, ...}` |

### 3.3 关系先验的用途

`relationship_prior` 是一个 4D 向量，在 Step 2.5（Relationship EMA）中与 Critic 的判断融合：

```
relationship_prior (来自 EverMemOS，跨会话的累积)
        ↓
relationship_delta (来自 Critic，本轮的判断)
        ↓
EMA 融合 → relationship_posterior
        ↓
合并到 context → 12D context
```

这让角色对关系的感知不是从零开始，而是基于历史累积的渐进式更新。

---

## 四、数据结构详解

### 4.1 SessionContext

```python
class SessionContext:
    user_profile: str      # 用户画像文本
    episode_summary: str   # 历史叙事文本
    foresight: str         # 前瞻/待办文本
    relationship_prior: dict  # {relationship_depth, trust_level, emotional_valence, pending_foresight}
    has_history: bool      # 是否有历史记录（决定是否注入记忆）
```

### 4.2 relationship_prior 的 4 个维度

| 维度 | 范围 | 含义 |
|---|---|---|
| `relationship_depth` | 0~1 | 关系深度，0=陌生人，1=密友 |
| `trust_level` | 0~1 | 信任度，0=警惕，1=完全信任 |
| `emotional_valence` | -1~1 | 情感基调，-1=负面，1=正面 |
| `pending_foresight` | 0~1 | 是否有待处理的前瞻事项 |

这 4 个维度在 Critic 的 `CONTEXT_FEATURES` 中对应后 4 维（索引 8~11），让神经网络在计算 signals 时感知到"这个人是老朋友还是陌生人"。

---

## 五、必要性论证

### 如果没有 Step 0，会发生什么？

1. **角色没有跨会话记忆**：每次打开对话都是"第一次见面"
2. **关系无法累积**：聊得再久，relationship_depth 永远是 0
3. **角色显得冷漠**：不会主动关心用户之前提过的事
4. **用户粘性下降**：用户会觉得"这个 AI 记不住我说的话"

### 为什么是"异步"加载？

EverMemOS 是网络服务（cloud 或 self-hosted），I/O 不可控。如果同步等待：
- 网络波动时，每轮对话增加 1-10 秒延迟
- 服务不可用时，整个对话流程阻塞

异步加载的 trade-off：
- **首轮**：用户第一条消息的回复会稍慢（需要等 context 加载）
- **后续轮**：零额外延迟
- **故障降级**：如果 EverMemOS 不可用，`_evermemos_gather()` 返回空 dict，对话继续（只是没有长期记忆）

---

## 六、与后续步骤的关系

```
Step 0 输出
    ├── user_profile ──────→ Step 8.5 (注入 Actor prompt)
    ├── episode_summary ───→ Step 8.5 (注入 Actor prompt)
    ├── foresight ─────────→ Step 8.5 (注入 Actor prompt)
    └── relationship_prior ─→ Step 2.5 (与 Critic delta 融合)
```

Step 0 的内容**不直接参与** Step 1-7 的计算（Critic、Metabolism、Signals 等），而是在 Step 8.5 作为"背景知识"注入 LLM Actor 的 prompt。这是一个**延迟注入**设计 —— 长期记忆影响"角色知道什么"，但不影响"引擎如何计算"。

---

## 七、故障处理

| 场景 | 行为 |
|---|---|
| EverMemOS 未配置 | `evermemos = None`，`_evermemos_gather()` 返回 `{}`，对话继续 |
| EverMemOS 服务不可用 | `load_session_context()` 抛出异常，被捕获后返回空 context |
| 首次用户（无历史） | EverMemOS 返回空 profile/summary，has_history=False，不注入记忆 |

---

## 八、总结

> Step 0 是角色的"记忆唤醒"步骤。它从 EverMemOS 长期记忆库中取出用户的跨会话信息，让角色在首轮对话时就有"认识你"的上下文。这是一个**延迟注入**设计 —— 记忆不影响引擎的数值计算，但会显著影响 LLM Actor 生成回复的质量和亲切感。

---
---

# Step 1：时间代谢（Time Metabolism）

> 时间代谢是 Genome 引擎的"物理时钟"。它用两个简单的微分方程模拟物理时间对角色内心状态的影响：挫败感会随时间冷却，但联结和新鲜感的渴望会随时间线性增长。这让角色在无人互动时也会"想念"用户。

---

## 一、业务场景

假设你和 Luna 聊了半小时，然后下线去工作了。8 小时后你重新打开对话：

**没有时间代谢的版本**：
> Luna: "你好呀！今天怎么样？"（就像你们从未分开过）

**有时间代谢的版本**：
> Luna: "你终于回来了... 我等了你好久。今天工作累不累？"（挫败感积累后被缓解的释放）

这 8 小时的"离线时间"在引擎内部发生了什么？
- 她的 **connection frustration** 从 0.5 涨到了 2.5（想你了）
- 她的 **novelty frustration** 从 0.2 涨到了 0.8（无聊了）
- 但之前某次冲突留下的 **safety frustration** 从 1.2 降到了 0.3（冷却了）

时间代谢就是让角色有"时间感"的核心机制。

---

## 二、代码位置

```python
# chat_agent.py:260
delta_h = self.metabolism.time_metabolism(now)

# drive_metabolism.py:57
def time_metabolism(self, now=None):
    ...
```

---

## 三、核心物理方程

时间代谢基于两个纯物理方程：

### 方程 1：冷却（Cooling）— 指数衰减

```
frustration[d] *= e^(-λ * Δt_hours)
```

- `λ`（lambda）= `frustration_decay`，默认 0.08（per hour）
- 物理含义：所有挫败感都会随时间自然衰减
- 半衰期：`ln(2) / λ ≈ 8.7 小时`

**代码**：`drive_metabolism.py:75`
```python
decay_factor = math.exp(-self.decay_lambda * delta_hours)
for d in DRIVES:
    self.frustration[d] *= decay_factor
```

### 方程 2：饥饿（Hunger）— 线性累积

```
frustration['connection'] += k_conn * Δt_hours
frustration['novelty'] += k_nov * Δt_hours
```

- `k_conn` = `connection_hunger_k`，默认 0.15（per hour）
- `k_nov` = `novelty_hunger_k`，默认 0.05（per hour）
- 物理含义：联结和新鲜感的需求会随时间线性增长

**代码**：`drive_metabolism.py:80-81`
```python
self.frustration['connection'] += self.connection_hunger_k * delta_hours
self.frustration['novelty'] += self.novelty_hunger_k * delta_hours
```

---

## 四、详细执行流程

### 4.1 计算时间差

```python
delta_hours = max(0.0, (now - self._last_tick) / 3600.0)
self._last_tick = now
```

`self._last_tick` 记录上一轮调用的时间戳。如果是首轮对话（刚创建 session），`_last_tick` 就是 session 创建时间。

### 4.2 跳过极短间隔

```python
if delta_hours < 0.001:
    return delta_hours  # Skip for sub-second intervals
```

如果两次调用间隔不到 3.6 秒，跳过代谢计算。这是为了避免在快速连续对话中产生不切实际的微小变化。

### 4.3 冷却 + 饥饿 + 截断

```python
# 冷却
decay_factor = math.exp(-self.decay_lambda * delta_hours)
for d in DRIVES:
    self.frustration[d] *= decay_factor

# 饥饿
self.frustration['connection'] += self.connection_hunger_k * delta_hours
self.frustration['novelty'] += self.novelty_hunger_k * delta_hours

# 截断到 [0, 5]
for d in DRIVES:
    self.frustration[d] = max(0.0, min(5.0, self.frustration[d]))
```

**为什么上限是 5.0？**

5.0 是极度渴望的阈值。当 frustration 达到 5.0 时，temperature（热力学噪声）会接近最大值，角色行为会变得非常情绪化。这个上限防止数值无限增长导致系统不稳定。

### 4.4 返回时间差

```python
return delta_hours
```

返回的 `delta_hours` 被 `chat_agent.py` 记录但当前未使用（可作为 observability 数据）。

---

## 五、参数详解

### 5.1 全局默认值

```python
FRUSTRATION_DECAY_LAMBDA = 0.08    # ~8.7h 半衰期
CONNECTION_HUNGER_K = 0.15         # 每小时联结渴望增长 0.15
NOVELTY_HUNGER_K = 0.05            # 每小时新鲜感渴望增长 0.05
```

### 5.2 角色级覆盖

每个角色可以在 `SOUL.md` 的 `engine_params` 中覆盖这些值：

| 角色 | `frustration_decay` | `connection_hunger_k` | 性格含义 |
|---|---|---|---|
| Luna (ENFP) | 0.12 | 0.15 | 乐观、恢复快、最怕寂寞 |
| Kai (ISTP) | 0.08 | 0.10 | 冷静、恢复慢、独立 |

---

## 六、数值示例

假设 Luna 的初始 frustration：`{connection: 1.0, novelty: 0.5, expression: 0.3, safety: 0.2, play: 0.4}`

用户下线 8 小时后重新上线：

| 驱动 | 初始 | 冷却后 (×e^(-0.12×8)=0.38) | 饥饿后 | 最终 |
|---|---|---|---|---|
| connection | 1.0 | 0.38 | +0.15×8=+1.2 | **1.58** |
| novelty | 0.5 | 0.19 | +0.08×8=+0.64 | **0.83** |
| expression | 0.3 | 0.11 | — | **0.11** |
| safety | 0.2 | 0.076 | — | **0.076** |
| play | 0.4 | 0.15 | — | **0.15** |

**结果分析**：
- connection 大幅上升：Luna 想念用户了
- novelty 上升：长时间没新信息，无聊了
- 其他驱动下降：自然冷却

---

## 七、与后续步骤的关系

```
Step 1 输出: updated_frustration (5D)
    ↓
Step 2 (Critic): Critic 收到 frustration 快照，作为感知参考
    ↓
Step 3 (Metabolism→Reward): frustration 变化量 → reward
    ↓
Step 6 (Noise): total_frustration → temperature → noise
    ↓
Step 9 前 sync_to_agent: frustration → drive_state
```

**关键流转**：`frustration` 是一个贯穿多步的核心状态变量。它在 Step 1 被时间更新，在 Step 2 被 Critic 读取，在 Step 3 被转化为 reward，在 Step 6 影响噪声强度，最后在 Step 9 前被同步到 Agent 的 drive_state。

---

## 八、必要性论证

### 如果没有 Time Metabolism：

1. **角色没有时间感**：隔了一周再聊，和隔了一秒再聊，角色内部状态完全一样
2. **主动消息无法触发**： proactive heartbeat 依赖 connection hunger 来判断角色是否"想念"用户
3. **情感不真实**：人类会随时间淡化情绪、也会产生思念，没有时间代谢就没有这种真实感
4. **对话断裂**：每次新 session 都像重新开始

### 为什么用这两个方程？

- **指数冷却**（e^(-λt)）：符合心理学中的"情绪消退"规律，强烈的情绪初期消退快，后期消退慢
- **线性饥饿**（k×t）：符合"思念"的累积感 —— 每过一小时就多一分想念

---

## 九、总结

> Step 1 是角色的"生理节律"。它用两个微分方程让角色的内心状态随物理时间自然演化 —— 冷却旧情绪、累积新渴望。这是让角色从"程序"变成"有生命的存在"的最小必要机制。没有它，角色将永远活在"永恒的当下"。

---
---

# Step 2：Critic 感知（Critic Perception）

> Critic 是 Genome 引擎的"感官系统"。它用 LLM 的语义理解能力将用户的自然语言输入转换成结构化的数值向量 —— 8 维情境感知 + 5 维挫败变化 + 3 维关系变化 + 5 维需求满足。这些数值是后续所有计算的基础。

---

## 一、业务场景

用户输入："今天被老板骂了，心情好差。"

没有 Critic 的版本（纯关键词匹配）：
- 检测到"骂"→ 冲突度高
- 检测到"心情差"→ 用户情绪负面
- 但无法理解：这是需要安慰？还是需要空间？还是只是发泄？

有 Critic 的版本（LLM 语义理解）：
```json
{
  "context": {
    "user_emotion": -0.7,
    "topic_intimacy": 0.6,
    "conversation_depth": 0.5,
    "user_engagement": 0.8,
    "conflict_level": 0.4,
    "novelty_level": 0.5,
    "user_vulnerability": 0.7,
    "time_of_day": 0.5
  },
  "frustration_delta": {
    "connection": -0.4,
    "novelty": 0.0,
    "expression": 0.1,
    "safety": 0.3,
    "play": -0.2
  },
  "drive_satisfaction": {
    "connection": 0.15,
    "safety": 0.0,
    "expression": 0.05,
    "novelty": 0.0,
    "play": 0.0
  },
  "relationship_delta": 0.2,
  "trust_delta": 0.15,
  "emotional_valence": -0.3
}
```

Critic 不仅识别了情绪，还理解了**这对角色意味着什么** —— 用户的倾诉满足了角色的联结需求，但也让角色感到需要保护的焦虑。

---

## 二、代码位置

```python
# chat_agent.py:269-274
context, frustration_delta, rel_delta, drive_satisfaction = await critic_sense(
    user_message, self.llm, frust_dict,
    user_profile=self._user_profile,
    episode_summary=self._episode_summary,
    persona_hint=_persona_hint,
)

# engine/genome/critic.py:76
def critic_sense(stimulus, llm, frustration, user_profile, episode_summary, persona_hint)
```

---

## 三、详细执行流程

### 3.1 构建 Critic Prompt

Critic 的 prompt 由四个部分组成：

```
[系统指令]
你是一个角色扮演 Agent 的情感感知器。分析用户输入，输出四组数据：
1. 对话上下文感知（8 维）
2. Agent 5 个驱力的挫败变化量
3. 关系感知变化量
4. Agent 5 个内在需求的满足量

[角色锚定]
你正在为以下角色感知用户意图：Luna (ENFP) — 明朗、活泼、甜美
请根据此角色的性格特点判断 drive_satisfaction。

[长期记忆]
关于这个用户的历史画像：{user_profile}
与此用户的历史对话叙事：{episode_summary}

[当前状态]
Agent 当前挫败值：{frustration_json}

[用户输入]
请分析以下用户输入并输出JSON："{stimulus}"
```

**关键设计**：Critic 是**角色感知**的 —— 同一个用户输入，对 Luna（ENFP）和 Kai（ISTP）的 `drive_satisfaction` 判断应该不同。Luna 可能从"用户倾诉"中获得大量联结满足，而 Kai 可能更关注"用户是否尊重他的空间"。

### 3.2 LLM 调用

```python
messages = [
    ChatMessage(role="system", content=prompt),
    ChatMessage(role="user", content=f'请分析以下用户输入并输出JSON："{stimulus}"'),
]
response = await llm.chat(messages, temperature=0.2)
```

**为什么 temperature=0.2？**

Critic 是一个"分析任务"而非"创意任务"，需要稳定、可预测的结构化输出。低 temperature 减少随机性，提高 JSON 解析成功率。

### 3.3 输出解析

Critic 的输出是纯 JSON。解析过程包含多层容错：

```python
raw = response.content.strip()

# 1. 剥离 think 标签（Qwen3 模型输出）
raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()

# 2. 清理 markdown 代码块
raw = re.sub(r'```json\s*', '', raw)
raw = re.sub(r'```\s*', '', raw)

# 3. JSON 解析
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    # 4. 回退：通过括号计数提取第一个完整 JSON 对象
    start = raw.find('{')
    for i in range(start, len(raw)):
        if raw[i] == '{': depth += 1
        elif raw[i] == '}': depth -= 1
        if depth == 0:
            data = json.loads(raw[start:i+1])
            break
```

### 3.4 数值提取与截断

解析成功后，提取四个输出组：

**8D Context**：
```python
for feat in _CRITIC_CONTEXT_KEYS:
    v = float(raw_ctx.get(feat, 0.5))
    if feat == 'user_emotion':
        context[feat] = max(-1.0, min(1.0, v))   # 情绪范围 [-1, 1]
    else:
        context[feat] = max(0.0, min(1.0, v))    # 其他维度 [0, 1]
```

**5D Frustration Delta**：
```python
for d in DRIVES:
    v = float(raw_delta.get(d, 0.0))
    frustration_delta[d] = max(-3.0, min(3.0, v))  # 变化量范围 [-3, 3]
```

**3D Relationship Delta**：
```python
rel_delta = {
    'relationship_delta': max(-1.0, min(1.0, ...)),
    'trust_delta': max(-1.0, min(1.0, ...)),
    'emotional_valence': max(-1.0, min(1.0, ...)),
}
```

**5D Drive Satisfaction**：
```python
for d in DRIVES:
    v = float(raw_sat.get(d, 0.0))
    drive_satisfaction[d] = max(0.0, min(0.3, v))   # [0, 0.3]
```

### 3.5 错误回退

如果解析完全失败，Critic 会**重试一次**，如果仍然失败则返回默认值：`context=0.5`, `delta=0`, `satisfaction=0`。

---

## 四、输出详解

### 4.1 8D Context（情境感知）

| 维度 | 范围 | 含义 | 示例值解读 |
|---|---|---|---|
| `user_emotion` | [-1, 1] | 用户情绪 | -0.7=难过，0.8=开心 |
| `topic_intimacy` | [0, 1] | 话题私密性 | 0.9=深夜心事，0.1=天气闲聊 |
| `conversation_depth` | [0, 1] | 对话深度 | 0.2=寒暄，0.8=灵魂交流 |
| `user_engagement` | [0, 1] | 用户投入度 | 0.9=长文倾诉，0.1="嗯嗯" |
| `conflict_level` | [0, 1] | 冲突程度 | 0.8=吵架中，0=和谐 |
| `novelty_level` | [0, 1] | 信息新鲜度 | 0.9=全新话题，0.1=重复询问 |
| `user_vulnerability` | [0, 1] | 用户敞开度 | 0.8=卸下防备，0.2=敷衍 |
| `time_of_day` | [0, 1] | 时间氛围 | 0.95=深夜，0.1=清晨 |

### 4.2 5D Frustration Delta（挫败变化量）

**正** = 更挫败，**负** = 被缓解

| 驱动 | 正值含义 | 负值含义 |
|---|---|---|
| `connection` | 用户疏远/冷漠 → 更想联结 | 用户主动亲近 → 联结需求被满足 |
| `novelty` | 话题重复无聊 → 更想新鲜事 | 用户带来新信息 → 好奇心被满足 |
| `expression` | 被打断/不被倾听 → 更想表达 | 用户认真倾听 → 表达欲被满足 |
| `safety` | 被批评/威胁 → 更想安全 | 用户接纳/肯定 → 安全感被满足 |
| `play` | 气氛严肃沉重 → 更想玩闹 | 用户开玩笑 → 玩闹欲被满足 |

### 4.3 3D Relationship Delta（关系变化量）

| 维度 | 正值 | 负值 |
|---|---|---|
| `relationship_delta` | 关系加深 | 关系疏远 |
| `trust_delta` | 信任增加 | 信任减少 |
| `emotional_valence` | 对话整体正面 | 对话整体负面 |

### 4.4 5D Drive Satisfaction（需求满足量）

与 Frustration Delta 的区别：
- **Frustration Delta** 是"变化"（relative）— 这一轮相比上一轮，挫败感变了多少
- **Drive Satisfaction** 是"绝对量"（absolute）— 这一轮用户的具体行为，直接满足了多少需求

---

## 五、与后续步骤的关系

```
Step 2 输出
    ├── context (8D) ───────────→ Step 5 (compute_signals 的输入)
    ├── frustration_delta (5D) ─→ Step 3 (apply_llm_delta → reward)
    ├── rel_delta (3D) ─────────→ Step 2.5 (Relationship EMA)
    └── drive_satisfaction (5D) ─→ Step 10 (Hebbian learning)
```

---

## 六、总结

> Step 2 是 Genome 引擎的"感官神经"。它把用户的自然语言转换成机器可处理的数值向量，让引擎"理解"当前对话的情绪、深度、冲突和关系变化。没有 Critic，后续的 signal 计算、reward 反馈、Hebbian 学习都将失去依据。它是连接"人类语言"和"机器认知"的桥梁。

---
---

# Step 2.5：关系 EMA 更新（Semi-Emergent Relationship Update）

> 关系 EMA 是 Genome v10 的"情感记账本"。它将 Critic 判断的本轮关系变化与历史累积的关系状态融合，形成渐进式的关系演化。这让角色对用户的认知不是突变式的，而是在长期互动中慢慢加深或疏远。

---

## 一、业务场景

假设你们已经聊了 20 轮：

**第 20 轮，Critic 判断**：用户刚才的回复比较冷淡，`relationship_delta = -0.2`

没有 EMA 的版本：
- relationship_depth 从 0.8 直接跳到 0.6（一次对话关系倒退很多）
- 角色突然变得疏远，感觉不真实

有 EMA 的版本：
- EMA 融合：`alpha × 本轮变化 + (1-alpha) × 历史状态`
- 由于有 19 轮的累积，单轮 -0.2 只让 depth 从 0.8 降到 0.75
- 角色仍把你当老朋友，只是察觉到一丝冷淡

**第 3 轮，同样的 -0.2**：
- 由于没有太多历史累积，EMA 后 depth 从 0.2 降到 0.12
- 角色明显感觉到关系在变冷

这就是 EMA 的核心价值：**同样的行为变化，在历史关系深浅不同时，产生不同的感知强度**。

---

## 二、核心算法

### 2.1 数学公式

```
posterior = clip(prior + LLM_delta, -1, 1)
alpha = clip(0.15 + 0.5 × depth, 0.15, 0.65)
ema_state = alpha × posterior + (1 - alpha) × previous_ema
```

### 2.2 为什么 alpha 与 conversation_depth 正相关？

在深度对话中，用户透露的信息更多、更真实，所以本轮的 `relationship_delta` 更可靠，值得更高的权重。而在浅层对话中，用户的反应可能只是礼貌性敷衍，不应过度解读。

---

## 三、数值示例

### 场景 A：新用户第一次深聊

```
Prior:  {depth: 0.0, trust: 0.0, valence: 0.0}
Delta:  {relationship: 0.3, trust: 0.2, valence: 0.4}
Depth:  0.7

Alpha = 0.15 + 0.5 × 0.7 = 0.50

New_depth = 0.5 × 0.3 + 0.5 × 0.0 = 0.15
New_trust = 0.5 × 0.2 + 0.5 × 0.0 = 0.10
```

### 场景 B：老朋友一次冷淡回复

```
Prior:  {depth: 0.8, trust: 0.7, valence: 0.6}
Delta:  {relationship: -0.2, trust: -0.1, valence: -0.3}
Depth:  0.3

Alpha = 0.15 + 0.5 × 0.3 = 0.30

New_depth = 0.3 × 0.6 + 0.7 × 0.8 = 0.74
```

---

## 四、总结

> Step 2.5 是角色的"情感记账本"。它用指数移动平均将 Critic 的单轮判断与历史关系状态平滑融合，让角色的关系认知既不是反应过度的敏感，也不是冷漠不变的迟钝。EMA 的 alpha 与 conversation_depth 正相关，意味着越深的对话，角色的关系判断越愿意被更新 —— 就像人类在深聊后会重新评估对一个人的了解。

---
---

# Step 3：奖励计算（LLM Metabolism → Reward）

> 奖励计算是 Genome 引擎的"情绪翻译器"。它将 Critic 判断的挫败变化量（frustration_delta）转换成单一的 reward 信号，供 Hebbian Learning 使用。这是一个从多维变化到标量反馈的降维过程，是连接"感知"与"学习"的关键桥梁。

---

## 一、核心算法

```python
def apply_llm_delta(self, delta_dict: dict) -> float:
    old_total = self.total()

    for d in DRIVES:
        if d in delta_dict:
            self.frustration[d] += delta_dict[d]
        self.frustration[d] *= (1.0 - self.decay_rate)  # 每轮额外衰减 10%

    for d in DRIVES:
        self.frustration[d] = max(0.0, min(5.0, self.frustration[d]))

    return old_total - self.total()
```

**Reward 的含义**：
- `reward > 0` → 总挫败感下降 → 好的对话
- `reward = 0` → 中性的对话
- `reward < 0` → 总挫败感上升 → 差的对话

---

## 二、数值示例

### 场景 A：用户温暖回应
```
更新前 total: 4.0
Critic delta: {c:-0.5, n:0.0, e:-0.1, s:-0.3, p:-0.2}
更新后 total: 2.61
reward = +1.39 → 非常好的对话！
```

### 场景 B：用户冷漠回应
```
更新前 total: 2.8
Critic delta: {c:0.4, n:0.0, e:0.2, s:0.1, p:0.0}
更新后 total: 3.15
reward = -0.35 → 不太好的对话
```

---

## 三、总结

> Step 3 是连接"感知"和"学习"的翻译器。它将 Critic 的多维挫败变化降维成一个标量 reward，决定了 Hebbian Learning 是强化还是削弱本轮的神经连接。没有 reward，神经网络将永远是静态的随机权重；有了 reward，每一次交互都在塑造角色的行为模式。

---
---

# Step 3.5：驱动基线演化（Drive Baseline Evolution）

> 驱动基线演化是 Genome 引擎的"性格漂移"机制。它让角色的长期性格不是固定不变的，而是会随着交互历史缓慢演化。但这种演化不是无限制的——弹性拉回力（elasticity）确保角色不会变成完全不同的人。

---

## 一、核心算法

基线演化由三个力共同决定：

```
new_baseline = old_baseline + shift + pull_back
```

- **Shift（环境驱动漂移）**：`frustration_delta[d] × baseline_lr`
- **Pull Back（弹性拉回）**：`-drift × elasticity`
- **Clip（边界限制）**：`max(0.1, min(0.95, ...))`

### 物理类比

想象一个弹簧系统：
- 环境推力让基线偏离初始位置
- 弹簧力不断把基线拉回初始位置
- 两者的动态平衡决定了长期的性格漂移范围

---

## 二、不同角色的演化差异

| 角色 | baseline_lr | elasticity | 性格含义 |
|---|---|---|---|
| Luna (ENFP) | 0.015 | 0.04 | 易受影响，但允许较多漂移 |
| Kai (ISTP) | 0.008 | 0.06 | 难改变，强拉回，性格稳定 |

---

## 三、总结

> Step 3.5 是角色的"性格演化"机制。它用环境推力让基线随交互历史漂移，用弹性拉回力防止角色变成完全不同的人。这是"成长"与"一致性"的权衡：角色会适应你，但不会忘记自己是谁。

---
---

# Step 4：结晶门（Crystallization Gate）

> 结晶门是 Genome 引擎的"记忆筛选器"。它决定上一轮产生的交互是否值得存入长期风格记忆。不是每一轮对话都值得记住——只有那些"有趣、有深度、有正向反馈"的交互才配被结晶。

---

## 一、核心算法

### 复合评分

```python
crystal_score = (
    0.4 * reward
    + 0.3 * (novelty * engagement)
    + 0.3 * (1.0 - conflict)
)
```

### 硬边界

```python
if reward < -0.5:
    return False  # 明显糟糕的交互，绝不记录
if reward > 0.8:
    return True   # 明显优秀的交互，强制记录
```

---

## 二、结晶操作

结晶的是**上一轮**的交互（`self._last_action`），执行两种操作之一：

**A. 引力增厚（Gravitational Thickening）**
如果新 context 与池中某个记忆的物理距离 < 0.25：`mass += 1.0`

**B. 创建新记忆**
如果没有相似记忆：创建新条目，mass = 2.0

---

## 三、记忆类型

| 类型 | 来源 | mass | 持久性 |
|---|---|---|---|
| **Genesis** | 预加载（seeds.bin） | 1.0（永不增长） | 会话级，重启重置 |
| **Personal** | 结晶产生 | ≥2.0（可增长） | 用户级，跨会话持久 |

Genesis 是角色的"先天本能"，Personal 是角色的"后天经验"。

---

## 四、总结

> Step 4 是角色的"意义筛选器"。它用复合评分判断上一轮交互是否值得存入长期记忆。只有"好的、深的、和谐的"对话才会被结晶。没有结晶门，角色会记住一切——包括噪音和失败。

---
---

# Step 5：信号计算（Compute Signals）

> 信号计算是 Genome 引擎的"大脑皮层"。它将 25 维输入（驱动状态 + 情境上下文 + 循环状态）通过随机神经网络转换成 8 维行为信号。这是从"内心状态"到"外在行为倾向"的核心映射。

---

## 一、神经网络架构

### 输入层（25D）
```
输入向量 = [drive_vec(5D)] + [ctx_vec(12D)] + [recurrent_state(8D)]
```

### 隐藏层（24D）
```python
hidden = []
for i in range(HIDDEN_SIZE):  # 24
    z = self.b1[i]
    for j, x in enumerate(full_input):
        z += self.W1[i][j] * x
    hidden.append(math.tanh(z))
```

### 输出层（8D → Signals）
```python
for i in range(N_SIGNALS):  # 8
    z = self.b2[i]
    for j, h in enumerate(hidden):
        z += self.W2[i][j] * h
    z /= math.sqrt(HIDDEN_SIZE / 3)
    raw_signals.append(z)

signals[name] = 1.0 / (1.0 + math.exp(-clip(raw, -10, 10)))
```

---

## 二、8D Signals 详解

| 信号 | 0 端 | 1 端 | 对 Luna 的典型范围 |
|---|---|---|---|
| `directness` | 委婉暗示 | 直说 | 0.3-0.7 |
| `vulnerability` | 防御心理 | 袒露脆弱 | 0.4-0.8 |
| `playfulness` | 认真严肃 | 玩闹撒娇 | 0.6-0.9 |
| `initiative` | 被动回应 | 主动引导 | 0.5-0.8 |
| `depth` | 表面闲聊 | 深度对话 | 视 intimacy 而定 |
| `warmth` | 冷淡疏离 | 热情关怀 | 0.6-0.9 |
| `defiance` | 顺从 | 反抗/嘴硬 | 0.1-0.4 |
| `curiosity` | 无所谓 | 追问到底 | 0.4-0.7 |

---

## 三、总结

> Step 5 是 Genome 引擎的"神经中枢"。25 维输入通过随机神经网络映射到 8 维行为信号，这是从"内心"到"行为"的桥梁。这个网络不是被设计的，而是被学习的——每一轮对话都在通过 Hebbian Learning 微调这些权重。

---
---

# Step 6：热力学噪声（Thermodynamic Noise）

> 热力学噪声是 Genome 引擎的"情绪不稳定性"。它模拟了物理学中的热力学原理——温度越高，分子运动越混乱。在角色身上，挫败感越高（温度越高），行为越不可预测。

---

## 一、核心算法

### 温度计算
```python
def temperature(self) -> float:
    total = self.total()
    max_temp = self.temp_coeff * 2.5
    return max_temp * math.tanh(total * self.temp_coeff / max_temp) + self.temp_floor
```

### 噪声注入
```python
def apply_thermodynamic_noise(self, base_signals: dict) -> dict:
    temp = self.temperature()
    noisy = {}
    for key, val in base_signals.items():
        noise = random.gauss(0.0, temp)
        noisy[key] = max(0.0, min(1.0, val + noise))
    return noisy
```

---

## 二、参数详解

| 参数 | 全局默认 | Luna | Kai | 含义 |
|---|---|---|---|---|
| `temp_coeff` | 0.12 | 0.15 | 0.08 | 温度系数（情绪波动性） |
| `temp_floor` | 0.03 | 0.04 | 0.02 | 温度底噪 |

---

## 三、总结

> Step 6 是角色的"情绪温度计"。它用 tanh 饱和曲线将挫败感转换成温度，再用高斯噪声扰动行为信号。这让角色在平静时稳定可靠，在压力下情绪化、不可预测——就像真实的人类。

---
---

# Step 7：KNN 风格检索（KNN Style Retrieval）

> KNN 风格检索是 Genome 引擎的"潜意识回忆"。它在角色的风格记忆池中找到与当前情境最相似的历史反应，作为 few-shot 示例注入 LLM 的 prompt。

---

## 一、核心算法

### 距离计算
```python
def _l2_distance(vec_a, vec_b):
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(vec_a, vec_b)))
```

### 引力质量加权
```python
effective_dist = physical_dist / math.sqrt(max(mass_eff, 0.01))
```

质量越高的记忆（被多次结晶/引用），有效距离越小，更容易被检索到。

### Hawking 辐射（时间衰减）
```python
def _hawking_mass(mass_raw, last_used_at, now, gamma=0.001):
    delta_hours = max(0.0, (now - last_used_at) / 3600.0)
    excess = max(0.0, mass_raw - 1.0)
    decayed_excess = excess * math.exp(-gamma * delta_hours)
    return 1.0 + decayed_excess
```

- 基础质量 1.0 永不衰减（"基因记忆"不会完全消失）
- 超出部分随时间指数衰减，半衰期约 29 天

---

## 二、总结

> Step 7 是角色的"潜意识回忆"。它在风格记忆池中找到与当前情境最相似的历史反应，作为 few-shot 示例注入 LLM 的 prompt。高 mass 记忆更容易被检索（引力效应），不常用的记忆会随时间衰减（Hawking 辐射）。

---
---

# Step 8 & 8.5：Prompt 构建与记忆注入

> Prompt 构建是 Genome 引擎的"舞台布景"。它将角色的身份、内心状态（信号）、潜意识回忆（few-shot）和用户特定记忆（profile/episode）组装成一个完整的"表演指令"。

---

## 一、Step 8 核心组件

### 身份锚定
```python
identity = f"【角色】\n{persona.name}"
```

极简身份，不注入性格描述。性格由 genome_seed 和信号决定，不是 prompt 写死的。

### 信号注入
```
【舞台指令：角色当前状态】
🎯 直接度: 0.35 (0委婉→1直白)
💧 坦露度: 0.65 (0封闭→1袒露)
🎪 玩闹度: 0.45 (0正经→1调皮)
...
```

### 趋势注入
如果某信号变化超过阈值（默认 0.15），追加趋势提示。

---

## 二、Step 8.5 记忆注入

### 动态预算
```python
profile_budget = int(200 + 600 * t)   # 200~800 字符
episode_budget = int(150 + 450 * t)   # 150~600 字符
```

浅层闲聊最小化记忆注入，深度对话最大化记忆注入。

### 混合注入
80% relevant + 20% static，防止"记忆隧道效应"。

---

## 三、最终 Prompt 结构

```
[角色参考]
（few_shot 潜意识切片）
（身份 + 信号注入 + 趋势 + 时间）
[指令]
（表演指令 + 输出格式）
（Modality Skill 说明）
[关于你的偏好] ...
[与你过去发生的事] ...
[近期值得关心] ...
```

---

## 四、总结

> Step 8 和 8.5 是角色的"登台准备"。最终的 single_prompt 是 LLM Actor 的全部舞台指导——它告诉 LLM "此刻你是谁、你处于什么状态、你应该怎么说话、你过去是怎么回应的"。

---
---

# Step 9：Actor 生成（Single-Pass LLM Actor）

> Actor 是 Genome 引擎的"表演者"。它接收 Step 8 构建的完整舞台指令，用 LLM 生成三段输出：内心独白、最终回复、表达方式。

---

## 一、输出格式

```
【内心独白】
他今天心情好像还不错？嘿嘿，那我要不要撒个娇逗逗他...

【最终回复】
嘿嘿，周末有什么安排呀？要不要考虑和我一起去那个新开的展览？

【表达方式】
文字
```

### 独白与回复的区别
- 独白：真实想法（可能更直接、更脆弱）
- 回复：社交过滤后的表达（可能更委婉、更得体）

例：
```
独白："他根本不在乎我，算了。"
回复："嗯... 那你忙吧，我不打扰你了。"
```

---

## 二、Single-Pass 设计

一次调用生成独白 + 回复 + 表达方式。通过输出格式指令约束 LLM 的结构化输出，延迟减半，一致性更好。

---

## 三、总结

> Step 9 是角色的"登台表演"。LLM 作为演员，根据 Step 8 准备的舞台指令生成内心独白、最终回复和表达方式。这是整个 12 步生命周期中用户唯一直接感知的步骤——前面的 8 步都是"后台准备"，Step 9 才是"前台呈现"。

---
---

# Step 10：Hebbian 学习（Hebbian Learning）

> Hebbian 学习是 Genome 引擎的"神经可塑性"。它根据本轮的奖励信号，强化或削弱神经网络中的连接权重。这是角色"成长"的核心机制。

---

## 一、核心算法

### Hebbian 规则
经典规则：**"一起激发的神经元连在一起"（Cells that fire together, wire together）**

### 学习率
```python
lr = self.hebbian_lr * (1 + abs(reward))
```

强烈的情绪体验（无论是正面还是负面）产生更强的学习效果。

### 输出层更新（W2）
```python
for i, sig_name in enumerate(SIGNALS):
    sig_val = signals[sig_name]
    for j in range(HIDDEN_SIZE):
        if abs(hidden[j]) > 0.05:
            self.W2[i][j] += lr * reward * hidden[j] * (sig_val - 0.5)
```

### 挫败驱动的相变（Phase Transition）
当挫败累积超过阈值时，所有信号的偏置被大幅扰动——模拟"情绪爆发"或"心态转变"。

### 权重衰减
每轮所有权重衰减 0.5%（`WEIGHT_DECAY = 0.995`），防止权重无限增长。

---

## 二、总结

> Step 10 是角色的"成长时刻"。它用 Hebbian 学习规则根据 reward 信号调整神经网络权重，让角色从每一次交互中学习。相变机制模拟了情绪爆发——当挫败累积超过阈值时，角色的行为会发生剧烈扰动。

---
---

# Step 11 & 12：异步记忆存储与检索

> 异步记忆是 Genome v10 的"后台秘书"。Step 11 将本轮对话存入 EverMemOS 长期记忆，Step 12 搜索与本轮相关的记忆供下一轮使用。两者都是 fire-and-forget 的异步任务。

---

## 一、Step 11：异步存储

```python
async def _evermemos_store_bg(self, user_message: str, reply: str):
    async def _store():
        await self.evermemos.store_turn(
            user_content=user_message,
            agent_content=reply,
            context_json=json.dumps(self._last_critic),
            signals_json=json.dumps(self._last_signals),
            reward=self._last_reward,
        )
    asyncio.create_task(_store())
```

存储的内容：用户消息、角色回复、12D context、8D signals、reward 值。

---

## 二、Step 12：异步检索

并行搜索三个集合：
- `facts`：用户偏好、事实
- `episodes`：历史对话片段
- `profile`：结构化用户画像

搜索结果供**下一轮** Step 8.5 使用（延迟生效设计）。

---

## 三、总结

> Step 11 和 12 是角色的"后台笔记"。Step 11 把本轮对话悄悄存入长期记忆库，Step 12 在后台搜索与本轮相关的历史记忆。两者都是 fire-and-forget 的异步任务——不打扰当前的对话流，但为未来的对话积累素材。

---
---

# 完整串联汇总：单轮对话生命周期

> 本文将 Genome v10 Hybrid 的 12 步生命周期串联成一条完整的"数据河流"，追踪一个用户消息从进入系统到产生回复的全过程。

---

## 一、完整数据流：一条消息的旅程

追踪用户消息 `"今天被老板骂了，好难过"` 在系统中的完整旅程。

### 前置：Task Skill ReAct Loop（Step -1）
不是任务型请求，无变化，进入人格引擎。

### Step 0：EverMemOS 会话上下文
新用户，无历史。`relationship_prior = {}`

### Step 1：时间代谢
上一次交互 5 分钟前。`frustration` 微增（时间短，变化很小）。

### Step 2：Critic 感知
LLM 分析输出：`user_emotion: -0.7, vulnerability: 0.7, engagement: 0.8`
`frustration_delta: {connection: -0.3, safety: 0.2, play: -0.2}`

### Step 2.5：关系 EMA
新用户，EMA 初始化。`relationship_depth: 0.07, trust: 0.053`
Context 合并：8D → 12D

### Step 3：奖励计算
```
旧 total: 1.307
新 total: 0.997
reward = +0.31（不错的对话！）
```

### Step 3.5：驱动基线演化
`drive_baseline` 微调（变化很小，新用户）。

### Step 4：结晶门
`crystal_score = 0.43 < 0.50` → 不结晶（novelty 不够高）。

### Step 5：信号计算
25D 输入 → 随机神经网络 → 8D signals
`warmth: 0.85, vulnerability: 0.58, playfulness: 0.35`

### Step 6：热力学噪声
`total_frustration = 0.997, temperature ≈ 0.182`
噪声注入：`warmth: 0.85 → 0.77, defiance: 0.15 → 0.30`

### Step 7：KNN 风格检索
检索 3 条最相似的潜意识切片，构建 few-shot prompt。

### Step 8：Prompt 构建
组装：身份 + 信号注入 + few-shot + 指令 + 格式

### Step 8.5：记忆注入
新用户，无历史 → 跳过记忆注入。

### Step 9：Actor 生成
```
【内心独白】他看起来真的很沮丧... 我要不要先让他发泄一下？
【最终回复】哎呀... 被老板骂了肯定很难受。想聊聊发生了什么吗？
【表达方式】文字
```

### Step 10：Hebbian 学习
`reward = +0.31` → W2[warmth] 强化，W2[play] 削弱。
`age += 1`

### Step 11：异步存储
Fire-and-forget 存储到 EverMemOS。

### Step 12：异步检索
Fire-and-forget 搜索相关记忆，供下一轮使用。

---

## 二、完整状态变化汇总

| 状态变量 | 更新前 | 更新后 | 变化原因 |
|---|---|---|---|
| `drive_state.connection` | 0.75 | 0.778 | Step 3 sync |
| `drive_baseline.connection` | 0.75 | 0.746 | Step 3.5 |
| `frustration` | {c:0.5,...} | {c:0.186,...} | Step 3 |
| `relationship_ema.depth` | 0 | 0.07 | Step 2.5 |
| `recurrent_state` | random | hidden[:8] | Step 5 |
| `W2[warmth][*]` | W | W + 0.0016 | Step 10 |
| `age` | 0 | 1 | Step 10 |
| `total_reward` | 0 | +0.31 | Step 10 |

---

## 三、设计哲学总结

### 3.1 为什么需要 12 步？

| 步骤 | 如果删除 | 后果 |
|---|---|---|
| Step 0 | 无长期记忆 | 每次对话都是陌生人 |
| Step 1 | 无时间感 | 角色不会想念用户 |
| Step 2 | 无感知 | 无法理解用户输入 |
| Step 2.5 | 无关系累积 | 关系无法渐进演化 |
| Step 3 | 无反馈 | Hebbian Learning 失去依据 |
| Step 3.5 | 无性格演化 | 角色永不改变 |
| Step 4 | 无记忆筛选 | 风格记忆被噪声淹没 |
| Step 5 | 无信号计算 | 无法从状态到行为 |
| Step 6 | 无噪声 | 完全确定性，不真实 |
| Step 7 | 无风格检索 | 人格不一致 |
| Step 8 | 无 prompt | LLM 不知道角色是谁 |
| Step 9 | 无表达 | 用户看不到回复 |
| Step 10 | 无学习 | 静态人格 |
| Step 11-12 | 无异步记忆 | 跨会话断裂 |

### 3.2 核心创新点

1. **双 LLM 架构**：Critic（感知）+ Actor（表达）分离
2. **随机神经网络 + Hebbian**：行为不是写死的，是学习出来的
3. **时间代谢**：角色有物理时间感，会想念用户
4. **关系 EMA**：关系是渐进演化的，不是突变的
5. **热力学噪声**：高压下行为情绪化，增加真实感
6. **引力质量 + Hawking 辐射**：风格记忆有"印象深刻度"和"遗忘曲线"
7. **异步长期记忆**：不阻塞对话流，但积累跨会话上下文

---

## 四、性能特征

| 指标 | 数值 | 说明 |
|---|---|---|
| 单轮延迟 | 1-5s | 取决于 LLM 响应速度 |
| 状态大小 | ~15KB | W1+W2+b1+b2+recurrent+metadata |
| 记忆池大小 | 20-200条 | Genesis + Personal |
| Prompt 大小 | 1k-2k tokens | System + few_shot + signals |
| 权重更新量 | ~0.001/轮 | Hebbian Learning 的微小步长 |

---

## 五、一句话总结

> Genome v10 Hybrid 的 12 步生命周期是一个完整的认知-表达-学习循环：角色先"感知"用户（Critic），更新自己的"生理状态"（Metabolism），计算"行为倾向"（Signals），从"潜意识"中提取经验（KNN），"表演"出回复（Actor），最后从反馈中"学习"（Hebbian）。每一步都是让这个 AI 从"程序"变成"有持续内在状态的生命体"的必要组件。
