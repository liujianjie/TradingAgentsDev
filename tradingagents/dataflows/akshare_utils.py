"""akshare 数据源 — A股/港股最强的免费源（数据来自东财/新浪/腾讯）。

akshare 无需 API key、不限量，A股与港股的行情/财务/中文新闻覆盖远好于 yfinance；
代价是接口依赖网页结构、偶发 ConnectionError/RemoteDisconnected，故每次调用都过
``_akshare_retry`` 重试，耗尽后抛 ``AkshareUnavailableError`` 让路由层 fallback 到
yfinance。

ticker 格式与 yfinance 相反，需各自适配（见 ``to_akshare_symbol``）：
  yfinance: A股 ``600519.SS`` / 港股去前导0补4位 ``7709.HK``
  akshare:  A股纯6位 ``600519`` / 港股5位带前导0 ``07709``
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)

# 东财对高频请求会临时封 IP（表现为 RemoteDisconnected）。akshare 走东财，故对
# 所有 akshare 调用做全局节流，串行化并保证最小间隔——正常分析对单 ticker 的
# akshare 调用本就低频，节流主要防批量/并发分析把 IP 打封。
_AK_MIN_INTERVAL = 1.2  # 秒
_ak_lock = threading.Lock()
_ak_last_call = 0.0


def _throttle():
    """阻塞到距上次 akshare 调用 >= _AK_MIN_INTERVAL，跨线程串行化。"""
    global _ak_last_call
    with _ak_lock:
        wait = _AK_MIN_INTERVAL - (time.time() - _ak_last_call)
        if wait > 0:
            time.sleep(wait)
        _ak_last_call = time.time()


class AkshareUnavailableError(Exception):
    """akshare 取不到数据（重试耗尽 / 非 CN 市场 / 空数据）。

    路由层 catch 它来 fallback 到下一个 vendor（通常 yfinance）。
    """


# ---------------------------------------------------------------------------
# 市场判断 + ticker 格式转换
# ---------------------------------------------------------------------------
def market_of(ticker: str) -> str:
    """返回 ticker 所属市场：'cn_a' / 'hk' / 'other'。akshare 只覆盖 cn_a / hk。"""
    t = ticker.strip().upper()
    if t.endswith(".SS") or t.endswith(".SZ"):
        return "cn_a"
    if t.endswith(".HK"):
        return "hk"
    return "other"


def to_akshare_symbol(ticker: str) -> str:
    """把 yfinance 风格的 ticker 转成 akshare 的代码格式。

    A股: ``600519.SS`` → ``600519``（纯6位，去交易所后缀）
    港股: ``7709.HK`` → ``07709``、``0700.HK`` → ``00700``（去 .HK 后补足5位带前导0）
    """
    t = ticker.strip().upper()
    if t.endswith(".SS") or t.endswith(".SZ"):
        return t[:-3]
    if t.endswith(".HK"):
        return t[:-3].zfill(5)
    return t


def _akshare_retry(func, max_retries: int = 3, base_delay: float = 1.5):
    """执行 akshare 调用，对暂时性网络故障退避重试。

    akshare 走爬虫聚合，偶发 ConnectionError / RemoteDisconnected / 读超时。
    重试通常能成功；耗尽后抛 AkshareUnavailableError 让路由 fallback。
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        _throttle()  # 全局节流，避免高频触发东财封 IP
        try:
            return func()
        except Exception as e:  # akshare 抛的网络异常类型不统一，按消息判断
            last_exc = e
            low = str(e).lower()
            transient = (
                "connection" in low or "timed out" in low or "timeout" in low
                or "remotedisconnected" in low or "max retries" in low
                or "reset" in low or "aborted" in low
            )
            if transient and attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "akshare 暂时性失败，%.0fs 后重试 (%d/%d): %s",
                    delay, attempt + 1, max_retries, str(e)[:80],
                )
                time.sleep(delay)
                continue
            break
    raise AkshareUnavailableError(f"akshare 调用失败: {str(last_exc)[:160]}") from last_exc


# akshare 新浪源行情列名（英文小写）→ 标准 OHLCV 列名
_OHLCV_COL_MAP = {
    "date": "Date",
    "open": "Open",
    "close": "Close",
    "high": "High",
    "low": "Low",
    "volume": "Volume",
    "amount": "Amount",
}


def _fetch_akshare_ohlcv_df(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """A股/港股历史行情 OHLCV DataFrame（列 Date/Open/High/Low/Close/Volume）。

    走 akshare 的**新浪源**（stock_zh_a_daily / stock_hk_daily），不走东财源——
    东财 push2his API 对爬虫请求反爬（RemoteDisconnected，即便直连大陆 IP），新浪源
    不反爬、列名为英文、港股小众标的（如 07709）也能取到。非 CN 市场 / 空数据直接抛
    AkshareUnavailableError → 调用方（行情 / 指标）据此 fallback 到 yfinance。

    供 ``get_akshare_stock_data``（格式化成 CSV）与 ``get_akshare_indicators``
    （喂给 stockstats 算指标）共用，保证行情与指标同源同口径（均为新浪前复权）。
    """
    import akshare as ak

    market = market_of(symbol)
    t = symbol.strip().upper()

    if market == "cn_a":
        # 新浪 A股符号需交易所前缀：600519.SS→sh600519、000001.SZ→sz000001
        sina_sym = ("sh" + t[:-3]) if t.endswith(".SS") else ("sz" + t[:-3])
        df = _akshare_retry(lambda: ak.stock_zh_a_daily(
            symbol=sina_sym,
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="qfq",
        ))
    elif market == "hk":
        # 新浪港股符号为5位带前导0（7709.HK→07709）；该接口返回全部历史，需自行按日期过滤
        hk_sym = t[:-3].zfill(5)
        df = _akshare_retry(lambda: ak.stock_hk_daily(symbol=hk_sym, adjust="qfq"))
        if df is not None and not df.empty and "date" in df.columns:
            df = df.copy()
            df["date"] = pd.to_datetime(df["date"])
            mask = (df["date"] >= pd.to_datetime(start_date)) & (df["date"] <= pd.to_datetime(end_date))
            df = df[mask]
    else:
        raise AkshareUnavailableError(f"akshare 不支持市场 {market}（{symbol}），交给 yfinance")

    if df is None or df.empty:
        raise AkshareUnavailableError(f"akshare 返回空数据: {symbol}")

    # 新浪英文列名 → 标准；保留 OHLCV，顺序对齐 yfinance(Date,Open,High,Low,Close,Volume)
    df = df.rename(columns=_OHLCV_COL_MAP)
    keep = [c for c in ["Date", "Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    return df[keep]


def get_akshare_stock_data(symbol: str, start_date: str, end_date: str) -> str:
    """A股/港股历史行情，返回与 yfinance ``get_YFin_data_online`` 相同的 header+CSV 格式。"""
    df = _fetch_akshare_ohlcv_df(symbol, start_date, end_date)
    csv_string = df.to_csv(index=False)

    header = f"# Stock data for {symbol.upper()} from {start_date} to {end_date}\n"
    header += f"# Total records: {len(df)}\n"
    header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    header += "# Source: akshare(sina)\n\n"
    return header + csv_string


def get_akshare_indicators(
    symbol: str, indicator: str, curr_date: str, look_back_days: int = 30
) -> str:
    """A股/港股技术指标：用 akshare 新浪 OHLCV 喂 stockstats，复用 yfinance 同一套
    指标窗口/描述逻辑（``get_stock_stats_indicators_window``），输出格式完全一致。

    指标本身与 vendor 无关（都是在 OHLCV 上由 stockstats 计算），唯一差异是行情来源；
    故这里只替换 OHLCV fetcher，让 A股/港股指标与行情同源（新浪前复权）、不再依赖
    yfinance 取数（中国大陆 / TUN 下 yfinance OHLCV 偶发失败）。非 CN 市场 / akshare
    取数失败 → AkshareUnavailableError，由路由 fallback 到 yfinance 指标。
    """
    if market_of(symbol) not in ("cn_a", "hk"):
        raise AkshareUnavailableError(f"akshare 指标不支持市场（{symbol}），交给 yfinance")
    # 延迟导入避免与 y_finance 的模块级互引；y_finance 不引用本模块，故无环。
    from .y_finance import get_stock_stats_indicators_window

    return get_stock_stats_indicators_window(
        symbol, indicator, curr_date, look_back_days,
        ohlcv_fetcher=_fetch_akshare_ohlcv_df, ohlcv_tag="akshare",
    )


def get_akshare_news(symbol: str, start_date: str, end_date: str) -> str:
    """A股/港股个股中文新闻（akshare 东财 stock_news_em）。

    填补 yfinance 对 A股/港股个股新闻覆盖几乎为零的缺口——StockTwits/Reddit 是美股社区、
    Yahoo 对中港股个股新闻极少，导致情感面/新闻面对 A股/港股长期"信息真空"。stock_news_em
    对港股（如 07709）与 A股都有中文新闻，且走的东财子域名不同于反爬的 push2his。
    非 CN 市场抛 AkshareUnavailableError → 路由 fallback 到 yfinance。

    stock_news_em 返回"最近"新闻、无日期入参，故按"发布时间"过滤到 <= end_date 当天
    （防回测 look-ahead），取窗口内最近若干条。
    """
    import akshare as ak

    market = market_of(symbol)
    if market not in ("cn_a", "hk"):
        raise AkshareUnavailableError(f"akshare 个股新闻不支持市场 {market}（{symbol}）")

    ak_symbol = to_akshare_symbol(symbol)
    df = _akshare_retry(lambda: ak.stock_news_em(symbol=ak_symbol))
    if df is None or df.empty:
        raise AkshareUnavailableError(f"akshare 无个股新闻: {symbol}")

    # 防 look-ahead：只保留发布时间 <= end_date 当天的新闻，并按时间降序
    if "发布时间" in df.columns:
        df = df.copy()
        df["_dt"] = pd.to_datetime(df["发布时间"], errors="coerce")
        cutoff = pd.to_datetime(end_date) + pd.Timedelta(days=1)
        df = df[df["_dt"].isna() | (df["_dt"] < cutoff)]
        df = df.sort_values("_dt", ascending=False, na_position="last")
    if df.empty:
        raise AkshareUnavailableError(f"akshare 个股新闻均晚于 {end_date}: {symbol}")

    lines = [f"## {symbol.upper()} 个股新闻（akshare/东财，截至 {end_date}）:\n"]
    for _, row in df.head(15).iterrows():
        title = str(row.get("新闻标题", "")).strip()
        content = str(row.get("新闻内容", "")).strip().replace("\n", " ")
        ptime = str(row.get("发布时间", "")).strip()
        src = str(row.get("文章来源", "")).strip()
        link = str(row.get("新闻链接", "")).strip()
        if not title:
            continue
        lines.append(f"### {title}（{src} · {ptime}）")
        if content:
            lines.append(content[:300])
        if link:
            lines.append(f"链接: {link}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 基本面 / 财务报表（A股走新浪不反爬源；港股走东财 em，非 push2his 故可用）
# ---------------------------------------------------------------------------
# 三大报表中文名（新浪与东财 em 的 symbol 入参用同一套中文名）
_REPORT_CN = {
    "balance": "资产负债表",
    "cashflow": "现金流量表",
    "income": "利润表",
}

# 港股财务指标(东财 em)关键字段 → 中文标签，挑选对基本面分析最有用的子集
_HK_INDICATOR_LABELS = {
    "OPERATE_INCOME": "营业收入",
    "OPERATE_INCOME_YOY": "营收同比(%)",
    "GROSS_PROFIT": "毛利",
    "GROSS_PROFIT_RATIO": "毛利率(%)",
    "HOLDER_PROFIT": "股东应占溢利",
    "HOLDER_PROFIT_YOY": "净利同比(%)",
    "NET_PROFIT_RATIO": "净利率(%)",
    "BASIC_EPS": "基本每股收益",
    "DILUTED_EPS": "稀释每股收益",
    "EPS_TTM": "每股收益TTM",
    "BPS": "每股净资产",
    "ROE_AVG": "平均净资产收益率ROE(%)",
    "ROA": "总资产收益率ROA(%)",
    "DEBT_ASSET_RATIO": "资产负债率(%)",
    "CURRENT_RATIO": "流动比率",
    "PER_NETCASH_OPERATE": "每股经营现金流",
    "CURRENCY": "货币单位",
}


def _fmt_num(v) -> str:
    """格式化财务数值：大额转亿/万便于阅读，比率/小数原样保留两位。"""
    try:
        f = float(v)
    except (TypeError, ValueError):
        s = str(v).strip()
        return s if s and s.lower() != "nan" else "—"
    if pd.isna(f):
        return "—"
    a = abs(f)
    if a >= 1e8:
        return f"{f / 1e8:.2f}亿"
    if a >= 1e4:
        return f"{f / 1e4:.2f}万"
    return f"{f:.2f}"


def _select_periods(dates: pd.Series, curr_date: str | None, annual_only: bool, limit: int):
    """从报告期序列里挑出 <= curr_date（防 look-ahead）的、按需仅年报、最近 limit 个。

    返回 (保留行的布尔 mask, 按时间降序排好的报告期 Timestamp 列表)。
    与 yfinance ``filter_financials_by_date`` 同约定：按报告期末过滤。
    """
    dt = pd.to_datetime(dates, errors="coerce")
    mask = dt.notna()
    if curr_date:
        mask &= dt <= pd.Timestamp(curr_date)
    if annual_only:
        mask &= dt.dt.month.eq(12) & dt.dt.day.eq(31)
    kept = dt[mask].sort_values(ascending=False)
    keep_periods = list(kept.head(limit))
    final_mask = mask & dt.isin(keep_periods)
    return final_mask, sorted(set(keep_periods), reverse=True)


def get_akshare_fundamentals(ticker: str, curr_date: str | None = None) -> str:
    """A股/港股基本面概览（A股新浪 stock_financial_abstract；港股东财指标）。

    A股: 财务摘要(常用/盈利/成长/财务风险等指标)取 <= curr_date 最近 3 个报告期对比。
    港股: 东财财务分析指标取最近 2 个报告期对比。非 CN 市场 / 无数据(如 ETP) →
    抛 AkshareUnavailableError 让路由 fallback 到 yfinance。
    """
    import akshare as ak

    market = market_of(ticker)
    ak_symbol = to_akshare_symbol(ticker)

    if market == "cn_a":
        df = _akshare_retry(lambda: ak.stock_financial_abstract(symbol=ak_symbol))
        if df is None or df.empty:
            raise AkshareUnavailableError(f"akshare 无基本面数据: {ticker}")
        date_cols = [c for c in df.columns if str(c).isdigit() and len(str(c)) == 8]
        mask, periods = _select_periods(pd.Series(date_cols), curr_date, annual_only=False, limit=3)
        cols = [str(p.strftime("%Y%m%d")) for p in periods]
        cols = [c for c in cols if c in df.columns]
        if not cols:
            raise AkshareUnavailableError(f"akshare 基本面均晚于 {curr_date}: {ticker}")

        lines = [f"# {ticker.upper()} 基本面概览（akshare/新浪，截至 {curr_date or '最新'}）",
                 f"# 数据获取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                 f"# 报告期: {' | '.join(cols)}（金额单位元，已折算亿/万）\n"]
        for section in df["选项"].unique():
            sub = df[df["选项"] == section]
            lines.append(f"## {section}")
            for _, row in sub.iterrows():
                name = str(row["指标"]).strip()
                vals = " | ".join(_fmt_num(row[c]) for c in cols)
                lines.append(f"- {name}: {vals}")
            lines.append("")
        return "\n".join(lines)

    if market == "hk":
        df = _akshare_retry(
            lambda: ak.stock_financial_hk_analysis_indicator_em(symbol=ak_symbol, indicator="报告期")
        )
        if df is None or df.empty:
            raise AkshareUnavailableError(f"akshare 无港股基本面: {ticker}")
        mask, periods = _select_periods(df["REPORT_DATE"], curr_date, annual_only=False, limit=2)
        df = df[mask].copy()
        if df.empty:
            raise AkshareUnavailableError(f"akshare 港股基本面均晚于 {curr_date}: {ticker}")
        df["_dt"] = pd.to_datetime(df["REPORT_DATE"], errors="coerce")
        df = df.sort_values("_dt", ascending=False)
        col_dates = [d.strftime("%Y-%m-%d") for d in df["_dt"]]

        lines = [f"# {ticker.upper()} 港股基本面概览（akshare/东财，截至 {curr_date or '最新'}）",
                 f"# 数据获取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                 f"# 报告期: {' | '.join(col_dates)}\n"]
        for code, label in _HK_INDICATOR_LABELS.items():
            if code not in df.columns:
                continue
            vals = " | ".join(_fmt_num(v) for v in df[code])
            lines.append(f"- {label}: {vals}")
        return "\n".join(lines)

    raise AkshareUnavailableError(f"akshare 基本面不支持市场 {market}（{ticker}）")


def _get_akshare_report(ticker: str, kind: str, freq: str, curr_date: str | None) -> str:
    """三大报表统一实现：A股走新浪 report、港股走东财 em report，转成行项目×报告期 CSV。

    输出与 yfinance ``get_balance_sheet`` 等同格式（header + CSV，列为报告期降序、
    行为报表科目），便于下游 agent/prompt 跨 vendor 一致解析。
    """
    import akshare as ak

    statement_cn = _REPORT_CN[kind]
    annual_only = str(freq).lower().startswith("annual")
    market = market_of(ticker)
    title = {"balance": "Balance Sheet", "cashflow": "Cash Flow", "income": "Income Statement"}[kind]

    if market == "cn_a":
        t = ticker.strip().upper()
        sina_sym = ("sh" + t[:-3]) if t.endswith(".SS") else ("sz" + t[:-3])
        df = _akshare_retry(lambda: ak.stock_financial_report_sina(stock=sina_sym, symbol=statement_cn))
        if df is None or df.empty or "报告日" not in df.columns:
            raise AkshareUnavailableError(f"akshare 无{statement_cn}: {ticker}")
        mask, _ = _select_periods(df["报告日"], curr_date, annual_only, limit=8)
        df = df[mask].copy()
        if df.empty:
            raise AkshareUnavailableError(f"akshare {statement_cn}均晚于 {curr_date}: {ticker}")
        # 报告期×科目 → 科目×报告期（对齐 yfinance），列按报告期降序
        df["报告日"] = pd.to_datetime(df["报告日"], format="%Y%m%d", errors="coerce")
        df = df.sort_values("报告日", ascending=False).set_index("报告日")
        df.index = df.index.strftime("%Y-%m-%d")
        out = df.T
        out = out.dropna(how="all")  # 去掉该标的全空的科目行（如非银行业的银行专用科目）
        source = "akshare(sina)"
    elif market == "hk":
        ak_symbol = to_akshare_symbol(ticker)
        indicator = "年度" if annual_only else "报告期"
        df = _akshare_retry(
            lambda: ak.stock_financial_hk_report_em(stock=ak_symbol, symbol=statement_cn, indicator=indicator)
        )
        if df is None or df.empty:
            raise AkshareUnavailableError(f"akshare 无港股{statement_cn}: {ticker}")
        item_order = list(dict.fromkeys(df["STD_ITEM_NAME"]))  # 保留首次出现顺序(资产在前)
        out = df.pivot_table(
            index="STD_ITEM_NAME", columns="REPORT_DATE", values="AMOUNT", aggfunc="first"
        ).reindex(item_order)
        out.columns = pd.to_datetime(out.columns, errors="coerce")
        mask, periods = _select_periods(pd.Series(out.columns), curr_date, annual_only, limit=8)
        out = out.loc[:, [c for c in out.columns if c in set(periods)]]
        out = out.reindex(columns=sorted(out.columns, reverse=True))
        if out.empty or out.shape[1] == 0:
            raise AkshareUnavailableError(f"akshare 港股{statement_cn}均晚于 {curr_date}: {ticker}")
        out.columns = [c.strftime("%Y-%m-%d") for c in out.columns]
        out = out.dropna(how="all")
        source = "akshare(eastmoney)"
    else:
        raise AkshareUnavailableError(f"akshare {statement_cn}不支持市场 {market}（{ticker}）")

    csv_string = out.to_csv()
    header = f"# {title} data for {ticker.upper()} ({freq})\n"
    header += f"# Source: {source}（{statement_cn}）\n"
    header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    return header + csv_string


def get_akshare_balance_sheet(ticker: str, freq: str = "quarterly", curr_date: str | None = None) -> str:
    """A股/港股资产负债表（A股新浪、港股东财），格式对齐 yfinance。"""
    return _get_akshare_report(ticker, "balance", freq, curr_date)


def get_akshare_cashflow(ticker: str, freq: str = "quarterly", curr_date: str | None = None) -> str:
    """A股/港股现金流量表（A股新浪、港股东财），格式对齐 yfinance。"""
    return _get_akshare_report(ticker, "cashflow", freq, curr_date)


def get_akshare_income_statement(ticker: str, freq: str = "quarterly", curr_date: str | None = None) -> str:
    """A股/港股利润表（A股新浪、港股东财），格式对齐 yfinance。"""
    return _get_akshare_report(ticker, "income", freq, curr_date)
