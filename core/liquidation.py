"""
core/liquidation.py
Liquidation Sweep Detection — Priority #1 feature.

Logic:
- Fetch recent forced liquidations from Binance futures public API.
- If total liquidation volume in last N minutes crosses a threshold
  → emit a LiquidationSweep event.
- Long liquidation sweep  → price dropped hard → potential bounce (BUY signal)
- Short liquidation sweep → price pumped hard → potential reversal (SELL signal)

This is INFORMATION ONLY. User makes final trade decision.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from utils.logger import get_logger

logger = get_logger(__name__)

# Minimum USD notional liquidated in the window to call it a "sweep"
_SWEEP_THRESHOLD_USD = 500_000     # $500K default
_WINDOW_MINUTES      = 15          # Rolling 15-minute window


class LiquidationDetector:
    def __init__(self, threshold_usd: float = _SWEEP_THRESHOLD_USD):
        self.threshold = threshold_usd
        self._liq_buffer: List[Dict] = []   # Raw liquidation events

    # ── Main API ────────────────────────────────────────────

    async def check_sweep(
        self, symbol: str, raw_liquidations: List[Dict]
    ) -> Optional[Dict]:
        """
        Given recent liquidation records for a symbol,
        return a sweep event dict if threshold is crossed, else None.

        raw_liquidations: list of Binance allForceOrders records:
            {"symbol", "side", "order_type", "time_in_force",
             "original_quantity", "price", "average_price",
             "order_status", "last_filled_qty", "accumulated_filled_qty",
             "trade_time"}
        """
        if not raw_liquidations:
            return None

        now_ms = datetime.utcnow().timestamp() * 1000
        cutoff = now_ms - _WINDOW_MINUTES * 60 * 1000

        long_liq_usd  = 0.0   # Longs got liquidated → price fell
        short_liq_usd = 0.0   # Shorts got liquidated → price rose

        for liq in raw_liquidations:
            t = liq.get("time") or liq.get("trade_time") or 0
            if t < cutoff:
                continue
            try:
                qty   = float(liq.get("accumulated_filled_qty") or liq.get("origQty") or 0)
                price = float(liq.get("average_price") or liq.get("price") or 0)
                notional = qty * price
                side = (liq.get("side") or "").upper()  # BUY or SELL
                # Binance: side=BUY means the exchange bought (short liq)
                #          side=SELL means the exchange sold (long liq)
                if side == "SELL":
                    long_liq_usd  += notional
                elif side == "BUY":
                    short_liq_usd += notional
            except Exception:
                continue

        total = long_liq_usd + short_liq_usd
        if total < self.threshold:
            return None

        dominant = "LONG" if long_liq_usd >= short_liq_usd else "SHORT"
        # Long sweep → longs got wrecked → potential bounce → signal BUY
        # Short sweep → shorts got wrecked → potential reversal → signal SELL
        direction = "BUY LONG" if dominant == "LONG" else "SELL SHORT"
        intensity = "🔴 MASSIVE" if total > self.threshold * 5 else \
                    "🟠 LARGE"   if total > self.threshold * 2 else \
                    "🟡 NOTABLE"

        return {
            "type":           "LIQUIDATION_SWEEP",
            "symbol":         symbol,
            "direction":      direction,
            "dominant_side":  dominant,
            "long_liq_usd":   round(long_liq_usd, 0),
            "short_liq_usd":  round(short_liq_usd, 0),
            "total_usd":      round(total, 0),
            "intensity":      intensity,
            "window_minutes": _WINDOW_MINUTES,
            "timestamp":      datetime.utcnow().isoformat(),
            "note": (
                f"{dominant} liquidation sweep detected. "
                "This often precedes a reversal — confirm with price action before trading."
            ),
        }

    async def scan_global_sweeps(
        self, raw_global: List[Dict], min_threshold: float = None
    ) -> List[Dict]:
        """
        Process global (all-symbol) liquidation feed.
        Groups by symbol and checks each for sweeps.
        Returns list of sweep events across all symbols.
        """
        thresh = min_threshold or self.threshold
        by_symbol: Dict[str, List[Dict]] = {}
        for liq in raw_global:
            sym = liq.get("symbol", "UNKNOWN")
            by_symbol.setdefault(sym, []).append(liq)

        sweeps = []
        for sym, liqs in by_symbol.items():
            result = await self.check_sweep(sym, liqs)
            if result and result["total_usd"] >= thresh:
                sweeps.append(result)

        # Sort by total USD descending
        sweeps.sort(key=lambda x: x["total_usd"], reverse=True)
        return sweeps


liq_detector = LiquidationDetector()
