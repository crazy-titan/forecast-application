/* ChainCast – Frontend Application */

const API = window.API_BASE ? window.API_BASE.replace(/\/$/, "") : "";

let sessionId = null;
let currentMode = "auto";
let allSeries = [];

document.addEventListener("DOMContentLoaded", async () => {
  initTheme();
  initTabs();
  initUpload();
  initModeToggle();
  initMappingConfirm();
  initRunButton();
  initExports();
  initTheory();
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
  document.getElementById("themeToggle").textContent = theme === "dark" ? "🌙" : "☀️";
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
        <div class="sample-card-icon">📦</div>
        <div class="sample-card-name">${escapeHtml(ds.name)}</div>
        <div class="sample-card-desc">${escapeHtml(ds.description)}</div>
        <div class="sample-card-meta">
          <span class="smeta">${ds.freq}</span>
          <span class="smeta">h=${ds.horizon}</span>
          <span class="smeta">m=${ds.season_length}</span>
        </div>
      `;
      card.onclick = () => loadSampleDataset(ds.name, ds);
      grid.appendChild(card);
    });
  } catch (err) {
    grid.innerHTML = `<div class="samples-loading">Failed to load samples: ${err.message}</div>`;
  }
}

async function loadSampleDataset(name, meta) {
  if (!sessionId) await startSession();
  showLoading("Loading sample dataset...");
  try {
    const res = await fetch(`${API}/datasets/${encodeURIComponent(name)}?session_id=${sessionId}`);
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
    wb.innerHTML = `<p>⚠️ ${escapeHtml(data.truncation_warning)}</p>`;
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
      show("settings-section");
      scrollTo("settings-section");
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
  banner.innerHTML = `
    <div class="det-item"><span class="det-label">Frequency</span><span class="det-value">${info.freq_label || "—"}</span></div>
    <div class="det-item"><span class="det-label">Season length</span><span class="det-value">${info.season_length || "—"}</span></div>
    <div class="det-item"><span class="det-label">Date range</span><span class="det-value">${info.date_range || "—"}</span></div>
    <div class="det-item"><span class="det-label">Rows</span><span class="det-value">${(info.n_rows || 0).toLocaleString()}</span></div>
    <div class="det-item"><span class="det-label">Series</span><span class="det-value">${info.n_series || 1}</span></div>
    <div class="det-item"><span class="det-label">Stationarity</span>
      <span class="det-value" style="color:${si.stationary ? "var(--green)" : "var(--gold)"}">
        ${si.stationary === true ? "Stationary" : si.stationary === false ? "Non-stationary (auto-fixed)" : "—"}
      </span>
    </div>
  `;
  if (validation.warnings && validation.warnings.length) {
    const wb = document.getElementById("warningsBox");
    wb.innerHTML = validation.warnings.map(w => `<p>⚠️ ${escapeHtml(w)}</p>`).join("");
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
    const res = await fetch(`${API}/forecast`, { method: "POST", body: fd });
    if (!res.ok) throw new Error((await res.json()).detail || `HTTP ${res.status}`);
    const data = await res.json();
    hide("loading-section");
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
      clearInterval(interval);
    }
  }, 1400);
}

function renderResults(data) {
  const scores = data.model_scores || {};
  const best = data.best_model || "SARIMA";
  const scoreVal = scores[best] != null ? Number(scores[best]).toFixed(2) : "—";
  document.getElementById("bestModelBanner").innerHTML = `
    <div><div class="bm-label">Best model</div><div class="bm-name">${escapeHtml(best)}</div></div>
    <div class="bm-score">MAE: ${scoreVal} — lowest across all tested models</div>
  `;

  const warningsDiv = document.getElementById("warningsBox");
  if (data.warnings && data.warnings.length) {
    warningsDiv.innerHTML = data.warnings.map(w => `<p>⚠️ ${escapeHtml(w)}</p>`).join("");
    warningsDiv.classList.remove("hidden");
  } else {
    warningsDiv.classList.add("hidden");
  }

  try { renderForecastChart(data); } catch (e) { console.error("Forecast chart error", e); }
  try { renderComparisonChart(data); } catch (e) { console.error("Comparison chart error", e); }
  try { renderResidualsChart(data); } catch (e) { console.error("Residuals chart error", e); }
  try { renderMetricsTable(data); } catch (e) { console.error("Metrics table error", e); }
  try { renderSCMetrics(data.supply_chain); } catch (e) { console.error("SC metrics error", e); }
}

function renderForecastChart(data) {
  const history = data.history || {};
  const forecast = data.forecast || [];
  const dark = isDark();
  const paper = dark ? "#1A2D45" : "#FFFFFF";
  const gridCol = dark ? "#1E3A55" : "#E2E8F0";
  const textCol = dark ? "#A8C4D0" : "#374151";
  const palette = ["#1E88E5", "#00ACC1", "#F5A623", "#27AE60", "#E74C3C"];
  const traces = [];
  const seriesIds = Object.keys(history);

  seriesIds.forEach((uid, idx) => {
    const hist = history[uid] || [];
    traces.push({
      x: hist.map(p => p.ds),
      y: hist.map(p => p.y),
      name: `${uid} (history)`,
      type: "scatter",
      mode: "lines",
      line: { color: palette[idx % palette.length], width: 2 }
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

    Object.entries(byUid).forEach(([uid, rows], idx) => {
      const color = palette[idx % palette.length];
      const xs = rows.map(r => r.ds);
      if (lo95 && hi95) {
        traces.push({
          x: [...xs, ...xs.slice().reverse()],
          y: [...rows.map(r => r[hi95] ?? null), ...rows.map(r => r[lo95] ?? null).reverse()],
          fill: "toself",
          fillcolor: rgba(color, 0.07),
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
          fillcolor: rgba(color, 0.18),
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
          line: { color: color, width: 2.5, dash: "dot" }
        });
      }
    });
  }

  Plotly.newPlot("forecastChart", traces, {
    paper_bgcolor: paper,
    plot_bgcolor: paper,
    font: { family: "Inter, sans-serif", color: textCol },
    xaxis: { gridcolor: gridCol, title: "Date" },
    yaxis: { gridcolor: gridCol, title: "Demand / Units" },
    legend: { orientation: "h", y: -0.22 },
    margin: { l: 60, r: 20, t: 10, b: 90 },
    hovermode: "x unified"
  }, { responsive: true, displayModeBar: false });
}

function renderComparisonChart(data) {
  const scores = data.model_scores || {};
  const best = data.best_model;
  const dark = isDark();
  const sorted = Object.entries(scores).sort((a, b) => a[1] - b[1]);
  Plotly.newPlot("comparisonChart", [{
    type: "bar",
    orientation: "h",
    x: sorted.map(s => s[1]),
    y: sorted.map(s => s[0]),
    marker: { color: sorted.map(([k]) => k === best ? "#00ACC1" : "#1E3A55") },
    text: sorted.map(s => Number(s[1]).toFixed(2)),
    textposition: "auto"
  }], {
    paper_bgcolor: dark ? "#1A2D45" : "#FFFFFF",
    plot_bgcolor: dark ? "#1A2D45" : "#FFFFFF",
    font: { family: "Inter, sans-serif", color: dark ? "#A8C4D0" : "#374151" },
    xaxis: { title: "MAE (lower is better)", gridcolor: dark ? "#1E3A55" : "#E2E8F0" },
    margin: { l: 130, r: 20, t: 10, b: 50 }
  }, { responsive: true, displayModeBar: false });
}

function renderResidualsChart(data) {
  const res = data.residuals;
  const dark = isDark();
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
      line: { color: "#00ACC1", width: 1.5 },
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
    paper_bgcolor: dark ? "#1A2D45" : "#FFFFFF",
    plot_bgcolor: dark ? "#1A2D45" : "#FFFFFF",
    font: { family: "Inter, sans-serif", color: dark ? "#A8C4D0" : "#374151", size: 11 },
    xaxis: { gridcolor: dark ? "#1E3A55" : "#E2E8F0", title: "Date" },
    yaxis: { gridcolor: dark ? "#1E3A55" : "#E2E8F0", title: "Residual" },
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
    { label: "Avg demand / period", value: safe("avg_demand_per_period"), unit: "units" },
    { label: "Total forecast", value: safe("total_forecast", 0), unit: "units", hl: true },
    { label: "Safety stock", value: safe("safety_stock", 0), unit: "units" },
    { label: "Reorder point (ROP)", value: safe("reorder_point", 0), unit: "units", hl: true },
    { label: "Stockout risk", value: safePct("stockout_risk_pct"), unit: "" },
    { label: "Service level", value: safePct("service_level_pct"), unit: "" }
  ];
  document.getElementById("scGrid").innerHTML = tiles.map(t => `
    <div class="sc-tile ${t.hl ? "hl" : ""}">
      <div class="sc-tile-label">${t.label}</div>
      <div class="sc-tile-value">${t.value}</div>
      ${t.unit ? `<div class="sc-tile-unit">${t.unit}</div>` : ""}
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
  document.getElementById("toastMsg").textContent = msg;
  document.getElementById("errorToast").classList.remove("hidden");
  setTimeout(hideToast, 10000);
}
function hideToast() { document.getElementById("errorToast").classList.add("hidden"); }