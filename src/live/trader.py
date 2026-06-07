"""
Live trading loop — connects Rithmic data feed to a strategy.

Usage (once Rithmic is wired up):
    config = load_config()
    strategy = MACrossoverStrategy(fast=9, slow=21)
    trader = LiveTrader(strategy, symbol="ES", config=config)
    trader.start()   # blocks, Ctrl-C to stop
"""

import signal
import time
from typing import Optional
from loguru import logger

from ..strategies.base_strategy import BaseStrategy, SignalType
from ..broker.rithmic_broker import RithmicBroker


class LiveTrader:
    def __init__(self, strategy: BaseStrategy, symbol: str, config: dict, contracts: int = 1):
        self.strategy = strategy
        self.symbol = symbol
        self.config = config
        self.contracts = contracts
        self._running = False
        self.broker: Optional[RithmicBroker] = None

    def start(self):
        logger.info(f"Starting live trader: {self.strategy.name} on {self.symbol}")
        self.broker = RithmicBroker(config=self.config.get("rithmic", {}))

        # Register shutdown hook
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

        try:
            self.broker.connect()
        except NotImplementedError:
            logger.error(
                "RithmicBroker.connect() is not implemented yet. "
                "See src/broker/rithmic_broker.py for instructions."
            )
            return

        self._running = True
        self.strategy.reset()
        logger.info("Live trading loop started. Press Ctrl-C to stop.")

        # --- Main loop (replace with Rithmic callback/stream) ---
        while self._running:
            # TODO: replace time.sleep with Rithmic bar callback
            # Example:
            #   bar = self.broker.get_latest_bar(self.symbol)
            #   signal = self.strategy.on_bar(bars_history_df, bar, position)
            #   if signal: self._execute_signal(signal)
            time.sleep(1)

    def _execute_signal(self, signal_obj):
        from ..broker.base_broker import Order, OrderSide, OrderType
        pos = self.broker.get_position(self.symbol)

        if signal_obj.signal_type == SignalType.BUY and pos <= 0:
            if pos < 0:
                self.broker.submit_order(Order(
                    symbol=self.symbol, side=OrderSide.BUY,
                    quantity=abs(pos), order_type=OrderType.MARKET,
                ))
            self.broker.submit_order(Order(
                symbol=self.symbol, side=OrderSide.BUY,
                quantity=self.contracts, order_type=OrderType.MARKET,
            ))

        elif signal_obj.signal_type == SignalType.SELL and pos >= 0:
            if pos > 0:
                self.broker.submit_order(Order(
                    symbol=self.symbol, side=OrderSide.SELL,
                    quantity=pos, order_type=OrderType.MARKET,
                ))
            self.broker.submit_order(Order(
                symbol=self.symbol, side=OrderSide.SELL,
                quantity=self.contracts, order_type=OrderType.MARKET,
            ))

        elif signal_obj.signal_type == SignalType.CLOSE and pos != 0:
            side = OrderSide.SELL if pos > 0 else OrderSide.BUY
            self.broker.submit_order(Order(
                symbol=self.symbol, side=side,
                quantity=abs(pos), order_type=OrderType.MARKET,
            ))

    def _shutdown(self, *_):
        logger.info("Shutting down live trader…")
        self._running = False
        if self.broker:
            self.broker.disconnect()
