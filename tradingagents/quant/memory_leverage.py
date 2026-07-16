"""Memory-sector leverage-ratio calculation.

The metric compares actual traded notional in single-stock leveraged products
with actual traded notional in the corresponding common shares and depositary
receipts.  It is a market-activity measure, not a balance-sheet leverage ratio.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Mapping, Sequence

import pandas as pd


Role = Literal["underlying", "leveraged"]
Scope = Literal["all", "kr"]


class MemoryLeverageDataError(RuntimeError):
    """Raised when no primary-listing data is usable."""


@dataclass(frozen=True)
class Instrument:
    symbol: str
    company_id: str
    role: Role
    scope: Scope
    currency: str
    venue: str
    leverage_multiple: float = 1.0
    quote_unit: float = 1.0
    is_primary: bool = False
    name: str = ""
    source_url: str = ""


@dataclass(frozen=True)
class SeriesDefinition:
    id: str
    company_id: str
    company_name: str
    scope: Scope
    primary_symbol: str
    color: str


@dataclass(frozen=True)
class MarketDataBatch:
    histories: Mapping[str, pd.DataFrame]
    errors: Mapping[str, str]


_FX_TO_USD = {
    "KRW": ("KRW=X", "divide"),
    "JPY": ("JPY=X", "divide"),
    "HKD": ("HKD=X", "divide"),
    "EUR": ("EURUSD=X", "multiply"),
    "GBP": ("GBPUSD=X", "multiply"),
}


def _normalise_index(values: pd.Series) -> pd.Series:
    result = values.copy()
    index = pd.to_datetime(result.index, errors="coerce", utc=True)
    valid = ~index.isna()
    result = result.loc[valid]
    result.index = index[valid].tz_convert(None).normalize()
    return result.groupby(level=0).last().sort_index()


def _valid_close_volume(frame: pd.DataFrame | None) -> pd.DataFrame:
    if frame is None or frame.empty or not {"Close", "Volume"}.issubset(frame.columns):
        return pd.DataFrame(columns=["Close", "Volume"], dtype=float)
    close = _normalise_index(pd.to_numeric(frame["Close"], errors="coerce"))
    volume = _normalise_index(pd.to_numeric(frame["Volume"], errors="coerce"))
    cleaned = pd.concat([close.rename("Close"), volume.rename("Volume")], axis=1)
    finite = cleaned.replace([float("inf"), float("-inf")], pd.NA).notna().all(axis=1)
    return cleaned.loc[finite & cleaned["Close"].gt(0) & cleaned["Volume"].ge(0)]


def _valid_close(frame: pd.DataFrame | None) -> pd.Series:
    if frame is None or frame.empty or "Close" not in frame.columns:
        return pd.Series(dtype=float)
    close = _normalise_index(pd.to_numeric(frame["Close"], errors="coerce"))
    close = close.replace([float("inf"), float("-inf")], pd.NA).dropna()
    return close.loc[close.gt(0)].astype(float)


def _fx_rate_to_usd(
    currency: str,
    index: pd.DatetimeIndex,
    histories: Mapping[str, pd.DataFrame],
) -> pd.Series:
    if currency.upper() == "USD":
        return pd.Series(1.0, index=index)
    spec = _FX_TO_USD.get(currency.upper())
    if spec is None:
        return pd.Series(dtype=float)
    symbol, operation = spec
    close = _valid_close(histories.get(symbol))
    aligned = close.reindex(close.index.union(index)).sort_index().ffill().reindex(index)
    if operation == "divide":
        return 1.0 / aligned
    return aligned


def _turnover_usd(
    instrument: Instrument,
    histories: Mapping[str, pd.DataFrame],
) -> pd.Series:
    history = _valid_close_volume(histories.get(instrument.symbol))
    if history.empty:
        return pd.Series(dtype=float)
    fx = _fx_rate_to_usd(instrument.currency, history.index, histories)
    turnover = history["Close"] * history["Volume"] * instrument.quote_unit * fx
    return turnover.replace([float("inf"), float("-inf")], pd.NA).dropna().astype(float)


def _utc_iso(value: datetime | None) -> str:
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _in_scope(instrument: Instrument, scope: Scope) -> bool:
    return scope == "all" or instrument.scope == "kr"


def _sum_turnover(
    selected: Sequence[Instrument],
    index: pd.DatetimeIndex,
    turnovers: Mapping[str, pd.Series],
    *,
    weighted: bool = False,
) -> pd.Series:
    total = pd.Series(0.0, index=index)
    for instrument in selected:
        values = turnovers[instrument.symbol].reindex(index).fillna(0.0)
        factor = abs(instrument.leverage_multiple) if weighted else 1.0
        total = total.add(values * factor, fill_value=0.0)
    return total


def _coverage(
    instruments: Sequence[Instrument],
    turnovers: Mapping[str, pd.Series],
) -> tuple[list[dict], list[str]]:
    rows = []
    warnings = []
    for instrument in instruments:
        values = turnovers[instrument.symbol]
        ok = not values.empty
        rows.append(
            {
                "symbol": instrument.symbol,
                "company_id": instrument.company_id,
                "role": instrument.role,
                "venue": instrument.venue,
                "status": "ok" if ok else "missing",
                "last_date": values.index[-1].date().isoformat() if ok else None,
                "source_url": instrument.source_url,
            }
        )
        if not ok:
            warnings.append(f"{instrument.symbol}: no valid daily close/volume data")
    return rows, warnings


def _build_series(
    definition: SeriesDefinition,
    instruments: Sequence[Instrument],
    turnovers: Mapping[str, pd.Series],
    as_of: pd.Timestamp,
) -> dict:
    primary = turnovers.get(definition.primary_symbol, pd.Series(dtype=float))
    anchor = primary.index[primary.index <= as_of]
    company_legs = [
        item
        for item in instruments
        if item.company_id == definition.company_id and _in_scope(item, definition.scope)
    ]
    underlying = [item for item in company_legs if item.role == "underlying"]
    leveraged = [item for item in company_legs if item.role == "leveraged"]
    long_legs = [item for item in leveraged if item.leverage_multiple > 0]
    short_legs = [item for item in leveraged if item.leverage_multiple < 0]

    denominator = _sum_turnover(underlying, anchor, turnovers)
    long_turnover = _sum_turnover(long_legs, anchor, turnovers)
    short_turnover = _sum_turnover(short_legs, anchor, turnovers)
    weighted = _sum_turnover(leveraged, anchor, turnovers, weighted=True)
    valid = denominator.gt(0)
    denominator = denominator.loc[valid]
    long_turnover = long_turnover.loc[valid]
    short_turnover = short_turnover.loc[valid]
    weighted = weighted.loc[valid]
    ratio = (long_turnover + short_turnover) / denominator
    weighted_ratio = weighted / denominator

    points = [
        {"date": date.date().isoformat(), "ratio": float(value)}
        for date, value in ratio.items()
    ]
    latest = None
    if not ratio.empty:
        change_1d = float(ratio.iloc[-1] - ratio.iloc[-2]) if len(ratio) > 1 else None
        latest = {
            "date": ratio.index[-1].date().isoformat(),
            "ratio": float(ratio.iloc[-1]),
            "change_1d": change_1d,
            "long_turnover_usd": float(long_turnover.iloc[-1]),
            "short_turnover_usd": float(short_turnover.iloc[-1]),
            "leverage_weighted_ratio": float(weighted_ratio.iloc[-1]),
            "underlying_turnover_usd": float(denominator.iloc[-1]),
        }
    return {
        "id": definition.id,
        "company_id": definition.company_id,
        "company_name": definition.company_name,
        "scope": definition.scope,
        "color": definition.color,
        "latest": latest,
        "points": points,
    }


def build_memory_leverage_report(
    instruments: Sequence[Instrument],
    definitions: Sequence[SeriesDefinition],
    batch: MarketDataBatch,
    *,
    generated_at: datetime | None = None,
    registry_version: str = "2026-07-16",
) -> dict:
    """Build the stable API payload from already-fetched, untrusted daily bars."""
    turnovers = {
        instrument.symbol: _turnover_usd(instrument, batch.histories)
        for instrument in instruments
    }
    primary_latest = [
        turnovers[definition.primary_symbol].index[-1]
        for definition in definitions
        if not turnovers.get(definition.primary_symbol, pd.Series(dtype=float)).empty
    ]
    if not primary_latest:
        raise MemoryLeverageDataError("no primary-listing data is usable")
    as_of = min(primary_latest)
    coverage, warnings = _coverage(instruments, turnovers)
    return {
        "generated_at": _utc_iso(generated_at),
        "as_of": as_of.date().isoformat(),
        "methodology": {
            "ratio": "leveraged_product_turnover_usd / underlying_turnover_usd",
            "weighted_ratio": (
                "abs(leverage_multiple) weighted numerator / underlying_turnover_usd"
            ),
            "data_source": "Yahoo Finance via yfinance",
            "registry_version": registry_version,
        },
        "series": [
            _build_series(definition, instruments, turnovers, as_of)
            for definition in definitions
        ],
        "coverage": coverage,
        "warnings": warnings,
    }
