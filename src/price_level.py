from typing import Optional
from .order import Order

class OrderNode:
    __slots__ = ['order', 'next_node', 'prev_node']

    def __init__(self, order: Order):
        self.order: Order = order
        self.next_node: Optional['OrderNode'] = None
        self.prev_node: Optional['OrderNode'] = None

class PriceLevel:
    """
    A Doubly Linked List representing queue of orders at A specific price
    FIFO order
    """
    __slots__ = ['price', 'head', 'tail', 'volume', 'count']

    def __init__(self, price: float):
        self.price: float = price
        self.head: Optional[OrderNode] = None  # Hold OrderNode or None if empty
        self.tail: Optional[OrderNode] = None  
        self.volume: int = 0                   # Total quantity of all orders at this price
        self.count: int = 0                    # Total number of active orders (participants)

    def append(self, node: OrderNode) -> None:
        """
        Adds a new order to the back of the queue
        """
        if self.tail is None:
            self.head = node
            self.tail = node
        else:
            # Add to the end
            self.tail.next_node = node
            node.prev_node = self.tail
            self.tail = node
        
        self.volume += node.order.quantity
        self.count += 1

    def remove(self, node: OrderNode) -> None:
        """
        Remove an order from the queue
        """
        if node.prev_node:
            node.prev_node.next_node = node.next_node
        else:
            self.head = node.next_node

        if node.next_node:
            node.next_node.prev_node = node.prev_node
        else:
            self.tail = node.prev_node

        node.next_node = None
        node.prev_node = None

        self.volume -= node.order.quantity
        self.count -= 1