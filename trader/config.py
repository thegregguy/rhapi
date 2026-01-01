"""
Configuration module for trader
Loads environment variables with sensible defaults
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Configuration class with environment variable parsing and defaults"""
    
    # Robinhood API
    API_KEY = os.getenv("API_KEY", "")
    BASE64_PRIVATE_KEY = os.getenv("BASE64_PRIVATE_KEY", "")
    
    # Coinbase API
    CB_API_KEY = os.getenv("CB_API_KEY", "")
    CB_PRIVATE_KEY = os.getenv("CB_PRIVATE_KEY", "")
    
    # Trading Configuration
    DEFAULT_BUY_USD = float(os.getenv("DEFAULT_BUY_USD", "1.00"))
    COOLDOWN = int(os.getenv("COOLDOWN", "600"))
    MAX_WORKERS = int(os.getenv("MAX_WORKERS", "4"))
    
    # Safety Features
    AUTO_DRY_RUN = os.getenv("AUTO_DRY_RUN", "false").lower() in ["true", "1", "yes", "on"]
    
    # Debug Mode
    DEBUG = os.getenv("DEBUG", "false").lower() in ["true", "1", "yes", "on"]
    
    # Portfolio File
    PORTFOLIO_FILE = os.getenv("PORTFOLIO_FILE", "portfolio.json")
    
    @classmethod
    def validate(cls):
        """Validate that required configuration is present"""
        errors = []
        
        if not cls.API_KEY:
            errors.append("API_KEY is required")
        if not cls.BASE64_PRIVATE_KEY:
            errors.append("BASE64_PRIVATE_KEY is required")
        if not cls.CB_API_KEY:
            errors.append("CB_API_KEY is required")
        if not cls.CB_PRIVATE_KEY:
            errors.append("CB_PRIVATE_KEY is required")
            
        return errors
    
    @classmethod
    def is_valid(cls):
        """Check if configuration is valid"""
        return len(cls.validate()) == 0
