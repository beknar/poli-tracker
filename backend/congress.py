"""Fetch and normalize congressional stock-purchase disclosures.

Source: the free, public House/Senate "stock watcher" datasets (community
mirrors of the official STOCK Act disclosures). No API key required.
"""
import hashlib
import re
from datetime import date, timedelta

import requests
from dateutil import parser as dateparser

from . import config

_AMOUNT_RE = re.compile(r"\$?([\d,]+)")


def _parse_amount(text):
    """'$1,001 - $15,000' -> (1001.0, 15000.0); best-effort."""
    if not text:
        return (None, None)
    nums = [float(m.replace(",", "")) for m in _AMOUNT_RE.findall(str(text))]
    if not nums:
        return (None, None)
    if len(nums) == 1:
        return (nums[0], nums[0])
    return (min(nums), max(nums))


def _parse_date(text):
    """Return ISO yyyy-mm-dd, or None if unparseable."""
    if not text:
        return None
    try:
        return dateparser.parse(str(text), dayfirst=False).date().isoformat()
    except (ValueError, OverflowError, TypeError):
        return None


def _clean_ticker(t):
    if not t:
        return ""
    t = str(t).strip().upper()
    # Disclosures use '--' / 'N/A' for non-tickered assets (bonds, funds, etc.).
    if t in {"--", "N/A", "NA", "", "<NA>"}:
        return ""
    return t


def _uid(member, ticker, tx_date, tx_type, amount, owner):
    raw = "|".join(str(x) for x in (member, ticker, tx_date, tx_type, amount, owner))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _fetch_json(url):
    resp = requests.get(url, timeout=config.HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _normalize(record, chamber):
    """Map a raw disclosure record to our transaction schema (or None to skip)."""
    tx_type = str(record.get("type", "")).strip().lower()
    if tx_type not in config.TX_TYPES:
        return None

    tx_date = _parse_date(record.get("transaction_date"))
    if not tx_date:
        return None

    member = record.get("representative") or record.get("senator") or "Unknown"
    amount = record.get("amount")
    amount_min, amount_max = _parse_amount(amount)
    ticker = _clean_ticker(record.get("ticker"))
    owner = record.get("owner") or ""

    return {
        "uid": _uid(member, ticker, tx_date, tx_type, amount, owner),
        "member": str(member).replace("Hon. ", "").strip(),
        "chamber": chamber,
        "state": record.get("state") or record.get("district") or "",
        "party": record.get("party") or "",
        "ticker": ticker,
        "asset_description": (record.get("asset_description") or "").strip(),
        "tx_type": tx_type,
        "tx_date": tx_date,
        "disclosure_date": _parse_date(record.get("disclosure_date")),
        "owner": owner,
        "amount_min": amount_min,
        "amount_max": amount_max,
        "source": chamber.lower(),
    }


def fetch_recent_purchases(lookback_months=None):
    """Yield normalized purchase records from the last N months across chambers."""
    months = lookback_months or config.LOOKBACK_MONTHS
    cutoff = date.today() - timedelta(days=int(months * 30.44))

    for chamber, url in (("House", config.DATA_SOURCES["house"]),
                         ("Senate", config.DATA_SOURCES["senate"])):
        try:
            records = _fetch_json(url)
        except Exception as exc:  # network / source hiccup — skip that chamber
            print(f"[congress] WARN: could not fetch {chamber} data: {exc}")
            continue

        for rec in records:
            norm = _normalize(rec, chamber)
            if norm is None:
                continue
            if norm["tx_date"] < cutoff.isoformat():
                continue
            yield norm
