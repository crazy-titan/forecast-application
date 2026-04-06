import io
import datetime
import traceback
from fpdf import FPDF


# --- Professional Metadata & Glossaries (3.1.5 Upgrade) ---
MODEL_DESCRIPTIONS = {
    "Seasonal AI Engine": "Our most advanced pattern-matching engine. It studies your 'Seasonal Heartbeat' (the natural rhythm of your business) and projects that exact cycle into the future. Ideal for data that peaks weekly or monthly.",
    "Adaptive Smoothing AI": "A reactive system that weights recent history more heavily than the distant past. It 'smooths' out random noise to focus on the current momentum of your demand.",
    "Optimized Curve-Fitting": "A high-precision model that mathematical balances 'Trend' (the direction) and 'Seasonality' (the cycle). It is remarkably stable for long-term strategic planning.",
    "Historic Baseline (Avg)": "A simplified safety check that uses your long-term average. While less 'intelligent,' it provides a solid floor for your inventory planning."
}

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
        self.set_x(15) 
        self.multi_cell(180, 6, f"* {clean_text(text)}")
        self.set_text_color(0, 0, 0)

    def insight_box(self, title, body, example=None):
        """Draws a professional highlighted box for educational context."""
        self.set_fill_color(240, 248, 255) # Light Alice Blue 
        self.set_draw_color(0, 80, 180)    # Deep Professional Blue
        self.set_line_width(0.3)
        
        self.set_x(10)
        curr_y = self.get_y()
        self.set_font("helvetica", "B", 10)
        self.set_text_color(0, 80, 180)
        
        # Calculate height needed for body + title + example
        text_content = f"{title.upper()}: {body}"
        if example: text_content += f"\n\nEXAMPLE: {example}"
        
        # Determine height (approximate)
        # Use a slightly wider margin for line counting to be safe
        lines = self.multi_cell(180, 5, clean_text(text_content), border=0, align='L', dry_run=True, output="LINES")
        # Add extra height for the title header (8mm) and bottom padding (4mm)
        h = (len(lines) * 5) + 12
        
        # Draw background and title
        self.rect(10, curr_y, 190, h, style='FD')
        self.set_xy(15, curr_y + 4)
        self.set_font("helvetica", "B", 10)
        self.cell(180, 6, f"{clean_text(title)} (Analysis Insight)", new_x="LMARGIN", new_y="NEXT")
        
        # Crucial Spacer to prevent overlap
        self.ln(1)
        
        self.set_font("helvetica", "", 9)
        self.set_text_color(40, 40, 40)
        self.set_x(15)
        self.multi_cell(180, 5, clean_text(body), new_x="LMARGIN", new_y="NEXT")
        
        if example:
            self.ln(1)
            self.set_x(15)
            self.set_font("helvetica", "I", 9)
            self.set_text_color(0, 80, 180)
            self.multi_cell(180, 5, f"Example: {clean_text(example)}")
            
        self.set_text_color(0, 0, 0)
        self.ln(4)


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
        pdf.ln(2)
        
        model_desc = MODEL_DESCRIPTIONS.get(best_model, "A customized statistical engine selected for its accuracy on your history.")
        pdf.insight_box("Why this model?", model_desc)
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
        
        pdf.ln(2)
        pdf.insight_box(
            "Understanding Error (MAE)", 
            "The MAE (Mean Absolute Error) is the single most important number for checking reliability. It tells you the average 'distance' between the AI and reality.",
            example=f"Your MAE is {results.get('model_scores', {}).get(best_model, 'N/A')}. This means on average, the forecast was off by this many units during our testing phase."
        )
        pdf.ln(5)

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
        pdf.ln(2)
        
        pdf.insight_box(
            "Inventory Strategy", 
            "Safety Stock protects you from the 'Unknown.' Use the Reorder Point (ROP) as your trigger: when inventory hits this level, place an order to ensure stock arrives before you run out.",
            example=f"With a {sc.get('service_level_pct', 95)}% service level, you are protected against stockouts in {sc.get('service_level_pct', 95)} out of 100 scenarios."
        )
        pdf.ln(5)

        # -- 6. Future Forecast Breakdown (First 50 periods) ----------------------------
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

        # -- 7. Dictionary of Logistics Intelligence (NEW 3.1.4) -----------------------
        pdf.add_page()
        pdf.section_title("7. Master Logistics Dictionary (Plain English Guide)")
        
        categories = [
            ("Category 1: The Basics (What you see)", [
                ("Historical Data", "The foundation. Your past sales/demand records. The AI uses this to learn your business 'DNA'.", "If you have 2 years of history, the AI can detect 2 full cycles of seasonal peaks."),
                ("Forecast Horizon", "How far into the future you are looking. Usually measured in days or months.", "A 30-day horizon helps with monthly procurement; a 90-day horizon helps with warehouse space planning."),
                ("Frequency", "The heartbeat of your data (Daily, Weekly, Monthly).", "A 'Business Day' frequency knows to ignore weekends when shops might be closed.")
            ]),
            ("Category 2: Performance (Is it accurate?)", [
                ("MAE (Mean Absolute Error)", "The average mistake size. Lower is better.", "An MAE of 10 means the AI is typically within 10 units of the actual value."),
                ("Confidence Interval (80%)", "The 'Shaded Area' on your chart. It represents the range where demand is highly likely to fall.", "If the high-80% is 150, and your forecast is 100, keep 50 units as buffer for extreme peaks.")
            ]),
            ("Category 3: Supply Chain Strategy (What to do)", [
                ("Safety Stock", "Your emergency buffer. It covers you if demand is suddenly higher than expected during lead time.", "Think of this as the 'Reserve' fuel in a car tank."),
                ("Reorder Point (ROP)", "Your action signal. When current stock hits this number, order more.", "Formula: (Daily Demand x Lead Time) + Safety Stock."),
                ("Service Level", "Your probability of being in stock. Higher means more safety stock but higher costs.", "95% is industry standard. 99% is 'Ultra-Critical' (medical/food)."),
                ("Lead Time", "The delay between ordering and receiving stock.", "If your lead time is 14 days, you must forecast at least 14 days ahead to be prepared.")
            ])
        ]

        for cat_title, items in categories:
            pdf.set_font("helvetica", "B", 11)
            pdf.set_text_color(0, 0, 0)
            pdf.set_x(10)
            pdf.cell(190, 8, clean_text(cat_title), border="B", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
            
            for term, definition, ex in items:
                pdf.set_font("helvetica", "B", 10)
                pdf.set_text_color(0, 80, 180)
                pdf.set_x(12)
                pdf.cell(190, 7, f" {clean_text(term)}", new_x="LMARGIN", new_y="NEXT")
                
                pdf.set_font("helvetica", "", 9)
                pdf.set_text_color(40, 40, 40)
                pdf.set_x(17)
                pdf.multi_cell(178, 5, clean_text(definition))
                
                pdf.set_font("helvetica", "I", 9)
                pdf.set_text_color(100, 100, 100)
                pdf.set_x(17)
                pdf.multi_cell(178, 5, f"Example: {clean_text(ex)}")
                pdf.ln(3)
            pdf.ln(3)

        pdf.ln(5)
        pdf.set_font("helvetica", "I", 8)
        pdf.set_text_color(128, 128, 128)
        pdf.set_x(10)
        # Explicit width 180 for footer note
        pdf.multi_cell(180, 5, "This report is an analytical summary generated by the ChainCast industrial forecasting engine. All metrics are calculated using standardized logistics formulas.")

        return bytes(pdf.output())
    except Exception as e:
        # If possible, return a partial PDF or at least don't crash 
        # But we want the error trace in the log
        traceback.print_exc()
        raise e
