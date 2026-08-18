from datetime import datetime, timedelta
import copy
from typing import List
import pandas as pd
import time
import pandas_ta as ta
import signal
import logging
import redis
from rithmic.interfaces.order.order_types import FillStatus

from sideways_structure import SidewaysStructure

from get_market_data import MarketDataHelper
from iron_beam_authenticator import IronbeamAuthenticator
from order_api import OrderAPI
from swing_info import SwingInfo
from divergence_info import DivergenceInfo
import talib
from rsistochfibnumber import RsiStochFibNumber
import psycopg2
from psycopg2 import sql
from threading import Thread
import sys
from itertools import chain
from rithmic import RithmicOrderApi, RithmicEnvironment, RithmicHistoryApi


pd.options.mode.chained_assignment = None  # Disable the warning

# Configure logging
logging.basicConfig(filename="trading_bot.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Global flag for stopping bot gracefully
running = True

# Initialize Redis connection
redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Initialize Flask-SocketIO

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
ORDER_API = RithmicOrderApi(env=RithmicEnvironment.RITHMIC_LIVE)
HISTORY_API = RithmicHistoryApi(env=RithmicEnvironment.RITHMIC_LIVE, loop=ORDER_API.loop)
class TradingBot:

    def __init__(self,  bot_id):
        self.bot_id = bot_id
        self.symbol_ironbeam = None
        self.symbol_schwab = None
        self.lot_size = 1
        self.live_trading = False
        self.stop_loss_adjust = 200

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

        self.stop_loss_order = None
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
        self.enable_trade_buying = True
        self.enable_trade_shorting = True
        self.candles_above_94 = []
        self.candles_below_5 = []
        self.cover_stop_limit = None
        self.sell_stop_limit = None

        self.zig_zag_swing_collection = {}
        self.swing_collection = {}
        self.divergences_by_index = {}
        self.update = True
        self.buying_shorting_conditions = {}
        self.cancelled_buy_divergence = False
        self.cancelled_short_divergence = False
        self.initial_df = None


        self.latest_upward_swing_candle_from_10_leg = None
        self.latest_downward_swing_candle_from_10_leg = None

        self.cancelled_buy_divergence = False
        self.cancelled_short_divergence = False



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

        self.bulk_buy_stop_loss_order = None
        self.bulk_sell_stop_loss_order = None
        self.bulk_lot_size = None


        self.first_high_rsi_candle_during_buy = None
        self.first_low_rsi_candle_during_short = None

        self.second_high_rsi_candle_during_buy = None
        self.second_low_rsi_candle_during_short = None

        self.in_memory_short_divergence_candle = None
        self.in_memory_buy_divergence_candle = None
        self.in_memory_divergence_info = None
        self.manual_buy_short_trigger_candle = None
        self.buy_divergence_candle = None
        self.short_divergence_candle = None
        self.exchange_code = 'CME'


    def submit_market_order(self, is_buy, lot_size):
        order_id = '{0}_mkt_order'.format(datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3])
        market_order = ORDER_API.submit_market_order(
            order_id=order_id, security_code=self.symbol_ironbeam, exchange_code=self.exchange_code, quantity=lot_size, is_buy=is_buy
        )
        while market_order.in_market is False:
            time.sleep(0.1) # Order is in the market once we have a basket id from the Exchange

        while market_order.fill_status != FillStatus.FILLED:
            time.sleep(0.1)

        avg_px, qty = market_order.average_fill_price_qty

        logging.info(f"Successfully submitted market order {market_order}, avg_px # {avg_px}, qty # {qty}, order_id # {order_id}")
        logging.info(f"{self.symbol_ironbeam} : Filled Price  {market_order.fill_dataframe}")

    def submit_stop_market_order(self, stop_loss, is_buy, lot_size):
        order_id = '{0}_stop_mkt_order'.format(datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3])
        stop_loss_order = ORDER_API.submit_stop_market_order(
            order_id=order_id, security_code=self.symbol_ironbeam, exchange_code=self.exchange_code, quantity=lot_size, is_buy=is_buy, stop_loss=stop_loss
        )
        while stop_loss_order.in_market is False:
            time.sleep(0.1) # Order is in the market once we have a basket id from the Exchange

        while stop_loss_order.fill_status == FillStatus.FILLED:
            time.sleep(0.1)

        logging.info(f"{self.symbol_ironbeam} : Stop market order submitted {stop_loss_order}")
        return stop_loss_order

    def load_bot_configuration(self):
        """Fetch bot configuration and customer credentials based on bot_id"""
        query = sql.SQL("""
            SELECT b.symbol_ironbeam, b.symbol_schwab, b.lot_size, b.stop_loss_adjust, b.strategy, b.live_trading,
                   c.username, c.password_hash, c.api_key
            FROM bots b
            JOIN customer_details c ON b.customer_id = c.customer_id
            WHERE b.bot_id = %s
        """)
        self.cursor.execute(query, (self.bot_id,))
        bot_data = self.cursor.fetchone()

        if bot_data:
            self.symbol_ironbeam, self.symbol_schwab, self.lot_size, self.stop_loss_adjust, self.strategy, self.live_trading, self.username, self.password_hash, self.api_key = bot_data
            logging.info(f"Bot {self.bot_id} initialized with:")
            logging.info(f"Symbols: ({self.symbol_ironbeam}, {self.symbol_schwab}), Lot Size: {self.lot_size}, Strategy: {self.strategy}, Live Trading: {self.live_trading}")
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
                    if self.buy_order and not self.short_order:
                        self.submit_market_order(True, self.lot_size)
                        stop_limit_price = float(self.get_stop_loss(True)) - float(self.stop_loss_adjust)
                        self.stop_loss_order = self.submit_stop_market_order(stop_limit_price, False, self.lot_size)
                        self.insert_trade("BUY", self.current_candle.close, self.lot_size)
                    if self.short_order and not self.buy_order:
                        self.submit_market_order(False, self.lot_size)
                        stop_limit_price = float(self.get_stop_loss(False)) + float(self.stop_loss_adjust)
                        self.stop_loss_order = self.submit_stop_market_order(stop_limit_price, True, self.lot_size)
                        self.insert_trade("SELL", self.current_candle.close, self.lot_size)



                elif action == "DISABLE_LIVE_TRADING":
                    self.live_trading = False
                    logging.info(f"Bot {self.bot_id}: Live trading DISABLED")
                    # self.update_trade_status("NONE", True)

                # Handle Standard Trading Actions
                elif action == "FLIP":
                    logging.info(f"Bot {self.bot_id}: Executing FLIP")
                    flipped = False
                    if self.buy_order:
                        self.short_order = True
                        self.buy_order = False
                        flipped = True
                        self.in_trade_candle = self.current_candle
                        if self.live_trading and self.stop_loss_order:
                            ORDER_API.submit_cancel_order(self.stop_loss_order.order_id)
                            self.submit_market_order(False, self.lot_size)
                            self.insert_trade("SELL", self.current_candle.close, self.lot_size)
                        if self.live_trading:
                            self.submit_market_order(False, self.lot_size)
                            stop_limit_price = float(self.get_stop_loss(False)) + float(self.stop_loss_adjust)
                            self.insert_trade("SELL", self.current_candle.close, self.lot_size)
                            self.stop_loss_order = self.submit_stop_market_order(stop_limit_price, True, self.lot_size)
                        self.update_bot_trade_status()
                        logging.info(f"Bot Id # {self.bot_id}, self.stop_loss_order # {self.stop_loss_order}, Symbol # {self.symbol_schwab}, Current Trade Status # {self.in_trade} ,  Buy Trade # {self.buy_order} , Short order # {self.short_order} , Live Trading # {self.live_trading}")

                    if self.short_order and not flipped:
                        self.short_order = False
                        self.buy_order = True
                        self.in_trade_candle = self.current_candle
                        if self.live_trading and self.stop_loss_order:
                            ORDER_API.submit_cancel_order(self.stop_loss_order.order_id)
                            self.submit_market_order(True, self.lot_size)
                            self.insert_trade("BUY", self.current_candle.close, self.lot_size)
                        if self.live_trading:
                            self.submit_market_order(True, self.lot_size)
                            stop_limit_price = float(self.get_stop_loss(True)) - float(self.stop_loss_adjust)
                            self.stop_loss_order = self.submit_stop_market_order(stop_limit_price, False, self.lot_size)
                            self.insert_trade("BUY", self.current_candle.close, self.lot_size)
                        self.update_bot_trade_status()
                        logging.info(f"Bot Id # {self.bot_id}, self.stop_loss_order # {self.stop_loss_order}, Symbol # {self.symbol_schwab}, Current Trade Status # {self.in_trade} ,  Buy Trade # {self.buy_order} , Short order # {self.short_order} , Live Trading # {self.live_trading}")

                elif action == "FLAT":
                    logging.info(f"Bot {self.bot_id}: Executing FLAT")
                    if self.live_trading and self.in_trade:
                        if self.buy_order and self.stop_loss_order:
                            ORDER_API.submit_cancel_order(self.stop_loss_order.order_id)
                            self.submit_market_order(False, self.lot_size)
                            self.stop_loss_order = None
                            self.insert_trade("SELL", self.current_candle.close, self.lot_size, True)

                        if self.buy_order and self.bulk_buy_stop_loss_order and self.bulk_lot_size:
                            ORDER_API.submit_cancel_order(self.bulk_buy_stop_loss_order.order_id)
                            self.submit_market_order(False, self.bulk_lot_size)
                            self.bulk_buy_stop_loss_order = None
                            self.insert_trade("SELL", self.current_candle.close, self.bulk_lot_size, True)
                            self.bulk_lot_size = None

                        if self.short_order and self.stop_loss_order:
                            ORDER_API.submit_cancel_order(self.stop_loss_order.order_id)
                            self.submit_market_order(True, self.lot_size)
                            self.stop_loss_order = None
                            self.insert_trade("BUY", self.current_candle.close, self.lot_size, True)

                        if self.short_order and self.bulk_sell_stop_loss_order and self.bulk_lot_size:
                            ORDER_API.submit_cancel_order(self.bulk_sell_stop_loss_order.order_id)
                            self.submit_market_order(True, self.bulk_lot_size)
                            self.bulk_sell_stop_loss_order = None
                            self.insert_trade("BUY", self.current_candle.close, self.bulk_lot_size, True)
                            self.bulk_lot_size = None
                        logging.info(f"Bot Id # {self.bot_id}, self.stop_loss_order # {self.stop_loss_order}, self.bulk_sell_stop_loss_order # {self.bulk_sell_stop_loss_order},  Symbol # {self.symbol_schwab}, Current Trade Status # {self.in_trade} ,  Buy Trade # {self.buy_order} , Short order # {self.short_order} , Live Trading # {self.live_trading}")

                elif action == "BULK_FLAT":
                    logging.info(f"Bot {self.bot_id}: Executing BULK FLAT")
                    if self.live_trading and self.in_trade:

                        if self.buy_order and self.bulk_buy_stop_loss_order and self.bulk_lot_size:
                            ORDER_API.submit_cancel_order(self.bulk_buy_stop_loss_order.order_id)
                            self.submit_market_order(False, self.bulk_lot_size)
                            self.bulk_buy_stop_loss_order = None
                            self.insert_trade("SELL", self.current_candle.close, self.bulk_lot_size, True)
                            self.bulk_lot_size = None

                        if self.short_order and self.bulk_sell_stop_loss_order and self.bulk_lot_size:
                            ORDER_API.submit_cancel_order(self.bulk_sell_stop_loss_order.order_id)
                            self.submit_market_order(True, self.bulk_lot_size)
                            self.bulk_sell_stop_loss_order = None
                            self.insert_trade("BUY", self.current_candle.close, self.bulk_lot_size, True)
                            self.bulk_lot_size = None
                        logging.info(f"Bot Id # {self.bot_id}, self.stop_loss_order # {self.stop_loss_order}, self.bulk_sell_stop_loss # {self.bulk_sell_stop_loss_order},  Symbol # {self.symbol_schwab}, Current Trade Status # {self.in_trade} ,  Buy Trade # {self.buy_order} , Short order # {self.short_order} , Live Trading # {self.live_trading}")

                elif action == "BUY":
                    logging.info(f"Bot {self.bot_id}: Executing BUY")
                    if self.buy_order and not self.stop_loss_order and self.live_trading:
                        self.submit_market_order(True, self.lot_size)
                        stop_limit_price = float(self.get_stop_loss(True)) - float(self.stop_loss_adjust)
                        self.stop_loss_order = self.submit_stop_market_order(stop_limit_price, False, self.lot_size)
                        self.insert_trade("BUY", self.current_candle.close, self.lot_size)
                        logging.info(f"Bot Id # {self.bot_id}, self.stop_loss_order # {self.stop_loss_order},  Symbol # {self.symbol_schwab}, Current Trade Status # {self.in_trade} ,  Buy Trade # {self.buy_order} , Short order # {self.short_order} , Live Trading # {self.live_trading}")

                elif action == "FORCE_BUY":
                    logging.info(f"Bot {self.bot_id}: Executing FORCE_BUY")
                    if not self.in_trade and self.live_trading:
                        self.in_trade = True
                        self.buy_order = True
                        self.submit_market_order(True, self.lot_size)
                        stop_limit_price = float(self.get_stop_loss(True)) - float(self.stop_loss_adjust)
                        self.stop_loss_order = self.submit_stop_market_order(stop_limit_price, False, self.lot_size)
                        self.insert_trade("BUY", self.current_candle.close, self.lot_size)
                        self.update_bot_trade_status()
                        self.in_trade_candle = self.current_candle
                        logging.info(f"Bot Id # {self.bot_id}, Symbol # {self.symbol_schwab}, Current Trade Status # {self.in_trade} ,  Buy Trade # {self.buy_order} , Short order # {self.short_order} , Live Trading # {self.live_trading}")


                elif action == "SELL":
                    logging.info(f"Bot {self.bot_id}: Executing SELL")
                    if self.short_order and not self.stop_loss_order and self.live_trading:
                        self.submit_market_order(False, self.lot_size)
                        stop_limit_price = float(self.get_stop_loss(False)) + float(self.stop_loss_adjust)
                        self.stop_loss_order = self.submit_stop_market_order(stop_limit_price, True, self.lot_size)
                        self.insert_trade("SELL", self.current_candle.close, self.lot_size)
                        logging.info(f"Bot Id # {self.bot_id}, self.stop_loss_order # {self.stop_loss_order}, Symbol # {self.symbol_schwab}, Current Trade Status # {self.in_trade} ,  Buy Trade # {self.buy_order} , Short order # {self.short_order} , Live Trading # {self.live_trading}")

                elif action == "FORCE_SELL":
                    logging.info(f"Bot {self.bot_id}: Executing FORCE_SELL")
                    if not self.in_trade and self.live_trading:
                        self.in_trade = True
                        self.short_order = True
                        self.submit_market_order(False, self.lot_size)
                        stop_limit_price = float(self.get_stop_loss(False)) + float(self.stop_loss_adjust)
                        self.stop_loss_order = self.submit_stop_market_order(stop_limit_price, True, self.lot_size)
                        self.insert_trade("SELL", self.current_candle.close, self.lot_size)
                        self.update_bot_trade_status()
                        self.in_trade_candle = self.current_candle
                        logging.info(f"Bot Id # {self.bot_id}, Symbol # {self.symbol_schwab}, Current Trade Status # {self.in_trade} ,  Buy Trade # {self.buy_order} , Short order # {self.short_order} , Live Trading # {self.live_trading}")


                # Handle BULK_BUY and BULK_SELL
                elif action.startswith("BULK_BUY:"):
                    lot_size = int(action.split(":")[1])
                    logging.info(f"Bot {self.bot_id}: Executing BULK_BUY with {lot_size} lots")
                    if lot_size > 0 and  self.live_trading and self.in_trade:
                        if self.buy_order and self.stop_loss_order:
                            self.submit_market_order(True, lot_size)
                            stop_limit_price = float(self.get_stop_loss(True)) - float(self.stop_loss_adjust)
                            self.bulk_buy_stop_loss_order = self.submit_stop_market_order(stop_limit_price, False, lot_size)
                            self.bulk_lot_size = lot_size
                            self.insert_trade("BUY", self.current_candle.close, self.bulk_lot_size)
                            logging.info(f"Bot Id # {self.bot_id}, self.stop_loss_order # {self.stop_loss_order}, self.bulk_buy_stop_loss_order # {self.bulk_buy_stop_loss_order} ,  Symbol # {self.symbol_schwab}, Current Trade Status # {self.in_trade} ,  Buy Trade # {self.buy_order} , Short order # {self.short_order} , Live Trading # {self.live_trading}")


                elif action.startswith("BULK_SELL:"):
                    lot_size = int(action.split(":")[1])
                    logging.info(f"Bot {self.bot_id}: Executing BULK_SELL with {lot_size} lots")
                    if lot_size > 0 and self.live_trading and self.in_trade:
                        if self.short_order and self.stop_loss_order:
                            self.submit_market_order(False, lot_size)
                            stop_limit_price = float(self.get_stop_loss(False)) + float(self.stop_loss_adjust)
                            self.bulk_sell_stop_loss_order = self.submit_stop_market_order(stop_limit_price, True, lot_size)
                            self.bulk_lot_size = lot_size
                            self.insert_trade("SELL", self.current_candle.close, self.bulk_lot_size)
                            logging.info(f"Bot Id # {self.bot_id}, self.stop_loss_order # {self.stop_loss_order}, self.bulk_buy_stop_loss_order # {self.bulk_buy_stop_loss_order} ,  Symbol # {self.symbol_schwab}, Current Trade Status # {self.in_trade} ,  Buy Trade # {self.buy_order} , Short order # {self.short_order} , Live Trading # {self.live_trading}")

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

    def detect_top_bottom_consolidation(self, percentage_threshold=0.0009, min_swings=5, top_percentage=0.09):
        swings = self.create_swings_using_zig_zag_indicator_for_10_legs()
        if len(swings) < min_swings:
            return None

        temp_highs = [s.swing_high_price for s in swings[-min_swings:]]
        temp_lows = [s.swing_low_price for s in swings[-min_swings:]]
        temp_indices = [(s.start_index, s.end_index) for s in swings[-min_swings:]]

        high_min = min(temp_highs)
        high_max = max(temp_highs)
        low_min = min(temp_lows)
        low_max = max(temp_lows)
        avg_high = sum(temp_highs) / len(temp_highs)
        avg_low = sum(temp_lows) / len(temp_lows)

        # Ensure consolidation: Check if price range remains within the threshold (e.g., 0.02%)
        if ((high_max - high_min) / avg_high) > (percentage_threshold) or ((low_max - low_min) / avg_low) > (percentage_threshold):
            return None  # Reject if price movement is too wide

        # Find the highest and lowest swing in all swings
        highest_swing = max(s.swing_high_price for s in swings)
        lowest_swing = min(s.swing_low_price for s in swings)

        # Define thresholds for top and bottom consolidations
        top_threshold = highest_swing * (1 - top_percentage / 100)
        bottom_threshold = lowest_swing * (1 + top_percentage / 100)

        # Identify structure type
        if avg_high >= top_threshold:
            structure_type = "Top"
        elif avg_low <= bottom_threshold:
            structure_type = "Bottom"
        else:
            return None  # Not a top/bottom structure

        return SidewaysStructure(
            start_index=temp_indices[0][0],
            end_index=temp_indices[-1][1],
            high_min=high_min,
            high_max=high_max,
            low_min=low_min,
            low_max=low_max,
            num_swings=len(temp_highs),
            structure_type=structure_type
        )

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
        swing_collection = self.create_swings_using_zig_zag_indicator()
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

        if "02:01 PM" in self.current_candle.date:
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
            return filtered_divergences[-1] if filtered_divergences else None

        return divergences[-1] if divergences else None

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
                        if current_candle.close > downward_swing_current.new_low_candle.high:
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
                    if current_candle.close > downward_swing_current.new_low_candle.high:
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
                        if current_candle.close < upward_swing_current.new_high_candle.low:
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
                    if current_candle.close < upward_swing_current.new_high_candle.low:
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
                        if current_candle.close > downward_swing_current.new_low_candle.high:
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
                    if current_candle.close > downward_swing_current.new_low_candle.high:
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
                        if current_candle.close < upward_swing_current.new_high_candle.low:
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
                    if current_candle.close < upward_swing_current.new_high_candle.low:
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
                            if current_candle.close > lowest_price_candle.high:
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
                        if current_candle.close > lowest_price_candle.high:
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
                            if current_candle.close > lowest_price_candle.high:
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
                        if current_candle.close > lowest_price_candle.high:
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
                            if current_candle.close < highest_price_candle.low:
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
                        if current_candle.close < highest_price_candle.low:
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
                            if current_candle.close < highest_price_candle.low:
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
                        if current_candle.close < highest_price_candle.low:
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
                            if self.current_candle.close > closest_lowest_price_candle.high:
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
                                if self.current_candle.close > closest_lowest_price_candle.high:
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
                            if current_candle.close > downward_swing_current.new_low_candle.high and current_candle.close > lowest_rsi_candle_in_downward_swing.high:
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
                            if self.current_candle.close < closest_highest_price_candle.low:
                                converting_to_short = True
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
                                if self.current_candle.close < closest_highest_price_candle.low:
                                    converting_to_short = True
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
                            if current_candle.close < self.save_upward_swing_current.new_high_candle.low:
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
                    if current_candle.close > downward_swing_current.new_low_candle.high:
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
                    if current_candle.close < upward_swing_current.new_high_candle.low:
                        time_diff = abs(highest_rsi_candle_in_upward_swing.datetime - upward_swing_current.new_high_candle.datetime)
                        if time_diff.total_seconds() > 2 * 60:
                            self.add_candles_short_side = [candle for candle in self.track_all_candles_during_buy if candle.datetime >= upward_swing_current.new_high_candle.datetime]
                            converting_to_short = True
                            upward_swing_current.new_high_candle.divergence_used = True
                            self.update_divergence_used_in_memory(upward_swing_current.new_high_candle)
                            self.short_divergence_candle = self.get_candle_by_index(upward_swing_current.new_high_candle.index)
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
        self.first_high_rsi_candle_during_buy = None

        self.buy_divergence_candle = None

        self.in_memory_short_divergence_candle = None
        self.in_memory_buy_divergence_candle = None
        self.in_memory_divergence_info = None

        if self.second_high_rsi_candle_during_buy:
            self.first_high_rsi_candle_during_buy = self.second_high_rsi_candle_during_buy
            self.second_high_rsi_candle_during_buy = None

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

        self.short_divergence_candle = None
        self.in_memory_short_divergence_candle = None
        self.in_memory_buy_divergence_candle = None
        self.in_memory_divergence_info = None
        self.first_low_rsi_candle_during_short = None

        if self.second_low_rsi_candle_during_short:
            self.first_low_rsi_candle_during_short = self.second_low_rsi_candle_during_short
            self.second_low_rsi_candle_during_short = None

    def update_divergence_used_in_memory(self, update_candle):
        for candle in self.track_all_candles:
            if candle.datetime == update_candle.datetime:
                candle.divergence_used = True

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
                                if self.current_candle.close < self.save_upward_swing_current.new_high_candle.close and self.current_candle.close <= self.save_upward_swing_current.new_high_candle.low:
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
                            if self.current_candle.close < self.save_upward_swing_current.new_high_candle.close and self.current_candle.close <= self.save_upward_swing_current.new_high_candle.low:
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
                                if self.current_candle.close < self.save_upward_swing_current.new_high_candle.close and self.current_candle.close <= self.save_upward_swing_current.new_high_candle.low:
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
                            if self.current_candle.close < self.save_upward_swing_current.new_high_candle.close and self.current_candle.close <= self.save_upward_swing_current.new_high_candle.low:
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
                                if self.current_candle.close > self.save_downward_swing_current.new_low_candle.close and self.current_candle.close >= self.save_downward_swing_current.new_low_candle.high:
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
                            if self.current_candle.close > self.save_downward_swing_current.new_low_candle.close and self.current_candle.close >= self.save_downward_swing_current.new_low_candle.high:
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
                                if self.current_candle.close > self.save_downward_swing_current.new_low_candle.close and self.current_candle.close >= self.save_downward_swing_current.new_low_candle.high:
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
                            if self.current_candle.close > self.save_downward_swing_current.new_low_candle.close and self.current_candle.close >= self.save_downward_swing_current.new_low_candle.high:
                                converting_to_buy = True
                                self.save_downward_swing_current.new_low_candle.divergence_used = True
                                self.update_divergence_used_in_memory(self.save_downward_swing_current.new_low_candle)
                                self.buy_divergence_candle = self.get_candle_by_index(self.save_downward_swing_current.new_low_candle.index)
                            self.add_divergence_info(True, False, converting_to_buy, self.save_downward_swing_previous.new_low_candle, self.save_downward_swing_current.new_low_candle, False , True, self.save_downward_swing_current, False, True )

        if not converting_to_buy and not pre_condition_buy:
            converting_to_buy, pre_condition_buy = self.is_non_extreme_internal_bullish_divergence_only_pre_condition(self.save_downward_swing_current, self.current_candle)

        return converting_to_buy, pre_condition_buy

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

    def check_all_candle_high_low_conditions(self):
        #UP
        if self.current_candle.high >= self.current_candle.std_second_top_price:
            self.candle_touched_sd_high = self.current_candle
            self.candle_touched_rsi_low = None
            self.candle_touched_k_low = None
            self.candle_touched_d_low = None
            #self.low_sd_rsi_k_red_candle = None
        if self.current_candle.rsi >= self.high_rsi_limit:
            self.candle_touched_rsi_high = self.current_candle
        if self.current_candle.stoch_k >= self.high_k_limit:
            self.candle_touched_k_high= self.current_candle
        if self.current_candle.stoch_d >= self.high_d_limit:
            self.candle_touched_d_high= self.current_candle
        if (self.current_candle.high >= self.current_candle.std_second_top_price and self.current_candle.body > 0 and
                self.current_candle.rsi >= self.high_rsi_limit and
                (self.current_candle.stoch_k >= self.high_k_limit or self.current_candle.stoch_d >= self.high_d_limit)):
            self.high_sd_rsi_k_green_candle = self.current_candle

        #DOWN
        if self.current_candle.low <= self.current_candle.std_second_bottom_price:
            self.candle_touched_sd_low = self.current_candle
            self.candle_touched_rsi_high = None
            self.candle_touched_k_high = None
            self.candle_touched_d_high = None
            #self.high_sd_rsi_k_green_candle = None
        if self.current_candle.rsi <= self.low_rsi_limit:
            self.candle_touched_rsi_low = self.current_candle
        if self.current_candle.stoch_k <= self.high_k_limit:
            self.candle_touched_k_low= self.current_candle
        if self.current_candle.stoch_d <= self.low_d_limit:
            self.candle_touched_d_low= self.current_candle
        if (self.current_candle.low <= self.current_candle.std_second_bottom_price and self.current_candle.body < 0 and
                self.current_candle.rsi <= self.low_rsi_limit and
                (self.current_candle.stoch_k <= self.high_k_limit or self.current_candle.stoch_d <= self.low_d_limit)):
            self.low_sd_rsi_k_red_candle = self.current_candle

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
            self.check_all_candle_high_low_conditions()
            if current_candle.rsi >= 94:
                self.candles_above_94.append(self.current_candle)
            if current_candle.rsi <= 5:
                self.candles_below_5.append(self.current_candle)

            self.track_all_candles.append(current_candle)
        self.highest_candle = max(self.track_all_candles, key=lambda x: x.high)
        self.lowest_candle = min(self.track_all_candles, key=lambda x: x.low)
        while running:
            try:
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
                self.check_all_candle_high_low_conditions()
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

                if self.stop_loss_order:
                    self.stop_loss_order = ORDER_API.get_order_by_order_id(self.stop_loss_order.order_id)
                    if self.stop_loss_order and self.stop_loss_order.cancelled:
                        logging.info(f"{self.symbol_ironbeam} :Stop Loss with order Id # {self.stop_loss_order.order_id} is cancelled")
                        self.stop_loss_order = None
                        logging.info("Closing Trade Manually")

                    if self.stop_loss_order and self.stop_loss_order.fill_status == FillStatus.FILLED:
                        logging.info(f"{self.symbol_ironbeam} :Stop Loss with order Id # {self.stop_loss_order.order_id} is cancelled")
                        self.stop_loss_order = None
                        logging.info("Closing Trade Manually")

                logging.info(f"Bot Id {self.bot_id}, self.stop_loss_order # {self.stop_loss_order}, Symbol # {self.symbol_schwab} Current Candle # {self.current_candle}")
                self.latest_upward_swing_candle_from_10_leg = self.get_latest_upward_swing_candle_from_10_leg()
                self.latest_downward_swing_candle_from_10_leg = self.get_latest_downward_swing_candle_from_10_leg()


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

                    if short_condition:
                        stop_loss = self.get_stop_loss(False)
                        self.update_converting_to_short()
                        self.add_helper_messages("First Divergence condition met for Short and Shorted, This is First Trade")
                        self.add_helper_messages(f"Divergence condition met for Short And Short Divergence Candle Used Start # {self.real_short_divergence_candle.start_candle.index.strftime('%I:%M %p')}, End # {self.real_short_divergence_candle.end_candle.index.strftime('%I:%M %p')}")

                    if buy_condition:
                        stop_loss = self.get_stop_loss(True)
                        self.update_converting_to_buy()
                        self.add_helper_messages("First Divergence condition met for Buy and Bought, This is First Trade")
                        self.add_helper_messages(f"Divergence condition met for Buy And Buy Divergence Candle Used Start # {self.real_buy_divergence_candle.start_candle.index.strftime('%I:%M %p')}, End # {self.real_buy_divergence_candle.end_candle.index.strftime('%I:%M %p')}")

                if self.in_trade:

                    if self.buy_order:

                        if "09:36 AM" in self.current_candle.date:
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
                                                self.save_upward_swing_current.previous_swing_info = self.save_upward_swing_previous
                                                self.save_upward_swing_previous = copy.deepcopy(self.save_upward_swing_current)
                                                self.save_upward_swing_current = upward_swing
                                                self.update_higher_candle(self.save_upward_swing_current)
                                                self.add_or_update_swing(self.save_upward_swing_current.datetime, self.save_upward_swing_current)


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




                        if converting_to_short:
                            divergence_info = self.get_divergence_info(self.current_candle.index , "SHORT")
                            time_difference = abs(divergence_info.start_candle.index - divergence_info.end_candle.index)
                            if time_difference < timedelta(minutes=30):
                                if not self.is_extreme_violation(divergence_info):
                                    self.add_helper_messages(f"Divergence condition met for Short And Short Divergence Candle Used Start # {divergence_info.start_candle.index.strftime('%I:%M %p')}, End # {divergence_info.end_candle.index.strftime('%I:%M %p')}")
                                    self.add_helper_messages(f"Short Divergence Candle used # {self.short_divergence_candle.index.strftime('%I:%M %p')}")
                                else:
                                    converting_to_short = False
                                    self.remove_divergence_info(self.current_candle.index , divergence_info)
                            else:
                                converting_to_short = False
                                self.remove_divergence_info(self.current_candle.index , divergence_info)



                        if not converting_to_short:
                            converting_to_short, pre_condition_short = self.is_artificial_bearish_divergence()
                            if converting_to_short:
                                self.short_divergence_candle = self.second_high_rsi_candle_during_buy
                                self.add_helper_messages(f"Artificial Short Divergence created between {self.first_high_rsi_candle_during_buy.index.strftime('%I:%M %p')} and {self.second_high_rsi_candle_during_buy.index.strftime('%I:%M %p')}")

                        if not converting_to_short:
                            divergence_info = self.get_latest_pre_condition_divergence("SHORT")
                            if divergence_info and not self.is_extreme_violation(divergence_info):
                                time_difference = abs(divergence_info.start_candle.index - divergence_info.end_candle.index)
                                if time_difference < timedelta(minutes=30):
                                    close_time_difference = None
                                    highest_price_close = self.get_highest_close_price_between_dates(divergence_info.end_candle.index, self.current_candle.index)
                                    if highest_price_close:
                                        close_time_difference = abs(divergence_info.end_candle.index - highest_price_close.index)
                                    if self.current_candle.close < divergence_info.end_candle.low or (highest_price_close and self.current_candle.close < highest_price_close.low and close_time_difference < timedelta(minutes=5)):
                                        converting_to_short = True
                                        divergence_info.end_candle.divergence_used = True
                                        self.update_divergence_used_in_memory(divergence_info.end_candle)
                                        self.short_divergence_candle = self.get_candle_by_index(divergence_info.end_candle.index)
                                        if highest_price_close:
                                            self.short_divergence_candle = self.get_candle_by_index(highest_price_close.index)
                                        self.add_helper_messages(f"Divergence condition met for Short And Short Divergence Candle Used Start : {divergence_info.start_candle.index.strftime('%I:%M %p')} End : {divergence_info.end_candle.index.strftime('%I:%M %p')}")


                        if not converting_to_short:
                            if not self.in_memory_divergence_info:
                                self.in_memory_divergence_info = self.get_latest_divergence("SHORT")

                            if  self.in_memory_divergence_info:
                                # Check if any highest price candle is present
                                highest_price_candle = self.get_highest_price_between_dates_above_divergence_end_candle(self.in_memory_divergence_info.end_candle.index, self.current_candle.index)
                                if not highest_price_candle:
                                    if self.current_candle.close <  self.in_memory_divergence_info.end_candle.low and self.current_candle.body > 0:
                                        self.in_memory_short_divergence_candle = self.current_candle

                            if self.in_memory_short_divergence_candle:
                                if self.current_candle.close < self.in_memory_short_divergence_candle.low:
                                    if self.buy_divergence_candle and not self.buy_divergence_candle.is_extreme_buy_sell:
                                        converting_to_short = True
                                        self.add_helper_messages(f"Shorted  because current candle closed below Short Divergence candle  {self.in_memory_short_divergence_candle.index.strftime('%I:%M %p')}")
                                        self.add_helper_messages(f"This is second artificial divergence trigger because it didn't close below latest short divergence candle Start : {self.in_memory_divergence_info.start_candle.index.strftime('%I:%M %p')}, End : {self.in_memory_divergence_info.end_candle.index.strftime('%I:%M %p')}")
                                        self.short_divergence_candle = self.in_memory_short_divergence_candle
                                    if  self.buy_divergence_candle and self.buy_divergence_candle.is_extreme_buy_sell:
                                        if self.current_candle.close < self.buy_divergence_candle.low:
                                            converting_to_short = True
                                            self.add_helper_messages(f"Shorted  because current candle closed below Short Divergence candle  {self.in_memory_short_divergence_candle.index.strftime('%I:%M %p')}")
                                            self.add_helper_messages(f"This is second artificial divergence trigger because it didn't close below latest short divergence candle Start : {self.in_memory_divergence_info.start_candle.index.strftime('%I:%M %p')}, End : {self.in_memory_divergence_info.end_candle.index.strftime('%I:%M %p')}")
                                            self.short_divergence_candle = self.in_memory_short_divergence_candle


                        if self.buy_divergence_candle and not converting_to_short:
                            if self.current_candle.close < self.buy_divergence_candle.low:
                                converting_to_short = True
                                self.add_helper_messages(f"Shorted  because current candle closed below Buy Divergence candle  {self.buy_divergence_candle.index.strftime('%I:%M %p')}")
                                self.short_divergence_candle = self.get_candle_by_index(self.buy_divergence_candle.index)


                        if self.current_candle.rsi < 94 and self.current_candle.previous_rsi > 94 and not self.second_high_rsi_candle_during_buy:
                            self.first_high_rsi_candle_during_buy = self.get_candle_by_index(self.current_candle.previous_index)


                        if not converting_to_short and self.first_high_rsi_candle_during_buy and self.first_high_rsi_candle_during_buy.index > self.in_trade_candle.index:
                            if self.current_candle.close < self.first_high_rsi_candle_during_buy.low and self.current_candle.rsi< 5:
                                converting_to_short = True
                                self.add_helper_messages(f"Shorted  because current candle closed below highest rsi candle   {self.first_high_rsi_candle_during_buy.index.strftime('%I:%M %p')}")
                                self.short_divergence_candle =  self.first_high_rsi_candle_during_buy
                                self.short_divergence_candle.is_extreme_buy_sell = True

                        if converting_to_short:
                            sell_condition = True
                            buy_condition = False
                            stop_loss = self.get_stop_loss(False)
                            short_condition = True
                            self.update_converting_to_short()


                        self.track_all_candles_during_buy.append(current_candle)

                    if self.short_order:

                        if "09:51 AM" in self.current_candle.date:
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
                                                self.save_downward_swing_current.previous_swing_info = self.save_downward_swing_previous
                                                self.save_downward_swing_previous = copy.deepcopy(self.save_downward_swing_current)
                                                self.save_downward_swing_current = downward_swing
                                                self.update_lower_candle(self.save_downward_swing_current)
                                                self.add_or_update_swing(self.save_downward_swing_current.datetime, self.save_downward_swing_current)

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



                        converting_to_short, pre_condition_short = self.check_short_divergence_during_short()




                        if not pre_condition_buy:
                            converting_to_buy, pre_condition_buy = self.check_buy_divergence_during_short()


                        if converting_to_buy and self.real_buy_divergence_candle:
                            if self.real_buy_divergence_candle.end_candle.index < self.in_trade_candle.index:
                                converting_to_buy = False
                                self.remove_divergence_info(self.current_candle.index , self.real_buy_divergence_candle)
                            # if converting_to_buy and self.real_buy_divergence_candle.is_extreme:
                            #     lowest_price_candle = self.get_lowest_price_between_start_and_end_divergence(self.real_buy_divergence_candle.start_candle.index, self.real_buy_divergence_candle.end_candle.index, self.real_buy_divergence_candle.end_candle)
                            #     if lowest_price_candle:
                            #         converting_to_buy = False
                            #         self.remove_divergence_info(self.current_candle.index , "BUY")



                        if converting_to_buy:
                            divergence_info = self.get_divergence_info(self.current_candle.index , "BUY")
                            time_difference = abs(divergence_info.start_candle.index - divergence_info.end_candle.index)
                            if time_difference < timedelta(minutes=30):
                                if not self.is_extreme_violation(divergence_info):
                                    self.add_helper_messages(f"Divergence condition met for Buy , And Buy Divergence Candle used Start # {divergence_info.start_candle.index.strftime('%I:%M %p')}, End # {divergence_info.end_candle.index.strftime('%I:%M %p')}")
                                    self.add_helper_messages(f"Buy Divergence Candle used {self.buy_divergence_candle.index.strftime('%I:%M %p')}")
                                else:
                                    converting_to_buy = False
                                    self.remove_divergence_info(self.current_candle.index , divergence_info)
                            else:
                                converting_to_buy = False
                                self.remove_divergence_info(self.current_candle.index , divergence_info)




                        if not converting_to_buy:
                            converting_to_buy, pre_condition_buy = self.is_artificial_bullish_divergence()
                            if converting_to_buy:
                                self.buy_divergence_candle = self.second_low_rsi_candle_during_short
                                self.add_helper_messages(f"Artificial Buy Divergence created between {self.first_low_rsi_candle_during_short.index.strftime('%I:%M %p')} and {self.second_low_rsi_candle_during_short.index.strftime('%I:%M %p')}")

                        if not converting_to_buy:
                            divergence_info = self.get_latest_pre_condition_divergence("BUY")
                            if divergence_info and not self.is_extreme_violation(divergence_info):
                                time_difference = abs(divergence_info.start_candle.index - divergence_info.end_candle.index)
                                if time_difference < timedelta(minutes=30):
                                    close_time_difference = None
                                    lowest_price_close = self.get_lowest_price_close_between_dates(divergence_info.end_candle.index, self.current_candle.index)
                                    if lowest_price_close:
                                        close_time_difference = abs(divergence_info.end_candle.index - lowest_price_close.index)
                                    if self.current_candle.close > divergence_info.end_candle.high or (lowest_price_close and  self.current_candle.close > lowest_price_close.high and close_time_difference < timedelta(minutes=5)):
                                        converting_to_buy = True
                                        divergence_info.end_candle.divergence_used = True
                                        self.update_divergence_used_in_memory(divergence_info.end_candle)
                                        self.buy_divergence_candle = self.get_candle_by_index(divergence_info.end_candle.index)
                                        if lowest_price_close:
                                            self.buy_divergence_candle = self.get_candle_by_index(lowest_price_close.index)

                                        self.add_helper_messages(f"Divergence condition met for Buy , And  Buy Divergence Candle used  Start : {divergence_info.start_candle.index.strftime('%I:%M %p')}, End : {divergence_info.end_candle.index.strftime('%I:%M %p')}")



                        if not converting_to_buy:
                            if not self.in_memory_divergence_info:
                                self.in_memory_divergence_info = self.get_latest_divergence("BUY")

                            if  self.in_memory_divergence_info:
                                lowest_price_candle = self.get_lowest_price_between_dates_below_divergence_end_candle(self.in_memory_divergence_info.end_candle.index, self.current_candle.index)
                                if not lowest_price_candle:
                                    if self.current_candle.close >  self.in_memory_divergence_info.end_candle.high and self.current_candle.body < 0:
                                        self.in_memory_buy_divergence_candle = self.current_candle

                            if self.in_memory_buy_divergence_candle:
                                if self.current_candle.close > self.in_memory_buy_divergence_candle.high:
                                    if self.short_divergence_candle and not self.short_divergence_candle.is_extreme_buy_sell:
                                        converting_to_buy = True
                                        self.add_helper_messages(f"Bought  because current candle closed above Buy Divergence candle  {self.in_memory_buy_divergence_candle.index.strftime('%I:%M %p')}")
                                        self.add_helper_messages(f"This is second artificial divergence trigger because it didn't close below latest buy divergence candle Start : {self.in_memory_divergence_info.start_candle.index.strftime('%I:%M %p')}, End : {self.in_memory_divergence_info.end_candle.index.strftime('%I:%M %p')}")
                                        self.buy_divergence_candle = self.in_memory_buy_divergence_candle
                                    if  self.short_divergence_candle and self.short_divergence_candle.is_extreme_buy_sell:
                                        if current_candle.close > self.short_divergence_candle.high:
                                            converting_to_buy = True
                                            self.add_helper_messages(f"Bought  because current candle closed above Buy Divergence candle  {self.in_memory_buy_divergence_candle.index.strftime('%I:%M %p')}")
                                            self.add_helper_messages(f"This is second artificial divergence trigger because it didn't close below latest buy divergence candle Start : {self.in_memory_divergence_info.start_candle.index.strftime('%I:%M %p')}, End : {self.in_memory_divergence_info.end_candle.index.strftime('%I:%M %p')}")
                                            self.buy_divergence_candle = self.in_memory_buy_divergence_candle


                        if self.short_divergence_candle and not converting_to_buy:
                            if self.current_candle.close > self.short_divergence_candle.high:
                                converting_to_buy = True
                                self.add_helper_messages(f"Bought because current candle closed above Short Divergence candle  {self.short_divergence_candle.index.strftime('%I:%M %p')}")
                                self.buy_divergence_candle = self.get_candle_by_index(self.short_divergence_candle.index)

                        if self.current_candle.rsi > 5 and self.current_candle.previous_rsi < 5 and not self.second_low_rsi_candle_during_short:
                            self.first_low_rsi_candle_during_short = self.get_candle_by_index(self.current_candle.previous_index)

                        if not converting_to_buy and self.first_low_rsi_candle_during_short and self.first_low_rsi_candle_during_short.index > self.in_trade_candle.index:
                            if self.current_candle.close > self.first_low_rsi_candle_during_short.high and self.current_candle.rsi > 94:
                                converting_to_buy = True
                                self.add_helper_messages(f"Bought because current candle closed above lowest rsi candle   {self.first_low_rsi_candle_during_short.index.strftime('%I:%M %p')}")
                                self.buy_divergence_candle =  self.first_low_rsi_candle_during_short
                                self.buy_divergence_candle.is_extreme_buy_sell = True


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
                            logging.info(f"{self.symbol_ironbeam} :Buy Order Reqeust In Progress")
                            stop_limit_price = float(stop_loss) - float(self.stop_loss_adjust)
                            if self.live_trading and self.enable_trade_buying:
                                self.submit_market_order(True, self.lot_size)
                                self.stop_loss_order =self.submit_stop_market_order(stop_limit_price, False, self.lot_size)
                                self.insert_trade("BUY", self.current_candle.close, self.lot_size)
                            self.buy_order = True
                            self.in_trade = True
                            self.in_trade_candle = current_candle
                            logging.info(f"{self.symbol_ironbeam} :Placed Buy Order with Stop Limit {stop_limit_price}")
                        except Exception as e:
                            logging.error(("An error occurred while placing buy order: %s", e))

                    # Short Order
                    if not self.in_trade and short_condition:
                        try:
                            logging.info(f"{self.symbol_ironbeam} :Short Order Reqeust In Progress")
                            stop_limit_price = float(stop_loss) + float(self.stop_loss_adjust)
                            if self.live_trading and self.enable_trade_shorting:
                                self.submit_market_order(False, self.lot_size)
                                self.stop_loss_order = self.submit_stop_market_order(stop_limit_price, True, self.lot_size)
                                self.insert_trade("SELL", self.current_candle.close, self.lot_size)
                            self.short_order = True
                            self.in_trade = True
                            self.in_trade_candle = current_candle
                            logging.info(f"{self.symbol_ironbeam} :Placed Short Order with Stop Limit {stop_limit_price}")
                        except Exception as e:
                            logging.error(("An error occurred while placing short order: %s", e))

                    # Close Buy Order
                    if (~self.close_only_once) and self.buy_order:
                        if sell_condition:
                            logging.info(f"{self.symbol_ironbeam} :Close Buy Order In Progress self.close_only_once {self.close_only_once}, self.buy_order {self.buy_order}, self.stop_loss_order {self.stop_loss_order}, sell_condition {sell_condition}")
                            sell_condition = False
                            if self.live_trading and self.stop_loss_order and self.enable_trade_buying:
                                self.submit_market_order(False, self.lot_size)
                                ORDER_API.submit_cancel_order(self.stop_loss_order.order_id)
                                self.insert_trade("SELL", self.current_candle.close, self.lot_size)
                            self.buy_order = False
                            self.in_trade = False
                            self.close_only_once = True
                            self.stop_loss_order = None
                            logging.info(f"Closed Buy Order")

                    # Close Short Order
                    if (~self.close_only_once) and self.short_order:
                        if cover_condition:
                            logging.info(f"{self.symbol_ironbeam} :Close Short Order In Progress self.close_only_once {self.close_only_once}, self.short_order {self.short_order}, self.stop_loss_order {self.stop_loss_order}, cover_condition {cover_condition}")
                            cover_condition = False
                            if self.live_trading and self.stop_loss_order and self.enable_trade_shorting:
                                self.submit_market_order(True, self.lot_size)
                                ORDER_API.submit_cancel_order(self.stop_loss_order.order_id)
                                self.insert_trade("BUY", self.current_candle.close, self.lot_size)
                            self.short_order = False
                            self.in_trade = False
                            self.close_only_once = True
                            self.stop_loss_order = None
                            logging.info(f"Closed Short Order")

                # Wait for 1 minute before next iteration

                logging.info(f"Bot Id # {self.bot_id}, self.stop_loss_order # {self.stop_loss_order} , Symbol # {self.symbol_schwab}, Current Trade Status # {self.in_trade} ,  Buy Trade # {self.buy_order} , Short order # {self.short_order} , Live Trading # {self.live_trading}")
                self.update_bot_trade_status()

                sleep_time = (next_run_time - datetime.now()).total_seconds()
                if sleep_time > 0:
                    time.sleep(sleep_time)
            except Exception as e:
                logging.error(
                    f"Exception Current Candle {self.current_candle}, Bot Id # {self.bot_id}, "
                    f"Stop Loss Order # {self.stop_loss_order}, Symbol # {self.symbol_schwab}, "
                    f"Current Trade Status # {self.in_trade}, Buy Trade # {self.buy_order}, "
                    f"Short Order # {self.short_order}, Live Trading # {self.live_trading}"
                )
                logging.exception("Full Stack Trace:")  # Logs full traceback
                sleep_time = (next_run_time - datetime.now()).total_seconds()
                if sleep_time > 0:
                    time.sleep(sleep_time)



if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python trading_bot_strategy_one.py <bot_id>")
        sys.exit(1)

    bot_id = int(sys.argv[1])
    bot = TradingBot(bot_id)

    trade_thread = Thread(target=bot.run)
    command_thread = Thread(target=bot.listen_for_commands)

    trade_thread.start()
    command_thread.start()

    trade_thread.join()
    command_thread.join()