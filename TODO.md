# TODO

> 最近更新：2026-06-07 | 路线见 `PLAN.md` | 规格见 `docs/spec-trading-platform.md`
> 本文件 = agent-skills 工作流的 **TASKS** 层（SPECIFY→PLAN→**TASKS**→IMPLEMENT）。
> 未完成任务按 agent-skills 结构写：**Acceptance**(完成标准) / **Verify**(如何验证) / **Files**(涉及文件)。

## 🟡 进行中 / 下一步

### 数据源按市场路由（详见 `PLAN.md`「数据源策略」）
D1 行情切片已完成（见下方已完成区）；继续后续 vendor 切片，**均走 akshare 新浪源，不用东财**（东财反爬，见搁置项）。

- [ ] **D1-2 · akshare 技术指标**（get_indicators）
  - Acceptance: A股/港股 `get_indicators` 走 akshare 新浪 OHLCV + 复用 stockstats 算指标，输出与 yfinance 同格式
  - Verify: `route_to_vendor('get_indicators','600519.SS',...)` 命中 akshare 并返回指标；`07709.HK` 同样有值
  - Files: `tradingagents/dataflows/akshare_utils.py`、`interface.py`（VENDOR_METHODS 注册 get_indicators）

- [ ] **D1-3 · akshare 基本面**（get_fundamentals / balance / cashflow / income）
  - Acceptance: A股走 akshare 财务（不反爬源，如新浪/`stock_financial_abstract`）；港股 ETP 无财报时优雅降级不崩
  - Verify: `600519.SS` 基本面有数据；`07709.HK` 返回"无财报"清晰提示而非异常
  - Files: `akshare_utils.py`、`interface.py`

- [x] **D1-4 · akshare 个股新闻**（get_news）✅ 2026-06-07
  - 实现: `get_akshare_news`（stock_news_em，防 look-ahead 按发布时间 <= end_date 过滤）+ interface 注册
  - 实测: 07709.HK 取到 10 条相关中文新闻（"南方两倍做多海力士涨14.98%"），route 命中 akshare
  - 效果: 新闻面有港股真实新闻；情感面 news_block 不再空（StockTwits/Reddit 港股仍无 = 美股社区无解）

- [ ] **D1-5 · ticker 规范化下沉到 yfinance vendor**（加固，当前只在 analyzer 入口）
  - Acceptance: 绕过 analyzer 入口、直接把 `07709.HK` 传给 yfinance vendor 也能取数（不再 404）
  - Verify: `get_YFin_data_online('07709.HK',...)` 内部自动归一为 `7709.HK` 成功取数
  - Files: `tradingagents/dataflows/y_finance.py`

- [ ] **D2 · UI 数据源选择**（PLAN 已定：自动为主 + 一键覆盖）
  - Acceptance: 设置页下拉「自动 / 强制 yfinance / 强制 akshare / 强制 AV」，选择透传到 Python 覆盖市场默认
  - Verify: UI 选「强制 yfinance」后分析 A股，日志显示走 yfinance 而非 akshare
  - Files: uniapp 设置页、C# `AnalysisController`/`AnalyzeRequest`、`api/analyzer.py`

- [ ] **settings 设置页**（阶段二遗留）：推送时间 + LLM 模型选择（建议与 D2 数据源选择同页）

- [低优先/可选] **baostock 第二层 fallback**
  - Acceptance: A股链 `akshare(新浪)→baostock→yfinance`；baostock 是独立免费 API（非爬虫）的真冗余
  - Verify: 模拟新浪失败时自动落 baostock 取到数据
  - Files: 新建 `baostock` vendor + `interface.py`
  - 注: TUN 下需 Clash 加 `baostock.com` 直连。新浪已稳，不急。

### 🔖 搁置待翻案：东财数据源（用户 2026-06-07 决定先记录、后续再议，现用新浪翻篇）
- 现状决定：行情 OHLCV 用新浪源（与东财同源同质、已验证可用），暂不引入东财。
- 东财的真正价值在**衍生数据**（研报 / 资金流 / 龙虎榜 / 北向资金），**不是**基础行情 OHLCV
  （日线开高低收量是交易所统一数据，新浪=东财=baostock，已验证茅台 1272.86 两边一致）。
  → 将来真要做"资金流/龙虎榜"这类分析时，再攻克东财才划算。
- TUN 环境下东财的障碍（实测，翻案时直接看这里）：
  - `www.eastmoney.com` chrome120 直连 HTTP 200 → 指纹够用、eastmoney 直连规则生效
  - 但 `push2his` API 子域名 chrome120/chrome110/chrome 全 `curl(56) Connection closed`
  - 结论：**指纹不是瓶颈，push2his 子域名被 Clash 路由到代理(台湾)被东财拒才是**。
    故 TradingAgents-CN 的 curl_cffi(chrome120) 方案（它直连大陆有效）搬到本 TUN 环境无效。
- 翻案攻克路径：① Clash 让 push2his 真直连（清 fake-ip 缓存 / DNS 段加 `fake-ip-filter: eastmoney.com`
  / 查 rules 顺序确认 DIRECT 在代理规则前）→ 用 www 同款直连验证 push2his 走大陆
  ② 复刻 TradingAgents-CN 的 monkeypatch（`providers/china/akshare.py:43-150`，eastmoney URL 走
  `curl_cffi.get(impersonate="chrome120")`）③ 把东财源加进 fallback 链作可选。

## 🟢 已完成

### 本次会话（提交 `1e7d37e`，2026-06-07）
- [x] **xAI(Grok) provider 接入** + apikeys 文档 xAI 章节（已验证 key + deep/quick 模型可用）
- [x] **yfinance 切 requests backend** 绕 curl_cffi TLS 错误（韩股 `.KS` 等非美市场）
- [x] **yf_retry 增加网络超时/连接错误重试**（中国大陆访问 Yahoo 偶发超时自愈）
- [x] **港股 ticker 前导0规范化**（`07709.HK`→`7709.HK`）+ analyzer 开跑前预检
- [x] **数据源 D1 行情切片**：akshare 新浪源 + 按市场自动路由（A股/港股→akshare，美股→yfinance）+ 失败 fallback；A股(沪深)/港股(0700/07709) 端到端实测通过
- [x] **情感分析**三数据源并行拉取 + 全异常兜底（防 GFW 干扰冒泡杀死节点）
- [x] **新闻分析** prompt 加约束，禁止把无关宏观新闻牵强关联到标的
- [x] **报告保存**：C# 编排器分析完成后存 MD 到 `reports/` + 前端显示保存路径
- [x] **文档**：PLAN/TODO 路线 + `docs/setup-clash-cn-direct.md`（Clash TUN 国内源直连指导）

### 更早（已提交）
- [x] 前端「清新金融卡片风」重做（`c6a9088`）
- [x] 分析报告在线 Markdown 渲染 marked + mp-html（`c6a9088`）
- [x] 修复自选股中文名乱码 `?`（DB 直接修，QQQ→纳斯达克100 ETF 等 8 条）
- [x] ~~DeepSeek key 失效阻塞~~ → 已改用 **xAI** 绕过，不再阻塞

## 📌 已知坑（避免重复踩）

- **akshare 行情走新浪源**（`stock_zh_a_daily` / `stock_hk_daily`），**别用东财源**（`stock_zh_a_hist`/`stock_hk_hist`）——东财 push2his API 反爬，直连大陆 IP 也 RemoteDisconnected。已加 1.2s 全局节流 + 必须保留 yfinance fallback。
- **用户网络是 Clash Verge TUN 全局代理**（为访问境外 grok）：会把国内数据源（新浪/东财）流量也绕到境外节点导致失败。需在 Clash 让国内域名直连（见 `docs/setup-clash-cn-direct.md`）；调试国内源时可临时关 TUN。
- **grok 经境外 api.x.ai 调用极慢**（单次 ~320s），完整分析十几次调用易 timeout；用户已知情，暂不处理（详见 memory）。
- 自选股**只能通过网页 UI 添加**；用 PowerShell/curl 加中文名会被 ASCII 编码成 `?`（不可逆）。
- 改任何 LLM key / provider 后**必须重启 Python API 服务**才生效。
- `.bat` 必须纯 ASCII（中文搬 `.ps1`）——见全局 CLAUDE.md。
