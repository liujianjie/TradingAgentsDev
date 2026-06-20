"""A 股特色数据 fetcher（北向资金 / 龙虎榜）—— 基本面分析师的补充输入.

A 股有几类**外部市场没有的**结构化数据，对基本面 / 事件面分析极有价值：

- **北向资金**（沪深港通持股）：境外机构对该股的持仓变化，反映"聪明钱"动向。
  时序数据，可看近期净流入趋势 vs 持仓比例。akshare 直接调
  ``stock_hsgt_individual_em(symbol)`` 拿到个股完整持仓时序。

- **龙虎榜**：游资 / 机构席位的异动买卖，反映短线主力博弈。akshare
  ``stock_lhb_stock_statistic_em(symbol="近一月")`` 给近一月全市场上榜
  统计；按 ticker filter 即可拿到"近一月是否上榜 / 上榜次数 / 累计净买入"。

两个 fetcher 直接调 akshare，不走 ``route_to_vendor``——只有 akshare 这一个 vendor 实现，
路由层会是 over-engineering。失败 / 非 A 股 → 返回**清晰的中文占位串**而不是抛栈，让
LLM 看到一致格式的"无数据"提示，按 prompt 描述应跳过本节而非编造。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pandas as pd

from .akshare_utils import AkshareUnavailableError, _akshare_retry, market_of, to_akshare_symbol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 北向资金（沪深港通持股）
# ---------------------------------------------------------------------------
def get_north_bound_holding(ticker: str, curr_date: str | None = None, days: int = 30) -> str:
    """A 股个股的北向资金持仓时序（沪深港通陆股通持仓）。

    返回近 ``days`` 个交易日的：
    - 当前持股市值 + 持股占 A 股流通比例
    - 区间累计净流入资金 + 区间内增 / 减仓天数
    - 最早 / 最新一日的关键数据对比（趋势）

    Args:
        ticker: A 股 ticker（``600519.SS`` / ``000001.SZ``）。
        curr_date: 当前分析日期 ``YYYY-MM-DD``，用于防 look-ahead；为 None 不过滤。
        days: 取最近多少个交易日窗口（默认 30）。

    Returns:
        markdown 文本块。非 A 股 / akshare 失败 → 清晰占位串（不抛）。
    """
    if market_of(ticker) != "cn_a":
        return f"## 北向资金 — {ticker.upper()}\n\n_n/a: 北向资金（沪深港通）仅覆盖 A 股标的。_"

    ak_sym = to_akshare_symbol(ticker)
    try:
        import akshare as ak
        df = _akshare_retry(lambda: ak.stock_hsgt_individual_em(symbol=ak_sym))
    except (AkshareUnavailableError, Exception) as e:
        logger.warning("北向资金取数失败 %s: %s", ticker, str(e)[:160])
        return (
            f"## 北向资金 — {ticker.upper()}\n\n"
            f"_数据暂不可用（{type(e).__name__}）。该股可能不在沪深港通标的范围。_"
        )

    if df is None or df.empty or "持股日期" not in df.columns:
        return f"## 北向资金 — {ticker.upper()}\n\n_无北向资金持仓记录（该股可能未被纳入沪深港通）。_"

    df = df.copy()
    df["_dt"] = pd.to_datetime(df["持股日期"], errors="coerce")
    if curr_date:
        df = df[df["_dt"].isna() | (df["_dt"] <= pd.to_datetime(curr_date))]
    df = df.sort_values("_dt", ascending=False).head(days)
    if df.empty:
        return f"## 北向资金 — {ticker.upper()}\n\n_截至 {curr_date} 暂无可用持仓数据。_"

    latest = df.iloc[0]
    earliest = df.iloc[-1]

    def _v(row: pd.Series, key: str, default: str = "—") -> str:
        v = row.get(key)
        return default if pd.isna(v) else v

    # 区间累计净流入
    net_sum = df["当日净流入资金"].dropna().sum() if "当日净流入资金" in df.columns else None
    # 增减仓天数（按"当日净流入资金" > 0 / < 0 计）
    inc_days = dec_days = 0
    if "当日净流入资金" in df.columns:
        s = df["当日净流入资金"].dropna()
        inc_days = int((s > 0).sum())
        dec_days = int((s < 0).sum())

    def _fmt_money(v) -> str:
        try:
            f = float(v)
        except (TypeError, ValueError):
            return "—"
        if pd.isna(f):
            return "—"
        a = abs(f)
        if a >= 1e8:
            return f"{f / 1e8:.2f}亿元"
        if a >= 1e4:
            return f"{f / 1e4:.2f}万元"
        return f"{f:.0f}元"

    def _fmt_pct(v) -> str:
        try:
            f = float(v)
            return f"{f:.2f}%"
        except (TypeError, ValueError):
            return "—"

    lines = [
        f"## 北向资金 — {ticker.upper()}（近 {len(df)} 个交易日，截至 {curr_date or '最新'}）",
        "",
        f"- 最新一日（{latest['_dt'].strftime('%Y-%m-%d')}）持股市值: {_fmt_money(latest.get('持股市值'))}；"
        f"占 A 股流通: {_fmt_pct(latest.get('持股数量占A股百分比'))}",
        f"- 区间起始（{earliest['_dt'].strftime('%Y-%m-%d')}）持股市值: {_fmt_money(earliest.get('持股市值'))}；"
        f"占 A 股流通: {_fmt_pct(earliest.get('持股数量占A股百分比'))}",
        f"- 区间累计净流入: {_fmt_money(net_sum)}（增仓 {inc_days} 日 / 减仓 {dec_days} 日）",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# 龙虎榜（近一月统计）
# ---------------------------------------------------------------------------
# 全市场近一月龙虎榜返回 ~850 行（probe 实测），按 ticker 取 1 行——和千股千评类似，
# 多个 ticker 调用同一份数据；这里复用模块级 5 分钟 TTL cache 摊销 ~5s 单次开销。
import threading
import time

_LHB_CACHE: dict[str, Any] = {"df": None, "fetched_at": 0.0, "period": None}
_LHB_CACHE_TTL_SEC = 300.0
_LHB_CACHE_LOCK = threading.Lock()


def _get_cached_lhb_df(period: str) -> pd.DataFrame | None:
    """全市场龙虎榜统计 cache（5 分钟 TTL）。period: ``近一月`` / ``近三月`` / ``近六月`` / ``近一年``。"""
    with _LHB_CACHE_LOCK:
        now = time.time()
        if (
            _LHB_CACHE["df"] is not None
            and _LHB_CACHE["period"] == period
            and now - _LHB_CACHE["fetched_at"] < _LHB_CACHE_TTL_SEC
        ):
            return _LHB_CACHE["df"]
        try:
            import akshare as ak
            df = _akshare_retry(lambda: ak.stock_lhb_stock_statistic_em(symbol=period))
        except (AkshareUnavailableError, Exception) as e:
            logger.warning("龙虎榜全市场快照取数失败 (%s): %s", period, str(e)[:160])
            return None
        if df is None or df.empty:
            return None
        _LHB_CACHE["df"] = df
        _LHB_CACHE["fetched_at"] = now
        _LHB_CACHE["period"] = period
        return df


def _reset_lhb_cache_for_tests() -> None:
    with _LHB_CACHE_LOCK:
        _LHB_CACHE["df"] = None
        _LHB_CACHE["fetched_at"] = 0.0
        _LHB_CACHE["period"] = None


def get_dragon_tiger_list(ticker: str, curr_date: str | None = None, period: str = "近一月") -> str:
    """A 股个股近一月（或指定周期）龙虎榜上榜情况。

    返回：是否上榜、上榜次数、最近上榜日、累计买入 / 卖出 / 净买入额、机构席位数。
    未上榜本身就是有效情绪信号（短线主力博弈较少）。

    Args:
        ticker: A 股 ticker。
        curr_date: 当前分析日期；用于在叙述中显示截至日。akshare 接口本身不支持按日截尾
            （近一月统计是相对接口调用时点），故 ``curr_date`` 仅用于叙述展示，不做截尾过滤。
            （回测场景下应当通过 ``period`` 参数控制窗口，本接口的近期统计不适合远历史回测。）
        period: ``近一月`` / ``近三月`` / ``近六月`` / ``近一年``。

    Returns:
        markdown 文本块。非 A 股 / akshare 失败 → 清晰占位串（不抛）。
    """
    if market_of(ticker) != "cn_a":
        return f"## 龙虎榜 — {ticker.upper()}\n\n_n/a: 龙虎榜仅覆盖 A 股标的。_"

    df = _get_cached_lhb_df(period)
    if df is None or df.empty:
        return f"## 龙虎榜 — {ticker.upper()}\n\n_龙虎榜数据暂不可用（akshare 失败）。_"

    code_col = next((c for c in df.columns if str(c) == "代码"), None)
    if code_col is None:
        return f"## 龙虎榜 — {ticker.upper()}\n\n_龙虎榜列结构异常，跳过。_"

    code = to_akshare_symbol(ticker)
    row = df[df[code_col].astype(str).str.zfill(6) == code]
    if row.empty:
        return (
            f"## 龙虎榜 — {ticker.upper()}（{period}）\n\n"
            f"_{period}内本股未上龙虎榜。短线主力博弈不活跃，可视为中性情绪信号。_"
        )

    r = row.iloc[0]

    def _v(name: str, default: str = "—") -> str:
        v = r.get(name)
        if pd.isna(v):
            return default
        return str(v)

    def _fmt_money(v) -> str:
        try:
            f = float(v)
        except (TypeError, ValueError):
            return "—"
        if pd.isna(f):
            return "—"
        a = abs(f)
        if a >= 1e8:
            return f"{f / 1e8:.2f}亿元"
        if a >= 1e4:
            return f"{f / 1e4:.2f}万元"
        return f"{f:.0f}元"

    lines = [
        f"## 龙虎榜 — {ticker.upper()}（{period}，截至 {curr_date or '最新'}）",
        "",
        f"- 上榜次数: {_v('上榜次数')} 次；最近上榜日: {_v('最近上榜日')}",
        f"- 累计买入: {_fmt_money(r.get('累计买入额'))} / 累计卖出: {_fmt_money(r.get('累计卖出额'))} / "
        f"累计成交: {_fmt_money(r.get('累计成交额'))}",
        f"- 机构席位: 买方 {_v('买方机构数')} 家 / 卖方 {_v('卖方机构数')} 家 / "
        f"机构净买额: {_fmt_money(r.get('机构买入净额'))}",
        f"- 涨跌幅: 近 1 月 {_v('近1月涨跌幅')}% / 近 3 月 {_v('近3月涨跌幅')}% / "
        f"近 6 月 {_v('近6月涨跌幅')}%",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


__all__ = [
    "get_north_bound_holding",
    "get_dragon_tiger_list",
    "_reset_lhb_cache_for_tests",
]
