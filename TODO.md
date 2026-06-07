# TODO

> 最近更新：2026-06-06 | 路线图见 `PLAN.md`

## 🔴 阻塞中

- [ ] **DeepSeek API key 无效（401）** — 当前 `apikeys.local.json` 的 deepseek key
      尾号 ...0979 被 DeepSeek 服务端拒绝（`authentication_error`）。key 结构正常
      （sk- + 32 位），所以是**凭据本身失效**（多半已在平台被重置/删除/欠费）。
      → 需用户去 platform.deepseek.com 确认或重新生成 key，填回 `apikeys.local.json`，
        **然后重启 Python API 服务**（load_apikeys 只在启动时读一次）。
      → 或临时把 `active_provider` 换成其他已配且有效的 provider。

## 🟡 进行中 / 下一步

- [ ] **数据源按市场自动路由 + UI 可选**（用户 2026-06-07 拍板，详见 PLAN.md「数据源策略」）
      akshare 已装（1.18.64），接口已探测可用（A股行情/新闻/财务✓，港股行情✓但偶发 ConnectionError）。

  **阶段 D1 — 后端核心路由（先做，让 A股/港股立刻有真数据）**
  - [ ] `dataflows/akshare_utils.py`：ticker 格式转换 + 市场判断 + akshare 调用重试
        - 市场判断：`.SS/.SZ`→A股、`.HK`→港股、其余→非 CN（akshare 不接）
        - 格式转换：A股 `600519.SS`→`600519`；港股 `7709.HK`→`07709`（补5位带前导0）
        - akshare 重试包装（ConnectionError/RemoteDisconnected → 退避重试，耗尽抛"无数据"）
        - 列名映射：日期→Date 开盘→Open 收盘→Close 最高→High 最低→Low 成交量→Volume 成交额→Amount
  - [ ] akshare vendor 方法（按切片推进，每个验证后再下一个）：
        - [ ] `get_stock_data`（行情）— `stock_zh_a_hist` / `stock_hk_hist`，返回与 yfinance 同格式 header+CSV
        - [ ] `get_indicators`（技术）— 取 OHLCV 后复用 stockstats（同 yfinance 路径）
        - [ ] `get_fundamentals`/`balance`/`cashflow`/`income` — `stock_financial_abstract` 等
        - [ ] `get_news`（个股中文新闻）— `stock_news_em`
  - [ ] 路由 market-aware：`interface.py` 加「按 ticker 后缀判市场 → 选该市场最优 vendor」默认映射
        - [ ] `route_to_vendor` 应用市场路由；扩展 fallback except（akshare 失败/无数据 → 切 yfinance）
        - [ ] 注册 akshare 进 `VENDOR_LIST` / `VENDOR_METHODS`
  - [ ] **不切 CN 源**：`get_global_news`（全球宏观）保持 yfinance/AV，akshare 无此能力
  - [ ] 验证：A股 600519.SS → akshare、港股 07709.HK → akshare、美股 AAPL → yfinance、韩股 000660.KS → yfinance

  **阶段 D2 — UI 数据源选择（随后补）**
  - [ ] 设置页加「数据源」下拉：自动（默认）/ 强制 yfinance / 强制 akshare / 强制 AV
  - [ ] C# 透传 dataSource 参数 → Python `/api/v1/analyze` → analyzer 注入 config 覆盖市场默认

  **D1 进度（2026-06-07）**
  - [x] akshare_utils.py 行情切片 + 市场判断/格式转换/重试/节流（列名映射）
  - [x] interface.py 注册 akshare + market-aware 路由 + fallback 扩展到 AkshareUnavailableError
  - [x] analyzer.py data_vendors → "auto"（触发市场路由）
  - [x] 验证：市场分流 / 路由选择 / fallback 全通过
  - [x] **行情切片端到端实测通过**：akshare 新浪源取 A股(沪 600519/深 000001)+港股(0700/07709)，
        route 在 auto 下命中 akshare(sina)
        - 真因：东财 push2his API 反爬（RemoteDisconnected，直连大陆 IP 也拒）+ 用户 Clash TUN 全局代理绕境外
        - 解法：akshare 行情改走**新浪源** stock_zh_a_daily / stock_hk_daily（不反爬、英文列名、小众港股也有）
  - [ ] 加固：ticker 规范化下沉到 yfinance vendor（当前只在 analyzer 入口，绕过入口会 404）
  - [ ] 下一切片：get_indicators（akshare OHLCV + 复用 stockstats）→ 基本面 → 个股新闻
        （注：基本面/新闻若用 akshare 也要选不反爬的源，别用东财 push2 系列）
  - [可选/低优先] A股加 baostock 作第二层独立 fallback（akshare新浪→baostock→yfinance）；
        baostock 是独立免费 API（非爬虫），但 TUN 下需 Clash 加 baostock.com 直连。新浪已稳，不急。

  **🔖 搁置待翻案：东财数据源（用户 2026-06-07 决定先记录、后续再议，现用新浪翻篇）**
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

- [ ] **settings 设置页**（阶段二遗留）：推送时间配置 + LLM 模型选择

## 🟢 已完成

- [x] 前端「清新金融卡片风」重做（已提交 c6a9088）
- [x] 分析报告在线 Markdown 渲染 marked + mp-html（已提交 c6a9088）
- [x] 数据源切回 yfinance 主力以支持全球+日韩（`api/analyzer.py`，未提交）
- [x] 修复自选股中文名乱码 `?`（DB 直接修，QQQ→纳斯达克100 ETF 等 8 条）

## 📌 已知坑（避免重复踩）

- **akshare 行情走新浪源**（stock_zh_a_daily / stock_hk_daily），**别用东财源**（stock_zh_a_hist/stock_hk_hist）——东财 push2his API 反爬，直连大陆 IP 也 RemoteDisconnected。新浪源不反爬。已加 1.2s 全局节流 + 必须保留 yfinance fallback。
- **用户网络是 Clash Verge TUN 全局代理**（为访问境外 grok）：会把国内数据源（新浪/东财）流量也绕到境外节点导致失败。需在 Clash 让国内域名直连（见 `docs/setup-clash-cn-direct.md`）；调试国内源时可临时关 TUN。
- 自选股**只能通过网页 UI 添加**；用 PowerShell/curl 加中文名会被 ASCII 编码成 `?`（不可逆）。
- 改任何 LLM key / provider 后**必须重启 Python API 服务**才生效。
- `.bat` 必须纯 ASCII（中文搬 `.ps1`）——见全局 CLAUDE.md。
