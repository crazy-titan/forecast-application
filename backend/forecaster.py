import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List

from statsforecast import StatsForecast
from statsforecast.models import Naive, HistoricAverage, SeasonalNaive, AutoARIMA
from utilsforecast.losses import mae, mse
from utilsforecast.evaluation import evaluate

def build_sf_dataframe(
    df: pd.DataFrame,
    date_col: str,
    value_col: str,
    id_col: Optional[str] = None,
    selected: Optional[List[str]] = None,
) -> pd.DataFrame:
    out = pd.DataFrame()
    out["ds"] = pd.to_datetime(df[date_col])
    
    if df[value_col].dtype == "object":
        val_clean = df[value_col].astype(str).str.replace(r'[^\d\.-]', '', regex=True)
        out["y"] = pd.to_numeric(val_clean, errors="coerce")
    else:
        out["y"] = pd.to_numeric(df[value_col], errors="coerce")
    
    if id_col and id_col in df.columns:
        out["unique_id"] = df[id_col].astype(str).values
        if out["unique_id"].str.lower().isin(["nan", "none", ""]).all():
            out["unique_id"] = "Series_1"
    else:
        out["unique_id"] = "Series_1"
    
    # --- Duplicate Resolution ---
    # Electricity datasets often have multiple entries per timestamp if no ID is selected.
    # We aggregate these to mean() to avoid StatsForecast crashing.
    if out.duplicated(subset=["unique_id", "ds"]).any():
        out = out.groupby(["unique_id", "ds"])["y"].mean().reset_index()
    
    out = out.sort_values(["unique_id", "ds"]).reset_index(drop=True)
    out["y"] = out.groupby("unique_id")["y"].transform(lambda x: x.ffill().bfill().interpolate())
    if selected:
        out = out[out["unique_id"].isin(selected)]
    if out.empty:
        out = pd.DataFrame({"unique_id": ["Series_1"], "ds": [pd.Timestamp.now()], "y": [0.0]})
    return out.reset_index(drop=True)

def run_pipeline(
    df_sf: pd.DataFrame,
    freq: str,
    season_length: int,
    horizon: int,
    n_windows: int = 5,
    mode: str = "auto",
    manual_params: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    results = {"errors": []}

    if df_sf.empty or df_sf["unique_id"].nunique() == 0:
        raise ValueError("No valid time series found.")

    # Minimum rows needed for a series to be forecastable
    min_rows_needed = max(horizon * 2, season_length * 2, 10)

    # Filter out series that are too short
    series_lengths = df_sf.groupby("unique_id").size()
    long_enough = series_lengths[series_lengths >= min_rows_needed].index.tolist()
    short_series = series_lengths[series_lengths < min_rows_needed].index.tolist()

    if short_series:
        results["errors"].append(
            f"Skipping {len(short_series)} series with insufficient data (< {min_rows_needed} rows): {', '.join(short_series[:5])}"
            + ("..." if len(short_series) > 5 else "")
        )
        df_sf = df_sf[df_sf["unique_id"].isin(long_enough)]
        if df_sf.empty:
            raise ValueError(
                f"No series has at least {min_rows_needed} rows. "
                f"Reduce forecast horizon (currently {horizon}) or season length (currently {season_length})."
            )

    # Validate remaining series
    for uid, group in df_sf.groupby("unique_id"):
        if group["y"].std() < 1e-6:
            results["errors"].append(f"Series '{uid}' is constant. Forecasting may produce trivial results.")

    # Split train/test
    test = df_sf.groupby("unique_id").tail(horizon)
    train = df_sf.drop(test.index).reset_index(drop=True)
    if train.empty:
        raise ValueError(f"Horizon ({horizon}) too large for all remaining series. Reduce horizon.")
    if len(train) < horizon * 3:
        results["errors"].append(f"Training data is limited ({len(train)} rows). Forecast may be unreliable.")

    # Models
    baseline = [Naive(), SeasonalNaive(season_length=season_length)]
    historic_avg = HistoricAverage()
    # Scale-Aware Optimization: Reduce search space for long series to prevent hangs
    avg_len = len(train) / train["unique_id"].nunique()
    is_large = avg_len > 2500 or train["unique_id"].nunique() > 20
    
    if mode == "auto":
        sarima = AutoARIMA(season_length=season_length, alias="SARIMA",
                           max_p=3 if is_large else 5, max_q=3 if is_large else 5,
                           max_P=1 if is_large else 2, max_Q=1 if is_large else 2)
        arima = AutoARIMA(season_length=1, alias="ARIMA",
                          max_p=3 if is_large else 5, max_q=3 if is_large else 5)
    else:
        mp = manual_params or {}
        d_val = min(mp.get("d", 2), 2)
        D_val = min(mp.get("D", 1), 1)
        sarima = AutoARIMA(season_length=season_length, alias="SARIMA",
                           max_p=mp.get("p",3), max_d=d_val, max_q=mp.get("q",3),
                           max_P=mp.get("P",2), max_D=D_val, max_Q=mp.get("Q",2))
        arima = AutoARIMA(season_length=1, alias="ARIMA",
                          max_p=mp.get("p",3), max_d=d_val, max_q=mp.get("q",3))
    all_models = baseline + [historic_avg, arima, sarima]

    # Fit with fallback
    try:
        sf = StatsForecast(models=all_models, freq=freq, n_jobs=1)
        sf.fit(train)
    except Exception as e:
        results["errors"].append(f"AutoARIMA/SARIMA failed ({str(e)}). Fallback to baseline.")
        try:
            sf = StatsForecast(models=baseline, freq=freq, n_jobs=1)
            sf.fit(train)
            all_models = baseline
            results["best_model"] = "SeasonalNaive"
            results["model_scores"] = {}
        except Exception as e2:
            raise ValueError(f"Baseline models failed: {str(e2)}")

    # Predictions
    point_preds = sf.predict(h=horizon)
    try:
        prob_preds = sf.predict(h=horizon, level=[80,95])
    except:
        prob_preds = point_preds
        results["errors"].append("Prediction intervals unavailable.")
    results["point_preds"] = point_preds
    results["prob_preds"] = prob_preds

    # Check for zero forecast and fallback to Naive if needed
    forecast_col = None
    for col in prob_preds.columns:
        if col not in ["unique_id", "ds"] and not col.startswith("-"):
            forecast_col = col
            break
    if forecast_col and prob_preds[forecast_col].abs().max() < 1e-6:
        results["errors"].append("SeasonalNaive produced zero forecast. Falling back to Naive (last observed value).")
        last_values = train.groupby("unique_id")["y"].last().reset_index()
        prob_preds = prob_preds.drop(columns=[forecast_col])
        prob_preds = prob_preds.merge(last_values, on="unique_id", how="left")
        prob_preds[forecast_col] = prob_preds["y"]
        prob_preds = prob_preds.drop(columns=["y"])
        results["prob_preds"] = prob_preds
        results["best_model"] = "Naive (fallback)"

    # Cross-validation (skip Naive and HistoricAverage)
    try:
        actual_windows = min(n_windows, max(2, len(train)//(horizon*2)))
        if actual_windows >= 1:
            adv_instances = [m for m in all_models if type(m).__name__ not in ("Naive", "HistoricAverage", "SeasonalNaive")]
            base_instances = [m for m in all_models if type(m).__name__ in ("Naive", "HistoricAverage", "SeasonalNaive")]
            all_model_names = [m.alias if hasattr(m,'alias') else m.__class__.__name__ for m in all_models]
            
            if adv_instances:
                sf_adv = StatsForecast(models=adv_instances, freq=freq, n_jobs=1)
                cv_adv = sf_adv.cross_validation(h=horizon, df=df_sf, n_windows=actual_windows, step_size=horizon, refit=False)
                if "unique_id" not in cv_adv.columns: cv_adv = cv_adv.reset_index()
                cv_df = cv_adv
            else:
                cv_df = pd.DataFrame()
                
            if base_instances:
                sf_base = StatsForecast(models=base_instances, freq=freq, n_jobs=1)
                cv_base = sf_base.cross_validation(h=horizon, df=df_sf, n_windows=actual_windows, step_size=horizon, refit=True)
                if "unique_id" not in cv_base.columns: cv_base = cv_base.reset_index()
                if cv_df.empty:
                    cv_df = cv_base
                else:
                    for col in cv_base.columns:
                        if col not in ["unique_id", "ds", "cutoff", "y"]:
                            cv_df[col] = cv_base[col].values
            
            if not cv_df.empty:
                present = [m for m in all_model_names if m in cv_df.columns]
                if present:
                    eval_df = evaluate(cv_df.drop(columns=["cutoff"], errors="ignore"), metrics=[mae,mse], models=present)
                    eval_agg = eval_df.drop(columns=["unique_id"], errors="ignore").groupby("metric").mean().reset_index()
                    results["eval_agg"] = eval_agg
                    mae_row = eval_agg[eval_agg["metric"]=="mae"]
                    if not mae_row.empty:
                        mae_vals = {k:float(v) for k,v in mae_row.iloc[0][present].items()}
                        results["best_model"] = min(mae_vals, key=mae_vals.get)
                        results["model_scores"] = mae_vals
                    else:
                        results["best_model"] = "SeasonalNaive"
                        results["model_scores"] = {}
                else:
                    results["best_model"] = "SeasonalNaive"
                    results["model_scores"] = {}
            else:
                results["errors"].append("No suitable models for CV.")
                results["best_model"] = "SeasonalNaive"
                results["model_scores"] = {}
        else:
            results["errors"].append("Not enough data for CV.")
            results["best_model"] = "SeasonalNaive"
            results["model_scores"] = {}
    except Exception as e:
        results["errors"].append(f"CV failed: {str(e)}")
        results["best_model"] = "SeasonalNaive"
        results["model_scores"] = {}
        results["eval_agg"] = pd.DataFrame()

    # Residuals (robust)
    try:
        fitted = None
        if hasattr(sf, "forecast_fitted_values"):
            try:
                fitted = sf.forecast_fitted_values()
            except Exception:
                pass
        if fitted is None:
            safe_model_instances = [m for m in all_models if type(m).__name__ not in ("Naive", "HistoricAverage", "SeasonalNaive")]
            if not safe_model_instances:
                raise ValueError("No models available for computing residuals via cross-validation fallback.")
            sf_resid = StatsForecast(models=safe_model_instances, freq=freq, n_jobs=1)
            fitted = sf_resid.cross_validation(h=1, df=df_sf, n_windows=1, step_size=1)
            if "unique_id" not in fitted.columns:
                fitted = fitted.reset_index()
        
        pred_col = None
        for col in fitted.columns:
            if col == results["best_model"] or (col not in ["unique_id","ds","y","cutoff"] and "lo" not in col and "hi" not in col):
                pred_col = col
                break
        if pred_col and pred_col in fitted.columns:
            residuals = fitted["y"] - fitted[pred_col]
            results["residuals"] = {
                "values": residuals.dropna().tolist(),
                "dates": fitted["ds"].astype(str).tolist()[:len(residuals.dropna())],
            }
            try:
                from statsmodels.stats.diagnostic import acorr_ljungbox
                resid_clean = residuals.dropna()
                if len(resid_clean) > 10:
                    lb = acorr_ljungbox(resid_clean, lags=10, return_df=True)
                    ok = (lb["lb_pvalue"] > 0.05).all()
                    results["ljung_box"] = {
                        "pass": bool(ok),
                        "message": "Residuals are white noise ✓" if ok else "Residuals have patterns ✗"
                    }
                else:
                    results["ljung_box"] = {"pass": None, "message": "Not enough residuals."}
            except:
                results["ljung_box"] = {"pass": None, "message": "Ljung-Box unavailable."}
        else:
            raise ValueError("No prediction column.")
    except Exception as e:
        results["errors"].append(f"Residuals failed: {str(e)}")
        results["residuals"] = None
        results["ljung_box"] = {"pass": None, "message": "Residuals not computed."}

    # History
    results["history"] = {
        uid: grp[["ds","y"]].assign(ds=grp["ds"].astype(str)).to_dict("records")
        for uid, grp in df_sf.groupby("unique_id")
    }
    results["horizon"] = horizon
    results["season_length"] = season_length
    results["freq"] = freq
    results["n_series"] = int(df_sf["unique_id"].nunique())
    results["series_list"] = df_sf["unique_id"].unique().tolist()
    return results

def compute_supply_chain_metrics(
    forecast_values: Optional[List[float]],
    forecast_errors: Optional[List[float]],
    lead_time_days: int,
    holding_cost: float = 0.0,
    stockout_cost: float = 0.0,
    service_level: float = 0.95,
) -> Dict[str, Any]:
    try:
        z = {0.90:1.28, 0.95:1.645, 0.99:2.326}.get(float(service_level), 1.645)
        fv = [float(v) for v in (forecast_values or []) if v is not None and v >= 0]
        fe = [float(v) for v in (forecast_errors or []) if v is not None]
        if not fv:
            return _empty_sc_metrics()
        avg = float(np.mean(fv))
        total = float(np.sum(fv))
        std = float(np.std(fe)) if len(fe) > 1 else (avg * 0.2 if avg > 0 else 1.0)
        lt = max(int(lead_time_days), 1)
        safety_stock = round(z * std * np.sqrt(lt), 1)
        rop = round(avg * lt + safety_stock, 1)
        stockout_pct = round((1 - float(service_level)) * 100, 1)
        sc = {
            "avg_demand_per_period": round(avg, 1),
            "total_forecast": round(total, 1),
            "safety_stock": safety_stock,
            "reorder_point": rop,
            "stockout_risk_pct": stockout_pct,
            "service_level_pct": round(float(service_level) * 100, 0),
            "z_score": z,
        }
        hc = float(holding_cost or 0)
        sc_ = float(stockout_cost or 0)
        if hc > 0 and sc_ > 0 and safety_stock > 0 and avg > 0:
            sc["annual_holding_cost"] = round(safety_stock * hc * 365, 2)
            sc["annual_stockout_cost"] = round((stockout_pct / 100) * 12 * avg * sc_, 2)
            sc["total_annual_cost"] = round(sc["annual_holding_cost"] + sc["annual_stockout_cost"], 2)
        return sc
    except Exception:
        return _empty_sc_metrics()

def _empty_sc_metrics() -> Dict[str, Any]:
    return {
        "avg_demand_per_period": 0, "total_forecast": 0,
        "safety_stock": 0, "reorder_point": 0,
        "stockout_risk_pct": 5.0, "service_level_pct": 95.0, "z_score": 1.645,
    }