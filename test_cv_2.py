import pandas as pd
from statsforecast import StatsForecast
from statsforecast.models import AutoARIMA, Naive
df = pd.DataFrame({
    'unique_id': ['id1']*40,
    'ds': pd.date_range(start='2020-01-01', periods=40),
    'y': range(40)
})

sf_cv = StatsForecast(models=[AutoARIMA(season_length=7)], freq='D', n_jobs=1)
cv_df_false = sf_cv.cross_validation(h=7, df=df, n_windows=2, step_size=7, refit=False)
print("REFIT=False cutoffs:")
print(cv_df_false[['cutoff', 'ds']].drop_duplicates().head(10))

sf_base = StatsForecast(models=[Naive()], freq='D', n_jobs=1)
cv_df_true = sf_base.cross_validation(h=7, df=df, n_windows=2, step_size=7, refit=True)
print("REFIT=True cutoffs:")
print(cv_df_true[['cutoff', 'ds']].drop_duplicates().head(10))
