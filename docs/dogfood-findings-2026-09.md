# Dogfood 发现清单（2026-09，试点前全流程自测）

> **背景**：v0.98.5 生产库清理后，Bisen 以真实用户身份跑通全流程（试点第 0 步）。
> 本文档记录 dogfood 过程中的发现，测完一轮后统一排优先级批量处理。
> **协作模式**：Claude 只读观察（DB/日志），发现 bug 只记录 + 给方案，Bisen 拍板后才动代码。

## 发现记录

### F-01 学生端导出报告只有 JSON 格式（2026-09-08）

- **现象**：学生端设置 TAB「导出学习报告 (JSON)」直接下载原始 JSON blob
- **评估**：后端 `/api/report/<sid>` 内容不简陋（summary + interpretation 规则引擎自然语言解读 + 完整 state），简陋的是交付形态——`interpretation` 已生成的人话被埋在 JSON 里，家长/学生无法阅读
- **方案（已拍板）**：选 C —— 前端 React 渲染 HTML 报告页（interpretation 为主体 + summary 数字，`window.print()` 打印即 PDF）作为主路径；JSON 降级为「导出原始数据（开发者）」次按钮保留
- **优先级**：P2（不阻塞试点，纯体验项）
- **状态**：📋 已拍板待做（dogfood 一轮结束后统一处理）

### F-02 今天 TAB「近况感知」挫败感等三维数据恒为默认值（2026-09-08）

- **现象**：学生端首页 MotivationPanel 的挫败感恒 0、投入度/信心恒 0.5（中性默认值），`observation_count` 恒 0
- **根因（已全链路排查）**：**生产链路无信号生产者**。MotivationProfile（v0.87.0 Kernel）消费端已建成（`ecos/lca/evaluator.py:156` frustration>0.7 → gain×0.7；`experiment_designer.py:266` → 强制 EXPLANATORY 降难度），`/api/state` 原样序列化默认值（`web/api/belief.py:477`），但答题流中没有任何代码从行为信号推导并写入 motivation observation——唯一写入入口 `plan_motivation_aware(motivation_observation=...)`（`ecos/runtime/api.py:340`）只是透传通道，生产路径从不传。built≠wired：数据结构 + 消费端 + UI 呈现三段齐备，中间的**信号推导段从未实现**
- **与数据库清理无关**：v0.98.5 清理前后行为一致，均为默认值
- **候选信号（实现时选）**：连续错误次数（response_history）/ 答题时延异常（evidence_log `raw_response_time`）/ 自评 4 档最悲观档（v0.97.2，试点要收集的信号之一）/ hint 请求频率（HintFatiguePlugin 已有 per-student 计数）
- **方案（已拍板）**：排 backlog，**试点数据回来后**从 evidence 回算标定映射再接实时路径——与 BKT 阈值、C 维折扣同批次；试点范围冻结，不提前接线引入新变量
- **附带可选项**：试点面向真实学生时，MotivationPanel 可加 `observation_count === 0` →「样本积累中」状态，避免默认值被误读（P2，UI 诚实性修正）
- **优先级**：P2（数据是派生量，不接不影响试点原始信号落库）
- **状态**：📋 已拍板待做（试点后批次）

## 已知占位项（避免 dogfood 期间误报为 bug）

以下为 v0.98.5 时点已知的「有意未接」项，见 `docs/for-partners.md` §九诚实标注表：

| 项 | 现状 | 计划 |
|----|------|------|
| 挫败感 frustration 恒 0 | MotivationProfile 消费端已建（LCA evaluator/planner），**生产链路无信号生产者**，UI 显示默认值 | 详见 **F-02**（试点数据回来后回算标定，与 C 维折扣同批次） |
| C 维折扣未接在线流程 | `confidence_for → 信念更新` 离线校准中 | 试点数据回来后一并校准接入 |
| BKT 衰减参数 | replay 读时视图，先验值 | 试点数据校准（v0.97.1 决策） |
