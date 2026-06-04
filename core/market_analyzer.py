import aiohttp
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import ta
from utils.logger import get_logger

logger = get_logger(__name__)

class MarketAnalyzer:
    """Advanced market analysis with technical indicators"""
    
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.cache = {}
        self.cache_time = {}
    
    async def get_price_data(self, symbol: str, days: int = 30) -> Optional[Dict]:
        """Get historical price data"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/coins/{symbol}/market_chart"
                params = {'vs_currency': 'usd', 'days': days}
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
        except Exception as e:
            logger.error(f"Error fetching price data for {symbol}: {e}")
        return None
    
    async def analyze_coin(self, symbol: str) -> Dict:
        """Comprehensive coin analysis"""
        try:
            data = await self.get_price_data(symbol, days=90)
            if not data:
                return {}
            
            prices = np.array([p[1] for p in data['prices']])
            market_caps = np.array([v[1] for v in data["market_caps"]])
            
            # Technical Analysis
            df = pd.DataFrame({
                'close': prices,
                'market_cap': market_caps
            })
            
            # RSI (Relative Strength Index)
            rsi = ta.momentum.rsi(df['close'], window=14)
            current_rsi = rsi.iloc[-1]
            
            # MACD
            macd = ta.trend.macd(df['close'])
            
            # Bollinger Bands
            bb = ta.volatility.bollinger_bands(df['close'], window=20, window_dev=2)
            
            # Support & Resistance
            support, resistance = self._calculate_support_resistance(prices)
            
            # Volatility
            volatility = self._calculate_volatility(prices)
            
            # Price Changes
            price_change_24h = ((prices[-1] - prices[-2]) / prices[-2] * 100) if prices[-2] != 0 else 0
            price_change_7d = ((prices[-1] - prices[-7]) / prices[-7] * 100) if prices[-7] != 0 else 0
            price_change_30d = ((prices[-1] - prices[-30]) / prices[-30] * 100) if prices[-30] != 0 else 0
            
            return {
                'symbol': symbol,
                'current_price': prices[-1],
                'rsi': current_rsi,
                'macd': float(macd.iloc[-1]) if hasattr(macd, 'iloc') else macd[-1],
                'support': support,
                'resistance': resistance,
                'volatility': volatility,
                'price_change_24h': price_change_24h,
                'price_change_7d': price_change_7d,
                'price_change_30d': price_change_30d,
                'signal': self._generate_signal(current_rsi, volatility, price_change_24h),
                'timestamp': datetime.utcnow().isoformat()
            }
       except Exception as e:
    import traceback
    traceback.print_exc()
    logger.error(f"Error analyzing {symbol}: {e}")
    return {}
    
    def _calculate_support_resistance(self, prices: np.ndarray) -> tuple:
        """Calculate support and resistance levels"""
        support = np.min(prices[-30:])
        resistance = np.max(prices[-30:])
        return support, resistance
    
    def _calculate_volatility(self, prices: np.ndarray) -> float:
        """Calculate price volatility"""
        returns = np.diff(prices) / prices[:-1]
        volatility = np.std(returns) * 100
        return volatility
    
    def _generate_signal(self, rsi: float, volatility: float, price_change: float) -> str:
        """Generate trading signal"""
        if rsi < 30 and volatility < 3:
            return "🟢 STRONG BUY"
        elif rsi < 40:
            return "💚 BUY"
        elif rsi > 70 and volatility > 4:
            return "🔴 STRONG SELL"
        elif rsi > 60:
            return "❤️ SELL"
        else:
            return "⚪ NEUTRAL"

market_analyzer = MarketAnalyzer()
