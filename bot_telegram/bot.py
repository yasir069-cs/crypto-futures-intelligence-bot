import asyncio
from datetime import datetime

from telegram import Update
from telegram.ext import Application, CommandHandler

from config import Config
from core.trading_signals import signal_generator
from bot_telegram.handlers import TelegramHandlers
from utils.logger import get_logger

logger = get_logger(__name__)


class TelegramBot:
    """Main Telegram bot class."""

    def __init__(self, db_instance):
        self.db = db_instance
        self.app = None
        self.handlers = None
        self.running = False
        self.alert_task = None

    async def initialize(self):
        """Initialize the bot and command handlers."""
        self.app = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
        self.handlers = TelegramHandlers(self.db)

        command_handlers = {
            "start": self.handlers.start,
            "help": self.handlers.help_command,
            "summary": self.handlers.summary,
            "top": self.handlers.top_opportunities,
            "buy": self.handlers.buy_signal,
            "sell": self.handlers.sell_signal,
            "analysis": self.handlers.analysis,
            "alerts": self.handlers.alerts,
            "portfolio": self.handlers.portfolio,
            "news": self.handlers.news,
            "status": self.handlers.status,
            "language": self.handlers.language_command,
        }
        for command, handler in command_handlers.items():
            self.app.add_handler(CommandHandler(command, handler))

        self.running = True
        logger.info("Bot initialized successfully")

    async def run_polling(self):
        """Run the bot with polling."""
        if not self.app:
            raise RuntimeError("Bot not initialized")

        self.alert_task = asyncio.create_task(self.start_background_tasks())
        try:
            await self.app.run_polling(allowed_updates=Update.ALL_TYPES)
        except Exception as e:
            logger.error(f"Error in polling: {e}")
            raise

    async def start_background_tasks(self):
        """Run automatic BUY/SELL scans on the configured interval."""
        while self.running:
            try:
                await self.run_signal_alert_scan()
                await asyncio.sleep(Config.SCAN_INTERVAL_MINUTES * 60)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error in background alert scan: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def run_signal_alert_scan(self):
        """Scan top coins and alert configured chat for non-HOLD signals."""
        signals = await signal_generator.scan_top_coins(
            Config.TOP_COINS_SCAN_LIMIT,
            include_hold=False,
        )

        for signal in signals:
            action = signal.get("action")
            coin = signal.get("coin") or signal.get("symbol")
            if action not in {"BUY LONG", "SELL SHORT"} or not coin:
                continue
            if self.db.check_cooldown(coin, action):
                continue

            await self.send_signal_alert(signal)
            self.db.insert_signal(signal)
            self.db.set_cooldown(coin, action, Config.ALERT_COOLDOWN_HOURS)

    async def send_message(self, chat_id: str, message: str):
        """Send message to user."""
        try:
            if self.app:
                await self.app.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
                logger.info(f"Message sent to {chat_id}")
        except Exception as e:
            logger.error(f"Error sending message: {e}")

    async def stop(self):
        """Stop the bot."""
        self.running = False
        if self.alert_task:
            self.alert_task.cancel()
        if self.app:
            await self.app.stop()
        logger.info("Bot stopped")

    async def send_signal_alert(self, signal: dict):
        """Send a formatted signal alert to the configured chat ID."""
        reasons = signal.get("reasons", [])
        if isinstance(reasons, list):
            reasons = "\n".join(f"- {reason}" for reason in reasons[:5])

        message = (
            f"🚨 **New Signal Alert** 🚨\n\n"
            f"📈 **Coin:** {(signal.get('coin') or signal.get('symbol', '')).upper()}\n"
            f"➡️ **Action:** {signal.get('action')}\n"
            f"🎯 **Signal Type:** {signal.get('signal_type')}\n"
            f"📊 **Confidence:** {signal.get('confidence')}%\n"
            f"⚠️ **Risk Level:** {signal.get('risk_level')}\n"
            f"💲 **Price:** ${signal.get('price', 0):.6g}\n"
            f"⏱️ **Timeframe:** {signal.get('timeframe', '1D')}\n"
            f"🕒 **Timestamp:** {signal.get('timestamp', datetime.utcnow().isoformat())}\n\n"
            f"💡 **Reasons:**\n{reasons}"
        )
        await self.send_message(Config.TELEGRAM_CHAT_ID, message)
