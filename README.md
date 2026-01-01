# RHAPI - Modular Crypto Trading Bot

A modular cryptocurrency trading bot supporting Robinhood and Coinbase exchanges with automatic buy/sell strategies, concurrent processing, and comprehensive testing.

## Features

- 🔄 **Dual Exchange Support**: Trade on both Robinhood (RH) and Coinbase (CB)
- 🚀 **Concurrent Processing**: Process multiple coins simultaneously with configurable worker threads
- 🧪 **Dry-Run Mode**: Test strategies without placing real orders
- 📊 **Profit Tracking**: Accurate profit/loss calculation with investment tracking
- ⚙️ **Environment Configuration**: Configure all parameters via environment variables
- 🧹 **Clean Architecture**: Modular design with separate concerns (config, exchanges, core logic)
- ✅ **Tested**: Comprehensive unit tests with CI/CD

## Installation

1. Clone the repository:
```bash
git clone https://github.com/thegregguy/rhapi.git
cd rhapi
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables (copy `.env.example` to `.env` and fill in your API keys):
```bash
cp .env.example .env
# Edit .env with your API credentials
```

## Configuration

Configure the trader using environment variables in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTO_BUY_USD` | `1.00` | Dollar amount to spend per buy order |
| `AUTO_COOLDOWN` | `600` | Cooldown period between buys (seconds) |
| `SCAN_INTERVAL` | `15` | Time between market scans (seconds) |
| `MAX_WORKERS` | `4` | Number of concurrent worker threads |
| `AUTO_DRY_RUN` | `false` | Enable dry-run mode (no real orders) |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `DEBUG` | `false` | Enable debug output |

### API Credentials

Required environment variables for exchange APIs:

- `API_KEY` - Robinhood API key
- `BASE64_PRIVATE_KEY` - Robinhood private key (base64 encoded)
- `CB_API_KEY` - Coinbase API key
- `CB_PRIVATE_KEY` - Coinbase private key

## Usage

### Interactive Menu

Run the trader with interactive menu:
```bash
python auto_trader.py
```

Features:
1. 🚀 Start Auto-Trader
2. ⚙️  Manage Portfolio / Watches
3. 🔍 Check Account Balances
4. 🧹 Clear Logs
5. 🩺 System Diagnostics

### Dry-Run Mode

Test your strategy without placing real orders:
```bash
AUTO_DRY_RUN=true python auto_trader.py
```

In dry-run mode:
- No real orders are placed
- All buy/sell signals are logged but not executed
- Perfect for testing strategies and configurations

### Debug Mode

Enable detailed logging:
```bash
DEBUG=true LOG_LEVEL=DEBUG python auto_trader.py
```

## Testing

Run tests:
```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest -v

# Run with coverage
pytest --cov=trader --cov=setcoin --cov-report=term-missing

# Run specific test file
pytest tests/test_trader_core.py -v
```

## Architecture

### Project Structure

```
rhapi/
├── trader/               # Core trading package
│   ├── __init__.py
│   ├── config.py        # Configuration management
│   ├── core.py          # Main Trader class
│   └── exchanges.py     # Exchange API wrappers
├── tests/               # Unit tests
│   ├── test_trader_core.py
│   └── test_setcoin.py
├── auto_trader.py       # CLI entrypoint
├── bot.py              # Exchange API clients
├── setcoin.py          # Portfolio management
├── bugeater.py         # Logging utilities
├── requirements.txt    # Python dependencies
└── .env.example        # Environment template
```

### Key Components

#### Trader Class (`trader/core.py`)
- Fetches holdings once per scan (efficient)
- Processes coins concurrently using ThreadPoolExecutor
- Implements correct profit calculation logic
- Supports dry-run mode
- Consolidates state writes (single update per coin per scan)

#### Exchange Wrappers (`trader/exchanges.py`)
- Normalized API interface across RH and CB
- Symbol normalization (RH uses -USD, CB uses -USDC)
- Retry logic with exponential backoff
- Type conversions for API compatibility

#### Portfolio Management (`setcoin.py`)
- Atomic file writes using temp files
- Caching for efficient multiple reads
- Symbol normalization helpers

## Profit Calculation Fix

The trader correctly calculates profit/loss:

1. **With Investment Data**: Uses recorded `total_invested` value
2. **Fallback**: Uses `last_reference_price` if investment data missing
3. **Unknown**: Marks P/L as unknown if neither available

This prevents the bug where `total_invested` was being overwritten with current market value, causing incorrect 0% P/L.

## Trading Strategy

The bot uses a simple momentum strategy:

- **Buy on Dips**: Purchases when price drops below threshold
- **Sell on Profit**: Sells when target profit percentage reached
- **Cooldown**: Prevents repeated buys with configurable cooldown
- **Risk Management**: Tracks investment per coin

## Safety Features

- ✅ Dry-run mode for testing
- ✅ No secrets in code (environment variables only)
- ✅ Atomic file operations
- ✅ Comprehensive error handling
- ✅ Configurable cooldown periods
- ✅ Pre-flight diagnostics

## Development

### Running Tests

```bash
# Quick test
pytest -q

# Verbose with coverage
pytest -v --cov=trader --cov=setcoin

# Watch mode (requires pytest-watch)
ptw
```

### CI/CD

GitHub Actions automatically runs tests on:
- Push to `main` or `refactor/trader-modularization`
- Pull requests to `main`

See `.github/workflows/ci.yml` for CI configuration.

## License

See repository for license information.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run tests locally
5. Submit a pull request

## Support

For issues, questions, or contributions, please open an issue on GitHub.
