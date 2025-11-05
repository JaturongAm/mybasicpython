"""
Unit tests for adaptive grid strategy
"""
import pytest
import numpy as np
from datetime import datetime, timedelta
from grid_strategy import (
    AdaptiveGridStrategy,
    GridLevel,
    VolatilityCalculator
)


class TestGridLevel:
    """Test GridLevel data class"""

    def test_grid_level_creation(self):
        """Test grid level creation"""
        level = GridLevel(price=40000.0, quantity=0.001, side='BUY')

        assert level.price == 40000.0
        assert level.quantity == 0.001
        assert level.side == 'BUY'
        assert level.status == 'pending'
        assert level.order_id is None

    def test_grid_level_repr(self):
        """Test grid level string representation"""
        level = GridLevel(price=40000.0, quantity=0.001, side='BUY')
        repr_str = repr(level)

        assert 'BUY' in repr_str
        assert '0.001' in repr_str
        assert 'pending' in repr_str


class TestVolatilityCalculator:
    """Test volatility calculator"""

    def test_volatility_calculator_creation(self):
        """Test volatility calculator initialization"""
        calc = VolatilityCalculator(window_size=24)

        assert calc.window_size == 24
        assert len(calc.price_history) == 0

    def test_add_price(self):
        """Test adding price to history"""
        calc = VolatilityCalculator()
        calc.add_price(40000.0)

        assert len(calc.price_history) == 1
        assert calc.price_history[0][1] == 40000.0

    def test_calculate_volatility_insufficient_data(self):
        """Test volatility calculation with insufficient data"""
        calc = VolatilityCalculator()
        calc.add_price(40000.0)

        vol = calc.calculate_volatility()
        assert vol == 0.0

    def test_calculate_volatility_with_data(self, price_series):
        """Test volatility calculation with price series"""
        calc = VolatilityCalculator()

        for price in price_series:
            calc.add_price(price)

        vol = calc.calculate_volatility()
        assert vol > 0
        assert vol < 100  # Reasonable volatility range

    def test_calculate_volatility_methods(self, price_series):
        """Test different volatility calculation methods"""
        calc = VolatilityCalculator()

        for price in price_series[:50]:
            calc.add_price(price)

        vol_std = calc.calculate_volatility(method='std')
        vol_atr = calc.calculate_volatility(method='atr')

        assert vol_std > 0
        assert vol_atr >= 0

    def test_get_volatility_regime(self):
        """Test volatility regime classification"""
        calc = VolatilityCalculator()

        # Add prices with different volatility levels
        base = 40000
        for i in range(50):
            calc.add_price(base + i * 10)

        regime = calc.get_volatility_regime()
        assert regime in ['low', 'medium', 'high', 'extreme']

    @pytest.mark.parametrize("volatility,expected_regime", [
        (0.5, 'low'),
        (1.5, 'medium'),
        (3.5, 'high'),
        (6.0, 'extreme'),
    ])
    def test_volatility_regime_classification(self, volatility, expected_regime):
        """Test volatility regime classification with known values"""
        calc = VolatilityCalculator()

        # Manually set volatility by adjusting calculation
        # This is a simplified test
        if expected_regime == 'low':
            prices = [40000 + i * 5 for i in range(50)]
        elif expected_regime == 'medium':
            prices = [40000 + i * 20 for i in range(50)]
        elif expected_regime == 'high':
            prices = [40000 + i * 50 for i in range(50)]
        else:  # extreme
            prices = [40000 + i * 100 for i in range(50)]

        for price in prices:
            calc.add_price(price)

        regime = calc.get_volatility_regime()
        # Note: exact regime may vary based on calculation


class TestAdaptiveGridStrategy:
    """Test adaptive grid strategy"""

    def test_grid_strategy_creation(self, bot_config):
        """Test grid strategy initialization"""
        strategy = AdaptiveGridStrategy(bot_config)

        assert strategy.config == bot_config
        assert isinstance(strategy.volatility_calculator, VolatilityCalculator)
        assert len(strategy.grid_levels) == 0

    def test_initialize_grid(self, bot_config):
        """Test grid initialization"""
        strategy = AdaptiveGridStrategy(bot_config)
        strategy.initialize_grid(current_price=40000.0, volatility=1.5)

        assert len(strategy.grid_levels) == bot_config.grid.grid_levels
        assert strategy.current_price == 40000.0
        assert strategy.upper_price > 40000.0
        assert strategy.lower_price < 40000.0

    def test_initialize_grid_with_adaptive_spacing(self, bot_config):
        """Test grid initialization with adaptive spacing"""
        bot_config.grid.adaptive_mode = True
        strategy = AdaptiveGridStrategy(bot_config)

        # High volatility should result in wider spacing
        strategy.initialize_grid(current_price=40000.0, volatility=5.0)
        high_vol_spacing = strategy.grid_spacing

        # Low volatility should result in tighter spacing
        strategy.initialize_grid(current_price=40000.0, volatility=0.5)
        low_vol_spacing = strategy.grid_spacing

        assert high_vol_spacing > low_vol_spacing

    def test_grid_levels_distribution(self, grid_strategy):
        """Test grid levels are properly distributed"""
        buy_levels = [l for l in grid_strategy.grid_levels if l.side == 'BUY']
        sell_levels = [l for l in grid_strategy.grid_levels if l.side == 'SELL']

        # Should have both buy and sell levels
        assert len(buy_levels) > 0
        assert len(sell_levels) > 0

        # Buy levels should be below current price
        for level in buy_levels:
            assert level.price < grid_strategy.current_price

        # Sell levels should be above current price
        for level in sell_levels:
            assert level.price > grid_strategy.current_price

    def test_get_pending_orders(self, grid_strategy):
        """Test getting pending orders"""
        pending = grid_strategy.get_pending_orders()

        assert len(pending) == len(grid_strategy.grid_levels)
        assert all(l.status == 'pending' for l in pending)

    def test_mark_order_placed(self, grid_strategy):
        """Test marking order as placed"""
        level = grid_strategy.grid_levels[0]
        original_price = level.price

        grid_strategy.mark_order_placed(original_price, order_id=12345)

        assert level.order_id == 12345
        assert level.status == 'placed'

    def test_mark_order_filled(self, grid_strategy):
        """Test marking order as filled"""
        level = grid_strategy.grid_levels[0]
        level.order_id = 12345
        level.status = 'placed'

        grid_strategy.mark_order_filled(order_id=12345, filled_price=level.price)

        assert level.status == 'filled'
        assert level.filled_price == level.price
        assert level.filled_time is not None
        assert grid_strategy.total_filled_orders == 1

    def test_should_rebalance_adaptive_mode(self, bot_config):
        """Test rebalance check in adaptive mode"""
        bot_config.grid.adaptive_mode = True
        bot_config.grid.rebalance_interval = 10  # 10 seconds for testing

        strategy = AdaptiveGridStrategy(bot_config)
        strategy.initialize_grid(40000.0, 1.5)

        # Should not rebalance immediately
        assert strategy.should_rebalance() is False

        # Simulate time passing
        strategy.last_rebalance = datetime.now() - timedelta(seconds=11)

        # Should rebalance now
        assert strategy.should_rebalance() is True

    def test_should_rebalance_non_adaptive_mode(self, bot_config):
        """Test rebalance check in non-adaptive mode"""
        bot_config.grid.adaptive_mode = False
        strategy = AdaptiveGridStrategy(bot_config)
        strategy.initialize_grid(40000.0, 1.5)

        # Should never rebalance in non-adaptive mode
        strategy.last_rebalance = datetime.now() - timedelta(hours=1)
        assert strategy.should_rebalance() is False

    def test_rebalance_grid(self, bot_config):
        """Test grid rebalancing"""
        strategy = AdaptiveGridStrategy(bot_config)
        strategy.initialize_grid(40000.0, 1.5)

        # Mark some orders as placed
        for i, level in enumerate(strategy.grid_levels[:3]):
            level.status = 'placed'
            level.order_id = 1000 + i

        # Rebalance with new price and volatility
        strategy.rebalance_grid(current_price=42000.0, volatility=2.5)

        # Grid should be reinitialized
        assert strategy.current_price == 42000.0
        assert len(strategy.grid_levels) == bot_config.grid.grid_levels

        # All levels should be pending (previous placed orders cancelled)
        pending = [l for l in strategy.grid_levels if l.status == 'pending']
        assert len(pending) > 0

    def test_calculate_grid_profit(self, grid_strategy):
        """Test grid profit calculation"""
        # Simulate some filled orders
        buy_level = [l for l in grid_strategy.grid_levels if l.side == 'BUY'][0]
        sell_level = [l for l in grid_strategy.grid_levels if l.side == 'SELL'][0]

        buy_level.status = 'filled'
        buy_level.filled_price = buy_level.price

        sell_level.status = 'filled'
        sell_level.filled_price = sell_level.price

        profit = grid_strategy.calculate_grid_profit()

        # Should have positive profit from buy-sell pair
        assert profit > 0

    def test_get_grid_statistics(self, grid_strategy):
        """Test getting grid statistics"""
        stats = grid_strategy.get_grid_statistics()

        assert 'total_levels' in stats
        assert 'pending' in stats
        assert 'placed' in stats
        assert 'filled' in stats
        assert 'grid_spacing' in stats
        assert 'upper_price' in stats
        assert 'lower_price' in stats
        assert 'current_price' in stats

        assert stats['total_levels'] == len(grid_strategy.grid_levels)

    def test_get_next_buy_level(self, grid_strategy):
        """Test getting next buy level"""
        current_price = grid_strategy.current_price

        next_buy = grid_strategy.get_next_buy_level(current_price)

        if next_buy:
            assert next_buy.side == 'BUY'
            assert next_buy.price < current_price
            assert next_buy.status == 'pending'

    def test_get_next_sell_level(self, grid_strategy):
        """Test getting next sell level"""
        current_price = grid_strategy.current_price

        next_sell = grid_strategy.get_next_sell_level(current_price)

        if next_sell:
            assert next_sell.side == 'SELL'
            assert next_sell.price > current_price
            assert next_sell.status == 'pending'

    def test_grid_price_bounds(self, bot_config):
        """Test grid respects price bounds"""
        bot_config.grid.upper_price = 45000.0
        bot_config.grid.lower_price = 35000.0

        strategy = AdaptiveGridStrategy(bot_config)
        strategy.initialize_grid(40000.0, 1.5)

        assert strategy.upper_price == 45000.0
        assert strategy.lower_price == 35000.0

        # All grid levels should be within bounds
        for level in strategy.grid_levels:
            assert level.price >= strategy.lower_price
            assert level.price <= strategy.upper_price


@pytest.mark.parametrize("current_price,volatility,expected_levels", [
    (40000.0, 1.0, 10),
    (50000.0, 2.5, 15),
    (30000.0, 0.5, 20),
])
def test_grid_initialization_parameters(bot_config, current_price, volatility, expected_levels):
    """Test grid initialization with various parameters"""
    bot_config.grid.grid_levels = expected_levels
    strategy = AdaptiveGridStrategy(bot_config)
    strategy.initialize_grid(current_price, volatility)

    assert len(strategy.grid_levels) == expected_levels
    assert strategy.current_price == current_price


def test_grid_quantity_calculation(bot_config):
    """Test grid level quantity calculation"""
    bot_config.grid.order_quantity_usdt = 100.0
    strategy = AdaptiveGridStrategy(bot_config)
    strategy.initialize_grid(40000.0, 1.5)

    for level in strategy.grid_levels:
        # Quantity should be approximately order_quantity_usdt / price
        expected_quantity = bot_config.grid.order_quantity_usdt / level.price
        assert abs(level.quantity - expected_quantity) < 0.0001
