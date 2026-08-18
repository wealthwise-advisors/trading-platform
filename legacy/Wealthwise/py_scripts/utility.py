import datetime
import pandas as pd
import plotly.io as pio

pio.renderers.default = 'browser'
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)

def get_file_name(filename=None):
    directory = "/home/ubuntu/back_testing/backtesting_results/"
    current_datetime = datetime.datetime.now()
    plot_filename_name = directory + filename + ".html"
    trades_filename_name = directory + filename  + ".xlsx"
    return plot_filename_name, trades_filename_name

def load_historical_data(file_path):
    data = pd.read_csv(file_path, index_col='Datetime')
    return data
