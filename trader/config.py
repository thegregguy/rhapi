"""
Configuration management for the trader.

Loads settings from environment variables with sensible defaults.
"""

import os
from typing import Optional
from decimal import Decimal
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Configuration settings for the trader."""
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        # Trading parameters
        self.default_buy_usd: Decimal = Decimal(
            os.getenv("DEFAULT_BUY_USD", "1.00")
        )
        self.cooldown: int = int(os.getenv("COOLDOWN", "600"))
        self.scan_interval: int = int(os.getenv("SCAN_INTERVAL", "15"))
        
        # Concurrency
        self.max_workers: int = int(os.getenv("MAX_WORKERS", "4"))
        
        # Dry run mode
        self.auto_dry_run: bool = os.getenv("AUTO_DRY_RUN", "false").lower() in [
            "true", "1", "yes", "on"
        ]
        
        # Logging
        self.debug: bool = os.getenv("DEBUG", "false").lower() in [
            "true", "1", "yes", "on"
        ]
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
        
    def __repr__(self) -> str:
        """String representation of config."""
        return (
            f"Config(default_buy_usd={self.default_buy_usd}, "
            f"cooldown={self.cooldown}, scan_interval={self.scan_interval}, "
            f"max_workers={self.max_workers}, auto_dry_run={self.auto_dry_run})"
        )
