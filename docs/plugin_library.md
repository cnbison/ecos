# ECOS Plugin Library —— v0.94 第一方 Plugin 库 (Phase 7+ 抽象推演 #7)

> **本文件是 ECOS v0.94 Plugin Library 文档**。v0.94 引入第一方 Plugin 库 (Kernel-only SDK),
> 包含 3 个 reference plugin: `HintFatiguePlugin` / `ParentEngagementPlugin` / `TeacherProgressPlugin`。
> 配合 v0.93 POMDP diagnostic + v0.91/v0.92 Cognitive Twin, 形成完整的 Plugin SDK surface。

---

## 一、Plugin SDK 原则 (跟 v0.91/v0.93 一致)

ECOS Plugin SDK 遵循 5 条核心原则:

1. **Plugin 不调 Twin / Runtime write API**: Plugin 是 process_event pattern, 不调
   `LCAEngine.select_intervention` / `Runtime.update_belief` 等 write API。
2. **Plugin 只读 event.payload + Kernel state**: Plugin 通过 `event.student_id` /
   `event.payload.diagnostic` 读数据, 通过 Runtime API 读 Kernel state (e.g.
   `Runtime.diagnose_pomdp`)。
3. **Plugin 不 mutate BeliefState**: 防御性自检 [8] hard block — Plugin 全程
   read-only + log warning, 不写 `state.X = value` (per CLAUDE.md §v0.81 hard block)。
4. **Plugin 通过 PluginRegistry.register 注册**: 走 SDK-level 注册管理, 跟
   DomainRegistry v0.88.0-a / POMDPPolicy 0.93.0 完全 parallel pattern。
5. **Plugin lifecycle: instantiate → register → enable → on_event (多次) → disable → unregister**:
   跟 v0.91 CognitiveTwinAgent / v0.92 ActionHistory lifecycle 一致。

---

## 二、Plugin ABC 契约 (v0.94.0-a)

`Plugin(ABC)` 是 ECOS Plugin SDK 基类, 4 abstract method 强制实现:

```python
from ecos.plugins.base import Plugin, PluginMetadata

class MyPlugin(Plugin):
    metadata = PluginMetadata(
        name="my_plugin",
        version="1.0.0",
        description="Custom plugin",
        subscribed_topics=("hint_requested",),
    )

    def on_event(self, event):  # 必须实现
        # 处理 event, 返 result (跟 PluginRuntime._handle_* 一致)
        return {"student_id": event.student_id}

    def get_subscribed_topics(self):  # 必须实现
        return set(self.metadata.subscribed_topics)

    def enable(self):  # 必须实现
        # Lifecycle: 启用 (清零内部 state, 不调 bus.subscribe)
        pass

    def disable(self):  # 必须实现
        # Lifecycle: 禁用 (清零内部 state, 不调 bus.unsubscribe)
        pass
```

**4 abstract method**:
- `on_event(event: LearningEvent) -> Optional[Any]` — 处理 event
- `get_subscribed_topics() -> Set[str]` — 返订阅 topic 集合
- `enable() -> None` — 启用 (PluginRegistry.subscribe_all 触发)
- `disable() -> None` — 禁用 (PluginRegistry.unsubscribe_all 触发)

---

## 三、PluginMetadata 字段 (v0.94.0-a)

`PluginMetadata(frozen=True)` 是 Plugin metadata dataclass (跟 v0.91
`HumanFeedbackEntry` / v0.92 `ActionEntry` / v0.93 `POMDPDiagnostic` 完全
parallel frozen dataclass pattern):

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `name` | `str` | (必填) | 唯一 plugin 标识 (lowercase alphanumeric+underscore) |
| `version` | `str` | (必填) | semver (e.g. `"1.0.0"`) |
| `description` | `str` | `""` | plugin 描述 |
| `dependencies` | `Tuple[str, ...]` | `()` | 软依赖的其他 plugin name |
| `subscribed_topics` | `Tuple[str, ...]` | `()` | 订阅的 event topic (LearningEventType 或 Plugin-internal) |
| `schema_version` | `str` | `"0.94.0"` | 独立 schema (跟 POMDPPolicy 0.93.0 / CognitiveTwinAgent 0.92.0 隔离) |

**防御性校验** (`__post_init__`):
- `name` 必须 lowercase alphanumeric+underscore (regex `^[a-z][a-z0-9_]*$`)
- `version` 必须 semver (regex `^\d+\.\d+\.\d+$`)
- `subscribed_topics` 元素必须在合法 topic 集合内
- `name not in dependencies` (不能依赖自己)

---

## 四、PluginRegistry API (v0.94.0-b)

`PluginRegistry` 是 ECOS Plugin 注册管理 singleton (跟 `DomainRegistry v0.88.0-a`
100% parallel API surface):

```python
from ecos.plugins.registry import PluginRegistry
from ecos.plugins.first_party import HintFatiguePlugin, ParentEngagementPlugin, TeacherProgressPlugin

registry = PluginRegistry()
registry.register(HintFatiguePlugin())
registry.register(ParentEngagementPlugin())
registry.register(TeacherProgressPlugin())

# List / Get / Has
registry.list_names()  # ['hint_fatigue', 'parent_engagement', 'teacher_progress']
registry.get("hint_fatigue")  # HintFatiguePlugin instance
registry.has("hint_fatigue")  # True

# Lifecycle
registry.is_enabled("hint_fatigue")  # False (未 enable)
registry.enable("hint_fatigue")  # 调 plugin.enable()
registry.disable("hint_fatigue")  # 调 plugin.disable()

# EventBus 集成
from ecos.event.bus import EventBus
bus = EventBus()
registry.subscribe_all(bus)  # 遍历 plugin → enable + bus.subscribe
registry.unsubscribe_all(bus)  # 遍历 plugin → bus.unsubscribe + plugin.disable

# Persistence (v0.94.0-d)
from ecos.persistence.plugin_registry_store import PluginRegistryStore
store = PluginRegistryStore(db_path="web/ecos.db")
registry.save_to_db(store)  # 持久化 metadata
registry.load_from_db(store)  # 从 DB 重建 registry
```

**PluginRegistry DI 集成** (PluginRuntime):
```python
from web.api.plugin_runtime import PluginRuntime
runtime = PluginRuntime(plugin_registry_factory=lambda: get_default_registry())
runtime.start()  # 调 registry.subscribe_all(bus), first-party plugin 挂载到 bus
runtime.stop()   # 调 registry.unsubscribe_all(bus)
```

---

## 五、3 First-party Plugin 详解 (v0.94.0-c)

### 5.1 HintFatiguePlugin (学生 hint 疲劳检测)

**订阅 topic**: `hint_requested` (LearningEventType.HINT_REQUESTED, v0.85.0-d)

**核心逻辑**:
- per-student 计数 hint 数 (`Dict[student_id, int]`)
- 阈值检查: `count > HINT_FATIGUE_THRESHOLD (=5)` 触发 `_log.warning`
- enable/disable 清零计数

**返回 result**:
```python
{
    "student_id": "lbc001",
    "hint_count": 7,
    "threshold_exceeded": True,
}
```

**用法** (跟 v0.91 `use_case_hint_fatigue_detection` 升级):
```python
from ecos.plugins.first_party import HintFatiguePlugin
plugin = HintFatiguePlugin(threshold=5)
plugin.enable()
result = plugin.on_event(event)  # 触发计数 + 阈值检查
```

### 5.2 ParentEngagementPlugin (家长 engagement dashboard)

**订阅 topic**: `pomdp_diagnostic_updated` (Plugin-internal, v0.93.0-b)

**核心逻辑** (v0.98.0 (a-a) 复活为 UI 可消费, 仿 TeacherProgressPlugin v0.95.1):
- 读 `event.payload.diagnostic` (POMDPDiagnostic.to_dict())
- 派生当前状态: `most_likely_state` → 状态名 (`Engaged` / `Frustrated` / `Bored` / `Confused`)
- 读 `evolution` (K=10 timed snapshots, v0.93.0-c) 派生最近状态序列
- 状态变化检测: 跟上一 snapshot 比, 标记 `state_changed=True`
- **双喂入路径**: `on_event(event)` (订阅) 或 `ingest_diagnostic(student_id, diagnostic)` (API 层经 Runtime.diagnose_pomdp 喂入) 共享 `_build_report` 单一派生逻辑 (DRY)
- **evolution 断层补线**: POMDPDiagnostic.to_dict() 不含 evolution (留在 POMDPPolicy._evolution), API 层经 `Runtime.diagnose_pomdp_evolution` (第 9 Runtime API) 拿序列后 `ingest_evolution(student_id, evolution)` 更新 report
- **规则表驱动建议** (`_build_advice`, 不调 LLM, deterministic): 按 current_state / 持续窗口 (SUSTAINED_ENGAGED_WINDOW=3) / cold_start / state_changed 产出中文建议条目 (trigger + severity: info / warning / attention); 阈值为先验值, v0.98 试点校准
- 报告缓存到 `self._reports[student_id]`, `report_for()` / `get_reports()` 查询

**返回 result**:
```python
{
    "student_id": "lbc001",
    "current_state": "Frustrated",
    "current_state_index": 1,
    "recent_states": ["Engaged", "Bored", "Frustrated"],
    "evolution_count": 3,
    "state_changed": True,
    "cold_start": False,
    "advice": [
        {"trigger": "state=frustrated", "severity": "warning",
         "message": "出现 Frustrated 状态, 建议了解题目难度是否过高"},
        {"trigger": "state_changed", "severity": "info",
         "message": "学习状态发生变化 (当前: Frustrated), 可与学生聊聊近况"},
    ],
    "updated_at": "2026-09-06T00:00:00",
}
```

**用法** (跟 v0.93 `use_case_parent_engagement_dashboard` 升级):
```python
from ecos.plugins.first_party import ParentEngagementPlugin
from ecos.runtime.api import diagnose_pomdp, diagnose_pomdp_evolution
plugin = ParentEngagementPlugin()
plugin.enable()
result = plugin.on_event(event)  # 读 diagnostic + 派生 report + 缓存
# 或 API 层 pull 路径:
diagnostic = diagnose_pomdp(student_id, lca_engine=lca)
report = plugin.ingest_diagnostic(student_id, diagnostic)
evolution = diagnose_pomdp_evolution(student_id, lca_engine=lca)
plugin.ingest_evolution(student_id, evolution)
parent_report = plugin.report_for(student_id)
```

### 5.3 TeacherProgressPlugin (教师 progress review)

**订阅 topic**: `pomdp_diagnostic_updated` (Plugin-internal, v0.93.0-b)

**核心逻辑**:
- 读 `event.payload.diagnostic` (POMDPDiagnostic.to_dict())
- 读 `most_likely_state` → 状态名
- 读 `coverage.min()` → 冷启动判断: `min < COLD_START_COVERAGE_THRESHOLD (=5)` → 冷启动期
- 派生教学建议: 冷启动期保守 / 已冷启动基于后验定制

**返回 result**:
```python
{
    "student_id": "lbc001",
    "most_likely_state": "Bored",
    "most_likely_state_index": 2,
    "belief": [0.1, 0.1, 0.7, 0.1],
    "min_coverage": 10,
    "cold_start": False,
    "advice": "已冷启动完成 (min_coverage=10), 可基于 POMDP 后验定制教学",
}
```

**用法** (跟 v0.93 `use_case_teacher_progress_review` 升级):
```python
from ecos.plugins.first_party import TeacherProgressPlugin
plugin = TeacherProgressPlugin()
plugin.enable()
result = plugin.on_event(event)  # 读 diagnostic + 派生教学分析
```

---

## 六、Plugin 注册生命周期 (v0.94 全周期)

完整 Plugin lifecycle 路径:

```
┌─────────────────────────────────────────────────────────┐
│ 1. instantiate: HintFatiguePlugin()                     │
│    └─ Plugin ABC 继承, metadata class-level frozen       │
│ 2. register: registry.register(plugin)                  │
│    └─ PluginRegistry 维护 _plugins dict + 校验 dependencies│
│ 3. enable: registry.enable(name) 或 subscribe_all 触发  │
│    └─ plugin.enable() 清零内部 state                    │
│ 4. on_event: bus.publish(topic, event) → plugin.on_event│
│    └─ Plugin 读 event.payload + 返回 result (不 mutate)  │
│ 5. disable: registry.disable(name) 或 unsubscribe_all    │
│    └─ plugin.disable() 清零内部 state                   │
│ 6. unregister: registry.clear() 或 reset_default_registry│
│    └─ 从 _plugins dict 删除 (测试隔离用)                │
└─────────────────────────────────────────────────────────┘
```

**PluginRuntime 集成路径** (生产环境):
1. `PluginRuntime.__init__` 接受 `plugin_registry_factory` DI kwarg
2. `PluginRuntime.start()` 调 built-in 8 subscriber + `registry.subscribe_all(bus)`
3. `PluginRuntime.stop()` 调 built-in unsubscribe + `registry.unsubscribe_all(bus)`
4. 8 built-in subscriber (response_submitted / calibration / intervention / hint / idle / goal / reflection / pomdp_diagnostic_updated) 优先 register, first-party plugin second (无重复订阅)

---

## 七、防御性自检 (跟 CLAUDE.md §v0.94 同步)

| # | 项 | v0.94 状态 |
|---|----|-----------|
| 1 | silent pass 扫描 | Plugin ABC / PluginRegistry / First-party plugin 全程 `_log.warning(..., exc_info=True)` |
| 2 | `__version__` 同步 | `"0.93.0"` → `"0.94.0"` bump (final 阶段) |
| 3 | `detect_with_hits` 传 `library_str` | 跟 v0.94 无关 |
| 4 | HTML class 与 CSS 对齐 | 跟 v0.94 无关 |
| 5 | schema_version | `PluginMetadata` "0.94.0" 独立 schema. 老 `plugin_registry` 表 `CREATE TABLE IF NOT EXISTS` 幂等 |
| 6 | DB 恢复 6 关键字段 | 跟 v0.94 无关 |
| 7 | replay 脚本无字面量 skill_id | 跟 v0.94 无关 |
| 8 | direct state mutation 扫描 | 0 新 mutation site (Plugin 是 process_event pattern, 不持 BeliefState 引用). AST 扫描 50+1 = 51 文件无新增 mutation site |

**FUNC_ALLOWLIST 维持 51 文件**:
- Plugin / PluginRegistry / First-party plugin / PluginRegistryStore 全是
  process_event pattern, 不调 `state.X = value`, 不需要 allowlist
- 跟 `POMDPDiagnostic` (v0.93.0-a) / `HumanFeedbackEntry` (v0.91.0-a) /
  `ActionEntry` (v0.92.0-a) frozen dataclass 模式完全 parallel

---

## 八、Plugin SDK 调用样例 (3 use case)

### 8.1 注册 3 first-party plugin + 启动 PluginRuntime

```python
from web.api.plugin_runtime import PluginRuntime
from ecos.plugins.registry import get_default_registry
from ecos.plugins.first_party import (
    HintFatiguePlugin, ParentEngagementPlugin, TeacherProgressPlugin,
)

# 1) Register 3 first-party plugin 到 default singleton registry
registry = get_default_registry()
registry.register(HintFatiguePlugin())
registry.register(ParentEngagementPlugin())
registry.register(TeacherProgressPlugin())
print(f"Registered plugins: {registry.list_names()}")
# ['hint_fatigue', 'parent_engagement', 'teacher_progress']

# 2) 启动 PluginRuntime (DI 注入 default registry)
runtime = PluginRuntime(plugin_registry_factory=get_default_registry)
runtime.start()  # built-in 8 subscriber + registry.subscribe_all(bus)
print(f"Subscription count: {runtime.subscription_count}")
# 8 (built-in, 不含 first-party plugin 注册的额外订阅)

# 3) Emit event 触发 plugin.on_event
from ecos.cta.event_log import LearningEvent
hint_event = LearningEvent.from_hint_requested(student_id="lbc001", problem_id="PB-Q01")
runtime._bus.publish("hint_requested", hint_event)
# → HintFatiguePlugin.on_event 触发计数

# 4) Stop PluginRuntime
runtime.stop()  # built-in unsubscribe + registry.unsubscribe_all(bus)
```

### 8.2 自定义 Plugin (继承 Plugin ABC)

```python
from ecos.plugins.base import Plugin, PluginMetadata

class MyCustomPlugin(Plugin):
    metadata = PluginMetadata(
        name="my_custom_plugin",
        version="1.0.0",
        description="Custom plugin for Teacher Dashboard",
        subscribed_topics=("reflection_completed",),
    )

    def on_event(self, event):
        # 读 event.payload + 返回 result
        reflection_text = event.payload.get("reflection_text", "")
        return {
            "student_id": event.student_id,
            "reflection_length": len(reflection_text),
        }

    def get_subscribed_topics(self):
        return set(self.metadata.subscribed_topics)

    def enable(self):
        self._state = {}

    def disable(self):
        self._state = {}

# Register + 启用
from ecos.plugins.registry import get_default_registry
get_default_registry().register(MyCustomPlugin())
```

### 8.3 Plugin persistence + hot reload from DB

```python
from ecos.persistence.plugin_registry_store import PluginRegistryStore
from ecos.plugins.registry import get_default_registry, reset_default_registry
from ecos.plugins.first_party import HintFatiguePlugin, ParentEngagementPlugin, TeacherProgressPlugin

# 1) 启动时 register + save 到 DB
registry = get_default_registry()
registry.register(HintFatiguePlugin())
registry.register(ParentEngagementPlugin())
registry.register(TeacherProgressPlugin())

store = PluginRegistryStore(db_path="web/ecos.db")
registry.save_to_db(store)
# → plugin_registry 表 3 行 (per-plugin metadata 持久化)
store.close()

# 2) 重启进程: 从 DB 重建 registry
reset_default_registry()
store2 = PluginRegistryStore(db_path="web/ecos.db")
new_registry = get_default_registry()
registered = new_registry.load_from_db(store2)
# → ['hint_fatigue', 'parent_engagement', 'teacher_progress']
print(f"Loaded plugins: {registered}")
store2.close()
```

---

## 相关文档

- [docs/plugin_sdk.md](./plugin_sdk.md) — v0.91 Plugin SDK 雏形 + 7 subscriber
- [docs/pomdp_diagnostic.md](./pomdp_diagnostic.md) — v0.93 POMDP T/R 后验可视化
- [research/00-overview/12-kernel-mapping-current-vs-2.0.md §6](../research/00-overview/12-kernel-mapping-current-vs-2.0.md) — Plugin SDK Kernel 映射
- [discussions/2026-08-13-v094-design.md](../discussions/2026-08-13-v094-design.md) — v0.94 设计文档
- [ecos/plugins/base.py](../ecos/plugins/base.py) — Plugin ABC + PluginMetadata
- [ecos/plugins/registry.py](../ecos/plugins/registry.py) — PluginRegistry singleton
- [ecos/plugins/first_party/](../ecos/plugins/first_party/) — 3 first-party plugin
- [ecos/persistence/plugin_registry_store.py](../ecos/persistence/plugin_registry_store.py) — Plugin metadata 持久化
- [examples/plugin_sample_first_party.py](../examples/plugin_sample_first_party.py) — Plugin 3 use case sample