# 会话记录: v0.98.0 家长端 + Evidence/Event 注入答题流（恢复期 backlog P0）

> **日期**: 2026-09-06 · **参与者**: Bisen + Claude (规划 + 实施)
> **上游决策**: 方案一（b → a）Bisen 拍板; 四项设计决策 (per-dim 5 行 / judge_completed 不同批 / H1 文档落 discussions/ / 家长端不放校准卡)

## 核心结论

1. **接线审计实例 ③ 收口**: Evidence/Event Engine 经构造期注入接入答题流（kernel-mapping §1.4 预留点 `BeliefEngine(evidence_engine=)` 接通）。答题流每 submit 落 evidence_log per-dim 5 行（payload 含 dim 标记）+ event_log 2 行（response_submitted + observation）。CALIBRATION_LOG 有意不接（防污染 compute_h3_ece.py 的 ECE 数据源）。
2. **第二处 FK CASCADE 同族 bug 修掉（硬规则 #8 价值再验证）**: evidence_log 修完后同类扫描发现 event_log FK 同样无 CASCADE，同样阻断 v0.64 测试 fixture 清表。两表 + 迁移（rename-rebuild-copy 幂等升级）一并收口。
3. **家长端三件套落地**: ParentEngagementPlugin 1.1.0（pull 模式 UI 可消费复活，规则表建议不调 LLM）+ `/api/parent/*` 只读两端点（严禁 _get_or_create_student 防幽灵学生）+ `/parent/` React 第三入口四卡（无校准卡）。
4. **evolution 断层补线**: POMDPDiagnostic.to_dict 不含 evolution → LCAEngine.get_pomdp_evolution + Runtime 第 9 API diagnose_pomdp_evolution。
5. **顺带修**: EvidenceEngine.add count gate bug（默认恒真 → 每次 add 三表全扫）; 删 db.save_evidence 重复死路径; db.load_intervention_history dead code 接活（家长端干预卡）。

## 产出

- commit 链 7 个（b-a `0db3849` / b-b `890ed5b` / b-c `4ef7fcb` / a-a `384537d` / a-b / a-c / d `2c9ba18`），pytest 1544 → **1583**，golden 零 diff（每 commit 实跑），pre-push 全量通过
- NEW 文件: `web/api/parent.py`、`web/frontend/parent.html` + `src/parent/`、`tests/test_web_evidence_injection.py` (13)、`tests/test_pomdp_evolution_api.py` (4)、`tests/test_parent_api.py` (10)、`discussions/2026-09-06-v098-H1-Twin-数据收集方案.md`
- README backlog P0 a/b/c 打勾 + 试点执行单列新 P0 行; CHANGELOG 0.98.0; 版本双源 bump 0.98.0

## 开放问题

- evidence_log 保留窗口（现无 retention，试点后定）
- 家长建议规则阈值（SUSTAINED_ENGAGED_WINDOW=3 等）= 先验值，试点校准
- C 维度折扣接线（confidence_for → BeliefState）等试点数据（v0.97.2/v0.97.3 纪律延续）
- 试点执行（5-10 学生 lbc004+，4 周）待 Bisen 启动

## 教训

- FK 引入后的同类扫描必须覆盖**所有**派生状态表（本次 evidence_log 修完 event_log 才暴露）——DDL 常量提取 + 迁移应一次做全族
- 测试里直插 FK 表前记得先建父行（sqlite PRAGMA foreign_keys 在连接级生效）
