"""
Pytest configuration and fixtures for grid bot tests
"""
import pytest
import json
import os
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BotConfig, APIConfig, GridConfig, RiskConfig
from binance_client import BinanceFuturesClient
from grid_strategy import AdaptiveGridStrategy, GridLevel, VolatilityCalculator
from risk_manager import RiskManager, Position
from order_manager import OrderManager, Order, OrderStatus
from monitoring import PerformanceTracker, StateManager


# ==================== Configuration Fixtures ====================

@pytest.fixture
def api_config():
    """API configuration fixture"""
    return APIConfig(
        api_key="test_api_key",
        api_secret="test_api_secret",
        testnet=True
    )


@pytest.fixture
def grid_config():
    """Grid configuration fixture"""
    return GridConfig(
        symbol="BTCUSDT",
        grid_levels=10,
        grid_spacing_percent=0.5,
        order_quantity_usdt=100.0,
        leverage=5,
        adaptive_mode=True,
        volatility_window=24
    )


@pytest.fixture
def risk_config():
    """Risk configuration fixture"""
    return RiskConfig(
        max_position_usdt=5000.0,
        max_drawdown_percent=15.0,
        stop_loss_percent=5.0,
        take_profit_percent=10.0,
        max_daily_loss_usdt=500.0,
        max_open_orders=20
    )


@pytest.fixture
def bot_config(api_config, grid_config, risk_config):
    """Complete bot configuration fixture"""
    config = BotConfig()
    config.api = api_config
    config.grid = grid_config
    config.risk = risk_config
    return config


# ==================== API Client Fixtures ====================

@pytest.fixture
def mock_response():
    """Mock HTTP response"""
    mock = Mock()
    mock.status_code = 200
    mock.json.return_value = {"success": True}
    return mock


@pytest.fixture
def mock_binance_client(api_config):
    """Mock Binance client"""
    with patch('binance_client.requests.Session') as mock_session:
        client = BinanceFuturesClient(
            api_key=api_config.api_key,
            api_secret=api_config.api_secret,
            testnet=api_config.testnet
        )
        client.session = MagicMock()
        yield client


@pytest.fixture
def binance_test_responses():
    """Common Binance API response templates"""
    return {
        'account_info': {
            'assets': [
                {'asset': 'USDT', 'availableBalance': '10000.00', 'walletBalance': '10000.00'}
            ],
            'totalWalletBalance': '10000.00'
        },
        'ticker_price': {
            'symbol': 'BTCUSDT',
            'price': '40000.00'
        },
        'order_response': {
            'orderId': 12345,
            'clientOrderId': 'test_order_123',
            'symbol': 'BTCUSDT',
            'status': 'NEW',
            'side': 'BUY',
            'type': 'LIMIT',
            'price': '40000.00',
            'origQty': '0.001',
            'executedQty': '0.0'
        },
        'position_info': [
            {
                'symbol': 'BTCUSDT',
                'positionAmt': '0.001',
                'entryPrice': '40000.00',
                'unRealizedProfit': '10.00'
            }
        ],
        'klines': [
            [1609459200000, '40000.0', '41000.0', '39500.0', '40500.0', '100.0'],
            [1609462800000, '40500.0', '41500.0', '40000.0', '41000.0', '110.0'],
            [1609466400000, '41000.0', '42000.0', '40500.0', '41500.0', '120.0']
        ]
    }


# ==================== Strategy Fixtures ====================

@pytest.fixture
def volatility_calculator():
    """Volatility calculator fixture"""
    calc = VolatilityCalculator(window_size=24)
    # Add some sample prices
    prices = [40000, 40100, 39900, 40200, 40000, 40300, 39800, 40100]
    for i, price in enumerate(prices):
        calc.add_price(price, datetime.now())
    return calc


@pytest.fixture
def grid_strategy(bot_config):
    """Grid strategy fixture"""
    strategy = AdaptiveGridStrategy(bot_config)
    strategy.initialize_grid(current_price=40000.0, volatility=1.5)
    return strategy


@pytest.fixture
def sample_grid_levels():
    """Sample grid levels for testing"""
    return [
        GridLevel(price=39500.0, quantity=0.0025, side='BUY'),
        GridLevel(price=39750.0, quantity=0.0025, side='BUY'),
        GridLevel(price=40000.0, quantity=0.0025, side='BUY'),
        GridLevel(price=40250.0, quantity=0.0025, side='SELL'),
        GridLevel(price=40500.0, quantity=0.0025, side='SELL'),
    ]


# ==================== Risk Manager Fixtures ====================

@pytest.fixture
def risk_manager(bot_config):
    """Risk manager fixture"""
    return RiskManager(bot_config)


@pytest.fixture
def sample_position():
    """Sample position for testing"""
    return Position(
        symbol='BTCUSDT',
        side='LONG',
        entry_price=40000.0,
        quantity=0.01,
        leverage=5,
        timestamp=datetime.now()
    )


# ==================== Order Manager Fixtures ====================

@pytest.fixture
def order_manager(mock_binance_client, bot_config, risk_manager):
    """Order manager fixture"""
    return OrderManager(mock_binance_client, bot_config, risk_manager)


@pytest.fixture
def sample_order():
    """Sample order for testing"""
    return Order(
        symbol='BTCUSDT',
        side='BUY',
        order_type='LIMIT',
        price=40000.0,
        quantity=0.001,
        status=OrderStatus.PENDING
    )


@pytest.fixture
def sample_filled_order():
    """Sample filled order for testing"""
    order = Order(
        symbol='BTCUSDT',
        side='BUY',
        order_type='LIMIT',
        price=40000.0,
        quantity=0.001,
        order_id=12345,
        status=OrderStatus.FILLED,
        filled_quantity=0.001,
        filled_price=40000.0
    )
    order.updated_time = datetime.now()
    return order


# ==================== Monitoring Fixtures ====================

@pytest.fixture
def performance_tracker(bot_config):
    """Performance tracker fixture"""
    return PerformanceTracker(bot_config)


@pytest.fixture
def state_manager(bot_config, tmp_path):
    """State manager fixture with temporary directory"""
    config = bot_config
    state_manager = StateManager(config)
    # Use temporary directory for testing
    state_manager.state_file = tmp_path / "bot_state.json"
    return state_manager


# ==================== Market Data Fixtures ====================

@pytest.fixture
def sample_market_data():
    """Sample market data for testing"""
    return {
        'current_price': 40000.0,
        'high_24h': 42000.0,
        'low_24h': 38000.0,
        'volume_24h': 1000.0,
        'price_change_24h': 2.5,
        'volatility': 1.5
    }


@pytest.fixture
def price_series():
    """Price series for volatility testing"""
    import numpy as np
    # Generate realistic price series with some volatility
    base_price = 40000
    returns = np.random.normal(0, 0.015, 100)  # 1.5% daily volatility
    prices = base_price * np.exp(np.cumsum(returns))
    return prices.tolist()


# ==================== Utility Fixtures ====================

@pytest.fixture
def mock_time():
    """Mock time for testing"""
    with patch('time.time') as mock:
        mock.return_value = 1609459200.0  # 2021-01-01 00:00:00
        yield mock


@pytest.fixture
def mock_datetime():
    """Mock datetime for testing"""
    with patch('datetime.datetime') as mock:
        mock.now.return_value = datetime(2021, 1, 1, 0, 0, 0)
        yield mock


@pytest.fixture
def temp_config_file(tmp_path, bot_config):
    """Temporary configuration file"""
    config_file = tmp_path / "test_config.json"
    config_data = bot_config.to_dict()
    with open(config_file, 'w') as f:
        json.dump(config_data, f)
    return str(config_file)


# ==================== Test Helpers ====================

class MockExchange:
    """Mock exchange for integration testing"""

    def __init__(self):
        self.orders = {}
        self.positions = {}
        self.current_price = 40000.0
        self.order_id_counter = 1000

    def place_order(self, symbol, side, order_type, quantity, price, time_in_force=None, **kwargs):
        """Simulate order placement"""
        order_id = self.order_id_counter
        self.order_id_counter += 1

        self.orders[order_id] = {
            'orderId': order_id,
            'symbol': symbol,
            'side': side,
            'type': order_type,
            'quantity': quantity,
            'price': price,
            'status': 'NEW',
            'timeInForce': time_in_force or 'GTC'
        }
        return self.orders[order_id]

    def fill_order(self, order_id):
        """Simulate order fill"""
        if order_id in self.orders:
            self.orders[order_id]['status'] = 'FILLED'
            self.orders[order_id]['executedQty'] = self.orders[order_id]['quantity']

    def set_price(self, price):
        """Set current market price"""
        self.current_price = price


@pytest.fixture
def mock_exchange():
    """Mock exchange fixture"""
    return MockExchange()


# ==================== Parametrize Helpers ====================

def pytest_configure(config):
    """Add custom markers"""
    config.addinivalue_line(
        "markers", "unit: Unit tests"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests"
    )
    config.addinivalue_line(
        "markers", "slow: Slow tests"
    )
    config.addinivalue_line(
        "markers", "requires_api: Tests requiring API access"
    )
