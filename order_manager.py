"""
Order Management System for Grid Bot
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging
from enum import Enum
import time


class OrderStatus(Enum):
    """Order status enumeration"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class Order:
    """Represents a trading order"""
    symbol: str
    side: str  # BUY or SELL
    order_type: str  # LIMIT, MARKET, STOP
    price: float
    quantity: float
    order_id: Optional[int] = None
    client_order_id: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    filled_price: Optional[float] = None
    commission: float = 0.0
    created_time: datetime = field(default_factory=datetime.now)
    updated_time: Optional[datetime] = None
    grid_level_index: Optional[int] = None

    def is_active(self) -> bool:
        """Check if order is active"""
        return self.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED]

    def is_completed(self) -> bool:
        """Check if order is completed"""
        return self.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED]

    def update_status(self, new_status: OrderStatus):
        """Update order status"""
        self.status = new_status
        self.updated_time = datetime.now()


class OrderManager:
    """Manages order placement and tracking"""

    def __init__(self, client, config, risk_manager):
        self.client = client
        self.config = config
        self.risk_manager = risk_manager
        self.logger = logging.getLogger(__name__)

        # Order tracking
        self.orders: Dict[int, Order] = {}  # order_id -> Order
        self.pending_orders: List[Order] = []
        self.order_history: List[Order] = []

        # Statistics
        self.total_orders_placed: int = 0
        self.total_orders_filled: int = 0
        self.total_orders_cancelled: int = 0
        self.total_commission_paid: float = 0.0

    def create_grid_orders(self, grid_levels: List) -> List[Order]:
        """Create orders for grid levels"""
        orders = []

        for idx, level in enumerate(grid_levels):
            if level.status == 'pending':
                order = Order(
                    symbol=self.config.grid.symbol,
                    side=level.side,
                    order_type='LIMIT',
                    price=level.price,
                    quantity=level.quantity,
                    grid_level_index=idx
                )
                orders.append(order)

        return orders

    def place_order(self, order: Order) -> Tuple[bool, str]:
        """Place an order on the exchange"""

        # Check risk limits
        allowed, reason = self.risk_manager.check_order_allowed(
            order.symbol,
            order.side,
            order.quantity,
            order.price
        )

        if not allowed:
            self.logger.warning(f"Order rejected by risk manager: {reason}")
            order.update_status(OrderStatus.REJECTED)
            return False, reason

        try:
            # Format quantity to appropriate precision
            quantity = round(order.quantity, 3)

            # Place order via API
            response = self.client.place_order(
                symbol=order.symbol,
                side=order.side,
                order_type=order.order_type,
                quantity=quantity,
                price=order.price,
                time_in_force='GTC'
            )

            # Update order with response data
            order.order_id = response['orderId']
            order.client_order_id = response.get('clientOrderId')
            order.update_status(OrderStatus.SUBMITTED)

            # Track order
            self.orders[order.order_id] = order
            self.total_orders_placed += 1

            self.logger.info(f"Order placed: {order.side} {order.quantity} {order.symbol} @ {order.price} (ID: {order.order_id})")
            return True, f"Order placed successfully (ID: {order.order_id})"

        except Exception as e:
            self.logger.error(f"Failed to place order: {e}")
            order.update_status(OrderStatus.REJECTED)
            return False, str(e)

    def place_multiple_orders(self, orders: List[Order], delay: float = 0.1) -> Dict:
        """Place multiple orders with delay between each"""
        results = {
            'success': [],
            'failed': [],
            'total': len(orders)
        }

        for order in orders:
            success, message = self.place_order(order)

            if success:
                results['success'].append(order.order_id)
            else:
                results['failed'].append({
                    'order': order,
                    'reason': message
                })

            # Small delay to avoid rate limiting
            if delay > 0:
                time.sleep(delay)

        self.logger.info(f"Placed {len(results['success'])}/{results['total']} orders successfully")
        return results

    def cancel_order(self, order_id: int) -> Tuple[bool, str]:
        """Cancel an order"""
        if order_id not in self.orders:
            return False, "Order not found"

        order = self.orders[order_id]

        try:
            response = self.client.cancel_order(
                symbol=order.symbol,
                order_id=order_id
            )

            order.update_status(OrderStatus.CANCELLED)
            self.total_orders_cancelled += 1
            self.order_history.append(order)
            del self.orders[order_id]

            self.logger.info(f"Order cancelled: {order_id}")
            return True, "Order cancelled successfully"

        except Exception as e:
            self.logger.error(f"Failed to cancel order {order_id}: {e}")
            return False, str(e)

    def cancel_all_orders(self, symbol: str = None) -> Dict:
        """Cancel all open orders for a symbol"""
        symbol = symbol or self.config.grid.symbol

        try:
            response = self.client.cancel_all_orders(symbol)

            # Update local order tracking
            cancelled_orders = [oid for oid, order in self.orders.items() if order.symbol == symbol]

            for order_id in cancelled_orders:
                order = self.orders[order_id]
                order.update_status(OrderStatus.CANCELLED)
                self.order_history.append(order)
                del self.orders[order_id]

            self.total_orders_cancelled += len(cancelled_orders)
            self.logger.info(f"Cancelled {len(cancelled_orders)} orders for {symbol}")

            return {
                'success': True,
                'cancelled_count': len(cancelled_orders),
                'cancelled_orders': cancelled_orders
            }

        except Exception as e:
            self.logger.error(f"Failed to cancel all orders: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def update_order_status(self, order_id: int) -> Optional[Order]:
        """Update order status from exchange"""
        if order_id not in self.orders:
            return None

        order = self.orders[order_id]

        try:
            response = self.client.get_order(
                symbol=order.symbol,
                order_id=order_id
            )

            # Update order information
            status_map = {
                'NEW': OrderStatus.SUBMITTED,
                'PARTIALLY_FILLED': OrderStatus.PARTIALLY_FILLED,
                'FILLED': OrderStatus.FILLED,
                'CANCELED': OrderStatus.CANCELLED,
                'REJECTED': OrderStatus.REJECTED,
                'EXPIRED': OrderStatus.EXPIRED
            }

            api_status = response.get('status', 'NEW')
            order.update_status(status_map.get(api_status, OrderStatus.SUBMITTED))

            # Update filled quantity
            order.filled_quantity = float(response.get('executedQty', 0))

            # Calculate average filled price
            if order.filled_quantity > 0:
                cumulative_quote = float(response.get('cumQuote', 0))
                order.filled_price = cumulative_quote / order.filled_quantity

            # Update commission
            # Note: Commission info might need separate API call

            # If order is filled, update risk manager
            if order.status == OrderStatus.FILLED:
                self.on_order_filled(order)

            return order

        except Exception as e:
            self.logger.error(f"Failed to update order status for {order_id}: {e}")
            return None

    def update_all_orders(self) -> int:
        """Update status of all active orders"""
        updated_count = 0
        order_ids = list(self.orders.keys())  # Create copy to avoid dict size change during iteration

        for order_id in order_ids:
            if self.update_order_status(order_id):
                updated_count += 1

        return updated_count

    def on_order_filled(self, order: Order):
        """Handle order filled event"""
        self.logger.info(f"Order filled: {order.side} {order.filled_quantity} {order.symbol} @ {order.filled_price}")

        self.total_orders_filled += 1

        # Update risk manager position
        self.risk_manager.update_position(
            symbol=order.symbol,
            side='LONG' if order.side == 'BUY' else 'SHORT',
            entry_price=order.filled_price,
            quantity=order.filled_quantity,
            leverage=self.config.grid.leverage
        )

        # Move to history
        self.order_history.append(order)
        if order.order_id in self.orders:
            del self.orders[order.order_id]

    def get_open_orders(self, symbol: str = None) -> List[Order]:
        """Get all open orders"""
        if symbol:
            return [order for order in self.orders.values() if order.symbol == symbol and order.is_active()]
        return [order for order in self.orders.values() if order.is_active()]

    def get_filled_orders(self, symbol: str = None, hours: int = 24) -> List[Order]:
        """Get filled orders within time period"""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        filled = [order for order in self.order_history
                 if order.status == OrderStatus.FILLED and order.updated_time > cutoff_time]

        if symbol:
            filled = [order for order in filled if order.symbol == symbol]

        return filled

    def get_order_statistics(self) -> Dict:
        """Get order statistics"""
        active_orders = len(self.orders)
        active_buy_orders = len([o for o in self.orders.values() if o.side == 'BUY'])
        active_sell_orders = len([o for o in self.orders.values() if o.side == 'SELL'])

        return {
            'total_placed': self.total_orders_placed,
            'total_filled': self.total_orders_filled,
            'total_cancelled': self.total_orders_cancelled,
            'active_orders': active_orders,
            'active_buy_orders': active_buy_orders,
            'active_sell_orders': active_sell_orders,
            'fill_rate': (self.total_orders_filled / self.total_orders_placed * 100) if self.total_orders_placed > 0 else 0.0,
            'total_commission_paid': self.total_commission_paid,
            'avg_fill_time': self._calculate_avg_fill_time()
        }

    def _calculate_avg_fill_time(self) -> float:
        """Calculate average time to fill orders"""
        filled_orders = [o for o in self.order_history if o.status == OrderStatus.FILLED and o.updated_time]

        if not filled_orders:
            return 0.0

        total_time = sum((o.updated_time - o.created_time).total_seconds() for o in filled_orders)
        return total_time / len(filled_orders)

    def sync_orders_with_exchange(self) -> Dict:
        """Sync local orders with exchange state"""
        symbol = self.config.grid.symbol

        try:
            # Get open orders from exchange
            exchange_orders = self.client.get_open_orders(symbol)
            exchange_order_ids = {order['orderId'] for order in exchange_orders}

            # Find orders that exist locally but not on exchange (likely filled or cancelled)
            local_order_ids = set(self.orders.keys())
            missing_orders = local_order_ids - exchange_order_ids

            # Update status of missing orders
            for order_id in missing_orders:
                self.update_order_status(order_id)

            # Find orders on exchange not tracked locally
            untracked_orders = exchange_order_ids - local_order_ids

            self.logger.info(f"Order sync complete. Missing: {len(missing_orders)}, Untracked: {len(untracked_orders)}")

            return {
                'synced': True,
                'missing_orders': len(missing_orders),
                'untracked_orders': len(untracked_orders),
                'total_active': len(exchange_orders)
            }

        except Exception as e:
            self.logger.error(f"Failed to sync orders: {e}")
            return {
                'synced': False,
                'error': str(e)
            }

    def cleanup_old_orders(self, hours: int = 168):  # 7 days default
        """Remove old completed orders from history"""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        before_count = len(self.order_history)
        self.order_history = [
            order for order in self.order_history
            if order.updated_time and order.updated_time > cutoff_time
        ]
        removed_count = before_count - len(self.order_history)

        if removed_count > 0:
            self.logger.info(f"Cleaned up {removed_count} old orders from history")

        return removed_count
