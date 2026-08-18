import pandas as pd

from utility import Utility


class DataManager:
    def __init__(self):
        self.orders = {}  # Store all orders by order_id
        self.cash_balance = 100000  # Initial cash balance
        self.total_profit = 0
        utility = Utility()
        self.df_main = utility.load_historical_data(file_path="ES_SUB_SET.csv")


    def resample_ohlc(self, df, interval):
        ohlc_dict = {
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }
        df = df.resample(interval).apply(ohlc_dict)
        df.dropna(inplace=True)
        return df

    def convert_to_t_format(self, value):
        return f"{value}min"

    def download_historical_tick_data(self,  start_time, end_time, bar_type_period):
        bar_type_period = self.convert_to_t_format(bar_type_period)
        df = self.df_main.loc[start_time:end_time]
        df.index = pd.to_datetime(df.index)
        df = self.resample_ohlc(df, bar_type_period)
        return df



