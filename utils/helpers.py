"""utils/helpers.py — Shared formatting and math helpers."""

from datetime import datetime, timedelta
from typing import List


def fmt_price(price: float) -> str:
    if price == 0:
        return "N/A"
    if price >= 1:
        return f"{price:,.4f}"
    return f"{price:.8f}".rstrip("0").rstrip(".")


def fmt_pct(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def fmt_volume(volume: float) -> str:
    if volume >= 1_000_000_000:
        return f"{volume/1e9:.2f}B"
    if volume >= 1_000_000:
        return f"{volume/1e6:.2f}M"
    if volume >= 1_000:
        return f"{volume/1e3:.2f}K"
    return f"{volume:.2f}"


def relative_time(dt: datetime) -> str:
    diff = datetime.utcnow() - dt
    if diff < timedelta(minutes=1):
        return "just now"
    if diff < timedelta(hours=1):
        return f"{int(diff.total_seconds()//60)}m ago"
    if diff < timedelta(days=1):
        return f"{int(diff.total_seconds()//3600)}h ago"
    return f"{diff.days}d ago"


# ── Technical helpers ────────────────────────────────────────

def sma(values: List[float], period: int) -> float:
    """Simple moving average of last `period` values."""
    if len(values) < period:
        return 0.0
    return sum(values[-period:]) / period


def ema(values: List[float], period: int) -> float:
    """EMA of the series; returns last value."""
    if len(values) < period:
        return 0.0
    k = 2.0 / (period + 1)
    result = sum(values[:period]) / period
    for v in values[period:]:
        result = v * k + result * (1 - k)
    return result


def rsi(closes: List[float], period: int = 14) -> float:
    """Wilder RSI."""
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def bollinger(closes: List[float], period: int = 20, std_dev: float = 2.0):
    """Returns (upper, middle, lower) bands."""
    if len(closes) < period:
        p = closes[-1] if closes else 0
        return p, p, p
    window = closes[-period:]
    mid = sum(window) / period
    variance = sum((x - mid) ** 2 for x in window) / period
    std = variance ** 0.5
    return mid + std_dev * std, mid, mid - std_dev * std


def macd(closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9):
    """Returns (macd_line, signal_line, histogram)."""
    if len(closes) < slow:
        return 0.0, 0.0, 0.0
    fast_ema = ema(closes, fast)
    slow_ema = ema(closes, slow)
    macd_line = fast_ema - slow_ema
    # For signal we'd need a series — approximate with single value
    return macd_line, 0.0, macd_line
