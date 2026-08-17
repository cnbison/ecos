# ECOS 项目 Makefile
# v0.55.0-e: pytest 套件自动化入口

.PHONY: help test check lint clean ci frontend frontend-dev frontend-build

help:
	@echo "ECOS 开发命令:"
	@echo "  make test          - 跑 pytest 测试套件"
	@echo "  make check         - 跑 8 项防御性自检 + 前端段 + pytest"
	@echo "  make frontend      - 前端最小集 (tsc + eslint + vitest)"
	@echo "  make frontend-build- 前端 build (vite build → dist, Flask 托管)"
	@echo "  make frontend-dev  - 前端 dev server (Vite 5174, proxy /api → Flask 5173)"
	@echo "  make clean         - 清理 __pycache__ / .pytest_cache"

test:
	python -m pytest tests/ -v

check:
	bash scripts/check_defensive.sh

frontend:
	cd web/frontend && npm run typecheck && npm run lint && npm test

frontend-build:
	cd web/frontend && npm run build

frontend-dev:
	cd web/frontend && npm run dev

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache

ci: check
