"""
Unit tests for order management module
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from order_manager import (
    OrderManager,
    Order,
    OrderStatus
)


class TestOrder:
    """Test Order data class"""

    def test_order_creation(self):
        """Test order creation"""
        order = Order(
            symbol='BTCUSDT',
            side='BUY',
            order_type='LIMIT',
            price=40000.0,
            quantity=0.001
        )

        assert order.symbol == 'BTCUSDT'
        assert order.side == 'BUY'
        assert order.order_type == 'LIMIT'
        assert order.status == OrderStatus.PENDING
        assert order.filled_quantity == 0.0

    def test_order_is_active(self, sample_order):
        """Test order active check"""
        sample_order.status = OrderStatus.SUBMITTED
        assert sample_order.is_active() is True

        sample_order.status = OrderStatus.FILLED
        assert sample_order.is_active() is False

    def test_order_is_completed(self, sample_order):
        """Test order completed check"""
        sample_order.status = OrderStatus.PENDING
        assert sample_order.is_completed() is False

        sample_order.status = OrderStatus.FILLED
        assert sample_order.is_completed() is True

        sample_order.status = OrderStatus.CANCELLED
        assert sample_order.is_completed() is True

    def test_order_update_status(self, sample_order):
        """Test order status update"""
        sample_order.update_status(OrderStatus.SUBMITTED)

        assert sample_order.status == OrderStatus.SUBMITTED
        assert sample_order.updated_time is not None


class TestOrderManager:
    """Test order manager"""

    def test_order_manager_creation(self, mock_binance_client, bot_config, risk_manager):
        """Test order manager initialization"""
        manager = OrderManager(mock_binance_client, bot_config, risk_manager)

        assert manager.client == mock_binance_client
        assert manager.config == bot_config
        assert len(manager.orders) == 0
        assert manager.total_orders_placed == 0

    def test_create_grid_orders(self, order_manager, sample_grid_levels):
        """Test creating orders from grid levels"""
        orders = order_manager.create_grid_orders(sample_grid_levels)

        assert len(orders) == len(sample_grid_levels)
        assert all(isinstance(o, Order) for o in orders)
        assert all(o.order_type == 'LIMIT' for o in orders)

    @patch.object(OrderManager, 'place_order')
    def test_place_order_success(self, mock_place, order_manager, sample_order):
        """Test successful order placement"""
        mock_place.return_value = (True, "Order placed successfully")

        success, message = order_manager.place_order(sample_order)

        assert success is True
        mock_place.assert_called_once()

    def test_place_order_risk_rejection(self, order_manager, sample_order):
        """Test order rejected by risk manager"""
        # Set risk manager to reject orders
        order_manager.risk_manager.trigger_emergency_stop("Test stop")

        success, message = order_manager.place_order(sample_order)

        assert success is False
        assert "Emergency stop active" in message
        assert sample_order.status == OrderStatus.REJECTED

    @patch('binance_client.BinanceFuturesClient.place_order')
    def test_place_order_api_success(self, mock_api, order_manager, sample_order, binance_test_responses):
        """Test order placement through API"""
        mock_api.return_value = binance_test_responses['order_response']

        success, message = order_manager.place_order(sample_order)

        assert success is True
        assert sample_order.order_id == 12345
        assert sample_order.status == OrderStatus.SUBMITTED
        assert 12345 in order_manager.orders

    @patch('binance_client.BinanceFuturesClient.place_order')
    def test_place_order_api_failure(self, mock_api, order_manager, sample_order):
        """Test order placement API failure"""
        mock_api.side_effect = Exception("API Error")

        success, message = order_manager.place_order(sample_order)

        assert success is False
        assert sample_order.status == OrderStatus.REJECTED

    @patch('binance_client.BinanceFuturesClient.place_order')
    def test_place_multiple_orders(self, mock_api, order_manager, sample_grid_levels, binance_test_responses):
        """Test placing multiple orders"""
        mock_api.return_value = binance_test_responses['order_response']

        orders = order_manager.create_grid_orders(sample_grid_levels)
        results = order_manager.place_multiple_orders(orders, delay=0)

        assert results['total'] == len(orders)
        assert len(results['success']) > 0

    @patch('binance_client.BinanceFuturesClient.cancel_order')
    def test_cancel_order_success(self, mock_api, order_manager, sample_filled_order):
        """Test successful order cancellation"""
        sample_filled_order.status = OrderStatus.SUBMITTED
        order_manager.orders[sample_filled_order.order_id] = sample_filled_order

        mock_api.return_value = {'orderId': sample_filled_order.order_id, 'status': 'CANCELED'}

        success, message = order_manager.cancel_order(sample_filled_order.order_id)

        assert success is True
        assert sample_filled_order.status == OrderStatus.CANCELLED

    def test_cancel_order_not_found(self, order_manager):
        """Test cancelling nonexistent order"""
        success, message = order_manager.cancel_order(99999)

        assert success is False
        assert "not found" in message

    @patch('binance_client.BinanceFuturesClient.cancel_all_orders')
    def test_cancel_all_orders(self, mock_api, order_manager):
        """Test cancelling all orders"""
        # Add some orders
        for i in range(3):
            order = Order(
                symbol='BTCUSDT',
                side='BUY',
                order_type='LIMIT',
                price=40000.0 + i * 100,
                quantity=0.001,
                order_id=1000 + i,
                status=OrderStatus.SUBMITTED
            )
            order_manager.orders[order.order_id] = order

        mock_api.return_value = {'code': 200}

        result = order_manager.cancel_all_orders('BTCUSDT')

        assert result['success'] is True
        assert result['cancelled_count'] == 3

    @patch('binance_client.BinanceFuturesClient.get_order')
    def test_update_order_status(self, mock_api, order_manager, binance_test_responses):
        """Test updating order status from exchange"""
        order = Order(
            symbol='BTCUSDT',
            side='BUY',
            order_type='LIMIT',
            price=40000.0,
            quantity=0.001,
            order_id=12345,
            status=OrderStatus.SUBMITTED
        )
        order_manager.orders[12345] = order

        # Mock filled order response
        filled_response = binance_test_responses['order_response'].copy()
        filled_response['status'] = 'FILLED'
        filled_response['executedQty'] = '0.001'
        filled_response['cumQuote'] = '40.0'
        mock_api.return_value = filled_response

        updated_order = order_manager.update_order_status(12345)

        assert updated_order is not None
        assert updated_order.status == OrderStatus.FILLED
        assert updated_order.filled_quantity == 0.001

    def test_update_order_status_not_found(self, order_manager):
        """Test updating nonexistent order"""
        result = order_manager.update_order_status(99999)

        assert result is None

    @patch('binance_client.BinanceFuturesClient.get_order')
    def test_update_all_orders(self, mock_api, order_manager, binance_test_responses):
        """Test updating all active orders"""
        # Add multiple orders
        for i in range(3):
            order = Order(
                symbol='BTCUSDT',
                side='BUY',
                order_type='LIMIT',
                price=40000.0,
                quantity=0.001,
                order_id=1000 + i,
                status=OrderStatus.SUBMITTED
            )
            order_manager.orders[order.order_id] = order

        mock_api.return_value = binance_test_responses['order_response']

        count = order_manager.update_all_orders()

        assert count == 3

    def test_on_order_filled(self, order_manager, sample_filled_order):
        """Test order filled event handling"""
        order_manager.orders[sample_filled_order.order_id] = sample_filled_order

        order_manager.on_order_filled(sample_filled_order)

        assert order_manager.total_orders_filled == 1
        assert sample_filled_order.order_id not in order_manager.orders
        assert len(order_manager.order_history) == 1

    def test_get_open_orders(self, order_manager):
        """Test getting open orders"""
        # Add mixed orders
        for i in range(3):
            order = Order(
                symbol='BTCUSDT',
                side='BUY',
                order_type='LIMIT',
                price=40000.0,
                quantity=0.001,
                order_id=1000 + i,
                status=OrderStatus.SUBMITTED if i < 2 else OrderStatus.FILLED
            )
            order_manager.orders[order.order_id] = order

        open_orders = order_manager.get_open_orders('BTCUSDT')

        assert len(open_orders) == 2  # Only submitted orders

    def test_get_filled_orders(self, order_manager, sample_filled_order):
        """Test getting filled orders"""
        order_manager.order_history.append(sample_filled_order)

        filled = order_manager.get_filled_orders('BTCUSDT', hours=24)

        assert len(filled) == 1
        assert filled[0].status == OrderStatus.FILLED

    def test_get_order_statistics(self, order_manager):
        """Test getting order statistics"""
        # Add some orders
        order_manager.total_orders_placed = 10
        order_manager.total_orders_filled = 8
        order_manager.total_orders_cancelled = 2

        for i in range(3):
            order = Order(
                symbol='BTCUSDT',
                side='BUY' if i < 2 else 'SELL',
                order_type='LIMIT',
                price=40000.0,
                quantity=0.001,
                order_id=1000 + i,
                status=OrderStatus.SUBMITTED
            )
            order_manager.orders[order.order_id] = order

        stats = order_manager.get_order_statistics()

        assert stats['total_placed'] == 10
        assert stats['total_filled'] == 8
        assert stats['active_orders'] == 3
        assert stats['active_buy_orders'] == 2
        assert stats['active_sell_orders'] == 1
        assert stats['fill_rate'] == 80.0

    @patch('binance_client.BinanceFuturesClient.get_open_orders')
    def test_sync_orders_with_exchange(self, mock_api, order_manager):
        """Test syncing orders with exchange"""
        # Local orders
        for i in range(3):
            order = Order(
                symbol='BTCUSDT',
                side='BUY',
                order_type='LIMIT',
                price=40000.0,
                quantity=0.001,
                order_id=1000 + i,
                status=OrderStatus.SUBMITTED
            )
            order_manager.orders[order.order_id] = order

        # Exchange only has 2 orders (one was filled)
        mock_api.return_value = [
            {'orderId': 1000},
            {'orderId': 1001}
        ]

        with patch.object(order_manager, 'update_order_status'):
            result = order_manager.sync_orders_with_exchange()

        assert result['synced'] is True
        assert result['missing_orders'] == 1

    def test_cleanup_old_orders(self, order_manager):
        """Test cleaning up old orders from history"""
        # Add old orders
        old_order = Order(
            symbol='BTCUSDT',
            side='BUY',
            order_type='LIMIT',
            price=40000.0,
            quantity=0.001,
            order_id=1000,
            status=OrderStatus.FILLED
        )
        old_order.updated_time = datetime.now() - timedelta(days=8)
        order_manager.order_history.append(old_order)

        # Add recent order
        recent_order = Order(
            symbol='BTCUSDT',
            side='BUY',
            order_type='LIMIT',
            price=40000.0,
            quantity=0.001,
            order_id=1001,
            status=OrderStatus.FILLED
        )
        recent_order.updated_time = datetime.now()
        order_manager.order_history.append(recent_order)

        removed = order_manager.cleanup_old_orders(hours=168)  # 7 days

        assert removed == 1
        assert len(order_manager.order_history) == 1


@pytest.mark.parametrize("side,price,quantity", [
    ('BUY', 40000.0, 0.001),
    ('SELL', 41000.0, 0.002),
    ('BUY', 39000.0, 0.0015),
])
@patch('binance_client.BinanceFuturesClient.place_order')
def test_place_order_parameters(mock_api, order_manager, binance_test_responses, side, price, quantity):
    """Test order placement with various parameters"""
    response = binance_test_responses['order_response'].copy()
    response['side'] = side
    response['price'] = str(price)
    response['origQty'] = str(quantity)
    mock_api.return_value = response

    order = Order(
        symbol='BTCUSDT',
        side=side,
        order_type='LIMIT',
        price=price,
        quantity=quantity
    )

    success, message = order_manager.place_order(order)

    assert success is True
    assert order.status == OrderStatus.SUBMITTED


def test_order_flow(order_manager):
    """Test complete order flow"""
    # Create order
    order = Order(
        symbol='BTCUSDT',
        side='BUY',
        order_type='LIMIT',
        price=40000.0,
        quantity=0.001,
        status=OrderStatus.PENDING
    )

    # Update to submitted
    order.update_status(OrderStatus.SUBMITTED)
    order.order_id = 12345
    order_manager.orders[12345] = order

    # Update to filled
    order.update_status(OrderStatus.FILLED)
    order.filled_quantity = 0.001
    order.filled_price = 40000.0

    # Process fill
    order_manager.on_order_filled(order)

    # Verify flow
    assert order.status == OrderStatus.FILLED
    assert order_manager.total_orders_filled == 1
    assert 12345 not in order_manager.orders
    assert len(order_manager.order_history) == 1
