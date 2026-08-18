import os
import re
import sys
import warnings
from colorsys import hls_to_rgb, rgb_to_hls
from itertools import cycle, combinations
from functools import partial
from typing import Callable, List, Union
import pandas_ta as ta
from scipy.signal import find_peaks

import numpy as np
import pandas as pd

from bokeh.colors import RGB
from bokeh.colors.named import (
    lime as BULL_COLOR,
    tomato as BEAR_COLOR
)
from bokeh.plotting import figure as _figure
from bokeh.models import (
    CrosshairTool,
    CustomJS,
    ColumnDataSource,
    NumeralTickFormatter,
    Span,
    HoverTool,
    Range1d,
    DatetimeTickFormatter,
    WheelZoomTool,
    LinearColorMapper,
    LinearAxis,
    Range1d,
    LabelSet,
    CategoricalColorMapper
)
try:
    from bokeh.models import CustomJSTickFormatter
except ImportError:  # Bokeh < 3.0
    from bokeh.models import FuncTickFormatter as CustomJSTickFormatter
from bokeh.io import output_notebook, output_file, show
from bokeh.io.state import curstate
from bokeh.layouts import gridplot
from bokeh.palettes import Category10
from bokeh.transform import factor_cmap

from backtesting._util import _data_period, _as_list, _Indicator

with open(os.path.join(os.path.dirname(__file__), 'autoscale_cb.js'),
          encoding='utf-8') as _f:
    _AUTOSCALE_JS_CALLBACK = _f.read()

IS_JUPYTER_NOTEBOOK = 'JPY_PARENT_PID' in os.environ

if IS_JUPYTER_NOTEBOOK:
    warnings.warn('Jupyter Notebook detected. '
                  'Setting Bokeh output to notebook. '
                  'This may not work in Jupyter clients without JavaScript '
                  'support (e.g. PyCharm, Spyder IDE). '
                  'Reset with `backtesting.set_bokeh_output(notebook=False)`.')
    output_notebook()


class SwingInfo:
    def __init__(self, start_index, end_index, swing_high_price, swing_low_price,
                 swing_high_close, swing_low_close, swing_high_rsi, swing_low_rsi, swing_type):
        self.start_index = start_index
        self.end_index = end_index
        self.swing_high_price = swing_high_price
        self.swing_low_price = swing_low_price
        self.swing_high_close = swing_high_close
        self.swing_low_close = swing_low_close
        self.swing_high_rsi = swing_high_rsi
        self.swing_low_rsi = swing_low_rsi
        self.swing_type = swing_type  # 1 for Upward, -1 for Downward
        self.flat = False  # Default flat swing flag

def create_swings_using_zig_zag_indicator(initial_df):
    swing_info_list = []
    zigzag_df = initial_df.copy()
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


# def create_swings_using_zig_zag_indicator(initial_df, reversal_amount=1.0):
#     reversal_amount = reversal_amount / 100
#     swing_info_list = []
#     zigzag_df = initial_df.copy()
#
#     close = zigzag_df['Close']  # Use Close price instead of High/Low
#
#     last_extreme = None
#     start_index = zigzag_df.index[0]
#     current_trend = None
#
#     for idx in range(1, len(zigzag_df) - 1):
#         prev_idx, next_idx = idx - 1, idx + 1
#         current_index = zigzag_df.index[idx]
#
#         # Identify High Swing Point based on Close price
#         if close.iloc[idx] > close.iloc[prev_idx] and close.iloc[idx] > close.iloc[next_idx]:
#             if last_extreme is None or (close.iloc[idx] - last_extreme) >= reversal_amount:
#                 if current_trend == "Down":  # Store previous downward swing
#                     swing_info_list.append(SwingInfo(
#                         start_index=start_index,
#                         end_index=current_index,
#                         swing_high_price=zigzag_df.loc[start_index, "Close"],
#                         swing_low_price=zigzag_df.loc[current_index, "Close"],
#                         swing_high_close=zigzag_df.loc[start_index, "Close"],
#                         swing_low_close=zigzag_df.loc[current_index, "Close"],
#                         swing_high_rsi=zigzag_df.loc[start_index, "RSI"],
#                         swing_low_rsi=zigzag_df.loc[current_index, "RSI"],
#                         swing_type=1  # Upward Swing
#                     ))
#                 last_extreme = close.iloc[idx]
#                 start_index = current_index
#                 current_trend = "Up"
#
#         # Identify Low Swing Point based on Close price
#         elif close.iloc[idx] < close.iloc[prev_idx] and close.iloc[idx] < close.iloc[next_idx]:
#             if last_extreme is None or (last_extreme - close.iloc[idx]) >= reversal_amount:
#                 if current_trend == "Up":  # Store previous upward swing
#                     swing_info_list.append(SwingInfo(
#                         start_index=start_index,
#                         end_index=current_index,
#                         swing_high_price=zigzag_df.loc[start_index, "Close"],
#                         swing_low_price=zigzag_df.loc[current_index, "Close"],
#                         swing_high_close=zigzag_df.loc[start_index, "Close"],
#                         swing_low_close=zigzag_df.loc[current_index, "Close"],
#                         swing_high_rsi=zigzag_df.loc[start_index, "RSI"],
#                         swing_low_rsi=zigzag_df.loc[current_index, "RSI"],
#                         swing_type=-1  # Downward Swing
#                     ))
#                 last_extreme = close.iloc[idx]
#                 start_index = current_index
#                 current_trend = "Down"
#
#     return swing_info_list

def create_swings_using_zig_zag_indicator_10_legs(initial_df):
    swing_info_list = []
    zigzag_df = initial_df.copy()
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
    return swing_info_list

def mark_flat_swings(swings, threshold_pct):
    start_index = None

    for i in range(len(swings) - 1):
        # print(swings[i])
        # print(swings[i + 1])

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

from bokeh.models import ColumnDataSource

def plot_zig_zag_swings(plot, df, swing_collection_10, swing_collection_3, divergence_swing_collection):
    """Draw separate lines for 10-leg, 3-leg, and divergence swings, highlighting flat swings."""


    # Define dictionaries to store line data
    swing_lines_10 = {"x_start": [], "x_end": [], "y_start": [], "y_end": []}
    swing_lines_3 = {"x_start": [], "x_end": [], "y_start": [], "y_end": []}
    divergence_swing_lines = {"x_start": [], "x_end": [], "y_start": [], "y_end": []}
    flat_swing_lines = {"x_start": [], "x_end": [], "y_start": [], "y_end": []}

    # Define Colors
    COLOR_10_LEGS = "lightblue"
    COLOR_3_LEGS = "yellow"
    COLOR_DIVERGENCE_SWING = "orange"
    COLOR_FLAT_SWING = "white"  # Flat swings in white (dashed)

    def process_swings(swing_collection, line_dict, flat_line_dict, df):
        # ✅ Check if df uses a DateTimeIndex
        use_datetime = isinstance(df.index, pd.DatetimeIndex)

        for swing in swing_collection:
            start_idx = swing.start_index
            end_idx = swing.end_index

            # ✅ Convert timestamp to numeric index for Zigzag Swings
            try:
                if use_datetime:
                    # ✅ If DataFrame uses a DatetimeIndex, convert timestamps
                    start_idx = df.index.get_loc(pd.Timestamp(start_idx))
                    end_idx = df.index.get_loc(pd.Timestamp(end_idx))
                else:
                    # ✅ If it's already numeric (RangeIndex), no conversion needed
                    if isinstance(start_idx, pd.Timestamp):
                        start_idx = df.index[df["datetime"] == start_idx].tolist()
                        start_idx = start_idx[0] if start_idx else df.index[df["datetime"].sub(start_idx).abs().idxmin()]

                    if isinstance(end_idx, pd.Timestamp):
                        end_idx = df.index[df["datetime"] == end_idx].tolist()
                        end_idx = end_idx[0] if end_idx else df.index[df["datetime"].sub(end_idx).abs().idxmin()]

            except Exception as e:
                print(f"Error processing swing {start_idx} - {end_idx}: {e}")
                continue  # Skip problematic swings

            # Ensure correct price mapping based on swing type
            if swing.swing_type == 1:  # Upward swing
                start_price = swing.swing_low_price
                end_price = swing.swing_high_price
            else:  # Downward swing
                start_price = swing.swing_high_price
                end_price = swing.swing_low_price

            # Normal swing plotting
            line_dict["x_start"].append(start_idx)
            line_dict["x_end"].append(end_idx)
            line_dict["y_start"].append(start_price)
            line_dict["y_end"].append(end_price)

            # If it's a flat swing, also add to flat_swing_lines
            if swing.flat:
                flat_line_dict["x_start"].append(start_idx)
                flat_line_dict["x_end"].append(end_idx)
                flat_line_dict["y_start"].append(start_price)
                flat_line_dict["y_end"].append(end_price)



    # Process swings
    process_swings(swing_collection_10, swing_lines_10, flat_swing_lines, df)
    process_swings(swing_collection_3, swing_lines_3, flat_swing_lines, df)
    process_swings(divergence_swing_collection, divergence_swing_lines, flat_swing_lines, df)  # New divergence swings

    # Convert to ColumnDataSource
    swing_source_10 = ColumnDataSource(swing_lines_10)
    swing_source_3 = ColumnDataSource(swing_lines_3)
    divergence_swing_source = ColumnDataSource(divergence_swing_lines)
    flat_swing_source = ColumnDataSource(flat_swing_lines)

    # Draw 10-leg swings (Blue Line)
    plot.segment(
        x0="x_start",
        x1="x_end",
        y0="y_start",
        y1="y_end",
        source=swing_source_10,
        line_width=2,
        line_color=COLOR_10_LEGS,
        line_dash="solid",
        legend_label="ZigZag 10 Legs"
    )

    # Draw 3-leg swings (Yellow Line)
    plot.segment(
        x0="x_start",
        x1="x_end",
        y0="y_start",
        y1="y_end",
        source=swing_source_3,
        line_width=2,
        line_color=COLOR_3_LEGS,
        line_dash="solid",
        legend_label="ZigZag 3 Legs"
    )

    # Draw Divergence Swings (Orange Line)
    # plot.segment(
    #     x0="x_start",
    #     x1="x_end",
    #     y0="y_start",
    #     y1="y_end",
    #     source=divergence_swing_source,
    #     line_width=2,
    #     line_color=COLOR_DIVERGENCE_SWING,
    #     line_dash="solid",
    #     legend_label="Divergence Swings"
    # )

    # Draw Flat Swings (Dashed White Line)
    plot.segment(
        x0="x_start",
        x1="x_end",
        y0="y_start",
        y1="y_end",
        source=flat_swing_source,
        line_width=4,
        line_color=COLOR_FLAT_SWING,
        line_dash="dashed",
        legend_label="Flat Swings"
    )

def plot_scipy_signal(plot, df):
    """
    Plot peaks and valleys detected by scipy.signal and connect them with a light orange line.
    """

    # Process all OHLC candles for peaks and valleys
    prices = df['Close'].values
    peaks, _ = find_peaks(prices, distance=3)  # Detect peaks
    valleys, _ = find_peaks(-prices, distance=3)  # Detect valleys
    turning_points = np.sort(np.concatenate((peaks, valleys)))  # Combine and sort peaks/valleys

    # Define dictionary for the line connecting peaks and valleys
    signal_lines = {"x": [], "y": []}

    # Process turning points (peaks and valleys)
    for idx in turning_points:
        signal_lines["x"].append(df.index[idx])  # Timestamp or index for x-axis
        signal_lines["y"].append(prices[idx])   # Price for y-axis

    # Convert to ColumnDataSource
    signal_source = ColumnDataSource(signal_lines)

    # Define color for the connecting line (Light Orange)
    COLOR_SIGNAL_LINE = "#FFA07A"  # Light orange hex code

    # Draw the connecting line in light orange
    plot.line(
        x="x",
        y="y",
        source=signal_source,
        line_width=2,
        line_color=COLOR_SIGNAL_LINE,
        legend_label="Signal Line"
    )

def plot_scipy_signal_10(plot, df):
    """
    Plot peaks and valleys detected by scipy.signal and connect them with a light orange line.
    """

    # Process all OHLC candles for peaks and valleys
    prices = df['Close'].values
    peaks, _ = find_peaks(prices, distance=10)  # Detect peaks
    valleys, _ = find_peaks(-prices, distance=10)  # Detect valleys
    turning_points = np.sort(np.concatenate((peaks, valleys)))  # Combine and sort peaks/valleys

    # Define dictionary for the line connecting peaks and valleys
    signal_lines = {"x": [], "y": []}

    # Process turning points (peaks and valleys)
    for idx in turning_points:
        signal_lines["x"].append(df.index[idx])  # Timestamp or index for x-axis
        signal_lines["y"].append(prices[idx])   # Price for y-axis

    # Convert to ColumnDataSource
    signal_source = ColumnDataSource(signal_lines)

    # Define color for the connecting line (Light Orange)
    COLOR_SIGNAL_LINE = "white"  # Light orange hex code

    # Draw the connecting line in light orange
    plot.line(
        x="x",
        y="y",
        source=signal_source,
        line_width=2,
        line_color=COLOR_SIGNAL_LINE,
        legend_label="Signal Line"
    )

# Function to assign Elliot Wave numbers based on ZIGZAGv_0.01%_3
# Function to assign Elliot Wave numbers based on ZIGZAGv_0.01%_3
def assign_wave_numbers(df,zigzag_column,dataframe_name,interval):

    # # Function to assign waves for an uptrend
    def assign_uptrend_waves(start_idx, prev_idx):
        wave_numbers = [None] * len(df)
        wave_numbers[start_idx] = 'Wave 1'  # First point is Wave 1

        current_wave = 1
        start_value = df[zigzag_column].iloc[start_idx]
        print_verbose(f"UpTrend Wave 1: {start_value}")
        # print_verbose(df[zigzag_column].iloc[start_idx-1])
        for i in range(start_idx + 1, len(df)):
            if current_wave == 1:
                # Wave 2: Correction: 2 Conditions : 1.Fib Retracement 2. Pattern Formation
                current_value = df[zigzag_column].iloc[i]
                print_verbose(f"Current Value, {current_value}")
                previous_value = df[zigzag_column].iloc[start_idx-1]
                print_verbose(f"Previous Value, {previous_value}")

                #Condition 1: Pattern Formation (Existing logic)
                # if df[zigzag_column].iloc[i] <= start_value and df[zigzag_column].iloc[start_idx-1] <= df[zigzag_column].iloc[i]:
                if current_value <= start_value and previous_value <= current_value:
                    # Calculate Fibonacci Retracement Levels
                    # Wave 2 Retracement: Typically between 38.2% to 61.8% of Wave 1.
                    # Wave 4 Retracement: Typically between 14.6% to 38.2% of Wave 3.
                    # Wave 3 Extension: Typically between 161.8% and 261.8% of Wave 1.
                    # Wave 5 is typically inverse 1.236 – 1.618% of wave 4, equal to wave 1 or 61.8% of wave 1+3
                    print_verbose(f"start_value , {start_value}")
                    print_verbose(f"previous_value, {previous_value}")
                    # Calculate Fibonacci Retracement Levels using `start_value` and `previous_value` (local low)
                    #Ex: Previous Value, 100.0 , start_value , 161.8
                    fib_levels = {
                        '38.2%': start_value - (start_value - previous_value) * 0.382,
                        '85.1%': start_value - (start_value - previous_value) * 0.851
                    }
                    print_verbose(fib_levels)

                    # Check if the current value is within the Fibonacci range (38.2% to 85.1% for correction)
                    #Ex: S.P: 5922.25, E.P: 5934.75, 38.2% level: 5930.00, 85.1% level: 5924.11, current value: 5928.75
                    # 5924.11 ≤ current value ≤5930.00
                    if fib_levels['85.1%'] <= current_value <= fib_levels['38.2%']:
                        print_verbose(f"Wave 2 Fibonacci condition met: {current_value} at index {i}, Both Condition meet, it should be shown in Dark Green Color")
                        wave_numbers[i] = 'Wave 2.1'
                        current_wave = 2.1  # Move to the next wave
                    else:
                        print_verbose(f"Wave 2 Fibonacci condition failed at index {i} Only Pattern Matching Condition Met.")
                        print_verbose(f"Still Assigning Wave as 2, but it will shown as green faint color, as it Completed 1 condition out of 2.")
                        wave_numbers[i] = 'Wave 2.2'
                        current_wave = 2.2  # Move to the next wave
                        # wave_numbers[start_idx] = None  # Reset Wave 1
                        # wave_numbers[i] = None  # Reset Wave 2
                        # break
                else:
                    print_verbose(f"UpTrend Wave 2 Pattern & Fib condition failed,at index {i}. Resetting Wave 1,2.")
                    wave_numbers[start_idx] = None  # Reset Wave 1
                    wave_numbers[i] = None  # Reset Wave 2
                    wave_numbers = []
                    break

            elif current_wave == 2.1 or current_wave == 2.2:
                wave_3_i2_flag_up = False
                # Wave 3: Impulse (greater than Wave 1)
                if df[zigzag_column].iloc[i] > start_value:
                    # Calculate Fibonacci Extensions for Wave 3 using Wave 1 and Wave 2
                    wave_1_length = start_value - previous_value  # Length of Wave 1
                    print_verbose(start_value,previous_value, wave_1_length)
                    current_value = df[zigzag_column].iloc[i]
                    print_verbose(f"Current Value: {current_value}")
                    #start_value is the end of Wave 1
                    fib_levels_wave_3 = {
                        '161.8%': start_value + (wave_1_length * 1.618),  # 161.8% extension of Wave 1
                        '261.8%': start_value + (wave_1_length * 2.618)   # 261.8% extension of Wave 1
                    }
                    print_verbose(f"Wave 3 Fibonacci extension levels: {fib_levels_wave_3}")
                    # Check if the current value is within the Fibonacci range (161.8% to 261.8% for)
                    if fib_levels_wave_3['161.8%'] <= current_value <= fib_levels_wave_3['261.8%']:
                        print_verbose(f"Wave 3 Fibonacci condition met: {current_value} at index {i}, Both Condition meet, it should be shown in Dark Green Color")
                        wave_numbers[i] = 'Wave 3.1'
                        current_wave = 3.1  # Move to the next wave
                    else:
                        print_verbose(f"Wave 3 Fibonacci condition failed at index {i} Only Pattern Matching Condition Met.")
                        print_verbose(f"Still Assigning Wave as 3, but it will shown as green faint color, as it Completed 1 condition out of 2.")
                        wave_numbers[i] = 'Wave 3.2'
                        current_wave = 3.2  # Move to the next wave
                else:
                    # If condition fails, we check the next point by incrementing the index by 2 and re-evaluating the conditions
                    print_verbose(f"UpTrend Wave 3 condition failed at index {i}. Trying the next point for Wave 3.")
                    i += 2  # Increment by 2 # Move the index by 2 to skip the current point and proceed to the next
                    if i < len(df): # Recheck the condition for the next point
                        # Re-evaluate the condition at the new index
                        if df[zigzag_column].iloc[i] > start_value and df[zigzag_column].iloc[i-1] >  previous_value: # 2nd condition to make sure pattern remain intact
                            # Perform your Fibonacci extensions and checks here again for the new index
                            wave_1_length = start_value - previous_value  # Length of Wave 1
                            print_verbose(start_value, previous_value, wave_1_length)
                            current_value = df[zigzag_column].iloc[i]
                            print_verbose(f"Rechecking for Wave 3 at new index {i}, Current Value: {current_value}")
                            fib_levels_wave_3 = {
                                '161.8%': start_value + (wave_1_length * 1.618),  # 161.8% extension of Wave 1
                                '261.8%': start_value + (wave_1_length * 2.618)   # 261.8% extension of Wave 1
                            }
                            print_verbose(f"Rechecking Wave 3 Fibonacci extension levels: {fib_levels_wave_3}")
                            wave_3_i2_flag_up = True
                            if fib_levels_wave_3['161.8%'] <= current_value <= fib_levels_wave_3['261.8%']:
                                print_verbose(f"Wave 3 Fibonacci condition met at new index {i}.")
                                wave_numbers[i] = 'Wave 3.1'
                                current_wave = 3.1  # Move to the next wave
                            else:
                                print_verbose(f"Wave 3 condition meet at new index {i}.")
                                wave_numbers[i] = 'Wave 3.2'
                                current_wave = 3.2  # Move to the next wave
                            #Now Assign Correct Label to Wave 2 for DownTrend Whicheven Wave is Higher, Compare i-1 & i-3 and assigne Wave 2 whichver wave is higher value
                            if df[zigzag_column].iloc[i-1] <= df[zigzag_column].iloc[i-3]:
                                for i in range(len(wave_numbers) - 1, -1, -1):  # Iterate backwards
                                    if wave_numbers[i] in ["Wave 2.1", "Wave 2.2"]:
                                        if i + 2 < len(wave_numbers) and wave_numbers[i + 2] is None:  # Ensure valid shift
                                            wave_numbers[i + 2] = wave_numbers[i]  # Move to i+2
                                            wave_numbers[i] = None  # Clear original index
                        else:
                            # If the condition for Wave 2 fails, reset Wave 1 and Wave 2 and start from next point
                            print_verbose(f"Wave 3 UpTrend condition failed at index {i}. Resetting Wave 1,2.")
                            wave_numbers = []
                            break
                    else:
                        print_verbose(f"Uptrend Wave 2 i+2 condition failed and out of range at index {i}, stopping evaluation.")
                        wave_numbers = [] # Clear the list to reset the waves
                        break

            elif current_wave == 3.1 or current_wave == 3.2:
                # Wave 4: Correction (back down)
                # if df[zigzag_column].iloc[i] >= start_value and wave_3_i2_flag_up == False:
                wave_4_i2_flag_up = False
                if df[zigzag_column].iloc[i] >= df[zigzag_column].iloc[start_idx + 1] and wave_3_i2_flag_up == False:
                    end_wave_3 = df[zigzag_column].iloc[i-1]
                    print_verbose(f"end_wave_3 Value , {end_wave_3}")
                    print_verbose(f"Wave 1 Lengths for Wave 4 Calculation , {wave_1_length}")
                    current_value = df[zigzag_column].iloc[i]
                    print_verbose(f"Current Value, {current_value}")
                    #start_value is the end of Wave 1 >> Retracement Level=End of Wave 3−(Wave 3 Length×Retracement Ratio)
                    fib_levels_wave_4 = {
                        '14.6%': end_wave_3 - (wave_1_length * 0.146),  # 14.6% Retracement of Wave 3
                        '78.2%': end_wave_3 - (wave_1_length * 0.782)   # 38.2% Retracement of Wave 3 #38.2% changed to 78.2%
                    }
                    print_verbose(f"Wave 4 Fibonacci extension levels: {fib_levels_wave_4}")
                    # Check if the current value is within the Fibonacci range (14.6% to 38.2% for correction)
                    #Ex: 14.6% level: 5963.7445, 38.2% level: 5963.3315
                    if fib_levels_wave_4['78.2%'] <= current_value <= fib_levels_wave_4['14.6%']:
                        print_verbose(f"Wave 4 Fibonacci condition met: {current_value} at index {i}, Both Condition meet, it should be shown in Dark Green Color")
                        wave_numbers[i] = 'Wave 4.1'
                        current_wave = 4.1  # Move to the next wave
                    else:
                        print_verbose(f"Wave 4 Fibonacci condition failed at index {i} Only Pattern Matching Condition Met.")
                        print_verbose(f"Still Assigning Wave as 4, but it will shown as green faint color, as it Completed 1 condition out of 2.")
                        wave_numbers[i] = 'Wave 4.2'
                        current_wave = 4.2  # Move to the next wave
                else:
                    # If condition fails, we check the next point by incrementing the index by 2 and re-evaluating the conditions
                    print_verbose(f"UpTrend Wave 4 condition failed at index {i}. Trying the next point for Wave 4.")
                    # Move the index by 2 to skip the current point and proceed to the next
                    i += 2  # Increment by 2
                    # wave_4_i2_flag_up = False
                    if i < len(df): # Recheck the condition for the next point
                        # if df[zigzag_column].iloc[i] >= start_value and wave_3_i2_flag_up == True:
                        if df[zigzag_column].iloc[i] >= df[zigzag_column].iloc[start_idx + 1] and wave_3_i2_flag_up == True:
                            end_wave_3 = df[zigzag_column].iloc[i-1]
                            print_verbose(f"end_wave_3 Value , {end_wave_3}")
                            print_verbose(f"Wave 1 Lengths for Wave 4 Calculation , {wave_1_length}")
                            current_value = df[zigzag_column].iloc[i]
                            print_verbose(f"Current Value, {current_value}")
                            #start_value is the end of Wave 1 >> Retracement Level=End of Wave 3−(Wave 3 Length×Retracement Ratio)
                            fib_levels_wave_4 = {
                                '14.6%': end_wave_3 - (wave_1_length * 0.146),  # 14.6% Retracement of Wave 3
                                '78.6%': end_wave_3 - (wave_1_length * 0.786)   # 38.2% Retracement of Wave 3 # From 38.2 change it to 78.6%
                            }
                            wave_4_i2_flag_up = True
                            print_verbose(f"Wave 4 Fibonacci extension levels: {fib_levels_wave_4}")
                            # Check if the current value is within the Fibonacci range (14.6% to 38.2% for correction)
                            #Ex: 14.6% level: 5963.7445, 38.2% level: 5963.3315
                            if fib_levels_wave_4['78.6%'] <= current_value <= fib_levels_wave_4['14.6%']:
                                print_verbose(f"Wave 4 i+2 Fib condition met: {current_value} at index {i}, Both Condition meet, it should be shown in Dark Green Color")
                                wave_numbers[i] = 'Wave 4.1'
                                current_wave = 4.1  # Move to the next wave
                            else:
                                print_verbose(f"Wave 4 i+2 Fib condition failed at index {i} Only Pattern Matching Condition Met.")
                                print_verbose(f"Still Assigning Wave as 4, but it will shown as green faint color, as it Completed 1 condition out of 2.")
                                # Check index before updating
                                print_verbose(f"Before updating: wave_numbers[{i}] = {wave_numbers[i]}")
                                wave_numbers[i] = 'Wave 4.2'
                                current_wave = 4.2  # Move to the next wave
                                print_verbose(f"wave_numbers updated at index {i}: {wave_numbers[i]}")
                        else:
                            # If the condition for Wave 4 fails, reset Wave 1 and Wave 2, 3 to None
                            print_verbose(f"UpTrend Wave 4 condition failed at index {i}. Resetting Wave 1,2,3.")
                            wave_numbers[start_idx] = None  # Reset Wave 1
                            wave_numbers[i-1] = None  # Reset Wave 2
                            wave_numbers[i-2] = None  # Reset Wave 3
                            wave_numbers = []
                            # current_wave = 1  # Reset to Wave 1 and continue from this index
                            break
                    else:
                        print_verbose(f"Wave 3 UpTrend i+2 condition failed and out of range at index {i}, stopping evaluation.")
                        wave_numbers = [] # Clear the list to reset the waves
                        break

            elif current_wave == 4.1 or current_wave == 4.2:
                wave_5_i2_flag_up = False
                wave_5_i4_flag_up = False
                # Wave 5: Impulse (greater than Wave 3): # Wave 5 is typically inverse 1.236 – 1.618% of wave 4, equal to wave 1 or 61.8% of wave 1+3
                if df[zigzag_column].iloc[i] > df[zigzag_column].iloc[i-2] and wave_4_i2_flag_up == False:
                    end_wave_4 = df[zigzag_column].iloc[i-1]
                    print_verbose(f"end_wave_4 Value , {end_wave_4}")
                    print_verbose(f"Wave 1 Length for Wave 5 Calculation , {wave_1_length}")
                    wave4_length = end_wave_3 - end_wave_4
                    print_verbose(f"Wave 4 Length for Wave 5 Calculation , {wave4_length}")
                    current_value = df[zigzag_column].iloc[i]
                    print_verbose(f"Current Value: {current_value}")
                    #Conditions of Fib 5:
                    #1. Wave 5 = End of Wave 4 + (Wave 4 length × Fibonacci extension ratios such as 1.236, 1.618)
                    #2. Wave 5 = End of Wave 4 + Wave 1 length.
                    #3. Wave 5 = End of Wave 4 + 61.8% of the combined length of Wave 1 and Wave 3.
                    # Check if the current value is within the Fibonacci range (38.2% to 61.8% for correction)
                    fib_levels_wave_5 = {
                        '123.6%': end_wave_4 + (wave4_length * 1.236),  # 14.6% Retracement of Wave 3
                        '161.8%': end_wave_4 + (wave4_length * 1.618)   # 38.2% Retracement of Wave 3
                    }
                    print_verbose(f"UpTrend Wave 5 Fibonacci extension levels: {fib_levels_wave_5}")
                    fib_levels_wave_5_condition_2 = end_wave_4 + wave_1_length
                    print_verbose(f"UpTrend Wave 5 Fib condition:2, {fib_levels_wave_5_condition_2}")

                    if fib_levels_wave_5['123.6%'] <= current_value <= fib_levels_wave_5['161.8%']:
                        print_verbose(f"UpTrend Wave 5 Fibonacci condition:1 met range between 123.6% & 161.8%,: {current_value} at index {i}, Both Condition meet, it should be shown in Dark Green Color")
                        wave_numbers[i] = 'Wave 5.1'
                        current_wave = 5.1  # Move to the next wave
                    else:
                        print_verbose(f"Wave 5 Fibonacci condition failed at index {i} Only Pattern Matching Condition Met.")
                        print_verbose(f"Still Assigning Wave as 5, but it will shown as green faint color, as it Completed 1 condition out of 2.")
                        wave_numbers[i] = 'Wave 5.2'
                        current_wave = 5.2  # Move to the next wave
                else:
                    # If condition fails, we check the next point by incrementing the index by 2 and re-evaluating the conditions
                    print_verbose(f"UpTrend Wave 5 condition failed at index {i}. Trying the next point for Wave 5.")
                    # Move the index by 2 to skip the current point and proceed to the next
                    i += 2  # Increment by 2
                    if i+2 < len(df) and df[zigzag_column].iloc[i] > df[zigzag_column].iloc[i-2] and wave_4_i2_flag_up == True:
                        print_verbose(df[zigzag_column].iloc[i], df[zigzag_column].iloc[i-2])  #For i +=2, i-2 will be Wave 3
                        print_verbose(f"UpTrend Wave 5 condition failed at index {i}. Trying the next point for Wave 5.")
                        end_wave_4 = df[zigzag_column].iloc[i-1]
                        print_verbose(f"end_wave_4 Value , {end_wave_4}")
                        print_verbose(f"Wave 1 Length for Wave 5 Calculation , {wave_1_length}")
                        wave4_length = end_wave_3 - end_wave_4
                        print_verbose(f"Wave 4 Length for Wave 5 Calculation , {wave4_length}")
                        current_value = df[zigzag_column].iloc[i]
                        print_verbose(f"Current Value: {current_value}")
                        #Conditions of Fib 5:
                        #1. Wave 5 = End of Wave 4 + (Wave 4 length × Fibonacci extension ratios such as 1.236, 1.618)
                        #2. Wave 5 = End of Wave 4 + Wave 1 length.
                        #3. Wave 5 = End of Wave 4 + 61.8% of the combined length of Wave 1 and Wave 3.
                        # Check if the current value is within the Fibonacci range (38.2% to 61.8% for correction)

                        fib_levels_wave_5 = {
                            '123.6%': end_wave_4 + (wave4_length * 1.236),  # 14.6% Retracement of Wave 3
                            '161.8%': end_wave_4 + (wave4_length * 1.618)   # 38.2% Retracement of Wave 3
                        }
                        wave_5_i2_flag_up = True
                        print_verbose(f"UpTrend Wave 5 Fibonacci extension levels: {fib_levels_wave_5}")
                        fib_levels_wave_5_condition_2 = end_wave_4 + wave_1_length
                        print_verbose(f"UpTrend Wave 5 Fib condition:2, {fib_levels_wave_5_condition_2}")

                        if fib_levels_wave_5['123.6%'] <= current_value <= fib_levels_wave_5['161.8%']:
                            print_verbose(f"UpTrend Wave 5 (i+2) Fibonacci condition:1 met range between 123.6% & 161.8%,: {current_value} at index {i}, Both Condition meet, it should be shown in Dark Green Color")
                            wave_numbers[i] = 'Wave 5.1'
                            current_wave = 5.1  # Move to the next wave
                        else:
                            print_verbose(f"Wave 5 (i+2) Fibonacci condition failed at index {i} Only Pattern Matching Condition Met.")
                            print_verbose(f"Still Assigning Wave as 5, but it will shown as green faint color, as it Completed 1 condition out of 2.")
                            wave_numbers[i] = 'Wave 5.2'
                            current_wave = 5.2  # Move to the next wave

                        # # #Now Assign Correct Label to Wave 2 for DownTrend Whicheven Wave is Higher, Compare i-1 & i-3 and assigne Wave 2 whichver wave is higher value
                        # if df[zigzag_column].iloc[i-1] >= df[zigzag_column].iloc[i-3]:
                        #     for i in range(len(wave_numbers) - 1, -1, -1):  # Iterate backwards
                        #         if wave_numbers[i] in ["Wave 4.1", "Wave 4.2"]:
                        #             if i + 2 < len(wave_numbers) and wave_numbers[i + 2] is None:  # Ensure valid shift
                        #                 wave_numbers[i + 2] = wave_numbers[i]  # Move to i+2
                        #                 wave_numbers[i] = None  # Clear original index

                        # Compare i-1 & i-3 and assign Wave 2 to whichever wave is higher in value # Now Assign Correct Label to Wave 4 for DownTrend (Whichever Wave is Higher)
                        # if df[zigzag_column].iloc[i-1] >= df[zigzag_column].iloc[i-3]:
                        #     for i in range(len(wave_numbers) - 1, -1, -1):  # Iterate backwards
                        #         # Check if current wave is 'Wave 4.1' or 'Wave 4.2'
                        #         if wave_numbers[i] in ["Wave 4.1", "Wave 4.2"]:
                        #             # Check if 'Wave 5.1' or 'Wave 5.2' appears before 'Wave 4.1' or 'Wave 4.2'
                        #             if any(wave in wave_numbers[:i] for wave in ["Wave 5.1", "Wave 5.2"]):
                        #                 # Ensure valid shift, check if we can move the wave to i+2 (next available index)
                        #                 if i + 2 < len(wave_numbers) and wave_numbers[i + 2] is None:
                        #                     wave_numbers[i + 2] = wave_numbers[i]  # Move to i+2
                        #                     wave_numbers[i] = None  # Clear original index

                    ### This condition is for i+2 3rd Wave and i+2 5th Wave
                    elif i+2 < len(df) and df[zigzag_column].iloc[i+2] > df[zigzag_column].iloc[i-2] and wave_4_i2_flag_up == True:  #For i +=4, i+2 is Wave 5 , as we already incremented i+2 , i-4 will be Wave 3
                        print_verbose(f"UpTrend Wave 5 condition failed at index i+2 {i+2}. Trying the next point for Wave 5.")
                        print_verbose(df[zigzag_column].iloc[i+2], df[zigzag_column].iloc[i-2])
                        end_wave_4 = min(df['ZIGZAGv_0.01%_3'].iloc[i - 1],df['ZIGZAGv_0.01%_3'].iloc[i + 1]) #, df['ZIGZAGv_0.01%_3'].iloc[i - 3]
                        print_verbose(f"end_wave_4 Value , {end_wave_4}")
                        print_verbose(f"Wave 1 Length for Wave 5 Calculation , {wave_1_length}")
                        wave4_length = end_wave_3 - end_wave_4
                        print_verbose(f"Wave 4 Length for Wave 5 Calculation , {wave4_length}")
                        current_value = df[zigzag_column].iloc[i+2]
                        print_verbose(f"Current Value: {current_value}")
                        #Conditions of Fib 5:
                        #1. Wave 5 = End of Wave 4 + (Wave 4 length × Fibonacci extension ratios such as 1.236, 1.618)
                        #2. Wave 5 = End of Wave 4 + Wave 1 length.
                        #3. Wave 5 = End of Wave 4 + 61.8% of the combined length of Wave 1 and Wave 3.
                        # Check if the current value is within the Fibonacci range (38.2% to 61.8% for correction)
                        fib_levels_wave_5 = {
                            '123.6%': end_wave_4 + (wave4_length * 1.236),  # 14.6% Retracement of Wave 3
                            '161.8%': end_wave_4 + (wave4_length * 1.618)   # 38.2% Retracement of Wave 3
                        }
                        wave_5_i4_flag_up = True
                        print_verbose(f"UpTrend Wave 5 Fibonacci extension levels: {fib_levels_wave_5}")
                        fib_levels_wave_5_condition_2 = end_wave_4 + wave_1_length
                        print_verbose(f"UpTrend Wave 5 Fib condition:2, {fib_levels_wave_5_condition_2}")
                        if fib_levels_wave_5['123.6%'] <= current_value <= fib_levels_wave_5['161.8%']:
                            print_verbose(f"UpTrend Wave 5 (i+4) Fibonacci condition:1 met range between 123.6% & 161.8%,: {current_value} at index {i}, Both Condition meet, it should be shown in Dark Green Color")
                            wave_numbers[i+2] = 'Wave 5.1' #As we are checking for i+4 value
                            current_wave = 5.1  # Move to the next wave
                        else:
                            print_verbose(f"Wave 5 (i+4) Fibonacci condition failed at index {i} Only Pattern Matching Condition Met.")
                            print_verbose(f"Still Assigning Wave as 5, but it will shown as green faint color, as it Completed 1 condition out of 2.")
                            wave_numbers[i+2] = 'Wave 5.2' #As we are checking for i+4 value
                            current_wave = 5.2  # Move to the next wave
                        #Now Assign Correct Label to Wave 2 for DownTrend Whicheven Wave is Higher, Compare i-1 & i-3 and assigne Wave 2 whichver wave is higher value
                        if df[zigzag_column].iloc[i+1] >= df[zigzag_column].iloc[i-1]: #For i+4 condition
                            for i in range(len(wave_numbers) - 1, -1, -1):  # Iterate backwards
                                if wave_numbers[i] in ["Wave 4.1", "Wave 4.2"]:
                                    if i + 2 < len(wave_numbers) and wave_numbers[i + 2] is None:  # Ensure valid shift
                                        wave_numbers[i + 2] = wave_numbers[i]  # Move to i+2
                                        wave_numbers[i] = None  # Clear original index
                    else:
                        # If the condition for Wave 4 fails, reset Wave 1 and Wave 2, 3 to None
                        print_verbose(f"UpTrend Wave 5 (i+2) & (i+4) condition failed at index {i}. Resetting Wave 1,2,3,4.")
                        wave_numbers = [] # Clear the list to reset the waves
                        break
            # Assign Impulsive Wave Numbers for UpTrend if there are any Higher Formed, otherwise assign Corrective Waves (A,B,C)
            elif current_wave == 5.1 or current_wave == 5.2:
                # for i in range(i + 1, len(df) - 3):  # Ensure there's space for i+3, i+4, etc.
                # if i > 1 and i + 3 < len(df):  # Ensure i-1, i-2 are valid and i+1, i+2, i+3 are within bounds
                # # Check if indices i+2 and i+3 exist
                if i+1 < len(df) and df[zigzag_column].iloc[i] < df[zigzag_column].iloc[i-1] and df[zigzag_column].iloc[i] >= df[zigzag_column].iloc[i-2] and wave_5_i2_flag_up == False and wave_5_i4_flag_up == False:
                    if df[zigzag_column].iloc[i+1] > df[zigzag_column].iloc[i-1]:
                        wave_numbers[i] = 'Wave 6'
                        wave_numbers[i+1] = 'Wave 7'
                        # Check if another Higher High is forming or not:
                        if i+3 < len(df) and df[zigzag_column].iloc[i+2] >= df[zigzag_column].iloc[i] and df[zigzag_column].iloc[i+3] > df[zigzag_column].iloc[i+1]:
                            wave_numbers[i+2] = 'Wave 8'
                            wave_numbers[i+3] = 'Wave 9'
                            # Check if indices i+4 and i+5 exist
                            if i+5 < len(df) and df[zigzag_column].iloc[i+5] > df[zigzag_column].iloc[i+3] and df[zigzag_column].iloc[i+4] > df[zigzag_column].iloc[i+2]:
                                wave_numbers[i+4] = 'Wave 10'
                                wave_numbers[i+5] = 'Wave 11'
                            else:
                                if i+5 < len(df) and df[zigzag_column].iloc[i+4] >= df[zigzag_column].iloc[i+2]:
                                    wave_numbers[i+4] = 'Wave a'
                                    wave_numbers[i+5] = 'Wave b'
                                    if i+6 < len(df) and df[zigzag_column].iloc[i+4] > df[zigzag_column].iloc[i+6]:
                                        wave_numbers[i+6] = 'Wave c'
                                    else:
                                        # Remove Wave a and Wave b if Wave c condition is not met
                                        wave_numbers[i+4] = None
                                        wave_numbers[i+5] = None
                                elif i+5 < len(df):
                                    # Reset Wave a and Wave b if they were partially set
                                    wave_numbers[i+4] = None
                                    wave_numbers[i+5] = None
                        else:
                            if i+3 < len(df) and df[zigzag_column].iloc[i+2] >= df[zigzag_column].iloc[i]:
                                wave_numbers[i+2] = 'Wave a'
                                wave_numbers[i+3] = 'Wave b'
                                if i+4 < len(df) and df[zigzag_column].iloc[i+2] > df[zigzag_column].iloc[i+4]:
                                    wave_numbers[i+4] = 'Wave c'
                                elif i+4 < len(df):
                                    # Remove Wave a and Wave b if Wave c condition is not met
                                    wave_numbers[i+2] = None
                                    wave_numbers[i+3] = None
                                    wave_numbers[i+4] = None
                    else:
                        if df[zigzag_column].iloc[i] >= df[zigzag_column].iloc[i-2]:
                            wave_numbers[i] = 'Wave a'
                            wave_numbers[i+1] = 'Wave b'
                            if i+2 < len(df) and df[zigzag_column].iloc[i] > df[zigzag_column].iloc[i+2]:
                                wave_numbers[i+2] = 'Wave c'
                            elif i+2 < len(df):
                                # Remove Wave a and Wave b if Wave c condition is not met
                                wave_numbers[i] = None
                                wave_numbers[i+1] = None
                                wave_numbers[i+2] = None
                else:
                    print_verbose(f"wave_numbers at 2nd else of 5.2 at index {6}: {wave_numbers[6]}")
                    # If condition fails, we check the next point by incrementing the index by 2 and re-evaluating the conditions
                    print_verbose(f"UpTrend Wave 6,7,8,9 or a,b,c condition failed at index {i}. Trying the next point for Wave 6,7,8,9 or a,b,c.")
                    # break
                    # Move the index by 2 to skip the current point and proceed to the next
                    i += 2  # Increment by 2
                    if i+1 < len(df) and df[zigzag_column].iloc[i] < df[zigzag_column].iloc[i-1] and df[zigzag_column].iloc[i] >= df[zigzag_column].iloc[i-2] and wave_5_i2_flag_up == False and wave_5_i4_flag_up == False:
                        if df[zigzag_column].iloc[i+1] > df[zigzag_column].iloc[i-1]:
                            wave_numbers[i] = 'Wave 6'
                            wave_numbers[i+1] = 'Wave 7'
                            # Check if another Higher High is forming or not:
                            if i+3 < len(df) and df[zigzag_column].iloc[i+2] >= df[zigzag_column].iloc[i] and df[zigzag_column].iloc[i+3] > df[zigzag_column].iloc[i+1]:
                                wave_numbers[i+2] = 'Wave 8'
                                wave_numbers[i+3] = 'Wave 9'
                                # Check if indices i+4 and i+5 exist
                                if i+5 < len(df) and df[zigzag_column].iloc[i+5] > df[zigzag_column].iloc[i+3] and df[zigzag_column].iloc[i+4] > df[zigzag_column].iloc[i+2]:
                                    wave_numbers[i+4] = 'Wave 10'
                                    wave_numbers[i+5] = 'Wave 11'
                                else:
                                    if i+5 < len(df) and df[zigzag_column].iloc[i+4] >= df[zigzag_column].iloc[i+2]:
                                        wave_numbers[i+4] = 'Wave a'
                                        wave_numbers[i+5] = 'Wave b'
                                        if i+6 < len(df) and df[zigzag_column].iloc[i+4] > df[zigzag_column].iloc[i+6]:
                                            wave_numbers[i+6] = 'Wave c'
                                        else:
                                            # Remove Wave a and Wave b if Wave c condition is not met
                                            wave_numbers[i+4] = None
                                            wave_numbers[i+5] = None
                                    elif i+5 < len(df):
                                        # Reset Wave a and Wave b if they were partially set
                                        wave_numbers[i+4] = None
                                        wave_numbers[i+5] = None
                            else:
                                if i+3 < len(df) and df[zigzag_column].iloc[i+2] >= df[zigzag_column].iloc[i]:
                                    wave_numbers[i+2] = 'Wave a'
                                    wave_numbers[i+3] = 'Wave b'
                                    if i+4 < len(df) and df[zigzag_column].iloc[i+2] > df[zigzag_column].iloc[i+4]:
                                        wave_numbers[i+4] = 'Wave c'
                                    elif i+4 < len(df):
                                        # Remove Wave a and Wave b if Wave c condition is not met
                                        wave_numbers[i+2] = None
                                        wave_numbers[i+3] = None
                                        wave_numbers[i+4] = None
                        else:
                            if df[zigzag_column].iloc[i] >= df[zigzag_column].iloc[i-2]:
                                wave_numbers[i] = 'Wave a'
                                wave_numbers[i+1] = 'Wave b'
                                if i+2 < len(df) and df[zigzag_column].iloc[i] > df[zigzag_column].iloc[i+2]:
                                    wave_numbers[i+2] = 'Wave c'
                                elif i+2 < len(df):
                                    # Remove Wave a and Wave b if Wave c condition is not met
                                    wave_numbers[i] = None
                                    wave_numbers[i+1] = None
                                    wave_numbers[i+2] = None
                    else:
                        break

        print_verbose(wave_numbers)
        # Check if 'Wave 1' exists in wave_numbers before attempting to find its index # # Remove None values
        if 'Wave 1' in wave_numbers:
            wave1_index = wave_numbers.index('Wave 1')
            print_verbose(f"Index of first occurrence of 'Wave 1': {wave1_index}")
            # Slice the lists to remove all None values before the index
            wave_numbers = wave_numbers[wave1_index:]
            # Find the index of the last non-None value in wave_numbers
            last_non_none_index = len(wave_numbers) - 1
            while last_non_none_index >= 0 and wave_numbers[last_non_none_index] is None:
                last_non_none_index -= 1
            # Trim the lists to remove trailing None values, keeping leading None intact in wave_numbers_outer
            wave_numbers = wave_numbers[:last_non_none_index + 1]
        else:
            print_verbose("'Wave 1' is not present in wave_numbers")
        # wave_numbers = [wave for wave in wave_numbers if wave is not None]
        print_verbose(wave_numbers)
        return wave_numbers

    def triangles_u(start_idx,prev_idx, i_2):
        # # Initialize wave_numbers list based on the length of df
        wave_numbers = [None] * len(df)
        # Check if indices are valid
        if 0 <= prev_idx < len(df) and 0 <= start_idx < len(df):
            i_2 = df[zigzag_column].iloc[i_2]
            start_value = df[zigzag_column].iloc[prev_idx]
            end_value = df[zigzag_column].iloc[start_idx]
            start_datetime = df['Datetime'].iloc[prev_idx]
            end_datetime = df['Datetime'].iloc[start_idx]

            # print_verbose the relevant details including index and datetime
            print_verbose(f"UpTrend Triangle Wave A: {start_value} at index {prev_idx}, Datetime: {start_datetime}")
            print_verbose(f"UpTrend Triangle Wave B: {end_value} at index {start_idx}, Datetime: {end_datetime}")

            # Assign wave numbers
            wave_numbers[prev_idx] = 'A'
            wave_numbers[start_idx] = 'B'
        else:
            print_verbose(f"Invalid indices: prev_idx={prev_idx}, start_idx={start_idx}")
        current_wave ="B"

        for i in range(start_idx + 1, len(df)):
            if current_wave =="B":
                #Condition for Point C: 1. C > A (Ascending Triangle) 2. C = A (Descending Triangle)
                # 3. Contracting Triangle (C > A)
                if (df[zigzag_column].iloc[i] < df[zigzag_column].iloc[start_idx-2]) and (df[zigzag_column].iloc[start_idx] <= df[zigzag_column].iloc[start_idx-2]) and (df[zigzag_column].iloc[i] >= df[zigzag_column].iloc[start_idx-1]) and (df[zigzag_column].iloc[i] < df[zigzag_column].iloc[start_idx]):
                    current_value = df[zigzag_column].iloc[i]
                    print_verbose(f"current_value for C, {current_value}")
                    wave_numbers[i] = 'C'
                    current_wave = "C"
                    print_verbose(f"Here wave A,B,C are appended")
                #Condition 4 for Point C: Expanding Triangles (A > C) (df[zigzag_column].iloc[i] < df[zigzag_column].iloc[start_idx-1])
                elif (df[zigzag_column].iloc[start_idx] > df[zigzag_column].iloc[start_idx-2]) and df[zigzag_column].iloc[i] < df[zigzag_column].iloc[start_idx-1] and df[zigzag_column].iloc[i] < df[zigzag_column].iloc[start_idx]:
                    current_value = df[zigzag_column].iloc[i]
                    print_verbose(f"current_value for C is for Expanded Triangles, {current_value}")
                    wave_numbers[i] = 'C'
                    current_wave = "C Expanded Triangle"
                    print_verbose(f"Here wave A,B,C are appended")
                else:
                    print_verbose("Triangle Corrective Pattern Broken")
                    wave_numbers = [] # Clear the list to reset the waves
                    break

            elif current_wave == "C" or current_wave == "C Expanded Triangle":
                #Condition for Point D: 1. B > D (Descending Triangle) 2. D = B (Ascending Triangle)
                # 3. Contracting Triangle (B>D) (current_value <= df[zigzag_column].iloc[i-2])
                current_value = df[zigzag_column].iloc[i]
                print_verbose(f"Current Value for D, {current_value}")
                if current_wave == "C" and current_value <= df[zigzag_column].iloc[i-2] and current_value > df[zigzag_column].iloc[i-1]:
                    print_verbose("Started D")
                    wave_numbers[i] = 'D'
                    current_wave = "D"
                #Condition 4 for Point C: Expanding Triangles (D > B) >> current_value > df[zigzag_column].iloc[i-2]
                elif current_wave == "C Expanded Triangle" and current_value > df[zigzag_column].iloc[i-2] and current_value > df[zigzag_column].iloc[i-1]:
                    current_value = df[zigzag_column].iloc[i]
                    print_verbose(f"current_value for D Expanded Triangles, {current_value}")
                    wave_numbers[i] = 'D'
                    current_wave = "D Expanded Triangle"
                else:
                    wave_numbers = [] # Clear the list to reset the waves
                    break

            elif current_wave == "D" or current_wave == "D Expanded Triangle":
                #Condition for Point E: 1. E > C (Ascending Triangle) 2. E = C (Descending Triangle)
                # 3. Contracting Triangle (E > C) (current_value <= df[zigzag_column].iloc[i-2])
                current_value = df[zigzag_column].iloc[i]
                prev_value = df[zigzag_column].iloc[i-1]
                print_verbose(f"current_value for E, {current_value}")

                if current_wave == "D" and current_value < prev_value and current_value > df[zigzag_column].iloc[i-2]:
                    wave_numbers[i] = 'E'
                    current_wave = "E"

                #Condition 4 for Point E: Expanding Triangles (C > E) >> current_value < df[zigzag_column].iloc[i-2]
                elif current_wave == "D Expanded Triangle" and current_value < prev_value  and current_value < df[zigzag_column].iloc[i-2]:
                    current_value = df[zigzag_column].iloc[i]
                    print_verbose(f"current_value for E Expanded Triangles, {current_value}")
                    wave_numbers[i] = 'E'
                    current_wave = "E"

                else:
                    wave_numbers = [] # Clear the list to reset the waves
                    break
        # # Remove None values
        wave_numbers = [wave for wave in wave_numbers if wave is not None]
        print_verbose(wave_numbers)
        return wave_numbers

    def flats(start_idx):
        # W1,X1,Y1 Condition: W1 > X1 and W1 > Y1: Mark Y1 point as A
        # W2 Condition: X1 >= W2: Ensures Wave X doesn't retrace beyond Wave W's end.
        # X2 Condition: X2 < W2 and X2 >= W1
        # Y2 Condition: Y2 > X1 annd Y2 > W2 , Mark this point as B
        wave_numbers_inner = [None] * len(df)
        wave_numbers_outer = [None] * len(df)
        wave_numbers_inner[start_idx] = '((w))'  # First point is Wave 1
        current_wave_inner = "((w))"
        # current_wave_outer = " "  # Initialize current_wave_outer to avoid UnboundLocalError
        w1 = df[zigzag_column].iloc[start_idx]
        print_verbose(f"Flat Wave w1: {w1}")
        # print_verbose(f"Current wave outer before checking: {current_wave_outer}")  # Debug print
        for i in range(start_idx + 1, len(df)):
            if current_wave_inner =="((w))":
                # Only check i + 2 < len(df) as it's sufficient to cover both
                if i + 2 < len(df):
                    x1 = df[zigzag_column].iloc[i]
                    # print_verbose(f"x1, {x1}")
                    previous_value = df[zigzag_column].iloc[start_idx-1]
                    # print_verbose(f"Previous Value, {previous_value}")
                    y1 = df[zigzag_column].iloc[start_idx+2]
                    # print_verbose(f"y1 Value, {y1}")
                    if (x1 > w1) and (w1 > y1) and (previous_value > x1 ): #(previous_value > x1 )
                        wave_numbers_inner[i] = '((x))'
                        wave_numbers_inner[i+1] = '((y))'
                        wave_numbers_outer[i+1] = "A"
                        current_wave_outer = "A"
                        # print_verbose(current_wave_outer)
                        current_wave_inner = "((y1))"
                        print_verbose("w1,x1,y1 are present and A is added")
                    else:
                        wave_numbers_inner = [] # Clear the list to reset the waves
                        wave_numbers_outer = [] # Clear the list to reset the waves
                        break
            elif current_wave_inner == "((y1))":
                # Only check i + 3 < len(df) as it's sufficient to cover both
                if i + 3 < len(df):
                    y1 = df[zigzag_column].iloc[i]
                    x1 = df[zigzag_column].iloc[i-1]
                    w1 = df[zigzag_column].iloc[i-2]
                    w2 = df[zigzag_column].iloc[i+1]
                    x2 = df[zigzag_column].iloc[i+2]
                    y2 = df[zigzag_column].iloc[i+3]
                    if (w2 > y1) and (w2 > x2) and (y2 > x1 and y2 > w2): #(x1 >= w2 and w2 > y1) and (w2 > x2 and x2 >= w1) and (y2 > x1 and y2 > w2)
                        wave_numbers_inner[i+1] = '((w))'
                        wave_numbers_inner[i+2] = '((x))'
                        wave_numbers_inner[i+3] = '((y))'
                        wave_numbers_outer[i+3] = "B"
                        # current_wave_outer = "B"
                        current_wave_inner = '((y2))'
                        print_verbose("w2,x2,y2 are present and B is added")
                    else:
                        wave_numbers_inner = [] # Clear the list to reset the waves
                        wave_numbers_outer = [] # Clear the list to reset the waves
                        break
            elif current_wave_inner == '((y2))':
                print_verbose("Checking for C")
                if i + 4 < len(df):
                    print_verbose("checking for 1,2")
                    w2 = df[zigzag_column].iloc[i]
                    y2 = df[zigzag_column].iloc[i+2]
                    one = df[zigzag_column].iloc[i+3]
                    two = df[zigzag_column].iloc[i+4]
                    print_verbose(y2, one, two)
                    if (y2 > one) and (two > one) and (y2 >= two):
                        wave_numbers_inner[i+3] = '((i))'
                        wave_numbers_inner[i+4] = '((ii))'
                        current_wave_inner = "((ii))"
                        print_verbose("1,2 is added")
                        if i + 7 < len(df) and current_wave_inner == "((ii))":
                            three = df[zigzag_column].iloc[i+5]
                            four = df[zigzag_column].iloc[i+6]
                            five = df[zigzag_column].iloc[i+7]
                            if (one > three) and (two >= four) and (three > five): #if (one > three) and (one >= four) and (three > five):
                                wave_numbers_inner[i+5] = '((iii))'
                                wave_numbers_inner[i+6] = '((iv))'
                                wave_numbers_inner[i+7] = '((v))'
                                wave_numbers_outer[i+7] = "C"
                                print_verbose("1,2,3,4,5 are present and C is added")
                                print_verbose(wave_numbers_inner)
                                print_verbose(wave_numbers_outer)
                            else:
                                wave_numbers_inner = [] # Clear the list to reset the waves
                                wave_numbers_outer = [] # Clear the list to reset the waves
                                break
                    else:
                        wave_numbers_inner = [] # Clear the list to reset the waves
                        wave_numbers_outer = [] # Clear the list to reset the waves
                        break

            else:
                # wave_numbers_inner = [] # Clear the list to reset the waves
                # wave_numbers_outer = [] # Clear the list to reset the waves
                break

        print_verbose("Before cleaning:")
        # print_verbose(wave_numbers_inner)  # Ensure this list is populated before cleaning
        # print_verbose(wave_numbers_outer)  # Ensure this list is populated before cleaning

        # Check if '((a))' exists in wave_numbers_inner before attempting to find its index
        if '((w))' in wave_numbers_inner:
            first_a_index = wave_numbers_inner.index('((w))')
            print_verbose(f"Index of first occurrence of '((w))': {first_a_index}")
            # Slice the lists to remove all None values before the index
            wave_numbers_inner = wave_numbers_inner[first_a_index:]
            wave_numbers_outer = wave_numbers_outer[first_a_index:]

            # Find the index of the last non-None value in wave_numbers_inner
            last_non_none_index_inner = len(wave_numbers_inner) - 1
            while last_non_none_index_inner >= 0 and wave_numbers_inner[last_non_none_index_inner] is None:
                last_non_none_index_inner -= 1

            # Find the index of the last non-None value in wave_numbers_outer
            last_non_none_index_outer = len(wave_numbers_outer) - 1
            while last_non_none_index_outer >= 0 and wave_numbers_outer[last_non_none_index_outer] is None:
                last_non_none_index_outer -= 1

            # Trim the lists to remove trailing None values, keeping leading None intact in wave_numbers_outer
            wave_numbers_inner = wave_numbers_inner[:last_non_none_index_inner + 1]
            wave_numbers_outer = wave_numbers_outer[:last_non_none_index_outer + 1]
        else:
            print_verbose("'((w))' is not present in wave_numbers_inner")

        # Printing the cleaned lists to verify the replacement of None with ""
        print_verbose("After cleaning:")
        print_verbose(wave_numbers_inner)
        print_verbose(wave_numbers_outer)

        return wave_numbers_inner, wave_numbers_outer

        # print_verbose("Before cleaning:")
        # print_verbose(wave_numbers_inner)  # Ensure this list is populated before cleaning
        # print_verbose(wave_numbers_outer)  # Ensure this list is populated before cleaning

        # # Before cleaning, both lists have a 'None' at the start.
        # # wave_numbers_inner = [None, '((w))', '((x))', '((y))', '((w))', '((x))', '((y))', '((i))', '((ii))', '((iii))', '((iv))', '((v))']
        # # wave_numbers_outer = [None, None, None, 'A', None, None, 'B', None, None, None, None, 'C']

        # # Check if the 0th index of both lists is None, and if so, remove the first element
        # if wave_numbers_inner and wave_numbers_inner[0] is None:
        #     wave_numbers_inner.pop(0)  # Remove the first element if it is None

        # # Check if the 4th index is 'A'
        # if wave_numbers_outer and len(wave_numbers_outer) > 3 and wave_numbers_outer[3] == 'A':
        #     # Check if the 0th index is None, and remove it if true
        #     if wave_numbers_outer[0] is None:
        #         wave_numbers_outer.pop(0)

        # # Cleaning the lists (replacing None with "")
        # wave_numbers_inner_cleaned = [x if x is not None else "" for x in wave_numbers_inner]
        # wave_numbers_outer_cleaned = [x if x is not None else "" for x in wave_numbers_outer]

        # # Printing the cleaned lists to verify the replacement of None with ""
        # print_verbose("After cleaning:")
        # print_verbose(wave_numbers_inner_cleaned)
        # print_verbose(wave_numbers_outer_cleaned)

        # # Check if 0th element is '((w))' or Not, If not then Empty the list
        # if wave_numbers_inner_cleaned and wave_numbers_inner_cleaned[0] != '((w))':
        #     wave_numbers_inner_cleaned = []  # Clear the entire list if the condition is met

        # # Check if 0th element is 'A' or Not, If not then Empty the list
        # if wave_numbers_outer_cleaned and wave_numbers_outer_cleaned[2] != 'A':
        #     wave_numbers_outer_cleaned = []  # Clear the entire list if the condition is met

        # print_verbose("List wave_numbers_inner_cleaned:", wave_numbers_inner_cleaned)
        # print_verbose("List wave_numbers_outer_cleaned:", wave_numbers_outer_cleaned)

        # return wave_numbers_inner_cleaned, wave_numbers_outer_cleaned

    def zigzag(start_idx):
        # W1,X1,Y1 Condition: W1 > X1 and W1 > Y1: Mark Y1 point as A
        # W2 Condition: X1 >= W2: Ensures Wave X doesn't retrace beyond Wave W's end.
        # X2 Condition: X2 < W2 and X2 >= W1
        # Y2 Condition: Y2 > X1 annd Y2 > W2 , Mark this point as B
        wave_numbers_inner = [None] * len(df)
        wave_numbers_outer = [None] * len(df)
        wave_numbers_inner[start_idx] = '((i))'  # First point is Wave 1
        current_wave_inner = "((i))"
        # current_wave_outer = " "  # Initialize current_wave_outer to avoid UnboundLocalError
        wave1 = df[zigzag_column].iloc[start_idx]
        print_verbose(f"Zigzag Wave i: {wave1}")
        # print_verbose(f"Current wave outer before checking: {current_wave_outer}")  # Debug print_verbose
        for i in range(start_idx + 1, len(df)):
            if current_wave_inner =="((i))":
                # Only check i + 2 < len(df) as it's sufficient to cover both
                if i + 5 < len(df):
                    wave1 = df[zigzag_column].iloc[i]
                    previous_value = df[zigzag_column].iloc[start_idx-1]
                    wave2 = df[zigzag_column].iloc[start_idx+2]
                    wave3 = df[zigzag_column].iloc[start_idx+3]
                    wave4 = df[zigzag_column].iloc[start_idx+4]
                    wave5 = df[zigzag_column].iloc[start_idx+5]
                    if (wave2 > wave1) and (previous_value > wave2) and (wave1 > wave3) and (wave1 > wave4) and (wave3 > wave5): #(previous_value > x1 )
                        wave_numbers_inner[i] = '((i))'
                        wave_numbers_inner[i+1] = '((ii))'
                        wave_numbers_inner[i+2] = '((iii))'
                        wave_numbers_inner[i+3] = '((iv))'
                        wave_numbers_inner[i+4] = '((v))'
                        wave_numbers_outer[i+4] = "A"
                        current_wave_outer = "A"
                        current_wave_inner = "((y1))"
                        print_verbose("wave1,2,3,4,5 are present in Zigzag and A is added")
                    else:
                        wave_numbers_inner = [] # Clear the list to reset the waves
                        wave_numbers_outer = [] # Clear the list to reset the waves
                        break
            elif current_wave_inner == "((v))":
                # Only check i + 3 < len(df) as it's sufficient to cover both
                if i + 6 < len(df):
                    wave2 = df[zigzag_column].iloc[i]
                    wave4 = df[zigzag_column].iloc[i+2]
                    wave5 = df[zigzag_column].iloc[i+3]
                    wavea = df[zigzag_column].iloc[i+4]
                    waveb = df[zigzag_column].iloc[i+5]
                    wavec = df[zigzag_column].iloc[i+6]
                    if (wave4 >= wavea and wave5 > wavea) and (waveb > wave5) and (wavec > wave4):
                        wave_numbers_inner[i+4] = '((a))'
                        wave_numbers_inner[i+5] = '((b))'
                        wave_numbers_inner[i+6] = '((c))'
                        wave_numbers_outer[i+6] = "B"
                        current_wave_inner = '((c))'
                        print_verbose("a,b,c are present in zigzag wave and B is added")
                    else:
                        wave_numbers_inner = [] # Clear the list to reset the waves
                        wave_numbers_outer = [] # Clear the list to reset the waves
                        break
            elif current_wave_inner == '((c))':
                print_verbose("Checking for C for Zigzag Wave")
                if i + 7 < len(df):
                    print_verbose("checking for 1,2")
                    wave3 = df[zigzag_column].iloc[i]
                    wavec = df[zigzag_column].iloc[i+5]
                    one = df[zigzag_column].iloc[i+6]
                    two = df[zigzag_column].iloc[i+7]
                    print_verbose(wavec, one, two)
                    if (wavec > one) and (two > one) and (wavec >= two):
                        wave_numbers_inner[i+6] = '((i))'
                        wave_numbers_inner[i+7] = '((ii))'
                        current_wave_inner = "((ii))"
                        print_verbose("1,2 is added")
                        if i + 10 < len(df) and current_wave_inner == "((ii))":
                            three = df[zigzag_column].iloc[i+8]
                            four = df[zigzag_column].iloc[i+9]
                            five = df[zigzag_column].iloc[i+10]
                            if (one > three) and (one >= four) and (three > five):
                                wave_numbers_inner[i+8] = '((iii))'
                                wave_numbers_inner[i+9] = '((iv))'
                                wave_numbers_inner[i+10] = '((v))'
                                wave_numbers_outer[i+10] = "C"
                                print_verbose("1,2,3,4,5 are present in Zigzag wave and C is added")
                                print_verbose(wave_numbers_inner)
                                print_verbose(wave_numbers_outer)
                            else:
                                wave_numbers_inner = [] # Clear the list to reset the waves
                                wave_numbers_outer = [] # Clear the list to reset the waves
                                break
                    else:
                        wave_numbers_inner = [] # Clear the list to reset the waves
                        wave_numbers_outer = [] # Clear the list to reset the waves
                        break

            else:
                # wave_numbers_inner = [] # Clear the list to reset the waves
                # wave_numbers_outer = [] # Clear the list to reset the waves
                break

        # print_verbose("Before cleaning:")
        # print_verbose(wave_numbers_inner)  # Ensure this list is populated before cleaning
        # print_verbose(wave_numbers_outer)  # Ensure this list is populated before cleaning

        # Check if '((i))' exists in wave_numbers_inner before attempting to find its index
        if '((i))' in wave_numbers_inner:
            first_a_index = wave_numbers_inner.index('((i))')
            print_verbose(f"Index of first occurrence of '((i))': {first_a_index}")
            # Slice the lists to remove all None values before the index
            wave_numbers_inner = wave_numbers_inner[first_a_index:]
            wave_numbers_outer = wave_numbers_outer[first_a_index:]

            # Find the index of the last non-None value in wave_numbers_inner
            last_non_none_index_inner = len(wave_numbers_inner) - 1
            while last_non_none_index_inner >= 0 and wave_numbers_inner[last_non_none_index_inner] is None:
                last_non_none_index_inner -= 1

            # Find the index of the last non-None value in wave_numbers_outer
            last_non_none_index_outer = len(wave_numbers_outer) - 1
            while last_non_none_index_outer >= 0 and wave_numbers_outer[last_non_none_index_outer] is None:
                last_non_none_index_outer -= 1

            # Trim the lists to remove trailing None values, keeping leading None intact in wave_numbers_outer
            wave_numbers_inner = wave_numbers_inner[:last_non_none_index_inner + 1]
            wave_numbers_outer = wave_numbers_outer[:last_non_none_index_outer + 1]
        else:
            print_verbose("'((i))' is not present in wave_numbers_inner")

        # print_verboseing the cleaned lists to verify the replacement of None with ""
        print_verbose("After cleaning:")
        print_verbose(wave_numbers_inner)
        print_verbose(wave_numbers_outer)

        return wave_numbers_inner, wave_numbers_outer

        # print_verbose("Before cleaning:")
        # print_verbose(wave_numbers_inner)  # Ensure this list is populated before cleaning
        # print_verbose(wave_numbers_outer)  # Ensure this list is populated before cleaning

        # # Before cleaning, both lists have a 'None' at the start.
        # # wave_numbers_inner = [None, '((w))', '((x))', '((y))', '((w))', '((x))', '((y))', '((i))', '((ii))', '((iii))', '((iv))', '((v))']
        # # wave_numbers_outer = [None, None, None, 'A', None, None, 'B', None, None, None, None, 'C']

        # # Check if the 0th index of both lists is None, and if so, remove the first element
        # if wave_numbers_inner and wave_numbers_inner[0] is None:
        #     wave_numbers_inner.pop(0)  # Remove the first element if it is None

        # # Check if the 4th index is 'A'
        # if wave_numbers_outer and len(wave_numbers_outer) > 3 and wave_numbers_outer[3] == 'A':
        #     # Check if the 0th index is None, and remove it if true
        #     if wave_numbers_outer[0] is None:
        #         wave_numbers_outer.pop(0)

        # # Cleaning the lists (replacing None with "")
        # wave_numbers_inner_cleaned = [x if x is not None else "" for x in wave_numbers_inner]
        # wave_numbers_outer_cleaned = [x if x is not None else "" for x in wave_numbers_outer]

        # # print_verboseing the cleaned lists to verify the replacement of None with ""
        # print_verbose("After cleaning:")
        # print_verbose(wave_numbers_inner_cleaned)
        # print_verbose(wave_numbers_outer_cleaned)
        # # Check if 0th element is '((w))' or Not, If not then Empty the list
        # if wave_numbers_inner_cleaned and wave_numbers_inner_cleaned[0] != '((i))':
        #     wave_numbers_inner_cleaned = []  # Clear the entire list if the condition is met
        # # Check if 0th element is 'A' or Not, If not then Empty the list
        # if wave_numbers_outer_cleaned and wave_numbers_outer_cleaned[4] != 'A':
        #     wave_numbers_outer_cleaned = []  # Clear the entire list if the condition is met
        # print_verbose("List wave_numbers_inner_cleaned:", wave_numbers_inner_cleaned)
        # print_verbose("List wave_numbers_outer_cleaned:", wave_numbers_outer_cleaned)
        # return wave_numbers_inner_cleaned, wave_numbers_outer_cleaned

    def swing_high_low_u(start_idx):
        wave_numbers = [None] * len(df)
        wave_numbers[start_idx] = 'SH'  # First point is Wave 1
        current_wave = "SH"
        start_value = df[zigzag_column].iloc[start_idx]
        print_verbose(f"Swing High Uprtrend Wave 1: {start_value}")
        for i in range(start_idx + 1, len(df)):
            if current_wave == "SH":
                if (df[zigzag_column].iloc[start_idx-2] < start_value) and (df[zigzag_column].iloc[i] < start_value) and (df[zigzag_column].iloc[i] >= df[zigzag_column].iloc[start_idx -1]):
                    wave_numbers[i] = 'SL'
                    current_wave = "SL1"  # Move to the next wave
                else:
                    wave_numbers = [] # Clear the list to reset the waves
                    break
            elif current_wave == "SL1":
                if (df[zigzag_column].iloc[i] > df[zigzag_column].iloc[i-2]):
                    wave_numbers[i] = 'SH'
                    current_wave = "SH2"  # Move to the next wave
                else:
                    # wave_numbers = [] # Clear the list to reset the waves
                    break
            elif current_wave == "SH2":
                if (df[zigzag_column].iloc[i] > df[zigzag_column].iloc[i-2]) and (df[zigzag_column].iloc[i] < df[zigzag_column].iloc[i-3]):
                    wave_numbers[i] = 'SL'
                    current_wave = "SL2"  # Move to the next wave
                else:
                    # wave_numbers = [] # Clear the list to reset the waves
                    break
        # Remove None values
        wave_numbers = [wave for wave in wave_numbers if wave is not None]
        print_verbose(wave_numbers)
        return wave_numbers

    # Function to assign waves for a downtrend
    def assign_downtrend_waves(start_idx):
        wave_numbers = [None] * len(df)
        wave_numbers[start_idx] = 'Wave 1'  # First point is Wave 1

        current_wave = 1
        start_value = df[zigzag_column].iloc[start_idx]
        print_verbose(f"DownTrend Wave 1: {start_value}")

        for i in range(start_idx + 1, len(df)):
            if pd.isna(df[zigzag_column].iloc[i]):
                continue  # Skip None values

            if current_wave == 1:
                # Wave 2: Correction: 2 Conditions : 1.Fib Retracement 2. Pattern Formation
                current_value = df[zigzag_column].iloc[i]
                print_verbose(f"current_value, {current_value}")
                previous_value = df[zigzag_column].iloc[start_idx-1]
                if df[zigzag_column].iloc[i] >= start_value and previous_value >= df[zigzag_column].iloc[i]:
                    # Calculate Fibonacci Retracement Levels using `start_value` and `previous_value` (local low)
                    #Retracement level=End point+(Start point−End point)×Fibonacci ratio
                    fib_levels = {
                        '38.2%': start_value + (previous_value - start_value) * 0.382,
                        '85.1%': start_value + (previous_value - start_value) * 0.851
                    }
                    print_verbose(fib_levels)
                    # Check if the current value is within the Fibonacci range (38.2% to 61.8% for correction)
                    if fib_levels['38.2%'] <= current_value <= fib_levels['85.1%']:
                        print_verbose(f"DownTrend Wave 2 Fibonacci condition met: {current_value} at index {i}, Both Condition meet, it should be shown in Dark Green Color")
                        wave_numbers[i] = 'Wave 2.1'
                        current_wave = 2.1  # Move to the next wave
                    else:
                        print_verbose(f"DownTrend Wave 2 Fibonacci condition failed at index {i} Only Pattern Matching Condition Met.")
                        print_verbose(f"Still Assigning DontTrend Wave as 2, but it will shown as green faint color, as it Completed 1 condition out of 2.")
                        wave_numbers[i] = 'Wave 2.2'
                        current_wave = 2.2  # Move to the next wave
                else:
                    # If the condition for Wave 2 fails, reset Wave 1 and Wave 2 and start from next point
                    print_verbose(f"Wave 2 DownTrend condition failed at index {i}. Resetting Wave 1 and Wave 2.")
                    wave_numbers[start_idx] = None  # Reset Wave 1
                    wave_numbers[i] = None  # Reset Wave 2
                    wave_numbers = [] # Clear the list to reset the waves
                    break

            elif current_wave == 2.1 or current_wave == 2.2:
                wave_3_i2_flag_down = False
                # Wave 3: Impulse (lower than Wave 1)
                # if df[zigzag_column].iloc[i] < start_value:
                if df[zigzag_column].iloc[i] < start_value and df[zigzag_column].iloc[start_idx-1] >= df[zigzag_column].iloc[i]:
                    # Wave 3: Impulse (greater than Wave 1)
                    # Calculate Fibonacci Extensions for Wave 3 using Wave 1 and Wave 2
                    wave_1_length = previous_value - start_value  # Length of Wave 1
                    print_verbose(start_value,previous_value, wave_1_length)
                    current_value = df[zigzag_column].iloc[i]
                    print_verbose(f"Current Value: {current_value}")
                    #start_value is the end of Wave 1
                    #Fibonacci Extension level=Start point+(Wave 1 length)×Fibonacci ratio
                    fib_levels_wave_3 = {
                        '161.8%': start_value - (wave_1_length * 1.618),  # 161.8% extension of Wave 1
                        '261.8%': start_value - (wave_1_length * 2.618)   # 261.8% extension of Wave 1
                    }
                    print_verbose(f"DownTrend Wave 3 Fibonacci extension levels: {fib_levels_wave_3}")
                    # Check if the current value is within the Fibonacci range (38.2% to 61.8% for correction)
                    # Alternate Way: fib_levels_wave_3['161.8%'] >= current_value >= fib_levels_wave_3['261.8%']:
                    if fib_levels_wave_3['261.8%'] <= current_value <= fib_levels_wave_3['161.8%']:
                        print_verbose(f"DownTrend Wave 3 Fibonacci condition met: {current_value} at index {i}, Both Condition meet, it should be shown in Dark Green Color")
                        wave_numbers[i] = 'Wave 3.1'
                        current_wave = 3.1  # Move to the next wave
                        # end_wave_2 = current_value
                    else:
                        print_verbose(f"DownTrend Wave 3 Fibonacci condition failed at index {i} Only Pattern Matching Condition Met.")
                        print_verbose(f"Still Assigning DownTrend Wave as 3, but it will shown as green faint color, as it Completed 1 condition out of 2.")
                        wave_numbers[i] = 'Wave 3.2'
                        current_wave = 3.2  # Move to the next wave
                else:
                    # If condition fails, we check the next point by incrementing the index by 2 and re-evaluating the conditions
                    print_verbose(f"Downtrend Wave 3 condition failed at index {i}. Trying the next point for Wave 3.")
                    # i += 2  # Increment by 2 # Move the index by 2 to skip the current point and proceed to the next
                    # if i < len(df): # Recheck the condition for the next point
                    if i + 2 < len(df):  # Ensure we don't go out of bounds
                        i += 2  # Move the index by 2
                        # Re-evaluate the condition at the new index
                        if df[zigzag_column].iloc[i] < start_value and df[zigzag_column].iloc[i-1] <  previous_value: # 2nd condition to make sure pattern remain intact
                            # Calculate Fibonacci Extensions for Wave 3 using Wave 1 and Wave 2
                            wave_1_length = previous_value - start_value  # Length of Wave 1
                            print_verbose(start_value,previous_value, wave_1_length)
                            current_value = df[zigzag_column].iloc[i]
                            print_verbose(f"Rechecking for Wave 3 at new index {i}, Current Value: {current_value}")
                            #Fibonacci Extension level=Start point+(Wave 1 length)×Fibonacci ratio
                            fib_levels_wave_3 = {
                                '161.8%': start_value - (wave_1_length * 1.618),  # 161.8% extension of Wave 1
                                '261.8%': start_value - (wave_1_length * 2.618)   # 261.8% extension of Wave 1
                            }
                            print_verbose(f"Rechecking Wave 3 Fibonacci extension levels: {fib_levels_wave_3}")
                            # Check if the current value is within the Fibonacci range (38.2% to 61.8% for correction)
                            # Alternate Way: fib_levels_wave_3['161.8%'] >= current_value >= fib_levels_wave_3['261.8%']:
                            wave_3_i2_flag_down = True
                            if fib_levels_wave_3['261.8%'] <= current_value <= fib_levels_wave_3['161.8%']:
                                print_verbose(f"DownTrend Wave 3 Fibonacci condition met: {current_value} at index {i}, Both Condition meet, it should be shown in Dark Green Color")
                                wave_numbers[i] = 'Wave 3.1'
                                current_wave = 3.1  # Move to the next wave
                            else:
                                print_verbose(f"DownTrend Wave 3 Fibonacci condition failed at index {i} Only Pattern Matching Condition Met.")
                                print_verbose(f"Still Assigning Wave as 3, but it will shown as green faint color, as it Completed 1 condition out of 2.")
                                wave_numbers[i] = 'Wave 3.2'
                                current_wave = 3.2  # Move to the next wave
                            #Now Assign Correct Label to Wave 2 for DownTrend Whicheven Wave is Higher, Compare i-1 & i-3 and assigne Wave 2 whichver wave is higher value
                            if df[zigzag_column].iloc[i-1] >= df[zigzag_column].iloc[i-3]:
                                for i in range(len(wave_numbers) - 1, -1, -1):  # Iterate backwards
                                    if wave_numbers[i] in ["Wave 2.1", "Wave 2.2"]:
                                        if i + 2 < len(wave_numbers) and wave_numbers[i + 2] is None:  # Ensure valid shift
                                            wave_numbers[i + 2] = wave_numbers[i]  # Move to i+2
                                            wave_numbers[i] = None  # Clear original index
                        else:
                            # If the condition for Wave 3 fails, reset Wave 1 and Wave 2 and start from next point
                            print_verbose(f"Wave 3 DownTrend condition failed at index {i}. Resetting Wave 1,2,3")
                            wave_numbers = [] # Clear the list to reset the waves
                            break
                    else:
                        print_verbose(f"Wave 3 DownTrend condition failed and out of range at index {i}, stopping evaluation.")
                        wave_numbers = [] # Clear the list to reset the waves
                        break

            elif current_wave == 3.1 or current_wave == 3.2:
                # Wave 4: Correction (back up)
                wave_4_i2_flag_down = False
                if df[zigzag_column].iloc[i] <= df[zigzag_column].iloc[start_idx + 1] and wave_3_i2_flag_down == False: #start_value
                    end_wave_3 = df[zigzag_column].iloc[i-1]
                    print_verbose(f"end_wave_3 Value , {end_wave_3}")
                    print_verbose(f"Wave 1 Lengths for DownTrend Wave 4 Calculation , {wave_1_length}")
                    current_value = df[zigzag_column].iloc[i]
                    print_verbose(f"Current Value: {current_value}")
                    #start_value is the end of Wave 1 >> Retracement Level=End of Wave 3−(Wave 3 Length×Retracement Ratio)
                    fib_levels_wave_4 = {
                        '14.6%': end_wave_3 + (wave_1_length * 0.146),  # 14.6% Retracement of Wave 3
                        '78.6%': end_wave_3 + (wave_1_length * 0.786)   # 38.2% Retracement of Wave 3  #38.2% changed to 78.6%
                    }
                    print_verbose(f"DownTrend Wave 4 Fibonacci extension levels: {fib_levels_wave_4}")
                    # Check if the current value is within the Fibonacci range (38.2% to 78.6% for correction)
                    if fib_levels_wave_4['14.6%'] <= current_value <= fib_levels_wave_4['78.6%']:
                        print_verbose(f"DownTrend Wave 4 Fibonacci condition met: {current_value} at index {i}, Both Condition meet, it should be shown in Dark Green Color")
                        wave_numbers[i] = 'Wave 4.1'
                        current_wave = 4.1  # Move to the next wave
                    else:
                        print_verbose(f"DownTrend Wave 4 Fibonacci condition failed at index {i} Only Pattern Matching Condition Met.")
                        print_verbose(f"Still Assigning Wave as 4, but it will shown as green faint color, as it Completed 1 condition out of 2.")
                        wave_numbers[i] = 'Wave 4.2'
                        current_wave = 4.2  # Move to the next wave
                else:
                    # If condition fails, we check the next point by incrementing the index by 2 and re-evaluating the conditions
                    print_verbose(f"DownTrend Wave 4 condition failed at index {i}. Trying the next point for Wave 4.")
                    # i += 2  # Increment by 2 # Move the index by 2 to skip the current point and proceed to the next
                    # if i < len(df): # Recheck the condition for the next point
                    if i + 2 < len(df):  # Ensure we don't go out of bounds
                        i += 2  # Move the index by 2
                        if i+2 < len(df) and df[zigzag_column].iloc[i] <= df[zigzag_column].iloc[start_idx + 1] and wave_3_i2_flag_down == True: # start_value
                            end_wave_3 = df[zigzag_column].iloc[i-1]
                            print_verbose(f"end_wave_3 Value , {end_wave_3}")
                            print_verbose(f"Wave 1 Lengths for DownTrend Wave 4 Calculation , {wave_1_length}")
                            current_value = df[zigzag_column].iloc[i]
                            print_verbose(f"Current Value: {current_value}")
                            #start_value is the end of Wave 1 >> Retracement Level=End of Wave 3−(Wave 3 Length×Retracement Ratio)
                            fib_levels_wave_4 = {
                                '14.6%': end_wave_3 + (wave_1_length * 0.146),  # 14.6% Retracement of Wave 3
                                '78.6%': end_wave_3 + (wave_1_length * 0.786)   # 38.2% Retracement of Wave 3  #38.2% changed to 78.6%
                            }
                            wave_4_i2_flag_down = True
                            print_verbose(f"DownTrend Wave 4 Fibonacci extension levels: {fib_levels_wave_4}")
                            # Check if the current value is within the Fibonacci range (38.2% to 61.8% for correction)
                            if fib_levels_wave_4['14.6%'] <= current_value <= fib_levels_wave_4['78.6%']:
                                print_verbose(f"DownTrend Wave 4 i+2 Fibonacci condition met: {current_value} at index {i}, Both Condition meet, it should be shown in Dark Green Color")
                                wave_numbers[i] = 'Wave 4.1'
                                current_wave = 4.1  # Move to the next wave
                            else:
                                print_verbose(f"DownTrend Wave 4 i+2 Fibonacci condition failed at index {i} Only Pattern Matching Condition Met.")
                                print_verbose(f"Still Assigning Wave as 4, but it will shown as green faint color, as it Completed 1 condition out of 2.")
                                wave_numbers[i] = 'Wave 4.2'
                                current_wave = 4.2  # Move to the next wave
                        else:
                            # If the condition for Wave 3 fails, reset Wave 1 and Wave 2 and start from next point
                            print_verbose(f"Wave 4 DownTrend condition failed at index {i}. Resetting Wave 1,2,3")
                            wave_numbers[start_idx] = None  # Reset Wave 1
                            wave_numbers[i] = None  # Reset Wave 2
                            wave_numbers[i-1] = None  # Reset Wave 2
                            wave_numbers[i-2] = None  # Reset Wave 3
                            wave_numbers = [] # Clear the list to reset the waves
                            break
                    else:
                        print_verbose(f"Wave 4 condition failed and out of range at index {i}, stopping evaluation.")
                        wave_numbers = [] # Clear the list to reset the waves
                        break

            elif current_wave == 4.1 or current_wave == 4.2:
                wave_5_i2_flag_down = False
                wave_5_i4_flag_down = False
                # Wave 5: Impulse (lower than Wave 3)
                if df[zigzag_column].iloc[i] < df[zigzag_column].iloc[i-2] and wave_4_i2_flag_down == False:
                    end_wave_4 = df[zigzag_column].iloc[i-1]
                    print_verbose(f"end_wave_4 Value , {end_wave_4}")
                    print_verbose(f"Wave 1 Length for Wave 5 Calculation , {wave_1_length}")
                    wave4_length = end_wave_4 - end_wave_3
                    print_verbose(f"Wave 4 Length for Wave 5 Calculation , {wave4_length}")
                    current_value = df[zigzag_column].iloc[i]
                    print_verbose(f"Current Value: {current_value}")
                    #Conditions of Fib 5:
                    #1. Wave 5 = End of Wave 4 + (Wave 4 length × Fibonacci extension ratios such as 1.236, 1.618)
                    #2. Wave 5 = End of Wave 4 + Wave 1 length.
                    #3. Wave 5 = End of Wave 4 + 61.8% of the combined length of Wave 1 and Wave 3.
                    # Check if the current value is within the Fibonacci range (38.2% to 61.8% for correction)

                    fib_levels_wave_5 = {
                        '123.6%': end_wave_4 - (wave4_length * 1.236),  # 14.6% Retracement of Wave 3
                        '161.8%': end_wave_4 - (wave4_length * 1.618)   # 38.2% Retracement of Wave 3
                    }
                    print_verbose(f"DownTrend Wave 5 Fibonacci extension levels: {fib_levels_wave_5}")
                    fib_levels_wave_5_condition_2 = end_wave_4 - wave_1_length
                    print_verbose(f"DownTrend Wave 5 Fib condition:2, {fib_levels_wave_5_condition_2}")
                    # Alternate Way: fib_levels_wave_5['123.6%'] >= current_value >= fib_levels_wave_5['161.8%']:
                    if fib_levels_wave_5['161.8%'] <= current_value <= fib_levels_wave_5['123.6%']:
                        print_verbose(f"DownTrend Wave 5 Fibonacci condition:1 met range between 123.6% & 161.8%,: {current_value} at index {i}, Both Condition meet, it should be shown in Dark Green Color")
                        wave_numbers[i] = 'Wave 5.1'
                        current_wave = 5.1  # Move to the next wave
                    else:
                        print_verbose(f"DownTrend Wave 5 Fibonacci condition failed at index {i} Only Pattern Matching Condition Met.")
                        print_verbose(f"Still Assigning Wave as 5, but it will shown as green faint color, as it Completed 1 condition out of 2.")
                        wave_numbers[i] = 'Wave 5.2'
                        current_wave = 5.2  # Move to the next wave
                else:
                    # If condition fails, we check the next point by incrementing the index by 2 and re-evaluating the conditions
                    print_verbose(f"UpTrend Wave 5 condition failed at index {i}. Trying the next point for Wave 5.")
                    ##Move the index by 2 to skip the current point and proceed to the next
                    i += 2  # Increment by 2
                    if i+2 < len(df) and df[zigzag_column].iloc[i] < df[zigzag_column].iloc[i-2] and wave_4_i2_flag_down == True:
                        print_verbose(df[zigzag_column].iloc[i], df[zigzag_column].iloc[i-2]) #For i +=2, i-2 will be Wave 3
                        if df[zigzag_column].iloc[i-1] >= df[zigzag_column].iloc[i-3]:
                            end_wave_4 = df[zigzag_column].iloc[i-1]
                        else:
                            end_wave_4 = df[zigzag_column].iloc[i-3]
                        print_verbose(f"end_wave_4 Value , {end_wave_4}")
                        print_verbose(f"Wave 1 Length for Wave 5 Calculation , {wave_1_length}")
                        wave4_length = end_wave_4 - end_wave_3
                        print_verbose(f"Wave 4 Length for Wave 5 Calculation , {wave4_length}")
                        current_value = df[zigzag_column].iloc[i]
                        print_verbose(f"Current Value: {current_value}")
                        fib_levels_wave_5 = {
                            '123.6%': end_wave_4 - (wave4_length * 1.236),  # 14.6% Retracement of Wave 3
                            '161.8%': end_wave_4 - (wave4_length * 1.618)   # 38.2% Retracement of Wave 3
                        }
                        wave_5_i2_flag_down = True
                        print_verbose(f"DownTrend Wave 5 Fibonacci extension levels: {fib_levels_wave_5}")
                        fib_levels_wave_5_condition_2 = end_wave_4 - wave_1_length
                        print_verbose(f"DownTrend Wave 5 Fib condition:2, {fib_levels_wave_5_condition_2}")
                        # Alternate Way: fib_levels_wave_5['123.6%'] >= current_value >= fib_levels_wave_5['161.8%']:
                        if fib_levels_wave_5['161.8%'] <= current_value <= fib_levels_wave_5['123.6%']:
                            print_verbose(f"DownTrend Wave 5 i+2 Fibonacci condition:1 met range between 123.6% & 161.8%,: {current_value} at index {i}, Both Condition meet, it should be shown in Dark Green Color")
                            wave_numbers[i] = 'Wave 5.1'
                            current_wave = 5.1  # Move to the next wave
                        else:
                            print_verbose(f"DownTrend Wave 5 i+2 Fibonacci condition failed at index {i} Only Pattern Matching Condition Met.")
                            print_verbose(f"Still Assigning Wave as 5, but it will shown as green faint color, as it Completed 1 condition out of 2.")
                            wave_numbers[i] = 'Wave 5.2'
                            current_wave = 5.2  # Move to the next wave
                        # #Now Assign Correct Label to Wave 2 for DownTrend Whicheven Wave is Higher, Compare i-1 & i-3 and assigne Wave 2 whichver wave is higher value
                        # if df[zigzag_column].iloc[i-1] >= df[zigzag_column].iloc[i-3]:
                        #     for i in range(len(wave_numbers) - 1, -1, -1):  # Iterate backwards
                        #         if wave_numbers[i] in ["Wave 4.1", "Wave 4.2"]:
                        #             if i + 2 < len(wave_numbers) and wave_numbers[i + 2] is None:  # Ensure valid shift
                        #                 wave_numbers[i + 2] = wave_numbers[i]  # Move to i+2
                        #                 wave_numbers[i] = None  # Clear original index

                        # # Compare i-1 & i-3 and assign Wave 2 to whichever wave is higher in value # Now Assign Correct Label to Wave 4 for DownTrend (Whichever Wave is Higher)
                        # if df[zigzag_column].iloc[i-1] >= df[zigzag_column].iloc[i-3]:
                        #     for i in range(len(wave_numbers) - 1, -1, -1):  # Iterate backwards
                        #         # Check if current wave is 'Wave 4.1' or 'Wave 4.2'
                        #         if wave_numbers[i] in ["Wave 4.1", "Wave 4.2"]:
                        #             # Check if 'Wave 5.1' or 'Wave 5.2' appears before 'Wave 4.1' or 'Wave 4.2'
                        #             if any(wave in wave_numbers[:i] for wave in ["Wave 5.1", "Wave 5.2"]):
                        #                 # Ensure valid shift, check if we can move the wave to i+2 (next available index)
                        #                 if i + 2 < len(wave_numbers) and wave_numbers[i + 2] is None:
                        #                     wave_numbers[i + 2] = wave_numbers[i]  # Move to i+2
                        #                     wave_numbers[i] = None  # Clear original index

                    ### This condition is for i+2 3rd Wave and i+2 5th Wave
                    elif i+2 < len(df) and df[zigzag_column].iloc[i+2] < df[zigzag_column].iloc[i-2] and wave_4_i2_flag_down == True: #For i +=4, i+2 is Wave 5 , as we already incremented i+2 , i-2 will be Wave 3
                        print_verbose(df[zigzag_column].iloc[i+2], df[zigzag_column].iloc[i-2])
                        end_wave_4 = max(df['ZIGZAGv_0.01%_3'].iloc[i - 1],df['ZIGZAGv_0.01%_3'].iloc[i + 1]) #, df['ZIGZAGv_0.01%_3'].iloc[i - 3]
                        # end_wave_4 = df[zigzag_column].iloc[i-1]
                        print_verbose(f"end_wave_4 Value , {end_wave_4}")
                        print_verbose(f"Wave 1 Length for Wave 5 Calculation , {wave_1_length}")
                        wave4_length = end_wave_3 - end_wave_4
                        print_verbose(f"Wave 4 Length for Wave 5 Calculation , {wave4_length}")
                        current_value = df[zigzag_column].iloc[i+2]
                        print_verbose(f"Current Value: {current_value}")
                        fib_levels_wave_5 = {
                            '123.6%': end_wave_4 - (wave4_length * 1.236),  # 14.6% Retracement of Wave 3
                            '161.8%': end_wave_4 - (wave4_length * 1.618)   # 38.2% Retracement of Wave 3
                        }
                        wave_5_i4_flag_down = True
                        print_verbose(f"DownTrend Wave 5 Fibonacci extension levels: {fib_levels_wave_5}")
                        fib_levels_wave_5_condition_2 = end_wave_4 - wave_1_length
                        print_verbose(f"DownTrend Wave 5 Fib condition:2, {fib_levels_wave_5_condition_2}")
                        # Alternate Way: fib_levels_wave_5['123.6%'] >= current_value >= fib_levels_wave_5['161.8%']:
                        if fib_levels_wave_5['161.8%'] <= current_value <= fib_levels_wave_5['123.6%']:
                            print_verbose(f"DownTrend Wave 5 i+4 Fibonacci condition:1 met range between 123.6% & 161.8%,: {current_value} at index {i}, Both Condition meet, it should be shown in Dark Green Color")
                            wave_numbers[i+2] = 'Wave 5.1' #As we are checking for i+4 value
                            current_wave = 5.1  # Move to the next wave
                        else:
                            print_verbose(f"DownTrend Wave 5 i+4 Fibonacci condition failed at index {i} Only Pattern Matching Condition Met.")
                            print_verbose(f"Still Assigning Wave as 5, but it will shown as green faint color, as it Completed 1 condition out of 2.")
                            wave_numbers[i+2] = 'Wave 5.2' #As we are checking for i+4 value
                            current_wave = 5.2  # Move to the next wave
                        #Now Assign Correct Label to Wave 4 for DownTrend Whicheven Wave is Higher, Compare i-1 & i-3 and assigne Wave 2 whichver wave is higher value
                        if df[zigzag_column].iloc[i+1] >= df[zigzag_column].iloc[i-1]: #For i+4 condition
                            for i in range(len(wave_numbers) - 1, -1, -1):  # Iterate backwards
                                if wave_numbers[i] in ["Wave 4.1", "Wave 4.2"]:
                                    if i+2 < len(wave_numbers) and wave_numbers[i + 2] is None:  # Ensure valid shift
                                        wave_numbers[i + 2] = wave_numbers[i]  # Move to i+2
                                        wave_numbers[i] = None  # Clear original index
                    else:
                        ##If the condition for Wave 3 fails, reset Wave 1 and Wave 2 and start from next point
                        print_verbose(f"Wave 5 DownTrend condition failed at index {i}. Resetting Wave 1,2,3,4.")
                        wave_numbers = [] # Clear the list to reset the waves
                        break  # Stop after completing wave 5

            # Assign Impulsive Wave Numbers if there are any Higher Formed, otherwise assign Corrective Waves (A,B,C)
            elif current_wave == 5.1 or current_wave == 5.2:
                # for i in range(i + 1, len(df) - 3):  # Ensure there's space for i+3, i+4, etc.
                # # Assign Impulsive Wave for DownTrend Numbers if Lower Low Condition Satisfied
                if i+1 < len(df) and df[zigzag_column].iloc[i] > df[zigzag_column].iloc[i-1] and df[zigzag_column].iloc[i] <= df[zigzag_column].iloc[i-2] and wave_5_i2_flag_down == False and wave_5_i4_flag_down == False:
                    if df[zigzag_column].iloc[i+1] < df[zigzag_column].iloc[i-1]:
                        # Assign Wave 6 and Wave 7
                        wave_numbers[i] = 'Wave 6'
                        wave_numbers[i+1] = 'Wave 7'

                        # Check for Wave 8 and Wave 9
                        if i+3 < len(df) and df[zigzag_column].iloc[i+2] <= df[zigzag_column].iloc[i] and df[zigzag_column].iloc[i+3] < df[zigzag_column].iloc[i+1]:
                            wave_numbers[i+2] = 'Wave 8'
                            wave_numbers[i+3] = 'Wave 9'

                            # Check for Wave 10 and Wave 11
                            if i+5 < len(df) and df[zigzag_column].iloc[i+5] < df[zigzag_column].iloc[i+3] and df[zigzag_column].iloc[i+4] < df[zigzag_column].iloc[i+2]:
                                wave_numbers[i+4] = 'Wave 10'
                                wave_numbers[i+5] = 'Wave 11'
                            else:
                                # Assign Wave a and Wave b
                                if i+5 < len(df) and df[zigzag_column].iloc[i+4] <= df[zigzag_column].iloc[i+2]:
                                    wave_numbers[i+4] = 'Wave a'
                                    wave_numbers[i+5] = 'Wave b'
                                    if i+6 < len(df) and df[zigzag_column].iloc[i+4] < df[zigzag_column].iloc[i+6]:
                                        wave_numbers[i+6] = 'Wave c'
                                    elif i+6 < len(df):
                                        # Reset a, b if c condition is not met
                                        wave_numbers[i+4] = None
                                        wave_numbers[i+5] = None
                                        wave_numbers[i+6] = None
                                elif i+5 < len(df):
                                    # Reset a, b if initial condition for a, b is not met
                                    wave_numbers[i+4] = None
                                    wave_numbers[i+5] = None
                        else:
                            # Assign Wave a, b, c
                            if i+3 <    len(df) and df[zigzag_column].iloc[i+2] <= df[zigzag_column].iloc[i]:
                                wave_numbers[i+2] = 'Wave a'
                                wave_numbers[i+3] = 'Wave b'
                                if i+4 < len(df) and df[zigzag_column].iloc[i+2] < df[zigzag_column].iloc[i+4]:
                                    wave_numbers[i+4] = 'Wave c'
                                elif i+4 < len(df):
                                    # Reset a, b, c if c condition is not met
                                    wave_numbers[i+2] = None
                                    wave_numbers[i+3] = None
                                    wave_numbers[i+4] = None
                    else:
                        # Alternative Wave a, b, c case
                        if df[zigzag_column].iloc[i] <= df[zigzag_column].iloc[i-2]:
                            wave_numbers[i] = 'Wave a'
                            wave_numbers[i+1] = 'Wave b'
                            if i+2 < len(df) and df[zigzag_column].iloc[i] < df[zigzag_column].iloc[i+2]:
                                wave_numbers[i+2] = 'Wave c'
                            elif i+2 < len(df):
                                # Reset a, b, c if c condition is not met
                                wave_numbers[i] = None
                                wave_numbers[i+1] = None
                                wave_numbers[i+2] = None
                else:
                    print_verbose(f"wave_numbers at 2nd else of 5.2 at index {6}: {wave_numbers[6]}")
                    # If condition fails, we check the next point by incrementing the index by 2 and re-evaluating the conditions
                    print_verbose(f"UpTrend Wave 6,7,8,9 or a,b,c condition failed at index {i}. Trying the next point for Wave 6,7,8,9 or a,b,c.")
                    # break
                    i += 2  # Increment by 2
                    if i+1 < len(df) and df[zigzag_column].iloc[i] > df[zigzag_column].iloc[i-1] and df[zigzag_column].iloc[i] <= df[zigzag_column].iloc[i-2] and wave_5_i2_flag_down == False and  wave_5_i4_flag_down == False:
                        if df[zigzag_column].iloc[i+1] > df[zigzag_column].iloc[i-1]:
                            wave_numbers[i] = 'Wave 6'
                            wave_numbers[i+1] = 'Wave 7'
                            # Check if another Higher High is forming or not:
                            if i+3 < len(df) and df[zigzag_column].iloc[i+2] >= df[zigzag_column].iloc[i] and df[zigzag_column].iloc[i+3] > df[zigzag_column].iloc[i+1]:
                                wave_numbers[i+2] = 'Wave 8'
                                wave_numbers[i+3] = 'Wave 9'
                                # Check if indices i+4 and i+5 exist
                                if i+5 < len(df) and df[zigzag_column].iloc[i+5] > df[zigzag_column].iloc[i+3] and df[zigzag_column].iloc[i+4] > df[zigzag_column].iloc[i+2]:
                                    wave_numbers[i+4] = 'Wave 10'
                                    wave_numbers[i+5] = 'Wave 11'
                                else:
                                    if i+5 < len(df) and df[zigzag_column].iloc[i+4] >= df[zigzag_column].iloc[i+2]:
                                        wave_numbers[i+4] = 'Wave a'
                                        wave_numbers[i+5] = 'Wave b'
                                        if i+6 < len(df) and df[zigzag_column].iloc[i+4] > df[zigzag_column].iloc[i+6]:
                                            wave_numbers[i+6] = 'Wave c'
                                        else:
                                            # Remove Wave a and Wave b if Wave c condition is not met
                                            wave_numbers[i+4] = None
                                            wave_numbers[i+5] = None
                                    elif i+5 < len(df):
                                        # Reset Wave a and Wave b if they were partially set
                                        wave_numbers[i+4] = None
                                        wave_numbers[i+5] = None
                            else:
                                if i+3 < len(df) and df[zigzag_column].iloc[i+2] >= df[zigzag_column].iloc[i]:
                                    wave_numbers[i+2] = 'Wave a'
                                    wave_numbers[i+3] = 'Wave b'
                                    if i+4 < len(df) and df[zigzag_column].iloc[i+2] > df[zigzag_column].iloc[i+4]:
                                        wave_numbers[i+4] = 'Wave c'
                                    elif i+4 < len(df):
                                        # Remove Wave a and Wave b if Wave c condition is not met
                                        wave_numbers[i+2] = None
                                        wave_numbers[i+3] = None
                                        wave_numbers[i+4] = None
                        else:
                            if df[zigzag_column].iloc[i] >= df[zigzag_column].iloc[i-2]:
                                wave_numbers[i] = 'Wave a'
                                wave_numbers[i+1] = 'Wave b'
                                if i+2 < len(df) and df[zigzag_column].iloc[i] > df[zigzag_column].iloc[i+2]:
                                    wave_numbers[i+2] = 'Wave c'
                                elif i+2 < len(df):
                                    # Remove Wave a and Wave b if Wave c condition is not met
                                    wave_numbers[i] = None
                                    wave_numbers[i+1] = None
                                    wave_numbers[i+2] = None
                    else:
                        break
        print_verbose(wave_numbers)
        # Check if 'Wave 1' exists in wave_numbers before attempting to find its index # # Remove None values
        if 'Wave 1' in wave_numbers:
            wave1_index = wave_numbers.index('Wave 1')
            print_verbose(f"Index of first occurrence of 'Wave 1': {wave1_index}")
            # Slice the lists to remove all None values before the index
            wave_numbers = wave_numbers[wave1_index:]
            # Find the index of the last non-None value in wave_numbers
            last_non_none_index = len(wave_numbers) - 1
            while last_non_none_index >= 0 and wave_numbers[last_non_none_index] is None:
                last_non_none_index -= 1
            # Trim the lists to remove trailing None values, keeping leading None intact in wave_numbers_outer
            wave_numbers = wave_numbers[:last_non_none_index + 1]
        else:
            print_verbose("'Wave 1' is not present in wave_numbers")
        # wave_numbers = [wave for wave in wave_numbers if wave is not None]
        print_verbose(wave_numbers)
        return wave_numbers

    def double_three(start_idx):
        # wave_numbers_inner = []  # Start with an empty list to avoid unnecessary None values
        # wave_numbers_outer = []
        # wave_numbers_inner.append('((a))')  # Adds '((a))' at the end of the list
        wave_numbers_inner = [None] * len(df)
        wave_numbers_outer = [None] * len(df)
        wave_numbers_inner[start_idx] = '((a))'  # First point is Wave 1
        current_wave_inner = "((a))"
        # current_wave_outer = " "  # Initialize current_wave_outer to avoid UnboundLocalError
        wavea1 = df[zigzag_column].iloc[start_idx]
        print_verbose(f"Double Three Wave ((a)) for Double Three Pattern: {wavea1}")
        for i in range(start_idx + 1, len(df)):
            if current_wave_inner =="((a))":
                # Only check i + 2 < len(df) as it's sufficient to cover both
                if i+1 < len(df):
                    wavea1 = df[zigzag_column].iloc[i-1]
                    waveb1 = df[zigzag_column].iloc[i]
                    wavec1 = df[zigzag_column].iloc[i+1]
                    prev_value = df[zigzag_column].iloc[start_idx-1]
                    if (waveb1 > prev_value) and (wavea1 > wavec1):
                        wave_numbers_inner[i] = '((b))'
                        wave_numbers_inner[i+1] = '((c))'
                        wave_numbers_outer[i+1] = 'W'
                        # wave_numbers_inner.append('((b))')
                        # wave_numbers_inner.append('((c))')
                        # # Add '((W))' at the same index as '((c))' in wave_numbers_outer
                        # wave_numbers_outer.append(None)  # Add placeholder for '((W))'
                        # wave_numbers_outer[-1] = '((W))'  # Set W in the same position as c
                        # wave_numbers_outer.append('((W))')
                        current_wave_inner = '((c1))'
                        print_verbose(wavea1,waveb1,wavec1)
                        print_verbose("wave a,b,c are present in Double Three and W is added")
                    else:
                        wave_numbers_inner = [] # Clear the list to reset the waves
                        wave_numbers_outer = [] # Clear the list to reset the waves
                        break

            elif current_wave_inner == "((c1))":
                # # Only check i + 2 < len(df) as it's sufficient to cover both
                if i + 3 < len(df):
                    waveb1 =  df[zigzag_column].iloc[i-1]
                    wavec1 =  df[zigzag_column].iloc[i]
                    wavea2 =  df[zigzag_column].iloc[i+1]
                    waveb2 =  df[zigzag_column].iloc[i+2]
                    wavec2 =  df[zigzag_column].iloc[i+3]
                    if (wavea2 > wavec1) and (wavea2 > waveb2) and (wavec2 > wavea2) and (waveb1 > wavec2):
                        wave_numbers_inner[i+1] = '((a))'
                        wave_numbers_inner[i+2] = '((b))'
                        wave_numbers_inner[i+3] = '((c))'
                        wave_numbers_outer[i+3] = 'X'
                        # wave_numbers_inner.append('((a))')
                        # wave_numbers_inner.append('((b))')
                        # wave_numbers_inner.append('((c))')
                        # wave_numbers_outer.append(None)  # Add placeholder for '((W))'
                        # wave_numbers_outer[-1] = '((X))'  # Set W in the same position as c
                        # # wave_numbers_outer.append('((X))')
                        current_wave_inner = '((c2))'
                        print_verbose("wave a,b,c are present in Double Three and X is added")
                    else:
                        wave_numbers_inner = [] # Clear the list to reset the waves
                        wave_numbers_outer = [] # Clear the list to reset the waves
                        break

            #Condition for ZigZag
            elif current_wave_inner == "((c2))":
                # Only check i + 5 < len(df) as it's sufficient to cover both
                if i+5 < len(df):
                    wavea2 =  df[zigzag_column].iloc[i]
                    wavec2 =  df[zigzag_column].iloc[i+2]
                    wavea3 =  df[zigzag_column].iloc[i+3]
                    waveb3 =  df[zigzag_column].iloc[i+4]
                    wavec3 =  df[zigzag_column].iloc[i+5]
                    if (wavec2 > wavea3) and (wavec2 > waveb3) and (wavea3 > wavec3):
                        wave_numbers_inner[i+3] = '((a))'
                        wave_numbers_inner[i+4] = '((b))'
                        wave_numbers_inner[i+5] = '((c))'
                        wave_numbers_outer[i+5] = 'Y'
                        # wave_numbers_inner.append('((a))')
                        # wave_numbers_inner.append('((b))')
                        # wave_numbers_inner.append('((c))')
                        # wave_numbers_outer.append('((Y))')
                        # wave_numbers_outer.append(None)  # Add placeholder for '((W))'
                        # wave_numbers_outer[-1] = '((W))'  # Set W in the same position as c
                        # current_wave_outer = 'Y'
                        print_verbose(wave_numbers_inner,wave_numbers_outer)
                        print_verbose("wave a3,b3,c3 are present in Double Three and Y is added")
                        break
                # Now, checking for the second condition
                if i+7 < len(df):
                    waved3 = df[zigzag_column].iloc[i+6]
                    wavee3 = df[zigzag_column].iloc[i+7]
                    if (wavec2 > waveb3) and wavee3 > max(wavec3,wavea3) and (waveb3 > waved3):
                        print_verbose("Check for Triangle")
                        wave_numbers_inner[i+3] = '((a))'
                        wave_numbers_inner[i+4] = '((b))'
                        wave_numbers_inner[i+5] = '((c))'
                        wave_numbers_inner[i+6] = '((d))'
                        wave_numbers_inner[i+7] = '((e))'
                        wave_numbers_outer[i+7] = 'Y'
                        # wave_numbers_inner.append('((a))')
                        # wave_numbers_inner.append('((b))')
                        # wave_numbers_inner.append('((c))')
                        # wave_numbers_inner.append('((d))')
                        # wave_numbers_inner.append('((e))')
                        # wave_numbers_outer.append('((Y))')
                        print_verbose("wave a3,b3,c3,d3,e3 are present in Double Three and Y is added")
                        break
                    else:
                        print_verbose("Pattern failed, resetting lists.")
                        wave_numbers_inner = [] # Clear the list to reset the waves
                        wave_numbers_outer = [] # Clear the list to reset the waves
                        break
            else:
                # wave_numbers_inner = [] # Clear the list to reset the waves
                # wave_numbers_outer = [] # Clear the list to reset the waves
                break

        # print_verbose("Before cleaning:")
        # print_verbose(wave_numbers_inner)  # Ensure this list is populated before cleaning
        # print_verbose(wave_numbers_outer)  # Ensure this list is populated before cleaning

        # Check if '((a))' exists in wave_numbers_inner before attempting to find its index
        if '((a))' in wave_numbers_inner:
            first_a_index = wave_numbers_inner.index('((a))')
            print_verbose(f"Index of first occurrence of '((a))': {first_a_index}")
            # Slice the lists to remove all None values before the index
            wave_numbers_inner = wave_numbers_inner[first_a_index:]
            wave_numbers_outer = wave_numbers_outer[first_a_index:]

            # Find the index of the last non-None value in wave_numbers_inner
            last_non_none_index_inner = len(wave_numbers_inner) - 1
            while last_non_none_index_inner >= 0 and wave_numbers_inner[last_non_none_index_inner] is None:
                last_non_none_index_inner -= 1

            # Find the index of the last non-None value in wave_numbers_outer
            last_non_none_index_outer = len(wave_numbers_outer) - 1
            while last_non_none_index_outer >= 0 and wave_numbers_outer[last_non_none_index_outer] is None:
                last_non_none_index_outer -= 1

            # Trim the lists to remove trailing None values, keeping leading None intact in wave_numbers_outer
            wave_numbers_inner = wave_numbers_inner[:last_non_none_index_inner + 1]
            wave_numbers_outer = wave_numbers_outer[:last_non_none_index_outer + 1]
        else:
            print_verbose("'((a))' is not present in wave_numbers_inner")

        # print_verboseing the cleaned lists to verify the replacement of None with ""
        print_verbose("After cleaning:")
        print_verbose(wave_numbers_inner)
        print_verbose(wave_numbers_outer)

        return wave_numbers_inner, wave_numbers_outer

    def triple_three(start_idx): # Flat , any three, double three, any three, zigzag
        wave_numbers_inner = [None] * len(df)
        wave_numbers_outer = [None] * len(df)
        wave_numbers_inner[start_idx] = '((a))'  # First point is Wave 1
        current_wave_inner = "((a))"
        # current_wave_outer = " "  # Initialize current_wave_outer to avoid UnboundLocalError
        wavea1 = df[zigzag_column].iloc[start_idx]
        print_verbose(f"Triple Three Wave ((a)): {wavea1}")
        for i in range(start_idx + 1, len(df)):
            if current_wave_inner =="((a))": # Flat
                # Only check i + 2 < len(df) as it's sufficient to cover both
                if i + 2 < len(df):
                    wavea1 = df[zigzag_column].iloc[i-1]
                    waveb1 = df[zigzag_column].iloc[i]
                    wavec1 = df[zigzag_column].iloc[i+1]
                    prev_value = df[zigzag_column].iloc[start_idx-1]
                    if (waveb1 > prev_value) and (wavea1 > wavec1):
                        # wave_numbers_inner[i-1] = '((a))'
                        wave_numbers_inner[i] = '((b))'
                        wave_numbers_inner[i+1] = '((c))'
                        current_wave_inner = '((c1))'
                        wave_numbers_outer[i+1] = 'W'
                        print_verbose("wave a1,b1,c1 are present in Triple Three and W is added")
                    else:
                        wave_numbers_inner = [] # Clear the list to reset the waves
                        wave_numbers_outer = [] # Clear the list to reset the waves
                        break

            elif current_wave_inner == "((c1))": # any three
                # Only check i + 2 < len(df) as it's sufficient to cover both
                if i + 3 < len(df):
                    waveb1 = df[zigzag_column].iloc[i-1]
                    wavec1 =  df[zigzag_column].iloc[i]
                    wavea2 =  df[zigzag_column].iloc[i+1]
                    waveb2 =  df[zigzag_column].iloc[i+2]
                    wavec2 =  df[zigzag_column].iloc[i+3]
                    print_verbose(waveb1)
                    if (wavea2 > wavec1) and (wavea2 > waveb2) and (wavec2 > wavea2) and (waveb1 > wavec2):
                        wave_numbers_inner[i+1] = '((a))'
                        wave_numbers_inner[i+2] = '((b))'
                        wave_numbers_inner[i+3] = '((c))'
                        wave_numbers_outer[i+3] = 'X'
                        current_wave_inner = '((c2))'
                        print_verbose("wave a2,b2,c2 are present in Triple Three and X is added")
                    else:
                        wave_numbers_inner = [] # Clear the list to reset the waves
                        wave_numbers_outer = [] # Clear the list to reset the waves
                        break

            elif current_wave_inner == '((c2))': # Double Three
                # Only check i + 2 < len(df) as it's sufficient to cover both
                if i + 5 < len(df):
                    wavea2 =  df[zigzag_column].iloc[i]
                    wavec2 =  df[zigzag_column].iloc[i+2]
                    wavew1 = df[zigzag_column].iloc[i+3]
                    wavex1 = df[zigzag_column].iloc[i+4]
                    wavey1 = df[zigzag_column].iloc[i+5]
                    if wavec2 > max(wavew1,wavex1,wavey1) and wavex1 > max(wavew1, wavey1) and (wavew1 > wavey1):
                        wave_numbers_inner[i+3] = '((w))'
                        wave_numbers_inner[i+4] = '((x))'
                        wave_numbers_inner[i+5] = '((y))'
                        wave_numbers_outer[i+5] = 'Y'
                        current_wave_inner = '((y1))'
                        print_verbose("wave w1,x1,y1 are present in Triple Three and Y is added")
                    else:
                        wave_numbers_inner = [] # Clear the list to reset the waves
                        wave_numbers_outer = [] # Clear the list to reset the waves
                        break

            elif current_wave_inner == "((y1))": # any three
                # Only check i + 2 < len(df) as it's sufficient to cover both
                if i + 7 < len(df):
                    waveb2 =  df[zigzag_column].iloc[i]
                    wavex1 = df[zigzag_column].iloc[i+3]
                    wavey1 =  df[zigzag_column].iloc[i+4]
                    wavea3 =  df[zigzag_column].iloc[i+5]
                    waveb3 =  df[zigzag_column].iloc[i+6]
                    wavec3 =  df[zigzag_column].iloc[i+7]
                    if (wavex1 > wavec3) and wavea3 > max(wavey1,waveb3) and wavec3 > max(wavea3,waveb3):
                        wave_numbers_inner[i+5] = '((a))'
                        wave_numbers_inner[i+6] = '((b))'
                        wave_numbers_inner[i+7] = '((c))'
                        wave_numbers_outer[i+7] = 'X'
                        current_wave_inner = '((c3))'
                        print_verbose("wave a3,b3,c3 are present in Triple Three and X is added")
                    else:
                        wave_numbers_inner = [] # Clear the list to reset the waves
                        wave_numbers_outer = [] # Clear the list to reset the waves
                        break

            #Condition for ZigZag
            elif current_wave_inner == "((c3))":
                # Only check i + 5 < len(df) as it's sufficient to cover both
                if i + 9 < len(df):
                    wavec2 =  df[zigzag_column].iloc[i]
                    wavey1 =  df[zigzag_column].iloc[i+3]
                    wavec3 =  df[zigzag_column].iloc[i+6]
                    wavea4 =  df[zigzag_column].iloc[i+7]
                    waveb4 =  df[zigzag_column].iloc[i+8]
                    wavec4 =  df[zigzag_column].iloc[i+9]
                    if (wavec3 > max(wavea4,waveb4,wavec4)) and waveb4 > max(wavea4,wavec4) and (wavea4 > wavec4) and wavey1 > max(wavea4,wavec4):
                        wave_numbers_inner[i+7] = '((a))'
                        wave_numbers_inner[i+8] = '((b))'
                        wave_numbers_inner[i+9] = '((c))'
                        wave_numbers_outer[i+9] = 'Z'
                        print_verbose("wave a4,b4,c4 are present in Triple Three and Z is added")
                    else:
                        wave_numbers_inner = [] # Clear the list to reset the waves
                        wave_numbers_outer = [] # Clear the list to reset the waves
                        break

            else:
                wave_numbers_inner = [] # Clear the list to reset the waves
                wave_numbers_outer = [] # Clear the list to reset the waves
                break

        # print_verbose("Before cleaning:")
        # print_verbose(wave_numbers_inner)  # Ensure this list is populated before cleaning
        # print_verbose(wave_numbers_outer)  # Ensure this list is populated before cleaning

        # Check if '((a))' exists in wave_numbers_inner before attempting to find its index
        if '((a))' in wave_numbers_inner:
            first_a_index = wave_numbers_inner.index('((a))')
            print_verbose(f"Index of first occurrence of '((a))': {first_a_index}")
            # Slice the lists to remove all None values before the index
            wave_numbers_inner = wave_numbers_inner[first_a_index:]
            wave_numbers_outer = wave_numbers_outer[first_a_index:]

            # Find the index of the last non-None value in wave_numbers_inner
            last_non_none_index_inner = len(wave_numbers_inner) - 1
            while last_non_none_index_inner >= 0 and wave_numbers_inner[last_non_none_index_inner] is None:
                last_non_none_index_inner -= 1

            # Find the index of the last non-None value in wave_numbers_outer
            last_non_none_index_outer = len(wave_numbers_outer) - 1
            while last_non_none_index_outer >= 0 and wave_numbers_outer[last_non_none_index_outer] is None:
                last_non_none_index_outer -= 1

            # Trim the lists to remove trailing None values, keeping leading None intact in wave_numbers_outer
            wave_numbers_inner = wave_numbers_inner[:last_non_none_index_inner + 1]
            wave_numbers_outer = wave_numbers_outer[:last_non_none_index_outer + 1]
        else:
            print_verbose("'((a))' is not present in wave_numbers_inner")

        # print_verboseing the cleaned lists to verify the replacement of None with ""
        print_verbose("After cleaning:")
        print_verbose(wave_numbers_inner)
        print_verbose(wave_numbers_outer)

        return wave_numbers_inner, wave_numbers_outer

        # # Before cleaning:
        # # [None, '((a))', '((b))', '((c))', '((a))', '((b))', '((c))', '((a))', '((b))', '((c))']
        # # [None, None, None, 'W', None, None, 'X', None, None, 'Y']
        # # Check if the 0th index of both lists is None, and if so, remove the first element
        # if wave_numbers_inner and wave_numbers_inner[0] is None:
        #     wave_numbers_inner.pop(0)  # Remove the first element if it is None

        # # Check if the 4th index is 'W'
        # if wave_numbers_outer and len(wave_numbers_outer) > 3 and wave_numbers_outer[3] == 'W':
        #     # Check if the 0th index is None, and remove it if true
        #     if wave_numbers_outer[0] is None:
        #         wave_numbers_outer.pop(0)

        # # Cleaning the lists (replacing None with "")
        # wave_numbers_inner_cleaned = [x if x is not None else "" for x in wave_numbers_inner]
        # wave_numbers_outer_cleaned = [x if x is not None else "" for x in wave_numbers_outer]

        # # print_verboseing the cleaned lists to verify the replacement of None with ""
        # print_verbose("After cleaning:")
        # print_verbose(wave_numbers_inner_cleaned)
        # print_verbose(wave_numbers_outer_cleaned)

        # # Check if 0th element is 'A' or Not, If not then Empty the list
        # if wave_numbers_inner_cleaned and wave_numbers_inner_cleaned[0] != '((a))':
        #     wave_numbers_inner_cleaned = []  # Clear the entire list if the condition is met
        # # Check if 0th element is 'A' or Not, If not then Empty the list
        # if wave_numbers_outer_cleaned and wave_numbers_outer_cleaned[2] != 'W':
        #     wave_numbers_outer_cleaned = []  # Clear the entire list if the condition is met

        # print_verbose("List wave_numbers_inner_cleaned:", wave_numbers_inner_cleaned)
        # print_verbose("List wave_numbers_outer_cleaned:", wave_numbers_outer_cleaned)

        # return wave_numbers_inner_cleaned, wave_numbers_outer_cleaned

    def triangles_d(start_idx,prev_idx,i_2):
        # # Initialize wave_numbers list based on the length of df
        wave_numbers = [None] * len(df)
        # Check if indices are valid
        if 0 <= prev_idx < len(df) and 0 <= start_idx < len(df):
            start_value = df[zigzag_column].iloc[prev_idx]
            end_value = df[zigzag_column].iloc[start_idx]
            start_datetime = df['Datetime'].iloc[prev_idx]
            end_datetime = df['Datetime'].iloc[start_idx]

            # print_verbose the relevant details including index and datetime
            print_verbose(f"DownTrend Triangle Wave A: {start_value} at index {prev_idx}, Datetime: {start_datetime}")
            print_verbose(f"DownTrend Triangle Wave B: {end_value} at index {start_idx}, Datetime: {end_datetime}")

            # Assign wave numbers
            wave_numbers[prev_idx] = 'A'
            wave_numbers[start_idx] = 'B'
        else:
            print_verbose(f"Invalid indices: prev_idx={prev_idx}, start_idx={start_idx}")
        current_wave ="B"

        for i in range(start_idx + 1, len(df)):
            if current_wave =="B":
                #Condition for Point C: 1. C > A (Ascending Triangle) 2. C = A (Descending Triangle)
                # 3. Contracting Triangle (C > A)
                if (df[zigzag_column].iloc[i] > df[zigzag_column].iloc[start_idx-2]) and (df[zigzag_column].iloc[start_idx] >= df[zigzag_column].iloc[start_idx-2]) and df[zigzag_column].iloc[i] <= df[zigzag_column].iloc[start_idx-1] and df[zigzag_column].iloc[i] > df[zigzag_column].iloc[start_idx]:
                    current_value = df[zigzag_column].iloc[i]
                    print_verbose(f"current_value for C, {current_value}")
                    wave_numbers[i] = 'C'
                    current_wave = "C"
                    print_verbose(f"DownTrend Triangle wave A,B,C are appended")

                #Condition 4 for Point C: Expanding Triangles (A > C) (df[zigzag_column].iloc[i] < df[zigzag_column].iloc[start_idx-1])
                elif (df[zigzag_column].iloc[start_idx] < df[zigzag_column].iloc[start_idx-2]) and df[zigzag_column].iloc[i] > df[zigzag_column].iloc[start_idx-1] and df[zigzag_column].iloc[i] > df[zigzag_column].iloc[start_idx]:
                    current_value = df[zigzag_column].iloc[i]
                    print_verbose(f"current_value for C is for Expanded Triangles, {current_value}")
                    wave_numbers[i] = 'C'
                    current_wave = "C Expanded Triangle"
                    print_verbose(f"DownTrend Triangle wave A,B,C are appended")
                else:
                    print_verbose("DownTrend Triangle Corrective Pattern Broken")
                    wave_numbers = [] # Clear the list to reset the waves
                    break

            elif current_wave == "C" or current_wave == "C Expanded Triangle":
                #Condition for Point D: 1. B > D (Descending Triangle) 2. D = B (Ascending Triangle)
                # 3. Contracting Triangle (B>D) (current_value <= df[zigzag_column].iloc[i-2])
                current_value = df[zigzag_column].iloc[i]
                print_verbose(f"Current Value for D, {current_value}")
                if current_wave == "C" and current_value >= df[zigzag_column].iloc[i-2] and current_value < df[zigzag_column].iloc[i-1]:
                    print_verbose("Started D")
                    wave_numbers[i] = 'D'
                    current_wave = "D"
                #Condition 4 for Point C: Expanding Triangles (D > B) >> current_value > df[zigzag_column].iloc[i-2]
                elif current_wave == "C Expanded Triangle" and current_value < df[zigzag_column].iloc[i-2] and current_value < df[zigzag_column].iloc[i-1]:
                    current_value = df[zigzag_column].iloc[i]
                    print_verbose(f"current_value for D Expande DownTrend Triangles, {current_value}")
                    wave_numbers[i] = 'D'
                    current_wave = "D Expanded Triangle"
                else:
                    wave_numbers = [] # Clear the list to reset the waves
                    break

            elif current_wave == "D" or current_wave == "D Expanded Triangle":
                #Condition for Point E: 1. E > C (Ascending Triangle) 2. E = C (Descending Triangle)
                # 3. Contracting Triangle (E > C) (current_value <= df[zigzag_column].iloc[i-2])
                current_value = df[zigzag_column].iloc[i]
                prev_value = df[zigzag_column].iloc[i-1]
                print_verbose(f"current_value for E, {current_value}")
                if current_wave == "D" and current_value > prev_value and current_value <= df[zigzag_column].iloc[i-2]:
                    wave_numbers[i] = 'E'
                    current_wave = "E"

                #Condition 4 for Point E: Expanding Triangles (C > E) >> current_value < df[zigzag_column].iloc[i-2]
                elif current_wave == "D Expanded Triangle" and current_value > prev_value  and current_value > df[zigzag_column].iloc[i-2]:
                    current_value = df[zigzag_column].iloc[i]
                    print_verbose(f"current_value for E Expanded DownTrend Triangles, {current_value}")
                    wave_numbers[i] = 'E'
                    current_wave = "E"

                else:
                    wave_numbers = [] # Clear the list to reset the waves
                    break
        # # Remove None values
        wave_numbers = [wave for wave in wave_numbers if wave is not None]
        print_verbose(wave_numbers)
        return wave_numbers

    def swing_high_low_d(start_idx):
        wave_numbers = [None] * len(df)
        wave_numbers[start_idx] = 'SL'  # First point is Wave 1
        current_wave = "SL"
        start_value = df[zigzag_column].iloc[start_idx]
        print_verbose(f"Swing High Uprtrend Wave 1: {start_value}")
        for i in range(start_idx + 1, len(df)):
            if current_wave == "SL":
                if (df[zigzag_column].iloc[start_idx-2] > start_value) and (df[zigzag_column].iloc[i] > start_value) and (df[zigzag_column].iloc[i] <= df[zigzag_column].iloc[start_idx -1]):
                    wave_numbers[i] = 'SH'
                    current_wave = "SH1"  # Move to the next wave
                else:
                    wave_numbers = [] # Clear the list to reset the waves
                    break
            elif current_wave == "SH1":
                if (df[zigzag_column].iloc[i] < df[zigzag_column].iloc[i-2]):
                    wave_numbers[i] = 'SL'
                    current_wave = "SL2"  # Move to the next wave
                else:
                    wave_numbers = [] # Clear the list to reset the waves
                    break
            elif current_wave == "SL2":
                if (df[zigzag_column].iloc[i] < df[zigzag_column].iloc[i-2]) and (df[zigzag_column].iloc[i] > df[zigzag_column].iloc[i-3]):
                    wave_numbers[i] = 'SH'
                    current_wave = "SH2"  # Move to the next wave
                else:
                    wave_numbers = [] # Clear the list to reset the waves
                    break
        # Remove None values
        wave_numbers = [wave for wave in wave_numbers if wave is not None]
        print_verbose(wave_numbers)
        return wave_numbers

    # Initialize wave number columns to empty values
    df['Wave Number Uptrend'] = [None] * len(df)
    df['Corrective Pattern inner numbers'] = [None] * len(df)
    df['Corrective Pattern outer numbers'] = [None] * len(df)
    # print_verbose(df['Wave Number Uptrend'])
    df['Wave Number Downtrend'] = [None] * len(df)
    df['Wave Number Swing High Low UpTrend'] = [None] * len(df)
    df['Wave Number Swing High Low DownTrend'] = [None] * len(df)
    # Main loop to detect the trend and assign waves
    for i in range(1, len(df)):
        if df[zigzag_column].iloc[i] > df[zigzag_column].iloc[i - 1]:
            print_verbose(f"Start Point of Uptrend Wave: {df[zigzag_column].iloc[i - 1]} having Datetime: {df['Datetime'].iloc[i - 1]}")
            print_verbose(f"End Point of Uptrend Wave: {df[zigzag_column].iloc[i]} having Datetime: {df['Datetime'].iloc[i]}")
            # If the next ZIGZAG point is higher, it's an uptrend
            wave_numbers_uptrend = assign_uptrend_waves(i,i - 1)
            # wave_numbers_triangles_u = triangles_u(i,i - 1, i-2)
            # wave_numbers_swing_high_low_u = swing_high_low_u(i)
            for idx in range(i, i + len(wave_numbers_uptrend)):
                if wave_numbers_uptrend[idx - i] is not None:  # Adjust index to match wave list
                    df.at[idx, 'Wave Number Uptrend'] = wave_numbers_uptrend[idx - i]
            # for idx in range(i, i + len(wave_numbers_triangles_u)): #Commented for 1m interval
            #     if [idx - i] is not None:  # Adjust index to match wave list
            #         df.at[idx - 1, 'Wave Number Uptrend'] = wave_numbers_triangles_u[idx - i]
            # for idx in range(i, i + len(wave_numbers_swing_high_low_u)):
            #     if [idx - i] is not None:  # Adjust index to match wave list
            #         df.at[idx, 'Wave Number Swing High Low UpTrend'] = wave_numbers_swing_high_low_u[idx - i]
            # break  # Stop after detecting the first trend and assigning waves
            # if dataframe_name == "df42":
            #     wave_numbers_swing_high_low_u = swing_high_low_u(i)
            #     for idx in range(i, i + len(wave_numbers_swing_high_low_u)):
            #         if [idx - i] is not None:  # Adjust index to match wave list
            #             df.at[idx, 'Wave Number Swing High Low UpTrend'] = wave_numbers_swing_high_low_u[idx - i]

        elif df[zigzag_column].iloc[i] < df[zigzag_column].iloc[i - 1]:
            print_verbose(f"Start Point of Downtrend Wave: {df[zigzag_column].iloc[i - 1]} having Datetime: {df['Datetime'].iloc[i - 1]}")
            print_verbose(f"End Point of Downtrend Wave: {df[zigzag_column].iloc[i]} having Datetime: {df['Datetime'].iloc[i]}")
            # If the next ZIGZAG point is lower, it's a downtrend
            wave_numbers_downtrend = assign_downtrend_waves(i)
            # wave_numbers_triangles_d = triangles_d(i,i - 1,i-2) #Commented for 1m interval
            # wave_numbers_swing_high_low_d = swing_high_low_d(i)

            # For all the wave numbers assigned, update the corresponding rows
            for idx in range(i, i + len(wave_numbers_downtrend)):
                if wave_numbers_downtrend[idx - i] is not None:  # Adjust index to match wave list
                    df.at[idx, 'Wave Number Downtrend'] = wave_numbers_downtrend[idx - i]

            # if dataframe_name == "df42":
            #     wave_numbers_swing_high_low_d = swing_high_low_d(i)
            #     for idx in range(i, i + len(wave_numbers_swing_high_low_d)):
            #         if [idx - i] is not None:  # Adjust index to match wave list
            #             df.at[idx, 'Wave Number Swing High Low DownTrend'] = wave_numbers_swing_high_low_d[idx - i]


            # for idx in range(i, i + len(wave_numbers_triangles_d)): #Commented for 1m interval
            #     if [idx - i] is not None:  # Adjust index to match wave list
            #         df.at[idx - 1, 'Wave Number Downtrend'] = wave_numbers_triangles_d[idx - i]

            # for idx in range(i, i + len(wave_numbers_swing_high_low_d)):
            #     if [idx - i] is not None:  # Adjust index to match wave list
            #         df.at[idx, 'Wave Number Swing High Low DownTrend'] = wave_numbers_swing_high_low_d[idx - i]

            #Required for df4 (1min interval)
            #wave_numbers_inner, wave_numbers_outer = flats(i)
            #wave_numbers_inner, wave_numbers_outer = zigzag(i)

            # for idx in range(i, i + len(wave_numbers_inner)):
            #    if wave_numbers_inner[idx - i] is not None:
            #         df.at[idx, 'Corrective Pattern inner numbers'] = wave_numbers_inner[idx - i]

            # for idx in range(i, i + len(wave_numbers_outer)):
            #    if wave_numbers_outer[idx -i] is not None:
            #         df.at[idx, 'Corrective Pattern outer numbers'] = wave_numbers_outer[idx - i]

            # Conditional logic for nested functions based on dataframe_name
            if dataframe_name == 'df4':
                # Run flats and zigzag for df4
                wave_numbers_inner, wave_numbers_outer = flats(i)
                for idx in range(i, i + len(wave_numbers_inner)):
                    if wave_numbers_inner[idx - i] is not None:
                        df.at[idx, 'Corrective Pattern inner numbers'] = wave_numbers_inner[idx - i]

                for idx in range(i, i + len(wave_numbers_outer)):
                    if wave_numbers_outer[idx -i] is not None:
                        df.at[idx, 'Corrective Pattern outer numbers'] = wave_numbers_outer[idx - i]

                wave_numbers_inner, wave_numbers_outer = zigzag(i)
                for idx in range(i, i + len(wave_numbers_inner)):
                    if wave_numbers_inner[idx - i] is not None:
                        df.at[idx, 'Corrective Pattern inner numbers'] = wave_numbers_inner[idx - i]

                for idx in range(i, i + len(wave_numbers_outer)):
                    if wave_numbers_outer[idx -i] is not None:
                        df.at[idx, 'Corrective Pattern outer numbers'] = wave_numbers_outer[idx - i]

            elif dataframe_name == 'df42':
                # Run double_three and triple_three for df42
                wave_numbers_inner, wave_numbers_outer = double_three(i)
                for idx in range(i, i + len(wave_numbers_inner)):
                    if wave_numbers_inner[idx - i] is not None:
                        df.at[idx, 'Corrective Pattern inner numbers'] = wave_numbers_inner[idx - i]

                for idx in range(i, i + len(wave_numbers_outer)):
                    if wave_numbers_outer[idx -i] is not None:
                        df.at[idx, 'Corrective Pattern outer numbers'] = wave_numbers_outer[idx - i]

                wave_numbers_inner, wave_numbers_outer = triple_three(i)
                for idx in range(i, i + len(wave_numbers_inner)):
                    if wave_numbers_inner[idx - i] is not None:
                        df.at[idx, 'Corrective Pattern inner numbers'] = wave_numbers_inner[idx - i]

                for idx in range(i, i + len(wave_numbers_outer)):
                    if wave_numbers_outer[idx -i] is not None:
                        df.at[idx, 'Corrective Pattern outer numbers'] = wave_numbers_outer[idx - i]

    if dataframe_name == 'df4': #Smaller Wave 0.01% Dev with 3 Legs
        # Forecasting Code for UpTrend Waves
        # # Dynamically calculate new dates based on the last 'Datetime' in df
        last_datetime = pd.to_datetime(df['Datetime'].iloc[-1])  # Get last datetime
        if interval == '1min':
            new_dates = pd.date_range(last_datetime + pd.Timedelta(minutes=1), periods=25, freq='min')  # Extend by 50 minutes
        elif interval == '5min':
            new_dates = pd.date_range(last_datetime + pd.Timedelta(minutes=5), periods=25, freq='min')
        elif interval == '10min':
            new_dates = pd.date_range(last_datetime + pd.Timedelta(minutes=10), periods=25, freq='min')
        elif interval == '15min':
            new_dates = pd.date_range(last_datetime + pd.Timedelta(minutes=15), periods=25, freq='min')
        elif interval == '30min':
            new_dates = pd.date_range(last_datetime + pd.Timedelta(minutes=30), periods=25, freq='30min')       # Generate new dates with 30-minute intervals
        elif interval == '1h':
            new_dates = pd.date_range(last_datetime + pd.Timedelta(hours=1), periods=25, freq='1h')
        else:
            raise ValueError("Invalid interval specified.")
        # # Check if the last wave number is 'Wave 1'
        # if df['Wave Number Uptrend'].iloc[-1] == 'Wave 1':
        #     # Get the last two rows
        #     start_point = df.iloc[-2][zigzag_column]  # Value from the second-to-last row
        #     end_point = df.iloc[-1][zigzag_column]    # Value from the last row

        #     # print_verbose the start and end points for the last pair of rows
        #     print_verbose(f"Start Point: {start_point}, End Point: {end_point}")

        #     # Calculate the difference between start and end points
        #     diff = end_point - start_point

        # # Wave2 Uptrend Range# fib_levels = {# '38.2%': start_value - (start_value - previous_value) * 0.382,# '85.1%': start_value - (start_value - previous_value) * 0.851# }
        # #fib_levels_wave_3 = {'161.8%': start_value + (wave_1_length * 1.618),  # 161.8% extension of Wave 1'261.8%': start_value + (wave_1_length * 2.618)   # 261.8% extension of Wave 1}
        # # fib_levels_wave_4 = {'14.6%': end_wave_3 - (wave_1_length * 0.146),  # 14.6% Retracement of Wave 3'38.2%': end_wave_3 - (wave_1_length * 0.382)   # 38.2% Retracement of Wave3}
        # #fib_levels_wave_5 = {'123.6%': end_wave_4 + (wave4_length * 1.236),  # 14.6% Retracement of Wave 3'161.8%': end_wave_4 + (wave4_length * 1.618)   # 38.2% Retracement of Wave 3}

        #     # Fibonacci extension levels (as percentages)
        #     fib_level_50 = end_point - diff * 0.50
        #     fib_level_161_8 = fib_level_50 + diff * 1.618
        #     fib_level_38_2 = fib_level_161_8 - diff * 0.382
        #     fib_level_61_8 = fib_level_38_2 + diff

        #     # Fibonacci extension levels (as percentages)
        #     fib_levels = {
        #         "50%": fib_level_50,
        #         "161.8%": fib_level_161_8,
        #         "38.2%": fib_level_38_2,
        #         "61.8%": fib_level_61_8  # wave 4 + length of wave 1
        #     }
        #     print_verbose(fib_levels)

        #     # Create new wave labels for the new rows
        #     new_waves = [None] * 25  # Initialize with None
        #     new_waves[6] = 'Wave 2.1'  # Add Wave 2 on the 3rd minute
        #     new_waves[13] = 'Wave 3.1'  # Add Wave 3 on the 6th minute
        #     new_waves[17] = 'Wave 4.1'  # Add Wave 4 on the 9th minute
        #     new_waves[23] = 'Wave 5.1'  # Add Wave 5 on the 15th minute

        #     # Create new data for the extended rows
        #     new_data = {
        #         'Datetime': new_dates,
        #         zigzag_column: [None] * 25,  # Initialize with None
        #         'Wave Number Uptrend': new_waves
        #     }

        #     # Assign Fibonacci levels to corresponding wave rows
        #     new_data[zigzag_column][6] = fib_levels["50%"]  # Wave 2 point
        #     new_data[zigzag_column][13] = fib_levels["161.8%"]  # Wave 3 point
        #     new_data[zigzag_column][17] = fib_levels["38.2%"]   # Wave 4 point
        #     new_data[zigzag_column][23] = fib_levels["61.8%"]   # Wave 5 point
        #     # Append the new rows to the original dataframe
        #     df = pd.concat([df, pd.DataFrame(new_data)], ignore_index=True)

        # # Check if the last wave number is either 'Wave 2.1' or 'Wave 2.2'
        if df['Wave Number Uptrend'].iloc[-1] in ['Wave 2.1', 'Wave 2.2']:
            start_point = df.iloc[-3][zigzag_column]  # Value from the Third Last row
            end_point = df.iloc[-2][zigzag_column]    # Value from the Second last row
            wave2_point = df.iloc[-1][zigzag_column]  #Wave2 point

            # print_verbose the start and end points for the last pair of rows
            print_verbose(f"Start Point: {start_point}, End Point: {end_point},Wave2 Point: {wave2_point}")
            # Calculate the difference between start and end points
            diff = end_point - start_point

            # Fibonacci extension levels (as percentages)
            fib_level_161_8 = wave2_point + diff * 1.618
            fib_level_38_2 = fib_level_161_8 - diff * 0.382
            fib_level_61_8 = fib_level_38_2 + diff

            # Store levels in a dictionary
            fib_levels = {
                "161.8%": fib_level_161_8,
                "38.2%": fib_level_38_2,
                "61.8%": fib_level_61_8,
            }
            print_verbose(fib_levels)
            # Create new wave labels for the new rows
            new_waves = [None] * 25  # Initialize with None
            new_waves[8] = 'Wave 3.1'  # Add Wave 3 on the 4th minute
            new_waves[13] = 'Wave 4.1'  # Add Wave 4 on the 6th minute
            new_waves[20] = 'Wave 5.1'  # Add Wave 5 on the 10th minute

            # Create new data for the extended rows
            new_data = {
                'Datetime': new_dates,
                zigzag_column: [None] * 25,  # Initialize with None
                'Wave Number Uptrend': new_waves
            }

            # Assign Fibonacci levels to corresponding wave rows
            new_data[zigzag_column][8] = fib_levels["161.8%"]  # Wave 3 point
            new_data[zigzag_column][13] = fib_levels["38.2%"]   # Wave 4 point
            new_data[zigzag_column][20] = fib_levels["61.8%"]   # Wave 5 point
            # Append the new rows to the original dataframe
            df = pd.concat([df, pd.DataFrame(new_data)], ignore_index=True)

        # Check if the last wave number is either 'Wave 3.1' or 'Wave 3.2'
        elif df['Wave Number Uptrend'].iloc[-1] in ['Wave 3.1', 'Wave 3.2'] or df['Wave Number Uptrend'].iloc[df['Close'].last_valid_index()-1:df['Close'].last_valid_index()+1].isin(['Wave 2.1', 'Wave 2.2']).any():
            start_point = df.iloc[-4][zigzag_column]  # Value from the Third Last row
            end_point = df.iloc[-3][zigzag_column]    # Value from the Second last row
            wave3_point = df.iloc[-1][zigzag_column]  #Wave3 point
            # Find the index of wave3_point in the zigzag_column column
            # wave3_index = df[df[zigzag_column] == wave3_point].index[-1]  # Get the index of the wave3_point
            # Replace the value in 'Wave Number Uptrend' for that index
            # df.iloc[wave3_index, df.columns.get_loc('Wave Number Uptrend')] = '3.' + str(df.iloc[wave3_index]['Wave Number Uptrend']).split('.')[1]
            # df.iloc[-1, df.columns.get_loc('Wave Number Uptrend')] = '3.' + str(df.iloc[-1]['Wave Number Uptrend']).split('.')[1]
            df.iloc[-1, df.columns.get_loc('Wave Number Uptrend')] = 'Wave 3.1' #Replace "Wave 2.1|Wave 2.2" with Wave 3.1

            # print_verbose the start and end points for the last pair of rows
            print_verbose(f"Start Point: {start_point}, End Point: {end_point},Wave3 Point: {wave3_point}")
            # Calculate the difference between start and end points
            diff = end_point - start_point
            # Fibonacci extension levels (as percentages)
            fib_level_38_2 = wave3_point - diff * 0.382
            fib_level_61_8 = fib_level_38_2 + diff
            # Fibonacci extension levels (as percentages)
            fib_levels = {
                "38.2%": fib_level_38_2,
                "61.8%": fib_level_61_8  # wave 4 + length of wave 1
            }
            print_verbose(fib_levels)
            # Create new wave labels for the new rows
            new_waves = [None] * 25  # Initialize with None
            new_waves[10] = 'Wave 4.1'  # Add Wave 3 on the 4th minute
            new_waves[18] = 'Wave 5.1'  # Add Wave 4 on the 6th minute

            # Create new data for the extended rows
            new_data = {
                'Datetime': new_dates,
                zigzag_column: [None] * 25,  # Initialize with None
                'Wave Number Uptrend': new_waves
            }
            # Assign Fibonacci levels to corresponding wave rows
            new_data[zigzag_column][10] = fib_levels["38.2%"]   # Wave 4 point
            new_data[zigzag_column][18] = fib_levels["61.8%"]   # Wave 5 point
            # Append the new rows to the original dataframe
            df = pd.concat([df, pd.DataFrame(new_data)], ignore_index=True)
        else:
            print_verbose("The last UpTrend wave is not 'Wave 1'. No new waves will be calculated.")

        # # Check if the last wave number is 'Wave 1'
        # if df['Wave Number Downtrend'].iloc[-1] == 'Wave 1' or (df['Wave Number Downtrend'].iloc[df['Close'].last_valid_index()] == 'Wave 1'):
        #     # Get the last two rows
        #     end_point = df.iloc[-2][zigzag_column]  # Value from the second-to-last row
        #     start_point = df.iloc[-1][zigzag_column]    # Value from the last row

        #     # Check if both start_point and end_point are valid (not None or NaN)
        #     if pd.notna(start_point) and pd.notna(end_point):
        #         print_verbose(f"Start Point: {start_point}, End Point: {end_point}")
        #     else:
        #         # Now you can access the row based on -1 and -2 from the last valid index
        #         start_point = df.iloc[df['Close'].last_valid_index() - 0][zigzag_column]  # Value from the row before the last valid index
        #         end_point = df.iloc[df['Close'].last_valid_index() - 1][zigzag_column]    # Value from the second row before the last valid index

        #     # print_verbose the start and end points for the last pair of rows
        #     print_verbose(f"Start Point: {start_point}, End Point: {end_point}")

        #     # Calculate the difference between start and end points
        #     diff = end_point - start_point

        #     # Fibonacci extension levels (as percentages)
        #     fib_level_50 = start_point + diff * 0.50
        #     fib_level_161_8 = fib_level_50 - diff * 1.618
        #     fib_level_38_2 = fib_level_161_8 + diff * 0.382
        #     fib_level_61_8 = fib_level_38_2 - diff

        #     # Fibonacci extension levels (as percentages)
        #     fib_levels = {
        #         "50%": fib_level_50,
        #         "161.8%": fib_level_161_8,
        #         "38.2%": fib_level_38_2,
        #         "61.8%": fib_level_61_8  # wave 4 + length of wave 1
        #     }
        #     print_verbose(fib_levels)

        #     # Create new wave labels for the new rows
        #     new_waves = [None] * 25  # Initialize with None
        #     new_waves[6] = 'Wave 2.1'  # Add Wave 2 on the 3rd minute
        #     new_waves[13] = 'Wave 3.1'  # Add Wave 3 on the 6th minute
        #     new_waves[17] = 'Wave 4.1'  # Add Wave 4 on the 9th minute
        #     new_waves[23] = 'Wave 5.1'  # Add Wave 5 on the 15th minute

        #     # Create new data for the extended rows
        #     new_data = {
        #         'Datetime': new_dates,
        #         zigzag_column: [None] * 25,  # Initialize with None
        #         'Wave Number Downtrend': new_waves
        #     }

        #     # Assign Fibonacci levels to corresponding wave rows
        #     new_data[zigzag_column][6] = fib_levels["50%"]  # Wave 2 point
        #     new_data[zigzag_column][13] = fib_levels["161.8%"]  # Wave 3 point
        #     new_data[zigzag_column][17] = fib_levels["38.2%"]   # Wave 4 point
        #     new_data[zigzag_column][23] = fib_levels["61.8%"]   # Wave 5 point
        #     # Append the new rows to the original dataframe
        #     df = pd.concat([df, pd.DataFrame(new_data)], ignore_index=True)

        # Check if the last wave number is either 'Wave 2.1' or 'Wave 2.2'
        if df['Wave Number Downtrend'].iloc[-1] in ['Wave 2.1', 'Wave 2.2'] or (df['Wave Number Downtrend'].iloc[df['Close'].last_valid_index()] in ['Wave 2.1', 'Wave 2.2']):
            # Get the last valid index of the 'Close' column
            last_valid_index = df['Close'].last_valid_index()

            # Get the last two rows
            end_point = df.iloc[-3][zigzag_column]  # Value from the second-to-last row
            start_point = df.iloc[-2][zigzag_column]    # Value from the last row
            wave2_point = df.iloc[-1][zigzag_column]  #Wave2 point

            # Check if both start_point and end_point are valid (not None or NaN)
            if pd.notna(start_point) and pd.notna(end_point):
                print_verbose(f"Start Point: {start_point}, End Point: {end_point}")
            else:
                # Now you can access the row based on -1 and -2 from the last valid index
                end_point = df.iloc[df['Close'].last_valid_index() - 2][zigzag_column]  # Value from the row before the last valid index
                start_point = df.iloc[df['Close'].last_valid_index() - 1][zigzag_column]    # Value from the second row before the last valid index
                wave2_point = df.iloc[last_valid_index][zigzag_column]
                print_verbose(f"Start Point: {start_point}, End Point: {end_point},Wave2 Point: {wave2_point}")

            # Calculate the difference between start and end points
            diff = end_point - start_point
            # Fibonacci extension levels (as percentages)
            fib_level_161_8 = wave2_point - diff * 1.618
            fib_level_38_2 = fib_level_161_8 + diff * 0.382
            fib_level_61_8 = fib_level_38_2 - diff

            # Store levels in a dictionary
            fib_levels = {
                "161.8%": fib_level_161_8,
                "38.2%": fib_level_38_2,
                "61.8%": fib_level_61_8,
            }
            print_verbose(fib_levels)
            # Create new wave labels for the new rows
            new_waves = [None] * 25  # Initialize with None
            new_waves[8] = 'Wave 3.1'  # Add Wave 3 on the 4th minute
            new_waves[13] = 'Wave 4.1'  # Add Wave 4 on the 6th minute
            new_waves[20] = 'Wave 5.1'  # Add Wave 5 on the 10th minute

            # Create new data for the extended rows
            new_data = {
                'Datetime': new_dates,
                zigzag_column: [None] * 25,  # Initialize with None
                'Wave Number Downtrend': new_waves
            }

            # Assign Fibonacci levels to corresponding wave rows
            new_data[zigzag_column][8] = fib_levels["161.8%"]    # Wave 3 point
            new_data[zigzag_column][13] = fib_levels["38.2%"]    # Wave 4 point
            new_data[zigzag_column][20] = fib_levels["61.8%"]    # Wave 5 point
            # Append the new rows to the original dataframe
            df = pd.concat([df, pd.DataFrame(new_data)], ignore_index=True)

        # Check if the last wave number is either 'Wave 3.1' or 'Wave 3.2'
        elif df['Wave Number Downtrend'].iloc[-1] in ['Wave 3.1', 'Wave 3.2'] or (df['Wave Number Downtrend'].iloc[df['Close'].last_valid_index()] in ['Wave 3.1', 'Wave 3.2']) or df['Wave Number Downtrend'].iloc[df['Close'].last_valid_index()-1:df['Close'].last_valid_index()+1].isin(['Wave 2.1', 'Wave 2.2']).any():
            end_point = df.iloc[-4][zigzag_column]  # Value from the Third Last row
            start_point = df.iloc[-3][zigzag_column]    # Value from the Second last row
            wave3_point = df.iloc[-1][zigzag_column]  #Wave3 point
            df.iloc[-1, df.columns.get_loc('Wave Number Downtrend')] = 'Wave 3.1' #Replace "Wave 2.1|Wave 2.2" with Wave 3.1
            # print_verbose the start and end points for the last pair of rows
            print_verbose(f"Start Point: {start_point}, End Point: {end_point},Wave3 Point: {wave3_point}")
            # Calculate the difference between start and end points
            diff = end_point - start_point
            # Fibonacci extension levels (as percentages)
            fib_level_38_2 = wave3_point + diff * 0.382
            fib_level_61_8 = fib_level_38_2 - diff

            # Fibonacci extension levels (as percentages)
            fib_levels = {
                "38.2%": fib_level_38_2,
                "61.8%": fib_level_61_8  # wave 4 + length of wave 1
            }
            print_verbose(fib_levels)
            # Create new wave labels for the new rows
            new_waves = [None] * 25  # Initialize with None
            new_waves[10] = 'Wave 4.1'  # Add Wave 3 on the 4th minute
            new_waves[18] = 'Wave 5.1'  # Add Wave 4 on the 6th minute

            # Create new data for the extended rows
            new_data = {
                'Datetime': new_dates,
                zigzag_column: [None] * 25,  # Initialize with None
                'Wave Number Downtrend': new_waves
            }
            # Assign Fibonacci levels to corresponding wave rows
            new_data[zigzag_column][10] = fib_levels["38.2%"]   # Wave 4 point
            new_data[zigzag_column][18] = fib_levels["61.8%"]   # Wave 5 point
            # Append the new rows to the original dataframe
            df = pd.concat([df, pd.DataFrame(new_data)], ignore_index=True)
        else:
            print_verbose("The last wave DownTrend is not 'Wave 1'. No new waves will be calculated.")

        # UpTrend Triangle Forecasting
        if df['Wave Number Uptrend'].iloc[-1] == 'C':
            print_verbose("Forecast for UpTrend Triangle point D and E")
            pt_b = df.iloc[-2][zigzag_column]
            pt_a = df.iloc[-3][zigzag_column]
            pt_c = df.iloc[-1][zigzag_column]
            print_verbose(pt_a,pt_b,pt_c)
            if pt_c >= pt_a: #It will be acending, symmetric,descending triangle
                new_waves = [None] * 25  # Initialize with None
                new_waves[6] = 'D'
                new_waves[11] = 'E'
                new_waves[17] = 'Up'
                # Create new data for the extended rows
                new_data = {
                    'Datetime': new_dates,
                    zigzag_column: [None] * 25,  # Initialize with None
                    'Wave Number Uptrend': new_waves
                }
                # Assign Fibonacci levels to corresponding wave rows
                new_data[zigzag_column][6] = pt_b - 0.15
                new_data[zigzag_column][11] = pt_a + 0.15
                new_data[zigzag_column][17] = pt_b + 5
                # Append the new rows to the original dataframe
                df = pd.concat([df, pd.DataFrame(new_data)], ignore_index=True)

            elif pt_a > pt_c: #Expanding UpTrend Triangle Forecasting
                new_waves = [None] * 25  # Initialize with None
                new_waves[6] = 'D'
                new_waves[11] = 'E'
                new_waves[17] = 'Up'
                # Create new data for the extended rows
                new_data = {
                    'Datetime': new_dates,
                    zigzag_column: [None] * 25,  # Initialize with None
                    'Wave Number Uptrend': new_waves
                }
                # Assign Fibonacci levels to corresponding wave rows
                new_data[zigzag_column][6] = pt_b + 2
                new_data[zigzag_column][11] = pt_c - 2
                new_data[zigzag_column][17] = pt_b + 5
                # Append the new rows to the original dataframe
                df = pd.concat([df, pd.DataFrame(new_data)], ignore_index=True)

        # DownTrend Triangle Forecasting
        if df['Wave Number Downtrend'].iloc[-1] == 'C':
            print_verbose("Forecast for DownTrend Triangle point D and E")
            pt_b = df.iloc[-2][zigzag_column]
            pt_a = df.iloc[-3][zigzag_column]
            pt_c = df.iloc[-1][zigzag_column]
            print_verbose(pt_a,pt_b,pt_c)
            if pt_a >= pt_c: #It will be DownTrend Triangle (acending, symmetric,descending
                new_waves = [None] * 25  # Initialize with None
                new_waves[6] = 'D'
                new_waves[11] = 'E'
                new_waves[17] = 'Up'
                # Create new data for the extended rows
                new_data = {
                    'Datetime': new_dates,
                    zigzag_column: [None] * 25,  # Initialize with None
                    'Wave Number Downtrend': new_waves
                }
                # Assign Fibonacci levels to corresponding wave rows
                new_data[zigzag_column][6] = pt_b + 0.15
                new_data[zigzag_column][11] = pt_c - 0.15
                new_data[zigzag_column][17] = pt_b - 5
                # Append the new rows to the original dataframe
                df = pd.concat([df, pd.DataFrame(new_data)], ignore_index=True)
            elif pt_c > pt_a: #Expanding DownTrend Triangle Forecasting
                new_waves = [None] * 25  # Initialize with None
                new_waves[6] = 'D'
                new_waves[11] = 'E'
                new_waves[17] = 'Down'
                # Create new data for the extended rows
                new_data = {
                    'Datetime': new_dates,
                    zigzag_column: [None] * 25,  # Initialize with None
                    'Wave Number Downtrend': new_waves
                }
                # Assign Fibonacci levels to corresponding wave rows
                new_data[zigzag_column][6] = pt_b - 2
                new_data[zigzag_column][11] = pt_c + 2
                new_data[zigzag_column][17] = pt_b - 5
                # Append the new rows to the original dataframe
                df = pd.concat([df, pd.DataFrame(new_data)], ignore_index=True)

    elif dataframe_name == "df42":
        # # Dynamically calculate new dates based on the last 'Datetime' in df
        last_datetime = pd.to_datetime(df['Datetime'].iloc[-1])  # Get last datetime
        if interval == '1min':
            new_dates = pd.date_range(last_datetime + pd.Timedelta(minutes=1), periods=50, freq='min')  # Extend by 50 minutes
        elif interval == '5min':
            new_dates = pd.date_range(last_datetime + pd.Timedelta(minutes=5), periods=50, freq='min')
        elif interval == '10min':
            new_dates = pd.date_range(last_datetime + pd.Timedelta(minutes=10), periods=50, freq='min')
        elif interval == '15min':
            new_dates = pd.date_range(last_datetime + pd.Timedelta(minutes=15), periods=50, freq='min')
        elif interval == '30min':
            new_dates = pd.date_range(last_datetime + pd.Timedelta(minutes=30), periods=50, freq='30min')       # Generate new dates with 30-minute intervals
        elif interval == '1h':
            new_dates = pd.date_range(last_datetime + pd.Timedelta(hours=1), periods=50, freq='1h')
        else:
            raise ValueError("Invalid interval specified.")

        # new_dates = pd.date_range(last_datetime + pd.Timedelta(minutes=1), periods=50, freq='min')  # Extend by 50 minutes

        # Check if the last wave number is 'Wave 1' >> Commented Wave 1 check and its Forecasting
        if df['Wave Number Uptrend'].iloc[-1] == 'Wave 1' and df['Wave Number Uptrend'].iloc[-2] not in ['Wave 2.1', 'Wave 2.2']:
            # Get the last two rows
            start_point = df.iloc[-2][zigzag_column]  # Value from the second-to-last row
            end_point = df.iloc[-1][zigzag_column]    # Value from the last row
            # print_verbose the start and end points for the last pair of rows
            print_verbose(f"Start Point: {start_point}, End Point: {end_point}")
            # Calculate the difference between start and end points
            diff = end_point - start_point

            # Wave2 Uptrend Range# fib_levels = {# '38.2%': start_value - (start_value - previous_value) * 0.382,# '85.1%': start_value - (start_value - previous_value) * 0.851# }
            #fib_levels_wave_3 = {'161.8%': start_value + (wave_1_length * 1.618),  # 161.8% extension of Wave 1'261.8%': start_value + (wave_1_length * 2.618)   # 261.8% extension of Wave 1}
            # fib_levels_wave_4 = {'14.6%': end_wave_3 - (wave_1_length * 0.146),  # 14.6% Retracement of Wave 3'38.2%': end_wave_3 - (wave_1_length * 0.382)   # 38.2% Retracement of Wave3}
            #fib_levels_wave_5 = {'123.6%': end_wave_4 + (wave4_length * 1.236),  # 14.6% Retracement of Wave 3'161.8%': end_wave_4 + (wave4_length * 1.618)   # 38.2% Retracement of Wave 3}

            # Fibonacci extension levels (as percentages)
            fib_level_38_4 = end_point - diff * 0.382
            fib_level_85_4 = end_point - diff * 0.85_4
            fib_level_100 = end_point - diff * 1

            # Fibonacci extension levels (as percentages)
            fib_levels = {
                "38.4%": fib_level_38_4,
                "85.4%": fib_level_85_4,
                # "100%": fib_level_100
            }
            print_verbose(fib_levels)

            # Create new columns for 161.8% and 261.8% ranges (initialize with None)
            range_38_4 = [None] * 50
            range_85_4 = [None] * 50
            # range_100 = [None] * 50
            # Assign values to the last 25 indices
            for i in range(5, 20):
                range_38_4[i] = fib_levels["38.4%"]
                range_85_4[i] = fib_levels["85.4%"]
                # range_100[i] = fib_levels["100%"]

            # Create new wave labels for the new rows
            new_waves = [None] * 50  # Initialize with None
            # new_waves[22] = 'Wave 2.1'  # Add Wave 2 on the 3rd minute
            # new_waves[34] = 'Wave 3.1'  # Add Wave 3 on the 6th minute
            # new_waves[40] = 'Wave 4.1'  # Add Wave 4 on the 9th minute
            # new_waves[49] = 'Wave 5.1'  # Add Wave 5 on the 15th minute

            new_data = {                                           # Create new data for the extended rows (for Wave 1)
                'Datetime': new_dates,
                zigzag_column: [None] * 50,                   # Initialize with None
                'Wave Number Uptrend': new_waves,      # Ensure correct wave labels
                # '100 range': range_100,
                '38_4 range': range_38_4,  # New column
                '85_4 range': range_85_4,  # New column
            }
            # Assign Fibonacci levels to corresponding wave rows
            # new_data[zigzag_column][22] = fib_levels["50%"]  # Wave 2 point
            # new_data[zigzag_column][34] = fib_levels["161.8%"]  # Wave 3 point
            # new_data[zigzag_column][40] = fib_levels["38.2%"]   # Wave 4 point
            # new_data[zigzag_column][49] = fib_levels["61.8%"]   # Wave 5 point

            # To avoid warning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes.
            # To retain the old behavior, exclude the relevant entries before the concat operation.
            new_data = {k: v for k, v in new_data.items() if any(val is not None for val in v)}

            # Append the new rows to the original dataframe
            df = pd.concat([df, pd.DataFrame(new_data)], ignore_index=True)

        # Check if the last wave number is either 'Wave 2.1' or 'Wave 2.2' >>  Commented Wave 1 check and its Forecasting
        elif df['Wave Number Uptrend'].iloc[-1] in ['Wave 2.1', 'Wave 2.2']:
            # rows_with_2_1 = df.tail(2)[df.tail(2)["Wave Number Uptrend"].str.contains('Wave 2.1|Wave 2.2', na=False)]
            # if rows_with_2_1.empty:
            start_point = df.iloc[-3][zigzag_column]  # Value from the Third Last row
            end_point = df.iloc[-2][zigzag_column]    # Value from the Second last row
            wave2_point = df.iloc[-1][zigzag_column]  #Wave2 point
            # else:
            #     # end_point_index = df.iloc[df['Wave Number Uptrend'].last_valid_index() -1: df['Wave Number Uptrend'].last_valid_index() + 1].loc[df['Corrective Pattern outer numbers'] == 'W'].index[0] if not df.iloc[df['Wave Number Uptrend'].last_valid_index() - 1: df['Wave Number Uptrend'].last_valid_index() + 1].loc[df['Wave Number Uptrend'] == 'W'].empty else None
            #     # end_point = df.iloc[end_point_index][zigzag_column]
            #     start_point = df.iloc[-3][zigzag_column]  # Value from the Third Last row
            #     end_point = df.iloc[-2][zigzag_column]    # Value from the Second last row
            #     wave2_point = df.iloc[-1][zigzag_column]  #Wave2 point

            # print_verbose the start and end points for the last pair of rows
            print_verbose(f"Start Point: {start_point}, End Point: {end_point},Wave2 Point: {wave2_point}")

            # Calculate the difference between start and end points
            diff = end_point - start_point

            # Fibonacci extension levels (as percentages)
            fib_level_161_8 = wave2_point + diff * 1.618
            fib_level_261_8 = wave2_point + diff * 2.618
            fib_level_100 = wave2_point + diff * 1
            fib_level_38_2 = fib_level_161_8 - diff * 0.382
            fib_level_61_8 = fib_level_38_2 + diff

            # Store levels in a dictionary
            fib_levels = {
                "161.8%": fib_level_161_8,
                "261.8%": fib_level_261_8,
                "100%": fib_level_100,
                "38.2%": fib_level_38_2,
                "61.8%": fib_level_61_8,
            }
            print_verbose(fib_levels)

            # Create new columns for 161.8% and 261.8% ranges (initialize with None)
            range_161_8 = [None] * 50
            range_261_8 = [None] * 50
            range_100 = [None] * 50

            # Assign values to the last 25 indices
            for i in range(15, 25):
                range_161_8[i] = fib_levels["161.8%"]
                range_261_8[i] = fib_levels["261.8%"]
                range_100[i] = fib_levels["100%"]

            # Create new wave labels for the new rows
            new_waves = [None] * 50  # Initialize with None
            new_waves[25] = 'Wave 3.1'  # Add Wave 3 on the 4th minute
            new_waves[35] = 'Wave 4.1'  # Add Wave 4 on the 6th minute
            new_waves[43] = 'Wave 5.1'  # Add Wave 5 on the 10th minute

            # Create new data for the extended rows
            new_data = {
                'Datetime': new_dates,
                zigzag_column: [None] * 50,  # Initialize with None
                'Wave Number Uptrend': new_waves,
                '100 range': range_100,
                '161_8 range': range_161_8,  # New column
                '261_8 range': range_261_8,  # New column
            }

            # Assign Fibonacci levels to corresponding wave rows , +2 , -2 as Offset values , removed during forecasting
            new_data[zigzag_column][25] = fib_levels["161.8%"] - 2 # Wave 3 point
            new_data[zigzag_column][35] = fib_levels["38.2%"]  + 2 # Wave 4 point
            new_data[zigzag_column][43] = fib_levels["61.8%"]  - 2 # Wave 5 point

            # To avoid warning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes.
            # To retain the old behavior, exclude the relevant entries before the concat operation.
            new_data = {k: v for k, v in new_data.items() if any(val is not None for val in v)}
            # Append the new rows to the original dataframe
            df = pd.concat([df, pd.DataFrame(new_data)], ignore_index=True)

        # Check if the last wave number is either 'Wave 3.1' or 'Wave 3.2'
        elif df['Wave Number Uptrend'].iloc[-1] in ['Wave 3.1', 'Wave 3.2']  or df['Wave Number Uptrend'].iloc[df['Close'].last_valid_index()-1:df['Close'].last_valid_index()+1].isin(['Wave 2.1', 'Wave 2.2']).any():
            start_point = df.iloc[-4][zigzag_column]  # Value from the Third Last row
            end_point = df.iloc[-3][zigzag_column]    # Value from the Second last row
            wave3_point = df.iloc[-1][zigzag_column]  #Wave3 point
            wave3_point_start = df.iloc[-2][zigzag_column]  #Wave3 point start
            # Find the index of wave3_point in the zigzag_column column
            # wave3_index = df[df[zigzag_column] == wave3_point].index[-1]  # Get the index of the wave3_point

            # Replace the value in 'Wave Number Uptrend' for that index
            # df.iloc[wave3_index, df.columns.get_loc('Wave Number Uptrend')] = '3.' + str(df.iloc[wave3_index]['Wave Number Uptrend']).split('.')[1]
            df.iloc[-1, df.columns.get_loc('Wave Number Uptrend')] = 'Wave 3.1' #Replace "Wave 2.1|Wave 2.2" with Wave 3.1
            # df.iloc[-1, df.columns.get_loc('Wave Number Uptrend')] = '3.' + str(df.iloc[-1]['Wave Number Uptrend']).split('.')[1]
            # print_verbose the start and end points for the last pair of rows
            print_verbose(f"Start Point: {start_point}, End Point: {end_point},Wave3 Point: {wave3_point}, ,Wave3 Point Start: {wave3_point_start}")
            # Calculate the difference between start and end points
            diff = wave3_point - wave3_point_start
            # Fibonacci extension levels (as percentages)
            fib_level_14_6 = wave3_point - diff * 0.146
            fib_level_38_4 = wave3_point - diff * 0.384
            fib_level_61_8 = fib_level_38_4 + diff
            fib_level_100 = wave3_point - diff * 1

            # Fibonacci extension levels (as percentages)
            fib_levels = {
                "14.6%": fib_level_14_6,
                "38.4%": fib_level_38_4,
                "61.8%": fib_level_61_8,  # wave 4 + length of wave 1
                "100%": fib_level_100
            }
            print_verbose(fib_levels)
            # Create new columns for 161.8% and 261.8% ranges (initialize with None)
            range_14_6 = [None] * 50
            range_38_4 = [None] * 50
            range_100 = [None] * 50
            # Assign values to the last 25 indices
            for i in range(30, 45):
                range_14_6[i] = fib_levels["14.6%"]
                range_38_4[i] = fib_levels["38.4%"]
                range_100[i] = fib_levels["100%"]
            # Create new wave labels for the new rows
            new_waves = [None] * 50  # Initialize with None
            new_waves[30] = 'Wave 4.1'  # Add Wave 3 on the 4th minute
            new_waves[40] = 'Wave 5.1'  # Add Wave 4 on the 6th minute
            # Create new data for the extended rows
            new_data = {
                'Datetime': new_dates,
                zigzag_column: [None] * 50,  # Initialize with None
                'Wave Number Uptrend': new_waves,
                '100 range': range_100,
                '14_6 range': range_14_6,  # New column
                '38_4 range': range_38_4,  # New column

            }
            # Assign Fibonacci levels to corresponding wave rows
            new_data[zigzag_column][30] = fib_levels["38.4%"] + 2  # Wave 4 point
            new_data[zigzag_column][40] = fib_levels["61.8%"] - 2  # Wave 5 point
            # To avoid warning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes.
            # To retain the old behavior, exclude the relevant entries before the concat operation.
            new_data = {k: v for k, v in new_data.items() if any(val is not None for val in v)}
            # Append the new rows to the original dataframe
            df = pd.concat([df, pd.DataFrame(new_data)], ignore_index=True)
        else:
            print_verbose("The last UpTrend wave is not 'Wave 1'. No new waves will be calculated.")

        # # # Check if the last wave number is 'Wave 1' >> Commented Wave 1 check and its Forecasting
        if "Wave 1" in df.loc[:df.last_valid_index(), 'Wave Number Downtrend'].values and not any(x in df.loc[:df.last_valid_index(), 'Wave Number Downtrend'].values for x in ["Wave 2.1", "Wave 2.2"]):
            # if (df['Wave Number Downtrend'].iloc[-1] == 'Wave 1' or df['Wave Number Downtrend'].iloc[df['Close'].last_valid_index()] == 'Wave 1') and (df['Wave Number Downtrend'].iloc[df['Close'].last_valid_index() - 2] not in ['Wave 2.1', 'Wave 2.2']):
            end_point = df.iloc[-2][zigzag_column]  # Value from the second-to-last row
            start_point = df.iloc[-1][zigzag_column]    # Value from the last row

            # Check if both start_point and end_point are valid (not None or NaN)
            if pd.notna(start_point) and pd.notna(end_point):
                print_verbose(f"Start Point: {start_point}, End Point: {end_point}")
            else:
                # Now you can access the row based on -1 and -2 from the last valid index
                start_point = df.iloc[df['Close'].last_valid_index() - 0][zigzag_column]  # Value from the row before the last valid index
                end_point = df.iloc[df['Close'].last_valid_index() - 1][zigzag_column]    # Value from the second row before the last valid index

            # print_verbose the start and end points for the last pair of rows
            print_verbose(f"Start Point: {start_point}, End Point: {end_point}")
            # Calculate the difference between start and end points
            diff = end_point - start_point
            # Fibonacci extension levels (as percentages)
            fib_level_38_4 = start_point + diff * 0.384
            fib_level_85_4 = start_point + diff * 0.854
            # fib_level_100 = start_point + diff * 1
            # Fibonacci extension levels (as percentages)
            fib_levels = {
                "38.4%": fib_level_38_4,
                "85.4%": fib_level_85_4
                # "100%": fib_level_100
            }
            # Create new columns for 161.8% and 261.8% ranges (initialize with None)
            range_38_4 = [None] * 50
            range_85_4 = [None] * 50
            range_100 = [None] * 50
            # Assign values to the last 25 indices
            for i in range(5, 20):
                range_38_4[i] = fib_levels["38.4%"]
                range_85_4[i] = fib_levels["85.4%"]
                # range_100[i] = fib_levels["100%"]
            # Create new wave labels for the new rows
            new_waves = [None] * 50  # Initialize with None
            # new_waves[25] = 'Wave 2.1'  # Add Wave 2 on the 3rd minute
            # new_waves[35] = 'Wave 3.1'  # Add Wave 3 on the 6th minute
            # new_waves[40] = 'Wave 4.1'  # Add Wave 4 on the 9th minute
            # new_waves[49] = 'Wave 5.1'  # Add Wave 5 on the 15th minute

            # Create new data for the extended rows
            new_data = {
                'Datetime': new_dates,
                zigzag_column: [None] * 50,  # Initialize with None
                'Wave Number Downtrend': new_waves,
                '38_4 range': range_38_4,  # New column
                '85_4 range': range_85_4,  # New column
                # '100 range': range_100
            }
            # To avoid warning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes.
            # To retain the old behavior, exclude the relevant entries before the concat operation.
            new_data = {k: v for k, v in new_data.items() if any(val is not None for val in v)}
            # Append the new rows to the original dataframe
            df = pd.concat([df, pd.DataFrame(new_data)], ignore_index=True)

        #     # else:
        #         # last_datetime = pd.to_datetime(df['Datetime'].iloc[-1])
        #         # new_dates = pd.date_range(last_datetime + pd.Timedelta(minutes=1), periods=20, freq='min')  # Extend by 10 minutes
        #         # Create new wave labels for the new rows
        #         # new_waves = [None] * 20  # Initialize with None
        #         # new_waves[3] = 'Wave 2.1'  # Add Wave 2 on the 3rd minute
        #         # new_waves[7] = 'Wave 3.1'  # Add Wave 3 on the 6th minute
        #         # new_waves[10] = 'Wave 4.1'  # Add Wave 4 on the 9th minute
        #         # new_waves[14] = 'Wave 5.1'  # Add Wave 5 on the 15th minute

        #         # # Create new data for the extended rows
        #         # new_data = {
        #         #     'Datetime': new_dates,
        #         #     zigzag_column: [None] * 20,  # Initialize with None
        #         #     'Wave Number Downtrend':  [new_waves[i] for i in range(20)]
        #         # }

        #         # # Assign Fibonacci levels to corresponding wave rows
        #         # new_data[zigzag_column][3] = fib_levels["50%"]  # Wave 2 point
        #         # new_data[zigzag_column][7] = fib_levels["161.8%"]  # Wave 3 point
        #         # new_data[zigzag_column][11] = fib_levels["38.2%"]   # Wave 4 point
        #         # new_data[zigzag_column][18] = fib_levels["61.8%"]   # Wave 5 point
        #         # # Append the new rows to the original dataframe
        #         # df = pd.concat([df, pd.DataFrame(new_data)], ignore_index=True)
        #         # print_verbose(df)

        # Check if the last wave number is either 'Wave 2.1' or 'Wave 2.2' >> Commented Wave 1 check and its Forecasting
        elif df['Wave Number Downtrend'].iloc[-1] in ['Wave 2.1', 'Wave 2.2'] or (df['Wave Number Downtrend'].iloc[df['Close'].last_valid_index()] in ['Wave 2.1', 'Wave 2.2']):
            # Get the last valid index of the 'Close' column
            last_valid_index = df['Close'].last_valid_index()

            # Get the last two rows
            end_point = df.iloc[-3][zigzag_column]  # Value from the second-to-last row
            start_point = df.iloc[-2][zigzag_column]    # Value from the last row
            wave2_point = df.iloc[-1][zigzag_column]  #Wave2 point

            # Check if both start_point and end_point are valid (not None or NaN)
            if pd.notna(start_point) and pd.notna(end_point):
                print_verbose(f"Start Point: {start_point}, End Point: {end_point}")
            else:
                # Now you can access the row based on -1 and -2 from the last valid index
                end_point = df.iloc[df['Close'].last_valid_index() - 2][zigzag_column]  # Value from the row before the last valid index
                start_point = df.iloc[df['Close'].last_valid_index() - 1][zigzag_column]    # Value from the second row before the last valid index
                wave2_point = df.iloc[last_valid_index][zigzag_column]
                print_verbose(f"Start Point: {start_point}, End Point: {end_point},Wave2 Point: {wave2_point}")

            # Calculate the difference between start and end points
            diff = end_point - start_point
            # Fibonacci extension levels (as percentages)
            fib_level_161_8 = wave2_point - diff * 1.618
            fib_level_261_8 = wave2_point - diff * 2.618
            fib_level_100 = wave2_point - diff * 1
            fib_level_38_2 = fib_level_161_8 + diff * 0.382
            fib_level_61_8 = fib_level_38_2 - diff

            # Store levels in a dictionary
            fib_levels = {
                "161.8%": fib_level_161_8,
                "261.8%": fib_level_261_8,
                "100%" : fib_level_100,
                "38.2%": fib_level_38_2,
                "61.8%": fib_level_61_8,
            }
            print_verbose(fib_levels)
            # Create new columns for 161.8% and 261.8% ranges (initialize with None)
            range_161_8 = [None] * 50
            range_261_8 = [None] * 50
            range_100 = [None] * 50

            # Assign values to the last 25 indices
            for i in range(15, 25):
                range_161_8[i] = fib_levels["161.8%"]
                range_261_8[i] = fib_levels["261.8%"]
                range_100[i] = fib_levels["100%"]

            # Create new wave labels for the new rows
            new_waves = [None] * 50  # Initialize with None
            new_waves[25] = 'Wave 3.1'  # Add Wave 3 on the 25th minute
            new_waves[35] = 'Wave 4.1'  # Add Wave 4 on the 35th minute
            new_waves[43] = 'Wave 5.1'  # Add Wave 5 on the 43th minute

            # Create new data for the extended rows
            new_data = {
                'Datetime': new_dates,
                zigzag_column: [None] * 50,  # Initialize with None
                'Wave Number Downtrend':  new_waves, #[new_waves[i] for i in range(50)]
                '100 range': range_100,
                '161_8 range': range_161_8,  # New column
                '261_8 range': range_261_8  # New column
            }

            # Assign Fibonacci levels to corresponding wave rows , +2 , -2 as Offset values , removed during forecasting
            new_data[zigzag_column][25] = fib_levels["161.8%"] + 2 # Wave 3 point
            new_data[zigzag_column][35] = fib_levels["38.2%"]  - 2 # Wave 4 point
            new_data[zigzag_column][43] = fib_levels["61.8%"]  + 2 # Wave 5 point
            # To avoid warning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes.
            # To retain the old behavior, exclude the relevant entries before the concat operation.
            new_data = {k: v for k, v in new_data.items() if any(val is not None for val in v)}
            # Append the new rows to the original dataframe
            df = pd.concat([df, pd.DataFrame(new_data)], ignore_index=True)


        # Check if the last wave number is either 'Wave 3.1' or 'Wave 3.2'
        elif df['Wave Number Downtrend'].iloc[-1] in ['Wave 3.1', 'Wave 3.2'] or (df['Wave Number Downtrend'].iloc[df['Close'].last_valid_index()] in ['Wave 3.1', 'Wave 3.2']) or df['Wave Number Downtrend'].iloc[df['Close'].last_valid_index()-1:df['Close'].last_valid_index()+1].isin(['Wave 2.1', 'Wave 2.2']).any():
            end_point = df.iloc[-4][zigzag_column]  # Value from the Third Last row
            start_point = df.iloc[-3][zigzag_column]    # Value from the Second last row
            wave3_point = df.iloc[-1][zigzag_column]  #Wave3 point
            wave3_point_start = df.iloc[-2][zigzag_column]  #Wave3 point start
            df.iloc[-1, df.columns.get_loc('Wave Number Downtrend')] = 'Wave 3.1' #Replace "Wave 2.1|Wave 2.2" with Wave 3.1

            # print_verbose the start and end points for the last pair of rows
            print_verbose(f"Start Point: {start_point}, End Point: {end_point},Wave3 Point: {wave3_point},Wave 3 Point Start: {wave3_point_start}")
            # Calculate the difference between start and end points
            diff = wave3_point_start - wave3_point # In DownTrend EW Wave Start Point higher than end Point
            print_verbose(diff)
            # Fibonacci extension levels (as percentages)
            fib_level_14_6 = wave3_point + diff * 0.146
            fib_level_38_4 = wave3_point + diff * 0.384
            fib_level_61_8 = fib_level_38_4 - diff
            fib_level_100 = wave3_point + diff * 1

            # Fibonacci extension levels (as percentages)
            fib_levels = {
                "14.6%": fib_level_14_6,
                "38.4%": fib_level_38_4,
                "100%": fib_level_100,
                "61.8%": fib_level_61_8,  # wave 4 + length of wave 1
            }
            print_verbose(fib_levels)
            # Create new columns for 161.8% and 261.8% ranges (initialize with None)
            range_14_6 = [None] * 50
            range_38_4 = [None] * 50
            range_100 = [None] * 50
            # Assign values to the last 25 indices
            for i in range(30, 45):
                range_14_6[i] = fib_levels["14.6%"]
                range_38_4[i] = fib_levels["38.4%"]
                range_100[i] = fib_levels["100%"]
            # Create new wave labels for the new rows
            new_waves = [None] * 50  # Initialize with None
            new_waves[30] = 'Wave 4.1'  # Add Wave 3 on the 4th minute
            new_waves[40] = 'Wave 5.1'  # Add Wave 4 on the 6th minute
            # Create new data for the extended rows
            new_data = {
                'Datetime': new_dates,
                zigzag_column: [None] * 50,  # Initialize with None
                'Wave Number Downtrend': new_waves, #[new_waves[i] for i in range(50)]
                '14_6 range': range_14_6,  # New column
                '38_4 range': range_38_4,  # New column
                '100 range': range_100,
            }
            # Assign Fibonacci levels to corresponding wave rows, +2 , -2 as Offset values , removed during forecasting
            new_data[zigzag_column][30] = fib_levels["38.4%"] - 2  # Wave 4 point
            new_data[zigzag_column][40] = fib_levels["61.8%"] + 2  # Wave 5 point

            # To avoid warning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes.
            # To retain the old behavior, exclude the relevant entries before the concat operation.
            new_data = {k: v for k, v in new_data.items() if any(val is not None for val in v)}
            # Append the new rows to the original dataframe
            df = pd.concat([df, pd.DataFrame(new_data)], ignore_index=True)

        else:
            print_verbose("The last wave DownTrend is not 'Wave 1'. No new waves will be calculated.")

        # Double Three Forecasting for Double Three contains Flat and Triangle
        # Check if the last three rows of 'Corrective Pattern outer numbers' are exactly 'W'
        # print_verbose(f"{df.tail(55)}, Dataframe before Double/Triple Three")
        if any(df["Corrective Pattern outer numbers"].tail(3).notna() & df["Corrective Pattern outer numbers"].tail(3).str.contains('W')) or df['Corrective Pattern outer numbers'].iloc[df['Close'].last_valid_index()-2:df['Close'].last_valid_index()+1].isin(['W']).any(): #Last 3 rows
            print_verbose("Forecast Double Three for Point X,Y")
            last_valid_index = df['Close'].last_valid_index() # Get the last valid index of the 'Close' column
            # • Wave X = 50%, 61.8%, 76.4%, or 85.4% of wave W , • Wave Y = 61.8%, 100%, or 123.6% of wave W # Select the rows containing 'W' for last 3 rows
            rows_with_w = df.tail(3)[df.tail(3)["Corrective Pattern outer numbers"].str.contains('W', na=False)]
            if not rows_with_w.empty:
                end_point_index = rows_with_w.index[0]  # The index of the row containing 'W',  # Get the row containing 'W' (end_point)
                end_point = df.iloc[end_point_index][zigzag_column]
            else:
                end_point_index = df.iloc[df['Close'].last_valid_index() - 3: df['Close'].last_valid_index() + 1].loc[df['Corrective Pattern outer numbers'] == 'W'].index[0] if not df.iloc[df['Close'].last_valid_index() - 3: df['Close'].last_valid_index() + 1].loc[df['Corrective Pattern outer numbers'] == 'W'].empty else None
                end_point = df.iloc[end_point_index][zigzag_column]

            # Get the row just before the 'W' row (start_point)
            if end_point > 0:  # Ensure there's a previous row before 'W'
                start_point = df.iloc[end_point_index - 1][zigzag_column]
            else:
                start_point = None  # If there's no previous row, set start_point to None
            # print_verbose the start and end points for the last pair of rows
            print_verbose(f"Start Point: {start_point}, End Point: {end_point}")
            # Calculate the difference between start and end points, as its Corrective , Formula (Start - End) as Start > End
            diff = start_point - end_point
            # Fibonacci extension levels (as percentages) , 85.4 % of W for Wave X, 123.6% of W for Wave Y
            fib_level_85_4 = end_point + diff * 0.854
            fib_level_123_6 = fib_level_85_4 - diff * 1.236
            # Fibonacci extension levels (as percentages)
            fib_levels = {
                "85.4%": fib_level_85_4,
                "123.6%": fib_level_123_6,
            }
            print_verbose(fib_levels)

            # Create new wave labels for the new rows
            new_waves = [None] * 50  # Initialize with None
            new_waves[25] = 'X'  # Add Wave X on the 20th minute
            new_waves[48] = 'Y'  # Add Wave Y on the 48th minute

            # Create new data for the extended rows
            new_data = {
                'Datetime': new_dates,
                zigzag_column: [None] * 50,  # Initialize with None
                'Corrective Pattern outer numbers': new_waves
            }

            # Assign Fibonacci levels to corresponding wave rows
            new_data[zigzag_column][25] = fib_levels["85.4%"]  # Wave X point
            new_data[zigzag_column][48] = fib_levels["123.6%"]  # Wave Y point

            # Append the new rows to the original dataframe
            df = pd.concat([df, pd.DataFrame(new_data)], ignore_index=True)

        # Check if the last three rows of 'Corrective Pattern outer numbers' are exactly 'X'
        # As Point X is coming in Double Three and Triple Three Pattern, Two Conditions are added!
        elif any(df["Corrective Pattern outer numbers"].tail(3).notna() & df["Corrective Pattern outer numbers"].tail(3).str.contains('X')) or df['Corrective Pattern outer numbers'].iloc[df['Close'].last_valid_index()-2:df['Close'].last_valid_index()+1].isin(['X']).any():
            print_verbose("Forecast Double Three for Point Y")
            last_valid_index = df['Close'].last_valid_index() # Get the last valid index of the 'Close' column
            # • Wave X = 50%, 61.8%, 76.4%, or 85.4% of wave W , • Wave Y = 61.8%, 100%, or 123.6% of wave W # Select the rows containing 'W' for last 6 rows
            rows_with_w = df.tail(6)[df.tail(6)["Corrective Pattern outer numbers"].str.contains('W', na=False)] # Check if any rows contain 'W'
            rows_with_w_last_valid_index = df.iloc[last_valid_index - 5: last_valid_index + 1][df.iloc[last_valid_index - 5: last_valid_index + 1]["Corrective Pattern outer numbers"].str.contains('W', na=False)]
            print_verbose(f"rows_with_w_last_valid_index: {rows_with_w_last_valid_index} ")
            if not rows_with_w.empty or not rows_with_w_last_valid_index.empty: # If either condition is satisfied, execute the if statement
                if not rows_with_w.empty: # Check if rows_with_w is non-empty, and set the index and zigzag_column
                    end_point_index = rows_with_w.index[0]  # Get the index of the first 'W' in the last 6 rows
                else:
                    end_point_index = rows_with_w_last_valid_index.index[0] if not rows_with_w_last_valid_index.empty else None # If rows_with_w is empty, use rows_with_w_last_valid_index
                if end_point_index is not None: # Get the zigzag_column value from the end_point_index
                    end_point = df.iloc[end_point_index][zigzag_column]
                    print_verbose(f"End point index: {end_point_index}, End point: {end_point}")
                else:
                    print_verbose("No valid 'W' found, end_point is None.")
                # end_point_index = rows_with_w.index[0]  # The index of the row containing 'W',  # Get the row containing 'W' (end_point)
                # end_point = df.iloc[end_point_index][zigzag_column]
                # Get the row just before the 'W' row (start_point)
                if end_point > 0:  # Ensure there's a previous row before 'W'
                    start_point = df.iloc[end_point_index - 1][zigzag_column]
                else:
                    start_point = None  # If there's no previous row, set start_point to None

                print_verbose(f"Start Point: {start_point}, End Point: {end_point}") # print_verbose the start and end points for the last pair of rows
                # Calculate the difference between start and end points, as its Corrective , Formula (Start - End) as Start > End
                diff = start_point - end_point
                row_with_x = df.tail(3)[df.tail(3)["Corrective Pattern outer numbers"].str.contains('X', na=False)]
                # x_point = row_with_x.iloc[0][zigzag_column]
                if not row_with_x.empty:
                    x_point = row_with_x.iloc[0][zigzag_column]
                else:
                    # If no 'X' found in the last 3 rows, check the last 3 rows relative to the last valid index
                    row_with_x = df.iloc[last_valid_index - 3: last_valid_index + 1][df.iloc[last_valid_index - 3: last_valid_index + 1]["Corrective Pattern outer numbers"].str.contains('X', na=False)]
                    if not row_with_x.empty:
                        x_point = row_with_x.iloc[0][zigzag_column] # If a 'X' is found in this subset, get the zigzag_column value from that row
                    else:
                        x_point = None                 # If no 'X' found in the fallback subset, set y_point to None
                print_verbose(f"X Point: {x_point}")
                # fib_level_85_4 = end_point + diff * 0.854 # Fibonacci extension levels (as percentages) , 85.4 % of W for Wave X, 123.6% of W for Wave Y
                fib_level_123_6 = x_point - diff * 1.236
                # Fibonacci extension levels (as percentages)
                fib_levels = {
                    "123.6%": fib_level_123_6,
                }
                print_verbose(fib_levels)

                # Create new wave labels for the new rows
                new_waves = [None] * 50  # Initialize with None
                new_waves[33] = 'Y'  # Add Wave Y on the 28th minute

                # Create new data for the extended rows
                new_data = {
                    'Datetime': new_dates,
                    zigzag_column: [None] * 50,  # Initialize with None
                    'Corrective Pattern outer numbers': new_waves
                }

                # Assign Fibonacci levels to corresponding wave rows
                new_data[zigzag_column][33] = fib_levels["123.6%"]  # Wave Y point

                # Append the new rows to the original dataframe
                df = pd.concat([df, pd.DataFrame(new_data)], ignore_index=True)
            else:
                print_verbose("Forecast Triple Three for Point Z")
                # • Wave X = 50%, 61.8%, 76.4%, or 85.4% of wave W , • Wave Z = 61.8%, 100%, or 123.6% of wave W # Select the rows containing 'W' for last 12 rows
                rows_with_w = df.tail(12)[df.tail(12)["Corrective Pattern outer numbers"].str.contains('W', na=False)]
                # end_point_index = rows_with_w.index[0]  # The index of the row containing 'W',  # Get the row containing 'W' (end_point)
                # end_point = df.iloc[end_point_index][zigzag_column]

                if not rows_with_w.empty:
                    end_point_index = rows_with_w.index[0]  # The index of the row containing 'W',  # Get the row containing 'W' (end_point)
                    end_point = df.iloc[end_point_index][zigzag_column]
                else:
                    # end_point_index = df.iloc[df['Close'].last_valid_index() - 12: df['Close'].last_valid_index() + 1].loc[df['Corrective Pattern outer numbers'] == 'W'].index[0] if not df.iloc[df['Close'].last_valid_index() - 3: df['Close'].last_valid_index() + 1].loc[df['Corrective Pattern outer numbers'] == 'W'].empty else None
                    # end_point_index = df.iloc[last_valid_index - 12: last_valid_index + 1][df.iloc[last_valid_index - 12: last_valid_index + 1]["Corrective Pattern outer numbers"].str.contains('W', na=False)]
                    # print_verbose(end_point_index)
                    # end_point = df.iloc[end_point_index][zigzag_column]
                    end_point_index = df.iloc[df['Close'].last_valid_index() - 12: df['Close'].last_valid_index() + 1].loc[df['Corrective Pattern outer numbers'] == 'W'].index[0] if not df.iloc[df['Close'].last_valid_index() - 12: df['Close'].last_valid_index() + 1].loc[df['Corrective Pattern outer numbers'] == 'W'].empty else None
                    end_point = df.iloc[end_point_index][zigzag_column]

                # Get the row just before the 'W' row (start_point)
                if end_point > 0:  # Ensure there's a previous row before 'W'
                    start_point = df.iloc[end_point_index - 1][zigzag_column]
                else:
                    start_point = None  # If there's no previous row, set start_point to None
                # print_verbose the start and end points for the last pair of rows
                print_verbose(f"Start Point: {start_point}, End Point: {end_point}")
                diff = start_point - end_point # Calculate difference between start and end points, as its Corrective , Formula (Start - End) as Start > End

                row_with_x = df.tail(3)[df.tail(3)["Corrective Pattern outer numbers"].str.contains('X', na=False)]
                # x_point = row_with_x.iloc[0][zigzag_column]
                if not row_with_x.empty:
                    x_point = row_with_x.iloc[0][zigzag_column]
                else:
                    # If no 'X' found in the last 3 rows, check the last 3 rows relative to the last valid index
                    row_with_x = df.iloc[last_valid_index - 3: last_valid_index + 1][df.iloc[last_valid_index - 3: last_valid_index + 1]["Corrective Pattern outer numbers"].str.contains('X', na=False)]
                    if not row_with_x.empty:
                        x_point = row_with_x.iloc[0][zigzag_column] # If a 'X' is found in this subset, get the zigzag_column value from that row
                    else:
                        x_point = None                 # If no 'X' found in the
                print_verbose(f"X Point: {x_point}")
                # Fibonacci extension levels (as percentages) , 85.4 % of W for Wave X, 123.6% of W for Wave Y
                fib_level_123_6 = x_point - diff * 1.236
                # Fibonacci extension levels (as percentages)
                fib_levels = {
                    "123.6%": fib_level_123_6,
                }
                print_verbose(fib_levels)

                # Create new wave labels for the new rows
                new_waves = [None] * 50  # Initialize with None
                new_waves[35] = 'Z'  # Add Wave Z on the 30th minute

                # Create new data for the extended rows
                new_data = {
                    'Datetime': new_dates,
                    zigzag_column: [None] * 50,  # Initialize with None
                    'Corrective Pattern outer numbers': new_waves
                }

                # Assign Fibonacci levels to corresponding wave rows
                new_data[zigzag_column][35] = fib_levels["123.6%"]  # Wave Z point

                # Append the new rows to the original dataframe
                df = pd.concat([df, pd.DataFrame(new_data)], ignore_index=True)


        #Checking for Triple Three Pattern as an Extension of Double Three Pattern, Here Double Pattern will get completed with Wave Y
        # Check if the last three rows of 'Corrective Pattern outer numbers' are exactly 'Y'
        elif any(df["Corrective Pattern outer numbers"].tail(3).notna() & df["Corrective Pattern outer numbers"].tail(3).str.contains('Y')) or df['Corrective Pattern outer numbers'].iloc[df['Close'].last_valid_index()-2:df['Close'].last_valid_index()+1].isin(['Y']).any(): #Last 3 rows
            print_verbose("Forecast Triple Three for Point X,Z")
            last_valid_index = df['Close'].last_valid_index() # Get the last valid index of the 'Close' column
            # • Wave X = 50%, 61.8%, 76.4%, or 85.4% of wave W , • Wave Z = 61.8%, 100%, or 123.6% of wave W # Select the rows containing 'W' for last 9 rows
            # rows_with_w = df.tail(9)[df.tail(9)["Corrective Pattern outer numbers"].str.contains('W', na=False)]
            # # end_point_index = rows_with_w.index[0]  # The index of the row containing 'W',  # Get the row containing 'W' (end_point)
            # # end_point = df.iloc[end_point_index][zigzag_column]
            # if not rows_with_w.empty:
            #     end_point_index = rows_with_w.index[0]  # The index of the row containing 'W',  # Get the row containing 'W' (end_point)
            #     end_point = df.iloc[end_point_index][zigzag_column]
            # else:
            #     # end_point_index = df.iloc[last_valid_index - 9: last_valid_index + 1][df.iloc[last_valid_index - 9: last_valid_index + 1]["Corrective Pattern outer numbers"].str.contains('W', na=False)]
            #     # end_point_index = end_point_index.index[0]
            #     # end_point = df.iloc[end_point_index][zigzag_column]
            #     end_point_index = df.iloc[df['Close'].last_valid_index() - 9: df['Close'].last_valid_index() + 1].loc[df['Corrective Pattern outer numbers'] == 'W'].index[0] if not df.iloc[df['Close'].last_valid_index() - 9: df['Close'].last_valid_index() + 1].loc[df['Corrective Pattern outer numbers'] == 'W'].empty else None
            #     end_point = df.iloc[end_point_index][zigzag_column]

            # Row W at last 9th row come for a,b,c Pattern, For Traingle Pattern Row a,b,c,d,e end with Y at 11th Row So 9th will be empty.
            # Check for 'W' in the last 9 rows
            rows_with_w_9 = df.tail(9)[df.tail(9)["Corrective Pattern outer numbers"].str.contains('W', na=False)]
            print_verbose(rows_with_w_9)

            if not rows_with_w_9.empty:
                end_point_index = rows_with_w_9.index[0]  # First occurrence of 'W'
                end_point = df.loc[end_point_index, zigzag_column]  # Use .loc[] for safety
            else:
                subset_9 = df.iloc[df['Close'].last_valid_index() - 9: df['Close'].last_valid_index() + 1]
                w_indices_9 = subset_9.loc[subset_9["Corrective Pattern outer numbers"] == 'W'].index
                end_point_index = w_indices_9[0] if not w_indices_9.empty else None
                end_point = df.loc[end_point_index, zigzag_column] if end_point_index is not None else None
            print_verbose(f"9th Row Check -> Selected index: {end_point_index}, End point: {end_point}")

            # Check for 'W' in the last 11 rows
            rows_with_w_11 = df.tail(11)[df.tail(11)["Corrective Pattern outer numbers"].str.contains('W', na=False)]
            print_verbose(rows_with_w_11)

            if not rows_with_w_11.empty:
                end_point_index = rows_with_w_11.index[0]  # First occurrence of 'W'
                end_point = df.loc[end_point_index, zigzag_column]  # Use .loc[] for safety
            else:
                subset_11 = df.iloc[df['Close'].last_valid_index() - 11: df['Close'].last_valid_index() + 1]
                w_indices_11 = subset_11.loc[subset_11["Corrective Pattern outer numbers"] == 'W'].index
                end_point_index = w_indices_11[0] if not w_indices_11.empty else None
                end_point = df.loc[end_point_index, zigzag_column] if end_point_index is not None else None
            print_verbose(f"11th Row Check -> Selected index: {end_point_index}, End point: {end_point}")

            # Get the row just before the 'W' row (start_point)
            if end_point > 0:  # Ensure there's a previous row before 'W'
                start_point = df.iloc[end_point_index - 1][zigzag_column]
            else:
                start_point = None  # If there's no previous row, set start_point to None
            print_verbose(f"Start Point: {start_point}, End Point: {end_point}")         # print_verbose the start and end points for the last pair of rows

            diff = start_point - end_point # Calculate difference between start and end points, as its Corrective , Formula (Start - End) as Start > End

            row_with_y = df.tail(3)[df.tail(3)["Corrective Pattern outer numbers"].str.contains('Y', na=False)]
            if not row_with_y.empty:
                y_point = row_with_y.iloc[0][zigzag_column]
            else:
                # If no 'Y' found in the last 3 rows, check the last 3 rows relative to the last valid index
                row_with_y = df.iloc[last_valid_index - 3: last_valid_index + 1][df.iloc[last_valid_index - 3: last_valid_index + 1]["Corrective Pattern outer numbers"].str.contains('Y', na=False)]
                if not row_with_y.empty:
                    y_point = row_with_y.iloc[0][zigzag_column] # If a 'Y' is found in this subset, get the zigzag_column value from that row
                else:
                    y_point = None                 # If no 'Y' found in the fallback subset, set y_point to None
            # y_point = row_with_y.iloc[0][zigzag_column]
            print_verbose(f"Y Point: {y_point}")
            # Fibonacci extension levels (as percentages) , 85.4 % of W for Wave X, 123.6% of W for Wave Y
            fib_level_76_4 = y_point + diff * 0.764
            fib_level_123_6 = fib_level_76_4 - diff * 1.236
            # Fibonacci extension levels (as percentages)
            fib_levels = {
                "76.4%": fib_level_76_4,
                "123.6%": fib_level_123_6,
            }
            print_verbose(fib_levels)

            # Create new wave labels for the new rows
            new_waves = [None] * 50  # Initialize with None
            new_waves[30] = 'X'  # Add Wave X on the 20th minute
            new_waves[48] = 'Z'  # Add Wave Y on the 48th minute

            # Create new data for the extended rows
            new_data = {
                'Datetime': new_dates,
                zigzag_column: [None] * 50,  # Initialize with None
                'Corrective Pattern outer numbers': new_waves
            }

            # Assign Fibonacci levels to corresponding wave rows
            new_data[zigzag_column][30] = fib_levels["76.4%"]  # Wave X point
            new_data[zigzag_column][48] = fib_levels["123.6%"]  # Wave Y point

            # Append the new rows to the original dataframe
            df = pd.concat([df, pd.DataFrame(new_data)], ignore_index=True)
        else:
            print_verbose("The last wave Does not Contain Double Three, Triple Three Waves. No new waves will be Forecaseted.")

    return df

def fetch_data(df):

    df['Datetime'] = df.datetime
    df['Datetime'] = pd.to_datetime(df['Datetime'])
    if 'datetime' in df.columns:
        df = df.drop(columns=['datetime'])
    df2 = df.copy()

    df2.reset_index(drop=False, inplace=True)

    three_legs_value = 3
    three_legs_std_dev = 0.01
    max_three_legs_value = 8  # Prevent infinite loops
    ten_legs_value = 10
    ten_legs_std_dev = 0.01
    max_ten_legs_value = 15  # Prevent infinite loops

    # Initial ZigZag calculation for 3 legs
    zigzag_result = ta.zigzag(
        high=df2['High'], low=df2['Low'], close=df2['Close'], # High prices of the asset , # Low prices of the asset, # Closing prices of the asset , # Minimum number of price points required for a significant trend change,
        legs=three_legs_value, deviation=0.01, retrace=False, last_extreme=True, offset=0  # # Consider retraces before identifying new points,  # Consider the last extreme point in the calculation,
    )                                                                                  # No time offset, meaning Zigzag points will be calculated from the current time
    df2 = df2.join(zigzag_result)

    # Initial ZigZag calculation for 10 legs
    zigzag_result2 = ta.zigzag(
        high=df2['High'], low=df2['Low'], close=df2['Close'],
        legs=ten_legs_value, deviation=0.01, retrace=False, last_extreme=True, offset=0
    )
    df2 = df2.join(zigzag_result2,rsuffix='_zigzag')

    # Problem that can Occur: 1. The condition only checks the global average and does not ensure even distribution.
    # It could still satisfy the condition while having long gaps with no ZigZag points.
    # If ZigZag points are clustered in some areas and missing in others, the logic won’t fix it.

    # Function to recalculate ZigZag for new legs value
    def new_legs(df, legs_value, std_dev_value):
        zigzag_col = f"ZIGZAGv_{std_dev_value}%_{legs_value}"
        # print_verbose(f"Trying ten_legs_value: {legs_value}, Column: {zigzag_col}")  # Debugging
        # Recalculate ZigZag for the updated ten_legs_value
        zigzag_result2 = ta.zigzag(
            high=df['High'], low=df['Low'], close=df['Close'],
            legs=legs_value, deviation=std_dev_value, retrace=False, last_extreme=True, offset=0
        )
        # Drop the previous zigzag column (avoid KeyError if it doesn't exist)
        prev_col = f"ZIGZAGv_{std_dev_value}%_{legs_value - 1}" #I If Incremented then {std_dev_value - 0.04}%
        # print(prev_col)
        if prev_col in df.columns:
            df = df.drop(columns=[prev_col])
        # Join new ZigZag result
        df = df.join(zigzag_result2, rsuffix='_zigzag')
        return df  # Return updated dataframe

    # Function to check if last 100 rows have at least 10 non-null ZigZag values
    def three_legs_condition_satisfied(df, legs_value, three_legs_std_dev):
        zigzag_col = f"ZIGZAGv_{three_legs_std_dev}%_{legs_value}"  # Generate column name
        if zigzag_col not in df.columns:  # Prevent KeyError
            # print(f"Column {zigzag_col} not found in dataframe.")
            return False  # Return False until the column is found
        last_60_rows = df.tail(60)  # Slice last 60 rows
        three_legs_notnan_rows = last_60_rows[zigzag_col].notna().sum()  # Count non-null values
        # print(f"Checking {zigzag_col} on last 60 rows:") # Debug prints
        # print(f"Non-null ZigZag count: {three_legs_notnan_rows}")
        # print(f"Required Minimum: 15 (Current: {three_legs_notnan_rows})\n")
        return three_legs_notnan_rows < 15 # Continue if non-null values are fewer than 10

    while three_legs_value < max_three_legs_value:
        if not three_legs_condition_satisfied(df2, three_legs_value, three_legs_std_dev):
            # print(f"Condition met for three_legs_value: {three_legs_value}")
            break  # Exit the loop if the condition is satisfied
        three_legs_value += 1 # Increment legs by 1
        # three_legs_std_dev += 0.04
        df2 = new_legs(df2, three_legs_value,three_legs_std_dev) # Update df2 with the new legs value
        zigzag_col_three_legs = f"ZIGZAGv_{three_legs_std_dev}%_{three_legs_value}"
        # print(zigzag_col_three_legs)
        if zigzag_col_three_legs in df2.columns: # # Ensure the new column exists before renaming
            df2 = df2.rename(columns={zigzag_col_three_legs: "ZIGZAGv_0.01%_3"})

    # Function to check if last 100 rows have at least 10 non-null ZigZag values
    def ten_legs_condition_satisfied(df, legs_value, ten_legs_std_dev):
        zigzag_col = f"ZIGZAGv_{ten_legs_std_dev}%_{legs_value}"  # Generate column name
        if zigzag_col not in df.columns:  # Prevent KeyError
            # print_verbose(f"Column {zigzag_col} not found in dataframe.")
            return False  # Return False until the column is found
        last_100_rows = df.tail(100)  # Slice last 100 rows
        ten_legs_notnan_rows = last_100_rows[zigzag_col].notna().sum()  # Count non-null values
        # print_verbose(f"Checking {zigzag_col} on last 100 rows:")  # Debug prints
        # print_verbose(f"Non-null ZigZag count: {ten_legs_notnan_rows}")
        # print_verbose(f"Required Minimum: 10 (Current: {ten_legs_notnan_rows})\n")
        # Continue if non-null values are fewer than 10
        return ten_legs_notnan_rows < 5

    # Increment legs until the condition is satisfied or max_legs_value is reached
    while ten_legs_value < max_ten_legs_value:
        if not ten_legs_condition_satisfied(df2, ten_legs_value, ten_legs_std_dev):
            # print_verbose(f"Condition met for ten_legs_value: {ten_legs_value}")
            break  # Exit the loop if the condition is satisfied
        # Increment legs by 1
        ten_legs_value += 1
        # ten_legs_std_dev += 0.04
        # Update df2 with the new legs value
        df2 = new_legs(df2, ten_legs_value, ten_legs_std_dev)

    zigzag_col_ten_legs = f"ZIGZAGv_{ten_legs_std_dev}%_{ten_legs_value}"
    if zigzag_col_ten_legs in df2.columns: # # Ensure the new column exists before renaming
        df2 = df2.rename(columns={zigzag_col_ten_legs: "ZIGZAGv_0.01%_10"})
    # print(f"Final three_legs_value: {three_legs_value}")
    # print(f"Final ten_legs_value: {ten_legs_value}")

    # # ##Find last two non-NaN values >> BLue Wave
    # non_nan_indices = df2[df2['ZIGZAGv_0.01%_3'].notna()].index[-2:]
    # ## Ensure there are at least two non-NaN values and three NaNs after the second one
    # if len(non_nan_indices) >= 2:
    #     idx1, idx2 = non_nan_indices[0], non_nan_indices[1]
    #     value1, value2 = df2.at[idx1, 'ZIGZAGv_0.01%_3'], df2.at[idx2, 'ZIGZAGv_0.01%_3']
    #     ## Count NaNs after the second non-NaN value
    #     nan_count_after_idx2 = df2.loc[idx2 + 1:, 'ZIGZAGv_0.01%_3'].isna().sum()
    #     print(value1, value2)
    #     if nan_count_after_idx2 >= 1:
    #         if value1 > value2:
    #             ## Find the first occurrence of the highest 'High' value after idx2
    #             idx_min_low = df2.loc[idx2:, 'Low'].idxmin()
    #             idx_max_high = df2.loc[idx2:, 'High'].idxmax()
    #             min_low_value = df2.loc[idx_min_low, 'Low']
    #             max_high_value = df2.loc[idx_max_high, 'High']
    #             # print(min_low_value,max_high_value)
    #             # if df2.at[idx_max_high, 'High'] < value2:
    #             #     df2.at[idx_max_high, 'ZIGZAGv_0.01%_3'] = df2.at[idx_max_high, 'High']
    #             # else:
    #             #     ## If no new high is found, look for the lowest 'Low' value instead
    #             #     idx_min_low = df2.loc[idx2:, 'Low'].idxmin()
    #             #     df2.at[idx_min_low, 'ZIGZAGv_0.01%_3'] = df2.at[idx_min_low, 'Low']
    #             #     df2.at[idx2, 'ZIGZAGv_0.01%_3'] = pd.NA # Remove value2 (set to NaN) in the 'ZIGZAGv_0.01%_3' column
    #             if df2.at[idx_min_low, 'Low'] < value2:
    #                 df2.at[idx_min_low, 'ZIGZAGv_0.01%_3'] = df2.at[idx_min_low, 'Low']
    #                 # Set the second value (value2) to NaN as part of the wave progression
    #                 df2.at[idx2, 'ZIGZAGv_0.01%_3'] = pd.NA
    #             else:
    #                 df2.at[idx_max_high, 'ZIGZAGv_0.01%_3'] = df2.at[idx_max_high, 'High']

    #         elif value1 < value2:
    #             # print(value1,value2)
    #             ## Find the first occurrence of the lowest 'Low' value after idx2
    #             idx_min_low = df2.loc[idx2:, 'Low'].idxmin()
    #             idx_max_high = df2.loc[idx2:, 'High'].idxmax()
    #             min_low_value = df2.loc[idx_min_low, 'Low']
    #             max_high_value = df2.loc[idx_max_high, 'High']
    #             # print(min_low_value,max_high_value)
    #             # if df2.at[idx_min_low, 'Low'] < value2 and value1 < :
    #             #     df2.at[idx_min_low, 'ZIGZAGv_0.01%_3'] = df2.at[idx_min_low, 'Low']
    #             #     print("v2 > low")
    #             # else:
    #             #     ## If no new low is found, look for the highest 'High' value instead
    #             #     idx_max_high = df2.loc[idx2:, 'High'].idxmax()
    #             #     df2.at[idx_max_high, 'ZIGZAGv_0.01%_3'] = df2.at[idx_max_high, 'High']
    #             #     df2.at[idx2, 'ZIGZAGv_0.01%_3'] = pd.NA # Remove value2 (set to NaN) in the 'ZIGZAGv_0.01%_3' column
    #             #     print("If no new low is found, look for the highest 'High' value instead")
    #             # Update the row with the highest value only if it is greater than value2
    #             if df2.at[idx_max_high, 'High'] > value2:
    #                 df2.at[idx_max_high, 'ZIGZAGv_0.01%_3'] = df2.at[idx_max_high, 'High']
    #                 # Set the second value (value2) to NaN as part of the wave progression
    #                 df2.at[idx2, 'ZIGZAGv_0.01%_3'] = pd.NA
    #             else:
    #                 df2.at[idx_min_low, 'ZIGZAGv_0.01%_3'] = df2.at[idx_min_low, 'Low']

    # ##Find last two non-NaN values >> BLue Wave
    non_nan_indices = df2[df2['ZIGZAGv_0.01%_3'].notna()].index[-2:]
    ## Ensure there are at least two non-NaN values and three NaNs after the second one
    if len(non_nan_indices) >= 2:
        idx1, idx2 = non_nan_indices[0], non_nan_indices[1]
        value1, value2 = df2.at[idx1, 'ZIGZAGv_0.01%_3'], df2.at[idx2, 'ZIGZAGv_0.01%_3']
        ## Count NaNs after the second non-NaN value
        nan_count_after_idx2 = df2.loc[idx2 + 1:, 'ZIGZAGv_0.01%_3'].isna().sum()
        print(f"v1,v2: Blue wave: {value1,value2}")
        if nan_count_after_idx2 >= 1:
            if value1 > value2:
                ## Find the first occurrence of the highest 'High' value after idx2
                idx_min_low = df2.loc[idx2:, 'Low'].idxmin()
                idx_max_high = df2.loc[idx2:, 'High'].idxmax()
                min_low_value = df2.loc[idx_min_low, 'Low']
                max_high_value = df2.loc[idx_max_high, 'High']
                print(df2.at[idx_min_low, 'Low'], df2.at[idx_max_high, 'High'])

                # if df2.at[idx_min_low, 'Low'] < value2:
                #     df2.at[idx_min_low, 'ZIGZAGv_0.01%_3'] = df2.at[idx_min_low, 'Low']
                #     # Set the second value (value2) to NaN as part of the wave progression
                #     df2.at[idx2, 'ZIGZAGv_0.01%_3'] = pd.NA
                # elif df2.at[idx_min_low, 'Low'] == value2:
                #     df2.at[idx_min_low, 'ZIGZAGv_0.01%_10'] = df2.at[idx_min_low, 'Low']
                # else:
                #     df2.at[idx_max_high, 'ZIGZAGv_0.01%_3'] = df2.at[idx_max_high, 'High']
                #
                # v1,v2: Blue wave: (6062.0, 6060.25)
                # 6060.25 6061.75
                # Blue, v1 > v2  condition:2

                if df2.at[idx_min_low, 'Low'] < value2:
                    df2.at[idx_min_low, 'ZIGZAGv_0.01%_3'] = df2.at[idx_min_low, 'Low']
                    # Set the second value (value2) to NaN as part of the wave progression
                    df2.at[idx2, 'ZIGZAGv_0.01%_3'] = pd.NA
                    print("Blue, v1 > v2  condition:1")
                elif df2.at[idx_max_high, 'High'] > value2 and idx_max_high != idx2: #   v1,v2: Blue wave: (6062.0, 6060.25) and condition No Higher Higher after v2
                    df2.at[idx_max_high, 'ZIGZAGv_0.01%_3'] = df2.at[idx_max_high, 'High']
                    print("Blue, v1 > v2  condition:2")
                elif df2.at[idx_min_low, 'Low'] == value2:
                    df2.at[idx_min_low, 'ZIGZAGv_0.01%_3'] = df2.at[idx_min_low, 'Low']
                    print("Blue, v1 > v2  condition:3")

            elif value1 < value2:
                # print(value1,value2)
                ## Find the first occurrence of the lowest 'Low' value after idx2
                idx_min_low = df2.loc[idx2:, 'Low'].idxmin()
                idx_max_high = df2.loc[idx2:, 'High'].idxmax()
                min_low_value = df2.loc[idx_min_low, 'Low']
                max_high_value = df2.loc[idx_max_high, 'High']
                # print(min_low_value, max_high_value)
                # print(idx_min_low, idx_max_high)
                # print(min_low_value,max_high_value)
                # Update the row with the highest value only if it is greater than value2
                # if df2.at[idx_max_high, 'High'] > value2:
                #     df2.at[idx_max_high, 'ZIGZAGv_0.01%_3'] = df2.at[idx_max_high, 'High']
                #     # Set the second value (value2) to NaN as part of the wave progression
                #     df2.at[idx2, 'ZIGZAGv_0.01%_3'] = pd.NA
                # elif df2.at[idx_max_high, 'High'] == value2:
                #     df2.at[idx_max_high, 'ZIGZAGv_0.01%_10'] = df2.at[idx_max_high, 'High']
                # else:
                #     df2.at[idx_min_low, 'ZIGZAGv_0.01%_3'] = df2.at[idx_min_low, 'Low']

                if df2.at[idx_max_high, 'High'] > value2:
                    df2.at[idx_max_high, 'ZIGZAGv_0.01%_3'] = df2.at[idx_max_high, 'High']
                    # Set the second value (value2) to NaN as part of the wave progression
                    df2.at[idx2, 'ZIGZAGv_0.01%_3'] = pd.NA
                    print("Blue, v1 < v2  condition:1")
                elif df2.at[idx_min_low, 'Low'] < value2 and idx_min_low != idx2: #   v1,v2: Blue wave: (6062.0, 6060.25) and condition No Higher Higher after v2:
                    df2.at[idx_min_low, 'ZIGZAGv_0.01%_3'] = df2.at[idx_min_low, 'Low']
                    print("Blue, v1 < v2  condition:2")
                elif df2.at[idx_max_high, 'High'] == value2:
                    df2.at[idx_max_high, 'ZIGZAGv_0.01%_3'] = df2.at[idx_max_high, 'High']
                    print("Blue, v1 < v2  condition:3")

    ##Find last two non-NaN values >> Yellow Wave
    non_nan_indices = df2[df2['ZIGZAGv_0.01%_10'].notna()].index[-2:]
    ## Ensure there are at least two non-NaN values and three NaNs after the second one
    if len(non_nan_indices) >= 2:
        idx1, idx2 = non_nan_indices[0], non_nan_indices[1]
        value1, value2 = df2.at[idx1, 'ZIGZAGv_0.01%_10'], df2.at[idx2, 'ZIGZAGv_0.01%_10']
        print(f"v1,v2: Yellow wave: {value1,value2}")
        ## Count NaNs after the second non-NaN value
        nan_count_after_idx2 = df2.loc[idx2 + 1:, 'ZIGZAGv_0.01%_10'].isna().sum()
        if nan_count_after_idx2 >= 1:
            if value1 > value2:
                ## Find the first occurrence of the highest 'High' value after idx2
                idx_min_low = df2.loc[idx2:, 'Low'].idxmin()
                idx_max_high = df2.loc[idx2:, 'High'].idxmax()
                min_low_value = df2.loc[idx_min_low, 'Low']
                max_high_value = df2.loc[idx_max_high, 'High']
                print(min_low_value,max_high_value)
                print(df2.at[idx_min_low, 'Low'], df2.at[idx_max_high, 'High'])
                # print(min_low_value,max_high_value)
                # if df2.at[idx_max_high, 'High'] < value2:
                #     df2.at[idx_max_high, 'ZIGZAGv_0.01%_10'] = df2.at[idx_max_high, 'High']
                # else:
                #     ## If no new high is found, look for the lowest 'Low' value instead
                #     idx_min_low = df2.loc[idx2:, 'Low'].idxmin()
                #     df2.at[idx_min_low, 'ZIGZAGv_0.01%_10'] = df2.at[idx_min_low, 'Low']
                #     df2.at[idx2, 'ZIGZAGv_0.01%_10'] = pd.NA # Remove value2 (set to NaN) in the 'ZIGZAGv_0.01%_10' column
                if df2.at[idx_min_low, 'Low'] < value2:
                    df2.at[idx_min_low, 'ZIGZAGv_0.01%_10'] = df2.at[idx_min_low, 'Low']
                    # Set the second value (value2) to NaN as part of the wave progression
                    df2.at[idx2, 'ZIGZAGv_0.01%_10'] = pd.NA
                    print("Yellow, v1 > v2  condition:1")
                elif df2.at[idx_max_high, 'High'] > value2  and idx_max_high != idx2: #   v1,v2: Blue wave: (6062.0, 6060.25) and condition No Higher Higher after v2 : # and df2.at[idx_max_high, High']
                    df2.at[idx_max_high, 'ZIGZAGv_0.01%_10'] = df2.at[idx_max_high, 'High']
                    print("Yellow, v1 > v2  condition:2")
                elif df2.at[idx_min_low, 'Low'] == value2:
                    df2.at[idx_min_low, 'ZIGZAGv_0.01%_10'] = df2.at[idx_min_low, 'Low']
                    print("Yellow, v1 > v2  condition:3")

            elif value1 < value2:
                # print(value1,value2)
                ## Find the first occurrence of the lowest 'Low' value after idx2
                idx_min_low = df2.loc[idx2:, 'Low'].idxmin()
                idx_max_high = df2.loc[idx2:, 'High'].idxmax()
                min_low_value = df2.loc[idx_min_low, 'Low']
                max_high_value = df2.loc[idx_max_high, 'High']
                print(min_low_value,max_high_value)
                # if df2.at[idx_min_low, 'Low'] < value2 and value1 < :
                #     df2.at[idx_min_low, 'ZIGZAGv_0.01%_10'] = df2.at[idx_min_low, 'Low']
                #     print("v2 > low")
                # else:
                #     ## If no new low is found, look for the highest 'High' value instead
                #     idx_max_high = df2.loc[idx2:, 'High'].idxmax()
                #     df2.at[idx_max_high, 'ZIGZAGv_0.01%_10'] = df2.at[idx_max_high, 'High']
                #     df2.at[idx2, 'ZIGZAGv_0.01%_10'] = pd.NA # Remove value2 (set to NaN) in the 'ZIGZAGv_0.01%_10' column
                #     print("If no new low is found, look for the highest 'High' value instead")
                # Update the row with the highest value only if it is greater than value2
                if df2.at[idx_max_high, 'High'] > value2:
                    df2.at[idx_max_high, 'ZIGZAGv_0.01%_10'] = df2.at[idx_max_high, 'High']
                    # Set the second value (value2) to NaN as part of the wave progression
                    df2.at[idx2, 'ZIGZAGv_0.01%_10'] = pd.NA
                    print("Yellow, v1 < v2  condition:1")
                elif df2.at[idx_min_low, 'Low'] < value2 and idx_min_low != idx2: #   v1,v2: Blue wave: (6062.0, 6060.25) and condition No Higher Higher after v2::
                    df2.at[idx_min_low, 'ZIGZAGv_0.01%_10'] = df2.at[idx_min_low, 'Low']
                    print("Yellow, v1 < v2  condition:2")
                elif df2.at[idx_max_high, 'High'] == value2:
                    df2.at[idx_max_high, 'ZIGZAGv_0.01%_10'] = df2.at[idx_max_high, 'High']
                    print("Yellow, v1 < v2  condition:3")


    return  df2

def print_verbose(*args, **kwargs):
    """Custom print_verbose function that respects the global VERBOSE flag."""
    VERBOSE = False
    if VERBOSE:
        print_verbose(*args, **kwargs)

def plot_elliot_waves(plot, df, interval):

    df2 = fetch_data(df)
    # Save the original index before any modifications
    df2['original_index'] = df2.index
    df31 = df2.copy()
    df31 = df31.dropna(subset=['Datetime','ZIGZAGv_0.01%_3'])
    df31 = df31.reset_index()
    # Apply the function to assign wave numbers to df3 using ZIGZAGv_0.01%_3
    df4 = assign_wave_numbers(df31, zigzag_column="ZIGZAGv_0.01%_3",interval=interval,dataframe_name="df4")
    # Identify the last non-NaN value in 'original_index'
    last_valid_index = df4['original_index'].dropna().max()

    # Generate a sequence starting from the next index
    df4['original_index'] = df4['original_index'].combine_first(
        pd.Series(range(int(last_valid_index) + 1, int(last_valid_index) + 1 + len(df4)))
    )
    df4 = df4.set_index('original_index')  # Restore original index for alignment

    ##Check for non-null values in 'Wave Number Uptrend' and set 'Wave Number Swing High Low UpTrend' to None
    df4.loc[df4['Wave Number Uptrend'].notnull(), 'Wave Number Swing High Low UpTrend'] = None
    ## Check for non-null values in 'Wave Number Uptrend' and set 'Wave Number Swing High Low UpTrend' to None
    df4.loc[df4['Wave Number Downtrend'].notnull(), 'Wave Number Swing High Low DownTrend'] = None

    df32 = df2.copy()
    df32 = df32.dropna(subset=['Datetime','ZIGZAGv_0.01%_10'])
    df32 = df32.reset_index()

    # Apply the function to assign wave numbers to df3 using ZIGZAGv_0.1%_3
    # df42 = assign_wave_numbers(df32,zigzag_column="ZIGZAGv_0.01%_10",dataframe_name="df42")
    df42 = assign_wave_numbers(df32, zigzag_column="ZIGZAGv_0.01%_10",interval=interval,dataframe_name="df42")

    # Identify the last non-NaN value in 'original_index'
    last_valid_index = df42['original_index'].dropna().max()

    # Generate a sequence starting from the next index
    df42['original_index'] = df42['original_index'].combine_first(
        pd.Series(range(int(last_valid_index) + 1, int(last_valid_index) + 1 + len(df42)))
    )
    df42 = df42.set_index('original_index')  # Restore original index for alignment

    ##Check for non-null values in 'Wave Number Uptrend' and set 'Wave Number Swing High Low UpTrend' to None
    df42.loc[df42['Wave Number Uptrend'].notnull(), 'Wave Number Swing High Low UpTrend'] = None
    ## Check for non-null values in 'Wave Number Uptrend' and set 'Wave Number Swing High Low UpTrend' to None
    df42.loc[df42['Wave Number Downtrend'].notnull(), 'Wave Number Swing High Low DownTrend'] = None

    def update_wave_numbers(df, column_name):
        # Initialize variables to track the previous waves
        previous_wave = None
        second_previous_wave = None
        third_previous_wave = None
        fourth_previous_wave = None
        # Initialize an empty list to store the updated wave values
        updated_wave_numbers = []
        for index, row in df.iterrows():
            value = row[column_name]
            # Only process if the value is not NaN
            if pd.notna(value):
                if value == "Wave 1":
                    # Check if any of the previous waves is "Wave 1" or "Wave 1.1"
                    if (previous_wave == "Wave 1" or second_previous_wave == "Wave 1" or
                            second_previous_wave == "Wave 1.1" or third_previous_wave == "Wave 1" or
                            third_previous_wave == "Wave 1.1" or fourth_previous_wave == "Wave 1" or
                            fourth_previous_wave == "Wave 1.1"):
                        value = "Wave 1.1"  # Modify to "Wave 1.1" if condition is met
                # Append the modified or unchanged wave value to the list
                updated_wave_numbers.append(value)
                # Update the previous wave values for the next iteration
                fourth_previous_wave = third_previous_wave
                third_previous_wave = second_previous_wave
                second_previous_wave = previous_wave
                previous_wave = value
            else:
                # If the value is NaN, append it as is
                updated_wave_numbers.append(value)
        # Add the updated wave numbers back to the DataFrame
        df[column_name] = updated_wave_numbers
        return df

    # Apply the function to both the 'Wave Number Uptrend' and 'Wave Number Downtrend' columns
    df4 = update_wave_numbers(df4, 'Wave Number Uptrend')
    df4 = update_wave_numbers(df4, 'Wave Number Downtrend')
    df42 = update_wave_numbers(df42, 'Wave Number Uptrend')
    df42 = update_wave_numbers(df42, 'Wave Number Downtrend')
    # Define the valid waves for the even and odd positions
    valid_wave_1 = ['Wave 1', 'Wave 1.1']  # Even indices should be Wave 1 or Wave 1.1
    valid_wave_2 = ['Wave 2.1', 'Wave 2.2']  # Odd indices should be Wave 2 or Wave 2.1, Wave 2.2

    def is_wave_pattern_valid(df, wave_column):
        # Get the last part of the 'Wave Number Downtrend' values
        last_valid_index = df['Close'].last_valid_index()
        # Identify the indices for the last 6 rows to update
        last_6_indices = df.index[df.index <= last_valid_index][-6:]
        # Get the wave values from the specified 'wave_column' corresponding to the last 6 indices
        last_waves = df.loc[last_6_indices, wave_column].dropna().tolist()
        # print("Last 6 waves:", last_waves)
        # Ensure there are at least 6 valid waves to check
        if len(last_waves) < 6:
            # print("Not enough valid waves in the last 6 rows.")
            return False  # or handle the missing data gracefully (e.g., fill or skip)

        # Check that the waves alternate correctly: Even indices should be valid Wave 1, Odd indices should be valid Wave 2
        for i, wave in enumerate(last_waves):
            if i % 2 == 0:  # Even indices should be 'Wave 1' or 'Wave 1.1'
                if wave not in valid_wave_1:
                    print(f"Wave at index {i} is invalid for Wave 1: {wave}")
                    return False
            else:  # Odd indices should be 'Wave 2' or 'Wave 2.1', 'Wave 2.2'
                if wave not in valid_wave_2:
                    print(f"Wave at index {i} is invalid for Wave 2: {wave}")
                    return False
        return True

    # Generalized function to apply wave updates
    def update_wave_patterns(df, wave_column):
        # Validate the pattern before applying updates
        if is_wave_pattern_valid(df, wave_column):
            # Find the last valid index of the 'Close' column
            last_valid_index = df['Close'].last_valid_index()
            # Identify the indices for the last 6 rows to update
            last_6_indices = df.index[df.index <= last_valid_index][-6:]
            # Get the last value of the specified wave column (keep it unchanged)
            last_wave_value = df.loc[last_valid_index, wave_column]
            # Get the first value (Wave 1) and keep it unchanged
            first_wave_value = df.loc[last_6_indices[0], wave_column]
            # Define the new wave sequence to be assigned to the intermediate 4 rows (Wave 2.1, Wave 3.1, Wave 4.1, Wave 1.1)
            new_wave_sequence = ['Wave 2.1', 'Wave 3.1', 'Wave 4.1', 'Wave 1.1']
            # Update the specified wave column for the last 4 rows (keeping Wave 1 and the last value unchanged)
            for idx, wave in zip(last_6_indices[1:-1], new_wave_sequence):  # Exclude the first and last indices
                df.at[idx, wave_column] = wave
            # Keep 'Wave 1' and the last value unchanged
            df.at[last_6_indices[0], wave_column] = first_wave_value
            df.at[last_valid_index, wave_column] = last_wave_value
            # Show the updated DataFrame
            # print(df[[wave_column, 'Close', 'Datetime']])
        else:
            print(f"Wave pattern in {wave_column} is invalid. Please check the sequence.")

    # Example usage for 'Wave Number Downtrend' and for 'Wave Number Uptrend'::
    update_wave_patterns(df4, 'Wave Number Uptrend')
    update_wave_patterns(df4, 'Wave Number Downtrend')
    # print(df4[['Wave Number Uptrend', 'Wave Number Downtrend', 'Close', 'Datetime']])
    update_wave_patterns(df42, 'Wave Number Downtrend')
    update_wave_patterns(df42, 'Wave Number Uptrend')

    # Display the modified sequence
    # print_verbose(df4[df4['Wave Number Uptrend'].notna()]['Wave Number Uptrend'])
    # print_verbose(df42[df42['Wave Number Downtrend'].notna()]['Wave Number Downtrend'])

    #Last 5 Hours Data to show in Viz
    #df2 = df2.tail(300)
    df2 = df2.round(2)
    df4 = df4.round(2)
    df42 = df42.round(2)

    # Step 2: Get the Datetime of the first row of this subset
    df2_first_row = df2.head(1)
    df2_datetime = df2_first_row['Datetime'].iloc[0]

    # Step 3: Filter df4 and df42 based on the Datetime from df2
    # Select rows where the Datetime in df4 and df42 is greater than or equal to df2_first_row's Datetime
    df4 = df4[df4['Datetime'] >= df2_datetime]
    df42 = df42[df42['Datetime'] >= df2_datetime]


    # Plot waves
    uptrend_wave_info_3_legs = [
        ('Wave 1', '1', '#00FF00', 'top center', 'U1_3legs',1.5),('Wave 1.1', '1.1', '#00FF00', 'top center', 'U1_3legs',2), ('Wave 2.1', '2.1', '#00FF00', 'bottom center', 'U2.1_3legs',-1.5) , ('Wave 2.2', '2.2', '#00FF00', 'bottom center', 'U2.2_3legs',-1.5),
        ('Wave 3.1', '3.1', '#00FF00', 'top center', 'U3.1_3legs',1.5) , ('Wave 3.2', '3.2', '#00FF00', 'top center', 'U3.2_3legs',1.5),  ('Wave 4.1', '4.1', '#00FF00', 'bottom center', 'U4.1_3legs',0) , ('Wave 4.2', '4.2', '#00FF00', 'bottom center', 'U4.2_3legs',0),
        ('Wave 5.1', '5.1', '#00FF00', 'top center', 'U5.1_3legs',0) , ('Wave 5.2', '5.2', '#00FF00', 'top center', 'U5.2_3legs',0),('Wave 6', '6','#00FF00', 'bottom center','U6_3legs',0),('Wave 7', '7','#00FF00', 'top center','U7_3legs',0),
        ('Wave 8', '8','#00FF00', 'bottom center','U8_3legs',0),('Wave 9', '9','#00FF00', 'top center','U9_3legs',0),('Wave a', 'a','#00FF00', 'bottom center','Ua_3legs',-2),('Wave b', 'b','#00FF00', 'top center','Ub_3legs',2),('Wave c', 'c','#00FF00', 'bottom center','Uc_3legs',-2)]

    # Loop through the wave info and add traces
    for wave_name, wave_label, color, text_position, trace_name, y_offset in uptrend_wave_info_3_legs:
        # Filter the data for the current wave
        wave_data = df4[df4['Wave Number Uptrend'] == wave_name]
        trace_name = None
        # Skip if no data exists for the wave
        if wave_data.empty:
            continue

        # Convert to ColumnDataSource for Bokeh
        source = ColumnDataSource(data={
            'x': wave_data.index,
            'y': wave_data['ZIGZAGv_0.01%_3'] + y_offset,
            'label': [wave_label] * len(wave_data)
        })

        # Add the scatter plot for the wave
        # plot.scatter(
        #     x='x', y='y',
        #     size=3,
        #     color=color,
        #     source=source
        # )

        # Add labels for the wave
        labels = LabelSet(
            x='x', y='y', text='label',
            source=source,
            text_font_size="10pt",
            text_color=color,
            text_align="center",
            text_baseline="middle"
        )
        plot.add_layout(labels)


    uptrend_wave_info_10_legs = [
        ('Wave 1', '1', '#00FF00', 'top center', 'U1_10legs', 3),('Wave 1.1', '1.1', '#00FF00', 'top center', 'U1_10legs', 3),('Wave 2.1', '2.1', '#00FF00', 'bottom center', 'U2.1_10legs', -1.5) , ('Wave 2.2', '2.2', '#00FF00', 'bottom center', 'U2.2_10legs', -1.5),
        ('Wave 3.1', '3.1', '#00FF00', 'top center', 'U3.1_10legs', 2) , ('Wave 3.2', '3.2', '#00FF00', 'top center', 'U3.2_10legs', 2),  ('Wave 4.1', '4.1', '#00FF00', 'bottom center', 'U4.1_10legs', -2) , ('Wave 4.2', '4.2', '#00FF00', 'bottom center', 'U4.2_10legs', -2),
        ('Wave 5.1', '5.1', '#00FF00', 'top center', 'U5.1_10legs', 2) , ('Wave 5.2', '5.2', '#00FF00', 'top center', 'U5.2_10legs', 2),('Wave 6', '6','#00FF00', 'bottom center','U6_10legs',-1),('Wave 7', '7','#00FF00', 'top center','U7_10legs',1),
        ('Wave 8', '8','#00FF00', 'bottom center','U8_10legs',-1),('Wave 9', '9','#00FF00', 'top center','U9_10legs',1),('Wave a', 'a','#00FF00', 'bottom center','Ua_10legs',-5),('Wave b', 'b','#00FF00', 'top center','Ub_10legs',5),('Wave c', 'c','#00FF00', 'bottom center','Uc_10legs',-5)]

    # Loop through the uptrend wave_info list and add traces
    for wave_name, wave_label, color, text_position, trace_name, y_offset in uptrend_wave_info_10_legs:
        # Filter the data for the current wave
        wave_data = df42[df42['Wave Number Uptrend'] == wave_name]

        # Skip if no data exists for the wave
        if wave_data.empty:
            continue

        # Convert wave_data to a ColumnDataSource for better integration with Bokeh
        source = ColumnDataSource(data={
            'x': wave_data.index,
            'y': wave_data['ZIGZAGv_0.01%_10'] + y_offset,  # Apply y-offset to avoid overlap
            'label': [wave_label] * len(wave_data)
        })

        # Add scatter plot for the wave (without legend)
        # plot.scatter(
        #     x='x',
        #     y='y',
        #     size=3,  # Increase marker size
        #     color=color,
        #     source=source
        # )

        # Add labels for the wave
        labels = LabelSet(
            x='x',
            y='y',
            text='label',
            source=source,
            text_font_size="12pt",  # Larger font for readability
            text_color=color,  # Use wave-specific color
            text_align="center",
            text_font_style="bold",
            text_baseline="middle"
        )
        plot.add_layout(labels)


    downtrend_wave_info_3_legs = [
        ('Wave 1', '1', '#FFA500', 'bottom center', 'D1_3legs', -0.5),('Wave 1.1', '1.1', '#FFA500', 'bottom center', 'D1_3legs', -0.5),('Wave 2.1', '2.1', '#FFA500', 'top center', 'D2.1_3legs', 0.5) , ('Wave 2.2', '2.2', '#FFA500', 'top center', 'D2.2_3legs', 0.5),
        ('Wave 3.1', '3.1', '#FFA500', 'bottom center', 'D3.1_3legs', -0.5) , ('Wave 3.2', '3.2', '#FFA500', 'bottom center', 'D3.2_3legs', -0.5),  ('Wave 4.1', '4.1', '#FFA500', 'top center', 'D4.1_3legs', 0.5) , ('Wave 4.2', '4.2', '#FFA500', 'top center', 'D4.2_3legs', 0.5),
        ('Wave 5.1', '5.1', '#FFA500', 'bottom center', 'D5.1_3legs', -0.5) , ('Wave 5.2', '5.2', '#FFA500', 'bottom center', 'D5.2_3legs', -0.5),('Wave 6', '6','#FFA500', 'top center','D6_3legs', 0.5),('Wave 7', '7','#FFA500', 'bottom center','D7_3legs', -0.5),
        ('Wave 8', '8','#FFA500', 'top center','D8_3legs', 0.5),('Wave 9', '9','#FFA500', 'bottom center','D9_3legs', -0.5),('Wave a', 'a','#FFA500', 'top center','Da_3legs', 0.5),('Wave b', 'b','#FFA500', 'bottom center','Db_3legs', -0.5),('Wave c', 'c','#FFA500', 'top center','Dc_3legs', 0.5)]

    # Loop through the downtrend wave_info list and add traces
    for wave_name, wave_label, color, text_position, trace_name, y_offset in downtrend_wave_info_3_legs:
        # Filter the data for the current wave
        wave_data = df4[df4['Wave Number Downtrend'] == wave_name]

        # Skip if no data exists for the wave
        if wave_data.empty:
            continue

        # Convert wave_data to a ColumnDataSource for better integration with Bokeh
        source = ColumnDataSource(data={
            'x': wave_data.index,
            'y': wave_data['ZIGZAGv_0.01%_3'] + y_offset,
            'label': [wave_label] * len(wave_data)
        })

        # Add scatter plot for the wave (without legend)
        # plot.scatter(
        #     x='x',
        #     y='y',
        #     size=3,  # Increase marker size
        #     color=color,
        #     source=source
        # )

        # Add labels for the wave
        labels = LabelSet(
            x='x',
            y='y',
            text='label',
            source=source,
            text_font_size="10pt",  # Larger font for readability
            text_color=color,  # Use wave-specific color
            text_align="center",
            text_baseline="middle"
        )
        plot.add_layout(labels)

    downtrend_wave_info_10_legs = [
        ('Wave 1', '1', '#FFA500', 'bottom center', 'D1_10legs',-3),('Wave 1.1', '1.1', '#FFA500', 'bottom center', 'D1_10legs',-3),('Wave 2.1', '2.1', '#FFA500', 'top center', 'D2.1_10legs',3) , ('Wave 2.2', '2.2', '#FFA500', 'top center', 'D2.2_10legs',3),
        ('Wave 3.1', '3.1', '#FFA500', 'bottom center', 'D3.1_10legs',-2) , ('Wave 3.2', '3.2', '#FFA500', 'bottom center', 'D3.2_10legs',-2),  ('Wave 4.1', '4.1', '#FFA500', 'top center', 'D4.1_10legs',2) , ('Wave 4.2', '4.2', '#FFA500', 'top center', 'D4.2_10legs',2),
        ('Wave 5.1', '5.1', '#FFA500', 'bottom center', 'D5.1_10legs',-2) , ('Wave 5.2', '5.2', '#FFA500', 'bottom center', 'D5.2_10legs',-2),('Wave 6', '6','#FFA500', 'top center','D6_10legs',1),('Wave 7', '7','#FFA500', 'bottom center','D7_10legs',-1),
        ('Wave 8', '8','#FFA500', 'top center','D8_10legs',1),('Wave 9', '9','#FFA500', 'bottom center','D9_10legs',-1),('Wave a', 'a','#FFA500', 'top center','Da_10legs',2),('Wave b', 'b','#FFA500', 'bottom center','Db_10legs',-2),('Wave c', 'c','#FFA500', 'top center','Dc_10legs',2)]
    # Loop through the uptrend wave_info list and add traces
    for wave_name, wave_label, color, text_position, trace_name, y_offset in downtrend_wave_info_10_legs:
        # Filter the data for the current wave
        wave_data = df42[df42['Wave Number Downtrend'] == wave_name]

        # Skip if no data exists for the wave
        if wave_data.empty:
            continue

        # Convert wave_data to a ColumnDataSource for better integration with Bokeh
        source = ColumnDataSource(data={
            'x': wave_data.index,
            'y': wave_data['ZIGZAGv_0.01%_10'] + y_offset,  # Apply y-offset to avoid overlap
            'label': [wave_label] * len(wave_data)
        })

        # Add scatter plot for the wave (without legend)
        # plot.scatter(
        #     x='x',
        #     y='y',
        #     size=3,  # Increase marker size
        #     color=color,
        #     source=source
        # )

        # Add labels for the wave
        labels = LabelSet(
            x='x',
            y='y',
            text='label',
            source=source,
            text_font_size="12pt",  # Larger font for readability
            text_color=color,  # Use wave-specific color
            text_align="center",
            text_baseline="middle"
        )
        plot.add_layout(labels)


    # # Triangle UpTrend List of wave numbers and their corresponding labels
    wave_infot_u = [('A', 'A', 'bottom center', -2), ('B', 'B', 'top center',2),
                    ('C', 'C', 'bottom center',-2), ('D', 'D', 'top center',2), ('E', 'E', 'bottom center',-2), ('Up', 'T-Up', 'top center',0)]


    # Loop through the wave_info list
    for wave_name, wave_label, text_position, offset in wave_infot_u:
        # Filter the DataFrame based on the wave number
        wave_data = df4[df4['Wave Number Uptrend'] == wave_name]

        # Skip if no data exists for the wave
        if wave_data.empty:
            continue

        # Convert wave_data to a ColumnDataSource for better integration with Bokeh
        source = ColumnDataSource(data={
            'x': wave_data.index,
            'y': wave_data['ZIGZAGv_0.01%_3'] + offset,  # Apply offset to avoid overlap
            'label': [wave_label] * len(wave_data)
        })

        # Add scatter plot for the wave (without legend)
        # plot.scatter(
        #     x='x',
        #     y='y',
        #     size=3,  # Adjust marker size for visibility
        #     color='green',
        #     source=source
        # )

        # Add labels for the wave
        labels = LabelSet(
            x='x',
            y='y',
            text='label',
            source=source,
            text_font_size="12pt",  # Larger font for readability
            text_color="white",  # Use wave-specific color
            text_align="center",
            text_baseline="middle"
        )
        plot.add_layout(labels)


    # # Triangle DownTrend List of wave numbers and their corresponding labels
    wave_infot_d = [('A', 'A', 'top center', 0.5), ('B', 'B', 'bottom center', -0.5),
                    ('C', 'C', 'top center', 0.5), ('D', 'D', 'bottom center', -0.5), ('E', 'E', 'top center', 0.5),('Down', 'T-Down', 'bottom center', -0.5)]

    # Loop through the wave_info list
    for wave_name, wave_label, text_position,offset in wave_infot_d:
        # Filter the DataFrame based on the wave number
        wave_data = df4[df4['Wave Number Downtrend'] == wave_name]

    # Loop through the wave_info list
    for wave_name, wave_label, text_position, offset in wave_infot_d:
        # Filter the DataFrame based on the wave number
        wave_data = df4[df4['Wave Number Downtrend'] == wave_name]

        # Skip if no data exists for the wave
        if wave_data.empty:
            continue

        # Convert wave_data to a ColumnDataSource for better integration with Bokeh
        source = ColumnDataSource(data={
            'x': wave_data.index,
            'y': wave_data['ZIGZAGv_0.01%_3'] + offset,  # Apply offset to adjust label positioning
            'label': [wave_label] * len(wave_data)
        })

        # Add scatter plot for the wave (without legend)
        # plot.scatter(
        #     x='x',
        #     y='y',
        #     size=3,  # Adjust marker size for better visibility
        #     color='lightblue',
        #     source=source
        # )

        # Add labels for the wave
        labels = LabelSet(
            x='x',
            y='y',
            text='label',
            source=source,
            text_font_size="12pt",  # Increase font size for readability
            text_color="lightblue",  # Set text color to red for downtrend
            text_align="center",
            text_baseline="middle"
        )
        plot.add_layout(labels)


    # # Zigzag, Flat Corrective Pattern List of wave numbers and their corresponding labels
    wave_info_zigzag_flat_inner = [('((i))', ' ', 'bottom center', -1), ('((ii))', '((ii))', 'top center', 1),('((iii))', '((iii))', 'bottom center', -1),('((iv))', '((iv))', 'top center', 1),('((v)', '((v))', 'bottom center', -1),
                                   ('((a))', '((a))', 'top center', 1),('((b))', '((b))', 'bottom center', -1),('((c))', '((c))', 'top center', 1), ('((w))', '((w))', 'bottom center', -1),('((x))', '((x))', 'top center', 1),('((y))', '((y))', 'bottom center', -1)]

    # Loop through the wave_info list
    for wave_name, wave_label, text_position, offset in wave_info_zigzag_flat_inner:
        # Filter the DataFrame based on the wave number
        wave_data = df4[df4['Corrective Pattern inner numbers'] == wave_name]

        # Skip if no data exists for the wave
        if wave_data.empty:
            continue

        # Convert wave_data to a ColumnDataSource for better integration with Bokeh
        source = ColumnDataSource(data={
            'x': wave_data.index,
            'y': wave_data['ZIGZAGv_0.01%_3'] + offset,
            'label': [wave_label] * len(wave_data)
        })

        # Add scatter plot for the wave (without legend)
        # plot.scatter(
        #     x='x',
        #     y='y',
        #     size=5,  # Adjust marker size for better visibility
        #     color='lightblue',
        #     source=source
        # )

        # Add labels for the wave
        labels = LabelSet(
            x='x',
            y='y',
            text='label',
            source=source,
            text_font_size="12pt",  # Larger font for readability
            text_color="lightblue",  # Use wave-specific color
            text_align="center",
            text_baseline="middle"
        )
        plot.add_layout(labels)


    # # Zigzag, Flat Corrective Pattern List of wave numbers and their corresponding labels
    wave_info_zigzag_flat_outer = [('A', 'A', 'bottom center', -0.5), ('B', 'B', 'top center', 0.5),('C', 'C', 'bottom center', -0.5)]

    # Loop through the wave_info list
    for wave_name, wave_label, text_position, offset in wave_info_zigzag_flat_outer:
        # Filter the DataFrame based on the wave number
        wave_data = df4[df4['Corrective Pattern outer numbers'] == wave_name]

        # Skip if no data exists for the wave
        if wave_data.empty:
            continue

        # Convert wave_data to a ColumnDataSource for better integration with Bokeh
        source = ColumnDataSource(data={
            'x': wave_data.index,
            'y': wave_data['ZIGZAGv_0.01%_3'] + offset,
            'label': [wave_label] * len(wave_data)
        })

        # Add scatter plot for the wave (without legend)
        # plot.scatter(
        #     x='x',
        #     y='y',
        #     size=3,  # Adjust marker size for better visibility
        #     color='lightblue',
        #     source=source,
        #     legend_label=None  # Hide legend for this trace
        # )

        # Add labels for the wave
        labels = LabelSet(
            x='x',
            y='y',
            text='label',
            source=source,
            text_font_size="12pt",  # Larger font for readability
            text_color="lightblue",  # Use red for outer wave labels
            text_align="center",
            text_baseline="middle"
        )
        plot.add_layout(labels)


    # # Double Three, Triple Three Inner Waves Corrective Pattern List of wave numbers and their corresponding labels
    wave_info_double_triple_three_inner = [('((a))', '((a))', 'top center', -0.5),('((b))', '((b))', 'bottom center', -0.5),('((c))', '((c))', 'top center', 0.5),('((d))', '((d))', 'top center', 0.5),('((e))', '((e))', 'bottom center', -0.5), ('((w))', '((w))', 'bottom center', -0.5),('((x))', '((x))', 'top center', 0.5),('((y))', '((y))', 'bottom center', -0.5)]

    # Loop through the wave_info list
    for wave_name, wave_label, text_position, offset in wave_info_double_triple_three_inner:
        # Filter the DataFrame based on the wave number
        wave_data = df42[df42['Corrective Pattern inner numbers'] == wave_name]

        # Skip if no data exists for the wave
        if wave_data.empty:
            continue

        # Convert wave_data to a ColumnDataSource for better integration with Bokeh
        source = ColumnDataSource(data={
            'x': wave_data.index,
            'y': wave_data['ZIGZAGv_0.01%_10'] + offset,
            'label': [wave_label] * len(wave_data)
        })

        # Add scatter plot for the wave (without legend)
        # plot.scatter(
        #     x='x',
        #     y='y',
        #     size=5,  # Adjust marker size for better visibility
        #     color='lightblue',
        #     source=source
        # )

        # Add labels for the wave
        labels = LabelSet(
            x='x',
            y='y',
            text='label',
            source=source,
            text_font_size="12pt",  # Larger font for readability
            text_color="lightblue",  # Set the text color to blue
            text_align="center",
            text_baseline="middle"
        )
        plot.add_layout(labels)


    # # Double Three, Triple Three Outer Waves Corrective Pattern List of wave numbers and their corresponding labels
    wave_info_double_triple_three_outer = [('W', 'W', 'bottom center',-1), ('X', 'X', 'top center',3),('Y', 'Y', 'bottom center',-1),('Z', 'Z', 'bottom center',-1)]

    # Loop through the wave_info list
    for wave_name, wave_label, text_position, offset in wave_info_double_triple_three_outer:
        # Filter the DataFrame based on the wave number
        wave_data = df42[df42['Corrective Pattern outer numbers'] == wave_name]

        # Skip if no data exists for the wave
        if wave_data.empty:
            continue

        # Convert wave_data to a ColumnDataSource for better integration with Bokeh
        source = ColumnDataSource(data={
            'x': wave_data.index,
            'y': wave_data['ZIGZAGv_0.01%_10'] + offset,
            'label': [wave_label] * len(wave_data)
        })

        # Add scatter plot for the wave (without legend)
        # plot.scatter(
        #     x='x',
        #     y='y',
        #     size=5,  # Increased marker size for better visibility
        #     color='yellow',
        #     source=source # Hide legend for this trace
        # )

        # Add labels for the wave
        labels = LabelSet(
            x='x',
            y='y',
            text='label',
            source=source,
            text_font_size="14pt",  # Larger font for better readability
            text_color="yellow",  # Set the text color to yellow
            text_align="center",
            text_baseline="middle",
            text_font_style="bold"  # Set font style to bold
        )
        plot.add_layout(labels)





    # Customize the legend
    plot.legend.title = "Elliot Waves"
    plot.legend.click_policy = "hide"

def plot_standard_deviation_lines(plot, df):
    """
    Draws standard deviation bands using Bokeh (1st SD: 68%, 2nd SD: 95%, 3rd SD: 99.7%).
    Uses **lighter colors** for better visibility on a **black background**.
    """

    # Ensure necessary columns exist
    required_cols = ["One_SD_Top", "One_SD_Bottom", "Two_SD_Top", "Two_SD_Bottom", "Three_SD_Top", "Three_SD_Bottom", "Avg_Close"]
    for col in required_cols:
        if col not in df.columns:
            raise KeyError(f"Missing column: {col} in DataFrame!")

    # Forward-fill missing values to prevent issues
    df = df.ffill().fillna(method="ffill")

    # Convert DataFrame into Bokeh ColumnDataSource
    source = ColumnDataSource(df)

    # **Dynamically Adjust Y-Range**
    y_min = df[["Three_SD_Bottom"]].min().min()
    y_max = df[["Three_SD_Top"]].max().max()
    buffer = (y_max - y_min) * 0.01  # 10% buffer to avoid extreme compression
    plot.y_range = Range1d(y_min - buffer, y_max + buffer)

    # **Lighter Colors for Better Visibility on Black Background**
    colors = {
        "1_SD": "#66FF99",  # Light Green
        "2_SD": "#FFDD88",  # Light Orange
        "3_SD": "#FF7777",  # Light Red
        "Avg_Close": "white"  # White for visibility
    }

    # **Plot standard deviation bands**
    plot.line(x="index", y="One_SD_Top", source=source, line_width=2, line_color=colors["1_SD"],
              line_dash="solid", legend_label="68% (1 SD) Top")
    plot.line(x="index", y="One_SD_Bottom", source=source, line_width=2, line_color=colors["1_SD"],
              line_dash="solid", legend_label="68% (1 SD) Bottom")

    plot.line(x="index", y="Two_SD_Top", source=source, line_width=1.5, line_color=colors["2_SD"],
              line_dash="dotted", legend_label="95% (2 SD) Top")
    plot.line(x="index", y="Two_SD_Bottom", source=source, line_width=1.5, line_color=colors["2_SD"],
              line_dash="dotted", legend_label="95% (2 SD) Bottom")

    plot.line(x="index", y="Three_SD_Top", source=source, line_width=1.5, line_color=colors["3_SD"],
              line_dash="dotted", legend_label="99.7% (3 SD) Top")
    plot.line(x="index", y="Three_SD_Bottom", source=source, line_width=1.5, line_color=colors["3_SD"],
              line_dash="dotted", legend_label="99.7% (3 SD) Bottom")

    # **Plot Avg_Close on the main Y-axis** (White for visibility)
    plot.line(x="index", y="Avg_Close", source=source, line_width=2,
              line_color=colors["Avg_Close"], line_dash="solid", legend_label="Average Close")

    print("✅ Standard Deviation lines fixed and visible on black background.")


def plot_vwap_lines(plot, df):


    # Convert DataFrame into Bokeh ColumnDataSource
    source = ColumnDataSource(df)

    # **Plot Avg_Close on the main Y-axis** (White for visibility)
    plot.line(x="index", y="VWAP", source=source, line_width=2,
              line_color='white', line_dash="solid", legend_label="Volume Weighted")

    print("✅ Standard Deviation lines fixed and visible on black background.")

def plot_ema_lines(plot, df):


    # Convert DataFrame into Bokeh ColumnDataSource
    source = ColumnDataSource(df)

    # **Plot Avg_Close on the main Y-axis** (White for visibility)
    plot.line(x="index", y="EMA9", source=source, line_width=2,
              line_color='green', line_dash="solid", legend_label="EMA 9")

    # **Plot Avg_Close on the main Y-axis** (White for visibility)
    plot.line(x="index", y="EMA21", source=source, line_width=2,
              line_color='yellow', line_dash="solid", legend_label="EMA 21")

    print("✅ Standard Deviation lines fixed and visible on black background.")




def set_bokeh_output(notebook=False):
    """
    Set Bokeh to output either to a file or Jupyter notebook.
    By default, Bokeh outputs to notebook if running from within
    notebook was detected.
    """
    global IS_JUPYTER_NOTEBOOK
    IS_JUPYTER_NOTEBOOK = notebook

def _windos_safe_filename(filename):
    if sys.platform.startswith('win'):
        return re.sub(r'[^a-zA-Z0-9,_-]', '_', filename.replace('=', '-'))
    return filename

def _bokeh_reset(filename=None):
    curstate().reset()
    if filename:
        if not filename.endswith('.html'):
            filename += '.html'
        output_file(filename, title=filename)
    elif IS_JUPYTER_NOTEBOOK:
        curstate().output_notebook()

def colorgen():
    yield from cycle(Category10[10])

def lightness(color, lightness=.94):
    rgb = np.array([color.r, color.g, color.b]) / 255
    h, _, s = rgb_to_hls(*rgb)
    rgb = np.array(hls_to_rgb(h, lightness, s)) * 255
    return RGB(*rgb)

_MAX_CANDLES = 10_000


def _maybe_resample_data(resample_rule, df, indicators, equity_data, trades):
    if isinstance(resample_rule, str):
        freq = resample_rule
    else:
        if resample_rule is False or len(df) <= _MAX_CANDLES:
            return df, indicators, equity_data, trades

        freq_minutes = pd.Series({
            "1T": 1,
            "5T": 5,
            "10T": 10,
            "15T": 15,
            "30T": 30,
            "1H": 60,
            "2H": 60*2,
            "4H": 60*4,
            "8H": 60*8,
            "1D": 60*24,
            "1W": 60*24*7,
            "1M": np.inf,
        })
        timespan = df.index[-1] - df.index[0]
        require_minutes = (timespan / _MAX_CANDLES).total_seconds() // 60
        freq = freq_minutes.where(freq_minutes >= require_minutes).first_valid_index()
        warnings.warn(f"Data contains too many candlesticks to plot; downsampling to {freq!r}. "
                      "See `Backtest.plot(resample=...)`")

    from .lib import OHLCV_AGG, TRADES_AGG, _EQUITY_AGG
    df = df.resample(freq, label='right').agg(OHLCV_AGG).dropna()

    indicators = [_Indicator(i.df.resample(freq, label='right').mean()
                             .dropna().reindex(df.index).values.T,
                             **dict(i._opts, name=i.name,
                                    # Replace saved index with the resampled one
                                    index=df.index))
                  for i in indicators]
    assert not indicators or indicators[0].df.index.equals(df.index)

    equity_data = equity_data.resample(freq, label='right').agg(_EQUITY_AGG).dropna(how='all')
    assert equity_data.index.equals(df.index)

    def _weighted_returns(s, trades=trades):
        df = trades.loc[s.index]
        return ((df['Size'].abs() * df['ReturnPct']) / df['Size'].abs().sum()).sum()

    def _group_trades(column):
        def f(s, new_index=pd.Index(df.index.view(int)), bars=trades[column]):
            if s.size:
                # Via int64 because on pandas recently broken datetime
                mean_time = int(bars.loc[s.index].view(int).mean())
                new_bar_idx = new_index.get_loc(mean_time, method='nearest')
                return new_bar_idx
        return f

    if len(trades):  # Avoid pandas "resampling on Int64 index" error
        trades = trades.assign(count=1).resample(freq, on='ExitTime', label='right').agg(dict(
            TRADES_AGG,
            ReturnPct=_weighted_returns,
            count='sum',
            EntryBar=_group_trades('EntryTime'),
            ExitBar=_group_trades('ExitTime'),
        )).dropna()

    return df, indicators, equity_data, trades


def plot(*, results: pd.Series,
         df: pd.DataFrame,
         indicators: List[_Indicator],
         filename='', plot_width=None,
         plot_equity=True, plot_return=False, plot_pl=True,
         plot_volume=True, plot_drawdown=False,
         smooth_equity=False, relative_equity=True,
         superimpose=True, resample=True,
         reverse_indicators=True,
         show_legend=True, open_browser=True, divergence_swing_collection=None):
    """
    Like much of GUI code everywhere, this is a mess.
    """
    # We need to reset global Bokeh state, otherwise subsequent runs of
    # plot() contain some previous run's cruft data (was noticed when
    # TestPlot.test_file_size() test was failing).
    if not filename and not IS_JUPYTER_NOTEBOOK:
        filename = _windos_safe_filename(str(results._strategy))
    _bokeh_reset(filename)

    COLORS = [BEAR_COLOR, BULL_COLOR]
    BAR_WIDTH = .8

    assert df.index.equals(results['_equity_curve'].index)
    equity_data = results['_equity_curve'].copy(deep=False)
    trades = results['_trades']

    plot_volume = plot_volume and not df.Volume.isnull().all()
    plot_equity = plot_equity and not trades.empty
    plot_return = plot_return and not trades.empty
    plot_pl = plot_pl and not trades.empty
    is_datetime_index = isinstance(df.index, pd.DatetimeIndex)

    from .lib import OHLCV_AGG
    # ohlc df may contain many columns. We're only interested in, and pass on to Bokeh, these
    df = df[list(OHLCV_AGG.keys())].copy(deep=False)

    # Limit data to max_candles
    if is_datetime_index:
        df, indicators, equity_data, trades = _maybe_resample_data(
            resample, df, indicators, equity_data, trades)

    df.index.name = None  # Provides source name @index
    df['datetime'] = df.index  # Save original, maybe datetime index
    df = df.reset_index(drop=True)
    equity_data = equity_data.reset_index(drop=True)
    index = df.index

    new_bokeh_figure = partial(
        _figure,
        x_axis_type='linear',
        width=plot_width,
        height=600,
        tools="xpan,xwheel_zoom,box_zoom,undo,redo,reset,save",
        active_drag='xpan',
        active_scroll='xwheel_zoom',
        background_fill_color="black",
        border_fill_color="black"
    )



    pad = (index[-1] - index[0]) / 20

    fig_ohlc = new_bokeh_figure(
        x_range=Range1d(index[0], index[-1],
                        min_interval=10,
                        bounds=(index[0] - pad,
                                index[-1] + pad)) if index.size > 1 else None)

    fig_ohlc.xgrid.grid_line_color = None  # Remove vertical grid lines
    fig_ohlc.ygrid.grid_line_color = None  # Remove horizontal grid lines
    figs_above_ohlc, figs_below_ohlc = [], []

    source = ColumnDataSource(df)
    source.add((df.Close >= df.Open).values.astype(np.uint8).astype(str), 'inc')

    trade_source = ColumnDataSource(dict(
        index=trades['ExitBar'],
        datetime=trades['ExitTime'],
        exit_price=trades['ExitPrice'],
        size=trades['Size'],
        returns_positive=(trades['ReturnPct'] > 0).astype(int).astype(str),
    ))

    inc_cmap = factor_cmap('inc', COLORS, ['0', '1'])
    cmap = factor_cmap('returns_positive', COLORS, ['0', '1'])
    colors_darker = [lightness(BEAR_COLOR, .35),
                     lightness(BULL_COLOR, .35)]
    trades_cmap = factor_cmap('returns_positive', colors_darker, ['0', '1'])

    if is_datetime_index:
        fig_ohlc.xaxis.formatter = CustomJSTickFormatter(
            args=dict(axis=fig_ohlc.xaxis[0],
                      formatter=DatetimeTickFormatter(days=['%d %b', '%a %d'],
                                                      months=['%m/%Y', "%b'%y"]),
                      source=source),
            code='''
this.labels = this.labels || formatter.doFormat(ticks
                                                .map(i => source.data.datetime[i])
                                                .filter(t => t !== undefined));
return this.labels[index] || "";
        ''')

    NBSP = '\N{NBSP}' * 4
    ohlc_extreme_values = df[['High', 'Low']].copy(deep=False)
    ohlc_tooltips = [
        ('x, y', NBSP.join(('$index',
                            '$y{0,0.0[0000]}'))),
        ('OHLC', NBSP.join(('@Open{0,0.0[0000]}',
                            '@High{0,0.0[0000]}',
                            '@Low{0,0.0[0000]}',
                            '@Close{0,0.0[0000]}'))),
        ('DATE', '@DATE'),
        ('RSI', '@RSI{0.00}'),
        ('RSI_13', '@RSI_13{0.00}'),
        ('STOCH', '@STOCH{0.00}'),
        ('STOCH_D', '@STOCH_D{0.00}'),
        ('ADX', '@ADX{0.00}'),
        ('RANGE', '@RANGE{0.00}'),
        ('BODY_VOLUME', '@BODY_VOLUME{0.00}'),
        ('Volume', '@Volume{0}'),
        ('DivergenceInfo', '@DivergenceInfo{safe}'),
        ('BuySellConditions', '@BuySellConditions{safe}'),

    ]

    def new_indicator_figure(**kwargs):
        kwargs.setdefault('height', 200)
        fig = new_bokeh_figure(x_range=fig_ohlc.x_range,
                               active_scroll='xwheel_zoom',
                               active_drag='xpan',
                               **kwargs)
        fig.xaxis.visible = False
        fig.yaxis.minor_tick_line_color = None
        return fig

    def set_tooltips(fig, tooltips=(), vline=True, renderers=()):
        tooltips = list(tooltips)
        renderers = list(renderers)

        if is_datetime_index:
            formatters = {'@datetime': 'datetime'}
            tooltips = tooltips
        else:
            formatters = {}
            tooltips = [("#", "@index")] + tooltips
        fig.add_tools(HoverTool(
            point_policy='follow_mouse',
            renderers=renderers, formatters=formatters,
            tooltips=tooltips, mode='vline' if vline else 'mouse'))

    def _plot_equity_section(is_return=False):
        """Equity section"""
        # Max DD Dur. line
        equity = equity_data['Equity'].copy()
        dd_end = equity_data['DrawdownDuration'].idxmax()
        if np.isnan(dd_end):
            dd_start = dd_end = equity.index[0]
        else:
            dd_start = equity[:dd_end].idxmax()
            # If DD not extending into the future, get exact point of intersection with equity
            if dd_end != equity.index[-1]:
                dd_end = np.interp(equity[dd_start],
                                   (equity[dd_end - 1], equity[dd_end]),
                                   (dd_end - 1, dd_end))

        if smooth_equity:
            interest_points = pd.Index([
                # Beginning and end
                equity.index[0], equity.index[-1],
                # Peak equity and peak DD
                equity.idxmax(), equity_data['DrawdownPct'].idxmax(),
                # Include max dd end points. Otherwise the MaxDD line looks amiss.
                dd_start, int(dd_end), min(int(dd_end + 1), equity.size - 1),
            ])
            select = pd.Index(trades['ExitBar']).union(interest_points)
            select = select.unique().dropna()
            equity = equity.iloc[select].reindex(equity.index)
            equity.interpolate(inplace=True)

        assert equity.index.equals(equity_data.index)

        if relative_equity:
            equity /= equity.iloc[0]
        if is_return:
            equity -= equity.iloc[0]

        yaxis_label = 'Return' if is_return else 'Equity'
        source_key = 'eq_return' if is_return else 'equity'
        source.add(equity, source_key)
        fig = new_indicator_figure(
            y_axis_label=yaxis_label,
            **({} if plot_drawdown else dict(height=110)))

        # High-watermark drawdown dents
        fig.patch('index', 'equity_dd', source=ColumnDataSource(dict(
            index=np.r_[index, index[::-1]],
            equity_dd=np.r_[equity, equity.cummax()[::-1]]
        )), fill_color='black', line_color='black')  # Set to match background

        # Equity line
        r = fig.line('index', source_key, source=source, line_width=1.5, line_alpha=1)
        if relative_equity:
            tooltip_format = f'@{source_key}{{+0,0.[000]%}}'
            tick_format = '0,0.[00]%'
            legend_format = '{:,.0f}%'
        else:
            tooltip_format = f'@{source_key}{{$ 0,0}}'
            tick_format = '$ 0.0 a'
            legend_format = '${:,.0f}'
        set_tooltips(fig, [(yaxis_label, tooltip_format)], renderers=[r])
        fig.yaxis.formatter = NumeralTickFormatter(format=tick_format)

        # Peaks
        argmax = equity.idxmax()
        fig.scatter(argmax, equity[argmax],
                    legend_label='Peak ({})'.format(
                        legend_format.format(equity[argmax] * (100 if relative_equity else 1))),
                    color='cyan', size=8)
        fig.scatter(index[-1], equity.values[-1],
                    legend_label='Final ({})'.format(
                        legend_format.format(equity.iloc[-1] * (100 if relative_equity else 1))),
                    color='blue', size=8)

        if not plot_drawdown:
            drawdown = equity_data['DrawdownPct']
            argmax = drawdown.idxmax()
            fig.scatter(argmax, equity[argmax],
                        legend_label='Max Drawdown (-{:.1f}%)'.format(100 * drawdown[argmax]),
                        color='red', size=8)
        dd_timedelta_label = df['datetime'].iloc[int(round(dd_end))] - df['datetime'].iloc[dd_start]
        fig.line([dd_start, dd_end], equity.iloc[dd_start],
                 line_color='red', line_width=2,
                 legend_label=f'Max Dd Dur. ({dd_timedelta_label})'
                 .replace(' 00:00:00', '')
                 .replace('(0 days ', '('))

        figs_above_ohlc.append(fig)

    def _plot_drawdown_section():
        """Drawdown section"""
        fig = new_indicator_figure(y_axis_label="Drawdown")
        drawdown = equity_data['DrawdownPct']
        argmax = drawdown.idxmax()
        source.add(drawdown, 'drawdown')
        r = fig.line('index', 'drawdown', source=source, line_width=1.3)
        fig.scatter(argmax, drawdown[argmax],
                    legend_label='Peak (-{:.1f}%)'.format(100 * drawdown[argmax]),
                    color='red', size=8)
        set_tooltips(fig, [('Drawdown', '@drawdown{-0.[0]%}')], renderers=[r])
        fig.yaxis.formatter = NumeralTickFormatter(format="-0.[0]%")
        return fig

    def _plot_pl_section():
        """Profit/Loss markers section"""
        fig = new_indicator_figure(y_axis_label="Profit / Loss")
        fig.add_layout(Span(location=0, dimension='width', line_color='#666666',
                            line_dash='dashed', line_width=1))
        returns_long = np.where(trades['Size'] > 0, trades['ReturnPct'], np.nan)
        returns_short = np.where(trades['Size'] < 0, trades['ReturnPct'], np.nan)
        size = trades['Size'].abs()
        size = np.interp(size, (size.min(), size.max()), (8, 20))
        trade_source.add(returns_long, 'returns_long')
        trade_source.add(returns_short, 'returns_short')
        trade_source.add(size, 'marker_size')
        if 'count' in trades:
            trade_source.add(trades['count'], 'count')
        r1 = fig.scatter('index', 'returns_long', source=trade_source, fill_color=cmap,
                         marker='triangle', line_color='black', size='marker_size')
        r2 = fig.scatter('index', 'returns_short', source=trade_source, fill_color=cmap,
                         marker='inverted_triangle', line_color='black', size='marker_size')
        tooltips = [("Size", "@size{0,0}")]
        if 'count' in trades:
            tooltips.append(("Count", "@count{0,0}"))
        set_tooltips(fig, tooltips + [("P/L", "@returns_long{+0.[000]%}")],
                     vline=False, renderers=[r1])
        set_tooltips(fig, tooltips + [("P/L", "@returns_short{+0.[000]%}")],
                     vline=False, renderers=[r2])
        fig.yaxis.formatter = NumeralTickFormatter(format="0.[00]%")
        return fig


    def _plot_volume_section():
        """Volume section"""
        fig = new_indicator_figure(y_axis_label="RSI")
        fig.xgrid.grid_line_color = None  # Remove vertical grid lines
        fig.ygrid.grid_line_color = None  # Remove horizontal grid lines
        fig.xaxis.formatter = fig_ohlc.xaxis[0].formatter
        fig.xaxis.visible = True
        fig_ohlc.xaxis.visible = False  # Show only Volume's xaxis
        r = fig.line('index', 'RSI', source=source, line_width=1.3, line_color='green')

        # Add horizontal lines at 94 and 5
        line_94 = Span(location=94, dimension='width', line_color='#FFA07A', line_dash='dashed', line_width=2)
        line_5 = Span(location=5, dimension='width', line_color='#FFA07A', line_dash='dashed', line_width=2)

        # Add the horizontal lines to the figure
        fig.add_layout(line_94)
        fig.add_layout(line_5)
        #fig.line('index', 'drawdown', source=source, line_width=1.3)
        set_tooltips(fig, [('RSI', '@RSI{0.00 a}')], renderers=[r])
        fig.yaxis.formatter = NumeralTickFormatter(format="0 a")
        return fig

    def _plot_unusual_volume_section():
        """Volume section with unusual volume highlighted and tooltip"""
        fig = new_indicator_figure(y_axis_label="Volume")
        fig.xgrid.grid_line_color = None
        fig.ygrid.grid_line_color = None

        fig.xaxis.formatter = fig_ohlc.xaxis[0].formatter
        fig.xaxis.visible = True
        fig_ohlc.xaxis.visible = False

        # Ensure 'unusual_str' column exists
        if 'unusual_str' not in source.data:
            source.data['unusual_str'] = [str(x) for x in source.data['unusual']]

        # Color mapper
        color_mapper = CategoricalColorMapper(
            factors=["False", "True"],
            palette=["gray", "red"]
        )

        # Plot bars and keep a reference for the hover tool
        bar_renderer = fig.vbar(
            x="index",
            top="Volume",
            width=0.8,
            source=source,
            fill_color={'field': 'unusual_str', 'transform': color_mapper},
            line_color=None
        )

        # Add hover tool
        hover = HoverTool(
            tooltips=[
                ("Index", "@index"),
                ("Volume", "@Volume{0,0}"),
                ("Unusual", "@unusual_str"),
            ],
            mode='vline',
            renderers=[bar_renderer]
        )
        fig.add_tools(hover)

        fig.yaxis.formatter = NumeralTickFormatter(format="0 a")
        return fig


    def _plot_volume_section_two():
        """Volume section"""
        fig = new_indicator_figure(y_axis_label="STOCH")
        fig.xgrid.grid_line_color = None  # Remove vertical grid lines
        fig.ygrid.grid_line_color = None  # Remove horizontal grid lines


        fig.xaxis.formatter = fig_ohlc.xaxis[0].formatter
        fig.xaxis.visible = True
        fig_ohlc.xaxis.visible = False  # Show only Volume's xaxis
        r1  = fig.line('index', 'STOCH', source=source, line_width=1.3, line_color='red')
        r2  = fig.line('index', 'STOCH_D', source=source, line_width=1.3, line_color='white')

        # Add horizontal lines at 94 and 5
        line_80 = Span(location=80, dimension='width', line_color='#FFA07A', line_dash='dashed', line_width=2)
        line_20 = Span(location=20, dimension='width', line_color='#FFA07A', line_dash='dashed', line_width=2)
        fig.add_layout(line_80)
        fig.add_layout(line_20)

        #fig.line('index', 'drawdown', source=source, line_width=1.3)
        set_tooltips(fig, [('STOCH', '@STOCH{0.00 a}')], renderers=[r1])
        set_tooltips(fig, [('STOCH_D', '@STOCH_D{0.00 a}')], renderers=[r2])
        fig.yaxis.formatter = NumeralTickFormatter(format="0 a")
        return fig


    def _plot_volume_section_three():
        """Volume section"""
        fig = new_indicator_figure(y_axis_label="RSI_13")
        fig.xgrid.grid_line_color = None  # Remove vertical grid lines
        fig.ygrid.grid_line_color = None  # Remove horizontal grid lines
        fig.xaxis.formatter = fig_ohlc.xaxis[0].formatter
        fig.xaxis.visible = True
        fig_ohlc.xaxis.visible = False  # Show only Volume's xaxis
        r = fig.line('index', 'RSI_13', source=source, line_width=1.3, line_color='green')

        # Add horizontal lines at 94 and 5
        line_94 = Span(location=55, dimension='width', line_color='#FFA07A', line_dash='dashed', line_width=2)
        line_5 = Span(location=45, dimension='width', line_color='#FFA07A', line_dash='dashed', line_width=2)

        # Add the horizontal lines to the figure
        fig.add_layout(line_94)
        fig.add_layout(line_5)
        #fig.line('index', 'drawdown', source=source, line_width=1.3)
        set_tooltips(fig, [('RSI_13', '@RSI_13{0.00 a}')], renderers=[r])
        fig.yaxis.formatter = NumeralTickFormatter(format="0 a")
        return fig

    def _plot_rvsd_histogram(df):
        """Plots RVSD as a histogram below Stochastic K & D."""
        fig = new_indicator_figure(y_axis_label="RVSD", height=150)
        fig.xaxis.formatter = fig_ohlc.xaxis[0].formatter
        fig.xaxis.visible = True
        fig_ohlc.xaxis.visible = False  # Show only RVSD's x-axis

        # Define color mapping based on standard deviation levels
        df["RVSD_Color"] = ["pink" if abs(val) >= 2 else "lightpink" for val in df["RVSD"]]

        # Convert to Bokeh data source
        source_rvsd = ColumnDataSource(df)

        # Add RVSD histogram bars
        fig.vbar(
            x="index",
            top="RVSD",
            width=0.8,
            source=source_rvsd,
            fill_color="RVSD_Color",
            line_color=None
        )

        set_tooltips(fig, [('RVSD', '@RVSD{0.000}')])
        fig.yaxis.formatter = NumeralTickFormatter(format="0.00")
        return fig


    def _plot_fom_histogram(df):
        """Plots FoM as a histogram below Stochastic K & D."""
        fig = new_indicator_figure(y_axis_label="FoM", height=150)
        fig.xaxis.formatter = fig_ohlc.xaxis[0].formatter
        fig.xaxis.visible = True
        fig_ohlc.xaxis.visible = False  # Show only FoM's x-axis

        # Define color mapping based on standard deviation levels
        df["FoM_Color"] = ["pink" if abs(val) >= 2 else "lightpink" for val in df["FoM"]]

        # Convert to Bokeh data source
        source_fom = ColumnDataSource(df)

        # Add FoM histogram bars
        fig.vbar(
            x="index",
            top="FoM",
            width=0.8,
            source=source_fom,
            fill_color="FoM_Color",
            line_color=None
        )

        set_tooltips(fig, [('FoM', '@FoM{0.000}')])
        fig.yaxis.formatter = NumeralTickFormatter(format="0.00")
        return fig

    def _plot_superimposed_ohlc():
        """Superimposed, downsampled vbars"""
        time_resolution = pd.DatetimeIndex(df['datetime']).resolution
        resample_rule = (superimpose if isinstance(superimpose, str) else
                         dict(day='M',
                              hour='D',
                              minute='H',
                              second='T',
                              millisecond='S').get(time_resolution))
        if not resample_rule:
            warnings.warn(
                f"'Can't superimpose OHLC data with rule '{resample_rule}'"
                f"(index datetime resolution: '{time_resolution}'). Skipping.",
                stacklevel=4)
            return

        df2 = (df.assign(_width=1).set_index('datetime')
               .resample(resample_rule, label='left')
               .agg(dict(OHLCV_AGG, _width='count')))

        # Check if resampling was downsampling; error on upsampling
        orig_freq = _data_period(df['datetime'])
        resample_freq = _data_period(df2.index)
        if resample_freq < orig_freq:
            raise ValueError('Invalid value for `superimpose`: Upsampling not supported.')
        if resample_freq == orig_freq:
            warnings.warn('Superimposed OHLC plot matches the original plot. Skipping.',
                          stacklevel=4)
            return

        df2.index = df2['_width'].cumsum().shift(1).fillna(0)
        df2.index += df2['_width'] / 2 - .5
        df2['_width'] -= .1  # Candles don't touch

        df2['inc'] = (df2.Close >= df2.Open).astype(int).astype(str)
        df2.index.name = None
        source2 = ColumnDataSource(df2)
        fig_ohlc.segment('index', 'High', 'index', 'Low', source=source2, color='#bbbbbb')
        colors_lighter = [lightness(BEAR_COLOR, .92),
                          lightness(BULL_COLOR, .92)]
        fig_ohlc.vbar('index', '_width', 'Open', 'Close', source=source2, line_color=None,
                      fill_color=factor_cmap('inc', colors_lighter, ['0', '1']))

    def _plot_ohlc():
        """Main OHLC bars"""
        fig_ohlc.segment('index', 'High', 'index', 'Low', source=source, color="white")
        r = fig_ohlc.vbar('index', BAR_WIDTH, 'Open', 'Close', source=source,
                          line_color="black", fill_color=inc_cmap)
        return r


    def _plot_ohlc_trades():
        """Trade entry/exit markers on OHLC plot with combined profit display and individual trade PnL."""

        # Calculate total combined PnL from existing column
        total_pnl = trades['PnL'].sum()

        # Format combined PnL for display
        pnl_label = f"Net P/L: ${total_pnl:,.2f}"

        # Add entry/exit lines
        trade_source.add(trades[['EntryBar', 'ExitBar']].values.tolist(), 'position_lines_xs')
        trade_source.add(trades[['EntryPrice', 'ExitPrice']].values.tolist(), 'position_lines_ys')

        # Calculate middle point for each trade to display PnL
        trades['MiddleBar'] = (trades['EntryBar'] + trades['ExitBar']) / 2
        trades['MiddlePrice'] = (trades['EntryPrice'] + trades['ExitPrice']) / 2

        # Format profit/loss text with `-` for negative values
        trades['PnL_Text'] = trades['PnL'].apply(lambda pnl: f"${pnl:,.3f}" if pnl >= 0 else f"-${abs(pnl):,.3f}")
        trades['PnL_Color'] = trades['PnL'].apply(lambda pnl: 'white' if pnl > 0 else 'white' if pnl < 0 else 'white')

        # Add data to trade_source
        trade_source.add(trades['PnL_Text'].tolist(), 'pnl_texts')
        trade_source.add(trades['PnL_Color'].tolist(), 'pnl_colors')
        trade_source.add(trades['MiddleBar'].tolist(), 'middle_x')
        trade_source.add(trades['MiddlePrice'].tolist(), 'middle_y')

        # Plot trade entry/exit lines
        fig_ohlc.multi_line(xs='position_lines_xs', ys='position_lines_ys',
                            source=trade_source, line_color=trades_cmap,
                            legend_label=f"Trades ({len(trades)}) | {pnl_label}",
                            line_width=8, line_alpha=1, line_dash='dotted')

        # Add text annotations for profit/loss in the middle of the entry/exit line
        fig_ohlc.text(x='middle_x', y='middle_y', text='pnl_texts', text_color='pnl_colors',
                      source=trade_source, text_font_size='10pt', text_font_style='bold', text_align='center')






    def _plot_indicators():
        """Strategy indicators"""

        def _too_many_dims(value):
            assert value.ndim >= 2
            if value.ndim > 2:
                warnings.warn(f"Can't plot indicators with >2D ('{value.name}')",
                              stacklevel=5)
                return False
            return False

        class LegendStr(str):
            # The legend string is such a string that only matches
            # itself if it's the exact same object. This ensures
            # legend items are listed separately even when they have the
            # same string contents. Otherwise, Bokeh would always consider
            # equal strings as one and the same legend item.
            def __eq__(self, other):
                return self is other

        ohlc_colors = colorgen()
        indicator_figs = []

        for i, value in enumerate(indicators):
            value = np.atleast_2d(value)

            # Use .get()! A user might have assigned a Strategy.data-evolved
            # _Array without Strategy.I()
            if not value._opts.get('plot') or _too_many_dims(value):
                continue

            is_overlay = value._opts['overlay']
            is_scatter = value._opts['scatter']
            if is_overlay:
                fig = fig_ohlc
            else:
                fig = new_indicator_figure()
                indicator_figs.append(fig)
            tooltips = []
            colors = value._opts['color']
            colors = colors and cycle(_as_list(colors)) or (
                cycle([next(ohlc_colors)]) if is_overlay else colorgen())
            legend_label = LegendStr(value.name)
            for j, arr in enumerate(value, 1):
                color = next(colors)
                source_name = f'{legend_label}_{i}_{j}'
                if arr.dtype == bool:
                    arr = arr.astype(int)
                source.add(arr, source_name)
                tooltips.append(f'@{{{source_name}}}{{0,0.0[0000]}}')
                if is_overlay:
                    ohlc_extreme_values[source_name] = arr
                    if is_scatter:
                        fig.scatter(
                            'index', source_name, source=source,
                            legend_label=legend_label, color=color,
                            line_color='black', fill_alpha=.8,
                            marker='circle', radius=BAR_WIDTH / 2 * 1.5)
                    else:
                        fig.line(
                            'index', source_name, source=source,
                            legend_label=legend_label, line_color=color,
                            line_width=1.3)
                else:
                    if is_scatter:
                        r = fig.scatter(
                            'index', source_name, source=source,
                            legend_label=LegendStr(legend_label), color=color,
                            marker='circle', radius=BAR_WIDTH / 2 * .9)
                    else:
                        r = fig.line(
                            'index', source_name, source=source,
                            legend_label=LegendStr(legend_label), line_color=color,
                            line_width=1.3)
                    # Add dashed centerline just because
                    mean = float(pd.Series(arr).mean())
                    if not np.isnan(mean) and (abs(mean) < .1 or
                                               round(abs(mean), 1) == .5 or
                                               round(abs(mean), -1) in (50, 100, 200)):
                        fig.add_layout(Span(location=float(mean), dimension='width',
                                            line_color='#666666', line_dash='dashed',
                                            line_width=.5))
            if is_overlay:
                ohlc_tooltips.append((legend_label, NBSP.join(tooltips)))
            else:
                set_tooltips(fig, [(legend_label, NBSP.join(tooltips))], vline=True, renderers=[r])
                # If the sole indicator line on this figure,
                # have the legend only contain text without the glyph
                if len(value) == 1:
                    fig.legend.glyph_width = 0
        return indicator_figs

    # Construct figure ...

    # if plot_equity:
    #     _plot_equity_section()

    if plot_return:
        _plot_equity_section(is_return=True)

    if plot_drawdown:
        figs_above_ohlc.append(_plot_drawdown_section())

    # if plot_pl:
    #     figs_above_ohlc.append(_plot_pl_section())

    if plot_volume:
        fig_volume_unusual = _plot_unusual_volume_section()
        figs_below_ohlc.append(fig_volume_unusual)
        fig_volume_three = _plot_volume_section_three()
        figs_below_ohlc.append(fig_volume_three)
        fig_volume = _plot_volume_section()
        figs_below_ohlc.append(fig_volume)
        fig_volume_two = _plot_volume_section_two()
        figs_below_ohlc.append(fig_volume_two)

        print(figs_below_ohlc)

        #fig_rvsd = _plot_rvsd_histogram(df)
        #figs_below_ohlc.append(fig_rvsd)

        #fig_fom = _plot_fom_histogram(df)
        #figs_below_ohlc.append(fig_fom)

    # if superimpose and is_datetime_index:
    #     _plot_superimposed_ohlc()
    ohlc_bars = _plot_ohlc()
    #plot_standard_deviation_lines(fig_ohlc, df)
    plot_vwap_lines(fig_ohlc, df)
    plot_ema_lines(fig_ohlc, df)

    swing_collection_3 = create_swings_using_zig_zag_indicator(df)
    swing_collection_3 = mark_flat_swings(swing_collection_3, 0.02)

    swing_collection_10 = create_swings_using_zig_zag_indicator_10_legs(df)
    plot_zig_zag_swings(fig_ohlc, df, swing_collection_10, swing_collection_3, divergence_swing_collection)
    plot_elliot_waves(fig_ohlc, df, "1min")
    #plot_scipy_signal(fig_ohlc, df)
    # plot_scipy_signal_10(fig_ohlc, df)

    _plot_ohlc_trades()
    indicator_figs = _plot_indicators()
    if reverse_indicators:
        indicator_figs = indicator_figs[::-1]
    figs_below_ohlc.extend(indicator_figs)

    set_tooltips(fig_ohlc, ohlc_tooltips, vline=True, renderers=[ohlc_bars])

    source.add(ohlc_extreme_values.min(1), 'ohlc_low')
    source.add(ohlc_extreme_values.max(1), 'ohlc_high')

    custom_js_args = dict(ohlc_range=fig_ohlc.y_range,
                          source=source)
    if plot_volume:
        custom_js_args.update(volume_range=fig_volume.y_range)

    fig_ohlc.x_range.js_on_change('end', CustomJS(args=custom_js_args,
                                                  code=_AUTOSCALE_JS_CALLBACK))

    plots = figs_above_ohlc + [fig_ohlc] + figs_below_ohlc
    linked_crosshair = CrosshairTool(dimensions='both')

    for f in plots:
        if f.legend:
            f.legend.visible = show_legend
            f.legend.location = 'top_left'
            f.legend.border_line_width = 1
            f.legend.border_line_color = '#333333'
            f.legend.padding = 5
            f.legend.spacing = 0
            f.legend.margin = 0
            f.legend.label_text_font_size = '8pt'
            f.legend.click_policy = "hide"
        f.min_border_left = 0
        f.min_border_top = 3
        f.min_border_bottom = 6
        f.min_border_right = 10
        f.outline_line_color = '#666666'

        f.add_tools(linked_crosshair)
        wheelzoom_tool = next(wz for wz in f.tools if isinstance(wz, WheelZoomTool))
        wheelzoom_tool.maintain_focus = False

    kwargs = {}
    if plot_width is None:
        kwargs['sizing_mode'] = 'stretch_width'

    fig = gridplot(
        plots,
        ncols=1,
        toolbar_location='right',
        toolbar_options=dict(logo=None),
        merge_tools=True,
        **kwargs
    )
    show(fig, browser=None if open_browser else 'none')
    return fig


def plot_heatmaps(heatmap: pd.Series, agg: Union[Callable, str], ncols: int,
                  filename: str = '', plot_width: int = 1200, open_browser: bool = True):
    if not (isinstance(heatmap, pd.Series) and
            isinstance(heatmap.index, pd.MultiIndex)):
        raise ValueError('heatmap must be heatmap Series as returned by '
                         '`Backtest.optimize(..., return_heatmap=True)`')

    _bokeh_reset(filename)

    param_combinations = combinations(heatmap.index.names, 2)
    dfs = [heatmap.groupby(list(dims)).agg(agg).to_frame(name='_Value')
           for dims in param_combinations]
    plots = []
    cmap = LinearColorMapper(palette='Viridis256',
                             low=min(df.min().min() for df in dfs),
                             high=max(df.max().max() for df in dfs),
                             nan_color='white')
    for df in dfs:
        name1, name2 = df.index.names
        level1 = df.index.levels[0].astype(str).tolist()
        level2 = df.index.levels[1].astype(str).tolist()
        df = df.reset_index()
        df[name1] = df[name1].astype('str')
        df[name2] = df[name2].astype('str')

        fig = _figure(x_range=level1,
                      y_range=level2,
                      x_axis_label=name1,
                      y_axis_label=name2,
                      width=plot_width // ncols,
                      height=plot_width // ncols,
                      tools='box_zoom,reset,save',
                      tooltips=[(name1, '@' + name1),
                                (name2, '@' + name2),
                                ('Value', '@_Value{0.[000]}')])
        fig.grid.grid_line_color = None
        fig.axis.axis_line_color = None
        fig.axis.major_tick_line_color = None
        fig.axis.major_label_standoff = 0

        fig.rect(x=name1,
                 y=name2,
                 width=1,
                 height=1,
                 source=df,
                 line_color=None,
                 fill_color=dict(field='_Value',
                                 transform=cmap))
        plots.append(fig)

    fig = gridplot(
        plots,
        ncols=ncols,
        toolbar_options=dict(logo=None),
        toolbar_location='above',
        merge_tools=True,
    )

    show(fig, browser=None if open_browser else 'none')
    return fig
