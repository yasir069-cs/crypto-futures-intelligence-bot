"""
config.py — Central configuration for Crypto Futures Intelligence Bot
All values come from .env; defaults are safe for production.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ── Telegram ──────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str   = os.getenv("TELEGRAM_CHAT_ID", "")

    # ── Logging ───────────────────────────────────────────────
    LOG_LEVEL: str    = os.getenv("LOG_LEVEL", "INFO")
    ENABLE_DEBUG: bool = os.getenv("ENABLE_DEBUG", "False").lower() == "true"

    # ── Database ──────────────────────────────────────────────
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/signals.db")

    # ── Scanner ───────────────────────────────────────────────
    SCAN_INTERVAL_MINUTES: int  = int(os.getenv("SCAN_INTERVAL_MINUTES", 30))
    TOP_COINS_SCAN_LIMIT: int   = int(os.getenv("TOP_COINS_SCAN_LIMIT", 100))
    ALERT_COOLDOWN_HOURS: int   = int(os.getenv("ALERT_COOLDOWN_HOURS", 6))
    CONFIDENCE_THRESHOLD: int   = int(os.getenv("CONFIDENCE_THRESHOLD", 65))

    # ── Data Sources ──────────────────────────────────────────
    # CoinGecko — free public API, no key needed, works in India
    COINGECKO_BASE: str = "https://api.coingecko.com/api/v3"

    # Binance public REST — read-only market data, no auth, works in India
    BINANCE_BASE: str   = "https://api.binance.com"

    # ── Risk weights (used in confidence scoring) ─────────────
    CONFIDENCE_WEIGHTS: dict = {
        "rsi":              0.20,
        "ema_cross":        0.20,
        "bollinger":        0.15,
        "macd":             0.15,
        "volume":           0.10,
        "liquidation":      0.10,
        "price_action":     0.10,
    }

    RISK_LEVELS: dict = {
        "LOW":    {"min": 75, "max": 100},
        "MEDIUM": {"min": 60, "max": 74},
        "HIGH":   {"min": 0,  "max": 59},
    }

    @classmethod
    def validate(cls) -> bool:
        missing = [k for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
                   if not getattr(cls, k)]
        if missing:
            raise ValueError(f"Missing .env keys: {', '.join(missing)}")
        Path(cls.DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
        return True
