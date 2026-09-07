# ECOS Web UI 审阅报告

> **日期**: 2026-09-07  
> **审阅范围**: 教师端 `/teacher/`、学生端 `/`、家长端 `/parent/`  
> **方法**: 基于源码审阅（React 18 + Vite 6 + TypeScript + 手写 CSS），未做浏览器截图/视觉走查；结论以**结构、一致性、响应式、可访问性、信息层级**为主。  
> **对应版本**: v0.98.1  
> **用途**: 记录当前 UI 现状，作为后续优化改进任务的参考基线。

---

## 1. 总体印象

| 维度 | 现状 | 主要风险 |
|---|---|---|
| **信息架构** | 三端职责清晰：教师做诊断、学生做题、家长看概览 | 教师详情页卡片堆叠过平，缺乏主次；家长端四卡权重相同 |
| **视觉风格** | 白卡灰边、系统字体、emoji 图标，偏“默认管理后台” | 缺乏品牌感；三端设计 token 不统一 |
| **响应式** | 学生端有底部 Tab；教师/家长主要靠 `@media` 缩字体 | **移动端教师/家长顶部栏被整个隐藏**（bug） |
| **可访问性 (a11y)** | 较弱：色盲-only 状态、无 focus 环、表格行靠鼠标点击 | 不符合教育场景基本可访问性要求 |
| **代码组织** | 无共享组件库，card/badge/button 在多份 CSS 中重复定义 | 改一处样式需改多处，易漂移 |

**一句话判断**: 功能链路已通，但**视觉体系、响应式、可访问性、组件复用**四块有明显改进空间；建议先修 P0 bug 并抽组件库，再做体验升级。

---

## 2. 分端问题与机会

### 2.1 教师端

**信息层级**
- 详情页卡片过多且平级：5D θ → 5D 证据链 → POMDP 诊断 → 自评校准 → per-misconception 证据 → 干预历史，全部使用同一个 `.card`，教师难以一眼抓到重点。
- 证据链下钻可读性差：使用 `<details>/<summary>` 直接堆文本，缺少时间、分数、视觉分隔。
- 干预历史表列名写 `intervention_type ?? type ?? "—"`，暴露 API schema 不一致。
- 5D 雷达图 indicator 仅显示 `K/P/S/C/X` 字母，教师未必能一眼识别含义；缺少图例。

**布局与美观**
- 顶部副标题版本号陈旧：`v0.95.2 · 证据链视图 · POMDP 诊断`，与当前 `0.98.1` 不符。
- 班级列表 7 列，在移动端即使缩小 padding 也大概率需要横向滚动。
- 各模块空状态不统一，有的用 `<p className="muted">`，有的缺空状态。

### 2.2 学生端

**功能与交互**
- 底部 Tab 在桌面端也固定显示，像手机 App 嵌入桌面，浪费纵向空间。
- 答题页自评 chips 选中态仅靠 `ok` 变绿，不够明显；未选时像普通标签。
- `CodeEditor` 用于所有题目输入，名称和形态暗示“写代码”，对开放文字题不友好。
- Idle 20s 事件：用户一停顿就发送，可能高频上报。
- 登录页标题写死“ECOS Python 基础”，未来扩学科时会穿帮。

**布局与美观**
- 首页三卡信息架构好（我在哪 / 我的成长 / 下一步学什么），但“我的成长”进度条把 θ∈[-2.5,2.5] 映射为百分比，超出范围会被截断。
- 成长页轨迹表使用 `120px repeat(5, 1fr) 1fr`，移动端必然溢出。
- “我在哪”页 5D 每维独立色是亮点；但“学习特质 LearningDNA 待启用”卡片永远占位，建议折叠或移除。

### 2.3 家长端（问题最集中）

**功能与信息层级**
- 无 URL 路由：选择学生后刷新页面会丢失选择，无法分享给另一位家长查看同一页。
- 四卡平铺无主次：家长最关心“状态有没有变”和“我该做什么”，但四卡视觉权重相同。
- 建议列表样式别扭：把整段建议文字包进一个 pill badge，长文本换行后像胶囊被拉长。
- 5D 概览过于极简：只有掌握概率数字，缺少“这算高还是低”的通俗解读。
- 干预历史表日期只保留 `YYYY-MM-DD`，缺少时间；rationale 过长会撑开表格。

**布局与美观**
- “返回列表”按钮放在标题卡片内，位置随意，像临时按钮。
- 顶部副标题版本号陈旧：`v0.98.0`。
- 直接复用教师端 CSS，导致家长端看起来像教师端换了个标题。

---

## 3. 全局跨端问题

1. **响应式 bug**（高优先级）  
   `@media (max-width: 720px) { .topbar { display: none; } }` 会把教师/家长顶部品牌栏整个删除，移动端直接丢失“ECOS 教师端/家长端”上下文。

2. **无共享组件库**  
   `card / badge / button / error-box / empty-state` 在三份 CSS 里各写一遍，颜色、圆角、间距已出现漂移。

3. **可访问性不足**
   - 状态 badge 仅用颜色区分（红/绿/黄），无色盲辅助文本或图标。
   - `tr.clickable` 使用 `onClick` 导航，键盘无法聚焦或回车触发。
   - 多个按钮/图标缺少 `aria-label`。

4. **缺少 Error Boundary**  
   单个卡片抛错可能崩溃整个 SPA。

5. **版本号硬编码**  
   topbar subtitle 多处写死，未使用 `__APP_VERSION__`。

6. **图标全是 emoji**  
   在 Windows/Linux 字体 fallback 下显示可能不一致。

---

## 4. 优化方案

### 4.1 P0 · 建议先做（低投入、高回报）

| 项 | 改动点 | 收益 |
|---|---|---|
| 修复移动端 topbar 隐藏 bug | 教师/家长保留简化 topbar 或汉堡菜单，不直接 `display:none` | 移动端可用 |
| 统一版本号显示 | topbar subtitle 改用 `__APP_VERSION__` | 不再过期 |
| 提取共享组件库雏形 | `Card / Badge / Button / EmptyState / SectionHeader` 放到 `src/components/ui/` | 后续改样式一处生效 |
| 统一空状态 | 所有“暂无数据”使用同一个 `<EmptyState>` 组件 | 视觉一致 |
| 修复家长建议列表样式 | 建议用左色条/图标 + 文字，不用 pill badge | 可读性提升 |
| 增加键盘可访问性 | `tr.clickable` 改为 `role=button tabIndex=0` 或包裹 `<Link>`；按钮增加 focus 环 | 基础 a11y |
| 强化学生自评选中态 | 明确区分未选 / 选中 / 禁用三种状态 | 减少误提交 |

### 4.2 P1 · 体验升级（中等投入）

| 项 | 改动点 | 收益 |
|---|---|---|
| 教师详情页重排 | 首屏只保留状态横幅 + 5D 雷达 + 证据链；POMDP/校准/misconception/干预放折叠区或第二屏 | 信息有主次 |
| 班级列表移动端卡片化 | `<720px` 时把表格换成学生卡片列表 | 不再横向滚动 |
| 家长端 URL 状态 | 选择学生后写入 query param `/parent/?student=lbc005` | 可刷新、可分享 |
| 引入图标库（推荐 Lucide） | 替换 emoji，统一风格 | 跨平台一致、更专业 |
| 学生端桌面导航 | 宽屏用左侧/顶部导航，底部 Tab 仅保留在移动端 | 桌面不浪费空间 |
| 增加 Error Boundary | 每端顶层 + 可选卡片级 fallback | 单点故障不崩整页 |
| 答题页输入控件按需切换 | 程序题用 CodeEditor，开放题用普通 textarea | 降低学生认知负担 |

### 4.3 P2 · 品牌化/大改造（按需）

| 项 | 说明 |
|---|---|
| 设计系统升级 | 定义 spacing scale（4/8/12/16/24）、color semantic、typography scale，统一三端 |
| 深色模式 | 利用 CSS variables 切换，适合长时间看屏 |
| 微交互动效 | 卡片入场、数字变化、状态切换过渡 |
| 教师端证据链时间轴 | 把下钻列表改成可视化时间轴 |
| 家长端 5D 通俗化解读 | 不显示 θ 值，显示“在这类题上表现如何” |

---

## 5. 建议的开工顺序

1. **P0 + 共享组件库**：先修 bug、统一版本、抽组件库 —— 这是所有后续改动的地基。
2. **P1 教师详情页重排 + 家长端 URL 状态**：立竿见影提升两端专业感。
3. **P1 图标库 + 学生端桌面导航**：整体质感提升。
4. **P2 设计系统**：在前三步稳定后再做全局换肤。

---

## 6. 相关文件清单

- `web/frontend/src/index.css` — 教师端/家长端基础样式
- `web/frontend/src/App.tsx` — 教师端路由
- `web/frontend/src/pages/RosterPage.tsx`
- `web/frontend/src/pages/StudentDetailPage.tsx`
- `web/frontend/src/student/index.css` — 学生端样式
- `web/frontend/src/student/App.tsx`
- `web/frontend/src/student/pages/HomePage.tsx`
- `web/frontend/src/student/pages/AnswerPage.tsx`
- `web/frontend/src/student/pages/WherePage.tsx`
- `web/frontend/src/student/pages/GrowthPage.tsx`
- `web/frontend/src/parent/App.tsx`
- `web/frontend/src/parent/pages/ParentHomePage.tsx`
- `web/frontend/src/parent/components/Cards.tsx`
- `web/frontend/src/components/EChart.tsx`

---

## 7. 审阅说明

- 本报告基于源码静态审阅，若某些问题在实机浏览器中表现不同，以实机效果为准。
- 优化方案未涉及后端 API 改动；若实施 P1/P2 中需要 API 补充字段，应另起任务评估。
