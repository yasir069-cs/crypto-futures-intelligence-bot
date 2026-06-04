"""
core/binance_client.py
Read-only Binance public REST client.
No API key required — market data only.
Works from India (no trading, no account).
"""

import asyncio
import aiohttp
from typing import Dict, List, Optional
from utils.logger import get_logger

logger = get_logger(__name__)

BINANCE = "https://api.binance.com"
FAPI   = "https://fapi.binance.com"   # Futures endpoints


class BinanceClient:
    """Async context-manager Binance public API client."""

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._timeout = aiohttp.ClientTimeout(total=15)

    async def __aenter__(self):
        self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self

    async def __aexit__(self, *_):
        if self._session:
            await self._session.close()

    async def _get(self, base: str, path: str, params: dict = None) -> Optional[dict | list]:
        try:
            async with self._session.get(f"{base}{path}", params=params) as r:
                if r.status == 200:
                    return await r.json()
                logger.warning(f"Binance {path} → HTTP {r.status}")
        except Exception as e:
            logger.error(f"Binance request error {path}: {e}")
        return None

    # ── Spot market data ────────────────────────────────────

    async def get_top_symbols(self, limit: int = 100) -> List[str]:
        """Top USDT perpetual futures symbols by 24h volume."""
        data = await self._get(FAPI, "/fapi/v1/ticker/24hr")
        if not data:
            # Fallback hardcoded list
            return [
                "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT",
                "DOGEUSDT","ADAUSDT","AVAXUSDT","TRXUSDT","DOTUSDT",
                "LINKUSDT","MATICUSDT","LTCUSDT","UNIUSDT","ATOMUSDT",
            ]
        # Sort by quoteVolume descending
        usdt = [d for d in data if d.get("symbol", "").endswith("USDT")]
        usdt.sort(key=lambda x: float(x.get("quoteVolume", 0)), reverse=True)
        return [d["symbol"] for d in usdt[:limit]]

    async def get_klines(self, symbol: str, interval: str, limit: int = 100) -> List[List]:
        """
        Futures klines. Returns list of:
        [open_time, open, high, low, close, volume, ...]
        """
        data = await self._get(
            FAPI, "/fapi/v1/klines",
            {"symbol": symbol, "interval": interval, "limit": limit}
        )
        return data or []

    async def get_ticker(self, symbol: str) -> Optional[Dict]:
        """Latest price ticker for a futures symbol."""
        data = await self._get(FAPI, "/fapi/v1/ticker/price", {"symbol": symbol})
        return data  # {"symbol":..., "price":..., "time":...}

    async def get_24h(self, symbol: str) -> Optional[Dict]:
        """24h stats for a futures symbol."""
        data = await self._get(FAPI, "/fapi/v1/ticker/24hr", {"symbol": symbol})
        return data

    # ── Open Interest ────────────────────────────────────────

    async def get_open_interest(self, symbol: str) -> Optional[Dict]:
        """Current open interest for a futures symbol."""
        data = await self._get(FAPI, "/fapi/v1/openInterest", {"symbol": symbol})
        return data  # {"openInterest":..., "symbol":...}

    async def get_oi_history(self, symbol: str, period: str = "30m", limit: int = 10) -> List[Dict]:
        """Open interest history — used for liquidation sweep detection."""
        data = await self._get(
            FAPI, "/futures/data/openInterestHist",
            {"symbol": symbol, "period": period, "limit": limit}
        )
        return data or []

    # ── Liquidation data ─────────────────────────────────────

    async def get_liquidations(self, symbol: str, limit: int = 20) -> List[Dict]:
        """Recent liquidation orders for futures symbol."""
        data = await self._get(
            FAPI, "/fapi/v1/allForceOrders",
            {"symbol": symbol, "limit": limit}
        )
        return data or []

    async def get_global_liquidations(self, limit: int = 50) -> List[Dict]:
        """Recent liquidations across all symbols (no symbol filter)."""
        data = await self._get(
            FAPI, "/fapi/v1/allForceOrders",
            {"limit": limit}
        )
        return data or []

    # ── Funding Rate ─────────────────────────────────────────

    async def get_funding_rate(self, symbol: str) -> Optional[float]:
        """Current funding rate for a symbol."""
        data = await self._get(
            FAPI, "/fapi/v1/premiumIndex", {"symbol": symbol}
        )
        if data and isinstance(data, dict):
            try:
                return float(data.get("lastFundingRate", 0))
            except Exception:
                pass
        return None
