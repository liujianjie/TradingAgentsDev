# TradingAgents 平台扩展 · 路线图（PLAN）

> 维护：随进展更新 | 最近更新：2026-06-06
> 详细规格见 `docs/spec-trading-platform.md`；本文件是高层路线 + 关键决策速查。

## 三阶段总览

| 阶段 | 目标 | 状态 |
|------|------|------|
| 阶段一 | 微信推送（Server酱定时分析） | ✅ 代码完成，待完整 E2E |
| 阶段二 | UniApp 可视化（H5 + 微信小程序） | ✅ 基本完成，缺 settings 设置页 |
| 阶段三 | IBKR 自动交易 | ⏸️ **用户决定延后到最后**，先把分析体验做厚 |

## 当前焦点（2026-06-06 起）：分析查看体验

- ✅ 前端「清新金融卡片风」重做（设计令牌 `uniapp-frontend/src/uni.scss`）
- ✅ 分析报告在线 Markdown 渲染（`marked` + `mp-html`，跨 H5/小程序）
- ⬜ settings 设置页（推送时间 + LLM 模型选择）—— 阶段二遗留
- ⬜ 实时进度从 5 秒轮询升级 SignalR（可选，非必须）

## 数据源策略（关键决策）

**覆盖需求**：全球（美股 / A股 / 日韩 / 港股都要），**每个市场用最强的源**。

### 用户决策（2026-06-07）：按市场自动路由 + UI 可一键覆盖
- 不要死用单一源；**按 ticker 市场自动选最优源**，失败自动 fallback。
- UI：默认「智能（按市场最优）」，设置页提供一键覆盖（自动 / 强制 yfinance / 强制 akshare / 强制 AV）。
- 实施顺序：**先后端核心路由**（让 A股/港股立刻有真数据），UI 选择随后补。

### 按「市场 × 类别」的源矩阵（目标）
| 市场（后缀） | 行情/技术/基本面 | 个股新闻 | 全球宏观新闻 |
|---|---|---|---|
| A股 `.SS/.SZ` | **akshare**（免费不限量）→ yfinance | akshare 中文（东财）→ yfinance | yfinance/AV（统一） |
| 港股 `.HK` | **akshare 港股** → yfinance | akshare → yfinance | yfinance/AV（统一） |
| 美股/日韩/英股 | **yfinance** → alpha_vantage | yfinance → AV | yfinance/AV |

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
  新增数据源 = 写模块实现 9 个方法 + 注册 `VENDOR_LIST` / `VENDOR_METHODS`。
- fallback 逻辑（`route_to_vendor`，约 159 行）**只 catch `AlphaVantageRateLimitError`**。
  要支持"无此股票就切源"，需扩展这个 except。
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
