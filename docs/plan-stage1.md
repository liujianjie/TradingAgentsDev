# 阶段一实施计划：微信推送

> 版本：v1.0 | 创建：2026-05-31
> 关联规格：[spec-trading-platform.md](./spec-trading-platform.md)

---

## Overview

阶段一目标：在工作日盘前盘后，自动分析自选股，结果通过 Server酱推送到用户微信。

**最终 vertical slice**：用户运行 `dotnet run`，等到 08:30 / 15:10，微信收到一条包含完整分析结果的消息。

把这个目标拆成 8 个递增的小任务，每完成一个，系统都处于"能跑、能验证"的状态。

---

## Architecture Decisions

| 决策 | 选择 | 理由 |
|------|------|------|
| Python 包管理 | 国内镜像源 + venv | PyPI 直连失败，用清华镜像 |
| 任务持久化 | 内存 dict（阶段一）→ SQLite（阶段二） | 阶段一只跑一台机器，无持久化需求；阶段二上 EF Core |
| 任务通信 | HTTP 轮询 | 简单可靠；SignalR/SSE 留到阶段二 |
| 配置加载 | C# 用环境变量 + appsettings.json | 不在代码里硬编码 SendKey |
| 测试范围 | 关键集成点写 smoke test | 不追求高覆盖率，重点是端到端能跑通 |

---

## 依赖图

```
T1 (Python 环境 + 装包)
  ↓
T2 (Python API 启动) ──→ T3 (Python 分析能跑完)
                              ↓
T4 (C# 脚手架) ──────────────────→ T5 (C# 调 Python API)
                                       ↓
                                  T6 (C# Server酱推送)
                                       ↓
                                  T7 (C# 串端到端流程)
                                       ↓
                                  T8 (Hangfire 定时调度)
```

---

## Task List

### Phase 1: Python 后端跑通

#### Task 1: 配置 Python 镜像源并安装 FastAPI 依赖

**Description**: 解决 PyPI 直连失败问题，用清华镜像安装 fastapi 和 uvicorn 到现有虚拟环境。

**Acceptance criteria**:
- [ ] `python -c "import fastapi, uvicorn"` 不报错
- [ ] `requirements-api.txt` 列出阶段一所需的额外依赖
- [ ] 配置文件 / 文档说明镜像源用法（避免下次又卡住）

**Verification**:
```bash
cd F:/AIProject/TradingAgents
pip install -r api/requirements-api.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python -c "import fastapi, uvicorn; print('OK')"
```

**Dependencies**: None

**Files likely touched**:
- `api/requirements-api.txt`（已存在，可能需要补依赖）
- `docs/setup-python-env.md`（新增：镜像源使用说明）

**Scope**: XS

---

#### Task 2: Python FastAPI 启动并响应 /health

**Description**: 启动 FastAPI 服务，验证 HTTP 接口存活。已有的 `api/main.py` 已经定义了 `/health`，但还没验证能跑。

**Acceptance criteria**:
- [ ] `uvicorn api.main:app --port 8000` 能启动，无 import 错误
- [ ] `curl http://localhost:8000/health` 返回 `{"status": "ok", ...}`
- [ ] `curl http://localhost:8000/docs` 能看到 Swagger UI

**Verification**:
```bash
cd F:/AIProject/TradingAgents
uvicorn api.main:app --port 8000 &
sleep 2
curl -s http://localhost:8000/health | grep -q "ok" && echo "PASS" || echo "FAIL"
```

**Dependencies**: T1

**Files likely touched**:
- 调试 `api/main.py` 的 import（可能需要修 `analyzer.py` 的相对导入）

**Scope**: XS

---

#### Task 3: Python API 能完整跑完一次股票分析

**Description**: 验证 `POST /api/v1/analyze` 能调用 TradingAgents 核心引擎并返回结果。这是阶段一的核心验证点 —— 一旦这个跑通，C# 层只是包装。

**Acceptance criteria**:
- [ ] POST `/api/v1/analyze` 立即返回 `job_id` 和 `status: queued`
- [ ] 后台异步执行 TradingAgentsGraph
- [ ] GET `/api/v1/jobs/{job_id}` 在分析中返回 `running`，完成后返回 `completed` + 完整报告
- [ ] 报告包含 market_report、sentiment_report、news_report、fundamentals_report、final_trade_decision

**Verification**:
```bash
# 触发分析（用 quick_think_llm 加快速度，AAPL 数据稳定）
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL", "date": "2026-05-30"}'
# → {"job_id": "xxx", "status": "queued"}

# 轮询直到 completed（首次约 5-15 分钟）
curl http://localhost:8000/api/v1/jobs/{job_id}
# → status=completed, result 包含 5 个报告字段
```

**Dependencies**: T2

**Files likely touched**:
- `api/analyzer.py`（可能需要修 ThreadPoolExecutor 死锁问题）
- `tests/test_api_smoke.py`（新增：smoke test）

**Scope**: S

---

### Checkpoint: Python 后端就绪
- [ ] uvicorn 能启动
- [ ] 一次完整分析能跑完，结果可拉取
- [ ] 失败的分析能在 GET 接口看到 `failed` 和错误信息

---

### Phase 2: C# 后端跑通

#### Task 4: C# ASP.NET Core 项目脚手架

**Description**: 用 `dotnet new webapi` 创建项目，配置基础中间件（CORS、Swagger、配置文件），跑 Hello World。

**Acceptance criteria**:
- [ ] `TradingPlatform/TradingPlatform.Api/` 目录下有完整 .NET 8 webapi 项目
- [ ] `dotnet run` 启动到 http://localhost:8080
- [ ] 访问 `/swagger` 能看到 Swagger UI
- [ ] `appsettings.json` 配置了 PythonApiBaseUrl 和 ServerChan SendKey 占位符
- [ ] `appsettings.local.json` 在 `.gitignore` 中，用于实际密钥

**Verification**:
```bash
cd F:/AIProject/TradingAgents/TradingPlatform/TradingPlatform.Api
dotnet run --urls http://localhost:8080 &
sleep 3
curl -s http://localhost:8080/swagger/index.html | grep -q "Swagger" && echo "PASS"
```

**Dependencies**: None（可与 T1-T3 并行）

**Files likely touched**:
- `TradingPlatform/TradingPlatform.sln`
- `TradingPlatform/TradingPlatform.Api/*.cs`（约 4-5 个文件）
- `TradingPlatform/TradingPlatform.Api/appsettings.json`
- `.gitignore`

**Scope**: S

---

#### Task 5: C# 调用 Python API 拉取分析结果

**Description**: C# 实现 `IAnalysisService`，封装对 Python FastAPI 的调用：触发分析 → 轮询 → 拿结果。

**Acceptance criteria**:
- [ ] `AnalysisService.TriggerAnalysisAsync(ticker, date)` 返回 jobId
- [ ] `AnalysisService.WaitForCompletionAsync(jobId, timeout)` 轮询直到完成或超时
- [ ] 失败时抛出明确异常（含 Python 端错误消息）
- [ ] 单元测试：用 mock HttpClient 验证序列化/反序列化正确

**Verification**:
```bash
# 启动 Python API
uvicorn api.main:app --port 8000 &
# 跑 C# 集成测试
cd TradingPlatform
dotnet test --filter "Category=Integration&FullyQualifiedName~AnalysisService"
```

**Dependencies**: T3, T4

**Files likely touched**:
- `TradingPlatform.Api/Services/IAnalysisService.cs`
- `TradingPlatform.Api/Services/AnalysisService.cs`
- `TradingPlatform.Api/Models/AnalysisDtos.cs`
- `TradingPlatform.Tests/AnalysisServiceTests.cs`

**Scope**: M

---

#### Task 6: C# Server酱推送服务

**Description**: 实现 `IPushService.SendAsync(title, content)`，调用 Server酱 HTTP 接口发送微信。

**Acceptance criteria**:
- [ ] `PushService` 从配置读取 SendKey（环境变量优先于 appsettings）
- [ ] 调用 `https://sctapi.ftqq.com/{SendKey}.send` 发送消息
- [ ] 失败时记录日志但不抛异常（推送失败不应阻塞业务）
- [ ] 集成测试（标记为 manual，避免每次跑都耗用免费额度）：手动跑后微信能收到

**Verification**:
```bash
# 手动测试（需要真实 SendKey）
$env:SERVERCHAN_SEND_KEY = "<YOUR_KEY>"
dotnet test --filter "Category=ManualPush"
# 微信检查是否收到消息
```

**Dependencies**: T4

**Files likely touched**:
- `TradingPlatform.Api/Services/IPushService.cs`
- `TradingPlatform.Api/Services/ServerChanPushService.cs`
- `TradingPlatform.Tests/PushServiceTests.cs`

**Scope**: S

---

#### Task 7: C# 端到端编排：分析 + 格式化 + 推送

**Description**: 实现 `AnalysisController.Trigger`，串起 T5 + T6：接收 ticker，触发分析，等待结果，格式化为微信消息，推送。

**Acceptance criteria**:
- [ ] `POST /api/analysis/trigger` Body `{ "ticker": "AAPL" }` 返回 jobId 立即响应
- [ ] 后台任务执行：调 Python → 等结果 → 格式化 → 推送
- [ ] 推送的微信消息符合 spec 中定义的格式（决策、技术面、情感面等小标题）
- [ ] 失败时推送一条失败通知（含 ticker 和错误摘要）

**Verification**:
```bash
# 启动 Python + C#
curl -X POST http://localhost:8080/api/analysis/trigger \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL"}'
# 等 5-15 分钟，微信收到完整报告
```

**Dependencies**: T5, T6

**Files likely touched**:
- `TradingPlatform.Api/Controllers/AnalysisController.cs`
- `TradingPlatform.Api/Services/ReportFormatter.cs`（格式化报告为微信文本）
- `TradingPlatform.Tests/ReportFormatterTests.cs`

**Scope**: M

---

#### Task 8: Hangfire 定时调度自选股分析

**Description**: 引入 Hangfire，配置每个工作日 08:30 和 15:10 自动触发对自选股列表的分析。

**Acceptance criteria**:
- [ ] Hangfire dashboard 可访问 http://localhost:8080/hangfire
- [ ] 自选股列表暂时硬编码在 appsettings.json（一个 JSON 数组）
- [ ] 定时任务在指定时间触发对每只股票调用 `AnalysisService.TriggerAndPushAsync`
- [ ] 验证：把 cron 临时改为 1 分钟后，等待自动触发，微信收到消息

**Verification**:
```bash
# 临时改 appsettings.local.json 中的 Cron 表达式为下一分钟
# 启动 dotnet run，等到那一分钟，观察：
# 1. Hangfire dashboard 能看到任务被触发
# 2. 微信收到一条分析报告
# 3. 结束后改回 0 30 8 * * MON-FRI
```

**Dependencies**: T7

**Files likely touched**:
- `TradingPlatform.Api/Services/SchedulerService.cs`
- `TradingPlatform.Api/Program.cs`（注册 Hangfire）
- `TradingPlatform.Api/appsettings.json`（自选股列表 + Cron 表达式）

**Scope**: S

---

### Checkpoint: 阶段一交付
- [ ] 工作日 08:30 / 15:10 自动触发
- [ ] 自选股列表中每只股票完成后微信收到一条消息
- [ ] 失败时也能收到错误通知
- [ ] Hangfire dashboard 显示任务历史

---

## Risks and Mitigations

| 风险 | 影响 | 缓解策略 |
|------|------|----------|
| PyPI 镜像源也不通 | 高 | 备选：阿里云镜像 https://mirrors.aliyun.com/pypi/simple/，或下载 wheel 离线安装 |
| TradingAgents 一次分析耗时 > 30 分钟 | 中 | 用 quick_think_llm 加速；Hangfire 任务超时设 60 分钟 |
| Server酱免费版每天 5 条限制 | 中 | 阶段一限制自选股 ≤ 2 只（每天 4 条 = 盘前盘后各 2 条） |
| LLM API Key 超额或失败 | 中 | C# 端捕获 Python 错误，推送失败通知到微信 |
| Windows 系统休眠导致 Hangfire 不触发 | 低 | 文档提示：保持电脑常开 + 关闭睡眠模式 |
| C# 调 Python 阻塞超时 | 中 | HttpClient Timeout 设 1 小时；轮询用 PollyExponentialBackoff |

---

## Open Questions（已自决）

1. ✅ **自选股列表存哪？** → 阶段一硬编码 appsettings.json；阶段二迁到 SQLite
2. ✅ **轮询间隔？** → C# 端每 10 秒轮询一次 Python，最多等 60 分钟
3. ✅ **报告格式语言？** → 跟随 TRADINGAGENTS_OUTPUT_LANGUAGE 配置；默认中文
4. ✅ **失败重试？** → 单次任务失败不重试，但 Hangfire 自身会保留任务历史

---

## 实施顺序

```
T1 → T2 → T3 → [Checkpoint Python 就绪]
  ↓
T4 (可与 T1-T3 并行)
  ↓
T5 → T6 → T7 → T8 → [Checkpoint 阶段一完成]
```

时间估算（仅供参考，按 spec 约定不强制）：
- T1-T3：Python 包安装 + 跑通分析（最大风险点）
- T4-T6：C# 三块独立可并行
- T7-T8：组装 + 调度

---

## 下一步

按照本计划，从 T1 开始逐任务推进。每完成一个任务，更新 TaskCreate 状态，并在对话中报告：
- 完成了什么
- 验证通过的证据
- 下一个任务即将开始
