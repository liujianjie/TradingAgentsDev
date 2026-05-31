from pydantic import BaseModel
from typing import Optional, Any
from enum import Enum


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class AnalyzeRequest(BaseModel):
    ticker: str
    date: str
    job_id: Optional[str] = None
    llm_provider: Optional[str] = None
    deep_think_llm: Optional[str] = None
    quick_think_llm: Optional[str] = None


class JobResult(BaseModel):
    decision: Optional[str] = None
    market_report: Optional[str] = None
    sentiment_report: Optional[str] = None
    news_report: Optional[str] = None
    fundamentals_report: Optional[str] = None
    investment_plan: Optional[str] = None
    final_trade_decision: Optional[str] = None


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    ticker: Optional[str] = None
    date: Optional[str] = None
    progress: int = 0
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str
