import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import aiohttp
from config import Config
from database import db
from utils.logger import get_logger
from core.market_analyzer import market_analyzer

logger = get_logger(__name__)

class TradingSignalGenerator:
    """Generate advanced trading signals"""
    
    def __init__(self):
        self.signals_history = []
        self.win_rate_cache = {}
        self._top_coin_cache = []
        self._top_coin_cache_at = None
        self.coin_aliases = {
            'btc': 'bitcoin',
            'xbt': 'bitcoin',
            'bitcoin': 'bitcoin',
            'eth': 'ethereum',
            'ethereum': 'ethereum',
            'sol': 'solana',
            'solana': 'solana',
            'xrp': 'ripple',
            'ripple': 'ripple',
            'ada': 'cardano',
            'cardano': 'cardano',
            'doge': 'dogecoin',
            'dogecoin': 'dogecoin',
            'dot': 'polkadot',
            'polkadot': 'polkadot',
            'link': 'chainlink',
            'chainlink': 'chainlink',
            'ltc': 'litecoin',
            'litecoin': 'litecoin',
            'uni': 'uniswap',
            'uniswap': 'uniswap',
            'bnb': 'binancecoin',
            'binancecoin': 'binancecoin',
            'matic': 'matic-network',
            'polygon': 'matic-network',
            'avax': 'avalanche-2',
            'avalanche': 'avalanche-2',
            'trx': 'tron',
            'tron': 'tron',
        }

    def normalize_symbol(self, symbol: str) -> str:
        """Normalize user input into a CoinGecko coin id."""
        cleaned = symbol.strip().lower()
        cleaned = cleaned.replace('/usdt', '').replace('usdt', '')
        cleaned = cleaned.replace('-usd', '').replace('-usdt', '')
        return self.coin_aliases.get(cleaned, cleaned)
    
    async def generate_signal(self, symbol: str) -> Optional[Dict]:
        """Generate comprehensive trading signal"""
        try:
            coin_id = self.normalize_symbol(symbol)
            analysis = await market_analyzer.analyze_coin(coin_id)
            if not analysis:
                return None
            
            signal_type = self._determine_signal_type(analysis)
            action = self._signal_to_action(signal_type)
            signal = {
                'symbol': coin_id,
                'coin': coin_id,
                'action': action,
                'timestamp': datetime.utcnow().isoformat(),
                'price': analysis.get('current_price', 0),
                'rsi': analysis.get('rsi', 50),
                'volatility': analysis.get('volatility', 0),
                'support': analysis.get('support', 0),
                'resistance': analysis.get('resistance', 0),
                'signal_type': signal_type,
                'confidence': self._calculate_confidence(analysis),
                'entry_point': self._calculate_entry(analysis),
                'stop_loss': self._calculate_stop_loss(analysis),
                'take_profit': self._calculate_take_profit(analysis),
                'risk_reward_ratio': self._calculate_risk_reward(analysis),
                'price_change_24h': analysis.get('price_change_24h', 0),
                'price_change_7d': analysis.get('price_change_7d', 0),
                'price_change_30d': analysis.get('price_change_30d', 0),
                'macd': analysis.get('macd', 0),
                'risk_level': self._calculate_risk_level(self._calculate_confidence(analysis)),
                'reasons': self._build_reasons(analysis, signal_type),
                'bot_view': self._build_bot_view(signal_type),
                'timeframe': '1D'
            }
            
            return signal
        except Exception as e:
            logger.error(f"Error generating signal for {symbol}: {e}")
            return None
    
    def _determine_signal_type(self, analysis: Dict) -> str:
        """Determine signal type (BUY, SELL, HOLD)"""
        rsi = analysis.get('rsi', 50)
        volatility = analysis.get('volatility', 0)
        
        if rsi < 30 and volatility < 4:
            return "STRONG_BUY"
        elif rsi < 45:
            return "BUY"
        elif rsi > 70 and volatility > 3:
            return "STRONG_SELL"
        elif rsi > 55:
            return "SELL"
        else:
            return "HOLD"

    def _signal_to_action(self, signal_type: str) -> str:
        """Map a directional signal to database/action language."""
        if 'BUY' in signal_type:
            return 'BUY LONG'
        if 'SELL' in signal_type:
            return 'SELL SHORT'
        return 'HOLD'

    def _calculate_risk_level(self, confidence: int) -> str:
        if confidence >= 80:
            return 'LOW'
        if confidence >= 60:
            return 'MEDIUM'
        return 'HIGH'

    def _build_bot_view(self, signal_type: str) -> str:
        if 'BUY' in signal_type:
            return 'Bullish setup detected from RSI, volatility, and momentum context.'
        if 'SELL' in signal_type:
            return 'Bearish setup detected from RSI, volatility, and momentum context.'
        return 'No directional edge is strong enough yet.'

    def _build_reasons(self, analysis: Dict, signal_type: str) -> List[str]:
        reasons = [
            f"RSI: {analysis.get('rsi', 50):.1f}",
            f"24h change: {analysis.get('price_change_24h', 0):.2f}%",
            f"Volatility: {analysis.get('volatility', 0):.2f}%",
        ]
        if 'BUY' in signal_type:
            reasons.append('Price is near a bullish reversal/accumulation zone.')
        elif 'SELL' in signal_type:
            reasons.append('Price is near an overbought or bearish continuation zone.')
        return reasons
    
    def _calculate_confidence(self, analysis: Dict) -> int:
        """Calculate signal confidence (0-100)"""
        rsi = analysis.get('rsi', 50)
        volatility = analysis.get('volatility', 0)
        price_change = abs(analysis.get('price_change_24h', 0))
        
        confidence = 50
        
        # RSI extremes
        if rsi < 30 or rsi > 70:
            confidence += 20
        elif rsi < 40 or rsi > 60:
            confidence += 10
        
        # Volatility alignment
        if volatility < 2:
            confidence += 10
        elif volatility > 5:
            confidence -= 10
        
        # Price momentum
        if price_change > 5:
            confidence += 15
        elif price_change < 1:
            confidence += 5
        
        return min(100, max(0, confidence))
    
    def _calculate_entry(self, analysis: Dict) -> float:
        """Calculate optimal entry point"""
        current_price = analysis.get('current_price', 0)
        support = analysis.get('support', 0)
        rsi = analysis.get('rsi', 50)
        
        if rsi < 30:
            return support * 1.01  # Buy near support
        elif rsi > 70:
            return current_price * 0.98  # Sell pullback
        else:
            return current_price
    
    def _calculate_stop_loss(self, analysis: Dict) -> float:
        """Calculate stop loss level"""
        support = analysis.get('support', 0)
        current_price = analysis.get('current_price', 0)
        volatility = analysis.get('volatility', 0)
        
        # Stop loss 2% below support
        return support * 0.98
    
    def _calculate_take_profit(self, analysis: Dict) -> float:
        """Calculate take profit level"""
        resistance = analysis.get('resistance', 0)
        current_price = analysis.get('current_price', 0)
        
        # Take profit 2% above resistance
        return resistance * 1.02
    
    def _calculate_risk_reward(self, analysis: Dict) -> float:
        """Calculate risk-reward ratio"""
        try:
            entry = self._calculate_entry(analysis)
            sl = self._calculate_stop_loss(analysis)
            tp = self._calculate_take_profit(analysis)
            
            risk = abs(entry - sl)
            reward = abs(tp - entry)
            
            if risk > 0:
                return reward / risk
            return 0
        except:
            return 0
    
    async def get_top_coin_ids(self, limit: int = None) -> List[str]:
        """Fetch the top CoinGecko coin ids by market cap."""
        limit = limit or Config.TOP_COINS_SCAN_LIMIT
        if (
            self._top_coin_cache
            and self._top_coin_cache_at
            and datetime.utcnow() - self._top_coin_cache_at < timedelta(minutes=30)
        ):
            return self._top_coin_cache[:limit]

        url = f"{market_analyzer.base_url}/coins/markets"
        params = {
            'vs_currency': 'usd',
            'order': 'market_cap_desc',
            'per_page': min(max(limit, 1), 250),
            'page': 1,
            'sparkline': 'false',
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        self._top_coin_cache = [coin['id'] for coin in data if coin.get('id')]
                        self._top_coin_cache_at = datetime.utcnow()
        except Exception as e:
            logger.error(f"Error fetching top coins: {e}")

        if not self._top_coin_cache:
            self._top_coin_cache = [
                'bitcoin', 'ethereum', 'tether', 'binancecoin', 'solana',
                'ripple', 'usd-coin', 'dogecoin', 'cardano', 'tron',
                'avalanche-2', 'chainlink', 'polkadot', 'matic-network',
                'litecoin', 'uniswap',
            ]
        return self._top_coin_cache[:limit]

    async def scan_top_coins(self, limit: int = None, include_hold: bool = False) -> List[Dict]:
        """Analyze top market-cap coins and optionally filter HOLD signals."""
        coin_ids = await self.get_top_coin_ids(limit or Config.TOP_COINS_SCAN_LIMIT)
        tasks = [self.generate_signal(coin) for coin in coin_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        signals = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Top coin scan failed: {result}")
                continue
            if not result:
                continue
            if not include_hold and result.get('action') == 'HOLD':
                continue
            signals.append(result)

        return sorted(signals, key=lambda x: x.get('confidence', 0), reverse=True)

    async def get_top_opportunities(self, limit: int = 10, action: str = None) -> List[Dict]:
        """Get top non-HOLD trading opportunities, optionally by action."""
        signals = await self.scan_top_coins(Config.TOP_COINS_SCAN_LIMIT, include_hold=False)
        if action:
            signals = [signal for signal in signals if signal.get('action') == action]
        return signals[:limit]

signal_generator = TradingSignalGenerator()
