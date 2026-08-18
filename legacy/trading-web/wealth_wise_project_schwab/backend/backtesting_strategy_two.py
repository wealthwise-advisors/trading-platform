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
last_index = None
start_time = None
end_time = None
lot_size = None
stop_loss_adjust = None
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
    df.index = df.index.tz_localize(None)
    df["RSI"] = talib.RSI(df['Close'], 2)
    df["ADX"] = talib.ADX(df['High'], df['Low'], df['Close'], 14)
    df["STOCH"], df["STOCH_D"] = talib.STOCHRSI(df["Close"], timeperiod=14, fastk_period=14, fastd_period=3)
    df["EMA5"] = talib.EMA(df['Close'], 5)
    df["EMA12"] = talib.EMA(df['Close'], 12)
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
    df["GREEN_WICK_UP"] = df.apply(get_green_wick_up, axis=1)
    df["GREEN_WICK_DOWN"] = df.apply(get_green_wick_down, axis=1)
    df["RED_WICK_UP"] = df.apply(get_red_wick_up, axis=1)
    df["RED_WICK_DOWN"] = df.apply(get_red_wick_down, axis=1)
    df["BODY_VOLUME"] = df.apply(get_body_volume, axis=1)
    df['BODY_VOLUME'] = pd.to_numeric(df['BODY_VOLUME'], errors='coerce')
    df["GREEN_WICK_UP_VOLUME"] = df.apply(get_green_wick_up_volume, axis=1)
    df["RED_WICK_UP_VOLUME"] = df.apply(get_red_wick_up_volume, axis=1)
    df["GREEN_WICK_DOWN_VOLUME"] = df.apply(get_green_wick_down_volume, axis=1)
    df["RED_WICK_DOWN_VOLUME"] = df.apply(get_red_wick_down_volume, axis=1)
    df["CLOSE_OPEN_OPEN"] = df.apply(get_HH_LL, axis=1)
    df["BODY_PERCENT"] = df.apply(apply_body_percentage, axis=1)
    df["CHART_TYPE"] = 0
    df['PREVIOUS_BODY'] = df['BODY'].shift(1)
    df['PREVIOUS_PREVIOUS_BODY'] = df['BODY'].shift(2)
    df['PREVIOUS_GREEN_WICK_UP'] = df['GREEN_WICK_UP'].shift(1)
    df['PREVIOUS_GREEN_WICK_DOWN'] = df['GREEN_WICK_DOWN'].shift(1)
    df['PREVIOUS_RED_WICK_UP'] = df['RED_WICK_UP'].shift(1)
    df['PREVIOUS_RED_WICK_DOWN'] = df['RED_WICK_DOWN'].shift(1)
    df['PREVIOUS_BODY_PERCENT'] = df['BODY_PERCENT'].shift(1)
    df['PREVIOUS_BODY_VOLUME'] = df['BODY_VOLUME'].shift(1)
    df['PREVIOUS_RSI'] = df['RSI'].shift(1)
    df['PREVIOUS_STOCH'] = df['STOCH'].shift(1)
    df['PREVIOUS_STOCH_D'] = df['STOCH_D'].shift(1)
    df['PREVIOUS_RANGE'] = df['RANGE'].shift(1)
    df['PREVIOUS_HIGH'] = df['High'].shift(1)
    df['PREVIOUS_LOW'] = df['Low'].shift(1)
    #df['GREEN_CLOSE'] = 0
    #df['RED_CLOSE'] = 0
    #df['Wave_Pattern'] = None
    df['previous_index'] = df.index.to_series().shift(1)

    df["EMA9"] = talib.EMA(df['Close'], 9)
    df["EMA21"] = talib.EMA(df['Close'], 21)

    df['previous_index'] = df.index.to_series().shift(1)


    # Calculate 20-period average volume
    df['avg_volume'] = df['Volume'].rolling(window=20).mean()

    # Identify unusual volume
    df['unusual'] = df['Volume'] > 2 * df['avg_volume']

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
        self.candles_above_94 = []
        self.candles_below_5 = []
        self.cover_stop_limit = None
        self.sell_stop_limit = None
        self.divergences_by_index = {}
        self.last_index = last_index

        self.lot_size = lot_size
        self.stop_loss_adjust = stop_loss_adjust

    def add_divergence_info(self, is_buy, pre_condition, post_condition, start_candle, end_candle, is_extreme, is_rsi_13, swing_used, pre_condition_only, only_rsi):


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

        # Add new divergence to divergences_by_index
        if new_divergence.index in self.divergences_by_index:
            self.divergences_by_index[new_divergence.index].append(new_divergence)
        else:
            self.divergences_by_index[new_divergence.index] = [new_divergence]

    def create_rsi_stoch_fib(self):
        data =  RsiStochFibNumber(self.data.Open[-1], self.data.Close[-1], self.data.High[-1], self.data.Low[-1], self.data.RSI[-1], self.data.STOCH[-1], self.data.STOCH_D[-1], self.data.Fib_Number[-1], self.data.DATE[-1], self.data.BODY[-1], 0, 0)
        data.volume = self.data.Volume[-1]
        data.previous_open = self.data.previous_open[-1]
        data.previous_close = self.data.previous_close[-1]
        data.previous_volume = self.data.previous_volume[-1]
        data.green_wick_up_percent = self.data.GREEN_WICK_UP[-1]
        data.green_wick_down_percent = self.data.GREEN_WICK_DOWN[-1]
        data.red_wick_up_percent = self.data.RED_WICK_UP[-1]
        data.red_wick_down_percent = self.data.RED_WICK_DOWN[-1]
        data.body_percent = self.data.BODY_PERCENT[-1]
        data.previous_green_wick_up_percent = self.data.PREVIOUS_GREEN_WICK_UP[-1]
        data.previous_green_wick_down_percent = self.data.PREVIOUS_GREEN_WICK_DOWN[-1]
        data.previous_red_wick_up_percent = self.data.PREVIOUS_RED_WICK_UP[-1]
        data.previous_red_wick_down_percent = self.data.PREVIOUS_RED_WICK_DOWN[-1]
        data.previous_body_percent = self.data.PREVIOUS_BODY_PERCENT[-1]
        data.body_volume = float(self.data.BODY_VOLUME[-1])
        data.previous_body_volume = float(self.data.PREVIOUS_BODY_VOLUME[-1])
        data.previous_body = self.data.PREVIOUS_BODY[-1]
        data.previous_rsi = self.data.PREVIOUS_RSI[-1]
        data.previous_stoch_k = self.data.PREVIOUS_STOCH[-1]
        data.previous_stoch_d = self.data.PREVIOUS_STOCH_D[-1]
        data.range = self.data.RANGE[-1]
        data.previous_range = self.data.PREVIOUS_RANGE[-1]
        data.previous_high = self.data.PREVIOUS_HIGH[-1]
        data.previous_low = self.data.PREVIOUS_LOW[-1]
        data.index = self.data.index[-1]
        return data

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
            if start_datetime <= candle.datetime <= end_datetime and candle.rsi < rsi_threshold and candle.low > low_threshold and candle.close > close_threshold
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
        filtered_candles = [candle for candle in self.track_all_candles if start_datetime <= candle.datetime <= end_datetime and candle.rsi > rsi_threshold and candle.high < high_threshold and candle.close < close_threshold and candle.body > 0]

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
                        print(f"Date # {current_candle.date} :Pre-Condition Bullish Internal Non-Extreme Divergence Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {closest_highest_rsi_candle.date} , Origin RSI {closest_highest_rsi_candle.rsi}, Origin STOCH_K  {closest_highest_rsi_candle.stoch_k},  Origin STOCH_D  {closest_highest_rsi_candle.stoch_d} , End Date {downward_swing_current.new_low_candle.date} , End RSI {downward_swing_current.new_low_candle.rsi}, End STOCH_K {downward_swing_current.new_low_candle.stoch_k}, End STOCH_D {downward_swing_current.new_low_candle.stoch_d}")
                        if current_candle.close > downward_swing_current.new_low_candle.high:
                            converting_to_buy = True
                    if converting_to_buy:
                        downward_swing_current.new_low_candle.divergence_used = True
                        self.update_divergence_used_in_memory(downward_swing_current.new_low_candle)
                        print(f"Date # {current_candle.date} :Bullish Internal Non-Extreme Divergence Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {closest_highest_rsi_candle.date} , Origin RSI {closest_highest_rsi_candle.rsi}, Origin STOCH_K  {closest_highest_rsi_candle.stoch_k},  Origin STOCH_D  {closest_highest_rsi_candle.stoch_d} , End Date {downward_swing_current.new_low_candle.date} , End RSI {downward_swing_current.new_low_candle.rsi}, End STOCH_K {downward_swing_current.new_low_candle.stoch_k}, End STOCH_D {downward_swing_current.new_low_candle.stoch_d}")
                        self.add_candles_buy_side = [candle for candle in self.track_all_candles_during_short if candle.datetime >= downward_swing_current.new_low_candle.datetime]
                    self.add_divergence_info(True, False, converting_to_buy, closest_highest_rsi_candle, downward_swing_current.new_low_candle, False , False, downward_swing_current, False, False )

        if closest_lowest_rsi_candle and closest_lowest_rsi_candle.body < 0 and downward_swing_current and not downward_swing_current.new_low_candle.divergence_used:
            time_diff = abs(closest_lowest_rsi_candle.datetime - downward_swing_current.new_low_candle.datetime)
            if downward_swing_current.new_low_candle.low < closest_lowest_rsi_candle.low and downward_swing_current.new_low_candle.close <= closest_lowest_rsi_candle.low and time_diff.total_seconds() < 30 * 60 and time_diff.total_seconds() > 2 * 60:
                if downward_swing_current.new_low_candle.rsi > closest_lowest_rsi_candle.rsi:
                    pre_condition_buy = True
                    print(f"Date # {current_candle.date} :Pre-Condition  Bullish Internal Non-Extreme Divergence Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {closest_lowest_rsi_candle.date} , Origin RSI {closest_lowest_rsi_candle.rsi}, End Date {downward_swing_current.new_low_candle.date} , End RSI {downward_swing_current.new_low_candle.rsi}")
                    if current_candle.close > downward_swing_current.new_low_candle.high:
                        converting_to_buy = True
                    if converting_to_buy:
                        downward_swing_current.new_low_candle.divergence_used = True
                        self.update_divergence_used_in_memory(downward_swing_current.new_low_candle)
                        print(f"Date # {current_candle.date} :Bullish Internal Non-Extreme Divergence Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {closest_lowest_rsi_candle.date} , Origin RSI {closest_lowest_rsi_candle.rsi}, End Date {downward_swing_current.new_low_candle.date} , End RSI {downward_swing_current.new_low_candle.rsi}")
                        self.add_candles_buy_side = [candle for candle in self.track_all_candles_during_short if candle.datetime >= downward_swing_current.new_low_candle.datetime]
                    self.add_divergence_info(True, False, converting_to_buy, closest_lowest_rsi_candle, downward_swing_current.new_low_candle, True , False, downward_swing_current, False, True )

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
                        print(f"Date # {current_candle.date} :Pre-Condition  Bearish Internal Non-Extreme Divergence Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {closest_lowest_rsi_candle.date} , Origin RSI {closest_lowest_rsi_candle.rsi}, Origin STOCH_K  {closest_lowest_rsi_candle.stoch_k},  Origin STOCH_D  {closest_lowest_rsi_candle.stoch_d} , End Date {upward_swing_current.new_high_candle.date} , End RSI {upward_swing_current.new_high_candle.rsi}, End STOCH_K {upward_swing_current.new_high_candle.stoch_k}, End STOCH_D {upward_swing_current.new_high_candle.stoch_d}")
                        if current_candle.close < upward_swing_current.new_high_candle.low:
                            converting_to_short = True
                    if converting_to_short:
                        upward_swing_current.new_high_candle.divergence_used = True
                        self.update_divergence_used_in_memory(upward_swing_current.new_high_candle)
                        print(f"Date # {current_candle.date} :Bearish Internal Non-Extreme Divergence Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {closest_lowest_rsi_candle.date} , Origin RSI {closest_lowest_rsi_candle.rsi}, Origin STOCH_K  {closest_lowest_rsi_candle.stoch_k},  Origin STOCH_D  {closest_lowest_rsi_candle.stoch_d} , End Date {upward_swing_current.new_high_candle.date} , End RSI {upward_swing_current.new_high_candle.rsi}, End STOCH_K {upward_swing_current.new_high_candle.stoch_k}, End STOCH_D {upward_swing_current.new_high_candle.stoch_d}")
                        self.add_candles_short_side = [candle for candle in self.track_all_candles_during_buy if candle.datetime >= upward_swing_current.new_high_candle.datetime]
                    self.add_divergence_info(False, pre_condition_short, converting_to_short, closest_lowest_rsi_candle, upward_swing_current.new_high_candle, False , False, upward_swing_current, False, False )


        if closest_highest_rsi_candle and closest_highest_rsi_candle.body > 0 and upward_swing_current and not upward_swing_current.new_high_candle.divergence_used:
            time_diff = abs(closest_highest_rsi_candle.datetime - upward_swing_current.new_high_candle.datetime)
            if upward_swing_current.new_high_candle.close >= closest_highest_rsi_candle.high and upward_swing_current.new_high_candle.high > closest_highest_rsi_candle.high and time_diff.total_seconds() < 30 * 60 and time_diff.total_seconds() > 2 * 60:
                if upward_swing_current.new_high_candle.rsi < closest_highest_rsi_candle.rsi:
                    pre_condition_short = True
                    print(f"Date # {current_candle.date} :Pre-Condition Bearish Internal Non-Extreme Divergence Triggered with Current RSI is lower then Previous RSI  # Origin Date {closest_highest_rsi_candle.date} , Origin RSI {closest_highest_rsi_candle.rsi}, End Date {upward_swing_current.new_high_candle.date} , End RSI {upward_swing_current.new_high_candle.rsi}")
                    if current_candle.close < upward_swing_current.new_high_candle.low:
                        converting_to_short = True
                    if converting_to_short:
                        upward_swing_current.new_high_candle.divergence_used = True
                        self.update_divergence_used_in_memory(upward_swing_current.new_high_candle)
                        print(f"Date # {current_candle.date} :Bearish Internal Non-Extreme Divergence Triggered with Current RSI is lower then Previous RSI # Origin Date {closest_highest_rsi_candle.date} , Origin RSI {closest_highest_rsi_candle.rsi}, End Date {upward_swing_current.new_high_candle.date} , End RSI {upward_swing_current.new_high_candle.rsi}")
                        self.add_candles_short_side = [candle for candle in self.track_all_candles_during_buy if candle.datetime >= upward_swing_current.new_high_candle.datetime]
                    self.add_divergence_info(False, False, converting_to_short, closest_highest_rsi_candle, upward_swing_current.new_high_candle, True , False, upward_swing_current, False, True )

        return converting_to_short, pre_condition_short

    def is_extreme_external_swing_bullish_divergence_triggered(self, downward_swing_current, current_candle):

        converting_to_buy = False
        pre_condition_buy = False
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
                        print(f"Date # {current_candle.date} :Pre Condition Bullish External Swings Extreme Divergence Trigger with Current RSI IS Lower Then Previous RSI # Origin Date {lowest_rsi_candle.date}  , Origin RSI {lowest_rsi_candle.rsi}, End Date {lowest_rsi_candle_in_downward_swing.date}, End RSI {lowest_rsi_candle_in_downward_swing.rsi}")
                        pre_condition_buy = True
                        if current_candle.close > downward_swing_current.new_low_candle.high and current_candle.close > lowest_rsi_candle_in_downward_swing.high:
                            print(f"Date # {current_candle.date} :External Swings Extreme Divergence Trigger with Current RSI IS Lower Then Previous RSI # Origin Date {lowest_rsi_candle.date}  , Origin RSI {lowest_rsi_candle.rsi}, End Date {lowest_rsi_candle_in_downward_swing.date}, End RSI {lowest_rsi_candle_in_downward_swing.rsi}")
                            self.add_candles_buy_side = [candle for candle in self.track_all_candles_during_short if candle.datetime >= downward_swing_current.new_low_candle.datetime]
                            converting_to_buy = True
                            downward_swing_current.new_low_candle.divergence_used = True
                            self.update_divergence_used_in_memory(downward_swing_current.new_low_candle)
                        self.add_divergence_info(True, False, converting_to_buy, lowest_rsi_candle, lowest_rsi_candle_in_downward_swing, True , False, downward_swing_current, False, True )
        return converting_to_buy, pre_condition_buy

    def is_extreme_external_swing_bearish_divergence_triggered(self, upward_swing_current,  current_candle):

        highest_rsi_candle = None
        converting_to_short = False
        pre_condition_short = False
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
                        print(f"Date # {current_candle.date} :Pre Condition Bearish External Swings Extreme Divergence Trigger with Current RSI IS Higher Then Previous RSI # Origin Date {highest_rsi_candle.date}, Origin RSI {highest_rsi_candle.rsi}, End Date {highest_rsi_candle_in_upward_swing.date}  , End RSI {highest_rsi_candle_in_upward_swing.rsi}")
                        if current_candle.close < self.save_upward_swing_current.new_high_candle.low:
                            print(f"Date # {current_candle.date} :Bearish External Swings Extreme Divergence Trigger with Current RSI IS Higher Then Previous RSI # Origin Date {highest_rsi_candle.date}, Origin RSI {highest_rsi_candle.rsi}, End Date {highest_rsi_candle_in_upward_swing.date}  , End RSI {highest_rsi_candle_in_upward_swing.rsi}")
                            self.add_candles_short_side = [candle for candle in self.track_all_candles_during_buy if candle.datetime >= upward_swing_current.new_high_candle.datetime]
                            converting_to_short = True
                            upward_swing_current.new_high_candle.divergence_used = True
                            self.update_divergence_used_in_memory(upward_swing_current.new_high_candle)
                        self.add_divergence_info(False, False, converting_to_short, highest_rsi_candle, highest_rsi_candle_in_upward_swing, True , False, upward_swing_current, False, True )

        return converting_to_short, pre_condition_short

    def is_extreme_internal_swing_bullish_divergence_triggered(self,  downward_swing_current, current_candle):

        converting_to_buy = False
        pre_condition_buy = False
        if downward_swing_current:
            lowest_rsi_candle_in_downward_swing = self.get_lowest_rsi_candle_below_5_between_dates(downward_swing_current.datetime, downward_swing_current.new_low_candle.datetime)
            if (lowest_rsi_candle_in_downward_swing and downward_swing_current.new_low_candle.rsi > lowest_rsi_candle_in_downward_swing.rsi
                    and downward_swing_current.new_low_candle.low < lowest_rsi_candle_in_downward_swing.low
                    and downward_swing_current.new_low_candle.close <= lowest_rsi_candle_in_downward_swing.low
                    and downward_swing_current.new_low_candle.close < lowest_rsi_candle_in_downward_swing.close and not downward_swing_current.new_low_candle.divergence_used):
                volume_condition = True #downward_swing_current.new_low_candle.body_volume < downward_swing_current.new_low_candle.body_volume or downward_swing_current.new_low_candle.volume < downward_swing_current.new_low_candle.volume
                if volume_condition:
                    pre_condition_buy = True
                    print(f"Date # {current_candle.date} :Pre Condition Bullish Internal Swings Extreme Divergence Trigger with Current RSI IS Lower Then Previous RSI # Origin Date {lowest_rsi_candle_in_downward_swing.date} , Origin RSI {lowest_rsi_candle_in_downward_swing.rsi}, End Date {downward_swing_current.new_low_candle.date} , End RSI {downward_swing_current.new_low_candle.rsi}")
                    if current_candle.close > downward_swing_current.new_low_candle.high:
                        time_diff = abs(lowest_rsi_candle_in_downward_swing.datetime - downward_swing_current.new_low_candle.datetime)
                        if time_diff.total_seconds() > 2 * 60:
                            print(f"Date # {current_candle.date} :Bullish Internal Swings Extreme Divergence Trigger with Current RSI IS Lower Then Previous RSI # Origin Date {lowest_rsi_candle_in_downward_swing.date} , Origin RSI {lowest_rsi_candle_in_downward_swing.rsi}, End Date {downward_swing_current.new_low_candle.date} , End RSI {downward_swing_current.new_low_candle.rsi}")
                            self.add_candles_buy_side = [candle for candle in self.track_all_candles_during_short if candle.datetime >= downward_swing_current.new_low_candle.datetime]
                            converting_to_buy = True
                            downward_swing_current.new_low_candle.divergence_used = True
                            self.update_divergence_used_in_memory(downward_swing_current.new_low_candle)
                    self.add_divergence_info(True, False, converting_to_buy, lowest_rsi_candle_in_downward_swing, downward_swing_current.new_low_candle, True , False, downward_swing_current, False, True )

        return converting_to_buy, pre_condition_buy

    def is_extreme_internal_swing_bearish_divergence_triggered(self,  upward_swing_current, current_candle):
        converting_to_short = False
        pre_condition_short = False
        if upward_swing_current:
            highest_rsi_candle_in_upward_swing = self.get_highest_rsi_candle_above_94_between_dates(upward_swing_current.datetime, upward_swing_current.new_high_candle.datetime)
            if (highest_rsi_candle_in_upward_swing and upward_swing_current.new_high_candle.rsi < highest_rsi_candle_in_upward_swing.rsi
                    and upward_swing_current.new_high_candle.high > highest_rsi_candle_in_upward_swing.high
                    and upward_swing_current.new_high_candle.close >= highest_rsi_candle_in_upward_swing.high
                    and upward_swing_current.new_high_candle.close > highest_rsi_candle_in_upward_swing.close and not upward_swing_current.new_high_candle.divergence_used):
                volume_condition = True #upward_swing_current.new_high_candle.body_volume < upward_swing_current.new_high_candle.previous_body_volume or upward_swing_current.new_high_candle.volume < upward_swing_current.new_high_candle.body_volume
                if volume_condition:
                    pre_condition_short = True
                    print(f"Date # {current_candle.date} :Pre Condition Bearish Internal Swings Extreme Divergence Triggered with Current RSI IS Lower Then Previous RSI # Origin Date {highest_rsi_candle_in_upward_swing.date} , Origin RSI {highest_rsi_candle_in_upward_swing.rsi}, End Date {upward_swing_current.new_high_candle.date} , End RSI {upward_swing_current.new_high_candle.rsi}")
                    if current_candle.close < upward_swing_current.new_high_candle.low:
                        time_diff = abs(highest_rsi_candle_in_upward_swing.datetime - upward_swing_current.new_high_candle.datetime)
                        if time_diff.total_seconds() > 2 * 60:
                            print(f"Date # {current_candle.date} :Bearish Internal Swings Extreme Divergence Triggered with Current RSI IS Lower Then Previous RSI # Origin Date {highest_rsi_candle_in_upward_swing.date} , Origin RSI {highest_rsi_candle_in_upward_swing.rsi}, End Date {upward_swing_current.new_high_candle.date} , End RSI {upward_swing_current.new_high_candle.rsi}")
                            self.add_candles_short_side = [candle for candle in self.track_all_candles_during_buy if candle.datetime >= upward_swing_current.new_high_candle.datetime]
                            converting_to_short = True
                            upward_swing_current.new_high_candle.divergence_used = True
                            self.update_divergence_used_in_memory(upward_swing_current.new_high_candle)
                    self.add_divergence_info(False, False, converting_to_short, highest_rsi_candle_in_upward_swing, upward_swing_current.new_high_candle, True , False, upward_swing_current, False, True )

        return converting_to_short, pre_condition_short

    def update_converting_to_short(self):
        if self.save_upward_swing_current:
            self.add_candles_short_side = [candle for candle in self.track_all_candles if candle.datetime >= self.save_upward_swing_current.new_high_candle.datetime]
        else:
            self.add_candles_short_side = self.track_all_candles_during_buy.copy()

        if self.save_downward_swing_previous and self.save_downward_swing_current and self.save_downward_swing_previous.datetime != self.save_downward_swing_current.datetime:
            self.save_downward_swing_current.previous_swing_info = self.save_downward_swing_previous
            self.save_downward_swing_previous = copy.deepcopy(self.save_downward_swing_current)
        if self.save_downward_swing_current and not self.save_downward_swing_previous:
            self.save_downward_swing_previous = copy.deepcopy(self.save_downward_swing_current)
        self.save_downward_swing_current = None

        if self.save_upward_swing_previous and self.save_upward_swing_current and self.save_upward_swing_previous.datetime != self.save_upward_swing_current.datetime:
            self.save_upward_swing_current.previous_swing_info = self.save_upward_swing_previous
            self.save_upward_swing_previous = copy.deepcopy(self.save_upward_swing_current)
        if self.save_upward_swing_current and not self.save_upward_swing_previous:
            self.save_upward_swing_previous = copy.deepcopy(self.save_upward_swing_current)
        self.save_upward_swing_current = None

        self.add_candles_short_side.append(self.current_candle)
        self.short_triggered_candle_two = None
        self.buy_triggered_candle_two = None
        self.manual_buy_short_trigger_candle = None
        self.copy_data = True
        self.in_trade_candle = self.current_candle

    def update_converting_to_buy(self):
        if self.save_downward_swing_current:
            self.add_candles_buy_side = [candle for candle in self.track_all_candles if candle.datetime >= self.save_downward_swing_current.new_low_candle.datetime]
        else:
            self.add_candles_buy_side = self.track_all_candles_during_short.copy()


        if self.save_downward_swing_previous and self.save_downward_swing_current and self.save_downward_swing_previous.datetime != self.save_downward_swing_current.datetime:
            self.save_downward_swing_current.previous_swing_info = self.save_downward_swing_previous
            self.save_downward_swing_previous = copy.deepcopy(self.save_downward_swing_current)
        if self.save_downward_swing_current and not self.save_downward_swing_previous:
            self.save_downward_swing_previous = copy.deepcopy(self.save_downward_swing_current)
        self.save_downward_swing_current = None

        if self.save_upward_swing_previous and self.save_upward_swing_current and self.save_upward_swing_previous.datetime != self.save_upward_swing_current.datetime:
            self.save_upward_swing_current.previous_swing_info = self.save_upward_swing_previous
            self.save_upward_swing_previous = copy.deepcopy(self.save_upward_swing_current)
        if self.save_upward_swing_current and not self.save_upward_swing_previous:
            self.save_upward_swing_previous = copy.deepcopy(self.save_upward_swing_current)
        self.save_upward_swing_current = None

        self.add_candles_buy_side.append(self.current_candle)
        self.buy_triggered_candle_two = None
        self.short_triggered_candle_two = None
        self.manual_buy_short_trigger_candle = None
        self.copy_data = True
        self.in_trade_candle = self.current_candle

    def initialize_insurance_trending_candles(self, current_candle):
        try:
            short_divergence_candle_timestamp = None
            buy_divergence_candle_timestamp = None
            buy_stop_limit_timestamp = None
            short_stop_limit_timestamp = None

            bulk_buy_stop_limit_timestamp = None
            bulk_short_stop_limit_timestamp = None
            bulk_buy_order_timestamp = None
            bulk_short_order_timestamp = None
            self.bulk_lot_size = None
            self.bulk_stop_loss_adjust = None

            buy_trending_candle_timestamp = None
            short_trending_candle_timestamp = None

            if not buy_trending_candle_timestamp:
                self.buy_trending_candle = None

            if buy_trending_candle_timestamp:
                buy_trending_datetime = datetime.strptime(buy_trending_candle_timestamp, "%m/%d %I:%M %p")
                filter_candles = [candle for candle in self.track_all_candles if candle.datetime == buy_trending_datetime]
                if filter_candles:
                    self.buy_trending_candle = filter_candles[-1]

            print(f"Date # {current_candle.date} :Buy Trending Candle {self.buy_trending_candle}")

            if short_trending_candle_timestamp:
                short_trending_datetime = datetime.strptime(short_trending_candle_timestamp, "%m/%d %I:%M %p")
                filter_candles = [candle for candle in self.track_all_candles if candle.datetime == short_trending_datetime]
                if filter_candles:
                    self.short_trending_candle = filter_candles[-1]

            if not short_trending_candle_timestamp:
                self.short_trending_candle = None


            print(f"Date # {current_candle.date} :Short Trending Candle  {self.short_trending_candle}")

            if not buy_divergence_candle_timestamp:
                self.buy_divergence_candle = None

            if buy_divergence_candle_timestamp and not self.buy_divergence_candle:
                buy_divergence_datetime = datetime.strptime(buy_divergence_candle_timestamp, "%m/%d %I:%M %p")
                filter_candles = [candle for candle in self.track_all_candles if candle.datetime == buy_divergence_datetime]
                if filter_candles:
                    self.buy_divergence_candle = filter_candles[-1]

            if self.buy_divergence_candle:
                if current_candle.close < self.buy_divergence_candle.close and current_candle.body < 0:
                    self.buy_divergence_candle = current_candle

            print(f"Date # {current_candle.date} :Buy Divergence Candle {self.buy_divergence_candle}")

            if not short_divergence_candle_timestamp:
                self.short_divergence_candle = None

            if short_divergence_candle_timestamp and not self.short_divergence_candle:
                short_divergence_datetime = datetime.strptime(short_divergence_candle_timestamp, "%m/%d %I:%M %p")
                filter_candles = [candle for candle in self.track_all_candles if candle.datetime == short_divergence_datetime]
                if filter_candles:
                    self.short_divergence_candle = filter_candles[-1]

            if self.short_divergence_candle:
                if current_candle.close > self.short_divergence_candle.close and current_candle.body > 0:
                    self.short_divergence_candle = current_candle

            print(f"Date # {current_candle.date} :Short Divergence Candle  {self.short_divergence_candle}")

            if not buy_stop_limit_timestamp:
                self.buy_stop_limit_candle = None

            if buy_stop_limit_timestamp:
                buy_stop_limit_datetime = datetime.strptime(buy_stop_limit_timestamp, "%m/%d %I:%M %p")
                filter_candles = [candle for candle in self.track_all_candles if candle.datetime == buy_stop_limit_datetime]
                if filter_candles:
                    self.buy_stop_limit_candle = filter_candles[-1]

            print(f"Date # {current_candle.date} :Buy Stop Limit Candle {self.buy_stop_limit_candle}")

            if not short_stop_limit_timestamp:
                self.short_stop_limit_candle = None

            if short_stop_limit_timestamp:
                short_stop_limit_datetime = datetime.strptime(short_stop_limit_timestamp, "%m/%d %I:%M %p")
                filter_candles = [candle for candle in self.track_all_candles if candle.datetime == short_stop_limit_datetime]
                if filter_candles:
                    self.short_stop_limit_candle = filter_candles[-1]

            print(f"Date # {current_candle.date} :Short Stop Limit Candle {self.short_stop_limit_candle}")

            if not bulk_buy_stop_limit_timestamp:
                self.bulk_buy_stop_limit_candle = None

            if bulk_buy_stop_limit_timestamp:
                bulk_buy_stop_limit_datetime = datetime.strptime(bulk_buy_stop_limit_timestamp, "%m/%d %I:%M %p")
                filter_candles = [candle for candle in self.track_all_candles if candle.datetime == bulk_buy_stop_limit_datetime]
                if filter_candles:
                    self.bulk_buy_stop_limit_candle = filter_candles[-1]

            print(f"Date # {current_candle.date} :Bulk Buy Stop Limit Candle {self.bulk_buy_stop_limit_candle}")

            if not bulk_short_stop_limit_timestamp:
                self.bulk_short_stop_limit_candle = None

            if bulk_short_stop_limit_timestamp:
                bulk_short_stop_limit_datetime = datetime.strptime(bulk_short_stop_limit_timestamp, "%m/%d %I:%M %p")
                filter_candles = [candle for candle in self.track_all_candles if candle.datetime == bulk_short_stop_limit_datetime]
                if filter_candles:
                    self.bulk_short_stop_limit_candle = filter_candles[-1]

            print(f"Date # {current_candle.date} :Bulk Short Stop Limit Candle {self.bulk_short_stop_limit_candle}")

            if not bulk_buy_order_timestamp:
                self.bulk_buy_order_candle = None

            if bulk_buy_order_timestamp:
                bulk_buy_order_datetime = datetime.strptime(bulk_buy_order_timestamp, "%m/%d %I:%M %p")
                filter_candles = [candle for candle in self.track_all_candles if candle.datetime == bulk_buy_order_datetime]
                if filter_candles:
                    self.bulk_buy_order_candle = filter_candles[-1]

            print(f"Date # {current_candle.date} :Bulk Buy Order Candle {self.bulk_buy_order_candle}")

            if not bulk_short_order_timestamp:
                self.bulk_short_order_candle = None

            if bulk_short_order_timestamp:
                bulk_short_order_datetime = datetime.strptime(bulk_short_order_timestamp, "%m/%d %I:%M %p")
                filter_candles = [candle for candle in self.track_all_candles if candle.datetime == bulk_short_order_datetime]
                if filter_candles:
                    self.bulk_short_order_candle = filter_candles[-1]

            print(f"Date # {current_candle.date} :Bulk Short Order Candle {self.bulk_short_order_candle}")
            print(f"Date # {current_candle.date} :Bulk Lot Size {self.bulk_lot_size}")
            print(f"Date # {current_candle.date} :Bulk stop loss  adjust  {self.bulk_stop_loss_adjust}")
        except:
            print(f"Date # {current_candle.date} :Error when initializing all limit candles ")

    def update_divergence_used_in_memory(self, update_candle):
        for candle in self.track_all_candles:
            if candle.datetime == update_candle.datetime:
                candle.divergence_used = True


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
        #self.initialize_insurance_trending_candles(current_candle)
        # is_buy_count = 0
        # is_higher_diverence_called = False
        # is_choppy = False
        #
        # if current_candle.fib == 377:
        #     print("Put Break Point")

        # for interval_divergence in interval_divergences:
        #     # If it's the first call, initialize last_candle_time
        #     if interval_divergence.last_candle_time is None:
        #         interval_divergence.last_candle_time = current_candle
        #         interval_divergence.next(current_candle)  # Call next for the first candle
        #         is_higher_diverence_called = True
        #
        #     # Calculate the time difference since the last call
        #     time_since_last_call = current_candle.datetime - interval_divergence.last_candle_time.datetime
        #
        #     if time_since_last_call >= interval_divergence.interval_time_delta:
        #         # Time to call the next method for this interval
        #         interval_divergence.next(current_candle)
        #         interval_divergence.last_candle_time = current_candle  # Update the last call time
        #         is_higher_diverence_called = True
        #
        # if is_higher_diverence_called:
        #     for interval_divergence in interval_divergences:
        #         if current_candle.close >= interval_divergence.current_candle.close:
        #             is_buy_count = is_buy_count + 1
        #
        #     if is_buy_count >= 1:
        #         self.enable_trade_buying = True
        #         self.enable_trade_shorting = False
        #     else:
        #         self.enable_trade_buying = False
        #         self.enable_trade_shorting = True
        #
        # if self.cover_stop_limit:
        #     if not self.enable_trade_shorting and self.enable_trade_buying:
        #         self.cover_stop_limit = None
        #
        # if self.sell_stop_limit:
        #     if self.enable_trade_shorting and not self.enable_trade_buying:
        #         self.sell_stop_limit = None
        # if is_choppy:
        #     self.enable_trade_buying = False
        #     self.enable_trade_shorting = False


        if self.current_candle.rsi >= 94:
            self.candles_above_94.append(self.current_candle)
        if self.current_candle.rsi <= 5:
            self.candles_below_5.append(self.current_candle)

        if self.current_candle.index == self.last_index:
            global updated_divergences
            updated_divergences = self.divergences_by_index.copy()

        if current_candle.fib == 64:
            print("Put Break Point")

        if self.enable_trade_shorting and not self.enable_trade_buying:
            if self.current_candle.rsi < 94 and self.current_candle.stoch_k < 100:
                if self.current_candle.previous_rsi > 94 and self.current_candle.previous_stoch_k > 80:
                    if not self.cover_stop_limit:
                        self.cover_stop_limit = self.current_candle.previous_high
                    if self.cover_stop_limit and self.cover_stop_limit != self.current_candle.previous_high:
                        self.cover_stop_limit = self.current_candle.previous_high
                    print(f"Date # {current_candle.previous_candle_datetime} :Current Only Shorting and If the price cross above self.cover_stop_limit then it will cover based on buy divergence # {self.cover_stop_limit}" )


        if self.enable_trade_buying and not self.enable_trade_shorting:
            if self.current_candle.rsi > 5 and self.current_candle.stoch_k > 0:
                if self.current_candle.previous_rsi < 5 and self.current_candle.previous_stoch_k < 20:
                    if not self.sell_stop_limit:
                        self.sell_stop_limit = self.current_candle.previous_low
                    if self.sell_stop_limit and self.sell_stop_limit != self.current_candle.previous_low:
                        self.sell_stop_limit = self.current_candle.previous_low
                    print(f"Date # {current_candle.previous_candle_datetime} :Current Only Buying and If the price cross below self.sell_stop_limit then it will sell based on short divergence # {self.sell_stop_limit}" )


        # count_above_94 = len(self.candles_above_94)
        # count_below_5 = len(self.candles_below_5)
        # if count_above_94 > (count_below_5 +  0.25 * count_below_5):
        #     self.enable_trade_buying = True
        #     self.enable_trade_shorting = False
        # elif count_below_5 > (count_above_94 + 0.25 * count_above_94):
        #     self.enable_trade_buying = True
        #     self.enable_trade_shorting = True
        # else:
        #     self.enable_trade_buying = True
        #     self.enable_trade_shorting = True
        manual_trade_date_list = []

        if self.data.TRADE[-1] == 0:
            self.buy_order = False
            self.short_order = False
            self.in_trade = False
            self.close_only_once = False
            self.position.close()
            self.track_first_set_candles.append(current_candle)

        if self.data.TRADE[-1] == 1:

            if len(self.track_first_set_candles) > 0:
                self.track_all_candles = self.track_first_set_candles[-60:]
                self.highest_candle = max(self.track_all_candles, key=lambda x: x.high)
                self.lowest_candle = min(self.track_all_candles, key=lambda x: x.low)
                self.track_first_set_candles.clear()

            #print(f"current_candle {current_candle}")
            self.track_all_candles.append(current_candle)
            self.close_only_once = False

            if not self.in_trade:

                if current_candle.fib == 44:
                    print("Put Break Point")

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
                        print(f"Date # {current_candle.date} :self.save_upward_swing_current # {self.save_upward_swing_current}")
                        print(f"Date # {current_candle.date} :self.save_upward_swing_previous # {self.save_upward_swing_previous}")
                        if upward_swing_current.is_new_high and not short_condition:
                            converting_to_short, pre_condition_short = self.is_extreme_internal_swing_bearish_divergence_triggered(upward_swing_current, current_candle)
                            if converting_to_short:
                                short_condition = True
                                print(f"Date # {current_candle.date} :Extreme Internal Swing Bearish Divergence Triggered Short Order At Candle {current_candle}")

                        if upward_swing_current.is_new_high and not short_condition and self.save_upward_swing_previous:
                            converting_to_short, pre_condition_short = self.is_extreme_external_swing_bearish_divergence_triggered(upward_swing_current, current_candle)
                            if converting_to_short:
                                short_condition = True
                                print(f"Date # {current_candle.date} :Extreme External Swing Bearish Divergence Triggered Short Order At Candle {current_candle}")

                        if upward_swing_current.is_new_high and not short_condition:
                            converting_to_short, pre_condition_short = self.is_non_extreme_internal_bearish_divergence(upward_swing_current, current_candle)
                            if converting_to_short:
                                short_condition = True
                                print(f"Date # {current_candle.date} :Non Extreme Internal Bearish Divergence Triggered Short Order At Candle {current_candle}")

                    if len(downward_swings) >= 1:
                        downward_swing_current = downward_swings[-1]
                        self.save_downward_swing_current = downward_swing_current
                        self.update_lower_candle(self.save_downward_swing_current)
                        print(f"Date # {current_candle.date} :self.save_downward_swing_current # {self.save_downward_swing_current}")
                        print(f"Date # {current_candle.date} :self.save_downward_swing_previous # {self.save_downward_swing_previous}")
                        if downward_swing_current.is_new_low and not buy_condition :
                            converting_to_buy, pre_condition_buy = self.is_extreme_internal_swing_bullish_divergence_triggered(downward_swing_current, current_candle)
                            if converting_to_buy:
                                buy_condition = True
                                print(f"Date # {current_candle.date} :Extreme Internal Swing Bullish Divergence Triggered Buy Order At Candle {current_candle}")

                        if downward_swing_current.is_new_low and not buy_condition and self.save_downward_swing_previous:
                            converting_to_buy, pre_condition_buy = self.is_extreme_external_swing_bullish_divergence_triggered(downward_swing_current, current_candle)
                            if converting_to_buy:
                                buy_condition = True
                                print(f"Date # {current_candle.date} :Extreme External Swing Bullish Divergence Triggered Buy Order At Candle {current_candle}")

                        if downward_swing_current.is_new_low and not buy_condition:
                            converting_to_buy, pre_condition_buy = self.is_non_extreme_internal_bullish_divergence(downward_swing_current, current_candle)
                            if converting_to_buy:
                                buy_condition = True
                                print(f"Date # {current_candle.date} :Non Extreme Internal Bullish Divergence Triggered Buy Order At Candle {current_candle}")


                if self.buy_divergence_candle and not self.buy_divergence_candle.divergence_used:
                    if current_candle.close > self.buy_divergence_candle.close:
                        if current_candle.close > self.buy_divergence_candle.high:
                            self.buy_divergence_candle.divergence_used = True
                            buy_condition = True
                            print(f"Date # {current_candle.date} :The Manual Buy Divergence condition met for Buy and candles invloved current_candle {current_candle} and self.buy_divergence_candle {self.buy_divergence_candle}")

                if self.short_divergence_candle and not self.short_divergence_candle.divergence_used:
                    if current_candle.close < self.short_divergence_candle.close:
                        if current_candle.close < self.short_divergence_candle.low:
                            self.short_divergence_candle.divergence_used = True
                            short_condition = True
                            print(f"Date # {current_candle.date} :The Manual Short Divergence condition met and shorted , candles invoved current_candle # {current_candle} and self.short_divergence_candle {self.short_divergence_candle}")

                if short_condition:
                    stop_loss = self.get_stop_loss(False)
                    self.update_converting_to_short()
                    print(f"Date # {current_candle.date} :###################")
                else:
                    short_condition = False

                if buy_condition:
                    stop_loss = self.get_stop_loss(True)
                    self.update_converting_to_buy()
                    print(f"Date # {current_candle.date} :###################")
                else:
                    buy_condition = False

            if self.in_trade:

                if self.buy_order:

                    if current_candle.fib == 232:
                        print("Put Break Point")

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
                                self.save_upward_swing_current.previous_swing_info = copy.deepcopy(self.save_upward_swing_previous)
                                self.save_upward_swing_previous = copy.deepcopy(self.save_upward_swing_current)
                                self.save_upward_swing_current = copy.deepcopy(upward_swing_current)
                                self.track_all_candles_during_buy = [candle for candle in self.track_all_candles_during_buy if candle.datetime >= upward_swing_current.datetime]
                            if upward_swing_current.new_high_candle.datetime != upward_swing_previous.new_high_candle.datetime and not self.save_upward_swing_current:
                                upward_swing_previous.previous_swing_info = copy.deepcopy(self.save_upward_swing_previous)
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
                        print(f"Date # {current_candle.date} :self.save_upward_swing_current # {self.save_upward_swing_current}")
                        print(f"Date # {current_candle.date} :self.save_upward_swing_previous # {self.save_upward_swing_previous}")
                        self.update_higher_candle(self.save_upward_swing_current)
                        if upward_swing_current.is_new_high:

                            # Divergence between two swing
                            if not converting_to_short and self.save_upward_swing_previous:
                                converting_to_short, pre_condition_short = self.is_extreme_external_swing_bearish_divergence_triggered(upward_swing_current, current_candle)

                            # Divergence with same swing
                            if not converting_to_short and not pre_condition_short:
                                converting_to_short, pre_condition_short = self.is_extreme_internal_swing_bearish_divergence_triggered(upward_swing_current, current_candle)

                            # Non Extreme Internal Divergence same swing.
                            if not converting_to_short and not pre_condition_short:
                                converting_to_short, pre_condition_short = self.is_non_extreme_internal_bearish_divergence(upward_swing_current, current_candle)

                            if not pre_condition_short and self.save_upward_swing_current and self.save_upward_swing_previous:
                                if self.save_upward_swing_previous.new_high_candle.close > self.save_upward_swing_current.new_high_candle.close and self.save_upward_swing_previous.new_high_candle.body > 0 and self.save_upward_swing_current.new_high_candle.body > 0:
                                    if self.save_upward_swing_previous.new_high_candle.high > self.save_upward_swing_current.new_high_candle.high:
                                        if not self.save_upward_swing_current.new_high_candle.divergence_used:
                                            if self.save_upward_swing_current.new_high_candle.rsi > self.save_upward_swing_previous.new_high_candle.rsi or self.save_upward_swing_current.new_high_candle.stoch_k > self.save_upward_swing_previous.new_high_candle.stoch_k or self.save_upward_swing_current.new_high_candle.stoch_d > self.save_upward_swing_previous.new_high_candle.stoch_d:
                                                pre_condition_short = True
                                                print(f"Date # {current_candle.date} :Pre-Condition  Bearish Internal Non-Extreme Divergence, when comparing current to previous swing, Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {self.save_upward_swing_previous.new_high_candle.date} , Origin RSI {self.save_upward_swing_previous.new_high_candle.rsi}, Origin STOCH_K  {self.save_upward_swing_previous.new_high_candle.stoch_k},  Origin STOCH_D  {self.save_upward_swing_previous.new_high_candle.stoch_d} , End Date {self.save_upward_swing_current.new_high_candle.date} , End RSI {self.save_upward_swing_current.new_high_candle.rsi}, End STOCH_K {self.save_upward_swing_current.new_high_candle.stoch_k}, End STOCH_D {self.save_upward_swing_current.new_high_candle.stoch_d}")
                                                if current_candle.close < self.save_upward_swing_current.new_high_candle.close and current_candle.close <= self.save_upward_swing_current.new_high_candle.low:
                                                    converting_to_short = True
                                                    self.save_upward_swing_current.new_high_candle.divergence_used = True
                                                    self.update_divergence_used_in_memory(self.save_upward_swing_current.new_high_candle)
                                                    print(f"Date # {current_candle.date} :Bearish Internal Non-Extreme Divergence, when comparing current to previous swing, Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {self.save_upward_swing_previous.new_high_candle.date} , Origin RSI {self.save_upward_swing_previous.new_high_candle.rsi}, Origin STOCH_K  {self.save_upward_swing_previous.new_high_candle.stoch_k},  Origin STOCH_D  {self.save_upward_swing_previous.new_high_candle.stoch_d} , End Date {self.save_upward_swing_current.new_high_candle.date} , End RSI {self.save_upward_swing_current.new_high_candle.rsi}, End STOCH_K {self.save_upward_swing_current.new_high_candle.stoch_k}, End STOCH_D {self.save_upward_swing_current.new_high_candle.stoch_d}")
                                                self.add_divergence_info(False, False, converting_to_short, self.save_upward_swing_previous.new_high_candle, self.save_upward_swing_current.new_high_candle, False , False, self.save_upward_swing_previous, False, True )

                            if not pre_condition_short and self.save_upward_swing_current and self.save_upward_swing_previous:
                                if self.save_upward_swing_previous.new_high_candle.close < self.save_upward_swing_current.new_high_candle.close and self.save_upward_swing_previous.new_high_candle.body > 0 and self.save_upward_swing_current.new_high_candle.body > 0:
                                    if self.save_upward_swing_previous.new_high_candle.high < self.save_upward_swing_current.new_high_candle.high:
                                        if not self.save_upward_swing_current.new_high_candle.divergence_used:
                                            if self.save_upward_swing_current.new_high_candle.rsi < self.save_upward_swing_previous.new_high_candle.rsi:
                                                pre_condition_short = True
                                                print(f"Date # {current_candle.date} :Pre-Condition  Bearish Internal Non-Extreme Divergence, when comparing current to previous swing, Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {self.save_upward_swing_previous.new_high_candle.date} , Origin RSI {self.save_upward_swing_previous.new_high_candle.rsi}, End Date {self.save_upward_swing_current.new_high_candle.date} , End RSI {self.save_upward_swing_current.new_high_candle.rsi}")
                                                if current_candle.close < self.save_upward_swing_current.new_high_candle.close and current_candle.close <= self.save_upward_swing_current.new_high_candle.low:
                                                    converting_to_short = True
                                                    self.save_upward_swing_current.new_high_candle.divergence_used = True
                                                    self.update_divergence_used_in_memory(self.save_upward_swing_current.new_high_candle)
                                                    print(f"Date # {current_candle.date} :Bearish Internal Non-Extreme Divergence, when comparing current to previous swing, Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {self.save_upward_swing_previous.new_high_candle.date} , Origin RSI {self.save_upward_swing_previous.new_high_candle.rsi}, End Date {self.save_upward_swing_current.new_high_candle.date} , End RSI {self.save_upward_swing_current.new_high_candle.rsi}")
                                                self.add_divergence_info(False, False, converting_to_short, self.save_upward_swing_previous.new_high_candle, self.save_upward_swing_current.new_high_candle, False , False, self.save_upward_swing_previous, False, True )

                        downward_swings = self.find_downward_swings_from_high(self.track_all_candles_during_buy, downward_candles_to_consider, True, upward_swing_current.new_high_candle.datetime, False)
                        if len(downward_swings) >= 1 and not converting_to_short and not sell_condition:
                            downward_swing_current = downward_swings[-1]
                            self.save_downward_swing_current = downward_swing_current

                            if downward_swing_current.new_low_candle:
                                upward_swings = self.find_upward_swings_from_low(self.track_all_candles_during_buy, downward_candles_to_consider, True, downward_swing_current.new_low_candle.datetime, False)
                                if len(upward_swings) > 0:
                                    upward_swing = upward_swings[-1]
                                    if upward_swing.datetime != self.save_upward_swing_current.datetime:
                                        if self.save_upward_swing_previous:
                                            #self.save_upward_swing_previous.previous_swing_info = None
                                            self.save_upward_swing_current.previous_swing_info = self.save_upward_swing_previous
                                            self.save_upward_swing_previous = copy.deepcopy(self.save_upward_swing_current)
                                            self.save_upward_swing_current = upward_swing

                                        if self.save_downward_swing_previous and self.save_downward_swing_previous.datetime != self.save_downward_swing_current.datetime:
                                            #self.save_downward_swing_previous.previous_swing_info = None
                                            self.save_downward_swing_current.previous_swing_info = self.save_downward_swing_previous
                                            self.save_downward_swing_previous = copy.deepcopy(self.save_downward_swing_current)
                                            candles_clean_up_list = [candle for candle in self.track_all_candles_during_buy if candle.datetime >= downward_swing_current.datetime]
                                            self.track_all_candles_during_buy = candles_clean_up_list.copy()
                                        if not self.save_downward_swing_previous :
                                            self.save_downward_swing_previous = copy.deepcopy(self.save_downward_swing_current)
                                            candles_clean_up_list = [candle for candle in self.track_all_candles_during_buy if candle.datetime >= downward_swing_current.datetime]
                                            self.track_all_candles_during_buy = candles_clean_up_list.copy()

                        if self.save_downward_swing_previous and self.in_trade_candle:
                            if current_candle.close < self.save_downward_swing_previous.new_low_candle.close and current_candle.low < self.save_downward_swing_previous.new_low_candle.low:
                                self.save_downward_swing_previous.new_low_candle = current_candle
                            if self.save_downward_swing_previous.new_low_candle.datetime > self.in_trade_candle.datetime:
                                converting_to_buy, pre_condition_buy = self.is_non_extreme_internal_bullish_divergence(self.save_downward_swing_previous, current_candle)
                                if not pre_condition_buy:
                                    converting_to_buy, pre_condition_buy = self.is_extreme_internal_swing_bullish_divergence_triggered(self.save_downward_swing_previous, current_candle)

                        if self.save_downward_swing_current and not pre_condition_buy:
                            if current_candle.close < self.save_downward_swing_current.new_low_candle.close and current_candle.low < self.save_downward_swing_current.new_low_candle.low:
                                self.save_downward_swing_current.new_low_candle = current_candle
                            converting_to_buy, pre_condition_buy = self.is_non_extreme_internal_bullish_divergence(self.save_downward_swing_current, current_candle)
                            if not pre_condition_buy:
                                converting_to_buy, pre_condition_buy = self.is_extreme_internal_swing_bullish_divergence_triggered(self.save_downward_swing_current, current_candle)

                        if not pre_condition_buy and self.save_downward_swing_previous and self.save_downward_swing_current:
                            if self.save_downward_swing_previous.new_low_candle.close < self.save_downward_swing_current.new_low_candle.close:
                                if self.save_downward_swing_previous.new_low_candle.low < self.save_downward_swing_current.new_low_candle.low:
                                    if self.save_downward_swing_current.new_low_candle.rsi < self.save_downward_swing_previous.new_low_candle.rsi or self.save_downward_swing_current.new_low_candle.stoch_k < self.save_downward_swing_previous.new_low_candle.stoch_k or self.save_downward_swing_current.new_low_candle.stoch_d < self.save_downward_swing_previous.new_low_candle.stoch_d:
                                        pre_condition_buy = True
                                        print(f"Date # {current_candle.date} :Pre-Condition  bullish Internal Non-Extreme Divergence, when comparing current to previous swing, Triggered with Current RSI is lower then Previous RSI and Below Candles Involved in Divergence # Origin Date {self.save_downward_swing_previous.new_low_candle.date} , Origin RSI {self.save_downward_swing_previous.new_low_candle.rsi}, Origin STOCH_K  {self.save_downward_swing_previous.new_low_candle.stoch_k},  Origin STOCH_D  {self.save_downward_swing_previous.new_low_candle.stoch_d} , End Date {self.save_downward_swing_current.new_low_candle.date} , End RSI {self.save_downward_swing_current.new_low_candle.rsi}, End STOCH_K {self.save_downward_swing_current.new_low_candle.stoch_k}, End STOCH_D {self.save_downward_swing_current.new_low_candle.stoch_d}")

                    if converting_to_short:
                        self.short_triggered_candle_two = current_candle
                        print(f"Date # {current_candle.date} :First Divergence condition met for Short and waiting for the next candle to close below current candle {current_candle}")
                        converting_to_short = False
                        print(f"Date # {current_candle.date} :###################")

                    if self.short_divergence_candle and not self.short_divergence_candle.divergence_used:
                        if current_candle.close < self.short_divergence_candle.close:
                            if current_candle.close < self.short_divergence_candle.low:
                                self.short_divergence_candle.divergence_used = True
                                converting_to_short = True
                                print(f"Date # {current_candle.date} :The Manual Short Divergence condition met and shorted , candles invoved current_candle # {current_candle} and self.short_divergence_candle {self.short_divergence_candle}")

                    if self.short_triggered_candle_two:
                        if current_candle.close < self.short_triggered_candle_two.close and current_candle.body < 0:
                            if self.sell_stop_limit:
                                if current_candle.close < self.sell_stop_limit:
                                    converting_to_short = True
                            else:
                                converting_to_short = True

                            print(f"Date # {current_candle.date} :Second Condition Met for Short and Divergence At Candle {current_candle} close below self.short_triggered_candle_two {self.short_triggered_candle_two}")
                        else:
                            converting_to_short = False

                    if self.buy_trending_candle:
                        if current_candle.close > self.buy_trending_candle.close:
                            converting_to_short = False
                            self.short_triggered_candle_two = None

                    if self.buy_stop_limit_candle:
                        if current_candle.close < self.buy_stop_limit_candle.close:
                            if current_candle.close < self.buy_stop_limit_candle.low:
                                converting_to_short = True
                                print(f"Date # {current_candle.date} :The Buy Trade is going and broke the Buy Stop Candle and Converting to short Trade , The candles invloved current candle {current_candle} and self.buy_stop_limit_candle {self.buy_stop_limit_candle}")

                    if self.enable_trade_shorting and not self.enable_trade_buying:
                        if self.current_candle.previous_rsi > 94 and self.current_candle.rsi < 94:
                            self.short_triggered_candle_two = current_candle
                            self.sell_stop_limit = None


                    if converting_to_short:
                        sell_condition = True
                        buy_condition = False
                        stop_loss = self.get_stop_loss(False)
                        short_condition = True
                        self.update_converting_to_short()


                    self.track_all_candles_during_buy.append(current_candle)

                if self.short_order:

                    if current_candle.fib == 70:
                        print("Put Break Point")

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
                                self.save_downward_swing_current.previous_swing_info = copy.deepcopy(self.save_downward_swing_previous)
                                self.save_downward_swing_previous = copy.deepcopy(self.save_downward_swing_current)
                                self.save_downward_swing_current = copy.deepcopy(downward_swing_current)
                                self.track_all_candles_during_short = [candle for candle in self.track_all_candles_during_short if candle.datetime >= downward_swing_current.datetime]
                                self.track_all_candles_during_short.clear()
                            if downward_swing_previous.datetime != downward_swing_current.datetime and not self.save_downward_swing_current:
                                downward_swing_previous.previous_swing_info = copy.deepcopy(self.save_downward_swing_previous)
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
                        print(f"Date # {current_candle.date} :self.save_downward_swing_current # {self.save_downward_swing_current}")
                        print(f"Date # {current_candle.date} :self.save_downward_swing_previous # {self.save_downward_swing_previous}")

                        self.update_lower_candle(self.save_downward_swing_current)
                        if downward_swing_current.is_new_low:
                            # print(f"Date # {current_candle.date} :downward_swing_current {downward_swing_current}")

                            # Divergence with external swing
                            if not converting_to_buy and self.save_downward_swing_previous:
                                converting_to_buy, pre_condition_buy = self.is_extreme_external_swing_bullish_divergence_triggered(downward_swing_current, current_candle)

                            # Divergence with same swing
                            if not converting_to_buy and not pre_condition_buy:
                                converting_to_buy, pre_condition_buy = self.is_extreme_internal_swing_bullish_divergence_triggered(downward_swing_current, current_candle)

                            # Divergence with non extereme internal swing
                            if not converting_to_buy and not pre_condition_buy:
                                converting_to_buy, pre_condition_buy = self.is_non_extreme_internal_bullish_divergence(downward_swing_current, current_candle)


                            if not pre_condition_buy and not pre_condition_buy and self.save_downward_swing_current and self.save_downward_swing_previous:
                                if self.save_downward_swing_previous.new_low_candle.close < self.save_downward_swing_current.new_low_candle.close:
                                    if self.save_downward_swing_previous.new_low_candle.low < self.save_downward_swing_current.new_low_candle.low:
                                        if not self.save_downward_swing_current.new_low_candle.divergence_used:
                                            if self.save_downward_swing_current.new_low_candle.rsi < self.save_downward_swing_previous.new_low_candle.rsi or self.save_downward_swing_current.new_low_candle.stoch_k < self.save_downward_swing_previous.new_low_candle.stoch_k or self.save_downward_swing_current.new_low_candle.stoch_d < self.save_downward_swing_previous.new_low_candle.stoch_d:
                                                pre_condition_buy = True
                                                print(f"Date # {current_candle.date} :Pre-Condition  Bullish Internal Non-Extreme Divergence, when comparing current to previous swing,  Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {self.save_downward_swing_previous.new_low_candle.date} , Origin RSI {self.save_downward_swing_previous.new_low_candle.rsi}, Origin STOCH_K  {self.save_downward_swing_previous.new_low_candle.stoch_k},  Origin STOCH_D  {self.save_downward_swing_previous.new_low_candle.stoch_d} , End Date {self.save_downward_swing_current.new_low_candle.date} , End RSI {self.save_downward_swing_current.new_low_candle.rsi}, End STOCH_K {self.save_downward_swing_current.new_low_candle.stoch_k}, End STOCH_D {self.save_downward_swing_current.new_low_candle.stoch_d}")
                                                if current_candle.close > self.save_downward_swing_current.new_low_candle.close and current_candle.close >= self.save_downward_swing_current.new_low_candle.high:
                                                    converting_to_buy = True
                                                    self.save_downward_swing_current.new_low_candle.divergence_used = True
                                                    self.update_divergence_used_in_memory(self.save_downward_swing_current.new_low_candle)
                                                    print(f"Date # {current_candle.date} :Bullish Internal Non-Extreme Divergence, when comparing current to previous swing, Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {self.save_downward_swing_previous.new_low_candle.date} , Origin RSI {self.save_downward_swing_previous.new_low_candle.rsi}, Origin STOCH_K  {self.save_downward_swing_previous.new_low_candle.stoch_k},  Origin STOCH_D  {self.save_downward_swing_previous.new_low_candle.stoch_d} , End Date {self.save_downward_swing_current.new_low_candle.date} , End RSI {self.save_downward_swing_current.new_low_candle.rsi}, End STOCH_K {self.save_downward_swing_current.new_low_candle.stoch_k}, End STOCH_D {self.save_downward_swing_current.new_low_candle.stoch_d}")
                                                self.add_divergence_info(True, False, converting_to_buy, self.save_downward_swing_previous.new_low_candle, self.save_downward_swing_current.new_low_candle, False , False, self.save_downward_swing_previous, False, True )

                            if not pre_condition_buy and not pre_condition_buy and self.save_downward_swing_current and self.save_downward_swing_previous:
                                if self.save_downward_swing_previous.new_low_candle.close > self.save_downward_swing_current.new_low_candle.close:
                                    if self.save_downward_swing_previous.new_low_candle.low > self.save_downward_swing_current.new_low_candle.low:
                                        if not self.save_downward_swing_current.new_low_candle.divergence_used:
                                            if self.save_downward_swing_current.new_low_candle.rsi > self.save_downward_swing_previous.new_low_candle.rsi:
                                                pre_condition_buy = True
                                                print(f"Date # {current_candle.date} :Pre-Condition  Bullish Internal Non-Extreme Divergence, when comparing current to previous swing, Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {self.save_downward_swing_previous.new_low_candle.date} , Origin RSI {self.save_downward_swing_previous.new_low_candle.rsi},  End Date {self.save_downward_swing_current.new_low_candle.date} , End RSI {self.save_downward_swing_current.new_low_candle.rsi}")
                                                if current_candle.close > self.save_downward_swing_current.new_low_candle.close and current_candle.close >= self.save_downward_swing_current.new_low_candle.high:
                                                    converting_to_buy = True
                                                    self.save_downward_swing_current.new_low_candle.divergence_used = True
                                                    self.update_divergence_used_in_memory(self.save_downward_swing_current.new_low_candle)
                                                    print(f"Date # {current_candle.date} :Bullish Internal Non-Extreme Divergence, when comparing current to previous swing, Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {self.save_downward_swing_previous.new_low_candle.date} , Origin RSI {self.save_downward_swing_previous.new_low_candle.rsi},  End Date {self.save_downward_swing_current.new_low_candle.date} , End RSI {self.save_downward_swing_current.new_low_candle.rsi}")
                                                self.add_divergence_info(True, False, converting_to_buy, self.save_downward_swing_previous.new_low_candle, self.save_downward_swing_current.new_low_candle, False , False, self.save_downward_swing_previous, False, True )


                        upward_swings = self.find_upward_swings_from_low(self.track_all_candles_during_short, upward_candles_to_consider, True, downward_swing_current.new_low_candle.datetime, False)
                        if len(upward_swings) >= 1:
                            upward_swing_current = upward_swings[-1]
                            self.save_upward_swing_current = upward_swing_current

                            if self.save_upward_swing_current.new_high_candle:
                                downward_swings = self.find_downward_swings_from_high(self.track_all_candles_during_short, downward_candles_to_consider, True, upward_swing_current.new_high_candle.datetime, False)
                                if len(downward_swings) > 0:
                                    downward_swing = downward_swings[-1]
                                    if downward_swing.datetime != self.save_downward_swing_current.datetime:
                                        if self.save_downward_swing_previous:
                                            #self.save_downward_swing_previous.previous_swing_info = None
                                            self.save_downward_swing_current.previous_swing_info = self.save_downward_swing_previous
                                            self.save_downward_swing_previous = copy.deepcopy(self.save_downward_swing_current)
                                            self.save_downward_swing_current = downward_swing

                                        if self.save_upward_swing_previous and self.save_upward_swing_previous.datetime != self.save_upward_swing_current.datetime:
                                            #self.save_upward_swing_previous.previous_swing_info = None
                                            self.save_upward_swing_current.previous_swing_info = self.save_upward_swing_previous
                                            self.save_upward_swing_previous = copy.deepcopy(self.save_upward_swing_current)
                                            candles_clean_up_list = [candle for candle in self.track_all_candles_during_short if candle.datetime >= upward_swing_current.datetime]
                                            self.track_all_candles_during_short = candles_clean_up_list.copy()

                                        if not self.save_upward_swing_previous:
                                            self.save_upward_swing_previous = copy.deepcopy(self.save_upward_swing_current)
                                            candles_clean_up_list = [candle for candle in self.track_all_candles_during_short if candle.datetime >= upward_swing_current.datetime]
                                            self.track_all_candles_during_short = candles_clean_up_list.copy()


                        if self.save_upward_swing_previous and self.in_trade_candle:
                            if current_candle.close > self.save_upward_swing_previous.new_high_candle.close and current_candle.high > self.save_upward_swing_previous.new_high_candle.high:
                                self.save_upward_swing_previous.new_high_candle = current_candle
                            if self.save_upward_swing_previous.new_high_candle.datetime > self.in_trade_candle.datetime:
                                converting_to_short, pre_condition_short = self.is_non_extreme_internal_bearish_divergence(self.save_upward_swing_previous, current_candle)
                                if not pre_condition_short:
                                    converting_to_short, pre_condition_short = self.is_extreme_internal_swing_bearish_divergence_triggered(self.save_upward_swing_previous, current_candle)

                        if self.save_upward_swing_current and not pre_condition_short:
                            if current_candle.close > self.save_upward_swing_current.new_high_candle.close and current_candle.high > self.save_upward_swing_current.new_high_candle.high:
                                self.save_upward_swing_current.new_high_candle = current_candle
                            converting_to_short, pre_condition_short = self.is_non_extreme_internal_bearish_divergence(self.save_upward_swing_current, current_candle)
                            if not pre_condition_short:
                                converting_to_short, pre_condition_short = self.is_extreme_internal_swing_bearish_divergence_triggered(self.save_upward_swing_current, current_candle)

                        if not pre_condition_short and self.save_upward_swing_previous and self.save_upward_swing_current:
                            if self.save_upward_swing_previous.new_high_candle.close > self.save_upward_swing_current.new_high_candle.close:
                                if self.save_upward_swing_previous.new_high_candle.high > self.save_upward_swing_current.new_high_candle.high:
                                    if self.save_upward_swing_current.new_high_candle.rsi > self.save_upward_swing_previous.new_high_candle.rsi or self.save_upward_swing_current.new_high_candle.stoch_k > self.save_upward_swing_previous.new_high_candle.stoch_k or self.save_upward_swing_current.new_high_candle.stoch_d > self.save_upward_swing_previous.new_high_candle.stoch_d:
                                        pre_condition_short = True
                                        print(f"Date # {current_candle.date} :Pre-Condition  Bearish Internal Non-Extreme Divergence, when comparing current to previous swing, Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {self.save_upward_swing_previous.new_high_candle.date} , Origin RSI {self.save_upward_swing_previous.new_high_candle.rsi}, Origin STOCH_K  {self.save_upward_swing_previous.new_high_candle.stoch_k},  Origin STOCH_D  {self.save_upward_swing_previous.new_high_candle.stoch_d} , End Date {self.save_upward_swing_current.new_high_candle.date} , End RSI {self.save_upward_swing_current.new_high_candle.rsi}, End STOCH_K {self.save_upward_swing_current.new_high_candle.stoch_k}, End STOCH_D {self.save_upward_swing_current.new_high_candle.stoch_d}")

                    if converting_to_buy:
                        self.buy_triggered_candle_two = current_candle
                        converting_to_buy = False
                        print(f"Date # {current_candle.date} :First Divergence condition met for Buy and waiting for the next candle to close below current candle {current_candle}")
                        print(f"Date # {current_candle.date} :###################")

                    if self.buy_divergence_candle and not self.buy_divergence_candle.divergence_used:
                        if current_candle.close > self.buy_divergence_candle.close:
                            if current_candle.close > self.buy_divergence_candle.high:
                                self.buy_divergence_candle.divergence_used = True
                                converting_to_buy = True
                                print(f"Date # {current_candle.date} : The Manual Buy Divergence condition met for Buy and candles invloved current_candle {current_candle} and self.buy_divergence_candle {self.buy_divergence_candle}")

                    if self.buy_triggered_candle_two:
                        if current_candle.close > self.buy_triggered_candle_two.close:
                            if self.cover_stop_limit:
                                if current_candle.close > self.cover_stop_limit:
                                    converting_to_buy = True
                            else:
                                converting_to_buy = True
                            print(f"Date # {current_candle.date} :Second Condition Met for Buy and Divergence At Candle {current_candle} close below self.buy_triggered_candle_two {self.buy_triggered_candle_two}")
                        else:
                            converting_to_buy = False

                    if self.short_trending_candle:
                        if current_candle.close < self.short_trending_candle.close:
                            converting_to_buy = False
                            self.buy_triggered_candle_two = None

                    if self.short_stop_limit_candle:
                        if current_candle.close > self.short_stop_limit_candle.close:
                            if current_candle.close > self.short_stop_limit_candle.high:
                                converting_to_buy = True
                                print(f"Date # {current_candle.date} :The Short Trade is going and broker the Short Stop Candle and Converting to Buy Trade , The candles invloved current candle {current_candle} and self.short_stop_limit_candle {self.short_stop_limit_candle}")

                    if self.enable_trade_buying and not self.enable_trade_shorting:
                        if self.current_candle.previous_rsi < 5 and self.current_candle.rsi > 5:
                            self.buy_triggered_candle_two = current_candle
                            self.cover_stop_limit = None

                    #if self.save_downward_swing_current and self.save_downward_swing_previous:
                    if converting_to_buy:
                        cover_condition = True
                        short_condition = False
                        stop_loss = self.get_stop_loss(True)
                        buy_condition = True
                        self.update_converting_to_buy()


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
                    print('Date = ' + str(self.data.DATE[-1]) + ' stop_loss=' + str(stop_limit_price))
                    print('Date = ' + str(self.data.DATE[-1]) + ' Triggered Buy Order=' + str(self.buy_order))
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
                        print('Date = ' + str(self.data.DATE[-1]) + ' stop_loss=' + str(stop_limit_price))
                        print('Date = ' + str(self.data.DATE[-1]) + ' Triggered Short Order=' + str(self.short_order))
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
                            print('Date # {self.data.DATE[-1]} : Closed Buy Order')
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
                            print('Closed Short  Order')
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
    refresh_meta_tag = '<meta http-equiv="refresh" content="30">'

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

    print(sys.argv)
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
    enable_trade_buying = sys.argv[10].lower() == 'true'
    enable_trade_shorting = sys.argv[11].lower() == 'true'

    # symbol = '/ES'
    # start_date = '2025-04-06'
    # end_date = '2025-04-06'
    # start_time = '17:00'
    # end_time = '23:59'
    # lot_size = 50
    # stop_loss_adjust = 200
    # output_html ='sample.html'
    # interval = '1m'
    # enable_trade_buying = True
    # enable_trade_shorting = False

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
    adjusted_start_time_dt = start_time_dt - pd.Timedelta(hours=3)

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
    initial_df.index = initial_df.index.tz_localize(None)
    initial_df["RSI"] = talib.RSI(initial_df['Close'], 2)
    initial_df["RSI"] = initial_df["RSI"].round(2)
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
