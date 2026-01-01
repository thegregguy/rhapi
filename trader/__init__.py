"""
Trader package for modular cryptocurrency trading.

This package provides a clean, testable interface for automated trading
across multiple exchanges (Robinhood and Coinbase).
"""

__version__ = "2.0.0"

from trader.core import Trader
from trader.config import Config

__all__ = ["Trader", "Config"]
