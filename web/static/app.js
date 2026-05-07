const statusLabels = {
  excellent: "Άριστη",
  good: "Καλή",
  red: "Κόκκινη",
};

/** Με HTTP Basic Auth, διατηρούμε συνομιλητικό session για same-origin API. */
const apiFetchInit = { credentials: "same-origin" };

const sourceLabels = {
  veltio: "Βελτιώνω την πόλη μου",
  supervisor: "Επόπτες Καθαριότητας",
  previous_weeks: "Προηγούμενες εβδομάδες (μουσταρδί)",
  unknown: "Άγνωστη πηγή",
};

const statusRecordLabels = {
  pending: "Εκκρεμεί",
  collected: "Συλλέχθηκε",
  unknown: "Άγνωστο",
};

function byId(id) {
  return document.getElementById(id);
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString("el-GR");
}

function setText(id, value) {
  byId(id).textContent = value;
}

function filterOptionLabel(kind, value) {
  if (kind === "status") {
    return statusRecordLabels[value] || value;
  }
  if (kind === "source") {
    return sourceLabels[value] || value;
  }
  return value;
}

function sortedOptionSig(values) {
  return [...values]
    .map((v) => String(v))
    .sort((a, b) => a.localeCompare(b, "el"))
    .join("\u0000");
}

function filterSourcesForUiSelect(sources) {
  return (sources || []).filter((value) => String(value).trim() !== "" && String(value).toLowerCase() !== "unknown");
}

function populateSelect(selectId, values, kind) {
  const select = byId(selectId);
  const sig = sortedOptionSig(values);
  if (select.dataset.optionSig === sig) {
    return;
  }
  select.dataset.optionSig = sig;
  const current = select.value;
  select.innerHTML = '<option value="">Όλες</option>';
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = filterOptionLabel(kind, value);
    select.appendChild(option);
  });
  const valid = current === "" || [...select.options].some((option) => option.value === current);
  select.value = valid ? current : "";
}

function renderBars(containerId, data) {
  const container = byId(containerId);
  const entries = Object.entries(data || {});
  container.innerHTML = "";

  if (entries.length === 0) {
    container.textContent = "Δεν υπάρχουν δεδομένα.";
    return;
  }

  const max = Math.max(...entries.map(([, value]) => Number(value)));
  entries.forEach(([label, value]) => {
    const row = document.createElement("div");
    row.className = "bar-row";

    const title = document.createElement("div");
    title.textContent = label;

    const track = document.createElement("div");
    track.className = "track";
    const fill = document.createElement("div");
    fill.className = "fill";
    fill.style.width = `${max === 0 ? 0 : (Number(value) / max) * 100}%`;
    track.appendChild(fill);

    const count = document.createElement("div");
    count.textContent = formatNumber(value);

    row.append(title, track, count);
    container.appendChild(row);
  });
}

function renderTopStreets(streets) {
  const body = byId("topStreetsBody");
  body.innerHTML = "";
  (streets || []).forEach((item) => {
    const row = document.createElement("tr");
    row.innerHTML = `<td>${item.street}</td><td>${formatNumber(item.pending)}</td>`;
    body.appendChild(row);
  });
}

function weekInsight(summary) {
  const pending = Number(summary.pending || 0);
  if (summary.week_status === "excellent") {
    return `Η εβδομάδα είναι σε άριστη κατάσταση, επειδή το υπόλοιπο είναι ${pending} σημεία και βρίσκεται κάτω από το όριο των 100.`;
  }
  if (summary.week_status === "good") {
    return `Η εβδομάδα είναι διαχειρίσιμη, με υπόλοιπο ${pending} σημείων. Χρειάζεται παρακολούθηση ώστε να μη ξεπεράσει το όριο των 300.`;
  }
  return `Η εβδομάδα είναι κόκκινη, με υπόλοιπο ${pending} σημείων. Απαιτείται επιχειρησιακή προτεραιοποίηση.`;
}

function formatSyncNote(summary) {
  const intervalSec = Number(summary.refresh_interval_seconds ?? 20);
  const iso = summary.extracted_at_utc;
  const sheetHint =
    "Η πηγή είναι το συνδεδεμένο Google Sheet· τα δεδομένα ανανεώνονται στον server όταν καλείται το API (και περιοδικά ~κάθε " +
    intervalSec +
    "s). Τα φίλτρα φιλτράρουν το τρέχον στιγμιότυπο CSV — δεν «ανοίγουν» το Sheets στο πρόγραμμα περιήγησης.";
  if (!iso) {
    return `${sheetHint} Δεν υπάρχει χρονοσήμανση τελευταίας ανάγνωσης (πιθανό παλιό API ή χωρίς επιτυχές refresh).`;
  }
  try {
    const d = new Date(iso);
    const stamp = d.toLocaleString("el-GR", { dateStyle: "short", timeStyle: "medium" });
    return `${sheetHint} Τελευταία επιτυχής ανάγνωση από το φύλλο: ${stamp}.`;
  } catch {
    return sheetHint;
  }
}

function anyFilterActive() {
  return !!(
    byId("statusFilter").value ||
    byId("sourceFilter").value ||
    byId("dayFilter").value ||
    byId("streetFilter").value.trim()
  );
}

function updateFilterHint() {
  const hint = byId("filterHint");
  if (!hint) return;
  hint.hidden = !anyFilterActive();
}

function focusRecordsTab() {
  document.querySelectorAll(".tab").forEach((node) => node.classList.remove("active"));
  document.querySelectorAll(".panel-view").forEach((node) => node.classList.remove("active"));
  const tab = document.querySelector('.tab[data-panel="records"]');
  const panel = byId("records");
  if (tab) tab.classList.add("active");
  if (panel) panel.classList.add("active");
}

async function loadSummary() {
  const response = await fetch("/api/summary", apiFetchInit);
  const summary = await response.json();
  setText("weekLabel", summary.week_label || "Τρέχουσα εβδομάδα");
  setText("weekStatus", statusLabels[summary.week_status] || summary.week_status || "-");
  setText("weekStatusNote", `${formatNumber(summary.pending)} εκκρεμή`);
  setText("pendingKpi", formatNumber(summary.pending));
  setText("collectedKpi", formatNumber(summary.collected));
  const dayCollected = Object.values(summary.collected_by_day || {}).reduce((sum, value) => sum + Number(value), 0);
  setText("dayCollectedKpi", formatNumber(dayCollected));
  byId("weekStatusCard").className = `kpi ${summary.week_status || ""}`;
  setText("insightText", weekInsight(summary));

  const syncEl = byId("syncNote");
  if (syncEl) syncEl.textContent = formatSyncNote(summary);

  renderBars("collectedByDay", summary.collected_by_day);
  renderBars("pendingByDay", summary.pending_by_day);
  renderTopStreets(summary.top_pending_streets);

  populateSelect("statusFilter", summary.filters?.statuses || [], "status");
  populateSelect("sourceFilter", filterSourcesForUiSelect(summary.filters?.sources || []), "source");
  populateSelect("dayFilter", summary.filters?.days || [], "day");
}

function badge(value) {
  const label = statusRecordLabels[value] || sourceLabels[value] || value || "Άγνωστο";
  const className = value || "unknown";
  return `<span class="badge ${className}">${label}</span>`;
}

async function loadRecords() {
  const params = new URLSearchParams();
  const status = byId("statusFilter").value;
  const source = byId("sourceFilter").value;
  const day = byId("dayFilter").value;
  const street = byId("streetFilter").value;
  if (status) params.set("status", status);
  if (source) params.set("source", source);
  if (day) params.set("day", day);
  if (street) params.set("street", street);
  params.set("limit", "200");

  const response = await fetch(`/api/records?${params.toString()}`, apiFetchInit);
  const payload = await response.json();
  setText("recordCount", `${formatNumber(payload.total)} εγγραφές`);

  const body = byId("recordsBody");
  body.innerHTML = "";
  payload.records.forEach((record) => {
    const row = document.createElement("tr");
    const period = record.day || record.period || "";
    row.innerHTML = `
      <td>${record.street || ""}</td>
      <td>${period}</td>
      <td>${record.point_id || ""}</td>
      <td>${badge(record.status)}</td>
      <td>${badge(record.source)}</td>
    `;
    body.appendChild(row);
  });
  updateFilterHint();
}

function onUserFilterChange() {
  updateFilterHint();
  if (anyFilterActive()) {
    focusRecordsTab();
  }
  loadRecords().catch((err) => console.error(err));
}

function bindTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((node) => node.classList.remove("active"));
      document.querySelectorAll(".panel-view").forEach((node) => node.classList.remove("active"));
      tab.classList.add("active");
      const panelId = tab.dataset.panel;
      const panel = byId(panelId);
      if (panel) panel.classList.add("active");
      if (panelId === "stats" && typeof window.loadStatsDashboard === "function") {
        window.loadStatsDashboard().catch((err) => console.error(err));
      }
    });
  });
}

function bindFilters() {
  ["statusFilter", "sourceFilter", "dayFilter"].forEach((id) => {
    byId(id).addEventListener("change", onUserFilterChange);
  });
  byId("streetFilter").addEventListener("input", () => {
    window.clearTimeout(window.streetFilterTimer);
    window.streetFilterTimer = window.setTimeout(onUserFilterChange, 180);
  });
}

async function init() {
  bindTabs();
  bindFilters();
  await loadSummary();
  await loadRecords();
  updateFilterHint();
  window.setInterval(async () => {
    await loadSummary();
    await loadRecords();
    if (byId("stats")?.classList.contains("active") && typeof window.loadStatsDashboard === "function") {
      await window.loadStatsDashboard();
    }
  }, 20000);
}

init().catch((error) => {
  console.error(error);
  setText("insightText", "Δεν ήταν δυνατή η φόρτωση των δεδομένων dashboard.");
});
