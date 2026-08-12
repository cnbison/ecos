# ECOS POMDP Diagnostic 文档

**版本**: v0.93.0 (Phase 7+ 抽象推演 #6)
**日期**: 2026-08-12
**状态**: Kernel 100% production-ready
**对应设计**: `discussions/2026-08-12-v093-design.md`

---

## 一、POMDP Diagnostic 原则

ECOS POMDP Diagnostic 遵循 **kernel-mapping §1.3 Policy Engine + §5 CQRS 原则** 的核心原则:

> **POMDP 是 LCA 第 4 层 PolicyLearner 的可观测 surface; Diagnostic 是诊断可观测, 不干预策略**

具体含义:
1. **Diagnostic 永远**不直接调 `POMDPPolicy.update()` / `bayes_update()`
2. **Diagnostic 永远**只读 `POMDPPolicy.get_diagnostic()` 派生 (T/R/belief/coverage)
3. **Diagnostic 永远**不持有 `BeliefState` 引用 (per 防御性自检 [8] hard block)
4. **Runtime 是 sole entry**: `Runtime.diagnose_pomdp(student_id)` 委托 `LCAEngine.get_pomdp_diagnostic`, LCAEngine 委托 `POMDPPolicy.get_diagnostic`

POMDP Diagnostic 抽象推演:
- **v0.87.0-c**: POMDP Policy 雏形 (4 状态 + Bayesian belief + LinUCB 接口同构)
- **v0.88.0-c**: POMDP 完整 (依赖型 T(s'|s,a) + 固定 init R(s,a))
- **v0.89.0-c**: PBVI 集成 (α-vector)
- **v0.90.0-c**: T/R 在线学习 (Beta-Multinomial posterior)
- **v0.93.0-a**: POMDPDiagnostic 数据结构 (3 件套 + coverage)
- **v0.93.0-b**: Runtime + LCAEngine + Plugin SDK 全栈集成
- **v0.93.0-c**: 演化追踪 (timed snapshots N=50/K=10) + 持久化

POMDP Diagnostic 100% production: 任何 Plugin endpoint 走 Plugin 路径 + POMDPDiagnostic 派生走 POMDPPolicy.get_diagnostic() 单一入口.

---

## 二、POMDPDiagnostic 字段 (Frozen Dataclass)

`POMDPDiagnostic` 是 POMDP 诊断 surface 的核心数据结构, 派生走 `POMDPPolicy.get_diagnostic()` 单一入口.

### 2.1 POMDPDiagnostic 结构

```python
@dataclass(frozen=True)
class POMDPDiagnostic:
    T: TransitionPosteriorSnapshot       # Dirichlet 后验 (n_states × n_states × n_arms)
    R: RewardPosteriorSnapshot           # Beta 后验 (n_states × n_arms)
    belief: np.ndarray                   # 4 状态 posterior (n_states,)
    coverage: np.ndarray                 # per-(s, a) 样本数 (n_states × n_arms)
    most_likely_state: int               # argmax(belief)
    last_updated: datetime               # 调用时算 (不持久化)
    schema_version: str = "0.93.0"
```

**关键设计**:
- **frozen** (跟 `AlphaVector` / `HumanFeedbackEntry` / `ActionEntry` 同模式): 防止外部 mutation 干扰内部状态
- **schema_version="0.93.0"**: 独立 schema_version, 跟 `POMDPPolicy` "0.93.0" / `CognitiveTwinAgent` "0.92.0" 模式对齐
- **三件套 + coverage**: T + R + belief + coverage 一次性暴露 POMDP 全部可观测字段 (per design §1.3 Policy Engine 原则)
- **last_updated 派生**: `datetime.now()` 在 `get_diagnostic()` 调用时算, 不存额外字段 (per `CognitiveTwinAgent` `last_updated` 一致 pattern)

### 2.2 TransitionPosteriorSnapshot 结构

```python
@dataclass(frozen=True)
class TransitionPosteriorSnapshot:
    mean: np.ndarray                     # 3D (n_states, n_states, n_arms)
    count: np.ndarray                    # 3D int (n_states, n_states, n_arms)
    alpha0: float                        # uniform prior 默认 1.0
    schema_version: str = "0.93.0"
```

**派生**: `from POMDPPolicy._transition_posterior` (lazy / 已注入).

### 2.3 RewardPosteriorSnapshot 结构

```python
@dataclass(frozen=True)
class RewardPosteriorSnapshot:
    mean: np.ndarray                     # 2D (n_states, n_arms)
    alpha: np.ndarray                    # 2D (n_states, n_arms), Beta α
    beta: np.ndarray                     # 2D (n_states, n_arms), Beta β
    alpha0: float                        # uniform prior 默认 1.0
    variance: np.ndarray                 # 2D (n_states, n_arms) αβ / ((α+β)² (α+β+1))
    schema_version: str = "0.93.0"
```

**派生**: `from POMDPPolicy._reward_posterior` (lazy / 已注入).

### 2.4 POMDPDiagnostic JSON 序列化

`POMDPDiagnostic.to_dict()` 返 JSON 可序列化 dict (含 ndarray → list + datetime ISO + schema_version).
`POMDPDiagnostic.from_dict()` 重建 (防御性自检 [5]: schema_version 校验 raise).

---

## 三、Runtime.diagnose_pomdp API

Runtime 第 8 plan/query API (跟 v0.92 plan_action_aware 第 7 plan API 完全 parallel):

```python
from ecos.runtime.api import diagnose_pomdp

# 委托 LCAEngine.get_pomdp_diagnostic(student_id)
diagnostic = diagnose_pomdp(student_id="lbc001")
print(diagnostic.T.mean.shape)        # (4, 4, 10)
print(diagnostic.R.mean[0, 0])        # Beta posterior mean
print(diagnostic.belief)              # 4 状态 posterior
print(diagnostic.coverage[0, 0])      # per-(s, a) 样本数 (冷启动判断)
print(diagnostic.most_likely_state)   # argmax(belief) 0-3
```

**关键设计**:
- **Runtime 是 sole entry**: `Runtime.diagnose_pomdp` 委托 `LCAEngine.get_pomdp_diagnostic`, 不直接调 `POMDPPolicy.get_diagnostic`
- **缓存机制**: LCAEngine 维护 `self._pomdp_diagnostic: Dict[str, POMDPDiagnostic]` per-student dict, 缓存 miss 时 lazy collect
- **kwargs 注入**: `diagnose_pomdp(student_id, **kwargs)` 支持外部 LCAEngine 注入 (测试用, 跟 v0.92.0-b Runtime.plan_action_aware 完全 parallel pattern)
- **8 项防御性自检**: 异常 _log.warning + 返 None (silent pass 防御); schema_version 校验 raise (防御性自检 [5])

---

## 四、LCAEngine.get_pomdp_diagnostic API

LCAEngine 是 POMDPDiagnostic 的核心缓存层 (跟 v0.92.0-d `_cognitive_twin` 完全 parallel):

```python
from ecos.lca.orchestrator import LCAEngine, LCAEngineConfig

lca = LCAEngine(config=LCAEngineConfig(policy_type="pomdp", pomdp_seed=42))
diagnostic = lca.get_pomdp_diagnostic(student_id="lbc001")
# 缓存命中返 last-known, miss 时 lazy collect (调 POMDPPolicy.get_diagnostic)
```

**关键设计**:
- **per-student dict 缓存**: `self._pomdp_diagnostic: Dict[str, POMDPDiagnostic]` (跟 `self._cognitive_twin` / `self._last_intervention` 同 pattern)
- **auto-collect**: `LCAEngine.select_intervention` POMDP path 自动调 `_collect_pomdp_diagnostic` 写 cache (per v0.92.0-b `append_action_history` 完全 parallel pattern)
- **非 POMDP fallback**: `policy_type != "pomdp"` → _log.warning + 返 None (per 防御性自检 [1])
- **持久化**: LCAEngine.dump_state 含 `pomdp_diagnostic` 子字段, LCAStore `student_lca_state.pomdp_diagnostic TEXT` 列持久化

---

## 五、Plugin SDK 第 8 Subscriber

PluginRuntime 第 8 subscriber: `pomdp_diagnostic_updated`:

| # | Topic | 来源 | Handler | Runtime API |
|---|-------|------|---------|-------------|
| 8 | `pomdp_diagnostic_updated` | LCAEngine 触发 (auto-collect 后) | `_handle_pomdp_diagnostic_updated` | `Runtime.diagnose_pomdp` |

**Plugin 订阅样例**:
```python
from web.api.plugin_runtime import get_plugin_runtime
from ecos.cta.event_bus import get_default_bus

runtime = get_plugin_runtime()

@runtime.on("pomdp_diagnostic_updated")
def handle_diagnostic_updated(event):
    """Plugin 收到 POMDPDiagnostic 更新事件后, 自定义渲染逻辑."""
    student_id = event.payload.get("student_id")
    diagnostic = runtime.get_last_diagnostic_result(student_id)
    print(f"{student_id} most_likely_state: {diagnostic.most_likely_state}")
    print(f"{student_id} coverage[0, 0]: {diagnostic.coverage[0, 0]}")
```

**关键设计**:
- **Plugin 不调 Twin**: `pomdp_diagnostic_updated` subscriber 只读 `runtime.get_last_diagnostic_result()`, 不直接调 POMDPPolicy.get_diagnostic (per kernel-mapping §6 Plugin 原则)
- **subscription_count**: v0.93.0-b 起 `PluginRuntime.subscription_count()` 返 8 (跟 v0.91.0-b 4 subscriber → 7 → 8 演进同步)

---

## 六、演化追踪 (Timed Snapshots)

`POMDPPolicy._evolution: List[POMDPDiagnostic]` 提供 POMDP diagnostic 趋势追踪:

```python
from ecos.lca.l4_optimization.pomdp import POMDPPolicy

p = POMDPPolicy(seed=42)
# 跑 60 次 _update_t_r → 触发 1 个 snapshot (N=50 阈值)
for i in range(60):
    p.update(arm=i % 10, reward=0.5, observation=0)

# 演化追踪 getter
evolution = p.get_evolution()              # List[POMDPDiagnostic] (cap K=10)
print(len(evolution))                       # 1 (60 / 50 = 1 snapshot)
print(evolution[0].T.mean.shape)            # (4, 4, 10)
```

**关键设计**:
- **N=50 触发阈值**: 每次 `_update_t_r` 后 `_update_count += 1`, 触发 `_update_count >= _next_snapshot_at` 时截一个 POMDPDiagnostic
- **K=10 FIFO cap**: `_evolution` cap 10, 超过时最早 snapshot 被丢弃
- **持久化**: `POMDPPolicy.dump_state` 含 `evolution` (List[Dict]) + `update_count` (int) + `next_snapshot_at` (int) 字段
- **跟 v0.81 EventLog retention 同 pattern**: max_per_student cap 模式, 防止存储爆炸
- **getter**: `get_evolution()` 返 list copy (防止外部 mutation); `evolution_snapshot_count()` 返当前长度 (0 <= N <= 10)

---

## 七、防御性自检

POMDP Diagnostic 遵循 8 项防御性自检 (跟 v0.93.0 ECOS Kernel 一致):

| # | 项 | POMDPDiagnostic 状态 |
|---|----|---------------------|
| 1 | silent pass 扫描 | `get_diagnostic()` 异常 _log.warning + 返 uniform prior diagnostic; `_take_evolution_snapshot` 派生失败 _log.warning 不 raise |
| 2 | `__version__` 同步 | "0.93.0" bump (跟 POMDPDiagnostic / POMDPPolicy / CognitiveTwinAgent 同步) |
| 5 | schema_version 校验 | POMDPDiagnostic / TransitionPosteriorSnapshot / RewardPosteriorSnapshot schema_version="0.93.0", 老 snapshot raise |
| 8 | direct state mutation 扫描 | POMDPDiagnostic 不持有 BeliefState 引用; LCAEngine._pomdp_diagnostic dict mutation 走 self mutation; POMDPPolicy._evolution list mutation 走 self mutation |

**FUNC_ALLOWLIST**: 51 文件 (v0.93 无新增, 跟 v0.92.0-d 一致).

---

## 八、调用样例

完整使用样例见 `examples/plugin_sample_pomdp_diagnostic.py` (3 use case):

1. **teacher_progress_review**: 教师查看学生 POMDP diagnostic (T/R/belief/coverage)
2. **parent_engagement**: 家长查看学生 POMDP 演化追踪 (recent evolution snapshot)
3. **student_self_reflection**: 学生查看自己最可能状态 (most_likely_state) + 学习建议

**Smoke 测试**:
```python
from ecos.runtime.api import diagnose_pomdp
from web.api.app import create_app

app = create_app()
with app.app_context():
    diag = diagnose_pomdp("lbc001")
    assert diag.schema_version == "0.93.0"
    assert diag.T.mean.shape == (4, 4, 10)
    assert diag.R.mean.shape == (4, 10)
    assert diag.belief.shape == (4,)
    assert diag.coverage.shape == (4, 10)
```

---

## 后续 (v0.94+)

POMDP Diagnostic 100% production-ready. 后续 v0.94+ Teacher/Parent Dashboard 可直接 `diagnostic.to_dict()` 反序列化渲染:
- T 后验 heatmap (`get_transition_heatmap(action)` 返 2D ndarray)
- R 后验曲线 (`get_reward_curves(action)` 返 alpha/beta/mean/variance per state)
- belief pie chart (`diagnostic.belief` 4 维)
- coverage bar chart (`diagnostic.coverage[s, a]` per (s, a) 样本数, 冷启动判断核心)
- evolution line chart (`diagnostic.evolution` K=10 snapshot 趋势)