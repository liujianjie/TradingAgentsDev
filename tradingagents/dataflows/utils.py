import os
import re
import json
import pandas as pd
from datetime import date, timedelta, datetime
from typing import Annotated

SavePathType = Annotated[str, "File path to save data. If None, data is not saved."]

# Tickers can contain letters, digits, dot, dash, underscore, and caret
# (for index symbols like ^GSPC). Anything else is rejected so the value
# never escapes a containing directory when interpolated into a path.
_TICKER_PATH_RE = re.compile(r"^[A-Za-z0-9._\-\^]+$")

# 港股代码：纯数字 + .HK 后缀（大小写均可）。其他市场不匹配，保持原样。
_HK_TICKER_RE = re.compile(r"^(\d+)\.(?:HK|hk)$")


def to_yfinance_symbol(ticker: str) -> str:
    """把 ticker 归一到 Yahoo Finance 的格式约定（目前只处理港股前导 0）。

    港交所主板代码是 5 位（带前导 0，如 07709、00700），但 Yahoo 用「去前导 0 后
    补足 4 位」：07709→7709、00700→0700、09988→9988。用户按券商/港交所习惯输入
    5 位代码（07709.HK）会让 yfinance 404——代码真实存在，只是格式不符 Yahoo 约定。

    归一**下沉到 yfinance vendor 层**（本函数被各 yfinance 取数入口调用），使得绕过
    analyzer 入口、直接调 vendor 传 07709.HK 也能取数。严格只匹配「纯数字.HK」：
    其他市场（美股无后缀、A股 .SS/.SZ、**韩股 .KS 同样有前导 0 但绝不能动**、指数
    ^GSPC、带横杠代码）一律原样返回。akshare 有自己的格式适配（``to_akshare_symbol``）。
    """
    t = ticker.strip()
    m = _HK_TICKER_RE.match(t)
    if m:
        code = (m.group(1).lstrip("0") or "0").zfill(4)
        return f"{code}.HK"
    return t


def safe_ticker_component(value: str, *, max_len: int = 32) -> str:
    """Validate ``value`` is safe to interpolate into a filesystem path.

    Tickers come from user CLI input or from LLM tool calls, both of which
    can be influenced by attacker-controlled content (e.g. prompt injection
    embedded in fetched news). Without validation, a value like
    ``"../../../etc/foo"`` flows into ``os.path.join`` / ``Path /`` and
    escapes the configured cache, checkpoint, or results directory.

    Returns ``value`` unchanged when it matches the allowed pattern; raises
    ``ValueError`` otherwise.
    """
    if not isinstance(value, str) or not value:
        raise ValueError(f"ticker must be a non-empty string, got {value!r}")
    if len(value) > max_len:
        raise ValueError(f"ticker exceeds {max_len} chars: {value!r}")
    if not _TICKER_PATH_RE.fullmatch(value):
        raise ValueError(
            f"ticker contains characters not allowed in a filesystem path: {value!r}"
        )
    # The regex above allows '.', so values like '.', '..', '...' would pass,
    # and as a path component they traverse the parent directory. Reject any
    # value that's only dots.
    if set(value) == {"."}:
        raise ValueError(f"ticker cannot consist solely of dots: {value!r}")
    return value


def save_output(data: pd.DataFrame, tag: str, save_path: SavePathType = None) -> None:
    if save_path:
        data.to_csv(save_path, encoding="utf-8")
        print(f"{tag} saved to {save_path}")


def get_current_date():
    return date.today().strftime("%Y-%m-%d")


def decorate_all_methods(decorator):
    def class_decorator(cls):
        for attr_name, attr_value in cls.__dict__.items():
            if callable(attr_value):
                setattr(cls, attr_name, decorator(attr_value))
        return cls

    return class_decorator


def get_next_weekday(date):

    if not isinstance(date, datetime):
        date = datetime.strptime(date, "%Y-%m-%d")

    if date.weekday() >= 5:
        days_to_add = 7 - date.weekday()
        next_weekday = date + timedelta(days=days_to_add)
        return next_weekday
    else:
        return date
