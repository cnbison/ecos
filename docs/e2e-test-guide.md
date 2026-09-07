# ECOS 端到端测试指南

> **适用版本**：v0.98.0 起。
> **目的**：从「学生端做题」一路验到「三端（学生/教师/家长）看到结果」，并核实数据落库。
> **与 [_启动与访问指南_](web-ui-quickstart.md) 的关系**：那份讲「怎么启动」，这份讲「启动之后怎么确认整条链路真的通了」。
> 约 10 分钟走完一遍。

---

## 0. 这是什么、为什么需要

单元测试（pytest，1583 项）验证的是「每个模块单独对不对」；但「生产环境里，答题 → 判题 → 状态更新 → 日志落库 → 三端展示」这条**组装起来的链路**有没有断，只有端到端能验证。本指南面向三类场景：

1. **拿真数据前**：确认试点采集链路（`evidence_log` / `event_log` / `calibration_log`）工作正常；
2. **交付/演示**：确认学生、教师、家长三个入口都能跑通一遍；
3. **接线审计**：核实某一版声称的「接线收口」在**生产路径**下是否真的生效（测试环境不一定等于生产）。

> ⚠️ 第 2 条、第 3 条正是本指南存在的意义——见 [§7 已知问题](#7-已知问题) 里的一个真实例子：一条接线在**测试环境**（legacy 路径）下通过、在**生产环境**（Plugin 路径）下却是断的。这类问题只有端到端能暴露。

---

## 1. 前置条件

与 [_启动与访问指南 §0_](web-ui-quickstart.md) 完全一致：

| 依赖 | 要求 | 验证 |
|---|---|---|
| Python | 3.11+ | `python3 --version` |
| Node.js | 18+ | `node --version` |
| LLM API key | `.env` 里 `MINIMAX_API_KEY` 或 `MOONSHOT_API_KEY` | 判题/评判需要它 |
| 数据库 | `web/ecos.db` 存在 | `ls -l web/ecos.db` |

```bash
# 首次准备
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cd web/frontend && npm install && npm run build && cd ..
```

> 缺 LLM key 时 `/api/judge` 返回 422（v0.56.1 起不降级、不写兜底），判题这一步会卡住，但不会污染任何状态。

---

## 2. 启动

```bash
# 后端（Flask，端口 5173）—— 生产形态：启动即注册 PluginRuntime subscriber
cd <ecos 仓库根目录>
ECOS_DUAL_AGENT_ENABLED=1 python -m web.api.app
```

两条启动日志需要确认：

- `DualAgentOrchestrator 初始化完成 (DUAL_AGENT_ENABLED=True, ...)` — 双 Agent 路径已开；
- `Production activation: PluginRuntime 启动 (subscriptions=...)` — **Plugin 路径已激活**（生产默认走这里，是 §4 验收的关键前提）。

> 前端已 `npm run build` 时，Flask 直接托管 `dist/`，无需另起 Vite。开发热更新才需要 `cd web/frontend && npm run dev`（Vite 5174）。

三个入口：

| 入口 | 地址 |
|---|---|
| 学生端 | `http://localhost:5173/` |
| 教师端 | `http://localhost:5173/teacher/` |
| 家长端 | `http://localhost:5173/parent/` |

---

## 3. 完整答题流验收（UI 手动路径）

用**一个全新的学生 ID**（例如 `lbcE2E`，避免复用历史数据）走一遍：

1. 打开学生端，输入学生 ID（或沿用 localStorage 记住的 ID）；
2. 做题 → 作答 → **揭晓对错之前**选「有几成把握」（4 档自评）；
3. 提交 → 看到判题结果（对/错 + 过程分析）；
4. 重复做几题（至少 1 题做「对」——真实知识题答对才会驱动认知状态更新，warmup 探针题不更新）。

每一步能走通、页面不白屏、判题有结果，即 UI 链路 OK。

---

## 4. 数据落库验收（关键，必做）

这是本指南最核心的一步：答完题后，用数据库核实「哪些日志真的写进去了」。这一步**不看 UI，直接看落库**，因为 UI 显示"答题成功"不代表日志落了库。

```bash
sqlite3 web/ecos.db "
SELECT 'calibration_log', COUNT(*) FROM calibration_log WHERE student_id='lbcE2E';
SELECT 'event_log',        COUNT(*) FROM event_log        WHERE student_id='lbcE2E';
SELECT 'evidence_log',     COUNT(*) FROM evidence_log     WHERE student_id='lbcE2E';
"
```

预期（每提交一题）：

| 表 | 每提交一题应新增 | 说明 |
|---|---|---|
| `calibration_log` | ≥1 行 | 双 Agent 校准/自评交互 |
| `event_log` | 2 行 | `response_submitted`（作答）+ `observation`（观测）|
| `evidence_log` | 5 行 | 每维（K/P/S/C/X）一行，`raw_response` 里带 `dim` 标记 |

逐表核对：

```bash
# evidence_log 的 dim 标记（应看到 K/P/S/C/X 各一行）
sqlite3 web/ecos.db "SELECT json_extract(raw_response,'$.dim'), COUNT(*) FROM evidence_log WHERE student_id='lbcE2E' GROUP BY 1;"

# event_log 的两种事件类型
sqlite3 web/ecos.db "SELECT event_type, COUNT(*) FROM event_log WHERE student_id='lbcE2E' GROUP BY 1;"
```

> ⚠️ **历史教训**：v0.98.0 曾在生产路径（Plugin）下这一步失败——`calibration_log` 正常但 `event_log`/`evidence_log` 恒 0，且 1583 项测试全绿（测试只走了 legacy 路径）。v0.98.1 已修复并补上 Plugin 路径回归测试（见 [§7](#7-已知问题与历史回归)）。这一步请保留为常设验收项：**「测试环境通过」不等于「生产路径通过」**。

---

## 5. 三端验收

在答题流走过之后，逐个入口确认能读到结果：

### 5.1 教师端（`/teacher/`）

- 病区/班级列表能看到刚才的学生；
- 点进该学生：五维诊断（K/P/S/C/X）+ 每维度**证据卡**（「系统为什么这么判断」）。

### 5.2 家长端（`/parent/`）

- 输入学生 ID，能看到四卡：投入状态、成长建议、五维概览、干预历史；
- 页面为**只读**——不会因为「查看」而创建幽灵学生。

### 5.3 学生端（`/`）

- 学生看到自己的进步与下一步。

> 三端能展示的前提是 §4 的日志落库正常，否则教师端证据卡会空、家长端五维/建议缺数据。

---

## 6. 常见失败排查

| 现象 | 处理 |
|---|---|
| `/api/judge` 返回 422 | LLM key 缺失/失效；失败不污染 state，可刷新重试 |
| 学生端「题目加载失败」 | `/api/state` 冷启动慢，等 1–2s 刷新 |
| 学生端是旧版 vanilla JS 页面 | `dist` 缺失，跑 `make frontend-build` |
| 教师/家长端证据卡空 | 先查 §4 落库；若 evidence_log 为 0，答题流没写库，非 UI 问题 |
| 改前端不生效 | dev 模式须 5173 + 5174 同时跑 |

---

## 7. 已知问题与历史回归

**[已修复 v0.98.1] 生产答题流（Plugin 路径）下 `event_log` / `evidence_log` 不落库**（2026-09-07 发现并修复）。

这条回归保留在此，因为它正是本指南存在意义的活例子——**1583 项 pytest 全绿，端到端一跑就现形**：

- **现象**：生产形态（`python -m web.api.app` 启动即激活 PluginRuntime）下答题，`calibration_log` 正常写入，但 `evidence_log` 与 `event_log` 对真实学生恒为 0。
- **根因**：`web/api/plugin_runtime.py` 的 `_handle_response_submitted` 调 `update_belief(..., log_event=False)`，旧注释认为「FeatureExtractor 已 emit response_submitted，避免重复」——但那混淆了两个 sink：`bus.publish` 是 EventBus 内存广播（不落库），FeatureExtractor 写的是 `event_log` 持久化行，本不重复。而 `log_event` 这个开关同时门控三处写入（FeatureExtractor emit / BeliefUpdater observation / v0.98.0 新增 evidence_log），`False` 把落库一并抑制。
- **为什么测试没抓到**：`tests/test_web_evidence_injection.py` 把 `_update_via_plugin_or_legacy` monkeypatch 成 `engine.update` 直调——**测试只走了 legacy 路径**，而生产默认走 Plugin 路径，恰好绕过。v0.98.1 补上了真实 PluginRuntime subscriber 的回归测试。
- **影响**：若未修复，试点的 H1 数据收集（依赖 `evidence_log`/`event_log` 零人工自动采集）会在生产下采集不到数据。
- **常设教训**：任何「接线收口」类改动，验收必须覆盖**生产实际走的路径**，而非只覆盖测试注入的路径；§4 的落库核对请保留为常设验收项。