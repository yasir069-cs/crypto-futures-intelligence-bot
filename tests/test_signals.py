"""Tests for signal generation"""

import pytest
from database import Database

@pytest.fixture
def test_db():
    """Create test database"""
    db = Database(":memory:")
    db.init_database()
    yield db
    # No explicit teardown needed for in-memory database, it's destroyed when connection closes

def test_insert_signal(test_db):
    """Test inserting a signal"""
    signal_data = {
        'coin': 'BTCUSDT',
        'action': 'BUY LONG',
        'signal_type': 'SWING',
        'confidence': 92,
        'risk_level': 'LOW',
        'reasons': ['Test reason'],
        'bot_view': 'Test view',
        'price': 50000,
        'timeframe': '4H',
        'timestamp': '2024-01-01T00:00:00'
    }
    
    signal_id = test_db.insert_signal(signal_data)
    assert signal_id > 0

def test_get_recent_signals(test_db):
    """Test retrieving recent signals"""
    signals = test_db.get_recent_signals(limit=10)
    assert isinstance(signals, list)
