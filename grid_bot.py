#!/usr/bin/env python3
"""
Institutional Adaptive Grid Bot for Binance Futures
Main orchestrator that coordinates all components
"""
import signal
import sys
import time
from datetime import datetime, timedelta
from typing import Optional
import logging

from config import BotConfig
from binance_client import BinanceFuturesClient
from grid_strategy import AdaptiveGridStrategy
from risk_manager import RiskManager
from order_manager import OrderManager
from monitoring import BotLogger, PerformanceTracker, StateManager, StatusDisplay


class GridBot:
    """Main Grid Bot orchestrator"""

    def __init__(self, config_file: str = None):
        # Load configuration
        self.config = BotConfig(config_file)
        self.config.validate_all()

        # Setup logging
        self.bot_logger = BotLogger(self.config)
        self.logger = logging.getLogger(__name__)

        # Initialize components
        self.client = BinanceFuturesClient(
            api_key=self.config.api.api_key,
            api_secret=self.config.api.api_secret,
            testnet=self.config.api.testnet
        )

        self.risk_manager = RiskManager(self.config)
        self.order_manager = OrderManager(self.client, self.config, self.risk_manager)
        self.grid_strategy = AdaptiveGridStrategy(self.config)

        # Monitoring and tracking
        self.performance_tracker = PerformanceTracker(self.config)
        self.state_manager = StateManager(self.config)
        self.status_display = StatusDisplay()

        # Control flags
        self.running = False
        self.paused = False

        # Timing
        self.last_status_update = datetime.now()
        self.last_metrics_update = datetime.now()
        self.last_order_sync = datetime.now()
        self.last_price_update = datetime.now()

        # Account info
        self.account_balance: float = 0.0
        self.current_price: float = 0.0

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.shutdown()
        sys.exit(0)

    def initialize(self) -> bool:
        """Initialize bot and verify connectivity"""
        self.status_display.display_header()

        try:
            # Test connectivity
            self.logger.info("Testing API connectivity...")
            if not self.client.test_connectivity():
                raise Exception("Failed to connect to Binance API")

            self.logger.info("✓ API connection successful")

            # Get account information
            self.logger.info("Fetching account information...")
            account_info = self.client.get_account_info()

            # Get USDT balance
            for asset in account_info.get('assets', []):
                if asset['asset'] == 'USDT':
                    self.account_balance = float(asset['availableBalance'])
                    break

            self.logger.info(f"✓ Account balance: {self.account_balance:.2f} USDT")

            # Verify sufficient balance
            min_balance = self.config.grid.order_quantity_usdt * self.config.grid.grid_levels
            if self.account_balance < min_balance:
                raise Exception(f"Insufficient balance. Need at least {min_balance:.2f} USDT")

            # Set leverage
            self.logger.info(f"Setting leverage to {self.config.grid.leverage}x...")
            try:
                self.client.set_leverage(
                    symbol=self.config.grid.symbol,
                    leverage=self.config.grid.leverage
                )
                self.logger.info(f"✓ Leverage set to {self.config.grid.leverage}x")
            except Exception as e:
                self.logger.warning(f"Could not set leverage: {e}")

            # Get current price
            self.logger.info(f"Fetching current price for {self.config.grid.symbol}...")
            ticker = self.client.get_ticker_price(self.config.grid.symbol)
            self.current_price = float(ticker['price'])
            self.logger.info(f"✓ Current price: {self.current_price:.2f}")

            # Get historical data for volatility calculation
            self.logger.info("Calculating market volatility...")
            klines = self.client.get_klines(
                symbol=self.config.grid.symbol,
                interval='1h',
                limit=self.config.grid.volatility_window
            )

            for kline in klines:
                close_price = float(kline[4])
                timestamp = datetime.fromtimestamp(kline[0] / 1000)
                self.grid_strategy.volatility_calculator.add_price(close_price, timestamp)

            volatility = self.grid_strategy.volatility_calculator.calculate_volatility()
            volatility_regime = self.grid_strategy.volatility_calculator.get_volatility_regime()
            self.logger.info(f"✓ Market volatility: {volatility:.2f}% ({volatility_regime})")

            # Initialize grid
            self.logger.info("Initializing grid strategy...")
            self.grid_strategy.initialize_grid(self.current_price, volatility)
            self.logger.info(f"✓ Grid initialized with {len(self.grid_strategy.grid_levels)} levels")

            # Set initial peak balance for drawdown tracking
            self.risk_manager.peak_balance = self.account_balance

            self.logger.info("✓ Initialization complete\n")
            return True

        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            self.status_display.display_error(str(e))
            return False

    def start(self):
        """Start the bot"""
        if not self.initialize():
            self.logger.error("Failed to initialize bot")
            return

        self.running = True
        self.logger.info("Bot started and running...")

        # Place initial grid orders
        self._place_grid_orders()

        # Main event loop
        self._run_event_loop()

    def _run_event_loop(self):
        """Main event loop"""
        loop_interval = 5  # seconds

        while self.running:
            try:
                if self.paused:
                    time.sleep(loop_interval)
                    continue

                # Update current price
                self._update_price()

                # Update order statuses
                self._update_orders()

                # Check risk limits
                self._check_risk_limits()

                # Check for grid rebalancing
                self._check_grid_rebalance()

                # Place pending orders
                self._place_pending_orders()

                # Update performance metrics
                self._update_metrics()

                # Display status
                self._display_status()

                # Save state
                self._save_state()

                # Reset daily stats if new day
                self.risk_manager.reset_daily_stats()

                # Sleep before next iteration
                time.sleep(loop_interval)

            except KeyboardInterrupt:
                self.logger.info("Received keyboard interrupt")
                break

            except Exception as e:
                self.logger.error(f"Error in event loop: {e}", exc_info=True)
                time.sleep(loop_interval)

        self.shutdown()

    def _update_price(self):
        """Update current price"""
        try:
            # Update every 5 seconds
            if (datetime.now() - self.last_price_update).total_seconds() < 5:
                return

            ticker = self.client.get_ticker_price(self.config.grid.symbol)
            self.current_price = float(ticker['price'])

            # Update volatility calculator
            self.grid_strategy.volatility_calculator.add_price(self.current_price)

            self.last_price_update = datetime.now()

        except Exception as e:
            self.logger.error(f"Failed to update price: {e}")

    def _update_orders(self):
        """Update order statuses"""
        try:
            # Update every 10 seconds
            if (datetime.now() - self.last_order_sync).total_seconds() < 10:
                return

            # Update all active orders
            updated = self.order_manager.update_all_orders()

            # Sync with exchange every minute
            if (datetime.now() - self.last_order_sync).total_seconds() > 60:
                self.order_manager.sync_orders_with_exchange()

            self.last_order_sync = datetime.now()

        except Exception as e:
            self.logger.error(f"Failed to update orders: {e}")

    def _place_grid_orders(self):
        """Place initial grid orders"""
        try:
            # Get pending grid levels
            pending_levels = self.grid_strategy.get_pending_orders()

            if not pending_levels:
                return

            # Create orders
            orders = self.order_manager.create_grid_orders(pending_levels)

            # Place orders
            self.logger.info(f"Placing {len(orders)} grid orders...")
            results = self.order_manager.place_multiple_orders(orders, delay=0.2)

            # Update grid levels with order IDs
            for order_id in results['success']:
                order = self.order_manager.orders[order_id]
                self.grid_strategy.mark_order_placed(order.price, order_id)

            self.logger.info(f"✓ Placed {len(results['success'])}/{len(orders)} orders")

            if results['failed']:
                self.logger.warning(f"Failed to place {len(results['failed'])} orders")

        except Exception as e:
            self.logger.error(f"Failed to place grid orders: {e}")

    def _place_pending_orders(self):
        """Place any pending orders"""
        try:
            pending_levels = self.grid_strategy.get_pending_orders()

            if pending_levels:
                orders = self.order_manager.create_grid_orders(pending_levels)

                if orders:
                    self.logger.info(f"Placing {len(orders)} pending orders...")
                    results = self.order_manager.place_multiple_orders(orders, delay=0.2)

                    for order_id in results['success']:
                        order = self.order_manager.orders[order_id]
                        self.grid_strategy.mark_order_placed(order.price, order_id)

        except Exception as e:
            self.logger.error(f"Failed to place pending orders: {e}")

    def _check_risk_limits(self):
        """Check risk limits and positions"""
        try:
            # Update account balance
            account_info = self.client.get_account_info()
            for asset in account_info.get('assets', []):
                if asset['asset'] == 'USDT':
                    self.account_balance = float(asset['walletBalance'])
                    break

            # Update drawdown
            self.risk_manager.update_drawdown(self.account_balance)

            # Check stop loss and take profit for positions
            for symbol in list(self.risk_manager.positions.keys()):
                if self.risk_manager.check_stop_loss(symbol, self.current_price):
                    self.logger.warning(f"Stop loss triggered for {symbol}")
                    self._close_position(symbol)

                elif self.risk_manager.check_take_profit(symbol, self.current_price):
                    self.logger.info(f"Take profit triggered for {symbol}")
                    self._close_position(symbol)

            # Check if emergency stop is active
            if self.risk_manager.emergency_stop:
                self.logger.error(f"Emergency stop active: {self.risk_manager.stop_reason}")
                self.pause()

        except Exception as e:
            self.logger.error(f"Failed to check risk limits: {e}")

    def _close_position(self, symbol: str):
        """Close a position"""
        try:
            response = self.client.close_position(symbol)
            self.logger.info(f"Position closed for {symbol}: {response}")

            # Update risk manager
            if symbol in self.risk_manager.positions:
                self.risk_manager.close_position(symbol, self.current_price)

        except Exception as e:
            self.logger.error(f"Failed to close position for {symbol}: {e}")

    def _check_grid_rebalance(self):
        """Check if grid should be rebalanced"""
        try:
            if self.grid_strategy.should_rebalance():
                self.logger.info("Rebalancing grid...")

                # Cancel all existing orders
                self.order_manager.cancel_all_orders(self.config.grid.symbol)

                # Calculate new volatility
                volatility = self.grid_strategy.volatility_calculator.calculate_volatility()

                # Rebalance grid
                self.grid_strategy.rebalance_grid(self.current_price, volatility)

                # Place new orders
                self._place_grid_orders()

                self.logger.info("✓ Grid rebalanced")

        except Exception as e:
            self.logger.error(f"Failed to rebalance grid: {e}")

    def _update_metrics(self):
        """Update performance metrics"""
        try:
            # Update every 5 minutes
            if (datetime.now() - self.last_metrics_update).total_seconds() < self.config.monitoring.metrics_interval:
                return

            metrics = self.performance_tracker.record_metrics(
                self.account_balance,
                self.risk_manager,
                self.order_manager,
                self.grid_strategy
            )

            self.last_metrics_update = datetime.now()

        except Exception as e:
            self.logger.error(f"Failed to update metrics: {e}")

    def _display_status(self):
        """Display status update"""
        try:
            # Display every 30 seconds
            if (datetime.now() - self.last_status_update).total_seconds() < 30:
                return

            self.status_display.display_status(
                self.grid_strategy,
                self.risk_manager,
                self.order_manager,
                self.account_balance
            )

            self.last_status_update = datetime.now()

        except Exception as e:
            self.logger.error(f"Failed to display status: {e}")

    def _save_state(self):
        """Save bot state"""
        try:
            if self.state_manager.should_save_state():
                self.state_manager.save_state(
                    self.grid_strategy,
                    self.risk_manager,
                    self.order_manager
                )

        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")

    def pause(self):
        """Pause bot operations"""
        self.paused = True
        self.logger.warning("Bot paused")
        self.status_display.display_warning("Bot operations paused")

    def resume(self):
        """Resume bot operations"""
        self.paused = False
        self.logger.info("Bot resumed")
        self.status_display.display_info("Bot operations resumed")

    def shutdown(self):
        """Shutdown bot gracefully"""
        self.logger.info("Shutting down bot...")

        self.running = False

        try:
            # Save final state
            self.state_manager.save_state(
                self.grid_strategy,
                self.risk_manager,
                self.order_manager
            )

            # Save metrics
            self.performance_tracker.save_metrics()

            # Display final summary
            summary = self.performance_tracker.get_performance_summary()
            self.logger.info("=" * 60)
            self.logger.info("Final Performance Summary:")
            self.logger.info(f"Runtime: {summary.get('runtime_hours', 0):.2f} hours")
            self.logger.info(f"Total PnL: {summary.get('total_pnl', 0):.2f} USDT ({summary.get('total_pnl_percent', 0):.2f}%)")
            self.logger.info(f"Total Trades: {summary.get('total_trades', 0)}")
            self.logger.info(f"Win Rate: {summary.get('win_rate', 0):.1f}%")
            self.logger.info(f"Max Drawdown: {summary.get('max_drawdown', 0):.2f}%")
            self.logger.info("=" * 60)

            # Optionally cancel all orders
            # Uncomment if you want to cancel orders on shutdown
            # self.order_manager.cancel_all_orders(self.config.grid.symbol)

            self.logger.info("Shutdown complete")

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Institutional Adaptive Grid Bot')
    parser.add_argument('--config', type=str, help='Path to configuration file')
    parser.add_argument('--dry-run', action='store_true', help='Run in dry-run mode (no actual trades)')

    args = parser.parse_args()

    try:
        bot = GridBot(config_file=args.config)

        if args.dry_run:
            bot.logger.warning("Running in DRY-RUN mode - no trades will be executed")

        bot.start()

    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
