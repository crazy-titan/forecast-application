import warnings
warnings.filterwarnings("ignore")

import os
import io
import sys
import traceback
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from backend.session_manager import create_session, get_session, update_session, delete_session
from backend.validator import validate_file_size, validate_dataframe
from backend.forecaster import build_sf_dataframe, run_pipeline, compute_supply_chain_metrics

# --- Placeholders for optional features (can be implemented later) ---
SAMPLE_DATASETS = {}  # Add sample datasets later if desired

def get_theory(results, validation):
    """Placeholder for theory generation (can be extended)."""
    return {}

def make_pdf_report(results, validation, theory, sc_metrics, name):
    """Placeholder for PDF export (can be implemented later)."""
    return b"PDF generation not yet implemented."

# --- JSON scrubber for NaN/Inf/Timestamp ---
def deep_clean_json(obj):
    if isinstance(obj, dict):
        return {k: deep_clean_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [deep_clean_json(x) for x in obj]
    elif isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return 0.0
        return obj
    elif isinstance(obj, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(obj).isoformat()
    elif isinstance(obj, (pd.Series, pd.DataFrame)):
        return deep_clean_json(obj.to_dict())
    return obj

# --- FastAPI app initialization ---
app = FastAPI(title="ChainCast API", description="Supply Chain Demand Forecasting", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Helper functions ---
def to_int(val, default):
    if val is None or val == "":
        return default
    try:
        return int(val)
    except:
        return default

def to_float(val, default):
    if val is None or val == "":
        return default
    try:
        return float(val)
    except:
        return default

# --- API Routes ---
@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/session/start")
def start_session():
    return {"session_id": create_session()}

@app.delete("/session/{session_id}")
def end_session(session_id: str):
    delete_session(session_id)
    return {"message": "done"}

@app.get("/datasets")
def list_datasets():
    # Placeholder – can be populated with sample datasets later
    return {"datasets": []}

@app.post("/upload")
async def upload(file: UploadFile = File(...), session_id: str = Form(...)):
    content = await file.read()
    ok, err = validate_file_size(len(content))
    if not ok:
        raise HTTPException(400, err)
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(400, f"Cannot read CSV: {e}")
    
    if len(df) == 0:
        raise HTTPException(400, "File is empty")
    
    sess = get_session(session_id)
    path = os.path.join(sess["folder"], "data.csv")
    df.to_csv(path, index=False)
    update_session(session_id, "df_path", path)
    update_session(session_id, "dataset_name", file.filename)
    
    cols = list(df.columns)
    return {
        "columns": cols,
        "n_rows": len(df),
        "preview": df.head(5).fillna("").to_dict(orient="records"),
        "suggestions": {
            "date_col": next((c for c in cols if c.lower() in ["date","ds","timestamp"]), cols[0]),
            "value_col": next((c for c in cols if c.lower() in ["y","value","demand"]), cols[1] if len(cols)>1 else cols[0]),
            "id_col": next((c for c in cols if c.lower() in ["unique_id","id","sku"]), None),
        }
    }

@app.post("/map-columns")
def map_columns(
    session_id: str = Form(...),
    date_col: str = Form(...),
    value_col: str = Form(...),
    id_col: str = Form(None),
):
    sess = get_session(session_id)
    path = sess.get("df_path")
    if not path or not os.path.exists(path):
        raise HTTPException(400, "No file found. Upload first.")
    
    df = pd.read_csv(path)
    actual_cols = list(df.columns)
    
    def find(col):
        if col in actual_cols:
            return col
        for c in actual_cols:
            if c.lower() == col.lower():
                return c
        return None
    
    final_date = find(date_col)
    final_value = find(value_col)
    final_id = find(id_col) if id_col else None
    
    if not final_date:
        raise HTTPException(400, f"Date column '{date_col}' not found. Columns: {actual_cols}")
    if not final_value:
        raise HTTPException(400, f"Value column '{value_col}' not found. Columns: {actual_cols}")
    
    try:
        validation = validate_dataframe(df, final_date, final_value, final_id)
    except ValueError as e:
        raise HTTPException(422, detail=str(e))
    
    mapping = {"date_col": final_date, "value_col": final_value, "id_col": final_id}
    update_session(session_id, "mapping", mapping)
    update_session(session_id, "validation", validation)
    return {"mapping": mapping, "validation": validation, "series_list": validation["series_list"]}

@app.post("/forecast")
def forecast(
    session_id: str = Form(...),
    mode: str = Form("auto"),
    horizon: Optional[str] = Form(None),
    season_length: Optional[str] = Form(None),
    n_windows: Optional[str] = Form("5"),
    selected_series: Optional[str] = Form(None),
    p: Optional[str] = Form("3"), d: Optional[str] = Form("2"), q: Optional[str] = Form("3"),
    P: Optional[str] = Form("2"), D: Optional[str] = Form("1"), Q: Optional[str] = Form("2"),
    lead_time_days: Optional[str] = Form("7"),
    service_level: Optional[str] = Form("0.95"),
    holding_cost: Optional[str] = Form("0.0"),
    stockout_cost: Optional[str] = Form("0.0"),
):
    sess = get_session(session_id)
    path = sess.get("df_path")
    mapping = sess.get("mapping")
    validation = sess.get("validation")
    if not path or not mapping or not validation:
        raise HTTPException(400, "Incomplete session. Upload and map first.")
    
    df = pd.read_csv(path)
    info = validation.get("info", {})
    freq = info.get("freq", "D")
    final_sl = to_int(season_length, info.get("season_length", 7))
    final_h = to_int(horizon, final_sl * 2)
    n_windows_val = to_int(n_windows, 5)
    
    sel = [s.strip() for s in selected_series.split(",")] if selected_series else None
    
    try:
        df_sf = build_sf_dataframe(df, mapping["date_col"], mapping["value_col"], mapping.get("id_col"), sel)
        df_sf["y"] = df_sf["y"].clip(lower=0)
        
        manual_params = None
        if mode == "manual":
            manual_params = {
                "p": to_int(p,3), "d": to_int(d,2), "q": to_int(q,3),
                "P": to_int(P,2), "D": to_int(D,1), "Q": to_int(Q,2)
            }
        
        results = run_pipeline(df_sf, freq, final_sl, final_h, n_windows_val, mode=mode, manual_params=manual_params)
        
        def extract_forecast_values(r):
            prob = r.get("prob_preds")
            if prob is None or prob.empty:
                return []
            cols = [c for c in prob.columns if not c.startswith(("unique_id","ds","-"))]
            return prob[cols[0]].tolist() if cols else []
        
        def extract_errors(r):
            res = r.get("residuals")
            return res["values"] if res and res.get("values") else []
        
        sc = compute_supply_chain_metrics(
            forecast_values=extract_forecast_values(results),
            forecast_errors=extract_errors(results),
            lead_time_days=to_int(lead_time_days,7),
            service_level=to_float(service_level,0.95),
            holding_cost=to_float(holding_cost,0),
            stockout_cost=to_float(stockout_cost,0)
        )
        
        response = {
            "best_model": results.get("best_model","SARIMA"),
            "model_scores": results.get("model_scores",{}),
            "history": results.get("history",{}),
            "forecast": results.get("prob_preds").fillna(0).to_dict(orient="records") if results.get("prob_preds") is not None else [],
            "cv_results": results.get("eval_agg",pd.DataFrame()).to_dict(orient="records") if results.get("eval_agg") is not None else [],
            "residuals": results.get("residuals"),
            "ljung_box": results.get("ljung_box"),
            "supply_chain": sc,
            "theory": get_theory(results, validation),
            "warnings": results.get("errors",[]) + validation.get("warnings",[])
        }
        
        update_session(session_id, "results", response)
        safe_response = deep_clean_json(response)
        return JSONResponse(content=safe_response)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Forecast failed: {str(e)}")

@app.get("/export/csv/{session_id}")
def export_csv(session_id: str):
    sess = get_session(session_id)
    results = sess.get("results")
    if not results:
        raise HTTPException(400, "Run forecast first.")
    data = results.get("forecast", [])
    if not data:
        raise HTTPException(400, "No forecast data.")
    csv_bytes = pd.DataFrame(data).to_csv(index=False).encode()
    return StreamingResponse(io.BytesIO(csv_bytes), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=forecast.csv"})

@app.get("/export/pdf/{session_id}")
def export_pdf(session_id: str):
    # Placeholder – implement later
    raise HTTPException(501, "PDF export not yet implemented")

@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)