# company_data.py — resolves the company named in an article to a stock
# ticker and fetches lightweight market data for it (Phase 1: price, market
# cap, 6-month chart). Never calls Groq. Every yfinance call is wrapped in a
# timeout + try/except so a slow or missing ticker can never crash the app
# or block the page — it just means "no market data for this one."

import re
import concurrent.futures

import pandas as pd
import streamlit as st
import yfinance as yf

LOOKUP_TIMEOUT = 8  # seconds — "about 8 seconds" per spec

# words stripped out before comparing company names, so "Akeso" matches
# "Akeso, Inc." and "Moderna" matches "Moderna Therapeutics Inc" etc.
_SUFFIX_WORDS = {
    "inc", "incorporated", "corp", "corporation", "co", "company",
    "ltd", "limited", "llc", "plc", "sa", "ag", "nv", "spa",
    "holdings", "holding", "group",
    "therapeutics", "pharma", "pharmaceutical", "pharmaceuticals",
    "biopharma", "biopharmaceuticals",
    "biotech", "biotechnology", "biosciences", "bioscience", "bio",
}


def _normalize_words(name):
    """Lowercase, strip punctuation, drop corporate-suffix noise words."""
    if not name:
        return []
    name = re.sub(r"[^a-z0-9\s]", " ", name.lower())
    return [w for w in name.split() if w not in _SUFFIX_WORDS]


def _is_confident_match(company_name, candidate_name):
    """
    True only if one normalized name is a prefix of the other — e.g.
    "akeso" is a prefix of "akeso r" (ADR suffix noise), and "akeso" ==
    "akeso". Never matches on a bare word overlap, to avoid false positives
    between unrelated companies that happen to share a generic word.
    """
    a_words = _normalize_words(company_name)
    b_words = _normalize_words(candidate_name)
    if not a_words or not b_words:
        return False
    shorter, longer = (a_words, b_words) if len(a_words) <= len(b_words) else (b_words, a_words)
    return longer[:len(shorter)] == shorter


@st.cache_data(ttl=604800, show_spinner=False)  # 7 days — tickers don't change often
def resolve_ticker(company_name):
    """
    Resolve a company name to a stock ticker using yfinance's search.
    Returns the ticker string, or None if the company looks private, isn't
    found, or multiple genuinely different companies match ambiguously.
    Never raises — any failure is treated as "no confident match."
    """
    if not company_name or not company_name.strip():
        return None

    try:
        results = yf.Search(
            company_name, max_results=8, news_count=0,
            lists_count=0, timeout=LOOKUP_TIMEOUT, raise_errors=False,
        ).quotes
    except Exception:
        return None

    if not results:
        return None

    # only consider actual listed equities — skip futures, ETFs, indices etc.
    equities = [r for r in results if r.get("quoteType") == "EQUITY"]

    confident = [
        r for r in equities
        if _is_confident_match(company_name, r.get("longname") or r.get("shortname") or "")
    ]
    if not confident:
        return None

    # confident matches can legitimately include the same company cross-listed
    # on several exchanges (e.g. Moderna on NASDAQ, Frankfurt, Vienna...).
    # That's not ambiguous. It IS ambiguous if two confident matches don't
    # match each other — i.e. they're different companies that both happen
    # to match the query name.
    first_name = confident[0].get("longname") or confident[0].get("shortname") or ""
    for r in confident[1:]:
        other_name = r.get("longname") or r.get("shortname") or ""
        if not _is_confident_match(first_name, other_name):
            return None  # genuinely ambiguous — different companies

    # same company across listings — pick the highest-relevance one
    best = max(confident, key=lambda r: r.get("score", 0))
    return best.get("symbol")


def _trend_label(price, ma50, ma200):
    """Price vs its 50/200-day moving averages. None if either MA is missing
    (e.g. the ticker has less than 200 days of trading history)."""
    if price is None or ma50 is None or ma200 is None:
        return None
    if price > ma50 and price > ma200:
        return "Uptrend"
    if price < ma50 and price < ma200:
        return "Downtrend"
    return "Sideways"


def _fetch_market_data_blocking(ticker):
    """The actual (blocking) yfinance work — run inside a timeout wrapper below.
    Pulls 1 year of history so the 200-day moving average can be computed;
    the chart and 6-month % change only use the most recent 6 months of it."""
    tk = yf.Ticker(ticker)

    fast = tk.fast_info
    price = fast.get("lastPrice")
    currency = fast.get("currency")
    market_cap = fast.get("marketCap")

    history = tk.history(period="1y", timeout=LOOKUP_TIMEOUT)
    closes = history["Close"] if history is not None and not history.empty else pd.Series(dtype=float)

    if price is None or closes.empty:
        return None

    six_month_closes = closes[closes.index >= closes.index[-1] - pd.Timedelta(days=182)]

    pct_change_6mo = None
    if len(six_month_closes) >= 2 and six_month_closes.iloc[0]:
        pct_change_6mo = (six_month_closes.iloc[-1] - six_month_closes.iloc[0]) / six_month_closes.iloc[0] * 100

    ma50 = closes.tail(50).mean() if len(closes) >= 50 else None
    ma200 = closes.tail(200).mean() if len(closes) >= 200 else None

    return {
        "ticker": ticker,
        "price": price,
        "currency": currency or "USD",
        "market_cap": market_cap,
        "history": six_month_closes,
        "pct_change_6mo": pct_change_6mo,
        "trend": _trend_label(price, ma50, ma200),
    }


@st.cache_data(ttl=900, show_spinner=False)  # 15 min — price/cap/chart are live-ish data
def get_market_data(ticker):
    """
    Fetch price, currency, market cap, a 6-month close-price history, the
    6-month % price change, and a 50/200-day moving-average trend label for
    a ticker. Returns None on any failure or timeout — never raises, and
    never blocks longer than LOOKUP_TIMEOUT seconds no matter what yfinance
    does internally (fast_info has no timeout knob of its own, so this
    enforces one with a short-lived worker thread).
    """
    if not ticker:
        return None

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_fetch_market_data_blocking, ticker)
            return future.result(timeout=LOOKUP_TIMEOUT)
    except Exception:
        return None


def _fetch_fundamentals_blocking(ticker):
    """The actual (blocking) yfinance work for slower-changing fundamentals."""
    tk = yf.Ticker(ticker)
    info = tk.get_info()

    return {
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
        "analyst_rating": info.get("recommendationKey"),
        "analyst_target_price": info.get("targetMeanPrice"),
    }


@st.cache_data(ttl=86400, show_spinner=False)  # 24h — fundamentals change slowly
def get_fundamentals(ticker):
    """
    Fetch revenue/earnings growth and analyst consensus rating + mean target
    price for a ticker. Any field yfinance doesn't have comes back as None —
    never estimated. Returns None entirely on failure or timeout; never
    raises and never blocks longer than LOOKUP_TIMEOUT seconds.
    """
    if not ticker:
        return None

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_fetch_fundamentals_blocking, ticker)
            return future.result(timeout=LOOKUP_TIMEOUT)
    except Exception:
        return None


def prefetch_companies(articles):
    """
    Collects the unique company names mentioned across all articles,
    resolves each to a ticker and fetches its market data in parallel.
    Returns {company_name: result_dict_or_None}. Skips articles with no
    company, and never raises — each lookup fails independently.
    """
    company_names = {
        article["ai_summary"]["company"]
        for article in articles
        if article.get("ai_summary") and article["ai_summary"].get("company")
    }

    results = {}
    if not company_names:
        return results

    def _resolve_and_fetch(name):
        ticker = resolve_ticker(name)
        if not ticker:
            return name, {"ticker": None, "market_data": None, "fundamentals": None}
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as inner_pool:
            market_future = inner_pool.submit(get_market_data, ticker)
            fundamentals_future = inner_pool.submit(get_fundamentals, ticker)
            return name, {
                "ticker": ticker,
                "market_data": market_future.result(),
                "fundamentals": fundamentals_future.result(),
            }

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_resolve_and_fetch, name): name for name in company_names}
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                _, result = future.result()
                results[name] = result
            except Exception:
                results[name] = {"ticker": None, "market_data": None, "fundamentals": None}

    return results
