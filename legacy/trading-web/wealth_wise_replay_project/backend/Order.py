class Order:
    def __init__(self, order_id, strategy_id, status, message):
        self.order_id = order_id
        self.strategy_id = strategy_id
        self.status = status
        self.message = message

    def to_dict(self):
        return {
            "orderId": self.order_id,
            "strategyId": self.strategy_id,
            "status": self.status,
            "message": self.message
        }

    def __hash__(self):
        return hash((self.order_id, self.strategy_id, self.status, self.message))

    def __str__(self):
        return f"Order(orderId={self.order_id}, strategyId={self.strategy_id}, status={self.status}, message={self.message})"

    def __repr__(self):
        return self.__str__()
