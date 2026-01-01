# rhapi - Modular Cryptocurrency Trading System

A production-ready, modular cryptocurrency trading system supporting both Robinhood and Coinbase exchanges with concurrent processing, dry-run mode, and comprehensive testing.

## 🌟 Features

- **Dual Exchange Support**: Trade on both Robinhood (RH) and Coinbase (CB)
- **Modular Architecture**: Clean separation of concerns with dedicated modules for config, exchanges, and core logic
- **Concurrent Processing**: Optional multi-threaded coin processing for improved performance
- **DRY_RUN Mode**: Test strategies without placing real orders
- **Decimal Precision**: Accurate numeric handling using Python's Decimal type
- **Smart Caching**: Single holdings fetch per scan with configurable TTL
- **Atomic Operations**: Thread-safe portfolio updates
- **Comprehensive Testing**: Unit tests with mocked external APIs
- **CI/CD**: GitHub Actions workflow for automated testing
- **Colored CLI**: Beautiful terminal UI with emoji indicators

## 📋 Requirements

- Python 3.9+
- Robinhood API credentials (API_KEY and BASE64_PRIVATE_KEY)
- Coinbase API credentials (CB_API_KEY and CB_PRIVATE_KEY)

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your API credentials:

```env
# Robinhood API Credentials
API_KEY=your_robinhood_api_key_here
BASE64_PRIVATE_KEY=your_base64_encoded_private_key_here

# Coinbase API Credentials
CB_API_KEY=your_coinbase_api_key_here
CB_PRIVATE_KEY=your_coinbase_private_key_here

# Trading Configuration
DEFAULT_BUY_USD=1.00
COOLDOWN=600
MAX_WORKERS=4

# Safety Features
AUTO_DRY_RUN=false

# Debug Mode
DEBUG=false
```

### 3. Run Tests

```bash
pytest -v
```

### 4. Test in Dry-Run Mode

```bash
AUTO_DRY_RUN=true python auto_trader.py
```

### 5. Run the Trader

```bash
python auto_trader.py
```

## 📁 Project Structure

```
rhapi/
├── trader/                    # Main trader package
│   ├── __init__.py
│   ├── config.py             # Environment configuration
│   ├── core.py               # Trader class with concurrent processing
│   └── exchanges.py          # Exchange adapters (RH + CB)
├── tests/                    # Unit tests
│   ├── test_trader_core.py
│   └── test_setcoin.py
├── .github/
│   └── workflows/
│       └── ci.yml            # GitHub Actions CI
├── auto_trader.py            # CLI entrypoint
├── setcoin.py                # Portfolio management
├── bugeater.py               # Logging utility
├── bot.py                    # Legacy exchange interface (kept for compatibility)
├── rhapi.py                  # Robinhood API client
├── cbapi.py                  # Coinbase API client
├── utils.py                  # Utility functions
├── requirements.txt          # Python dependencies
├── .env.example              # Example environment configuration
└── README.md                 # This file
```

## 🎯 Usage

### Main Menu

The trader provides an interactive CLI menu:

1. **🚀 Start Auto-Trader** - Begin automated trading
2. **⚙️ Manage Portfolio** - Add/remove coins, toggle trading
3. **💰 Check Balances** - View account balances
4. **🧹 Clear Logs** - Clean up log files
5. **🩺 System Diagnostics** - Test API connectivity
6. **❌ Exit** - Quit the application

### Portfolio Management

- **Add Coins**: Add cryptocurrency pairs to your watchlist
- **Toggle Trading**: Enable/disable buying for specific coins
- **Audit Portfolio**: Sync with your actual exchange holdings

### Trading Logic

The trader implements a simple but effective strategy:

- **WATCH Mode**: Monitors price movements when you have no position
- **RISK_ON Mode**: Actively manages positions to hit profit targets
- **Auto-buy on Dips**: Purchases coins when price drops below threshold
- **Auto-sell on Profit**: Sells when profit target is reached

### Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_BUY_USD` | 1.00 | Dollar amount per buy order |
| `COOLDOWN` | 600 | Seconds between buy orders for same coin |
| `MAX_WORKERS` | 4 | Number of concurrent threads for processing |
| `AUTO_DRY_RUN` | false | Enable dry-run mode (no real orders) |
| `DEBUG` | false | Enable debug logging |

## 🔒 Security

- **Never commit credentials** - Always use `.env` file (gitignored)
- **DRY_RUN mode** - Test strategies before risking real money
- **Atomic saves** - Portfolio updates use temporary files to prevent corruption
- **Thread-safe** - Concurrent operations use proper locking

## 🧪 Testing

### Run All Tests

```bash
pytest -v
```

### Run Specific Test File

```bash
pytest tests/test_trader_core.py -v
```

### Run with Coverage

```bash
pytest --cov=trader --cov-report=html
```

### Quick Import Test

```bash
python auto_trader.py --test
```

## 🔧 Development

### Adding a New Exchange

1. Create a new adapter class in `trader/exchanges.py` inheriting from `ExchangeAdapter`
2. Implement required methods: `get_quote`, `get_holdings`, `place_order`, `get_buying_power`
3. Add normalization for symbol format
4. Register in `UnifiedExchangeRouter`

### Modifying Trading Strategy

Edit the `process_coin` method in `trader/core.py` to adjust:
- Profit/loss calculations
- Buy/sell triggers
- Risk management logic

## 📊 CI/CD

GitHub Actions automatically runs tests on:
- Push to `main` or `refactor/*` branches
- Pull requests to `main`

The CI pipeline:
1. Tests on Python 3.9, 3.10, and 3.11
2. Runs pytest suite
3. Validates module imports
4. Lints code with flake8

## 🤝 Contributing

This is a refactored version of the original rhapi project. Key improvements in v2.0:

- Modular package structure
- Concurrent processing support
- DRY_RUN safety mode
- Decimal-based calculations
- Comprehensive test coverage
- CI/CD integration
- Thread-safe operations
- Improved error handling
- Python logging integration

## 📄 License

Preserves original license and authorship. See repository for details.

## ⚠️ Disclaimer

**This software is for educational purposes only. Cryptocurrency trading carries significant financial risk. Use at your own risk. The authors and contributors are not responsible for any financial losses.**

Always start with DRY_RUN mode enabled and small trading amounts until you fully understand the system behavior.

## 🐛 Troubleshooting

### API Connection Errors

Run system diagnostics:
```bash
python auto_trader.py
# Select option 9 for diagnostics
```

### Module Import Errors

Ensure all dependencies are installed:
```bash
pip install -r requirements.txt
```

### Portfolio File Corruption

The system uses atomic saves with `.tmp` files. If corruption occurs, check for leftover `.tmp` files and restore from backup.

## 📞 Support

For issues, please check:
1. System diagnostics in the CLI
2. DEBUG=true for detailed logs
3. Existing GitHub issues
4. Test suite for expected behavior
