from datetime import datetime
import pytz
import pandas as pd
from schwabdev import Client

class MarketDataHelper:
    def __init__(self, api_key, app_secret, callback_url):
        self.client = Client(api_key, app_secret, callback_url, verbose=True)
        self.cst = pytz.timezone('America/Chicago')

    def convert_to_central_time(self, timestamp):
        """Convert UTC timestamp to Central Time (CST/CDT)."""
        utc_dt = datetime.utcfromtimestamp(timestamp / 1000).replace(tzinfo=pytz.utc)
        return utc_dt.astimezone(self.cst)

    def fetch_price_history(self, symbol, start_date_str, frequencyType, frequency, needExtendedHoursData,end_date_str=None,periodType=None, period=None):
        """
        Fetches market price data for a given symbol, date range, and interval in CST.

        :param symbol: String representing the stock/futures symbol (e.g., "/ESH25")
        :param start_date_str: String date in format 'YYYY-MM-DD' for the start date
        :param end_date_str: String date in format 'YYYY-MM-DD' for the end date (optional)
        :param time_interval: Time interval for fetching data (e.g., 'minute', '5minute', etc.)
        :return: Pandas DataFrame with OHLCV data and Datetime index
        """
        try:
            # Convert start date string to datetime and localize to CST
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            start_date_cst = self.cst.localize(start_date)

            # If no end date is provided, use today's date
            if end_date_str is None:
                end_date = datetime.now(self.cst)
                end_date_cst = end_date.replace(hour=23, minute=59)  # Set end time to the end of today
            else:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
                end_date_cst = self.cst.localize(end_date)

            # Convert start and end times to UTC
            start_time_utc = start_date_cst.astimezone(pytz.utc)
            end_time_utc = end_date_cst.astimezone(pytz.utc)

            # Fetch price history from API
            # data = self.client.price_history(
            #     symbol,  # Use provided symbol
            #     periodType, period, #"day",   # Can be adjusted based on needs
            #     needExtendedHoursData,
            #     frequencyType = frequencyType, #="minute"
            #     frequency = frequency, #="1" # Default to 1 minute, modify this based on `time_interval`
            #     startDate=start_time_utc,
            #     endDate=end_time_utc
            #     # needExtendedHoursData=False
            # ).json()

            data = self.client.price_history(
                symbol,  # Use provided symbol
                periodType, period,  # periodType and period as positional arguments
                needExtendedHoursData= needExtendedHoursData,
                frequencyType=frequencyType,  # Pass frequencyType as a keyword argument
                frequency=frequency,          # Pass frequency as a keyword argument
                startDate=start_time_utc,
                endDate=end_time_utc
            ).json()

            if 'candles' not in data:
                raise ValueError(f"No data available for {symbol} between {start_date_str} and {end_date_str}")

            # Convert timestamps to CST
            for candle in data['candles']:
                candle['datetime'] = self.convert_to_central_time(candle['datetime'])

            # Normalize JSON data into DataFrame
            df = pd.json_normalize(data['candles'])
            df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume', 'datetime': 'Datetime'}, inplace=True)

            # Reorder columns with Datetime first
            df = df[['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume']]
            df.set_index('Datetime', inplace=True)

            return df

        except Exception as e:
            print(f"Error fetching data for {symbol} between {start_date_str} and {end_date_str}: {e}")
            return None
