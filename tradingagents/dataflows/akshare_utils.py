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


def get_akshare_stock_data(symbol: str, start_date: str, end_date: str) -> str:
    """A股/港股历史行情，返回与 yfinance ``get_YFin_data_online`` 相同的 header+CSV 格式。

    走 akshare 的**新浪源**（stock_zh_a_daily / stock_hk_daily），不走东财源——
    东财 push2his API 对爬虫请求反爬（RemoteDisconnected，即便直连大陆 IP），新浪源
    不反爬、列名为英文、港股小众标的（如 07709）也能取到。非 CN 市场直接抛
    AkshareUnavailableError → 路由 fallback 到 yfinance。
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
    df = df[keep]
    csv_string = df.to_csv(index=False)

    header = f"# Stock data for {symbol.upper()} from {start_date} to {end_date}\n"
    header += f"# Total records: {len(df)}\n"
    header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    header += "# Source: akshare(sina)\n\n"
    return header + csv_string
