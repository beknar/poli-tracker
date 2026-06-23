"""Orchestrate a data refresh.

First run: creates the SQLite DB, pulls the last N months of purchases, and
prices each holding. Subsequent runs: upsert any new purchases and refresh the
current prices (so 'current value' stays up to date) without re-pricing history
that's already cached.
"""
from datetime import datetime, timezone

from . import config, congress, db, prices


def run_ingest(verbose=True):
    db.init_db()
    inserted = 0
    seen_tx = []  # (ticker, tx_date) pairs that need a purchase price

    with db.connect() as conn:
        # 1. Pull + upsert recent purchases.
        for rec in congress.fetch_recent_purchases():
            before = conn.total_changes
            db.upsert_transaction(conn, rec)
            if conn.total_changes > before and rec["ticker"]:
                seen_tx.append((rec["ticker"], rec["tx_date"]))
            if conn.total_changes > before:
                inserted += 1

        tickers = db.distinct_tickers(conn)
        if config.MAX_TICKERS:
            tickers = tickers[: config.MAX_TICKERS]
        if verbose:
            print(f"[ingest] {inserted} new purchases; pricing {len(tickers)} tickers")

        # 2. Fill in purchase prices for any rows missing one (cached after first time).
        cur = conn.execute(
            "SELECT DISTINCT ticker, tx_date FROM transactions "
            "WHERE ticker != '' AND purchase_price IS NULL"
        )
        for row in cur.fetchall():
            if config.MAX_TICKERS and row["ticker"] not in tickers:
                continue
            pp = prices.historical_close(conn, row["ticker"], row["tx_date"])
            if pp is not None:
                db.set_purchase_price(conn, row["ticker"], row["tx_date"], pp)

        # 3. Refresh current prices for every distinct ticker (always, so 'now' is fresh).
        for ticker in tickers:
            cp, asof = prices.current_close(ticker)
            if cp is not None:
                db.set_current_price(conn, ticker, cp, asof)

        db.set_meta(
            conn, "last_ingest", datetime.now(timezone.utc).isoformat(timespec="seconds")
        )

    if verbose:
        print("[ingest] done")
    return {"inserted": inserted, "tickers": len(tickers)}


if __name__ == "__main__":
    run_ingest()
