import pandas as pd
from statsforecast import StatsForecast
from statsforecast.models import Naive
df = pd.DataFrame({
    'unique_id': ['id1']*40,
    'ds': pd.date_range(start='2020-01-01', periods=40),
    'y': range(40)
})
sf_cv = StatsForecast(models=[Naive()], freq='D', n_jobs=1)
cv_df_false = sf_cv.cross_validation(h=7, df=df, n_windows=2, step_size=7, refit=False)
print("Columns:", cv_df_false.columns)
print("Index:", cv_df_false.index.name)
