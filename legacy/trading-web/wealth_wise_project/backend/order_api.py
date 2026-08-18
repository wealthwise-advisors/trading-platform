import requests

from iron_beam_authenticator import IronbeamAuthenticator
from Order import Order
import logging

logging.basicConfig(filename="trading_bot.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class OrderAPI:
    def __init__(self, token):
        self.base_url = "https://live.ironbeamapi.com/v2"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }



    def place_market_order(self, account_id, exch_sym, side, quantity):
        url = f"{self.base_url}/order/{account_id}/place"
        payload = {
            "accountId": account_id,
            "exchSym": exch_sym,
            "side": side,
            "quantity": quantity,
            "orderType": "MARKET",
            "duration": "DAY"
        }
        logging.info(f"Submitting Market Order {payload} and URL {url}")
        response = requests.post(url, json=payload, headers=self.headers)
        response_data = response.json()
        logging.info(f"Order Response For Market Order  {response_data}")
        return Order(
            order_id=response_data.get("orderId"),
            strategy_id=response_data.get("strategyId"),
            status=response_data.get("status"),
            message=response_data.get("message")
        )

    def place_stop_order(self, account_id, exch_sym, side, quantity, stop_price):
        url = f"{self.base_url}/order/{account_id}/place"
        payload = {
            "accountId": account_id,
            "exchSym": exch_sym,
            "side": side,
            "quantity": quantity,
            "orderType": "STOP",
            "stopPrice": stop_price,
            "duration": "DAY"
        }
        logging.info(f"Submitting Stop Order {payload} and URL {url}")
        response = requests.post(url, json=payload, headers=self.headers)
        response_data = response.json()
        logging.info(f"Order Response For Stop Order  {response_data}")
        return Order(
            order_id=response_data.get("orderId"),
            strategy_id=response_data.get("strategyId"),
            status=response_data.get("status"),
            message=response_data.get("message")
        )



    def cancel_order(self, account_id, order_id):
        url = f"{self.base_url}/order/{account_id}/cancel/{order_id}"
        logging.info(f"Submitting Cancel Order  URL {url}")
        response = requests.delete(url, headers=self.headers)
        logging.info(f"Order Response For Cancel Order  {response}")
        return response.json()

    def get_order_by_order_id(self, account_id, order_id, order_status):
        url = f"{self.base_url}/order/{account_id}/{order_status}"
        logging.info(f"Submitting get_order_by_order_id  URL {url}")
        response = requests.get(url, headers=self.headers)
        logging.info(f"Order Response For get_order_by_order_id  {response}")
        if response.status_code != 200:
            return None  # Handle failure case

        response_data = response.json()

        # Filter the order with the given order_id
        filtered_orders = [
            Order(
                order_id=order.get("orderId"),
                strategy_id=order.get("strategyId"),
                status=order.get("status"),
                message=order.get("message", "OK")
            )
            for order in response_data.get("orders", [])
            if order.get("orderId") == order_id  # Filter condition
        ]

        # Return only the specific order or None if not found
        return filtered_orders[0] if filtered_orders else None



# Example usage:
if __name__ == "__main__":
    base_url = "https://live.ironbeamapi.com/v2"  # Replace with actual base URL

    def log_to_main(msg):
        print(msg)

    SYMBOL = "XCME:ES.H25"  # Example symbol

    # Replace with your actual credentials and API key
    account_id = "23087442"
    password = "empire786110"
    api_key = "REDACTED__see_legacy_REDACTIONS_md"

    # Initialize the authenticator
    authenticator = IronbeamAuthenticator(account_id, password, api_key)
    #
    # # Authenticate and fetch the Bearer token
    token = authenticator.authenticate()

    order_api = OrderAPI(token)

    #Place a Market Order
    # market_order_response = order_api.place_market_order(
    #     account_id=account_id,
    #     exch_sym=SYMBOL,
    #     side="BUY",
    #     quantity=1
    # )
    # print("Market Order Response:", market_order_response)

    # #Place a Stop Limit Order
    # stop_limit_order_response = order_api.place_stop_order(
    #     account_id=account_id,
    #     exch_sym=SYMBOL,
    #     side="SELL",
    #     quantity=1,
    #     stop_price=5800
    # )
    # print("Stop Limit Order Response:", stop_limit_order_response)

    #
    # Get order by strategy ID
    # strategy_id = 1523773940111106  # Replace with actual strategy ID
    # get_order_response = order_api.get_order_by_strategy_id(account_id, strategy_id)
    # print("Get Order Response:", get_order_response)
    #
    # Cancel an order
    # order_id = "10715391738387924563-3055445"  # Replace with actual order ID
    # cancel_response = order_api.cancel_order(account_id, order_id)
    # print("Cancel Order Response:", cancel_response)
    # Get all order
    # order_id = "10715391738387924563-3055445"  # Replace with actual order ID
    # order = order_api.get_order_by_order_id(account_id, order_id, "ANY")
    # print("Cancel Order Response:", order)
