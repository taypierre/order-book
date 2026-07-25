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
        
        self.best_bid: float = 0.0          # Set Highest buying price
        self.best_ask: float = float('inf') # Set Lowest selling price

    def _get_or_create_price_level(self, side: Side, price: float) -> PriceLevel:
        """
        A private helper function. It checks if a PriceLevel already exists for a given price
        If it doesn't, it creates a new one and adds it to the book
        """
        book_side = self.bids if side == Side.BUY else self.asks
        
        if price not in book_side:
            book_side[price] = PriceLevel(price)
            
        return book_side[price]
    
    def add_order(self, order_id: int, side: Side, price: float, quantity: int, timestamp: int) -> None:
        """
        Processes a new incoming order and places it into the correct price queue
        Matches if crosses spread, else add to order book
        """
        remaining_qty = quantity # Keep track of how much of the order is left to fill
        
        if side == Side.BUY and price >= self.best_ask: # If the BUY order price is greater than or equal to the best ask, we can match it
            remaining_qty = self._match_order(side, price, remaining_qty)
        elif side == Side.SELL and price <= self.best_bid: # If the SELL order price is less than or equal to the best bid, we can match it
            remaining_qty = self._match_order(side, price, remaining_qty)
            
        # If the order was completely filled during matching
        if remaining_qty == 0:
            return
            
        # Remaining quantity, add to order book
        new_order = Order(order_id, side, price, remaining_qty, timestamp)
        new_node = OrderNode(new_order)
        
        self.order_map[order_id] = new_node
        
        price_level = self._get_or_create_price_level(side, price)
        price_level.append(new_node)
        
        # Set the best BID/ASK
        if side == Side.BUY and price > self.best_bid:
            self.best_bid = price
        elif side == Side.SELL and price < self.best_ask:
            self.best_ask = price
            
            
    def _match_order(self, side: Side, aggressive_price: float, quantity: int) -> int:
        """
        Eats liquidity from the opposite side of the book until the order is filled 
        or the price limit is reached. Returns the remaining quantity.
        """
        remaining = quantity
        
        # If buying, we look at the sellers (asks). If selling, we look at buyers (bids).
        if side == Side.BUY:
            target_book = self.asks    # Buyers look at the sellers' book
            reverse_sort = False       # Sort asks in ascending order
        else:
            target_book = self.bids    # Sellers look at the buyers' book
            reverse_sort = True        # Sort bids in descending order (highest price first)
        
        # Loop through the available price levels in the correct order
        for price in sorted(target_book.keys(), reverse=reverse_sort):
            # Check if the price is still valid for our limit order
            if side == Side.BUY and aggressive_price < price:
                break  # The remaining sellers are too expensive
            elif side == Side.SELL and aggressive_price > price:
                break  # The remaining buyers are too cheap
                
            price_level = target_book[price]
            
            # Walk through the line of waiting orders at this price
            while price_level.head and remaining > 0:
                resting_node = price_level.head
                resting_order = resting_node.order
                
                if remaining >= resting_order.quantity:
                    remaining -= resting_order.quantity
                    
                    price_level.remove(resting_node)
                    del self.order_map[resting_order.order_id]
                else:
                    resting_order.quantity -= remaining
                    price_level.volume -= remaining
                    remaining = 0
                    
            # If price level empty, delete from book
            if price_level.head is None:
                del target_book[price]
                
            # If we've filled entire order, stop searching
            if remaining == 0:
                break
                
        # Update our best bid/ask
        self._update_top_of_book()
        
        return remaining

    def _update_top_of_book(self) -> None:
            if len(self.bids) > 0:
                self.best_bid = max(self.bids.keys())
            else:
                self.best_bid = 0.0
                
            if len(self.asks) > 0:
                self.best_ask = min(self.asks.keys())
            else:
                self.best_ask = float('inf')