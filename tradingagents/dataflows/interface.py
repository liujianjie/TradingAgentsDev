import logging
import threading
from typing import Annotated

logger = logging.getLogger(__name__)

# Import from vendor-specific modules
from .y_finance import (
    get_YFin_data_online,
    get_stock_stats_indicators_window,
    get_fundamentals as get_yfinance_fundamentals,
    get_balance_sheet as get_yfinance_balance_sheet,
    get_cashflow as get_yfinance_cashflow,
    get_income_statement as get_yfinance_income_statement,
    get_insider_transactions as get_yfinance_insider_transactions,
)
from .yfinance_news import get_news_yfinance, get_global_news_yfinance
from .alpha_vantage import (
    get_stock as get_alpha_vantage_stock,
    get_indicator as get_alpha_vantage_indicator,
    get_fundamentals as get_alpha_vantage_fundamentals,
    get_balance_sheet as get_alpha_vantage_balance_sheet,
    get_cashflow as get_alpha_vantage_cashflow,
    get_income_statement as get_alpha_vantage_income_statement,
    get_insider_transactions as get_alpha_vantage_insider_transactions,
    get_news as get_alpha_vantage_news,
    get_global_news as get_alpha_vantage_global_news,
)
from .alpha_vantage_common import AlphaVantageRateLimitError
from .akshare_utils import (
    get_akshare_stock_data,
    get_akshare_indicators,
    get_akshare_news,
    get_akshare_fundamentals,
    get_akshare_balance_sheet,
    get_akshare_cashflow,
    get_akshare_income_statement,
    AkshareUnavailableError,
    market_of,
)

# Configuration and routing logic
from .config import get_config

# Tools organized by category
TOOLS_CATEGORIES = {
    "core_stock_apis": {
        "description": "OHLCV stock price data",
        "tools": [
            "get_stock_data"
        ]
    },
    "technical_indicators": {
        "description": "Technical analysis indicators",
        "tools": [
            "get_indicators"
        ]
    },
    "fundamental_data": {
        "description": "Company fundamentals",
        "tools": [
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement"
        ]
    },
    "news_data": {
        "description": "News and insider data",
        "tools": [
            "get_news",
            "get_global_news",
            "get_insider_transactions",
        ]
    }
}

VENDOR_LIST = [
    "yfinance",
    "alpha_vantage",
    "akshare",
]

# Mapping of methods to their vendor-specific implementations
VENDOR_METHODS = {
    # core_stock_apis
    "get_stock_data": {
        "alpha_vantage": get_alpha_vantage_stock,
        "yfinance": get_YFin_data_online,
        "akshare": get_akshare_stock_data,
    },
    # technical_indicators
    "get_indicators": {
        "akshare": get_akshare_indicators,
        "alpha_vantage": get_alpha_vantage_indicator,
        "yfinance": get_stock_stats_indicators_window,
    },
    # fundamental_data
    "get_fundamentals": {
        "akshare": get_akshare_fundamentals,
        "alpha_vantage": get_alpha_vantage_fundamentals,
        "yfinance": get_yfinance_fundamentals,
    },
    "get_balance_sheet": {
        "akshare": get_akshare_balance_sheet,
        "alpha_vantage": get_alpha_vantage_balance_sheet,
        "yfinance": get_yfinance_balance_sheet,
    },
    "get_cashflow": {
        "akshare": get_akshare_cashflow,
        "alpha_vantage": get_alpha_vantage_cashflow,
        "yfinance": get_yfinance_cashflow,
    },
    "get_income_statement": {
        "akshare": get_akshare_income_statement,
        "alpha_vantage": get_alpha_vantage_income_statement,
        "yfinance": get_yfinance_income_statement,
    },
    # news_data
    "get_news": {
        "akshare": get_akshare_news,
        "alpha_vantage": get_alpha_vantage_news,
        "yfinance": get_news_yfinance,
    },
    "get_global_news": {
        "yfinance": get_global_news_yfinance,
        "alpha_vantage": get_alpha_vantage_global_news,
    },
    "get_insider_transactions": {
        "alpha_vantage": get_alpha_vantage_insider_transactions,
        "yfinance": get_yfinance_insider_transactions,
    },
}

def get_category_for_method(method: str) -> str:
    """Get the category that contains the specified method."""
    for category, info in TOOLS_CATEGORIES.items():
        if method in info["tools"]:
            return category
    raise ValueError(f"Method '{method}' not found in any category")

def get_vendor(category: str, method: str = None) -> str:
    """Get the configured vendor for a data category or specific tool method.
    Tool-level configuration takes precedence over category-level.
    """
    config = get_config()

    # Check tool-level configuration first (if method provided)
    if method:
        tool_vendors = config.get("tool_vendors", {})
        if method in tool_vendors:
            return tool_vendors[method]

    # Fall back to category-level configuration
    return config.get("data_vendors", {}).get(category, "default")

# 各市场的默认 vendor 优先链（config 未显式指定时按 ticker 市场自动选）。
# akshare 对某 method 无实现时，route_to_vendor 会自动跳到链中下一个，故这里
# 统一写 akshare 优先即可——尚未实现的方法天然落到 yfinance。
_MARKET_VENDOR_CHAIN = {
    "cn_a":  ["akshare", "yfinance"],
    "hk":    ["akshare", "yfinance"],
    "other": ["yfinance", "alpha_vantage"],
}


def _auto_vendor_chain(method: str, args: tuple) -> list:
    """按 ticker 市场返回默认 vendor 优先链。

    get_global_news 是全市场宏观新闻，akshare 无此能力，恒走 yfinance/AV（且其
    args[0] 是日期而非 ticker，不该参与市场判断）。其余方法 args[0] 即 ticker。
    """
    if method == "get_global_news":
        return ["yfinance", "alpha_vantage"]
    ticker = str(args[0]) if args else ""
    return _MARKET_VENDOR_CHAIN.get(market_of(ticker), _MARKET_VENDOR_CHAIN["other"])


# ---------------------------------------------------------------------------
# 数据源溯源（透明展示「本次用了哪个源 / 降级了什么」，见 PLAN「数据源策略」D2-b）
# ---------------------------------------------------------------------------
# 用 threading.local 隔离每次分析：分析在 executor worker 线程同步跑，route_to_vendor
# 与 reset/format 同线程故能采集到（market/基本面/新闻分析员均主线程调用）。注意：经
# ThreadPoolExecutor 子线程的调用（如 sentiment 并行抓 news）不在此线程，不会被采集——
# 但 news 已被新闻分析员主线程记录，冗余无碍；社交源降级由 sentiment 节点体(主线程)单独记。
_provenance = threading.local()

# method → 友好中文类别名（多个 method 归一到同一类别，如三大报表都算"基本面"）
_PROVENANCE_LABELS = {
    "get_stock_data": "行情",
    "get_indicators": "技术指标",
    "get_fundamentals": "基本面",
    "get_balance_sheet": "基本面",
    "get_cashflow": "基本面",
    "get_income_statement": "基本面",
    "get_news": "个股新闻",
    "get_global_news": "全球新闻",
    "get_insider_transactions": "内部交易",
}


def reset_provenance() -> None:
    """清空当前线程的数据源溯源记录。每次分析开始（propagate 前）调用。"""
    _provenance.records = []


def record_provenance(category: str, served_by, degraded=None, note: str = "") -> None:
    """记录一条溯源：category 类别 / served_by 实际命中源(None=无数据) / degraded 试过但
    没用上的源 / note 备注。route_to_vendor 自动记录；社交情感等不走路由的源可手动记。"""
    recs = getattr(_provenance, "records", None)
    if recs is None:
        recs = []
        _provenance.records = recs
    recs.append({
        "category": category,
        "served_by": served_by,
        "degraded": list(degraded or []),
        "note": note,
    })


def get_provenance() -> list:
    """返回当前线程已记录的溯源（副本）。"""
    return list(getattr(_provenance, "records", []))


def format_provenance_summary() -> str:
    """把本线程溯源记录按类别聚合成 markdown 表格（供报告"数据源溯源"段）。无记录返回空串。

    只返回**纯表格**（不含标题），由各消费方自加标题：C# 报告加 "### 数据源溯源"、
    UniApp 用卡片标题"数据源"，避免标题重复。
    """
    recs = get_provenance()
    if not recs:
        return ""
    agg, order = {}, []
    for r in recs:
        cat = r["category"]
        if cat not in agg:
            agg[cat] = {"served": set(), "degraded": set(), "notes": set()}
            order.append(cat)
        if r["served_by"]:
            agg[cat]["served"].add(r["served_by"])
        agg[cat]["degraded"].update(r["degraded"])
        if r["note"]:
            agg[cat]["notes"].add(r["note"])

    lines = ["| 数据 | 实际来源 | 降级/备注 |", "|---|---|---|"]
    for cat in order:
        a = agg[cat]
        served = "、".join(sorted(a["served"])) if a["served"] else "—（无数据）"
        deg = sorted(a["degraded"] - a["served"])  # 降级 = 试过但最终没命中的源
        remark = "；".join(([f"降级跳过 {', '.join(deg)}"] if deg else []) + sorted(a["notes"])) or "—"
        lines.append(f"| {cat} | {served} | {remark} |")
    return "\n".join(lines)


def _looks_empty(result) -> bool:
    """判断 vendor 返回是否"无有效数据"——None / 空串 / 形如 "No ... found ..." 的占位串。

    yfinance 各取数函数对无数据统一返回 "No <X> data found for symbol ..." /
    "No data found for symbol ..." / "No news found for ..."（均以 "No " 开头且含
    "found"）。akshare 无数据是抛 AkshareUnavailableError（走异常分支，不在此判断）。
    AV 返回原始 JSON/CSV，其空响应不在此特判（本项目 AV 无 key、为兜底末位，命中即
    抛异常被下方捕获）。判为空时路由会继续尝试链中下一个源。
    """
    if result is None:
        return True
    if isinstance(result, str):
        s = result.strip()
        if not s:
            return True
        low = s.lower()
        if low.startswith("no ") and "found" in low:
            return True
    return False


def route_to_vendor(method: str, *args, **kwargs):
    """Route method calls to appropriate vendor implementation with fallback support.

    Vendor 选择：config 显式指定（如 UI 强制某源）优先；否则按 ticker 市场自动选
    （A股/港股→akshare 优先，美股/其他→yfinance 优先）。

    Fallback 触发两类情况，均自动转链中下一个源：
      1. vendor **抛异常**（限流 / akshare 不可用 / AV 无 key / 网络错等，广义捕获）
      2. vendor **返回空数据**（``_looks_empty``，如 yfinance 对小众标的的 "No data found"）
    全链都空 → 返回最后一个源的清晰"无数据"提示（不裸崩）；全链都异常 → 抛聚合异常。
    """
    category = get_category_for_method(method)
    vendor_config = get_vendor(category, method)

    # config 为空 / "auto" / "default" → 按市场自动；否则用 config 显式指定的 vendor
    if not vendor_config or vendor_config in ("auto", "default"):
        primary_vendors = _auto_vendor_chain(method, args)
    else:
        primary_vendors = [v.strip() for v in vendor_config.split(',')]

    if method not in VENDOR_METHODS:
        raise ValueError(f"Method '{method}' not supported")

    # Build fallback chain: primary vendors first, then remaining available vendors
    all_available_vendors = list(VENDOR_METHODS[method].keys())
    fallback_vendors = primary_vendors.copy()
    for vendor in all_available_vendors:
        if vendor not in fallback_vendors:
            fallback_vendors.append(vendor)

    label = _PROVENANCE_LABELS.get(method, method)
    tried_failed = []  # 试过但异常/空的源 → 溯源里记为"降级跳过"
    last_empty = None  # 记住最后一个"返回空"的结果，全链无数据时回退给它（清晰提示而非裸崩）
    errors = []        # 记录各源异常，全链都异常时聚合抛出，便于排查
    for vendor in fallback_vendors:
        if vendor not in VENDOR_METHODS[method]:
            continue

        vendor_impl = VENDOR_METHODS[method][vendor]
        impl_func = vendor_impl[0] if isinstance(vendor_impl, list) else vendor_impl

        try:
            result = impl_func(*args, **kwargs)
        except Exception as e:
            # 广义捕获是有意为之：fallback 链的语义就是"换源直到有数据"，逐条枚举异常
            # 类型既不全也脆（限流 / akshare 不可用 / AV 无 key 的 ValueError / 网络错…）。
            # WARNING 日志保证 bug 仍可见；全链失败时下方抛聚合异常，不掩盖系统性问题。
            logger.warning("vendor %s failed for %s: %s", vendor, method, str(e)[:160])
            errors.append((vendor, repr(e)[:160]))
            tried_failed.append(vendor)
            continue

        if _looks_empty(result):
            logger.info("vendor %s 对 %s 返回空数据，尝试链中下一个源", vendor, method)
            last_empty = result
            tried_failed.append(vendor)
            continue

        record_provenance(label, vendor, degraded=tried_failed)  # 命中源 + 此前降级的源
        return result  # 拿到有效数据

    # 所有源都无数据/异常
    record_provenance(label, None, degraded=tried_failed)
    if last_empty is not None:
        return last_empty  # 返回最后一个清晰"无数据"提示
    raise RuntimeError(f"所有数据源对 '{method}' 均失败: {errors}")