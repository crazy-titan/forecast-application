import pandas as pd
from statsforecast import StatsForecast
from statsforecast.models import Naive, SeasonalNaive, HistoricAverage
df = pd.DataFrame({
    'unique_id': ['id1']*100,
    'ds': pd.date_range(start='2020-01-01', periods=100),
    'y': range(100)
})
try:
    sf_base = StatsForecast(models=[Naive(), SeasonalNaive(season_length=7), HistoricAverage()], freq='D', n_jobs=1)
    cv_base = sf_base.cross_validation(h=7, df=df, n_windows=2, step_size=7, refit=True)
    print("Success")
    print(cv_base.head())
except Exception as e:
    print(f"Error: {e}")
