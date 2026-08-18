import datetime
import pandas as pd
import plotly.io as pio

class Utility:

    def __init__(self):
        print("init")


    # Step 1: Data Collection (Reading from local Excel file)
    def load_historical_data(self, file_path):
        data = pd.read_csv(file_path, index_col='Datetime')
        return data

    # Step 1: Data Collection (Reading from local Excel file)
    def load_historical_daily(self, file_path):
        data = pd.read_csv(file_path, index_col='Date')
        return data
