import json

from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
import logging
import redis
import subprocess
from threading import Thread
from sqlalchemy.orm import sessionmaker, scoped_session
import os
import signal
import platform
import datetime
import time
import sys



app = Flask(__name__, static_folder="static")  # Ensures Flask recognizes 'static/' as a base static folder
CORS(app, supports_credentials=True)

# PostgreSQL Database Configuration
app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://wealth_user:wealth_pass@localhost/wealth_wise"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


BACKTEST_OUTPUT_DIR = os.path.join(os.getcwd(), "static", "backtests")  # Absolute Path
os.makedirs(BACKTEST_OUTPUT_DIR, exist_ok=True)  # Ensure Directory Exists

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Redis Client for Pub/Sub
redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Ensure the database session is created within the application context
with app.app_context():
    SessionLocal = scoped_session(sessionmaker(bind=db.engine))

# Dictionary to Track Running Bots
running_bots = {}

# Map strategies to different bot scripts
STRATEGY_BOT_MAPPING = {
    "Strategy_One": "iron_beam_trading_bot_one.py",
    "Strategy_Two": "iron_beam_trading_bot_two.py",
    "Strategy_Three": "iron_beam_trading_bot_three.py",
    "Strategy_Four": "iron_beam_trading_bot_four.py"
}

# Map strategies to backtesting scripts
BACKTESTING_SCRIPTS = {
    "Strategy_One": "backtesting_strategy_one.py",
    "Strategy_Two": "backtesting_strategy_two.py",
    "Strategy_Three": "backtesting_strategy_three.py",
    "Strategy_Four": "backtesting_strategy_four.py",
    "Strategy_Five": "backtesting_strategy_five.py"


}

# STRATEGY_BOT_MAPPING = {
#     "Strategy_One": "trading_bot_strategy_one.py",
#     "Strategy_Two": "trading_bot_strategy_two.py",
# }

log_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
# File Handler (Logs to backend.log)
file_handler = logging.FileHandler("backend.log")
file_handler.setFormatter(log_formatter)

# Stream Handler (Logs to Console)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)

# Get Root Logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)  # Set logging level
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Suppress Flask request logs but keep warnings/errors
werkzeug_logger = logging.getLogger("werkzeug")
werkzeug_logger.setLevel(logging.WARNING)  # Hide API request logs




# ---------------- Database Models ----------------
class CustomerDetails(db.Model):
    __tablename__ = "customer_details"
    customer_id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(255), unique=True, nullable=False)

    # Address Fields
    street = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    country = db.Column(db.String(100), nullable=False)
    postal_code = db.Column(db.String(20), nullable=False)

    # User Fields
    username = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    api_key = db.Column(db.Text, nullable=False)

    # Timestamp
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())

class Bot(db.Model):
    __tablename__ = "bots"
    bot_id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer_details.customer_id"), nullable=False)
    bot_name = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(10), nullable=False, default="STOPPED")  # STOPPED or RUNNING
    live_trading = db.Column(db.Boolean, default=False)
    symbol_ironbeam = db.Column(db.String(50), nullable=False)  # Ironbeam Symbol
    symbol_schwab = db.Column(db.String(50), nullable=False)    # Schwab Symbol
    lot_size = db.Column(db.Integer, nullable=False)
    current_trade_status = db.Column(db.String(10), nullable=False, default="NONE")  # BUY, SELL, or NONE
    current_bot_trade_status = db.Column(db.String(10), nullable=False, default="NONE")  # BUY, SELL, or NONE
    strategy = db.Column(db.String(20), nullable=False, default="Strategy_One")  # Strategy_One or Strategy_Two
    stop_loss_adjust = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)  # New column
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())

class Trade(db.Model):
    __tablename__ = "trades"
    trade_id = db.Column(db.Integer, primary_key=True)
    bot_id = db.Column(db.Integer, db.ForeignKey("bots.bot_id"), nullable=False)
    symbol = db.Column(db.String(50), nullable=False)
    lot_size = db.Column(db.Integer, nullable=False)
    trade_type = db.Column(db.String(10), nullable=False)
    price = db.Column(db.Numeric(18, 8), nullable=False)
    status = db.Column(db.String(50), nullable=False, default="PENDING")
    executed_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())

# ---------------- Bot Process Management ----------------
def start_bot(bot_id, strategy):
    """Start the trading bot with a specific strategy."""
    bot_script = STRATEGY_BOT_MAPPING.get(strategy)
    if bot_script:
        process = subprocess.Popen(["python", bot_script, str(bot_id)])
        running_bots[bot_id] = process
        logging.info(f"Started {strategy} bot for Bot ID: {bot_id} and {bot_script}")
    else:
        logging.warning(f"No bot script found for strategy: {strategy}")

def stop_bot(bot_id):
    """Stop the trading bot process, ensuring cross-platform compatibility."""
    if bot_id in running_bots:
        process = running_bots[bot_id]

        # Send termination signal
        process.terminate()

        try:
            process.wait(timeout=5)  # Wait up to 5 seconds
        except subprocess.TimeoutExpired:
            logging.warning(f"Bot {bot_id} did not terminate in time, attempting force kill...")

            if platform.system() == "Windows":
                # Windows uses taskkill instead of os.kill
                subprocess.run(["taskkill", "/F", "/PID", str(process.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                os.kill(process.pid, signal.SIGKILL)  # Linux/Mac force kill

        del running_bots[bot_id]
        logging.info(f"Stopped bot for Bot ID: {bot_id}")
    else:
        logging.warning(f"Bot {bot_id} is not running.")




# ---------------- Customer CRUD API Routes ----------------

@app.route("/api/customers", methods=["GET"])
def get_customers():
    """Fetch all customers"""
    customers = CustomerDetails.query.all()
    return jsonify([
        {
            "customer_id": c.customer_id,
            "customer_name": c.customer_name,
            "street": c.street,
            "city": c.city,
            "state": c.state,
            "country": c.country,
            "postal_code": c.postal_code,
            "username": c.username,
            "api_key": c.api_key
        }
        for c in customers
    ])

@app.route("/api/customers", methods=["POST"])
def add_customer():
    """Add a new customer"""
    data = request.json
    new_customer = CustomerDetails(**data)
    db.session.add(new_customer)
    db.session.commit()
    return jsonify({"customer_id": new_customer.customer_id}), 201

@app.route("/api/customers/<int:customer_id>", methods=["GET"])
def get_customer(customer_id):
    """Get a specific customer"""
    customer = db.session.get(CustomerDetails, customer_id)
    if not customer:
        return jsonify({"error": "Customer not found"}), 404

    return jsonify({
        "customer_id": customer.customer_id,
        "customer_name": customer.customer_name,
        "street": customer.street,
        "city": customer.city,
        "state": customer.state,
        "country": customer.country,
        "postal_code": customer.postal_code,
        "username": customer.username,
        "api_key": customer.api_key
    })

@app.route("/api/customers/<int:customer_id>", methods=["PUT"])
def update_customer(customer_id):
    """Update a customer"""
    customer = db.session.get(CustomerDetails, customer_id)
    if not customer:
        return jsonify({"error": "Customer not found"}), 404

    data = request.json
    customer.customer_name = data.get("customer_name", customer.customer_name)
    customer.street = data.get("street", customer.street)
    customer.city = data.get("city", customer.city)
    customer.state = data.get("state", customer.state)
    customer.country = data.get("country", customer.country)
    customer.postal_code = data.get("postal_code", customer.postal_code)
    customer.username = data.get("username", customer.username)
    customer.api_key = data.get("api_key", customer.api_key)

    db.session.commit()
    return jsonify({"message": "Customer updated successfully"}), 200

@app.route("/api/customers/<int:customer_id>", methods=["DELETE"])
def delete_customer(customer_id):
    """Delete a customer"""
    customer = db.session.get(CustomerDetails, customer_id)
    if not customer:
        return jsonify({"error": "Customer not found"}), 404

    try:
        db.session.delete(customer)
        db.session.commit()
        return jsonify({"message": f"Customer {customer_id} deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to delete customer: {str(e)}"}), 500

# ---------------- Bot CRUD API Routes ----------------

@app.route("/api/bots", methods=["POST"])
def add_bot():
    """Create a new trading bot."""
    data = request.json
    required_fields = ["bot_name", "customer_id", "symbol_ironbeam", "symbol_schwab", "lot_size", "live_trading", "strategy"]

    # Validate required fields
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    new_bot = Bot(
        bot_name=data["bot_name"],
        customer_id=data["customer_id"],
        symbol_ironbeam=data["symbol_ironbeam"],
        symbol_schwab=data["symbol_schwab"],
        lot_size=data["lot_size"],
        live_trading=data["live_trading"],
        strategy=data["strategy"],
        stop_loss_adjust=data.get("stop_loss_adjust", 0.00)
    )

    with SessionLocal() as session:
        session.add(new_bot)
        session.commit()
        return jsonify({"bot_id": new_bot.bot_id}), 201


@app.route("/api/bots/<int:bot_id>", methods=["GET"])
def get_bot(bot_id):
    """Retrieve a specific bot."""
    with SessionLocal() as session:
        bot = session.get(Bot, bot_id)
        if not bot:
            return jsonify({"error": "Bot not found"}), 404

        customer = session.get(CustomerDetails, bot.customer_id)
        customer_name = customer.customer_name if customer else "N/A"

        return jsonify({
            "bot_id": bot.bot_id,
            "bot_name": bot.bot_name,
            "customer_id": bot.customer_id,
            "customer_name": customer_name,
            "symbol_ironbeam": bot.symbol_ironbeam,
            "symbol_schwab": bot.symbol_schwab,
            "lot_size": bot.lot_size,
            "live_trading": bot.live_trading,
            "strategy": bot.strategy,
            "stop_loss_adjust": float(bot.stop_loss_adjust)
        })


@app.route("/api/bots", methods=["GET"])
def get_bots():
    """Retrieve all bots."""
    with SessionLocal() as session:
        bots = session.query(Bot).all()
        result = []

        for bot in bots:
            customer = session.get(CustomerDetails, bot.customer_id)
            customer_name = customer.customer_name if customer else "N/A"

            result.append({
                "bot_id": bot.bot_id,
                "bot_name": bot.bot_name,
                "customer_id": bot.customer_id,
                "customer_name": customer_name,
                "symbol_ironbeam": bot.symbol_ironbeam,
                "symbol_schwab": bot.symbol_schwab,
                "lot_size": bot.lot_size,
                "live_trading": bot.live_trading,
                "status": bot.status,
                "current_trade_status": bot.current_trade_status,
                "current_bot_trade_status": bot.current_bot_trade_status,
                "strategy": bot.strategy,
                "stop_loss_adjust": float(bot.stop_loss_adjust)
            })

        return jsonify(result)


@app.route("/api/bots/<int:bot_id>", methods=["PUT"])
def update_bot(bot_id):
    """Update bot details."""
    data = request.json
    with SessionLocal() as session:
        bot = session.get(Bot, bot_id)
        if not bot:
            return jsonify({"error": "Bot not found"}), 404


        # Update bot details
        bot.bot_name = data.get("bot_name", bot.bot_name)
        bot.symbol_ironbeam = data.get("symbol_ironbeam", bot.symbol_ironbeam)
        bot.symbol_schwab = data.get("symbol_schwab", bot.symbol_schwab)
        bot.lot_size = data.get("lot_size", bot.lot_size)
        bot.live_trading = data.get("live_trading", bot.live_trading)
        bot.strategy = data.get("strategy", bot.strategy)
        bot.stop_loss_adjust = data.get("stop_loss_adjust", bot.stop_loss_adjust)  # Handle new column

        session.commit()
        return jsonify({"message": "Bot updated successfully"}), 200


@app.route("/api/bots/<int:bot_id>", methods=["DELETE"])
def delete_bot(bot_id):
    """Delete a bot."""
    with SessionLocal() as session:
        bot = session.get(Bot, bot_id)
        if not bot:
            return jsonify({"error": "Bot not found"}), 404

        session.delete(bot)
        session.commit()
        return jsonify({"message": f"Bot {bot_id} deleted successfully"}), 200

@app.route('/api/bots/action', methods=['POST'])
def bot_action():
    """Handle bot actions: START, STOP, BUY, SELL, FLAT, FLIP, BULK_BUY, BULK_SELL, ENABLE_LIVE_TRADING, DISABLE_LIVE_TRADING."""
    data = request.json
    action = data.get("action")
    bot_ids = data.get("bot_ids", [])
    lot_size = data.get("lot_size", 0)  # Default 0 for bulk actions

    if not bot_ids:
        return jsonify({"error": "No bots selected"}), 400

    with SessionLocal() as session:
        logging.info(f"Action Received {action}")
        if action == "START":
            bots = session.query(Bot).filter(Bot.bot_id.in_(bot_ids)).all()
            started_bots = []

            # Get current time and calculate the start time for the next minute
            now = datetime.datetime.now()
            next_minute = (now + datetime.timedelta(minutes=1)).replace(second=0, microsecond=0)
            wait_time = (next_minute - now).total_seconds()

            logging.info(f"Waiting {wait_time:.2f} seconds to start bots at {next_minute.strftime('%H:%M:%S')}")

            time.sleep(wait_time)  # Delay execution until the start of the next minute

            for bot in bots:
                if bot.bot_id not in running_bots:
                    thread = Thread(target=start_bot, args=(bot.bot_id, bot.strategy))
                    thread.start()
                    started_bots.append(bot.bot_id)

            if started_bots:
                session.query(Bot).filter(Bot.bot_id.in_(started_bots)).update({"status": "RUNNING"}, synchronize_session=False)
                session.commit()
                logging.info(f"Started bots: {started_bots}")

            return jsonify({"message": f"Bots {started_bots} started successfully"}), 200
        elif action == "STOP":
            stopped_bots = []
            for bot_id in bot_ids:
                if bot_id in running_bots:
                    stop_bot(bot_id)
                    stopped_bots.append(bot_id)

            if stopped_bots:
                session.query(Bot).filter(Bot.bot_id.in_(stopped_bots)).update(
                    {
                        "status": "STOPPED",
                        "current_trade_status": "NONE",
                        "current_bot_trade_status": "NONE"
                    },
                    synchronize_session=False
                )
                session.commit()
                logging.info(f"Stopped bots: {stopped_bots}, set current_trade_status and current_bot_trade_status to NONE")

            return jsonify({"message": f"Bots {stopped_bots} stopped successfully"}), 200

        elif action in ["BUY", "SELL", "FLAT", "FLIP", "FORCE_BUY", "FORCE_SELL", "BULK_FLAT"]:
            for bot_id in bot_ids:
                redis_client.publish(f"bot:{bot_id}", action)  # Send command to bot via Redis
            return jsonify({"message": f"{action} executed for bots {bot_ids}"}), 200

        elif action in ["BULK_BUY", "BULK_SELL", "MOVE_FORWARD"]:
            if lot_size <= 0:
                return jsonify({"error": "Invalid lot size"}), 400

            for bot_id in bot_ids:
                redis_client.publish(f"bot:{bot_id}", f"{action}:{lot_size}")


            return jsonify({"message": f"{action} executed successfully with lot size {lot_size}"}), 200

        elif action == "ENABLE_LIVE_TRADING":
            session.query(Bot).filter(Bot.bot_id.in_(bot_ids)).update({"live_trading": True}, synchronize_session=False)
            session.commit()

            for bot_id in bot_ids:
                redis_client.publish(f"bot:{bot_id}", "ENABLE_LIVE_TRADING")  # Notify bot

            logging.info(f"Live trading ENABLED for bots {bot_ids}")
            return jsonify({"message": f"Live trading enabled for bots {bot_ids}"}), 200

        elif action == "DISABLE_LIVE_TRADING":
            session.query(Bot).filter(Bot.bot_id.in_(bot_ids)).update({"live_trading": False}, synchronize_session=False)
            session.commit()

            for bot_id in bot_ids:
                redis_client.publish(f"bot:{bot_id}", "DISABLE_LIVE_TRADING")  # Notify bot

            logging.info(f"Live trading DISABLED for bots {bot_ids}")
            return jsonify({"message": f"Live trading disabled for bots {bot_ids}"}), 200

    return jsonify({"error": "Invalid action"}), 400


# ---------------- Trade CRUD API Routes ----------------

@app.route("/api/trades", methods=["POST"])
def add_trade():
    """Create a new trade."""
    data = request.json
    required_fields = ["bot_id", "symbol", "lot_size", "trade_type", "price"]

    # Validate required fields
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    # Validate trade type
    if data["trade_type"] not in ["BUY", "SELL"]:
        return jsonify({"error": "Invalid trade type. Must be 'BUY' or 'SELL'"}), 400

    new_trade = Trade(
        bot_id=data["bot_id"],
        symbol=data["symbol"],
        lot_size=data["lot_size"],
        trade_type=data["trade_type"],
        price=data["price"],
        status="PENDING"
    )

    with SessionLocal() as session:
        session.add(new_trade)
        session.commit()
        return jsonify({"trade_id": new_trade.trade_id}), 201


@app.route("/api/trades/<int:trade_id>", methods=["GET"])
def get_trade(trade_id):
    """Retrieve a specific trade."""
    with SessionLocal() as session:
        trade = session.get(Trade, trade_id)
        if not trade:
            return jsonify({"error": "Trade not found"}), 404

        return jsonify({
            "trade_id": trade.trade_id,
            "bot_id": trade.bot_id,
            "symbol": trade.symbol,
            "lot_size": trade.lot_size,
            "trade_type": trade.trade_type,
            "price": str(trade.price),
            "status": trade.status,
            "executed_at": trade.executed_at.strftime("%Y-%m-%d %H:%M:%S")
        })


@app.route("/api/trades", methods=["GET"])
def get_trades():
    """Retrieve all trades."""
    logging.info(f"calling trades")
    with SessionLocal() as session:
        trades = session.query(Trade).all()
        result = [{
            "trade_id": t.trade_id,
            "bot_id": t.bot_id,
            "symbol": t.symbol,
            "lot_size": t.lot_size,
            "trade_type": t.trade_type,
            "price": str(t.price),
            "status": t.status,
            "executed_at": t.executed_at.strftime("%Y-%m-%d %H:%M:%S")
        } for t in trades]

        return jsonify(result)


@app.route("/api/trades/<int:trade_id>", methods=["PUT"])
def update_trade(trade_id):
    """Update trade details."""
    data = request.json
    with SessionLocal() as session:
        trade = session.get(Trade, trade_id)
        if not trade:
            return jsonify({"error": "Trade not found"}), 404

        # Update only provided fields
        trade.lot_size = data.get("lot_size", trade.lot_size)
        trade.status = data.get("status", trade.status)

        session.commit()
        return jsonify({"message": "Trade updated successfully"}), 200


@app.route("/api/trades/<int:trade_id>", methods=["DELETE"])
def delete_trade(trade_id):
    """Delete a trade."""

    with SessionLocal() as session:
        trade = session.get(Trade, trade_id)
        if not trade:
            return jsonify({"error": "Trade not found"}), 404

        session.delete(trade)
        session.commit()
        return jsonify({"message": f"Trade {trade_id} deleted successfully"}), 200

@app.route("/backtests/<path:filename>")
def serve_backtest_file(filename):
    """Serve backtest HTML files from static/backtests."""
    logging.info(f"serve_backtest_file: {filename}")
    file_path = os.path.join(BACKTEST_OUTPUT_DIR, filename)

    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404

    return send_from_directory(BACKTEST_OUTPUT_DIR, filename)


@app.route("/api/backtest", methods=["POST"])
def run_backtest():
    """Runs the backtesting script and returns the generated HTML filename."""
    logging.info(f"Calling run_backtest with params: {request.json}")

    data = request.json
    symbol = data.get("symbol")
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    start_time = data.get("start_time")
    end_time = data.get("end_time")
    lot_size = int(data.get("lot_size", 1))
    stop_loss_adjust = float(data.get("stop_loss_adjust", 0))
    strategy = data.get("strategy")
    interval = data.get("interval")

    if not all([symbol, start_date, end_date, start_time, end_time, lot_size, strategy, interval]):
        return jsonify({"error": "All parameters are required"}), 400

    if strategy not in BACKTESTING_SCRIPTS:
        return jsonify({"error": "Invalid strategy"}), 400

    backtesting_script = BACKTESTING_SCRIPTS[strategy]
    filename = f"{symbol}_backtest_{strategy}.html".lstrip("/")
    output_file = os.path.join(BACKTEST_OUTPUT_DIR, filename)

    # logging.info(f"Starting backtest using: {backtesting_script}")
    # logging.info(f"BACKTEST_OUTPUT_DIR: {BACKTEST_OUTPUT_DIR}")
    # logging.info(f"Filename: {filename}")
    # logging.info(f"Final Output Path: {output_file}")

    try:
        result = subprocess.run(
            [
                "python", backtesting_script, symbol, start_date, end_date, start_time, end_time,
                str(lot_size), str(stop_loss_adjust), output_file, interval
            ],
            check=True,
            capture_output=True,  #Capture errors for debugging
            text=True  # Ensure output is in string format
        )

        logging.info(f"Backtest successful: {result.stdout}")

        return jsonify({"backtest_url": filename}), 200  #Return only filename

    except subprocess.CalledProcessError as e:
        logging.error(f"Backtest failed: {e.stderr}")
        return jsonify({"error": f"Backtest failed: {e.stderr}"}), 500



# ---------------- Run the App ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
