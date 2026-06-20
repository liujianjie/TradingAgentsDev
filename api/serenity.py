"""Serenity 产业链卡点研究 API（独立路由）。

独立挂在 ``/api/v1/serenity/*`` 下，不影响现有 ``/api/v1/analyze``。
in-memory job 队列（与 ``analyzer._jobs`` 隔离），进程重启清空——
持久化推到后续 task（见 spec §3 Out of scope）。
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingagents.serenity.schemas import ResearchMode, ScanRequest

router = APIRouter(prefix="/api/v1/serenity", tags=["serenity"])

_executor = ThreadPoolExecutor(max_workers=2)
_jobs: Dict[str, dict] = {}


def _now() -> str:
    return datetime.utcnow().isoformat()


def _update_job(job_id: str, **kwargs) -> None:
    if job_id in _jobs:
        _jobs[job_id].update(kwargs)
        _jobs[job_id]["updated_at"] = _now()


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "module": "serenity", "time": _now()}


@router.post("/scan")
async def scan(request: ScanRequest) -> dict:
    if request.mode == ResearchMode.theme_scan and not request.theme:
        raise HTTPException(400, "theme_scan 必须提供 theme")
    if request.mode != ResearchMode.theme_scan and not request.tickers:
        raise HTTPException(400, f"{request.mode.value} 必须提供 tickers")

    job_id = f"ser-{uuid.uuid4().hex[:12]}"
    now = _now()
    _jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "progress": {"step": 0, "total": 9, "stage": "queued"},
        "result": None,
        "sources_consulted": 0,
        "candidates_inspected": 0,
        "trace_log": [],
        "error": None,
        "created_at": now,
        "updated_at": now,
        "request": request.model_dump(),
    }
    # T1 仅落骨架；workflow 执行在 T4 接入，写入 _run_workflow → _executor.submit。
    return {"job_id": job_id, "status": "queued"}


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/jobs")
def list_jobs() -> dict:
    return {
        "jobs": sorted(_jobs.values(), key=lambda j: j["created_at"], reverse=True)
    }
