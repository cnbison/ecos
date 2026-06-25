# 2026-06-22 — SGE Phase 3 应用层反思：从 AiBeing 借鉴的下一层

> **目的**：M2.1 已经借鉴 AiBeing 的 9 个**引擎内部机制**。Phase 3 进入应用层，需要从 AiBeing 借鉴**应用级经验**（性能、状态管理、用户体验、生产鲁棒性）。
> **关系文档**：
> - **SGE-M21-AiBeing-Implementation-Mapping.md**（SelfLab 时代文件，ECOS 暂无对应） — M2.1 引擎内部机制映射
> - **SGE-Learning-from-AiBeing.md**（SelfLab 时代文件，ECOS 暂无对应） — 借鉴分析（概念层）

---

## 0. 核心洞察

**M2.1 学的是"引擎怎么转"，Phase 3 要学"应用怎么跑"。**

| 阶段 | 从 AiBeing 学什么 | 性质 |
|------|-----------------|------|
| **M2.1** | 引擎内部机制（Critic/EMA/Hebbian/Hawking 等 9 个） | 算法/公式/参数 |
| **M2.2** | 真实 LLM 集成 + 工程模式（chunk 隔离、retry、warmup） | 工程化 |
| **Phase 3** | **应用层经验**（会话管理、性能优化、生产鲁棒性） | 产品化 |

**关键差别**：AiBeing 是**生产级 AI 角色引擎**（已有真实用户），SGE 是**研究项目**。AiBeing 解决过 SGE 还没遇到的问题——这些经验对 Phase 3 极有价值。

---

## 1. AiBeing 应用层架构（Phase 3 学习对象）

### 1.1 AiBeing 的应用层组件（M2.1 mapping 没覆盖）

```
AiBeing 应用层（M2.1 没借鉴）
├── chat_agent.py（会话编排）
│   ├── _chat_inner() - 单轮对话主循环
│   ├── Session 管理（多轮上下文窗口）
│   ├── 用户输入预处理 + 注入
│   └── 异步输出（不等 LLM 完成就返回骨架）
│
├── evermemos_mixin.py（用户长期记忆）
│   ├── User profile 加载/更新
│   ├── Persona 历史
│   └── 跨会话记忆持久化
│
├── prompt/ 目录
│   ├── actor_single / critic / reflector 模板
│   ├── few-shot examples
│   └── system prompts
│
├── config/ 目录
│   ├── engine_params.yaml（运行时参数）
│   ├── persona config（角色预设）
│   └── A/B 测试 variants
│
├── cache/ 目录（生产性能优化）
│   ├── LLM response cache（避免重复调用）
│   ├── embedding cache
│   └── episodic memory cache
│
└── tests/ 目录
    ├── unit tests
    ├── integration tests
    └── e2e tests
```

### 1.2 SGE 当前缺什么（Phase 3 视角）

| SGE 现状 | 缺失（应用层） | AiBeing 怎么做的 |
|---------|---------------|----------------|
| `SGEOrchestrator.run(n_epochs)` | **会话管理**：多轮对话的状态维护 | `chat_agent._chat_inner()` 有 session state |
| 无用户上下文注入 | **用户画像注入**：让 SGE 知道在跟谁对话 | `EverMemOS` 自动加载用户 profile |
| 无 caching | **LLM response cache**：相同 prompt 不重复调用 | `cache/` 目录 + LRU 策略 |
| 同步阻塞 LLM 调用 | **异步/流式**：UX 不等待 | `chat_agent` 异步返回骨架 |
| 无 prompt 模板库 | **prompt 版本管理**：A/B 测试不同 prompt | `prompt/` 目录 + variant config |
| 无单元测试 | **测试覆盖**：M2.2 靠手动验证 | `tests/` 完整覆盖 |

---

## 2. AiBeing 的应用层经验（SGE Phase 3 可借鉴）

### 2.1 借鉴 1：**会话管理（Session Management）**

**AiBeing 做法**（`chat_agent.py:_chat_inner()`）：
```python
def _chat_inner(self, user_input: str, session_id: str) -> str:
    # 1. 加载 session 状态（之前几轮的 context）
    session_state = self.session_manager.load(session_id)
    
    # 2. 把 session_state 注入到 12 步循环的每个 step
    # - Step 0 EverMemOS 加载包含 session 历史
    # - Step 7 KNN retrieval 也用 session 历史
    # - Step 8 build prompt 包含 session context
    
    # 3. 单轮结束，保存 session_state
    self.session_manager.save(session_id, new_state)
```

**SGE Phase 3 怎么用**（学生数字孪生）：

```python
# sge/session.py（新模块）
class TwinSession:
    """单次学生与 twin 交互的 session"""
    
    def __init__(self, student_id: str, twin_db: TwinStateDB):
        self.student_id = student_id
        self.db = twin_state_db
        self.sge_state, self.app_state, self.last_epoch = \
            twin_db.load_full_state(student_id)
        self.current_epoch = self.last_epoch
    
    def process_event(self, student_event: StudentEvent) -> TwinResponse:
        # 用 session 的 SGE state 处理一个事件
        orchestrator.step(self.current_epoch)
        self.current_epoch += 1
        return actor_output
    
    def close(self):
        # Session 结束 → 保存到 DB
        self.db.save_full_state(
            self.student_id, 
            self.sge_state, 
            self.app_state,
            epoch=self.current_epoch,
            trigger='on_close'
        )
```

**关键**：session 不是简单"读 state → run → 写 state"，而是**滚动 epoch 计数器 + state 在 session 期间驻内存**。

### 2.2 借鉴 2：**用户画像注入（EverMemOS）**

**AiBeing 做法**（`evermemos_mixin.py`）：
```python
def inject_user_context(critic_input, user_id):
    # 从 EverMemOS 加载用户画像
    profile = evermemos.get_user_profile(user_id)
    
    # 注入到 Critic prompt
    critic_input += f"""
    [用户画像]
    姓名: {profile.name}
    兴趣: {profile.interests}
    历史偏好: {profile.history}
    """
    return critic_input
```

**SGE Phase 3 怎么用**：

```python
# sge/context_injection.py
class TwinContextBuilder:
    """构造注入到 SGE 各层的 context"""
    
    def build_critic_context(self, student: StudentProfile, 
                             mastery_state: SubjectMasteryState) -> dict:
        return {
            # SGE 原生 8D
            'user_emotion': self._infer_emotion(student),
            'topic_intimacy': 0.5,
            
            # App 层注入（学生特有）
            'student_name': student.name,
            'current_mastery': mastery_state.summary(),
            'recent_struggle': mastery_state.most_recent_struggling(),
            'learning_pace': mastery_state.learning_velocity(),
        }
```

**关键**：SGE 不需要改内部逻辑——App 层构造 rich context 后，注入到 SGE 原生 8D + 额外字段。

### 2.3 借鉴 3：**LLM Response Caching**

**AiBeing 做法**（`cache/`）：
```python
class LLMCache:
    """LRU cache for LLM responses"""
    
    def __init__(self, max_size=10000):
        self.cache = LRUCache(max_size)
    
    def get_or_call(self, prompt_hash: str, call_fn: Callable) -> str:
        if prompt_hash in self.cache:
            return self.cache[prompt_hash]  # O(1)
        result = call_fn()
        self.cache[prompt_hash] = result
        return result
```

**SGE Phase 3 怎么用**（解决 M2.2 chunk 跑 6600 次 LLM 浪费）：

```python
# sge/llm_cache.py
class SGELLMCache:
    """LLM 响应缓存（避免重复调用）"""
    
    def __init__(self, cache_dir: str = ".sge_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache = {}
    
    def cached_chat(self, client: SGELLMClient, messages: list, **kwargs):
        """带缓存的 chat 调用"""
        prompt_hash = hashlib.sha256(
            json.dumps(messages + [str(kwargs)]).encode()
        ).hexdigest()[:16]
        
        cache_file = self.cache_dir / f"{prompt_hash}.json"
        if cache_file.exists():
            return json.loads(cache_file.read_text())['response']
        
        response = client.chat(messages, **kwargs)
        cache_file.write_text(json.dumps({'response': response}))
        return response
```

**关键价值**：
- M2.2 跑了 ~6600 次 LLM 调用，如果启用缓存，chunk 1/2/3 的相同事件（如所有 chunk 0 都有 epoch 0 事件）可复用
- 调试时同 prompt 改代码后只需重跑受影响的部分
- 降低 MiniMax API 调用次数（成本 + 稳定性）

### 2.4 借鉴 4：**异步 + 流式响应**

**AiBeing 做法**：
```python
async def _chat_inner_async(self, user_input):
    # 不等所有 12 步完成才返回
    # Step 2 Critic 返回后就开始构造响应骨架
    # Step 9 Actor 是最重的，可以 async 等待
    
    skeleton = await self.step_2_critic(user_input)  # 快速
    response = await self.step_9_actor(skeleton)     # 重，但 UX 已经有骨架
    return response
```

**SGE Phase 3 怎么用**（学生 chat 应用 UX）：

```python
# 用户问"我数学哪里不行？"
# 不需要等全部 12 步 + LLM 完成
# 1. 先返回骨架（"让我看看你的数学状态..."）
# 2. 异步跑 SGE
# 3. 流式返回完整响应
```

**注意**：SGE 当前是研究项目，但 Phase 3 应用化时**async 是 UX 必需**。

### 2.5 借鉴 5：**Prompt 版本管理**

**AiBeing 做法**（`prompt/`）：
```
prompt/
├── critic/
│   ├── v1_basic.txt
│   ├── v2_with_emotion.txt
│   ├── v3_chain_of_thought.txt
│   └── current → v3_chain_of_thought.txt (symlink)
├── actor/
│   ├── ...
└── reflector/
    └── ...
```

**SGE Phase 3 怎么用**：

```python
# sge/prompts/
├── critic/
│   ├── basic.txt
│   ├── student_domain.txt  # 加 subject mastery context
│   └── current -> student_domain.txt
└── actor/
    ├── basic.txt
    ├── student_domain.txt  # 加 subject context
    └── current -> student_domain.txt
```

**价值**：
- A/B 测试不同 prompt（哪个让 AI 回答更连贯？）
- 升级不破坏历史数据（versioning）
- 多语言支持（不同语言用不同 prompt）

### 2.6 借鉴 6：**单元测试覆盖**

**AiBeing 现状**：完整的 `tests/` 目录，单元 + 集成 + e2e

**SGE 现状**：M2.2/M2.3 阶段只有 `test_hawking_decay_fix.py` + `test_e1_event_generator.py`，覆盖很少

**SGE Phase 3 应该补**：
```
sge/tests/
├── unit/
│   ├── test_baseline.py (Agent, Value, Hawking, Crystallizer)
│   ├── test_event.py
│   ├── test_identity.py
│   ├── test_narrative.py
│   ├── test_orchestrator.py
│   └── test_persistence.py
├── integration/
│   ├── test_12step_loop.py
│   └── test_chunk_continuity.py
└── e2e/
    └── test_real_llm_smoke.py
```

**目标覆盖率**：核心模块 ≥ 80%（基线、Hawking、Crystallizer 必测）

---

## 3. AiBeing 有但 SGE 不需要的东西（避免过度借鉴）

| AiBeing 特性 | SGE 是否需要 | 理由 |
|------------|------------|------|
| **SOUL.md persona 系统** | ❌ 不需要 | SGE 是身份**涌现**，AiBeing 是身份**预设** |
| **多语言支持** | ❌ 不需要（v1）| Phase 4 商业化再考虑 |
| **触觉/听觉 skill** | ❌ 不需要 | SGE 只处理文本事件 |
| **多 persona 切换** | ❌ 不需要 | SGE 每个 twin 有唯一身份 |
| **情感规则引擎** | ❌ 不需要 | SGE 通过 frustration 真实累积 |

**关键原则**：M2.1 mapping 已经标了"直接复用 / 低改造 / 中改造 / 新增 / 不适用"——继续这个分层，避免照搬 AiBeing 的所有东西。

---

## 4. SGE 有但 AiBeing 没有的东西（Phase 3 差异化）

| SGE 独有 | AiBeing 没有 | Phase 3 价值 |
|---------|-------------|-------------|
| **Identity Layer**（自我概念涌现）| AiBeing 用 SOUL.md 预设 | SGE 的 AI 是"不知道自己是谁 → 知道自己是谁"，更具真实性 |
| **Narrative Builder**（自传叙事）| AiBeing 只有 style memory | SGE 能回答"我的人生故事是什么" |
| **Phase Transition**（真实成长）| AiBeing 的"phase"是预设状态切换 | SGE 的 phase 是 frustration 累积触发 |
| **SubjectMasteryState**（领域适配）| AiBeing 没有领域特化 | SGE 可直接接入学生领域 |
| **4 层记忆系统** | AiBeing 主要 1-2 层 | SGE 记忆结构更丰富 |
| **chunk 隔离** | AiBeing 单进程 | SGE 可长跑（17h 验证过）|

**这些是 SGE 的护城河**——Phase 3 应该强化这些差异化能力，不是模仿 AiBeing。

---

## 5. Phase 3 实施清单（按优先级）

| 优先级 | 任务 | 工作量 | 来源 | 受益 |
|--------|------|--------|------|------|
| **P0** | `sge/session.py`（会话管理）| 1.5 天 | AiBeing §2.1 | 所有应用 |
| **P0** | `sge/context_injection.py`（用户画像注入）| 1 天 | AiBeing §2.2 | 学生 twin |
| **P0** | `sge/persistence.py`（持久化）| 1.5 天 | 之前讨论 | 解决 chunk reset |
| **P1** | `sge/llm_cache.py`（LLM cache）| 0.5 天 | AiBeing §2.3 | 成本 + 调试 |
| **P1** | 单元测试覆盖（核心模块 ≥ 80%）| 1.5 天 | AiBeing §2.6 | 质量保证 |
| **P2** | `sge/prompts/` 版本管理 | 1 天 | AiBeing §2.5 | A/B 测试 |
| **P2** | async/streaming 支持 | 1 天 | AiBeing §2.4 | UX |
| **P3** | 多语言 prompt | 1 周 | 商业化时 | Phase 4 |
| **P3** | SOUL.md 类似预设 | ❌ 不做 | SGE 设计原则 | 避免身份预设 |

**Phase 3.1 优先 P0**（3 周内）：
- `sge/persistence.py` ✓（已设计）
- `sge/session.py`（TwinSession）
- `sge/context_injection.py`（TwinContextBuilder）

**Phase 3.2 优先 P1**（再 2 周）：
- LLM cache
- 单元测试覆盖

---

## 6. 与 M2.1 mapping 的关系

| 文档 | 关注点 |
|------|--------|
| `SGE-M21-AiBeing-Implementation-Mapping.md` | 引擎内部机制（M2.1 已借鉴） |
| **本文件（Phase 3 应用层反思）** | 应用层经验（Phase 3 待借鉴） |
| `SGE-Learning-from-AiBeing.md` | 概念层借鉴分析（已存在） |

**三文档组成完整 AiBeing 借鉴体系**：
1. 概念层：为什么借鉴
2. 引擎层：借鉴什么算法/公式
3. 应用层：借鉴什么工程模式/产品经验

---

## 7. 关键决策（与之前 Phase 3 讨论一致）

| 决策 | 选择 | 理由 |
|------|------|------|
| 会话管理 | TwinSession class | AiBeing 验证的模式 |
| 用户上下文注入 | App 层构造 + SGE 注入 | SGE 不需知道用户画像 schema |
| LLM cache | 文件级 SHA256 hash | 简单 + 跨进程 |
| async | Phase 3.2 再说 | 优先级低，先功能后 UX |
| 单元测试 | 从 P0 模块开始 | 与开发同步 |

---

## 8. 关联文档

- **SGE-M21-AiBeing-Implementation-Mapping.md**（SelfLab 时代文件，ECOS 暂无对应） — M2.1 引擎层映射
- **SGE-Learning-from-AiBeing.md**（SelfLab 时代文件，ECOS 暂无对应） — 概念层分析
- **SGE-M22-Implementation-Plan.md §三 风险与缓解**（SelfLab 时代文件，ECOS 暂无对应） — Phase 3 风险
- **2026-06-21-sge-strategic-significance.md**（SelfLab 时代文件，ECOS 暂无对应） — SGE 战略意义（Phase 3 视角）
- **SelfLab SGE 文档**（ECOS 独立后无对应文件；ECOS 的路线图见 [03-roadmap.md](../00-overview/03-roadmap.md)） — 工程路线图

---

## 9. 版本

- v1: 2026-06-22 — 初版（Phase 3 应用层反思：6 个具体借鉴方向 + 5 个避免项 + 实施优先级）

---

**维护者**：Bisen & Claude
**创建日期**：2026-06-22
**状态**：✅ M2.1 mapping 已完成；本文档补充 Phase 3 应用层借鉴方向
