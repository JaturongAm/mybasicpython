# Quick Start Guide - Grid Bot

Get your institutional adaptive grid bot running in 5 minutes!

## Prerequisites Checklist

- [ ] Python 3.8+ installed
- [ ] Binance Futures account created
- [ ] API keys generated (with Futures trading enabled)
- [ ] Testnet access enabled (recommended for testing)

## Step 1: Installation (2 minutes)

```bash
# Navigate to project directory
cd mybasicpython

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Configuration (2 minutes)

### Create Environment File
```bash
# Copy example environment file
cp .env.example .env

# Edit with your favorite editor
nano .env  # or vim, code, etc.
```

Add your Binance API credentials:
```env
BINANCE_API_KEY=your_actual_api_key_here
BINANCE_API_SECRET=your_actual_secret_here
BINANCE_TESTNET=True  # Keep True for testing!
```

### Create Configuration File
```bash
# Copy example config
cp config.example.json config.json

# Edit if you want to customize (optional for first run)
nano config.json
```

**For first run, you can use the default settings!**

## Step 3: Get Testnet Funds (1 minute)

1. Visit: https://testnet.binancefuture.com
2. Login with your Binance account
3. Click "Get Test Funds" to receive testnet USDT
4. You should get 10,000 USDT for testing

## Step 4: Run the Bot (30 seconds)

```bash
# Start the bot on testnet
python grid_bot.py --config config.json
```

You should see:
```
╔══════════════════════════════════════════════════════════════╗
║     Institutional Adaptive Grid Bot - Binance Futures       ║
║                  Trading System v1.0                         ║
╚══════════════════════════════════════════════════════════════╝

Testing API connectivity...
✓ API connection successful
✓ Account balance: 10000.00 USDT
✓ Leverage set to 5x
✓ Current price: 41000.00
✓ Market volatility: 1.50% (medium)
✓ Grid initialized with 20 levels
✓ Initialization complete

Bot started and running...
```

## Step 5: Monitor (Ongoing)

Watch the bot in action! Status updates appear every 30 seconds.

### Check Logs
```bash
# In another terminal
tail -f logs/grid_bot.log
```

### Stop the Bot
Press `Ctrl+C` to stop gracefully. The bot will:
- Save current state
- Save performance metrics
- Display final summary

## What's Happening?

1. **Grid Initialization**: Bot creates 20 buy/sell orders around current price
2. **Order Placement**: Orders are placed at calculated grid levels
3. **Order Monitoring**: Bot tracks order fills and status
4. **Position Management**: Manages positions with risk controls
5. **Grid Rebalancing**: Adjusts grid spacing based on volatility (every hour)

## Understanding the Status Display

```
┌─────────────────── Account Status ───────────────────┐
│ Balance: $10,000.00 USDT              ← Your balance
│ Total PnL: $50.00 USDT (0.50%)        ← Total profit
│ Daily PnL: $25.00 USDT                ← Today's profit
│ Unrealized PnL: $10.00 USDT           ← Open position P&L
│ Drawdown: 2.0% (Max: 3.5%)            ← Risk metric
└──────────────────────────────────────────────────────┘
```

## Quick Configuration Tips

### Conservative Settings (Lower Risk)
```json
{
  "grid": {
    "order_quantity_usdt": 50.0,     // Smaller orders
    "leverage": 2,                    // Lower leverage
    "grid_spacing_percent": 0.8      // Wider spacing
  },
  "risk": {
    "max_position_usdt": 2000.0,     // Lower exposure
    "stop_loss_percent": 3.0         // Tighter stop loss
  }
}
```

### Aggressive Settings (Higher Risk)
```json
{
  "grid": {
    "order_quantity_usdt": 200.0,    // Larger orders
    "leverage": 10,                   // Higher leverage
    "grid_spacing_percent": 0.3      // Tighter spacing
  },
  "risk": {
    "max_position_usdt": 20000.0,    // Higher exposure
    "stop_loss_percent": 8.0         // Looser stop loss
  }
}
```

## Common First-Run Issues

### "Insufficient balance"
- Get testnet funds from testnet.binancefuture.com
- Or reduce `order_quantity_usdt` in config

### "API authentication failed"
- Double-check API keys in `.env`
- Ensure Futures trading is enabled for API keys
- Verify testnet keys for testnet trading

### "Cannot set leverage"
- This is usually just a warning, bot continues
- Leverage may already be set on exchange

### Orders not filling
- This is normal! Grid orders wait for price to reach them
- Watch for a few minutes as price moves
- Check `logs/grid_bot.log` for activity

## Testing Checklist

After starting the bot, verify:

- [ ] Bot starts without errors
- [ ] Grid orders are placed (check logs)
- [ ] Status displays every 30 seconds
- [ ] Can see orders on Binance testnet UI
- [ ] Log file is being created
- [ ] Can stop bot with Ctrl+C cleanly

## Next Steps

Once comfortable on testnet:

1. **Run for 24 hours** - Let it trade in different market conditions
2. **Review metrics** - Check `metrics/` folder for performance data
3. **Adjust settings** - Fine-tune based on results
4. **Test edge cases** - Try stopping/restarting, network issues, etc.

### Going Live (When Ready)

⚠️ **Only after thorough testnet testing!**

```bash
# 1. Update .env
BINANCE_TESTNET=False

# 2. Use MAINNET API keys (not testnet keys!)
BINANCE_API_KEY=your_mainnet_key
BINANCE_API_SECRET=your_mainnet_secret

# 3. Start with conservative settings
# Reduce position sizes significantly

# 4. Start the bot
python grid_bot.py --config config.json
```

## Getting Help

- **Check logs**: `logs/grid_bot.log`
- **Review README**: Full documentation in `GRID_BOT_README.md`
- **Test connectivity**: `python -c "from binance_client import *; client = BinanceFuturesClient('key', 'secret', True); print(client.test_connectivity())"`

## Quick Commands Reference

```bash
# Start bot
python grid_bot.py --config config.json

# Start in dry-run mode (no trades)
python grid_bot.py --config config.json --dry-run

# View logs
tail -f logs/grid_bot.log

# View today's metrics
cat metrics/metrics_$(date +%Y%m%d).json | python -m json.tool

# Check current state
cat state/bot_state.json | python -m json.tool
```

## Emergency Stop

If something goes wrong:

1. **Stop the bot**: `Ctrl+C`
2. **Check Binance**: Login to cancel orders manually if needed
3. **Review logs**: `logs/grid_bot.log`
4. **Check state**: `state/bot_state.json`

The bot has built-in emergency stop triggers:
- Max drawdown exceeded
- Daily loss limit hit
- Critical errors

## Performance Expectations

On testnet with default settings:
- **Orders**: 20 grid levels placed
- **Activity**: Depends on market volatility
- **Fills**: Varies (more in volatile markets)
- **Profit**: Comes from price oscillations within grid

Grid trading profits from volatility, not trends!

---

**You're all set! Start the bot and watch it trade. 🎉**

Questions? Check `GRID_BOT_README.md` for detailed documentation.
