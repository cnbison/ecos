# experiments/ — Phase 4+ 一次性实验代码

> **状态**：📋 占位（待 Phase 4.1 实施时填充）
> **关联**：[CLAUDE.md §实验代码约定](../../CLAUDE.md)、[research/90-mvp/](../research/90-mvp/README.md)

## 目录约定

实验代码组织：

```
experiments/
├── notebooks/              # Jupyter notebooks（单次实验运行）
├── scripts/                # ad-hoc 脚本（一次性验证）
├── analysis/               # 数据处理脚本（统计、可视化、报告生成）
├── configs/                # 配置文件（YAML）
└── output/                 # 实验输出（不 commit，仅本地）
```

## 命名约定

- **Notebook**：`YYYY-MM-DD-{phase}-m{milestone}-{description}.ipynb`
  - 例：`2026-07-15-phase4-m41-cta-belief-prototype.ipynb`
- **脚本**：`{milestone}_{action}.py`
  - 例：`m41_estimate_student_state.py`
- **配置**：`{milestone}_{variant}.yaml`
  - 例：`m41_math_mvp.yaml`

## 与项目级文档的同步

- 实验代码必须与文档关联：每个 notebook/脚本头部说明"对应 ROADMAP §M4.1"
- 实验结果文档化：跑完实验后，结果应记录在 `discussions/` 或 `research/90-mvp/` 下的报告中
- 不演进为可复用系统：实验代码不追求"代码质量"，追求"假设验证"

## 何时停止使用

- 实验完成后，代码归档（不删除，但不再修改）
- 不进入主分支的 develop/main 演进路径
- 新可复用代码放 `ecos/` Python 包

---

**创建日期**：2026-06-24
**维护者**：Bisen & Claude
