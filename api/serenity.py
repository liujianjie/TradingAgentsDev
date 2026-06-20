"""Serenity 产业链卡点研究 API（独立路由）。

独立挂在 ``/api/v1/serenity/*`` 下，不影响现有 ``/api/v1/analyze``。
in-memory job 队列（与 ``analyzer._jobs`` 隔离），进程重启清空——
持久化推到后续 task（见 spec §3 Out of scope）。

工作流跑在 ``ThreadPoolExecutor`` 里（与 ``api/analyzer.py`` 模式一致），
通过 ``_dispatch`` 单层间接，让单测可换成同步直跑、不依赖时间窗口。
"""
from __future__ import annotations

import logging
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict

from fastapi import APIRouter, HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingagents.serenity.schemas import ResearchMode, ScanRequest
from tradingagents.serenity.workflow import (
    SerenityWorkflowError,
    run_serenity_workflow,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/serenity", tags=["serenity"])

_executor = ThreadPoolExecutor(max_workers=2)
_jobs: Dict[str, dict] = {}

_TRACE_LOG_MAX_LINES = 200


def _now() -> str:
    return datetime.utcnow().isoformat()


def _update_job(job_id: str, **kwargs) -> None:
    if job_id in _jobs:
        _jobs[job_id].update(kwargs)
        _jobs[job_id]["updated_at"] = _now()


def _make_progress_cb(job_id: str):
    def cb(step: int, stage: str) -> None:
        _update_job(
            job_id,
            status="running",
            progress={"step": step, "total": 9, "stage": stage},
        )

    return cb


def _make_trace_cb(job_id: str):
    def cb(line: str) -> None:
        if job_id not in _jobs:
            return
        log = _jobs[job_id].setdefault("trace_log", [])
        log.append(line)
        if len(log) > _TRACE_LOG_MAX_LINES:
            del log[: len(log) - _TRACE_LOG_MAX_LINES]

    return cb


def _run_workflow_job(job_id: str, request: ScanRequest) -> None:
    """后台任务：跑 workflow，把状态写回 ``_jobs[job_id]``。"""
    try:
        report, sources_count = run_serenity_workflow(
            request,
            progress_cb=_make_progress_cb(job_id),
            trace_cb=_make_trace_cb(job_id),
        )
        _update_job(
            job_id,
            status="completed",
            progress={"step": 9, "total": 9, "stage": "done"},
            result=report.model_dump(),
            sources_consulted=sources_count,
            candidates_inspected=len(report.company_universe),
        )
    except SerenityWorkflowError as e:
        _update_job(job_id, status="failed", error=str(e))
    except Exception as e:
        # workflow 内层应已包装；这里兜底防 thread 内异常被吞
        logger.exception("serenity job %s failed", job_id)
        _update_job(job_id, status="failed", error=f"{type(e).__name__}: {e}")


def _dispatch(job_id: str, request: ScanRequest) -> None:
    """提交后台任务的单层间接，单测可 monkeypatch 成同步直跑。"""
    _executor.submit(_run_workflow_job, job_id, request)


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
    _dispatch(job_id, request)
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
