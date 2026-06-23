"""Configuration for the congressional-trades app.

Everything here is overridable via environment variables so nothing
environment-specific is baked in.
"""
import os

# How far back to look for purchases.
LOOKBACK_MONTHS = int(os.environ.get("CT_LOOKBACK_MONTHS", "6"))

# Only keep "purchase"-type transactions (the brief asked for purchases).
TX_TYPES = {"purchase"}

# Where the SQLite database lives (gitignored).
DB_PATH = os.environ.get(
    "CT_DB_PATH",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "trades.sqlite"),
)

# Free, public disclosure datasets (STOCK Act filings), no API key required.
# These are community-maintained mirrors of the House/Senate clerk disclosures.
DATA_SOURCES = {
    "house": os.environ.get(
        "CT_HOUSE_URL",
        "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json",
    ),
    "senate": os.environ.get(
        "CT_SENATE_URL",
        "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json",
    ),
}

# HTTP timeout (seconds) for dataset/price fetches.
HTTP_TIMEOUT = int(os.environ.get("CT_HTTP_TIMEOUT", "30"))

# Cap the number of distinct tickers priced per refresh (yfinance is slow / rate
# limited). 0 = no cap. Useful to keep the sample responsive.
MAX_TICKERS = int(os.environ.get("CT_MAX_TICKERS", "0"))
