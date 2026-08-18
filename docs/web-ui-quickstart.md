# ECOS Web UI 启动与访问指南

> **适用范围**: v0.95/v0.96 起的 React SPA 形态 — 前端 Vite build → `web/frontend/dist/` → Flask 托管（学生端 + 教师端双页）。
> 本文是 README §启动 Web UI 的详细版；路由实现见 `web/api/app.py`。

## 0. 前置条件

| 依赖 | 要求 | 验证 |
|---|---|---|
| Python | 3.11+ | `python3 --version` |
| Node.js | 18+（Vite 6 要求 18+/20+） | `node --version` |
| LLM API key | 答题评判走 LLM（`.env` 里 `MINIMAX_API_KEY` 或 `MOONSHOT_API_KEY`） | `cp .env.example .env` 后填入 |

```bash
# Python 依赖（虚拟环境）
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 前端依赖
cd web/frontend && npm install && cd ..
```

> 缺 LLM key 时 `/api/judge` 会失败并返回 422（v0.56.1 起不降级、不写启发式兜底）。

## 1. 启动后端（Flask，端口 5173）

```bash
cd <ecos 仓库根目录>
ECOS_DUAL_AGENT_ENABLED=1 python -m web.api.app
```

- debug 模式，改代码自动重载
- 确认 dual_agent 已启用：启动日志出现 `DualAgentOrchestrator 初始化完成 (DUAL_AGENT_ENABLED=True, ...)`
- `ECOS_DUAL_AGENT_ENABLED` 可省略（默认关）；省略时走老路径，dual_agent 与 v0.69.0 confidence 指标不启用

## 2. 启动前端（两种形态，二选一）

### 形态 A — 生产/演示（Flask 托管 build 产物）

`web/frontend/dist/` 已 gitignore，**首次必须构建一次**；构建后 Flask 自动优先服务 dist。

```bash
cd web/frontend && npm run build && cd ..
```

### 形态 B — 开发（Vite dev server，热更新）

后端照常跑在 5173，另开一个终端：

```bash
cd web/frontend && npm run dev
```

Vite 5174（proxy `/api` → Flask 5173），改前端代码即时生效，无需重新 build。

## 3. 访问入口

### 形态 A（Flask 托管）

| 入口 | 地址 | 说明 |
|---|---|---|
| 学生端 | `http://localhost:5173/` | v0.96 React SPA；dist 缺失时 fallback 旧版 `web/student/` |
| 教师端 | `http://localhost:5173/teacher/` | v0.95 React SPA；dist 缺失时 fallback 旧版 `web/teacher/` |

### 形态 B（Vite dev）

| 入口 | 地址 |
|---|---|
| 学生端 | `http://localhost:5174/student.html` |
| 教师端 | `http://localhost:5174/` |

## 4. Makefile 快捷方式

| 命令 | 等价操作 |
|---|---|
| `make frontend-dev` | `cd web/frontend && npm run dev`（Vite 5174）|
| `make frontend-build` | `cd web/frontend && npm run build` → dist |
| `make frontend` | 前端静态检查（tsc + eslint + vitest）|
| `make test` / `make check` | pytest / 防御性自检（`bash scripts/check_defensive.sh`）|

## 5. 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| 访问 `/` 是旧版学生页面（vanilla JS） | dist 未构建或缺失 — 跑 `make frontend-build` 后刷新（Flask 无 dist 时 fallback 旧页面）|
| `/api/judge` 返回 422 | LLM key 缺失/失效 — 检查 `.env`；评判失败不污染任何 state，可刷新重试 |
| 学生端显示"题目加载失败" | `/api/state` 冷启动慢 — 等 1-2s 刷新；或 Flask 进程需重启 |
| 想清掉浏览器记住的学生 ID | 设置页「退出登录」或清除 localStorage `ecos_last_student_id` |
| 前端改动不生效（dev 模式） | Vite 5174 与 Flask 5173 需同时运行；确认访问的是 5174 而非 5173 |

## 6. 目录/产物说明

- `web/frontend/` — React 18 + Vite 6 + TS 前端（多页 build：`index.html` 教师端 + `student.html` 学生端）
- `web/frontend/dist/` — build 产物（gitignore，Flask 托管源；`index.html` / `student.html` + `assets/`）
- `web/api/app.py` — Flask 路由：`/api/*` + 静态托管（`/` `/student/` `/teacher/`，均 dist 优先 + legacy fallback）
- `web/student/` / `web/teacher/` — 旧版 vanilla JS 页面（迁移期兼容，dist 缺失时兜底）
