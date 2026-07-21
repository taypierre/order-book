from typing import Dict, Optional
from .order import Order, Side
from .price_level import PriceLevel, OrderNode

class OrderBook:
    """
    The core matching engine data structure.
    Maintains the state of all bids and asks and provides O(1) order lookups.
    """
    def __init__(self):
        # Hash Map mapping OrderID -> OrderNode
        # Find and cancel any order without searching
        self.order_map: Dict[int, OrderNode] = {}
        
        # Dictionaries mapping Price -> PriceLevel.
        self.bids: Dict[float, PriceLevel] = {}
        self.asks: Dict[float, PriceLevel] = {}

    def _get_or_create_price_level(self, side: Side, price: float) -> PriceLevel:
        """
        A private helper function. It checks if a PriceLevel already exists for a given price.
        If it doesn't, it creates a new one and adds it to the book.
        """
        book_side = self.bids if side == Side.BUY else self.asks
        
        if price not in book_side:
            book_side[price] = PriceLevel(price)
            
        return book_side[price]