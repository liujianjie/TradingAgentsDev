"""Sentiment analyst — multi-source sentiment analysis for a target ticker.

Previously named ``social_media_analyst``. Renamed and redesigned because
the old version had a prompt that demanded social-media analysis but the
only tool available was Yahoo Finance news — which led LLMs to fabricate
Reddit/X/StockTwits content under prompt pressure (verified live).

The redesigned agent **pre-fetches** data sources before the LLM is invoked
and injects them into the prompt as structured blocks. Source selection
splits by market:

  * US / 日韩 / 其他   → News (yfinance) + StockTwits + Reddit
  * A 股 (cn_a)        → News (akshare) + 千股千评 + 热度时序 + 所属概念热度
  * 港股 (hk)          → News (akshare) + 港股实时热度时序

Reddit / StockTwits 是美股社区，对中文市场零覆盖；中文路径用东财量化情感指标
（千股千评：综合得分 / 机构参与度 / 关注指数 / 市场排名）+ 热度时序 + 所属概念
板块热度替代，这些都是**结构化数值**，LLM 不需要二次情绪打分，比原本对中文市场
"无社交情感数据"显著提升一个层级。源选型 / 可用性 probe 详见
``docs/spec-sentiment-multi-source.md``。

The agent does not use tool-calling; the data is in the prompt from turn 0.
Output uses the structured-output pattern (json_schema for OpenAI/xAI,
response_schema for Gemini, tool-use for Anthropic), falling back to free-text
generation for providers that lack native support, so the sentiment header
(band + score + confidence) is deterministic across runs and providers
instead of free-form per-model prose.

See: https://github.com/TauricResearch/TradingAgents/issues/557
See: https://github.com/TauricResearch/TradingAgents/issues/796
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.schemas import SentimentReport, render_sentiment_report
from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_language_instruction,
    get_news,
)
from tradingagents.agents.utils.structured import (
    bind_structured,
    invoke_structured_or_freetext,
)
from tradingagents.dataflows.akshare_utils import market_of
from tradingagents.dataflows.chinese_sentiment import (
    fetch_cn_comment,
    fetch_cn_hot_keyword,
    fetch_cn_hot_trend,
    fetch_hk_hot_trend,
)
from tradingagents.dataflows.interface import record_provenance
from tradingagents.dataflows.reddit import fetch_reddit_posts
from tradingagents.dataflows.stocktwits import fetch_stocktwits_messages


def _seven_days_back(trade_date: str) -> str:
    return (datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")


def create_sentiment_analyst(llm):
    """Create a sentiment analyst node for the trading graph.

    The node routes by market: US / 其他 keep the existing 3-source path
    (News + StockTwits + Reddit), A股 / 港股 use the new Chinese aggregator
    (akshare 东财量化情感指标 + 热度时序). All paths share the same
    ``SentimentReport`` schema and structured-output / free-text fallback.
    """
    structured_llm = bind_structured(llm, SentimentReport, "Sentiment Analyst")

    def sentiment_analyst_node(state):
        ticker = state["company_of_interest"]
        end_date = state["trade_date"]
        start_date = _seven_days_back(end_date)
        instrument_context = get_instrument_context_from_state(state)

        mkt = market_of(ticker)
        if mkt == "cn_a":
            system_message = _build_cn_system_message(ticker, start_date, end_date)
        elif mkt == "hk":
            system_message = _build_hk_system_message(ticker, start_date, end_date)
        else:
            system_message = _build_us_system_message(ticker, start_date, end_date)

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    "\n{system_message}\n"
                    "For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(current_date=end_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        # Format the template into a concrete message list so the structured
        # and free-text paths receive the same input. No bind_tools — the
        # data is already in the prompt.
        formatted_messages = prompt.format_messages(messages=state["messages"])

        report_text = invoke_structured_or_freetext(
            structured_llm,
            llm,
            formatted_messages,
            render_sentiment_report,
            "Sentiment Analyst",
        )

        return {
            "messages": [AIMessage(content=report_text)],
            "sentiment_report": report_text,
        }

    return sentiment_analyst_node


# ---------------------------------------------------------------------------
# US (existing path) — News + StockTwits + Reddit
# ---------------------------------------------------------------------------
def _build_us_system_message(ticker: str, start_date: str, end_date: str) -> str:
    """美股 / 其他市场：保持原 3 路并行抓取 + 原 prompt 模板。"""
    # Pre-fetch all three sources in parallel. Each fetcher degrades
    # gracefully and returns a string (no exceptions surface from here),
    # so the LLM always sees something — either real data or a clear
    # placeholder. Parallel because StockTwits / Reddit are overseas sites
    # that are slow (or GFW-blocked) from mainland China — serially they
    # cost ~49s; in parallel the step is bounded by the slowest source.
    with ThreadPoolExecutor(max_workers=3) as pool:
        f_news = pool.submit(get_news.func, ticker, start_date, end_date)
        f_stocktwits = pool.submit(fetch_stocktwits_messages, ticker, 30)
        f_reddit = pool.submit(fetch_reddit_posts, ticker)
        news_block = f_news.result()
        stocktwits_block = f_stocktwits.result()
        reddit_block = f_reddit.result()

    # 记录社交情感源命中/降级（不走 route_to_vendor，故在此主线程手动记入溯源）。
    # 两个 fetcher 对无数据/异常都返回 <...> 占位串（见 reddit/stocktwits 模块），以此判定。
    # Reddit/StockTwits 是美股社区，港股/A股无替代源——透明告知用户而非假装换源找。
    def _ok(block, name):
        return name if block and not block.strip().startswith("<") else None
    st_ok, rd_ok = _ok(stocktwits_block, "StockTwits"), _ok(reddit_block, "Reddit")
    served = [x for x in (st_ok, rd_ok) if x]
    degraded = [n for n, ok in (("StockTwits", st_ok), ("Reddit", rd_ok)) if not ok]
    record_provenance(
        "社交情感",
        "、".join(served) if served else None,
        degraded=degraded,
        note="" if served else "Reddit/StockTwits 仅覆盖美股，本标的无社交情感数据",
    )

    return _render_us_system_message(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        news_block=news_block,
        stocktwits_block=stocktwits_block,
        reddit_block=reddit_block,
    )


# ---------------------------------------------------------------------------
# A 股 (cn_a) — News + 千股千评 + 热度时序 + 所属概念热度
# ---------------------------------------------------------------------------
def _build_cn_system_message(ticker: str, start_date: str, end_date: str) -> str:
    """A 股：并行抓 4 路（news + 千股千评 + 热度时序 + 所属概念热度）+ CN prompt 模板。

    千股千评是核心结构化情绪指标（综合得分 / 机构参与度 / 关注指数 / 市场排名）。
    热度时序反映关注度趋势；所属概念热度反映板块情绪传导；news 是事件/媒体框架。
    每路独立失败 → 占位串注入 prompt + record_provenance 记降级，主流程不被单路拖死。
    """
    with ThreadPoolExecutor(max_workers=4) as pool:
        f_news = pool.submit(get_news.func, ticker, start_date, end_date)
        f_comment = pool.submit(fetch_cn_comment, ticker, end_date)
        f_trend = pool.submit(fetch_cn_hot_trend, ticker, end_date)
        f_keyword = pool.submit(fetch_cn_hot_keyword, ticker, end_date)
        news_block = f_news.result()
        comment_block = f_comment.result()
        trend_block = f_trend.result()
        keyword_block = f_keyword.result()

    # 占位串：fetcher 返回 None → 注入清晰的 unavailable 标记，并溯源降级。
    # （news 走 route_to_vendor 已自动 record_provenance；本路径只需补 3 个中文情感源）
    served, degraded = [], []
    if comment_block:
        served.append("千股千评")
    else:
        degraded.append("千股千评")
        comment_block = "<unavailable: 千股千评>"
    if trend_block:
        served.append("热度时序")
    else:
        degraded.append("热度时序")
        trend_block = "<unavailable: 热度时序>"
    if keyword_block:
        served.append("所属概念热度")
    else:
        degraded.append("所属概念热度")
        keyword_block = "<unavailable: 所属概念热度>"
    record_provenance(
        "中文情感",
        "、".join(served) if served else None,
        degraded=degraded,
        note="" if served else "akshare 东财量化情感指标系列全部不可用",
    )

    return _render_cn_system_message(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        news_block=news_block,
        comment_block=comment_block,
        trend_block=trend_block,
        keyword_block=keyword_block,
    )


# ---------------------------------------------------------------------------
# 港股 (hk) — News + 港股实时热度时序
# ---------------------------------------------------------------------------
def _build_hk_system_message(ticker: str, start_date: str, end_date: str) -> str:
    """港股：并行抓 2 路（news + 港股热度时序）+ HK prompt 模板。

    港股没有 A 股的"千股千评"等价物（东财只对 A 股算综合评分），所以情感面信号弱于
    A 股，主要靠 news（akshare 东财港股新闻覆盖较好）+ 港股实时热度时序。
    Google News 中英双搜在 P2 阶段（新闻面强化）追加进 ``get_news`` 的 route_to_vendor 链。
    """
    with ThreadPoolExecutor(max_workers=2) as pool:
        f_news = pool.submit(get_news.func, ticker, start_date, end_date)
        f_trend = pool.submit(fetch_hk_hot_trend, ticker, end_date)
        news_block = f_news.result()
        trend_block = f_trend.result()

    served, degraded = [], []
    if trend_block:
        served.append("港股热度时序")
    else:
        degraded.append("港股热度时序")
        trend_block = "<unavailable: 港股热度时序>"
    record_provenance(
        "中文情感",
        "、".join(served) if served else None,
        degraded=degraded,
        note="" if served else "港股实时热度时序不可用；港股情感面以新闻为主",
    )

    return _render_hk_system_message(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        news_block=news_block,
        trend_block=trend_block,
    )


# ---------------------------------------------------------------------------
# Prompt renderers
# ---------------------------------------------------------------------------
def _render_us_system_message(
    *,
    ticker: str,
    start_date: str,
    end_date: str,
    news_block: str,
    stocktwits_block: str,
    reddit_block: str,
) -> str:
    """Assemble the US sentiment-analyst system message with structured data blocks."""
    return f"""You are a financial market sentiment analyst. Your task is to produce a comprehensive sentiment report for {ticker} covering the period from {start_date} to {end_date}, drawing on three complementary data sources that have already been collected for you.

## Data sources (pre-fetched, in this prompt)

### News headlines — Yahoo Finance, past 7 days
Institutional framing. Fact-driven, slower-moving signal.

<start_of_news>
{news_block}
<end_of_news>

### StockTwits messages — retail-trader social platform indexed by cashtag
Fast-moving signal. Each message carries a user-labeled sentiment tag (Bullish / Bearish / no-label) plus the message body.

<start_of_stocktwits>
{stocktwits_block}
<end_of_stocktwits>

### Reddit posts — r/wallstreetbets, r/stocks, r/investing (past 7 days)
Community discussion. Engagement signal via upvote score and comment count. Subreddit character matters (r/wallstreetbets is often contrarian/exuberant; r/stocks more measured; r/investing longer-term).

<start_of_reddit>
{reddit_block}
<end_of_reddit>

## How to analyze this data (best practices)

1. **Read the StockTwits Bullish/Bearish ratio as a leading retail-sentiment signal.** A 70/30 bullish/bearish split is moderately bullish; ≥90/10 may indicate over-extension and contrarian risk; 50/50 is uncertainty. Sample size matters — base rates on the actual message count, not percentages alone.

2. **Look for cross-source divergences.** If news framing is bearish but StockTwits is overwhelmingly bullish, that mismatch is itself a signal — it can mean retail is leaning into a thesis the news flow hasn't caught up to (or vice versa, that retail is chasing while institutions are cautious).

3. **Weight Reddit posts by engagement.** A 400-upvote / 200-comment thread reflects community attention; a 3-upvote post is noise. Read the body excerpts for context — the title alone often misleads.

4. **Distinguish opinion from event.** A news headline ("Nvidia announces $500M Corning deal") is an event; a StockTwits post ("buying NVDA, this is going to moon") is opinion. Both are inputs but should be weighted differently in your conclusions.

5. **Identify recurring narrative themes.** What topic keeps coming up across sources? That's the dominant narrative driving current sentiment.

6. **Be honest about data limits.** If StockTwits returned only a handful of messages, or one or more sources returned an "<unavailable>" placeholder, the sentiment read is less robust — flag this explicitly in the `confidence` field and the narrative. If the sources are silent on a given subreddit, say so.

7. **Identify catalysts and risks** that emerge across sources — news of upcoming earnings, product launches, competitive threats, macro headlines, etc.

8. **Past sentiment is not predictive.** Frame your conclusions as signal for the trader to weigh alongside fundamentals and technicals, not as a price call.

## Output fields

Fill the following fields:

- **overall_band**: Exactly one of Bullish / Mildly Bullish / Neutral / Mixed / Mildly Bearish / Bearish. Use Mixed when sources point in clearly different directions; Neutral only when all sources are genuinely silent.
- **overall_score**: A number from 0 (maximally bearish) to 10 (maximally bullish); 5 is neutral. Keep it consistent with overall_band.
- **confidence**: low / medium / high, based on data quality and sample size.
- **narrative**: Full source-by-source breakdown, divergences, dominant narrative themes, catalysts and risks, and a markdown summary table of key sentiment signals (direction, source, supporting evidence).

{get_language_instruction()}"""


def _render_cn_system_message(
    *,
    ticker: str,
    start_date: str,
    end_date: str,
    news_block: str,
    comment_block: str,
    trend_block: str,
    keyword_block: str,
) -> str:
    """A 股 sentiment prompt：突出"东财千股千评是结构化量化情感指标，无需二次打分"。"""
    return f"""You are a financial market sentiment analyst specialised in the Chinese A-share market. Produce a comprehensive sentiment report for {ticker} covering {start_date} to {end_date}, drawing on the four complementary data sources that have already been collected for you.

## 数据源（已预抓，注入在本 prompt 中）

### 1. 个股新闻 — akshare 东财（past 7 days）
机构与媒体框架。事件驱动、变化较慢的信号。

<start_of_news>
{news_block}
<end_of_news>

### 2. 东财千股千评 — 结构化情感指标（核心）
**这是东财对该股的量化情感雷达**，每个交易日盘后更新：
- **综合得分（0-100）**：东财对个股近期市场综合评价的打分；> 70 偏正面，50-70 中性，< 50 偏负面。
- **机构参与度（0-1）**：机构资金持仓/关注比例；越高代表机构资金涉入越深。
- **关注指数（0-100）**：散户讨论 / 浏览热度；越高代表市场情绪关注度越高。
- **上升**：综合得分较上日的变化；正值代表情绪改善，负值代表情绪转差。
- **目前排名**：在 5000+ A 股中的综合得分排名；前 500 名属于市场情绪最积极的群体。

<start_of_em_comment>
{comment_block}
<end_of_em_comment>

### 3. 东财热度时序 — 关注度趋势（30 天）
排名变化 + 新晋粉丝 / 铁杆粉丝比例。新晋粉丝比例上升 = 短线散户涌入；排名持续下降 = 关注度上行。

<start_of_hot_trend>
{trend_block}
<end_of_hot_trend>

### 4. 所属概念板块热度 — 板块情绪传导
个股所属概念板块（如"白酒""新能源车""AI"）当下的市场热度。板块热度高且方向积极时，往往带动个股情绪；板块冷清时，个股的独立情绪信号更值得关注。

<start_of_concept_heat>
{keyword_block}
<end_of_concept_heat>

## 分析方法（A 股情景下的最佳实践）

1. **优先读千股千评的"综合得分 + 上升"**：这是东财算好的量化情感分。
   - 综合得分 > 70 + 上升 > 0：明确偏多。
   - 综合得分 < 50 + 上升 < 0：明确偏空。
   - 综合得分 50-70 + 上升 ≈ 0：中性。
   - 综合得分高但上升为负：可能见顶回落（先扬后抑），是潜在反转信号。
2. **机构参与度与关注指数的组合**：机构高 + 散户低 = 机构控盘行情；机构低 + 散户高 = 散户行情（易拉升后回落）；机构高 + 散户高 = 共识强烈。
3. **热度时序的趋势**：排名持续上升（数字变小）代表关注度上行；新晋粉丝比例突然飙高代表短线情绪发酵，警惕短期过热。
4. **板块情绪传导**：若个股的"上升"为负但所属板块热度持续走高，常意味着板块轮动还在 → 短期情绪可能反转向上；反之板块冷清而个股独立走强，要小心可持续性。
5. **新闻 vs 量化情感的背离**：新闻偏空但综合得分上升，常意味着负面消息已被市场消化；新闻偏多但综合得分下降，可能是利好兑现。
6. **诚实标注数据缺失**：任何源返回 ``<unavailable>`` 占位串时，在 ``confidence`` 字段和叙述中明确指出可信度下降。
7. **A 股特殊提醒**：A 股散户占比高、政策面影响显著（监管 / 利好政策 / 板块限制），叙述中应特别提醒结构性风险与政策事件（如有）。
8. **过去情感不是预测**：把结论框定为"供交易员与基本面/技术面综合权衡的信号"，不要做价格点位预测。

## 输出字段

Fill the following fields:

- **overall_band**: Exactly one of Bullish / Mildly Bullish / Neutral / Mixed / Mildly Bearish / Bearish. 当综合得分上升与新闻或板块信号背离时使用 Mixed；只有当所有源都真正缄默时才用 Neutral。
- **overall_score**: 0 (maximally bearish) – 10 (maximally bullish)；与综合得分大致对齐：综合得分 70 → score ≈ 7。
- **confidence**: low / medium / high，依据千股千评是否取到 + 几路源齐备程度。
- **narrative**: 按 1) 千股千评结构化解读 → 2) 热度趋势 → 3) 板块情绪 → 4) 新闻事件 → 5) 跨源背离与综合判断 → 6) markdown 总览表 的顺序展开。

{get_language_instruction()}"""


def _render_hk_system_message(
    *,
    ticker: str,
    start_date: str,
    end_date: str,
    news_block: str,
    trend_block: str,
) -> str:
    """港股 sentiment prompt：说明港股情感面信号弱于 A 股、以新闻 + 热度时序为主。"""
    return f"""You are a financial market sentiment analyst specialised in the Hong Kong equity market. Produce a comprehensive sentiment report for {ticker} covering {start_date} to {end_date}, drawing on the two complementary data sources that have already been collected for you.

## 数据源（已预抓，注入在本 prompt 中）

### 1. 个股新闻 — akshare 东财（past 7 days）
机构与媒体框架，含港股中文媒体覆盖。事件驱动信号。

<start_of_news>
{news_block}
<end_of_news>

### 2. 港股实时热度时序 — 分钟级排名
东财港股热门榜的分钟级排名时序，反映当日 / 近段时间市场对该标的的关注度变化。
排名持续下降（数字变小）= 关注度上升；剧烈波动 = 情绪发酵。

<start_of_hk_hot_trend>
{trend_block}
<end_of_hk_hot_trend>

## 分析方法（港股情景下的最佳实践）

1. **港股情感面信号本身弱于 A 股**：没有 A 股"千股千评"那样的官方综合评分；本任务以新闻框架 + 关注度趋势为主线，叙述中明确这一事实，避免过度自信。
2. **新闻面权重**：港股个股新闻覆盖虽然不如 A 股密集，但东财港股新闻仍能反映内地视角；重点识别业绩公告、监管动作、行业政策、内地南下资金动向等催化剂。
3. **热度时序的解读**：港股市场（尤其细分中小盘）流动性差异大；排名稳定在前列代表持续关注，突发上升常对应事件驱动（业绩发布 / 重大公告）。
4. **南北资金视角**：港股的内地资金（沪深港通南下）情绪与外资情绪可能背离；新闻里如有"南向资金净买入"等线索，应单独提示。
5. **诚实标注数据缺失**：返回 ``<unavailable>`` 占位串时显式说明，并在 ``confidence`` 字段下调。
6. **过去情感不是预测**：把结论框定为"信号"而非价格点位。

## 输出字段

Fill the following fields:

- **overall_band**: Exactly one of Bullish / Mildly Bullish / Neutral / Mixed / Mildly Bearish / Bearish.
- **overall_score**: 0 – 10。
- **confidence**: low / medium / high；港股情感面源较少，多数情况建议 low / medium。
- **narrative**: 按 1) 新闻事件框架 → 2) 热度时序解读 → 3) 综合判断 → 4) markdown 总览表 的顺序展开。

{get_language_instruction()}"""


# ---------------------------------------------------------------------------
# Backwards-compatibility shim
# ---------------------------------------------------------------------------
def create_social_media_analyst(llm):
    """Deprecated alias for :func:`create_sentiment_analyst`.

    Kept so existing code that imports ``create_social_media_analyst``
    continues to work.

    .. deprecated::
        Import :func:`create_sentiment_analyst` directly instead.
    """
    import warnings
    warnings.warn(
        "create_social_media_analyst is deprecated and will be removed in a "
        "future version. Use create_sentiment_analyst instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return create_sentiment_analyst(llm)
