"""
core/trading_signals.py
Signal generation engine.
Uses: RSI + EMA21 + EMA50 + Bollinger Bands + MACD + Volume + Liquidation.
Each factor contributes to a weighted confidence score (0-100).
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional

from config import Config
from database import db
from core.market_analyzer import market_analyzer
from utils.helpers import fmt_price, fmt_pct
from utils.logger import get_logger

logger = get_logger(__name__)

# ── Coin aliases: user input → CoinGecko id ─────────────────
_ALIASES = {
    "btc": "bitcoin",       "bitcoin": "bitcoin",
    "eth": "ethereum",      "ethereum": "ethereum",
    "sol": "solana",        "solana": "solana",
    "xrp": "ripple",        "ripple": "ripple",
    "ada": "cardano",       "cardano": "cardano",
    "doge": "dogecoin",     "dogecoin": "dogecoin",
    "dot": "polkadot",      "polkadot": "polkadot",
    "link": "chainlink",    "chainlink": "chainlink",
    "ltc": "litecoin",      "litecoin": "litecoin",
    "uni": "uniswap",       "uniswap": "uniswap",
    "bnb": "binancecoin",   "binancecoin": "binancecoin",
    "matic": "matic-network","polygon": "matic-network",
    "avax": "avalanche-2",  "avalanche": "avalanche-2",
    "trx": "tron",          "tron": "tron",
    "atom": "cosmos",       "cosmos": "cosmos",
    "near": "near",
    "apt": "aptos",         "aptos": "aptos",
    "arb": "arbitrum",      "arbitrum": "arbitrum",
    "op": "optimism",       "optimism": "optimism",
    "shib": "shiba-inu",    "shiba": "shiba-inu",
}


def normalize_symbol(symbol: str) -> str:
    cleaned = symbol.strip().lower()
    for suffix in ("/usdt", "usdt", "-usd", "-usdt", "usd"):
        cleaned = cleaned.replace(suffix, "")
    return _ALIASES.get(cleaned, cleaned)


class TradingSignalGenerator:

    async def generate_signal(self, symbol: str) -> Optional[Dict]:
        """Full signal for one coin. Returns None if analysis fails."""
        coin_id = normalize_symbol(symbol)
        a = await market_analyzer.analyze_coin(coin_id)
        if not a or not a.get("current_price"):
            return None

        score, reasons = self._score(a)
        action         = self._action(score)
        confidence     = self._confidence(score)
        signal_type    = self._signal_type(a)

        return {
            "coin":             coin_id,
            "symbol":           coin_id,
            "action":           action,
            "signal_type":      signal_type,
            "confidence":       confidence,
            "risk_level":       self._risk(confidence),
            "price":            a["current_price"],
            "rsi":              a["rsi"],
            "ema21":            a["ema21"],
            "ema50":            a["ema50"],
            "bb_upper":         a["bb_upper"],
            "bb_lower":         a["bb_lower"],
            "macd_line":        a["macd_line"],
            "volatility":       a["volatility"],
            "support":          a["support"],
            "resistance":       a["resistance"],
            "price_change_24h": a["price_change_24h"],
            "price_change_7d":  a["price_change_7d"],
            "price_change_30d": a["price_change_30d"],
            "rvol":             a.get("rvol", 0),
            "entry_point":      self._entry(a),
            "stop_loss":        self._stop_loss(a, action),
            "take_profit":      self._take_profit(a, action),
            "risk_reward":      self._rr(a, action),
            "reasons":          reasons,
            "bot_view":         self._bot_view(action, confidence, a),
            "timeframe":        "1D",
            "timestamp":        datetime.utcnow().isoformat(),
        }

    async def scan_top_coins(
        self, limit: int = 100, include_hold: bool = False
    ) -> List[Dict]:
        """Analyze top `limit` coins concurrently. Returns signals sorted by confidence."""
        coin_ids = await market_analyzer.get_top_coin_ids(limit)

        # Binance rate-limit friendly: batch 10 at a time
        signals = []
        batch_size = 10
        for i in range(0, len(coin_ids), batch_size):
            batch   = coin_ids[i:i + batch_size]
            tasks   = [self.generate_signal(c) for c in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception) or not r:
                    continue
                if not include_hold and r["action"] == "HOLD":
                    continue
                signals.append(r)
            await asyncio.sleep(1)   # be gentle with free API

        return sorted(signals, key=lambda x: x["confidence"], reverse=True)

    async def get_top_opportunities(
        self, limit: int = 10, action: str = None
    ) -> List[Dict]:
        """Top non-HOLD signals, optionally filtered by action."""
        signals = await self.scan_top_coins(Config.TOP_COINS_SCAN_LIMIT)
        if action:
            signals = [s for s in signals if s["action"] == action]
        return signals[:limit]

    # ── Scoring ──────────────────────────────────────────────

    def _score(self, a: Dict):
        """
        Returns (raw_score, reasons).
        raw_score > 0 → bullish, < 0 → bearish, ~0 → hold.
        """
        score   = 0.0
        reasons = []

        rsi_v = a["rsi"]
        price = a["current_price"]
        ema21 = a["ema21"]
        ema50 = a["ema50"]
        bb_u  = a["bb_upper"]
        bb_l  = a["bb_lower"]
        macd  = a["macd_line"]
        vol   = a["volatility"]
        rvol  = a.get("rvol", 1)

        # ── RSI (±25 pts) ─────────────────────────────────
        if rsi_v < 30:
            score += 25
            reasons.append(f"📉 RSI oversold ({rsi_v:.1f}) — strong buy zone")
        elif rsi_v < 45:
            score += 12
            reasons.append(f"📉 RSI low ({rsi_v:.1f}) — bullish bias")
        elif rsi_v > 70:
            score -= 25
            reasons.append(f"📈 RSI overbought ({rsi_v:.1f}) — strong sell zone")
        elif rsi_v > 55:
            score -= 12
            reasons.append(f"📈 RSI elevated ({rsi_v:.1f}) — bearish bias")
        else:
            reasons.append(f"➡️ RSI neutral ({rsi_v:.1f})")

        # ── EMA21 vs EMA50 cross (±20 pts) ────────────────
        if ema21 > ema50 and price > ema21:
            score += 20
            reasons.append(f"✅ Price > EMA21 > EMA50 — bullish trend")
        elif ema21 < ema50 and price < ema21:
            score -= 20
            reasons.append(f"❌ Price < EMA21 < EMA50 — bearish trend")
        elif price > ema21:
            score += 8
            reasons.append(f"✅ Price above EMA21")
        elif price < ema21:
            score -= 8
            reasons.append(f"❌ Price below EMA21")

        # ── Bollinger Bands (±15 pts) ──────────────────────
        if price <= bb_l:
            score += 15
            reasons.append(f"📊 Price at/below BB lower — potential bounce")
        elif price >= bb_u:
            score -= 15
            reasons.append(f"📊 Price at/above BB upper — potential pullback")
        else:
            reasons.append(f"📊 Price within Bollinger Bands")

        # ── MACD (±10 pts) ─────────────────────────────────
        if macd > 0:
            score += 10
            reasons.append(f"📈 MACD positive ({macd:.4f})")
        elif macd < 0:
            score -= 10
            reasons.append(f"📉 MACD negative ({macd:.4f})")

        # ── Volume (±5 pts) ────────────────────────────────
        if rvol >= 2.0:
            score += 5 if score > 0 else -5   # volume confirms direction
            reasons.append(f"📦 High relative volume ({rvol:.1f}x)")

        # ── Price momentum 24h (±5 pts) ───────────────────
        pc = a["price_change_24h"]
        if pc > 5:
            score += 5
            reasons.append(f"🚀 Strong 24h momentum (+{pc:.1f}%)")
        elif pc < -5:
            score -= 5
            reasons.append(f"🔻 Weak 24h momentum ({pc:.1f}%)")

        return score, reasons

    def _action(self, score: float) -> str:
        if score >= 30:
            return "BUY LONG"
        if score <= -30:
            return "SELL SHORT"
        return "HOLD"

    def _confidence(self, score: float) -> int:
        """Map raw score → 0-100 confidence."""
        abs_score = abs(score)
        # Max possible score ≈ 80
        return min(100, int(abs_score / 80 * 100))

    def _signal_type(self, a: Dict) -> str:
        if a["volatility"] < 2 and abs(a["price_change_24h"]) < 3:
            return "SWING"
        return "INTRADAY"

    def _risk(self, confidence: int) -> str:
        if confidence >= 75:
            return "LOW"
        if confidence >= 60:
            return "MEDIUM"
        return "HIGH"

    def _entry(self, a: Dict) -> float:
        return a["current_price"]

    def _stop_loss(self, a: Dict, action: str) -> float:
        support    = a["support"]
        resistance = a["resistance"]
        price      = a["current_price"]
        if action == "BUY LONG":
            # SL = 2% below support
            return round(support * 0.98, 6)
        elif action == "SELL SHORT":
            # SL = 2% above resistance
            return round(resistance * 1.02, 6)
        return price

    def _take_profit(self, a: Dict, action: str) -> float:
        support    = a["support"]
        resistance = a["resistance"]
        price      = a["current_price"]
        if action == "BUY LONG":
            return round(resistance * 1.02, 6)
        elif action == "SELL SHORT":
            return round(support * 0.98, 6)
        return price

    def _rr(self, a: Dict, action: str) -> float:
        entry = self._entry(a)
        sl    = self._stop_loss(a, action)
        tp    = self._take_profit(a, action)
        risk   = abs(entry - sl)
        reward = abs(tp - entry)
        if risk == 0:
            return 0.0
        return round(reward / risk, 2)

    def _bot_view(self, action: str, confidence: int, a: Dict) -> str:
        if action == "BUY LONG":
            if confidence >= 80:
                return "Strong bullish setup — RSI, EMA & BB all aligned. High conviction."
            return "Bullish setup forming. Moderate confidence — wait for price confirmation."
        if action == "SELL SHORT":
            if confidence >= 80:
                return "Strong bearish setup — multiple indicators confirm downside. High conviction."
            return "Bearish setup forming. Moderate confidence — watch for rejection candle."
        return "No directional edge. Indicators are mixed — stay on the sidelines."


signal_generator = TradingSignalGenerator()
