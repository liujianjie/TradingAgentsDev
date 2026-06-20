"""Google News RSS 搜索 vendor — A 股 / 港股新闻面的"外部视角"兜底源.

新闻面 fallback 链的中间一档：A 股 / 港股链上当 akshare 失败时，先尝试 Google News
RSS 搜索（不要求 API key，覆盖港媒 + 内地媒体 + 外媒），仍失败再落到 yfinance（对
中港股个股新闻覆盖几乎为零，作为最末位兜底）。

按 ticker 市场自动调整搜索参数：
  * A 股 (cn_a): query="{ticker} 股票"，hl=zh-CN，gl=CN
  * 港股 (hk):   query="{ticker} 港股 stock"，hl=zh-CN，gl=HK（中英双搜——香港媒体含两种）
  * 其他:        query="{ticker} stock"，hl=en，gl=US（route_to_vendor 末位兜底场景）

防 look-ahead：按 RSS item 的 pubDate 严格过滤 ≤ end_date 当天，超过当天的丢弃。
无任何结果 / 网络失败 → 抛 ``GoogleNewsUnavailableError``，让 route_to_vendor 链
fallback 到下一个 vendor。

probe 已在 ``reports/sentiment_probe/20260619_235021/report.md`` 验证：A 股 ~2.7s、
港股 ~2.5s，TUN 全局代理环境下可达（无需为本 vendor 单独配代理）。
"""

from __future__ import annotations

import logging
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Iterable
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

import requests

from .akshare_utils import market_of

logger = logging.getLogger(__name__)


_RSS_URL = "https://news.google.com/rss/search"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_DEFAULT_TIMEOUT_SEC = 8
_DEFAULT_MAX_ITEMS = 15


class GoogleNewsUnavailableError(Exception):
    """Google News RSS 取数失败（网络异常 / 无结果 / 解析异常）。

    route_to_vendor catch 它后 fallback 到链中下一个 vendor（通常 yfinance）。
    """


def _ticker_query_params(ticker: str) -> tuple[str, str, str]:
    """根据 ticker 市场返回 (query, hl, gl)。"""
    mkt = market_of(ticker)
    t = ticker.strip().upper()
    if mkt == "cn_a":
        # 6 位代码搜索效率最高（".SS"/".SZ" 后缀本身在中文新闻里不出现）
        bare = t[:-3] if (t.endswith(".SS") or t.endswith(".SZ")) else t
        return f"{bare} 股票", "zh-CN", "CN"
    if mkt == "hk":
        # 港股代码不带前导 0 用得更多（"0700"/"00700"/"700.HK"/"腾讯"都常见）
        bare = t[:-3].lstrip("0") if t.endswith(".HK") else t
        return f"{bare} 港股 stock", "zh-CN", "HK"
    return f"{t} stock", "en", "US"


def _parse_pubdate(s: str) -> datetime | None:
    """RSS pubDate 是 RFC 822 格式（``Mon, 16 Jun 2026 12:34:00 GMT``）。失败返回 None。"""
    s = (s or "").strip()
    if not s:
        return None
    try:
        return parsedate_to_datetime(s)
    except (TypeError, ValueError):
        return None


def _filter_items_by_end_date(items: Iterable[ET.Element], end_date: str | None) -> list[ET.Element]:
    """按 RSS pubDate 严格过滤 ≤ end_date 当天，防回测 look-ahead。

    end_date 为 None 时不做过滤（即不防穿越，仅 live 分析时这样）。
    """
    if not end_date:
        return list(items)
    try:
        cutoff = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        # end_date 格式异常时不过滤（避免静默丢全部）
        return list(items)
    # cutoff = 当天 23:59:59（pubDate 是 GMT 时区有时区信息；放宽到当天末）
    cutoff_naive_end = cutoff.replace(hour=23, minute=59, second=59)
    kept = []
    for it in items:
        pd_text = (it.findtext("pubDate") or "").strip()
        pd = _parse_pubdate(pd_text)
        if pd is None:
            kept.append(it)  # 无 pubDate 不丢，留给下游 LLM 自行判断
            continue
        # 比较去掉 tz 后的 naive datetime（UTC 的当天结尾 ≈ 北京 +8h，影响极小且偏保守）
        if pd.tzinfo is not None:
            pd = pd.replace(tzinfo=None)
        if pd <= cutoff_naive_end:
            kept.append(it)
    return kept


def get_google_news(
    ticker: str,
    start_date: str,
    end_date: str,
    *,
    max_items: int = _DEFAULT_MAX_ITEMS,
    timeout: int = _DEFAULT_TIMEOUT_SEC,
) -> str:
    """A 股 / 港股 / 美股个股新闻——Google News RSS。

    签名与 ``get_akshare_news`` / ``get_news_yfinance`` 对齐：``(ticker, start_date, end_date)``。
    ``start_date`` 当前不传给 RSS（Google News RSS 不支持开始日期参数；返回的是最近相关），
    但 ``end_date`` 用于防 look-ahead 截尾过滤。
    """
    query, hl, gl = _ticker_query_params(ticker)
    params = {
        "q": query,
        "hl": hl,
        "gl": gl,
        "ceid": f"{gl}:{hl.split('-')[0]}",
    }
    url = f"{_RSS_URL}?{urlencode(params)}"

    try:
        resp = requests.get(url, headers={"User-Agent": _UA}, timeout=timeout)
    except requests.RequestException as e:
        raise GoogleNewsUnavailableError(f"Google News 网络异常: {type(e).__name__}: {str(e)[:160]}") from e

    if resp.status_code != 200:
        raise GoogleNewsUnavailableError(f"Google News HTTP {resp.status_code}")

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as e:
        raise GoogleNewsUnavailableError(f"Google News RSS 解析失败: {e}") from e

    items = root.findall(".//item")
    if not items:
        raise GoogleNewsUnavailableError(f"Google News 无结果（query={query!r}）")

    items = _filter_items_by_end_date(items, end_date)
    if not items:
        raise GoogleNewsUnavailableError(f"Google News 所有结果均晚于 {end_date}（query={query!r}）")

    # 取前 max_items 条
    items = items[:max_items]

    lines = [
        f"## {ticker.upper()} 个股新闻（Google News RSS · query={query!r} · 截至 {end_date}）",
        "",
    ]
    for it in items:
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        pub = (it.findtext("pubDate") or "").strip()
        src_el = it.find("source")
        src = (src_el.text or "").strip() if src_el is not None else ""
        if not title:
            continue
        head = f"### {title}"
        if src:
            head += f"（{src}）"
        lines.append(head)
        if pub:
            lines.append(f"_发布时间: {pub}_")
        # description 含 HTML，先简单去标签——保留纯文本摘要给 LLM
        desc = (it.findtext("description") or "").strip()
        if desc:
            # 朴素去 HTML 标签（Google News RSS 的 description 一般是 "<a ...>title</a> ..."）
            import re
            desc_text = re.sub(r"<[^>]+>", "", desc).strip()
            if desc_text and desc_text.lower() != title.lower():
                lines.append(desc_text[:300])
        if link:
            lines.append(f"链接: {link}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


__all__ = ["get_google_news", "GoogleNewsUnavailableError"]
