import pandas as pd
import numpy as np
from typing import Tuple, Optional, Dict, Any

def validate_file_size(size_bytes: int, max_mb: int = 10) -> Tuple[bool, Optional[str]]:
    """Check if file size is within limit."""
    max_bytes = max_mb * 1024 * 1024
    if size_bytes > max_bytes:
        return False, f"File size exceeds {max_mb} MB limit."
    return True, None

def validate_dataframe(
    df: pd.DataFrame,
    date_col: str,
    value_col: str,
    id_col: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validate dataframe and return info, stationarity, warnings, series list.
    """
    warnings = []
    info = {}
    stationarity = {}

    # --- Column existence checks ---
    if date_col not in df.columns:
        raise ValueError(f"Date column '{date_col}' not found. Available: {list(df.columns)}")
    if value_col not in df.columns:
        raise ValueError(f"Value column '{value_col}' not found. Available: {list(df.columns)}")
    if id_col and id_col not in df.columns:
        warnings.append(f"ID column '{id_col}' not found – treating as single series.")
        id_col = None

    # --- Date column conversion ---
    try:
        df["_date"] = pd.to_datetime(df[date_col], errors='coerce')
        if df["_date"].isna().all():
            # try alternative parsing
            df["_date"] = pd.to_datetime(df[date_col], errors='coerce', dayfirst=True)
        if df["_date"].isna().any():
            n_invalid = df["_date"].isna().sum()
            warnings.append(f"{n_invalid} rows with invalid dates. They will be dropped.")
            df = df.dropna(subset=["_date"])
            if df.empty:
                raise ValueError("No valid dates found after cleaning.")
        df = df.sort_values("_date").reset_index(drop=True)
        info["date_min"] = df["_date"].min().isoformat()
        info["date_max"] = df["_date"].max().isoformat()
        info["date_range"] = f"{info['date_min']} → {info['date_max']}"

        # Infer frequency
        if len(df) > 1:
            inferred_freq = pd.infer_freq(df["_date"])
            if inferred_freq:
                info["freq"] = inferred_freq
                freq_labels = {
                    "D": "Daily", "W": "Weekly", "M": "Monthly",
                    "Q": "Quarterly", "H": "Hourly", "Y": "Yearly"
                }
                info["freq_label"] = freq_labels.get(inferred_freq, inferred_freq)
            else:
                info["freq"] = "D"
                info["freq_label"] = "Daily (assumed)"
        else:
            info["freq"] = "D"
            info["freq_label"] = "Daily (assumed)"
    except Exception as e:
        sample_vals = df[date_col].head(10).tolist()
        raise ValueError(f"Date column '{date_col}' parsing failed. Samples: {sample_vals}. Error: {e}")

    # --- Value column conversion ---
    try:
        df["_value"] = pd.to_numeric(df[value_col], errors="coerce")
        if df["_value"].isna().all():
            raise ValueError(f"Value column '{value_col}' contains no numeric data.")
        n_nan = df["_value"].isna().sum()
        if n_nan > 0:
            warnings.append(f"{n_nan} missing values in '{value_col}'. Interpolating.")
            if id_col:
                df["_value"] = df.groupby(id_col)["_value"].transform(lambda x: x.interpolate().bfill().ffill())
            else:
                df["_value"] = df["_value"].interpolate().bfill().ffill()
    except Exception as e:
        raise ValueError(f"Value column '{value_col}' conversion failed: {e}")

    # --- Series identification ---
    if id_col:
        series_list = df[id_col].dropna().unique().tolist()
        info["n_series"] = len(series_list)
    else:
        series_list = ["Series_1"]
        info["n_series"] = 1

    info["n_rows"] = len(df)
    # Simple season length heuristic
    freq = info.get("freq", "D")
    if freq == "D":
        info["season_length"] = 7
    elif freq == "W":
        info["season_length"] = 52
    elif freq == "M":
        info["season_length"] = 12
    else:
        info["season_length"] = 7

    # --- Stationarity test (ADF) on first series ---
    try:
        from statsmodels.tsa.stattools import adfuller
        if id_col and len(series_list) > 1:
            first_vals = df[df[id_col] == series_list[0]]["_value"].dropna()
        else:
            first_vals = df["_value"].dropna()
        if len(first_vals) > 5:
            adf = adfuller(first_vals, autolag="AIC")
            p_val = adf[1]
            is_stat = p_val < 0.05
            stationarity[series_list[0]] = {
                "stationary": is_stat,
                "p_value": p_val,
                "test_stat": adf[0]
            }
            if not is_stat:
                warnings.append(f"Series '{series_list[0]}' is non-stationary (p={p_val:.3f}). Auto-differencing will be applied.")
        else:
            stationarity[series_list[0]] = {"stationary": None, "p_value": None, "test_stat": None}
    except ImportError:
        warnings.append("statsmodels not installed – stationarity test skipped.")
        stationarity[series_list[0]] = {"stationary": None, "p_value": None, "test_stat": None}
    except Exception as e:
        warnings.append(f"Stationarity test failed: {e}")

    return {
        "info": info,
        "stationarity": stationarity,
        "warnings": warnings,
        "series_list": series_list,
    }