"""
bot_telegram/bot.py
Main Telegram bot class — wires handlers + scheduler together.
"""

import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler
from telegram.constants import ParseMode

from config import Config
from database import db
from bot_telegram.handlers import TelegramHandlers
from core.scheduler import Scheduler
from utils.logger import get_logger

logger = get_logger(__name__)


class TelegramBot:
    def __init__(self):
        self.app       = None
        self.handlers  = None
        self.scheduler = None
        self._running  = False

    async def initialize(self):
        self.app = (
            Application.builder()
            .token(Config.TELEGRAM_BOT_TOKEN)
            .build()
        )

        # send_fn used by scheduler to push messages to the configured chat
        async def send_fn(text: str):
            try:
                await self.app.bot.send_message(
                    chat_id=Config.TELEGRAM_CHAT_ID,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN,
                )
            except Exception as e:
                logger.error(f"send_fn error: {e}")

        self.handlers  = TelegramHandlers(db, send_fn)
        self.scheduler = Scheduler(send_fn)

        # Register commands
        cmds = {
            "start":    self.handlers.start,
            "help":     self.handlers.help_command,
            "top":      self.handlers.top_opportunities,
            "buy":      self.handlers.buy_signal,
            "sell":     self.handlers.sell_signal,
            "analysis": self.handlers.analysis,
            "liq":      self.handlers.liquidations,
            "news":     self.handlers.news,
            "summary":  self.handlers.summary,
            "status":   self.handlers.status,
            "alerts":   self.handlers.alerts,
        }
        for name, fn in cmds.items():
            self.app.add_handler(CommandHandler(name, fn))

        self._running = True
        logger.info("TelegramBot initialized — all commands registered")

    async def run_polling(self):
        if not self.app:
            raise RuntimeError("Call initialize() first")

        # Start scheduler (background tasks) after app starts
        async def post_init(app):
            self.scheduler.start()
            logger.info("Background scheduler started")

        self.app.post_init = post_init

        logger.info("Starting polling...")
        await self.app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )

    async def stop(self):
        self._running = False
        if self.scheduler:
            self.scheduler.stop()
        if self.app:
            await self.app.stop()
        logger.info("Bot stopped")
