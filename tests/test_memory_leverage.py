from datetime import datetime, timezone

import pandas as pd
import pytest

from tradingagents.quant.memory_leverage import (
    Instrument,
    MarketDataBatch,
    SeriesDefinition,
    build_memory_leverage_report,
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
