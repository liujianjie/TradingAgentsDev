# TradingAgents 平台扩展 · 路线图（PLAN）

> 维护：随进展更新 | 最近更新：2026-06-07
> 详细规格见 `docs/spec-trading-platform.md`；任务清单见 `TODO.md`；本文件是高层路线 + 关键决策速查。
> （对应 agent-skills 工作流的 PLAN 层：SPECIFY=docs/spec → **PLAN=本文件** → TASKS=TODO.md → IMPLEMENT）

## 三阶段总览

| 阶段 | 目标 | 状态 |
|------|------|------|
| 阶段一 | 微信推送（Server酱定时分析） | ✅ 代码完成，待完整 E2E |
| 阶段二 | UniApp 可视化（H5 + 微信小程序） | ✅ 基本完成，缺 settings 设置页 |
| 阶段三 | IBKR 自动交易 | ⏸️ **用户决定延后到最后**，先把分析体验做厚 |

## 当前焦点（2026-06-06 起）：分析查看体验

- ✅ 前端「清新金融卡片风」重做（设计令牌 `uniapp-frontend/src/uni.scss`）
- ✅ 分析报告在线 Markdown 渲染（`marked` + `mp-html`，跨 H5/小程序）
- ✅ 报告保存本地 MD（`reports/`）+ 前端显示保存路径
- ✅ 多 LLM 支持（新增 xAI/Grok）；数据获取健壮性修复（TLS/超时/港股代码规范化）
- ✅ 数据源按市场路由（akshare 新浪源）— D1 全系列(行情/指标/基本面/新闻/ticker加固) + D2(智能 fallback+透明溯源) 完成
- ✅ settings 设置页（推送时间 + LLM 模型选择）—— 全栈完成；数据源不进设置页(D2 纯智能 fallback)、密钥留 apikeys
- ⬜ 实时进度从 5 秒轮询升级 SignalR（可选，非必须）

## 数据源策略（关键决策）

**覆盖需求**：全球（美股 / A股 / 日韩 / 港股都要），**每个市场用最强的源**。

### 用户决策（2026-06-07）：纯智能优先级链 + 自动 fallback，**不做手动选源 UI**
- 不要死用单一源；**按 ticker 市场自动选最优源**（优先级链），失败/无数据自动转下一个源。
- **否决「手动强制单一源」**：用户指出硬锁单一源会「选了没数据的源 → 白跑一次」，违背本意。
  改为：默认就是智能优先级链（auto），**不给手动选源下拉**；UI/报告只**透明展示**「本次实际用了
  哪个源、降级了什么」。最简单、永不白跑、信息透明。（与用户一贯偏好「分层级联而非二选一」一致。）
- **fallback 两类触发**（route_to_vendor，D2-a 已实现）：① vendor 抛异常（限流/akshare 不可用/
  AV 无 key/网络错，广义捕获+WARNING 日志）② vendor **返回空数据**（如 yfinance 小众标的 "No data found"）
  → 均自动转链中下一个源；全链空→返回清晰"无数据"提示不裸崩；全链异常→抛聚合异常。
- **情感源特例**：Reddit/StockTwits 是美股社区，港股/A股**全球无替代源**（不是换源能解决）→ 已优雅降级
  （fetcher 返回 `<...unavailable>` 占位 + prompt 要求 LLM 在 confidence/narrative 明示），不假装换源找。
- 实施顺序：**先后端 fallback 健壮性（D2-a ✅）**，再透明展示（D2-b）。

### 按「市场 × 类别」的源矩阵（目标）
| 市场（后缀） | 行情/技术/基本面 | 个股新闻 | 全球宏观新闻 |
|---|---|---|---|
| A股 `.SS/.SZ` | **akshare 新浪** → yfinance | akshare 中文新闻* → yfinance | yfinance/AV（统一） |
| 港股 `.HK` | **akshare 新浪** → yfinance | akshare 中文新闻* → yfinance | yfinance/AV（统一） |
| 美股/日韩/英股 | **yfinance** → alpha_vantage | yfinance → AV | yfinance/AV |

> \*个股新闻 akshare 主力 `stock_news_em` 走**东财**、受反爬影响，D1-4 切片时确认可用源（必要时降级 yfinance）。
> 行情已确认走**新浪**（`stock_zh_a_daily`/`stock_hk_daily`），不受东财反爬影响。
> \*\*基本面（D1-3 已实现）源细分**：A股财务走**新浪**（`stock_financial_abstract`/`stock_financial_report_sina`，不反爬）；
> 港股财务 akshare **无新浪接口**，走**东财 em**（`stock_financial_hk_*`，非 push2his 故可用）。即「行情新浪、A股财务新浪、港股财务东财」。

- **关键区分**：`get_news`（个股新闻）可按市场切 CN 源；但 `get_global_news`（全球宏观）
  只有 yfinance/AV 有，**永远不切 CN 源**（akshare 无全球宏观）。
- **ticker 格式适配（坑）**：各 vendor 代码格式不同，路由时按 vendor 转换——
  - yfinance：A股 `600519.SS`、港股去前导0补4位 `7709.HK`
  - akshare：A股纯6位 `600519`、港股5位**带**前导0 `07709`（与 yfinance 相反！）
- **否决**：tushare（积分制、偏 A股、不覆盖日韩）。
- **akshare 取舍**：免费不限量、A股/港股最全，但接口依赖爬虫偶失效 → 故必须 yfinance 兜底。
- **akshare 必走新浪源**（`stock_zh_a_daily` / `stock_hk_daily`），**不用东财源**：东财
  `push2his` API 反爬，直连大陆 IP 也 `RemoteDisconnected`；新浪源不反爬、英文列名、小众港股(07709)也有。
- **用户网络是 Clash Verge TUN 全局代理**（为 grok）：国内数据源会被绕境外而失败，需 Clash
  规则让国内域名直连（`docs/setup-clash-cn-direct.md`），或调试国内源时临时关 TUN。

## 架构事实（改动前必读）

- 数据层是 **vendor 路由 + fallback**（`tradingagents/dataflows/interface.py`）。
  新增数据源 = 写模块实现对应方法 + 注册 `VENDOR_LIST` / `VENDOR_METHODS`。
- 路由已支持**按 ticker 市场自动选 vendor**（`_auto_vendor_chain`：A股/港股→akshare 优先、
  美股→yfinance；`get_global_news` 恒走 yfinance/AV）。config 显式指定（UI 覆盖）优先于自动。
- fallback 已扩展：`route_to_vendor` 现 catch `AlphaVantageRateLimitError` + `AkshareUnavailableError`
  （akshare 失败/无数据/非 CN 市场 → 自动切链中下一个 vendor）。
- LLM key 流向：`config/apikeys.local.json` → `api/config_loader.py` 注入环境变量
  → `load_apikeys()` 只在 **API 启动时执行一次**（改 key 后必须重启 Python 服务）。
- deepseek/qwen/glm/minimax 等 OpenAI 兼容源会**自动解析各自官方 endpoint**
  （`openai_client.py` `_PROVIDER_BASE_URL`），无需手填 base_url。

## 全球 Ticker 速查（yfinance 后缀）

| 市场 | 后缀 | 示例 |
|------|------|------|
| 美股 | 无 | `AAPL` `QQQ` |
| A股·沪 | `.SS` | `600519.SS` 茅台 |
| A股·深 | `.SZ` | `000001.SZ` 平安银行 |
| 港股 | `.HK` | `0700.HK` 腾讯 |
| 日本 | `.T` | `7203.T` 丰田 |
| **韩国** | `.KS` | `000660.KS` SK海力士 |
| 英股 | `.L` | `SHEL.L` 壳牌 |
