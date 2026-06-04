"""
core/scheduler.py
Background task scheduler.
Runs inside the bot's asyncio event loop.

Tasks:
 1. Signal scan    — every SCAN_INTERVAL_MINUTES (default 30)
 2. News alert     — every 15 min, push only new articles
 3. Market report  — every 30 min, 1-hour lookback summary
 4. Liq sweep      — every 5 min, global liquidation scan
"""

import asyncio
from datetime import datetime
from typing import Callable, Awaitable

from config import Config
from core.trading_signals import signal_generator
from core.market_analyzer import market_analyzer
from core.news_aggregator import news_aggregator
from core.liquidation import liq_detector
from core.binance_client import BinanceClient
from database import db
from utils.helpers import fmt_price, fmt_pct
from utils.logger import get_logger

logger = get_logger(__name__)

# Type alias for the send_message callback
SendFn = Callable[[str], Awaitable[None]]


class Scheduler:
    def __init__(self, send_fn: SendFn):
        self._send    = send_fn
        self._running = False
        self._tasks   = []

    # ── Public ───────────────────────────────────────────────

    def start(self) -> None:
        self._running = True
        self._tasks = [
            asyncio.create_task(self._signal_scan_loop()),
            asyncio.create_task(self._news_loop()),
            asyncio.create_task(self._market_report_loop()),
            asyncio.create_task(self._liq_sweep_loop()),
        ]
        logger.info("Scheduler started — 4 background tasks running")

    def stop(self) -> None:
        self._running = False
        for t in self._tasks:
            t.cancel()
        self._tasks = []
        logger.info("Scheduler stopped")

    # ── Task 1: Signal scan every 30 min ────────────────────

    async def _signal_scan_loop(self) -> None:
        interval = Config.SCAN_INTERVAL_MINUTES * 60
        logger.info(f"Signal scan loop: every {Config.SCAN_INTERVAL_MINUTES} min")
        while self._running:
            try:
                await self._run_signal_scan()
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error(f"Signal scan error: {e}", exc_info=True)
            await asyncio.sleep(interval)

    async def _run_signal_scan(self) -> None:
        logger.info("Running signal scan...")
        signals = await signal_generator.scan_top_coins(
            Config.TOP_COINS_SCAN_LIMIT, include_hold=False
        )
        sent = 0
        for signal in signals:
            action = signal.get("action")
            coin   = signal.get("coin", signal.get("symbol", ""))
            conf   = signal.get("confidence", 0)

            if action not in {"BUY LONG", "SELL SHORT"}:
                continue
            if conf < Config.CONFIDENCE_THRESHOLD:
                continue
            if db.check_cooldown(coin, action):
                continue

            await self._send(_format_signal_alert(signal))
            db.insert_signal(signal)
            db.set_cooldown(coin, action, Config.ALERT_COOLDOWN_HOURS)
            sent += 1
            await asyncio.sleep(0.5)  # avoid Telegram flood

        logger.info(f"Signal scan done — {sent} alerts sent")

    # ── Task 2: News alert every 15 min ─────────────────────

    async def _news_loop(self) -> None:
        logger.info("News alert loop: every 15 min")
        while self._running:
            try:
                await self._run_news_check()
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error(f"News loop error: {e}", exc_info=True)
            await asyncio.sleep(900)   # 15 minutes

    async def _run_news_check(self) -> None:
        new_articles = await news_aggregator.fetch_new_only(limit=5)
        if not new_articles:
            return
        for article in new_articles:
            await self._send(_format_news_alert(article))
            await asyncio.sleep(1)
        logger.info(f"News: sent {len(new_articles)} new articles")

    # ── Task 3: Market report every 30 min ──────────────────

    async def _market_report_loop(self) -> None:
        logger.info("Market report loop: every 30 min")
        while self._running:
            try:
                await self._run_market_report()
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error(f"Market report error: {e}", exc_info=True)
            await asyncio.sleep(1800)  # 30 minutes

    async def _run_market_report(self) -> None:
        logger.info("Building 30-min market report...")
        # Analyse top 20 coins for the summary
        signals = await signal_generator.scan_top_coins(20, include_hold=True)
        if not signals:
            return

        buys  = [s for s in signals if s["action"] == "BUY LONG"]
        sells = [s for s in signals if s["action"] == "SELL SHORT"]
        holds = [s for s in signals if s["action"] == "HOLD"]

        # Market sentiment
        total = len(signals)
        bull_pct = round(len(buys) / total * 100) if total else 0
        bear_pct = round(len(sells) / total * 100) if total else 0

        mood = "🟢 BULLISH" if bull_pct > 55 else "🔴 BEARISH" if bear_pct > 55 else "⚪ NEUTRAL"

        lines = [
            "━━━━━━━━━━━━━━━━━━━━━━",
            f"📊 *30-Min Market Report*",
            f"🕒 {datetime.utcnow().strftime('%H:%M UTC')}",
            "━━━━━━━━━━━━━━━━━━━━━━",
            f"🌡️ Sentiment: {mood}",
            f"🟢 BUY signals:  {len(buys)} ({bull_pct}%)",
            f"🔴 SELL signals: {len(sells)} ({bear_pct}%)",
            f"⚪ HOLD:         {len(holds)}",
            "",
            "*Top BUY setups:*",
        ]
        for s in buys[:3]:
            lines.append(
                f"  • {s['coin'].upper()} — {s['confidence']}% confidence "
                f"| RSI {s['rsi']:.0f} | {fmt_pct(s['price_change_24h'])} 24h"
            )
        lines.append("*Top SELL setups:*")
        for s in sells[:3]:
            lines.append(
                f"  • {s['coin'].upper()} — {s['confidence']}% confidence "
                f"| RSI {s['rsi']:.0f} | {fmt_pct(s['price_change_24h'])} 24h"
            )
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")

        await self._send("\n".join(lines))
        logger.info("Market report sent")

    # ── Task 4: Liquidation sweep every 5 min ───────────────

    async def _liq_sweep_loop(self) -> None:
        logger.info("Liquidation sweep loop: every 5 min")
        while self._running:
            try:
                await self._run_liq_scan()
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error(f"Liq sweep error: {e}", exc_info=True)
            await asyncio.sleep(300)   # 5 minutes

    async def _run_liq_scan(self) -> None:
        try:
            async with BinanceClient() as client:
                raw = await client.get_global_liquidations(limit=100)

            if not raw:
                return

            sweeps = await liq_detector.scan_global_sweeps(raw)
            for sweep in sweeps[:3]:   # max 3 per scan to avoid spam
                coin = sweep["symbol"].replace("USDT", "").lower()
                key  = f"liq_{sweep['direction']}"
                if db.check_cooldown(coin, key):
                    continue
                await self._send(_format_liq_alert(sweep))
                db.set_cooldown(coin, key, 1)   # 1-hour cooldown
        except Exception as e:
            logger.error(f"Liq scan error: {e}")


# ── Formatters ───────────────────────────────────────────────

def _format_signal_alert(signal: Dict) -> str:
    icon   = "🟢" if signal["action"] == "BUY LONG" else "🔴"
    emo    = "📈" if signal["action"] == "BUY LONG" else "📉"
    rr     = signal.get("risk_reward", 0)
    reasons = signal.get("reasons", [])
    if isinstance(reasons, list):
        reason_text = "\n".join(f"  {r}" for r in reasons[:4])
    else:
        reason_text = reasons

    return (
        f"{icon} *{signal['action']} SIGNAL* {emo}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🪙 *Coin:*       {signal['coin'].upper()}\n"
        f"💰 *Price:*      ${fmt_price(signal['price'])}\n"
        f"📊 *Confidence:* {signal['confidence']}%\n"
        f"⚠️ *Risk Level:* {signal['risk_level']}\n"
        f"📐 *Signal:*     {signal['signal_type']}\n"
        f"🎯 *Entry:*      ${fmt_price(signal['entry_point'])}\n"
        f"🛑 *Stop Loss:*  ${fmt_price(signal['stop_loss'])}\n"
        f"✅ *Take Profit:* ${fmt_price(signal['take_profit'])}\n"
        f"⚖️ *Risk/Reward:* {rr}:1\n"
        f"📉 *RSI:*        {signal['rsi']:.1f}\n"
        f"📊 *24h Change:* {fmt_pct(signal['price_change_24h'])}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"*Analysis:*\n{reason_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 _{signal['bot_view']}_\n"
        f"⏰ {datetime.utcnow().strftime('%H:%M UTC')}"
    )


def _format_news_alert(article: Dict) -> str:
    priority = "🔥 *BREAKING*" if article.get("high_priority") else "📰 *News Alert*"
    return (
        f"{priority}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"*{article['title'][:120]}*\n"
        f"📡 Source: {article['source']}\n"
        f"🔗 {article['url']}"
    )


def _format_liq_alert(sweep: Dict) -> str:
    direction = sweep["direction"]
    icon = "🟢 LONG SWEEP → Potential Bounce" if direction == "BUY LONG" \
           else "🔴 SHORT SWEEP → Potential Reversal"
    total_m = round(sweep["total_usd"] / 1_000_000, 2)
    long_m  = round(sweep["long_liq_usd"] / 1_000_000, 2)
    short_m = round(sweep["short_liq_usd"] / 1_000_000, 2)

    return (
        f"💥 *LIQUIDATION SWEEP DETECTED* 💥\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🪙 *Symbol:*    {sweep['symbol']}\n"
        f"{sweep['intensity']} — {icon}\n"
        f"💵 *Total Liq:* ${total_m}M\n"
        f"  🟢 Longs liquidated:  ${long_m}M\n"
        f"  🔴 Shorts liquidated: ${short_m}M\n"
        f"⏱️ *Window:*   last {sweep['window_minutes']} minutes\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ _{sweep['note']}_\n"
        f"📊 *Analyze price action before trading.*\n"
        f"⏰ {datetime.utcnow().strftime('%H:%M UTC')}"
    )
