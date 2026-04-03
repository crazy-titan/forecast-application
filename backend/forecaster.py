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
    """Convert raw dataframe to StatsForecast format (unique_id, ds, y)."""
    out = pd.DataFrame()
    out["unique_id"] = (
        df[id_col].astype(str) if (id_col and id_col in df.columns) else "Series_1"
    )
    out["ds"] = pd.to_datetime(df[date_col])
    out["y"] = pd.to_numeric(df[value_col], errors="coerce")
    out = out.sort_values(["unique_id", "ds"]).reset_index(drop=True)

    # Interpolate missing values per series
    out["y"] = out.groupby("unique_id")["y"].transform(
        lambda x: x.ffill().bfill().interpolate()
    )
    if selected:
        out = out[out["unique_id"].isin(selected)]
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
    """
    Run forecasting pipeline with fallbacks, cross-validation, and residual diagnostics.
    """
    results: Dict[str, Any] = {"errors": []}

    # Ensure non-negative demand
    df_sf["y"] = df_sf["y"].clip(lower=0)

    # Validate data length and constant series
    min_rows_needed = max(horizon * 2, season_length * 2, 10)
    for uid, group in df_sf.groupby("unique_id"):
        if len(group) < min_rows_needed:
            raise ValueError(
                f"Series '{uid}' has only {len(group)} rows. "
                f"Need at least {min_rows_needed} rows."
            )
        if group["y"].std() < 1e-6:
            raise ValueError(
                f"Series '{uid}' is constant (no variation). Forecasting not possible."
            )

    # Split train/test
    test = df_sf.groupby("unique_id").tail(horizon)
    train = df_sf.drop(test.index).reset_index(drop=True)
    if len(train) < horizon * 3:
        raise ValueError(f"Not enough training data. Need at least {horizon*3} rows.")

    # Baseline models (exclude HistoricAverage from CV later)
    baseline = [Naive(), SeasonalNaive(season_length=season_length)]
    historic_avg = HistoricAverage()

    if mode == "auto":
        sarima = AutoARIMA(season_length=season_length, alias="SARIMA")
        arima = AutoARIMA(season_length=1, alias="ARIMA")
    else:
        mp = manual_params or {}
        d_val = min(mp.get("d", 2), 2)
        D_val = min(mp.get("D", 1), 1)
        sarima = AutoARIMA(
            season_length=season_length,
            alias="SARIMA",
            max_p=mp.get("p", 3),
            max_d=d_val,
            max_q=mp.get("q", 3),
            max_P=mp.get("P", 2),
            max_D=D_val,
            max_Q=mp.get("Q", 2),
        )
        arima = AutoARIMA(
            season_length=1,
            alias="ARIMA",
            max_p=mp.get("p", 3),
            max_d=d_val,
            max_q=mp.get("q", 3),
        )

    all_models = baseline + [historic_avg, arima, sarima]

    # Fit with fallback
    fit_success = False
    try:
        sf = StatsForecast(models=all_models, freq=freq, n_jobs=1)
        sf.fit(train)
        fit_success = True
    except Exception as e:
        results["errors"].append(
            f"AutoARIMA/SARIMA failed ({str(e)}). Falling back to Naive + SeasonalNaive."
        )
        try:
            sf = StatsForecast(models=baseline, freq=freq, n_jobs=1)
            sf.fit(train)
            fit_success = True
            all_models = baseline
            results["best_model"] = "SeasonalNaive"
            results["model_scores"] = {}
        except Exception as e2:
            raise ValueError(f"Even baseline models failed: {str(e2)}")

    if not fit_success:
        raise ValueError("Model fitting failed after fallback attempt.")

    # Predictions
    try:
        point_preds = sf.predict(h=horizon)
        results["point_preds"] = point_preds
    except Exception as e:
        raise ValueError(f"Prediction failed: {str(e)}")

    try:
        prob_preds = sf.predict(h=horizon, level=[80, 95])
        results["prob_preds"] = prob_preds
    except Exception as e:
        results["prob_preds"] = point_preds
        results["errors"].append(f"Prediction intervals unavailable: {str(e)}")

    # Cross-validation (skip models without 'forward' method)
    try:
        actual_windows = min(n_windows, max(2, len(train) // (horizon * 2)))
        if actual_windows >= 1:
            # Identify safe models (exclude HistoricAverage)
            safe_models = []
            for model in all_models:
                model_name = getattr(model, "alias", model.__class__.__name__)
                if "HistoricAverage" in model_name:
                    continue
                safe_models.append(model_name)

            if safe_models:
                cv_df = sf.cross_validation(
                    h=horizon,
                    df=df_sf,
                    n_windows=actual_windows,
                    step_size=horizon,
                    refit=False,
                )
                # Evaluate only models present in cv_df
                present = [m for m in safe_models if m in cv_df.columns]
                if present:
                    eval_df = evaluate(
                        cv_df.drop(columns=["cutoff"], errors="ignore"),
                        metrics=[mae, mse],
                        models=present,
                    )
                    eval_agg = (
                        eval_df.drop(columns=["unique_id"], errors="ignore")
                        .groupby("metric")
                        .mean()
                        .reset_index()
                    )
                    results["eval_agg"] = eval_agg
                    mae_row = eval_agg[eval_agg["metric"] == "mae"]
                    if not mae_row.empty:
                        mae_vals = {k: float(v) for k, v in mae_row.iloc[0][present].items()}
                        best = min(mae_vals, key=mae_vals.get)
                        results["best_model"] = best
                        results["model_scores"] = mae_vals
                    else:
                        results["best_model"] = "SeasonalNaive"
                        results["model_scores"] = {}
                else:
                    results["best_model"] = "SeasonalNaive"
                    results["model_scores"] = {}
            else:
                results["errors"].append("No suitable models for cross-validation.")
                results["best_model"] = "SeasonalNaive"
                results["model_scores"] = {}
        else:
            results["errors"].append("Not enough data for cross-validation.")
            results["best_model"] = "SeasonalNaive"
            results["model_scores"] = {}
    except Exception as e:
        results["errors"].append(f"Cross-validation failed: {str(e)}")
        results["best_model"] = "SeasonalNaive"
        results["model_scores"] = {}
        results["eval_agg"] = pd.DataFrame()

    # Residuals
    try:
        if hasattr(sf, "forecast_fitted_values"):
            fitted = sf.forecast_fitted_values()
        else:
            # Fallback: predict on training data with fitted=True
            fitted_preds = sf.predict(h=len(train), fitted=True)
            fitted = pd.DataFrame({"ds": train["ds"], "y": train["y"]})
            pred_col = [c for c in fitted_preds.columns if c not in ["unique_id", "ds"]][0]
            fitted[pred_col] = fitted_preds[pred_col]
        pred_cols = [c for c in fitted.columns if c not in ["unique_id", "ds", "y"]]
        if pred_cols:
            pred_col = pred_cols[0]
            residuals = fitted["y"] - fitted[pred_col]
            results["residuals"] = {
                "values": residuals.dropna().tolist(),
                "dates": fitted["ds"].astype(str).tolist()[: len(residuals.dropna())],
            }
            # Ljung-Box test
            try:
                from statsmodels.stats.diagnostic import acorr_ljungbox
                resid_clean = residuals.dropna()
                if len(resid_clean) > 10:
                    lb = acorr_ljungbox(resid_clean, lags=10, return_df=True)
                    p_vals = lb["lb_pvalue"].values
                    ok = bool((p_vals > 0.05).all())
                    results["ljung_box"] = {
                        "pass": ok,
                        "message": "Residuals are white noise ✓" if ok else "Residuals still have patterns ✗ – try manual mode.",
                    }
                else:
                    results["ljung_box"] = {"pass": None, "message": "Not enough residuals for Ljung-Box test."}
            except Exception:
                results["ljung_box"] = {"pass": None, "message": "Ljung-Box test unavailable."}
        else:
            raise ValueError("No prediction column found")
    except Exception as e:
        results["errors"].append(f"Residuals unavailable: {str(e)}")
        results["residuals"] = None
        results["ljung_box"] = {"pass": None, "message": "Residuals not computed."}

    # History data for charts
    results["history"] = {
        uid: grp[["ds", "y"]].assign(ds=grp["ds"].astype(str)).to_dict("records")
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
    """Compute safety stock, reorder point, and optional costs."""
    try:
        z = {0.90: 1.28, 0.95: 1.645, 0.99: 2.326}.get(float(service_level), 1.645)
        fv = [float(v) for v in (forecast_values or []) if v is not None and v >= 0]
        fe = [float(v) for v in (forecast_errors or []) if v is not None]

        if not fv:
            return _empty_sc_metrics()

        avg = float(np.mean(fv))
        total = float(np.sum(fv))
        if len(fe) > 1:
            std = float(np.std(fe))
        else:
            std = avg * 0.2 if avg > 0 else 1.0
        lt = max(int(lead_time_days), 1)

        safety_stock = round(z * std * float(np.sqrt(lt)), 1)
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
        "avg_demand_per_period": 0,
        "total_forecast": 0,
        "safety_stock": 0,
        "reorder_point": 0,
        "stockout_risk_pct": 5.0,
        "service_level_pct": 95.0,
        "z_score": 1.645,
    }