"""
Configuration management for Institutional Adaptive Grid Bot
"""
import os
from typing import Dict, Any
from dataclasses import dataclass, field
import json


@dataclass
class APIConfig:
    """Binance API configuration"""
    api_key: str = field(default_factory=lambda: os.getenv('BINANCE_API_KEY', ''))
    api_secret: str = field(default_factory=lambda: os.getenv('BINANCE_API_SECRET', ''))
    testnet: bool = field(default_factory=lambda: os.getenv('BINANCE_TESTNET', 'True').lower() == 'true')

    def validate(self) -> bool:
        """Validate API configuration"""
        if not self.api_key or not self.api_secret:
            raise ValueError("API key and secret must be provided via environment variables")
        return True


@dataclass
class GridConfig:
    """Grid trading strategy configuration"""
    symbol: str = "BTCUSDT"
    grid_levels: int = 20  # Number of grid levels
    grid_spacing_percent: float = 0.5  # Initial spacing between grid levels (%)
    upper_price: float = None  # Will be calculated dynamically if None
    lower_price: float = None  # Will be calculated dynamically if None
    order_quantity_usdt: float = 100.0  # USDT per grid level
    leverage: int = 5

    # Adaptive parameters
    adaptive_mode: bool = True
    volatility_window: int = 24  # Hours for volatility calculation
    min_grid_spacing: float = 0.2  # Minimum spacing (%)
    max_grid_spacing: float = 2.0  # Maximum spacing (%)
    rebalance_interval: int = 3600  # Seconds between grid rebalancing

    def validate(self) -> bool:
        """Validate grid configuration"""
        if self.grid_levels < 5:
            raise ValueError("Grid levels must be at least 5")
        if self.leverage < 1 or self.leverage > 125:
            raise ValueError("Leverage must be between 1 and 125")
        if self.order_quantity_usdt <= 0:
            raise ValueError("Order quantity must be positive")
        return True


@dataclass
class RiskConfig:
    """Risk management configuration"""
    max_position_usdt: float = 10000.0  # Maximum position size
    max_drawdown_percent: float = 15.0  # Max drawdown before stopping
    stop_loss_percent: float = 5.0  # Stop loss per position
    take_profit_percent: float = 10.0  # Take profit target
    max_daily_loss_usdt: float = 500.0  # Max loss per day

    # Position limits
    max_open_orders: int = 40
    min_order_spacing_percent: float = 0.1  # Minimum spacing between orders

    def validate(self) -> bool:
        """Validate risk configuration"""
        if self.max_position_usdt <= 0:
            raise ValueError("Max position size must be positive")
        if self.max_drawdown_percent <= 0 or self.max_drawdown_percent > 50:
            raise ValueError("Max drawdown must be between 0 and 50%")
        return True


@dataclass
class MonitoringConfig:
    """Monitoring and logging configuration"""
    log_level: str = "INFO"
    log_file: str = "grid_bot.log"
    enable_telegram: bool = False
    telegram_token: str = field(default_factory=lambda: os.getenv('TELEGRAM_TOKEN', ''))
    telegram_chat_id: str = field(default_factory=lambda: os.getenv('TELEGRAM_CHAT_ID', ''))

    # Performance tracking
    track_metrics: bool = True
    metrics_interval: int = 300  # Seconds between metrics logging
    save_state_interval: int = 60  # Seconds between state persistence


class BotConfig:
    """Main bot configuration"""

    def __init__(self, config_file: str = None):
        self.api = APIConfig()
        self.grid = GridConfig()
        self.risk = RiskConfig()
        self.monitoring = MonitoringConfig()

        if config_file and os.path.exists(config_file):
            self.load_from_file(config_file)

    def load_from_file(self, config_file: str):
        """Load configuration from JSON file"""
        with open(config_file, 'r') as f:
            config_data = json.load(f)

        # Update configurations
        if 'grid' in config_data:
            for key, value in config_data['grid'].items():
                if hasattr(self.grid, key):
                    setattr(self.grid, key, value)

        if 'risk' in config_data:
            for key, value in config_data['risk'].items():
                if hasattr(self.risk, key):
                    setattr(self.risk, key, value)

        if 'monitoring' in config_data:
            for key, value in config_data['monitoring'].items():
                if hasattr(self.monitoring, key):
                    setattr(self.monitoring, key, value)

    def validate_all(self) -> bool:
        """Validate all configurations"""
        self.api.validate()
        self.grid.validate()
        self.risk.validate()
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            'grid': {
                'symbol': self.grid.symbol,
                'grid_levels': self.grid.grid_levels,
                'grid_spacing_percent': self.grid.grid_spacing_percent,
                'order_quantity_usdt': self.grid.order_quantity_usdt,
                'leverage': self.grid.leverage,
                'adaptive_mode': self.grid.adaptive_mode,
                'volatility_window': self.grid.volatility_window,
                'rebalance_interval': self.grid.rebalance_interval,
            },
            'risk': {
                'max_position_usdt': self.risk.max_position_usdt,
                'max_drawdown_percent': self.risk.max_drawdown_percent,
                'stop_loss_percent': self.risk.stop_loss_percent,
                'max_daily_loss_usdt': self.risk.max_daily_loss_usdt,
                'max_open_orders': self.risk.max_open_orders,
            },
            'monitoring': {
                'log_level': self.monitoring.log_level,
                'track_metrics': self.monitoring.track_metrics,
            }
        }

    def save_to_file(self, config_file: str):
        """Save configuration to JSON file"""
        with open(config_file, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
