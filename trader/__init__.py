"""
Trader package for modular cryptocurrency trading.

This package provides a structured approach to automated trading
across multiple exchanges with support for configuration, dry-run mode,
and concurrent execution.
"""

from trader.core import Trader
from trader.config import Config

__all__ = ['Trader', 'Config']
