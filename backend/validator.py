import pandas as pd
import numpy as np
from typing import Tuple, Optional, Dict, Any

def validate_file_size(size_bytes: int, max_mb: int = 10) -> Tuple[bool, Optional[str]]:
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
    warnings = []
    info = {}
    stationarity = {}

    # Column existence
    if date_col not in df.columns:
        raise ValueError(f"Date column '{date_col}' not found. Available: {list(df.columns)}")
    if value_col not in df.columns:
        raise ValueError(f"Value column '{value_col}' not found. Available: {list(df.columns)}")
    if id_col and id_col not in df.columns:
        warnings.append(f"ID column '{id_col}' not found – treating as single series.")
        id_col = None

    # --- Universal date parsing ---
    try:
        # ── Check for raw integer IDs being mapped to dates ──
        if df[date_col].dtype in [np.int64, np.float64]:
            sample = df[date_col].head(1)
            # If values are small (like 0, 1, 100), they aren't timestamps
            if sample.iloc[0] < 1e9: # Less than 1970/1/1 in unix time
                raise ValueError(f"Column '{date_col}' looks like an ID or Category, not a Date. Please choose a temporal column.")

        # First attempt: let pandas guess
        df["_date"] = pd.to_datetime(df[date_col], errors='coerce')
        # ... rest of the smart logic ...
        # [OMITTING PREVIOUS CODE FOR BREVITY - ASKING AI TO KEEP THE SMART LOGIC]
        if df["_date"].isna().all():
            df["_date"] = pd.to_datetime(df[date_col], errors='coerce', dayfirst=True)
        if df["_date"].isna().all():
            df["_date"] = pd.to_datetime(df[date_col], errors='coerce', infer_datetime_format=True)
            
        if df["_date"].dt.tz is not None:
            df["_date"] = df["_date"].dt.tz_localize(None)

        # ── Drop invalid dates and check for unique timelines ──
        if df["_date"].isna().any():
            n_invalid = df["_date"].isna().sum()
            warnings.append(f"{n_invalid} invalid dates found. Dropping them.")
            df = df.dropna(subset=["_date"])
            
        if df.empty or df["_date"].nunique() < 5:
            raise ValueError(f"Insufficient distinct timeline points found in '{date_col}'. Need at least 5 unique dates to forecast.")

        df = df.sort_values("_date").reset_index(drop=True)
        info["date_min"] = df["_date"].min().isoformat()
        info["date_max"] = df["_date"].max().isoformat()
        info["date_range"] = f"{info['date_min']} → {info['date_max']}"

        # --- Intelligent frequency detection ---
        if len(df) > 1:
            inferred_freq = pd.infer_freq(df["_date"])
            if inferred_freq:
                info["freq"] = inferred_freq
                freq_labels = {"D": "Daily", "W": "Weekly", "M": "Monthly", "Q": "Quarterly",
                               "H": "Hourly", "Y": "Yearly", "MS": "Monthly start", "W-MON": "Weekly"}
                info["freq_label"] = freq_labels.get(inferred_freq, inferred_freq)
            else:
                # Fallback: guess from median difference
                diffs = df["_date"].diff().dropna()
                median_days = diffs.dt.days.median()
                if median_days == 1:
                    info["freq"] = "D"
                    info["freq_label"] = "Daily"
                elif 7 <= median_days <= 8:
                    info["freq"] = "W"
                    info["freq_label"] = "Weekly"
                elif 28 <= median_days <= 31:
                    info["freq"] = "M"
                    info["freq_label"] = "Monthly"
                elif 89 <= median_days <= 92:
                    info["freq"] = "Q"
                    info["freq_label"] = "Quarterly"
                else:
                    info["freq"] = "D"
                    info["freq_label"] = "Unknown (treated as daily)"
        else:
            info["freq"] = "D"
            info["freq_label"] = "Daily (single observation)"
    except Exception as e:
        sample_vals = df[date_col].head(10).tolist()
        raise ValueError(f"Date column '{date_col}' parsing failed. Samples: {sample_vals}. Error: {e}")

    # --- Value column conversion ---
    try:
        if df[value_col].dtype == "object":
            # Remove anything that isn't a digit, decimal, or negative sign
            val_clean = df[value_col].astype(str).str.replace(r'[^\d\.-]', '', regex=True)
            df["_value"] = pd.to_numeric(val_clean, errors="coerce")
        else:
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

    # --- Season length inference based on frequency ---
    freq = info.get("freq", "D")
    if freq in ["D", "H", "T", "S"]:
        info["season_length"] = 7   # weekly seasonality
    elif freq in ["W", "W-MON"]:
        info["season_length"] = 52  # yearly
    elif freq in ["M", "MS"]:
        info["season_length"] = 12
    elif freq in ["Q", "Q-DEC"]:
        info["season_length"] = 4
    else:
        info["season_length"] = 7

    # --- Stationarity test with numpy type conversion ---
    try:
        from statsmodels.tsa.stattools import adfuller
        if id_col and len(series_list) > 1:
            first_vals = df[df[id_col] == series_list[0]]["_value"].dropna()
        else:
            first_vals = df["_value"].dropna()
        if len(first_vals) > 5:
            adf = adfuller(first_vals, autolag="AIC")
            p_val = float(adf[1])
            test_stat = float(adf[0])
            is_stat = bool(p_val < 0.05)
            stationarity[series_list[0]] = {
                "stationary": is_stat,
                "p_value": p_val,
                "test_stat": test_stat,
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