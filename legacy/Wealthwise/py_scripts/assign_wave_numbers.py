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
import plotly.graph_objects as go
import plotly.io as pio
import time
import streamlit as st

# Global flag to control verbosity
VERBOSE = False

def print_verbose(*args, **kwargs):
    """Custom print_verbose function that respects the global VERBOSE flag."""
    if VERBOSE:
        print(*args, **kwargs)

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
                    # 5924.11 ≤ current value ≤5930.00
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
                    # if i < len(df): # Recheck the condition for the next point

                    if i-1 >= len(df[zigzag_column]):  # Check if i + 1 is out of bounds in the zigzag_column 
                        print_verbose(f"Index i-1 {i-1} is out of bounds in {zigzag_column}. Exiting loop.")
                        if df[zigzag_column].iloc[i-4] >= df[zigzag_column].iloc[i-2]: #It means starting point less than last downward wave which will invalidate ew pattern
                            print_verbose(f"Wave 3 UpTrend condition i th failed as Latest EW point index {i} greater than Start Point EW Wave, stopping evaluation, resetting Downtrend EW list.")
                            wave_numbers = [] # Clear the list to reset the waves
                            break   
                    # Ensure i + 2 is within the bounds of the DataFrame for the zigzag_column
                    elif i >= len(df[zigzag_column]):  # Check if i + 2 is out of bounds in the zigzag_column 
                        print_verbose(f"Index i {i} is out of bounds in {zigzag_column}. Exiting loop.")
                        #Readjust the Wave 4.1 , 4.2 based on i+1 Wave Count
                        # For UpTrend, assign Wave 4 to whichever wave is lower (compare i-3 and i-1) as only i+1 wave present currently
                        # if i-1 >= len(df[zigzag_column]) and df[zigzag_column].iloc[i-1] <= df[zigzag_column].iloc[i-3]:
                        if df[zigzag_column].iloc[i-1] <= df[zigzag_column].iloc[i-3] and df[zigzag_column].iloc[i-1] >= df[zigzag_column].iloc[i-5]:  #not pd.isna(df[zigzag_column].iloc[i-1]) and not pd.isna(df[zigzag_column].iloc[i-3]) Error >> Index out of range
                            for idx in range(len(wave_numbers) - 1, -1, -1):  # Iterate backwards
                                if wave_numbers[idx] in ["Wave 2.1", "Wave 2.2"]:   
                                    # Check if we can shift to i+2 and that it is within bounds
                                    if idx + 2 < len(wave_numbers) and wave_numbers[idx + 2] is None:
                                        wave_numbers[idx + 2] = wave_numbers[idx]  # Move wave to i+2
                                        wave_numbers[idx] = None  # Clear the original index
                        # break  # Exit the loop since i + 2 is not available, to preserve the i+2 Wave Nummbering
                        
                        elif df[zigzag_column].iloc[i-1] < df[zigzag_column].iloc[i-5]: #It means starting point less than last downward wave which will invalidate ew pattern
                            print_verbose(f"Wave 2 UpTrend condition i+2 failed as Latest EW point index {i} greater than Start Point EW Wave, stopping evaluation, resetting Downtrend EW list.")
                            wave_numbers = [] # Clear the list to reset the waves
                            break     

                    # Re-evaluate the condition at the new index
                    elif df[zigzag_column].iloc[i] > start_value and df[zigzag_column].iloc[i-1] > previous_value:# previous_value  df[zigzag_column].iloc[i-5]# 2nd condition to make sure pattern remain intact, i+1 should not be less than wave 2
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
                        # For UpTrend, assign Wave 2 to whichever wave is lower (compare i-1 and i-3)
                        if df[zigzag_column].iloc[i-1] <= df[zigzag_column].iloc[i-3]:
                            for i in range(len(wave_numbers) - 1, -1, -1):  # Iterate backwards
                                if wave_numbers[i] in ["Wave 2.1", "Wave 2.2"]:
                                    if i + 2 < len(wave_numbers) and wave_numbers[i + 2] is None:  # Ensure valid shift
                                        wave_numbers[i + 2] = wave_numbers[i]  # Move to i+2
                                        wave_numbers[i] = None  # Clear original index

                            # If the condition for Wave 2 fails, reset Wave 1 and Wave 2 and start from next point
                            # print_verbose(f"Wave 3 UpTrend condition failed at index {i}. Resetting Wave 1,2.")
                            # wave_numbers = []
                            # break
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
                    #start_value is the end of Wave 1 >> Retracement Level=End of Wave 3−(Wave 3 Length×Retracement Ratio)
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
                    # if i < len(df): # Recheck the condition for the next point
                    if i-1 >= len(df[zigzag_column]):  # Check if i + 1 is out of bounds in the zigzag_column, it means EW 4 is invalid for i th wave 
                        print_verbose(f"Index i-1 {i-1} is out of bounds in {zigzag_column}. Exiting loop.")
                        if df[zigzag_column].iloc[i-4] >= df[zigzag_column].iloc[i-2]: #It means starting point less than last downward wave which will invalidate ew pattern
                            print_verbose(f"Wave 4 UpTrend condition i th failed as Latest EW point index {i} greater than Start Point EW Wave, stopping evaluation, resetting Downtrend EW list.")
                            wave_numbers = [] # Clear the list to reset the waves
                            break   
                    # Ensure i + 2 is within the bounds of the DataFrame for the zigzag_column
                    elif i >= len(df[zigzag_column]):  # Check if i + 2 is out of bounds in the zigzag_column 
                        print_verbose(f"Index i {i} is out of bounds in {zigzag_column}. Exiting loop.")
                        if df[zigzag_column].iloc[i-4] >= df[zigzag_column].iloc[i-2]: #It means starting point less than last downward wave which will invalidate ew pattern
                            print_verbose(f"Wave 4 UpTrend condition i th failed as Latest EW point index {i} greater than Start Point EW Wave, stopping evaluation, resetting Downtrend EW list.")
                            wave_numbers = [] # Clear the list to reset the waves
                            break   

                    # if df[zigzag_column].iloc[i] >= start_value and wave_3_i2_flag_up == True:
                    elif df[zigzag_column].iloc[i] >= df[zigzag_column].iloc[start_idx + 1] and wave_3_i2_flag_up == True:
                        end_wave_3 = df[zigzag_column].iloc[i-1]
                        print_verbose(f"end_wave_3 Value , {end_wave_3}")
                        print_verbose(f"Wave 1 Lengths for Wave 4 Calculation , {wave_1_length}")
                        current_value = df[zigzag_column].iloc[i]
                        print_verbose(f"Current Value, {current_value}")
                        #start_value is the end of Wave 1 >> Retracement Level=End of Wave 3−(Wave 3 Length×Retracement Ratio)
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
                            print_verbose(f"wave_numbers 4 updated at index {i}: {wave_numbers[i]}")
                    # else:
                    #     # If the condition for Wave 4 fails, reset Wave 1 and Wave 2, 3 to None
                    #     print_verbose(f"UpTrend Wave 4 condition failed at index {i}. Resetting Wave 1,2,3.")
                    #     wave_numbers[start_idx] = None  # Reset Wave 1
                    #     wave_numbers[i-1] = None  # Reset Wave 2
                    #     wave_numbers[i-2] = None  # Reset Wave 3
                    #     wave_numbers = []
                    #     # current_wave = 1  # Reset to Wave 1 and continue from this index
                    #     break
                    else:
                        print_verbose(f"Wave 4 UpTrend i+2 condition failed and out of range at index {i}, stopping evaluation.")
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
                    
                    if i-1 >= len(df[zigzag_column]):  # Check if i + 1 is out of bounds in the zigzag_column 
                        print_verbose(f"Index {i-1} is out of bounds in {zigzag_column}. Exiting loop.")
                    # Ensure i + 2 is within the bounds of the DataFrame for the zigzag_column
                    elif i >= len(df[zigzag_column]):  # Check if i + 2 is out of bounds in the zigzag_column 
                        print_verbose(f"Index {i} is out of bounds in {zigzag_column}. Exiting loop.")
                        #Readjust the Wave 4.1 , 4.2 based on i+1 Wave Count
                        # For UpTrend, assign Wave 4 to whichever wave is lower (compare i-3 and i-1) as only i+1 wave present currently
                        # if i-1 >= len(df[zigzag_column]) and df[zigzag_column].iloc[i-1] <= df[zigzag_column].iloc[i-3]:
                        if df[zigzag_column].iloc[i-1] <= df[zigzag_column].iloc[i-3] and df[zigzag_column].iloc[i-1] >= df[zigzag_column].iloc[i-5]:  #not pd.isna(df[zigzag_column].iloc[i-1]) and not pd.isna(df[zigzag_column].iloc[i-3]) Error >> Index out of range
                            for idx in range(len(wave_numbers) - 1, -1, -1):  # Iterate backwards
                                if wave_numbers[idx] in ["Wave 4.1", "Wave 4.2"]:   
                                    # Check if we can shift to i+2 and that it is within bounds
                                    if idx + 2 < len(wave_numbers) and wave_numbers[idx + 2] is None:
                                        wave_numbers[idx + 2] = wave_numbers[idx]  # Move wave to i+2
                                        wave_numbers[idx] = None  # Clear the original index
                        # break  # Exit the loop since i + 2 is not available, to preserve the i+2 Wave Nummbering
                        elif df[zigzag_column].iloc[i-1] < df[zigzag_column].iloc[i-5]: #It means starting point less than last downward wave which will invalidate ew pattern
                            print_verbose(f"Wave 4 UpTrend condition i+2 failed as Latest EW point index {i} greater than Start Point EW Wave, stopping evaluation, resetting Downtrend EW list.")
                            wave_numbers = [] # Clear the list to reset the waves
                            break  
                    # Condition of 3rd Wave Failure 
                    elif wave_3_i2_flag_up and i < len(df) and df[zigzag_column].iloc[i] > df[zigzag_column].iloc[i-2]: # and wave_4_i2_flag_up == True
                        print_verbose(df[zigzag_column].iloc[i], df[zigzag_column].iloc[i-2])  #For i +=2, i-2 will be Wave 3
                        print_verbose(f"UpTrend Wave 5 condition failed at index {i}. Trying the next point for Wave 5.")
                        if df[zigzag_column].iloc[i-1] >= df[zigzag_column].iloc[i-3]:
                            end_wave_4 = df[zigzag_column].iloc[i-1]
                        else:
                            end_wave_4 = df[zigzag_column].iloc[i-3]
                        # end_wave_4 = df[zigzag_column].iloc[i-1]
                        print_verbose(f"end_wave_4 Value , {end_wave_4}")
                        print_verbose(f"Wave 1 Length for Wave 5 Calculation , {wave_1_length}")
                        wave4_length = end_wave_3 - end_wave_4
                        print_verbose(f"Wave 4 Length for Wave 5 Calculation , {wave4_length}")
                        current_value = df[zigzag_column].iloc[i]
                        print_verbose(f"Current Value: {current_value}")
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

                        # # # #Now Assign Correct Label to Wave 2 for DownTrend Whicheven Wave is Higher, Compare i-1 & i-3 and assigne Wave 2 whichver wave is higher value
                        # if df[zigzag_column].iloc[i-1] >= df[zigzag_column].iloc[i-3]:
                        #     for i in range(len(wave_numbers) - 1, -1, -1):  # Iterate backwards
                        #         if wave_numbers[i] in ["Wave 4.1", "Wave 4.2"]:
                        #             if i + 2 < len(wave_numbers) and wave_numbers[i + 2] is None:  # Ensure valid shift
                        #                 wave_numbers[i + 2] = wave_numbers[i]  # Move to i+2
                        #                 wave_numbers[i] = None  # Clear original index

                        # For UpTrend, assign Wave 4 to whichever wave is lower (compare i-1 and i-3)
                        if df[zigzag_column].iloc[i-1] <= df[zigzag_column].iloc[i-3]:
                            for i in range(len(wave_numbers) - 1, -1, -1):  # Iterate backwards
                                if wave_numbers[i] in ["Wave 4.1", "Wave 4.2"]:
                                    if i + 2 < len(wave_numbers) and wave_numbers[i + 2] is None:  # Ensure valid shift
                                        wave_numbers[i + 2] = wave_numbers[i]  # Move to i+2
                                        wave_numbers[i] = None  # Clear original index

                        
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
                    
                    elif i < len(df) and wave_3_i2_flag_up == False and df[zigzag_column].iloc[i] > df[zigzag_column].iloc[i-4] and df[zigzag_column].iloc[i-5] < df[zigzag_column].iloc[i-1] : #Condition for 5th Wave Failure  
                        print_verbose(df[zigzag_column].iloc[i], df[zigzag_column].iloc[i-4]) 
                        if df[zigzag_column].iloc[i-1] >= df[zigzag_column].iloc[i-3]:
                            end_wave_4 = df[zigzag_column].iloc[i-1]
                        else:
                            end_wave_4 = df[zigzag_column].iloc[i-3]
                        # end_wave_4 = df[zigzag_column].iloc[i-1]
                        print_verbose(f"end_wave_4 Value , {end_wave_4}")
                        print_verbose(f"Wave 1 Length for Wave 5 Calculation , {wave_1_length}")
                        wave4_length = end_wave_3 - end_wave_4
                        print_verbose(f"Wave 4 Length for Wave 5 Calculation , {wave4_length}")
                        current_value = df[zigzag_column].iloc[i]
                        print_verbose(f"Current Value: {current_value}")
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

                        # For UpTrend, assign Wave 4 to whichever wave is lower (compare i-1 and i-3)
                        if df[zigzag_column].iloc[i-1] <= df[zigzag_column].iloc[i-3]:
                            for i in range(len(wave_numbers) - 1, -1, -1):  # Iterate backwards
                                if wave_numbers[i] in ["Wave 4.1", "Wave 4.2"]:
                                    if i + 2 < len(wave_numbers) and wave_numbers[i + 2] is None:  # Ensure valid shift
                                        wave_numbers[i + 2] = wave_numbers[i]  # Move to i+2
                                        wave_numbers[i] = None  # Clear original index
                        
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
                        # if df[zigzag_column].iloc[i+1] >= df[zigzag_column].iloc[i-1]: #For i+4 condition
                        #     for i in range(len(wave_numbers) - 1, -1, -1):  # Iterate backwards
                        #         if wave_numbers[i] in ["Wave 4.1", "Wave 4.2"]: 
                        #             if i + 2 < len(wave_numbers) and wave_numbers[i + 2] is None:  # Ensure valid shift
                        #                 wave_numbers[i + 2] = wave_numbers[i]  # Move to i+2
                        #                 wave_numbers[i] = None  # Clear original index4
                        
                        # For UpTrend, assign Wave 4 to whichever wave is lower (compare i-1 and i-3)
                        if df[zigzag_column].iloc[i-1] <= df[zigzag_column].iloc[i-3]:
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
                    break  #Not requred after this
                    print_verbose(f"wave_numbers at 2nd else of 5.2 at index {6}: {wave_numbers[6]}")
                    # If condition fails, we check the next point by incrementing the index by 2 and re-evaluating the conditions
                    print_verbose(f"UpTrend Wave 6,7,8,9 or a,b,c condition failed at index {i}. Trying the next point for Wave 6,7,8,9 or a,b,c.")
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
        #Add one condition to tackle such list which is not correct: ['Wave 1', None, None, 'Wave 2.1', 'Wave 3.2', None, 'Wave 5.1', 'Wave 4.1']
        if wave_numbers and wave_numbers[-1] in ['Wave 4.1', 'Wave 4.2'] and wave_numbers[-2] in ['Wave 5.1', 'Wave 5.2']:
                wave_numbers = []  # Empty the list
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
                    #Retracement level=End point+(Start point−End point)×Fibonacci ratio
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
                    #Fibonacci Extension level=Start point+(Wave 1 length)×Fibonacci ratio
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
                    i += 2  # Move the index by 2

                    if i-1 >= len(df[zigzag_column]):  # Check if i + 1 is out of bounds in the zigzag_column 
                        print_verbose(f"Index {i-1} is out of bounds in {zigzag_column}. Exiting loop.")
                        if df[zigzag_column].iloc[i-4] <= df[zigzag_column].iloc[i-2]: #It means starting point less than last downward wave which will invalidate ew pattern
                            print_verbose(f"Wave 3 DownTrend condition i th failed as Latest EW point index {i} greater than Start Point EW Wave, stopping evaluation, resetting Downtrend EW list.")
                            wave_numbers = [] # Clear the list to reset the waves
                            break  
                    # Ensure i + 2 is within the bounds of the DataFrame for the zigzag_column
                    elif i >= len(df[zigzag_column]):  # Check if i + 2 is out of bounds in the zigzag_column 
                        print_verbose(f"Index {i} is out of bounds in {zigzag_column}. Exiting loop.")
                        #Readjust the Wave 4.1 , 4.2 based on i+1 Wave Count
                        # For UpTrend, assign Wave 4 to whichever wave is lower (compare i-3 and i-1) as only i+1 wave present currently
                        # if i-1 >= len(df[zigzag_column]) and df[zigzag_column].iloc[i-1] <= df[zigzag_column].iloc[i-3]:
                        if df[zigzag_column].iloc[i-1] >= df[zigzag_column].iloc[i-3] and df[zigzag_column].iloc[i-1] <= df[zigzag_column].iloc[i-5]:  #not pd.isna(df[zigzag_column].iloc[i-1]) and not pd.isna(df[zigzag_column].iloc[i-3]) Error >> Index out of range
                            for idx in range(len(wave_numbers) - 1, -1, -1):  # Iterate backwards
                                if wave_numbers[idx] in ["Wave 2.1", "Wave 2.2"]:   
                                    # Check if we can shift to i+2 and that it is within bounds
                                    if idx + 2 < len(wave_numbers) and wave_numbers[idx + 2] is None:
                                        wave_numbers[idx + 2] = wave_numbers[idx]  # Move wave to i+2
                                        wave_numbers[idx] = None  # Clear the original index
                        elif df[zigzag_column].iloc[i-1] > df[zigzag_column].iloc[i-5]: #It means starting point less than last downward wave which will invalidate ew pattern
                            print_verbose(f"Wave 2 DownTrend condition i+2 failed as Latest EW point index {i} greater than Start Point EW Wave, stopping evaluation, resetting Downtrend EW list.")
                            wave_numbers = [] # Clear the list to reset the waves
                            break                            
                        
                    # Re-evaluate the condition at the new index
                    elif df[zigzag_column].iloc[i] < start_value and df[zigzag_column].iloc[i-1] <  previous_value: # 2nd condition to make sure pattern remain intact
                        # Calculate Fibonacci Extensions for Wave 3 using Wave 1 and Wave 2
                        wave_1_length = previous_value - start_value  # Length of Wave 1
                        print_verbose(start_value,previous_value, wave_1_length)
                        current_value = df[zigzag_column].iloc[i]
                        print_verbose(f"Rechecking for Wave 3 at new index {i}, Current Value: {current_value}")
                        #Fibonacci Extension level=Start point+(Wave 1 length)×Fibonacci ratio
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
                        # else:
                        #     # If the condition for Wave 3 fails, reset Wave 1 and Wave 2 and start from next point
                        #     print_verbose(f"Wave 3 DownTrend condition failed at index {i}. Resetting Wave 1,2,3")
                        #     wave_numbers = [] # Clear the list to reset the waves
                        #     break
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
                    #start_value is the end of Wave 1 >> Retracement Level=End of Wave 3−(Wave 3 Length×Retracement Ratio)
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
                    i += 2  # Increment by 2 # Move the index by 2 to skip the current point and proceed to the next
                    # if i < len(df): # Recheck the condition for the next point
                    # if i + 2 < len(df):  # Ensure we don't go out of bounds
                    
                    if i-1 >= len(df[zigzag_column]):  # Check if i + 1 is out of bounds in the zigzag_column 
                        print_verbose(f"Index i-1 {i-1} is out of bounds in {zigzag_column}. Exiting loop.")
                        if df[zigzag_column].iloc[i-4] <= df[zigzag_column].iloc[i-2]: #It means starting point less than last downward wave which will invalidate ew pattern
                            print_verbose(f"Wave 4 DownTrend condition i th failed as Latest EW point index {i} greater than Start Point EW Wave, stopping evaluation, resetting Downtrend EW list.")
                            wave_numbers = [] # Clear the list to reset the waves
                            break  
                    # Ensure i + 2 is within the bounds of the DataFrame for the zigzag_column
                    elif i >= len(df[zigzag_column]):  # Check if i + 2 is out of bounds in the zigzag_column 
                        print_verbose(f"Index i {i} is out of bounds in {zigzag_column}. Exiting loop.")
                        if df[zigzag_column].iloc[i-4] <= df[zigzag_column].iloc[i-2]: #It means starting point less than last downward wave which will invalidate ew pattern
                            print_verbose(f"Wave 4 DownTrend condition i th failed as Latest EW point index {i} greater than Start Point EW Wave, stopping evaluation, resetting Downtrend EW list.")
                            wave_numbers = [] # Clear the list to reset the waves
                            break  

                    elif df[zigzag_column].iloc[i] <= df[zigzag_column].iloc[start_idx + 1] and wave_3_i2_flag_down == True: #  i < len(df) and  start_value
                        end_wave_3 = df[zigzag_column].iloc[i-1]
                        print_verbose(f"end_wave_3 Value , {end_wave_3}")
                        print_verbose(f"Wave 1 Lengths for DownTrend Wave 4 Calculation , {wave_1_length}")
                        current_value = df[zigzag_column].iloc[i]
                        print_verbose(f"Current Value: {current_value}")
                        #start_value is the end of Wave 1 >> Retracement Level=End of Wave 3−(Wave 3 Length×Retracement Ratio)
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
                    # else:
                    #     # If the condition for Wave 3 fails, reset Wave 1 and Wave 2 and start from next point
                    #     print_verbose(f"Wave 4 DownTrend condition failed at index {i}. Resetting Wave 1,2,3")
                    #     wave_numbers[start_idx] = None  # Reset Wave 1
                    #     wave_numbers[i] = None  # Reset Wave 2
                    #     wave_numbers[i-1] = None  # Reset Wave 2
                    #     wave_numbers[i-2] = None  # Reset Wave 3
                    #     wave_numbers = [] # Clear the list to reset the waves
                        #     break
                    else:
                        print_verbose(f"DownTrend Wave 4 i+2 condition failed and out of range at index {i}, stopping evaluation.")
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
                    print_verbose(f"DownTrend Wave 5 condition failed at index {i}. Trying the next point for Wave 5.")
                    ##Move the index by 2 to skip the current point and proceed to the next
                    i += 2  # Increment by 2
                    
                    if i-1 >= len(df[zigzag_column]):  # Check if i + 1 is out of bounds in the zigzag_column 
                        print_verbose(f"Index {i-1} is out of bounds in {zigzag_column}. Exiting loop.")
                    # Ensure i + 2 is within the bounds of the DataFrame for the zigzag_column
                    elif i >= len(df[zigzag_column]):  # Check if i + 2 is out of bounds in the zigzag_column 
                        print_verbose(f"Index {i} is out of bounds in {zigzag_column}. Exiting loop.")
                        #Readjust the Wave 4.1 , 4.2 based on i+1 Wave Count
                        # For UpTrend, assign Wave 4 to whichever wave is lower (compare i-3 and i-1) as only i+1 wave present currently
                        # if i-1 >= len(df[zigzag_column]) and df[zigzag_column].iloc[i-1] <= df[zigzag_column].iloc[i-3]:
                        if df[zigzag_column].iloc[i-1] >= df[zigzag_column].iloc[i-3] and df[zigzag_column].iloc[i-1] <= df[zigzag_column].iloc[i-5]:  #not pd.isna(df[zigzag_column].iloc[i-1]) and not pd.isna(df[zigzag_column].iloc[i-3]) Error >> Index out of range
                            for idx in range(len(wave_numbers) - 1, -1, -1):  # Iterate backwards
                                if wave_numbers[idx] in ["Wave 4.1", "Wave 4.2"]:   
                                    # Check if we can shift to i+2 and that it is within bounds
                                    if idx + 2 < len(wave_numbers) and wave_numbers[idx + 2] is None:
                                        wave_numbers[idx + 2] = wave_numbers[idx]  # Move wave to i+2
                                        wave_numbers[idx] = None  # Clear the original index

                        elif df[zigzag_column].iloc[i-1] > df[zigzag_column].iloc[i-5]: #It means starting point less than last downward wave which will invalidate ew pattern
                            print_verbose(f"Wave 4 DownTrend condition i+2 failed as Latest EW point index {i} greater than Start Point EW Wave, stopping evaluation, resetting Downtrend EW list.")
                            wave_numbers = [] # Clear the list to reset the waves
                            break   
                    
                    # Condition of 3rd Wave Failure
                    elif wave_3_i2_flag_down and i < len(df) and df[zigzag_column].iloc[i] < df[zigzag_column].iloc[i-2]:
                        print_verbose(df[zigzag_column].iloc[i], df[zigzag_column].iloc[i-2]) #For i +=2, i-2 will be Wave 3
                        if df[zigzag_column].iloc[i-1] >= df[zigzag_column].iloc[i-3]:
                            end_wave_4 = df[zigzag_column].iloc[i-1]
                        else:
                            end_wave_4 = df[zigzag_column].iloc[i-3]
                        # end_wave_4 = max(df['ZIGZAGv_0.01%_3'].iloc[i - 1],df['ZIGZAGv_0.01%_3'].iloc[i + 1]) #, df['ZIGZAGv_0.01%_3'].iloc[i - 3]
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
                        if df[zigzag_column].iloc[i-1] >= df[zigzag_column].iloc[i-3]:
                            for i in range(len(wave_numbers) - 1, -1, -1):  # Iterate backwards
                                if wave_numbers[i] in ["Wave 4.1", "Wave 4.2"]:
                                    if i + 2 < len(wave_numbers) and wave_numbers[i + 2] is None:  # Ensure valid shift
                                        wave_numbers[i + 2] = wave_numbers[i]  # Move to i+2
                                        wave_numbers[i] = None  # Clear original index
                    
                    elif i < len(df) and wave_3_i2_flag_down == False and df[zigzag_column].iloc[i] < df[zigzag_column].iloc[i-4] and df[zigzag_column].iloc[i-5] > df[zigzag_column].iloc[i-1]: #Condition for 5th Wave Failure  
                        print_verbose(df[zigzag_column].iloc[i], df[zigzag_column].iloc[i-4]) 
                        if df[zigzag_column].iloc[i-1] >= df[zigzag_column].iloc[i-3]:
                            end_wave_4 = df[zigzag_column].iloc[i-1]
                        else:
                            end_wave_4 = df[zigzag_column].iloc[i-3]
                        # end_wave_4 = max(df['ZIGZAGv_0.01%_3'].iloc[i - 1],df['ZIGZAGv_0.01%_3'].iloc[i + 1]) #, df['ZIGZAGv_0.01%_3'].iloc[i - 3]
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
                        if df[zigzag_column].iloc[i-1] >= df[zigzag_column].iloc[i-3]:
                            for i in range(len(wave_numbers) - 1, -1, -1):  # Iterate backwards
                                if wave_numbers[i] in ["Wave 4.1", "Wave 4.2"]:
                                    if i + 2 < len(wave_numbers) and wave_numbers[i + 2] is None:  # Ensure valid shift
                                        wave_numbers[i + 2] = wave_numbers[i]  # Move to i+2
                                        wave_numbers[i] = None  # Clear original index

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

                    ### This condition is for i+2 3rd Wave and i+2 5th Wave , If 3rd and 5th both ith Wave Failed
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
                    break  #Not requred after this
                    print_verbose(f"wave_numbers at 2nd else of 5.2 at index {6}: {wave_numbers[6]}")
                    # If condition fails, we check the next point by incrementing the index by 2 and re-evaluating the conditions
                    print_verbose(f"UpTrend Wave 6,7,8,9 or a,b,c condition failed at index {i}. Trying the next point for Wave 6,7,8,9 or a,b,c.")
                    # break
                    i += 2  # Increment by 2
                    if i < len(df) and df[zigzag_column].iloc[i] > df[zigzag_column].iloc[i-1] and df[zigzag_column].iloc[i] <= df[zigzag_column].iloc[i-2] and wave_5_i2_flag_down == False and  wave_5_i4_flag_down == False:
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
        #Add one condition to tackle such list which is not correct: ['Wave 1', None, None, 'Wave 2.1', 'Wave 3.2', None, 'Wave 5.1', 'Wave 4.1']
        if wave_numbers and wave_numbers[-1] in ['Wave 4.1', 'Wave 4.2'] and wave_numbers[-2] in ['Wave 5.1', 'Wave 5.2']:
                wave_numbers = []  # Empty the list
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
                    if (prev_value > waveb1) and (wavea1 > wavec1): #waveb1 > prev_value
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
                        # print_verbose(wavea1,waveb1,wavec1)
                        print_verbose("wave a,b,c are present in Double Three and W is added")
                    else:
                        wave_numbers_inner = [] # Clear the list to reset the waves
                        wave_numbers_outer = [] # Clear the list to reset the waves
                        break

            elif current_wave_inner == "((c1))":
                if i+1 < len(df): # X Point having 1 Wave
                    wavec1 =  df[zigzag_column].iloc[i]
                    waveb1 =  df[zigzag_column].iloc[i-1]
                    wavec2 = df[zigzag_column].iloc[i+1]
                    wave_start_value =  df[zigzag_column].iloc[i-3]
                    x_at_i1 =  False
                    x_at_i1_5_waves = False
                    if (wavec2 > waveb1) and (wave_start_value > wavec2): #Wavec > Waveb1
                        x_reference_value = wave_start_value
                        wave_numbers_inner[i+1] = '((c))'
                        wave_numbers_outer[i+1] = 'X'
                        current_wave_inner = '((c2))'
                        x_at_i1 = True
                        if i+3 < len(df) and (df[zigzag_column].iloc[i+1]) < (df[zigzag_column].iloc[i+3]) and (df[zigzag_column].iloc[i-3] > df[zigzag_column].iloc[i+3]): ## Suppose there are 3 rows instead of 1 & 3rd Row Greater than i+1 row then shift X to i+3 row and i+3 > i+1
                            print_verbose("wave c2 are present in Double Three and X is added based on prev value")
                            wave_numbers_inner[i+1] = '((a))'
                            wave_numbers_inner[i+2] = '((b))'
                            wave_numbers_inner[i+3] = '((c))'
                            wave_numbers_outer[i+3] = 'X'
                            wave_numbers_outer[i+1] = None
                            current_wave_inner = '((c2))'
                            if i+5 < len(df) and (df[zigzag_column].iloc[i+3]) < (df[zigzag_column].iloc[i+5]):# and (df[zigzag_column].iloc[i-3] > df[zigzag_column].iloc[i+5]): ## Suppose there are 5 rows instead of 3 & 5th Row Greater than i+3 row then shift X to i+5 row and i+5 > i+3
                                wave_numbers_inner[i+1] = '((a))'
                                wave_numbers_inner[i+4] = '((b))'
                                wave_numbers_inner[i+5] = '((c))'
                                wave_numbers_outer[i+5] = 'X'
                                wave_numbers_outer[i+3] = None
                                current_wave_inner = '((c2))'
                                x_at_i1_5_waves = True
                    # elif (wavec2 < waveb1) and (wave_start_value > wavec2): COndition Commented as lot of WXY Patterns formed on Downward Impulse Wave
                    #     x_reference_value = wave_start_value
                    #     wave_numbers_inner[i+1] = '((c))'
                    #     wave_numbers_outer[i+1] = 'X'
                    #     current_wave_inner = '((c2))'
                    #     x_at_i1 = True
                    #     if i+3 < len(df) and (df[zigzag_column].iloc[i+1]) < (df[zigzag_column].iloc[i+3]) and (df[zigzag_column].iloc[i-3] > df[zigzag_column].iloc[i+3]): ## Suppose there are 3 rows instead of 1 & 3rd Row Greater than i+1 row then shift X to i+3 row and i+3 > i+1
                    #         print_verbose("wave c2 are present in Double Three and X is added based on prev value")
                    #         wave_numbers_inner[i+1] = '((a))'
                    #         wave_numbers_inner[i+2] = '((b))'
                    #         wave_numbers_inner[i+3] = '((c))'
                    #         wave_numbers_outer[i+3] = 'X'
                    #         wave_numbers_outer[i+1] = None
                    #         current_wave_inner = '((c2))'
                    #         if i+5 < len(df) and (df[zigzag_column].iloc[i+3]) < (df[zigzag_column].iloc[i+5]):# and (df[zigzag_column].iloc[i-3] > df[zigzag_column].iloc[i+5]): ## Suppose there are 5 rows instead of 3 & 5th Row Greater than i+3 row then shift X to i+5 row and i+5 > i+3
                    #             wave_numbers_inner[i+1] = '((a))'
                    #             wave_numbers_inner[i+4] = '((b))'
                    #             wave_numbers_inner[i+5] = '((c))'
                    #             wave_numbers_outer[i+5] = 'X'
                    #             wave_numbers_outer[i+3] = None
                    #             current_wave_inner = '((c2))'
                    #             x_at_i1_5_waves = True
                    elif (wavec2 > waveb1) and (df[zigzag_column].iloc[i-5] > wavec2): ## Checking for 2nd Prev Value
                        x_reference_value = df[zigzag_column].iloc[i-5] 
                        wave_numbers_inner[i+1] = '((c))'
                        wave_numbers_outer[i+1] = 'X'
                        current_wave_inner = '((c2))'
                        x_at_i1 = True
                        print_verbose("wave c2 are present in Double Three and X is added based on 2nd prev value")
                        if i+3 < len(df) and (df[zigzag_column].iloc[i+1]) < (df[zigzag_column].iloc[i+3]) and (df[zigzag_column].iloc[i-5] > df[zigzag_column].iloc[i+3]): ## Suppose there are 3 rows instead of 1 & 3rd Row Greater than i+1 row then shift X to i+3 row and i+3 > i+1
                            print_verbose("wave c2 are present in Double Three and X is added based on 2nd prev value")
                            wave_numbers_inner[i+1] = '((a))'
                            wave_numbers_inner[i+2] = '((b))'
                            wave_numbers_inner[i+3] = '((c))'
                            wave_numbers_outer[i+3] = 'X'
                            wave_numbers_outer[i+1] = None
                            current_wave_inner = '((c2))' 
                            if i+5 < len(df) and (df[zigzag_column].iloc[i+3]) < (df[zigzag_column].iloc[i+5]):# and (df[zigzag_column].iloc[i-5] > df[zigzag_column].iloc[i+5]): ## Suppose there are 5 rows instead of 3 & 5th Row Greater than i+3 row then shift X to i+5 row and i+5 > i+3
                                wave_numbers_inner[i+1] = '((a))'
                                wave_numbers_inner[i+4] = '((b))'
                                wave_numbers_inner[i+5] = '((c))'
                                wave_numbers_outer[i+5] = 'X'
                                wave_numbers_outer[i+3] = None
                                current_wave_inner = '((c2))'
                                x_at_i1_5_waves = True
                    elif (wavec2 > waveb1) and (df[zigzag_column].iloc[i-7] > wavec2): ## Checking for 4th Prev Value
                        x_reference_value = df[zigzag_column].iloc[i-7] 
                        # print_verbose(x_reference_value)
                        # print_verbose(wavec2)
                        # print_verbose(df[zigzag_column].iloc[i+3])
                        wave_numbers_inner[i+1] = '((c))'
                        wave_numbers_outer[i+1] = 'X'
                        current_wave_inner = '((c2))'
                        x_at_i1 = True
                        # if i + 3 < len(df) and df[zigzag_column].iloc[i + 1] < df[zigzag_column].iloc[i + 3]:# and df[zigzag_column].iloc[i - 7] > df[zigzag_column].iloc[i + 3]: ## Suppose there are 3 rows instead of 1 & 3rd Row Greater than i+1 row then shift X to i+3 row and i+3 > i+1 and compare wavec and x_ref value again
                        if ( i + 3 < len(df) and df[zigzag_column].iloc[i + 1] < df[zigzag_column].iloc[i + 3] and x_reference_value > df[zigzag_column].iloc[i + 3]):
                            print_verbose("wave c2 are present in Double Three and X is added based on 4th prev value")
                            wave_numbers_inner[i+1] = '((a))'
                            wave_numbers_inner[i+2] = '((b))'
                            wave_numbers_inner[i+3] = '((c))'
                            wave_numbers_outer[i+3] = 'X'
                            wave_numbers_outer[i+1] = None
                            current_wave_inner = '((c2))'   
                            if i+5 < len(df) and (df[zigzag_column].iloc[i+3]) < (df[zigzag_column].iloc[i+5]):# and (df[zigzag_column].iloc[i-7] > df[zigzag_column].iloc[i+5]): ## Suppose there are 5 rows instead of 3 & 5th Row Greater than i+3 row then shift X to i+5 row and i+5 > i+3
                                wave_numbers_inner[i+1] = '((a))'
                                wave_numbers_inner[i+4] = '((b))'
                                wave_numbers_inner[i+5] = '((c))'
                                wave_numbers_outer[i+5] = 'X'
                                wave_numbers_outer[i+3] = None
                                current_wave_inner = '((c2))'    
                                x_at_i1_5_waves = True                     
                    elif (wavec2 > waveb1) and (df[zigzag_column].iloc[i-9] > wavec2): ## Checking for 6th Prev Value
                        x_reference_value = df[zigzag_column].iloc[i-9] 
                        wave_numbers_inner[i+1] = '((c))'
                        wave_numbers_outer[i+1] = 'X'
                        current_wave_inner = '((c2))'
                        x_at_i1 = True
                        if i + 3 < len(df) and df[zigzag_column].iloc[i + 1] < df[zigzag_column].iloc[i + 3] and x_reference_value > df[zigzag_column].iloc[i + 3]: ##i + 3 < len(df) and df[zigzag_column].iloc[i + 1] < df[zigzag_column].iloc[i + 3]and   ## Suppose there are 3 rows instead of 1 & 3rd Row Greater than i+1 row then shift X to i+3 row and i+3 > i+1
                            print_verbose("wave c2 are present in Double Three and X is added based on 6th prev value")
                            wave_numbers_inner[i+1] = '((a))'
                            wave_numbers_inner[i+2] = '((b))'
                            wave_numbers_inner[i+3] = '((c))'
                            wave_numbers_outer[i+3] = 'X'
                            wave_numbers_outer[i+1] = None
                            current_wave_inner = '((c2))'    
                            if i+5 < len(df) and (df[zigzag_column].iloc[i+3]) < (df[zigzag_column].iloc[i+5]) and (df[zigzag_column].iloc[i-9] > df[zigzag_column].iloc[i+5]): ## Suppose there are 5 rows instead of 3 & 5th Row Greater than i+3 row then shift X to i+5 row and i+5 > i+3
                                wave_numbers_inner[i+1] = '((a))'
                                wave_numbers_inner[i+4] = '((b))'
                                wave_numbers_inner[i+5] = '((c))'
                                wave_numbers_outer[i+5] = 'X'
                                wave_numbers_outer[i+3] = None
                                current_wave_inner = '((c2))'
                                x_at_i1_5_waves = True
                    else:
                        wave_numbers_inner = [] # Clear the list to reset the waves
                        wave_numbers_outer = [] # Clear the list to reset the waves
                        break

                elif i+3 < len(df):   # Standard X Position
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

            elif current_wave_inner == "((c2))":
                # Initialize pattern match flags before entering the block
                pattern_matched_i3 = False
                pattern_matched_i5_custom = False
                pattern_matched_i5_zigzag = False

                # if not x_at_i1 and i+1 < len(df): # Checking X as Two Wave Conditiona and Y as 1 Wave Condition
                #     wavec1 =  df[zigzag_column].iloc[i-2] ## W Point
                #     wavec2 =  df[zigzag_column].iloc[i+2] ## X Point
                #     wavec3 = df[zigzag_column].iloc[i+2] ## Y Point
                #     if wavec1 > wavec3: ## W > Y
                #         wave_numbers_inner[i+2] = '((c))'
                #         wave_numbers_outer[i+2] = 'Y'
                #         break

                if not x_at_i1_5_waves and i+3 < len(df):  # Only check 3-wave Y if 5-wave isn't possible: # Checking X as Single Wave Conditiona and Y as 3 Wave Condition having 3 waves in downtrend
                    wavec2 = df[zigzag_column].iloc[i]
                    wavea3 = df[zigzag_column].iloc[i+1]
                    waveb3 = df[zigzag_column].iloc[i+2]
                    wavec3 = df[zigzag_column].iloc[i+3]  
                    print_verbose(wavec2,wavea3, waveb3, wavec3)
                    if (wavec2 > waveb3) and (waveb3 > wavea3) and (wavea3 > wavec3) and (x_reference_value > wavec2):
                        print_verbose("Check for Custom Double Three Condition having 1 inner Wave in X and 3 inner wave in Y")
                        wave_numbers_inner[i+1] = '((a))'
                        wave_numbers_inner[i+2] = '((b))'
                        wave_numbers_inner[i+3] = '((c))'
                        wave_numbers_outer[i+3] = 'Y'
                        print_verbose("Custom Double Three Condition having 1 inner Wave in X and 3 inner wave in Y Formed")
                        if i+5 < len(df): # To check for Impulse Elliot Wave DownTrend till 5th Wave as Y Point
                            waved3 = df[zigzag_column].iloc[i+4] 
                            wavee3 = df[zigzag_column].iloc[i+5] 
                            if (waveb3 > waved3) and (wavec3 > wavee3):
                                wave_numbers_inner[i+4] = '((d))'
                                wave_numbers_inner[i+5] = '((e))'
                                wave_numbers_outer[i+5] = 'Y'
                                wave_numbers_outer[i+3] = None  # If i+5 is assigned 'Y', set i+3 to None
                                print_verbose("Custom Double Three Condition having 1 inner Wave in X and 5 inner wave in Y Formed")
                                break # Success — exit loop
                        pattern_matched_i3 = True
                        break  # Success — exit loop
                    # else:  # Pattern failed, check if i+5 exists
                    #     if i + 5 < len(df):  # If i+5 exists, continue to the next iteration
                    #         continue  # Skip the current iteration and move to the next iteration of the loop
                    #     else:
                    #         print_verbose("Pattern failed, resetting lists.")
                    #         wave_numbers_inner = []  # Clear the list to reset the waves
                    #         wave_numbers_outer = []  # Clear the list to reset the waves
                    #         break  # If i+5 doesn't exist, break out of the loop since no further patterns can be checked
                
                if x_at_i1_5_waves and i+7 < len(df): # Condition Contains X at Wave 5 in EW and Y at Wave 3 DTrend EW or Wave 5 DTrend EW
                    wavec2 = df[zigzag_column].iloc[i+4] #Existing poistion of wave c2 is i
                    wavea3 = df[zigzag_column].iloc[i+5]
                    waveb3 = df[zigzag_column].iloc[i+6]
                    wavec3 = df[zigzag_column].iloc[i+7]
                    if (wavec2 > waveb3) and (waveb3 > wavea3) and (waveb3 > wavec3) and (x_reference_value > wavec2): ## Sometime in wave building a3 >c3 not possible as in Live data, pattern formation is going on so compared b3 with a3 & c3
                        print_verbose("Check for Custom Double Three Condition having 5 Impulse UTrend inner EW Wave in X and 3 inner wave in Y")
                        wave_numbers_inner[i+5] = '((a))'
                        wave_numbers_inner[i+6] = '((b))'
                        wave_numbers_inner[i+7] = '((c))'
                        wave_numbers_outer[i+7] = 'Y'
                        print_verbose("Custom Double Three Condition having 5 Impulse UTrend inner EW Wave in X and 3 inner wave in Y Formed")
                        if i+9 < len(df):  # Condition Contains X at Wave 5 in EW and Y at Wave 5 DTrend EW or Wave 5 DTrend EW
                            waved3 = df[zigzag_column].iloc[i+8]
                            wavee3 = df[zigzag_column].iloc[i+9]
                            if (waveb3 > waved3) and (wavec3 > wavee3):
                                wave_numbers_inner[i+8] = '((d))'
                                wave_numbers_inner[i+9] = '((e))'
                                wave_numbers_outer[i+9] = 'Y'
                                wave_numbers_outer[i+7] = None ## Remove Y wave at i+7
                        break
                    # else:
                    #     print_verbose("Pattern failed, resetting lists.")
                    #     wave_numbers_inner = [] # Clear the list to reset the waves
                    #     wave_numbers_outer = [] # Clear the list to reset the waves
                    #     break

                if not pattern_matched_i3 and i+5 < len(df): # Y Condition for Contracting/Symmetrical Triangle (DownTrend)
                    wavec2 = df[zigzag_column].iloc[i]
                    wavea3 = df[zigzag_column].iloc[i+1]
                    waveb3 = df[zigzag_column].iloc[i+2]
                    wavec3 = df[zigzag_column].iloc[i+3] 
                    waved3 = df[zigzag_column].iloc[i+4]
                    wavee3 = df[zigzag_column].iloc[i+5]
                    if (wavec2 > waveb3) and (waveb3 > wavea3) and (wavec3 > wavea3) and (waveb3 > waved3):
                        print_verbose("Check for Custom Double Three Condition having 1 inner Wave in X and 5 inner wave in Y")
                        wave_numbers_inner[i+1] = '((a))'
                        wave_numbers_inner[i+2] = '((b))'
                        wave_numbers_inner[i+3] = '((c))'
                        wave_numbers_inner[i+4] = '((d))'
                        wave_numbers_inner[i+5] = '((e))'
                        wave_numbers_outer[i+5] = 'Y'
                        print_verbose("Custom Double Three Condition having 1 inner Wave in X and 5 inner wave in Y Formed")
                        pattern_matched_i5_custom = True
                        break
                    # else:
                        # print_verbose("Pattern failed, resetting lists.")
                        # wave_numbers_inner = [] # Clear the list to reset the waves
                        # wave_numbers_outer = [] # Clear the list to reset the waves
                        # break

                if not pattern_matched_i5_custom and i+5 < len(df): # Only check i + 5 < len(df) as it's sufficient to cover both >> Standard Condition >> #Condition for ZigZag
                    ## Based on Whether X is coming at  i th or  is i+2 th, Both are different Conditions
                    if not x_at_i1: 
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
                            pattern_matched_i5_zigzag = True
                            break
                    elif x_at_i1: # Special Condition where i3 > i1 (X Point), So Shift X (i1 point) to (i3 point)
                        wavec2 =  df[zigzag_column].iloc[i] #Currently X is at i, if i+2 > i then shift to i+2 to new High as X Point
                        wavea3 =  df[zigzag_column].iloc[i+1]
                        waveb3 =  df[zigzag_column].iloc[i+2]
                        wavec3 =  df[zigzag_column].iloc[i+3]
                        if (wavec2 < waveb3) and x_reference_value > waveb3: ## Checking X Point at C2 (i th Position < i+2 th Position)
                            wavec2 =  df[zigzag_column].iloc[i+2] #As X Point at i th Position Smaller than i+2 th Position, Shift the X Point (c2) as i+2 th Position
                            wavea3 =  df[zigzag_column].iloc[i+3]
                            waveb3 =  df[zigzag_column].iloc[i+4]
                            wavec3 =  df[zigzag_column].iloc[i+5]
                            if (wavec2 > waveb3) and (waveb3 > wavea3) and (wavea3 > wavec3) and [(df[zigzag_column].iloc[i-4] > wavec2) or (df[zigzag_column].iloc[i-6] > wavec2) or (df[zigzag_column].iloc[i-8] > wavec2)]: #and (x_reference_value > wavec2):## Check for x_reference_value can be i-7, i-9 , i-5, i-3 condition to confirm i+3 pattern is intact
                                print_verbose("Check for x_at_i1 Condition where i+2 > i th Position having 1 inner Wave in X and 3 inner wave in Y")
                                wave_numbers_inner[i] = '((a))'
                                wave_numbers_inner[i+1] = '((b))'
                                wave_numbers_inner[i+2] = '((c))'
                                wave_numbers_inner[i+3] = '((a))'
                                wave_numbers_inner[i+4] = '((b))'   
                                wave_numbers_inner[i+5] = '((c))'
                                wave_numbers_outer[i+5] = 'Y'
                                wave_numbers_outer[i+2] = 'X'
                                wave_numbers_outer[i] = None # As X Point moved to i+2 from ith Point, so X at i th Point made None
                                print_verbose("Check for x_at_i1 Condition where i+2 > i th Position which changed inner Wave 2 from 1 in X and 3 inner wave in Y Formed")
                                if i+7 < len(df): # To check for Impulse Elliot Wave DownTrend till 5th Wave as Y Point
                                    waved3 = df[zigzag_column].iloc[i+6] 
                                    wavee3 = df[zigzag_column].iloc[i+7] 
                                    if (waveb3 > waved3) and (wavec3 > wavee3):
                                        wave_numbers_inner[i+6] = '((d))'
                                        wave_numbers_inner[i+7] = '((e))'
                                        wave_numbers_outer[i+7] = 'Y'
                                        wave_numbers_outer[i+5] = None  # If i+5 is assigned 'Y', set i+3 to None
                                        print_verbose("Double Three Condition having x_at_i1 where it contains 2 inner Wave in X and 5 inner wave in Y Formed")
                                        break # Success — exit loop
                                break
                
                # Now, checking for the second condition >> Triangle Condition Having 5 Points
                if not pattern_matched_i5_zigzag and i+7 < len(df):
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
            
            # elif current_wave_inner == "((c2))": ## Condition for Single inner Wave in Y where Point W > Y        
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
                    if (prev_value > waveb1) and (wavea1 > wavec1): #(waveb1 > prev_value) 
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

        # # # Check if the last wave number is 'Wave 1' >> To Forecast EW 2
        # if "Wave 1" in df.loc[:df.last_valid_index(), 'Wave Number Downtrend'].values and not any(x in df.loc[:df.last_valid_index(), 'Wave Number Downtrend'].values for x in ["Wave 2.1", "Wave 2.2"]):
        if (df['Wave Number Downtrend'].iloc[-1] in ['Wave 1'] or df['Wave Number Downtrend'].iloc[df['Close'].last_valid_index()] in ['Wave 1']) and df['Wave Number Downtrend'].iloc[df['Close'].last_valid_index() - 2] != 'Wave 1':

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
        if any(df["Corrective Pattern outer numbers"].tail(3).notna() & df["Corrective Pattern outer numbers"].tail(3).str.contains('W')) or df['Corrective Pattern outer numbers'].iloc[df['Close'].last_valid_index()-2:df['Close'].last_valid_index()+1].isin(['W']).any() and \
             df['Corrective Pattern outer numbers'].iloc[df['Close'].last_valid_index()] != 'X':  # Last 3 rows and condition added: #Last 3 rows
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
            # if end_point > 0:  # Ensure there's a previous row before 'W'
            if end_point is not None and end_point  > 0:  # Ensure there's a previous row before 'W'
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
            if end_point is None: # It Means its Forming Triange Pattern as End Point at w_11           
                rows_with_w_11 = df.tail(11)[df.tail(11)["Corrective Pattern outer numbers"].str.contains('W', na=False)]  # Check for 'W' in the last 11 rows
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

# Create an empty container for the chart
chart_placeholder = st.empty()

# Function to update the chart in real-time
def update_chart(fetch_data, interval):
    # global previous_layout  # Use the global previous_layout variable
    
    while True:
        # Get the latest data from the database
        df2 = fetch_data()
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
        
        # Convert WXWXY Pattern: Two Double Three Patterns to Single Triple Three Pattern
        pattern_indices_wxyxz = df42[df42['Corrective Pattern outer numbers'].notnull()].index
        pattern_values_wxyxz = df42.loc[pattern_indices_wxyxz, 'Corrective Pattern outer numbers'].tolist()

        for i in range(len(pattern_values_wxyxz) - 4): # Step 2: Replace pattern WXWXY → WXYXZ
            sub = pattern_values_wxyxz[i:i+5]
            if sub == ['W', 'X', 'W', 'X', 'Y']: # We're looking for ['W', 'X', 'W', 'X', 'Y'] pattern
                # Get corresponding DataFrame indices
                idx_w2 = pattern_indices_wxyxz[i+2]
                idx_y = pattern_indices_wxyxz[i+4]
                # Update values
                df42.at[idx_w2, 'Corrective Pattern outer numbers'] = 'Y'
                df42.at[idx_y, 'Corrective Pattern outer numbers'] = 'Z'

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
                        print_verbose(f"Wave at index {i} is invalid for Wave 1: {wave}")
                        return False
                else:  # Odd indices should be 'Wave 2' or 'Wave 2.1', 'Wave 2.2'
                    if wave not in valid_wave_2:
                        print_verbose(f"Wave at index {i} is invalid for Wave 2: {wave}")
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
                print_verbose(f"Wave pattern in {wave_column} is invalid. Please check the sequence.")

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
        df2 = df2.tail(300) 
        df2 = df2.round(2)
        df4 = df4.round(2)
        df42 = df42.round(2)

        # Step 2: Get the Datetime of the first row of this subset
        df2_first_row = df2.head(1)
        df2_datetime = df2_first_row['Datetime'].iloc[0]

        # Step 3: Filter df4 and df42 based on the Datetime from df2
        # Select rows where the Datetime in df4 and df42 is greater than or equal to df2_first_row's Datetime
        
        # Function to handle datetime conversion only if the column is a string for CSV File, In Csv file Datetime coming as String instead of Datetime
        def convert_to_datetime_if_needed(df, column_name):
            # Check if the column is a string (it could also be an object type)
            if df[column_name].dtype == 'O':  # 'O' means Object type (string type in pandas)
                # Convert string to datetime
                df[column_name] = pd.to_datetime(df[column_name])
        
        # For CSV data, apply conversion if needed
        convert_to_datetime_if_needed(df4, 'Datetime')
        convert_to_datetime_if_needed(df42, 'Datetime')
        df4 = df4[df4['Datetime'] >= df2_datetime]
        df42 = df42[df42['Datetime'] >= df2_datetime]

        ##### Elliot Wave Viz:
        # fig = go.Figure()

        # Create subplots: 2 rows, 1 column
        fig = make_subplots(    
            rows=3, cols=1,
            shared_xaxes=True,  # Share the x-axis between plots
            vertical_spacing=0.1,  # Adjust space between plots
            row_heights=[0.8, 0.2,0.2],  # Control the relative height of each subplot
            subplot_titles=('Candlestick Chart', 'RSI Chart', 'RSI Stoch'),
            row_titles=['Price', 'RSI', 'RSI Stoch']
        )

        # # **Save the current layout state before clearing the data**
        # if previous_layout is not None:
        #     fig.update_layout(previous_layout)  # Reapply previous layout to preserve zoom
        
        # # **Clear existing data before updating**
        # fig.data = []

        # # Reapply the saved layout state (preserves zoom and layout)
        # previous_layout = fig.layout

        # # Plot the candlestick chart
        fig.add_trace(go.Candlestick(
            x=df2.index,
            open=df2['Open'],
            high=df2['High'],
            low=df2['Low'],
            close=df2['Close'],
            name='Candlestick',
            increasing=dict(line=dict(color='green')),  # Green color for upward movements
            decreasing=dict(line=dict(color='red')),    # Red color for downward movements
            hovertext=df2['Datetime'].astype(str),  # Directly passing Datetime as hover text
            hoverinfo="text+y"  # Display datetime, x and y values on hover
        ), row=1, col=1)

        # Create a second subplot for the RSI chart
        fig.add_trace(go.Scatter(
            x=df2.index,
            y=df2['RSI'],
            mode='lines',
            name='RSI',
            line=dict(color='blue'),
            showlegend=False,  # Hide legend,
            hovertext=df2['Datetime'].astype(str),  # Directly passing Datetime as hover text
            hoverinfo="text+y"  # Display datetime, x and y values on hover
        ), row=2, col=1)

        # Create a third subplot for the STOCH_K and STOCH_D Chart
        fig.add_trace(go.Scatter(
            x=df2.index,
            y=df2['STOCH_K'], #STOCHRSIk_14_14_14_3 for Pandas-TA , STOCH_K for TALIB
            mode='lines',
            name='RSI STOCH_K',
            line=dict(color='blue'),
            showlegend=False,  # Hide legend
            hovertext=df2['Datetime'].astype(str),  # Directly passing Datetime as hover text
            hoverinfo="text+y"  # Display datetime, x and y values on hover
        ), row=3, col=1)

        fig.add_trace(go.Scatter(
            x=df2.index,
            y=df2['STOCH_D'],  #STOCHRSId_14_14_14_3 for Pandas-TA , STOCH_D for TALIB
            mode='lines',
            name='RSI STOCH_D',
            line=dict(color='red'),
            showlegend=False,  # Hide legend
            hovertext=df2['Datetime'].astype(str),  # Directly passing Datetime as hover text
            hoverinfo="text+y"  # Display datetime, x and y values on hover 
        ), row=3, col=1)
        
        #SuperTrend Viz >> NOT Required
        # fig.add_trace(go.Scatter(
        #     x=df2.index,
        #     y=df2.final_upperband,
        #     mode='markers',
        #     line=dict(color='red', width=2),
        #     marker=dict(symbol='star-triangle-down', size=7, color='red'),
        #     name='Down Trend'
        # ), row=1, col=1)

        # fig.add_trace(go.Scatter(
        #     x=df2.index,
        #     y=df2.final_lowerband,
        #     mode='markers',
        #     marker=dict(symbol='star-triangle-up', size=7, color='green'),
        #     line=dict(color='green', width=2),
        #     name='Up Trend'
        # ), row=1, col=1)    
 
        # # # # Get unique numeric values (as strings) from the 'blue_wave_count' column >> Blue Wave Numbering B/w Yellow Wave in Sky Blue Color
        # numeric_wave_count = df2['blue_wave_count'].unique()
        # numeric_wave_count = [str(val) for val in numeric_wave_count if val not in ['nan']] #not-nan

        # # Loop through the numeric values and add traces
        # for wave_name in numeric_wave_count:
        #     wave_data = df2[df2['blue_wave_count'] == wave_name]
        #     # Drop rows where 'blue_wave_count' contains non-NaN or 'not-nan' values
        #     # wave_data = wave_data[~wave_data['blue_wave_count'].isin(['0'])]
            
        #     # Remove rows where wave_direction is NaN or None
        #     wave_data = wave_data.dropna(subset=['wave_direction'])
            
        #     # Prepare dynamic wave label (e.g., "(i)", "(ii)", "(iii)", etc.)
        #     wave_label = f"({wave_name})"  
        #     # Initialize variables for offset and text position
        #     offset = 0
        #     text_position = 'top center'  # Default text position
            
        #     if len(wave_data) > 0:
        #         wave_direction = wave_data['wave_direction'].iloc[0]  # Get the first row's wave direction for this wave
                
        #         # Set dynamic offset and text position based on wave direction
        #         if wave_direction == 'up':
        #             offset = 4
        #             text_position = 'top center'
        #         elif wave_direction == 'down':
        #             offset = -4
        #             text_position = 'bottom center'
            
        #     # Add trace for each wave
        #     fig.add_trace(go.Scatter(
        #         x=wave_data.index,
        #         y=wave_data['ZIGZAGv_0.01%_3'] + offset,  # Apply offset to the y-values
        #         mode='text',  # markers + text
        #         name=wave_label,
        #         text=[wave_label] * len(wave_data),  # Use dynamic wave label
        #         textfont=dict(color='skyblue'),
        #         textposition=text_position,  # Set dynamic text position
        #         showlegend=False  # Hide the trace from the legend
        #     ))

        uptrend_wave_info_3_legs = [
            ('Wave 1', '1', 'green', 'top center', 'U1_3legs',1.5),('Wave 1.1', '1.1', 'green', 'top center', 'U1_3legs',2),('Wave 2.1', '2.1', 'green', 'bottom center', 'U2.1_3legs',-1.5) , ('Wave 2.2', '2.2', 'green', 'bottom center', 'U2.2_3legs',-1.5),
            ('Wave 3.1', '3.1', 'green', 'top center', 'U3.1_3legs',1.5) , ('Wave 3.2', '3.2', 'green', 'top center', 'U3.2_3legs',1.5),  ('Wave 4.1', '4.1', 'green', 'bottom center', 'U4.1_3legs',0) , ('Wave 4.2', '4.2', 'green', 'bottom center', 'U4.2_3legs',0),
            ('Wave 5.1', '5.1', 'green', 'top center', 'U5.1_3legs',0) , ('Wave 5.2', '5.2', 'green', 'top center', 'U5.2_3legs',0),('Wave 6', '6','green', 'bottom center','U6_3legs',0),('Wave 7', '7','green', 'top center','U7_3legs',0),
            ('Wave 8', '8','green', 'bottom center','U8_3legs',0),('Wave 9', '9','green', 'top center','U9_3legs',0),('Wave a', 'a','green', 'bottom center','Ua_3legs',-2),('Wave b', 'b','green', 'top center','Ub_3legs',2),('Wave c', 'c','green', 'bottom center','Uc_3legs',-2)]

        # Loop through the uptrend wave_info list and add traces
        for wave_name, wave_label, color, text_position, trace_name, offset in uptrend_wave_info_3_legs:
            wave_data = df4[df4['Wave Number Uptrend'] == wave_name]
            
            fig.add_trace(go.Scatter(
                x=wave_data.index,
                y=wave_data['ZIGZAGv_0.01%_3'] + offset,
                mode='text',
                name=trace_name,
                text=[wave_label] * len(wave_data),  # Use the wave label (e.g., 1, 2.1, etc.)
                textfont=dict(color=color),
                textposition=[text_position if val > 0 else 'bottom center' for val in wave_data['ZIGZAGv_0.01%_3']],
                showlegend=False,  # Hide the trace from the legend
                hovertext=wave_data['Datetime'].astype(str),  # Directly passing Datetime as hover text
                hoverinfo="text+y"  # Display datetime, x and y values on hover
            ))

        uptrend_wave_info_10_legs = [
            ('Wave 1', '1', 'green', 'top center', 'U1_10legs', 3),('Wave 1.1', '1.1', 'green', 'top center', 'U1_10legs', 3),('Wave 2.1', '2.1', 'green', 'bottom center', 'U2.1_10legs', -1.5) , ('Wave 2.2', '2.2', 'green', 'bottom center', 'U2.2_10legs', -1.5),
            ('Wave 3.1', '3.1', 'green', 'top center', 'U3.1_10legs', 2) , ('Wave 3.2', '3.2', 'green', 'top center', 'U3.2_10legs', 2),  ('Wave 4.1', '4.1', 'green', 'bottom center', 'U4.1_10legs', -2) , ('Wave 4.2', '4.2', 'green', 'bottom center', 'U4.2_10legs', -2),
            ('Wave 5.1', '5.1', 'green', 'top center', 'U5.1_10legs', 2) , ('Wave 5.2', '5.2', 'green', 'top center', 'U5.2_10legs', 2),('Wave 6', '6','green', 'bottom center','U6_10legs',-1),('Wave 7', '7','green', 'top center','U7_10legs',1),
            ('Wave 8', '8','green', 'bottom center','U8_10legs',-1),('Wave 9', '9','green', 'top center','U9_10legs',1),('Wave a', 'a','green', 'bottom center','Ua_10legs',-5),('Wave b', 'b','green', 'top center','Ub_10legs',5),('Wave c', 'c','green', 'bottom center','Uc_10legs',-5)]

        # Loop through the uptrend wave_info list and add traces
        for wave_name, wave_label, color, text_position, trace_name, y_offset in uptrend_wave_info_10_legs:
            wave_data = df42[df42['Wave Number Uptrend'] == wave_name]
            
            fig.add_trace(go.Scatter(
                x=wave_data.index,
                y=wave_data['ZIGZAGv_0.01%_10'] + y_offset,  # Apply y-offset to avoid overlap
                mode='text',
                name=trace_name,
                text=[wave_label] * len(wave_data),  # Use the wave label (e.g., 1, 2.1, etc.)
                textfont=dict(color=color, size=18, family='Arial Black'),
                textposition=[text_position if val > 0 else 'bottom center' for val in wave_data['ZIGZAGv_0.01%_10']],
                showlegend=False,  # Hide the trace from the legend
                hovertext=wave_data['Datetime'].astype(str),  # Directly passing Datetime as hover text
                hoverinfo="text+y"  # Display datetime, x and y values on hover
            ))

        downtrend_wave_info_3_legs = [
            ('Wave 1', '1', 'red', 'bottom center', 'D1_3legs'),('Wave 1.1', '1.1', 'red', 'bottom center', 'D1_3legs'),('Wave 2.1', '2.1', 'red', 'top center', 'D2.1_3legs') , ('Wave 2.2', '2.2', 'red', 'top center', 'D2.2_3legs'),
            ('Wave 3.1', '3.1', 'red', 'bottom center', 'D3.1_3legs') , ('Wave 3.2', '3.2', 'red', 'bottom center', 'D3.2_3legs'),  ('Wave 4.1', '4.1', 'red', 'top center', 'D4.1_3legs') , ('Wave 4.2', '4.2', 'red', 'top center', 'D4.2_3legs'),
            ('Wave 5.1', '5.1', 'red', 'bottom center', 'D5.1_3legs') , ('Wave 5.2', '5.2', 'red', 'bottom center', 'D5.2_3legs'),('Wave 6', '6','red', 'top center','D6_3legs'),('Wave 7', '7','red', 'bottom center','D7_3legs'),
            ('Wave 8', '8','red', 'top center','D8_3legs'),('Wave 9', '9','red', 'bottom center','D9_3legs'),('Wave a', 'a','red', 'top center','Da_3legs'),('Wave b', 'b','red', 'bottom center','Db_3legs'),('Wave c', 'c','red', 'top center','Dc_3legs')]

        # Loop through the uptrend wave_info list and add traces
        for wave_name, wave_label, color, text_position, trace_name in downtrend_wave_info_3_legs:
            wave_data = df4[df4['Wave Number Downtrend'] == wave_name]
            
            fig.add_trace(go.Scatter(
                x=wave_data.index,
                y=wave_data['ZIGZAGv_0.01%_3'],
                mode='markers+text',
                name=trace_name,
                text=[wave_label] * len(wave_data),  # Use the wave label (e.g., 1, 2.1, etc.)
                textfont=dict(color=color),
                textposition=[text_position if val > 0 else 'bottom center' for val in wave_data['ZIGZAGv_0.01%_3']],
                showlegend=False,  # Hide the trace from the legend
                hovertext=wave_data['Datetime'].astype(str),  # Directly passing Datetime as hover text
                hoverinfo="text+y"  # Display datetime, x and y values on hover
            ))

        downtrend_wave_info_10_legs = [
            ('Wave 1', '1', 'red', 'bottom center', 'D1_10legs',-3),('Wave 1.1', '1.1', 'red', 'bottom center', 'D1_10legs',-3),('Wave 2.1', '2.1', 'red', 'top center', 'D2.1_10legs',3) , ('Wave 2.2', '2.2', 'red', 'top center', 'D2.2_10legs',3),
            ('Wave 3.1', '3.1', 'red', 'bottom center', 'D3.1_10legs',-2) , ('Wave 3.2', '3.2', 'red', 'bottom center', 'D3.2_10legs',-2),  ('Wave 4.1', '4.1', 'red', 'top center', 'D4.1_10legs',2) , ('Wave 4.2', '4.2', 'red', 'top center', 'D4.2_10legs',2),
            ('Wave 5.1', '5.1', 'red', 'bottom center', 'D5.1_10legs',-2) , ('Wave 5.2', '5.2', 'red', 'bottom center', 'D5.2_10legs',-2),('Wave 6', '6','red', 'top center','D6_10legs',1),('Wave 7', '7','red', 'bottom center','D7_10legs',-1),
            ('Wave 8', '8','red', 'top center','D8_10legs',1),('Wave 9', '9','red', 'bottom center','D9_10legs',-1),('Wave a', 'a','red', 'top center','Da_10legs',2),('Wave b', 'b','red', 'bottom center','Db_10legs',-2),('Wave c', 'c','red', 'top center','Dc_10legs',2)]
        # Loop through the uptrend wave_info list and add traces
        for wave_name, wave_label, color, text_position, trace_name, y_offset in downtrend_wave_info_10_legs:
            wave_data = df42[df42['Wave Number Downtrend'] == wave_name]
            
            fig.add_trace(go.Scatter(
                x=wave_data.index,
                y=wave_data['ZIGZAGv_0.01%_10'] + y_offset,  # Apply y-offset to avoid overlap
                mode='text',
                name=trace_name,
                text=[wave_label] * len(wave_data),  # Use the wave label (e.g., 1, 2.1, etc.)
                textfont=dict(color=color, size=18, family='Arial Black'),
                textposition=[text_position if val > 0 else 'bottom center' for val in wave_data['ZIGZAGv_0.01%_10']],
                showlegend=False,  # Hide the trace from the legend
                hovertext=wave_data['Datetime'].astype(str),  # Directly passing Datetime as hover text
                hoverinfo="text+y"  # Display datetime, x and y values on hover
            ))

        # # Triangle UpTrend List of wave numbers and their corresponding labels
        wave_infot_u = [('A', 'A', 'bottom center', -2), ('B', 'B', 'top center',2),
                    ('C', 'C', 'bottom center',-2), ('D', 'D', 'top center',2), ('E', 'E', 'bottom center',-2), ('Up', 'T-Up', 'top center',0)]
        
        # Loop through the wave_info list
        for wave_name, wave_label, text_position, offset in wave_infot_u:
            # Filter the DataFrame based on the wave number
            wave_data = df4[df4['Wave Number Uptrend'] == wave_name]

            # Add the trace to the figure
            fig.add_trace(go.Scatter(
                x=wave_data.index,
                y=wave_data['ZIGZAGv_0.01%_3'] + offset,
                mode='text', #markers+text
                name=wave_name,  # Use the wave number as the name
                text=[wave_label] * len(wave_data),  # Use the wave label (A, B, C, D, etc.)
                textfont=dict(color='green'),  # Set the text color
                textposition=text_position,  # Position the text
                showlegend=False,  # Hide the trace from the legend
                hovertext=wave_data['Datetime'].astype(str),  # Directly passing Datetime as hover text
                hoverinfo="text+y"  # Display datetime, x and y values on hover
            ))

        # # Triangle DownTrend List of wave numbers and their corresponding labels
        wave_infot_d = [('A', 'A', 'top center', 0), ('B', 'B', 'bottom center', 0),
                    ('C', 'C', 'top center', 0), ('D', 'D', 'bottom center', 0), ('E', 'E', 'top center', 0),('Down', 'T-Down', 'bottom center', 0)]

        # Loop through the wave_info list
        for wave_name, wave_label, text_position,offset in wave_infot_d:
            # Filter the DataFrame based on the wave number
            wave_data = df4[df4['Wave Number Downtrend'] == wave_name]

            # Add the trace to the figure
            fig.add_trace(go.Scatter(
                x=wave_data.index,
                y=wave_data['ZIGZAGv_0.01%_3'] + offset,
                mode='text', #markers+text
                name=wave_name,  # Use the wave number as the name
                text=[wave_label] * len(wave_data),  # Use the wave label (A, B, C, D, etc.)
                textfont=dict(color='red'),  # Set the text color
                textposition=text_position,  # Position the text
                showlegend=False,  # Hide the trace from the legend
                hovertext=wave_data['Datetime'].astype(str),  # Directly passing Datetime as hover text
                hoverinfo="text+y"  # Display datetime, x and y values on hover
            ))

        # # Swing High Low (Uptrend) List of wave numbers and their corresponding labels
        wave_infosh_u = [('SH', 'SH', 'top center',1), ('SL', 'SL', 'bottom center' , -1)]
        # Loop through the wave_info list
        for wave_name, wave_label, text_position,offset in wave_infosh_u:
            # Filter the DataFrame based on the wave number
            wave_data = df4[df4['Wave Number Swing High Low UpTrend'] == wave_name]

            # Add the trace to the figure
            fig.add_trace(go.Scatter(
                x=wave_data.index,
                y=wave_data['ZIGZAGv_0.01%_3'] + offset,
                mode='text',
                name=wave_name,  # Use the wave number as the name
                text=[wave_label] * len(wave_data),  # Use the wave label (A, B, C, D, etc.)
                textfont=dict(color='green'),  # Set the text color
                textposition=text_position,  # Position the text
                showlegend=False,  # Hide the trace from the legend
                hovertext=wave_data['Datetime'].astype(str),  # Directly passing Datetime as hover text
                hoverinfo="text+y"  # Display datetime, x and y values on hover
            ))

        # # Swing High Low (Uptrend) List of wave numbers and their corresponding labels
        wave_infosh_d = [('SH', 'SH', 'top center',1), ('SL', 'SL', 'bottom center', -1.5)]
        # Loop through the wave_info list
        for wave_name, wave_label, text_position, offset in wave_infosh_d:
            # Filter the DataFrame based on the wave number
            wave_data = df4[df4['Wave Number Swing High Low DownTrend'] == wave_name]

            # Add the trace to the figure
            fig.add_trace(go.Scatter(
                x=wave_data.index,
                y=wave_data['ZIGZAGv_0.01%_3'] + offset,
                mode='text',
                name=wave_name,  # Use the wave number as the name
                text=[wave_label] * len(wave_data),  # Use the wave label (A, B, C, D, etc.)
                textfont=dict(color='red'),  # Set the text color
                textposition=text_position,  # Position the text
                showlegend=False,  # Hide the trace from the legend
                hovertext=wave_data['Datetime'].astype(str),  # Directly passing Datetime as hover text
                hoverinfo="text+y"  # Display datetime, x and y values on hover
            ))

            # # Swing High Low (Uptrend) List of wave numbers and their corresponding labels
            wave_infosh_u_10_legs = [('SH', 'SH', 'top center',3), ('SL', 'SL', 'bottom center',-3)]
            # Loop through the wave_info list
            for wave_name, wave_label, text_position, offset in wave_infosh_u_10_legs:
                # Filter the DataFrame based on the wave number
                wave_data = df42[df42['Wave Number Swing High Low UpTrend'] == wave_name]

                # Add the trace to the figure
                fig.add_trace(go.Scatter(
                    x=wave_data.index,
                    y=wave_data['ZIGZAGv_0.01%_10'] + offset,
                    mode='text',
                    name=wave_name,  # Use the wave number as the name
                    text=[wave_label] * len(wave_data),  # Use the wave label (A, B, C, D, etc.)
                    textfont=dict(color='green', size=18, family='Arial Black'),  # Set the text color
                    textposition=text_position,  # Position the text
                    showlegend=False,  # Hide the trace from the legend
                    hovertext=wave_data['Datetime'].astype(str),  # Directly passing Datetime as hover text
                    hoverinfo="text+y"  # Display datetime, x and y values on hover
                ))

            # # Swing High Low (Uptrend) List of wave numbers and their corresponding labels
            wave_infosh_d_10_legs = [('SH', 'SH', 'top center',4), ('SL', 'SL', 'bottom center', -3)]
            # Loop through the wave_info list
            for wave_name, wave_label, text_position, offset in wave_infosh_d_10_legs:
                # Filter the DataFrame based on the wave number
                wave_data = df42[df42['Wave Number Swing High Low DownTrend'] == wave_name]

                # Add the trace to the figure
                fig.add_trace(go.Scatter(
                    x=wave_data.index,
                    y=wave_data['ZIGZAGv_0.01%_10'] + offset,
                    mode='text',
                    name=wave_name,  # Use the wave number as the name
                    text=[wave_label] * len(wave_data),  # Use the wave label (A, B, C, D, etc.)
                    textfont=dict(color='red', size=18, family='Arial Black'),  # Set the text color
                    textposition=text_position,  # Position the text
                    showlegend=False,  # Hide the trace from the legend
                    hovertext=wave_data['Datetime'].astype(str),  # Directly passing Datetime as hover text
                    hoverinfo="text+y"  # Display datetime, x and y values on hover
                ))

        # # # Zigzag, Flat Corrective Pattern List of wave numbers and their corresponding labels >> Commented due to Conjestion in Chart 
        # wave_info_zigzag_flat_inner = [('((i))', ' ', 'bottom center'), ('((ii))', '((ii))', 'top center'),('((iii))', '((iii))', 'bottom center'),('((iv))', '((iv))', 'top center'),('((v))', '((v))', 'bottom center'),
        #                         ('((a))', '((a))', 'top center'),('((b))', '((b))', 'bottom center'),('((c))', '((c))', 'top center'), ('((w))', '((w))', 'bottom center'),('((x))', '((x))', 'top center'),('((y))', '((y))', 'bottom center')]

        # # Loop through the wave_info list
        # for wave_name, wave_label, text_position in wave_info_zigzag_flat_inner:
        #     # Filter the DataFrame based on the wave number
        #     wave_data = df4[df4['Corrective Pattern inner numbers'] == wave_name]

        #     # Add the trace to the figure
        #     fig.add_trace(go.Scatter(
        #         x=wave_data.index,
        #         y=wave_data['ZIGZAGv_0.01%_3'],
        #         mode='text',
        #         name=wave_name,  # Use the wave number as the name
        #         text=[wave_label] * len(wave_data),  # Use the wave label (A, B, C, D, etc.)
        #         textfont=dict(color='skyblue'),  # Set the text color
        #         textposition=text_position,  # Position the text
        #         showlegend=False,  # Hide the trace from the legend
        #         hovertext=wave_data['Datetime'].astype(str),  # Directly passing Datetime as hover text
        #         hoverinfo="text+y"  # Display datetime, x and y values on hover
        #     ))
        # # Zigzag, Flat Corrective Pattern List of wave numbers and their corresponding labels
        wave_info_zigzag_flat_outer = [('A', 'A', 'bottom center',-1), ('B', 'B', 'top center',1),('C', 'C', 'bottom center',-1)]

        # Loop through the wave_info list
        for wave_name, wave_label, text_position,offset in wave_info_zigzag_flat_outer:
            # Filter the DataFrame based on the wave number
            wave_data = df4[df4['Corrective Pattern outer numbers'] == wave_name]

            # Add the trace to the figure
            fig.add_trace(go.Scatter(
                x=wave_data.index,
                y=wave_data['ZIGZAGv_0.01%_3'] + offset,
                mode='text',
                name=wave_name,  # Use the wave number as the name
                text=[wave_label] * len(wave_data),  # Use the wave label (A, B, C, D, etc.)
                # textfont=dict(color='red'),  # Set the text color
                textfont=dict(color='skyblue', size=10, family='Arial Black'),
                textposition=text_position,  # Position the text
                showlegend=False,  # Hide the trace from the legend
                hovertext=wave_data['Datetime'].astype(str),  # Directly passing Datetime as hover text
                hoverinfo="text+y"  # Display datetime, x and y values on hover
            ))

        # # Double Three, Triple Three Inner Waves Corrective Pattern List of wave numbers and their corresponding labels
        wave_info_double_triple_three_inner = [('((a))', '((a))', 'top center'),('((b))', '((b))', 'bottom center'),('((c))', '((c))', 'top center'),('((d))', '((d))', 'top center'),('((e))', '((e))', 'bottom center'), ('((w))', '((w))', 'bottom center'),('((x))', '((x))', 'top center'),('((y))', '((y))', 'bottom center')]

        # Loop through the wave_info list
        for wave_name, wave_label, text_position in wave_info_double_triple_three_inner:
            # Filter the DataFrame based on the wave number
            wave_data = df42[df42['Corrective Pattern inner numbers'] == wave_name]

            # Add the trace to the figure
            fig.add_trace(go.Scatter(
                x=wave_data.index,
                y=wave_data['ZIGZAGv_0.01%_10'],
                mode='markers+text',
                name=wave_name,  # Use the wave number as the name
                text=[wave_label] * len(wave_data),  # Use the wave label (A, B, C, D, etc.)
                textfont=dict(color='skyblue'),  # Set the text color
                textposition=text_position,  # Position the text
                showlegend=False,  # Hide the trace from the legend
                hovertext=wave_data['Datetime'].astype(str),  # Directly passing Datetime as hover text
                hoverinfo="text+y"  # Display datetime, x and y values on hover
            ))

        # # Double Three, Triple Three Outer Waves Corrective Pattern List of wave numbers and their corresponding labels
        wave_info_double_triple_three_outer = [('W', 'W', 'bottom center',-4), ('X', 'X', 'top center',6),('Y', 'Y', 'bottom center',-4),('Z', 'Z', 'bottom center',-4)]

        # Loop through the wave_info list
        for wave_name, wave_label, text_position, offset in wave_info_double_triple_three_outer:
            # Filter the DataFrame based on the wave number
            wave_data = df42[df42['Corrective Pattern outer numbers'] == wave_name]

            # Add the trace to the figure
            fig.add_trace(go.Scatter(
                x=wave_data.index,
                y=wave_data['ZIGZAGv_0.01%_10'] + offset,
                mode='text',
                name=wave_name,  # Use the wave number as the name
                text=[wave_label] * len(wave_data),  # Use the wave label (A, B, C, D, etc.)
                textfont=dict(color='yellow',size=18,family='Arial Black'),  # Set the text color
                textposition=text_position,  # Position the text
                showlegend=False,  # Hide the trace from the legend
                hovertext=wave_data['Datetime'].astype(str),  # Directly passing Datetime as hover text
                hoverinfo="text+y"  # Display datetime, x and y values on hover
            ))

        # RSI Points with corresponding markers (symbols) and colors
        rsi_points = [
            ('r-b', 'RSI Over Bought only', 'top center', 'circle', 'green'),
            ('s-b', 'Stochastic Signal Over Bought only', 'top center', 'cross', 'green'),
            ('r-s', 'RSI Over Sold only', 'bottom center', 'diamond', 'red'),
            ('s-s', 'Stochastic Signal Over Sold only', 'bottom center', 'star', 'red'),
            ('b-b', 'Over Bought', 'top center', 'x', 'green'),
            ('b-s', 'Over Sold', 'bottom center', 'square', 'red'),
            ('rb-ss', 'RSI OB Stochastic OS', 'bottom center', 'triangle-up', 'blue'),
            ('rs-sb', 'RSI OS Stochastic OB', 'top center', 'triangle-down', 'yellow')
        ]

        # Loop through the rsi_points list
        for label, rsi_stoc_point, text_position, symbol, color in rsi_points:
            # Filter the DataFrame based on the wave number
            wave_data = df2[df2['Both Signals'] == rsi_stoc_point]

            # Add the trace to the figure
            fig.add_trace(go.Scatter(
                x=wave_data.index,
                y=wave_data['Close'],
                mode='markers',  # Only use markers, no text
                marker=dict(
                    symbol=symbol,  # Set the symbol
                    size=10,  # Adjust the marker size as needed
                    color=color  # Use the color from the tuple
                ),
                hovertext=[label] * len(wave_data),  # Show the label when hovering
                hoverinfo='text',  # Only show the hovertext (label)
                showlegend=False  # Hide the trace from the legend
            ))

        # Filter non-NaN values in ZIGZAGv_0.01%_3 for plotting
        valid_zigzag_data = df2[df2['ZIGZAGv_0.01%_3'].notna()]

        # Adding Zigzag line trace with dots
        fig.add_trace(go.Scatter(
            x=valid_zigzag_data.index,  # Non-NaN indices
            y=valid_zigzag_data['ZIGZAGv_0.01%_3'],  # Non-NaN Zigzag values
            mode='markers+lines',  # Both markers (dots) and lines
            line=dict(color='skyblue', width=1),  # Customize the line color and width #rgba(0, 0, 255, 0.9)
            marker=dict(color='blue', size=2),  # Customize the dots color and size
            name='0.01% DEV 3 Legs',
            hovertext=valid_zigzag_data['Datetime'].astype(str),  # Directly passing Datetime as hover text
            hoverinfo="text+y"  # Display datetime, x and y values on hover
        ))

        # Filter non-NaN values in ZIGZAGv_0.01%_3 for plotting
        valid_zigzag_data = df2[df2['ZIGZAGv_0.01%_10'].notna()]

        # Adding Zigzag line trace with dots
        fig.add_trace(go.Scatter(
            x=valid_zigzag_data.index,  # Non-NaN indices
            y=valid_zigzag_data['ZIGZAGv_0.01%_10'],  # Non-NaN Zigzag values
            mode='markers+lines',  # Both markers (dots) and lines
            line=dict(color='yellow', width=1),  # Customize the line color and width
            marker=dict(color='red', size=6),  # Customize the dots color and size
            name='0.01% DEV 10 Legs',
            hovertext=valid_zigzag_data['Datetime'].astype(str),  # Directly passing Datetime as hover text
            hoverinfo="text+y"  # Display datetime, x and y values on hover
        ))

        # Wave-2 Range (First Range) Forecasting Range and for Wave-4 this is (Second Range)
        if '38_4 range' in df42.columns and not any(col in df42.columns for col in ['161_8 range', '261_8 range']):
            # Filter non-NaN values in ZIGZAGv_0.01%_3 for plotting
            fib_38_4_range = df42[df42['38_4 range'].notna()]
            fig.add_trace(go.Scatter(
                x=fib_38_4_range.index,  # Non-NaN indices
                y=fib_38_4_range['38_4 range'],  # Non-NaN Zigzag values
                mode='lines',  # Both markers (dots) and lines
                line=dict(color='#FFFF99', width=1),  # Faint yellow line color
                marker=dict(color='#FFFF99'),  # Faint yellow dots color and size
                name='38.4% Range',
                showlegend=False,
                hoverinfo='x+y'  # Only show x and y values on hover
            ))
            
            # Get the midpoint index
            mid_index = len(fib_38_4_range) // 3
            # Determine the text to display based on the presence of the '85_4 range' column
            if '85_4 range' in df42.columns:
                text = [""] * mid_index + ["EW-2 38.4%"] + [""] * (len(fib_38_4_range) - mid_index - 1)
                textposition = "top center"
            else:  # If '85_4 range' is not in df42.columns
                text = [""] * mid_index + ["EW-4 38.4%"] + [""] * (len(fib_38_4_range) - mid_index - 1)
                textposition = "top center"
            fig.add_trace(go.Scatter(
                x=fib_38_4_range.index,
                y=fib_38_4_range['38_4 range'],
                mode='lines+text',  # Enable text mode
                text=text,  # Use the text list determined above
                textposition=textposition,  # Position above the line
                line=dict(color='yellow', width=1),
                marker=dict(color='yellow'),
                textfont=dict(size=10, color='yellow'),
                showlegend=False,
                hoverinfo='x+y'  # Only show x and y values on hover
            ))

        if '85_4 range' in df42.columns and not any(col in df42.columns for col in ['161_8 range', '261_8 range','14_6 range']): #Wave-3 Range column should not exist
            # Filter non-NaN values in ZIGZAGv_0.01%_3 for plotting
            fib_85_4_range = df42[df42['85_4 range'].notna()]
            fig.add_trace(go.Scatter(
                x=fib_85_4_range.index,  # Non-NaN indices
                y=fib_85_4_range['85_4 range'],  # Non-NaN Zigzag values
                mode='lines',  # Both markers (dots) and lines
                line=dict(color='#FFFF99', width=1),  # Faint yellow line color
                marker=dict(color='#FFFF99'),  # Faint yellow dots color and size
                name='85.4% Range',
                showlegend=False,
                hoverinfo='x+y'  # Only show x and y values on hover
            ))
            # Get the midpoint index
            mid_index = len(fib_85_4_range) // 3
            fig.add_trace(go.Scatter(
                x=fib_85_4_range.index,
                y=fib_85_4_range['85_4 range'],
                mode='lines+text',  # Enable text mode
                text=[""] * mid_index + ["EW-2 85.4%"] + [""] * (len(fib_85_4_range) - mid_index - 1),
                textposition="top center",  # Position above the line
                line=dict(color='yellow', width=1),
                marker=dict(color='yellow'),
                textfont=dict(size=10, color='yellow'),
                showlegend=False,
                hoverinfo='x+y'  # Only show x and y values on hover
            ))

        #Wave 3 Forecasting Range
        if '161_8 range' in df42.columns:
            # Filter non-NaN values in ZIGZAGv_0.01%_3 for plotting
            fib_161_8_range = df42[df42['161_8 range'].notna()]
            # Adding Zigzag line trace with dots
            fig.add_trace(go.Scatter(
                x=fib_161_8_range.index,  # Non-NaN indices
                y=fib_161_8_range['161_8 range'],  # Non-NaN Zigzag values
                mode='lines',  # +markers Both markers (dots) and lines
                line=dict(color='yellow', width=1),  # Customize the line color and width
                marker=dict(color='yellow'),  # Customize the dots color and size
                name='161.8% Range',
                showlegend=False
            ))
            # Get the midpoint index
            mid_index = len(fib_161_8_range) // 3
            fig.add_trace(go.Scatter(
                x=fib_161_8_range.index,
                y=fib_161_8_range['161_8 range'],
                mode='lines+text',  # Enable text mode
                text=[""] * mid_index + ["EW-3 161.8%"] + [""] * (len(fib_161_8_range) - mid_index - 1),
                textposition="top center",  # Position above the line
                line=dict(color='yellow', width=1),
                marker=dict(color='yellow'),
                textfont=dict(size=10, color='yellow'),
                showlegend=False,
                hoverinfo='x+y'  # Only show x and y values on hover
            ))

        if '261_8 range' in df42.columns:
            # Filter non-NaN values in ZIGZAGv_0.01%_3 for plotting
            fib_261_8_range = df42[df42['261_8 range'].notna()]
            fig.add_trace(go.Scatter(
                x=fib_261_8_range.index,  # Non-NaN indices
                y=fib_261_8_range['261_8 range'],  # Non-NaN Zigzag values
                mode='lines',  # Both markers (dots) and lines
                line=dict(color='#FFFF99', width=1),  # Faint yellow line color
                marker=dict(color='#FFFF99'),  # Faint yellow dots color and size
                name='261.8% Range',
                showlegend=False,
                hoverinfo='x+y'  # Only show x and y values on hover
            ))

            # Get the midpoint index
            mid_index = len(fib_261_8_range) // 3
            fig.add_trace(go.Scatter(
                x=fib_261_8_range.index,
                y=fib_261_8_range['261_8 range'],
                mode='lines+text',  # Enable text mode
                text=[""] * mid_index + ["EW-3 261.8%"] + [""] * (len(fib_261_8_range) - mid_index - 1),
                textposition="bottom center",  # Position above the line
                line=dict(color='yellow', width=1),
                marker=dict(color='yellow'),
                textfont=dict(size=10, color='yellow'),
                showlegend=False,
                hoverinfo='x+y'  # Only show x and y values on hover
            ))

        # Wave-4 Range Forecasting Range
        if '14_6 range' in df42.columns and not any(col in df42.columns for col in ['161_8 range', '261_8 range']):
            # Filter non-NaN values in ZIGZAGv_0.01%_3 for plotting
            fib_14_6_range = df42[df42['14_6 range'].notna()]
            fig.add_trace(go.Scatter(
                x=fib_14_6_range.index,  # Non-NaN indices
                y=fib_14_6_range['14_6 range'],  # Non-NaN Zigzag values
                mode='lines',  # Both markers (dots) and lines
                line=dict(color='#FFFF99', width=1),  # Faint yellow line color
                marker=dict(color='#FFFF99'),  # Faint yellow dots color and size
                name='14.6% Range',
                showlegend=False,
                hoverinfo='x+y'  # Only show x and y values on hover
            ))
            # Get the midpoint index
            mid_index = len(fib_14_6_range) // 3
            fig.add_trace(go.Scatter(
                x=fib_14_6_range.index,
                y=fib_14_6_range['14_6 range'],
                mode='lines+text',  # Enable text mode
                text=[""] * mid_index + ["EW-4 14.6%"] + [""] * (len(fib_14_6_range) - mid_index - 1),
                textposition="top center",  # Position above the line
                line=dict(color='yellow', width=1),
                marker=dict(color='yellow'),
                textfont=dict(size=10, color='yellow'),
                showlegend=False,
                hoverinfo='x+y'  # Only show x and y values on hover
            ))
        
        if any(col in df42.columns for col in ['14_6 range','161_8 range']):
            # Fib 100% Range
            fib_100_range = df42[df42['100 range'].notna()]
            fig.add_trace(go.Scatter(
                x=fib_100_range.index,  # Non-NaN indices
                y=fib_100_range['100 range'],  # Non-NaN Zigzag values
                mode='lines',  # Both markers (dots) and lines
                line=dict(color='#FFFF99', width=1),  # Faint yellow line color
                marker=dict(color='#FFFF99'),  # Faint yellow dots color and size
                name='100% Range',  
                showlegend=False,
                hoverinfo='x+y'  # Only show x and y values on hover
            ))
            # Get the midpoint index
            mid_index = len(fib_100_range) // 3
            text = [""] * mid_index + ["100%"] + [""] * (len(fib_100_range) - mid_index - 1)
            if '161_8 range' in df42.columns:  # Check if the '161_8' column is present in df2
                text = [""] * mid_index + ["EW-3 100%"] + [""] * (len(fib_100_range) - mid_index - 1)
            elif '14_6 range' in df42.columns:
                text = [""] * mid_index + ["EW-4 100%"] + [""] * (len(fib_100_range) - mid_index - 1)
            fig.add_trace(go.Scatter(
                x=fib_100_range.index,
                y=fib_100_range['100 range'],
                mode='lines+text',  # Enable text mode
                text=text, #[""] * mid_index + ["100% Fib"] + [""] * (len(fib_100_range) - mid_index - 1),
                textposition="top center",  # Position above the line
                line=dict(color='yellow', width=1),
                marker=dict(color='yellow'),
                textfont=dict(size=10, color='yellow'),
                showlegend=False,
                hoverinfo='x+y'  # Only show x and y values on hover
            ))


        # if '38_4 range' in df42.columns and not any(col in df42.columns for col in ['161_8 range', '261_8 range']): #Wave-3 Range column should not exist
        #     # Filter non-NaN values in ZIGZAGv_0.01%_3 for plotting
        #     fib_38_2_range = df42[df42['38_4 range'].notna()]
        #     fig.add_trace(go.Scatter(
        #         x=fib_38_2_range.index,  # Non-NaN indices
        #         y=fib_38_2_range['38_4 range'],  # Non-NaN Zigzag values
        #         mode='lines',  # Both markers (dots) and lines
        #         line=dict(color='#FFFF99'),  # Faint yellow line color
        #         marker=dict(color='#FFFF99'),  # Faint yellow dots color and size
        #         name='38.2% Range',
        #         showlegend=False
        #     ))
        #     # Get the midpoint index
        #     mid_index = len(fib_38_2_range) // 2
        #     fig.add_trace(go.Scatter(
        #         x=fib_38_2_range.index,
        #         y=fib_38_2_range['38_4 range'],
        #         mode='lines+text',  # Enable text mode
        #         text=[""] * mid_index + ["EW-4 38_2 range"] + [""] * (len(fib_38_2_range) - mid_index - 1),
        #         textposition="top center",  # Position above the line
        #         line=dict(color='blue'),
        #         marker=dict(color='blue'),
        #         showlegend=False
        #     ))


        # To Get correct Waves from 1 to 5, Eliminate Waves 1,2, coming repeatedly

        # """Without Connecting Line or Waves"""
        #Create pairs of consecutive waves
        # wave_pairs = [('Wave 1', 'Wave 2'), ('Wave 2', 'Wave 3'), ('Wave 3', 'Wave 4'), ('Wave 4', 'Wave 5')]

        # Loop through each pair and connect the points
        # for wave1_name, wave2_name in wave_pairs:
        #     # Get the data for Wave 1 and Wave 2
        #     wave1 = df4[df4['Wave Number Uptrend'] == wave1_name]
        #     wave2 = df4[df4['Wave Number Uptrend'] == wave2_name]

        #     # Check if both waves exist and plot the line connecting the points
        #     if not wave1.empty and not wave2.empty:
        #         # Ensure the number of points matches between wave1 and wave2
        #         if len(wave1) == len(wave2):
        #             for i in range(len(wave1)):
        #                 wave1_datetime = wave1.iloc[i]['Datetime']
        #                 wave1_value = wave1.iloc[i]['ZIGZAGv_0.01%_3']

        #                 wave2_datetime = wave2.iloc[i]['Datetime']
        #                 wave2_value = wave2.iloc[i]['ZIGZAGv_0.01%_3']

        #                 # Plot a line connecting each corresponding point of Wave 1 and Wave 2
        #                 fig.add_trace(go.Scatter(
        #                     x=[wave1_datetime, wave2_datetime],
        #                     y=[wave1_value, wave2_value],
        #                     mode='lines',
        #                     line=dict(color='blue', width=2),
        #                     showlegend=False  # Hide the line from the legend
        #                 ))
        #         else:
        #             print_verbose(f"The number of points in {wave1_name} and {wave2_name} do not match!")

        # # Loop through each pair and connect the points
        # for wave1_name, wave2_name in wave_pairs:
        #     # Get the data for Wave 1 and Wave 2
        #     wave1 = df4[df4['Wave Number Uptrend'] == wave1_name]
        #     wave2 = df4[df4['Wave Number Uptrend'] == wave2_name]

        #     # Check if both waves exist
        #     if not wave1.empty and not wave2.empty:
        #         # Find the minimum length between the two waves
        #         min_len = min(len(wave1), len(wave2))

        #         # Plot the line connecting the points for the common range (minimum length)
        #         for i in range(min_len):
        #             wave1_datetime = wave1.iloc[i]['Datetime']
        #             wave1_value = wave1.iloc[i]['ZIGZAGv_0.01%_3']

        #             wave2_datetime = wave2.iloc[i]['Datetime']
        #             wave2_value = wave2.iloc[i]['ZIGZAGv_0.01%_3']

        #             # Plot a line connecting each corresponding point of Wave 1 and Wave 2
        #             fig.add_trace(go.Scatter(
        #                 x=[wave1_datetime, wave2_datetime],
        #                 y=[wave1_value, wave2_value],
        #                 mode='lines',
        #                 line=dict(color='blue', width=2),
        #                 showlegend=False  # Hide the line from the legend
        #             ))
        #     else:
        #         print_verbose(f"One of the waves {wave1_name} or {wave2_name} does not have data!")

        # Set up layout
        fig.update_layout(
            title=f"EW Chart {interval}",
            xaxis_title="Date",
            xaxis=dict(
                rangeslider=dict(
                    visible=False  # Set to True to make the range slider visible
                ),
                type='category',  # Treat as categorical data to remove gaps
                tickangle=45
                # tickvals=df2.index[::24]  # Show every 24th timestamp (adjustable)
                # showgrid=False  # Disable grid lines for x-axis
            ),
            yaxis=dict(
                autorange=True,  # Enable dynamic Y-axis range adjustment
                fixedrange=False,  # Allow zooming on the y-axis
                showgrid=True,
                tickformat=".2f"  # Forces full number display with two decimal points
            ),
            # showgrid=False,  # Disable grid lines for y-axis
            yaxis_title="Price",
            template="plotly_dark",
            showlegend=True,
            legend=dict(
                orientation='h',  # Horizontal legend
                yanchor='top',
                y=1.1,  # Position legend slightly above the plot
                xanchor='left',
                x=0.65,  # Center the legend horizontally
                font=dict(
                    color="blue"  # Change the legend text color here
                )
            ),
            xaxis2=dict(title='Date', type='category'),
            yaxis2=dict(
                title='RSI',
                range=[0, 100],
                showgrid=True
            ),
            xaxis3=dict(title='Datetime', type='category',tickvals=df2['Datetime'][::100]),#tickvals=df2.index[::24]
            yaxis3=dict(
                title='RSI Stochastic',
                range=[0, 100],  # Typically between 0 and 100
                showgrid=True
            ),
            # hovermode='x unified',  # Enables crosshair behavior across both subplots
            # Set chart width and height
            # width=2000,  # Set chart width
            height=900  # Set chart height
        )

        # Display the updated chart
        # chart_placeholder.plotly_chart(fig)
        # Use a unique key to avoid StreamlitDuplicateElementId error
        chart_placeholder.plotly_chart(fig, key=f"chart_{int(time.time())}")
        # pio.write_html(fig, file='C:\\Users\\HP\\Downloads\\wave1_wave_1_1_till_fourth_sequence.html', auto_open=True)

        if interval == "1min":
            time.sleep(60)  # Sleep for 60 seconds before the next update
        elif interval == "5min":
            time.sleep(180)  # Sleep for 60 seconds before the next update
        elif interval == "10min":
            time.sleep(360)  # Sleep for 60 seconds before the next update
        elif interval == "15min":
            time.sleep(720)  # Sleep for 60 seconds before the next update
        elif interval == "30min":
            time.sleep(900)  # Sleep for 300 seconds before the next update
        elif interval == "1h":
            time.sleep(1800)  # Sleep for 600 seconds before the next update