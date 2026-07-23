"""ECOS pytest 测试套件 (v0.55.0+).

CLAUDE.md §防御性自检规范 v0.47.6+ 自动化:
  - 5 项 grep 自检清单 (silent failure / 版本号 / git diff / CSS / DB)
  - 3 条 CI gate (虚标 / library_str / partial credit)

组织:
  - conftest.py: 共享 fixtures + sys.path 配置
  - test_defensive.py: 5 项防御性自检
  - test_partial_credit.py: partial credit + MIRT 回归保护 (v0.55.0-b)
  - test_dual_layer.py: 5D 双层架构验证 (v0.55.0-b)
  - test_cross_subject.py: 跨学科迁移验证 (v0.55.0-c)
"""
