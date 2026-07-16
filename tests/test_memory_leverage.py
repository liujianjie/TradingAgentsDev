from datetime import date, datetime, timezone
import sys
from types import SimpleNamespace

import pandas as pd
import pytest

from tradingagents.quant.memory_leverage import (
    Instrument,
    MarketDataBatch,
    SeriesDefinition,
    YFinanceMarketDataProvider,
    build_memory_leverage_report,
    default_instruments,
    default_series_definitions,
)


DATES = pd.to_datetime(["2026-07-09", "2026-07-10"])


def _history(close, volume, dates=DATES):
    return pd.DataFrame({"Close": close, "Volume": volume}, index=dates)


def _definition(series_id, company_id, scope, primary_symbol):
    return SeriesDefinition(
        id=series_id,
        company_id=company_id,
        company_name=company_id,
        scope=scope,
        primary_symbol=primary_symbol,
        color="#123456",
    )


def test_ratio_uses_raw_turnover_and_exposes_leverage_weighted_variant():
    instruments = (
        Instrument("BASE", "memory", "underlying", "all", "USD", "US", is_primary=True),
        Instrument("LONG", "memory", "leveraged", "all", "USD", "US", leverage_multiple=2),
        Instrument("SHORT", "memory", "leveraged", "all", "USD", "US", leverage_multiple=-1),
    )
    batch = MarketDataBatch(
        histories={
            "BASE": _history([10, 20], [100, 100]),
            "LONG": _history([5, 5], [100, 100]),
            "SHORT": _history([2, 2], [100, 50]),
        },
        errors={},
    )

    report = build_memory_leverage_report(
        instruments,
        (_definition("memory_all", "memory", "all", "BASE"),),
        batch,
        generated_at=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )

    series = report["series"][0]
    assert [point["ratio"] for point in series["points"]] == pytest.approx([0.7, 0.3])
    assert series["latest"]["long_turnover_usd"] == pytest.approx(500)
    assert series["latest"]["short_turnover_usd"] == pytest.approx(100)
    assert series["latest"]["underlying_turnover_usd"] == pytest.approx(2_000)
    assert series["latest"]["leverage_weighted_ratio"] == pytest.approx(0.55)
    assert series["latest"]["change_1d"] == pytest.approx(-0.4)


def test_all_and_kr_scopes_use_fx_and_include_only_their_registered_legs():
    instruments = (
        Instrument("KR_BASE", "sk", "underlying", "kr", "KRW", "KRX", is_primary=True),
        Instrument("ADR", "sk", "underlying", "all", "USD", "US"),
        Instrument("KR_LONG", "sk", "leveraged", "kr", "KRW", "KRX", leverage_multiple=2),
        Instrument("US_LONG", "sk", "leveraged", "all", "USD", "US", leverage_multiple=2),
    )
    one_day = pd.to_datetime(["2026-07-10"])
    batch = MarketDataBatch(
        histories={
            "KR_BASE": _history([1_000], [100], one_day),
            "ADR": _history([5], [20], one_day),
            "KR_LONG": _history([500], [100], one_day),
            "US_LONG": _history([25], [2], one_day),
            "KRW=X": _history([1_000], [0], one_day),
        },
        errors={},
    )

    report = build_memory_leverage_report(
        instruments,
        (
            _definition("sk_all", "sk", "all", "KR_BASE"),
            _definition("sk_kr", "sk", "kr", "KR_BASE"),
        ),
        batch,
        generated_at=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )

    all_latest = report["series"][0]["latest"]
    kr_latest = report["series"][1]["latest"]
    assert all_latest["underlying_turnover_usd"] == pytest.approx(200)
    assert all_latest["long_turnover_usd"] == pytest.approx(100)
    assert all_latest["ratio"] == pytest.approx(0.5)
    assert kr_latest["underlying_turnover_usd"] == pytest.approx(100)
    assert kr_latest["long_turnover_usd"] == pytest.approx(50)
    assert kr_latest["ratio"] == pytest.approx(0.5)


def test_company_without_leveraged_product_returns_zero_ratio():
    instruments = (
        Instrument("KIOXIA", "kioxia", "underlying", "all", "USD", "TSE", is_primary=True),
    )
    batch = MarketDataBatch(
        histories={"KIOXIA": _history([10, 12], [100, 100])},
        errors={},
    )

    report = build_memory_leverage_report(
        instruments,
        (_definition("kioxia_all", "kioxia", "all", "KIOXIA"),),
        batch,
        generated_at=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )

    assert report["series"][0]["latest"]["ratio"] == 0
    assert report["series"][0]["latest"]["leverage_weighted_ratio"] == 0


def test_default_registry_covers_the_seven_visible_series_and_key_products():
    instruments = default_instruments()
    definitions = default_series_definitions()

    assert [item.id for item in definitions] == [
        "sandisk_all",
        "micron_all",
        "sk_hynix_all",
        "sk_hynix_kr",
        "samsung_all",
        "samsung_kr",
        "kioxia_all",
    ]
    symbols = {item.symbol for item in instruments}
    assert len(symbols) == len(instruments)
    assert {
        "SNXX",
        "SNDU",
        "SNDG",
        "SNDQ",
        "MUU",
        "MULL",
        "MUD",
        "0193T0.KS",
        "0197X0.KS",
        "7709.HK",
        "SKHY",
        "0193W0.KS",
        "0193L0.KS",
        "7747.HK",
        "7347.HK",
    }.issubset(symbols)
    assert all(item.leverage_multiple != 0 for item in instruments if item.role == "leveraged")
    assert all(item.source_url for item in instruments if item.role == "leveraged")


def test_yfinance_provider_avoids_optional_repair_dependency_and_cache_races(monkeypatch):
    columns = pd.MultiIndex.from_tuples(
        [
            ("AAA", "Close"),
            ("AAA", "Volume"),
            ("KRW=X", "Close"),
            ("KRW=X", "Volume"),
        ]
    )
    downloaded = pd.DataFrame(
        [[10.0, 100.0, 1_000.0, 0.0]],
        index=pd.to_datetime(["2026-07-10"]),
        columns=columns,
    )
    seen = {}

    def fake_download(tickers, **kwargs):
        seen["tickers"] = tickers
        seen.update(kwargs)
        return downloaded

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(download=fake_download))

    batch = YFinanceMarketDataProvider().fetch(
        ["AAA", "KRW=X"],
        start=date(2026, 7, 1),
        end=date(2026, 7, 11),
    )

    assert seen["auto_adjust"] is False
    assert seen["repair"] is False
    assert seen["threads"] is False
    assert seen["group_by"] == "ticker"
    assert batch.histories["AAA"]["Close"].tolist() == [10.0]
    assert batch.histories["KRW=X"]["Close"].tolist() == [1_000.0]
    assert batch.errors == {}
