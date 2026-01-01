"""
Trader Package - Modular Crypto Trading Bot

This package provides a modular, testable crypto trading system
with support for multiple exchanges (Robinhood, Coinbase).
"""

from .core import Trader
from .config import Config

__version__ = "2.0.0"
__all__ = ["Trader", "Config"]
