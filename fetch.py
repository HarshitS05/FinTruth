import re
import requests
import xml.etree.ElementTree as ET
import yfinance as yf

JUNK = re.compile(
    r"share price today|live share price|live chart|stock price|tradingview|techgraph"
    r"|- facebook|- instagram|- youtube|- linkedin|wikipedia|screener|estimates\b",
    re.I,
)


def get_news(query: str, limit: int = 5, when: str = "") -> list:
    """Google News RSS. `when` like '14d' restricts to recent articles."""
    q = f"{query} when:{when}" if when else query
    url = "https://news.google.com/rss/search"
    params = {"q": q, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"}
    try:
        r = requests.get(url, params=params, timeout=8)
        root = ET.fromstring(r.content)
        titles = [item.findtext("title") for item in root.iter("item")]
        return [t for t in titles if t and not JUNK.search(t)][:limit]
    except Exception:
        return []


def get_stock_data(query: str) -> dict:
    ticker = query.upper().strip()
    if not ticker.endswith((".NS", ".BO")):
        ticker += ".NS"

    stock = yf.Ticker(ticker)
    info = stock.info or {}

    if not info.get("longName"):
        return {"error": f"Couldn't find data for {ticker}"}

    hist = stock.history(period="6mo")

    yf_news = []
    for n in (stock.news or [])[:10]:
        title = n.get("title") or n.get("content", {}).get("title")
        if title and not JUNK.search(title):
            yf_news.append(title)

    seen, news = set(), []
    for t in yf_news + get_news(info.get("longName"), limit=15, when="30d"):
        k = t.lower()[:60]
        if k not in seen:  # drop near-duplicate headlines
            seen.add(k)
            news.append(t)
    news = news[:15]
    dte = info.get("debtToEquity")

    return {
        "industry": info.get("industry"),
        "ebitda_margin": info.get("ebitdaMargins"),
        "roe": info.get("returnOnEquity"),
        "ticker": ticker,
        "name": info.get("longName"),
        "sector": info.get("sector"),
        "price": info.get("currentPrice"),
        "market_cap": info.get("marketCap"),
        "pe": info.get("trailingPE"),
        "debt_to_equity": round(dte / 100, 2) if dte is not None else None,
        "revenue_growth": info.get("revenueGrowth"),
        "profit_margin": info.get("profitMargins"),
        "avg_volume": info.get("averageVolume"),
        "change_6mo_pct": round(
            (hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100, 2
        ) if len(hist) else None,
        "news": news,
        "business": (info.get("longBusinessSummary") or "")[:500],
    }


if __name__ == "__main__":
    for t in ["RELIANCE", "TCS", "SUZLON"]:
        print(get_stock_data(t))
        print("-" * 40)