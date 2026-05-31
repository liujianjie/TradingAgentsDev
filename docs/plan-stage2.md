# 阶段二实施计划：UniApp 可视化 Dashboard

> 版本：v1.0 | 创建：2026-05-31
> 关联规格：[spec-trading-platform.md](./spec-trading-platform.md)

---

## Overview

让用户用手机/微信/浏览器查看实时分析、历史报告、自选股管理。

**最终 vertical slice**：`npm run dev:h5` 启动后，浏览器访问 H5 页面，能看到自选股列表、点击触发分析、看到实时进度、查看历史报告。

技术栈：UniApp + Vue3 + Vite + uni-ui，与 C# 后端用 HTTP REST 通信。

---

## Architecture Decisions

| 决策 | 选择 | 理由 |
|------|------|------|
| 创建方式 | `npm create vite-uni`（命令行） | 不强制装 HBuilderX，全自动 |
| Vue 版本 | Vue 3 + Composition API | 现代 |
| UI 库 | uni-ui（官方组件） | 轻量，跨端兼容 |
| 状态管理 | Pinia | Vue3 官方 |
| 实时进度 | HTTP 轮询（每 5 秒） | 比 SignalR 简单，足够 |
| 数据持久化 | C# 端 EF Core SQLite（阶段二上） | 自选股、历史报告 |
| 优先目标 | H5（浏览器）跑通；微信小程序后置 | H5 验证最快 |

---

## 依赖图

```
T10 (UniApp 脚手架 + 跑通 H5)
   ↓
T11 (C# 后端：SQLite + 自选股 CRUD API)
   ↓                    ↓
T12 (前端：自选股管理) T13 (C# 后端：历史记录 API)
   ↓                    ↓
T14 (前端：触发分析 + 实时进度)
   ↓
T15 (前端：历史报告查看)
   ↓
T16 (前端：发布微信小程序版本)
```

---

## Task List

### Phase 1: 前端骨架

#### T10: UniApp 脚手架 + H5 跑通

**Description**: 用 vite + uni-app 模板创建项目，配置 uni-ui，跑起 H5 模式，浏览器看到默认页面。

**Acceptance**:
- [ ] `uniapp-frontend/` 项目可用 vite 创建
- [ ] `npm run dev:h5` 启动开发服务器
- [ ] 浏览器访问 `http://localhost:5173` 看到 hello world 页面
- [ ] 配置 axios 或 uni.request 封装，能 `GET http://localhost:8080/health` 显示后端状态

**Verification**:
```bash
cd uniapp-frontend
npm run dev:h5 &
curl -s http://localhost:5173 | grep -q "uni-app"
```

**Files**:
- `uniapp-frontend/package.json`、`vite.config.js`
- `uniapp-frontend/src/pages/index/index.vue`
- `uniapp-frontend/src/utils/api.js`

**Scope**: M

---

### Phase 2: 后端持久化

#### T11: C# EF Core SQLite + 自选股 API

**Description**: 引入 EF Core SQLite，建 `WatchlistItems` 表，提供 CRUD endpoint。把硬编码的 appsettings.Watchlist 迁移到数据库。

**Acceptance**:
- [ ] `data/tradingplatform.db` SQLite 文件自动创建
- [ ] `GET /api/watchlist` 返回列表
- [ ] `POST /api/watchlist` 添加 `{ ticker, name }`
- [ ] `DELETE /api/watchlist/{ticker}` 删除
- [ ] Hangfire 调度从数据库读取自选股列表（不再读 appsettings）

**Verification**:
```bash
curl -X POST http://localhost:8080/api/watchlist -d '{"ticker":"TSLA","name":"特斯拉"}'
curl http://localhost:8080/api/watchlist  # 应包含 TSLA
```

**Files**:
- `Data/AppDbContext.cs`、`Models/WatchlistItem.cs`、`Controllers/WatchlistController.cs`
- 修改 `Services/ScheduledAnalysisJob.cs` 从 DB 读

**Scope**: M

---

#### T13: C# 历史记录持久化 + API

**Description**: 每次分析完成（success or failed），结果写入 `AnalysisRecords` 表。提供查询 API。

**Acceptance**:
- [ ] `AnalysisRecords` 表存：jobId, ticker, date, status, decision, reportMarkdown, createdAt
- [ ] `AnalysisOrchestrator` 完成后写入 DB
- [ ] `GET /api/history?ticker=&from=&to=` 支持过滤

**Files**: `Models/AnalysisRecord.cs`、`Controllers/HistoryController.cs`、修改 `AnalysisOrchestrator.cs`

**Scope**: S

---

### Phase 3: 前端功能

#### T12: 前端自选股管理页

**Description**: 实现 `/pages/watchlist/index.vue`：列表展示、添加按钮、删除按钮。

**Acceptance**:
- [ ] 浏览器看到自选股列表（来自 C# API）
- [ ] 输入框 + 添加按钮，能新增
- [ ] 每行右滑/长按出现删除

**Files**: `pages/watchlist/index.vue`、`store/watchlist.js`

**Scope**: M

---

#### T14: 前端触发分析 + 实时进度

**Description**: 自选股列表点击「分析」按钮 → POST trigger → 跳转到分析详情页 → 每 5 秒轮询状态 → 完成后展示报告。

**Acceptance**:
- [ ] 点击触发后立即跳转
- [ ] 进度条 / 状态文字根据 status 更新（queued→running→completed/failed）
- [ ] 完成后展示 5 个 Agent 报告

**Files**: `pages/analysis/[jobId].vue`

**Scope**: M

---

#### T15: 前端历史报告

**Description**: `/pages/history/index.vue` 列表，按日期倒序，可按 ticker 过滤；点击进入详情。

**Acceptance**:
- [ ] 列表显示所有历史分析（来自 `/api/history`）
- [ ] 顶部下拉框筛选 ticker
- [ ] 点击进入复用 T14 的详情页

**Files**: `pages/history/index.vue`

**Scope**: S

---

### Phase 4: 多端发布

#### T16: 微信小程序模式

**Description**: `npm run dev:mp-weixin` 编译微信小程序版本，验证关键页面在小程序模拟器/真机能跑。

**Acceptance**:
- [ ] dist/dev/mp-weixin 目录下生成小程序代码
- [ ] 在微信开发者工具打开能预览（这步需要用户操作）

**Scope**: S（代码层面 0 工作量，UniApp 自动）

---

## Risks and Mitigations

| 风险 | 缓解 |
|------|------|
| UniApp 模板 npm 依赖装不上 | 配置 npm 国内镜像（淘宝/华为云） |
| H5 跨域（CORS） | C# 已配置 AllowAnyOrigin |
| 微信小程序域名白名单 | 阶段二只做 H5，小程序待用户配 |
| 长报告（>10KB）渲染卡顿 | 用 v-for + 分页，不一次全渲染 |

---

## 实施顺序

```
T10 (前端骨架) → T11 (后端 DB) → T12 (前端自选股)
              ↓
              T13 (后端历史 API) → T14 (触发+进度) → T15 (历史) → T16 (小程序)
```

每完成 2-3 个任务做一次中段 checkpoint 报告。

---

## 与阶段一的关系

阶段一已完成的代码不动。阶段二只在 C# 端添加表和 endpoint，不替换原有逻辑。

阶段一现有 `/api/analysis/trigger` 和 `/api/analysis/jobs/{id}` 完全保留，前端复用。
