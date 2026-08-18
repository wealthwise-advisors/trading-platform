
from datetime import datetime
import pytz
import pandas as pd
from schwabdev import Client
import logging


logging.basicConfig(filename="backend.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class MarketDataHelper:
    def __init__(self, api_key, app_secret, callback_url):
        self.client = Client(api_key, app_secret, callback_url, verbose=True)
        self.cst = pytz.timezone('America/Chicago')

    def convert_to_central_time(self, timestamp):
        """Convert UTC timestamp to Central Time (CST/CDT)."""
        utc_dt = datetime.utcfromtimestamp(timestamp / 1000).replace(tzinfo=pytz.utc)
        return utc_dt.astimezone(self.cst)

    def fetch_price_history(self, symbol, date_str, frequency=1):
        """
        Fetches market price data for a given symbol and date in CST.

        :param symbol: String representing the stock/futures symbol (e.g., "/ESH25")
        :param date_str: String date in format 'YYYY-MM-DD'
        :return: Pandas DataFrame with OHLCV data and Datetime index
        """
        try:
            # Convert date string to datetime and localize to CST
            specific_date = datetime.strptime(date_str, "%Y-%m-%d")
            specific_date_cst = self.cst.localize(specific_date)

            # Define start and end times (7:30 AM - 1:45 PM CST)
            start_time_cst = specific_date_cst.replace(hour=00, minute=1)
            end_time_cst = specific_date_cst.replace(hour=23, minute=59)

            # Convert start and end times to UTC
            start_time_utc = start_time_cst.astimezone(pytz.utc)
            end_time_utc = end_time_cst.astimezone(pytz.utc)

            # Fetch price history from API
            data = self.client.price_history(
                symbol,  # Use provided symbol
                "day",
                frequencyType="minute",
                frequency=frequency,
                startDate=start_time_utc,
                endDate=end_time_utc,
                needExtendedHoursData=True
            ).json()

            if 'candles' not in data:
                raise ValueError(f"No data available for {symbol} on {date_str}")

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
            print(f"Error fetching data for {symbol} on {date_str}: {e}")
            return None


    def fetch_price_history_for_backtesting(self, symbol, start_date_str, frequencyType, frequency, needExtendedHoursData, end_date_str=None):
        """
        Fetch market price data with flexible interval handling.

        :param symbol: Stock/futures symbol (e.g., "/ESH25")
        :param start_date_str: Start date in 'YYYY-MM-DD' format
        :param end_date_str: End date in 'YYYY-MM-DD' format (optional)
        :param frequencyType: Interval type ('minute', 'daily', etc.)
        :param frequency: Number of units (1, 5, 15, etc.)
        :param needExtendedHoursData: Boolean flag for extended hours data
        :return: Pandas DataFrame with OHLCV data
        """
        try:
            # Ensure start_date starts at 00:01:00
            start_date = self.cst.localize(
                datetime.strptime(start_date_str, "%Y-%m-%d")
            ).replace(hour=0, minute=1, second=0)

            # Ensure end_date ends at 23:59:00
            if end_date_str:
                end_date = self.cst.localize(
                    datetime.strptime(end_date_str, "%Y-%m-%d")
                ).replace(hour=23, minute=59, second=0)
            else:
                end_date = self.cst.localize(datetime.now()).replace(hour=23, minute=59, second=0)

            start_time_utc, end_time_utc = start_date.astimezone(pytz.utc), end_date.astimezone(pytz.utc)

            # Fetch data from API
            data = self.client.price_history(
                symbol,
                frequencyType=frequencyType,
                frequency=frequency,
                needExtendedHoursData=needExtendedHoursData,
                startDate=start_time_utc,
                endDate=end_time_utc
            ).json()

            if 'candles' not in data:
                raise ValueError(f"No data available for {symbol} between {start_date_str} and {end_date_str}")

            # Convert timestamps to CST
            for candle in data['candles']:
                candle['datetime'] = self.convert_to_central_time(candle['datetime'])

            df = pd.json_normalize(data['candles'])
            df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume', 'datetime': 'Datetime'}, inplace=True)
            df.set_index('Datetime', inplace=True)

            return df

        except Exception as e:
            logging.error(f"Error fetching data for {symbol} between {start_date_str} and {end_date_str}: {e}")
            return None
