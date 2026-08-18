
class SchwabOrderManager:
    def __init__(self, schwab_client, schwab_account_hash, symbol, log_callback):
        self.schwab_client = schwab_client
        self.schwab_account_hash = schwab_account_hash
        self.symbol = symbol
        self.log_to_main = log_callback
        self.stop_loss_order_id = None

    def submit_buy_sell_market_order(self, is_buy, lot_size):
        instruction = "BUY" if is_buy else "SELL"
        order = self._create_order("MARKET", instruction, lot_size)
        self._execute_order(order, "Market")

    def submit_short_cover_market_order(self, is_short, lot_size):
        instruction = "SELL_SHORT" if is_short else "BUY_TO_COVER"
        order = self._create_order("MARKET", instruction, lot_size)
        self._execute_order(order, "Market")

    def submit_stop_market_order(self, stop_loss, is_buy, lot_size):
        instruction = "BUY_TO_COVER" if is_buy else "SELL"
        order = self._create_order("STOP", instruction, lot_size, stop_price=stop_loss)
        self._execute_order(order, "Stop Market")

    def submit_cancel_order(self, order_id):
        response = self.schwab_client.order_cancel(self.schwab_account_hash, order_id)
        self.log_to_main(f"{self.symbol} : Successfully Canceled Order with ID # {order_id}")

    def get_order_by_order_id(self, order_id):
        return self._get_order_details(order_id).get("status")

    def get_order_details_order_id(self, order_id):
        return self._get_order_details(order_id)

    def _create_order(self, order_type, instruction, lot_size, stop_price=None):
        order = {
            "orderType": order_type,
            "session": "NORMAL",
            "duration": "DAY",
            "orderStrategyType": "SINGLE",
            "orderLegCollection": [
                {
                    "instruction": instruction,
                    "quantity": lot_size,
                    "instrument": {
                        "symbol": self.symbol,
                        "assetType": "EQUITY"
                    }
                }
            ]
        }
        if stop_price is not None:
            order["stopPrice"] = stop_price
        return order

    def _execute_order(self, order, order_type):
        self.log_to_main(f"{self.symbol} : Submitting Live {order_type} {order}")
        response = self.schwab_client.order_place(self.schwab_account_hash, order)
        order_id = response.headers.get('location', '/').split('/')[-1]
        self.log_to_main(f"{self.symbol} : {order_type} Order Response {self.get_order_details_order_id(order_id)}")
        if order_type == "Stop Market":
            self.stop_loss_order_id = order_id
            self.log_to_main(f"{self.symbol} : Stop market order ID {self.stop_loss_order_id}")

    def _get_order_details(self, order_id):
        return self.schwab_client.order_details(self.schwab_account_hash, order_id).json()


# Main method to test SchwabOrderManager
# if __name__ == "__main__":
#
#     # def log_message(message):
#     #     print(message)
#     #
#     # api_key = 'REDACTED__see_legacy_REDACTIONS_md'
#     # app_secret = 'REDACTED__see_legacy_REDACTIONS_md'
#     # callback_url = 'https://127.0.0.1:8182'
#     # schwab_client = Client(api_key, app_secret, callback_url, verbose=True)
#     # linked_accounts = schwab_client.account_linked().json()
#     # schwab_account_hash = linked_accounts[0].get('hashValue')
#     # order_api = SchwabOrderManager(schwab_client,  schwab_account_hash, "AMD", log_message)
#     # order_api.submit_cancel_order(1002718851757)
#     # #order_api.submit_buy_sell_market_order(False, 1)
#     # #order_api.submit_stop_market_order(80, False, 1)
#     # order_api.submit_short_cover_market_order(False, 1)
#     # #order_api.submit_stop_market_order(120, True, 1)



