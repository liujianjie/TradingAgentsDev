from .config_loader import load_apikeys

load_apikeys()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

from .models import AnalyzeRequest
from .analyzer import queue_analysis, get_job, list_jobs

app = FastAPI(title="TradingAgents API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.post("/api/v1/analyze")
async def analyze(request: AnalyzeRequest):
    overrides = {}
    if request.llm_provider:
        overrides["llm_provider"] = request.llm_provider
    if request.deep_think_llm:
        overrides["deep_think_llm"] = request.deep_think_llm
    if request.quick_think_llm:
        overrides["quick_think_llm"] = request.quick_think_llm

    job_id = await queue_analysis(
        ticker=request.ticker,
        date=request.date,
        overrides=overrides or None,
    )
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/v1/jobs/{job_id}")
def get_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/v1/jobs")
def list_all_jobs():
    return {"jobs": list_jobs()}
