# RHAPI - Unified Crypto Trading Bot

A modular, testable cryptocurrency trading bot that supports both Robinhood and Coinbase exchanges.

## Features

- **Dual Exchange Support**: Trade on both Robinhood (USD pairs) and Coinbase (USDC pairs)
- **Automated Trading**: Configurable buy/sell triggers based on price movements
- **Dry Run Mode**: Test strategies without placing real orders
- **Concurrent Execution**: Optional parallel processing for improved performance
- **Portfolio Management**: Track positions across multiple exchanges
- **Interactive CLI**: User-friendly menu system for managing trades

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

3. Configure your environment:
```bash
cp .env.example .env
# Edit .env with your API keys and preferences
```

## Configuration

All configuration is done via environment variables. See `.env.example` for all available options:

- **API Keys**: Configure Robinhood and Coinbase API credentials
- **Trading Parameters**: Set buy amounts, cooldown periods, scan intervals
- **Concurrency**: Control parallel execution with `MAX_WORKERS`
- **Dry Run**: Enable `AUTO_DRY_RUN=true` for testing without real trades
- **Logging**: Configure debug mode and log levels

## Usage

### Starting the Bot

Run the interactive menu:
```bash
python auto_trader.py
```

### Running in Dry-Run Mode

Test without placing real orders:
```bash
AUTO_DRY_RUN=true python auto_trader.py
```

### Running Tests

Execute the test suite:
```bash
pytest -q
```

Run tests with coverage:
```bash
pytest --cov=trader --cov=setcoin
```

## Architecture

```
rhapi/
├── auto_trader.py          # CLI entrypoint
├── trader/
│   ├── __init__.py        # Package initialization
│   ├── config.py          # Configuration management
│   ├── core.py            # Main Trader class
│   └── exchanges.py       # Exchange adapter functions
├── setcoin.py             # Portfolio state management
├── bugeater.py            # Logging utilities
├── rhapi.py               # Robinhood API client
├── cbapi.py               # Coinbase API client
└── tests/
    ├── test_trader_core.py
    └── test_setcoin.py
```

## Trading Logic

The bot monitors configured cryptocurrency pairs and:

1. **Buys** when price drops below a threshold (configurable dip multiplier)
2. **Sells** when profit target is reached (configurable profit multiplier)
3. **Respects** cooldown periods between purchases
4. **Tracks** positions and invested amounts per coin

## Safety Features

- **Dry Run Mode**: Test strategies without real money
- **Cooldown Periods**: Prevent rapid consecutive purchases
- **Portfolio Tracking**: Maintain accurate state across sessions
- **Error Handling**: Graceful recovery from API failures
- **Type Safety**: Decimal precision for financial calculations

## Development

### Project Structure

- `trader/core.py`: Main trading logic and scan loop
- `trader/exchanges.py`: Unified interface for multiple exchanges
- `setcoin.py`: Portfolio persistence and state management
- `bugeater.py`: Colored logging with debug modes

### Contributing

Contributions are welcome! This refactor modernizes the codebase with:
- Modular, testable architecture
- Type hints and documentation
- Unit test coverage
- CI/CD integration

## License

[Original License] - Contributors: Refactor by GitHub Copilot

## Disclaimer

This software is for educational purposes only. Trading cryptocurrencies carries risk. Use at your own discretion.
