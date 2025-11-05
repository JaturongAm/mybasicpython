"""
Risk Management Module for Grid Bot
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging
from collections import defaultdict


@dataclass
class Position:
    """Represents a trading position"""
    symbol: str
    side: str  # LONG or SHORT
    entry_price: float
    quantity: float
    leverage: int
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    @property
    def position_value(self) -> float:
        """Calculate position value in USDT"""
        return self.entry_price * self.quantity

    @property
    def margin_used(self) -> float:
        """Calculate margin used"""
        return self.position_value / self.leverage

    def calculate_pnl(self, current_price: float) -> float:
        """Calculate unrealized PnL"""
        if self.side == 'LONG':
            pnl = (current_price - self.entry_price) * self.quantity
        else:
            pnl = (self.entry_price - current_price) * self.quantity
        return pnl

    def calculate_pnl_percent(self, current_price: float) -> float:
        """Calculate PnL as percentage"""
        pnl = self.calculate_pnl(current_price)
        return (pnl / self.position_value) * 100 if self.position_value > 0 else 0.0


@dataclass
class TradeRecord:
    """Record of a completed trade"""
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    entry_time: datetime
    exit_time: datetime
    trade_duration: timedelta = None

    def __post_init__(self):
        if self.trade_duration is None:
            self.trade_duration = self.exit_time - self.entry_time


class RiskManager:
    """Manages trading risk and position limits"""

    def __init__(self, config):
        self.config = config
        self.risk_config = config.risk
        self.logger = logging.getLogger(__name__)

        # Track positions and trades
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[TradeRecord] = []

        # Daily tracking
        self.daily_pnl: float = 0.0
        self.daily_trades: int = 0
        self.day_start: datetime = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Drawdown tracking
        self.peak_balance: float = 0.0
        self.current_drawdown: float = 0.0
        self.max_drawdown: float = 0.0

        # Emergency stop
        self.emergency_stop: bool = False
        self.stop_reason: str = ""

    def check_order_allowed(self, symbol: str, side: str, quantity: float, price: float) -> Tuple[bool, str]:
        """Check if an order is allowed based on risk parameters"""

        # Check emergency stop
        if self.emergency_stop:
            return False, f"Emergency stop active: {self.stop_reason}"

        # Check position size limit
        order_value = quantity * price
        total_position_value = self._calculate_total_position_value()

        if total_position_value + order_value > self.risk_config.max_position_usdt:
            return False, f"Position size limit exceeded: {total_position_value + order_value:.2f} > {self.risk_config.max_position_usdt}"

        # Check daily loss limit
        if self.daily_pnl < -self.risk_config.max_daily_loss_usdt:
            return False, f"Daily loss limit exceeded: {abs(self.daily_pnl):.2f} USDT"

        # Check max drawdown
        if self.current_drawdown > self.risk_config.max_drawdown_percent:
            return False, f"Max drawdown exceeded: {self.current_drawdown:.2f}%"

        # Check max open orders
        if len(self.positions) >= self.risk_config.max_open_orders:
            return False, f"Max open orders limit reached: {len(self.positions)}"

        return True, "Order allowed"

    def _calculate_total_position_value(self) -> float:
        """Calculate total value of all positions"""
        total = sum(pos.position_value for pos in self.positions.values())
        return total

    def update_position(self, symbol: str, side: str, entry_price: float,
                       quantity: float, leverage: int):
        """Update or create position"""
        if symbol in self.positions:
            # Update existing position
            pos = self.positions[symbol]
            # Calculate weighted average entry price
            total_quantity = pos.quantity + quantity
            pos.entry_price = (pos.entry_price * pos.quantity + entry_price * quantity) / total_quantity
            pos.quantity = total_quantity
            pos.leverage = leverage
        else:
            # Create new position
            position = Position(
                symbol=symbol,
                side=side,
                entry_price=entry_price,
                quantity=quantity,
                leverage=leverage
            )
            self.positions[symbol] = position

        self.logger.info(f"Position updated: {symbol} {side} {quantity} @ {entry_price}")

    def close_position(self, symbol: str, exit_price: float, quantity: float = None) -> Optional[TradeRecord]:
        """Close position and record trade"""
        if symbol not in self.positions:
            self.logger.warning(f"No position found for {symbol}")
            return None

        position = self.positions[symbol]

        # Close full or partial position
        close_quantity = quantity if quantity else position.quantity

        if close_quantity > position.quantity:
            self.logger.warning(f"Close quantity {close_quantity} exceeds position {position.quantity}")
            close_quantity = position.quantity

        # Calculate PnL
        if position.side == 'LONG':
            pnl = (exit_price - position.entry_price) * close_quantity
        else:
            pnl = (position.entry_price - exit_price) * close_quantity

        # Create trade record
        trade = TradeRecord(
            symbol=symbol,
            side=position.side,
            entry_price=position.entry_price,
            exit_price=exit_price,
            quantity=close_quantity,
            pnl=pnl,
            entry_time=position.timestamp,
            exit_time=datetime.now()
        )

        self.trade_history.append(trade)
        self.daily_pnl += pnl
        self.daily_trades += 1

        # Update position
        position.realized_pnl += pnl
        position.quantity -= close_quantity

        if position.quantity <= 0.0001:  # Close to zero
            del self.positions[symbol]
            self.logger.info(f"Position closed: {symbol}, PnL: {pnl:.2f} USDT")
        else:
            self.logger.info(f"Position partially closed: {symbol}, remaining: {position.quantity}")

        return trade

    def update_unrealized_pnl(self, symbol: str, current_price: float):
        """Update unrealized PnL for position"""
        if symbol in self.positions:
            position = self.positions[symbol]
            position.unrealized_pnl = position.calculate_pnl(current_price)

    def check_stop_loss(self, symbol: str, current_price: float) -> bool:
        """Check if stop loss should be triggered"""
        if symbol not in self.positions:
            return False

        position = self.positions[symbol]
        pnl_percent = position.calculate_pnl_percent(current_price)

        if pnl_percent <= -self.risk_config.stop_loss_percent:
            self.logger.warning(f"Stop loss triggered for {symbol}: {pnl_percent:.2f}%")
            return True

        return False

    def check_take_profit(self, symbol: str, current_price: float) -> bool:
        """Check if take profit should be triggered"""
        if symbol not in self.positions:
            return False

        position = self.positions[symbol]
        pnl_percent = position.calculate_pnl_percent(current_price)

        if pnl_percent >= self.risk_config.take_profit_percent:
            self.logger.info(f"Take profit triggered for {symbol}: {pnl_percent:.2f}%")
            return True

        return False

    def update_drawdown(self, current_balance: float):
        """Update drawdown tracking"""
        if current_balance > self.peak_balance:
            self.peak_balance = current_balance

        if self.peak_balance > 0:
            self.current_drawdown = ((self.peak_balance - current_balance) / self.peak_balance) * 100
            self.max_drawdown = max(self.max_drawdown, self.current_drawdown)

            # Check if max drawdown exceeded
            if self.current_drawdown > self.risk_config.max_drawdown_percent:
                self.trigger_emergency_stop(f"Max drawdown exceeded: {self.current_drawdown:.2f}%")

    def trigger_emergency_stop(self, reason: str):
        """Trigger emergency stop"""
        self.emergency_stop = True
        self.stop_reason = reason
        self.logger.error(f"EMERGENCY STOP TRIGGERED: {reason}")

    def reset_emergency_stop(self):
        """Reset emergency stop (manual intervention)"""
        self.emergency_stop = False
        self.stop_reason = ""
        self.logger.info("Emergency stop reset")

    def reset_daily_stats(self):
        """Reset daily statistics"""
        current_time = datetime.now()
        if current_time.date() > self.day_start.date():
            self.logger.info(f"Daily stats - PnL: {self.daily_pnl:.2f} USDT, Trades: {self.daily_trades}")
            self.daily_pnl = 0.0
            self.daily_trades = 0
            self.day_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)

    def get_risk_metrics(self) -> Dict:
        """Get current risk metrics"""
        total_position_value = self._calculate_total_position_value()
        total_unrealized_pnl = sum(pos.unrealized_pnl for pos in self.positions.values())
        total_realized_pnl = sum(trade.pnl for trade in self.trade_history)

        # Win rate calculation
        winning_trades = len([t for t in self.trade_history if t.pnl > 0])
        total_trades = len(self.trade_history)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

        # Average trade metrics
        avg_win = sum(t.pnl for t in self.trade_history if t.pnl > 0) / winning_trades if winning_trades > 0 else 0.0
        losing_trades = [t for t in self.trade_history if t.pnl < 0]
        avg_loss = sum(t.pnl for t in losing_trades) / len(losing_trades) if losing_trades else 0.0

        return {
            'total_position_value': total_position_value,
            'total_unrealized_pnl': total_unrealized_pnl,
            'total_realized_pnl': total_realized_pnl,
            'daily_pnl': self.daily_pnl,
            'daily_trades': self.daily_trades,
            'current_drawdown': self.current_drawdown,
            'max_drawdown': self.max_drawdown,
            'peak_balance': self.peak_balance,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': abs(avg_win / avg_loss) if avg_loss != 0 else 0.0,
            'open_positions': len(self.positions),
            'emergency_stop': self.emergency_stop,
            'stop_reason': self.stop_reason
        }

    def get_position_summary(self) -> List[Dict]:
        """Get summary of all positions"""
        summary = []
        for symbol, pos in self.positions.items():
            summary.append({
                'symbol': symbol,
                'side': pos.side,
                'entry_price': pos.entry_price,
                'quantity': pos.quantity,
                'position_value': pos.position_value,
                'margin_used': pos.margin_used,
                'leverage': pos.leverage,
                'unrealized_pnl': pos.unrealized_pnl,
                'realized_pnl': pos.realized_pnl,
                'timestamp': pos.timestamp.isoformat()
            })
        return summary

    def calculate_position_size(self, account_balance: float, risk_percent: float, entry_price: float, stop_loss_price: float) -> float:
        """Calculate position size based on risk percentage"""
        risk_amount = account_balance * (risk_percent / 100)
        price_difference = abs(entry_price - stop_loss_price)

        if price_difference > 0:
            position_size = risk_amount / price_difference
            return position_size
        return 0.0
