from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime
from config import Config
from core.trading_signals import signal_generator

from core.news_aggregator import news_aggregator
from core.market_analyzer import market_analyzer
from models.language_support import language_support
from utils.logger import get_logger
from database import Database
from core.portfolio_tracker import PortfolioTracker




logger = get_logger(__name__)

class TelegramHandlers:
    """Handle telegram bot commands"""
    def __init__(self, db_instance):
        self.db = db_instance
        self.portfolio_tracker = PortfolioTracker(self.db)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name
        
        message = f'''👋 Welcome to Crypto Futures Intelligence Bot, {user_name}!

🤖 I'm your AI-powered crypto trading assistant.

📊 What I can do:
✅ Real-time market analysis
✅ Trading signals & alerts
✅ Portfolio tracking
✅ Volatility monitoring
✅ News aggregation
✅ Risk analysis

💡 Type /help to see all commands
📈 Get started with /summary for market overview

Happy trading! 🚀'''
        
        await update.message.reply_text(message)
        logger.info(f"User {user_name} ({user_id}) started the bot")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = language_support.get_message('help', 'Help not available')
        await update.message.reply_text(help_text)
    
    async def summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Market summary"""
        await update.message.reply_text("📊 Analyzing top 10 coins...")
        
        opportunities = await signal_generator.get_top_opportunities(10)
        
        if not opportunities:
            await update.message.reply_text("❌ Could not fetch market data")
            return
        
        summary = "📈 **Market Summary**\n\n"
        for i, signal in enumerate(opportunities[:5], 1):
            summary += f"""{i}. **{signal['symbol'].upper()}**
   Price: ${signal['price']:.2f}
   RSI: {signal['rsi']:.1f}
   Signal: {signal['signal_type']}
   Confidence: {signal['confidence']}%
   R:R Ratio: {signal['risk_reward_ratio']:.2f}:1\n"""
        
        await update.message.reply_text(summary, parse_mode='Markdown')
    
    async def top_opportunities(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show top trading opportunities"""
        await update.message.reply_text("🔍 Finding top opportunities...")
        
        opportunities = await signal_generator.get_top_opportunities(5)
        
        message = "🎯 **Top Trading Opportunities**\n\n"
        for signal in opportunities:
            message += f"""
🔹 **{signal['symbol'].upper()}**
   Entry: ${signal['entry_point']:.2f}
   Stop Loss: ${signal['stop_loss']:.2f}
   Take Profit: ${signal['take_profit']:.2f}
   Risk/Reward: {signal['risk_reward_ratio']:.2f}:1
   Confidence: {signal['confidence']}%
   Signal: {signal['signal_type']}
"""
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def buy_signal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get buy signals"""
        if not context.args:
            await update.message.reply_text("Usage: /buy <coin_name>")
            return
        
        coin = context.args[0].lower()
        await update.message.reply_text(f"📊 Analyzing {coin}...")
        
        signal = await signal_generator.generate_signal(coin)
        
        if not signal:
            await update.message.reply_text(f"❌ Could not analyze {coin}")
            return
        
        message = f"""
🟢 **BUY Analysis for {coin.upper()}**

Current Price: ${signal['price']:.2f}
RSI: {signal['rsi']:.1f}
Volatility: {signal['volatility']:.2f}%

Entry Point: ${signal['entry_point']:.2f}
Stop Loss: ${signal['stop_loss']:.2f}
Take Profit: ${signal['take_profit']:.2f}

Risk/Reward: {signal['risk_reward_ratio']:.2f}:1
Confidence: {signal['confidence']}%
Signal Type: {signal['signal_type']}
"""
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def portfolio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show portfolio"""
        user_id = str(update.effective_user.id)
        summary = self.portfolio_tracker.get_portfolio_summary(user_id)
        
        if summary['holdings_count'] == 0:
            await update.message.reply_text("📭 Your portfolio is empty")
            return
        
        message = f"""
💼 **Your Portfolio**

Total Invested: ${summary['total_invested']:.2f}
Current Value: ${summary['total_current']:.2f}
Profit/Loss: ${summary['total_profit_loss']:.2f}
ROI: {summary['total_roi']:.2f}%

Holdings: {summary['holdings_count']}
"""
        
        for holding in summary['portfolio']:
            message += f"""
📌 {holding['coin'].upper()}
   Quantity: {holding['quantity']}
   Entry Price: ${holding['entry_price']:.2f}
   Current: ${holding['current_price']:.2f}
   P&L: ${holding['profit_loss']:.2f}
   ROI: {holding['roi']:.2f}%
"""
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def news(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get latest crypto news"""
        await update.message.reply_text("📰 Fetching latest news...")
        
        news_list = await news_aggregator.fetch_news(limit=5)
        
        if not news_list:
            await update.message.reply_text("❌ Could not fetch news")
            return
        
        message = "📰 **Latest Crypto News**\n\n"
        for i, news in enumerate(news_list, 1):
            message += f"""{i}. **{news['title'][:50]}...**
   Source: {news['source']}
   🔗 {news['link'][:60]}\n\n"""
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Bot status"""
        stats = self.db.get_daily_stats()
        
        message = f"""
🤖 **Bot Status**

✅ Status: ONLINE
⏰ Uptime: 24/7
📊 Signals Today: {stats['total_signals']}
🟢 Buy Signals: {stats['buy_signals']}
🔴 Sell Signals: {stats['sell_signals']}
📍 Coins Tracked: {stats['unique_coins']}

🔄 Polling: Active
🔍 Analysis: Real-time
📱 Connected: ✓
"""
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def language_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Change language"""
        if context.args:
            lang = context.args[0].lower()
            if language_support.set_language(lang):
                await update.message.reply_text(f"✅ Language changed to {language_support.LANGUAGES.get(lang)}")
            else:
                langs = ", ".join(language_support.LANGUAGES.values())
                await update.message.reply_text(f"❌ Language not supported. Available: {langs}")
        else:
            langs = ", ".join([f"{code}: {name}" for code, name in language_support.LANGUAGES.items()])
            await update.message.reply_text(f"Available languages:\n{langs}\n\nUsage: /language <code>")


