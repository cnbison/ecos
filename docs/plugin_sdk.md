# ECOS Plugin SDK 文档

**版本**: v0.91.0 (Phase 7+ 抽象推演 #4)
**日期**: 2026-08-12
**状态**: Kernel 100% production-ready
**对应设计**: `discussions/2026-08-12-v091-design.md` §4-§5

---

## 一、Plugin 原则

ECOS Plugin SDK 遵循 **kernel-mapping §6 Plugin SDK 边界** 的核心原则:

> **Plugin 不调用 Twin, Plugin 只能产生 Event**

具体含义:
1. **Plugin 永远**不直接调 `BeliefEngine.update()` / `LCAEngine.select_intervention()` / `CognitiveTwinAgent.append_human_feedback()`
2. **Plugin 永远**只构造 `LearningEvent` + `bus.publish(topic, event)`
3. **Plugin 永远**不持有 `BeliefState` / `CognitiveTwinAgent` 引用
4. **Runtime 是 sole entry**: `PluginRuntime` 包装 Runtime API 作为 EventBus subscriber, 接 event 后调 Runtime 委托

Plugin SDK 抽象推演:
- **v0.84.0-d**: PluginRuntime 雏形 (1 subscriber: `response_submitted`)
- **v0.85.0-b**: 加 `request_calibration` subscriber
- **v0.85.0-c**: 加 `request_intervention` subscriber
- **v0.85.0-d**: Production activation (Flask startup 注册 PluginRuntime.start())
- **v0.91.0-b**: 加 4 frontend stub subscribers (`hint_requested` / `idle_detected` / `goal_changed` / `reflection_completed`)
- **v0.91.0-c**: LCA 4 layer 接入 Human feedback (ExperimentDesigner + Evaluator)
- **v0.91.0-d**: 冷启动 + 持久化 + canary

Plugin SDK 100% production: 任何 Plugin endpoint 走 Plugin 路径, 无 legacy fallback.

---

## 二、7 Subscriber 完整契约

PluginRuntime 注册 **7 subscribers** 到 EventBus:

| # | Topic | 来源 | Handler | Runtime API |
|---|-------|------|---------|-------------|
| 1 | `response_submitted` | `/api/answer` (学生提交答案) | `_handle_response_submitted` | `Runtime.update_belief` |
| 2 | `request_calibration` | `/api/dual_agent` (双 Agent 互校) | `_handle_request_calibration` | `DualAgentOrchestrator.process_observation` |
| 3 | `request_intervention` | `/api/lca` (LCA 干预选择) | `_handle_request_intervention` | `Runtime.plan` |
| 4 | `hint_requested` | `/api/event/hint` (frontend stub) | `_handle_hint_requested` | `LCAEngine.append_human_feedback` |
| 5 | `idle_detected` | `/api/event/idle` (frontend stub) | `_handle_idle_detected` | `LCAEngine.append_human_feedback` |
| 6 | `goal_changed` | `/api/event/goal_change` (frontend stub) | `_handle_goal_changed` | `LCAEngine.append_human_feedback` |
| 7 | `reflection_completed` | `/api/event/reflection` (frontend stub) | `_handle_reflection_completed` | `LCAEngine.append_human_feedback` |

### 2.1 核心 API (v0.84-0.85)

#### `response_submitted`
- **来源**: 学生端 `/api/answer` 提交答案
- **Payload**: `Observation.to_dict()` (含 skill_id, problem_id, correct, score, bloom_level)
- **Handler**: 重构 `Observation` → 调 `Runtime.update_belief` → 写入 BeliefState
- **持久化**: 调 `engine.update(...)` 内部触发 `StateEngine.commit` → 写 DB

#### `request_calibration`
- **来源**: 双 Agent 互校 endpoint `/api/dual_agent`
- **Payload**: `{problem_id, skill_id, correct, score, bloom_layer}`
- **Handler**: 重构 `Observation` → 调 `DualAgentOrchestrator.process_observation` → 返 `CalibratedLCAResult`
- **持久化**: 调 `_write_calibration_log` 写 DB

#### `request_intervention`
- **来源**: LCA 选择 endpoint `/api/lca`
- **Payload**: `{audience}` (student / teacher / parent)
- **Handler**: 调 `Runtime.plan(student_id, audience, cta_input, lca_engine)` → 返 `LCAResult`
- **持久化**: 调 `_save_lca_state` 写 DB

### 2.2 Frontend Stub API (v0.91)

#### `hint_requested`
- **来源**: 学生请求提示 (frontend 检测到 hint button click)
- **Payload**: `{problem_id: str, hint_level: int}` (1=soft, 2=detailed, 3=full outline)
- **Handler**: `HumanFeedbackEntry.from_event(event)` → `LCAEngine.append_human_feedback(sid, entry, state=...)`
- **影响**: 6+ 次 → LCA 后续 select 优先 EXPLANATORY (ExperimentDesigner._human_feedback_itype_override)

#### `idle_detected`
- **来源**: Frontend 检测 N 秒无操作
- **Payload**: `{idle_seconds: float}`
- **Handler**: 同上
- **影响**: 4+ 次 → 优先 INQUIRY (激活兴趣)

#### `goal_changed`
- **来源**: 学生切换学习目标
- **Payload**: `{old_goal_id: str, new_goal_id: str}`
- **Handler**: 同上
- **影响**: 2+ 次 → 优先 PRACTICE (目标调整后巩固)

#### `reflection_completed`
- **来源**: 学生完成反思
- **Payload**: `{reflection_text: str, problem_id: Optional[str]}`
- **Handler**: 同上
- **影响**: 4+ 次 → 优先 PRACTICE (深度反思后巩固) + reward boost 1.2x

---

## 三、LCAEngine.append_human_feedback 接口

```python
def append_human_feedback(
    self,
    student_id: str,
    entry: HumanFeedbackEntry,
    state: Optional[BeliefState] = None,
) -> None:
    """v0.91.0-b: 追加 HumanFeedbackEntry 到 per-student CognitiveTwinAgent.

    Args:
        student_id: 学生 ID
        entry: HumanFeedbackEntry 实例 (4 event_type 校验已通过, frozen)
        state: Optional[BeliefState] for lazy init CognitiveTwinAgent.
               None 时若 student_id 不在 _cognitive_twin dict, skip (下次 select
               时 select_intervention 走 from_state 兜底).

    Returns:
        None (mutation 走 allowlist, FUNC_ALLOWLIST += "append_human_feedback")
    """
```

### 3.1 数据结构 (HumanFeedbackEntry)

```python
@dataclass(frozen=True)
class HumanFeedbackEntry:
    student_id: str
    timestamp: datetime
    event_type: str  # HUMAN_FEEDBACK_EVENT_TYPES = frozenset({"hint_requested", "idle_detected", "goal_changed", "reflection_completed"})
    payload: Dict[str, Any]
    source: str = "plugin"  # 留 v0.92+ 扩展 "teacher" / "parent"
    schema_version: str = SCHEMA_VERSION  # "0.91.0"
```

### 3.2 CognitiveTwinAgent 3-tuple

```python
@dataclass
class CognitiveTwinAgent:
    belief_state: BeliefState  # 完整 CTA 5D + Bloom + DomainExtension + Motivation 状态 (不变)
    trajectory: TrajectoryState  # 成长轨迹 (从 belief_state.trajectory 派生, 已内嵌)
    human_feedback: HumanFeedbackTrajectory  # Human feedback 轨迹 (v0.91.0-a 新增)
    action_history: Optional[Dict[str, Any]] = None  # v0.92+ 占位
    schema_version: str = SCHEMA_VERSION  # "0.91.0"
```

---

## 四、防御性自检 (CLAUDE.md §7 同步)

Plugin SDK 受 3 项防御性自检约束:

### 4.1 防御性自检 [1] silent pass 扫描

`web/api/plugin_runtime.py` 不允许 `except ...: pass` 模式. handler 异常必须 `_log.warning(..., exc_info=True)`, 不破坏 EventBus.

```python
# 正确: handler 异常 _log.warning 不 raise
try:
    lca_engine.append_human_feedback(student_id, entry, state=state)
except Exception as e:  # noqa: BLE001
    _log.warning("...", exc_info=True)
    return None
```

### 4.2 防御性自检 [5] schema_version 校验

`CognitiveTwinAgent.load_state` 校验 `schema_version == "0.91.0"`, 老 `0.90.0` snapshot raise `ValueError`. 同样 pattern 应用到 `HumanFeedbackEntry.from_dict` / `HumanFeedbackTrajectory.from_dict`.

### 4.3 防御性自检 [8] direct state mutation 扫描

`scripts/check_no_direct_state_mutation.py` 维护 `FUNC_ALLOWLIST`, 仅以下方法可直接 mutate state:

- `BeliefState.{__init__, to_dict, from_dict, apply_snapshot, validate, bump_version, append_trajectory_snapshot, add_evidence, add_motivation_observation, set_domain_extension}`
- `StateEngine.commit`
- `BeliefUpdator.apply`
- `create_initial_state`
- **v0.91.0-a 新增**: `CognitiveTwinAgent.append_human_feedback`

任何 allowlist 之外的直接 `state.X = value` mutation 都会 fail pre-commit 静态检查.

---

## 五、Runtime API 6 plan 接口

Plugin SDK 跟 Runtime API 6 plan API 协同:

| API | kwargs | v0.91 维持 |
|---|---|---|
| `plan` | `lca_engine, cta_input, goal, event_log` | ✅ |
| `plan_goal_aware` | + `goal` | ✅ |
| `plan_motivation_aware` | + `motivation_observation, motivation` | ✅ |
| `plan_domain_aware` | + `domain_name, motivation` | ✅ |
| `plan_human_feedback_aware` (NEW v0.91.0-b) | + `human_feedback_entry` | ✅ |
| `plan` 委托链 | `plan → plan_goal_aware → plan_motivation_aware → plan_domain_aware → plan_human_feedback_aware` | ✅ |

Plugin SDK 不暴露 `plan` API 直接调用 — Plugin 永远只产 event, Runtime 委托 plan.

---

## 六、5 sub-commit 演进日志

| 版本 | 范围 | pytest 增量 |
|------|------|-------------|
| v0.91.0-a | CognitiveTwinAgent 数据结构 + HumanFeedbackEntry | +12 |
| v0.91.0-b | Runtime + Plugin SDK 4 subscriber | +15 |
| v0.91.0-c | LCA 4 layer 接入 Human feedback | +21 |
| v0.91.0-d | 冷启动 + 持久化 + canary | +8 |
| v0.91.0-e | Plugin SDK 文档化 (本文档) | +0 (doctest only) |

累计 pytest: 1143 → 1199 (+56, +4.9%). 缺失清单 0.

---

## 七、相关文档

- `discussions/2026-08-12-v091-design.md`: v0.91 完整设计 (5 decisions + 5 sub-commit)
- `discussions/2026-08-11-v084-design.md`: v0.84 Plugin SDK 雏形设计
- `discussions/2026-08-11-v085-design.md`: v0.85 Plugin SDK 100% + Production Activation
- `ecos/cta/cognitive_twin.py`: CognitiveTwinAgent + HumanFeedbackEntry 实现
- `ecos/runtime/api.py`: 6 plan API (含 plan_human_feedback_aware)
- `ecos/lca/orchestrator.py`: LCAEngine._cognitive_twin + append_human_feedback
- `web/api/plugin_runtime.py`: PluginRuntime + 7 subscribers
- `examples/plugin_sample_human_feedback.py`: 5 use case 示例

---

## 八、Plugin SDK 调用样例

详见 `examples/plugin_sample_human_feedback.py` (5 use case):

1. **教师后台**: 订阅 `reflection_completed` → 读 human_feedback_trajectory → 生成学生反思分析
2. **家长 dashboard**: 订阅 `goal_changed` → 读 human_feedback_trajectory → 显示学习目标调整历史
3. **提示疲劳检测**: 订阅 `hint_requested` → 计数 → 提示教师学生可能过度依赖 hint
4. **走神提醒**: 订阅 `idle_detected` → 计数 → 提示教师学生可能需要干预
5. **深度反思分析**: 订阅 `reflection_completed` → LLM 分析 reflection_text → 写入 cognitive_twin

每个 use case 演示 Plugin 原则:
- 订阅 EventBus topic
- 构造 / 读取 `HumanFeedbackEntry`
- 调 `LCAEngine.append_human_feedback` 或读 `LCAEngine._cognitive_twin`
- 不直接 mutate `BeliefState` (防御性自检 [8])