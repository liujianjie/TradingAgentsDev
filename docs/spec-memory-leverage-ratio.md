# Spec：存储板块杠杆率（Memory-sector leverage ratio）

> 状态：v1 已批准
> 分支：`codex/memory-leverage-ratio`
> 日期：2026-07-16

## 1. 目标与假设

在现有 TradingAgentsDev 中增加一个只读量化工具，用公开日线行情复刻截图里的“存储杠杆率”，帮助研究者观察单股杠杆产品的成交热度相对正股成交热度是否异常放大。

以下默认方案已于 2026-07-16 review 通过：

1. 功能落在 Python FastAPI + UniApp H5/小程序前端，不接入 LLM，也不改变现有 TradingAgents/Serenity 工作流。
2. v1 使用项目已经依赖的 `yfinance==1.4.1` 拉取 Yahoo Finance 日线 OHLCV 和外汇日线，不新增付费数据源或 API Key。
3. v1 是研究工具，不保证达到 Bloomberg/交易所付费数据的逐笔完整性；返回每个代码的覆盖状态和缺失警告，不把不完整结果伪装成精确值。
4. 独立页面从“产业链研究”页进入，提供时间窗口、全球/仅韩股口径、趋势图、最新日拆分和公式说明。
5. API 与现有 Python API 保持 `snake_case` 字段风格，不另造一套 camelCase 契约。

## 2. 指标定义

对公司（或公司+口径）在交易日 `t`：

```text
turnover_usd(i,t)
  = unadjusted_close(i,t) * volume(i,t) * quote_unit(i) * fx_to_usd(currency(i),t)

leverage_ratio(t)
  = sum(turnover_usd(leveraged_product,t))
    / sum(turnover_usd(common_share_or_adr_or_gdr,t))

leverage_weighted_ratio(t)
  = sum(abs(leverage_multiple) * turnover_usd(leveraged_product,t))
    / sum(turnover_usd(common_share_or_adr_or_gdr,t))
```

- `leverage_ratio` 对应截图的主指标，分子使用杠杆 ETF/ETN/ETP 的**实际美元成交额**，不先乘杠杆倍数。
- `leverage_weighted_ratio` 对应截图的 `lev-wtd`，界面统一显示为“杠杆倍数折算比”，分子按 `abs(±2x/±3x)` 加权。
- `long_turnover_usd` 和 `short_turnover_usd` 按产品杠杆倍数正负拆分。
- `change_1d` 是最新两个有效主板交易日的 `leverage_ratio` 之差，不是百分比变化。
- ADR/GDR 的价格和成交量按其自身证券直接计算美元成交额，不换算为等价普通股股数，因为指标比较的是各证券实际成交金额。
- Kioxia 在产品注册表中没有杠杆腿；只要正股分母有效，其比率返回 `0`，而不是缺失值。

### 2.1 交易日对齐

- 每组以普通股主上市地的交易日为锚点。
- 只计入同一日实际存在的证券日线，不跨日沿用成交额。
- 休市或数据缺失的腿在该日不计入，并写入 `coverage`/`warnings`。
- 最新日必须有主上市普通股的有效收盘价和成交量；否则回退到上一个有效主板交易日。

### 2.2 数据防污染规则

- 价格必须有限且 `> 0`，成交量必须有限且 `>= 0`，汇率必须有限且 `> 0`。
- 主上市腿若在已有至少 5 个历史观测后，单日美元成交额低于前 20 个主板交易日中位数的 1%，视为行情供应商尚未补全的残缺日线；该日不作为比率锚点，避免临时成交量制造假尖峰。
- 第三方响应缺列、空表、异常数值或单个代码失败时，该代码标记为 `missing`，其余代码继续计算。
- 分母为 `0` 或缺失时不生成该日 point，绝不返回无穷大。
- 使用未复权收盘价；拆股日由价格与成交量自身的同日口径相乘，避免把复权价与真实成交量混用。

## 3. v1 产品注册表

产品清单与计算引擎分离。每条记录至少包含：`symbol`、`company_id`、`role`、`scope`、`currency`、`leverage_multiple`、`quote_unit`、`venue`、`source_url`。

### 3.1 正股 / ADR / GDR

| 公司 | 主上市腿 | 全球额外腿 |
|---|---|---|
| SanDisk | `SNDK` | — |
| Micron | `MU` | — |
| SK hynix | `000660.KS` | `SKHY` ADR |
| Samsung Electronics | `005930.KS` | `SMSN.IL` GDR |
| Kioxia | `285A.T` | — |

### 3.2 杠杆产品

| 公司 | 仅韩股腿 | 全球额外腿 |
|---|---|---|
| SanDisk | — | `SNXX` +2x、`SNDU` +2x、`SNDG` +2x、`SNDQ` -2x |
| Micron | — | `MUU` +2x、`MULL` +2x、`MU2.L` +2x、`MUD` -1x |
| SK hynix | `0193T0.KS`、`0195S0.KS`、`0197W0.KS`、`0194T0.KS`、`0192L0.KS`、`0198D0.KS`、`0194R0.KS`（均 +2x），`0197X0.KS`（-2x） | `7709.HK` +2x、`HNX3.L` +3x、`SKHL` +2x、`SKHX` +2x、`SKUU` +2x、`SKDD` -2x |
| Samsung Electronics | `0193W0.KS`、`0195R0.KS`、`0194M0.KS`、`0192M0.KS`、`0193K0.KS`、`0194N0.KS`、`0198B0.KS`（均 +2x），`0193L0.KS`（-2x） | `7747.HK` +2x、`7347.HK` -2x、`SMG3.L` +3x |
| Kioxia | — | — |

说明：`SKHL/SKHX/SKUU/SKDD` 在截图日期 2026-07-10 之后才开始交易；注册表保留它们，以便当前日期后的结果自动纳入，历史点不会回填。

## 4. 数据来源与依据

### 4.1 行情

- 运行时：Yahoo Finance 的公开日线接口，经项目已有 `yfinance 1.4.1` 调用。
- 批量下载：`yf.download(..., interval="1d", auto_adjust=False, repair=False, threads=False)`；`repair=True` 在当前 yfinance 会额外依赖项目未安装的 SciPy，因此按“不新增依赖”约束关闭，改由本模块的价格/成交量/汇率有限值校验防污染。官方参数文档：<https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html>。
- 外汇：同一接口拉取 `KRW=X`、`JPY=X`、`HKD=X`、`EURUSD=X`、`GBPUSD=X` 等日线；注册表中的行情币种决定换算方向。
- 使用限制：yfinance 官方明确其 Yahoo 接口面向研究/教育及个人使用，部署或再分发前应再次核对数据许可：<https://ranaroussi.github.io/yfinance/index.html>。

### 4.2 产品身份与杠杆倍数

- 韩国 2026-05-27 上市的 16 只三星电子/SK hynix 单股 ±2x ETF，以 KRX/管理人资料为产品身份依据；KODEX 汇总说明：<https://www.samsungfund.com/etf/insight/newsroom/view.do?seq=76433>。
- SK hynix KRX 产品示例与代码：KODEX `0193T0` <https://www.samsungfund.com/etf/product/view.do?id=2ETFV6>；RISE `0192L0` <https://eng.riseetf.co.kr/prod/finderDetail/44K6>；SOL -2x `0197X0` <https://www.soletf.com/ko/fund/etf/211114>。
- Micron `MUU/MUD` 的 +2x/-1x 目标：<https://www.direxion.com/product/daily-mu-bull-and-bear-leveraged-single-stock-etfs>。
- SanDisk `SNDG` 的 +2x 目标：<https://leverageshares.com/us/etfs/leverage-shares-2x-long-sndk-daily-etf/>。
- SK hynix `SKHL` 的 +2x 目标及其跟踪 `SKHY` ADR：<https://www.direxion.com/press-release/direxion-launches-skhl-2x-daily-exposure-to-sk-hynix>。
- 欧洲 SK hynix `HNX3` 与 Samsung `SMG3` 的 +3x 法律文件：<https://leverageshares.com/documents/ft/3x_hnx3_ft_cbi.pdf>、<https://leverageshares.com/documents/factsheet/3x_smg3_factsheet.pdf>。

## 5. 技术栈与项目结构

- Python `>=3.10`、pandas `>=2.3.0`、yfinance `>=1.4.1`、FastAPI（现有 `api` 依赖）。
- Vue `3.4.21`、UniApp alpha `3.0.0-alpha-5010220260529001`、Vite `5.2.8`。
- 不新增 npm/Python 依赖。

```text
tradingagents/quant/
  memory_leverage.py              # 纯计算、注册表、行情 provider
api/
  quant.py                        # GET API，输入边界和短 TTL 缓存
tests/
  test_memory_leverage.py         # 纯计算 RED/GREEN 单测
  test_quant_api.py               # FastAPI 契约/错误语义
uniapp-frontend/src/pages/quant/
  memory-leverage.vue             # 趋势图、过滤器、当日拆分
docs/
  spec-memory-leverage-ratio.md   # 本文件
```

## 6. API 契约

### `GET /api/v1/quant/memory-leverage-ratios`

查询参数：

- `days`：自然日回看窗口，整数，`30..730`，默认 `220`。
- `refresh`：是否绕过新鲜的内存/磁盘缓存并重新拉取行情，布尔值，默认 `false`。

成功响应固定为：

```json
{
  "generated_at": "2026-07-16T10:00:00Z",
  "as_of": "2026-07-15",
  "methodology": {
    "ratio": "leveraged_product_turnover_usd / underlying_turnover_usd",
    "weighted_ratio": "abs(leverage_multiple) weighted numerator / underlying_turnover_usd",
    "data_source": "Yahoo Finance via yfinance",
    "registry_version": "2026-07-16"
  },
  "series": [
    {
      "id": "sk_hynix_all",
      "company_id": "sk_hynix",
      "company_name": "SK hynix",
      "scope": "all",
      "latest": {
        "date": "2026-07-15",
        "ratio": 0.0,
        "change_1d": 0.0,
        "long_turnover_usd": 0.0,
        "short_turnover_usd": 0.0,
        "leverage_weighted_ratio": 0.0,
        "underlying_turnover_usd": 0.0
      },
      "points": [
        {
          "date": "2026-07-15",
          "ratio": 0.0,
          "change_1d": 0.0,
          "long_turnover_usd": 0.0,
          "short_turnover_usd": 0.0,
          "leverage_weighted_ratio": 0.0,
          "underlying_turnover_usd": 0.0
        }
      ]
    }
  ],
  "coverage": [
    {
      "symbol": "0193T0.KS",
      "role": "leveraged",
      "status": "ok",
      "last_date": "2026-07-15"
    }
  ],
  "warnings": [],
  "cache": {
    "layer": "live",
    "is_stale": false,
    "ttl_seconds": 900
  }
}
```

- 输出顺序稳定：SanDisk、Micron、SK hynix(all)、SK hynix(KR)、Samsung(all)、Samsung(KR)、Kioxia。
- 单个代码缺失仍返回 `200`，并通过 `coverage`/`warnings` 暴露；所有主上市腿均失败时返回现有 FastAPI 风格的 `502 {"detail": "..."}`，不暴露堆栈或第三方原始响应。
- `points` 与 `latest` 使用同一组完整日指标，前端回看历史交易日时无需再次请求。
- 缓存 TTL 为 15 分钟：先查进程内缓存，再查位于 `data_cache_dir/memory-leverage` 的版本化 JSON 磁盘缓存；磁盘缓存可跨 API 重启复用。
- 行情源失败但存在历史磁盘缓存时返回 `200`、`cache.layer=stale_disk`、`cache.is_stale=true`，并在 `warnings` 明示缓存回退；没有任何可用缓存时才返回 `502`。

## 7. 前端契约

- 页面标题“存储杠杆率”，副标题明确“杠杆产品成交额 ÷ 正股/ADR/GDR 成交额”。
- 用户可见指标全部使用中文名称；最新读数卡展示杠杆产品总成交额、正向/反向构成与占比、正股成交额、杠杆倍数折算比和行情可用产品数量。
- 页面底部提供“指标怎么读”、具体算例以及“成交额不等于净流入/持仓/公司财务杠杆”的提示。
- 页面一次请求 730 日数据；30/90/365/730 日窗口只在本地裁剪趋势图，默认 365 日，切换窗口不会重复拉取行情。
- 提供最近 8 个共同交易日的快照按钮，前三项显示“最新 / 前1交易日 / 前2交易日”；切换后卡片展示对应交易日的完整成交额、方向构成和折算比。
- 顶部展示数据生成时间与“实时拉取 / 内存缓存 / 本地缓存 / 过期缓存”状态；过期缓存必须显示醒目提示。
- “全球 / 仅韩股”切换仅影响 SK hynix 与 Samsung；SanDisk、Micron、Kioxia 始终显示。
- 使用 UniApp `canvas` 绘制折线，不引入 ECharts；数据更新后重新绘制。
- 同时用文字标签显示每条线的名称和最新值，不能仅靠颜色区分。
- 趋势图支持鼠标点击、按住左右拖动和触摸横向拖动；十字线吸附到最近的真实交易日，浮层显示该日全部序列的杠杆率，缺失值明确显示为“—”。
- 图表容器可键盘聚焦，左右方向键按真实交易日切换，`Esc` 清除当前选择；选择日期时画布同步绘制日期标记和各序列数据点。
- 必须包含 skeleton、错误态、空态、刷新按钮和“仅供研究，不构成交易建议”。
- 页面移动优先，验证 320、768、1024、1440 px 宽度；交互按钮可键盘聚焦。

Vue `onMounted` 用于首屏请求，canvas 仅在组件挂载后创建；依据：<https://vuejs.org/api/composition-api-lifecycle>、<https://uniapp.dcloud.net.cn/api/canvas/createCanvasContext>。

## 8. 命令、代码风格与测试策略

```text
后端单测：python -m pytest tests/test_memory_leverage.py tests/test_quant_api.py -q
全量单测：python -m pytest -q
前端构建：npm run build:h5（工作目录 uniapp-frontend）
前端审计：npm audit --omit=dev（工作目录 uniapp-frontend）
本地 API：python -m uvicorn api.main:app --host 127.0.0.1 --port 28100
本地 H5：npm run dev:h5 -- --host 127.0.0.1（工作目录 uniapp-frontend）
```

代码风格沿用仓库：Python 类型标注 + 小型纯函数；Vue `<script setup>` + Composition API；不引入通用抽象框架。

测试分层：

1. 小型单测：用手工构造 pandas 日线验证 USD 成交额、长短拆分、杠杆加权、KR/all、0 分母、缺失腿、FX。
2. API 测试：替换 provider，不访问网络；验证参数边界、稳定响应顺序、部分失败 200、全失败 502。
3. 真实行情 smoke：不纳入默认 pytest；手动验证全部注册代码至少部分返回数据。
4. 浏览器验证：H5 页面无 console error，API 请求 200，趋势图和错误态可见，检查移动/桌面宽度与可访问名称。

## 9. 实施任务

- [ ] T1：提交本 spec 和功能分支
  - 验收：用户确认假设、公式、v1 落点和免费数据源限制。
- [ ] T2：RED——纯计算与 API 契约测试先失败
  - 验收：失败原因是模块/行为尚未实现，而不是测试自身错误。
- [ ] T3：GREEN——注册表、yfinance provider、计算引擎
  - 验收：纯计算测试通过，真实行情 smoke 能生成至少一个系列。
- [ ] T4：GREEN——FastAPI 路由与缓存
  - 验收：API 契约测试通过，OpenAPI 中出现新 GET 路由。
- [ ] T5：UniApp 页面与入口
  - 验收：前端构建通过，浏览器看见趋势、明细、方法说明和各状态。
- [ ] T6：全量验证、密钥扫描和文档收尾
  - 验收：全量测试/构建通过；diff 无明文密钥；说明已知数据覆盖差异。

## 10. 边界

### 始终做

- 对 API 查询参数和所有第三方行情字段做边界校验。
- 在响应中公开产品覆盖与缺失情况。
- 先写失败测试，再写实现；每个可运行增量独立提交。

### 需先确认

- 改为付费/商用行情源、增加 API Key、引入数据库持久化。
- 新增依赖、改变现有 CORS、修改现有分析接口。
- 把该指标用于自动交易、仓位或买卖信号。

### 绝不做

- 硬编码密钥、提交 `.env`、记录第三方响应中的敏感内容。
- 用前端计算替代后端口径，或在数据不完整时静默返回“完整”结果。
- 把该指标表述为因果证明或交易建议。

## 11. 成功标准

1. 免费公开行情下可生成截图同口径的 7 条序列及最新拆分。
2. 2026-05-27 前韩国单股杠杆产品成交额为 0，上市后进入计算；SKHY ADR 从其真实上市日才进入分母。
3. `ratio = (long + short) / underlying`、`weighted_ratio`、`change_1d` 均由确定性测试证明。
4. 任一非主腿失效不会拖垮全部结果，用户能看见覆盖警告。
5. H5 页面在移动端和桌面端可用，构建与浏览器验证通过。
6. 不影响现有 `/api/v1/analyze`、`/api/v1/serenity/*` 与已有测试。

## 12. Review 结论

1. v1 使用 Yahoo/yfinance 免费研究数据，不接 Bloomberg/交易所付费源。
2. 独立页面从“产业链研究”页进入，不占用底部 Tab。
3. 全球口径按当前可验证注册表 best-effort 聚合，并把覆盖差异显式展示。
