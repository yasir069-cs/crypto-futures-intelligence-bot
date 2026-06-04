from telegram import Update
from telegram.ext import ContextTypes

from core.market_analyzer import market_analyzer
from core.news_aggregator import news_aggregator
from core.portfolio_tracker import PortfolioTracker
from core.trading_signals import signal_generator
from models.language_support import language_support
from utils.logger import get_logger

logger = get_logger(__name__)


class TelegramHandlers:
    """Handle Telegram bot commands."""

    def __init__(self, db_instance):
        self.db = db_instance
        self.portfolio_tracker = PortfolioTracker(self.db)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user_name = update.effective_user.first_name
        message = (
            f"Welcome to Crypto Futures Intelligence Bot, {user_name}!\n\n"
            "I can scan top crypto markets, separate BUY and SELL opportunities, "
            "send scheduled signal alerts, and analyze individual coins.\n\n"
            "Use /help to see all commands or /top to scan current opportunities."
        )
        await update.message.reply_text(message)
        logger.info(f"User {user_name} ({update.effective_user.id}) started the bot")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_text = (
            "Available Commands:\n"
            "/start - Start the bot\n"
            "/status - Check bot status\n"
            "/summary - Market summary\n"
            "/top - Top BUY and SELL opportunities\n"
            "/buy <coin> - Get BUY analysis for a coin\n"
            "/sell <coin> - Get SELL analysis for a coin\n"
            "/analysis <coin> - Detailed coin analysis\n"
            "/alerts - Show automatic alert configuration\n"
            "/portfolio - View your portfolio\n"
            "/news - Latest crypto news\n"
            "/language <code> - Change language\n"
            "/help - Show this help"
        )
        await update.message.reply_text(help_text)

    async def summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Market summary."""
        await update.message.reply_text("Scanning the top 100 coins...")
        opportunities = await signal_generator.get_top_opportunities(10)

        if not opportunities:
            await update.message.reply_text("No BUY or SELL opportunities found right now.")
            return

        message = "Market Summary\n\n"
        for index, signal in enumerate(opportunities[:10], 1):
            message += self._format_signal_summary(index, signal)

        await update.message.reply_text(message)

    async def top_opportunities(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show top BUY and SELL opportunities separately."""
        await update.message.reply_text("Scanning top 100 coins for BUY and SELL opportunities...")

        buy_signals = await signal_generator.get_top_opportunities(5, action="BUY LONG")
        sell_signals = await signal_generator.get_top_opportunities(5, action="SELL SHORT")

        if not buy_signals and not sell_signals:
            await update.message.reply_text("No non-HOLD opportunities found right now.")
            return

        message = "Top Trading Opportunities\n\n"
        message += "BUY Opportunities\n"
        message += self._format_signal_list(buy_signals) if buy_signals else "None right now.\n"
        message += "\nSELL Opportunities\n"
        message += self._format_signal_list(sell_signals) if sell_signals else "None right now.\n"

        await update.message.reply_text(message)

    async def buy_signal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get buy analysis for a coin."""
        coin = await self._get_coin_arg(update, context, "/buy <coin>")
        if not coin:
            return

        signal = await self._load_coin_signal(update, coin)
        if not signal:
            return

        if signal["action"] == "SELL SHORT":
            await update.message.reply_text(
                f"{signal['symbol'].upper()} is currently a SELL setup, not a BUY.\n\n"
                f"{self._format_signal_detail(signal)}"
            )
            return

        if signal["action"] == "HOLD":
            await update.message.reply_text(
                f"{signal['symbol'].upper()} is currently HOLD/neutral. No BUY setup found."
            )
            return

        await update.message.reply_text(self._format_signal_detail(signal))

    async def sell_signal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get sell analysis for a coin."""
        coin = await self._get_coin_arg(update, context, "/sell <coin>")
        if not coin:
            return

        signal = await self._load_coin_signal(update, coin)
        if not signal:
            return

        if signal["action"] == "BUY LONG":
            await update.message.reply_text(
                f"{signal['symbol'].upper()} is currently a BUY setup, not a SELL.\n\n"
                f"{self._format_signal_detail(signal)}"
            )
            return

        if signal["action"] == "HOLD":
            await update.message.reply_text(
                f"{signal['symbol'].upper()} is currently HOLD/neutral. No SELL setup found."
            )
            return

        await update.message.reply_text(self._format_signal_detail(signal))

    async def analysis(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Detailed coin analysis."""
        coin = await self._get_coin_arg(update, context, "/analysis <coin>")
        if not coin:
            return

        coin_id = signal_generator.normalize_symbol(coin)
        await update.message.reply_text(f"Running detailed analysis for {coin_id.upper()}...")

        analysis = await market_analyzer.analyze_coin(coin_id)
        signal = await signal_generator.generate_signal(coin_id)
        if not analysis or not signal:
            await update.message.reply_text(f"Could not analyze {coin}. Try a CoinGecko id like bitcoin or ethereum.")
            return

        message = (
            f"Detailed Analysis: {coin_id.upper()}\n\n"
            f"Price: ${analysis.get('current_price', 0):.6g}\n"
            f"Signal: {signal['signal_type']} ({signal['action']})\n"
            f"Confidence: {signal['confidence']}%\n"
            f"Risk: {signal['risk_level']}\n"
            f"RSI: {analysis.get('rsi', 0):.1f}\n"
            f"MACD: {analysis.get('macd', 0):.6g}\n"
            f"Volatility: {analysis.get('volatility', 0):.2f}%\n"
            f"24h Change: {analysis.get('price_change_24h', 0):.2f}%\n"
            f"7d Change: {analysis.get('price_change_7d', 0):.2f}%\n"
            f"30d Change: {analysis.get('price_change_30d', 0):.2f}%\n"
            f"Support: ${analysis.get('support', 0):.6g}\n"
            f"Resistance: ${analysis.get('resistance', 0):.6g}\n\n"
            f"{signal['bot_view']}"
        )
        await update.message.reply_text(message)

    async def alerts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show automatic alert configuration."""
        stats = self.db.get_daily_stats()
        message = (
            "Automatic Signal Alerts\n\n"
            "Status: enabled\n"
            "Scanner: top 100 coins by market cap\n"
            "Interval: every 15 minutes\n"
            "Filters: HOLD signals are excluded\n"
            "Alerts: BUY LONG and SELL SHORT only\n"
            "Cooldown: one alert per coin/action every 6 hours\n\n"
            f"Signals today: {stats['total_signals']}\n"
            f"BUY alerts today: {stats['buy_signals']}\n"
            f"SELL alerts today: {stats['sell_signals']}"
        )
        await update.message.reply_text(message)

    async def portfolio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show portfolio."""
        try:
            user_id = str(update.effective_user.id)
            summary = self.portfolio_tracker.get_portfolio_summary(user_id)
        except Exception as e:
            logger.error(f"Portfolio command failed: {e}", exc_info=True)
            await update.message.reply_text("Portfolio tracking is not initialized yet.")
            return

        if summary["holdings_count"] == 0:
            await update.message.reply_text("Your portfolio is empty.")
            return

        message = (
            "Your Portfolio\n\n"
            f"Total Invested: ${summary['total_invested']:.2f}\n"
            f"Current Value: ${summary['total_current']:.2f}\n"
            f"Profit/Loss: ${summary['total_profit_loss']:.2f}\n"
            f"ROI: {summary['total_roi']:.2f}%\n"
            f"Holdings: {summary['holdings_count']}\n"
        )
        for holding in summary["portfolio"]:
            message += (
                f"\n{holding['coin'].upper()}\n"
                f"Quantity: {holding['quantity']}\n"
                f"Entry Price: ${holding['entry_price']:.2f}\n"
                f"Current: ${holding['current_price']:.2f}\n"
                f"P&L: ${holding['profit_loss']:.2f}\n"
                f"ROI: {holding['roi']:.2f}%\n"
            )

        await update.message.reply_text(message)

    async def news(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get latest crypto news."""
        await update.message.reply_text("Fetching latest crypto news...")
        news_list = await news_aggregator.fetch_news(limit=5)

        if not news_list:
            await update.message.reply_text("Could not fetch news.")
            return

        message = "Latest Crypto News\n\n"
        for index, news in enumerate(news_list, 1):
            message += (
                f"{index}. {news['title'][:80]}\n"
                f"Source: {news['source']}\n"
                f"{news['link']}\n\n"
            )
        await update.message.reply_text(message)

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Bot status."""
        stats = self.db.get_daily_stats()
        message = (
            "Bot Status\n\n"
            "Status: ONLINE\n"
            f"Signals Today: {stats['total_signals']}\n"
            f"Buy Signals: {stats['buy_signals']}\n"
            f"Sell Signals: {stats['sell_signals']}\n"
            f"Coins Tracked Today: {stats['unique_coins']}\n"
            "Polling: Active\n"
            "Automatic Alerts: Active"
        )
        await update.message.reply_text(message)

    async def language_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Change language."""
        if context.args:
            lang = context.args[0].lower()
            if language_support.set_language(lang):
                await update.message.reply_text(f"Language changed to {language_support.LANGUAGES.get(lang)}")
            else:
                langs = ", ".join(language_support.LANGUAGES.values())
                await update.message.reply_text(f"Language not supported. Available: {langs}")
        else:
            langs = ", ".join([f"{code}: {name}" for code, name in language_support.LANGUAGES.items()])
            await update.message.reply_text(f"Available languages:\n{langs}\n\nUsage: /language <code>")

    async def _get_coin_arg(self, update: Update, context: ContextTypes.DEFAULT_TYPE, usage: str):
        if not context.args:
            await update.message.reply_text(f"Usage: {usage}")
            return None
        return context.args[0]

    async def _load_coin_signal(self, update: Update, coin: str):
        coin_id = signal_generator.normalize_symbol(coin)
        await update.message.reply_text(f"Analyzing {coin_id.upper()}...")
        signal = await signal_generator.generate_signal(coin_id)
        if not signal:
            await update.message.reply_text(f"Could not analyze {coin}. Try a CoinGecko id like bitcoin or ethereum.")
            return None
        return signal

    def _format_signal_list(self, signals):
        message = ""
        for index, signal in enumerate(signals, 1):
            message += self._format_signal_summary(index, signal)
        return message

    def _format_signal_summary(self, index: int, signal: dict):
        return (
            f"{index}. {signal['symbol'].upper()} - {signal['action']}\n"
            f"Price: ${signal['price']:.6g}\n"
            f"Signal: {signal['signal_type']}\n"
            f"Confidence: {signal['confidence']}%\n"
            f"Risk/Reward: {signal['risk_reward_ratio']:.2f}:1\n\n"
        )

    def _format_signal_detail(self, signal: dict):
        reasons = "\n".join(f"- {reason}" for reason in signal.get("reasons", [])[:5])
        return (
            f"{signal['action']} Analysis for {signal['symbol'].upper()}\n\n"
            f"Current Price: ${signal['price']:.6g}\n"
            f"Signal Type: {signal['signal_type']}\n"
            f"Confidence: {signal['confidence']}%\n"
            f"Risk Level: {signal['risk_level']}\n"
            f"RSI: {signal['rsi']:.1f}\n"
            f"Volatility: {signal['volatility']:.2f}%\n\n"
            f"Entry Point: ${signal['entry_point']:.6g}\n"
            f"Stop Loss: ${signal['stop_loss']:.6g}\n"
            f"Take Profit: ${signal['take_profit']:.6g}\n"
            f"Risk/Reward: {signal['risk_reward_ratio']:.2f}:1\n\n"
            f"Reasons:\n{reasons}"
        )
