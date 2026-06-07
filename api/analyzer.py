import uuid
import asyncio
import re
import sys
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from .models import JobStatus

_executor = ThreadPoolExecutor(max_workers=2)
_jobs: Dict[str, dict] = {}


def _normalize_ticker(ticker: str) -> str:
    """规范化股票代码以匹配 Yahoo Finance 的格式约定。

    目前只处理港股。港交所主板代码是 5 位（带前导 0，如 07709 = XL二南方海力士、
    00700 = 腾讯），但 Yahoo Finance 用「去前导 0 后补足 4 位」的格式：
    07709 → 7709、00700 → 0700、09988 → 9988。用户按券商/港交所习惯输入 5 位代码
    （07709.HK）会让 yfinance 404——代码真实存在，只是格式不符 Yahoo 约定。

    其他市场不动：美股无后缀、A股 .SS/.SZ 六位、韩股 .KS 六位都保持原样。
    """
    t = ticker.strip()
    m = re.match(r"^(\d+)\.(HK|hk)$", t)
    if m:
        code = (m.group(1).lstrip("0") or "0").zfill(4)
        return f"{code}.HK"
    return t


def _precheck_ticker(ticker: str) -> Optional[str]:
    """开跑前快速校验 ticker 在数据源是否有行情。有效返回 None，否则返回中文错误信息。

    传入的 ticker 已经过 _normalize_ticker 规范化（港股前导 0 已处理）。若此处仍
    取不到数据，说明 Yahoo Finance 确实未收录该代码（部分小众港股 ETP、债券，或代码
    有误）。与其让完整分析在中途因 404 崩溃（错误信息为裸 404 / timeout，用户无法理解，
    且已白跑十几分钟 + 烧掉 token），不如开跑前 ~5 秒预检，立即给出可操作提示。
    yf_retry 会对暂时性超时自动重试，故偶发网络抖动不会误判。
    """
    import yfinance as yf
    from tradingagents.dataflows.stockstats_utils import yf_retry

    hint = (f"请确认代码格式：港股用 Yahoo 的去前导 0 格式（如 7709.HK 而非 07709.HK）、"
            f"A股如 600000.SS / 000001.SZ、美股如 AAPL、韩股如 000660.KS。")
    try:
        hist = yf_retry(lambda: yf.Ticker(ticker).history(period="5d"))
        if hist is None or hist.empty:
            return f"代码 {ticker} 在数据源（Yahoo Finance）无行情数据，可能 Yahoo 未收录该标的。{hint}"
        return None
    except Exception as e:
        msg = str(e).lower()
        if "404" in msg or "not found" in msg or "delisted" in msg:
            return f"代码 {ticker} 在数据源（Yahoo Finance）无行情数据，可能 Yahoo 未收录该标的。{hint}"
        # 其他错误（含重试后仍超时、TLS 等）不在此拦截，交给正式分析流程处理
        return None


def _run_analysis(job_id: str, ticker: str, date: str, config: dict):
    _update_job(job_id, status=JobStatus.running, progress=5)
    try:
        precheck_err = _precheck_ticker(ticker)
        if precheck_err:
            _update_job(job_id, status=JobStatus.failed, error=precheck_err)
            return
        ta = TradingAgentsGraph(debug=False, config=config)
        final_state, decision = ta.propagate(ticker, date)

        result = {
            "decision": decision,
            "market_report": final_state.get("market_report", ""),
            "sentiment_report": final_state.get("sentiment_report", ""),
            "news_report": final_state.get("news_report", ""),
            "fundamentals_report": final_state.get("fundamentals_report", ""),
            "investment_plan": final_state.get("investment_plan", ""),
            "final_trade_decision": final_state.get("final_trade_decision", ""),
        }
        _update_job(job_id, status=JobStatus.completed, progress=100, result=result)
    except Exception as e:
        _update_job(job_id, status=JobStatus.failed, error=str(e))


def _update_job(job_id: str, **kwargs):
    if job_id in _jobs:
        _jobs[job_id].update(kwargs)
        _jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()


async def queue_analysis(
    ticker: str, date: str, overrides: Optional[dict] = None
) -> str:
    # 港股 5 位代码（07709.HK）规范化为 Yahoo 的 4 位格式（7709.HK），否则 yfinance 404。
    # 全程（_jobs 记录、propagate、报告）统一用规范化后的代码。
    ticker = _normalize_ticker(ticker)
    job_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    config = DEFAULT_CONFIG.copy()
    # "auto" → 路由层按 ticker 市场自动选最优源（A股/港股→akshare 优先，
    # 美股/日韩等→yfinance 优先），失败自动 fallback。见 interface.route_to_vendor。
    # UI 未来可通过 overrides 传入具体 vendor 覆盖（强制 yfinance/akshare/AV）。
    _vendor = "auto"
    config["data_vendors"] = {
        "core_stock_apis": _vendor,
        "technical_indicators": _vendor,
        "fundamental_data": _vendor,
        "news_data": _vendor,
    }
    if overrides:
        config.update(overrides)

    _jobs[job_id] = {
        "job_id": job_id,
        "status": JobStatus.queued,
        "ticker": ticker,
        "date": date,
        "progress": 0,
        "result": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
    }

    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, _run_analysis, job_id, ticker, date, config)
    return job_id


def get_job(job_id: str) -> Optional[dict]:
    return _jobs.get(job_id)


def list_jobs() -> list:
    return sorted(_jobs.values(), key=lambda j: j["created_at"], reverse=True)
