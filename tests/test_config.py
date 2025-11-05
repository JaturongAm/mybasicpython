"""
Unit tests for configuration management
"""
import pytest
import json
import os
from config import BotConfig, APIConfig, GridConfig, RiskConfig, MonitoringConfig


class TestAPIConfig:
    """Test API configuration"""

    def test_api_config_creation(self, api_config):
        """Test API config object creation"""
        assert api_config.api_key == "test_api_key"
        assert api_config.api_secret == "test_api_secret"
        assert api_config.testnet is True

    def test_api_config_validation_success(self, api_config):
        """Test valid API config passes validation"""
        assert api_config.validate() is True

    def test_api_config_validation_failure(self):
        """Test invalid API config fails validation"""
        config = APIConfig(api_key="", api_secret="")
        with pytest.raises(ValueError, match="API key and secret must be provided"):
            config.validate()

    def test_api_config_from_environment(self, monkeypatch):
        """Test API config from environment variables"""
        monkeypatch.setenv('BINANCE_API_KEY', 'env_key')
        monkeypatch.setenv('BINANCE_API_SECRET', 'env_secret')
        monkeypatch.setenv('BINANCE_TESTNET', 'False')

        config = APIConfig()
        assert config.api_key == 'env_key'
        assert config.api_secret == 'env_secret'
        assert config.testnet is False


class TestGridConfig:
    """Test grid configuration"""

    def test_grid_config_creation(self, grid_config):
        """Test grid config object creation"""
        assert grid_config.symbol == "BTCUSDT"
        assert grid_config.grid_levels == 10
        assert grid_config.grid_spacing_percent == 0.5
        assert grid_config.leverage == 5

    def test_grid_config_validation_success(self, grid_config):
        """Test valid grid config passes validation"""
        assert grid_config.validate() is True

    def test_grid_config_validation_min_levels(self):
        """Test grid config validation fails with too few levels"""
        config = GridConfig(grid_levels=3)
        with pytest.raises(ValueError, match="Grid levels must be at least 5"):
            config.validate()

    def test_grid_config_validation_leverage_range(self):
        """Test grid config validation fails with invalid leverage"""
        config = GridConfig(leverage=150)
        with pytest.raises(ValueError, match="Leverage must be between 1 and 125"):
            config.validate()

    def test_grid_config_validation_positive_quantity(self):
        """Test grid config validation fails with negative quantity"""
        config = GridConfig(order_quantity_usdt=-100)
        with pytest.raises(ValueError, match="Order quantity must be positive"):
            config.validate()

    @pytest.mark.parametrize("leverage,expected", [
        (1, True),
        (5, True),
        (125, True),
    ])
    def test_grid_config_leverage_edge_cases(self, leverage, expected):
        """Test grid config leverage edge cases"""
        config = GridConfig(leverage=leverage)
        assert config.validate() == expected


class TestRiskConfig:
    """Test risk configuration"""

    def test_risk_config_creation(self, risk_config):
        """Test risk config object creation"""
        assert risk_config.max_position_usdt == 5000.0
        assert risk_config.max_drawdown_percent == 15.0
        assert risk_config.stop_loss_percent == 5.0

    def test_risk_config_validation_success(self, risk_config):
        """Test valid risk config passes validation"""
        assert risk_config.validate() is True

    def test_risk_config_validation_positive_position(self):
        """Test risk config validation fails with negative position"""
        config = RiskConfig(max_position_usdt=-1000)
        with pytest.raises(ValueError, match="Max position size must be positive"):
            config.validate()

    def test_risk_config_validation_drawdown_range(self):
        """Test risk config validation fails with invalid drawdown"""
        config = RiskConfig(max_drawdown_percent=60)
        with pytest.raises(ValueError, match="Max drawdown must be between 0 and 50%"):
            config.validate()

    @pytest.mark.parametrize("drawdown,valid", [
        (0.1, True),
        (25.0, True),
        (50.0, True),
        (0, False),
        (51, False),
    ])
    def test_risk_config_drawdown_edge_cases(self, drawdown, valid):
        """Test risk config drawdown edge cases"""
        config = RiskConfig(max_drawdown_percent=drawdown)
        if valid:
            assert config.validate() is True
        else:
            with pytest.raises(ValueError):
                config.validate()


class TestBotConfig:
    """Test complete bot configuration"""

    def test_bot_config_creation(self, bot_config):
        """Test bot config object creation"""
        assert isinstance(bot_config.api, APIConfig)
        assert isinstance(bot_config.grid, GridConfig)
        assert isinstance(bot_config.risk, RiskConfig)
        assert isinstance(bot_config.monitoring, MonitoringConfig)

    def test_bot_config_validate_all(self, bot_config):
        """Test bot config validates all sub-configs"""
        assert bot_config.validate_all() is True

    def test_bot_config_to_dict(self, bot_config):
        """Test bot config serialization to dict"""
        config_dict = bot_config.to_dict()

        assert 'grid' in config_dict
        assert 'risk' in config_dict
        assert 'monitoring' in config_dict

        assert config_dict['grid']['symbol'] == 'BTCUSDT'
        assert config_dict['risk']['max_position_usdt'] == 5000.0

    def test_bot_config_save_to_file(self, bot_config, tmp_path):
        """Test bot config save to file"""
        config_file = tmp_path / "test_config.json"
        bot_config.save_to_file(str(config_file))

        assert config_file.exists()

        with open(config_file, 'r') as f:
            loaded_data = json.load(f)

        assert loaded_data['grid']['symbol'] == 'BTCUSDT'

    def test_bot_config_load_from_file(self, temp_config_file):
        """Test bot config load from file"""
        config = BotConfig(config_file=temp_config_file)

        assert config.grid.symbol == 'BTCUSDT'
        assert config.grid.grid_levels == 10

    def test_bot_config_load_from_nonexistent_file(self):
        """Test bot config with nonexistent file uses defaults"""
        config = BotConfig(config_file="nonexistent.json")

        # Should use default values
        assert isinstance(config.grid, GridConfig)

    def test_bot_config_partial_update(self, bot_config, tmp_path):
        """Test bot config partial update from file"""
        # Save partial config
        config_file = tmp_path / "partial_config.json"
        partial_config = {
            'grid': {
                'symbol': 'ETHUSDT',
                'grid_levels': 15
            }
        }
        with open(config_file, 'w') as f:
            json.dump(partial_config, f)

        # Load config
        config = BotConfig(config_file=str(config_file))

        # Updated values
        assert config.grid.symbol == 'ETHUSDT'
        assert config.grid.grid_levels == 15

        # Default values remain
        assert config.grid.leverage == 5  # default value

    def test_bot_config_invalid_api_fails_validation(self, bot_config):
        """Test bot config with invalid API fails validation"""
        bot_config.api.api_key = ""
        bot_config.api.api_secret = ""

        with pytest.raises(ValueError):
            bot_config.validate_all()

    def test_bot_config_invalid_grid_fails_validation(self, bot_config):
        """Test bot config with invalid grid fails validation"""
        bot_config.grid.grid_levels = 2

        with pytest.raises(ValueError):
            bot_config.validate_all()

    def test_bot_config_invalid_risk_fails_validation(self, bot_config):
        """Test bot config with invalid risk fails validation"""
        bot_config.risk.max_position_usdt = -1000

        with pytest.raises(ValueError):
            bot_config.validate_all()


class TestMonitoringConfig:
    """Test monitoring configuration"""

    def test_monitoring_config_defaults(self):
        """Test monitoring config default values"""
        config = MonitoringConfig()

        assert config.log_level == "INFO"
        assert config.log_file == "grid_bot.log"
        assert config.enable_telegram is False
        assert config.track_metrics is True

    def test_monitoring_config_telegram_from_env(self, monkeypatch):
        """Test monitoring config loads telegram from environment"""
        monkeypatch.setenv('TELEGRAM_TOKEN', 'test_token')
        monkeypatch.setenv('TELEGRAM_CHAT_ID', 'test_chat_id')

        config = MonitoringConfig()

        assert config.telegram_token == 'test_token'
        assert config.telegram_chat_id == 'test_chat_id'


@pytest.mark.parametrize("symbol,valid", [
    ("BTCUSDT", True),
    ("ETHUSDT", True),
    ("BNBUSDT", True),
])
def test_valid_symbols(symbol, valid, bot_config):
    """Test various valid trading symbols"""
    bot_config.grid.symbol = symbol
    assert bot_config.validate_all() == valid


@pytest.mark.parametrize("leverage,quantity,levels", [
    (1, 10, 5),
    (5, 100, 10),
    (10, 50, 20),
    (20, 200, 30),
])
def test_config_combinations(leverage, quantity, levels, bot_config):
    """Test various configuration combinations"""
    bot_config.grid.leverage = leverage
    bot_config.grid.order_quantity_usdt = quantity
    bot_config.grid.grid_levels = levels

    assert bot_config.validate_all() is True
