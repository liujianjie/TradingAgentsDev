"""中文情感面聚合 fetcher（akshare 东财量化情绪指标系列）。

填补 ``sentiment_analyst`` 对 A 股 / 港股"情感面缺失"的窟窿——StockTwits 和 Reddit
是美股社区，对中文市场零覆盖；本模块用东财千股千评（结构化情绪指标，含综合得分 /
机构参与度 / 关注指数 / 市场排名）+ 热度时序 + 热门关键词 + 港股热度作为替代，作为
中文市场 sentiment_analyst 的**预注入数据块**（不走 tool calling）。

四个 fetcher 的约定：

- 成功 → 返回**可注入 prompt 的 markdown 文本块**（已含小节标题）
- 无数据 / 非目标市场 / akshare 失败 → 返回 ``None``（**不抛**），由
  ``sentiment_analyst`` 在主线程组装时替换成占位串、并写入 ``record_provenance`` 降级

这样保持与 ``fetch_reddit_posts`` / ``fetch_stocktwits_messages`` 一致的
graceful-degrade 契约——LLM 永远看到的是字符串，从不抛栈。

数据源选型与可用性验证见 ``docs/spec-sentiment-multi-source.md`` 第 3.1 节
（probe 报告：``reports/sentiment_probe/20260619_235021/report.md``）。
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any

import pandas as pd

from .akshare_utils import (
    AkshareUnavailableError,
    _akshare_retry,
    market_of,
    to_akshare_symbol,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ticker → 东财股票排名接口的 symbol（SH600519 / SZ000001 / 00700）
# ---------------------------------------------------------------------------
def _to_em_rank_symbol(ticker: str) -> str:
    """A 股 ``600519.SS`` → ``SH600519``；港股 ``0700.HK`` → ``00700``（5 位带前导 0）。

    东财热度系列接口（``stock_hot_rank_detail_em`` / ``stock_hot_keyword_em``）的
    symbol 需要交易所前缀（SH/SZ）；港股专用接口
    ``stock_hk_hot_rank_detail_realtime_em`` 用 5 位代码。不同于 akshare 行情/新闻类
    接口用的 ``to_akshare_symbol``，故新增一个专门函数避免歧义。
    """
    t = ticker.strip().upper()
    if t.endswith(".SS"):
        return "SH" + t[:-3]
    if t.endswith(".SZ"):
        return "SZ" + t[:-3]
    if t.endswith(".HK"):
        return t[:-3].zfill(5)
    return t


# ---------------------------------------------------------------------------
# 千股千评全市场快照缓存（5 分钟 TTL）
# ---------------------------------------------------------------------------
# ``stock_comment_em()`` 返回 5000+ 行全市场快照，单次调用 ~10s（probe 实测）。
# 一次分析里 sentiment_analyst 对单 ticker 只抽一行，但同一会话/同一进程可能
# 对多个 ticker 跑分析，全部命中同一张表。故模块级 TTL 缓存把 10s 摊到首次调用，
# 后续 < 0.1s；TTL=5 分钟够覆盖单次会话，且数据每个交易日更新一次（盘后），
# 5 分钟过期不会拿到陈数据但能避免反复打 akshare 触发节流。
_COMMENT_CACHE: dict[str, Any] = {"df": None, "fetched_at": 0.0}
_COMMENT_CACHE_TTL_SEC = 300.0
_COMMENT_CACHE_LOCK = threading.Lock()


def _get_cached_comment_df() -> pd.DataFrame | None:
    """拿全市场千股千评 DataFrame，命中 5 分钟内的 cache 直接返回。失败返回 None。"""
    with _COMMENT_CACHE_LOCK:
        now = time.time()
        if (
            _COMMENT_CACHE["df"] is not None
            and now - _COMMENT_CACHE["fetched_at"] < _COMMENT_CACHE_TTL_SEC
        ):
            return _COMMENT_CACHE["df"]
        try:
            import akshare as ak  # 延迟导入：避免模块加载时拖慢解释器启动
            df = _akshare_retry(lambda: ak.stock_comment_em())
        except AkshareUnavailableError as e:
            logger.warning("千股千评全市场快照取数失败: %s", str(e)[:160])
            return None
        except Exception as e:  # akshare 内部偶发其他异常
            logger.warning("千股千评全市场快照异常: %s: %s", type(e).__name__, str(e)[:160])
            return None
        if df is None or df.empty:
            return None
        _COMMENT_CACHE["df"] = df
        _COMMENT_CACHE["fetched_at"] = now
        return df


def _reset_comment_cache_for_tests() -> None:
    """单元测试用：清缓存。生产路径不调。"""
    with _COMMENT_CACHE_LOCK:
        _COMMENT_CACHE["df"] = None
        _COMMENT_CACHE["fetched_at"] = 0.0


# ---------------------------------------------------------------------------
# fetcher 1: 东财千股千评（A 股核心情感指标）
# ---------------------------------------------------------------------------
def fetch_cn_comment(ticker: str, curr_date: str | None = None) -> str | None:
    """A 股个股的东财千股千评——**结构化量化情感指标**。

    返回字段含「综合得分 / 机构参与度 / 关注指数 / 上升 / 市场排名 / 主力成本」，
    无需 LLM 二次打分，可直接被 sentiment_analyst 的 prompt 解读为情绪雷达。

    防 look-ahead：千股千评接口返回的"交易日"字段是数据所属日，超过 curr_date 当天
    则丢弃（因为这等于把未来盘后的数据漏给历史回测）。

    Args:
        ticker: A 股 ticker（``600519.SS`` / ``000001.SZ``），非 A 股返回 None。
        curr_date: 回测/分析的当前日期 ``YYYY-MM-DD``；为 None 不做日期校验。

    Returns:
        markdown 文本块；非 A 股 / 全市场无该 ticker / akshare 失败 → None。
    """
    if market_of(ticker) != "cn_a":
        return None

    df = _get_cached_comment_df()
    if df is None or df.empty:
        return None

    code = to_akshare_symbol(ticker)  # 600519.SS → 600519
    code_col = next((c for c in df.columns if "代码" in str(c)), None)
    if code_col is None:
        logger.warning("千股千评未找到代码列：%s", list(df.columns)[:10])
        return None

    row = df[df[code_col].astype(str).str.zfill(6) == code]
    if row.empty:
        return None

    # 防 look-ahead：交易日 > curr_date 则丢弃
    if curr_date and "交易日" in row.columns:
        cutoff = pd.to_datetime(curr_date)
        td = pd.to_datetime(row["交易日"], errors="coerce")
        row = row[td.isna() | (td <= cutoff)]
        if row.empty:
            return None

    r = row.iloc[0]
    # 行 → 易读 markdown；部分字段做温和单位提示（机构参与度是 0~1 比例，关注指数百分制）
    def _v(name: str, default: str = "—") -> str:
        v = r.get(name)
        if pd.isna(v):
            return default
        return str(v)

    name = _v("名称", ticker)
    lines = [
        f"## 东财千股千评 — {name}（{ticker.upper()}）",
        f"- 交易日: {_v('交易日')}",
        f"- 综合得分: {_v('综合得分')}（满分 100；越高代表市场综合评价越积极）",
        f"- 机构参与度: {_v('机构参与度')}（0~1，越高代表机构持仓 / 关注比例越大）",
        f"- 关注指数: {_v('关注指数')}（散户关注度，越高代表讨论热度越高）",
        f"- 上升: {_v('上升')}（综合得分较上一交易日的变化值，正=情绪改善）",
        f"- 目前排名: {_v('目前排名')} / 5000+ 只 A 股",
        f"- 最新价: {_v('最新价')} / 涨跌幅: {_v('涨跌幅')}% / 换手率: {_v('换手率')}%",
        f"- 主力成本: {_v('主力成本')}（东财估算的主力建仓均价）",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# fetcher 2: 东财热度时序（A 股 / 港股的排名 + 粉丝结构变化）
# ---------------------------------------------------------------------------
def fetch_cn_hot_trend(ticker: str, curr_date: str | None = None, days: int = 30) -> str | None:
    """A 股个股的东财热度时序（排名 + 新晋/铁杆粉丝比例）。

    用最近 ``days`` 天的排名走势 + 粉丝结构反映"散户关注度的时间趋势"：
    排名持续上升 = 关注度上行；新晋粉丝比例 ↑ = 短线交易热度。

    Returns:
        markdown 块（含趋势摘要）；非 A 股 / akshare 失败 → None。
    """
    if market_of(ticker) != "cn_a":
        return None

    em_sym = _to_em_rank_symbol(ticker)
    try:
        import akshare as ak
        df = _akshare_retry(lambda: ak.stock_hot_rank_detail_em(symbol=em_sym))
    except (AkshareUnavailableError, Exception) as e:
        logger.warning("热度时序取数失败 %s: %s", ticker, str(e)[:160])
        return None
    if df is None or df.empty:
        return None

    return _format_a_hot_trend(df, ticker, curr_date, days)


def _format_a_hot_trend(df: pd.DataFrame, ticker: str, curr_date: str | None, days: int) -> str | None:
    """A 股热度时序 → markdown 摘要。"""
    if "时间" not in df.columns:
        return None
    df = df.copy()
    df["_dt"] = pd.to_datetime(df["时间"], errors="coerce")
    if curr_date:
        df = df[df["_dt"].isna() | (df["_dt"] <= pd.to_datetime(curr_date))]
    df = df.sort_values("_dt", ascending=False).head(days)
    if df.empty:
        return None

    # 趋势摘要：取最早 / 最晚的排名 vs 粉丝结构
    latest, earliest = df.iloc[0], df.iloc[-1]
    rank_latest = latest.get("排名")
    rank_earliest = earliest.get("排名")
    rank_trend = "—"
    if pd.notna(rank_latest) and pd.notna(rank_earliest):
        delta = int(rank_earliest) - int(rank_latest)  # 排名数小=更热门，故 earliest - latest > 0 表示热度上升
        rank_trend = f"{int(rank_earliest)} → {int(rank_latest)}（{'热度上升' if delta > 0 else '热度回落' if delta < 0 else '持平'}，变动 {abs(delta)} 名）"

    new_fans_latest = latest.get("新晋粉丝")
    new_fans_earliest = earliest.get("新晋粉丝")
    fans_trend = "—"
    if pd.notna(new_fans_latest) and pd.notna(new_fans_earliest):
        fans_trend = (
            f"新晋粉丝比 {float(new_fans_earliest):.2%} → {float(new_fans_latest):.2%}"
            f"（高比例 = 短线散户涌入）"
        )

    lines = [
        f"## 东财个股热度时序 — {ticker.upper()}（近 {len(df)} 天，截至 {curr_date or '最新'}）",
        f"- 排名走势: {rank_trend}",
        f"- 粉丝结构: {fans_trend}",
        "",
        "| 时间 | 排名 | 新晋粉丝 | 铁杆粉丝 |",
        "|---|---|---|---|",
    ]
    # 展示首尾 5 行，中间省略——给 LLM 看趋势而不淹没在 366 行里
    head = df.head(5)
    for _, row in head.iterrows():
        dt = row.get("_dt")
        dt_s = dt.strftime("%Y-%m-%d") if pd.notna(dt) else "—"
        rk = row.get("排名")
        nf = row.get("新晋粉丝")
        tf = row.get("铁杆粉丝")
        lines.append(
            f"| {dt_s} | {int(rk) if pd.notna(rk) else '—'} | "
            f"{f'{float(nf):.2%}' if pd.notna(nf) else '—'} | "
            f"{f'{float(tf):.2%}' if pd.notna(tf) else '—'} |"
        )
    if len(df) > 10:
        lines.append("| ... | ... | ... | ... |")
    if len(df) > 5:
        for _, row in df.tail(min(5, len(df) - 5)).iterrows():
            dt = row.get("_dt")
            dt_s = dt.strftime("%Y-%m-%d") if pd.notna(dt) else "—"
            rk = row.get("排名")
            nf = row.get("新晋粉丝")
            tf = row.get("铁杆粉丝")
            lines.append(
                f"| {dt_s} | {int(rk) if pd.notna(rk) else '—'} | "
                f"{f'{float(nf):.2%}' if pd.notna(nf) else '—'} | "
                f"{f'{float(tf):.2%}' if pd.notna(tf) else '—'} |"
            )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# fetcher 3: 东财热门关键词（A 股个股 → 概念板块热度映射）
# ---------------------------------------------------------------------------
def fetch_cn_hot_keyword(ticker: str, curr_date: str | None = None) -> str | None:
    """A 股个股的东财热门关键词——所属概念板块当下的热度排序。

    用于"情绪传导"分析：当个股所属的某一概念板块（如"白酒""新能源车""AI"）当下
    热度极高，意味着板块情绪可能正在拉动个股；若板块冷清，个股的孤立情绪信号更值得关注。

    Returns:
        markdown 块；非 A 股 / akshare 失败 → None。
    """
    if market_of(ticker) != "cn_a":
        return None

    em_sym = _to_em_rank_symbol(ticker)
    try:
        import akshare as ak
        df = _akshare_retry(lambda: ak.stock_hot_keyword_em(symbol=em_sym))
    except (AkshareUnavailableError, Exception) as e:
        logger.warning("热门关键词取数失败 %s: %s", ticker, str(e)[:160])
        return None
    if df is None or df.empty:
        return None

    # 防 look-ahead：时间 > curr_date 则丢弃
    df = df.copy()
    if "时间" in df.columns:
        df["_dt"] = pd.to_datetime(df["时间"], errors="coerce")
        if curr_date:
            cutoff = pd.to_datetime(curr_date) + pd.Timedelta(days=1)
            df = df[df["_dt"].isna() | (df["_dt"] < cutoff)]
        if df.empty:
            return None

    # 按热度降序，最多展示 10 个
    if "热度" in df.columns:
        df = df.sort_values("热度", ascending=False)

    snap_time = ""
    if "时间" in df.columns and not df["时间"].empty:
        snap_time = str(df["时间"].iloc[0])

    lines = [
        f"## 东财所属概念热度 — {ticker.upper()}（{snap_time}）",
        "（热度=该概念板块当前的市场关注度数值，越高代表板块越热）",
        "",
        "| 概念名称 | 概念代码 | 热度 |",
        "|---|---|---|",
    ]
    for _, row in df.head(10).iterrows():
        name = str(row.get("概念名称", "—")).strip()
        code = str(row.get("概念代码", "—")).strip()
        heat = row.get("热度")
        heat_s = f"{int(heat)}" if pd.notna(heat) else "—"
        lines.append(f"| {name} | {code} | {heat_s} |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# fetcher 4: 港股热度时序（分钟级排名）
# ---------------------------------------------------------------------------
def fetch_hk_hot_trend(ticker: str, curr_date: str | None = None) -> str | None:
    """港股个股的东财实时热度排名时序（分钟级）。

    返回当日 / 最近时间段的排名走势，用于判断港股市场对该标的的关注度变化。
    数据粒度细到 10 分钟一档，故主要用于反映"日内 / 短期"情绪而非长期趋势。

    Returns:
        markdown 块；非港股 / akshare 失败 → None。
    """
    if market_of(ticker) != "hk":
        return None

    em_sym = _to_em_rank_symbol(ticker)
    try:
        import akshare as ak
        df = _akshare_retry(lambda: ak.stock_hk_hot_rank_detail_realtime_em(symbol=em_sym))
    except (AkshareUnavailableError, Exception) as e:
        logger.warning("港股热度时序取数失败 %s: %s", ticker, str(e)[:160])
        return None
    if df is None or df.empty:
        return None
    if "时间" not in df.columns or "排名" not in df.columns:
        return None

    df = df.copy()
    df["_dt"] = pd.to_datetime(df["时间"], errors="coerce")
    if curr_date:
        cutoff = pd.to_datetime(curr_date) + pd.Timedelta(days=1)
        df = df[df["_dt"].isna() | (df["_dt"] < cutoff)]
    df = df.sort_values("_dt", ascending=False)
    if df.empty:
        return None

    latest, earliest = df.iloc[0], df.iloc[-1]
    rk_latest = latest.get("排名")
    rk_earliest = earliest.get("排名")
    trend = "—"
    if pd.notna(rk_latest) and pd.notna(rk_earliest):
        delta = int(rk_earliest) - int(rk_latest)
        trend = f"{int(rk_earliest)} → {int(rk_latest)}（{'热度上升' if delta > 0 else '热度回落' if delta < 0 else '持平'}）"

    rk_min = df["排名"].dropna().min()
    rk_max = df["排名"].dropna().max()

    span = f"{earliest['_dt'].strftime('%Y-%m-%d %H:%M')} → {latest['_dt'].strftime('%Y-%m-%d %H:%M')}"
    lines = [
        f"## 港股实时热度时序 — {ticker.upper()}（{span}，{len(df)} 个数据点）",
        f"- 排名走势: {trend}",
        f"- 区间排名: 最热 #{int(rk_min) if pd.notna(rk_min) else '—'} / 最冷 #{int(rk_max) if pd.notna(rk_max) else '—'}",
    ]
    return "\n".join(lines)


__all__ = [
    "fetch_cn_comment",
    "fetch_cn_hot_trend",
    "fetch_cn_hot_keyword",
    "fetch_hk_hot_trend",
]
