from datetime import datetime, timedelta
import copy
from typing import List
import pandas as pd

import pandas_ta as ta
import signal
import logging
import redis
from sideways_structure import SidewaysStructure
from schwab_client import Client

from get_market_data import MarketDataHelper
from order_api import SchwabOrderManager
from swing_info import SwingInfo
from divergence_info import DivergenceInfo
import talib
from rsistochfibnumber import RsiStochFibNumber
import psycopg2
from psycopg2 import sql
from threading import Thread
import sys
from itertools import chain
from ElliotWaveHelper import ElliotWaveHelper
import psutil
import time

pd.options.mode.chained_assignment = None  # Disable the warning

# Configure logging
logging.basicConfig(filename="trading_bot.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Global flag for stopping bot gracefully
running = True

# Initialize Redis connection
redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Database connection parameters
DB_PARAMS = {
    "dbname": "wealth_wise",
    "user": "wealth_user",
    "password": "wealth_pass",
    "host": "localhost",
    "port": "5432"
}

def signal_handler(sig, frame):
    """Handles termination signals (SIGTERM, SIGINT)"""
    global running
    logging.info("Bot received termination signal. Stopping...")
    running = False

# Register signal handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

class TradingBot:

    def __init__(self,  bot_id):
        self.bot_id = bot_id
        self.symbol_ironbeam = None
        self.symbol_schwab = None
        self.lot_size = None
        self.live_trading = False
        self.stop_loss_adjust = None
        self.enable_trade_buying = None
        self.enable_trade_shorting = None

        # Connect to the database
        self.db_conn = psycopg2.connect(**DB_PARAMS)
        self.db_conn.autocommit = True
        self.cursor = self.db_conn.cursor()

        # Credentials from CustomerDetails
        self.username = None
        self.password_hash = None
        self.api_key = None

        # Load bot configuration
        self.load_bot_configuration()

        self.schwab_client = None
        self.schwab_account_hash = None
        self.order_api = None
        self.initialize_schwab_client()



        self.stop_loss_order_id = None
        # Trade Attributes
        self.buy_order = False
        self.short_order = False
        self.in_trade = False
        self.close_only_once = False
        self.high_price_during_trading = None
        self.low_price_during_trading = None
        self.track_all_candles_during_buy = []
        self.track_all_candles_during_short = []
        self.save_downward_swing_current = None
        self.save_upward_swing_current = None
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
        self.in_trade_candle = None

        self.current_candle = None

        self.candles_above_94 = []
        self.candles_below_5 = []
        self.cover_stop_limit = None
        self.sell_stop_limit = None

        self.zig_zag_swing_collection = {}
        self.swing_collection = {}
        self.divergences_by_index = {}
        self.update = True
        self.buying_shorting_conditions = {}
        self.initial_df = None


        self.latest_upward_swing_candle_from_10_leg = None
        self.latest_downward_swing_candle_from_10_leg = None
        self.previous_downward_swing_candle_from_10_leg = None
        self.previous_upward_swing_candle_from_10_leg = None

        self.candle_touched_rsi_high = None
        self.candle_touched_sd_high = None
        self.candle_touched_k_high = None
        self.candle_touched_d_high = None
        self.candle_touched_k_low = None
        self.candle_touched_sd_low = None
        self.candle_touched_rsi_low = None
        self.candle_touched_d_low = None
        self.high_rsi_limit = 94
        self.low_rsi_limit = 5
        self.high_k_limit = 80
        self.low_k_limit = 20
        self.high_d_limit = 80
        self.low_d_limit = 20

        self.bulk_buy_stop_loss_order_id = None
        self.bulk_sell_stop_loss_order_id = None
        self.bulk_lot_size = None


        self.first_high_rsi_candle_during_buy = None
        self.first_low_rsi_candle_during_short = None

        self.second_high_rsi_candle_during_buy = None
        self.second_low_rsi_candle_during_short = None

        self.in_memory_short_divergence_candle = None
        self.in_memory_buy_divergence_candle = None
        self.in_memory_divergence_info = None
        self.manual_buy_short_trigger_candle = None

        self.last_wave_in_impulsive_downtrend = None
        self.last_wave_in_impulsive_uptrend = None
        self.profit_taking_or_stop_loss_candle = None
        self.wave2_downtrend_3leg = None
        self.wave2_uptrend_3leg = None
        self.wave1_downtrend_3leg = None
        self.wave1_uptrend_3leg = None
        self.stop_loss = None
        self.close_due_to_stop_loss = None
        self.stop_loss_used = False

        self.wave_w_corrective_10leg = None
        self.wave_x_corrective_10leg = None

        self.df_3legs = None
        self.df_10legs  = None
        self.triggered_elliot_waves = False


    def get_hash_value(self, data, account_number):
        for item in data:
            if item['accountNumber'] == account_number:
                return item['hashValue']
        return None

    def initialize_schwab_client(self):
        api_key = 'REDACTED__see_legacy_REDACTIONS_md'
        app_secret = 'REDACTED__see_legacy_REDACTIONS_md'
        callback_url = 'https://127.0.0.1:8182'
        self.schwab_client = Client(api_key, app_secret, callback_url, verbose=True)
        linked_accounts = self.schwab_client.account_linked().json()
        self.schwab_account_hash = self.get_hash_value(linked_accounts, self.username)
        self.order_api = SchwabOrderManager(self.schwab_client,  self.schwab_account_hash, self.symbol_schwab, logging.info)

    def load_bot_configuration(self):
        """Fetch bot configuration and customer credentials based on bot_id"""
        query = sql.SQL("""
            SELECT b.symbol_ironbeam, b.symbol_schwab, b.lot_size, b.stop_loss_adjust, b.strategy, b.live_trading,
                   c.username, c.password_hash, c.api_key,  b.enable_trade_buying, b.enable_trade_shorting
            FROM bots b
            JOIN customer_details c ON b.customer_id = c.customer_id
            WHERE b.bot_id = %s
        """)
        self.cursor.execute(query, (self.bot_id,))
        bot_data = self.cursor.fetchone()

        if bot_data:
            self.symbol_ironbeam, self.symbol_schwab, self.lot_size, self.stop_loss_adjust, self.strategy, self.live_trading, self.username, self.password_hash, self.api_key, self.enable_trade_buying, self.enable_trade_shorting = bot_data
            logging.info(f"Bot {self.bot_id} initialized with:")
            logging.info(f"Symbols: ({self.symbol_ironbeam}, {self.symbol_schwab}), Lot Size: {self.lot_size}, Strategy: {self.strategy}, Live Trading: {self.live_trading},  Enable Trade Buying: {self.enable_trade_buying},  Enable Trade Shorting: {self.enable_trade_shorting}")
            logging.info(f"Credentials: Username={self.username}, API Key={self.api_key}")
        else:
            logging.error(f"Bot {self.bot_id} not found in the database!")

    def reconnect_db(self):
        """Reconnect to the database and recreate cursor"""
        try:
            logging.info("Reconnecting to database...")
            self.db_conn = psycopg2.connect(**DB_PARAMS)
            self.db_conn.autocommit = True
            self.cursor = self.db_conn.cursor()
            logging.info("Reconnected successfully!")
        except psycopg2.Error as e:
            logging.error(f"Failed to reconnect: {e}")

    def ensure_connection(self):
        """Ensure database connection and cursor are open"""
        if self.db_conn.closed:
            self.reconnect_db()
        if self.cursor.closed:
            self.cursor = self.db_conn.cursor()

    def update_trade_status(self, trade_type, is_flat=False):
        """Update bot's trade status in the database"""
        self.ensure_connection()

        self.current_trade = trade_type
        if is_flat:
            self.current_trade = "NONE"

        update_query = sql.SQL("UPDATE bots SET current_trade_status = %s WHERE bot_id = %s")

        try:
            self.cursor.execute(update_query, (self.current_trade, self.bot_id))
            self.db_conn.commit()
            logging.info(f"Bot {self.bot_id}: Trade status updated to {trade_type}")
        except psycopg2.Error as e:
            logging.error(f"Database error: {e}")
            self.reconnect_db()

    def update_bot_trade_status(self):
        """Update bot's trade status in the database"""
        self.ensure_connection()

        if self.in_trade:
            if self.buy_order:
                self.current_trade = "BUY"
            elif self.short_order:
                self.current_trade = "SELL"

            update_query = sql.SQL("UPDATE bots SET current_bot_trade_status = %s WHERE bot_id = %s")

            try:
                self.cursor.execute(update_query, (self.current_trade, self.bot_id))
                self.db_conn.commit()
            except psycopg2.Error as e:
                logging.error(f"Database error: {e}")
                self.reconnect_db()

    def update_bot_stop_trade_status(self):
        """Update bot's trade status in the database"""
        self.ensure_connection()

        self.current_trade = "NONE"

        try:
            update_query = sql.SQL("UPDATE bots SET current_trade_status = %s WHERE bot_id = %s")
            self.cursor.execute(update_query, (self.current_trade, self.bot_id))

            update_query = sql.SQL("UPDATE bots SET current_bot_trade_status = %s WHERE bot_id = %s")
            self.cursor.execute(update_query, (self.current_trade, self.bot_id))

            self.db_conn.commit()
        except psycopg2.Error as e:
            logging.error(f"Database error: {e}")
            self.reconnect_db()

    def insert_trade(self, trade_type, price, lot_size, is_flat=False):
        """Insert a new trade record into the trades table"""
        self.ensure_connection()
        self.update_trade_status(trade_type, is_flat)

        insert_query = sql.SQL("""
            INSERT INTO trades (bot_id, symbol, lot_size, trade_type, price, status)
            VALUES (%s, %s, %s, %s, %s, 'EXECUTED')
        """)

        try:
            self.cursor.execute(insert_query, (self.bot_id, self.symbol_ironbeam, lot_size, trade_type, price))
            self.db_conn.commit()
            logging.info(f"Bot {self.bot_id}: Trade inserted - {trade_type} at price {price}")
        except psycopg2.Error as e:
            logging.error(f"Database error: {e}")
            self.reconnect_db()

    def listen_for_commands(self):
        """Listens to Redis Pub/Sub for trading actions, including BULK_BUY & BULK_SELL."""
        pubsub = redis_client.pubsub()
        pubsub.subscribe(f"bot:{self.bot_id}")

        logging.info(f"Bot {self.bot_id} listening for commands...")

        for message in pubsub.listen():
            if message["type"] == "message":
                action = message["data"]

                # Handle Live Trading Enable/Disable
                if action == "ENABLE_LIVE_TRADING":
                    self.live_trading = True
                    logging.info(f"Bot {self.bot_id}: Live trading ENABLED")

                elif action == "DISABLE_LIVE_TRADING":
                    self.live_trading = False
                    logging.info(f"Bot {self.bot_id}: Live trading DISABLED")
                    self.update_trade_status("NONE", True)

                elif action == "ENABLE_TRADING_BUYING":
                    self.enable_trade_buying = True
                    logging.info(f"Bot {self.bot_id}: Buy Trading ENABLED")

                elif action == "DISABLE_TRADING_BUYING":
                    self.enable_trade_buying = False
                    logging.info(f"Bot {self.bot_id}: Buy Trading DISABLED")

                elif action == "ENABLE_TRADING_SHORTING":
                    self.enable_trade_shorting = True
                    logging.info(f"Bot {self.bot_id}: Short Trading ENABLED")

                elif action == "DISABLE_TRADING_SHORTING":
                    self.enable_trade_shorting = False
                    logging.info(f"Bot {self.bot_id}: Short Trading DISABLED")

                # Handle Standard Trading Actions
                elif action == "FLIP":
                    logging.info(f"Bot {self.bot_id}: Executing FLIP")
                    flipped = False
                    if self.buy_order:
                        self.short_order = True
                        self.buy_order = False
                        self.in_trade_candle = self.current_candle
                        flipped = True
                        if self.live_trading and self.stop_loss_order_id:
                            self.order_api.submit_cancel_order(self.stop_loss_order_id)
                            self.order_api.submit_buy_sell_market_order(False, self.lot_size)
                            self.insert_trade("SELL", self.current_candle.close, self.lot_size)
                            self.stop_loss_order_id = None
                        if self.live_trading:
                            stop_limit_price = float(self.get_stop_loss(False)) + float(self.stop_loss_adjust)
                            self.order_api.submit_short_cover_market_order(True, self.lot_size)
                            self.order_api.submit_stop_market_order(stop_limit_price, True,  self.lot_size)
                            self.stop_loss_order_id = self.order_api.stop_loss_order_id
                        self.update_bot_trade_status()
                        logging.info(f"Bot Id # {self.bot_id}, self.stop_loss_order_id # {self.stop_loss_order_id},   Symbol # {self.symbol_schwab}, Current Trade Status # {self.in_trade} ,  Buy Trade # {self.buy_order} , Short order # {self.short_order} , Live Trading # {self.live_trading}")

                    if self.short_order and not flipped:
                        self.short_order = False
                        self.buy_order = True
                        self.in_trade_candle = self.current_candle
                        if self.live_trading and self.stop_loss_order_id:
                            self.order_api.submit_cancel_order(self.stop_loss_order_id)
                            self.order_api.submit_short_cover_market_order(False, self.lot_size)
                            self.stop_loss_order_id = None
                            self.insert_trade("BUY", self.current_candle.close, self.lot_size)
                        if self.live_trading:
                            stop_limit_price = float(self.get_stop_loss(True)) - float(self.stop_loss_adjust)
                            self.order_api.submit_buy_sell_market_order(True, self.lot_size)
                            self.order_api.submit_stop_market_order(stop_limit_price, False,  self.lot_size)
                            self.stop_loss_order_id = self.order_api.stop_loss_order_id
                            self.insert_trade("BUY", self.current_candle.close, self.lot_size)
                        self.update_bot_trade_status()
                        logging.info(f"Bot Id # {self.bot_id}, self.stop_loss_order_id # {self.stop_loss_order_id},  Symbol # {self.symbol_schwab}, Current Trade Status # {self.in_trade} ,  Buy Trade # {self.buy_order} , Short order # {self.short_order} , Live Trading # {self.live_trading}")

                elif action == "FLAT":
                    logging.info(f"Bot {self.bot_id}: Executing FLAT")
                    if self.live_trading and self.in_trade:
                        if self.buy_order and self.stop_loss_order_id:
                            self.order_api.submit_cancel_order(self.stop_loss_order_id)
                            self.order_api.submit_buy_sell_market_order(False, self.lot_size)
                            self.stop_loss_order_id = None
                            self.insert_trade("SELL", self.current_candle.close, self.lot_size, True)

                        if self.buy_order and self.bulk_sell_stop_loss_order_id and self.bulk_lot_size:
                            self.order_api.submit_cancel_order(self.bulk_sell_stop_loss_order_id)
                            self.order_api.submit_buy_sell_market_order(False, self.bulk_lot_size)
                            self.bulk_sell_stop_loss_order_id = None
                            self.insert_trade("SELL", self.current_candle.close, self.bulk_lot_size, True)
                            self.bulk_lot_size = None

                        if self.short_order and self.stop_loss_order_id:
                            self.order_api.submit_cancel_order(self.stop_loss_order_id)
                            self.order_api.submit_short_cover_market_order(False, self.lot_size)
                            self.stop_loss_order_id = None
                            self.insert_trade("BUY", self.current_candle.close, self.lot_size, True)

                        if self.short_order and self.bulk_sell_stop_loss_order_id and self.bulk_lot_size:
                            self.order_api.submit_cancel_order(self.bulk_sell_stop_loss_order_id)
                            self.order_api.submit_short_cover_market_order(False, self.bulk_lot_size)
                            self.bulk_sell_stop_loss_order_id = None
                            self.insert_trade("BUY", self.current_candle.close, self.bulk_lot_size, True)
                            self.bulk_lot_size = None
                    logging.info(f"Bot Id # {self.bot_id}, self.stop_loss_order_id # {self.stop_loss_order_id}, self.bulk_sell_stop_loss_order_id # {self.bulk_sell_stop_loss_order_id},  Symbol # {self.symbol_schwab}, Current Trade Status # {self.in_trade} ,  Buy Trade # {self.buy_order} , Short order # {self.short_order} , Live Trading # {self.live_trading}")

                elif action == "BULK_FLAT":
                    logging.info(f"Bot {self.bot_id}: Executing BULK FLAT")
                    if self.live_trading and self.in_trade:

                        if self.buy_order and self.bulk_sell_stop_loss_order_id and self.bulk_lot_size:
                            self.order_api.submit_cancel_order(self.bulk_sell_stop_loss_order_id)
                            self.order_api.submit_buy_sell_market_order(False, self.bulk_lot_size)
                            self.bulk_sell_stop_loss_order_id = None
                            self.insert_trade("SELL", self.current_candle.close, self.bulk_lot_size, True)
                            self.bulk_lot_size = None

                        if self.short_order and self.bulk_sell_stop_loss_order_id and self.bulk_lot_size:
                            self.order_api.submit_cancel_order(self.bulk_sell_stop_loss_order_id)
                            self.order_api.submit_short_cover_market_order(False, self.bulk_lot_size)
                            self.bulk_sell_stop_loss_order_id = None
                            self.insert_trade("BUY", self.current_candle.close, self.bulk_lot_size, True)
                            self.bulk_lot_size = None
                        logging.info(f"Bot Id # {self.bot_id}, self.stop_loss_order_id # {self.stop_loss_order_id}, self.bulk_sell_stop_loss_order_id # {self.bulk_sell_stop_loss_order_id},  Symbol # {self.symbol_schwab}, Current Trade Status # {self.in_trade} ,  Buy Trade # {self.buy_order} , Short order # {self.short_order} , Live Trading # {self.live_trading}")

                elif action == "BUY":
                    logging.info(f"Bot {self.bot_id}: Executing BUY")
                    if self.buy_order and not self.stop_loss_order_id and self.live_trading:
                        stop_limit_price = float(self.get_stop_loss(True)) - float(self.stop_loss_adjust)
                        self.order_api.submit_buy_sell_market_order(True, self.lot_size)
                        self.order_api.submit_stop_market_order(stop_limit_price, False,  self.lot_size)
                        self.stop_loss_order_id = self.order_api.stop_loss_order_id
                        self.insert_trade("BUY", self.current_candle.close, self.lot_size)
                        logging.info(f"Bot Id # {self.bot_id}, self.stop_loss_order_id # {self.stop_loss_order_id},  Symbol # {self.symbol_schwab}, Current Trade Status # {self.in_trade} ,  Buy Trade # {self.buy_order} , Short order # {self.short_order} , Live Trading # {self.live_trading}")

                elif action == "FORCE_BUY":
                    logging.info(f"Bot {self.bot_id}: Executing FORCE_BUY")
                    if not self.in_trade and self.live_trading:
                        self.in_trade = True
                        self.buy_order = True
                        stop_limit_price = float(self.get_stop_loss(True)) - float(self.stop_loss_adjust)
                        self.order_api.submit_buy_sell_market_order(True, self.lot_size)
                        self.order_api.submit_stop_market_order(stop_limit_price, False,  self.lot_size)
                        self.stop_loss_order_id = self.order_api.stop_loss_order_id
                        self.insert_trade("BUY", self.current_candle.close, self.lot_size)
                        self.update_bot_trade_status()
                        self.in_trade_candle = self.current_candle
                        logging.info(f"Bot Id # {self.bot_id}, self.stop_loss_order_id # {self.stop_loss_order_id},  Symbol # {self.symbol_schwab}, Current Trade Status # {self.in_trade} ,  Buy Trade # {self.buy_order} , Short order # {self.short_order} , Live Trading # {self.live_trading}")

                elif action == "SELL":
                    logging.info(f"Bot {self.bot_id}: Executing SELL")
                    if self.short_order and not self.stop_loss_order_id and self.live_trading:
                        stop_limit_price = float(self.get_stop_loss(False)) + float(self.stop_loss_adjust)
                        self.order_api.submit_short_cover_market_order(True, self.lot_size)
                        self.order_api.submit_stop_market_order(stop_limit_price, True,  self.lot_size)
                        self.stop_loss_order_id = self.order_api.stop_loss_order_id
                        self.insert_trade("SELL", self.current_candle.close, self.lot_size)
                        logging.info(f"Bot Id # {self.bot_id}, self.stop_loss_order_id # {self.stop_loss_order_id},  Symbol # {self.symbol_schwab}, Current Trade Status # {self.in_trade} ,  Buy Trade # {self.buy_order} , Short order # {self.short_order} , Live Trading # {self.live_trading}")

                elif action == "FORCE_SELL":
                    logging.info(f"Bot {self.bot_id}: Executing FORCE_SELL")
                    if not self.in_trade and self.live_trading:
                        self.in_trade = True
                        self.short_order = True
                        stop_limit_price = float(self.get_stop_loss(False)) + float(self.stop_loss_adjust)
                        self.order_api.submit_short_cover_market_order(True, self.lot_size)
                        self.order_api.submit_stop_market_order(stop_limit_price, True,  self.lot_size)
                        self.stop_loss_order_id = self.order_api.stop_loss_order_id
                        self.insert_trade("SELL", self.current_candle.close, self.lot_size)
                        self.update_bot_trade_status()
                        self.in_trade_candle = self.current_candle
                        logging.info(f"Bot Id # {self.bot_id}, self.stop_loss_order_id # {self.stop_loss_order_id},  Symbol # {self.symbol_schwab}, Current Trade Status # {self.in_trade} ,  Buy Trade # {self.buy_order} , Short order # {self.short_order} , Live Trading # {self.live_trading}")

                # Handle BULK_BUY and BULK_SELL
                elif action.startswith("BULK_BUY:"):
                    lot_size = int(action.split(":")[1])
                    logging.info(f"Bot {self.bot_id}: Executing BULK_BUY with {lot_size} lots")
                    if lot_size > 0 and  self.live_trading and self.in_trade:
                        if self.buy_order and self.stop_loss_order_id:
                            self.bulk_lot_size = lot_size
                            stop_limit_price = float(self.get_stop_loss(True)) - float(self.stop_loss_adjust)
                            self.order_api.submit_buy_sell_market_order(True, lot_size)
                            self.order_api.submit_stop_market_order(stop_limit_price, False,  lot_size)
                            self.bulk_sell_stop_loss_order_id = self.order_api.stop_loss_order_id
                            self.insert_trade("BUY", self.current_candle.close,lot_size)
                            logging.info(f"Bot Id # {self.bot_id}, self.stop_loss_order_id # {self.stop_loss_order_id},  Symbol # {self.symbol_schwab}, Current Trade Status # {self.in_trade} ,  Buy Trade # {self.buy_order} , Short order # {self.short_order} , Live Trading # {self.live_trading}")

                elif action.startswith("BULK_SELL:"):
                    lot_size = int(action.split(":")[1])
                    logging.info(f"Bot {self.bot_id}: Executing BULK_SELL with {lot_size} lots")
                    if lot_size > 0 and self.live_trading and self.in_trade:
                        if self.short_order and self.stop_loss_order_id:
                            self.bulk_lot_size = lot_size
                            stop_limit_price = float(self.get_stop_loss(False)) + float(self.stop_loss_adjust)
                            self.order_api.submit_short_cover_market_order(True, lot_size)
                            self.order_api.submit_stop_market_order(stop_limit_price, True,  lot_size)
                            self.bulk_sell_stop_loss_order_id = self.order_api.stop_loss_order_id
                            self.insert_trade("SELL", self.current_candle.close, lot_size)
                            logging.info(f"Bot Id # {self.bot_id}, self.stop_loss_order_id # {self.stop_loss_order_id},  Symbol # {self.symbol_schwab}, Current Trade Status # {self.in_trade} ,  Buy Trade # {self.buy_order} , Short order # {self.short_order} , Live Trading # {self.live_trading}")

                # Stop Bot Execution
                elif action == "STOP":
                    logging.info(f"Bot {self.bot_id} stopping...")
                    self.update_bot_stop_trade_status()
                    global running
                    running = False
                    break  # Exit loop to stop the bot

    def get_green_wick_up(self, row):
        if row.BODY > 0:
            upper_wick_length = row.High - row.Close
            candle_range = row.High - row.Low
            result = (upper_wick_length / candle_range) * 100
            return round(result, 2)
        else:
            return 0

    def get_green_wick_down(self, row):
        if row.BODY > 0:
            lower_wick_length = row.Open - row.Low
            candle_range = row.High - row.Low
            result = (lower_wick_length / candle_range) * 100
            return round(result, 2)
        else:
            return 0

    def get_red_wick_up(self, row):
        if row.BODY < 0:
            upper_wick_length = row.High - row.Open
            candle_range = row.High - row.Low
            result = (upper_wick_length / candle_range) * 100
            return round(result, 2)
        else:
            return 0

    def get_red_wick_down(self, row):
        if row.BODY < 0:
            lower_wick_length = row.Close - row.Low
            candle_range = row.High - row.Low
            result = (lower_wick_length / candle_range) * 100
            return round(result, 2)
        else:
            return 0

    def get_body_volume(self, row):
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

    def get_red_wick_up_volume(self, row):
        if row.RANGE > 0 and row.BODY < 0 and row.RED_WICK_UP > 0:
            return round( row.Volume * row.RED_WICK_UP/100, 2)
        else:
            return 0

    def get_green_wick_up_volume(self, row):
        if row.RANGE > 0 and row.BODY > 0 and row.GREEN_WICK_UP > 0:
            return round(row.Volume * row.GREEN_WICK_UP/100 , 2)
        else:
            return 0

    def get_red_wick_down_volume(self, row):
        if row.RANGE > 0 and row.BODY < 0 and row.RED_WICK_DOWN > 0:
            return round(row.Volume * row.RED_WICK_DOWN/100, 2)
        else:
            return 0

    def get_green_wick_down_volume(self, row):
        if row.RANGE > 0 and row.BODY > 0 and row.GREEN_WICK_DOWN > 0:
            return round(row.Volume * row.GREEN_WICK_DOWN/100, 2)
        else:
            return 0

    def apply_body_percentage(self, row):
        body_percentage = 0
        direction = row.Close - row.Open
        body_size = abs(direction)
        full_range = row.High - row.Low
        if full_range > 0:
            body_percentage = round((body_size / full_range) * 100, 2)
        return body_percentage

    def relative_volume_std_dev(self, volume_series, length=30, num_dev=2.0):
        """Computes Relative Volume Standard Deviation (RVSD)."""
        mean_volume = talib.SMA(volume_series, timeperiod=length)
        std_dev_volume = talib.STDDEV(volume_series, timeperiod=length, nbdev=1)
        rvsd = (volume_series - mean_volume) / (std_dev_volume + 1e-9)  # Avoid division by zero
        return rvsd

    def freedom_of_movement(self, close_series, length=30, num_dev=2.0):
        """Computes Freedom of Movement (FoM)."""
        prev_close = close_series.shift(1)
        std_dev_price = talib.STDDEV(close_series, timeperiod=length, nbdev=1)
        fom = (close_series - prev_close) / (std_dev_price + 1e-9)  # Avoid division by zero
        return fom

    def apply_rsi_stoch_doji_fib(self, data):

        num_dev = 2.0
        length = 30
        df = data.copy()
        df.index = pd.to_datetime(df.index)
        df.index = df.index.tz_localize(None)
        df["RSI"] = talib.RSI(df['Close'], 2)
        df["STOCH"], df["STOCH_D"] = talib.STOCHRSI(df["Close"], timeperiod=14, fastk_period=14, fastd_period=3)
        # Rounding to 2 decimal places
        df["STOCH"] = df["STOCH"].round(2)
        df["STOCH_D"] = df["STOCH_D"].round(2)
        df["RSI"] = df["RSI"].round(2)
        df["DATE"] = df.index.strftime("%m/%d %I:%M %p")
        df["PRICE"] = df['Close'] - df['Open']
        df['previous_close'] = df['Close'].shift(1)
        df['previous_open'] = df['Open'].shift(1)
        df['previous_volume'] = df['Volume'].shift(1)
        df["BODY"] = df['Close'] - df['Open']
        df["RANGE"] = df['High'] - df['Low']
        df["GREEN_WICK_UP"] = df.apply(self.get_green_wick_up, axis=1)
        df["GREEN_WICK_DOWN"] = df.apply(self.get_green_wick_down, axis=1)
        df["RED_WICK_UP"] = df.apply(self.get_red_wick_up, axis=1)
        df["RED_WICK_DOWN"] = df.apply(self.get_red_wick_down, axis=1)
        df["BODY_VOLUME"] = df.apply(self.get_body_volume, axis=1)
        df["GREEN_WICK_UP_VOLUME"] = df.apply(self.get_green_wick_up_volume, axis=1)
        df["RED_WICK_UP_VOLUME"] = df.apply(self.get_red_wick_up_volume, axis=1)
        df["GREEN_WICK_DOWN_VOLUME"] = df.apply(self.get_green_wick_down_volume, axis=1)
        df["RED_WICK_DOWN_VOLUME"] = df.apply(self.get_red_wick_down_volume, axis=1)
        df["BODY_PERCENT"] = df.apply(self.apply_body_percentage, axis=1)
        df['PREVIOUS_BODY'] = df['BODY'].shift(1)
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
        df["RSI_13"] = talib.RSI(df['Close'], 13)
        df["RSI_13"] =  df["RSI_13"].round(2)
        df['MEDIAN'] = (df['High'] + df['Low']) / 2
        df['AVG_MEDIAN'] = df['MEDIAN'].rolling(window=5).mean()
        df['PREVIOUS_MEDIAN'] = df['MEDIAN'].shift(1)
        df['PREVIOUS_AVG_MEDIAN'] = df['AVG_MEDIAN'].shift(1)
        df['previous_index'] = df.index.to_series().shift(1)

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
        df["RVSD"] = self.relative_volume_std_dev(df["Volume"], length=30, num_dev=num_dev)
        df["Above_RVSD"] = df["RVSD"] > num_dev  # Extreme high volume
        df["Below_RVSD"] = df["RVSD"] < -num_dev  # Extreme low volume

        # Compute FoM with ThinkOrSwim settings (length=30, num_dev=2.0)
        df["FoM"] = self.freedom_of_movement(df["Close"], length=30, num_dev=num_dev)
        df["Above_FoM"] = df["FoM"] > num_dev  # Strong upward movement
        df["Below_FoM"] = df["FoM"] < -num_dev  # Strong downward movement
        # Assuming df is your DataFrame and it includes a 'Close' column
        close = df['Close']
        df = df[df.High != df.Low]
        df = df.round(4)
        return df

    def create_rsi_stoch_fib(self, candle):
        data = RsiStochFibNumber(candle.Open, candle.Close, candle.High, candle.Low, candle.RSI, candle.STOCH, candle.STOCH_D, 0, candle.DATE, candle.BODY, 0, 0)
        data.volume = candle.Volume
        data.previous_open = candle.previous_open
        data.previous_close = candle.previous_close
        data.previous_volume = candle.previous_volume
        data.green_wick_up_percent = candle.GREEN_WICK_UP
        data.green_wick_down_percent = candle.GREEN_WICK_DOWN
        data.red_wick_up_percent = candle.RED_WICK_UP
        data.red_wick_down_percent = candle.RED_WICK_DOWN
        data.body_percent = candle.BODY_PERCENT
        data.previous_green_wick_up_percent = candle.PREVIOUS_GREEN_WICK_UP
        data.previous_green_wick_down_percent = candle.PREVIOUS_GREEN_WICK_DOWN
        data.previous_red_wick_up_percent = candle.PREVIOUS_RED_WICK_UP
        data.previous_red_wick_down_percent = candle.PREVIOUS_RED_WICK_DOWN
        data.previous_body_percent = candle.PREVIOUS_BODY_PERCENT
        data.body_volume = float(candle.BODY_VOLUME) if candle.BODY_VOLUME is not None else 0.0
        data.previous_body_volume = float(candle.PREVIOUS_BODY_VOLUME) if candle.PREVIOUS_BODY_VOLUME is not None else 0.0
        data.previous_body = candle.PREVIOUS_BODY
        data.previous_rsi = candle.PREVIOUS_RSI
        data.previous_stoch_k = candle.PREVIOUS_STOCH
        data.previous_stoch_d = candle.PREVIOUS_STOCH_D
        data.range = candle.RANGE
        data.previous_range = candle.PREVIOUS_RANGE
        data.previous_high = candle.PREVIOUS_HIGH
        data.previous_low = candle.PREVIOUS_LOW
        data.rsi_13 = candle.RSI_13
        data.index = candle.name
        data.previous_index = candle.previous_index
        data.median = candle.MEDIAN
        data.avg_median = candle.AVG_MEDIAN
        data.previous_median =candle.PREVIOUS_MEDIAN
        data.previous_avg_median = candle.PREVIOUS_AVG_MEDIAN
        data.datetime = candle.name
        data.previous_candle_datetime = candle.previous_index
        data.std_second_top_price = candle.Two_SD_Top
        data.std_second_bottom_price = candle.Two_SD_Bottom

        return data

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
                        logging.info(f"Candle without 'high': {candle}")

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
                        logging.info(f"Date # {current_candle.date} :Pre-Condition Bullish Internal Non-Extreme Divergence Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {closest_highest_rsi_candle.date} , Origin RSI {closest_highest_rsi_candle.rsi}, Origin STOCH_K  {closest_highest_rsi_candle.stoch_k},  Origin STOCH_D  {closest_highest_rsi_candle.stoch_d} , End Date {downward_swing_current.new_low_candle.date} , End RSI {downward_swing_current.new_low_candle.rsi}, End STOCH_K {downward_swing_current.new_low_candle.stoch_k}, End STOCH_D {downward_swing_current.new_low_candle.stoch_d}")
                        if current_candle.close > downward_swing_current.new_low_candle.high:
                            converting_to_buy = True
                    if converting_to_buy:
                        downward_swing_current.new_low_candle.divergence_used = True
                        self.update_divergence_used_in_memory(downward_swing_current.new_low_candle)
                        logging.info(f"Date # {current_candle.date} :Bullish Internal Non-Extreme Divergence Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {closest_highest_rsi_candle.date} , Origin RSI {closest_highest_rsi_candle.rsi}, Origin STOCH_K  {closest_highest_rsi_candle.stoch_k},  Origin STOCH_D  {closest_highest_rsi_candle.stoch_d} , End Date {downward_swing_current.new_low_candle.date} , End RSI {downward_swing_current.new_low_candle.rsi}, End STOCH_K {downward_swing_current.new_low_candle.stoch_k}, End STOCH_D {downward_swing_current.new_low_candle.stoch_d}")
                        self.add_candles_buy_side = [candle for candle in self.track_all_candles_during_short if candle.datetime >= downward_swing_current.new_low_candle.datetime]
                    self.add_divergence_info(True, False, converting_to_buy, closest_highest_rsi_candle, downward_swing_current.new_low_candle, False , False, downward_swing_current, False, False )

        if closest_lowest_rsi_candle and closest_lowest_rsi_candle.body < 0 and downward_swing_current and not downward_swing_current.new_low_candle.divergence_used:
            time_diff = abs(closest_lowest_rsi_candle.datetime - downward_swing_current.new_low_candle.datetime)
            if downward_swing_current.new_low_candle.low < closest_lowest_rsi_candle.low and downward_swing_current.new_low_candle.close <= closest_lowest_rsi_candle.low and time_diff.total_seconds() < 30 * 60 and time_diff.total_seconds() > 2 * 60:
                if downward_swing_current.new_low_candle.rsi > closest_lowest_rsi_candle.rsi:
                    pre_condition_buy = True
                    logging.info(f"Date # {current_candle.date} :Pre-Condition  Bullish Internal Non-Extreme Divergence Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {closest_lowest_rsi_candle.date} , Origin RSI {closest_lowest_rsi_candle.rsi}, End Date {downward_swing_current.new_low_candle.date} , End RSI {downward_swing_current.new_low_candle.rsi}")
                    if current_candle.close > downward_swing_current.new_low_candle.high:
                        converting_to_buy = True
                    if converting_to_buy:
                        downward_swing_current.new_low_candle.divergence_used = True
                        self.update_divergence_used_in_memory(downward_swing_current.new_low_candle)
                        logging.info(f"Date # {current_candle.date} :Bullish Internal Non-Extreme Divergence Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {closest_lowest_rsi_candle.date} , Origin RSI {closest_lowest_rsi_candle.rsi}, End Date {downward_swing_current.new_low_candle.date} , End RSI {downward_swing_current.new_low_candle.rsi}")
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
                        logging.info(f"Date # {current_candle.date} :Pre-Condition  Bearish Internal Non-Extreme Divergence Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {closest_lowest_rsi_candle.date} , Origin RSI {closest_lowest_rsi_candle.rsi}, Origin STOCH_K  {closest_lowest_rsi_candle.stoch_k},  Origin STOCH_D  {closest_lowest_rsi_candle.stoch_d} , End Date {upward_swing_current.new_high_candle.date} , End RSI {upward_swing_current.new_high_candle.rsi}, End STOCH_K {upward_swing_current.new_high_candle.stoch_k}, End STOCH_D {upward_swing_current.new_high_candle.stoch_d}")
                        if current_candle.close < upward_swing_current.new_high_candle.low:
                            converting_to_short = True
                    if converting_to_short:
                        upward_swing_current.new_high_candle.divergence_used = True
                        self.update_divergence_used_in_memory(upward_swing_current.new_high_candle)
                        logging.info(f"Date # {current_candle.date} :Bearish Internal Non-Extreme Divergence Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {closest_lowest_rsi_candle.date} , Origin RSI {closest_lowest_rsi_candle.rsi}, Origin STOCH_K  {closest_lowest_rsi_candle.stoch_k},  Origin STOCH_D  {closest_lowest_rsi_candle.stoch_d} , End Date {upward_swing_current.new_high_candle.date} , End RSI {upward_swing_current.new_high_candle.rsi}, End STOCH_K {upward_swing_current.new_high_candle.stoch_k}, End STOCH_D {upward_swing_current.new_high_candle.stoch_d}")
                        self.add_candles_short_side = [candle for candle in self.track_all_candles_during_buy if candle.datetime >= upward_swing_current.new_high_candle.datetime]
                    self.add_divergence_info(False, pre_condition_short, converting_to_short, closest_lowest_rsi_candle, upward_swing_current.new_high_candle, False , False, upward_swing_current, False, False )


        if closest_highest_rsi_candle and closest_highest_rsi_candle.body > 0 and upward_swing_current and not upward_swing_current.new_high_candle.divergence_used:
            time_diff = abs(closest_highest_rsi_candle.datetime - upward_swing_current.new_high_candle.datetime)
            if upward_swing_current.new_high_candle.close >= closest_highest_rsi_candle.high and upward_swing_current.new_high_candle.high > closest_highest_rsi_candle.high and time_diff.total_seconds() < 30 * 60 and time_diff.total_seconds() > 2 * 60:
                if upward_swing_current.new_high_candle.rsi < closest_highest_rsi_candle.rsi:
                    pre_condition_short = True
                    logging.info(f"Date # {current_candle.date} :Pre-Condition Bearish Internal Non-Extreme Divergence Triggered with Current RSI is lower then Previous RSI  # Origin Date {closest_highest_rsi_candle.date} , Origin RSI {closest_highest_rsi_candle.rsi}, End Date {upward_swing_current.new_high_candle.date} , End RSI {upward_swing_current.new_high_candle.rsi}")
                    if current_candle.close < upward_swing_current.new_high_candle.low:
                        converting_to_short = True
                    if converting_to_short:
                        upward_swing_current.new_high_candle.divergence_used = True
                        self.update_divergence_used_in_memory(upward_swing_current.new_high_candle)
                        logging.info(f"Date # {current_candle.date} :Bearish Internal Non-Extreme Divergence Triggered with Current RSI is lower then Previous RSI # Origin Date {closest_highest_rsi_candle.date} , Origin RSI {closest_highest_rsi_candle.rsi}, End Date {upward_swing_current.new_high_candle.date} , End RSI {upward_swing_current.new_high_candle.rsi}")
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
                        logging.info(f"Date # {current_candle.date} :Pre Condition Bullish External Swings Extreme Divergence Trigger with Current RSI IS Lower Then Previous RSI # Origin Date {lowest_rsi_candle.date}  , Origin RSI {lowest_rsi_candle.rsi}, End Date {lowest_rsi_candle_in_downward_swing.date}, End RSI {lowest_rsi_candle_in_downward_swing.rsi}")
                        pre_condition_buy = True
                        if current_candle.close > downward_swing_current.new_low_candle.high and current_candle.close > lowest_rsi_candle_in_downward_swing.high:
                            logging.info(f"Date # {current_candle.date} :External Swings Extreme Divergence Trigger with Current RSI IS Lower Then Previous RSI # Origin Date {lowest_rsi_candle.date}  , Origin RSI {lowest_rsi_candle.rsi}, End Date {lowest_rsi_candle_in_downward_swing.date}, End RSI {lowest_rsi_candle_in_downward_swing.rsi}")
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
                        logging.info(f"Date # {current_candle.date} :Pre Condition Bearish External Swings Extreme Divergence Trigger with Current RSI IS Higher Then Previous RSI # Origin Date {highest_rsi_candle.date}, Origin RSI {highest_rsi_candle.rsi}, End Date {highest_rsi_candle_in_upward_swing.date}  , End RSI {highest_rsi_candle_in_upward_swing.rsi}")
                        if current_candle.close < self.save_upward_swing_current.new_high_candle.low:
                            logging.info(f"Date # {current_candle.date} :Bearish External Swings Extreme Divergence Trigger with Current RSI IS Higher Then Previous RSI # Origin Date {highest_rsi_candle.date}, Origin RSI {highest_rsi_candle.rsi}, End Date {highest_rsi_candle_in_upward_swing.date}  , End RSI {highest_rsi_candle_in_upward_swing.rsi}")
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
                    logging.info(f"Date # {current_candle.date} :Pre Condition Bullish Internal Swings Extreme Divergence Trigger with Current RSI IS Lower Then Previous RSI # Origin Date {lowest_rsi_candle_in_downward_swing.date} , Origin RSI {lowest_rsi_candle_in_downward_swing.rsi}, End Date {downward_swing_current.new_low_candle.date} , End RSI {downward_swing_current.new_low_candle.rsi}")
                    if current_candle.close > downward_swing_current.new_low_candle.high:
                        time_diff = abs(lowest_rsi_candle_in_downward_swing.datetime - downward_swing_current.new_low_candle.datetime)
                        if time_diff.total_seconds() > 2 * 60:
                            logging.info(f"Date # {current_candle.date} :Bullish Internal Swings Extreme Divergence Trigger with Current RSI IS Lower Then Previous RSI # Origin Date {lowest_rsi_candle_in_downward_swing.date} , Origin RSI {lowest_rsi_candle_in_downward_swing.rsi}, End Date {downward_swing_current.new_low_candle.date} , End RSI {downward_swing_current.new_low_candle.rsi}")
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
                    logging.info(f"Date # {current_candle.date} :Pre Condition Bearish Internal Swings Extreme Divergence Triggered with Current RSI IS Lower Then Previous RSI # Origin Date {highest_rsi_candle_in_upward_swing.date} , Origin RSI {highest_rsi_candle_in_upward_swing.rsi}, End Date {upward_swing_current.new_high_candle.date} , End RSI {upward_swing_current.new_high_candle.rsi}")
                    if current_candle.close < upward_swing_current.new_high_candle.low:
                        time_diff = abs(highest_rsi_candle_in_upward_swing.datetime - upward_swing_current.new_high_candle.datetime)
                        if time_diff.total_seconds() > 2 * 60:
                            logging.info(f"Date # {current_candle.date} :Bearish Internal Swings Extreme Divergence Triggered with Current RSI IS Lower Then Previous RSI # Origin Date {highest_rsi_candle_in_upward_swing.date} , Origin RSI {highest_rsi_candle_in_upward_swing.rsi}, End Date {upward_swing_current.new_high_candle.date} , End RSI {upward_swing_current.new_high_candle.rsi}")
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

    def update_divergence_used_in_memory(self, update_candle):
        for candle in self.track_all_candles:
            if candle.datetime == update_candle.datetime:
                candle.divergence_used = True

    def remove_last_candle_if_invalid(self, df, timeframe_seconds=60):
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

    def run(self):
        next_run_time = datetime.now()
        logging.info("Bot Started")
        api_key = 'REDACTED__see_legacy_REDACTIONS_md'
        app_secret = 'REDACTED__see_legacy_REDACTIONS_md'
        callback_url = 'https://127.0.0.1:8182'
        helper = MarketDataHelper(api_key, app_secret, callback_url)
        current_date = datetime.today().strftime('%Y-%m-%d')
        df = helper.fetch_price_history(self.symbol_schwab, current_date, 1)
        data = self.remove_last_candle_if_invalid(df)

        self.initial_df = data.copy()
        self.initial_df.index = pd.to_datetime(self.initial_df.index)
        self.initial_df.index = self.initial_df.index.tz_localize(None)
        self.initial_df["RSI"] = talib.RSI(self.initial_df['Close'], 2)
        self.initial_df["RSI"] = self.initial_df["RSI"].round(2)

        data.index = pd.to_datetime(data.index)
        data_high_low = self.apply_rsi_stoch_doji_fib(data)

        self.high_price_during_trading = data_high_low['High'].max()
        self.low_price_during_trading = data_high_low['Low'].min()
        n = min(60, len(data_high_low))
        for i in range(-n, 0) :
            current_candle = self.create_rsi_stoch_fib(data_high_low.iloc[i])
            self.current_candle = current_candle
            if current_candle.rsi >= 94:
                self.candles_above_94.append(self.current_candle)
            if current_candle.rsi <= 5:
                self.candles_below_5.append(self.current_candle)

            self.track_all_candles.append(current_candle)
        self.highest_candle = max(self.track_all_candles, key=lambda x: x.high)
        self.lowest_candle = min(self.track_all_candles, key=lambda x: x.low)
        while running:
            try:
                self.triggered_elliot_waves = False
                bot_start_time = time.time()
                next_run_time += timedelta(seconds=60)
                buy_condition = False
                short_condition = False
                sell_condition = False
                cover_condition = False
                self.close_only_once = False
                stop_loss = 0
                downward_candles_to_consider = 1
                upward_candles_to_consider = 1
                pre_condition_buy = False
                pre_condition_short = False
                converting_to_short = False
                converting_to_buy = False
                end_time = datetime.now()
                interval_minutes = 1
                num_candles = 500
                total_time_span = timedelta(minutes=interval_minutes * num_candles)
                start_time = end_time - total_time_span
                helper = MarketDataHelper(api_key, app_secret, callback_url)
                current_date = datetime.today().strftime('%Y-%m-%d')
                df = helper.fetch_price_history(self.symbol_schwab, current_date, 1)
                data = self.remove_last_candle_if_invalid(df)
                self.initial_df = data.copy()
                self.initial_df.index = pd.to_datetime(self.initial_df.index)
                self.initial_df.index = self.initial_df.index.tz_localize(None)
                self.initial_df["RSI"] = talib.RSI(self.initial_df['Close'], 2)
                self.initial_df["RSI"] = self.initial_df["RSI"].round(2)

                data = self.apply_rsi_stoch_doji_fib(data)

                current_candle = self.create_rsi_stoch_fib(data.iloc[-1])
                self.current_candle = current_candle
                self.track_all_candles.append(current_candle)

                if self.current_candle.rsi >= 94:
                    self.candles_above_94.append(self.current_candle)
                if self.current_candle.rsi <= 5:
                    self.candles_below_5.append(self.current_candle)

                if not self.enable_trade_shorting:
                    self.cover_stop_limit = None

                if self.enable_trade_shorting and not self.enable_trade_buying:
                    if self.current_candle.rsi < 94 and self.current_candle.stoch_k < 100:
                        if self.current_candle.previous_rsi > 94 and self.current_candle.previous_stoch_k > 80:
                            if not self.cover_stop_limit:
                                self.cover_stop_limit = self.current_candle.previous_high
                            if self.cover_stop_limit and self.cover_stop_limit != self.current_candle.previous_high:
                                self.cover_stop_limit = self.current_candle.previous_high

                if not self.enable_trade_buying:
                    self.sell_stop_limit = None

                if self.enable_trade_buying and not self.enable_trade_shorting:
                    if self.current_candle.rsi > 5 and self.current_candle.stoch_k > 0:
                        if self.current_candle.previous_rsi < 5 and self.current_candle.previous_stoch_k < 20:
                            if not self.sell_stop_limit:
                                self.sell_stop_limit = self.current_candle.previous_low
                            if self.sell_stop_limit and self.sell_stop_limit != self.current_candle.previous_low:
                                self.sell_stop_limit = self.current_candle.previous_low

                if self.stop_loss_order_id:
                    status = self.order_api.get_order_by_order_id(self.stop_loss_order_id)
                    if status == 'CANCELLED':
                        logging.info(f"{self.symbol_ironbeam} :Stop Loss with order Id # {self.stop_loss_order_id} is cancelled")
                        self.stop_loss_order_id = None
                        logging.info("Closing Trade Manually")

                    if status == 'FILLED':
                        logging.info(f"{self.symbol_ironbeam} :Stop Loss with order Id # {self.stop_loss_order_id} is Filled")
                        self.stop_loss_order_id = None
                        self.profit_taking_or_stop_loss_candle = self.current_candle
                        self.close_due_to_stop_loss = True
                        logging.info("Stop Loss Order Executed By Broker")


                logging.info(f"Bot Id # {self.bot_id}, self.stop_loss_order_id # {self.stop_loss_order_id}, Symbol # {self.symbol_schwab} Current Candle # {self.current_candle}")
                logging.info(f"Bot Id # {self.bot_id}, Live Trading # {self.live_trading}, Buy Trading  # {self.enable_trade_buying} Sell Trading # {self.enable_trade_shorting}")


                if not self.in_trade:

                    if current_candle.fib == 44:
                        logging.info("Put Break Point")

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
                            logging.info(f"Date # {current_candle.date} :self.save_upward_swing_current # {self.save_upward_swing_current}")
                            logging.info(f"Date # {current_candle.date} :self.save_upward_swing_previous # {self.save_upward_swing_previous}")
                            if upward_swing_current.is_new_high and not short_condition:
                                converting_to_short, pre_condition_short = self.is_extreme_internal_swing_bearish_divergence_triggered(upward_swing_current, current_candle)
                                if converting_to_short:
                                    short_condition = True
                                    logging.info(f"Date # {current_candle.date} :Extreme Internal Swing Bearish Divergence Triggered Short Order At Candle {current_candle}")

                            if upward_swing_current.is_new_high and not short_condition and self.save_upward_swing_previous:
                                converting_to_short, pre_condition_short = self.is_extreme_external_swing_bearish_divergence_triggered(upward_swing_current, current_candle)
                                if converting_to_short:
                                    short_condition = True
                                    logging.info(f"Date # {current_candle.date} :Extreme External Swing Bearish Divergence Triggered Short Order At Candle {current_candle}")

                            if upward_swing_current.is_new_high and not short_condition:
                                converting_to_short, pre_condition_short = self.is_non_extreme_internal_bearish_divergence(upward_swing_current, current_candle)
                                if converting_to_short:
                                    short_condition = True
                                    logging.info(f"Date # {current_candle.date} :Non Extreme Internal Bearish Divergence Triggered Short Order At Candle {current_candle}")

                        if len(downward_swings) >= 1:
                            downward_swing_current = downward_swings[-1]
                            self.save_downward_swing_current = downward_swing_current
                            self.update_lower_candle(self.save_downward_swing_current)
                            logging.info(f"Date # {current_candle.date} :self.save_downward_swing_current # {self.save_downward_swing_current}")
                            logging.info(f"Date # {current_candle.date} :self.save_downward_swing_previous # {self.save_downward_swing_previous}")
                            if downward_swing_current.is_new_low and not buy_condition :
                                converting_to_buy, pre_condition_buy = self.is_extreme_internal_swing_bullish_divergence_triggered(downward_swing_current, current_candle)
                                if converting_to_buy:
                                    buy_condition = True
                                    logging.info(f"Date # {current_candle.date} :Extreme Internal Swing Bullish Divergence Triggered Buy Order At Candle {current_candle}")

                            if downward_swing_current.is_new_low and not buy_condition and self.save_downward_swing_previous:
                                converting_to_buy, pre_condition_buy = self.is_extreme_external_swing_bullish_divergence_triggered(downward_swing_current, current_candle)
                                if converting_to_buy:
                                    buy_condition = True
                                    logging.info(f"Date # {current_candle.date} :Extreme External Swing Bullish Divergence Triggered Buy Order At Candle {current_candle}")

                            if downward_swing_current.is_new_low and not buy_condition:
                                converting_to_buy, pre_condition_buy = self.is_non_extreme_internal_bullish_divergence(downward_swing_current, current_candle)
                                if converting_to_buy:
                                    buy_condition = True
                                    logging.info(f"Date # {current_candle.date} :Non Extreme Internal Bullish Divergence Triggered Buy Order At Candle {current_candle}")


                    if short_condition:
                        stop_loss = self.get_stop_loss(False)
                        self.update_converting_to_short()
                        logging.info(f"Date # {current_candle.date} :###################")
                    else:
                        short_condition = False

                    if buy_condition:
                        stop_loss = self.get_stop_loss(True)
                        self.update_converting_to_buy()
                        logging.info(f"Date # {current_candle.date} :###################")
                    else:
                        buy_condition = False

                if self.in_trade:

                    if self.buy_order:

                        if current_candle.fib == 232:
                            logging.info("Put Break Point")

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
                            logging.info(f"Date # {current_candle.date} :self.save_upward_swing_current # {self.save_upward_swing_current}")
                            logging.info(f"Date # {current_candle.date} :self.save_upward_swing_previous # {self.save_upward_swing_previous}")
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
                                                    logging.info(f"Date # {current_candle.date} :Pre-Condition  Bearish Internal Non-Extreme Divergence, when comparing current to previous swing, Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {self.save_upward_swing_previous.new_high_candle.date} , Origin RSI {self.save_upward_swing_previous.new_high_candle.rsi}, Origin STOCH_K  {self.save_upward_swing_previous.new_high_candle.stoch_k},  Origin STOCH_D  {self.save_upward_swing_previous.new_high_candle.stoch_d} , End Date {self.save_upward_swing_current.new_high_candle.date} , End RSI {self.save_upward_swing_current.new_high_candle.rsi}, End STOCH_K {self.save_upward_swing_current.new_high_candle.stoch_k}, End STOCH_D {self.save_upward_swing_current.new_high_candle.stoch_d}")
                                                    if current_candle.close < self.save_upward_swing_current.new_high_candle.close and current_candle.close <= self.save_upward_swing_current.new_high_candle.low:
                                                        converting_to_short = True
                                                        self.save_upward_swing_current.new_high_candle.divergence_used = True
                                                        self.update_divergence_used_in_memory(self.save_upward_swing_current.new_high_candle)
                                                        logging.info(f"Date # {current_candle.date} :Bearish Internal Non-Extreme Divergence, when comparing current to previous swing, Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {self.save_upward_swing_previous.new_high_candle.date} , Origin RSI {self.save_upward_swing_previous.new_high_candle.rsi}, Origin STOCH_K  {self.save_upward_swing_previous.new_high_candle.stoch_k},  Origin STOCH_D  {self.save_upward_swing_previous.new_high_candle.stoch_d} , End Date {self.save_upward_swing_current.new_high_candle.date} , End RSI {self.save_upward_swing_current.new_high_candle.rsi}, End STOCH_K {self.save_upward_swing_current.new_high_candle.stoch_k}, End STOCH_D {self.save_upward_swing_current.new_high_candle.stoch_d}")
                                                    self.add_divergence_info(False, False, converting_to_short, self.save_upward_swing_previous.new_high_candle, self.save_upward_swing_current.new_high_candle, False , False, self.save_upward_swing_previous, False, True )

                                if not pre_condition_short and self.save_upward_swing_current and self.save_upward_swing_previous:
                                    if self.save_upward_swing_previous.new_high_candle.close < self.save_upward_swing_current.new_high_candle.close and self.save_upward_swing_previous.new_high_candle.body > 0 and self.save_upward_swing_current.new_high_candle.body > 0:
                                        if self.save_upward_swing_previous.new_high_candle.high < self.save_upward_swing_current.new_high_candle.high:
                                            if not self.save_upward_swing_current.new_high_candle.divergence_used:
                                                if self.save_upward_swing_current.new_high_candle.rsi < self.save_upward_swing_previous.new_high_candle.rsi:
                                                    pre_condition_short = True
                                                    logging.info(f"Date # {current_candle.date} :Pre-Condition  Bearish Internal Non-Extreme Divergence, when comparing current to previous swing, Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {self.save_upward_swing_previous.new_high_candle.date} , Origin RSI {self.save_upward_swing_previous.new_high_candle.rsi}, End Date {self.save_upward_swing_current.new_high_candle.date} , End RSI {self.save_upward_swing_current.new_high_candle.rsi}")
                                                    if current_candle.close < self.save_upward_swing_current.new_high_candle.close and current_candle.close <= self.save_upward_swing_current.new_high_candle.low:
                                                        converting_to_short = True
                                                        self.save_upward_swing_current.new_high_candle.divergence_used = True
                                                        self.update_divergence_used_in_memory(self.save_upward_swing_current.new_high_candle)
                                                        logging.info(f"Date # {current_candle.date} :Bearish Internal Non-Extreme Divergence, when comparing current to previous swing, Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {self.save_upward_swing_previous.new_high_candle.date} , Origin RSI {self.save_upward_swing_previous.new_high_candle.rsi}, End Date {self.save_upward_swing_current.new_high_candle.date} , End RSI {self.save_upward_swing_current.new_high_candle.rsi}")
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
                                            logging.info(f"Date # {current_candle.date} :Pre-Condition  bullish Internal Non-Extreme Divergence, when comparing current to previous swing, Triggered with Current RSI is lower then Previous RSI and Below Candles Involved in Divergence # Origin Date {self.save_downward_swing_previous.new_low_candle.date} , Origin RSI {self.save_downward_swing_previous.new_low_candle.rsi}, Origin STOCH_K  {self.save_downward_swing_previous.new_low_candle.stoch_k},  Origin STOCH_D  {self.save_downward_swing_previous.new_low_candle.stoch_d} , End Date {self.save_downward_swing_current.new_low_candle.date} , End RSI {self.save_downward_swing_current.new_low_candle.rsi}, End STOCH_K {self.save_downward_swing_current.new_low_candle.stoch_k}, End STOCH_D {self.save_downward_swing_current.new_low_candle.stoch_d}")

                        if converting_to_short:
                            self.short_triggered_candle_two = current_candle
                            logging.info(f"Date # {current_candle.date} :First Divergence condition met for Short and waiting for the next candle to close below current candle {current_candle}")
                            converting_to_short = False
                            logging.info(f"Date # {current_candle.date} :###################")

                        if self.short_triggered_candle_two:
                            if current_candle.close < self.short_triggered_candle_two.close and current_candle.body < 0:
                                if self.sell_stop_limit:
                                    if current_candle.close < self.sell_stop_limit:
                                        converting_to_short = True
                                else:
                                    converting_to_short = True

                                logging.info(f"Date # {current_candle.date} :Second Condition Met for Short and Divergence At Candle {current_candle} close below self.short_triggered_candle_two {self.short_triggered_candle_two}")
                            else:
                                converting_to_short = False

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
                            logging.info("Put Break Point")

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
                            logging.info(f"Date # {current_candle.date} :self.save_downward_swing_current # {self.save_downward_swing_current}")
                            logging.info(f"Date # {current_candle.date} :self.save_downward_swing_previous # {self.save_downward_swing_previous}")

                            self.update_lower_candle(self.save_downward_swing_current)
                            if downward_swing_current.is_new_low:
                                # logging.info(f"Date # {current_candle.date} :downward_swing_current {downward_swing_current}")

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
                                                    logging.info(f"Date # {current_candle.date} :Pre-Condition  Bullish Internal Non-Extreme Divergence, when comparing current to previous swing,  Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {self.save_downward_swing_previous.new_low_candle.date} , Origin RSI {self.save_downward_swing_previous.new_low_candle.rsi}, Origin STOCH_K  {self.save_downward_swing_previous.new_low_candle.stoch_k},  Origin STOCH_D  {self.save_downward_swing_previous.new_low_candle.stoch_d} , End Date {self.save_downward_swing_current.new_low_candle.date} , End RSI {self.save_downward_swing_current.new_low_candle.rsi}, End STOCH_K {self.save_downward_swing_current.new_low_candle.stoch_k}, End STOCH_D {self.save_downward_swing_current.new_low_candle.stoch_d}")
                                                    if current_candle.close > self.save_downward_swing_current.new_low_candle.close and current_candle.close >= self.save_downward_swing_current.new_low_candle.high:
                                                        converting_to_buy = True
                                                        self.save_downward_swing_current.new_low_candle.divergence_used = True
                                                        self.update_divergence_used_in_memory(self.save_downward_swing_current.new_low_candle)
                                                        logging.info(f"Date # {current_candle.date} :Bullish Internal Non-Extreme Divergence, when comparing current to previous swing, Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {self.save_downward_swing_previous.new_low_candle.date} , Origin RSI {self.save_downward_swing_previous.new_low_candle.rsi}, Origin STOCH_K  {self.save_downward_swing_previous.new_low_candle.stoch_k},  Origin STOCH_D  {self.save_downward_swing_previous.new_low_candle.stoch_d} , End Date {self.save_downward_swing_current.new_low_candle.date} , End RSI {self.save_downward_swing_current.new_low_candle.rsi}, End STOCH_K {self.save_downward_swing_current.new_low_candle.stoch_k}, End STOCH_D {self.save_downward_swing_current.new_low_candle.stoch_d}")
                                                    self.add_divergence_info(True, False, converting_to_buy, self.save_downward_swing_previous.new_low_candle, self.save_downward_swing_current.new_low_candle, False , False, self.save_downward_swing_previous, False, True )

                                if not pre_condition_buy and not pre_condition_buy and self.save_downward_swing_current and self.save_downward_swing_previous:
                                    if self.save_downward_swing_previous.new_low_candle.close > self.save_downward_swing_current.new_low_candle.close:
                                        if self.save_downward_swing_previous.new_low_candle.low > self.save_downward_swing_current.new_low_candle.low:
                                            if not self.save_downward_swing_current.new_low_candle.divergence_used:
                                                if self.save_downward_swing_current.new_low_candle.rsi > self.save_downward_swing_previous.new_low_candle.rsi:
                                                    pre_condition_buy = True
                                                    logging.info(f"Date # {current_candle.date} :Pre-Condition  Bullish Internal Non-Extreme Divergence, when comparing current to previous swing, Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {self.save_downward_swing_previous.new_low_candle.date} , Origin RSI {self.save_downward_swing_previous.new_low_candle.rsi},  End Date {self.save_downward_swing_current.new_low_candle.date} , End RSI {self.save_downward_swing_current.new_low_candle.rsi}")
                                                    if current_candle.close > self.save_downward_swing_current.new_low_candle.close and current_candle.close >= self.save_downward_swing_current.new_low_candle.high:
                                                        converting_to_buy = True
                                                        self.save_downward_swing_current.new_low_candle.divergence_used = True
                                                        self.update_divergence_used_in_memory(self.save_downward_swing_current.new_low_candle)
                                                        logging.info(f"Date # {current_candle.date} :Bullish Internal Non-Extreme Divergence, when comparing current to previous swing, Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {self.save_downward_swing_previous.new_low_candle.date} , Origin RSI {self.save_downward_swing_previous.new_low_candle.rsi},  End Date {self.save_downward_swing_current.new_low_candle.date} , End RSI {self.save_downward_swing_current.new_low_candle.rsi}")
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
                                            logging.info(f"Date # {current_candle.date} :Pre-Condition  Bearish Internal Non-Extreme Divergence, when comparing current to previous swing, Triggered with Current RSI is greater then Previous RSI and Below Candles Involved in Divergence # Origin Date {self.save_upward_swing_previous.new_high_candle.date} , Origin RSI {self.save_upward_swing_previous.new_high_candle.rsi}, Origin STOCH_K  {self.save_upward_swing_previous.new_high_candle.stoch_k},  Origin STOCH_D  {self.save_upward_swing_previous.new_high_candle.stoch_d} , End Date {self.save_upward_swing_current.new_high_candle.date} , End RSI {self.save_upward_swing_current.new_high_candle.rsi}, End STOCH_K {self.save_upward_swing_current.new_high_candle.stoch_k}, End STOCH_D {self.save_upward_swing_current.new_high_candle.stoch_d}")

                        if converting_to_buy:
                            self.buy_triggered_candle_two = current_candle
                            converting_to_buy = False
                            logging.info(f"Date # {current_candle.date} :First Divergence condition met for Buy and waiting for the next candle to close below current candle {current_candle}")
                            logging.info(f"Date # {current_candle.date} :###################")


                        if self.buy_triggered_candle_two:
                            if current_candle.close > self.buy_triggered_candle_two.close:
                                if self.cover_stop_limit:
                                    if current_candle.close > self.cover_stop_limit:
                                        converting_to_buy = True
                                else:
                                    converting_to_buy = True
                                logging.info(f"Date # {current_candle.date} :Second Condition Met for Buy and Divergence At Candle {current_candle} close below self.buy_triggered_candle_two {self.buy_triggered_candle_two}")
                            else:
                                converting_to_buy = False

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
                    # Buy Order
                    if not self.in_trade and buy_condition:
                        try:
                            logging.info(f"{self.symbol_schwab} :Buy Order Reqeust In Progress")
                            stop_limit_price = float(stop_loss) - float(self.stop_loss_adjust)
                            if self.live_trading and self.enable_trade_buying:
                                self.order_api.submit_buy_sell_market_order(True, self.lot_size)
                                self.order_api.submit_stop_market_order(stop_limit_price, False,  self.lot_size)
                                self.stop_loss_order_id = self.order_api.stop_loss_order_id
                                self.insert_trade("BUY", self.current_candle.close, self.lot_size)
                            self.buy_order = True
                            self.in_trade = True
                            self.in_trade_candle = current_candle
                            logging.info(f"{self.symbol_ironbeam} :Placed Buy Order with Stop Limit {self.stop_loss}")
                        except Exception as e:
                            logging.error(("An error occurred while placing buy order: %s", e))

                    # Short Order
                    if not self.in_trade and short_condition:
                        try:
                            logging.info(f"{self.symbol_schwab} :Short Order Reqeust In Progress")
                            stop_limit_price = float(stop_loss) + float(self.stop_loss_adjust)
                            if self.live_trading and self.enable_trade_shorting:
                                self.order_api.submit_short_cover_market_order(True, self.lot_size)
                                self.order_api.submit_stop_market_order(stop_limit_price, True,  self.lot_size)
                                self.stop_loss_order_id = self.order_api.stop_loss_order_id
                                self.insert_trade("SELL", self.current_candle.close, self.lot_size)
                            self.short_order = True
                            self.in_trade = True
                            self.in_trade_candle = current_candle
                            logging.info(f"{self.symbol_ironbeam} :Placed Short Order with Stop Limit {self.stop_loss}")
                        except Exception as e:
                            logging.error(("An error occurred while placing short order: %s", e))

                    # Close Buy Order
                    if (~self.close_only_once) and self.buy_order:
                        if sell_condition:
                            logging.info(f"{self.symbol_schwab} :Close Buy Order In Progress self.close_only_once {self.close_only_once}, self.buy_order {self.buy_order}, self.stop_loss_order {self.stop_loss_order_id}, sell_condition {sell_condition}")
                            sell_condition = False
                            if self.live_trading and self.stop_loss_order_id and self.enable_trade_buying:
                                self.order_api.submit_cancel_order(self.stop_loss_order_id)
                                self.order_api.submit_buy_sell_market_order(False, self.lot_size)
                                self.stop_loss_order_id = None
                                self.insert_trade("SELL", self.current_candle.close, self.lot_size)
                            self.buy_order = False
                            self.in_trade = False
                            self.close_only_once = True
                            self.stop_loss_order_id = None
                            logging.info(f"Closed Buy Order")

                    # Close Short Order
                    if (~self.close_only_once) and self.short_order:
                        if cover_condition:
                            logging.info(f"{self.symbol_schwab} :Close Short Order In Progress self.close_only_once {self.close_only_once}, self.short_order {self.short_order}, self.stop_loss_order {self.stop_loss_order_id}, cover_condition {cover_condition}")
                            cover_condition = False
                            if self.live_trading and self.stop_loss_order_id and self.enable_trade_shorting:
                                self.order_api.submit_cancel_order(self.stop_loss_order_id)
                                self.order_api.submit_short_cover_market_order(False, self.lot_size)
                                self.stop_loss_order_id = None
                                self.insert_trade("BUY", self.current_candle.close, self.lot_size)
                            self.short_order = False
                            self.in_trade = False
                            self.close_only_once = True
                            self.stop_loss_order_id = None
                            logging.info(f"Closed Short Order")

                # Wait for 1 minute before next iteration

                logging.info(f"Bot Id # {self.bot_id}, self.stop_loss_order_id # {self.stop_loss_order_id}, Symbol # {self.symbol_schwab}, Current Trade Status # {self.in_trade} ,  Buy Trade # {self.buy_order} , Short order # {self.short_order} , Live Trading # {self.live_trading}")
                logging.info(f"Bot Id # {self.bot_id}, Live Trading # {self.live_trading}, Buy Trading  # {self.enable_trade_buying},  Sell Trading # {self.enable_trade_shorting}")
                self.update_bot_trade_status()

                sleep_time = (next_run_time - datetime.now()).total_seconds()
                if sleep_time > 0:
                    time.sleep(sleep_time)
            except Exception as e:
                logging.error(
                    f"Exception Current Candle {self.current_candle}, Bot Id # {self.bot_id}, "
                    f"Stop Loss Order # {self.stop_loss_order_id}, Symbol # {self.symbol_schwab}, "
                    f"Current Trade Status # {self.in_trade}, Buy Trade # {self.buy_order}, "
                    f"Short Order # {self.short_order}, Live Trading # {self.live_trading}"
                )
                logging.exception("Full Stack Trace:")  # Logs full traceback
                sleep_time = (next_run_time - datetime.now()).total_seconds()
                if sleep_time > 0:
                    time.sleep(sleep_time)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        logging.info("Usage: python trading_bot_strategy_one.py <bot_id>")
        sys.exit(1)

    bot_id = int(sys.argv[1])
    bot = TradingBot(bot_id)

    trade_thread = Thread(target=bot.run)
    command_thread = Thread(target=bot.listen_for_commands)

    trade_thread.start()
    command_thread.start()

    trade_thread.join()
    command_thread.join()