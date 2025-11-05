"""
Unit tests for risk management module
"""
import pytest
from datetime import datetime, timedelta
from risk_manager import (
    RiskManager,
    Position,
    TradeRecord
)


class TestPosition:
    """Test Position data class"""

    def test_position_creation(self):
        """Test position creation"""
        pos = Position(
            symbol='BTCUSDT',
            side='LONG',
            entry_price=40000.0,
            quantity=0.01,
            leverage=5
        )

        assert pos.symbol == 'BTCUSDT'
        assert pos.side == 'LONG'
        assert pos.entry_price == 40000.0
        assert pos.quantity == 0.01
        assert pos.leverage == 5
        assert pos.unrealized_pnl == 0.0

    def test_position_value(self, sample_position):
        """Test position value calculation"""
        value = sample_position.position_value

        expected = 40000.0 * 0.01
        assert value == expected

    def test_margin_used(self, sample_position):
        """Test margin calculation"""
        margin = sample_position.margin_used

        expected = (40000.0 * 0.01) / 5
        assert margin == expected

    def test_calculate_pnl_long_profit(self, sample_position):
        """Test PnL calculation for long position with profit"""
        current_price = 42000.0
        pnl = sample_position.calculate_pnl(current_price)

        expected = (42000.0 - 40000.0) * 0.01
        assert pnl == expected
        assert pnl > 0

    def test_calculate_pnl_long_loss(self, sample_position):
        """Test PnL calculation for long position with loss"""
        current_price = 38000.0
        pnl = sample_position.calculate_pnl(current_price)

        expected = (38000.0 - 40000.0) * 0.01
        assert pnl == expected
        assert pnl < 0

    def test_calculate_pnl_short_profit(self):
        """Test PnL calculation for short position with profit"""
        pos = Position(
            symbol='BTCUSDT',
            side='SHORT',
            entry_price=40000.0,
            quantity=0.01,
            leverage=5
        )

        current_price = 38000.0
        pnl = pos.calculate_pnl(current_price)

        expected = (40000.0 - 38000.0) * 0.01
        assert pnl == expected
        assert pnl > 0

    def test_calculate_pnl_percent(self, sample_position):
        """Test PnL percentage calculation"""
        current_price = 42000.0
        pnl_percent = sample_position.calculate_pnl_percent(current_price)

        expected = ((42000.0 - 40000.0) / 40000.0) * 100
        assert abs(pnl_percent - expected) < 0.01


class TestTradeRecord:
    """Test TradeRecord data class"""

    def test_trade_record_creation(self):
        """Test trade record creation"""
        entry_time = datetime.now() - timedelta(hours=1)
        exit_time = datetime.now()

        trade = TradeRecord(
            symbol='BTCUSDT',
            side='LONG',
            entry_price=40000.0,
            exit_price=42000.0,
            quantity=0.01,
            pnl=20.0,
            entry_time=entry_time,
            exit_time=exit_time
        )

        assert trade.symbol == 'BTCUSDT'
        assert trade.pnl == 20.0
        assert trade.trade_duration is not None


class TestRiskManager:
    """Test risk manager"""

    def test_risk_manager_creation(self, bot_config):
        """Test risk manager initialization"""
        manager = RiskManager(bot_config)

        assert manager.config == bot_config
        assert len(manager.positions) == 0
        assert len(manager.trade_history) == 0
        assert manager.daily_pnl == 0.0
        assert manager.emergency_stop is False

    def test_check_order_allowed_success(self, risk_manager):
        """Test order allowed check passes"""
        allowed, reason = risk_manager.check_order_allowed(
            symbol='BTCUSDT',
            side='BUY',
            quantity=0.001,
            price=40000.0
        )

        assert allowed is True
        assert reason == "Order allowed"

    def test_check_order_allowed_position_limit(self, risk_manager):
        """Test order rejected due to position limit"""
        # Set current position near limit
        risk_manager.positions['BTCUSDT'] = Position(
            symbol='BTCUSDT',
            side='LONG',
            entry_price=40000.0,
            quantity=0.12,  # Close to limit
            leverage=5
        )

        allowed, reason = risk_manager.check_order_allowed(
            symbol='BTCUSDT',
            side='BUY',
            quantity=0.2,  # Would exceed limit
            price=40000.0
        )

        assert allowed is False
        assert "Position size limit exceeded" in reason

    def test_check_order_allowed_daily_loss_limit(self, risk_manager):
        """Test order rejected due to daily loss limit"""
        risk_manager.daily_pnl = -600.0  # Exceeds limit

        allowed, reason = risk_manager.check_order_allowed(
            symbol='BTCUSDT',
            side='BUY',
            quantity=0.001,
            price=40000.0
        )

        assert allowed is False
        assert "Daily loss limit exceeded" in reason

    def test_check_order_allowed_emergency_stop(self, risk_manager):
        """Test order rejected due to emergency stop"""
        risk_manager.trigger_emergency_stop("Test emergency")

        allowed, reason = risk_manager.check_order_allowed(
            symbol='BTCUSDT',
            side='BUY',
            quantity=0.001,
            price=40000.0
        )

        assert allowed is False
        assert "Emergency stop active" in reason

    def test_update_position_new(self, risk_manager):
        """Test creating new position"""
        risk_manager.update_position(
            symbol='BTCUSDT',
            side='LONG',
            entry_price=40000.0,
            quantity=0.01,
            leverage=5
        )

        assert 'BTCUSDT' in risk_manager.positions
        pos = risk_manager.positions['BTCUSDT']
        assert pos.quantity == 0.01
        assert pos.entry_price == 40000.0

    def test_update_position_existing(self, risk_manager):
        """Test updating existing position"""
        # Create initial position
        risk_manager.update_position(
            symbol='BTCUSDT',
            side='LONG',
            entry_price=40000.0,
            quantity=0.01,
            leverage=5
        )

        # Update with additional quantity
        risk_manager.update_position(
            symbol='BTCUSDT',
            side='LONG',
            entry_price=41000.0,
            quantity=0.01,
            leverage=5
        )

        pos = risk_manager.positions['BTCUSDT']
        assert pos.quantity == 0.02
        # Entry price should be weighted average
        assert pos.entry_price == 40500.0

    def test_close_position_full(self, risk_manager):
        """Test closing full position"""
        # Create position
        risk_manager.update_position(
            symbol='BTCUSDT',
            side='LONG',
            entry_price=40000.0,
            quantity=0.01,
            leverage=5
        )

        # Close position
        trade = risk_manager.close_position('BTCUSDT', exit_price=42000.0)

        assert trade is not None
        assert trade.pnl == 20.0
        assert 'BTCUSDT' not in risk_manager.positions
        assert len(risk_manager.trade_history) == 1

    def test_close_position_partial(self, risk_manager):
        """Test closing partial position"""
        # Create position
        risk_manager.update_position(
            symbol='BTCUSDT',
            side='LONG',
            entry_price=40000.0,
            quantity=0.02,
            leverage=5
        )

        # Close half
        trade = risk_manager.close_position('BTCUSDT', exit_price=42000.0, quantity=0.01)

        assert trade is not None
        assert trade.pnl == 20.0
        assert 'BTCUSDT' in risk_manager.positions
        assert risk_manager.positions['BTCUSDT'].quantity == 0.01

    def test_close_position_nonexistent(self, risk_manager):
        """Test closing nonexistent position"""
        trade = risk_manager.close_position('ETHUSDT', exit_price=3000.0)

        assert trade is None

    def test_check_stop_loss(self, risk_manager):
        """Test stop loss check"""
        # Create losing position
        risk_manager.update_position(
            symbol='BTCUSDT',
            side='LONG',
            entry_price=40000.0,
            quantity=0.01,
            leverage=5
        )

        # Price drops 6% (exceeds 5% stop loss)
        current_price = 37600.0
        should_stop = risk_manager.check_stop_loss('BTCUSDT', current_price)

        assert should_stop is True

    def test_check_take_profit(self, risk_manager):
        """Test take profit check"""
        # Create winning position
        risk_manager.update_position(
            symbol='BTCUSDT',
            side='LONG',
            entry_price=40000.0,
            quantity=0.01,
            leverage=5
        )

        # Price rises 11% (exceeds 10% take profit)
        current_price = 44400.0
        should_take_profit = risk_manager.check_take_profit('BTCUSDT', current_price)

        assert should_take_profit is True

    def test_update_drawdown(self, risk_manager):
        """Test drawdown calculation"""
        # Set peak balance
        risk_manager.update_drawdown(10000.0)
        assert risk_manager.peak_balance == 10000.0

        # Balance drops
        risk_manager.update_drawdown(8500.0)
        assert risk_manager.current_drawdown == 15.0  # 15% drawdown
        assert risk_manager.max_drawdown == 15.0

    def test_update_drawdown_triggers_emergency_stop(self, risk_manager):
        """Test drawdown triggers emergency stop"""
        risk_manager.peak_balance = 10000.0

        # Trigger emergency stop with 20% drawdown (exceeds 15% limit)
        risk_manager.update_drawdown(8000.0)

        assert risk_manager.emergency_stop is True
        assert "Max drawdown exceeded" in risk_manager.stop_reason

    def test_trigger_emergency_stop(self, risk_manager):
        """Test triggering emergency stop"""
        risk_manager.trigger_emergency_stop("Test reason")

        assert risk_manager.emergency_stop is True
        assert risk_manager.stop_reason == "Test reason"

    def test_reset_emergency_stop(self, risk_manager):
        """Test resetting emergency stop"""
        risk_manager.trigger_emergency_stop("Test")
        risk_manager.reset_emergency_stop()

        assert risk_manager.emergency_stop is False
        assert risk_manager.stop_reason == ""

    def test_reset_daily_stats(self, risk_manager):
        """Test resetting daily statistics"""
        risk_manager.daily_pnl = 100.0
        risk_manager.daily_trades = 10
        risk_manager.day_start = datetime.now() - timedelta(days=2)

        risk_manager.reset_daily_stats()

        assert risk_manager.daily_pnl == 0.0
        assert risk_manager.daily_trades == 0

    def test_get_risk_metrics(self, risk_manager):
        """Test getting risk metrics"""
        # Create some positions and trades
        risk_manager.update_position('BTCUSDT', 'LONG', 40000.0, 0.01, 5)
        risk_manager.close_position('BTCUSDT', 42000.0)

        metrics = risk_manager.get_risk_metrics()

        assert 'total_position_value' in metrics
        assert 'total_unrealized_pnl' in metrics
        assert 'total_realized_pnl' in metrics
        assert 'win_rate' in metrics
        assert 'profit_factor' in metrics

    def test_get_position_summary(self, risk_manager):
        """Test getting position summary"""
        risk_manager.update_position('BTCUSDT', 'LONG', 40000.0, 0.01, 5)
        risk_manager.update_position('ETHUSDT', 'LONG', 3000.0, 0.1, 3)

        summary = risk_manager.get_position_summary()

        assert len(summary) == 2
        assert all('symbol' in pos for pos in summary)
        assert all('position_value' in pos for pos in summary)

    def test_calculate_position_size(self, risk_manager):
        """Test position size calculation"""
        account_balance = 10000.0
        risk_percent = 1.0  # 1% risk
        entry_price = 40000.0
        stop_loss_price = 38000.0

        position_size = risk_manager.calculate_position_size(
            account_balance,
            risk_percent,
            entry_price,
            stop_loss_price
        )

        # Risk amount = 10000 * 0.01 = 100
        # Price diff = 2000
        # Position size = 100 / 2000 = 0.05
        assert position_size == 0.05

    def test_win_rate_calculation(self, risk_manager):
        """Test win rate calculation"""
        # Add winning trades
        risk_manager.update_position('BTCUSDT', 'LONG', 40000.0, 0.01, 5)
        risk_manager.close_position('BTCUSDT', 42000.0)  # Win

        risk_manager.update_position('BTCUSDT', 'LONG', 42000.0, 0.01, 5)
        risk_manager.close_position('BTCUSDT', 41000.0)  # Loss

        metrics = risk_manager.get_risk_metrics()

        assert metrics['total_trades'] == 2
        assert metrics['winning_trades'] == 1
        assert metrics['losing_trades'] == 1
        assert metrics['win_rate'] == 50.0


@pytest.mark.parametrize("entry_price,exit_price,quantity,expected_pnl", [
    (40000.0, 42000.0, 0.01, 20.0),
    (40000.0, 38000.0, 0.01, -20.0),
    (50000.0, 51000.0, 0.1, 100.0),
])
def test_pnl_calculations(risk_manager, entry_price, exit_price, quantity, expected_pnl):
    """Test PnL calculations with various parameters"""
    risk_manager.update_position('BTCUSDT', 'LONG', entry_price, quantity, 5)
    trade = risk_manager.close_position('BTCUSDT', exit_price)

    assert trade.pnl == expected_pnl
