"""
Configuration module for trader application.

Loads configuration from environment variables with sensible defaults.
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)


class Config:
    """Configuration class for trader application."""
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        
        # Trading Parameters
        self.DEFAULT_BUY_USD: float = float(os.getenv("DEFAULT_BUY_USD", "1.00"))
        self.COOLDOWN: int = int(os.getenv("COOLDOWN_SECONDS", "600"))
        self.SCAN_INTERVAL: int = int(os.getenv("SCAN_INTERVAL", "15"))
        
        # Performance Settings
        self.MAX_WORKERS: int = int(os.getenv("MAX_WORKERS", "4"))
        self.USE_CONCURRENCY: bool = os.getenv("USE_CONCURRENCY", "true").lower() in ["true", "1", "yes"]
        
        # Dry Run Mode
        self.DRY_RUN: bool = os.getenv("AUTO_DRY_RUN", "false").lower() in ["true", "1", "yes"]
        
        # Debug Mode
        self.DEBUG: bool = os.getenv("DEBUG", "false").lower() in ["true", "1", "yes"]
        
        # API Keys (for validation)
        self.RH_API_KEY: Optional[str] = os.getenv("API_KEY")
        self.RH_PRIVATE_KEY: Optional[str] = os.getenv("BASE64_PRIVATE_KEY")
        self.CB_API_KEY: Optional[str] = os.getenv("CB_API_KEY")
        self.CB_PRIVATE_KEY: Optional[str] = os.getenv("CB_PRIVATE_KEY")
        
        # Portfolio File
        self.PORTFOLIO_FILE: str = os.getenv("PORTFOLIO_FILE", "portfolio.json")
    
    def validate_api_keys(self) -> tuple[bool, list[str]]:
        """
        Validate that required API keys are present.
        
        Returns:
            tuple: (all_valid: bool, missing_keys: list[str])
        """
        missing = []
        
        if not self.RH_API_KEY:
            missing.append("API_KEY (Robinhood)")
        if not self.RH_PRIVATE_KEY:
            missing.append("BASE64_PRIVATE_KEY (Robinhood)")
        if not self.CB_API_KEY:
            missing.append("CB_API_KEY (Coinbase)")
        if not self.CB_PRIVATE_KEY:
            missing.append("CB_PRIVATE_KEY (Coinbase)")
        
        return len(missing) == 0, missing
    
    def __repr__(self) -> str:
        """String representation of config (hides sensitive data)."""
        return (
            f"Config(DRY_RUN={self.DRY_RUN}, "
            f"DEFAULT_BUY_USD={self.DEFAULT_BUY_USD}, "
            f"SCAN_INTERVAL={self.SCAN_INTERVAL}, "
            f"MAX_WORKERS={self.MAX_WORKERS})"
        )
