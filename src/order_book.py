from typing import Dict, Optional
from order import Order, Side
from price_level import PriceLevel, OrderNode

from dataclasses import dataclass

@dataclass
class Trade:
    maker_order_id: int   # The resting order ID
    taker_order_id: int   # The incoming order ID
    price: float          # The price the trade executed at
    quantity: int         # How many shares traded
    
class OrderBook:
    """
    The core matching engine data structure.
    Maintains the state of all bids and asks and provides O(1) order lookups.
    """
    def __init__(self):
        # Hash Map mapping OrderID -> OrderNode
        # Find and cancel any order without searching
        self.order_map: Dict[int, OrderNode] = {}
        
        self.trade_log = []
        
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
            
    def _match_order(self, taker_order_id: int, side: Side, aggressive_price: float, quantity: int) -> int:
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
                
                traded_qty = resting_order.quantity
                
                if remaining >= resting_order.quantity:
                    remaining -= resting_order.quantity
                    
                    price_level.remove(resting_node)
                    del self.order_map[resting_order.order_id]
                else:
                    traded_qty = remaining
                    
                    resting_order.quantity -= remaining
                    price_level.volume -= remaining
                    remaining = 0
                
                new_trade = Trade(
                    maker_order_id=resting_order.order_id,
                    taker_order_id=taker_order_id,
                    price=price, 
                    quantity=traded_qty
                )
                self.trade_log.append(new_trade)
                    
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
            """
            Updates the best bid and best ask prices based on the current state of the order book
            """
            if len(self.bids) > 0:
                self.best_bid = max(self.bids.keys())
            else:
                self.best_bid = 0.0
                
            if len(self.asks) > 0:
                self.best_ask = min(self.asks.keys())
            else:
                self.best_ask = float('inf')
                
                
    def process_order(self, order_id: str, side: Side, price: float, quantity: int, timestamp: int):
        """
        The MAIN entry point for new orders, attempts to match first 
        """
        # Try to match the incoming order against existing liquidity
        remaining_qty = self._match_order(order_id, side, price, quantity)
        
        # If the order didn't completely fill, it becomes a resting order
        if remaining_qty > 0:
            self._add_to_book(order_id, side, price, remaining_qty, timestamp)
            
    def _add_to_book(self, order_id: int, side: Side, price: float, quantity: int, timestamp: int) -> None:
        """
        Places an unfilled order into the book to rest
        """
        # Create the Order and OrderNode
        new_order = Order(order_id, side, price, quantity, timestamp)
        new_node = OrderNode(new_order)
        
        target_book = self.bids if side == Side.BUY else self.asks
        
        # If this is the first time seeing this price, create new PriceLevel
        if price not in target_book:
            target_book[price] = PriceLevel(price)
            
        # Add the node to the back of the queue at this price
        target_book[price].append(new_node)
        
        # Store the NODE in global map 
        self.order_map[order_id] = new_node
        
        # Update the best bid/ask
        self._update_top_of_book()
        
    def cancel_order(self, order_id: int) -> bool:
        """
        Cancels an active resting order instantly using the global map
        Returns True/False
        """
        # Look up the order instantly
        if order_id not in self.order_map:
            return False 

        # Get exact node and its data
        node_to_cancel = self.order_map[order_id]
        order = node_to_cancel.order

        # Find which book and price level
        target_book = self.bids if order.side == Side.BUY else self.asks
        price_level = target_book[order.price]

        # Remove from linked list
        price_level.remove(node_to_cancel)

        # Delete it from global map
        del self.order_map[order_id]

        # If that was the very last order at that price, delete the price level
        if price_level.head is None:
            del target_book[order.price]

        # Recalculate top of book
        self._update_top_of_book()

        return True
    
    def modify_order(self, order_id: int, new_price: float, new_quantity: int, timestamp: int) -> bool:
        """
        Modifies an active order
        - If Decreasing quantity only: Keeps queue position
        - If change in price or increase in quantity: Loses queue position (Cancel + Replace)
        """
        # Check if the order actually exists
        if order_id not in self.order_map:
            return False
            
        node = self.order_map[order_id]
        order = node.order
        
        # Case 1: Only decreasing quantity
        if new_price == order.price and new_quantity < order.quantity:
            
            # Get difference in quantity
            qty_difference = order.quantity - new_quantity
            
            # Update the order's personal quantity
            order.quantity = new_quantity
            
            # Update the total volume available at this price level
            target_book = self.bids if order.side == Side.BUY else self.asks
            target_book[order.price].volume -= qty_difference
            
            return True
            
        # Case 2: Price changed/Quantity increased
        else:
            # Save the side
            original_side = order.side
            
            # Remove the order from the book
            self.cancel_order(order_id)
            
            # Re-create the order with new parameters and process it as a new order
            self.process_order(order_id, original_side, new_price, new_quantity, timestamp)
            
            return True
        
    def process_market_order(self, order_id: int, side: Side, quantity: int) -> int:
        """
        Executes immediately against available liquidity at the best possible prices
        Never rests on the book. Returns the unfilled quantity (if the book is emptied)
        """
        
        # Set the ultimate aggressive price since market orders have no price limit
        if side == Side.BUY:
            aggressive_price = float('inf')
        else:
            aggressive_price = 0.0
            
        # Match the market order against the opposite side of the book
        remaining_qty = self._match_order(order_id, side, aggressive_price, quantity)
        
        # CRITICAL: DOES NOT call _add_to_book since Market orders never rest. 
        # They are either filled immediately or expire unfilled.
        return remaining_qty
    
def print_book(book: OrderBook):
        """A helper function to visualize the book in the terminal."""
        print("\n" + "="*25 + " ORDER BOOK " + "="*25)
        
        print("--- ASKS (Sellers) ---")
        # Print asks in descending order (highest price at the top)
        for price in sorted(book.asks.keys(), reverse=True):
            print(f"     ${price:.2f}  |  Volume: {book.asks[price].volume}")
        
        print("-" * 62)
        print(f" SPREAD: Best Ask ${book.best_ask:.2f}  <--->  Best Bid ${book.best_bid:.2f}")
        print("-" * 62)
        
        print("--- BIDS (Buyers) ---")
        # Print bids in descending order (highest price at the top)
        for price in sorted(book.bids.keys(), reverse=True):
            print(f"     ${price:.2f}  |  Volume: {book.bids[price].volume}")
        print("="*62 + "\n")

# --- MAIN EXECUTION SCRIPT ---
if __name__ == "__main__":
    ob = OrderBook()
    
    # Add some resting liquidity to the book
    print("-> Adding resting liquidity to the market...")
    ob.process_order(order_id=101, side=Side.SELL, price=150.0, quantity=100, timestamp=1)
    ob.process_order(order_id=102, side=Side.SELL, price=151.0, quantity=50, timestamp=2)
    ob.process_order(order_id=201, side=Side.BUY, price=148.0, quantity=200, timestamp=3)
    
    print_book(ob)
    
    # Submit aggressive order
    print("-> Aggressive BUY (Taker): 120 shares @ Limit $150.50...")
    ob.process_order(order_id=202, side=Side.BUY, price=150.5, quantity=120, timestamp=4)
    
    # Show the book after trading
    print_book(ob)
    
    # Print the trade receipts
    print("=== TRADE LOG ===")
    if not ob.trade_log:
        print("No trades executed.")
    else:
        for trade in ob.trade_log:
            print(f"Maker ID: {trade.maker_order_id: <4} | Taker ID: {trade.taker_order_id: <4} | "
                  f"Exec Price: ${trade.price:.2f} | Traded Qty: {trade.quantity}")
    print()
            
    print("-> Submitting Aggressive MARKET BUY (Taker): 60 shares...")
    ob.process_market_order(order_id=203, side=Side.BUY, quantity=60)
    
    print_book(ob)
    print("=== TRADE LOG ===")
    if not ob.trade_log:
        print("No trades executed.")
    else:
        for trade in ob.trade_log:
            print(f"Maker ID: {trade.maker_order_id: <4} | Taker ID: {trade.taker_order_id: <4} | "
                  f"Exec Price: ${trade.price:.2f} | Traded Qty: {trade.quantity}")