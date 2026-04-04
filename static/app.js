/* ChainCast – Frontend Application */

const API = window.API_BASE ? window.API_BASE.replace(/\/$/, "") : "";

let sessionId = null;
let currentMode = "auto";
let allSeries = [];

document.addEventListener("DOMContentLoaded", async () => {
  initTabs();
  initUpload();
  initModeToggle();
  initMappingConfirm();
  initRunButton();
  initExports();
  initTheory();
  initTooltips();
  
  // Dynamic Year Sync (3.4.6 Upgrade)
  const yr = document.getElementById("currentYear");
  if (yr) yr.textContent = new Date().getFullYear();

  // Restore Below-Graph Toolbars
  initChartToolbar("forecastChart", "forecastToolbar");
  initChartToolbar("historyOnlyChart", "historyToolbar");

  await startSession();
  loadSamples();
});

// Session management
async function startSession() {
  try {
    const res = await fetch(`${API}/session/start`, { method: "POST" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    sessionId = (await res.json()).session_id;
  } catch (err) {
    showToast("Backend unreachable", `Cannot connect to ${API || "backend"}. Error: ${err.message}`);
  }
}

// Theme handling
function initTheme() {
  const saved = localStorage.getItem("theme") || "dark";
  applyTheme(saved);
  document.getElementById("themeToggle").onclick = () => {
    const cur = document.documentElement.getAttribute("data-theme") || "dark";
    applyTheme(cur === "dark" ? "light" : "dark");
  };
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  const toggle = document.getElementById("themeToggle");
  if (toggle) toggle.textContent = theme === "dark" ? "Light" : "Dark";
  localStorage.setItem("theme", theme);
}

// Tab switching
function initTabs() {
  document.querySelectorAll(".tab").forEach(tab => {
    tab.onclick = () => {
      document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(`tab-${tab.dataset.tab}`).classList.add("active");
    };
  });
}

// Load sample datasets
async function loadSamples() {
  const grid = document.getElementById("samplesGrid");
  try {
    const res = await fetch(`${API}/datasets`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const { datasets } = await res.json();
    grid.innerHTML = "";
    datasets.forEach(ds => {
      const card = document.createElement("div");
      card.className = "sample-card";
      card.innerHTML = `
        <div class="sample-card-icon"><svg viewBox="0 0 24 24"><path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" stroke="currentColor" stroke-width="2" fill="none" stroke-linejoin="round"/></svg></div>
        <div class="sample-card-name">${escapeHtml(ds.name)}</div>
        <div class="sample-card-desc">${escapeHtml(ds.description)}</div>
        <div class="sample-card-meta">
          <span class="smeta">${ds.freq}</span>
          <span class="smeta">h=${ds.horizon}</span>
          <span class="smeta">m=${ds.season_length}</span>
        </div>
      `;
      card.onclick = () => loadSampleDataset(ds.id, ds);
      grid.appendChild(card);
    });
  } catch (err) {
    grid.innerHTML = `<div class="samples-loading">Failed to load samples: ${err.message}</div>`;
  }
}

async function loadSampleDataset(id, meta) {
  if (!sessionId) await startSession();
  showLoading(`Configuring ${meta.name || "Sample"}...`);
  try {
    const res = await fetch(`${API}/datasets/${encodeURIComponent(id)}?session_id=${sessionId}`);
    if (!res.ok) throw new Error((await res.json()).detail || `HTTP ${res.status}`);
    const data = await res.json();
    hideLoading();
    allSeries = data.validation.series_list || [];
    showDetectedBanner(data.validation);
    updateAutoSummary(data.validation.info);
    populateSeries(allSeries);
    hide("mapping-section");
    show("settings-section");
    scrollTo("settings-section");
    if (meta.suggested_lead_time) {
      document.getElementById("aLeadTime").value = meta.suggested_lead_time;
      document.getElementById("pLeadTime").value = meta.suggested_lead_time;
    }
  } catch (err) {
    hideLoading();
    showToast("Dataset error", err.message);
  }
}

// CSV upload
function initUpload() {
  const zone = document.getElementById("uploadZone");
  const input = document.getElementById("fileInput");
  zone.onclick = () => input.click();
  zone.ondragover = e => { e.preventDefault(); zone.classList.add("drag-over"); };
  zone.ondragleave = () => zone.classList.remove("drag-over");
  zone.ondrop = e => {
    e.preventDefault();
    zone.classList.remove("drag-over");
    if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
  };
  input.onchange = () => {
    if (input.files[0]) handleFile(input.files[0]);
  };
}

async function handleFile(file) {
  if (!file.name.toLowerCase().endsWith(".csv")) {
    showToast("Invalid file", "Please upload a CSV file.");
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    showToast("File too large", "Maximum size is 10 MB.");
    return;
  }
  if (!sessionId) await startSession();

  const fd = new FormData();
  fd.append("file", file);
  fd.append("session_id", sessionId);

  showLoading("Reading CSV...");
  try {
    const res = await fetch(`${API}/upload`, { method: "POST", body: fd });
    if (!res.ok) throw new Error((await res.json()).detail || `HTTP ${res.status}`);
    const data = await res.json();
    hideLoading();
    showMappingSection(data);
  } catch (err) {
    hideLoading();
    showToast("Upload failed", err.message);
  }
}

function showMappingSection(data) {
  const cols = data.columns || [];
  renderPreviewTable(data.preview, cols);

  const dateSelect = document.getElementById("dateColSelect");
  const valueSelect = document.getElementById("valueColSelect");
  const idSelect = document.getElementById("idColSelect");

  dateSelect.innerHTML = "";
  valueSelect.innerHTML = "";
  idSelect.innerHTML = '<option value="">None (single series)</option>';

  cols.forEach(c => {
    const opt1 = document.createElement("option");
    opt1.value = c;
    opt1.textContent = c;
    dateSelect.appendChild(opt1);

    const opt2 = document.createElement("option");
    opt2.value = c;
    opt2.textContent = c;
    valueSelect.appendChild(opt2);

    const opt3 = document.createElement("option");
    opt3.value = c;
    opt3.textContent = c;
    idSelect.appendChild(opt3);
  });

  const sug = data.suggestions || {};
  if (sug.date_col) dateSelect.value = sug.date_col;
  if (sug.value_col) valueSelect.value = sug.value_col;
  if (sug.id_col) idSelect.value = sug.id_col;

  if (data.truncation_warning) {
    const wb = document.getElementById("warningsBox");
    wb.innerHTML = `<p><svg viewBox="0 0 24 24" width="16" height="16" style="vertical-align: bottom; margin-right: 5px; fill: none; stroke: var(--danger); stroke-width: 2"><path d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" stroke-linecap="round" stroke-linejoin="round"/></svg> ${escapeHtml(data.truncation_warning)}</p>`;
    wb.classList.remove("hidden");
  }

  show("mapping-section");
  scrollTo("mapping-section");
}

function renderPreviewTable(rows, cols) {
  const container = document.getElementById("previewTable");
  if (!rows || !cols || rows.length === 0) {
    container.innerHTML = "<p class='preview-placeholder'>No preview available.</p>";
    return;
  }
  const thead = `<thead><tr>${cols.map(c => `<th>${escapeHtml(c)}</th>`).join("")}</tr></thead>`;
  const tbody = `<tbody>${rows.map(row => `
    <tr>${cols.map(c => `<td>${escapeHtml(String(row[c] ?? ""))}</td>`).join("")}</tr>
  `).join("")}</tbody>`;
  container.innerHTML = `<table>${thead}${tbody}</table>`;
}

function initMappingConfirm() {
  document.getElementById("confirmMappingBtn").onclick = async () => {
    if (!sessionId) return;
    const fd = new FormData();
    fd.append("session_id", sessionId);
    fd.append("date_col", document.getElementById("dateColSelect").value);
    fd.append("value_col", document.getElementById("valueColSelect").value);
    const idVal = document.getElementById("idColSelect").value;
    if (idVal) fd.append("id_col", idVal);

    showLoading("Validating data...");
    try {
      const res = await fetch(`${API}/map-columns`, { method: "POST", body: fd });
      if (!res.ok) throw new Error((await res.json()).detail || `HTTP ${res.status}`);
      const data = await res.json();
      hideLoading();
      allSeries = data.series_list || [];
      showDetectedBanner(data.validation);
      updateAutoSummary(data.validation.info);
      populateSeries(allSeries);
      
      // Trigger Pre-flight Diagnostic Modal (3.1.3 Upgrade)
      showDataInsights(data.personality);
    } catch (err) {
      hideLoading();
      showToast("Validation failed", err.message);
    }
  };
}

function showDetectedBanner(validation) {
  const info = validation.info || {};
  const stat = validation.stationarity || {};
  const firstKey = Object.keys(stat)[0] || "";
  const si = stat[firstKey] || {};
  const banner = document.getElementById("detectedBanner");

  const formatDate = d => d ? d.split("T")[0] : "—";
  const range = `${formatDate(info.date_min)} — ${formatDate(info.date_max)}`;

  const items = [
    { 
      label: "Frequency", value: info.freq_label || "—", 
      icon: `<svg viewBox="0 0 24 24"><path d="M19 4H5c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 14H5V8h14v10z"></path></svg>` 
    },
    { 
      label: "Seasonality", value: `${info.season_length || "—"} steps`, 
      icon: `<svg viewBox="0 0 24 24"><path d="M10 20h4V4h-4v16zm-6 0h4v-8H4v8zM16 9v11h4V9h-4z"></path></svg>` 
    },
    { 
      label: "Date range", value: range, 
      icon: `<svg viewBox="0 0 24 24"><path d="M9 11H7v2h2v-2zm4 0h-2v2h2v-2zm4 0h-2v2h2v-2zm2-7h-1V2h-2v2H8V2H6v2H5c-1.11 0-1.99.9-1.99 2L3 20c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V9h14v11z"></path></svg>` 
    },
    { 
      label: "Total rows", value: (info.n_rows || 0).toLocaleString(), 
      icon: `<svg viewBox="0 0 24 24"><path d="M4 6h16V4H4v2zm0 5h16V9H4v2zm0 5h16v-2H4v2zm0 4h16v-2H4v2z"></path></svg>` 
    },
    { 
      label: "Series count", value: info.n_series || 1, 
      icon: `<svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"></path></svg>` 
    },
    { 
      label: "Stationarity", value: si.stationary === true ? "Stationary" : si.stationary === false ? "Correction Needed" : "—",
      color: si.stationary ? "var(--success)" : "var(--gold)",
      icon: `<svg viewBox="0 0 24 24"><path d="M3.5 18.49l6-6.01 4 4L22.69 7.3l-1.41-1.41-7.78 7.78-4-4-7.41 7.41 1.41 1.41z"></path></svg>`
    }
  ];

  banner.innerHTML = items.map(t => `
    <div class="det-card">
      <div class="det-icon">${t.icon}</div>
      <div class="det-body">
        <div class="det-label">${t.label}</div>
        <div class="det-value" style="${t.color ? `color: ${t.color}` : ""}">${t.value}</div>
      </div>
    </div>
  `).join("");

  if (validation.warnings && validation.warnings.length) {
    const wb = document.getElementById("warningsBox");
    wb.innerHTML = validation.warnings.map(w => `<p><svg viewBox="0 0 24 24" width="16" height="16" style="vertical-align: bottom; margin-right: 5px; fill: none; stroke: var(--danger); stroke-width: 2"><path d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" stroke-linecap="round" stroke-linejoin="round"/></svg> ${escapeHtml(w)}</p>`).join("");
    wb.classList.remove("hidden");
  }
}

function updateAutoSummary(info) {
  const sl = info?.season_length || 7;
  document.getElementById("autoSL").textContent = sl;
  document.getElementById("autoHz").textContent = `${sl * 2} periods`;
  document.getElementById("pSeasonLen").value = sl;
  document.getElementById("pHorizon").value = sl * 2;
}

function populateSeries(series) {
  const container = document.getElementById("seriesSelector");
  if (!series || series.length <= 1) {
    container.classList.add("hidden");
    return;
  }
  const checksDiv = document.getElementById("seriesCheckboxes");
  checksDiv.innerHTML = "";
  series.forEach((s, idx) => {
    const label = document.createElement("label");
    label.innerHTML = `<input type="checkbox" value="${escapeHtml(s)}" ${idx < 5 ? "checked" : ""}> ${escapeHtml(s)}`;
    checksDiv.appendChild(label);
  });
  container.classList.remove("hidden");
}

function initModeToggle() {
  document.querySelectorAll(".mode-btn").forEach(btn => {
    btn.onclick = () => {
      document.querySelectorAll(".mode-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentMode = btn.dataset.mode;
      if (currentMode === "manual") {
        show("manualControls");
        hide("autoSummary");
        hide("autoScInputs");
      } else {
        hide("manualControls");
        show("autoSummary");
        show("autoScInputs");
      }
    };
  });
}

function initRunButton() {
  document.getElementById("runForecastBtn").onclick = runForecast;
}

async function runForecast() {
  if (!sessionId) {
    showToast("No session", "Please upload a file or select a sample first.");
    return;
  }
  show("loading-section");
  hide("results-section");
  scrollTo("loading-section");
  animateSteps();

  const fd = new FormData();
  fd.append("session_id", sessionId);
  fd.append("mode", currentMode);

  if (currentMode === "manual") {
    fd.append("horizon", getVal("pHorizon"));
    fd.append("season_length", getVal("pSeasonLen"));
    fd.append("n_windows", getVal("pWindows"));
    fd.append("p", getVal("pP")); fd.append("d", getVal("pD")); fd.append("q", getVal("pQ"));
    fd.append("P", getVal("pSP")); fd.append("D", getVal("pSD")); fd.append("Q", getVal("pSQ"));
    fd.append("lead_time_days", getVal("pLeadTime"));
    fd.append("service_level", getVal("pServiceLevel"));
    fd.append("holding_cost", getVal("pHoldCost"));
    fd.append("stockout_cost", getVal("pStockCost"));
  } else {
    fd.append("lead_time_days", getVal("aLeadTime"));
    fd.append("service_level", getVal("aServiceLevel"));
    fd.append("holding_cost", getVal("aHoldCost"));
    fd.append("stockout_cost", getVal("aStockCost"));
  }

  const selected = [...document.querySelectorAll("#seriesCheckboxes input:checked")].map(i => i.value);
  if (selected.length) fd.append("selected_series", selected.join(","));

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
      document.getElementById("loadingTitle").textContent = "High-volume data detected: crunching complex patterns...";
    }, 12000);

    const res = await fetch(`${API}/forecast`, { method: "POST", body: fd, signal: controller.signal });
    clearTimeout(timeoutId);
    if (!res.ok) throw new Error((await res.json()).detail || `HTTP ${res.status}`);
    const data = await res.json();
    hide("loading-section");
    hide("welcomeGuide");
    const summaryText = document.getElementById("execSummaryText");
    if (summaryText) summaryText.textContent = data.dashboard_summary || "Turbo Engine Active: Processing your high-capacity series results.";
    renderResults(data);
    show("results-section");
    scrollTo("results-section");
  } catch (err) {
    hide("loading-section");
    showToast("Forecast failed", err.message);
    scrollTo("settings-section");
  }
}

function getVal(id) {
  return document.getElementById(id)?.value || "";
}

function animateSteps() {
  const steps = document.querySelectorAll(".lstep");
  steps.forEach(s => s.classList.remove("active", "done"));
  let i = 0;
  const interval = setInterval(() => {
    if (i > 0 && i <= steps.length) steps[i-1].classList.replace("active", "done");
    if (i < steps.length) {
      steps[i].classList.add("active");
      i++;
    } else {
      // Keep showing busy state if we reach the end but still haven't returned
      document.getElementById("loadingTitle").textContent = "Finalizing results and generating business insights...";
      clearInterval(interval);
    }
  }, 1500);
}

function renderResults(data) {
  const scores   = data.model_scores || {};
  const best     = data.best_model || "SARIMA";
  const warnings = data.warnings || [];
  const hasMae   = scores[best] != null && !isNaN(Number(scores[best]));
  const cvFailed = warnings.some(w =>
    w.toLowerCase().includes("cv failed") ||
    w.toLowerCase().includes("not enough data for cv")
  );

  let scoreHtml;
  if (hasMae) {
    scoreHtml = `MAE: <strong>${Number(scores[best]).toFixed(2)}</strong> — lowest error across all tested models`;
  } else if (cvFailed) {
    scoreHtml = `<span style="color:var(--accent-orange)">Cross-validation failed — reliability score unavailable. Check warnings below.</span>`;
  } else {
    scoreHtml = `Fallback model used — no error score available (limited data)`;
  }

  document.getElementById("bestModelBanner").innerHTML = `
    <div><div class="bm-label">Best model selected</div><div class="bm-name">${escapeHtml(best)}</div></div>
    <div class="bm-score">${scoreHtml}</div>
  `;


  const warningsDiv = document.getElementById("warningsBox");
  if (data.warnings && data.warnings.length) {
    warningsDiv.innerHTML = data.warnings.map(w => `<p><svg viewBox="0 0 24 24" width="16" height="16" style="vertical-align: bottom; margin-right: 5px; fill: none; stroke: var(--danger); stroke-width: 2"><path d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" stroke-linecap="round" stroke-linejoin="round"/></svg> ${escapeHtml(w)}</p>`).join("");
    warningsDiv.classList.remove("hidden");
  } else {
    warningsDiv.classList.add("hidden");
  }

  try { renderForecastChart(data); } catch (e) { console.error("Forecast chart error", e); }
  try { renderComparisonChart(data); } catch (e) { console.error("Comparison chart error", e); }
  try { renderResidualsChart(data); } catch (e) { console.error("Residuals chart error", e); }
  try { renderMetricsTable(data); } catch (e) { console.error("Metrics table error", e); }
  try { renderSCMetrics(data.supply_chain); } catch (e) { console.error("SC metrics error", e); }
  try { renderTheory(data.theory); } catch (e) { console.error("Theory error", e); }
  try { renderHistoryOnlyChart(data); } catch (e) { console.error("History-only chart error", e); }
  try { renderTrustScore(data); } catch (e) { console.error("Trust score error", e); }
  try { showDataReport(data); } catch (e) { console.error("Data report error", e); }
}

function showDataReport(data) {
  const sc     = data.supply_chain || {};
  const hist   = data.history || {};
  const series = Object.keys(hist);
  const warnings = data.warnings || [];

  // Gather stats
  const totalRows = series.reduce((sum, uid) => sum + (hist[uid]?.length || 0), 0);
  const forecastRows = data.forecast?.length || 0;
  const skippedWarnings = warnings.filter(w => w.toLowerCase().includes("skip"));
  const dataWarnings = warnings.filter(w => !w.toLowerCase().includes("skip"));

  // Date range from history
  let dateMin = "—", dateMax = "—";
  if (series.length && hist[series[0]]?.length) {
    const pts = hist[series[0]];
    dateMin = pts[0]?.ds?.split("T")[0] || "—";
    dateMax = pts[pts.length - 1]?.ds?.split("T")[0] || "—";
  }

  // Build rows
  const reportSections = [
    {
      icon: "[+]", title: "What We Processed",
      color: "#00E676",
      rows: [
        ["Total data rows used", `${totalRows.toLocaleString()} rows`],
        ["Unique series forecasted", `${series.join(", ") || "\u2014"}`],
        ["Historical date range", `${dateMin} \u2192 ${dateMax}`],
        ["Forecast periods generated", `${forecastRows} future time steps`],
        ["Best model selected", data.best_model || "\u2014"],
        ["Avg demand / period", `${sc.avg_demand_per_period || 0} units`],
      ]
    },
    {
      icon: "[*]", title: "Automatic Adjustments Applied",
      color: "#FFD600",
      rows: [
        ["Duplicate timestamps", "Auto-resolved via mean aggregation (prevents engine crash)"],
        ["Missing gaps in history", "Auto-filled using forward-fill + linear interpolation"],
        ["Negative values", "Clipped to 0 (demand cannot be negative)"],
        ["Stationarity", "ADF test applied. If non-stationary, auto-differencing was used"],
      ]
    },
    ...(skippedWarnings.length ? [{
      icon: "[!]", title: "What Was Skipped or Ignored",
      color: "#FF9800",
      rows: skippedWarnings.map(w => ["Skipped", w])
    }] : []),
    ...(dataWarnings.length ? [{
      icon: "[i]", title: "Data Quality Notices",
      color: "#FF1744",
      rows: dataWarnings.map(w => ["Notice", w])
    }] : []),
    {
      icon: "[~]", title: "Supply Chain Parameters Used",
      color: "#9D4EDD",
      rows: [
        ["Service level target", `${sc.service_level_pct || 95}%`],
        ["Safety stock calculated", `${sc.safety_stock || 0} units (buffer for volatility)`],
        ["Reorder point", `${sc.reorder_point || 0} units (trigger a new order at this level)`],
        ["Stockout risk", `${sc.stockout_risk_pct || 5}% chance of running out`],
      ]
    }
  ];

  const body = document.getElementById("dataReportBody");
  body.innerHTML = reportSections.map(sec => `
    <div class="report-section">
      <div class="report-section-header" style="border-left: 3px solid ${sec.color}">
        <span class="report-icon">${sec.icon}</span>
        <span class="report-section-title" style="color:${sec.color}">${sec.title}</span>
      </div>
      <table class="report-table">
        ${sec.rows.map(([k, v]) => `
          <tr>
            <td class="report-key">${k}</td>
            <td class="report-val">${escapeHtml(String(v))}</td>
          </tr>`).join("")}
      </table>
    </div>
  `).join("");

  document.getElementById("dataReportOverlay").classList.remove("hidden");
  document.body.style.overflow = "hidden";
}

function closeDataReport(e) {
  if (e && e.target !== document.getElementById("dataReportOverlay")) return;
  document.getElementById("dataReportOverlay").classList.add("hidden");
  document.body.style.overflow = "";
}

function renderTrustScore(data) {
  const scores   = data.model_scores || {};
  const best     = data.best_model || "";
  const sc       = data.supply_chain || {};
  const avg      = parseFloat(sc.avg_demand_per_period) || 0;
  const warnings = data.warnings || [];
  const cvData   = data.cv_results || [];
  const bar      = document.getElementById("trustScoreBar");
  if (!bar) return;

  // ── Detect CV failure conditions ──────────────────────────────────────
  const cvFailed = warnings.some(w =>
    w.toLowerCase().includes("cv failed") ||
    w.toLowerCase().includes("not enough data for cv") ||
    w.toLowerCase().includes("no suitable models")
  );
  const hasMaeScore = scores[best] != null && !isNaN(parseFloat(scores[best]));
  const maeval = hasMaeScore ? parseFloat(scores[best]) : null;

  // ── Determine trust ────────────────────────────────────────────────────
  let trust = null;
  let label, color, desc, subtext = "";

  if (cvFailed || !hasMaeScore || cvData.length === 0) {
    // CV did not complete — cannot give a reliable score
    label   = "Cannot compute";
    color   = "#FF9800";
    desc    = "Cross-validation did not complete, so reliability cannot be measured. Check the warnings above.";
    subtext = warnings.find(w => w.toLowerCase().includes("cv") || w.toLowerCase().includes("order")) || "";
  } else if (avg <= 0) {
    label   = "Score unavailable";
    color   = "#a0aec0";
    desc    = "Average demand is zero — cannot calculate a meaningful reliability percentage.";
  } else {
    // Core formula: how small is the error relative to average demand?
    trust = Math.max(0, Math.min(100, Math.round((1 - maeval / avg) * 100)));
    if (isNaN(trust)) {
      label   = "Cannot compute";
      color   = "#FF9800";
      desc    = "Score unavailable — errors were detected during statistical validation.";
    } else if (trust >= 85) {
      label = `${trust}% Reliable`; color = "#00E676";
      desc  = "Excellent accuracy. This forecast is highly trustworthy for business decisions.";
    } else if (trust >= 65) {
      label = `${trust}% Reliable`; color = "#FFD600";
      desc  = "Good accuracy. Use this forecast as a strong guide, but allow for some flexibility.";
    } else if (trust >= 40) {
      label = `${trust}% Reliable`; color = "#FF9800";
      desc  = "Moderate accuracy. Your data has high volatility — treat predictions with caution.";
    } else {
      label = `${trust}% Reliable`; color = "#FF1744";
      desc  = "Low accuracy. The model struggled with this data pattern. Try AutoPilot mode instead.";
    }
  }

  const pct = trust ?? 0;
  const warnHtml = subtext
    ? `<div class="trust-warning">${escapeHtml(subtext)}</div>`
    : "";

  bar.innerHTML = `
    <div class="trust-card">
      <div class="trust-header">
        <span class="trust-label">AI Reliability Meter</span>
        <span class="trust-score" style="color:${color}">${label}</span>
      </div>
      <div class="trust-bar-track">
        <div class="trust-bar-fill" style="width:${pct}%;background:${color};box-shadow:0 0 12px ${color}60"></div>
      </div>
      <div class="trust-desc">${desc}</div>
      ${warnHtml}
    </div>
  `;
}


function renderHistoryOnlyChart(data) {
  const history = data.history || {};
  const paper = "rgba(0,0,0,0)";
  const gridCol = "rgba(255,255,255,0.06)";
  const textCol = "#a0aec0";
  const palette = ["#00E5FF", "#9D4EDD", "#FFD600", "#00E676", "#FF1744"];
  const traces = [];

  // Rolling average helper (window = 10% of data, min 3)
  function rollingMean(arr, win) {
    return arr.map((_, i) => {
      const start = Math.max(0, i - Math.floor(win / 2));
      const slice = arr.slice(start, start + win);
      return slice.reduce((a, b) => a + b, 0) / slice.length;
    });
  }

  Object.entries(history).forEach(([uid, hist], idx) => {
    const xs = hist.map(p => p.ds);
    const ys = hist.map(p => p.y);

    // Distinct fixed colors — different per trace TYPE, not per series
    const RAW_COLOR   = "#00E5FF";  // Cyan — raw actual data
    const TREND_COLOR = "#FF9800";  // Orange — smoothed trend
    const ANOM_COLOR  = "#FF1744";  // Red — anomalous outliers

    // Raw history line
    traces.push({
      x: xs, y: ys,
      name: `${uid} (raw data)`,
      type: "scatter", mode: "lines",
      line: { color: RAW_COLOR, width: 1.5 },
      opacity: 0.55
    });

    // Rolling trend line — distinctly Orange
    const win = Math.max(3, Math.floor(ys.length * 0.08));
    const trend = rollingMean(ys, win);
    traces.push({
      x: xs, y: trend,
      name: `${uid} trend (smoothed)`,
      type: "scatter", mode: "lines",
      line: { color: TREND_COLOR, width: 3 },
      opacity: 1
    });

    // Anomaly detection — Red
    const mean = ys.reduce((a, b) => a + b, 0) / ys.length;
    const std = Math.sqrt(ys.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / ys.length);
    const anomalyX = [], anomalyY = [], anomalyText = [];
    ys.forEach((y, i) => {
      if (Math.abs(y - mean) > 2.5 * std) {
        anomalyX.push(xs[i]);
        anomalyY.push(y);
        anomalyText.push(`Anomaly: ${y.toFixed(1)} (${((y-mean)/std).toFixed(1)} std devs from average)`);
      }
    });
    if (anomalyX.length) {
      traces.push({
        x: anomalyX, y: anomalyY,
        name: "Anomalies / Outliers",
        type: "scatter", mode: "markers",
        marker: { color: ANOM_COLOR, size: 11, symbol: "circle", line: { color: "white", width: 1.5 } },
        text: anomalyText, hoverinfo: "text+x"
      });
    }
  });

  Plotly.newPlot("historyOnlyChart", traces, {
    paper_bgcolor: paper,
    plot_bgcolor: paper,
    font: { family: "Outfit, sans-serif", color: textCol },
    xaxis: { 
      gridcolor: gridCol, 
      title: "Historical Time Range",
      type: "date",
      tickformat: "%b %d, %Y"
    },
    yaxis: { gridcolor: gridCol, title: "Actual Demand / Units" },
    legend: { orientation: "h", y: -0.38 },
    margin: { l: 70, r: 30, t: 70, b: 120 },
    hovermode: "closest",
    annotations: [
      {
        x: 0.5, y: 1.12, xref: 'paper', yref: 'paper', xanchor: 'center',
        text: 'PURE DATA — Trend Line + Anomaly Detection',
        showarrow: false, font: { color: textCol, size: 12, family: "Outfit, sans-serif" },
        bgcolor: 'rgba(255,255,255,0.03)', borderpad: 6
      }
    ]
  }, { responsive: true, displayModeBar: false });
}

function renderTheory(theory) {
  const body = document.getElementById("theoryBody");
  if (!theory || !theory.steps || !theory.steps.length) {
    body.innerHTML = '<p class="theory-placeholder">Run a forecast first – a personalised explanation will appear here.</p>';
    return;
  }
  body.innerHTML = theory.steps.map((s, idx) => `
    <div class="theory-item">
      <div class="theory-step-num">${idx + 1}</div>
      <div class="theory-content">
        <h4>${s.header}</h4>
        <p>${s.body}</p>
      </div>
    </div>
  `).join("");
}

function renderForecastChart(data) {
  const history = data.history || {};
  const forecast = data.forecast || [];
  const paper = "rgba(0,0,0,0)";
  const gridCol = "rgba(255,255,255,0.06)";
  const textCol = "#a0aec0";

  // Distinct fixed colors per trace type
  const HISTORY_COLOR  = "#00E5FF";  // Cyan  — actual historical data
  const FORECAST_COLOR = "#FFD600";  // Gold  — AI predicted future line
  const BAND_COLOR     = "#9D4EDD";  // Purple — confidence bands

  const traces = [];
  const seriesIds = Object.keys(history);
  const multiSeries = seriesIds.length > 1;
  const seriesPalette = ["#00E5FF", "#00E676", "#FF9800", "#8BC34A", "#03A9F4"];

  seriesIds.forEach((uid, idx) => {
    const hist = history[uid] || [];
    const lineColor = multiSeries ? seriesPalette[idx % seriesPalette.length] : HISTORY_COLOR;
    traces.push({
      x: hist.map(p => p.ds),
      y: hist.map(p => p.y),
      name: `${uid} (history)`,
      type: "scatter",
      mode: "lines",
      line: { color: lineColor, width: 2 }
    });
  });

  if (forecast.length) {
    const cols = Object.keys(forecast[0]).filter(k => !["unique_id", "ds"].includes(k));
    const bestCol = cols.find(c => c === data.best_model) || cols.find(c => !c.includes("-")) || cols[0];
    const lo80 = cols.find(c => c.includes("-lo-80")) || cols.find(c => c.includes("-lo-"));
    const hi80 = cols.find(c => c.includes("-hi-80")) || cols.find(c => c.includes("-hi-"));
    const lo95 = cols.find(c => c.includes("-lo-95"));
    const hi95 = cols.find(c => c.includes("-hi-95"));

    const byUid = {};
    forecast.forEach(row => {
      const uid = row.unique_id || seriesIds[0] || "Series_1";
      if (!byUid[uid]) byUid[uid] = [];
      byUid[uid].push(row);
    });

    Object.entries(byUid).forEach(([uid, rows]) => {
      const xs = rows.map(r => r.ds);
      if (lo95 && hi95) {
        traces.push({
          x: [...xs, ...xs.slice().reverse()],
          y: [...rows.map(r => r[hi95] ?? null), ...rows.map(r => r[lo95] ?? null).reverse()],
          fill: "toself",
          fillcolor: rgba(BAND_COLOR, 0.07),
          line: { color: "transparent" },
          name: `${uid} 95% band`,
          hoverinfo: "skip"
        });
      }
      if (lo80 && hi80) {
        traces.push({
          x: [...xs, ...xs.slice().reverse()],
          y: [...rows.map(r => r[hi80] ?? null), ...rows.map(r => r[lo80] ?? null).reverse()],
          fill: "toself",
          fillcolor: rgba(BAND_COLOR, 0.22),
          line: { color: "transparent" },
          name: `${uid} 80% band`,
          hoverinfo: "skip"
        });
      }
      if (bestCol) {
        traces.push({
          x: xs,
          y: rows.map(r => r[bestCol] ?? null),
          name: `${uid} forecast (${data.best_model})`,
          type: "scatter",
          mode: "lines",
          line: { color: FORECAST_COLOR, width: 2.5, dash: "dot" }
        });
      }
    });
  }

  const layout = {
    paper_bgcolor: paper,
    plot_bgcolor: paper,
    font: { family: "Outfit, sans-serif", color: textCol },
    xaxis: { 
      gridcolor: gridCol, 
      title: "Time Continuum (Past → Future)",
      type: "date",
      tickformat: "%b %d, %Y",
      rangeselector: { visible: false }
    },
    yaxis: { gridcolor: gridCol, title: "Demand / Units" },
    legend: { orientation: "h", y: -0.2 }, 
    margin: { l: 70, r: 30, t: 50, b: 80 }, 
    hovermode: "x unified",
    shapes: [
      {
        type: 'line', x0: forecast[0]?.ds, x1: forecast[0]?.ds,
        y0: 0, y1: 1, yref: 'paper',
        line: { color: 'rgba(255,255,255,0.5)', width: 2, dash: 'dash' }
      }
    ],
    annotations: [
      {
        x: 0, y: 1.08, xref: 'paper', yref: 'paper', xanchor: 'left',
        text: 'PAST HISTORY',
        showarrow: false, font: { color: textCol, size: 12, family: "Outfit, sans-serif" }
      },
      {
        x: 1, y: 1.08, xref: 'paper', yref: 'paper', xanchor: 'right',
        text: 'AI FUTURE PREDICTION',
        showarrow: false, font: { color: "#00E5FF", size: 12, family: "Outfit, sans-serif" }
      }
    ]
  };

  // Risk Zone: shade where lo95 drops below 0 (stockout territory)
  if (forecast.length) {
    const cols95 = Object.keys(forecast[0]).filter(k => k.includes("-lo-95"));
    cols95.forEach(loCol => {
      const uidRows = forecast.filter(r => r[loCol] != null && r[loCol] < 0);
      if (uidRows.length) {
        const riskXs = uidRows.map(r => r.ds);
        traces.push({
          x: [...riskXs, ...riskXs.slice().reverse()],
          y: [...uidRows.map(r => r[loCol]), ...uidRows.map(() => 0)],
          fill: "toself",
          fillcolor: "rgba(255,23,68,0.12)",
          line: { color: "transparent" },
          name: "Stockout Risk Zone",
          hoverinfo: "name",
          showlegend: true
        });
      }
    });
  }

  Plotly.newPlot("forecastChart", traces, layout, { responsive: true, displayModeBar: false });
}

function renderComparisonChart(results) {
  const scores = results.model_scores || {};
  const best = results.best_model || "None";
  const sorted = Object.entries(scores).sort((a, b) => a[1] - b[1]);
  
  if (sorted.length === 0) {
    document.getElementById("comparisonChart").innerHTML = `<div class="chart-empty-msg">Fallback model used — no comparative metrics available for this dataset size.</div>`;
    return;
  }

  const layout = {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: "Outfit, sans-serif", color: "#a0aec0" },
    xaxis: { title: "MAE (lower is better)", gridcolor: "rgba(255,255,255,0.06)" },
    margin: { l: 200, r: 20, t: 10, b: 50 },
    height: 300
  };

  Plotly.newPlot("comparisonChart", [{
    type: "bar",
    orientation: "h",
    x: sorted.map(s => s[1]),
    y: sorted.map(s => s[0]),
    marker: { color: sorted.map(([k]) => k === best ? "#00E5FF" : "rgba(157, 78, 221, 0.4)") },
    text: sorted.map(s => Number(s[1]).toFixed(2)),
    textposition: "auto"
  }], layout, { responsive: true, displayModeBar: false });

  const compExpl = document.querySelector("#comparisonChart + .chart-explanation");
  if (compExpl) compExpl.innerHTML = `<strong>Which model wins?</strong> We tested many forecasting methods against your data. The shortest bar above (<strong>${best}</strong>) had the smallest mathematical "error," making it the most reliable choice for your future predictions.`;
}

function renderResidualsChart(data) {
  const res = data.residuals;
  const container = document.getElementById("residualsChart");
  if (!res?.values?.length) {
    container.innerHTML = "<p class='preview-placeholder'>Residuals not available.</p>";
    return;
  }
  Plotly.newPlot("residualsChart", [
    {
      x: res.dates,
      y: res.values,
      type: "scatter",
      mode: "lines",
      line: { color: "#00E5FF", width: 1.5 },
      name: "Residuals"
    },
    {
      x: res.dates,
      y: Array(res.values.length).fill(0),
      type: "scatter",
      mode: "lines",
      line: { color: "#F5A623", dash: "dash", width: 1 },
      showlegend: false
    }
  ], {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: "Outfit, sans-serif", color: "#a0aec0", size: 11 },
    xaxis: { 
      gridcolor: "rgba(255,255,255,0.06)", 
      title: "Date",
      type: "date",
      tickformat: "%b %d, %Y" // Prevents millisecond '...59.999' formatting
    },
    yaxis: { gridcolor: "rgba(255,255,255,0.06)", title: "Residual" },
    margin: { l: 55, r: 10, t: 10, b: 60 },
    showlegend: false
  }, { responsive: true, displayModeBar: false });

  const lb = data.ljung_box || {};
  const lbEl = document.getElementById("ljungBoxResult");
  lbEl.className = `ljung-result ${lb.pass === true ? "ljung-pass" : lb.pass === false ? "ljung-fail" : "ljung-unknown"}`;
  lbEl.textContent = lb.message || "Ljung-Box test not available.";
}

function renderMetricsTable(data) {
  const cv = data.cv_results;
  const container = document.getElementById("metricsTable");
  if (!cv || cv.length === 0) {
    container.innerHTML = "<p class='preview-placeholder'>Metrics not available.</p>";
    return;
  }
  const metrics = [...new Set(cv.map(r => r.metric))];
  const modelCols = Object.keys(cv[0]).filter(k => k !== "metric");
  const bestPerMetric = {};
  metrics.forEach(m => {
    const row = cv.find(r => r.metric === m);
    const vals = modelCols.map(c => ({ c, v: row?.[c] })).filter(x => x.v != null);
    if (vals.length) bestPerMetric[m] = vals.reduce((a, b) => a.v < b.v ? a : b).c;
  });
  const thead = `<thead><tr><th>Metric</th>${modelCols.map(c => `<th>${escapeHtml(c)}</th>`).join("")}</tr></thead>`;
  const tbody = metrics.map(m => {
    const row = cv.find(r => r.metric === m);
    const cells = modelCols.map(c => {
      const val = row?.[c];
      const cls = c === bestPerMetric[m] ? "cell-best" : "";
      return `<td class="${cls}">${val != null ? Number(val).toFixed(3) : "—"}</td>`;
    }).join("");
    return `<tr><td class="model-name-cell">${m.toUpperCase()}</td>${cells}</tr>`;
  }).join("");
  container.innerHTML = `<table>${thead}<tbody>${tbody}</tbody></table>`;
}

function renderSCMetrics(sc) {
  const card = document.getElementById("scMetricsCard");
  if (!sc || typeof sc !== "object" || sc.error) {
    card.classList.add("hidden");
    return;
  }
  card.classList.remove("hidden");
  const safe = (key, decimals = 1) => {
    const v = sc[key];
    if (v == null || isNaN(Number(v))) return "0";
    return Number(v).toFixed(decimals);
  };
  const safePct = (key) => {
    const v = sc[key];
    if (v == null || isNaN(Number(v))) return "0%";
    return `${Number(v).toFixed(1)}%`;
  };
  const tiles = [
    { 
      label: "Avg demand / period", value: safe("avg_demand_per_period"), unit: "units",
      desc: "Baseline consumption rate per time period."
    },
    { 
      label: "Total forecast", value: safe("total_forecast", 0), unit: "units", hl: true,
      desc: "Cumulative expected volume over the next forecast horizon."
    },
    { 
      label: "Safety stock", value: safe("safety_stock", 0), unit: "units",
      desc: "Buffer inventory to absorb demand spikes or lead-time variance."
    },
    { 
      label: "Reorder point (ROP)", value: safe("reorder_point", 0), unit: "units", hl: true,
      desc: "The inventory level that triggers an replenishment response."
    },
    { 
      label: "Stockout risk", value: safePct("stockout_risk_pct"), unit: "",
      desc: "Statistical likelihood of depleting stock before arrival."
    },
    { 
      label: "Service level", value: safePct("service_level_pct"), unit: "",
      desc: "Your target probability for meeting all customer demand."
    }
  ];

  // --- Noob-Friendly Executive Summary Injection ---
  const rop = Math.round(sc.reorder_point || 0);
  const qty = Math.round(sc.total_forecast || 0);
  const summaryBox = document.getElementById("scSummary");
  if (summaryBox) {
    summaryBox.innerHTML = `
      <div class="summary-card">
        <div class="summary-icon"><svg viewBox="0 0 24 24"><path d="M11 7h2v2h-2zm0 4h2v6h-2zm1-9C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z" fill="currentColor"/></svg></div>
        <div class="summary-text">
          <strong>OPERATIONAL INSTRUCTION:</strong> To maintain your target ${sc.service_level_pct}% service level, you should place a new order of approximately <strong>${qty.toLocaleString()} units</strong> when your available stock touches <strong>${rop.toLocaleString()} units</strong>.
        </div>
      </div>
    `;
  }

  document.getElementById("scGrid").innerHTML = tiles.map(t => `
    <div class="sc-tile ${t.hl ? "hl" : ""}">
      <div class="sc-tile-label">${t.label}</div>
      <div class="sc-tile-value">${t.value}</div>
      ${t.unit ? `<div class="sc-tile-unit">${t.unit}</div>` : ""}
      <div class="sc-tile-desc">${t.desc}</div>
    </div>
  `).join("");
  const costSection = document.getElementById("scCostSection");
  const hasCosts = sc.total_annual_cost != null && !isNaN(Number(sc.total_annual_cost));
  if (hasCosts) {
    costSection.classList.remove("hidden");
    costSection.innerHTML = `
      <h5>Annual cost estimation</h5>
      <div class="cost-grid">
        <div class="cost-item"><div class="cost-label">Holding cost</div><div class="cost-value">$${Number(sc.annual_holding_cost || 0).toLocaleString()}</div></div>
        <div class="cost-item"><div class="cost-label">Stockout cost</div><div class="cost-value">$${Number(sc.annual_stockout_cost || 0).toLocaleString()}</div></div>
        <div class="cost-item"><div class="cost-label">Total annual</div><div class="cost-value">$${Number(sc.total_annual_cost || 0).toLocaleString()}</div></div>
      </div>
    `;
  } else {
    costSection.classList.add("hidden");
  }
}

function initTheory() {
  document.getElementById("theoryToggle").onclick = () => {
    const body = document.getElementById("theoryBody");
    const btn = document.getElementById("theoryToggle");
    body.classList.toggle("hidden");
    btn.textContent = body.classList.contains("hidden") ? "Show explanation ↓" : "Hide explanation ↑";
  };
}

function initExports() {
  document.getElementById("downloadCsvBtn").onclick = () => {
    if (sessionId) window.open(`${API}/export/csv/${sessionId}`, "_blank");
  };
  document.getElementById("downloadPdfBtn").onclick = () => {
    if (sessionId) window.open(`${API}/export/pdf/${sessionId}`, "_blank");
  };
  document.getElementById("newForecastBtn").onclick = () => {
    hide("results-section");
    document.getElementById("warningsBox").classList.add("hidden");
    show("welcomeGuide");
    scrollTo("data-section");
  };
}

// Utilities
function show(id) { document.getElementById(id)?.classList.remove("hidden"); }
function hide(id) { document.getElementById(id)?.classList.add("hidden"); }
function scrollTo(id) { setTimeout(() => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" }), 80); }
function showLoading(msg = "Processing...") { document.getElementById("loadingTitle").textContent = msg; show("loading-section"); }
function hideLoading() { hide("loading-section"); }
function isDark() { return document.documentElement.getAttribute("data-theme") !== "light"; }
function rgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/[&<>]/g, function(m) {
    if (m === "&") return "&amp;";
    if (m === "<") return "&lt;";
    if (m === ">") return "&gt;";
    return m;
  });
}
function showToast(title, msg) {
  document.getElementById("toastTitle").textContent = title;
  document.getElementById("toastMsg").innerHTML = msg;
  document.getElementById("errorToast").classList.remove("hidden");
  clearTimeout(window.toastTimer);
  window.toastTimer = setTimeout(hideToast, 12000);
}

function updateThemeIcon() {
  const icon = document.getElementById("themeIcon");
  if (!icon) return;
  icon.innerHTML = theme === "dark" ? "LIGHT" : "DARK";
}
function hideToast() { 
  document.getElementById("errorToast").classList.add("hidden"); 
}

/* ═══════════════════════════════════════════════════════════
   SMART TOOLTIP ENGINE — 3-second delayed tooltip on hover
═══════════════════════════════════════════════════════════ */
function initTooltips() {
  // Create one shared tooltip element
  const tip = document.createElement("div");
  tip.id = "smartTooltip";
  tip.className = "smart-tooltip";
  tip.setAttribute("aria-hidden", "true");
  document.body.appendChild(tip);

  let timer = null;
  let currentTarget = null;

  function showTip(target) {
    const text = target.getAttribute("data-tooltip");
    if (!text) return;
    tip.textContent = text;
    tip.classList.add("visible");
    positionTip(target);
  }

  function hideTip() {
    clearTimeout(timer);
    timer = null;
    currentTarget = null;
    tip.classList.remove("visible");
  }

  function positionTip(target) {
    const rect = target.getBoundingClientRect();
    const tW = tip.offsetWidth;
    const tH = tip.offsetHeight;
    const scrollX = window.scrollX;
    const scrollY = window.scrollY;
    const gap = 10;

    // Default: above the element, centred
    let top  = rect.top  + scrollY - tH - gap;
    let left = rect.left + scrollX + rect.width / 2 - tW / 2;

    // If not enough space above, flip below
    if (top < scrollY + 8) {
      top = rect.bottom + scrollY + gap;
    }
    // Keep within horizontal viewport
    const vw = document.documentElement.clientWidth;
    if (left < 8) left = 8;
    if (left + tW > vw - 8) left = vw - tW - 8;

    tip.style.top  = `${top}px`;
    tip.style.left = `${left}px`;
  }

  // Use event delegation — works for dynamically added elements too
  document.addEventListener("mouseover", (e) => {
    const target = e.target.closest("[data-tooltip]");
    if (!target || target === currentTarget) return;
    currentTarget = target;
    clearTimeout(timer);
    timer = setTimeout(() => showTip(target), 3000);
  });

  document.addEventListener("mouseout", (e) => {
    const target = e.target.closest("[data-tooltip]");
    if (!target) return;
    hideTip();
  });

  // Hide on click / scroll / focus loss
  document.addEventListener("mousedown", hideTip);
  document.addEventListener("scroll", hideTip, true);
  document.addEventListener("keydown", hideTip);
}

function initChartToolbar(chartId, toolbarId) {
    const toolbar = document.getElementById(toolbarId);
    if (!toolbar) return;
    
    toolbar.addEventListener('click', (e) => {
        const btn = e.target.closest('.btn-range');
        if (!btn) return;
        
        // UI State
        toolbar.querySelectorAll('.btn-range').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        // Logic
        const count = btn.getAttribute('data-count');
        const step = btn.getAttribute('data-step');
        const chart = document.getElementById(chartId);
        
        if (!chart || !chart.layout) return;

        if (step === 'all') {
            Plotly.relayout(chartId, { 
                'xaxis.autorange': true,
                'xaxis.range': null 
            });
        } else {
            const now = new Date();
            let start = new Date();
            if (step === 'year') start.setFullYear(now.getFullYear() - parseInt(count));
            if (step === 'month') start.setMonth(now.getMonth() - parseInt(count));
            if (step === 'day') start.setDate(now.getDate() - parseInt(count));
            
            Plotly.relayout(chartId, {
                'xaxis.range': [start.toISOString(), now.toISOString()],
                'xaxis.autorange': false
            });
        }
    });
}

function showDataInsights(p) {
    if (!p || !p.type) {
        // Fallback: If AI diagnostics fail/missing, just proceed to settings
        show("settings-section");
        scrollTo("settings-section");
        return;
    }
    document.getElementById("diagPersonality").textContent = p.type || "Custom Dataset";
    document.getElementById("diagPersonalityDesc").textContent = p.type_desc || "No special pattern detected.";
    const healthEl = document.getElementById("diagHealth");
    healthEl.textContent = p.health || "--";
    healthEl.className = `diag-value ${p.health === 'Excellent' ? 'diag-status-excellent' : 'diag-status-caution'}`;
    
    document.getElementById("diagFindings").textContent = p.health_msg || "--";
    document.getElementById("diagStrategy").textContent = p.strategy || "--";
    document.getElementById("diagStrategyMsg").textContent = p.strategy_msg || "--";
    
    const overlay = document.getElementById("dataInsightsOverlay");
    overlay.classList.remove("hidden");
    
    // Bind buttons
    document.getElementById("closeInsightsBtn").onclick = () => overlay.classList.add("hidden");
    document.getElementById("confirmInsightsBtn").onclick = () => {
        overlay.classList.add("hidden");
        show("settings-section");
        scrollTo("settings-section");
    };
}
// ═══════════════════════════════════════════════════════════
// RESPONSIVE CHART SCALING (3.2)
// ═══════════════════════════════════════════════════════════
window.addEventListener('resize', () => {
    const charts = ['forecastChart', 'residChart', 'distChart'];
    charts.forEach(id => {
        const el = document.getElementById(id);
        if (el && el.classList.contains('js-plotly-plot')) {
            Plotly.Plots.resize(el).catch(e => console.warn("Chart resize skip:", e));
        }
    });
});
