# 2026-09-05 ECOS 恢复期 A2 reconcile v0.97.3 — 会话记录

- **日期**: 2026-09-05
- **主题**: ECOS 恢复期 backlog P2 — A2 reconcile (per-misconception 证据驱动权重)
- **参与者**: Bisen × Claude (minimax-m3)
- **背景**: 恢复期 backlog P2 (README §下一步) 触发条件已就位:
  - ✅ v0.97.2 学生自评观测落地
  - ✅ `calibration_view.expected_accuracy` 作查询入口已备
  - ✅ evidence_log 原料就位 (misc_hits JSON 列 + structured_correctness + problem_id + skill_id)

## 核心结论

**A2 reconcile 落地三选一拍板**: 选 A (落 reconcile 模板 + 暂不接 C 折扣)。

| 候选 | 选择理由 | 否决理由 |
|---|---|---|
| **A (推荐) 落 reconcile + 暂不接 C** | 落算法 + DB + API + UI 完整闭环; 不违反 v0.97.2 拍板纪律 | 需 4 段原子 commit, 工作量适中 |
| B 仅暴露 evidence | 零新算法, 风险最小 | P2 backlog 实质冻结; 验证数据长期不来 |
| C 立即挂 C 折扣 | A2 闭环最完整 | 推翻 v0.97.2 "等试点数据" 拍板; 试点前无可验证基准 |

## 产出文件

### 代码 (a/b/c 段已分 3 个原子 commit)

- **NEW `ecos/cta/misconception_reconcile.py`** — `MisconceptionEvidenceTracker` (per-student) + `record_success/failure` + `reconcile()` + `quarantined()` + `confidence_for()` (C 维度折扣接入点, 暂不挂 BeliefState) + `MisconceptionEvidenceRow` 数据类 + `load_tracker_for_student` / `reconcile_for_student` 工厂
- **MODIFY `ecos/persistence/db.py`** — 新表 `misconception_evidence` (PK=(student_id, misc_id) upsert 幂等) + 3 方法 save/load/delete
- **MODIFY `ecos/cta/__init__.py`** — 导出 4 个公开符号
- **MODIFY `ecos/cta/belief_engine.py`** — `@property feature_extractor` 暴露 (与 perception_critic 同款)
- **MODIFY `web/api/belief.py`** — `submit_answer` 末尾注入 reconcile 段 (session 窗口, 排序时间升序, 失败兜底不阻断主流程)
- **NEW `web/api/teacher.py`** — `GET /api/teacher/students/<id>/misconceptions` 端点
- **MODIFY `web/frontend/src/api/{client,types}.ts`** — `fetchMisconceptions` + `MisconceptionsResponse` / `MisconceptionEvidenceItem` 类型 + 端点契约
- **MODIFY `web/frontend/src/pages/StudentDetailPage.tsx`** — `MisconceptionsCard` 组件 (三色置信度 + 4 档状态)
- **MODIFY `web/frontend/src/api/client.test.ts`** — 端点契约 +2

### 测试 (48 项新测试, 0 回归)

- `tests/test_misconception_reconcile.py` — 34 项 (Laplace 数学 + reconcile 分支 + quarantine + data class + DB 往返 + 工厂 + 防御性自检 [1])
- `tests/test_belief_reconcile_integration.py` — 7 项 (端到端 5 路径 + 时序排序 + 防御性自检 [1] silent pass 回归)
- `tests/test_teacher_misconceptions_api.py` — 7 项 (空数据 / 404 / 元数据 / quarantined 阈值 / 未知 misc_id 兜底 / 排序 / 500 兜底)
- pytest 1493 → **1541** (+48)

### 文档

- **MODIFY `CHANGELOG.md`** — §0.97.3 三段 (a/b/c) 完整记录 + 决策摘要
- **MODIFY `README.md`** — 状态徽章 v0.97.2 → v0.97.3 + backlog P2 ✅ + 版本脚注
- **MODIFY `ecos/__init__.py`** + **`web/frontend/package.json`** — 版本 0.97.2 → 0.97.3

## 关键设计决策

1. **多人 ECOS vs 单人 CogMirror**: tracker 按 student_id 实例化, 持久化表加 student_id 列; load 时按学生加载, 避免误用 (v0.97.3 文档化差异)
2. **reconcile 计数语义**: PredictionReconciler 模式 (后续仍错/重触发=success, 答对=failure), 与方案 5.1/5.6 验收方向一致 (vs 学习者视角 "答对=success" 会让 Laplace 方向反转)
3. **session 窗口**: in-memory response_history (maxlen=100), 进程重启 = 天然 session 边界 (CogMirror 5.7 方案: 跨会话语义不成立, 全量历史会重复计数)
4. **不挂 C 折扣**: v0.97.2 拍板 "C 维度等试点数据", v0.97.3 暴露 `confidence_for()` 但 BeliefEngine 不消费, 试点回来同批接 (避免"修一处即提交一处" 重复 v0.97 教训)
5. **持久化独立表**: A2 是 derived 状态, 走自己 `misconception_evidence` 表干净 (类似 calibration_log 模式), 不旁路 evidence_log
6. **失败兜底**: reconcile 失败 warning + 不污染 evidence_log + 不阻断主流程 (防御性自检 [1] 兼容)

## 黄金回归基线影响

**零 diff** (新行为全部走可选注入, no-misc 命中时 DB 不写, no-misconception 路径与 v0.97.2 完全一致)。

## 防御性自检 8 项

- [1] silent pass: misconception_reconcile 模块扫描 + belief.py 注入段扫描 + 防御性自检回归 1 项, 全绿
- [2] `__version__` 同步: 0.97.2 → 0.97.3 (ecos + frontend)
- [3] detect_with_hits 传 library_str: 信念路径无改动, 回归扫描通过
- [4] HTML class vs CSS: 新卡无新 class, 复用现有样式
- [5] DB 恢复 6 关键字段: 学生状态恢复路径无改动
- [6] DB 恢复走 apply_snapshot: 无状态修改, 不涉及
- [7] replay 脚本无字面量 skill_id: 无新 replay 脚本
- [8] 直接 state.X = value mutation: AST 扫描 53 个文件, 0 新增

## 开放问题

1. **C 维度折扣接法**: v0.97.3 暴露 `confidence_for(misc_id)`, v0.98 试点数据回来后, 需决策 "C 折扣 = f(Laplace 置信度)" 的具体函数形式 (当前是 `1.0 - LLM 单次 conf * 0.3`); 函数形如 `1.0 - laplace * 0.3` 是直觉起点, 需 v0.98 试点验证
2. **跨学生 generalize**: 当前 `confidence_for(misc_id)` 是 per-student (校准只对某学生该 misc 模式可靠); 是否需要 per-misc-per-skill 全局统计 (跨学生) 给教师"这个 misc 在全班通常多可靠" 的视图? v0.98 试点后决策
3. **quarantine 阈值先验值**: QUARANTINE_CONF_MAX=0.3 + QUARANTINE_MIN_EVIDENCE=3 (CogMirror 同款), 试点后看是否需调
4. **LLM 真实流量**: 当前 LLM critic 路径在测试外几乎不跑, 真实 misconception 命中数据要等 v0.98 试点; 现阶段 reconcile 在测试中可端到端跑通, 但生产路径还无数据

## 产出 commit 链 (按时间顺序)

- `55f67b5` v0.97.3 (a): misconception_reconcile 纯算法核心 + DB 持久化 — CogMirror A2 移植
- `353b5cc` v0.97.3 (b): 答题流注入 A2 reconcile — session 窗口, 不挂 BeliefState
- `a5564eb` v0.97.3 (c): web 接线 — 教师端 per-misconception 证据卡
- `2f1a938` v0.97.3 (d): docs 收口 — CHANGELOG + README backlog P2 打勾 + 状态徽章
- `d1e395a` v0.97.3 (a-fix): ON DELETE CASCADE — 修复 v0.64 test fixture FK 阻断 (silent try/except: pass 漏掉)

## 关联

- 上游: [discussions/2026-09-05-CogMirror迁移适用性分析-与built-unwired接线审计.md](2026-09-05-CogMirror迁移适用性分析-与built-unwired接线审计.md) §四 backlog 提案 #4
- CogMirror 模板: `cogmirror/misconception_tracker.py` + `tests/test_misconception_tracker.py`
- 下一项: v0.98 家长端 + 验证主线 (README P0 任务)
