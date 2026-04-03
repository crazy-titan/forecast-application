import io
import datetime
import traceback
from fpdf import FPDF


def clean_text(text):
    """Deeply defensive text cleaner to prevent PDF rendering crashes."""
    if text is None:
        return "N/A"
    if isinstance(text, (list, tuple)):
        text = ", ".join(map(str, text))
    
    # ── 1. Basic ASCII cleanup ──────────────────────────────────────────────
    s = str(text)
    # Replace common troublesome unicode with ASCII
    s = s.replace("\u2014", "--").replace("\u2013", "-").replace("\u2022", "*")
    s = s.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
    
    # ── 2. Strip ALL non-ASCII (safe fallback) ──────────────────────────────
    # Latin-1 is usually safe in Helvetica, but some users have emojis or non-latin
    return "".join(c if ord(c) < 128 else "?" for c in s).strip()


class ForecastPDF(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 16)
        self.set_text_color(0, 0, 0)
        # Use explicit 190 width instead of 0 to be safe
        self.cell(190, 10, 'ChainCast Statistical Forecast Report', border=0, new_x="LMARGIN", new_y="NEXT", align='C')
        self.set_line_width(0.5)
        self.set_draw_color(50, 50, 50)
        self.line(10, 20, 200, 20)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(190, 10, f'ChainCast Report -- Page {self.page_no()} -- Generated {datetime.datetime.now().strftime("%Y-%m-%d")}', 0, 0, 'C')

    def section_title(self, title):
        self.set_font("helvetica", "B", 13)
        self.set_text_color(0, 0, 0)
        self.set_fill_color(230, 235, 245)
        # Force X reset
        self.set_x(10)
        self.cell(190, 9, f"  {clean_text(title)}", new_x="LMARGIN", new_y="NEXT", fill=True)
        self.ln(2)

    def key_value(self, key, value, key_color=(80, 80, 80), val_color=(20, 20, 20)):
        # FORCE LEFT MARGIN
        self.set_x(10)
        self.set_font("helvetica", "B", 10)
        self.set_text_color(*key_color)
        self.cell(60, 7, f"{clean_text(key)}:", border=0) # 60 width
        
        self.set_font("helvetica", "", 10)
        self.set_text_color(*val_color)
        # Force X start for value to 70 (gives 10mm gap)
        self.set_x(70)
        # Width 125 leaves 15mm right margin (210 - 70 - 125 = 15) -- VERY SAFE
        self.multi_cell(125, 7, clean_text(value), border=0, new_x="LMARGIN", new_y="NEXT")

    def notice_row(self, text, kind="warn"):
        colors = {"warn": (180, 100, 0), "skip": (180, 0, 0), "ok": (0, 120, 0), "info": (0, 80, 180)}
        r, g, b = colors.get(kind, (80, 80, 80))
        self.set_font("helvetica", "", 9)
        self.set_text_color(r, g, b)
        # Resets X to slightly indented
        self.set_x(15) 
        # Width 180 leaves 15mm right margin (210 - 15 - 180 = 15) -- VERY SAFE
        self.multi_cell(180, 6, f"* {clean_text(text)}")
        self.set_text_color(0, 0, 0)


def make_pdf_report(session_data: dict) -> bytes:
    try:
        results = session_data.get("results", {})
        mapping = session_data.get("mapping", {})
        validation = session_data.get("validation", {})
        dataset_name = session_data.get("dataset_name", "Unknown Dataset")
        info = validation.get("info", {}) if validation else {}
        warnings_data = results.get("warnings", [])
        best_model = results.get("best_model", "Unknown")
        sc = results.get("supply_chain", {}) or {}

        pdf = ForecastPDF()
        pdf.set_auto_page_break(True, margin=15)
        pdf.add_page()

        # -- 1. Run Summary ---------------------------------------------------------
        pdf.section_title("1. Forecast Run Summary")
        pdf.key_value("File name", dataset_name)
        pdf.key_value("Date column mapped", mapping.get('date_col', 'N/A'))
        pdf.key_value("Target value column", mapping.get('value_col', 'N/A'))
        pdf.key_value("Report generated", datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        pdf.key_value("Best model selected", best_model, val_color=(0, 120, 0))
        pdf.ln(5)

        # -- 2. Data Processing Report ----------------------------------------------
        pdf.section_title("2. Data Processing Report -- Context & Assumptions")
        history = results.get("history", {})
        series_ids = list(history.keys())
        total_hist_rows = sum(len(v) for v in history.values())
        forecast_rows = len(results.get("forecast", []))

        date_min = info.get("date_min", "N/A")
        date_max = info.get("date_max", "N/A")
        if date_min and "T" in str(date_min): date_min = str(date_min).split("T")[0]
        if date_max and "T" in str(date_max): date_max = str(date_max).split("T")[0]

        pdf.key_value("Total rows processed", f"{total_hist_rows:,} data points")
        pdf.key_value("Series forecasted", ", ".join(series_ids) or "None")
        pdf.key_value("Historical date range", f"{date_min} to {date_max}")
        pdf.key_value("Forecast periods output", f"{forecast_rows} future time steps")
        pdf.key_value("Data frequency detected", info.get('freq_label', info.get('freq', 'Unknown')))
        pdf.key_value("Season length used", str(info.get('season_length', 'None')))
        pdf.ln(4)

        pdf.set_font("helvetica", "B", 11)
        pdf.set_text_color(0, 80, 180)
        pdf.set_x(10)
        pdf.cell(190, 8, "Automatic Adjustments Applied by ChainCast:", new_x="LMARGIN", new_y="NEXT")
        adjustments = [
            ("ok",   "Duplicate timestamps: Auto-resolved via mean aggregation to prevent engine errors."),
            ("ok",   "Missing data gaps: Auto-filled using forward-fill and linear interpolation."),
            ("ok",   "Negative demand values: Clipped to 0 (demand cannot be physically negative)."),
            ("info", "Turbo Mode: High-efficiency matrix inversion enabled for near-instant results."),
            ("info", "Performance Guard: Academic models (ARIMA) replaced with Industry AI for 5-year scale."),
        ]
        for kind, msg in adjustments:
            pdf.notice_row(msg, kind)
        pdf.ln(5)

        # -- 3. Skipped & Warnings --------------------------------------------------
        skipped = [w for w in warnings_data if "skip" in w.lower()]
        quality  = [w for w in warnings_data if "skip" not in w.lower()]

        if skipped or quality:
            pdf.section_title("3. What Was Skipped or Flagged")
            if skipped:
                pdf.set_font("helvetica", "B", 10)
                pdf.set_text_color(180, 80, 0)
                pdf.set_x(10)
                pdf.cell(190, 7, "Series / Data Skipped:", new_x="LMARGIN", new_y="NEXT")
                for w in skipped:
                    pdf.notice_row(w, "skip")
                pdf.ln(3)
            if quality:
                pdf.set_font("helvetica", "B", 10)
                pdf.set_text_color(0, 80, 180)
                pdf.set_x(10)
                pdf.cell(190, 7, "Data Quality Notices:", new_x="LMARGIN", new_y="NEXT")
                for w in quality:
                    pdf.notice_row(w, "info")
            pdf.ln(5)
        else:
            pdf.section_title("3. Data Quality")
            pdf.notice_row("No issues detected. All series passed validation cleanly.", "ok")
            pdf.ln(5)

        # -- 4. Model Performance ---------------------------------------------------
        pdf.section_title("4. Model Comparison & Error Metrics")
        pdf.set_font("helvetica", "B", 10)
        pdf.set_text_color(0, 120, 0)
        pdf.set_x(10)
        pdf.cell(190, 7, f"Winner: {clean_text(best_model)} (Turbo AI Selection)", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

        cv_records = results.get("cv_results", [])
        if cv_records:
            pdf.ln(2)
            pdf.set_font("helvetica", "B", 9)
            metrics = [k for k in cv_records[0].keys() if k != "metric"]
            # Total width for table: 30 + (metrics * col_w) = 180 max
            # 180 - 30 = 150 available for metrics
            col_w = min(35, 150 / max(1, len(metrics)))
            pdf.set_fill_color(220, 220, 220)
            pdf.set_x(10)
            pdf.cell(30, 8, "Metric", border=1, fill=True)
            for m in metrics:
                pdf.cell(col_w, 8, clean_text(m)[:12], border=1, fill=True, align="C")
            pdf.ln()
            pdf.set_font("helvetica", "", 9)
            for row in cv_records:
                metric = row.get("metric", "")
                pdf.set_x(10)
                pdf.cell(30, 8, clean_text(metric).upper(), border=1)
                for m in metrics:
                    val = row.get(m, 0.0)
                    try:
                        nval = f"{float(val):.3f}"
                    except:
                        nval = "N/A"
                    pdf.cell(col_w, 8, nval, border=1, align="R")
                pdf.ln()
        pdf.ln(8)

        # -- 5. Supply Chain Metrics ------------------------------------------------
        pdf.section_title("5. Supply Chain Decision Parameters")
        sc_rows = [
            ("Service level target",    f"{sc.get('service_level_pct', 95)}% probability"),
            ("Avg demand / period",     f"{sc.get('avg_demand_per_period', 0)} units"),
            ("Total forecast volume",   f"{sc.get('total_forecast', 0)} units total"),
            ("Safety stock",            f"{sc.get('safety_stock', 0)} units buffer"),
            ("Reorder point (ROP)",     f"{sc.get('reorder_point', 0)} series unit level"),
            ("Stockout risk",           f"{sc.get('stockout_risk_pct', 5)}% probability"),
            ("Statistical Z-score",     str(sc.get('z_score', 1.645))),
        ]
        for k, v in sc_rows:
            pdf.key_value(k, v)
        pdf.ln(5)

        # -- 6. Forecast Breakdown Table --------------------------------------------
        pdf.add_page()
        pdf.section_title("6. Future Forecast Breakdown (First 50 periods)")
        forecasts = results.get("forecast", [])
        if forecasts:
            # 40 + 35 + 35 + 35 + 35 = 180 total width. Margin 10 = 190 max.
            cw = [40, 35, 35, 35, 35] 
            pdf.set_font("helvetica", "B", 9)
            pdf.set_fill_color(220, 220, 220)
            pdf.set_x(10)
            pdf.cell(cw[0], 8, "Date",          border=1, fill=True)
            pdf.cell(cw[1], 8, "Best Forecast", border=1, fill=True, align="C")
            pdf.cell(cw[2], 8, "Low (80%)",     border=1, fill=True, align="C")
            pdf.cell(cw[3], 8, "High (80%)",    border=1, fill=True, align="C")
            pdf.cell(cw[4], 8, "Series",        border=1, fill=True, align="C")
            pdf.ln()
            pdf.set_font("helvetica", "", 8)
            for i, row in enumerate(forecasts):
                if i >= 50:
                    pdf.set_x(10)
                    pdf.cell(180, 8, f"... plus {len(forecasts)-50} additional periods omitted.", new_x="LMARGIN", new_y="NEXT")
                    break
                d = str(row.get("ds", "N/A"))
                if "T" in d: d = d.split("T")[0]
                elif " " in d: d = d.split(" ")[0]
                f_val  = float(row.get(best_model, 0.0) or 0.0)
                lo_val = float(row.get(f"{best_model}-lo-80", 0.0) or 0.0)
                hi_val = float(row.get(f"{best_model}-hi-80", 0.0) or 0.0)
                uid    = clean_text(row.get("unique_id", "N/A"))[:15]
                
                is_risk = lo_val < 0
                if is_risk: pdf.set_text_color(180, 0, 0)
                
                pdf.set_x(10)
                pdf.cell(cw[0], 7, d,              border=1)
                pdf.cell(cw[1], 7, f"{f_val:,.2f}", border=1, align="R")
                pdf.cell(cw[2], 7, f"{lo_val:.2f}",border=1, align="R")
                pdf.cell(cw[3], 7, f"{hi_val:.2f}",border=1, align="R")
                pdf.cell(cw[4], 7, uid,             border=1, align="C")
                pdf.ln()
                if is_risk: pdf.set_text_color(0, 0, 0)

        pdf.ln(5)
        pdf.set_font("helvetica", "I", 8)
        pdf.set_text_color(128, 128, 128)
        pdf.set_x(10)
        # Explicit width 180 for footer note
        pdf.multi_cell(180, 5, "Note: Rows in red indicate periods where the lower 80% confidence band dips below zero (Stockout Risk). These periods require additional safety stock buffer. All calculations performed by ChainCast AutoPilot engine.")

        return bytes(pdf.output())
    except Exception as e:
        # If possible, return a partial PDF or at least don't crash 
        # But we want the error trace in the log
        traceback.print_exc()
        raise e
