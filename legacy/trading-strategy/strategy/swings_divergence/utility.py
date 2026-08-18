import datetime
import pandas as pd
import plotly.io as pio

pio.renderers.default = 'browser'
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)

def get_file_name(filename=None):
    directory = "C:\\BackTest_Results\\"
    current_datetime = datetime.datetime.now()
    plot_filename_name = directory + filename + ".html"
    trades_filename_name = directory + filename  + ".xlsx"
    return plot_filename_name, trades_filename_name


def get_all_us_stocks_from_file():
    file_path = '../constants/us_stock_tickers.txt'
    with open(file_path, 'r') as file:
        tickers = [line.strip() for line in file.readlines()]
    return tickers

# Step 1: Data Collection (Reading from local Excel file)
def load_historical_data(file_path):
    data = pd.read_csv(file_path, index_col='Datetime')
    return data

# Step 1: Data Collection (Reading from local Excel file)
def load_historical_daily_data(file_path):
    data = pd.read_csv(file_path, index_col='Date')
    return data

# Step 1: Data Collection (Reading from local Excel file)
def load_historical_daily(file_path):
    data = pd.read_csv(file_path, index_col='Date')
    return data
