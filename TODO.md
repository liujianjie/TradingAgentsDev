# TODO

> 最近更新：2026-06-07 | 路线见 `PLAN.md` | 规格见 `docs/spec-trading-platform.md`
> 本文件 = agent-skills 工作流的 **TASKS** 层（SPECIFY→PLAN→**TASKS**→IMPLEMENT）。
> 未完成任务按 agent-skills 结构写：**Acceptance**(完成标准) / **Verify**(如何验证) / **Files**(涉及文件)。

## 🟡 进行中 / 下一步

### Serenity 产业链卡点研究（spec: `docs/spec-serenity-research.md`）

独立模块，不接入多代理交易分析图；后端 `tradingagents/serenity/` + 独立 endpoint
`/api/v1/serenity/*`；前端独立 Tab "产业链研究"。10 个 commit 已落，56 单测全过。

- [x] **T1-T6 · 后端全栈 + 单测** ✅ 2026-06-20
  - 实现: schemas / prompts / 6 个 tool / workflow / API endpoint，56 case 全过
  - Files: `tradingagents/serenity/*`、`api/serenity.py`、`tests/test_serenity_*.py`

- [x] **T7-T8 · 前端 UniApp 提交页 + 报告页** ✅ 2026-06-20
  - 实现: 三 mode 切换 + 三市场 + 9 步进度条 + 报告分块渲染 + 证据点击
  - Files: `uniapp-frontend/src/pages/serenity/{index,report}.vue`

- [x] **T9 · e2e probe 脚本就绪** ✅ 2026-06-20
  - Files: `scripts/probe_serenity_e2e.py`
  - **Acceptance 待用户授权真跑**：A 股 AI 半导体 + 美股 AI 算力，验收 top_priorities ≥3 / evidence ≥2 含 ≥1 primary。
  - Verify: `python scripts/probe_serenity_e2e.py`；预算 ~400K tokens。

- [ ] **T11 · v1.1 港股纳入 + 历史持久化** (待开)
  - 港股 HKEX filings tool + 港股 market hint 已就位但 spec §3 v1 排除。
  - in-memory `_jobs` → SQLite / 文件持久化，重启不丢历史。

### S（Sentiment）情感面 / 新闻面 / 特色数据三阶段强化（spec: `docs/spec-sentiment-multi-source.md`）
背景：A股/港股 sentiment_analyst 之前对 StockTwits/Reddit 直接降级"无数据"；用 akshare 东财量化情感指标
+ 热度时序 + Google News 替代，把"情感面缺失"补齐。参考项目 TradingAgents-CN 的 A股情感是空壳 TODO，
不抄。源已 probe 实证（`reports/sentiment_probe/20260619_235021/report.md`）。**美股链路不变**。
不接：小红书 / 抖音（强反爬+法律风险）；雪球 / 富途留接口位不实施（Phase 2 再说）；tushare（PLAN 已否决）。

- [x] **S1-1 · 中文情感聚合器（千股千评 + 热度 + 关键词 + 港股热度）** ✅ 2026-06-20
  - 实现: `dataflows/chinese_sentiment.py` 4 fetcher（千股千评/热度时序/热门关键词/港股热度），
    每个失败返回 None graceful-degrade；千股千评全市场表（5184 行）5 分钟模块级 TTL cache；
    防 look-ahead（按交易日/时间过滤 <= curr_date）；ticker → 东财 SH/SZ/5位前缀格式。
  - Verify: 15 unit test + 2 integration test 通过；茅台真实网络 ~10s 首调 / cache 后 <0.1s。
  - Files: `tradingagents/dataflows/chinese_sentiment.py`、`tests/test_chinese_sentiment.py`

- [x] **S1-2/3 · sentiment_analyst 按市场分流 + CN/HK prompt 模板 + 溯源** ✅ 2026-06-20
  - 实现: `market_of(ticker)` 三路分流（US 保留 News+StockTwits+Reddit / A股 News+千股千评+
    热度时序+所属概念热度 / HK News+港股热度时序）；CN 模板突出"千股千评是结构化情感雷达，
    无需 LLM 二次打分"分析方法；fetcher 返回 None → 注入 `<unavailable: ...>` 占位串到 prompt
    并 record_provenance 走降级条目；`SentimentReport` schema 不变。
  - Verify: 8 routing test 全过；US/CN/HK 三路 prompt 各自包含市场专属数据块标签（如
    `<start_of_em_comment>` / `<start_of_hk_hot_trend>`），不混入其它市场标签；
    全项目 290 回归 test 通过（2 个 pre-existing failure 与本改动无关）。
  - Files: `tradingagents/agents/analysts/sentiment_analyst.py`、`tests/test_sentiment_market_routing.py`

- [x] **S2 · 新闻面强化（Google News 兜底）** ✅ 2026-06-20
  - 实现: `dataflows/google_news.py` RSS 搜索（按 ticker 市场自动调 hl/gl/query：A 股 zh-CN，
    港股 zh-HK 中英双搜，美股 en-US），防 look-ahead 按 pubDate 严格过滤 ≤ end_date；
    `interface.py` VENDOR_METHODS["get_news"] 加 google_news；`_MARKET_VENDOR_CHAIN` A 股/港股
    链改成 `["akshare", "google_news", "yfinance"]`。美股链不变。失败抛 GoogleNewsUnavailableError
    自动 fallback 到下一个 vendor。
  - Verify: 13 unit test（含 query 参数 / happy path / HTTP 错 / 网络错 / 空 RSS / look-ahead /
    route_to_vendor 集成 3 场景）通过。test_route_us_path_unchanged_no_google_news_call 确认
    美股链不被破坏。
  - Files: `tradingagents/dataflows/google_news.py`、`tradingagents/dataflows/interface.py`、
    `tests/test_google_news.py`

- [x] **S-E2E · 新闻面端到端业务回归 + 兜底协议** ✅ 2026-06-20
  - 实现: `scripts/verify_news_e2e.py` 模拟真实 API 路径（vendor=auto），覆盖正常路径
    11 ticker（A股×4 / 港股×4 / 美股×3）、兜底路径 4 ticker（akshare 强制失败验证 google_news
    救场）、极端路径 1（全链失败验证抛 RuntimeError + 溯源完整）。spec 补 § 5.5 四层处理协议
    （L1 主源 / L2 google_news / L3 末位 / L4 全空时透明降级+`<unavailable>`+ confidence=low
    +禁编造）。
  - Verify: 11/11 正常路径 [OK] + 4/4 兜底路径 [OK] + 1/1 极端路径 [OK]，**总失败 0**。
    A股/港股全部命中 akshare 主源（耗时 ~1.2s）、美股全部命中 yfinance、akshare 失败时
    google_news 100% 救场（耗时 ~2-5s）。
  - Files: `scripts/verify_news_e2e.py`、`docs/spec-sentiment-multi-source.md` § 5.4/5.5

- [x] **S3 · A股特色数据（北向资金 / 龙虎榜）** ✅ 2026-06-20
  - 实现: `dataflows/akshare_cn_features.py` 两 fetcher（`get_north_bound_holding` 走
    `stock_hsgt_individual_em` 近 30 个交易日陆股通持仓时序 / `get_dragon_tiger_list` 走
    `stock_lhb_stock_statistic_em` 全市场近一月统计按 ticker 抽行，5 分钟模块级 cache）；
    `agents/utils/cn_features_tools.py` LangChain @tool wrapper（非 A 股返回 n/a 占位串
    不抛栈，让 LLM 自然跳过）；`fundamentals_analyst.py` tools 列表追加两 tool +
    prompt 段说明"A 股 ticker 必调，HK/US 安全跳过"。决策放在 fundamentals_analyst（避免新增
    event_analyst 引入 graph 复杂度，spec § 3.6 已决）。
  - Verify: 12 unit test（含 mock akshare 形态 / 失败 graceful / 防 look-ahead / cache 摊销 /
    fundamentals_analyst.bind_tools 注册验证）+ 2 integration test（茅台北向 / 龙虎榜真实网络）
    通过。
  - Files: `tradingagents/dataflows/akshare_cn_features.py`、
    `tradingagents/agents/utils/cn_features_tools.py`、
    `tradingagents/agents/analysts/fundamentals_analyst.py`、`tests/test_cn_features.py`

### 数据源按市场路由（详见 `PLAN.md`「数据源策略」）
D1 核心切片均已完成：行情(下方已完成区) + **D1-2 技术指标 / D1-3 基本面 / D1-4 个股新闻**（见各项）。
A股财务/行情/指标**走 akshare 新浪源**，港股财务走东财 em（非 push2his），**均不用东财行情接口**（反爬，见搁置项）。
D1 全系列 ✅ + D2（智能 fallback + 透明溯源）✅ + **settings 设置页 ✅**。阶段二主线全部收尾。
剩余：低优先 baostock fallback（不急）、可选 SignalR 实时进度。阶段三 IBKR 用户决定延后。

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

- [x] **D1-5 · ticker 规范化下沉到 yfinance vendor**（加固）✅ 2026-06-07
  - 实现: 新增**单一真相源** `dataflows/utils.py:to_yfinance_symbol`（港股前导0：07709.HK→7709.HK，
    严格只匹配 `\d+.HK`——**韩股 000660.KS 等其他市场原样不动**）。下沉到所有 yfinance 取数入口：
    `y_finance.py` 6 个函数（data/fundamentals/balance/cashflow/income/insider）+ `stockstats_utils.load_ohlcv`
    **仅 yfinance 路径归一**（akshare 走新浪要 5 位、由 fetcher 自适配，不污染）。`api/analyzer._normalize_ticker`
    改为委托该函数（消除重复正则、防漂移）。
  - 实测: 直传 `get_YFin_data_online('07709.HK',...)` 内部归一为 7709.HK 取到 8 条真数据(不再 404)；
    akshare 指标直传 `07709.HK` 仍走 5 位正常；analyzer 委托 + 韩股保留均验证；加单测覆盖契约（含韩股陷阱）。
  - Files: `dataflows/utils.py`、`y_finance.py`、`stockstats_utils.py`、`api/analyzer.py`、`tests/test_ticker_symbol_handling.py`

### D2 重塑（2026-06-07 用户决策）：纯智能 fallback + 透明展示，**不做手动选源 UI**
> 用户否决「手动强制单一源」（会"选了没数据的源→白跑一次"）。改为默认智能优先级链 + 自动 fallback，
> UI/报告只透明展示用了哪个源。详见 `PLAN.md`「数据源策略」。先后端 fallback，再透明展示。

- [x] **D2-a · 后端 fallback 健壮性（空数据/异常 → 自动转源）** ✅ 2026-06-07
  - 实现: `route_to_vendor` 两类触发自动转链中下一个源——① vendor **抛任何异常**（广义捕获+WARNING
    日志：限流/akshare 不可用/AV 无 key 的 ValueError/网络错）② vendor **返回空数据**（`_looks_empty`：
    None/空串/"No ... found" yfinance 占位）。全链空→返回最后一个清晰"无数据"提示（不裸崩）；
    全链异常→抛聚合 RuntimeError（含各源异常，便于排查）。
  - Verify: 合成 vendor 验证四路径（空→转源拿数据 / 异常→转源拿数据 / 全空→提示 / 全异常→聚合抛）；
    `_looks_empty` 契约；A股基本面 happy path 回归走 akshare 真数据不变。
  - Files: `interface.py`

- [x] **D2-b · 透明展示「本次用了哪个源 / 降级了什么」** ✅ 2026-06-07
  - 实现（纵向切片 6 层）: ① `interface.py` threading.local 溯源采集器（`reset/record/get/format_provenance`）
    + `route_to_vendor` 自动记录「类别→命中源 + 降级跳过的源」② `sentiment_analyst.py` 节点体(主线程)按
    `<...>` 占位判定 Reddit/StockTwits 降级并记入「社交情感」③ `api/analyzer.py` propagate 前 reset、后
    `result['data_sources']=format_provenance_summary()`（纯 markdown 表格）④ C# `AnalysisResult.DataSources`
    （SnakeCaseLower 自动映射 data_sources）⑤ `ReportFormatter` 加"数据源溯源"段（存 MD+推送）⑥ UniApp
    报告页加"🔌 数据源"段（htmlMap+SECTION_META，空自动隐藏）。
  - Verify: Python 模拟 600519.SS 跑通——行情/基本面=akshare、个股新闻全链降级显示"无数据/降级跳过
    akshare,AV,yfinance"、社交情感显示"无数据 + Reddit/StockTwits 仅覆盖美股"；C# `dotnet build` 0 错误；
    UniApp 2 行镜像现有 section 模式（需前端构建看渲染）。
  - 限制: 经 ThreadPoolExecutor 子线程的路由（sentiment 并行抓 news）不被 threading.local 采集——但
    news 已由新闻分析员主线程记录，冗余无碍。
  - Files: `interface.py`、`sentiment_analyst.py`、`api/analyzer.py`、`AnalysisDtos.cs`、`ReportFormatter.cs`、`uniapp .../analysis/index.vue`

- [x] **settings 设置页**（阶段二遗留）：推送时间 + LLM 模型选择 ✅ 2026-06-07
  - 实现（全栈）: C# `UserSettings` 实体(单行 Id=1，不存密钥) + DbSet + Program.cs 建表/种子(LLM 默认取
    apikeys active_provider) + `SettingsController`(GET/POST/`GET providers`) + Hangfire 读 DB 设置(HH:MM→cron
    + 启停 + 保存即热更新) + Orchestrator 把持久化 LLM 默认应用到**所有分析(含定时)**(修复定时推送默认用
    DEFAULT_CONFIG/openai)。UniApp `pages/settings/index.vue`(盘前/盘后开关+时间选择器、provider 下拉只列已配 key、
    深/快模型) + api.js + 首页"⚙️设置"入口。
  - Verify: C# `dotnet build` 0 错误 + **运行时冒烟**(建表、种子 llm=xai、GET/POST/providers 往返、POST 热更新
    盘前 09:00/盘后关 已确认)；UniApp `build:h5` DONE；providers 只返回 xai(唯一配 key)；测试后已恢复 DB 默认。
  - 决策: 数据源**不进设置页**（D2 已定纯智能 fallback）；密钥(SendKey/各 LLM key)**不进设置页**，留 apikeys.local.json(密钥铁律)。
  - Files: `Entities.cs`、`AppDbContext.cs`、`AnalysisDtos.cs`、`SettingsController.cs`、`ScheduledAnalysisJob.cs`、
    `AnalysisOrchestrator.cs`、`Program.cs`、`pages.json`、`api.js`、`pages/settings/index.vue`、`pages/index/index.vue`

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
