"""
core/market_analyzer.py
CoinGecko-based deep analysis: RSI, EMA, Bollinger Bands, MACD.
Returns a clean dict ready for signal generation.
"""

import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np

from config import Config
from utils.helpers import rsi, ema, bollinger, macd, sma
from utils.logger import get_logger

logger = get_logger(__name__)

# CoinGecko free API — 30 req/min limit; we cache aggressively
_CACHE: Dict[str, Dict] = {}
_CACHE_TS: Dict[str, datetime] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes


class MarketAnalyzer:
    def __init__(self):
        self.base = Config.COINGECKO_BASE

    # ── Public ───────────────────────────────────────────────

    async def analyze_coin(self, coin_id: str) -> Dict:
        """
        Full technical analysis for a CoinGecko coin_id.
        Returns empty dict on failure — callers must guard.
        """
        # Cache check
        if self._is_cached(coin_id):
            return _CACHE[coin_id]

        data = await self._fetch_market_chart(coin_id, days=90)
        if not data:
            return {}

        try:
            prices = [p[1] for p in data.get("prices", [])]
            volumes = [v[1] for v in data.get("total_volumes", [])]

            if len(prices) < 30:
                return {}

            closes = prices  # daily close prices

            current_price = closes[-1]
            prev_price    = closes[-2] if len(closes) >= 2 else closes[-1]

            # ── Indicators ──────────────────────────────────
            rsi_val   = rsi(closes, 14)
            ema21_val = ema(closes, 21)
            ema50_val = ema(closes, 50)
            bb_upper, bb_mid, bb_lower = bollinger(closes, 20, 2.0)
            macd_line, sig_line, hist  = macd(closes, 12, 26, 9)

            # ── Price changes ────────────────────────────────
            pc_24h  = _pct(closes[-1], closes[-2])  if len(closes) >= 2  else 0
            pc_7d   = _pct(closes[-1], closes[-7])  if len(closes) >= 7  else 0
            pc_30d  = _pct(closes[-1], closes[-30]) if len(closes) >= 30 else 0

            # ── Support / Resistance (last 30 candles) ───────
            window = closes[-30:]
            support    = float(np.min(window))
            resistance = float(np.max(window))

            # ── Volatility (std of daily returns %) ──────────
            rets = [(closes[i] - closes[i-1]) / closes[i-1] * 100
                    for i in range(1, len(closes))]
            volatility = float(np.std(rets[-30:])) if len(rets) >= 30 else 0.0

            # ── Volume ───────────────────────────────────────
            avg_vol = sma(volumes, 20) if len(volumes) >= 20 else (volumes[-1] if volumes else 0)
            cur_vol = volumes[-1] if volumes else 0
            rvol    = round(cur_vol / avg_vol, 2) if avg_vol else 0

            result = {
                "coin_id":        coin_id,
                "current_price":  current_price,
                "prev_price":     prev_price,
                "rsi":            round(rsi_val, 2),
                "ema21":          round(ema21_val, 6),
                "ema50":          round(ema50_val, 6),
                "bb_upper":       round(bb_upper, 6),
                "bb_mid":         round(bb_mid, 6),
                "bb_lower":       round(bb_lower, 6),
                "macd_line":      round(macd_line, 6),
                "macd_hist":      round(hist, 6),
                "support":        round(support, 6),
                "resistance":     round(resistance, 6),
                "volatility":     round(volatility, 2),
                "price_change_24h": round(pc_24h, 2),
                "price_change_7d":  round(pc_7d, 2),
                "price_change_30d": round(pc_30d, 2),
                "rvol":           rvol,
                "timestamp":      datetime.utcnow().isoformat(),
            }

            _CACHE[coin_id]    = result
            _CACHE_TS[coin_id] = datetime.utcnow()
            return result

        except Exception as e:
            logger.error(f"analyze_coin({coin_id}): {e}", exc_info=True)
            return {}

    async def get_top_coin_ids(self, limit: int = 100) -> List[str]:
        """Top N coin IDs by market cap from CoinGecko."""
        per_page = min(limit, 250)
        url    = f"{self.base}/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": per_page,
            "page": 1,
            "sparkline": "false",
        }
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, params=params,
                                  timeout=aiohttp.ClientTimeout(total=20)) as r:
                    if r.status == 200:
                        data = await r.json()
                        return [c["id"] for c in data if c.get("id")]
        except Exception as e:
            logger.error(f"get_top_coin_ids: {e}")
        # Fallback
        return [
            "bitcoin","ethereum","tether","binancecoin","solana",
            "ripple","usd-coin","dogecoin","cardano","tron",
            "avalanche-2","chainlink","polkadot","matic-network",
            "litecoin","uniswap","stellar","monero","cosmos","algorand",
        ]

    # ── Private ──────────────────────────────────────────────

    def _is_cached(self, coin_id: str) -> bool:
        if coin_id not in _CACHE or coin_id not in _CACHE_TS:
            return False
        age = (datetime.utcnow() - _CACHE_TS[coin_id]).total_seconds()
        return age < _CACHE_TTL_SECONDS

    async def _fetch_market_chart(self, coin_id: str, days: int) -> Optional[Dict]:
        url    = f"{self.base}/coins/{coin_id}/market_chart"
        params = {"vs_currency": "usd", "days": days}
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, params=params,
                                  timeout=aiohttp.ClientTimeout(total=20)) as r:
                    if r.status == 200:
                        return await r.json()
                    if r.status == 429:
                        logger.warning(f"CoinGecko rate limit hit for {coin_id}")
                        await asyncio.sleep(10)
                    else:
                        logger.warning(f"CoinGecko {coin_id} → HTTP {r.status}")
        except Exception as e:
            logger.error(f"_fetch_market_chart({coin_id}): {e}")
        return None


def _pct(new: float, old: float) -> float:
    if old == 0:
        return 0.0
    return (new - old) / old * 100


market_analyzer = MarketAnalyzer()
