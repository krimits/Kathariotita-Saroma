(function () {
  const COL_PENDING = "#b7791f";
  const COL_COLLECTED = "#2f855a";
  const COL_RATIO = "#2563eb";

  const statsCharts = {};

  function byId(id) {
    return document.getElementById(id);
  }

  function setText(id, text) {
    const el = byId(id);
    if (el) el.textContent = text;
  }

  function destroyStatsCharts() {
    Object.keys(statsCharts).forEach((key) => {
      try {
        statsCharts[key].destroy();
      } catch (_) {
        /* ignore */
      }
      delete statsCharts[key];
    });
  }

  function formatPct01(value) {
    if (value == null || Number.isNaN(Number(value))) return "—";
    const pct = Number(value) * 100;
    return `${pct.toLocaleString("el-GR", { maximumFractionDigits: 1, minimumFractionDigits: 1 })}%`;
  }

  async function loadStatsDashboard() {
    if (typeof window.Chart === "undefined") {
      setText(
        "weeklyReportBlock",
        "Δεν φορτώθηκε η βιβλιοθήκη γραφημάτων (Chart.js). Ελέγξτε τη σύνδεση ή το CDN.",
      );
      return;
    }

    let data;
    try {
      const res = await fetch("/api/stats");
      data = await res.json();
    } catch (err) {
      console.error(err);
      return;
    }

    destroyStatsCharts();

    const rs = data.daily?.ratio_stats || {};
    setText("statRatioMean", rs.ratio_mean != null ? formatPct01(rs.ratio_mean) : "—");
    setText(
      "statRatioStdev",
      rs.ratio_stdev != null
        ? Number(rs.ratio_stdev).toLocaleString("el-GR", { maximumFractionDigits: 4 })
        : "—",
    );
    const outliers = rs.outlier_days || [];
    setText("statOutlierDays", outliers.length ? outliers.map((o) => o.day).join(", ") : "Καμία");
    setText("statSnapshotsCount", String(data.snapshots_count ?? 0));
    const tot = data.totals || {};
    setText("statOverallRatio", tot.ratio_collected != null ? formatPct01(tot.ratio_collected) : "—");

    const report = byId("weeklyReportBlock");
    if (report) report.textContent = data.weekly_report || "";

    const weeklyHint = byId("statsWeeklyHint");
    if (weeklyHint) {
      weeklyHint.textContent =
        (data.snapshots_count || 0) < 2
          ? "Για πιο αξιόπιστη εβδομαδιαία τάση χρειάζονται τουλάχιστον δύο αποθηκευμένα στιγμιότυπα (διαδοχικά refresh)."
          : "";
    }

    const monthlyHint = byId("statsMonthlyHint");
    if (monthlyHint) {
      const monthly = data.monthly || {};
      monthlyHint.textContent =
        monthly.labels && monthly.labels.length
          ? ""
          : "Δεν υπάρχουν ακόμα μηνιαία aggregates — χρειάζονται snapshots που να καλύπτουν διαφορετικούς μήνες.";
    }

    const series = data.daily?.series || [];
    const dayLabels = series.map((r) => r.day);
    const pendingDay = series.map((r) => Number(r.pending || 0));
    const collectedDay = series.map((r) => Number(r.collected || 0));
    const ratioPct = series.map((r) =>
      Number(r.total_points || 0) > 0 ? Number(r.ratio_collected || 0) * 100 : null,
    );

    const ctxBars = byId("chartDailyBars");
    if (ctxBars) {
      statsCharts.dailyBars = new window.Chart(ctxBars, {
        type: "bar",
        data: {
          labels: dayLabels.length ? dayLabels : ["—"],
          datasets: [
            { label: "Εκκρεμή", data: dayLabels.length ? pendingDay : [0], backgroundColor: COL_PENDING },
            {
              label: "Συλλεχθέντα",
              data: dayLabels.length ? collectedDay : [0],
              backgroundColor: COL_COLLECTED,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: { stacked: false },
            y: { beginAtZero: true, ticks: { precision: 0 } },
          },
          plugins: { legend: { position: "bottom" } },
        },
      });
    }

    const ctxRatio = byId("chartDailyRatio");
    if (ctxRatio) {
      statsCharts.dailyRatio = new window.Chart(ctxRatio, {
        type: "line",
        data: {
          labels: dayLabels.length ? dayLabels : ["—"],
          datasets: [
            {
              label: "Λόγος συλλεχθέντων (%)",
              data: dayLabels.length ? ratioPct.map((v) => (v == null ? null : v)) : [null],
              borderColor: COL_RATIO,
              backgroundColor: "rgba(37,99,235,0.12)",
              tension: 0.25,
              spanGaps: true,
              fill: true,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: {
              beginAtZero: true,
              max: 100,
              ticks: {
                callback: (value) => `${value}%`,
              },
            },
          },
          plugins: {
            tooltip: {
              callbacks: {
                label: (ctx) =>
                  `${ctx.dataset.label}: ${Number(ctx.parsed.y).toLocaleString("el-GR", {
                    maximumFractionDigits: 1,
                  })}%`,
              },
            },
          },
        },
      });
    }

    const wt = data.weekly_trend || {};
    const wl = wt.labels || [];
    const wp = (wt.pending || []).map(Number);
    const wc = (wt.collected || []).map(Number);

    const ctxW = byId("chartWeeklyTrend");
    if (ctxW) {
      statsCharts.weekly = new window.Chart(ctxW, {
        type: "bar",
        data: {
          labels: wl.length ? wl : ["Αναμονή δεδομένων"],
          datasets: [
            {
              label: "Εκκρεμή (εβδομαδιαίο σύνολο)",
              data: wl.length ? wp : [0],
              backgroundColor: COL_PENDING,
            },
            {
              label: "Συλλεχθέντα (εβδομαδιαίο σύνολο)",
              data: wl.length ? wc : [0],
              backgroundColor: COL_COLLECTED,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: { beginAtZero: true, ticks: { precision: 0 } },
          },
          plugins: { legend: { position: "bottom" } },
        },
      });
    }

    const mo = data.monthly || {};
    const ml = mo.labels || [];
    const mp = (mo.pending_avg || []).map(Number);
    const mc = (mo.collected_avg || []).map(Number);

    const ctxM = byId("chartMonthlyBars");
    if (ctxM) {
      statsCharts.monthly = new window.Chart(ctxM, {
        type: "bar",
        data: {
          labels: ml.length ? ml : ["Αναμονή δεδομένων"],
          datasets: [
            {
              label: "Μέσος εκκρεμών ανά εβδομάδα (snapshot)",
              data: ml.length ? mp : [0],
              backgroundColor: COL_PENDING,
            },
            {
              label: "Μέσος συλλεχθέντων ανά εβδομάδα (snapshot)",
              data: ml.length ? mc : [0],
              backgroundColor: COL_COLLECTED,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: { beginAtZero: true },
          },
          plugins: { legend: { position: "bottom" } },
        },
      });
    }
  }

  window.loadStatsDashboard = loadStatsDashboard;
})();
