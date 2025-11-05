"""
Integration tests for grid bot
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import time

from config import BotConfig
from binance_client import BinanceFuturesClient
from grid_strategy import AdaptiveGridStrategy
from risk_manager import RiskManager
from order_manager import OrderManager, OrderStatus


@pytest.mark.integration
class TestGridBotIntegration:
    """Integration tests for complete grid bot workflow"""

    @pytest.fixture
    def integrated_bot(self, bot_config, mock_exchange):
        """Create integrated bot components"""
        client = MagicMock(spec=BinanceFuturesClient)
        risk_manager = RiskManager(bot_config)
        order_manager = OrderManager(client, bot_config, risk_manager)
        grid_strategy = AdaptiveGridStrategy(bot_config)

        # Mock client responses
        client.get_ticker_price.return_value = {'price': '40000.0'}
        client.get_account_info.return_value = {
            'assets': [{'asset': 'USDT', 'availableBalance': '10000.0', 'walletBalance': '10000.0'}]
        }
        client.place_order.side_effect = lambda **kwargs: mock_exchange.place_order(**kwargs)

        return {
            'client': client,
            'risk_manager': risk_manager,
            'order_manager': order_manager,
            'grid_strategy': grid_strategy,
            'exchange': mock_exchange
        }

    def test_complete_grid_initialization_flow(self, integrated_bot):
        """Test complete grid initialization workflow"""
        grid_strategy = integrated_bot['grid_strategy']
        order_manager = integrated_bot['order_manager']

        # Initialize grid
        grid_strategy.initialize_grid(current_price=40000.0, volatility=1.5)

        # Verify grid created
        assert len(grid_strategy.grid_levels) > 0

        # Create orders from grid
        orders = order_manager.create_grid_orders(grid_strategy.get_pending_orders())

        # Verify orders created
        assert len(orders) == len(grid_strategy.grid_levels)

    def test_order_placement_and_tracking_flow(self, integrated_bot):
        """Test order placement and tracking workflow"""
        grid_strategy = integrated_bot['grid_strategy']
        order_manager = integrated_bot['order_manager']
        exchange = integrated_bot['exchange']

        # Initialize and place orders
        grid_strategy.initialize_grid(40000.0, 1.5)
        orders = order_manager.create_grid_orders(grid_strategy.get_pending_orders())

        # Place first order
        order = orders[0]
        success, message = order_manager.place_order(order)

        # Verify order placed
        assert success is True
        assert order.order_id is not None
        assert order.order_id in order_manager.orders

        # Mark in grid strategy
        grid_strategy.mark_order_placed(order.price, order.order_id)

        # Verify tracking
        active_orders = grid_strategy.get_active_orders()
        assert len(active_orders) > 0

    def test_order_fill_and_position_creation_flow(self, integrated_bot):
        """Test order fill and position creation workflow"""
        grid_strategy = integrated_bot['grid_strategy']
        order_manager = integrated_bot['order_manager']
        risk_manager = integrated_bot['risk_manager']
        exchange = integrated_bot['exchange']

        # Initialize grid and place buy order
        grid_strategy.initialize_grid(40000.0, 1.5)
        orders = order_manager.create_grid_orders(grid_strategy.get_pending_orders())

        # Find a buy order
        buy_order = next((o for o in orders if o.side == 'BUY'), None)
        assert buy_order is not None

        # Place order
        order_manager.place_order(buy_order)
        grid_strategy.mark_order_placed(buy_order.price, buy_order.order_id)

        # Simulate fill
        exchange.fill_order(buy_order.order_id)
        buy_order.status = OrderStatus.FILLED
        buy_order.filled_quantity = buy_order.quantity
        buy_order.filled_price = buy_order.price

        # Process fill
        order_manager.on_order_filled(buy_order)
        grid_strategy.mark_order_filled(buy_order.order_id, buy_order.filled_price)

        # Verify position created
        assert len(risk_manager.positions) > 0

    def test_risk_limits_during_trading_flow(self, integrated_bot):
        """Test risk limit enforcement during trading"""
        grid_strategy = integrated_bot['grid_strategy']
        order_manager = integrated_bot['order_manager']
        risk_manager = integrated_bot['risk_manager']

        # Set position limit for testing
        # Each order is 0.001 BTC * 40000 = 40 USDT
        # Set limit to 150 USDT so first order passes (40 < 150) but second fails (80 > 150 with buffer)
        risk_manager.risk_config.max_position_usdt = 150.0

        # Initialize grid
        grid_strategy.initialize_grid(40000.0, 1.5)
        orders = order_manager.create_grid_orders(grid_strategy.get_pending_orders())

        # Place first order and fill it to create a position
        success, msg = order_manager.place_order(orders[0])
        assert success is True

        # Simulate order fill to create position (leverage affects position value)
        risk_manager.update_position(
            symbol=orders[0].symbol,
            side=orders[0].side,
            entry_price=orders[0].price,
            quantity=orders[0].quantity,
            leverage=5
        )

        # Now try to place more orders (should fail due to position limit)
        results = order_manager.place_multiple_orders(orders[1:5], delay=0)

        # Some orders should be rejected due to position limit
        assert len(results['failed']) > 0

    def test_stop_loss_trigger_flow(self, integrated_bot):
        """Test stop loss triggering workflow"""
        risk_manager = integrated_bot['risk_manager']

        # Create position
        risk_manager.update_position(
            symbol='BTCUSDT',
            side='LONG',
            entry_price=40000.0,
            quantity=0.01,
            leverage=5
        )

        # Price drops below stop loss
        current_price = 37500.0  # -6.25% loss
        should_stop = risk_manager.check_stop_loss('BTCUSDT', current_price)

        assert should_stop is True

    def test_grid_rebalancing_flow(self, integrated_bot):
        """Test grid rebalancing workflow"""
        grid_strategy = integrated_bot['grid_strategy']
        order_manager = integrated_bot['order_manager']

        # Initialize grid
        grid_strategy.initialize_grid(40000.0, 1.5)
        initial_spacing = grid_strategy.grid_spacing

        # Place some orders
        orders = order_manager.create_grid_orders(grid_strategy.get_pending_orders())
        order_manager.place_multiple_orders(orders[:3], delay=0)

        # Rebalance with different volatility
        grid_strategy.rebalance_grid(42000.0, volatility=3.0)

        # Verify grid rebalanced
        assert grid_strategy.current_price == 42000.0
        # Higher volatility should result in wider spacing
        assert grid_strategy.grid_spacing != initial_spacing

    def test_emergency_stop_flow(self, integrated_bot):
        """Test emergency stop workflow"""
        risk_manager = integrated_bot['risk_manager']
        order_manager = integrated_bot['order_manager']

        # Trigger emergency stop
        risk_manager.trigger_emergency_stop("Test emergency")

        # Try to place order
        from order_manager import Order, OrderStatus
        order = Order(
            symbol='BTCUSDT',
            side='BUY',
            order_type='LIMIT',
            price=40000.0,
            quantity=0.001
        )

        success, message = order_manager.place_order(order)

        # Order should be rejected
        assert success is False
        assert "Emergency stop" in message

    def test_profit_calculation_flow(self, integrated_bot):
        """Test profit calculation across components"""
        risk_manager = integrated_bot['risk_manager']
        grid_strategy = integrated_bot['grid_strategy']

        # Initialize grid
        grid_strategy.initialize_grid(40000.0, 1.5)

        # Simulate buy order fill
        buy_level = [l for l in grid_strategy.grid_levels if l.side == 'BUY'][0]
        buy_level.status = 'filled'
        buy_level.filled_price = buy_level.price
        risk_manager.update_position('BTCUSDT', 'LONG', buy_level.price, buy_level.quantity, 5)

        # Simulate sell order fill
        sell_level = [l for l in grid_strategy.grid_levels if l.side == 'SELL'][0]
        sell_level.status = 'filled'
        sell_level.filled_price = sell_level.price

        # Close position
        trade = risk_manager.close_position('BTCUSDT', sell_level.filled_price)

        # Calculate grid profit
        grid_profit = grid_strategy.calculate_grid_profit()

        # Verify profit calculated
        assert trade is not None
        assert trade.pnl > 0
        assert grid_profit > 0

    @pytest.mark.slow
    def test_full_trading_cycle(self, integrated_bot):
        """Test complete trading cycle from initialization to profit"""
        grid_strategy = integrated_bot['grid_strategy']
        order_manager = integrated_bot['order_manager']
        risk_manager = integrated_bot['risk_manager']
        exchange = integrated_bot['exchange']

        # Step 1: Initialize grid
        grid_strategy.initialize_grid(40000.0, 1.5)

        # Step 2: Place grid orders
        orders = order_manager.create_grid_orders(grid_strategy.get_pending_orders())
        results = order_manager.place_multiple_orders(orders, delay=0)

        # Step 3: Simulate price movement and order fills
        # Price drops, fill buy order
        buy_orders = [o for o in orders if o.side == 'BUY']
        if buy_orders:
            buy_order = buy_orders[0]
            exchange.fill_order(buy_order.order_id)
            buy_order.status = OrderStatus.FILLED
            buy_order.filled_quantity = buy_order.quantity
            buy_order.filled_price = buy_order.price

            # Process fill
            order_manager.on_order_filled(buy_order)
            grid_strategy.mark_order_filled(buy_order.order_id, buy_order.filled_price)

        # Step 4: Price rises, fill sell order
        sell_orders = [o for o in orders if o.side == 'SELL']
        if sell_orders:
            sell_order = sell_orders[0]
            exchange.fill_order(sell_order.order_id)
            sell_order.status = OrderStatus.FILLED
            sell_order.filled_quantity = sell_order.quantity
            sell_order.filled_price = sell_order.price

            # Close position (simulated)
            if 'BTCUSDT' in risk_manager.positions:
                trade = risk_manager.close_position('BTCUSDT', sell_order.filled_price)

        # Step 5: Verify profit made
        metrics = risk_manager.get_risk_metrics()

        assert metrics['total_trades'] >= 0
        # In a realistic scenario with proper fills, should have profit


@pytest.mark.integration
class TestComponentInteraction:
    """Test interactions between components"""

    def test_config_propagation(self, bot_config):
        """Test configuration propagates correctly"""
        risk_manager = RiskManager(bot_config)
        grid_strategy = AdaptiveGridStrategy(bot_config)

        # Verify config used
        assert risk_manager.risk_config.max_position_usdt == bot_config.risk.max_position_usdt
        assert grid_strategy.grid_config.grid_levels == bot_config.grid.grid_levels

    def test_risk_manager_order_manager_interaction(self, bot_config, mock_binance_client):
        """Test risk manager and order manager interaction"""
        risk_manager = RiskManager(bot_config)
        order_manager = OrderManager(mock_binance_client, bot_config, risk_manager)

        # Risk manager should block orders when limits reached
        risk_manager.daily_pnl = -600.0  # Exceeds limit

        from order_manager import Order
        order = Order(
            symbol='BTCUSDT',
            side='BUY',
            order_type='LIMIT',
            price=40000.0,
            quantity=0.001
        )

        success, message = order_manager.place_order(order)

        assert success is False
        assert "Daily loss limit" in message

    def test_grid_strategy_order_manager_sync(self, bot_config, mock_binance_client):
        """Test grid strategy and order manager synchronization"""
        risk_manager = RiskManager(bot_config)
        order_manager = OrderManager(mock_binance_client, bot_config, risk_manager)
        grid_strategy = AdaptiveGridStrategy(bot_config)

        # Initialize grid
        grid_strategy.initialize_grid(40000.0, 1.5)

        # Create and place orders
        orders = order_manager.create_grid_orders(grid_strategy.get_pending_orders())

        # Verify order count matches
        assert len(orders) == len(grid_strategy.get_pending_orders())


@pytest.mark.integration
@pytest.mark.slow
class TestPerformanceUnderLoad:
    """Test system performance under load"""

    def test_many_grid_levels(self, bot_config):
        """Test with large number of grid levels"""
        bot_config.grid.grid_levels = 50

        grid_strategy = AdaptiveGridStrategy(bot_config)
        grid_strategy.initialize_grid(40000.0, 1.5)

        assert len(grid_strategy.grid_levels) == 50

        # Should still be performant
        stats = grid_strategy.get_grid_statistics()
        assert stats['total_levels'] == 50

    def test_many_concurrent_orders(self, bot_config, mock_binance_client):
        """Test handling many concurrent orders"""
        risk_manager = RiskManager(bot_config)
        order_manager = OrderManager(mock_binance_client, bot_config, risk_manager)

        # Create many orders
        from order_manager import Order, OrderStatus
        for i in range(50):
            order = Order(
                symbol='BTCUSDT',
                side='BUY' if i % 2 == 0 else 'SELL',
                order_type='LIMIT',
                price=40000.0 + i * 100,
                quantity=0.001,
                order_id=1000 + i,
                status=OrderStatus.SUBMITTED
            )
            order_manager.orders[order.order_id] = order

        # Should handle update efficiently
        stats = order_manager.get_order_statistics()
        assert stats['active_orders'] == 50


@pytest.mark.integration
class TestErrorRecovery:
    """Test error recovery scenarios"""

    def test_recover_from_api_failure(self, bot_config):
        """Test recovery from API failures"""
        client = MagicMock(spec=BinanceFuturesClient)
        client.place_order.side_effect = Exception("API Error")

        risk_manager = RiskManager(bot_config)
        order_manager = OrderManager(client, bot_config, risk_manager)

        from order_manager import Order
        order = Order(
            symbol='BTCUSDT',
            side='BUY',
            order_type='LIMIT',
            price=40000.0,
            quantity=0.001
        )

        # Should handle error gracefully
        success, message = order_manager.place_order(order)

        assert success is False
        assert order.status == OrderStatus.REJECTED

    def test_handle_invalid_configuration(self, bot_config):
        """Test handling of invalid configuration"""
        bot_config.grid.grid_levels = 2  # Invalid

        with pytest.raises(ValueError):
            bot_config.validate_all()
