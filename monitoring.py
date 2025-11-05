"""
Monitoring and Performance Tracking Module
"""
import logging
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import sys
from dataclasses import dataclass, asdict
import time


@dataclass
class PerformanceMetrics:
    """Performance metrics snapshot"""
    timestamp: str
    account_balance: float
    total_pnl: float
    unrealized_pnl: float
    realized_pnl: float
    daily_pnl: float
    total_trades: int
    win_rate: float
    profit_factor: float
    max_drawdown: float
    current_drawdown: float
    open_positions: int
    active_orders: int
    grid_levels_filled: int
    grid_profit: float


class PerformanceTracker:
    """Track and store performance metrics"""

    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)

        self.metrics_history: List[PerformanceMetrics] = []
        self.start_time = datetime.now()
        self.start_balance: Optional[float] = None

        # Create metrics directory
        self.metrics_dir = Path("metrics")
        self.metrics_dir.mkdir(exist_ok=True)

    def record_metrics(self, account_balance: float, risk_manager, order_manager, grid_strategy) -> PerformanceMetrics:
        """Record current performance metrics"""

        # Get risk metrics
        risk_metrics = risk_manager.get_risk_metrics()

        # Get order statistics
        order_stats = order_manager.get_order_statistics()

        # Get grid statistics
        grid_stats = grid_strategy.get_grid_statistics()

        # Set start balance if not set
        if self.start_balance is None:
            self.start_balance = account_balance

        # Create metrics snapshot
        metrics = PerformanceMetrics(
            timestamp=datetime.now().isoformat(),
            account_balance=account_balance,
            total_pnl=account_balance - self.start_balance if self.start_balance else 0.0,
            unrealized_pnl=risk_metrics['total_unrealized_pnl'],
            realized_pnl=risk_metrics['total_realized_pnl'],
            daily_pnl=risk_metrics['daily_pnl'],
            total_trades=risk_metrics['total_trades'],
            win_rate=risk_metrics['win_rate'],
            profit_factor=risk_metrics['profit_factor'],
            max_drawdown=risk_metrics['max_drawdown'],
            current_drawdown=risk_metrics['current_drawdown'],
            open_positions=risk_metrics['open_positions'],
            active_orders=order_stats['active_orders'],
            grid_levels_filled=grid_stats['filled'],
            grid_profit=grid_stats['grid_profit']
        )

        self.metrics_history.append(metrics)

        # Save to file periodically
        if len(self.metrics_history) % 10 == 0:
            self.save_metrics()

        return metrics

    def save_metrics(self):
        """Save metrics to JSON file"""
        try:
            filename = self.metrics_dir / f"metrics_{datetime.now().strftime('%Y%m%d')}.json"

            metrics_data = [asdict(m) for m in self.metrics_history]

            with open(filename, 'w') as f:
                json.dump(metrics_data, f, indent=2)

            self.logger.debug(f"Metrics saved to {filename}")

        except Exception as e:
            self.logger.error(f"Failed to save metrics: {e}")

    def get_performance_summary(self) -> Dict:
        """Get overall performance summary"""
        if not self.metrics_history:
            return {}

        latest = self.metrics_history[-1]
        runtime = datetime.now() - self.start_time

        return {
            'runtime_hours': runtime.total_seconds() / 3600,
            'start_balance': self.start_balance,
            'current_balance': latest.account_balance,
            'total_pnl': latest.total_pnl,
            'total_pnl_percent': (latest.total_pnl / self.start_balance * 100) if self.start_balance else 0.0,
            'daily_pnl': latest.daily_pnl,
            'total_trades': latest.total_trades,
            'win_rate': latest.win_rate,
            'profit_factor': latest.profit_factor,
            'max_drawdown': latest.max_drawdown,
            'current_drawdown': latest.current_drawdown,
            'grid_profit': latest.grid_profit,
            'metrics_count': len(self.metrics_history)
        }


class BotLogger:
    """Configure and manage bot logging"""

    def __init__(self, config):
        self.config = config
        self.log_file = config.monitoring.log_file
        self.log_level = getattr(logging, config.monitoring.log_level.upper())

        self._setup_logging()

    def _setup_logging(self):
        """Setup logging configuration"""

        # Create logs directory
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        # Create log file path
        log_path = log_dir / self.log_file

        # Create formatters
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )

        # Setup root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)

        # Clear existing handlers
        root_logger.handlers.clear()

        # File handler
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(self.log_level)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.log_level)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

        # Reduce verbosity of requests library
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)

        logging.info(f"Logging configured: {log_path}")


class StateManager:
    """Manage and persist bot state"""

    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)

        self.state_file = Path("state") / "bot_state.json"
        self.state_file.parent.mkdir(exist_ok=True)

        self.last_save_time = datetime.now()

    def save_state(self, grid_strategy, risk_manager, order_manager) -> bool:
        """Save current bot state"""
        try:
            state = {
                'timestamp': datetime.now().isoformat(),
                'grid': {
                    'current_price': grid_strategy.current_price,
                    'upper_price': grid_strategy.upper_price,
                    'lower_price': grid_strategy.lower_price,
                    'grid_spacing': grid_strategy.grid_spacing,
                    'total_filled_orders': grid_strategy.total_filled_orders,
                    'realized_pnl': grid_strategy.realized_pnl,
                    'last_rebalance': grid_strategy.last_rebalance.isoformat(),
                    'statistics': grid_strategy.get_grid_statistics()
                },
                'risk': {
                    'metrics': risk_manager.get_risk_metrics(),
                    'positions': risk_manager.get_position_summary(),
                    'emergency_stop': risk_manager.emergency_stop,
                    'stop_reason': risk_manager.stop_reason
                },
                'orders': {
                    'statistics': order_manager.get_order_statistics(),
                    'active_orders_count': len(order_manager.orders)
                }
            }

            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)

            self.last_save_time = datetime.now()
            self.logger.debug("Bot state saved")
            return True

        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")
            return False

    def load_state(self) -> Optional[Dict]:
        """Load saved bot state"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    state = json.load(f)

                self.logger.info(f"Bot state loaded from {state['timestamp']}")
                return state

        except Exception as e:
            self.logger.error(f"Failed to load state: {e}")

        return None

    def should_save_state(self) -> bool:
        """Check if state should be saved"""
        elapsed = (datetime.now() - self.last_save_time).total_seconds()
        return elapsed >= self.config.monitoring.save_state_interval


class StatusDisplay:
    """Display bot status in terminal"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def display_header(self):
        """Display bot header"""
        header = """
╔══════════════════════════════════════════════════════════════╗
║     Institutional Adaptive Grid Bot - Binance Futures       ║
║                  Trading System v1.0                         ║
╚══════════════════════════════════════════════════════════════╝
"""
        print(header)
        self.logger.info("Bot started")

    def display_status(self, grid_strategy, risk_manager, order_manager, account_balance: float):
        """Display current status"""

        # Get statistics
        grid_stats = grid_strategy.get_grid_statistics()
        risk_metrics = risk_manager.get_risk_metrics()
        order_stats = order_manager.get_order_statistics()

        status = f"""
┌─────────────────── Account Status ───────────────────┐
│ Balance: ${account_balance:,.2f} USDT
│ Total PnL: ${risk_metrics['total_realized_pnl']:,.2f} USDT ({risk_metrics['total_realized_pnl']/account_balance*100:.2f}%)
│ Daily PnL: ${risk_metrics['daily_pnl']:,.2f} USDT
│ Unrealized PnL: ${risk_metrics['total_unrealized_pnl']:,.2f} USDT
│ Drawdown: {risk_metrics['current_drawdown']:.2f}% (Max: {risk_metrics['max_drawdown']:.2f}%)
└──────────────────────────────────────────────────────┘

┌─────────────────── Grid Status ──────────────────────┐
│ Price Range: ${grid_stats['lower_price']:,.2f} - ${grid_stats['upper_price']:,.2f}
│ Current Price: ${grid_stats['current_price']:,.2f}
│ Grid Spacing: {grid_stats['grid_spacing']:.2%}
│ Grid Levels: {grid_stats['total_levels']} (Filled: {grid_stats['filled']})
│ Grid Profit: ${grid_stats['grid_profit']:,.2f} USDT
└──────────────────────────────────────────────────────┘

┌─────────────────── Trading Stats ────────────────────┐
│ Active Orders: {order_stats['active_orders']} (Buy: {order_stats['active_buy_orders']}, Sell: {order_stats['active_sell_orders']})
│ Total Trades: {risk_metrics['total_trades']} (Wins: {risk_metrics['winning_trades']}, Losses: {risk_metrics['losing_trades']})
│ Win Rate: {risk_metrics['win_rate']:.1f}%
│ Profit Factor: {risk_metrics['profit_factor']:.2f}
│ Open Positions: {risk_metrics['open_positions']}
└──────────────────────────────────────────────────────┘
"""
        print(status)
        self.logger.info("Status updated")

    def display_error(self, error_msg: str):
        """Display error message"""
        error = f"""
╔════════════════════ ERROR ═══════════════════════════╗
║ {error_msg:54s} ║
╚══════════════════════════════════════════════════════╝
"""
        print(error)
        self.logger.error(error_msg)

    def display_warning(self, warning_msg: str):
        """Display warning message"""
        print(f"\n⚠️  WARNING: {warning_msg}\n")
        self.logger.warning(warning_msg)

    def display_info(self, info_msg: str):
        """Display info message"""
        print(f"ℹ️  {info_msg}")
        self.logger.info(info_msg)
