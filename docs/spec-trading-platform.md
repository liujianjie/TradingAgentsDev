# Spec: TradingAgents 三阶段平台扩展

> 版本：v1.0 | 创建：2026-05-31

---

## Objective

在现有 TradingAgents Python 多智能体分析框架基础上，分三个阶段扩展为完整的全球股票智能投研平台：

| 阶段 | 目标 | 核心价值 |
|------|------|----------|
| **阶段一** | 微信推送 | 定时分析指定股票，结果主动推送到微信，无需主动查询 |
| **阶段二** | UniApp 可视化 | 通过手机/小程序实时查看分析过程、历史报告、Agent 推理过程 |
| **阶段三** | IBKR 自动交易 | 基于 AI 决策，通过 Interactive Brokers API 自动下单 |

**用户**：个人投资者，关注全球市场（美股、A股、港股、日股、欧股等），偏好 C# 技术栈，不熟悉 Python。

---

## 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                     UniApp 前端                          │
│    微信小程序 / H5 / App (Vue3 + UniApp)                 │
│    实时进度、分析报告、历史记录、股票管理                  │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP REST / WebSocket
┌──────────────────────────▼──────────────────────────────┐
│              C# ASP.NET Core 后端 (8080)                 │
│  • 任务调度 (Hangfire)      • 推送通知 (Server酱)         │
│  • 结果持久化 (SQLite)      • WebSocket 实时流            │
│  • 用户股票列表管理          • IBKR 交易接口 (阶段三)      │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP REST (内网)
┌──────────────────────────▼──────────────────────────────┐
│              Python FastAPI 分析服务 (8000)              │
│  • TradingAgents 核心引擎 (原有代码不改动)                │
│  • POST /analyze 触发分析                                 │
│  • GET  /status/{job_id} 查询进度                        │
│  • SSE  /stream/{job_id} 实时推流                        │
└─────────────────────────────────────────────────────────┘
```

### 为什么这样分层

- **Python 层**：TradingAgents 核心（LangChain + LangGraph）不可直接用 C# 替换，保持原样，仅在外层封装 FastAPI 接口
- **C# 层**：用户偏好 C#；承担调度、持久化、推送、鉴权等业务逻辑
- **UniApp 层**：一套代码同时输出微信小程序 + H5 + App，与 C# 后端通信

---

## Tech Stack

### Python 分析服务
| 组件 | 选型 | 说明 |
|------|------|------|
| 核心框架 | TradingAgents (现有) | 不改动 |
| API 层 | FastAPI 0.115+ | 最小侵入，加在 main.py 同级 |
| 异步任务 | asyncio + subprocess | 避免阻塞 |
| 依赖管理 | uv (现有) | 已有 uv.lock |

### C# 后端服务
| 组件 | 选型 | 说明 |
|------|------|------|
| 框架 | ASP.NET Core 8 | LTS，稳定 |
| 调度 | Hangfire | 定时任务，有 Web UI |
| 数据库 | SQLite + EF Core | 单机部署，零维护 |
| 实时通信 | SignalR | WebSocket 封装，UniApp 有对应库 |
| HTTP 客户端 | HttpClient (内置) | 调用 Python FastAPI |
| 推送 | Server酱 HTTP API | 免费，绑定微信 |
| 交易 (阶段三) | IBKR TWS API (C# 官方库) | Interactive Brokers |

### UniApp 前端
| 组件 | 选型 | 说明 |
|------|------|------|
| 框架 | UniApp + Vue3 | HBuilderX 开发，一键发布多端 |
| UI 库 | uni-ui | 官方组件库 |
| 图表 | uCharts | UniApp 专用图表库 |
| 状态 | Pinia | Vue3 官方状态管理 |
| HTTP | uni.request | UniApp 内置 |
| WebSocket | uni.connectSocket | UniApp 内置 |

---

## 项目结构

```
F:/AIProject/TradingAgents/          ← 现有 Python 项目根目录
├── tradingagents/                   ← 现有核心（不改动）
├── cli/                             ← 现有 CLI（不改动）
├── api/                             ← 新增：Python FastAPI 服务
│   ├── main.py                      ← FastAPI 入口
│   ├── analyzer.py                  ← 调用 TradingAgentsGraph 的包装器
│   ├── models.py                    ← Pydantic 请求/响应模型
│   └── requirements-api.txt         ← api 额外依赖
│
├── TradingPlatform/                 ← 新增：C# 解决方案
│   ├── TradingPlatform.sln
│   ├── TradingPlatform.Api/         ← ASP.NET Core Web API
│   │   ├── Controllers/
│   │   │   ├── AnalysisController.cs
│   │   │   ├── StockListController.cs
│   │   │   └── TradeController.cs   ← 阶段三
│   │   ├── Services/
│   │   │   ├── AnalysisService.cs   ← 调用 Python API
│   │   │   ├── PushService.cs       ← Server酱推送
│   │   │   ├── SchedulerService.cs  ← Hangfire 任务定义
│   │   │   └── IbkrService.cs       ← 阶段三
│   │   ├── Hubs/
│   │   │   └── AnalysisHub.cs       ← SignalR Hub
│   │   ├── Data/
│   │   │   ├── AppDbContext.cs
│   │   │   └── Migrations/
│   │   ├── Models/
│   │   │   ├── AnalysisJob.cs
│   │   │   ├── StockWatch.cs
│   │   │   └── TradeRecord.cs
│   │   ├── appsettings.json
│   │   └── Program.cs
│   └── TradingPlatform.Tests/
│
├── uniapp-frontend/                 ← 新增：UniApp 项目
│   ├── pages/
│   │   ├── index/index.vue          ← 首页：今日推荐
│   │   ├── analysis/                ← 分析进度+报告
│   │   ├── history/                 ← 历史记录
│   │   ├── watchlist/               ← 自选股管理
│   │   └── settings/                ← 推送时间、LLM 配置
│   ├── store/
│   ├── utils/
│   │   ├── api.js                   ← HTTP 请求封装
│   │   └── ws.js                    ← SignalR/WebSocket 封装
│   ├── manifest.json
│   └── pages.json
│
└── docs/
    ├── spec-trading-platform.md    ← 本文件
    ├── setup-serverchan.md          ← Server酱注册和配置指南
    ├── setup-ibkr.md                ← IBKR 开户和 Paper Trading 指南
    └── api-reference.md             ← 接口文档
```

---

## 阶段一：微信推送

### 功能范围

1. 用户在配置文件中维护"自选股列表"（股票代码 + 名称）
2. 定时任务（默认：工作日 09:00 盘前 + 15:30 盘后）自动触发分析
3. 分析完成后，格式化报告推送到微信（通过 Server酱）
4. 支持手动触发（HTTP 接口）

### 推送消息格式

```
【TradingAgents 分析报告】

📊 $AAPL (苹果) | 2026-05-31 09:00

决策：🟢 BUY
信心：★★★★☆ (4/5)
目标价：$225.00 | 止损：$195.00
时间维度：3-6 个月

━━ 技术面 ━━
RSI(14): 58.3 | 中性偏多
MACD: 金叉形成，趋势向上
布林带：价格在中轨上方运行

━━ 情感面 ━━
Reddit/StockTwits：看涨情绪 7.2/10
近期新闻：AI 产品发布预期升温

━━ 基本面 ━━
PE: 28.5 | EPS 成长 12%
现金流充裕，回购计划推进

━━ 风险提示 ━━
美联储政策不确定性 | 宏观压力

[查看完整报告] [查看所有股票]
```

### API 设计（Python FastAPI）

```
POST /api/v1/analyze
  Body: { "ticker": "AAPL", "date": "2026-05-31", "job_id": "uuid" }
  返回: { "job_id": "uuid", "status": "queued" }

GET  /api/v1/jobs/{job_id}
  返回: { "status": "running|completed|failed", "progress": 0-100, "result": {...} }

GET  /api/v1/jobs/{job_id}/stream   (Server-Sent Events)
  流式返回: { "agent": "market_analyst", "message": "...", "timestamp": "..." }
```

### API 设计（C# 后端）

```
POST /api/analysis/trigger          ← 手动触发单股分析
  Body: { "ticker": "AAPL" }

GET  /api/analysis/jobs             ← 获取历史任务列表
GET  /api/analysis/jobs/{id}        ← 获取单个任务详情
GET  /api/stocklist                 ← 获取自选股列表
POST /api/stocklist                 ← 添加自选股
DELETE /api/stocklist/{ticker}      ← 删除自选股
```

### 成功标准

- [ ] `dotnet run` 启动 C# 服务，Hangfire 控制台可见 http://localhost:8080/hangfire
- [ ] 手动 POST `/api/analysis/trigger` 后，5-30 分钟内微信收到格式化消息
- [ ] 工作日 09:00 自动触发，15:30 自动触发
- [ ] 任务失败时推送失败通知（含错误摘要）

---

## 阶段二：UniApp 可视化

### 功能范围

1. **首页**：今日自选股分析结果卡片，信号颜色高亮
2. **分析详情页**：
   - 实时进度（每个 Agent 状态）
   - 各分析员完整报告
   - 最终决策展示（交易信号 + 目标价 + 止损）
3. **历史记录**：按日期/股票筛选，支持搜索
4. **自选股管理**：增删改查，支持全球市场代码（加后缀：.HK/.SS/.SZ）
5. **设置**：推送时间配置、LLM 模型选择

### 实时进度 WebSocket 数据格式

```json
{
  "job_id": "uuid",
  "event": "agent_start|agent_done|analysis_complete|error",
  "agent": "market_analyst",
  "message": "正在分析技术指标...",
  "data": { "report": "..." },
  "timestamp": "2026-05-31T09:15:30Z"
}
```

### 成功标准

- [ ] HBuilderX 一键发布为 H5，浏览器访问 `http://localhost:8080/h5`
- [ ] 发布为微信小程序，手机可扫码预览
- [ ] 分析进度实时更新（每个 Agent 完成后 < 2 秒更新到 UI）
- [ ] 历史报告支持按股票/日期筛选

---

## 阶段三：IBKR 自动交易（架构预留）

### 功能范围（待实现）

1. Portfolio Manager 输出 BUY 信号且信心 >= 4/5 时，生成待执行订单
2. 用户在 UniApp 确认后执行，或设置自动确认阈值
3. 支持 Paper Trading（模拟盘）和 Live Trading（实盘）切换
4. 订单历史和持仓展示

### 架构预留

- `IbkrService.cs` 骨架已创建，预留接口
- `TradeRecord` 数据表结构已在 Phase 1 迁移中建立
- IBKR TWS API 需要本地运行 TWS 或 IB Gateway（参见 `docs/setup-ibkr.md`）

### 风险声明

> **重要**：自动交易涉及真实资金损失风险。阶段三代码仅在 Paper Trading 账户充分测试后方可接入实盘。本项目 AI 分析结果不构成投资建议。

---

## 全球市场支持

TradingAgents 通过 Yahoo Finance 获取数据，不同市场使用不同 Ticker 后缀：

| 市场 | 示例 Ticker | 说明 |
|------|-------------|------|
| 美股 | `AAPL`, `TSLA` | 无后缀 |
| A股上交所 | `600519.SS` | 茅台 |
| A股深交所 | `000001.SZ` | 平安银行 |
| 港股 | `0700.HK` | 腾讯 |
| 日股 | `7203.T` | 丰田 |
| 英股 | `SHEL.L` | 壳牌 |
| 德股 | `BMW.DE` | 宝马 |
| 加密货币 | `BTC-USD` | 比特币 |

A股分析限制：社交情感（Reddit/StockTwits）主要覆盖英文内容，A股情感分析准确度低于美股。

---

## 代码风格

### C# 示例

```csharp
// ASP.NET Core Controller 风格
[ApiController]
[Route("api/[controller]")]
public class AnalysisController : ControllerBase
{
    private readonly IAnalysisService _analysisService;

    public AnalysisController(IAnalysisService analysisService)
        => _analysisService = analysisService;

    [HttpPost("trigger")]
    public async Task<IActionResult> Trigger([FromBody] TriggerRequest request)
    {
        var jobId = await _analysisService.QueueAnalysisAsync(request.Ticker);
        return Ok(new { jobId });
    }
}
```

### Vue3 UniApp 示例

```vue
<script setup>
import { ref, onMounted } from 'vue'
import { useAnalysisStore } from '@/store/analysis'

const store = useAnalysisStore()
const loading = ref(false)

onMounted(() => store.fetchJobs())
</script>
```

### 约定
- C#：PascalCase 类/方法名，camelCase 参数，`async/await` 全面使用
- Vue：Composition API（`<script setup>`），不使用 Options API
- API 响应统一格式：`{ "success": bool, "data": any, "error": string? }`

---

## 命令速查

```bash
# Python 分析服务
cd F:/AIProject/TradingAgents
uvicorn api.main:app --port 28100 --reload

# C# 后端（Windows）
cd TradingPlatform/TradingPlatform.Api
dotnet run

# UniApp 前端（HBuilderX 运行，或命令行）
cd uniapp-frontend
npm run dev:h5           # H5 模式
npm run dev:mp-weixin    # 微信小程序模式
```

---

## Boundaries

**Always（必须做）：**
- Python 核心代码（`tradingagents/`）只读，不改动
- API Key 通过环境变量 / `.env` 注入，不硬编码
- 阶段三任何真实交易代码，必须先在 Paper Trading 验证
- Server酱 SendKey 存在 `appsettings.json` 的 UserSecrets 或环境变量，不提交 Git

**Ask First（先询问）：**
- 改变推送消息格式（用户可能已适应）
- 修改定时任务触发时间
- 引入新的 NuGet / npm 包

**Never（禁止）：**
- 将 IBKR 实盘 API 连接暴露到公网
- 提交 `.env`、`appsettings.local.json`、任何含 API Key 的文件
- 在 Paper Trading 未验证的情况下启用实盘交易

---

## Open Questions

以下问题待用户确认后实施：

1. **部署环境**：是否始终在本机运行（Windows 家用机），还是需要部署到服务器/NAS？影响网络访问和定时任务稳定性。
2. **Server酱推送频率**：免费版每天 5 条，是否够用？（每只股票盘前+盘后=2条，5只股票=10条/天，需要付费版）
3. **A股交易时间**：A股盘前分析触发时间建议 08:30（开盘前 1 小时），盘后建议 15:10（收盘后 10 分钟），是否合适？
4. **LLM 费用**：每次完整分析消耗约 50k-200k tokens（取决于模型），全球多市场每日分析成本需评估。

---

## Success Criteria（全局）

| 阶段 | 验收标准 |
|------|----------|
| 阶段一 | 工作日自动推送，手机微信收到格式化报告，内容包含明确的买/卖/持信号 |
| 阶段二 | UniApp 小程序可查看实时分析进度和历史报告，支持添加全球市场股票 |
| 阶段三 | Paper Trading 环境下，AI 信号触发自动下单，持仓和订单可在 UniApp 查看 |
