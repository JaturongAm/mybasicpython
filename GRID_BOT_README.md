# Institutional Adaptive Grid Bot for Binance Futures

A professional-grade, adaptive grid trading bot for Binance Futures with institutional features including risk management, performance tracking, and automatic volatility-based grid adjustment.

## Features

### Core Features
- ✅ **Adaptive Grid Strategy**: Automatically adjusts grid spacing based on market volatility
- ✅ **Risk Management**: Built-in stop-loss, take-profit, position limits, and drawdown protection
- ✅ **Order Management**: Efficient order placement, tracking, and synchronization
- ✅ **Performance Tracking**: Real-time metrics, statistics, and performance reporting
- ✅ **State Persistence**: Automatic state saving and recovery
- ✅ **Comprehensive Logging**: Detailed logging for monitoring and debugging

### Advanced Features
- 📊 Volatility-based grid rebalancing
- 🔒 Multi-layer risk controls (position size, daily loss limits, max drawdown)
- ⚡ Rate limiting and exponential backoff for API calls
- 🔄 Automatic order synchronization with exchange
- 📈 Real-time performance metrics and statistics
- 🛡️ Emergency stop mechanism
- 💾 State persistence for recovery

## Architecture

```
grid_bot.py           # Main orchestrator
├── config.py         # Configuration management
├── binance_client.py # Binance Futures API client
├── grid_strategy.py  # Adaptive grid strategy engine
├── risk_manager.py   # Risk management module
├── order_manager.py  # Order management system
└── monitoring.py     # Logging, monitoring, and performance tracking
```

## Installation

### Prerequisites
- Python 3.8 or higher
- Binance Futures account with API keys
- Sufficient USDT balance for trading

### Setup

1. **Clone the repository**
```bash
cd mybasicpython
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your API keys
```

4. **Create configuration file**
```bash
cp config.example.json config.json
# Adjust settings according to your strategy
```

## Configuration

### API Configuration
Set your Binance API credentials in `.env`:
```env
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
BINANCE_TESTNET=True  # Set to False for live trading
```

### Trading Configuration
Edit `config.json` to customize your strategy:

#### Grid Settings
```json
{
  "grid": {
    "symbol": "BTCUSDT",              // Trading pair
    "grid_levels": 20,                 // Number of grid levels
    "grid_spacing_percent": 0.5,       // Initial spacing between levels (%)
    "order_quantity_usdt": 100.0,      // USDT per grid level
    "leverage": 5,                     // Leverage multiplier
    "adaptive_mode": true,             // Enable adaptive spacing
    "volatility_window": 24,           // Hours for volatility calculation
    "min_grid_spacing": 0.2,           // Minimum spacing (%)
    "max_grid_spacing": 2.0,           // Maximum spacing (%)
    "rebalance_interval": 3600         // Seconds between rebalancing
  }
}
```

#### Risk Settings
```json
{
  "risk": {
    "max_position_usdt": 10000.0,      // Maximum total position size
    "max_drawdown_percent": 15.0,      // Maximum drawdown before stop
    "stop_loss_percent": 5.0,          // Stop loss per position
    "take_profit_percent": 10.0,       // Take profit target
    "max_daily_loss_usdt": 500.0,      // Maximum daily loss
    "max_open_orders": 40,             // Maximum open orders
    "min_order_spacing_percent": 0.1   // Minimum order spacing
  }
}
```

## Usage

### Start the Bot

**Testnet Mode (Recommended for testing)**
```bash
python grid_bot.py --config config.json
```

**Dry Run Mode (No actual trades)**
```bash
python grid_bot.py --config config.json --dry-run
```

**Live Trading (Use with caution)**
```bash
# Set BINANCE_TESTNET=False in .env first
python grid_bot.py --config config.json
```

### Monitor the Bot

The bot displays real-time status updates every 30 seconds:
```
┌─────────────────── Account Status ───────────────────┐
│ Balance: $10,000.00 USDT
│ Total PnL: $150.00 USDT (1.50%)
│ Daily PnL: $50.00 USDT
│ Unrealized PnL: $25.00 USDT
│ Drawdown: 2.5% (Max: 5.0%)
└──────────────────────────────────────────────────────┘

┌─────────────────── Grid Status ──────────────────────┐
│ Price Range: $40,000.00 - $42,000.00
│ Current Price: $41,000.00
│ Grid Spacing: 0.50%
│ Grid Levels: 20 (Filled: 8)
│ Grid Profit: $200.00 USDT
└──────────────────────────────────────────────────────┘
```

### View Logs

Logs are stored in the `logs/` directory:
```bash
tail -f logs/grid_bot.log
```

### Check Metrics

Performance metrics are saved in `metrics/` directory:
```bash
cat metrics/metrics_20250101.json
```

## Strategy Explanation

### Grid Trading
Grid trading places buy and sell orders at regular price intervals (grid levels) around the current market price. When a buy order fills, a corresponding sell order is placed above it, and vice versa. This strategy profits from market volatility within a range.

### Adaptive Grid
The adaptive feature adjusts grid spacing based on market volatility:
- **High volatility** → Wider grid spacing (fewer whipsaws)
- **Low volatility** → Tighter grid spacing (more opportunities)

### Risk Management
Multiple layers of protection:
1. **Position Limits**: Caps total exposure
2. **Stop Loss**: Automatic exit on excessive loss
3. **Take Profit**: Lock in profits at target
4. **Drawdown Protection**: Emergency stop at max drawdown
5. **Daily Loss Limits**: Caps daily losses

## Performance Metrics

The bot tracks comprehensive metrics:
- **Total PnL**: Overall profit/loss
- **Win Rate**: Percentage of profitable trades
- **Profit Factor**: Ratio of average win to average loss
- **Max Drawdown**: Largest peak-to-trough decline
- **Grid Profit**: Profit from grid trading specifically
- **Order Fill Rate**: Percentage of orders filled

## Safety & Best Practices

### Before Running
1. ✅ **Test on testnet first** - Always test with testnet before live trading
2. ✅ **Start small** - Begin with small position sizes
3. ✅ **Monitor closely** - Watch the bot especially in first hours
4. ✅ **Set conservative limits** - Use conservative risk settings initially
5. ✅ **Check API permissions** - Ensure API keys have only necessary permissions

### API Key Security
- Enable IP whitelist on Binance
- Use read + trade permissions only (no withdrawal)
- Store keys in `.env` file (never commit to git)
- Rotate keys periodically

### Risk Warnings
- **Market Risk**: Crypto markets are highly volatile
- **Liquidation Risk**: Futures trading uses leverage
- **System Risk**: Bot failures or connectivity issues
- **API Risk**: Exchange API changes or downtime

⚠️ **NEVER invest more than you can afford to lose**

## Troubleshooting

### Common Issues

**Bot won't start**
- Check API keys in `.env`
- Verify sufficient balance
- Ensure testnet/mainnet setting is correct

**Orders not filling**
- Check grid spacing (may be too wide)
- Verify sufficient liquidity for symbol
- Check order sizes meet minimum requirements

**Emergency stop triggered**
- Review risk limits in config
- Check drawdown settings
- Monitor logs for specific reason

**Rate limiting errors**
- Reduce order placement frequency
- Increase delay between orders
- Check Binance API rate limits

## Development

### Running Tests
```bash
pytest tests/ -v --cov
```

### Code Style
```bash
black *.py
flake8 *.py
```

### Adding Features
The modular architecture makes it easy to extend:
- Custom strategies → Modify `grid_strategy.py`
- New risk controls → Extend `risk_manager.py`
- Additional monitoring → Update `monitoring.py`

## File Structure

```
mybasicpython/
├── grid_bot.py              # Main bot orchestrator
├── config.py                # Configuration management
├── binance_client.py        # Binance API client
├── grid_strategy.py         # Grid strategy engine
├── risk_manager.py          # Risk management
├── order_manager.py         # Order management
├── monitoring.py            # Monitoring & logging
├── config.json              # User configuration
├── .env                     # API credentials (gitignored)
├── requirements.txt         # Python dependencies
├── logs/                    # Log files
│   └── grid_bot.log
├── metrics/                 # Performance metrics
│   └── metrics_YYYYMMDD.json
└── state/                   # Bot state persistence
    └── bot_state.json
```

## Support & Contributing

### Getting Help
- Check logs in `logs/grid_bot.log`
- Review configuration settings
- Test on testnet first
- Read Binance API documentation

### Contributing
Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request

## Disclaimer

This software is provided for educational purposes only. Use at your own risk. The authors are not responsible for any financial losses incurred through the use of this bot.

**Trading cryptocurrencies carries significant risk. Past performance does not guarantee future results.**

## License

MIT License - See LICENSE file for details

## Version History

### v1.0.0 (2025-01-05)
- Initial release
- Adaptive grid strategy
- Comprehensive risk management
- Performance tracking
- State persistence

## Acknowledgments

- Binance for providing Futures API
- Python community for excellent libraries
- Grid trading community for strategy insights

---

**Happy Trading! 🚀**

*Remember: Always test thoroughly on testnet before live trading.*
