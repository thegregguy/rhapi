"""
Configuration management for the trader.
Loads settings from environment variables with sensible defaults.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Environment-driven configuration with defaults"""
    
    def __init__(self):
        # Trading parameters
        self.AUTO_BUY_USD = float(os.getenv("AUTO_BUY_USD", "1.00"))
        self.AUTO_COOLDOWN = int(os.getenv("AUTO_COOLDOWN", "600"))  # seconds
        self.SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", "15"))  # seconds
        
        # Concurrency
        self.MAX_WORKERS = int(os.getenv("MAX_WORKERS", "4"))
        
        # Dry-run mode
        self.AUTO_DRY_RUN = os.getenv("AUTO_DRY_RUN", "false").lower() in ["true", "1", "yes", "on"]
        
        # Logging
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
        
    def __repr__(self):
        return (
            f"Config(AUTO_BUY_USD={self.AUTO_BUY_USD}, "
            f"AUTO_COOLDOWN={self.AUTO_COOLDOWN}s, "
            f"SCAN_INTERVAL={self.SCAN_INTERVAL}s, "
            f"MAX_WORKERS={self.MAX_WORKERS}, "
            f"AUTO_DRY_RUN={self.AUTO_DRY_RUN}, "
            f"LOG_LEVEL={self.LOG_LEVEL})"
        )
