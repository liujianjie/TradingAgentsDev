"""Memory-sector leverage-ratio calculation.

The metric compares actual traded notional in single-stock leveraged products
with actual traded notional in the corresponding common shares and depositary
receipts.  It is a market-activity measure, not a balance-sheet leverage ratio.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
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


_SRC = {
    "sndg": "https://leverageshares.com/us/etfs/leverage-shares-2x-long-sndk-daily-etf/",
    "sndu": "https://www.rexshares.com/rex-shares-launches-t-rex-2x-paas-paau-2x-sndk-sndu-etfs/",
    "sndx": "https://www.sec.gov/Archives/edgar/data/1587982/000121390026046509/ea0285820-01_485bpos.htm",
    "mu": "https://www.direxion.com/product/daily-mu-bull-and-bear-leveraged-single-stock-etfs",
    "mull": "https://graniteshares.com/etfs/mull/",
    "mu2": "https://leverageshares.com/documents/factsheet/2x_mu_factsheet.pdf",
    "kr": "https://www.samsungfund.com/etf/insight/newsroom/view.do?seq=76433",
    "sk_hk": "https://www.hkex.com.hk/News/Products-and-Services/2026/260527news",
    "sk_eu": "https://leverageshares.com/documents/ft/3x_hnx3_ft_cbi.pdf",
    "sk_us": "https://www.direxion.com/press-release/direxion-launches-skhl-2x-daily-exposure-to-sk-hynix",
    "sk_us_multi": "https://graniteshares.com/etfs/leveraged/",
    "samsung_hk": "https://www.hkex.com.hk/News/Products-and-Services/2026/260527news",
    "samsung_eu": "https://leverageshares.com/documents/factsheet/3x_smg3_factsheet.pdf",
}


def _instrument(
    symbol: str,
    company_id: str,
    role: Role,
    scope: Scope,
    currency: str,
    venue: str,
    *,
    leverage: float = 1.0,
    primary: bool = False,
    source: str = "",
) -> Instrument:
    return Instrument(
        symbol=symbol,
        company_id=company_id,
        role=role,
        scope=scope,
        currency=currency,
        venue=venue,
        leverage_multiple=leverage,
        is_primary=primary,
        name=symbol,
        source_url=source,
    )


def default_instruments() -> tuple[Instrument, ...]:
    """Return the reviewed 2026-07-16 instrument registry."""
    i = _instrument
    return (
        i("SNDK", "sandisk", "underlying", "all", "USD", "NASDAQ", primary=True),
        i("SNXX", "sandisk", "leveraged", "all", "USD", "CBOE", leverage=2, source=_SRC["sndx"]),
        i("SNDU", "sandisk", "leveraged", "all", "USD", "CBOE", leverage=2, source=_SRC["sndu"]),
        i("SNDG", "sandisk", "leveraged", "all", "USD", "CBOE", leverage=2, source=_SRC["sndg"]),
        i("SNDQ", "sandisk", "leveraged", "all", "USD", "CBOE", leverage=-2, source=_SRC["sndx"]),
        i("MU", "micron", "underlying", "all", "USD", "NASDAQ", primary=True),
        i("MUU", "micron", "leveraged", "all", "USD", "NASDAQ", leverage=2, source=_SRC["mu"]),
        i("MULL", "micron", "leveraged", "all", "USD", "NASDAQ", leverage=2, source=_SRC["mull"]),
        i("MU2.L", "micron", "leveraged", "all", "USD", "LSE", leverage=2, source=_SRC["mu2"]),
        i("MUD", "micron", "leveraged", "all", "USD", "NASDAQ", leverage=-1, source=_SRC["mu"]),
        i("000660.KS", "sk_hynix", "underlying", "kr", "KRW", "KRX", primary=True),
        i("SKHY", "sk_hynix", "underlying", "all", "USD", "NASDAQ"),
        i("0193T0.KS", "sk_hynix", "leveraged", "kr", "KRW", "KRX", leverage=2, source=_SRC["kr"]),
        i("0195S0.KS", "sk_hynix", "leveraged", "kr", "KRW", "KRX", leverage=2, source=_SRC["kr"]),
        i("0197W0.KS", "sk_hynix", "leveraged", "kr", "KRW", "KRX", leverage=2, source=_SRC["kr"]),
        i("0194T0.KS", "sk_hynix", "leveraged", "kr", "KRW", "KRX", leverage=2, source=_SRC["kr"]),
        i("0192L0.KS", "sk_hynix", "leveraged", "kr", "KRW", "KRX", leverage=2, source=_SRC["kr"]),
        i("0198D0.KS", "sk_hynix", "leveraged", "kr", "KRW", "KRX", leverage=2, source=_SRC["kr"]),
        i("0194R0.KS", "sk_hynix", "leveraged", "kr", "KRW", "KRX", leverage=2, source=_SRC["kr"]),
        i("0197X0.KS", "sk_hynix", "leveraged", "kr", "KRW", "KRX", leverage=-2, source=_SRC["kr"]),
        i("7709.HK", "sk_hynix", "leveraged", "all", "HKD", "HKEX", leverage=2, source=_SRC["sk_hk"]),
        i("HNX3.L", "sk_hynix", "leveraged", "all", "USD", "LSE", leverage=3, source=_SRC["sk_eu"]),
        i("SKHL", "sk_hynix", "leveraged", "all", "USD", "NYSE", leverage=2, source=_SRC["sk_us"]),
        i("SKHX", "sk_hynix", "leveraged", "all", "USD", "CBOE", leverage=2, source=_SRC["sk_us_multi"]),
        i("SKUU", "sk_hynix", "leveraged", "all", "USD", "NASDAQ", leverage=2, source=_SRC["sk_us_multi"]),
        i("SKDD", "sk_hynix", "leveraged", "all", "USD", "NASDAQ", leverage=-2, source=_SRC["sk_us_multi"]),
        i("005930.KS", "samsung", "underlying", "kr", "KRW", "KRX", primary=True),
        i("SMSN.IL", "samsung", "underlying", "all", "USD", "LSE"),
        i("0193W0.KS", "samsung", "leveraged", "kr", "KRW", "KRX", leverage=2, source=_SRC["kr"]),
        i("0195R0.KS", "samsung", "leveraged", "kr", "KRW", "KRX", leverage=2, source=_SRC["kr"]),
        i("0194M0.KS", "samsung", "leveraged", "kr", "KRW", "KRX", leverage=2, source=_SRC["kr"]),
        i("0192M0.KS", "samsung", "leveraged", "kr", "KRW", "KRX", leverage=2, source=_SRC["kr"]),
        i("0193K0.KS", "samsung", "leveraged", "kr", "KRW", "KRX", leverage=2, source=_SRC["kr"]),
        i("0194N0.KS", "samsung", "leveraged", "kr", "KRW", "KRX", leverage=2, source=_SRC["kr"]),
        i("0198B0.KS", "samsung", "leveraged", "kr", "KRW", "KRX", leverage=2, source=_SRC["kr"]),
        i("0193L0.KS", "samsung", "leveraged", "kr", "KRW", "KRX", leverage=-2, source=_SRC["kr"]),
        i("7747.HK", "samsung", "leveraged", "all", "HKD", "HKEX", leverage=2, source=_SRC["samsung_hk"]),
        i("7347.HK", "samsung", "leveraged", "all", "HKD", "HKEX", leverage=-2, source=_SRC["samsung_hk"]),
        i("SMG3.L", "samsung", "leveraged", "all", "USD", "LSE", leverage=3, source=_SRC["samsung_eu"]),
        i("285A.T", "kioxia", "underlying", "all", "JPY", "TSE", primary=True),
    )


def default_series_definitions() -> tuple[SeriesDefinition, ...]:
    return (
        SeriesDefinition("sandisk_all", "sandisk", "SanDisk", "all", "SNDK", "#58A6FF"),
        SeriesDefinition("micron_all", "micron", "Micron", "all", "MU", "#35B8A0"),
        SeriesDefinition("sk_hynix_all", "sk_hynix", "SK hynix (all)", "all", "000660.KS", "#D99000"),
        SeriesDefinition("sk_hynix_kr", "sk_hynix", "SK hynix (KR)", "kr", "000660.KS", "#F2B84B"),
        SeriesDefinition("samsung_all", "samsung", "Samsung (all)", "all", "005930.KS", "#138A42"),
        SeriesDefinition("samsung_kr", "samsung", "Samsung (KR)", "kr", "005930.KS", "#50B36A"),
        SeriesDefinition("kioxia_all", "kioxia", "Kioxia", "all", "285A.T", "#9B7CE8"),
    )


def _extract_downloaded_frame(
    downloaded: pd.DataFrame,
    symbol: str,
    symbol_count: int,
) -> pd.DataFrame:
    if downloaded is None or downloaded.empty:
        return pd.DataFrame()
    if isinstance(downloaded.columns, pd.MultiIndex):
        for level in range(downloaded.columns.nlevels):
            if symbol in downloaded.columns.get_level_values(level):
                frame = downloaded.xs(symbol, axis=1, level=level, drop_level=True)
                if isinstance(frame, pd.Series):
                    frame = frame.to_frame()
                return frame
        return pd.DataFrame()
    if symbol_count == 1:
        return downloaded.copy()
    return pd.DataFrame()


class YFinanceMarketDataProvider:
    """Bulk daily-bar adapter for the project's existing yfinance dependency."""

    def fetch(
        self,
        symbols: Sequence[str],
        *,
        start: date,
        end: date,
    ) -> MarketDataBatch:
        import yfinance as yf

        unique_symbols = tuple(dict.fromkeys(symbols))
        try:
            # Current signature and parameter semantics:
            # https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html
            downloaded = yf.download(
                tickers=list(unique_symbols),
                start=start.isoformat(),
                end=end.isoformat(),
                interval="1d",
                group_by="ticker",
                auto_adjust=False,
                repair=False,
                keepna=False,
                progress=False,
                threads=False,
                timeout=20,
                multi_level_index=True,
            )
        except Exception:
            return MarketDataBatch(
                histories={},
                errors={symbol: "bulk_download_failed" for symbol in unique_symbols},
            )

        histories: dict[str, pd.DataFrame] = {}
        errors: dict[str, str] = {}
        for symbol in unique_symbols:
            frame = _extract_downloaded_frame(downloaded, symbol, len(unique_symbols))
            if frame.empty or "Close" not in frame.columns:
                errors[symbol] = "no_daily_data"
                continue
            histories[symbol] = frame
        return MarketDataBatch(histories=histories, errors=errors)


class MemoryLeverageService:
    """Fetch the reviewed registry and build one report without persistence."""

    def __init__(
        self,
        provider: YFinanceMarketDataProvider | None = None,
        instruments: Sequence[Instrument] | None = None,
        definitions: Sequence[SeriesDefinition] | None = None,
    ) -> None:
        self.provider = provider or YFinanceMarketDataProvider()
        self.instruments = tuple(instruments or default_instruments())
        self.definitions = tuple(definitions or default_series_definitions())

    def get_report(self, *, days: int) -> dict:
        if days <= 0:
            raise ValueError("days must be positive")
        now = datetime.now(timezone.utc)
        fx_symbols = [
            _FX_TO_USD[item.currency.upper()][0]
            for item in self.instruments
            if item.currency.upper() in _FX_TO_USD
        ]
        symbols = [item.symbol for item in self.instruments]
        symbols.extend(fx_symbols)
        batch = self.provider.fetch(
            tuple(dict.fromkeys(symbols)),
            start=now.date() - timedelta(days=days + 7),
            end=now.date() + timedelta(days=1),
        )
        return build_memory_leverage_report(
            self.instruments,
            self.definitions,
            batch,
            generated_at=now,
        )
