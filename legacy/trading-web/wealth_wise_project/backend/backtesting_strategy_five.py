import copy
from datetime import datetime, timedelta, time

import numpy as np
import pandas as pd
import plotly.io as pio
import talib


from get_market_data import MarketDataHelper
from backtesting import Strategy
from backtesting import Backtest
from rsistochfibnumber import RsiStochFibNumber
from typing import List
import pandas_ta as ta
from swing_info import SwingInfo
from sideways_structure import SidewaysStructure
from divergence_info import DivergenceInfo
import argparse
import sys
import pytz
from itertools import chain
from ElliotWaveHelper import ElliotWaveHelper

sys.stdout.reconfigure(encoding='utf-8')
pd.options.mode.chained_assignment = None  # Disable the warning

pio.renderers.default = 'browser'
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)

stop_loss_high = 0
stop_loss_low = 0
enable_trade_buying = False
enable_trade_shorting = False
initial_df = None
updated_divergences = {}
buying_shorting_conditions = {}
divergence_swing_collection = {}
swing_yellow_collection = {}
swing_blue_collection = {}
all_conditions_store = []
last_index = None
start_time = None
end_time = None
lot_size = None
stop_loss_adjust = None
USE_HIGH_LOW_PRICE = False
import psutil
import time


def is_between(start_time, end_time, target_time):
    return start_time <= target_time <= end_time

def apply_body_percentage(row):
    body_percentage = 0
    direction = row.Close - row.Open
    body_size = abs(direction)
    full_range = row.High - row.Low
    if full_range > 0:
        body_percentage = round((body_size / full_range) * 100, 2)
    return body_percentage

def is_friday(given_date_str):
    given_date = datetime.strptime(given_date_str, "%Y-%m-%d")
    return given_date.weekday() == 4  # In Python's datetime module, Monday is 0 and Sunday is 6

def check_for_trading(row):
    target_time = row.name.strftime("%H:%M")
    date = row.name.strftime("%Y-%m-%d")
    if is_between(start_time, end_time, target_time):
        return 1
    else:
        return 0

def get_green_wick_up(row):
    if row.BODY > 0:
        upper_wick_length = row.High - row.Close
        candle_range = row.High - row.Low
        result = (upper_wick_length / candle_range) * 100
        return round(result, 2)
    else:
        return 0

def get_green_wick_down(row):
    if row.BODY > 0:
        lower_wick_length = row.Open - row.Low
        candle_range = row.High - row.Low
        result = (lower_wick_length / candle_range) * 100
        return round(result, 2)
    else:
        return 0

def get_red_wick_up(row):
    if row.BODY < 0:
        upper_wick_length = row.High - row.Open
        candle_range = row.High - row.Low
        result = (upper_wick_length / candle_range) * 100
        return round(result, 2)
    else:
        return 0

def get_red_wick_down(row):
    if row.BODY < 0:
        lower_wick_length = row.Close - row.Low
        candle_range = row.High - row.Low
        result = (lower_wick_length / candle_range) * 100
        return round(result, 2)
    else:
        return 0

def get_body_volume(row):
    if row.RANGE > 0:
        percent = row.Volume / row.RANGE
        if row.BODY > 0:
            result = percent * row.BODY
        elif row.BODY < 0:
            result = percent * abs(row.BODY)
        else:
            result = 0
        return f"{result:.2f}"
    return "0.00"

def get_red_wick_up_volume(row):
    if row.RANGE > 0 and row.BODY < 0 and row.RED_WICK_UP > 0:
        return round( row.Volume * row.RED_WICK_UP/100, 2)
    else:
        return 0

def get_green_wick_up_volume(row):
    if row.RANGE > 0 and row.BODY > 0 and row.GREEN_WICK_UP > 0:
        return round(row.Volume * row.GREEN_WICK_UP/100 , 2)
    else:
        return 0

def get_red_wick_down_volume(row):
    if row.RANGE > 0 and row.BODY < 0 and row.RED_WICK_DOWN > 0:
        return round(row.Volume * row.RED_WICK_DOWN/100, 2)
    else:
        return 0

def get_green_wick_down_volume(row):
    if row.RANGE > 0 and row.BODY > 0 and row.GREEN_WICK_DOWN > 0:
        return round(row.Volume * row.GREEN_WICK_DOWN/100, 2)
    else:
        return 0

def get_HH_LL(row):
    if row.previous_close == row.Open and  row.previous_open > row.Open:
        return '#H'
    if row.previous_close == row.Open and  row.previous_open < row.Open:
        return '#L'
    if row.previous_close < row.Open and  row.previous_open > row.Open:
        return 'HH'
    if row.previous_close > row.Open and  row.previous_open < row.Open:
        return 'LL'
    if row.previous_close < row.Open and row.previous_open < row.Open:
        return 'HL'
    if row.previous_close > row.Open and row.previous_open > row.Open:
        return 'LH'

def relative_volume_std_dev(volume_series, length=30, num_dev=2.0):
    """Computes Relative Volume Standard Deviation (RVSD)."""
    mean_volume = talib.SMA(volume_series, timeperiod=length)
    std_dev_volume = talib.STDDEV(volume_series, timeperiod=length, nbdev=1)
    rvsd = (volume_series - mean_volume) / (std_dev_volume + 1e-9)  # Avoid division by zero
    return rvsd

def freedom_of_movement(close_series, length=30, num_dev=2.0):
    """Computes Freedom of Movement (FoM)."""
    prev_close = close_series.shift(1)
    std_dev_price = talib.STDDEV(close_series, timeperiod=length, nbdev=1)
    fom = (close_series - prev_close) / (std_dev_price + 1e-9)  # Avoid division by zero
    return fom

def kama(price, fast_length=2, slow_length=30, er_length=10):
    # Handle edge case: insufficient data
    if len(price) < er_length:
        return pd.Series(np.nan, index=price.index)

    # Efficiency Ratio (ER)
    change = np.abs(price.diff(er_length))
    volatility = price.diff().abs().rolling(er_length).sum()
    efficiency_ratio = change / volatility
    efficiency_ratio = efficiency_ratio.fillna(0)  # Avoid NaN in early values

    # Smoothing Constants (SC)
    fast_sc = 2 / (fast_length + 1)
    slow_sc = 2 / (slow_length + 1)
    smoothing_constant = (efficiency_ratio * (fast_sc - slow_sc) + slow_sc) ** 2

    # KAMA Calculation
    kama_values = [price.iloc[0]]  # Start with the first price
    for i in range(1, len(price)):
        kama_values.append(
            kama_values[-1] + smoothing_constant.iloc[i] * (price.iloc[i] - kama_values[-1])
        )

    return pd.Series(kama_values, index=price.index)

def calculate_vwap(df, high_col='High', low_col='Low', close_col='Close', volume_col='Volume'):
    try:
        for col in [high_col, low_col, close_col, volume_col]:
            if col not in df.columns or df[col].isnull().any():
                raise ValueError(f"Invalid or missing column: {col}")

        df['Typical_Price'] = (df[high_col] + df[low_col] + df[close_col]) / 3
        df['Cumulative_TP_Volume'] = (df['Typical_Price'] * df[volume_col]).cumsum()
        df['Cumulative_Volume'] = df[volume_col].cumsum()
        df['VWAP'] = df['Cumulative_TP_Volume'] / df['Cumulative_Volume']
        df.drop(columns=['Typical_Price', 'Cumulative_TP_Volume', 'Cumulative_Volume'], inplace=True)

        return df['VWAP']

    except Exception as e:
        return df

def apply_rsi_stoch_doji(df):

    num_dev = 2.0
    length = 30

    df.index = pd.to_datetime(df.index)
    df["RSI"] = talib.RSI(df['Close'], 2)
    df["ADX"] = talib.ADX(df['High'], df['Low'], df['Close'], 14)
    df["STOCH"], df["STOCH_D"] = talib.STOCHRSI(df["Close"], timeperiod=14, fastk_period=14, fastd_period=3)
    df["EMA5"] = talib.EMA(df['Close'], 5)
    df["EMA12"] = talib.EMA(df['Close'], 12)

    df["EMA9"] = talib.EMA(df['Close'], 9)
    df["EMA21"] = talib.EMA(df['Close'], 21)


    df["EMA200"] = talib.EMA(df['Close'], 200)
    df["KAMA"] = kama(df['Close'])
    df['MEDIAN'] = (df['High'] + df['Low']) / 2
    df["RSI_13"] = talib.RSI(df['Close'], 13)
    df["RSI_13"] =  df["RSI_13"].round(2)
    df["VWAP"] = calculate_vwap(df)
    df['AVG_MEDIAN'] = df['MEDIAN'].rolling(window=5).mean()
    df['PREVIOUS_MEDIAN'] = df['MEDIAN'].shift(1)
    df['PREVIOUS_AVG_MEDIAN'] = df['AVG_MEDIAN'].shift(1)
    #df['PREVIOUS_PREVIOUS_MEDIAN'] = df['MEDIAN'].shift(2)
    #df['PREVIOUS_PREVIOUS_AVG_MEDIAN'] = df['AVG_MEDIAN'].shift(2)
    # Rounding to 2 decimal places
    df["STOCH"] = df["STOCH"].round(2)
    df["STOCH_D"] = df["STOCH_D"].round(2)
    df["RSI"] = df["RSI"].round(2)
    df["DATE"] = df.index.strftime("%m/%d %I:%M %p")
    df["TRADE"] = df.apply(check_for_trading, axis=1)
    df["PRICE"] = df['Close'] - df['Open']
    df['previous_close'] = df['Close'].shift(1)
    df['previous_open'] = df['Open'].shift(1)
    df['previous_volume'] = df['Volume'].shift(1)
    df["Fib_Number"] = 0
    df["BODY"] = df['Close'] - df['Open']
    df["RANGE"] = df['High'] - df['Low']
    #df["GREEN_WICK_UP"] = df.apply(get_green_wick_up, axis=1)
    #df["GREEN_WICK_DOWN"] = df.apply(get_green_wick_down, axis=1)
    #df["RED_WICK_UP"] = df.apply(get_red_wick_up, axis=1)
    #df["RED_WICK_DOWN"] = df.apply(get_red_wick_down, axis=1)
    df["BODY_VOLUME"] = df.apply(get_body_volume, axis=1)
    df['BODY_VOLUME'] = pd.to_numeric(df['BODY_VOLUME'], errors='coerce')
    #df["GREEN_WICK_UP_VOLUME"] = df.apply(get_green_wick_up_volume, axis=1)
    #df["RED_WICK_UP_VOLUME"] = df.apply(get_red_wick_up_volume, axis=1)
    #df["GREEN_WICK_DOWN_VOLUME"] = df.apply(get_green_wick_down_volume, axis=1)
    #df["RED_WICK_DOWN_VOLUME"] = df.apply(get_red_wick_down_volume, axis=1)
    #df["CLOSE_OPEN_OPEN"] = df.apply(get_HH_LL, axis=1)
    df["BODY_PERCENT"] = df.apply(apply_body_percentage, axis=1)
    #df["CHART_TYPE"] = 0
    df['PREVIOUS_BODY'] = df['BODY'].shift(1)
    #df['PREVIOUS_PREVIOUS_BODY'] = df['BODY'].shift(2)
    #df['PREVIOUS_GREEN_WICK_UP'] = df['GREEN_WICK_UP'].shift(1)
    #df['PREVIOUS_GREEN_WICK_DOWN'] = df['GREEN_WICK_DOWN'].shift(1)
    ##df['PREVIOUS_RED_WICK_UP'] = df['RED_WICK_UP'].shift(1)
    #df['PREVIOUS_RED_WICK_DOWN'] = df['RED_WICK_DOWN'].shift(1)
    #df['PREVIOUS_BODY_PERCENT'] = df['BODY_PERCENT'].shift(1)
    #df['PREVIOUS_BODY_VOLUME'] = df['BODY_VOLUME'].shift(1)
    df['PREVIOUS_RSI'] = df['RSI'].shift(1)
    df['PREVIOUS_STOCH'] = df['STOCH'].shift(1)
    df['PREVIOUS_STOCH_D'] = df['STOCH_D'].shift(1)
    df['PREVIOUS_RANGE'] = df['RANGE'].shift(1)
    df['PREVIOUS_HIGH'] = df['High'].shift(1)
    df['PREVIOUS_LOW'] = df['Low'].shift(1)
    df['PREVIOUS_RSI_13'] = df['RSI_13'].shift(1)
    #df['GREEN_CLOSE'] = 0
    #df['RED_CLOSE'] = 0
    #df['Wave_Pattern'] = None
    df['previous_index'] = df.index.to_series().shift(1)

    df["EMA9"] = talib.EMA(df['Close'], 9)
    df["EMA21"] = talib.EMA(df['Close'], 21)

    # Calculate 20-period average volume
    df['avg_volume'] = df['Volume'].rolling(window=20).mean()

    # Identify unusual volume
    df['unusual'] = df['Volume'] > 2 * df['avg_volume']

    df['volatility'] = df['RANGE'].rolling(window=14).mean()

    # Calculate the rolling 10-candle average close price
    df["Avg_Close"] = df["Close"].rolling(window=10).mean()

    # Calculate the rolling standard deviation of close prices over 10 candles
    df["Std_Close"] = df["Close"].rolling(window=10).std()

    # Calculate the standard deviation levels
    df["One_SD_Top"] = df["Avg_Close"] + (df["Std_Close"] * 1)
    df["One_SD_Bottom"] = df["Avg_Close"] - (df["Std_Close"] * 1)

    df["Two_SD_Top"] = df["Avg_Close"] + (df["Std_Close"] * 2)
    df["Two_SD_Bottom"] = df["Avg_Close"] - (df["Std_Close"] * 2)

    df["Three_SD_Top"] = df["Avg_Close"] + (df["Std_Close"] * 3)
    df["Three_SD_Bottom"] = df["Avg_Close"] - (df["Std_Close"] * 3)

    # Calculate 20-period average volume
    df['avg_volume'] = df['Volume'].rolling(window=20).mean()

    # Identify unusual volume
    df['unusual'] = df['Volume'] > 2 * df['avg_volume']

    # Compute RVSD with ThinkOrSwim settings (length=30, num_dev=2.0)
    df["RVSD"] = relative_volume_std_dev(df["Volume"], length=30, num_dev=num_dev)
    df["Above_RVSD"] = df["RVSD"] > num_dev  # Extreme high volume
    df["Below_RVSD"] = df["RVSD"] < -num_dev  # Extreme low volume

    # Compute FoM with ThinkOrSwim settings (length=30, num_dev=2.0)
    df["FoM"] = freedom_of_movement(df["Close"], length=30, num_dev=num_dev)
    df["Above_FoM"] = df["FoM"] > num_dev  # Strong upward movement
    df["Below_FoM"] = df["FoM"] < -num_dev  # Strong downward movement
    # Assuming df is your DataFrame and it includes a 'Close' column
    close = df['Close']

    # Parameters
    length = 14

    # Calculate custom RSI (CHOPPY)
    delta = close.diff()  # Calculate the difference between consecutive close prices

    # Use np.maximum and np.minimum for efficiency
    gain = np.maximum(delta, 0)  # Positive changes only
    loss = -np.minimum(delta, 0)  # Negative changes as positive values

    # Compute rolling mean for gains and losses
    avg_gain = pd.Series(gain).rolling(window=length, min_periods=1).mean()
    avg_loss = pd.Series(loss).rolling(window=length, min_periods=1).mean()

    # Avoid division by zero and calculate the RSI
    rs = np.where(avg_loss == 0, 0, avg_gain / avg_loss)  # Handle division by zero
    rsi = np.where(avg_loss == 0, 100, 100 - (100 / (1 + rs)))  # Final RSI computation

    # Add the CHOPPY column to the DataFrame
    df['CHOPPY'] = rsi

    # Optional: Replace NaN values in the CHOPPY column
    df['CHOPPY'] = df['CHOPPY'].fillna(50)  # Set initial values to neutral if necessary

    df = df[df.High != df.Low]

    return df

def get_item(rsi_stoch_fib_numbers, value):
    try:
        return [item for item in rsi_stoch_fib_numbers if item.fib == value][0]
    except:
        return None

# Function to remove items based on a specific value
def remove_item(rsi_stoch_fib_numbers, value):
    # Iterate over the collection in reverse to avoid index issues when removing items
    for i in range(len(rsi_stoch_fib_numbers) - 1, -1, -1):
        if rsi_stoch_fib_numbers[i].fib == value:
            del rsi_stoch_fib_numbers[i]

def generate_fibonacci_sequence(df, price_index, fromTop, fromBottom):
    start_pos = df.index.get_loc(price_index) + 1
    rsi_stoch_fib_numbers = []
    fib_sequence = [0]  # Start with 2 and 1
    rsi_stoch_fib_numbers.append(RsiStochFibNumber(df['Open'].iloc[0], df['Close'].iloc[0], df['High'].iloc[0], df['Low'].iloc[0], df['RSI'].iloc[0], df['STOCH'].iloc[0], df['STOCH_D'].iloc[0],0, df['DATE'].iloc[0], 0, 0, 0))
    fib_one_number = True
    next_value = 0
    less_check = False
    greater_check = False
    for i in range(start_pos, len(df)):
        # For 1 first check if High is taken
        previous_high = df['High'].iloc[i - 1]
        previous_close = df['Close'].iloc[i - 1]
        current_close = df['Close'].iloc[i]
        current_low = df['Low'].iloc[i]
        current_open = df['Open'].iloc[i]
        current_high = df['High'].iloc[i]
        previous_low = df['Close'].iloc[i - 1]
        body = df['Close'].iloc[i] - df['Open'].iloc[i]

        if fib_one_number:

            if fromTop:
                if current_close > previous_close and next_value == 1:
                    fromTop = False
                if current_close <= previous_close and fromTop:  # and current_high != previous_high and current_low != previous_low:
                    next_value = 1
                    less_check = True
                    rsi_stoch_fib_number_local = get_item(rsi_stoch_fib_numbers, next_value)
                    if rsi_stoch_fib_number_local and not greater_check:
                        if current_close <= rsi_stoch_fib_number_local.close:
                            remove_item(rsi_stoch_fib_numbers, next_value)
                            df['Fib_Number'].iloc[i - 1] = 0
                            rsi_stoch_fib_numbers.append(RsiStochFibNumber(df['Open'].iloc[i], df['Close'].iloc[i], df['High'].iloc[i], df['Low'].iloc[i], df['RSI'].iloc[i], df['STOCH'].iloc[i],  df['STOCH_D'].iloc[i] , next_value, df['DATE'].iloc[i], 0, 0, 0))
                    else:
                        #If the current close price is lower than the previous close price, add the last Fibonacci number to the current sequence
                        greater_check = False
                        next_value = fib_sequence[-1] + 1
                        rsi_stoch_fib_numbers.append(RsiStochFibNumber(df['Open'].iloc[i], df['Close'].iloc[i], df['High'].iloc[i], df['Low'].iloc[i], df['RSI'].iloc[i], df['STOCH'].iloc[i],  df['STOCH_D'].iloc[i] , next_value, df['DATE'].iloc[i], 0, 0, 0))
                        fib_sequence.append(next_value)

            if fromBottom:
                if current_close < previous_close and next_value == 1:
                    fromBottom = False
                if current_close >= previous_close and fromBottom: # and current_high != previous_high and current_low != previous_low:
                    next_value = 1
                    greater_check = True
                    # If the current close price is higher than the previous close price, add the last two Fibonacci numbers
                    rsi_stoch_fib_number_local = get_item(rsi_stoch_fib_numbers, next_value)
                    if rsi_stoch_fib_number_local and not less_check:
                        if current_close >= rsi_stoch_fib_number_local.close:
                            remove_item(rsi_stoch_fib_numbers, next_value)
                            df['Fib_Number'].iloc[i - 1] = 0
                            rsi_stoch_fib_numbers.append(RsiStochFibNumber(df['Open'].iloc[i], df['Close'].iloc[i], df['High'].iloc[i], df['Low'].iloc[i], df['RSI'].iloc[i], df['STOCH'].iloc[i],  df['STOCH_D'].iloc[i] , next_value, df['DATE'].iloc[i], 0, 0, 0))
                    else:
                        less_check = False
                        next_value = fib_sequence[-1] + 1
                        rsi_stoch_fib_numbers.append(RsiStochFibNumber(df['Open'].iloc[i], df['Close'].iloc[i], df['High'].iloc[i], df['Low'].iloc[i], df['RSI'].iloc[i], df['STOCH'].iloc[i],  df['STOCH_D'].iloc[i] , next_value, df['DATE'].iloc[i], 0, 0, 0))
                        fib_sequence.append(next_value)

            if not fromTop and not fromBottom:
                if current_close >= previous_close and body > 0 : # and current_high != previous_high and current_low != previous_low:
                    greater_check = True
                    # If the current close price is higher than the previous close price, add the last two Fibonacci numbers
                    rsi_stoch_fib_number_local = get_item(rsi_stoch_fib_numbers, next_value)
                    if rsi_stoch_fib_number_local and not less_check:
                        if current_close >= rsi_stoch_fib_number_local.close:
                            remove_item(rsi_stoch_fib_numbers, next_value)
                            df['Fib_Number'].iloc[i - 1] = 0
                            rsi_stoch_fib_numbers.append(RsiStochFibNumber(df['Open'].iloc[i], df['Close'].iloc[i], df['High'].iloc[i], df['Low'].iloc[i], df['RSI'].iloc[i], df['STOCH'].iloc[i],  df['STOCH_D'].iloc[i] , next_value, df['DATE'].iloc[i], 0, 0, 0))
                    else:
                        less_check = False
                        next_value = fib_sequence[-1] + 1
                        rsi_stoch_fib_numbers.append(RsiStochFibNumber(df['Open'].iloc[i], df['Close'].iloc[i], df['High'].iloc[i], df['Low'].iloc[i], df['RSI'].iloc[i], df['STOCH'].iloc[i],  df['STOCH_D'].iloc[i] , next_value, df['DATE'].iloc[i], 0, 0, 0))
                        fib_sequence.append(next_value)


                elif current_close <= previous_close and body <  0:  # and current_high != previous_high and current_low != previous_low:
                    less_check = True
                    rsi_stoch_fib_number_local = get_item(rsi_stoch_fib_numbers, next_value)
                    if rsi_stoch_fib_number_local and not greater_check:
                        if current_close <= rsi_stoch_fib_number_local.close:
                            remove_item(rsi_stoch_fib_numbers, next_value)
                            df['Fib_Number'].iloc[i - 1] = 0
                            rsi_stoch_fib_numbers.append(RsiStochFibNumber(df['Open'].iloc[i], df['Close'].iloc[i], df['High'].iloc[i], df['Low'].iloc[i], df['RSI'].iloc[i], df['STOCH'].iloc[i],  df['STOCH_D'].iloc[i] , next_value, df['DATE'].iloc[i], 0, 0, 0))
                    else:
                        #If the current close price is lower than the previous close price, add the last Fibonacci number to the current sequence
                        greater_check = False
                        next_value = fib_sequence[-1] + 1
                        rsi_stoch_fib_numbers.append(RsiStochFibNumber(df['Open'].iloc[i], df['Close'].iloc[i], df['High'].iloc[i], df['Low'].iloc[i], df['RSI'].iloc[i], df['STOCH'].iloc[i],  df['STOCH_D'].iloc[i] , next_value, df['DATE'].iloc[i], 0, 0, 0))
                        fib_sequence.append(next_value)
            df['Fib_Number'].iloc[i] = next_value

    return rsi_stoch_fib_numbers

class RSIStochExtremeStrategy(Strategy):

    def init(self):
        super().init()

        self.buy_order = False
        self.short_order = False
        self.in_trade = False
        self.close_only_once = False
        self.high_price_during_trading = stop_loss_high
        self.low_price_during_trading = stop_loss_low
        self.track_all_candles_during_buy = []
        self.track_all_candles_during_short = []
        self.save_downward_swing_current = None
        self.save_upward_swing_current = None
        self.current_trade_candle = None
        self.track_all_candles = []
        self.copy_data = False
        self.lowest_candle = None
        self.highest_candle = None
        self.add_candles_buy_side = None
        self.add_candles_short_side = None
        self.save_downward_swing_previous = None
        self.save_upward_swing_previous = None
        self.short_triggered_candle_two = None
        self.buy_triggered_candle_two = None
        self.track_first_set_candles = []
        self.in_trade_candle = None
        self.manual_buy_short_trigger_candle = None
        self.hold_buy_short_candles_temp = []

        self.buy_divergence_candle = None
        self.short_divergence_candle = None
        self.buy_trending_candle = None
        self.short_trending_candle = None
        self.buy_stop_limit_candle = None
        self.short_stop_limit_candle = None

        self.bulk_buy_stop_limit_candle = None
        self.bulk_short_stop_limit_candle = None
        self.bulk_buy_order_candle = None
        self.bulk_short_order_candle = None
        self.bulk_lot_size = None
        self.bulk_stop_loss_adjust = None
        self.current_candle = None
        self.enable_trade_buying = enable_trade_buying
        self.enable_trade_shorting = enable_trade_shorting
        self.is_choppy = False
        self.candles_above_94 = []
        self.candles_below_5 = []
        self.cover_stop_limit = None
        self.sell_stop_limit = None
        self.zig_zag_swing_collection = {}
        self.initial_df = initial_df
        self.swing_collection = {}
        self.divergences_by_index = {}
        self.buying_shorting_conditions = {}
        self.cancelled_buy_divergence = False
        self.cancelled_short_divergence = False
        self.last_index = last_index
        self.latest_upward_swing_candle_from_10_leg = None
        self.latest_downward_swing_candle_from_10_leg = None

        self.first_high_rsi_candle_during_buy = None
        self.first_low_rsi_candle_during_short = None

        self.second_high_rsi_candle_during_buy = None
        self.second_low_rsi_candle_during_short = None

        self.in_memory_short_divergence_candle = None
        self.in_memory_buy_divergence_candle = None
        self.in_memory_divergence_info = None

        self.real_buy_divergence_candle = None
        self.real_short_divergence_candle = None
        self.previous_lowest_rsi_candle = None
        self.previous_highest_rsi_candle = None
        self.trend_is_down_check_for_rsi_13_above_55_for_buy = False
        self.first_red_candle_condition_statisfied = None
        self.candle_close_above_short_divergence_buy = None
        self.candle_close_below_buy_divergence_short = None

        self.lot_size = lot_size
        self.stop_loss_adjust = stop_loss_adjust

    def create_rsi_stoch_fib(self):
        data =  RsiStochFibNumber(self.data.Open[-1], self.data.Close[-1], self.data.High[-1], self.data.Low[-1], self.data.RSI[-1], self.data.STOCH[-1], self.data.STOCH_D[-1], self.data.Fib_Number[-1], self.data.DATE[-1], self.data.BODY[-1], 0, 0)
        data.volume = self.data.Volume[-1]
        data.previous_open = self.data.previous_open[-1]
        data.previous_close = self.data.previous_close[-1]
        data.previous_volume = self.data.previous_volume[-1]
        #data.green_wick_up_percent = self.data.GREEN_WICK_UP[-1]
        #data.green_wick_down_percent = self.data.GREEN_WICK_DOWN[-1]
        #data.red_wick_up_percent = self.data.RED_WICK_UP[-1]
        #data.red_wick_down_percent = self.data.RED_WICK_DOWN[-1]
        data.body_percent = self.data.BODY_PERCENT[-1]
        #data.previous_green_wick_up_percent = self.data.PREVIOUS_GREEN_WICK_UP[-1]
        #data.previous_green_wick_down_percent = self.data.PREVIOUS_GREEN_WICK_DOWN[-1]
        #data.previous_red_wick_up_percent = self.data.PREVIOUS_RED_WICK_UP[-1]
        #data.previous_red_wick_down_percent = self.data.PREVIOUS_RED_WICK_DOWN[-1]
        #data.previous_body_percent = self.data.PREVIOUS_BODY_PERCENT[-1]
        data.body_volume = float(self.data.BODY_VOLUME[-1])
        #data.previous_body_volume = float(self.data.PREVIOUS_BODY_VOLUME[-1])
        data.previous_body = self.data.PREVIOUS_BODY[-1]
        data.previous_rsi = self.data.PREVIOUS_RSI[-1]
        data.previous_stoch_k = self.data.PREVIOUS_STOCH[-1]
        data.previous_stoch_d = self.data.PREVIOUS_STOCH_D[-1]
        data.previous_rsi_13 = self.data.PREVIOUS_RSI_13[-1]
        data.range = self.data.RANGE[-1]
        data.previous_range = self.data.PREVIOUS_RANGE[-1]
        data.previous_high = self.data.PREVIOUS_HIGH[-1]
        data.previous_low = self.data.PREVIOUS_LOW[-1]
        data.median = self.data.MEDIAN[-1]
        data.avg_median = self.data.AVG_MEDIAN[-1]
        data.previous_median = self.data.PREVIOUS_MEDIAN[-1]
        data.previous_avg_median = self.data.PREVIOUS_AVG_MEDIAN[-1]
        data.ema_5 = self.data.EMA5[-1]
        data.kama = self.data.KAMA[-1]
        data.ema_12 = self.data.EMA12[-1]
        data.ema_200 = self.data.EMA200[-1]
        data.vwap = self.data.VWAP[-1]
        data.rsi_13 = self.data.RSI_13[-1]
        data.index = self.data.index[-1]
        data.previous_index = self.data.previous_index[-1]
        data.previous_low = self.data.PREVIOUS_LOW[-1]
        #data.previous_previous_median = self.data.PREVIOUS_PREVIOUS_MEDIAN[-1]
        #data.previous_previous_avg_median = self.data.PREVIOUS_PREVIOUS_AVG_MEDIAN[-1]
        #data.previous_previous_body = self.data.PREVIOUS_PREVIOUS_BODY[-1]
        data.datetime = self.data.index[-1]
        data.previous_candle_datetime = self.data.previous_index[-1]



        return data

    def create_swings_using_zig_zag_indicator(self):
        swing_info_list = []
        zigzag_df = self.initial_df.loc[:self.current_candle.index]
        zigzag_result = ta.zigzag(
            high=zigzag_df['High'],
            low=zigzag_df['Low'],
            close=zigzag_df['Close'],
            legs=3,
            deviation=0.001, #0.07
            retrace=True,
            last_extreme=False,
            offset=0
        )
        zigzag_df = zigzag_df.join(zigzag_result,rsuffix='_ZIG')
        #zigzag_df.to_csv('zig_zag.csv', index=True)
        start_index = zigzag_df.index[0]   # Initialize starting point

        for idx, row in zigzag_df.iterrows():
            zigzag_value = row['ZIGZAGs_0.001%_3']

            if pd.notna(zigzag_value):  # Process only rows with zigzag values

                if zigzag_value == 1:  # Upward Swing
                    # Record the previous downward swing (if any)
                    swing_info_list.append(SwingInfo(
                        start_index=start_index,
                        end_index=idx,
                        swing_high_price=zigzag_df.loc[idx, "High"],
                        swing_low_price=zigzag_df.loc[start_index, "Low"],
                        swing_high_close=zigzag_df.loc[idx, "Close"],
                        swing_low_close=zigzag_df.loc[start_index, "Close"],
                        swing_high_rsi=zigzag_df.loc[idx, "RSI"],
                        swing_low_rsi=zigzag_df.loc[start_index, "RSI"],
                        swing_type=zigzag_value  # Upward Swing
                    ))
                    start_index = idx

                elif zigzag_value == -1:  # Downward Swing
                    # Record the previous upward swing (if any)
                    swing_info_list.append(SwingInfo(
                        start_index=start_index,
                        end_index=idx,
                        swing_high_price=zigzag_df.loc[start_index, "High"],
                        swing_low_price=zigzag_df.loc[idx, "Low"],
                        swing_high_close=zigzag_df.loc[start_index, "Close"],
                        swing_low_close=zigzag_df.loc[idx, "Close"],
                        swing_high_rsi=zigzag_df.loc[start_index, "RSI"],
                        swing_low_rsi=zigzag_df.loc[idx, "RSI"],
                        swing_type=zigzag_value  # Upward Swing
                    ))
                    # Start a new downward swing
                    start_index = idx
        return swing_info_list

    def create_swings_using_zig_zag_indicator_for_10_legs(self, use_timestamp=False):
        swing_info_list = []
        try:
            if use_timestamp:  # Boolean flag
                cutoff_time = self.current_candle.index - pd.Timedelta(minutes=5)
                zigzag_df = self.initial_df.loc[:cutoff_time]  # Get all rows before 5 minutes
            else:
                current_idx = self.initial_df.index.get_loc(self.current_candle.index)
                start_idx = max(0, current_idx - 5)
                zigzag_df = self.initial_df.iloc[:start_idx]  # Get all rows before 5 candles
            #zigzag_df = self.initial_df.loc[:self.current_candle.index]
            zigzag_result = ta.zigzag(
                high=zigzag_df['High'],
                low=zigzag_df['Low'],
                close=zigzag_df['Close'],
                legs=10,
                deviation=0.01, #0.07
                retrace=True,
                last_extreme=False,
                offset=0
            )
            zigzag_df = zigzag_df.join(zigzag_result,rsuffix='_ZIG')
            #zigzag_df.to_csv('zig_zag.csv', index=True)
            start_index = zigzag_df.index[0]   # Initialize starting point

            for idx, row in zigzag_df.iterrows():
                zigzag_value = row['ZIGZAGs_0.01%_10']

                if pd.notna(zigzag_value):  # Process only rows with zigzag values

                    if zigzag_value == 1:  # Upward Swing
                        # Record the previous downward swing (if any)
                        swing_info_list.append(SwingInfo(
                            start_index=start_index,
                            end_index=idx,
                            swing_high_price=zigzag_df.loc[idx, "High"],
                            swing_low_price=zigzag_df.loc[start_index, "Low"],
                            swing_high_close=zigzag_df.loc[idx, "Close"],
                            swing_low_close=zigzag_df.loc[start_index, "Close"],
                            swing_high_rsi=zigzag_df.loc[idx, "RSI"],
                            swing_low_rsi=zigzag_df.loc[start_index, "RSI"],
                            swing_type=zigzag_value  # Upward Swing
                        ))
                        start_index = idx

                    elif zigzag_value == -1:  # Downward Swing
                        # Record the previous upward swing (if any)
                        swing_info_list.append(SwingInfo(
                            start_index=start_index,
                            end_index=idx,
                            swing_high_price=zigzag_df.loc[start_index, "High"],
                            swing_low_price=zigzag_df.loc[idx, "Low"],
                            swing_high_close=zigzag_df.loc[start_index, "Close"],
                            swing_low_close=zigzag_df.loc[idx, "Close"],
                            swing_high_rsi=zigzag_df.loc[start_index, "RSI"],
                            swing_low_rsi=zigzag_df.loc[idx, "RSI"],
                            swing_type=zigzag_value  # Upward Swing
                        ))
                        # Start a new downward swing
                        start_index = idx
        except:
            pass
        return swing_info_list

    def get_last_upward_swing_low_high_candle(self):
        last_upward_swing = None
        upward_swing_low_candle = None
        upward_swing_high_candle = None
        self.zig_zag_swing_collection = self.create_swings_using_zig_zag_indicator()
        if len(self.zig_zag_swing_collection) > 0:
            upward_swings = [s for s in self.zig_zag_swing_collection if s.swing_type == 1]
            if len(upward_swings) > 0:
                last_upward_swing = upward_swings[-1]  # Assume swings are stored in chronological order
                if last_upward_swing.swing_high_close == last_upward_swing.swing_low_close:
                    # If there is a previous swing, return it
                    if len(upward_swings) > 1:
                        last_upward_swing = upward_swings[-2]  # Previous upward swing
                    else:
                        last_upward_swing = None
        if last_upward_swing:
            upward_swing_low_candle = self.get_candle_by_index(last_upward_swing.start_index)
            upward_swing_high_candle = self.get_candle_by_index(last_upward_swing.end_index)
            # if upward_swing_low_candle and upward_swing_low_candle.open == upward_swing_low_candle.previous_close and upward_swing_low_candle.low == upward_swing_low_candle.previous_low:
            #     upward_swing_low_candle = self.get_candle_by_index(upward_swing_low_candle.previous_index)
        return upward_swing_low_candle, upward_swing_high_candle

    def get_last_downward_swing_high_low_candle(self):
        last_downward_swing = None
        downward_swing_high_candle = None
        downward_swing_low_candle = None
        self.zig_zag_swing_collection = self.create_swings_using_zig_zag_indicator()
        if len(self.zig_zag_swing_collection) > 0:
            downward_swings = [s for s in self.zig_zag_swing_collection if s.swing_type == -1]
            if len(downward_swings) > 0:
                last_downward_swing = downward_swings[-1]  # Assume swings are stored in chronological order
                if last_downward_swing.swing_high_close == last_downward_swing.swing_low_close:
                    # If there is a previous swing, return it
                    if len(downward_swings) > 1:
                        last_downward_swing = downward_swings[-2]  # Previous downward swing
                    else:
                        last_downward_swing = None
        if last_downward_swing:
            downward_swing_high_candle = self.get_candle_by_index(last_downward_swing.start_index)
            downward_swing_low_candle = self.get_candle_by_index(last_downward_swing.end_index)
            # if downward_swing_high_candle and downward_swing_high_candle.open == downward_swing_high_candle.previous_close and downward_swing_high_candle.high == downward_swing_high_candle.previous_high:
            #     downward_swing_high_candle = self.get_candle_by_index(downward_swing_high_candle.previous_index)

        return downward_swing_high_candle, downward_swing_low_candle

    def check_price_in_downtrend(self, n=2):
        # Separate upward and downward swings
        self.zig_zag_swing_collection = self.create_swings_using_zig_zag_indicator()
        upward_swings = [s for s in self.zig_zag_swing_collection if s.swing_type == 1]
        downward_swings = [s for s in self.zig_zag_swing_collection if s.swing_type == -1]


        # Determine the number of swings to compare
        num_upward = min(len(upward_swings), n)
        num_downward = min(len(downward_swings), n)

        if num_upward < n or num_downward < n:
            return False

        # Get the relevant swings for comparison
        last_upward_highs = [s.swing_high_price for s in upward_swings[-num_upward:]]
        last_downward_lows = [s.swing_low_price for s in downward_swings[-num_downward:]]

        # Check if high prices are decreasing for upward swings
        upward_highs_down = all(x > y for x, y in zip(last_upward_highs, last_upward_highs[1:]))
        # Check if low prices are decreasing for downward swings
        downward_lows_down = all(x > y for x, y in zip(last_downward_lows, last_downward_lows[1:]))

        if downward_lows_down:
            return True
        else:
            return False

    def check_price_in_uptrend(self, n=2):
        # Separate upward and upward swings
        swing_collection = self.create_swings_using_zig_zag_indicator()
        upward_swings = [s for s in swing_collection if s.swing_type == 1]
        downward_swings = [s for s in swing_collection if s.swing_type == -1]

        # Determine the number of swings to compare
        num_upward = min(len(upward_swings), n)
        num_downward = min(len(downward_swings), n)

        if num_upward < n or num_downward < n:
            return False

        # Get the relevant swings for comparison
        last_upward_highs = [s.swing_high_price for s in upward_swings[-num_upward:]]
        last_downward_lows = [s.swing_low_price for s in downward_swings[-num_downward:]]

        # Check if high prices are increasing for upward swings
        upward_highs_up = all(x < y for x, y in zip(last_upward_highs, last_upward_highs[1:]))
        # Check if low prices are increasing for downward swings
        downward_lows_up = all(x < y for x, y in zip(last_downward_lows, last_downward_lows[1:]))

        if upward_highs_up:
            return True
        else:
            return False

    def check_price_in_downtrend_for_10_legs(self, n=2):
        # Separate upward and downward swings
        swing_collection = self.create_swings_using_zig_zag_indicator_for_10_legs()
        downward_swings = [s for s in swing_collection if s.swing_type == -1]

        # Determine the number of swings to compare
        num_downward = min(len(downward_swings), n)

        if num_downward < n:
            return False

        if len(downward_swings) > 1:
            downward_swing_one = downward_swings[-1]
            downward_swing_two = downward_swings[-2]
            time_difference = downward_swing_one.end_index - downward_swing_two.start_index
            if time_difference > timedelta(minutes=60):
                swing_collection = self.create_swings_using_zig_zag_indicator_for_10_legs(True)
                downward_swings = [s for s in swing_collection if s.swing_type == -1]


        # Determine the number of swings to compare
        num_downward = min(len(downward_swings), n)

        if  num_downward < n:
            return False

        if len(downward_swings) > 0:
            downward_swing = downward_swings[-1]
            downward_swing_previous = downward_swings[-2]
            if self.current_candle.close < downward_swing.swing_low_price and downward_swing.swing_low_price < downward_swing_previous.swing_low_price:
                downward_swings.append(SwingInfo(
                    start_index=downward_swing.end_index,
                    end_index=self.current_candle.index,
                    swing_high_price=downward_swing.swing_low_price,
                    swing_low_price=self.current_candle.low,
                    swing_high_close=downward_swing.swing_low_close,
                    swing_low_close=self.current_candle.close,
                    swing_high_rsi=downward_swing.swing_low_rsi,
                    swing_low_rsi=self.current_candle.rsi,
                    swing_type=-1  # Upward Swing
                ))


        # Get the relevant swings for comparison
        last_downward_lows = [s.swing_low_price for s in downward_swings[-num_downward:]]

        # Check if high prices are decreasing for upward swings
        # Check if low prices are decreasing for downward swings
        downward_lows_down = all(x > y for x, y in zip(last_downward_lows, last_downward_lows[1:]))

        if downward_lows_down:
            return True
        else:
            return False

    def check_price_in_uptrend_for_10_legs(self, n=2):
        # Separate upward and upward swings
        swing_collection = self.create_swings_using_zig_zag_indicator_for_10_legs()
        upward_swings = [s for s in swing_collection if s.swing_type == 1]

        # Determine the number of swings to compare
        num_upward = min(len(upward_swings), n)

        if num_upward < n :
            return False


        if len(upward_swings) > 1:
            upward_swing_one = upward_swings[-1]
            upward_swing_two = upward_swings[-2]
            time_difference = upward_swing_one.end_index - upward_swing_two.start_index
            if time_difference > timedelta(minutes=60):
                swing_collection = self.create_swings_using_zig_zag_indicator_for_10_legs(True)
                upward_swings = [s for s in swing_collection if s.swing_type == 1]
                downward_swings = [s for s in swing_collection if s.swing_type == -1]

        if len(upward_swings) > 0:
            upward_swing = upward_swings[-1]
            upward_swing_previous = upward_swings[-2]
            if self.current_candle.close > upward_swing.swing_high_price and upward_swing.swing_high_price > upward_swing_previous.swing_high_price:
                upward_swings.append(SwingInfo(
                    start_index=upward_swing.end_index,
                    end_index=self.current_candle.index,
                    swing_high_price=self.current_candle.high,
                    swing_low_price=upward_swing.swing_high_price,
                    swing_high_close=self.current_candle.close,
                    swing_low_close=upward_swing.swing_high_close,
                    swing_high_rsi=self.current_candle.rsi,
                    swing_low_rsi=upward_swing.swing_high_rsi,
                    swing_type=1  # Upward Swing
                ))


        # Determine the number of swings to compare
        num_upward = min(len(upward_swings), n)

        if num_upward < n:
            return False

        # Get the relevant swings for comparison
        last_upward_highs = [s.swing_high_price for s in upward_swings[-num_upward:]]

        # Check if high prices are increasing for upward swings
        upward_highs_up = all(x < y for x, y in zip(last_upward_highs, last_upward_highs[1:]))
        # Check if low prices are increasing for downward swings

        if upward_highs_up:
            return True
        else:
            return False

    def get_last_downward_swing_high_low_candle_from_10_leg(self):
        last_downward_swing = None
        downward_swing_high_candle = None
        downward_swing_low_candle = None
        swing_collection = self.create_swings_using_zig_zag_indicator_for_10_legs()
        if len(swing_collection) > 0:
            downward_swings = [s for s in swing_collection if s.swing_type == -1]
            if len(downward_swings) > 0:
                last_downward_swing = downward_swings[-1]  # Assume swings are stored in chronological order
                if last_downward_swing.swing_high_close == last_downward_swing.swing_low_close:
                    # If there is a previous swing, return it
                    if len(downward_swings) > 1:
                        last_downward_swing = downward_swings[-2]  # Previous downward swing
                    else:
                        last_downward_swing = None
        if last_downward_swing:
            downward_swing_high_candle = self.get_candle_by_index(last_downward_swing.start_index)
            downward_swing_low_candle = self.get_candle_by_index(last_downward_swing.end_index)

        return downward_swing_high_candle, downward_swing_low_candle

    def get_last_upward_swing_low_high_candle_from_10_leg(self):
        last_upward_swing = None
        upward_swing_low_candle = None
        upward_swing_high_candle = None
        swing_collection = self.create_swings_using_zig_zag_indicator_for_10_legs()
        if len(swing_collection) > 0:
            upward_swings = [s for s in swing_collection if s.swing_type == 1]
            if len(upward_swings) > 0:
                last_upward_swing = upward_swings[-1]  # Assume swings are stored in chronological order
                if last_upward_swing.swing_high_close == last_upward_swing.swing_low_close:
                    # If there is a previous swing, return it
                    if len(upward_swings) > 1:
                        last_upward_swing = upward_swings[-2]  # Previous upward swing
                    else:
                        last_upward_swing = None
        if last_upward_swing:
            upward_swing_low_candle = self.get_candle_by_index(last_upward_swing.start_index)
            upward_swing_high_candle = self.get_candle_by_index(last_upward_swing.end_index)
            # if upward_swing_low_candle and upward_swing_low_candle.open == upward_swing_low_candle.previous_close and upward_swing_low_candle.low == upward_swing_low_candle.previous_low:
            #     upward_swing_low_candle = self.get_candle_by_index(upward_swing_low_candle.previous_index)
        return upward_swing_low_candle, upward_swing_high_candle

    def get_latest_upward_swing_candle_from_10_leg(self):
        """
        Retrieves the latest upward swing candle (swing_type == 1) from the swings
        created using the zig-zag indicator for 10 legs.

        Returns:
            The latest upward swing candle, or None if no upward swing is found.
        """
        swing_collection = self.create_swings_using_zig_zag_indicator_for_10_legs()

        # Find the latest upward swing (swing_type == 1)
        for swing in reversed(swing_collection):  # Iterate from the most recent swing
            if swing.swing_type == 1:  # Check if the swing is upward
                return swing

        return None  # No upward swing found

    def get_latest_downward_swing_candle_from_10_leg(self):
        """
        Retrieves the latest downward swing candle (swing_type == -1) from the swings
        created using the zig-zag indicator for 10 legs.

        Returns:
            The latest downward swing candle, or None if no downward swing is found.
        """
        swing_collection = self.create_swings_using_zig_zag_indicator_for_10_legs()

        # Find the latest downward swing (swing_type == -1)
        for swing in reversed(swing_collection):  # Iterate from the most recent swing
            if swing.swing_type == -1:  # Check if the swing is downward
                return swing

        return None  # No downward swing found

    def mark_flat_swings(self, swings, threshold_pct):
        start_index = None

        for i in range(len(swings) - 1):
            # Calculate percentage difference
            high_diff_pct = abs(swings[i].swing_high_price - swings[i + 1].swing_high_price) / swings[i].swing_high_price * 100
            low_diff_pct = abs(swings[i].swing_low_price - swings[i + 1].swing_low_price) / swings[i].swing_low_price * 100

            # Check if both high and low differences are within the percentage threshold
            if high_diff_pct <= threshold_pct and low_diff_pct <= threshold_pct:
                if start_index is None:
                    start_index = i
            else:
                if start_index is not None:
                    # Mark the swings in the flat range
                    for j in range(start_index, i + 1):
                        swings[j].flat = True
                    start_index = None

        # Mark the last flat range if it extends to the end of the list
        if start_index is not None:
            for j in range(start_index, len(swings)):
                swings[j].flat = True

        return swings

    def calculate_slope(self, start_date, end_date, start_price, end_price, time_unit="minutes"):
        # Ensure datetime format if input is a string
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")

        # Calculate the time difference in seconds
        time_diff_seconds = (end_date - start_date).total_seconds()

        # Convert time difference to the desired unit
        if time_unit == "seconds":
            time_diff = time_diff_seconds
        elif time_unit == "minutes":
            time_diff = time_diff_seconds / 60
        elif time_unit == "hours":
            time_diff = time_diff_seconds / 3600
        elif time_unit == "days":
            time_diff = time_diff_seconds / 86400
        else:
            raise ValueError("Invalid time_unit. Choose from 'seconds', 'minutes', 'hours', 'days'.")

        # Calculate price difference
        price_diff = end_price - start_price

        # Calculate slope
        slope = price_diff / time_diff if time_diff != 0 else float('inf')

        return abs(slope)

    def check_to_take_profit(self):
        # if self.check_rsi_trending():
        #     return False

        if (self.current_candle.close - self.in_trade_candle.close) > 10 and self.current_candle.rsi < self.current_candle.previous_rsi:
            swing_collection = self.create_swings_using_zig_zag_indicator()
            last_swing = swing_collection[-1]
            if last_swing.swing_type == -1:
                slope = self.calculate_slope(last_swing.end_index, self.current_candle.previous_index, last_swing.swing_low_price, self.current_candle.previous_high)
                if slope > 3.00:
                    return True
        elif (self.in_trade_candle.close - self.current_candle.close ) > 10 and self.current_candle.rsi > self.current_candle.previous_rsi:
            swing_collection = self.create_swings_using_zig_zag_indicator()
            last_swing = swing_collection[-1]
            if last_swing.swing_type == 1:
                slope = self.calculate_slope(last_swing.end_index, self.current_candle.previous_index, last_swing.swing_high_price, self.current_candle.previous_low)
                if slope > 3.00:
                    return True

        else:
            return False

    def is_last_swing_flat(self):
        latest_upward_swing = None
        latest_downward_swing = None
        threshold = 0.02
        swing_collection = self.create_swings_using_zig_zag_indicator()
        swing_collection = self.mark_flat_swings(swing_collection, threshold)
        upward_swings = [s for s in swing_collection if s.swing_type == 1]
        if len(upward_swings) > 0:
            latest_upward_swing = upward_swings[-1]
        downward_swings = [s for s in swing_collection if s.swing_type == -1]
        if len(downward_swings) > 0:
            latest_downward_swing = downward_swings[-1]
        return latest_upward_swing and latest_upward_swing.flat or latest_downward_swing and latest_downward_swing.flat

    def get_lowest_downward_swing(self):
        swing_collection = self.create_swings_using_zig_zag_indicator()
        downward_swings = [swing for swing in swing_collection if swing.swing_type == -1]
        if not downward_swings:
            return None  # No downward swings available

        # Sort by lowest price first, then by latest end_index (descending order)
        return min(downward_swings, key=lambda x: (x.swing_low_price, -x.end_index.timestamp()))

    def get_highest_upward_swing(self):
        swing_collection = self.L()
        upward_swings = [swing for swing in swing_collection if swing.swing_type == 1]
        if not upward_swings:
            return None  # No upward swings available

        # Sort by highest price first, then by latest end_index (descending order)
        return max(upward_swings, key=lambda x: (x.swing_high_price, x.end_index.timestamp()))

    def get_candle_by_index(self, index):
        if not self.track_all_candles:
            return None

        # Filter candles to only include those within the specified date range
        filtered_candles = [candle for candle in self.track_all_candles if candle.index  == index]

        if not filtered_candles:
            return None

        # Find the candle with the highest RSI among the filtered candles
        candle_by_index = filtered_candles[0]


        return candle_by_index

    def find_upward_swings_from_low(self, track_all_candles_during_buy, candle_count, start_from_red=True, filter_by_date=None, start_from_bottom=True, skip_doji_candles=True, forward=True):
        swings = []
        last_green_candle = None
        lowest_red_candle = None
        highest_price = float('-inf')
        red_candle_count = 0
        doji_candle_count = 0
        previous_green_candle = None

        # Filter candles based on the given date

        if track_all_candles_during_buy:

            if filter_by_date:
                if forward:
                    track_all_candles_during_buy = [candle for candle in track_all_candles_during_buy if candle.datetime >= filter_by_date]
                else:
                    track_all_candles_during_buy = [candle for candle in track_all_candles_during_buy if candle.datetime <= filter_by_date]

            if track_all_candles_during_buy:
                lowest_price_index = 0
                if start_from_bottom:
                    lowest_price_index = min(range(len(track_all_candles_during_buy)), key=lambda i: track_all_candles_during_buy[i].close)

                # if start_from_red and lowest_price_index >= 1:
                #     lowest_price_index = lowest_price_index - 1


                for i in range(lowest_price_index, len(track_all_candles_during_buy)):
                    candle = track_all_candles_during_buy[i]

                    if not hasattr(candle, 'close'):
                        print(f"Candle without 'high': {candle}")

                    if i == lowest_price_index:
                        if (candle.close - candle.open) < 0:
                            lowest_red_candle = candle
                            red_candle_count = red_candle_count + 1
                            continue

                    if candle.close - candle.open == 0:
                        if lowest_red_candle is None:
                            lowest_red_candle = candle
                            red_candle_count = red_candle_count + 1
                            doji_candle_count = doji_candle_count + 1
                        elif doji_candle_count == 0:
                            red_candle_count = red_candle_count + 1
                            doji_candle_count = doji_candle_count + 1


                    if (candle.close - candle.open) > 0:  # Green candle
                        previous_green_candle = candle
                        if last_green_candle is None:
                            last_green_candle = candle
                            continue

                        if lowest_red_candle and last_green_candle:
                            try:
                                is_green_candle = track_all_candles_during_buy[i+1]
                                if (is_green_candle.close - is_green_candle.open) > 0 and (is_green_candle.high >= previous_green_candle.high or is_green_candle.close >= previous_green_candle.close):
                                    continue

                                if skip_doji_candles:
                                    if (is_green_candle.close - is_green_candle.open) == 0 and (is_green_candle.high >= previous_green_candle.high or is_green_candle.close >= previous_green_candle.close or is_green_candle.close >= previous_green_candle.close or is_green_candle.close >= previous_green_candle.open):
                                        is_green_candle = track_all_candles_during_buy[i+2]
                                        if ((is_green_candle.close - is_green_candle.open) > 0 or (is_green_candle.close - is_green_candle.open) == 0) and (is_green_candle.high >= previous_green_candle.high):
                                            continue


                                if (is_green_candle.close - is_green_candle.open) < 0:
                                    is_green_candle = track_all_candles_during_buy[i+2]
                                    if (is_green_candle.close - is_green_candle.open) > 0 and (is_green_candle.high >= previous_green_candle.high or is_green_candle.close >= previous_green_candle.close):
                                        continue
                                    if (is_green_candle.close - is_green_candle.open) < 0:
                                        is_green_candle = track_all_candles_during_buy[i+3]
                                        if (is_green_candle.close - is_green_candle.open) > 0 and (is_green_candle.high >= previous_green_candle.high or is_green_candle.close >= previous_green_candle.close):
                                            continue

                            except:
                                pass

                        if candle.close > last_green_candle.close:
                            if lowest_red_candle:
                                if candle.close > highest_price:
                                    lowest_red_candle.is_new_high = True
                                    lowest_red_candle.new_high_candle = candle
                                    highest_price = candle.close
                                if red_candle_count >= candle_count:
                                    lowest_red_candle.cumulative_close_diff = abs(lowest_red_candle.new_high_candle.close - lowest_red_candle.close)
                                    swings.append(lowest_red_candle)
                            last_green_candle = candle
                            lowest_red_candle = None
                            red_candle_count = 0

                    elif (candle.close - candle.open) < 0:  # Red candle
                        red_candle_count = red_candle_count + 1
                        if last_green_candle is not None:
                            if lowest_red_candle is None or (candle.close <= lowest_red_candle.close):
                                lowest_red_candle = candle

        return swings

    def find_downward_swings_from_high(self, track_all_candles_during_short, candle_count, start_from_green=True, filter_by_date=None, start_from_high=True, skip_doji_candles=True, forward=True):
        swings = []
        last_red_candle = None
        highest_green_candle = None
        lowest_price = float('inf')
        green_candle_count = 0
        doji_candle_count = 0
        previous_red_candle = None

        # Filter candles based on the given date

        if track_all_candles_during_short:
            if filter_by_date:
                if forward:
                    track_all_candles_during_short = [candle for candle in track_all_candles_during_short if candle.datetime >= filter_by_date]
                else:
                    track_all_candles_during_short = [candle for candle in track_all_candles_during_short if candle.datetime <= filter_by_date]

            if track_all_candles_during_short:

                highest_price_index = 0
                if start_from_high:
                    highest_price_index = max(range(len(track_all_candles_during_short)), key=lambda i: track_all_candles_during_short[i].close)

                for i in range(highest_price_index, len(track_all_candles_during_short)):
                    candle = track_all_candles_during_short[i]

                    if i == highest_price_index and start_from_green:
                        if (candle.close - candle.open) > 0:
                            highest_green_candle = candle
                            green_candle_count = green_candle_count + 1
                            continue

                    if candle.close - candle.open == 0:
                        if highest_green_candle is None:
                            highest_green_candle = candle
                            green_candle_count = green_candle_count + 1
                            doji_candle_count = doji_candle_count + 1
                        elif doji_candle_count == 0:
                            green_candle_count = green_candle_count + 1
                            doji_candle_count = doji_candle_count + 1


                    if (candle.close - candle.open) < 0 :  # Red candle
                        previous_red_candle = candle
                        if last_red_candle is None:
                            last_red_candle = candle
                            continue

                        if highest_green_candle and last_red_candle:
                            try:
                                is_red_candle = track_all_candles_during_short[i+1]
                                if (is_red_candle.close - is_red_candle.open) < 0 and (is_red_candle.close <= previous_red_candle.close or is_red_candle.low <= previous_red_candle.low):
                                    continue

                                if skip_doji_candles:
                                    if (is_red_candle.close - is_red_candle.open) == 0 and (is_red_candle.close <= previous_red_candle.close or is_red_candle.low <= previous_red_candle.low):
                                        is_red_candle = track_all_candles_during_short[i+2]
                                        if ((is_red_candle.close - is_red_candle.open) < 0 or (is_red_candle.close - is_red_candle.open) == 0) and (is_red_candle.close <= previous_red_candle.close or is_red_candle.low <= previous_red_candle.low):
                                            continue


                                if (is_red_candle.close - is_red_candle.open) > 0:
                                    is_red_candle = track_all_candles_during_short[i+2]
                                    if (is_red_candle.close - is_red_candle.open) < 0 and (is_red_candle.close <= previous_red_candle.close or is_red_candle.low <= previous_red_candle.low):
                                        continue
                                    if (is_red_candle.close - is_red_candle.open) > 0:
                                        is_red_candle = track_all_candles_during_short[i+3]
                                        if (is_red_candle.close - is_red_candle.open) < 0 and (is_red_candle.close <= previous_red_candle.close or is_red_candle.low <= previous_red_candle.low):
                                            continue


                            except:
                                pass

                        if candle.close < last_red_candle.close:
                            if highest_green_candle:
                                if candle.close < lowest_price:
                                    highest_green_candle.is_new_low = True
                                    highest_green_candle.new_low_candle = candle
                                    lowest_price = candle.close
                                if green_candle_count >= candle_count:
                                    highest_green_candle.cumulative_close_diff = abs(highest_green_candle.new_low_candle.close - highest_green_candle.close)
                                    swings.append(highest_green_candle)
                            last_red_candle = candle
                            highest_green_candle = None
                            green_candle_count = 0

                    elif (candle.close - candle.open) > 0:  # Green candle
                        green_candle_count = green_candle_count + 1
                        if last_red_candle is not None:
                            if highest_green_candle is None or (candle.close >= highest_green_candle.close):
                                highest_green_candle = candle
        return swings

    def get_stop_loss(self, is_buy):
        stop_loss = None
        if is_buy:
            stop_loss = self.low_price_during_trading
        else:
            stop_loss = self.high_price_during_trading

        return stop_loss

    def get_previous_closest_red_highest_rsi_candle_only_pre_condition(self, start_datetime, end_datetime, rsi_threshold, low_threshold, close_threshold, k_threshold, d_threshold):
        if not self.track_all_candles:
            return None

        # Filter candles that meet conditions
        filtered_candles = [
            candle for candle in self.track_all_candles
            if start_datetime <= candle.datetime <= end_datetime
               and candle.rsi > rsi_threshold
               and (candle.stoch_k < k_threshold or candle.stoch_d < d_threshold)
               and candle.low < low_threshold
               and candle.close < close_threshold
               and candle.body < 0  # Red candle condition
        ]

        if not filtered_candles:
            return None

        # Find the lowest close price among the filtered candles
        lowest_close = min(candle.close for candle in filtered_candles)

        # Get all candles that have the lowest close price
        lowest_close_candles = [candle for candle in filtered_candles if candle.close == lowest_close]

        # Find the highest RSI among lowest close candles
        highest_rsi = max(candle.rsi for candle in lowest_close_candles)

        # Get all candles that have the highest RSI among lowest close candles
        highest_rsi_candles = [candle for candle in lowest_close_candles if candle.rsi == highest_rsi]

        # Select the closest one to end_datetime
        closest_candle = min(highest_rsi_candles, key=lambda candle: abs(end_datetime - candle.datetime))

        return closest_candle

    def get_previous_closest_red_highest_rsi_candle_only_pre_condition_rsi_13(self, start_datetime, end_datetime, rsi_threshold, low_threshold, close_threshold, k_threshold, d_threshold):
        if not self.track_all_candles:
            return None

        # Filter candles that meet conditions
        filtered_candles = [
            candle for candle in self.track_all_candles
            if start_datetime <= candle.datetime <= end_datetime
               and candle.rsi_13 > rsi_threshold
               and (candle.stoch_k < k_threshold or candle.stoch_d < d_threshold)
               and candle.low < low_threshold
               and candle.close < close_threshold
               and candle.body < 0  # Red candle condition
        ]

        if not filtered_candles:
            return None

        # Find the lowest close price among the filtered candles
        lowest_close = min(candle.close for candle in filtered_candles)

        # Get all candles that have the lowest close price
        lowest_close_candles = [candle for candle in filtered_candles if candle.close == lowest_close]

        # Find the highest RSI among lowest close candles
        highest_rsi = max(candle.rsi_13 for candle in lowest_close_candles)

        # Get all candles that have the highest RSI among lowest close candles
        highest_rsi_candles = [candle for candle in lowest_close_candles if candle.rsi_13 == highest_rsi]

        # Select the closest one to end_datetime
        closest_candle = min(highest_rsi_candles, key=lambda candle: abs(end_datetime - candle.datetime))

        return closest_candle

    def get_previous_closest_green_lowest_rsi_candle_pre_condition_only(self, start_datetime, end_datetime, rsi_threshold, high_threshold, close_threshold, k_threshold, d_threshold):
        if not self.track_all_candles:
            return None

        # Filter candles that meet conditions
        filtered_candles = [
            candle for candle in self.track_all_candles
            if start_datetime <= candle.datetime <= end_datetime
               and candle.rsi < rsi_threshold
               and (candle.stoch_k > k_threshold or candle.stoch_d > d_threshold)
               and candle.high > high_threshold
               and candle.close > close_threshold
               and candle.body > 0  # Green candle condition
        ]

        if not filtered_candles:
            return None

        # Find the highest close price among the filtered candles
        highest_close = max(candle.close for candle in filtered_candles)

        # Get all candles that have the highest close price
        highest_close_candles = [candle for candle in filtered_candles if candle.close == highest_close]

        # Find the lowest RSI among highest close candles
        lowest_rsi = min(candle.rsi for candle in highest_close_candles)

        # Get all candles that have the lowest RSI among highest close candles
        lowest_rsi_candles = [candle for candle in highest_close_candles if candle.rsi == lowest_rsi]

        # Select the closest one to end_datetime
        closest_candle = min(lowest_rsi_candles, key=lambda candle: abs(end_datetime - candle.datetime))

        return closest_candle

    def get_previous_closest_green_lowest_rsi_candle_pre_condition_only_rsi_13(self, start_datetime, end_datetime, rsi_threshold, high_threshold, close_threshold, k_threshold, d_threshold):
        if not self.track_all_candles:
            return None

        # Filter candles that meet conditions
        filtered_candles = [
            candle for candle in self.track_all_candles
            if start_datetime <= candle.datetime <= end_datetime
               and candle.rsi_13 < rsi_threshold
               and (candle.stoch_k > k_threshold or candle.stoch_d > d_threshold)
               and candle.high > high_threshold
               and candle.close > close_threshold
               and candle.body > 0  # Green candle condition
        ]

        if not filtered_candles:
            return None

        # Find the highest close price among the filtered candles
        highest_close = max(candle.close for candle in filtered_candles)

        # Get all candles that have the highest close price
        highest_close_candles = [candle for candle in filtered_candles if candle.close == highest_close]

        # Find the lowest RSI among highest close candles
        lowest_rsi = min(candle.rsi_13 for candle in highest_close_candles)

        # Get all candles that have the lowest RSI among highest close candles
        lowest_rsi_candles = [candle for candle in highest_close_candles if candle.rsi_13 == lowest_rsi]

        # Select the closest one to end_datetime
        closest_candle = min(lowest_rsi_candles, key=lambda candle: abs(end_datetime - candle.datetime))

        return closest_candle

    def get_previous_closest_red_highest_rsi_candle(self, start_datetime, end_datetime, rsi_threshold, low_threshold, close_threshold, k_threshold, d_threshold):
        if not self.track_all_candles:
            return None

        # Filter candles to only include those between end_datetime and start_datetime and with RSI below the threshold
        filtered_candles = [candle for candle in self.track_all_candles if start_datetime <= candle.datetime <= end_datetime and candle.rsi > rsi_threshold and (candle.stoch_k < k_threshold or candle.stoch_d < d_threshold) and candle.low > low_threshold and candle.close > close_threshold and candle.body < 0]

        if not filtered_candles:
            return None

        # Initialize the candle with the highest RSI and closest time
        highest_rsi_candle = filtered_candles[0]
        smallest_time_diff = abs(start_datetime - filtered_candles[0].datetime)

        for candle in filtered_candles[1:]:
            time_diff = abs(start_datetime - candle.datetime)

            # Select the candle if it has a higher RSI or same RSI but a closer time
            if candle.rsi > highest_rsi_candle.rsi or (candle.rsi == highest_rsi_candle.rsi and time_diff < smallest_time_diff):
                highest_rsi_candle = candle
                smallest_time_diff = time_diff

        return highest_rsi_candle

    def get_previous_closest_red_lowest_rsi_candle(self, start_datetime, end_datetime, rsi_threshold, low_threshold, close_threshold):
        if not self.track_all_candles:
            return None

        # Filter candles by time and RSI threshold
        filtered_candles = [
            candle for candle in self.track_all_candles
            #if start_datetime <= candle.datetime <= end_datetime and candle.rsi < rsi_threshold and candle.low > low_threshold and candle.close > close_threshold
            if start_datetime <= candle.datetime <= end_datetime and candle.rsi < rsi_threshold and candle.close > close_threshold
        ]

        if not filtered_candles:
            return None

        # Initialize with the first candle in the filtered list
        closest_lowest_rsi_candle = filtered_candles[0]
        smallest_time_diff = abs(start_datetime - filtered_candles[0].datetime)

        for candle in filtered_candles[1:]:
            time_diff = abs(start_datetime - candle.datetime)

            # Update if a candle has lower RSI or same RSI but closer to start_datetime
            if (candle.rsi < closest_lowest_rsi_candle.rsi or
                    (candle.rsi == closest_lowest_rsi_candle.rsi and time_diff < smallest_time_diff)):
                closest_lowest_rsi_candle = candle
                smallest_time_diff = time_diff

        return closest_lowest_rsi_candle

    def get_previous_closest_green_highest_rsi_candle(self, start_datetime, end_datetime, rsi_threshold, high_threshold, close_threshold):
        if not self.track_all_candles:
            return None

        # Filter candles to only include those between end_datetime and start_datetime and with RSI below the threshold
        filtered_candles = [candle for candle in self.track_all_candles if start_datetime <= candle.datetime <= end_datetime and candle.rsi > rsi_threshold  and candle.close < close_threshold and candle.body > 0]
        #filtered_candles = [candle for candle in self.track_all_candles if start_datetime <= candle.datetime <= end_datetime and candle.rsi > rsi_threshold and candle.high < high_threshold and candle.close < close_threshold and candle.body > 0]


        if not filtered_candles:
            return None

        # Initialize the candle with the highest RSI and closest time
        highest_rsi_candle = filtered_candles[0]
        smallest_time_diff = abs(start_datetime - filtered_candles[0].datetime)

        for candle in filtered_candles[1:]:
            time_diff = abs(start_datetime - candle.datetime)

            # Select the candle if it has a higher RSI or same RSI but a closer time
            if candle.rsi > highest_rsi_candle.rsi or (candle.rsi == highest_rsi_candle.rsi and time_diff < smallest_time_diff):
                highest_rsi_candle = candle
                smallest_time_diff = time_diff

        return highest_rsi_candle

    def get_previous_closest_green_lowest_rsi_candle(self, start_datetime, end_datetime, rsi_threshold, high_threshold, close_threshold, k_threshold, d_threshold):
        if not self.track_all_candles:
            return None

        # Filter candles by time and RSI threshold
        filtered_candles = [
            candle for candle in self.track_all_candles
            if start_datetime <= candle.datetime <= end_datetime and candle.rsi < rsi_threshold and (candle.stoch_k > k_threshold or candle.stoch_d > d_threshold) and candle.high < high_threshold and candle.close < close_threshold and candle.body > 0
        ]

        if not filtered_candles:
            return None

        # Initialize with the first candle in the filtered list
        closest_lowest_rsi_candle = filtered_candles[0]
        smallest_time_diff = abs(start_datetime - filtered_candles[0].datetime)

        for candle in filtered_candles[1:]:
            time_diff = abs(start_datetime - candle.datetime)

            # Update if a candle has lower RSI or same RSI but closer to start_datetime
            if (candle.rsi < closest_lowest_rsi_candle.rsi or
                    (candle.rsi == closest_lowest_rsi_candle.rsi and time_diff < smallest_time_diff)):
                closest_lowest_rsi_candle = candle
                smallest_time_diff = time_diff

        return closest_lowest_rsi_candle

    def get_highest_rsi_candle_between_dates(self, start_datetime, end_datetime):
        if not self.track_all_candles:
            return None

        # Filter candles to only include those within the specified date range
        filtered_candles = [candle for candle in self.track_all_candles if start_datetime <= candle.datetime <= end_datetime]

        if not filtered_candles:
            return None

        # Find the candle with the highest RSI among the filtered candles
        highest_rsi_candle = filtered_candles[0]

        for candle in filtered_candles[1:]:
            if candle.rsi > highest_rsi_candle.rsi:
                highest_rsi_candle = candle

        return highest_rsi_candle

    def get_highest_rsi_candle_above_94_between_dates(self, start_datetime, end_datetime):
        if not self.track_all_candles:
            return None

        # Filter candles to only include those within the specified date range
        filtered_candles = [candle for candle in self.track_all_candles if start_datetime <= candle.datetime <= end_datetime]

        if not filtered_candles:
            return None

        # Filter further to only include candles with RSI above 94
        filtered_candles_above_94 = [candle for candle in filtered_candles if candle.rsi > 94]

        if not filtered_candles_above_94:
            return None

        # Find the candle with the highest RSI among the filtered candles above 94
        highest_rsi_candle = max(filtered_candles_above_94, key=lambda candle: candle.rsi)

        return highest_rsi_candle

    def get_lowest_rsi_candle_between_dates(self, start_datetime, end_datetime):
        if not self.track_all_candles:
            return None

        # Filter candles to only include those within the specified date range
        filtered_candles = [candle for candle in self.track_all_candles if start_datetime <= candle.datetime <= end_datetime]

        if not filtered_candles:
            return None

        # Find the candle with the lowest RSI among the filtered candles
        lowest_rsi_candle = filtered_candles[0]

        for candle in filtered_candles[1:]:
            if candle.rsi < lowest_rsi_candle.rsi:
                lowest_rsi_candle = candle

        return lowest_rsi_candle

    def get_lowest_rsi_candle_below_5_between_dates(self, start_datetime, end_datetime):
        if not self.track_all_candles:
            return None

        # Filter candles to only include those within the specified date range
        filtered_candles = [candle for candle in self.track_all_candles if start_datetime <= candle.datetime <= end_datetime]

        if not filtered_candles:
            return None

        # Filter further to only include candles with RSI below 5
        filtered_candles_below_5 = [candle for candle in filtered_candles if candle.rsi < 5]

        if not filtered_candles_below_5:
            return None

        # Find the candle with the lowest RSI among the filtered candles below 5
        lowest_rsi_candle = min(filtered_candles_below_5, key=lambda candle: candle.rsi)

        return lowest_rsi_candle

    def get_previous_closest_red_lowest_rsi_candle_rsi_13(self, start_datetime, end_datetime, rsi_threshold, low_threshold, close_threshold):
        if not self.track_all_candles:
            return None

        # Filter candles by time and RSI threshold
        filtered_candles = [
            candle for candle in self.track_all_candles
            if start_datetime <= candle.datetime <= end_datetime and candle.rsi_13 < rsi_threshold and candle.low > low_threshold and candle.close > close_threshold
        ]

        if not filtered_candles:
            return None

        # Initialize with the first candle in the filtered list
        closest_lowest_rsi_candle = filtered_candles[0]
        smallest_time_diff = abs(start_datetime - filtered_candles[0].datetime)

        for candle in filtered_candles[1:]:
            time_diff = abs(start_datetime - candle.datetime)

            # Update if a candle has lower RSI or same RSI but closer to start_datetime
            if (candle.rsi_13 < closest_lowest_rsi_candle.rsi_13 or
                    (candle.rsi_13 == closest_lowest_rsi_candle.rsi_13 and time_diff < smallest_time_diff)):
                closest_lowest_rsi_candle = candle
                smallest_time_diff = time_diff

        return closest_lowest_rsi_candle

    def get_previous_closest_red_highest_rsi_candle_rsi_13(self, start_datetime, end_datetime, rsi_threshold, low_threshold, close_threshold, k_threshold, d_threshold):
        if not self.track_all_candles:
            return None

        # Filter candles to only include those between end_datetime and start_datetime and with RSI below the threshold
        filtered_candles = [candle for candle in self.track_all_candles if start_datetime <= candle.datetime <= end_datetime and candle.rsi_13 > rsi_threshold and (candle.stoch_k < k_threshold or candle.stoch_d < d_threshold) and candle.low > low_threshold and candle.close > close_threshold and candle.body < 0]

        if not filtered_candles:
            return None

        # Initialize the candle with the highest RSI and closest time
        highest_rsi_candle = filtered_candles[0]
        smallest_time_diff = abs(start_datetime - filtered_candles[0].datetime)

        for candle in filtered_candles[1:]:
            time_diff = abs(start_datetime - candle.datetime)

            # Select the candle if it has a higher RSI or same RSI but a closer time
            if candle.rsi_13 > highest_rsi_candle.rsi_13 or (candle.rsi_13 == highest_rsi_candle.rsi_13 and time_diff < smallest_time_diff):
                highest_rsi_candle = candle
                smallest_time_diff = time_diff

        return highest_rsi_candle

    def get_previous_closest_green_highest_rsi_candle_rsi_13(self, start_datetime, end_datetime, rsi_threshold, high_threshold, close_threshold):
        if not self.track_all_candles:
            return None

        # Filter candles to only include those between end_datetime and start_datetime and with RSI below the threshold
        filtered_candles = [candle for candle in self.track_all_candles if start_datetime <= candle.datetime <= end_datetime and candle.rsi_13 > rsi_threshold and candle.high < high_threshold and candle.close < close_threshold and candle.body > 0]

        if not filtered_candles:
            return None

        # Initialize the candle with the highest RSI and closest time
        highest_rsi_candle = filtered_candles[0]
        smallest_time_diff = abs(start_datetime - filtered_candles[0].datetime)

        for candle in filtered_candles[1:]:
            time_diff = abs(start_datetime - candle.datetime)

            # Select the candle if it has a higher RSI or same RSI but a closer time
            if candle.rsi_13 > highest_rsi_candle.rsi_13 or (candle.rsi_13 == highest_rsi_candle.rsi_13 and time_diff < smallest_time_diff):
                highest_rsi_candle = candle
                smallest_time_diff = time_diff

        return highest_rsi_candle

    def get_previous_closest_green_lowest_rsi_candle_rsi_13(self, start_datetime, end_datetime, rsi_threshold, high_threshold, close_threshold, k_threshold, d_threshold):
        if not self.track_all_candles:
            return None

        # Filter candles by time and RSI threshold
        filtered_candles = [
            candle for candle in self.track_all_candles
            if start_datetime <= candle.datetime <= end_datetime and candle.rsi_13 < rsi_threshold and (candle.stoch_k > k_threshold or candle.stoch_d > d_threshold) and candle.high < high_threshold and candle.close < close_threshold and candle.body > 0
        ]

        if not filtered_candles:
            return None

        # Initialize with the first candle in the filtered list
        closest_lowest_rsi_candle = filtered_candles[0]
        smallest_time_diff = abs(start_datetime - filtered_candles[0].datetime)

        for candle in filtered_candles[1:]:
            time_diff = abs(start_datetime - candle.datetime)

            # Update if a candle has lower RSI or same RSI but closer to start_datetime
            if (candle.rsi_13 < closest_lowest_rsi_candle.rsi_13 or
                    (candle.rsi_13 == closest_lowest_rsi_candle.rsi_13 and time_diff < smallest_time_diff)):
                closest_lowest_rsi_candle = candle
                smallest_time_diff = time_diff

        return closest_lowest_rsi_candle

    def get_previous_closest_highest_rsi_candle(self, start_index, end_index):
        """
        Finds the closest highest RSI candle within a given index range.

        Args:
            start_index: The starting index of the range.
            end_index: The ending index of the range.

        Returns:
            The candle with the highest RSI that is closest to the start_index,
            or None if no candles are found within the range.
        """
        if not self.track_all_candles:
            return None

        # Filter candles to include those between start_index and end_index with a green body
        filtered_candles = [
            candle for candle in self.track_all_candles
            if start_index <= candle.index <= end_index and candle.body > 0
        ]

        if not filtered_candles:
            return None

        # Initialize the candle with the highest RSI and closest index
        highest_rsi_candle = filtered_candles[0]
        smallest_index_diff = abs(start_index - filtered_candles[0].index)

        for candle in filtered_candles[1:]:
            index_diff = abs(start_index - candle.index)

            # Select the candle if it has a higher RSI or the same RSI but a closer index
            if candle.rsi > highest_rsi_candle.rsi or (candle.rsi == highest_rsi_candle.rsi and index_diff < smallest_index_diff):
                highest_rsi_candle = candle
                smallest_index_diff = index_diff

        return highest_rsi_candle

    def get_previous_closest_highest_rsi_13_candle(self, start_index, end_index):
        """
        Finds the closest highest RSI candle within a given index range.

        Args:
            start_index: The starting index of the range.
            end_index: The ending index of the range.

        Returns:
            The candle with the highest RSI that is closest to the start_index,
            or None if no candles are found within the range.
        """
        if not self.track_all_candles:
            return None

        # Filter candles to include those between start_index and end_index with a green body
        filtered_candles = [
            candle for candle in self.track_all_candles
            if start_index <= candle.index <= end_index and candle.body > 0
        ]

        if not filtered_candles:
            return None

        # Initialize the candle with the highest RSI and closest index
        highest_rsi_candle = filtered_candles[0]
        smallest_index_diff = abs(start_index - filtered_candles[0].index)

        for candle in filtered_candles[1:]:
            index_diff = abs(start_index - candle.index)

            # Select the candle if it has a higher RSI or the same RSI but a closer index
            if candle.rsi_13 > highest_rsi_candle.rsi_13 or (candle.rsi_13 == highest_rsi_candle.rsi_13 and index_diff < smallest_index_diff):
                highest_rsi_candle = candle
                smallest_index_diff = index_diff

        return highest_rsi_candle

    def get_previous_closest_lowest_rsi_candle(self, start_index, end_index):
        """
        Finds the closest lowest RSI candle within a given index range.

        Args:
            start_index: The starting index of the range.
            end_index: The ending index of the range.

        Returns:
            The candle with the lowest RSI that is closest to the start_index,
            or None if no candles are found within the range.
        """
        if not self.track_all_candles:
            return None

        # Filter candles to include those between start_index and end_index with a green body
        filtered_candles = [
            candle for candle in self.track_all_candles
            if start_index <= candle.index <= end_index and candle.body < 0
        ]

        if not filtered_candles:
            return None

        # Initialize the candle with the lowest RSI and closest index
        lowest_rsi_candle = filtered_candles[0]
        smallest_index_diff = abs(start_index - filtered_candles[0].index)

        for candle in filtered_candles[1:]:
            index_diff = abs(start_index - candle.index)

            # Select the candle if it has a lower RSI or the same RSI but a closer index
            if candle.rsi < lowest_rsi_candle.rsi or (candle.rsi == lowest_rsi_candle.rsi and index_diff < smallest_index_diff):
                lowest_rsi_candle = candle
                smallest_index_diff = index_diff

        return lowest_rsi_candle

    def get_previous_closest_lowest_rsi_13_candle(self, start_index, end_index):
        """
        Finds the closest lowest RSI candle within a given index range.

        Args:
            start_index: The starting index of the range.
            end_index: The ending index of the range.

        Returns:
            The candle with the lowest RSI that is closest to the start_index,
            or None if no candles are found within the range.
        """
        if not self.track_all_candles:
            return None

        # Filter candles to include those between start_index and end_index with a green body
        filtered_candles = [
            candle for candle in self.track_all_candles
            if start_index <= candle.index <= end_index and candle.body < 0
        ]

        if not filtered_candles:
            return None

        # Initialize the candle with the lowest RSI and closest index
        lowest_rsi_candle = filtered_candles[0]
        smallest_index_diff = abs(start_index - filtered_candles[0].index)

        for candle in filtered_candles[1:]:
            index_diff = abs(start_index - candle.index)

            # Select the candle if it has a lower RSI or the same RSI but a closer index
            if candle.rsi_13 < lowest_rsi_candle.rsi_13 or (candle.rsi_13 == lowest_rsi_candle.rsi_13 and index_diff < smallest_index_diff):
                lowest_rsi_candle = candle
                smallest_index_diff = index_diff

        return lowest_rsi_candle

    def get_previous_closest_highest_price_candle(self, start_index, end_index):
        """
        Finds the closest highest close price candle within a given index range.

        Args:
            start_index: The starting timestamp of the range.
            end_index: The ending timestamp of the range.

        Returns:
            The candle with the highest close price that is closest to the start_index,
            or None if no candles are found within the range.
        """
        if not self.track_all_candles:
            return None

        # Filter candles within the specified index range
        filtered_candles = [
            candle for candle in self.track_all_candles
            if start_index <= candle.index <= end_index and candle.body > 0
        ]

        if not filtered_candles:
            return None

        # Find the candle with the highest close price and the latest index
        highest_price_candle = max(
            filtered_candles,
            key=lambda candle: (candle.close, candle.index)
        )

        return highest_price_candle

    def get_previous_closest_lowest_price_candle(self, start_index, end_index):
        """
        Finds the latest lowest close price candle within a given index range.

        Args:
            start_index: The starting timestamp of the range.
            end_index: The ending timestamp of the range.

        Returns:
            The candle with the lowest close price that is the latest,
            or None if no candles are found within the range.
        """
        if not self.track_all_candles:
            return None

        # Filter candles within the specified index range
        filtered_candles = [
            candle for candle in self.track_all_candles
            if start_index <= candle.index <= end_index and candle.body < 0
        ]

        if not filtered_candles:
            return None

        # Find the candle with the lowest close price and the latest timestamp
        lowest_price_candle = min(
            filtered_candles,
            key=lambda candle: (candle.close, -candle.index.timestamp())
        )

        return lowest_price_candle

    def combine_rsi_stoch_fib_numbers(self, numbers: List[RsiStochFibNumber]) -> List[RsiStochFibNumber]:
        combined_list = []
        skip_next = False

        for i in range(len(numbers)):
            if skip_next:
                skip_next = False
                continue

            current = numbers[i]
            for offset in range(1, 4):  # Look ahead 1 to 3 candles
                if i + offset < len(numbers):
                    next_number = numbers[i + offset]

                    # Check for time difference between new_high_candle or new_low_candle and next_number
                    if (current.new_high_candle and current.new_high_candle.datetime and
                        abs((current.new_high_candle.datetime - next_number.datetime).total_seconds()) / 60 <= 4) or \
                            (current.new_low_candle and current.new_low_candle.datetime and
                             abs((current.new_low_candle.datetime - next_number.datetime).total_seconds()) / 60 <= 4):

                        # Combine the entries
                        combined_entry = RsiStochFibNumber(
                            open=current.open,
                            close=current.close,
                            high=current.high,
                            low=current.low,
                            rsi=current.rsi,
                            stoch_k=current.stoch_k,
                            stoch_d=current.stoch_d,
                            fib=current.fib,
                            date=current.date,
                            body=current.body,
                            close_open=current.close_open,
                            index=current.index,
                        )
                        combined_entry.cumulative_close_diff = current.cumulative_close_diff + next_number.cumulative_close_diff
                        combined_entry.is_new_high = current.is_new_high or next_number.is_new_high
                        combined_entry.is_new_low = current.is_new_low or next_number.is_new_low
                        combined_entry.new_high_candle = next_number.new_high_candle
                        combined_entry.new_low_candle = next_number.new_low_candle
                        combined_entry.datetime = current.datetime

                        combined_list.append(combined_entry)
                        skip_next = True
                        break
            if not skip_next:
                combined_list.append(current)

        return combined_list

    def update_higher_candle(self, upward_swing):
        if upward_swing:
            if not self.highest_candle:
                self.highest_candle = upward_swing.new_high_candle
            elif upward_swing.new_high_candle.high > self.highest_candle.high:
                self.highest_candle = upward_swing.new_high_candle

    def update_lower_candle(self, downward_swing):
        if downward_swing:
            if not self.lowest_candle:
                self.lowest_candle = downward_swing.new_low_candle
            elif downward_swing.new_low_candle.low < self.lowest_candle.low:
                self.lowest_candle = downward_swing.new_low_candle

    def get_highest_price_between_dates(self, start_datetime, end_datetime):
        if not self.track_all_candles:
            return None

        # Filter candles to only include those within the specified date range
        filtered_candles = [candle for candle in self.track_all_candles if start_datetime <= candle.datetime <= end_datetime]

        if not filtered_candles:
            return None

        # Find the candle with the highest price among the filtered candles
        highest_price_candle = filtered_candles[0]

        for candle in filtered_candles[1:]:
            if candle.high > highest_price_candle.high and candle.body > 0:
                highest_price_candle = candle

        return highest_price_candle

    def get_lowest_price_between_dates(self, start_datetime, end_datetime):
        if not self.track_all_candles:
            return None

        # Filter candles to only include those within the specified date range
        filtered_candles = [candle for candle in self.track_all_candles if start_datetime <= candle.datetime <= end_datetime]

        if not filtered_candles:
            return None

        # Find the candle with the lowest price among the filtered candles
        lowest_price_candle = filtered_candles[0]

        for candle in filtered_candles[1:]:
            if candle.low < lowest_price_candle.low and candle.body < 0:
                lowest_price_candle = candle

        return lowest_price_candle

    def get_highest_close_price_between_dates(self, start_datetime, end_datetime):
        if not self.track_all_candles:
            return None

        # Filter candles to only include those within the specified date range
        filtered_candles = [candle for candle in self.track_all_candles if start_datetime <= candle.datetime <= end_datetime]

        if not filtered_candles:
            return None

        # Get the start_datetime candle
        start_candle = next((c for c in self.track_all_candles if c.datetime == start_datetime), None)

        if not start_candle:
            return None

        start_close = start_candle.close

        # Find the highest close price candle within the range
        highest_price_candle = None

        for candle in filtered_candles:
            if candle.close > start_close:
                if highest_price_candle is None or candle.close > highest_price_candle.close:
                    highest_price_candle = candle

        return highest_price_candle

    def get_lowest_price_close_between_dates(self, start_datetime, end_datetime):
        if not self.track_all_candles:
            return None

        # Filter candles to only include those within the specified date range
        filtered_candles = [candle for candle in self.track_all_candles if start_datetime <= candle.datetime <= end_datetime]

        if not filtered_candles:
            return None

        # Get the start_datetime candle
        start_candle = next((c for c in self.track_all_candles if c.datetime == start_datetime), None)

        if not start_candle:
            return None

        start_close = start_candle.close

        # Find the lowest close price candle within the range
        lowest_price_candle = None

        for candle in filtered_candles:
            if candle.close < start_close:
                if lowest_price_candle is None or candle.close < lowest_price_candle.close:
                    lowest_price_candle = candle

        return lowest_price_candle

    def get_highest_price_between_dates_above_divergence_end_candle(self, start_datetime, end_datetime):
        if not self.track_all_candles:
            return None

        # Filter candles to only include those within the specified date range
        filtered_candles = [candle for candle in self.track_all_candles if start_datetime <= candle.datetime <= end_datetime]

        if not filtered_candles:
            return None

        # Get the start_datetime candle
        start_candle = next((c for c in self.track_all_candles if c.datetime == start_datetime), None)

        if not start_candle:
            return None

        start_close = start_candle.close

        # Find the highest price candle with close price above start_datetime candle's close
        highest_price_candle = None

        for candle in filtered_candles:
            if candle.close > start_close and (highest_price_candle is None or candle.high > highest_price_candle.high):
                highest_price_candle = candle

        return highest_price_candle

    def get_lowest_price_between_dates_below_divergence_end_candle(self, start_datetime, end_datetime):
        if not self.track_all_candles:
            return None

        # Filter candles to only include those within the specified date range
        filtered_candles = [candle for candle in self.track_all_candles if start_datetime <= candle.datetime <= end_datetime]

        if not filtered_candles:
            return None

        # Get the start_datetime candle
        start_candle = next((c for c in self.track_all_candles if c.datetime == start_datetime), None)

        if not start_candle:
            return None

        start_close = start_candle.close

        # Find the lowest price candle with close price below start_datetime candle's close
        lowest_price_candle = None

        for candle in filtered_candles:
            if candle.close < start_close and (lowest_price_candle is None or candle.low < lowest_price_candle.low):
                lowest_price_candle = candle

        return lowest_price_candle

    def get_lowest_price_between_start_and_end_divergence(self, start_datetime, end_datetime, end_candle):
        if not self.track_all_candles:
            return None

        # Filter candles to only include those within the specified date range, excluding end_candle
        filtered_candles = [candle for candle in self.track_all_candles if start_datetime < candle.datetime < end_datetime]

        if not filtered_candles:
            return None

        # Find the lowest price candle that is lower than end_candle.low
        for candle in filtered_candles:
            if candle.low < end_candle.low:
                return candle  # Return immediately if any candle is lower

        # If no candle is lower than end_candle.low, return None
        return None

    def get_highest_price_between_start_and_end_divergence(self, start_datetime, end_datetime, end_candle):
        if not self.track_all_candles:
            return None

        # Filter candles to only include those within the specified date range, excluding end_candle
        filtered_candles = [candle for candle in self.track_all_candles if start_datetime < candle.datetime < end_datetime]

        if not filtered_candles:
            return None

        # Find the lowest price candle that is lower than end_candle.low
        for candle in filtered_candles:
            if candle.high > end_candle.high:
                return candle  # Return immediately if any candle is lower

        # If no candle is lower than end_candle.low, return None
        return None

    def get_closest_rsi_red_candle_between_thresholds(self, start_timestamp, end_timestamp):
        if not self.track_all_candles:
            return None

        # Find the start and end candles using index (Timestamp)
        start_candle = next((c for c in self.track_all_candles if c.index == start_timestamp), None)
        end_candle = next((c for c in self.track_all_candles if c.index == end_timestamp), None)

        if not start_candle or not end_candle:
            return None  # Ensure both timestamps exist

        start_rsi = start_candle.rsi
        end_rsi = end_candle.rsi

        # Ensure start RSI < end RSI
        if not (start_rsi < end_rsi):
            return None

        # Get reference values from the end_timestamp candle
        reference_close = end_candle.close
        reference_low = end_candle.low  # Ensure low is not below end candle low

        # Filter candles meeting conditions and ensuring they are red candles
        filtered_candles = [
            candle for candle in self.track_all_candles
            if start_timestamp < candle.index < end_timestamp
               and start_rsi < candle.rsi < end_rsi
               and candle.close > reference_close
               and candle.low >= reference_low  # Ensure low is not below end candle low
               and candle.close < candle.open  # Ensure the candle is red
        ]

        if not filtered_candles:
            return None

        # Find the red candle with RSI closest to end_rsi
        closest_candle = min(filtered_candles, key=lambda c: abs(end_rsi - c.rsi))

        return closest_candle

    def get_closest_rsi_green_candle_between_thresholds(self, start_timestamp, end_timestamp):
        if not self.track_all_candles:
            return None

        # Find the start and end candles using index (Timestamp)
        start_candle = next((c for c in self.track_all_candles if c.index == start_timestamp), None)
        end_candle = next((c for c in self.track_all_candles if c.index == end_timestamp), None)

        if not start_candle or not end_candle:
            return None  # Ensure both timestamps exist

        start_rsi = start_candle.rsi
        end_rsi = end_candle.rsi

        # Ensure start RSI > end RSI
        if not (start_rsi > end_rsi):
            return None

        # Get reference values from the end_timestamp candle
        reference_close = end_candle.close
        reference_high = end_candle.high  # Condition: High should be below end candle's high

        # Filter candles meeting conditions and ensuring they are green candles
        filtered_candles = [
            candle for candle in self.track_all_candles
            if start_timestamp < candle.index < end_timestamp
               and candle.rsi > start_rsi  # RSI must be greater than start RSI
               and candle.close < reference_close  # Close should be below end candle close
               and candle.high <= reference_high  # High should be below end candle high
               and candle.close > candle.open  # Ensure the candle is green
        ]

        if not filtered_candles:
            return None

        # Find the green candle with RSI closest to start_rsi
        closest_candle = min(filtered_candles, key=lambda c: abs(start_rsi - c.rsi))

        return closest_candle

    def get_highest_green_closing_candle_between(self, start_timestamp, end_timestamp):
        if not self.track_all_candles:
            return None

        # Find the start and end candles using index (Timestamp)
        start_candle = next((c for c in self.track_all_candles if c.index == start_timestamp), None)
        end_candle = next((c for c in self.track_all_candles if c.index == end_timestamp), None)

        if not start_candle or not end_candle:
            return None  # Ensure both timestamps exist

        start_close = start_candle.close
        end_close = end_candle.close
        end_rsi = end_candle.rsi

        # Ensure start candle close is above end candle close
        if start_close <= end_close:
            return None

        # Find the highest close green candle between start and end timestamps
        valid_candles = [
            candle for candle in self.track_all_candles
            if start_timestamp < candle.index < end_timestamp
               and candle.close > candle.open  # Ensure it's a green candle
               and candle.rsi < end_rsi  # RSI should be lower than end RSI
               and candle.close > end_close  # Ensure close is above end candle close
        ]

        if not valid_candles:
            return None

        # Find the highest close value
        highest_close = max(candle.close for candle in valid_candles)

        # Get all candles with the highest close
        highest_close_candles = [c for c in valid_candles if c.close == highest_close]

        # If multiple candles have the same highest close, return the one closest to end_timestamp
        return min(highest_close_candles, key=lambda c: abs(end_timestamp - c.index))

    def get_lowest_red_closing_candle_between(self, start_timestamp, end_timestamp):
        if not self.track_all_candles:
            return None

        # Find the start and end candles using index (Timestamp)
        start_candle = next((c for c in self.track_all_candles if c.index == start_timestamp), None)
        end_candle = next((c for c in self.track_all_candles if c.index == end_timestamp), None)

        if not start_candle or not end_candle:
            return None  # Ensure both timestamps exist

        start_close = start_candle.close
        end_close = end_candle.close
        end_rsi = end_candle.rsi
        end_high = end_candle.high  # Reference high for filtering

        # Ensure start candle close is below end candle close
        if start_close >= end_close:
            return None

        # Filter only red candles meeting the conditions
        valid_red_candles = [
            candle for candle in self.track_all_candles
            if start_timestamp < candle.index < end_timestamp
               and candle.close < candle.open  # Ensure it's a red candle
               and candle.rsi > end_rsi  # RSI should be higher than end RSI
               and candle.close < end_close  # Ensure close is below end candle close
        ]

        if not valid_red_candles:
            return None

        # Find the red candle with the lowest close
        lowest_close_red_candle = min(valid_red_candles, key=lambda c: c.close)

        return lowest_close_red_candle

    def find_previous_lowest_rsi_candle(self, rsi_above_94_timestamp, track_all_candles):
        prev_rsi = float('inf')
        lowest_candle = None

        for candle in reversed(track_all_candles):
            if candle.datetime >= rsi_above_94_timestamp:
                continue
            if candle.rsi is None:
                continue

            if candle.rsi < prev_rsi:
                lowest_candle = candle
                prev_rsi = candle.rsi
            else:
                break  # stop when RSI starts rising

        return lowest_candle

    def find_previous_highest_rsi_candle(self, rsi_below_5_timestamp, track_all_candles):
        prev_rsi = float('-inf')
        highest_candle = None

        for candle in reversed(track_all_candles):
            if candle.datetime >= rsi_below_5_timestamp:
                continue
            if candle.rsi is None:
                continue

            if candle.rsi > prev_rsi:
                highest_candle = candle
                prev_rsi = candle.rsi
            else:
                break  # stop when RSI starts falling

        return highest_candle

    def find_previous_highest_price_candle(self, lowest_red_candle, track_all_candles):
        prev_high = lowest_red_candle.high
        highest_candle = None

        for candle in reversed(track_all_candles):
            if candle.datetime >= lowest_red_candle.index:
                continue
            if candle.rsi is None:
                continue

            if candle.high > prev_high:
                highest_candle = candle
                prev_high = candle.high
            else:
                break  # stop when High starts falling

        return highest_candle

    def find_previous_highest_close_price_candle(self, current_candle, track_all_candles):
        close_price = current_candle.close

        for candle in reversed(track_all_candles):
            if candle.datetime >= current_candle.index:
                continue
            if candle.rsi is None:
                continue

            if candle.close > close_price and candle.close > candle.open:
                return candle

        return None

    def find_previous_lowest_rsi_candle_latest(self, current_candle, track_all_candles, use_close):
        current_rsi = current_candle.rsi

        for candle in reversed(track_all_candles):
            if candle.datetime >= current_candle.index:
                continue
            if candle.rsi is None:
                continue

            if candle.rsi < current_rsi and candle.body < 0 and candle.close < current_candle.close and use_close:
                return candle  # Found the first candle with lower RSI — exit early

            if candle.rsi < current_rsi and candle.body < 0  and not use_close:
                return candle  # Found the first candle with lower RSI — exit early

        return None  # No such candle found

    def find_previous_lowest_stoch_d_candle_latest(self, current_candle, track_all_candles, use_close):
        current_stoch_d = current_candle.stoch_d

        for candle in reversed(track_all_candles):
            if candle.datetime >= current_candle.index:
                continue
            if candle.stoch_d is None:
                continue

            if candle.stoch_d < current_stoch_d and candle.body < 0 and candle.close < current_candle.close and use_close:
                return candle  # Found the first candle with lower RSI — exit early

            if candle.stoch_d < current_stoch_d and candle.body < 0  and not use_close:
                return candle  # Found the first candle with lower RSI — exit early

        return None  # No such candle found

    def find_previous_lowest_stoch_d_and_below_20_candle_latest(self, current_candle, track_all_candles, use_close):
        current_stoch_d = current_candle.stoch_d

        for candle in reversed(track_all_candles):
            if candle.datetime >= current_candle.index:
                continue
            if candle.stoch_d is None:
                continue

            if candle.stoch_d < current_stoch_d and candle.stoch_d < 20 and candle.stoch_k == 0 and candle.body < 0 and candle.close < current_candle.close and use_close:
                return candle  # Found the first candle with lower RSI — exit early

            if candle.stoch_d < current_stoch_d and candle.body < 0 and candle.stoch_k == 0 and not use_close and candle.stoch_d < 20:
                return candle  # Found the first candle with lower RSI — exit early

        return None  # No such candle found

    def find_previous_lowest_stoch_k_candle_latest(self, current_candle, track_all_candles, use_close):
        current_stoch_k = current_candle.stoch_k

        for candle in reversed(track_all_candles):
            if candle.datetime >= current_candle.index:
                continue
            if candle.stoch_d is None:
                continue

            if candle.stoch_k <= current_stoch_k and candle.body < 0 and candle.close < current_candle.close and use_close:
                return candle  # Found the first candle with lower RSI — exit early

            if candle.stoch_k <= current_stoch_k and candle.body < 0  and not use_close:
                return candle  # Found the first candle with lower RSI — exit early

        return None  # No such candle found

    def find_next_lowest_rsi_candle_latest(self, current_candle, track_all_candles, use_close):
        current_rsi = current_candle.rsi
        start_index = track_all_candles.index(current_candle)

        for i in range(start_index, len(track_all_candles)):
            candle = track_all_candles[i]

            if candle.rsi is None:
                continue

            if candle.rsi < current_rsi and candle.body < 0:
                if use_close:
                    if candle.close < current_candle.close:
                        return candle
                else:
                    return candle

        return None  # No such candle found

    def find_previous_lowest_rsi_13_candle_latest(self, current_candle, track_all_candles, use_close):
        current_rsi = current_candle.rsi_13

        for candle in reversed(track_all_candles):
            if candle.datetime >= current_candle.index:
                continue
            if candle.rsi_13 is None:
                continue

            if candle.rsi_13 < current_rsi and not candle.rsi_13_used_for_cancel and candle.body < 0 and candle.close < current_candle.close and use_close:
                return candle  # Found the first candle with lower RSI — exit early

            if candle.rsi_13 < current_rsi and candle.body < 0  and not use_close:
                return candle  # Found the first candle with lower RSI — exit early

        return None  # No such candle found

    def find_previous_highest_rsi_13_candle_latest(self, current_candle, track_all_candles):
        current_rsi = current_candle.rsi_13

        for candle in reversed(track_all_candles):
            if candle.datetime >= current_candle.index:
                continue
            if candle.rsi_13 is None:
                continue
            if candle.rsi_13 > current_rsi and candle.body > 0:
                return candle  # Found the first candle with lower RSI — exit early

        return None  # No such candle found

    def find_previous_highest_stoch_k_candle_latest(self, current_candle, track_all_candles):
        current_stoch_k = current_candle.stoch_k

        for candle in reversed(track_all_candles):
            if candle.datetime >= current_candle.index:
                continue
            if candle.stoch_k is None:
                continue
            if candle.stoch_k >= current_stoch_k and candle.body > 0:
                return candle  # Found the first candle with lower RSI — exit early

        return None  # No such candle found

    def find_previous_highest_rsi_candle_with_doji_latest(self, current_candle, track_all_candles, use_close):
        current_rsi = current_candle.rsi

        for candle in reversed(track_all_candles):
            if candle.datetime >= current_candle.index:
                continue
            if candle.rsi is None:
                continue

            if candle.rsi > current_rsi and (candle.body > 0  or candle.body == 0) and candle.close > current_candle.close and use_close:
                return candle  # Found the first candle with higher RSI — exit early

            if candle.rsi > current_rsi and (candle.body > 0  or candle.body == 0)  and not use_close:
                return candle  # Found the first candle with higher RSI — exit early

        return None  # No such candle found

    def find_previous_highest_rsi_2_candle_latest(self, current_candle, track_all_candles):
        current_rsi = current_candle.rsi

        for candle in reversed(track_all_candles):
            if candle.datetime >= current_candle.index:
                continue
            if candle.rsi is None:
                continue
            if candle.rsi > current_rsi and candle.body > 0:
                return candle  # Found the first candle with lower RSI — exit early

        return None  # No such candle found

    def find_previous_lowest_rsi_13_candle_only(self, current_candle, track_all_candles):
        current_rsi = current_candle.rsi_13

        for candle in reversed(track_all_candles):
            if candle.datetime >= current_candle.index:
                continue
            if candle.rsi_13 is None:
                continue
            if candle.rsi_13 < current_rsi and candle.body < 0:
                return candle  # Found the first candle with lower RSI — exit early

        return None  # No such candle found

    def find_green_candle_from_low(self, index, track_all_candles):
        for candle in reversed(track_all_candles):
            if candle.datetime >= index:
                continue
            if candle.body > 0:
                return candle  # Found the first candle with higher RSI — exit early

        return None  # No such candle found

    def find_previous_highest_rsi_candle_latest(self, current_candle, track_all_candles, use_close):
        current_rsi = current_candle.rsi

        for candle in reversed(track_all_candles):
            if candle.datetime >= current_candle.index:
                continue
            if candle.rsi is None:
                continue

            if candle.rsi > current_rsi and candle.body > 0 and candle.close > current_candle.close and use_close:
                return candle  # Found the first candle with higher RSI — exit early

            if candle.rsi > current_rsi and candle.body > 0  and not use_close:
                return candle  # Found the first candle with higher RSI — exit early

        return None  # No such candle found

    def find_previous_highest_stoch_d_candle_latest(self, current_candle, track_all_candles, use_close):
        current_rsi = current_candle.stoch_d

        for candle in reversed(track_all_candles):
            if candle.datetime >= current_candle.index:
                continue
            if candle.rsi is None:
                continue

            if candle.stoch_d > current_rsi and candle.body > 0 and candle.close > current_candle.close and use_close:
                return candle  # Found the first candle with higher RSI — exit early

            if candle.stoch_d > current_rsi and candle.body > 0  and not use_close:
                return candle  # Found the first candle with higher RSI — exit early

        return None  # No such candle found

    def find_previous_highest_k_and_d_candle_latest(self, current_candle, track_all_candles, use_close):
        current_rsi_k = current_candle.stoch_k
        current_rsi_d = current_candle.stoch_d

        for candle in reversed(track_all_candles):
            if candle.datetime >= current_candle.index:
                continue
            if candle.rsi is None:
                continue

            if candle.stoch_k >= current_rsi_k and candle.stoch_d >= current_rsi_d and candle.body > 0 and candle.close > current_candle.close and use_close:
                return candle  # Found the first candle with higher RSI — exit early

            if candle.stoch_k >= current_rsi_k and candle.stoch_d >= current_rsi_d  and candle.body > 0  and not use_close:
                return candle  # Found the first candle with higher RSI — exit early

        return None  # No such candle found

    def find_previous_highest_rsi_candle_extreme(self, current_candle, track_all_candles):

        for candle in reversed(track_all_candles):
            if candle.datetime >= current_candle.index:
                continue
            if candle.rsi is None:
                continue

            if candle.rsi > 94:
                return candle  # Found the first candle with higher RSI — exit early

        return None  # No such candle found

    def find_previous_lowest_rsi_or_rsi_13_ir_stoch_k_candle_latest(self, current_candle, track_all_candles):
        current_rsi = current_candle.rsi
        current_rsi_13 = current_candle.rsi_13
        current_stoch_k = current_candle.stoch_k

        for candle in reversed(track_all_candles):
            if candle.datetime >= current_candle.index:
                continue
            if candle.rsi is None:
                continue


            if (candle.rsi < current_rsi or candle.rsi_13 < current_rsi_13 or candle.stoch_k < current_stoch_k) and candle.body < 0 :
                return candle  # Found the first candle with lower RSI — exit early

        return None  # No such candle found

    def find_previous_lowest_rsi_candle_extreme(self, current_candle, track_all_candles):

        for candle in reversed(track_all_candles):
            if candle.datetime >= current_candle.index:
                continue
            if candle.rsi is None:
                continue

            if candle.rsi < 5:
                return candle  # Found the first candle with higher RSI — exit early

        return None  # No such candle found

    def find_previous_highest_high_green_candle(self, current_candle, track_all_candles):
        highest_candle = None
        highest_high = None

        for candle in reversed(track_all_candles):
            if candle.datetime >= current_candle.index:
                continue
            if candle.body <= 0:
                continue  # skip red candles

            if highest_high is None or candle.high > highest_high:
                highest_high = candle.high
                highest_candle = candle
            else:
                # high is falling after reaching a peak
                break

        return highest_candle

    def find_previous_lowest_low_red_candle(self, current_candle, track_all_candles):
        lowest_candle = None
        lowest_low = None

        for candle in reversed(track_all_candles):
            if candle.datetime >= current_candle.index:
                continue
            if candle.body >= 0:
                continue  # skip green candles

            if lowest_low is None or candle.low < lowest_low:
                lowest_low = candle.low
                lowest_candle = candle
            else:
                # low is rising after reaching a bottom
                break

        return lowest_candle

    def find_red_candle_from_high(self, index, track_all_candles):
        for candle in reversed(track_all_candles):
            if candle.datetime >= index:
                continue
            if candle.body < 0:
                return candle  # Found the first candle with higher RSI — exit early

        return None  # No such candle found

    def find_red_with_lowes_k_or_13_candle_from_high(self, current_candle_high, red_candle, track_all_candles):
        for candle in reversed(track_all_candles):
            if candle.datetime >= current_candle_high.index:
                continue
            if candle.body < 0 and (candle.rsi_13 < red_candle.rsi_13 or candle.stoch_k < red_candle.stoch_k) and candle.rsi > red_candle.rsi:
                return candle  # Found the first candle with higher RSI — exit early

        return None  # No such candle found

    def find_rsi_13_used_for_cancel(self, start_candle, end_candle, track_all_candles):
        for candle in reversed(track_all_candles):
            if not (start_candle.datetime < candle.datetime < end_candle.datetime):
                continue
            if getattr(candle, 'rsi_13_used_for_cancel', False):  # Safely check the flag
                return candle  # Found the candle with the flag set to True

        return None  # No such candle found

    def find_red_candle_with_lowest_rsi_only(self, current_candle_high, red_candle, track_all_candles):
        for candle in reversed(track_all_candles):
            if candle.datetime >= current_candle_high.index:
                continue
            if candle.body < 0 and candle.rsi < red_candle.rsi:
                return candle  # Found the first candle with higher RSI — exit early

        return None  # No such candle found

    def find_previous_lowest_price_rsi_candle_new(self, start_timestamp, end_timestamp, track_all_candles):
        # Filter candles between start and end (exclusive of end_timestamp), with RSI and red candle
        valid_candles = [
            c for c in track_all_candles
            if start_timestamp < c.datetime < end_timestamp and c.rsi is not None and c.close < c.open
        ]

        # Return the red candle with the lowest RSI
        return min(valid_candles, key=lambda c: c.low, default=None)

    def find_candle_with_lowest_low_price_candle(self, start_timestamp, end_timestamp, track_all_candles):
        # Filter candles between start and end (exclusive of end_timestamp), with RSI and red candle
        valid_candles = [
            c for c in track_all_candles
            if start_timestamp < c.datetime < end_timestamp
        ]

        # Return the red candle with the lowest RSI
        return min(valid_candles, key=lambda c: c.low, default=None)

    def find_lowest_close_red_candle_between_start_end(self, start_timestamp, end_timestamp, track_all_candles):
        # Filter candles between start and end (exclusive of end_timestamp), with RSI and red candle
        valid_candles = [
            c for c in track_all_candles
            if start_timestamp <= c.index <= end_timestamp
        ]

        # Return the red candle with the lowest RSI
        return min(valid_candles, key=lambda c: c.close, default=None)

    def find_highest_close_green_candle_between_start_end(self, start_timestamp, end_timestamp, track_all_candles):
        # Filter candles between start and end (exclusive of end_timestamp), with RSI and red candle
        valid_candles = [
            c for c in track_all_candles
            if start_timestamp <= c.index <= end_timestamp
        ]

        # Return the red candle with the lowest RSI
        return max(valid_candles, key=lambda c: c.close, default=None)

    def find_highest_high_green_candle_between_start_end(self, start_timestamp, end_timestamp, track_all_candles):
        # Filter candles between start and end (exclusive of end_timestamp), with RSI and red candle
        valid_candles = [
            c for c in track_all_candles
            if start_timestamp < c.index < end_timestamp
        ]

        # Return the red candle with the lowest RSI
        return max(valid_candles, key=lambda c: c.high, default=None)

    def get_total_red_candles(self, start_timestamp, end_timestamp, track_all_candles):
        # Filter candles between start and end (exclusive of end_timestamp), with RSI and red candle
        valid_candles = [
            c for c in track_all_candles
            if start_timestamp < c.datetime < end_timestamp and c.rsi is not None and (c.close < c.open or c.close == c.open)
        ]

        # Return the red candle with the lowest RSI
        return len(valid_candles)

    def get_total_green_candles(self, start_timestamp, end_timestamp, track_all_candles):
        # Filter candles between start and end (exclusive of end_timestamp), with RSI and red candle
        valid_candles = [
            c for c in track_all_candles
            if start_timestamp < c.datetime < end_timestamp and c.rsi is not None and c.close > c.open
        ]

        # Return the red candle with the lowest RSI
        return len(valid_candles)

    def count_consecutive_green_candles(self, start_candle, track_all_candles):
        count = 0
        # Build a datetime -> candle map for quick access
        candle_map = {candle.datetime: candle for candle in track_all_candles}
        sorted_candles = sorted(track_all_candles, key=lambda c: c.datetime)

        for i in range(len(sorted_candles) - 1, -1, -1):
            candle = sorted_candles[i]
            if candle.datetime >= start_candle.datetime:
                continue  # skip start_candle and newer

            if i == 0:
                break  # no previous candle

            previous_candle = sorted_candles[i - 1]
            previous_body = previous_candle.close - previous_candle.open

            if candle.close > candle.open:  # green candle
                if previous_body >= 0:
                    if candle.low > previous_candle.low and candle.low > previous_candle.open:
                        count += 1
                    else:
                        break
                else:
                    count += 1  # skip low/open check if previous candle is red
            else:
                break  # red candle ends the streak

        return count

    def any_red_candle_with_extremen_rsi(self, start_timestamp, end_timestamp, track_all_candles):
        # Filter candles between start and end (exclusive of end_timestamp), with RSI and red candle
        valid_candles = [
            c for c in track_all_candles
            if start_timestamp <= c.datetime <= end_timestamp and c.rsi < 5 and c.close < c.open
        ]

        # Return the red candle with the lowest RSI
        return len(valid_candles)

    def find_previous_lowest_rsi_candle_with_rsi_13(self, start_timestamp, end_timestamp, track_all_candles):
        # Filter candles between start and end (exclusive of end_timestamp), with RSI and red candle
        valid_candles = [
            c for c in track_all_candles
            if start_timestamp < c.datetime < end_timestamp and c.rsi is not None and c.close < c.open and c.rsi_13 < 45
        ]

        # Return the red candle with the lowest RSI
        return min(valid_candles, key=lambda c: c.rsi, default=None)

    def find_previous_highest_rsi_candle_with_rsi_13(self, start_timestamp, end_timestamp, track_all_candles):
        # Filter candles between start and end (exclusive of end_timestamp), with RSI and red candle
        valid_candles = [
            c for c in track_all_candles
            if start_timestamp < c.datetime < end_timestamp and c.rsi is not None and c.close > c.open and c.rsi_13 > 55
        ]

        # Return the red candle with the lowest RSI
        return max(valid_candles, key=lambda c: c.rsi, default=None)

    def find_previous_highest_rsi_candle_new(self, start_timestamp, end_timestamp, track_all_candles):
        # Filter candles between start and end (exclusive of end_timestamp), with RSI and green candle
        valid_candles = [
            c for c in track_all_candles
            if start_timestamp < c.datetime < end_timestamp and c.rsi is not None and c.close > c.open
        ]

        # Return the green candle with the highest RSI
        return max(valid_candles, key=lambda c: c.rsi, default=None)

    def find_green_candle_with_highest_rsi_closest_to_candle2(self, candle1, candle2, track_all_candles):
        start_index = min(candle1.index, candle2.index)
        end_index = max(candle1.index, candle2.index)

        low_rsi = min(candle1.rsi, candle2.rsi)
        high_rsi = max(candle1.rsi, candle2.rsi)
        low_close = min(candle1.close, candle2.close)
        high_close = max(candle1.close, candle2.close)

        # Traverse in reverse so closest to candle2 comes first
        for candle in reversed(track_all_candles):
            if not (start_index < candle.index < end_index):
                continue
            if candle.close > candle.open and \
                    low_rsi < candle.rsi < high_rsi and \
                    low_close < candle.close < high_close:
                return candle  # First valid candle (closest to candle2)

        return None

    def find_previous_green_candle(self, red_candle_timestamp):
        for candle in reversed(self.track_all_candles):
            if candle.datetime >= red_candle_timestamp:
                continue
            if candle.close > candle.open:  # Green candle
                return candle

        return None  # If no green candle is found

    def find_previous_red_candle(self, green_candle_timestamp):
        for candle in reversed(self.track_all_candles):
            if candle.datetime >= green_candle_timestamp:
                continue
            if candle.close < candle.open:  # Red candle
                return candle
        return None

    def is_extreme_violation(self, divergence_info):
        """
        Checks if any candle between start_index and end_index has a close below (BUY)
        or above (SHORT) the close price of the end_index candle when is_extreme is True.

        :param divergence_info: Object with attributes start_index, end_index, is_extreme, trade_type.
        :return: True if any candle violates the condition, else False.
        """
        if not divergence_info.is_extreme or not self.track_all_candles:
            return False


        # Get start and end candles
        start_candle = next((c for c in self.track_all_candles if c.index == divergence_info.start_candle.index), None)
        end_candle = next((c for c in self.track_all_candles if c.index == divergence_info.end_candle.index), None)


        if not start_candle or not end_candle:
            return False  # Ensure both timestamps exist

        if start_candle.open == start_candle.close or end_candle.open == end_candle.close:
            conditons_reason = f"Script Five, Cancel Divergence due to one candle is Doji # {start_candle.index.strftime('%I:%M %p')}, End # {end_candle.index.strftime('%I:%M %p')} "
            self.log_condition("Cancel Divergence due to one candle is Doji", conditons_reason, self.current_candle.index )
            self.add_helper_messages(f"Script Five, Cancel Divergence due to one candle is Doji # {start_candle.index.strftime('%I:%M %p')}, End # {end_candle.index.strftime('%I:%M %p')} ")
            return False

        end_close = end_candle.close

        if divergence_info.trade_type == "BUY":
            # Check if any candle's close is less than end_close (for BUY)
            return any(
                candle.close < end_close
                for candle in self.track_all_candles
                if divergence_info.start_candle.index < candle.index < divergence_info.end_candle.index
            )
        elif divergence_info.trade_type == "SHORT":
            # Check if any candle's close is greater than end_close (for SHORT)
            return any(
                candle.close > end_close
                for candle in self.track_all_candles
                if divergence_info.start_candle.index < candle.index < divergence_info.end_candle.index
            )

        return False  # Default case if trade_type is invalid

    def add_divergence_info(self, is_buy, pre_condition, post_condition, start_candle, end_candle, is_extreme, is_rsi_13, swing_used, pre_condition_only, only_rsi):

        # Debugging: Check for specific candle date
        # Validate conditions based on latest swings
        # if is_buy and self.latest_downward_swing_candle_from_10_leg and start_candle.index < self.latest_downward_swing_candle_from_10_leg.start_index:
        #     self.add_messages(f"Removed Divergence, it was after {self.latest_downward_swing_candle_from_10_leg.start_index}")
        #     return
        # if not is_buy and self.latest_upward_swing_candle_from_10_leg and start_candle.index < self.latest_upward_swing_candle_from_10_leg.start_index:
        #     self.add_messages(f"Removed Divergence, it was after {self.latest_upward_swing_candle_from_10_leg.start_index}")
        #     return

        if "01:00 PM" in self.current_candle.date:
            print("Put Break Point")

        # Update pre_condition if post_condition is met
        if post_condition:
            pre_condition = False

        if is_extreme and only_rsi and not is_rsi_13:
            if is_buy:
                close_start_Candle = self.get_closest_rsi_red_candle_between_thresholds(start_candle.index, end_candle.index)
                if close_start_Candle:
                    start_candle = close_start_Candle
                if self.buy_divergence_candle and not post_condition:
                    if end_candle.index < self.buy_divergence_candle.index or end_candle.index == self.buy_divergence_candle.index:
                        end_candle.divergence_used = True
                        self.update_divergence_used_in_memory(end_candle)
                        return
            else :
                close_start_Candle = self.get_closest_rsi_green_candle_between_thresholds(start_candle.index, end_candle.index)
                if close_start_Candle:
                    start_candle = close_start_Candle
                if self.short_divergence_candle and not post_condition:
                    if end_candle.index < self.short_divergence_candle.index or end_candle.index == self.short_divergence_candle.index:
                        end_candle.divergence_used = True
                        self.update_divergence_used_in_memory(end_candle)
                        return

        if not is_extreme and only_rsi and not is_rsi_13:
            if is_buy:
                close_start_candle = self.get_lowest_red_closing_candle_between(start_candle.index, end_candle.index)
                if close_start_candle:
                    if end_candle.stoch_d  > close_start_candle.stoch_d  or  end_candle.stoch_k > close_start_candle.stoch_k :
                        start_candle = close_start_candle
            else:
                close_start_candle = self.get_highest_green_closing_candle_between(start_candle.index, end_candle.index)
                if close_start_candle:
                    if end_candle.stoch_d  < close_start_candle.stoch_d  or  end_candle.stoch_k < close_start_candle.stoch_k :
                        start_candle = close_start_candle


        # Determine trade type
        trade_type = 'BUY' if is_buy else 'SHORT'

        # Check if a divergence already exists for the given start_candle, end_candle, and trade_type
        existing_divergences = self.divergences_by_index.get(self.current_candle.index, [])
        for divergence in existing_divergences:
            if (
                    divergence.start_candle.index == start_candle.index and
                    divergence.end_candle.index == end_candle.index and
                    divergence.trade_type == trade_type
            ):
                # Skip adding duplicate divergence
                if post_condition and is_buy:
                    self.real_buy_divergence_candle = divergence

                if post_condition and not is_buy:
                    self.real_short_divergence_candle = divergence
                return

        # Create new divergence entry
        new_divergence = DivergenceInfo(
            index=self.current_candle.index,
            trade_type=trade_type,
            is_extreme=is_extreme,
            is_pre_condition=pre_condition,
            is_rsi_13=is_rsi_13,
            start_candle=start_candle,
            end_candle=end_candle,
            swing_used=swing_used,
            pre_condition_only=pre_condition_only,
            only_rsi=only_rsi
        )

        if post_condition and is_buy:
            self.real_buy_divergence_candle = new_divergence

        if post_condition and not is_buy:
            self.real_short_divergence_candle = new_divergence

        # Add new divergence to divergences_by_index
        if new_divergence.index in self.divergences_by_index:
            self.divergences_by_index[new_divergence.index].append(new_divergence)
        else:
            self.divergences_by_index[new_divergence.index] = [new_divergence]

    def get_divergence_info(self, index, trade_type=None):
        if index not in self.divergences_by_index:
            return None

        divergences = self.divergences_by_index[index]

        if trade_type:
            filtered_divergences = [div for div in divergences if div.trade_type == trade_type]
            divergence_info = filtered_divergences[-1] if filtered_divergences else None
        else:
            divergence_info = divergences[-1] if divergences else None

        if not divergence_info:
            return None

        time_difference = abs(divergence_info.end_candle.index - divergence_info.start_candle.index)

        # Return divergence only if at least one full candle exists between start and end
        if time_difference >= timedelta(minutes=2):
            return divergence_info

        return None

    def remove_divergence_info(self, index, divergence_info):
        if index in self.divergences_by_index:
            try:
                self.divergences_by_index[index].remove(divergence_info)

                # Remove the key if the list becomes empty
                if not self.divergences_by_index[index]:
                    del self.divergences_by_index[index]
            except ValueError:
                pass  # DivergenceInfo not found in the list, do nothing

    def copy_divergence(self, trade_type=None):
        # Get the previous and current indices
        previous_index = pd.Timestamp(self.current_candle.previous_index).round('s')
        current_index = self.current_candle.index

        # Check if the previous index has divergences
        if previous_index not in self.divergences_by_index:
            return

        # Get divergences at the previous index
        previous_divergences = self.divergences_by_index[previous_index]

        # Filter divergences based on the given trade_type
        filtered_divergences = [
            div for div in previous_divergences
            if not div.is_pre_condition and (trade_type is None or div.trade_type == trade_type)
        ]

        # If the current index already has a divergence with the same start and end candle indices, do not add
        if current_index in self.divergences_by_index:
            existing_divergences = self.divergences_by_index[current_index]
            for div in filtered_divergences:
                if any(
                        div.start_candle.index == existing_div.start_candle.index and
                        div.end_candle.index == existing_div.end_candle.index
                        for existing_div in existing_divergences
                ):
                    continue  # Skip if already exists

        # If no duplicate divergence exists, add the filtered divergences
        if filtered_divergences:
            if current_index not in self.divergences_by_index:
                self.divergences_by_index[current_index] = []
            # Copy filtered divergences, preserving the original index
            for div in filtered_divergences:
                copied_divergence = DivergenceInfo(
                    index=current_index,
                    trade_type=div.trade_type,
                    is_extreme=div.is_extreme,
                    is_pre_condition=div.is_pre_condition,
                    is_rsi_13=div.is_rsi_13,
                    start_candle=div.start_candle,
                    end_candle=div.end_candle,
                    swing_used=div.swing_used,
                    pre_condition_only=div.pre_condition_only
                )
                self.divergences_by_index[current_index].append(copied_divergence)

    def get_first_divergence_trade_type(self):

        current_index = self.current_candle.index
        if current_index not in self.divergences_by_index:
            return None

        # Get divergences for the current index
        divergences = self.divergences_by_index[current_index]

        # Find the divergence with the smallest start_candle.index
        first_divergence = max(divergences, key=lambda div: div.end_candle.index, default=None)

        # Return the trade_type of the first divergence if it exists
        return first_divergence.trade_type if first_divergence else None

    def get_latest_extreme_divergence(self, trade_type):
        """
        Finds the latest extreme divergence for the given trade_type.

        Args:
            trade_type: The trade type to filter divergences.

        Returns:
            The extreme divergence closest to the current_candle.index.
            Returns None if no extreme divergences exist for the given trade_type.
        """
        current_index = self.current_candle.index
        in_trade_candle_index = self.in_trade_candle.index if hasattr(self, 'in_trade_candle') and self.in_trade_candle else None

        # Flatten divergences list
        valid_divergences = [
            d for d in chain.from_iterable(self.divergences_by_index.values())
            if d.trade_type == trade_type and (not in_trade_candle_index or d.end_candle.index >= in_trade_candle_index)
        ]

        # Find the closest divergence
        return min(
            valid_divergences,
            key=lambda d: (
                abs((current_index - d.end_candle.index).total_seconds()),
                -d.end_candle.index.timestamp()  # Ensure latest divergence in case of tie
            ),
            default=None
        )

    def get_latest_pre_condition_divergence(self, trade_type):
        """
        Finds the latest extreme divergence for the given trade_type.

        Args:
            trade_type: The trade type to filter divergences.

        Returns:
            The extreme divergence closest to the current_candle.index.
            Returns None if no extreme divergences exist for the given trade_type.
        """
        current_index = self.current_candle.index
        in_trade_candle_index = self.in_trade_candle.index if hasattr(self, 'in_trade_candle') and self.in_trade_candle else None

        # Flatten divergences list
        valid_divergences = [
            d for d in chain.from_iterable(self.divergences_by_index.values())
            if d.trade_type == trade_type and d.pre_condition_only and (not in_trade_candle_index or d.end_candle.index >= in_trade_candle_index)
        ]

        # Find the closest divergence
        return min(
            valid_divergences,
            key=lambda d: (
                abs((current_index - d.end_candle.index).total_seconds()),
                -d.end_candle.index.timestamp()  # Ensure latest divergence in case of tie
            ),
            default=None
        )

    def get_latest_divergence(self, trade_type):
        """
        Finds the latest extreme divergence for the given trade_type.

        Args:
            trade_type: The trade type to filter divergences.

        Returns:
            The latest extreme divergence having the latest start and end candle.
            Returns None if no extreme divergences exist for the given trade_type.
        """
        if not self.divergences_by_index:
            return None

        current_index = self.current_candle.index
        in_trade_candle_index = (
            self.in_trade_candle.index if hasattr(self, 'in_trade_candle') and self.in_trade_candle else None
        )

        # Flatten divergences list and filter by trade_type
        valid_divergences = [
            d for d in chain.from_iterable(self.divergences_by_index.values())
            if d.trade_type == trade_type and (not in_trade_candle_index or d.end_candle.index > in_trade_candle_index)
        ]

        if not valid_divergences:
            return None

        # Sort divergences by start_candle.index and end_candle.index (latest first)
        valid_divergences.sort(key=lambda d: (d.start_candle.index, d.end_candle.index), reverse=True)

        # Return the latest divergence (first in sorted list)
        return valid_divergences[0]

    def add_messages(self, message):
        """
        Adds a helper message to `self.buying_shorting_conditions` for the current candle index.
        Supports storing multiple messages for the same index.

        :param message: The message to add.
        """
        index = self.current_candle.index

        # Ensure the key exists and is a list
        if index not in self.buying_shorting_conditions:
            self.buying_shorting_conditions[index] = []

        # Append the new message to the list
        self.buying_shorting_conditions[index].append(message)

    def find_message_flag(self, search_text):
        """
        Checks if any message for the current candle index contains the specified substring.

        :param search_text: The substring to search for.
        :return: True if a matching message is found, False otherwise.
        """
        index = self.current_candle.index

        # Get messages for the current index
        messages = self.buying_shorting_conditions.get(index, [])

        # Check for the substring in messages
        for msg in messages:
            if search_text in msg:
                return True
        return False

    def add_buy_sell_met_message(self, is_buy):
        message = 'Buy Condition Met' if is_buy else 'Short Condition Met'
        self.add_messages(message)

    def add_helper_messages(self, message):
        self.add_messages(message)

    def add_buy_sell_executed_message(self, is_buy, median, negative_trade=False, sideways_structure=False, profit_taking=False):
        message = None
        if median:
            message = 'Buy Condition Executed due to Median & Avg Median' if is_buy else 'Short Condition Executed due to Median & Avg Median'
        elif negative_trade:
            message = 'Buy Condition Executed due to price going opposite directly and trend is upward' if is_buy else 'Short Condition Executed due to price going opposite directly and trend is downward'
        elif sideways_structure:
            message = 'Buy Condition Executed due to price break above bottom sideway structure' if is_buy else 'Short Condition Executed due to price break below top sideway structure'
        elif profit_taking:
            message = 'Buy Condition Executed due to profit taking' if is_buy else 'Short Condition Executed due to profit taking'

        else:
            message = 'Buy Condition Executed using Divergence' if is_buy else 'Short Condition Executed using Divergence'

        self.add_messages(message)

    def is_non_extreme_internal_bullish_divergence_only_pre_condition(self, downward_swing_current, current_candle):
        closest_highest_rsi_candle = None
        pre_condition_buy = False

        if "02:01 PM" in self.current_candle.date:
            print("Put Break Point")

        if downward_swing_current and current_candle.body < 0 and current_candle.close > downward_swing_current.new_low_candle.close:
            closest_highest_rsi_candle = self.get_previous_closest_red_highest_rsi_candle_only_pre_condition(downward_swing_current.datetime, current_candle.datetime, current_candle.rsi, current_candle.low, current_candle.close, current_candle.stoch_k, current_candle.stoch_d)

            if closest_highest_rsi_candle and closest_highest_rsi_candle.body < 0 and downward_swing_current:
                if closest_highest_rsi_candle.low < current_candle.low and closest_highest_rsi_candle.close <= current_candle.low:
                    if current_candle.rsi < closest_highest_rsi_candle.rsi:
                        if current_candle.stoch_d > closest_highest_rsi_candle.stoch_d or current_candle.stoch_k > closest_highest_rsi_candle.stoch_k:
                            pre_condition_buy = True
                            self.add_divergence_info(True, pre_condition_buy, False, closest_highest_rsi_candle, current_candle, False , False, downward_swing_current, True, True)

        if not pre_condition_buy:
            if downward_swing_current and current_candle.body < 0 and current_candle.close > downward_swing_current.new_low_candle.close:
                closest_highest_rsi_candle = self.get_previous_closest_red_highest_rsi_candle_only_pre_condition_rsi_13(downward_swing_current.datetime, current_candle.datetime, current_candle.rsi_13, current_candle.low, current_candle.close, current_candle.stoch_k, current_candle.stoch_d)

            if closest_highest_rsi_candle and closest_highest_rsi_candle.body < 0 and downward_swing_current:
                if closest_highest_rsi_candle.low < current_candle.low and closest_highest_rsi_candle.close <= current_candle.low:
                    if current_candle.rsi_13 < closest_highest_rsi_candle.rsi_13:
                        if current_candle.stoch_d > closest_highest_rsi_candle.stoch_d or current_candle.stoch_k > closest_highest_rsi_candle.stoch_k:
                            pre_condition_buy = True
                            self.add_divergence_info(True, pre_condition_buy, False, closest_highest_rsi_candle, current_candle, False , True, downward_swing_current, True, True )


        if not pre_condition_buy and self.latest_downward_swing_candle_from_10_leg and current_candle.body < 0:
            closest_highest_rsi_candle = self.get_previous_closest_red_highest_rsi_candle_only_pre_condition(self.latest_downward_swing_candle_from_10_leg.start_index, current_candle.index, current_candle.rsi, current_candle.low, current_candle.close, current_candle.stoch_k, current_candle.stoch_d)

            if closest_highest_rsi_candle and closest_highest_rsi_candle.body < 0 and current_candle.body < 0:
                if closest_highest_rsi_candle.low < current_candle.low and closest_highest_rsi_candle.close <= current_candle.low:
                    if current_candle.rsi < closest_highest_rsi_candle.rsi:
                        if current_candle.stoch_d > closest_highest_rsi_candle.stoch_d or current_candle.stoch_k > closest_highest_rsi_candle.stoch_k:
                            pre_condition_buy = True
                            self.add_divergence_info(True, pre_condition_buy, False, closest_highest_rsi_candle, current_candle, False , False, None, True, True )

        if not pre_condition_buy and self.latest_downward_swing_candle_from_10_leg and current_candle.body < 0:
            closest_highest_rsi_candle = self.get_previous_closest_red_highest_rsi_candle_only_pre_condition_rsi_13(self.latest_downward_swing_candle_from_10_leg.start_index, current_candle.index, current_candle.rsi_13, current_candle.low, current_candle.close, current_candle.stoch_k, current_candle.stoch_d)

            if closest_highest_rsi_candle and closest_highest_rsi_candle.body < 0:
                if closest_highest_rsi_candle.low < current_candle.low and closest_highest_rsi_candle.close <= current_candle.low:
                    if current_candle.rsi_13 < closest_highest_rsi_candle.rsi_13:
                        if current_candle.stoch_d > closest_highest_rsi_candle.stoch_d or current_candle.stoch_k > closest_highest_rsi_candle.stoch_k:
                            pre_condition_buy = True
                            self.add_divergence_info(True, pre_condition_buy, False, closest_highest_rsi_candle, current_candle, False , True, None, True, True )

        return False, pre_condition_buy

    def is_artificial_bearish_divergence(self):
        pre_condition_short = False
        converting_to_short = False

        if self.first_high_rsi_candle_during_buy:
            if self.current_candle.rsi < 94 and self.current_candle.previous_rsi > 94:
                if self.current_candle.close < self.first_high_rsi_candle_during_buy.close:
                    self.second_high_rsi_candle_during_buy = self.get_candle_by_index(self.current_candle.previous_index)

        if self.second_high_rsi_candle_during_buy:
            if self.current_candle.close < self.second_high_rsi_candle_during_buy.low:
                pre_condition_short = True
                converting_to_short = True

        return converting_to_short, pre_condition_short

    def is_artificial_bullish_divergence(self):
        pre_condition_buy = False
        converting_to_buy = False

        if self.first_low_rsi_candle_during_short:
            if self.current_candle.rsi > 5  and self.current_candle.previous_rsi < 5:
                if self.current_candle.close > self.first_low_rsi_candle_during_short.close:
                    self.second_low_rsi_candle_during_short = self.get_candle_by_index(self.current_candle.previous_index)
        if self.second_low_rsi_candle_during_short:
            if self.current_candle.close > self.second_low_rsi_candle_during_short.high:
                pre_condition_buy = True
                converting_to_buy = True

        return converting_to_buy, pre_condition_buy

    def is_non_extreme_internal_bearish_divergence_only_pre_condition(self,  upward_swing_current, current_candle):


        if "02:01 PM" in self.current_candle.date:
            print("Put Break Point")

        closest_lowest_rsi_candle = None
        pre_condition_short = False
        if upward_swing_current and current_candle.body > 0 and current_candle.close < upward_swing_current.new_high_candle.close:
            closest_lowest_rsi_candle = self.get_previous_closest_green_lowest_rsi_candle_pre_condition_only(upward_swing_current.datetime, current_candle.datetime, current_candle.rsi, current_candle.high, current_candle.close, current_candle.stoch_k, current_candle.stoch_d)

            if closest_lowest_rsi_candle and closest_lowest_rsi_candle.body > 0 and upward_swing_current:
                if current_candle.close <= closest_lowest_rsi_candle.high and current_candle.high < closest_lowest_rsi_candle.high:
                    if current_candle.rsi > closest_lowest_rsi_candle.rsi:
                        if current_candle.stoch_d < closest_lowest_rsi_candle.stoch_d or current_candle.stoch_k < closest_lowest_rsi_candle.stoch_k:
                            pre_condition_short = True
                            self.add_divergence_info(False, pre_condition_short, False, closest_lowest_rsi_candle, current_candle, False , False, upward_swing_current, True, True )

        if not pre_condition_short:
            if upward_swing_current and current_candle.body > 0 and current_candle.close < upward_swing_current.new_high_candle.close:
                closest_lowest_rsi_candle = self.get_previous_closest_green_lowest_rsi_candle_pre_condition_only_rsi_13(upward_swing_current.datetime, current_candle.datetime, current_candle.rsi_13, current_candle.high, current_candle.close, current_candle.stoch_k, current_candle.stoch_d)

            if closest_lowest_rsi_candle and closest_lowest_rsi_candle.body > 0 and upward_swing_current:
                if current_candle.close <= closest_lowest_rsi_candle.high and current_candle.high < closest_lowest_rsi_candle.high:
                    if current_candle.rsi_13 > closest_lowest_rsi_candle.rsi_13:
                        if current_candle.stoch_d < closest_lowest_rsi_candle.stoch_d or current_candle.stoch_k < closest_lowest_rsi_candle.stoch_k:
                            pre_condition_short = True
                            self.add_divergence_info(False, pre_condition_short, False, closest_lowest_rsi_candle, current_candle, False , False, upward_swing_current, True, True )

        if not pre_condition_short and self.latest_upward_swing_candle_from_10_leg and current_candle.body > 0:
            closest_lowest_rsi_candle = self.get_previous_closest_green_lowest_rsi_candle_pre_condition_only(self.latest_upward_swing_candle_from_10_leg.start_index, current_candle.index, current_candle.rsi, current_candle.high, current_candle.close, current_candle.stoch_k, current_candle.stoch_d)

            if closest_lowest_rsi_candle and closest_lowest_rsi_candle.body > 0:
                if current_candle.close <= closest_lowest_rsi_candle.high and current_candle.high < closest_lowest_rsi_candle.high:
                    if current_candle.rsi > closest_lowest_rsi_candle.rsi:
                        if current_candle.stoch_d < closest_lowest_rsi_candle.stoch_d or current_candle.stoch_k < closest_lowest_rsi_candle.stoch_k:
                            pre_condition_short = True
                            self.add_divergence_info(False, pre_condition_short, False, closest_lowest_rsi_candle, current_candle, False , False, None, True, True )

        if not pre_condition_short and self.latest_upward_swing_candle_from_10_leg  and current_candle.body > 0:
            closest_lowest_rsi_candle = self.get_previous_closest_green_lowest_rsi_candle_pre_condition_only_rsi_13(self.latest_upward_swing_candle_from_10_leg.start_index, current_candle.index, current_candle.rsi_13, current_candle.high, current_candle.close, current_candle.stoch_k, current_candle.stoch_d)

            if closest_lowest_rsi_candle and closest_lowest_rsi_candle.body > 0 and current_candle.body > 0:
                if current_candle.close <= closest_lowest_rsi_candle.high and current_candle.high < closest_lowest_rsi_candle.high:
                    if current_candle.rsi_13 > closest_lowest_rsi_candle.rsi_13:
                        if current_candle.stoch_d < closest_lowest_rsi_candle.stoch_d or current_candle.stoch_k < closest_lowest_rsi_candle.stoch_k:
                            pre_condition_short = True
                            self.add_divergence_info(False, pre_condition_short, False, closest_lowest_rsi_candle, current_candle, False , True, None, True, True )

        return False, pre_condition_short

    def is_non_extreme_internal_bullish_divergence(self, downward_swing_current, current_candle):

        closest_lowest_rsi_candle = None
        closest_highest_rsi_candle = None
        converting_to_buy = False
        pre_condition_buy = False
        if downward_swing_current:
            closest_lowest_rsi_candle = self.get_previous_closest_red_lowest_rsi_candle(downward_swing_current.datetime, downward_swing_current.new_low_candle.datetime, downward_swing_current.new_low_candle.rsi, downward_swing_current.new_low_candle.low, downward_swing_current.new_low_candle.close)
            closest_highest_rsi_candle = self.get_previous_closest_red_highest_rsi_candle(downward_swing_current.datetime, downward_swing_current.new_low_candle.datetime, downward_swing_current.new_low_candle.rsi, downward_swing_current.new_low_candle.low, downward_swing_current.new_low_candle.close, downward_swing_current.new_low_candle.stoch_k, downward_swing_current.new_low_candle.stoch_d)
            if closest_highest_rsi_candle:
                lowest_price_candle = self.get_lowest_price_between_dates(downward_swing_current.datetime, closest_highest_rsi_candle.datetime)
                if lowest_price_candle.close < closest_highest_rsi_candle.close and lowest_price_candle.low < closest_highest_rsi_candle.low:
                    closest_highest_rsi_candle = None

        if closest_highest_rsi_candle and closest_highest_rsi_candle.body < 0 and downward_swing_current and not downward_swing_current.new_low_candle.divergence_used:
            time_diff = abs(closest_highest_rsi_candle.datetime - downward_swing_current.new_low_candle.datetime)
            if downward_swing_current.new_low_candle.low < closest_highest_rsi_candle.low and downward_swing_current.new_low_candle.close <= closest_highest_rsi_candle.low  and time_diff.total_seconds() < 30 * 60 and time_diff.total_seconds() > 2 * 60:
                if downward_swing_current.new_low_candle.rsi < closest_highest_rsi_candle.rsi:
                    if downward_swing_current.new_low_candle.stoch_d > closest_highest_rsi_candle.stoch_d or downward_swing_current.new_low_candle.stoch_k > closest_highest_rsi_candle.stoch_k:
                        pre_condition_buy = True
                        previous_green_candle = self.find_previous_green_candle(downward_swing_current.new_low_candle.index)
                        if (current_candle.close > downward_swing_current.new_low_candle.high
                            or (current_candle.rsi > previous_green_candle.rsi and downward_swing_current.new_low_candle.close != previous_green_candle.open)) \
                                or (current_candle.close > current_candle.previous_high and current_candle.rsi > current_candle.previous_rsi and  current_candle.rsi_13 > current_candle.previous_rsi_13 and  current_candle.stoch_k > current_candle.previous_stoch_k):
                            converting_to_buy = True
                    if converting_to_buy:
                        downward_swing_current.new_low_candle.divergence_used = True
                        self.buy_divergence_candle = self.get_candle_by_index(downward_swing_current.new_low_candle.index)
                        self.update_divergence_used_in_memory(downward_swing_current.new_low_candle)
                        self.add_candles_buy_side = [candle for candle in self.track_all_candles_during_short if candle.datetime >= downward_swing_current.new_low_candle.datetime]
                    self.add_divergence_info(True, False, converting_to_buy, closest_highest_rsi_candle, downward_swing_current.new_low_candle, False , False, downward_swing_current, False, False )

        if closest_lowest_rsi_candle and closest_lowest_rsi_candle.body < 0 and downward_swing_current and not downward_swing_current.new_low_candle.divergence_used:
            time_diff = abs(closest_lowest_rsi_candle.datetime - downward_swing_current.new_low_candle.datetime)
            if downward_swing_current.new_low_candle.low < closest_lowest_rsi_candle.low and downward_swing_current.new_low_candle.close <= closest_lowest_rsi_candle.low and time_diff.total_seconds() < 30 * 60 and time_diff.total_seconds() > 2 * 60:
                if downward_swing_current.new_low_candle.rsi > closest_lowest_rsi_candle.rsi:
                    pre_condition_buy = True
                    previous_green_candle = self.find_previous_green_candle(downward_swing_current.new_low_candle.index)
                    if (current_candle.close > downward_swing_current.new_low_candle.high
                        or (current_candle.rsi > previous_green_candle.rsi and downward_swing_current.new_low_candle.close != previous_green_candle.open)) \
                            or (current_candle.close > current_candle.previous_high and current_candle.rsi > current_candle.previous_rsi and  current_candle.rsi_13 > current_candle.previous_rsi_13 and  current_candle.stoch_k > current_candle.previous_stoch_k):
                        converting_to_buy = True
                    if converting_to_buy:
                        downward_swing_current.new_low_candle.divergence_used = True
                        self.buy_divergence_candle = self.get_candle_by_index(downward_swing_current.new_low_candle.index)
                        self.update_divergence_used_in_memory(downward_swing_current.new_low_candle)
                        self.add_candles_buy_side = [candle for candle in self.track_all_candles_during_short if candle.datetime >= downward_swing_current.new_low_candle.datetime]
                    self.add_divergence_info(True, False, converting_to_buy, closest_lowest_rsi_candle, downward_swing_current.new_low_candle, True , False, downward_swing_current, False, True )

        if not pre_condition_buy:
            converting_to_buy, pre_condition_buy = self.is_non_extreme_internal_bullish_divergence_rsi_13(downward_swing_current, current_candle)

        if not pre_condition_buy:
            converting_to_buy, pre_condition_buy = self.is_non_extreme_internal_bullish_divergence_for_10_leg(self.current_candle)

        if not pre_condition_buy:
            converting_to_buy, pre_condition_buy = self.is_non_extreme_internal_bullish_divergence_for_10_leg_rsi_13(self.current_candle)

        return converting_to_buy, pre_condition_buy

    def is_non_extreme_internal_bearish_divergence(self,  upward_swing_current, current_candle):

        closest_highest_rsi_candle = None
        closest_lowest_rsi_candle = None
        converting_to_short = False
        pre_condition_short = False
        if upward_swing_current:
            closest_highest_rsi_candle = self.get_previous_closest_green_highest_rsi_candle(upward_swing_current.datetime, upward_swing_current.new_high_candle.datetime, upward_swing_current.new_high_candle.rsi, upward_swing_current.new_high_candle.high, upward_swing_current.new_high_candle.close)
            closest_lowest_rsi_candle = self.get_previous_closest_green_lowest_rsi_candle(upward_swing_current.datetime, upward_swing_current.new_high_candle.datetime, upward_swing_current.new_high_candle.rsi, upward_swing_current.new_high_candle.high, upward_swing_current.new_high_candle.close, upward_swing_current.new_high_candle.stoch_k, upward_swing_current.new_high_candle.stoch_d)
            if closest_highest_rsi_candle:
                highest_price_candle = self.get_highest_price_between_dates(upward_swing_current.datetime, closest_highest_rsi_candle.datetime)
                if highest_price_candle.close > closest_highest_rsi_candle.close and highest_price_candle.high > closest_highest_rsi_candle.high:
                    closest_highest_rsi_candle = None

        if closest_lowest_rsi_candle and closest_lowest_rsi_candle.body > 0 and upward_swing_current  and not upward_swing_current.new_high_candle.divergence_used:
            time_diff = abs(closest_lowest_rsi_candle.datetime - upward_swing_current.new_high_candle.datetime)
            if upward_swing_current.new_high_candle.close >= closest_lowest_rsi_candle.high and upward_swing_current.new_high_candle.high > closest_lowest_rsi_candle.high and time_diff.total_seconds() < 30 * 60 and time_diff.total_seconds() > 2 * 60:
                if upward_swing_current.new_high_candle.rsi > closest_lowest_rsi_candle.rsi:
                    if upward_swing_current.new_high_candle.stoch_d < closest_lowest_rsi_candle.stoch_d or upward_swing_current.new_high_candle.stoch_k < closest_lowest_rsi_candle.stoch_k:
                        pre_condition_short = True
                        previous_red_candle = self.find_previous_red_candle(upward_swing_current.new_high_candle.index)
                        if current_candle.close < upward_swing_current.new_high_candle.low or (current_candle.rsi < previous_red_candle.rsi and upward_swing_current.new_high_candle.close != previous_red_candle.open):
                            converting_to_short = True
                    if converting_to_short:
                        upward_swing_current.new_high_candle.divergence_used = True
                        self.update_divergence_used_in_memory(upward_swing_current.new_high_candle)
                        self.short_divergence_candle = self.get_candle_by_index(upward_swing_current.new_high_candle.index)
                        self.add_candles_short_side = [candle for candle in self.track_all_candles_during_buy if candle.datetime >= upward_swing_current.new_high_candle.datetime]
                    self.add_divergence_info(False, pre_condition_short, converting_to_short, closest_lowest_rsi_candle, upward_swing_current.new_high_candle, False , False, upward_swing_current, False, False )

        if closest_highest_rsi_candle and closest_highest_rsi_candle.body > 0 and upward_swing_current and not upward_swing_current.new_high_candle.divergence_used:
            time_diff = abs(closest_highest_rsi_candle.datetime - upward_swing_current.new_high_candle.datetime)
            if upward_swing_current.new_high_candle.close >= closest_highest_rsi_candle.high and upward_swing_current.new_high_candle.high > closest_highest_rsi_candle.high and time_diff.total_seconds() < 30 * 60 and time_diff.total_seconds() > 2 * 60:
                if upward_swing_current.new_high_candle.rsi < closest_highest_rsi_candle.rsi:
                    pre_condition_short = True
                    previous_red_candle = self.find_previous_red_candle(upward_swing_current.new_high_candle.index)
                    if current_candle.close < upward_swing_current.new_high_candle.low or (current_candle.rsi < previous_red_candle.rsi and upward_swing_current.new_high_candle.close != previous_red_candle.open):
                        converting_to_short = True
                    if converting_to_short:
                        upward_swing_current.new_high_candle.divergence_used = True
                        self.short_divergence_candle = self.get_candle_by_index(upward_swing_current.new_high_candle.index)
                        self.update_divergence_used_in_memory(upward_swing_current.new_high_candle)
                        self.add_candles_short_side = [candle for candle in self.track_all_candles_during_buy if candle.datetime >= upward_swing_current.new_high_candle.datetime]
                    self.add_divergence_info(False, False, converting_to_short, closest_highest_rsi_candle, upward_swing_current.new_high_candle, True , False, upward_swing_current, False, True )

        if not pre_condition_short:
            converting_to_short, pre_condition_short = self.is_non_extreme_internal_bearish_divergence_rsi_13(upward_swing_current, current_candle)

        if not pre_condition_short:
            converting_to_short, pre_condition_short = self.is_non_extreme_internal_bearish_divergence_for_10_leg(self.current_candle)

        if not pre_condition_short:
            converting_to_short, pre_condition_short = self.is_non_extreme_internal_bearish_divergence_for_10_leg_rsi_13(self.current_candle)

        return converting_to_short, pre_condition_short

    def is_non_extreme_internal_bullish_divergence_rsi_13(self, downward_swing_current, current_candle):

        if "12:05 PM" in self.current_candle.date:
            print("Put Break Point")

        closest_lowest_rsi_candle = None
        closest_highest_rsi_candle = None
        converting_to_buy = False
        pre_condition_buy = False
        if downward_swing_current:
            closest_lowest_rsi_candle = self.get_previous_closest_red_lowest_rsi_candle_rsi_13(downward_swing_current.datetime, downward_swing_current.new_low_candle.datetime, downward_swing_current.new_low_candle.rsi_13, downward_swing_current.new_low_candle.low, downward_swing_current.new_low_candle.close)
            closest_highest_rsi_candle = self.get_previous_closest_red_highest_rsi_candle_rsi_13(downward_swing_current.datetime, downward_swing_current.new_low_candle.datetime, downward_swing_current.new_low_candle.rsi_13, downward_swing_current.new_low_candle.low, downward_swing_current.new_low_candle.close, downward_swing_current.new_low_candle.stoch_k, downward_swing_current.new_low_candle.stoch_d)
            if closest_highest_rsi_candle:
                lowest_price_candle = self.get_lowest_price_between_dates(downward_swing_current.datetime, closest_highest_rsi_candle.datetime)
                if lowest_price_candle.close < closest_highest_rsi_candle.close and lowest_price_candle.low < closest_highest_rsi_candle.low:
                    closest_highest_rsi_candle = None

        if closest_highest_rsi_candle and closest_highest_rsi_candle.body < 0 and downward_swing_current and not downward_swing_current.new_low_candle.divergence_used :
            time_diff = abs(closest_highest_rsi_candle.datetime - downward_swing_current.new_low_candle.datetime)
            if downward_swing_current.new_low_candle.low < closest_highest_rsi_candle.low and downward_swing_current.new_low_candle.close <= closest_highest_rsi_candle.low  and time_diff.total_seconds() < 30 * 60 and time_diff.total_seconds() > 2 * 60:
                if downward_swing_current.new_low_candle.rsi_13 < closest_highest_rsi_candle.rsi_13:
                    if downward_swing_current.new_low_candle.stoch_d > closest_highest_rsi_candle.stoch_d or downward_swing_current.new_low_candle.stoch_k > closest_highest_rsi_candle.stoch_k:
                        pre_condition_buy = True
                        previous_green_candle = self.find_previous_green_candle(downward_swing_current.new_low_candle.index)
                        if (current_candle.close > downward_swing_current.new_low_candle.high
                                or (current_candle.rsi > previous_green_candle.rsi  and current_candle.close > previous_green_candle.close and  downward_swing_current.new_low_candle.close != previous_green_candle.open) \
                                or (current_candle.close > current_candle.previous_high and current_candle.rsi > current_candle.previous_rsi and  current_candle.rsi_13 > current_candle.previous_rsi_13 and  current_candle.stoch_k > current_candle.previous_stoch_k)):
                            converting_to_buy = True
                    if converting_to_buy:
                        downward_swing_current.new_low_candle.divergence_used = True
                        self.buy_divergence_candle = self.get_candle_by_index(downward_swing_current.new_low_candle.index)
                        self.update_divergence_used_in_memory(downward_swing_current.new_low_candle)
                        self.add_candles_buy_side = [candle for candle in self.track_all_candles_during_short if candle.datetime >= downward_swing_current.new_low_candle.datetime]
                    self.add_divergence_info(True, False, converting_to_buy, closest_highest_rsi_candle, downward_swing_current.new_low_candle, False , True, downward_swing_current, False, False )

        if closest_lowest_rsi_candle and closest_lowest_rsi_candle.body < 0 and downward_swing_current and not downward_swing_current.new_low_candle.divergence_used:
            time_diff = abs(closest_lowest_rsi_candle.datetime - downward_swing_current.new_low_candle.datetime)
            if downward_swing_current.new_low_candle.low < closest_lowest_rsi_candle.low and downward_swing_current.new_low_candle.close <= closest_lowest_rsi_candle.low and time_diff.total_seconds() < 30 * 60 and time_diff.total_seconds() > 2 * 60:
                if downward_swing_current.new_low_candle.rsi_13 > closest_lowest_rsi_candle.rsi_13:
                    pre_condition_buy = True
                    previous_green_candle = self.find_previous_green_candle(downward_swing_current.new_low_candle.index)
                    if (current_candle.close > downward_swing_current.new_low_candle.high
                            or (current_candle.rsi > previous_green_candle.rsi and current_candle.close > previous_green_candle.close and downward_swing_current.new_low_candle.close != previous_green_candle.open) \
                            or (current_candle.close > current_candle.previous_high and current_candle.rsi > current_candle.previous_rsi and  current_candle.rsi_13 > current_candle.previous_rsi_13 and  current_candle.stoch_k > current_candle.previous_stoch_k)):
                        converting_to_buy = True
                    if converting_to_buy:
                        downward_swing_current.new_low_candle.divergence_used = True
                        self.buy_divergence_candle = self.get_candle_by_index(downward_swing_current.new_low_candle.index)
                        self.update_divergence_used_in_memory(downward_swing_current.new_low_candle)
                        self.add_candles_buy_side = [candle for candle in self.track_all_candles_during_short if candle.datetime >= downward_swing_current.new_low_candle.datetime]
                    self.add_divergence_info(True, False, converting_to_buy, closest_lowest_rsi_candle, downward_swing_current.new_low_candle, True , True, downward_swing_current, False, True )

        return converting_to_buy, pre_condition_buy

    def is_non_extreme_internal_bearish_divergence_rsi_13(self,  upward_swing_current, current_candle):

        closest_highest_rsi_candle = None
        closest_lowest_rsi_candle = None
        converting_to_short = False
        pre_condition_short = False
        if upward_swing_current:
            closest_highest_rsi_candle = self.get_previous_closest_green_highest_rsi_candle_rsi_13(upward_swing_current.datetime, upward_swing_current.new_high_candle.datetime, upward_swing_current.new_high_candle.rsi_13, upward_swing_current.new_high_candle.high, upward_swing_current.new_high_candle.close)
            closest_lowest_rsi_candle = self.get_previous_closest_green_lowest_rsi_candle_rsi_13(upward_swing_current.datetime, upward_swing_current.new_high_candle.datetime, upward_swing_current.new_high_candle.rsi_13, upward_swing_current.new_high_candle.high, upward_swing_current.new_high_candle.close, upward_swing_current.new_high_candle.stoch_k, upward_swing_current.new_high_candle.stoch_d)
            if closest_highest_rsi_candle:
                highest_price_candle = self.get_highest_price_between_dates(upward_swing_current.datetime, closest_highest_rsi_candle.datetime)
                if highest_price_candle.close > closest_highest_rsi_candle.close and highest_price_candle.high > closest_highest_rsi_candle.high:
                    closest_highest_rsi_candle = None

        if closest_lowest_rsi_candle and closest_lowest_rsi_candle.body > 0 and upward_swing_current  and not upward_swing_current.new_high_candle.divergence_used:
            time_diff = abs(closest_lowest_rsi_candle.datetime - upward_swing_current.new_high_candle.datetime)
            if upward_swing_current.new_high_candle.close >= closest_lowest_rsi_candle.high and upward_swing_current.new_high_candle.high > closest_lowest_rsi_candle.high and time_diff.total_seconds() < 30 * 60 and time_diff.total_seconds() > 2 * 60:
                if upward_swing_current.new_high_candle.rsi_13 > closest_lowest_rsi_candle.rsi_13:
                    if upward_swing_current.new_high_candle.stoch_d < closest_lowest_rsi_candle.stoch_d or upward_swing_current.new_high_candle.stoch_k < closest_lowest_rsi_candle.stoch_k:
                        pre_condition_short = True
                        previous_red_candle = self.find_previous_red_candle(upward_swing_current.new_high_candle.index)
                        if current_candle.close < upward_swing_current.new_high_candle.low or (current_candle.rsi < previous_red_candle.rsi and upward_swing_current.new_high_candle.close != previous_red_candle.open):
                            converting_to_short = True
                    if converting_to_short:
                        upward_swing_current.new_high_candle.divergence_used = True
                        self.update_divergence_used_in_memory(upward_swing_current.new_high_candle)
                        self.short_divergence_candle = self.get_candle_by_index(upward_swing_current.new_high_candle.index)
                        self.add_candles_short_side = [candle for candle in self.track_all_candles_during_buy if candle.datetime >= upward_swing_current.new_high_candle.datetime]
                    self.add_divergence_info(False, False, converting_to_short, closest_lowest_rsi_candle, upward_swing_current.new_high_candle, False , True, upward_swing_current, False, False )

        if closest_highest_rsi_candle and closest_highest_rsi_candle.body > 0 and upward_swing_current and not upward_swing_current.new_high_candle.divergence_used:
            time_diff = abs(closest_highest_rsi_candle.datetime - upward_swing_current.new_high_candle.datetime)
            if upward_swing_current.new_high_candle.close >= closest_highest_rsi_candle.high and upward_swing_current.new_high_candle.high > closest_highest_rsi_candle.high and time_diff.total_seconds() < 30 * 60 and time_diff.total_seconds() > 2 * 60:
                if upward_swing_current.new_high_candle.rsi_13 < closest_highest_rsi_candle.rsi_13:
                    pre_condition_short = True
                    previous_red_candle = self.find_previous_red_candle(upward_swing_current.new_high_candle.index)
                    if current_candle.close < upward_swing_current.new_high_candle.low or (current_candle.rsi < previous_red_candle.rsi and upward_swing_current.new_high_candle.close != previous_red_candle.open):
                        converting_to_short = True
                    if converting_to_short:
                        upward_swing_current.new_high_candle.divergence_used = True
                        self.update_divergence_used_in_memory(upward_swing_current.new_high_candle)
                        self.short_divergence_candle = self.get_candle_by_index(upward_swing_current.new_high_candle.index)
                        self.add_candles_short_side = [candle for candle in self.track_all_candles_during_buy if candle.datetime >= upward_swing_current.new_high_candle.datetime]
                    self.add_divergence_info(False, False, converting_to_short, closest_highest_rsi_candle, upward_swing_current.new_high_candle, False , True, upward_swing_current, False, True )


        return converting_to_short, pre_condition_short

    def is_non_extreme_internal_bullish_divergence_for_10_leg(self, current_candle):

        closest_lowest_rsi_candle = None
        closest_highest_rsi_candle = None
        converting_to_buy = False
        pre_condition_buy = False
        lowest_price_candle = None
        if self.latest_downward_swing_candle_from_10_leg:
            lowest_price_candle = self.get_lowest_price_between_dates(self.latest_downward_swing_candle_from_10_leg.start_index, self.latest_downward_swing_candle_from_10_leg.end_index)
            if lowest_price_candle:
                closest_lowest_rsi_candle = self.get_previous_closest_red_lowest_rsi_candle(self.latest_downward_swing_candle_from_10_leg.start_index, self.latest_downward_swing_candle_from_10_leg.end_index, lowest_price_candle.rsi, lowest_price_candle.low, lowest_price_candle.close)
                closest_highest_rsi_candle = self.get_previous_closest_red_highest_rsi_candle(self.latest_downward_swing_candle_from_10_leg.start_index, self.latest_downward_swing_candle_from_10_leg.end_index, lowest_price_candle.rsi, lowest_price_candle.low, lowest_price_candle.close, lowest_price_candle.stoch_k, lowest_price_candle.stoch_d)
                if closest_highest_rsi_candle:
                    if lowest_price_candle.close <= closest_highest_rsi_candle.close and lowest_price_candle.low <= closest_highest_rsi_candle.low:
                        closest_highest_rsi_candle = None

            if closest_highest_rsi_candle and closest_highest_rsi_candle.body < 0 and lowest_price_candle and not lowest_price_candle.divergence_used:
                time_diff = abs(closest_highest_rsi_candle.datetime - lowest_price_candle.datetime)
                if lowest_price_candle.low < closest_highest_rsi_candle.low and lowest_price_candle.close <= closest_highest_rsi_candle.low  and time_diff.total_seconds() < 30 * 60 and time_diff.total_seconds() > 2 * 60:
                    if lowest_price_candle.rsi < closest_highest_rsi_candle.rsi:
                        if lowest_price_candle.stoch_d > closest_highest_rsi_candle.stoch_d or lowest_price_candle.stoch_k > closest_highest_rsi_candle.stoch_k:
                            pre_condition_buy = True
                            previous_green_candle = self.find_previous_green_candle(lowest_price_candle.index)
                            if (current_candle.close > lowest_price_candle.high
                                or (current_candle.rsi > previous_green_candle.rsi and lowest_price_candle.close != previous_green_candle.open)) \
                                    or (current_candle.close > current_candle.previous_high and current_candle.rsi > current_candle.previous_rsi and  current_candle.rsi_13 > current_candle.previous_rsi_13 and  current_candle.stoch_k > current_candle.previous_stoch_k):
                                converting_to_buy = True
                        if converting_to_buy:
                            lowest_price_candle.divergence_used = True
                            self.update_divergence_used_in_memory(lowest_price_candle)
                            self.buy_divergence_candle = self.get_candle_by_index(lowest_price_candle.index)
                            self.add_candles_buy_side = [candle for candle in self.track_all_candles_during_short if candle.datetime >= lowest_price_candle.datetime]
                        self.add_divergence_info(True, False, converting_to_buy, closest_highest_rsi_candle, lowest_price_candle, False , False, lowest_price_candle, False, False )

            if closest_lowest_rsi_candle and closest_lowest_rsi_candle.body < 0 and lowest_price_candle and not lowest_price_candle.divergence_used:
                time_diff = abs(closest_lowest_rsi_candle.datetime - lowest_price_candle.datetime)
                if lowest_price_candle.low < closest_lowest_rsi_candle.low and lowest_price_candle.close <= closest_lowest_rsi_candle.low and time_diff.total_seconds() < 30 * 60 and time_diff.total_seconds() > 2 * 60:
                    if lowest_price_candle.rsi > closest_lowest_rsi_candle.rsi:
                        pre_condition_buy = True
                        previous_green_candle = self.find_previous_green_candle(lowest_price_candle.index)
                        if (current_candle.close > lowest_price_candle.high
                            or (current_candle.rsi > previous_green_candle.rsi and lowest_price_candle.close != previous_green_candle.open)) \
                                or (current_candle.close > current_candle.previous_high and current_candle.rsi > current_candle.previous_rsi and  current_candle.rsi_13 > current_candle.previous_rsi_13 and  current_candle.stoch_k > current_candle.previous_stoch_k):
                            converting_to_buy = True
                        if converting_to_buy:
                            lowest_price_candle.divergence_used = True
                            self.update_divergence_used_in_memory(lowest_price_candle)
                            self.buy_divergence_candle = self.get_candle_by_index(lowest_price_candle.index)
                            self.add_candles_buy_side = [candle for candle in self.track_all_candles_during_short if candle.datetime >= lowest_price_candle.datetime]
                        self.add_divergence_info(True, False, converting_to_buy, closest_lowest_rsi_candle, lowest_price_candle, True , False, lowest_price_candle, False, True )


        return converting_to_buy, pre_condition_buy

    def is_non_extreme_internal_bullish_divergence_for_10_leg_rsi_13(self, current_candle):

        closest_lowest_rsi_candle = None
        closest_highest_rsi_candle = None
        converting_to_buy = False
        pre_condition_buy = False
        lowest_price_candle = None
        if self.latest_downward_swing_candle_from_10_leg:
            lowest_price_candle = self.get_lowest_price_between_dates(self.latest_downward_swing_candle_from_10_leg.start_index, self.latest_downward_swing_candle_from_10_leg.end_index)
            if lowest_price_candle:
                closest_lowest_rsi_candle = self.get_previous_closest_red_lowest_rsi_candle_rsi_13(self.latest_downward_swing_candle_from_10_leg.start_index, self.latest_downward_swing_candle_from_10_leg.end_index, lowest_price_candle.rsi, lowest_price_candle.low, lowest_price_candle.close)
                closest_highest_rsi_candle = self.get_previous_closest_red_highest_rsi_candle_rsi_13(self.latest_downward_swing_candle_from_10_leg.start_index, self.latest_downward_swing_candle_from_10_leg.end_index, lowest_price_candle.rsi, lowest_price_candle.low, lowest_price_candle.close, lowest_price_candle.stoch_k, lowest_price_candle.stoch_d)
                if closest_highest_rsi_candle:
                    if lowest_price_candle.close <= closest_highest_rsi_candle.close and lowest_price_candle.low <= closest_highest_rsi_candle.low:
                        closest_highest_rsi_candle = None

            if closest_highest_rsi_candle and closest_highest_rsi_candle.body < 0 and lowest_price_candle and not lowest_price_candle.divergence_used:
                time_diff = abs(closest_highest_rsi_candle.datetime - lowest_price_candle.datetime)
                if lowest_price_candle.low < closest_highest_rsi_candle.low and lowest_price_candle.close <= closest_highest_rsi_candle.low  and time_diff.total_seconds() < 30 * 60 and time_diff.total_seconds() > 2 * 60:
                    if lowest_price_candle.rsi_13 < closest_highest_rsi_candle.rsi_13:
                        if lowest_price_candle.stoch_d > closest_highest_rsi_candle.stoch_d or lowest_price_candle.stoch_k > closest_highest_rsi_candle.stoch_k:
                            pre_condition_buy = True
                            previous_green_candle = self.find_previous_green_candle(lowest_price_candle.index)
                            if (current_candle.close > lowest_price_candle.high
                                or (current_candle.rsi > previous_green_candle.rsi and lowest_price_candle.close != previous_green_candle.open)) \
                                    or (current_candle.close > current_candle.previous_high and current_candle.rsi > current_candle.previous_rsi and  current_candle.rsi_13 > current_candle.previous_rsi_13 and  current_candle.stoch_k > current_candle.previous_stoch_k):
                                converting_to_buy = True
                        if converting_to_buy:
                            lowest_price_candle.divergence_used = True
                            self.update_divergence_used_in_memory(lowest_price_candle)
                            self.buy_divergence_candle = self.get_candle_by_index(lowest_price_candle.index)
                            self.add_candles_buy_side = [candle for candle in self.track_all_candles_during_short if candle.datetime >= lowest_price_candle.datetime]
                        self.add_divergence_info(True, False, converting_to_buy, closest_highest_rsi_candle, lowest_price_candle, False , True, lowest_price_candle, False, False)

            if closest_lowest_rsi_candle and closest_lowest_rsi_candle.body < 0 and lowest_price_candle and not lowest_price_candle.divergence_used:
                time_diff = abs(closest_lowest_rsi_candle.datetime - lowest_price_candle.datetime)
                if lowest_price_candle.low < closest_lowest_rsi_candle.low and lowest_price_candle.close <= closest_lowest_rsi_candle.low and time_diff.total_seconds() < 30 * 60 and time_diff.total_seconds() > 2 * 60:
                    if lowest_price_candle.rsi_13 > closest_lowest_rsi_candle.rsi_13:
                        pre_condition_buy = True
                        previous_green_candle = self.find_previous_green_candle(lowest_price_candle.index)
                        if (current_candle.close > lowest_price_candle.high
                            or (current_candle.rsi > previous_green_candle.rsi and lowest_price_candle.close != previous_green_candle.open)) \
                                or (current_candle.close > current_candle.previous_high and current_candle.rsi > current_candle.previous_rsi and  current_candle.rsi_13 > current_candle.previous_rsi_13 and  current_candle.stoch_k > current_candle.previous_stoch_k):
                            converting_to_buy = True
                        if converting_to_buy:
                            lowest_price_candle.divergence_used = True
                            self.update_divergence_used_in_memory(lowest_price_candle)
                            self.buy_divergence_candle = self.get_candle_by_index(lowest_price_candle.index)
                            self.add_candles_buy_side = [candle for candle in self.track_all_candles_during_short if candle.datetime >= lowest_price_candle.datetime]
                        self.add_divergence_info(True, False, converting_to_buy, closest_lowest_rsi_candle, lowest_price_candle, False , True, lowest_price_candle, False, True )


        return converting_to_buy, pre_condition_buy

    def is_non_extreme_internal_bearish_divergence_for_10_leg(self,  current_candle):

        closest_highest_rsi_candle = None
        closest_lowest_rsi_candle = None
        converting_to_short = False
        pre_condition_short = False
        highest_price_candle = None
        if self.latest_upward_swing_candle_from_10_leg:
            highest_price_candle = self.get_highest_price_between_dates(self.latest_upward_swing_candle_from_10_leg.start_index, self.latest_upward_swing_candle_from_10_leg.end_index)
            if highest_price_candle:
                closest_highest_rsi_candle = self.get_previous_closest_green_highest_rsi_candle(self.latest_upward_swing_candle_from_10_leg.start_index, self.latest_upward_swing_candle_from_10_leg.end_index, highest_price_candle.rsi, highest_price_candle.high, highest_price_candle.close)
                closest_lowest_rsi_candle = self.get_previous_closest_green_lowest_rsi_candle(self.latest_upward_swing_candle_from_10_leg.start_index, self.latest_upward_swing_candle_from_10_leg.end_index, highest_price_candle.rsi, highest_price_candle.high, highest_price_candle.close, highest_price_candle.stoch_k, highest_price_candle.stoch_d)
                if closest_highest_rsi_candle:
                    if highest_price_candle.close >= closest_highest_rsi_candle.close and highest_price_candle.high >= closest_highest_rsi_candle.high:
                        closest_highest_rsi_candle = None

            if closest_lowest_rsi_candle and closest_lowest_rsi_candle.body > 0 and highest_price_candle  and not highest_price_candle.divergence_used:
                time_diff = abs(closest_lowest_rsi_candle.datetime - highest_price_candle.datetime)
                if highest_price_candle.close >= closest_lowest_rsi_candle.high and highest_price_candle.high > closest_lowest_rsi_candle.high and time_diff.total_seconds() < 30 * 60 and time_diff.total_seconds() > 2 * 60:
                    if highest_price_candle.rsi > closest_lowest_rsi_candle.rsi:
                        if highest_price_candle.stoch_d < closest_lowest_rsi_candle.stoch_d or highest_price_candle.stoch_k < closest_lowest_rsi_candle.stoch_k:
                            pre_condition_short = True
                            previous_red_candle = self.find_previous_red_candle(highest_price_candle.index)
                            if current_candle.close < highest_price_candle.low or (current_candle.rsi < previous_red_candle.rsi and highest_price_candle.close != previous_red_candle.open):
                                converting_to_short = True
                        if converting_to_short:
                            highest_price_candle.divergence_used = True
                            self.update_divergence_used_in_memory(highest_price_candle)
                            self.short_divergence_candle = self.get_candle_by_index(highest_price_candle.index)
                            self.add_candles_short_side = [candle for candle in self.track_all_candles_during_buy if candle.datetime >= highest_price_candle.datetime]
                        self.add_divergence_info(False, False, converting_to_short, closest_lowest_rsi_candle, highest_price_candle, False , False, highest_price_candle, False, False )

            if closest_highest_rsi_candle and closest_highest_rsi_candle.body > 0 and highest_price_candle and not highest_price_candle.divergence_used:
                time_diff = abs(closest_highest_rsi_candle.datetime - highest_price_candle.datetime)
                if highest_price_candle.close >= closest_highest_rsi_candle.high and highest_price_candle.high > closest_highest_rsi_candle.high and time_diff.total_seconds() < 30 * 60 and time_diff.total_seconds() > 2 * 60:
                    if highest_price_candle.rsi < closest_highest_rsi_candle.rsi:
                        pre_condition_short = True
                        previous_red_candle = self.find_previous_red_candle(highest_price_candle.index)
                        if current_candle.close < highest_price_candle.low or (current_candle.rsi < previous_red_candle.rsi and highest_price_candle.close != previous_red_candle.open):
                            converting_to_short = True
                        if converting_to_short:
                            highest_price_candle.divergence_used = True
                            self.update_divergence_used_in_memory(highest_price_candle)
                            self.short_divergence_candle = self.get_candle_by_index(highest_price_candle.index)
                            self.add_candles_short_side = [candle for candle in self.track_all_candles_during_buy if candle.datetime >= highest_price_candle.datetime]
                        self.add_divergence_info(False, False, converting_to_short, closest_highest_rsi_candle, highest_price_candle, True , False, highest_price_candle, False, True )

        return converting_to_short, pre_condition_short

    def is_non_extreme_internal_bearish_divergence_for_10_leg_rsi_13(self,  current_candle):

        closest_highest_rsi_candle = None
        closest_lowest_rsi_candle = None
        converting_to_short = False
        pre_condition_short = False
        highest_price_candle = None
        if self.latest_upward_swing_candle_from_10_leg:
            highest_price_candle = self.get_highest_price_between_dates(self.latest_upward_swing_candle_from_10_leg.start_index, self.latest_upward_swing_candle_from_10_leg.end_index)
            if highest_price_candle:
                closest_highest_rsi_candle = self.get_previous_closest_green_highest_rsi_candle_rsi_13(self.latest_upward_swing_candle_from_10_leg.start_index, self.latest_upward_swing_candle_from_10_leg.end_index, highest_price_candle.rsi, highest_price_candle.high, highest_price_candle.close)
                closest_lowest_rsi_candle = self.get_previous_closest_green_lowest_rsi_candle_rsi_13(self.latest_upward_swing_candle_from_10_leg.start_index, self.latest_upward_swing_candle_from_10_leg.end_index, highest_price_candle.rsi, highest_price_candle.high, highest_price_candle.close, highest_price_candle.stoch_k, highest_price_candle.stoch_d)
                if closest_highest_rsi_candle:
                    if highest_price_candle.close >= closest_highest_rsi_candle.close and highest_price_candle.high >= closest_highest_rsi_candle.high:
                        closest_highest_rsi_candle = None

            if closest_lowest_rsi_candle and closest_lowest_rsi_candle.body > 0 and highest_price_candle  and not highest_price_candle.divergence_used:
                time_diff = abs(closest_lowest_rsi_candle.datetime - highest_price_candle.datetime)
                if highest_price_candle.close >= closest_lowest_rsi_candle.high and highest_price_candle.high > closest_lowest_rsi_candle.high and time_diff.total_seconds() < 30 * 60 and time_diff.total_seconds() > 2 * 60:
                    if highest_price_candle.rsi_13 > closest_lowest_rsi_candle.rsi_13:
                        if highest_price_candle.stoch_d < closest_lowest_rsi_candle.stoch_d or highest_price_candle.stoch_k < closest_lowest_rsi_candle.stoch_k:
                            pre_condition_short = True
                            previous_red_candle = self.find_previous_red_candle(highest_price_candle.index)
                            if current_candle.close < highest_price_candle.low or (current_candle.rsi < previous_red_candle.rsi and highest_price_candle.close != previous_red_candle.open):
                                converting_to_short = True
                        if converting_to_short:
                            highest_price_candle.divergence_used = True
                            self.update_divergence_used_in_memory(highest_price_candle)
                            self.short_divergence_candle = self.get_candle_by_index(highest_price_candle.index)
                            self.add_candles_short_side = [candle for candle in self.track_all_candles_during_buy if candle.datetime >= highest_price_candle.datetime]
                        self.add_divergence_info(False, False, converting_to_short, closest_lowest_rsi_candle, highest_price_candle, False , True, highest_price_candle, False, False )

            if closest_highest_rsi_candle and closest_highest_rsi_candle.body > 0 and highest_price_candle and not highest_price_candle.divergence_used:
                time_diff = abs(closest_highest_rsi_candle.datetime - highest_price_candle.datetime)
                if highest_price_candle.close >= closest_highest_rsi_candle.high and highest_price_candle.high > closest_highest_rsi_candle.high and time_diff.total_seconds() < 30 * 60 and time_diff.total_seconds() > 2 * 60:
                    if highest_price_candle.rsi_13 < closest_highest_rsi_candle.rsi_13:
                        pre_condition_short = True
                        previous_red_candle = self.find_previous_red_candle(highest_price_candle.index)
                        if current_candle.close < highest_price_candle.low or (current_candle.rsi < previous_red_candle.rsi and highest_price_candle.close != previous_red_candle.open):
                            converting_to_short = True
                        if converting_to_short:
                            highest_price_candle.divergence_used = True
                            self.update_divergence_used_in_memory(highest_price_candle)
                            self.short_divergence_candle = self.get_candle_by_index(highest_price_candle.index)
                            self.add_candles_short_side = [candle for candle in self.track_all_candles_during_buy if candle.datetime >= highest_price_candle.datetime]
                        self.add_divergence_info(False, False, converting_to_short, closest_highest_rsi_candle, highest_price_candle, False , True, highest_price_candle, False, True )

        return converting_to_short, pre_condition_short

    def is_bullish_divergence(self,  start_index, end_index):

        pre_condition_buy = False
        converting_to_buy = False
        closest_lowest_rsi_candle = self.get_previous_closest_lowest_rsi_candle(start_index, end_index)
        if closest_lowest_rsi_candle:
            closest_lowest_price_candle = self.get_previous_closest_lowest_price_candle(closest_lowest_rsi_candle.index, end_index)
            if closest_lowest_rsi_candle and closest_lowest_price_candle and not closest_lowest_price_candle.divergence_used:
                if closest_lowest_price_candle.index > closest_lowest_rsi_candle.index:
                    if closest_lowest_price_candle.close < closest_lowest_rsi_candle.close and closest_lowest_price_candle.close <= closest_lowest_rsi_candle.low:
                        if closest_lowest_price_candle.rsi > closest_lowest_rsi_candle.rsi:
                            pre_condition_buy = True
                            previous_green_candle = self.find_previous_green_candle(closest_lowest_price_candle.index)
                            if (self.current_candle.close > closest_lowest_price_candle.high
                                or (self.current_candle.rsi > previous_green_candle.rsi and closest_lowest_price_candle.close != previous_green_candle.open) and (closest_lowest_price_candle.rsi < 5 or closest_lowest_rsi_candle.rsi < 5)) \
                                    or (self.current_candle.close > self.current_candle.previous_high and self.current_candle.rsi > self.current_candle.previous_rsi and  self.current_candle.rsi_13 > self.current_candle.previous_rsi_13 and  self.current_candle.stoch_k > self.current_candle.previous_stoch_k and (closest_lowest_price_candle.rsi < 5 or closest_lowest_rsi_candle.rsi < 5)):
                                converting_to_buy = True
                        if converting_to_buy:
                            closest_lowest_price_candle.divergence_used = True
                            self.buy_divergence_candle = self.get_candle_by_index(closest_lowest_price_candle.index)
                            self.update_divergence_used_in_memory(closest_lowest_price_candle)
                        self.add_divergence_info(True, False, converting_to_buy, closest_lowest_rsi_candle, closest_lowest_price_candle, True , False, None, False, True )

        if not pre_condition_buy and not  converting_to_buy:
            closest_lowest_rsi_candle = self.get_previous_closest_lowest_rsi_13_candle(start_index, end_index)
            if closest_lowest_rsi_candle:
                closest_lowest_price_candle = self.get_previous_closest_lowest_price_candle(closest_lowest_rsi_candle.index, end_index)
                if closest_lowest_rsi_candle and closest_lowest_price_candle and not closest_lowest_price_candle.divergence_used:
                    if closest_lowest_price_candle.index > closest_lowest_rsi_candle.index:
                        if closest_lowest_price_candle.close < closest_lowest_rsi_candle.close and closest_lowest_price_candle.close <= closest_lowest_rsi_candle.low:
                            if closest_lowest_price_candle.rsi_13 > closest_lowest_rsi_candle.rsi_13:
                                pre_condition_buy = True
                                previous_green_candle = self.find_previous_green_candle(closest_lowest_price_candle.index)
                                if (self.current_candle.close > closest_lowest_price_candle.high
                                    or (self.current_candle.rsi > previous_green_candle.rsi and closest_lowest_price_candle.close != previous_green_candle.open) and (closest_lowest_price_candle.rsi < 5 or closest_lowest_rsi_candle.rsi < 5)) \
                                        or (self.current_candle.close > self.current_candle.previous_high and self.current_candle.rsi > self.current_candle.previous_rsi and  self.current_candle.rsi_13 > self.current_candle.previous_rsi_13 and  self.current_candle.stoch_k > self.current_candle.previous_stoch_k and (closest_lowest_price_candle.rsi < 5 or closest_lowest_rsi_candle.rsi < 5)):
                                    converting_to_buy = True
                            if converting_to_buy:
                                closest_lowest_price_candle.divergence_used = True
                                self.buy_divergence_candle = self.get_candle_by_index(closest_lowest_price_candle.index)
                                self.update_divergence_used_in_memory(closest_lowest_price_candle)
                            self.add_divergence_info(True, False, converting_to_buy, closest_lowest_rsi_candle, closest_lowest_price_candle, True , True, None, False, True )

        return converting_to_buy, pre_condition_buy

    def is_extreme_external_swing_bullish_divergence_triggered(self, downward_swing_current, current_candle):

        converting_to_buy = False
        pre_condition_buy = False

        if self.in_trade_candle:
            converting_to_buy, pre_condition_buy = self.is_bullish_divergence(self.in_trade_candle.index, self.current_candle.index)

        if self.latest_downward_swing_candle_from_10_leg and not pre_condition_buy:
            converting_to_buy, pre_condition_buy = self.is_bullish_divergence(self.latest_downward_swing_candle_from_10_leg.start_index, current_candle.index)

        if downward_swing_current and not pre_condition_buy:
            lowest_rsi_candle = self.get_lowest_rsi_candle_below_5_between_dates(self.save_downward_swing_previous.datetime , downward_swing_current.new_low_candle.datetime)

            save_downward_swing_previous_local = self.save_downward_swing_previous
            if self.save_downward_swing_previous and downward_swing_current.previous_swing_info:
                if self.save_downward_swing_previous.datetime == downward_swing_current.datetime:
                    save_downward_swing_previous_local = downward_swing_current.previous_swing_info

            if (lowest_rsi_candle and save_downward_swing_previous_local
                    and downward_swing_current.datetime != save_downward_swing_previous_local.datetime
                    and downward_swing_current.new_low_candle.low < lowest_rsi_candle.low
                    and downward_swing_current.new_low_candle.close < lowest_rsi_candle.close
                    and downward_swing_current.new_low_candle.low < save_downward_swing_previous_local.new_low_candle.low
                    and downward_swing_current.new_low_candle.close < save_downward_swing_previous_local.new_low_candle.close):
                if lowest_rsi_candle.rsi < downward_swing_current.new_low_candle.rsi and not downward_swing_current.new_low_candle.divergence_used:
                    lowest_rsi_candle_in_downward_swing = self.get_lowest_rsi_candle_between_dates(downward_swing_current.datetime, downward_swing_current.new_low_candle.datetime)
                    if lowest_rsi_candle_in_downward_swing.close > downward_swing_current.new_low_candle.close:
                        lowest_rsi_candle_in_downward_swing = downward_swing_current.new_low_candle
                    if lowest_rsi_candle.rsi < lowest_rsi_candle_in_downward_swing.rsi:
                        volume_condition = True #downward_swing_current.new_low_candle.body_volume < downward_swing_current.new_low_candle.previous_body_volume or downward_swing_current.new_low_candle.volume < downward_swing_current.new_low_candle.body_volume
                        if volume_condition:
                            pre_condition_buy = True
                            previous_green_candle = self.find_previous_green_candle(downward_swing_current.new_low_candle.index)
                            if ((current_candle.close > downward_swing_current.new_low_candle.high and current_candle.close > lowest_rsi_candle_in_downward_swing.high)
                                or (current_candle.rsi > previous_green_candle.rsi and downward_swing_current.new_low_candle.close != previous_green_candle.open)) \
                                    or (self.current_candle.close > self.current_candle.previous_high and self.current_candle.rsi > self.current_candle.previous_rsi and  self.current_candle.rsi_13 > self.current_candle.previous_rsi_13 and  self.current_candle.stoch_k > self.current_candle.previous_stoch_k):
                                self.add_candles_buy_side = [candle for candle in self.track_all_candles_during_short if candle.datetime >= downward_swing_current.new_low_candle.datetime]
                                converting_to_buy = True
                                downward_swing_current.new_low_candle.divergence_used = True
                                self.buy_divergence_candle = self.get_candle_by_index(downward_swing_current.new_low_candle.index)
                                self.update_divergence_used_in_memory(downward_swing_current.new_low_candle)
                        self.add_divergence_info(True, False, converting_to_buy, lowest_rsi_candle, lowest_rsi_candle_in_downward_swing, True , False, downward_swing_current, False, True )


        return converting_to_buy, pre_condition_buy

    def is_bearish_divergence(self,  start_index, end_index):

        pre_condition_short = False
        converting_to_short = False
        closest_highest_rsi_candle = self.get_previous_closest_highest_rsi_candle(start_index, end_index)
        if closest_highest_rsi_candle:
            closest_highest_price_candle = self.get_previous_closest_highest_price_candle(closest_highest_rsi_candle.index, end_index)
            if closest_highest_rsi_candle and closest_highest_price_candle and not closest_highest_price_candle.divergence_used:
                if closest_highest_price_candle.index > closest_highest_rsi_candle.index:
                    if closest_highest_price_candle.close > closest_highest_rsi_candle.close and closest_highest_price_candle.close >= closest_highest_rsi_candle.high:
                        if closest_highest_price_candle.rsi < closest_highest_rsi_candle.rsi:
                            pre_condition_short = True
                            previous_red_candle = self.find_previous_red_candle(closest_highest_price_candle.index)
                            find_previous_highest_rsi_13_candle = self.find_previous_highest_rsi_13_candle_latest(closest_highest_price_candle, self.track_all_candles)
                            check_rsi_13_close_below = False
                            if find_previous_highest_rsi_13_candle:
                                if closest_highest_price_candle.close < find_previous_highest_rsi_13_candle.close and closest_highest_price_candle.rsi_13 < 55 and find_previous_highest_rsi_13_candle.rsi_13 > 55 and self.current_candle.body < 0:
                                    check_rsi_13_close_below = True
                                    closest_highest_price_candle.check_rsi_13_close_below = True
                            if self.current_candle.close < closest_highest_price_candle.low or ((self.current_candle.rsi < previous_red_candle.rsi or check_rsi_13_close_below) and (closest_highest_price_candle.close != previous_red_candle.open or self.current_candle.close < closest_highest_price_candle.open) and self.current_candle.stoch_k < 80):
                                converting_to_short = True
                                # Special COndition for 04/11 to skip 12:04 short
                                if self.current_candle.body < 0 and self.current_candle.previous_body > 0 and self.current_candle.high > self.current_candle.previous_high and self.current_candle.close > self.current_candle.previous_low:
                                    converting_to_short = False
                        if converting_to_short:
                            closest_highest_price_candle.divergence_used = True
                            self.update_divergence_used_in_memory(closest_highest_price_candle)
                            self.short_divergence_candle = self.get_candle_by_index(closest_highest_price_candle.index)
                        self.add_divergence_info(False, False, converting_to_short, closest_highest_rsi_candle, closest_highest_price_candle, True , False, None, False, True )

        if not pre_condition_short and not converting_to_short:
            closest_highest_rsi_candle = self.get_previous_closest_highest_rsi_13_candle(start_index, end_index)
            if closest_highest_rsi_candle:
                closest_highest_price_candle = self.get_previous_closest_highest_price_candle(closest_highest_rsi_candle.index, end_index)
                if closest_highest_rsi_candle and closest_highest_price_candle and not closest_highest_price_candle.divergence_used:
                    if closest_highest_price_candle.index > closest_highest_rsi_candle.index:
                        if closest_highest_price_candle.close > closest_highest_rsi_candle.close and closest_highest_price_candle.close >= closest_highest_rsi_candle.high:
                            if closest_highest_price_candle.rsi_13 < closest_highest_rsi_candle.rsi_13:
                                pre_condition_short = True
                                previous_red_candle = self.find_previous_red_candle(closest_highest_price_candle.index)
                                find_previous_highest_rsi_13_candle = self.find_previous_highest_rsi_13_candle_latest(closest_highest_price_candle, self.track_all_candles)
                                check_rsi_13_close_below = False
                                if find_previous_highest_rsi_13_candle:
                                    if closest_highest_price_candle.close < find_previous_highest_rsi_13_candle.close and closest_highest_price_candle.rsi_13 < 55 and find_previous_highest_rsi_13_candle.rsi_13 > 55 and self.current_candle.body < 0:
                                        check_rsi_13_close_below = True
                                        closest_highest_price_candle.check_rsi_13_close_below = True
                                if self.current_candle.close < closest_highest_price_candle.low or ((self.current_candle.rsi < previous_red_candle.rsi or check_rsi_13_close_below) and (closest_highest_price_candle.close != previous_red_candle.open or self.current_candle.close < closest_highest_price_candle.open) and self.current_candle.stoch_k < 80):
                                    converting_to_short = True
                                    if self.current_candle.body < 0 and self.current_candle.previous_body > 0 and self.current_candle.high > self.current_candle.previous_high and self.current_candle.close > self.current_candle.previous_low:
                                        converting_to_short = False

                            if converting_to_short:
                                closest_highest_price_candle.divergence_used = True
                                self.update_divergence_used_in_memory(closest_highest_price_candle)
                                self.short_divergence_candle = self.get_candle_by_index(closest_highest_price_candle.index)
                            self.add_divergence_info(False, False, converting_to_short, closest_highest_rsi_candle, closest_highest_price_candle, True , False, None, False, True )


        return converting_to_short, pre_condition_short

    def is_extreme_external_swing_bearish_divergence_triggered(self, upward_swing_current,  current_candle):


        highest_rsi_candle = None
        converting_to_short = False
        pre_condition_short = False

        if self.in_trade_candle:
            converting_to_short, pre_condition_short = self.is_bearish_divergence(self.in_trade_candle.index, self.current_candle.index)

        if self.latest_upward_swing_candle_from_10_leg and not pre_condition_short:
            converting_to_short, pre_condition_short = self.is_bearish_divergence(self.latest_upward_swing_candle_from_10_leg.start_index, self.current_candle.index)

        if upward_swing_current and not pre_condition_short:
            if upward_swing_current and self.save_upward_swing_previous:
                highest_rsi_candle = self.get_highest_rsi_candle_above_94_between_dates(self.save_upward_swing_previous.datetime , upward_swing_current.new_high_candle.datetime)

            save_upward_swing_previous_local = self.save_upward_swing_previous
            if self.save_upward_swing_previous:
                if self.save_upward_swing_previous.datetime == upward_swing_current.datetime and upward_swing_current.previous_swing_info:
                    save_upward_swing_previous_local = upward_swing_current.previous_swing_info

            if (highest_rsi_candle and save_upward_swing_previous_local
                    and upward_swing_current.datetime != save_upward_swing_previous_local.datetime
                    and upward_swing_current.new_high_candle.high > highest_rsi_candle.high
                    and upward_swing_current.new_high_candle.close > highest_rsi_candle.close
                    and upward_swing_current.new_high_candle.high > save_upward_swing_previous_local.new_high_candle.high
                    and upward_swing_current.new_high_candle.close > save_upward_swing_previous_local.new_high_candle.close):
                if highest_rsi_candle.rsi > upward_swing_current.new_high_candle.rsi and not upward_swing_current.new_high_candle.divergence_used:
                    highest_rsi_candle_in_upward_swing = self.get_highest_rsi_candle_between_dates(upward_swing_current.datetime, upward_swing_current.new_high_candle.datetime)
                    if highest_rsi_candle_in_upward_swing.close < upward_swing_current.new_high_candle.close:
                        highest_rsi_candle_in_upward_swing = upward_swing_current.new_high_candle
                    if highest_rsi_candle.rsi > highest_rsi_candle_in_upward_swing.rsi:
                        volume_condition = True #upward_swing_current.new_high_candle.body_volume < upward_swing_current.new_high_candle.previous_body_volume or upward_swing_current.new_high_candle.volume < upward_swing_current.new_high_candle.previous_volume
                        if volume_condition:
                            pre_condition_short = True
                            previous_red_candle = self.find_previous_red_candle(self.save_upward_swing_current.new_high_candle.index)
                            if current_candle.close < self.save_upward_swing_current.new_high_candle.low or (current_candle.rsi < previous_red_candle.rsi and self.save_upward_swing_current.new_high_candle.close != previous_red_candle.open):
                                self.add_candles_short_side = [candle for candle in self.track_all_candles_during_buy if candle.datetime >= upward_swing_current.new_high_candle.datetime]
                                converting_to_short = True
                                upward_swing_current.new_high_candle.divergence_used = True
                                self.short_divergence_candle = self.get_candle_by_index(self.save_upward_swing_current.new_high_candle.index)
                                self.update_divergence_used_in_memory(upward_swing_current.new_high_candle)
                        self.add_divergence_info(False, False, converting_to_short, highest_rsi_candle, highest_rsi_candle_in_upward_swing, True , False, upward_swing_current, False, True )



        return converting_to_short, pre_condition_short

    def is_extreme_internal_swing_bullish_divergence_triggered(self,  downward_swing_current, current_candle):

        converting_to_buy = False
        pre_condition_buy = False

        if self.in_trade_candle:
            converting_to_buy, pre_condition_buy = self.is_bullish_divergence(self.in_trade_candle.index, self.current_candle.index)

        if self.latest_downward_swing_candle_from_10_leg:
            converting_to_buy, pre_condition_buy = self.is_bullish_divergence(self.latest_downward_swing_candle_from_10_leg.start_index, current_candle.index)

        if downward_swing_current and not pre_condition_buy:
            lowest_rsi_candle_in_downward_swing = self.get_lowest_rsi_candle_below_5_between_dates(downward_swing_current.datetime, downward_swing_current.new_low_candle.datetime)
            if (lowest_rsi_candle_in_downward_swing and downward_swing_current.new_low_candle.rsi > lowest_rsi_candle_in_downward_swing.rsi
                    and downward_swing_current.new_low_candle.low < lowest_rsi_candle_in_downward_swing.low
                    and downward_swing_current.new_low_candle.close <= lowest_rsi_candle_in_downward_swing.low
                    and downward_swing_current.new_low_candle.close < lowest_rsi_candle_in_downward_swing.close and not downward_swing_current.new_low_candle.divergence_used):
                volume_condition = True #downward_swing_current.new_low_candle.body_volume < downward_swing_current.new_low_candle.body_volume or downward_swing_current.new_low_candle.volume < downward_swing_current.new_low_candle.volume
                if volume_condition:
                    pre_condition_buy = True
                    previous_green_candle = self.find_previous_green_candle(downward_swing_current.new_low_candle.index)
                    if (current_candle.close > downward_swing_current.new_low_candle.high
                        or (current_candle.rsi > previous_green_candle.rsi and downward_swing_current.new_low_candle.close != previous_green_candle.open)) \
                            or (self.current_candle.close > self.current_candle.previous_high and self.current_candle.rsi > self.current_candle.previous_rsi and  self.current_candle.rsi_13 > self.current_candle.previous_rsi_13 and  self.current_candle.stoch_k > self.current_candle.previous_stoch_k):
                        time_diff = abs(lowest_rsi_candle_in_downward_swing.datetime - downward_swing_current.new_low_candle.datetime)
                        if time_diff.total_seconds() > 2 * 60:
                            self.add_candles_buy_side = [candle for candle in self.track_all_candles_during_short if candle.datetime >= downward_swing_current.new_low_candle.datetime]
                            converting_to_buy = True
                            self.buy_divergence_candle = self.get_candle_by_index(downward_swing_current.new_low_candle.index)
                            downward_swing_current.new_low_candle.divergence_used = True
                            self.update_divergence_used_in_memory(downward_swing_current.new_low_candle)
                self.add_divergence_info(True, False, converting_to_buy, lowest_rsi_candle_in_downward_swing, downward_swing_current.new_low_candle, True , False, downward_swing_current, False, True )

        return converting_to_buy, pre_condition_buy

    def is_extreme_internal_swing_bearish_divergence_triggered(self,  upward_swing_current, current_candle):
        converting_to_short = False
        pre_condition_short = False


        if self.in_trade_candle:
            converting_to_short, pre_condition_short = self.is_bearish_divergence(self.in_trade_candle.index, self.current_candle.index)

        if self.latest_upward_swing_candle_from_10_leg:
            converting_to_short, pre_condition_short = self.is_bearish_divergence(self.latest_upward_swing_candle_from_10_leg.start_index, self.current_candle.index)

        if upward_swing_current and not pre_condition_short:
            highest_rsi_candle_in_upward_swing = self.get_highest_rsi_candle_above_94_between_dates(upward_swing_current.datetime, upward_swing_current.new_high_candle.datetime)
            if (highest_rsi_candle_in_upward_swing and upward_swing_current.new_high_candle.rsi < highest_rsi_candle_in_upward_swing.rsi
                    and upward_swing_current.new_high_candle.high > highest_rsi_candle_in_upward_swing.high
                    and upward_swing_current.new_high_candle.close >= highest_rsi_candle_in_upward_swing.high
                    and upward_swing_current.new_high_candle.close > highest_rsi_candle_in_upward_swing.close and not upward_swing_current.new_high_candle.divergence_used):
                volume_condition = True #upward_swing_current.new_high_candle.body_volume < upward_swing_current.new_high_candle.previous_body_volume or upward_swing_current.new_high_candle.volume < upward_swing_current.new_high_candle.body_volume
                if volume_condition:
                    pre_condition_short = True
                    previous_red_candle = self.find_previous_red_candle(upward_swing_current.new_high_candle.index)
                    if current_candle.close < upward_swing_current.new_high_candle.low or (current_candle.rsi < previous_red_candle.rsi and upward_swing_current.new_high_candle.close != previous_red_candle.open):
                        time_diff = abs(highest_rsi_candle_in_upward_swing.datetime - upward_swing_current.new_high_candle.datetime)
                        if time_diff.total_seconds() > 2 * 60:
                            self.add_candles_short_side = [candle for candle in self.track_all_candles_during_buy if candle.datetime >= upward_swing_current.new_high_candle.datetime]
                            converting_to_short = True
                            upward_swing_current.new_high_candle.divergence_used = True
                            self.update_divergence_used_in_memory(upward_swing_current.new_high_candle)
                            self.short_divergence_candle = self.get_candle_by_index(upward_swing_current.new_high_candle.index)
                self.add_divergence_info(False, False, converting_to_short, highest_rsi_candle_in_upward_swing, upward_swing_current.new_high_candle, True , False, upward_swing_current, False, True )

        return converting_to_short, pre_condition_short

    def update_converting_to_short(self, divergence_start_candle, divergence_end_candle):

        if self.in_trade_candle:
            trade_type = 'BUY'
            profit_loss =  self.in_trade_candle.open - self.current_candle.close
            #self.update_conditions_with_profit_loss(self.in_trade_candle.index, self.current_candle.index, profit_loss * 50, trade_type)

        if self.save_upward_swing_current:
            self.add_candles_short_side = [candle for candle in self.track_all_candles if candle.datetime >= self.save_upward_swing_current.new_high_candle.datetime]
        else:
            self.add_candles_short_side = self.track_all_candles_during_buy.copy()

        if self.save_downward_swing_previous and self.save_downward_swing_current and self.save_downward_swing_previous.datetime != self.save_downward_swing_current.datetime:
            #self.save_downward_swing_current.previous_swing_info = self.save_downward_swing_previous
            self.save_downward_swing_previous = copy.deepcopy(self.save_downward_swing_current)
        if self.save_downward_swing_current and not self.save_downward_swing_previous:
            self.save_downward_swing_previous = copy.deepcopy(self.save_downward_swing_current)
        self.save_downward_swing_current = None

        if self.save_upward_swing_previous and self.save_upward_swing_current and self.save_upward_swing_previous.datetime != self.save_upward_swing_current.datetime:
            #self.save_upward_swing_current.previous_swing_info = self.save_upward_swing_previous
            self.save_upward_swing_previous = copy.deepcopy(self.save_upward_swing_current)
        if self.save_upward_swing_current and not self.save_upward_swing_previous:
            self.save_upward_swing_previous = copy.deepcopy(self.save_upward_swing_current)
        self.save_upward_swing_current = None

        self.add_candles_short_side.append(self.current_candle)
        self.short_triggered_candle_two = None
        self.buy_triggered_candle_two = None
        self.manual_buy_short_trigger_candle = None
        self.copy_data = True
        if self.in_trade_candle:
            self.in_trade_candle.divergence_start_candle = None
            self.in_trade_candle.divergence_end_candle = None
        self.in_trade_candle = self.current_candle
        self.in_trade_candle.divergence_start_candle = divergence_start_candle
        self.in_trade_candle.divergence_end_candle = divergence_end_candle
        self.first_high_rsi_candle_during_buy = None

        self.buy_divergence_candle = None

        self.in_memory_short_divergence_candle = None
        self.in_memory_buy_divergence_candle = None
        self.in_memory_divergence_info = None
        self.trend_is_down_check_for_rsi_13_above_55_for_buy = False
        self.first_red_candle_condition_statisfied = None

        if self.second_high_rsi_candle_during_buy:
            self.first_high_rsi_candle_during_buy = self.second_high_rsi_candle_during_buy
            self.second_high_rsi_candle_during_buy = None

    def update_converting_to_buy(self, divergence_start_candle, divergence_end_candle):

        if self.in_trade_candle:
            trade_type = 'SHORT'
            profit_loss =  self.in_trade_candle.open - self.current_candle.close
            #self.update_conditions_with_profit_loss(self.in_trade_candle.index, self.current_candle.index, profit_loss * 50, trade_type)

        if self.save_downward_swing_current:
            self.add_candles_buy_side = [candle for candle in self.track_all_candles if candle.datetime >= self.save_downward_swing_current.new_low_candle.datetime]
        else:
            self.add_candles_buy_side = self.track_all_candles_during_short.copy()


        if self.save_downward_swing_previous and self.save_downward_swing_current and self.save_downward_swing_previous.datetime != self.save_downward_swing_current.datetime:
            #self.save_downward_swing_current.previous_swing_info = self.save_downward_swing_previous
            self.save_downward_swing_previous = copy.deepcopy(self.save_downward_swing_current)
        if self.save_downward_swing_current and not self.save_downward_swing_previous:
            self.save_downward_swing_previous = copy.deepcopy(self.save_downward_swing_current)
        self.save_downward_swing_current = None

        if self.save_upward_swing_previous and self.save_upward_swing_current and self.save_upward_swing_previous.datetime != self.save_upward_swing_current.datetime:
            #self.save_upward_swing_current.previous_swing_info = self.save_upward_swing_previous
            self.save_upward_swing_previous = copy.deepcopy(self.save_upward_swing_current)
        if self.save_upward_swing_current and not self.save_upward_swing_previous:
            self.save_upward_swing_previous = copy.deepcopy(self.save_upward_swing_current)
        self.save_upward_swing_current = None

        self.add_candles_buy_side.append(self.current_candle)
        self.buy_triggered_candle_two = None
        self.short_triggered_candle_two = None
        self.manual_buy_short_trigger_candle = None
        self.copy_data = True
        if self.in_trade_candle:
            self.in_trade_candle.divergence_start_candle = None
            self.in_trade_candle.divergence_end_candle = None
        self.in_trade_candle = self.current_candle
        self.in_trade_candle.divergence_start_candle = divergence_start_candle
        self.in_trade_candle.divergence_end_candle = divergence_end_candle

        self.short_divergence_candle = None
        self.in_memory_short_divergence_candle = None
        self.in_memory_buy_divergence_candle = None
        self.in_memory_divergence_info = None
        self.first_low_rsi_candle_during_short = None
        self.trend_is_down_check_for_rsi_13_above_55_for_buy = False
        self.first_red_candle_condition_statisfied = None

        if self.second_low_rsi_candle_during_short:
            self.first_low_rsi_candle_during_short = self.second_low_rsi_candle_during_short
            self.second_low_rsi_candle_during_short = None

    def log_condition(self, condition_name: str, condition_reason: str, condition_time: datetime = None):
        condition_time = condition_time or datetime.now()
        entry = {
            "timestamp": condition_time.strftime('%Y-%m-%d %H:%M:%S'),
            "condition_name": condition_name,
            "condition_reason": condition_reason
        }
        all_conditions_store.append(entry)

    def update_conditions_with_profit_loss(self, start_time: datetime, end_time: datetime, profit_loss: float, trade_type: str):
        for condition in all_conditions_store:
            condition_time = datetime.strptime(condition["timestamp"], '%Y-%m-%d %H:%M:%S')
            if start_time <= condition_time <= end_time:
                condition["trade_type"] = trade_type.upper()  # store as "BUY" or "SELL"
                condition["profit_loss"] = profit_loss

    def update_divergence_used_in_memory(self, update_candle):
        for candle in self.track_all_candles:
            if candle.datetime == update_candle.datetime:
                candle.divergence_used = True

    def update_divergence_used_in_memory_to_false(self, update_candle):
        for candle in self.track_all_candles:
            if candle.datetime == update_candle.datetime:
                candle.divergence_used = False

    def check_is_converting_to_short_valid(self, converting_to_short, pre_condition_buy, pre_condition_short):
        return converting_to_short

    def check_is_converting_to_buy_valid(self, converting_to_buy, pre_condition_short, pre_condition_buy):
        return converting_to_buy

    def add_or_update_swing(self, swing_datetime, swing_data):
        swing_info = None

        if swing_data.is_new_low:
            swing_info = SwingInfo(
                start_index=swing_data.index,
                end_index=swing_data.new_low_candle.index,
                swing_high_price=swing_data.high,
                swing_low_price=swing_data.new_low_candle.low,
                swing_high_close=swing_data.close,
                swing_low_close=swing_data.new_low_candle.close,
                swing_high_rsi=swing_data.rsi,
                swing_low_rsi=swing_data.new_low_candle.rsi,
                swing_type=-1  # Downward Swing
            )

        if swing_data.is_new_high:
            swing_info = SwingInfo(
                start_index=swing_data.index,
                end_index=swing_data.new_high_candle.index,
                swing_high_price=swing_data.new_high_candle.high,
                swing_low_price=swing_data.low,
                swing_high_close=swing_data.new_high_candle.close,
                swing_low_close=swing_data.close,
                swing_high_rsi=swing_data.new_high_candle.rsi,
                swing_low_rsi=swing_data.rsi,
                swing_type=1  # Upward Swing
            )

        if swing_info:
            self.swing_collection[swing_datetime] = swing_info  # Store swing_info, not swing_data

    def merge_swings_with_overlap(self):
        """ Merge all swings that overlap and have the same type """
        if not self.swing_collection:
            return {}

        # Sort swings by datetime
        sorted_swings = sorted(self.swing_collection.items(), key=lambda x: x[0])
        merged_swings = []

        # Start with the first swing
        prev_datetime, prev_swing = sorted_swings[0]

        for curr_datetime, curr_swing in sorted_swings[1:]:
            # Check if swings have the same type and overlap
            if prev_swing.swing_type == curr_swing.swing_type and prev_swing.end_index >= curr_swing.start_index:
                # Merge swings by updating end index and relevant values
                prev_swing.end_index = max(prev_swing.end_index, curr_swing.end_index)
                prev_swing.swing_high_price = max(prev_swing.swing_high_price, curr_swing.swing_high_price)
                prev_swing.swing_low_price = min(prev_swing.swing_low_price, curr_swing.swing_low_price)
                prev_swing.swing_high_close = max(prev_swing.swing_high_close, curr_swing.swing_high_close)
                prev_swing.swing_low_close = min(prev_swing.swing_low_close, curr_swing.swing_low_close)
                prev_swing.swing_high_rsi = max(prev_swing.swing_high_rsi, curr_swing.swing_high_rsi)
                prev_swing.swing_low_rsi = min(prev_swing.swing_low_rsi, curr_swing.swing_low_rsi)
            else:
                # Store the non-overlapping swing and move forward
                merged_swings.append((prev_datetime, prev_swing))
                prev_datetime, prev_swing = curr_datetime, curr_swing

        # Add the last processed swing
        merged_swings.append((prev_datetime, prev_swing))

        return dict(merged_swings)

    def remove_contained_swings(self, swings_dict):
        """ Remove swings that are completely contained within another swing """
        sorted_swings = sorted(swings_dict.items(), key=lambda x: x[0])
        filtered_swings = []

        for i in range(len(sorted_swings)):
            curr_datetime, curr_swing = sorted_swings[i]
            is_contained = False

            for j in range(len(sorted_swings)):
                if i != j:  # Don't compare a swing with itself
                    _, other_swing = sorted_swings[j]

                    # Check if curr_swing is fully inside other_swing
                    if (curr_swing.swing_type == other_swing.swing_type and
                            curr_swing.start_index >= other_swing.start_index and
                            curr_swing.end_index <= other_swing.end_index):
                        is_contained = True
                        break  # No need to check further

            if not is_contained:
                filtered_swings.append((curr_datetime, curr_swing))

        return dict(filtered_swings)

    def merge_and_clean_swings(self):
        """ Main method to merge overlapping swings and remove contained ones """
        merged_swings = self.merge_swings_with_overlap()
        cleaned_swings = self.remove_contained_swings(merged_swings)
        return cleaned_swings

    def check_short_divergence_during_buy(self):
        converting_to_short = False
        pre_condition_short = False

        # Divergence between two swing
        if not converting_to_short:
            converting_to_short, pre_condition_short = self.is_extreme_external_swing_bearish_divergence_triggered(self.save_upward_swing_current, self.current_candle)

        # Divergence with same swing
        if not converting_to_short and not pre_condition_short:
            converting_to_short, pre_condition_short = self.is_extreme_internal_swing_bearish_divergence_triggered(self.save_upward_swing_current, self.current_candle)

        # Non Extreme Internal Divergence same swing.
        if not converting_to_short and not pre_condition_short:
            converting_to_short, pre_condition_short = self.is_non_extreme_internal_bearish_divergence(self.save_upward_swing_current, self.current_candle)


        if not pre_condition_short and self.save_upward_swing_current and self.save_upward_swing_previous:
            if self.save_upward_swing_previous.new_high_candle.close > self.save_upward_swing_current.new_high_candle.close and self.save_upward_swing_previous.new_high_candle.body > 0 and self.save_upward_swing_current.new_high_candle.body > 0:
                if self.save_upward_swing_previous.new_high_candle.high > self.save_upward_swing_current.new_high_candle.high:
                    if not self.save_upward_swing_current.new_high_candle.divergence_used:
                        if self.save_upward_swing_current.new_high_candle.rsi > self.save_upward_swing_previous.new_high_candle.rsi:
                            if self.save_upward_swing_current.new_high_candle.stoch_k < self.save_upward_swing_previous.new_high_candle.stoch_k or self.save_upward_swing_current.new_high_candle.stoch_d < self.save_upward_swing_previous.new_high_candle.stoch_d:
                                pre_condition_short = True
                                previous_red_candle = self.find_previous_red_candle(self.save_upward_swing_current.new_high_candle.index)
                                if (self.current_candle.close < self.save_upward_swing_current.new_high_candle.close and self.current_candle.close <= self.save_upward_swing_current.new_high_candle.low) or (self.current_candle.rsi < previous_red_candle.rsi and self.save_upward_swing_current.new_high_candle.close != previous_red_candle.open):
                                    converting_to_short = True
                                    self.save_upward_swing_current.new_high_candle.divergence_used = True
                                    self.update_divergence_used_in_memory(self.save_upward_swing_current.new_high_candle)
                                    self.short_divergence_candle = self.get_candle_by_index(self.save_upward_swing_current.new_high_candle.index)
                                self.add_divergence_info(False, False, converting_to_short, self.save_upward_swing_previous.new_high_candle, self.save_upward_swing_current.new_high_candle, False , False, self.save_upward_swing_previous, False, True )

        if not pre_condition_short and self.save_upward_swing_current and self.save_upward_swing_previous:
            if self.save_upward_swing_previous.new_high_candle.close < self.save_upward_swing_current.new_high_candle.close and self.save_upward_swing_previous.new_high_candle.body > 0 and self.save_upward_swing_current.new_high_candle.body > 0:
                if self.save_upward_swing_previous.new_high_candle.high < self.save_upward_swing_current.new_high_candle.high:
                    if not self.save_upward_swing_current.new_high_candle.divergence_used:
                        if self.save_upward_swing_current.new_high_candle.rsi > self.save_upward_swing_previous.new_high_candle.rsi:
                            if self.save_upward_swing_current.new_high_candle.stoch_k < self.save_upward_swing_previous.new_high_candle.stoch_k or self.save_upward_swing_current.new_high_candle.stoch_d < self.save_upward_swing_previous.new_high_candle.stoch_d:
                                pre_condition_short = True
                                previous_red_candle = self.find_previous_red_candle(self.save_upward_swing_current.new_high_candle.index)
                                if (self.current_candle.close < self.save_upward_swing_current.new_high_candle.close and self.current_candle.close <= self.save_upward_swing_current.new_high_candle.low) or (self.current_candle.rsi < previous_red_candle.rsi and self.save_upward_swing_current.new_high_candle.close != previous_red_candle.open):
                                    converting_to_short = True
                                    self.save_upward_swing_current.new_high_candle.divergence_used = True
                                    self.update_divergence_used_in_memory(self.save_upward_swing_current.new_high_candle)
                                    self.short_divergence_candle = self.get_candle_by_index(self.save_upward_swing_current.new_high_candle.index)
                                self.add_divergence_info(False, False, converting_to_short, self.save_upward_swing_previous.new_high_candle, self.save_upward_swing_current.new_high_candle, False , False, self.save_upward_swing_previous, False, True )

        if not pre_condition_short and self.save_upward_swing_current and self.save_upward_swing_previous:
            if self.save_upward_swing_previous.new_high_candle.close < self.save_upward_swing_current.new_high_candle.close and self.save_upward_swing_previous.new_high_candle.body > 0 and self.save_upward_swing_current.new_high_candle.body > 0:
                if self.save_upward_swing_previous.new_high_candle.high < self.save_upward_swing_current.new_high_candle.high:
                    if not self.save_upward_swing_current.new_high_candle.divergence_used:
                        if self.save_upward_swing_current.new_high_candle.rsi < self.save_upward_swing_previous.new_high_candle.rsi:
                            pre_condition_short = True
                            previous_red_candle = self.find_previous_red_candle(self.save_upward_swing_current.new_high_candle.index)
                            if (self.current_candle.close < self.save_upward_swing_current.new_high_candle.close and self.current_candle.close <= self.save_upward_swing_current.new_high_candle.low) or (self.current_candle.rsi < previous_red_candle.rsi and self.save_upward_swing_current.new_high_candle.close != previous_red_candle.open):
                                converting_to_short = True
                                self.save_upward_swing_current.new_high_candle.divergence_used = True
                                self.short_divergence_candle = self.get_candle_by_index(self.save_upward_swing_current.new_high_candle.index)
                                self.update_divergence_used_in_memory(self.save_upward_swing_current.new_high_candle)
                            self.add_divergence_info(False, False, converting_to_short, self.save_upward_swing_previous.new_high_candle, self.save_upward_swing_current.new_high_candle, False , False, self.save_upward_swing_previous, False, True )

        if not pre_condition_short and self.save_upward_swing_current and self.save_upward_swing_previous:
            if self.save_upward_swing_previous.new_high_candle.close > self.save_upward_swing_current.new_high_candle.close and self.save_upward_swing_previous.new_high_candle.body > 0 and self.save_upward_swing_current.new_high_candle.body > 0:
                if self.save_upward_swing_previous.new_high_candle.high > self.save_upward_swing_current.new_high_candle.high:
                    if not self.save_upward_swing_current.new_high_candle.divergence_used:
                        if self.save_upward_swing_current.new_high_candle.rsi_13 > self.save_upward_swing_previous.new_high_candle.rsi_13:
                            if self.save_upward_swing_current.new_high_candle.stoch_k < self.save_upward_swing_previous.new_high_candle.stoch_k or self.save_upward_swing_current.new_high_candle.stoch_d < self.save_upward_swing_previous.new_high_candle.stoch_d:
                                pre_condition_short = True
                                previous_red_candle = self.find_previous_red_candle(self.save_upward_swing_current.new_high_candle.index)
                                if (self.current_candle.close < self.save_upward_swing_current.new_high_candle.close and self.current_candle.close <= self.save_upward_swing_current.new_high_candle.low) or (self.current_candle.rsi < previous_red_candle.rsi and self.save_upward_swing_current.new_high_candle.close != previous_red_candle.open):
                                    converting_to_short = True
                                    self.save_upward_swing_current.new_high_candle.divergence_used = True
                                    self.update_divergence_used_in_memory(self.save_upward_swing_current.new_high_candle)
                                    self.short_divergence_candle = self.get_candle_by_index(self.save_upward_swing_current.new_high_candle.index)
                                self.add_divergence_info(False, False, converting_to_short, self.save_upward_swing_previous.new_high_candle, self.save_upward_swing_current.new_high_candle, False , True, self.save_upward_swing_previous, False, True )

        if not pre_condition_short and self.save_upward_swing_current and self.save_upward_swing_previous:
            if self.save_upward_swing_previous.new_high_candle.close < self.save_upward_swing_current.new_high_candle.close and self.save_upward_swing_previous.new_high_candle.body > 0 and self.save_upward_swing_current.new_high_candle.body > 0:
                if self.save_upward_swing_previous.new_high_candle.high < self.save_upward_swing_current.new_high_candle.high:
                    if not self.save_upward_swing_current.new_high_candle.divergence_used:
                        if self.save_upward_swing_current.new_high_candle.rsi_13 < self.save_upward_swing_previous.new_high_candle.rsi_13:
                            pre_condition_short = True
                            previous_red_candle = self.find_previous_red_candle(self.save_upward_swing_current.new_high_candle.index)
                            if (self.current_candle.close < self.save_upward_swing_current.new_high_candle.close and self.current_candle.close <= self.save_upward_swing_current.new_high_candle.low) or (self.current_candle.rsi < previous_red_candle.rsi and self.save_upward_swing_current.new_high_candle.close != previous_red_candle.open):
                                converting_to_short = True
                                self.save_upward_swing_current.new_high_candle.divergence_used = True
                                self.short_divergence_candle = self.get_candle_by_index(self.save_upward_swing_current.new_high_candle.index)
                                self.update_divergence_used_in_memory(self.save_upward_swing_current.new_high_candle)
                            self.add_divergence_info(False, False, converting_to_short, self.save_upward_swing_previous.new_high_candle, self.save_upward_swing_current.new_high_candle, False , True, self.save_upward_swing_previous, False, True )

        if not converting_to_short and not pre_condition_short:
            converting_to_short, pre_condition_short = self.is_non_extreme_internal_bearish_divergence_only_pre_condition(self.save_upward_swing_current, self.current_candle)

        return converting_to_short, pre_condition_short

    def check_buy_divergence_during_buy(self):

        pre_condition_buy = False
        converting_to_buy = False
        if self.save_downward_swing_previous and self.in_trade_candle and self.current_candle.close > self.save_downward_swing_previous.new_low_candle.low:
            if self.current_candle.close < self.save_downward_swing_previous.new_low_candle.close and self.current_candle.low < self.save_downward_swing_previous.new_low_candle.low:
                self.save_downward_swing_previous.new_low_candle = self.current_candle
            if self.save_downward_swing_previous.new_low_candle.datetime > self.in_trade_candle.datetime:
                converting_to_buy, pre_condition_buy = self.is_non_extreme_internal_bullish_divergence_only_pre_condition(self.save_downward_swing_previous, self.current_candle)


        if self.save_downward_swing_current and not pre_condition_buy:
            if self.current_candle.close < self.save_downward_swing_current.new_low_candle.close and self.current_candle.low < self.save_downward_swing_current.new_low_candle.low:
                self.save_downward_swing_current.new_low_candle = self.current_candle
                converting_to_buy, pre_condition_buy = self.is_non_extreme_internal_bullish_divergence_only_pre_condition(self.save_downward_swing_current, self.current_candle)


        if not pre_condition_buy and self.save_downward_swing_previous and self.save_downward_swing_current:
            if self.save_downward_swing_previous.new_low_candle.close < self.save_downward_swing_current.new_low_candle.close:
                if self.save_downward_swing_previous.new_low_candle.low < self.save_downward_swing_current.new_low_candle.low:
                    if self.save_downward_swing_current.new_low_candle.rsi < self.save_downward_swing_previous.new_low_candle.rsi:
                        if  self.save_downward_swing_current.new_low_candle.stoch_k > self.save_downward_swing_previous.new_low_candle.stoch_k or self.save_downward_swing_current.new_low_candle.stoch_d > self.save_downward_swing_previous.new_low_candle.stoch_d:
                            pre_condition_buy = True
                            self.add_divergence_info(True, pre_condition_buy, False, self.save_downward_swing_previous.new_low_candle, self.save_downward_swing_current.new_low_candle, False , False, self.save_downward_swing_previous, True, False )

        if not pre_condition_buy and self.save_downward_swing_previous and self.save_downward_swing_current:
            if self.save_downward_swing_previous.new_low_candle.close < self.save_downward_swing_current.new_low_candle.close:
                if self.save_downward_swing_previous.new_low_candle.low < self.save_downward_swing_current.new_low_candle.low:
                    if self.save_downward_swing_current.new_low_candle.rsi_13 < self.save_downward_swing_previous.new_low_candle.rsi_13:
                        if  self.save_downward_swing_current.new_low_candle.stoch_k > self.save_downward_swing_previous.new_low_candle.stoch_k or self.save_downward_swing_current.new_low_candle.stoch_d > self.save_downward_swing_previous.new_low_candle.stoch_d:
                            pre_condition_buy = True
                            self.add_divergence_info(True, pre_condition_buy, False, self.save_downward_swing_previous.new_low_candle, self.save_downward_swing_current.new_low_candle, False , True, self.save_downward_swing_previous, True, False )

        if not pre_condition_buy:
            converting_to_buy, pre_condition_buy = self.is_non_extreme_internal_bullish_divergence_only_pre_condition(None, self.current_candle)

        return converting_to_buy, pre_condition_buy

    def check_short_divergence_during_short(self):
        converting_to_short = False
        pre_condition_short = False
        if self.save_upward_swing_previous and self.in_trade_candle:
            if self.current_candle.close > self.save_upward_swing_previous.new_high_candle.close and self.current_candle.high > self.save_upward_swing_previous.new_high_candle.high:
                self.save_upward_swing_previous.new_high_candle = self.current_candle
            if self.save_upward_swing_previous.new_high_candle.datetime > self.in_trade_candle.datetime:
                if not pre_condition_short:
                    converting_to_short, pre_condition_short = self.is_non_extreme_internal_bearish_divergence_only_pre_condition(self.save_upward_swing_previous, self.current_candle)


        if self.save_upward_swing_current and not pre_condition_short:
            if self.current_candle.close > self.save_upward_swing_current.new_high_candle.close and self.current_candle.high > self.save_upward_swing_current.new_high_candle.high:
                self.save_upward_swing_current.new_high_candle = self.current_candle
            if not pre_condition_short:
                converting_to_short, pre_condition_short = self.is_non_extreme_internal_bearish_divergence_only_pre_condition(self.save_upward_swing_current, self.current_candle)


        if not pre_condition_short and self.save_upward_swing_previous and self.save_upward_swing_current:
            if self.save_upward_swing_previous.new_high_candle.close > self.save_upward_swing_current.new_high_candle.close:
                if self.save_upward_swing_previous.new_high_candle.high > self.save_upward_swing_current.new_high_candle.high:
                    if self.save_upward_swing_current.new_high_candle.rsi > self.save_upward_swing_previous.new_high_candle.rsi:
                        if self.save_upward_swing_current.new_high_candle.stoch_k < self.save_upward_swing_previous.new_high_candle.stoch_k or self.save_upward_swing_current.new_high_candle.stoch_d < self.save_upward_swing_previous.new_high_candle.stoch_d:
                            pre_condition_short = True
                            self.add_divergence_info(False, pre_condition_short, False, self.save_upward_swing_previous.new_high_candle, self.save_upward_swing_current.new_high_candle, False , True, self.save_upward_swing_previous, True,  False )

        if not pre_condition_short and self.save_upward_swing_previous and self.save_upward_swing_current:
            if self.save_upward_swing_previous.new_high_candle.close > self.save_upward_swing_current.new_high_candle.close:
                if self.save_upward_swing_previous.new_high_candle.high > self.save_upward_swing_current.new_high_candle.high:
                    if self.save_upward_swing_current.new_high_candle.rsi_13 > self.save_upward_swing_previous.new_high_candle.rsi_13:
                        if  self.save_upward_swing_current.new_high_candle.stoch_k < self.save_upward_swing_previous.new_high_candle.stoch_k or self.save_upward_swing_current.new_high_candle.stoch_d < self.save_upward_swing_previous.new_high_candle.stoch_d:
                            pre_condition_short = True
                            self.add_divergence_info(False, pre_condition_short, False, self.save_upward_swing_previous.new_high_candle, self.save_upward_swing_current.new_high_candle, False , True, self.save_upward_swing_previous, True, False )

        if not pre_condition_short:
            converting_to_short, pre_condition_short = self.is_non_extreme_internal_bearish_divergence_only_pre_condition(None, self.current_candle)


        return converting_to_short, pre_condition_short

    def check_buy_divergence_during_short(self):

        pre_condition_buy = False
        converting_to_buy = False
        # Divergence with external swing
        if not converting_to_buy and self.save_downward_swing_previous:
            converting_to_buy, pre_condition_buy = self.is_extreme_external_swing_bullish_divergence_triggered(self.save_downward_swing_current, self.current_candle)

        # Divergence with same swing
        if not converting_to_buy and not pre_condition_buy:
            converting_to_buy, pre_condition_buy = self.is_extreme_internal_swing_bullish_divergence_triggered(self.save_downward_swing_current, self.current_candle)

        # Divergence with non extereme internal swing
        if not converting_to_buy and not pre_condition_buy:
            converting_to_buy, pre_condition_buy = self.is_non_extreme_internal_bullish_divergence(self.save_downward_swing_current, self.current_candle)


        if not pre_condition_buy and not pre_condition_buy and self.save_downward_swing_current and self.save_downward_swing_previous:
            if self.save_downward_swing_previous.new_low_candle.close < self.save_downward_swing_current.new_low_candle.close:
                if self.save_downward_swing_previous.new_low_candle.low < self.save_downward_swing_current.new_low_candle.low:
                    if not self.save_downward_swing_current.new_low_candle.divergence_used:
                        if self.save_downward_swing_current.new_low_candle.rsi < self.save_downward_swing_previous.new_low_candle.rsi:
                            if self.save_downward_swing_current.new_low_candle.stoch_k > self.save_downward_swing_previous.new_low_candle.stoch_k or self.save_downward_swing_current.new_low_candle.stoch_d > self.save_downward_swing_previous.new_low_candle.stoch_d:
                                pre_condition_buy = True
                                previous_green_candle = self.find_previous_green_candle(self.save_downward_swing_current.new_low_candle.index)
                                if ((self.current_candle.close > self.save_downward_swing_current.new_low_candle.close and self.current_candle.close >= self.save_downward_swing_current.new_low_candle.high)
                                    or (self.current_candle.rsi > previous_green_candle.rsi and self.save_downward_swing_current.new_low_candle.close != previous_green_candle.open)) \
                                        or (self.current_candle.close > self.current_candle.previous_high and self.current_candle.rsi > self.current_candle.previous_rsi and  self.current_candle.rsi_13 > self.current_candle.previous_rsi_13 and  self.current_candle.stoch_k > self.current_candle.previous_stoch_k):
                                    converting_to_buy = True
                                    self.save_downward_swing_current.new_low_candle.divergence_used = True
                                    self.buy_divergence_candle = self.get_candle_by_index(self.save_downward_swing_current.new_low_candle.index)
                                    self.update_divergence_used_in_memory(self.save_downward_swing_current.new_low_candle)
                                self.add_divergence_info(True, False, converting_to_buy, self.save_downward_swing_previous.new_low_candle, self.save_downward_swing_current.new_low_candle, False , False, self.save_downward_swing_previous, False, True )

        if not pre_condition_buy and not pre_condition_buy and self.save_downward_swing_current and self.save_downward_swing_previous:
            if self.save_downward_swing_previous.new_low_candle.close > self.save_downward_swing_current.new_low_candle.close:
                if self.save_downward_swing_previous.new_low_candle.low > self.save_downward_swing_current.new_low_candle.low:
                    if not self.save_downward_swing_current.new_low_candle.divergence_used:
                        if self.save_downward_swing_current.new_low_candle.rsi < self.save_downward_swing_previous.new_low_candle.rsi:
                            if self.save_downward_swing_current.new_low_candle.stoch_k > self.save_downward_swing_previous.new_low_candle.stoch_k or self.save_downward_swing_current.new_low_candle.stoch_d > self.save_downward_swing_previous.new_low_candle.stoch_d:
                                pre_condition_buy = True
                                previous_green_candle = self.find_previous_green_candle(self.save_downward_swing_current.new_low_candle.index)
                                if ((self.current_candle.close > self.save_downward_swing_current.new_low_candle.close and self.current_candle.close >= self.save_downward_swing_current.new_low_candle.high)
                                    or (self.current_candle.rsi > previous_green_candle.rsi and self.save_downward_swing_current.new_low_candle.close != previous_green_candle.open)) \
                                        or (self.current_candle.close > self.current_candle.previous_high and self.current_candle.rsi > self.current_candle.previous_rsi and  self.current_candle.rsi_13 > self.current_candle.previous_rsi_13 and  self.current_candle.stoch_k > self.current_candle.previous_stoch_k):
                                    converting_to_buy = True
                                    self.save_downward_swing_current.new_low_candle.divergence_used = True
                                    self.buy_divergence_candle = self.get_candle_by_index(self.save_downward_swing_current.new_low_candle.index)
                                    self.update_divergence_used_in_memory(self.save_downward_swing_current.new_low_candle)
                                self.add_divergence_info(True, False, converting_to_buy, self.save_downward_swing_previous.new_low_candle, self.save_downward_swing_current.new_low_candle, False , False, self.save_downward_swing_previous, False, True )

        if not pre_condition_buy and not pre_condition_buy and self.save_downward_swing_current and self.save_downward_swing_previous:
            if self.save_downward_swing_previous.new_low_candle.close > self.save_downward_swing_current.new_low_candle.close:
                if self.save_downward_swing_previous.new_low_candle.low > self.save_downward_swing_current.new_low_candle.low:
                    if not self.save_downward_swing_current.new_low_candle.divergence_used and not self.save_downward_swing_previous.new_low_candle.divergence_used:
                        if self.save_downward_swing_current.new_low_candle.rsi > self.save_downward_swing_previous.new_low_candle.rsi:
                            pre_condition_buy = True
                            previous_green_candle = self.find_previous_green_candle(self.save_downward_swing_current.new_low_candle.index)
                            if ((self.current_candle.close > self.save_downward_swing_current.new_low_candle.close and self.current_candle.close >= self.save_downward_swing_current.new_low_candle.high)
                                or (self.current_candle.rsi > previous_green_candle.rsi and self.save_downward_swing_current.new_low_candle.close != previous_green_candle.open)) \
                                    or (self.current_candle.close > self.current_candle.previous_high and self.current_candle.rsi > self.current_candle.previous_rsi and  self.current_candle.rsi_13 > self.current_candle.previous_rsi_13 and  self.current_candle.stoch_k > self.current_candle.previous_stoch_k):
                                converting_to_buy = True
                                self.save_downward_swing_current.new_low_candle.divergence_used = True
                                self.update_divergence_used_in_memory(self.save_downward_swing_current.new_low_candle)
                                self.buy_divergence_candle = self.get_candle_by_index(self.save_downward_swing_current.new_low_candle.index)
                            self.add_divergence_info(True, False, converting_to_buy, self.save_downward_swing_previous.new_low_candle, self.save_downward_swing_current.new_low_candle, False , False, self.save_downward_swing_previous, False, True )

        if not pre_condition_buy and not pre_condition_buy and self.save_downward_swing_current and self.save_downward_swing_previous:
            if self.save_downward_swing_previous.new_low_candle.close < self.save_downward_swing_current.new_low_candle.close:
                if self.save_downward_swing_previous.new_low_candle.low < self.save_downward_swing_current.new_low_candle.low:
                    if not self.save_downward_swing_current.new_low_candle.divergence_used:
                        if self.save_downward_swing_current.new_low_candle.rsi_13 < self.save_downward_swing_previous.new_low_candle.rsi_13:
                            if self.save_downward_swing_current.new_low_candle.stoch_k > self.save_downward_swing_previous.new_low_candle.stoch_k or self.save_downward_swing_current.new_low_candle.stoch_d > self.save_downward_swing_previous.new_low_candle.stoch_d:
                                pre_condition_buy = True
                                previous_green_candle = self.find_previous_green_candle(self.save_downward_swing_current.new_low_candle.index)
                                if ((self.current_candle.close > self.save_downward_swing_current.new_low_candle.close and self.current_candle.close >= self.save_downward_swing_current.new_low_candle.high)
                                    or (self.current_candle.rsi > previous_green_candle.rsi and self.save_downward_swing_current.new_low_candle.close != previous_green_candle.open)) \
                                        or (self.current_candle.close > self.current_candle.previous_high and self.current_candle.rsi > self.current_candle.previous_rsi and  self.current_candle.rsi_13 > self.current_candle.previous_rsi_13 and  self.current_candle.stoch_k > self.current_candle.previous_stoch_k):
                                    converting_to_buy = True
                                    self.save_downward_swing_current.new_low_candle.divergence_used = True
                                    self.update_divergence_used_in_memory(self.save_downward_swing_current.new_low_candle)
                                    self.buy_divergence_candle = self.get_candle_by_index(self.save_downward_swing_current.new_low_candle.index)
                                self.add_divergence_info(True, False, converting_to_buy, self.save_downward_swing_previous.new_low_candle, self.save_downward_swing_current.new_low_candle, False , True, self.save_downward_swing_current, False, True )

        if not pre_condition_buy and not pre_condition_buy and self.save_downward_swing_current and self.save_downward_swing_previous:
            if self.save_downward_swing_previous.new_low_candle.close > self.save_downward_swing_current.new_low_candle.close:
                if self.save_downward_swing_previous.new_low_candle.low > self.save_downward_swing_current.new_low_candle.low:
                    if not self.save_downward_swing_current.new_low_candle.divergence_used:
                        if self.save_downward_swing_current.new_low_candle.rsi_13 > self.save_downward_swing_previous.new_low_candle.rsi_13:
                            pre_condition_buy = True
                            previous_green_candle = self.find_previous_green_candle(self.save_downward_swing_current.new_low_candle.index)
                            if ((self.current_candle.close > self.save_downward_swing_current.new_low_candle.close and self.current_candle.close >= self.save_downward_swing_current.new_low_candle.high)
                                or (self.current_candle.rsi > previous_green_candle.rsi and self.save_downward_swing_current.new_low_candle.close != previous_green_candle.open)) \
                                    or (self.current_candle.close > self.current_candle.previous_high and self.current_candle.rsi > self.current_candle.previous_rsi and  self.current_candle.rsi_13 > self.current_candle.previous_rsi_13 and  self.current_candle.stoch_k > self.current_candle.previous_stoch_k):
                                converting_to_buy = True
                                self.save_downward_swing_current.new_low_candle.divergence_used = True
                                self.update_divergence_used_in_memory(self.save_downward_swing_current.new_low_candle)
                                self.buy_divergence_candle = self.get_candle_by_index(self.save_downward_swing_current.new_low_candle.index)
                            self.add_divergence_info(True, False, converting_to_buy, self.save_downward_swing_previous.new_low_candle, self.save_downward_swing_current.new_low_candle, False , True, self.save_downward_swing_current, False, True )

        if not converting_to_buy and not pre_condition_buy:
            converting_to_buy, pre_condition_buy = self.is_non_extreme_internal_bullish_divergence_only_pre_condition(self.save_downward_swing_current, self.current_candle)

        return converting_to_buy, pre_condition_buy

    def is_all_four_matching_to_buy(self, previous_lowest_rsi_candle):
        all_four_matching = False
        all_four_matching_with_open_taken = False
        condition_one = self.current_candle.rsi >= previous_lowest_rsi_candle.rsi
        condition_two = self.current_candle.rsi_13 >= previous_lowest_rsi_candle.rsi_13
        condition_three = self.current_candle.stoch_k >= previous_lowest_rsi_candle.stoch_k
        condition_four = self.current_candle.stoch_d >= previous_lowest_rsi_candle.stoch_d
        match_count = sum([condition_one, condition_two, condition_three, condition_four])
        open_taken = self.current_candle.close > previous_lowest_rsi_candle.open

        if match_count == 4 and open_taken:
            all_four_matching = True
            # if open_taken:
            #     all_four_matching_with_open_taken = True

        return all_four_matching

    def is_all_four_matching_to_short(self, previous_highest_rsi_candle):
        all_four_matching = False
        all_four_matching_with_open_taken = False
        condition_one = self.current_candle.rsi <= previous_highest_rsi_candle.rsi
        condition_two = self.current_candle.rsi_13 <= previous_highest_rsi_candle.rsi_13
        condition_three = self.current_candle.stoch_k <= previous_highest_rsi_candle.stoch_k
        condition_four = self.current_candle.stoch_d <= previous_highest_rsi_candle.stoch_d
        match_count = sum([condition_one, condition_two, condition_three, condition_four])
        open_taken = self.current_candle.close < previous_highest_rsi_candle.open
        if match_count == 4 and open_taken:
            all_four_matching = True
            # if open_taken:
            #     all_four_matching_with_open_taken = True
        return all_four_matching

    def next(self):
        # Define buy and short signals based on conditions
        buy_condition = False
        short_condition = False
        sell_condition = False
        cover_condition = False
        stop_loss = 0
        converting_to_short = False
        converting_to_buy = False
        pre_condition_short = False
        pre_condition_buy = False
        downward_candles_to_consider = 1
        upward_candles_to_consider = 1
        current_candle = self.create_rsi_stoch_fib()
        #print(f"current_candle # {current_candle}")
        self.current_candle = current_candle

        if self.current_candle.rsi >= 94:
            self.candles_above_94.append(self.current_candle)

        if self.current_candle.rsi <= 5:
            self.candles_below_5.append(self.current_candle)

        if self.enable_trade_shorting and not self.enable_trade_buying:
            if self.current_candle.rsi < 94 and self.current_candle.stoch_k < 100:
                if self.current_candle.previous_rsi > 94 and self.current_candle.previous_stoch_k > 80:
                    if not self.cover_stop_limit:
                        self.cover_stop_limit = self.current_candle.previous_high
                    if self.cover_stop_limit and self.cover_stop_limit != self.current_candle.previous_high:
                        self.cover_stop_limit = self.current_candle.previous_high

        if self.enable_trade_buying and not self.enable_trade_shorting:
            if self.current_candle.rsi > 5 and self.current_candle.stoch_k > 0:
                if self.current_candle.previous_rsi < 5 and self.current_candle.previous_stoch_k < 20:
                    if not self.sell_stop_limit:
                        self.sell_stop_limit = self.current_candle.previous_low
                    if self.sell_stop_limit and self.sell_stop_limit != self.current_candle.previous_low:
                        self.sell_stop_limit = self.current_candle.previous_low

        if self.current_candle.index == self.last_index:
            global updated_divergences
            updated_divergences = self.divergences_by_index.copy()

        if self.current_candle.index == self.last_index:
            global buying_shorting_conditions
            buying_shorting_conditions = self.buying_shorting_conditions.copy()

        if self.current_candle.index == self.last_index:
            global divergence_swing_collection
            global swing_yellow_collection
            global swing_blue_collection
            divergence_swing_collection = self.merge_and_clean_swings()
            swing_yellow_collection = self.create_swings_using_zig_zag_indicator()
            swing_blue_collection = self.create_swings_using_zig_zag_indicator_for_10_legs()

        if self.data.TRADE[-1] == 0:
            self.buy_order = False
            self.short_order = False
            self.in_trade = False
            self.close_only_once = False
            self.position.close()
            self.track_first_set_candles.append(current_candle)

            if self.current_candle.rsi >= 94:
                if len(self.track_all_candles) == 0:
                    self.previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle(self.current_candle.index, self.track_first_set_candles)
                else:
                    self.previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle(self.current_candle.index, self.track_all_candles)

            if self.current_candle.rsi <= 5:
                if len(self.track_all_candles) == 0:
                    self.previous_highest_rsi_candle = self.find_previous_highest_rsi_candle(self.current_candle.index, self.track_first_set_candles)
                else:
                    self.previous_highest_rsi_candle = self.find_previous_highest_rsi_candle(self.current_candle.index, self.track_all_candles)

        if self.data.TRADE[-1] == 1:


            if len(self.track_first_set_candles) > 0:
                n = min(60, len(self.track_first_set_candles))
                self.track_all_candles = self.track_first_set_candles[-n:]
                self.highest_candle = max(self.track_all_candles, key=lambda x: x.high)
                self.lowest_candle = min(self.track_all_candles, key=lambda x: x.low)
                self.track_first_set_candles.clear()

            #print(f"current_candle {current_candle}")
            self.track_all_candles.append(current_candle)
            self.close_only_once = False

            self.latest_upward_swing_candle_from_10_leg = self.get_latest_upward_swing_candle_from_10_leg()

            self.latest_downward_swing_candle_from_10_leg = self.get_latest_downward_swing_candle_from_10_leg()


            if self.current_candle.rsi >= 94:
                if len(self.track_all_candles) == 0:
                    self.previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle(self.current_candle.index, self.track_first_set_candles)
                else:
                    self.previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle(self.current_candle.index, self.track_all_candles)

            if self.current_candle.rsi <= 5:
                if len(self.track_all_candles) == 0:
                    self.previous_highest_rsi_candle = self.find_previous_highest_rsi_candle(self.current_candle.index, self.track_first_set_candles)
                else:
                    self.previous_highest_rsi_candle = self.find_previous_highest_rsi_candle(self.current_candle.index, self.track_all_candles)



            short_cancelled_due_to_overlap = False

            if self.current_candle.body < 0:

                previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                if previous_lowest_rsi_candle:
                    time_difference = abs(self.current_candle.index - previous_lowest_rsi_candle.index)
                    if time_difference <= timedelta(minutes=30) : #and previous_highest_rsi_candle.close > self.current_candle.close:
                        find_previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(previous_lowest_rsi_candle, self.track_all_candles, False)
                        if find_previous_highest_rsi_candle and (self.current_candle.rsi < find_previous_highest_rsi_candle.rsi
                                                                 and (self.current_candle.rsi_13 > find_previous_highest_rsi_candle.rsi_13 \
                                                                      or self.current_candle.stoch_k > find_previous_highest_rsi_candle.stoch_k
                                                                      or self.current_candle.stoch_d > find_previous_highest_rsi_candle.stoch_d)):
                            short_cancelled_due_to_overlap = True
                            self.add_helper_messages(f"Info Only: RSI_2 Short Cancel Overlap Found, Start # {find_previous_highest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")


                previous_lowest_rsi_candle = self.find_previous_lowest_rsi_13_candle_latest(self.current_candle, self.track_all_candles, False)
                if previous_lowest_rsi_candle and not short_cancelled_due_to_overlap:
                    time_difference = abs(self.current_candle.index - previous_lowest_rsi_candle.index)
                    if time_difference < timedelta(minutes=30) : #and previous_highest_rsi_candle.close > self.current_candle.close:
                        find_previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(previous_lowest_rsi_candle, self.track_all_candles, False)
                        if find_previous_highest_rsi_candle and  (self.current_candle.rsi > find_previous_highest_rsi_candle.rsi
                                                                  and (self.current_candle.rsi_13 < find_previous_highest_rsi_candle.rsi_13
                                                                       or self.current_candle.stoch_k < find_previous_highest_rsi_candle.stoch_k
                                                                       or self.current_candle.stoch_d < find_previous_highest_rsi_candle.stoch_d)):
                            short_cancelled_due_to_overlap = True
                            self.add_helper_messages(f"Info Only: RSI_13 Short Cancel Overlap Found, Start # {find_previous_highest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")

            if self.current_candle.body < 0 :
                previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, True)
                if self.in_trade_candle and previous_highest_rsi_candle and previous_highest_rsi_candle.index >= self.in_trade_candle.index:
                    time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                    if time_difference < timedelta(minutes=20):
                        condition_one = previous_highest_rsi_candle.rsi_13 > 60
                        condition_two = previous_highest_rsi_candle.rsi > 94
                        condition_three = previous_highest_rsi_candle.stoch_k > 80
                        condition_four = previous_highest_rsi_candle.stoch_d > 80
                        match_count = sum([condition_one, condition_two, condition_three, condition_four])
                        if match_count == 4:
                            if self.current_candle.close < previous_highest_rsi_candle.close:
                                self.add_helper_messages(f"Info Only: Shorted Extreme found {previous_highest_rsi_candle.index.strftime('%I:%M %p')}")

            if self.current_candle.body < 0:
                condition_match = False
                previous_highest_rsi_candle = self.find_previous_highest_rsi_2_candle_latest(self.current_candle, self.track_all_candles)
                if previous_highest_rsi_candle:
                    time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                    if time_difference < timedelta(minutes=15):

                        if self.in_trade_candle and self.in_trade_candle.previous_highest_rsi_candle and previous_highest_rsi_candle.close < self.in_trade_candle.previous_highest_rsi_candle.close:
                            previous_highest_rsi_candle = self.in_trade_candle.previous_highest_rsi_candle

                        find_previous_highest_rsi_2_candle = self.find_previous_highest_rsi_2_candle_latest(previous_highest_rsi_candle, self.track_all_candles)
                        if find_previous_highest_rsi_2_candle and find_previous_highest_rsi_2_candle.close < previous_highest_rsi_candle.close and find_previous_highest_rsi_2_candle.high < previous_highest_rsi_candle.high:
                            time_difference = abs(find_previous_highest_rsi_2_candle.index - previous_highest_rsi_candle.index)
                            if previous_highest_rsi_candle.rsi <  find_previous_highest_rsi_2_candle.rsi and time_difference <= timedelta(minutes=15):
                                if self.in_trade_candle:
                                    self.in_trade_candle.previous_highest_rsi_candle = previous_highest_rsi_candle
                                if self.is_all_four_matching_to_short(previous_highest_rsi_candle):
                                    condition_match = True
                                    if self.in_trade_candle:
                                        self.in_trade_candle.previous_highest_rsi_candle = None
                                    self.add_helper_messages(f"Info Only : RSI_2 Short Divergence Found , Start # {find_previous_highest_rsi_2_candle.index.strftime('%I:%M %p')}, End # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}")


                        find_previous_highest_rsi_13_candle = self.find_previous_highest_rsi_13_candle_latest(previous_highest_rsi_candle, self.track_all_candles)
                        if not condition_match and find_previous_highest_rsi_13_candle and find_previous_highest_rsi_13_candle.close < previous_highest_rsi_candle.close and find_previous_highest_rsi_13_candle.high < previous_highest_rsi_candle.high:
                            time_difference = abs(find_previous_highest_rsi_13_candle.index - previous_highest_rsi_candle.index)
                            if previous_highest_rsi_candle.rsi_13 <  find_previous_highest_rsi_13_candle.rsi_13 and time_difference <= timedelta(minutes=15):
                                if self.in_trade_candle:
                                    self.in_trade_candle.previous_highest_rsi_candle = previous_highest_rsi_candle
                                if self.is_all_four_matching_to_short(previous_highest_rsi_candle):
                                    condition_match = True
                                    if self.in_trade_candle:
                                        self.in_trade_candle.previous_highest_rsi_candle = None
                                    self.add_helper_messages(f"Info Only : RSI_13 Short Divergence Found , Start # {find_previous_highest_rsi_13_candle.index.strftime('%I:%M %p')}, End # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}")

                        find_previous_highest_stoch_k_candle = self.find_previous_highest_stoch_k_candle_latest(previous_highest_rsi_candle, self.track_all_candles)
                        if not condition_match and find_previous_highest_stoch_k_candle and find_previous_highest_stoch_k_candle.close < previous_highest_rsi_candle.close and find_previous_highest_stoch_k_candle.high < previous_highest_rsi_candle.high:
                            time_difference = abs(find_previous_highest_stoch_k_candle.index - previous_highest_rsi_candle.index)
                            if previous_highest_rsi_candle.stoch_k <  find_previous_highest_stoch_k_candle.stoch_k and time_difference <= timedelta(minutes=15):
                                if self.in_trade_candle:
                                    self.in_trade_candle.previous_highest_rsi_candle = previous_highest_rsi_candle
                                if self.is_all_four_matching_to_short(previous_highest_rsi_candle):
                                    condition_match = True
                                    if self.in_trade_candle:
                                        self.in_trade_candle.previous_highest_rsi_candle = None
                                    self.add_helper_messages(f"Info Only : Stoch_K Short Divergence Found , Start # {find_previous_highest_stoch_k_candle.index.strftime('%I:%M %p')}, End # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}")


                        find_previous_highest_stoch_d_candle = self.find_previous_highest_stoch_d_candle_latest(previous_highest_rsi_candle, self.track_all_candles, False)
                        if not condition_match and find_previous_highest_stoch_d_candle and find_previous_highest_stoch_d_candle.close < previous_highest_rsi_candle.close and find_previous_highest_stoch_d_candle.high < previous_highest_rsi_candle.high:
                            time_difference = abs(find_previous_highest_stoch_d_candle.index - previous_highest_rsi_candle.index)
                            if previous_highest_rsi_candle.stoch_d <  find_previous_highest_stoch_d_candle.stoch_d and time_difference <= timedelta(minutes=15):
                                if self.in_trade_candle:
                                    self.in_trade_candle.previous_highest_rsi_candle = previous_highest_rsi_candle
                                if self.is_all_four_matching_to_short(previous_highest_rsi_candle):
                                    condition_match = True
                                    if self.in_trade_candle:
                                        self.in_trade_candle.previous_highest_rsi_candle = None
                                    self.add_helper_messages(f"Info Only : Stoch_K Short Divergence Found , Start # {find_previous_highest_stoch_d_candle.index.strftime('%I:%M %p')}, End # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}")


            if self.current_candle.body < 0:
                condition_match = False
                previous_highest_rsi_candle = self.find_previous_highest_rsi_2_candle_latest(self.current_candle, self.track_all_candles)
                if previous_highest_rsi_candle:
                    time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                    if time_difference < timedelta(minutes=15):

                        if self.in_trade_candle and self.in_trade_candle.previous_highest_rsi_candle and previous_highest_rsi_candle.close < self.in_trade_candle.previous_highest_rsi_candle.close:
                            previous_highest_rsi_candle = self.in_trade_candle.previous_highest_rsi_candle

                        find_previous_highest_rsi_2_candle = self.find_previous_highest_rsi_2_candle_latest(previous_highest_rsi_candle, self.track_all_candles)
                        if find_previous_highest_rsi_2_candle and find_previous_highest_rsi_2_candle.close > previous_highest_rsi_candle.close and find_previous_highest_rsi_2_candle.high > previous_highest_rsi_candle.high:
                            time_difference = abs(find_previous_highest_rsi_2_candle.index - previous_highest_rsi_candle.index)
                            if previous_highest_rsi_candle.rsi <  find_previous_highest_rsi_2_candle.rsi and time_difference <= timedelta(minutes=120):
                                high_candle_found = self.find_highest_high_green_candle_between_start_end(find_previous_highest_rsi_2_candle.index, self.current_candle.index,  self.track_all_candles )
                                if high_candle_found and high_candle_found.high <= find_previous_highest_rsi_2_candle.high and (previous_highest_rsi_candle.rsi_13 >  find_previous_highest_rsi_2_candle.rsi_13 or previous_highest_rsi_candle.stoch_k >  find_previous_highest_rsi_2_candle.stoch_k or previous_highest_rsi_candle.stoch_d >  find_previous_highest_rsi_2_candle.stoch_d):
                                    if self.in_trade_candle:
                                        self.in_trade_candle.previous_highest_rsi_candle = previous_highest_rsi_candle
                                    if self.is_all_four_matching_to_short(previous_highest_rsi_candle):
                                        condition_match = True
                                        if self.in_trade_candle:
                                            self.in_trade_candle.previous_highest_rsi_candle = None
                                        self.add_helper_messages(f"Info Only : RSI_2 Structure Short Divergence Found , Start # {find_previous_highest_rsi_2_candle.index.strftime('%I:%M %p')}, End # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}")


                        find_previous_highest_rsi_13_candle = self.find_previous_highest_rsi_13_candle_latest(previous_highest_rsi_candle, self.track_all_candles)
                        if not condition_match and find_previous_highest_rsi_13_candle and find_previous_highest_rsi_13_candle.close > previous_highest_rsi_candle.close and find_previous_highest_rsi_13_candle.high > previous_highest_rsi_candle.high:
                            time_difference = abs(find_previous_highest_rsi_13_candle.index - previous_highest_rsi_candle.index)
                            if previous_highest_rsi_candle.rsi_13 <  find_previous_highest_rsi_13_candle.rsi_13 and time_difference <= timedelta(minutes=120):
                                high_candle_found = self.find_highest_high_green_candle_between_start_end(find_previous_highest_rsi_13_candle.index, self.current_candle.index,  self.track_all_candles )
                                if high_candle_found and high_candle_found.high <= find_previous_highest_rsi_13_candle.high and (previous_highest_rsi_candle.rsi >  find_previous_highest_rsi_13_candle.rsi or previous_highest_rsi_candle.stoch_k >  find_previous_highest_rsi_13_candle.stoch_k or previous_highest_rsi_candle.stoch_d >  find_previous_highest_rsi_13_candle.stoch_d):
                                    if self.in_trade_candle:
                                        self.in_trade_candle.previous_highest_rsi_candle = previous_highest_rsi_candle
                                    if self.is_all_four_matching_to_short(previous_highest_rsi_candle):
                                        condition_match = True
                                        if self.in_trade_candle:
                                            self.in_trade_candle.previous_highest_rsi_candle = None
                                        self.add_helper_messages(f"Info Only : RSI_13 Structure Short Divergence Found , Start # {find_previous_highest_rsi_13_candle.index.strftime('%I:%M %p')}, End # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}")

                        find_previous_highest_stoch_k_candle = self.find_previous_highest_stoch_k_candle_latest(previous_highest_rsi_candle, self.track_all_candles)
                        if not condition_match and find_previous_highest_stoch_k_candle and find_previous_highest_stoch_k_candle.close > previous_highest_rsi_candle.close and find_previous_highest_stoch_k_candle.high > previous_highest_rsi_candle.high:
                            time_difference = abs(find_previous_highest_stoch_k_candle.index - previous_highest_rsi_candle.index)
                            if previous_highest_rsi_candle.stoch_k <  find_previous_highest_stoch_k_candle.stoch_k and time_difference <= timedelta(minutes=120):
                                high_candle_found = self.find_highest_high_green_candle_between_start_end(find_previous_highest_stoch_k_candle.index, self.current_candle.index,  self.track_all_candles )
                                if high_candle_found and high_candle_found.high <= find_previous_highest_stoch_k_candle.high and (previous_highest_rsi_candle.rsi >  find_previous_highest_stoch_k_candle.rsi or previous_highest_rsi_candle.rsi_13 >  find_previous_highest_stoch_k_candle.rsi_13 or previous_highest_rsi_candle.stoch_d >  find_previous_highest_stoch_k_candle.stoch_d):
                                    if self.in_trade_candle:
                                        self.in_trade_candle.previous_highest_rsi_candle = previous_highest_rsi_candle
                                    if self.is_all_four_matching_to_short(previous_highest_rsi_candle):
                                        condition_match = True
                                        if self.in_trade_candle:
                                            self.in_trade_candle.previous_highest_rsi_candle = None
                                        self.add_helper_messages(f"Info Only : Stoch_K Structure Short Divergence Found , Start # {find_previous_highest_stoch_k_candle.index.strftime('%I:%M %p')}, End # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}")


                        find_previous_highest_stoch_d_candle = self.find_previous_highest_stoch_d_candle_latest(previous_highest_rsi_candle, self.track_all_candles, False)
                        if not condition_match and find_previous_highest_stoch_d_candle and find_previous_highest_stoch_d_candle.close > previous_highest_rsi_candle.close and find_previous_highest_stoch_d_candle.high > previous_highest_rsi_candle.high:
                            time_difference = abs(find_previous_highest_stoch_d_candle.index - previous_highest_rsi_candle.index)
                            if previous_highest_rsi_candle.stoch_d <  find_previous_highest_stoch_d_candle.stoch_d and time_difference <= timedelta(minutes=120):
                                high_candle_found = self.find_highest_high_green_candle_between_start_end(find_previous_highest_stoch_d_candle.index, self.current_candle.index,  self.track_all_candles )
                                if high_candle_found and high_candle_found.high <= find_previous_highest_stoch_d_candle.high and (previous_highest_rsi_candle.rsi >  find_previous_highest_stoch_d_candle.rsi or previous_highest_rsi_candle.rsi_13 >  find_previous_highest_stoch_d_candle.rsi_13 or previous_highest_rsi_candle.stoch_k >  find_previous_highest_stoch_d_candle.stoch_k):
                                    if self.in_trade_candle:
                                        self.in_trade_candle.previous_highest_rsi_candle = previous_highest_rsi_candle
                                    if self.is_all_four_matching_to_short(previous_highest_rsi_candle):
                                        condition_match = True
                                        if self.in_trade_candle:
                                            self.in_trade_candle.previous_highest_rsi_candle = None
                                        self.add_helper_messages(f"Info Only : Stoch_K Short Divergence Found , Start # {find_previous_highest_stoch_d_candle.index.strftime('%I:%M %p')}, End # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}")

            if self.current_candle.body < 0:
                condition_match = False
                previous_previous_lowest_rsi_2_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                if previous_previous_lowest_rsi_2_candle and previous_previous_lowest_rsi_2_candle.close > self.current_candle.close and previous_previous_lowest_rsi_2_candle.low > self.current_candle.low:
                    time_difference = abs(self.current_candle.index - previous_previous_lowest_rsi_2_candle.index)
                    if time_difference <= timedelta(minutes=15):
                        if previous_previous_lowest_rsi_2_candle.rsi < self.current_candle.rsi:
                            condition_match = True
                            self.add_helper_messages(f"Info Only : RSI_2 Short Divergence Cancel Found , Start # {previous_previous_lowest_rsi_2_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")

                previous_previous_lowest_rsi_13_candle = self.find_previous_lowest_rsi_13_candle_latest(self.current_candle, self.track_all_candles, False)
                if not condition_match and previous_previous_lowest_rsi_13_candle and previous_previous_lowest_rsi_13_candle.close > self.current_candle.close and previous_previous_lowest_rsi_13_candle.low > self.current_candle.low:
                    time_difference = abs(self.current_candle.index - previous_previous_lowest_rsi_13_candle.index)
                    if time_difference <= timedelta(minutes=15):
                        if previous_previous_lowest_rsi_13_candle.rsi_13 < self.current_candle.rsi_13:
                            condition_match = True
                            self.add_helper_messages(f"Info Only : RSI_13 Short Divergence Cancel Found , Start # {previous_previous_lowest_rsi_13_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")

                previous_previous_lowest_stoch_k_candle = self.find_previous_lowest_stoch_k_candle_latest(self.current_candle, self.track_all_candles, False)
                if not condition_match and previous_previous_lowest_stoch_k_candle and previous_previous_lowest_stoch_k_candle.close > self.current_candle.close and previous_previous_lowest_stoch_k_candle.low > self.current_candle.low:
                    time_difference = abs(self.current_candle.index - previous_previous_lowest_stoch_k_candle.index)
                    if time_difference <= timedelta(minutes=15):
                        if previous_previous_lowest_stoch_k_candle.stoch_k < self.current_candle.stoch_k:
                            condition_match = True
                            self.add_helper_messages(f"Info Only : Stoch_K Short Divergence Cancel Found , Start # {previous_previous_lowest_stoch_k_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")

                previous_previous_lowest_stoch_d_candle = self.find_previous_lowest_stoch_d_candle_latest(self.current_candle, self.track_all_candles, False)
                if not condition_match and previous_previous_lowest_stoch_d_candle and previous_previous_lowest_stoch_d_candle.close > self.current_candle.close and previous_previous_lowest_stoch_d_candle.low > self.current_candle.low:
                    time_difference = abs(self.current_candle.index - previous_previous_lowest_stoch_d_candle.index)
                    if time_difference <= timedelta(minutes=15):
                        if previous_previous_lowest_stoch_d_candle.stoch_k < self.current_candle.stoch_k:
                            condition_match = True
                            self.add_helper_messages(f"Info Only : Stoch_D Short Divergence Cancel Found , Start # {previous_previous_lowest_stoch_d_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")


            if self.current_candle.body < 0:
                condition_match = False
                previous_previous_lowest_rsi_2_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                if previous_previous_lowest_rsi_2_candle and previous_previous_lowest_rsi_2_candle.close < self.current_candle.close and previous_previous_lowest_rsi_2_candle.low < self.current_candle.low:
                    time_difference = abs(self.current_candle.index - previous_previous_lowest_rsi_2_candle.index)
                    if time_difference <= timedelta(minutes=120):
                        if previous_previous_lowest_rsi_2_candle.rsi < self.current_candle.rsi:
                            low_candle_found = self.find_candle_with_lowest_low_price_candle(previous_previous_lowest_rsi_2_candle.index, self.current_candle.index,  self.track_all_candles )
                            if low_candle_found and low_candle_found.low >= previous_previous_lowest_rsi_2_candle.low and (previous_previous_lowest_rsi_2_candle.rsi_13 > self.current_candle.rsi_13 or previous_previous_lowest_rsi_2_candle.stoch_k > self.current_candle.stoch_k or previous_previous_lowest_rsi_2_candle.stoch_d > self.current_candle.stoch_d):
                                condition_match = True
                                self.add_helper_messages(f"Info Only : RSI_2 Structure Short Divergence Cancel Found , Start # {previous_previous_lowest_rsi_2_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")

                previous_previous_lowest_rsi_13_candle = self.find_previous_lowest_rsi_13_candle_latest(self.current_candle, self.track_all_candles, False)
                if not condition_match and previous_previous_lowest_rsi_13_candle and previous_previous_lowest_rsi_13_candle.close < self.current_candle.close and previous_previous_lowest_rsi_13_candle.low < self.current_candle.low:
                    time_difference = abs(self.current_candle.index - previous_previous_lowest_rsi_13_candle.index)
                    if time_difference <= timedelta(minutes=120):
                        if previous_previous_lowest_rsi_13_candle.rsi_13 < self.current_candle.rsi_13:
                            low_candle_found = self.find_candle_with_lowest_low_price_candle(previous_previous_lowest_rsi_13_candle.index, self.current_candle.index,  self.track_all_candles )
                            if low_candle_found and low_candle_found.low >= previous_previous_lowest_rsi_13_candle.low and (previous_previous_lowest_rsi_13_candle.rsi > self.current_candle.rsi or previous_previous_lowest_rsi_13_candle.stoch_k > self.current_candle.stoch_k or previous_previous_lowest_rsi_13_candle.stoch_d > self.current_candle.stoch_d):
                                condition_match = True
                                self.add_helper_messages(f"Info Only : RSI_13 Structure Short Divergence Cancel Found , Start # {previous_previous_lowest_rsi_13_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")

                previous_previous_lowest_stoch_k_candle = self.find_previous_lowest_stoch_k_candle_latest(self.current_candle, self.track_all_candles, False)
                if not condition_match and previous_previous_lowest_stoch_k_candle and previous_previous_lowest_stoch_k_candle.close < self.current_candle.close and previous_previous_lowest_stoch_k_candle.low < self.current_candle.low:
                    time_difference = abs(self.current_candle.index - previous_previous_lowest_stoch_k_candle.index)
                    if time_difference <= timedelta(minutes=120):
                        if previous_previous_lowest_stoch_k_candle.stoch_k < self.current_candle.stoch_k:
                            low_candle_found = self.find_candle_with_lowest_low_price_candle(previous_previous_lowest_stoch_k_candle.index, self.current_candle.index,  self.track_all_candles )
                            if low_candle_found and low_candle_found.low >= previous_previous_lowest_stoch_k_candle.low and (previous_previous_lowest_stoch_k_candle.rsi > self.current_candle.rsi or previous_previous_lowest_stoch_k_candle.rsi_13 > self.current_candle.rsi_13 or previous_previous_lowest_stoch_k_candle.stoch_d > self.current_candle.stoch_d):
                                condition_match = True
                                self.add_helper_messages(f"Info Only : Stoch_K Structure Short Divergence Cancel Found , Start # {previous_previous_lowest_stoch_k_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")

                previous_previous_lowest_stoch_d_candle = self.find_previous_lowest_stoch_d_candle_latest(self.current_candle, self.track_all_candles, False)
                if not condition_match and previous_previous_lowest_stoch_d_candle and previous_previous_lowest_stoch_d_candle.close < self.current_candle.close and previous_previous_lowest_stoch_d_candle.low < self.current_candle.low:
                    time_difference = abs(self.current_candle.index - previous_previous_lowest_stoch_d_candle.index)
                    if time_difference <= timedelta(minutes=120):
                        if previous_previous_lowest_stoch_d_candle.stoch_k < self.current_candle.stoch_k:
                            low_candle_found = self.find_candle_with_lowest_low_price_candle(previous_previous_lowest_stoch_d_candle.index, self.current_candle.index,  self.track_all_candles )
                            if low_candle_found and low_candle_found.low >= previous_previous_lowest_stoch_d_candle.low and (previous_previous_lowest_stoch_d_candle.rsi > self.current_candle.rsi or previous_previous_lowest_stoch_d_candle.rsi_13 > self.current_candle.rsi_13 or previous_previous_lowest_stoch_d_candle.stoch_k > self.current_candle.stoch_k):
                                condition_match = True
                                self.add_helper_messages(f"Info Only : Stoch_D Structure Short Divergence Cancel Found , Start # {previous_previous_lowest_stoch_d_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")


            buy_cancelled_due_to_overlap = False


            if self.current_candle.body > 0:

                if "01:50 PM" in self.current_candle.date:
                    print("Put Break Point")

                previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                if previous_highest_rsi_candle:
                    time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                    if time_difference <= timedelta(minutes=30) :
                        find_previous_lowest_rsi_candle = self.find_red_candle_from_high(previous_highest_rsi_candle.index, self.track_all_candles)
                        if self.current_candle.rsi < find_previous_lowest_rsi_candle.rsi and (self.current_candle.rsi_13 > find_previous_lowest_rsi_candle.rsi_13 \
                                                                                              or self.current_candle.stoch_k > find_previous_lowest_rsi_candle.stoch_k or self.current_candle.stoch_d > find_previous_lowest_rsi_candle.stoch_d):
                            buy_cancelled_due_to_overlap = True
                            self.add_helper_messages(f"Info Only: RSI_2 Buy Cancel Overlap Found, Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")


                previous_highest_rsi_candle = self.find_previous_highest_rsi_13_candle_latest(self.current_candle, self.track_all_candles)
                if previous_highest_rsi_candle and not buy_cancelled_due_to_overlap:
                    time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                    if time_difference < timedelta(minutes=30) :
                        find_previous_lowest_rsi_candle = self.find_red_candle_from_high(previous_highest_rsi_candle.index, self.track_all_candles)
                        if self.current_candle.rsi_13 < find_previous_lowest_rsi_candle.rsi_13 and (self.current_candle.rsi > find_previous_lowest_rsi_candle.rsi or self.current_candle.stoch_k > find_previous_lowest_rsi_candle.stoch_k or self.current_candle.stoch_d > find_previous_lowest_rsi_candle.stoch_d):
                            buy_cancelled_due_to_overlap = True
                            self.add_helper_messages(f"Info Only: RSI_13 Buy Cancel Overlap Found, Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")


            if self.current_candle.body > 0:
                previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle, self.track_all_candles, True)
                if self.in_trade_candle and previous_lowest_rsi_candle and previous_lowest_rsi_candle.index > self.in_trade_candle.index:
                    time_difference = abs(self.current_candle.index - previous_lowest_rsi_candle.index)
                    if time_difference < timedelta(minutes=20):
                        if previous_lowest_rsi_candle.rsi_13 < 30 and previous_lowest_rsi_candle.rsi < 5 and previous_lowest_rsi_candle.stoch_k < 20 \
                                and previous_lowest_rsi_candle.stoch_d < 20:
                            if self.current_candle.close > previous_lowest_rsi_candle.close:
                                self.add_helper_messages(f"Info Only: Buy Extreme found  {previous_lowest_rsi_candle.index.strftime('%I:%M %p')}")


            if self.current_candle.body > 0:
                condition_match = False
                previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                if previous_lowest_rsi_candle:
                    time_difference = abs(self.current_candle.index - previous_lowest_rsi_candle.index)
                    if time_difference < timedelta(minutes=15):

                        if self.in_trade_candle and self.in_trade_candle.previous_lowest_rsi_candle and previous_lowest_rsi_candle.close > self.in_trade_candle.previous_lowest_rsi_candle.close:
                            previous_lowest_rsi_candle = self.in_trade_candle.previous_lowest_rsi_candle

                        find_previous_lowest_rsi_2_candle = self.find_previous_lowest_rsi_candle_latest(previous_lowest_rsi_candle, self.track_all_candles, False)
                        if find_previous_lowest_rsi_2_candle and find_previous_lowest_rsi_2_candle.close > previous_lowest_rsi_candle.close and find_previous_lowest_rsi_2_candle.low > previous_lowest_rsi_candle.low:
                            time_difference = abs(find_previous_lowest_rsi_2_candle.index - previous_lowest_rsi_candle.index)
                            if previous_lowest_rsi_candle.rsi >  find_previous_lowest_rsi_2_candle.rsi and time_difference <= timedelta(minutes=15):
                                if self.in_trade_candle:
                                    self.in_trade_candle.previous_lowest_rsi_candle = previous_lowest_rsi_candle
                                if self.is_all_four_matching_to_buy(previous_lowest_rsi_candle):
                                    condition_match = True
                                    if self.in_trade_candle:
                                        self.in_trade_candle.previous_lowest_rsi_candle = None
                                    self.add_helper_messages(f"Info Only : RSI_2 Buy Divergence Found , Start # {find_previous_lowest_rsi_2_candle.index.strftime('%I:%M %p')}, End # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')}")


                        find_previous_lowest_rsi_13_candle = self.find_previous_lowest_rsi_13_candle_latest(previous_lowest_rsi_candle, self.track_all_candles, False)
                        if not condition_match and find_previous_lowest_rsi_13_candle and find_previous_lowest_rsi_13_candle.close > previous_lowest_rsi_candle.close and find_previous_lowest_rsi_13_candle.low > previous_lowest_rsi_candle.low:
                            time_difference = abs(find_previous_lowest_rsi_13_candle.index - previous_lowest_rsi_candle.index)
                            if previous_lowest_rsi_candle.rsi_13 >  find_previous_lowest_rsi_13_candle.rsi_13 and time_difference <= timedelta(minutes=15):
                                if self.in_trade_candle:
                                    self.in_trade_candle.previous_lowest_rsi_candle = previous_lowest_rsi_candle
                                if self.is_all_four_matching_to_buy(previous_lowest_rsi_candle):
                                    condition_match = True
                                    if self.in_trade_candle:
                                        self.in_trade_candle.previous_lowest_rsi_candle = None
                                    self.add_helper_messages(f"Info Only : RSI_13 Buy Divergence Found , Start # {find_previous_lowest_rsi_13_candle.index.strftime('%I:%M %p')}, End # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')}")

                        find_previous_lowest_stoch_k_candle = self.find_previous_lowest_stoch_k_candle_latest(previous_lowest_rsi_candle, self.track_all_candles, False)
                        if not condition_match and find_previous_lowest_stoch_k_candle and find_previous_lowest_stoch_k_candle.close > previous_lowest_rsi_candle.close and find_previous_lowest_stoch_k_candle.low > previous_lowest_rsi_candle.low:
                            time_difference = abs(find_previous_lowest_stoch_k_candle.index - previous_lowest_rsi_candle.index)
                            if previous_lowest_rsi_candle.stoch_k >  find_previous_lowest_stoch_k_candle.stoch_k and time_difference <= timedelta(minutes=15):
                                if self.in_trade_candle:
                                    self.in_trade_candle.previous_lowest_rsi_candle = previous_lowest_rsi_candle
                                if self.is_all_four_matching_to_buy(previous_lowest_rsi_candle):
                                    condition_match = True
                                    if self.in_trade_candle:
                                        self.in_trade_candle.previous_lowest_rsi_candle = None
                                    self.add_helper_messages(f"Info Only : Stoch_K Buy Divergence Found , Start # {find_previous_lowest_stoch_k_candle.index.strftime('%I:%M %p')}, End # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')}")


                        find_previous_lowest_stoch_d_candle = self.find_previous_lowest_stoch_d_candle_latest(previous_lowest_rsi_candle, self.track_all_candles, False)
                        if not condition_match and find_previous_lowest_stoch_d_candle and find_previous_lowest_stoch_d_candle.close > previous_lowest_rsi_candle.close and find_previous_lowest_stoch_d_candle.low > previous_lowest_rsi_candle.low:
                            time_difference = abs(find_previous_lowest_stoch_d_candle.index - previous_lowest_rsi_candle.index)
                            if previous_lowest_rsi_candle.stoch_d >  find_previous_lowest_stoch_d_candle.stoch_d and time_difference <= timedelta(minutes=15):
                                if self.in_trade_candle:
                                    self.in_trade_candle.previous_lowest_rsi_candle = previous_lowest_rsi_candle
                                if self.is_all_four_matching_to_buy(previous_lowest_rsi_candle):
                                    condition_match = True
                                    if self.in_trade_candle:
                                        self.in_trade_candle.previous_lowest_rsi_candle = None
                                    self.add_helper_messages(f"Info Only : Stoch_K Buy Divergence Found , Start # {find_previous_lowest_stoch_d_candle.index.strftime('%I:%M %p')}, End # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')}")


            if self.current_candle.body > 0:
                condition_match = False
                previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                if previous_lowest_rsi_candle:
                    time_difference = abs(self.current_candle.index - previous_lowest_rsi_candle.index)
                    if time_difference < timedelta(minutes=15):

                        if self.in_trade_candle and self.in_trade_candle.previous_lowest_rsi_candle and previous_lowest_rsi_candle.close > self.in_trade_candle.previous_lowest_rsi_candle.close:
                            previous_lowest_rsi_candle = self.in_trade_candle.previous_lowest_rsi_candle

                        find_previous_lowest_rsi_2_candle = self.find_previous_lowest_rsi_candle_latest(previous_lowest_rsi_candle, self.track_all_candles, False)
                        if find_previous_lowest_rsi_2_candle and find_previous_lowest_rsi_2_candle.close < previous_lowest_rsi_candle.close and find_previous_lowest_rsi_2_candle.low < previous_lowest_rsi_candle.low:
                            time_difference = abs(find_previous_lowest_rsi_2_candle.index - previous_lowest_rsi_candle.index)
                            if previous_lowest_rsi_candle.rsi >  find_previous_lowest_rsi_2_candle.rsi and time_difference <= timedelta(minutes=120):
                                low_candle_found = self.find_candle_with_lowest_low_price_candle(find_previous_lowest_rsi_2_candle.index, self.current_candle.index,  self.track_all_candles )
                                if low_candle_found and low_candle_found.low >= previous_lowest_rsi_candle.low and (previous_lowest_rsi_candle.rsi_13 <  find_previous_lowest_rsi_2_candle.rsi_13 or previous_lowest_rsi_candle.stoch_k <  find_previous_lowest_rsi_2_candle.stoch_k or previous_lowest_rsi_candle.stoch_d <  find_previous_lowest_rsi_2_candle.stoch_d):
                                    if self.in_trade_candle:
                                        self.in_trade_candle.previous_lowest_rsi_candle = previous_lowest_rsi_candle
                                    if self.is_all_four_matching_to_buy(previous_lowest_rsi_candle):
                                        condition_match = True
                                        if self.in_trade_candle:
                                            self.in_trade_candle.previous_lowest_rsi_candle = None
                                        self.add_helper_messages(f"Info Only : RSI_2 Structure Buy Divergence Found , Start # {find_previous_lowest_rsi_2_candle.index.strftime('%I:%M %p')}, End # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')}")


                        find_previous_lowest_rsi_13_candle = self.find_previous_lowest_rsi_13_candle_latest(previous_lowest_rsi_candle, self.track_all_candles, False)
                        if not condition_match and find_previous_lowest_rsi_13_candle and find_previous_lowest_rsi_13_candle.close < previous_lowest_rsi_candle.close and find_previous_lowest_rsi_13_candle.low < previous_lowest_rsi_candle.low:
                            time_difference = abs(find_previous_lowest_rsi_13_candle.index - previous_lowest_rsi_candle.index)
                            if previous_lowest_rsi_candle.rsi_13 >  find_previous_lowest_rsi_13_candle.rsi_13 and time_difference <= timedelta(minutes=120):
                                low_candle_found = self.find_candle_with_lowest_low_price_candle(find_previous_lowest_rsi_13_candle.index, self.current_candle.index,  self.track_all_candles )
                                if low_candle_found and low_candle_found.low >= find_previous_lowest_rsi_13_candle.low and (previous_lowest_rsi_candle.rsi <  find_previous_lowest_rsi_13_candle.rsi or previous_lowest_rsi_candle.stoch_k <  find_previous_lowest_rsi_13_candle.stoch_k or previous_lowest_rsi_candle.stoch_d <  find_previous_lowest_rsi_13_candle.stoch_d):
                                    if self.in_trade_candle:
                                        self.in_trade_candle.previous_lowest_rsi_candle = previous_lowest_rsi_candle
                                    if self.is_all_four_matching_to_buy(previous_lowest_rsi_candle):
                                        condition_match = True
                                        if self.in_trade_candle:
                                            self.in_trade_candle.previous_lowest_rsi_candle = None
                                        self.add_helper_messages(f"Info Only : RSI_13 Structure Buy Divergence Found , Start # {find_previous_lowest_rsi_13_candle.index.strftime('%I:%M %p')}, End # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')}")

                        find_previous_lowest_stoch_k_candle = self.find_previous_lowest_stoch_k_candle_latest(previous_lowest_rsi_candle, self.track_all_candles, False)
                        if not condition_match and find_previous_lowest_stoch_k_candle and find_previous_lowest_stoch_k_candle.close < previous_lowest_rsi_candle.close and find_previous_lowest_stoch_k_candle.high < previous_lowest_rsi_candle.high:
                            time_difference = abs(find_previous_lowest_stoch_k_candle.index - previous_lowest_rsi_candle.index)
                            if previous_lowest_rsi_candle.stoch_k >  find_previous_lowest_stoch_k_candle.stoch_k and time_difference <= timedelta(minutes=120):
                                low_candle_found = self.find_candle_with_lowest_low_price_candle(find_previous_lowest_stoch_k_candle.index, self.current_candle.index,  self.track_all_candles )
                                if low_candle_found and low_candle_found.low >= find_previous_lowest_stoch_k_candle.low and (previous_lowest_rsi_candle.rsi <  find_previous_lowest_stoch_k_candle.rsi or previous_lowest_rsi_candle.rsi_13 <  find_previous_lowest_stoch_k_candle.rsi_13 or previous_lowest_rsi_candle.stoch_d <  find_previous_lowest_stoch_k_candle.stoch_d):
                                    if self.in_trade_candle:
                                        self.in_trade_candle.previous_lowest_rsi_candle = previous_lowest_rsi_candle
                                    if self.is_all_four_matching_to_buy(previous_lowest_rsi_candle):
                                        condition_match = True
                                        if self.in_trade_candle:
                                            self.in_trade_candle.previous_lowest_rsi_candle = None
                                        self.add_helper_messages(f"Info Only : Stoch_K Structure Buy Divergence Found , Start # {find_previous_lowest_stoch_k_candle.index.strftime('%I:%M %p')}, End # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')}")


                        find_previous_lowest_stoch_d_candle = self.find_previous_lowest_stoch_d_candle_latest(previous_lowest_rsi_candle, self.track_all_candles, False)
                        if not condition_match and find_previous_lowest_stoch_d_candle and find_previous_lowest_stoch_d_candle.close < previous_lowest_rsi_candle.close and find_previous_lowest_stoch_d_candle.low < previous_lowest_rsi_candle.low:
                            time_difference = abs(find_previous_lowest_stoch_d_candle.index - previous_lowest_rsi_candle.index)
                            if previous_lowest_rsi_candle.stoch_d >  find_previous_lowest_stoch_d_candle.stoch_d and time_difference <= timedelta(minutes=120):
                                low_candle_found = self.find_candle_with_lowest_low_price_candle(find_previous_lowest_stoch_d_candle.index, self.current_candle.index,  self.track_all_candles )
                                if low_candle_found and low_candle_found.low >= find_previous_lowest_stoch_d_candle.low and (previous_lowest_rsi_candle.rsi <  find_previous_lowest_stoch_d_candle.rsi or previous_lowest_rsi_candle.rsi_13 <  find_previous_lowest_stoch_d_candle.rsi_13 or previous_lowest_rsi_candle.stoch_k <  find_previous_lowest_stoch_d_candle.stoch_k):
                                    if self.in_trade_candle:
                                        self.in_trade_candle.previous_lowest_rsi_candle = previous_lowest_rsi_candle
                                    if self.is_all_four_matching_to_buy(previous_lowest_rsi_candle):
                                        condition_match = True
                                        if self.in_trade_candle:
                                            self.in_trade_candle.previous_lowest_rsi_candle = None
                                        self.add_helper_messages(f"Info Only : Stoch_K Buy Divergence Found , Start # {find_previous_lowest_stoch_d_candle.index.strftime('%I:%M %p')}, End # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')}")

            if self.current_candle.body > 0:

                condition_match = False
                previous_previous_highest_rsi_2_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                if previous_previous_highest_rsi_2_candle and previous_previous_highest_rsi_2_candle.close < self.current_candle.close and previous_previous_highest_rsi_2_candle.high < self.current_candle.high:
                    time_difference = abs(self.current_candle.index - previous_previous_highest_rsi_2_candle.index)
                    if time_difference <= timedelta(minutes=15):
                        if previous_previous_highest_rsi_2_candle.rsi > self.current_candle.rsi:
                            condition_match = True
                            self.add_helper_messages(f"Info Only : RSI_2 Buy Divergence Cancel Found , Start # {previous_previous_highest_rsi_2_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")

                previous_previous_highest_rsi_13_candle = self.find_previous_highest_rsi_13_candle_latest(self.current_candle, self.track_all_candles)
                if not condition_match and previous_previous_highest_rsi_13_candle and previous_previous_highest_rsi_13_candle.close < self.current_candle.close and previous_previous_highest_rsi_13_candle.high < self.current_candle.high:
                    time_difference = abs(self.current_candle.index - previous_previous_highest_rsi_13_candle.index)
                    if time_difference <= timedelta(minutes=15):
                        if previous_previous_highest_rsi_13_candle.rsi_13 > self.current_candle.rsi_13:
                            condition_match = True
                            self.add_helper_messages(f"Info Only : RSI_13 Buy Divergence Cancel Found , Start # {previous_previous_highest_rsi_13_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")

                previous_previous_highest_stoch_k_candle = self.find_previous_highest_stoch_k_candle_latest(self.current_candle, self.track_all_candles)
                if not condition_match and previous_previous_highest_stoch_k_candle and previous_previous_highest_stoch_k_candle.close < self.current_candle.close and previous_previous_highest_stoch_k_candle.high < self.current_candle.high:
                    time_difference = abs(self.current_candle.index - previous_previous_highest_stoch_k_candle.index)
                    if time_difference <= timedelta(minutes=15):
                        if previous_previous_highest_stoch_k_candle.stoch_k > self.current_candle.stoch_k:
                            condition_match = True
                            self.add_helper_messages(f"Info Only : Stoch_K Buy Divergence Cancel Found , Start # {previous_previous_highest_stoch_k_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")

                previous_previous_highest_stoch_d_candle = self.find_previous_highest_stoch_d_candle_latest(self.current_candle, self.track_all_candles, False)
                if not condition_match and previous_previous_highest_stoch_d_candle and previous_previous_highest_stoch_d_candle.close < self.current_candle.close and previous_previous_highest_stoch_d_candle.high < self.current_candle.high:
                    time_difference = abs(self.current_candle.index - previous_previous_highest_stoch_d_candle.index)
                    if time_difference <= timedelta(minutes=15):
                        if previous_previous_highest_stoch_d_candle.stoch_k > self.current_candle.stoch_k:
                            condition_match = True
                            self.add_helper_messages(f"Info Only : Stoch_D Buy Divergence Cancel Found , Start # {previous_previous_highest_stoch_d_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")


            if self.current_candle.body > 0:
                condition_match = False
                previous_previous_highest_rsi_2_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                if previous_previous_highest_rsi_2_candle and previous_previous_highest_rsi_2_candle.close > self.current_candle.close and previous_previous_highest_rsi_2_candle.high > self.current_candle.high:
                    time_difference = abs(self.current_candle.index - previous_previous_highest_rsi_2_candle.index)
                    if time_difference <= timedelta(minutes=120):
                        if previous_previous_highest_rsi_2_candle.rsi > self.current_candle.rsi:
                            high_candle_found = self.find_highest_high_green_candle_between_start_end(previous_previous_highest_rsi_2_candle.index, self.current_candle.index,  self.track_all_candles )
                            if high_candle_found and high_candle_found.high <= previous_previous_highest_rsi_2_candle.high and (previous_previous_highest_rsi_2_candle.rsi_13 < self.current_candle.rsi_13 or previous_previous_highest_rsi_2_candle.stoch_k < self.current_candle.stoch_k or previous_previous_highest_rsi_2_candle.stoch_d < self.current_candle.stoch_d):
                                condition_match = True
                                self.add_helper_messages(f"Info Only : RSI_2 Structure Buy Divergence Cancel Found , Start # {previous_previous_highest_rsi_2_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")

                previous_previous_highest_rsi_13_candle = self.find_previous_highest_rsi_13_candle_latest(self.current_candle, self.track_all_candles)
                if not condition_match and previous_previous_highest_rsi_13_candle and previous_previous_highest_rsi_13_candle.close > self.current_candle.close and previous_previous_highest_rsi_13_candle.high > self.current_candle.high:
                    time_difference = abs(self.current_candle.index - previous_previous_highest_rsi_13_candle.index)
                    if time_difference <= timedelta(minutes=120):
                        if previous_previous_highest_rsi_13_candle.rsi_13 > self.current_candle.rsi_13:
                            high_candle_found = self.find_highest_high_green_candle_between_start_end(previous_previous_highest_rsi_13_candle.index, self.current_candle.index,  self.track_all_candles )
                            if high_candle_found and high_candle_found.high <= previous_previous_highest_rsi_13_candle.high and (previous_previous_highest_rsi_13_candle.rsi < self.current_candle.rsi or previous_previous_highest_rsi_13_candle.stoch_k < self.current_candle.stoch_k or previous_previous_highest_rsi_13_candle.stoch_d < self.current_candle.stoch_d):
                                condition_match = True
                                self.add_helper_messages(f"Info Only : RSI_13 Structure Buy Divergence Cancel Found , Start # {previous_previous_highest_rsi_13_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")

                previous_previous_highest_stoch_k_candle = self.find_previous_highest_stoch_k_candle_latest(self.current_candle, self.track_all_candles)
                if not condition_match and previous_previous_highest_stoch_k_candle and previous_previous_highest_stoch_k_candle.close > self.current_candle.close and previous_previous_highest_stoch_k_candle.high > self.current_candle.high:
                    time_difference = abs(self.current_candle.index - previous_previous_highest_stoch_k_candle.index)
                    if time_difference <= timedelta(minutes=120):
                        if previous_previous_highest_stoch_k_candle.stoch_k > self.current_candle.stoch_k:
                            high_candle_found = self.find_highest_high_green_candle_between_start_end(previous_previous_highest_stoch_k_candle.index, self.current_candle.index,  self.track_all_candles )
                            if high_candle_found and high_candle_found.high <= previous_previous_highest_stoch_k_candle.high and (previous_previous_highest_stoch_k_candle.rsi < self.current_candle.rsi or previous_previous_highest_stoch_k_candle.rsi_13 < self.current_candle.rsi_13 or previous_previous_highest_stoch_k_candle.stoch_d < self.current_candle.stoch_d):
                                condition_match = True
                                self.add_helper_messages(f"Info Only : Stoch_K Structure Buy Divergence Cancel Found , Start # {previous_previous_highest_stoch_k_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")

                previous_previous_highest_stoch_d_candle = self.find_previous_highest_stoch_d_candle_latest(self.current_candle, self.track_all_candles, False)
                if not condition_match and previous_previous_highest_stoch_d_candle and previous_previous_highest_stoch_d_candle.close > self.current_candle.close and previous_previous_highest_stoch_d_candle.high > self.current_candle.high:
                    time_difference = abs(self.current_candle.index - previous_previous_highest_stoch_d_candle.index)
                    if time_difference <= timedelta(minutes=120):
                        if previous_previous_highest_stoch_d_candle.stoch_k > self.current_candle.stoch_k:
                            high_candle_found = self.find_highest_high_green_candle_between_start_end(previous_previous_highest_stoch_k_candle.index, self.current_candle.index,  self.track_all_candles )
                            if high_candle_found and high_candle_found.high <= previous_previous_highest_stoch_d_candle.high and (previous_previous_highest_stoch_d_candle.rsi < self.current_candle.rsi or previous_previous_highest_stoch_d_candle.rsi_13 < self.current_candle.rsi_13 or previous_previous_highest_stoch_d_candle.stoch_k < self.current_candle.stoch_k):
                                condition_match = True
                                self.add_helper_messages(f"Info Only : Stoch_D Structure Buy Divergence Cancel Found , Start # {previous_previous_highest_stoch_d_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")

            if not self.in_trade:

                if not self.manual_buy_short_trigger_candle:
                    upward_swings = self.find_upward_swings_from_low(self.track_all_candles, 2, True, None, True)
                    if len(upward_swings) == 0 and not self.save_upward_swing_current:
                        highest_price_candle =max(self.track_all_candles, key=lambda candle: candle.high)
                        upward_swings = self.find_upward_swings_from_low(self.track_all_candles, 2, True, highest_price_candle.datetime, True, True, False)

                    if len(upward_swings) == 1:
                        if self.save_upward_swing_current and self.save_upward_swing_current.new_high_candle and not self.save_upward_swing_current.new_high_candle.new_low_candle:
                            upward_swing_current = upward_swings[-1]
                            if upward_swing_current.new_high_candle.close < self.save_upward_swing_current.new_high_candle.close and upward_swing_current.new_high_candle.high < self.save_upward_swing_current.new_high_candle.high:
                                upward_swings.clear()

                    if len(upward_swings) >= 2:
                        upward_swings = self.combine_rsi_stoch_fib_numbers(upward_swings)
                        if len(upward_swings) == 1:
                            upward_swing_current = upward_swings[-1]
                            if not self.save_upward_swing_current:
                                self.save_upward_swing_current = copy.deepcopy(upward_swing_current)
                            else:
                                self.save_upward_swing_previous = copy.deepcopy(self.save_upward_swing_current)
                                self.save_upward_swing_current = copy.deepcopy(upward_swing_current)
                            upward_swings.clear()

                        if len(upward_swings) >= 2:
                            upward_swing_previous = upward_swings[-2]
                            upward_swing_current = upward_swings[-1]
                            self.save_upward_swing_current = copy.deepcopy(upward_swing_current)
                            self.save_upward_swing_previous = copy.deepcopy(upward_swing_previous)
                            upward_swings.clear()

                    if len(upward_swings) == 0 and self.save_upward_swing_current:
                        if current_candle.close > self.save_upward_swing_current.new_high_candle.close and current_candle.high > self.save_upward_swing_current.new_high_candle.high:
                            self.save_upward_swing_current.new_high_candle = current_candle
                            self.save_upward_swing_current.cumulative_close_diff  = abs(self.save_upward_swing_current.new_high_candle.close - self.save_upward_swing_current.close)

                        upward_swings.append(self.save_upward_swing_current)

                    downward_swings = self.find_downward_swings_from_high(self.track_all_candles, 2, True, None, True)
                    if len(downward_swings) == 0 and not self.save_downward_swing_current:
                        lowest_price_candle = min(self.track_all_candles, key=lambda candle: candle.low)
                        downward_swings = self.find_downward_swings_from_high(self.track_all_candles, 2, True, lowest_price_candle.datetime, True, True, False)

                    if len(downward_swings) == 1:
                        if self.save_downward_swing_current and self.save_downward_swing_current.new_low_candle and not self.save_downward_swing_current.new_low_candle.new_high_candle:
                            downward_swing_current = downward_swings[-1]
                            if downward_swing_current.new_low_candle.close > self.save_downward_swing_current.new_low_candle.close and downward_swing_current.new_low_candle.low > self.save_downward_swing_current.new_low_candle.low:
                                downward_swings.clear()

                    if len(downward_swings) >= 2:
                        downward_swings = self.combine_rsi_stoch_fib_numbers(downward_swings)
                        if len(downward_swings) == 1:
                            downward_swing_current = downward_swings[-1]
                            if not self.save_downward_swing_current:
                                self.save_downward_swing_current = copy.deepcopy(downward_swing_current)
                            else:
                                self.save_downward_swing_previous = copy.deepcopy(self.save_downward_swing_current)
                                self.save_downward_swing_current = copy.deepcopy(downward_swing_current)
                            downward_swings.clear()


                        if len(downward_swings) >= 2:
                            downward_swing_previous = downward_swings[-2]
                            downward_swing_current = downward_swings[-1]
                            self.save_downward_swing_current = copy.deepcopy(downward_swing_current)
                            self.save_downward_swing_previous = copy.deepcopy(downward_swing_previous)
                            downward_swings.clear()

                    if len(downward_swings) == 0 and self.save_downward_swing_current:
                        if current_candle.close < self.save_downward_swing_current.new_low_candle.close and  current_candle.low < self.save_downward_swing_current.new_low_candle.low:
                            self.save_downward_swing_current.new_low_candle = current_candle
                            self.save_downward_swing_current.cumulative_close_diff  = abs(self.save_downward_swing_current.new_low_candle.close - self.save_downward_swing_current.close)
                        downward_swings.append(self.save_downward_swing_current)

                    if len(upward_swings) >= 1:
                        upward_swing_current = upward_swings[-1]
                        self.save_upward_swing_current = upward_swing_current
                        self.update_higher_candle(self.save_upward_swing_current)
                        self.add_or_update_swing(self.save_upward_swing_current.datetime, self.save_upward_swing_current)
                        if upward_swing_current.is_new_high and not short_condition and not pre_condition_short:
                            converting_to_short, pre_condition_short = self.is_extreme_internal_swing_bearish_divergence_triggered(upward_swing_current, current_candle)
                            if converting_to_short:
                                short_condition = True

                        if upward_swing_current.is_new_high and not short_condition and not pre_condition_short and self.save_upward_swing_previous:
                            converting_to_short, pre_condition_short = self.is_extreme_external_swing_bearish_divergence_triggered(upward_swing_current, current_candle)
                            if converting_to_short:
                                short_condition = True

                        if upward_swing_current.is_new_high and not short_condition and not pre_condition_short:
                            converting_to_short, pre_condition_short = self.is_non_extreme_internal_bearish_divergence(upward_swing_current, current_candle)
                            if converting_to_short:
                                short_condition = True

                        if upward_swing_current.is_new_high and not short_condition and not pre_condition_short:
                            converting_to_short, pre_condition_short = self.is_non_extreme_internal_bearish_divergence_only_pre_condition(upward_swing_current, current_candle)


                    if len(downward_swings) >= 1:
                        downward_swing_current = downward_swings[-1]
                        self.save_downward_swing_current = downward_swing_current
                        self.update_lower_candle(self.save_downward_swing_current)
                        self.add_or_update_swing(self.save_downward_swing_current.datetime, self.save_downward_swing_current)
                        if downward_swing_current.is_new_low and not buy_condition :
                            converting_to_buy, pre_condition_buy = self.is_extreme_internal_swing_bullish_divergence_triggered(downward_swing_current, current_candle)
                            if converting_to_buy:
                                buy_condition = True

                        if downward_swing_current.is_new_low and not buy_condition and self.save_downward_swing_previous:
                            converting_to_buy, pre_condition_buy = self.is_extreme_external_swing_bullish_divergence_triggered(downward_swing_current, current_candle)
                            if converting_to_buy:
                                buy_condition = True

                        if downward_swing_current.is_new_low and not buy_condition:
                            converting_to_buy, pre_condition_buy = self.is_non_extreme_internal_bullish_divergence(downward_swing_current, current_candle)
                            if converting_to_buy:
                                buy_condition = True

                if short_condition and buy_condition:
                    if self.real_buy_divergence_candle.end_candle.index > self.real_short_divergence_candle.end_candle.index:
                        short_condition = False
                    else:
                        buy_condition = False

                if buy_condition:
                    if self.current_candle.rsi_13 < 55 and self.current_candle.rsi_13 > 45:
                        if self.previous_lowest_rsi_candle:
                            if self.current_candle.rsi > self.previous_lowest_rsi_candle.rsi and self.current_candle.stoch_k < self.previous_lowest_rsi_candle.stoch_k:
                                buy_condition = False
                                self.add_messages(f"<b>Cancelled</b> Buy, Due to rsi_13 is between 45 and 55 and current candle rsi {self.current_candle.rsi} is greater then previous_lowest_rsi_candle rsi {self.previous_lowest_rsi_candle.rsi}")

                if short_condition:
                    if self.current_candle.rsi_13 < 55 and self.current_candle.rsi_13 > 45:
                        if self.previous_highest_rsi_candle:
                            if self.current_candle.rsi > self.previous_highest_rsi_candle.rsi and self.current_candle.stoch_k < self.previous_highest_rsi_candle.stoch_k:
                                short_condition = False
                                self.add_messages(f"<b>Cancelled</b> Short, Due to rsi_13 is between 45 and 55 and current candle rsi {self.current_candle.rsi} is greater then previous_lowest_rsi_candle rsi {self.previous_highest_rsi_candle.rsi}")

                if buy_condition:
                    short_divergence_info = self.get_divergence_info(self.current_candle.index , "SHORT")
                    buy_divergence_info = self.get_divergence_info(self.current_candle.index , "BUY")
                    if short_divergence_info and short_divergence_info.is_extreme:
                        if self.current_candle.index ==  short_divergence_info.end_candle.index:
                            if self.current_candle.close < short_divergence_info.start_candle.high:
                                buy_condition = False
                                self.add_messages(f"<b>Cancelled</b> Buy, The current candle did close above high of short divergence start candle  {short_divergence_info.start_candle.rsi}")
                        if buy_divergence_info and buy_divergence_info.end_candle.index  <  short_divergence_info.start_candle.index:
                            buy_condition = False
                            self.add_messages(f"<b>Cancelled</b> Buy cancelled due to latest short divergence")

                if buy_condition:
                    find_previous_highest_rsi_13_candle = self.find_previous_highest_rsi_13_candle_latest(self.current_candle , self.track_all_candles)
                    if find_previous_highest_rsi_13_candle:
                        if self.current_candle.rsi > find_previous_highest_rsi_13_candle.rsi and self.current_candle.stoch_k < find_previous_highest_rsi_13_candle.stoch_k:
                            buy_condition = False
                            self.add_messages(f"<b>Cancelled</b> Buy cancelled due to divergence RSI & RSI_K Divergence , Candle Used Start # {find_previous_highest_rsi_13_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")
                            conditons_reason = f"<b>Cancelled</b> Buy cancelled due to divergence RSI & RSI_K Divergence , Candle Used Start # {find_previous_highest_rsi_13_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}"
                            self.log_condition("First Buy Cancelled Due to RSI & K Divergence", conditons_reason, self.current_candle.index )


                if buy_condition and (self.current_candle.body < 0 or (self.current_candle.open == self.current_candle.close)) :
                    buy_condition = False
                    self.add_helper_messages(f"Buy <b>Cancelled</b>  Because Current Candle is Red")
                    if self.real_buy_divergence_candle and self.real_buy_divergence_candle.end_candle:
                        self.real_buy_divergence_candle.end_candle.divergence_used = False
                        self.update_divergence_used_in_memory_to_false(self.real_buy_divergence_candle.end_candle)


                if short_condition and (self.current_candle.body > 0 or self.current_candle.open == self.current_candle.close):
                    short_condition = False
                    self.add_helper_messages(f"Short <b>Cancelled</b> because current candle is green candle")
                    if self.real_short_divergence_candle and self.real_short_divergence_candle.end_candle:
                        self.real_short_divergence_candle.end_candle.divergence_used = False
                        self.update_divergence_used_in_memory_to_false(self.real_short_divergence_candle.end_candle)


                if not buy_condition and self.current_candle.body > 0 :
                    if "02:01 PM" in self.current_candle.date:
                        print("Put Break Point")
                        previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                        previous_lowest_rsi_candle = None
                        candle_used = None
                        if previous_highest_rsi_candle:
                            previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(previous_highest_rsi_candle, self.track_all_candles, False)
                        previous_highest_rsi_13_candle = self.find_previous_highest_rsi_13_candle_latest(self.current_candle, self.track_all_candles)
                        if previous_lowest_rsi_candle and previous_lowest_rsi_candle.high < previous_highest_rsi_candle.low and self.current_candle.rsi > previous_lowest_rsi_candle.rsi and previous_lowest_rsi_candle.stoch_k > self.current_candle.stoch_k:
                            buy_condition = False
                            candle_used = previous_lowest_rsi_candle
                        if previous_highest_rsi_13_candle and self.current_candle.rsi < previous_highest_rsi_13_candle.rsi and previous_highest_rsi_13_candle.rsi_13 > self.current_candle.rsi_13:
                            buy_condition = False
                            candle_used = previous_highest_rsi_13_candle

                        if not buy_condition:
                            buy_condition = False
                            self.add_helper_messages(f"First Buy Cancelled Due to Overlap  , Candle used Start # {candle_used.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")
                            conditons_reason = f"First Buy Cancelled Due to Overlap , Candle used Start # {candle_used.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} "
                            self.log_condition("First Buy Cancelled Due to Overlap", conditons_reason, self.current_candle.index )


                if not short_condition and not buy_condition:
                    if self.candle_close_above_short_divergence_buy and not self.candle_close_below_buy_divergence_short:
                        if self.current_candle.close > self.candle_close_above_short_divergence_buy.high and self.current_candle.low > self.candle_close_above_short_divergence_buy.open:
                            buy_condition = True
                            self.add_helper_messages(f"First Buy, Candle closed above Short Divergence Candle   , Candle used Start # {self.candle_close_above_short_divergence_buy.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")

                    if self.candle_close_below_buy_divergence_short and not self.candle_close_above_short_divergence_buy:
                        if self.current_candle.close < self.candle_close_below_buy_divergence_short.low and self.current_candle.high < self.candle_close_below_buy_divergence_short.open:
                            short_condition = True
                            self.add_helper_messages(f"First Short, Candle closed below Buy Divergence Candle   , Candle used Start # {self.candle_close_below_buy_divergence_short.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")

                    short_divergence_info = self.get_divergence_info(self.current_candle.index , "SHORT")
                    buy_divergence_info = self.get_divergence_info(self.current_candle.index , "BUY")
                    if short_divergence_info and not self.candle_close_above_short_divergence_buy:
                        self.candle_close_above_short_divergence_buy = short_divergence_info.end_candle
                    if buy_divergence_info and not self.candle_close_below_buy_divergence_short:
                        self.candle_close_below_buy_divergence_short = buy_divergence_info.end_candle



                if short_condition:
                    stop_loss = self.get_stop_loss(False)
                    self.candle_close_above_short_divergence_buy = None
                    self.candle_close_below_buy_divergence_short = None
                    self.update_converting_to_short(None, None)
                    if self.real_short_divergence_candle:
                        self.add_helper_messages("First Divergence condition met for Short and Shorted, This is First Trade")
                        self.add_helper_messages(f"Divergence condition met for Short And Short Divergence Candle Used Start # {self.real_short_divergence_candle.start_candle.index.strftime('%I:%M %p')}, End # {self.real_short_divergence_candle.end_candle.index.strftime('%I:%M %p')}")

                if buy_condition:
                    stop_loss = self.get_stop_loss(True)
                    self.candle_close_above_short_divergence_buy = None
                    self.candle_close_below_buy_divergence_short = None
                    self.update_converting_to_buy(None, None)
                    if self.real_buy_divergence_candle:
                        self.add_helper_messages("First Divergence condition met for Buy and Bought, This is First Trade")
                        self.add_helper_messages(f"Divergence condition met for Buy And Buy Divergence Candle Used Start # {self.real_buy_divergence_candle.start_candle.index.strftime('%I:%M %p')}, End # {self.real_buy_divergence_candle.end_candle.index.strftime('%I:%M %p')}")

            if self.in_trade:
                if "03:13 PM" in self.current_candle.date:
                    print("Put Break Point")

                if self.buy_order:

                    if "11:32 AM" in self.current_candle.date:
                        print("Put Break Point")
                    self.short_divergence_candle = None
                    if self.copy_data and self.add_candles_buy_side:
                        self.track_all_candles_during_buy = self.add_candles_buy_side.copy()
                        self.add_candles_buy_side = None
                        self.copy_data = False

                    self.track_all_candles_during_short.clear()

                    upward_swings = self.find_upward_swings_from_low(self.track_all_candles_during_buy, upward_candles_to_consider, True, None, True)
                    if len(upward_swings) == 1:
                        upward_swing_current = upward_swings[-1]
                        if self.save_upward_swing_current and self.save_upward_swing_current.new_high_candle:
                            if not self.save_upward_swing_current.new_high_candle.new_low_candle or (self.save_upward_swing_current.new_high_candle.new_low_candle and upward_swing_current.new_high_candle.close < self.save_upward_swing_current.new_high_candle.new_low_candle.high):
                                if upward_swing_current.new_high_candle.close < self.save_upward_swing_current.new_high_candle.close and upward_swing_current.new_high_candle.high < self.save_upward_swing_current.new_high_candle.high:
                                    upward_swings.clear()

                    if len(upward_swings) == 1:
                        upward_swing_current = upward_swings[-1]
                        if self.save_upward_swing_current and upward_swing_current.datetime != self.save_upward_swing_current.datetime:
                            if self.save_upward_swing_current.datetime < self.save_upward_swing_current.new_high_candle.datetime:
                                upward_swings.clear()
                                upward_swings.append(self.save_upward_swing_current)
                                upward_swings.append(upward_swing_current)

                    if len(upward_swings) >= 2:
                        previous_upward_swing = upward_swings[-2]
                        if previous_upward_swing.new_high_candle and not previous_upward_swing.new_high_candle.new_low_candle:
                            upward_swings = self.combine_rsi_stoch_fib_numbers(upward_swings)
                            if len(upward_swings) == 2:
                                upward_swing_current = upward_swings[-2]
                                upward_swing_latest = upward_swings[-1]
                                if upward_swing_current.new_high_candle and upward_swing_latest.new_high_candle:
                                    if upward_swing_current.new_high_candle.datetime == upward_swing_latest.new_high_candle.datetime:
                                        upward_swings.clear()
                                        upward_swings.append(upward_swing_current)

                            if len(upward_swings) == 1:
                                upward_swing_current = upward_swings[-1]
                                if not self.save_upward_swing_current:
                                    self.save_upward_swing_current = copy.deepcopy(upward_swing_current)
                                else:
                                    #self.save_upward_swing_previous = copy.deepcopy(self.save_upward_swing_current)
                                    if upward_swing_current.new_high_candle.datetime == self.save_upward_swing_current.new_high_candle.datetime:
                                        upward_swing_current.new_high_candle = self.save_upward_swing_current.new_high_candle
                                    self.save_upward_swing_current = copy.deepcopy(upward_swing_current)
                                    #pass
                                self.track_all_candles_during_buy.clear()
                                upward_swings.clear()


                        if len(upward_swings) == 2:
                            upward_swing_previous = upward_swings[-2]
                            upward_swing_current = upward_swings[-1]
                            if upward_swing_current.new_high_candle.datetime != upward_swing_previous.new_high_candle.datetime and self.save_upward_swing_current:
                                #self.save_upward_swing_current.previous_swing_info = copy.deepcopy(self.save_upward_swing_previous)
                                self.save_upward_swing_previous = copy.deepcopy(self.save_upward_swing_current)
                                self.save_upward_swing_current = copy.deepcopy(upward_swing_current)
                                self.track_all_candles_during_buy = [candle for candle in self.track_all_candles_during_buy if candle.datetime >= upward_swing_current.datetime]
                            if upward_swing_current.new_high_candle.datetime != upward_swing_previous.new_high_candle.datetime and not self.save_upward_swing_current:
                                #upward_swing_previous.previous_swing_info = copy.deepcopy(self.save_upward_swing_previous)
                                self.save_upward_swing_previous = copy.deepcopy(upward_swing_previous)
                                self.save_upward_swing_current = copy.deepcopy(upward_swing_current)
                                self.track_all_candles_during_buy = [candle for candle in self.track_all_candles_during_buy if candle.datetime >= upward_swing_current.datetime]
                            upward_swings.clear()

                    if len(upward_swings) == 0 and self.save_upward_swing_current:
                        if current_candle.close >= self.save_upward_swing_current.new_high_candle.close and current_candle.body > 0:
                            self.save_upward_swing_current.new_high_candle = current_candle
                        upward_swings.append(self.save_upward_swing_current)

                    if len(upward_swings) >= 1:
                        upward_swing_current = upward_swings[-1]
                        self.save_upward_swing_current = upward_swing_current
                        self.add_or_update_swing(self.save_upward_swing_current.datetime, self.save_upward_swing_current)
                        self.update_higher_candle(self.save_upward_swing_current)

                        if upward_swing_current.is_new_high:
                            converting_to_short, pre_condition_short = self.check_short_divergence_during_buy()

                        downward_swings = self.find_downward_swings_from_high(self.track_all_candles_during_buy, downward_candles_to_consider, True, upward_swing_current.new_high_candle.datetime, False)
                        if len(downward_swings) >= 1 and not converting_to_short and not sell_condition:
                            downward_swing_current = downward_swings[-1]
                            if self.current_candle.close < downward_swing_current.new_low_candle.close:
                                downward_swing_current.new_low_candle = self.current_candle
                            self.save_downward_swing_current = downward_swing_current
                            self.update_lower_candle(self.save_downward_swing_current)
                            self.add_or_update_swing(self.save_downward_swing_current.datetime, self.save_downward_swing_current)


                            if downward_swing_current.new_low_candle:
                                upward_swings = self.find_upward_swings_from_low(self.track_all_candles_during_buy, downward_candles_to_consider, True, downward_swing_current.new_low_candle.datetime, False)
                                if len(upward_swings) > 0:
                                    upward_swing = upward_swings[-1]
                                    if upward_swing.datetime != self.save_upward_swing_current.datetime:
                                        if self.save_upward_swing_previous:
                                            #self.save_upward_swing_previous.previous_swing_info = None
                                            #self.save_upward_swing_current.previous_swing_info = self.save_upward_swing_previous
                                            self.save_upward_swing_previous = copy.deepcopy(self.save_upward_swing_current)
                                            self.save_upward_swing_current = upward_swing
                                            self.update_higher_candle(self.save_upward_swing_current)
                                            self.add_or_update_swing(self.save_upward_swing_current.datetime, self.save_upward_swing_current)


                                        if self.save_downward_swing_previous and self.save_downward_swing_previous.datetime != self.save_downward_swing_current.datetime:
                                            #self.save_downward_swing_previous.previous_swing_info = None
                                            #self.save_downward_swing_current.previous_swing_info = self.save_downward_swing_previous
                                            self.save_downward_swing_previous = copy.deepcopy(self.save_downward_swing_current)
                                            candles_clean_up_list = [candle for candle in self.track_all_candles_during_buy if candle.datetime >= downward_swing_current.datetime]
                                            self.track_all_candles_during_buy = candles_clean_up_list.copy()
                                        if not self.save_downward_swing_previous :
                                            self.save_downward_swing_previous = copy.deepcopy(self.save_downward_swing_current)
                                            candles_clean_up_list = [candle for candle in self.track_all_candles_during_buy if candle.datetime >= downward_swing_current.datetime]
                                            self.track_all_candles_during_buy = candles_clean_up_list.copy()

                    converting_to_buy, pre_condition_buy = self.check_buy_divergence_during_buy()

                    if not pre_condition_short:
                        converting_to_short, pre_condition_short = self.check_short_divergence_during_buy()


                    if converting_to_short and self.real_short_divergence_candle:
                        if self.real_short_divergence_candle.end_candle.index < self.in_trade_candle.index:
                            converting_to_short = False
                            self.remove_divergence_info(self.current_candle.index , self.real_short_divergence_candle)
                        # if converting_to_short and self.real_short_divergence_candle.is_extreme:
                        #     highest_price_candle = self.get_highest_price_between_start_and_end_divergence(self.real_short_divergence_candle.start_candle.index, self.real_short_divergence_candle.end_candle.index, self.real_short_divergence_candle.end_candle)
                        #     if highest_price_candle:
                        #         converting_to_short = False
                        #         self.remove_divergence_info(self.current_candle.index , "SHORT")



                    start_candle = None
                    end_candle = None

                    if converting_to_short:
                        short_divergence_info = self.get_divergence_info(self.current_candle.index , "SHORT")
                        if short_divergence_info:
                            time_difference = abs(short_divergence_info.start_candle.index - short_divergence_info.end_candle.index)
                            if time_difference > timedelta(minutes=30):
                                next_higest_green_candle = self.find_green_candle_with_highest_rsi_closest_to_candle2(short_divergence_info.start_candle, short_divergence_info.end_candle, self.track_all_candles)
                                if next_higest_green_candle:
                                    time_difference = abs(next_higest_green_candle.index - short_divergence_info.end_candle.index)
                            if time_difference < timedelta(minutes=30):
                                if not self.is_extreme_violation(short_divergence_info):
                                    self.add_helper_messages(f"Divergence condition met for Short And Short Divergence Candle Used Start # {short_divergence_info.start_candle.index.strftime('%I:%M %p')}, End # {short_divergence_info.end_candle.index.strftime('%I:%M %p')}")
                                    self.add_helper_messages(f"Short Divergence Candle used # {self.short_divergence_candle.index.strftime('%I:%M %p')}")
                                    start_candle = short_divergence_info.start_candle
                                    end_candle = short_divergence_info.end_candle
                                else:
                                    converting_to_short = False
                                    self.remove_divergence_info(self.current_candle.index , short_divergence_info)
                            else:
                                converting_to_short = False
                                self.remove_divergence_info(self.current_candle.index , short_divergence_info)



                    if not converting_to_short:
                        converting_to_short, pre_condition_short = self.is_artificial_bearish_divergence()
                        if converting_to_short:
                            self.short_divergence_candle = self.second_high_rsi_candle_during_buy
                            self.add_helper_messages(f"Artificial Short Divergence created between {self.first_high_rsi_candle_during_buy.index.strftime('%I:%M %p')} and {self.second_high_rsi_candle_during_buy.index.strftime('%I:%M %p')}")

                    if not converting_to_short:
                        short_divergence_info = self.get_latest_pre_condition_divergence("SHORT")
                        if short_divergence_info and not self.is_extreme_violation(short_divergence_info) and not short_divergence_info.end_candle.divergence_used:
                            time_difference = abs(short_divergence_info.start_candle.index - short_divergence_info.end_candle.index)
                            if time_difference < timedelta(minutes=30):
                                close_time_difference = None
                                highest_price_close = None
                                if USE_HIGH_LOW_PRICE:
                                    highest_price_close = self.get_highest_close_price_between_dates(short_divergence_info.end_candle.index, self.current_candle.index)
                                if highest_price_close:
                                    close_time_difference = abs(short_divergence_info.end_candle.index - highest_price_close.index)
                                if (self.current_candle.close < short_divergence_info.end_candle.low
                                        or (highest_price_close and self.current_candle.close < highest_price_close.low and close_time_difference < timedelta(minutes=5) and not (self.current_candle.high > short_divergence_info.start_candle.low)) \
                                        or (highest_price_close and highest_price_close.rsi > 94 and highest_price_close.stoch_k < 80
                                            and highest_price_close.rsi_13 > 55 and highest_price_close.body < 0
                                            and highest_price_close.previous_body < 0 and close_time_difference < timedelta(minutes=5))):
                                    converting_to_short = True
                                    short_divergence_info.end_candle.divergence_used = True
                                    self.update_divergence_used_in_memory(short_divergence_info.end_candle)
                                    self.short_divergence_candle = self.get_candle_by_index(short_divergence_info.end_candle.index)
                                    if highest_price_close:
                                        self.short_divergence_candle = self.get_candle_by_index(highest_price_close.index)
                                    self.add_helper_messages(f"Divergence condition met for Short And Short Divergence Candle Used Start : "
                                                             f"{short_divergence_info.start_candle.index.strftime('%I:%M %p')} End : {short_divergence_info.end_candle.index.strftime('%I:%M %p')}")
                                    start_candle = short_divergence_info.start_candle
                                    end_candle = short_divergence_info.end_candle



                    # if not converting_to_short:
                    #     if not self.in_memory_divergence_info:
                    #         self.in_memory_divergence_info = self.get_latest_divergence("SHORT")
                    #
                    #     if  self.in_memory_divergence_info:
                    #         # Check if any highest price candle is present
                    #         highest_price_candle = self.get_highest_price_between_dates_above_divergence_end_candle(self.in_memory_divergence_info.end_candle.index, self.current_candle.index)
                    #         if not highest_price_candle:
                    #             if self.current_candle.close <  self.in_memory_divergence_info.end_candle.low and self.current_candle.body > 0:
                    #                 self.in_memory_short_divergence_candle = self.current_candle
                    #
                    #     if self.in_memory_short_divergence_candle:
                    #         if self.current_candle.close < self.in_memory_short_divergence_candle.low:
                    #             if self.buy_divergence_candle and not self.buy_divergence_candle.is_extreme_buy_sell:
                    #                 converting_to_short = True
                    #                 self.add_helper_messages(f"Shorted  because current candle closed below Short Divergence candle  {self.in_memory_short_divergence_candle.index.strftime('%I:%M %p')}")
                    #                 self.add_helper_messages(f"This is second artificial divergence trigger because it didn't close below latest short divergence candle Start : {self.in_memory_divergence_info.start_candle.index.strftime('%I:%M %p')}, End : {self.in_memory_divergence_info.end_candle.index.strftime('%I:%M %p')}")
                    #                 self.short_divergence_candle = self.in_memory_short_divergence_candle
                    #             if  self.buy_divergence_candle and self.buy_divergence_candle.is_extreme_buy_sell:
                    #                 if self.current_candle.close < self.buy_divergence_candle.low:
                    #                     converting_to_short = True
                    #                     self.add_helper_messages(f"Shorted  because current candle closed below Short Divergence candle  {self.in_memory_short_divergence_candle.index.strftime('%I:%M %p')}")
                    #                     self.add_helper_messages(f"This is second artificial divergence trigger because it didn't close below latest short divergence candle Start : {self.in_memory_divergence_info.start_candle.index.strftime('%I:%M %p')}, End : {self.in_memory_divergence_info.end_candle.index.strftime('%I:%M %p')}")
                    #                     self.short_divergence_candle = self.in_memory_short_divergence_candle


                    if self.current_candle.rsi < 94 and self.current_candle.previous_rsi > 94 and not self.second_high_rsi_candle_during_buy:
                        self.first_high_rsi_candle_during_buy = self.get_candle_by_index(self.current_candle.previous_index)

                    if "02:23 PM" in self.current_candle.date:
                        print("Put Break Point")


                    # This Condition is helping on chart 5/8  TODO
                    # Helping 5/8, 4/23, 4/17
                    # Not Helping 4/8
                    # Remove is giving  negative  impact -2875
                    if not converting_to_short and self.current_candle.body < 0:
                        high_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                        if high_rsi_candle and high_rsi_candle.index == self.in_trade_candle.index:
                            next_high_rsi_candle = self.find_previous_highest_rsi_candle_latest(high_rsi_candle, self.track_all_candles, False)
                            if next_high_rsi_candle and next_high_rsi_candle.close < high_rsi_candle.close and next_high_rsi_candle.high <  high_rsi_candle.high and next_high_rsi_candle.rsi >  high_rsi_candle.rsi:
                                if self.current_candle.close < high_rsi_candle.low and self.current_candle.high < high_rsi_candle.high:
                                    converting_to_short = True
                                    self.short_divergence_candle = high_rsi_candle
                                    start_candle = next_high_rsi_candle
                                    end_candle = high_rsi_candle
                                    self.add_helper_messages(f"Divergence condition met for Short And Short Divergence Candle Used Start # {start_candle.index.strftime('%I:%M %p')}, End # {end_candle.index.strftime('%I:%M %p')}")
                                    conditons_reason = f"Divergence condition met for Short And Short Divergence Candle Used Start # {start_candle.index.strftime('%I:%M %p')}, End # {end_candle.index.strftime('%I:%M %p')}"
                                    self.log_condition("Divergence condition met for Short - New One", conditons_reason, self.current_candle.index )


                    # This Condition is helping on chart 5/8  TODO
                    # Helping 4/25, 4/9, 5/8, 4/17, 4/15, 4/23, 5/12, 5/5, 5/21, 4/16
                    # Not Helping 4/30, 4/11, 4/29, 4/14, 5/19, 3/31, 3/27, 4/22, 5/14
                    # Remove is giving  negative  impact -4350
                    cancel_due_to_extreme = False
                    cancel_short = False
                    if converting_to_short:
                        if "09:45 AM" in self.current_candle.date:
                            print("Put Break Point")
                        if start_candle and end_candle:
                            if (start_candle.rsi < 94 and start_candle.stoch_k < 80
                                and end_candle.rsi < 94 and end_candle.stoch_k < 80) and self.current_candle.rsi_13 > 45 and not end_candle.check_rsi_13_close_below:
                                converting_to_short = False
                                cancel_short = True
                                cancel_due_to_extreme = True
                                self.add_helper_messages(f"One Short <b>Cancelled</b>  because None of the divergence is extreme")
                                if end_candle:
                                    end_candle.divergence_used = False
                                    self.update_divergence_used_in_memory_to_false(end_candle)


                    # This Condition is helping on chart 5/8  TODO
                    # Helping 5/8, 4/28, 4/2
                    # Not Helping 4/4, 4/14, 4/16, 5/12, 5/13, 5/6, 4/15, 5/2, 4/9, 5/22, 5/14, 4/22
                    # Remove is giving  negative  impact +3750
                    if not converting_to_short and self.first_high_rsi_candle_during_buy and self.first_high_rsi_candle_during_buy.index > self.in_trade_candle.index:
                        if self.current_candle.close < self.first_high_rsi_candle_during_buy.low and self.current_candle.rsi< 5:
                            converting_to_short = True
                            self.add_helper_messages(f"Shorted because current candle closed below highest rsi candle   {self.first_high_rsi_candle_during_buy.index.strftime('%I:%M %p')}")
                            self.short_divergence_candle =  self.current_candle
                            self.short_divergence_candle.is_extreme_buy_sell = True

                    # This Condition is helping on chart 5/8  TODO
                    # Helping 5/8, 4/15, 5/12, 5/7,
                    # Not Helping 4/7, 4/29, 5/20, 5/6
                    # Remove is giving  positive  impact  75
                    if not converting_to_short:
                        if self.in_trade_candle:
                            short_divergence_info = self.get_divergence_info(self.in_trade_candle.index, "SHORT")
                            if short_divergence_info:
                                time_difference = abs(self.current_candle.index - self.in_trade_candle.index)
                                if time_difference < timedelta(minutes=2) and self.current_candle.close < self.in_trade_candle.close and self.current_candle.rsi_13 < 45 and self.in_trade_candle.rsi_13 < 45:
                                    converting_to_short = True
                                    self.short_divergence_candle = self.current_candle
                                    self.add_helper_messages(f"Shorted immediately current candle close below previous candle and both current candle rsi_13 and previous candle rsi_!3 are below 45")


                    # This Condition is helping on chart 5/8  TODO
                    # Helping 5/8, 5/2, 4/25
                    # Not Helping 4/11
                    # Remove is giving  negative  impact -2675
                    if converting_to_short:
                        if "12:01 PM" in self.current_candle.date:
                            print("Put Break Point")

                        if self.in_trade_candle:
                            short_divergence_info = self.get_divergence_info(self.current_candle.index, "SHORT")
                            if short_divergence_info and self.current_candle.rsi_13 > 55 and self.current_candle.close > short_divergence_info.end_candle.low:
                                time_difference = abs(short_divergence_info.start_candle.index - short_divergence_info.end_candle.index)
                                if time_difference > timedelta(minutes=30):
                                    converting_to_short = False
                                    self.short_divergence_candle = None
                                    self.add_helper_messages(f"Script Five, Short <b>Cancelled</b>  the divergence start and end is greater then 30 minutes,  Candle used Start # {short_divergence_info.start_candle.index.strftime('%I:%M %p')}, End # {short_divergence_info.end_candle.index.strftime('%I:%M %p')}")
                                    conditons_reason = f"Short <b>Cancelled</b>  the divergence start and end is greater then 30 minutes,  Candle used Start # {short_divergence_info.start_candle.index.strftime('%I:%M %p')}, End # {short_divergence_info.end_candle.index.strftime('%I:%M %p')}"
                                    self.log_condition("Script Five, Short Cancelled the divergence start and end is greater then 30 minutes", conditons_reason, self.current_candle.index )


                    all_are_high_nullified = False
                    shorted_cancelled_all_are_high = False

                    # This Condition is helping on chart 5/8  TODO
                    # Helping 4/10, 5/8, 4/9, 4/30, 4/23, 5/5, 5/13, 5/12, 5/6, 5/1
                    # Not Helping 4/14, 4/8, 5/20, 4/15, 5/2, 4/4, 5/14, 4/22, 3/27, 5/22, 3/28, 4/17
                    # Remove is giving  negative  impact -4100
                    if converting_to_short:

                        if "03:40 PM" in self.current_candle.date:
                            print("Put Break Point")

                        #TODO Need to Revist this conditon in fourth script its using extreme candle
                        previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, True)
                        if previous_highest_rsi_candle:
                            time_difference = abs(self.current_candle.index - self.in_trade_candle.index)
                            if time_difference < timedelta(minutes=20): #and previous_highest_rsi_candle.close > self.current_candle.close:
                                if previous_highest_rsi_candle.rsi_13 > 55 and previous_highest_rsi_candle.rsi > 94 and previous_highest_rsi_candle.stoch_k > 80 \
                                        and self.current_candle.close > self.in_trade_candle.low:
                                    continue_to_skip = True
                                    previous_lowest_rsi_candle = self.find_red_candle_from_high(previous_highest_rsi_candle.index, self.track_all_candles)
                                    if previous_lowest_rsi_candle:
                                        if (self.current_candle.rsi < previous_lowest_rsi_candle.rsi or previous_lowest_rsi_candle.stoch_k < 20) and self.current_candle.close < previous_highest_rsi_candle.low and (self.current_candle.rsi_13 < 55 or self.current_candle.close < previous_lowest_rsi_candle.low):
                                            continue_to_skip = False
                                            all_are_high_nullified = True
                                    if continue_to_skip:
                                        converting_to_short = False
                                        self.short_divergence_candle = None
                                        cancel_short = True
                                        shorted_cancelled_all_are_high = True
                                        if end_candle:
                                            end_candle.divergence_used = False
                                            self.update_divergence_used_in_memory_to_false(end_candle)
                                        self.add_helper_messages(f"Shorted Cancelled All are high,  Candle used Start # {self.in_trade_candle.index.strftime('%I:%M %p')}, End # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}")


                    lowest_rsi_short = False

                    # This Condition is helping on chart 5/8  TODO
                    # Helping 4/17, 4/14, 5/8, 4/8, 4/10, 4/3, 3/28, 4/23, 4/22, 5/14, 5/20, 5/2, 5/21, 4/24, 5/16, 5/12
                    # Not Helping 4/9, 4/15, 4/2, 4/30, 5/15, 5/7, 4/16, 3/27,3/31, 5/5, 4/28, 5/9
                    # 5/8 @ 10:02 Neg
                    # Remove is giving  negative  impact -4025
                    if not converting_to_short:
                        if "03:26 PM" in self.current_candle.date:
                            print("Put Break Point")
                        if self.current_candle.body < 0 and self.current_candle.previous_body > 0:
                            previous_index = pd.Timestamp(self.current_candle.previous_index).round('s')
                            previous_lowest_rsi_candle = self.find_red_candle_from_high(previous_index, self.track_all_candles)
                            if previous_lowest_rsi_candle and previous_lowest_rsi_candle.body < -0.25:
                                if self.current_candle.rsi < previous_lowest_rsi_candle.rsi and (self.current_candle.high > previous_lowest_rsi_candle.high or self.current_candle.close > previous_lowest_rsi_candle.close) and (not (self.current_candle.previous_rsi > 94 and self.current_candle.previous_stoch_k > 80) or self.current_candle.rsi_13 < 55) and self.current_candle.open <= self.current_candle.previous_close:
                                    if self.current_candle.stoch_k < 80:
                                        continue_with_short = True
                                        short_divergence_info = self.get_divergence_info(self.current_candle.index, "SHORT")
                                        if not short_divergence_info:
                                            if self.current_candle.stoch_k > previous_lowest_rsi_candle.stoch_k or self.current_candle.rsi_13 > previous_lowest_rsi_candle.rsi_13:
                                                continue_with_short = False
                                                conditons_reason = f"Script Five Added RSI 13 or K  also to check for Short,  Candle used Start # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}"
                                                self.log_condition("Script Five, Added RSI 13 or K  also to check for Short - One", conditons_reason, self.current_candle.index )
                                                self.add_helper_messages(f"Script Five, Short Cancelled One,  Added RSI 13 or K  also to check for Short,  Candle used Start # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")

                                        if continue_with_short:
                                            if self.current_candle.rsi_13 > previous_lowest_rsi_candle.rsi_13 and self.current_candle.rsi_13 > 55:
                                                continue_with_short = False
                                                conditons_reason = f"Script Five Added RSI 13 or K  also to check for Short,  Candle used Start # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}"
                                                self.log_condition("Script Five, Added RSI 13 or K  also to check for Short - Two ", conditons_reason, self.current_candle.index )
                                                self.add_helper_messages(f"Script Five , Short Cancelled Two , Added RSI 13 or K  also to check for Short,  Candle used Start # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")

                                        if continue_with_short:
                                            if self.in_trade_candle.side_ways_structure_detected:
                                                if self.current_candle.close < self.in_trade_candle.high:
                                                    if self.current_candle.close > self.buy_divergence_candle.low:
                                                        continue_with_short = False
                                                        self.add_helper_messages("Script Five, Side Way Structure - The condition  triggered to nullify converting_to_short from False to True")
                                                        conditons_reason = "Side Way Structure - The condition  triggered to nullify converting_to_short from False to True"
                                                        self.log_condition("Script Five, Side Way Structure - The condition  triggered to nullify converting_to_short from False to True", conditons_reason, self.current_candle.index )


                                        if continue_with_short:
                                            converting_to_short = True
                                            lowest_rsi_short = True
                                            self.short_divergence_candle = self.current_candle
                                            self.add_helper_messages(f"One - Shorted current rsi lower then previous lowest rsi,  Candle used Start # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")

                    # This Condition is helping on chart 5/8  TODO
                    # Helping 5/8
                    # Not Helping 4/22
                    # Remove is giving  negative  impact -1225
                    if not converting_to_short and cancel_due_to_extreme:
                        if "09:10 AM" in self.current_candle.date:
                            print("Put Break Point")
                        if self.current_candle.body < 0 and self.current_candle.previous_body < 0:
                            previous_index = pd.Timestamp(self.current_candle.previous_index).round('s')
                            previous_candle = self.get_candle_by_index(previous_index)
                            if previous_candle and previous_candle.previous_body > 0:
                                previous_index = pd.Timestamp(previous_candle.previous_index).round('s')
                                previous_lowest_rsi_candle = self.find_red_candle_from_high(previous_index, self.track_all_candles)
                                if previous_lowest_rsi_candle:
                                    if self.current_candle.rsi < previous_lowest_rsi_candle.rsi and (self.current_candle.high > previous_lowest_rsi_candle.high or self.current_candle.close > previous_lowest_rsi_candle.close) and (not (self.current_candle.previous_rsi > 94 and self.current_candle.previous_stoch_k > 80) or self.current_candle.rsi_13 < 55):
                                        if self.current_candle.stoch_k < 80:
                                            if self.current_candle.stoch_k < previous_lowest_rsi_candle.stoch_k and self.current_candle.stoch_d < previous_lowest_rsi_candle.stoch_d:
                                                if self.current_candle.close < previous_lowest_rsi_candle.close or self.current_candle.low != previous_lowest_rsi_candle.low:
                                                    converting_to_short = True
                                                    lowest_rsi_short = True
                                                    self.add_helper_messages(f"Two - Shorted current rsi lower then previous lowest rsi,  Candle used Start # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")

                    # This Condition is helping on chart 5/8  TODO
                    # Helping 5/8, 5/19
                    # Not Helping 5/7, 4/17, 4/15, 4/14, 5/21
                    # Remove is giving  negative  impact -375
                    if converting_to_short and not lowest_rsi_short:
                        if "11:02 AM" in self.current_candle.date:
                            print("Put Break Point")
                        continue_with_short = False
                        if self.current_candle.body < 0 and self.current_candle.previous_body > 0:
                            previous_index = pd.Timestamp(self.current_candle.previous_index).round('s')
                            previous_lowest_rsi_candle = self.find_red_candle_from_high(previous_index, self.track_all_candles)
                            if previous_lowest_rsi_candle:
                                if self.current_candle.rsi_13 > 55 and self.current_candle.rsi < previous_lowest_rsi_candle.rsi and (self.current_candle.stoch_k > previous_lowest_rsi_candle.stoch_k or self.current_candle.rsi_13 > previous_lowest_rsi_candle.rsi_13) \
                                        and self.current_candle.close > previous_lowest_rsi_candle.close and self.current_candle.low > previous_lowest_rsi_candle.low:

                                    continue_with_short = True

                                    if continue_with_short:
                                        converting_to_short = False
                                        self.short_divergence_candle = None
                                        cancel_short = True
                                        if end_candle:
                                            end_candle.divergence_used = False
                                            self.update_divergence_used_in_memory_to_false(end_candle)

                                        self.add_helper_messages(f"Shorted Cancelled RSI 13 above 55 and K or 13 is above and Close & Low is above,  Candle used Start # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")


                    # This Condition is helping on chart 5/8  TODO
                    # Helping 4/7, 4/11, 4/29, 4/17, 5/8, 5/19, 5/20, 4/3
                    # Not Helping 4/25, 5/13, 5/7, 4/30, 4/9, 3/27, 5/5
                    # Remove is giving  negative  impact -4525
                    high_ohlc_cancel = False
                    high_ohlc_cancel_skipped = False
                    if converting_to_short and not lowest_rsi_short:
                        if "10:14 AM" in self.current_candle.date:
                            print("Put Break Point")
                        if self.current_candle.body < 0 and self.current_candle.previous_body > 0:
                            previous_index = pd.Timestamp(self.current_candle.previous_index).round('s')
                            previous_lowest_rsi_candle = self.find_red_candle_from_high(previous_index, self.track_all_candles)
                            if previous_lowest_rsi_candle:
                                if (self.current_candle.rsi_13 > 55 and self.current_candle.close > previous_lowest_rsi_candle.close and self.current_candle.low > previous_lowest_rsi_candle.low
                                        and self.current_candle.open > previous_lowest_rsi_candle.open and self.current_candle.high > previous_lowest_rsi_candle.high):

                                    high_ohlc_cancel = True
                                    if high_ohlc_cancel:
                                        if not (self.current_candle.open > previous_lowest_rsi_candle.open and self.current_candle.high > previous_lowest_rsi_candle.high and previous_lowest_rsi_candle.low > self.current_candle.low and previous_lowest_rsi_candle.close > self.current_candle.close) \
                                                and not (self.current_candle.close > previous_lowest_rsi_candle.open) \
                                                and self.current_candle.rsi < previous_lowest_rsi_candle.rsi \
                                                and self.current_candle.stoch_k < previous_lowest_rsi_candle.stoch_k \
                                                and self.current_candle.stoch_d < previous_lowest_rsi_candle.stoch_d:
                                            high_ohlc_cancel = False
                                            high_ohlc_cancel_skipped = True

                                    if start_candle and end_candle and high_ohlc_cancel:
                                        if start_candle.rsi < 94 and  end_candle.rsi < 94:
                                            previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_extreme(start_candle, self.track_all_candles)
                                            if previous_highest_rsi_candle:
                                                if (previous_highest_rsi_candle.rsi > 94
                                                        and previous_highest_rsi_candle.close < end_candle.close
                                                        and previous_highest_rsi_candle.high < end_candle.high
                                                        and self.current_candle.close < end_candle.low):
                                                    high_ohlc_cancel = False
                                                    high_ohlc_cancel_skipped = True


                                    # Added this condition to fix 2025-04-29 chart to skip short at 11:02 AM
                                    if high_ohlc_cancel and start_candle and end_candle:
                                        if start_candle.rsi > 94 or end_candle.rsi > 94:
                                            if end_candle.rsi_13 > start_candle.rsi_13 and start_candle.rsi > end_candle.rsi:
                                                # Get Highest RSI Candle in between start and end candle
                                                if "11:02 AM" in self.current_candle.date:
                                                    print("Put Break Point")

                                                high_price_compare = start_candle.high
                                                closest_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(end_candle, self.track_all_candles, False)
                                                if closest_highest_rsi_candle:
                                                    if start_candle.close < closest_highest_rsi_candle.close < end_candle.close and closest_highest_rsi_candle.rsi > end_candle.rsi:
                                                        high_price_compare = closest_highest_rsi_candle.high

                                                if (self.current_candle.previous_body > 0 and self.current_candle.close < high_price_compare) or (self.current_candle.previous_body < 0 and self.current_candle.body < 0 and self.current_candle.open < self.current_candle.previous_close):
                                                    ## TODO IMPORTANT:
                                                    ## In LIVE BOT . GET THE OPEN PRICE OF THE CANDLE , GET THE OPEN PRICE OF THE CANDLE, OPEN PRICE SHOULD BELOW PREVIOUS CANDLE CLOSE
                                                    high_ohlc_cancel = False
                                                    high_ohlc_cancel_skipped = True
                                                    conditons_reason = f"Shorted Cancelled RSI 13 above 55 OHLC is high above previous Red Candle,  Candle used Start # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}"
                                                    self.log_condition("RSI 13 above 55 OHLC Cancel Short Nullified", conditons_reason, self.current_candle.index )

                                    if end_candle and high_ohlc_cancel:
                                        end_candle.divergence_used = False
                                        self.update_divergence_used_in_memory_to_false(end_candle)

                                    if high_ohlc_cancel:
                                        cancel_short = True
                                        converting_to_short = False
                                        self.short_divergence_candle = None
                                        self.add_helper_messages(f"Shorted Cancelled RSI 13 above 55 OHLC is high above previous Red Candle,  Candle used Start # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")

                    short_due_to_divergence = False
                    # This Condition is helping on chart 5/8  TODO
                    # Helping 0
                    # Not Helping 5/8
                    # Remove is giving  positive  impact 375
                    if not converting_to_short and self.current_candle.body < 0 and high_ohlc_cancel:
                        if "11:21 AM" in self.current_candle.date:
                            print("Put Break Point")
                        previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, True)
                        if previous_highest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15): #and previous_highest_rsi_candle.close > self.current_candle.close:
                                previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(previous_highest_rsi_candle, self.track_all_candles, False)
                                if previous_lowest_rsi_candle:
                                    previous_previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(previous_lowest_rsi_candle, self.track_all_candles, True)
                                    if previous_previous_highest_rsi_candle:
                                        time_difference = abs(previous_lowest_rsi_candle.index - previous_previous_highest_rsi_candle.index)
                                        if time_difference < timedelta(minutes=15): #and previous_highest_rsi_candle.close > self.current_candle.close:
                                            previous_previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(previous_previous_highest_rsi_candle, self.track_all_candles, False)
                                            if previous_previous_lowest_rsi_candle and previous_lowest_rsi_candle.low <= previous_previous_lowest_rsi_candle.high <= previous_lowest_rsi_candle.high:
                                                if self.current_candle.rsi_13 > 55 and previous_highest_rsi_candle.rsi > previous_previous_lowest_rsi_candle.rsi and previous_highest_rsi_candle.stoch_k < previous_previous_lowest_rsi_candle.stoch_k and self.current_candle.close < previous_highest_rsi_candle.low:
                                                    converting_to_short = True
                                                    short_due_to_divergence = True
                                                    self.add_helper_messages(f"Shorting Due to Divergence,  Candle used Start # {previous_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {previous_highest_rsi_candle.index.strftime('%I:%M %p')} ")

                    # This Condition is helping on chart 5/8  TODO
                    # Helping 4/7, 5/8, 4/10, 4/22, 4/16, 5/20
                    # Not Helping 3/31, 5/22, 5/12, 4/15, 4/14, 5/16, 5/1
                    # Remove is giving  negative  impact -5373
                    if not converting_to_short and self.current_candle.body < 0 and not high_ohlc_cancel:
                        if "12:46 PM" in self.current_candle.date:
                            print("Put Break Point")
                        previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, True)
                        if previous_highest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15): #and previous_highest_rsi_candle.close > self.current_candle.close:
                                previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                                if previous_lowest_rsi_candle:
                                    if self.current_candle.rsi_13 > 55 and self.current_candle.rsi > previous_lowest_rsi_candle.rsi and self.current_candle.stoch_k < previous_lowest_rsi_candle.stoch_k and self.current_candle.close < previous_highest_rsi_candle.low:
                                        converting_to_short = True
                                        short_due_to_divergence =True
                                        self.add_helper_messages(f"Shorting Due to Divergence,  Candle used Start # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")


                    # This Condition is helping on chart 5/8  TODO
                    # Helping 5/8, 4/3, 3/27, 4/2, 5/1
                    # Not Helping 5/14, 4/17, 5/22, 5/20, 4/15, 5/16, 5/7, 5/6
                    # Remove is giving  negative  impact -1050
                    if converting_to_short and not lowest_rsi_short and not all_are_high_nullified:
                        if "11:42 AM" in self.current_candle.date:
                            print("Put Break Point")
                        continue_with_short = False
                        previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                        if previous_lowest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_lowest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15) : # and previous_lowest_rsi_candle.close < self.current_candle.close:
                                find_previous_highest_rsi_candle = self.find_green_candle_from_low(previous_lowest_rsi_candle.index, self.track_all_candles)
                                if self.current_candle.rsi_13 > 55 and  self.current_candle.rsi < find_previous_highest_rsi_candle.rsi and (self.current_candle.stoch_k > find_previous_highest_rsi_candle.stoch_k):
                                    continue_with_short = True
                                    # Added this condition to fix 2025-04-29 chart to skip short at 11:02 AM
                                    if start_candle and end_candle:
                                        if start_candle.rsi > 94 or end_candle.rsi > 94:
                                            if end_candle.rsi_13 > start_candle.rsi_13 and start_candle.rsi > end_candle.rsi:
                                                # Get Highest RSI Candle in between start and end candle
                                                if "11:43 AM" in self.current_candle.date:
                                                    print("Put Break Point")

                                                high_price_compare = start_candle.high
                                                closest_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(end_candle, self.track_all_candles, False)
                                                if closest_highest_rsi_candle:
                                                    if start_candle.close < closest_highest_rsi_candle.close < end_candle.close and closest_highest_rsi_candle.rsi > end_candle.rsi:
                                                        high_price_compare = closest_highest_rsi_candle.high

                                                if (self.current_candle.previous_body > 0 and self.current_candle.close < high_price_compare) or (self.current_candle.previous_body < 0 and self.current_candle.body < 0 and self.current_candle.open < self.current_candle.previous_close):
                                                    ## TODO IMPORTANT:
                                                    ## In LIVE BOT . GET THE OPEN PRICE OF THE CANDLE , GET THE OPEN PRICE OF THE CANDLE, OPEN PRICE SHOULD BELOW PREVIOUS CANDLE CLOSE
                                                    continue_with_short = False
                                                    conditons_reason = f"Short <b>Cancelled</b> Due to Divergence One,  Candle used Start # {find_previous_highest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} "
                                                    self.log_condition("Short Cancel Nullified Due to Divergence One", conditons_reason, self.current_candle.index )


                                    if continue_with_short:
                                        converting_to_short = False
                                        self.short_divergence_candle = None
                                        cancel_short = True
                                        if end_candle:
                                            end_candle.divergence_used = False
                                            self.update_divergence_used_in_memory_to_false(end_candle)
                                        self.add_helper_messages(f"One Short <b>Cancelled</b> Due to Divergence One,  Candle used Start # {find_previous_highest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")


                    # This Condition is helping on chart 5/8  TODO
                    # Helping 5/8, 5/1, 5/6, 5/16
                    # Not Helping 4/4, 3/27, 4/28, 4/29
                    # Remove is giving  negative  impact -2750

                    if converting_to_short and not lowest_rsi_short:
                        if "11:24 AM" in self.current_candle.date:
                            print("Put Break Point")
                        previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle, self.track_all_candles, True)
                        if previous_lowest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_lowest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15) : # and previous_lowest_rsi_candle.close < self.current_candle.close:
                                find_previous_highest_rsi_candle = self.find_green_candle_from_low(previous_lowest_rsi_candle.index, self.track_all_candles)
                                previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                                if  previous_highest_rsi_candle.rsi < find_previous_highest_rsi_candle.rsi and (previous_highest_rsi_candle.stoch_k > find_previous_highest_rsi_candle.stoch_k) and previous_highest_rsi_candle.low <= find_previous_highest_rsi_candle.high  <= previous_highest_rsi_candle.high:
                                    converting_to_short = False
                                    self.short_divergence_candle = None
                                    cancel_short = True
                                    if end_candle:
                                        end_candle.divergence_used = False
                                        self.update_divergence_used_in_memory_to_false(end_candle)
                                    self.add_helper_messages(f"Short <b>Cancelled</b> Due to Divergence Two,  Candle used Start # {find_previous_highest_rsi_candle.index.strftime('%I:%M %p')}, End # {previous_highest_rsi_candle.index.strftime('%I:%M %p')} ")


                    # This Condition is helping on chart 4/11 at 10:09 AM
                    # This Condition is helping on chart 4/09 at 09:44 AM
                    # Helping 4/11 , 4/9, 5/15, 3/31, 4/10, 4/30, 5/5, 5/12, 5/22, 4/3
                    # Not Helping 4/4, 4/1, 4/22, 5/2, 4/2, 4/25
                    # Remove is giving negative impact
                    short_extreme = False
                    if not converting_to_short and self.current_candle.body < 0:
                        if "12:16 PM" in self.current_candle.date:
                            print("Put Break Point")

                        short_divergence_info = self.get_divergence_info(self.current_candle.index, "SHORT")
                        if  short_divergence_info:
                            if short_divergence_info.start_candle.rsi > 94 or short_divergence_info.end_candle.rsi > 94:
                                total_red_candles = self.get_total_red_candles(self.in_trade_candle.index, self.current_candle.index, self.track_all_candles)
                                total_green_candles = self.get_total_green_candles(self.in_trade_candle.index, self.current_candle.index, self.track_all_candles)
                                if total_red_candles == 0 and total_green_candles >= 2 and self.current_candle.stoch_k < 80:
                                    converting_to_short = True
                                    short_extreme = True
                                    self.short_divergence_candle = short_divergence_info.end_candle
                                    self.add_helper_messages(f"Shorting Due to Extreme Divergence, No red candles ")


                    # This Condition is helping on chart 4/11 at 11:24 AM, 1:34 PM
                    # This Condition is helping on chart 4/1 at 09:43 AM
                    # Helping 4/11 , 4/1, 4/4, 5/7, 4/10, 4/14, 4/25, 5/02, 4/23, 4/30, 4/07, 5/09. 4/8, 3/31, 5/12, 5/20
                    # Not Helping 5/6, 5/21, 4/10, 5/22, 4/3, 4/21, 4/28, 4/2, 4/22
                    # Remove is giving big negative impact
                    if converting_to_short  and not lowest_rsi_short and self.current_candle.body < 0 and not short_extreme:
                        if "12:41 PM" in self.current_candle.date:
                            print("Put Break Point")
                        previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, True)
                        if previous_highest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15) : #and previous_highest_rsi_candle.close > self.current_candle.close:
                                find_previous_lowest_rsi_candle = self.find_red_candle_from_high(previous_highest_rsi_candle.index, self.track_all_candles)
                                if find_previous_lowest_rsi_candle and self.current_candle.rsi > 5 and self.current_candle.stoch_k > 20 and self.current_candle.rsi_13 < 45 and self.current_candle.close > find_previous_lowest_rsi_candle.low:
                                    converting_to_short = False
                                    self.short_divergence_candle = None
                                    cancel_short = True
                                    if end_candle:
                                        end_candle.divergence_used = False
                                        self.update_divergence_used_in_memory_to_false(end_candle)

                                    self.add_helper_messages(f"Short <b>Cancelled</b> Current candle RSI and K is not extreme and also not closed below previous low,  Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")

                    # This Condition is helping on chart 4/11 at 09:58 AM , Need to revisit Buying Due to Divergence Three
                    # Helping 4/11
                    # Not Helping 4/3, 3/27, 5/9
                    # Remove is giving No impact
                    if converting_to_short and not short_due_to_divergence and not lowest_rsi_short and self.current_candle.body < 0 and not short_extreme:
                        if "10:51 AM" in self.current_candle.date:
                            print("Put Break Point")
                        previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, True)
                        if previous_highest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15) : #and previous_highest_rsi_candle.close > self.current_candle.close:
                                find_previous_lowest_rsi_candle = self.find_red_candle_from_high(previous_highest_rsi_candle.index, self.track_all_candles)
                                if  (find_previous_lowest_rsi_candle and self.current_candle.rsi_13 > 55
                                        and self.current_candle.close > find_previous_lowest_rsi_candle.low \
                                        and self.current_candle.rsi > find_previous_lowest_rsi_candle.rsi
                                        and ( self.current_candle.stoch_k <  find_previous_lowest_rsi_candle.stoch_k  or self.current_candle.stoch_d <  find_previous_lowest_rsi_candle.stoch_d)):
                                    converting_to_short = False
                                    self.short_divergence_candle = None
                                    cancel_short = True
                                    if end_candle:
                                        end_candle.divergence_used = False
                                        self.update_divergence_used_in_memory_to_false(end_candle)
                                    self.add_helper_messages(f"One Short <b>Cancelled</b> Current candle RSI above 55 and Current candle didn't close previous lowest rsi candle,  Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")


                    # This Condition is helping on chart 4/29 at 10:51 AM
                    # Helping 4/29
                    # Not Helping 5/14
                    # Remove is giving No impact

                    if converting_to_short and not short_due_to_divergence and not lowest_rsi_short and self.current_candle.body < 0 and not short_extreme:
                        if "09:59 AM" in self.current_candle.date:
                            print("Put Break Point")
                        previous_highest_rsi_candle = self.find_previous_highest_high_green_candle(self.current_candle, self.track_all_candles)
                        if previous_highest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15) : #and previous_highest_rsi_candle.close > self.current_candle.close:
                                find_previous_lowest_rsi_candle = self.find_red_candle_from_high(previous_highest_rsi_candle.index, self.track_all_candles)
                                if  (find_previous_lowest_rsi_candle and self.current_candle.rsi_13 > 55 and self.current_candle.close > find_previous_lowest_rsi_candle.low \
                                        and self.current_candle.rsi > find_previous_lowest_rsi_candle.rsi
                                        and self.current_candle.high > find_previous_lowest_rsi_candle.high
                                        and ( self.current_candle.stoch_k <  find_previous_lowest_rsi_candle.stoch_k   or self.current_candle.stoch_d <  find_previous_lowest_rsi_candle.stoch_d)):
                                    converting_to_short = False
                                    self.short_divergence_candle = None
                                    cancel_short = True
                                    # if end_candle:
                                    #     end_candle.divergence_used = False
                                    #     self.update_divergence_used_in_memory_to_false(end_candle)
                                    self.add_helper_messages(f"Two Short <b>Cancelled</b> Current candle RSI above 55 and Current candle didn't close previous lowest rsi candle,  Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")
                                    conditons_reason = f"Short <b>Cancelled</b> Current candle RSI above 55 and Current candle didn't close previous lowest rsi candle,  Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} "
                                    self.log_condition("Cancel Short Above RSI 13 Above 55", conditons_reason, self.current_candle.index )


                    # This Condition is helping on chart 4/25 at 12:48 PM
                    # Helping 4/25
                    # Not Helping 4/14
                    # Remove is giving Positive impact

                    if converting_to_short and not lowest_rsi_short and self.current_candle.body < 0 and not short_extreme:
                        if "12:48 PM" in self.current_candle.date:
                            print("Put Break Point")
                        previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, True)
                        if previous_highest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15) : #and previous_highest_rsi_candle.close > self.current_candle.close:
                                find_previous_lowest_rsi_candle = self.find_red_candle_with_lowest_rsi_only(previous_highest_rsi_candle, self.current_candle , self.track_all_candles)
                                if find_previous_lowest_rsi_candle and self.current_candle.rsi < 5 and (self.current_candle.rsi > find_previous_lowest_rsi_candle.rsi
                                                                                                        and ( self.current_candle.stoch_k <  find_previous_lowest_rsi_candle.stoch_k
                                                                                                              or self.current_candle.stoch_d <  find_previous_lowest_rsi_candle.stoch_d)
                                                                                                        and self.current_candle.rsi_13 < 45
                                                                                                        and self.current_candle.close > find_previous_lowest_rsi_candle.low):

                                    converting_to_short = False
                                    self.short_divergence_candle = None
                                    cancel_short = True
                                    if end_candle:
                                        end_candle.divergence_used = False
                                        self.update_divergence_used_in_memory_to_false(end_candle)

                                    self.add_helper_messages(f"One Short <b>Cancelled</b> Current candle RSI & K is lower but D is higher and also not closed below previous low red,  Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")


                    # This Condition is helping on chart 4/11 at 02:39 PM
                    # Helping 4/11, 5/9, 4/22, 4//29, 5/16
                    # Not Helping 4/8, 3/31, 5/6, 5/12, 5/22, 5/8
                    # Remove is giving No impact

                    if converting_to_short and not lowest_rsi_short and self.current_candle.body < 0 and not short_extreme:
                        if "09:47 AM" in self.current_candle.date:
                            print("Put Break Point")
                        previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, True)
                        if previous_highest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15) : #and previous_highest_rsi_candle.close > self.current_candle.close:
                                find_previous_lowest_rsi_candle = self.find_previous_lowest_rsi_13_candle_latest(self.current_candle , self.track_all_candles, True)
                                if find_previous_lowest_rsi_candle and self.current_candle.rsi < find_previous_lowest_rsi_candle.rsi \
                                        and self.current_candle.stoch_k < find_previous_lowest_rsi_candle.stoch_k \
                                        and self.current_candle.rsi_13 > find_previous_lowest_rsi_candle.rsi_13 \
                                        and find_previous_lowest_rsi_candle.rsi_13 < 45 \
                                        and self.current_candle.low <= find_previous_lowest_rsi_candle.high <= self.current_candle.high:
                                    converting_to_short = False
                                    self.short_divergence_candle = None
                                    cancel_short = True
                                    if end_candle:
                                        end_candle.divergence_used = False
                                        self.update_divergence_used_in_memory_to_false(end_candle)

                                    self.add_helper_messages(f"Two Short <b>Cancelled</b> Current candle RSI & K is lower but D is higher and also not closed below previous low red,  Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")


                    # This Condition is helping on chart 4/8  TODO
                    # Helping 4/8, 5/12, 4/4, 5/2, 4/16, 5/22, 3/28, 4/28
                    # Not Helping 05/06, 4/29, 5/7, 4/2, 4/17, 4/10, 4/23, 5/14
                    # Remove is giving Negative impact

                    if converting_to_short and not lowest_rsi_short and self.current_candle.body < 0 and not short_extreme:
                        if "09:47 AM" in self.current_candle.date:
                            print("Put Break Point")
                        previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, True)
                        if previous_highest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15) : #and previous_highest_rsi_candle.close > self.current_candle.close:
                                find_previous_lowest_rsi_candle = self.find_previous_lowest_rsi_13_candle_latest(self.current_candle , self.track_all_candles, False)
                                if find_previous_lowest_rsi_candle and self.current_candle.rsi < find_previous_lowest_rsi_candle.rsi \
                                        and self.current_candle.stoch_k > find_previous_lowest_rsi_candle.stoch_k \
                                        and self.current_candle.stoch_d > find_previous_lowest_rsi_candle.stoch_d \
                                        and self.current_candle.rsi_13 > find_previous_lowest_rsi_candle.rsi_13 \
                                        and find_previous_lowest_rsi_candle.rsi_13 < 45 \
                                        and self.current_candle.low <= find_previous_lowest_rsi_candle.high <= self.current_candle.high:
                                    converting_to_short = False
                                    self.short_divergence_candle = None
                                    cancel_short = True
                                    if end_candle:
                                        end_candle.divergence_used = False
                                        self.update_divergence_used_in_memory_to_false(end_candle)

                                    self.add_helper_messages(f"Three Short <b>Cancelled</b> Current candle RSI & K is lower but D is higher and also not closed below previous low red,  Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")



                    rsi_13_used_for_cancel = False
                    # This Condition is helping on chart 4/7  TODO
                    # Helping 4/7, 5/8, 4/1, 4/25, 4/28, 5/20, 4/11, 5/15,
                    # Not Helping 04/9,3/31, 4/22, 4/3, 5/6, 5/25/, 5/12, 5/14
                    # Remove is giving Big Negative impact

                    if converting_to_short and self.current_candle.body < 0:
                        if "10:06 AM" in self.current_candle.date:
                            print("Put Break Point")
                        previous_lowest_rsi_candle = self.find_previous_lowest_rsi_13_candle_latest(self.current_candle, self.track_all_candles, True)
                        if previous_lowest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_lowest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15) : #and previous_highest_rsi_candle.close > self.current_candle.close:
                                if (self.current_candle.rsi < previous_lowest_rsi_candle.rsi
                                        and self.current_candle.stoch_k < previous_lowest_rsi_candle.stoch_k
                                        and self.current_candle.stoch_d < previous_lowest_rsi_candle.stoch_d
                                        and self.current_candle.rsi_13 > 55
                                        and self.current_candle.rsi_13 > previous_lowest_rsi_candle.rsi_13
                                        and self.current_candle.close > previous_lowest_rsi_candle.open):

                                    continue_to_cancel = True
                                    if self.current_candle.body < 0:
                                        previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, True)
                                        if previous_highest_rsi_candle:
                                            time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                                            if time_difference < timedelta(minutes=15) : #and previous_highest_rsi_candle.close > self.current_candle.close:
                                                find_previous_lowest_rsi_candle = self.find_red_candle_from_high(previous_highest_rsi_candle.index , self.track_all_candles)
                                                if (find_previous_lowest_rsi_candle and self.current_candle.close < find_previous_lowest_rsi_candle.low
                                                        and self.current_candle.rsi < find_previous_lowest_rsi_candle.rsi
                                                        and self.current_candle.rsi_13 < find_previous_lowest_rsi_candle.rsi_13
                                                        and self.current_candle.stoch_k < find_previous_lowest_rsi_candle.stoch_k
                                                        and self.current_candle.stoch_d < find_previous_lowest_rsi_candle.stoch_d):
                                                    continue_to_cancel = False

                                    if continue_to_cancel:
                                        converting_to_short = False
                                        self.short_divergence_candle = None
                                        rsi_13_used_for_cancel = True
                                        self.current_candle.rsi_13_used_for_cancel = True
                                        cancel_short = True
                                        self.in_trade_candle.short_cancel_due_to_rsi_13_and_Above_55 = self.current_candle
                                        if end_candle:
                                            end_candle.divergence_used = False
                                            self.update_divergence_used_in_memory_to_false(end_candle)

                                        self.add_helper_messages(f"Short <b>Cancelled</b> RSI 13 Divergence and Above 55 ,  Candle used Start # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")
                                        conditons_reason = f"Short <b>Cancelled</b> RSI 13 Divergence and Above 55 ,  Candle used Start # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} "
                                        self.log_condition("Short Cancelled RSI 13 Divergence and Above 55", conditons_reason, self.current_candle.index )



                    # This Condition is helping on chart 4/7  TODO
                    # Helping 4/7, 5/8, 4/1, 4/25, 4/28, 5/20
                    # Not Helping 05/15
                    # Remove is giving Big Negative impact

                    if converting_to_short and self.current_candle.body < 0:
                        if "10:19 AM" in self.current_candle.date:
                            print("Put Break Point")

                        any_rsi_13_used_for_cancel = self.find_rsi_13_used_for_cancel(self.in_trade_candle, self.current_candle, self.track_all_candles)
                        if any_rsi_13_used_for_cancel:
                            if self.current_candle.close > any_rsi_13_used_for_cancel.low and self.current_candle.rsi_13 > 55:
                                continue_to_cancel = True
                                if self.current_candle.body < 0 and high_ohlc_cancel_skipped:
                                    previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, True)
                                    if previous_highest_rsi_candle:
                                        time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                                        if time_difference < timedelta(minutes=15) : #and previous_highest_rsi_candle.close > self.current_candle.close:
                                            find_previous_lowest_rsi_candle = self.find_red_candle_from_high(previous_highest_rsi_candle.index , self.track_all_candles)
                                            if (find_previous_lowest_rsi_candle and self.current_candle.close < previous_highest_rsi_candle.low
                                                    and self.current_candle.rsi < find_previous_lowest_rsi_candle.rsi
                                                    and self.current_candle.rsi_13 < find_previous_lowest_rsi_candle.rsi_13
                                                    and self.current_candle.stoch_k < find_previous_lowest_rsi_candle.stoch_k
                                                    and self.current_candle.stoch_d < find_previous_lowest_rsi_candle.stoch_d
                                                    and self.current_candle.low <= find_previous_lowest_rsi_candle.open <= self.current_candle.high):
                                                continue_to_cancel = False

                                if continue_to_cancel:
                                    if self.current_candle.rsi < any_rsi_13_used_for_cancel.rsi:
                                        if self.current_candle.close < any_rsi_13_used_for_cancel.close or self.current_candle.low < any_rsi_13_used_for_cancel.low:
                                            continue_to_cancel = False
                                            if start_candle and end_candle:
                                                if end_candle.rsi_13 > start_candle.rsi_13:
                                                    continue_to_cancel = True

                                if start_candle and end_candle:
                                    if continue_to_cancel and start_candle.rsi > 94 or end_candle.rsi > 94:
                                        if end_candle.rsi_13 > start_candle.rsi_13 and start_candle.rsi > end_candle.rsi:
                                            continue_to_cancel = False
                                            conditons_reason = f"Short <b>Cancelled</b> Didn't close below previous RSI_13 Divergence and Above 55 ,  Candle used Start # {any_rsi_13_used_for_cancel.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} "
                                            self.log_condition("Skipping Short Cancelled Condition Didn't close below previous RSI_13 Divergence and Above 55", conditons_reason, self.current_candle.index )


                                if continue_to_cancel:
                                    converting_to_short = False
                                    self.short_divergence_candle = None
                                    self.current_candle.rsi_13_used_for_cancel = True
                                    cancel_short = True
                                    self.add_helper_messages(f"Short <b>Cancelled</b> Didn't close below previous RSI_13 Divergence and Above 55 ,  Candle used Start # {any_rsi_13_used_for_cancel.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")
                                    if end_candle:
                                        end_candle.divergence_used = False
                                        self.update_divergence_used_in_memory_to_false(end_candle)



                    # This Condition is helping on chart 5/8  TODO
                    # Helping  5/8, 4/1, 4/25
                    # Not Helping
                    # Remove is giving Big Negative impact
                    if not converting_to_short and not cancel_short and self.current_candle.body < 0 and self.current_candle.stoch_k < 80:
                        if "02:50 PM" in self.current_candle.date:
                            print("Put Break Point")

                        previous_highest_rsi_candle = self.find_previous_highest_high_green_candle(self.current_candle, self.track_all_candles)
                        if previous_highest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15) :
                                find_previous_highest_rsi_13_candle = self.find_previous_highest_rsi_13_candle_latest(previous_highest_rsi_candle, self.track_all_candles)
                                if find_previous_highest_rsi_13_candle and self.current_candle.rsi_13 > 55:
                                    if (previous_highest_rsi_candle.rsi >=  find_previous_highest_rsi_13_candle.rsi and previous_highest_rsi_candle.stoch_k >=  find_previous_highest_rsi_13_candle.stoch_k and previous_highest_rsi_candle.stoch_d >=  find_previous_highest_rsi_13_candle.stoch_d
                                            and previous_highest_rsi_candle.rsi_13 < find_previous_highest_rsi_13_candle.rsi_13
                                            and previous_highest_rsi_candle.close < find_previous_highest_rsi_13_candle.close
                                            and  self.current_candle.close <= previous_highest_rsi_candle.low):

                                        buy_divergence_info = self.get_divergence_info(self.current_candle.index , "BUY")
                                        if not buy_divergence_info:
                                            converting_to_short = True
                                            self.add_helper_messages(f"Shorting Due Divergence between RSI & RSI_13 , Candle used Start # {find_previous_highest_rsi_13_candle.index.strftime('%I:%M %p')}, End # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}  ")


                    # This Condition is helping on chart 4/15  TODO
                    # Helping  4/15, 4/16, 4/2, 4/8, 5/8, 4/21, 5/22, 4/1, 4/30, 4/25, 3/27, 4/9, 3/28, 5/13, 5/20
                    # Not Helping 4/4, 4/24, 4/7, 4/14, 5/14, 5/5, 5/21, 4/23, 5/2, 5/16, 3/31, 5/15
                    # Remove is giving Big Negative impact

                    if not converting_to_short and self.current_candle.body < 0 and self.current_candle.stoch_k < 80 and not shorted_cancelled_all_are_high:
                        if "11:47 AM" in self.current_candle.date:
                            print("Put Break Point")

                        previous_highest_rsi_candle = self.find_previous_highest_high_green_candle(self.current_candle, self.track_all_candles)
                        if previous_highest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15) :
                                find_previous_highest_rsi_2_candle = self.find_previous_highest_rsi_2_candle_latest(previous_highest_rsi_candle, self.track_all_candles)
                                if find_previous_highest_rsi_2_candle and self.current_candle.rsi_13 < 55:
                                    high_price = None
                                    highest_high_green_candle_between_start_end = self.find_highest_high_green_candle_between_start_end(find_previous_highest_rsi_2_candle.index, previous_highest_rsi_candle.index, self.track_all_candles)
                                    high_price = find_previous_highest_rsi_2_candle.high
                                    if highest_high_green_candle_between_start_end:
                                        if highest_high_green_candle_between_start_end.high > find_previous_highest_rsi_2_candle.high:
                                            high_price = highest_high_green_candle_between_start_end.high
                                    if (previous_highest_rsi_candle.rsi <=  find_previous_highest_rsi_2_candle.rsi and previous_highest_rsi_candle.stoch_k <=  find_previous_highest_rsi_2_candle.stoch_k and previous_highest_rsi_candle.stoch_d <=  find_previous_highest_rsi_2_candle.stoch_d
                                            and previous_highest_rsi_candle.rsi_13 <= find_previous_highest_rsi_2_candle.rsi_13
                                            and previous_highest_rsi_candle.close < high_price
                                            and previous_highest_rsi_candle.high < high_price
                                            #and  self.current_candle.close <= previous_highest_rsi_candle.low
                                            and (previous_highest_rsi_candle.rsi > 94 or find_previous_highest_rsi_2_candle.rsi > 94)):

                                        find_previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(previous_highest_rsi_candle,  self.track_all_candles , False)
                                        if find_previous_lowest_rsi_candle and self.current_candle.rsi < find_previous_lowest_rsi_candle.rsi:
                                            continue_to_short = True
                                            if self.current_candle.low <= find_previous_lowest_rsi_candle.open <= self.current_candle.high:
                                                if self.current_candle.stoch_k > find_previous_lowest_rsi_candle.stoch_k or  self.current_candle.stoch_d > find_previous_lowest_rsi_candle.stoch_d:
                                                    continue_to_short = False
                                            if continue_to_short:
                                                converting_to_short = True
                                                self.add_helper_messages(f"Shorting the price is going down ,"
                                                                         f" Candle used Start # {find_previous_highest_rsi_2_candle.index.strftime('%I:%M %p')}, End # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}"
                                                                         f" And also Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")


                    # This Condition is helping on chart 5/8  TODO
                    # Helping  5/8, 4/15, 3/31
                    # Not Helping 4/17, 5/13, 5/15, 5/12, 5/1, 5/21
                    # Remove is giving Positive  impact
                    if not converting_to_short and self.current_candle.body < 0 and self.current_candle.stoch_k < 80 and not shorted_cancelled_all_are_high:
                        if "11:47 AM" in self.current_candle.date:
                            print("Put Break Point")

                        previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                        if previous_highest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15) :
                                find_previous_highest_rsi_2_candle = self.find_previous_highest_rsi_13_candle_latest(previous_highest_rsi_candle, self.track_all_candles)
                                if find_previous_highest_rsi_2_candle and self.current_candle.rsi_13 < 55:
                                    high_price = None
                                    highest_high_green_candle_between_start_end = self.find_highest_high_green_candle_between_start_end(find_previous_highest_rsi_2_candle.index, previous_highest_rsi_candle.index, self.track_all_candles)
                                    high_price = find_previous_highest_rsi_2_candle.high
                                    if highest_high_green_candle_between_start_end:
                                        if highest_high_green_candle_between_start_end.high > find_previous_highest_rsi_2_candle.high:
                                            high_price = highest_high_green_candle_between_start_end.high
                                    if (previous_highest_rsi_candle.rsi >=  find_previous_highest_rsi_2_candle.rsi and previous_highest_rsi_candle.stoch_k >=  find_previous_highest_rsi_2_candle.stoch_k and previous_highest_rsi_candle.stoch_d >=  find_previous_highest_rsi_2_candle.stoch_d
                                            and previous_highest_rsi_candle.rsi_13 <= find_previous_highest_rsi_2_candle.rsi_13
                                            and previous_highest_rsi_candle.close < high_price
                                            and previous_highest_rsi_candle.high < high_price
                                            and find_previous_highest_rsi_2_candle.low < previous_highest_rsi_candle.high
                                            #and  self.current_candle.close <= previous_highest_rsi_candle.low
                                            and (previous_highest_rsi_candle.rsi > 94 or find_previous_highest_rsi_2_candle.rsi > 94)):

                                        condition_one = previous_highest_rsi_candle.rsi > 94
                                        condition_two = previous_highest_rsi_candle.rsi_13 > 55
                                        condition_three = previous_highest_rsi_candle.stoch_k > 80
                                        match_count = sum([condition_one, condition_two, condition_three])
                                        if self.current_candle.close <= previous_highest_rsi_candle.open and match_count >= 2:
                                            continue_to_short = True
                                            if continue_to_short:
                                                converting_to_short = True
                                                self.add_helper_messages(f"Script Five, Shorting the price is going down Using RSI & RSI_13 Two ,"
                                                                         f" Candle used Start # {find_previous_highest_rsi_2_candle.index.strftime('%I:%M %p')}, End # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}")


                    # This Condition is helping on chart 5/8  TODO
                    # Helping  4/10, 5/8
                    # Not Helping 5/1
                    # Remove is giving Negative  impact
                    if not converting_to_short and self.current_candle.body < 0 and self.current_candle.stoch_k < 80 and self.current_candle.rsi_13 < 55 and not shorted_cancelled_all_are_high:
                        if "03:09 PM" in self.current_candle.date:
                            print("Put Break Point")

                        previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, True)
                        if previous_highest_rsi_candle and previous_highest_rsi_candle.rsi > 94 and previous_highest_rsi_candle.rsi_13 > 55 and previous_highest_rsi_candle.stoch_k > 80:
                            time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                            if time_difference < timedelta(minutes=5) :
                                previous_previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(previous_highest_rsi_candle, self.track_all_candles, True)
                                if previous_previous_highest_rsi_candle and previous_highest_rsi_candle.low < previous_previous_highest_rsi_candle.low < previous_highest_rsi_candle.high:
                                    time_difference = abs(self.current_candle.index - previous_previous_highest_rsi_candle.index)
                                    time_difference_between_highs = abs(previous_highest_rsi_candle.index - previous_previous_highest_rsi_candle.index)
                                    if time_difference < timedelta(minutes=25) and time_difference_between_highs >  timedelta(minutes=10):
                                        if previous_previous_highest_rsi_candle.high > previous_highest_rsi_candle.high and previous_previous_highest_rsi_candle.close > previous_highest_rsi_candle.close:
                                            if (previous_highest_rsi_candle.rsi <  previous_previous_highest_rsi_candle.rsi and self.current_candle.close < previous_highest_rsi_candle.close and  self.current_candle.high < previous_highest_rsi_candle.high
                                                    and previous_highest_rsi_candle.rsi_13 < previous_previous_highest_rsi_candle.rsi_13
                                                    and (previous_highest_rsi_candle.rsi > 94 or previous_previous_highest_rsi_candle.rsi > 94)):
                                                converting_to_short = True
                                                self.add_helper_messages(f"Script Five,Shorting the price is going down,Candle used Start # {previous_previous_highest_rsi_candle.index.strftime('%I:%M %p')}, End # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}")
                                                conditons_reason = f"Script Five,Shorting the price is going down,Candle used Start # {previous_previous_highest_rsi_candle.index.strftime('%I:%M %p')}, End # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}"
                                                self.log_condition("Script Five, Shorting the price is going down", conditons_reason, self.current_candle.index )



                    # This Condition is helping on chart 5/8  TODO
                    # Helping  4/7, 4/9, 4/16, 5/8, 4/25
                    # Not Helping 4/10, 4/4, 4/1, 5/2, 4/29, 5/20
                    # Remove is giving Big Negative  impact
                    if converting_to_short and not lowest_rsi_short and self.current_candle.body < 0 and not short_extreme and not short_due_to_divergence:
                        if "01:32 PM" in self.current_candle.date:
                            print("Put Break Point")
                        previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, True)
                        if previous_highest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15) : #and previous_highest_rsi_candle.close > self.current_candle.close:
                                find_previous_lowest_rsi_13_candle = self.find_previous_lowest_rsi_13_candle_latest(self.current_candle , self.track_all_candles, True)
                                find_previous_lowest_rsi_candle = self.find_red_candle_from_high(previous_highest_rsi_candle.index , self.track_all_candles)
                                if find_previous_lowest_rsi_13_candle and find_previous_lowest_rsi_candle:
                                    if self.current_candle.rsi < find_previous_lowest_rsi_13_candle.rsi \
                                            and self.current_candle.stoch_k < find_previous_lowest_rsi_13_candle.stoch_k \
                                            and self.current_candle.rsi_13 > find_previous_lowest_rsi_13_candle.rsi_13 \
                                            and self.current_candle.low <= find_previous_lowest_rsi_candle.close >= self.current_candle.close \
                                            and self.current_candle.close > find_previous_lowest_rsi_candle.low \
                                            and start_candle and self.current_candle.close > start_candle.close:
                                        converting_to_short = False
                                        self.short_divergence_candle = None
                                        cancel_short = True
                                        if end_candle:
                                            end_candle.divergence_used = False
                                            self.update_divergence_used_in_memory_to_false(end_candle)

                                        self.add_helper_messages(f"Short <b>Cancelled</b> Current candle RSI & K is lower but RSI_13 is higher and also not closed below previous low red,  Candle used Start # {find_previous_lowest_rsi_13_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")

                    # This Condition is helping on chart 5/8  TODO
                    # Helping 5/8, 4/9, 4/7, 3/31
                    # Not Helping 5/21
                    # Remove is giving Big Negative  impact
                    shorted_due_to_all_green = False
                    if not converting_to_short and self.current_candle.body < 0 and self.current_candle.previous_body < 0:
                        if "11:33 AM" in self.current_candle.date:
                            print("Put Break Point")

                        if self.in_trade_candle and self.in_trade_candle.divergence_start_candle and self.in_trade_candle.divergence_end_candle:
                            any_red_candle_with_extremen_rsi = self.any_red_candle_with_extremen_rsi(self.in_trade_candle.divergence_start_candle.index, self.in_trade_candle.divergence_end_candle.index, self.track_all_candles)
                            if any_red_candle_with_extremen_rsi > 0:
                                previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, True)
                                if previous_highest_rsi_candle:
                                    time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                                    if time_difference < timedelta(minutes=15) :
                                        if previous_highest_rsi_candle.rsi > 94 and previous_highest_rsi_candle.rsi_13 > 55 and previous_highest_rsi_candle.stoch_k > 80:
                                            total_red_candles = self.get_total_red_candles(self.in_trade_candle.divergence_end_candle.index, previous_highest_rsi_candle.index, self.track_all_candles)
                                            if total_red_candles == 0 and self.current_candle.close < self.current_candle.previous_low:
                                                converting_to_short = True
                                                shorted_due_to_all_green = True
                                                self.short_divergence_candle = previous_highest_rsi_candle
                                                self.short_divergence_candle.shorted_due_to_all_green = True
                                                self.add_helper_messages(f"Shorting Due All Green Candles and previous divergence is low extreme  , Candle used Start # {self.in_trade_candle.divergence_end_candle.index.strftime('%I:%M %p')}, End # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}  ")


                    # This Condition is helping on chart 5/8  TODO
                    # Helping 5/8, 4/15, 5/1, 5/19, 3/31
                    # Not Helping 5/6, 4/9, 5/20, 5/2, 5/5
                    # Remove is giving Negative  impact
                    if converting_to_short and self.current_candle.body < 0 and not shorted_due_to_all_green:
                        if "11:57 AM" in self.current_candle.date:
                            print("Put Break Point")
                        previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, True)
                        if previous_highest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15) : #and previous_highest_rsi_candle.close > self.current_candle.close:
                                find_previous_lowest_rsi_candle = self.find_red_candle_from_high(previous_highest_rsi_candle.index, self.track_all_candles)
                                if find_previous_lowest_rsi_candle:
                                    previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(find_previous_lowest_rsi_candle, self.track_all_candles, True)
                                    if previous_highest_rsi_candle and previous_highest_rsi_candle.close > find_previous_lowest_rsi_candle.high:
                                        if (previous_highest_rsi_candle.rsi > self.current_candle.rsi
                                                and  self.current_candle.stoch_k > previous_highest_rsi_candle.stoch_k
                                                and  self.current_candle.stoch_d > previous_highest_rsi_candle.stoch_d
                                                and previous_highest_rsi_candle.close <  self.current_candle.close):
                                            converting_to_short = False
                                            self.short_divergence_candle = None
                                            cancel_short = True
                                            if end_candle:
                                                end_candle.divergence_used = False
                                                self.update_divergence_used_in_memory_to_false(end_candle)

                                            self.add_helper_messages(f"Short <b>Cancelled</b> Overlap between RSI , K & D,  Candle used Start # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")


                    # This Condition is helping on chart 5/8  TODO
                    # Helping 5/8, 4/7, 4/28, 4/24, 4/3, 4/8, 4/14, 5/1, 4/21
                    # Not Helping 4/10, 5/22, 5/21, 4/17, 5/7, 5/19, 4/30
                    # Remove is giving Negative  impact
                    if not converting_to_short and self.current_candle.body < 0:
                        if "10:27 AM" in self.current_candle.date:
                            print("Put Break Point")
                        previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, True)
                        if previous_highest_rsi_candle and previous_highest_rsi_candle.rsi_13 > 55:
                            time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15) :
                                find_previous_lowest_rsi_candle = self.find_red_candle_from_high(previous_highest_rsi_candle.index, self.track_all_candles)
                                if find_previous_lowest_rsi_candle:
                                    previous_previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(find_previous_lowest_rsi_candle, self.track_all_candles, True)
                                    if previous_previous_highest_rsi_candle and previous_highest_rsi_candle.close > previous_previous_highest_rsi_candle.close and previous_highest_rsi_candle.high > previous_previous_highest_rsi_candle.high and previous_previous_highest_rsi_candle.rsi > previous_highest_rsi_candle.rsi:
                                        if previous_previous_highest_rsi_candle.rsi > 94 or previous_highest_rsi_candle.rsi > 94:
                                            if previous_highest_rsi_candle.rsi_13 > previous_previous_highest_rsi_candle.rsi_13:
                                                if self.current_candle.close < self.current_candle.previous_low and self.current_candle.previous_body < 0:
                                                    converting_to_short = True
                                                    self.short_divergence_candle = previous_highest_rsi_candle
                                                    self.add_helper_messages(f"Script Five, Short Due to Divergence RSI & RSI_13,  Candle used Start # {previous_previous_highest_rsi_candle.index.strftime('%I:%M %p')}, End # {previous_highest_rsi_candle.index.strftime('%I:%M %p')} ")
                                                    conditons_reason = f"Short Due to Divergence RSI & RSI_13,  Candle used Start # {previous_previous_highest_rsi_candle.index.strftime('%I:%M %p')}, End # {previous_highest_rsi_candle.index.strftime('%I:%M %p')} "
                                                    self.log_condition("Script Five, Short Due to Divergence RSI & RSI_13", conditons_reason, self.current_candle.index )


                    # This Condition is helping on chart 5/8  TODO
                    # Helping 5/8, 4/28, 5/2
                    # Not Helping 4/14
                    # Remove is giving Negative  impact
                    if not converting_to_short and self.current_candle.body < 0:
                        if "09:43 AM" in self.current_candle.date:
                            print("Put Break Point")
                        short_divergence_info = self.get_divergence_info(self.current_candle.index , "SHORT")
                        if not short_divergence_info:
                            previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, True)
                            if previous_highest_rsi_candle:
                                time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                                if time_difference < timedelta(minutes=15) :
                                    find_previous_lowest_rsi_candle = self.find_red_candle_from_high(previous_highest_rsi_candle.index, self.track_all_candles)
                                    if find_previous_lowest_rsi_candle:
                                        previous_previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(find_previous_lowest_rsi_candle, self.track_all_candles, True)
                                        if previous_previous_highest_rsi_candle and previous_highest_rsi_candle.close > previous_previous_highest_rsi_candle.close and previous_highest_rsi_candle.high > previous_previous_highest_rsi_candle.high and previous_previous_highest_rsi_candle.rsi > previous_highest_rsi_candle.rsi:
                                            if previous_previous_highest_rsi_candle.rsi > 94 or previous_highest_rsi_candle.rsi > 94 or previous_previous_highest_rsi_candle.stoch_k > 80 or previous_highest_rsi_candle.stoch_k > 80:
                                                if self.current_candle.close < previous_highest_rsi_candle.low:
                                                    converting_to_short = True
                                                    self.short_divergence_candle = previous_highest_rsi_candle
                                                    self.add_helper_messages(f"Script Five, Short Due to Divergence,  Candle used Start # {previous_previous_highest_rsi_candle.index.strftime('%I:%M %p')}, End # {previous_highest_rsi_candle.index.strftime('%I:%M %p')} ")
                                                    conditons_reason = f"Short Due to Divergence,  Candle used Start # {previous_previous_highest_rsi_candle.index.strftime('%I:%M %p')}, End # {previous_highest_rsi_candle.index.strftime('%I:%M %p')} "
                                                    self.log_condition("Script Five, Short Due to Divergence", conditons_reason, self.current_candle.index )



                    # This Condition is helping on chart 5/8  TODO
                    # Helping 4/9, 4/16, 5/8, 3/27, 5/1, 5/9, 4/11, 4/24, 5/6, 4/2, 5/16, 5/21
                    # Not Helping 4/15, 5/13, 4/25, 4/29, 4/17, 5/15, 4/23, 5/19, 5/2, 3/31
                    # Remove is giving Negative  impact

                    if not converting_to_short:
                        if "02:04 PM" in self.current_candle.date:
                            print("Put Break Point")
                        if self.current_candle.body < 0 :
                            previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                            if previous_highest_rsi_candle:
                                previous_lowest_rsi_candle = self.find_red_candle_from_high(previous_highest_rsi_candle.index, self.track_all_candles)
                                short_divergence_info = self.get_divergence_info(self.current_candle.index, "SHORT")
                                if previous_lowest_rsi_candle and self.current_candle.rsi < previous_lowest_rsi_candle.rsi and short_divergence_info and short_divergence_info.end_candle.index == previous_highest_rsi_candle.index:
                                    continue_with_short = True
                                    if (self.current_candle.rsi_13 < 55 or self.current_candle.low < previous_lowest_rsi_candle.open  < self.current_candle.high \
                                            or (self.current_candle.low < previous_lowest_rsi_candle.close  < self.current_candle.high)
                                            or (self.current_candle.low <= previous_lowest_rsi_candle.high  < self.current_candle.high)
                                            or (previous_lowest_rsi_candle.body_percent <= 5)
                                            or self.current_candle.stoch_k > 80
                                            or (self.current_candle.stoch_k < 20 and self.current_candle.rsi > 5 and self.current_candle.rsi_13 > 55)
                                            or (short_divergence_info.end_candle.rsi < 94 or  short_divergence_info.start_candle.rsi > 94 and  short_divergence_info.end_candle.rsi_13 > short_divergence_info.start_candle.rsi_13)
                                            or ((self.current_candle.rsi_13 > 55 and previous_lowest_rsi_candle.rsi_13 > 55) and self.current_candle.rsi_13 > previous_lowest_rsi_candle.rsi_13)):
                                        continue_with_short = False
                                        if not ((self.current_candle.low < previous_lowest_rsi_candle.open  < self.current_candle.high) or (self.current_candle.low < previous_lowest_rsi_candle.close  < self.current_candle.high)  or (self.current_candle.low <= previous_lowest_rsi_candle.high  < self.current_candle.high)):
                                            if not continue_with_short :
                                                if short_divergence_info.end_candle.rsi > 94 and short_divergence_info.end_candle.stoch_k > 80 and short_divergence_info.end_candle.rsi_13 > 55:
                                                    if short_divergence_info.end_candle.rsi_13 > short_divergence_info.start_candle.rsi_13 and short_divergence_info.end_candle.stoch_d < short_divergence_info.start_candle.stoch_d:
                                                        continue_with_short = True
                                                if short_divergence_info.end_candle.rsi > 94 and short_divergence_info.end_candle.stoch_k >= 100 and short_divergence_info.end_candle.stoch_d >= 100  and short_divergence_info.end_candle.rsi_13 > 55:
                                                    continue_with_short = True
                                                if short_divergence_info.start_candle.stoch_k < 80 and short_divergence_info.start_candle.stoch_d < 80 and short_divergence_info.end_candle.stoch_k > 80  and short_divergence_info.end_candle.stoch_d > 80:
                                                    continue_with_short = True
                                                if short_divergence_info.start_candle.stoch_k >= 100 and short_divergence_info.start_candle.stoch_d >= 100 and short_divergence_info.end_candle.stoch_k < 80  and short_divergence_info.end_candle.stoch_d < 80:
                                                    continue_with_short = True
                                                if short_divergence_info.start_candle.stoch_k < 80 and short_divergence_info.start_candle.stoch_d < 80 and short_divergence_info.end_candle.stoch_k > 80  and short_divergence_info.end_candle.stoch_d > 80:
                                                    continue_with_short = True
                                                if short_divergence_info.end_candle.rsi > 94 and  short_divergence_info.start_candle.rsi > 94:
                                                    if short_divergence_info.end_candle.rsi_13 < short_divergence_info.start_candle.rsi_13 and short_divergence_info.end_candle.stoch_d < short_divergence_info.start_candle.stoch_d:
                                                        continue_with_short = True


                                            #Fix 4/17 and 4/15 . Divergence matching
                                    if continue_with_short:
                                        converting_to_short = True
                                        self.add_helper_messages(f"Three - Shorted current rsi lower then previous lowest rsi,  Candle used Start # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")
                                        conditons_reason = f"Three - Shorted current rsi lower then previous lowest rsi,  Candle used Start # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}"
                                        self.log_condition("Shorted current rsi lower then previous lowest rsi", conditons_reason, self.current_candle.index )


                    if converting_to_short and (self.current_candle.body > 0 or self.current_candle.open == self.current_candle.close):
                        converting_to_short = False
                        self.short_divergence_candle = None
                        self.add_helper_messages(f"Short <b>Cancelled</b> because current candle is green candle")
                        # if end_candle:
                        #     end_candle.divergence_used = False
                        #     self.update_divergence_used_in_memory_to_false(end_candle)


                    # This Condition is helping on chart 5/8  TODO
                    # Helping 5/8, 4/30, 4/8, 4/21, 4/24, 5/5, 5/14
                    # Not Helping 4/4, 5/21, 4/15 ,
                    # Remove is giving Negative  impact
                    if not converting_to_short and self.current_candle.body < 0 and not rsi_13_used_for_cancel:
                        if "10:00 AM" in self.current_candle.date:
                            print("Put Break Point")

                        short_divergence_info = self.get_divergence_info(self.current_candle.index, "SHORT")
                        if not short_divergence_info:
                            previous_highest_rsi_candle = self.find_previous_highest_price_candle(self.current_candle, self.track_all_candles)
                            if previous_highest_rsi_candle:
                                if previous_highest_rsi_candle.rsi > 94 and previous_highest_rsi_candle.rsi_13 > 55 and previous_highest_rsi_candle.stoch_k > 80 and previous_highest_rsi_candle.stoch_d > 80 and self.current_candle.rsi_13 < 55:
                                    lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(previous_highest_rsi_candle, self.track_all_candles, True)
                                    if lowest_rsi_candle:
                                        if self.current_candle.previous_body > 0 and not self.first_red_candle_condition_statisfied and self.current_candle.rsi < lowest_rsi_candle.rsi:
                                            self.first_red_candle_condition_statisfied = self.current_candle
                                        elif self.current_candle.stoch_k < 80 and (self.current_candle.rsi < lowest_rsi_candle.rsi
                                                                                   and ((self.current_candle.previous_body < 0 and not self.first_red_candle_condition_statisfied) or (self.first_red_candle_condition_statisfied and self.current_candle.close <= self.first_red_candle_condition_statisfied.low))):
                                            converting_to_short = True
                                            previous_index = pd.Timestamp(self.current_candle.previous_index).round('s')
                                            previous_candle = self.get_candle_by_index(previous_index)
                                            self.short_divergence_candle = previous_candle
                                            self.add_helper_messages(f"Script Five, Four - Shorted current rsi lower then previous lowest rsi,  Candle used Start # {lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")
                                            conditons_reason = f"Four - Shorted current rsi lower then previous lowest rsi,  Candle used Start # {lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}"
                                            self.log_condition("Script Five Change, Shorted current rsi lower then previous lowest rsi when All Extreme", conditons_reason, self.current_candle.index )



                    if self.buy_divergence_candle and not converting_to_short and not cancel_short and self.current_candle.body < 0:
                        if self.current_candle.close < self.buy_divergence_candle.low:
                            converting_to_short = True
                            self.add_helper_messages(f"Shorted because current candle closed below Buy Divergence candle  {self.buy_divergence_candle.index.strftime('%I:%M %p')}")
                            self.short_divergence_candle = self.get_candle_by_index(self.buy_divergence_candle.index)

                    # This Condition is helping on chart 4/23  10:42 AM
                    # Helping 5/8, 4/4, 4/23, 4/30, 5/1
                    # Not Helping 3/28, 4/9, 4/8, 5/22, 5/2, 4/14, 3/27
                    # Remove is giving small negative  impact
                    if converting_to_short:
                        lowest_rsi_candle = self.find_previous_lowest_rsi_or_rsi_13_ir_stoch_k_candle_latest(self.current_candle , self.track_all_candles)
                        if lowest_rsi_candle:
                            time_difference = abs(self.current_candle.index - lowest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15) :
                                if self.current_candle.close < lowest_rsi_candle.close and self.current_candle.low < lowest_rsi_candle.low:
                                    if self.current_candle.rsi > lowest_rsi_candle.rsi and self.current_candle.rsi_13 < lowest_rsi_candle.rsi_13 and self.current_candle.close > self.in_trade_candle.low:
                                        self.add_helper_messages(f"Script Five, Short <b>Cancelled</b> Due to Buy Divergence RSI & RSI 13 # {lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")
                                        conditons_reason = f"Short <b>Cancelled</b> Due to Buy Divergence RSI & RSI 13 # {lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} "
                                        self.log_condition("Script Five, Short Cancelled Due to Buy Divergence RSI & RSI 13", conditons_reason, self.current_candle.index )
                                        converting_to_short = False
                                        self.short_divergence_candle = None
                                        self.buy_divergence_candle = self.current_candle
                                        self.in_trade_candle.side_ways_structure_detected = True

                    # This Condition is helping on chart 5/8  TODO
                    # Helping 5/8, 4/2, 5/14, 5/7, 4/15
                    # Not Helping 5/6, 5/12, 4/28, 4/21
                    # Remove is giving Positive  impact
                    if converting_to_short:
                        lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle , self.track_all_candles, True)
                        short_divergence_info = self.get_divergence_info(self.current_candle.index, "SHORT")
                        if lowest_rsi_candle and not short_divergence_info:
                            time_difference = abs(self.current_candle.index - lowest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15) :
                                if self.current_candle.low > lowest_rsi_candle.high:
                                    highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(lowest_rsi_candle , self.track_all_candles, True)
                                    if highest_rsi_candle:
                                        condition_one = highest_rsi_candle.rsi > 94
                                        condition_two = highest_rsi_candle.rsi_13 > 55
                                        condition_three = highest_rsi_candle.stoch_k > 80
                                        match_count = sum([condition_one, condition_two, condition_three])
                                        if match_count >= 1 and self.current_candle.rsi < highest_rsi_candle.rsi and (self.current_candle.rsi_13 > highest_rsi_candle.rsi_13 or self.current_candle.stoch_k > highest_rsi_candle.stoch_k):
                                            self.add_helper_messages(f"Script Five, Short <b>Cancelled</b> Due to Overlap  RSI & RSI_13 Or K # {highest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")
                                            conditons_reason = f"Short <b>Cancelled</b> Due to Overlap  RSI & RSI_13 Or K # {highest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} "
                                            self.log_condition("Script Five - Fix, Short Cancelled Due to Overlap RSI & RSI_13 Or K ", conditons_reason, self.current_candle.index )
                                            converting_to_short = False
                                            self.short_divergence_candle = None
                                            if end_candle:
                                                end_candle.divergence_used = False
                                                self.update_divergence_used_in_memory_to_false(end_candle)

                    # This Condition is helping on chart 5/8  TODO
                    # Helping 4/9, 4/10, 5/8, 4/29, 4/28, 4/30, 5/16, 5/2, 5/19, 5/22
                    # Not Helping 5/6, 4/22, 4/21, 5/13, 4/8, 4/24, 3/27
                    # Remove is giving big negative  impact
                    if converting_to_short:
                        lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle , self.track_all_candles, False)
                        if lowest_rsi_candle:
                            time_difference = abs(self.current_candle.index - lowest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15) :
                                if self.current_candle.close < lowest_rsi_candle.close and self.current_candle.low < lowest_rsi_candle.low:
                                    if self.current_candle.rsi > lowest_rsi_candle.rsi and self.current_candle.rsi_13 < lowest_rsi_candle.rsi_13 and self.current_candle.stoch_k >= lowest_rsi_candle.stoch_k and self.current_candle.stoch_d >= lowest_rsi_candle.stoch_d:
                                        conitunue_to_cancel = True
                                        if self.in_trade_candle.short_cancelled_due_to_new_buy_divergence:
                                            if self.current_candle.close < self.current_candle.previous_low:
                                                conitunue_to_cancel = False

                                        if conitunue_to_cancel:
                                            self.add_helper_messages(f"Script Five, Short <b>Cancelled</b> Due to New Buy Divergence  # {lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")
                                            conditons_reason = f"Short <b>Cancelled</b> Due to New Buy Divergence  # {lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} "
                                            self.log_condition("Script Five - Fix, Short Cancelled Due to New Buy Divergence", conditons_reason, self.current_candle.index )
                                            converting_to_short = False
                                            self.in_trade_candle.short_cancelled_due_to_new_buy_divergence = True
                                            self.short_divergence_candle = None
                                            if end_candle:
                                                end_candle.divergence_used = False
                                                self.update_divergence_used_in_memory_to_false(end_candle)

                    # This Condition is helping on chart 5/8  TODO
                    # Helping 5/8, 4/22, 5/6, 5/22,
                    # Not Helping 3/31
                    # Remove is giving  negative  impact -2350
                    if not converting_to_short and self.in_trade_candle.short_cancel_due_to_rsi_13_and_Above_55:
                        if self.current_candle.close < self.in_trade_candle.short_cancel_due_to_rsi_13_and_Above_55.low:
                            converting_to_short = True
                            self.add_helper_messages(f"Shorted due to current candle close below previous rsi_13 and above 55 cancel candle ,  Candle used Start # {self.in_trade_candle.short_cancel_due_to_rsi_13_and_Above_55.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")
                            self.short_divergence_candle = self.in_trade_candle.short_cancel_due_to_rsi_13_and_Above_55


                    if converting_to_short and not lowest_rsi_short and self.current_candle.body < 0 and not short_extreme:
                        if "02:37 PM" in self.current_candle.date:
                            print("Put Break Point")
                        previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, True)
                        if previous_highest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15) : #and previous_highest_rsi_candle.close > self.current_candle.close:
                                find_previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(previous_highest_rsi_candle , self.track_all_candles, False)
                                if find_previous_lowest_rsi_candle and self.current_candle.rsi < find_previous_lowest_rsi_candle.rsi \
                                        and self.current_candle.stoch_k > find_previous_lowest_rsi_candle.stoch_k \
                                        and self.current_candle.stoch_d > find_previous_lowest_rsi_candle.stoch_d \
                                        and self.current_candle.rsi_13 > find_previous_lowest_rsi_candle.rsi_13 \
                                        and find_previous_lowest_rsi_candle.rsi_13 < 55 \
                                        and self.current_candle.low > find_previous_lowest_rsi_candle.high:
                                    converting_to_short = False
                                    self.short_divergence_candle = None
                                    cancel_short = True
                                    if end_candle:
                                        end_candle.divergence_used = False
                                        self.update_divergence_used_in_memory_to_false(end_candle)

                                    self.add_helper_messages(f"Three_RSI_2 Short <b>Cancelled</b> Current candle RSI & K is lower but D is higher and also not closed below previous low red,  Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")

                    if converting_to_short and self.current_candle.stoch_k > 80:
                        converting_to_short = False
                        self.short_divergence_candle = None
                        self.in_trade_candle.short_cancelled_due_to_stoch_k_above_80_candle = self.current_candle
                        self.add_helper_messages(f"Cancel Short , RSI K is above 80")
                        if end_candle:
                            end_candle.divergence_used = False
                            self.update_divergence_used_in_memory_to_false(end_candle)


                    if not converting_to_short and self.in_trade_candle.short_cancelled_due_to_stoch_k_above_80_candle and self.current_candle.body < 0:
                        previous_index = pd.Timestamp(self.current_candle.previous_index).round('s')
                        if self.in_trade_candle.short_cancelled_due_to_stoch_k_above_80_candle.index == previous_index:
                            if self.current_candle.close < self.in_trade_candle.short_cancelled_due_to_stoch_k_above_80_candle.low:
                                converting_to_short = True
                                self.add_helper_messages(f"Shorted due to current candle close below previous cancel due to stoch_k above 80")
                                self.short_divergence_candle = self.in_trade_candle.short_cancelled_due_to_stoch_k_above_80_candle

                    if converting_to_short:
                        sell_condition = True
                        buy_condition = False
                        stop_loss = self.get_stop_loss(False)
                        short_condition = True
                        self.update_converting_to_short(start_candle, end_candle)


                    self.track_all_candles_during_buy.append(current_candle)

                if self.short_order:

                    if "03:13 PM" in self.current_candle.date:
                        print("Put Break Point")

                    self.buy_divergence_candle = None
                    if self.copy_data and self.add_candles_short_side:
                        self.track_all_candles_during_short = self.add_candles_short_side.copy()
                        self.copy_data = False
                        self.add_candles_short_side = None

                    self.track_all_candles_during_buy.clear()

                    downward_swings = self.find_downward_swings_from_high(self.track_all_candles_during_short, downward_candles_to_consider, True,None, True)
                    if len(downward_swings) == 1:
                        downward_swing_current = downward_swings[-1]
                        if self.save_downward_swing_current and self.save_downward_swing_current.new_low_candle:
                            if not self.save_downward_swing_current.new_low_candle.new_high_candle or (self.save_downward_swing_current.new_low_candle.new_high_candle and downward_swing_current.new_low_candle.close > self.save_downward_swing_current.new_low_candle.new_high_candle.low):
                                if downward_swing_current.new_low_candle.close > self.save_downward_swing_current.new_low_candle.close and downward_swing_current.new_low_candle.low > self.save_downward_swing_current.new_low_candle.low:
                                    downward_swings.clear()

                    if len(downward_swings) == 1:
                        downward_swing_current = downward_swings[-1]
                        if self.save_downward_swing_current and downward_swing_current.datetime != self.save_downward_swing_current.datetime:
                            if self.save_downward_swing_current.datetime < self.save_downward_swing_current.new_low_candle.datetime:
                                downward_swings.clear()
                                downward_swings.append(self.save_downward_swing_current)
                                downward_swings.append(downward_swing_current)

                    if len(downward_swings) >= 2:
                        previous_downward_swing = downward_swings[-2]
                        if previous_downward_swing.new_low_candle and not previous_downward_swing.new_low_candle.new_high_candle:
                            downward_swings = self.combine_rsi_stoch_fib_numbers(downward_swings)
                            if len(downward_swings) == 2:
                                downward_swing_current = downward_swings[-2]
                                downward_swing_latest = downward_swings[-1]
                                if downward_swing_current.new_low_candle and downward_swing_latest.new_low_candle:
                                    if downward_swing_current.new_low_candle.datetime == downward_swing_latest.new_low_candle.datetime:
                                        downward_swings.clear()
                                        downward_swings.append(downward_swing_current)
                            if len(downward_swings) == 1:
                                downward_swing_current = downward_swings[-1]
                                if not self.save_downward_swing_current:
                                    self.save_downward_swing_current = copy.deepcopy(downward_swing_current)
                                else:
                                    #self.save_downward_swing_previous = copy.deepcopy(self.save_downward_swing_current)
                                    if downward_swing_current.new_low_candle.datetime == self.save_downward_swing_current.new_low_candle.datetime:
                                        downward_swing_current.new_low_candle = self.save_downward_swing_current.new_low_candle
                                    self.save_downward_swing_current = copy.deepcopy(downward_swing_current)
                                    #pass
                                self.track_all_candles_during_buy.clear()
                                downward_swings.clear()

                        if len(downward_swings) == 2:
                            downward_swing_previous = downward_swings[-2]
                            downward_swing_current = downward_swings[-1]
                            if downward_swing_previous.datetime != downward_swing_current.datetime and self.save_downward_swing_current:
                                #self.save_downward_swing_current.previous_swing_info = copy.deepcopy(self.save_downward_swing_previous)
                                self.save_downward_swing_previous = copy.deepcopy(self.save_downward_swing_current)
                                self.save_downward_swing_current = copy.deepcopy(downward_swing_current)
                                self.track_all_candles_during_short = [candle for candle in self.track_all_candles_during_short if candle.datetime >= downward_swing_current.datetime]
                                self.track_all_candles_during_short.clear()
                            if downward_swing_previous.datetime != downward_swing_current.datetime and not self.save_downward_swing_current:
                                #downward_swing_previous.previous_swing_info = copy.deepcopy(self.save_downward_swing_previous)
                                self.save_downward_swing_previous = copy.deepcopy(downward_swing_previous)
                                self.save_downward_swing_current = copy.deepcopy(downward_swing_current)
                                self.track_all_candles_during_short = [candle for candle in self.track_all_candles_during_short if candle.datetime >= downward_swing_current.datetime]
                                self.track_all_candles_during_short.clear()

                            downward_swings.clear()

                    if len(downward_swings) == 0 and self.save_downward_swing_current:
                        if current_candle.close <= self.save_downward_swing_current.new_low_candle.close and current_candle.body < 0:
                            self.save_downward_swing_current.new_low_candle = current_candle
                        downward_swings.append(self.save_downward_swing_current)

                    if len(downward_swings) >= 1:
                        downward_swing_current = downward_swings[-1]
                        self.save_downward_swing_current = downward_swing_current
                        self.add_or_update_swing(self.save_downward_swing_current.datetime, self.save_downward_swing_current)

                        self.update_lower_candle(self.save_downward_swing_current)
                        if downward_swing_current.is_new_low:
                            converting_to_buy, pre_condition_buy = self.check_buy_divergence_during_short()

                        upward_swings = self.find_upward_swings_from_low(self.track_all_candles_during_short, upward_candles_to_consider, True, downward_swing_current.new_low_candle.datetime, False)
                        if len(upward_swings) >= 1:
                            upward_swing_current = upward_swings[-1]
                            if self.current_candle.close > upward_swing_current.new_high_candle.close:
                                upward_swing_current.new_high_candle = self.current_candle
                            self.save_upward_swing_current = upward_swing_current
                            self.update_higher_candle(self.save_upward_swing_current)
                            self.add_or_update_swing(self.save_upward_swing_current.datetime, self.save_upward_swing_current)


                            if self.save_upward_swing_current.new_high_candle:
                                downward_swings = self.find_downward_swings_from_high(self.track_all_candles_during_short, downward_candles_to_consider, True, upward_swing_current.new_high_candle.datetime, False)
                                if len(downward_swings) > 0:
                                    downward_swing = downward_swings[-1]
                                    if downward_swing.datetime != self.save_downward_swing_current.datetime:
                                        if self.save_downward_swing_previous:
                                            #self.save_downward_swing_previous.previous_swing_info = None
                                            #self.save_downward_swing_current.previous_swing_info = self.save_downward_swing_previous
                                            self.save_downward_swing_previous = copy.deepcopy(self.save_downward_swing_current)
                                            self.save_downward_swing_current = downward_swing
                                            self.update_lower_candle(self.save_downward_swing_current)
                                            self.add_or_update_swing(self.save_downward_swing_current.datetime, self.save_downward_swing_current)

                                        if self.save_upward_swing_previous and self.save_upward_swing_previous.datetime != self.save_upward_swing_current.datetime:
                                            #self.save_upward_swing_previous.previous_swing_info = None
                                            #self.save_upward_swing_current.previous_swing_info = self.save_upward_swing_previous
                                            self.save_upward_swing_previous = copy.deepcopy(self.save_upward_swing_current)
                                            candles_clean_up_list = [candle for candle in self.track_all_candles_during_short if candle.datetime >= upward_swing_current.datetime]
                                            self.track_all_candles_during_short = candles_clean_up_list.copy()

                                        if not self.save_upward_swing_previous:
                                            self.save_upward_swing_previous = copy.deepcopy(self.save_upward_swing_current)
                                            candles_clean_up_list = [candle for candle in self.track_all_candles_during_short if candle.datetime >= upward_swing_current.datetime]
                                            self.track_all_candles_during_short = candles_clean_up_list.copy()



                    converting_to_short, pre_condition_short = self.check_short_divergence_during_short()




                    if not pre_condition_buy:
                        converting_to_buy, pre_condition_buy = self.check_buy_divergence_during_short()


                    if converting_to_buy and self.real_buy_divergence_candle:
                        if self.real_buy_divergence_candle.end_candle.index < self.in_trade_candle.index:
                            converting_to_buy = False
                            self.buy_divergence_candle = None
                            self.remove_divergence_info(self.current_candle.index , self.real_buy_divergence_candle)
                        # if converting_to_buy and self.real_buy_divergence_candle.is_extreme:
                        #     lowest_price_candle = self.get_lowest_price_between_start_and_end_divergence(self.real_buy_divergence_candle.start_candle.index, self.real_buy_divergence_candle.end_candle.index, self.real_buy_divergence_candle.end_candle)
                        #     if lowest_price_candle:
                        #         converting_to_buy = False
                        #         self.remove_divergence_info(self.current_candle.index , "BUY")


                    if "10:29 AM" in self.current_candle.date:
                        print("Put Break Point")

                    start_candle = None
                    end_candle = None

                    if converting_to_buy:
                        buy_divergence_info = self.get_divergence_info(self.current_candle.index , "BUY")
                        if buy_divergence_info:
                            time_difference = abs(buy_divergence_info.start_candle.index - buy_divergence_info.end_candle.index)
                            if time_difference < timedelta(minutes=30):
                                if not self.is_extreme_violation(buy_divergence_info):
                                    self.add_helper_messages(f"Divergence condition met for Buy , And Buy Divergence Candle used Start # {buy_divergence_info.start_candle.index.strftime('%I:%M %p')}, End # {buy_divergence_info.end_candle.index.strftime('%I:%M %p')}")
                                    self.add_helper_messages(f"Buy Divergence Candle used {self.buy_divergence_candle.index.strftime('%I:%M %p')}")
                                    start_candle = buy_divergence_info.start_candle
                                    end_candle = buy_divergence_info.end_candle
                                else:
                                    converting_to_buy = False
                                    self.buy_divergence_candle = None
                                    self.remove_divergence_info(self.current_candle.index , buy_divergence_info)
                            else:
                                converting_to_buy = False
                                self.buy_divergence_candle = None
                                self.remove_divergence_info(self.current_candle.index , buy_divergence_info)




                    if not converting_to_buy:
                        converting_to_buy, pre_condition_buy = self.is_artificial_bullish_divergence()
                        if converting_to_buy:
                            self.buy_divergence_candle = self.second_low_rsi_candle_during_short
                            self.add_helper_messages(f"Artificial Buy Divergence created between {self.first_low_rsi_candle_during_short.index.strftime('%I:%M %p')} and {self.second_low_rsi_candle_during_short.index.strftime('%I:%M %p')}")


                    if "11:30 AM" in self.current_candle.date:
                        print("Put Break Point")
                    if not converting_to_buy:
                        buy_divergence_info = self.get_latest_pre_condition_divergence("BUY")
                        if buy_divergence_info and not self.is_extreme_violation(buy_divergence_info) and not buy_divergence_info.end_candle.divergence_used:
                            time_difference = abs(buy_divergence_info.start_candle.index - buy_divergence_info.end_candle.index)
                            if time_difference < timedelta(minutes=30):
                                close_time_difference = None
                                lowest_price_close = None
                                if USE_HIGH_LOW_PRICE:
                                    lowest_price_close = self.get_lowest_price_close_between_dates(buy_divergence_info.end_candle.index, self.current_candle.index)
                                if lowest_price_close:
                                    close_time_difference = abs(buy_divergence_info.end_candle.index - lowest_price_close.index)
                                #previous_green_candle = self.find_previous_green_candle(divergence_info.end_candle.index)
                                if (self.current_candle.close > buy_divergence_info.end_candle.high
                                        or (lowest_price_close and  self.current_candle.close > lowest_price_close.high and close_time_difference < timedelta(minutes=5) and not (self.current_candle.high < buy_divergence_info.start_candle.low))
                                        or (lowest_price_close and  lowest_price_close.rsi < 5 and lowest_price_close.stoch_k > 20 and lowest_price_close.rsi_13 < 45 and  self.current_candle.body > 0 and self.current_candle.previous_body > 0 and close_time_difference < timedelta(minutes=5))):
                                    converting_to_buy = True
                                    buy_divergence_info.end_candle.divergence_used = True
                                    self.update_divergence_used_in_memory(buy_divergence_info.end_candle)
                                    self.buy_divergence_candle = self.get_candle_by_index(buy_divergence_info.end_candle.index)
                                    if lowest_price_close:
                                        self.buy_divergence_candle = self.get_candle_by_index(lowest_price_close.index)

                                    self.add_helper_messages(f"Divergence condition met for Buy , And  Buy Divergence Candle used  Start : {buy_divergence_info.start_candle.index.strftime('%I:%M %p')}, End : {buy_divergence_info.end_candle.index.strftime('%I:%M %p')}")
                                    start_candle = buy_divergence_info.start_candle
                                    end_candle = buy_divergence_info.end_candle



                    # if not converting_to_buy:
                    #     if not self.in_memory_divergence_info:
                    #         self.in_memory_divergence_info = self.get_latest_divergence("BUY")
                    #
                    #     if  self.in_memory_divergence_info:
                    #         lowest_price_candle = self.get_lowest_price_between_dates_below_divergence_end_candle(self.in_memory_divergence_info.end_candle.index, self.current_candle.index)
                    #         if not lowest_price_candle:
                    #             if self.current_candle.close >  self.in_memory_divergence_info.end_candle.high and self.current_candle.body < 0:
                    #                 self.in_memory_buy_divergence_candle = self.current_candle
                    #
                    #     if self.in_memory_buy_divergence_candle:
                    #         if self.current_candle.close > self.in_memory_buy_divergence_candle.high:
                    #             if self.short_divergence_candle and not self.short_divergence_candle.is_extreme_buy_sell:
                    #                 converting_to_buy = True
                    #                 self.add_helper_messages(f"Bought  because current candle closed above Buy Divergence candle  {self.in_memory_buy_divergence_candle.index.strftime('%I:%M %p')}")
                    #                 self.add_helper_messages(f"This is second artificial divergence trigger because it didn't close below latest buy divergence candle Start : {self.in_memory_divergence_info.start_candle.index.strftime('%I:%M %p')}, End : {self.in_memory_divergence_info.end_candle.index.strftime('%I:%M %p')}")
                    #                 self.buy_divergence_candle = self.in_memory_buy_divergence_candle
                    #             if  self.short_divergence_candle and self.short_divergence_candle.is_extreme_buy_sell:
                    #                 if current_candle.close > self.short_divergence_candle.high:
                    #                     converting_to_buy = True
                    #                     self.add_helper_messages(f"Bought  because current candle closed above Buy Divergence candle  {self.in_memory_buy_divergence_candle.index.strftime('%I:%M %p')}")
                    #                     self.add_helper_messages(f"This is second artificial divergence trigger because it didn't close below latest buy divergence candle Start : {self.in_memory_divergence_info.start_candle.index.strftime('%I:%M %p')}, End : {self.in_memory_divergence_info.end_candle.index.strftime('%I:%M %p')}")
                    #                     self.buy_divergence_candle = self.in_memory_buy_divergence_candle


                    bought_due_to_close_above_short = False
                    if self.short_divergence_candle and not converting_to_buy:
                        if self.current_candle.close > self.short_divergence_candle.high:
                            converting_to_buy = True
                            self.add_helper_messages(f"Bought because current candle closed above Short Divergence candle  {self.short_divergence_candle.index.strftime('%I:%M %p')}")
                            self.buy_divergence_candle = self.get_candle_by_index(self.short_divergence_candle.index)
                            bought_due_to_close_above_short = True

                    if self.current_candle.rsi > 5 and self.current_candle.previous_rsi < 5 and not self.second_low_rsi_candle_during_short:
                        self.first_low_rsi_candle_during_short = self.get_candle_by_index(self.current_candle.previous_index)

                    cancel_buy = False
                    cancel_due_to_extreme = False



                    # This Condition  is helping on chart 5/8
                    # Helping 5/8
                    # Not Helping 5/19
                    # Remove is giving negative impact - 1475

                    if not converting_to_buy and self.current_candle.body > 0 and self.current_candle.previous_body > 0 and self.in_trade_candle.buy_divergence_two_cancel_candle_index:
                        buy_divergence_two_cancel_candle = self.get_candle_by_index(self.in_trade_candle.buy_divergence_two_cancel_candle_index)
                        if buy_divergence_two_cancel_candle and (self.current_candle.close > buy_divergence_two_cancel_candle.close
                                                                 and self.current_candle.rsi > buy_divergence_two_cancel_candle.rsi
                                                                 and self.current_candle.rsi_13 > buy_divergence_two_cancel_candle.rsi_13
                                                                 and self.current_candle.stoch_k > buy_divergence_two_cancel_candle.stoch_k) :
                            converting_to_buy = True
                            self.buy_divergence_candle = buy_divergence_two_cancel_candle
                            self.add_helper_messages(f"Buy Due to Previous Divergence Two Cancel,  Candle used Start # {buy_divergence_two_cancel_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")
                            conditons_reason = f"Buy Due to Previous Divergence Two Cancel,  Candle used Start # {buy_divergence_two_cancel_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} "
                            self.log_condition("Script Five, Buy Due to Previous Divergence Two Cancel", conditons_reason, self.current_candle.index )



                    # This Condition  is helping on chart 5/8
                    # Helping 5/8,5/12, 4/3, 4/17, 4/14, 4/24, 3/27, 5/20
                    # Not Helping 4/16, 4/23, 4/4, 5/22, 4/30
                    # Remove is giving negative impact -4450

                    if converting_to_buy:
                        if "09:45 AM" in self.current_candle.date:
                            print("Put Break Point")
                        if start_candle and end_candle:
                            if (start_candle.rsi > 5 and start_candle.stoch_k > 20
                                and end_candle.rsi > 5 and end_candle.stoch_k > 20) and self.current_candle.rsi_13 < 55:
                                converting_to_buy = False
                                self.buy_divergence_candle = None
                                cancel_buy = True
                                cancel_due_to_extreme = True
                                if end_candle:
                                    end_candle.divergence_used = False
                                    self.update_divergence_used_in_memory_to_false(end_candle)
                                self.add_helper_messages(f"Buy <b>Cancelled</b>  because None of the divergence is extreme")


                    # This Condition  is helping on chart 5/8
                    # Helping 5/8, 4/29, 4/21, 4/23, 5/12, 5/5
                    # Not Helping 5/13
                    # Remove is giving negative impact -5250

                    if not converting_to_buy and self.first_low_rsi_candle_during_short and self.first_low_rsi_candle_during_short.index > self.in_trade_candle.index:
                        if self.current_candle.close > self.first_low_rsi_candle_during_short.high and self.current_candle.rsi > 94:
                            converting_to_buy = True
                            self.add_helper_messages(f"Bought because current candle closed above lowest rsi candle   {self.first_low_rsi_candle_during_short.index.strftime('%I:%M %p')}")
                            self.buy_divergence_candle =  self.first_low_rsi_candle_during_short
                            self.buy_divergence_candle.is_extreme_buy_sell = True


                    # This Condition  is helping on chart 5/8
                    # Helping 5/8, 4/7, 4/10, 4/25, 5/1 , 5/12, 4/14, 4/4, 4/15, 3/31, 4/28, 4/3, 4/2, 5/7. 4/29
                    # Not Helping 4/11, 5/9, 5/19, 4/9, 5/5, 5/13, 4/1, 5/14, 4/17
                    # Remove is giving negative impact -7475
                    rsi_higher_buy = False
                    buy_current_rsi_higher_then_previous_higher = False
                    buy_current_rsi_higher_then_previous_higher_candle = None
                    if not converting_to_buy:
                        if "02:35 PM" in self.current_candle.date:
                            print("Put Break Point")
                        if self.current_candle.body > 0 and self.current_candle.previous_body < 0:
                            previous_index = pd.Timestamp(self.current_candle.previous_index).round('s')
                            previous_candle = self.get_candle_by_index(previous_index)
                            previous_highest_rsi_candle = self.find_green_candle_from_low(previous_index, self.track_all_candles)
                            if previous_highest_rsi_candle:
                                if self.current_candle.rsi > previous_highest_rsi_candle.rsi and (self.current_candle.rsi_13 > previous_highest_rsi_candle.rsi_13 or self.current_candle.high >= previous_highest_rsi_candle.high or self.current_candle.close >= self.current_candle.previous_open) and self.current_candle.close < previous_highest_rsi_candle.close:
                                    continue_to_buy = True
                                    if self.current_candle.rsi_13 < 45:
                                        if self.current_candle.low >= self.current_candle.previous_low and self.current_candle.high <= self.current_candle.previous_high \
                                                and self.current_candle.close > previous_highest_rsi_candle.low \
                                                and self.current_candle.open > self.current_candle.previous_close:
                                            continue_to_buy = False
                                            #self.current_candle.rsi_13_below_45_cancel = True
                                    # Fix 4/15 Chart
                                    if continue_to_buy:
                                        converting_to_buy = True
                                        rsi_higher_buy = True
                                        buy_current_rsi_higher_then_previous_higher = True
                                        buy_current_rsi_higher_then_previous_higher_candle = previous_highest_rsi_candle
                                        self.buy_divergence_candle = previous_candle
                                        self.add_helper_messages(f"Buy current rsi higher then previous higher rsi one,  Candle used Start # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")
                                        conditons_reason = f"Buy current rsi higher then previous higher rsi one,  Candle used Start # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}"
                                        self.log_condition("One - Buy current rsi higher then previous higher rsi", conditons_reason, self.current_candle.index )


                    # This Condition  is helping on chart 5/8
                    # Helping 5/8, 5/15, 4/15, 5/19
                    # Not Helping 5/13
                    # Remove is giving positive impact 500
                    if not converting_to_buy and self.current_candle.body > 0 :
                        if "09:42 AM" in self.current_candle.date:
                            print("Put Break Point")
                        previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                        if previous_lowest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_lowest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15): #and previous_highest_rsi_candle.close > self.current_candle.close:
                                previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(previous_lowest_rsi_candle, self.track_all_candles, True)
                                if previous_highest_rsi_candle:
                                    find_previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(previous_highest_rsi_candle, self.track_all_candles, False)
                                    if find_previous_lowest_rsi_candle:
                                        time_difference = abs(previous_highest_rsi_candle.index - find_previous_lowest_rsi_candle.index)
                                        if time_difference < timedelta(minutes=5) and self.current_candle.close > previous_lowest_rsi_candle.high and previous_lowest_rsi_candle.rsi < find_previous_lowest_rsi_candle.rsi and (previous_lowest_rsi_candle.stoch_d > find_previous_lowest_rsi_candle.stoch_d ):
                                            converting_to_buy = True
                                            self.buy_divergence_candle = self.current_candle
                                            skipped_check_for_cancel_due_to_four_or_three = True
                                            self.add_helper_messages(f"Buying Due to Divergence One,  Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')} ")



                    buy_cancelled = False
                    #Ovrerlap Condition
                    skipped_overlap_condition = False

                    # This Condition  is helping on chart 5/8
                    # Helping 4/7, 4/3, 4/11, 5/8, 4/25, 5/7, 4/9, 4/29, 4/10, 4/23, 5/15, 5/1, 3/28, 4/24, 4/4, 4/21
                    # Not Helping 4/15, 3/31, 5/14, 4/2, 4/28, 4/16, 4/1, 5/19, 4/17, 5/20, 5/12, 5/5, 4/30, 5/13, 4/8, 3/27, 4/22, 4/14, 5/22, 5/21, 5/9
                    # Remove is giving negative impact -8325
                    if converting_to_buy:
                        if "10:03 AM" in self.current_candle.date:
                            print("Put Break Point")
                        previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                        if previous_highest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15) : #and previous_highest_rsi_candle.close > self.current_candle.close:
                                find_previous_lowest_rsi_candle = self.find_red_candle_from_high(previous_highest_rsi_candle.index, self.track_all_candles)
                                find_previous_lowest_rsi_candle_first = find_previous_lowest_rsi_candle
                                if ((self.current_candle.rsi > find_previous_lowest_rsi_candle.rsi and self.current_candle.stoch_k < find_previous_lowest_rsi_candle.stoch_k)
                                        or (self.current_candle.rsi < find_previous_lowest_rsi_candle.rsi and self.current_candle.rsi_13 > find_previous_lowest_rsi_candle.rsi_13 and self.current_candle.low > find_previous_lowest_rsi_candle.high)):

                                    skip_condition = False
                                    if (self.current_candle.rsi < find_previous_lowest_rsi_candle.rsi and self.current_candle.rsi_13 > find_previous_lowest_rsi_candle.rsi_13):
                                        conditons_reason = f"Buy <b>Cancelled</b> Due to Divergence One,  Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} "
                                        self.log_condition("Buy Cancelled Due to Divergence One - Nullified-1", conditons_reason, self.current_candle.index )
                                        self.add_helper_messages(f"Buy <b>Cancelled</b> Due to Divergence One- Nullified-1,  Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")

                                    if start_candle and end_candle:
                                        if start_candle.rsi < 5 or end_candle.rsi < 5 :
                                            previous_highest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle, self.track_all_candles, True)
                                            skip_condition = True
                                            if previous_highest_rsi_candle and self.current_candle.open < previous_highest_rsi_candle.close or self.current_candle.close > self.in_trade_candle.low:
                                                skip_condition = False

                                    if rsi_higher_buy :
                                        previous_highest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle, self.track_all_candles, True)
                                        if previous_highest_rsi_candle and previous_highest_rsi_candle.rsi < 5 and previous_highest_rsi_candle.stoch_k < 20 and previous_highest_rsi_candle.rsi_13 < 45:
                                            skip_condition = True
                                    previous_highest_rsi_candle_new = None
                                    if not skip_condition:
                                        previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                                        if previous_lowest_rsi_candle:
                                            time_difference = abs(self.current_candle.index - previous_lowest_rsi_candle.index)
                                            if time_difference < timedelta(minutes=15) : #and previous_highest_rsi_candle.close > self.current_candle.close:
                                                previous_highest_rsi_candle = self.find_previous_highest_high_green_candle(previous_lowest_rsi_candle, self.track_all_candles)
                                                if previous_highest_rsi_candle:
                                                    previous_highest_rsi_candle_new = previous_highest_rsi_candle
                                                    find_previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(previous_highest_rsi_candle, self.track_all_candles, False)
                                                    find_previous_lowest_rsi_13_candle = self.find_previous_lowest_rsi_13_candle_only(previous_lowest_rsi_candle, self.track_all_candles)
                                                    if find_previous_lowest_rsi_candle and find_previous_lowest_rsi_13_candle:
                                                        if (previous_lowest_rsi_candle.rsi > find_previous_lowest_rsi_candle.rsi
                                                                and  previous_lowest_rsi_candle.close < find_previous_lowest_rsi_candle.close
                                                                and previous_lowest_rsi_candle.stoch_d < find_previous_lowest_rsi_13_candle.stoch_d
                                                                and  previous_lowest_rsi_candle.close > find_previous_lowest_rsi_13_candle.close
                                                                and self.current_candle.close > previous_lowest_rsi_candle.high):
                                                            skip_condition = True
                                                            skipped_overlap_condition = True
                                                            conditons_reason = f"Buy <b>Cancelled</b> Due to Divergence One,  Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}"
                                                            self.log_condition("Buy Cancelled Due to Divergence One - Nullified-2", conditons_reason, self.current_candle.index )
                                                            self.add_helper_messages(f"Buy <b>Cancelled</b> Due to Divergence One- Nullified-2,  Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")

                                    if not skip_condition and previous_highest_rsi_candle_new:
                                        if self.current_candle.close > previous_highest_rsi_candle_new.close:
                                            if self.current_candle.rsi_13 > 55 and previous_highest_rsi_candle_new.rsi_13 > 55 and self.current_candle.stoch_k > 80 and self.current_candle.stoch_d > 80 and previous_highest_rsi_candle_new.stoch_k > 80 and previous_highest_rsi_candle_new.stoch_d > 80:
                                                skip_condition = True
                                                skipped_overlap_condition = True
                                                conditons_reason = f"Buy <b>Cancelled</b> Due to Divergence One,  Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}"
                                                self.log_condition("Buy Cancelled Due to Divergence One - Nullified-3", conditons_reason, self.current_candle.index )
                                                self.add_helper_messages(f"Buy <b>Cancelled</b> Due to Divergence One- Nullified-3,  Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")


                                    if not skip_condition:
                                        if (end_candle and find_previous_lowest_rsi_candle and self.current_candle.rsi_13 > 45
                                                and self.current_candle.previous_body > 0):
                                            if ((self.current_candle.close > end_candle.high or self.current_candle.open > find_previous_lowest_rsi_candle.close )
                                                    and self.current_candle.close > self.current_candle.previous_high):
                                                skip_condition = True
                                                skipped_overlap_condition = True
                                                conditons_reason = f"Buy <b>Cancelled</b> Due to Divergence One - Nullified,  Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}"
                                                self.log_condition("Buy Cancelled Due to Divergence One - Nullified-4", conditons_reason, self.current_candle.index )
                                                self.add_helper_messages(f"Buy <b>Cancelled</b> Due to Divergence One- Nullified-4,  Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")



                                    if not skip_condition:
                                        converting_to_buy = False
                                        self.buy_divergence_candle = None
                                        buy_cancelled = True
                                        cancel_buy = True
                                        if not self.in_trade_candle.buy_divergence_one_cancel_candle_index:
                                            self.in_trade_candle.buy_divergence_one_cancel_candle_index = self.current_candle.index
                                        if end_candle:
                                            end_candle.divergence_used = False
                                            self.update_divergence_used_in_memory_to_false(end_candle)
                                        self.add_helper_messages(f"Buy <b>Cancelled</b> Due to Divergence One,  Candle used Start # {find_previous_lowest_rsi_candle_first.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")


                    #Ovrerlap Condition Two
                    # This Condition  is helping on chart 5/8
                    # Helping 5/8, 4/10, 5/7, 5/1, 5/21
                    # Not Helping 5/9, 5/5, 4/22, 5/13, 5/14
                    # Remove is giving negative impact -3950
                    if not converting_to_buy and self.current_candle.body > 0 and self.in_trade_candle.buy_divergence_two_cancel_candle_index:
                        if "03:13 PM" in self.current_candle.date:
                            print("Put Break Point")
                        buy_divergence_two_cancel_candle = self.get_candle_by_index(self.in_trade_candle.buy_divergence_two_cancel_candle_index)
                        if buy_divergence_two_cancel_candle:
                            previous_index = pd.Timestamp(buy_divergence_two_cancel_candle.previous_index).round('s')
                            previous_candle = self.get_candle_by_index(previous_index)
                            previous_high_rsi_2_candle = None
                            previous_high_rsi_13_candle = None
                            if previous_candle:
                                previous_high_rsi_2_candle = self.find_previous_highest_rsi_candle_latest(previous_candle, self.track_all_candles, False)
                                previous_high_rsi_13_candle = self.find_previous_highest_rsi_13_candle_latest(previous_candle, self.track_all_candles)
                            continue_to_buy = False
                            buy_divergence_candle = None
                            if previous_high_rsi_2_candle and self.current_candle.close > previous_high_rsi_2_candle.close  and self.current_candle.rsi > previous_high_rsi_2_candle.rsi:
                                continue_to_buy = True
                                buy_divergence_candle = previous_high_rsi_2_candle

                            elif not continue_to_buy and previous_high_rsi_13_candle and self.current_candle.close > previous_high_rsi_13_candle.close and self.current_candle.rsi_13 > previous_high_rsi_13_candle.rsi_13:
                                continue_to_buy = True
                                buy_divergence_candle = previous_high_rsi_13_candle

                            elif previous_candle and not continue_to_buy and self.current_candle.close > previous_candle.close and self.current_candle.rsi > previous_candle.rsi and self.current_candle.rsi_13 > previous_candle.rsi_13 and self.current_candle.stoch_k > previous_candle.stoch_k:
                                continue_to_buy = True
                                buy_divergence_candle = previous_candle

                            if continue_to_buy:
                                converting_to_buy = True
                                #buy_divergence_candle = previous_high_rsi_13_candle
                                self.buy_divergence_candle = buy_divergence_candle
                                self.add_helper_messages(f"Buying Due Buy Divergence and RSI & Close Break - Two,  Candle used Start # {buy_divergence_two_cancel_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")
                                conditons_reason = f"Buying Due Buy Divergence and RSI & Close Break - Two,  Candle used Start # {buy_divergence_two_cancel_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} "
                                self.log_condition("Buying Due To Buy Divergence and RSI & Close Break - Two", conditons_reason, self.current_candle.index )


                    #Ovrerlap Condition

                    # This Condition  is helping on chart 5/8
                    # Helping 4/10, 5/8, 4/8, 4/11, 5/7, 5/1, 4/28
                    # Not Helping 4/14, 5/9, 5/19, 5/5, 5/21, 5/14, 4/25, 5/13
                    # Remove is giving negative impact -3600
                    if converting_to_buy and self.current_candle.body > 0 and not skipped_overlap_condition :
                        if "03:23 PM" in self.current_candle.date:
                            print("Put Break Point")
                        previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                        if previous_lowest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_lowest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15) : #and previous_highest_rsi_candle.close > self.current_candle.close:
                                previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(previous_lowest_rsi_candle, self.track_all_candles, True)
                                if previous_highest_rsi_candle:
                                    find_previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(previous_highest_rsi_candle, self.track_all_candles, False)
                                    if find_previous_lowest_rsi_candle and self.current_candle.rsi > find_previous_lowest_rsi_candle.rsi and (self.current_candle.stoch_k < find_previous_lowest_rsi_candle.stoch_k):
                                        skip_condition = False
                                        if start_candle and end_candle:
                                            if start_candle.rsi < 5 or end_candle.rsi < 5:
                                                skip_condition = True
                                                if self.current_candle.open < previous_highest_rsi_candle.close:
                                                    skip_condition = False

                                        if rsi_higher_buy :
                                            if previous_highest_rsi_candle and previous_highest_rsi_candle.rsi < 5 and previous_highest_rsi_candle.stoch_k < 20 and previous_highest_rsi_candle.rsi_13 < 45:
                                                skip_condition = True


                                        if not skip_condition:
                                            converting_to_buy = False
                                            self.buy_divergence_candle = None
                                            buy_cancelled = True
                                            cancel_buy = True
                                            if end_candle:
                                                end_candle.divergence_used = False
                                                self.update_divergence_used_in_memory_to_false(end_candle)
                                            self.add_helper_messages(f"Buy <b>Cancelled</b> Due to Divergence Two ,  Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")
                                            if not self.in_trade_candle.buy_divergence_two_cancel_candle_index:
                                                self.in_trade_candle.buy_divergence_two_cancel_candle_index = self.current_candle.index


                    if "01:58 PM" in self.current_candle.date:
                        print("Put Break Point")
                    # This Condition  is helping on chart 5/8
                    # Helping 5/8
                    # Not Helping 5/20
                    # Remove is giving negative impact -1625
                    if converting_to_buy and not rsi_higher_buy and self.current_candle.body > 0 and not skipped_overlap_condition:
                        if "01:58 PM" in self.current_candle.date:
                            print("Put Break Point")
                        continue_to_cancel = False
                        previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, True)
                        if previous_highest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15) : #and previous_highest_rsi_candle.close > self.current_candle.close:
                                find_previous_lowest_rsi_candle = self.find_red_candle_from_high(previous_highest_rsi_candle.index, self.track_all_candles)
                                if find_previous_lowest_rsi_candle:
                                    previous_lowest_rsi_candle = self.find_previous_lowest_price_rsi_candle_new(previous_highest_rsi_candle.index, self.current_candle.index, self.track_all_candles)
                                    if previous_lowest_rsi_candle and previous_lowest_rsi_candle.rsi > find_previous_lowest_rsi_candle.rsi and (previous_lowest_rsi_candle.stoch_k < find_previous_lowest_rsi_candle.stoch_k) and previous_lowest_rsi_candle.low <= find_previous_lowest_rsi_candle.low  <= previous_lowest_rsi_candle.high:
                                        continue_to_cancel = True
                                        previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_extreme(self.current_candle, self.track_all_candles)
                                        if previous_highest_rsi_candle:
                                            if self.current_candle.close > previous_highest_rsi_candle.close or self.current_candle.high > previous_highest_rsi_candle.high :
                                                continue_to_cancel = False
                                                conditons_reason = f"Buy <b>Cancelled</b> Due to Divergence Three,  Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')} "
                                                self.log_condition("New Conditon Cancel Divergence Three Nullified", conditons_reason, self.current_candle.index )
                                        if continue_to_cancel:
                                            converting_to_buy = False
                                            self.buy_divergence_candle = None
                                            buy_cancelled = True
                                            cancel_buy = True
                                            if end_candle:
                                                end_candle.divergence_used = False
                                                self.update_divergence_used_in_memory_to_false(end_candle)

                                            self.add_helper_messages(f"Buy <b>Cancelled</b> Due to Divergence Three,  Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')} ")



                    skipped_check_for_cancel_due_to_four_or_three = False
                    # This Condition  is helping on chart 5/8
                    # Helping 5/8, 4/3, 5/22, 5/16,
                    # Not Helping 5/15, 4/14
                    # Remove is giving negative impact -2475
                    if converting_to_buy and not rsi_higher_buy and self.current_candle.body > 0 and not skipped_overlap_condition:
                        if "11:30 PM" in self.current_candle.date:
                            print("Put Break Point")
                        continue_to_cancel = False
                        previous_highest_rsi_candle = self.find_previous_highest_close_price_candle(self.current_candle, self.track_all_candles)
                        if previous_highest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15) and  time_difference > timedelta(minutes=5): #and previous_highest_rsi_candle.close > self.current_candle.close:
                                if self.current_candle.rsi > previous_highest_rsi_candle.rsi \
                                        and self.current_candle.rsi_13 < previous_highest_rsi_candle.rsi_13 \
                                        and self.current_candle.stoch_k < previous_highest_rsi_candle.stoch_k \
                                        and self.current_candle.low <= previous_highest_rsi_candle.low <= self.current_candle.high:
                                    continue_to_cancel = True

                                    if continue_to_cancel:
                                        previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                                        if previous_lowest_rsi_candle:
                                            time_difference = abs(self.current_candle.index - previous_lowest_rsi_candle.index)
                                            if time_difference < timedelta(minutes=15) : #and previous_highest_rsi_candle.close > self.current_candle.close:
                                                previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(previous_lowest_rsi_candle, self.track_all_candles, True)
                                                if previous_highest_rsi_candle:
                                                    find_previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(previous_highest_rsi_candle, self.track_all_candles, False)
                                                    if find_previous_lowest_rsi_candle:
                                                        if previous_lowest_rsi_candle.open < find_previous_lowest_rsi_candle.open < previous_lowest_rsi_candle.close:
                                                            if find_previous_lowest_rsi_candle.rsi > previous_lowest_rsi_candle.rsi and find_previous_lowest_rsi_candle.stoch_k < previous_lowest_rsi_candle.stoch_k:
                                                                if self.current_candle.rsi > previous_highest_rsi_candle.rsi:
                                                                    continue_to_cancel = False
                                                                    skipped_check_for_cancel_due_to_four_or_three = True
                                                                    conditons_reason = f"Buy <b>Cancelled</b> Due to Divergence Four,  Candle used Start # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} "
                                                                    self.log_condition("Nullify Cancel Buy Divergence Four - Check One", conditons_reason, self.current_candle.index )

                                    if continue_to_cancel:
                                        if end_candle:
                                            condition_one = self.current_candle.rsi > previous_highest_rsi_candle.rsi
                                            condition_two = self.current_candle.rsi_13 > previous_highest_rsi_candle.rsi_13
                                            condition_three = self.current_candle.stoch_k > previous_highest_rsi_candle.stoch_k
                                            match_count = sum([condition_one, condition_two, condition_three])
                                            if self.current_candle.close > end_candle.high and match_count > 2:
                                                continue_to_cancel = False
                                                skipped_check_for_cancel_due_to_four_or_three = True
                                                conditons_reason = f"Buy <b>Cancelled</b> Due to Divergence Four,  Candle used Start # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} "
                                                self.log_condition("Nullify Cancel Buy Divergence Four - Check Two", conditons_reason, self.current_candle.index )

                                    if continue_to_cancel:
                                        converting_to_buy = False
                                        self.buy_divergence_candle = None
                                        buy_cancelled = True
                                        cancel_buy = True
                                        if end_candle:
                                            end_candle.divergence_used = False
                                            self.update_divergence_used_in_memory_to_false(end_candle)

                                        self.add_helper_messages(f"Buy <b>Cancelled</b> Due to Divergence Four,  Candle used Start # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")


                    # This Condition  is helping on chart 5/8
                    # Helping 4/23, 5/8, 4/11, 5/21, 4/7, 4/21, 5/1, 3/28, 5/19
                    # Not Helping 5/6, 5/9, 4/8, 5/22, 4/2, 5/16, 5/7, 4/14, 4/15, 5/15, 4/29, 4/22, 3/27, 5/14, 5/20, 5/12, 4/28, 4/4
                    # Remove is giving negative impact -650
                    if converting_to_buy and not rsi_higher_buy and self.current_candle.body > 0 and not skipped_overlap_condition:
                        if "11:30 AM" in self.current_candle.date:
                            print("Put Break Point")
                        continue_to_cancel = False
                        previous_highest_rsi_candle = self.find_previous_highest_close_price_candle(self.current_candle, self.track_all_candles)
                        if previous_highest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15): #and previous_highest_rsi_candle.close > self.current_candle.close:
                                if self.current_candle.rsi > previous_highest_rsi_candle.rsi \
                                        and (self.current_candle.rsi_13 < previous_highest_rsi_candle.rsi_13 \
                                             or self.current_candle.stoch_k < previous_highest_rsi_candle.stoch_k) \
                                        and not (self.current_candle.low <= previous_highest_rsi_candle.low <= self.current_candle.high):
                                    continue_to_cancel = True

                                    if continue_to_cancel:
                                        previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                                        if previous_lowest_rsi_candle:
                                            time_difference = abs(self.current_candle.index - previous_lowest_rsi_candle.index)
                                            if time_difference < timedelta(minutes=15) : #and previous_highest_rsi_candle.close > self.current_candle.close:
                                                previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(previous_lowest_rsi_candle, self.track_all_candles, True)
                                                if previous_highest_rsi_candle:
                                                    find_previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(previous_highest_rsi_candle, self.track_all_candles, False)
                                                    if find_previous_lowest_rsi_candle:
                                                        if previous_lowest_rsi_candle.open < find_previous_lowest_rsi_candle.open < previous_lowest_rsi_candle.close:
                                                            if find_previous_lowest_rsi_candle.rsi > previous_lowest_rsi_candle.rsi and find_previous_lowest_rsi_candle.stoch_k < previous_lowest_rsi_candle.stoch_k:
                                                                if self.current_candle.rsi > previous_highest_rsi_candle.rsi:
                                                                    continue_to_cancel = False
                                                                    skipped_check_for_cancel_due_to_four_or_three = True
                                                                    conditons_reason = f"Buy <b>Cancelled</b> Due to Divergence Four,  Candle used Start # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} "
                                                                    self.log_condition("Nullify Cancel Buy Divergence Four - Check Three", conditons_reason, self.current_candle.index )

                                    if continue_to_cancel:
                                        if end_candle:
                                            condition_one = self.current_candle.rsi > previous_highest_rsi_candle.rsi
                                            condition_two = self.current_candle.rsi_13 > previous_highest_rsi_candle.rsi_13
                                            condition_three = self.current_candle.stoch_k > previous_highest_rsi_candle.stoch_k
                                            match_count = sum([condition_one, condition_two, condition_three])
                                            if self.current_candle.close > end_candle.high and match_count > 2:
                                                continue_to_cancel = False
                                                skipped_check_for_cancel_due_to_four_or_three = True
                                                conditons_reason = f"Buy <b>Cancelled</b> Due to Divergence Four,  Candle used Start # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} "
                                                self.log_condition("Nullify Cancel Buy Divergence Four - Check Four", conditons_reason, self.current_candle.index )

                                    if continue_to_cancel:
                                        converting_to_buy = False
                                        self.buy_divergence_candle = None
                                        buy_cancelled = True
                                        cancel_buy = True
                                        if end_candle:
                                            end_candle.divergence_used = False
                                            self.update_divergence_used_in_memory_to_false(end_candle)

                                        self.add_helper_messages(f"Buy <b>Cancelled</b> Due to Divergence Four-NEW,  Candle used Start # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")
                                        conditons_reason = f"Buy <b>Cancelled</b> Due to Divergence Four,  Candle used Start # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} "
                                        self.log_condition("Buy Cancelled Due to Divergence Four - NEW", conditons_reason, self.current_candle.index )


                    buying_due_to_divergence_start_candle = None
                    buying_due_to_divergence_end_candle = None
                    buying_due_to_divergence_two = False
                    # This Condition  is helping on chart 5/8
                    # Helping 5/8, 4/17, 5/21, 4/4, 4/24, 5/22, 4/29, 5/9, 5/6
                    # Not Helping
                    # Remove is giving negative impact -5700
                    if not converting_to_buy:
                        if "10:55 AM" in self.current_candle.date:
                            print("Put Break Point")
                        previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, True)
                        if previous_highest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_highest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15): #and previous_highest_rsi_candle.close > self.current_candle.close:
                                previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                                if previous_lowest_rsi_candle:
                                    find_previous_lowest_rsi_candle = self.find_red_with_lowes_k_or_13_candle_from_high(previous_highest_rsi_candle,previous_lowest_rsi_candle, self.track_all_candles)
                                    if find_previous_lowest_rsi_candle:
                                        time_difference = abs(previous_highest_rsi_candle.index - find_previous_lowest_rsi_candle.index)
                                        if time_difference < timedelta(minutes=5) and self.current_candle.close > previous_lowest_rsi_candle.high:
                                            continue_with_buy = True
                                            if self.short_divergence_candle and self.short_divergence_candle.shorted_due_to_all_green:
                                                continue_with_buy = False
                                            if continue_with_buy:
                                                converting_to_buy = True
                                                buying_due_to_divergence_two = True
                                                buying_due_to_divergence_start_candle = find_previous_lowest_rsi_candle
                                                buying_due_to_divergence_end_candle = previous_lowest_rsi_candle
                                                self.add_helper_messages(f"Buying Due to Divergence Two,  Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')} ")

                    rsi_13_below_45_cancelled = False

                    # This Condition  is helping on chart 5/8
                    # Helping 4/10, 4/4, 4/16, 4/17, 4/3, 4/1, 5/7, 5/8, 4/23, 4/28, 3/27, 4/21, 5/19, 5/22, 4/11, 4/29
                    # Not Helping 4/9, 4/7, 5/2, 5/1, 5/21, 5/20, 5/14, 4/25, 4/15, 5/9, 4/24, 5/12, 4/30, 4/8, 5/16, 4/22, 3/31, 5/13, 4/14, 4/2
                    # Remove is giving negative impact -5950
                    if converting_to_buy and not skipped_check_for_cancel_due_to_four_or_three:
                        if "12:29 PM" in self.current_candle.date:
                            print("Put Break Point")
                        if start_candle and end_candle:
                            lowest_close_from_start_candle = self.find_previous_lowest_rsi_candle_latest(end_candle, self.track_all_candles, False)
                            if lowest_close_from_start_candle and lowest_close_from_start_candle.index != start_candle.index and lowest_close_from_start_candle.close < start_candle.close:
                                start_candle = lowest_close_from_start_candle
                            if start_candle.rsi_13 < 45 and end_candle.rsi_13 < 45 and self.current_candle.rsi_13 < 45:

                                continue_to_cancel = True

                                if self.current_candle.close > end_candle.close and self.current_candle.high > end_candle.high and self.current_candle.rsi_13 < 45:
                                    if self.current_candle.stoch_k < 15 and self.current_candle.stoch_d < 15:
                                        continue_to_cancel = False

                                if continue_to_cancel:
                                    if end_candle.rsi < 5 and end_candle.stoch_k < 20 and end_candle.stoch_d < 20 and end_candle.rsi_13 < 45 and self.current_candle.close > end_candle.high :
                                        previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(end_candle, self.track_all_candles, True)
                                        if previous_highest_rsi_candle:
                                            if self.current_candle.rsi > previous_highest_rsi_candle.rsi:
                                                continue_to_cancel = False
                                                conditons_reason = f"Buy <b>Cancelled</b> Start and End Candle RSI_13 is below 45 and Current Candle Didn't close above Divergence Candle, Start # {start_candle.index.strftime('%I:%M %p')}, End # {end_candle.index.strftime('%I:%M %p')} "
                                                self.log_condition("Nullify Cancel Buy Divergence Checking Start & End Candle", conditons_reason, self.current_candle.index )

                                if continue_to_cancel:
                                    if  end_candle.rsi < 5 or start_candle.rsi < 5 or end_candle.stoch_k < 20 or start_candle.stoch_k < 20:
                                        condition_one  = start_candle.stoch_k == 0 and start_candle.stoch_d == 0
                                        condition_two =  start_candle.stoch_k == 0 and end_candle.stoch_d < start_candle.stoch_d

                                        match_count = sum([condition_one, condition_two])
                                        if end_candle.rsi > start_candle.rsi and (end_candle.stoch_k < start_candle.stoch_k or start_candle.stoch_k == 0) and not condition_one and not condition_two and self.current_candle.close > end_candle.high:
                                            previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, True)
                                            if self.current_candle.rsi_13 > previous_highest_rsi_candle.rsi_13:
                                                continue_to_cancel = False
                                                conditons_reason = f"Buy <b>Cancelled</b>  because Start and End Candle RSI and K  is below 5 and 20  and Current Candle Didn't close above Divergence Candle, Candle used Start # {start_candle.index.strftime('%I:%M %p')}, End # {end_candle.index.strftime('%I:%M %p')} "
                                                self.log_condition("Script Five One, Buy Cancelled Nullified because Start and End Candle RSI and K  is below 5 and 20", conditons_reason, self.current_candle.index )
                                                self.add_helper_messages(f"Script Five One, Buy Cancelled Nullified because Start and End Candle RSI and K  is below 5 and 20, Candle used Start # {start_candle.index.strftime('%I:%M %p')}, End # {end_candle.index.strftime('%I:%M %p')} ")


                                if continue_to_cancel:
                                    converting_to_buy = False
                                    self.buy_divergence_candle = None
                                    cancel_buy = True
                                    rsi_13_below_45_cancelled = True
                                    if end_candle:
                                        end_candle.divergence_used = False
                                        self.update_divergence_used_in_memory_to_false(end_candle)

                                    self.add_helper_messages(f"Buy <b>Cancelled</b>  because Start and End Candle RSI 13 is below 45 and Current Candle may have not  close above divergence Candle, Candle used Start # {start_candle.index.strftime('%I:%M %p')}, End # {end_candle.index.strftime('%I:%M %p')} ")

                    buying_due_to_divergence_three = False

                    # This Condition  is helping on chart 5/8
                    # Helping 4/9, 5/8, 4/23, 5/15, 4/15, 4/10, 4/17, 4/21, 5/1, 4/14, 4/22, 5/13, 4/11, 5/2, 4/24, 5/19, 4/1, 5/14
                    # Not Helping 4/4, 5/6, 4/30, 4/3, 3/27, 4/16, 3/31, 5/22, 5/21, 5/20, 4/25
                    # Remove is giving negative impact -7950

                    if not converting_to_buy and self.current_candle.body > 0 and not buy_cancelled and not rsi_13_below_45_cancelled:
                        if "10:29 AM" in self.current_candle.date:
                            print("Put Break Point")
                        previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                        if previous_lowest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_lowest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15): #and previous_highest_rsi_candle.close > self.current_candle.close:
                                previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(previous_lowest_rsi_candle, self.track_all_candles, True)
                                if previous_highest_rsi_candle:
                                    find_previous_lowest_rsi_candle = self.find_red_with_lowes_k_or_13_candle_from_high(previous_highest_rsi_candle,previous_lowest_rsi_candle, self.track_all_candles)
                                    if find_previous_lowest_rsi_candle:
                                        time_difference = abs(previous_highest_rsi_candle.index - find_previous_lowest_rsi_candle.index)
                                        if time_difference < timedelta(minutes=15) and self.current_candle.close > previous_lowest_rsi_candle.high and previous_lowest_rsi_candle.rsi < find_previous_lowest_rsi_candle.rsi:
                                            continue_with_buy = True
                                            if self.short_divergence_candle and self.short_divergence_candle.shorted_due_to_all_green:
                                                continue_with_buy = False
                                            if continue_with_buy:
                                                converting_to_buy = True
                                                buying_due_to_divergence_three = True
                                                buying_due_to_divergence_start_candle = find_previous_lowest_rsi_candle
                                                buying_due_to_divergence_end_candle = previous_lowest_rsi_candle
                                                self.buy_divergence_candle = previous_lowest_rsi_candle
                                                skipped_check_for_cancel_due_to_four_or_three = True
                                                self.add_helper_messages(f"Buying Due to Divergence Three,  Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')} ")


                    # This Condition  is helping on chart 5/8
                    # Helping 4/23, 4/11, 4/8, 5/8, 3/31, 4/22, 4/7, 5/1, 5/7, 5/22, 5/6, 4/28
                    # Not Helping
                    # Remove is giving negative impact -11650

                    if not converting_to_buy and self.current_candle.body > 0 and not buy_cancelled:
                        if "10:58 AM" in self.current_candle.date:
                            print("Put Break Point")
                        previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                        if previous_lowest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_lowest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15): #and previous_highest_rsi_candle.close > self.current_candle.close:
                                previous_highest_rsi_candle = self.find_previous_highest_price_candle(previous_lowest_rsi_candle, self.track_all_candles)
                                if previous_highest_rsi_candle:
                                    find_previous_lowest_rsi_candle = self.find_red_candle_with_lowest_rsi_only(previous_highest_rsi_candle,previous_lowest_rsi_candle, self.track_all_candles)
                                    if find_previous_lowest_rsi_candle:
                                        time_difference = abs(previous_highest_rsi_candle.index - find_previous_lowest_rsi_candle.index)
                                        if time_difference < timedelta(minutes=15):
                                            previous_lowest_price_rsi_candle = self.find_previous_lowest_price_rsi_candle_new(previous_highest_rsi_candle.index, previous_lowest_rsi_candle.index, self.track_all_candles)
                                            if previous_lowest_price_rsi_candle and previous_lowest_price_rsi_candle.low < find_previous_lowest_rsi_candle.low:
                                                find_previous_lowest_rsi_candle = previous_lowest_price_rsi_candle
                                            if previous_lowest_rsi_candle.close >= find_previous_lowest_rsi_candle.low and self.current_candle.close > previous_lowest_rsi_candle.high and find_previous_lowest_rsi_candle.rsi < 5 \
                                                    and previous_lowest_rsi_candle.low <= find_previous_lowest_rsi_candle.open <= previous_lowest_rsi_candle.high:
                                                converting_to_buy = True
                                                start_candle = find_previous_lowest_rsi_candle
                                                end_candle = previous_lowest_rsi_candle
                                                self.add_helper_messages(f"Buying Due to Divergence Four,  Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')} ")


                    # This Condition  is helping on chart 5/8
                    # Helping 5/8, 4/25, 5/1, 5/13, 5/19, 3/31
                    # Not Helping 4/9, 4/2, 4/23
                    # Remove is giving negative impact -1350

                    if not converting_to_buy and self.current_candle.body > 0 and not buy_cancelled:
                        if "09:34 AM" in self.current_candle.date:
                            print("Put Break Point")
                        previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                        if previous_lowest_rsi_candle:
                            short_divergence_info = self.get_divergence_info(previous_lowest_rsi_candle.index, "SHORT")
                            time_difference = abs(self.current_candle.index - previous_lowest_rsi_candle.index)
                            if (not short_divergence_info or not short_divergence_info.is_extreme) and time_difference < timedelta(minutes=15): #and previous_highest_rsi_candle.close > self.current_candle.close:
                                previous_highest_rsi_candle = self.find_previous_highest_price_candle(previous_lowest_rsi_candle, self.track_all_candles)
                                if previous_highest_rsi_candle:
                                    find_previous_lowest_rsi_candle = self.find_red_candle_with_lowest_rsi_only(previous_highest_rsi_candle,previous_lowest_rsi_candle, self.track_all_candles)
                                    if find_previous_lowest_rsi_candle:
                                        time_difference = abs(previous_highest_rsi_candle.index - find_previous_lowest_rsi_candle.index)
                                        if time_difference <= timedelta(minutes=30):
                                            if self.current_candle.close > previous_lowest_rsi_candle.high and previous_lowest_rsi_candle.rsi >  find_previous_lowest_rsi_candle.rsi \
                                                    and (previous_lowest_rsi_candle.stoch_k <  find_previous_lowest_rsi_candle.stoch_k or previous_lowest_rsi_candle.stoch_d <  find_previous_lowest_rsi_candle.stoch_d) \
                                                    and not (previous_lowest_rsi_candle.low <= find_previous_lowest_rsi_candle.high <= previous_lowest_rsi_candle.high) \
                                                    and find_previous_lowest_rsi_candle.high < previous_lowest_rsi_candle.low:
                                                converting_to_buy = True
                                                self.buy_divergence_candle = previous_lowest_rsi_candle
                                                self.add_helper_messages(f"Script Five, Buying Due to Divergence Five,  Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')} ")
                                                conditons_reason = f"Buying Due to Divergence Five,  Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')} "
                                                self.log_condition("Script Five Fix, Added buy divergence candle if trade goes wrong.", conditons_reason, self.current_candle.index )


                    # This Condition  is helping on chart 5/8
                    # Helping 4/7, 5/8, 4/10, 4/21, 5/1, 4/15, 4/1, 4/22, 5/9, 4/3, 4/14, 4/29, 4/30
                    # Not Helping 4/8, 4/4, 4/11, 3/31, 5/20, 5/19, 3/27, 3/28, 5/7, 5/13, 4/2, 4/23, 5/16
                    # Remove is giving negative impact -5200

                    if  converting_to_buy and rsi_higher_buy:
                        if "12:32 PM" in self.current_candle.date:
                            print("Put Break Point")
                        if self.current_candle.body > 0 and self.current_candle.previous_body < 0:
                            previous_index = pd.Timestamp(self.current_candle.previous_index).round('s')
                            previous_highest_rsi_candle = self.find_green_candle_from_low(previous_index, self.track_all_candles)
                            if previous_highest_rsi_candle:
                                if self.current_candle.rsi_13 < 55 and not (self.current_candle.low <= previous_highest_rsi_candle.low <= self.current_candle.high):
                                    converting_to_buy = False
                                    self.buy_divergence_candle = None
                                    cancel_buy = True
                                    self.add_helper_messages(f"Buy <b>Cancelled</b>  because  RSI 13 is below 55 and OHLC , Candle used Start # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")
                                    previous_candle = self.get_candle_by_index(previous_index)
                                    if previous_candle.rsi < 5 and previous_candle.stoch_k < 20 and previous_candle.stoch_d < 20 and previous_candle.rsi_13 < 45:
                                        previous_lowest_rsi_extreme_candle = self.find_previous_lowest_rsi_or_rsi_13_ir_stoch_k_candle_latest(previous_candle, self.track_all_candles)
                                        if previous_lowest_rsi_extreme_candle:
                                            time_difference = abs(self.current_candle.index - previous_lowest_rsi_extreme_candle.index)
                                            if time_difference < timedelta(minutes=120):
                                                if previous_lowest_rsi_extreme_candle.low < previous_candle.low: # and previous_candle.rsi < previous_lowest_rsi_extreme_candle.rsi and previous_candle.rsi_13 < previous_lowest_rsi_extreme_candle.rsi_13 and previous_candle.stoch_k <= previous_lowest_rsi_extreme_candle.stoch_k and previous_candle.stoch_d <= previous_lowest_rsi_extreme_candle.stoch_d:
                                                    self.in_trade_candle.lowest_candle_cancelled_before = previous_candle
                                                    conditons_reason = f"Buy <b>Cancelled</b>  because  RSI 13 is below 55 and OHLC , Candle used Start # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} "
                                                    self.log_condition("New Condition  to Store Previous Candle to Buy Next Time , Using Lowest RSI 13 or RSI or K", conditons_reason, self.current_candle.index )
                                    if end_candle:
                                        end_candle.divergence_used = False
                                        self.update_divergence_used_in_memory_to_false(end_candle)


                    # This Condition  is helping on chart 5/8
                    # Helping 5/8, 4/15, 4/1, 5/12, 5/2, 3/28, 5/19, 4/2 , 5/13
                    # Not Helping 4/4, 4/29, 5/9, 5/16, 5/5, 5/14, 4/25
                    # Remove is giving negative impact -2450

                    if not converting_to_buy and not cancel_buy and self.current_candle.body > 0 and self.current_candle.stoch_k > 20:
                        if "02:54 PM" in self.current_candle.date:
                            print("Put Break Point")

                        previous_lowest_rsi_candle = self.find_previous_lowest_low_red_candle(self.current_candle, self.track_all_candles)
                        if previous_lowest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_lowest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15) :
                                lowest_close_red_candle_between_start_end = self.find_lowest_close_red_candle_between_start_end(previous_lowest_rsi_candle.index, self.current_candle.index ,  self.track_all_candles)
                                if lowest_close_red_candle_between_start_end and lowest_close_red_candle_between_start_end.close < previous_lowest_rsi_candle.close:
                                    previous_lowest_rsi_candle = lowest_close_red_candle_between_start_end
                                find_previous_lowest_rsi_13_candle = self.find_previous_lowest_rsi_13_candle_only(previous_lowest_rsi_candle, self.track_all_candles)

                                highest_close_green_candle_between_start_end = self.find_highest_close_green_candle_between_start_end(previous_lowest_rsi_candle.index, self.current_candle.index ,  self.track_all_candles)
                                if highest_close_green_candle_between_start_end and highest_close_green_candle_between_start_end.index == self.current_candle.index:
                                    if self.current_candle.low <= previous_lowest_rsi_candle.open <= self.current_candle.high:
                                        if find_previous_lowest_rsi_13_candle and self.current_candle.rsi_13 < 55:
                                            if (previous_lowest_rsi_candle.rsi <=  find_previous_lowest_rsi_13_candle.rsi
                                                    and previous_lowest_rsi_candle.stoch_k <=  find_previous_lowest_rsi_13_candle.stoch_k
                                                    and previous_lowest_rsi_candle.stoch_d <=  find_previous_lowest_rsi_13_candle.stoch_d
                                                    and previous_lowest_rsi_candle.rsi_13 > find_previous_lowest_rsi_13_candle.rsi_13
                                                    and previous_lowest_rsi_candle.close > find_previous_lowest_rsi_13_candle.close
                                                    and  self.current_candle.close >= previous_lowest_rsi_candle.open):

                                                short_divergence_info = self.get_divergence_info(self.current_candle.index , "SHORT")
                                                if not short_divergence_info:
                                                    converting_to_buy = True
                                                    self.buy_divergence_candle = previous_lowest_rsi_candle
                                                    self.add_helper_messages(f"Buying Due Divergence between RSI & RSI_13 , Candle used Start # {find_previous_lowest_rsi_13_candle.index.strftime('%I:%M %p')}, End # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')}  ")


                    # This Condition  is helping on chart 5/8
                    # Helping 4/7, 5/8, 4/28
                    # Not Helping 4/10, 4/2
                    # Remove is giving negative impact -2450
                    if not converting_to_buy and self.current_candle.body > 0 and not cancel_buy:
                        previous_index = pd.Timestamp(self.current_candle.previous_index).round('s')
                        if (self.in_trade_candle and self.short_divergence_candle and self.in_trade_candle.index == previous_index
                                and self.in_trade_candle.close != self.current_candle.open
                                and self.current_candle.low > self.in_trade_candle.low ):
                            if self.current_candle.rsi > 55 and self.current_candle.close > self.short_divergence_candle.close and self.current_candle.close > self.in_trade_candle.open:
                                converting_to_buy = True
                                self.buy_divergence_candle = self.current_candle
                                self.add_helper_messages(f"Buying Due close above previous divergence close and also close above in_trade open,  Candle used Start # {self.in_trade_candle.index.strftime('%I:%M %p')}, End # {self.short_divergence_candle.index.strftime('%I:%M %p')} ")



                    # This Condition  is helping on chart 5/8
                    # Helping 5/8, 4/15
                    # Not Helping
                    # Remove is giving negative impact -2600
                    buying_immediately_on_green_candle = False
                    if not converting_to_buy and self.current_candle.body > 0 and not cancel_buy:
                        if "09:37 AM" in self.current_candle.date:
                            print("Put Break Point")
                        if self.current_candle.high > self.current_candle.previous_high and self.current_candle.rsi_13 > 55:
                            buy_divergence_info = self.get_divergence_info(self.current_candle.index, "BUY")
                            if buy_divergence_info:
                                if buy_divergence_info.end_candle.rsi > buy_divergence_info.start_candle.rsi \
                                        and buy_divergence_info.end_candle.rsi_13 < buy_divergence_info.start_candle.rsi_13 \
                                        and buy_divergence_info.end_candle.stoch_k < buy_divergence_info.start_candle.stoch_k:
                                    lowest_price_candle = self.find_candle_with_lowest_low_price_candle(buy_divergence_info.start_candle.index, buy_divergence_info.end_candle.index, self.track_all_candles)
                                    if lowest_price_candle:
                                        if lowest_price_candle.low < buy_divergence_info.end_candle.low:
                                            converting_to_buy = True
                                            buying_immediately_on_green_candle = True
                                            self.buy_divergence_candle = buy_divergence_info.end_candle
                                            self.add_helper_messages(f"Buying Immediately on Green Candle , the high is taken,  Candle used Start # {buy_divergence_info.start_candle.index.strftime('%I:%M %p')}, End # {buy_divergence_info.end_candle.index.strftime('%I:%M %p')} ")

                    # This Condition  is helping on chart 5/8
                    # Helping 5/8, 4/22, 3/31, 5/6
                    # Not Helping
                    # Remove is giving negative impact -3950
                    if not converting_to_buy:
                        if "09:55 AM" in self.current_candle.date:
                            print("Put Break Point")
                        if self.current_candle.body > 0:
                            previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                            if previous_lowest_rsi_candle:
                                previous_highest_rsi_candle = self.find_green_candle_from_low(previous_lowest_rsi_candle.index, self.track_all_candles)
                                if self.current_candle.rsi > previous_highest_rsi_candle.rsi and (self.current_candle.rsi_13 > previous_highest_rsi_candle.rsi_13 or self.current_candle.rsi_13 > 55) and self.current_candle.close < previous_highest_rsi_candle.close:
                                    continue_to_buy = True
                                    if (self.current_candle.rsi_13 < 45 or self.current_candle.low < previous_highest_rsi_candle.open  < self.current_candle.high \
                                            or self.current_candle.low < previous_highest_rsi_candle.close  < self.current_candle.high
                                            or previous_highest_rsi_candle.body_percent <= 10):
                                        continue_to_buy = False
                                        #self.current_candle.rsi_13_below_45_cancel = True
                                    if continue_to_buy:
                                        if self.in_trade_candle.divergence_start_candle and self.in_trade_candle.divergence_end_candle:
                                            short_divergence_info = self.get_divergence_info(self.in_trade_candle.divergence_end_candle.index, "SHORT")
                                            if short_divergence_info and short_divergence_info.is_extreme:
                                                continue_to_buy = False
                                    if continue_to_buy:
                                        converting_to_buy = True
                                        rsi_higher_buy = True
                                        buy_current_rsi_higher_then_previous_higher = True
                                        buy_current_rsi_higher_then_previous_higher_candle = previous_highest_rsi_candle
                                        self.add_helper_messages(f"Buy current rsi higher then previous higher rsi two,  Candle used Start # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")

                    # This Condition  is helping on chart 4/28 at 11:53 AM
                    # This Condition  is helping on chart 5/07 at 03:14 PM
                    # Helping 4/28, 5/8, 5/7, 5/5, 4/15, 4/29, 5/16, 5/2, 5/22, 5/21
                    # Not Helping 4/9, 4/4, 5/19, 4/3, 5/14, 5/6, 5/12
                    # Remove is giving negative impact  -4625
                    if converting_to_buy and not rsi_higher_buy  and not buying_due_to_divergence_three and not bought_due_to_close_above_short:
                        if "11:32 AM" in self.current_candle.date:
                            print("Put Break Point")
                        short_divergence_info = self.get_divergence_info(self.current_candle.index, "SHORT")
                        buy_divergence_info = self.get_divergence_info(self.current_candle.index, "BUY")
                        if short_divergence_info and not buy_divergence_info:
                            if (short_divergence_info.end_candle.rsi > short_divergence_info.start_candle.rsi
                                    and short_divergence_info.end_candle.close < short_divergence_info.start_candle.open
                                    and self.in_trade_candle.low < short_divergence_info.end_candle.close):
                                self.add_helper_messages(f"Buy <b>Cancelled</b>  because due to short divergence and short divergence end candel close below start candle open")
                                converting_to_buy = False
                                self.buy_divergence_candle = None
                                # if end_candle:
                                #     end_candle.divergence_used = False
                                #     self.update_divergence_used_in_memory_to_false(end_candle)

                    # This Condition is helping on chart 4/24 at 10:41 AM
                    # Helping 5/8, 4/24, 4/15, 4/28
                    # Not Helping 4/8, 4/4, 4/22, 4/30, 3/28
                    # Remove is giving positive impact 1450
                    if converting_to_buy and not buying_immediately_on_green_candle:
                        time_difference = abs(self.current_candle.index - self.in_trade_candle.index)
                        if time_difference < timedelta(minutes=3) :
                            if (self.in_trade_candle.rsi < self.in_trade_candle.previous_rsi
                                    and self.in_trade_candle.rsi_13 < self.in_trade_candle.previous_rsi_13
                                    and self.in_trade_candle.stoch_k < self.in_trade_candle.previous_stoch_k
                                    and self.in_trade_candle.stoch_d < self.in_trade_candle.previous_stoch_d
                                    and self.in_trade_candle.previous_stoch_k > 80
                                    and self.in_trade_candle.previous_stoch_d > 80):
                                if self.current_candle.close < self.in_trade_candle.open:
                                    if self.in_trade_candle.low <= self.current_candle.high <= self.in_trade_candle.high:
                                        self.add_helper_messages(f"Buy <b>Cancelled</b>  because current candle didn't close above in_trade candle which all are down compared to previous candle ")
                                        converting_to_buy = False
                                        self.buy_divergence_candle = None
                                        # if end_candle:
                                        #     end_candle.divergence_used = False
                                        #     self.update_divergence_used_in_memory_to_false(end_candle)

                    # This Condition is helping on chart
                    # Helping 5/8
                    # Not Helping
                    # Remove is giving positive impact -1850
                    if converting_to_buy and buying_due_to_divergence_three:
                        if self.current_candle.rsi_13 < 35:
                            if buying_due_to_divergence_start_candle.open > self.current_candle.close and  buying_due_to_divergence_start_candle.high > self.current_candle.high:
                                self.add_helper_messages(f"Buy <b>Cancelled</b>  RSI Below 35 and start candle open high is greater then buy candle , Candle used Start # {buying_due_to_divergence_start_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")
                                converting_to_buy = False
                                self.buy_divergence_candle = None


                    # This Condition is helping on chart
                    # Helping 5/8
                    # Not Helping
                    # Remove is giving positive impact -1850

                    # Adding or Removing is not giving any impact
                    if converting_to_buy and buying_due_to_divergence_three:
                        if self.current_candle.rsi_13 < 40:
                            if (buying_due_to_divergence_start_candle.rsi > buying_due_to_divergence_end_candle.rsi
                                    and  buying_due_to_divergence_start_candle.rsi_13 < buying_due_to_divergence_end_candle.rsi_13
                                    and buying_due_to_divergence_start_candle.open < self.current_candle.close and  buying_due_to_divergence_start_candle.high < self.current_candle.high
                                    and buying_due_to_divergence_end_candle.low < self.current_candle.low):
                                self.add_helper_messages(f"Buy <b>Cancelled</b>  RSI Below 40 and start and end  candle RSI & RSI 13 diverge  , Candle used Start # {buying_due_to_divergence_start_candle.index.strftime('%I:%M %p')}, End # {buying_due_to_divergence_end_candle.index.strftime('%I:%M %p')}")
                                converting_to_buy = False
                                self.buy_divergence_candle = None

                    # This Condition is helping on chart
                    # Helping 5/8
                    # Not Helping
                    # Remove is giving positive impact -1850

                    if converting_to_buy and buy_current_rsi_higher_then_previous_higher:
                        if self.current_candle.rsi_13 < 35:
                            if (self.current_candle.high < buy_current_rsi_higher_then_previous_higher_candle.high
                                    and self.current_candle.low < buy_current_rsi_higher_then_previous_higher_candle.low
                                    and self.current_candle.rsi_13 > buy_current_rsi_higher_then_previous_higher_candle.rsi_13
                                    and self.current_candle.close <=  buy_current_rsi_higher_then_previous_higher_candle.open):
                                self.add_helper_messages(f"Buy <b>Cancelled</b>  RSI Below 35 and  Buy candle high & low is below start candle    , Candle used Start # {buy_current_rsi_higher_then_previous_higher_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")
                                converting_to_buy = False
                                self.buy_divergence_candle = None

                    # This Condition is helping on chart
                    # Helping 5/8
                    # Not Helping
                    # Remove is giving positive impact -1850
                    if converting_to_buy and (buying_due_to_divergence_three or buying_due_to_divergence_two):
                        if "10:20 AM" in self.current_candle.date:
                            print("Put Break Point")
                        if self.current_candle.rsi_13 < 55:
                            if (buying_due_to_divergence_start_candle.rsi_13 < 30 and buying_due_to_divergence_end_candle.rsi_13 < 30
                                    and buying_due_to_divergence_start_candle.rsi > buying_due_to_divergence_end_candle.rsi
                                    and buying_due_to_divergence_start_candle.rsi_13 > buying_due_to_divergence_end_candle.rsi_13
                                    and buying_due_to_divergence_start_candle.stoch_k < buying_due_to_divergence_end_candle.stoch_k
                                    and buying_due_to_divergence_start_candle.stoch_d < buying_due_to_divergence_end_candle.stoch_d
                                    and (buying_due_to_divergence_start_candle.stoch_k < 20 or buying_due_to_divergence_end_candle.stoch_k < 20)
                                    and (buying_due_to_divergence_start_candle.stoch_d < 20 or buying_due_to_divergence_end_candle.stoch_d < 20)):
                                self.add_helper_messages(f"Buy <b>Cancelled</b>  RSI Below 55 and start and end  candle RSI & RSI 13 is going lower   , Candle used Start # {buying_due_to_divergence_start_candle.index.strftime('%I:%M %p')}, End # {buying_due_to_divergence_end_candle.index.strftime('%I:%M %p')}")

                                if end_candle:
                                    end_candle.divergence_used = True
                                    self.update_divergence_used_in_memory(end_candle)

                                converting_to_buy = False
                                self.buy_divergence_candle = None
                                self.trend_is_down_check_for_rsi_13_above_55_for_buy = True



                    # This Condition is helping on chart
                    # Helping 5/8
                    # Not Helping
                    # Remove is giving positive impact -1850
                    if converting_to_buy and self.trend_is_down_check_for_rsi_13_above_55_for_buy:
                        if not skipped_check_for_cancel_due_to_four_or_three:
                            if self.current_candle.rsi_13 < 55 :
                                converting_to_buy = False
                                self.buy_divergence_candle = None
                                self.add_helper_messages(f"Buy <b>Cancelled</b> Trend is Down and any Buy should be above 55")
                                conditons_reason = f"Buy <b>Cancelled</b> Trend is Down and any Buy should be above 55"
                                self.log_condition("Buy Cancelled Trend is Down and any Buy should be above 55", conditons_reason, self.current_candle.index )




                    # This Condition is helping on chart
                    # Helping 5/8
                    # Not Helping
                    # Remove is giving positive impact -1850
                    if not converting_to_buy and self.in_trade_candle.lowest_candle_cancelled_before and self.current_candle.body > 0:
                        if self.current_candle.close > self.in_trade_candle.lowest_candle_cancelled_before.high and self.current_candle.previous_body > 0:
                            if self.in_trade_candle.lowest_candle_cancelled_previous_highest_rsi_candle:
                                continue_to_buy = True
                                if self.current_candle.rsi_13 < self.in_trade_candle.lowest_candle_cancelled_previous_highest_rsi_candle.rsi_13 and self.current_candle.rsi >  self.in_trade_candle.lowest_candle_cancelled_previous_highest_rsi_candle.rsi:
                                    continue_to_buy = False
                                if continue_to_buy:
                                    converting_to_buy = True
                                    self.add_helper_messages(f"Buying Due To current candle closed  above previous candel  which was cancelled before due to all extreme down")
                                    conditons_reason = f"Buying Due To current candle closed  above previous candel  which was cancelled before due to all extreme down"
                                    self.log_condition("Closed Above Before Previous Cancelled Buy ", conditons_reason, self.current_candle.index )



                    # This Condition is helping on chart
                    # Helping 5/8, 4.25, 4/24, 5/22
                    # Not Helping 5/19
                    # Remove is giving positive impact -2100
                    if not converting_to_buy and self.current_candle.body > 0 and not cancel_buy:
                        if "03:13 AM" in self.current_candle.date:
                            print("Put Break Point")

                        buy_divergence_info = self.get_divergence_info(self.current_candle.index, "BUY")
                        if buy_divergence_info and buy_divergence_info.is_extreme:
                            highest_rsi_green_candle = self.get_highest_rsi_candle_between_dates(buy_divergence_info.start_candle.index, buy_divergence_info.end_candle.index)
                            if highest_rsi_green_candle:
                                if self.current_candle.close > highest_rsi_green_candle.close and self.current_candle.close > self.current_candle.previous_high and self.current_candle.rsi > highest_rsi_green_candle.rsi:
                                    continue_with_buy = True
                                    highest_rsi_13 = self.find_previous_highest_rsi_13_candle_latest(self.current_candle, self.track_all_candles)
                                    if highest_rsi_13 and self.current_candle.rsi > highest_rsi_13.rsi and self.current_candle.rsi_13 < highest_rsi_13.rsi_13:
                                        continue_with_buy = False
                                        conditons_reason = f"Buying Due Buy Divergence and RSI & Close Break, Cancelled,  Candle used Start # {highest_rsi_green_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} "
                                        self.log_condition("Buying Due To Buy Divergence and RSI & Close Break, One Cancelled Due to RSI & RSI 13 Divergence", conditons_reason, self.current_candle.index )

                                    if continue_with_buy:
                                        converting_to_buy = True
                                        self.buy_divergence_candle = buy_divergence_info.end_candle
                                        start_candle = buy_divergence_info.start_candle
                                        end_candle = buy_divergence_info.end_candle
                                        self.add_helper_messages(f"Buying Due Buy Divergence and RSI & Close Break,  Candle used Start # {highest_rsi_green_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")
                                        conditons_reason = f"Buying Due Buy Divergence and RSI & Close Break,  Candle used Start # {highest_rsi_green_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} "
                                        self.log_condition("Buying Due To Buy Divergence and RSI & Close Break", conditons_reason, self.current_candle.index )



                    # This Condition is helping on chart
                    # Helping 5/8
                    # Not Helping 5/7
                    # Remove is giving positive impact 925
                    #Ovrerlap Condition
                    if converting_to_buy and self.current_candle.body > 0 :
                        if "10:14 AM" in self.current_candle.date:
                            print("Put Break Point")
                        skip_buying = False
                        previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                        if previous_lowest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_lowest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15) : #and previous_highest_rsi_candle.close > self.current_candle.close:
                                if self.current_candle.open < previous_lowest_rsi_candle.open < self.current_candle.close:
                                    condition_one = self.current_candle.rsi > 94
                                    condition_two = self.current_candle.stoch_k > 80
                                    condition_three = self.current_candle.rsi_13 > 45
                                    high_rsi_13_candle = self.find_previous_highest_rsi_13_candle_latest(self.current_candle, self.track_all_candles)
                                    high_rsi_candle = self.find_previous_highest_rsi_candle_latest(previous_lowest_rsi_candle, self.track_all_candles, False)
                                    match_count = sum([condition_one, condition_two, condition_three])
                                    check_condition = True
                                    if (match_count >= 2 or (high_rsi_13_candle and self.current_candle.close > high_rsi_13_candle.close)) and self.current_candle.rsi_13 > 55 :
                                        check_condition = False

                                    if check_condition and (match_count >= 1 or (high_rsi_candle and self.current_candle.close > high_rsi_candle.close and self.current_candle.rsi > high_rsi_candle.rsi and self.current_candle.rsi_13 > high_rsi_candle.rsi_13 and self.current_candle.stoch_k > high_rsi_candle.stoch_k)):
                                        check_condition = False

                                    if check_condition and previous_lowest_rsi_candle and self.current_candle.rsi > previous_lowest_rsi_candle.rsi and (previous_lowest_rsi_candle.stoch_k > self.current_candle.stoch_k or previous_lowest_rsi_candle.stoch_d >  self.current_candle.stoch_d):
                                        skip_buying = True

                                    if skip_buying and end_candle and start_candle:
                                        if  end_candle.rsi < 5 or start_candle.rsi < 5 or end_candle.stoch_k < 20 or start_candle.stoch_k < 20:
                                            if end_candle.rsi > start_candle.rsi and end_candle.stoch_k < start_candle.stoch_k:
                                                skip_buying = False
                                                conditons_reason = f"Buy <b>Cancelled</b>  because Start and End Candle RSI and K  is below 5 and 20  and Current Candle Didn't close above Divergence Candle, Candle used Start # {start_candle.index.strftime('%I:%M %p')}, End # {end_candle.index.strftime('%I:%M %p')} "
                                                self.log_condition("Script Five Two, Buy Cancelled because Start and End Candle RSI and K  is below 5 and 20", conditons_reason, self.current_candle.index )


                                    if skip_buying:
                                        converting_to_buy = False
                                        self.buy_divergence_candle = None
                                        buy_cancelled = True
                                        cancel_buy = True
                                        if end_candle:
                                            end_candle.divergence_used = False
                                            self.update_divergence_used_in_memory_to_false(end_candle)
                                        self.add_helper_messages(f"Buy <b>Cancelled</b> Due to Divergence Two, Ovrerlap Condition ,  Candle used Start # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")
                                        conditons_reason = f"Buy <b>Cancelled</b> Due to Divergence Two,  Candle used Start # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} "
                                        self.log_condition("Buy Cancelled Due to Divergence Two, Ovrerlap Condition and No Extreme", conditons_reason, self.current_candle.index )
                                        if not self.in_trade_candle.buy_divergence_two_cancel_candle_index:
                                            self.in_trade_candle.buy_divergence_two_cancel_candle_index = self.current_candle

                    # This Condition is helping on chart
                    # Helping 5/8
                    # Not Helping
                    # Remove is giving positive impact -1850
                    if not converting_to_buy and self.current_candle.body > 0 :
                        if "02:01 PM" in self.current_candle.date:
                            print("Put Break Point")
                        rsi_below_5_candle = self.find_previous_lowest_rsi_candle_extreme(self.current_candle, self.track_all_candles)
                        if rsi_below_5_candle:
                            time_difference = abs(self.current_candle.index - rsi_below_5_candle.index)
                            if time_difference < timedelta(minutes=15) :
                                lowest_rsi_13_candle = self.find_previous_lowest_rsi_13_candle_only(rsi_below_5_candle, self.track_all_candles)
                                if lowest_rsi_13_candle:
                                    if lowest_rsi_13_candle.close > rsi_below_5_candle.close and self.current_candle.close > rsi_below_5_candle.high:
                                        continue_to_buy = True
                                        previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                                        if previous_highest_rsi_candle:
                                            previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(previous_highest_rsi_candle, self.track_all_candles, False)
                                        previous_highest_rsi_13_candle = self.find_previous_highest_rsi_13_candle_latest(self.current_candle, self.track_all_candles)
                                        if previous_highest_rsi_candle and  rsi_below_5_candle.index < previous_highest_rsi_candle.index < self.current_candle.index:
                                            if previous_highest_rsi_candle.close > self.current_candle.close:
                                                continue_to_buy = False

                                        if continue_to_buy:
                                            if previous_lowest_rsi_candle and self.current_candle.rsi > previous_lowest_rsi_candle.rsi and previous_lowest_rsi_candle.stoch_k > self.current_candle.stoch_k:
                                                continue_to_buy = False

                                        if continue_to_buy:
                                            if previous_highest_rsi_13_candle and self.current_candle.rsi < previous_highest_rsi_13_candle.rsi and previous_highest_rsi_13_candle.rsi_13 > self.current_candle.rsi_13:
                                                continue_to_buy = False

                                        if continue_to_buy:
                                            highest_rsi_13 = self.find_previous_highest_rsi_13_candle_latest(self.current_candle, self.track_all_candles)
                                            if highest_rsi_13 and self.current_candle.rsi > highest_rsi_13.rsi and self.current_candle.rsi_13 < highest_rsi_13.rsi_13:
                                                continue_to_buy = False
                                                conditons_reason = f"Buying Due Buy Divergence and RSI & Close Break, Cancelled,  Candle used Start # {lowest_rsi_13_candle.index.strftime('%I:%M %p')}, End # {rsi_below_5_candle.index.strftime('%I:%M %p')} "
                                                self.log_condition("Buying Due To Buy Divergence and RSI & Close Break, Two Cancelled Due to RSI & RSI 13 Divergence", conditons_reason, self.current_candle.index )

                                        if continue_to_buy:
                                            converting_to_buy = True
                                            self.add_helper_messages(f"Buying Due To RSI 13 Divergence , Candle used Start # {lowest_rsi_13_candle.index.strftime('%I:%M %p')}, End # {rsi_below_5_candle.index.strftime('%I:%M %p')} ")
                                            conditons_reason = f"Buying Due To RSI 13 Divergence , Candle used Start # {lowest_rsi_13_candle.index.strftime('%I:%M %p')}, End # {rsi_below_5_candle.index.strftime('%I:%M %p')} "
                                            self.log_condition("Buying Due To RSI 13 Divergence, Using Lowest RSI 13 Close", conditons_reason, self.current_candle.index )


                    # This Condition is helping on chart
                    # Helping 4/10, 5/8, 4/17, 3/31, 4/30, 3/28, 4/2, 4/11, 5/19, 5/16, 4/15, 5/21, 3/27, 5/5, 5/2
                    # Not Helping 4/4, 4/24, 4/28, 5/22, 5/1
                    # Remove is giving positive impact -7100
                    if converting_to_buy:
                        if "10:10 AM" in self.current_candle.date:
                            print("Put Break Point")
                        previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                        if previous_lowest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_lowest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15): #and previous_highest_rsi_candle.close > self.current_candle.close:
                                previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(previous_lowest_rsi_candle, self.track_all_candles, False)
                                if previous_highest_rsi_candle:
                                    find_previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(previous_highest_rsi_candle, self.track_all_candles, False)
                                    if find_previous_lowest_rsi_candle:
                                        time_difference = abs(previous_highest_rsi_candle.index - find_previous_lowest_rsi_candle.index)
                                        if time_difference < timedelta(minutes=15):
                                            if find_previous_lowest_rsi_candle.high < self.current_candle.low and not (self.current_candle.close > previous_highest_rsi_candle.close and self.current_candle.rsi > 94 and self.current_candle.rsi_13 > 55):
                                                if self.current_candle.rsi > find_previous_lowest_rsi_candle.rsi and (self.current_candle.rsi_13 < find_previous_lowest_rsi_candle.rsi_13 or self.current_candle.stoch_k < find_previous_lowest_rsi_candle.stoch_k):
                                                    converting_to_buy = False
                                                    self.buy_divergence_candle = None
                                                    if end_candle:
                                                        end_candle.divergence_used = False
                                                        self.update_divergence_used_in_memory_to_false(end_candle)
                                                    self.add_helper_messages(f"Buy <b>Cancelled</b> Due to Divergence Five,  Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")
                                                    conditons_reason = f"Buy <b>Cancelled</b> Due to Divergence Five,  Candle used Start # {find_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} "
                                                    self.log_condition("Buy Cancelled Due to Divergence Five", conditons_reason, self.current_candle.index )


                    # This Condition is helping on chart
                    # Helping 4/10, 4/14, 5/8, 4/11, 3/31, 5/20, 3/28, 5/13
                    # Not Helping 4/24, 4/15, 3/27, 4/28, 5/22, 5/6, 5/1
                    # Remove is giving positive impact -9400
                    if converting_to_buy and self.current_candle.body > 0:
                        # Fix 4/10 Chart at 10:10 AM
                        previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                        if previous_lowest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_lowest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15): #and previous_highest_rsi_candle.close > self.current_candle.close:
                                previous_highest_rsi_candle = self.find_previous_highest_rsi_candle_latest(previous_lowest_rsi_candle, self.track_all_candles, False)
                                if previous_highest_rsi_candle and self.current_candle.rsi < previous_highest_rsi_candle.rsi and self.current_candle.stoch_k > previous_highest_rsi_candle.stoch_k:
                                    if self.current_candle.low < previous_highest_rsi_candle.low < self.current_candle.high:
                                        continue_with_cancel = True
                                        if "10:23 AM" in self.current_candle.date:
                                            print("Put Break Point")
                                        if start_candle and end_candle:
                                            if start_candle.rsi_13 < 45 and end_candle.rsi_13 < 45 and  start_candle.stoch_k < 20 and end_candle.stoch_k < 20:
                                                continue_with_cancel = False

                                        # Fix 3/27 , 3:07 PM
                                        if continue_with_cancel:
                                            converting_to_buy = False
                                            self.buy_divergence_candle = None
                                            if self.current_candle.close > previous_highest_rsi_candle.close and not self.in_trade_candle.buy_divergence_six_cancel_candle_index:
                                                self.in_trade_candle.buy_divergence_six_cancel_candle_index = self.current_candle.index
                                            if end_candle:
                                                end_candle.divergence_used = False
                                                self.update_divergence_used_in_memory_to_false(end_candle)
                                            self.add_helper_messages(f"Buy <b>Cancelled</b> Due to Divergence Six, Between RSI & K  Candle used Start # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")
                                            conditons_reason = f"Buy <b>Cancelled</b> Due to Divergence Six ,  Candle used Start # {previous_highest_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} "
                                            self.log_condition("Buy Cancelled Due to Divergence Six", conditons_reason, self.current_candle.index )



                    # This Condition is helping on chart
                    # Helping 4/23, 5/8, 4/8, 4/14, 5/20, 4/24
                    # Not Helping 5/9, 5/12, 3/28, 5/2, 5/1, 4/22, 4/16, 5/19
                    # Remove is giving positive impact -4225
                    if not converting_to_buy and self.current_candle.body > 0:
                        if "10:03 AM" in self.current_candle.date:
                            print("Put Break Point")

                        buy_divergence_info = self.get_divergence_info(self.current_candle.index, "BUY")
                        if not buy_divergence_info:
                            previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                            if previous_lowest_rsi_candle:
                                if previous_lowest_rsi_candle.rsi < 5 and previous_lowest_rsi_candle.rsi_13 < 45 and previous_lowest_rsi_candle.stoch_k < 20 and previous_lowest_rsi_candle.stoch_d < 20:
                                    find_previous_highest_rsi = self.find_previous_highest_rsi_candle_latest(previous_lowest_rsi_candle, self.track_all_candles, False)
                                    if find_previous_highest_rsi:
                                        if self.current_candle.rsi > find_previous_highest_rsi.rsi and self.current_candle.rsi_13 > find_previous_highest_rsi.rsi_13:
                                            continue_to_buy = True
                                            # Fix 4/10 chart @ 12:25
                                            find_previous_previous_highest_rsi = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, True)
                                            if find_previous_previous_highest_rsi and self.current_candle.rsi_13 < 45:
                                                find_previous_lowest_rsi = self.find_previous_lowest_rsi_candle_latest(find_previous_previous_highest_rsi, self.track_all_candles, True)
                                                if find_previous_lowest_rsi and self.current_candle.rsi > find_previous_lowest_rsi.rsi and self.current_candle.rsi_13 < find_previous_lowest_rsi.rsi_13:
                                                    continue_to_buy = False
                                                    self.add_helper_messages(f"Script Five Fix, Cancel Three Buy current rsi higher then previous higher rsi,  Candle used Start # {find_previous_lowest_rsi.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")
                                                    conditons_reason = f"Three Buy current rsi higher then previous higher rsi,  Candle used Start # {find_previous_lowest_rsi.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}"
                                                    self.log_condition("Script Five Fix, Cancel Three Buy current rsi higher then previous higher rsi", conditons_reason, self.current_candle.index )

                                            if continue_to_buy:
                                                converting_to_buy = True
                                                self.add_helper_messages(f"Script Five, Three Buy current rsi higher then previous higher rsi,  Candle used Start # {find_previous_highest_rsi.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")
                                                conditons_reason = f"Three Buy current rsi higher then previous higher rsi,  Candle used Start # {find_previous_highest_rsi.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}"
                                                self.log_condition("Script Five, Three Buy current rsi higher then previous higher rsi", conditons_reason, self.current_candle.index )

                    if converting_to_buy and (self.current_candle.body < 0 or (self.current_candle.open == self.current_candle.close)) :
                        converting_to_buy = False
                        self.buy_divergence_candle = None
                        self.add_helper_messages(f"Buy <b>Cancelled</b>  Because Current Candle is Red")
                        # if end_candle:
                        #     end_candle.divergence_used = False
                        #     self.update_divergence_used_in_memory_to_false(end_candle)


                    # This Condition is helping on chart
                    # Helping 4/25, 5/1, 4/21, 5/15, 4/16, 5/12, 4/17, 5/9, 5/21, 4/10, 5/7, 5/6, 5/19, 5/13, 4/22, 4/30
                    # Not Helping 4/23, 4/28, 5/14, 4/15, 5/5, 5/20, 5/16. 4/14, 4/24, 5/8, 5/2, 4/29
                    # Remove is giving positive impact -5812
                    if converting_to_buy and self.current_candle.rsi_13 < 47:
                        if "10:15 AM" in self.current_candle.date:
                            print("Put Break Point")
                        high_rsi_candle = self.find_previous_highest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                        if high_rsi_candle and self.current_candle.open < high_rsi_candle.low and self.current_candle.low < high_rsi_candle.low < self.current_candle.high:
                            time_difference = abs(self.current_candle.index - high_rsi_candle.index)
                            if time_difference < timedelta(minutes=15): #and previous_highest_rsi_candle.close > self.current_candle.close:
                                condition_one = self.current_candle.rsi_13 > high_rsi_candle.rsi_13
                                condition_two =  self.current_candle.stoch_k >= high_rsi_candle.stoch_k
                                condition_three =  self.current_candle.stoch_d >= high_rsi_candle.stoch_d
                                condition_four =  self.current_candle.close < high_rsi_candle.close
                                match_count = sum([condition_one, condition_two, condition_three, condition_four])
                                if  match_count >= 1 and match_count <=3:
                                    converting_to_buy = False
                                    self.buy_divergence_candle = None
                                    if end_candle:
                                        end_candle.divergence_used = False
                                        self.update_divergence_used_in_memory_to_false(end_candle)
                                    self.add_helper_messages(f"Script Five Fix - RSI, Buy cancelled RSI & RSI_13, K & D Divergence,  Candle used Start # {high_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")
                                    conditons_reason = f"Script Five Fix - RSI, Buy cancelled RSI & RSI_13, K & D Divergence,  Candle used Start # {high_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}"
                                    self.log_condition("Script Five Fix - One, Buy cancelled RSI & RSI_13, K & D Divergence", conditons_reason, self.current_candle.index )


                    # This Condition is helping on chart
                    # Helping 4/10, 5/8, 4/21
                    # Not Helping 5/1, 4/30, 5/2, 5/14, 4/14,
                    # Remove is giving positive impact -6475
                    if converting_to_buy and self.current_candle.rsi_13 < 47:
                        if "10:15 AM" in self.current_candle.date:
                            print("Put Break Point")

                        high_stoch_d_candle = self.find_previous_highest_stoch_d_candle_latest(self.current_candle, self.track_all_candles, False)
                        if high_stoch_d_candle and self.current_candle.open < high_stoch_d_candle.low and self.current_candle.low < high_stoch_d_candle.low < self.current_candle.high:
                            time_difference = abs(self.current_candle.index - high_stoch_d_candle.index)
                            if time_difference < timedelta(minutes=15): #and previous_highest_rsi_candle.close > self.current_candle.close:
                                condition_one = self.current_candle.rsi_13 > high_stoch_d_candle.rsi_13
                                condition_two =  self.current_candle.stoch_k >= high_stoch_d_candle.stoch_k
                                condition_three =  self.current_candle.stoch_d >= high_stoch_d_candle.stoch_d
                                condition_four =  self.current_candle.close < high_rsi_candle.close
                                match_count = sum([condition_one, condition_two, condition_three, condition_four])
                                if  match_count >= 1 and match_count <=3:
                                    converting_to_buy = False
                                    self.buy_divergence_candle = None
                                    if end_candle:
                                        end_candle.divergence_used = False
                                        self.update_divergence_used_in_memory_to_false(end_candle)
                                    self.add_helper_messages(f"Script Five Fix - STOCH_D, Buy cancelled RSI & RSI_13, K & D Divergence,  Candle used Start # {high_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")
                                    conditons_reason = f"Script Five Fix - STOCH_D, Buy cancelled RSI & RSI_13, K & D Divergence,  Candle used Start # {high_rsi_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}"
                                    self.log_condition("Script Five Fix - Two, Buy cancelled RSI & RSI_13, K & D Divergence", conditons_reason, self.current_candle.index )


                    # This Condition is helping on chart
                    # Helping 5/8, 4/3, 4/2, 4/11, 5/2, 5/21, 4/1, 4/28, 5/14, 5/20, 4/29
                    # Not Helping 4/7, 4/8, 4/23, 4/24, 4/14, 3/31, 5/5, 5/9, 5/1, 4/15, 3/28, 5/6, 3/27, 4/21, 4/17, 5/19, 5/13
                    # 4/7 @ 2:16 PM
                    # Remove is giving positive impact -1600

                    if converting_to_buy and self.current_candle.body > 0 :
                        if "11:45 AM" in self.current_candle.date:
                            print("Put Break Point")
                        buy_divergence_info = self.get_divergence_info(self.current_candle.index, "BUY")
                        previous_highest_rsi_13_candle = self.find_previous_highest_rsi_13_candle_latest(self.current_candle, self.track_all_candles)
                        if previous_highest_rsi_13_candle and (not buy_divergence_info or (buy_divergence_info and buy_divergence_info.start_candle.rsi < 5 and buy_divergence_info.end_candle.rsi < 5)):
                            time_difference = abs(self.current_candle.index - previous_highest_rsi_13_candle.index)
                            if time_difference < timedelta(minutes=30) :
                                if self.current_candle.rsi >  previous_highest_rsi_13_candle.rsi and self.current_candle.close < previous_highest_rsi_13_candle.close and self.current_candle.high < previous_highest_rsi_13_candle.high and self.current_candle.high < previous_highest_rsi_13_candle.close:
                                    if self.current_candle.low < previous_highest_rsi_13_candle.low and (self.current_candle.stoch_k < previous_highest_rsi_13_candle.stoch_k or self.current_candle.stoch_d < previous_highest_rsi_13_candle.stoch_d):
                                        continue_to_cancel = True
                                        previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_extreme(self.current_candle, self.track_all_candles)
                                        if previous_lowest_rsi_candle :
                                            time_difference = abs(self.current_candle.index - previous_lowest_rsi_candle.index)
                                            if  time_difference < timedelta(minutes=10) and previous_lowest_rsi_candle.rsi < 5 and previous_lowest_rsi_candle.stoch_k < 20 and previous_lowest_rsi_candle.stoch_d < 20 and self.current_candle.close > previous_lowest_rsi_candle.high:
                                                continue_to_cancel = False
                                        if continue_to_cancel:
                                            converting_to_buy = False
                                            self.add_helper_messages(f"Script Seven,Buy cancel  the price is going down RSI & RSI_13 Divergence ,Candle used Start # {previous_highest_rsi_13_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}")
                                            conditons_reason = f"Script Seven,Buy cancel  the price is going down,Candle used Start # {previous_highest_rsi_13_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')}"
                                            self.log_condition("Script Seven,Buy cancel  the price is going down", conditons_reason, self.current_candle.index )
                                            if end_candle:
                                                end_candle.divergence_used = False
                                                self.update_divergence_used_in_memory_to_false(end_candle)


                    # This Condition is helping on chart
                    # Helping 5/8, 3/27, 5/13
                    # Not Helping
                    # Remove is giving positive impact -2075
                    if not converting_to_buy and self.current_candle.body > 0 and self.current_candle.previous_body > 0 and self.in_trade_candle.buy_divergence_six_cancel_candle_index:
                        buy_divergence_six_cancel_candle = self.get_candle_by_index(self.in_trade_candle.buy_divergence_six_cancel_candle_index)
                        if buy_divergence_six_cancel_candle and self.current_candle.close > buy_divergence_six_cancel_candle.close:
                            converting_to_buy = True
                            self.buy_divergence_candle = buy_divergence_six_cancel_candle
                            self.add_helper_messages(f"Buy Due to Previous Divergence Six Cancel,  Candle used Start # {buy_divergence_six_cancel_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")
                            conditons_reason = f"Buy Due to Previous Divergence Six Cancel,  Candle used Start # {buy_divergence_six_cancel_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} "
                            self.log_condition("Buy Due to Previous Divergence Six Cancel", conditons_reason, self.current_candle.index )


                    # This Condition is helping on chart
                    # Helping 5/8, 4/22, 4/11, 4/2, 4/3, 4/10, 4/28, 4/24, 5/5, 5/9, 4/29 , 5/20
                    # Not Helping 4/4, 4/15, 4/17, 4/16, 5/21, 5/19, 4/30, 3/31, 5/15, 5/12, 5/22, 5/13, 4/1
                    # Remove is giving positive impact 2300
                    if not converting_to_buy and self.current_candle.body > 0 and self.current_candle.previous_body > 0 and self.in_trade_candle.buy_divergence_one_cancel_candle_index:
                        if "10:55 AM" in self.current_candle.date:
                            print("Put Break Point")

                        buy_divergence_one_cancel_candle = self.get_candle_by_index(self.in_trade_candle.buy_divergence_one_cancel_candle_index)
                        if buy_divergence_one_cancel_candle and (self.current_candle.close > buy_divergence_one_cancel_candle.close
                                                                 and self.current_candle.rsi > buy_divergence_one_cancel_candle.rsi
                                                                 and self.current_candle.rsi_13 > buy_divergence_one_cancel_candle.rsi_13
                                                                 and self.current_candle.stoch_k > buy_divergence_one_cancel_candle.stoch_k) :
                            converting_to_buy = True
                            self.buy_divergence_candle = buy_divergence_one_cancel_candle
                            self.add_helper_messages(f"Buy Due to Previous Divergence One Cancel,  Candle used Start # {buy_divergence_one_cancel_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} ")
                            conditons_reason = f"Buy Due to Previous Divergence One Cancel,  Candle used Start # {buy_divergence_one_cancel_candle.index.strftime('%I:%M %p')}, End # {self.current_candle.index.strftime('%I:%M %p')} "
                            self.log_condition("Script Five, Buy Due to Previous Divergence One Cancel", conditons_reason, self.current_candle.index )



                    if not converting_to_buy and self.current_candle.body > 0 and not cancel_buy:
                        if "10:23 AM" in self.current_candle.date:
                            print("Put Break Point")
                        previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(self.current_candle, self.track_all_candles, False)
                        if previous_lowest_rsi_candle:
                            time_difference = abs(self.current_candle.index - previous_lowest_rsi_candle.index)
                            if time_difference < timedelta(minutes=15): #and previous_highest_rsi_candle.close > self.current_candle.close:
                                find_previous_previous_lowest_rsi_candle = self.find_previous_lowest_rsi_candle_latest(previous_lowest_rsi_candle, self.track_all_candles, False)
                                if find_previous_previous_lowest_rsi_candle:
                                    time_difference = abs(previous_lowest_rsi_candle.index - find_previous_previous_lowest_rsi_candle.index)
                                    if time_difference < timedelta(minutes=15):
                                        find_low_red_candle = self.find_previous_lowest_price_rsi_candle_new(find_previous_previous_lowest_rsi_candle.index, previous_lowest_rsi_candle.index,  self.track_all_candles)
                                        found_low_red_candle = False
                                        if find_low_red_candle and find_low_red_candle.close < find_previous_previous_lowest_rsi_candle.close:
                                            found_low_red_candle = True

                                        if not find_low_red_candle and previous_lowest_rsi_candle.close < find_previous_previous_lowest_rsi_candle.close and previous_lowest_rsi_candle.rsi > find_previous_previous_lowest_rsi_candle.rsi and previous_lowest_rsi_candle.rsi_13 < find_previous_previous_lowest_rsi_candle.rsi_13:
                                            if self.current_candle.close > previous_lowest_rsi_candle.high:
                                                converting_to_buy = True
                                                self.buy_divergence_candle = previous_lowest_rsi_candle
                                                self.add_helper_messages(f"Script Six, Buy Due to RSI & RSI_13 Divergence ,  Candle used Start # {find_previous_previous_lowest_rsi_candle.index.strftime('%I:%M %p')}, End # {previous_lowest_rsi_candle.index.strftime('%I:%M %p')}")


                    if converting_to_buy:
                        cover_condition = True
                        short_condition = False
                        stop_loss = self.get_stop_loss(True)
                        buy_condition = True
                        self.update_converting_to_buy(start_candle, end_candle)


                    self.track_all_candles_during_short.append(current_candle)


            for i in range(0, 2):
                ############## BUY ORDER ##################
                if not self.in_trade and buy_condition:
                    # try:
                    #stop_limit_price = self.current_candle.low - 4
                    stop_limit_price = stop_loss - self.stop_loss_adjust
                    if self.enable_trade_buying:
                        self.buy(sl=stop_limit_price, size=self.lot_size)
                    self.buy_order = True
                    self.in_trade = True
                    self.in_trade_candle = current_candle
                # except:
                #     print("Skipping Buy Order Due To Exception")

                ############## SHORT ORDER ##################
                if not self.in_trade and short_condition:
                    try:
                        #stop_limit_price = self.current_candle.high + 4
                        stop_limit_price = stop_loss + self.stop_loss_adjust
                        if self.enable_trade_shorting:
                            self.sell(sl=stop_limit_price,  size=self.lot_size)
                        self.short_order = True
                        self.in_trade = True
                        self.in_trade_candle = current_candle
                    except:
                        print("Date # {self.data.DATE[-1]} : Skipping Short Order Due to Exception")

                ##############  HIGH BUY CLOSE ##################
                if not self.close_only_once  and self.buy_order:
                    if sell_condition:
                        try:
                            if self.enable_trade_buying and len(self.trades) > 0:
                                self.position.close()
                            self.buy_order = False
                            self.in_trade = False
                            self.close_only_once = True
                        except Exception as e:
                            print("Date # {self.data.DATE[-1]} : Skipping Buy Order Close Due To Exception", e)

                ############## SHORT ORDER CLOSE ##################
                if not self.close_only_once and  self.short_order:
                    if cover_condition:
                        try:
                            if self.enable_trade_shorting and len(self.trades) > 0:
                                self.position.close()
                            self.short_order = False
                            self.in_trade = False
                            self.close_only_once = True
                        except Exception as e:
                            print("Date # {self.data.DATE[-1]} : Skipping Short Order Close Due To Exception", e)

def calculate_swing_volume(df, swing_collection, label):
    """
    Calculate total volume for a swing, ignoring doji candles (where Open == Close).
    Excludes start_index from volume calculation.
    """
    df[label] = 0  # Initialize new column

    for swing in swing_collection:
        start_idx, end_idx = swing.start_index, swing.end_index

        # Ensure we get the correct index positions
        if start_idx in df.index and end_idx in df.index:
            start_pos = df.index.get_loc(start_idx)  # Get position of start index
            end_pos = df.index.get_loc(end_idx)  # Get position of end index

            if start_pos + 1 <= end_pos:  # Ensure valid range
                swing_df = df.iloc[start_pos + 1:end_pos + 1]  # Exclude start_index

                # Ignore doji candles (where Open == Close)
                valid_swing_df = swing_df[swing_df['Open'] != swing_df['Close']]

                # Sum the volume of valid candles
                swing_volume = valid_swing_df['Volume'].sum()

                # Store volume at the end_index
                df.at[end_idx, label] = swing_volume

def calculate_adjusted_swing_volume(df, swing_collection, label):
    """
    Calculate swing volume while subtracting opposite candle volume.
    - For upward swing: Subtract red candle volume from total.
    - For downward swing: Subtract green candle volume from total.
    Excludes start_index from volume calculation.
    """
    df[label] = 0  # Initialize new column

    for swing in swing_collection:
        start_idx, end_idx = swing.start_index, swing.end_index

        # Ensure we get the correct index positions
        if start_idx in df.index and end_idx in df.index:
            start_pos = df.index.get_loc(start_idx)  # Get position of start index
            end_pos = df.index.get_loc(end_idx)  # Get position of end index

            if start_pos + 1 <= end_pos:  # Ensure valid range
                swing_df = df.iloc[start_pos + 1:end_pos + 1]  # Exclude start_index

                # Ignore doji candles (where Open == Close)
                valid_swing_df = swing_df[swing_df['Open'] != swing_df['Close']]

                # Calculate adjusted volume based on swing type
                green_volume = valid_swing_df[valid_swing_df['Close'] > valid_swing_df['Open']]['Volume'].sum()
                red_volume = valid_swing_df[valid_swing_df['Close'] < valid_swing_df['Open']]['Volume'].sum()

                adjusted_volume = (green_volume - red_volume) if swing.swing_type == 1 else (red_volume - green_volume)

                # Store adjusted volume at the end_index
                df.at[end_idx, label] = abs(adjusted_volume)

def calculate_adjusted_swing_body_volume(df, swing_collection, label):
    """
    Calculate swing volume while subtracting opposite candle volume.
    - For upward swing: Subtract red candle volume from total.
    - For downward swing: Subtract green candle volume from total.
    Excludes start_index from volume calculation.
    """
    df[label] = 0  # Initialize new column

    for swing in swing_collection:
        start_idx, end_idx = swing.start_index, swing.end_index

        # Ensure we get the correct index positions
        if start_idx in df.index and end_idx in df.index:
            start_pos = df.index.get_loc(start_idx)  # Get position of start index
            end_pos = df.index.get_loc(end_idx)  # Get position of end index

            if start_pos + 1 <= end_pos:  # Ensure valid range
                swing_df = df.iloc[start_pos + 1:end_pos + 1]  # Exclude start_index

                # Ignore doji candles (where Open == Close)
                valid_swing_df = swing_df[swing_df['Open'] != swing_df['Close']]

                # Calculate adjusted volume based on swing type
                green_volume = valid_swing_df[valid_swing_df['Close'] > valid_swing_df['Open']]['BODY_VOLUME'].sum()
                red_volume = valid_swing_df[valid_swing_df['Close'] < valid_swing_df['Open']]['BODY_VOLUME'].sum()

                adjusted_volume = (green_volume - red_volume) if swing.swing_type == 1 else (red_volume - green_volume)

                # Store adjusted volume at the end_index
                df.at[end_idx, label] = abs(adjusted_volume)

def process_swings(df, swing_yellow_collection, swing_blue_collection):

    calculate_swing_volume(df, swing_yellow_collection, "Yellow_Swing_Volume")
    calculate_swing_volume(df, swing_blue_collection, "Blue_Swing_Volume")

    calculate_adjusted_swing_volume(df, swing_yellow_collection, "Yellow_Average_Swing_Volume")
    calculate_adjusted_swing_body_volume(df, swing_yellow_collection, "Yellow_Body_Average_Swing_Volume")
    calculate_adjusted_swing_volume(df, swing_blue_collection, "Blue_Average_Swing_Volume")

    return df  # Return modified DataFrame

def remove_last_candle_if_invalid(df, timeframe_seconds=60):
    if len(df) < 2:
        return df  # Return as is if there are not enough candles

    last_timestamp = df.index[-1]  # This is likely timezone-aware
    current_time = datetime.now()  # This is timezone-naive

    # Ensure current_time is converted to the same timezone as last_timestamp
    if last_timestamp.tzinfo is not None:
        current_time = current_time.astimezone(last_timestamp.tzinfo)


    # Check if the latest candle is not closed by verifying if the system time has exceeded its expected closing time
    if (current_time - last_timestamp).total_seconds() < timeframe_seconds:
        df = df.iloc[:-1]  # Remove the last row

    return df


def seconds_until_next_run(offset_seconds: int = 10) -> int:
    """Return seconds until next (minute boundary + offset_seconds)."""
    now = datetime.now()

    # next minute at :00
    next_minute = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)

    # add 10-second offset
    target_time = next_minute + timedelta(seconds=offset_seconds)

    return int((target_time - now).total_seconds())

def inject_zoom_persistence(html_file, plot_id):
    """
    Injects JavaScript code for zoom state saving/restoring and adds auto-refresh to a Bokeh HTML file.

    Parameters:
        html_file (str): Path to the Bokeh-generated HTML file.
        plot_id (str): The ID of the Bokeh plot to target for zoom persistence.
    """
    # JavaScript code for zoom persistence
    script = f"""
    <script>
        function saveZoomState() {{
            const allModels = Bokeh.documents[0]._all_models;
            const plot = allModels.get("{plot_id}");
            if (!plot) return;

            const {{ x_range, y_range }} = plot;

            if (!x_range || !y_range || x_range.start === undefined || y_range.start === undefined) return;

            const zoomState = {{
                xStart: x_range.start,
                xEnd: x_range.end,
                yStart: y_range.start,
                yEnd: y_range.end,
            }};
            localStorage.setItem("zoomState", JSON.stringify(zoomState));
        }}

        function restoreZoomState() {{
            const zoomState = JSON.parse(localStorage.getItem("zoomState"));
            if (!zoomState) return;

            function tryRestore() {{
                const plot = Bokeh.documents[0]?._all_models.get("{plot_id}");
                if (plot) {{
                    const {{ x_range, y_range }} = plot;
                    if (x_range && y_range) {{
                        x_range.start = zoomState.xStart;
                        x_range.end = zoomState.xEnd;
                        y_range.start = zoomState.yStart;
                        y_range.end = zoomState.yEnd;
                    }}
                }} else {{
                    setTimeout(tryRestore, 100);
                }}
            }}

            tryRestore();
        }}

        window.addEventListener("beforeunload", saveZoomState);
        document.addEventListener("DOMContentLoaded", restoreZoomState);
        setInterval(saveZoomState, 10000);
    </script>
    """

    # Meta tag for refreshing the page every 60 seconds
    refresh_meta_tag = '<meta http-equiv="refresh" content="15">'

    try:
        # Read the HTML content
        with open(html_file, "r", encoding="utf-8") as file:
            content = file.read()

        # Inject the meta tag after the opening <head> tag
        if "<head>" in content:
            content = content.replace("<head>", f"<head>\n    {refresh_meta_tag}")
        else:
            raise ValueError("The HTML file does not contain a <head> tag.")

        # Inject the zoom persistence script before the closing </body> tag
        if "</body>" in content:
            content = content.replace("</body>", script + "</body>")
        else:
            raise ValueError("The HTML file does not contain a closing </body> tag.")

        # Write the modified content back to the file
        with open(html_file, "w", encoding="utf-8") as file:
            file.write(content)

        print(f"Zoom persistence script and auto-refresh successfully injected into '{html_file}'.")
    except Exception as e:
        print(f"An error occurred while injecting the script and meta tag: {e}")

def get_frequency_settings(interval):
    """
    Determines the correct API frequency settings and resampling needs.

    :param interval: Time interval (e.g., '1m', '15m', '1h')
    :return: Tuple (frequencyType, frequency, resample_interval)
    """
    interval_map = {
        "1d": ("daily", "1", None),
        "1m": ("minute", "1", None),
        "5m": ("minute", "5", None),
        "10m": ("minute", "10", None),
        "15m": ("minute", "15", None),
        "20m": ("minute", "10", "20T"),
        "30m": ("minute", "30", None),
        "45m": ("minute", "15", "45T"),
        "75m": ("minute", "15", "75T"),
        "90m": ("minute", "30", "90T"),
        "1h": ("minute", "30", "1h"),
        "2h": ("minute", "30", "2h"),
        "3h": ("minute", "30", "3h"),
        "4h": ("minute", "30", "4h")
    }

    return interval_map.get(interval, ("minute", "1", None))  # Default to 1m if not found


if __name__ == "__main__":
    if len(sys.argv) < 10:
        print("Usage: python backtest.py <symbol> <start_date> <end_date> <start_time> <end_time> <lot_size> <stop_loss_adjust> <output_html> <interval>")
        sys.exit(1)

    # Read arguments from the command line
    symbol = sys.argv[1]
    start_date = sys.argv[2]
    end_date = sys.argv[3]
    start_time = sys.argv[4]
    end_time = sys.argv[5]
    lot_size = int(sys.argv[6])
    stop_loss_adjust = float(sys.argv[7])
    output_html = sys.argv[8]
    interval = sys.argv[9]

    # symbol = '/ES'
    # start_date = '2025-11-11'
    # end_date = '2025-11-11'
    # start_time = '18:00'
    # end_time = '23:59'
    # lot_size = 50
    # stop_loss_adjust = 200
    # output_html ='sample.html'
    # interval = '1m'

    print("Starting BackTesting")
    api_key = 'REDACTED__see_legacy_REDACTIONS_md'
    app_secret = 'REDACTED__see_legacy_REDACTIONS_md'
    callback_url = 'https://127.0.0.1:8182'
    helper = MarketDataHelper(api_key, app_secret, callback_url)
    frequencyType, frequency, resample_interval = get_frequency_settings(interval)
    df = helper.fetch_price_history_for_backtesting(symbol, start_date, frequencyType, frequency, True, end_date)

    #  Futher Filter based on selected time.

    cst = pytz.timezone("America/Chicago")  # CST corresponds to America/Chicago

    # Convert start and end times to datetime (initially naive)
    start_time_dt = pd.to_datetime(start_date + " " + start_time, format="%Y-%m-%d %H:%M")
    end_time_dt = pd.to_datetime(start_date + " " + end_time, format="%Y-%m-%d %H:%M")

    # Adjust start time to 1 hour before
    adjusted_start_time_dt = start_time_dt - pd.Timedelta(hours=8)

    # Ensure df.index is datetime and correctly adjusted for CST
    df.index = pd.to_datetime(df.index)  # Convert to datetime if needed

    # Check if df.index is already timezone-aware
    if df.index.tz is None:
        df.index = df.index.tz_localize("America/Chicago")  # Localize if tz-naive
    else:
        df.index = df.index.tz_convert("America/Chicago")  # Convert if already tz-aware

    # Convert start times to CST if they are naive
    adjusted_start_time_dt = cst.localize(adjusted_start_time_dt) if adjusted_start_time_dt.tzinfo is None else adjusted_start_time_dt
    start_time_dt = cst.localize(start_time_dt) if start_time_dt.tzinfo is None else start_time_dt
    end_time_dt = cst.localize(end_time_dt) if end_time_dt.tzinfo is None else end_time_dt

    # Get min/max timestamps in df
    df_min_time = df.index.min()
    df_max_time = df.index.max()

    # Ensure adjusted start time does not go below available data
    final_start_time = max(adjusted_start_time_dt, df_min_time)
    final_end_time = min(end_time_dt, df_max_time)

    # Filter DataFrame using index
    df = df.loc[(df.index >= final_start_time) & (df.index <= final_end_time)]

    if resample_interval:
        df = df.resample(resample_interval).agg({
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum"
        })
    df = remove_last_candle_if_invalid(df)
    initial_df = df.copy()
    initial_df.index = pd.to_datetime(initial_df.index)
    #initial_df.index = initial_df.index.tz_localize(None)
    initial_df["RSI"] = talib.RSI(initial_df['Close'], 2)
    initial_df["RSI"] = initial_df["RSI"].round(2)
    print(f"Data shape before apply # {df.shape}")
    df = apply_rsi_stoch_doji(df)
    highest_price_index = df['High'].idxmax()
    lowest_price_index = df['Low'].idxmin()
    stop_loss_high = df['High'].max()
    stop_loss_low = df['Low'].min()
    first_index = df.index[0]
    generate_fibonacci_sequence(df, first_index, False, True)
    last_index = df.index[-1]
    df["KAMA"] = 0
    df["VWAP"] = 0
    enable_trade_buying = True
    enable_trade_shorting = True

    bt = Backtest(df, RSIStochExtremeStrategy, cash=10_00000, commission=.00, exclusive_orders=False)
    stats = bt.run()
    # Convert each timestamp's divergences into a formatted string
    divergence_series = pd.Series({
        ts: "<br>".join([
            f"<b>Trade Type:</b> {div.trade_type} | <b>Extreme:</b> {div.is_extreme} | <b>Pre-Condition:</b> {div.is_pre_condition} | <b>RSI 13:</b> {div.is_rsi_13}<br>"
            f"<b>Start Date:</b> {div.start_candle.date} | <b>End Date:</b> {div.end_candle.date}<br>"
            # Conditionally include RSI 13 if is_rsi_13 is True, otherwise use RSI
            f"<b>Start RSI:</b> {div.start_candle.rsi_13 if div.is_rsi_13 else div.start_candle.rsi} | "
            f"<b>End RSI:</b> {div.end_candle.rsi_13 if div.is_rsi_13 else div.end_candle.rsi}<br>"
            # Conditionally add Stochastic values only if `is_extreme` is False
            + (f"<b>Start Stoch K:</b> {div.start_candle.stoch_k} | <b>End Stoch K:</b> {div.end_candle.stoch_k}<br>"
               f"<b>Start Stoch D:</b> {div.start_candle.stoch_d} | <b>End Stoch D:</b> {div.end_candle.stoch_d}<br>"
               if not div.is_extreme else "")
            for div in divergences  # Multiple divergences at the same timestamp
        ])
        for ts, divergences in updated_divergences.items()
    })
    # Update `df` with properly formatted HTML tooltips
    df['DivergenceInfo'] = df.index.map(divergence_series).fillna("")

    # Ensure Bokeh uses the formatted divergence info
    bt._data['DivergenceInfo'] = df['DivergenceInfo']


    # Convert `buying_shorting_conditions` into a pandas Series
    buying_shorting_series = pd.Series(buying_shorting_conditions)

    # Ensure all indexes match and fill missing values with a default string
    df['BuySellConditions'] = df.index.map(buying_shorting_series).fillna("")

    # Format the `BuySellConditions` column for better readability
    def format_conditions(value):
        if isinstance(value, list):
            # Join list elements into a string separated by HTML line breaks
            return "<br>".join(value)
        elif isinstance(value, str) and len(value) > 50:  # If a single message is long
            # Break long strings into lines of up to 50 characters using <br>
            return "<br>".join(value[i:i + 50] for i in range(0, len(value), 50))
        return value

    # Apply formatting to the 'BuySellConditions' column
    df['BuySellConditions'] = df['BuySellConditions'].apply(format_conditions)

    # Update the `bt._data` dictionary
    bt._data['BuySellConditions'] = df['BuySellConditions']

    # Separate dictionaries for upward and downward swings

    df = process_swings(df, swing_yellow_collection, swing_blue_collection)

    bt._data["Yellow_Swing_Volume"] = df["Yellow_Swing_Volume"]
    bt._data["Blue_Swing_Volume"] = df["Blue_Swing_Volume"]
    bt._data["Yellow_Average_Swing_Volume"] = df["Yellow_Average_Swing_Volume"]
    bt._data["Blue_Average_Swing_Volume"] = df["Blue_Average_Swing_Volume"]
    bt._data["Yellow_Body_Average_Swing_Volume"] = df["Yellow_Body_Average_Swing_Volume"]
    bt.plot(filename=output_html, divergence_swing_collection=list(divergence_swing_collection.values()))
    inject_zoom_persistence(output_html, "p1002")
