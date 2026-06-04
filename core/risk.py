"""Risk Assessment Engine"""

from typing import Dict
from config import Config
from utils.logger import get_logger

logger = get_logger(__name__)

class RiskEngine:
    """Calculate and classify risk levels"""
    
    def __init__(self):
        self.risk_levels = Config.RISK_LEVELS
    
    def calculate_risk(self, confidence: int, reason_count: int) -> str:
        """
        Calculate risk level based on:
        - Confidence score
        - Number of confirmation reasons
        
        Returns: 'LOW', 'MEDIUM', 'HIGH'
        """
        
        # Normalize confidence to 0-1
        normalized_confidence = confidence / 100.0
        
        # Boost score with more reasons
        reason_boost = min(0.2, reason_count * 0.05)
        adjusted_score = normalized_confidence + reason_boost
        adjusted_score = min(1.0, adjusted_score)
        
        # Classify risk
        if adjusted_score >= self.risk_levels['LOW']['min_confidence'] / 100:
            return 'LOW'
        elif adjusted_score >= self.risk_levels['MEDIUM']['min_confidence'] / 100:
            return 'MEDIUM'
        else:
            return 'HIGH'
    
    def get_risk_description(self, risk_level: str) -> str:
        """Get risk level description"""
        descriptions = {
            'LOW': 'Strong trend, strong volume, strong structure',
            'MEDIUM': 'Good setup with some conflicting factors',
            'HIGH': 'Volatile conditions, weak confirmation'
        }
        return descriptions.get(risk_level, 'Unknown')
