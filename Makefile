# ECOS 项目 Makefile
# v0.55.0-e: pytest 套件自动化入口

.PHONY: help test check lint clean ci

help:
	@echo "ECOS v0.55.0+ 开发命令:"
	@echo "  make test  - 跑 pytest 测试套件 (22/22)"
	@echo "  make check - 跑 5 项防御性自检 + pytest"
	@echo "  make lint  - 跑代码风格检查 (暂未启用, v0.56.0+ 计划)"
	@echo "  make clean - 清理 __pycache__ / .pytest_cache"
	@echo "  make ci    - CI 入口 (同 check)"

test:
	python -m pytest tests/ -v

check:
	bash scripts/check_defensive.sh

lint:
	@echo "TODO v0.56.0+: ruff + black + mypy"

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache

ci: check
