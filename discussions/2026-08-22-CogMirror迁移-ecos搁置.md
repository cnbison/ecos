# 讨论存档: ecos 暂时搁置 — 迁移重启 CogMirror

- **日期**: 2026-08-22
- **主题**: ecos 搁置, 从 ECOS 迁移到 CogMirror 新项目, 抛开 K12
- **参与者**: Bisen (决策)
- **性质**: 搁置标记存档 (非新洞察)

## 背景

- ecos 最后活跃 commit: `0f9066c` (v0.96.9, 2026-08-19, 修复 /api/answer 不持久化幽灵学生 bug; 全量 pytest 1407 passed)
- 既定路线 (v0.95 方向审查): v0.97 家长端 + 验证主线 (小规模真实试点)
- Bisen 决策: **ecos 暂时搁置**, 迁移重启为独立新项目 **CogMirror**, 抛弃 K12 定位

## 核心结论

**CogMirror 定位** (与 ecos README 里 ECOS 的愿景承接但彻底换对象):
> 帮**成年自学者**在学 Python 的过程中, 随时看清自己**真实认知状态**的 AI 学习教练:
> - 哪里**真会** (真实掌握)
> - 哪里是**伪自信** (虚假掌握/过度自信)
> - **卡在哪个概念** (临界概念卡点定位)

**CogMirror 关键决策** (来源: CogMirror CLAUDE.md / PRD / MIGRATION.md):
- 从 ECOS **选择性迁移 + 收缩重启**, 版本号从 **v0.1.0** 重新开始, 不继承 v0.9x
- **MVP 无 LLM 依赖**: 静态题库 + 确定性判分 (可复现, 不引入 LLM)
- 现阶段只做"做题"一种交互, 只服务 Python 一个学科 (单一垂直)
- 明确不做: 双 Agent 互校 (ECOS H3 假设验证显著反向, p<0.0001) / POMDP·PBVI 重型策略 / Multi-Domain 通用内核·插件化·B端 / 游戏化激励·长期陪伴叙事 / 开放对话学习的认知信号提取 (PRD §8 未解难题, 需单独预研)
- 工程: Python ≥3.11, 依赖仅 numpy + scipy; 命名 user_id (非 student_id); 成人向合规 (可导出、可删除, 去监护人同意字段)
- 进度双线汇报: "工程完成了什么" vs "验证证实了什么" 永不合并; 测试者 ≠ 开发者

**CogMirror 当前状态** (2026-08-22):
- 独立目录 `/Users/loubicheng/project/CogMirror`, 独立 git 仓库, 当前 commit `5e0af22` (Phase 0: 从 ECOS 选择性迁移并搭建最小可运行链路)
- 工程线: 做题 (静态题库 + 确定性 partial credit 判分) → 5D 信念更新 (K/P/S/C/X) → 命令行认知地图 (5D / Bloom 六层 / 伪自信标注 / 临界概念标注 / 一句话建议), 81 项 pytest 全绿
- 验证线: 无 — 未经任何真实用户验证, 不声称任何"有效"结论
- **尚未配置 git remote** (无法 push)

## ecos 搁置状态

- 搁置标记点: `0f9066c` (v0.96.9) + git tag `ecos-paused-cogmirror-v0.96.9`
- 已标注: 本存档 + CHANGELOG 搁置条目 + README 当前状态横幅 + 下一步段顺延
- **恢复条件: 未定** (Bisen 后续决策)

## 开放问题

- ecos 恢复时机 / 是否永久冻结 — 未定
- CogMirror 是否需要建 git remote (如 GitHub) 以便推送 — 未定, 待 Bisen 决策
- ecos 遗留数据 (幽灵学生行清理、lbc002 轨迹缺失) 是否仍要处理 — 搁置, 随 ecos 一起冻结

## 产出

- ecos: 本存档 `discussions/2026-08-22-CogMirror迁移-ecos搁置.md`
- ecos: `CHANGELOG.md` 搁置条目
- ecos: `README.md` 当前状态横幅 + 下一步段顺延标注
- ecos: git tag `ecos-paused-cogmirror-v0.96.9`
- CogMirror 项目 (独立目录, 含 CLAUDE.md / PRD / ROADMAP / MIGRATION / GOVERNANCE / LESSONS-FROM-ECOS / cogmirror 包 / tests)
