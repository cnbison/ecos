# v0.69.0 重新设计双 Agent Confidence 指标 — PRD

> **生成时间**: 2026-07-30
> **作者**: Mavis
> **拍板**: Bisen 2026-07-30 21:25 同意 B 方案 (per-question 答对概率预测)
> **目标版本**: v0.69.0
> **触发**: H3 验证暴露双 Agent confidence 指标选错 (`discussions/2026-07-30-H3-verification-B-report.md` §3.1)

---

## 0. TL;DR

H3 验证 V1/V2 失败不是互校本身失败, 是 **confidence 指标选错**:
- V1 `expected_gain` = LinUCB 预测的 reward/gain (state_delta), **不是答对概率**
- V2 `state_overall_confidence` = belief_state 5D 平均, **是系统对自身估计的把握度, 不是答对概率**

v0.69.0 核心改动: **让 LinUCB reward = actual_outcome**, `Intervention.expected_gain` 自动变成"答对概率预测"。落盘 calibration_log 加新字段 `dual_agent_confidence` (D1), 跟 V1/V2 三版兼容。Confidence 仅记录不参与 arm 选择 (C1), H3 验证归因干净。

---

## 1. 背景

### 1.1 H3 验证暴露的核心矛盾 (H3 报告 §3.1)

**H3 假设**: 双 Agent 互校有效减少 LLM 幻觉
**评估指标**: ECE (Expected Calibration Error), 越小越校准
**通过阈值**: 双 Agent ECE ≤ 0.10 + 显著优于单 Agent

**v0.68.0 验证结果** (lbc003, 35 样本):

| 指标 | 单 Agent | 双 V1 (expected_gain) | 双 V2 (overall_confidence) |
|---|---|---|---|
| 平均 confidence | 0.6491 | 0.1393 | 0.5231 |
| 平均 accuracy | 0.89 | 0.90 | 0.78 |
| ECE | 0.2366 | 0.7274 | 0.3769 |
| p-value vs 单 | — | 0.000009 (反向) | 0.000009 (反向) |

**结论**: ❌ H3 当前数据下未通过, **两种 confidence 指标都显著反向 (p < 0.0001)**

### 1.2 失败根因 (代码层确认)

| 信号 | 是什么 | 是不是答对概率 |
|---|---|---|
| `expected_gain` (`Intervention`) | `LCAEngine._estimate_gain` 用 `scale × (1 - K_mastery) × (0.5 + 0.5×scaffolding)` 简化估算 (`lca/orchestrator.py:540-559`) | ❌ 是"增长空间" |
| `expected_reward` (LinUCB) | `θ @ x` 预测的 reward (state_delta) | ❌ 是 mastery 增长预测 |
| `confidence_bound` (LinUCB) | `α √(x^T A_inv x)` 探索不确定性 (`linucb.py:87`) | ❌ 是 UCB 探索 bonus |
| `state_overall_confidence` | belief_state 5D 维度 confidence 平均 | ❌ 是系统对自身估计的把握度 |
| `confidence_in_evidence` (BeliefChallenge) | 硬编码默认 0.8 | ❌ 不是数据驱动 |
| **peer_review / peer_judge** | **代码中不存在** | — (候选方案, 未实现) |

**核心缺口**: 没有任何信号是"双 Agent 对每题答对概率的直接预测"。H3 验证设计是"互校抗幻觉"测答对概率置信度, 但当前没有任何字段在测这件事。

### 1.3 文档足迹 (防御性自检 [7] 触碰范围)

v0.68.0 落盘 `state_overall_confidence` 字段 (1 float per round, `calibration_log.message_payload`), V2 优先信号。
v0.68.0 之前 round 1-21 全没这字段, v0.68.0 之后 round 22+ 才有。
**当前可用 V2 数据: round 22 一个样本** (lbc003 2026-07-30 11:34 验证 1 道题), 统计意义不足。

---

## 2. 核心设计决策 (B4 + C1 + D1)

### 2.1 决策一览

| 设计点 | 选择 | 关键理由 |
|---|---|---|
| Q1: confidence 信号 | **B4. LinUCB reward = actual_outcome** | 唯一真"答对概率预测"路径, 改动集中, 独立 LCAEngine 隔离 |
| Q2: 跟 Intervention 关系 | **C1. 仅记录** | H3 验证归因干净, 不让 confidence 跟 arm 选择耦合 |
| Q3: calibration_log 改法 | **D1. 加新字段 `dual_agent_confidence`** | 跟 v0.68.0 范式一致, 三版兼容 V3/V2/V1 |

### 2.2 4 个候选方案对比 (Q1 完整利弊)

**B1. 维护独立 dual_agent confidence tracker (类似小 BKT 模型)**
- 利: 概念上跟 H3 完全对齐
- 弊: 要新加数据结构 + 训练逻辑; dual_agent 本身复杂, 再叠 BKT 风险高
- **不可取**: 架构复杂度爆炸

**B2. 改 `belief_state.overall_confidence` 语义让它真代表答对概率**
- 利: 字段已存在, 改动小
- 弊: rationale/generator.py L185 已引用 `c_confidence=belief_state.C.mastery_prob`, 改语义牵一发动全身
- **不可取**: 违反 v0.68.0 [7] 防御性警告 ("触碰运行时 state 要警告"), 历史 rationale 文本会变

**B3. 复用现有信号 (K.mastery_prob / 1-X.frustration) 当 confidence**
- 利: 不引入新模型
- 弊: **换汤不换药**, 本质"单 Agent 信号充双 Agent", 违背"双 Agent 互校"理念
- **不可取**: H3 验证就变成"两个单 Agent 互相对比"了

**B4. LinUCB reward 改 actual_outcome (让 expected_gain 自动变答对概率预测) ✅ 选**
- 利: 跟 H3 假设完全对齐; LinUCB 已有现成 `expected_reward = θ @ x` 公式
- 利: **dual_agent 内部 LCAEngine 是 v0.62.0-A 独立实例**, 改 reward 不污染教学 LCA
- 弊: 要改 LinUCB update 接口; dual_agent 内部 LinUCB 冷启动期 (v0.62.0-A 不持久化) 需要 fallback
- 风险点: 教学 LCA 路径的 `_estimate_gain` (lca/orchestrator.py:540-559) 要不要也改? **决策: 不改**, 教学 LCA 用简化估算, dual_agent 内部 LCA 用 LinUCB 预测, 两个引擎语义不同

### 2.3 3 个候选方案对比 (Q2 完整利弊)

**C1. 仅记录 (不参与 arm 选择) ✅ 选**
- 利: H3 验证归因干净 ("互校抗幻觉"独立于"决策策略")
- 利: 改动最小, 风险最低
- 弊: 双 Agent 核心价值是"互校 → 修正决策", confidence 旁路略尴尬 (但 v0.70.0+ 可以再演进)

**C2. 参与 arm 选择 (低 confidence 强制选简单干预)**
- 利: 让 confidence 真正"作用"于决策
- 弊: H3 验证里 confidence 跟 arm 选择耦合, ECE 不再纯测"互校抗幻觉"
- 风险: 把"互校价值"和"决策策略价值"混在一起测

**C3. 只在 rationale 文本里展示**
- 利: rationale 可读性提升
- 弊: H3 验证里 confidence 跟决策无关, 等于装饰

### 2.4 3 个候选方案对比 (Q3 完整利弊)

**D1. 加新字段 `dual_agent_confidence` (跟 v0.68.0 加 `state_overall_confidence` 同模式) ✅ 选**
- 利: 跟现有 v0.68.0 范式一致, CLAUDE.md [5] 防御性自检成熟
- 利: 老数据 (V1/V2) 继续可用, 新数据有 V3
- 利: H3 脚本 V3 优先 / V2 其次 / V1 兜底, 三版兼容
- 弊: 字段多一个

**D2. 改 `expected_gain` 字段语义 (让它真代表答对概率)**
- 利: 字段少
- 弊: **破坏向后兼容**, v0.60.0~v0.68.0 历史 calibration_log 全部语义错位
- 风险: rationale 文本含义会变 (虽然代码层确认不引用, 但未来维护风险)

**D3. 独立新表 `dual_agent_confidence_log`**
- 利: 跟 calibration_log 解耦
- 弊: 引入新持久化表, CLAUDE.md 防御性自检 [5] 要重做对齐
- 风险: round 一致性问题 (新表 vs calibration_log 写顺序)

---

## 3. 详细设计

### 3.1 B4: LinUCB reward 改 actual_outcome

#### 3.1.1 核心改动

**当前 (v0.68.0)**:
```python
# ecos/dual_agent/orchestrator.py:251 (v0.68.0)
self.lca_engine.update(
    student_id=sid,
    intervention=prev_calibrated.intervention,
    new_state=new_state,
    state_delta=state_delta,  # ← reward = state_delta (mastery 增长)
)
```

**v0.69.0 改**:
```python
# v0.69.0: reward = actual_outcome (答对概率, partial credit 0-1)
#   dual_agent 内部 LCAEngine 不动: 仍然调 lca_engine.update
#   但 reward 来源从 state_delta 改为 prev_calibrated.actual_outcome
actual_outcome = prev_calibrated.actual_outcome  # 0-1 partial credit
self.lca_engine.update(
    student_id=sid,
    intervention=prev_calibrated.intervention,
    new_state=new_state,
    reward=actual_outcome,  # ← v0.69.0 改: reward = actual_outcome
)
```

**关键决策**: 改的是 **dual_agent 内部 LCAEngine.update 的 reward 参数**, 不是 LinUCB 本身。LinUCB 的 update 接口 (lca/l4_optimization/linucb.py:92-106) 已经接受 `reward: float` 参数, 不需要改 LinUCB 代码。

**LinUCB 内部不变**: `update(arm, context, reward)` 公式 `A_a += xx^T, b_a += r*x` 通用, `reward` 可以是 state_delta 或 actual_outcome。**重点是 reward 的语义变了, 不是 update 公式变了**。

#### 3.1.2 LinUCB 预测路径 (选 arm 后给 expected_reward)

**当前**: `Intervention.expected_gain = LCAEngine._estimate_gain()` 简化估算 (lca/orchestrator.py:540-559)

**v0.69.0 改**:
```python
# v0.69.0: Intervention.expected_gain 改成 LinUCB 的 expected_reward
#   选 arm 时, LinUCB.select_arm 算 ucb_values[arm] = expected_reward + confidence_bound
#   取 chosen arm 的 expected_reward 部分 = θ_a @ x, 写入 Intervention.expected_gain
#
#   关键: 这只对 dual_agent 内部 LCAEngine 生效 (独立实例, v0.62.0-A 决策)
#   教学 LCA 路径 (web/api/lca.py) 不改, 仍用 _estimate_gain 简化估算
```

**实施位置**: `ecos/lca/orchestrator.py` LCAEngine.select_intervention 第 5 步 (生成候选 + LinUCB 选择) 末尾, 把 chosen arm 的 `expected_reward = θ @ x` 写入 `chosen.expected_gain`。

#### 3.1.3 冷启动期处理 (dual_agent 内部 LinUCB 不持久化)

v0.62.0-A 决策: dual_agent 内部 LCAEngine **不持久化 bandit 数据**, 重启后冷启动。这意味着前 N 轮 LinUCB 没数据, `expected_reward` 不可信。

**冷启动判定**:
```python
# v0.69.0: arm_pull_counts 总数 < 阈值 → 冷启动期
#  BanditConfig.arm_pull_counts.sum() < COLD_START_THRESHOLD (默认 10)
#  = 10 个 arm 各被拉 1 次 (或同 arm 拉 10 次)
def _is_linucb_cold_start(self, sid: str) -> bool:
    bandit = self.bandits.get(sid)
    if bandit is None:
        return True
    return int(bandit.bandit.arm_pull_counts.sum()) < self.config.bandit_config.cold_start_threshold
```

**冷启动期 fallback**:
```python
# v0.69.0: 冷启动期, expected_gain 用 _estimate_gain 简化估算 (跟教学 LCA 同)
#  非冷启动期, expected_gain 用 LinUCB 预测的 expected_reward
if self._is_linucb_cold_start(sid):
    chosen.expected_gain = self._estimate_gain(chosen, belief_state)
else:
    # LinUCB 预测: θ @ x (排除 confidence_bound, 只取 expected_reward)
    chosen.expected_gain = float(theta @ context)
```

**配置项**:
```python
@dataclass
class BanditConfig:
    n_arms: int = 10
    context_dim: int = 16
    alpha: float = 1.0
    min_reward: float = 0.0
    max_reward: float = 1.0
    cold_start_threshold: int = 10  # v0.69.0 新增 (默认 10, 即 10 次 arm pull 后 LinUCB 预测生效)
```

**冷启动期说明**:
- lbc003 在 v0.69.0 部署后, 前 10 道题 calibration_log 的 `dual_agent_confidence` 字段为 `_estimate_gain` 简化估算 (跟 V1 `expected_gain` 数值上接近, 但**写入字段不同**)
- 10 道之后, `dual_agent_confidence` = LinUCB `expected_reward` (θ @ x)
- H3 验证脚本 v0.69.0-d 会标记冷启动期数据 (跟 v0.64.0 加 `used_fallback` 同模式), 报告里清楚说明

### 3.2 C1: Confidence 仅记录不参与决策

**严格约束**: v0.69.0 confidence **不影响** LinUCB 的 arm 选择, 不影响 Intervention 决策的任何环节。

**理由**:
- H3 验证要"互校抗幻觉", 跟"决策策略"必须独立测, 否则 ECE 不归因
- v0.69.0 阶段只解决"答对概率指标"问题, 决策问题留 v0.70.0+
- 改动最小, 风险最低

**后续演进** (v0.70.0+ PRD 单独写):
- 可以让 confidence 影响 rationale 文本 (C3 方案)
- 可以让 confidence 影响 arm 选择 (C2 方案)
- 但要先看 v0.69.0 confidence 质量如何 (跟 actual_outcome 的相关性)

### 3.3 D1: calibration_log 加 `dual_agent_confidence` 字段

#### 3.3.1 落盘 schema

**当前** (v0.68.0 后):
```json
{
  "intervention_id": "...",
  "expected_gain": 0.15,           // V1 候选 (LinUCB 预测 reward / 简化估算)
  "actual_outcome": 0.8,           // partial credit 0-1
  "state_overall_confidence": 0.52 // V2 候选 (v0.68.0 新增, belief_state 5D 平均)
}
```

**v0.69.0 改**:
```json
{
  "intervention_id": "...",
  "expected_gain": 0.15,              // 保留 (向后兼容)
  "actual_outcome": 0.8,              // 保留
  "state_overall_confidence": 0.52,   // 保留 (V2, v0.68.0 后数据)
  "dual_agent_confidence": 0.72,      // ← v0.69.0 新增 (V3, 优先 confidence)
  "dual_agent_confidence_source": "linucb"  // ← v0.69.0 新增 (标记来源: "linucb" 或 "estimate_gain_fallback")
}
```

**关键设计**:
- **3 版 confidence 并存**: V3 (`dual_agent_confidence`) / V2 (`state_overall_confidence`) / V1 (`expected_gain`)
- **额外标记 `source`**: 区分 LinUCB 预测 vs 冷启动 fallback, H3 验证里能识别冷启动数据
- **`expected_gain` 字段保留**: dual_agent 内部 LCA 用 LinUCB 预测, 教学 LCA 用 _estimate_gain, 数值含义不一致但**字段不删**, 避免破坏历史

#### 3.3.2 写入位置

`web/api/dual_agent.py` `_write_calibration_log` 函数 (当前在 v0.68.0 加了 `state_overall_confidence`, 同位置加 `dual_agent_confidence` 和 `dual_agent_confidence_source`):

```python
# v0.69.0: 加 dual_agent_confidence 字段
#  来源: 选 Intervention 时的 expected_gain (v0.69.0 起 = LinUCB 预测 / 冷启动 fallback)
#  跟 expected_gain 数值上相同, 但**写入不同字段** (语义清晰, 避免混淆)
dual_agent_confidence = None
dual_agent_confidence_source = None
try:
    if result.intervention is not None:
        dual_agent_confidence = float(result.intervention.expected_gain)
        # 来源标记 (跟 result.metadata 配合读, 冷启动期由 orch 写入)
        dual_agent_confidence_source = result.metadata.get(
            "dual_agent_confidence_source", "linucb"
        )
except Exception:
    _log.debug("拿 dual_agent_confidence 失败 (student=%s), 留 None", student_id, exc_info=True)
    dual_agent_confidence = None
    dual_agent_confidence_source = None

message_payload = {
    "intervention_id": ...,
    "expected_gain": result.expected_gain,
    "actual_outcome": result.actual_outcome,
    "state_overall_confidence": state_overall_confidence,
    "dual_agent_confidence": dual_agent_confidence,  # v0.69.0 新字段
    "dual_agent_confidence_source": dual_agent_confidence_source,  # v0.69.0 新字段
}
```

#### 3.3.3 来源标记写入位置

`ecos/dual_agent/orchestrator.py` `_is_linucb_cold_start` 判定后, 把 source 写入 `chosen.metadata`:

```python
# v0.69.0: 选 Intervention 时标记 source
if self._is_linucb_cold_start(sid):
    chosen.expected_gain = self._estimate_gain(chosen, belief_state)
    chosen.metadata["dual_agent_confidence_source"] = "estimate_gain_fallback"
else:
    chosen.expected_gain = float(theta @ context)
    chosen.metadata["dual_agent_confidence_source"] = "linucb"
```

---

## 4. 数据兼容性

### 4.1 历史数据兼容

| 字段 | v0.69.0 之前 | v0.69.0 之后 |
|---|---|---|
| `expected_gain` | 简化估算 (lbc003 round 1-21) | dual_agent: LinUCB 预测 / fallback; 教学 LCA: 简化估算 |
| `state_overall_confidence` | lbc003 round 22+ 有, 之前 None | 继续写 (V2 候选, 备用) |
| `dual_agent_confidence` | **字段不存在** | v0.69.0 后新落库的全有 |
| `dual_agent_confidence_source` | **字段不存在** | v0.69.0 后新落库的全有 |

### 4.2 H3 验证脚本 (compute_h3_ece.py) 升级

`compute_dual_agent_ece` 加 V3 优先逻辑:
```python
# v0.69.0-d: V3 优先 / V2 其次 / V1 兜底
dual_conf = payload.get("dual_agent_confidence")
if dual_conf is not None:
    conf = float(dual_conf)
    version = "V3"
else:
    overall_conf = payload.get("state_overall_confidence")
    if overall_conf is not None:
        conf = float(overall_conf)
        version = "V2"
    else:
        conf = float(payload.get("expected_gain", 0.5))  # V1 兜底
        version = "V1"
```

报告里加版本分布:
```
- V3 (dual_agent_confidence): 25 样本
- V2 (state_overall_confidence): 6 样本
- V1 (expected_gain fallback): 5 样本
- 合计: 36 样本
```

**冷启动期单独标记**:
```python
# v0.69.0-d: 标记冷启动数据
source = payload.get("dual_agent_confidence_source")
if source == "estimate_gain_fallback":
    confidence_is_cold_start = True
else:
    confidence_is_cold_start = False
```

报告里 ECE 分两段算: 冷启动期 vs 非冷启动期, 让 Bisen 直观看到 LinUCB 预测质量。

---

## 5. 风险与缓解

| 风险 | 缓解 |
|---|---|
| dual_agent 内部 LinUCB 冷启动期 (前 10 题) 数据失真 | 报告分两段 (冷启动 / 非冷启动), source 字段标记; BanditConfig.cold_start_threshold 默认 10 |
| LinUCB reward 改 actual_outcome 后, 历史 calibration_round 数据对比性下降 | V3/V2/V1 三版兼容, 报告里分版本算; H3 阈值不用 v0.68.0 报告里那批数据 |
| `Intervention.expected_gain` 数值含义不一致 (dual_agent 路径 LinUCB 预测, 教学 LCA 路径简化估算) | 加注释说明; 不在 rationale 文本里 (已确认 rationale 不引用 expected_gain, §3.1.1 风险点 2) |
| v0.69.0 改动触及 dual_agent orchestrator 主循环 (process_observation) | 防御性自检 [6]: 失败不污染 in-memory state; [7]: 改动范围提前在 PR 头部写清楚 |
| dual_agent 内部 LCAEngine 冷启动时, expected_gain = _estimate_gain 跟 V1 数值上接近, V1/V3 区分模糊 | **V3 字段独立** (`dual_agent_confidence` 不是 `expected_gain`), 数值上可以相近, 但语义清晰, H3 脚本按字段名读取, 不会混 |
| 冷启动期 dual_agent_confidence 跟 V1 expected_gain 数值相近, H3 验证提升不明显 | 真正有效数据要 10+ 轮后, lbc003 答 30+ 题足够覆盖冷启动期 |
| 教学 LCA 路径 (web/api/lca.py) 不动, lbc001 / lbc002 答题行为不变 | v0.62.0-A 隔离决策保留; 加注释明示 "dual_agent 路径改动, 教学 LCA 路径不动" |

---

## 6. CLAUDE.md [7] 防御性自查: 触碰范围

### 6.1 v0.69.0 触碰范围

**触碰**:
- `ecos/dual_agent/orchestrator.py` (process_observation 主循环, LCAEngine.update 调用点)
- `ecos/lca/orchestrator.py` (LCAEngine.select_intervention 第 5 步, 改 chosen.expected_gain 来源)
- `ecos/lca/l4_optimization/policy_learner.py` (如有 wrapping LinUCB, 加 reward 参数透传)
- `web/api/dual_agent.py` (_write_calibration_log 加新字段)
- `scripts/compute_h3_ece.py` (V3 优先逻辑 + 冷启动分段)
- `ecos/lca/l4_optimization/linucb.py` **不动** (接口已支持 reward 参数)
- `ecos/__init__.py` (version bump 0.68.0 → 0.69.0)
- `CHANGELOG.md` (v0.69.0 头部条目)

**不动**:
- `ecos/cta/belief_state.py` (BeliefState 字段不动, 避免 rationale 文案影响)
- `ecos/lca/intervention.py` (Intervention 数据结构不动, 不加 confidence 字段, 避免破坏向后兼容)
- `ecos/lca/rationale/generator.py` (rationale 文本不受影响, 跟 §3.1.1 风险点 2 一致)
- 教学 LCA 路径 (web/api/lca.py, v0.62.0-A 隔离决策保留)
- lbc001 / lbc002 历史 calibration_log (老数据 V1/V2 继续读, 不重写)
- lbc003 已有 calibration_log (round 22+ 已有 state_overall_confidence, 继续保留 V2, 新落库加 V3)

### 6.2 不动数据自查

- **lbc001** (60+ 题历史): 不动 (教学 LCA 路径完全不动)
- **lbc002** (60+ 题历史): 不动 (同上)
- **lbc003** calibration_log 已有 round (round 1-22+): 不重写, 新字段只在 v0.69.0 后新落库的行有
- **students.***: 不动
- **student_lca_state.***: 不动 (教学 LCA 路径, v0.62.0-A 隔离)
- **student_dual_agent_state.***: 不动 (8 字段 dump/load 不变, 只在 LCAEngine.update 调用的 reward 参数变化)

### 6.3 风险与缓解 (防御性 [1-5] 静态检查清单)

| 防御性条款 | 检查项 | 实施 |
|---|---|---|
| [1] silent pass | orchestrator / LCAEngine / compute_h3_ece 改动不能 silent pass | try/except + _log.warning / debug + raise 主流程 |
| [2] __version__ | 0.68.0 → 0.69.0 | ecos/__init__.py bump, CHANGELOG 头部条目 |
| [3] detect_with_hits | 跟 v0.69.0 无关 (不动 CTA) | N/A |
| [4] HTML class vs CSS | 跟 v0.69.0 无关 (不动 UI) | N/A |
| [5] DB 恢复字段完整性 | calibration_log 新增 2 字段, 兼容老 None | 读侧 (compute_h3_ece) 兼容 None, 写侧 (web/api/dual_agent) try/except + None fallback |
| [6] 失败不污染 in-memory | LCAEngine.update reward=actual_outcome 失败不能污染 state | try/except, 失败时用 state_delta fallback (跟之前一致) |
| [7] 架构升级前警告历史状态丢失 | **本 PRD 头部已写明 §6.1 触碰范围 + §6.2 不动数据** | ✅ |
| [8] pytest 套件 | 新加 test: B4 LinUCB 预测路径, C1 confidence 仅记录, D1 新字段落盘 | tests/ 加 5+ 测试, 总数保持 245+ |

---

## 7. 实施步骤 (v0.69.0 拆 a~e)

### 7.1 v0.69.0-a: LinUCB 冷启动判定 + BanditConfig 加 cold_start_threshold

**改动文件**:
- `ecos/lca/l4_optimization/linucb.py`: 不动 (接口已支持)
- `ecos/lca/orchestrator.py`: BanditConfig 加 `cold_start_threshold: int = 10`, LCAEngine 加 `_is_linucb_cold_start(sid)` 方法
- `ecos/lca/l4_optimization/policy_learner.py`: 透传 reward (如有 wrapping)

**测试**:
- `tests/test_linucb_cold_start.py`: 冷启动判定 + threshold 边界
- 跑现有 LinUCB 测试, 验证不破坏

**commit message** (Bisen 风格):
```
v0.69.0-a: LinUCB 冷启动判定 + BanditConfig 加 cold_start_threshold (H3 BUG 修复前置)

- BanditConfig 加 cold_start_threshold: int = 10 字段
- LCAEngine 加 _is_linucb_cold_start(sid) 方法 (arm_pull_counts.sum() < 阈值)
- 防御性自检 [1]: 冷启动判定失败兜底返回 True (保守, 走简化估算)
- 防御性自检 [2]: __version__ 不动 (a 阶段)
- 245+ 测试
```

### 7.2 v0.69.0-b: LCAEngine.select_intervention 改 expected_gain 来源 (仅 dual_agent 内部生效)

**改动文件**:
- `ecos/lca/orchestrator.py`: select_intervention 第 5 步末尾, 选 arm 后判定冷启动, 改 `chosen.expected_gain` 来源
- 加 `chosen.metadata["dual_agent_confidence_source"]` 标记

**关键设计**:
- 改动对 dual_agent 内部 LCAEngine 生效 (用 v0.62.0-A 独立实例)
- 教学 LCA 路径不动 (仍用 `_estimate_gain` 简化估算)
- 实施方法: 用 `if not self.config.use_llm_rationale and self.config.dual_agent_mode:` 区分? **不**, 更干净的方法: **在 dual_agent orchestrator 调 LCAEngine.update 时改 reward 参数**, 不改 LCAEngine.select_intervention

**重新设计 v0.69.0-b**:
- **不**改 `LCAEngine.select_intervention` (避免同时改教学 LCA 路径)
- 改 `ecos/dual_agent/orchestrator.py` process_observation 内调 LCAEngine.update 的 reward 参数 (state_delta → actual_outcome)
- `Intervention.expected_gain` 仍是 `LCAEngine._estimate_gain` 简化估算 (跟之前一致)
- **dual_agent_confidence 字段** 不从 `Intervention.expected_gain` 取, 而是**直接用 LinUCB 预测的 expected_reward** (从 LCAEngine 内部拿, 不通过 Intervention)

**重新设计的 v0.69.0-b 实施位置**:
- `ecos/dual_agent/orchestrator.py` process_observation step "LCA update" 区域 (L250-256)
- 改 reward = prev_calibrated.actual_outcome (替代 state_delta)
- 不动 Intervention.expected_gain (LCAEngine.select_intervention 不动)
- 新加 helper: `_compute_dual_agent_confidence(sid, intervention)` 返回 `(float, source_str)`, 用 LinUCB 内部 θ @ x

**实施细节**:
```python
# ecos/dual_agent/orchestrator.py process_observation 改动
# Step 3 末尾: 在 LCAEngine.update 之前, 计算 dual_agent_confidence
dual_agent_confidence = None
dual_agent_confidence_source = "linucb"
try:
    # 拿当前 context (跟选 arm 时同一份, 不重新算)
    context = self._build_context(current_state)  # TODO: 跟 LCAEngine._build_context 对齐
    bandit = self.lca_engine.bandits.get(sid)
    if bandit is None or self._is_linucb_cold_start(sid):
        dual_agent_confidence_source = "estimate_gain_fallback"
        dual_agent_confidence = self.lca_engine._estimate_gain(calibrated.intervention, current_state)
    else:
        # LinUCB 预测: θ_a @ x (排除 confidence_bound)
        arm_idx = ...  # TODO: 拿 chosen arm 的 index
        theta = np.linalg.inv(bandit.A[arm_idx]) @ bandit.b[arm_idx]
        dual_agent_confidence = float(theta @ context)
except Exception:
    _log.debug("拿 dual_agent_confidence 失败 (sid=%s), fallback", sid, exc_info=True)
    dual_agent_confidence = calibrated.intervention.expected_gain
    dual_agent_confidence_source = "estimate_gain_fallback"

# Step 3 LCA update: reward 改 actual_outcome
self.lca_engine.update(
    student_id=sid,
    intervention=prev_calibrated.intervention,
    new_state=new_state,
    reward=actual_outcome,  # ← v0.69.0 改 (从 state_delta 改 actual_outcome)
)

# 存到 metadata, _write_calibration_log 读取
calibrated.metadata["dual_agent_confidence"] = dual_agent_confidence
calibrated.metadata["dual_agent_confidence_source"] = dual_agent_confidence_source
```

**重新设计的 v0.69.0-b commit message**:
```
v0.69.0-b: dual_agent 内部 LCAEngine 改 reward=actual_outcome + 计算 dual_agent_confidence

- ecos/dual_agent/orchestrator.py: process_observation LCA update 改 reward 参数
  - 之前: reward = state_delta (mastery 增长预测)
  - 现在: reward = actual_outcome (partial credit 0-1, 答对概率直接度量)
- 教学 LCA 路径完全不动 (v0.62.0-A 隔离决策保留)
- 新增 _compute_dual_agent_confidence helper:
  - 冷启动期 (arm_pull_counts.sum() < 10): 走 _estimate_gain fallback
  - 非冷启动期: LinUCB θ @ x 预测
- calibrated.metadata 加 dual_agent_confidence + dual_agent_confidence_source 字段
- 防御性自检 [6]: 失败不污染 in-memory, fallback 到 calibrated.intervention.expected_gain
- 防御性自检 [1]: 拿 LinUCB 内部状态失败 _log.debug + fallback
- 245+ 测试
```

### 7.3 v0.69.0-c: web/api/dual_agent.py 加 dual_agent_confidence 落盘字段

**改动文件**:
- `web/api/dual_agent.py` `_write_calibration_log`: message_payload 加 `dual_agent_confidence` + `dual_agent_confidence_source` 字段
- 失败兜底: 拿 confidence 失败 → 留 None, 不阻断 calibration_log 落盘 (跟 v0.68.0 加 state_overall_confidence 同模式)

**commit message**:
```
v0.69.0-c: calibration_log 加 dual_agent_confidence 字段 (D1 落盘)

- web/api/dual_agent.py _write_calibration_log 加 2 字段:
  - dual_agent_confidence: float (V3 优先 confidence, 来自 calibrated.metadata)
  - dual_agent_confidence_source: str ("linucb" 或 "estimate_gain_fallback")
- 跟 v0.68.0 加 state_overall_confidence 同模式 (CLAUDE.md [5] 防御性自检成熟)
- 失败兜底: 拿 confidence 失败 → 留 None, _log.debug + 不阻断主流程
- 老 calibration_log 行 (v0.69.0 之前) 没这 2 字段, compute_h3_ece V3 优先逻辑跳过 (V2/V1 兜底)
- 245+ 测试
```

### 7.4 v0.69.0-d: compute_h3_ece.py 加 V3 优先逻辑 + 冷启动分段

**改动文件**:
- `scripts/compute_h3_ece.py` `compute_dual_agent_ece`:
  - V3 (`dual_agent_confidence`) 优先 / V2 (`state_overall_confidence`) 其次 / V1 (`expected_gain`) 兜底
  - 报告加版本分布统计
  - 冷启动期数据 (`dual_agent_confidence_source == "estimate_gain_fallback"`) 单独标记
  - ECE 分两段算: 冷启动期 vs 非冷启动期
- `scripts/compute_h3_ece.py` `format_report`: 加 V3/V2/V1 版本分布 + 冷启动段 ECE 报告

**commit message**:
```
v0.69.0-d: compute_h3_ece V3 优先 + 冷启动分段 (H3 验证重跑前置)

- scripts/compute_h3_ece.py compute_dual_agent_ece 改 confidence 选取逻辑:
  - V3 (dual_agent_confidence) 优先 → V2 (state_overall_confidence) → V1 (expected_gain) 兜底
- 加版本分布统计: 报告 §2 显示 V3/V2/V1 各多少样本
- 冷启动分段: dual_agent_confidence_source == "estimate_gain_fallback" 的样本单独算 ECE
- 报告 §5 加冷启动段 vs 非冷启动段对比, 让 Bisen 直观看到 LinUCB 预测质量
- 245+ 测试 (H3 脚本本身不跑 pytest, 但 manual test 验证)
```

### 7.5 v0.69.0-e: lbc003 答 30+ 题, 重跑 H3 写 B+ 报告

**操作**:
- lbc003 用 ECOS_DUAL_AGENT_ENABLED=1 启动, 答 30+ 道题
- 跑 `python scripts/compute_h3_ece.py --student-id lbc003`
- 看 V3 优先 confidence 的 ECE 跟 V1/V2 哪个更校准
- 看冷启动段 vs 非冷启动段 ECE 差异
- 写 `discussions/2026-07-30-v0690-H3-verification-report.md` (B+ 报告)

**commit message**:
```
v0.69.0-e: lbc003 答 30+ 题, 重跑 H3 写 B+ 报告 (B4 验证收尾)

- discussions/2026-07-30-v0690-H3-verification-report.md: B+ 报告
- 验证 B4 设计的 dual_agent_confidence 跟 actual_outcome 校准度
- 跟 v0.68.0 B 报告对比: ECE 是否显著降低
- 冷启动段 vs 非冷启动段对比: LinUCB 预测质量
- 决策: B4 设计是否需要回滚 / 微调 / 继续
- 245+ 测试
```

---

## 8. 验证方法

### 8.1 单元测试 (pytest)

| 测试 | 验证点 | 文件 |
|---|---|---|
| `test_linucb_cold_start.py` | _is_linucb_cold_start 判定 + threshold 边界 | tests/ |
| `test_lca_update_reward_actual_outcome.py` | LCAEngine.update reward 参数改 actual_outcome, LinUCB A/b 矩阵更新正确 | tests/ |
| `test_dual_agent_confidence_computation.py` | _compute_dual_agent_confidence 冷启动 / 非冷启动 / 失败 fallback 三种路径 | tests/ |
| `test_calibration_log_dual_confidence.py` | _write_calibration_log 落盘 2 字段, 老数据兼容 | tests/ |
| `test_compute_h3_ece_v3_priority.py` | V3 优先 / V2 / V1 兜底 + 冷启动分段 | tests/ |

**总数**: 245+ (现有) + 5+ (新增) = 250+ 测试

### 8.2 集成测试 (lbc003 答题)

- lbc003 用 ECOS_DUAL_AGENT_ENABLED=1 启动 Flask
- 答 30+ 道 Python 基础题
- 验证:
  - 前 10 道 calibration_log 的 dual_agent_confidence_source 都是 "estimate_gain_fallback"
  - 10 道后开始出现 "linucb"
  - V3 ECE 跟 V1/V2 对比, 看哪个更校准
  - 冷启动段 vs 非冷启动段 ECE 差异

### 8.3 H3 验证 (重跑)

- 跑 `python scripts/compute_h3_ece.py --student-id lbc003`
- 报告 v0.69.0-e 写 B+ 报告
- 跟 v0.68.0 B 报告对比:
  - V3 ECE 是否 < V1/V2 ECE
  - V3 是否显著优于单 Agent baseline
  - 冷启动段 vs 非冷启动段是否分得开

### 8.4 通过标准

| 维度 | 通过 | 不通过 |
|---|---|---|
| 测试 | 250+ pytest 全过 | 任何失败 |
| V3 ECE | < 0.30 (跟 V1 0.72, V2 0.38 比显著改善) | ≥ 0.30 (B4 失败) |
| V3 vs 单 Agent | ECE 差距缩小 或 至少不反向 | 显著反向 (B4 失败) |
| 冷启动分段 | 非冷启动段 ECE < 冷启动段 (LinUCB 预测质量高) | 非冷启动段 ≥ 冷启动段 (LinUCB 没用) |
| rationale 文本 | 跟 v0.68.0 文本基本一致 (L185 c_confidence 不变) | 文本明显变化 (B4 破坏了 rationale) |

---

## 9. 不做的事 (out of scope)

**v0.69.0 明确不做** (留给后续版本):

1. **C2. confidence 参与 arm 选择** (留 v0.70.0+ PRD 单独设计)
2. **C3. confidence 写入 rationale 文本** (留 v0.70.0+)
3. **B1. 独立 confidence tracker** (B4 走 LinUCB 路径, 不引入新模型)
4. **B2. 改 belief_state.overall_confidence 语义** (Bisen 触发 1 次拒绝: 触碰运行时 state 风险)
5. **D2. 改 expected_gain 字段语义** (Bisen 触发 1 次拒绝: 破坏向后兼容)
6. **D3. 独立新表 dual_agent_confidence_log** (Bisen 触发 1 次拒绝: 新表 round 一致性风险)
7. **教学 LCA 路径 (web/api/lca.py) 改动** (v0.62.0-A 隔离决策保留)
8. **reliability diagram 画图** (matplotlib 依赖, v0.70.0+ 评估)
9. **C 主导题扩 20+ 题** (v0.54.0 后续)
10. **元反思模式** (v0.63.0 后续)

---

## 10. 关键 commit 信息 (规划)

```
v0.69.0-a LinUCB 冷启动判定 + BanditConfig 加 cold_start_threshold
v0.69.0-b dual_agent 内部 LCAEngine 改 reward=actual_outcome + 计算 dual_agent_confidence
v0.69.0-c calibration_log 加 dual_agent_confidence 字段 (D1 落盘)
v0.69.0-d compute_h3_ece V3 优先 + 冷启动分段 (H3 验证重跑前置)
v0.69.0-e lbc003 答 30+ 题, 重跑 H3 写 B+ 报告 (B4 验证收尾)
```

**v0.69.0 全部 commit (a~e) 触碰**:
- 4 个 Python 文件 (orchestrator.py, lca/orchestrator.py, web/api/dual_agent.py, scripts/compute_h3_ece.py)
- 1 个新测试文件 (test_linucb_cold_start.py)
- 2 个改测试文件 (test_dual_agent_confidence_computation.py, test_calibration_log_dual_confidence.py)
- 1 个新讨论文档 (discussions/2026-07-30-v0690-H3-verification-report.md)
- ecos/__init__.py (version bump)
- CHANGELOG.md (v0.69.0 头部)

**估计改动行数**: +200~300 行 (含测试), -30 行

---

## 11. 相关链接

- v0.68.0 验证小结: `discussions/2026-07-30-v0680-verification.md`
- H3 B 报告 (V1/V2 失败): `discussions/2026-07-30-H3-verification-B-report.md`
- H3 A 报告 (lbc001, v0.63.0): `discussions/2026-07-29-H3-verification-report.md`
- CHANGELOG v0.68.0 段 (后续 v0.69.0 计划): `CHANGELOG.md` L3627
- dual_agent orchestrator: `ecos/dual_agent/orchestrator.py`
- LCAEngine: `ecos/lca/orchestrator.py`
- LinUCB: `ecos/lca/l4_optimization/linucb.py`
- 落盘逻辑: `web/api/dual_agent.py`
- H3 脚本: `scripts/compute_h3_ece.py`

---

**PRD 拍板状态**: ✅ Bisen 2026-07-30 21:25 同意 B 方案 (B4 + C1 + D1)
**下一步**: 实施 v0.69.0-a (LinUCB 冷启动判定 + BanditConfig 加 cold_start_threshold)
