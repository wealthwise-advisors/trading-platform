import sys
import time
import redis
import logging
import signal
import psycopg2
from psycopg2 import sql
from threading import Thread

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
    def __init__(self, bot_id):
        self.bot_id = bot_id
        self.current_trade = "NONE"
        self.symbol_ironbeam = None
        self.symbol_schwab = None
        self.lot_size = 1
        self.strategy = "Strategy_One"
        self.live_trading = False

        # Credentials from CustomerDetails
        self.username = None
        self.password_hash = None
        self.api_key = None

        # Connect to the database
        self.db_conn = psycopg2.connect(**DB_PARAMS)
        self.db_conn.autocommit = True
        self.cursor = self.db_conn.cursor()

        # Load bot configuration
        self.load_bot_configuration()
        self.in_trade = None
        self.buy_order = None
        self.short_order = None
        self.bulk_buy_order = None
        self.bulk_short_order = None

    def update_bot_stop_trade_status(self):
        """Update bot's trade status in the database"""
        self.current_trade = "NONE"
        update_query = sql.SQL("UPDATE bots SET current_trade_status = %s WHERE bot_id = %s")
        self.cursor.execute(update_query, (self.current_trade, self.bot_id))
        update_query = sql.SQL("UPDATE bots SET current_bot_trade_status = %s WHERE bot_id = %s")
        self.cursor.execute(update_query, (self.current_trade, self.bot_id))

    def update_bot_trade_status(self):
        """Update bot's trade status in the database"""
        if self.in_trade:

            if self.buy_order:
                self.current_trade = "BUY"
            if self.short_order:
                self.current_trade = "SELL"

            update_query = sql.SQL("UPDATE bots SET current_bot_trade_status = %s WHERE bot_id = %s")
            self.cursor.execute(update_query, (self.current_trade, self.bot_id))

    def load_bot_configuration(self):
        """Fetch bot configuration and customer credentials based on bot_id"""
        query = sql.SQL("""
            SELECT b.symbol_ironbeam, b.symbol_schwab, b.lot_size, b.strategy, b.live_trading,
                   c.username, c.password_hash, c.api_key
            FROM bots b
            JOIN customer_details c ON b.customer_id = c.customer_id
            WHERE b.bot_id = %s
        """)
        self.cursor.execute(query, (self.bot_id,))
        bot_data = self.cursor.fetchone()

        if bot_data:
            self.symbol_ironbeam, self.symbol_schwab, self.lot_size, self.strategy, self.live_trading, self.username, self.password_hash, self.api_key = bot_data
            logging.info(f"Bot {self.bot_id} initialized with:")
            logging.info(f"Symbols: ({self.symbol_ironbeam}, {self.symbol_schwab}), Lot Size: {self.lot_size}, Strategy: {self.strategy}, Live Trading: {self.live_trading}")
            logging.info(f"Credentials: Username={self.username}, API Key={self.api_key}")
        else:
            logging.error(f"Bot {self.bot_id} not found in the database!")

    def update_trade_status(self, trade_type):
        if trade_type == "BUY":
            self.in_trade = True
            self.buy_order = True
            self.short_order = False
        if trade_type == "SELL":
            self.in_trade = True
            self.buy_order = False
            self.short_order = True
        """Update bot's trade status in the database"""
        self.current_trade = trade_type
        update_query = sql.SQL("UPDATE bots SET current_trade_status = %s WHERE bot_id = %s")
        self.cursor.execute(update_query, (self.current_trade, self.bot_id))

        logging.info(f"Bot {self.bot_id}: Trade status updated to {trade_type}")

    def insert_trade(self, trade_type, price, lot_size):
        """Insert a new trade record into the trades table"""
        insert_query = sql.SQL("""
            INSERT INTO trades (bot_id, symbol, lot_size, trade_type, price, status)
            VALUES (%s, %s, %s, %s, %s, 'EXECUTED')
        """)
        self.cursor.execute(insert_query, (self.bot_id, self.symbol_ironbeam, lot_size, trade_type, price))

        logging.info(f"Bot {self.bot_id}: Trade inserted - {trade_type} at price {price}")

    def execute_trade(self, action, lot_size):
        """Executes trade actions and updates the database"""
        if action in ["BUY", "SELL", "BULK_BUY", "BULK_SELL", "FORCE_BUY", "FORCE_SELL"]:
            price = self.get_market_price()
            self.update_trade_status(action)
            self.insert_trade(action, price, lot_size)

        elif action == "FLAT" or action == "BULK_FLAT":
            self.update_trade_status("NONE")

        elif action == "FLIP":
            new_trade = "BUY" if self.current_trade == "SELL" else "SELL"
            price = self.get_market_price()
            self.update_trade_status(new_trade)
            self.insert_trade(new_trade, price, lot_size)

    def get_market_price(self):
        """Mock function to fetch the latest market price"""
        return round(1000 + (self.bot_id % 10) * 5, 2)  # Simulated price for testing

    def update_live_trading_status(self, status):
        """Update live_trading status in database"""
        update_query = sql.SQL("UPDATE bots SET live_trading = %s WHERE bot_id = %s")
        self.cursor.execute(update_query, (status, self.bot_id))
        logging.info(f"Bot {self.bot_id}: Database updated - live_trading set to {status}")

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
                    self.update_live_trading_status(True)

                elif action == "DISABLE_LIVE_TRADING":
                    self.live_trading = False
                    logging.info(f"Bot {self.bot_id}: Live trading DISABLED")
                    self.update_live_trading_status(False)

                # Handle Standard Trading Actions
                elif action in ["BUY", "SELL", "FLAT", "FLIP"]:
                    self.execute_trade(action, self.lot_size)

                elif action == "BULK_FLAT":
                    self.execute_trade(action, self.lot_size)
                    self.bulk_buy_order = None
                    self.bulk_short_order = None

                # Handle BULK_BUY and BULK_SELL
                elif action.startswith("BULK_BUY:"):
                    lot_size = int(action.split(":")[1])
                    self.bulk_buy_order = True
                    logging.info(f"Bot {self.bot_id}: Executing BULK_BUY with {lot_size} lots")
                    self.execute_trade("BUY", lot_size)

                elif action == "FORCE_BUY":
                    logging.info(f"Bot {self.bot_id}: Executing FORCE BUY")
                    self.execute_trade("BUY", self.lot_size)

                elif action == "FORCE_SELL":
                    logging.info(f"Bot {self.bot_id}: Executing FORCE SELL")
                    self.execute_trade("SELL", self.lot_size)

                elif action.startswith("BULK_SELL:"):
                    lot_size = int(action.split(":")[1])
                    self.bulk_short_order = True
                    logging.info(f"Bot {self.bot_id}: Executing BULK_SELL with {lot_size} lots")
                    self.execute_trade("SELL", lot_size)

                # Stop Bot Execution
                elif action == "STOP":
                    logging.info(f"Bot {self.bot_id} stopping...")
                    self.update_bot_stop_trade_status()
                    global running
                    running = False
                    break  # Exit loop to stop the bot

    def run(self):
        """Main trading loop"""
        logging.info(f"Bot {self.bot_id} started!")
        while running:
            self.update_bot_trade_status()
            time.sleep(5)
            logging.info(f"Bot {self.bot_id}: In Trade = {self.in_trade}, Buy Trade = {self.buy_order}, Short Trade = {self.short_order}, Bulk Buy Trade = {self.bulk_buy_order}, Bulk Short Trade = {self.bulk_short_order}")

        logging.info(f"Bot {self.bot_id} stopped.")

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
