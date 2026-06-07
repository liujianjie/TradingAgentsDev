# TODO

> 最近更新：2026-06-07 | 路线见 `PLAN.md` | 规格见 `docs/spec-trading-platform.md`
> 本文件 = agent-skills 工作流的 **TASKS** 层（SPECIFY→PLAN→**TASKS**→IMPLEMENT）。
> 未完成任务按 agent-skills 结构写：**Acceptance**(完成标准) / **Verify**(如何验证) / **Files**(涉及文件)。

## 🟡 进行中 / 下一步

### 数据源按市场路由（详见 `PLAN.md`「数据源策略」）
D1 核心切片均已完成：行情(下方已完成区) + **D1-2 技术指标 / D1-3 基本面 / D1-4 个股新闻**（见各项）。
A股财务/行情/指标**走 akshare 新浪源**，港股财务走东财 em（非 push2his），**均不用东财行情接口**（反爬，见搁置项）。
剩 D1-5（加固）+ D2（UI 数据源选择）。

- [x] **D1-2 · akshare 技术指标**（get_indicators）✅ 2026-06-07
  - 实现: 把 OHLCV 来源做成**可插拔**——`load_ohlcv` 加 `fetcher`/`source_tag`（默认 yfinance 不变、
    缓存文件名各源独立 `{sym}-{tag}-data`）；`get_stock_stats_indicators_window`/`_get_stock_stats_bulk`
    透传 fetcher。akshare 只提供新浪 OHLCV fetcher（`_fetch_akshare_ohlcv_df`，与行情同源同口径=新浪前复权），
    **复用 yfinance 同一套指标窗口+描述逻辑**，输出格式完全一致。自定义源取数失败时上抛 → 路由 vendor 级
    fallback 到 yfinance 指标（不静默改用 yfinance OHLCV 造成源不一致）。
  - 实测: `600519.SS` rsi 走 akshare 新浪取到值（缓存生成 `600519.SS-akshare-data` 证实非回落）；
    `7709.HK`(ETP) rsi 同样有值；`AAPL` akshare 正确弃权 → fallback yfinance；旧 4 参数调用签名兼容。
  - Files: `akshare_utils.py`、`stockstats_utils.py`、`y_finance.py`、`interface.py`（注册 get_indicators）

- [x] **D1-3 · akshare 基本面**（get_fundamentals / balance / cashflow / income）✅ 2026-06-07
  - 实现: A股走**新浪不反爬源**（`stock_financial_abstract` 概览 + `stock_financial_report_sina` 三大报表）；
    港股走**东财 em**（`stock_financial_hk_analysis_indicator_em` + `stock_financial_hk_report_em`，非 push2his 故可用）。
    报表统一转成「行项目×报告期」CSV，对齐 yfinance；防 look-ahead 按报告期末 <= curr_date 过滤（同 yfinance 约定）。
    freq=annual 仅取年报(12-31)、quarterly 含季报；4 个函数注册进 `interface.py` VENDOR_METHODS（akshare 优先）。
  - 实测: `600519.SS` 基本面/资产负债/利润/现金流均走 akshare 新浪取到真数据（茅台 2025 营收 1720.54亿、ROE 32.53）；
    `000001.SZ`(平安银行季报)、`0700.HK`(腾讯，东财年报+指标 ROE 21.13%) 均通过。
  - 降级: `07709.HK`(ETP) akshare 内部 NoneType → AkshareUnavailableError → fallback yfinance，
    fundamentals 返回 ETP 概览、balance 返回 "No balance sheet data found" 清晰提示，**不崩**。
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
- TUN 环境下东财障碍的实测结论（2026-06-07 多轮验证，翻案时直接看这里）：
  - `www.eastmoney.com`(首页)、`stock_news_em`(新闻 API) 在 TUN 下**可访问** → 东财非全站封锁、非 IP 封
  - 但 `push2his`(行情 API) chrome120/chrome110/chrome 全 `curl(56) Connection closed`
  - **已排除三种解释**：① 非 IP 暂封——隔数小时低频复测仍 curl(56)，若封 IP 早解封 ② 非指纹——chrome120
    也 56 ③ 非整站/路由——所有东财域名 DNS 均 fake-ip(198.18.x) 走 Clash，但其它东财接口照样通
  - **结论：是 `push2his` 行情接口本身的针对性反爬（拒爬虫请求），与 IP/指纹/TUN 路由无关**；
    东财新闻接口(stock_news_em)反爬松、可用。故"行情走新浪 + 新闻走 stock_news_em"正确绕开了 push2his。
- 翻案攻克路径（若将来要东财行情）：① 研究 push2his 反爬绕过（需要的 cookie/秘钥参数/频率控制，
  参考 akshare 内部或抓包真实浏览器请求）② 或直接用东财别的行情接口(如 stock_zh_a_hist 的不同 endpoint)
  ③ 但鉴于新浪行情已稳、数据同源同质，东财行情价值低，优先做东财**衍生数据**(研报/资金流/龙虎榜)才划算。

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
