#!/usr/bin/env python3
"""
main.py — Crypto Futures Intelligence Bot
Entry point. Run with: python main.py
"""

import asyncio
import sys
from datetime import datetime

from config import Config
from utils.logger import setup_logging, get_logger
from bot_telegram.bot import TelegramBot

logger = None
bot    = None


async def main():
    global logger, bot

    setup_logging(Config.LOG_LEVEL)
    logger = get_logger("main")

    logger.info("=" * 55)
    logger.info("  Crypto Futures Intelligence Bot")
    logger.info(f"  Started: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    logger.info("=" * 55)

    Config.validate()
    logger.info("Configuration OK")

    bot = TelegramBot()
    await bot.initialize()
    logger.info("Bot initialized — starting polling")

    try:
        await bot.run_polling()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        if bot:
            await bot.stop()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
