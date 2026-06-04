"""Market Analysis Engine"""

from typing import Dict, List, Optional
from datetime import datetime
from utils.logger import get_logger
from utils.helpers import (
    moving_average, exponential_moving_average, calculate_rvol,
    calculate_oi_change, get_resistance_level, get_support_level,
    is_breakout, is_breakdown
)
from core.confidence import ConfidenceEngine
from core.risk import RiskEngine

logger = get_logger(__name__)

class Analyzer:
    """Multi-timeframe analysis engine"""
    
    def __init__(self):
        self.confidence_engine = ConfidenceEngine()
        self.risk_engine = RiskEngine()
    
    async def analyze_pair(
        self,
        coin: str,
        timeframe_data: Dict[str, List[Dict]],
        current_price: float,
        volume_data: Dict[str, float],
        oi_data: Dict[str, Dict]
    ) -> Optional[Dict]:
        """
        Analyze a trading pair across multiple timeframes
        
        Returns signal dict if confidence >= threshold, None otherwise
        """
        
        # Analyze each timeframe
        intraday_analysis = self._analyze_timeframe(
            coin, '15m', timeframe_data.get('15m', []),
            current_price, volume_data
        )
        
        intraday_1h = self._analyze_timeframe(
            coin, '1H', timeframe_data.get('1H', []),
            current_price, volume_data
        )
        
        swing_4h = self._analyze_timeframe(
            coin, '4H', timeframe_data.get('4H', []),
            current_price, volume_data
        )
        
        swing_1d = self._analyze_timeframe(
            coin, '1D', timeframe_data.get('1D', []),
            current_price, volume_data
        )
        
        # Generate intraday signal
        intraday_signal = self._generate_signal(
            coin, 'INTRADAY', current_price,
            [intraday_analysis, intraday_1h]
        )
        
        # Generate swing signal
        swing_signal = self._generate_signal(
            coin, 'SWING', current_price,
            [swing_4h, swing_1d]
        )
        
        # Return best signal
        if intraday_signal and swing_signal:
            return intraday_signal if intraday_signal['confidence'] >= swing_signal['confidence'] else swing_signal
        return intraday_signal or swing_signal
    
    def _analyze_timeframe(
        self,
        coin: str,
        timeframe: str,
        candles: List[Dict],
        current_price: float,
        volume_data: Dict[str, float]
    ) -> Dict:
        """Analyze single timeframe"""
        
        if not candles or len(candles) < 20:
            return {'score': 0, 'reasons': []}
        
        analysis = {
            'timeframe': timeframe,
            'candles': candles,
            'current_price': current_price,
            'scores': {},
            'reasons': []
        }
        
        # Extract OHLCV data
        closes = [float(c[4]) for c in candles]
        highs = [float(c[2]) for c in candles]
        lows = [float(c[3]) for c in candles]
        volumes = [float(c[5]) for c in candles]
        
        # Price expansion analysis
        price_expansion = self._analyze_price_expansion(closes, current_price)
        analysis['scores']['price_expansion'] = price_expansion['score']
        analysis['reasons'].extend(price_expansion['reasons'])
        
        # Volume analysis
        volume_analysis = self._analyze_volume(volumes)
        analysis['scores']['volume'] = volume_analysis['score']
        analysis['reasons'].extend(volume_analysis['reasons'])
        
        # Trend analysis
        trend_analysis = self._analyze_trend(closes)
        analysis['scores']['trend'] = trend_analysis['score']
        analysis['reasons'].extend(trend_analysis['reasons'])
        
        # Market structure
        structure_analysis = self._analyze_market_structure(closes, highs, lows, current_price)
        analysis['scores']['structure'] = structure_analysis['score']
        analysis['reasons'].extend(structure_analysis['reasons'])
        
        # Breakout/Breakdown
        breakout_analysis = self._analyze_breakouts(closes, highs, lows, current_price)
        analysis['scores']['breakout'] = breakout_analysis['score']
        analysis['reasons'].extend(breakout_analysis['reasons'])
        
        return analysis
    
    def _analyze_price_expansion(self, closes: List[float], current_price: float) -> Dict:
        """Analyze price expansion"""
        score = 0
        reasons = []
        
        # Check if price is at new highs
        recent_high = max(closes[-20:])
        recent_low = min(closes[-20:])
        
        if current_price > recent_high * 0.98:
            score += 20
            reasons.append("â€¢ Price near recent highs")
        elif current_price < recent_low * 1.02:
            score -= 20
            reasons.append("â€¢ Price near recent lows")
        
        return {'score': score, 'reasons': reasons}
    
    def _analyze_volume(self, volumes: List[float]) -> Dict:
        """Analyze volume"""
        score = 0
        reasons = []
        
        avg_volume = sum(volumes[-20:]) / 20
        current_volume = volumes[-1]
        rvol = calculate_rvol(current_volume, avg_volume)
        
        if rvol > 5:
            score += 25
            reasons.append(f"â€¢ Very strong volume ({rvol:.1f}x)")
        elif rvol > 3:
            score += 20
            reasons.append(f"â€¢ Strong volume ({rvol:.1f}x)")
        elif rvol > 1.5:
            score += 10
            reasons.append(f"â€¢ Above average volume ({rvol:.1f}x)")
        
        return {'score': score, 'reasons': reasons}
    
    def _analyze_trend(self, closes: List[float]) -> Dict:
        """Analyze trend using moving averages"""
        score = 0
        reasons = []
        
        # Calculate moving averages
        ma20 = sum(closes[-20:]) / 20
        ma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else ma20
        
        current = closes[-1]
        
        if current > ma20 > ma50:
            score += 25
            reasons.append("â€¢ Strong uptrend (above MA20 > MA50)")
        elif current < ma20 < ma50:
            score -= 25
            reasons.append("â€¢ Strong downtrend (below MA20 < MA50)")
        elif current > ma20:
            score += 15
            reasons.append("â€¢ Above MA20 (bullish)")
        elif current < ma20:
            score -= 15
            reasons.append("â€¢ Below MA20 (bearish)")
        
        return {'score': score, 'reasons': reasons}
    
    def _analyze_market_structure(self, closes: List[float], highs: List[float], lows: List[float], current_price: float) -> Dict:
        """Analyze market structure"""
        score = 0
        reasons = []
        
        resistance = get_resistance_level(highs)
        support = get_support_level(lows)
        
        if current_price > resistance * 0.99:
            score += 20
            reasons.append("â€¢ Near resistance level")
        elif current_price < support * 1.01:
            score -= 20
            reasons.append("â€¢ Near support level")
        
        return {'score': score, 'reasons': reasons}
    
    def _analyze_breakouts(self, closes: List[float], highs: List[float], lows: List[float], current_price: float) -> Dict:
        """Analyze breakouts/breakdowns"""
        score = 0
        reasons = []
        
        resistance = get_resistance_level(highs)
        support = get_support_level(lows)
        
        if is_breakout(current_price, resistance):
            score += 15
            reasons.append("â€¢ Breakout above resistance")
        elif is_breakdown(current_price, support):
            score -= 15
            reasons.append("â€¢ Breakdown below support")
        
        return {'score': score, 'reasons': reasons}
    
    def _generate_signal(
        self,
        coin: str,
        signal_type: str,
        current_price: float,
        timeframe_analyses: List[Dict]
    ) -> Optional[Dict]:
        """Generate signal from multi-timeframe analysis"""
        
        # Aggregate scores from all timeframes
        total_score = sum(
            sum(analysis.get('scores', {}).values()) if analysis.get('scores') else analysis.get('score', 0)
            for analysis in timeframe_analyses
        )
        all_reasons = []
        
        for analysis in timeframe_analyses:
            all_reasons.extend(analysis.get('reasons', []))
        
        # Determine action based on aggregate analysis
        # For now, simple logic - can be enhanced
        action = 'BUY LONG' if total_score > 50 else 'SELL SHORT' if total_score < -50 else None
        
        if action is None:
            return None
        
        # Calculate confidence
        confidence = min(99, int(abs(total_score) / 2))
        
        # Calculate risk
        risk_level = self.risk_engine.calculate_risk(confidence, len(all_reasons))
        
        # Generate bot view
        bot_view = self._generate_bot_view(action, confidence, all_reasons)
        
        return {
            'coin': coin,
            'action': action,
            'signal_type': signal_type,
            'confidence': confidence,
            'risk_level': risk_level,
            'reasons': all_reasons,
            'bot_view': bot_view,
            'price': current_price,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _generate_bot_view(self, action: str, confidence: int, reasons: List[str]) -> str:
        """Generate human-readable bot view"""
        if action == 'BUY LONG':
            if confidence > 90:
                return "Strong bullish momentum confirmed. Significant upside potential."
            elif confidence > 88:
                return "Current market structure favors upside continuation."
            else:
                return "Bullish setup forming with moderate confidence."
        else:  # SELL SHORT
            if confidence > 90:
                return "Strong bearish momentum confirmed. Significant downside potential."
            elif confidence > 88:
                return "Current market structure favors downside continuation."
            else:
                return "Bearish setup forming with moderate confidence."
