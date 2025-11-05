"""
Adaptive Grid Strategy Engine with volatility-based adjustments
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
from collections import deque


@dataclass
class GridLevel:
    """Represents a single grid level"""
    price: float
    quantity: float
    side: str  # 'BUY' or 'SELL'
    order_id: Optional[int] = None
    status: str = 'pending'  # pending, placed, filled, cancelled
    filled_price: Optional[float] = None
    filled_time: Optional[datetime] = None

    def __repr__(self):
        return f"GridLevel({self.side} {self.quantity} @ {self.price:.2f}, status={self.status})"


class VolatilityCalculator:
    """Calculate and track market volatility"""

    def __init__(self, window_size: int = 24):
        self.window_size = window_size
        self.price_history = deque(maxlen=1000)
        self.logger = logging.getLogger(__name__)

    def add_price(self, price: float, timestamp: datetime = None):
        """Add price to history"""
        if timestamp is None:
            timestamp = datetime.now()
        self.price_history.append((timestamp, price))

    def calculate_volatility(self, method: str = 'std') -> float:
        """Calculate volatility using different methods"""
        if len(self.price_history) < 2:
            return 0.0

        prices = [p[1] for p in self.price_history]
        returns = np.diff(np.log(prices))

        if method == 'std':
            # Standard deviation of returns
            volatility = np.std(returns) * 100
        elif method == 'atr':
            # Average True Range based volatility
            volatility = self._calculate_atr(prices)
        elif method == 'parkinson':
            # Parkinson's volatility (requires high/low data)
            volatility = np.std(returns) * 100
        else:
            volatility = np.std(returns) * 100

        return volatility

    def _calculate_atr(self, prices: List[float], period: int = 14) -> float:
        """Calculate Average True Range"""
        if len(prices) < period + 1:
            return 0.0

        true_ranges = []
        for i in range(1, len(prices)):
            high_low = abs(prices[i] - prices[i-1])
            true_ranges.append(high_low)

        atr = np.mean(true_ranges[-period:]) if len(true_ranges) >= period else np.mean(true_ranges)
        return (atr / prices[-1]) * 100 if prices[-1] > 0 else 0.0

    def get_volatility_regime(self) -> str:
        """Classify current volatility regime"""
        vol = self.calculate_volatility()

        if vol < 1.0:
            return 'low'
        elif vol < 2.5:
            return 'medium'
        elif vol < 5.0:
            return 'high'
        else:
            return 'extreme'


class AdaptiveGridStrategy:
    """Adaptive grid trading strategy with dynamic adjustments"""

    def __init__(self, config):
        self.config = config
        self.grid_config = config.grid
        self.logger = logging.getLogger(__name__)

        self.volatility_calculator = VolatilityCalculator(
            window_size=self.grid_config.volatility_window
        )

        self.grid_levels: List[GridLevel] = []
        self.current_price: float = 0.0
        self.upper_price: float = 0.0
        self.lower_price: float = 0.0
        self.grid_spacing: float = self.grid_config.grid_spacing_percent

        self.last_rebalance: datetime = datetime.now()
        self.total_filled_orders: int = 0
        self.realized_pnl: float = 0.0

    def initialize_grid(self, current_price: float, volatility: float = None):
        """Initialize grid levels based on current price and volatility"""
        self.current_price = current_price

        # Calculate grid spacing based on volatility if adaptive mode is enabled
        if self.grid_config.adaptive_mode and volatility:
            self.grid_spacing = self._calculate_adaptive_spacing(volatility)
        else:
            self.grid_spacing = self.grid_config.grid_spacing_percent

        # Calculate upper and lower bounds
        self._calculate_price_bounds(current_price)

        # Generate grid levels
        self._generate_grid_levels()

        self.logger.info(f"Grid initialized: {len(self.grid_levels)} levels")
        self.logger.info(f"Price range: {self.lower_price:.2f} - {self.upper_price:.2f}")
        self.logger.info(f"Grid spacing: {self.grid_spacing:.2%}")

    def _calculate_adaptive_spacing(self, volatility: float) -> float:
        """Calculate grid spacing based on volatility"""
        # Higher volatility = wider spacing
        # Normalize volatility to spacing range
        min_spacing = self.grid_config.min_grid_spacing
        max_spacing = self.grid_config.max_grid_spacing

        # Volatility typically ranges from 0.5% to 10%
        # Map this to our spacing range
        normalized_vol = np.clip(volatility, 0.5, 10.0)
        spacing = min_spacing + (normalized_vol - 0.5) / 9.5 * (max_spacing - min_spacing)

        self.logger.info(f"Volatility: {volatility:.2f}%, Adaptive spacing: {spacing:.2%}")
        return spacing

    def _calculate_price_bounds(self, current_price: float):
        """Calculate upper and lower price bounds for grid"""
        # If bounds are provided in config, use them
        if self.grid_config.upper_price and self.grid_config.lower_price:
            self.upper_price = self.grid_config.upper_price
            self.lower_price = self.grid_config.lower_price
        else:
            # Calculate bounds based on grid levels and spacing
            total_range = self.grid_spacing * (self.grid_config.grid_levels - 1)
            half_range = total_range / 2

            self.upper_price = current_price * (1 + half_range / 100)
            self.lower_price = current_price * (1 - half_range / 100)

    def _generate_grid_levels(self):
        """Generate grid levels between upper and lower bounds"""
        self.grid_levels.clear()

        # Calculate price increment
        price_range = self.upper_price - self.lower_price
        price_increment = price_range / (self.grid_config.grid_levels - 1)

        # Generate grid levels
        for i in range(self.grid_config.grid_levels):
            price = self.lower_price + (i * price_increment)

            # Determine if this is a buy or sell level
            # Below current price = buy, above = sell
            side = 'BUY' if price < self.current_price else 'SELL'

            # Calculate quantity based on USDT amount
            quantity = self.grid_config.order_quantity_usdt / price

            grid_level = GridLevel(
                price=price,
                quantity=quantity,
                side=side
            )

            self.grid_levels.append(grid_level)

        self.logger.info(f"Generated {len(self.grid_levels)} grid levels")

    def get_pending_orders(self) -> List[GridLevel]:
        """Get grid levels that need orders placed"""
        return [level for level in self.grid_levels if level.status == 'pending']

    def get_active_orders(self) -> List[GridLevel]:
        """Get grid levels with active orders"""
        return [level for level in self.grid_levels if level.status == 'placed']

    def mark_order_placed(self, price: float, order_id: int):
        """Mark a grid level as having an order placed"""
        for level in self.grid_levels:
            if abs(level.price - price) < 0.01:  # Small tolerance for floating point
                level.order_id = order_id
                level.status = 'placed'
                self.logger.debug(f"Order placed for level: {level}")
                break

    def mark_order_filled(self, order_id: int, filled_price: float):
        """Mark a grid level as filled and create opposite order"""
        for level in self.grid_levels:
            if level.order_id == order_id:
                level.status = 'filled'
                level.filled_price = filled_price
                level.filled_time = datetime.now()
                self.total_filled_orders += 1

                self.logger.info(f"Grid order filled: {level}")

                # Create opposite order at next grid level
                self._create_opposite_order(level)
                break

    def _create_opposite_order(self, filled_level: GridLevel):
        """Create opposite order when a grid level is filled"""
        # Find the next grid level in opposite direction
        if filled_level.side == 'BUY':
            # Create SELL order above
            for level in self.grid_levels:
                if level.price > filled_level.price and level.status == 'pending':
                    level.status = 'pending'  # Mark for placement
                    self.logger.debug(f"Created opposite SELL order: {level}")
                    break
        else:
            # Create BUY order below
            for level in reversed(self.grid_levels):
                if level.price < filled_level.price and level.status == 'pending':
                    level.status = 'pending'  # Mark for placement
                    self.logger.debug(f"Created opposite BUY order: {level}")
                    break

    def should_rebalance(self) -> bool:
        """Check if grid should be rebalanced"""
        if not self.grid_config.adaptive_mode:
            return False

        elapsed = (datetime.now() - self.last_rebalance).total_seconds()
        return elapsed >= self.grid_config.rebalance_interval

    def rebalance_grid(self, current_price: float, volatility: float):
        """Rebalance grid levels based on new price and volatility"""
        self.logger.info("Rebalancing grid...")

        # Cancel all pending orders (will be recreated)
        pending_orders = self.get_pending_orders()
        for level in pending_orders:
            level.status = 'cancelled'

        # Reinitialize grid with new parameters
        self.initialize_grid(current_price, volatility)

        self.last_rebalance = datetime.now()

    def calculate_grid_profit(self) -> float:
        """Calculate profit from filled grid orders"""
        profit = 0.0

        # Find matching buy/sell pairs
        filled_buys = [l for l in self.grid_levels if l.side == 'BUY' and l.status == 'filled']
        filled_sells = [l for l in self.grid_levels if l.side == 'SELL' and l.status == 'filled']

        # Calculate profit from each matched pair
        for buy in filled_buys:
            for sell in filled_sells:
                if sell.filled_price and buy.filled_price:
                    pair_profit = (sell.filled_price - buy.filled_price) * buy.quantity
                    profit += pair_profit

        return profit

    def get_grid_statistics(self) -> Dict:
        """Get statistics about grid performance"""
        total_levels = len(self.grid_levels)
        pending = len([l for l in self.grid_levels if l.status == 'pending'])
        placed = len([l for l in self.grid_levels if l.status == 'placed'])
        filled = len([l for l in self.grid_levels if l.status == 'filled'])

        return {
            'total_levels': total_levels,
            'pending': pending,
            'placed': placed,
            'filled': filled,
            'total_filled_orders': self.total_filled_orders,
            'grid_spacing': self.grid_spacing,
            'upper_price': self.upper_price,
            'lower_price': self.lower_price,
            'current_price': self.current_price,
            'grid_profit': self.calculate_grid_profit(),
            'last_rebalance': self.last_rebalance.isoformat()
        }

    def get_next_buy_level(self, current_price: float) -> Optional[GridLevel]:
        """Get the next buy level below current price"""
        buy_levels = [l for l in self.grid_levels
                     if l.side == 'BUY' and l.price < current_price and l.status == 'pending']
        return min(buy_levels, key=lambda x: abs(x.price - current_price)) if buy_levels else None

    def get_next_sell_level(self, current_price: float) -> Optional[GridLevel]:
        """Get the next sell level above current price"""
        sell_levels = [l for l in self.grid_levels
                      if l.side == 'SELL' and l.price > current_price and l.status == 'pending']
        return min(sell_levels, key=lambda x: abs(x.price - current_price)) if sell_levels else None
