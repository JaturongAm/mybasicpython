"""
Unit tests for monitoring and performance tracking
"""
import pytest
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, mock_open
from monitoring import (
    PerformanceMetrics,
    PerformanceTracker,
    BotLogger,
    StateManager,
    StatusDisplay
)


class TestPerformanceMetrics:
    """Test PerformanceMetrics dataclass"""

    def test_performance_metrics_creation(self):
        """Test creating performance metrics"""
        metrics = PerformanceMetrics(
            timestamp="2025-01-01T00:00:00",
            account_balance=10000.0,
            total_pnl=500.0,
            unrealized_pnl=100.0,
            realized_pnl=400.0,
            daily_pnl=50.0,
            total_trades=10,
            win_rate=60.0,
            profit_factor=2.5,
            max_drawdown=5.0,
            current_drawdown=2.0,
            open_positions=2,
            active_orders=5,
            grid_levels_filled=8,
            grid_profit=250.0
        )

        assert metrics.account_balance == 10000.0
        assert metrics.total_pnl == 500.0
        assert metrics.win_rate == 60.0


class TestPerformanceTracker:
    """Test PerformanceTracker functionality"""

    def test_tracker_initialization(self, bot_config, tmp_path):
        """Test performance tracker initialization"""
        # Use tmp_path for testing
        with patch('monitoring.Path') as mock_path:
            mock_metrics_dir = tmp_path / "metrics"
            mock_path.return_value = mock_metrics_dir

            tracker = PerformanceTracker(bot_config)

            assert tracker.config == bot_config
            assert tracker.metrics_history == []
            assert tracker.start_balance is None

    def test_record_metrics(self, bot_config, tmp_path):
        """Test recording performance metrics"""
        tracker = PerformanceTracker(bot_config)
        tracker.metrics_dir = tmp_path / "metrics"
        tracker.metrics_dir.mkdir()

        # Create mock managers
        risk_manager = Mock()
        risk_manager.get_risk_metrics.return_value = {
            'total_unrealized_pnl': 100.0,
            'total_realized_pnl': 400.0,
            'daily_pnl': 50.0,
            'total_trades': 10,
            'win_rate': 60.0,
            'profit_factor': 2.5,
            'max_drawdown': 5.0,
            'current_drawdown': 2.0,
            'open_positions': 2,
            'winning_trades': 6,
            'losing_trades': 4
        }

        order_manager = Mock()
        order_manager.get_order_statistics.return_value = {
            'active_orders': 5,
            'active_buy_orders': 3,
            'active_sell_orders': 2
        }

        grid_strategy = Mock()
        grid_strategy.get_grid_statistics.return_value = {
            'filled': 8,
            'grid_profit': 250.0,
            'total_levels': 10,
            'upper_price': 42000.0,
            'lower_price': 38000.0,
            'current_price': 40000.0,
            'grid_spacing': 0.02
        }

        # Record metrics
        metrics = tracker.record_metrics(10000.0, risk_manager, order_manager, grid_strategy)

        assert metrics.account_balance == 10000.0
        assert metrics.unrealized_pnl == 100.0
        assert metrics.realized_pnl == 400.0
        assert metrics.active_orders == 5
        assert metrics.grid_levels_filled == 8
        assert tracker.start_balance == 10000.0
        assert len(tracker.metrics_history) == 1

    def test_record_metrics_sets_start_balance(self, bot_config, tmp_path):
        """Test that recording metrics sets start balance on first call"""
        tracker = PerformanceTracker(bot_config)
        tracker.metrics_dir = tmp_path / "metrics"
        tracker.metrics_dir.mkdir()

        risk_manager = Mock()
        risk_manager.get_risk_metrics.return_value = {
            'total_unrealized_pnl': 0.0, 'total_realized_pnl': 0.0,
            'daily_pnl': 0.0, 'total_trades': 0, 'win_rate': 0.0,
            'profit_factor': 0.0, 'max_drawdown': 0.0, 'current_drawdown': 0.0,
            'open_positions': 0, 'winning_trades': 0, 'losing_trades': 0
        }
        order_manager = Mock()
        order_manager.get_order_statistics.return_value = {'active_orders': 0}
        grid_strategy = Mock()
        grid_strategy.get_grid_statistics.return_value = {'filled': 0, 'grid_profit': 0.0}

        # First call should set start_balance
        tracker.record_metrics(10000.0, risk_manager, order_manager, grid_strategy)
        assert tracker.start_balance == 10000.0

        # Second call should not change start_balance
        tracker.record_metrics(10500.0, risk_manager, order_manager, grid_strategy)
        assert tracker.start_balance == 10000.0

    def test_save_metrics(self, bot_config, tmp_path):
        """Test saving metrics to file"""
        tracker = PerformanceTracker(bot_config)
        tracker.metrics_dir = tmp_path / "metrics"
        tracker.metrics_dir.mkdir()

        # Add some metrics
        tracker.metrics_history.append(PerformanceMetrics(
            timestamp="2025-01-01T00:00:00",
            account_balance=10000.0,
            total_pnl=500.0,
            unrealized_pnl=100.0,
            realized_pnl=400.0,
            daily_pnl=50.0,
            total_trades=10,
            win_rate=60.0,
            profit_factor=2.5,
            max_drawdown=5.0,
            current_drawdown=2.0,
            open_positions=2,
            active_orders=5,
            grid_levels_filled=8,
            grid_profit=250.0
        ))

        # Save metrics
        tracker.save_metrics()

        # Verify file was created
        metrics_files = list(tracker.metrics_dir.glob("metrics_*.json"))
        assert len(metrics_files) > 0

        # Verify content
        with open(metrics_files[0]) as f:
            data = json.load(f)

        assert len(data) == 1
        assert data[0]['account_balance'] == 10000.0

    def test_save_metrics_error_handling(self, bot_config, tmp_path, caplog):
        """Test save_metrics handles errors gracefully"""
        tracker = PerformanceTracker(bot_config)
        tracker.metrics_dir = Path("/nonexistent/path/metrics")

        tracker.metrics_history.append(PerformanceMetrics(
            timestamp="2025-01-01T00:00:00", account_balance=10000.0,
            total_pnl=0.0, unrealized_pnl=0.0, realized_pnl=0.0,
            daily_pnl=0.0, total_trades=0, win_rate=0.0,
            profit_factor=0.0, max_drawdown=0.0, current_drawdown=0.0,
            open_positions=0, active_orders=0, grid_levels_filled=0,
            grid_profit=0.0
        ))

        # Should not raise exception
        with caplog.at_level(logging.ERROR):
            tracker.save_metrics()

        assert "Failed to save metrics" in caplog.text

    def test_get_performance_summary(self, bot_config, tmp_path):
        """Test getting performance summary"""
        tracker = PerformanceTracker(bot_config)
        tracker.metrics_dir = tmp_path / "metrics"
        tracker.metrics_dir.mkdir()
        tracker.start_balance = 10000.0

        # Add metrics
        tracker.metrics_history.append(PerformanceMetrics(
            timestamp="2025-01-01T00:00:00",
            account_balance=10500.0,
            total_pnl=500.0,
            unrealized_pnl=100.0,
            realized_pnl=400.0,
            daily_pnl=50.0,
            total_trades=10,
            win_rate=60.0,
            profit_factor=2.5,
            max_drawdown=5.0,
            current_drawdown=2.0,
            open_positions=2,
            active_orders=5,
            grid_levels_filled=8,
            grid_profit=250.0
        ))

        summary = tracker.get_performance_summary()

        assert summary['start_balance'] == 10000.0
        assert summary['current_balance'] == 10500.0
        assert summary['total_pnl'] == 500.0
        assert summary['total_pnl_percent'] == 5.0
        assert summary['win_rate'] == 60.0
        assert summary['metrics_count'] == 1

    def test_get_performance_summary_empty(self, bot_config):
        """Test getting performance summary with no metrics"""
        tracker = PerformanceTracker(bot_config)

        summary = tracker.get_performance_summary()

        assert summary == {}


class TestBotLogger:
    """Test BotLogger functionality"""

    def test_logger_initialization(self, bot_config, tmp_path):
        """Test bot logger initialization"""
        # Temporarily change log directory
        with patch('monitoring.Path') as mock_path:
            log_dir = tmp_path / "logs"
            mock_path.return_value = log_dir

            logger = BotLogger(bot_config)

            assert logger.config == bot_config
            assert logger.log_file == bot_config.monitoring.log_file

    def test_setup_logging(self, bot_config, tmp_path):
        """Test logging setup creates log file"""
        with patch('monitoring.Path') as mock_path_class:
            log_dir = tmp_path / "logs"
            log_dir.mkdir()

            # Mock Path to return our tmp log directory
            mock_path = Mock()
            mock_path.mkdir = Mock()
            mock_path.__truediv__ = lambda self, other: log_dir / other
            mock_path_class.return_value = mock_path

            logger = BotLogger(bot_config)

            # Verify logger is configured
            root_logger = logging.getLogger()
            assert root_logger.level == logging.INFO


class TestStateManager:
    """Test StateManager functionality"""

    def test_state_manager_initialization(self, bot_config, tmp_path):
        """Test state manager initialization"""
        state_manager = StateManager(bot_config)
        state_manager.state_file = tmp_path / "bot_state.json"

        assert state_manager.config == bot_config
        assert state_manager.state_file.name == "bot_state.json"

    def test_save_state(self, bot_config, tmp_path):
        """Test saving bot state"""
        state_manager = StateManager(bot_config)
        state_manager.state_file = tmp_path / "bot_state.json"
        state_manager.state_file.parent.mkdir(exist_ok=True)

        # Create mock components
        grid_strategy = Mock()
        grid_strategy.current_price = 40000.0
        grid_strategy.upper_price = 42000.0
        grid_strategy.lower_price = 38000.0
        grid_strategy.grid_spacing = 0.02
        grid_strategy.total_filled_orders = 5
        grid_strategy.realized_pnl = 100.0
        grid_strategy.last_rebalance = datetime.now()
        grid_strategy.get_grid_statistics.return_value = {'total_levels': 10}

        risk_manager = Mock()
        risk_manager.get_risk_metrics.return_value = {'total_trades': 10}
        risk_manager.get_position_summary.return_value = []
        risk_manager.emergency_stop = False
        risk_manager.stop_reason = None

        order_manager = Mock()
        order_manager.get_order_statistics.return_value = {'active_orders': 5}
        order_manager.orders = {}

        # Save state
        result = state_manager.save_state(grid_strategy, risk_manager, order_manager)

        assert result is True
        assert state_manager.state_file.exists()

        # Verify content
        with open(state_manager.state_file) as f:
            state = json.load(f)

        assert 'timestamp' in state
        assert state['grid']['current_price'] == 40000.0
        assert state['risk']['emergency_stop'] is False

    def test_save_state_error_handling(self, bot_config, caplog):
        """Test save_state handles errors gracefully"""
        state_manager = StateManager(bot_config)
        state_manager.state_file = Path("/nonexistent/path/state.json")

        grid_strategy = Mock()
        grid_strategy.current_price = 40000.0
        grid_strategy.last_rebalance = datetime.now()
        grid_strategy.get_grid_statistics.return_value = {}

        risk_manager = Mock()
        risk_manager.get_risk_metrics.return_value = {}
        risk_manager.get_position_summary.return_value = []
        risk_manager.emergency_stop = False
        risk_manager.stop_reason = None

        order_manager = Mock()
        order_manager.get_order_statistics.return_value = {}
        order_manager.orders = {}

        # Should return False on error
        with caplog.at_level(logging.ERROR):
            result = state_manager.save_state(grid_strategy, risk_manager, order_manager)

        assert result is False
        assert "Failed to save state" in caplog.text

    def test_load_state_success(self, bot_config, tmp_path):
        """Test loading bot state from file"""
        state_manager = StateManager(bot_config)
        state_manager.state_file = tmp_path / "bot_state.json"

        # Create a state file
        test_state = {
            'timestamp': '2025-01-01T00:00:00',
            'grid': {'current_price': 40000.0}
        }

        with open(state_manager.state_file, 'w') as f:
            json.dump(test_state, f)

        # Load state
        state = state_manager.load_state()

        assert state is not None
        assert state['timestamp'] == '2025-01-01T00:00:00'
        assert state['grid']['current_price'] == 40000.0

    def test_load_state_no_file(self, bot_config, tmp_path):
        """Test loading state when file doesn't exist"""
        state_manager = StateManager(bot_config)
        state_manager.state_file = tmp_path / "nonexistent.json"

        state = state_manager.load_state()

        assert state is None

    def test_load_state_error_handling(self, bot_config, tmp_path, caplog):
        """Test load_state handles errors gracefully"""
        state_manager = StateManager(bot_config)
        state_manager.state_file = tmp_path / "corrupt.json"

        # Create corrupt JSON file
        with open(state_manager.state_file, 'w') as f:
            f.write("{ invalid json }")

        # Should return None on error
        with caplog.at_level(logging.ERROR):
            state = state_manager.load_state()

        assert state is None
        assert "Failed to load state" in caplog.text

    def test_should_save_state(self, bot_config):
        """Test checking if state should be saved"""
        state_manager = StateManager(bot_config)

        # Just saved, should not save again
        state_manager.last_save_time = datetime.now()
        assert state_manager.should_save_state() is False

        # Saved long ago, should save now
        state_manager.last_save_time = datetime.now() - timedelta(seconds=400)
        assert state_manager.should_save_state() is True


class TestStatusDisplay:
    """Test StatusDisplay functionality"""

    def test_display_header(self, capsys):
        """Test displaying bot header"""
        display = StatusDisplay()

        display.display_header()

        captured = capsys.readouterr()
        assert "Institutional Adaptive Grid Bot" in captured.out
        assert "Trading System v1.0" in captured.out

    def test_display_status(self, capsys):
        """Test displaying bot status"""
        display = StatusDisplay()

        # Create mock components
        grid_strategy = Mock()
        grid_strategy.get_grid_statistics.return_value = {
            'lower_price': 38000.0,
            'upper_price': 42000.0,
            'current_price': 40000.0,
            'grid_spacing': 0.02,
            'total_levels': 10,
            'filled': 5,
            'grid_profit': 250.0
        }

        risk_manager = Mock()
        risk_manager.get_risk_metrics.return_value = {
            'total_realized_pnl': 400.0,
            'daily_pnl': 50.0,
            'total_unrealized_pnl': 100.0,
            'current_drawdown': 2.0,
            'max_drawdown': 5.0,
            'total_trades': 10,
            'winning_trades': 6,
            'losing_trades': 4,
            'win_rate': 60.0,
            'profit_factor': 2.5,
            'open_positions': 2
        }

        order_manager = Mock()
        order_manager.get_order_statistics.return_value = {
            'active_orders': 5,
            'active_buy_orders': 3,
            'active_sell_orders': 2
        }

        display.display_status(grid_strategy, risk_manager, order_manager, 10000.0)

        captured = capsys.readouterr()
        assert "Account Status" in captured.out
        assert "Grid Status" in captured.out
        assert "Trading Stats" in captured.out
        assert "$10,000.00" in captured.out

    def test_display_error(self, capsys):
        """Test displaying error message"""
        display = StatusDisplay()

        display.display_error("Test error message")

        captured = capsys.readouterr()
        assert "ERROR" in captured.out
        assert "Test error message" in captured.out

    def test_display_warning(self, capsys):
        """Test displaying warning message"""
        display = StatusDisplay()

        display.display_warning("Test warning")

        captured = capsys.readouterr()
        assert "WARNING" in captured.out
        assert "Test warning" in captured.out

    def test_display_info(self, capsys):
        """Test displaying info message"""
        display = StatusDisplay()

        display.display_info("Test info")

        captured = capsys.readouterr()
        assert "Test info" in captured.out


@pytest.mark.parametrize("interval,expected", [
    (30, False),   # Recently saved (30s < 60s threshold)
    (400, True),   # Long time ago (400s > 60s threshold)
])
def test_should_save_state_parametrized(bot_config, interval, expected):
    """Test should_save_state with different intervals"""
    state_manager = StateManager(bot_config)
    state_manager.last_save_time = datetime.now() - timedelta(seconds=interval)

    assert state_manager.should_save_state() == expected
