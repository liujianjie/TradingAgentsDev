# 阶段一日常使用指南

## 概览

阶段一已完成。日常使用流程：

1. 配置好 LLM API Key 和 Server酱 SendKey
2. 启动两个服务：Python FastAPI（8000）+ C# ASP.NET Core（8080）
3. 把电脑保持开机
4. 工作日 08:30 / 15:10 自动触发分析，微信收到推送

## 前置：一次性配置

完成下面三件事各一次（之后无需重复）：

- [ ] 装好 Python 依赖：参见 [`setup-python-env.md`](./setup-python-env.md)
- [ ] 配置 LLM API Key（环境变量）：参见 [`setup-llm-api-key.md`](./setup-llm-api-key.md)
- [ ] 配置 Server酱 SendKey（环境变量）：参见 [`setup-serverchan.md`](./setup-serverchan.md)

验证：

```powershell
echo $env:DEEPSEEK_API_KEY        # 或你选的 LLM 提供商
echo $env:SERVERCHAN_SEND_KEY     # 应输出 SCT...
```

## 自选股配置

编辑 `TradingPlatform/TradingPlatform.Api/appsettings.json` 中的 `Watchlist`：

```json
"Watchlist": [
  { "Ticker": "AAPL", "Name": "苹果" },
  { "Ticker": "TSLA", "Name": "特斯拉" },
  { "Ticker": "600519.SS", "Name": "贵州茅台" },
  { "Ticker": "0700.HK", "Name": "腾讯" }
]
```

**Ticker 后缀速查**：

| 市场 | 后缀 | 示例 |
|------|------|------|
| 美股 | 无 | `AAPL` |
| A股上交所 | `.SS` | `600519.SS` |
| A股深交所 | `.SZ` | `000001.SZ` |
| 港股 | `.HK` | `0700.HK` |
| 日股 | `.T` | `7203.T` |
| 加密货币 | `-USD` | `BTC-USD` |

注意：自选股越多，每天消耗的 LLM token 越多。Server酱免费版每天最多 5 条推送，每只股票每天 2 条（盘前+盘后），所以免费版最多 2 只股票。

## 启动服务

### 方式一：手动开两个终端

**终端 1（Python）**：
```powershell
cd F:\AIProject\TradingAgents
uvicorn api.main:app --port 28100
```

**终端 2（C#）**：
```powershell
cd F:\AIProject\TradingAgents\TradingPlatform\TradingPlatform.Api
dotnet run
```

### 方式二：用 .bat 启动器（待实现，参考全局规范）

可以后续加一个 `start-stage1.bat` 一键启动，目前先用方式一。

## 验证启动成功

启动后访问：

- http://localhost:28100/health  → Python API 存活
- http://localhost:28100/docs    → Python API Swagger
- http://localhost:8080/health  → C# API 存活
- http://localhost:8080/swagger → C# API Swagger
- http://localhost:8080/hangfire → Hangfire 调度面板（看定时任务列表）

## 手动触发一次分析（不等定时）

```bash
curl -X POST http://localhost:8080/api/analysis/trigger \
  -H "Content-Type: application/json" \
  -d "{\"ticker\":\"AAPL\"}"
```

返回 `jobId` 后立即响应。后台执行约 5-15 分钟，完成后微信收到报告。

查询当前 Job 状态：

```bash
curl http://localhost:8080/api/analysis/jobs/{jobId}
```

## 临时改时间快速验证

想立刻测试定时触发，把 `appsettings.json` 中 cron 改成下一分钟：

```json
"Schedule": {
  "PreMarketCron": "55 14 * * *"   ← 假设现在 14:54，改成 14:55
}
```

重启 C# 服务，等到那一分钟，Hangfire 自动触发，微信会收到消息。验证完后改回原值。

## 常见卡点

| 现象 | 原因 | 解决 |
|------|------|------|
| 推送收不到 | SendKey 没生效 | 重启终端让环境变量加载 |
| 微信推送有"分析失败"消息 | LLM Key 没配 | 配置 LLM Key |
| 定时不触发 | 电脑休眠了 | 关闭睡眠模式或保持插电 |
| C# 启动报端口占用 | 之前没关干净 | `taskkill /F /IM TradingPlatform.Api.exe` |
| Python 报 import 错误 | 依赖没装 | `pip install -r api/requirements-api.txt -i 清华源` |

## API 端点速查

C# 端（端口 8080）：

| 端点 | 用途 |
|------|------|
| `GET  /health` | 健康检查 |
| `GET  /swagger` | API 文档 |
| `GET  /hangfire` | 调度面板 |
| `POST /api/push/test` | 发测试微信消息 |
| `POST /api/analysis/trigger` | 手动触发分析 |
| `GET  /api/analysis/jobs/{jobId}` | 查询 Job 状态 |

Python 端（端口 8000）：

| 端点 | 用途 |
|------|------|
| `GET  /health` | 健康检查 |
| `POST /api/v1/analyze` | 触发分析 |
| `GET  /api/v1/jobs/{jobId}` | 查询 Job |
| `GET  /api/v1/jobs` | 列出所有 Job |

## 阶段一已知限制

- **任务持久化**：Hangfire 用 in-memory，C# 重启后任务历史丢失（阶段二上 SQLite 解决）
- **自选股管理**：只能改 appsettings.json + 重启（阶段二做 UniApp 界面）
- **进度查询**：客户端只能轮询，无 WebSocket 推送（阶段二上 SignalR）
- **多用户**：单用户单 SendKey，无登录鉴权（产品定位是个人工具，无需多用户）
