"""SQLite storage: schema, upserts, and price cache.

Uses the stdlib sqlite3 (no ORM) to keep dependencies minimal. The first
ingest creates the file; subsequent ingests upsert into it.
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    uid              TEXT UNIQUE,           -- stable hash for dedupe/upsert
    member           TEXT,
    chamber          TEXT,                  -- 'House' | 'Senate'
    state            TEXT,
    party            TEXT,
    ticker           TEXT,
    asset_description TEXT,
    tx_type          TEXT,                  -- 'purchase'
    tx_date          TEXT,                  -- ISO yyyy-mm-dd
    disclosure_date  TEXT,
    owner            TEXT,
    amount_min       REAL,
    amount_max       REAL,
    purchase_price   REAL,                  -- per-share close at tx_date
    current_price    REAL,                  -- latest per-share close
    price_asof       TEXT,
    source           TEXT,
    created_at       TEXT,
    updated_at       TEXT
);
CREATE INDEX IF NOT EXISTS idx_tx_ticker ON transactions(ticker);
CREATE INDEX IF NOT EXISTS idx_tx_member ON transactions(member);

CREATE TABLE IF NOT EXISTS price_cache (
    ticker TEXT,
    d      TEXT,                            -- ISO date of the close
    close  REAL,
    PRIMARY KEY (ticker, d)
);

CREATE TABLE IF NOT EXISTS meta (
    k TEXT PRIMARY KEY,
    v TEXT
);
"""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect():
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)


def upsert_transaction(conn, row):
    """Insert a transaction if new (by uid); leave existing rows' prices intact."""
    now = _now()
    conn.execute(
        """
        INSERT INTO transactions
            (uid, member, chamber, state, party, ticker, asset_description,
             tx_type, tx_date, disclosure_date, owner, amount_min, amount_max,
             source, created_at, updated_at)
        VALUES
            (:uid, :member, :chamber, :state, :party, :ticker, :asset_description,
             :tx_type, :tx_date, :disclosure_date, :owner, :amount_min, :amount_max,
             :source, :created_at, :updated_at)
        ON CONFLICT(uid) DO UPDATE SET
            disclosure_date = excluded.disclosure_date,
            updated_at = excluded.updated_at
        """,
        {**row, "created_at": now, "updated_at": now},
    )


def distinct_tickers(conn):
    cur = conn.execute(
        "SELECT DISTINCT ticker FROM transactions "
        "WHERE ticker IS NOT NULL AND ticker != '' ORDER BY ticker"
    )
    return [r["ticker"] for r in cur.fetchall()]


def set_purchase_price(conn, ticker, tx_date, price):
    conn.execute(
        "UPDATE transactions SET purchase_price=?, updated_at=? "
        "WHERE ticker=? AND tx_date=?",
        (price, _now(), ticker, tx_date),
    )


def set_current_price(conn, ticker, price, asof):
    conn.execute(
        "UPDATE transactions SET current_price=?, price_asof=?, updated_at=? "
        "WHERE ticker=?",
        (price, asof, _now(), ticker),
    )


def cache_get_close(conn, ticker, d):
    cur = conn.execute(
        "SELECT close FROM price_cache WHERE ticker=? AND d=?", (ticker, d)
    )
    r = cur.fetchone()
    return r["close"] if r else None


def cache_put_close(conn, ticker, d, close):
    conn.execute(
        "INSERT OR REPLACE INTO price_cache (ticker, d, close) VALUES (?,?,?)",
        (ticker, d, close),
    )


def set_meta(conn, k, v):
    conn.execute("INSERT OR REPLACE INTO meta (k, v) VALUES (?, ?)", (k, str(v)))


def get_meta(conn, k, default=None):
    cur = conn.execute("SELECT v FROM meta WHERE k=?", (k,))
    r = cur.fetchone()
    return r["v"] if r else default


def fetch_dashboard_rows(conn):
    """Return enriched purchase rows for the dashboard, newest first."""
    cur = conn.execute(
        """
        SELECT member, chamber, state, party, ticker, asset_description,
               tx_date, owner, amount_min, amount_max,
               purchase_price, current_price, price_asof
        FROM transactions
        ORDER BY tx_date DESC, member ASC
        """
    )
    rows = []
    for r in cur.fetchall():
        d = dict(r)
        amt_mid = None
        if d["amount_min"] is not None and d["amount_max"] is not None:
            amt_mid = (d["amount_min"] + d["amount_max"]) / 2.0
        pp, cp = d["purchase_price"], d["current_price"]
        d["amount_mid"] = amt_mid
        d["value_at_purchase"] = amt_mid  # the disclosed amount IS the buy value
        if amt_mid and pp and cp and pp > 0:
            d["value_now"] = amt_mid * (cp / pp)
            d["change_pct"] = (cp / pp - 1.0) * 100.0
        else:
            d["value_now"] = None
            d["change_pct"] = None
        rows.append(d)
    return rows


def summary(conn):
    rows = fetch_dashboard_rows(conn)
    members = {r["member"] for r in rows if r["member"]}
    val_now = sum(r["value_now"] for r in rows if r["value_now"])
    val_buy = sum(r["value_at_purchase"] for r in rows if r["value_at_purchase"])
    return {
        "members": len(members),
        "purchases": len(rows),
        "value_now": val_now,
        "value_at_purchase": val_buy,
        "last_updated": get_meta(conn, "last_ingest", "never"),
    }


def fetch_members(conn):
    """One aggregated row per member: chamber, purchase count, and est. values."""
    agg = {}
    for r in fetch_dashboard_rows(conn):
        m = r["member"] or "Unknown"
        a = agg.setdefault(m, {
            "member": m, "chamber": r["chamber"], "state": r["state"],
            "purchases": 0, "value_now": 0.0, "value_at_purchase": 0.0,
        })
        a["purchases"] += 1
        if r["value_now"]:
            a["value_now"] += r["value_now"]
        if r["value_at_purchase"]:
            a["value_at_purchase"] += r["value_at_purchase"]
    return sorted(agg.values(), key=lambda x: x["value_now"], reverse=True)


def fetch_member_rows(conn, member):
    """All of one member's purchase rows (newest first) + per-member totals."""
    rows = [r for r in fetch_dashboard_rows(conn) if (r["member"] or "") == member]
    totals = {
        "purchases": len(rows),
        "chamber": rows[0]["chamber"] if rows else "",
        "state": rows[0]["state"] if rows else "",
        "disclosed": sum(r["value_at_purchase"] for r in rows if r["value_at_purchase"]),
        "value_now": sum(r["value_now"] for r in rows if r["value_now"]),
    }
    return rows, totals
