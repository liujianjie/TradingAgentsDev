# Spec — A股 / 港股情感面多源聚合

状态：**Draft**（2026-06-20）
作者：liujianjie + Claude
范围：sentiment_analyst 按市场分流 + 中文聚合器 + 新闻面强化 + A股特色数据
关联：`PLAN.md` 阶段 1（推送）；`docs/spec-trading-platform.md`

---

## 1. 背景与痛点

当前 `sentiment_analyst` 对 A股 / 港股**直接降级到"无社交情感数据"**：
StockTwits 和 Reddit 是美股社区，对 A股 / 港股零覆盖。新闻面虽有 akshare
东财作 fallback，但仅 1 路单点。

参考项目 **TradingAgents-CN** 的对应实现是 TODO 占位 —— `get_stock_sentiment_unified`
在 A股 / 港股分支直接返回写死字符串「整体情绪：中性 / 待分析」，注释承认
"完整的中文社交媒体情绪分析功能正在开发中"（`agent_utils.py:1320-1344`）。
**没有实现可抄**，故走自研路线。

本 spec 主线：用 **akshare 东财量化情绪指标** 替代 StockTwits / Reddit 在
sentiment_analyst 中的位置，并补齐 A股 / 港股新闻面与特色数据。

---

## 2. 目标 / 非目标

### 2.1 目标

- A股 / 港股 sentiment_analyst 输出的 `overall_band` / `overall_score` / `confidence`
  与美股一样有真实数据支撑，不再永远 Neutral。
- A股 / 港股新闻面从单源（akshare 东财）扩展到 2 源（+ Google News 中文/英文）。
- 接入 A股特色数据（北向资金 / 龙虎榜 / 公告）作为基本面 / 事件面补充。
- 美股链路**不变**（StockTwits + Reddit + Yahoo News 保留）。
- 所有失败 / 降级走 `record_provenance` 透明展示，不静默吞错。

### 2.2 非目标

- 不接 **小红书 / 抖音**：反爬维护成本高 + 内容质量边缘 + 法律风险。
- 不接 **雪球 / 富途**：保留 `BaseSentimentSource` 扩展点供 Phase 2，不在本 spec 实施。
- 不引入 OpenAI WebSearch / 任何付费 LLM 联网搜索：等真需要再加。
- 不引入 tushare：`PLAN.md` 已否决（积分制 / 偏 A股 / 无日韩）。
- 不重构 `route_to_vendor` 既有架构：只**扩展**新闻链 fallback，不替换。

---

## 3. 设计

### 3.1 数据源（已 probe 验证可用，2026-06-19）

| 源 | 接口 | 市场 | 数据形态 | probe 耗时 |
|---|---|---|---|---|
| 东财个股新闻 | `ak.stock_news_em` | A / HK | 文本 | 0.1s |
| **东财千股千评** | `ak.stock_comment_em` | A | **结构化指标**（综合得分/机构参与度/关注指数/排名） | 10s（全市场快照，cache） |
| 东财热度时序 | `ak.stock_hot_rank_detail_em` | A | 366d 时序（新晋粉丝/铁杆粉丝/排名） | 1.2s |
| 东财热门关键词 | `ak.stock_hot_keyword_em` | A | 个股→概念板块热度映射 | 0.6s |
| Google News 中文 | `news.google.com/rss/search?hl=zh-CN` | A | RSS 文本 | 2.7s |
| 港股热度时序 | `ak.stock_hk_hot_rank_detail_realtime_em` | HK | 分钟级排名时序 | 1.7s |
| Google News 中英 | `news.google.com/rss/search?hl=zh-CN` | HK | RSS 文本 | 2.5s |

probe 报告位置：`reports/sentiment_probe/20260619_235021/report.md`

### 3.2 架构

```
sentiment_analyst (现有)
    │
    ├── market = market_of(ticker)
    │       │
    │       ├── "other" (US/日韩/...) → 现有路径不变
    │       │       └── ThreadPool[news, stocktwits, reddit] → 注入 prompt(US)
    │       │
    │       ├── "cn_a" (A股) → 新中文聚合路径
    │       │       └── ThreadPool[
    │       │             cn_news,            # akshare stock_news_em (复用现有)
    │       │             cn_comment,         # akshare stock_comment_em (新)
    │       │             cn_hot_trend,       # akshare stock_hot_rank_detail_em (新)
    │       │             cn_google_news,     # Google News RSS hl=zh-CN (新)
    │       │           ] → 注入 prompt(CN)
    │       │
    │       └── "hk" (港股) → 新港股聚合路径
    │               └── ThreadPool[
    │                     hk_news,            # akshare stock_news_em (复用)
    │                     hk_hot_trend,       # akshare stock_hk_hot_rank_detail_realtime_em
    │                     hk_google_news,     # Google News RSS hl=zh-CN
    │                   ] → 注入 prompt(HK)
    │
    ├── 每源 record_provenance (单独溯源)
    └── invoke_structured_or_freetext → SentimentReport (现有 schema，不变)
```

**关键决策**：

1. **不引入工具调用层**：现有 sentiment_analyst 用"预注入 prompt"模式，新中文路径沿用，避免架构分裂。
2. **不改 `SentimentReport` schema**：A股 / 港股 / 美股共用同一输出契约，下游不变。
3. **市场分流在 analyst 内部完成**：`market_of(ticker)` 已是项目共识工具
   （`akshare_utils.py:52`），无需新建 utility。
4. **千股千评单次全市场 cache**：10s 耗时是因为返回 5184 行全市场表，按 ticker 抽行；
   运行期对单 ticker 调用 cache 5 分钟（同一分析 session 内多 ticker 复用）。
5. **每源独立超时**：每个 fetcher 内部 `try/except` + 8s timeout，失败返回 `None`，
   主线程不被单源拖死。

### 3.3 新增模块

**`tradingagents/dataflows/chinese_sentiment.py`** —— 中文情感聚合器：

```python
def fetch_cn_comment(ticker: str, curr_date: str) -> str | None:
    """东财千股千评行（含综合得分/机构参与度/关注指数/排名）。失败返回 None。"""

def fetch_cn_hot_trend(ticker: str, curr_date: str, days: int = 30) -> str | None:
    """东财热度时序（30 天排名 / 粉丝结构变化）。"""

def fetch_cn_hot_keyword(ticker: str, curr_date: str) -> str | None:
    """东财热门关键词（概念板块热度映射）—— 作为 prompt 增强，不进 fallback 链。"""

def fetch_hk_hot_trend(ticker: str, curr_date: str) -> str | None:
    """港股分钟级热度排名时序。"""
```

**`tradingagents/dataflows/google_news.py`** —— 新增（不依赖 akshare）：

```python
def fetch_google_news_rss(query: str, hl: str = "zh-CN", gl: str = "CN",
                          end_date: str, max_items: int = 15) -> str | None:
    """RSS 搜索 + 日期过滤（防 look-ahead）。"""
```

### 3.4 复用与兼容

- `route_to_vendor` 现有链不动；中文新闻面的 Google News 作为**新增 fallback**
  追加到 A股 / 港股的 vendor 链尾：
  - A股: `akshare → google_news_zh_cn → yfinance`（兜底，几乎无数据）
  - 港股: `akshare → google_news_zh_cn → yfinance`
  - 美股: `yfinance → alpha_vantage` （不变）
- sentiment_analyst 现有美股路径完全保留。

### 3.5 prompt 模板

按市场分支构造 system message（共 3 个变种：US 现有 + A股新 + 港股新），
共用同一份"输出字段说明"段。CN / HK 变种文案要求 LLM 重点解读：

- 千股千评的「综合得分 / 机构参与度 / 关注指数 / 排名 vs 全市场」
- 热度时序的「排名趋势 / 粉丝结构变化」
- 热门关键词的「所属概念板块当下热度」
- 东财新闻 + Google News 的「事件 vs 情绪倾向」
- 数据稀疏时的 confidence 标注

### 3.6 A股特色数据（Phase 3）

新增 `dataflows/akshare_cn_features.py`：

| 数据 | 接口 | 接入位置 |
|---|---|---|
| 北向资金（沪深港通持股变化） | `ak.stock_hsgt_*` | 增强 fundamentals_analyst 的 prompt 数据块 |
| 龙虎榜 | `ak.stock_lhb_detail_em` | 同上 |
| 公告 | 已含在 `stock_news_em` 中 | 不重复接 |

**Phase 3 不进 sentiment**，进基本面 / 事件面。是否拆出独立 `event_analyst` 留到 Phase 3 实施时再决定（spec 留口子）。

---

## 4. 任务拆解（按 incremental-implementation 切片）

> 每个任务都是一个可独立 ship 的薄切片，依次累积。每片完成后跑 `python -m tradingagents.graph.cli` 对 1 个 A股 + 1 个港股做端到端冒烟测试。

### Phase 1 — 中文情感聚合器（情感面）

| # | 任务 | 验收 |
|---|---|---|
| P1-1 | 新增 `dataflows/chinese_sentiment.py`，实现 `fetch_cn_comment` | unit test：贵州茅台返回字符串含"综合得分" |
| P1-2 | `fetch_cn_hot_trend` + `fetch_cn_hot_keyword` + `fetch_hk_hot_trend` | unit test：每个函数对真实 ticker 返回非空字符串 |
| P1-3 | sentiment_analyst 按市场分流：A股路径 + CN prompt 模板 | 跑 `600519.SS`，`SentimentReport` 非 Neutral 默认 |
| P1-4 | 港股路径 + HK prompt 模板 | 跑 `0700.HK`，同上 |
| P1-5 | 溯源 record_provenance 适配（每源独立条目） | 跑测试，最终报告含"千股千评 / 热度时序 / Google News"溯源行 |

### Phase 2 — 新闻面强化

| # | 任务 | 验收 |
|---|---|---|
| P2-1 | 新增 `dataflows/google_news.py`：RSS 搜索 + 日期过滤 | unit test：返回 ≥5 条带 pubDate 的新闻 |
| P2-2 | `get_news` 的 route_to_vendor 链追加 Google News（A股 / 港股链） | 模拟 akshare 失败，自动 fallback 到 Google News |
| P2-3 | 端到端：禁用 akshare 后 news_analyst 仍能产出 A股 / 港股新闻报告 | 报告非空、溯源显示"google_news_zh_cn" |

### Phase 3 — A股特色数据（基本面/事件面）

| # | 任务 | 验收 |
|---|---|---|
| P3-1 | 新增 `dataflows/akshare_cn_features.py`：北向资金 / 龙虎榜 | unit test：返回结构化 DataFrame |
| P3-2 | 决策点：进 `fundamentals_analyst` prompt 还是新建 `event_analyst` | 写一段 design note 在本 spec 第 6 节 |
| P3-3 | 接入选定 analyst，prompt 模板更新 | 端到端跑通，报告含"北向资金 N 日累计净流入"等量化结论 |

### 扩展点（不实施）

P-Future：定义 `BaseSentimentSource` 协议（fetch / name / market 三件套），将
chinese_sentiment.py 现有 4 个函数包装成 Source 实例。后续雪球 / 富途加入时只需
实现新 Source 类、注册到 sentiment_analyst 即可。**不在 Phase 1-3 内实施**，
等真要接雪球时再做协议提取（YAGNI）。

---

## 5. 验证策略

### 5.1 单元

- 每个 fetcher 函数单测：mock akshare / requests，断言返回字符串结构。
- 千股千评全市场快照 cache 单测：连续两次调用，第二次 < 0.1s。

### 5.2 集成（端到端冒烟）

- `python -m tradingagents.graph.cli` 跑 `600519.SS` + `0700.HK` + `AAPL` 各一遍：
  - 美股报告与 baseline diff（应无变化）
  - A股 / 港股 sentiment_report 含真实数据（band ≠ 默认 Neutral）
  - 溯源表完整无静默失败

### 5.3 性能基线

- A股 sentiment_analyst 完整一次调用 P95 < 15s（千股千评 10s + 其余并行）
- 千股千评 cache 命中后 < 1s

### 5.4 回归

- **源探活**：`scripts/probe_sentiment_sources.py`——每次 akshare 升级 / 反爬规则可能变时跑一遍，对比哪些源失效。
- **新闻面 E2E 业务回归**：`scripts/verify_news_e2e.py`——跑 11 个真实 ticker × ``route_to_vendor('get_news', ...)`` + 兜底/极端场景。每次改 `VENDOR_METHODS["get_news"]` 或 vendor 链顺序后必跑。**2026-06-20 验证：11/11 正常 + 4/4 兜底 + 1/1 极端，总失败 0。**

### 5.5 当某 ticker 新闻面"全空"时的处理协议（4 层）

| 层 | 触发 | 行为 |
|---|---|---|
| L1 | 主源（A/HK akshare、US yfinance）拿到数据 | 直接返回，命中记溯源 |
| L2 | 主源异常 / 空数据 | 自动 fallback → google_news（A/HK 链）/ alpha_vantage（US 链）；命中记溯源 + 降级前序源 |
| L3 | 上一层仍失败 | 继续 fallback 到最末位（A/HK 落 yfinance、US 落 google_news）；命中记溯源 + 降级全链 |
| L4 | **全链异常或全链空数据** | <ul><li>**全链异常** → 抛 `RuntimeError`（聚合所有源异常），让上游分析 fail 而不是静默继续</li><li>**全链空数据** → 返回末位源的清晰"无数据"提示（如 yfinance 的 "No news found for ..."），溯源记 served_by=None + degraded=全链，sentiment_analyst 的 prompt 模板把这段当作 `<unavailable>` 处理，按 § 3.5 prompt 指引 LLM 把 `confidence` 降到 low 并在 narrative 里说明数据稀疏，**不允许 LLM 编造新闻**</li></ul> |

不增加更多兜底源的判断依据：当前 3 主 + 1 副（akshare/google_news/yfinance/alpha_vantage）已能覆盖正常 + akshare 反爬 + Google 网络抖动三种常见失败；再加 OpenAI WebSearch / Bing News 等收益不大且引入新依赖，**等真有 ticker 持续掉到 L4 再补**（已有 verify_news_e2e 可定期跑发现这种情况）。

---

## 6. 风险与开放问题

| 风险 | 缓解 |
|---|---|
| akshare 接口字段名变更 | probe 脚本作回归基线；fetcher 内显式 schema 校验+ degrade |
| 千股千评 10s 拖慢首次调用 | 全市场 cache，5 分钟 TTL，session 内只付一次 |
| Google News 在 TUN 全局代理下访问波动 | `record_provenance` 标记"google_news 失败"不影响主流程 |
| TradingPlatform 后端是否消费新增字段 | sentiment_report 仍是字符串，无 schema 变更 → 后端无需改 |

**开放问题**（Phase 3 时定）：
- 北向资金 / 龙虎榜放在 fundamentals_analyst prompt 还是新建 event_analyst？倾向前者（避免 graph 复杂度），实施时再敲。

---

## 7. memory 指针

本设计决策记在仓库 `docs/spec-sentiment-multi-source.md`（本文件）。
auto-memory `MEMORY.md` 只留一行索引：
`- [情感面多源聚合 spec](docs/spec-sentiment-multi-source.md) — 中文情感聚合器架构 + 任务拆解`
