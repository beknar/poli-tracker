/* Dashboard interactivity: sortable/searchable table + performance-graph modal. */
let perfChart = null;

document.addEventListener("DOMContentLoaded", function () {
  // Sortable, searchable, paginated table — sorted by purchase date desc.
  if (window.jQuery && jQuery.fn.DataTable) {
    jQuery("#trades").DataTable({
      order: [[4, "desc"]],
      pageLength: 25,
      lengthMenu: [10, 25, 50, 100],
    });
  }

  // Disable the refresh button while a refresh is running (it can take a while).
  const form = document.getElementById("refresh-form");
  if (form) {
    form.addEventListener("submit", function () {
      const btn = document.getElementById("refresh-btn");
      btn.disabled = true;
      btn.textContent = "⏳ Refreshing… (fetching trades + prices)";
    });
  }

  // Graph buttons -> fetch price history -> draw line chart in the modal.
  document.querySelectorAll(".graph-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const ticker = btn.dataset.ticker;
      const start = btn.dataset.start;
      const member = btn.dataset.member;
      openGraph(ticker, start, member);
    });
  });
});

function openGraph(ticker, start, member) {
  const modalEl = document.getElementById("graphModal");
  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  document.getElementById("graphTitle").textContent =
    `${ticker} — ${member} (since ${start})`;
  const status = document.getElementById("graphStatus");
  status.textContent = "Loading price history…";
  modal.show();

  fetch(`/api/price-history?ticker=${encodeURIComponent(ticker)}&start=${encodeURIComponent(start)}`)
    .then((r) => r.json())
    .then((data) => {
      const series = data.series || [];
      if (!series.length) {
        status.textContent = "No price history available for this holding.";
        if (perfChart) { perfChart.destroy(); perfChart = null; }
        return;
      }
      const first = series[0].close;
      const last = series[series.length - 1].close;
      const pct = (((last - first) / first) * 100).toFixed(1);
      status.textContent =
        `From $${first.toFixed(2)} on ${series[0].date} to $${last.toFixed(2)} on ${series[series.length - 1].date} (${pct >= 0 ? "+" : ""}${pct}%).`;

      const up = last >= first;
      const ctx = document.getElementById("perfChart").getContext("2d");
      if (perfChart) perfChart.destroy();
      perfChart = new Chart(ctx, {
        type: "line",
        data: {
          labels: series.map((p) => p.date),
          datasets: [{
            label: `${ticker} close`,
            data: series.map((p) => p.close),
            borderColor: up ? "#198754" : "#dc3545",
            backgroundColor: up ? "rgba(25,135,84,.1)" : "rgba(220,53,69,.1)",
            fill: true,
            pointRadius: 0,
            borderWidth: 2,
            tension: 0.1,
          }],
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: {
            x: { ticks: { maxTicksLimit: 8 } },
            y: { ticks: { callback: (v) => "$" + v } },
          },
        },
      });
    })
    .catch(() => { status.textContent = "Failed to load price history."; });
}
