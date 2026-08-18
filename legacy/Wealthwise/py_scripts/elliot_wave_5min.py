import streamlit as st
# Set the page configuration
st.set_page_config(
    page_title="EW 5min Chart",
    # page_icon="/home/ubuntu/code_repo/streamlit4analysis/img/favicon.PNG",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": None
    }
)

from pandas_ta import zigzag
import pandas_ta as ta
import pandas as pd
import numpy as np
import plotly.io as pio
from datetime import date
from datetime import datetime, timedelta
from pytz import timezone
import plotly.graph_objects as go
import plotly.figure_factory as ff
import plotly.express as px
import plotly.io as pio
from plotly.subplots import make_subplots
import pymysql
from sqlalchemy import create_engine, text
import yfinance as yf
import plotly.graph_objects as go
import plotly.io as pio
import time
import defs as defs
import utility as utility
from get_market_data import MarketDataHelper
import talib
from assign_wave_numbers import assign_wave_numbers,update_chart, VERBOSE


schwab_client = None


# Streamlit layout
# st.title("Real-Time Candlestick Chart")
# st.subheader("Real-Time Candlestick Chart")
# st.write("This dashboard updates every minute to reflect new data.")

# Create an empty container for the chart
chart_placeholder = st.empty()

def fetch_data():

    # Define the stock ticker symbol (replace 'ES=F' with your desired stock symbol)
    symbol = '/ES'  #ES=F, ^GSPC
    # Fetch the last 1 day of data with 1-minute intervals
    # data = yf.download(ticker, interval='1m', period='5d')
    start_date = (datetime.now() - timedelta(days=7))#.date() #.date() not required for yfinacne, but required for schdev API
    end_date = (datetime.now() + timedelta(days=1)).date()
    # start_date_str = start_date.strftime('%Y-%m-%d')     # Convert the dates to string format (required by yfinance) 
    # Adjust the start_date to 00:00 (midnight) on the calculated day
    # start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    # data = yf.download(symbol, start=start_date,interval='5m')
    frequencyType = "minute"
    frequency = "5"
    needExtendedHoursData = True
    api_key = 'REDACTED__see_legacy_REDACTIONS_md'
    app_secret = 'REDACTED__see_legacy_REDACTIONS_md'
    callback_url = 'https://127.0.0.1:8182'
    helper = MarketDataHelper(api_key, app_secret, callback_url)
    data = helper.fetch_price_history(symbol ,start_date.strftime('%Y-%m-%d') , frequencyType, frequency, needExtendedHoursData, end_date.strftime('%Y-%m-%d'))
    data = data.dropna()
    # Convert the datetime index from UTC to Eastern Time (US/Eastern)
    # data.index = data.index.tz_convert('US/Eastern')
    df2 = data.copy()
    # df2 = pd.read_csv(r"C:\Users\HP\Downloads\df2_downtrend_cross_check.csv")
    # Flatten the MultiIndex and remove the ticker part (symbol name)
    # df2.columns = df2.columns.get_level_values('Price')
    # Reset index to get a default integer-based index
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
            print(f"Column {zigzag_col} not found in dataframe.")
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
                elif df2.at[idx_min_low, 'Low'] < value2 and idx_min_low != idx2: #   v1,v2: Blue wave: (6062.0, 6060.25) and condition No Higher Higher after v2
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


    # ##Find last two non-NaN values >> Yellow Wave
    # non_nan_indices = df2[df2['ZIGZAGv_0.01%_10'].notna()].index[-2:]
    # ## Ensure there are at least two non-NaN values and three NaNs after the second one
    # if len(non_nan_indices) >= 2:
    #     idx1, idx2 = non_nan_indices[0], non_nan_indices[1]
    #     value1, value2 = df2.at[idx1, 'ZIGZAGv_0.01%_10'], df2.at[idx2, 'ZIGZAGv_0.01%_10']
    #     ## Count NaNs after the second non-NaN value
    #     nan_count_after_idx2 = df2.loc[idx2 + 1:, 'ZIGZAGv_0.01%_10'].isna().sum()
    #     if nan_count_after_idx2 >= 1:
    #         if value1 > value2:
    #             ## Find the first occurrence of the highest 'High' value after idx2
    #             idx_min_low = df2.loc[idx2:, 'Low'].idxmin()
    #             idx_max_high = df2.loc[idx2:, 'High'].idxmax()
    #             min_low_value = df2.loc[idx_min_low, 'Low']
    #             max_high_value = df2.loc[idx_max_high, 'High']
    #             # print(min_low_value,max_high_value)
    #             # if df2.at[idx_max_high, 'High'] < value2:
    #             #     df2.at[idx_max_high, 'ZIGZAGv_0.01%_10'] = df2.at[idx_max_high, 'High']
    #             # else:
    #             #     ## If no new high is found, look for the lowest 'Low' value instead
    #             #     idx_min_low = df2.loc[idx2:, 'Low'].idxmin()
    #             #     df2.at[idx_min_low, 'ZIGZAGv_0.01%_10'] = df2.at[idx_min_low, 'Low']
    #             #     df2.at[idx2, 'ZIGZAGv_0.01%_10'] = pd.NA # Remove value2 (set to NaN) in the 'ZIGZAGv_0.01%_10' column
    #             if df2.at[idx_min_low, 'Low'] < value2:
    #                 df2.at[idx_min_low, 'ZIGZAGv_0.01%_10'] = df2.at[idx_min_low, 'Low']
    #                 # Set the second value (value2) to NaN as part of the wave progression
    #                 df2.at[idx2, 'ZIGZAGv_0.01%_10'] = pd.NA
    #             else:
    #                 df2.at[idx_max_high, 'ZIGZAGv_0.01%_10'] = df2.at[idx_max_high, 'High']                

    #         elif value1 < value2:
    #             # print(value1,value2)
    #             ## Find the first occurrence of the lowest 'Low' value after idx2
    #             idx_min_low = df2.loc[idx2:, 'Low'].idxmin()
    #             idx_max_high = df2.loc[idx2:, 'High'].idxmax()
    #             min_low_value = df2.loc[idx_min_low, 'Low']
    #             max_high_value = df2.loc[idx_max_high, 'High']
    #             # print(min_low_value,max_high_value)
    #             # if df2.at[idx_min_low, 'Low'] < value2 and value1 < :
    #             #     df2.at[idx_min_low, 'ZIGZAGv_0.01%_10'] = df2.at[idx_min_low, 'Low']
    #             #     print("v2 > low")
    #             # else:
    #             #     ## If no new low is found, look for the highest 'High' value instead
    #             #     idx_max_high = df2.loc[idx2:, 'High'].idxmax()
    #             #     df2.at[idx_max_high, 'ZIGZAGv_0.01%_10'] = df2.at[idx_max_high, 'High']
    #             #     df2.at[idx2, 'ZIGZAGv_0.01%_10'] = pd.NA # Remove value2 (set to NaN) in the 'ZIGZAGv_0.01%_10' column
    #             #     print("If no new low is found, look for the highest 'High' value instead")
    #             # Update the row with the highest value only if it is greater than value2
    #             if df2.at[idx_max_high, 'High'] > value2:
    #                 df2.at[idx_max_high, 'ZIGZAGv_0.01%_10'] = df2.at[idx_max_high, 'High']
    #                 # Set the second value (value2) to NaN as part of the wave progression
    #                 df2.at[idx2, 'ZIGZAGv_0.01%_10'] = pd.NA
    #             else:
    #                 df2.at[idx_min_low, 'ZIGZAGv_0.01%_10'] = df2.at[idx_min_low, 'Low']

    # # Initialize the new column with NaN
    # df2['blue_wave_count'] = np.nan
    # df2['blue_wave_count'] = df2['blue_wave_count'].astype(str)  # Ensure the column is of type string
    # # Assign "0" when both ZIGZAGv_0.01%_3 and ZIGZAGv_0.01%_10 are not NaN in the same row
    # df2.loc[df2['ZIGZAGv_0.01%_3'].notna() & df2['ZIGZAGv_0.01%_10'].notna(), 'blue_wave_count'] = '0'
    # # Get indices where blue wave count is "0"
    # nonnan_blue_yellow_wave_index = df2[df2['blue_wave_count'] == '0'].index
    # # Handle rows before the first "0"
    # if len(nonnan_blue_yellow_wave_index) > 0:
    #     first_not_nan_index = nonnan_blue_yellow_wave_index[0]
    #     before_first_indices = df2.loc[:first_not_nan_index - 1, 'ZIGZAGv_0.01%_3'].dropna().index
    #     # Assign sequential numbers starting from 1
    #     for j, idx in enumerate(before_first_indices):
    #         df2.loc[idx, 'blue_wave_count'] = str(j + 1)
    # # Iterate between consecutive "0" rows
    # for i in range(len(nonnan_blue_yellow_wave_index) - 1):
    #     start_idx = nonnan_blue_yellow_wave_index[i]
    #     end_idx = nonnan_blue_yellow_wave_index[i + 1]
    #     # Find non-NaN rows in ZIGZAGv_0.01%_3 within the range
    #     not_nan_indices = df2.loc[start_idx + 1:end_idx - 1, 'ZIGZAGv_0.01%_3'].dropna().index
    #     # Assign sequential numbers (as strings) to these rows
    #     for j, idx in enumerate(not_nan_indices):
    #         df2.loc[idx, 'blue_wave_count'] = str(j + 1)
    # # Handle rows after the last "0"
    # if len(nonnan_blue_yellow_wave_index) > 0:
    #     last_not_nan_index = nonnan_blue_yellow_wave_index[-1]
    #     after_last_indices = df2.loc[last_not_nan_index + 1:, 'ZIGZAGv_0.01%_3'].dropna().index

    # # Create new column 'wave_direction' with default value as None
    # df2['wave_direction'] = None
    # # Drop rows where 'Datetime' or 'ZIGZAGv_0.01%_3' is NaN
    # df2_blue_wave_dir = df2.dropna(subset=['Datetime', 'ZIGZAGv_0.01%_3'])
    # # Initialize a list to store wave directions
    # wave_directions = [None]  # First row has no previous comparison, so set to None
    # # Iterate through rows to compare current and next 'ZIGZAGv_0.01%_3' values
    # for i in range(1, len(df2_blue_wave_dir)):
    #     if df2_blue_wave_dir['ZIGZAGv_0.01%_3'].iloc[i] > df2_blue_wave_dir['ZIGZAGv_0.01%_3'].iloc[i - 1]:
    #         wave_directions.append('up')
    #     else:
    #         wave_directions.append('down')
    # # Assign wave directions back to the DataFrame
    # df2_blue_wave_dir['wave_direction'] = wave_directions
    # # Map the updated 'wave_direction' back to the original DataFrame by index
    # df2.loc[df2_blue_wave_dir.index, 'wave_direction'] = df2_blue_wave_dir['wave_direction']

    ######RSI and RSI Stocastic Indicator Added and Columns related to it in df2 data frame

    # Calculate the Stochastic RSI with custom parameters
    # stochrsi = ta.stochrsi( df2['Close'],    # Close prices
    #     length=14,      # Stochastic RSI period (length) , # rsi_length=14,  # RSI period
    #     k=14,           # Fast %K period
    #     d=3,            # Slow %K period (moving average of %K), # mamode='sma',   # Moving Average Mode ('sma', 'ema', etc.) , # talib=True,     # Use TA-Lib RSI , # offset=0        # No offset
    # )
    #TA -LIB StockRSI and RSI
    df2["RSI"] = talib.RSI(df2['Close'], 2)
    df2["STOCH_K"], df2["STOCH_D"] = talib.STOCHRSI(df2["Close"], timeperiod=14, fastk_period=14, fastd_period=3)
    # df2 = df2.join(stochrsi)
    # 1. Calculate the RSI (Relative Strength Index)
    # df2['RSI'] = ta.rsi(df2['Close'], length=2)  # Default RSI period of 2
    # Create RSI Signal Column
    df2['RSI Signal'] = df2['RSI'].apply(
        lambda x: 'Over Bought' if x > 94 else ('Over Sold' if x < 5 else None)
    )

    # Create Stochastic Signal Column
    df2['Stochastic Signal'] = df2.apply(
        lambda row: 'Over Bought' if row['STOCH_K'] > 80 and row['STOCH_D'] > 80 else #STOCHRSIk_14_14_14_3,STOCHRSId_14_14_14_3 , #'STOCH_K, STOCH_D
                ('Over Sold' if row['STOCH_K'] < 20 and row['STOCH_D'] < 20 else None), #STOCHRSIk_14_14_14_3,STOCHRSId_14_14_14_3
        axis=1
    )

    # Create Both Signals Column with additional logic
    def set_both_signals(row):
        # If both signals exist and are the same
        if row['RSI Signal'] and row['Stochastic Signal']:
            if row['RSI Signal'] == row['Stochastic Signal']:  # Same signals
                return row['RSI Signal']

            # If RSI is "Over Bought" and Stochastic is "Over Sold" or vice versa
            elif row['RSI Signal'] == 'Over Bought' and row['Stochastic Signal'] == 'Over Sold':
                return 'RSI OB Stochastic OS'
            elif row['RSI Signal'] == 'Over Sold' and row['Stochastic Signal'] == 'Over Bought':
                return 'RSI OS Stochastic OB'

        # If only RSI Signal exists but Stochastic Signal is None
        elif row['RSI Signal']:
            return f"RSI {row['RSI Signal']} only"

        # If only Stochastic Signal exists but RSI Signal is None
        elif row['Stochastic Signal']:
            return f"Stochastic Signal {row['Stochastic Signal']} only"

        # If neither RSI nor Stochastic signals exist
        return None

    # Apply the function to create the 'Both Signals' column
    df2['Both Signals'] = df2.apply(set_both_signals, axis=1)

    # def Supertrend(data, atr_period, multiplier):
    #     high = data['High']
    #     low = data['Low']
    #     close = data['Close']

    #     # Calculate ATR
    #     price_diffs = [high - low,
    #                 high - close.shift(),
    #                 close.shift() - low]
    #     true_range = pd.concat(price_diffs, axis=1)
    #     true_range = true_range.abs().max(axis=1)
    #     atr = true_range.ewm(alpha=1/atr_period, min_periods=atr_period).mean()

    #     hl2 = (high + low) / 2
    #     final_upperband = upperband = hl2 + (multiplier * atr)
    #     final_lowerband = lowerband = hl2 - (multiplier * atr)

    #     supertrend = [True] * len(data)
    #     for i in range(1, len(data.index)):
    #         curr, prev = i, i - 1

    #         # Use .iloc for positional indexing
    #         if close.iloc[curr] > final_upperband.iloc[prev]: #if close[curr] > final_upperband[prev]: ##Without iloc
    #             supertrend[curr] = True
    #         elif close.iloc[curr] < final_lowerband.iloc[prev]: #close[curr] < final_lowerband[prev]: ##Without iloc
    #             supertrend[curr] = False
    #         else:
    #             supertrend[curr] = supertrend[prev]
    #             if supertrend[curr] == True and final_lowerband.iloc[curr] < final_lowerband.iloc[prev]: # if supertrend[curr] == True and final_lowerband[curr] < final_lowerband[prev]: ##WIthout iloc
    #                 final_lowerband.iloc[curr] = final_lowerband.iloc[prev]
    #             if supertrend[curr] == False and final_upperband.iloc[curr] > final_upperband.iloc[prev]:
    #                 final_upperband.iloc[curr] = final_upperband.iloc[prev]

    #         # To remove bands according to the trend direction
    #         if supertrend[curr] == True:
    #             final_upperband.iloc[curr] = np.nan
    #         else:
    #             final_lowerband.iloc[curr] = np.nan

    #     return pd.DataFrame({
    #         'Supertrend': supertrend,
    #         'final_lowerband': final_lowerband,
    #         'final_upperband': final_upperband
    #     }, index=data.index)

    # supertrend = Supertrend(df2, 7, 5)
    # df2 = df2.join(supertrend)

    return df2

# Create a placeholder for the chart
chart_placeholder = st.empty()

# Run the update function in the background
update_chart(fetch_data, interval="5min")