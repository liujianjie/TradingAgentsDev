from .config_loader import load_apikeys

load_apikeys()

# yfinance 1.x 默认用 curl_cffi(impersonate="chrome") 发请求。
# Chrome TLS 指纹 (JA3/JA4) 对韩国、部分亚洲 Yahoo Finance 端点握手失败
# (curl error 35, OPENSSL_internal:invalid library)。
# 告知 yfinance curl_cffi 不可用 → new_session() 走 requests 分支，绕过此问题。
try:
    import requests as _req
    import yfinance._http as _yf_http
    import yfinance.data as _yf_data

    _yf_http.HAS_CURL_CFFI = False   # new_session() 检查这个变量
    _yf_http._backend = _req
    _yf_http.requests = _req
    _yf_data.YfData._instances.clear()
    print("[yfinance] requests backend active (curl_cffi TLS bypassed)")
except Exception as _patch_err:
    print(f"[yfinance] patch skipped: {_patch_err}")

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
