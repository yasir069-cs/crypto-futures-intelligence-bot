#!/usr/bin/env python3
"""
Crypto Market Intelligence Bot
Telegram-based bot for market analysis and signals
"""

import asyncio
import signal
import sys
from datetime import datetime
from database import Database
from config import Config
from utils.logger import get_logger, setup_logging
from bot_telegram.bot import TelegramBot

logger = None
bot = None

async def main():
    """Main entry point"""
    global logger, bot
    
    # Setup logging
    setup_logging(Config.LOG_LEVEL)
    logger = get_logger(__name__)
    
    logger.info("="*60)
    logger.info("Crypto Market Intelligence Bot")
    logger.info(f"Started at {datetime.utcnow().isoformat()} UTC")
    logger.info("="*60)
    
    try:
        # Validate configuration
        Config.validate()
        logger.info("Configuration validated successfully")
        
        # Initialize database
        app_db = Database()

        # Initialize Telegram bot
        bot = TelegramBot(app_db)
        await bot.initialize()
        logger.info("Telegram bot initialized and running")
        logger.info("Bot is ready for commands. Press Ctrl+C to stop.")
        
        # Keep bot running
        await bot.run_polling()
        
    except KeyboardInterrupt:
        logger.info("Bot interrupted by user")
        await shutdown()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        await shutdown()
        sys.exit(1)

async def shutdown():
    """Graceful shutdown"""
    global bot
    
    logger.info("Shutting down bot...")
    
    if bot:
        await bot.stop()
    
    logger.info("Bot shutdown complete")

def handle_signal(signum, frame):
    """Handle system signals"""
    logger.info(f"Received signal {signum}")
    asyncio.create_task(shutdown())

if __name__ == '__main__':
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    # Run bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        sys.exit(0)
