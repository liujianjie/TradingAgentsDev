from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from tradingagents.quant.memory_leverage import MemoryLeverageDataError


def _report():
    return {
        "generated_at": datetime(2026, 7, 16, tzinfo=timezone.utc).isoformat(),
        "as_of": "2026-07-15",
        "methodology": {
            "ratio": "leveraged_product_turnover_usd / underlying_turnover_usd",
            "weighted_ratio": "weighted / underlying_turnover_usd",
            "data_source": "Yahoo Finance via yfinance",
            "registry_version": "2026-07-16",
        },
        "series": [
            {
                "id": "sandisk_all",
                "company_id": "sandisk",
                "company_name": "SanDisk",
                "scope": "all",
                "color": "#58A6FF",
                "latest": {
                    "date": "2026-07-15",
                    "ratio": 0.1,
                    "change_1d": 0.01,
                    "long_turnover_usd": 100.0,
                    "short_turnover_usd": 20.0,
                    "leverage_weighted_ratio": 0.2,
                    "underlying_turnover_usd": 1_200.0,
                },
                "points": [
                    {
                        "date": "2026-07-15",
                        "ratio": 0.1,
                        "change_1d": 0.01,
                        "long_turnover_usd": 100.0,
                        "short_turnover_usd": 20.0,
                        "leverage_weighted_ratio": 0.2,
                        "underlying_turnover_usd": 1_200.0,
                    }
                ],
            }
        ],
        "coverage": [
            {
                "symbol": "SNDK",
                "company_id": "sandisk",
                "role": "underlying",
                "venue": "NASDAQ",
                "status": "ok",
                "last_date": "2026-07-15",
                "source_url": "",
            }
        ],
        "warnings": [],
    }


class FakeService:
    def __init__(self, result=None, error=None):
        self.result = result or _report()
        self.error = error
        self.calls = []

    def get_report(self, *, days):
        self.calls.append(days)
        if self.error:
            raise self.error
        return self.result


@pytest.fixture
def client(monkeypatch, tmp_path):
    from api import quant as quant_api
    from api.main import app

    service = FakeService()
    disk_cache = quant_api.MemoryLeverageReportDiskCache(tmp_path)
    monkeypatch.setattr(quant_api, "_disk_cache", disk_cache)
    quant_api.clear_memory_leverage_cache(include_disk=True)
    monkeypatch.setattr(quant_api, "_service", service)
    return TestClient(app), service, quant_api


def test_memory_leverage_endpoint_returns_typed_payload_and_uses_cache(client):
    http, service, _ = client

    first = http.get("/api/v1/quant/memory-leverage-ratios?days=90")
    second = http.get("/api/v1/quant/memory-leverage-ratios?days=90")

    assert first.status_code == 200
    assert first.json()["series"][0]["id"] == "sandisk_all"
    assert first.json()["cache"]["layer"] == "live"
    assert second.status_code == 200
    assert second.json()["cache"]["layer"] == "memory"
    assert service.calls == [90]


def test_disk_cache_survives_memory_cache_reset(client):
    http, service, quant_api = client

    first = http.get("/api/v1/quant/memory-leverage-ratios?days=90")
    quant_api.clear_memory_leverage_cache()
    second = http.get("/api/v1/quant/memory-leverage-ratios?days=90")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["cache"]["layer"] == "disk"
    assert service.calls == [90]


def test_refresh_bypasses_cache(client):
    http, service, _ = client

    http.get("/api/v1/quant/memory-leverage-ratios?days=220")
    refreshed = http.get(
        "/api/v1/quant/memory-leverage-ratios?days=220&refresh=true"
    )

    assert refreshed.status_code == 200
    assert refreshed.json()["cache"]["layer"] == "live"
    assert service.calls == [220, 220]


def test_stale_disk_cache_is_returned_when_provider_fails(client, monkeypatch):
    http, _, quant_api = client

    cached = _report()
    quant_api._disk_cache.save(
        220,
        cached,
        saved_at=quant_api.time.time() - quant_api._CACHE_TTL_SECONDS - 1,
    )
    failing = FakeService(error=MemoryLeverageDataError("upstream private detail"))
    monkeypatch.setattr(quant_api, "_service", failing)

    response = http.get("/api/v1/quant/memory-leverage-ratios?days=220")

    assert response.status_code == 200
    assert response.json()["cache"] == {
        "layer": "stale_disk",
        "is_stale": True,
        "ttl_seconds": quant_api._CACHE_TTL_SECONDS,
    }
    assert any("缓存" in warning for warning in response.json()["warnings"])


@pytest.mark.parametrize("days", [29, 731])
def test_days_boundary_is_validated(days, client):
    http, service, _ = client

    response = http.get(f"/api/v1/quant/memory-leverage-ratios?days={days}")

    assert response.status_code == 422
    assert service.calls == []


def test_provider_failure_returns_sanitized_502(client, monkeypatch):
    http, _, quant_api = client
    failing = FakeService(error=MemoryLeverageDataError("upstream private detail"))
    monkeypatch.setattr(quant_api, "_service", failing)

    response = http.get("/api/v1/quant/memory-leverage-ratios")

    assert response.status_code == 502
    assert response.json() == {"detail": "memory leverage data unavailable"}
    assert "private" not in response.text
