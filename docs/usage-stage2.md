# 阶段二日常使用指南（H5 + 微信小程序）

## 启动三个服务

需要开三个终端：

**终端 1（Python 后端）**：
```powershell
cd F:\AIProject\TradingAgents
uvicorn api.main:app --port 8000
```

**终端 2（C# 后端）**：
```powershell
cd F:\AIProject\TradingAgents\TradingPlatform\TradingPlatform.Api
dotnet run
```

**终端 3（前端 H5）**：
```powershell
cd F:\AIProject\TradingAgents\uniapp-frontend
npm run dev:h5
```

## 访问地址

| 入口 | URL | 用途 |
|------|-----|------|
| **H5 Dashboard** | http://localhost:5173 | 浏览器访问，主入口 |
| C# Swagger | http://localhost:8080/swagger | 后端 API 调试 |
| Python Swagger | http://localhost:8000/docs | Python API 调试 |
| Hangfire | http://localhost:8080/hangfire | 定时任务面板 |

## H5 模式：4 个 tab 页

打开 http://localhost:5173 后能看到：

- **首页**：后端在线状态、快捷入口
- **自选**：自选股 CRUD，每行有「分析」「删除」按钮
- **历史**：所有分析记录，支持按 ticker 筛选
- 顶部跳转：点击「分析」进入 `/pages/analysis` 实时显示进度，每 5 秒轮询

## 微信小程序模式

**编译**：

```powershell
cd F:\AIProject\TradingAgents\uniapp-frontend
npm run build:mp-weixin
```

产物在 `dist/build/mp-weixin/`。

**预览（这一步需要手动操作）**：

1. 下载并安装 [微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)
2. 打开 → 导入项目 → 项目目录选 `F:\AIProject\TradingAgents\uniapp-frontend\dist\build\mp-weixin`
3. AppID 填测试号或自己的（可以暂用「测试号」模式）
4. 点「编译」预览

注意：小程序模式下 baseURL 是 `http://localhost:8080`，确保 C# 服务在跑。
真机调试时小程序需要 HTTPS（这是阶段三/上线时再处理）。

## 常用操作

### 添加自选股

打开「自选」tab → 输入框填股票代码（如 `MSFT`、`600519.SS`、`0700.HK`）→ 添加。

### 触发一次分析

「自选」页 → 找到目标股票 → 点「分析」按钮 → 自动跳转分析详情页 → 5 秒轮询直到完成。

### 查看历史

「历史」tab → 列表显示所有任务 → 点击进入详情。

## 数据存储

- **自选股 + 分析记录**：`data/tradingplatform.db` （SQLite，C# EF Core 自动创建）
- **API Keys**：`config/apikeys.local.json` （已加 .gitignore）
- **Hangfire 任务**：In-Memory，C# 重启后清空

## 已知限制

- 阶段二仍依赖 Yahoo Finance 数据，受其限流影响
- 小程序真机预览需要域名白名单 + HTTPS（阶段三处理）
- 没有用户登录，单机单用户场景
