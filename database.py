"""
database.py — SQLite storage for signals, cooldowns, news cache.
Thread-safe via per-call connections (sqlite3 handles WAL mode).
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from config import Config
from utils.logger import get_logger

logger = get_logger(__name__)


class Database:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or Config.DATABASE_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        logger.info(f"Database ready: {self.db_path}")

    # ── Connection ───────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    # ── Schema ───────────────────────────────────────────────

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS signals (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    coin         TEXT    NOT NULL,
                    action       TEXT    NOT NULL,
                    signal_type  TEXT    NOT NULL,
                    confidence   INTEGER NOT NULL,
                    risk_level   TEXT    NOT NULL,
                    reasons      TEXT    NOT NULL,
                    bot_view     TEXT    NOT NULL,
                    price        REAL    NOT NULL,
                    timeframe    TEXT    NOT NULL DEFAULT '1D',
                    timestamp    TEXT    NOT NULL,
                    alert_sent   INTEGER DEFAULT 0,
                    created_at   TEXT    DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS cooldown (
                    coin            TEXT NOT NULL,
                    action          TEXT NOT NULL,
                    cooldown_until  TEXT NOT NULL,
                    PRIMARY KEY (coin, action)
                );

                CREATE TABLE IF NOT EXISTS news_seen (
                    url        TEXT PRIMARY KEY,
                    title      TEXT,
                    seen_at    TEXT DEFAULT (datetime('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_sig_coin ON signals(coin);
                CREATE INDEX IF NOT EXISTS idx_sig_ts   ON signals(timestamp);
            """)

    # ── Signals ──────────────────────────────────────────────

    def insert_signal(self, signal: Dict) -> None:
        reasons = signal.get("reasons", [])
        if isinstance(reasons, list):
            reasons = json.dumps(reasons)
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO signals
                   (coin, action, signal_type, confidence, risk_level,
                    reasons, bot_view, price, timeframe, timestamp)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    signal.get("coin", signal.get("symbol", "?")),
                    signal.get("action", ""),
                    signal.get("signal_type", "SCAN"),
                    signal.get("confidence", 0),
                    signal.get("risk_level", "HIGH"),
                    reasons,
                    signal.get("bot_view", ""),
                    signal.get("price", 0),
                    signal.get("timeframe", "1D"),
                    signal.get("timestamp", datetime.utcnow().isoformat()),
                ),
            )

    def get_recent_signals(self, limit: int = 20) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM signals ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_daily_stats(self) -> Dict:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        with self._conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM signals WHERE timestamp LIKE ?", (f"{today}%",)
            ).fetchone()[0]
            buys = conn.execute(
                "SELECT COUNT(*) FROM signals WHERE timestamp LIKE ? AND action='BUY LONG'",
                (f"{today}%",),
            ).fetchone()[0]
            sells = conn.execute(
                "SELECT COUNT(*) FROM signals WHERE timestamp LIKE ? AND action='SELL SHORT'",
                (f"{today}%",),
            ).fetchone()[0]
            unique = conn.execute(
                "SELECT COUNT(DISTINCT coin) FROM signals WHERE timestamp LIKE ?",
                (f"{today}%",),
            ).fetchone()[0]
        return {
            "total_signals": total,
            "buy_signals": buys,
            "sell_signals": sells,
            "unique_coins": unique,
        }

    # ── Cooldown ─────────────────────────────────────────────

    def check_cooldown(self, coin: str, action: str) -> bool:
        """Returns True if still in cooldown (should NOT alert)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT cooldown_until FROM cooldown WHERE coin=? AND action=?",
                (coin, action),
            ).fetchone()
        if not row:
            return False
        return datetime.utcnow() < datetime.fromisoformat(row["cooldown_until"])

    def set_cooldown(self, coin: str, action: str, hours: int) -> None:
        until = (datetime.utcnow() + timedelta(hours=hours)).isoformat()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO cooldown (coin, action, cooldown_until)
                   VALUES (?,?,?)
                   ON CONFLICT(coin,action) DO UPDATE SET cooldown_until=excluded.cooldown_until""",
                (coin, action, until),
            )

    # ── News dedup ───────────────────────────────────────────

    def is_news_seen(self, url: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM news_seen WHERE url=?", (url,)
            ).fetchone()
        return row is not None

    def mark_news_seen(self, url: str, title: str = "") -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO news_seen (url, title) VALUES (?,?)",
                (url, title),
            )


# Module-level singleton used by other modules
db = Database()
