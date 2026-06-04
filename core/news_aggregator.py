"""
core/news_aggregator.py
Real-time crypto news from RSS feeds.
Sources: CoinTelegraph, CoinDesk, Bitcoin Magazine, Decrypt, Messari.
No API keys required — all public RSS.
"""

import asyncio
import aiohttp
import feedparser
from datetime import datetime
from typing import Dict, List, Optional

from database import db
from utils.logger import get_logger

logger = get_logger(__name__)

_FEEDS = [
    {
        "url":    "https://cointelegraph.com/feed/",
        "source": "CoinTelegraph",
    },
    {
        "url":    "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "source": "CoinDesk",
    },
    {
        "url":    "https://bitcoinmagazine.com/.rss/full/",
        "source": "Bitcoin Magazine",
    },
    {
        "url":    "https://decrypt.co/feed",
        "source": "Decrypt",
    },
    {
        "url":    "https://cryptoslate.com/feed/",
        "source": "CryptoSlate",
    },
]

# Keywords that make news "high priority"
_HIGH_PRIORITY = [
    "crash", "hack", "exploit", "ban", "sec", "regulation", "etf",
    "liquidation", "whale", "dump", "pump", "breakout", "ath",
    "all-time high", "bankruptcy", "halving", "fork",
]

_COIN_KEYWORDS = {
    "bitcoin":   ["btc", "bitcoin"],
    "ethereum":  ["eth", "ethereum"],
    "solana":    ["sol", "solana"],
    "ripple":    ["xrp", "ripple"],
    "binancecoin": ["bnb", "binance"],
    "cardano":   ["ada", "cardano"],
    "dogecoin":  ["doge", "dogecoin"],
    "matic-network": ["matic", "polygon"],
    "avalanche-2": ["avax", "avalanche"],
}


class NewsAggregator:
    def __init__(self):
        self._cache: List[Dict] = []
        self._cache_ts: Optional[datetime] = None
        self._ttl = 300  # seconds

    async def fetch_news(self, limit: int = 10, force: bool = False) -> List[Dict]:
        """Fetch latest news from all RSS feeds. Returns newest-first."""
        if not force and self._is_cached():
            return self._cache[:limit]

        articles = []
        timeout  = aiohttp.ClientTimeout(total=12)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            tasks = [self._fetch_feed(session, f) for f in _FEEDS]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                articles.extend(result)

        # De-duplicate by URL
        seen_urls = set()
        unique = []
        for a in articles:
            if a["url"] not in seen_urls:
                seen_urls.add(a["url"])
                unique.append(a)

        # Sort newest first (by published, fall back to fetched)
        unique.sort(key=lambda x: x.get("published_ts", 0), reverse=True)

        self._cache    = unique
        self._cache_ts = datetime.utcnow()
        return unique[:limit]

    async def fetch_new_only(self, limit: int = 5) -> List[Dict]:
        """Return only articles not previously seen (for push alerts)."""
        all_news = await self.fetch_news(limit=50, force=True)
        new_ones = []
        for article in all_news:
            if not db.is_news_seen(article["url"]):
                new_ones.append(article)
                db.mark_news_seen(article["url"], article["title"])
        return new_ones[:limit]

    def get_coin_news(self, coin_id: str) -> List[Dict]:
        """Filter cached news for a specific coin."""
        keywords = _COIN_KEYWORDS.get(coin_id, [coin_id])
        result   = []
        for a in self._cache:
            text = (a["title"] + " " + a.get("summary", "")).lower()
            if any(kw in text for kw in keywords):
                result.append(a)
        return result[:5]

    # ── Private ──────────────────────────────────────────────

    def _is_cached(self) -> bool:
        if not self._cache or not self._cache_ts:
            return False
        return (datetime.utcnow() - self._cache_ts).total_seconds() < self._ttl

    async def _fetch_feed(
        self, session: aiohttp.ClientSession, feed_info: Dict
    ) -> List[Dict]:
        url    = feed_info["url"]
        source = feed_info["source"]
        try:
            async with session.get(url) as r:
                if r.status != 200:
                    logger.warning(f"News feed {source} → HTTP {r.status}")
                    return []
                raw  = await r.text()
                feed = feedparser.parse(raw)

            articles = []
            for entry in feed.entries[:8]:
                title     = entry.get("title", "").strip()
                link      = entry.get("link", "")
                summary   = entry.get("summary", "")[:300]
                published = entry.get("published", "")

                # Parse timestamp
                ts = 0
                try:
                    import email.utils
                    ts = email.utils.parsedate_to_datetime(published).timestamp()
                except Exception:
                    pass

                priority = any(kw in title.lower() for kw in _HIGH_PRIORITY)

                articles.append({
                    "title":        title,
                    "url":          link,
                    "summary":      summary,
                    "source":       source,
                    "published":    published,
                    "published_ts": ts,
                    "high_priority": priority,
                })
            return articles
        except asyncio.TimeoutError:
            logger.warning(f"News feed {source} timeout")
            return []
        except Exception as e:
            logger.error(f"News feed {source}: {e}")
            return []


news_aggregator = NewsAggregator()
