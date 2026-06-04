import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from database import db
from utils.logger import get_logger
from core.market_analyzer import market_analyzer

logger = get_logger(__name__)

class TradingSignalGenerator:
    """Generate advanced trading signals"""
    
    def __init__(self):
        self.signals_history = []
        self.win_rate_cache = {}
    
    async def generate_signal(self, symbol: str) -> Optional[Dict]:
        """Generate comprehensive trading signal"""
        try:
            analysis = await market_analyzer.analyze_coin(symbol)
            if not analysis:
                return None
            
            signal = {
                'symbol': symbol,
                'timestamp': datetime.utcnow().isoformat(),
                'price': analysis.get('current_price', 0),
                'rsi': analysis.get('rsi', 50),
                'volatility': analysis.get('volatility', 0),
                'support': analysis.get('support', 0),
                'resistance': analysis.get('resistance', 0),
                'signal_type': self._determine_signal_type(analysis),
                'confidence': self._calculate_confidence(analysis),
                'entry_point': self._calculate_entry(analysis),
                'stop_loss': self._calculate_stop_loss(analysis),
                'take_profit': self._calculate_take_profit(analysis),
                'risk_reward_ratio': self._calculate_risk_reward(analysis)
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
    
    async def get_top_opportunities(self, limit: int = 10) -> List[Dict]:
        """Get top trading opportunities"""
        top_coins = ['bitcoin', 'ethereum', 'cardano', 'solana', 'ripple', 
                     'polkadot', 'dogecoin', 'litecoin', 'chainlink', 'uniswap']
        
        signals = []
        for coin in top_coins[:limit]:
    signal = await self.generate_signal(coin)

    print("DEBUG:", coin, bool(signal))

    if signal:
        signals.append(signal)
        
        # Sort by confidence
        return sorted(signals, key=lambda x: x.get('confidence', 0), reverse=True)

signal_generator = TradingSignalGenerator()
