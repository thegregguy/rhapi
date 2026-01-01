"""
Configuration management for the trading bot.

Loads configuration from environment variables with sensible defaults.
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """
    Configuration manager for trading bot.
    
    All settings can be overridden via environment variables.
    """
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        # Trading parameters
        self.default_buy_usd: float = float(os.getenv('DEFAULT_BUY_USD', '1.0'))
        self.cooldown: int = int(os.getenv('COOLDOWN', '600'))
        self.scan_interval: int = int(os.getenv('SCAN_INTERVAL', '15'))
        
        # Concurrency
        self.max_workers: int = int(os.getenv('MAX_WORKERS', '4'))
        
        # Dry run mode
        self.dry_run: bool = os.getenv('AUTO_DRY_RUN', 'false').lower() in ['true', '1', 'yes', 'on']
        
        # Logging
        self.debug: bool = os.getenv('DEBUG', 'false').lower() in ['true', '1', 'yes', 'on']
        self.log_level: str = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    def __repr__(self) -> str:
        """String representation of configuration."""
        return (
            f"Config(default_buy_usd={self.default_buy_usd}, "
            f"cooldown={self.cooldown}, "
            f"scan_interval={self.scan_interval}, "
            f"max_workers={self.max_workers}, "
            f"dry_run={self.dry_run}, "
            f"log_level={self.log_level})"
        )
