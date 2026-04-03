import pandas as pd
from statsforecast import StatsForecast
from statsforecast.models import AutoARIMA, Naive
df = pd.DataFrame({
    'unique_id': ['id1']*40,
    'ds': pd.date_range(start='2020-01-01', periods=40),
    'y': range(40)
})

sf_cv = StatsForecast(models=[AutoARIMA(season_length=7)], freq='D', n_jobs=1)
cv_df = sf_cv.cross_validation(h=7, df=df, n_windows=2, step_size=7, refit=False)

sf_base = StatsForecast(models=[Naive()], freq='D', n_jobs=1)
cv_base = sf_base.cross_validation(h=7, df=df, n_windows=2, step_size=7, refit=True)

try:
    if "unique_id" not in cv_base.columns: cv_base = cv_base.reset_index()
    if "unique_id" not in cv_df.columns: cv_df = cv_df.reset_index()
    
    cols_to_use = cv_base.columns.difference(cv_df.columns).tolist() + ["unique_id", "ds", "cutoff"]
    print("Cols to use:", cols_to_use)
    cv_df = pd.merge(cv_df, cv_base[cols_to_use], on=["unique_id", "ds", "cutoff"], how="left")
    print("Merged columns:", cv_df.columns)
except Exception as e:
    print("MERGE FAILED:", e)
