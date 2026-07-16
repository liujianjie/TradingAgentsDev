"""Read-only quantitative research endpoints."""

from __future__ import annotations

import threading
import time
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from tradingagents.quant.memory_leverage import (
    MemoryLeverageDataError,
    MemoryLeverageService,
)


class MethodologyPayload(BaseModel):
    ratio: str
    weighted_ratio: str
    data_source: str
    registry_version: str


class RatioPointPayload(BaseModel):
    date: str
    ratio: float


class LatestRatioPayload(BaseModel):
    date: str
    ratio: float
    change_1d: float | None
    long_turnover_usd: float
    short_turnover_usd: float
    leverage_weighted_ratio: float
    underlying_turnover_usd: float


class RatioSeriesPayload(BaseModel):
    id: str
    company_id: str
    company_name: str
    scope: Literal["all", "kr"]
    color: str
    latest: LatestRatioPayload | None
    points: list[RatioPointPayload]


class CoveragePayload(BaseModel):
    symbol: str
    company_id: str
    role: Literal["underlying", "leveraged"]
    venue: str
    status: Literal["ok", "missing"]
    last_date: str | None
    source_url: str


class MemoryLeverageResponse(BaseModel):
    generated_at: str
    as_of: str
    methodology: MethodologyPayload
    series: list[RatioSeriesPayload]
    coverage: list[CoveragePayload]
    warnings: list[str]


router = APIRouter(prefix="/api/v1/quant", tags=["quant"])
_service = MemoryLeverageService()
_CACHE_TTL_SECONDS = 15 * 60
_cache: dict[int, tuple[float, dict]] = {}
_cache_lock = threading.Lock()


def clear_memory_leverage_cache() -> None:
    with _cache_lock:
        _cache.clear()


def _get_report(days: int, refresh: bool) -> dict:
    now = time.monotonic()
    if not refresh:
        with _cache_lock:
            cached = _cache.get(days)
            if cached and now - cached[0] < _CACHE_TTL_SECONDS:
                return cached[1]
    report = _service.get_report(days=days)
    with _cache_lock:
        _cache[days] = (time.monotonic(), report)
    return report


@router.get(
    "/memory-leverage-ratios",
    response_model=MemoryLeverageResponse,
    summary="Memory-sector leveraged-product turnover ratios",
)
def memory_leverage_ratios(
    days: int = Query(220, ge=30, le=730),
    refresh: bool = Query(False),
) -> dict:
    try:
        return _get_report(days, refresh)
    except MemoryLeverageDataError:
        raise HTTPException(
            status_code=502,
            detail="memory leverage data unavailable",
        ) from None

