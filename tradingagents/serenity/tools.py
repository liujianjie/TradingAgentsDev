"""Serenity 工作流的 LangChain Tool 集合（6 个）。

设计取舍：
- web_search 走 Google News RSS（已知能穿 TUN 全局代理），不引入 Tavily/SerpAPI 依赖
- filings_us 走 SEC EDGAR 公开 full-text search API（``efts.sec.gov``），无需 key、无第三方包
- filings_cn 走 akshare ``stock_notice_report``（与 ``akshare_cn_features`` 同一 retry 模式）
- compute_bottleneck_score 包内联的 ``scorecard.score`` 函数
- get_dragon_tiger_list / get_north_bound_holding 直接 re-export ``cn_features_tools``,
  让 LLM 看到一致命名

所有 tool 失败一律返回**清晰中文占位串**（"[xxx 失败] ..."），不抛栈打断 agent loop——
这与 ``akshare_cn_features`` 的"返回 n/a 占位串"约定一致。
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Annotated, Optional
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

import requests
from langchain_core.tools import tool

from tradingagents.agents.utils.cn_features_tools import (
    get_dragon_tiger_list,
    get_north_bound_holding,
)

from .scorecard import score as _scorecard_score

logger = logging.getLogger(__name__)

_UA_BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
# SEC 官方要求 UA 含可联系邮箱（https://www.sec.gov/os/accessing-edgar-data）。
# 优先从 env 取联系人；未配置时降级到 placeholder——可能被风控限流，部署前应 set SEC_UA_EMAIL。
_UA_SEC = (
    f"serenity-skill/1.0 "
    f"(contact: {os.environ.get('SEC_UA_EMAIL', 'admin@example.local')})"
)
_TIMEOUT = 10


@tool
def web_search(
    query: Annotated[str, "搜索词；中文 query 自动用 zh-CN/CN，英文 query 用 en/US"],
    lang: Annotated[str, "'zh' 或 'en'，默认 'zh'"] = "zh",
    max_items: Annotated[int, "返回前 N 条，默认 10，最大 20"] = 10,
) -> str:
    """通用 Web 搜索（Google News RSS）。

    用途：查公司动向、行业新闻、媒体报道、市场分析、产业链趋势。
    结果按发布时间倒序，含标题 / 来源 / 时间 / 链接 / 摘要。
    成本：单次 ≈ 2-3 秒，TUN 全局代理可达。
    """
    max_items = max(1, min(20, max_items))
    hl = "zh-CN" if lang == "zh" else "en"
    gl = "CN" if lang == "zh" else "US"
    params = {"q": query, "hl": hl, "gl": gl, "ceid": f"{gl}:{hl.split('-')[0]}"}
    url = f"https://news.google.com/rss/search?{urlencode(params)}"
    try:
        resp = requests.get(url, headers={"User-Agent": _UA_BROWSER}, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return f"[web_search 失败] HTTP {resp.status_code} query={query!r}"
        root = ET.fromstring(resp.text)
    except Exception as e:
        return f"[web_search 失败] {type(e).__name__}: {str(e)[:160]}"

    items = root.findall(".//item")[:max_items]
    if not items:
        return f"[web_search 无结果] query={query!r}"

    lines = [f"## Web 搜索结果（query={query!r}, lang={lang}）", ""]
    for it in items:
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        pub = (it.findtext("pubDate") or "").strip()
        src_el = it.find("source")
        src = (src_el.text or "").strip() if src_el is not None else ""
        if not title:
            continue
        head = f"- **{title}**"
        if src:
            head += f" — {src}"
        if pub:
            head += f" — {pub}"
        lines.append(head)
        if link:
            lines.append(f"  {link}")
    return "\n".join(lines)


@tool
def get_filings_cn(
    ticker: Annotated[str, "A 股 ticker，如 '600519.SS' / '000001.SZ' / 裸 6 位 '600519'"],
    keywords: Annotated[
        Optional[str], "可选空格分隔关键词过滤标题，如 '产能 扩产 募投'"
    ] = None,
    days_back: Annotated[int, "回溯天数，默认 30，最大 180"] = 30,
) -> str:
    """A 股个股近期公告 / 临时公告。

    覆盖：年报 / 半年报 / 季报 / 重大事项 / 关联交易 / 增发 / 问询函回复 / 投资者关系。
    数据源：akshare → 巨潮 / 东财 / 交易所披露。非 A 股 ticker 返回 n/a 占位串。
    """
    from tradingagents.dataflows.akshare_utils import market_of

    days_back = max(1, min(180, days_back))
    if market_of(ticker) != "cn_a":
        return f"[get_filings_cn n/a] ticker={ticker} 非 A 股；本工具仅支持 A 股公告"

    bare = ticker.upper().replace(".SS", "").replace(".SZ", "").replace(".SH", "")
    try:
        import akshare as ak

        date_str = datetime.now().strftime("%Y%m%d")
        try:
            df = ak.stock_notice_report(symbol="全部", date=date_str)
        except TypeError:
            df = ak.stock_notice_report()
        if df is None or df.empty:
            return f"[get_filings_cn 无数据] ticker={ticker} date={date_str}"

        cols = df.columns.tolist()
        sym_col = next(
            (c for c in cols if "代码" in c or "symbol" in c.lower() or "code" in c.lower()),
            None,
        )
        if sym_col:
            # 精确匹配避免 "600519" 误命中 "1600519" / "600519X" 等同号段邻股
            df = df[df[sym_col].astype(str) == bare]

        if keywords:
            title_col = next(
                (c for c in cols if "标题" in c or "title" in c.lower() or "公告" in c),
                None,
            )
            if title_col:
                for kw in keywords.split():
                    df = df[df[title_col].astype(str).str.contains(kw, na=False)]

        if df.empty:
            return (
                f"[get_filings_cn 过滤后无数据] ticker={ticker} keywords={keywords}; "
                "可能近期无对应主题公告（不代表公司无活动，仅说明今日全市场公告池中无匹配）"
            )

        n = min(20, len(df))
        return (
            f"## A 股公告（{ticker} · 近期 {n} 条）\n\n"
            "```\n" + df.head(n).to_string(index=False) + "\n```\n"
        )
    except Exception as e:
        return f"[get_filings_cn 失败] {type(e).__name__}: {str(e)[:200]}"


@tool
def get_filings_us(
    ticker_or_query: Annotated[str, "美股 ticker (如 'NVDA') 或自然语言 query"],
    forms: Annotated[str, "filing 类型逗号分隔，默认 '10-K,10-Q,8-K'"] = "10-K,10-Q,8-K",
    max_items: Annotated[int, "返回前 N 条，默认 10，最大 25"] = 10,
) -> str:
    """美股 SEC EDGAR filings 全文搜索（公开 API，无需 key）。

    覆盖 10-K / 10-Q / 8-K / S-1 / proxy 等所有美股公开 filings。
    用途：查公司风险因素、客户集中度、收入分拆、产能扩张、增发披露。
    数据源：``efts.sec.gov/LATEST/search-index`` 官方 full-text search。
    """
    max_items = max(1, min(25, max_items))
    params = {"q": ticker_or_query, "forms": forms}
    url = f"https://efts.sec.gov/LATEST/search-index?{urlencode(params)}"
    try:
        resp = requests.get(
            url, headers={"User-Agent": _UA_SEC, "Accept": "application/json"}, timeout=_TIMEOUT
        )
        if resp.status_code != 200:
            return f"[get_filings_us 失败] HTTP {resp.status_code} q={ticker_or_query}"
        data = resp.json()
    except Exception as e:
        return f"[get_filings_us 失败] {type(e).__name__}: {str(e)[:200]}"

    hits = (data.get("hits") or {}).get("hits") or []
    if not hits:
        return f"[get_filings_us 无结果] q={ticker_or_query} forms={forms}"

    lines = [f"## SEC EDGAR 搜索（q={ticker_or_query!r}, forms={forms}）", ""]
    for h in hits[:max_items]:
        src = h.get("_source") or {}
        form = src.get("form", "")
        display_names = src.get("display_names") or []
        display = display_names[0] if display_names else ""
        date = src.get("file_date", "")
        adsh = (h.get("_id") or "").split(":")[0]
        line = f"- **{form}** — {display} — {date}"
        if adsh:
            adsh_clean = adsh.replace("-", "")
            line += f" — https://www.sec.gov/Archives/edgar/data/{src.get('ciks', [''])[0]}/{adsh_clean}/{adsh}-index.htm"
        lines.append(line)
    return "\n".join(lines)


@tool
def compute_bottleneck_score(
    payload_json: Annotated[
        str,
        "JSON 字符串，含 ticker/company/market/factors/penalties，详见 docstring",
    ],
) -> str:
    """对单家公司算 Serenity 卡点评分（0-100，越高越值得优先研究）。

    payload_json 必填字段：
    - ticker, company, market
    - factors（每项 0-5）: demand_inflection / architecture_coupling / chokepoint_severity /
      supplier_concentration / expansion_difficulty / evidence_quality /
      valuation_disconnect / catalyst_timing
    - penalties（每项 0-5）: dilution_financing / governance / geopolitics / liquidity /
      hype_risk / accounting_quality / cyclicality / alternative_design_risk

    返回 JSON：{ticker, final_score, verdict, raw_factor_points, penalty_points}
    verdict ∈ {"Top research priority", "High research priority", "Worth tracking", "Early lead or low priority"}
    """
    try:
        data = json.loads(payload_json) if isinstance(payload_json, str) else payload_json
        if not isinstance(data, dict):
            return "[compute_bottleneck_score 失败] payload 必须是 JSON 对象"
        result, _ = _scorecard_score(data)
        out = {
            "ticker": result.get("ticker", ""),
            "company": result.get("company", ""),
            "final_score": result["final_score"],
            "verdict": result["verdict"],
            "raw_factor_points": result["raw_factor_points"],
            "penalty_points": result["penalty_points"],
        }
        return json.dumps(out, ensure_ascii=False)
    except ValueError as e:
        return f"[compute_bottleneck_score 校验失败] {e}"
    except Exception as e:
        return f"[compute_bottleneck_score 失败] {type(e).__name__}: {str(e)[:200]}"


SERENITY_TOOLS = [
    web_search,
    get_filings_cn,
    get_filings_us,
    get_dragon_tiger_list,
    get_north_bound_holding,
    compute_bottleneck_score,
]


__all__ = [
    "web_search",
    "get_filings_cn",
    "get_filings_us",
    "compute_bottleneck_score",
    "get_dragon_tiger_list",
    "get_north_bound_holding",
    "SERENITY_TOOLS",
]
