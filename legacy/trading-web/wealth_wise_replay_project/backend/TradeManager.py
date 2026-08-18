from types import SimpleNamespace
import logging

logging.basicConfig(filename="trading_bot.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class Order:
    def __init__(self, order_id, order_type, symbol, entry_price, quantity, status='FILLED'):
        self.order_id = order_id
        self.type = order_type
        self.symbol = symbol
        self.entry_price = entry_price
        self.quantity = quantity
        self.status = status
        self.unrealized_profit = 0  # Track unrealized profit
        self.exit_price = 0

class StopLossOrder:
    def __init__(self, order_id, linked_order_id, symbol, stop_loss_price, status='ACTIVE'):
        self.order_id = order_id
        self.linked_order_id = linked_order_id
        self.symbol = symbol
        self.stop_loss_price = stop_loss_price
        self.status = status

class TradeManager:
    def __init__(self):
        self.orders = {}  # Store all orders by order_id
        self.cash_balance = 100000  # Initial cash balance
        self.total_profit = 0


    def place_order(self, order_id, order_type, symbol, entry_price, quantity):
        if order_type == 'long' and entry_price * quantity > self.cash_balance:
            logging.info("Not enough cash to buy.")
            return None

        if order_type == 'long':
            self.cash_balance -= entry_price * quantity
        elif order_type == 'short':
            self.cash_balance += entry_price * quantity

        order = Order(order_id, order_type, symbol, entry_price, quantity)
        self.orders[order_id] = order

        logging.info(f"Placed {order_type.upper()} order: {order_id}, {quantity} {symbol} at {entry_price}")
        return order

    def update_profit_for_candle(self, order_id, current_price):
        """Update unrealized profit for each candle."""
        order = self.orders.get(order_id)
        if not order or order.status != 'FILLED':
            logging.info(f"No valid open order found with ID: {order_id}")
            return

        entry_price = order.entry_price
        quantity = order.quantity
        point_move = abs(current_price - entry_price)
        profit_per_contract = point_move * 50  # $50 per point
        unrealized_profit = 0
        if order.type == 'long':
            unrealized_profit = profit_per_contract * quantity if current_price > entry_price else -profit_per_contract * quantity
        elif order.type == 'short':
            unrealized_profit = profit_per_contract * quantity if current_price < entry_price else -profit_per_contract * quantity

        order.unrealized_profit = unrealized_profit
        logging.info(f"Updated {order.type} order: {order_id}, Current Price: {current_price}, Unrealized Profit: {unrealized_profit}")

    def place_stop_loss(self, stop_loss_id, linked_order_id, symbol, stop_loss_price):
        if linked_order_id not in self.orders:
            logging.info("Invalid linked order ID.")
            return None

        stop_loss_order = StopLossOrder(stop_loss_id, linked_order_id, symbol, stop_loss_price)
        self.orders[stop_loss_id] = stop_loss_order

        logging.info(f"Placed STOP-LOSS order: {stop_loss_id}, {symbol} at {stop_loss_price}")
        return stop_loss_order

    def close_order(self, order_id, exit_price):
        order = self.orders.get(order_id)
        order.exit_price = exit_price
        if not order or order.status != 'FILLED':
            logging.info(f"No valid open order found with ID: {order_id}")
            return False

        quantity = order.quantity
        entry_price = order.entry_price
        point_move = abs(exit_price - entry_price)
        profit_per_contract = point_move * 50  # $50 per point
        profit = 0
        if order.type == 'long':
            profit = profit_per_contract * quantity if exit_price > entry_price else -profit_per_contract * quantity
            self.cash_balance += exit_price * quantity
        elif order.type == 'short':
            profit = profit_per_contract * quantity if exit_price < entry_price else -profit_per_contract * quantity
            self.cash_balance -= exit_price * quantity

        self.total_profit += profit
        order.status = 'CLOSED'
        self.update_profit_for_candle(order_id, exit_price)
        logging.info(f"Closed {order.type} order: {order_id}, {order.symbol} at {exit_price}, Profit: {profit}")
        return order

    def update_stop_loss_status(self, stop_loss_id, new_status):
        if stop_loss_id in self.orders and isinstance(self.orders[stop_loss_id], StopLossOrder):
            self.orders[stop_loss_id].status = new_status
            logging.info(f"Updated STOP-LOSS order: {stop_loss_id}, New Status: {new_status}")
        else:
            logging.info(f"No valid STOP-LOSS order found with ID: {stop_loss_id}")

    def get_order(self, order_id):
        order = self.orders.get(order_id)
        if order:
            logging.info(f"Retrieved order: {order}")
            return order
        logging.info(f"No order found with ID: {order_id}")
        return None

    def show_summary(self):
        logging.info("\n--- Trade Summary ---")
        logging.info(f"Cash Balance: {self.cash_balance}")
        logging.info(f"Total Profit: {self.total_profit}")
        logging.info("\nOrders:")
        for order_id, order in self.orders.items():
            logging.info(f"ID: {order_id}, {vars(order)}")
