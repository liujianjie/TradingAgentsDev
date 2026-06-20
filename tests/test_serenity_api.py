"""serenity FastAPI 路由单测：mock workflow，验证 happy + 错误路径。"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tradingagents.serenity.schemas import SerenityReport


_VALID_REPORT_DICT = {
    "scope": {
        "market": "A-share",
        "theme": "AI 半导体",
        "tickers": None,
        "time_window": "12 个月",
    },
    "system_change": "test",
    "value_chain_layers": [{"name": "x", "rank": 1, "reason": "y"}],
    "scarce_layers": [{"layer": "x", "why_scarce": "y", "evidence_strength": "strong"}],
    "company_universe": [
        {
            "ticker": "688981.SS",
            "company": "x",
            "chain_position": "y",
            "classification": "supplies_scarce_layer",
        },
        {
            "ticker": "002230.SZ",
            "company": "z",
            "chain_position": "w",
            "classification": "story_only",
        },
    ],
    "top_priorities": [
        {
            "ticker": "688981.SS",
            "company": "x",
            "constrains_what": "y",
            "chain_position": "z",
            "rank_reason": "w",
            "evidence": [
                {"claim": "a", "source": "b", "strength": "primary"},
                {"claim": "c", "source": "d", "strength": "media"},
            ],
            "main_risk": "r",
        }
    ],
    "what_could_go_wrong": ["x"],
    "next_research_moves": ["y"],
}


@pytest.fixture
def client(monkeypatch):
    """让 _dispatch 同步直跑，单测 deterministic。"""
    from api import serenity as ser_mod
    from api.main import app

    # 重置 in-memory store, 不让用例之间互相污染
    ser_mod._jobs.clear()

    def sync_dispatch(job_id, request):
        ser_mod._run_workflow_job(job_id, request)

    monkeypatch.setattr(ser_mod, "_dispatch", sync_dispatch)
    return TestClient(app)


def _patch_workflow_success():
    report = SerenityReport.model_validate(_VALID_REPORT_DICT)
    return patch(
        "api.serenity.run_serenity_workflow",
        return_value=(report, 27),
    )


def test_health(client):
    r = client.get("/api/v1/serenity/health")
    assert r.status_code == 200
    assert r.json()["module"] == "serenity"


def test_scan_theme_scan_missing_theme(client):
    r = client.post(
        "/api/v1/serenity/scan",
        json={"mode": "theme_scan", "market": "A-share"},
    )
    assert r.status_code == 400
    assert "theme" in r.json()["detail"]


def test_scan_single_challenge_missing_tickers(client):
    r = client.post(
        "/api/v1/serenity/scan",
        json={"mode": "single_challenge", "market": "US"},
    )
    assert r.status_code == 400
    assert "tickers" in r.json()["detail"]


def test_scan_happy_runs_workflow(client):
    with _patch_workflow_success():
        r = client.post(
            "/api/v1/serenity/scan",
            json={
                "mode": "theme_scan",
                "market": "A-share",
                "theme": "AI 半导体",
            },
        )
    assert r.status_code == 200
    jid = r.json()["job_id"]

    rj = client.get(f"/api/v1/serenity/jobs/{jid}")
    assert rj.status_code == 200
    body = rj.json()
    assert body["status"] == "completed"
    assert body["progress"]["step"] == 9
    assert body["progress"]["stage"] == "done"
    assert body["sources_consulted"] == 27
    assert body["candidates_inspected"] == 2
    assert body["result"]["scope"]["theme"] == "AI 半导体"
    assert len(body["result"]["top_priorities"]) == 1


def test_scan_workflow_failure_marks_failed(client):
    from tradingagents.serenity.workflow import SerenityWorkflowError

    with patch(
        "api.serenity.run_serenity_workflow",
        side_effect=SerenityWorkflowError("agent loop 执行失败: timeout"),
    ):
        r = client.post(
            "/api/v1/serenity/scan",
            json={
                "mode": "theme_scan",
                "market": "A-share",
                "theme": "x",
            },
        )
    jid = r.json()["job_id"]
    body = client.get(f"/api/v1/serenity/jobs/{jid}").json()
    assert body["status"] == "failed"
    assert "timeout" in body["error"]


def test_scan_unexpected_exception_marks_failed(client):
    with patch(
        "api.serenity.run_serenity_workflow",
        side_effect=RuntimeError("unexpected"),
    ):
        r = client.post(
            "/api/v1/serenity/scan",
            json={
                "mode": "single_challenge",
                "market": "US",
                "tickers": ["NVDA"],
            },
        )
    jid = r.json()["job_id"]
    body = client.get(f"/api/v1/serenity/jobs/{jid}").json()
    assert body["status"] == "failed"
    assert "RuntimeError" in body["error"]


def test_get_job_404(client):
    r = client.get("/api/v1/serenity/jobs/ser-nope")
    assert r.status_code == 404


def test_list_jobs_sorted(client):
    with _patch_workflow_success():
        client.post(
            "/api/v1/serenity/scan",
            json={"mode": "theme_scan", "market": "US", "theme": "a"},
        )
        client.post(
            "/api/v1/serenity/scan",
            json={"mode": "theme_scan", "market": "A-share", "theme": "b"},
        )
    body = client.get("/api/v1/serenity/jobs").json()
    assert len(body["jobs"]) == 2
    # 倒序：最新在前
    assert body["jobs"][0]["created_at"] >= body["jobs"][1]["created_at"]


def test_progress_cb_writes_running_state(client):
    """progress_cb 在 workflow 内被调用时, 应触发 status=running 写回 _jobs。"""
    from api import serenity as ser_mod

    captured_states = []

    def fake_workflow(request, *, progress_cb, trace_cb, **kwargs):
        progress_cb(1, "set_scope")
        # 立即抓快照，看下 _jobs 已被改成 running
        jid = next(iter(ser_mod._jobs))
        captured_states.append(dict(ser_mod._jobs[jid]))
        progress_cb(9, "done")
        report = SerenityReport.model_validate(_VALID_REPORT_DICT)
        return report, 5

    with patch("api.serenity.run_serenity_workflow", side_effect=fake_workflow):
        client.post(
            "/api/v1/serenity/scan",
            json={"mode": "theme_scan", "market": "A-share", "theme": "x"},
        )
    assert captured_states
    snap = captured_states[0]
    assert snap["status"] == "running"
    assert snap["progress"]["step"] == 1
    assert snap["progress"]["stage"] == "set_scope"


def test_trace_log_capped(client):
    from api import serenity as ser_mod

    def fake_workflow(request, *, progress_cb, trace_cb, **kwargs):
        for i in range(500):
            trace_cb(f"line {i}")
        report = SerenityReport.model_validate(_VALID_REPORT_DICT)
        return report, 1

    with patch("api.serenity.run_serenity_workflow", side_effect=fake_workflow):
        r = client.post(
            "/api/v1/serenity/scan",
            json={"mode": "theme_scan", "market": "A-share", "theme": "x"},
        )
    jid = r.json()["job_id"]
    body = client.get(f"/api/v1/serenity/jobs/{jid}").json()
    assert len(body["trace_log"]) == ser_mod._TRACE_LOG_MAX_LINES
    # 保留的应是最新的 200 条
    assert body["trace_log"][-1] == "line 499"
    assert body["trace_log"][0] == f"line {500 - ser_mod._TRACE_LOG_MAX_LINES}"
