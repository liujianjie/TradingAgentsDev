import uuid
import asyncio
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


def _run_analysis(job_id: str, ticker: str, date: str, config: dict):
    _update_job(job_id, status=JobStatus.running, progress=5)
    try:
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
    job_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    config = DEFAULT_CONFIG.copy()
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
