import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

class Config:
    """Base configuration"""
    
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
    
    # Bot Configuration
    ENABLE_DEBUG = os.getenv('ENABLE_DEBUG', 'False').lower() == 'true'
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # Database
    DATABASE_PATH = os.getenv("DATABASE_PATH", "data/signals.db")

    # Scanner Configuration
    SCAN_INTERVAL_MINUTES = int(os.getenv("SCAN_INTERVAL_MINUTES", 15))
    SCAN_INTERVAL_HOURS = int(os.getenv("SCAN_INTERVAL_HOURS", 1))
    MAX_PAIRS_SCAN = int(os.getenv("MAX_PAIRS_SCAN", 100))
    TOP_COINS_SCAN_LIMIT = int(os.getenv("TOP_COINS_SCAN_LIMIT", 100))
    ALERT_COOLDOWN_HOURS = int(os.getenv("ALERT_COOLDOWN_HOURS", 6))

    # OKX API Configuration
    OKX_BASE_URL = os.getenv("OKX_BASE_URL", "https://www.okx.com")
    OKX_API_KEY = os.getenv("OKX_API_KEY", "")
    OKX_API_SECRET = os.getenv("OKX_API_SECRET", "")
    OKX_PASSPHRASE = os.getenv("OKX_PASSPHRASE", "")

    # Analysis Configuration
    CONFIDENCE_WEIGHTS = {
        "price_expansion": 0.2,
        "relative_volume": 0.15,
        "open_interest": 0.15,
        "trend": 0.2,
        "market_structure": 0.1,
        "breakout_strength": 0.1,
        "multi_timeframe": 0.1
    }
    CONFIDENCE_THRESHOLD = int(os.getenv("CONFIDENCE_THRESHOLD", 70))
    RISK_LEVELS = {
        "LOW": {"min_confidence": 80, "max_confidence": 100},
        "MEDIUM": {"min_confidence": 60, "max_confidence": 79},
        "HIGH": {"min_confidence": 0, "max_confidence": 59}
    }
    
    @classmethod
    def validate(cls):
        """Validate configuration"""
        required = [
            "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"
        ]
        missing = [key for key in required if not getattr(cls, key)]
        if missing:
            raise ValueError(f"Missing configuration: {', '.join(missing)}")
        
        # Create data directory if it doesn't exist
        Path(cls.DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
        
        return True

class DevelopmentConfig(Config):
    """Development configuration"""
    ENABLE_DEBUG = True
    LOG_LEVEL = 'DEBUG'

class ProductionConfig(Config):
    """Production configuration"""
    ENABLE_DEBUG = False
    LOG_LEVEL = 'INFO'

def get_config():
    """Get config based on environment"""
    env = os.getenv('ENVIRONMENT', 'production').lower()
    if env == 'development':
        return DevelopmentConfig()
    return ProductionConfig()
