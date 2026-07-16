"""Read-only quantitative research endpoints."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.quant.memory_leverage import (
    MemoryLeverageDataError,
    MemoryLeverageService,
)

_CACHE_FORMAT_VERSION = 2


class MethodologyPayload(BaseModel):
    ratio: str
    weighted_ratio: str
    data_source: str
    registry_version: str


class RatioPointPayload(BaseModel):
    date: str
    ratio: float
    change_1d: float | None
    long_turnover_usd: float
    short_turnover_usd: float
    leverage_weighted_ratio: float
    underlying_turnover_usd: float


class LatestRatioPayload(RatioPointPayload):
    pass


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


class CachePayload(BaseModel):
    layer: Literal["live", "memory", "disk", "stale_disk"]
    is_stale: bool
    ttl_seconds: int


class MemoryLeverageResponse(BaseModel):
    generated_at: str
    as_of: str
    methodology: MethodologyPayload
    series: list[RatioSeriesPayload]
    coverage: list[CoveragePayload]
    warnings: list[str]
    cache: CachePayload


class MemoryLeverageReportDiskCache:
    """Small JSON cache for successful reports, reusable across API restarts."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    def _path(self, days: int) -> Path:
        return self.directory / f"report-{days}.json"

    def load(self, days: int) -> tuple[float, dict] | None:
        try:
            payload = json.loads(self._path(days).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeError):
            return None
        if not isinstance(payload, dict):
            return None
        if payload.get("format_version") != _CACHE_FORMAT_VERSION:
            return None
        saved_at = payload.get("saved_at")
        report = payload.get("report")
        if (
            not isinstance(saved_at, (int, float))
            or not isinstance(report, dict)
            or not isinstance(report.get("series"), list)
            or not isinstance(report.get("coverage"), list)
            or not isinstance(report.get("warnings"), list)
        ):
            return None
        return float(saved_at), report

    def save(
        self,
        days: int,
        report: dict,
        *,
        saved_at: float | None = None,
    ) -> bool:
        path = self._path(days)
        temp_path = path.with_suffix(f".{threading.get_ident()}.tmp")
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            temp_path.write_text(
                json.dumps(
                    {
                        "format_version": _CACHE_FORMAT_VERSION,
                        "saved_at": time.time() if saved_at is None else saved_at,
                        "report": report,
                    },
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            temp_path.replace(path)
        except (OSError, TypeError, ValueError):
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            return False
        return True

    def clear(self) -> None:
        try:
            paths = tuple(self.directory.glob("report-*.json"))
        except OSError:
            return
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                continue


router = APIRouter(prefix="/api/v1/quant", tags=["quant"])
_service = MemoryLeverageService()
_CACHE_TTL_SECONDS = 15 * 60
_cache: dict[int, tuple[float, dict]] = {}
_cache_lock = threading.Lock()
_refresh_lock = threading.Lock()
_disk_cache = MemoryLeverageReportDiskCache(
    Path(DEFAULT_CONFIG["data_cache_dir"]) / "memory-leverage"
)


def clear_memory_leverage_cache(*, include_disk: bool = False) -> None:
    with _cache_lock:
        _cache.clear()
    if include_disk:
        _disk_cache.clear()


def _cache_response(report: dict, layer: str, *, is_stale: bool = False) -> dict:
    payload = dict(report)
    if is_stale:
        warning = "行情源暂时不可用，当前展示最近一次成功缓存"
        warnings = list(report.get("warnings", []))
        if warning not in warnings:
            warnings.append(warning)
        payload["warnings"] = warnings
    payload["cache"] = {
        "layer": layer,
        "is_stale": is_stale,
        "ttl_seconds": _CACHE_TTL_SECONDS,
    }
    return payload


def _memory_cache_hit(days: int, now: float) -> dict | None:
    with _cache_lock:
        cached = _cache.get(days)
        if cached and now - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1]
    return None


def _remember(days: int, report: dict) -> None:
    with _cache_lock:
        _cache[days] = (time.monotonic(), report)


def _get_report(days: int, refresh: bool) -> dict:
    if not refresh:
        memory_report = _memory_cache_hit(days, time.monotonic())
        if memory_report is not None:
            return _cache_response(memory_report, "memory")

    with _refresh_lock:
        if not refresh:
            memory_report = _memory_cache_hit(days, time.monotonic())
            if memory_report is not None:
                return _cache_response(memory_report, "memory")

        disk_entry = _disk_cache.load(days)
        if not refresh and disk_entry is not None:
            saved_at, disk_report = disk_entry
            if time.time() - saved_at < _CACHE_TTL_SECONDS:
                _remember(days, disk_report)
                return _cache_response(disk_report, "disk")

        try:
            report = _service.get_report(days=days)
        except MemoryLeverageDataError:
            if disk_entry is not None:
                return _cache_response(disk_entry[1], "stale_disk", is_stale=True)
            raise

        _disk_cache.save(days, report)
        _remember(days, report)
        return _cache_response(report, "live")


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
