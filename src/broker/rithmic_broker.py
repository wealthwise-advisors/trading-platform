"""
Rithmic live broker adapter.

Wire-up steps:
1. Install pyrithmic:  pip install pyrithmic
2. Fill in config/credentials.yaml  (username, password, server_url)
3. Uncomment the import below and implement _connect().

Full pyrithmic docs: https://github.com/jacksonwoody/pyrithmic
"""

from loguru import logger

from .base_broker import BaseBroker, Fill, Order


class RithmicBroker(BaseBroker):
    """Thin adapter over pyrithmic (or R|API+) for live order execution."""

    def __init__(self, config: dict):
        self._config = config
        self._client = None   # pyrithmic.RithmicClient instance goes here
        self._fills: list[Fill] = []
        self._positions: dict[str, int] = {}
        logger.warning("RithmicBroker: not connected — call connect() before trading.")

    def connect(self):
        """
        Establish connection to Rithmic gateway.

        Example (pyrithmic):
            from pyrithmic import RithmicClient
            self._client = RithmicClient(
                user=self._config["username"],
                password=self._config["password"],
                server_url=self._config["server_url"],
            )
            self._client.connect()
        """
        raise NotImplementedError(
            "Wire up pyrithmic here. See docstring for instructions."
        )

    def disconnect(self):
        if self._client:
            # self._client.disconnect()
            self._client = None

    # ------------------------------------------------------------------
    # BaseBroker interface — all raise until wired up
    # ------------------------------------------------------------------

    def submit_order(self, order: Order) -> str:
        self._require_connection()
        raise NotImplementedError("Implement order submission via pyrithmic.")

    def cancel_order(self, order_id: str) -> bool:
        self._require_connection()
        raise NotImplementedError("Implement order cancellation via pyrithmic.")

    def get_position(self, symbol: str) -> int:
        self._require_connection()
        raise NotImplementedError("Implement position query via pyrithmic.")

    def get_cash(self) -> float:
        self._require_connection()
        raise NotImplementedError("Implement balance query via pyrithmic.")

    def get_fills(self) -> list[Fill]:
        return list(self._fills)

    def _require_connection(self):
        if self._client is None:
            raise RuntimeError("Not connected to Rithmic. Call connect() first.")
