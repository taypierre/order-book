from enum import Enum

class Side(Enum):
    BUY = "BUY"
    SELL = "SELL"

class Order:
    __slots__ = ['order_id', 'side', 'price', 'quantity', 'timestamp']

    def __init__(self, order_id: int, side: Side, price: float, quantity: int, timestamp: int):
        self.order_id: int = order_id
        self.side: Side = side
        self.price: float = price
        self.quantity: int = quantity
        self.timestamp: int = timestamp  # Usually nanoseconds from epoch in HFT

    def __repr__(self) -> str:
        """A clean string representation for debugging."""
        return f"Order({self.order_id}, {self.side.value}, {self.price}, {self.quantity} qty)"