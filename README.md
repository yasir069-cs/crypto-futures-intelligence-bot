# Crypto Futures Intelligence Bot

Personal-use Telegram bot for crypto futures analysis.
Works 100% from India — uses CoinGecko (free) + Binance public API (read-only, no auth).

---

## What it does

### Auto-alerts (no commands needed)
| Task | Interval | What it sends |
|------|----------|---------------|
| Signal scan | Every 30 min | BUY LONG / SELL SHORT alerts for top 100 coins |
| News alert | Every 15 min | Breaking news from CoinTelegraph, CoinDesk, Decrypt, etc. |
| Market report | Every 30 min | 30-min sentiment summary (bull/bear %, top setups) |
| Liquidation sweep | Every 5 min | Large liq events — long sweep = potential bounce, short sweep = potential reversal |

### Commands
| Command | Description |
|---------|-------------|
| `/top` | Top 10 BUY + 10 SELL from top 100 coins |
| `/buy BTC` | BUY LONG analysis for a coin |
| `/sell ETH` | SELL SHORT analysis for a coin |
| `/analysis BTC` | Full breakdown: RSI, EMA21/50, BB, MACD, S/R, entry/SL/TP |
| `/liq` | Latest liquidation sweeps right now |
| `/news` | Latest 5 crypto news articles |
| `/summary` | Quick market sentiment overview |
| `/status` | Bot uptime + today's signal count |
| `/alerts` | Scanner configuration |

---

## Signal logic

Each coin is scored using 5 indicators:

| Indicator | Weight | Bullish condition |
|-----------|--------|-------------------|
| RSI (14) | 25 pts | < 30 oversold |
| EMA21 > EMA50 | 20 pts | Price > EMA21 > EMA50 |
| Bollinger Bands | 15 pts | Price at/below lower band |
| MACD | 10 pts | MACD line positive |
| Volume + Momentum | 10 pts | RVOL > 2x + 24h move |

**Score ≥ 30 → BUY LONG | Score ≤ -30 → SELL SHORT | else HOLD**

Confidence = `abs(score) / 80 * 100` (0-100%)
Only signals above 65% confidence are auto-alerted.

---

## Liquidation Sweep Logic

- Pulls last 100 forced liquidations from Binance futures (public, no auth)
- Groups by symbol, sums USD notional in last 15 minutes
- **Long sweep (>$500K)**: many longs got liquidated → price dropped hard → potential bounce → BUY signal
- **Short sweep (>$500K)**: many shorts got liquidated → price pumped → potential reversal → SELL signal
- **This is information only** — you analyze, you decide, you trade.

---

## Setup

### 1. Clone / unzip

```bash
unzip crypto-futures-intelligence-bot.zip
cd crypto-futures-intelligence-bot
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create `.env`

```bash
cp .env.example .env
```

Edit `.env`:
```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

**Get bot token:** Chat with [@BotFather](https://t.me/BotFather), send `/newbot`

**Get chat ID:** Chat with [@userinfobot](https://t.me/userinfobot), send `/start`

### 4. Run

```bash
python main.py
```

---

## Deployment (keep running 24/7)

### Option A — systemd (Linux VPS / EC2)

```ini
# /etc/systemd/system/cryptobot.service
[Unit]
Description=Crypto Futures Intelligence Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/crypto-futures-intelligence-bot
ExecStart=/usr/bin/python3 main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable cryptobot
sudo systemctl start cryptobot
sudo systemctl status cryptobot
```

### Option B — Railway (free tier, easy)
1. Push to GitHub
2. railway.app → New Project → Deploy from GitHub
3. Add env vars in Railway dashboard

### Option C — Screen (quick & dirty)
```bash
screen -S cryptobot
python main.py
# Ctrl+A, D to detach
```

---

## Run tests

```bash
pytest tests/ -v
```

Expected: **28 passed**

---

## Project structure

```
crypto-futures-intelligence-bot/
├── main.py                    # Entry point
├── config.py                  # All settings from .env
├── database.py                # SQLite (signals, cooldowns, news dedup)
├── requirements.txt
├── .env.example
│
├── core/
│   ├── binance_client.py      # Binance public API (futures data, liquidations)
│   ├── market_analyzer.py     # CoinGecko + RSI/EMA/BB/MACD calculations
│   ├── trading_signals.py     # Signal scoring engine
│   ├── liquidation.py         # Liquidation sweep detector ← Priority #1
│   ├── news_aggregator.py     # RSS feeds (CoinTelegraph, CoinDesk, Decrypt...)
│   └── scheduler.py           # Background tasks (scan/news/report/liq loops)
│
├── bot_telegram/
│   ├── bot.py                 # Telegram app + command registration
│   └── handlers.py            # All /command implementations
│
├── utils/
│   ├── helpers.py             # RSI/EMA/BB/MACD math + formatters
│   └── logger.py              # Colored console logging
│
└── tests/
    └── test_bot.py            # 28 unit tests
```

---

## Supported coins (auto-detected by `/top`)

Top 100 by market cap — automatically fetched from CoinGecko.

For manual commands, use: `BTC`, `ETH`, `SOL`, `XRP`, `ADA`, `DOGE`,
`DOT`, `LINK`, `LTC`, `UNI`, `BNB`, `MATIC`, `AVAX`, `TRX`, `ATOM`,
`NEAR`, `APT`, `ARB`, `OP`, `SHIB` — or any CoinGecko coin ID.
