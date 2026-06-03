from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram import Update
import asyncio
from datetime import datetime
from config import Config
from telegram.handlers import TelegramHandlers
from core.alert_scheduler import alert_scheduler
from utils.logger import get_logger

logger = get_logger(__name__)

class TelegramBot:
    """Main Telegram bot class"""
    
    def __init__(self, db_instance):
        self.db = db_instance
        self.app = None
        self.running = False
    
    async def initialize(self):
        """Initialize the bot"""
        self.app = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
        
        # Instantiate handlers with the database instance
        self.handlers = TelegramHandlers(self.db)
        self.app.add_handler(CommandHandler("start", self.handlers.start))
        self.app.add_handler(CommandHandler("help", self.handlers.help_command))
        self.app.add_handler(CommandHandler("summary", self.handlers.summary))
        self.app.add_handler(CommandHandler("top", self.handlers.top_opportunities))
        self.app.add_handler(CommandHandler("buy", self.handlers.buy_signal))
        self.app.add_handler(CommandHandler("portfolio", self.handlers.portfolio))
        self.app.add_handler(CommandHandler("news", self.handlers.news))
        self.app.add_handler(CommandHandler("status", self.handlers.status))
        self.app.add_handler(CommandHandler("language", self.handlers.language_command))
        
        self.running = True
        logger.info("Bot initialized successfully")
    
    async def run_polling(self):
        """Run the bot with polling"""
        if not self.app:
            raise RuntimeError("Bot not initialized")
        
        try:
            # Start background alert scheduler
            asyncio.create_task(self.start_background_tasks())
            
            # Start polling
            await self.app.run_polling(allowed_updates=Update.ALL_TYPES)
        except Exception as e:
            logger.error(f"Error in polling: {e}")
            raise
    
    async def start_background_tasks(self):
        """Start background tasks"""
        while self.running:
            try:
                # Could add background scan tasks here
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Error in background tasks: {e}")
                await asyncio.sleep(60)
    
    async def send_message(self, chat_id: str, message: str):
        """Send message to user"""
        try:
            if self.app:
                await self.app.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
                logger.info(f"Message sent to {chat_id}")
        except Exception as e:
            logger.error(f"Error sending message: {e}")
    
    async def stop(self):
        """Stop the bot"""
        self.running = False
        if self.app:
            await self.app.stop()
        logger.info("Bot stopped")

    async def send_signal_alert(self, signal: dict):
        """Send a formatted signal alert to the configured chat ID"""
        message = (
            f"🚨 **New Signal Alert** 🚨\n\n"
            f"📈 **Coin:** {signal["coin"].upper()}\n"
            f"➡️ **Action:** {signal["action"]}\n"
            f"🎯 **Signal Type:** {signal["signal_type"]}\n"
            f"📊 **Confidence:** {signal["confidence"]}%\n"
            f"⚠️ **Risk Level:** {signal["risk_level"]}\n"
            f"💡 **Reasons:** {signal["reasons"]}\n"
            f"💲 **Price:** ${signal["price"]:.2f}\n"
            f"⏱️ **Timeframe:** {signal["timeframe"]}\n"
            f"⏰ **Timestamp:** {signal["timestamp"]}\n"
        )
        await self.send_message(Config.TELEGRAM_CHAT_ID, message)
