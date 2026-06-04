import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
from database import Database
from utils.logger import get_logger

logger = get_logger(__name__)

class PortfolioTracker:
    """Track user portfolio and P&L"""
    
    def __init__(self, db_instance):
        self.db = db_instance
        self.init_tables()
    
    def init_tables(self):
        """Initialize portfolio tables"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Portfolio holdings
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                coin TEXT NOT NULL,
                quantity REAL NOT NULL,
                entry_price REAL NOT NULL,
                current_price REAL NOT NULL,
                buy_date DATETIME NOT NULL,
                profit_loss REAL,
                roi REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Trading history
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                coin TEXT NOT NULL,
                action TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL NOT NULL,
                fee REAL,
                total REAL NOT NULL,
                trade_date DATETIME NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_holding(self, user_id: str, coin: str, quantity: float, entry_price: float) -> bool:
        """Add coin to portfolio"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO portfolio (user_id, coin, quantity, entry_price, current_price, buy_date)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, coin, quantity, entry_price, entry_price, datetime.utcnow()))
            
            conn.commit()
            conn.close()
            logger.info(f"Added {quantity} {coin} to portfolio for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error adding holding: {e}")
            return False
    
    def get_portfolio(self, user_id: str) -> List[Dict]:
        """Get user portfolio"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM portfolio WHERE user_id = ?', (user_id,))
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching portfolio: {e}")
            return []
    
    def update_price(self, user_id: str, coin: str, current_price: float) -> bool:
        """Update coin current price"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT quantity, entry_price FROM portfolio 
                WHERE user_id = ? AND coin = ?
            ''', (user_id, coin))
            row = cursor.fetchone()
            
            if row:
                quantity = row['quantity']
                entry_price = row['entry_price']
                
                profit_loss = (current_price - entry_price) * quantity
                roi = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
                
                cursor.execute('''
                    UPDATE portfolio 
                    SET current_price = ?, profit_loss = ?, roi = ?
                    WHERE user_id = ? AND coin = ?
                ''', (current_price, profit_loss, roi, user_id, coin))
                
                conn.commit()
            
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error updating price: {e}")
            return False
    
    def get_portfolio_summary(self, user_id: str) -> Dict:
        """Get portfolio summary"""
        portfolio = self.get_portfolio(user_id)
        
        total_invested = sum(p['quantity'] * p['entry_price'] for p in portfolio)
        total_current = sum(p['quantity'] * p['current_price'] for p in portfolio)
        total_profit_loss = total_current - total_invested
        total_roi = (total_profit_loss / total_invested * 100) if total_invested > 0 else 0
        
        return {
            'total_invested': total_invested,
            'total_current': total_current,
            'total_profit_loss': total_profit_loss,
            'total_roi': total_roi,
            'holdings_count': len(portfolio),
            'portfolio': portfolio
        }
    
    def record_trade(self, user_id: str, coin: str, action: str, quantity: float, price: float, fee: float = 0) -> bool:
        """Record trade transaction"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            total = quantity * price + fee
            
            cursor.execute('''
                INSERT INTO trades (user_id, coin, action, quantity, price, fee, total, trade_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, coin, action, quantity, price, fee, total, datetime.utcnow()))
            
            conn.commit()
            conn.close()
            logger.info(f"Recorded {action} trade for {quantity} {coin}")
            return True
        except Exception as e:
            logger.error(f"Error recording trade: {e}")
            return False
