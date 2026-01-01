# RHAPI - Robinhood & Coinbase Crypto Auto Trader

A modular cryptocurrency auto-trading bot supporting both Robinhood and Coinbase exchanges with automated buy/sell strategies based on dip detection and profit targets.

## Features

- **Dual-Exchange Support**: Trade on both Robinhood (USD pairs) and Coinbase (USDC pairs)
- **Automated Trading**: Buy on dips, sell on profit targets
- **Portfolio Management**: Track holdings and manage trading strategies
- **Dry Run Mode**: Test strategies without placing real orders
- **Concurrent Scanning**: Optional parallel processing for improved performance
- **Interactive CLI**: User-friendly menu system for manual control

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

3. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your API credentials and preferences
```

## Configuration

Edit the `.env` file with your settings:

- **API_KEY / BASE64_PRIVATE_KEY**: Robinhood API credentials
- **CB_API_KEY / CB_PRIVATE_KEY**: Coinbase API credentials
- **DEFAULT_BUY_USD**: Amount in USD to buy per transaction (default: 1.00)
- **COOLDOWN**: Minimum seconds between buys for the same coin (default: 600)
- **SCAN_INTERVAL**: Seconds between portfolio scans (default: 15)
- **MAX_WORKERS**: Number of concurrent workers (default: 4, set to 1 for sequential)
- **AUTO_DRY_RUN**: Set to `true` to prevent real orders (testing mode)
- **DEBUG**: Enable verbose logging
- **LOG_LEVEL**: Logging level (INFO, DEBUG, WARNING, ERROR)

## Usage

### Start the Interactive CLI

```bash
python auto_trader.py
```

The menu provides options to:
1. Start the auto-trader
2. Manage portfolio and watchlist
3. Check account balances
4. Run diagnostics
5. Clear logs

### Dry Run Mode (Testing)

Test the bot without placing real orders:

```bash
AUTO_DRY_RUN=true python auto_trader.py
```

### Run Unit Tests

```bash
pytest -q
```

## Project Structure

```
rhapi/
├── auto_trader.py          # CLI entrypoint
├── trader/                 # Core trading logic
│   ├── __init__.py
│   ├── config.py          # Configuration management
│   ├── core.py            # Main Trader class
│   └── exchanges.py       # Exchange adapter functions
├── bot.py                 # Legacy exchange interface (kept for compatibility)
├── setcoin.py             # Portfolio state management
├── bugeater.py            # Logging and debugging utilities
├── rhapi.py               # Robinhood API client
├── cbapi.py               # Coinbase API client
├── utils.py               # Helper functions
├── tests/                 # Unit tests
│   ├── test_trader_core.py
│   └── test_setcoin.py
└── requirements.txt       # Python dependencies
```

## Trading Strategy

The bot implements a simple but effective strategy:

1. **Watch Mode**: Monitor coins with no position
2. **Risk-On Mode**: Monitor coins with active positions
3. **Buy Signal**: Triggered when price drops below the dip threshold (configurable multiplier)
4. **Sell Signal**: Triggered when profit target is reached (configurable multiplier)
5. **Cooldown**: Prevents rapid buy/sell cycles

## Safety Features

- **Dry Run Mode**: Test without risking real funds
- **Cooldown Period**: Prevents overtrading
- **Per-Exchange Routing**: Automatic symbol normalization
- **Error Handling**: Graceful failure with detailed logging
- **Atomic File Operations**: Safe portfolio persistence

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=trader --cov=setcoin

# Run specific test file
pytest tests/test_trader_core.py
```

### Code Style

The project follows Python best practices:
- Type hints for public functions
- Docstrings for classes and methods
- Modular design with clear separation of concerns

## Contributing

Contributions are welcome! This refactoring was performed to modernize the codebase and make it more maintainable and testable.

## License

[Original repository license applies]

## Disclaimer

**USE AT YOUR OWN RISK**: This software is for educational purposes. Cryptocurrency trading involves substantial risk of loss. The authors are not responsible for any financial losses incurred while using this software.

## Credits

Original implementation by thegregguy. Refactored for modularity, testability, and production readiness.
