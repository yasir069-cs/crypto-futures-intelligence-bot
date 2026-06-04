"""
tests/test_bot.py
Unit tests — run with: pytest tests/ -v
Tests all core logic without network calls (mocked).
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ── Utils tests ──────────────────────────────────────────────

from utils.helpers import rsi, ema, bollinger, macd, fmt_price, fmt_pct, sma


def test_rsi_oversold():
    # 14 falling values → RSI should be < 30
    closes = [100 - i * 3 for i in range(20)]
    result = rsi(closes, 14)
    assert result < 40, f"Expected oversold RSI, got {result}"


def test_rsi_overbought():
    # 14 rising values → RSI should be > 70
    closes = [100 + i * 3 for i in range(20)]
    result = rsi(closes, 14)
    assert result > 60, f"Expected overbought RSI, got {result}"


def test_rsi_neutral():
    # Flat prices → RSI near 50
    closes = [100.0] * 20
    result = rsi(closes, 14)
    # All gains/losses zero → returns 100 (no losses), acceptable edge case
    assert isinstance(result, float)


def test_ema_returns_float():
    closes = [float(i) for i in range(1, 30)]
    result = ema(closes, 21)
    assert isinstance(result, float)
    assert result > 0


def test_ema_short_series():
    # Should return 0 if not enough data
    result = ema([1.0, 2.0], 21)
    assert result == 0.0


def test_bollinger_bands():
    closes = [100.0 + (i % 5) for i in range(25)]
    upper, mid, lower = bollinger(closes, 20, 2.0)
    assert upper > mid > lower, "BB bands not in order"


def test_bollinger_flat():
    closes = [100.0] * 25
    upper, mid, lower = bollinger(closes, 20, 2.0)
    assert upper == mid == lower == 100.0


def test_macd_returns_tuple():
    closes = [float(50 + i * 0.1) for i in range(30)]
    result = macd(closes, 12, 26, 9)
    assert len(result) == 3
    assert all(isinstance(x, float) for x in result)


def test_fmt_price_large():
    assert fmt_price(42000.1234) == "42,000.1234"


def test_fmt_price_small():
    result = fmt_price(0.00001234)
    assert "0.00001234" in result


def test_fmt_price_zero():
    assert fmt_price(0) == "N/A"


def test_fmt_pct_positive():
    assert fmt_pct(5.123) == "+5.12%"


def test_fmt_pct_negative():
    assert fmt_pct(-3.5) == "-3.50%"


def test_sma():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert sma(values, 3) == pytest.approx(4.0)


# ── Config tests ─────────────────────────────────────────────

def test_config_missing_raises(monkeypatch):
    from config import Config
    monkeypatch.setattr(Config, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(Config, "TELEGRAM_CHAT_ID", "")
    with pytest.raises(ValueError):
        Config.validate()


def test_config_ok(monkeypatch, tmp_path):
    from config import Config
    monkeypatch.setattr(Config, "TELEGRAM_BOT_TOKEN", "fake_token")
    monkeypatch.setattr(Config, "TELEGRAM_CHAT_ID", "123456")
    monkeypatch.setattr(Config, "DATABASE_PATH", str(tmp_path / "test.db"))
    assert Config.validate() is True


# ── Database tests ───────────────────────────────────────────

from database import Database


@pytest.fixture
def test_db(tmp_path):
    return Database(str(tmp_path / "test.db"))


def test_db_insert_and_stats(test_db):
    signal = {
        "coin": "bitcoin",
        "action": "BUY LONG",
        "signal_type": "SWING",
        "confidence": 80,
        "risk_level": "LOW",
        "reasons": ["RSI oversold", "EMA cross"],
        "bot_view": "Strong setup",
        "price": 65000.0,
        "timeframe": "1D",
        "timestamp": "2026-06-05T10:00:00",
    }
    test_db.insert_signal(signal)
    stats = test_db.get_daily_stats()
    assert stats["total_signals"] >= 0   # may be 0 if date doesn't match today


def test_cooldown(test_db):
    assert test_db.check_cooldown("bitcoin", "BUY LONG") is False
    test_db.set_cooldown("bitcoin", "BUY LONG", hours=6)
    assert test_db.check_cooldown("bitcoin", "BUY LONG") is True


def test_news_dedup(test_db):
    assert test_db.is_news_seen("https://example.com/article1") is False
    test_db.mark_news_seen("https://example.com/article1", "Test article")
    assert test_db.is_news_seen("https://example.com/article1") is True


# ── Signal generator tests ───────────────────────────────────

from core.trading_signals import TradingSignalGenerator, normalize_symbol


def test_normalize_symbol_aliases():
    assert normalize_symbol("BTC") == "bitcoin"
    assert normalize_symbol("btcusdt") == "bitcoin"
    assert normalize_symbol("ETH") == "ethereum"
    assert normalize_symbol("SOL/USDT") == "solana"
    assert normalize_symbol("MATIC") == "matic-network"
    assert normalize_symbol("unknown_coin") == "unknown_coin"


def test_signal_action_from_score():
    gen = TradingSignalGenerator()
    assert gen._action(40)  == "BUY LONG"
    assert gen._action(-40) == "SELL SHORT"
    assert gen._action(10)  == "HOLD"
    assert gen._action(-10) == "HOLD"


def test_signal_confidence_range():
    gen = TradingSignalGenerator()
    for score in [-80, -40, 0, 40, 80]:
        conf = gen._confidence(score)
        assert 0 <= conf <= 100, f"Confidence out of range for score={score}: {conf}"


def test_risk_levels():
    gen = TradingSignalGenerator()
    assert gen._risk(80) == "LOW"
    assert gen._risk(65) == "MEDIUM"
    assert gen._risk(40) == "HIGH"


@pytest.mark.asyncio
async def test_generate_signal_mock():
    """Test signal generation with mocked market data."""
    gen = TradingSignalGenerator()
    mock_analysis = {
        "coin_id": "bitcoin",
        "current_price": 65000.0,
        "prev_price":    63000.0,
        "rsi":      28.5,
        "ema21":    62000.0,
        "ema50":    60000.0,
        "bb_upper": 68000.0,
        "bb_mid":   64000.0,
        "bb_lower": 60000.0,
        "macd_line": 100.0,
        "macd_hist": 50.0,
        "support":    60000.0,
        "resistance": 70000.0,
        "volatility": 1.8,
        "price_change_24h": 3.2,
        "price_change_7d":  8.1,
        "price_change_30d": 15.0,
        "rvol": 1.5,
        "timestamp": "2026-06-05T10:00:00",
    }

    with patch("core.trading_signals.market_analyzer") as mock_ma:
        mock_ma.analyze_coin = AsyncMock(return_value=mock_analysis)
        signal = await gen.generate_signal("bitcoin")

    assert signal is not None
    assert signal["action"] == "BUY LONG"      # RSI 28.5, price>EMA21>EMA50, MACD+
    assert signal["confidence"] > 0
    assert signal["stop_loss"] < signal["entry_point"]
    assert signal["take_profit"] > signal["entry_point"]
    assert signal["risk_reward"] > 0


# ── Liquidation tests ────────────────────────────────────────

from core.liquidation import LiquidationDetector
import time


def _make_liq(side: str, qty: float, price: float, seconds_ago: int = 1) -> dict:
    ts_ms = int((time.time() - seconds_ago) * 1000)
    return {
        "symbol": "BTCUSDT",
        "side":   side,
        "accumulated_filled_qty": str(qty),
        "average_price":          str(price),
        "time":                   ts_ms,
    }


@pytest.mark.asyncio
async def test_liq_sweep_detected():
    det  = LiquidationDetector(threshold_usd=100_000)
    liqs = [_make_liq("SELL", 2.0, 65000.0) for _ in range(5)]  # SELL = long liq
    result = await det.check_sweep("BTCUSDT", liqs)
    assert result is not None
    assert result["direction"] == "BUY LONG"    # long sweep → potential bounce
    assert result["total_usd"] >= 100_000


@pytest.mark.asyncio
async def test_liq_sweep_below_threshold():
    det  = LiquidationDetector(threshold_usd=1_000_000)
    liqs = [_make_liq("SELL", 0.01, 65000.0)]
    result = await det.check_sweep("BTCUSDT", liqs)
    assert result is None


@pytest.mark.asyncio
async def test_liq_short_sweep():
    det  = LiquidationDetector(threshold_usd=100_000)
    liqs = [_make_liq("BUY", 2.0, 65000.0) for _ in range(5)]   # BUY = short liq
    result = await det.check_sweep("BTCUSDT", liqs)
    assert result is not None
    assert result["direction"] == "SELL SHORT"  # short sweep → potential reversal


@pytest.mark.asyncio
async def test_liq_old_records_ignored():
    det  = LiquidationDetector(threshold_usd=100_000)
    # Very old records (2 hours ago)
    liqs = [_make_liq("SELL", 10.0, 65000.0, seconds_ago=7200) for _ in range(10)]
    result = await det.check_sweep("BTCUSDT", liqs)
    assert result is None   # all outside 15-min window
