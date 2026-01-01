# rhapi - Dual-Exchange Crypto Trading Bot

A modular, production-ready cryptocurrency trading bot supporting both Robinhood and Coinbase exchanges with automated buy/sell strategies.

## Features

- **Multi-Exchange Support**: Trade on both Robinhood (USD pairs) and Coinbase (USDC pairs)
- **Automated Trading**: Automatic buy-on-dip and sell-on-profit strategies
- **Modular Architecture**: Clean separation of concerns with testable components
- **Concurrent Processing**: Optional multi-threaded coin processing for faster scans
- **DRY_RUN Mode**: Test strategies without placing real orders
- **Portfolio Management**: Interactive CLI for managing watched coins
- **Configuration**: Environment variable-based configuration with sensible defaults
- **Comprehensive Testing**: Unit tests with mocked external dependencies
- **CI/CD**: GitHub Actions workflow for automated testing

## Quick Start

### Prerequisites

- Python 3.10 or higher
- Robinhood API credentials (API key and private key)
- Coinbase Advanced Trade API credentials

### Installation

1. Clone the repository:
```bash
git clone https://github.com/thegregguy/rhapi.git
cd rhapi
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your API credentials
```

### Configuration

Edit the `.env` file with your settings:

```env
# Required: API Credentials
API_KEY=your_robinhood_api_key
BASE64_PRIVATE_KEY=your_robinhood_private_key
CB_API_KEY=your_coinbase_api_key
CB_PRIVATE_KEY=your_coinbase_private_key

# Trading Parameters
DEFAULT_BUY_USD=1.00          # Amount to spend per buy order
COOLDOWN_SECONDS=600          # Time between buys for same coin
SCAN_INTERVAL=15              # Seconds between trading scans

# Performance
USE_CONCURRENCY=true          # Enable parallel processing
MAX_WORKERS=4                 # Thread pool size

# Operational Modes
AUTO_DRY_RUN=false           # Set to true to prevent real orders
DEBUG=false                   # Enable verbose logging
```

### Usage

#### Interactive Mode

Run the bot with an interactive menu:

```bash
python auto_trader.py
```

Menu options:
1. **Start Auto-Trader**: Begin automated trading loop
2. **Manage Portfolio**: Add/remove coins, toggle buy permissions
3. **Check Account Balances**: View available funds on each exchange
4. **Clear Logs**: Remove log files
5. **System Diagnostics**: Test API connectivity and configuration

#### DRY_RUN Mode (Recommended for Testing)

Test the bot without placing real orders:

```bash
AUTO_DRY_RUN=true python auto_trader.py
```

#### Development Mode

Enable debug logging:

```bash
DEBUG=true python auto_trader.py
```

## Architecture

### Project Structure

```
rhapi/
├── trader/                    # Main trading package
│   ├── __init__.py           # Package exports
│   ├── config.py             # Configuration management
│   ├── core.py               # Trader class with trading logic
│   └── exchanges.py          # Exchange adapter with API wrappers
├── tests/                     # Unit tests
│   ├── test_trader_core.py   # Trader class tests
│   └── test_setcoin.py       # Portfolio management tests
├── .github/workflows/         # CI/CD configuration
│   └── ci.yml                # GitHub Actions workflow
├── auto_trader.py            # CLI entrypoint
├── bot.py                    # Legacy bot functions (wrapped by exchanges.py)
├── setcoin.py                # Portfolio persistence
├── bugeater.py               # Logging utilities
├── rhapi.py                  # Robinhood API client
├── cbapi.py                  # Coinbase API client
├── requirements.txt          # Python dependencies
└── .env.example              # Example configuration
```

### Core Components

#### Trader Class (`trader/core.py`)
- Main trading orchestrator
- Fetches holdings once per scan (cached)
- Processes coins sequentially or concurrently
- Implements buy/sell decision logic
- Respects DRY_RUN mode

#### ExchangeAdapter Class (`trader/exchanges.py`)
- Unified interface for multiple exchanges
- Handles symbol normalization (USD vs USDC suffixes)
- Wraps external API calls
- DRY_RUN order interception
- Holdings caching

#### Config Class (`trader/config.py`)
- Environment variable parsing
- Default value management
- API key validation
- Type-safe configuration access

## Trading Strategy

The bot implements a simple momentum-based strategy:

### Buy Conditions
- Coin must have `can_buy` enabled in portfolio
- Price drops below dip threshold (based on spread × dip_mult)
- Cooldown period has elapsed since last buy
- Sufficient buying power available

### Sell Conditions
- Coin has holdings worth > $1
- Price rises above profit threshold (based on spread × profit_mult)

### Parameters (per coin)
- `profit_mult`: Multiplier for profit target (default: 2.0)
- `dip_mult`: Multiplier for dip detection (default: 3.0)
- `can_buy`: Enable/disable buying for this coin

## Testing

### Run Unit Tests

```bash
pytest -v
```

### Run Specific Test File

```bash
pytest tests/test_trader_core.py -v
```

### Test Coverage

```bash
pytest --cov=trader --cov-report=html
```

## Performance Optimizations

### Implemented Optimizations
1. **Single Holdings Fetch**: Holdings fetched once per scan, cached for all coins
2. **Removed Blocking Sleeps**: No per-coin delays, only scan interval
3. **Optional Concurrency**: ThreadPoolExecutor for parallel coin processing
4. **Efficient Portfolio Updates**: Atomic file writes with temp file

### Concurrency

Enable concurrent processing in `.env`:
```env
USE_CONCURRENCY=true
MAX_WORKERS=4
```

Concurrency is most beneficial when:
- Portfolio has many coins (>5)
- Network latency is significant
- API rate limits allow parallel requests

## Safety Features

### DRY_RUN Mode
Prevents all real orders while simulating trading logic:
```bash
AUTO_DRY_RUN=true python auto_trader.py
```

### Cooldown Protection
Prevents rapid repeated buys of the same coin (default: 10 minutes)

### Atomic Portfolio Writes
Portfolio file updates use temp file + rename for crash safety

## API Documentation

### Robinhood API
- Trading endpoint: `https://trading.robinhood.com`
- Authentication: API key + ED25519 signed requests
- Pairs: Crypto-USD (e.g., BTC-USD)

### Coinbase Advanced Trade API
- Python SDK: `coinbase-advanced-py`
- Authentication: API key + secret
- Pairs: Crypto-USDC (e.g., BTC-USDC)

## Troubleshooting

### Common Issues

**Import Error**: `ModuleNotFoundError: No module named 'trader'`
- Solution: Ensure you're in the project root directory
- Run: `pip install -r requirements.txt`

**API Connection Failed**
- Verify credentials in `.env` file
- Check network connectivity
- Run diagnostics: Menu option 9

**No Trades Executing**
- Verify `can_buy` is enabled for coins
- Check account balances
- Ensure not in DRY_RUN mode
- Verify price meets buy/sell thresholds

**Tests Failing**
- Install test dependencies: `pip install pytest pytest-mock`
- Check Python version (3.10+ required)

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass: `pytest`
5. Submit a pull request

### Development Setup

```bash
# Install dev dependencies
pip install -r requirements.txt

# Run tests
pytest -v

# Run with debug logging
DEBUG=true python auto_trader.py
```

## License

This project is provided as-is without warranty. Use at your own risk.

Trading cryptocurrencies involves substantial risk of loss. The authors are not responsible for any financial losses incurred through use of this software.

## Contributors

- **thegregguy** - Original author
- **Repository Refactoring (2026)** - Modularization, testing infrastructure, and performance improvements

## Changelog

### Version 2.0.0 (2026-01)
- **Refactored** to modular package structure
- **Added** Trader class with clean separation of concerns
- **Added** configuration via environment variables
- **Added** DRY_RUN mode for safe testing
- **Added** optional concurrency for IO-bound operations
- **Added** unit tests with pytest and mocks
- **Added** GitHub Actions CI workflow
- **Improved** performance by caching holdings per scan
- **Improved** logging with standard library bridge
- **Removed** per-coin blocking sleeps
- **Updated** documentation with comprehensive README

### Version 1.0.0 (Original)
- Initial implementation with dual-exchange support
- Basic buy/sell automation
- Interactive CLI menu
