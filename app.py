"""Flask web dashboard for congressional stock purchases.

Run (dev):
    pip install -r requirements.txt
    python -m backend.ingest        # first-time data load (or use the Refresh button)
    flask --app app run             # http://127.0.0.1:5000

For HTTPS / production (nginx + Let's Encrypt), see deploy/README.md.
"""
from flask import Flask, jsonify, redirect, render_template, request, url_for

from backend import db, prices
from backend.ingest import run_ingest

app = Flask(__name__)


@app.route("/")
def dashboard():
    """One row per member: name (link) | chamber | purchases | est. value."""
    db.init_db()
    with db.connect() as conn:
        members = db.fetch_members(conn)
        summary = db.summary(conn)
    return render_template("dashboard.html", members=members, summary=summary)


@app.route("/member/<member>")
def member_detail(member):
    """A single member's purchases over the last 6 months, with per-row prices."""
    db.init_db()
    with db.connect() as conn:
        rows, totals = db.fetch_member_rows(conn, member)
        last_updated = db.get_meta(conn, "last_ingest", "never")
    return render_template(
        "member.html", member=member, rows=rows, totals=totals,
        last_updated=last_updated,
    )


@app.route("/refresh", methods=["POST"])
def refresh():
    """Run (or re-run) ingestion, then return to the dashboard."""
    run_ingest(verbose=True)
    return redirect(url_for("dashboard"))


@app.route("/api/price-history")
def price_history():
    """JSON daily closes for the performance graph: ?ticker=AAPL&start=2024-01-02"""
    ticker = (request.args.get("ticker") or "").strip().upper()
    start = request.args.get("start")
    if not ticker or not start:
        return jsonify({"error": "ticker and start are required"}), 400
    series = prices.price_series(ticker, start)
    return jsonify({"ticker": ticker, "start": start, "series": series})


if __name__ == "__main__":
    app.run(debug=True)
