"""
bot_telegram/handlers.py
All /command handlers for the Telegram bot.
"""

from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from core.market_analyzer import market_analyzer
from core.news_aggregator import news_aggregator
from core.trading_signals import signal_generator, normalize_symbol
from core.liquidation import liq_detector
from core.binance_client import BinanceClient
from core.scheduler import _format_signal_alert, _format_liq_alert
from database import db
from utils.helpers import fmt_price, fmt_pct
from utils.logger import get_logger

logger = get_logger(__name__)


class TelegramHandlers:
    def __init__(self, db_instance, bot_send_fn):
        self.db      = db_instance
        self._send   = bot_send_fn   # async (chat_id, text) → None

    # ── /start ───────────────────────────────────────────────

    async def start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        name = update.effective_user.first_name
        await update.message.reply_text(
            f"👋 Welcome *{name}*!\n\n"
            "I'm your *Crypto Futures Intelligence Bot*.\n"
            "I scan top 100 coins, detect liquidation sweeps, "
            "and push BUY/SELL alerts every 30 minutes.\n\n"
            "Use /help to see all commands.",
            parse_mode="Markdown",
        )

    # ── /help ────────────────────────────────────────────────

    async def help_command(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "📋 *Available Commands*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "/top      — Top 10 BUY + 10 SELL opportunities (top 100 coins)\n"
            "/buy BTC  — BUY analysis for a specific coin\n"
            "/sell ETH — SELL analysis for a specific coin\n"
            "/analysis BTC — Full technical breakdown\n"
            "/liq      — Latest liquidation sweeps\n"
            "/news     — Latest crypto news\n"
            "/summary  — Quick market sentiment summary\n"
            "/status   — Bot status + today's stats\n"
            "/alerts   — Scanner settings\n"
            "/help     — This menu\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🤖 _Auto-alerts fire every 30 min for BUY/SELL signals,\n"
            "every 15 min for breaking news,\n"
            "every 5 min for liquidation sweeps._",
            parse_mode="Markdown",
        )

    # ── /top ─────────────────────────────────────────────────

    async def top_opportunities(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🔍 Scanning top 100 coins... (~30 seconds)", parse_mode="Markdown")
        buys  = await signal_generator.get_top_opportunities(10, action="BUY LONG")
        sells = await signal_generator.get_top_opportunities(10, action="SELL SHORT")

        if not buys and not sells:
            await update.message.reply_text("No strong BUY or SELL setups right now.")
            return

        msg = "🏆 *Top Trading Opportunities*\n━━━━━━━━━━━━━━━━━━━━━━\n"

        if buys:
            msg += "\n🟢 *TOP BUY LONG*\n"
            for i, s in enumerate(buys, 1):
                msg += (
                    f"{i}. *{s['coin'].upper()}* — {s['confidence']}% conf | "
                    f"RSI {s['rsi']:.0f} | {fmt_pct(s['price_change_24h'])} 24h | "
                    f"${fmt_price(s['price'])}\n"
                )
        if sells:
            msg += "\n🔴 *TOP SELL SHORT*\n"
            for i, s in enumerate(sells, 1):
                msg += (
                    f"{i}. *{s['coin'].upper()}* — {s['confidence']}% conf | "
                    f"RSI {s['rsi']:.0f} | {fmt_pct(s['price_change_24h'])} 24h | "
                    f"${fmt_price(s['price'])}\n"
                )

        msg += f"\n━━━━━━━━━━━━━━━━━━━━━━\n⏰ {datetime.utcnow().strftime('%H:%M UTC')}"
        await update.message.reply_text(msg, parse_mode="Markdown")

    # ── /buy <coin> ──────────────────────────────────────────

    async def buy_signal(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        coin = await self._coin_arg(update, ctx, "/buy BTC")
        if not coin:
            return
        signal = await self._get_signal(update, coin)
        if not signal:
            return

        if signal["action"] == "SELL SHORT":
            await update.message.reply_text(
                f"⚠️ *{signal['coin'].upper()}* is currently a *SELL SHORT* setup, not a BUY.\n\n"
                + _format_signal_alert(signal),
                parse_mode="Markdown",
            )
        elif signal["action"] == "HOLD":
            await update.message.reply_text(
                f"⚪ *{signal['coin'].upper()}* has no clear BUY setup right now. Indicators are mixed.",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(_format_signal_alert(signal), parse_mode="Markdown")

    # ── /sell <coin> ─────────────────────────────────────────

    async def sell_signal(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        coin = await self._coin_arg(update, ctx, "/sell ETH")
        if not coin:
            return
        signal = await self._get_signal(update, coin)
        if not signal:
            return

        if signal["action"] == "BUY LONG":
            await update.message.reply_text(
                f"⚠️ *{signal['coin'].upper()}* is currently a *BUY LONG* setup, not a SELL.\n\n"
                + _format_signal_alert(signal),
                parse_mode="Markdown",
            )
        elif signal["action"] == "HOLD":
            await update.message.reply_text(
                f"⚪ *{signal['coin'].upper()}* has no clear SELL setup right now. Indicators are mixed.",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(_format_signal_alert(signal), parse_mode="Markdown")

    # ── /analysis <coin> ─────────────────────────────────────

    async def analysis(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        coin = await self._coin_arg(update, ctx, "/analysis BTC")
        if not coin:
            return

        coin_id = normalize_symbol(coin)
        await update.message.reply_text(f"🔬 Analyzing *{coin_id.upper()}*...", parse_mode="Markdown")

        a = await market_analyzer.analyze_coin(coin_id)
        s = await signal_generator.generate_signal(coin_id)
        if not a or not s:
            await update.message.reply_text(
                f"❌ Could not analyze *{coin_id}*. Try a coin name like bitcoin, ethereum, solana.",
                parse_mode="Markdown",
            )
            return

        # BB position
        price = a["current_price"]
        if price >= a["bb_upper"]:
            bb_pos = "Above Upper Band 🔴"
        elif price <= a["bb_lower"]:
            bb_pos = "Below Lower Band 🟢"
        else:
            bb_pos = "Inside Bands ⚪"

        msg = (
            f"🔬 *Deep Analysis: {coin_id.upper()}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 *Price:*       ${fmt_price(price)}\n"
            f"📊 *Signal:*      {s['action']} ({s['confidence']}% confidence)\n"
            f"⚠️ *Risk Level:*  {s['risk_level']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"*Indicators:*\n"
            f"  📉 RSI (14):    {a['rsi']:.1f}\n"
            f"  📈 EMA21:       ${fmt_price(a['ema21'])}\n"
            f"  📈 EMA50:       ${fmt_price(a['ema50'])}\n"
            f"  📊 BB Upper:    ${fmt_price(a['bb_upper'])}\n"
            f"  📊 BB Lower:    ${fmt_price(a['bb_lower'])}\n"
            f"  📊 BB Position: {bb_pos}\n"
            f"  📈 MACD:        {a['macd_line']:.6g}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"*Price Action:*\n"
            f"  24h: {fmt_pct(a['price_change_24h'])}\n"
            f"  7d:  {fmt_pct(a['price_change_7d'])}\n"
            f"  30d: {fmt_pct(a['price_change_30d'])}\n"
            f"  Volatility: {a['volatility']:.2f}%\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"*Levels:*\n"
            f"  🟢 Support:    ${fmt_price(a['support'])}\n"
            f"  🔴 Resistance: ${fmt_price(a['resistance'])}\n"
            f"  🎯 Entry:      ${fmt_price(s['entry_point'])}\n"
            f"  🛑 Stop Loss:  ${fmt_price(s['stop_loss'])}\n"
            f"  ✅ Take Profit: ${fmt_price(s['take_profit'])}\n"
            f"  ⚖️ R/R Ratio:  {s['risk_reward']}:1\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💬 _{s['bot_view']}_"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    # ── /liq ─────────────────────────────────────────────────

    async def liquidations(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("💥 Scanning liquidation data...", parse_mode="Markdown")
        try:
            async with BinanceClient() as client:
                raw = await client.get_global_liquidations(limit=100)

            if not raw:
                await update.message.reply_text("No liquidation data available right now.")
                return

            sweeps = await liq_detector.scan_global_sweeps(raw, min_threshold=200_000)

            if not sweeps:
                await update.message.reply_text(
                    "✅ No significant liquidation sweeps in the last 15 minutes.\n"
                    "Market is relatively calm."
                )
                return

            await update.message.reply_text(
                f"💥 *{len(sweeps)} Liquidation Sweep(s) Detected*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━",
                parse_mode="Markdown",
            )
            for sweep in sweeps[:5]:
                await update.message.reply_text(_format_liq_alert(sweep), parse_mode="Markdown")

        except Exception as e:
            logger.error(f"/liq error: {e}", exc_info=True)
            await update.message.reply_text("❌ Error fetching liquidation data. Try again.")

    # ── /news ────────────────────────────────────────────────

    async def news(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("📰 Fetching latest crypto news...")
        articles = await news_aggregator.fetch_news(limit=5)

        if not articles:
            await update.message.reply_text("Could not fetch news right now. Try again in a minute.")
            return

        for a in articles:
            priority = "🔥 *BREAKING*\n" if a.get("high_priority") else ""
            msg = (
                f"{priority}"
                f"*{a['title'][:120]}*\n"
                f"📡 {a['source']}\n"
                f"🔗 {a['url']}"
            )
            await update.message.reply_text(msg, parse_mode="Markdown")

    # ── /summary ─────────────────────────────────────────────

    async def summary(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("📊 Building market summary...")
        signals = await signal_generator.scan_top_coins(20, include_hold=True)

        if not signals:
            await update.message.reply_text("Could not fetch market data right now.")
            return

        buys  = [s for s in signals if s["action"] == "BUY LONG"]
        sells = [s for s in signals if s["action"] == "SELL SHORT"]
        total = len(signals)
        bull  = round(len(buys) / total * 100) if total else 0
        bear  = round(len(sells) / total * 100) if total else 0
        mood  = "🟢 BULLISH" if bull > 55 else "🔴 BEARISH" if bear > 55 else "⚪ NEUTRAL"

        msg = (
            f"📊 *Market Summary (Top 20)*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🌡️ Sentiment: *{mood}*\n"
            f"🟢 BUY signals:  {len(buys)}/{total} ({bull}%)\n"
            f"🔴 SELL signals: {len(sells)}/{total} ({bear}%)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
        )
        for i, s in enumerate(signals[:10], 1):
            icon = "🟢" if s["action"] == "BUY LONG" else "🔴" if s["action"] == "SELL SHORT" else "⚪"
            msg += f"{i:2}. {icon} *{s['coin'].upper():12}* {fmt_pct(s['price_change_24h'])} 24h | RSI {s['rsi']:.0f}\n"

        await update.message.reply_text(msg, parse_mode="Markdown")

    # ── /status ──────────────────────────────────────────────

    async def status(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        stats = self.db.get_daily_stats()
        await update.message.reply_text(
            f"🤖 *Bot Status*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Status:          ONLINE\n"
            f"📊 Signals today:   {stats['total_signals']}\n"
            f"🟢 BUY signals:     {stats['buy_signals']}\n"
            f"🔴 SELL signals:    {stats['sell_signals']}\n"
            f"🪙 Coins tracked:   {stats['unique_coins']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            parse_mode="Markdown",
        )

    # ── /alerts ──────────────────────────────────────────────

    async def alerts(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        stats = self.db.get_daily_stats()
        await update.message.reply_text(
            f"⚙️ *Alert Configuration*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📡 Signal scan:    every 30 min (top 100 coins)\n"
            f"📰 News alerts:    every 15 min (new articles only)\n"
            f"💥 Liq sweeps:     every 5 min\n"
            f"📊 Market report:  every 30 min\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔢 Confidence threshold: 65%\n"
            f"⏳ Cooldown per coin:    6 hours\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Today: {stats['total_signals']} signals | "
            f"{stats['buy_signals']} BUY | {stats['sell_signals']} SELL",
            parse_mode="Markdown",
        )

    # ── Helpers ──────────────────────────────────────────────

    async def _coin_arg(self, update, ctx, usage: str) -> str | None:
        if not ctx.args:
            await update.message.reply_text(f"Usage: `{usage}`", parse_mode="Markdown")
            return None
        return ctx.args[0]

    async def _get_signal(self, update, coin: str):
        coin_id = normalize_symbol(coin)
        await update.message.reply_text(f"🔍 Analyzing *{coin_id.upper()}*...", parse_mode="Markdown")
        signal = await signal_generator.generate_signal(coin_id)
        if not signal:
            await update.message.reply_text(
                f"❌ Could not analyze *{coin_id}*. Try: bitcoin, ethereum, solana, etc.",
                parse_mode="Markdown",
            )
            return None
        return signal
