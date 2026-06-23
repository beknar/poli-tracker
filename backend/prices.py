"""Stock price lookups via yfinance (free, no API key), cached in SQLite.

- historical_close: per-share close on/just-before a purchase date.
- current_close: latest close.
- price_series: daily closes between two dates (for the performance graph).
"""
from datetime import date, datetime, timedelta

import yfinance as yf

from . import db


def _to_date(d):
    if isinstance(d, date):
        return d
    return datetime.fromisoformat(str(d)).date()


def historical_close(conn, ticker, on_date):
    """Closing price on `on_date` (or the nearest prior trading day). Cached."""
    iso = _to_date(on_date).isoformat()
    cached = db.cache_get_close(conn, ticker, iso)
    if cached is not None:
        return cached

    start = _to_date(on_date) - timedelta(days=7)
    end = _to_date(on_date) + timedelta(days=1)
    try:
        hist = yf.Ticker(ticker).history(start=start.isoformat(), end=end.isoformat())
    except Exception as exc:
        print(f"[prices] WARN historical {ticker}@{iso}: {exc}")
        return None
    if hist is None or hist.empty:
        return None

    close = float(hist["Close"].iloc[-1])  # nearest trading day on/before the date
    db.cache_put_close(conn, ticker, iso, close)
    return close


def current_close(ticker):
    """Latest available close + the date it's as-of."""
    try:
        hist = yf.Ticker(ticker).history(period="5d")
    except Exception as exc:
        print(f"[prices] WARN current {ticker}: {exc}")
        return (None, None)
    if hist is None or hist.empty:
        return (None, None)
    close = float(hist["Close"].iloc[-1])
    asof = hist.index[-1].date().isoformat()
    return (close, asof)


def price_series(ticker, start_date, end_date=None):
    """List of {date, close} from start_date..end_date (inclusive-ish)."""
    start = _to_date(start_date)
    end = _to_date(end_date) if end_date else date.today()
    try:
        hist = yf.Ticker(ticker).history(
            start=start.isoformat(), end=(end + timedelta(days=1)).isoformat()
        )
    except Exception as exc:
        print(f"[prices] WARN series {ticker}: {exc}")
        return []
    if hist is None or hist.empty:
        return []
    return [
        {"date": idx.date().isoformat(), "close": round(float(row["Close"]), 4)}
        for idx, row in hist.iterrows()
    ]
