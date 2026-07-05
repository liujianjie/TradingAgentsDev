"""轻量数据 HTTP 接口，给 AIStockingNews（Node 主项目）做 M1 数据 sidecar。

7 个端点全是对 tradingagents.dataflows 已有函数的薄包装，**不动 dataflows 内部代码**。
方便从外部仓库 pull 上游更新时只与 main.py 的 include_router 行冲突，data.py 单独维护。
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/data", tags=["data"])


def _today_iso() -> str:
    return date.today().isoformat()


def _days_ago_iso(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# 1. quote — 最近报价（实际取近 10 天 OHLCV 字符串，AIStockingNews 端解析最新一行）
# ---------------------------------------------------------------------------
@router.get("/quote")
def quote(symbol: str = Query(..., description="ticker，如 NVDA / 600519.SS / 7709.HK")):
    from tradingagents.dataflows.interface import route_to_vendor, reset_provenance

    reset_provenance()
    try:
        text = route_to_vendor("get_stock_data", symbol, _days_ago_iso(10), _today_iso())
        return {"symbol": symbol, "raw": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"quote failed: {e}")


# ---------------------------------------------------------------------------
# 2. kline — 历史 K 线（默认近 60 个交易日）
# ---------------------------------------------------------------------------
@router.get("/kline")
def kline(
    symbol: str = Query(..., description="ticker"),
    period: str = Query("daily", description="周期，目前仅支持 daily"),
    days: int = Query(60, ge=1, le=1000, description="回看天数"),
):
    from tradingagents.dataflows.interface import route_to_vendor, reset_provenance

    reset_provenance()
    try:
        # 回看天数包含周末，多取一倍 buffer
        text = route_to_vendor("get_stock_data", symbol, _days_ago_iso(days * 2), _today_iso())
        return {"symbol": symbol, "period": period, "days": days, "raw": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"kline failed: {e}")


# ---------------------------------------------------------------------------
# 3. news — 个股新闻（A/港股优先中文，美股英文，含 fallback）
# ---------------------------------------------------------------------------
@router.get("/news")
def news(
    symbol: str = Query(..., description="ticker"),
    days: int = Query(7, ge=1, le=30, description="回看天数"),
):
    from tradingagents.dataflows.interface import route_to_vendor, reset_provenance

    reset_provenance()
    try:
        text = route_to_vendor("get_news", symbol, _days_ago_iso(days), _today_iso())
        return {"symbol": symbol, "days": days, "raw": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"news failed: {e}")


# ---------------------------------------------------------------------------
# 4. sentiment — 中文情感（千股千评 + 热度趋势 + 热门关键词），仅 A 股 / 港股
# ---------------------------------------------------------------------------
@router.get("/sentiment")
def sentiment(symbol: str = Query(..., description="A 股或港股 ticker（.SS/.SZ/.HK）")):
    from tradingagents.dataflows.akshare_utils import market_of
    from tradingagents.dataflows.chinese_sentiment import (
        fetch_cn_comment,
        fetch_cn_hot_trend,
        fetch_cn_hot_keyword,
        fetch_hk_hot_trend,
    )

    market = market_of(symbol)
    if market not in ("cn_a", "hk"):
        raise HTTPException(
            status_code=400,
            detail=f"sentiment only supports cn_a/hk markets, got: {market}",
        )
    try:
        if market == "cn_a":
            return {
                "symbol": symbol,
                "market": market,
                "comment": fetch_cn_comment(symbol),
                "hot_trend": fetch_cn_hot_trend(symbol),
                "hot_keyword": fetch_cn_hot_keyword(symbol),
            }
        return {
            "symbol": symbol,
            "market": market,
            "hot_trend": fetch_hk_hot_trend(symbol),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"sentiment failed: {e}")


# ---------------------------------------------------------------------------
# 5. cn_features — 北向资金 + 龙虎榜（仅 A 股）
# ---------------------------------------------------------------------------
@router.get("/cn_features")
def cn_features(symbol: str = Query(..., description="A 股 ticker（.SS/.SZ）")):
    from tradingagents.dataflows.akshare_cn_features import (
        get_north_bound_holding,
        get_dragon_tiger_list,
    )
    from tradingagents.dataflows.akshare_utils import market_of

    market = market_of(symbol)
    if market != "cn_a":
        raise HTTPException(
            status_code=400,
            detail=f"cn_features only supports cn_a market, got: {market}",
        )
    try:
        return {
            "symbol": symbol,
            "north_bound": get_north_bound_holding(symbol),
            "dragon_tiger": get_dragon_tiger_list(symbol),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"cn_features failed: {e}")


# ---------------------------------------------------------------------------
# 6. fund_nav — 场外公募基金日级净值（akshare 直调，TradingAgents 原本无此能力）
# ---------------------------------------------------------------------------
@router.get("/fund_nav")
def fund_nav(symbol: str = Query(..., description="场外基金 6 位代码，如 018229")):
    try:
        import akshare as ak

        df = ak.fund_open_fund_info_em(symbol=symbol, indicator="单位净值走势")
        return {
            "symbol": symbol,
            "indicator": "单位净值走势",
            "rows": df.to_dict(orient="records"),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"akshare fund_open_fund_info_em failed: {e}"
        )


# ---------------------------------------------------------------------------
# 7. theme_etfs — 主题 ETF 自动发现（基于 ETF 全列表 + 关键词过滤）
# ---------------------------------------------------------------------------
@router.get("/theme_etfs")
def theme_etfs(
    theme: str = Query(..., description="主题关键词，如 CPO / 半导体 / 通信 / 光通信"),
    limit: int = Query(30, ge=1, le=100),
):
    try:
        import akshare as ak

        df = ak.fund_etf_category_sina(symbol="ETF基金")
        if df is None or df.empty:
            return {"theme": theme, "count": 0, "etfs": []}

        # 优先按 "名称" 列模糊匹配；列名变化时 fallback 全表
        name_col = None
        for col in ("名称", "name", "基金简称"):
            if col in df.columns:
                name_col = col
                break

        if name_col:
            filtered = df[df[name_col].astype(str).str.contains(theme, case=False, na=False)]
        else:
            filtered = df

        return {
            "theme": theme,
            "count": len(filtered),
            "etfs": filtered.head(limit).to_dict(orient="records"),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"akshare fund_etf_category_sina failed: {e}"
        )


# ---------------------------------------------------------------------------
# 8. theme_heatmap — A 股概念/行业板块实时行情排序（AIStockingNews M2-3）
# ---------------------------------------------------------------------------
@router.get("/theme_heatmap")
def theme_heatmap(
    category: str = Query("concept", description="板块类型 concept(概念) / industry(行业)"),
    limit: int = Query(50, ge=1, le=200, description="返回 top N（按涨幅降序，含负涨幅）"),
):
    """A 股概念/行业板块实时行情。

    输出 schema:
      {category, count, boards: [
        {rank, name, code, latest_price, change_pct, change_amount,
         total_market_cap, turnover_rate, up_count, down_count,
         leader_name, leader_change_pct}, ...
      ]}

    数据源:
      - concept → ak.stock_board_concept_name_em()  ~370 个概念板块
      - industry → ak.stock_board_industry_name_em() ~86 个行业板块
    返回字段为 akshare 列名（中文）→ 蛇形映射，未知列原样保留并打前缀 raw_。
    """
    try:
        import akshare as ak

        if category == "concept":
            df = ak.stock_board_concept_name_em()
        elif category == "industry":
            df = ak.stock_board_industry_name_em()
        else:
            raise HTTPException(
                status_code=400, detail=f"category must be concept|industry, got: {category}"
            )

        if df is None or df.empty:
            return {"category": category, "count": 0, "boards": []}

        # akshare 列名 → 输出 key 映射（akshare 字段名偶尔会改，写多个 alias 防御）
        col_map = {
            "排名": "rank",
            "板块名称": "name",
            "板块代码": "code",
            "最新价": "latest_price",
            "涨跌额": "change_amount",
            "涨跌幅": "change_pct",
            "总市值": "total_market_cap",
            "换手率": "turnover_rate",
            "上涨家数": "up_count",
            "下跌家数": "down_count",
            "领涨股票": "leader_name",
            "领涨股票-涨跌幅": "leader_change_pct",
        }

        # 按涨跌幅降序排序（确保 leader 在前；akshare 默认按代码序）
        pct_col = "涨跌幅" if "涨跌幅" in df.columns else None
        if pct_col:
            df = df.sort_values(pct_col, ascending=False, na_position="last")

        boards = []
        for _, row in df.head(limit).iterrows():
            entry = {}
            for src, dst in col_map.items():
                if src in df.columns:
                    val = row[src]
                    # NaN → None；numpy 类型 → python 原生
                    try:
                        import math
                        if isinstance(val, float) and math.isnan(val):
                            val = None
                        elif hasattr(val, "item"):
                            val = val.item()
                    except Exception:
                        pass
                    entry[dst] = val
            boards.append(entry)

        return {"category": category, "count": len(boards), "boards": boards}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"akshare stock_board_{category}_name_em failed: {e}"
        )
