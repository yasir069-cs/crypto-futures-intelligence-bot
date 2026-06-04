import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from config import Config
from utils.logger import get_logger

logger = get_logger(__name__)

class Database:
    """SQLite database manager"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or Config.DATABASE_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = None # Store connection for in-memory DB
        self.init_database()
    
    def get_connection(self):
        """Get database connection"""
        if self.db_path == ":memory:" and self._conn:
            return self._conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        if self.db_path == ":memory:":
            self._conn = conn
        return conn
    
    def init_database(self):
        """Initialize database schema"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Signals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coin TEXT NOT NULL,
                action TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                confidence INTEGER NOT NULL,
                risk_level TEXT NOT NULL,
                reasons TEXT NOT NULL,
                bot_view TEXT NOT NULL,
                price REAL NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                alert_sent BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Cooldown table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cooldown (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coin TEXT UNIQUE NOT NULL,
                action TEXT NOT NULL,
                last_alert_time DATETIME NOT NULL,
                cooldown_until DATETIME NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Market data cache table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coin TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                timestamp DATETIME NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Analysis logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analysis_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coin TEXT NOT NULL,
                analysis_data TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indices for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_coin ON signals(coin)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cooldown_coin ON cooldown(coin)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_market_data_coin_tf ON market_data(coin, timeframe)')
        
        conn.commit()
        if self.db_path != ":memory:":
            conn.close()
        logger.info("Database initialized successfully")
    
    def insert_signal(self, signal_data: Dict) -> int:
        """Insert signal into database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO signals 
                (coin, action, signal_type, confidence, risk_level, reasons, bot_view, price, timeframe, timestamp, alert_sent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                signal_data['coin'],
                signal_data['action'],
                signal_data['signal_type'],
                signal_data['confidence'],
                signal_data['risk_level'],
                json.dumps(signal_data['reasons']),
                signal_data['bot_view'],
                signal_data['price'],
                signal_data['timeframe'],
                signal_data['timestamp'],
                1  # alert_sent
            ))
            
            conn.commit()
            signal_id = cursor.lastrowid
            logger.info(f"Signal inserted: {signal_data['coin']} {signal_data['action']} (ID: {signal_id})")
            return signal_id
        except Exception as e:
            logger.error(f"Error inserting signal: {e}")
            raise
        finally:
            conn.close()
    
    def get_recent_signals(self, limit: int = 50) -> List[Dict]:
        """Get recent signals"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM signals
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_signals_by_coin(self, coin: str, limit: int = 10) -> List[Dict]:
        """Get signals for a specific coin"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM signals
            WHERE coin = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (coin, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_signals_by_action(self, action: str, limit: int = 50) -> List[Dict]:
        """Get signals by action type"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM signals
            WHERE action = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (action, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def check_cooldown(self, coin: str, action: str) -> bool:
        """Check if coin is in cooldown"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT cooldown_until FROM cooldown
            WHERE coin = ? AND action = ?
        ''', (coin, action))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            cooldown_until = datetime.fromisoformat(row['cooldown_until'])
            if datetime.utcnow() < cooldown_until:
                return True
        
        return False
    
    def set_cooldown(self, coin: str, action: str, cooldown_hours: int):
        """Set cooldown for coin"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.utcnow()
        cooldown_until = datetime.utcfromtimestamp(
            now.timestamp() + (cooldown_hours * 3600)
        )
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO cooldown (coin, action, last_alert_time, cooldown_until)
                VALUES (?, ?, ?, ?)
            ''', (coin, action, now, cooldown_until))
            
            conn.commit()
            logger.info(f"Cooldown set for {coin} {action} until {cooldown_until}")
        except Exception as e:
            logger.error(f"Error setting cooldown: {e}")
            raise
        finally:
            conn.close()
    
    def get_daily_stats(self) -> Dict:
        """Get daily statistics"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        today = datetime.utcnow().date()
        
        # Total signals today
        cursor.execute('''
            SELECT COUNT(*) as total FROM signals
            WHERE DATE(timestamp) = ?
        ''', (today,))
        total = cursor.fetchone()['total']
        
        # BUY signals
        cursor.execute('''
            SELECT COUNT(*) as buy_count FROM signals
            WHERE DATE(timestamp) = ? AND action = 'BUY LONG'
        ''', (today,))
        buy_count = cursor.fetchone()['buy_count']
        
        # SELL signals
        cursor.execute('''
            SELECT COUNT(*) as sell_count FROM signals
            WHERE DATE(timestamp) = ? AND action = 'SELL SHORT'
        ''', (today,))
        sell_count = cursor.fetchone()['sell_count']
        
        # Unique coins
        cursor.execute('''
            SELECT COUNT(DISTINCT coin) as unique_coins FROM signals
            WHERE DATE(timestamp) = ?
        ''', (today,))
        unique_coins = cursor.fetchone()['unique_coins']
        
        conn.close()
        
        return {
            'total_signals': total,
            'buy_signals': buy_count,
            'sell_signals': sell_count,
            'unique_coins': unique_coins,
            'date': str(today)
        }
    
    def cleanup_old_data(self, days: int = 30):
        """Clean up old data"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                DELETE FROM signals
                WHERE DATE(timestamp) < DATE('now', '-' || ? || ' days')
            ''', (days,))
            
            cursor.execute('''
                DELETE FROM market_data
                WHERE DATE(timestamp) < DATE('now', '-' || ? || ' days')
            ''', (days,))
            
            cursor.execute('''
                DELETE FROM analysis_logs
                WHERE DATE(timestamp) < DATE('now', '-' || ? || ' days')
            ''', (days,))
            
            conn.commit()
            deleted = cursor.rowcount
            logger.info(f"Cleaned up {deleted} old records")
        except Exception as e:
            logger.error(f"Error cleaning up data: {e}")
            raise
        finally:
            conn.close()
    def get_portfolio(self, user_id: str):
        """Get user portfolio"""

        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT *
            FROM portfolio
            WHERE user_id = ?
        """, (user_id,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]
db = Database()
